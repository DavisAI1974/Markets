# Job 0 step 2 (verification): diagnose and run the producers' own tests on Frankie's box.
# The staging run collected 8 errors and pytest stopped before any test ran; this prints the first tracebacks
# (dependency or path errors are the usual cause), then re-runs the suite with --continue-on-collection-errors
# so the tests that do collect actually run, and records the counts. Read-only except the log and one receipt.
# Optional input: EXTRA_PIP (space-separated extra packages to install into the venv before the run; default none).
set -u
ROOT=/opt/frankie-box
PY="$ROOT/venv/bin/python"
[ -x "$PY" ] || { echo "no venv at $ROOT/venv (run frankie_box_stage_producers.sh first)"; exit 2; }
export PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
mkdir -p "$ROOT/logs" "$ROOT/receipts"
if [ -n "${EXTRA_PIP:-}" ]; then
  echo "### extra packages: $EXTRA_PIP"
  # shellcheck disable=SC2086
  "$PY" -m pip install -q $EXTRA_PIP >>"$ROOT/logs/pip.log" 2>&1 || { echo "pip install failed"; tail -5 "$ROOT/logs/pip.log"; }
fi
cd "$ROOT/producers" || exit 2
echo "### collection errors (first 2 tracebacks, trimmed)"
timeout 600 "$PY" -m pytest -q -p no:cacheprovider --collect-only research/kalshi/frankie_raw_mbo_benchmark/tests >"$ROOT/logs/producer-collect.log" 2>&1
grep -nE "^(E  |ERROR|ModuleNotFoundError|ImportError|_+ ERROR collecting)" "$ROOT/logs/producer-collect.log" | head -40
echo "### distinct missing modules"
grep -oE "No module named '[^']+'" "$ROOT/logs/producer-collect.log" | sort | uniq -c
echo "### full run (continue past collection errors; capped 25 min)"
timeout 1500 "$PY" -m pytest -q -p no:cacheprovider --continue-on-collection-errors research/kalshi/frankie_raw_mbo_benchmark/tests research/test_ng_exhaustion_mbo_v4_state_adapter_20260820.py >"$ROOT/logs/producer-tests.log" 2>&1
code=$?
tail -4 "$ROOT/logs/producer-tests.log"; echo "pytest exit $code"
echo "### failures (first 30)"
grep -E "^(FAILED|ERROR) " "$ROOT/logs/producer-tests.log" | head -30
summary=$(tail -1 "$ROOT/logs/producer-tests.log" | tr -d '"')
printf '{"schema":"FRANKIE_BOX_PRODUCER_TESTS_RECEIPT_V1","at":%s,"pytest_exit":%s,"summary":"%s","log":"%s/logs/producer-tests.log","collect_log":"%s/logs/producer-collect.log"}\n' "$(date +%s)" "$code" "$summary" "$ROOT" "$ROOT" > "$ROOT/receipts/producer-tests-$(date +%s).json"
echo "### done"
