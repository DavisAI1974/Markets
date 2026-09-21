# Write (or show) the box's serverless READING lane configuration: /opt/frankie-box/serverless.json. The session
# (frankie_box_boss_session.py) fans the reading parts out over the RunPod serverless endpoint named here when this file
# exists and the SecureString /markets/frankie/runpod-serverless (us-east-2, the RunPod API key, read into memory only)
# is readable; the merges and the writing stay on the retained Pod. Inputs: ENDPOINT_ID (required to write), WORKERS
# (default 16), GPU (label only), ACTION (write | show | remove | key | reading; default show); reading takes TENSOR_MODE (values | identity). Never prints a key. The running session
# picks the file up at its next reading stage (an ACTION=restart_session on frankie_box_session.sh applies it now).
set -u
ROOT=/opt/frankie-box; F="$ROOT/serverless.json"; ACTION="${ACTION:-show}"
case "$ACTION" in
  show) [ -s "$F" ] && { echo "### $F"; cat "$F"; } || echo "no serverless configuration on the box (reading runs on the retained Pod)";;
  remove) [ -s "$F" ] && { mv "$F" "$ROOT/receipts/serverless-removed-$(date +%s).json"; echo "moved aside (nothing deleted)"; } || echo "nothing to remove";;
  write)
    ENDPOINT_ID="${ENDPOINT_ID:-}"; WORKERS="${WORKERS:-16}"; GPU="${GPU:-}"
    [[ "$ENDPOINT_ID" =~ ^[a-z0-9]{6,40}$ ]] || { echo "ENDPOINT_ID must be the RunPod endpoint id"; exit 2; }
    [[ "$WORKERS" =~ ^[0-9]{1,3}$ ]] && [ "$WORKERS" -ge 1 ] || { echo "WORKERS must be 1..999"; exit 2; }
    printf '{"schema":"FRANKIE_BOX_SERVERLESS_READING_V1","endpoint_id":"%s","workers":%s,"gpu":"%s","written_at":%s}\n' "$ENDPOINT_ID" "$WORKERS" "$GPU" "$(date +%s)" > "$F"
    echo "### $F"; cat "$F"
    "$ROOT/venv/bin/python" - <<'PY'
import boto3
def code(e): return getattr(e, 'response', {}).get('Error', {}).get('Code') or type(e).__name__
try:
    boto3.client('ssm', region_name='us-east-2').get_parameter(Name='/markets/frankie/runpod-serverless', WithDecryption=True); print('/markets/frankie/runpod-serverless readable (not printed)')
except Exception as e: print('/markets/frankie/runpod-serverless', code(e), '- the session will refuse the serverless lane until it is readable')
PY
    ;;
  key)
    # Read-only: can the box role read the SecureString the session needs (never printed)?
    "$ROOT/venv/bin/python" - <<'PY'
import boto3
def code(e): return getattr(e, 'response', {}).get('Error', {}).get('Code') or type(e).__name__
try:
    v = boto3.client('ssm', region_name='us-east-2').get_parameter(Name='/markets/frankie/runpod-serverless', WithDecryption=True)['Parameter']
    print('KEY_PROBE {"parameter":"/markets/frankie/runpod-serverless","readable":true,"version":%d,"length":%d,"prefix":"%s"}' % (v['Version'], len(v['Value']), v['Value'][:4]))
except Exception as e: print('KEY_PROBE {"parameter":"/markets/frankie/runpod-serverless","readable":false,"error":"%s"}' % code(e))
PY
    ;;
  reading)
    # The lossless reading render's tensor mode (frankie_box_reading_render.py): values = every decoder weight as an exact
    # decimal (all data visible, more tokens); identity = per-tensor name/dtype/shape/sha256/statistics with the bytes kept
    # in the package by digest (fewer tokens). Greg's call; default values.
    TENSOR_MODE="${TENSOR_MODE:-identity}"; case "$TENSOR_MODE" in values|identity) ;; *) echo "TENSOR_MODE must be values or identity"; exit 2;; esac
    printf '{"schema":"FRANKIE_BOX_READING_CONFIG_V1","tensor_mode":"%s","written_at":%s}\n' "$TENSOR_MODE" "$(date +%s)" > "$ROOT/reading.json"
    echo "### $ROOT/reading.json"; cat "$ROOT/reading.json" ;;
  *) echo "ACTION must be show, write, remove, key or reading"; exit 2;;
esac
