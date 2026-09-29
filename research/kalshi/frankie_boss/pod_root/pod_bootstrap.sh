#!/bin/bash
# The ROOT Pod's start (SPEC-pod-day-runner.md). The Pod's entrypoint fetches this file from GitHub at the pinned commit
# (raw.githubusercontent.com/DavisAI1974/Markets/<MARKETS_SHA>/research/kalshi/frankie_boss/pod_root/pod_bootstrap.sh; the
# repository is public) and runs it; it runs again at every Pod restart and is idempotent.
#   1. the box's own worker setup, deploy/aws/box/frankie_box_worker_setup.sh at the same commit: apt (git zstd sqlite3
#      curl), the same Python 3.13.15 build the main box's venv points at, /opt/frankie-box/venv with the main box's 75
#      pins (it prints the freeze diff), /opt/frankie-box/markets at MARKETS_SHA. /opt/frankie-box is the Pod's
#      persistent volume, so a restart re-uses the venv and the checkouts (only Python itself is re-installed into the
#      container disk);
#   2. the pinned producers checkout /opt/frankie-box/producers (lineage ccode/frankie-receiver-feed-20260916 at
#      2ebb8ce8), its ten producer files checked by the agent against the sha256 pins before every job;
#   3. the agent (pod_agent.py serve) on port 8081, bearer POD_TOKEN; it runs one day's ROOT per slot (POD_SLOTS).
# Env (set when the Pod is created by pod_root/controller.py): MARKETS_SHA, POD_TOKEN, POD_SLOTS. Prints no secret.
set -eu
: "${MARKETS_SHA:?the pinned commit}"; : "${POD_TOKEN:?the agent token}"
export HOME="${HOME:-/root}" DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1
ROOT=/opt/frankie-box
mkdir -p "$ROOT/logs" "$ROOT/pod-agent"
exec > >(tee -a "$ROOT/logs/pod-bootstrap.log") 2>&1
echo "### $(date -u +%FT%TZ) pod bootstrap at $MARKETS_SHA (pod ${RUNPOD_POD_ID:-?})"
apt-get update -q >/dev/null
apt-get install -y -q git curl ca-certificates zstd sqlite3 procps util-linux >/dev/null
T=$(mktemp -d)
curl -fsSL "https://raw.githubusercontent.com/DavisAI1974/Markets/$MARKETS_SHA/deploy/aws/box/frankie_box_worker_setup.sh" -o "$T/setup.sh"
MARKETS_SHA="$MARKETS_SHA" sh "$T/setup.sh"
rm -rf "$T"
if [ ! -d "$ROOT/producers/.git" ]; then
  git clone -q --depth 1 --branch ccode/frankie-receiver-feed-20260916 https://github.com/DavisAI1974/Markets.git "$ROOT/producers"
fi
echo "producers $(git -C "$ROOT/producers" rev-parse HEAD)"
"$ROOT/venv/bin/python" - "$ROOT/pod-agent/bootstrap.json" "$MARKETS_SHA" <<'PY'
import json, os, platform, sys, time
json.dump(dict(schema='FRANKIE_POD_ROOT_BOOTSTRAP_V1', at=time.time(), markets_commit=sys.argv[2], python=platform.python_version(),
               cpus=os.cpu_count(), affinity=len(os.sched_getaffinity(0)), pod=os.environ.get('RUNPOD_POD_ID')),
          open(sys.argv[1], 'w'), sort_keys=True, indent=1)
PY
echo "### agent"
cd "$ROOT/pod-agent"
exec "$ROOT/venv/bin/python" -B "$ROOT/markets/research/kalshi/frankie_boss/pod_root/pod_agent.py" serve
