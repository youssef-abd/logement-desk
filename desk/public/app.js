import { fmtRent, fmtSurface, isHttps, ago, matches, tabOf, needsNudge } from "./format.js";

const $ = (id) => document.getElementById(id);
const ls = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };
const S = { token: ls.get("ld-token") || "", data: null, marks: {}, yield: {}, f: { tab: "new", source: "all", poster: "all", near: true, q: "" } };
const STAGES = [["none", "New"], ["contacted", "Contacted"], ["visit", "Visit"], ["dossier", "Dossier sent"], ["refused", "Refused"]];

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, cache: "no-store", headers: { "content-type": "application/json", "x-token": S.token, ...(opts.headers || {}) } });
  if (r.status === 401) throw new Error("wrong or missing access code");
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }; // text only, never HTML

async function load() {
  if (!S.token) { $("msg").textContent = "Open Settings and enter the access code."; return; }
  try {
    const [d, m] = await Promise.all([api("/api/listings"), api("/api/marks")]);
    S.data = d; S.marks = m.marks || {}; S.yield = d.yield || {}; $("msg").textContent = "";
  } catch (e) { $("msg").textContent = e.message; return; }
  const src = [...new Set(S.data.listings.map((l) => l.source))];
  $("source").replaceChildren(new Option("All sources", "all"), ...src.map((s) => new Option(s, s)));
  render();
}

function render() {
  const d = S.data; if (!d) return;
  const age = d.updated ? (Date.now() - Date.parse(d.updated)) / 60000 : Infinity;
  $("updated").textContent = d.updated ? "updated " + ago(d.updated) : "no data yet";
  $("updated").classList.toggle("bad", age > 30);
  const stage = (l) => (S.marks[l.id] && S.marks[l.id].s) || "none";
  for (const t of ["new", "following", "closed"]) $("n-" + t).textContent = d.listings.filter((l) => tabOf(l, stage(l)) === t).length;
  const rows = d.listings.filter((l) => matches(l, S.f, stage(l)));
  $("list").replaceChildren(...rows.map(card));
  if (!rows.length) $("msg").textContent = "Nothing here.";
  renderHealth();
}

function card(l) {
  const c = el("div", "card" + (l.status === "stale" ? " stale" : ""));
  const img = el("img", "thumb"); img.alt = ""; img.loading = "lazy"; img.referrerPolicy = "no-referrer";
  if (l.photos && l.photos[0] && isHttps(l.photos[0])) { img.src = l.photos[0]; img.addEventListener("error", () => { img.removeAttribute("src"); }); img.addEventListener("click", () => gallery(l)); }
  const b = el("div", "body");
  b.append(el("div", "price", `${fmtRent(l.rent_cc)} · ${fmtSurface(l.surface_m2)} · ${l.district || ""}`.replace(/ · +·/g, " ·").trim()));
  b.append(el("div", "muted", `${l.title} · ${l.source}${l.poster ? " · " + l.poster : ""}${l.also ? " · also on " + l.also + " more" : ""}`));
  const chips = el("div", "chips");
  for (const t of l.tags || []) chips.append(el("span", "chip warn", t));
  for (const t of l.flags || []) chips.append(el("span", "chip", t.replace(/_/g, " ")));
  if (l.status === "stale") chips.append(el("span", "chip", "not in latest results"));
  b.append(chips);
  const row = el("div", "row");
  if (isHttps(l.url)) { const a = el("a", null, "Open listing"); a.href = l.url; a.target = "_blank"; a.rel = "noopener noreferrer"; row.append(a); }
  const sel = el("select"); for (const [v, name] of STAGES) sel.append(new Option(name, v));
  sel.value = (S.marks[l.id] && S.marks[l.id].s) || "none";
  sel.addEventListener("change", () => setStage(l.id, sel.value));
  row.append(sel);
  if (l.photos && l.photos[0] && isHttps(l.photos[0])) { const a = el("a", null, "Image search"); a.href = "https://lens.google.com/uploadbyurl?url=" + encodeURIComponent(l.photos[0]); a.target = "_blank"; a.rel = "noopener noreferrer"; row.append(a); }
  if (needsNudge(S.marks[l.id], Date.now())) row.append(el("span", "nudge", "contacted " + ago(new Date(S.marks[l.id].t).toISOString()) + ", no update"));
  b.append(row); c.append(img, b); return c;
}

function gallery(l) {
  $("strip").replaceChildren(...(l.photos || []).filter(isHttps).map((u) => { const i = el("img"); i.src = u; i.referrerPolicy = "no-referrer"; i.alt = ""; return i; }));
  $("gal").showModal();
}

async function setStage(id, s) {
  const t = Date.now();
  if (s === "none") delete S.marks[id]; else S.marks[id] = { s, t };
  render();
  try { await api("/api/marks", { method: "POST", body: JSON.stringify({ id, s, t }) }); } catch (e) { $("msg").textContent = "Could not save: " + e.message; }
}

function renderHealth() {
  const box = $("health"); box.replaceChildren();
  for (const [name, h] of Object.entries(S.data.health || {})) {
    const days = Object.keys(S.yield).sort().slice(-7), n = days.reduce((a, d) => a + ((S.yield[d] || {})[name] || 0), 0);
    const bad = h.failures >= 3 || h.status === "error" || h.status === "blocked";
    box.append(el("div", bad ? "bad" : "", `${name}: ${h.status || "?"}${h.error ? " (" + h.error + ")" : ""} · last ok ${ago(h.last_success) || "never"} · ${n} new in 7 days`));
  }
}

/* ---- alerts (Web Push). The service worker needs the code to ask what to say, so a copy is kept in IndexedDB. ---- */
const idb = () => new Promise((res, rej) => { const r = indexedDB.open("desk", 1); r.onupgradeneeded = () => r.result.createObjectStore("kv"); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
async function idbToken(v) { try { const db = await idb(); db.transaction("kv", "readwrite").objectStore("kv").put(v, "token"); } catch (e) { /* alerts are optional */ } }
const b64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
const canPush = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

async function pushRefresh() {
  const btn = $("pushbtn"), msg = $("pushmsg");
  if (!canPush()) { msg.textContent = /iPhone|iPad/.test(navigator.userAgent) ? "On iPhone: Share, Add to Home Screen, open the app from there, then turn alerts on." : "This browser cannot show alerts."; btn.hidden = true; return; }
  if (Notification.permission === "denied") { msg.textContent = "Notifications are blocked for this site in the browser settings."; btn.hidden = true; return; }
  const reg = await navigator.serviceWorker.getRegistration("/"), cur = reg ? await reg.pushManager.getSubscription() : null;
  msg.textContent = cur ? "Alerts are on for this device." : "Get a notification when a new flat matches."; btn.textContent = cur ? "Turn off alerts" : "Turn on alerts"; btn.hidden = false;
}
async function pushToggle() {
  $("pushbtn").disabled = true;
  try {
    const reg = await navigator.serviceWorker.ready, cur = await reg.pushManager.getSubscription();
    if (cur) { await api("/api/push/subscribe", { method: "DELETE", body: JSON.stringify({ endpoint: cur.endpoint }) }); await cur.unsubscribe(); }
    else {
      if ((await Notification.requestPermission()) !== "granted") { $("pushmsg").textContent = "Permission was not given."; return; }
      const key = (await (await fetch("/api/push/key")).json()).key;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64u(key) });
      await api("/api/push/subscribe", { method: "POST", body: JSON.stringify({ subscription: sub.toJSON() }) });
      await idbToken(S.token);
    }
  } catch (e) { $("pushmsg").textContent = "Could not change alerts: " + e.message; }
  $("pushbtn").disabled = false; pushRefresh();
}

async function runRefresh() {
  try { const { last } = await api("/api/run"); $("runmsg").textContent = `Last run: ${last.status}${last.conclusion ? " (" + last.conclusion + ")" : ""} ${ago(last.updated)}`; $("runbtn").disabled = last.status === "in_progress" || last.status === "queued"; }
  catch (e) { $("runmsg").textContent = e.message; }
}

$("tabs").addEventListener("click", (e) => { const t = e.target.closest("button"); if (!t) return; S.f.tab = t.dataset.tab; for (const b of $("tabs").children) b.setAttribute("aria-selected", String(b === t)); $("msg").textContent = ""; render(); });
for (const [id, key] of [["source", "source"], ["poster", "poster"]]) $(id).addEventListener("change", (e) => { S.f[key] = e.target.value; render(); });
$("near").addEventListener("change", (e) => { S.f.near = e.target.checked; render(); });
$("q").addEventListener("input", (e) => { S.f.q = e.target.value; render(); });
$("galx").addEventListener("click", () => $("gal").close());
$("menu").addEventListener("click", () => { $("code").value = S.token; $("dlg").showModal(); pushRefresh(); if (S.token) runRefresh(); });
$("dlgcancel").addEventListener("click", () => $("dlg").close());
$("dlgsave").addEventListener("click", () => { S.token = $("code").value.trim(); ls.set("ld-token", S.token || null); idbToken(S.token); $("dlg").close(); load(); });
$("pushbtn").addEventListener("click", pushToggle);
$("pushtest").addEventListener("click", async () => { try { const r = await api("/api/push/test", { method: "POST" }); $("pushmsg").textContent = `Test sent to ${r.sent} of ${r.devices} device(s).`; } catch (e) { $("pushmsg").textContent = e.message; } });
$("runbtn").addEventListener("click", async () => { try { await api("/api/run", { method: "POST" }); $("runmsg").textContent = "Run started."; $("runbtn").disabled = true; } catch (e) { $("runmsg").textContent = e.message; } });
if ("serviceWorker" in navigator) addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
load(); setInterval(() => { if (S.token && !document.hidden) load(); }, 120000);
