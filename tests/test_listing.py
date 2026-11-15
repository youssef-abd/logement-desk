from factories import make_listing


def test_key_combines_source_and_id():
    assert make_listing(source="bienici", source_id="x1").key == "bienici:x1"


def test_to_dict_keeps_all_fields_and_defaults():
    d = make_listing(photos=["https://img.test/1.jpg"]).to_dict()
    assert d["rent_cc"] == 500.0
    assert d["photos"] == ["https://img.test/1.jpg"]
    assert d["flags"] == [] and d["tags"] == []
    assert d["kind"] is None and d["found_by"] == ""
