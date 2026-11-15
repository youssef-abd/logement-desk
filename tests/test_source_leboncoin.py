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


def test_charges_are_not_added_when_the_included_attribute_is_missing():
    ad = fake_ad({"monthly_charges": "40"})
    del ad.attributes["charges_included"]
    assert parse_ad(ad, max_photos=6).rent_cc == 506.0
