# CLM sidecar (Jev): upload the extract's dataset through a presigned PUT the runner signed (the box role writes
# nothing in S3; measured 2026-09-28, both host-delivery prefixes refused). Dispatch with
#   presign="put:frankie-granite42-568968024170-us-east-1/clm-sidecar/<STAMP>/dataset.jsonl.gz"  variables="STAMP=<STAMP>"
# Reads only /opt/frankie-box/work/clm-sidecar/<STAMP>/; prints the dataset's size and sha256 and the S3 key.
set -eu
: "${STAMP:?extract stamp required}"; : "${MAP_URL:?presigned map required (presign input)}"
case "$STAMP" in *[!A-Za-z0-9_.-]*|'') echo "invalid STAMP" >&2; exit 2;; esac
exec /usr/bin/python3 -B - <<'PY'
import hashlib, json, os, urllib.request
from pathlib import Path
stamp = os.environ['STAMP']
path = Path('/opt/frankie-box/work/clm-sidecar') / stamp / 'dataset.jsonl.gz'
data = path.read_bytes()
digest = hashlib.sha256(data).hexdigest()
manifest = json.loads((path.parent / 'manifest.json').read_text())
if manifest.get('sha256') != digest:
    raise SystemExit('dataset differs from its manifest')
slots = {k: v for k, v in json.loads(urllib.request.urlopen(os.environ['MAP_URL'], timeout=60).read()).items()
         if k.startswith('put:')}
key = 'clm-sidecar/%s/dataset.jsonl.gz' % stamp
slot = slots.get('put:' + key)
if slot is None:
    raise SystemExit('no upload slot for ' + key)
request = urllib.request.Request(slot['url'], data=data, method='PUT')
with urllib.request.urlopen(request, timeout=300) as response:
    status = response.status
print(json.dumps(dict(schema='CLM_SIDECAR_UPLOAD_V1', stamp=stamp, bucket=slot['bucket'], key=key, bytes=len(data),
                      sha256=digest, http=status, uploaded=status == 200), sort_keys=True))
PY
