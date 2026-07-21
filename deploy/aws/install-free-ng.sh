#!/usr/bin/env bash
# Install and start only the free EIA + NOAA/NWS collectors on the Markets AWS box.
# No paid data key is required; historical and live Databento jobs are untouched.
set -euo pipefail

MARKETS_DIR="${MARKETS_DIR:-/opt/markets}"
CODE_BRANCH="${MARKETS_CODE_BRANCH:-chatgpt/rt-ng-mbp10-collector}"

if [ ! -d "$MARKETS_DIR/.git" ]; then
  echo "[install-free-ng] $MARKETS_DIR is not a git checkout" >&2
  exit 2
fi
cd "$MARKETS_DIR"
if [ -n "$(git status --porcelain)" ]; then
  echo "[install-free-ng] working tree is dirty; refusing to overwrite local work" >&2
  git status --short >&2
  exit 2
fi

git fetch origin "$CODE_BRANCH"
git checkout "$CODE_BRANCH" 2>/dev/null || git checkout -B "$CODE_BRANCH" "origin/$CODE_BRANCH"
git pull --ff-only origin "$CODE_BRANCH"
sudo MARKETS_DIR="$MARKETS_DIR" bash deploy/aws/setup.sh
sudo systemctl enable --now markets-free-ng.timer
sudo systemctl start markets-free-ng.service

for _ in $(seq 1 60); do
  if [ -s /var/lib/markets/free_ng/latest.json ]; then break; fi
  sleep 2
done
sudo systemctl --no-pager --full status markets-free-ng.timer || true
sudo systemctl --no-pager --full status markets-free-ng.service || true
if [ ! -s /var/lib/markets/free_ng/latest.json ]; then
  echo "[install-free-ng] snapshot missing; inspect journalctl -u markets-free-ng.service" >&2
  exit 1
fi
sudo python3 - <<'PY'
import json
p=json.load(open('/var/lib/markets/free_ng/latest.json'))
print('[install-free-ng] status:',p.get('status'))
print('[install-free-ng] sources:',sorted(p.get('sources',{})))
print('[install-free-ng] errors:',p.get('errors'))
print('[install-free-ng] storage:',p.get('sources',{}).get('eia',{}).get('storage',{}).get('latest'))
print('[install-free-ng] weather:',p.get('sources',{}).get('nws',{}).get('gas_weighted_next_24h'))
PY

echo "[install-free-ng] free collectors are running every 30 minutes across logout and reboot"
