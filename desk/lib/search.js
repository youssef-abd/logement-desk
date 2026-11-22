// Which city the next runs collect: stored in KV by the desk, read by the Python run.
export const MAX_CITIES = 1; // how many cities at once; every city multiplies the requests of a run. Raise it here, nowhere else.
const KEY = /^[a-z0-9-]{2,40}$/;

export const slug = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

// A choice is a key ("lyon", or a city already verified on the server) or a full city record the run builds its requests from.
export function cleanCity(c) {
  if (typeof c === "string") return KEY.test(c) ? c : null;
  if (!c || typeof c !== "object" || !KEY.test(c.key || "")) return null;
  const codes = Array.isArray(c.postal_codes) ? c.postal_codes.filter((x) => typeof x === "string" && /^\d{5}$/.test(x)).slice(0, 40) : [];
  if (!codes.length || typeof c.name !== "string" || !c.name.trim() || !/^[0-9AB]{2,3}$/.test(String(c.dept)) || !Number.isFinite(c.lat) || !Number.isFinite(c.lng)) return null;
  return { key: c.key, name: c.name.trim().slice(0, 60), dept: String(c.dept), postal_codes: codes, lat: c.lat, lng: c.lng, region: typeof c.region === "string" && /^[a-z0-9-]{1,60}$/.test(c.region) ? c.region : "" };
}

export function cleanCities(list) {
  if (!Array.isArray(list)) return [];
  const seen = new Set(), out = [];
  for (const c of list.map(cleanCity)) {
    const k = typeof c === "string" ? c : c && c.key;
    if (k && !seen.has(k)) { seen.add(k); out.push(c); }
  }
  return out.slice(0, MAX_CITIES);
}

// One commune from geo.api.gouv.fr -> a city record. Lyon is the home city: its settings live in the private profile.
export function toCity(g) {
  if (!g || typeof g.nom !== "string" || !g.departement || !g.centre || !Array.isArray(g.codesPostaux)) return null;
  const [lng, lat] = g.centre.coordinates || [];
  return cleanCity({
    key: g.code === "69123" ? "lyon" : `${slug(g.nom)}-${String(g.departement.code).toLowerCase()}`, name: g.nom, dept: String(g.departement.code),
    postal_codes: g.codesPostaux, lat, lng, region: g.region && g.region.nom ? slug(g.region.nom) : "",
  });
}
