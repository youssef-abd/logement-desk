import argparse
import copy
import importlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

from . import store
from .config import load_profile
from .dedupe import process
from .errors import Blocked, DriftError, EmptyResult
from .export import build_payload
from .filters import hard_filter
from .flags import apply_flags

DEFAULT_HEALTH = {"consecutive_failures": 0, "blocked_runs": 0, "cooldown_until": None,
                  "last_success": None, "last_error": None}


def load_fetch(name):
    return importlib.import_module(f"logement.sources.{name}").fetch


def check_drift(listings, ratio, min_count=5):
    """Results that miss rent, url or id are a broken parser, not an empty market."""
    if len(listings) < min_count:
        return
    bad = sum(1 for l in listings if l.rent_cc is None or not l.url or not l.source_id)
    if bad / len(listings) > ratio:
        raise DriftError(f"{bad}/{len(listings)} listings miss rent, url or id")


def _fetch_with_retry(fetch, profile, sleep):
    try:
        return fetch(profile)
    except Blocked:
        sleep(profile["poll"]["retry_wait_s"])
        return fetch(profile)


def _record_success(h, now, profile):
    h["consecutive_failures"] = 0
    h["blocked_runs"] = 0
    h["cooldown_until"] = None
    h["last_error"] = None
    if h["last_success"] is None or store.age_minutes(now, h["last_success"]) >= profile["touch_minutes"]:
        h["last_success"] = now


def run(profile, state, now, fetchers=None, sleep=time.sleep, deep=False):
    fetch_profile = {**profile, **(profile.get("collect") or {}), **({"deep": True} if deep else {})}  # sources are asked with the wide net
    fetchers = fetchers or {}
    state.setdefault("listings", {})
    health = state.setdefault("health", {})
    threshold = profile["health"]["fail_threshold"]
    report, kept_all, ok, newly_failing = {}, [], set(), []
    for name, opts in profile["sources"].items():
        if not opts.get("enabled"):
            continue
        if opts.get("deep_only") and not deep:  # costly sources (a real browser) run on the hourly deep sweep only
            report[name] = {"status": "skipped"}
            continue
        h = health.setdefault(name, dict(DEFAULT_HEALTH))
        if h["cooldown_until"] and store.age_minutes(now, h["cooldown_until"]) < 0:
            report[name] = {"status": "cooldown"}
            continue
        fetch = fetchers.get(name) or load_fetch(name)
        try:
            items = _fetch_with_retry(fetch, fetch_profile, sleep)
            check_drift(items, profile["health"]["drift_ratio"])
            if not items:
                raise EmptyResult("no listings")
            for l in items:
                l.found_by = name
                apply_flags(l, profile)
            kept = [l for l in items if hard_filter(l, profile)]
        except Blocked:
            h["consecutive_failures"] = min(h["consecutive_failures"] + 1, threshold + 1)
            h["blocked_runs"] += 1
            h["last_error"] = "blocked"
            if h["blocked_runs"] >= profile["poll"]["block_threshold"]:
                h["cooldown_until"] = (datetime.fromisoformat(now) + timedelta(
                    minutes=profile["poll"]["block_cooldown_minutes"])).isoformat(timespec="seconds")
                h["blocked_runs"] = 0
            report[name] = {"status": "blocked"}
        except Exception as e:  # one source must never stop the run; only the class name is kept (logs are public)
            h["consecutive_failures"] = min(h["consecutive_failures"] + 1, threshold + 1)
            h["last_error"] = type(e).__name__
            report[name] = {"status": "error", "error": type(e).__name__}
        else:
            _record_success(h, now, profile)
            kept_all += kept
            ok.add(name)
            report[name] = {"status": "ok", "fetched": len(items), "kept": len(kept)}
            continue
        if h["consecutive_failures"] == threshold:
            newly_failing.append(name)
    alerts = [l for l in process(state, kept_all, ok, now, profile) if l.match]
    store.prune(state, now, profile["prune_days"])
    attempted = [r for r in report.values() if r["status"] in ("ok", "error", "blocked")]
    failing = sorted(n for n, h in health.items() if h["consecutive_failures"] >= threshold)
    return {"alerts": alerts, "report": report, "failing": failing, "newly_failing": newly_failing,
            "run_failed": bool(attempted) and not ok}


def notify(topic, text):
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=text.encode("utf-8"), method="POST")
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="logement.run")
    ap.add_argument("--check", action="store_true", help="dry run: write nothing")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any enabled source did not answer ok")
    ap.add_argument("--show", action="store_true", help="print the new listings (local use only: Actions logs are public)")
    ap.add_argument("--deep", action="store_true", help="deep sweep: all result pages")
    ap.add_argument("--profile")
    ap.add_argument("--state", default="state/seen_listings.json")
    a = ap.parse_args(argv)

    profile = load_profile(a.profile)
    state = store.load(a.state)
    working = copy.deepcopy(state) if a.check else state
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res = run(profile, working, now, deep=a.deep)

    for name, r in res["report"].items():  # counts only: the Actions log of a public repo is public
        extra = f" fetched={r['fetched']} kept={r['kept']}" if r["status"] == "ok" else ""
        print(f"{name}: {r['status']}{extra}")
    active = sum(1 for e in working["listings"].values() if e["listing"] and e["status"] == "active")
    print(f"new={len(res['alerts'])} active={active}")
    if a.show:
        for l in res["alerts"]:
            print(f"  {l.rent_cc} EUR | {l.surface_m2} m2 | {l.district} | {l.poster} | {' '.join(l.flags + l.tags)} | {l.url}")
    if not a.check:
        store.save(a.state, state)
        os.makedirs("out", exist_ok=True)
        with open("out/desk.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(build_payload(state, res["report"], now, profile), f, ensure_ascii=False)
        topic = os.environ.get("NTFY_TOPIC", "")
        if topic and res["newly_failing"]:
            notify(topic, "logement-desk: source failing: " + ", ".join(res["newly_failing"]))
    if res["run_failed"]:
        return 1
    if a.strict and any(r["status"] != "ok" for r in res["report"].values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
