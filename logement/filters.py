import re

from .coloc import is_coloc


def _tag(listing, tag):
    if tag not in listing.tags:
        listing.tags.append(tag)


def infer_kind(l):
    if l.kind:
        return l.kind
    title = (l.title or "").lower()
    if is_coloc(l):
        return "coloc"
    if l.rooms == 1:
        return "studio" if "studio" in title else "t1"
    if "studio" in title:
        return "studio"
    if "chambre" in title:
        return "room"
    if l.rooms == 2:
        return "t2"
    if l.rooms is not None and l.rooms >= 3:
        return "t3+"
    return None


def _check(l, p):
    """True to keep. Adds tags for unknown values instead of rejecting on them."""
    codes = p["areas"].get("allowed_postal_codes") or []
    if codes:
        if l.postal_code is None:
            _tag(l, "area?")
        elif l.postal_code not in codes:
            return False

    if l.surface_m2 is not None and l.surface_m2 < p["min_surface_m2"]:
        return False

    if (
        l.rooms is None
        and not re.search(r"\b(studio|t1|f1)\b", l.title or "", re.I)
        and any(re.search(pat, l.title or "", re.I) for pat in p["reject_title_patterns"])
    ):
        return False

    kind = infer_kind(l)
    if kind is None:
        _tag(l, "kind?")
    elif kind not in p["kinds"]["allowed"]:
        return False
    elif kind in ("studio", "t1") and l.surface_m2 is not None and l.surface_m2 > p["kinds"]["max_surface_for_t1"]:
        return False
    l.kind = kind

    if l.rent_cc is None:
        _tag(l, "rent?")
    else:
        if l.rent_cc > p["max_rent_cc"] + p["near_miss_margin"]:
            return False

    if p["furnished"] == "required":
        if l.furnished is False:
            return False
        if l.furnished is None:
            _tag(l, "furnished?")
    return True


def hard_filter(l, p):
    """True to keep. With a profile "collect" section the net is wider than the owner's criteria (the desk narrows it live);
    l.match then says whether the listing also meets the owner's own criteria, which is what phone alerts use."""
    wide = {**p, **(p.get("collect") or {})}
    if not _check(l, wide):
        return False
    if l.rent_cc is not None and p["max_rent_cc"] < l.rent_cc <= p["max_rent_cc"] + p["near_miss_margin"]:
        _tag(l, "near-miss")
    l.match = _check(l, p) if p.get("collect") else True
    return True
