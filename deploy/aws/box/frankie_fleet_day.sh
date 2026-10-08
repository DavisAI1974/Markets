# Frankie fleet day driver (session 8, slice f / B1,B2,B3,B6). Run by the systemd unit frankie-fleet-day.service on
# EVERY boot (not once, so a stopped-and-started fleet box picks its days back up). It RESUMES this box's own,
# already-staged, box-local SAVED days; it does NOT start a fresh day from scratch. A self-driving box has no lawful
# route to its partitions (the box role reads nothing in S3 directly; the ingest fetch needs the MAP_URL presign and a
# committed plan), so a FRESH day-start is driven per instance by frankie_box_run.yml (ACTION=stage then ACTION=start
# with the FULL dispatch set -- PLAN/DAY_CLASS/CLASSROOM_ARM/BRAIN/EXTERNAL_HISTORY_RUN + the presign) with fleet mode
# on via this box's /opt/frankie-box/fleet.json. This driver's job is reboot-resume and the per-day claim only.
# It honors every exit code and never uses `|| echo`.
set -uo pipefail
LOG=/var/log/frankie-fleet-day.log
exec >>"$LOG" 2>&1
echo "frankie fleet day driver $(date -u +%Y-%m-%dT%H:%M:%SZ)"
CFG=/opt/frankie-box/fleet.json
[ -f "$CFG" ] || { echo "no $CFG; box not prepared by user-data; nothing to do"; exit 0; }
VENV=/opt/frankie-box/venv/bin/python
if [ -x "$VENV" ]; then PY="$VENV"; else PY=python3; fi      # B3: the venv python so boto3/botocore import
field() { "$PY" -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],''))" "$CFG" "$1"; }
RUN=$(field run); COMMIT=$(field commit); CODE_ROOT=$(field code_root)
[ -n "$RUN" ] && [ -n "$COMMIT" ] && [ -n "$CODE_ROOT" ] || { echo "fleet.json missing run/commit/code_root"; exit 2; }
[ -d "$CODE_ROOT" ] || { echo "staged checkout $CODE_ROOT missing; cannot resume"; exit 2; }
FLEET="$CODE_ROOT/deploy/aws/box/frankie_box_fleet.py"
QUEUE="$CODE_ROOT/deploy/aws/box/frankie_box_frankie_queue.sh"
# this box's own SAVED days for the run (the queue ledger); empty on a fresh box awaiting external dispatch
mapfile -t SAVED < <("$PY" -B "$FLEET" saved-days --run "$RUN" || true)
if [ "${#SAVED[@]}" -eq 0 ]; then
  echo "no box-local saved days for $RUN; awaiting external day-start dispatch (run.yml stage+start)"
  "$PY" -B "$FLEET" note-awaiting --run "$RUN" || true
  exit 0
fi
rc=0
for D in "${SAVED[@]}"; do
  case "$D" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) continue;; esac
  # B3: claim with an exit-code split -- 0 won / idempotent-own, 1 lost to another box (skip), >=2 error (STOP loudly)
  "$PY" -B "$FLEET" claim-day --run "$RUN" --day "$D" --stage root --commit "$COMMIT"; cc=$?
  if [ "$cc" -ge 2 ]; then echo "claim error for $D (exit $cc); stopping the driver"; exit "$cc"; fi
  if [ "$cc" -eq 1 ]; then echo "day $D is claimed by another box; skipping"; continue; fi
  # resume the saved day on the staged checkout; REBOOK=on (B4: the day re-books its CPUs fresh when it proceeds)
  if ! CODE_ROOT="$CODE_ROOT" MARKETS_SHA="$COMMIT" ACTION=resume RUN="$RUN" DAY="$D" REBOOK=on bash "$QUEUE"; then
    echo "resume $D failed (exit $?)"; rc=3; continue
  fi
  if ! CODE_ROOT="$CODE_ROOT" MARKETS_SHA="$COMMIT" ACTION=kick LINE=root SCOPE="$RUN:$D" bash "$QUEUE"; then
    echo "kick $D failed (exit $?)"; rc=3; continue
  fi
  echo "resumed+kicked $D"
done
echo "frankie fleet day driver done (rc=$rc) $(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit "$rc"
