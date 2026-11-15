import copy
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def profile():
    with open(ROOT / "profile.example.json", encoding="utf-8") as f:
        p = json.load(f)
    p["areas"]["allowed_postal_codes"] = ["69003", "69007"]
    return copy.deepcopy(p)
