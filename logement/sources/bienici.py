import json
import urllib.error
import urllib.parse
import urllib.request

from ..errors import Blocked
from ..listing import Listing
from ..paging import collect

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
ENDPOINT = "https://www.bienici.com/realEstateAds.json"


def build_filters(profile, size=None, offset=0):
    opts = profile["sources"]["bienici"]
    f = {
        "size": size or opts.get("size", 24), "from": offset, "filterType": "rent", "propertyType": ["flat"],
        "maxPrice": int(profile["max_rent_cc"] + profile["near_miss_margin"]),
        "sortBy": "publicationDate", "sortOrder": "desc",
        "zoneIdsByTypes": {"zoneIds": opts["zone_ids"]},
    }
    if profile["furnished"] == "required":
        f["isFurnished"] = True  # the key "furnished" is silently ignored by the site
    return f


def _title(rooms, surface, city):
    parts = []
    if rooms is not None:
        parts.append(f"{rooms} pièce(s)")
    if surface is not None:
        parts.append(f"{surface:g} m²")
    if city:
        parts.append(city)
    return " ".join(parts)


def parse(data, max_photos):
    out = []
    for a in data.get("realEstateAds") or []:
        sid = str(a.get("id") or "")
        pro = a.get("adCreatedByPro")
        out.append(Listing(
            source="bienici", source_id=sid,
            url=f"https://www.bienici.com/annonce/{sid}" if sid else "",
            title=a.get("title") or _title(a.get("roomsQuantity"), a.get("surfaceArea"), a.get("city")),
            rent_cc=a.get("price"),  # already includes charges
            charges=a.get("charges"), surface_m2=a.get("surfaceArea"), rooms=a.get("roomsQuantity"),
            district=a.get("city"), postal_code=a.get("postalCode"), furnished=a.get("isFurnished"),
            poster=None if pro is None else ("agence" if pro else "particulier"),
            poster_name=(str(a.get("accountDisplayName") or "").strip()[:60] or None) if pro else None,
            published_at=None if str(a.get("publicationDate") or "").startswith("1970") else a.get("publicationDate"), description=a.get("description") or "",
            photos=[p["url"] for p in (a.get("photos") or []) if isinstance(p, dict) and p.get("url")][:max_photos],
        ))
    return out


def fetch_page(profile, offset, size):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"filters": json.dumps(build_filters(profile, size, offset))})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 503):
            raise Blocked(f"HTTP {e.code}") from e
        raise
    return parse(data, profile["max_photos"])


def fetch(profile):
    opts = profile["sources"]["bienici"]
    if not profile.get("deep", False):
        size = opts.get("size", 24)
        return fetch_page(profile, 0, size)
    size = 200
    return collect(lambda n: fetch_page(profile, n * size, size), opts.get("deep_pages", 6), size,
                   lambda l: l.source_id)
