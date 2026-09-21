"""Frankie's brain: the calculation findings of every prior cycle, carried into the next cycle's reading (Greg, 2026-09-21
chat 6: "cycle 0 and 1 calc findings should be in the brain without a doubt; other generated docs case by case").

One entry per cycle under <brain>/cycle-<NN>/: the derivation digest (every layer of the pin, what the calculations
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


def write_entry(work, out, brain, cycle, include_analysis=True):
    """Write <brain>/cycle-<cycle>/ from the session's work and out directories. Returns the manifest."""
    work, out, entry_dir = Path(work), Path(out), Path(brain) / f'cycle-{cycle}'
    entry_dir.mkdir(parents=True, exist_ok=True)
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
    manifest = dict(schema=SCHEMA, cycle=cycle, at=time.time(), entries=entries,
                    note='Greg, 2026-09-21: the calculation findings of cycles 0 and 1 are in the brain without a doubt; other documents '
                         'case by case: set include to false to keep an entry out of the next corpus, add a file with include true to bring one in.')
    (entry_dir / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


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


def identity(brain, cycle):
    """A short digest of every included prior entry (name + sha256): part of the corpus identity."""
    h = hashlib.sha256()
    for cyc, manifest, d in entries_before(brain, cycle):
        for e in manifest.get('entries', []):
            if e.get('include'):
                h.update(f'{cyc}/{e["name"]}/{e["sha256"]}\n'.encode())
    return h.hexdigest()[:16]


def load(brain, cycle):
    """(text, members): the included, digest-verified entries of every earlier cycle as corpus text plus member records."""
    parts, members = [], []
    for cyc, manifest, d in entries_before(brain, cycle):
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
