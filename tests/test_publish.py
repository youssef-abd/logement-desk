import json

import pytest

from publish import publish


class Resp:
    def __init__(self, body, status=200):
        self.status, self._b = status, body

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_publish_posts_the_payload_with_the_push_token(tmp_path):
    f = tmp_path / "desk.json"
    f.write_text('{"listings": []}', encoding="utf-8")
    seen = {}

    def fake(req, timeout):
        seen.update(url=req.full_url, token=req.get_header("X-push-token"), body=req.data)
        return Resp(b'{"ok": true, "fresh": 2, "sent": 1}')

    out = publish("https://desk.example.test/", "tok", str(f), urlopen=fake)
    assert seen["url"] == "https://desk.example.test/api/ingest" and seen["token"] == "tok"
    assert json.loads(seen["body"]) == {"listings": []}
    assert out == {"ok": True, "fresh": 2, "sent": 1}


def test_publish_fails_loudly_on_http_error(tmp_path):
    f = tmp_path / "desk.json"
    f.write_text("{}", encoding="utf-8")

    def fake(req, timeout):
        import urllib.error
        raise urllib.error.HTTPError(req.full_url, 401, "no", {}, None)

    with pytest.raises(SystemExit):
        publish("https://desk.example.test", "bad", str(f), urlopen=fake)
