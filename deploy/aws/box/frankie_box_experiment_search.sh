# The experiment's search, first slice (frankie_box_experiment_search.py): series on one causal axis per day from the
# exported day data, the leakage gate on every source's real alignment, and sign-step couplings with the circular-shift
# chance check, as counts per pair, cell, lag and day. One day per run; never pooled; no model call.
# Inputs: CODE_ROOT (staged checkout), DAY (YYYYMMDD), CYCLE (NN), DAY_ROLE (discovery | confirmation; confirmation needs
# FROZEN_SURVIVORS), LAGS (default 20), WORKERS (default 8), TRANSFORMS (comma list; default all of
# frankie_box_experiment_transforms.TRANSFORMS). Output: /opt/frankie-box/work/experiment-search/<day>/
# cycle-<NN>/<role>/ (MANIFEST + couplings/*.jsonl). Needs duckdb 1.5.5 + its bundled extensions and pyarrow in the venv.
# A probe: frankie_box_progress.sh DIRECTORY=/opt/frankie-box/work/experiment-search/<day>.
set -eu
export HOME="${HOME:-/root}"   # SSM runs without HOME; DuckDB refuses to load extensions without a home directory (2026-09-29)
: "${MARKETS_SHA:?full dispatched commit required}"; : "${CODE_ROOT:?staged clean checkout required}"
: "${DAY:?YYYYMMDD required}"; : "${CYCLE:?cycle required}"; : "${DAY_ROLE:?discovery or confirmation required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
[ "$(git -C "$CODE_ROOT" rev-parse HEAD)" = "$MARKETS_SHA" ] || { echo "staged checkout differs from MARKETS_SHA" >&2; exit 2; }
/opt/frankie-box/venv/bin/python -c 'import duckdb, pyarrow' 2>/dev/null || { echo "duckdb and pyarrow are not in the box venv (install on Greg's go)" >&2; exit 3; }
set -- --day "$DAY" --cycle "$CYCLE" --day-role "$DAY_ROLE" --lags "${LAGS:-20}" --workers "${WORKERS:-8}"
[ -z "${FROZEN_SURVIVORS:-}" ] || set -- "$@" --frozen-survivors "$FROZEN_SURVIVORS"
[ -z "${TRANSFORMS:-}" ] || set -- "$@" --transforms "$TRANSFORMS"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
exec nice -n 10 /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_experiment_search.py" "$@"
