// Command Center — checkmark/note state store.
// Password-gated. Persists ONE JSON blob to Upstash Redis (REST), so your
// progress syncs across devices and survives every morning rebuild/redeploy.
//
// Required Vercel environment variables (Project → Settings → Environment Variables):
//   APP_PASSWORD               the password you'll type to unlock the board
//   UPSTASH_REDIS_REST_URL     from the Upstash Redis store (Vercel Marketplace)
//   UPSTASH_REDIS_REST_TOKEN   from the same store
//
// No npm install needed — uses built-in fetch (Node 18+).

// Accept either naming scheme: Vercel's Upstash integration creates KV_REST_API_*;
// a manual Upstash setup creates UPSTASH_REDIS_REST_*. Use whichever exists.
const REDIS_URL = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const REDIS_TOKEN = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
const APP_PASSWORD = process.env.APP_PASSWORD;
const RKEY = "cc:state";

async function redis(command) {
  const r = await fetch(REDIS_URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${REDIS_TOKEN}`, "content-type": "application/json" },
    body: JSON.stringify(command),
  });
  if (!r.ok) throw new Error("redis " + r.status);
  return (await r.json()).result;
}

export default async function handler(req, res) {
  if (!REDIS_URL || !REDIS_TOKEN) {
    res.status(500).json({ error: "Server not configured. Set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN." });
    return;
  }

  // Body may be a parsed object (application/json) or a string (sendBeacon).
  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch (e) { body = {}; } }
  body = body || {};

  try {
    if (req.method === "GET") {
      const raw = await redis(["GET", RKEY]);
      res.status(200).json({ state: raw ? JSON.parse(raw) : {} });
      return;
    }
    if (req.method === "POST") {
      const state = body.state || {};
      await redis(["SET", RKEY, JSON.stringify(state)]);
      res.status(200).json({ ok: true });
      return;
    }
    res.status(405).json({ error: "method not allowed" });
  } catch (e) {
    res.status(500).json({ error: String(e && e.message || e) });
  }
}
