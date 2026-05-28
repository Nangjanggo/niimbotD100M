import socket
import time
import sys
sys.path.insert(0, './niimprint')
import niimprint.printerclient as pc
import niimprint.niimbotpacket as nb

addr = "06:A7:13:68:00:11"
sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
sock.connect((addr, 1))
sock.settimeout(3)

def send_raw(type_, data):
    checksum = type_ ^ len(data)
    for i in data:
        checksum ^= i
    pkt = bytes((0x55, 0x55, type_, len(data), *data, checksum, 0xaa, 0xaa))
    print(f"send type=0x{type_:02x}: {pkt.hex()}")
    sock.send(pkt)

def recv_raw():
    try:
        data = sock.recv(1024)
        print(f"recv raw: {data.hex()}")
        return data
    except socket.timeout:
        print("recv: timeout")
        return b''

# START_PRINT = 0x01
send_raw(0x01, b'\x01')
time.sleep(0.3)
recv_raw()

# END_PAGE_PRINT = 0xf3
send_raw(0xf3, b'\x01')
time.sleep(0.3)
recv_raw()

sock.close()
