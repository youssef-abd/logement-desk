import { isOwner, json } from "../../lib/auth.js";

const COOLDOWN_MS = 5 * 60 * 1000;

export async function onRequest({ request, env }) {
  if (!isOwner(request, env)) return json({ error: "unauthorized" }, 401);
  if (!env.RUNNER) return json({ error: "the runner is not connected" }, 503);
  let last;
  try { last = await (await env.RUNNER.fetch("https://runner/last-run")).json(); } catch (e) { return json({ error: "the runner did not answer" }, 502); }
  if (request.method === "GET") return json({ last });
  if (request.method !== "POST") return json({ error: "method" }, 405);
  if (last.status === "in_progress" || last.status === "queued") return json({ error: "a run is already in progress", last }, 409);
  const prev = Number(await env.DESK.get("runnow")) || 0;
  if (Date.now() - prev < COOLDOWN_MS) return json({ error: "wait a few minutes", last }, 429);
  let d;
  try { d = await (await env.RUNNER.fetch("https://runner/dispatch", { method: "POST" })).json(); } catch (e) { return json({ error: "the runner did not answer" }, 502); }
  if (d.status !== 204) return json({ error: "GitHub refused the start (HTTP " + d.status + ")" }, 502);
  await env.DESK.put("runnow", String(Date.now()));
  return json({ ok: true });
}
