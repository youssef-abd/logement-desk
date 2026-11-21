import html as htmllib
import re
import time
import urllib.error
import urllib.request

from ..errors import Blocked
from ..listing import Listing

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
SLEEP = time.sleep
BASE = "https://www.immojeune.com"
SPLIT = '<div class="card col">'
TITLE = re.compile(r'class="title">\s*<a href="([^"]+)"[^>]*>\s*([^<]*?)\s*</a>')
PRICE = re.compile(r"<p>\s*([\d.,]+)\s*m\S*\s*-\s*([\d\s]+?)\s*(?:€|&euro;)\s*<sup>(\w+)</sup>")
GEO = re.compile(r"(?:&nbsp;|\xa0)\s*(\d{5})\s*([^<\n]+)")
BADGES = re.compile(r'class="badge badge-light">\s*([^<]+?)\s*<')
OWNER = re.compile(r'class="badge badge-cyan">\s*<img[^>]*>\s*([^<]+?)\s*<')
PHOTO = re.compile(r'data-background="(https://[^"]+)"')
ID = re.compile(r"_(\d+)\.html")
UNIT = re.compile(r'<option value="(\d+)"[^>]*>\s*([^<:]+?)\s*:\s*([\d.,]+)(?:\s*\S\s*([\d.,]+))?\s*m\S*\s*-\s*([\d\s]+?)\s*(?:€|&euro;)\s*</option>')
H1 = re.compile(r"<h1[^>]*>\s*([^<]+?)\s*</h1>")
ROOMS = {"studio": 1, "t1": 1, "t1 bis": 1, "t2": 2, "t3": 3, "t4": 4}


def _district(postal, city):
    city = city.strip()
    m = re.match(r"Lyon\s+0?(\d)\b", city, re.I)
    if m:
        return f"Lyon {m.group(1)}{'er' if m.group(1) == '1' else 'e'}"
    return city.title() or None


def _num(s):
    return float(s.replace(",", ".")) if s else None


def parse_list(page_html, max_photos):
    """Cards of a result page: (private ads as listings, {residence page url: its photos})."""
    ads, residences = [], {}
    for raw in page_html.split(SPLIT)[1:]:
        c = htmllib.unescape(raw)
        link = TITLE.search(c)
        if not link:
            continue
        href, title = link.group(1), re.sub(r"\s+", " ", link.group(2))
        if "/residence-etudiante/" in href:
            residences.setdefault(href, PHOTO.findall(c)[:max_photos])
            continue
        price, geo, ident = PRICE.search(c), GEO.search(c), ID.search(href)
        if not (price and ident):
            continue
        badges = [b.upper() for b in BADGES.findall(c)]
        owner = OWNER.search(c)
        kind = next((b.lower() for b in badges if b.lower() in ROOMS), None)
        ads.append(Listing(
            source="immojeune", source_id=ident.group(1), url=BASE + href, title=title,
            rent_cc=float(re.sub(r"\D", "", price.group(2))) or None, surface_m2=_num(price.group(1)),
            rooms=ROOMS.get(kind) or (int(m.group(1)) if (m := re.match(r"T(\d)", kind or "", re.I)) else None),
            district=_district(geo.group(1), geo.group(2)) if geo else None, postal_code=geo.group(1) if geo else None,
            poster="particulier" if owner and "PARTICULIER" in owner.group(1).upper() else "agence",
            tags=["colocation"] if "COLOCATION" in badges else [], photos=PHOTO.findall(c)[:max_photos],
            description="",
        ))
    return ads, residences


def next_page(page_html):
    m = re.search(r'<link rel="next" href="([^"]+)"', page_html)
    return BASE + m.group(1) if m else None


def parse_residence(page_html, url, max_photos, photos=()):
    """The units a residence page offers (its contact form lists them with their rent)."""
    t = htmllib.unescape(page_html)
    name = (H1.search(t) or [None, "Residence"])[1].strip()
    geo = re.search(r"(\d{5})\s+([A-Za-zÀ-ÿ' -]+?)(?:[,<\n]|$)", re.sub(r"<[^>]+>", "\n", t[t.find("<h1"):t.find("<h1") + 3000]))
    postal, city = (geo.group(1), geo.group(2)) if geo else (None, "")
    lyon = re.search(r"lyon-0?(\d)-69", url)
    district = f"Lyon {lyon.group(1)}{'er' if lyon.group(1) == '1' else 'e'}" if lyon else (city.strip().title() or None)
    postal = postal or (f"6900{lyon.group(1)}" if lyon else None)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S)))
    furnished = False if re.search(r"non[ -]meubl", text, re.I) else (True if re.search(r"meubl", text, re.I) else None)
    photos = list(photos)[:max_photos]
    out = []
    for uid, kind, s1, _s2, rent in UNIT.findall(t):
        k = kind.strip().lower()
        out.append(Listing(
            source="immojeune", source_id=f"u{uid}", url=url, title=f"{name} : {kind.strip()}",
            rent_cc=float(re.sub(r"\D", "", rent)) or None, surface_m2=_num(s1),
            rooms=ROOMS.get(k), district=district, postal_code=postal, furnished=furnished, poster="agence", poster_name=name[:60],
            photos=photos, tags=["residence"], description="",
        ))
    return out


def _get(url):
    req = urllib.request.Request(url if url.startswith("http") else BASE + url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 503):
            raise Blocked(f"HTTP {e.code}") from e
        raise


def fetch(profile):
    opts = profile["sources"]["immojeune"]
    deep = profile.get("deep", False)
    out, seen, residences = [], set(), {}
    pages = opts.get("deep_pages", 6) if deep else 1
    for n, url in enumerate(opts["urls"]):
        for p in range(pages):  # the deep sweep follows the page's own "next" link
            try:
                html = _get(url)
                ads, res = parse_list(html, profile["max_photos"])
            except Blocked:
                if n == 0 and p == 0 and not out:
                    raise
                break
            new = [l for l in ads if l.source_id not in seen]
            for l in new:
                seen.add(l.source_id)
                out.append(l)
            fresh = [h for h in res if h not in residences]
            for href in fresh:
                residences[href] = res[href]
            SLEEP(1)
            url = next_page(html)
            if not url or not (new or fresh):  # no next page, or it only repeats what is known
                break
    if deep:  # residence pages are one request each: read them on the hourly deep sweep only
        for href in list(residences)[: opts.get("max_residences", 25)]:
            try:
                units = parse_residence(_get(href), BASE + href, profile["max_photos"], residences[href])
            except Blocked:
                break
            for l in units:
                if l.source_id not in seen:
                    seen.add(l.source_id)
                    out.append(l)
            SLEEP(1)
    return out
