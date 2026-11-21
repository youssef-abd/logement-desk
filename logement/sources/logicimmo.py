"""Logic-Immo: each search page embeds its first 25 listings (newest first) as JSON in window["__UFRN_FETCHER__"]."""
import json
import re
import time

from ..errors import Blocked, DriftError
from ..listing import Listing

SLEEP = time.sleep
BASE = "https://www.logic-immo.com/recherche-immo/location/appartement/"
FETCHER = re.compile(r'__UFRN_FETCHER__"\]\s*=\s*JSON\.parse\((".*?")\)\s*;?\s*</script>', re.S)
DISTRICT = re.compile(r"Lyon\s+(\d+)", re.I)


def _district(city):
    m = DISTRICT.match(city or "")
    return f"Lyon {m.group(1)}{'er' if m.group(1) == '1' else 'e'}" if m else (city or None)


def parse_html(page_html, max_photos):
    m = FETCHER.search(page_html)
    if not m:
        raise DriftError("no embedded listing data")
    try:
        serp = json.loads(json.loads(m.group(1)))["data"]["classified-serp-data"]
        cards = serp["classifiedsData"]
        order = serp["classifieds"]
    except (ValueError, KeyError, TypeError) as e:
        raise DriftError("listing data changed shape") from e
    out = []
    for ident in order:  # the main results only: the "suggested" ones come from other searches
        c = cards.get(ident)
        raw = (c or {}).get("rawData") or {}
        if not c or not raw.get("price") or not c.get("url"):
            continue
        loc = (c.get("location") or {}).get("address") or {}
        head = (c.get("mainDescription") or {}).get("headline") or ""
        desc = re.sub(r"\s+", " ", (c.get("mainDescription") or {}).get("description") or "").strip()
        text = f"{head} {desc}"
        prov = c.get("provider") or {}
        private = bool(prov.get("isPrivateOwner"))
        name = ((prov.get("intermediaryCard") or {}).get("title") or "").strip()
        out.append(Listing(
            source="logicimmo", source_id=str(ident), url=c["url"], title=head, rent_cc=float(raw["price"]),
            surface_m2=float((raw.get("surface") or {}).get("main") or 0) or None, rooms=int(raw["nbroom"]) if raw.get("nbroom") else None,
            district=_district(loc.get("city") or raw.get("providercity")), postal_code=str(loc.get("zipCode") or raw.get("providerzipcode") or "") or None,
            furnished=False if re.search(r"non[ -]meubl", text, re.I) else (True if re.search(r"meubl", text, re.I) else None),
            poster="particulier" if private else "agence", poster_name=None if private else (name[:60] or None),
            published_at=(c.get("metadata") or {}).get("creationDate"), description=desc[:600],
            photos=[i["url"] for i in ((c.get("gallery") or {}).get("images") or []) if i.get("url")][:max_photos],
        ))
    return out


def _get(url):
    from curl_cffi import requests

    r = requests.get(url, impersonate="chrome", timeout=30, headers={"Accept-Language": "fr-FR,fr;q=0.9"})
    if r.status_code in (403, 429, 503):
        raise Blocked(f"HTTP {r.status_code}")
    r.raise_for_status()
    return r.text


def fetch(profile):
    opts = profile["sources"]["logicimmo"]
    urls = [u if u.startswith("http") else BASE + u for u in opts["paths"]]
    if not profile.get("deep", False):
        urls = urls[: opts.get("light_count", 2)]  # the light poll reads the widest searches only: one page is ~1 MB
    out, seen = [], set()
    for n, url in enumerate(urls):
        try:
            items = parse_html(_get(url), profile["max_photos"])
        except Blocked:
            if n == 0 and not out:
                raise
            break
        out += [l for l in items if l.source_id not in seen and not seen.add(l.source_id)]
        if n < len(urls) - 1:
            SLEEP(1.5)
    return out
