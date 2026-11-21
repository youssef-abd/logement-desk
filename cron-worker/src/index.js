// Cloudflare cron -> starts the GitHub Actions workflow run.yml every 10 minutes (GitHub's own `schedule:` runs hours late).
// Once an hour it also checks that a run succeeded recently and alerts through ntfy if not. One cron trigger only.
// Secrets (set with `wrangler secret put`, never in the repo): GITHUB_TOKEN (fine-grained PAT, this repo only, "Actions: read and write"), NTFY_TOPIC.
const REPO = "youssef-abd/logement-desk";
const WORKFLOW = "run.yml";
const STALE_AFTER_MIN = 60;
const gh = (env) => ({ Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "logement-cron" });

export const minutesSince = (iso, nowMs) => (iso ? (nowMs - Date.parse(iso)) / 60000 : Infinity);
export const isDue = (nowMs) => new Date(nowMs).getUTCMinutes() < 10;
const jsonRes = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json" } });

const dispatch = (env, deep = false) => fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
  method: "POST", headers: gh(env), body: JSON.stringify({ ref: "main", inputs: { mode: "full", deep: deep ? "true" : "false" } }) });
const tryDispatch = async (env, deep) => { try { return (await dispatch(env, deep)).status; } catch (e) { return 0; } };

async function alert(env, text) {
  if (!env.NTFY_TOPIC) return;
  try { await fetch(`https://ntfy.sh/${env.NTFY_TOPIC}`, { method: "POST", headers: { Title: "logement-desk", Tags: "warning" }, body: text }); } catch (e) { console.error("ntfy failed", String(e)); }
}

async function lastRun(env, extra = "") {
  const res = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?per_page=1${extra}`, { headers: gh(env) });
  if (!res.ok) return { error: `GitHub answered HTTP ${res.status}` };
  const r = ((await res.json()).workflow_runs || [])[0];
  return r ? { status: r.status, conclusion: r.conclusion, started: r.run_started_at || r.created_at, updated: r.updated_at } : { status: "none" };
}

export default {
  async scheduled(event, env) {
    if (!env.GITHUB_TOKEN) { await alert(env, "Runs are not started: the GITHUB_TOKEN secret is missing."); return; }
    let status = 0;
    for (let attempt = 1; attempt <= 2 && status !== 204; attempt++) status = await tryDispatch(env, isDue(event.scheduledTime));
    if (status !== 204 && isDue(event.scheduledTime)) await alert(env, `A run was not started (GitHub answered HTTP ${status}).${[401, 403, 404].includes(status) ? " The GitHub token has probably expired: renew it." : ""}`);
    if (isDue(event.scheduledTime)) {
      let ok = {};
      try { ok = await lastRun(env, "&status=success"); } catch (e) { ok = {}; }
      const age = minutesSince(ok.updated, Date.now());
      if (age > STALE_AFTER_MIN) await alert(env, `No successful run for ${Number.isFinite(age) ? Math.round(age) + " minutes" : "a long time"}.`);
    }
  },
  // Reached only through the desk's service binding (workers_dev = false: no public address).
  async fetch(request, env) {
    const u = new URL(request.url);
    if (!env.GITHUB_TOKEN) return jsonRes({ error: "GITHUB_TOKEN secret is not set" }, 500);
    if (request.method === "GET" && u.pathname === "/last-run") return jsonRes(await lastRun(env));
    if (request.method === "POST" && u.pathname === "/dispatch") return jsonRes({ status: (await dispatch(env)).status });
    return jsonRes({ error: "not found" }, 404);
  },
};
