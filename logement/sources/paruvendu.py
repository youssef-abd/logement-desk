import html as htmllib
import re
import time
import urllib.error
import urllib.request

from ..errors import Blocked
from ..listing import Listing
from ..paging import collect

SLEEP = time.sleep
PAGE_SIZE = 30
AREA = re.compile(r"\bLyon\s+([1-9])(?:er|e|ème)?\b", re.I)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
SPLIT = re.compile(r'(?=<div[^>]*class="blocAnnonce)')
IS_CARD = re.compile(r'<div[^>]*class="blocAnnonce')
PRICE = re.compile(r"<!--\s*Prix\s*-->\s*<div>\s*([\d\s]+?)\s*€\s*(?:<span[^>]*>\s*(CC|HC))?", re.I)
LINK = re.compile(r'<a href="(/immobilier/location/[^"]+)"\s+title="([^"]*)"')
POSTER = re.compile(r'<span class="pseudoinfo">\s*([^<]+?)\s*</span>')
DATE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
PHOTO = re.compile(r"https://img\.paruvendu\.fr/media_ext/[^\"'\s)]+")


def _card(raw):
    c = htmllib.unescape(raw)
    did = re.search(r'data-id="(\d+)"', c)
    link = LINK.search(c)
    if not did or not link:
        return None
    price = PRICE.search(c)
    title = link.group(2).strip()
    rooms = re.search(r"(\d+)\s*pièce", title)
    surface = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", title)
    m = POSTER.search(c)
    if m:
        poster = "particulier" if m.group(1).lower() == "particulier" else "agence"
    else:
        poster = "agence" if re.search(r'alt="pro : ', c, re.I) else None
    date = DATE.search(c)
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", c, flags=re.S))
    text = re.sub(r"\s+", " ", text).strip()
    if re.search(r"non[ -]meubl|\bvide\b", text, re.I):
        furnished = False
    else:
        furnished = True if re.search(r"meubl", text, re.I) else None
    photos = list(dict.fromkeys(PHOTO.findall(c)))
    return did.group(1), link.group(1), title, price, rooms, surface, poster, date, text, furnished, photos


def parse_html(html, max_photos):
    out = []
    for raw in SPLIT.split(html):
        if not IS_CARD.match(raw):
            continue
        parsed = _card(raw)
        if parsed is None:
            continue
        did, href, title, price, rooms, surface, poster, date, text, furnished, photos = parsed
        area = AREA.search(text)
        n = area.group(1) if area else None
        district = (f"Lyon {n}er" if n == "1" else f"Lyon {n}e") if n else None
        tags = []
        rent = None
        if price:
            rent = int(re.sub(r"\D", "", price.group(1)) or 0) or None
            if (price.group(2) or "").upper() == "HC":
                tags.append("hc?")
        l = Listing(
            source="paruvendu", source_id=did, url="https://www.paruvendu.fr" + href, title=title,
            rent_cc=rent, surface_m2=float(surface.group(1).replace(",", ".")) if surface else None,
            rooms=int(rooms.group(1)) if rooms else None, furnished=furnished,
            district=district, postal_code=f"6900{n}" if n else None,
            poster=poster,
            published_at=f"{date.group(3)}-{date.group(2)}-{date.group(1)}" if date else None,
            description=text, photos=photos[:max_photos],
        )
        l.tags = tags
        out.append(l)
    return out


def page_url(url, page):
    if page <= 1:
        return url
    return f"{url}{'&' if '?' in url else '?'}p={page}"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 503):
            raise Blocked(f"HTTP {e.code}") from e
        raise


def fetch(profile):
    opts = profile["sources"]["paruvendu"]
    urls = opts.get("urls") or [opts["url"]]
    pages = opts.get("deep_pages", 8) if profile.get("deep", False) else 1
    out, seen = [], set()
    for url in urls:
        got = collect(lambda n: parse_html(_get(page_url(url, n + 1)), profile["max_photos"]),
                      pages, PAGE_SIZE, lambda l: l.source_id, sleep=lambda s: SLEEP(s), pause=1.5)
        m = re.search(r"-(\d{5})/?$", url.split("?")[0])  # city pages end with the postal code
        for l in got:
            if m and l.postal_code is None:
                l.postal_code = m.group(1)
            if l.source_id not in seen:
                seen.add(l.source_id)
                out.append(l)
    return out
