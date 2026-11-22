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
  const p = cleanPayload({ updated: "t", listings: Array.from({ length: 1600 }, (_, i) => ({ ...good, id: `bienici:${i}` })), health: { bienici: { failures: 2, run: { status: "ok", fetched: 24, kept: 20 } }, "BAD name": {} } });
  assert.equal(p.listings.length, 1500);
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

test("cleanListing keeps eur_m2, posted and similar with safe types", () => {
  const l = cleanListing({ ...good, eur_m2: 18.5, posted: "2026-11-15T09:00:00+00:00", similar: 3 });
  assert.equal(l.eur_m2, 18.5); assert.equal(l.posted, "2026-11-15T09:00:00+00:00"); assert.equal(l.similar, 3);
  const d = cleanListing({ ...good, eur_m2: "x", posted: 5, similar: -2 });
  assert.equal(d.eur_m2, null); assert.equal(d.posted, ""); assert.equal(d.similar, 0);
  assert.equal(cleanListing({ ...good, similar: 1.5 }).similar, 0);
  assert.equal(cleanListing({ ...good, posted: "x".repeat(99) }).posted.length, 40);
});

test("cleanPayload keeps only well-formed areas", () => {
  const areas = JSON.parse('{"69003":{"n":9,"median_eur_m2":24.5},"1234":{"n":1,"median_eur_m2":1},"__proto__":{"n":1,"median_eur_m2":1},"69007":{"n":"x","median_eur_m2":3},"69009":"junk"}');
  const p = cleanPayload({ updated: "t", listings: [good], areas });
  assert.deepEqual(p.areas, { "69003": { n: 9, median_eur_m2: 24.5 } });
  assert.equal(Object.getPrototypeOf(p.areas), Object.prototype);
  assert.deepEqual(cleanPayload({ updated: "t", listings: [good] }).areas, {});
  const many = Object.fromEntries(Array.from({ length: 60 }, (_, i) => [String(10000 + i), { n: 1, median_eur_m2: 1 }]));
  assert.equal(Object.keys(cleanPayload({ listings: [good], areas: many }).areas).length, 40);
});

test("risk fields are whitelisted", () => {
  const l = cleanListing({ ...good, risk: "high", risk_reasons: ["keys sent by post", 7, "x".repeat(200)] });
  assert.equal(l.risk, "high");
  assert.equal(l.risk_reasons.length, 2);
  assert.equal(l.risk_reasons[1].length, 60);
  assert.equal(cleanListing({ ...good, risk: "<b>" }).risk, null);
});

test("poster_name is kept as a short string", () => {
  assert.equal(cleanListing({ ...good, poster_name: "AGENCE EXAMPLE" }).poster_name, "AGENCE EXAMPLE");
  assert.equal(cleanListing({ ...good, poster_name: "x".repeat(200) }).poster_name.length, 60);
  assert.equal(cleanListing({ ...good, poster_name: 5 }).poster_name, null);
});

test("cleanPayload keeps the match flag and the criteria, and tolerates their absence", () => {
  const l = { id: "a", source: "bienici", url: "https://www.bienici.com/annonce/a" };
  const p = cleanPayload({ listings: [l, { ...l, id: "b", match: false }], criteria: { max_rent_cc: 600, near_miss_margin: 100, furnished: "required", collect_max_rent_cc: 1200, junk: 1 } });
  assert.deepEqual(p.listings.map((x) => x.match), [true, false]);
  assert.deepEqual(p.criteria, { max_rent_cc: 600, near_miss_margin: 100, furnished: "required", collect_max_rent_cc: 1200 });
  assert.equal(cleanPayload({ listings: [l] }).criteria, null);
  assert.equal(cleanPayload({ listings: [l], criteria: { max_rent_cc: "x" } }).criteria, null);
});

test("cleanPayload keeps valid cities and a listing's city, and drops bad ones", () => {
  const l = { id: "a", source: "bienici", url: "https://www.bienici.com/annonce/a", city: "grenoble" };
  const p = cleanPayload({ listings: [l, { ...l, id: "b", city: "../x" }], cities: [{ key: "lyon", name: "Lyon", postal_codes: ["69001"] }, { key: "Bad Key" }, null] });
  assert.deepEqual(p.listings.map((x) => x.city), ["grenoble", null]);
  assert.deepEqual(p.cities, [{ key: "lyon", name: "Lyon", postal_codes: ["69001"], sources: {} }]);
  assert.deepEqual(cleanPayload({ listings: [l] }).cities, []);
});

test("cleanPayload keeps what each source found in a city and sanitises it", () => {
  const l = { id: "a", source: "bienici", url: "https://www.bienici.com/annonce/a" };
  const p = cleanPayload({ listings: [l], cities: [{ key: "angers-49", name: "Angers", postal_codes: ["49000"], sources: { foncia: { status: "ok", fetched: 30, kept: 20 }, "Bad Name": { status: "ok" }, paruvendu: { status: "weird", fetched: "x" } } }] });
  assert.deepEqual(p.cities[0].sources, { foncia: { status: "ok", fetched: 30, kept: 20 }, paruvendu: { status: "error", fetched: 0, kept: 0 } });
  assert.deepEqual(cleanPayload({ listings: [l], cities: [{ key: "lyon", name: "Lyon" }] }).cities[0].sources, {});
});
