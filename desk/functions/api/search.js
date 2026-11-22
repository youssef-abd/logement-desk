import { canUse, isPusher, json } from "../../lib/auth.js";
import { cleanCities, MAX_CITIES } from "../../lib/search.js";

// GET: the city to collect (the owner's desk and the run read it). PUT: the owner changes it.
export async function onRequest({ request, env }) {
  const owner = await canUse(request, env);
  if (!owner && !(request.method === "GET" && isPusher(request, env))) return json({ error: "unauthorized" }, 401);
  if (request.method === "GET") {
    const s = await env.DESK.get("search", "json");
    const cities = cleanCities(s && s.cities);
    return json({ cities: cities.length ? cities : ["lyon"], max: MAX_CITIES });
  }
  if (request.method !== "PUT") return json({ error: "method" }, 405);
  let b;
  try { b = await request.json(); } catch (e) { return json({ error: "bad json" }, 400); }
  const cities = cleanCities(b && b.cities);
  if (!cities.length) return json({ error: "pick a city" }, 400);
  await env.DESK.put("search", JSON.stringify({ cities }));
  return json({ ok: true, cities, max: MAX_CITIES });
}
