#!/usr/bin/env bash
# deploy/aws/setup.sh — idempotent setup for the durable Markets AWS box.
# Historical jobs and the live NG collector are separate systemd services.
set -euo pipefail

MARKETS_DIR="${MARKETS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
RUN_USER="${SUDO_USER:-$(id -un)}"
echo "[setup] Markets dir = $MARKETS_DIR ; run user = $RUN_USER"

echo "[setup] installing system deps..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git python3 python3-pip

echo "[setup] installing python deps..."
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade databento boto3 pandas numpy fastapi 'uvicorn[standard]'

echo "[setup] env dir /etc/markets ..."
mkdir -p /etc/markets
if [ ! -f /etc/markets/markets.env ]; then
  cp "$MARKETS_DIR/deploy/aws/env.template" /etc/markets/markets.env
  chmod 600 /etc/markets/markets.env
  echo "[setup] created /etc/markets/markets.env — fill runtime secrets before starting collectors."
else
  echo "[setup] /etc/markets/markets.env already exists — left untouched."
fi

echo "[setup] installing systemd units..."
units=(
  nymex-pull.service
  markets-ng-live.service
  markets-ng-live-watchdog.service
  markets-ng-live-watchdog.timer
  markets-desk.service
  markets-update.service
  markets-update.timer
  markets-daily.service
  markets-daily.timer
)
for unit in "${units[@]}"; do
  sed -e "s#@MARKETS_DIR@#$MARKETS_DIR#g" -e "s#@RUN_USER@#$RUN_USER#g" \
    "$MARKETS_DIR/deploy/aws/$unit" > "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now markets-update.timer
# Enable boot persistence without starting the data service against an unverified key.
systemctl enable markets-ng-live.service
systemctl enable --now markets-ng-live-watchdog.timer
systemctl enable markets-desk.service

echo "[setup] DONE. Historical services were not changed or restarted."
echo "[setup] After DATABENTO_API_KEY is present in /etc/markets/markets.env:"
echo "        sudo systemctl enable --now markets-ng-live.service markets-desk.service"
echo "        sudo journalctl -u markets-ng-live.service -f"
echo "[setup] Health: /var/lib/markets/ng_live/health.json"
echo "[setup] Desk: http://127.0.0.1:8091 (use an SSM port forward)"
echo "[setup] Raw DBN: s3://bento-568968024170-us-east-2-an/nymex/live/ng/YYYY/MM/DD/"
