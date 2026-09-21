"""frankie_box_docs: the docs bundle and the merge guard (structural fixtures only; no market data)."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box' / 'frankie_box_docs.py'
spec = importlib.util.spec_from_file_location('frankie_box_docs', MOD)
docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs)

H1 = 'a' * 64
H2 = 'b' * 64
H3 = 'c' * 64


def test_keep_if_lossy_accepts_a_merge_that_keeps_every_hash():
    text, note = docs.keep_if_lossy([f'x {H1}\n', f'y {H2} and {H1}\n'], f'merged: {H2} {H1}')
    assert note is None and text == f'merged: {H2} {H1}'


def test_keep_if_lossy_keeps_the_inputs_when_a_hash_is_lost():
    inputs = [f'group A {H1}\n', f'I cannot complete this request {H2} {H3}\n']
    text, note = docs.keep_if_lossy(inputs, f'I will merge only the first group: {H1}')
    assert note == 'the merge output lost 2 of 3 sha256 values'
    assert text.startswith('\n'.join(inputs)) and 'MERGE KEPT VERBATIM' in text and H2 in text and H3 in text


def test_keep_if_lossy_keeps_the_inputs_on_empty_output():
    text, note = docs.keep_if_lossy([f'a {H1}'], '')
    assert note == 'empty output' and H1 in text


@pytest.fixture
def work(tmp_path):
    w = tmp_path / 'work'
    notes = w / 'notes-abcdef123456-unbounded'
    notes.mkdir(parents=True)
    (notes / 'note-0000.md').write_text(f'## Notes on part 1/2\n\n- hash {H1}\n', encoding='utf-8')
    (notes / 'note-0001.md').write_text(f'## Notes on part 2/2 [OUTPUT INCOMPLETE]\n\n- hash {H2}\n', encoding='utf-8')
    (w / 'merged-notes.md').write_bytes(('## merged\n\n' + H1 + '\n').encode())
    (w / 'derivation-digest-full.md').write_bytes(b'# digest\n\ntable t: 2 rows\n')
    (w / 'verify.json').write_text(json.dumps(dict(schema='V', request_sha256=H3, cycle_index=0, z=1, a=[1, 2])), encoding='utf-8')
    (w / 'labels.json').write_text('{"schema": "L", "n": 29}', encoding='utf-8')
    (w / 'reading-corpus-full.md').write_bytes(b'corpus bytes\n')
    j = w / 'serverless-jobs' / 'merge-0-0000'
    j.mkdir(parents=True)
    (j / 'result.json').write_text(json.dumps(dict(choices=[dict(message=dict(content=f'merge text {H1} {H2}'))])), encoding='utf-8')
    (w / 'serverless-jobs' / 'read-0000').mkdir()
    (w / 'serverless-jobs' / 'read-0000' / 'result.json').write_text('{"choices": [{"message": {"content": "not a merge"}}]}', encoding='utf-8')
    return w


def test_build_docs_gathers_notes_merges_markdown_and_receipts_with_an_exact_index(work, tmp_path):
    out = tmp_path / 'docs'
    index = docs.build_docs(work, out, '00')
    names = [e['name'] for e in index['docs']]
    assert names == ['reading-note-0000.md', 'reading-note-0001.md', 'merge-0-0000.md', 'merged-notes.md',
                     'derivation-digest-full.md', 'verify.md', 'labels.md']
    assert (out / 'reading-note-0001.md').read_bytes() == (work / 'notes-abcdef123456-unbounded' / 'note-0001.md').read_bytes()
    assert (out / 'merged-notes.md').read_bytes() == (work / 'merged-notes.md').read_bytes()
    assert H1 in (out / 'merge-0-0000.md').read_text() and 'not a merge' not in ''.join(p.read_text() for p in out.glob('*.md'))
    verify_md = (out / 'verify.md').read_text()
    block = verify_md.split('```json\n', 1)[1].split('\n```', 1)[0]
    assert json.loads(block) == json.loads((work / 'verify.json').read_text())
    for e in index['docs']:
        assert e['sha256'] == hashlib.sha256((out / e['name']).read_bytes()).hexdigest() and e['bytes'] == (out / e['name']).stat().st_size
    assert index['referenced'][0]['name'] == 'reading-corpus-full.md' and not (out / 'reading-corpus-full.md').exists()
    readme = (out / 'README.md').read_text()
    assert '| merged-notes.md |' in readme and 'Referenced, not copied' in readme
    assert json.loads((out / 'docs-index.json').read_text())['schema'] == 'FRANKIE_BOX_DOCS_INDEX_V1'


def test_build_docs_prefers_merges_the_session_wrote_and_is_idempotent(work, tmp_path):
    (work / 'merges').mkdir()
    (work / 'merges' / 'merge-0-final.md').write_bytes(b'final merge text\n')
    out = tmp_path / 'docs'
    first = docs.build_docs(work, out, '00')
    names = [e['name'] for e in first['docs']]
    assert 'merge-0-final.md' in names and 'merge-0-0000.md' not in names
    again = docs.build_docs(work, out, '00')
    assert [(e['name'], e['sha256']) for e in again['docs']] == [(e['name'], e['sha256']) for e in first['docs']]


def test_build_docs_survives_a_broken_receipt(work, tmp_path):
    (work / 'derive.json').write_text('{not json', encoding='utf-8')
    index = docs.build_docs(work, tmp_path / 'docs', '00')
    broken = [e for e in index['docs'] if e.get('name') == 'derive.json']
    assert broken and 'error' in broken[0] and 'NOT RENDERED' in (tmp_path / 'docs' / 'README.md').read_text()
