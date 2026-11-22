import json
import urllib.error

import pytest

from factories import make_listing
from logement import liveness, store
from logement.dedupe import process
from logement.errors import Blocked
from logement.liveness import check, sweep

NOW = "2026-11-22T12:00:00+00:00"
EARLIER = "2026-11-22T00:00:00+00:00"


def listing(source, sid, url, **kw):
    return {**make_listing(source=source, source_id=sid, url=url, **kw).to_dict(), "id": f"{source}:{sid}"}


def page(status=200, final=None, text=""):
    return lambda url: (status, final or url, text)


def ad(on):
    return json.dumps({"status": {"onTheMarket": on, "closedByUser": False}})


def test_bienici_says_gone_when_the_ad_is_off_the_market():
    l = listing("bienici", "ad-1", "https://www.bienici.com/annonce/location/lyon/ad-1")
    seen = []
    assert check(l, lambda u: seen.append(u) or (200, u, ad(False))) == "gone"
    assert seen == ["https://www.bienici.com/realEstateAd.json?id=ad-1"]
    assert check(l, page(text=ad(True))) == "live"
    assert check(l, page(404)) == "gone"
    assert check(l, page(text="not json")) == "unknown" and check(l, page(text="{}")) == "unknown"


def test_immojeune_redirects_away_and_residence_units_that_disappear_are_gone():
    private = listing("immojeune", "3809807", "https://www.immojeune.com/location-etudiant/lyon-69/studio_3809807.html")
    assert check(private, page(final="https://www.immojeune.com/logement-etudiant/lyon-06-69.html")) == "gone"
    assert check(private, page()) == "live" and check(private, page(404)) == "gone" and check(private, page(500)) == "unknown"
    unit = listing("immojeune", "u3998740", "https://www.immojeune.com/residence-etudiante/lyon-09-69/studea_66788.html")
    assert check(unit, page(text='<option value="3998740">Studio</option>')) == "live"
    assert check(unit, page(text='<option value="999">T2</option>')) == "gone"


def test_other_sites_are_gone_only_on_a_404_or_a_redirect_to_another_page():
    l = listing("paruvendu", "1", "https://www.paruvendu.fr/immobilier/location/x/1A")
    assert check(l, page()) == "live" and check(l, page(410)) == "gone" and check(l, page(500)) == "unknown"
    assert check(l, page(final="https://www.paruvendu.fr/immobilier/location/")) == "gone"
    assert check(l, page(final="https://www.paruvendu.fr/immobilier/location/x/1A/")) == "live"  # a trailing slash is not a move


def test_foncia_goes_through_the_relay(monkeypatch):
    l = listing("foncia", "9", "https://fr.foncia.com/location/lyon-69003/appartement/9.htm")
    monkeypatch.setattr(liveness.relay, "get", lambda u: "<html>")
    assert check(l) == "live"
    def gone(u):
        raise urllib.error.HTTPError(u, 404, "nf", {}, None)
    monkeypatch.setattr(liveness.relay, "get", gone)
    assert check(l) == "gone"
    def blocked(u):
        raise Blocked("403")
    monkeypatch.setattr(liveness.relay, "get", blocked)
    assert check(l) == "unknown"


def test_unknown_sources_and_blocks_are_never_guessed_gone():
    assert check(listing("leboncoin", "1", "https://www.leboncoin.fr/ad/1"), page(404)) == "unknown"
    def blocked(url):
        raise Blocked("403")
    assert check(listing("paruvendu", "1", "https://x/1"), blocked) == "unknown"
    def boom(url):
        raise RuntimeError("network")
    assert check(listing("paruvendu", "1", "https://x/1"), boom) == "unknown"


def entry(source, sid, status="active", checked=None, first="2026-11-20T00:00:00+00:00", dup_of=None):
    l = make_listing(source=source, source_id=sid, url=f"https://www.paruvendu.fr/{sid}").to_dict()
    return {"listing": None if dup_of else l, "status": status, "first_seen": first, "last_seen": EARLIER, "dup_of": dup_of, "also": [], "notified": True, "checked": checked}


def test_sweep_checks_the_least_recently_checked_first_and_closes_what_is_gone(profile):
    state = store.empty()
    state["listings"] = {
        "paruvendu:new": entry("paruvendu", "new"), "paruvendu:old": entry("paruvendu", "old", checked="2026-11-21T00:00:00+00:00"),
        "paruvendu:fresh": entry("paruvendu", "fresh", checked="2026-11-22T11:00:00+00:00"),  # checked an hour ago: not due
        "paruvendu:closed": entry("paruvendu", "closed", status="stale"), "paruvendu:dup": entry("paruvendu", "dup", dup_of="paruvendu:new"),
        "leboncoin:l": entry("leboncoin", "l"),
    }
    profile["liveness"] = {"max_per_run": 2, "recheck_hours": 6}
    asked = []
    def probe(url):
        asked.append(url)
        return (404, url, "") if url.endswith("/old") else (200, url, "")
    out = sweep(state, NOW, profile, probe=probe, sleep=lambda s: None)
    assert out == {"checked": 2, "gone": 1, "unknown": 0}
    assert asked == ["https://www.paruvendu.fr/new", "https://www.paruvendu.fr/old"]  # never checked comes first, then the oldest check
    L = state["listings"]
    assert L["paruvendu:old"]["status"] == "stale" and L["paruvendu:old"]["gone"] == NOW and L["paruvendu:new"]["checked"] == NOW
    assert L["paruvendu:new"]["status"] == "active" and L["paruvendu:fresh"]["checked"] == "2026-11-22T11:00:00+00:00"
    assert L["leboncoin:l"].get("checked") is None and L["paruvendu:dup"].get("checked") is None


def test_sweep_can_be_switched_off_and_a_gone_listing_that_reappears_revives(profile):
    state = store.empty()
    state["listings"] = {"paruvendu:a": entry("paruvendu", "a")}
    profile["liveness"] = {"enabled": False}
    assert sweep(state, NOW, profile, probe=page(404), sleep=lambda s: None) == {"checked": 0, "gone": 0, "unknown": 0}
    profile["liveness"] = {}
    sweep(state, NOW, profile, probe=page(404), sleep=lambda s: None)
    e = state["listings"]["paruvendu:a"]
    assert e["status"] == "stale" and e["gone"]
    process(state, [make_listing(source="paruvendu", source_id="a", url="https://www.paruvendu.fr/a")], {"paruvendu"}, NOW, profile)
    assert e["status"] == "active" and "gone" not in e


def test_a_redirect_to_a_login_page_is_not_proof_that_the_ad_is_gone():
    l = listing("studapart", "p1", "https://www.studapart.com/fr/logement-Lyon/Studio/property/abc")
    assert check(l, page(final="https://www.studapart.com/fr/login")) == "unknown"
    assert check(listing("immojeune", "55", "https://www.immojeune.com/x_55.html"), page(final="https://www.immojeune.com/login")) == "unknown"


def test_la_carte_des_colocs_deactivated_ads_answer_410_with_a_banner():
    l = listing("lacartedescolocs", "jbg8fq", "https://www.lacartedescolocs.fr/colocations/x/jbg8fq")
    banner = "<h1>Erreur 410</h1><p>Cette annonce a été désactivée le 22/11/2026 , son propriétaire semble avoir reçu suffisamment de candidatures.</p>"
    assert check(l, page(410, text=banner)) == "gone"
    assert check(l, page(200, text=banner)) == "gone"  # even if the site stops sending the 410
    assert check(l, page(200, text="<h1>Appartement 3 pièces</h1><p>3 chambres disponibles</p>")) == "live"
    assert check(l, page(500)) == "unknown"
