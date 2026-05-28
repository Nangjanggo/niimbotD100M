import socket, time

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
    except socket.timeout:
        print("recv: timeout")

# END_PAGE_PRINT = 0xe3
send(0xe3, b'\x01')
time.sleep(0.5)
recv()

sock.close()
