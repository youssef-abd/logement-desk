from ..errors import Blocked
from ..listing import Listing


def _attr(ad, key):
    a = ad.attributes.get(key)
    return a.value if a is not None else None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_ad(ad, max_photos):
    price = _num(ad.price)
    charges = _num(_attr(ad, "monthly_charges"))
    rent = price
    if price is not None and charges and _attr(ad, "charges_included") == "2":
        rent = price + charges
    rooms = _num(_attr(ad, "rooms"))
    owner = (ad.raw.get("owner") or {}).get("type")
    loc = ad.location
    return Listing(
        source="leboncoin", source_id=str(ad.id), url=ad.url, title=ad.subject or "",
        rent_cc=rent, charges=charges, surface_m2=_num(_attr(ad, "square")),
        rooms=int(rooms) if rooms is not None else None,
        district=f"{loc.city} {loc.zipcode}".strip() if loc else None,
        postal_code=loc.zipcode if loc else None,
        furnished={"1": True, "2": False}.get(_attr(ad, "furnished")),
        poster={"private": "particulier", "pro": "agence"}.get(owner),
        published_at=str(ad.first_publication_date) if ad.first_publication_date else None,
        description=ad.body or "", photos=list(ad.images or [])[:max_photos],
    )


def fetch(profile):
    import lbc
    from lbc.exceptions import DatadomeError, RequestError

    opts = profile["sources"]["leboncoin"]
    client = lbc.Client()
    loc = lbc.City(lat=opts["lat"], lng=opts["lng"], radius=opts["radius_m"], city=opts["city"])
    extra = {"real_estate_type": ["2"]}  # apartments only: parkings and caves share the category
    if profile["furnished"] == "required":
        extra["furnished"] = ["1"]
    try:
        res = client.search(
            locations=[loc], page=1, limit=opts.get("limit", 35), sort=lbc.Sort.NEWEST,
            category=lbc.Category.IMMOBILIER_LOCATIONS,
            price=[0, int(profile["max_rent_cc"] + profile["near_miss_margin"])],
            square=[int(profile["min_surface_m2"]), int(opts.get("max_square", 60))], **extra,
        )
    except DatadomeError as e:
        raise Blocked("datadome") from e
    except RequestError as e:
        if any(code in str(e) for code in ("403", "429")):
            raise Blocked(str(e)[:60]) from e
        raise
    return [parse_ad(ad, profile["max_photos"]) for ad in res.ads]
