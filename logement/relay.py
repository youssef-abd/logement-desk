"""Fetch a page through the desk's relay (Cloudflare's network), for sites that refuse GitHub's servers."""
import os
import urllib.error
import urllib.parse
import urllib.request

from .errors import Blocked


def get(url):
    own, token = os.environ.get("RELAY_URL", "").rstrip("/"), os.environ.get("PUSH_TOKEN", "")
    desk = os.environ.get("DESK_URL", "").rstrip("/")
    endpoint = f"{own}/" if own else (f"{desk}/api/relay" if desk else "")  # RELAY_URL: the stand-alone relay Worker (pinned to Europe)
    if not endpoint or not token:
        raise Blocked("relay not configured (RELAY_URL or DESK_URL, and PUSH_TOKEN)")
    req = urllib.request.Request(f"{endpoint}?url={urllib.parse.quote(url, safe='')}",
                                 headers={"x-push-token": token, "User-Agent": "logement-run"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429, 502, 503):
            raise Blocked(f"relay HTTP {e.code}") from e
        raise
