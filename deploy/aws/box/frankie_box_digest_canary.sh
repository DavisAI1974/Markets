# Digest token canary (Greg, 2026-09-28: "measure a slice, extrapolate"; the standing 1-2 minute canary rule).
# Read-only on Frankie's files; no model call, bills nothing (serverless is retired: Granite runs on the A100 Pods).
# Measures tokens per byte with the pinned Granite tokenizer on SLICES 4 MB slices spaced evenly from start to end,
# reports each slice individually, and extrapolates to the whole digest and to PART_TOKENS reading parts.
# Inputs: DIGEST (default: the Monday ROOT digest), SLICES (1..32, default 3), PART_TOKENS (default 87000).
# Writes only /opt/frankie-box/work/digest-canary/<UTC stamp>/.
set -eu
export DIGEST="${DIGEST:-/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work/derivation-digest-full.md}"
export PART_TOKENS="${PART_TOKENS:-87000}" SLICES="${SLICES:-3}"
case "$SLICES" in ''|*[!0-9]*) echo "SLICES must be 1..32"; exit 2;; esac
[ "$SLICES" -ge 1 ] && [ "$SLICES" -le 32 ] || { echo "SLICES must be 1..32"; exit 2; }
case "$PART_TOKENS" in ''|*[!0-9]*) echo "PART_TOKENS must be a positive integer"; exit 2;; esac
exec nice -n 5 /opt/frankie-box/venv/bin/python -B - <<'PY'
import hashlib, json, os, time
from pathlib import Path
from tokenizers import Tokenizer

DIGEST, PART, NSLICES = Path(os.environ['DIGEST']), int(os.environ['PART_TOKENS']), int(os.environ['SLICES'])
raw = Path('/opt/frankie-box/tmp/granite_tokenizer.json').read_bytes()
if not hashlib.sha256(raw).hexdigest().startswith('883975314d587437'):
    raise SystemExit('pinned Granite tokenizer differs')
tok = Tokenizer.from_str(raw.decode())
size = DIGEST.stat().st_size
if size == 0 or PART <= 0:
    raise SystemExit('empty digest or PART_TOKENS 0')
with DIGEST.open('rb') as handle:
    digest_sha = hashlib.file_digest(handle, 'sha256').hexdigest()
OUT = Path('/opt/frankie-box/work/digest-canary') / time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
OUT.mkdir(parents=True)
report = dict(schema='FRANKIE_DIGEST_CANARY_V2', digest=str(DIGEST), digest_bytes=size, digest_sha256=digest_sha,
              part_tokens=PART, slices=[])
print('digest', DIGEST, size, 'bytes sha256', digest_sha, flush=True)
SLICE = min(4 * 1024 * 1024, size)
span = size - SLICE
offsets = sorted({0} if NSLICES == 1 else {span * i // (NSLICES - 1) for i in range(NSLICES)})
with DIGEST.open('rb') as handle:
    for index, offset in enumerate(offsets):
        handle.seek(offset)
        text = handle.read(SLICE).decode('utf-8', errors='replace')
        t0 = time.time()
        n = len(tok.encode(text, add_special_tokens=False).ids)
        report['slices'].append(dict(label='slice-%d' % index, offset=offset, bytes=SLICE, tokens=n,
                                     tokens_per_byte=round(n / SLICE, 4), encode_seconds=round(time.time() - t0, 2)))
        print('slice', report['slices'][-1], flush=True)
tpb = sum(s['tokens'] for s in report['slices']) / sum(s['bytes'] for s in report['slices'])
report['tokens_per_byte'] = round(tpb, 4)
report['digest_tokens_estimate'] = int(size * tpb)
report['parts_estimate'] = -(-int(size * tpb) // PART)
(OUT / 'canary.json').write_text(json.dumps(report, indent=1, sort_keys=True))
print(json.dumps(report, sort_keys=True))
PY
