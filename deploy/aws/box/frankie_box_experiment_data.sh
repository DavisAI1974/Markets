# One day and cycle's data from the ROOT, CONFIG and CYCLE processes, hard-linked for the experiment's teachers
# (Greg, 2026-09-29: "we forgot root in the experiment"; "fix gaps"). frankie_box_experiment_data.py holds the catalog:
# every file is INCLUDED (data or receipt), EXCLUDED with its reason (Frankie's reasoning R09, grades R10, bedrock, mixed,
# other models), MISSING (a stage that never got that far) or UNCLAIMED (listed with bytes). Hard links only; nothing is
# recomputed or copied; the same day and cycle is exported once (duplicate data declines the run).
# ACTION=plan (read-only: prints what would be linked, excluded, missing and unclaimed) or ACTION=export.
# Inputs: CODE_ROOT (staged checkout), DAY (YYYYMMDD), CYCLE (NN), CALCULATIONS (the ROOT, e.g.
# /opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48), and as far as they exist: INGEST (the ingest
# directory holding journal.compact.sqlite), LAUNCH (the monday-launch authorship directory), PREPARATION
# (trading-day-preparation/<r>), PRINCIPAL_INPUTS (principal-inputs/<r>), HOST_CONFIG (monday-run-config/<r>), RUN (ONE
# runs/<run_id>). A directory not given is listed as missing, never guessed.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${DAY:?YYYYMMDD required}"; : "${CYCLE:?cycle required}"; : "${CALCULATIONS:?the ROOT calculations directory required}"
ACTION="${ACTION:-plan}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
set -- --day "$DAY" --cycle "$CYCLE" --calculations "$CALCULATIONS"
[ -z "${INGEST:-}" ] || set -- "$@" --ingest "$INGEST"
[ -z "${LAUNCH:-}" ] || set -- "$@" --authorship "$LAUNCH"
[ -z "${PREPARATION:-}" ] || set -- "$@" --preparation "$PREPARATION"
[ -z "${PRINCIPAL_INPUTS:-}" ] || set -- "$@" --principal-inputs "$PRINCIPAL_INPUTS"
[ -z "${HOST_CONFIG:-}" ] || set -- "$@" --host-config "$HOST_CONFIG"
[ -z "${RUN:-}" ] || set -- "$@" --run "$RUN"
[ -z "${TEACHER:-}" ] || set -- "$@" --teacher "$TEACHER"
# WORKERS (default 1; DATA_WORKERS accepted as the orchestrator's name for it): processes hashing the linked files side
# by side; the orchestrator starts this step under its booked 16 CPUs and may give 15. The pins (bytes, sha256) are
# identical whatever the count.
WORKERS="${WORKERS:-${DATA_WORKERS:-1}}"
case "$WORKERS" in *[!0-9]*|0) echo "WORKERS must be a positive integer" >&2; exit 2;; esac
set -- "$@" --workers "$WORKERS"
case "$ACTION" in plan) set -- "$@" --plan-only;; export) ;; *) echo "ACTION must be plan or export" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec nice -n 10 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment_data.py" "$@"
