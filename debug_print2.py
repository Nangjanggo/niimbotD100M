import socket, time, struct, sys, select
sys.path.insert(0, './niimprint/niimprint')
import printencoder
from PIL import Image
import glob

addr = "06:A7:13:68:00:11"
sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
sock.connect((addr, 1))
print("connected")

def send_pkt(type_, data):
    checksum = type_ ^ len(data)
    for i in data: checksum ^= i
    return bytes((0x55, 0x55, type_, len(data), *data, checksum, 0xaa, 0xaa))

def transceive(type_, data):
    sock.send(send_pkt(type_, data))
    time.sleep(0.3)
    r, _, _ = select.select([sock], [], [], 0)
    if r:
        d = sock.recv(1024)
        print(f"  0x{type_:02x} -> {d.hex()}")
    else:
        print(f"  0x{type_:02x} -> no response")

img_path = sorted(glob.glob('./images/*.png'))[-1]
img = Image.open(img_path)
if img.width / img.height > 1:
    img = img.transpose(Image.ROTATE_270)
print(f"image: {img.width}x{img.height}")

transceive(0x23, b'\x01')
transceive(0x21, b'\x02')
transceive(0x01, b'\x01')
transceive(0x20, b'\x01')
transceive(0x03, b'\x01')
transceive(0x13, struct.pack('>HH', img.height, img.width))
transceive(0x15, struct.pack('>H', 1))

pkts = list(printencoder.naive_encoder(img))
print(f"sending {len(pkts)} image lines...")
for pkt in pkts:
    sock.send(pkt.to_bytes())
print("image sent, waiting...")
time.sleep(2)

transceive(0xe3, b'\x01')
time.sleep(3)
transceive(0xa3, b'\x01')
time.sleep(2)
transceive(0xf3, b'\x01')

sock.close()
print("done")
