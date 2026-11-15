import json
import pathlib

import pytest

from logement.config import load_profile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _example():
    return json.loads((ROOT / "profile.example.json").read_text(encoding="utf-8"))


def test_example_profile_is_valid():
    p = load_profile(str(ROOT / "profile.example.json"), env={})
    assert p["max_rent_cc"] > 0
    assert p["furnished"] in ("required", "preferred", "any")


def test_env_profile_wins_over_the_file(tmp_path):
    p = _example()
    p["max_rent_cc"] = 123
    got = load_profile(str(tmp_path / "missing.json"), env={"PROFILE_JSON": json.dumps(p)})
    assert got["max_rent_cc"] == 123


def test_missing_keys_raise(tmp_path):
    f = tmp_path / "p.json"
    f.write_text('{"max_rent_cc": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        load_profile(str(f), env={})


def test_bad_furnished_value_raises(tmp_path):
    p = _example()
    p["furnished"] = "maybe"
    f = tmp_path / "p.json"
    f.write_text(json.dumps(p), encoding="utf-8")
    with pytest.raises(ValueError, match="furnished"):
        load_profile(str(f), env={})
