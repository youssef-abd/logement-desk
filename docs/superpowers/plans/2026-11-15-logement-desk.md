# logement-desk, plan 2: automatic runs, alerts and the desk

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the pipeline run by itself every ~10 minutes, push a phone alert (tap opens the listing), and show the listings with photos on a small private desk where you track each flat.

**Architecture:** Cloudflare Worker cron dispatches `run.yml`. After each run the workflow POSTs the desk payload to the desk's `/api/ingest` (Cloudflare Pages Function), which stores it in KV, works out which listings are new, and sends an empty Web Push. The desk is a static page that reads `/api/listings` (access-code protected). Copies and trims the owner's job desk.

**Tech Stack:** Python 3.12 (pytest), Cloudflare Workers + Pages Functions + KV (JS ES modules, `node --test`), Web Push (VAPID), GitHub Actions, wrangler 3.

**Spec:** `docs/superpowers/specs/2026-11-15-logement-desk-design.md` (sections 3, 9, 10, 11). Plan 1 (pipeline) is done: see `HANDOFF.md`.

## Decisions made here (spec amendments, written in Task 14)

1. **Listing data goes through KV, not static files.** Cloudflare Pages free allows about 500 deployments a month; a deploy every 10 minutes would exceed that. The desk code is deployed only when it changes; the data is stored by `/api/ingest`. As a bonus the data is behind the access code, not public.
2. **"Notified" tracking lives in KV** (`notified`), like the job desk, so a failed publish heals itself on the next run. The `notified` flag in `state/` is unused.
3. **First ingest seeds silently** (everything already known counts as notified), so no flood of 40 alerts.
4. **One cron trigger** (`*/10 * * * *`) also does the hourly staleness check (the Cloudflare free plan limits cron triggers per account, and the job desk already uses 3).
5. **Single user:** one `API_TOKEN` (header `x-token`), one `PUSH_TOKEN` (header `x-push-token`, used by the workflow). No friends, no per-user keys.
6. **Alerts name the flat.** One new listing: "540 € · 27 m² · district · particulier", tap opens that listing. Several: count plus the cheapest, tap opens the desk. Text comes only from validated structured fields.
7. **Photos:** only URLs, shown with `referrerpolicy="no-referrer"`; a source whose photos do not load cross-site gets a placeholder (Task 1 measures this).
8. **Yield:** per-source count of new listings per day in KV, shown in the health panel (replaces the per-query log).

## File structure

| File | Responsibility |
|---|---|
| `logement/export.py` | `build_payload(state, report, now)`: desk JSON from state |
| `logement/run.py` (modify) | `main` writes `out/desk.json` after a real run |
| `scripts/publish.py` | POST `out/desk.json` to the desk's `/api/ingest` |
| `desk/lib/auth.js`, `validate.js`, `message.js`, `ingest.js`, `push.js`, `marks.js` | desk server logic (pure, tested) |
| `desk/functions/api/*.js` | thin endpoints: `ingest`, `listings`, `marks`, `run`, `pending`, `push/{key,subscribe,test}` |
| `desk/public/` | `index.html`, `app.js`, `format.js`, `app.css`, `sw.js`, `manifest.webmanifest`, `_headers`, `robots.txt`, `icons/` |
| `cron-worker/` | Worker: cron dispatch, staleness alert, "Run now" routes |
| `.github/workflows/` | `ci.yml` (+ node tests), `run.yml` (+ publish step), `deploy-desk.yml` |
| `scripts/make_vapid.mjs`, `scripts/make_pwa_icons.py` | one-off key and icon generators |

Python tests: `.venv/Scripts/python -m pytest -q`. JS tests: `node --test` from the repo root (finds `**/*.test.mjs`).

---

### Task 1: Measure whether photo URLs load cross-site

**Files:** none committed (one-off, results go in `HANDOFF.md` at Task 14).

- [ ] **Step 1:** `git pull`, then run (reads `state/seen_listings.json`, picks one photo URL per source, requests it with no `Referer` and with a foreign one; prints status and content type only):
```bash
.venv/Scripts/python - <<'EOF'
import json, urllib.request
st = json.load(open("state/seen_listings.json", encoding="utf-8"))
first = {}
for e in st["listings"].values():
    l = e.get("listing")
    if l and l["photos"] and l["source"] not in first:
        first[l["source"]] = l["photos"][0]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
for src, url in first.items():
    for label, ref in (("no referer", None), ("foreign referer", "https://desk.example.test/")):
        h = {"User-Agent": UA}
        if ref: h["Referer"] = ref
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20)
            print(src, label, r.status, r.headers.get("content-type"))
        except Exception as ex:
            print(src, label, "ERR", type(ex).__name__, getattr(ex, "code", ""))
EOF
```
Expected: each source prints `200 image/...` for both cases. Write down any source that does not; the desk shows a placeholder for it (handled by `onerror` in Task 9) and Task 14 records it. Real confirmation happens in a browser at Task 13.

---

### Task 2: `build_payload` (Python)

**Files:** Create `logement/export.py`, `tests/test_export.py`. Modify `pytest.ini`.

- [ ] **Step 1:** In `pytest.ini` change `pythonpath = . tests` to `pythonpath = . tests scripts`.

- [ ] **Step 2: Failing test** `tests/test_export.py`:
```python
from logement import store
from logement.dedupe import process
from logement.export import build_payload
from factories import make_listing

NOW = "2026-11-15T10:00:00+00:00"


def test_payload_has_listings_newest_first_without_duplicates_and_health(profile):
    state = store.empty()
    a = make_listing(source="bienici", source_id="b1", poster="agence", photos=["https://img.example.test/1.jpg"])
    b = make_listing(source="leboncoin", source_id="l1")          # same flat as b1 -> duplicate entry
    c = make_listing(source="leboncoin", source_id="l2", rent_cc=420.0, surface_m2=15.0)
    process(state, [a], {"bienici"}, "2026-11-15T09:00:00+00:00", profile)
    process(state, [b, c], {"leboncoin"}, NOW, profile)
    state["health"]["bienici"] = {"consecutive_failures": 0, "last_success": NOW, "last_error": None, "cooldown_until": None, "blocked_runs": 0}
    p = build_payload(state, {"bienici": {"status": "ok", "fetched": 24, "kept": 20}}, NOW)
    assert [l["id"] for l in p["listings"]] == ["leboncoin:l2", "bienici:b1"]
    assert p["listings"][1]["also"] == 1 and p["listings"][1]["photos"] == ["https://img.example.test/1.jpg"]
    assert "description" not in p["listings"][0]
    assert p["updated"] == NOW
    assert p["health"]["bienici"] == {"last_success": NOW, "failures": 0, "error": None, "cooldown_until": None,
                                      "run": {"status": "ok", "fetched": 24, "kept": 20}}


def test_payload_is_capped(profile):
    state = store.empty()
    for i in range(450):
        state["listings"][f"s:{i}"] = {"dup_of": None, "first_seen": f"2026-11-15T10:{i % 60:02d}:00+00:00", "last_seen": NOW,
                                       "status": "active", "also": [], "notified": False,
                                       "listing": make_listing(source="s", source_id=str(i)).to_dict()}
    assert len(build_payload(state, {}, NOW)["listings"]) == 400
```
Run `.venv/Scripts/python -m pytest tests/test_export.py -v` → FAIL (`No module named 'logement.export'`).

- [ ] **Step 3: Implement** `logement/export.py`:
```python
KEEP = ("source", "url", "title", "rent_cc", "surface_m2", "rooms", "kind", "district", "postal_code",
        "furnished", "poster", "published_at", "flags", "tags", "photos")
MAX_LISTINGS = 400


def build_payload(state, report, now):
    """The desk's data: canonical listings (no duplicate entries, no descriptions), newest first, plus per-source health."""
    rows = []
    for key, e in state["listings"].items():
        l = e.get("listing")
        if not l or e.get("dup_of"):
            continue
        row = {k: l.get(k) for k in KEEP}
        row.update(id=key, first_seen=e["first_seen"], last_seen=e["last_seen"], status=e["status"], also=len(e.get("also", [])))
        rows.append(row)
    rows.sort(key=lambda r: r["first_seen"], reverse=True)
    health = {name: {"last_success": h.get("last_success"), "failures": h.get("consecutive_failures", 0),
                     "error": h.get("last_error"), "cooldown_until": h.get("cooldown_until"), "run": report.get(name)}
              for name, h in state.get("health", {}).items()}
    return {"updated": now, "listings": rows[:MAX_LISTINGS], "health": health}
```
- [ ] **Step 4:** run the tests → pass. Commit `feat: desk payload builder`.

---

### Task 3: `main` writes the payload; `publish.py`

**Files:** Modify `logement/run.py`, `.gitignore` (`out/` is already ignored). Create `scripts/publish.py`, `tests/test_publish.py`.

- [ ] **Step 1: Failing test** `tests/test_publish.py`:
```python
import json

import pytest

from publish import publish


class Resp:
    def __init__(self, body, status=200):
        self.status, self._b = status, body

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_publish_posts_the_payload_with_the_push_token(tmp_path):
    f = tmp_path / "desk.json"
    f.write_text('{"listings": []}', encoding="utf-8")
    seen = {}

    def fake(req, timeout):
        seen.update(url=req.full_url, token=req.get_header("X-push-token"), body=req.data)
        return Resp(b'{"ok": true, "fresh": 2, "sent": 1}')

    out = publish("https://desk.example.test/", "tok", str(f), urlopen=fake)
    assert seen["url"] == "https://desk.example.test/api/ingest" and seen["token"] == "tok"
    assert json.loads(seen["body"]) == {"listings": []}
    assert out == {"ok": True, "fresh": 2, "sent": 1}


def test_publish_fails_loudly_on_http_error(tmp_path):
    f = tmp_path / "desk.json"
    f.write_text("{}", encoding="utf-8")

    def fake(req, timeout):
        import urllib.error
        raise urllib.error.HTTPError(req.full_url, 401, "no", {}, None)

    with pytest.raises(SystemExit):
        publish("https://desk.example.test", "bad", str(f), urlopen=fake)
```
Run → FAIL (`No module named 'publish'`).

- [ ] **Step 2: Implement** `scripts/publish.py`:
```python
"""POST out/desk.json to the desk (/api/ingest). Prints counts only (Actions logs are public).
Env: DESK_URL, PUSH_TOKEN. Usage: python scripts/publish.py [path]"""
import json
import os
import sys
import urllib.error
import urllib.request


def publish(desk_url, push_token, path, urlopen=urllib.request.urlopen):
    data = open(path, "rb").read()
    req = urllib.request.Request(desk_url.rstrip("/") + "/api/ingest", data=data, method="POST",
                                 headers={"x-push-token": push_token, "content-type": "application/json", "user-agent": "logement-publish"})
    try:
        with urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"publish failed: HTTP {e.code}")
    except Exception as e:
        raise SystemExit(f"publish failed: {type(e).__name__}")


if __name__ == "__main__":
    out = publish(os.environ["DESK_URL"], os.environ["PUSH_TOKEN"], sys.argv[1] if len(sys.argv) > 1 else "out/desk.json")
    print({k: out.get(k) for k in ("ok", "stored", "fresh", "sent", "devices", "seeded")})
```
- [ ] **Step 3:** In `logement/run.py` add `from .export import build_payload` and, in `main`, inside `if not a.check:` after `store.save(a.state, state)`:
```python
        os.makedirs("out", exist_ok=True)
        with open("out/desk.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(build_payload(state, res["report"], now), f, ensure_ascii=False)
```
(add `import json` at the top). Run the whole suite → all pass. Commit `feat: publish script and desk payload on every real run`.

---

### Task 4: Desk skeleton, auth and validation (JS)

**Files:** Create `desk/package.json`, `cron-worker/package.json` (both `{"private": true, "type": "module"}`), `desk/lib/auth.js`, `desk/lib/validate.js`, `desk/tests/helpers.mjs`, `desk/tests/validate.test.mjs`.

- [ ] **Step 1: Failing test** `desk/tests/validate.test.mjs`:
```js
import test from "node:test";
import assert from "node:assert/strict";
import { safeUrl, cleanListing, cleanPayload } from "../lib/validate.js";

test("safeUrl accepts only https on the source hosts", () => {
  assert.equal(safeUrl("https://www.leboncoin.fr/ad/locations/1"), "https://www.leboncoin.fr/ad/locations/1");
  assert.equal(safeUrl("http://www.leboncoin.fr/x"), "");
  assert.equal(safeUrl("https://evil.example/x"), "");
  assert.equal(safeUrl("https://leboncoin.fr.evil.example/x"), "");
  assert.equal(safeUrl("javascript:alert(1)"), "");
});

const good = { id: "bienici:a1", source: "bienici", url: "https://www.bienici.com/annonce/a1", title: "T", rent_cc: 500,
  surface_m2: 20, rooms: 1, district: "City 3e", poster: "agence", status: "active", flags: ["visale"], tags: [], photos: ["https://file.bienici.com/p1", "http://x/y", "javascript:1"] };

test("cleanListing keeps good fields, drops bad photos and bad urls", () => {
  const l = cleanListing(good);
  assert.equal(l.rent_cc, 500);
  assert.deepEqual(l.photos, ["https://file.bienici.com/p1"]);
  assert.equal(cleanListing({ ...good, url: "https://evil.example/" }), null);
  assert.equal(cleanListing({ ...good, id: "" }), null);
  assert.equal(cleanListing({ ...good, rent_cc: "500" }).rent_cc, null);
  assert.equal(cleanListing({ ...good, poster: "<script>" }).poster, null);
});

test("cleanPayload caps size and rejects junk", () => {
  assert.equal(cleanPayload(null), null);
  assert.equal(cleanPayload({ listings: "x" }), null);
  const p = cleanPayload({ updated: "t", listings: Array(500).fill(good), health: { bienici: { failures: 2, run: { status: "ok", fetched: 24, kept: 20 } }, "BAD name": {} } });
  assert.equal(p.listings.length, 400);
  assert.deepEqual(Object.keys(p.health), ["bienici"]);
  assert.equal(p.health.bienici.kept, 20);
});
```
Run `node --test` → FAIL (module missing).

- [ ] **Step 2: Implement** `desk/lib/validate.js`:
```js
// Everything the desk stores or shows comes from scraped, attacker-controllable text: keep only known fields, known types, short strings.
const HOSTS = ["bienici.com", "leboncoin.fr", "lacartedescolocs.fr", "paruvendu.fr"]; // add a source's domain here when you add the source

export function safeUrl(u) {
  try {
    const x = new URL(u);
    if (x.protocol !== "https:") return "";
    return HOSTS.some((d) => x.hostname === d || x.hostname.endsWith("." + d)) ? x.href : "";
  } catch (e) { return ""; }
}
const safePhoto = (u) => { try { const x = new URL(u); return x.protocol === "https:" ? x.href : ""; } catch (e) { return ""; } };
const str = (v, n) => (typeof v === "string" ? v.slice(0, n) : "");
const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const arr = (a) => (Array.isArray(a) ? a.filter((x) => typeof x === "string").map((x) => x.slice(0, 24)).slice(0, 12) : []);

export function cleanListing(l) {
  if (!l || typeof l !== "object") return null;
  const id = str(l.id, 100), url = safeUrl(l.url);
  if (!id || !url) return null;
  return {
    id, source: str(l.source, 30), url, title: str(l.title, 120), rent_cc: num(l.rent_cc), surface_m2: num(l.surface_m2), rooms: num(l.rooms),
    kind: str(l.kind, 12) || null, district: str(l.district, 60) || null, postal_code: str(l.postal_code, 10) || null,
    furnished: typeof l.furnished === "boolean" ? l.furnished : null, poster: ["particulier", "agence"].includes(l.poster) ? l.poster : null,
    published_at: str(l.published_at, 40) || null, first_seen: str(l.first_seen, 40), last_seen: str(l.last_seen, 40),
    status: l.status === "stale" ? "stale" : "active", flags: arr(l.flags), tags: arr(l.tags),
    photos: (Array.isArray(l.photos) ? l.photos : []).map(safePhoto).filter(Boolean).slice(0, 8), also: num(l.also) || 0,
  };
}

export function cleanPayload(p) {
  if (!p || typeof p !== "object" || !Array.isArray(p.listings)) return null;
  const health = {};
  for (const [name, h] of Object.entries(p.health && typeof p.health === "object" ? p.health : {}).slice(0, 12)) {
    if (!/^[a-z0-9_]{2,30}$/.test(name) || !h || typeof h !== "object") continue;
    const run = h.run && typeof h.run === "object" ? h.run : {};
    health[name] = { last_success: str(h.last_success, 40) || null, failures: num(h.failures) || 0, error: str(h.error, 40) || null,
      cooldown_until: str(h.cooldown_until, 40) || null, status: str(run.status, 12) || null, fetched: num(run.fetched), kept: num(run.kept) };
  }
  return { updated: str(p.updated, 40), listings: p.listings.slice(0, 400).map(cleanListing).filter(Boolean), health };
}
```
`desk/lib/auth.js`:
```js
export function same(a, b) { // constant-time compare
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
export const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });
export const isOwner = (request, env) => !!env.API_TOKEN && same(request.headers.get("x-token") || "", env.API_TOKEN);
export const isPusher = (request, env) => !!env.PUSH_TOKEN && same(request.headers.get("x-push-token") || "", env.PUSH_TOKEN);
```
`desk/tests/helpers.mjs`:
```js
export function fakeKV(init = {}) {
  const m = new Map(Object.entries(init).map(([k, v]) => [k, JSON.stringify(v)]));
  return {
    async get(k, type) { const v = m.get(k); return v === undefined ? null : type === "json" ? JSON.parse(v) : v; },
    async put(k, v) { m.set(k, v); },
    dump: () => Object.fromEntries([...m].map(([k, v]) => [k, JSON.parse(v)])),
  };
}
```
- [ ] **Step 3:** `node --test` → pass. Commit `feat(desk): auth and payload validation`.

---

### Task 5: Message and ingest logic (JS)

**Files:** Create `desk/lib/message.js`, `desk/lib/ingest.js`, `desk/tests/ingest.test.mjs`.

- [ ] **Step 1: Failing test** `desk/tests/ingest.test.mjs`:
```js
import test from "node:test";
import assert from "node:assert/strict";
import { fakeKV } from "./helpers.mjs";
import { ingest } from "../lib/ingest.js";
import { messageFor } from "../lib/message.js";

const L = (id, o = {}) => ({ id, source: "bienici", url: `https://www.bienici.com/annonce/${id}`, rent_cc: 540, surface_m2: 27.4, district: "City 7e", poster: "particulier", status: "active", ...o });
const P = (...ls) => ({ updated: "t", listings: ls, health: {} });
const NOW = Date.parse("2026-11-15T10:00:00Z");

test("messageFor: one listing opens the listing, several open the desk", () => {
  assert.deepEqual(messageFor([L("a")]), { body: "540 € · 27 m² · City 7e · particulier", url: "https://www.bienici.com/annonce/a" });
  const m = messageFor([L("a", { rent_cc: 600 }), L("b", { rent_cc: 450 })]);
  assert.equal(m.url, "/");
  assert.match(m.body, /^2 new: from 450 €/);
  assert.equal(messageFor([]), null);
});

test("the first ingest seeds silently, the next one alerts only on new active listings", async () => {
  const kv = fakeKV({ push: [{ endpoint: "https://push.example/1" }] });
  const sent = [];
  const send = async (s) => { sent.push(s.endpoint); return 201; };
  const first = await ingest({ kv, payload: P(L("a"), L("b")), now: NOW, send });
  assert.equal(first.seeded, true); assert.equal(sent.length, 0);
  const none = await ingest({ kv, payload: P(L("a"), L("b")), now: NOW, send });
  assert.equal(none.fresh, 0); assert.equal(sent.length, 0);
  const next = await ingest({ kv, payload: P(L("c"), L("d", { status: "stale" }), L("a"), L("b")), now: NOW, send });
  assert.equal(next.fresh, 1); assert.equal(next.sent, 1);
  assert.equal((await kv.get("pending", "json")).url, "https://www.bienici.com/annonce/c");
  assert.deepEqual(kv.dump().yield["2026-11-15"], { bienici: 1 });
  const again = await ingest({ kv, payload: P(L("c"), L("a"), L("b")), now: NOW, send });
  assert.equal(again.fresh, 0);
});

test("a device that answered 410 is forgotten, a failing push does not break ingest", async () => {
  const kv = fakeKV({ notified: [], push: [{ endpoint: "https://gone" }, { endpoint: "https://ok" }, { endpoint: "https://boom" }] });
  const send = async (s) => { if (s.endpoint === "https://gone") return 410; if (s.endpoint === "https://boom") throw new Error("x"); return 201; };
  const r = await ingest({ kv, payload: P(L("a")), now: NOW, send });
  assert.equal(r.sent, 1);
  assert.deepEqual((await kv.get("push", "json")).map((s) => s.endpoint), ["https://ok", "https://boom"]);
});
```
Run → FAIL.

- [ ] **Step 2: Implement** `desk/lib/message.js`:
```js
const rent = (n) => (n == null ? "? €" : `${Math.round(n)} €`);
export function oneLine(l) {
  const p = [rent(l.rent_cc)];
  if (l.surface_m2 != null) p.push(`${Math.round(l.surface_m2)} m²`);
  if (l.district) p.push(l.district);
  if (l.poster) p.push(l.poster);
  return p.join(" · ");
}
// Built only from validated fields (never from description text). One new listing: tap opens it. Several: tap opens the desk.
export function messageFor(fresh) {
  if (!fresh.length) return null;
  if (fresh.length === 1) return { body: oneLine(fresh[0]), url: fresh[0].url };
  const best = [...fresh].sort((a, b) => (a.rent_cc ?? 1e9) - (b.rent_cc ?? 1e9))[0];
  return { body: `${fresh.length} new: from ${oneLine(best)}`, url: "/" };
}
```
`desk/lib/ingest.js`:
```js
import { messageFor } from "./message.js";

// payload is already cleaned. kv is the KV binding; send(sub) returns the push HTTP status.
export async function ingest({ kv, payload, now, send }) {
  const raw = await kv.get("notified", "json");
  const first = !Array.isArray(raw);
  const notified = new Set(first ? [] : raw);
  const fresh = first ? [] : payload.listings.filter((l) => l.status === "active" && !notified.has(l.id));
  await kv.put("listings", JSON.stringify(payload));
  let sent = 0, devices = 0;
  if (fresh.length) {
    const m = messageFor(fresh);
    await kv.put("pending", JSON.stringify({ ...m, t: now }));
    const subs = (await kv.get("push", "json")) || [];
    const keep = [];
    for (const s of subs) {
      let code = 0;
      try { code = await send(s); } catch (e) { code = 0; }
      if (code === 404 || code === 410) continue; // the device unsubscribed
      keep.push(s);
      if (code >= 200 && code < 300) sent++;
    }
    devices = keep.length;
    if (keep.length !== subs.length) await kv.put("push", JSON.stringify(keep));
    const day = new Date(now).toISOString().slice(0, 10), y = (await kv.get("yield", "json")) || {};
    y[day] = y[day] || {};
    for (const l of fresh) y[day][l.source] = (y[day][l.source] || 0) + 1;
    for (const d of Object.keys(y).sort().slice(0, -14)) delete y[d];
    await kv.put("yield", JSON.stringify(y));
  }
  if (first || fresh.length) {
    const ids = first ? payload.listings.map((l) => l.id) : fresh.map((l) => l.id);
    await kv.put("notified", JSON.stringify([...notified, ...ids].slice(-3000)));
  }
  return { stored: payload.listings.length, fresh: fresh.length, sent, devices, seeded: first };
}
```
- [ ] **Step 3:** `node --test` → pass. Commit `feat(desk): alert message and ingest logic`.

---

### Task 6: Endpoints (ingest, listings, marks, push, run)

**Files:** Create `desk/lib/marks.js`, `desk/lib/push.js`, `desk/tests/marks.test.mjs`, `desk/functions/api/{ingest,listings,marks,run,pending}.js`, `desk/functions/api/push/{key,subscribe,test}.js`.

- [ ] **Step 1: Failing test** `desk/tests/marks.test.mjs`:
```js
import test from "node:test";
import assert from "node:assert/strict";
import { applyMark } from "../lib/marks.js";

test("applyMark sets, replaces by newest, removes and validates", () => {
  let m = applyMark({}, { id: "bienici:a1", s: "contacted", t: 5 });
  assert.deepEqual(m, { "bienici:a1": { s: "contacted", t: 5 } });
  assert.deepEqual(applyMark(m, { id: "bienici:a1", s: "visit", t: 4 }), m);            // older write ignored
  assert.equal(applyMark(m, { id: "bienici:a1", s: "visit", t: 6 })["bienici:a1"].s, "visit");
  assert.deepEqual(applyMark(m, { id: "bienici:a1", s: "none", t: 9 }), {});
  assert.equal(applyMark(m, { id: "x y", s: "visit", t: 1 }), null);
  assert.equal(applyMark(m, { id: "a", s: "hacked", t: 1 }), null);
  assert.equal(applyMark(m, { id: "a", s: "visit", t: "1" }), null);
});
```
Run → FAIL. Implement `desk/lib/marks.js`:
```js
const STAGES = new Set(["contacted", "visit", "dossier", "refused", "none"]);
// Returns the new marks object, or null when the input is invalid.
export function applyMark(marks, b) {
  if (!b || !/^[A-Za-z0-9_.:-]{1,100}$/.test(b.id || "") || !STAGES.has(b.s) || !Number.isFinite(b.t)) return null;
  const next = { ...marks };
  if (b.s === "none") { delete next[b.id]; return next; }
  if (!next[b.id] && Object.keys(next).length >= 1000) return null;
  if (!next[b.id] || next[b.id].t <= b.t) next[b.id] = { s: b.s, t: b.t };
  return next;
}
```
- [ ] **Step 2:** Create `desk/lib/push.js` (copy of the job desk's `vapidHeader` and `sendPush`, nothing else):
```js
// Web Push without payloads: a push carries no text, it only wakes sw.js, which asks /api/pending. Needs the secret VAPID_PRIVATE
// (JWK of a P-256 key), and vars VAPID_PUBLIC (raw public key, base64url) and VAPID_SUBJECT (the desk's web address, not an email).
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const enc = (s) => new TextEncoder().encode(s);

export async function vapidHeader(env, endpoint) {
  const header = b64u(enc(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const claims = b64u(enc(JSON.stringify({ aud: new URL(endpoint).origin, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: env.VAPID_SUBJECT })));
  const k = await crypto.subtle.importKey("jwk", JSON.parse(env.VAPID_PRIVATE), { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, k, enc(header + "." + claims));
  return `vapid t=${header}.${claims}.${b64u(sig)}, k=${env.VAPID_PUBLIC}`;
}

// One empty push to one device; returns the HTTP status (404 / 410 = the device is gone).
export async function sendPush(env, sub) {
  const res = await fetch(sub.endpoint, { method: "POST", headers: { Authorization: await vapidHeader(env, sub.endpoint), TTL: "21600", Urgency: "normal", "Content-Length": "0" } });
  return res.status;
}
```
- [ ] **Step 3:** Endpoint files (thin; logic is already tested):

`desk/functions/api/ingest.js`:
```js
import { isPusher, json } from "../../lib/auth.js";
import { cleanPayload } from "../../lib/validate.js";
import { ingest } from "../../lib/ingest.js";
import { sendPush } from "../../lib/push.js";

export async function onRequestPost({ request, env }) {
  if (!isPusher(request, env)) return json({ error: "unauthorized" }, 401);
  if (Number(request.headers.get("content-length") || 0) > 2_000_000) return json({ error: "too large" }, 413);
  let body;
  try { body = await request.json(); } catch (e) { return json({ error: "bad json" }, 400); }
  const payload = cleanPayload(body);
  if (!payload) return json({ error: "bad payload" }, 400);
  return json({ ok: true, ...(await ingest({ kv: env.DESK, payload, now: Date.now(), send: (s) => sendPush(env, s) })) });
}
```
`desk/functions/api/listings.js`:
```js
import { isOwner, json } from "../../lib/auth.js";

export async function onRequestGet({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  const data = (await env.DESK.get("listings", "json")) || { updated: null, listings: [], health: {} };
  return json({ ...data, yield: (await env.DESK.get("yield", "json")) || {} });
}
```
`desk/functions/api/marks.js`:
```js
import { isOwner, json } from "../../lib/auth.js";
import { applyMark } from "../../lib/marks.js";

export async function onRequest({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  const marks = (await env.DESK.get("marks", "json")) || {};
  if (request.method === "GET") return json({ marks });
  if (request.method !== "POST") return json({ error: "method" }, 405);
  let b;
  try { b = await request.json(); } catch (e) { return json({ error: "bad json" }, 400); }
  const next = applyMark(marks, b);
  if (!next) return json({ error: "bad input" }, 400);
  await env.DESK.put("marks", JSON.stringify(next));
  return json({ ok: true });
}
```
`desk/functions/api/pending.js`:
```js
import { isOwner, json } from "../../lib/auth.js";

export async function onRequestGet({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  return json((await env.DESK.get("pending", "json")) || { body: "", url: "/" });
}
```
`desk/functions/api/push/key.js`:
```js
import { json } from "../../../lib/auth.js";

export async function onRequestGet({ env }) { return json({ key: env.VAPID_PUBLIC || "" }); } // public half of the key pair, not secret
```
`desk/functions/api/push/subscribe.js`:
```js
import { isOwner, json } from "../../../lib/auth.js";

const okEndpoint = (e) => typeof e === "string" && e.length < 600 && /^https:\/\//.test(e);

export async function onRequest({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  let b;
  try { b = await request.json(); } catch (e) { return json({ error: "bad json" }, 400); }
  const subs = (await env.DESK.get("push", "json")) || [];
  if (request.method === "DELETE") {
    await env.DESK.put("push", JSON.stringify(subs.filter((s) => s.endpoint !== (b && b.endpoint))));
    return json({ ok: true });
  }
  if (request.method !== "POST") return json({ error: "method" }, 405);
  const s = b && b.subscription;
  if (!s || !okEndpoint(s.endpoint)) return json({ error: "bad subscription" }, 400);
  const next = [...subs.filter((x) => x.endpoint !== s.endpoint), { endpoint: s.endpoint, t: Date.now() }].slice(-5);
  await env.DESK.put("push", JSON.stringify(next));
  return json({ ok: true, devices: next.length });
}
```
`desk/functions/api/push/test.js`:
```js
import { isOwner, json } from "../../../lib/auth.js";
import { sendPush } from "../../../lib/push.js";

export async function onRequestPost({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  await env.DESK.put("pending", JSON.stringify({ body: "Test alert: this is how alerts will look.", url: "/", t: Date.now() }));
  let sent = 0;
  const subs = (await env.DESK.get("push", "json")) || [];
  for (const s of subs) { try { const c = await sendPush(env, s); if (c >= 200 && c < 300) sent++; } catch (e) { /* counted as not sent */ } }
  return json({ ok: true, sent, devices: subs.length });
}
```
`desk/functions/api/run.js` ("Run now": the Worker holds the GitHub token, reached through the service binding `RUNNER`):
```js
import { isOwner, json } from "../../lib/auth.js";

const COOLDOWN_MS = 5 * 60 * 1000;

export async function onRequest({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  if (!env.RUNNER) return json({ error: "the runner is not connected" }, 503);
  let last;
  try { last = await (await env.RUNNER.fetch("https://runner/last-run")).json(); } catch (e) { return json({ error: "the runner did not answer" }, 502); }
  if (request.method === "GET") return json({ last });
  if (request.method !== "POST") return json({ error: "method" }, 405);
  if (last.status === "in_progress" || last.status === "queued") return json({ error: "a run is already in progress", last }, 409);
  const prev = Number(await env.DESK.get("runnow")) || 0;
  if (Date.now() - prev < COOLDOWN_MS) return json({ error: "wait a few minutes", last }, 429);
  let d;
  try { d = await (await env.RUNNER.fetch("https://runner/dispatch", { method: "POST" })).json(); } catch (e) { return json({ error: "the runner did not answer" }, 502); }
  if (d.status !== 204) return json({ error: "GitHub refused the start (HTTP " + d.status + ")" }, 502);
  await env.DESK.put("runnow", String(Date.now()));
  return json({ ok: true });
}
```
- [ ] **Step 4:** `node --test` → all pass; syntax-check each endpoint with `node --check <file>`. Commit `feat(desk): API endpoints`.

---

### Task 7: Cron Worker

**Files:** Create `cron-worker/src/index.js`, `cron-worker/wrangler.toml`, `cron-worker/tests/worker.test.mjs`.

- [ ] **Step 1: Failing test** `cron-worker/tests/worker.test.mjs`:
```js
import test from "node:test";
import assert from "node:assert/strict";
import { minutesSince, isDue } from "../src/index.js";

test("minutesSince and isDue", () => {
  assert.equal(minutesSince("2026-11-15T10:00:00Z", Date.parse("2026-11-15T11:30:00Z")), 90);
  assert.equal(minutesSince(null, 1), Infinity);
  assert.equal(isDue(Date.parse("2026-11-15T10:03:00Z")), true);   // first 10 minutes of the hour: do the hourly check
  assert.equal(isDue(Date.parse("2026-11-15T10:23:00Z")), false);
});
```
Run → FAIL. Implement `cron-worker/src/index.js`:
```js
// Cloudflare cron -> starts the GitHub Actions workflow run.yml every 10 minutes (GitHub's own `schedule:` runs hours late).
// Once an hour it also checks that a run succeeded recently and alerts through ntfy if not. One cron trigger only.
// Secrets (set with `wrangler secret put`, never in the repo): GITHUB_TOKEN (fine-grained PAT, this repo only, "Actions: read and write"), NTFY_TOPIC.
const REPO = "youssef-abd/logement-desk";
const WORKFLOW = "run.yml";
const STALE_AFTER_MIN = 60;
const gh = (env) => ({ Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "logement-cron" });

export const minutesSince = (iso, nowMs) => (iso ? (nowMs - Date.parse(iso)) / 60000 : Infinity);
export const isDue = (nowMs) => new Date(nowMs).getUTCMinutes() < 10;
const jsonRes = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json" } });

const dispatch = (env) => fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
  method: "POST", headers: gh(env), body: JSON.stringify({ ref: "main", inputs: { mode: "full" } }) });

async function alert(env, text) {
  if (!env.NTFY_TOPIC) return;
  try { await fetch(`https://ntfy.sh/${env.NTFY_TOPIC}`, { method: "POST", headers: { Title: "logement-desk", Tags: "warning" }, body: text }); } catch (e) { console.error("ntfy failed", String(e)); }
}

async function lastRun(env, extra = "") {
  const res = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?per_page=1${extra}`, { headers: gh(env) });
  if (!res.ok) return { error: `GitHub answered HTTP ${res.status}` };
  const r = ((await res.json()).workflow_runs || [])[0];
  return r ? { status: r.status, conclusion: r.conclusion, started: r.run_started_at || r.created_at, updated: r.updated_at } : { status: "none" };
}

export default {
  async scheduled(event, env) {
    if (!env.GITHUB_TOKEN) { await alert(env, "Runs are not started: the GITHUB_TOKEN secret is missing."); return; }
    let status = 0;
    for (let attempt = 1; attempt <= 2 && status !== 204; attempt++) status = (await dispatch(env)).status;
    if (status !== 204) await alert(env, `A run was not started (GitHub answered HTTP ${status}).${[401, 403, 404].includes(status) ? " The GitHub token has probably expired: renew it." : ""}`);
    if (isDue(event.scheduledTime)) {
      const ok = await lastRun(env, "&status=success");
      const age = minutesSince(ok.updated, Date.now());
      if (age > STALE_AFTER_MIN) await alert(env, `No successful run for ${Number.isFinite(age) ? Math.round(age) + " minutes" : "a long time"}.`);
    }
  },
  // Reached only through the desk's service binding (workers_dev = false: no public address).
  async fetch(request, env) {
    const u = new URL(request.url);
    if (!env.GITHUB_TOKEN) return jsonRes({ error: "GITHUB_TOKEN secret is not set" }, 500);
    if (request.method === "GET" && u.pathname === "/last-run") return jsonRes(await lastRun(env));
    if (request.method === "POST" && u.pathname === "/dispatch") return jsonRes({ status: (await dispatch(env)).status });
    return jsonRes({ error: "not found" }, 404);
  },
};
```
`cron-worker/wrangler.toml`:
```toml
name = "logement-cron"
main = "src/index.js"
compatibility_date = "2026-11-01"
workers_dev = false        # no public URL: this Worker only runs on its cron and through the desk's service binding

[triggers]
crons = ["*/10 * * * *"]
```
- [ ] **Step 2:** `node --test` → pass. Commit `feat: cron worker`.

---

### Task 8: The desk page

**Files:** Create `desk/public/format.js`, `desk/tests/format.test.mjs`, `desk/public/index.html`, `app.css`, `app.js`.

- [ ] **Step 1: Failing test** `desk/tests/format.test.mjs`:
```js
import test from "node:test";
import assert from "node:assert/strict";
import { ago, tabOf, matches, needsNudge } from "../public/format.js";

const L = (o = {}) => ({ id: "a", source: "bienici", status: "active", poster: "particulier", tags: [], title: "Studio", district: "City 7e", ...o });
const F = { tab: "new", source: "all", poster: "all", near: true, q: "" };

test("ago", () => {
  const now = Date.parse("2026-11-15T12:00:00Z");
  assert.equal(ago("2026-11-15T11:50:00Z", now), "10 min ago");
  assert.equal(ago("2026-11-15T07:00:00Z", now), "5 h ago");
  assert.equal(ago("2026-11-10T12:00:00Z", now), "5 d ago");
  assert.equal(ago(null, now), "");
});

test("tabOf follows the stage first, then staleness", () => {
  assert.equal(tabOf(L(), "none"), "new");
  assert.equal(tabOf(L({ status: "stale" }), "none"), "closed");
  assert.equal(tabOf(L({ status: "stale" }), "visit"), "following");
  assert.equal(tabOf(L(), "refused"), "closed");
});

test("matches applies tab, source, poster, near-miss and text", () => {
  assert.equal(matches(L(), F, "none"), true);
  assert.equal(matches(L(), { ...F, tab: "following" }, "none"), false);
  assert.equal(matches(L(), { ...F, source: "leboncoin" }, "none"), false);
  assert.equal(matches(L({ poster: "agence" }), { ...F, poster: "particulier" }, "none"), false);
  assert.equal(matches(L({ tags: ["near-miss"] }), { ...F, near: false }, "none"), false);
  assert.equal(matches(L(), { ...F, q: "city 7" }, "none"), true);
  assert.equal(matches(L(), { ...F, q: "zzz" }, "none"), false);
});

test("needsNudge", () => {
  const day = 86400000;
  assert.equal(needsNudge({ s: "contacted", t: 0 }, 4 * day), true);
  assert.equal(needsNudge({ s: "contacted", t: 0 }, 2 * day), false);
  assert.equal(needsNudge({ s: "visit", t: 0 }, 9 * day), false);
});
```
Run → FAIL. Implement `desk/public/format.js`:
```js
export const fmtRent = (n) => (n == null ? "? €" : `${Math.round(n)} €`);
export const fmtSurface = (n) => (n == null ? "" : `${Math.round(n)} m²`);
export const isHttps = (u) => typeof u === "string" && u.startsWith("https://");

export function ago(iso, nowMs = Date.now()) {
  if (!iso) return "";
  const m = Math.max(0, Math.round((nowMs - Date.parse(iso)) / 60000));
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} d ago`;
}

export function tabOf(l, stage) {
  if (["contacted", "visit", "dossier"].includes(stage)) return "following";
  if (stage === "refused" || l.status === "stale") return "closed";
  return "new";
}

export function matches(l, f, stage) {
  if (tabOf(l, stage) !== f.tab) return false;
  if (f.source !== "all" && l.source !== f.source) return false;
  if (f.poster !== "all" && l.poster !== f.poster) return false;
  if (!f.near && (l.tags || []).includes("near-miss")) return false;
  return !f.q || `${l.title} ${l.district || ""} ${l.source}`.toLowerCase().includes(f.q.toLowerCase());
}

export const needsNudge = (mark, nowMs, days = 3) => !!mark && mark.s === "contacted" && nowMs - mark.t > days * 86400000;
```
- [ ] **Step 2:** `node --test` → pass.

- [ ] **Step 3:** `desk/public/index.html` (system fonts, no inline script or style: the CSP in `_headers` forbids them):
```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#0f1114">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<link rel="icon" href="/icons/icon-192.png">
<title>Logement</title>
<link rel="stylesheet" href="/app.css">
</head>
<body>
<header class="bar"><strong>Logement</strong><span id="updated" class="muted"></span><button id="menu" class="btn" type="button">Settings</button></header>
<main>
  <nav class="tabs" id="tabs">
    <button data-tab="new" aria-selected="true">New <span id="n-new"></span></button>
    <button data-tab="following" aria-selected="false">Following <span id="n-following"></span></button>
    <button data-tab="closed" aria-selected="false">Closed <span id="n-closed"></span></button>
  </nav>
  <div class="filters">
    <select id="source" aria-label="Source"><option value="all">All sources</option></select>
    <select id="poster" aria-label="Poster"><option value="all">Anyone</option><option value="particulier">Private only</option></select>
    <label class="chk"><input type="checkbox" id="near" checked> near-miss</label>
    <input id="q" type="search" placeholder="Search" aria-label="Search">
  </div>
  <p id="msg" class="muted"></p>
  <div id="list"></div>
  <details class="health"><summary>Source health</summary><div id="health"></div></details>
</main>
<dialog id="gal"><button id="galx" class="btn" type="button">Close</button><div id="strip"></div></dialog>
<dialog id="dlg">
  <h2>Settings</h2>
  <label for="code">Access code</label><input id="code" type="password" autocomplete="off">
  <div class="box"><strong>Alerts on this device</strong><p id="pushmsg" class="muted"></p>
    <button class="btn" id="pushbtn" type="button">Turn on alerts</button> <button class="btn" id="pushtest" type="button">Send a test</button></div>
  <div class="box"><strong>Run now</strong><p id="runmsg" class="muted"></p><button class="btn" id="runbtn" type="button">Start a run</button></div>
  <div class="foot"><button class="btn" id="dlgcancel" type="button">Close</button><button class="btn primary" id="dlgsave" type="button">Save</button></div>
</dialog>
<script type="module" src="/app.js"></script>
</body>
</html>
```
`desk/public/app.css`:
```css
:root{--bg:#f4f5f7;--fg:#14171a;--mut:#5c6670;--card:#fff;--line:#dde1e6;--acc:#1d5fbf;--warn:#b42318}
@media (prefers-color-scheme:dark){:root{--bg:#0f1114;--fg:#ececec;--mut:#98a2ad;--card:#171a1f;--line:#2a2f36;--acc:#6aa6f5;--warn:#f97066}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,-apple-system,Segoe UI,sans-serif}
.bar{display:flex;gap:12px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:2}
.bar .muted{flex:1;font-size:12px}main{max-width:760px;margin:0 auto;padding:12px 16px 40px}
.muted{color:var(--mut)}.btn,select,input{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 10px}
.btn.primary{background:var(--acc);color:#fff;border-color:var(--acc)}.tabs{display:flex;gap:6px;margin-bottom:10px}
.tabs button{flex:1;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:inherit;font:inherit}
.tabs button[aria-selected=true]{background:var(--acc);color:#fff;border-color:var(--acc)}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}.filters input[type=search]{flex:1;min-width:120px}.chk{display:flex;gap:4px;align-items:center}
.card{display:flex;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px;margin-bottom:10px}
.card.stale{opacity:.6}.thumb{width:112px;height:84px;object-fit:cover;border-radius:8px;background:var(--line);flex:none;cursor:pointer}
.body{min-width:0;flex:1}.price{font-weight:600}.chips{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0}
.chip{font-size:12px;padding:1px 8px;border:1px solid var(--line);border-radius:99px}.chip.warn{color:var(--warn);border-color:var(--warn)}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:13px}.nudge{color:var(--warn)}a{color:var(--acc)}
.health{margin-top:20px}.bad{color:var(--warn)}dialog{border:1px solid var(--line);border-radius:12px;background:var(--bg);color:var(--fg);max-width:520px;width:calc(100% - 24px)}
dialog::backdrop{background:#0008}.box{border-top:1px solid var(--line);margin-top:12px;padding-top:10px}.foot{display:flex;gap:8px;justify-content:flex-end;margin-top:14px}
#strip{display:flex;gap:8px;overflow-x:auto;margin-top:8px}#strip img{height:55vh;border-radius:8px}
```
`desk/public/app.js`:
```js
import { fmtRent, fmtSurface, isHttps, ago, matches, tabOf, needsNudge } from "./format.js";

const $ = (id) => document.getElementById(id);
const ls = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };
const S = { token: ls.get("ld-token") || "", data: null, marks: {}, yield: {}, f: { tab: "new", source: "all", poster: "all", near: true, q: "" } };
const STAGES = [["none", "New"], ["contacted", "Contacted"], ["visit", "Visit"], ["dossier", "Dossier sent"], ["refused", "Refused"]];

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, cache: "no-store", headers: { "content-type": "application/json", "x-token": S.token, ...(opts.headers || {}) } });
  if (r.status === 401) throw new Error("wrong or missing access code");
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }; // text only, never HTML

async function load() {
  if (!S.token) { $("msg").textContent = "Open Settings and enter the access code."; return; }
  try {
    const [d, m] = await Promise.all([api("/api/listings"), api("/api/marks")]);
    S.data = d; S.marks = m.marks || {}; S.yield = d.yield || {}; $("msg").textContent = "";
  } catch (e) { $("msg").textContent = e.message; return; }
  const src = [...new Set(S.data.listings.map((l) => l.source))];
  $("source").replaceChildren(new Option("All sources", "all"), ...src.map((s) => new Option(s, s)));
  render();
}

function render() {
  const d = S.data; if (!d) return;
  const age = d.updated ? (Date.now() - Date.parse(d.updated)) / 60000 : Infinity;
  $("updated").textContent = d.updated ? "updated " + ago(d.updated) : "no data yet";
  $("updated").classList.toggle("bad", age > 30);
  const stage = (l) => (S.marks[l.id] && S.marks[l.id].s) || "none";
  for (const t of ["new", "following", "closed"]) $("n-" + t).textContent = d.listings.filter((l) => tabOf(l, stage(l)) === t).length;
  const rows = d.listings.filter((l) => matches(l, S.f, stage(l)));
  $("list").replaceChildren(...rows.map(card));
  if (!rows.length) $("msg").textContent = "Nothing here.";
  renderHealth();
}

function card(l) {
  const c = el("div", "card" + (l.status === "stale" ? " stale" : ""));
  const img = el("img", "thumb"); img.alt = ""; img.loading = "lazy"; img.referrerPolicy = "no-referrer";
  if (l.photos && l.photos[0] && isHttps(l.photos[0])) { img.src = l.photos[0]; img.addEventListener("error", () => { img.removeAttribute("src"); }); img.addEventListener("click", () => gallery(l)); }
  const b = el("div", "body");
  b.append(el("div", "price", `${fmtRent(l.rent_cc)} · ${fmtSurface(l.surface_m2)} · ${l.district || ""}`.replace(/ · +·/g, " ·").trim()));
  b.append(el("div", "muted", `${l.title} · ${l.source}${l.poster ? " · " + l.poster : ""}${l.also ? " · also on " + l.also + " more" : ""}`));
  const chips = el("div", "chips");
  for (const t of l.tags || []) chips.append(el("span", "chip warn", t));
  for (const t of l.flags || []) chips.append(el("span", "chip", t.replace(/_/g, " ")));
  if (l.status === "stale") chips.append(el("span", "chip", "not in latest results"));
  b.append(chips);
  const row = el("div", "row");
  if (isHttps(l.url)) { const a = el("a", null, "Open listing"); a.href = l.url; a.target = "_blank"; a.rel = "noopener noreferrer"; row.append(a); }
  const sel = el("select"); for (const [v, name] of STAGES) sel.append(new Option(name, v));
  sel.value = (S.marks[l.id] && S.marks[l.id].s) || "none";
  sel.addEventListener("change", () => setStage(l.id, sel.value));
  row.append(sel);
  if (l.photos && l.photos[0] && isHttps(l.photos[0])) { const a = el("a", null, "Image search"); a.href = "https://lens.google.com/uploadbyurl?url=" + encodeURIComponent(l.photos[0]); a.target = "_blank"; a.rel = "noopener noreferrer"; row.append(a); }
  if (needsNudge(S.marks[l.id], Date.now())) row.append(el("span", "nudge", "contacted " + ago(new Date(S.marks[l.id].t).toISOString()) + ", no update"));
  b.append(row); c.append(img, b); return c;
}

function gallery(l) {
  $("strip").replaceChildren(...(l.photos || []).filter(isHttps).map((u) => { const i = el("img"); i.src = u; i.referrerPolicy = "no-referrer"; i.alt = ""; return i; }));
  $("gal").showModal();
}

async function setStage(id, s) {
  const t = Date.now();
  if (s === "none") delete S.marks[id]; else S.marks[id] = { s, t };
  render();
  try { await api("/api/marks", { method: "POST", body: JSON.stringify({ id, s, t }) }); } catch (e) { $("msg").textContent = "Could not save: " + e.message; }
}

function renderHealth() {
  const box = $("health"); box.replaceChildren();
  for (const [name, h] of Object.entries(S.data.health || {})) {
    const days = Object.keys(S.yield).sort().slice(-7), n = days.reduce((a, d) => a + ((S.yield[d] || {})[name] || 0), 0);
    const bad = h.failures >= 3 || h.status === "error" || h.status === "blocked";
    box.append(el("div", bad ? "bad" : "", `${name}: ${h.status || "?"}${h.error ? " (" + h.error + ")" : ""} · last ok ${ago(h.last_success) || "never"} · ${n} new in 7 days`));
  }
}

/* ---- alerts (Web Push). The service worker needs the code to ask what to say, so a copy is kept in IndexedDB. ---- */
const idb = () => new Promise((res, rej) => { const r = indexedDB.open("desk", 1); r.onupgradeneeded = () => r.result.createObjectStore("kv"); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
async function idbToken(v) { try { const db = await idb(); db.transaction("kv", "readwrite").objectStore("kv").put(v, "token"); } catch (e) { /* alerts are optional */ } }
const b64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
const canPush = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

async function pushRefresh() {
  const btn = $("pushbtn"), msg = $("pushmsg");
  if (!canPush()) { msg.textContent = /iPhone|iPad/.test(navigator.userAgent) ? "On iPhone: Share, Add to Home Screen, open the app from there, then turn alerts on." : "This browser cannot show alerts."; btn.hidden = true; return; }
  if (Notification.permission === "denied") { msg.textContent = "Notifications are blocked for this site in the browser settings."; btn.hidden = true; return; }
  const reg = await navigator.serviceWorker.getRegistration("/"), cur = reg ? await reg.pushManager.getSubscription() : null;
  msg.textContent = cur ? "Alerts are on for this device." : "Get a notification when a new flat matches."; btn.textContent = cur ? "Turn off alerts" : "Turn on alerts"; btn.hidden = false;
}
async function pushToggle() {
  $("pushbtn").disabled = true;
  try {
    const reg = await navigator.serviceWorker.ready, cur = await reg.pushManager.getSubscription();
    if (cur) { await api("/api/push/subscribe", { method: "DELETE", body: JSON.stringify({ endpoint: cur.endpoint }) }); await cur.unsubscribe(); }
    else {
      if ((await Notification.requestPermission()) !== "granted") { $("pushmsg").textContent = "Permission was not given."; return; }
      const key = (await (await fetch("/api/push/key")).json()).key;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64u(key) });
      await api("/api/push/subscribe", { method: "POST", body: JSON.stringify({ subscription: sub.toJSON() }) });
      await idbToken(S.token);
    }
  } catch (e) { $("pushmsg").textContent = "Could not change alerts: " + e.message; }
  $("pushbtn").disabled = false; pushRefresh();
}

async function runRefresh() {
  try { const { last } = await api("/api/run"); $("runmsg").textContent = `Last run: ${last.status}${last.conclusion ? " (" + last.conclusion + ")" : ""} ${ago(last.updated)}`; $("runbtn").disabled = last.status === "in_progress" || last.status === "queued"; }
  catch (e) { $("runmsg").textContent = e.message; }
}

$("tabs").addEventListener("click", (e) => { const t = e.target.closest("button"); if (!t) return; S.f.tab = t.dataset.tab; for (const b of $("tabs").children) b.setAttribute("aria-selected", String(b === t)); $("msg").textContent = ""; render(); });
for (const [id, key] of [["source", "source"], ["poster", "poster"]]) $(id).addEventListener("change", (e) => { S.f[key] = e.target.value; render(); });
$("near").addEventListener("change", (e) => { S.f.near = e.target.checked; render(); });
$("q").addEventListener("input", (e) => { S.f.q = e.target.value; render(); });
$("galx").addEventListener("click", () => $("gal").close());
$("menu").addEventListener("click", () => { $("code").value = S.token; $("dlg").showModal(); pushRefresh(); if (S.token) runRefresh(); });
$("dlgcancel").addEventListener("click", () => $("dlg").close());
$("dlgsave").addEventListener("click", () => { S.token = $("code").value.trim(); ls.set("ld-token", S.token || null); idbToken(S.token); $("dlg").close(); load(); });
$("pushbtn").addEventListener("click", pushToggle);
$("pushtest").addEventListener("click", async () => { try { const r = await api("/api/push/test", { method: "POST" }); $("pushmsg").textContent = `Test sent to ${r.sent} of ${r.devices} device(s).`; } catch (e) { $("pushmsg").textContent = e.message; } });
$("runbtn").addEventListener("click", async () => { try { await api("/api/run", { method: "POST" }); $("runmsg").textContent = "Run started."; $("runbtn").disabled = true; } catch (e) { $("runmsg").textContent = e.message; } });
if ("serviceWorker" in navigator) addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
load(); setInterval(() => { if (S.token && !document.hidden) load(); }, 120000);
```
- [ ] **Step 4:** `node --check desk/public/app.js` (syntax only; ES module import statements are accepted by `--check` on `.js` only if the package says module: add `"type":"module"` already in `desk/package.json`). Commit `feat(desk): page`.

---

### Task 9: Service worker, manifest, headers, icons

**Files:** Create `desk/public/sw.js`, `manifest.webmanifest`, `_headers`, `robots.txt`, `scripts/make_pwa_icons.py`, `desk/public/icons/*.png`.

- [ ] **Step 1:** `desk/public/sw.js` (the job desk's, with these differences: `VER = "logement-v1"`, `SHELL = ["/", "/app.css", "/app.js", "/format.js", "/icons/icon-192.png"]`, notification title "Logement", the pending body default "A new flat matches", and the click handler opens `data.url`). Full file:
```js
// Rule 1: /api/* is never cached or touched. Rule 2: everything else is network-first, last copy when offline.
// A push carries no text: on a push this worker asks /api/pending (with the access code kept in IndexedDB) what to say.
const VER = "logement-v1";
const SHELL = ["/", "/app.css", "/app.js", "/format.js", "/icons/icon-192.png"];

self.addEventListener("install", (e) => { e.waitUntil(caches.open(VER).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VER).map((k) => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", (e) => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  e.respondWith(fetch(r).then((res) => { if (res.ok) { const copy = res.clone(); caches.open(VER).then((c) => c.put(r, copy)); } return res; })
    .catch(() => caches.match(r).then((m) => m || (r.mode === "navigate" ? caches.match("/") : Response.error()))));
});

function readToken() {
  return new Promise((resolve) => {
    const open = indexedDB.open("desk", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("kv");
    open.onerror = () => resolve("");
    open.onsuccess = () => { const g = open.result.transaction("kv").objectStore("kv").get("token"); g.onsuccess = () => resolve(g.result || ""); g.onerror = () => resolve(""); };
  });
}

self.addEventListener("push", (e) => {
  e.waitUntil((async () => {
    let body = "A new flat matches", url = "/";
    try {
      const token = await readToken();
      if (token) { const r = await fetch("/api/pending", { headers: { "x-token": token }, cache: "no-store" }); if (r.ok) { const p = await r.json(); if (p.body) body = p.body; if (typeof p.url === "string") url = p.url; } }
    } catch (err) { /* keep the generic line */ }
    await self.registration.showNotification("Logement", { body, icon: "/icons/icon-192.png", badge: "/icons/icon-192.png", tag: "logement", renotify: true, data: { url } });
  })());
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(url.startsWith("https://") ? self.clients.openWindow(url) : self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((ws) => { for (const w of ws) { if ("focus" in w) return w.focus(); } return self.clients.openWindow("/"); }));
});
```
- [ ] **Step 2:** `manifest.webmanifest`: copy the job desk's (`C:\Users\youss\OneDrive\Documents\Claude\ai-job-search\jobdesk\public\manifest.webmanifest`) changing `name`/`short_name` to `Logement`, `description` to `Rental listings that match, with alerts.`. `robots.txt`: `User-agent: *` / `Disallow: /`. `_headers`:
```
/*
  X-Robots-Tag: noindex, nofollow
  Referrer-Policy: no-referrer
  X-Content-Type-Options: nosniff
  Content-Security-Policy: default-src 'self'; img-src https: data:; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'
/sw.js
  Cache-Control: no-cache
  Service-Worker-Allowed: /
/manifest.webmanifest
  Cache-Control: no-cache
  Content-Type: application/manifest+json
/icons/*
  Cache-Control: public, max-age=86400
```
- [ ] **Step 3:** Copy `scripts/make_pwa_icons.py` from the job repo (same path as above, under `scripts/`), change its `OUT` to `desk/public/icons` and its docstring to say Logement; keep the drawing. Run `.venv/Scripts/python -m pip install -q pillow && .venv/Scripts/python scripts/make_pwa_icons.py` (Pillow is for this one-off only: do not add it to the requirements files). Expected: four `wrote ...png` lines. Commit `feat(desk): service worker, manifest, headers, icons`.

---

### Task 10: Workflows

**Files:** Modify `.github/workflows/ci.yml`, `run.yml`. Create `.github/workflows/deploy-desk.yml`.

- [ ] **Step 1: `ci.yml`:** add a second job after `test`:
```yaml
  desk:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - run: node --test
```
- [ ] **Step 2: `run.yml`:** in the job `env:` add `DESK_URL: ${{ secrets.DESK_URL }}` and `PUSH_TOKEN: ${{ secrets.PUSH_TOKEN }}`. After the `Save state` step add:
```yaml
      - name: Publish to the desk (stores the listings, sends the phone alerts)
        if: inputs.mode != 'check' && env.DESK_URL != ''
        run: python scripts/publish.py
```
(If publishing fails the run fails and the failure alert fires; nothing is lost because "already notified" lives in the desk's KV and the next run republishes everything.)

- [ ] **Step 3: `deploy-desk.yml`** (deploys only when the desk's code changes):
```yaml
name: deploy-desk

# The desk code is deployed only when it changes (Cloudflare Pages free plan allows about 500 deployments a month); listings travel through /api/ingest.
on:
  push:
    branches: [main]
    paths:
      - "desk/**"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: deploy-desk
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
      CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - name: Deploy the desk
        if: env.CLOUDFLARE_API_TOKEN != ''
        working-directory: desk
        run: npx --yes wrangler@3 pages deploy public --branch main --commit-dirty=true
      - name: No Cloudflare token
        if: env.CLOUDFLARE_API_TOKEN == ''
        run: echo "::warning::CLOUDFLARE_API_TOKEN is not set, nothing deployed."
```
(`pages deploy` reads the project name from `desk/wrangler.toml`.)
- [ ] **Step 4:** Validate all workflow YAML with PyYAML as in plan 1 Task 14 Step 5; commit `ci: node tests, publish step, desk deploy workflow`.

---

### Task 11: Keys and Cloudflare configuration files

**Files:** Create `scripts/make_vapid.mjs`, `desk/wrangler.toml`. Modify `.gitignore` (add `.vapid.json`, `.desk_secrets.json`).

- [ ] **Step 1:** `scripts/make_vapid.mjs` (one-off; prints a key pair and writes the private values to the gitignored `.vapid.json`):
```js
import { webcrypto as c } from "node:crypto";
import { writeFileSync } from "node:fs";
const b64u = (b) => Buffer.from(b).toString("base64url");
const kp = await c.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
const pub = b64u(await c.subtle.exportKey("raw", kp.publicKey));
const jwk = await c.subtle.exportKey("jwk", kp.privateKey);
const rnd = () => b64u(c.getRandomValues(new Uint8Array(24)));
writeFileSync(".vapid.json", JSON.stringify({ vapid_public: pub, vapid_private_jwk: jwk, api_token: rnd(), push_token: rnd() }, null, 2));
console.log("wrote .vapid.json (gitignored). VAPID_PUBLIC =", pub);
```
Run `node scripts/make_vapid.mjs`; expected `wrote .vapid.json ...`. Confirm `git status` does not list it.

- [ ] **Step 2:** `desk/wrangler.toml` (filled in at Task 12 with the real project name, KV id and the public key; only public values go in it):
```toml
name = "<pages-project-name>"
pages_build_output_dir = "public"
compatibility_date = "2026-11-01"

[[kv_namespaces]]
binding = "DESK"
id = "<kv-namespace-id>"

[vars]
VAPID_PUBLIC = "<vapid-public-key>"
VAPID_SUBJECT = "https://<pages-project-name>.pages.dev"

# "Run now": the desk asks the cron Worker, so the GitHub token never lives in Pages
[[services]]
binding = "RUNNER"
service = "logement-cron"
```
Commit `chore: key generator and desk config template` (the file keeps placeholders until Task 12).

---

### Task 12: Create the Cloudflare resources and deploy (needs the owner's go-ahead for each outward step)

These create things in the owner's Cloudflare and GitHub accounts. Do each only after the owner agrees; wrangler is already logged in on this PC (OAuth).

- [ ] **Step 1: Worker first** (the Pages project references it): GitHub fine-grained token, created by the OWNER in the browser: repository `logement-desk` only, permission "Actions: Read and write", 90-day expiry. Then:
```bash
cd cron-worker && npx wrangler@3 deploy
printf '%s' "<the token>" | npx wrangler@3 secret put GITHUB_TOKEN
printf '%s' "<ntfy topic>" | npx wrangler@3 secret put NTFY_TOPIC
```
Expected: `Deployed logement-cron` with the cron `*/10 * * * *`. Note the token expiry date in `HANDOFF.md`.
- [ ] **Step 2: KV and Pages project:**
```bash
cd ../desk && npx wrangler@3 kv namespace create DESK
npx wrangler@3 pages project create logement-$(node -e "console.log(require('crypto').randomBytes(3).toString('hex'))") --production-branch main
```
Edit `desk/wrangler.toml`: the project name, the KV `id`, `VAPID_PUBLIC` from `.vapid.json`.
- [ ] **Step 3: Pages secrets and first deploy:**
```bash
node -e "const j=require('../.vapid.json');process.stdout.write(j.api_token)" | npx wrangler@3 pages secret put API_TOKEN
node -e "const j=require('../.vapid.json');process.stdout.write(j.push_token)" | npx wrangler@3 pages secret put PUSH_TOKEN
node -e "const j=require('../.vapid.json');process.stdout.write(JSON.stringify(j.vapid_private_jwk))" | npx wrangler@3 pages secret put VAPID_PRIVATE
npx wrangler@3 pages deploy public --branch main --commit-dirty=true
```
Expected: a `https://<project>.pages.dev` URL. Check `curl -s https://<project>.pages.dev/api/push/key` returns the public key and `curl -s -o /dev/null -w "%{http_code}" https://<project>.pages.dev/api/listings` prints `401`.
- [ ] **Step 4: GitHub secrets** (the values never printed): `DESK_URL` = the Pages URL, `PUSH_TOKEN` and the optional `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` (for `deploy-desk.yml`; the owner creates a Cloudflare token with "Cloudflare Pages: Edit"):
```bash
gh secret set DESK_URL -R youssef-abd/logement-desk --body "https://<project>.pages.dev"
node -e "process.stdout.write(require('./.vapid.json').push_token)" | gh secret set PUSH_TOKEN -R youssef-abd/logement-desk
```
- [ ] **Step 5:** Commit `desk/wrangler.toml` (project name, KV id and public key are not secrets). Give the owner the access code (`api_token`) once, in the terminal only, and tell them to store it in a password manager.

---

### Task 13: Acceptance

- [ ] **Step 1: Automatic runs.** Wait for the next `*/10` minute; `gh run list -R youssef-abd/logement-desk --workflow run.yml --limit 3` shows a run started by `workflow_dispatch` and a `Publish to the desk` step with `ok: True`. Expected on the first ingest: `seeded: True`, `fresh: 0` (silent).
- [ ] **Step 2: The desk loads.** Open the desk URL in a browser, Settings, enter the access code, Save. Expected: the listings appear with thumbnails and flag chips; "updated N min ago" is under 15. Confirm in the browser (not only with curl) that thumbnails from each source show; record any source whose photos show the placeholder in `HANDOFF.md`.
- [ ] **Step 3: Stages sync.** Mark one flat Contacted on the phone; reload on the laptop; it is under Following.
- [ ] **Step 4: Alerts.** On the phone, Settings, Turn on alerts (iPhone: install to the home screen first), then Send a test. Expected: a notification "Test alert: ..." arrives. Then wait for a real new flat (or temporarily delete one id from KV `notified` with `npx wrangler@3 kv key put notified "[]" --binding DESK` ... only if the owner agrees) and confirm the notification names the flat and a tap opens the listing.
- [ ] **Step 5: Failure paths.** Confirm the health panel lists both sources. (Optional, with the owner's agreement:) disable the Worker cron for 70 minutes to see the staleness ntfy alert.
- [ ] **Step 6: Run now.** Settings, Start a run: the run appears on GitHub within a minute; pressing it again says a run is in progress or to wait.
- [ ] **Step 7:** For a few days, read `state/` commit frequency (`git log --oneline | head`): it should be a handful a day. If commits happen on every run, find which state field changes and fix it.

---

### Task 14: Docs

**Files:** Modify `HANDOFF.md`, `docs/superpowers/specs/2026-11-15-logement-desk-design.md`, `README.md`.

- [ ] **Step 1: `HANDOFF.md`:** new section "Plan 2: automatic runs and the desk" with: the architecture line (Worker cron -> run.yml -> publish -> `/api/ingest` -> KV -> desk), where each secret lives by NAME (Worker: `GITHUB_TOKEN`, `NTFY_TOPIC`; Pages: `API_TOKEN`, `PUSH_TOKEN`, `VAPID_PRIVATE`; GitHub: `PROFILE_JSON`, `DESK_URL`, `PUSH_TOKEN`, `NTFY_TOPIC`, optional `CLOUDFLARE_*`; local gitignored `.vapid.json`), the GitHub token expiry date and how to renew (`cd cron-worker; npx wrangler@3 secret put GITHUB_TOKEN`), the photo-hotlink findings from Task 1 and Task 13, how to add a source (spec section 16, plus add its domain to `HOSTS` in `desk/lib/validate.js`), and these gotchas: the Pages deployment limit (do not deploy per run), `notified` lives in KV (to re-alert, edit that key), the first ingest is silent, the desk data is behind the access code, and the project name/KV id in `desk/wrangler.toml` are public by design.
- [ ] **Step 2: Spec:** append `## 18. Amendments from plan 2` listing the eight decisions at the top of this plan, one line each.
- [ ] **Step 3: `README.md`:** replace the "Current state" line with: `Current state: runs every ~10 minutes, alerts the phone and shows a private desk. See HANDOFF.md.`
- [ ] **Step 4:** Commit and push. Update the owner's memory note for the housing project (`housing-app-project.md`) with the final state.
