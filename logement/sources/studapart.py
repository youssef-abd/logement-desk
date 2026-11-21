"""Studapart: its search page loads the listings with a request that refuses plain HTTP clients, so a real
headless Chrome opens the page the way a visitor does and this adapter reads the answer the page itself receives."""
import json
import re
from datetime import datetime, timezone

from ..errors import Blocked, DriftError
from ..listing import Listing

BASE = "https://www.studapart.com"
MEDIA = "https://media.studapart.com"


def _photos(media, max_photos):
    if isinstance(media, str):
        try:
            media = json.loads(media)
        except ValueError:
            return []
    out = []
    for m in media or []:
        url = None
        try:
            urls = json.loads(m.get("final_url") or "{}")
            url = next((u for k, u in urls.items() if k.endswith("_large")), None) or next(iter(urls.values()), None)
        except (ValueError, AttributeError):
            pass
        if not url and m.get("filesystem") and m.get("key"):
            url = f"{MEDIA}/{m['filesystem']}_large/{m['key']}"
        if url and url not in out:
            out.append(url)
        if len(out) >= max_photos:
            break
    return out


def parse_item(it, max_photos):
    path = (it.get("canonicalUrls") or {}).get("fr")
    ident, rent = it.get("distinctId"), it.get("rentWithExpensesAmount")
    if not (path and ident and rent):
        return None
    residence = it.get("ad_type") == "residence"
    address = str(it.get("full_address") or it.get("address") or "")
    postal = str(it.get("zipcode") or "") or (re.search(r"\b(\d{5})\b", address) or [None, ""])[1] or None
    city = str(it.get("city") or "").strip()
    district = f"Lyon {postal[4]}{'er' if postal[4] == '1' else 'e'}" if postal and postal.startswith("6900") and city.lower() == "lyon" else (city or None)
    agency = residence or it.get("lessorType") == "agency"
    created = it.get("createdAt")
    return Listing(
        source="studapart", source_id=str(ident), url=BASE + path, title=str(it.get("title") or it.get("residenceName") or "").strip(),
        rent_cc=float(rent), surface_m2=float(it["propertySurface"]) if it.get("propertySurface") else None,
        rooms=int(it["roomsCount"]) if it.get("roomsCount") else None, district=district, postal_code=postal,
        furnished=it.get("isFurnished") if isinstance(it.get("isFurnished"), bool) else None,
        poster="agence" if agency else "particulier",
        poster_name=(str(it.get("residenceName") or it.get("ownerName") or "") or None) if agency else None,
        published_at=datetime.fromtimestamp(created, timezone.utc).isoformat(timespec="seconds") if created and not residence else None,
        description=re.sub(r"\s+", " ", str(it.get("description") or "")).strip()[:600], photos=_photos(it.get("media"), max_photos),
        tags=["residence"] if residence else [],
    )


def parse_response(data, max_photos):
    out = []
    for it in (data or {}).get("results") or []:
        l = parse_item(it, max_photos)
        if l:
            out.append(l)
    return out


def _load(url, scrolls, launch):
    from playwright.sync_api import sync_playwright

    answers = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch)
        try:
            page = browser.new_page(locale="fr-FR")

            def on_response(r):
                if r.request.method == "POST" and r.url.endswith("/property"):
                    try:
                        answers.append(r.json())
                    except Exception:
                        pass

            page.on("response", on_response)
            resp = page.goto(url, wait_until="networkidle", timeout=60000)
            if resp is not None and resp.status in (403, 429, 503):
                raise Blocked(f"HTTP {resp.status}")
            for _ in range(scrolls):
                if not answers or answers[-1].get("isLastPage", True):
                    break
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(1500)
        finally:
            browser.close()
    return answers


def fetch(profile):
    opts = profile["sources"]["studapart"]
    out, seen = [], set()
    for n, url in enumerate(opts["urls"]):
        answers = _load(url, opts.get("scrolls", 4), opts.get("launch", {}))
        if not answers:
            if n == 0 and not out:
                raise DriftError("the page made no listing request")  # the site changed: a parser problem, not an empty market
            continue
        for a in answers:
            for l in parse_response(a, profile["max_photos"]):
                if l.source_id not in seen:
                    seen.add(l.source_id)
                    out.append(l)
    return out
