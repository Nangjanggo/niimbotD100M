import PIL.Image as Image
import PIL.ImageOps as ImageOps
import struct
import niimbotpacket
import math

def naive_encoder(img):
    img = img.convert("L").convert("1")
    for y in range(img.height):
        line_data = [img.getpixel((x, y)) for x in range(img.width)]
        # PIL "1" mode: 0=black, 255=white. Printer wants 1=black, 0=white.
        line_data = "".join("1" if pix == 0 else "0" for pix in line_data)
        line_data = int(line_data, 2).to_bytes(math.ceil(img.width / 8), "big")
        header = struct.pack('>H3BB', y, 0, 0, 0, 1)
        pkt = niimbotpacket.NiimbotPacket(0x85, header + line_data)
        yield pkt
