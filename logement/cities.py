"""Which cities a run collects. The registry (data/cities.json, built by scripts/make_cities.py) lists, per city, the postcodes and the
per-source options that were verified to return listings there. Lyon is the profile's own hand-tuned setup and needs no entry."""
import json
import os
import unicodedata
import urllib.parse
import urllib.request

REGISTRY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cities.json")
HOME = "lyon"


def load_registry(path=None):
    try:
        with open(path or REGISTRY, encoding="utf-8") as f:
            return json.load(f).get("cities", {})
    except (OSError, ValueError):
        return {}


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "-".join("".join(c if c.isalnum() else " " for c in s).split())


def options_for(c, zones=()):
    """The per-source options for a city record {name, dept, postal_codes, lat, lng, region}, built from each site's address pattern."""
    name, dept, sl = c["name"], c["dept"], slug(c["name"])
    pv = "https://www.paruvendu.fr/immobilier/recherche/location/appartement/"
    out = {
        "leboncoin": {"city": name, "lat": c["lat"], "lng": c["lng"], "radius_m": 9000},
        "paruvendu": {"urls": [f"{pv}{sl}/"]},
        "foncia": {"urls": [f"https://fr.foncia.com/location/{sl}-{dept}/appartement-meuble", f"https://fr.foncia.com/location/{sl}-{dept}/appartement"]},
        "immojeune": {"urls": [f"https://www.immojeune.com/logement-etudiant/{sl}-{dept}.html", f"https://www.immojeune.com/location-etudiant/{sl}-{dept}.html"]},
        "studapart": {"urls": [f"https://www.studapart.com/fr/location-studio-{sl}", f"https://www.studapart.com/fr/location-appartement-{sl}"]},
    }
    if c.get("region"):
        out["lacartedescolocs"] = {"url": f"https://www.lacartedescolocs.fr/colocations/fr/{c['region']}/{sl}"}
    if zones:
        out["bienici"] = {"zone_ids": list(zones)}
    return out


def bienici_zones(c):
    """Bien'ici's zone ids for the city (its own search suggestion service); empty when it cannot be found."""
    try:
        req = urllib.request.Request("https://res.bienici.com/suggest.json?q=" + urllib.parse.quote(c["name"]), headers={"User-Agent": "logement-run"})
        with urllib.request.urlopen(req, timeout=15) as r:
            found = json.load(r)
    except Exception:
        return []
    for x in found:
        if x.get("type") == "city" and (c.get("postal_codes") and set(x.get("postalCodes") or []) & set(c["postal_codes"])):
            return list(x.get("zoneIds") or [])
    return []


def _valid(c):
    return (isinstance(c, dict) and isinstance(c.get("key"), str) and isinstance(c.get("name"), str) and isinstance(c.get("dept"), str)
            and isinstance(c.get("postal_codes"), list) and c["postal_codes"] and isinstance(c.get("lat"), (int, float)) and isinstance(c.get("lng"), (int, float)))


def plan(profile, registry, wanted, zones_for=bienici_zones):
    """[(key, name, postal_codes, per-source overrides or None for the profile's own settings)] for the wanted cities.
    An entry is a key (Lyon, or a city whose options were verified in the registry) or a full city record, whose options are then built
    from the address patterns. Unusable entries are ignored; with nothing usable the run falls back to the home city."""
    out, seen = [], set()
    for item in wanted or [HOME]:
        key = item if isinstance(item, str) else (item.get("key") if isinstance(item, dict) else None)
        if key in seen or not isinstance(key, str):
            continue
        seen.add(key)
        if key == HOME:
            out.append((HOME, "Lyon", list(profile["areas"].get("allowed_postal_codes") or []), None))
        elif key in registry:
            c = registry[key]
            out.append((key, c["name"], list(c["postal_codes"]), c.get("sources", {})))
        elif _valid(item):
            out.append((key, item["name"], list(item["postal_codes"]), options_for(item, zones_for(item))))
    return out or [(HOME, "Lyon", list(profile["areas"].get("allowed_postal_codes") or []), None)]


def desk_cities(env=None):
    """The cities chosen on the desk (None when it cannot be reached: the profile's own choice then applies)."""
    env = os.environ if env is None else env
    base, token = env.get("DESK_URL", "").rstrip("/"), env.get("PUSH_TOKEN", "")
    if not base or not token:
        return None
    req = urllib.request.Request(f"{base}/api/search", headers={"x-push-token": token, "User-Agent": "logement-run"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            cities = json.load(r).get("cities")
    except Exception:
        return None
    return [c for c in cities if isinstance(c, (str, dict))] if isinstance(cities, list) and cities else None
