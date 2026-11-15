import json
import os
from datetime import datetime


def empty():
    return {"listings": {}, "health": {}}


def load(path):
    if not os.path.exists(path):
        return empty()
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, state):
    """Write to a temp file then rename, so a crash never leaves half a file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def age_minutes(now, then):
    return (datetime.fromisoformat(now) - datetime.fromisoformat(then)).total_seconds() / 60


def prune(state, now, max_age_days):
    limit = max_age_days * 24 * 60
    old = [k for k, e in state["listings"].items() if age_minutes(now, e["last_seen"]) > limit]
    for k in old:
        del state["listings"][k]
    return len(old)
