import pytest

from logement.errors import Blocked
from logement.paging import collect
from logement.sources import bienici, leboncoin


class Ad:
    def __init__(self, i):
        self.source_id = str(i)


def pages(sizes, start=0):
    out, n = [], start
    for s in sizes:
        out.append([Ad(n + i) for i in range(s)])
        n += s
    return out


def getter(pgs, calls, block_at=None):
    def get(n):
        calls.append(n)
        if n == block_at:
            raise Blocked("x")
        return pgs[n]
    return get


def ids(ads):
    return [a.source_id for a in ads]


def test_deep_stops_on_short_page():
    calls = []
    out = collect(getter(pages([200, 200, 37, 5]), calls), 6, 200, lambda a: a.source_id)
    assert len(out) == 437 and len({a.source_id for a in out}) == 437 and calls == [0, 1, 2]


def test_light_is_one_call():
    calls = []
    out = collect(getter(pages([200, 200]), calls), 1, 200, lambda a: a.source_id)
    assert len(out) == 200 and calls == [0]


def test_block_after_first_keeps_partial_and_first_raises():
    calls = []
    out = collect(getter(pages([200, 200]), calls, block_at=1), 6, 200, lambda a: a.source_id)
    assert len(out) == 200
    with pytest.raises(Blocked):
        collect(getter(pages([200]), [], block_at=0), 6, 200, lambda a: a.source_id)


def test_dedupe_and_sleep_between_pages():
    sleeps = []
    p = pages([35, 35, 10])
    p[1][0] = Ad(0)  # duplicate of page 1
    out = collect(lambda n: p[n], 9, 35, lambda a: a.source_id, sleep=sleeps.append, pause=1.5)
    assert len(out) == 79 and sleeps == [1.5, 1.5]


def test_bienici_filters_size_and_offset(profile):
    profile["sources"]["bienici"]["zone_ids"] = ["-1"]
    f = bienici.build_filters(profile, size=200, offset=400)
    assert f["size"] == 200 and f["from"] == 400
    f = bienici.build_filters(profile)
    assert f["size"] == profile["sources"]["bienici"].get("size", 24) and f["from"] == 0


def test_bienici_1970_date_is_none():
    ad = {"id": "a1", "publicationDate": "1970-01-01T00:00:00Z", "price": 1}
    [l] = bienici.parse({"realEstateAds": [ad]}, 3)
    assert l.published_at is None


def test_bienici_deep_uses_pages_and_leboncoin_exposes_sleep(profile, monkeypatch):
    calls = []
    def fake(profile, offset, size):
        calls.append((offset, size))
        return [Ad(offset + i) for i in range(size if offset < 400 else 3)]
    monkeypatch.setattr(bienici, "fetch_page", fake)
    profile["sources"]["bienici"]["zone_ids"] = ["-1"]
    out = bienici.fetch({**profile, "deep": True})
    assert calls == [(0, 200), (200, 200), (400, 200)] and len(out) == 403
    calls.clear()
    bienici.fetch(profile)
    assert calls == [(0, profile["sources"]["bienici"].get("size", 24))]
    assert callable(leboncoin.SLEEP)
