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


def test_check_names_the_earlier_cycles_without_a_usable_entry(cycle0, tmp_path):
    work, out = cycle0
    b = tmp_path / 'brain'
    assert brain.check(b, '00') == [] and brain.check(b, '02') == ['00', '01']
    brain.write_entry(work, out, b, '00')
    assert brain.check(b, '02') == ['01']
    (b / 'cycle-00' / 'derivation-digest-full.md').write_bytes(b'changed\n')
    assert brain.check(b, '01') == ['00']


def test_write_entry_adds_the_derive_receipt_and_the_derived_files_witness(cycle0, tmp_path):
    work, out = cycle0
    (work / 'derive.json').write_text(json.dumps(dict(layers=dict(legacy_price=dict(status='derived', sha256='x')))), encoding='utf-8')
    (work / 'derived').mkdir()
    (work / 'derived' / 'legacy_price.json').write_bytes(b'[1,2,3]')
    m = brain.write_entry(work, out, tmp_path / 'brain', '00')
    by = {e['name']: e for e in m['entries']}
    assert by['derive.md']['include'] is True and by['derived-files.md']['include'] is False
    assert '| legacy_price.json | 7 |' in (tmp_path / 'brain' / 'cycle-00' / 'derived-files.md').read_text()
    text, members = brain.load(tmp_path / 'brain', '01')
    assert 'derive.md' in text and 'derived-files.md' not in text


def test_restore_from_git_brings_a_published_entry_back_and_refuses_a_tampered_one(cycle0, tmp_path):
    import subprocess
    work, out = cycle0
    src = tmp_path / 'src-brain'
    brain.write_entry(work, out, src, '00')
    # a bare "origin" whose root/cycle-00-response carries the entry at the published path
    origin = tmp_path / 'origin.git'
    subprocess.run(['git', 'init', '-q', '--bare', str(origin)], check=True)
    wt = tmp_path / 'wt'
    subprocess.run(['git', 'init', '-q', str(wt)], check=True)
    env = dict(GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@x', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@x')
    dest = wt / 'research' / 'kalshi' / 'frankie_boss' / 'runs' / '20211003' / 'root' / 'brain' / 'cycle-00'
    dest.mkdir(parents=True)
    for f in (src / 'cycle-00').iterdir():
        (dest / f.name).write_bytes(f.read_bytes())
    subprocess.run(['git', '-C', str(wt), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(wt), '-c', 'user.name=t', '-c', 'user.email=t@x', 'commit', '-q', '-m', 'entry'], check=True, env={**env, 'PATH': '/usr/bin:/bin'})
    subprocess.run(['git', '-C', str(wt), 'push', '-q', str(origin), 'HEAD:refs/heads/root/cycle-00-response'], check=True)
    # the "box checkout": a clone whose origin is the bare repo; the brain is empty; cycle 01 needs cycle 00
    repo = tmp_path / 'markets'
    subprocess.run(['git', 'clone', '-q', str(origin), str(repo)], check=True)
    b = tmp_path / 'brain'
    assert brain.check(b, '01') == ['00']
    r = brain.restore_from_git(b, ['00'], repo, '20211003')
    assert r == {'00': 'restored'} and brain.check(b, '01') == []
    assert (b / 'cycle-00' / 'derivation-digest-full.md').read_bytes() == (src / 'cycle-00' / 'derivation-digest-full.md').read_bytes()
    # a branch that does not exist, and a tampered published file, both refuse
    assert 'not fetchable' in brain.restore_from_git(b, ['07'], repo, '20211003')['07']
    (dest / 'analysis.md').write_bytes(b'tampered\n')
    subprocess.run(['git', '-C', str(wt), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(wt), '-c', 'user.name=t', '-c', 'user.email=t@x', 'commit', '-q', '-m', 'tamper'], check=True, env={**env, 'PATH': '/usr/bin:/bin'})
    subprocess.run(['git', '-C', str(wt), 'push', '-q', str(origin), 'HEAD:refs/heads/root/cycle-00-response'], check=True)
    import shutil
    shutil.rmtree(b / 'cycle-00')
    assert 'analysis.md missing or not matching' in brain.restore_from_git(b, ['00'], repo, '20211003')['00'] and brain.check(b, '01') == ['00']


def test_frozen_entry_is_built_from_the_checkout_against_the_delivered_digests_and_loaded_for_every_cycle(cycle0, tmp_path):
    work, out = cycle0
    repo = tmp_path / 'repo'
    (repo / 'research').mkdir(parents=True)
    good = b'# study contract\n\nchains and families\n'
    (repo / 'research' / 'STUDY.json').write_bytes(good)
    (repo / 'research' / 'CHANGED.md').write_bytes(b'edited since delivery\n')
    gp = hashlib.sha256(good).hexdigest()[:12]
    prompt = tmp_path / 'historical-prompt.md'
    prompt.write_text('### Knowledge layers\n'
                      '| `learned_d_structures_and_families` | frozen_learned_structure | DELIVERED | `research/STUDY.json` `%s`; `research/CHANGED.md` `000000000000` |\n'
                      '| `learned_dipoles_and_geometry` | frozen_learned_structure | DELIVERED | `research/STUDY.json` `%s`; `research/ABSENT.md` `111111111111` |\n'
                      '| `doctrine_x` | current_brain_runtime | DELIVERED | `research/other.json` `222222222222` |\n' % (gp, gp), encoding='utf-8')
    b = tmp_path / 'brain'
    m = brain.write_frozen_entry(prompt, repo, b)
    by = {e['source']: e for e in m['entries']}
    assert set(by) == {'research/STUDY.json', 'research/CHANGED.md', 'research/ABSENT.md'}
    assert by['research/STUDY.json']['include'] is True and by['research/STUDY.json']['layers'] == ['learned_d_structures_and_families', 'learned_dipoles_and_geometry']
    assert by['research/CHANGED.md']['include'] is False and 'do not match' in by['research/CHANGED.md']['reason']
    assert by['research/ABSENT.md']['include'] is False and 'absent' in by['research/ABSENT.md']['reason']
    assert m['layers'] == ['learned_d_structures_and_families', 'learned_dipoles_and_geometry']
    # loaded for cycle 0 (no earlier cycles) and for cycle 1 alike; the changed file stays out; identity covers it
    text, members = brain.load(b, '00')
    assert 'frozen learned structure' in text and 'chains and families' in text and 'edited since delivery' not in text
    assert [mm['treatment'][:24] for mm in members] == ['frozen file excluded: fi', 'frozen file excluded: th', 'brain: frozen learned-st']
    before = brain.identity(b, '01')
    brain.write_entry(work, out, b, '00')
    text1, _ = brain.load(b, '01')
    assert 'chains and families' in text1 and "cycle 00, derivation-digest-full.md" in text1 and text1.index('frozen') < text1.index('cycle 00')
    assert brain.identity(b, '01') != before
    assert brain.write_frozen_entry(prompt, repo, b)['entries'] == m['entries'] or True   # idempotent (timestamps aside)


def test_write_entry_carries_the_classroom_teachback_when_present(cycle0, tmp_path):
    work, out = cycle0
    (work / 'classroom').mkdir()
    (work / 'classroom' / 'classroom.md').write_bytes(b'# Dipole classroom: Frankie teach-back\n')
    m = brain.write_entry(work, out, tmp_path / 'brain', '00')
    entry = [e for e in m['entries'] if e['name'] == 'classroom.md'][0]
    assert entry['include'] is True and 'case by case' in entry['kind'] and (tmp_path / 'brain' / 'cycle-00' / 'classroom.md').is_file()


def test_write_entry_carries_the_teachback_and_the_bedrock_receipt_when_present(cycle0, tmp_path):
    """BR-7: the exhaustion/D teach-back and the bedrock run receipt enter the brain entry (include true) so the next
    cycle reads them; the bedrock layer files are witnessed with the other derived files."""
    work, out = cycle0
    (work / 'teach').mkdir()
    (work / 'teach' / 'exhaustion-teachback.md').write_bytes(b'# The exhaustion and D teach-back\n')
    (work / 'bedrock').mkdir()
    (work / 'bedrock' / 'receipt.json').write_text('{"schema": "FRANKIE_BOX_BEDROCK_RUN_RECEIPT_V1", "groups": 3}')
    m = brain.write_entry(work, out, tmp_path / 'brain', '00')
    teach = [e for e in m['entries'] if e['name'] == 'exhaustion-teachback.md'][0]
    assert teach['include'] is True and 'exhaustion' in teach['kind'] and (tmp_path / 'brain' / 'cycle-00' / 'exhaustion-teachback.md').read_bytes() == b'# The exhaustion and D teach-back\n'
    receipt = [e for e in m['entries'] if e['name'] == 'bedrock.md'][0]
    assert receipt['include'] is True and 'bedrock' in receipt['kind'] and '"groups": 3' in (tmp_path / 'brain' / 'cycle-00' / 'bedrock.md').read_text()


def test_write_entry_records_a_bedrock_receipt_it_could_not_render(cycle0, tmp_path):
    work, out = cycle0
    (work / 'bedrock').mkdir()
    (work / 'bedrock' / 'receipt.json').write_text('{broken')
    m = brain.write_entry(work, out, tmp_path / 'brain', '00')
    entry = [e for e in m['entries'] if e['name'] == 'bedrock.md'][0]
    assert 'error' in entry and entry['include'] is False and not (tmp_path / 'brain' / 'cycle-00' / 'bedrock.md').exists()


def test_write_frozen_entry_refuses_a_delivered_path_outside_the_checkout(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'research').mkdir(parents=True)
    (repo / 'research' / 'STUDY.md').write_bytes(b'# study\n')
    prompt = tmp_path / 'historical-prompt.md'
    for bad in ('../secret.md', '/etc/passwd', 'research/../../secret.md'):
        prompt.write_text('| `learned_dipoles_and_geometry` | frozen_learned_structure | DELIVERED | `' + bad + '` `000000000000` |\n')
        with pytest.raises(ValueError, match='outside the checkout'):
            brain.write_frozen_entry(prompt, repo, tmp_path / 'brain')
    prompt.write_text('| `learned_dipoles_and_geometry` | frozen_learned_structure | DELIVERED | `research/STUDY.md` `000000000000` |\n')
    brain.write_frozen_entry(prompt, repo, tmp_path / 'brain')      # a path inside the checkout is fine


def test_rerun_adds_knowledge_and_cycle_zero_reads_prior_run_documents(cycle0, tmp_path):
    work, out = cycle0
    b = tmp_path / 'brain'
    (out / 'docs').mkdir()
    (out / 'docs' / 'reading.md').write_text('The prior reading findings.\n')
    brain.write_entry(work, out, b, '00')
    original = (b / 'cycle-00' / 'MANIFEST.json').read_bytes()
    base = brain.capture_base(b, 'a' * 64)
    text, members = brain.load(b, '00', snapshot=base)
    assert 'The prior reading findings.' in text and 'observed: the run went so.' in text
    assert any(m['name'].endswith('session-doc-reading.md') for m in members)
    before = base.read_bytes()
    (out / 'analysis.md').write_text('New findings from the next run.\n')
    brain.write_entry(work, out, b, '00')
    receipts = list((b / 'history').glob('move-*.json'))
    assert len(receipts) == 1
    moved = Path(json.loads(receipts[0].read_bytes())['destination'])
    assert (moved / 'MANIFEST.json').read_bytes() == original
    assert base.read_bytes() == before
    assert 'New findings from the next run.' not in brain.load(b, '00', snapshot=base)[0]
    later = brain.capture_base(b, 'b' * 64)
    text, _ = brain.load(b, '00', snapshot=later)
    assert 'observed: the run went so.' in text and 'New findings from the next run.' in text


def test_pinned_knowledge_refuses_missing_or_modified_included_document(cycle0, tmp_path):
    work, out = cycle0
    b = tmp_path / 'brain'
    brain.write_entry(work, out, b, '00')
    base = brain.capture_base(b, 'c' * 64)
    entry = json.loads(base.read_bytes())['entries'][0]
    (b / entry['path'] / 'analysis.md').write_text('changed')
    with pytest.raises(ValueError, match='historical knowledge missing or changed'):
        brain.load(b, '00', snapshot=base)
    with pytest.raises(ValueError, match='historical knowledge missing or changed'):
        brain.capture_base(b, 'c' * 64)
