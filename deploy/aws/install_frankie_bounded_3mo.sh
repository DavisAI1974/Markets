#!/usr/bin/env bash
set -euo pipefail

MARKETS_DIR="${1:-/opt/markets}"
RUN_USER="${2:-ubuntu}"
STATE_DIR="/var/lib/markets/frankie/bounded-3mo"
UNIT="markets-frankie-bounded-3mo.service"
UNIT_DIR="/etc/systemd/system"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo $0 [markets-dir] [run-user]" >&2
  exit 2
fi
if ! id "$RUN_USER" >/dev/null 2>&1; then
  echo "run user does not exist: $RUN_USER" >&2
  exit 2
fi
if [[ ! -f "$MARKETS_DIR/research/kalshi/frankie_bounded_3mo_parallel.py" ]]; then
  echo "bounded Frankie runner not found under $MARKETS_DIR" >&2
  exit 2
fi
if [[ ! -f "$MARKETS_DIR/deploy/aws/$UNIT" ]]; then
  echo "bounded Frankie unit template missing: $MARKETS_DIR/deploy/aws/$UNIT" >&2
  exit 2
fi
if [[ ! -f /etc/markets/frankie.env ]]; then
  echo "/etc/markets/frankie.env is missing; install/configure Frankie first" >&2
  exit 2
fi

install -d -m 0700 -o "$RUN_USER" -g "$RUN_USER" "$STATE_DIR"
sed \
  -e "s|@MARKETS_DIR@|$MARKETS_DIR|g" \
  -e "s|@RUN_USER@|$RUN_USER|g" \
  "$MARKETS_DIR/deploy/aws/$UNIT" > "$UNIT_DIR/$UNIT"
chmod 0644 "$UNIT_DIR/$UNIT"
systemctl daemon-reload

echo "Bounded Sep-Nov 2021 Frankie batch unit installed but NOT started."
echo "It is a static one-shot unit and cannot be enabled for boot."
echo "The run itself will fail closed unless four effective CPUs, the CPU canary,"
echo "runtime/input pins, hybrid mode, queue exclusivity, and the normal Frankie service checks pass."
