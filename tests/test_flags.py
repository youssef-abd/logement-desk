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
