# Launch playbook — operational steps that have to happen on real hardware / accounts

This is the step-by-step you'll work through to take markets-watch from
"all the code is committed" to "Tier 1 launch with the closed friends
group." None of these steps can happen inside a sandbox — they involve
real domain names, real exchange dashboards, real API keys, real money.

The list is grouped by area. Within each area, do the steps in order.
Each step has: **what**, **why**, **how**, **verify**.

---

## 1. Backend deployment + HTTPS (Caddy)

### 1.1 Provision a host

- **What**: a small VM (DigitalOcean, Linode, Hetzner, AWS Lightsail).
  2 vCPU / 4 GB RAM is enough for the closed group.
- **Why**: the central PWA + backend has to be reachable on a public
  domain over HTTPS for the service worker + push subscription to work
  on phones.
- **How**: spin up Ubuntu 22.04 LTS or 24.04 LTS, harden with `ufw`
  (allow 22, 80, 443; deny everything else), create a non-root user
  with sudo + ssh-key access, disable password auth.
- **Verify**: `ssh user@host` works with key, password auth is off in
  `/etc/ssh/sshd_config`.

### 1.2 Point a domain at the host

- **What**: a real DNS name like `markets.yourname.com` pointing at the
  VM's IPv4 (and IPv6 if available).
- **Why**: Let's Encrypt needs DNS to validate; iOS's "Add to Home
  Screen" install prompt only fires on HTTPS sites with a real cert.
- **How**: register or reuse a domain. Add an A record (and AAAA if
  v6) to your DNS provider pointing at the VM. Use a 5-minute TTL until
  it's stable, then bump to an hour.
- **Verify**: `dig +short markets.yourname.com` returns the VM IP from
  multiple resolvers; takes ~5 minutes after edit.

### 1.3 Install Caddy + deploy our config

- **What**: Caddy as the reverse proxy + auto-Let's-Encrypt cert.
- **Why**: simplest possible HTTPS setup; no manual cert renewal.
- **How**:
  ```bash
  sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt update && sudo apt install -y caddy

  # Clone the repo on the host:
  git clone https://github.com/davisai1974/markets.git /opt/markets
  cd /opt/markets

  # Edit deploy/Caddyfile — replace markets.example.com with your real domain
  sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
  sudo $EDITOR /etc/caddy/Caddyfile     # edit the domain on line ~32

  sudo systemctl enable --now caddy
  ```
- **Verify**: `curl -I https://markets.yourname.com/` returns a 200 or
  404 (404 is fine — means Caddy is serving but the static dir is
  empty; we'll fix in 1.5). Check Caddy log: `sudo journalctl -u caddy
  -f` should show "certificate obtained successfully".

### 1.4 Build + deploy the PWA

- **What**: build the React/Vite frontend and copy the `dist/` to where
  Caddy expects.
- **How**:
  ```bash
  # On the host:
  cd /opt/markets/frontend
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt install -y nodejs
  npm install
  npm run build
  sudo mkdir -p /var/www/markets-watch
  sudo cp -r dist/* /var/www/markets-watch/
  ```
- **Verify**: `https://markets.yourname.com/` loads the PWA. The
  "Live", "Signals", "Practice", "History", "Stats", "About" tabs are
  visible. The connection dot in the top right is red (because the
  backend isn't running yet — that's expected).

### 1.5 Set up the backend as a systemd service

- **What**: backend running under uvicorn, restart-on-fail, auto-start
  on boot.
- **How**: create `/etc/systemd/system/markets-watch-backend.service`:
  ```ini
  [Unit]
  Description=markets-watch backend
  After=network.target

  [Service]
  Type=simple
  User=ubuntu
  WorkingDirectory=/opt/markets
  Environment="MARKETS_WATCH_ACCESS_TOKEN=set-a-long-random-string"
  Environment="VAPID_PRIVATE_KEY="
  Environment="VAPID_PUBLIC_KEY="
  Environment="VAPID_CONTACT_EMAIL=mailto:you@yourname.com"
  ExecStartPre=/usr/bin/pip install -q -r backend/requirements.txt
  ExecStart=/usr/bin/python -m uvicorn backend.api_server:app --host 127.0.0.1 --port 8080
  Restart=on-failure
  RestartSec=5

  [Install]
  WantedBy=multi-user.target
  ```
  Then:
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl enable --now markets-watch-backend
  ```
- **Verify**: `curl -I http://127.0.0.1:8080/api/health` returns 200
  on the VM. Then `curl -I https://markets.yourname.com/api/health`
  returns 200 from your laptop. The PWA's connection dot turns green.

### 1.6 Build the playbook registry

- **What**: per-(asset, venue, regime) edge stats that drive the
  dynamic playbook strings the PWA + Discord embed.
- **Why**: without it, signals fall back to per-regime defaults that
  ignore venue-specific dynamics (CB momentum vs KR mean-reversion,
  etc.). The fallback is safe — signals still emit — but you lose the
  per-venue precision until the registry is built.
- **How**, on the host (after the backend is running and the data
  branch has at least 1 collection cycle):
  ```bash
  cd /opt/markets
  git fetch origin data/eth-bins
  git checkout origin/data/eth-bins -- eth_coinbase_bins.json eth_kraken_bins.json
  python build_playbook_registry.py --asset ETH \
      --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \
      --output-path /opt/markets/playbook_registry.json
  # Repeat per asset as you add them (BTC, etc.)
  ```
  The backend hot-reloads the registry by mtime — no restart needed.
- **Schedule**: rerun after each GHA collection cycle. Add to crontab:
  ```cron
  10 */6 * * * cd /opt/markets && git fetch origin data/eth-bins && \
    git checkout origin/data/eth-bins -- eth_coinbase_bins.json eth_kraken_bins.json && \
    python build_playbook_registry.py --asset ETH \
      --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json \
      --output-path /opt/markets/playbook_registry.json
  ```
  This runs ~10 minutes after each GHA cycle finishes.
- **Verify**: `cat /opt/markets/playbook_registry.json | python -m
  json.tool` shows entries like `"ETH/CB/WHALE_UP"`. Trigger a test
  signal and confirm the playbook text in Discord includes the
  `[n=..., r=..., p=...]` caveat.

---

## 2. VAPID keys (Web Push)

### 2.1 Generate the keypair

- **What**: a P-256 ECDSA keypair used to sign push notifications so
  browsers trust them.
- **Why**: without it, the "Notify me on new signals" button in
  Onboarding stays disabled.
- **How**, on the host:
  ```bash
  cd /opt/markets
  python -m backend.push --generate-keys
  ```
  Output is two long URL-safe-base64 strings: `private_b64u` and
  `public_b64u`.
- **Verify**: both strings are present in stdout.

### 2.2 Wire them into the systemd service

- **How**: edit the service file from §1.5 — set `VAPID_PRIVATE_KEY` to
  `private_b64u` and `VAPID_PUBLIC_KEY` to `public_b64u`. Also set
  `VAPID_CONTACT_EMAIL` to `mailto:` plus your real email (this is in
  the Web Push spec; if pushes fail the browser vendor needs to be
  able to reach you).
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl restart markets-watch-backend
  ```
- **Verify**: `curl https://markets.yourname.com/api/push/vapid-public-key`
  returns `{"public_key":"...", "configured": true}`.

### 2.3 Test the subscription on a real phone

- **What**: install the PWA on a phone and confirm push arrives.
- **How**:
  - Android Chrome: open the URL → menu → "Install app" → in the
    installed app, go to About → tap "Notify me on new signals" → grant
    permission. Should switch to "Notifications ON".
  - iOS Safari: open the URL → Share → Add to Home Screen → open the
    app from the Home Screen (not Safari) → About → "Notify me" → grant.
- **Verify**: trigger a test signal (next section) and confirm it
  arrives as a system notification on the phone.

---

## 3. Discord bot

### 3.1 Create a Discord application

- **What**: a Discord bot account scoped to your closed group's server.
- **How**:
  1. Go to <https://discord.com/developers/applications>
  2. Click "New Application", name it "markets-watch"
  3. Under "Bot" tab → "Add Bot" → "Reset Token" → copy the token
     (you'll never see it again; store it securely)
  4. Under "Bot" → "Privileged Gateway Intents" → leave all OFF (we
     don't need Message Content)
  5. Under "OAuth2" → "URL Generator":
     - Scopes: `bot`, `applications.commands`
     - Bot permissions: `Send Messages`, `Embed Links`, `Read Message
       History`, `Use Slash Commands`, `Attach Files`
  6. Open the generated URL → select your closed-group server →
     authorize
- **Verify**: the bot appears in your Discord server's member list,
  greyed out (offline).

### 3.2 Get the channel ID

- **What**: the Discord channel ID where signals will post.
- **How**: in Discord client settings → Advanced → enable "Developer
  Mode". Right-click the target channel → "Copy Channel ID".

### 3.3 Run the bot on the host

- **What**: signal_poster.py running under systemd next to the backend.
- **How**: create `/etc/systemd/system/markets-watch-discord.service`:
  ```ini
  [Unit]
  Description=markets-watch Discord bot
  After=markets-watch-backend.service
  Wants=markets-watch-backend.service

  [Service]
  Type=simple
  User=ubuntu
  WorkingDirectory=/opt/markets
  Environment="DISCORD_BOT_TOKEN=YOUR_BOT_TOKEN_FROM_3.1"
  Environment="DISCORD_CHANNEL_ID=YOUR_CHANNEL_ID_FROM_3.2"
  Environment="MARKETS_WATCH_API=http://127.0.0.1:8080"
  Environment="SIGNAL_POSTER_NAME=markets-watch"
  ExecStartPre=/usr/bin/pip install -q -r discord_bot/requirements.txt
  ExecStart=/usr/bin/python discord_bot/signal_poster.py
  Restart=on-failure
  RestartSec=10

  [Install]
  WantedBy=multi-user.target
  ```
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl enable --now markets-watch-discord
  ```
- **Verify**: bot status flips to online in Discord. Slash commands
  `/status` and `/stats` work in the channel. Trigger a test signal
  (DEMO mode is on by default) and a rich embed posts.

---

## 4. Exchange wallet wiring (per user)

Each member who wants automated trading does this on their own machine.
Don't do it on the central host — keys must never touch infrastructure
that handles other people's data.

The order matters: **testnet first, then small-position live, then
full-size live.** Don't skip steps.

### 4.1 Coinbase Advanced Trade

- **Testnet**: Coinbase doesn't have a public testnet. Skip ahead to
  small-position live (4.1.b) but cap your first orders at the
  exchange minimum.
- **4.1.a — Real-money key generation**:
  1. Sign in to <https://www.coinbase.com>
  2. Settings → API → New API Key
  3. Permissions: `wallet:accounts:read`, `wallet:user:read`,
     `wallet:trades:read`, `wallet:trades:create`. **Do NOT enable
     `wallet:withdraw`** — markets-watch never needs to withdraw.
  4. IP whitelist: add your home IP or VPN endpoint
  5. Copy the API Key + API Secret. Store them in your password manager.
- **4.1.b — Local config**:
  ```bash
  # On your own laptop:
  cd ~/markets    # your local clone
  cp executor/config.example.json my_config.json
  # Edit my_config.json: set settings.exchange to "coinbase"
  export COINBASE_API_KEY=...
  export COINBASE_API_SECRET=...
  # First: dry-run (no real orders, no API calls)
  python -m executor.executor --config my_config.json --dry-run
  # Then: adapter dry-run (signed requests built but not sent)
  python -m executor.executor --config my_config.json
  # Verify the audit log shows "DRYRUN-..." order ids:
  tail executor/audit.jsonl
  ```
- **4.1.c — Small-position live verification**:
  1. Set `EXCHANGE_LIVE=1` in your shell.
  2. In your config, set `position_size_usd` to **$10** (or
     whatever's just above Coinbase's minimum order size).
  3. Run the executor.
  4. Wait for one signal to fire and watch the audit log + your
     Coinbase order history. Verify the order appears, fills, and the
     position lookup matches.
  5. Manually close the position on Coinbase to flatten.
- **Verify before scaling up**: at least 3 small live trades complete
  end-to-end (open + close), audit log entries match the exchange's
  trade history exactly, fees match what we computed.

### 4.2 Binance Spot

- **Testnet (recommended first)**:
  1. Go to <https://testnet.binance.vision>
  2. Generate testnet API keys (separate from real Binance)
  3. Set `BINANCE_REST=https://testnet.binance.vision` and the testnet
     keys in env
  4. Run the executor in live mode (`EXCHANGE_LIVE=1`) on testnet
  5. Verify orders place, fill, and balances update on the testnet
     dashboard
- **4.2.a — Real-money key generation**:
  1. Sign in to <https://binance.com>
  2. Account → API Management → Create API
  3. Restrict permissions to "Enable Spot & Margin Trading" only.
     **Do NOT enable "Enable Withdrawals"**.
  4. IP whitelist: your home IP
  5. Copy the API Key + Secret Key
- **4.2.b — Switch from testnet to live**:
  ```bash
  unset BINANCE_REST   # default is api.binance.com
  export BINANCE_API_KEY=...    # real keys
  export BINANCE_API_SECRET=...
  ```
- **4.2.c — Small-position live**: same protocol as 4.1.c, $10 size.
  Note Binance's min order size is in coin units (`MIN_NOTIONAL`),
  often around $5–$10.

### 4.3 Kraken

- **Testnet**: Kraken doesn't have a public spot testnet. Practice
  mode (in the PWA) is your validation; then go straight to small-
  position live.
- **4.3.a — Real-money key generation**:
  1. Sign in to <https://kraken.com>
  2. Settings → API → Generate New Key
  3. Permissions: enable `Query Funds`, `Query Open Orders & Trades`,
     `Query Closed Orders & Trades`, `Modify Orders`. **Do NOT enable
     `Withdraw Funds`** or `Deposit Funds`.
  4. IP whitelist: your home IP
  5. Copy the API Key + Private Key (the Private Key is base64-encoded;
     paste it as-is into the env var)
- **4.3.b — Local config**:
  ```bash
  export KRAKEN_API_KEY=...
  export KRAKEN_API_SECRET=...   # base64-encoded; do NOT decode it
  # In my_config.json: settings.exchange = "kraken"
  python -m executor.executor --config my_config.json --dry-run
  python -m executor.executor --config my_config.json   # adapter dry-run
  ```
- **4.3.c — Small-position live**: same protocol. Kraken's min sizes
  vary per asset (BTC ~0.0001, ETH ~0.002).

---

## 5. End-to-end smoke test before opening to friends

Before you tell the closed group "go install the app and turn on
notifications," run this checklist yourself:

1. ☐ Backend up; `https://markets.yourname.com/api/health` returns 200
2. ☐ PWA loads on Android Chrome and iOS Safari (after Add-to-Home-
   Screen)
3. ☐ "Notify me" button works on both phones; you receive a push when
   a signal fires
4. ☐ Discord bot online; `/status` returns current regimes; a real
   signal posts as a multi-embed with chart attachment
5. ☐ Practice mode on the PWA: tap a bid/ask cell, place a practice
   trade, watch it appear on the Practice tab, close it manually
6. ☐ For at least one of (Coinbase / Binance / Kraken), you've
   completed 4.x.c — a $10 live trade end-to-end with matching audit
7. ☐ Multi-day GHA collection still running on `data/eth-bins`
   (rerun `phase1_5_evaluator.py` to confirm gates still pass with
   more data)

If any item is unchecked, do not open to the group yet.

---

## 6. Onboarding the closed group

When the smoke test passes:

1. **Send the install link** with both Android and iOS install steps
   (Share → Add to Home Screen on iOS is non-obvious; include a
   screenshot).
2. **Walk every member through Practice mode first.** Tell them not to
   flip the Live toggle for the first week. Watch their practice P&L
   on `/api/practice-trades` (you can add a backend admin route if
   needed).
3. **Live mode is opt-in per member.** Each member who wants it does
   §4 themselves on their own machine. You don't host their keys; you
   don't see their balances; you don't sign their orders.
4. **Set group house rules in Discord pinned post**: research not
   advice; closed group; no sharing; each member's risk is their own.

---

## 7. Operational hygiene (ongoing)

- **Backend logs**: `sudo journalctl -u markets-watch-backend -f`
- **Discord bot logs**: `sudo journalctl -u markets-watch-discord -f`
- **Caddy logs**: `/var/log/caddy/markets-watch.log`
- **Cert renewal**: automatic via Caddy; verify with
  `sudo systemctl status caddy` once a month
- **Update cycle**: when you `git pull` on the host:
  ```bash
  cd /opt/markets && git pull
  cd frontend && npm run build && sudo cp -r dist/* /var/www/markets-watch/
  sudo systemctl restart markets-watch-backend markets-watch-discord
  ```
- **Backups**: rsync `/opt/markets/backend_signals.jsonl`,
  `backend_practice_trades.jsonl`, and `data/eth-bins` periodically
  to a separate host so you can roll back state.

---

## 8. Failure modes you should rehearse

- **Backend dies**: systemd restarts it. PWA shows red dot, SSE
  reconnects automatically when backend comes back. Push notifications
  resume immediately. **No data loss** because bins are written by
  GHA collectors to a separate branch.
- **Caddy cert renewal fails**: extremely rare. Cert valid for 90
  days, attempt renewal at 60. If it fails, `journalctl -u caddy`
  shows the error; usually a DNS or rate-limit issue.
- **An exchange API returns 5xx for a signed request**: the adapter
  returns `OrderResult(success=False, error=...)` and the executor
  audits it. The user is responsible for handling — it's their wallet.
- **Push notifications stop arriving**: usually because the user
  cleared their browser data, or because Apple's push service is
  flaky. The Notify Me button is idempotent — re-tapping re-subscribes.
- **Discord bot offline**: Discord rate-limited or token revoked.
  Restart `markets-watch-discord` service; if revoked, regenerate the
  bot token in the Developer Portal and update the systemd unit.

If something goes wrong outside business hours and a member is mid-
trade, the executor audit log + their exchange's order history are the
truth — you don't owe anyone real-time support, this is research, not
a brokerage.
