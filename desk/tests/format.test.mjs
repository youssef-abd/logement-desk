import test from "node:test";
import assert from "node:assert/strict";
import { ago, tabOf, matches, needsNudge } from "../public/format.js";

const L = (o = {}) => ({ id: "a", source: "bienici", status: "active", poster: "particulier", tags: [], title: "Studio", district: "City 7e", ...o });
const F = { tab: "new", source: "all", poster: "all", near: true, q: "" };

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
