"""One-off: render JavaScript-heavy listing pages in headless Chrome and report what they hold. Counts and short samples only."""
import re
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

PAGES = {
    "locservice": "https://www.locservice.fr/location-lyon.html",
    "appartager": "https://www.appartager.com/colocations/lyon",
}
with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, url in PAGES.items():
        page = browser.new_page(locale="fr-FR")
        feeds = []
        page.on("response", lambda r: feeds.append((urlparse(r.url).netloc + urlparse(r.url).path, r.headers.get("content-type", "")))
                if "json" in r.headers.get("content-type", "") else None)
        try:
            resp = page.goto(url, wait_until="networkidle", timeout=45000)
            status = resp.status if resp else None
        except Exception as e:
            print(name, "ERROR", type(e).__name__)
            continue
        page.wait_for_timeout(2500)
        blocks = page.evaluate("""() => [...document.querySelectorAll('article, li, div, a')]
            .filter(e => { const t = e.innerText || ''; return t.length > 30 && t.length < 500 && /€/.test(t) && /(m²|m2|chambre|pièce)/i.test(t) && e.children.length < 40; })
            .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())""")
        uniq = list(dict.fromkeys(blocks))
        links = page.evaluate("""() => [...new Set([...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href')).filter(h => /\\d{5,}/.test(h)))].length""")
        title = page.title()[:70]
        print(f"{name}: http {status} | title={title!r} | listing-like blocks={len(uniq)} | links with ids={links} | json responses={len(feeds)}")
        for s in uniq[:3]:
            print("   sample:", s[:170])
        for f in list(dict.fromkeys(feeds))[:8]:
            print("   json feed:", f[0][:110])
        page.close()
    browser.close()
