import socket, time, struct
from PIL import Image

addr = "06:A7:13:68:00:11"
sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
sock.connect((addr, 1))
sock.settimeout(3)

def send(type_, data):
    checksum = type_ ^ len(data)
    for i in data: checksum ^= i
    pkt = bytes((0x55, 0x55, type_, len(data), *data, checksum, 0xaa, 0xaa))
    print(f"send 0x{type_:02x}: {pkt.hex()}")
    sock.send(pkt)

def recv():
    try:
        d = sock.recv(1024)
        print(f"recv: {d.hex()}")
        return d
    except socket.timeout:
        print("recv: timeout")
        return b''

# SET_LABEL_TYPE = 0x23
send(0x23, b'\x01'); time.sleep(0.3); recv()
# SET_LABEL_DENSITY = 0x21
send(0x21, b'\x02'); time.sleep(0.3); recv()
# START_PRINT = 0x01
send(0x01, b'\x01'); time.sleep(0.3); recv()
# ALLOW_PRINT_CLEAR = 0x20
send(0x20, b'\x01'); time.sleep(0.3); recv()
# START_PAGE_PRINT = 0x03
send(0x03, b'\x01'); time.sleep(0.3); recv()
# SET_DIMENSION w=220 h=96 = 0x13
send(0x13, struct.pack('>HH', 220, 96)); time.sleep(0.3); recv()
# SET_QUANTITY = 0x15
send(0x15, struct.pack('>H', 1)); time.sleep(0.3); recv()
# END_PAGE_PRINT = 0xe3
send(0xe3, b'\x01'); time.sleep(0.5); recv()
# GET_PRINT_STATUS = 0xa3
send(0xa3, b'\x01'); time.sleep(0.5); recv()
# END_PRINT = 0xf3
send(0xf3, b'\x01'); time.sleep(0.3); recv()

sock.close()
