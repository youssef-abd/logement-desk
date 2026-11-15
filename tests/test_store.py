from logement import store


def test_load_missing_file_returns_empty_state(tmp_path):
    assert store.load(str(tmp_path / "s.json")) == {"listings": {}, "health": {}}


def test_save_then_load_round_trips_and_leaves_no_tmp_file(tmp_path):
    p = str(tmp_path / "sub" / "s.json")
    state = {"listings": {"a:1": {"last_seen": "2026-11-15T10:00:00+00:00"}}, "health": {}}
    store.save(p, state)
    assert store.load(p) == state
    assert not (tmp_path / "sub" / "s.json.tmp").exists()


def test_age_minutes():
    assert store.age_minutes("2026-11-15T12:00:00+00:00", "2026-11-15T10:30:00+00:00") == 90


def test_prune_drops_only_old_entries():
    now = "2026-11-15T12:00:00+00:00"
    state = {"listings": {
        "old": {"last_seen": "2026-09-01T00:00:00+00:00"},
        "new": {"last_seen": "2026-11-14T00:00:00+00:00"},
    }, "health": {}}
    assert store.prune(state, now, 45) == 1
    assert list(state["listings"]) == ["new"]
