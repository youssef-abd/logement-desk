import json
import re

from ..errors import Blocked
from ..listing import Listing

LD = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def _walk(o):
    if isinstance(o, dict):
        if o.get("@type") == "RealEstateListing":
            yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def parse_html(html, max_photos):
    out, seen = [], set()
    for m in LD.finditer(html):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for o in _walk(data):
            url = o.get("url") or ""
            sid = url.rstrip("/").rsplit("/", 1)[-1]
            if not sid or sid in seen:
                continue
            seen.add(sid)
            about, offers = o.get("about") or {}, o.get("offers") or {}
            name, avail, img = o.get("name") or "", offers.get("availabilityStarts"), o.get("image")
            out.append(Listing(
                source="lacartedescolocs", source_id=sid, url=url, title=name, kind="coloc",
                rent_cc=offers.get("price"), surface_m2=(about.get("floorSize") or {}).get("value"),
                district=(about.get("address") or {}).get("addressLocality"),
                description=f"{name}. Disponible dès {avail}" if avail else name,
                photos=[img][:max_photos] if img else [],
            ))
    return out


def fetch(profile):
    from curl_cffi import requests

    url = profile["sources"]["lacartedescolocs"]["url"]
    r = requests.get(url, impersonate="chrome", timeout=30, headers={"Accept-Language": "fr-FR,fr;q=0.9"})
    if r.status_code in (403, 429, 503):
        raise Blocked(f"HTTP {r.status_code}")
    r.raise_for_status()
    return parse_html(r.text, profile["max_photos"])
