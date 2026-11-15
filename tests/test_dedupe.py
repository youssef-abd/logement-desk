import copy

from factories import make_listing
from logement import store
from logement.dedupe import process, same_flat

NOW = "2026-11-15T10:00:00+00:00"
PLUS_60M = "2026-11-15T11:00:00+00:00"
PLUS_200M = "2026-11-15T13:20:00+00:00"
PLUS_13H = "2026-11-15T23:00:00+00:00"


def test_new_listing_alerts_and_is_stored(profile):
    state = store.empty()
    alerts = process(state, [make_listing()], {"bienici"}, NOW, profile)
    assert [a.key for a in alerts] == ["bienici:a1"]
    e = state["listings"]["bienici:a1"]
    assert e["status"] == "active" and e["notified"] is False and e["first_seen"] == NOW
    assert e["listing"]["rent_cc"] == 500.0


def test_second_identical_pass_changes_nothing(profile):
    state = store.empty()
    process(state, [make_listing()], {"bienici"}, NOW, profile)
    snapshot = copy.deepcopy(state)
    assert process(state, [make_listing()], {"bienici"}, NOW, profile) == []
    assert state == snapshot


def test_cross_source_duplicate_is_attached_not_alerted(profile):
    state = store.empty()
    a = make_listing(source="bienici", source_id="b1", poster="agence")
    b = make_listing(source="leboncoin", source_id="l1", poster="particulier")
    process(state, [a], {"bienici"}, NOW, profile)
    assert process(state, [b], {"leboncoin"}, NOW, profile) == []
    assert state["listings"]["leboncoin:l1"]["dup_of"] == "bienici:b1"
    assert "leboncoin:l1" in state["listings"]["bienici:b1"]["also"]


def test_two_agency_listings_from_one_source_stay_apart(profile):
    state = store.empty()
    a = make_listing(source_id="u1", poster="agence")
    b = make_listing(source_id="u2", poster="agence")
    assert len(process(state, [a, b], {"bienici"}, NOW, profile)) == 2


def test_private_repost_under_a_new_id_is_not_alerted_again(profile):
    state = store.empty()
    first = make_listing(source="leboncoin", source_id="l1", poster="particulier")
    repost = make_listing(source="leboncoin", source_id="l2", poster="particulier")
    process(state, [first], {"leboncoin"}, NOW, profile)
    assert process(state, [repost], {"leboncoin"}, NOW, profile) == []


def test_unknown_fields_never_merge(profile):
    state = store.empty()
    a = make_listing(source="bienici", source_id="b1")
    b = make_listing(source="leboncoin", source_id="l1", surface_m2=None)
    process(state, [a], {"bienici"}, NOW, profile)
    assert len(process(state, [b], {"leboncoin"}, NOW, profile)) == 1


def test_different_rent_or_postal_code_do_not_merge(profile):
    assert not same_flat(make_listing().to_dict(), make_listing(source="leboncoin", rent_cc=560.0).to_dict())
    assert not same_flat(make_listing().to_dict(), make_listing(source="leboncoin", postal_code="69007").to_dict())


def test_last_seen_is_only_touched_after_the_interval(profile):
    state = store.empty()
    process(state, [make_listing()], {"bienici"}, NOW, profile)
    process(state, [make_listing()], {"bienici"}, PLUS_60M, profile)
    assert state["listings"]["bienici:a1"]["last_seen"] == NOW
    process(state, [make_listing()], {"bienici"}, PLUS_200M, profile)
    assert state["listings"]["bienici:a1"]["last_seen"] == PLUS_200M


def test_unseen_listing_goes_stale_only_when_its_source_answered(profile):
    state = store.empty()
    process(state, [make_listing()], {"bienici"}, NOW, profile)
    process(state, [], set(), PLUS_13H, profile)
    assert state["listings"]["bienici:a1"]["status"] == "active"
    process(state, [], {"bienici"}, PLUS_13H, profile)
    assert state["listings"]["bienici:a1"]["status"] == "stale"


def test_a_stale_listing_seen_again_becomes_active(profile):
    state = store.empty()
    process(state, [make_listing()], {"bienici"}, NOW, profile)
    process(state, [], {"bienici"}, PLUS_13H, profile)
    assert process(state, [make_listing()], {"bienici"}, PLUS_13H, profile) == []
    e = state["listings"]["bienici:a1"]
    assert e["status"] == "active" and e["last_seen"] == PLUS_13H


def test_a_stale_listing_does_not_swallow_a_similar_new_one(profile):
    state = store.empty()
    process(state, [make_listing(source="leboncoin", source_id="l1", poster="particulier")], {"leboncoin"}, NOW, profile)
    process(state, [], {"leboncoin"}, PLUS_13H, profile)
    assert state["listings"]["leboncoin:l1"]["status"] == "stale"
    similar = make_listing(source="leboncoin", source_id="l2", poster="particulier")
    assert [a.key for a in process(state, [similar], {"leboncoin"}, PLUS_13H, profile)] == ["leboncoin:l2"]


def test_reactivating_a_stale_listing_refreshes_last_seen_even_with_a_long_touch_interval(profile):
    profile["touch_minutes"] = 100000
    state = store.empty()
    process(state, [make_listing()], {"bienici"}, NOW, profile)
    process(state, [], {"bienici"}, PLUS_13H, profile)
    process(state, [make_listing()], {"bienici"}, PLUS_13H, profile)
    e = state["listings"]["bienici:a1"]
    assert e["status"] == "active" and e["last_seen"] == PLUS_13H
