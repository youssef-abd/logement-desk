from logement.listing import Listing


def make_listing(**kw):
    base = dict(
        source="bienici", source_id="a1", url="https://example.test/a1", title="Studio",
        rent_cc=500.0, charges=40.0, surface_m2=20.0, rooms=1, district="City 3e", postal_code="69003",
        furnished=True, poster="particulier", published_at="2026-11-15T10:00:00+00:00",
        description="", photos=[],
    )
    base.update(kw)
    return Listing(**base)
