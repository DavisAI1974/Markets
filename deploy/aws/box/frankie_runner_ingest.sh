# ONE trading day's ingest on a GitHub-hosted runner (Greg, 2026-09-29: "Keep ingest data in aws and make a pointer that
# points at git ... use those CPUs just for ingest"; the box's 32 CPUs are the bottleneck). Runs ON THE RUNNER (not over
# SSM), dispatched through frankie_box_run.yml script=deploy/aws/box/frankie_runner_ingest.sh variables="DAYS=<d1,d2,..>
# [WORKERS=3] [VERIFY=inline] [OBSERVATION=full] [MODE=sequential]"; one matrix job per day.
# 1. the day's committed manifest research/kalshi/frankie_boss/blocks/BLOCK_<DAY>_SOURCE_MANIFEST.json;
# 2. each member downloaded from S3 by its session's archive_key (the manifest's prefix lacks the month folder), checked
#    against the manifest's size and sha256 (a different file is REFUSED);
# 3. the same tool the box runs (operations/ingest_block_sources.py, cme_trading_day), the day warming its own opening
#    book (as DAYS_AT_ONCE does on the box);
# 4. every output file sha256'd and uploaded to s3://<manifest bucket>/frankie/ingest/<DAY>/gh-<run>-<attempt>/, each
#    re-read by head_object (size) after upload; the journal NEVER goes to git;
# 5. a pointer (FRANKIE_INGEST_POINTER_V1: day, manifest hash, S3 prefix, every file with bytes and sha256, the receipt,
#    run id, commit) written to $POINTER for the pointer job to commit to the branch frankie-ingest-pointers.
# Nothing dropped: a failed day uploads what it wrote (progress, partial receipts) under the same prefix and its pointer
# says status failed. No model call, no Databento.
set -euo pipefail
: "${DAY:?trading day required}"; : "${POINTER:?pointer output path required}"
WORKERS="${WORKERS:-3}"; VERIFY="${VERIFY:-inline}"; OBSERVATION="${OBSERVATION:-full}"; MODE="${MODE:-sequential}"
[[ "$DAY" =~ ^[0-9]{8}$ ]] || { echo "DAY must be YYYYMMDD"; exit 2; }
[[ "$WORKERS" =~ ^[0-9]+$ ]] || { echo "WORKERS must be an integer"; exit 2; }
case "$VERIFY" in inline|deferred) ;; *) echo "VERIFY must be inline or deferred"; exit 2;; esac
case "$OBSERVATION" in full|none) ;; *) echo "OBSERVATION must be full or none"; exit 2;; esac
case "$MODE" in sequential|parallel) ;; *) echo "MODE must be sequential or parallel"; exit 2;; esac
M="research/kalshi/frankie_boss/blocks/BLOCK_${DAY}_SOURCE_MANIFEST.json"
[ -s "$M" ] || { echo "no committed manifest $M"; exit 2; }
echo "### runner"; nproc; free -g | head -2; df -h / /mnt 2>/dev/null
# the largest free disk: /mnt when it has more room than /
WORK=/mnt/frankie; sudo mkdir -p "$WORK" && sudo chown "$(id -u):$(id -g)" "$WORK" || WORK="$RUNNER_TEMP/frankie"
FREE_MNT=$(df -B1 --output=avail "$WORK" | tail -1); FREE_ROOT=$(df -B1 --output=avail "$RUNNER_TEMP" | tail -1)
if [ "$FREE_ROOT" -gt "$FREE_MNT" ]; then WORK="$RUNNER_TEMP/frankie"; fi
mkdir -p "$WORK/sources"; echo "work directory $WORK ($(df -h --output=avail "$WORK" | tail -1) free)"
OUT="$WORK/ingest-$DAY-gh-$GITHUB_RUN_ID"
PREFIX="frankie/ingest/$DAY/gh-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
echo "### members"
python - "$M" "$WORK/sources" <<'PY'
import hashlib, json, sys, boto3
from pathlib import Path
m = json.load(open(sys.argv[1])); out = Path(sys.argv[2])
archive = {Path(s['archive_key']).name: s['archive_key'] for s in m['sessions']}
s3 = boto3.client('s3', region_name='us-east-2')
for member in m['sources']:
    key = archive.get(member['member_key'])
    if key is None:
        raise SystemExit('no session archive_key for ' + member['member_key'])
    target = out / member['member_key']
    s3.download_file(m['bucket'], key, str(target))
    h = hashlib.sha256()
    with open(target, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    if target.stat().st_size != member['size_bytes'] or h.hexdigest() != member['sha256']:
        raise SystemExit('member differs from the manifest: %s' % member['member_key'])
    print(member['member_key'], member['size_bytes'], 'sha256 ok', flush=True)
PY
echo "### ingest $DAY: $WORKERS workers, mode $MODE, observation $OBSERVATION, verify $VERIFY"
STATUS=sealed
START=$(date +%s)
set +e
PYTHONPATH="$PWD" python research/kalshi/frankie_boss/operations/ingest_block_sources.py --manifest "$M" \
  --sources-dir "$WORK/sources" --output-dir "$OUT" --session-policy cme_trading_day --workers "$WORKERS" \
  --mode "$MODE" --observation "$OBSERVATION" --verify "$VERIFY" 2>&1 | tee "$WORK/ingest.log" \
  | grep --line-buffered -E '"records": [0-9]*00000,|"phase": "(start|complete|conformance)|Error|error|Traceback'
TOOL_EXIT=${PIPESTATUS[0]}   # the probe above: every 100k records, the phases and any error stream to the job log
set -e
[ "$TOOL_EXIT" = 0 ] || STATUS=failed
WALL=$(( $(date +%s) - START ))
tail -n 40 "$WORK/ingest.log"
[ -s "$OUT/ingestion-receipt.json" ] || STATUS=failed
mkdir -p "$OUT"; cp "$WORK/ingest.log" "$OUT/runner-ingest.log"
echo "### upload to s3://<bucket>/$PREFIX ($STATUS, ${WALL}s)"
python - "$M" "$OUT" "$PREFIX" "$POINTER" "$STATUS" "$WALL" <<'PY'
import hashlib, json, os, sys, boto3
from pathlib import Path
m = json.load(open(sys.argv[1])); out = Path(sys.argv[2]); prefix = sys.argv[3]
s3 = boto3.client('s3', region_name='us-east-2')
files = []
for p in sorted(x for x in out.rglob('*') if x.is_file()):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    key = prefix + '/' + str(p.relative_to(out))
    s3.upload_file(str(p), m['bucket'], key)
    size = s3.head_object(Bucket=m['bucket'], Key=key)['ContentLength']
    if size != p.stat().st_size:
        raise SystemExit('uploaded size differs: ' + key)
    files.append(dict(path=str(p.relative_to(out)), bytes=size, sha256=h.hexdigest()))
    print(size, h.hexdigest(), key, flush=True)
receipt = out / 'ingestion-receipt.json'
pointer = dict(schema='FRANKIE_INGEST_POINTER_V1', day=m['trading_day'], block=m['block'],
               manifest=sys.argv[1], manifest_hash=m['manifest_hash'], status=sys.argv[5], wall_seconds=int(sys.argv[6]),
               bucket=m['bucket'], prefix=prefix, files=files,
               receipt=json.loads(receipt.read_bytes()) if receipt.is_file() else None,
               runner=dict(run_id=os.environ['GITHUB_RUN_ID'], attempt=os.environ['GITHUB_RUN_ATTEMPT'],
                           commit=os.environ['GITHUB_SHA'], cpus=os.cpu_count()))
Path(sys.argv[4]).write_text(json.dumps(pointer, sort_keys=True, indent=1) + '\n')
print('pointer', sys.argv[4], 'status', sys.argv[5], 'files', len(files), 'bytes', sum(f['bytes'] for f in files))
PY
[ "$STATUS" = sealed ] || { echo "the ingest of $DAY did not seal; what it wrote is under $PREFIX"; exit 3; }
