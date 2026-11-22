import test from "node:test";
import assert from "node:assert/strict";
import { fakeKV } from "./helpers.mjs";
import { cleanCity, cleanCities, toCity, slug, MAX_CITIES } from "../lib/search.js";
import { onRequest } from "../functions/api/search.js";
import { onRequestGet as citySearch } from "../functions/api/city-search.js";

const env = (kv) => ({ DESK: kv, API_TOKEN: "owner", PUSH_TOKEN: "pusher" });
const req = (method, token, body, header = "x-token", url = "https://d.test/api/search") => ({ request: new Request(url, { method, headers: { [header]: token, "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }) });
const ANGERS = { key: "angers-49", name: "Angers", dept: "49", postal_codes: ["49000", "49100"], lat: 47.47, lng: -0.55, region: "pays-de-la-loire" };
const GEO = { nom: "Angers", code: "49007", codesPostaux: ["49000", "49100"], centre: { type: "Point", coordinates: [-0.55, 47.47] }, departement: { code: "49" }, region: { nom: "Pays de la Loire" } };
const search = (q) => `https://d.test/api/city-search?q=${q}`;

test("one city at a time for now: the cap is one number", () => {
  assert.equal(MAX_CITIES, 1);
  assert.deepEqual(cleanCities(["lyon", "grenoble"]), ["lyon"]);
  assert.deepEqual(cleanCities([ANGERS, ANGERS, "lyon"]), [ANGERS]);
  assert.deepEqual(cleanCities("lyon"), []);
});

test("cleanCity accepts keys and complete records and rejects the rest", () => {
  assert.equal(cleanCity("lyon"), "lyon");
  assert.equal(cleanCity("../x"), null);
  assert.deepEqual(cleanCity({ ...ANGERS, junk: 1, name: "  Angers " }), ANGERS);
  for (const bad of [{ ...ANGERS, key: "A B" }, { ...ANGERS, postal_codes: ["abc"] }, { ...ANGERS, postal_codes: [] }, { ...ANGERS, lat: "x" }, { ...ANGERS, dept: "9999" }, { ...ANGERS, name: "" }, null, 5]) assert.equal(cleanCity(bad), null);
  assert.equal(cleanCity({ ...ANGERS, region: "<b>" }).region, "");
});

test("toCity turns a commune into a record; Lyon is the home city", () => {
  assert.deepEqual(toCity(GEO), ANGERS);
  assert.equal(toCity({ ...GEO, nom: "Lyon", code: "69123", departement: { code: "69" } }).key, "lyon");
  assert.equal(toCity({ ...GEO, nom: "Saint-Étienne", code: "42218", departement: { code: "42" } }).key, "saint-etienne-42");
  assert.equal(toCity({ nom: "x" }), null);
  assert.equal(slug("Aix-en-Provence"), "aix-en-provence");
});

test("the owner sets the city, the run and the owner read it, strangers do nothing", async () => {
  const kv = fakeKV();
  assert.deepEqual(await (await onRequest({ ...req("GET", "owner"), env: env(kv) })).json(), { cities: ["lyon"], max: 1 }); // nothing saved yet
  const put = await onRequest({ ...req("PUT", "owner", { cities: [ANGERS, "lyon", "<script>"] }), env: env(kv) });
  assert.deepEqual(await put.json(), { ok: true, cities: [ANGERS], max: 1 });
  assert.deepEqual((await (await onRequest({ ...req("GET", "pusher", undefined, "x-push-token"), env: env(kv) })).json()).cities, [ANGERS]);
  assert.equal((await onRequest({ ...req("PUT", "pusher", { cities: ["nice"] }, "x-push-token"), env: env(kv) })).status, 401); // the run only reads
  assert.equal((await onRequest({ ...req("GET", "wrong"), env: env(kv) })).status, 401);
  assert.equal((await onRequest({ ...req("PUT", "owner", { cities: [] }), env: env(kv) })).status, 400);
  assert.deepEqual(kv.dump().search, { cities: [ANGERS] });
});

test("city-search looks communes up, needs the owner, and survives a failing lookup", async () => {
  const real = globalThis.fetch;
  try {
    let asked = "";
    globalThis.fetch = async (u) => { asked = String(u); return new Response(JSON.stringify([GEO, { nom: "broken" }]), { status: 200 }); };
    const ok = await citySearch({ ...req("GET", "owner", undefined, "x-token", search("ang%C3%A9")), env: env(fakeKV()) });
    assert.deepEqual(await ok.json(), { cities: [ANGERS] });
    assert.match(asked, /^https:\/\/geo\.api\.gouv\.fr\/communes\?nom=ang%C3%A9&/);
    assert.equal((await citySearch({ ...req("GET", "nope", undefined, "x-token", search("ang")), env: env(fakeKV()) })).status, 401);
    assert.deepEqual(await (await citySearch({ ...req("GET", "owner", undefined, "x-token", search("a")), env: env(fakeKV()) })).json(), { cities: [] });
    globalThis.fetch = async () => { throw new Error("down"); };
    assert.equal((await citySearch({ ...req("GET", "owner", undefined, "x-token", search("angers")), env: env(fakeKV()) })).status, 502);
  } finally { globalThis.fetch = real; }
});
