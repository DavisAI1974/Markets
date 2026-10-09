"""Build a running ROOT's bedrock tables on the idle cores, beside it, from its finished sources.sqlite.

ROOT (b35e79b7) writes each bedrock table on one core; bedrock.members alone is ~63 GB of member data at ~1.75 MB/s.
This opens that ROOT's finished sources.sqlite READ-ONLY, rebuilds the same table registry (frankie_box_digest_parallel
.ReopenedSources), and writes every bedrock table with the parallel writer (same bytes as write_table) into a new
sibling scratch, work/derived/.digest-side-<id>/, each with the save receipt the restarted ROOT looks up (same key
as frankie_box_digest_document). Nothing of ROOT is written, locked or signalled. Resumable: a table an earlier side
run finished is found by its receipt and not rebuilt.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frankie_box_digest_document as D  # noqa: E402
import frankie_box_digest_parallel as P  # noqa: E402

LEGACY_TABLES = 5      # write_digest writes five legacy tables (ordinals 0-4) before the bedrock tables


def siblings(cpus):
    out = set(cpus)
    for cpu in cpus:
        path = Path('/sys/devices/system/cpu') / ('cpu%d' % cpu) / 'topology' / 'thread_siblings_list'
        for part in path.read_text().strip().split(','):
            lo, _, hi = part.partition('-')
            out.update(range(int(lo), int(hi or lo) + 1))
    return sorted(out & os.sched_getaffinity(0))


def _own_saved(side, ordinal, key):
    """A table an earlier run of this side builder finished and receipted in the same side scratch (D._saved_table
    looks only in other scratches)."""
    receipt = side / ('table-%04d.save.json' % ordinal)
    try:
        value = json.loads(receipt.read_bytes())
        path = Path(value['path'])
        if (value.get('schema') == D.TABLE_SAVE_SCHEMA and D._key_matches(value.get('key'), key) and path.parent == side
                and path.name == 'table-%04d.txt' % ordinal and path.is_file() and D._witness(path) == value.get('digest')):
            return dict(name=value['name'], rows=value['rows'], path=path, digest=value['digest'], saved=str(receipt))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--digest', required=True)
    parser.add_argument('--cpus', required=True, help='comma-separated physical CPUs to use')
    parser.add_argument('--with-siblings', action='store_true')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    root = Path(args.directory).resolve(strict=True)
    if not root.is_relative_to(Path('/opt/frankie-box/work/monday-calculations')):
        raise SystemExit('Monday calculation root required')
    work = root / 'work'
    layers_root = work / 'derived' / args.digest / 'calculation-layers'
    if not args.digest.startswith('.digest-') or not (layers_root / 'sources.sqlite').is_file():
        raise SystemExit('DIGEST must name the ROOT scratch holding the finished sources.sqlite')
    if (layers_root / 'sources.sqlite-journal').exists():
        raise SystemExit('sources.sqlite is still being written (journal present)')
    cpus = [int(c) for c in args.cpus.split(',') if c.strip()]
    if args.with_siblings:
        cpus = siblings(cpus)
    # One fixed side scratch for this root (not one per run): a rerun after a stop or failure finds the tables already
    # saved here and the unfinished table's saved passes (frankie_box_digest_parallel save points) and resumes.
    side = work / 'derived' / '.digest-side-work'
    side.mkdir(exist_ok=True)
    receipt = json.loads((work / 'derive.json').read_bytes())
    entries = {name: entry for name, entry in receipt['layers'].items() if entry.get('bedrock')}
    entries = P.recorded_order(entries, layers_root / 'sources.sqlite')   # derive.json keys are sorted
    code = D._code_identity()                 # a record beside each save key, never compared
    layers_identity = D.layers_identity_of(entries)
    progress = side / 'progress.jsonl'

    def note(name, phase, **extra):
        line = json.dumps(dict(at=time.time(), table=name, phase=phase, **extra), sort_keys=True)
        print(line, flush=True)
        with progress.open('a', encoding='utf-8') as handle:
            handle.write(line + '\n')

    with P.ReopenedSources(entries, layers_root) as sources:
        tables = list(sources.tables.items())
        order = sorted(range(len(tables)), key=lambda i: (tables[i][0] != 'bedrock.members', i))   # biggest first
        note(None, 'start', cpus=cpus, run_id=args.run_id, tables=[name for name, _ in tables])
        for i in order:
            name, rows = tables[i]
            ordinal = LEGACY_TABLES + i
            spec = D.bedrock_spec(rows, sources.root)
            key = D.bedrock_key(name, layers_identity, spec)
            saved = _own_saved(side, ordinal, key) or D._saved_table(side, ordinal, key)
            if saved is not None:
                note(name, 'reused', ordinal=ordinal, saved=saved['saved'])
                continue
            started = time.time()
            path = side / ('table-%04d.txt' % ordinal)
            proof = P.write_table_parallel(path, name, P.split_specs(spec, 2 * len(cpus)),
                                           side / ('table-%04d' % ordinal), cpus,
                                           progress=lambda table, phase: note(table, phase, ordinal=ordinal),
                                           reserve=int(os.environ.get('FRANKIE_DIGEST_DISK_RESERVE', P.DISK_RESERVE)))
            digest = D._witness(path)
            if D.TS._identity(path) != proof['verified_identity']:
                raise ValueError('proved table changed before its byte witness')
            entry = dict(name=name, rows=proof['rows'], path=path, digest=digest)
            D._save_table(side, ordinal, key, entry, code=code)
            note(name, 'saved', ordinal=ordinal, rows=proof['rows'], bytes=digest['bytes'], seconds=round(time.time() - started, 1))
        note(None, 'done')


if __name__ == '__main__':
    main()
