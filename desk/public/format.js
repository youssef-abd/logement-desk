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

export function tabOf(l, stage) {
  if (["contacted", "visit", "dossier"].includes(stage)) return "following";
  if (stage === "refused" || l.status === "stale") return "closed";
  return "new";
}

export function matches(l, f, stage) {
  if (tabOf(l, stage) !== f.tab) return false;
  if (f.source !== "all" && l.source !== f.source) return false;
  if (f.poster !== "all" && l.poster !== f.poster) return false;
  if (!f.near && (l.tags || []).includes("near-miss")) return false;
  return !f.q || `${l.title} ${l.district || ""} ${l.source}`.toLowerCase().includes(f.q.toLowerCase());
}

export const needsNudge = (mark, nowMs, days = 3) => !!mark && mark.s === "contacted" && nowMs - mark.t > days * 86400000;
