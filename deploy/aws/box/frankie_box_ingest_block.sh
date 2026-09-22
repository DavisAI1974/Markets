# The TRADING-DAY INGEST on Frankie's box (SPEC-trading-day-ingest.md; Greg 2026-09-22: "Lets rerun cyc 0", "Monday by
# itself before we do 4 days at a time", every CPU the encoders can use while the parent keeps the causal sequence). One committed script, four read-then-act actions:
#   fetch   the manifest's partitions by the presigned map (MAP_URL from frankie_box_run.yml presign=<bucket>/<key> ...),
#           each verified against the manifest's sha256 and size; present and equal = kept; different = REFUSED
#   canary  the ingest tool on the first CANARY records: the measured rate, no completion claim
#   ingest  the ingest tool to completion (the pinned conformance stack reconciles the declared counts)
#   status  what is on the box: partitions, work directories, receipts (touches no git: the current checkout is read)
# Inputs: ACTION, MANIFEST (repo-relative, default the Monday trading day), WORKERS (default 31: the parent keeps a CPU),
# CANARY (default 20000), MARKETS_SHA (the DISPATCHED COMMIT; frankie_box_run.yml sets it from GITHUB_SHA: the box checks out
# that commit, never a branch name, and refuses a HEAD that differs; the chat-9 ship review), CYCLE (00).
# Order (the chat-9 ship review): the cycle units are checked idle BEFORE the checkout moves (a running session lazy-loads
# modules from this checkout), the manifest is validated by the tool's own block_source_scope BEFORE any path is built from
# it, and every destination is pinned under the data directory. Nothing deleted, nothing overwritten, no key, no model call,
# no S3 write (publish is a separate action on Greg's word). SSM runs this under sh: POSIX only.
set -u
ROOT=/opt/frankie-box; CYCLE="${CYCLE:-00}"; ACTION="${ACTION:-status}"; WORKERS="${WORKERS:-31}"; CANARY="${CANARY:-20000}"
MARKETS_SHA="${MARKETS_SHA:-}"
MANIFEST="${MANIFEST:-research/kalshi/frankie_boss/blocks/BLOCK_20211004_SOURCE_MANIFEST.json}"
case "$MARKETS_SHA" in ""|*[!0-9a-f]*) echo "MARKETS_SHA must be the dispatched commit (frankie_box_run.yml sets it from GITHUB_SHA)"; exit 2;; esac
[ "${#MARKETS_SHA}" -eq 40 ] || { echo "MARKETS_SHA must be the full 40-hex commit"; exit 2; }
case "$MANIFEST" in research/kalshi/frankie_boss/blocks/BLOCK_*_SOURCE_MANIFEST.json) ;; *) echo "MANIFEST must be a committed blocks/BLOCK_*_SOURCE_MANIFEST.json"; exit 2;; esac
case "$MANIFEST" in *..*|research/kalshi/frankie_boss/blocks/*/*) echo "MANIFEST must be a file directly under blocks/"; exit 2;; esac
case "$WORKERS" in ""|*[!0-9]*) echo "WORKERS must be an integer"; exit 2;; esac
case "$CANARY" in ""|*[!0-9]*) echo "CANARY must be an integer"; exit 2;; esac
NCPU=$(nproc 2>/dev/null || echo 1)
[ "$WORKERS" -le "$NCPU" ] || { echo "WORKERS must be at most the box's $NCPU CPUs"; exit 2; }
[ "$CANARY" -ge 1 ] || { echo "CANARY must be at least 1"; exit 2; }
mkdir -p "$ROOT/data" "$ROOT/work" "$ROOT/receipts" "$ROOT/tmp"
PY="$ROOT/venv/bin/python"; [ -x "$PY" ] || { echo "venv not staged"; exit 2; }
units_idle() {
  for U in "frankie-cycle-$CYCLE" "frankie-heartbeat-$CYCLE" "frankie-correction-$CYCLE"; do
    if systemctl is-active --quiet "$U.service"; then echo "$U is running: the ingest waits (the box is the cycle's while its unit runs)"; return 2; fi
  done
}
checkout_markets() {   # only after units_idle: the running session's lazy imports read this checkout
  git -C "$ROOT/markets" fetch -q --depth 1 origin -- "$MARKETS_SHA" || { echo "markets fetch of $MARKETS_SHA failed"; return 2; }
  git -C "$ROOT/markets" checkout -q "$MARKETS_SHA" || { echo "markets checkout of $MARKETS_SHA failed"; return 2; }
  [ "$(git -C "$ROOT/markets" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "markets HEAD differs from the dispatched commit; refused"; return 2; }
  echo "markets HEAD $MARKETS_SHA (the dispatched commit)"
}
manifest_ok() {   # M, BLOCK, DATA from the checkout as it stands (status) or as just checked out (fetch, canary, ingest)
  M="$ROOT/markets/$MANIFEST"; [ -s "$M" ] || { echo "manifest missing at $M"; return 2; }
  BLOCK=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['block'])" "$M") || return 2
  case "$BLOCK" in ""|*[!0-9_]*) echo "bad block name in the manifest; refused"; return 2;; esac
  DATA="$ROOT/data/block_$BLOCK"
}
prepare() { units_idle || return 2; checkout_markets || return 2; manifest_ok || return 2; mkdir -p "$DATA"; }
fetch() {
  [ -n "${MAP_URL:-}" ] || { echo "MAP_URL not set (dispatch frankie_box_run.yml with presign=<bucket>/<prefix>/<member_key> for every partition)"; return 2; }
  case "$MAP_URL" in https://*.amazonaws.com/*) ;; *) echo "MAP_URL must be an https amazonaws URL"; return 2;; esac
  cd "$ROOT/tmp" || return 2
  curl -fsS --proto =https -m 60 --retry 3 -o ingest-map.json --url "$MAP_URL" || { echo "map download failed"; return 2; }
  M="$M" DATA="$DATA" ROOT="$ROOT" MARKETS_SHA="$MARKETS_SHA" "$PY" - <<'PYEOF'
import hashlib, json, os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.environ['ROOT'], 'markets'))
from research.kalshi.frankie_boss.block_source_scope import block_source_scope     # the tool's own validation, before any path is built
m = json.load(open('ingest-map.json')); manifest = json.load(open(os.environ['M'])); data = os.path.realpath(os.environ['DATA'])
scope = block_source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])   # refuses '..', a leading '/', a bad hash
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): h.update(b)
    return h.hexdigest()
def ok_url(u):
    return isinstance(u, str) and u.startswith('https://') and '.amazonaws.com/' in u.split('?', 1)[0]
receipt = dict(schema='FRANKIE_BOX_INGEST_FETCH_RECEIPT_V1', at=time.time(), block=manifest['block'], manifest_hash=manifest['manifest_hash'],
               markets_sha=os.environ['MARKETS_SHA'], files=[], refused=[])
for member in scope.members:
    dest = os.path.realpath(os.path.join(data, member.member_key))
    if not dest.startswith(data + os.sep):
        raise SystemExit(f'{member.member_key} escapes the data directory; refused')
    key = next((k for k in m if k.endswith('/' + member.member_key) or k == member.member_key), None)
    if os.path.exists(dest):
        have = sha(dest)
        if have == member.sha256 and os.path.getsize(dest) == member.size_bytes:
            receipt['files'].append(dict(member_key=member.member_key, status='present', sha256=have)); print('present', dest); continue
        receipt['refused'].append(dict(member_key=member.member_key, reason='a different file is already at the destination; not overwritten (move it aside with a receipt first)', sha256=have))
        print('REFUSED (present, different):', dest); continue
    if key is None:
        receipt['refused'].append(dict(member_key=member.member_key, reason='not in the presigned map')); print('REFUSED (not presigned):', member.member_key); continue
    if m[key].get('bytes') != member.size_bytes:
        receipt['refused'].append(dict(member_key=member.member_key, reason='bytes differ from the manifest', have=m[key].get('bytes'))); print('REFUSED (bytes):', member.member_key); continue
    if not ok_url(m[key].get('url')):
        receipt['refused'].append(dict(member_key=member.member_key, reason='the map entry is not an https amazonaws URL')); print('REFUSED (url):', member.member_key); continue
    part = dest + '.part'; t0 = time.time()
    r = subprocess.run(['curl', '-fsS', '--proto', '=https', '-L', '--retry', '5', '--retry-delay', '5', '-C', '-', '-o', part, '--url', m[key]['url']])
    if r.returncode != 0:
        receipt['refused'].append(dict(member_key=member.member_key, reason='download failed', returncode=r.returncode)); print('REFUSED (download):', member.member_key); continue
    got = sha(part)
    if os.path.getsize(part) != member.size_bytes or got != member.sha256:
        os.replace(part, part + f'.rejected-{int(time.time())}')
        receipt['refused'].append(dict(member_key=member.member_key, reason='digest differs from the manifest; the bytes are kept aside as .part.rejected-<ts>', sha256=got)); print('REFUSED (digest):', member.member_key); continue
    if os.path.exists(dest):   # something landed at the destination during the download: never overwritten
        os.replace(part, part + f'.late-{int(time.time())}')
        receipt['refused'].append(dict(member_key=member.member_key, reason='a file appeared at the destination during the download; not overwritten (the download is kept aside as .part.late-<ts>)')); print('REFUSED (late):', member.member_key); continue
    os.replace(part, dest); receipt['files'].append(dict(member_key=member.member_key, status='restored', sha256=got, seconds=round(time.time() - t0, 1)))
    print('restored', dest, member.size_bytes, f'{time.time()-t0:.0f}s')
name = os.path.join(os.environ['ROOT'], 'receipts', f'ingest-fetch-{manifest["block"]}-{int(time.time())}.json')
with open(name, 'x') as f: json.dump(receipt, f, indent=1, sort_keys=True)
print('RECEIPT', name)
raise SystemExit(0 if not receipt['refused'] else 1)
PYEOF
  code=$?; rm -f "$ROOT/tmp/ingest-map.json"; return $code
}
run_tool() {   # $1 = canary|ingest (prepare ran: units idle, the dispatched commit checked out, the manifest read)
  for member in $("$PY" -c "import json,sys; print(' '.join(s['member_key'] for s in json.load(open(sys.argv[1]))['sources']))" "$M"); do
    [ -s "$DATA/$member" ] || { echo "partition $member not on the box (ACTION=fetch first)"; return 2; }
  done
  OUT="$ROOT/work/ingest-$BLOCK-$1-$(date +%s)"     # a fresh directory per run, CREATED BY THE TOOL (it refuses an existing one; run 35680854102); it writes once, never over
  EXTRA=""; [ "$1" = canary ] && EXTRA="--canary-records $CANARY"
  echo "### $1: block $BLOCK, $WORKERS workers, manifest $MANIFEST, markets $MARKETS_SHA, out $OUT"
  ( cd "$ROOT/markets" && PYTHONPATH="$ROOT/markets" "$PY" research/kalshi/frankie_boss/operations/ingest_block_sources.py \
      --manifest "$M" --sources-dir "$DATA" --output-dir "$OUT" --session-policy cme_trading_day --workers "$WORKERS" $EXTRA ) \
    || { echo "$1 failed (exit $?); the directory $OUT is kept"; return 3; }
  for R in canary-receipt.json ingestion-receipt.json; do [ -s "$OUT/$R" ] && { echo "### $R"; cat "$OUT/$R"; }; done
  return 0     # the tool's exit decided above; a missing ingestion receipt on a canary is not a failure (run 35681037861 exited 1 on this test)
}
status() {
  echo "### markets HEAD $(git -C "$ROOT/markets" rev-parse HEAD 2>/dev/null || echo unknown) (as it stands; status moves nothing)"
  echo "### partitions under $ROOT/data"; ls -la "$ROOT"/data/block_* 2>/dev/null || echo "(none)"
  echo "### ingest work directories"; ls -d "$ROOT"/work/ingest-* 2>/dev/null || echo "(none)"
  for d in "$ROOT"/work/ingest-*/; do [ -d "$d" ] || continue; for R in canary-receipt.json ingestion-receipt.json; do [ -s "$d$R" ] && { echo "### $d$R"; "$PY" -c "import json,sys; r=json.load(open(sys.argv[1])); keys=('schema','block','trading_day','records','record_count','records_per_second','extrapolated_hours_for_total','journal_count','journal_head_hash','journal_sha256','sessions','partial_members','partial_members_ingested','completion_claimed','workers'); print(json.dumps({k: r[k] for k in keys if k in r}, sort_keys=True))" "$d$R"; }; done; done
  echo "### receipts"; ls "$ROOT"/receipts/ingest-* 2>/dev/null || echo "(none)"
  df -h / | tail -1
}
case "$ACTION" in
  fetch) prepare && fetch ;;
  canary) prepare && run_tool canary ;;
  ingest) prepare && run_tool ingest ;;
  status) manifest_ok && status ;;
  *) echo "ACTION must be fetch, canary, ingest or status"; exit 2 ;;
esac
