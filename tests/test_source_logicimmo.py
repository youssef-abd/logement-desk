import json

import pytest

from logement.errors import Blocked, DriftError
from logement.sources import logicimmo
from logement.sources.logicimmo import parse_html


def card(ident, price=700, private=False, text="Beau studio meublé", city="Lyon 2ème arrondissement"):
    return {
        "url": f"https://www.logic-immo.com/detail-annonce/location/x/{ident}",
        "location": {"address": {"city": city, "zipCode": "69002"}},
        "mainDescription": {"headline": "Location appartement 1 pièce", "description": text},
        "provider": {"isPrivateOwner": private, "intermediaryCard": {"title": "OXIA Lyon"}},
        "metadata": {"creationDate": "2026-11-21T09:03:00Z"},
        "gallery": {"images": [{"url": "https://cdn/1.jpg"}, {"url": "https://cdn/2.jpg"}]},
        "rawData": {"price": price, "surface": {"main": 25.18}, "nbroom": 1, "providerzipcode": "69002", "providercity": "Lyon"},
    }


def page(cards, order=None, suggested=()):
    data = {"data": {"classified-serp-data": {"classifiedsData": cards, "classifieds": order if order is not None else list(cards), "suggestedClassifieds": list(suggested), "page": 1, "totalCount": 344}}}
    return f'<html><script>window["__UFRN_FETCHER__"]=JSON.parse({json.dumps(json.dumps(data))})</script></html>'


def test_parse_reads_the_embedded_listings():
    [l] = parse_html(page({"A1": card("A1")}), 3)
    assert (l.source, l.source_id, l.rent_cc, l.surface_m2, l.rooms) == ("logicimmo", "A1", 700, 25.18, 1)
    assert l.district == "Lyon 2e" and l.postal_code == "69002" and l.furnished is True
    assert l.poster == "agence" and l.poster_name == "OXIA Lyon" and l.published_at == "2026-11-21T09:03:00Z"
    assert l.photos == ["https://cdn/1.jpg", "https://cdn/2.jpg"] and l.url.endswith("/A1")


def test_parse_private_owner_unknown_furnished_and_skips_suggestions_and_unpriced():
    cards = {"A1": card("A1", private=True, text="Studio lumineux"), "A2": card("A2", price=None), "S1": card("S1")}
    ls = parse_html(page(cards, order=["A1", "A2"], suggested=["S1"]), 3)
    assert [l.source_id for l in ls] == ["A1"]
    assert ls[0].poster == "particulier" and ls[0].poster_name is None and ls[0].furnished is None
    assert parse_html(page({"A1": card("A1", text="Studio non meublé")}), 3)[0].furnished is False


def test_pages_without_the_data_or_with_another_shape_are_drift():
    with pytest.raises(DriftError):
        parse_html("<html>nothing here</html>", 3)
    with pytest.raises(DriftError):
        parse_html('<script>window["__UFRN_FETCHER__"]=JSON.parse("{\\"data\\":{}}")</script>', 3)


def profile(deep):
    return {"max_photos": 3, "deep": deep, "sources": {"logicimmo": {"light_count": 1, "paths": ["a", "b", "c"]}}}


def test_light_run_reads_the_first_searches_only_and_deep_reads_all_without_duplicates(monkeypatch):
    calls = []
    monkeypatch.setattr(logicimmo, "_get", lambda u: calls.append(u) or page({"A1": card("A1")}))
    monkeypatch.setattr(logicimmo, "SLEEP", lambda s: None)
    assert len(logicimmo.fetch(profile(False))) == 1 and calls == [logicimmo.BASE + "a"]
    calls.clear()
    assert len(logicimmo.fetch(profile(True))) == 1 and len(calls) == 3


def test_blocked_first_page_raises_but_a_later_block_keeps_what_was_read(monkeypatch):
    def always(u):
        raise Blocked("403")
    monkeypatch.setattr(logicimmo, "_get", always)
    with pytest.raises(Blocked):
        logicimmo.fetch(profile(True))

    def later(u):
        if u.endswith("b"):
            raise Blocked("403")
        return page({"A1": card("A1")})
    monkeypatch.setattr(logicimmo, "_get", later)
    monkeypatch.setattr(logicimmo, "SLEEP", lambda s: None)
    assert len(logicimmo.fetch(profile(True))) == 1
