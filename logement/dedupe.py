from . import store


def same_flat(a, b, rent_tol=10.0, surface_tol=1.0):
    """Both arguments are listing dicts. All of rent, surface and postal code must be known on both sides.
    Two listings from one source are never merged when either poster is an agency (identical units exist)."""
    for k in ("rent_cc", "surface_m2", "postal_code"):
        if a.get(k) is None or b.get(k) is None:
            return False
    if a["source"] == b["source"] and "agence" in (a.get("poster"), b.get("poster")):
        return False
    return (abs(a["rent_cc"] - b["rent_cc"]) <= rent_tol
            and abs(a["surface_m2"] - b["surface_m2"]) <= surface_tol
            and a["postal_code"] == b["postal_code"])


def find_match(entries, d):
    for key, e in entries.items():
        if e["status"] == "active" and e["listing"] is not None and same_flat(e["listing"], d):
            return key
    return None


def process(state, kept, ok_sources, now, profile):
    """Update state with the listings that passed the filter; return the listings that are new (to alert)."""
    entries = state["listings"]
    touch, stale = profile["touch_minutes"], profile["stale_after_minutes"]
    seen, alerts = set(), []
    for l in kept:
        key = l.key
        seen.add(key)
        e = entries.get(key)
        if e is not None:
            if e["status"] == "stale":
                e["status"] = "active"
                e["last_seen"] = now
            elif store.age_minutes(now, e["last_seen"]) >= touch:
                e["last_seen"] = now
            continue
        d = l.to_dict()
        d["description"] = d["description"][:500]
        match = find_match(entries, d)
        if match:
            entries[key] = {"dup_of": match, "first_seen": now, "last_seen": now, "status": "active",
                            "listing": None, "also": [], "notified": True}
            entries[match]["also"].append(key)
            continue
        entries[key] = {"dup_of": None, "first_seen": now, "last_seen": now, "status": "active",
                        "listing": d, "also": [], "notified": False}
        alerts.append(l)
    for key, e in entries.items():
        if key in seen or e["dup_of"] or e["status"] == "stale":
            continue
        if key.split(":", 1)[0] in ok_sources and store.age_minutes(now, e["last_seen"]) >= stale:
            e["status"] = "stale"
    return alerts
