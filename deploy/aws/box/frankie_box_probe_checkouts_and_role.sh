# Read-only: what the checkouts on Frankie's box are, which Pythons exist, and what the instance role can read.
# Writes nothing on the box or in S3 (head/list/get-caller-identity only).
set -u
echo "### checkouts"
for d in /opt/frankie-main /opt/frankie-receiver /opt/frankie-receiver-checks /opt/frankie-profile-20260917 /opt/actions-runner/_work/Markets/Markets; do
  echo "--- $d"; [ -d "$d" ] || { echo "(absent)"; continue; }
  if [ -d "$d/.git" ]; then git -C "$d" log --oneline -1 2>&1; git -C "$d" rev-parse --abbrev-ref HEAD 2>&1; git -C "$d" remote -v 2>&1 | head -1; git -C "$d" status --porcelain --untracked-files=no 2>/dev/null | wc -l | sed 's/^/dirty_tracked_files=/'; else echo "(not a git checkout)"; fi
  ls -la "$d" | head -12; du -sh "$d" 2>/dev/null
  ls -d "$d"/research/kalshi/frankie_raw_mbo_benchmark "$d"/research/kalshi/frankie_boss "$d"/research/ng_exhaustion_mbo_v4_state_adapter_20260820.py "$d"/venv "$d"/.venv 2>/dev/null
done
echo "### pythons"; ls /opt/hostedtoolcache/Python 2>/dev/null; for p in /opt/hostedtoolcache/Python/*/x64/bin/python; do [ -x "$p" ] && "$p" --version; done; ls -d /opt/*/venv /opt/*/.venv /opt/frankie-*/bin/python 2>/dev/null
for v in /opt/frankie-main/venv /opt/frankie-receiver/venv /opt/frankie-receiver-checks/venv /opt/frankie-profile-20260917/venv; do [ -x "$v/bin/python" ] && { echo "--- $v"; "$v/bin/python" --version; "$v/bin/python" -m pip list 2>/dev/null | grep -iE "^(torch|numpy|boto3|zstandard|databento|cryptography|pandas|scipy|openai|anthropic) " ; }; done
echo "### instance role identity and S3 reach (read-only)"
python3 - <<'PY'
import boto3, botocore
try:
    print('sts:', boto3.client('sts', region_name='us-east-1').get_caller_identity()['Arn'])
except Exception as e: print('sts failed:', type(e).__name__, str(e)[:200])
checks = [
 ('bento-568968024170-us-east-2-an', 'us-east-2', 'nymex/ng_mbo_5y_v0/frankie/parallel_source_verification/cefa75692528b3a66cc89d10993ecbc8e9d420dce924876fc85cfdbfdfa7679f.tar.gz', 'frankie/'),
 ('frankie-granite42-568968024170-us-east-1', 'us-east-1', 'host-deliveries/20211003/principal-request/cycle-00/35557744815/historical-prompt.md', 'host-deliveries/20211003/'),
]
for bucket, region, key, prefix in checks:
    s3 = boto3.client('s3', region_name=region)
    try:
        h = s3.head_object(Bucket=bucket, Key=key); print('head OK', bucket, key.rsplit('/',1)[-1], h['ContentLength'], h.get('ServerSideEncryption'))
    except Exception as e: print('head FAILED', bucket, key.rsplit('/',1)[-1], type(e).__name__, getattr(e,'response',{}).get('Error',{}).get('Code'))
    try:
        r = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=5); print('list OK', bucket, prefix, r.get('KeyCount'), [o['Key'] for o in r.get('Contents', [])][:5])
    except Exception as e: print('list FAILED', bucket, prefix, type(e).__name__, getattr(e,'response',{}).get('Error',{}).get('Code'))
try:
    r = boto3.client('ssm', region_name='us-east-1').get_parameter(Name='/markets/DATABENTO_API_KEY', WithDecryption=False); print('ssm get-parameter (no decrypt) reachable: yes (value not printed)')
except Exception as e: print('ssm get-parameter:', type(e).__name__, getattr(e,'response',{}).get('Error',{}).get('Code'))
try:
    b = boto3.client('bedrock', region_name='us-east-1').list_foundation_models(byProvider='Anthropic'); print('bedrock list models OK:', len(b['modelSummaries']), 'anthropic models')
except Exception as e: print('bedrock list models:', type(e).__name__, getattr(e,'response',{}).get('Error',{}).get('Code'))
PY
echo "### outbound reach"; for u in https://github.com https://pypi.org/simple/pip/ https://download.pytorch.org/whl/cpu/ https://api.anthropic.com; do printf '%-45s ' "$u"; curl -s -m 8 -o /dev/null -w '%{http_code}\n' "$u" || echo "unreachable"; done
echo "### done (read-only)"
