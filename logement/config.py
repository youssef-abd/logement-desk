import json
import os

REQUIRED = [
    "areas", "max_rent_cc", "near_miss_margin", "kinds", "min_surface_m2", "furnished",
    "reject_title_patterns", "max_photos", "stale_after_minutes", "touch_minutes", "prune_days",
    "sources", "flags", "poll", "health",
]


def load_profile(path=None, env=None):
    """The PROFILE_JSON environment variable (the GitHub secret) wins over the file."""
    env = os.environ if env is None else env
    raw = env.get("PROFILE_JSON", "").strip()
    if raw:
        data = json.loads(raw)
    else:
        with open(path or "profile.json", encoding="utf-8") as f:
            data = json.load(f)
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError("profile is missing: " + ", ".join(missing))
    if data["furnished"] not in ("required", "preferred", "any"):
        raise ValueError("furnished must be required, preferred or any")
    return data
