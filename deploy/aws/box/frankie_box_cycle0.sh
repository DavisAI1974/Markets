# Monday cycle 0 on the box, through frankie_box_run.yml. ACTION=config builds the actual host configuration;
# ACTION=launch runs ONE cycle (--cycles 1 = cycle 0) with --pending-return; RESUME=1 adds --ec2-resume for the
# same run (and WAIT_SHA256 the exact retained WAIT hash). Exit 3/4 with a durable WAIT/ATTENTION is pending, not failure.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${CODE_ROOT:?staged clean checkout required}"
: "${ACTION:?config or launch}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
PYTHON=/opt/frankie-box/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
case "$ACTION" in
  config)
    : "${PREPARED:?prepared-configuration.json}"; : "${PRINCIPAL:?principal-inputs-receipt.json}"
    : "${RUN_ID:?fresh run id}"; : "${OUTPUT_ROOT:?fresh config root}"
    exec "$PYTHON" -B "$CODE_ROOT/deploy/aws/box/frankie_box_host_config.py" --prepared "$PREPARED" \
      --principal "$PRINCIPAL" --commit "$MARKETS_SHA" --run-id "$RUN_ID" --output-root "$OUTPUT_ROOT" \
      --completion-ref "${COMPLETION_REF:-claude/agent-skills-execution-tzh7sw}"
    ;;
  launch)
    : "${CONFIGURATION:?actual host configuration}"
    set -- --configuration "$CONFIGURATION" --compact-source-tools "$CODE_ROOT" --cycles 1 --pending-return
    [ "${RESUME:-0}" = 1 ] && set -- "$@" --ec2-resume
    [ -n "${WAIT_SHA256:-}" ] && set -- "$@" --resume-wait-sha256 "$WAIT_SHA256"
    cd "$CODE_ROOT"
    set +e
    "$PYTHON" -B "$CODE_ROOT/research/kalshi/frankie_boss/operations/run_actual_sunday_ec2.py" "$@"
    code=$?
    echo "CYCLE0_EXIT $code"
    exit $code
    ;;
  *) echo "ACTION must be config or launch" >&2; exit 2;;
esac
