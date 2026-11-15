"""Draw the Logement app icons (same three-bar mark as the page header) into desk/public/icons/. Needs Pillow. Usage: python scripts/make_pwa_icons.py"""
import os
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desk", "public", "icons")
BG, FG, ACCENT = "#0f1114", "#ececec", "#6aa6f5"
BARS = [(2, 4, 16, 2.4, FG), (2, 9, 11, 2.4, FG), (2, 14, 6, 2.4, ACCENT)]  # x, y, width, height in the 20x20 header mark


def icon(size, glyph_fraction):
    ss = 4  # draw 4x bigger, then shrink: smooth edges
    im = Image.new("RGB", (size * ss, size * ss), BG)
    d = ImageDraw.Draw(im)
    unit = size * ss * glyph_fraction / 16.0           # the mark is 16 units wide (x 2..18) and 12.4 tall (y 4..16.4)
    ox = (size * ss - 16 * unit) / 2 - 2 * unit
    oy = (size * ss - 12.4 * unit) / 2 - 4 * unit
    for x, y, w, h, col in BARS:
        d.rounded_rectangle([ox + x * unit, oy + y * unit, ox + (x + w) * unit, oy + (y + h) * unit], radius=0.5 * unit, fill=col)
    return im.resize((size, size), Image.LANCZOS)


os.makedirs(OUT, exist_ok=True)
for name, size, frac in (("icon-192.png", 192, 0.56), ("icon-512.png", 512, 0.56), ("icon-maskable-512.png", 512, 0.42), ("apple-touch-icon.png", 180, 0.56)):
    icon(size, frac).save(os.path.join(OUT, name), optimize=True)
    print("wrote", name)
