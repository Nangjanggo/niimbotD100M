import asyncio
import math
import os
import signal
import struct
import sys

import printencoder
from PIL import Image
from bleak import BleakClient, BleakScanner

CHAR_UUID = "bef8d6c9-9c21-4c9e-b632-bd58c1009f9f"
SOCKET_PATH = "/tmp/niimbot_printer.sock"
RECONNECT_DELAY = 8

client = None
connect_lock = None


def make_packet(type_, data):
    checksum = type_ ^ len(data)
    for b in data:
        checksum ^= b
    return bytes((0x55, 0x55, type_, len(data), *data, checksum, 0xaa, 0xaa))


async def print_image(c, image_path, density=3, quantity=1):
    img = Image.open(image_path)
    if img.width / img.height > 1:
        img = img.transpose(Image.ROTATE_270)

    rows, cols = img.height, img.width
    recv_queue = asyncio.Queue()

    def on_notify(_, data):
        recv_queue.put_nowait(data)

    await c.start_notify(CHAR_UUID, on_notify)

    async def transceive(type_, data, timeout=2):
        await c.write_gatt_char(CHAR_UUID, make_packet(type_, data), response=False)
        try:
            return await asyncio.wait_for(recv_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return b''

    await transceive(0x23, b'\x01')
    await transceive(0x21, bytes([density]))
    await transceive(0x01, bytes([0x00, quantity, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00]))
    await transceive(0xa3, b'\x01')
    await transceive(0x13, struct.pack('>HHHHHBBBH', rows, cols, quantity, 0, 0, 0, 0, 0, 0))

    for pkt in printencoder.naive_encoder(img):
        await c.write_gatt_char(CHAR_UUID, pkt.to_bytes(), response=False)
    await asyncio.sleep(0.3)

    await transceive(0xe3, b'\x01')
    await asyncio.sleep(1)
    await transceive(0xa3, b'\x01')
    await asyncio.sleep(0.3)
    await transceive(0xf3, b'\x01')

    await c.stop_notify(CHAR_UUID)


async def ensure_connected(address):
    global client, connect_lock
    if connect_lock is None:
        connect_lock = asyncio.Lock()
    async with connect_lock:
        if client is not None and client.is_connected:
            return client
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
            client = None

        while True:
            try:
                print(f"[daemon] scanning for {address}...", flush=True)
                device = await BleakScanner.find_device_by_address(address, timeout=10.0)
                if device is None:
                    raise RuntimeError("not found in scan")
                print(f"[daemon] connecting...", flush=True)
                c = BleakClient(device, timeout=20.0)
                await c.connect(dangerous_use_bleak_cache=True)
                client = c
                print(f"[daemon] connected", flush=True)
                return client
            except Exception as e:
                print(f"[daemon] connect failed: {type(e).__name__}: {e}, retrying in {RECONNECT_DELAY}s...", flush=True)
                await asyncio.sleep(RECONNECT_DELAY)


async def handle_job(address, reader, writer):
    global client
    try:
        line = await asyncio.wait_for(reader.readline(), timeout=10)
        image_path = line.decode().strip()
        if not image_path:
            writer.write(b"ERROR: empty path\n")
            await writer.drain()
            return

        print(f"[daemon] printing {image_path}", flush=True)
        c = await ensure_connected(address)
        try:
            await print_image(c, image_path)
            writer.write(b"OK\n")
            print(f"[daemon] done", flush=True)
        except Exception as e:
            print(f"[daemon] print error: {type(e).__name__}: {e}", flush=True)
            client = None  # force reconnect on next job
            writer.write(f"ERROR: {e}\n".encode())
    except Exception as e:
        print(f"[daemon] job error: {type(e).__name__}: {e}", flush=True)
        try:
            writer.write(f"ERROR: {e}\n".encode())
        except Exception:
            pass
    finally:
        try:
            await writer.drain()
            writer.close()
        except Exception:
            pass


async def run_daemon(address):
    global client

    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    def make_handler(addr):
        def handler(reader, writer):
            return handle_job(addr, reader, writer)
        return handler

    server = await asyncio.start_unix_server(make_handler(address), path=SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o666)
    print(f"[daemon] socket ready at {SOCKET_PATH}", flush=True)

    # pre-connect in background so first print is fast
    asyncio.ensure_future(ensure_connected(address))

    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: daemon.py <MAC>", file=sys.stderr)
        sys.exit(1)

    address = sys.argv[1]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown(sig, frame):
        print(f"[daemon] shutting down", flush=True)
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
        loop.stop()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        loop.run_until_complete(run_daemon(address))
    finally:
        loop.close()
