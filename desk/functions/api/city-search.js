import { canUse, json } from "../../lib/auth.js";
import { toCity } from "../../lib/search.js";

// Looks a French commune up by name in the public communes API (the browser never calls it itself: the page's CSP stays strict).
export async function onRequestGet({ request, env }) {
  if (!(await canUse(request, env))) return json({ error: "unauthorized" }, 401);
  const q = (new URL(request.url).searchParams.get("q") || "").trim();
  if (q.length < 2 || q.length > 60) return json({ cities: [] });
  let list;
  try {
    const r = await fetch(`https://geo.api.gouv.fr/communes?nom=${encodeURIComponent(q)}&boost=population&limit=8&fields=nom,code,codesPostaux,centre,departement,region`);
    if (!r.ok) throw new Error("lookup");
    list = await r.json();
  } catch (e) { return json({ error: "lookup failed" }, 502); }
  return json({ cities: (Array.isArray(list) ? list : []).map(toCity).filter(Boolean) });
}
