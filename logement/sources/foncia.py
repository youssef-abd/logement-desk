import html as htmllib
import re
import time
import urllib.error
import urllib.request

from ..errors import Blocked
from ..listing import Listing

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
SLEEP = time.sleep
LINK = re.compile(r"/location/[a-z0-9-]+/(appartement[a-z-]*)/(\d{6,})\.htm")


def _cls(name):
    return r'class="[^"]*\b' + name + r'\b[^"]*"[^>]*>'


TITLE = re.compile(_cls("foncia-card-title-small-title") + r"\s*([^<]+?)\s*<")
PRICE = re.compile(_cls("foncia-card-price") + r"\s*<span[^>]*>\s*([\d\s ]+?)\s*€\s*</span>\s*(?:<sup[^>]*>\s*/\s*mois\s*(CC|HC))?", re.I)
SURFACE = re.compile(_cls("foncia-card-surface") + r"\s*([\d.,]+)\s*m", re.I)
PLACE = re.compile(_cls("foncia-card-place") + r"\s*([^<]+?)\s*<")
DESC = re.compile(_cls("foncia-card-description") + r"\s*([^<]*)")
IMG = re.compile(r'<img[^>]+src="(https://[^"]+)"')
ROOMS = re.compile(r"(\d+)\s*pi[èe]ces?", re.I)


def page_url(url, n):
    return url if n == 1 else url + ("&" if "?" in url else "?") + f"page={n}"


def parse_html(html, max_photos):
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    out, seen = [], set()
    for chunk in html.split("<app-annonce-card")[1:]:
        chunk = htmllib.unescape(chunk)  # prices of 1,000 and more carry a non-breaking space entity
        link = LINK.search(chunk)
        if not link or link.group(2) in seen:
            continue
        seen.add(link.group(2))
        title = htmllib.unescape((TITLE.search(chunk) or [None, ""])[1])
        price, place = PRICE.search(chunk), htmllib.unescape((PLACE.search(chunk) or [None, ""])[1])
        surface, desc, img = SURFACE.search(chunk), DESC.search(chunk), IMG.search(chunk)
        postal = (re.search(r"\((\d{5})\)", place) or [None, None])[1]
        city = place.split("(")[0].strip()
        district = (f"Lyon {int(postal[4])}{'er' if postal[4] == '1' else 'e'}" if postal and postal.startswith("6900") else city) or None
        rm = ROOMS.search(title) or ROOMS.search(chunk)
        rooms = 1 if re.search(r"\bstudio\b", title, re.I) else (int(rm.group(1)) if rm else None)
        rent = int(re.sub(r"\D", "", price.group(1)) or 0) or None if price else None
        listing = Listing(
            source="foncia", source_id=link.group(2), url="https://fr.foncia.com" + link.group(0), title=title,
            rent_cc=rent, surface_m2=float(surface.group(1).replace(",", ".")) if surface else None, rooms=rooms,
            district=district, postal_code=postal, furnished="meuble" in link.group(1), poster="agence", poster_name="Foncia",
            description=htmllib.unescape(desc.group(1)).strip() if desc else "", photos=[img.group(1)][:max_photos] if img else [],
        )
        if price and (price.group(2) or "").upper() == "HC":
            listing.tags = ["hc?"]
        out.append(listing)
    return out


def _get(url, impersonate=False):
    if impersonate:  # a real-browser TLS fingerprint (curl_cffi); some sites refuse plain Python requests
        from curl_cffi import requests

        r = requests.get(url, impersonate="chrome", timeout=30, headers={"Accept-Language": "fr-FR,fr;q=0.9"})
        if r.status_code in (403, 429, 503):
            raise Blocked(f"HTTP {r.status_code}")
        r.raise_for_status()
        return r.text
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 503):
            raise Blocked(f"HTTP {e.code}") from e
        raise


def fetch(profile):
    opts = profile["sources"]["foncia"]
    pages = opts.get("deep_pages", 6) if profile.get("deep", False) else 1
    out, seen = [], set()
    for url in opts["urls"]:
        for n in range(1, pages + 1):
            try:
                items = parse_html(_get(page_url(url, n), opts.get("impersonate", False)), profile["max_photos"])
            except Blocked:
                if n == 1 and not out:
                    raise
                break  # keep what was collected
            new = [l for l in items if l.source_id not in seen]
            if not new:  # past the last page the site repeats or empties the list
                break
            seen.update(l.source_id for l in new)
            out += new
            if n < pages:
                SLEEP(1.5)
    return out
