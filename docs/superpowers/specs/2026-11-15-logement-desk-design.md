# logement-desk: design

Date: 2026-11-15. Status: draft for owner review. Single-user tool.

## 1. Goal

Find a rental in France fast. The tool polls several listing sources every few minutes, keeps only listings that match a private search profile, removes duplicates across sources, and pushes a phone alert whose tap opens the listing itself. A small desk page tracks what the owner did with each listing.

Success criteria:
- A new matching listing reaches the owner's phone within one poll interval plus about 2 minutes.
- The same flat never alerts twice (cross-source duplicates and reposts included).
- A broken or blocked source produces a failure alert naming that source; it never fails silently.
- Everything that depends on the search (area, budget, kind, flags, sources, cadence) is configuration, not code.

Non-goals (version 1): auto-contacting landlords, multi-user accounts, price-drop alerts, quiet hours, a message generator, a scoring model, PAP (blocked from cloud IPs), SeLoger and Logic-Immo (DataDome).

## 2. Configuration

All search behaviour lives in `profile.json`. The real file is stored as a GitHub Actions secret (the repo is public); the repo contains only `profile.example.json`. Fields (all required unless marked optional):

| Field | Meaning |
|---|---|
| `areas` | list of communes/districts per source (resolved to each source's zone ids) |
| `max_rent_cc` | hard ceiling, rent including charges |
| `near_miss_margin` | listings up to `max_rent_cc + margin` are kept and tagged `near-miss` |
| `kinds` | allowed kinds (`studio`, `t1`, `coloc`, `room`) with `max_surface_for_t1` |
| `min_surface_m2` | removes parkings, garages |
| `furnished` | `required`, `preferred` or `any`; unknown furnished status is kept with tag `furnished?` |
| `sources` | enabled sources, each with its own query options |
| `flags` | regex lists per flag (garant, visale, student_ok, student_no, agency_fees, charges_cc, charges_hc, availability, scam) |
| `poll` | interval (Worker cron expression), retry wait, cool-down thresholds |
| `max_photos` | photo URLs kept per listing (keeps state and `listings.json` small) |
| `gone_after_polls` | polls without a sighting before a listing is marked gone |
| `health` | consecutive-failure threshold per source, drift ratio |

## 3. Architecture

Mirrors the owner's ai-job-search system.

```
Cloudflare Worker cron (interval from profile)
  -> workflow_dispatch on GitHub Actions (concurrency group, no cancel)
     -> scripts/scrape_logement.py
        adapters -> normalize -> hard filter -> flags -> dedupe -> save state
     -> export desk/public/listings.json
     -> deploy Cloudflare Pages desk
     -> Web Push (payload-less) -> device fetches /api/pending -> notification
Failures -> ntfy (workflow step + Worker)
```

Order inside a run: scrape, dedupe, save state, push alerts, deploy. If the state save fails after retries, no alert is sent and the run fails; the next run finds the same listings still new.

Reused from the job desk (copied into this repo, the job repo is not modified): Worker cron pattern, workflow structure and failure-alert step, `save_state.sh` pattern, desk `functions/` (auth, push, status, run-now), service worker, manifest, VAPID push setup.

## 4. Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `sources/<name>.py` | `fetch(profile) -> [Listing]`; raises on failure; prints nothing | network |
| `listing.py` | `Listing` record | none |
| `filters.py` | hard filter and text flags | profile |
| `dedupe.py` | exact, cross-source and repost matching; gone detection | state |
| `store.py` | read/write `seen_listings.json` atomically, prune old entries | filesystem |
| `scrape_logement.py` | orchestration, per-source isolation, health counters, query log | all of the above |
| `export_site.py` | write `listings.json` for the desk | state |
| `desk/` | static page, KV-backed stages, push | Cloudflare |
| `cron-worker/` | scheduled dispatch, staleness check | GitHub API |

## 5. Data model

`Listing`: `source, source_id, url, title, rent_cc, charges, surface_m2, rooms, kind, district, furnished (True/False/None), poster (particulier/agence/None), published_at (nullable), description, photos`. Unknown values are `None`, never guessed. The orchestrator adds `first_seen`, `last_seen` and `found_by` (`source|query|area`).

State, `seen_listings.json` (git): per listing `first_seen, last_seen, sources[], dedupe_key, status (active/gone), notified`. Entries not seen for a long period are pruned. Commits happen only when state changed.

Desk marks, per listing: stage (`new, contacted, visit, dossier_sent, refused, gone`) and timestamps, stored in Cloudflare KV behind one access code (Pages secret). Not in git.

## 6. Sources (version 1)

| Source | Access | Notes |
|---|---|---|
| Bien'ici | plain GET to the site's JSON endpoint (`realEstateAds.json`), zone ids from its suggest endpoint | filters sent in the request; mostly agencies |
| Leboncoin | `lbc` library, category "locations" | mixes in parkings; filter by real-estate type and `min_surface_m2` |
| La Carte des Colocs | `curl_cffi` with browser impersonation, JSON-LD in the list page | coloc profile only; dates are availability dates |
| ParuVendu | plain GET, HTML cards | last priority, most fragile |

Verified from a GitHub runner on 2026-11-15 with one request each: Bien'ici, `lbc`, La Carte des Colocs and ParuVendu answered; PAP and AVendreALouer returned 403.

Rules: no proxies, no IP rotation. On 403/429 wait, retry once, then stop that source for the run and mark it blocked. After the configured number of consecutive blocked runs the source cools down for a configured number of runs.

## 7. Filter and flags

Hard filter, cheapest check first: area, kind, minimum surface, rent (`max_rent_cc`, near-miss band tagged), furnished policy. Flags are regex matches over title and description and are shown as chips; a flag never hides a listing. Negations ("sans garant", "garant non exigé", "pas d'étudiants") must not trigger the positive flag. Each adapter normalizes CC versus HC rent itself so the ceiling is comparable across sources.

## 8. Dedupe

1. Exact: same `(source, source_id)`.
2. Cross-source: rent within a tolerance, surface within about 1 m2, same district, title-word similarity (Jaccard threshold, as in the job desk's `tkey`). Merged into one row; best source first, others in `also`.
3. Repost: same source, same price, surface and district under a new id; not alerted again.

Principle: when unsure, do not merge. A visible duplicate is cheaper than a missed flat.

Gone detection: a listing not seen for `gone_after_polls` polls is marked gone and greyed on the desk.

## 9. Alerts and health

Web Push, payload-less: after a run with new matches the workflow calls the desk's protected push endpoint; the service worker fetches `/api/pending` and shows a short message built from structured fields (price, surface, district, poster). Tapping the notification opens the listing URL directly. ntfy is used only for failures: failed workflow step, Worker dispatch refused twice, Worker staleness check (last successful run older than a configured age).

Health: per source consecutive-failure counter and last-success time; schema drift (results returned but required fields `url, id, rent` missing above the configured ratio) is a distinct error. The desk shows a source-health panel.

## 10. Desk

Static Cloudflare Pages site, one access code. Each row shows a thumbnail (first photo) and opens a gallery of up to `max_photos` photos. Photos are never copied: only their URLs are stored, and the page loads them straight from the source with lazy loading and no referrer; a placeholder shows when an image fails to load. Each listing also has an "image search" link so a suspicious photo can be checked by hand. Newest-first list with flag chips; filters for source, particulier only, near-miss and furnished; stage select per listing; "no update for N days" hint on contacted listings; source-health panel; "Run now" button. Installable PWA.

## 11. Security and privacy

- Listing text is attacker-controlled: render as text only (no HTML injection), allow only https links on the source's own domain, build notifications from structured fields.
- The repo and its Actions logs are public: logs print counts and status codes only, never listing content, the profile or secrets; secrets are masked.
- The profile is a secret; the repo holds only the example. Desk data is public listing data behind a random Pages name and `noindex`.
- No auto-contact: the tool alerts, the owner writes to the landlord.

## 12. Error handling

Per-source isolation (a failing source is recorded, the run continues; the run fails only if all sources fail or save/deploy/push fails). Pinned `lbc` version, bumped by hand after a `check` run. State written atomically with retries. Concurrency group prevents overlapping runs.

## 13. Testing

| Layer | Check |
|---|---|
| Adapter unit tests | parse trimmed real fixtures to expected `Listing` records; drift detection when required fields are missing; no live network |
| Filter and flag tests | table-driven: parking, rent at the ceiling and one above, near-miss, unknown furnished, kind; French phrases with negations |
| Dedupe tests | cross-source merge, repost not re-alerted, similar but different flats kept apart |
| Idempotency | full pipeline on fixtures twice: second run yields zero alerts and zero state changes |
| `check` mode | real sources, writes nothing, prints per-source counts (workflow `mode=check`) |
| Weekly live contract test | each adapter live, asserts required fields present |
| CI | `pytest` on every push |
| End to end | one real run and a push received on the owner's phone |

Fixtures are trimmed to parsed fields and contain no personal data.

## 14. Verify during implementation

These are facts not yet confirmed; each is a task, not an assumption:
- Whether Bien'ici's `price` includes charges, and the field for charges.
- How `lbc` exposes real-estate type, furnished status and surface filters, and whether sort-by-newest can be relied on (promoted ads appeared out of order in an early test).
- Which Leboncoin and La Carte des Colocs fields carry price and publication or availability dates.
- Whether each source's photo URLs can be loaded from another site (hotlinking, expiring or signed URLs); Bien'ici `photos[].url`, `lbc` `images`, La Carte des Colocs JSON-LD `image` and ParuVendu card images are the fields to use.
- Request volume per poll that stays below each source's rate limits.

## 15. Build order

1. Skeleton: `Listing`, config loading, `store`, orchestrator with the `check` mode, CI.
2. Adapters and tests: Bien'ici, then Leboncoin (including the parkings filter), then La Carte des Colocs, then ParuVendu.
3. Filter, flags, dedupe, with their tests and the idempotency test.
4. Workflow, `save_state`, Worker cron, failure alerts.
5. Desk, push alerts, health panel, "Run now".
6. Acceptance: real run with a push on the phone, then a week of measurement (run duration, alert lag, per-source yield).

## 16. Adding sources later

More sources are planned after version 1. A new source touches only `sources/<name>.py`, its fixture, its tests and one entry under `sources` in the profile; nothing else changes. Procedure, in order:
1. Probe: plain GET, then browser impersonation, from the owner's machine, then from a GitHub runner (the `probe` workflow). Record status codes and sizes only.
2. Extraction check on one list page and one detail page: stable id, price (CC or HC), surface, furnished, date, photos, poster type.
3. Write the adapter, save a trimmed fixture, add the adapter, drift and filter tests.
4. Run `check` mode, enable it in the profile, watch its yield in the query log for a few days, and drop it if it only produces duplicates.

Candidates from the 2026-11-14/15 sweep, in rough priority: AVendreALouer (list JSON-LD works, detail pages blocked from the cloud), Entreparticuliers (Lyon URL not yet found), PAP (blocked from cloud IPs; would need a self-hosted runner on the owner's PC), Foncia, Immojeune, student-residence sites (Estudines, Studelites, Kley, Studea) and HousingAnywhere for the student angle. SeLoger and Logic-Immo stay out while DataDome blocks them. Sources the owner finds later follow the same procedure.

## 17. Amendments found while planning (2026-11-15)

- Code lives in the package `logement/` (run as `python -m logement.run`).
- `areas` is `{"allowed_postal_codes": [...]}`; per-source location settings live under `sources.<name>`.
- `gone_after_polls` is replaced by `stale_after_minutes` and `touch_minutes`; status `gone` is `stale` ("not in the latest results"), because only the newest page is polled and `last_seen` must not change every run.
- `reject_title_patterns` is a profile field (parking guard when the room count is unknown); it is skipped when the title says studio, t1 or f1.
- Dedupe: rent (10), surface (1 m2) and postal code, all known; no title similarity; two listings of one source are not merged when either poster is an agency.
- Dedupe matches only active entries; a stale listing seen again refreshes `last_seen`.
- The profile has an `agency_fees_no` flag; `agency_fees` is dropped when the text says "sans frais d'agence".
- Bien'ici uses `isFurnished`; `price` includes charges. Leboncoin is filtered server-side with `real_estate_type=["2"]` and `furnished=["1"]`.
- Leboncoin charges are added to the price only when `charges_included` is explicitly "2".
- ParuVendu: a card with an `alt="pro : ..."` logo and no `pseudoinfo` span is an agency.
- `found_by` is the source name; the per-query yield log moves to plan 2.
- Cooldown is time-based (`poll.block_cooldown_minutes`) and the failure counter is capped, so a persistent outage does not rewrite state on every run.
