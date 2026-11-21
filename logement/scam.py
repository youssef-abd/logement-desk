"""Scam signals for the desk. Hints only: nothing is hidden, the card shows the reasons. Needs no extra requests."""
import re
import unicodedata
from collections import defaultdict

# (points, reason, pattern, agencies_too). Patterns are matched against title + description, case-insensitive.
TEXT = [
    (3, "asks for money before a visit", r"(verser|virement|paiement|payer|envoy\w+)[^.]{0,40}(avant|sans)[^.]{0,20}(visite|visiter)|(caution|d[ée]p[oô]t)[^.]{0,40}avant (la )?(visite|remise)", True),
    (3, "keys sent by post", r"cl[ée]s?[^.]{0,30}(par la poste|par courrier|colis|dhl|ups)", True),
    (3, "money-transfer wording", r"western union|moneygram|mandat (cash|international)|ria money|paysafecard|transcash", True),
    (2, "owner abroad", r"(propri[ée]taire|je)[^.]{0,30}(vis|r[ée]side|habite|suis)[^.]{0,20}(à l.[ée]tranger|en (espagne|angleterre|allemagne|suisse|italie|belgique|afrique|canada|usa))|\bexpatri[ée]|mission (à|en) l.[ée]tranger", True),
    (2, "contact outside the site", r"whatsapp|telegram|contactez[- ]moi (uniquement )?(par )?(mail|e-?mail|courriel)", True),
    (2, "contact by e-mail only", r"[\w.+-]+@[\w-]+\.\w{2,}", False),
    (2, "payment through a booking site", r"airbnb|booking\.com|paiement s[ée]curis[ée]", True),
]
_COMPILED = [(p, why, re.compile(rx, re.I), agencies) for p, why, rx, agencies in TEXT]
MIN_TEXT = 80  # shorter descriptions are too generic to compare


def _norm(text):
    t = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()[:160]


def _photo(url):
    return url.split("?")[0] if isinstance(url, str) else ""


def signals(items):
    """items: iterable of (key, listing dict). Returns {key: [(points, reason), ...]} for listings with at least one signal."""
    items = list(items)
    out = defaultdict(list)
    by_text, by_photo = defaultdict(list), defaultdict(list)
    for key, l in items:
        text = f"{l.get('title') or ''}\n{l.get('description') or ''}"
        agency = l.get("poster") == "agence"
        for points, why, rx, agencies in _COMPILED:
            if (agencies or not agency) and rx.search(text):
                out[key].append((points, why))
        n = _norm(l.get("description"))
        if len(n) >= MIN_TEXT:
            by_text[n].append((key, l))
        for u in {_photo(u) for u in (l.get("photos") or [])}:
            if u:
                by_photo[u].append((key, l))
    for group in by_text.values():
        if len(group) >= 2 and any(l.get("poster") != "agence" for _, l in group):
            for key, _ in group:
                out[key].append((2, f"same text on {len(group) - 1} other listing(s)"))
    for group in by_photo.values():
        codes = {l.get("postal_code") for _, l in group if l.get("postal_code")}
        if len(group) >= 2 and len(codes) >= 2 and any(l.get("poster") != "agence" for _, l in group):
            for key, _ in group:
                if not any(w.startswith("same photo") for _, w in out[key]):
                    out[key].append((2, "same photo used in another area"))
    return out


def risk(points_reasons, too_cheap=False):
    """(level, reasons): level is None, 'check' (score >= 2) or 'high' (score >= 4)."""
    pr = list(points_reasons)
    if too_cheap:
        pr.append((2, "price under half the area median"))
    score = sum(p for p, _ in pr)
    level = "high" if score >= 4 else "check" if score >= 2 else None
    return level, [w for _, w in pr][:5]
