from logement.errors import Blocked
from logement.sources import foncia
from logement.sources.foncia import page_url, parse_html

CARD = """
<app-annonce-card _ngcontent-sc1="" class="large"><div _ngcontent-sc190="" class="foncia-card" tabindex="0">
 <!----><div class="gallery"><a class="gallery-container" href="/location/lyon-69003/appartement-meuble/331724968.htm">
 <img alt="appartement-meuble 1 pièce à louer Lyon 3ᵉ 69003 37.13 m²" class="ng-star-inserted" src="https://cdn.example.test/annonces/aa/lg.jpeg"></a></div>
 <div class="foncia-card-content"><div class="foncia-card-content-left">
  <p _ngcontent-sc193="" class="foncia-card-price"><span _ngcontent-sc193="">715 €</span><!----><sup class="ng-star-inserted">/ mois CC</sup></p>
  <a class="foncia-card-title-small ng-star-inserted" href="/location/lyon-69003/appartement-meuble/331724968.htm"><span><span class="foncia-card-title-small-title">Location Studio meublé 37.13 m² - Lyon 69003</span></span><span class="foncia-card-surface ng-star-inserted"> 37,13 m² </span></a>
  <span><p class="foncia-card-place">Lyon (69003)</p></span></div>
 <div class="foncia-card-content-right"><p class="foncia-card-description ng-star-inserted">20 RUE EXAMPLE - LYON 3 VISITE VIRTUELLE UNIQUEMENT</p></div></div></div></app-annonce-card>
"""
CARD_2 = CARD.replace("331724968", "331700001").replace("715 €", "1&nbsp;120 €").replace("CC", "HC").replace("Lyon (69003)", "Villeurbanne (69100)").replace("Studio meublé 37.13", "Appartement meublé 2 pièces 45").replace("1 pièce à louer", "2 pièces à louer").replace("37,13", "45")


def test_parse_reads_a_card():
    [l] = parse_html("<html>" + CARD + "</html>", max_photos=3)
    assert l.source == "foncia" and l.source_id == "331724968"
    assert l.url == "https://fr.foncia.com/location/lyon-69003/appartement-meuble/331724968.htm"
    assert (l.rent_cc, l.surface_m2, l.rooms) == (715, 37.13, 1)
    assert l.postal_code == "69003" and l.district == "Lyon 3e" and l.furnished is True
    assert l.poster == "agence" and l.poster_name == "Foncia" and l.tags == []
    assert l.photos == ["https://cdn.example.test/annonces/aa/lg.jpeg"] and "VISITE VIRTUELLE" in l.description


def test_parse_handles_hc_prices_other_cities_and_duplicates():
    ls = parse_html("<html>" + CARD + CARD_2 + CARD + "</html>", max_photos=3)
    assert [x.source_id for x in ls] == ["331724968", "331700001"]
    assert ls[1].rent_cc == 1120 and ls[1].tags == ["hc?"] and ls[1].district == "Villeurbanne" and ls[1].postal_code == "69100" and ls[1].rooms == 2
    assert parse_html("<html></html>", 3) == []


def test_page_url():
    assert page_url("https://x/lyon", 1) == "https://x/lyon" and page_url("https://x/lyon", 3) == "https://x/lyon?page=3"
    assert page_url("https://x/lyon?a=1", 2) == "https://x/lyon?a=1&page=2"


def profile(deep):
    return {"max_photos": 3, "deep": deep, "sources": {"foncia": {"urls": ["https://x/a"], "deep_pages": 5}}}


def test_fetch_light_reads_one_page_and_deep_stops_when_a_page_adds_nothing(monkeypatch):
    calls = []
    pages = {"https://x/a": CARD, "https://x/a?page=2": CARD_2, "https://x/a?page=3": CARD_2}

    def fake_get(url):
        calls.append(url)
        return pages[url]
    monkeypatch.setattr(foncia, "_get", fake_get)
    monkeypatch.setattr(foncia, "SLEEP", lambda s: None)
    assert len(foncia.fetch(profile(False))) == 1 and calls == ["https://x/a"]
    calls.clear()
    assert len(foncia.fetch(profile(True))) == 2 and calls == ["https://x/a", "https://x/a?page=2", "https://x/a?page=3"]


def test_blocked_after_the_first_page_keeps_the_pages_already_read(monkeypatch):
    def fake_get(url):
        if url.endswith("page=2"):
            raise Blocked("403")
        return CARD
    monkeypatch.setattr(foncia, "_get", fake_get)
    monkeypatch.setattr(foncia, "SLEEP", lambda s: None)
    assert len(foncia.fetch(profile(True))) == 1
