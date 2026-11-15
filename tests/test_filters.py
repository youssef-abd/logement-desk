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
