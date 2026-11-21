import test from "node:test";
import assert from "node:assert/strict";
import worker, { minutesSince, isDue } from "../src/index.js";

test("minutesSince and isDue", () => {
  assert.equal(minutesSince("2026-11-15T10:00:00Z", Date.parse("2026-11-15T11:30:00Z")), 90);
  assert.equal(minutesSince(null, 1), Infinity);
  assert.equal(isDue(Date.parse("2026-11-15T10:03:00Z")), true);   // first 10 minutes of the hour: do the hourly check
  assert.equal(isDue(Date.parse("2026-11-15T10:23:00Z")), false);
});

test("scheduled survives network errors and alerts only in the due window", async () => {
  const realFetch = globalThis.fetch;
  const ntfyCalls = [];
  globalThis.fetch = async (url, opts) => {
    const u = String(url);
    if (u.startsWith("https://api.github.com/")) throw new TypeError("network down");
    if (u.startsWith("https://ntfy.sh/")) { ntfyCalls.push({ url: u, body: opts && opts.body }); return new Response("ok"); }
    throw new Error("unexpected fetch " + u);
  };
  try {
    const env = { GITHUB_TOKEN: "t", NTFY_TOPIC: "x" };
    // minute 20: not due, so no alert even though dispatch fails
    await worker.scheduled({ scheduledTime: Date.parse("2026-11-15T10:20:00Z") }, env);
    assert.equal(ntfyCalls.length, 0);
    // minute 03: due, so the failed dispatch and the stale check alert
    await worker.scheduled({ scheduledTime: Date.parse("2026-11-15T10:03:00Z") }, env);
    assert.ok(ntfyCalls.length >= 1);
  } finally {
    globalThis.fetch = realFetch;
  }
});

test("hourly tick dispatches a deep sweep, other ticks and Run now stay light", async () => {
  const realFetch = globalThis.fetch;
  const bodies = [];
  globalThis.fetch = async (url, opts) => {
    const u = String(url);
    if (u.includes("/dispatches")) { bodies.push(JSON.parse(opts.body)); return new Response(null, { status: 204 }); }
    if (u.startsWith("https://api.github.com/")) return new Response(JSON.stringify({ workflow_runs: [{ status: "completed", conclusion: "success", updated_at: new Date().toISOString() }] }));
    return new Response("ok");
  };
  try {
    const env = { GITHUB_TOKEN: "t" };
    await worker.scheduled({ scheduledTime: Date.parse("2026-11-15T10:03:00Z") }, env);
    await worker.scheduled({ scheduledTime: Date.parse("2026-11-15T10:23:00Z") }, env);
    await worker.fetch(new Request("https://x/dispatch", { method: "POST" }), env);
    assert.deepEqual(bodies.map((b) => b.inputs.deep), ["true", "false", "false"]);
    assert.equal(bodies[0].inputs.mode, "full");
  } finally {
    globalThis.fetch = realFetch;
  }
});
