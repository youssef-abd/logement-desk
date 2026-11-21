import { isPusher, json } from "../../lib/auth.js";
import { relay } from "../../lib/relay.js";

export async function onRequestGet({ request, env }) {
  if (!isPusher(request, env)) return json({ error: "unauthorized" }, 401);
  const target = new URL(request.url).searchParams.get("url") || "";
  const { status, body } = await relay(target);
  return new Response(body, { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
}
