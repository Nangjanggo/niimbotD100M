import socket, time, select

addr = "06:A7:13:68:00:11"
sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
# NO setblocking call - default is blocking
sock.connect((addr, 1))
print("connected")

def send(type_, data):
    checksum = type_ ^ len(data)
    for i in data: checksum ^= i
    pkt = bytes((0x55, 0x55, type_, len(data), *data, checksum, 0xaa, 0xaa))
    sock.send(pkt)

def recv(timeout=2):
    r, _, _ = select.select([sock], [], [], timeout)
    if r:
        d = sock.recv(1024)
        print(f"recv: {d.hex()}")
    else:
        print("recv: timeout")

send(0x23, b'\x01')
recv()
send(0x21, b'\x02')
recv()

# 작은 이미지 데이터 10줄만 테스트
import struct
for i in range(10):
    line_data = bytes(12)
    header = struct.pack('>H3BB', i, 0, 0, 0, 1)
    pkt_data = header + line_data
    checksum = 0x85 ^ len(pkt_data)
    for b in pkt_data: checksum ^= b
    pkt = bytes((0x55, 0x55, 0x85, len(pkt_data), *pkt_data, checksum, 0xaa, 0xaa))
    sock.send(pkt)
    print(f"sent line {i}")

sock.close()
print("done")
