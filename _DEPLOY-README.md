# Command Center → Vercel (private, synced)

This makes your checkmarks **stick** and **sync across devices**. They no longer live in the
browser's local file storage (which is why they kept resetting) — they live in a small
backend store. The morning scan can rebuild the page all it wants; your progress is safe.

## What's in this folder
- `public/index.html` — the board (same look as your local one; checks now save to the cloud)
- `api/state.js` — tiny serverless function that reads/writes your checks, password-protected
- `build_webapp.py` — regenerates `public/index.html` from the normal local build
- `vercel.json` — config (also tells search engines not to index it)

## One-time setup (~10 min, you do these — I can't log in or enter passwords for you)

1. **Create the project on Vercel**
   - Easiest: push this `webapp/` folder to a private GitHub repo, then in Vercel → *Add New → Project* → import it.
   - Or, with the Vercel CLI: open a terminal in this `webapp/` folder and run `vercel` (then `vercel --prod`).

2. **Add the state store (free)**
   - In your Vercel project → **Storage** → create an **Upstash Redis** store (free tier is plenty for one person).
   - Vercel will auto-add `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` to the project's environment variables.

3. **Set your password**
   - Project → **Settings → Environment Variables** → add `APP_PASSWORD` = whatever password you want to type to open the board.
   - Redeploy (Vercel → Deployments → ⋯ → Redeploy) so the variables take effect.

That's it. Open the Vercel URL on any device, type your password once, and check things off —
they'll be there on your laptop and your phone.

## Security
- **`.env.local` is gitignored** — your local secrets never commit to git.
- **Vercel stores secrets securely** — use the Project Settings → Environment Variables UI, never hardcode them.
- **`.env.local.example`** shows what variables you need to set up locally (template only, no real values).

## How protected is it?
The password gate keeps the public out (and `noindex` keeps it off Google). It's solid deterrence
for confidential content, not bank-grade auth. If you ever want stronger protection, Vercel's
built-in **Deployment Protection** (Pro plan) adds an account-level password on top — optional.

## Keeping it in sync with the morning scan
Each morning the scan already runs `build_command_center.py`. To refresh the web page too, add
these two lines after it (then redeploy):

```bash
python3 "Evie Command Center/build_command_center.py"
python3 "Evie Command Center/webapp/build_webapp.py"
# then deploy webapp/  (git push if connected to GitHub, or: cd webapp && vercel --prod)
```

If you connect the GitHub repo, the simplest path is: the scan commits + pushes `webapp/public/index.html`,
and Vercel auto-deploys. Tell me once the project exists and I'll wire the scan to do this automatically.

> Note: this is intentionally separate from the SharePoint "keep local" rule — nothing here touches
> SharePoint. The board content lives in `tasks.json` (local) and is only *published* to your private Vercel URL.
