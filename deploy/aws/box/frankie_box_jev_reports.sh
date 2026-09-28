# Read Jev's sit-in outputs (Greg, 2026-09-28: "what is going on with jev"). READ-ONLY: the runner presigns a GET for every
# object under the stamp (dispatch with presign="getprefix:frankie-granite42-568968024170-us-east-1/clm-sidecar/<STAMP>/"
# and PREFIX=<optional sub-prefix, e.g. sit-in/ or out/>); this prints each object whole, in key order (.gz inflated;
# the feed bundles the relay wrote are listed by name and size only unless FEED=1). The box writes nothing.
set -eu
: "${MAP_URL:?presigned map required (presign getprefix:...)}"
export MAP_URL PREFIX="${PREFIX:-}" FEED="${FEED:-0}"
exec /usr/bin/python3 -B - <<'PY'
import gzip, json, os, urllib.request
entries = json.loads(urllib.request.urlopen(os.environ['MAP_URL'], timeout=60).read())
keys = sorted(k for k in entries if not k.startswith('put:') and os.environ['PREFIX'] in k)
print('%d object(s)' % len(keys))
for key in keys:
    size = entries[key].get('bytes')
    if '/feed/' in key and os.environ['FEED'] != '1':
        print('--- %s (%s bytes; feed bundle, not printed)' % (key, size))
        continue
    data = urllib.request.urlopen(entries[key]['url'], timeout=120).read()
    if key.endswith('.gz'):
        data = gzip.decompress(data)
    print('\n===== %s (%s bytes) =====' % (key, size))
    print(data.decode('utf-8', errors='replace'))
PY
