"""Draw the Logement app icons (a white house on the app's blue) into desk/public/icons/. Needs Pillow. Usage: python scripts/make_pwa_icons.py"""
import os
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desk", "public", "icons")
BG, FG = "#1d5fbf", "#ffffff"
ROOF = [(50, 14), (92, 52), (8, 52)]          # unit coordinates in a 100 x 100 box
BODY = [(22, 50), (78, 88)]
DOOR = [(43, 62), (57, 88)]


def icon(size, glyph_fraction):
    ss = 4  # draw 4x bigger, then shrink: smooth edges
    im = Image.new("RGB", (size * ss, size * ss), BG)
    d = ImageDraw.Draw(im)
    unit = size * ss * glyph_fraction / 100.0
    off = (size * ss - 100 * unit) / 2
    P = lambda x, y: (off + x * unit, off + y * unit)
    d.polygon([P(*p) for p in ROOF], fill=FG)
    d.rectangle([P(*BODY[0]), P(*BODY[1])], fill=FG)
    d.rectangle([P(*DOOR[0]), P(*DOOR[1])], fill=BG)
    return im.resize((size, size), Image.LANCZOS)


os.makedirs(OUT, exist_ok=True)
for name, size, frac in (("icon-192.png", 192, 0.62), ("icon-512.png", 512, 0.62), ("icon-maskable-512.png", 512, 0.46), ("apple-touch-icon.png", 180, 0.62)):
    icon(size, frac).save(os.path.join(OUT, name), optimize=True)
    print("wrote", name)
