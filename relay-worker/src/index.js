// Same job as the desk's /api/relay, as its own Worker so it can be pinned to a European region.
import { same } from "../../desk/lib/auth.js";
import { relay } from "../../desk/lib/relay.js";

export default {
  async fetch(request, env) {
    if (!env.PUSH_TOKEN || !same(request.headers.get("x-push-token") || "", env.PUSH_TOKEN)) return new Response("unauthorized", { status: 401 });
    const { status, body } = await relay(new URL(request.url).searchParams.get("url") || "");
    return new Response(body, { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-relay-colo": request.cf?.colo || "" } });
  },
};
