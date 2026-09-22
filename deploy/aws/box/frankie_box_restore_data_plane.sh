# Job 0 step 1+2 (data): restore the cycle-0 data plane and the exported request on Frankie's box.
# Inputs: MAP_URL (a presigned GET to a {key: {bucket, bytes, url}} JSON signed by frankie_box_run.yml; every url
# is a short-lived presigned GET). The box's instance role reads nothing in S3 (probe 35577004016), so this is the
# only route. Every file lands under /opt/frankie-box/, is verified against the sha256 pinned BELOW (from git:
# RESTORATION_MANIFEST.json and ROOT_CYCLE_00_TASK_20260920.md), and a receipt is written. Idempotent: a file
# already present with the right digest is kept. Nothing on the box is deleted or overwritten: a DIFFERENT file at a
# pinned destination (a request restored under an earlier pin) is REFUSED until the operator moves it aside with a receipt.
set -u
[ -n "${MAP_URL:-}" ] || { echo "MAP_URL not set (dispatch frankie_box_run.yml with presign keys)"; exit 2; }
ROOT=/opt/frankie-box
mkdir -p "$ROOT/data" "$ROOT/request" "$ROOT/receipts" "$ROOT/tmp"
cd "$ROOT/tmp" || exit 2
curl -fsS -m 60 --retry 3 -o map.json "$MAP_URL" || { echo "map download failed"; exit 2; }
export ROOT
python3 - <<'PY'
import hashlib, json, os, subprocess, sys, time
root = os.environ['ROOT']
m = json.load(open('map.json'))
# key suffix -> (destination under ROOT, expected bytes, expected sha256); pinned in git, not read from the map
PINNED = {
 'FB/sunday-launch-20260915/restored-journal/result/journal.compact.sqlite':
   ('data/journal.compact.sqlite', 569667584, '19603159548b1e443a3565f8c999543981c43c23c80fd511c11e760f633b260f'),
 'FB/source-execution-20260915/actual-first-cutoff-capacity/prefix.sqlite':
   ('data/prefix-00.sqlite', 463036416, '722512df404c89783e49b577b163c5917764171aa19237e142c52b859f196883'),
 'FB/actual-prefixes/prefix-01.sqlite':
   ('data/prefix-01.sqlite', 50348032, '6873366e98438e8122c91f62b2a8c8091115863a20009b1696608b7e1560d416'),
 'principal-request/cycle-00/35557744815/session-request.json':
   ('request/session-request.json', 14915624, '1b777cf28c34415c4387119b1a42aed7dbc1f5e7b1799fdc0ed2cabd755624be'),
 'principal-request/cycle-00/35557744815/prompt.md':
   ('request/prompt.md', 28310877, '2403f47f0bdbe04e429aaff15859df6919c4a5e4434e8b0edf646e11c3bb24ee'),
 'principal-request/cycle-00/35557744815/historical-prompt.md':
   ('request/historical-prompt.md', 158950, '8ff55bb2a5bb6a0e3549b0260d38b0e9237b26a020ab5d8fad8372e77a6d7705'),
}
def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()
receipt = dict(schema='FRANKIE_BOX_RESTORE_RECEIPT_V1', at=time.time(), root=root, files=[], refused=[])
for key, entry in m.items():
    suffix = next((s for s in PINNED if key.endswith(s)), None)
    if suffix is None:
        receipt['refused'].append(dict(key=key, reason='not pinned in this script')); print('REFUSED (not pinned):', key); continue
    dest_rel, want_bytes, want_sha = PINNED[suffix]
    dest = os.path.join(root, dest_rel)
    if entry.get('bytes') != want_bytes:
        receipt['refused'].append(dict(key=key, reason='bytes differ from pin', have=entry.get('bytes'), want=want_bytes)); print('REFUSED (bytes):', key); continue
    if os.path.exists(dest) and os.path.getsize(dest) == want_bytes and sha(dest) == want_sha:
        receipt['files'].append(dict(key=key, path=dest, bytes=want_bytes, sha256=want_sha, status='already_present')); print('present ', dest); continue
    if os.path.exists(dest):
        have = sha(dest)
        receipt['refused'].append(dict(key=key, reason='a different file is already at the destination; not overwritten (move it aside with a receipt first)', path=dest, bytes=os.path.getsize(dest), sha256=have, want_sha256=want_sha))
        print('REFUSED (present, different):', dest, have[:16], 'want', want_sha[:16]); continue
    part = dest + '.part'
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    t0 = time.time()
    r = subprocess.run(['curl', '-fsS', '-L', '--retry', '5', '--retry-delay', '5', '-C', '-', '-o', part, entry['url']])
    if r.returncode != 0:
        receipt['refused'].append(dict(key=key, reason='download failed', returncode=r.returncode)); print('FAILED download', key); continue
    got = sha(part); size = os.path.getsize(part)
    if size != want_bytes or got != want_sha:
        receipt['refused'].append(dict(key=key, reason='digest differs from pin', bytes=size, sha256=got)); print('REFUSED (digest):', key, size, got); os.replace(part, dest + f'.rejected-{int(time.time())}'); continue
    os.replace(part, dest)
    receipt['files'].append(dict(key=key, path=dest, bytes=size, sha256=got, status='restored', seconds=round(time.time() - t0, 1)))
    print('restored', dest, size, f'{time.time()-t0:.1f}s')
missing = [s for s in PINNED if not any(f['key'].endswith(s) for f in receipt['files'])]
receipt['missing'] = missing
name = os.path.join(root, 'receipts', f'restore-{int(receipt["at"])}.json')
with open(name, 'w') as f: json.dump(receipt, f, indent=1, sort_keys=True)
print('RECEIPT', name); print(json.dumps({k: v for k, v in receipt.items() if k != 'files'}, sort_keys=True))
for f in receipt['files']: print(' ', f['status'], f['path'], f['bytes'], f['sha256'][:16])
sys.exit(0 if not receipt['refused'] and not missing else 1)
PY
code=$?
rm -f "$ROOT/tmp/map.json"
df -h / | tail -1
exit $code
