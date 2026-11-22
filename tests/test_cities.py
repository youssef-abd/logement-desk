import io
import json

from factories import make_listing
from logement import cities, store
from logement.errors import Blocked
from logement.run import run

NOW = "2026-11-15T10:00:00+00:00"
REG = {"grenoble": {"name": "Grenoble", "postal_codes": ["38000", "38100"], "sources": {"bienici": {"zone_ids": ["-80348"]}, "foncia": {"urls": ["https://x/gre"]}}}}


def only(profile, *names):
    for n, o in profile["sources"].items():
        o["enabled"] = n in names
    return profile


def test_plan_keeps_the_home_city_first_ignores_unknown_cities_and_falls_back(profile):
    home = cities.plan(profile, REG, None)
    assert [p[0] for p in home] == ["lyon"] and home[0][3] is None and home[0][2] == profile["areas"]["allowed_postal_codes"]
    two = cities.plan(profile, REG, ["grenoble", "atlantis", "lyon", "grenoble"])
    assert [p[0] for p in two] == ["grenoble", "lyon"] and two[0][3] == REG["grenoble"]["sources"]
    assert [p[0] for p in cities.plan(profile, REG, ["atlantis"])] == ["lyon"]


def test_each_city_is_fetched_with_its_own_options_and_listings_know_their_city(profile):
    p = only(profile, "bienici", "foncia")
    p["sources"]["bienici"]["zone_ids"] = ["-lyon"]
    p["sources"]["foncia"]["urls"] = ["https://x/lyon"]
    p["areas"]["allowed_postal_codes"] = ["69003"]
    seen = {"bienici": [], "foncia": []}

    def fetcher(name):
        def f(prof):
            o = prof["sources"][name]
            seen[name].append(o.get("zone_ids") or o.get("urls"))
            gre = "-80348" in str(o) or "gre" in str(o)
            return [make_listing(source=name, source_id=("g" if gre else "l") + name, postal_code="38000" if gre else "69003", rent_cc=500.0 if name == "bienici" else 600.0)]
        return f
    state = store.empty()
    res = run(p, state, NOW, fetchers={n: fetcher(n) for n in seen}, cities=["lyon", "grenoble"], registry=REG)
    assert seen == {"bienici": [["-lyon"], ["-80348"]], "foncia": [["https://x/lyon"], ["https://x/gre"]]}
    assert {l["city"] for e in state["listings"].values() for l in [e["listing"]]} == {"lyon", "grenoble"}
    assert res["report"]["bienici"] == {"status": "ok", "fetched": 2, "kept": 2}  # both cities' postcodes are allowed
    assert [c["key"] for c in res["cities"]] == ["lyon", "grenoble"] and res["cities"][1]["postal_codes"] == ["38000", "38100"]


def test_a_source_without_a_verified_option_for_a_city_is_skipped_there_and_one_failing_city_keeps_the_others(profile):
    p = only(profile, "leboncoin")  # the registry entry has no leboncoin option for Grenoble
    calls = []
    res = run(p, store.empty(), NOW, fetchers={"leboncoin": lambda prof: calls.append(1) or [make_listing()]}, cities=["lyon", "grenoble"], registry=REG)
    assert len(calls) == 1 and res["report"]["leboncoin"]["status"] == "ok"

    p = only(profile, "bienici")
    def flaky(prof):
        if "-80348" in str(prof["sources"]["bienici"]):
            raise Blocked("403")
        return [make_listing()]
    ok = run(p, store.empty(), NOW, fetchers={"bienici": flaky}, sleep=lambda s: None, cities=["lyon", "grenoble"], registry=REG)
    assert ok["report"]["bienici"]["status"] == "ok"
    both = run(p, store.empty(), NOW, fetchers={"bienici": lambda prof: (_ for _ in ()).throw(Blocked("403"))}, sleep=lambda s: None, cities=["lyon", "grenoble"], registry=REG)
    assert both["report"]["bienici"]["status"] == "blocked"


def test_desk_cities_reads_the_selection_and_never_raises(monkeypatch):
    env = {"DESK_URL": "https://desk.test", "PUSH_TOKEN": "t"}
    monkeypatch.setattr(cities.urllib.request, "urlopen", lambda req, timeout: io.BytesIO(json.dumps({"cities": ["lyon", "grenoble", 7]}).encode()))
    assert cities.desk_cities(env) == ["lyon", "grenoble"]
    monkeypatch.setattr(cities.urllib.request, "urlopen", lambda req, timeout: io.BytesIO(b'{"cities": []}'))
    assert cities.desk_cities(env) is None

    def boom(req, timeout):
        raise OSError("down")
    monkeypatch.setattr(cities.urllib.request, "urlopen", boom)
    assert cities.desk_cities(env) is None and cities.desk_cities({}) is None
