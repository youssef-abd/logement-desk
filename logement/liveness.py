"""Is a listing still online? A listing only turned "closed" after 12 hours of missing from the results, and a light poll reads page 1 only,
so a taken-down ad could stay clickable for a long time. The hourly deep run therefore opens a few listing pages itself, oldest check first.

What counts as gone is only what was seen on the real sites (2026-11-22):
- Bien'ici: its single-ad API says status.onTheMarket is false for a taken-down ad.
- ImmoJeune: a removed ad redirects to a search page; a residence unit is gone when its page no longer offers that unit.
- Any site: HTTP 404 or 410, or a redirect away from the listing to another path (a redirect to a login page proves nothing: unknown).
- La Carte des Colocs: HTTP 410 with "Cette annonce a été désactivée le ..." (the owner received enough applications).
Sites with no known signal (Leboncoin, ParuVendu when the page still loads) stay "live" or "unknown"; they are never guessed gone."""
import json
import re
import time
import urllib.error
from urllib.parse import urlparse

from . import relay
from .errors import Blocked

SLEEP = time.sleep
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
DEFAULTS = {"enabled": True, "max_per_run": 80, "recheck_hours": 6}


def _probe(url):
    """(status, final url, text) of a page, following redirects with a browser-like fingerprint. Raises Blocked when refused."""
    from curl_cffi import requests

    r = requests.get(url, impersonate="chrome", timeout=30, allow_redirects=True, headers={"Accept-Language": "fr-FR,fr;q=0.9"})
    if r.status_code in (403, 429, 503):
        raise Blocked(f"HTTP {r.status_code}")
    return r.status_code, r.url, r.text


def _moved(url, final):
    a, b = urlparse(url), urlparse(final)
    return b.hostname != a.hostname or b.path.rstrip("/") != a.path.rstrip("/")


def _login(final):
    return "/login" in urlparse(final).path  # a login wall says nothing about whether the ad is online


def _generic(l, probe):
    status, final, _ = probe(l["url"])
    if _login(final):
        return "unknown"
    if status in (404, 410) or (status < 400 and _moved(l["url"], final)):
        return "gone"
    return "live" if status < 400 else "unknown"


def _bienici(l, probe):
    status, _, text = probe("https://www.bienici.com/realEstateAd.json?id=" + l["id"].split(":", 1)[1])
    if status in (404, 410):
        return "gone"
    try:
        on = (json.loads(text).get("status") or {}).get("onTheMarket")
    except ValueError:
        return "unknown"
    return "live" if on is True else "gone" if on is False else "unknown"


def _immojeune(l, probe):
    status, final, text = probe(l["url"])
    if _login(final):
        return "unknown"
    if status in (404, 410) or (status < 400 and _moved(l["url"], final)):
        return "gone"
    if status >= 400:
        return "unknown"
    uid = l["id"].split(":", 1)[1]
    if uid.startswith("u"):  # a residence unit: the residence page lists the units on offer
        return "live" if f'value="{uid[1:]}"' in text else "gone"
    return "live"


DEACTIVATED = re.compile(r"Cette annonce a .{1,6}d.sactiv", re.I)


def _lcdc(l, probe):
    """La Carte des Colocs answers HTTP 410 with "Cette annonce a été désactivée le ... son propriétaire semble avoir reçu suffisamment de candidatures"."""
    status, final, text = probe(l["url"])
    if _login(final):
        return "unknown"
    if status in (404, 410) or DEACTIVATED.search(re.sub(r"<[^>]+>", " ", text)) or (status < 400 and _moved(l["url"], final)):
        return "gone"
    return "live" if status < 400 else "unknown"


def _foncia(l, probe):
    try:
        relay.get(l["url"])
    except urllib.error.HTTPError as e:
        return "gone" if e.code in (404, 410) else "unknown"
    return "live"


CHECKERS = {"bienici": _bienici, "immojeune": _immojeune, "foncia": _foncia, "paruvendu": _generic, "studapart": _generic, "lacartedescolocs": _lcdc}


def check(l, probe=_probe):
    """'live', 'gone' or 'unknown' for one listing dict (with its state key under "id")."""
    fn = CHECKERS.get(l["source"])
    if fn is None:
        return "unknown"
    try:
        return fn(l, probe)
    except Blocked:
        return "unknown"
    except Exception:
        return "unknown"


def sweep(state, now, profile, probe=_probe, sleep=None):
    """Check the least recently checked active listings; a gone one is closed at once (and revives if the results show it again).
    Returns counts only: the Actions log is public."""
    from . import store

    cfg = {**DEFAULTS, **(profile.get("liveness") or {})}
    out = {"checked": 0, "gone": 0, "unknown": 0}
    if not cfg["enabled"]:
        return out
    sleep = sleep or SLEEP
    due = []
    for key, e in state["listings"].items():
        l = e.get("listing")
        if not l or e.get("dup_of") or e["status"] != "active" or l["source"] not in CHECKERS:
            continue
        last = e.get("checked")
        if last and store.age_minutes(now, last) < cfg["recheck_hours"] * 60:
            continue
        due.append((last or "", e["first_seen"], key))
    for _, _, key in sorted(due)[: cfg["max_per_run"]]:
        e = state["listings"][key]
        verdict = check({**e["listing"], "id": key}, probe)
        out["checked"] += 1
        e["checked"] = now
        if verdict == "gone":
            e["status"] = "stale"
            e["gone"] = now
            out["gone"] += 1
        elif verdict == "unknown":
            out["unknown"] += 1
        sleep(1)
    return out
