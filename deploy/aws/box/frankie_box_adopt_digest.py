"""Adopt a STOPPED ROOT's finished digest work as save points, so the restarted ROOT only assembles the document.

Adopted (receipts the current runtime looks up; nothing rewritten or deleted):
- work/derived/<DIGEST>/calculation-layers/sources.sqlite: finished (the bedrock tables had started, so preparation,
  merge, copy-in and the run/layer rows were committed) and no journal left: sources.save.json (bytes, mtime, sha256).
- the five legacy tables table-0000..0004 in <DIGEST>: each was inverse-proven before the next began, and the bedrock
  stage only starts after all five, so a started bedrock stage proves them: table-NNNN.save.json with the legacy key
  (name, context names, TABLE_FORMAT, legacy layer sha256s from work/derive.json) and the context database witness.

Refused unless: the calculation root lock is free (ROOT stopped). The code version is RECORDED, NEVER COMPARED (Greg,
2026-10-09): the old runtime's table and sources code and this checkout's are both written on the adoption report and
on each receipt (a difference is listed, never refused); the keys carry the format integers (TABLE_FORMAT,
SOURCES_FORMAT), bumped only when the saved bytes' format changes.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frankie_box_digest_document as D  # noqa: E402
import frankie_box_digest_parallel as P  # noqa: E402

LEGACY = (('legacy_price', ()), ('per_second_flow_and_roll20', ()), ('legacy_book_imbalance', ()),
          ('legacy_structure_observables', ('legacy_book_imbalance',)), ('structure_families', ()))

OLD_CODE = r'''
import hashlib, inspect, json, sys
sys.path.insert(0, sys.argv[1])
import frankie_box_digest_sources as S
import frankie_box_digest_document as D
from pathlib import Path
out = {}
for name in ('frankie_box_digest_stream.py', 'frankie_box_digest_render.py'):
    out[name] = hashlib.sha256((Path(sys.argv[1]) / name).read_bytes()).hexdigest()
names = {'sources._Rows': S._Rows, 'sources._Members': S._Members, 'sources._decoded': S._decoded,
         'sources._compare_groups': S._compare_groups, 'sources.BedrockSources._rows': S.BedrockSources._rows,
         'sources.BedrockSources._merge': S.BedrockSources._merge, 'sources._reusable_prepared': S._reusable_prepared,
         'document.per_second_rows': D.per_second_rows}
for name, obj in names.items():
    out[name] = hashlib.sha256(inspect.getsource(obj).encode()).hexdigest()
print(json.dumps(out, sort_keys=True))
'''


def code_of(box):
    """The runtime's table/sources code record, or {'unreadable': reason}: a record only, never a refusal."""
    result = subprocess.run([sys.executable, '-B', '-c', OLD_CODE, str(box)], capture_output=True, text=True, check=False)
    if result.returncode:
        return dict(unreadable='runtime code could not be read: ' + result.stderr.strip()[-400:])
    return json.loads(result.stdout)


def sha256(path):
    hashed = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(8 << 20), b''):
            hashed.update(block)
    return hashed.hexdigest()


def adopt(directory, digest, old_code_root):
    directory = Path(directory).resolve(strict=True)
    work = directory / 'work'
    scratch = work / 'derived' / digest
    layers = scratch / 'calculation-layers'
    if not digest.startswith('.digest-') or not (layers / 'sources.sqlite').is_file():
        raise ValueError('DIGEST must name the stopped ROOT scratch holding sources.sqlite')
    lock = (directory / 'calculation.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError('the calculation root is locked: ROOT is still running') from None
    try:
        old, new = code_of(Path(old_code_root) / 'deploy/aws/box'), code_of(Path(__file__).resolve().parent)
        # recorded, never compared: the names whose code differs are listed on the report, nothing is refused
        differs = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
        if not any(scratch.glob('table-0005*')):
            raise ValueError('the bedrock table stage never started: legacy tables and sources are not proven finished')
        if (layers / 'sources.sqlite-journal').exists():
            raise ValueError('sources.sqlite has a journal: its last transaction did not finish')
        report = dict(schema='FRANKIE_DIGEST_ADOPTION_V1', directory=str(directory), digest=digest, adopted=[],
                      code_record=dict(old_runtime=old, this_checkout=new, differs=differs))
        receipt = json.loads((work / 'derive.json').read_bytes())
        entries = {name: entry for name, entry in receipt['layers'].items() if entry.get('bedrock')}
        sources = layers / 'sources.sqlite'
        entries = P.recorded_order(entries, sources)   # ROOT's in-memory layer order, not derive.json's sorted keys
        target = layers / 'sources.save.json'
        if not target.exists():
            info = sources.stat()
            value = dict(key=P.sources_key(entries), path=str(sources), bytes=info.st_size, mtime_ns=info.st_mtime_ns,
                         sha256=sha256(sources), adopted_from=str(old_code_root),
                         code=dict(old_runtime=old, this_checkout=P.sources_code()))
            with target.open('x', encoding='utf-8') as handle:
                json.dump(value, handle, sort_keys=True)
            report['adopted'].append('sources.sqlite')
        code = dict(old_runtime=old, this_checkout=D._code_identity())     # recorded beside each key
        inputs = {name: entry.get('sha256') for name, entry in sorted(receipt['layers'].items()) if not entry.get('bedrock')}
        for ordinal, (name, context) in enumerate(LEGACY):
            path = scratch / ('table-%04d.txt' % ordinal)
            database = scratch / ('table-%04d' % ordinal) / 'table.sqlite'
            if (scratch / ('table-%04d.save.json' % ordinal)).exists():
                continue
            with path.open(encoding='utf-8') as handle:
                header = handle.readline()
            m = re.fullmatch(r'### table (\S+): (\d+) rows, .*\n', header)
            if m is None or m.group(1) != name:
                raise ValueError('legacy table %d is not %s' % (ordinal, name))
            key = D.legacy_key(name, context, inputs)
            D._save_table(scratch, ordinal, key, dict(name=name, rows=int(m.group(2)), path=path, digest=D._witness(path)),
                          context=D._witness(database), code=code)
            report['adopted'].append(path.name)
        return report
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--digest', required=True)
    parser.add_argument('--old-code-root', required=True)
    args = parser.parse_args()
    if not str(Path(args.directory).resolve(strict=True)).startswith('/opt/frankie-box/work/monday-calculations/'):
        raise SystemExit('Monday calculation root required')
    print(json.dumps(adopt(args.directory, args.digest, args.old_code_root), indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
