import test from "node:test";
import assert from "node:assert/strict";
import { safeUrl, cleanListing, cleanPayload } from "../lib/validate.js";

test("safeUrl accepts only https on the source hosts", () => {
  assert.equal(safeUrl("https://www.leboncoin.fr/ad/locations/1"), "https://www.leboncoin.fr/ad/locations/1");
  assert.equal(safeUrl("http://www.leboncoin.fr/x"), "");
  assert.equal(safeUrl("https://evil.example/x"), "");
  assert.equal(safeUrl("https://leboncoin.fr.evil.example/x"), "");
  assert.equal(safeUrl("javascript:alert(1)"), "");
});

const good = { id: "bienici:a1", source: "bienici", url: "https://www.bienici.com/annonce/a1", title: "T", rent_cc: 500,
  surface_m2: 20, rooms: 1, district: "City 3e", poster: "agence", status: "active", flags: ["visale"], tags: [], photos: ["https://file.bienici.com/p1", "http://x/y", "javascript:1"] };

test("cleanListing keeps good fields, drops bad photos and bad urls", () => {
  const l = cleanListing(good);
  assert.equal(l.rent_cc, 500);
  assert.deepEqual(l.photos, ["https://file.bienici.com/p1"]);
  assert.equal(cleanListing({ ...good, url: "https://evil.example/" }), null);
  assert.equal(cleanListing({ ...good, id: "" }), null);
  assert.equal(cleanListing({ ...good, rent_cc: "500" }).rent_cc, null);
  assert.equal(cleanListing({ ...good, poster: "<script>" }).poster, null);
});

test("cleanPayload caps size and rejects junk", () => {
  assert.equal(cleanPayload(null), null);
  assert.equal(cleanPayload({ listings: "x" }), null);
  const p = cleanPayload({ updated: "t", listings: Array(500).fill(good), health: { bienici: { failures: 2, run: { status: "ok", fetched: 24, kept: 20 } }, "BAD name": {} } });
  assert.equal(p.listings.length, 400);
  assert.deepEqual(Object.keys(p.health), ["bienici"]);
  assert.equal(p.health.bienici.kept, 20);
});
