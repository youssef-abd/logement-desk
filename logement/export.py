import statistics

KEEP = ("source", "url", "title", "rent_cc", "surface_m2", "rooms", "kind", "district", "postal_code",
        "furnished", "poster", "published_at", "flags", "tags", "photos")
MAX_LISTINGS = 1500


def build_payload(state, report, now):
    """The desk's data: canonical listings (no duplicate entries, no descriptions), newest first, plus per-source health."""
    rows = []
    for key, e in state["listings"].items():
        l = e.get("listing")
        if not l or e.get("dup_of"):
            continue
        row = {k: l.get(k) for k in KEEP}
        row["photos"] = (row["photos"] or [])[:3]
        row["tags"] = list(row["tags"] or [])
        rent, surf, pub = l.get("rent_cc"), l.get("surface_m2"), l.get("published_at")
        row["eur_m2"] = round(rent / surf, 1) if rent is not None and surf is not None and surf >= 9 else None
        row["posted"] = pub if isinstance(pub, str) and pub and not pub.startswith("1970") else e["first_seen"]
        row["similar"] = 0
        row.update(id=key, first_seen=e["first_seen"], last_seen=e["last_seen"], status=e["status"], also=len(e.get("also", [])))
        rows.append(row)
    rows.sort(key=lambda r: r["first_seen"], reverse=True)
    kept, groups = [], {}
    for r in rows:
        if r["poster"] == "agence" and None not in (r["rent_cc"], r["surface_m2"], r["postal_code"]):
            g = groups.setdefault((r["source"], r["poster"], r["rent_cc"], r["surface_m2"], r["postal_code"]), r)
            if g is not r:
                g["similar"] += 1
                continue
        kept.append(r)
    rows = kept
    by_area = {}
    for r in rows:
        if r["status"] == "active" and r["eur_m2"] is not None and r["postal_code"]:
            by_area.setdefault(r["postal_code"], []).append(r["eur_m2"])
    areas = {pc: {"n": len(v), "median_eur_m2": round(statistics.median(v), 1)} for pc, v in by_area.items()}
    for r in rows:
        a = areas.get(r["postal_code"])
        if a and r["eur_m2"] is not None and a["n"] >= 8:
            if r["eur_m2"] <= 0.5 * a["median_eur_m2"]:
                r["tags"].append("too-cheap")
            elif r["eur_m2"] <= 0.75 * a["median_eur_m2"]:
                r["tags"].append("cheap-for-area")
    health = {name: {"last_success": h.get("last_success"), "failures": h.get("consecutive_failures", 0),
                     "error": h.get("last_error"), "cooldown_until": h.get("cooldown_until"), "run": report.get(name)}
              for name, h in state.get("health", {}).items()}
    return {"updated": now, "listings": rows[:MAX_LISTINGS], "areas": areas, "health": health}
