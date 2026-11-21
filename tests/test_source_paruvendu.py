from logement.sources.paruvendu import parse_html

CARD_1 = """
<div class="blocAnnonce border-1" data-id="1000000001" data-cdp="">
 <a href="/immobilier/location/appartement/1000000001A1KILHAP000" title=" Appartement - 1 pièce(s) - 24 m²">
  <img src="https://img.paruvendu.fr/_static_/x/transparent_1x1.png" id="firstImg" />
  <script> const el = document.getElementById('firstImg'); el.src = 'https://img.paruvendu.fr/media_ext/_https_/m/aa/p1.jpg?func=crop&w=320'; </script>
  <img src="https://img.paruvendu.fr/media_ext/_https_/m/bb/p2.jpg?func=crop&amp;w=320" />
  <span class="text-sm font-bold">4</span>
 </a>
 <!-- Prix --> <div> 550 &euro; <span class="f10">CC*</span> </div>
 <p>Studio meublé de 24m² proche des universités</p>
 <span class="pseudoinfo">Particulier</span> <p class="text-xs"><img src="x.svg">13/11/2026</p>
</div>
"""
CARD_2 = """
<div class="blocAnnonce border-1" data-id="1000000002" data-cdp="">
 <a href="/immobilier/location/appartement/1000000002A1KILHAP000" title=" Appartement - 2 pièce(s) - 35 m²">
  <span class="text-sm font-bold">9</span>
 </a>
 <!-- Prix --> <div> 1&nbsp;270 &euro; <span class="f10">HC</span> </div>
 <p>Appartement non meublé</p>
 <span class="pseudoinfo">Professionnel</span> <p class="text-xs"><img src="x.svg">12/11/2026</p>
</div>
"""


def test_parse_reads_a_private_cc_card():
    l = parse_html("<html>" + CARD_1 + CARD_2 + "</html>", max_photos=6)[0]
    assert l.source == "paruvendu" and l.source_id == "1000000001"
    assert l.url == "https://www.paruvendu.fr/immobilier/location/appartement/1000000001A1KILHAP000"
    assert (l.rent_cc, l.rooms, l.surface_m2) == (550, 1, 24.0)
    assert l.poster == "particulier" and l.published_at == "2026-11-13"
    assert l.furnished is True and l.tags == []
    assert l.photos == ["https://img.paruvendu.fr/media_ext/_https_/m/aa/p1.jpg?func=crop&w=320",
                        "https://img.paruvendu.fr/media_ext/_https_/m/bb/p2.jpg?func=crop&w=320"]
    assert "proche des universités" in l.description


def test_parse_reads_a_professional_hc_card_with_a_thousands_space():
    l = parse_html(CARD_2, max_photos=6)[0]
    assert l.rent_cc == 1270 and l.poster == "agence" and l.tags == ["hc?"]
    assert l.furnished is False and l.rooms == 2 and l.photos == []


def test_parse_caps_photos_and_handles_no_cards():
    assert len(parse_html(CARD_1, max_photos=1)[0].photos) == 1
    assert parse_html("<html></html>", max_photos=6) == []


CARD_PRO = """
<div class="blocAnnonce border-1" data-id="1000000003" data-cdp="">
 <a href="/immobilier/location/appartement/1000000003A1KILHAP000" title=" Appartement - 1 pièce(s) - 20 m²">
  <span class="text-sm font-bold">3</span>
 </a>
 <!-- Prix --> <div> 480 &euro; <span class="f10">CC*</span> </div>
 <img src="logo.png" alt="pro : agency.example.test" title="Toutes les annonces de agency.example.test" />
 <p class="text-xs"><img src="x.svg">10/11/2026</p>
</div>
"""


def test_professional_card_without_pseudoinfo_is_an_agency():
    assert parse_html(CARD_PRO, max_photos=6)[0].poster == "agence"


def test_card_with_neither_marker_has_unknown_poster():
    html = CARD_PRO.replace('alt="pro : agency.example.test"', 'alt="logo"')
    assert parse_html(html, max_photos=6)[0].poster is None


# ---- multi-page, area, furnished ----
import pytest
from logement.errors import Blocked
from logement.sources import paruvendu as pv


def test_page_url_appends_p_or_amp_p():
    assert pv.page_url("https://x.test/l/", 1) == "https://x.test/l/"
    assert pv.page_url("https://x.test/l/", 3) == "https://x.test/l/?p=3"
    assert pv.page_url("https://x.test/l/?a=1", 2) == "https://x.test/l/?a=1&p=2"


def _card(i, extra=""):
    return (f'<div class="blocAnnonce" data-id="{i}"><a href="/immobilier/location/a/{i}A" '
            f'title=" Appartement - 1 pièce(s) - 20 m²">x</a> <!-- Prix --> <div> 500 &euro; '
            f'<span>CC*</span></div> <p>{extra}</p></div>')


def _profile(**kw):
    p = {"max_photos": 3, "sources": {"paruvendu": {"urls": ["https://x.test/l/"], "deep_pages": 5}}}
    p.update(kw)
    return p


def _fake(monkeypatch, pages_by_n, blocked_at=None):
    calls = []

    def fake_get(url):
        calls.append(url)
        n = int(url.split("p=")[1]) if "p=" in url else 1
        if blocked_at == n:
            raise Blocked("HTTP 403")
        return "".join(pages_by_n[n])
    monkeypatch.setattr(pv, "_get", fake_get)
    monkeypatch.setattr(pv, "SLEEP", lambda s: None)
    monkeypatch.setattr(pv, "PAGE_SIZE", 2)
    return calls


def test_deep_collects_pages_and_stops_on_short_page(monkeypatch):
    calls = _fake(monkeypatch, {1: [_card(1), _card(2)], 2: [_card(2), _card(3)], 3: [_card(4)]})
    got = pv.fetch(_profile(deep=True))
    assert [l.source_id for l in got] == ["1", "2", "3", "4"]
    assert len(calls) == 3


def test_light_poll_fetches_page_one_only(monkeypatch):
    calls = _fake(monkeypatch, {1: [_card(1), _card(2)], 2: [_card(3)]})
    assert len(pv.fetch(_profile())) == 2 and len(calls) == 1


def test_legacy_single_url_still_works(monkeypatch):
    calls = _fake(monkeypatch, {1: [_card(1)]})
    p = {"max_photos": 3, "sources": {"paruvendu": {"url": "https://old.test/l/"}}}
    assert len(pv.fetch(p)) == 1 and calls == ["https://old.test/l/"]


def test_blocked_on_page_two_keeps_page_one(monkeypatch):
    _fake(monkeypatch, {1: [_card(1), _card(2)]}, blocked_at=2)
    assert [l.source_id for l in pv.fetch(_profile(deep=True))] == ["1", "2"]


def test_blocked_on_first_page_propagates(monkeypatch):
    _fake(monkeypatch, {}, blocked_at=1)
    with pytest.raises(Blocked):
        pv.fetch(_profile(deep=True))


@pytest.mark.parametrize("txt,district,postal", [
    ("20 m² Lyon 3 Appartement", "Lyon 3e", "69003"),
    ("20 m² Lyon 1er proche", "Lyon 1er", "69001"),
    ("20 m² Lyon 2e proche", "Lyon 2e", "69002"),
    ("20 m² Lyon 9 ", "Lyon 9e", "69009"),
])
def test_area_parsed_from_card(txt, district, postal):
    l = parse_html(_card(7, txt), max_photos=1)[0]
    assert (l.district, l.postal_code) == (district, postal)


def test_card_without_area_keeps_none():
    l = parse_html(_card(7, "Villeurbanne 20 m²"), max_photos=1)[0]
    assert l.district is None and l.postal_code is None


@pytest.mark.parametrize("txt,expected", [
    ("Appartement non meublé", False), ("non-meublé", False), ("logement vide", False),
    ("Studio meublé", True), ("rien", None), ("videoprojecteur", None),
])
def test_furnished_values(txt, expected):
    assert parse_html(_card(8, txt), max_photos=1)[0].furnished is expected
