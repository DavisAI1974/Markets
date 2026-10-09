"""Adopt a stopped ROOT's completed member-merge shards as save points, so a restart of the same Monday calculation
root on a later runtime reuses them instead of merging again.

A runtime before the merge save points (b35e79b7) wrote merge-NN.sqlite and no receipt. This writes, for each shard
that is provably complete, the receipt the current runtime looks for (frankie_box_digest_sources._saved_shard):

- the ROOT is not running (the calculation root's lock is taken here, non-blocking);
- the code version is RECORDED, NEVER COMPARED (Greg, 2026-10-09): the old runtime's merge code (every function in
  MERGE_CODE) and this checkout's are both written on the report and each receipt (a difference is listed, never
  refused); the key carries MERGE_FORMAT, bumped only when a shard's bytes change for the same layers;
- the shard is complete: _merge_shard writes a shard in ONE transaction committed at its end, so a shard with no hot
  journal, a passing quick_check and committed groups and members rows is the whole shard;
- the receipt carries the shard's bytes and sha256; reuse hashes it again.

A shard that fails any check gets no receipt and is merged again on the restart. Nothing is deleted or rewritten.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frankie_box_digest_sources as S  # noqa: E402

WORK_ROOT = Path('/opt/frankie-box/work')

OLD_CODE = r'''
import hashlib, inspect, json, sys
sys.path.insert(0, sys.argv[1])
import frankie_box_digest_sources as S
DG = S.DG
names = json.loads(sys.argv[2])
code = {}
for name in names:
    function = getattr(DG, name[3:]) if name.startswith('DG.') else getattr(S, name)
    code[name] = hashlib.sha256(inspect.getsource(function).encode()).hexdigest()
print(json.dumps(code, sort_keys=True))
'''


def old_merge_code(old_box, python=sys.executable):
    """The old runtime's merge code record, or {'unreadable': reason}: a record only, never a refusal."""
    names = sorted(S.MERGE_CODE)
    result = subprocess.run([python, '-B', '-c', OLD_CODE, str(old_box), json.dumps(names)],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        return dict(unreadable='the old runtime merge code could not be read: ' + result.stderr.strip()[-400:])
    return json.loads(result.stdout)


def shard_identity(work, layers_root):
    """The [[index, name, pinned sha256], ...] a restart computes: the derivation receipt's bedrock layers in order,
    those whose (reusable) prepared layer is keyed and derived."""
    receipt = json.loads((work / 'derive.json').read_bytes())
    entries = [(name, entry) for name, entry in receipt['layers'].items() if entry.get('bedrock')]
    identity = []
    for index, (name, pin) in enumerate(entries):
        prepared = S._reusable_prepared(index, pin, layers_root)
        if prepared is None:
            raise ValueError('layer %d (%s) has no reusable prepared receipt; a restart prepares it again' % (index, name))
        if not prepared.get('keyed'):
            raise ValueError('layer %d (%s) is not keyed; the sharded merge does not apply' % (index, name))
        if prepared['meta'].get('status') == 'derived':
            identity.append([index, name, pin.get('sha256')])
    return identity


def shard_evidence(path):
    """(complete, evidence) for one shard file, read-only."""
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        return False, dict(reason='no shard file')
    if (path.parent / (path.name + '-journal')).exists() or (path.parent / (path.name + '-wal')).exists():
        return False, dict(reason='a journal remains: the shard transaction did not finish')
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        check = [row[0] for row in db.execute('PRAGMA quick_check')]
        groups = db.execute('SELECT count(*) FROM groups').fetchone()[0]
        members = db.execute('SELECT count(*) FROM members').fetchone()[0]
    except sqlite3.DatabaseError as error:
        return False, dict(reason='unreadable: %s' % error)
    finally:
        db.close()
    evidence = dict(quick_check=check, groups=groups, members=members)
    if check != ['ok']:
        return False, dict(evidence, reason='quick_check failed')
    if not groups or not members:
        return False, dict(evidence, reason='no committed rows: the shard transaction did not commit')
    return True, evidence


def adopt(directory, digest, old_code_root, python=sys.executable):
    directory = Path(directory).resolve(strict=True)
    work = directory / 'work'
    scratch = work / 'derived' / digest
    layers = scratch / 'calculation-layers'
    if not digest.startswith('.digest-') or '/' in digest or not layers.is_dir():
        raise ValueError('DIGEST must name an existing .digest-* scratch under work/derived')
    lock = (directory / 'calculation.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError('the calculation root is locked: ROOT is still running; adopt only after it stops') from None
    try:
        old = old_merge_code(Path(old_code_root) / 'deploy/aws/box', python)
        identity = shard_identity(work, layers)
        key = S.merge_shard_key(identity)
        new = S.merge_code()
        code = dict(old_runtime=old, this_checkout=new,
                    differs=sorted(n for n in set(old) | set(new) if old.get(n) != new.get(n)))   # recorded, never compared
        shards = [layers / ('merge-%02d.sqlite' % shard) for shard in range(S.SHARDS)]
        with ThreadPoolExecutor(S.SHARDS) as pool:
            checked = list(pool.map(shard_evidence, shards))
        report = []
        for shard, (path, (complete, evidence)) in enumerate(zip(shards, checked)):
            receipt = layers / ('merge-%02d.save.json' % shard)
            if receipt.exists():
                report.append(dict(shard=shard, adopted=False, reason='a receipt already exists'))
            elif not complete:
                report.append(dict(shard=shard, adopted=False, **evidence))
            else:
                S._save_shard(layers, shard, key, path, adopted=dict(old_code_root=str(old_code_root), **evidence),
                              code=code)
                report.append(dict(shard=shard, adopted=True, **evidence))
        return dict(schema='FRANKIE_MERGE_SHARD_ADOPTION_V1', directory=str(directory), digest=digest,
                    layers=len(identity), adopted=sum(r['adopted'] for r in report), shards=report, code_record=code)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--digest', required=True)
    parser.add_argument('--old-code-root', required=True)
    args = parser.parse_args()
    directory = Path(args.directory).resolve(strict=True)
    if not directory.is_relative_to(WORK_ROOT / 'monday-calculations'):
        raise SystemExit('the calculation root must be under /opt/frankie-box/work/monday-calculations')
    if not str(Path(args.old_code_root).resolve(strict=True)).startswith('/opt/frankie-box/code/'):
        raise SystemExit('the old runtime must be a staged checkout under /opt/frankie-box/code')
    print(json.dumps(adopt(directory, args.digest, args.old_code_root), indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
