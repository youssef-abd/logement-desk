const rent = (n) => (n == null ? "? €" : `${Math.round(n)} €`);
export function oneLine(l) {
  const p = [rent(l.rent_cc)];
  if (l.surface_m2 != null) p.push(`${Math.round(l.surface_m2)} m²`);
  if (l.district) p.push(l.district);
  if (l.poster) p.push(l.poster);
  return p.join(" · ");
}
// Built only from validated fields (never from description text). One new listing: tap opens it. Several: tap opens the desk.
export function messageFor(fresh) {
  if (!fresh.length) return null;
  if (fresh.length === 1) return { body: oneLine(fresh[0]), url: fresh[0].url };
  const best = [...fresh].sort((a, b) => (a.rent_cc ?? 1e9) - (b.rent_cc ?? 1e9))[0];
  return { body: `${fresh.length} new: from ${oneLine(best)}`, url: "/" };
}
