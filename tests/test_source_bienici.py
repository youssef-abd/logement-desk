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


def test_parse_survives_odd_photo_and_list_values():
    assert parse({"realEstateAds": None}, max_photos=6) == []
    [l] = parse({"realEstateAds": [{**AD, "photos": None}]}, max_photos=6)
    assert l.photos == []
    [l] = parse({"realEstateAds": [{**AD, "photos": ["x", {"url": "https://file.example.test/p1"}]}]}, max_photos=6)
    assert l.photos == ["https://file.example.test/p1"]


def test_agency_name_is_kept_for_professionals_only():
    [pro] = parse({"realEstateAds": [{**AD, "accountDisplayName": "AGENCE EXAMPLE"}]}, max_photos=6)
    assert pro.poster == "agence" and pro.poster_name == "AGENCE EXAMPLE"
    [priv] = parse({"realEstateAds": [{**AD, "adCreatedByPro": False, "accountDisplayName": "Some Person"}]}, max_photos=6)
    assert priv.poster == "particulier" and priv.poster_name is None


def test_build_filters_only_asks_for_ads_still_on_the_market(profile):
    profile["sources"]["bienici"]["zone_ids"] = ["-1"]
    assert build_filters(profile)["onTheMarket"] == [True]
