import pytest

from logement.errors import Blocked
from logement.sources import immojeune
from logement.sources.immojeune import parse_list, parse_residence

PRIVATE = """<div class="card col"><div class="slick-card"><div class="img-slick" data-background="https://www.immojeune.com/uploads/housing/a.jpeg"></div></div>
<div class="content"><div class="flex"><span class="badge badge-cyan"><img src="/i.svg" alt="Boost"> PARTICULIER </span><span class="badge badge-light"> STUDIO </span></div>
<p class="title"><a href="/location-etudiant/lyon-69/studio-500-metres-universite-lyon-3_3809807.html"> STUDIO 500 mètres Université LYON 3 </a></p>
<p class="description"></p><p> 18 m² - 625 €<sup>CC</sup> </p>
<div class="geo"><img src="/g.svg" alt="Ville">&nbsp;69000 Lyon </div></div></div>"""
RESIDENCE = """<div class="card col"><div class="content"><div class="flex"><span class="badge badge-light"> RÉSIDENCE ÉTUDIANTE </span><span class="badge badge-light"> STUDIO </span></div>
<p class="title"><a href="/residence-etudiante/lyon-09-69/studea-lyon-vaise_66788.html"> Studéa Lyon Vaise : Studio </a></p></div></div>"""
OUT_OF_TOWN = PRIVATE.replace("3809807", "2950561").replace("69000 Lyon", "42000 Saint-Étienne").replace("625", "399")
PAGE = """<html><h1 class="x"> Studéa Lyon Vaise </h1><p>Meublés et aménagés avec style.</p><p>69009 Lyon</p>
<select id="candidate_advert"><option value="">Choisir</option><option value="3998740" selected="selected">Studio : 17 – 23 m² - 563 €</option>
<option value="3998741">T2 : 38 m² - 810 €</option></select></html>"""


def test_list_reads_private_ads_and_collects_residence_pages_without_double_counting():
    ads, res = parse_list("<html>" + PRIVATE + RESIDENCE + RESIDENCE + OUT_OF_TOWN + "</html>", 3)
    assert [a.source_id for a in ads] == ["3809807", "2950561"]
    a = ads[0]
    assert (a.rent_cc, a.surface_m2, a.rooms, a.poster, a.district, a.postal_code) == (625, 18, 1, "particulier", "Lyon", "69000")
    assert a.url.startswith("https://www.immojeune.com/location-etudiant/lyon-69/") and a.photos == ["https://www.immojeune.com/uploads/housing/a.jpeg"]
    assert list(res) == ["/residence-etudiante/lyon-09-69/studea-lyon-vaise_66788.html"]


def test_residence_page_gives_one_listing_per_unit_with_its_rent():
    units = parse_residence(PAGE, "https://www.immojeune.com/residence-etudiante/lyon-09-69/studea-lyon-vaise_66788.html", 3, ["https://p/1.jpg"])
    assert [(u.source_id, u.rent_cc, u.surface_m2, u.rooms) for u in units] == [("u3998740", 563, 17, 1), ("u3998741", 810, 38, 2)]
    u = units[0]
    assert u.district == "Lyon 9e" and u.postal_code == "69009" and u.furnished is True and u.poster == "agence" and u.poster_name == "Studéa Lyon Vaise" and u.photos == ["https://p/1.jpg"]
    assert parse_residence("<html></html>", "https://x/residence-etudiante/lyon-09-69/a_1.html", 3) == []


def profile(deep):
    return {"max_photos": 3, "deep": deep, "sources": {"immojeune": {"urls": ["/a.html"], "max_residences": 5}}}


def test_light_run_reads_lists_only_deep_run_also_reads_residence_pages(monkeypatch):
    calls = []
    pages = {"/a.html": "<html>" + PRIVATE + RESIDENCE + "</html>", "/residence-etudiante/lyon-09-69/studea-lyon-vaise_66788.html": PAGE}
    monkeypatch.setattr(immojeune, "_get", lambda u: calls.append(u) or pages[u])
    monkeypatch.setattr(immojeune, "SLEEP", lambda s: None)
    assert len(immojeune.fetch(profile(False))) == 1 and calls == ["/a.html"]
    calls.clear()
    assert len(immojeune.fetch(profile(True))) == 3 and len(calls) == 2


def test_deep_run_follows_the_next_link_and_stops_when_a_page_adds_nothing(monkeypatch):
    nxt = lambda n: f'<link rel="next" href="/x/{n}">'
    other = RESIDENCE.replace("66788", "66799")
    pages = {"/a.html": "<html>" + nxt(2) + PRIVATE + RESIDENCE + "</html>", "https://www.immojeune.com/x/2": "<html>" + nxt(3) + other + "</html>",
             "https://www.immojeune.com/x/3": "<html>" + nxt(4) + other + "</html>"}
    calls = []
    monkeypatch.setattr(immojeune, "_get", lambda u: calls.append(u) or (pages.get(u) or PAGE))
    monkeypatch.setattr(immojeune, "SLEEP", lambda s: None)
    immojeune.fetch(profile(True))
    assert calls[:3] == ["/a.html", "https://www.immojeune.com/x/2", "https://www.immojeune.com/x/3"] and not any("/x/4" in c for c in calls)
    calls.clear()
    immojeune.fetch(profile(False))
    assert calls == ["/a.html"]


def test_blocked_first_list_raises_but_a_blocked_residence_page_keeps_the_rest(monkeypatch):
    def blocked(u):
        raise Blocked("403")
    monkeypatch.setattr(immojeune, "_get", blocked)
    with pytest.raises(Blocked):
        immojeune.fetch(profile(True))

    def residence_blocked(u):
        if "residence" in u:
            raise Blocked("403")
        return "<html>" + PRIVATE + RESIDENCE + "</html>"
    monkeypatch.setattr(immojeune, "_get", residence_blocked)
    monkeypatch.setattr(immojeune, "SLEEP", lambda s: None)
    assert len(immojeune.fetch(profile(True))) == 1
