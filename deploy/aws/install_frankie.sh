#!/usr/bin/env bash
set -euo pipefail

MARKETS_DIR="${1:-/opt/markets}"
RUN_USER="${2:-ubuntu}"
SERVICE_SRC="$MARKETS_DIR/deploy/aws/markets-frankie.service"
SERVICE_DST="/etc/systemd/system/markets-frankie.service"
STATE_DIR="/var/lib/markets/frankie"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0 [markets-dir] [run-user]" >&2
  exit 2
fi
if [[ ! -f "$MARKETS_DIR/research/kalshi/agent_frankie.py" ]]; then
  echo "agent_frankie.py not found under $MARKETS_DIR" >&2
  exit 2
fi
if [[ ! -f "$SERVICE_SRC" ]]; then
  echo "service template not found: $SERVICE_SRC" >&2
  exit 2
fi
if ! id "$RUN_USER" >/dev/null 2>&1; then
  echo "run user does not exist: $RUN_USER" >&2
  exit 2
fi

python3 -m pip install --upgrade -r "$MARKETS_DIR/deploy/aws/requirements-frankie.txt"
install -d -m 0700 -o "$RUN_USER" -g "$RUN_USER" \
  "$STATE_DIR/evidence" "$STATE_DIR/proposals/pending"
install -d -m 0750 /etc/markets

sed \
  -e "s|@MARKETS_DIR@|$MARKETS_DIR|g" \
  -e "s|@RUN_USER@|$RUN_USER|g" \
  "$SERVICE_SRC" > "$SERVICE_DST"
chmod 0644 "$SERVICE_DST"

if [[ ! -f /etc/markets/frankie.env ]]; then
  cat > /etc/markets/frankie.env <<'EOF'
# Frankie starts in deterministic observation mode until the private Claude paper links
# are exported into research/kalshi/frankie_paper_manifest.json and reviewed.
FRANKIE_DETERMINISTIC_ONLY=1
FRANKIE_EVIDENCE_ROOT=/var/lib/markets/frankie/evidence
FRANKIE_SQS_REGION=us-east-2
FRANKIE_BEDROCK_REGION=us-east-1
# FRANKIE_QUEUE_URL=https://sqs.us-east-2.amazonaws.com/ACCOUNT/frankie-events
# FRANKIE_EVIDENCE_BUCKET=bento-568968024170-us-east-2-an
# FRANKIE_EVIDENCE_PREFIX=frankie/evidence
# FRANKIE_PRIMARY_BACKEND=bedrock
# FRANKIE_CRITIC_BACKEND=openai
# FRANKIE_BEDROCK_MODEL=<inference-profile-or-model-id>
# FRANKIE_OPENAI_MODEL=<approved-model-id>
EOF
  chmod 0600 /etc/markets/frankie.env
fi

systemctl daemon-reload

echo "Frankie installed but NOT enabled or started."
echo "1. Configure /etc/markets/frankie.env and the SQS queue/DLQ."
echo "2. Run: sudo -u $RUN_USER bash -lc 'cd $MARKETS_DIR/research/kalshi && python3 agent_frankie.py health && python3 agent_frankie.py selftest'"
echo "3. Then: systemctl enable --now markets-frankie.service"
