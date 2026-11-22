import test from "node:test";
import assert from "node:assert/strict";
import { fakeKV } from "./helpers.mjs";
import { cleanCities, MAX_CITIES } from "../lib/search.js";
import { onRequest } from "../functions/api/search.js";

const env = (kv) => ({ DESK: kv, API_TOKEN: "owner", PUSH_TOKEN: "pusher" });
const req = (method, token, body, header = "x-token") => ({ request: new Request("https://d.test/api/search", { method, headers: { [header]: token, "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }) });

test("cleanCities keeps valid distinct keys and caps the count", () => {
  assert.deepEqual(cleanCities(["lyon", "Grenoble", "grenoble", "lyon", "a", "../x", 7, "paris-15"]), ["lyon", "grenoble", "paris-15"]);
  assert.equal(cleanCities(Array.from({ length: 20 }, (_, i) => "city-" + i)).length, MAX_CITIES);
  assert.deepEqual(cleanCities("lyon"), []);
});

test("the owner sets the cities, the run and the owner read them, strangers do nothing", async () => {
  const kv = fakeKV();
  assert.deepEqual(await (await onRequest({ ...req("GET", "owner"), env: env(kv) })).json(), { cities: ["lyon"] }); // nothing saved yet
  const put = await onRequest({ ...req("PUT", "owner", { cities: ["lyon", "grenoble", "<script>"] }), env: env(kv) });
  assert.deepEqual(await put.json(), { ok: true, cities: ["lyon", "grenoble"] });
  assert.deepEqual(await (await onRequest({ ...req("GET", "pusher", undefined, "x-push-token"), env: env(kv) })).json(), { cities: ["lyon", "grenoble"] });
  assert.equal((await onRequest({ ...req("PUT", "pusher", { cities: ["nice"] }, "x-push-token"), env: env(kv) })).status, 401); // the run only reads
  assert.equal((await onRequest({ ...req("GET", "wrong"), env: env(kv) })).status, 401);
  assert.equal((await onRequest({ ...req("PUT", "owner", { cities: [] }), env: env(kv) })).status, 400);
  assert.deepEqual(kv.dump().search, { cities: ["lyon", "grenoble"] });
});
