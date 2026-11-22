// Which cities the next runs collect: stored in KV by the desk, read by the Python run.
export const MAX_CITIES = 6; // every city multiplies the requests of a run
export function cleanCities(list) {
  if (!Array.isArray(list)) return [];
  return [...new Set(list.filter((k) => typeof k === "string" && /^[a-z0-9-]{2,30}$/.test(k)))].slice(0, MAX_CITIES);
}
