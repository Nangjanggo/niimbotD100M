import socket, time, struct, sys, select
sys.path.insert(0, './niimprint/niimprint')
sys.path.insert(0, './niimprint')
import printencoder
from PIL import Image
import glob

addr = "06:A7:13:68:00:11"
sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
sock.setblocking(True)
sock.connect((addr, 1))

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

def transceive(type_, data):
    send(type_, data)
    recv()

img_path = sorted(glob.glob('./images/*.png'))[-1]
print(f"image: {img_path}")
img = Image.open(img_path)
if img.width / img.height > 1:
    img = img.transpose(Image.ROTATE_270)
print(f"size: {img.width}x{img.height}")

transceive(0x23, b'\x01')  # SET_LABEL_TYPE
transceive(0x21, b'\x02')  # SET_LABEL_DENSITY
transceive(0x01, b'\x01')  # START_PRINT
transceive(0x20, b'\x01')  # ALLOW_PRINT_CLEAR
transceive(0x03, b'\x01')  # START_PAGE_PRINT
transceive(0x13, struct.pack('>HH', img.height, img.width))  # SET_DIMENSION
transceive(0x15, struct.pack('>H', 1))  # SET_QUANTITY

pkts = list(printencoder.naive_encoder(img))
print(f"sending {len(pkts)} image packets...")
for pkt in pkts:
    sock.send(pkt.to_bytes())
print("image sent")
time.sleep(1)

transceive(0xe3, b'\x01')  # END_PAGE_PRINT
time.sleep(2)
transceive(0xa3, b'\x01')  # GET_PRINT_STATUS
time.sleep(2)
transceive(0xf3, b'\x01')  # END_PRINT

sock.close()
print("done")
