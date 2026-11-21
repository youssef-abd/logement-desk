from logement import store
from logement.dedupe import process
from logement.export import build_payload
from factories import make_listing

NOW = "2026-11-15T10:00:00+00:00"


def test_payload_has_listings_newest_first_without_duplicates_and_health(profile):
    state = store.empty()
    a = make_listing(source="bienici", source_id="b1", poster="agence", photos=["https://img.example.test/1.jpg"])
    b = make_listing(source="leboncoin", source_id="l1")          # same flat as b1 -> duplicate entry
    c = make_listing(source="leboncoin", source_id="l2", rent_cc=420.0, surface_m2=15.0)
    process(state, [a], {"bienici"}, "2026-11-15T09:00:00+00:00", profile)
    process(state, [b, c], {"leboncoin"}, NOW, profile)
    state["health"]["bienici"] = {"consecutive_failures": 0, "last_success": NOW, "last_error": None, "cooldown_until": None, "blocked_runs": 0}
    p = build_payload(state, {"bienici": {"status": "ok", "fetched": 24, "kept": 20}}, NOW)
    assert [l["id"] for l in p["listings"]] == ["leboncoin:l2", "bienici:b1"]
    assert p["listings"][1]["also"] == 1 and p["listings"][1]["photos"] == ["https://img.example.test/1.jpg"]
    assert "description" not in p["listings"][0]
    assert p["updated"] == NOW
    assert p["health"]["bienici"] == {"last_success": NOW, "failures": 0, "error": None, "cooldown_until": None,
                                      "run": {"status": "ok", "fetched": 24, "kept": 20}}


def test_payload_is_capped(profile):
    state = store.empty()
    for i in range(1600):
        state["listings"][f"s:{i}"] = {"dup_of": None, "first_seen": f"2026-11-15T10:{i % 60:02d}:00+00:00", "last_seen": NOW,
                                       "status": "active", "also": [], "notified": False,
                                       "listing": make_listing(source="s", source_id=str(i)).to_dict()}
    assert len(build_payload(state, {}, NOW)["listings"]) == 1500


def _add(state, key, minute, tags=None, status="active", **kw):
    state["listings"][key] = {"dup_of": None, "first_seen": f"2026-11-15T09:{minute:02d}:00+00:00", "last_seen": NOW,
                              "status": status, "also": [], "notified": False,
                              "listing": make_listing(source="s", source_id=key, **kw).to_dict() | ({"tags": tags} if tags is not None else {})}


def _rows(state):
    return {r["id"]: r for r in build_payload(state, {}, NOW)["listings"]}


def test_photos_capped_to_three():
    state = store.empty()
    _add(state, "a", 1, photos=[f"https://i.example.test/{i}.jpg" for i in range(6)])
    assert len(_rows(state)["a"]["photos"]) == 3


def test_eur_m2_and_posted():
    state = store.empty()
    _add(state, "a", 1, rent_cc=500.0, surface_m2=20.0)
    _add(state, "b", 2, rent_cc=300.0, surface_m2=8.0, published_at="1970-01-01T00:00:00+00:00")
    _add(state, "c", 3, surface_m2=None, published_at="")
    r = _rows(state)
    assert r["a"]["eur_m2"] == 25.0 and r["a"]["posted"] == "2026-11-15T10:00:00+00:00"
    assert r["b"]["eur_m2"] is None and r["b"]["posted"] == "2026-11-15T09:02:00+00:00"
    assert r["c"]["eur_m2"] is None and r["c"]["posted"] == "2026-11-15T09:03:00+00:00"


def test_identical_agency_units_collapse():
    state = store.empty()
    for i in range(3):
        _add(state, f"ag{i}", 10 + i, poster="agence")
    _add(state, "ag_other", 20, poster="agence", rent_cc=510.0)
    for i in range(2):
        _add(state, f"pv{i}", 30 + i, poster="particulier")
    _add(state, "nosurf1", 40, poster="agence", surface_m2=None)
    _add(state, "nosurf2", 41, poster="agence", surface_m2=None)
    r = _rows(state)
    assert set(r) == {"ag2", "ag_other", "pv0", "pv1", "nosurf1", "nosurf2"}
    assert r["ag2"]["similar"] == 2
    assert all(r[k]["similar"] == 0 for k in r if k != "ag2")


def test_areas_medians_and_tags_need_eight():
    state = store.empty()
    for i in range(8):
        _add(state, f"n{i}", i, rent_cc=500.0, surface_m2=20.0 + i * 0.0, poster="particulier")  # 25 eur/m2
    _add(state, "cheap", 20, tags=["x"], rent_cc=360.0, surface_m2=20.0)      # 18 <= 0.75*25
    _add(state, "too", 21, rent_cc=240.0, surface_m2=20.0)                    # 12 <= 0.5*25
    _add(state, "stale", 22, status="stale", rent_cc=100.0, surface_m2=20.0)  # ignored for areas
    _add(state, "few", 23, rent_cc=100.0, surface_m2=20.0, postal_code="69009")
    before = repr(state)
    p = build_payload(state, {}, NOW)
    r = {x["id"]: x for x in p["listings"]}
    assert p["areas"]["69003"]["n"] == 10 and p["areas"]["69003"]["median_eur_m2"] == 25.0
    assert p["areas"]["69009"] == {"n": 1, "median_eur_m2": 5.0}
    assert r["cheap"]["tags"] == ["x", "cheap-for-area"]
    assert r["too"]["tags"] == ["too-cheap"]
    assert r["few"]["tags"] == [] or "too-cheap" not in r["few"]["tags"]
    assert "cheap-for-area" not in r["few"]["tags"]
    assert repr(state) == before


def test_no_area_tags_below_eight():
    state = store.empty()
    for i in range(6):
        _add(state, f"n{i}", i, rent_cc=500.0)
    _add(state, "low", 20, rent_cc=100.0)
    assert "too-cheap" not in _rows(state)["low"]["tags"]


def test_scam_risk_is_computed_in_the_payload(profile):
    state = store.empty()
    bad = make_listing(source="leboncoin", source_id="s1", poster="particulier", rent_cc=300.0, surface_m2=20.0,
                       description="Les clés vous seront envoyées par la poste, virement avant la visite")
    ok = make_listing(source="leboncoin", source_id="s2", poster="particulier", rent_cc=520.0, surface_m2=21.0, description="Studio calme")
    process(state, [bad, ok], {"leboncoin"}, NOW, profile)
    rows = {r["id"]: r for r in build_payload(state, {}, NOW)["listings"]}
    assert rows["leboncoin:s1"]["risk"] == "high" and "keys sent by post" in rows["leboncoin:s1"]["risk_reasons"]
    assert rows["leboncoin:s2"]["risk"] is None and rows["leboncoin:s2"]["risk_reasons"] == []


def test_price_tags_only_compare_small_flats(profile):
    state = store.empty()
    for i in range(9):
        process(state, [make_listing(source="s", source_id=f"s{i}", rent_cc=30.0 * (18 + 2 * i), surface_m2=float(18 + 2 * i), poster="particulier")], {"s"}, NOW, profile)
    process(state, [make_listing(source="s", source_id="big", rent_cc=500.0, surface_m2=100.0, poster="particulier")], {"s"}, NOW, profile)
    process(state, [make_listing(source="s", source_id="deal", rent_cc=250.0, surface_m2=19.0, poster="particulier")], {"s"}, NOW, profile)
    rows = {r["id"]: r for r in build_payload(state, {}, NOW)["listings"]}
    assert "too-cheap" not in rows["s:big"]["tags"] and rows["s:big"]["risk"] is None
    assert "too-cheap" in rows["s:deal"]["tags"] and rows["s:deal"]["risk"] == "check"


def test_only_the_most_recent_stale_listings_are_exported(profile):
    state = store.empty()
    for i in range(130):
        state["listings"][f"s:{i}"] = {"dup_of": None, "first_seen": NOW, "last_seen": f"2026-11-14T{i // 60:02d}:{i % 60:02d}:00+00:00",
                                       "status": "stale", "also": [], "notified": True,
                                       "listing": make_listing(source="s", source_id=str(i), rent_cc=500.0 + i).to_dict()}
    process(state, [make_listing(source="s", source_id="live")], {"s"}, NOW, profile)
    ids = {r["id"] for r in build_payload(state, {}, NOW)["listings"]}
    assert "s:live" in ids and len(ids) == 101 and "s:129" in ids and "s:0" not in ids
