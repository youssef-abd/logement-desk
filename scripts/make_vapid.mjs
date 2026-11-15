import { webcrypto as c } from "node:crypto";
import { writeFileSync } from "node:fs";
const b64u = (b) => Buffer.from(b).toString("base64url");
const kp = await c.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
const pub = b64u(await c.subtle.exportKey("raw", kp.publicKey));
const jwk = await c.subtle.exportKey("jwk", kp.privateKey);
const rnd = () => b64u(c.getRandomValues(new Uint8Array(24)));
writeFileSync(".vapid.json", JSON.stringify({ vapid_public: pub, vapid_private_jwk: jwk, api_token: rnd(), push_token: rnd() }, null, 2));
console.log("wrote .vapid.json (gitignored). VAPID_PUBLIC =", pub);
