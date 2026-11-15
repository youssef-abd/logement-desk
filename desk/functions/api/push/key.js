import { json } from "../../../lib/auth.js";

export async function onRequestGet({ env }) { return json({ key: env.VAPID_PUBLIC || "" }); } // public half of the key pair, not secret
