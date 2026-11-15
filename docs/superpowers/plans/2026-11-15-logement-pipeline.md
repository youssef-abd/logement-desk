# logement-desk, plan 1: the scraping pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python pipeline that polls Bien'ici, Leboncoin, La Carte des Colocs and ParuVendu, filters and flags listings from a private profile, removes duplicates, keeps state in git, and runs on GitHub Actions (by hand in this plan; the Cloudflare cron, desk and push alerts are plan 2).

**Architecture:** A package `logement/` with one module per responsibility (`listing`, `config`, `store`, `filters`, `flags`, `dedupe`, `sources/<name>`, `run`). Each source exposes a pure `parse` function (tested on inline fixtures) and a thin `fetch(profile)` that does the network call. `run.run()` isolates each source, then filters, flags, dedupes and updates state; `run.main()` is the CLI. State is one JSON file committed by `scripts/save_state.sh`.

**Tech Stack:** Python 3.12, pytest, `lbc==1.1.9` (Leboncoin client, needs `curl_cffi`), `curl_cffi` (browser-impersonating HTTP), the standard library for the rest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-15-logement-desk-design.md`. Plan 2 (separate file, written after this one ships) covers the Worker cron, the Pages desk, Web Push, the health panel and "Run now".

## Changes to the spec found while checking the sources

The spec is amended at the end of Task 16. These are decided here:

1. **Package name:** code lives in `logement/` (run as `python -m logement.run`), not `scripts/`.
2. **Area filter:** `areas.allowed_postal_codes` (empty list = allow all). Sources give a postal code (Bien'ici `postalCode`, Leboncoin `location.zipcode`); source-specific location settings (zone ids, coordinates, URLs) live under `sources.<name>`.
3. **Staleness, not "gone":** the poll only reads the newest page, so a listing can leave the results while still online. Status becomes `stale` ("not in the latest results") after `stale_after_minutes`, replacing `gone_after_polls`.
4. **State churn:** `last_seen` is rewritten only when it is older than `touch_minutes`, and health counters change only on failures, so unchanged runs produce no commit.
5. **Parking guard:** `reject_title_patterns` rejects listings with unknown room count whose title matches (parkings, caves). Leboncoin also filters server-side by real-estate type.
6. **Dedupe:** match on rent (within 10), surface (within 1 m2) and postal code, all known on both sides. No title similarity (titles differ across sources). Two listings from the same source where either poster is an agency are never merged (agencies list identical units).
7. **Verified source facts:** Bien'ici ignores the `furnished` filter, the working key is `isFurnished`; Bien'ici `price` already includes charges. `lbc` accepts `real_estate_type=["2"]` and `furnished=["1"]` (string lists) server-side.
8. **Deferred to plan 2:** `found_by` is just the source name for now; the per-query yield log and report come with the desk work.

## File structure

| File | Responsibility |
|---|---|
| `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.gitignore` | tooling |
| `profile.example.json` | the profile shape with placeholder values (the real `profile.json` is gitignored and stored as the `PROFILE_JSON` secret) |
| `logement/errors.py` | `Blocked`, `DriftError` |
| `logement/listing.py` | the `Listing` record |
| `logement/config.py` | load and validate the profile |
| `logement/store.py` | read/write/prune state, time helpers |
| `logement/filters.py` | `infer_kind`, `hard_filter` |
| `logement/flags.py` | `apply_flags` |
| `logement/dedupe.py` | `same_flat`, `find_match`, `process` (new, duplicate, stale) |
| `logement/sources/bienici.py`, `leboncoin.py`, `lacartedescolocs.py`, `paruvendu.py` | one adapter each |
| `logement/run.py` | orchestration, health, CLI |
| `scripts/save_state.sh` | commit and push state |
| `.github/workflows/ci.yml`, `run.yml`, `contract.yml` | tests, the run, the weekly live check |
| `tests/` | one test module per unit plus `test_pipeline.py` |
| `HANDOFF.md` | state of the project for the next session |

Run tests with the project venv. In a bash shell on this machine: `.venv/Scripts/python -m pytest -q`.

---

### Task 1: Project skeleton

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.gitignore`, `logement/__init__.py`, `logement/sources/__init__.py`, `logement/errors.py`, `tests/factories.py`, `tests/conftest.py`

- [ ] **Step 1: Create the tooling files**

`requirements.txt`:
```
lbc==1.1.9
curl_cffi
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest
```

`pytest.ini`:
```
[pytest]
pythonpath = . tests
testpaths = tests
```

`.gitignore`:
```
.venv/
__pycache__/
.pytest_cache/
*.tmp
profile.json
out/
```

`logement/__init__.py` (empty file) and `logement/sources/__init__.py` (empty file).

`logement/errors.py`:
```python
class Blocked(Exception):
    """A source answered 403/429 or a challenge page."""


class DriftError(Exception):
    """A source returned data but required fields are missing."""
```

`tests/factories.py`:
```python
from logement.listing import Listing


def make_listing(**kw):
    base = dict(
        source="bienici", source_id="a1", url="https://example.test/a1", title="Studio",
        rent_cc=500.0, charges=40.0, surface_m2=20.0, rooms=1, district="City 3e", postal_code="69003",
        furnished=True, poster="particulier", published_at="2026-11-15T10:00:00+00:00",
        description="", photos=[],
    )
    base.update(kw)
    return Listing(**base)
```

`tests/conftest.py`:
```python
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
```

- [ ] **Step 2: Create the venv and install**

Run: `python -m venv .venv && .venv/Scripts/python -m pip install -q -r requirements-dev.txt`
Expected: no error. Check: `.venv/Scripts/python -c "import lbc, curl_cffi, pytest; print('ok')"` prints `ok`.

- [ ] **Step 3: Confirm pytest starts**

Run: `.venv/Scripts/python -m pytest -q`
Expected: `no tests ran` (exit code 5 is fine here).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: project skeleton, tooling and test factories

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The `Listing` record

**Files:**
- Create: `logement/listing.py`
- Test: `tests/test_listing.py`

- [ ] **Step 1: Write the failing test**

`tests/test_listing.py`:
```python
from factories import make_listing


def test_key_combines_source_and_id():
    assert make_listing(source="bienici", source_id="x1").key == "bienici:x1"


def test_to_dict_keeps_all_fields_and_defaults():
    d = make_listing(photos=["https://img.test/1.jpg"]).to_dict()
    assert d["rent_cc"] == 500.0
    assert d["photos"] == ["https://img.test/1.jpg"]
    assert d["flags"] == [] and d["tags"] == []
    assert d["kind"] is None and d["found_by"] == ""
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_listing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'logement.listing'`.

- [ ] **Step 3: Implement**

`logement/listing.py`:
```python
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Listing:
    source: str
    source_id: str
    url: str
    title: str = ""
    rent_cc: Optional[float] = None
    charges: Optional[float] = None
    surface_m2: Optional[float] = None
    rooms: Optional[int] = None
    kind: Optional[str] = None
    district: Optional[str] = None
    postal_code: Optional[str] = None
    furnished: Optional[bool] = None
    poster: Optional[str] = None
    published_at: Optional[str] = None
    description: str = ""
    photos: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    found_by: str = ""

    @property
    def key(self):
        return f"{self.source}:{self.source_id}"

    def to_dict(self):
        return asdict(self)
```

- [ ] **Step 4: Run it to see it pass**

Run: `.venv/Scripts/python -m pytest tests/test_listing.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add logement/listing.py tests/test_listing.py
git commit -m "feat: Listing record

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Profile example and config loader

**Files:**
- Create: `profile.example.json`, `logement/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'logement.config'`).

- [ ] **Step 3: Create the example profile**

`profile.example.json` (placeholder values only; the real file is private):
```json
{
  "areas": {"allowed_postal_codes": []},
  "max_rent_cc": 700,
  "near_miss_margin": 50,
  "kinds": {"allowed": ["studio", "t1"], "max_surface_for_t1": 35},
  "min_surface_m2": 9,
  "furnished": "required",
  "reject_title_patterns": ["parking", "garage", "\\bbox\\b", "\\bcave\\b", "stockage"],
  "max_photos": 6,
  "stale_after_minutes": 720,
  "touch_minutes": 180,
  "prune_days": 45,
  "sources": {
    "bienici": {"enabled": true, "zone_ids": ["<bienici-zone-id>"], "size": 24},
    "leboncoin": {"enabled": true, "city": "<city>", "lat": 0.0, "lng": 0.0, "radius_m": 6000, "limit": 35, "max_square": 60},
    "lacartedescolocs": {"enabled": false, "url": "<list-page-url>"},
    "paruvendu": {"enabled": false, "url": "<list-page-url>"}
  },
  "flags": {
    "garant_no": {"patterns": ["sans garant", "garant non exig\\w*", "pas de garant", "aucun garant"]},
    "garant": {"patterns": ["\\bgarants?\\b", "caution solidaire"], "unless": ["garant_no"]},
    "visale": {"patterns": ["visale"]},
    "student_no": {"patterns": ["pas d.\\s?[ée]tudiant", "sans [ée]tudiant", "[ée]tudiants? non accept"]},
    "student_ok": {"patterns": ["[ée]tudiants? (?:accept|bienvenu)", "convient (?:à|a) un [ée]tudiant"], "unless": ["student_no"]},
    "agency_fees": {"patterns": ["frais d.agence", "honoraires"]},
    "charges_cc": {"patterns": ["charges comprises", "\\bCC\\b"]},
    "charges_hc": {"patterns": ["hors charges", "\\bHC\\b"]},
    "available_now": {"patterns": ["disponible imm[ée]diatement", "libre imm[ée]diatement"]},
    "scam": {"patterns": ["whatsapp", "western union", "mandat cash", "[àa] l.[ée]tranger"]}
  },
  "poll": {"retry_wait_s": 20, "block_threshold": 3, "block_cooldown_runs": 6},
  "health": {"fail_threshold": 3, "drift_ratio": 0.5}
}
```

- [ ] **Step 4: Implement the loader**

`logement/config.py`:
```python
import json
import os

REQUIRED = [
    "areas", "max_rent_cc", "near_miss_margin", "kinds", "min_surface_m2", "furnished",
    "reject_title_patterns", "max_photos", "stale_after_minutes", "touch_minutes", "prune_days",
    "sources", "flags", "poll", "health",
]


def load_profile(path=None, env=None):
    """The PROFILE_JSON environment variable (the GitHub secret) wins over the file."""
    env = os.environ if env is None else env
    raw = env.get("PROFILE_JSON", "").strip()
    if raw:
        data = json.loads(raw)
    else:
        with open(path or "profile.json", encoding="utf-8") as f:
            data = json.load(f)
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError("profile is missing: " + ", ".join(missing))
    if data["furnished"] not in ("required", "preferred", "any"):
        raise ValueError("furnished must be required, preferred or any")
    return data
```

- [ ] **Step 5: Run the tests and commit**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: 4 passed.

```bash
git add profile.example.json logement/config.py tests/test_config.py
git commit -m "feat: profile example and config loader

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: State store

**Files:**
- Create: `logement/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

`tests/test_store.py`:
```python
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
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_store.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'logement.store'`).

- [ ] **Step 3: Implement**

`logement/store.py`:
```python
import json
import os
from datetime import datetime


def empty():
    return {"listings": {}, "health": {}}


def load(path):
    if not os.path.exists(path):
        return empty()
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, state):
    """Write to a temp file then rename, so a crash never leaves half a file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def age_minutes(now, then):
    return (datetime.fromisoformat(now) - datetime.fromisoformat(then)).total_seconds() / 60


def prune(state, now, max_age_days):
    limit = max_age_days * 24 * 60
    old = [k for k, e in state["listings"].items() if age_minutes(now, e["last_seen"]) > limit]
    for k in old:
        del state["listings"][k]
    return len(old)
```

- [ ] **Step 4: Run the tests and commit**

Run: `.venv/Scripts/python -m pytest tests/test_store.py -v`
Expected: 4 passed.

```bash
git add logement/store.py tests/test_store.py
git commit -m "feat: state store with atomic save and prune

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Hard filter

> Amended during execution: the parking guard is skipped when the title contains studio, t1 or f1 (a review found real studios were rejected); see the test `test_studio_or_t1_with_parking_in_the_title_is_kept_even_when_rooms_is_unknown`.

**Files:**
- Create: `logement/filters.py`
- Test: `tests/test_filters.py`

- [ ] **Step 1: Write the failing test**

`tests/test_filters.py`:
```python
from factories import make_listing
from logement.filters import hard_filter, infer_kind


def test_a_normal_match_is_kept_without_tags(profile):
    l = make_listing()
    assert hard_filter(l, profile) is True
    assert l.tags == [] and l.kind == "studio"


def test_wrong_postal_code_is_rejected_and_missing_one_is_tagged(profile):
    assert hard_filter(make_listing(postal_code="75001"), profile) is False
    l = make_listing(postal_code=None)
    assert hard_filter(l, profile) is True and "area?" in l.tags


def test_empty_allowed_postal_codes_allows_everything(profile):
    profile["areas"]["allowed_postal_codes"] = []
    assert hard_filter(make_listing(postal_code="75001"), profile) is True


def test_surface_below_minimum_is_rejected(profile):
    assert hard_filter(make_listing(surface_m2=profile["min_surface_m2"] - 1), profile) is False


def test_parking_with_unknown_rooms_is_rejected_but_studio_with_parking_is_kept(profile):
    assert hard_filter(make_listing(title="Parking souterrain", rooms=None, surface_m2=12), profile) is False
    assert hard_filter(make_listing(title="Studio avec parking", rooms=1), profile) is True


def test_kind_rules(profile):
    assert hard_filter(make_listing(rooms=2, title="Appartement 2 pieces"), profile) is False
    l = make_listing(rooms=None, title="Location appartement")
    assert hard_filter(l, profile) is True and "kind?" in l.tags
    assert hard_filter(make_listing(rooms=1, title="T1 avec une chambre separee"), profile) is True
    too_big = profile["kinds"]["max_surface_for_t1"] + 10
    assert hard_filter(make_listing(rooms=1, surface_m2=too_big), profile) is False


def test_infer_kind_order():
    assert infer_kind(make_listing(title="Colocation 3 chambres", rooms=1)) == "coloc"
    assert infer_kind(make_listing(title="Studio meuble", rooms=1)) == "studio"
    assert infer_kind(make_listing(title="Une chambre", rooms=None)) == "room"
    assert infer_kind(make_listing(title="x", rooms=2)) == "t2"
    assert infer_kind(make_listing(title="x", rooms=4)) == "t3+"
    assert infer_kind(make_listing(title="x", rooms=None)) is None
    assert infer_kind(make_listing(title="x", rooms=3, kind="coloc")) == "coloc"


def test_rent_ceiling_near_miss_and_unknown(profile):
    ceiling, margin = profile["max_rent_cc"], profile["near_miss_margin"]
    l = make_listing(rent_cc=ceiling)
    assert hard_filter(l, profile) is True and "near-miss" not in l.tags
    l = make_listing(rent_cc=ceiling + 1)
    assert hard_filter(l, profile) is True and "near-miss" in l.tags
    assert hard_filter(make_listing(rent_cc=ceiling + margin + 1), profile) is False
    l = make_listing(rent_cc=None)
    assert hard_filter(l, profile) is True and "rent?" in l.tags


def test_furnished_policy(profile):
    assert hard_filter(make_listing(furnished=False), profile) is False
    l = make_listing(furnished=None)
    assert hard_filter(l, profile) is True and "furnished?" in l.tags
    profile["furnished"] = "any"
    assert hard_filter(make_listing(furnished=False), profile) is True
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_filters.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'logement.filters'`).

- [ ] **Step 3: Implement**

`logement/filters.py`:
```python
import re


def _tag(listing, tag):
    if tag not in listing.tags:
        listing.tags.append(tag)


def infer_kind(l):
    if l.kind:
        return l.kind
    title = (l.title or "").lower()
    if "coloc" in title:
        return "coloc"
    if l.rooms == 1:
        return "studio" if "studio" in title else "t1"
    if "studio" in title:
        return "studio"
    if "chambre" in title:
        return "room"
    if l.rooms == 2:
        return "t2"
    if l.rooms is not None and l.rooms >= 3:
        return "t3+"
    return None


def hard_filter(l, p):
    """True to keep. Adds tags for unknown values instead of rejecting on them."""
    codes = p["areas"].get("allowed_postal_codes") or []
    if codes:
        if l.postal_code is None:
            _tag(l, "area?")
        elif l.postal_code not in codes:
            return False

    if l.surface_m2 is not None and l.surface_m2 < p["min_surface_m2"]:
        return False

    if l.rooms is None and any(re.search(pat, l.title or "", re.I) for pat in p["reject_title_patterns"]):
        return False

    kind = infer_kind(l)
    if kind is None:
        _tag(l, "kind?")
    elif kind not in p["kinds"]["allowed"]:
        return False
    elif kind in ("studio", "t1") and l.surface_m2 is not None and l.surface_m2 > p["kinds"]["max_surface_for_t1"]:
        return False
    l.kind = kind

    if l.rent_cc is None:
        _tag(l, "rent?")
    else:
        ceiling = p["max_rent_cc"]
        if l.rent_cc > ceiling + p["near_miss_margin"]:
            return False
        if l.rent_cc > ceiling:
            _tag(l, "near-miss")

    if p["furnished"] == "required":
        if l.furnished is False:
            return False
        if l.furnished is None:
            _tag(l, "furnished?")
    return True
```

- [ ] **Step 4: Run the tests and commit**

Run: `.venv/Scripts/python -m pytest tests/test_filters.py -v`
Expected: 9 passed.

```bash
git add logement/filters.py tests/test_filters.py
git commit -m "feat: hard filter with kind inference and tags for unknowns

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Text flags

> Amended during execution: the example profile gained an `agency_fees_no` flag and `agency_fees` is dropped when it matches ("Sans frais d'agence" was flagged as having fees).

**Files:**
- Create: `logement/flags.py`
- Test: `tests/test_flags.py`

- [ ] **Step 1: Write the failing test**

`tests/test_flags.py`:
```python
import pytest

from factories import make_listing
from logement.flags import apply_flags


def flags_for(text, profile, title=""):
    l = make_listing(title=title, description=text)
    apply_flags(l, profile)
    return l.flags


@pytest.mark.parametrize("text,expected", [
    ("Visale accepté, garantie Visale possible", ["visale"]),
    ("Sans garant, Visale ok", ["garant_no", "visale"]),
    ("Garant exigé, 3 derniers bulletins", ["garant"]),
    ("Caution solidaire demandée", ["garant"]),
    ("Pas d'étudiants", ["student_no"]),
    ("Étudiants acceptés", ["student_ok"]),
    ("Convient à un étudiant", ["student_ok"]),
    ("Frais d'agence : 200 EUR", ["agency_fees"]),
    ("Écrivez-moi sur WhatsApp", ["scam"]),
    ("Loyer 450 CC", ["charges_cc"]),
    ("Loyer 400 HC", ["charges_hc"]),
    ("Disponible immédiatement", ["available_now"]),
    ("Beau studio lumineux", []),
])
def test_flags(text, expected, profile):
    assert flags_for(text, profile) == expected


def test_flags_also_read_the_title(profile):
    assert flags_for("", profile, title="Studio, étudiants acceptés") == ["student_ok"]
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_flags.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'logement.flags'`).

- [ ] **Step 3: Implement**

`logement/flags.py`:
```python
import re


def apply_flags(listing, profile):
    """Set listing.flags (sorted). A flag listed under another flag's `unless` is dropped when that one matches."""
    text = f"{listing.title}\n{listing.description}"
    specs = profile["flags"]
    matched = {name for name, s in specs.items() if any(re.search(pat, text, re.I) for pat in s["patterns"])}
    listing.flags = sorted(n for n in matched if not (set(specs[n].get("unless", [])) & matched))
```

- [ ] **Step 4: Run the tests and commit**

Run: `.venv/Scripts/python -m pytest tests/test_flags.py -v`
Expected: 14 passed.

```bash
git add logement/flags.py tests/test_flags.py
git commit -m "feat: text flags with negation handling

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Dedupe and state updates

**Files:**
- Create: `logement/dedupe.py`
- Test: `tests/test_dedupe.py`

- [ ] **Step 1: Write the failing test**

`tests/test_dedupe.py`:
```python
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
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_dedupe.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'logement.dedupe'`).

- [ ] **Step 3: Implement**

`logement/dedupe.py`:
```python
from . import store


def same_flat(a, b, rent_tol=10.0, surface_tol=1.0):
    """Both arguments are listing dicts. All of rent, surface and postal code must be known on both sides.
    Two listings from one source are never merged when either poster is an agency (identical units exist)."""
    for k in ("rent_cc", "surface_m2", "postal_code"):
        if a.get(k) is None or b.get(k) is None:
            return False
    if a["source"] == b["source"] and "agence" in (a.get("poster"), b.get("poster")):
        return False
    return (abs(a["rent_cc"] - b["rent_cc"]) <= rent_tol
            and abs(a["surface_m2"] - b["surface_m2"]) <= surface_tol
            and a["postal_code"] == b["postal_code"])


def find_match(entries, d):
    for key, e in entries.items():
        if e["listing"] is not None and same_flat(e["listing"], d):
            return key
    return None


def process(state, kept, ok_sources, now, profile):
    """Update state with the listings that passed the filter; return the listings that are new (to alert)."""
    entries = state["listings"]
    touch, stale = profile["touch_minutes"], profile["stale_after_minutes"]
    seen, alerts = set(), []
    for l in kept:
        key = l.key
        seen.add(key)
        e = entries.get(key)
        if e is not None:
            if store.age_minutes(now, e["last_seen"]) >= touch:
                e["last_seen"] = now
            if e["status"] == "stale":
                e["status"] = "active"
            continue
        d = l.to_dict()
        d["description"] = d["description"][:500]
        match = find_match(entries, d)
        if match:
            entries[key] = {"dup_of": match, "first_seen": now, "last_seen": now, "status": "active",
                            "listing": None, "also": [], "notified": True}
            entries[match]["also"].append(key)
            continue
        entries[key] = {"dup_of": None, "first_seen": now, "last_seen": now, "status": "active",
                        "listing": d, "also": [], "notified": False}
        alerts.append(l)
    for key, e in entries.items():
        if key in seen or e["dup_of"] or e["status"] == "stale":
            continue
        if key.split(":", 1)[0] in ok_sources and store.age_minutes(now, e["last_seen"]) >= stale:
            e["status"] = "stale"
    return alerts
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python -m pytest tests/test_dedupe.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add logement/dedupe.py tests/test_dedupe.py
git commit -m "feat: dedupe, duplicates, reposts and stale detection

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Bien'ici adapter

**Files:**
- Create: `logement/sources/bienici.py`
- Test: `tests/test_source_bienici.py`

- [ ] **Step 1: Write the failing test**

`tests/test_source_bienici.py`:
```python
from logement.sources.bienici import build_filters, parse

AD = {
    "id": "ag100-1", "city": "City 3e", "postalCode": "69003", "price": 430, "charges": 41,
    "surfaceArea": 19.71, "roomsQuantity": 1, "isFurnished": True, "adCreatedByPro": True,
    "publicationDate": "2026-11-14T00:36:11.792Z", "description": "Studio meuble", "title": "",
    "photos": [{"url": "https://file.example.test/p1"}, {"url": "https://file.example.test/p2"}, {"url_photo": "x"}],
}


def test_parse_maps_fields():
    [l] = parse({"realEstateAds": [AD]}, max_photos=6)
    assert l.source == "bienici" and l.source_id == "ag100-1"
    assert l.url == "https://www.bienici.com/annonce/ag100-1"
    assert (l.rent_cc, l.charges, l.surface_m2, l.rooms) == (430, 41, 19.71, 1)
    assert l.furnished is True and l.poster == "agence"
    assert l.district == "City 3e" and l.postal_code == "69003"
    assert l.published_at == "2026-11-14T00:36:11.792Z"
    assert "19.71 m²" in l.title
    assert l.photos == ["https://file.example.test/p1", "https://file.example.test/p2"]


def test_parse_caps_photos_and_handles_missing_fields():
    [l] = parse({"realEstateAds": [{**AD, "adCreatedByPro": None, "isFurnished": None}]}, max_photos=1)
    assert len(l.photos) == 1 and l.poster is None and l.furnished is None


def test_parse_private_poster_and_empty_response():
    [l] = parse({"realEstateAds": [{**AD, "adCreatedByPro": False}]}, max_photos=6)
    assert l.poster == "particulier"
    assert parse({}, max_photos=6) == []


def test_build_filters_uses_isfurnished_and_the_near_miss_ceiling(profile):
    profile["sources"]["bienici"]["zone_ids"] = ["-1"]
    f = build_filters(profile)
    assert f["isFurnished"] is True and "furnished" not in f
    assert f["maxPrice"] == profile["max_rent_cc"] + profile["near_miss_margin"]
    assert f["zoneIdsByTypes"] == {"zoneIds": ["-1"]}
    assert f["sortBy"] == "publicationDate" and f["sortOrder"] == "desc"
    profile["furnished"] = "any"
    assert "isFurnished" not in build_filters(profile)
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_source_bienici.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'logement.sources.bienici'`).

- [ ] **Step 3: Implement**

`logement/sources/bienici.py`:
```python
import json
import urllib.error
import urllib.parse
import urllib.request

from ..errors import Blocked
from ..listing import Listing

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
ENDPOINT = "https://www.bienici.com/realEstateAds.json"


def build_filters(profile):
    opts = profile["sources"]["bienici"]
    f = {
        "size": opts.get("size", 24), "from": 0, "filterType": "rent", "propertyType": ["flat"],
        "maxPrice": int(profile["max_rent_cc"] + profile["near_miss_margin"]),
        "sortBy": "publicationDate", "sortOrder": "desc",
        "zoneIdsByTypes": {"zoneIds": opts["zone_ids"]},
    }
    if profile["furnished"] == "required":
        f["isFurnished"] = True  # the key "furnished" is silently ignored by the site
    return f


def _title(rooms, surface, city):
    parts = []
    if rooms is not None:
        parts.append(f"{rooms} pièce(s)")
    if surface is not None:
        parts.append(f"{surface:g} m²")
    if city:
        parts.append(city)
    return " ".join(parts)


def parse(data, max_photos):
    out = []
    for a in data.get("realEstateAds", []):
        sid = str(a.get("id") or "")
        pro = a.get("adCreatedByPro")
        out.append(Listing(
            source="bienici", source_id=sid,
            url=f"https://www.bienici.com/annonce/{sid}" if sid else "",
            title=a.get("title") or _title(a.get("roomsQuantity"), a.get("surfaceArea"), a.get("city")),
            rent_cc=a.get("price"),  # already includes charges
            charges=a.get("charges"), surface_m2=a.get("surfaceArea"), rooms=a.get("roomsQuantity"),
            district=a.get("city"), postal_code=a.get("postalCode"), furnished=a.get("isFurnished"),
            poster=None if pro is None else ("agence" if pro else "particulier"),
            published_at=a.get("publicationDate"), description=a.get("description") or "",
            photos=[p["url"] for p in a.get("photos", []) if p.get("url")][:max_photos],
        ))
    return out


def fetch(profile):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"filters": json.dumps(build_filters(profile))})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 503):
            raise Blocked(f"HTTP {e.code}") from e
        raise
    return parse(data, profile["max_photos"])
```

- [ ] **Step 4: Run the tests and commit**

Run: `.venv/Scripts/python -m pytest tests/test_source_bienici.py -v`
Expected: 4 passed.

```bash
git add logement/sources/bienici.py tests/test_source_bienici.py
git commit -m "feat: Bien'ici adapter

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Leboncoin adapter

**Files:**
- Create: `logement/sources/leboncoin.py`
- Test: `tests/test_source_leboncoin.py`

- [ ] **Step 1: Write the failing test**

`tests/test_source_leboncoin.py`:
```python
from types import SimpleNamespace as NS

from logement.sources.leboncoin import parse_ad


def fake_ad(attrs=None, **over):
    a = {"furnished": "1", "square": "25", "rooms": "1", "real_estate_type": "2",
         "charges_included": "1", "monthly_charges": "40"}
    a.update(attrs or {})
    base = dict(
        id=123, url="https://www.leboncoin.fr/ad/locations/123", subject="T1 proche campus", price=506.0,
        first_publication_date="2026-11-15 12:13:07", body="Studio meuble", images=["u1", "u2", "u3"],
        location=NS(city="City", zipcode="69100"), raw={"owner": {"type": "private"}},
        attributes={k: NS(value=v) for k, v in a.items()},
    )
    base.update(over)
    return NS(**base)


def test_parse_maps_fields():
    l = parse_ad(fake_ad(), max_photos=2)
    assert l.source == "leboncoin" and l.source_id == "123"
    assert l.url == "https://www.leboncoin.fr/ad/locations/123"
    assert (l.rent_cc, l.charges, l.surface_m2, l.rooms) == (506.0, 40.0, 25.0, 1)
    assert l.furnished is True and l.poster == "particulier"
    assert l.district == "City 69100" and l.postal_code == "69100"
    assert l.published_at == "2026-11-15 12:13:07" and l.description == "Studio meuble"
    assert l.photos == ["u1", "u2"]


def test_charges_not_included_are_added_to_the_rent():
    l = parse_ad(fake_ad({"charges_included": "2", "monthly_charges": "40"}), max_photos=6)
    assert l.rent_cc == 546.0 and l.charges == 40.0


def test_furnished_values_and_missing_attributes():
    assert parse_ad(fake_ad({"furnished": "2"}), 6).furnished is False
    ad = fake_ad()
    del ad.attributes["furnished"]
    del ad.attributes["rooms"]
    del ad.attributes["monthly_charges"]
    l = parse_ad(ad, 6)
    assert l.furnished is None and l.rooms is None and l.charges is None and l.rent_cc == 506.0


def test_professional_owner_is_an_agency():
    assert parse_ad(fake_ad(raw={"owner": {"type": "pro"}}), 6).poster == "agence"
    assert parse_ad(fake_ad(raw={}), 6).poster is None
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_source_leboncoin.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'logement.sources.leboncoin'`).

- [ ] **Step 3: Implement**

`logement/sources/leboncoin.py`:
```python
from ..errors import Blocked
from ..listing import Listing


def _attr(ad, key):
    a = ad.attributes.get(key)
    return a.value if a is not None else None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_ad(ad, max_photos):
    price = _num(ad.price)
    charges = _num(_attr(ad, "monthly_charges"))
    rent = price
    if price is not None and charges and _attr(ad, "charges_included") != "1":
        rent = price + charges
    rooms = _num(_attr(ad, "rooms"))
    owner = (ad.raw.get("owner") or {}).get("type")
    loc = ad.location
    return Listing(
        source="leboncoin", source_id=str(ad.id), url=ad.url, title=ad.subject or "",
        rent_cc=rent, charges=charges, surface_m2=_num(_attr(ad, "square")),
        rooms=int(rooms) if rooms is not None else None,
        district=f"{loc.city} {loc.zipcode}".strip() if loc else None,
        postal_code=loc.zipcode if loc else None,
        furnished={"1": True, "2": False}.get(_attr(ad, "furnished")),
        poster={"private": "particulier", "pro": "agence"}.get(owner),
        published_at=str(ad.first_publication_date) if ad.first_publication_date else None,
        description=ad.body or "", photos=list(ad.images or [])[:max_photos],
    )


def fetch(profile):
    import lbc
    from lbc.exceptions import DatadomeError, RequestError

    opts = profile["sources"]["leboncoin"]
    client = lbc.Client()
    loc = lbc.City(lat=opts["lat"], lng=opts["lng"], radius=opts["radius_m"], city=opts["city"])
    extra = {"real_estate_type": ["2"]}  # apartments only: parkings and caves share the category
    if profile["furnished"] == "required":
        extra["furnished"] = ["1"]
    try:
        res = client.search(
            locations=[loc], page=1, limit=opts.get("limit", 35), sort=lbc.Sort.NEWEST,
            category=lbc.Category.IMMOBILIER_LOCATIONS,
            price=[0, int(profile["max_rent_cc"] + profile["near_miss_margin"])],
            square=[int(profile["min_surface_m2"]), int(opts.get("max_square", 60))], **extra,
        )
    except DatadomeError as e:
        raise Blocked("datadome") from e
    except RequestError as e:
        if any(code in str(e) for code in ("403", "429")):
            raise Blocked(str(e)[:60]) from e
        raise
    return [parse_ad(ad, profile["max_photos"]) for ad in res.ads]
```

- [ ] **Step 4: Run the tests and commit**

Run: `.venv/Scripts/python -m pytest tests/test_source_leboncoin.py -v`
Expected: 4 passed.

```bash
git add logement/sources/leboncoin.py tests/test_source_leboncoin.py
git commit -m "feat: Leboncoin adapter

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: La Carte des Colocs adapter

**Files:**
- Create: `logement/sources/lacartedescolocs.py`
- Test: `tests/test_source_lacartedescolocs.py`

- [ ] **Step 1: Write the failing test**

`tests/test_source_lacartedescolocs.py`:
```python
import json

from logement.sources.lacartedescolocs import parse_html

ITEM = {
    "@type": "RealEstateListing", "url": "https://www.example.test/colocations/city/a/abc123",
    "name": "Appartement 3 pièces de 80 m²", "image": "https://img.example.test/1.jpg",
    "about": {"@type": "Room", "address": {"@type": "PostalAddress", "addressLocality": "City"},
              "floorSize": {"@type": "QuantitativeValue", "value": 80}},
    "offers": {"@type": "Offer", "price": 580, "availabilityStarts": "2026-12-14"},
}


def page(*blocks):
    return "<html>" + "".join(f'<script type="application/ld+json">{b}</script>' for b in blocks) + "</html>"


def test_parse_reads_listings_nested_in_a_result_list():
    data = {"@type": "SearchResultsPage", "mainEntity": {"@type": "ItemList",
            "itemListElement": [{"@type": "ListItem", "position": 1, "item": ITEM}]}}
    [l] = parse_html(page(json.dumps(data)), max_photos=6)
    assert l.source == "lacartedescolocs" and l.source_id == "abc123" and l.kind == "coloc"
    assert l.url == ITEM["url"] and l.rent_cc == 580 and l.surface_m2 == 80 and l.district == "City"
    assert "2026-12-14" in l.description and l.photos == ["https://img.example.test/1.jpg"]


def test_parse_skips_duplicates_and_invalid_json():
    html = page("{not json", json.dumps([ITEM, ITEM]))
    assert len(parse_html(html, max_photos=6)) == 1
    assert parse_html("<html></html>", max_photos=6) == []
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_source_lacartedescolocs.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'logement.sources.lacartedescolocs'`).

- [ ] **Step 3: Implement**

`logement/sources/lacartedescolocs.py`:
```python
import json
import re

from ..errors import Blocked
from ..listing import Listing

LD = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def _walk(o):
    if isinstance(o, dict):
        if o.get("@type") == "RealEstateListing":
            yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def parse_html(html, max_photos):
    out, seen = [], set()
    for m in LD.finditer(html):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for o in _walk(data):
            url = o.get("url") or ""
            sid = url.rstrip("/").rsplit("/", 1)[-1]
            if not sid or sid in seen:
                continue
            seen.add(sid)
            about, offers = o.get("about") or {}, o.get("offers") or {}
            name, avail, img = o.get("name") or "", offers.get("availabilityStarts"), o.get("image")
            out.append(Listing(
                source="lacartedescolocs", source_id=sid, url=url, title=name, kind="coloc",
                rent_cc=offers.get("price"), surface_m2=(about.get("floorSize") or {}).get("value"),
                district=(about.get("address") or {}).get("addressLocality"),
                description=f"{name}. Disponible dès {avail}" if avail else name,
                photos=[img][:max_photos] if img else [],
            ))
    return out


def fetch(profile):
    from curl_cffi import requests

    url = profile["sources"]["lacartedescolocs"]["url"]
    r = requests.get(url, impersonate="chrome", timeout=30, headers={"Accept-Language": "fr-FR,fr;q=0.9"})
    if r.status_code in (403, 429, 503):
        raise Blocked(f"HTTP {r.status_code}")
    r.raise_for_status()
    return parse_html(r.text, profile["max_photos"])
```

- [ ] **Step 4: Run the tests and commit**

Run: `.venv/Scripts/python -m pytest tests/test_source_lacartedescolocs.py -v`
Expected: 2 passed.

```bash
git add logement/sources/lacartedescolocs.py tests/test_source_lacartedescolocs.py
git commit -m "feat: La Carte des Colocs adapter

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 11: ParuVendu adapter

**Files:**
- Create: `logement/sources/paruvendu.py`
- Test: `tests/test_source_paruvendu.py`

- [ ] **Step 1: Write the failing test**

`tests/test_source_paruvendu.py`:
```python
from logement.sources.paruvendu import parse_html

CARD_1 = """
<div class="blocAnnonce border-1" data-id="1000000001" data-cdp="">
 <a href="/immobilier/location/appartement/1000000001A1KILHAP000" title=" Appartement - 1 pièce(s) - 24 m²">
  <img src="https://img.paruvendu.fr/_static_/x/transparent_1x1.png" id="firstImg" />
  <script> const el = document.getElementById('firstImg'); el.src = 'https://img.paruvendu.fr/media_ext/_https_/m/aa/p1.jpg?func=crop&w=320'; </script>
  <img src="https://img.paruvendu.fr/media_ext/_https_/m/bb/p2.jpg?func=crop&amp;w=320" />
  <span class="text-sm font-bold">4</span>
 </a>
 <!-- Prix --> <div> 550 &euro; <span class="f10">CC*</span> </div>
 <p>Studio meublé de 24m² proche des universités</p>
 <span class="pseudoinfo">Particulier</span> <p class="text-xs"><img src="x.svg">13/11/2026</p>
</div>
"""
CARD_2 = """
<div class="blocAnnonce border-1" data-id="1000000002" data-cdp="">
 <a href="/immobilier/location/appartement/1000000002A1KILHAP000" title=" Appartement - 2 pièce(s) - 35 m²">
  <span class="text-sm font-bold">9</span>
 </a>
 <!-- Prix --> <div> 1&nbsp;270 &euro; <span class="f10">HC</span> </div>
 <p>Appartement non meublé</p>
 <span class="pseudoinfo">Professionnel</span> <p class="text-xs"><img src="x.svg">12/11/2026</p>
</div>
"""


def test_parse_reads_a_private_cc_card():
    l = parse_html("<html>" + CARD_1 + CARD_2 + "</html>", max_photos=6)[0]
    assert l.source == "paruvendu" and l.source_id == "1000000001"
    assert l.url == "https://www.paruvendu.fr/immobilier/location/appartement/1000000001A1KILHAP000"
    assert (l.rent_cc, l.rooms, l.surface_m2) == (550, 1, 24.0)
    assert l.poster == "particulier" and l.published_at == "2026-11-13"
    assert l.furnished is True and l.tags == []
    assert l.photos == ["https://img.paruvendu.fr/media_ext/_https_/m/aa/p1.jpg?func=crop&w=320",
                        "https://img.paruvendu.fr/media_ext/_https_/m/bb/p2.jpg?func=crop&w=320"]
    assert "proche des universités" in l.description


def test_parse_reads_a_professional_hc_card_with_a_thousands_space():
    l = parse_html(CARD_2, max_photos=6)[0]
    assert l.rent_cc == 1270 and l.poster == "agence" and l.tags == ["hc?"]
    assert l.furnished is None and l.rooms == 2 and l.photos == []


def test_parse_caps_photos_and_handles_no_cards():
    assert len(parse_html(CARD_1, max_photos=1)[0].photos) == 1
    assert parse_html("<html></html>", max_photos=6) == []
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_source_paruvendu.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'logement.sources.paruvendu'`).

- [ ] **Step 3: Implement**

`logement/sources/paruvendu.py`:
```python
import html as htmllib
import re
import urllib.error
import urllib.request

from ..errors import Blocked
from ..listing import Listing

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
SPLIT = re.compile(r'(?=<div[^>]*class="blocAnnonce)')
IS_CARD = re.compile(r'<div[^>]*class="blocAnnonce')
PRICE = re.compile(r"<!--\s*Prix\s*-->\s*<div>\s*([\d\s]+?)\s*€\s*(?:<span[^>]*>\s*(CC|HC))?", re.I)
LINK = re.compile(r'<a href="(/immobilier/location/[^"]+)"\s+title="([^"]*)"')
POSTER = re.compile(r'<span class="pseudoinfo">\s*([^<]+?)\s*</span>')
DATE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
PHOTO = re.compile(r"https://img\.paruvendu\.fr/media_ext/[^\"'\s)]+")


def _card(raw):
    c = htmllib.unescape(raw)
    did = re.search(r'data-id="(\d+)"', c)
    link = LINK.search(c)
    if not did or not link:
        return None
    price = PRICE.search(c)
    title = link.group(2).strip()
    rooms = re.search(r"(\d+)\s*pièce", title)
    surface = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", title)
    poster = POSTER.search(c)
    date = DATE.search(c)
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", c, flags=re.S))
    text = re.sub(r"\s+", " ", text).strip()
    furnished = True if re.search(r"meubl", text, re.I) and not re.search(r"non[ -]meubl", text, re.I) else None
    photos = list(dict.fromkeys(PHOTO.findall(c)))
    return did.group(1), link.group(1), title, price, rooms, surface, poster, date, text, furnished, photos


def parse_html(html, max_photos):
    out = []
    for raw in SPLIT.split(html):
        if not IS_CARD.match(raw):
            continue
        parsed = _card(raw)
        if parsed is None:
            continue
        did, href, title, price, rooms, surface, poster, date, text, furnished, photos = parsed
        tags = []
        rent = None
        if price:
            rent = int(re.sub(r"\D", "", price.group(1)) or 0) or None
            if (price.group(2) or "").upper() == "HC":
                tags.append("hc?")
        l = Listing(
            source="paruvendu", source_id=did, url="https://www.paruvendu.fr" + href, title=title,
            rent_cc=rent, surface_m2=float(surface.group(1).replace(",", ".")) if surface else None,
            rooms=int(rooms.group(1)) if rooms else None, furnished=furnished,
            poster=None if not poster else ("particulier" if poster.group(1).lower() == "particulier" else "agence"),
            published_at=f"{date.group(3)}-{date.group(2)}-{date.group(1)}" if date else None,
            description=text, photos=photos[:max_photos],
        )
        l.tags = tags
        out.append(l)
    return out


def fetch(profile):
    url = profile["sources"]["paruvendu"]["url"]
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 503):
            raise Blocked(f"HTTP {e.code}") from e
        raise
    return parse_html(html, profile["max_photos"])
```

- [ ] **Step 4: Run the tests and commit**

Run: `.venv/Scripts/python -m pytest tests/test_source_paruvendu.py -v`
Expected: 3 passed. If the photo assertion fails on a trailing character, inspect `l.photos` and adjust the `PHOTO` character class, not the test.

```bash
git add logement/sources/paruvendu.py tests/test_source_paruvendu.py
git commit -m "feat: ParuVendu adapter

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Orchestrator and CLI

**Files:**
- Create: `logement/run.py`
- Test: `tests/test_run.py`

- [ ] **Step 1: Write the failing test**

`tests/test_run.py`:
```python
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
    p["poll"].update(block_threshold=2, block_cooldown_runs=2)
    def blocked(_):
        raise Blocked("403")
    state = store.empty()
    fetchers = {"bienici": blocked}
    run(p, state, NOW, fetchers=fetchers, sleep=lambda s: None)
    run(p, state, NOW, fetchers=fetchers, sleep=lambda s: None)
    assert state["health"]["bienici"]["cooldown_left"] == 2
    assert run(p, state, NOW, fetchers=fetchers)["report"]["bienici"]["status"] == "cooldown"
    assert run(p, state, NOW, fetchers=fetchers)["report"]["bienici"]["status"] == "cooldown"
    fetchers["bienici"] = ok_fetcher(make_listing())
    assert run(p, state, NOW, fetchers=fetchers)["report"]["bienici"]["status"] == "ok"


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
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv/Scripts/python -m pytest tests/test_run.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'logement.run'`).

- [ ] **Step 3: Implement**

`logement/run.py`:
```python
import argparse
import copy
import importlib
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

from . import store
from .config import load_profile
from .dedupe import process
from .errors import Blocked, DriftError
from .filters import hard_filter
from .flags import apply_flags

DEFAULT_HEALTH = {"consecutive_failures": 0, "blocked_runs": 0, "cooldown_left": 0,
                  "last_success": None, "last_error": None}


def load_fetch(name):
    return importlib.import_module(f"logement.sources.{name}").fetch


def check_drift(listings, ratio, min_count=5):
    """Results that miss rent, url or id are a broken parser, not an empty market."""
    if len(listings) < min_count:
        return
    bad = sum(1 for l in listings if l.rent_cc is None or not l.url or not l.source_id)
    if bad / len(listings) > ratio:
        raise DriftError(f"{bad}/{len(listings)} listings miss rent, url or id")


def _fetch_with_retry(fetch, profile, sleep):
    try:
        return fetch(profile)
    except Blocked:
        sleep(profile["poll"]["retry_wait_s"])
        return fetch(profile)


def _record_success(h, now, profile):
    h["consecutive_failures"] = 0
    h["blocked_runs"] = 0
    h["last_error"] = None
    if h["last_success"] is None or store.age_minutes(now, h["last_success"]) >= profile["touch_minutes"]:
        h["last_success"] = now


def run(profile, state, now, fetchers=None, sleep=time.sleep):
    fetchers = fetchers or {}
    state.setdefault("listings", {})
    health = state.setdefault("health", {})
    threshold = profile["health"]["fail_threshold"]
    report, kept_all, ok, newly_failing = {}, [], set(), []
    for name, opts in profile["sources"].items():
        if not opts.get("enabled"):
            continue
        h = health.setdefault(name, dict(DEFAULT_HEALTH))
        if h["cooldown_left"] > 0:
            h["cooldown_left"] -= 1
            report[name] = {"status": "cooldown"}
            continue
        fetch = fetchers.get(name) or load_fetch(name)
        try:
            items = _fetch_with_retry(fetch, profile, sleep)
            check_drift(items, profile["health"]["drift_ratio"])
        except Blocked:
            h["consecutive_failures"] += 1
            h["blocked_runs"] += 1
            h["last_error"] = "blocked"
            if h["blocked_runs"] >= profile["poll"]["block_threshold"]:
                h["cooldown_left"] = profile["poll"]["block_cooldown_runs"]
                h["blocked_runs"] = 0
            report[name] = {"status": "blocked"}
        except Exception as e:  # one source must never stop the run; only the class name is kept (logs are public)
            h["consecutive_failures"] += 1
            h["last_error"] = type(e).__name__
            report[name] = {"status": "error", "error": type(e).__name__}
        else:
            _record_success(h, now, profile)
            for l in items:
                l.found_by = name
                apply_flags(l, profile)
            kept = [l for l in items if hard_filter(l, profile)]
            kept_all += kept
            ok.add(name)
            report[name] = {"status": "ok", "fetched": len(items), "kept": len(kept)}
            continue
        if h["consecutive_failures"] == threshold:
            newly_failing.append(name)
    alerts = process(state, kept_all, ok, now, profile)
    store.prune(state, now, profile["prune_days"])
    attempted = [r for r in report.values() if r["status"] in ("ok", "error", "blocked")]
    failing = sorted(n for n, h in health.items() if h["consecutive_failures"] >= threshold)
    return {"alerts": alerts, "report": report, "failing": failing, "newly_failing": newly_failing,
            "run_failed": bool(attempted) and not ok}


def notify(topic, text):
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=text.encode("utf-8"), method="POST")
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="logement.run")
    ap.add_argument("--check", action="store_true", help="dry run: write nothing")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any enabled source did not answer ok")
    ap.add_argument("--show", action="store_true", help="print the new listings (local use only: Actions logs are public)")
    ap.add_argument("--profile")
    ap.add_argument("--state", default="state/seen_listings.json")
    a = ap.parse_args(argv)

    profile = load_profile(a.profile)
    state = store.load(a.state)
    working = copy.deepcopy(state) if a.check else state
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res = run(profile, working, now)

    for name, r in res["report"].items():  # counts only: the Actions log of a public repo is public
        extra = f" fetched={r['fetched']} kept={r['kept']}" if r["status"] == "ok" else ""
        print(f"{name}: {r['status']}{extra}")
    active = sum(1 for e in working["listings"].values() if e["listing"] and e["status"] == "active")
    print(f"new={len(res['alerts'])} active={active}")
    if a.show:
        for l in res["alerts"]:
            print(f"  {l.rent_cc} EUR | {l.surface_m2} m2 | {l.district} | {l.poster} | {' '.join(l.flags + l.tags)} | {l.url}")
    if not a.check:
        store.save(a.state, state)
        topic = os.environ.get("NTFY_TOPIC", "")
        if topic and res["newly_failing"]:
            notify(topic, "logement-desk: source failing: " + ", ".join(res["newly_failing"]))
    if res["run_failed"]:
        return 1
    if a.strict and any(r["status"] != "ok" for r in res["report"].values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests and commit**

Run: `.venv/Scripts/python -m pytest tests/test_run.py -v`
Expected: 8 passed.

```bash
git add logement/run.py tests/test_run.py
git commit -m "feat: orchestrator with source isolation, retry, cooldown, drift and CLI

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 13: End-to-end idempotency test

**Files:**
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the test**

`tests/test_pipeline.py`:
```python
import copy

from factories import make_listing
from logement import store
from logement.run import run

NOW = "2026-11-15T10:00:00+00:00"


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
    second = run(profile, state, NOW, fetchers=fetchers())
    assert second["alerts"] == []
    assert state == snapshot  # nothing to commit on an unchanged run
```

- [ ] **Step 2: Run the whole suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass (about 56 tests). If `test_whole_pipeline_is_idempotent` fails on the second run, the cause is a field that changes per run (a timestamp or counter); fix the code that writes it, not the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_pipeline.py
git commit -m "test: whole pipeline is idempotent

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 14: State saving and workflows

**Files:**
- Create: `scripts/save_state.sh`, `.github/workflows/ci.yml`, `.github/workflows/run.yml`, `.github/workflows/contract.yml`

- [ ] **Step 1: Create `scripts/save_state.sh`**

```bash
#!/usr/bin/env bash
# Commit and push state/seen_listings.json when it changed. Prints SAVED or FAILED.
set -u
cd "$(dirname "$0")/.."
git add -- state/seen_listings.json 2>/dev/null
if git diff --cached --quiet; then
  echo "SAVED (nothing changed)"
  exit 0
fi
git commit -q -m "state: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
for i in 1 2 3; do
  if git pull --rebase --autostash -q origin main && git push -q origin HEAD:main; then
    echo "SAVED to main: $(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep 3
done
echo "FAILED: could not push"
exit 1
```

- [ ] **Step 2: Create `.github/workflows/ci.yml`**

```yaml
name: ci

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements*.txt
      - run: pip install -r requirements-dev.txt
      - run: python -m pytest -q
```

- [ ] **Step 3: Create `.github/workflows/run.yml`**

```yaml
name: run

# Real run or dry check. By hand for now: gh workflow run run.yml -f mode=full|check
# (the Cloudflare Worker cron that dispatches it comes with plan 2).
on:
  workflow_dispatch:
    inputs:
      mode:
        description: "full = real run and save state, check = dry run that writes nothing"
        type: choice
        options: [full, check]
        default: full

permissions:
  contents: write

concurrency:
  group: logement-run
  cancel-in-progress: false

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      PROFILE_JSON: ${{ secrets.PROFILE_JSON }}
      NTFY_TOPIC: ${{ secrets.NTFY_TOPIC }}
      PYTHONUTF8: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements.txt
      - run: pip install -r requirements.txt
      - name: Git identity for the state commit
        run: |
          git config user.name "logement-desk[bot]"
          git config user.email "logement-desk@users.noreply.github.com"
      - name: Scrape
        run: python -m logement.run ${{ inputs.mode == 'check' && '--check' || '' }}
      - name: Save state
        if: always() && inputs.mode != 'check'
        run: bash scripts/save_state.sh
      - name: Phone alert if the run failed
        if: failure() && env.NTFY_TOPIC != ''
        run: curl -s -d "logement-desk run failed" "https://ntfy.sh/${NTFY_TOPIC}" > /dev/null
```

- [ ] **Step 4: Create `.github/workflows/contract.yml`**

```yaml
name: contract

# Weekly live check: every enabled source must answer with parseable listings. Writes nothing.
on:
  schedule:
    - cron: "17 6 * * 1"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  contract:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      PROFILE_JSON: ${{ secrets.PROFILE_JSON }}
      NTFY_TOPIC: ${{ secrets.NTFY_TOPIC }}
      PYTHONUTF8: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements.txt
      - run: pip install -r requirements.txt
      - run: python -m logement.run --check --strict
      - name: Phone alert if a source broke
        if: failure() && env.NTFY_TOPIC != ''
        run: curl -s -d "logement-desk weekly check: a source is broken" "https://ntfy.sh/${NTFY_TOPIC}" > /dev/null
```

- [ ] **Step 5: Validate the YAML before pushing**

Run: `.venv/Scripts/python -m pip install -q pyyaml && .venv/Scripts/python -c "import yaml,glob; [yaml.safe_load(open(f,encoding='utf-8')) for f in glob.glob('.github/workflows/*.yml')]; print('yaml ok')"`
Expected: `yaml ok`. (Your notes record a workflow broken by an unquoted `: ` in a `run:` line; this catches that.)

- [ ] **Step 6: Commit and push (CI runs the tests)**

```bash
git add scripts/save_state.sh .github/workflows
git commit -m "ci: tests, run and weekly contract workflows, state saving

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push origin HEAD:main
gh run list -R youssef-abd/logement-desk --workflow ci.yml --limit 1
```
Expected: the `ci` run completes with `success` after a minute (`gh run watch <id> -R youssef-abd/logement-desk --exit-status`).

---

### Task 15: Real profile, live check, first full run

**Files:**
- Create (private, gitignored): `profile.json`
- Modify: GitHub repo secrets

- [ ] **Step 1: Build the private profile**

Copy `profile.example.json` to `profile.json` and set the owner's values (they stay out of the repo): `areas.allowed_postal_codes`, `max_rent_cc`, `near_miss_margin`, and under `sources`: the Bien'ici `zone_ids`, the Leboncoin `city`, `lat`, `lng`, `radius_m`. Get the Bien'ici zone id with:

Run: `curl -s "https://res.bienici.com/suggest.json?q=<city name>"` and read `zoneIds` of the entry whose `type` is `city`.

Check it loads: `.venv/Scripts/python -c "from logement.config import load_profile; load_profile('profile.json', env={}); print('profile ok')"`
Expected: `profile ok`. Check `git status` does not list `profile.json`.

- [ ] **Step 2: Live dry run on this machine**

Run: `.venv/Scripts/python -m logement.run --check --show --profile profile.json`
Expected: one line per enabled source such as `bienici: ok fetched=24 kept=N`, then `new=N active=N`, then the new listings with rent, surface, district, poster, flags and URL. If a source prints `error`, `blocked` or `DriftError`, stop and debug that adapter against the live response before going on.

- [ ] **Step 3: Eyeball the results against the sites**

Open 3 of the printed URLs. Confirm for each: the rent shown on the site matches `rent_cc` (charges included), the flat is furnished, and it is inside the allowed area. Any mismatch is a bug in that adapter's mapping: fix it with a test first.

- [ ] **Step 4: Store the profile as the Actions secret**

Run: `gh secret set PROFILE_JSON -R youssef-abd/logement-desk < profile.json`
Expected: `Set Actions secret PROFILE_JSON`. (Optional: `gh secret set NTFY_TOPIC -R youssef-abd/logement-desk` with a random topic name, to get failure alerts on the phone.)

- [ ] **Step 5: Dry run on GitHub's runner**

Run: `gh workflow run run.yml -R youssef-abd/logement-desk -f mode=check` then `gh run watch $(gh run list -R youssef-abd/logement-desk --workflow run.yml --limit 1 --json databaseId --jq '.[0].databaseId') -R youssef-abd/logement-desk --exit-status`
Expected: success, and the log lines show `ok` for the enabled sources and counts only. Open the log and confirm it contains no listing text, URL or profile value.

- [ ] **Step 6: First full run and second run**

Run `gh workflow run run.yml -R youssef-abd/logement-desk -f mode=full`, wait, then `git pull`.
Expected: a commit `state: <timestamp>` adds `state/seen_listings.json`. Run the same workflow again straight away: the log shows `new=0` and `SAVED (nothing changed)`, with no new commit. That is the "no commit when nothing changed" check.

---

### Task 16: Hand-off notes and spec amendments

**Files:**
- Create: `HANDOFF.md`
- Modify: `README.md`, `docs/superpowers/specs/2026-11-15-logement-desk-design.md`

- [ ] **Step 1: Write `HANDOFF.md`**

```markdown
# logement-desk: handoff

Read this first. State: plan 1 (pipeline) shipped; plan 2 (Worker cron, desk, push alerts) not started.

## What exists
- `logement/`: the pipeline. `python -m logement.run --check --show --profile profile.json` is the local dry run; `--strict` exits 1 if any source is not ok.
- State: `state/seen_listings.json`, committed by `scripts/save_state.sh` only when it changed.
- Workflows: `ci` (tests on push), `run` (by hand: `gh workflow run run.yml -f mode=full|check`), `contract` (weekly live check).

## Rules
- The repo and its Actions logs are PUBLIC. Logs print counts and status words only. Never print listing text, the profile or secrets.
- The real profile is the Actions secret `PROFILE_JSON` and the gitignored `profile.json`. The repo only has `profile.example.json`.
- No proxies, no IP rotation. A blocked source is retried once, then cooled down.
- The tool never contacts landlords.

## Secrets (names only)
`PROFILE_JSON` (required), `NTFY_TOPIC` (optional, failure alerts).

## Source facts (verified 2026-11-15)
- Bien'ici: JSON endpoint; filter key `isFurnished` (not `furnished`); `price` includes charges.
- Leboncoin: `lbc==1.1.9`, server-side `real_estate_type=["2"]`, `furnished=["1"]`; poster from `ad.raw["owner"]["type"]`.
- La Carte des Colocs: JSON-LD, needs `curl_cffi` browser impersonation; coloc only (disabled by default).
- ParuVendu: HTML cards, plain GET; last priority.
- Blocked from the cloud: PAP, AVendreALouer (403). SeLoger, Logic-Immo: DataDome.

## Gotchas
- Status `stale` means "not in the latest results", not "taken": the poll reads only the newest page.
- `last_seen` is rewritten at most every `touch_minutes`, on purpose (no commit on unchanged runs).
- When a source returns data but no prices, the run reports `DriftError`: the site changed its format.

## Next (plan 2)
Cloudflare Worker cron (dispatches `run.yml`), Pages desk with photos and stages, Web Push, source-health panel, "Run now", per-query yield log. Before showing photos, verify that each source's photo URLs load from another site (spec section 14). Adding sources: spec section 16.
```

- [ ] **Step 2: Update `README.md`**

Replace its last line ("Current state: source probe only ...") with:
```
Current state: the scraping pipeline runs on GitHub Actions (`run` workflow). See `HANDOFF.md`.
```

- [ ] **Step 3: Append the amendments to the spec**

Append to `docs/superpowers/specs/2026-11-15-logement-desk-design.md`:
```markdown

## 17. Amendments found while planning (2026-11-15)

- Code lives in the package `logement/` (run as `python -m logement.run`).
- `areas` is `{"allowed_postal_codes": [...]}`; per-source location settings live under `sources.<name>`.
- `gone_after_polls` is replaced by `stale_after_minutes` and `touch_minutes`; status `gone` is `stale` ("not in the latest results"), because only the newest page is polled and `last_seen` must not change every run.
- `reject_title_patterns` is a profile field (parking guard when the room count is unknown).
- Dedupe: rent (10), surface (1 m2) and postal code, all known; no title similarity; two listings of one source are not merged when either poster is an agency.
- Bien'ici uses `isFurnished`; `price` includes charges. Leboncoin is filtered server-side with `real_estate_type=["2"]` and `furnished=["1"]`.
- `found_by` is the source name; the per-query yield log moves to plan 2.
```

- [ ] **Step 4: Commit and push**

```bash
git add HANDOFF.md README.md docs/superpowers/specs
git commit -m "docs: handoff, readme and spec amendments

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push origin HEAD:main
```
Expected: CI passes again.
