import test from "node:test";
import assert from "node:assert/strict";
import { ago, tabOf, matches, needsNudge, AREA_NAMES, areaName, sortRows, paginate, isNew, buildMessage } from "../public/format.js";

const L = (o = {}) => ({ id: "a", source: "bienici", status: "active", poster: "particulier", tags: [], title: "Studio", district: "City 7e", ...o });
const F = { tab: "new", source: "all", poster: "all", near: true, q: "", area: "all", cheap: false };

test("ago", () => {
  const now = Date.parse("2026-11-15T12:00:00Z");
  assert.equal(ago("2026-11-15T11:50:00Z", now), "10 min ago");
  assert.equal(ago("2026-11-15T07:00:00Z", now), "5 h ago");
  assert.equal(ago("2026-11-10T12:00:00Z", now), "5 d ago");
  assert.equal(ago(null, now), "");
});

test("tabOf follows the stage first, then staleness", () => {
  assert.equal(tabOf(L(), "none"), "new");
  assert.equal(tabOf(L({ status: "stale" }), "none"), "closed");
  assert.equal(tabOf(L({ status: "stale" }), "visit"), "following");
  assert.equal(tabOf(L(), "refused"), "closed");
  assert.equal(tabOf(L(), "saved"), "saved");
  assert.equal(tabOf(L({ status: "stale" }), "saved"), "saved");
});

test("matches applies tab, source, poster, near-miss and text", () => {
  assert.equal(matches(L(), F, "none"), true);
  assert.equal(matches(L(), { ...F, tab: "following" }, "none"), false);
  assert.equal(matches(L(), { ...F, source: "leboncoin" }, "none"), false);
  assert.equal(matches(L({ poster: "agence" }), { ...F, poster: "particulier" }, "none"), false);
  assert.equal(matches(L({ tags: ["near-miss"] }), { ...F, near: false }, "none"), false);
  assert.equal(matches(L(), { ...F, q: "city 7" }, "none"), true);
  assert.equal(matches(L(), { ...F, q: "zzz" }, "none"), false);
});

test("needsNudge", () => {
  const day = 86400000;
  assert.equal(needsNudge({ s: "contacted", t: 0 }, 4 * day), true);
  assert.equal(needsNudge({ s: "contacted", t: 0 }, 2 * day), false);
  assert.equal(needsNudge({ s: "visit", t: 0 }, 9 * day), false);
});

test("matches area and cheap filters", () => {
  assert.equal(matches(L({ postal_code: "69007" }), { ...F, area: "69007" }, "none"), true);
  assert.equal(matches(L({ postal_code: "69003" }), { ...F, area: "69007" }, "none"), false);
  assert.equal(matches(L(), { ...F, cheap: true }, "none"), false);
  assert.equal(matches(L({ tags: ["cheap-for-area"] }), { ...F, cheap: true }, "none"), true);
});

test("areaName", () => {
  assert.equal(areaName("69001"), "Lyon 1er");
  assert.equal(areaName("69009"), "Lyon 9e");
  assert.equal(areaName("69100"), "Villeurbanne");
  assert.equal(areaName("69130"), "Écully");
  assert.equal(areaName("01000"), "01000");
  assert.equal(Object.keys(AREA_NAMES).length, 16);
});

test("sortRows", () => {
  const rows = [
    { id: "a", posted: "2026-11-01T00:00:00Z", rent_cc: 500, eur_m2: null, surface_m2: 20 },
    { id: "b", posted: "2026-11-03T00:00:00Z", rent_cc: null, eur_m2: 15, surface_m2: null },
    { id: "c", posted: "2026-11-03T00:00:00Z", first_seen: "2026-11-04T00:00:00Z", rent_cc: 400, eur_m2: 12, surface_m2: 30 },
  ];
  const copy = JSON.stringify(rows);
  assert.deepEqual(sortRows(rows, "newest").map((r) => r.id), ["c", "b", "a"]);
  assert.deepEqual(sortRows(rows, "price").map((r) => r.id), ["c", "a", "b"]);
  assert.deepEqual(sortRows(rows, "eur_m2").map((r) => r.id), ["c", "b", "a"]);
  assert.deepEqual(sortRows(rows, "size").map((r) => r.id), ["c", "a", "b"]);
  assert.equal(JSON.stringify(rows), copy);
});

test("paginate", () => {
  const r = [1, 2, 3, 4, 5];
  assert.deepEqual(paginate(r, 2), { rows: [1, 2], rest: 3 });
  assert.deepEqual(paginate(r, 60), { rows: r, rest: 0 });
});

test("isNew", () => {
  assert.equal(isNew({ first_seen: "2026-11-10T00:00:00Z" }, Date.parse("2026-11-09T00:00:00Z")), true);
  assert.equal(isNew({ first_seen: "2026-11-08T00:00:00Z" }, Date.parse("2026-11-09T00:00:00Z")), false);
  assert.equal(isNew({ first_seen: "nope" }, 0), false);
  assert.equal(isNew({}, 0), false);
});

test("buildMessage uses only listing and own details", () => {
  const m = buildMessage(L({ rent_cc: 550, surface_m2: 22, title: "Studio calme" }), { name: "Sam", phone: "0600000000", visale: "V123" });
  for (const s of ["Bonjour,", "550", "22", "City 7e", "V123", "visite", "Cordialement,", "Sam", "0600000000"]) assert.ok(m.includes(s), s);
  const e = buildMessage(L({ rent_cc: null, surface_m2: null }), { name: "", phone: "", visale: "" });
  assert.ok(e.startsWith("Bonjour,") && e.includes("Cordialement,"));
  assert.ok(!e.includes("Visale") && !e.includes("undefined") && !e.includes("null"));
});

test("the kind filter separates colocations from flats", () => {
  const F2 = { tab: "new", source: "all", poster: "all", near: true, q: "", area: "all", cheap: false };
  assert.equal(matches(L({ kind: "coloc" }), { ...F2, kind: "coloc" }, "none"), true);
  assert.equal(matches(L({ kind: "studio" }), { ...F2, kind: "coloc" }, "none"), false);
  assert.equal(matches(L({ kind: "coloc" }), { ...F2, kind: "flat" }, "none"), false);
  assert.equal(matches(L({ kind: "studio" }), { ...F2, kind: "flat" }, "none"), true);
  assert.equal(matches(L({ kind: "coloc" }), { ...F2 }, "none"), true);
});

test("matches applies the budget, furnished and room-type filters", () => {
  assert.equal(matches(L({ rent_cc: 650 }), { ...F, maxRent: 600 }, "none"), false);
  assert.equal(matches(L({ rent_cc: 650 }), { ...F, maxRent: 700 }, "none"), true);
  assert.equal(matches(L({ rent_cc: null }), { ...F, maxRent: 300 }, "none"), true); // an unknown rent is not hidden
  assert.equal(matches(L({ furnished: false }), { ...F, furn: "known" }, "none"), false);
  assert.equal(matches(L({ furnished: null }), { ...F, furn: "known" }, "none"), true);
  assert.equal(matches(L({ furnished: null }), { ...F, furn: "yes" }, "none"), false);
  assert.equal(matches(L({ furnished: false }), { ...F, furn: "any" }, "none"), true);
  assert.equal(matches(L({ kind: "t2" }), { ...F, kind: "studio" }, "none"), false);
  assert.equal(matches(L({ kind: "studio" }), { ...F, kind: "studio" }, "none"), true);
});

test("matches filters by city and treats listings without one as Lyon", () => {
  assert.equal(matches(L({ city: "grenoble" }), { ...F, city: "lyon" }, "none"), false);
  assert.equal(matches(L({ city: "grenoble" }), { ...F, city: "grenoble" }, "none"), true);
  assert.equal(matches(L(), { ...F, city: "lyon" }, "none"), true);
  assert.equal(matches(L(), { ...F, city: "all" }, "none"), true);
});
