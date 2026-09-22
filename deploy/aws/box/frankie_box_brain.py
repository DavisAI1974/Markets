"""Frankie's brain: the calculation findings of every prior cycle, carried into the next cycle's reading (Greg, 2026-09-21
chat 6: "cycle 0 and 1 calc findings should be in the brain without a doubt; other generated docs case by case").

The latest entry remains under <brain>/cycle-<NN>/ for compatibility; every replaced version is preserved in history with a move receipt. Requests pin all accumulated entries, including earlier runs of the same cycle number, through capture_base. Each entry holds: the derivation digest (every layer of the pin, what the calculations
found), the accounting entry and the ten output ledgers (from response.json's lessons), the analysis, each with its
bytes and sha256 in MANIFEST.json. The next cycle's session loads every entry of an EARLIER cycle whose manifest says
include: true and whose bytes still match, and appends it to the reading corpus as members, so Frankie reads and
notes his own prior findings before deriving again. Case by case = the manifest: set "include": false on an entry to
keep it out of the corpus, or add a file with "include": true to bring another document in. Durable on the box; the
pusher publishes each cycle's entry under runs/<day>/root/brain/cycle-<NN>/. Nothing here is a summary, nothing is
deleted; a changed manifest changes the corpus identity, so the corpus is rebuilt.
"""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path

SCHEMA = 'FRANKIE_BOX_BRAIN_ENTRY_V1'
ACCOUNTING_NAME = 'accounting-and-ledgers.md'


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _lessons_doc(response):
    """The accounting entry and the output ledgers (every JSON lesson of the response) as one Markdown document."""
    lessons = response.get('lessons') or []
    blocks = []
    for entry in lessons:
        if isinstance(entry, dict):
            title = entry.get('ledger') or entry.get('name') or 'entry'
            blocks.append(f'## {title}\n\n```json\n' + json.dumps(entry, indent=1, sort_keys=True, ensure_ascii=False) + '\n```\n')
    if not blocks:
        return None
    return f'# Accounting entry and output ledgers ({len(blocks)} JSON lessons of the response)\n\n' + '\n'.join(blocks)


def _archive_entry(brain, entry_dir):
    """Preserve the previous version with a receipt for its move."""
    import uuid
    brain, entry_dir = Path(brain).resolve(), Path(entry_dir)
    if not entry_dir.exists():
        return None
    if entry_dir.is_symlink() or entry_dir.resolve().parent != brain:
        raise ValueError('brain entry must be an immediate real directory')
    history = brain / 'history'
    history.mkdir(exist_ok=True)
    stamp = str(time.time_ns()) + '-' + uuid.uuid4().hex
    target = history / (entry_dir.name + '-' + stamp)
    manifest = entry_dir / 'MANIFEST.json'
    value = dict(schema='FRANKIE_BRAIN_PRESERVATION_RECEIPT_V1', source=str(entry_dir),
                 destination=str(target), manifest_sha256=sha256_bytes(manifest.read_bytes()) if manifest.is_file() else None,
                 reason='new run adds knowledge; previous entry retained whole')
    entry_dir.rename(target)
    with (history / ('move-' + stamp + '.json')).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
    return target


def _checked_entry(directory, expected_hash=None):
    directory = Path(directory)
    raw = (directory / 'MANIFEST.json').read_bytes()
    if expected_hash is not None and sha256_bytes(raw) != expected_hash:
        raise ValueError('knowledge manifest differs from pinned base')
    manifest = json.loads(raw)
    for entry in manifest.get('entries', []):
        if not entry.get('include'):
            continue
        name = entry.get('name', '')
        path = directory / name
        if (not name or Path(name).name != name or path.is_symlink() or not path.is_file()
                or sha256_bytes(path.read_bytes()) != entry.get('sha256')
                or path.stat().st_size != entry.get('bytes')):
            raise ValueError('included historical knowledge missing or changed: ' + name)
    return manifest, sha256_bytes(raw)


def capture_base(brain, request_identity):
    """Pin all accumulated prior-run knowledge, including cycle zero, for this request."""
    import re
    import shutil
    if not re.fullmatch('[0-9a-f]{64}', request_identity):
        raise ValueError('full request identity required for knowledge base')
    brain = Path(brain)
    snapshot = brain / 'bases' / request_identity / 'MANIFEST.json'
    if snapshot.is_file():
        list(snapshot_entries(brain, snapshot))
        return snapshot
    history = brain / 'history'
    history.mkdir(parents=True, exist_ok=True)
    candidates = list(brain.glob('cycle-*/MANIFEST.json')) + list(history.glob('*/MANIFEST.json'))
    frozen = brain / FROZEN_DIR / 'MANIFEST.json'
    if frozen.is_file():
        candidates.append(frozen)
    entries = {}
    for path in sorted(candidates):
        manifest, digest = _checked_entry(path.parent)
        if digest in entries:
            continue
        destination = history / ('entry-' + digest)
        if not destination.exists():
            shutil.copytree(path.parent, destination)
        _checked_entry(destination, digest)
        entries[digest] = dict(path=str(destination.relative_to(brain)), sha256=digest,
                               cycle=manifest.get('cycle'), source_schema=manifest.get('schema'))
    value = dict(schema='FRANKIE_ACCUMULATED_KNOWLEDGE_BASE_V1', request_identity=request_identity,
                 entries=list(entries.values()), rule='all previously stored intact knowledge; immutable for this request')
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    with snapshot.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
    return snapshot


def snapshot_entries(brain, snapshot):
    brain = Path(brain).resolve()
    value = json.loads(Path(snapshot).read_bytes())
    if value.get('schema') != 'FRANKIE_ACCUMULATED_KNOWLEDGE_BASE_V1':
        raise ValueError('accumulated knowledge base schema differs')
    for entry in value['entries']:
        path = (brain / entry['path']).resolve()
        if not path.is_relative_to(brain / 'history'):
            raise ValueError('knowledge base entry is outside retained history')
        manifest, digest = _checked_entry(path, entry['sha256'])
        yield ('prior-run-' + digest[:16] + '-cycle-' + str(entry.get('cycle')), manifest, path)


def write_entry(work, out, brain, cycle, include_analysis=True):
    """Write <brain>/cycle-<cycle>/ from the session's work and out directories. Returns the manifest."""
    work, out, entry_dir = Path(work), Path(out), Path(brain) / f'cycle-{cycle}'
    if not (work / 'derivation-digest-full.md').is_file():
        raise FileNotFoundError('the brain entry needs the calculation findings')
    _archive_entry(brain, entry_dir)
    entry_dir.mkdir(parents=True, exist_ok=False)
    entries = []

    def put(name, data, source, kind, include=True):
        (entry_dir / name).write_bytes(data)
        entries.append(dict(name=name, bytes=len(data), sha256=sha256_bytes(data), source=str(source), kind=kind, include=include))

    digest = work / 'derivation-digest-full.md'
    if not digest.is_file():
        raise FileNotFoundError(f'no derivation digest at {digest}; the brain entry needs the calculation findings')
    put('derivation-digest-full.md', digest.read_bytes(), digest, 'calculation findings: the derivation digest, every layer of the pin')
    response = out / 'response.json'
    if response.is_file():
        doc = _lessons_doc(json.loads(response.read_bytes()))
        if doc:
            put(ACCOUNTING_NAME, doc.encode('utf-8'), response, 'calculation findings: the accounting entry and the output ledgers')
    analysis = out / 'analysis.md'
    if analysis.is_file():
        put('analysis.md', analysis.read_bytes(), analysis, 'the run analysis', include_analysis)
    derive = work / 'derive.json'
    if derive.is_file():
        try:
            doc = '# Derivation receipt (derive.json: every layer of the pin with its status, producer and sha256)\n\n```json\n' + \
                json.dumps(json.loads(derive.read_bytes()), indent=1, sort_keys=True, ensure_ascii=False) + '\n```\n'
            put('derive.md', doc.encode('utf-8'), derive, 'calculation findings: the derivation receipt (layer statuses, producers, digests)')
        except Exception:
            pass
    comparison = work / 'comparison.md'
    if comparison.is_file():
        put('comparison.md', comparison.read_bytes(), comparison, 'calculation findings: the comparison packet (derived layers beside the frozen learned-structure files)')
    classroom = work / 'classroom' / 'classroom.md'
    if classroom.is_file():
        put('classroom.md', classroom.read_bytes(), classroom, "the Dipole classroom: Frankie's own teach-back of the 19-dimension surface for this cycle (case by case: set include false to keep it out)")
    teach = work / 'teach' / 'exhaustion-teachback.md'
    if teach.is_file():
        put('exhaustion-teachback.md', teach.read_bytes(), teach, 'calculation findings: the exhaustion and D teach-back (the BOSS on its own bedrock facts and the frozen learned structure; numbers checked by code; Greg, 2026-09-21: All 3)')
    bedrock = work / 'bedrock' / 'receipt.json'
    if bedrock.is_file():
        try:
            doc = '# The bedrock traversal receipt (bedrock/receipt.json: the pinned producers\' own driver on this cycle\'s rows; identity, arguments, ledgers, reconciliation, sections fed)\n\n```json\n' + \
                json.dumps(json.loads(bedrock.read_bytes()), indent=1, sort_keys=True, ensure_ascii=False) + '\n```\n'
            put('bedrock.md', doc.encode('utf-8'), bedrock, 'calculation findings: the bedrock traversal receipt (the twenty bedrock layers\' provenance)')
        except Exception as error:
            entries.append(dict(name='bedrock.md', error=f'{type(error).__name__}: {error}', source=str(bedrock), include=False))
    derived = work / 'derived'
    if derived.is_dir():
        files = [dict(name=f.name, bytes=f.stat().st_size, sha256=sha256_bytes(f.read_bytes())) for f in sorted(derived.iterdir()) if f.is_file()]
        doc = ('# Derived files of this cycle (witnessed by name, bytes, sha256; the derivation digest renders their content losslessly)\n\n'
               '| file | bytes | sha256 |\n|---|---:|---|\n' + '\n'.join(f"| {f['name']} | {f['bytes']} | {f['sha256']} |" for f in files) + '\n')
        put('derived-files.md', doc.encode('utf-8'), derived, 'witness of the derived files (their content is in the digest)', False)
    docs = out / 'docs'
    if docs.is_dir():
        for path in sorted(docs.glob('*.md')):
            put('session-doc-' + path.name, path.read_bytes(), path,
                'session document: retained whole for subsequent runs')
    manifest = dict(schema=SCHEMA, cycle=cycle, at=time.time(), entries=entries,
                    note='Greg, 2026-09-21: the calculation findings of cycles 0 and 1 are in the brain without a doubt; other documents '
                         'case by case: set include to false to keep an entry out of the next corpus, add a file with include true to bring one in.')
    (entry_dir / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def check(brain, cycle):
    """The earlier cycles WITHOUT a usable brain entry (no manifest, or the digest missing or not matching). Empty = ready."""
    brain = Path(brain)
    missing = []
    for n in range(int(cycle)):
        cyc = f'{n:02d}'
        d = brain / f'cycle-{cyc}'
        m = d / 'MANIFEST.json'
        ok = False
        if m.is_file():
            try:
                manifest = json.loads(m.read_bytes())
                digest = next((e for e in manifest.get('entries', []) if e.get('name') == 'derivation-digest-full.md'), None)
                ok = bool(digest) and (d / 'derivation-digest-full.md').is_file() and \
                    sha256_bytes((d / 'derivation-digest-full.md').read_bytes()) == digest.get('sha256')
            except Exception:
                ok = False
        if not ok:
            missing.append(cyc)
    return missing


def restore_from_git(brain, cycles, repo, day, remote='origin', branch_format='root/cycle-{cycle}-response'):
    """Restore the named cycles' entries from their published branches (a fetch into FETCH_HEAD; the checkout is never
    moved). Returns {cycle: 'restored' | reason}. Files land under <brain>/cycle-<NN>/ only when the manifest and every
    listed file arrive and match their sha256."""
    import subprocess
    brain, repo = Path(brain), Path(repo)
    result = {}
    for cyc in cycles:
        branch = branch_format.format(cycle=cyc)
        prefix = f'research/kalshi/frankie_boss/runs/{day}/root/brain/cycle-{cyc}'
        fetch = subprocess.run(['git', '-C', str(repo), 'fetch', '-q', '--depth', '1', remote, branch], capture_output=True, text=True)
        if fetch.returncode:
            result[cyc] = f'branch {branch} not fetchable: {fetch.stderr.strip()[:200]}'
            continue
        show = subprocess.run(['git', '-C', str(repo), 'show', f'FETCH_HEAD:{prefix}/MANIFEST.json'], capture_output=True)
        if show.returncode:
            result[cyc] = f'no brain entry on {branch} ({prefix}/MANIFEST.json)'
            continue
        try:
            manifest = json.loads(show.stdout)
        except Exception:
            result[cyc] = f'unreadable manifest on {branch}'
            continue
        staged = {}
        bad = None
        for e in manifest.get('entries', []):
            got = subprocess.run(['git', '-C', str(repo), 'show', f'FETCH_HEAD:{prefix}/{e["name"]}'], capture_output=True)
            if got.returncode or sha256_bytes(got.stdout) != e.get('sha256'):
                bad = e['name']
                break
            staged[e['name']] = got.stdout
        if bad:
            result[cyc] = f'{bad} missing or not matching its sha256 on {branch}'
            continue
        d = brain / f'cycle-{cyc}'
        d.mkdir(parents=True, exist_ok=True)
        for name, data in staged.items():
            (d / name).write_bytes(data)
        (d / 'MANIFEST.json').write_bytes(show.stdout)
        result[cyc] = 'restored'
    return result


FROZEN_DIR = 'frozen-learned-structure'
FROZEN_ROW = re.compile(r'^\|\s*`([^`]+)`\s*\|\s*frozen_learned_structure\s*\|')
FILE_REF = re.compile(r'`([^`]+)`\s+`([0-9a-f]{12})`')


def frozen_files_from_prompt(historical_prompt_text):
    """{(path, sha256 prefix): [layers]} for every file the request's knowledge table names under frozen_learned_structure."""
    found = {}
    for line in historical_prompt_text.splitlines():
        m = FROZEN_ROW.match(line)
        if not m:
            continue
        layer = m.group(1)
        for path, prefix in FILE_REF.findall(line):
            found.setdefault((path, prefix), []).append(layer)
    return found


def write_frozen_entry(historical_prompt, repo, brain):
    """Greg, 2026-09-21 ("unfreeze the structure content"): the frozen learned-structure layers are delivered BY PATH
    only (the request names the files and 12-char digests; Frankie saw only that table in cycle 0). This writes
    <brain>/frozen-learned-structure/ from the box's own checkout: every named file whose bytes match the delivered
    digest prefix, flattened by path, with a manifest (include true); a file whose bytes differ, or is absent, is
    listed with include false and the reason (case by case: flip include to carry the checkout's version anyway).
    Deterministic and idempotent; rebuilt at every session start."""
    repo, entry_dir = Path(repo), Path(brain) / FROZEN_DIR
    text = Path(historical_prompt).read_text(encoding='utf-8', errors='replace')
    files = frozen_files_from_prompt(text)
    repo_root = Path(repo).resolve()
    for (path, _prefix) in list(files):
        # containment: a path the delivered prompt names is data; it must resolve inside the checkout (never .. or absolute)
        if Path(path).is_absolute() or '..' in Path(path).parts or not (repo_root / path).resolve().is_relative_to(repo_root):
            raise ValueError(f'the delivered prompt names a frozen file outside the checkout: {path!r}')
    _archive_entry(brain, entry_dir)
    entry_dir.mkdir(parents=True, exist_ok=False)
    entries = []
    for (path, prefix), layers in sorted(files.items()):
        src = repo / path
        name = path.replace('/', '__')
        if not src.is_file():
            entries.append(dict(name=name, source=path, layers=layers, include=False, reason='file absent from the checkout', delivered_prefix=prefix))
            continue
        data = src.read_bytes()
        digest = sha256_bytes(data)
        (entry_dir / name).write_bytes(data)
        e = dict(name=name, source=path, bytes=len(data), sha256=digest, layers=layers, delivered_prefix=prefix,
                 kind='frozen learned structure: a file the request names for these layers, from the checkout')
        if digest.startswith(prefix):
            e['include'] = True
        else:
            e['include'] = False
            e['reason'] = 'the checkout bytes do not match the delivered digest prefix; excluded unless include is set true'
        entries.append(e)
    manifest = dict(schema='FRANKIE_BOX_BRAIN_FROZEN_ENTRY_V1', at=time.time(), historical_prompt=str(historical_prompt),
                    layers=sorted({l for ls in files.values() for l in ls}), entries=entries,
                    note='the frozen learned-structure content, so the comparison step can run; rebuilt from the checkout at every session start')
    (entry_dir / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def frozen_entry(brain):
    """(manifest, entry_dir) of the standing frozen entry, or (None, None)."""
    d = Path(brain) / FROZEN_DIR
    m = d / 'MANIFEST.json'
    if not m.is_file():
        return None, None
    try:
        return json.loads(m.read_bytes()), d
    except Exception:
        return None, None


def entries_before(brain, cycle):
    """(cycle, manifest, entry_dir) for every earlier cycle's entry, in cycle order."""
    brain = Path(brain)
    found = []
    if not brain.is_dir():
        return found
    for d in sorted(brain.glob('cycle-*')):
        cyc = d.name[len('cycle-'):]
        m = d / 'MANIFEST.json'
        if m.is_file() and cyc.isdigit() and int(cyc) < int(cycle):
            try:
                found.append((cyc, json.loads(m.read_bytes()), d))
            except Exception:
                continue
    return found


def identity(brain, cycle, *, snapshot=None):
    """A short digest of every included prior entry (name + sha256): part of the corpus identity."""
    h = hashlib.sha256()
    fm, _ = (None, None) if snapshot else frozen_entry(brain)
    for e in (fm or {}).get('entries', []):
        if e.get('include'):
            h.update(f'frozen/{e["name"]}/{e["sha256"]}\n'.encode())
    for cyc, manifest, d in (snapshot_entries(brain, snapshot) if snapshot else entries_before(brain, cycle)):
        for e in manifest.get('entries', []):
            if e.get('include'):
                h.update(f'{cyc}/{e["name"]}/{e["sha256"]}\n'.encode())
    return h.hexdigest()[:16]


def load(brain, cycle, *, snapshot=None):
    """(text, members): the included, digest-verified entries of every earlier cycle as corpus text plus member records."""
    parts, members = [], []
    fm, fd = (None, None) if snapshot else frozen_entry(brain)
    if fm:
        parts.append("\n\n## Frankie's brain: the frozen learned structure, the files the request's knowledge layers name (delivered by path; "
                     "their content here from the checkout, each verified against the delivered digest). Compare this cycle's derivations "
                     "with them, layer by layer.\n")
        for e in fm.get('entries', []):
            name = e.get('name', '')
            p = fd / name
            if not e.get('include'):
                members.append(dict(name=f'brain-frozen-{name}', bytes=e.get('bytes'), treatment=f'frozen file excluded: {e.get("reason", "include false")}'))
                continue
            data = p.read_bytes() if p.is_file() else None
            if data is None or sha256_bytes(data) != e.get('sha256'):
                members.append(dict(name=f'brain-frozen-{name}', treatment='frozen file missing or changed since its manifest; not in the corpus'))
                continue
            parts.append(f"\n### {e['source']} (layers: {', '.join(e.get('layers', []))}; sha256 {e['sha256'][:16]})\n\n" + data.decode('utf-8', errors='replace') + '\n')
            members.append(dict(name=f'brain-frozen-{name}', bytes=len(data), sha256=e['sha256'], treatment='brain: frozen learned-structure file, whole'))
    for cyc, manifest, d in (snapshot_entries(brain, snapshot) if snapshot else entries_before(brain, cycle)):
        for e in manifest.get('entries', []):
            name = e.get('name', '')
            p = d / name
            if not e.get('include'):
                members.append(dict(name=f'brain-cycle-{cyc}-{name}', bytes=e.get('bytes'), sha256=e.get('sha256'), treatment='brain entry excluded by its manifest (include false); not in the corpus'))
                continue
            if not p.is_file():
                members.append(dict(name=f'brain-cycle-{cyc}-{name}', treatment='brain entry file missing; not in the corpus'))
                continue
            data = p.read_bytes()
            if sha256_bytes(data) != e.get('sha256'):
                members.append(dict(name=f'brain-cycle-{cyc}-{name}', bytes=len(data), treatment='brain entry bytes differ from its manifest; not in the corpus'))
                continue
            parts.append(f"\n\n## Frankie's brain: cycle {cyc}, {name} ({e.get('kind', 'document')}; carried forward whole, sha256 {e['sha256'][:16]})\n\n"
                         + data.decode('utf-8', errors='replace') + '\n')
            members.append(dict(name=f'brain-cycle-{cyc}-{name}', bytes=len(data), sha256=e['sha256'], treatment='brain: prior cycle calculation findings, whole'))
    return ''.join(parts), members


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--work', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--brain', required=True)
    p.add_argument('--cycle', required=True)
    a = p.parse_args()
    m = write_entry(a.work, a.out, a.brain, a.cycle)
    print(f"brain entry cycle {a.cycle}: {len(m['entries'])} documents in {Path(a.brain) / ('cycle-' + a.cycle)}")
    for e in m['entries']:
        print(f"  {e['name']}: {e['bytes']} bytes, include {e['include']}")


if __name__ == '__main__':
    main()
