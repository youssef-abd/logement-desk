import { messageFor } from "./message.js";

// payload is already cleaned. kv is the KV binding; send(sub) returns the push HTTP status.
export async function ingest({ kv, payload, now, send }) {
  if (payload.listings.length === 0) return { stored: 0, fresh: 0, sent: 0, devices: 0, seeded: false, skipped: true };
  const raw = await kv.get("notified", "json");
  const first = !Array.isArray(raw);
  const notified = new Set(first ? [] : raw);
  const fresh = first ? [] : payload.listings.filter((l) => l.status === "active" && !notified.has(l.id));
  await kv.put("listings", JSON.stringify(payload));
  let sent = 0, devices = 0;
  if (fresh.length) {
    const m = messageFor(fresh);
    await kv.put("pending", JSON.stringify({ ...m, t: now }));
    const raw = await kv.get("push", "json");
    const subs = Array.isArray(raw) ? raw : [];
    const keep = [];
    for (const s of subs) {
      let code = 0;
      try { code = await send(s); } catch (e) { code = 0; }
      if (code === 404 || code === 410) continue; // the device unsubscribed
      keep.push(s);
      if (code >= 200 && code < 300) sent++;
    }
    devices = keep.length;
    if (keep.length !== subs.length) await kv.put("push", JSON.stringify(keep));
    const day = new Date(now).toISOString().slice(0, 10), y = (await kv.get("yield", "json")) || {};
    y[day] = y[day] || {};
    for (const l of fresh) y[day][l.source] = (y[day][l.source] || 0) + 1;
    for (const d of Object.keys(y).sort().slice(0, -14)) delete y[d];
    await kv.put("yield", JSON.stringify(y));
  }
  if (first || fresh.length) {
    const ids = first ? payload.listings.map((l) => l.id) : fresh.map((l) => l.id);
    await kv.put("notified", JSON.stringify([...notified, ...ids].slice(-3000)));
  }
  return { stored: payload.listings.length, fresh: fresh.length, sent, devices, seeded: first };
}
