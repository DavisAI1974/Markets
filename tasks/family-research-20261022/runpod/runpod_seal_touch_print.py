"""Run the decision step once from sealed inputs; caller holds standalone.lock."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(actual, expected, label):
    if actual != expected:
        raise ValueError(f'{label}: {actual!r} != {expected!r}')


def seal(day, source, target, runner):
    source, target, runner = source.resolve(), target.resolve(), runner.resolve()
    source_receipt = json.loads((source.parent / 'receipt.json').read_bytes())
    require(source_receipt['session'], day, 'session')
    saved = source_receipt['groups_file']
    require(saved['path'], source.name, 'groups file')
    require(source.stat().st_size, saved['bytes'], 'groups bytes')
    identity = dict(trade_date=day, input=str(source), input_groups=saved,
                    runner_sha256=digest(runner))
    if target.exists():
        retained = json.loads((target / 'receipt.json').read_bytes())
        for key, value in identity.items():
            require(retained[key], value, key)
        require(retained['status'], 'touch-print-decisions-sealed', 'status')
        require((target / 'decisions.jsonl.gz').stat().st_size,
                retained['output']['bytes'], 'decision bytes')
        return retained

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'.{day}-decisions-', dir=target.parent) as work:
        pending = Path(work)
        output = pending / 'decisions.jsonl.gz'
        run = subprocess.run([sys.executable, '-B', str(runner), '--day', day,
                              '--input', str(source), '--output', str(output)],
                             check=True, stdout=subprocess.PIPE, text=True)
        summary = json.loads(run.stdout)
        require(summary['trade_date'], day, 'decision date')
        for key in ('groups', 'prints'):
            require(summary['counts'].get(f'source_{key}', 0), source_receipt['counts'][key],
                    f'source_{key}')
        result = dict(identity, status='touch-print-decisions-sealed', summary=summary,
                      decision_rows=sum(row[-1] for row in summary['dispositions']),
                      output=dict(path=output.name, bytes=output.stat().st_size, sha256=digest(output)))
        (pending / 'receipt.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        pending.rename(target)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--day', required=True, choices=('20231002', '20231003', '20231017', '20231018'))
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='Atomic result directory')
    parser.add_argument('--runner', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(seal(args.day, args.input, args.output, args.runner), indent=2))
