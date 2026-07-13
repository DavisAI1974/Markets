#!/usr/bin/env bash
# deploy/aws/daily_lifecycle.sh — the DAILY forecast/trade lifecycle entrypoint (Greg S90: "how do we
# remember to do this daily?" -> a durable timer, not memory). Run by markets-daily.timer, which is
# DISABLED by default. This is a STUB until the pieces exist; enabling the timer before then is a no-op.
#
# What it WILL run once built (see the FORECAST WORKFLOW block in KALSHI_TRADING.md +
# WEATHER_FORECAST_INTERFACE_S90.md):
#   1. ~5PM local: score TOMORROW's KXHIGH ladders from the forecaster emit (per-cell (value,sigma) ->
#      bucket probs via the kalshi_score/weather_regime_score bridge) + load the NYMEX path forecast.
#   2. AM recalc with overnight state (curve, news, weather, storage, regime).
#   3. Intraday: re-check RT vs the loaded forecast; re-forecast or exit.
# Until the scoring script lands this exits 0 (harmless no-op) so a premature enable does nothing bad.
set -euo pipefail
MARKETS_DIR="${MARKETS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$MARKETS_DIR"

SCORER="research/kalshi/weather_regime_score.py"     # the per-cell scorer the lifecycle will drive
if [ ! -f "$SCORER" ]; then
  echo "[daily] scorer $SCORER absent — nothing to run yet (stub no-op)"; exit 0
fi
# TODO(S90+): wire the real lifecycle here once the forecaster emit + per-cell scoring script exist.
echo "[daily] lifecycle not yet wired — see deploy/aws/daily_lifecycle.sh header + FORECAST WORKFLOW TODO"
exit 0
