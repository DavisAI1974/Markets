# Canary for the parallel journal walk (Greg, 2026-09-28: "We have to fix that 1 cpu problem"). Read-only.
# Opens the SAME compact prefix snapshot a launch reads (its cycle directory's host-prefix.c15.json), runs
# research/kalshi/frankie_boss/parallel_journal.parallel_journal_prefix over it on WORKERS CPUs (default 16, so a running
# launch keeps its core), and prints: wall seconds, payloads yielded, whether they are exactly cursors 0..cutoff in order,
# and the summary (journal_prefix_hash, journal_entries). Compare those with the launch's own serial receipt,
# host-context-cache.c15.json (printed too when it exists). Inputs: CODE_ROOT (staged commit), RUN (run directory),
# WORKERS. Writes nothing.
set -eu
: "${CODE_ROOT:?staged checkout required}"; : "${RUN:?run directory required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$RUN" in /opt/frankie-box/work/runs/*) ;; *) echo "RUN must be under /opt/frankie-box/work/runs" >&2; exit 2;; esac
export RUN WORKERS="${WORKERS:-16}" PYTHONPATH="$CODE_ROOT" PYTHONDONTWRITEBYTECODE=1
cd "$CODE_ROOT"
# spawned workers re-import the main module, so the canary runs from a file, never from stdin
SCRIPT=$(mktemp /tmp/parallel-journal-canary-XXXXXX.py)
cat > "$SCRIPT" <<'PY'
import json, os, time
from pathlib import Path
from types import SimpleNamespace
from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
from research.kalshi.frankie_boss.parallel_journal import parallel_journal_prefix
from research.kalshi.frankie_boss.c15_journal import unpack


def load(path):
    value = json.loads(Path(path).read_bytes())
    return unpack(value) if isinstance(value, list) else value   # c15 driver files are tagged

def main():
    run = Path(os.environ['RUN'])
    witnesses = sorted(run.rglob('host-prefix.c15.json'))
    if not witnesses:
        raise SystemExit('no host-prefix.c15.json under ' + str(run))
    files = load(witnesses[0])['files']
    receipt = load(files['receipt']['path'])
    print('snapshot', files['snapshot']['path'], 'journal_count', receipt['journal_count'], 'records', receipt['records_in_prefix'], flush=True)
    reader = FrankieCompactReader(files['snapshot']['path'], expected_count=receipt['journal_count'],
                                  expected_head_hash=receipt['journal_head_hash'], workers=int(os.environ['WORKERS']))
    builder = SimpleNamespace(_failed=False, chain=SimpleNamespace(next_cursor=receipt['records_in_prefix']), journal=reader)
    cutoff = receipt['records_in_prefix'] - 1
    summary, count, ordered, started = {}, 0, True, time.time()
    for payload in parallel_journal_prefix(builder, cutoff, summary):
        ordered = ordered and payload['cursor'] == count
        count += 1
        if count % 200000 == 0:
            print('... %d payloads, %.0f s' % (count, time.time() - started), flush=True)
    wall = time.time() - started
    result = dict(schema='FRANKIE_PARALLEL_JOURNAL_CANARY_V1', wall_seconds=round(wall, 1), workers=len(reader.worker_cpus),
                  payloads=count, expected_payloads=cutoff + 1, cursors_in_order=ordered and count == cutoff + 1,
                  summary=summary, worker_cpu_seconds=round(reader.worker_cpu_seconds, 1))
    serial = sorted(run.rglob('host-context-cache.c15.json'))
    if serial:
        value = load(serial[0])
        result['serial_receipt'] = {k: value.get(k) for k in ('journal_prefix_hash', 'journal_entries', 'input_hash', 'consumed_rows')}
        result['summary_matches_serial'] = (value.get('journal_prefix_hash') == summary.get('journal_prefix_hash')
                                            and value.get('journal_entries') == summary.get('journal_entries'))
    print('CANARY ' + json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
PY
exec nice -n 5 /opt/frankie-box/venv/bin/python -B "$SCRIPT"
