import argparse
import socket
import struct
import time

import printencoder
from PIL import Image


def make_packet(type_, data):
    checksum = type_ ^ len(data)
    for b in data:
        checksum ^= b
    return bytes((0x55, 0x55, type_, len(data), *data, checksum, 0xaa, 0xaa))


def transceive(sock, type_, data, timeout=2):
    sock.send(make_packet(type_, data))
    sock.settimeout(timeout)
    try:
        return sock.recv(1024)
    except socket.timeout:
        return b''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Niimbot D110M printer client")
    parser.add_argument('-a', '--address', required=True, help="MAC address of target device")
    parser.add_argument('-d', '--density', type=int, default=3, help="Printer density (1~5)")
    parser.add_argument('-n', '--quantity', type=int, default=1, help="Number of copies")
    parser.add_argument('image', help="PIL supported image file")
    args = parser.parse_args()

    img = Image.open(args.image)
    if img.width / img.height > 1:
        img = img.transpose(Image.ROTATE_270)

    rows, cols = img.height, img.width

    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    sock.connect((args.address, 1))

    transceive(sock, 0x23, b'\x01')                          # SET_LABEL_TYPE
    transceive(sock, 0x21, bytes([args.density]))             # SET_DENSITY
    # printStart9b: totalPages, 0,0,0,0, pageColor=0, speed=0, someFlag=0
    transceive(sock, 0x01, bytes([0x00, args.quantity, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00]))
    transceive(sock, 0xa3, b'\x01')                          # PRINT_STATUS
    # setPageSize13b: rows, cols, copies, 0,0,0,0,0,0,0
    transceive(sock, 0x13, struct.pack('>HHHHHBBBH', rows, cols, args.quantity, 0, 0, 0, 0, 0, 0))

    for pkt in printencoder.naive_encoder(img):
        sock.send(pkt.to_bytes())
    time.sleep(1)

    transceive(sock, 0xe3, b'\x01')                          # PAGE_END
    time.sleep(3)
    transceive(sock, 0xa3, b'\x01')                          # PRINT_STATUS
    time.sleep(2)
    transceive(sock, 0xf3, b'\x01')                          # PRINT_END

    sock.close()
