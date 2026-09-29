# Move a SEALED ingest day off a box into S3, verified, so the box's space can be reused (Greg, 2026-09-29: "as box space
# opens up, clean trash and move important data to S3 before the space is refilled"; first targets the twin
# i-0d17573dbce871520's 20250930 and 20251001). The box's role writes nothing in S3: every object goes through a presigned
# PUT slot of the dispatch's private map (MAP_URL). Dispatched through frankie_box_run.yml, one directory per dispatch:
#   ACTION=plan    DIRECTORY=/opt/frankie-box/work/ingest-<day>-<name>   (no presign) read-only: every file with bytes and
#                  sha256, the layout, and the EXACT presign string of the upload (PRESIGN putarchive:..:<N> getprefix:..)
#   ACTION=upload  DIRECTORY=...  presign=<the plan's PRESIGN line>  every piece PUT, hashed as sent, equal to the plan's;
#                  the archive manifest last (a re-dispatch resumes: objects already there are proven by GET, never rewritten)
#   ACTION=verify  DIRECTORY=...  presign="getprefix:bento-568968024170-us-east-2-an/frankie/ingest/<day>/box-<name>/"
#                  every object read back and sha256-compared with the manifest, per piece and per file
#   ACTION=restore DIRECTORY=...  (same getprefix) the read path: the day rebuilt at DIRECTORY (create-only), every sha256
#                  checked; refused when DIRECTORY exists or the day already has a sealed ingest on the box
# Optional: PARALLEL (pieces or files side by side, default 4), ALLOW_UNCONFORMED=1 (a deferred conformance not run yet).
# Layout and refusals: frankie_box_archive_day.py. Receipts: /opt/frankie-box/receipts/archive-<day>-<utc>.json.
# NO DELETE ACTION: the local directory stays until Greg says otherwise (a separate later step). Nothing overwritten; no
# model call, no Databento, no key. CPU and I/O light (nice 10, idle-leaning I/O): a running ingest keeps priority.
# The code runs from a worktree of the dispatched commit (MARKETS_SHA), made the way the ingest wrapper makes it.
# SSM runs this under sh: POSIX only.
set -u
ROOT=/opt/frankie-box; ACTION="${ACTION:-plan}"; DIRECTORY="${DIRECTORY:-}"; PARALLEL="${PARALLEL:-4}"
MARKETS_SHA="${MARKETS_SHA:-}"; ALLOW_UNCONFORMED="${ALLOW_UNCONFORMED:-}"
case "$ACTION" in plan|upload|verify|restore) ;; *) echo "ACTION must be plan, upload, verify or restore (there is no delete)"; exit 2;; esac
case "$DIRECTORY" in "$ROOT"/work/ingest-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-*) ;; *) echo "DIRECTORY must be $ROOT/work/ingest-<YYYYMMDD>-<name>"; exit 2;; esac
case "${DIRECTORY#"$ROOT"/work/}" in *..*|*/*|*[!A-Za-z0-9_-]*) echo "DIRECTORY names one ingest directory directly under $ROOT/work ([A-Za-z0-9_-] only)"; exit 2;; esac
case "$PARALLEL" in ""|*[!0-9]*|0) echo "PARALLEL must be a positive integer"; exit 2;; esac
[ "$PARALLEL" -le 16 ] || { echo "PARALLEL is at most 16"; exit 2; }
case "$ALLOW_UNCONFORMED" in ""|1) ;; *) echo "ALLOW_UNCONFORMED must be 1 or unset"; exit 2;; esac
case "$MARKETS_SHA" in ""|*[!0-9a-f]*) echo "MARKETS_SHA must be the dispatched commit (frankie_box_run.yml sets it from GITHUB_SHA)"; exit 2;; esac
[ "${#MARKETS_SHA}" -eq 40 ] || { echo "MARKETS_SHA must be the full 40-hex commit"; exit 2; }
case "$ACTION" in plan) ;; *) [ -n "${MAP_URL:-}" ] || { echo "ACTION=$ACTION needs the dispatch's presign (MAP_URL)"; exit 2; };; esac
PY="$ROOT/venv/bin/python"; [ -x "$PY" ] || PY=python3
mkdir -p "$ROOT/ingest-code" "$ROOT/tmp" "$ROOT/receipts"
MK="$ROOT/ingest-code/$MARKETS_SHA"
( flock 9
  if [ ! -e "$MK/.git" ]; then
    git -C "$ROOT/markets" fetch -q --depth 1 origin -- "$MARKETS_SHA" || { echo "markets fetch of $MARKETS_SHA failed"; exit 2; }
    git -C "$ROOT/markets" worktree add -q --detach "$MK" "$MARKETS_SHA" || { echo "worktree for $MARKETS_SHA failed"; exit 2; }
  fi ) 9>"$ROOT/tmp/ingest-code.lock" || exit 2
[ "$(git -C "$MK" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "the worktree HEAD differs from the dispatched commit; refused"; exit 2; }
[ -f "$MK/deploy/aws/box/frankie_box_archive_day.py" ] || { echo "the dispatched commit holds no frankie_box_archive_day.py"; exit 2; }
echo "markets worktree $MK (the dispatched commit)"
export ACTION DIRECTORY PARALLEL MARKETS_SHA ALLOW_UNCONFORMED MAP_URL="${MAP_URL:-}" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
nice -n 10 ionice -c2 -n7 "$PY" -B "$MK/deploy/aws/box/frankie_box_archive_day.py"
RC=$?
echo "### free after: $(df -B1 --output=avail "$ROOT" | tail -1) bytes"
exit $RC
