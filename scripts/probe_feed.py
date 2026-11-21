"""One-off: capture Studapart's listing request in Chrome, then replay it with plain HTTP and summarise the items."""
import json
import urllib.request
from playwright.sync_api import sync_playwright

URL = "https://www.studapart.com/fr/location-studio-lyon"
cap = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(locale="fr-FR")

    def on_req(r):
        if r.url.endswith("/property") and r.method == "POST" and "body" not in cap:
            cap["url"], cap["body"], cap["headers"] = r.url, r.post_data, dict(r.headers)

    page.on("request", on_req)
    page.goto(URL, wait_until="networkidle", timeout=60000)
    b.close()
body = cap["body"]
print("BODY length", len(body))
for i in range(0, min(len(body), 9000), 1500):
    print("BODY", i, body[i:i + 1500])
print("HEADERS", {k: v for k, v in cap["headers"].items() if k.lower() in ("origin", "referer", "content-type")})
req = urllib.request.Request(cap["url"], data=body.encode(), headers={"content-type": "application/json", "accept": "application/json"})
try:
    d = json.load(urllib.request.urlopen(req, timeout=30))
    items = d.get("results", [])
    print("REPLAY plain http ok: items", len(items), "nbHits", d.get("nbHits"), "last", d.get("isLastPage"))
    for it in items[:5]:
        print("ITEM", json.dumps({k: it.get(k) for k in ("ad_type", "propertyType", "announcementType", "rentWithExpensesAmount", "rentWithExpensesAmountFullAccommodation", "propertySurface", "roomsCount", "isFurnished", "ownerName", "residenceName", "address", "onlineAt", "createdAt")}, ensure_ascii=False), (it.get("canonicalUrls") or {}).get("fr"), str(it.get("media"))[:150])
    print("ad types:", {t: sum(1 for x in items if x.get("ad_type") == t) for t in {x.get("ad_type") for x in items}})
except Exception as e:
    print("REPLAY failed", type(e).__name__, str(e)[:150])
