"""Which cities a run collects. The registry (data/cities.json, built by scripts/make_cities.py) lists, per city, the postcodes and the
per-source options that were verified to return listings there. Lyon is the profile's own hand-tuned setup and needs no entry."""
import json
import os
import urllib.request

REGISTRY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cities.json")
HOME = "lyon"


def load_registry(path=None):
    try:
        with open(path or REGISTRY, encoding="utf-8") as f:
            return json.load(f).get("cities", {})
    except (OSError, ValueError):
        return {}


def plan(profile, registry, wanted):
    """[(key, name, postal_codes, per-source overrides or None for the profile's own settings)] for the wanted cities.
    Unknown keys are ignored; with nothing usable the run falls back to the home city."""
    out = []
    for key in dict.fromkeys(wanted or [HOME]):
        if key == HOME:
            out.append((HOME, "Lyon", list(profile["areas"].get("allowed_postal_codes") or []), None))
        elif key in registry:
            c = registry[key]
            out.append((key, c["name"], list(c["postal_codes"]), c.get("sources", {})))
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
    return [c for c in cities if isinstance(c, str)] if isinstance(cities, list) and cities else None
