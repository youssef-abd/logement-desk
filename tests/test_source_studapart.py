import json

import pytest

from logement.errors import DriftError
from logement.sources import studapart
from logement.sources.studapart import parse_item, parse_response

PROPERTY = {
    "ad_type": "property", "lessorType": "owner", "distinctId": "a59f", "ownerName": "etienne", "title": "Studio TOUT INCLUS Part-Dieu",
    "rentWithExpensesAmount": 590, "propertySurface": 28, "roomsCount": 1, "isFurnished": True, "address": "51 Rue Leon Jouhaux",
    "city": "Lyon", "zipcode": "69003", "createdAt": 1783423816, "description": "Beau studio\r\n  lumineux",
    "canonicalUrls": {"fr": "/fr/logement-Lyon/Studio-de-28m2/property/a59f"},
    "media": json.dumps([{"filesystem": "property_images", "key": "x.jpg"}, {"filesystem": "property_images", "key": "y.jpg", "final_url": json.dumps({"property_images_small": "https://m/s.jpg", "property_images_large": "https://m/l.jpg"})}]),
}
RESIDENCE = {
    "ad_type": "residence", "distinctId": "residence_626", "residenceName": "UXCO Oxygene", "ownerName": "UXCO Oxygene", "rentWithExpensesAmount": 710,
    "propertySurface": 24, "roomsCount": 1, "isFurnished": True, "address": "3 Rue Bechevelin, 69007 Lyon, France", "city": "Lyon", "createdAt": 1650543877,
    "canonicalUrls": {"fr": "/fr/logement-Lyon/UXCO-Oxygene/residence/626"},
    "media": [{"filesystem": "residence_images", "key": "r.jpg", "final_url": json.dumps({"residence_images_large": "https://media.studapart.com/residence_images_large/r.jpg"})}],
}


def test_private_property():
    l = parse_item(PROPERTY, 3)
    assert (l.source, l.source_id, l.rent_cc, l.surface_m2, l.rooms, l.furnished) == ("studapart", "a59f", 590, 28, 1, True)
    assert l.url == "https://www.studapart.com/fr/logement-Lyon/Studio-de-28m2/property/a59f"
    assert l.district == "Lyon 3e" and l.postal_code == "69003" and l.poster == "particulier" and l.poster_name is None  # a private person's name is never kept
    assert l.published_at.startswith("2026-07-07") and l.description == "Beau studio lumineux"
    assert l.photos == ["https://media.studapart.com/property_images_large/x.jpg", "https://m/l.jpg"]


def test_residence_unit_is_an_agency_listing_with_postal_code_from_the_address():
    l = parse_item(RESIDENCE, 3)
    assert l.poster == "agence" and l.poster_name == "UXCO Oxygene" and l.tags == ["residence"] and l.published_at is None
    assert l.postal_code == "69007" and l.district == "Lyon 7e" and l.photos == ["https://media.studapart.com/residence_images_large/r.jpg"]


def test_items_without_rent_or_url_are_dropped_and_response_is_tolerant():
    assert parse_item({**PROPERTY, "rentWithExpensesAmount": None}, 3) is None
    assert parse_item({**PROPERTY, "canonicalUrls": {}}, 3) is None
    assert [l.source_id for l in parse_response({"results": [PROPERTY, RESIDENCE, {}]}, 3)] == ["a59f", "residence_626"]
    assert parse_response(None, 3) == [] and parse_response({}, 3) == []


def profile():
    return {"max_photos": 3, "sources": {"studapart": {"urls": ["https://x/a", "https://x/b"]}}}


def test_fetch_merges_pages_and_urls_without_duplicates(monkeypatch):
    monkeypatch.setattr(studapart, "_load", lambda url, scrolls, launch: [{"results": [PROPERTY]}, {"results": [PROPERTY, RESIDENCE]}])
    assert [l.source_id for l in studapart.fetch(profile())] == ["a59f", "residence_626"]


def test_a_page_that_makes_no_listing_request_is_reported_as_drift(monkeypatch):
    monkeypatch.setattr(studapart, "_load", lambda url, scrolls, launch: [])
    with pytest.raises(DriftError):
        studapart.fetch(profile())
