# The TRADING-DAY INGEST on Frankie's box (SPEC-trading-day-ingest.md; Greg 2026-09-22: "Lets rerun cyc 0", "Monday by
# itself before we do 4 days at a time", every CPU the encoders can use while the parent keeps the causal sequence). One committed script, four read-then-act actions:
#   fetch   the manifest's partitions by the presigned map (MAP_URL from frankie_box_run.yml presign=<bucket>/<key> ...),
#           each verified against the manifest's sha256 and size; present and equal = kept; different = REFUSED
#   canary  the ingest tool on the first CANARY records: the measured rate, no completion claim
#   ingest  the ingest tool to completion (the pinned conformance stack reconciles the declared counts)
#   status  what is on the box: partitions, work directories, receipts
# Inputs: ACTION, MANIFEST (repo-relative, default the Monday trading day), WORKERS (default 32), CANARY (default 20000),
# MARKETS_REF (this branch), CYCLE (00). Nothing deleted, nothing overwritten, no key, no model call, no S3 write
# (publish is a separate action on Greg's word).
set -u
ROOT=/opt/frankie-box; CYCLE="${CYCLE:-00}"; ACTION="${ACTION:-status}"; WORKERS="${WORKERS:-31}"; CANARY="${CANARY:-20000}"
MARKETS_REF="${MARKETS_REF:-claude/cycle-0-frankie-box-rerun-od5sxk}"
MANIFEST="${MANIFEST:-research/kalshi/frankie_boss/blocks/BLOCK_20211004_SOURCE_MANIFEST.json}"
case "$MARKETS_REF" in -*|*[!A-Za-z0-9._/-]*) echo "bad MARKETS_REF"; exit 2;; esac
case "$MANIFEST" in research/kalshi/frankie_boss/blocks/BLOCK_*_SOURCE_MANIFEST.json) ;; *) echo "MANIFEST must be a committed blocks/BLOCK_*_SOURCE_MANIFEST.json"; exit 2;; esac
case "$WORKERS$CANARY" in ""|*[!0-9]*) echo "WORKERS and CANARY must be integers"; exit 2;; esac   # SSM runs this under sh: POSIX only
mkdir -p "$ROOT/data" "$ROOT/work" "$ROOT/receipts" "$ROOT/tmp"
PY="$ROOT/venv/bin/python"; [ -x "$PY" ] || { echo "venv not staged"; exit 2; }
git -C "$ROOT/markets" fetch -q --depth 1 origin -- "$MARKETS_REF" && git -C "$ROOT/markets" checkout -q FETCH_HEAD || { echo "markets fetch/checkout of $MARKETS_REF failed"; exit 2; }
echo "markets HEAD $(git -C "$ROOT/markets" rev-parse HEAD) ($MARKETS_REF)"
M="$ROOT/markets/$MANIFEST"; [ -s "$M" ] || { echo "manifest missing at $M"; exit 2; }
BLOCK=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['block'])" "$M") || exit 2
DATA="$ROOT/data/block_$BLOCK"; mkdir -p "$DATA"
units_idle() {
  for U in "frankie-cycle-$CYCLE" "frankie-heartbeat-$CYCLE" "frankie-correction-$CYCLE"; do
    if systemctl is-active --quiet "$U.service"; then echo "$U is running: the ingest waits (the box is the cycle's while its unit runs)"; return 2; fi
  done
}
fetch() {
  [ -n "${MAP_URL:-}" ] || { echo "MAP_URL not set (dispatch frankie_box_run.yml with presign=<bucket>/<prefix>/<member_key> for every partition)"; return 2; }
  cd "$ROOT/tmp" || return 2
  curl -fsS -m 60 --retry 3 -o ingest-map.json "$MAP_URL" || { echo "map download failed"; return 2; }
  M="$M" DATA="$DATA" ROOT="$ROOT" "$PY" - <<'PYEOF'
import hashlib, json, os, subprocess, time
m = json.load(open('ingest-map.json')); manifest = json.load(open(os.environ['M'])); data = os.environ['DATA']
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): h.update(b)
    return h.hexdigest()
receipt = dict(schema='FRANKIE_BOX_INGEST_FETCH_RECEIPT_V1', at=time.time(), block=manifest['block'], files=[], refused=[])
for member in manifest['sources']:
    key = next((k for k in m if k.endswith('/' + member['member_key']) or k == member['member_key']), None)
    dest = os.path.join(data, member['member_key'])
    if os.path.exists(dest):
        have = sha(dest)
        if have == member['sha256'] and os.path.getsize(dest) == member['size_bytes']:
            receipt['files'].append(dict(member_key=member['member_key'], status='present', sha256=have)); print('present', dest); continue
        receipt['refused'].append(dict(member_key=member['member_key'], reason='a different file is already at the destination; not overwritten (move it aside with a receipt first)', sha256=have))
        print('REFUSED (present, different):', dest); continue
    if key is None:
        receipt['refused'].append(dict(member_key=member['member_key'], reason='not in the presigned map')); print('REFUSED (not presigned):', member['member_key']); continue
    if m[key].get('bytes') != member['size_bytes']:
        receipt['refused'].append(dict(member_key=member['member_key'], reason='bytes differ from the manifest', have=m[key].get('bytes'))); print('REFUSED (bytes):', member['member_key']); continue
    part = dest + '.part'; t0 = time.time()
    r = subprocess.run(['curl', '-fsS', '-L', '--retry', '5', '--retry-delay', '5', '-C', '-', '-o', part, m[key]['url']])
    if r.returncode != 0:
        receipt['refused'].append(dict(member_key=member['member_key'], reason='download failed', returncode=r.returncode)); print('FAILED download', member['member_key']); continue
    got = sha(part)
    if got != member['sha256'] or os.path.getsize(part) != member['size_bytes']:
        os.replace(part, part + f'.rejected-{int(time.time())}'); receipt['refused'].append(dict(member_key=member['member_key'], reason='digest differs from the manifest', sha256=got)); print('REFUSED (digest):', member['member_key']); continue
    os.replace(part, dest); receipt['files'].append(dict(member_key=member['member_key'], status='restored', sha256=got, seconds=round(time.time() - t0, 1)))
    print('restored', dest, member['size_bytes'], f'{time.time()-t0:.0f}s')
name = os.path.join(os.environ['ROOT'], 'receipts', f'ingest-fetch-{manifest["block"]}-{int(time.time())}.json')
json.dump(receipt, open(name, 'w'), indent=1, sort_keys=True); print('RECEIPT', name)
raise SystemExit(0 if not receipt['refused'] else 1)
PYEOF
  code=$?; rm -f "$ROOT/tmp/ingest-map.json"; return $code
}
run_tool() {   # $1 = canary|ingest
  units_idle || return 2
  for member in $("$PY" -c "import json,sys; print(' '.join(s['member_key'] for s in json.load(open(sys.argv[1]))['sources']))" "$M"); do
    [ -s "$DATA/$member" ] || { echo "partition $member not on the box (ACTION=fetch first)"; return 2; }
  done
  OUT="$ROOT/work/ingest-$BLOCK-$1-$(date +%s)"     # a fresh directory per run, CREATED BY THE TOOL (it refuses an existing one; run 35680854102); it writes once, never over
  EXTRA=""; [ "$1" = canary ] && EXTRA="--canary-records $CANARY"
  echo "### $1: block $BLOCK, $WORKERS workers, manifest $MANIFEST, out $OUT"
  ( cd "$ROOT/markets" && PYTHONPATH="$ROOT/markets" "$PY" research/kalshi/frankie_boss/operations/ingest_block_sources.py \
      --manifest "$M" --sources-dir "$DATA" --output-dir "$OUT" --session-policy cme_trading_day --workers "$WORKERS" $EXTRA ) \
    || { echo "$1 failed (exit $?); the directory $OUT is kept"; return 3; }
  for R in canary-receipt.json ingestion-receipt.json; do [ -s "$OUT/$R" ] && { echo "### $R"; cat "$OUT/$R"; }; done
}
status() {
  echo "### partitions under $ROOT/data"; ls -la "$ROOT"/data/block_* 2>/dev/null || echo "(none)"
  echo "### ingest work directories"; ls -d "$ROOT"/work/ingest-* 2>/dev/null || echo "(none)"
  for d in "$ROOT"/work/ingest-*/; do [ -d "$d" ] || continue; for R in canary-receipt.json ingestion-receipt.json; do [ -s "$d$R" ] && { echo "### $d$R"; "$PY" -c "import json,sys; r=json.load(open(sys.argv[1])); print(json.dumps({k: r.get(k) for k in ('schema','block','trading_day','records','record_count','records_per_second','extrapolated_hours_for_total','journal_count','journal_sha256','sessions','partial_members_ingested','completion_claimed','workers')}, sort_keys=True))" "$d$R"; }; done; done
  echo "### receipts"; ls "$ROOT"/receipts/ingest-* 2>/dev/null || echo "(none)"
  df -h / | tail -1
}
case "$ACTION" in
  fetch) fetch ;;
  canary) run_tool canary ;;
  ingest) run_tool ingest ;;
  status) status ;;
  *) echo "ACTION must be fetch, canary, ingest or status"; exit 2 ;;
esac
