const STAGES = new Set(["contacted", "visit", "dossier", "refused", "none"]);
// Returns the new marks object, or null when the input is invalid.
export function applyMark(marks, b) {
  if (!b || !/^[A-Za-z0-9_.:-]{1,100}$/.test(b.id || "") || !STAGES.has(b.s) || !Number.isFinite(b.t)) return null;
  const next = { ...marks };
  if (b.s === "none") { delete next[b.id]; return next; }
  if (!next[b.id] && Object.keys(next).length >= 1000) return null;
  if (!next[b.id] || next[b.id].t <= b.t) next[b.id] = { s: b.s, t: b.t };
  return next;
}
