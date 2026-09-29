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
# A step that fails no longer ends the container silently (2026-09-29: four Pods ran two hours with the agent port
# answering 404 and no way to read why). On any error the Pod serves its failure on the agent's port instead: HTTP 503,
# the same bearer token, the failing step and the last 200 lines of this log (no secret is ever printed here).
STEP=start
failed() {
  code=$?
  echo "### BOOTSTRAP FAILED at step '$STEP' (exit $code)"
  command -v python3 >/dev/null 2>&1 || { apt-get install -y -q python3 >/dev/null 2>&1 || true; }
  exec python3 - "$ROOT/logs/pod-bootstrap.log" "$STEP" "$code" <<'PY'
import http.server, json, os, sys
log, step, code = sys.argv[1], sys.argv[2], sys.argv[3]
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Authorization') != 'Bearer ' + os.environ.get('POD_TOKEN', ''):
            self.send_response(401); self.end_headers(); return
        try:
            tail = open(log, errors='replace').read().splitlines()[-200:]
        except OSError as e:
            tail = ['log unreadable: %s' % e]
        body = json.dumps(dict(schema='FRANKIE_POD_BOOTSTRAP_FAILED_V1', bootstrap_failed=True, step=step,
                               exit_code=int(code), pod=os.environ.get('RUNPOD_POD_ID'), log_tail=tail)).encode()
        self.send_response(503); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a):
        pass
http.server.HTTPServer(('0.0.0.0', int(os.environ.get('POD_PORT') or 8081)), Handler).serve_forever()
PY
}
trap failed ERR
set -E
STEP=apt
apt-get update -q >/dev/null
# python3: the stock ubuntu:24.04 image has none, and the worker setup reads the python-versions manifest with it
# before the pinned 3.13.15 exists (the cause of the 2026-09-29 Pods never starting their agent)
apt-get install -y -q git curl ca-certificates zstd sqlite3 procps util-linux python3 >/dev/null
STEP=worker-setup
T=$(mktemp -d)
curl -fsSL "https://raw.githubusercontent.com/DavisAI1974/Markets/$MARKETS_SHA/deploy/aws/box/frankie_box_worker_setup.sh" -o "$T/setup.sh"
MARKETS_SHA="$MARKETS_SHA" sh "$T/setup.sh"
rm -rf "$T"
STEP=producers
if [ ! -d "$ROOT/producers/.git" ]; then
  git clone -q --depth 1 --branch ccode/frankie-receiver-feed-20260916 https://github.com/DavisAI1974/Markets.git "$ROOT/producers"
fi
echo "producers $(git -C "$ROOT/producers" rev-parse HEAD)"
STEP=bootstrap-receipt
"$ROOT/venv/bin/python" - "$ROOT/pod-agent/bootstrap.json" "$MARKETS_SHA" <<'PY'
import json, os, platform, sys, time
json.dump(dict(schema='FRANKIE_POD_ROOT_BOOTSTRAP_V1', at=time.time(), markets_commit=sys.argv[2], python=platform.python_version(),
               cpus=os.cpu_count(), affinity=len(os.sched_getaffinity(0)), pod=os.environ.get('RUNPOD_POD_ID')),
          open(sys.argv[1], 'w'), sort_keys=True, indent=1)
PY
echo "### agent"
STEP=agent
trap - ERR
cd "$ROOT/pod-agent"
exec "$ROOT/venv/bin/python" -B "$ROOT/markets/research/kalshi/frankie_boss/pod_root/pod_agent.py" serve
