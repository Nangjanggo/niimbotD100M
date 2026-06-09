import argparse
import asyncio
import struct

import printencoder
from PIL import Image
from bleak import BleakClient

CHAR_UUID = "bef8d6c9-9c21-4c9e-b632-bd58c1009f9f"


def make_packet(type_, data):
    checksum = type_ ^ len(data)
    for b in data:
        checksum ^= b
    return bytes((0x55, 0x55, type_, len(data), *data, checksum, 0xaa, 0xaa))


async def print_label(address, image_path, density=3, quantity=1):
    img = Image.open(image_path)
    if img.width / img.height > 1:
        img = img.transpose(Image.ROTATE_270)

    rows, cols = img.height, img.width
    recv_queue = asyncio.Queue()

    def on_notify(_, data):
        recv_queue.put_nowait(data)

    async def transceive(type_, data, timeout=2):
        await client.write_gatt_char(CHAR_UUID, make_packet(type_, data), response=False)
        try:
            return await asyncio.wait_for(recv_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return b''

    async with BleakClient(address) as client:
        await client.start_notify(CHAR_UUID, on_notify)

        await transceive(0x23, b'\x01')                          # SET_LABEL_TYPE
        await transceive(0x21, bytes([density]))                  # SET_DENSITY
        await transceive(0x01, bytes([0x00, quantity, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00]))  # START_PRINT
        await transceive(0xa3, b'\x01')                          # PRINT_STATUS
        await transceive(0x13, struct.pack('>HHHHHBBBH', rows, cols, quantity, 0, 0, 0, 0, 0, 0))  # SET_PAGE_SIZE

        for pkt in printencoder.naive_encoder(img):
            await client.write_gatt_char(CHAR_UUID, pkt.to_bytes(), response=False)
        await asyncio.sleep(1)

        await transceive(0xe3, b'\x01')                          # PAGE_END
        await asyncio.sleep(3)
        await transceive(0xa3, b'\x01')                          # PRINT_STATUS
        await asyncio.sleep(2)
        await transceive(0xf3, b'\x01')                          # PRINT_END


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Niimbot D110M printer client")
    parser.add_argument('-a', '--address', required=True, help="MAC address of target device")
    parser.add_argument('-d', '--density', type=int, default=3, help="Printer density (1~5)")
    parser.add_argument('-n', '--quantity', type=int, default=1, help="Number of copies")
    parser.add_argument('image', help="PIL supported image file")
    args = parser.parse_args()

    asyncio.run(print_label(args.address, args.image, args.density, args.quantity))
