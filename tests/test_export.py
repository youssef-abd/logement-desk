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
    for i in range(450):
        state["listings"][f"s:{i}"] = {"dup_of": None, "first_seen": f"2026-11-15T10:{i % 60:02d}:00+00:00", "last_seen": NOW,
                                       "status": "active", "also": [], "notified": False,
                                       "listing": make_listing(source="s", source_id=str(i)).to_dict()}
    assert len(build_payload(state, {}, NOW)["listings"]) == 400
