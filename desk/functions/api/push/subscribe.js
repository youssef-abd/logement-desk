import { isOwner, json } from "../../../lib/auth.js";

const okEndpoint = (e) => typeof e === "string" && e.length < 600 && /^https:\/\//.test(e);

export async function onRequest({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  let b;
  try { b = await request.json(); } catch (e) { return json({ error: "bad json" }, 400); }
  const subs = (await env.DESK.get("push", "json")) || [];
  if (request.method === "DELETE") {
    await env.DESK.put("push", JSON.stringify(subs.filter((s) => s.endpoint !== (b && b.endpoint))));
    return json({ ok: true });
  }
  if (request.method !== "POST") return json({ error: "method" }, 405);
  const s = b && b.subscription;
  if (!s || !okEndpoint(s.endpoint)) return json({ error: "bad subscription" }, 400);
  const next = [...subs.filter((x) => x.endpoint !== s.endpoint), { endpoint: s.endpoint, t: Date.now() }].slice(-5);
  await env.DESK.put("push", JSON.stringify(next));
  return json({ ok: true, devices: next.length });
}
