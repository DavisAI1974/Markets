#!/bin/bash
# CLM sidecar Pod bootstrap (image vllm/vllm-openai). Everything arrives by presigned URL in the environment:
# LEARN_URL, DATASET_URL (GET); PUT_REPORT, PUT_SUMMARY, PUT_PREDICTIONS, PUT_RAW, PUT_LOG, PUT_STATUS (PUT).
# Ends by uploading status.json (done or failed) and idling; the launcher deletes the Pod.
set -u
LOG=/tmp/sidecar.log
exec > >(tee -a "$LOG") 2>&1
echo "bootstrap start $(date -u +%FT%TZ)"
put() { python3 - "$1" "$2" <<'PY'
import sys, urllib.request
url, path = sys.argv[1], sys.argv[2]
data = open(path, 'rb').read()
req = urllib.request.Request(url, data=data, method='PUT')
with urllib.request.urlopen(req, timeout=300) as r:
    print('uploaded', path, r.status)
PY
}
finish() {
  status=$1
  printf '{"status": "%s", "at": "%s", "vllm": "%s"}\n' "$status" "$(date -u +%FT%TZ)" \
    "$(python3 -c 'import vllm; print(vllm.__version__)' 2>/dev/null)" > /tmp/status.json
  for pair in "PUT_REPORT:/tmp/out/report.md" "PUT_SUMMARY:/tmp/out/summary.json" \
              "PUT_PREDICTIONS:/tmp/out/predictions.jsonl.gz" "PUT_RAW:/tmp/out/zero_shot_raw_examples.json"; do
    var=${pair%%:*}; file=${pair#*:}
    [ -f "$file" ] && put "${!var}" "$file" || echo "missing $file"
  done
  put "$PUT_LOG" "$LOG" || true
  put "$PUT_STATUS" /tmp/status.json || true
  echo "finished: $status; idling until the launcher deletes the Pod"
  sleep infinity
}
# Checkpoints (Greg, 2026-09-28: "more frequent scheduled outputs ... every 30 min", not only at the end): every
# CHECKPOINT_MINUTES the log, a progress marker and whatever outputs exist so far go up to the same S3 keys (each later
# upload replaces the earlier one; the final finish() upload is the last word).
STAGE=download
checkpoint() {
  printf '{"stage": "%s", "at": "%s", "started": "%s", "outputs": "%s"}\n' "$STAGE" "$(date -u +%FT%TZ)" "$STARTED" \
    "$(ls /tmp/out 2>/dev/null | tr '\n' ' ')" > /tmp/progress.json
  put "$PUT_PROGRESS" /tmp/progress.json || true
  put "$PUT_LOG" "$LOG" || true
  for pair in "PUT_REPORT:/tmp/out/report.md" "PUT_SUMMARY:/tmp/out/summary.json"; do
    var=${pair%%:*}; file=${pair#*:}
    [ -f "$file" ] && put "${!var}" "$file" || true
  done
}
STARTED=$(date -u +%FT%TZ)
( while true; do sleep $(( ${CHECKPOINT_MINUTES:-30} * 60 )); STAGE=$(cat /tmp/stage 2>/dev/null || echo unknown); checkpoint; done ) &
stage() { STAGE=$1; echo "$1" > /tmp/stage; echo "STAGE $1 $(date -u +%FT%TZ)"; checkpoint; }
stage download
python3 - <<'PY' || finish failed-download
import os, urllib.request
urllib.request.urlretrieve(os.environ['LEARN_URL'], '/tmp/learn.py')
urllib.request.urlretrieve(os.environ['DATASET_URL'], '/tmp/dataset.jsonl.gz')
print('downloaded learn.py and dataset')
PY
stage install
pip install --no-cache-dir contrastive-lm numpy || echo "contrastive-lm install failed; head-only run"
stage encoder
vllm serve Qwen/Qwen3-8B --served-model-name qwen3-8b --runner pooling --port 8090 --max-model-len 8192 \
  > /tmp/vllm.log 2>&1 &
for i in $(seq 1 180); do
  python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/v1/models', timeout=5)" 2>/dev/null && break
  sleep 10
done
python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/v1/models', timeout=5)" || { tail -50 /tmp/vllm.log; finish failed-encoder; }
echo "encoder up $(date -u +%FT%TZ)"
if command -v clm-serve >/dev/null; then
  clm-serve --help 2>&1 | head -30
  clm-serve > /tmp/clm.log 2>&1 &
  for i in $(seq 1 60); do
    python3 -c "import socket; socket.create_connection(('127.0.0.1', 8700), 3)" 2>/dev/null && break
    sleep 5
  done
  tail -20 /tmp/clm.log
fi
stage learn
python3 /tmp/learn.py --dataset /tmp/dataset.jsonl.gz --out /tmp/out --stamp "${STAMP:-}" && finish done || finish failed-learn
