import { fmtRent, fmtSurface, isHttps, ago, areaName, sortRows, paginate, isNew, buildMessage, tabOf, matches, needsNudge } from "./format.js";
import { VIEWBOX, GEO } from "./geo.js";

const $ = (id) => document.getElementById(id);
const ls = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };
const S = {
  token: ls.get("ld-token") || "", data: null, marks: {}, yield: {}, sort: "newest", dense: ls.get("ld-density") === "compact", shown: 60,
  since: Number(ls.get("ld-lastvisit")) || Date.now(), f: { tab: "new", source: "all", poster: "all", kind: "all", near: true, cheap: false, q: "", area: "all", city: null, maxRent: null, furn: "known" },
};
const TABS = [["new", "New", "New listings"], ["saved", "Saved", "Saved"], ["following", "Following", "Following up"], ["closed", "Closed", "Closed"]];
const STAGES = [["none", "New"], ["saved", "Saved"], ["contacted", "Contacted"], ["visit", "Visit"], ["dossier", "Dossier sent"], ["refused", "Refused"]];
const FLAGS = { visale: "Visale accepted", student_ok: "Students accepted", student_no: "No students", garant: "Guarantor required", garant_no: "No guarantor", agency_fees: "Agency fees", agency_fees_no: "No agency fees", available_now: "Available now" };
const me = () => { try { return JSON.parse(ls.get("ld-me") || "{}"); } catch (e) { return {}; } };
const stage = (l) => (S.marks[l.id] && S.marks[l.id].s) || "none";
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }; // text only, never HTML
const median = (a) => { const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length ? (s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2) : null; };
const place = (l) => (l.postal_code ? areaName(l.postal_code) : l.district || "Area unknown");

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, cache: "no-store", headers: { "content-type": "application/json", "x-token": S.token, ...(opts.headers || {}) } });
  if (r.status === 401) throw new Error("wrong or missing access code");
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

async function load() {
  if (!S.token) { $("finding").textContent = "Open Settings and enter the access code."; return; }
  try {
    const [d, m] = await Promise.all([api("/api/listings"), api("/api/marks")]);
    S.data = d; S.marks = m.marks || {}; S.yield = d.yield || {}; $("msg").textContent = "";
  } catch (e) { $("finding").textContent = "Could not load: " + e.message; return; }
  const src = [...new Set(S.data.listings.map((l) => l.source))];
  $("source").replaceChildren(new Option("All sources", "all"), ...src.map((s) => new Option(s, s)));
  if (!src.includes(S.f.source)) S.f.source = "all";
  $("source").value = S.f.source;
  const cs = S.data.cities || [];
  const label = (k) => (cs.find((c) => c.key === k) || {}).name || k.replace(/-\d+[ab]?$/, "").replace(/-/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
  const keys = [...new Set([...cs.map((c) => c.key), ...S.data.listings.map((l) => l.city || "lyon")])]; // the city being collected, and any earlier one still listed
  $("city").replaceChildren(new Option("All cities", "all"), ...keys.map((k) => new Option(label(k), k)));
  if (S.f.city === null) S.f.city = cs.length && keys.length > 1 ? cs[0].key : "all"; // first look: the city being collected
  if (S.f.city !== "all" && !keys.includes(S.f.city)) S.f.city = "all";
  $("city").value = S.f.city; $("city").hidden = keys.length < 2;
  if (cs.length) $("scope").textContent = cs.map((c) => c.name).join(", ") + ", furnished or not";
  document.querySelector(".where").hidden = cs.length === 1 && cs[0].key !== "lyon"; // the map outlines Lyon's areas only
  setupBudget(S.data.criteria);
  render();
}

const rowsFor = (ignoreArea) => S.data.listings.filter((l) => matches(l, ignoreArea ? { ...S.f, area: "all" } : S.f, stage(l)));

function render() {
  const d = S.data; if (!d) return;
  const rows = sortRows(rowsFor(false), S.sort);
  const area = S.f.area !== "all" ? areaName(S.f.area) : "";
  const tab = TABS.find((t) => t[0] === S.f.tab);
  $("h1").textContent = tab[2] + (area ? " in " + area : "");
  $("mtitle").textContent = tab[2];
  const fresh = d.listings.filter((l) => tabOf(l, stage(l)) === "new" && isNew(l, S.since));
  const cheap = fresh.filter((l) => (l.tags || []).includes("cheap-for-area")).length;
  $("finding").textContent = fresh.length ? `${fresh.length} new since your last visit${cheap ? `, ${cheap} cheap for their area` : ""}.` : "Nothing new since your last visit.";
  const age = d.updated ? (Date.now() - Date.parse(d.updated)) / 60000 : Infinity;
  $("updated").textContent = d.updated ? "Updated " + ago(d.updated) : "No data yet";
  $("updated").classList.toggle("bad", age > 30);
  nav($("nav")); nav($("sheetnav"), true);
  kpis(rows); drawMap(); areaList(); list(rows); health();
}

function nav(box, sheet) {
  box.replaceChildren(...TABS.map(([key, name]) => {
    const n = S.data.listings.filter((l) => tabOf(l, stage(l)) === key).length;
    const b = el("button", "navbtn"); b.type = "button";
    b.append(el("span", null, name)); if (key !== "closed") b.append(el("span", "n", String(n)));
    if (S.f.tab === key) b.setAttribute("aria-current", "page");
    b.addEventListener("click", () => { S.f.tab = key; S.shown = 60; if (sheet) $("navsheet").close(); render(); });
    return b;
  }));
  if (sheet) { const s = el("button", "navbtn", "Settings"); s.type = "button"; s.addEventListener("click", () => { $("navsheet").close(); openSettings(); }); box.append(s); }
}

function kpis(rows) {
  const m = median(rows.filter((l) => l.eur_m2 != null).map((l) => l.eur_m2));
  const cells = [["Listings", String(rows.length), "", ""], ["New since your last visit", String(rows.filter((l) => isNew(l, S.since)).length), "", ""],
    ["Median price per m²", m == null ? "–" : m.toFixed(1), " €/m²", "money"], ["From private owners", String(rows.filter((l) => l.poster === "particulier").length), "", ""]];
  $("kpis").replaceChildren(...cells.map(([k, v, unit, cls]) => {
    const c = el("div", "kpi"); c.append(el("span", "k", k)); const val = el("span", "v " + cls, v); if (unit) val.append(el("small", null, unit)); c.append(val); return c;
  }));
}

/* the map: real outlines of the 16 areas, shaded by how many listings match the other filters */
const SVGNS = "http://www.w3.org/2000/svg";
const mapEls = {};
const short = (code, name) => (/^6900\d$/.test(code) ? String(Number(code.slice(4))) : name.length > 9 ? name.slice(0, 8) + "." : name);
function buildMap() {
  const svg = $("map"); svg.setAttribute("viewBox", VIEWBOX);
  for (const [code, g] of Object.entries(GEO)) {
    const p = document.createElementNS(SVGNS, "path"); p.setAttribute("d", g.path); p.setAttribute("class", "area"); p.setAttribute("tabindex", "0"); p.setAttribute("role", "button");
    const t = document.createElementNS(SVGNS, "title"); p.append(t);
    const toggle = () => { S.f.area = S.f.area === code ? "all" : code; S.shown = 60; render(); };
    p.addEventListener("click", toggle); p.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
    const lab = document.createElementNS(SVGNS, "text"); lab.setAttribute("x", g.cx); lab.setAttribute("y", g.cy); lab.setAttribute("class", "alabel"); lab.textContent = short(code, g.name);
    svg.append(p); mapEls[code] = { p, t, lab };
  }
  for (const { lab } of Object.values(mapEls)) svg.append(lab); // labels above every outline
}
function drawMap() {
  if (!Object.keys(mapEls).length) buildMap();
  const counts = {}; for (const l of rowsFor(true)) if (l.postal_code) counts[l.postal_code] = (counts[l.postal_code] || 0) + 1;
  const max = Math.max(1, ...Object.values(counts));
  for (const [code, { p, t, lab }] of Object.entries(mapEls)) {
    const n = counts[code] || 0, a = S.data.areas && S.data.areas[code];
    p.setAttribute("class", "area" + (n ? "" : " none") + (S.f.area === code ? " on" : ""));
    n ? p.setAttribute("fill-opacity", (0.14 + 0.82 * n / max).toFixed(2)) : p.removeAttribute("fill-opacity");
    p.setAttribute("aria-pressed", String(S.f.area === code));
    const txt = `${GEO[code].name}: ${n} listing${n === 1 ? "" : "s"}${a ? `, median ${a.median_eur_m2} €/m²` : ""}`;
    t.textContent = txt; p.setAttribute("aria-label", txt);
    lab.setAttribute("class", "alabel" + (n && 0.14 + 0.82 * n / max > 0.55 ? " light" : ""));
  }
  const sel = S.f.area !== "all" && S.data.areas ? S.data.areas[S.f.area] : null;
  $("maplabel").textContent = S.f.area === "all" ? "Click an area to filter the list. Darker means more listings." : `${areaName(S.f.area)}: ${counts[S.f.area] || 0} listings${sel ? `, median ${sel.median_eur_m2} €/m²` : ""}.`;
  $("clear-area").hidden = S.f.area === "all";
}

function areaList() {
  const all = median(S.data.listings.filter((l) => l.status === "active" && l.eur_m2 != null).map((l) => l.eur_m2));
  const entries = Object.entries(S.data.areas || {}).filter(([, a]) => a.n >= 5).sort((a, b) => a[1].median_eur_m2 - b[1].median_eur_m2).slice(0, 10);
  $("arealist").replaceChildren(...entries.map(([code, a]) => {
    const b = el("button", "arow" + (S.f.area === code ? " on" : "")); b.type = "button"; b.setAttribute("aria-pressed", String(S.f.area === code));
    const nm = el("span", "nm", areaName(code)); nm.append(el("i", null, a.n + " listings"));
    const d = all ? Math.round((a.median_eur_m2 / all - 1) * 100) : 0;
    b.append(nm, el("span", "dl", d === 0 ? "same as all areas" : (d > 0 ? "+" : "\u2212") + Math.abs(d) + "% vs all areas"), el("span", "md", a.median_eur_m2.toFixed(1) + " €/m²"));
    b.addEventListener("click", () => { S.f.area = S.f.area === code ? "all" : code; S.shown = 60; render(); });
    return b;
  }));
}

function list(rows) {
  const { rows: shown, rest } = paginate(rows, S.shown);
  $("list").className = S.dense ? "compact" : "";
  $("list").replaceChildren(...(shown.length ? [header(), ...shown.map(row)] : []));
  $("more").hidden = rest === 0; $("more").textContent = `Show ${Math.min(rest, 60)} more (${rest} left)`;
  $("msg").textContent = rows.length ? "" : "Nothing matches these filters.";
  $("d-cards").setAttribute("aria-pressed", String(!S.dense)); $("d-compact").setAttribute("aria-pressed", String(S.dense));
}

function header() {
  const h = el("div", "row rowhead"); h.append(el("span", "thumb-ph"), el("span", "main", "Listing"), el("span", "c-s", "Surface"), el("span", "c-p", "€/m²"), el("span", "c-r", "Rent"), el("span", "acts"));
  return h;
}

function pill(cls, text) { return el("span", "pill " + cls, text); }

function row(l) {
  const r = el("div", "row" + (l.status === "stale" ? " stale" : ""));
  const media = el("div", "media"), photos = (l.photos || []).filter(isHttps);
  const photo = (src, cls, i) => { const im = el("img", cls); im.alt = ""; im.loading = "lazy"; im.referrerPolicy = "no-referrer"; im.src = src; im.addEventListener("error", () => im.removeAttribute("src")); im.addEventListener("click", () => gallery(l, i)); return im; };
  media.append(photos[0] ? photo(photos[0], "thumb", 0) : el("div", "thumb"));
  if (photos.length > 1) { const minis = el("div", "minis"); photos.slice(1, 3).forEach((p, i) => minis.append(photo(p, "mini", i + 1))); media.append(minis); }
  const main = el("div", "main"), l1 = el("div", "l1");
  if (isNew(l, S.since)) { const d = el("span", "dot"); d.title = "New since your last visit"; l1.append(d); }
  l1.append(el("span", null, [place(l), l.rooms != null ? l.rooms + " room" + (l.rooms === 1 ? "" : "s") : ""].filter(Boolean).join(" · ")));
  const l2 = [l.source, "posted " + ago(l.posted), l.similar ? `+${l.similar} similar units` : "", l.status === "stale" ? "not in latest results" : ""].filter(Boolean).join(" · ");
  const chips = el("div", "chips"), tags = l.tags || [];
  if (l.kind === "coloc") chips.append(pill("warn", "Colocation"));
  if (l.poster === "particulier") chips.append(pill("pos", "Private owner")); else if (l.poster === "agence") chips.append(pill("", l.poster_name || "Agency"));
  if (tags.includes("near-miss")) chips.append(pill("", "over budget"));
  if (tags.includes("cheap-for-area")) chips.append(pill("pos", "cheap for the area"));
  if (l.risk === "high") chips.append(pill("neg", "high risk")); else if (l.risk === "check") chips.append(pill("warn", "check carefully"));
  for (const t of tags.filter((x) => !["near-miss", "cheap-for-area", "too-cheap"].includes(x))) chips.append(pill("", t.replace(/[-?]/g, " ").trim()));
  for (const f of (l.flags || []).filter((x) => FLAGS[x]).slice(0, 3)) chips.append(pill(f === "student_no" || f === "garant" ? "warn" : "", FLAGS[f]));
  main.append(l1, el("div", "l2", l2), chips);
  if (l.risk && (l.risk_reasons || []).length) main.append(el("div", "why", l.risk_reasons.join("; ") + "."));
  const cs = el("span", "c-s", l.surface_m2 != null ? fmtSurface(l.surface_m2) : "–"), cp = el("span", "c-p", l.eur_m2 != null ? l.eur_m2.toFixed(1) : "–"), cr = el("span", "c-r", fmtRent(l.rent_cc));
  const acts = el("div", "acts"), sel = el("select"); sel.setAttribute("aria-label", "Stage");
  for (const [v, name] of STAGES) sel.append(new Option(name, v));
  sel.value = stage(l); sel.addEventListener("change", () => setStage(l.id, sel.value));
  const copy = el("button", "btn sm", "Copy message"); copy.type = "button"; copy.addEventListener("click", () => copyMessage(l, copy));
  acts.append(sel, copy);
  const links = el("div", "links");
  if (isHttps(l.url)) { const a = el("a", null, "Open"); a.href = l.url; a.target = "_blank"; a.rel = "noopener noreferrer"; links.append(a); }
  const mk = S.marks[l.id]; if (Number.isFinite(mk && mk.t) && needsNudge(mk, Date.now())) links.append(el("span", "nudge", "contacted " + ago(new Date(mk.t).toISOString()) + ", no update"));
  acts.append(links);
  r.append(media, main, cs, cp, cr, acts); return r;
}

function copyMessage(l, btn) {
  const text = buildMessage(l, me());
  const done = (t) => { btn.textContent = t; setTimeout(() => { btn.textContent = "Copy message"; }, 1500); };
  (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => done("Copied"), () => done("Could not copy"));
}

async function setStage(id, s) {
  const t = Date.now(), prev = S.marks[id];
  if (s === "none") delete S.marks[id]; else S.marks[id] = { s, t };
  render();
  try { await api("/api/marks", { method: "POST", body: JSON.stringify({ id, s, t }) }); }
  catch (e) { if (prev) S.marks[id] = prev; else delete S.marks[id]; render(); $("msg").textContent = "Could not save: " + e.message; }
}

/* photo carousel */
const G = { photos: [], i: 0 };
function showPhoto() { $("galimg").src = G.photos[G.i]; $("galn").textContent = `${G.i + 1} / ${G.photos.length}`; }
function gallery(l, i = 0) { G.photos = (l.photos || []).filter(isHttps); G.i = i; if (!G.photos.length) return; showPhoto(); $("gal").showModal(); }
const step = (d) => { if (G.photos.length) { G.i = (G.i + d + G.photos.length) % G.photos.length; showPhoto(); } };

function health() {
  const box = $("health"); box.replaceChildren();
  for (const [name, h] of Object.entries(S.data.health || {})) {
    if (!h) continue;
    const n = Object.keys(S.yield).sort().slice(-7).reduce((a, d) => a + ((S.yield[d] || {})[name] || 0), 0);
    const bad = h.failures >= 3 || h.status === "error" || h.status === "blocked";
    box.append(el("div", bad ? "bad" : "", `${name}: ${h.status || "?"}${h.error ? " (" + h.error + ")" : ""} · last ok ${ago(h.last_success) || "never"} · ${n} new in 7 days`));
  }
}

/* settings, alerts (Web Push) and run now */
const idb = () => new Promise((res, rej) => { const r = indexedDB.open("desk", 1); r.onupgradeneeded = () => r.result.createObjectStore("kv"); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
async function idbToken(v) { try { const db = await idb(); db.transaction("kv", "readwrite").objectStore("kv").put(v, "token"); } catch (e) { /* alerts are optional */ } }
const b64u = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
const canPush = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
async function pushRefresh() {
  const btn = $("pushbtn"), msg = $("pushmsg");
  if (!canPush()) { msg.textContent = /iPhone|iPad/.test(navigator.userAgent) ? "On iPhone: Share, Add to Home Screen, open the app from there, then turn alerts on." : "This browser cannot show alerts."; btn.hidden = true; return; }
  if (Notification.permission === "denied") { msg.textContent = "Notifications are blocked for this site in the browser settings."; btn.hidden = true; return; }
  let cur = null;
  try { const reg = await navigator.serviceWorker.getRegistration("/"); cur = reg ? await reg.pushManager.getSubscription() : null; }
  catch (e) { msg.textContent = "Could not check alerts on this device."; btn.hidden = true; return; }
  msg.textContent = cur ? "Alerts are on for this device." : "Get a notification when a new flat matches."; btn.textContent = cur ? "Turn off alerts" : "Turn on alerts"; btn.hidden = false;
}
async function pushToggle() {
  $("pushbtn").disabled = true;
  try {
    if (!(await navigator.serviceWorker.getRegistration("/"))) { $("pushmsg").textContent = "Alerts need the app worker: reload the page and try again."; $("pushbtn").disabled = false; return; }
    const reg = await navigator.serviceWorker.ready, cur = await reg.pushManager.getSubscription();
    if (cur) { await api("/api/push/subscribe", { method: "DELETE", body: JSON.stringify({ endpoint: cur.endpoint }) }); await cur.unsubscribe(); }
    else {
      if ((await Notification.requestPermission()) !== "granted") { $("pushmsg").textContent = "Permission was not given."; $("pushbtn").disabled = false; return; }
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
function openSettings() {
  $("code").value = S.token; const m = me(); $("me-name").value = m.name || ""; $("me-phone").value = m.phone || ""; $("me-visale").value = m.visale || "";
  $("dlg").showModal(); pushRefresh(); if (S.token) { runRefresh(); cityRefresh(); }
}

// the budget and furnished filters start from the owner's own criteria and can be loosened up to what the run collects
function setupBudget(c) {
  const top = (c && c.collect_max_rent_cc) || 1200, own = c ? c.max_rent_cc + (c.near_miss_margin || 0) : top;
  let saved = {}; try { saved = JSON.parse(ls.get("ld-filters") || "{}"); } catch (e) { saved = {}; }
  $("rent").max = String(top);
  S.f.maxRent = Math.min(top, Number.isFinite(saved.maxRent) ? saved.maxRent : own);
  S.f.furn = ["known", "yes", "any"].includes(saved.furn) ? saved.furn : c && c.furnished === "any" ? "any" : "known";
  $("rent").value = String(S.f.maxRent); $("furn").value = S.f.furn; $("rentout").textContent = S.f.maxRent + " €";
}
const saveFilters = () => ls.set("ld-filters", JSON.stringify({ maxRent: S.f.maxRent, furn: S.f.furn }));
const rerender = () => { S.shown = 60; render(); };
// the city the next runs collect: any French commune, looked up by the desk; one at a time for now (the desk says how many are allowed)
const CITY = { chosen: [{ key: "lyon", name: "Lyon" }], max: 1 };
const nameOf = (c) => (typeof c === "string" ? ((S.data && (S.data.cities || []).find((x) => x.key === c)) || {}).name || c : c.name);
const keyOf = (c) => (typeof c === "string" ? c : c.key);
const SRC_NAMES = { bienici: "Bien'ici", leboncoin: "Leboncoin", paruvendu: "ParuVendu", foncia: "Foncia", immojeune: "ImmoJeune", studapart: "Studapart", lacartedescolocs: "La Carte des Colocs", pap: "PAP", logicimmo: "Logic-Immo" };
function srcLine(name, r) {
  const label = SRC_NAMES[name] || name, row = el("div", r.status === "ok" ? "" : "warn");
  row.textContent = r.status === "ok" ? `${label}: ${r.fetched} found, ${r.kept} kept`
    : r.status === "none" ? `${label}: nothing found (the site may not cover this city)`
    : r.status === "blocked" ? `${label}: blocked on the last run`
    : r.status === "n/a" ? `${label}: no address for this city` : `${label}: failed on the last run`;
  return row;
}
function renderCity() {
  $("citynow").textContent = CITY.chosen.map(nameOf).join(", ") || "none";
  $("citysub").textContent = `The next run (within 10 minutes) starts collecting the city you pick. ${CITY.max === 1 ? "One city at a time." : `Up to ${CITY.max} cities.`}`;
  const live = S.data && (S.data.cities || []).find((c) => c.key === keyOf(CITY.chosen[0] || ""));
  const rows = live ? Object.entries(live.sources || {}) : [];
  $("citystat").replaceChildren(...(rows.length ? [el("div", "", "Last run, per source:"), ...rows.map(([n, r]) => srcLine(n, r))] : []));
}
async function cityRefresh() {
  try { const cur = await api("/api/search"); CITY.chosen = cur.cities; CITY.max = cur.max || 1; $("citymsg").textContent = ""; }
  catch (e) { $("citymsg").textContent = "Could not load the city."; }
  renderCity();
}
let cityTimer = 0;
$("cityq").addEventListener("input", (e) => {
  clearTimeout(cityTimer);
  const q = e.target.value.trim();
  if (q.length < 2) { $("cityres").replaceChildren(); return; }
  cityTimer = setTimeout(async () => {
    try {
      const r = await api("/api/city-search?q=" + encodeURIComponent(q));
      $("cityres").replaceChildren(...(r.cities.length ? r.cities.map((c) => {
        const b = el("button", "btn", `${c.name} (${c.dept})`); b.type = "button";
        b.addEventListener("click", () => { CITY.chosen = CITY.max === 1 ? [c] : [...CITY.chosen.filter((x) => keyOf(x) !== c.key), c].slice(-CITY.max); $("cityres").replaceChildren(); $("cityq").value = ""; $("citymsg").textContent = ""; renderCity(); });
        return b;
      }) : [el("span", "sub", "No city found.")]));
    } catch (err) { $("cityres").replaceChildren(el("span", "sub", "Search failed: " + err.message)); }
  }, 300);
});
$("citysave").addEventListener("click", async () => {
  if (!CITY.chosen.length) { $("citymsg").textContent = "Pick a city first."; return; }
  try { const r = await api("/api/search", { method: "PUT", body: JSON.stringify({ cities: CITY.chosen }) }); CITY.chosen = r.cities; CITY.max = r.max || CITY.max; renderCity(); $("citymsg").textContent = "Saved. The next run starts collecting it."; }
  catch (e) { $("citymsg").textContent = "Not saved: " + e.message; }
});
$("city").addEventListener("change", (e) => { S.f.city = e.target.value; rerender(); });
$("rent").addEventListener("input", (e) => { S.f.maxRent = Number(e.target.value); $("rentout").textContent = S.f.maxRent + " €"; saveFilters(); rerender(); });
$("furn").addEventListener("change", (e) => { S.f.furn = e.target.value; saveFilters(); rerender(); });
$("sort").addEventListener("change", (e) => { S.sort = e.target.value; rerender(); });
$("source").addEventListener("change", (e) => { S.f.source = e.target.value; rerender(); });
$("kind").addEventListener("change", (e) => { S.f.kind = e.target.value; rerender(); });
$("poster").addEventListener("change", (e) => { S.f.poster = e.target.value; rerender(); });
$("near").addEventListener("change", (e) => { S.f.near = e.target.checked; rerender(); });
$("cheap").addEventListener("change", (e) => { S.f.cheap = e.target.checked; rerender(); });
$("q").addEventListener("input", (e) => { S.f.q = e.target.value; rerender(); });
$("d-cards").addEventListener("click", () => { S.dense = false; ls.set("ld-density", "cards"); render(); });
$("d-compact").addEventListener("click", () => { S.dense = true; ls.set("ld-density", "compact"); render(); });
$("more").addEventListener("click", () => { S.shown += 60; render(); });
$("clear-area").addEventListener("click", () => { S.f.area = "all"; rerender(); });
$("settings").addEventListener("click", openSettings);
$("burger").addEventListener("click", () => $("navsheet").showModal());
$("sheetclose").addEventListener("click", () => $("navsheet").close());
$("galx").addEventListener("click", () => $("gal").close());
$("galp").addEventListener("click", () => step(-1)); $("galnx").addEventListener("click", () => step(1));
$("gal").addEventListener("keydown", (e) => { if (e.key === "ArrowLeft") step(-1); else if (e.key === "ArrowRight") step(1); });
$("dlgcancel").addEventListener("click", () => $("dlg").close());
$("dlgsave").addEventListener("click", () => {
  S.token = $("code").value.trim(); ls.set("ld-token", S.token || null); idbToken(S.token);
  ls.set("ld-me", JSON.stringify({ name: $("me-name").value.trim(), phone: $("me-phone").value.trim(), visale: $("me-visale").value.trim() }));
  $("dlg").close(); load();
});
$("pushbtn").addEventListener("click", pushToggle);
$("pushtest").addEventListener("click", async () => { try { const r = await api("/api/push/test", { method: "POST" }); $("pushmsg").textContent = `Test sent to ${r.sent} of ${r.devices} device(s).`; } catch (e) { $("pushmsg").textContent = e.message; } });
$("runbtn").addEventListener("click", async () => { try { await api("/api/run", { method: "POST" }); $("runmsg").textContent = "Run started."; $("runbtn").disabled = true; } catch (e) { $("runmsg").textContent = e.message; } });
document.addEventListener("visibilitychange", () => { if (document.hidden) ls.set("ld-lastvisit", String(Date.now())); });
if ("serviceWorker" in navigator) addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
$("rank").open = window.matchMedia("(min-width: 901px)").matches; // the ranking starts folded on a phone so the listings come first
load(); setInterval(() => { if (S.token && !document.hidden) load(); }, 120000);
