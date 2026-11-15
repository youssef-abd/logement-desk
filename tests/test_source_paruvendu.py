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
    assert l.furnished is None and l.rooms == 2 and l.photos == []


def test_parse_caps_photos_and_handles_no_cards():
    assert len(parse_html(CARD_1, max_photos=1)[0].photos) == 1
    assert parse_html("<html></html>", max_photos=6) == []
