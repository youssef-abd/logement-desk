import html as htmllib
import re
import time

from .. import relay
from ..errors import Blocked
from ..listing import Listing

SLEEP = time.sleep
SPLIT = '<div class="col-1-3">'
LINK = re.compile(r'href="(/annonces/[^"]*-r(\d+))"')
PRICE = re.compile(r'class="item-price[^"]*"[^>]*>\s*([\d.\s ]+?)\s*(?:&nbsp;|\s)*(?:€|&euro;)', re.I)
PLACE = re.compile(r'<span class="h1">\s*([^<]+?)\s*</span>')
TAG = re.compile(r"<li>\s*([^<]+?)\s*</li>")
DESC = re.compile(r'class="item-description"[^>]*>\s*(.*?)\s*</p>', re.S)
IMG = re.compile(r'<img[^>]+src="(https://cdn\.pap\.fr/[^"]+)"')


def page_url(url, n):
    return url if n == 1 else f"{url}-{n}"


def parse_html(html, max_photos, furnished_search=None):
    out, seen = [], set()
    for raw in html.split(SPLIT)[1:]:
        chunk = htmllib.unescape(raw)
        link = LINK.search(chunk)
        if not link or link.group(2) in seen:
            continue
        seen.add(link.group(2))
        price, place = PRICE.search(chunk), (PLACE.search(chunk) or [None, ""])[1].strip()
        tags = [t.replace(" ", " ").strip() for t in TAG.findall(chunk)]
        rooms = surface = None
        for t in tags:
            if m := re.match(r"(\d+)\s*pi[èe]ces?", t, re.I):
                rooms = int(m.group(1))
            elif m := re.match(r"([\d.,]+)\s*m", t):
                surface = float(m.group(1).replace(",", "."))
        postal = (re.search(r"\((\d{5})\)", place) or [None, None])[1]
        city = place.split("(")[0].strip()
        lyon = re.match(r"Lyon\s+(\d)", city, re.I)
        postal = postal or (f"6900{lyon.group(1)}" if lyon else None)
        district = f"Lyon {lyon.group(1)}{'er' if lyon.group(1) == '1' else 'e'}" if lyon else (city.title() or None)
        desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (DESC.search(chunk) or [None, ""])[1])).strip()
        text = f"{place} {' '.join(tags)} {desc}"
        furnished = False if re.search(r"non[ -]meubl", text, re.I) else (True if re.search(r"meubl", text, re.I) else furnished_search)
        out.append(Listing(
            source="pap", source_id=link.group(2), url="https://www.pap.fr" + link.group(1), title=f"{place} {' '.join(tags)}".strip(),
            rent_cc=float(re.sub(r"\D", "", price.group(1))) if price and re.sub(r"\D", "", price.group(1)) else None,
            surface_m2=surface, rooms=rooms, district=district, postal_code=postal, furnished=furnished, poster="particulier",
            description=desc, photos=list(dict.fromkeys(IMG.findall(chunk)))[:max_photos],
        ))
    return out


def fetch(profile):
    opts = profile["sources"]["pap"]
    pages = opts.get("deep_pages", 4) if profile.get("deep", False) else 1
    out, seen = [], set()
    for url in opts["urls"]:
        for n in range(1, pages + 1):
            try:
                items = parse_html(relay.get(page_url(url, n)), profile["max_photos"], True if "meuble" in url else None)
            except Blocked:
                if n == 1 and not out:
                    raise
                break
            new = [l for l in items if l.source_id not in seen]
            if not new:
                break
            seen.update(l.source_id for l in new)
            out += new
            if n < pages:
                SLEEP(1.5)
    return out
