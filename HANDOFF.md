# logement-desk: handoff

Read this first. State: plan 1 (the pipeline) is built, tested (77 offline tests) and verified live on GitHub Actions on 2026-11-15: a dry run and two full runs from a runner IP (Bien'ici and Leboncoin both answer; the first full run saved the state, the immediate second run made no commit). It is started by hand: `gh workflow run run.yml -f mode=full|check`. Plan 2 (Worker cron, desk, push alerts) is not started.

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

## Next (plan 2)
Cloudflare Worker cron (dispatches `run.yml`), Pages desk with photos and stages, Web Push, source-health panel, "Run now", per-query yield log. Before showing photos, verify that each source's photo URLs load from another site (spec section 14). Adding sources: spec section 16.
