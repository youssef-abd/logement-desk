import re


def apply_flags(listing, profile):
    """Set listing.flags (sorted). A flag listed under another flag's `unless` is dropped when that one matches."""
    text = f"{listing.title}\n{listing.description}"
    specs = profile["flags"]
    matched = {name for name, s in specs.items() if any(re.search(pat, text, re.I) for pat in s["patterns"])}
    listing.flags = sorted(n for n in matched if not (set(specs[n].get("unless", [])) & matched))
