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


def test_studio_or_t1_with_parking_in_the_title_is_kept_even_when_rooms_is_unknown(profile):
    assert hard_filter(make_listing(title="Studio + cave", rooms=None), profile) is True
    assert hard_filter(make_listing(title="T1 avec parking", rooms=None), profile) is True
    assert hard_filter(make_listing(title="Garage box", rooms=None, surface_m2=15), profile) is False


def test_colocation_is_detected_from_the_description_but_not_from_a_landlord_rule(profile):
    assert infer_kind(make_listing(title="", description="Chambre dans un appartement partagé, cuisine partagée", rooms=3)) == "coloc"
    assert infer_kind(make_listing(title="Colocation 3 chambres", description="", rooms=3)) == "coloc"
    assert infer_kind(make_listing(title="T3", description="Colocation autorisée, beau T3 lumineux", rooms=3)) == "t3+"
    assert infer_kind(make_listing(title="Studio", description="Colocation non acceptée", rooms=1)) == "studio"


def wide(profile):
    profile["collect"] = {"max_rent_cc": 1200, "near_miss_margin": 0, "furnished": "any", "kinds": {"allowed": ["studio", "t1", "t2", "t3+", "room", "coloc"], "max_surface_for_t1": 60}}
    return profile


def test_collect_widens_the_net_but_marks_what_misses_the_owners_criteria(profile):
    p = wide(profile)
    cheap, dear, unfurnished = make_listing(rent_cc=500.0), make_listing(rent_cc=950.0), make_listing(rent_cc=550.0, furnished=False)
    for l in (cheap, dear, unfurnished):
        assert hard_filter(l, p) is True
    assert (cheap.match, dear.match, unfurnished.match) == (True, False, False)
    assert hard_filter(make_listing(rent_cc=1300.0), p) is False


def test_near_miss_tag_still_refers_to_the_owners_budget_when_the_net_is_wide(profile):
    p = wide(profile)  # budget 700, margin 50
    near, over = make_listing(rent_cc=720.0), make_listing(rent_cc=800.0)
    hard_filter(near, p)
    hard_filter(over, p)
    assert "near-miss" in near.tags and near.match is True and "near-miss" not in over.tags and over.match is False


def test_without_collect_nothing_changes_and_everything_matches(profile):
    l = make_listing(rent_cc=720.0)
    assert hard_filter(l, profile) is True and l.match is True and hard_filter(make_listing(rent_cc=900.0), profile) is False
