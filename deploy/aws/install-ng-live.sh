#!/usr/bin/env bash
# Install and start ONLY the unattended live NG collector. Historical L1/MBP jobs are untouched.
set -euo pipefail

MARKETS_DIR="${MARKETS_DIR:-/opt/markets}"
CODE_BRANCH="${MARKETS_CODE_BRANCH:-chatgpt/rt-ng-mbp10-collector}"
ENV_FILE="/etc/markets/markets.env"

if [ ! -d "$MARKETS_DIR/.git" ]; then
  echo "[install-ng-live] $MARKETS_DIR is not a git checkout" >&2
  exit 2
fi

cd "$MARKETS_DIR"
if [ -n "$(git status --porcelain)" ]; then
  echo "[install-ng-live] working tree is dirty; refusing to overwrite local work" >&2
  git status --short >&2
  exit 2
fi

echo "[install-ng-live] fetching $CODE_BRANCH"
git fetch origin "$CODE_BRANCH"
git checkout "$CODE_BRANCH" 2>/dev/null || git checkout -B "$CODE_BRANCH" "origin/$CODE_BRANCH"
git pull --ff-only origin "$CODE_BRANCH"

sudo MARKETS_DIR="$MARKETS_DIR" bash deploy/aws/setup.sh

if [ ! -f "$ENV_FILE" ]; then
  echo "[install-ng-live] missing $ENV_FILE" >&2
  exit 2
fi
if ! sudo grep -Eq '^DATABENTO_API_KEY=db-[A-Za-z0-9_-]{10,}$' "$ENV_FILE"; then
  echo "[install-ng-live] put the rotated DATABENTO_API_KEY in $ENV_FILE, then rerun" >&2
  exit 2
fi

# Keep the daily code updater on this branch until the work is merged.
if sudo grep -q '^MARKETS_CODE_BRANCH=' "$ENV_FILE"; then
  sudo sed -i "s#^MARKETS_CODE_BRANCH=.*#MARKETS_CODE_BRANCH=$CODE_BRANCH#" "$ENV_FILE"
else
  echo "MARKETS_CODE_BRANCH=$CODE_BRANCH" | sudo tee -a "$ENV_FILE" >/dev/null
fi
sudo chmod 600 "$ENV_FILE"

sudo systemctl daemon-reload
sudo systemctl enable --now markets-ng-live.service
sudo systemctl enable --now markets-ng-live-watchdog.timer

for _ in $(seq 1 30); do
  if [ -s /var/lib/markets/ng_live/health.json ]; then
    break
  fi
  sleep 2
done

sudo systemctl --no-pager --full status markets-ng-live.service || true
if [ -s /var/lib/markets/ng_live/health.json ]; then
  sudo python3 - <<'PY'
import json
p = json.load(open('/var/lib/markets/ng_live/health.json'))
print('[install-ng-live] health')
print('  connection:', p.get('connection'))
print('  symbol:', p.get('raw_symbol') or p.get('requested_symbol'))
print('  record_age_ms:', p.get('record_age_ms'))
print('  archive_bytes:', p.get('archive_bytes'))
print('  counts:', p.get('record_counts'))
print('  error:', p.get('last_error'))
PY
else
  echo "[install-ng-live] health file not produced; inspect:" >&2
  echo "  sudo journalctl -u markets-ng-live.service -n 100 --no-pager" >&2
  exit 1
fi

echo "[install-ng-live] unattended collection is enabled across logout and reboot"
