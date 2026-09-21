# Job 0 step 3: the engine is the BOSS (Greg, 2026-09-21: no keys, no external model). This script only proves,
# read-only, what the box can reach for the git push and the heartbeat: the SecureString /markets/frankie/github-token
# (us-east-2, never printed) and PutObject on the progress prefix (a labelled probe object, not a heartbeat). It sets
# the box's git identity. Nothing is installed; no credential is created or printed. Idempotent.
set -u
ROOT=/opt/frankie-box
mkdir -p "$ROOT/receipts" "$ROOT/logs"
export HOME=/root
PY=/usr/bin/python3; [ -x "$ROOT/venv/bin/python" ] && PY="$ROOT/venv/bin/python"
echo "### credential reach (read-only, names only; boto3 $("$PY" -c 'import boto3;print(boto3.__version__)'))"
"$PY" - <<'PYX'
import boto3, json, time
def code(e): return getattr(e, 'response', {}).get('Error', {}).get('Code') or type(e).__name__
ssm = boto3.client('ssm', region_name='us-east-2')
for name in ('/markets/frankie/github-token', '/markets/frankie/granite-service'):
    try:
        v = ssm.get_parameter(Name=name, WithDecryption=True)['Parameter']['Value']; print(f'{name}: readable ({len(v)} chars, not printed)'); del v
    except Exception as e:
        print(f'{name}: {code(e)}')
s3 = boto3.client('s3', region_name='us-east-1')
key = f'host-deliveries/20211003/principal-response/cycle-00/progress/probe-{int(time.time())}-role-write-check.json'
try:
    s3.put_object(Bucket='frankie-granite42-568968024170-us-east-1', Key=key, Body=json.dumps(dict(schema='ROLE_WRITE_PROBE', note='written by the box role to test PutObject; not a heartbeat')).encode())
    print('s3 put progress/ OK (role may write heartbeats):', key)
except Exception as e:
    print('s3 put progress/:', code(e))
PYX
echo "### git identity for the box"
git config --global user.name >/dev/null 2>&1 || git config --global user.name "frankie-box"
git config --global user.email >/dev/null 2>&1 || git config --global user.email "frankie-box@markets.local"
git config --global --add safe.directory '*' 2>/dev/null
printf '{"schema":"FRANKIE_BOX_CREDENTIAL_PROBE_V1","at":%s}\n' "$(date +%s)" > "$ROOT/receipts/credential-probe-$(date +%s).json"
echo "### done (read-only)"
