// Web Push without payloads: a push carries no text, it only wakes sw.js, which asks /api/pending. Needs the secret VAPID_PRIVATE
// (JWK of a P-256 key), and vars VAPID_PUBLIC (raw public key, base64url) and VAPID_SUBJECT (the desk's web address, not an email).
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const enc = (s) => new TextEncoder().encode(s);

export async function vapidHeader(env, endpoint) {
  const header = b64u(enc(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const claims = b64u(enc(JSON.stringify({ aud: new URL(endpoint).origin, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: env.VAPID_SUBJECT })));
  const k = await crypto.subtle.importKey("jwk", JSON.parse(env.VAPID_PRIVATE), { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, k, enc(header + "." + claims));
  return `vapid t=${header}.${claims}.${b64u(sig)}, k=${env.VAPID_PUBLIC}`;
}

// One empty push to one device; returns the HTTP status (404 / 410 = the device is gone).
export async function sendPush(env, sub) {
  const res = await fetch(sub.endpoint, { method: "POST", headers: { Authorization: await vapidHeader(env, sub.endpoint), TTL: "21600", Urgency: "normal", "Content-Length": "0" }, signal: AbortSignal.timeout(8000) });
  return res.status;
}
