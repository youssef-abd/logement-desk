import { isOwner, json } from "../../lib/auth.js";

export async function onRequestGet({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  const data = (await env.DESK.get("listings", "json")) || { updated: null, listings: [], health: {} };
  return json({ ...data, yield: (await env.DESK.get("yield", "json")) || {} });
}
