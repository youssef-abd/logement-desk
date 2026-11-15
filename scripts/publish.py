"""POST out/desk.json to the desk (/api/ingest). Prints counts only (Actions logs are public).
Env: DESK_URL, PUSH_TOKEN. Usage: python scripts/publish.py [path]"""
import json
import os
import sys
import urllib.error
import urllib.request


def publish(desk_url, push_token, path, urlopen=urllib.request.urlopen):
    data = open(path, "rb").read()
    req = urllib.request.Request(desk_url.rstrip("/") + "/api/ingest", data=data, method="POST",
                                 headers={"x-push-token": push_token, "content-type": "application/json", "user-agent": "logement-publish"})
    try:
        with urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"publish failed: HTTP {e.code}")
    except Exception as e:
        raise SystemExit(f"publish failed: {type(e).__name__}")


if __name__ == "__main__":
    out = publish(os.environ["DESK_URL"], os.environ["PUSH_TOKEN"], sys.argv[1] if len(sys.argv) > 1 else "out/desk.json")
    print({k: out.get(k) for k in ("ok", "stored", "fresh", "sent", "devices", "seeded")})
