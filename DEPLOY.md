# Deployment notes — markets-watch front-end stack

Three pieces. Each runs independently. Order: backend → frontend → Discord bot.

## 1. Backend (FastAPI, polls bins files, exposes API + SSE)

Wherever the collectors are running (Oracle Cloud, Hetzner, your laptop):

```bash
cd /path/to/Markets
pip install -r backend/requirements.txt
uvicorn backend.api_server:app --host 0.0.0.0 --port 8000
```

Health check: `curl http://localhost:8000/api/health`

Production: run under systemd or in tmux/screen. Same machine as the
collectors — it polls the same `*_bins.json` files those collectors write.

To expose externally: front it with Caddy or nginx + Let's Encrypt for
HTTPS. The frontend's PWA service worker requires HTTPS in production
(localhost is exempt for dev).

## 2. Frontend (React + Vite + Tailwind PWA)

Build once, deploy static files:

```bash
cd frontend
npm install
npm run build
# Output is in frontend/dist/
```

Deploy options for the static `dist/` folder:

- **Cloudflare Pages** (recommended): drag-and-drop the dist folder, free,
  global CDN, automatic HTTPS. Set rewrite rule so all routes serve `/index.html`.
- **Vercel**: same pattern, also free.
- **Same VM as backend**: serve via Caddy/nginx with reverse proxy `/api/*`
  to the FastAPI server.

For dev:
```bash
cd frontend && npm run dev
```
Vite dev server runs on port 5173 and proxies `/api/*` to localhost:8000.

### PWA "install on phone"

Once deployed over HTTPS, visiting the URL on a phone shows an "Add to Home
Screen" prompt (iOS Safari, Android Chrome). Installed PWA runs full-screen
with no browser chrome and supports push notifications (iOS 16.4+).

You'll need to generate `/icon-192.png` and `/icon-512.png` (the manifest
references them). Any 512×512 PNG of the project logo works; Tailwind's
slate-950 background looks good as the icon background.

## 3. Discord bot (signal poster)

```bash
cd discord_bot
pip install -r requirements.txt

# Discord Developer Portal: create app, add bot, copy token
# Server settings: invite bot with Send Messages + Embed Links scopes
# Set the channel ID where signals should post (right-click → copy id, dev mode on)

export DISCORD_BOT_TOKEN="…"
export DISCORD_CHANNEL_ID="…"
export MARKETS_WATCH_API="https://your-backend-url.com"   # default: localhost:8000

python signal_poster.py
```

The bot connects to the backend SSE stream and posts each new signal as a
color-coded embed. Slash commands work in any channel the bot can read:
- `/status` — current regime per (asset, venue)
- `/stats limit:50` — recent signal counts by regime and asset

Run under systemd or in tmux on the same VM as the backend.

## Putting it together — minimal $0 deployment plan

1. **VM**: Oracle Cloud Always-Free ARM VM (1 OCPU, 6 GB RAM — overspecced).
2. **Collectors + backend** run on the VM under tmux:
   - `python coinbase_btcusd_4hr_trajectory.py --collect-only --duration 86400 ...`
   - `python kraken_btcusd_collector.py --duration 86400 ...`
   - (similar for ETH)
   - `uvicorn backend.api_server:app --host 0.0.0.0 --port 8000`
   - `python discord_bot/signal_poster.py`
3. **Caddy reverse proxy** on the VM exposes `https://markets.yourdomain.com`
   serving `frontend/dist/` and proxying `/api/*` to localhost:8000.
4. **Discord server** with one channel for signals, one for discussion.
5. **Friends** visit the URL, hit "Add to Home Screen," get the PWA.

Total cost: $0/month for compute, $10-20/year for the domain.

## Local dev workflow (no deployment needed)

```bash
# Terminal 1: backend
cd /path/to/Markets
uvicorn backend.api_server:app --reload --port 8000

# Terminal 2: frontend
cd frontend && npm install && npm run dev

# Open http://localhost:5173
```

The frontend talks to the backend via Vite's `/api/*` proxy. Hot-reload
works for both.

## Troubleshooting

- **Frontend says "Disconnected"**: check backend `/api/health` is reachable
  and CORS allows your frontend origin. In dev the proxy handles this; in
  prod you may need to update CORS settings in `api_server.py`.
- **"No regime data yet"**: backend hasn't polled bins yet (30s delay)
  or bins files don't exist. Check `phase1_bins.json` etc are present in
  the repo root.
- **Discord bot silent**: confirm backend SSE works first
  (`curl -N http://localhost:8000/api/stream`), then check bot has access
  to the configured channel.
- **PWA won't install**: requires HTTPS (or localhost). manifest.json must
  be reachable. Service worker registration fails silently in dev tools.

## Future hardening (deferred)

- Auth: Discord OAuth2 wrapper around the API; only members of the closed
  group can hit the endpoints.
- Push notifications: extend the service worker push handler + add a
  /api/subscribe endpoint that registers the user's push subscription with
  the backend; backend sends webpush on signal events.
- Per-user mute / signal preferences.
- Audit log endpoint (Tier 2 compliance requirement).
