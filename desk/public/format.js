export const fmtRent = (n) => (n == null ? "? €" : `${Math.round(n)} €`);
export const fmtSurface = (n) => (n == null ? "" : `${Math.round(n)} m²`);
export const isHttps = (u) => typeof u === "string" && u.startsWith("https://");

export function ago(iso, nowMs = Date.now()) {
  if (!iso) return "";
  const m = Math.max(0, Math.round((nowMs - Date.parse(iso)) / 60000));
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} d ago`;
}

export const AREA_NAMES = {
  ...Object.fromEntries(Array.from({ length: 9 }, (_, i) => [String(69001 + i), i === 0 ? "Lyon 1er" : `Lyon ${i + 1}e`])),
  69100: "Villeurbanne", 69300: "Caluire", 69500: "Bron", 69200: "Vénissieux", 69600: "Oullins", 69190: "Saint-Fons", 69130: "Écully",
};
export const areaName = (code) => AREA_NAMES[code] || code;

const ms = (iso) => { const n = Date.parse(iso); return Number.isFinite(n) ? n : -Infinity; };
const asc = (k) => (a, b) => (a[k] == null) - (b[k] == null) || (a[k] ?? 0) - (b[k] ?? 0);
const SORTS = {
  newest: (a, b) => ms(b.posted) - ms(a.posted) || ms(b.first_seen) - ms(a.first_seen) || 0,
  price: asc("rent_cc"),
  eur_m2: asc("eur_m2"),
  size: (a, b) => (a.surface_m2 == null) - (b.surface_m2 == null) || (b.surface_m2 ?? 0) - (a.surface_m2 ?? 0),
};
export const sortRows = (rows, key) => [...rows].sort(SORTS[key] || SORTS.newest);
export const paginate = (rows, shown) => ({ rows: rows.slice(0, shown), rest: Math.max(0, rows.length - shown) });
export const isNew = (l, sinceMs) => { const n = Date.parse(l.first_seen); return Number.isFinite(n) && n > sinceMs; };

export function buildMessage(l, me = {}) {
  const facts = [l.rent_cc != null && `${Math.round(l.rent_cc)} €`, l.surface_m2 != null && `${Math.round(l.surface_m2)} m²`].filter(Boolean).join(", ");
  const what = [l.title, l.district].filter(Boolean).join(", ");
  const lines = [
    "Bonjour,", "",
    `Je suis intéressé(e) par votre annonce${what ? " « " + what + " »" : ""}${facts ? " (" + facts + ")" : ""}.`,
    `Mon dossier est complet et je suis disponible immédiatement${me.visale ? ". Mon numéro Visale : " + me.visale : ""}.`,
    "Serait-il possible d'organiser une visite, ou une visite en vidéo si je ne suis pas sur place ?", "",
    "Cordialement,",
  ];
  if (me.name) lines.push(me.name);
  if (me.phone) lines.push(me.phone);
  return lines.join("\n");
}

export function tabOf(l, stage) {
  if (stage === "saved") return "saved";
  if (["contacted", "visit", "dossier"].includes(stage)) return "following";
  if (stage === "refused" || l.status === "stale") return "closed";
  return "new";
}

export function matches(l, f, stage) {
  if (tabOf(l, stage) !== f.tab) return false;
  if (f.source !== "all" && l.source !== f.source) return false;
  if (f.poster !== "all" && l.poster !== f.poster) return false;
  if (f.kind === "coloc" && l.kind !== "coloc") return false;
  if (f.kind === "flat" && l.kind === "coloc") return false;
  if (["studio", "t1", "t2", "t3+", "room"].includes(f.kind) && l.kind !== f.kind) return false;
  if (f.maxRent != null && l.rent_cc != null && l.rent_cc > f.maxRent) return false;
  if (f.furn === "yes" && l.furnished !== true) return false;
  if (f.furn === "known" && l.furnished === false) return false;
  if (f.area && f.area !== "all" && l.postal_code !== f.area) return false;
  if (f.cheap && !(l.tags || []).includes("cheap-for-area")) return false;
  if (!f.near && (l.tags || []).includes("near-miss")) return false;
  return !f.q || `${l.title} ${l.district || ""} ${l.source}`.toLowerCase().includes(f.q.toLowerCase());
}

export const needsNudge = (mark, nowMs, days = 3) => !!mark && mark.s === "contacted" && nowMs - mark.t > days * 86400000;
