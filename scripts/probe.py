"""One-off probe: can each source be reached from this machine (GitHub Actions runner)?
Prints status codes, sizes and counts only. Never stores listing data. Always exits 0.
"""
import json, re, sys, urllib.request, urllib.error, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def row(name, status, detail):
    print(f"{name:22} {status:<8} {detail}", flush=True)


def bienici():
    filters = {"size": 24, "from": 0, "filterType": "rent", "propertyType": ["flat"], "maxPrice": 600, "furnished": True,
               "sortBy": "publicationDate", "sortOrder": "desc", "zoneIdsByTypes": {"zoneIds": ["-120965"]}}
    url = "https://www.bienici.com/realEstateAds.json?" + urllib.parse.urlencode({"filters": json.dumps(filters)})
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30)
        d = json.loads(r.read())
        ads = d.get("realEstateAds", [])
        row("bienici json", r.status, f"ads={len(ads)} newest={ads[0]['publicationDate'][:16] if ads else '-'}")
    except Exception as e:
        row("bienici json", "ERR", f"{type(e).__name__} {str(e)[:80]}")


def leboncoin():
    try:
        import lbc
        client = lbc.Client()
        loc = lbc.City(lat=45.764, lng=4.8357, radius=6000, city="Lyon")
        res = client.search(locations=[loc], page=1, limit=15, sort=lbc.Sort.NEWEST,
                            category=lbc.Category.IMMOBILIER_LOCATIONS, price=[0, 600])
        row("leboncoin lbc", "ok", f"ads={len(res.ads)}")
    except Exception as e:
        row("leboncoin lbc", "ERR", f"{type(e).__name__} {str(e)[:100]}")


def cffi(name, url, pattern):
    try:
        from curl_cffi import requests
        r = requests.get(url, impersonate="chrome", timeout=30, headers={"Accept-Language": "fr-FR,fr;q=0.9"})
        n = len(set(re.findall(pattern, r.text)))
        title = (re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I) or [None, ""])[1].strip()[:40]
        row(name, r.status_code, f"{len(r.text)//1000}KB matches={n} title={title!r}")
    except Exception as e:
        row(name, "ERR", f"{type(e).__name__} {str(e)[:100]}")


if __name__ == "__main__":
    bienici()
    leboncoin()
    cffi("pap list lyon3e", "https://www.pap.fr/annonce/locations-appartement-lyon-3e-g35371", r"/annonces/[^\"]*-r\d{6,}")
    cffi("lacartedescolocs", "https://www.lacartedescolocs.fr/colocations/fr/auvergne-rhone-alpes/lyon", r"RealEstateListing")
    cffi("avendrealouer list", "https://www.avendrealouer.fr/location/rhone/lyon/loc-4-69123", r"/location/appartement/[^\"]*fd-\d+")
    cffi("paruvendu list", "https://www.paruvendu.fr/immobilier/recherche/location/appartement/lyon/", r"/immobilier/location/appartement/\w+")
