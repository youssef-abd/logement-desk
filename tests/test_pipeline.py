import copy

from factories import make_listing
from logement import store
from logement.run import run

NOW = "2026-11-15T10:00:00+00:00"
FIVE_MINUTES_LATER = "2026-11-15T10:05:00+00:00"


def fetchers():
    a = make_listing(source="bienici", source_id="b1", poster="agence", description="Studio meublé, Visale accepté")
    dup = make_listing(source="leboncoin", source_id="l1", poster="particulier")  # same flat as b1
    other = make_listing(source="leboncoin", source_id="l2", rent_cc=420.0, surface_m2=15.0)
    return {"bienici": lambda p: [copy.deepcopy(a)], "leboncoin": lambda p: [copy.deepcopy(dup), copy.deepcopy(other)]}


def test_whole_pipeline_is_idempotent(profile):
    for name, opts in profile["sources"].items():
        opts["enabled"] = name in ("bienici", "leboncoin")
    state = store.empty()
    first = run(profile, state, NOW, fetchers=fetchers())
    assert sorted(a.key for a in first["alerts"]) == ["bienici:b1", "leboncoin:l2"]
    assert state["listings"]["leboncoin:l1"]["dup_of"] == "bienici:b1"

    snapshot = copy.deepcopy(state)
    second = run(profile, state, FIVE_MINUTES_LATER, fetchers=fetchers())
    assert second["alerts"] == []
    assert state == snapshot  # nothing to commit on an unchanged run
