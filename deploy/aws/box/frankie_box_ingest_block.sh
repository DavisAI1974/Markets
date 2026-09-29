# The TRADING-DAY INGEST on Frankie's box (SPEC-trading-day-ingest.md; Greg 2026-09-22: "Lets rerun cyc 0", "Monday by
# itself before we do 4 days at a time", every CPU the encoders can use while the parent keeps the causal sequence). One committed script, four read-then-act actions:
#   fetch   the manifest's partitions by the presigned map (MAP_URL from frankie_box_run.yml presign=<bucket>/<key> ...),
#           each verified against the manifest's sha256 and size; present and equal = kept; different = REFUSED
#   canary  the ingest tool on the first CANARY records: the measured rate, no completion claim
#   ingest  the ingest tool to completion (the pinned conformance stack reconciles the declared counts)
#   status  what is on the box: partitions, work directories, receipts (touches no git: the current checkout is read)
# Inputs: ACTION, MANIFEST (repo-relative, default the Monday trading day; for fetch and ingest a COMMA LIST of trading
# days in order, each its own journal, each after the first opening with the book the one before it closed with: Greg,
# 2026-09-29 "ingest wed separately so it's there when we need it right after"), OPENING_RECEIPT (the prior trading day's
# sealed ingest receipt for the FIRST day of the list when that day opens at the prior halt: $ROOT/work/ingest-*/
# ingestion-receipt.json, or Monday's recovery receipt on the box, $ROOT/work/sealed-recovery-*/recovery-receipt.json,
# whose checkpoint sits beside it; see opening_book.py), WORKERS (PER DAY PROCESS; default the most its CPU booking fits:
# 3 with VERIFY=inline, 7 with VERIFY=deferred and for a conform; see "CPU booking" below),
# CANARY (default 20000), MARKETS_SHA (the DISPATCHED COMMIT; frankie_box_run.yml sets it from GITHUB_SHA: the box checks out
# that commit, never a branch name, and refuses a HEAD that differs; the chat-9 ship review), CYCLE (00).
# Order (the chat-9 ship review): the cycle units are checked idle BEFORE the checkout moves (a running session lazy-loads
# modules from this checkout), the manifest is validated by the tool's own block_source_scope BEFORE any path is built from
# it, and every destination is pinned under the data directory. Nothing deleted, nothing overwritten, no key, no model call,
# no S3 write (publish is a separate action on Greg's word). SSM runs this under sh: POSIX only.
set -u
ROOT=/opt/frankie-box; CYCLE="${CYCLE:-00}"; ACTION="${ACTION:-status}"; WORKERS="${WORKERS:-}"; CANARY="${CANARY:-20000}"
MARKETS_SHA="${MARKETS_SHA:-}"
# an ingest names its day(s) explicitly: the default (Monday) is for status only, so a dispatch that forgets MANIFEST
# never ingests Monday a second time (the gold standard; the read-only audit of 2026-09-29)
[ "$ACTION" != ingest ] || [ -n "${MANIFEST:-}" ] || { echo "ACTION=ingest requires MANIFEST (the day list); refused"; exit 2; }
MANIFEST="${MANIFEST:-research/kalshi/frankie_boss/blocks/BLOCK_20211004_SOURCE_MANIFEST.json}"
MANIFESTS="$MANIFEST"; OPENING_RECEIPT="${OPENING_RECEIPT:-}"
# Greg, 2026-09-29 ("Do 1-5 now. We are supposed to have save code so we can pick up where we left off"):
#   MODE=sequential|parallel (parallel = operations/parallel_ingest.py: three saved passes on the workers; needs OBSERVATION=none)
#   OBSERVATION=full|none (none = the experiment journal: no full-book copy at a group close)
#   VERIFY=inline|deferred (deferred = seal now, ACTION=conform DIRECTORY=<ingest dir> runs the drain later)
#   DAYS_AT_ONCE=N (the MANIFEST list N days at a time, each its own journal, the workers split between them; only
#     without OPENING_RECEIPT, each day warming its own opening book), RESUME_DIR=<an ingest dir> (parallel: continue it)
# The defaults are Frankie's journal as before (sequential, full, inline, one day at a time).
MODE="${MODE:-sequential}"; OBSERVATION="${OBSERVATION:-full}"; VERIFY="${VERIFY:-inline}"; DAYS_AT_ONCE="${DAYS_AT_ONCE:-1}"
RESUME_DIR="${RESUME_DIR:-}"; DIRECTORY="${DIRECTORY:-}"
case "$MODE" in sequential|parallel) ;; *) echo "MODE must be sequential or parallel"; exit 2;; esac
case "$OBSERVATION" in full|none) ;; *) echo "OBSERVATION must be full or none"; exit 2;; esac
case "$VERIFY" in inline|deferred) ;; *) echo "VERIFY must be inline or deferred"; exit 2;; esac
case "$DAYS_AT_ONCE" in ""|*[!0-9]*|0) echo "DAYS_AT_ONCE must be a positive integer"; exit 2;; esac
case "$RESUME_DIR" in ""|"$ROOT"/work/ingest-*) ;; *) echo "RESUME_DIR must be an existing $ROOT/work/ingest-* directory"; exit 2;; esac
case "$DIRECTORY" in ""|"$ROOT"/work/ingest-*) ;; *) echo "DIRECTORY must be a $ROOT/work/ingest-* directory"; exit 2;; esac
case "$RESUME_DIR$DIRECTORY" in *..*) echo "no .. in RESUME_DIR or DIRECTORY"; exit 2;; esac
[ "$DAYS_AT_ONCE" = 1 ] || [ -z "$OPENING_RECEIPT" ] || { echo "DAYS_AT_ONCE > 1 runs days that warm their own books: no OPENING_RECEIPT"; exit 2; }
case "$MARKETS_SHA" in ""|*[!0-9a-f]*) echo "MARKETS_SHA must be the dispatched commit (frankie_box_run.yml sets it from GITHUB_SHA)"; exit 2;; esac
[ "${#MARKETS_SHA}" -eq 40 ] || { echo "MARKETS_SHA must be the full 40-hex commit"; exit 2; }
case "$MANIFESTS" in *..*) echo "MANIFEST must not contain .."; exit 2;; esac
COUNT=0
for ONE in $(echo "$MANIFESTS" | tr ',' ' '); do
  case "$ONE" in research/kalshi/frankie_boss/blocks/BLOCK_*_SOURCE_MANIFEST.json) ;; *) echo "MANIFEST must be committed blocks/BLOCK_*_SOURCE_MANIFEST.json files ($ONE)"; exit 2;; esac
  case "$ONE" in research/kalshi/frankie_boss/blocks/*/*) echo "MANIFEST must be files directly under blocks/ ($ONE)"; exit 2;; esac
  COUNT=$((COUNT + 1))
done
[ "$COUNT" -ge 1 ] || { echo "MANIFEST names no manifest"; exit 2; }
[ -z "$RESUME_DIR" ] || [ "$COUNT" = 1 ] || { echo "RESUME_DIR continues ONE day: MANIFEST names that day only"; exit 2; }
[ -z "$RESUME_DIR" ] || [ "$MODE" = parallel ] || { echo "RESUME_DIR is the parallel mode's"; exit 2; }
if [ "$COUNT" -gt 1 ]; then case "$ACTION" in fetch|ingest) ;; *) echo "a MANIFEST list is for fetch and ingest only"; exit 2;; esac; fi
case "$OPENING_RECEIPT" in
  "") ;;
  "$ROOT"/work/ingest-*/ingestion-receipt.json|"$ROOT"/work/sealed-recovery-*/recovery-receipt.json) ;;
  *) echo "OPENING_RECEIPT must be a sealed ingest's $ROOT/work/ingest-*/ingestion-receipt.json or a recovery's $ROOT/work/sealed-recovery-*/recovery-receipt.json (its checkpoint beside it)"; exit 2;;
esac
case "$OPENING_RECEIPT" in *..*) echo "OPENING_RECEIPT must not contain .."; exit 2;; esac
# CPU booking (Greg, 2026-09-29: "Correct 16 and no double booking"; "We don't double book cores or workers"): every
# ingest, canary and conform day process books 8 CPUs in the box's ledger (frankie_box_cores.py) and runs under
# taskset -c <its 8>, so every reader worker (pinned from cpus[1:] of the process's own affinity) and every encoder stays
# inside them. THE RULE: VERIFY=inline runs the encode pool and the conformance-reader pool at the same time, so it needs
# WORKERS x 2 + 1 CPUs; VERIFY=deferred and a conform run one pool: WORKERS + 1. Above 8 the dispatch is REFUSED here with
# that reason (measured 2026-09-29: an inline WORKERS=7 ingest ran 14 workers + its parent). Fewer than 8 free: the day
# does not start, prints CPU_BOOKING_WAITING with 'waiting: N free of 8 needed' and the script exits 75 (retry later).
if [ -z "$WORKERS" ]; then
  if [ "$ACTION" = conform ] || [ "$VERIFY" = deferred ]; then WORKERS=7; else WORKERS=3; fi
fi
case "$WORKERS" in ""|*[!0-9]*) echo "WORKERS must be an integer"; exit 2;; esac
if [ "$ACTION" = conform ] || [ "$VERIFY" = deferred ]; then DEMAND=$((WORKERS + 1)); FITS=7; RULE="one pool: WORKERS + 1"
else DEMAND=$((WORKERS * 2 + 1)); FITS=3; RULE="VERIFY=inline runs the encode and verify pools together: WORKERS x 2 + 1"; fi
case "$ACTION" in canary|ingest|conform)
  [ "$DEMAND" -le 8 ] || { echo "WORKERS=$WORKERS needs $DEMAND CPUs ($RULE), more than the 8 a day process books; refused (the most that fits: $FITS)"; exit 2; } ;;
esac
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
MK="$ROOT/markets"      # the code the tool runs from; checkout_markets points it at this commit's own worktree
checkout_markets() {   # item 1 (Greg, 2026-09-29): one worktree per dispatched commit, made under a lock, so dispatches running
  # side by side never move each other's code (the shared checkout is fetched into, never checked out any more)
  MK="$ROOT/ingest-code/$MARKETS_SHA"
  mkdir -p "$ROOT/ingest-code" "$ROOT/tmp"
  ( flock 9
    if [ ! -e "$MK/.git" ]; then
      git -C "$ROOT/markets" fetch -q --depth 1 origin -- "$MARKETS_SHA" || { echo "markets fetch of $MARKETS_SHA failed"; exit 2; }
      git -C "$ROOT/markets" worktree add -q --detach "$MK" "$MARKETS_SHA" || { echo "worktree for $MARKETS_SHA failed"; exit 2; }
    fi ) 9>"$ROOT/tmp/ingest-code.lock" || return 2
  [ "$(git -C "$MK" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "the worktree HEAD differs from the dispatched commit; refused"; return 2; }
  echo "markets worktree $MK (the dispatched commit)"
}
manifest_ok() {   # M, BLOCK, DATA from the checkout as it stands (status) or as just checked out (fetch, canary, ingest)
  M="$MK/$MANIFEST"; [ -s "$M" ] || { echo "manifest missing at $M"; return 2; }
  BLOCK=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['block'])" "$M") || return 2
  case "$BLOCK" in ""|*[!0-9_]*) echo "bad block name in the manifest; refused"; return 2;; esac
  DATA="$ROOT/data/block_$BLOCK"
}
prepare() { units_idle || return 2; checkout_markets || return 2; manifest_ok || return 2; mkdir -p "$DATA"; }
each_day() {   # $1 = fetch|ingest over the MANIFEST list, in order; a day that fails stops the list (the next day's book waits on it)
  units_idle || return 2; checkout_markets || return 2
  if [ "$1" = ingest ] && [ "$DAYS_AT_ONCE" -gt 1 ]; then at_once; return $?; fi
  for MANIFEST in $(echo "$MANIFESTS" | tr ',' ' '); do
    manifest_ok || return 2; mkdir -p "$DATA"
    if [ "$1" = fetch ]; then fetch || return $?; continue; fi
    run_tool ingest; RC=$?
    [ "$RC" != 75 ] || { echo "### the list waits at $MANIFEST for its CPU booking; the days after it wait too (exit 75)"; return 75; }
    [ "$RC" = 0 ] || { echo "### the list stops at $MANIFEST; the days after it wait (each opens with the book this day closes with)"; return 3; }
    [ -s "$OUT/ingestion-receipt.json" ] || { echo "### $OUT has no ingestion receipt; the list stops at $MANIFEST"; return 3; }
    OPENING_RECEIPT="$OUT/ingestion-receipt.json"     # the next day opens with the book this day closed with
  done
}
fetch() {
  [ -n "${MAP_URL:-}" ] || { echo "MAP_URL not set (dispatch frankie_box_run.yml with presign=<bucket>/<prefix>/<member_key> for every partition)"; return 2; }
  case "$MAP_URL" in https://*.amazonaws.com/*) ;; *) echo "MAP_URL must be an https amazonaws URL"; return 2;; esac
  cd "$ROOT/tmp" || return 2
  MAPF="ingest-map-$$.json"     # per dispatch: dispatches running side by side never share or delete each other's map
  curl -fsS --proto =https -m 60 --retry 3 -o "$MAPF" --url "$MAP_URL" || { echo "map download failed"; return 2; }
  MAPF="$MAPF" M="$M" DATA="$DATA" ROOT="$ROOT" MK="$MK" MARKETS_SHA="$MARKETS_SHA" "$PY" - <<'PYEOF'
import glob, hashlib, json, os, subprocess, sys, time
sys.path.insert(0, os.environ['MK'])
from research.kalshi.frankie_boss.block_source_scope import block_source_scope     # the tool's own validation, before any path is built
m = json.load(open(os.environ['MAPF'])); manifest = json.load(open(os.environ['M'])); data = os.path.realpath(os.environ['DATA'])
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
    if not os.path.exists(dest):
        # the same partition already verified under another block (Tuesday's 20211004 tail is in Monday's block): hard-link it,
        # nothing downloaded or copied; only a file whose size and sha256 equal the manifest's is linked
        for other in sorted(glob.glob(os.path.join(os.path.dirname(data), 'block_*', member.member_key))):
            if os.path.getsize(other) == member.size_bytes and sha(other) == member.sha256:
                os.link(other, dest)
                receipt['files'].append(dict(member_key=member.member_key, status='linked', linked_from=other, sha256=member.sha256))
                print('linked', dest, 'from', other); break
        if os.path.exists(dest):
            continue
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
  code=$?; rm -f "$ROOT/tmp/$MAPF"; return $code
}
run_tool() {   # $1 = canary|ingest (prepare ran: units idle, the dispatched commit checked out, the manifest read)
  for member in $("$PY" -c "import json,sys; print(' '.join(s['member_key'] for s in json.load(open(sys.argv[1]))['sources']))" "$M"); do
    [ -s "$DATA/$member" ] || { echo "partition $member not on the box (ACTION=fetch first)"; return 2; }
  done
  OUT="$ROOT/work/ingest-$BLOCK-$1-$(date +%s)"     # a fresh directory per run, CREATED BY THE TOOL (it refuses an existing one; run 35680854102); it writes once, never over
  EXTRA=""; [ "$1" = canary ] && EXTRA="--canary-records $CANARY"
  EXTRA="$EXTRA --mode $MODE --observation $OBSERVATION --verify $VERIFY"
  if [ -n "$RESUME_DIR" ]; then
    [ -d "$RESUME_DIR" ] || { echo "RESUME_DIR $RESUME_DIR is not on the box"; return 2; }
    OUT="$RESUME_DIR"; EXTRA="$EXTRA --resume"; echo "### resuming in $OUT (saved pass 1 and finished segments are reused)"
  fi
  if [ -n "$OPENING_RECEIPT" ]; then
    [ -s "$OPENING_RECEIPT" ] || { echo "OPENING_RECEIPT $OPENING_RECEIPT is not on the box"; return 2; }
    EXTRA="$EXTRA --opening-receipt $OPENING_RECEIPT"; echo "### opening book: the prior day's sealed ingest $OPENING_RECEIPT"
  fi
  [ "${PROFILE:-0}" = 1 ] && EXTRA="$EXTRA --profile"     # PROFILE=1: cProfile the parent, profile.txt in the work directory (a measurement)
  echo "### $1: block $BLOCK, $WORKERS workers, manifest $MANIFEST, markets $MARKETS_SHA, out $OUT"
  # inside its CPU booking: frankie_box_cores.py books 8 CPUs, starts the tool under taskset -c <them>, releases at its end
  ( cd "$MK" && PYTHONPATH="$MK" "$PY" "$MK/deploy/aws/box/frankie_box_cores.py" run --kind "$1" --day "$BLOCK" \
      --run "$(basename "$OUT")" --stage "$1" --commit "$MARKETS_SHA" --workers "$WORKERS" --verify "$VERIFY" -- \
      "$PY" research/kalshi/frankie_boss/operations/ingest_block_sources.py \
      --manifest "$M" --sources-dir "$DATA" --output-dir "$OUT" --session-policy cme_trading_day --workers "$WORKERS" $EXTRA )
  RC=$?
  [ "$RC" != 75 ] || { echo "### $1 of block $BLOCK WAITING for its CPU booking (not started; nothing written)"; return 75; }
  [ "$RC" = 0 ] || { echo "$1 failed (exit $RC); the directory $OUT is kept"; return 3; }
  for R in canary-receipt.json ingestion-receipt.json; do [ -s "$OUT/$R" ] && { echo "### $R"; cat "$OUT/$R"; }; done
  [ -s "$OUT/profile.txt" ] && { echo "### profile.txt (whole)"; cat "$OUT/profile.txt"; }
  return 0     # the tool's exit decided above; a missing ingestion receipt on a canary is not a failure (run 35681037861 exited 1 on this test)
}
at_once() {   # DAYS_AT_ONCE days of the list side by side (each warms its own book), each day process its own 8-CPU booking
  # with WORKERS workers (never split, never shared: a day that cannot book its 8 waits and is listed)
  N=$(echo "$MANIFESTS" | tr ',' '\n' | grep -c .); AT=$DAYS_AT_ONCE; [ "$N" -ge "$AT" ] || AT=$N
  SHARE=$WORKERS
  RUNNING=0; FAILED=0; WAITED=0
  for MANIFEST in $(echo "$MANIFESTS" | tr ',' ' '); do       # POSIX sh: batches of AT days, each batch waited whole
    manifest_ok || return 2; mkdir -p "$DATA"
    ( WORKERS=$SHARE; run_tool ingest ) > "$ROOT/tmp/ingest-$BLOCK-$$.log" 2>&1 &
    echo "### started $MANIFEST (pid $!, $SHARE workers, log $ROOT/tmp/ingest-$BLOCK-$$.log)"
    RUNNING=$((RUNNING + 1))
    if [ "$RUNNING" -ge "$AT" ]; then wait; RUNNING=0; fi
    sleep 1                                   # distinct output directory names (their names carry the second)
  done
  wait
  for MANIFEST in $(echo "$MANIFESTS" | tr ',' ' '); do
    manifest_ok || return 2
    echo "### $MANIFEST"; cat "$ROOT/tmp/ingest-$BLOCK-$$.log"
    if ! grep -q '"schema": "BOSS_BLOCK_INGESTION_RECEIPT_V1"' "$ROOT/tmp/ingest-$BLOCK-$$.log"; then
      FAILED=$((FAILED + 1)); if grep -q '^CPU_BOOKING_WAITING ' "$ROOT/tmp/ingest-$BLOCK-$$.log"; then WAITED=$((WAITED + 1)); fi
    fi
  done
  [ "$FAILED" -eq 0 ] || [ "$FAILED" != "$WAITED" ] || { echo "### $WAITED day(s) WAITING for a CPU booking (not started); retry later (exit 75)"; return 75; }
  [ "$FAILED" -eq 0 ] || { echo "### $FAILED day(s) have no sealed ingest ($WAITED of them waiting for a CPU booking); each directory is kept (RESUME_DIR continues a parallel one)"; return 3; }
}
conform() {   # item 3's later half: the conformance drain on a sealed ingest whose conformance was deferred (the day's
  # manifest is the committed one the receipt names by hash)
  [ -n "$DIRECTORY" ] && [ -s "$DIRECTORY/ingestion-receipt.json" ] || { echo "DIRECTORY must hold a sealed ingestion-receipt.json"; return 2; }
  ( cd "$MK" && PYTHONPATH="$MK" "$PY" "$MK/deploy/aws/box/frankie_box_cores.py" run --kind conform \
      --day "$(basename "$DIRECTORY")" --run "$(basename "$DIRECTORY")" --stage conform --commit "$MARKETS_SHA" --workers "$WORKERS" -- \
      "$PY" research/kalshi/frankie_boss/operations/ingest_block_sources.py --conform "$DIRECTORY" --workers "$WORKERS" )
  RC=$?
  [ "$RC" != 75 ] || { echo "### conform WAITING for its CPU booking (not started)"; return 75; }
  [ "$RC" = 0 ] || { echo "conform failed or differs (exit $RC)"; return 3; }
  cat "$DIRECTORY/conformance.json"
}
status() {
  echo "### markets HEAD $(git -C "$ROOT/markets" rev-parse HEAD 2>/dev/null || echo unknown) (as it stands; status moves nothing)"
  echo "### partitions under $ROOT/data"; ls -la "$ROOT"/data/block_* 2>/dev/null || echo "(none)"
  echo "### ingest work directories"; ls -d "$ROOT"/work/ingest-* 2>/dev/null || echo "(none)"
  for d in "$ROOT"/work/ingest-*/; do [ -d "$d" ] || continue; for R in canary-receipt.json ingestion-receipt.json; do [ -s "$d$R" ] && { echo "### $d$R"; "$PY" -c "import json,sys; r=json.load(open(sys.argv[1])); keys=('schema','block','trading_day','records','record_count','records_per_second','extrapolated_hours_for_total','journal_count','journal_head_hash','journal_sha256','sessions','partial_members','partial_members_ingested','tail_members_ingested','opening_book','completion_claimed','workers'); print(json.dumps({k: r[k] for k in keys if k in r}, sort_keys=True))" "$d$R"; }; done; done
  for d in "$ROOT"/work/ingest-*/; do [ -s "$d/journal.compact.sqlite" ] && { echo "### $d/journal.compact.sqlite (boxes, rows, bytes)"; "$PY" -c "import sqlite3,sys,os; p=sys.argv[1]; db=sqlite3.connect('file:'+p+'?mode=ro', uri=True); n,rows,body=next(db.execute('SELECT count(*), coalesce(sum(count),0), coalesce(sum(length(body)),0) FROM blocks')); print(dict(boxes=n, rows=rows, block_bytes=body, file_bytes=os.path.getsize(p), bytes_per_row=(round(body/rows,1) if rows else None)))" "$d/journal.compact.sqlite"; }; done
  echo "### receipts"; ls "$ROOT"/receipts/ingest-* 2>/dev/null || echo "(none)"
  df -h / | tail -1
}
# Worker spread (Greg, 2026-09-29: "Is there any way we can speed this part up?" / "Fix that please"): the reader pins each
# worker to one CPU from cpus[1:], so drains started side by side all land on CPUs 1..N while the rest idle (measured
# 16:50Z: CPUs 1-6 at 100%, 7-31 idle; spreading them made the drains 4-5x faster). While an ingest or conform runs, a
# sidecar re-runs the committed frankie_box_spread_workers.sh every 60 s (CPU affinity only; nothing stopped or changed in
# what is written); it ends with this script.
spread_sidecar() {
  mkdir -p "$ROOT/logs"
  ( while :; do SP="$ROOT/ingest-code/$MARKETS_SHA/deploy/aws/box/frankie_box_spread_workers.sh"
      [ -f "$SP" ] && sh "$SP" >>"$ROOT/logs/spread-workers.log" 2>&1; sleep 60; done ) >/dev/null 2>&1 </dev/null &
  SPREAD_PID=$!
  trap 'kill "$SPREAD_PID" 2>/dev/null' EXIT
}
case "$ACTION" in ingest|conform) spread_sidecar ;; esac
case "$ACTION" in
  fetch) each_day fetch ;;
  canary) prepare && run_tool canary ;;
  conform) units_idle && checkout_markets && conform ;;
  ingest) each_day ingest ;;
  status) manifest_ok && status ;;
  *) echo "ACTION must be fetch, canary, ingest, conform or status"; exit 2 ;;
esac
