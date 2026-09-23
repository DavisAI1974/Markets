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
MARKDOWN = ('merged-notes.md', 'derivation-digest-full.md', 'comparison.md', 'session-receipts.md')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def keep_if_lossy(inputs, output):
    """The merge guard. inputs: the note texts a merge was given; output: what the model returned.
    Returns (text, note): output only when it preserves every hash and every nonblank input line
    (outside whitespace ignored). Reordering and exact-line deduplication are permitted.
    Otherwise retain all inputs verbatim: echoed hashes or headings alone do not prove coverage."""
    joined = '\n'.join(inputs)
    have = set(SHA_RE.findall(joined))
    got = set(SHA_RE.findall(output or ''))
    lost = sorted(have - got)
    if not output or not output.strip():
        return joined + '\n\n[MERGE KEPT VERBATIM: the merge returned no text; the inputs are kept unchanged]\n', 'empty output'
    if lost:
        note = f'the merge output lost {len(lost)} of {len(have)} sha256 values'
        return joined + f'\n\n[MERGE KEPT VERBATIM: {note}; the inputs are kept unchanged; first lost: {lost[0][:16]}]\n', note
    retained_lines = {line.strip() for line in output.splitlines() if line.strip()}
    missing_parts = [i for i, text in enumerate(inputs)
        if any(line.strip() not in retained_lines for line in text.splitlines() if line.strip())]
    if missing_parts:
        note = f'the merge output lost verbatim lines from {len(missing_parts)} of {len(inputs)} input groups'
        return joined + '\n\n[MERGE KEPT VERBATIM: ' + note + '; the inputs are kept unchanged]\n', note
    return output, None


REFUSAL_RE = re.compile(r"^\W{0,40}(I cannot|I can't|I can not|I am unable|I'm unable|I will not|I won't|I must decline|"
                        r"I am not able|I'm not able|As an AI|Sorry, (but )?I)", re.I)
MIN_NOTE_CHARS = 200
RUNAWAY_WINDOW = 200        # lines examined at the end of a note
RUNAWAY_DISTINCT = 5        # a tail of >= RUNAWAY_MIN lines drawn from <= this many distinct lines is a runaway
RUNAWAY_MIN = 60


def runaway_tail(text):
    """The line index where a repeating tail begins, or None. Cycle 0, part 4: the reader copied the digest's delta
    spellings and repeated `I+1` for the whole remaining context (174 KB); a tail of many lines drawn from a handful
    of distinct lines is not notes. Deterministic; the full text is always kept in the attempt file."""
    lines = (text or '').split('\n')
    tail = [l.strip() for l in lines[-RUNAWAY_WINDOW:]]
    body = [l for l in tail if l]
    if len(body) < RUNAWAY_MIN or len(set(body)) > RUNAWAY_DISTINCT:
        return None
    pool = set(body)
    start = len(lines)
    while start > 0 and (not lines[start - 1].strip() or lines[start - 1].strip() in pool):
        start -= 1
    return start


def deloop(text):
    """The note with a runaway tail removed and a marker in its place (None if there is no runaway)."""
    start = runaway_tail(text)
    if start is None:
        return None
    lines = text.split('\n')
    kept, removed = lines[:start], lines[start:]
    return '\n'.join(kept).rstrip('\n') + f'\n\n[RUNAWAY TAIL REMOVED FROM THIS NOTE: {len(removed)} lines drawn from ' \
        f'{len(set(l.strip() for l in removed if l.strip()))} distinct lines; the full text is kept in the attempt file]\n'


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
    if runaway_tail(text) is not None:
        return 'runaway'
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


def _first_balanced_object(text):
    """The first {...} with balanced braces outside strings, or None."""
    start = text.find('{')
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _close_open(text):
    """Close the strings and brackets a truncated JSON text left open."""
    stack, in_str, esc = [], False, False
    for c in text:
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c in '{[':
            stack.append('}' if c == '{' else ']')
        elif c in '}]' and stack:
            stack.pop()
    out = text + ('"' if in_str else '')
    out = re.sub(r',\s*$', '', out)
    return out + ''.join(reversed(stack))


def tolerant_json(text):
    """(object, repairs) for a model's JSON answer, or (None, repairs). Tries, in order: the text as is (fences stripped);
    the first balanced object; the same with // and /* */ comments and trailing commas removed; the same closed if
    truncated. Every step applied is named in repairs, so the ledger entry says how it was read. Cycle 0's
    knowledge_retrieval_receipts failed at one character and was kept as raw text; this is the rescue (Greg, chat 6)."""
    repairs = []
    body = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', (text or '').strip())
    if body != (text or '').strip():
        repairs.append('fences stripped')
    candidates = [body]
    first = _first_balanced_object(body)
    if first and first != body:
        candidates.append(first)
    for cand, label in ((c, 'first balanced object' if i else '') for i, c in enumerate(candidates)):
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj, repairs + ([label] if label else [])
        except Exception:
            pass
    base = first or body
    cleaned = re.sub(r'(?m)^\s*//[^\n]*$', '', base)                      # line comments on their own line
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.S)                   # block comments
    cleaned = re.sub(r'("(?:[^"\\]|\\.)*")|//[^\n]*', lambda m: m.group(1) or '', cleaned)   # trailing line comments outside strings
    cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)                          # trailing commas
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj, repairs + ['comments and trailing commas removed']
    except Exception:
        pass
    # truncated: close what is open; a dangling partial value is cut back to the last complete element, a few times
    cut = cleaned
    for _ in range(4):
        try:
            obj = json.loads(_close_open(cut))
            if isinstance(obj, dict):
                return obj, repairs + ['truncated object closed']
        except Exception:
            pass
        last = cut.rfind(',')
        if last <= 0:
            break
        cut = cut[:last]
    return None, repairs


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
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(data)
        entries.append(dict(name=name, bytes=len(data), sha256=sha256_bytes(data), source=str(source), what=what))

    current = None
    plan = work / 'reading-plan.json'
    if plan.is_file():
        try:
            current = Path(json.loads(plan.read_bytes())['notes_dir']).name
        except Exception:
            current = None
    for notes_dir in sorted(work.glob('notes-*')):
        this = current is None or notes_dir.name == current
        prefix = 'reading-' if this else f'superseded-{notes_dir.name}-'
        what = 'reading notes for one part of the corpus, verbatim' if this else 'notes of a SUPERSEDED corpus (an earlier restart), verbatim'
        for p in sorted(notes_dir.glob('*.md')):
            put(f'{prefix}{p.stem}.md', p.read_bytes(), p, what if p.name.startswith('note-') else what.replace('reading notes for one part', 'one reading attempt'))
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
                                            'derivation-digest-full.md': "Frankie's derivation digest, every layer of the pin",
                                            'comparison.md': 'the comparison packet: the derived pin layers beside the frozen learned-structure files (session code)',
                                            'session-receipts.md': "the session receipts packet: the session's provider invocations, what it read, the wall it kept (session code)"}[name])
    for name in RECEIPTS:
        p = work / name
        if p.is_file():
            try:
                put(name[:-5] + '.md', _json_doc(name[:-5], p).encode('utf-8'), p, 'a session receipt, rendered as JSON in Markdown')
            except Exception as error:
                entries.append(dict(name=name, error=f'{type(error).__name__}: {error}', source=str(p)))
    classroom = work / 'classroom'
    if classroom.is_dir():
        md = classroom / 'classroom.md'
        if md.is_file():
            put('classroom.md', md.read_bytes(), md, "the Dipole classroom: Frankie's teach-back narratives, cycle summary, correlation review, pair scan and novel findings (the per-cursor observation review is in response.json)")
        for name in ('receipt.json', 'correction-receipt.json'):
            p = classroom / name
            if p.is_file():
                try:
                    put('classroom-' + name[:-5] + '.md', _json_doc('classroom ' + name[:-5], p).encode('utf-8'), p, 'a classroom receipt, rendered as JSON in Markdown')
                except Exception as error:
                    entries.append(dict(name='classroom-' + name, error=f'{type(error).__name__}: {error}', source=str(p)))
    # BR-7 (2026-09-21): the exhaustion/D teach-back beside the classroom; the bedrock run receipt and result as JSON docs;
    # the three exact ledgers copied WHOLE under bedrock/ledgers/ (the digest carries the carrier columns, the bundle the
    # rows); every bedrock layer file referenced by name, bytes and sha256 (its content is in the DIGEST_V6 tables).
    teach = work / 'teach' / 'exhaustion-teachback.md'
    if teach.is_file():
        put('exhaustion-teachback.md', teach.read_bytes(), teach, "the exhaustion and D teach-back: the BOSS on its own bedrock facts and the frozen learned structure, every number checked against the facts by code (session code)")
    bedrock = work / 'bedrock'
    for name in ('receipt.json', 'result.json'):
        p = bedrock / name
        if p.is_file():
            try:
                put('bedrock-' + name[:-5] + '.md', _json_doc('bedrock ' + name[:-5], p).encode('utf-8'), p, 'the bedrock traversal ' + name[:-5] + ' (the pinned producers\' own driver on this cycle\'s rows), rendered as JSON in Markdown')
            except Exception as error:
                entries.append(dict(name='bedrock-' + name, error=f'{type(error).__name__}: {error}', source=str(p)))
    referenced = []
    ledgers = bedrock / 'ledgers'
    if ledgers.is_dir():
        # the three exact ledgers STAY ON THE BOX (git = code, S3 = data; the day's ledgers are about 1 GiB; the pusher ships
        # docs/*.md and the index): witnessed here by name, bytes and sha256 so the published index matches the published tree
        for p in sorted(ledgers.glob('*.jsonl')):
            referenced.append(dict(name=f'bedrock/ledgers/{p.name}', bytes=p.stat().st_size, sha256=sha256_bytes(p.read_bytes()), source=str(p),
                                   what='one exact ledger of the bedrock traversal, whole, in emission order (JSONL, sorted keys), reconciled against its counter on the box; kept on the box under the session work directory (not published: data, not code)'))
    corpus = work / 'reading-corpus-full.md'
    if corpus.is_file():
        referenced.append(dict(name='reading-corpus-full.md', bytes=corpus.stat().st_size, sha256=sha256_bytes(corpus.read_bytes()),
                               source=str(corpus), what='the rendered reading corpus; referenced by digest, not copied (size; derivable from the request on the box)'))
    derive = work / 'derive.json'
    if derive.is_file():
        try:
            layers = json.loads(derive.read_bytes()).get('layers') or {}
        except Exception as error:
            layers = {}
            entries.append(dict(name='derived/*', error=f'the bedrock layer references could not be read from derive.json: {type(error).__name__}: {error}', source=str(derive)))
        for name, entry in sorted(layers.items()):
            path = Path(entry.get('path') or '')
            if entry.get('bedrock') and path.is_file():
                referenced.append(dict(name=f'derived/{path.name}', bytes=path.stat().st_size, sha256=sha256_bytes(path.read_bytes()), source=str(path),
                                       what=f'the bedrock layer file for {name} ({entry.get("status")}); referenced by digest, not copied: its rows are in the DIGEST_V6 bedrock tables of derivation-digest-full.md and in bedrock/ledgers/'))
    index = dict(schema=SCHEMA, at=time.time(), cycle=cycle, work=str(work), docs=entries, referenced=referenced)
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
    for r in referenced:
        lines += ['', f"Referenced, not copied: `{r['name']}` {r['bytes']} bytes, sha256 {r['sha256']}: {r['what']}"]
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
