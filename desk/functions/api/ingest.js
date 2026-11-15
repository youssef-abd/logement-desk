import { isPusher, json } from "../../lib/auth.js";
import { cleanPayload } from "../../lib/validate.js";
import { ingest } from "../../lib/ingest.js";
import { sendPush } from "../../lib/push.js";

export async function onRequestPost({ request, env }) {
  if (!isPusher(request, env)) return json({ error: "unauthorized" }, 401);
  if (Number(request.headers.get("content-length") || 0) > 2_000_000) return json({ error: "too large" }, 413);
  let body;
  try { body = await request.json(); } catch (e) { return json({ error: "bad json" }, 400); }
  const payload = cleanPayload(body);
  if (!payload) return json({ error: "bad payload" }, 400);
  return json({ ok: true, ...(await ingest({ kv: env.DESK, payload, now: Date.now(), send: (s) => sendPush(env, s) })) });
}
