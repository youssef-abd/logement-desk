export function same(a, b) { // constant-time compare
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
export const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });
export const isOwner = (request, env) => !!env.API_TOKEN && same(request.headers.get("x-token") || "", env.API_TOKEN);
// The owner's access code can be switched off for a while: KV key "auth_off" = "1" (wrangler kv key put/delete, no redeploy).
// Only the harmless parts use it (reading, stage marks, the city choice). Starting a run and the push endpoints always need the code.
export const canUse = async (request, env) => isOwner(request, env) || (await env.DESK.get("auth_off")) === "1";
export const isPusher = (request, env) => !!env.PUSH_TOKEN && same(request.headers.get("x-push-token") || "", env.PUSH_TOKEN);
