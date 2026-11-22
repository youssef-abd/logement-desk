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
- `data/cities.json` (built by `python scripts/make_cities.py`, run from the PC): 11 cities with postcodes and the per-source options that really returned listings there; `desk/public/cities.json` is the catalogue shown in Settings. Lyon is the profile's own hand-tuned setup.
- The desk stores the chosen cities in KV (`/api/search`, max 6); the run reads them (`logement/cities.py: desk_cities`, falls back to the profile's `cities`, then Lyon). `run()` makes one pass per city per source with that city's options; a failing city keeps the others; listings carry `city`. ParuVendu's city pages show only the département, so area is attributed by city, not postcode.

## What exists
- `logement/`: the pipeline. `python -m logement.run --check --show --profile profile.json` is the local dry run; `--strict` exits 1 if any source is not ok.
- State: `state/seen_listings.json`, committed by `scripts/save_state.sh` only when it changed.
- Workflows: `ci` (tests on push), `run` (by hand: `gh workflow run run.yml -f mode=full|check`), `contract` (weekly live check).
- Tests: `.venv/Scripts/python -m pytest -q` (expect 75 passed).

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
