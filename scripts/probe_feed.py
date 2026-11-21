"""One-off: list the JSON/XHR calls Studapart's Lyon page makes, to find its listing feed. Paths and key names only."""
import json
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = "https://www.studapart.com/fr/location-studio-lyon"
seen = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(locale="fr-FR")

    def on_resp(r):
        ct = r.headers.get("content-type", "")
        if "json" in ct and r.request.resource_type in ("xhr", "fetch"):
            try:
                body = r.text()
            except Exception:
                body = ""
            seen.append((r.request.method, r.url, r.status, len(body), body[:2000000]))
            if r.url.endswith('/property'):
                print('PROPERTY request headers:', {k: v for k, v in r.request.headers.items() if k.lower() in ('content-type', 'origin', 'accept')})
                print('PROPERTY request body:', (r.request.post_data or '')[:1500])
                try:
                    d = json.loads(body)
                    print('PROPERTY top:', (list(d.keys()) if isinstance(d, dict) else type(d).__name__))
                    items = d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])
                    print('PROPERTY items:', len(items))
                    if items:
                        print('PROPERTY item keys:', list(items[0].keys())[:60])
                        print('PROPERTY item sample:', json.dumps(items[0], ensure_ascii=False)[:1800])
                except Exception as e:
                    print('PROPERTY parse error', e)

    page.on("response", on_resp)
    page.goto(URL, wait_until="networkidle", timeout=60000)
    for _ in range(4):
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(1200)
    cards = page.evaluate("""() => [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href')).filter(h => /\/(annonce|logement|location|listing|housing)[^ ]*[0-9]{3,}/.test(h)).length""")
    print("rendered links with ids:", cards, "| json calls:", len(seen))
    for m, u, s, n, body in seen:
        pu = urlparse(u)
        keys = ""
        try:
            d = json.loads(body)
            keys = (list(d.keys())[:8] if isinstance(d, dict) else f"list[{len(d)}]")
        except Exception:
            keys = "?"
        print(m, s, n, pu.netloc + pu.path, ("?" + pu.query[:90]) if pu.query else "", keys)
    b.close()
