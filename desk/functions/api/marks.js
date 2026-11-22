import { canUse, json } from "../../lib/auth.js";
import { applyMark } from "../../lib/marks.js";

export async function onRequest({ request, env }) {
  if (!(await canUse(request, env))) return json({ error: "unauthorized" }, 401);
  const marks = (await env.DESK.get("marks", "json")) || {};
  if (request.method === "GET") return json({ marks });
  if (request.method !== "POST") return json({ error: "method" }, 405);
  let b;
  try { b = await request.json(); } catch (e) { return json({ error: "bad json" }, 400); }
  const next = applyMark(marks, b);
  if (!next) return json({ error: "bad input" }, 400);
  await env.DESK.put("marks", JSON.stringify(next));
  return json({ ok: true });
}
