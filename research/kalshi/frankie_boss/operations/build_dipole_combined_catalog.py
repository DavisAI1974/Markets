"""Combine every Dipole source in the repository, on every branch, into ONE shared-knowledge catalog.

Greg, 2026-10-06: "The dipole collection. Anything dipole. And if they're in different places, combine them into 1."
Built by CCode on that word. Code over committed bytes: no model (R17), no data run, nothing summarized or judged.

What goes in (all of it, each labelled by its source; R11):
  1. the 127 sources of DIPOLE_SHARED_CATALOG_20260922.json, carried byte-for-byte (same ids, revisions, sha256);
  2. every other file whose CONTENT mentions "dipole" (case-insensitive) on the tip of every non-data branch of origin,
     one entry per distinct (path, blob) so a file that differs across branches keeps every version; a version's
     revision is the newest branch tip carrying it (git show <revision>:<path> reproduces the bytes), and every other
     branch carrying the same bytes is named in provenance.also_on;
  3. machine data that mentions dipole (.jsonl/.csv/.npz/.html, or .json over DATA_BYTES) is LISTED under data_listed
     with the same identity, not extracted as prose: the teachers reach it by revision when a computation needs it;
  4. the outputs of this pipeline itself (earlier catalogs, coverage indexes, HISTORICAL_CLAIMS_V1-*) are LISTED under
     derived_excluded, never re-ingested as sources (they would duplicate every statement they already carry).
Nothing is dropped: every swept (path, blob) lands in exactly one of sources / data_listed / derived_excluded.

Output: research/kalshi/frankie_boss/knowledge/DIPOLE_SHARED_CATALOG_20261006_COMBINED.json, schema
FRANKIE_SHARED_KNOWLEDGE_CATALOG_V1 (validated by dipole_shared_knowledge._catalog), review_groups K01-K10 carried, so
frankie_box_historical_claims.build(catalog_path=...) reads it unchanged. Reproduction needs the branch tips fetched
(git fetch --depth=1 origin <branch>...); the sweep's branch list and tip commits are recorded under sweep.
Usage: python3 build_dipole_combined_catalog.py [--sweep-tsv path] [--out path]
  --sweep-tsv: a precomputed sweep (path, blob, bytes, branch, commit per row); otherwise the sweep runs here.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[4]
BASE = 'research/kalshi/frankie_boss/knowledge/DIPOLE_SHARED_CATALOG_20260922.json'
OUT = 'research/kalshi/frankie_boss/knowledge/DIPOLE_SHARED_CATALOG_20261006_COMBINED.json'
VERSION = '20261006-combined-every-dipole-source-v1'
DATA_SUFFIX = ('.jsonl', '.csv', '.npz', '.html', '.png', '.jpg')
DATA_BYTES = 1_000_000
DERIVED = re.compile(r'(HISTORICAL_CLAIMS_V1-|DIPOLE_SHARED_CATALOG_|DIPOLE_KNOWLEDGE_SOURCE_COVERAGE_)')
PRIVATE = re.compile(r'teacher[-_]key|classroom[-_]audit', re.I)
ID_BAD = re.compile(r'[^A-Za-z0-9_.:-]')


def git(*args, text=True):
    return subprocess.run(['git', '-C', str(REPO)] + list(args), capture_output=True, check=True, text=text).stdout


def sweep():
    """(path, blob, bytes, branch, commit) for every dipole-content file on every non-data origin branch tip."""
    refs = [r for r in git('for-each-ref', '--sort=-committerdate', '--format=%(refname:short)', 'refs/remotes/origin').split()
            if not r.startswith('origin/data/') and r != 'origin/HEAD']
    rows = []
    for ref in refs:
        commit = git('rev-parse', ref).strip()
        try:
            hits = git('grep', '-il', 'dipole', ref, '--', ':(exclude)data/*', ':(exclude)*.npz', ':(exclude)*.png', ':(exclude)*.jpg')
        except subprocess.CalledProcessError:
            continue
        paths = {h.split(':', 1)[1] for h in hits.split('\n') if h}
        for line in git('ls-tree', '-r', '-l', ref).split('\n'):
            if not line:
                continue
            meta, path = line.split('\t', 1)
            if path in paths:
                _, _, blob, size = meta.split()
                rows.append((path, blob, int(size), ref, commit))
    return refs, rows


def load_tsv(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        p, blob, size, ref, commit = line.split('\t')
        rows.append((p, blob, int(size), ref, commit))
    refs = list(dict.fromkeys(r[3] for r in rows))
    return refs, rows


def entry_id(path, blob):
    return 'swept.' + ID_BAD.sub('_', path.replace('/', '.')) + ':' + blob[:7]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--sweep-tsv')
    p.add_argument('--out', default=OUT)
    a = p.parse_args()
    base_bytes = (REPO / BASE).read_bytes()
    base = json.loads(base_bytes)
    refs, rows = load_tsv(a.sweep_tsv) if a.sweep_tsv else sweep()
    tips = {ref: commit for _, _, _, ref, commit in rows}
    by_version = collections.OrderedDict()           # (path, blob) -> dict(bytes, branches[])
    for path, blob, size, ref, commit in rows:        # rows are newest-branch-first
        v = by_version.setdefault((path, blob), dict(bytes=size, branches=[]))
        v['branches'].append((ref, commit))
    carried = {(s['path'], s['sha256']) for s in base['sources']}
    carried_paths = {s['path'] for s in base['sources']}
    sources = list(base['sources'])
    data_listed, derived, duplicates_of_base = [], [], 0
    for (path, blob), v in by_version.items():
        newest_ref, newest_commit = v['branches'][0]
        if PRIVATE.search(path):
            continue
        sha = hashlib.sha256(git('show', '%s:%s' % (newest_commit, path), text=False)).hexdigest()
        if (path, sha) in carried:
            duplicates_of_base += 1
            continue
        item = dict(id=entry_id(path, blob), path=path, revision=newest_commit, sha256=sha, bytes=v['bytes'],
                    required=True, access='SHARED_RESEARCH',
                    provenance=dict(repository='DavisAI1974/Markets', branch=newest_ref, commit=newest_commit,
                                    git_blob_sha=blob, also_on=[r for r, _ in v['branches'][1:]],
                                    sweep='content mentions dipole (git grep -il) on the branch tip'),
                    supersedes=[])
        suffix = PurePosixPath(path).suffix.lower()
        if DERIVED.search(path):
            item.update(status='DERIVED_PIPELINE_OUTPUT', explanation='An output of the catalog/claims pipeline itself; '
                        'listed, not re-ingested (it already carries every statement of its own sources).')
            derived.append(item)
        elif suffix in DATA_SUFFIX or (suffix == '.json' and v['bytes'] > DATA_BYTES):
            item.update(status='DATA_LISTED_NOT_EXTRACTED', explanation='Machine data that mentions dipole; identity '
                        'and bytes listed so a teacher computation can read it by revision; not extracted as prose.')
            data_listed.append(item)
        else:
            item.update(status='SWEPT_DIPOLE_CONTENT' + ('_OTHER_VERSION' if path in carried_paths else ''),
                        explanation='Every file whose content mentions dipole, on every branch tip, kept at its own '
                        'bytes; a historical claim, never truth (R11); constructions stay distinct (K01).')
            sources.append(item)
    doc = dict(schema=base['schema'], version=VERSION,
               policy=base['policy'] + ' COMBINED 2026-10-06 (Greg: anything dipole, in one place): every file whose '
                      'content mentions dipole on every branch tip is a source at its own bytes; versions that differ '
                      'across branches are each kept; machine data and pipeline outputs are listed, never dropped.',
               combined_from=dict(base_catalog=BASE, base_sha256=hashlib.sha256(base_bytes).hexdigest(),
                                  base_sources=len(base['sources'])),
               baseline_artifacts=base['baseline_artifacts'], review_groups=base['review_groups'],
               sweep=dict(method='git grep -il dipole on each origin branch tip (data/ branches, .npz/.png/.jpg excluded); '
                                 'one entry per distinct (path, blob); revision = newest tip carrying the blob',
                          branches=len(refs), tips={r: tips.get(r) for r in refs}, rows=len(rows),
                          distinct_versions=len(by_version), duplicates_of_base_catalog=duplicates_of_base),
               counts=dict(sources=len(sources), data_listed=len(data_listed), derived_excluded=len(derived)),
               sources=sources, data_listed=data_listed, derived_excluded=derived)
    import importlib.util                          # by file: the package __init__ imports torch, not needed here
    spec = importlib.util.spec_from_file_location('dipole_shared_knowledge',
                                                  REPO / 'research/kalshi/frankie_boss/dipole_shared_knowledge.py')
    K = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(K)
    K._catalog(doc)                                  # the shared-knowledge validator, or it raises
    out = REPO / a.out
    out.write_bytes((json.dumps(doc, indent=1, sort_keys=True) + '\n').encode())
    print(json.dumps(dict(out=str(out), bytes=out.stat().st_size, **doc['counts'], **{k: v for k, v in doc['sweep'].items() if k != 'tips'})))


if __name__ == '__main__':
    main()
