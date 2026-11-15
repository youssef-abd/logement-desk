import json

import pytest

from factories import make_listing
from logement import store
from logement.errors import Blocked, DriftError
from logement.run import check_drift, run

NOW = "2026-11-15T10:00:00+00:00"


def profile_with(profile, *enabled):
    for name, opts in profile["sources"].items():
        opts["enabled"] = name in enabled
    return profile


def ok_fetcher(*listings):
    return lambda profile: list(listings)


def test_one_failing_source_does_not_stop_the_others(profile):
    p = profile_with(profile, "bienici", "leboncoin")
    def boom(_):
        raise RuntimeError("secret detail that must not be stored")
    state = store.empty()
    res = run(p, state, NOW, fetchers={"bienici": ok_fetcher(make_listing()), "leboncoin": boom})
    assert res["report"]["bienici"]["status"] == "ok"
    assert res["report"]["leboncoin"] == {"status": "error", "error": "RuntimeError"}
    assert [a.key for a in res["alerts"]] == ["bienici:a1"]
    assert res["run_failed"] is False
    assert state["health"]["leboncoin"]["last_error"] == "RuntimeError"


def test_all_sources_failing_fails_the_run(profile):
    p = profile_with(profile, "bienici")
    def boom(_):
        raise RuntimeError
    assert run(p, store.empty(), NOW, fetchers={"bienici": boom})["run_failed"] is True


def test_blocked_source_is_retried_once_then_succeeds(profile):
    p = profile_with(profile, "bienici")
    calls, waits = [], []
    def flaky(_):
        calls.append(1)
        if len(calls) == 1:
            raise Blocked("403")
        return [make_listing()]
    res = run(p, store.empty(), NOW, fetchers={"bienici": flaky}, sleep=waits.append)
    assert len(calls) == 2 and waits == [p["poll"]["retry_wait_s"]]
    assert res["report"]["bienici"]["status"] == "ok"


def test_repeated_blocks_trigger_a_cooldown_and_then_resume(profile):
    p = profile_with(profile, "bienici")
    p["poll"].update(block_threshold=2, block_cooldown_minutes=60)
    def blocked(_):
        raise Blocked("403")
    state = store.empty()
    fetchers = {"bienici": blocked}
    run(p, state, NOW, fetchers=fetchers, sleep=lambda s: None)
    run(p, state, NOW, fetchers=fetchers, sleep=lambda s: None)
    assert state["health"]["bienici"]["cooldown_until"] == "2026-11-15T11:00:00+00:00"
    before = json.dumps(state, sort_keys=True)
    res = run(p, state, "2026-11-15T10:30:00+00:00", fetchers=fetchers, sleep=lambda s: None)
    assert res["report"]["bienici"]["status"] == "cooldown"
    assert json.dumps(state, sort_keys=True) == before
    fetchers["bienici"] = ok_fetcher(make_listing())
    res = run(p, state, "2026-11-15T11:01:00+00:00", fetchers=fetchers, sleep=lambda s: None)
    assert res["report"]["bienici"]["status"] == "ok"
    assert state["health"]["bienici"]["cooldown_until"] is None


def test_a_persistently_failing_source_stops_changing_state(profile):
    p = profile_with(profile, "bienici")
    def boom(_):
        raise RuntimeError
    state = store.empty()
    for _ in range(p["health"]["fail_threshold"] + 1):
        run(p, state, NOW, fetchers={"bienici": boom})
    before = json.dumps(state, sort_keys=True)
    run(p, state, NOW, fetchers={"bienici": boom})
    assert json.dumps(state, sort_keys=True) == before


def test_failure_threshold_is_reported_once(profile):
    p = profile_with(profile, "bienici")
    p["health"]["fail_threshold"] = 2
    def boom(_):
        raise RuntimeError
    state = store.empty()
    assert run(p, state, NOW, fetchers={"bienici": boom})["newly_failing"] == []
    assert run(p, state, NOW, fetchers={"bienici": boom})["newly_failing"] == ["bienici"]
    assert run(p, state, NOW, fetchers={"bienici": boom})["newly_failing"] == []
    assert run(p, state, NOW, fetchers={"bienici": boom})["failing"] == ["bienici"]


def test_drift_is_an_error_not_an_empty_result(profile):
    p = profile_with(profile, "bienici")
    broken = [make_listing(source_id=f"x{i}", rent_cc=None) for i in range(6)]
    res = run(p, store.empty(), NOW, fetchers={"bienici": ok_fetcher(*broken)})
    assert res["report"]["bienici"] == {"status": "error", "error": "DriftError"}


def test_check_drift_ignores_small_samples_and_healthy_data():
    check_drift([make_listing(rent_cc=None)], 0.5)
    check_drift([make_listing(source_id=str(i)) for i in range(6)], 0.5)
    with pytest.raises(DriftError):
        check_drift([make_listing(source_id=str(i), url="") for i in range(6)], 0.5)


def test_filters_and_flags_are_applied_before_state(profile):
    p = profile_with(profile, "bienici")
    good = make_listing(source_id="g", description="Visale accepté")
    too_dear = make_listing(source_id="d", rent_cc=p["max_rent_cc"] + 500)
    res = run(p, store.empty(), NOW, fetchers={"bienici": ok_fetcher(good, too_dear)})
    assert [a.key for a in res["alerts"]] == ["bienici:g"]
    assert res["alerts"][0].flags == ["visale"] and res["alerts"][0].found_by == "bienici"
    assert res["report"]["bienici"] == {"status": "ok", "fetched": 2, "kept": 1}
