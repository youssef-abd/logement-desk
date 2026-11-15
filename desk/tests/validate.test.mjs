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
  const p = cleanPayload({ updated: "t", listings: Array.from({ length: 500 }, (_, i) => ({ ...good, id: `bienici:${i}` })), health: { bienici: { failures: 2, run: { status: "ok", fetched: 24, kept: 20 } }, "BAD name": {} } });
  assert.equal(p.listings.length, 400);
  assert.deepEqual(Object.keys(p.health), ["bienici"]);
  assert.equal(p.health.bienici.kept, 20);
});

test("safeUrl rejects credentials and non-default ports", () => {
  assert.equal(safeUrl("https://u:p@www.leboncoin.fr/x"), "");
  assert.equal(safeUrl("https://www.leboncoin.fr:444/x"), "");
});

test("cleanListing drops a listing whose source is not a plain slug", () => {
  assert.equal(cleanListing({ ...good, source: "constructor!" }), null);
});

test("cleanPayload keeps a valid health entry after 12 junk names", () => {
  const junk = Object.fromEntries(Array.from({ length: 12 }, (_, i) => [`BAD ${i}`, { failures: 1 }]));
  const p = cleanPayload({ updated: "t", listings: [good], health: { ...junk, bienici: { failures: 0, run: { status: "ok" } } } });
  assert.deepEqual(Object.keys(p.health), ["bienici"]);
});

test("cleanPayload keeps one listing per id (first occurrence)", () => {
  const p = cleanPayload({ updated: "t", listings: [good, { ...good, title: "second" }] });
  assert.equal(p.listings.length, 1);
  assert.equal(p.listings[0].title, "T");
});
