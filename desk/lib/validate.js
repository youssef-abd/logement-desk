// Everything the desk stores or shows comes from scraped, attacker-controllable text: keep only known fields, known types, short strings.
const HOSTS = ["bienici.com", "leboncoin.fr", "lacartedescolocs.fr", "paruvendu.fr"]; // add a source's domain here when you add the source

export function safeUrl(u) {
  try {
    const x = new URL(u);
    if (x.username || x.password || x.port) return "";
    if (x.protocol !== "https:") return "";
    return HOSTS.some((d) => x.hostname === d || x.hostname.endsWith("." + d)) ? x.href : "";
  } catch (e) { return ""; }
}
const safePhoto = (u) => { try { const x = new URL(u); return x.protocol === "https:" ? x.href : ""; } catch (e) { return ""; } };
const str = (v, n) => (typeof v === "string" ? v.slice(0, n) : "");
const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const arr = (a) => (Array.isArray(a) ? a.filter((x) => typeof x === "string").map((x) => x.slice(0, 24)).slice(0, 12) : []);

export function cleanListing(l) {
  if (!l || typeof l !== "object") return null;
  const id = str(l.id, 100), url = safeUrl(l.url);
  if (!id || !url) return null;
  if (typeof l.source !== "string" || !/^[a-z0-9_]{2,30}$/.test(l.source)) return null;
  return {
    id, source: l.source, url, title: str(l.title, 120), rent_cc: num(l.rent_cc), surface_m2: num(l.surface_m2), rooms: num(l.rooms),
    kind: str(l.kind, 12) || null, district: str(l.district, 60) || null, postal_code: str(l.postal_code, 10) || null,
    furnished: typeof l.furnished === "boolean" ? l.furnished : null, poster: ["particulier", "agence"].includes(l.poster) ? l.poster : null,
    published_at: str(l.published_at, 40) || null, first_seen: str(l.first_seen, 40), last_seen: str(l.last_seen, 40),
    status: l.status === "stale" ? "stale" : "active", flags: arr(l.flags), tags: arr(l.tags),
    photos: (Array.isArray(l.photos) ? l.photos : []).map(safePhoto).filter(Boolean).slice(0, 8), also: num(l.also) || 0,
  };
}

export function cleanPayload(p) {
  if (!p || typeof p !== "object" || !Array.isArray(p.listings)) return null;
  const health = {};
  const healthEntries = Object.entries(p.health && typeof p.health === "object" ? p.health : {})
    .filter(([name, h]) => /^[a-z0-9_]{2,30}$/.test(name) && h && typeof h === "object").slice(0, 12);
  for (const [name, h] of healthEntries) {
    const run = h.run && typeof h.run === "object" ? h.run : {};
    health[name] = { last_success: str(h.last_success, 40) || null, failures: num(h.failures) || 0, error: str(h.error, 40) || null,
      cooldown_until: str(h.cooldown_until, 40) || null, status: str(run.status, 12) || null, fetched: num(run.fetched), kept: num(run.kept) };
  }
  const seen = new Set(), listings = [];
  for (const l of p.listings.map(cleanListing)) {
    if (l && !seen.has(l.id)) { seen.add(l.id); listings.push(l); }
  }
  return { updated: str(p.updated, 40), listings: listings.slice(0, 400), health };
}
