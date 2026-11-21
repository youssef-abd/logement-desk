"""Fetch a page through the desk's relay (Cloudflare's network), for sites that refuse GitHub's servers."""
import os
import urllib.error
import urllib.parse
import urllib.request

from .errors import Blocked


def get(url):
    base, token = os.environ.get("DESK_URL", "").rstrip("/"), os.environ.get("PUSH_TOKEN", "")
    if not base or not token:
        raise Blocked("relay not configured (DESK_URL / PUSH_TOKEN)")
    req = urllib.request.Request(f"{base}/api/relay?url={urllib.parse.quote(url, safe='')}",
                                 headers={"x-push-token": token, "User-Agent": "logement-run"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429, 502, 503):
            raise Blocked(f"relay HTTP {e.code}") from e
        raise
