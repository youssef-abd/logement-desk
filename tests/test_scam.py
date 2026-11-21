from logement.scam import risk, signals


def L(**kw):
    base = dict(title="Studio", description="", poster="particulier", postal_code="69003", photos=[])
    base.update(kw)
    return base


def reasons(d, key):
    return [w for _, w in d.get(key, [])]


def test_text_signals():
    d = signals([
        ("a", L(description="Merci de verser la caution avant la visite")),
        ("b", L(description="Les clés vous seront envoyées par la poste")),
        ("c", L(description="Je suis propriétaire et je vis à l'étranger")),
        ("d", L(description="Écrivez-moi sur WhatsApp au plus vite")),
        ("e", L(description="Paiement par Western Union")),
        ("f", L(description="Joli studio lumineux proche métro, visite possible le week-end")),
    ])
    assert reasons(d, "a") == ["asks for money before a visit"]
    assert reasons(d, "b") == ["keys sent by post"]
    assert reasons(d, "c") == ["owner abroad"]
    assert reasons(d, "d") == ["contact outside the site"]
    assert reasons(d, "e") == ["money-transfer wording"]
    assert "f" not in d


def test_email_only_counts_for_private_posters():
    text = "Contact: agence@example.test pour visiter"
    assert reasons(signals([("p", L(description=text))]), "p") == ["contact by e-mail only"]
    assert "x" not in signals([("x", L(description=text, poster="agence"))])


LONG = "Magnifique studio meublé entièrement rénové, idéalement situé, libre de suite, loyer charges comprises, contactez-nous vite pour une visite"


def test_same_text_flags_when_a_private_poster_is_involved_but_not_agency_templates():
    d = signals([("a", L(description=LONG)), ("b", L(description=LONG, postal_code="69007"))])
    assert reasons(d, "a") == ["same text on 1 other listing(s)"] and reasons(d, "b") == ["same text on 1 other listing(s)"]
    assert signals([("x", L(description=LONG, poster="agence")), ("y", L(description=LONG, poster="agence"))]) == {}
    assert signals([("s1", L(description="court")), ("s2", L(description="court"))]) == {}


def test_same_photo_in_another_area():
    ph = ["https://img.example.test/p1.jpg?w=320"]
    d = signals([("a", L(photos=ph)), ("b", L(photos=["https://img.example.test/p1.jpg?w=800"], postal_code="69007"))])
    assert reasons(d, "a") == ["same photo used in another area"] and "b" in d
    same_area = signals([("a", L(photos=ph)), ("b", L(photos=ph))])
    assert same_area == {}


def test_risk_levels():
    assert risk([]) == (None, [])
    assert risk([(2, "x")]) == ("check", ["x"])
    assert risk([(2, "x"), (2, "y")]) == ("high", ["x", "y"])
    assert risk([], too_cheap=True) == ("check", ["price under half the area median"])
    assert risk([(3, "keys sent by post")], too_cheap=True)[0] == "high"
