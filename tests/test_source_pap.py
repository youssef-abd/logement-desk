import pytest

from logement import relay
from logement.errors import Blocked
from logement.sources import pap
from logement.sources.pap import page_url, parse_html

CARD = """<div class="col-1-3"><div class="search-list-item-alt">
<div class="owl-carousel"><div><img src="https://cdn.pap.fr/photos/pap/aa/1.webp"></div><div><img src="https://cdn.pap.fr/photos/pap/bb/2.webp"></div></div>
<a href="/annonces/appartement-lyon-3e-69003-r111" class="item-thumb-link"></a>
<div class="item-body"><a class="item-title" href="/annonces/appartement-lyon-3e-69003-r111" name="111">
<div class="item-price-container"><span class="item-price txt-purple">\n 1.125&nbsp;&euro; </span></div>
<span class="h1">\n Lyon 3E (69003) </span>
<ul class="item-tags"><li>2&nbsp;pièces</li><li>1&nbsp;chambre</li><li>45&nbsp;m²</li></ul></a>
<p class="item-description">Beau studio meublé près de la Part-Dieu.</p></div></div></div>"""
CARD_2 = (CARD.replace("r111", "r222").replace("1.125", "620").replace("Lyon 3E (69003)", "Lyon 5E")
          .replace("2&nbsp;pièces", "1&nbsp;pièce").replace("meublé", "calme"))


def test_parse_reads_a_card():
    [l] = parse_html("<html>" + CARD + "</html>", max_photos=3)
    assert (l.source, l.source_id, l.rent_cc, l.surface_m2, l.rooms) == ("pap", "111", 1125, 45, 2)
    assert l.url == "https://www.pap.fr/annonces/appartement-lyon-3e-69003-r111"
    assert l.district == "Lyon 3e" and l.postal_code == "69003" and l.poster == "particulier" and l.furnished is True
    assert l.photos == ["https://cdn.pap.fr/photos/pap/aa/1.webp", "https://cdn.pap.fr/photos/pap/bb/2.webp"]


def test_parse_fills_gaps_dedupes_and_ignores_pages_without_cards():
    ls = parse_html("<html>" + CARD + CARD_2 + CARD + "</html>", 3, furnished_search=True)
    assert [x.source_id for x in ls] == ["111", "222"]
    assert ls[1].rent_cc == 620 and ls[1].postal_code == "69005" and ls[1].district == "Lyon 5e" and ls[1].rooms == 1
    assert ls[1].furnished is True  # not stated on the card: the search asked for furnished
    assert parse_html("<html></html>", 3) == []


def test_page_url():
    assert page_url("https://x/lyon-g1", 1) == "https://x/lyon-g1" and page_url("https://x/lyon-g1", 3) == "https://x/lyon-g1-3"


def profile(deep):
    return {"max_photos": 3, "deep": deep, "sources": {"pap": {"urls": ["https://x/meuble-lyon-g1"], "deep_pages": 5}}}


def test_fetch_light_reads_one_page_and_deep_stops_when_a_page_adds_nothing(monkeypatch):
    calls = []
    pages = {"https://x/meuble-lyon-g1": CARD, "https://x/meuble-lyon-g1-2": CARD_2, "https://x/meuble-lyon-g1-3": CARD_2}
    monkeypatch.setattr(relay, "get", lambda url: calls.append(url) or pages[url])
    monkeypatch.setattr(pap, "SLEEP", lambda s: None)
    assert len(pap.fetch(profile(False))) == 1 and calls == ["https://x/meuble-lyon-g1"]
    calls.clear()
    assert len(pap.fetch(profile(True))) == 2 and len(calls) == 3


def test_blocked_on_the_first_page_raises_but_later_pages_keep_what_was_read(monkeypatch):
    def first_blocked(url):
        raise Blocked("403")
    monkeypatch.setattr(relay, "get", first_blocked)
    with pytest.raises(Blocked):
        pap.fetch(profile(False))

    def second_blocked(url):
        if url.endswith("-2"):
            raise Blocked("403")
        return CARD
    monkeypatch.setattr(relay, "get", second_blocked)
    monkeypatch.setattr(pap, "SLEEP", lambda s: None)
    assert len(pap.fetch(profile(True))) == 1


def test_relay_without_config_counts_as_blocked(monkeypatch):
    monkeypatch.delenv("DESK_URL", raising=False)
    monkeypatch.delenv("PUSH_TOKEN", raising=False)
    with pytest.raises(Blocked):
        relay.get("https://www.pap.fr/x")
