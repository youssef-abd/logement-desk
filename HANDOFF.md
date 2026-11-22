# logement-desk: handoff

Read this first. State on 2026-11-22: the pipeline, the Cloudflare cron Worker (runs every 10 minutes, deep sweep on the hourly tick), the Pages desk (photos, stages, filters, city picker, Web Push code) and many sources are live. Tests: 163 Python (`.venv/Scripts/python -m pytest -q`), 43 JS (`node --test desk/tests/*.test.mjs`). Phone alerts and the phone test are still postponed (no device subscribed yet). Sections "Sources today", "Collect vs match" and "Cities" below are the current picture; the older "Source facts" were verified on 2026-11-15.

## Sources today (cloud, no PC)
- Work: Bien'ici, ParuVendu, Foncia (through the desk relay, `relay: true`), ImmoJeune (private ads each run; residence units via each residence page on deep runs; deep paging follows the page's `rel="next"` link), Studapart (headless Chrome via Playwright, `deep_only` in the profile so Chrome is installed only on deep runs), La Carte des Colocs (fallback only for the owner), Leboncoin (mostly blocked: about 21 of 24 recent runs).
- Built but off (blocked from the GitHub runner): PAP (works from the PC and through the desk relay from some Cloudflare data centres only), Logic-Immo (works from the PC with a Chrome-fingerprint request; page 1 of each search embeds 25 listings as JSON in `__UFRN_FETCHER__`). SeLoger is blocked even from the PC (real Edge too).
- Dead ends, do not retry: Scrapling and headless Chrome from GitHub (IP block, not fingerprint), Cloudflare placement hints for PAP, spoofing headers/TLS or cycling browser fingerprints against Datadome (the assistant is blocked from doing it), Locservice (teaser only), Jinka (needs an account), FJT directory (no prices).
- The desk relay (`/api/relay`, x-push-token, hosts allowlisted in `desk/lib/relay.js`) fetches pages from Cloudflare's network for sites that refuse GitHub.
- The desk is NOT deployed by `deploy-desk.yml` (no Cloudflare token secret): deploy by hand with `cd desk && npx wrangler pages deploy public --branch main`. Bump `VER` in `desk/public/sw.js` when the interface files change.

## Collect vs match
- Profile `collect` (private): the net the sources are asked with (currently up to 1200 EUR, furnished or not, all kinds). The top-level `max_rent_cc`, `near_miss_margin`, `furnished`, `kinds` are the owner's own criteria. `Listing.match` says whether a listing meets them; only `match` listings raise phone alerts (desk `ingest.js` checks it). Deploy the desk BEFORE widening `collect`, otherwise an old desk would alert on everything.
- The desk filters (max rent slider, furnished, room type, city) start from `criteria` in the payload and are saved per browser.

## Cities
- Any French commune works. In Settings the owner types a name; the desk (`/api/city-search`, a proxy of geo.api.gouv.fr) returns city records `{key, name, dept, postal_codes, lat, lng, region}`; the choice is stored in KV (`/api/search`). ONE city at a time: `MAX_CITIES` in `desk/lib/search.js` is the only number to raise for 2 or 3.
- The run (`logement/cities.py`) reads the choice (`desk_cities`, fallback: profile `cities`, then Lyon) and builds each source's requests from the record at run time (`options_for`: one address pattern per source; Bien'ici zone ids come from its suggest service). Lyon stays the profile's own hand-tuned setup. `data/cities.json` (from `python scripts/make_cities.py`, run from the PC) holds 11 cities whose options were VERIFIED against the real sites; a verified entry wins over the generated options.
- `run()` makes one pass per city per source; a failing city keeps the others; listings carry `city`; a site that gives no area gets the searched city's name. The payload's `cities[].sources` says per source what the last run found (`ok`/`none`/`blocked`/`error`/`n/a`, with counts); Settings shows it, so a source that finds nothing for a town is visible, not silent.
- Switching city leaves the old city's listings active for about 12 hours; the desk defaults its city filter to the collected city. The Where map and area ranking are Lyon's and are hidden for other cities.
- Tested end to end on 2026-11-22 with Angers (not in the registry): picked in the UI, collected on the cloud, shown on the desk; the test listings were then purged from the state.

## What exists
- `logement/`: the pipeline. `python -m logement.run --check --show --profile profile.json` is the local dry run; `--strict` exits 1 if any source is not ok.
- State: `state/seen_listings.json`, committed by `scripts/save_state.sh` only when it changed.
- Workflows: `ci` (tests on push), `run` (by hand: `gh workflow run run.yml -f mode=full|check`), `contract` (weekly live check).
- Tests: `.venv/Scripts/python -m pytest -q` (expect 75 passed).

## Phone layout (desk)
- One breakpoint, `max-width: 900px`, in `desk/public/app.css` (the last block). Phone: top bar with Settings, bottom tab bar (New / Saved / Following / Closed), search box + "Filters (n)" + "Map and areas" buttons (both fold away; `ui` and `mobileBar()` in `app.js`), listing cards with a full-width photo and 44px controls, every form field 16px (iOS does not zoom), Settings dialog opens focused on Close (no keyboard pop-up), photo gallery swipes.
- Checked in Edge at 360, 390 and 768 px: no sideways scroll, no touch target under 40px, desktop unchanged. Bump `VER` in `desk/public/sw.js` after interface changes, then deploy by hand with wrangler.

## Taken-down ads
- Besides the 12-hour "not seen" rule, the hourly deep run opens listing pages itself (`logement/liveness.py`, profile `liveness: {enabled, max_per_run (80), recheck_hours (6)}`, all optional): least recently checked first, never-checked oldest first. A gone listing is closed at once (`status stale`, `gone` timestamp) and revives if the results show it again.
- Only signals seen on the real sites count: Bien'ici single-ad API `status.onTheMarket == false`; ImmoJeune redirect to a search page (a residence unit is gone when its page no longer offers it); HTTP 404/410 or a redirect to another path elsewhere. A redirect to a login page is "unknown". Leboncoin, ParuVendu and La Carte des Colocs closed ads still load normally, so those are never guessed gone. Foncia is checked through the desk relay (404 only).
- Validated 2026-11-22 on real data: Bien'ici 6/6 live and 6/6 closed separated, ImmoJeune 6/6 and 6/6; a Studapart live ad that redirects to `/fr/login` made the login rule necessary.

## Rules
- The repo and its Actions logs are PUBLIC. Logs print counts and status words only. Never print listing text, the profile or secrets.
- The real profile is the Actions secret `PROFILE_JSON` and the gitignored `profile.json`. The repo only has `profile.example.json`.
- No proxies, no IP rotation. A blocked source is retried once, then cooled down.
- The tool never contacts landlords.
- Decision (owner, 2026-11-15): state is committed to this PUBLIC repo. `state/seen_listings.json` holds the listings that matched, so the area, rent band and kind of flat are inferable from it. Accepted knowingly; the alternative (a private state repo with a token secret) is documented in the final review and can be adopted later.

## Secrets (names only)
`PROFILE_JSON` (required), `NTFY_TOPIC` (optional, failure alerts).

## Source facts (verified 2026-11-15)
- Bien'ici: JSON endpoint; filter key `isFurnished` (not `furnished`); `price` includes charges.
- Leboncoin: `lbc==1.1.9`, server-side `real_estate_type=["2"]` and `furnished=["1"]` (string lists); poster from `ad.raw["owner"]["type"]`; charges are added to the price only when `charges_included` is explicitly "2".
- La Carte des Colocs: JSON-LD, needs `curl_cffi` browser impersonation; coloc only (disabled by default). The parser assumes `about` and `offers` are dicts and `image` is a string (live shape).
- ParuVendu: HTML cards, plain GET; last priority. Poster: `pseudoinfo` span "Particulier", else agency; a card with `alt="pro : ..."` is an agency. The price must be read after the `<!-- Prix -->` comment (a photo-count digit precedes it).
- Blocked from the cloud: PAP, AVendreALouer (403). SeLoger, Logic-Immo: DataDome.

## Gotchas
- Status `stale` means "not in the latest results", not "taken": the poll reads only the newest page.
- `last_seen` is rewritten at most every `touch_minutes`, on purpose (no commit on unchanged runs).
- When a source returns data but no prices, the run reports `DriftError`: the site changed its format.
- Carte des Colocs: a schema.org array variant of `about`/`offers`/`image` would break the parser and need hardening; the weekly contract check should catch it.
- Parking guard (`reject_title_patterns`) applies only when the room count is unknown AND the title does not say studio/t1/f1.
- `find_match` only matches ACTIVE entries; a stale listing seen again refreshes `last_seen`.
- Cooldown is time-based (`poll.block_cooldown_minutes`, state field `cooldown_until`); `consecutive_failures` is capped at `fail_threshold + 1` so an outage does not rewrite state every run.
- The idempotency test reruns 5 minutes later, so time-dependent state changes are caught.
- The first real run marks every kept listing as not yet notified (up to ~60), so the push step of plan 2 must seed or batch the first run.
- A repost more than `stale_after_minutes` after the original left the newest page alerts again; ParuVendu and La Carte des Colocs have no postal code, so they never dedupe.
- `--strict` (weekly contract check) fails while a source is in cooldown or returns nothing, by design.

## Next
Phone test of Web Push; widen the profile (T2, suburbs) if the volume is still thin; a residential proxy is the only thing seen to unblock Leboncoin/SeLoger/PAP/Logic-Immo from the cloud (paid, not chosen). Adding sources: spec section 16. Adding a city: add its name to `CANDIDATES` in `scripts/make_cities.py` and run it.
