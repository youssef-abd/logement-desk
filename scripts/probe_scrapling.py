"""One-off: can Scrapling's stealth browser read sites that block plain requests from a GitHub runner? Counts only."""
import re
from scrapling.fetchers import StealthyFetcher

PAGES = {
    "leboncoin": "https://www.leboncoin.fr/recherche?category=10&locations=Lyon_69000&furnished=1&price=0-700",
    "pap": "https://www.pap.fr/annonce/location-appartement-lyon-69-g43590",
    "seloger": "https://www.seloger.com/immobilier/locations/immo-lyon-69/",
    "foncia": "https://fr.foncia.com/location/lyon-69",
}
for name, url in PAGES.items():
    try:
        r = StealthyFetcher.fetch(url, headless=True, network_idle=True, timeout=60000)
        html = str(r.html_content) if hasattr(r, "html_content") else str(r.body)
        text = re.sub(r"<[^>]+>", " ", html)
        title = (r.css("title::text").get() or "")[:70]
        print(f"{name}: http {r.status} | title={title!r} | html={len(html)} | euro mentions={text.count('€')} | m2 mentions={len(re.findall(r'm²|m2', text))}")
    except Exception as e:
        print(name, "ERROR", type(e).__name__, str(e)[:100])
