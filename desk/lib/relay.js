// A fetch relay: some listing sites refuse GitHub's servers but answer Cloudflare's, so the Python run asks the desk to fetch for it.
// Only these hosts, only https, only GET: the relay is not an open proxy.
export const RELAY_HOSTS = ["www.pap.fr", "fr.foncia.com"];

export function allowedUrl(raw) {
  let u;
  try { u = new URL(raw); } catch (e) { return null; }
  if (u.protocol !== "https:" || u.username || u.password || !RELAY_HOSTS.includes(u.hostname)) return null;
  return u.toString();
}

const HEADERS = {
  "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
  "accept-language": "fr-FR,fr;q=0.9",
  accept: "text/html,application/xhtml+xml",
};

export async function relay(raw, fetcher = fetch) {
  const url = allowedUrl(raw);
  if (!url) return { status: 400, body: "url not allowed" };
  try {
    const res = await fetcher(url, { headers: HEADERS, redirect: "follow" });
    return { status: res.status, body: await res.text() };
  } catch (e) {
    return { status: 502, body: "fetch failed" };
  }
}
