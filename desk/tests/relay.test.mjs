import test from "node:test";
import assert from "node:assert/strict";
import { allowedUrl, relay } from "../lib/relay.js";

test("only https urls on the allowed hosts pass", () => {
  assert.equal(allowedUrl("https://www.pap.fr/annonce/x"), "https://www.pap.fr/annonce/x");
  assert.equal(allowedUrl("https://fr.foncia.com/location/lyon-69"), "https://fr.foncia.com/location/lyon-69");
  for (const bad of ["http://www.pap.fr/x", "https://evil.test/", "https://www.pap.fr.evil.test/", "https://u:p@www.pap.fr/x", "not a url", ""]) {
    assert.equal(allowedUrl(bad), null, bad);
  }
});

test("relay passes the status and body through and never throws", async () => {
  const ok = await relay("https://www.pap.fr/a", async () => new Response("<html>hi</html>", { status: 200 }));
  assert.deepEqual(ok, { status: 200, body: "<html>hi</html>" });
  const blocked = await relay("https://www.pap.fr/a", async () => new Response("no", { status: 403 }));
  assert.equal(blocked.status, 403);
  assert.equal((await relay("https://evil.test/", async () => { throw new Error("must not be called"); })).status, 400);
  assert.equal((await relay("https://www.pap.fr/a", async () => { throw new Error("down"); })).status, 502);
});
