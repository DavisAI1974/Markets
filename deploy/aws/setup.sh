#!/usr/bin/env bash
# deploy/aws/setup.sh — one-time (idempotent) setup of a durable box to host the Markets code + the NYMEX
# raw-ingestion pull (and, later, the daily forecast/trade lifecycle). Ubuntu/Debian assumed.
#
# Usage (as a sudo-capable user on the box):
#   git clone <the Markets repo> ~/Markets && cd ~/Markets
#   git checkout claude/kalshi-s79-kickoff-ij8t9o && git pull
#   sudo bash deploy/aws/setup.sh
#   sudo cp deploy/aws/env.template /etc/markets/markets.env && sudo chmod 600 /etc/markets/markets.env
#   sudoedit /etc/markets/markets.env      # fill DATABENTO_API_KEY (+ AWS keys only if no instance role)
#   sudo systemctl start nymex-pull.service && journalctl -u nymex-pull -f   # start + watch the year pull
#
# Re-run any time; it only adds/updates, never destroys data or the env file.
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
python3 -m pip install databento boto3 pandas

echo "[setup] env dir /etc/markets ..."
mkdir -p /etc/markets
if [ ! -f /etc/markets/markets.env ]; then
  cp "$MARKETS_DIR/deploy/aws/env.template" /etc/markets/markets.env
  chmod 600 /etc/markets/markets.env
  echo "[setup] created /etc/markets/markets.env from template — FILL IN THE SECRETS (chmod 600)."
else
  echo "[setup] /etc/markets/markets.env already exists — left untouched."
fi

echo "[setup] installing systemd units (templated with MARKETS_DIR + RUN_USER)..."
for unit in nymex-pull.service markets-update.service markets-update.timer markets-daily.service markets-daily.timer; do
  sed -e "s#@MARKETS_DIR@#$MARKETS_DIR#g" -e "s#@RUN_USER@#$RUN_USER#g" \
      "$MARKETS_DIR/deploy/aws/$unit" > "/etc/systemd/system/$unit"
done
systemctl daemon-reload
# keep the code fresh daily (pull --rebase the trunk); pull runs on demand; daily lifecycle stays DISABLED
# until the forecaster emit + scoring script exist (a timer into an empty pipeline is premature).
systemctl enable --now markets-update.timer
echo "[setup] DONE. Next: fill /etc/markets/markets.env, then 'systemctl start nymex-pull.service'."
echo "[setup] The daily lifecycle timer is intentionally DISABLED — enable it later with:"
echo "        sudo systemctl enable --now markets-daily.timer   # ONLY once the daily scorer exists"
