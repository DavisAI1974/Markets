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
# whose checkpoint sits beside it; see opening_book.py), DAY_CPUS (8|16|24|32|auto, the CPUs one day process books) and
# WORKERS (PER DAY PROCESS; default DAY_CPUS - 1: one pool at a time; see "CPU booking" below), FETCH_AHEAD (on|off,
# default on with MAP_URL: a list's next day is fetched inside the running day's booking), MEMBER_STREAMS / RANGE_STREAMS
# (the fetch's members side by side and its shared 16 MB range GETs),
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
case "${FETCH_AHEAD:-on}" in on|off) ;; *) echo "FETCH_AHEAD must be on or off"; exit 2;; esac
case "${MEMBER_STREAMS:-1}" in ""|*[!0-9]*|0) echo "MEMBER_STREAMS must be a positive integer"; exit 2;; esac
case "${RANGE_STREAMS:-15}" in ""|*[!0-9]*|0) echo "RANGE_STREAMS must be a positive integer"; exit 2;; esac
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
# ingest, canary and conform day process books its CPUs in the box's ledger (frankie_box_cores.py) and runs under
# taskset -c <them>; inside, the parent is pinned to the lowest booked CPU and every encoder, replay and reader worker
# to one other booked CPU, physical cores first (operations/ingest_cpus.py), so nothing floats and nothing leaves the
# booking. SIZE (Greg, 2026-10-07 night: "Including ingest. Basically anything using a cpu to do its work"):
#   DAY_CPUS=8|16|24|32|auto  the CPUs one day process books. auto = the free CPUs (frankie_box_cores.py free) divided by
#     the days run side by side, rounded down to 8/16/24/32: one day takes the whole box, or the days fill it together.
#     Default: auto for MODE=parallel and ACTION=conform (their pools scale with the CPUs), 8 for the sequential writer
#     (its parent is the causal sequence; more encoders would idle); with WORKERS given, the smallest size it fits.
#   WORKERS  default DAY_CPUS - 1. THE RULE: a day process runs ONE pool at a time (the encode pool ends at the seal,
#     before the conformance reader starts; the parallel writer's replay/encode pool closes before its reader), so it
#     needs WORKERS + 1 CPUs; a demand above DAY_CPUS is REFUSED with that reason (measured 2026-09-29: an inline
#     WORKERS=7 ingest of the older writer kept both pools alive, 14 workers + its parent). The output never depends on
#     the count: the encodings are pure, the replay segments are fixed by the plan, the reader only verifies.
# A size not free: the day does not start, prints CPU_BOOKING_WAITING with 'waiting: N free of M needed' and the script
# exits 75 (retry later).
DAY_CPUS="${DAY_CPUS:-}"
case "$DAY_CPUS" in ""|auto|8|16|24|32) ;; *) echo "DAY_CPUS must be 8, 16, 24, 32 or auto"; exit 2;; esac
case "$WORKERS" in "") ;; *[!0-9]*) echo "WORKERS must be an integer"; exit 2;; esac
case "$CANARY" in ""|*[!0-9]*) echo "CANARY must be an integer"; exit 2;; esac
NCPU=$(nproc 2>/dev/null || echo 1)
[ -z "$WORKERS" ] || [ "$WORKERS" -le "$NCPU" ] || { echo "WORKERS must be at most the box's $NCPU CPUs"; exit 2; }
[ "$CANARY" -ge 1 ] || { echo "CANARY must be at least 1"; exit 2; }
AT=1
size_day() {   # resolves DAY_CPUS and WORKERS for the day process(es) about to start (after the checkout: this commit's
  # frankie_box_cores.py answers `free`); idempotent once resolved; AT = the days that will book side by side
  if [ -z "$DAY_CPUS" ] && [ -n "$WORKERS" ]; then
    for S in 8 16 24 32; do if [ $((WORKERS + 1)) -le "$S" ]; then DAY_CPUS=$S; break; fi; done
    [ -n "$DAY_CPUS" ] || { echo "WORKERS=$WORKERS needs $((WORKERS + 1)) CPUs, more than the 32 a day process books; refused"; return 2; }
  fi
  if [ -z "$DAY_CPUS" ]; then
    if [ "$MODE" = parallel ] || [ "$ACTION" = conform ]; then DAY_CPUS=auto; else DAY_CPUS=8; fi
  fi
  if [ "$DAY_CPUS" = auto ]; then
    FREE=$("$PY" -I -S "$MK/deploy/aws/box/frankie_box_cores.py" free 2>/dev/null | cut -d' ' -f1)
    case "$FREE" in ""|*[!0-9]*) FREE=$NCPU; echo "### the ledger's free count could not be read; sizing from the box's $NCPU CPUs";; esac
    PER=$((FREE / AT)); DAY_CPUS=8
    for S in 16 24 32; do if [ "$PER" -ge "$S" ]; then DAY_CPUS=$S; fi; done
    echo "### DAY_CPUS=auto: $FREE CPUs free for $AT day process(es) side by side: $DAY_CPUS CPUs each"
  fi
  [ "$DAY_CPUS" -le "$NCPU" ] || { echo "DAY_CPUS=$DAY_CPUS is more than the box's $NCPU CPUs; refused"; return 2; }
  [ -n "$WORKERS" ] || WORKERS=$((DAY_CPUS - 1))
  DEMAND=$((WORKERS + 1))
  [ "$DEMAND" -le "$DAY_CPUS" ] || { echo "WORKERS=$WORKERS needs $DEMAND CPUs (one pool at a time: WORKERS + 1), more than the $DAY_CPUS this day process books; refused (the most that fits: $((DAY_CPUS - 1)), or a larger DAY_CPUS)"; return 2; }
}
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
  if [ "$1" = ingest ]; then size_day || return 2; fi
  I=0; FA=""
  for MANIFEST in $(echo "$MANIFESTS" | tr ',' ' '); do
    I=$((I + 1))
    if [ -n "$FA" ]; then fetch_ahead_wait "$FA"; FA=""; fi       # this day's partitions, fetched inside the previous day's booking
    manifest_ok || return 2; mkdir -p "$DATA"
    if [ "$1" = fetch ]; then fetch || return $?; continue; fi
    if [ -n "${MAP_URL:-}" ] && ! partitions_present; then fetch || return $?; fi   # the first day (or a skipped fetch-ahead)
    # FETCH-AHEAD (Greg, 2026-10-07 night: "fetch of partition N+1 while decoding N"): with MAP_URL set, the next day's
    # partitions are fetched while this day ingests, INSIDE this day's CPU booking (taskset of its booked CPUs, read from
    # the booking outcome), so nothing outside the ledger runs; the next day starts only after that fetch has ended.
    NEXT=$(echo "$MANIFESTS" | tr ',' '\n' | grep . | sed -n "$((I + 1))p")
    OUTCOME="$ROOT/tmp/ingest-booking-$$-$I.json"
    if [ -n "$NEXT" ] && [ -n "${MAP_URL:-}" ] && [ "${FETCH_AHEAD:-on}" != off ]; then
      FA="$ROOT/tmp/ingest-fetch-ahead-$$-$((I + 1))"; fetch_ahead "$OUTCOME" "$NEXT" "$FA"
    fi
    BOOKING_OUTCOME="$OUTCOME"; run_tool ingest; RC=$?; BOOKING_OUTCOME=""
    [ -s "$OUTCOME" ] || echo '{"status": "not started"}' > "$OUTCOME"     # a fetch-ahead waiting on it ends at once
    if [ "$RC" != 0 ] && [ -n "$FA" ]; then fetch_ahead_wait "$FA"; FA=""; fi
    [ "$RC" != 75 ] || { echo "### the list waits at $MANIFEST for its CPU booking; the days after it wait too (exit 75)"; return 75; }
    [ "$RC" = 0 ] || { echo "### the list stops at $MANIFEST; the days after it wait (each opens with the book this day closes with)"; return 3; }
    [ -s "$OUT/ingestion-receipt.json" ] || { echo "### $OUT has no ingestion receipt; the list stops at $MANIFEST"; [ -z "$FA" ] || fetch_ahead_wait "$FA"; return 3; }
    OPENING_RECEIPT="$OUT/ingestion-receipt.json"     # the next day opens with the book this day closed with
  done
}
partitions_present() {   # every member of the manifest M on the box under DATA (sizes and sha256 are the fetch's and the tool's checks)
  for member in $("$PY" -c "import json,sys; print(' '.join(s['member_key'] for s in json.load(open(sys.argv[1]))['sources']))" "$M"); do
    [ -s "$DATA/$member" ] || return 1
  done
}
fetch_ahead() {   # $1 = the booking outcome file of the day about to ingest, $2 = the next day's manifest, $3 = marker prefix
  ( W=0
    while [ ! -s "$1" ] && [ "$W" -lt 900 ]; do sleep 1; W=$((W + 1)); done
    CPUS=$("$PY" -I -S -c "import json,sys; o=json.load(open(sys.argv[1])); print(o.get('cpus') or '' if o.get('status') == 'booked' else '')" "$1" 2>/dev/null)
    case "$CPUS" in ""|*[!0-9,-]*) echo "### fetch-ahead of $2 skipped: the day's booking was not made (the day fetches it before it starts)"; echo skipped > "$3.rc"; exit 0;; esac
    MANIFEST="$2"
    if manifest_ok && mkdir -p "$DATA"; then
      echo "### fetch-ahead of $MANIFEST inside the running day's booking (CPUs $CPUS)"
      FETCH_PIN="taskset -c $CPUS" fetch; RC=$?
    else RC=2; fi
    echo "$RC" > "$3.rc.tmp" && mv "$3.rc.tmp" "$3.rc"
  ) > "$3.log" 2>&1 &
  FA_PID=$!
}
fetch_ahead_wait() {   # $1 = marker prefix: waits for the fetch-ahead, prints its log; a failed one is fetched again by the day itself
  while [ ! -s "$1.rc" ] && kill -0 "$FA_PID" 2>/dev/null; do sleep 2; done
  [ -s "$1.rc" ] || echo 2 > "$1.rc"                       # ended without its exit record: treated as failed (refetched)
  echo "### fetch-ahead log ($1.log)"; cat "$1.log"
  [ "$(cat "$1.rc")" = 0 ] || [ "$(cat "$1.rc")" = skipped ] || echo "### fetch-ahead exited $(cat "$1.rc"); the day checks its partitions and fetches again before it starts"
}
fetch() {   # FETCH_PIN (optional) = "taskset -c <cpus>": the fetch runs inside a day booking it was handed (fetch-ahead)
  [ -n "${MAP_URL:-}" ] || { echo "MAP_URL not set (dispatch frankie_box_run.yml with presign=<bucket>/<prefix>/<member_key> for every partition)"; return 2; }
  case "$MAP_URL" in https://*.amazonaws.com/*) ;; *) echo "MAP_URL must be an https amazonaws URL"; return 2;; esac
  cd "$ROOT/tmp" || return 2
  MAPF="ingest-map-$$-$BLOCK.json"     # per dispatch and day: dispatches and fetch-aheads never share or delete each other's map
  curl -fsS --proto =https -m 60 --retry 3 -o "$MAPF" --url "$MAP_URL" || { echo "map download failed"; return 2; }
  MAPF="$MAPF" M="$M" DATA="$DATA" ROOT="$ROOT" MK="$MK" MARKETS_SHA="$MARKETS_SHA" FETCH_PIN="${FETCH_PIN:-}" ${FETCH_PIN:-} "$PY" - <<'PYEOF'
import glob, hashlib, json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
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
# A partition above RANGED_ABOVE is pulled as concurrent byte-range GETs of the same presigned URL (aws-storage skill, S3
# byte-range fetches: 8-16 MB ranges, ~15 streams fill a 12.5 Gb/s NIC; the journal pull's pattern) written at their
# offsets into <dest>.part; smaller ones keep the one curl stream. The bytes and sha256 check below are unchanged.
# The members run side by side (MEMBER_STREAMS, default every member up to 4; Greg, 2026-10-07 night "anything using a
# cpu"): ONE shared pool of RANGE_STREAMS range GETs serves all of them (the NIC budget is not multiplied), and a member is
# hashed the moment it lands while the others still download. The receipt lists the members in manifest order.
# The transfer itself is the ONE shared transport (deploy/aws/box/frankie_box_s3_transport.fetch_url, session 5): above
# 64 MiB, RANGE_STREAMS concurrent 16 MiB byte-range GETs from the shared pool; at or below, one stream with range resume;
# the sha256 is computed IN ORDER WHILE THE BYTES LAND (the partition is never re-read to hash it: COMPUTE dedupe), every
# retry and any report-only stall is on the transport receipt, every read has a 120 s socket timeout and bounded tries
# (the old one-stream curl had no stall bound). The bytes and sha256 check against the manifest is unchanged.
sys.path.insert(0, os.path.join(os.environ['MK'], 'deploy', 'aws', 'box'))
import frankie_box_s3_transport as T
RANGE_STREAMS = int(os.environ.get('RANGE_STREAMS') or 15)
MEMBER_STREAMS = int(os.environ.get('MEMBER_STREAMS') or min(4, max(1, len(scope.members))))
RANGES = ThreadPoolExecutor(max(1, RANGE_STREAMS), thread_name_prefix='range')
SAY = threading.Lock()
def say(*a):
    with SAY:
        print(*a, flush=True)
# one FRANKIE_WORK_PROBE_V1 progress.json for the block's fetch (bytes of the members still to download), beside the
# partitions (the stage heartbeat finds a probe beside the files the tree holds open)
TO_FETCH = sum(mm.size_bytes for mm in scope.members if not os.path.exists(os.path.join(data, mm.member_key)))
PROBE = T.WorkProbe(data, 'fetch:block_' + str(manifest['block']), TO_FETCH)
LANDED = [0]; LANDED_LOCK = threading.Lock()
def landed(n):
    with LANDED_LOCK:
        LANDED[0] += n
        PROBE.update(LANDED[0])
def member_one(member):
    """(kind, entry): kind 'files' or 'refused', exactly the entries the one-at-a-time loop wrote."""
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
                say('linked', dest, 'from', other)
                return 'files', dict(member_key=member.member_key, status='linked', linked_from=other, sha256=member.sha256)
    if os.path.exists(dest):
        have = sha(dest)
        if have == member.sha256 and os.path.getsize(dest) == member.size_bytes:
            say('present', dest); return 'files', dict(member_key=member.member_key, status='present', sha256=have)
        say('REFUSED (present, different):', dest)
        return 'refused', dict(member_key=member.member_key, reason='a different file is already at the destination; not overwritten (move it aside with a receipt first)', sha256=have)
    if key is None:
        say('REFUSED (not presigned):', member.member_key); return 'refused', dict(member_key=member.member_key, reason='not in the presigned map')
    if m[key].get('bytes') != member.size_bytes:
        say('REFUSED (bytes):', member.member_key); return 'refused', dict(member_key=member.member_key, reason='bytes differ from the manifest', have=m[key].get('bytes'))
    if not ok_url(m[key].get('url')):
        say('REFUSED (url):', member.member_key); return 'refused', dict(member_key=member.member_key, reason='the map entry is not an https amazonaws URL')
    t0 = time.time()
    tr = T.fetch_url(m[key]['url'], dest, expected_bytes=member.size_bytes, expected_sha256=member.sha256,
                     range_streams=RANGE_STREAMS, ranges=RANGES, say=say, on_bytes=landed)
    if tr['status'] != 'restored':     # the same refusals as before (download / digest / late), the reason from the transport
        return 'refused', dict(member_key=member.member_key, reason=tr.get('reason'), sha256=tr.get('sha256'),
                               kept_aside=tr.get('kept_aside'), transport=tr.get('transport'), transport_receipt=tr)
    say('restored', dest, member.size_bytes, f'{time.time()-t0:.0f}s', tr['transport'], '%d retries' % len(tr['retries']))
    return 'files', dict(member_key=member.member_key, status='restored', sha256=tr['sha256'], seconds=round(time.time() - t0, 1),
                         transport=tr['transport'], hash_pass=tr['hash_pass'], retries=len(tr['retries']),
                         stalls=len(tr['stalls']), transport_receipt=tr)
receipt = dict(schema='FRANKIE_BOX_INGEST_FETCH_RECEIPT_V1', at=time.time(), block=manifest['block'], manifest_hash=manifest['manifest_hash'],
               markets_sha=os.environ['MARKETS_SHA'], files=[], refused=[], member_streams=MEMBER_STREAMS, range_streams=RANGE_STREAMS,
               transport_module=T.SCHEMA, fetch_pin=os.environ.get('FETCH_PIN') or None, bytes_to_fetch=TO_FETCH,
               rehash_rule='a partition already present is hashed again in full (no skip by stat: Greg\'s open call (c))')
try:
    with ThreadPoolExecutor(max(1, MEMBER_STREAMS), thread_name_prefix='member') as members:
        for kind, entry in members.map(member_one, scope.members):    # manifest order
            receipt[kind].append(entry)
finally:
    RANGES.shutdown(wait=True)        # bounded: every range read has a socket timeout and bounded tries
    PROBE.update(LANDED[0], state='complete' if not receipt['refused'] else 'refused', force=True)
receipt['bytes_fetched'] = LANDED[0]
name = os.path.join(os.environ['ROOT'], 'receipts', f'ingest-fetch-{manifest["block"]}-{int(time.time())}-{os.getpid()}.json')
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
  size_day || return 2
  echo "### $1: block $BLOCK, $DAY_CPUS CPUs, $WORKERS workers, manifest $MANIFEST, markets $MARKETS_SHA, out $OUT"
  # inside its CPU booking: frankie_box_cores.py books DAY_CPUS CPUs, starts the tool under taskset -c <them>, releases at
  # its end; the booking outcome (booked CPUs) goes to BOOKING_OUTCOME when a fetch-ahead waits on it
  ( cd "$MK" && PYTHONPATH="$MK" "$PY" "$MK/deploy/aws/box/frankie_box_cores.py" run --kind "$1" --day "$BLOCK" \
      --run "$(basename "$OUT")" --stage "$1" --commit "$MARKETS_SHA" --workers "$WORKERS" --verify "$VERIFY" \
      --size "$DAY_CPUS" ${BOOKING_OUTCOME:+--outcome "$BOOKING_OUTCOME"} -- \
      "$PY" research/kalshi/frankie_boss/operations/ingest_block_sources.py \
      --manifest "$M" --sources-dir "$DATA" --output-dir "$OUT" --session-policy cme_trading_day --workers "$WORKERS" $EXTRA )
  RC=$?
  [ "$RC" != 75 ] || { echo "### $1 of block $BLOCK WAITING for its CPU booking (not started; nothing written)"; return 75; }
  [ "$RC" = 0 ] || { echo "$1 failed (exit $RC); the directory $OUT is kept"; return 3; }
  for R in canary-receipt.json ingestion-receipt.json; do [ -s "$OUT/$R" ] && { echo "### $R"; cat "$OUT/$R"; }; done
  [ -s "$OUT/profile.txt" ] && { echo "### profile.txt (whole)"; cat "$OUT/profile.txt"; }
  return 0     # the tool's exit decided above; a missing ingestion receipt on a canary is not a failure (run 35681037861 exited 1 on this test)
}
at_once() {   # DAYS_AT_ONCE days of the list side by side (each warms its own book), each day process its own booking of
  # DAY_CPUS (auto: the free CPUs divided among the days at once) with WORKERS workers (never split, never shared: a day
  # that cannot book waits and is listed). ROLLING (Greg, 2026-10-07 night, nothing idle): the next day starts as soon as
  # any running day ends, not when a whole batch has ended. With MAP_URL set, every day's partitions are fetched first
  # (members side by side, ranged), before any day books: a fetch outside a booking never runs beside the days.
  N=$(echo "$MANIFESTS" | tr ',' '\n' | grep -c .); AT=$DAYS_AT_ONCE; [ "$N" -ge "$AT" ] || AT=$N
  if [ -n "${MAP_URL:-}" ]; then
    for MANIFEST in $(echo "$MANIFESTS" | tr ',' ' '); do
      manifest_ok || return 2; mkdir -p "$DATA"; partitions_present || fetch || return $?
    done
  fi
  size_day || return 2
  RUNNING=""; FAILED=0; WAITED=0
  for MANIFEST in $(echo "$MANIFESTS" | tr ',' ' '); do       # POSIX sh: a slot frees when any running day's pid ends
    while :; do
      LIVE=""; C=0; for P in $RUNNING; do if kill -0 "$P" 2>/dev/null; then LIVE="$LIVE $P"; C=$((C + 1)); fi; done; RUNNING=$LIVE
      [ "$C" -lt "$AT" ] && break
      sleep 2
    done
    manifest_ok || return 2; mkdir -p "$DATA"
    ( run_tool ingest ) > "$ROOT/tmp/ingest-$BLOCK-$$.log" 2>&1 &
    RUNNING="$RUNNING $!"
    echo "### started $MANIFEST (pid $!, $DAY_CPUS CPUs, $WORKERS workers, log $ROOT/tmp/ingest-$BLOCK-$$.log)"
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
  size_day || return 2
  echo "### conform: $DIRECTORY, $DAY_CPUS CPUs, $WORKERS reader workers"
  ( cd "$MK" && PYTHONPATH="$MK" "$PY" "$MK/deploy/aws/box/frankie_box_cores.py" run --kind conform \
      --day "$(basename "$DIRECTORY")" --run "$(basename "$DIRECTORY")" --stage conform --commit "$MARKETS_SHA" --workers "$WORKERS" \
      --size "$DAY_CPUS" -- \
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
