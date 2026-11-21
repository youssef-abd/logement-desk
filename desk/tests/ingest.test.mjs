import test from "node:test";
import assert from "node:assert/strict";
import { fakeKV } from "./helpers.mjs";
import { ingest } from "../lib/ingest.js";
import { messageFor } from "../lib/message.js";

const L = (id, o = {}) => ({ id, source: "bienici", url: `https://www.bienici.com/annonce/${id}`, rent_cc: 540, surface_m2: 27.4, district: "City 7e", poster: "particulier", status: "active", first_seen: "2026-11-15T09:50:00Z", ...o });
const P = (...ls) => ({ updated: "t", listings: ls, health: {} });
const NOW = Date.parse("2026-11-15T10:00:00Z");

test("messageFor: one listing opens the listing, several open the desk", () => {
  assert.deepEqual(messageFor([L("a")]), { body: "540 € · 27 m² · City 7e · particulier", url: "https://www.bienici.com/annonce/a" });
  const m = messageFor([L("a", { rent_cc: 600 }), L("b", { rent_cc: 450 })]);
  assert.equal(m.url, "/");
  assert.match(m.body, /^2 new: from 450 €/);
  assert.equal(messageFor([]), null);
});

test("the first ingest seeds silently, the next one alerts only on new active listings", async () => {
  const kv = fakeKV({ push: [{ endpoint: "https://push.example/1" }] });
  const sent = [];
  const send = async (s) => { sent.push(s.endpoint); return 201; };
  const first = await ingest({ kv, payload: P(L("a"), L("b")), now: NOW, send });
  assert.equal(first.seeded, true); assert.equal(sent.length, 0);
  const none = await ingest({ kv, payload: P(L("a"), L("b")), now: NOW, send });
  assert.equal(none.fresh, 0); assert.equal(sent.length, 0);
  const next = await ingest({ kv, payload: P(L("c"), L("d", { status: "stale" }), L("a"), L("b")), now: NOW, send });
  assert.equal(next.fresh, 1); assert.equal(next.sent, 1);
  assert.equal((await kv.get("pending", "json")).url, "https://www.bienici.com/annonce/c");
  assert.deepEqual(kv.dump().yield["2026-11-15"], { bienici: 1 });
  const again = await ingest({ kv, payload: P(L("c"), L("a"), L("b")), now: NOW, send });
  assert.equal(again.fresh, 0);
});

test("a device that answered 410 is forgotten, a failing push does not break ingest", async () => {
  const kv = fakeKV({ notified: [], push: [{ endpoint: "https://gone" }, { endpoint: "https://ok" }, { endpoint: "https://boom" }] });
  const send = async (s) => { if (s.endpoint === "https://gone") return 410; if (s.endpoint === "https://boom") throw new Error("x"); return 201; };
  const r = await ingest({ kv, payload: P(L("a")), now: NOW, send });
  assert.equal(r.sent, 1);
  assert.deepEqual((await kv.get("push", "json")).map((s) => s.endpoint), ["https://ok", "https://boom"]);
});

test("an empty payload is skipped: no KV write, not counted as the seeding run", async () => {
  const kv = fakeKV({});
  const r = await ingest({ kv, payload: P(), now: NOW, send: async () => 201 });
  assert.deepEqual(r, { stored: 0, fresh: 0, sent: 0, devices: 0, seeded: false, skipped: true });
  assert.deepEqual(kv.dump(), {});
  const first = await ingest({ kv, payload: P(L("a")), now: NOW, send: async () => 201 });
  assert.equal(first.seeded, true);
});

test("only listings first seen in the last 90 minutes are fresh; a deep sweep of old ones sends nothing", async () => {
  const kv = fakeKV({ notified: [], push: [{ endpoint: "https://ok" }] });
  const send = async () => 201;
  const old = L("old", { first_seen: "2026-11-15T07:00:00Z" }), recent = L("new", { first_seen: "2026-11-15T09:50:00Z" });
  const bad = L("bad", { first_seen: "garbage" }), none = L("none", { first_seen: undefined });
  const r = await ingest({ kv, payload: P(old, recent, bad, none), now: NOW, send });
  assert.equal(r.fresh, 1);
  assert.deepEqual(kv.dump().yield["2026-11-15"], { bienici: 1 });
  const sweep = await ingest({ kv, payload: P(old, bad, none), now: NOW, send });
  assert.equal(sweep.fresh, 0); assert.equal(sweep.sent, 0);
});

test("freshness follows the posted date: an old listing discovered just now is not fresh", async () => {
  const kv = fakeKV({ notified: [] });
  const old = L("old", { first_seen: "2026-11-15T09:55:00Z", posted: "2026-11-12T08:00:00Z" });
  const live = L("live", { first_seen: "2026-11-15T09:55:00Z", posted: "2026-11-15T09:50:00Z" });
  const r = await ingest({ kv, payload: P(old, live), now: NOW, send: async () => 201 });
  assert.equal(r.fresh, 1);
});
