"""Frankie's brain (frankie_box_brain): one entry per cycle, loaded into the next cycle's corpus when included and intact."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box' / 'frankie_box_brain.py'
spec = importlib.util.spec_from_file_location('frankie_box_brain', MOD)
brain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brain)


@pytest.fixture
def cycle0(tmp_path):
    work, out = tmp_path / 'work', tmp_path / 'out'
    work.mkdir(); out.mkdir()
    (work / 'derivation-digest-full.md').write_bytes(b'# digest\n\nlayer legacy_price: derived 57027 rows\n')
    (out / 'analysis.md').write_bytes(b'# analysis\n\nobserved: the run went so.\n')
    (out / 'response.json').write_text(json.dumps(dict(lessons=['# analysis text', dict(ledger='calculation_accounting', layers=[dict(layer='legacy_price', status='derived')]),
                                                                dict(ledger='output_first_locks_and_no_locks', rows=[])])), encoding='utf-8')
    return work, out


def test_write_entry_records_digest_accounting_ledgers_and_analysis_with_digests(cycle0, tmp_path):
    work, out = cycle0
    m = brain.write_entry(work, out, tmp_path / 'brain', '00')
    names = [e['name'] for e in m['entries']]
    assert names == ['derivation-digest-full.md', 'accounting-and-ledgers.md', 'analysis.md'] and all(e['include'] for e in m['entries'])
    d = tmp_path / 'brain' / 'cycle-00'
    for e in m['entries']:
        assert hashlib.sha256((d / e['name']).read_bytes()).hexdigest() == e['sha256'] and e['bytes'] == (d / e['name']).stat().st_size
    acc = (d / 'accounting-and-ledgers.md').read_text()
    assert '## calculation_accounting' in acc and '## output_first_locks_and_no_locks' in acc and '# analysis text' not in acc
    assert json.loads((d / 'MANIFEST.json').read_text())['schema'] == 'FRANKIE_BOX_BRAIN_ENTRY_V1'


def test_write_entry_refuses_without_the_digest(tmp_path):
    (tmp_path / 'work').mkdir(); (tmp_path / 'out').mkdir()
    with pytest.raises(FileNotFoundError):
        brain.write_entry(tmp_path / 'work', tmp_path / 'out', tmp_path / 'brain', '00')


def test_load_carries_only_earlier_included_intact_entries_into_the_corpus(cycle0, tmp_path):
    work, out = cycle0
    b = tmp_path / 'brain'
    brain.write_entry(work, out, b, '00')
    brain.write_entry(work, out, b, '01')          # the current cycle's own entry must not be loaded into itself
    text, members = brain.load(b, '01')
    assert "## Frankie's brain: cycle 00, derivation-digest-full.md" in text and 'legacy_price: derived 57027 rows' in text
    assert "cycle 00, accounting-and-ledgers.md" in text and "cycle 00, analysis.md" in text and 'cycle 01' not in text
    assert [m['name'] for m in members] == ['brain-cycle-00-derivation-digest-full.md', 'brain-cycle-00-accounting-and-ledgers.md', 'brain-cycle-00-analysis.md']
    assert brain.load(b, '00') == ('', [])
    # case by case: include false keeps an entry out; a tampered file is skipped, never loaded
    m = json.loads((b / 'cycle-00' / 'MANIFEST.json').read_text())
    m['entries'][2]['include'] = False
    (b / 'cycle-00' / 'MANIFEST.json').write_text(json.dumps(m), encoding='utf-8')
    (b / 'cycle-00' / 'accounting-and-ledgers.md').write_bytes(b'tampered\n')
    text, members = brain.load(b, '01')
    assert 'analysis.md' not in text and 'tampered' not in text and 'legacy_price' in text
    assert [m['treatment'][:20] for m in members] == ['brain: prior cycle c', 'brain entry bytes di', 'brain entry excluded']


def test_identity_changes_with_the_included_set(cycle0, tmp_path):
    work, out = cycle0
    b = tmp_path / 'brain'
    assert brain.identity(b, '01') == brain.identity(tmp_path / 'nowhere', '01')
    brain.write_entry(work, out, b, '00')
    one = brain.identity(b, '01')
    assert one != brain.identity(b, '00') and len(one) == 16
    m = json.loads((b / 'cycle-00' / 'MANIFEST.json').read_text()); m['entries'][0]['include'] = False
    (b / 'cycle-00' / 'MANIFEST.json').write_text(json.dumps(m), encoding='utf-8')
    assert brain.identity(b, '01') != one
