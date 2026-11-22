"""Build data/cities.json: for each candidate city, the per-source options that really return listings there.

Run from the repo root on a machine that can reach the sites (the PC):  python scripts/make_cities.py [city name ...]
Every source is verified with its own adapter: it is kept for a city only when it returns listings inside that city's postcodes.
Lyon is not generated: its hand-tuned options stay in the private profile."""
import copy
import importlib
import json
import sys
import unicodedata
import urllib.parse
import urllib.request

sys.path.insert(0, ".")
from logement.cities import options_for, slug  # noqa: E402
from logement.errors import Blocked  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
CANDIDATES = ["Paris", "Marseille", "Toulouse", "Bordeaux", "Lille", "Nantes", "Montpellier", "Strasbourg", "Rennes", "Grenoble", "Nice"]
OUT = "data/cities.json"


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25))


def commune(name):
    q = urllib.parse.quote(name)
    c = get(f"https://geo.api.gouv.fr/communes?nom={q}&boost=population&limit=1&fields=nom,code,codesPostaux,centre,departement,region")[0]
    z = [x for x in get("https://res.bienici.com/suggest.json?q=" + q) if x.get("type") == "city" and c["code"] in (x.get("insee_codes") or [])]
    return c, (z[0]["zoneIds"] if z else [])


def candidates(c, zones):
    """The per-source options to try for a city, in the order they are verified (the same address patterns the run uses)."""
    rec = {"name": c["nom"], "dept": c["departement"]["code"], "postal_codes": c["codesPostaux"], "lat": c["centre"]["coordinates"][1],
           "lng": c["centre"]["coordinates"][0], "region": slug(c["region"]["nom"]) if c.get("region") else ""}
    out = {k: [v] for k, v in options_for(rec, zones).items()}
    out["paruvendu"].append({"urls": [f"https://www.paruvendu.fr/immobilier/recherche/location/appartement/{slug(c['nom'])}-{c['codesPostaux'][0]}/"]})
    out["studapart"] = [{**out["studapart"][0], "launch": {"channel": "msedge"}}]  # the PC's own Edge for the check
    return out


def verify(base, src, opts, codes, name):
    prof = copy.deepcopy(base)
    prof = {**prof, **(prof.get("collect") or {}), "deep": False}
    prof["sources"][src] = {**prof["sources"].get(src, {}), **opts, "enabled": True, "relay": False}
    fetch = importlib.import_module(f"logement.sources.{src}").fetch
    try:
        items = fetch(prof)
    except Blocked:
        return "blocked", 0, 0
    except Exception as e:  # a wrong URL is an ordinary outcome here
        return type(e).__name__, 0, 0
    key = slug(name)
    inside = sum(1 for l in items if l.postal_code in codes or (not l.postal_code and key in slug(f"{l.district or ''} {l.description[:120]}")))
    return "ok" if inside else "none", len(items), inside


def main(names):
    base = json.load(open("profile.json", encoding="utf-8"))
    try:
        registry = json.load(open(OUT, encoding="utf-8"))
    except FileNotFoundError:
        registry = {"cities": {}}
    for name in names:
        c, zones = commune(name)
        codes = c["codesPostaux"]
        lng, lat = c["centre"]["coordinates"]
        entry = {"name": c["nom"], "dept": c["departement"]["code"], "postal_codes": codes, "lat": lat, "lng": lng, "sources": {}}
        report = []
        for src, tries in candidates(c, zones).items():
            for opts in tries:
                status, n, inside = verify(base, src, opts, codes, c["nom"])
                if status == "ok":
                    entry["sources"][src] = opts if src != "studapart" else {k: v for k, v in opts.items() if k != "launch"}
                    report.append(f"{src}:{inside}/{n}")
                    break
            else:
                report.append(f"{src}:-({status})")
        registry["cities"][slug(c["nom"])] = entry
        print(f"{c['nom']:<13} postal={codes[0]}..{codes[-1]}  " + "  ".join(report), flush=True)
        json.dump(registry, open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)


def finish():
    """Leboncoin's option is only coordinates, so it needs no verification (the site may refuse this machine)."""
    registry = json.load(open(OUT, encoding="utf-8"))
    for e in registry["cities"].values():
        e["sources"].setdefault("leboncoin", {"city": e["name"], "lat": e["lat"], "lng": e["lng"], "radius_m": 9000})
    json.dump(registry, open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print("registry written:", ", ".join(e["name"] for e in registry["cities"].values()))


if __name__ == "__main__":
    if sys.argv[1:] == ["--finish"]:
        finish()
    else:
        main(sys.argv[1:] or CANDIDATES)
        finish()
