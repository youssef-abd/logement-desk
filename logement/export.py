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
