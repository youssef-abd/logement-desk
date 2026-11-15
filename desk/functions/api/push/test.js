import { isOwner, json } from "../../../lib/auth.js";
import { sendPush } from "../../../lib/push.js";

export async function onRequestPost({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  await env.DESK.put("pending", JSON.stringify({ body: "Test alert: this is how alerts will look.", url: "/", t: Date.now() }));
  let sent = 0;
  const subs = (await env.DESK.get("push", "json")) || [];
  for (const s of subs) { try { const c = await sendPush(env, s); if (c >= 200 && c < 300) sent++; } catch (e) { /* counted as not sent */ } }
  return json({ ok: true, sent, devices: subs.length });
}
