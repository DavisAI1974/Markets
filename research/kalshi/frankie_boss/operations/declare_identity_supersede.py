"""Declare that a cycle's saved binding may be superseded by the current code identity (2026-09-20).

A host code advance while a cycle is open changes `training_identities.code_hash` (the hash of every
source file) and nothing else; the cycle coordinator then refuses `cycle request identity changed`
(feedback_cycle.run). This helper is the operator's explicit declaration that the coordinator's
`_binding_supersede` requires: it reads the OLD code_hash from the coordinator's saved binding
(read-only), computes the CURRENT code identity exactly as run_actual_sunday.ActualHost does
(every .py under research/kalshi/frankie_boss and research/refrag except tests, plus the host
script under 'host_script'), and appends `{request_id, old_code_hash, new_code_hash, reason}` to
<run_directory>/cycles.sqlite.identity-supersede.json with a receipt beside the day's receipts.
It writes nothing else, never touches the cycle store, and declares nothing when the identity is
not stale.

    python declare_identity_supersede.py --run-directory DIR --tools-root REPO --request-id ID
        --reason TEXT --receipt-directory DIR
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

from research.kalshi.frankie_boss.c15_journal import evidence_hash, unpack

SCHEMA = 'FRANKIE_CYCLE_IDENTITY_SUPERSEDE_DECLARED_V1'
DECLARATION_SUFFIX = '.identity-supersede.json'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def code_identity(repo):
    """The map run_actual_sunday.ActualHost hashes into identities.code_hash, and that hash."""
    repo = Path(repo)
    code = {str(p.relative_to(repo)): sha(p) for root in ('research/kalshi/frankie_boss', 'research/refrag')
            for p in sorted((repo / root).rglob('*.py')) if 'tests' not in p.parts}
    code['host_script'] = sha(repo / 'research/kalshi/frankie_boss/operations/run_actual_sunday.py')
    return code, evidence_hash(code)


def saved_code_hash(cycles_path, request_id):
    connection = sqlite3.connect(Path(cycles_path).as_uri() + '?mode=ro', uri=True)
    try:
        row = connection.execute('SELECT payload, digest FROM stages WHERE request=? AND stage=?',
                                 (request_id, 'binding')).fetchone()
    finally:
        connection.close()
    if row is None:
        raise SystemExit('no saved binding for ' + request_id)
    value = unpack(json.loads(row[0]))
    if evidence_hash(value) != row[1]:
        raise SystemExit('saved binding digest differs')
    return value['training_identities']['code_hash']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--run-directory', required=True)
    parser.add_argument('--tools-root', required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--reason', required=True)
    parser.add_argument('--receipt-directory', required=True)
    args = parser.parse_args(argv)
    run = Path(args.run_directory)
    cycles = run / 'cycles.sqlite'
    if not cycles.exists():
        raise SystemExit('cycle store missing: ' + str(cycles))
    old = saved_code_hash(cycles, args.request_id)
    _, new = code_identity(args.tools_root)
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    declaration = Path(str(cycles) + DECLARATION_SUFFIX)
    entries = json.loads(declaration.read_bytes()) if declaration.exists() else []
    entry = dict(schema=SCHEMA, request_id=args.request_id, old_code_hash=old, new_code_hash=new,
                 reason=args.reason, declared_at=stamp)
    status = 'not_stale' if old == new else ('already_declared' if any(
        e.get('request_id') == args.request_id and e.get('old_code_hash') == old and e.get('new_code_hash') == new
        for e in entries) else 'declared')
    if status == 'declared':
        entries.append(entry)
        declaration.write_bytes(json.dumps(entries, sort_keys=True, indent=1).encode())
    receipt = dict(schema=SCHEMA + '_RECEIPT', status=status, request_id=args.request_id, old_code_hash=old,
                   new_code_hash=new, declaration=str(declaration), reason=args.reason, at=stamp)
    receipt_path = Path(args.receipt_directory) / ('identity-supersede-declared-' + stamp + '.json')
    receipt_path.write_bytes(json.dumps(receipt, sort_keys=True, indent=1).encode())
    print('RECEIPT ' + json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
