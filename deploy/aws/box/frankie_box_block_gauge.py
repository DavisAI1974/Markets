#!/usr/bin/env python3
"""The block-1 gauge (Greg, 2026-10-09: "we're running the 1st 5 min again and again right so we have a good gauge"):
the first 5 minutes of the day (sealed block 1) run through the whole classroom session on the CURRENT code, into a
gauge directory named by the code commit, never touching the day's real classroom outputs. One number per code version:
the session seconds, with the per-step seconds beside it. Same functions, same data, same science; only the code changes.

    python3 deploy/aws/box/frankie_box_block_gauge.py --rows-dir <teacher rows dir> --ingest-dir <ingest dir> \
        --day 20231018 --out /opt/frankie-box/work/gauge-block1 [--block 1] [--brain <brain>]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--rows-dir', required=True)
    p.add_argument('--ingest-dir', required=True)
    p.add_argument('--day', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--block', type=int, default=1)
    p.add_argument('--brain', default=None)
    a = p.parse_args()
    import frankie_box_classroom_code as K
    import frankie_box_experiment as X
    commit = subprocess.run(['git', '-C', str(HERE.parents[2]), 'rev-parse', '--short=8', 'HEAD'], capture_output=True,
                            text=True).stdout.strip() or 'unknown'
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    out = Path(a.out) / ('%s-%s' % (commit, stamp))
    out.mkdir(parents=True, exist_ok=True)
    day_file, day_sha = X.attached_day_file(Path(a.ingest_dir))[:2]
    brain = a.brain or str(X.BRAIN)
    began = time.monotonic()
    record = K.block_work(a.rows_dir, out, a.block, a.day, brain, None, day_file, day_sha)
    wall = round(time.monotonic() - began, 3)
    session = json.load(open(out / 'blocks' / str(a.block) / 'session.json'))
    steps = session.get('steps') or {}
    result = dict(schema='FRANKIE_BLOCK_GAUGE_V1', commit=commit, at_utc=stamp, day=a.day, block=a.block,
                  rows=session.get('rows'), status=session.get('status'), wall_seconds=wall,
                  session_seconds=session.get('seconds'), lesson_seconds=session.get('lesson_seconds'),
                  steps=dict(sorted(steps.items(), key=lambda kv: -kv[1])), work=record, out=str(out))
    (out / 'gauge.json').write_text(json.dumps(result, indent=1, default=str) + '\n')
    line = dict(commit=commit, at_utc=stamp, block=a.block, rows=result['rows'], status=result['status'],
                wall=wall, session=result['session_seconds'])
    with (Path(a.out) / 'gauge.jsonl').open('a') as handle:
        handle.write(json.dumps(line) + '\n')
    print('BLOCK_GAUGE ' + json.dumps(line))
    print('STEPS ' + json.dumps({k: round(v, 1) for k, v in result['steps'].items() if v >= 0.5}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
