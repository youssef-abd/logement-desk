export function same(a, b) { // constant-time compare
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
export const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });
export const isOwner = (request, env) => !!env.API_TOKEN && same(request.headers.get("x-token") || "", env.API_TOKEN);
export const isPusher = (request, env) => !!env.PUSH_TOKEN && same(request.headers.get("x-push-token") || "", env.PUSH_TOKEN);
