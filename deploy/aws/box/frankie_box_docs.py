"""Frankie box docs: every document the session produces, as Markdown files with an index (Greg, 2026-09-21 chat 6).

The session already writes most of its documents as Markdown on the box (the per-part reading notes, the merged notes,
the derivation digest); the receipts are JSON; the intermediate merge outputs live only inside job results. This module
gathers them into ONE docs directory of Markdown files plus an index, so the pusher can publish them beside the four
cycle files under runs/<day>/root/docs-cycle-<NN>/ and nobody needs a box probe to read what Frankie read, noted,
merged and derived. Nothing is transformed: Markdown is copied byte for byte; JSON receipts are rendered as a fenced,
sorted, pretty-printed JSON block (lossless); merge outputs are extracted from the job results' chat.completion content.
No LLM, no network. Idempotent: rerunning overwrites the docs directory's files with the same bytes.

Also here: keep_if_lossy(), the merge guard the session applies to every merge output (see the cycle-0 finding: the
final merge discarded a whole note group as "hallucinated"; the guard keeps the inputs verbatim when a merge output
loses any sha256 value the inputs carried).
"""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path

SCHEMA = 'FRANKIE_BOX_DOCS_INDEX_V1'
SHA_RE = re.compile(r'\b[0-9a-f]{64}\b')
RECEIPTS = ('verify.json', 'labels.json', 'derive.json', 'reading-plan.json', 'reading.json', 'writing.json',
            'engine.json', 'engine-serverless.json')
MARKDOWN = ('merged-notes.md', 'derivation-digest-full.md')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def keep_if_lossy(inputs, output):
    """The merge guard. inputs: the note texts a merge was given; output: what the model returned.
    Returns (text, note): the output when it carries every sha256 value the inputs carried, else the inputs joined
    verbatim with a marker naming what was lost. A merge that dedups keeps every hash at least once, so set
    containment is exactly the rule 'loses no observed fact, number, hash or section id' applied to the hashes."""
    joined = '\n'.join(inputs)
    have = set(SHA_RE.findall(joined))
    got = set(SHA_RE.findall(output or ''))
    lost = sorted(have - got)
    if not output or not output.strip():
        return joined + '\n\n[MERGE KEPT VERBATIM: the merge returned no text; the inputs are kept unchanged]\n', 'empty output'
    if lost:
        note = f'the merge output lost {len(lost)} of {len(have)} sha256 values'
        return joined + f'\n\n[MERGE KEPT VERBATIM: {note}; the inputs are kept unchanged; first lost: {lost[0][:16]}]\n', note
    return output, None


REFUSAL_RE = re.compile(r"^\W{0,40}(I cannot|I can't|I can not|I am unable|I'm unable|I will not|I won't|I must decline|"
                        r"I am not able|I'm not able|As an AI|Sorry, (but )?I)", re.I)
MIN_NOTE_CHARS = 200


def note_verdict(text, outcome):
    """Why a reading note is unusable, or None. Checked before a note is accepted for the merge (chat 6, cycle 0: the
    fourth part's note opened with a refusal and carried an output-incomplete mark; the merge then threw the group away).
    error: the lane returned no result; empty: no or trivial text; refusal: the model declined instead of taking
    notes; incomplete: finish_reason length (the output bound = the remaining context, so a length stop means a runaway)."""
    if outcome.get('error'):
        return 'error'
    if text and REFUSAL_RE.match(text.strip()[:300]):
        return 'refusal'                       # judged before length: a short refusal is a refusal, not an empty note
    if not text or len(text.strip()) < MIN_NOTE_CHARS:
        return 'empty'
    if outcome.get('incomplete'):
        return 'incomplete'
    return None


def split_range(data, start, end):
    """Two halves of data[start:end] on a line boundary at or after the middle; (None, None) if it cannot be split."""
    if end - start < 2:
        return None, None
    mid = (start + end) // 2
    cut = data.find(b'\n', mid, end)
    cut = (cut + 1) if cut != -1 and cut + 1 < end else mid
    if cut <= start or cut >= end:
        return None, None
    return (start, cut), (cut, end)


def _content(result):
    """The text of one job result (chat.completion on both lanes)."""
    try:
        return result['choices'][0]['message'].get('content') or ''
    except Exception:
        return ''


def _json_doc(title, path):
    data = json.loads(path.read_bytes())
    return f'# {title}\n\nSource: `{path.name}` (rendered lossless: sorted keys, pretty-printed).\n\n```json\n' + \
        json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + '\n```\n'


def build_docs(work, out, cycle):
    """Gather the session's documents from `work` into `out` as Markdown plus docs-index.json and README.md."""
    work, out = Path(work), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    entries = []

    def put(name, data, source, what):
        (out / name).write_bytes(data)
        entries.append(dict(name=name, bytes=len(data), sha256=sha256_bytes(data), source=str(source), what=what))

    for notes_dir in sorted(work.glob('notes-*')):
        for p in sorted(notes_dir.glob('note-*.md')):
            put(f'reading-{p.stem}.md', p.read_bytes(), p, 'reading notes for one part of the corpus, verbatim')
    merges_dir = work / 'merges'
    if merges_dir.is_dir():
        for p in sorted(merges_dir.glob('merge-*.md')):
            put(p.name, p.read_bytes(), p, 'one merge output, verbatim (written by the session as it merged)')
    else:
        for jobs in ('serverless-jobs', 'boss-jobs'):
            for d in sorted((work / jobs).glob('merge-*')) if (work / jobs).is_dir() else []:
                r = d / 'result.json'
                if r.is_file():
                    try:
                        text = _content(json.loads(r.read_bytes()))
                    except Exception:
                        text = ''
                    if text:
                        put(f'{d.name}.md', (f'## {d.name} (extracted from {jobs}/{d.name}/result.json)\n\n' + text + '\n').encode('utf-8'),
                            r, 'one merge output, extracted from the job result (best effort for cycles before the session wrote merges itself)')
    for name in MARKDOWN:
        p = work / name
        if p.is_file():
            put(name, p.read_bytes(), p, {'merged-notes.md': 'the merged reading notes the analysis is written from',
                                            'derivation-digest-full.md': "Frankie's derivation digest, every layer of the pin"}[name])
    for name in RECEIPTS:
        p = work / name
        if p.is_file():
            try:
                put(name[:-5] + '.md', _json_doc(name[:-5], p).encode('utf-8'), p, 'a session receipt, rendered as JSON in Markdown')
            except Exception as error:
                entries.append(dict(name=name, error=f'{type(error).__name__}: {error}', source=str(p)))
    corpus = work / 'reading-corpus-full.md'
    referenced = dict(name='reading-corpus-full.md', bytes=corpus.stat().st_size, sha256=sha256_bytes(corpus.read_bytes()),
                      source=str(corpus), what='the rendered reading corpus; referenced by digest, not copied (size; derivable from the request on the box)') \
        if corpus.is_file() else None
    index = dict(schema=SCHEMA, at=time.time(), cycle=cycle, work=str(work), docs=entries, referenced=[referenced] if referenced else [])
    (out / 'docs-index.json').write_text(json.dumps(index, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    lines = [f'# Frankie cycle {cycle}: the session documents', '',
             'Every document the box session produced, as Markdown, gathered by `deploy/aws/box/frankie_box_docs.py` from the',
             f'session work directory `{work}`. Markdown is byte-for-byte; receipts are rendered as JSON blocks; merge',
             'outputs are the model text of each merge job. Nothing here is a summary.', '',
             '| file | bytes | sha256 | what |', '|---|---:|---|---|']
    for e in entries:
        if 'error' in e:
            lines.append(f"| {e['name']} | | | NOT RENDERED: {e['error']} |")
        else:
            lines.append(f"| {e['name']} | {e['bytes']} | {e['sha256'][:16]} | {e['what']} |")
    if referenced:
        lines += ['', f"Referenced, not copied: `{referenced['name']}` {referenced['bytes']} bytes, sha256 {referenced['sha256']}."]
    (out / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return index


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--work', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--cycle', default='00')
    a = p.parse_args()
    index = build_docs(a.work, a.out, a.cycle)
    print(f"docs: {len(index['docs'])} files in {a.out}")
    for e in index['docs']:
        print(f"  {e['name']}: {e.get('bytes', '?')} bytes" + (f" ({e['error']})" if 'error' in e else ''))


if __name__ == '__main__':
    main()
