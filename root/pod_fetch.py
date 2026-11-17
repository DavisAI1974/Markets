"""ROOT part 2: fetch what a pod made, and prove it before it is stored (the session's side of `root/pod.py`).

For each named calculation (or the chain link models) of one trade day: the receipt is fetched from the pod, then
every file the receipt lists, and each file's size and fingerprint are compared with the receipt's. The pod must
have run the expected code commit on the same stored rows as the local copy. Only then are the files written into
the local folder of that trade day's `root-rows` branch. A file that differs stops everything and nothing of that
calculation is kept (Greg: bad or incomplete data is not saved).

    python3 -m root.pod_fetch https://<pod id>-8000.proxy.runpod.net 20231002 <commit> --into <rows folder> \
        refills sweeps chain_peaks [models]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

MODELS = 'models'
AGENT = 'curl/8'                                       # the pods' web front refuses the library's own name
BYTES_PER_MEGABYTE = 2 ** 20


def get(base: str, name: str) -> bytes:
    ask = urllib.request.Request(f'{base.rstrip("/")}/{name}', headers={'User-Agent': AGENT})
    with urllib.request.urlopen(ask) as answer:
        return answer.read()


def fetch(base: str, day: str, commit: str, into: Path, names: list) -> dict:
    ran = get(base, 'CODE_COMMIT').decode().strip()
    if ran != commit:
        raise SystemExit(f'the pod last ran commit {ran}, not {commit}')
    rows_here = subprocess.run(['git', '-C', str(into), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                               check=True).stdout.strip()
    rows_there = get(base, 'ROWS_COMMIT').decode().strip()
    if rows_there != rows_here:
        raise SystemExit(f'the pod ran on stored rows {rows_there}; the local copy is {rows_here}')
    status = get(base, 'STATUS').decode()
    out = {}
    for name in names:
        ran_as = 'chain_models' if name == MODELS else name
        if f'{ran_as} passed' not in status or f'{ran_as} FAILED' in status.split(f'{ran_as} passed')[-1]:
            raise SystemExit(f'{name}: the pod does not say it passed (or it failed after it last passed)')
        receipt_name = f'CHAIN-MODELS-{day}.json' if name == MODELS else f'CALC-{name}-{day}.json'
        raw = get(base, receipt_name)
        receipt = json.loads(raw)
        listed = list(receipt['files']) + [f for t in receipt.get('tables', {}).values() for f in t['files']]
        held = {}
        for f in listed:
            held[f['file']] = get(base, f['file'])
            if len(held[f['file']]) != f['bytes'] or hashlib.sha256(held[f['file']]).hexdigest() != f['sha256']:
                raise SystemExit(f'{f["file"]}: not the file its receipt describes; nothing of {name} is kept')
        for file_name, content in held.items():
            (into / file_name).write_bytes(content)
        (into / receipt_name).write_bytes(raw)
        out[name] = dict(receipt=receipt_name, files=len(held), megabytes=round(sum(map(len, held.values())) / BYTES_PER_MEGABYTE, 1))
    return out


def main():
    ap = argparse.ArgumentParser(description='fetch and prove what a pod made')
    ap.add_argument('base')
    ap.add_argument('trade_day')
    ap.add_argument('commit')
    ap.add_argument('--into', type=Path, required=True, help='the local folder of that trade day\'s root-rows branch')
    ap.add_argument('names', nargs='+')
    a = ap.parse_args()
    print(json.dumps(fetch(a.base, a.trade_day, a.commit, a.into, a.names), indent=1))


if __name__ == '__main__':
    main()
