# The box side of the Pod ROOT path (SPEC-pod-day-runner.md). Called over SSM by the runner-side controller
# research/kalshi/frankie_boss/pod_root/controller.py (frankie_box_run.yml script=deploy/aws/box/frankie_box_pod_root_loop.sh), not by hand; every action prints
# one line POD_ROOT_RESULT <json>.
# On the MAIN box (i-035994afa8bdf66a5), with CODE_ROOT = a staged clean checkout that holds frankie_box_pod_root.py:
#   ACTION=enable                          create the ROOT claim store /opt/frankie-box/work/root-claims (from then on the
#                                          orchestrator's root stage claims each day before its ROOT)
#   ACTION=queue   RUN                     read-only: each day of the run's saved plan with its state (ready = sealed ingest
#                                          + day file attached + no ROOT + no claim)
#   ACTION=claim   RUN DAY WHERE [COMMIT]  the gate re-checked, then the create-only claim
#   ACTION=export  RUN DAY WHERE ATTEMPT FILES MAP_URL   the named ingest files to presigned PUT slots (read-only on the ingest)
#   ACTION=import  RUN DAY WHERE ATTEMPT MAP_URL [DISK_FLOOR_GB]  the Pod's ROOT streamed in, every file sha256-checked, then
#                                          renamed whole into /opt/frankie-box/work/experiment-roots/<ATTEMPT>
#   ACTION=release RUN DAY WHERE ATTEMPT REASON   the claim renamed aside (never deleted)
#   ACTION=status  [RUN]                   read-only: claims and import receipts
# On a WORKER box (the twin, i-08cee), with COMMIT = the ROOT's commit (a worktree /opt/frankie-box/code/<COMMIT>-pod-1/markets
# is made from /opt/frankie-box/markets, which frankie_box_worker_setup.sh cloned):
#   ACTION=work MAP_URL (its "job")  |  ACTION=jobs  |  ACTION=clean JOB [VERIFIED]  |  ACTION=reupload JOB MAP_URL
# SSM runs this under sh: POSIX only. No model call; no S3 write of its own (presigned slots only).
set -eu
ROOT=/opt/frankie-box; PY="$ROOT/venv/bin/python"
: "${ACTION:?ACTION required}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 HOME="${HOME:-/root}" PROTOCOL=1 GIT_TERMINAL_PROMPT=0
export ACTION RUN="${RUN:-}" DAY="${DAY:-}" WHERE="${WHERE:-}" ATTEMPT="${ATTEMPT:-}" FILES="${FILES:-}" MAP_URL="${MAP_URL:-}"
export REASON="${REASON:-}" COMMIT="${COMMIT:-}" DISK_FLOOR_GB="${DISK_FLOOR_GB:-100}" JOB="${JOB:-}" VERIFIED="${VERIFIED:-}"
case "$RUN$DAY$WHERE$ATTEMPT$FILES$JOB" in *..*|*/*) echo "no .. or / in RUN DAY WHERE ATTEMPT FILES JOB" >&2; exit 2;; esac
case "$ACTION" in
  enable|queue|claim|export|import|release|status|coordinate)
    : "${CODE_ROOT:?CODE_ROOT (a staged checkout under /opt/frankie-box/code) required}"
    case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
    [ -f "$CODE_ROOT/deploy/aws/box/frankie_box_pod_root.py" ] || { echo "$CODE_ROOT holds no frankie_box_pod_root.py: stage a commit that has it" >&2; exit 2; }
    [ -z "$(git -C "$CODE_ROOT" status --porcelain --untracked-files=no)" ] || { echo "$CODE_ROOT has tracked changes" >&2; exit 2; }
    echo "code root $CODE_ROOT at $(git -C "$CODE_ROOT" rev-parse HEAD)"
    export PYTHONPATH="$CODE_ROOT" CODE_COMMIT="$(git -C "$CODE_ROOT" rev-parse HEAD)"
    exec nice -n 5 "$PY" -B "$CODE_ROOT/deploy/aws/box/frankie_box_pod_root.py" ;;
  work|jobs|clean|reupload|renew|resume)
    : "${COMMIT:?COMMIT (full ROOT commit) required}"
    case "$COMMIT" in *[!0-9a-f]*) echo "COMMIT must be a full hex commit" >&2; exit 2;; esac
    [ "${#COMMIT}" -eq 40 ] || { echo "COMMIT must be 40 hex characters" >&2; exit 2; }
    CODE="$ROOT/code/$COMMIT-pod-1/markets"
    if [ ! -e "$CODE/.git" ]; then
      [ -d "$ROOT/markets/.git" ] || { echo "no $ROOT/markets: run frankie_box_worker_setup.sh on this box first" >&2; exit 2; }
      git -C "$ROOT/markets" fetch -q --depth 1 origin -- "$COMMIT"
      mkdir -p "$ROOT/code/$COMMIT-pod-1"
      git -C "$ROOT/markets" worktree add -q --detach "$CODE" "$COMMIT"
    fi
    [ "$(git -C "$CODE" rev-parse HEAD)" = "$COMMIT" ] || { echo "$CODE is not at $COMMIT" >&2; exit 2; }
    [ -d "$ROOT/producers/.git" ] || git clone -q --depth 1 --branch ccode/frankie-receiver-feed-20260916 https://github.com/DavisAI1974/Markets.git "$ROOT/producers"
    mkdir -p "$ROOT/pod-agent"; cd "$ROOT/pod-agent"
    export PYTHONPATH="$CODE" POD_SLOTS="${POD_SLOTS:-1}"
    exec "$PY" -B "$CODE/research/kalshi/frankie_boss/pod_root/pod_agent.py" "$ACTION" ;;
  *) echo "unknown ACTION $ACTION" >&2; exit 2;;
esac
