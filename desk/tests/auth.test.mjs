import test from "node:test";
import assert from "node:assert/strict";
import { fakeKV } from "./helpers.mjs";
import { onRequestGet as listings } from "../functions/api/listings.js";
import { onRequestGet as pending } from "../functions/api/pending.js";
import { onRequest as marks } from "../functions/api/marks.js";
import { onRequest as search } from "../functions/api/search.js";
import { onRequestGet as citySearch } from "../functions/api/city-search.js";
import { onRequest as run } from "../functions/api/run.js";
import { onRequest as subscribe } from "../functions/api/push/subscribe.js";
import { onRequestPost as pushTest } from "../functions/api/push/test.js";

const env = (kv) => ({ DESK: kv, API_TOKEN: "owner", PUSH_TOKEN: "pusher", CRON: { fetch: async () => new Response("{}") } });
const ask = (method, token, body) => ({ request: new Request("https://d.test/api/x", { method, headers: token ? { "x-token": token, "content-type": "application/json" } : { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }) });
const status = async (fn, ctx) => { try { return (await fn(ctx)).status; } catch (e) { return "threw"; } };

test("with the code on, nothing works without it", async () => {
  const e = env(fakeKV());
  for (const fn of [listings, pending, marks, search, citySearch, run, subscribe, pushTest]) assert.equal(await status(fn, { ...ask("GET"), env: e }), 401);
  assert.equal(await status(listings, { ...ask("GET", "owner"), env: e }), 200);
});

test("with auth_off set, the harmless parts open and the costly ones stay locked", async () => {
  const kv = fakeKV();
  await kv.put("auth_off", "1");
  const e = env(kv);
  for (const fn of [listings, pending, marks, search]) assert.equal(await status(fn, { ...ask("GET"), env: e }), 200);
  assert.equal(await status(marks, { ...ask("POST", undefined, { id: "a", s: "saved", t: 1 }), env: e }), 200);
  assert.equal(await status(search, { ...ask("PUT", undefined, { cities: ["lyon"] }), env: e }), 200);
  for (const fn of [run, subscribe, pushTest]) assert.equal(await status(fn, { ...ask("POST"), env: e }), 401);
});

test("any value other than 1 keeps the code on, and a wrong code is still refused", async () => {
  const kv = fakeKV();
  await kv.put("auth_off", "0");
  assert.equal(await status(listings, { ...ask("GET"), env: env(kv) }), 401);
  assert.equal(await status(listings, { ...ask("GET", "nope"), env: env(kv) }), 401);
});
