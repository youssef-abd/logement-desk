import json

from logement.sources.lacartedescolocs import parse_html

ITEM = {
    "@type": "RealEstateListing", "url": "https://www.example.test/colocations/city/a/abc123",
    "name": "Appartement 3 pièces de 80 m²", "image": "https://img.example.test/1.jpg",
    "about": {"@type": "Room", "address": {"@type": "PostalAddress", "addressLocality": "City"},
              "floorSize": {"@type": "QuantitativeValue", "value": 80}},
    "offers": {"@type": "Offer", "price": 580, "availabilityStarts": "2026-12-14"},
}


def page(*blocks):
    return "<html>" + "".join(f'<script type="application/ld+json">{b}</script>' for b in blocks) + "</html>"


def test_parse_reads_listings_nested_in_a_result_list():
    data = {"@type": "SearchResultsPage", "mainEntity": {"@type": "ItemList",
            "itemListElement": [{"@type": "ListItem", "position": 1, "item": ITEM}]}}
    [l] = parse_html(page(json.dumps(data)), max_photos=6)
    assert l.source == "lacartedescolocs" and l.source_id == "abc123" and l.kind == "coloc"
    assert l.url == ITEM["url"] and l.rent_cc == 580 and l.surface_m2 == 80 and l.district == "City"
    assert "2026-12-14" in l.description and l.photos == ["https://img.example.test/1.jpg"]


def test_parse_skips_duplicates_and_invalid_json():
    html = page("{not json", json.dumps([ITEM, ITEM]))
    assert len(parse_html(html, max_photos=6)) == 1
    assert parse_html("<html></html>", max_photos=6) == []
