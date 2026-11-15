import { isOwner, json } from "../../lib/auth.js";

export async function onRequestGet({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  return json((await env.DESK.get("pending", "json")) || { body: "", url: "/" });
}
