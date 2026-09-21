"""BR-4 (SPEC_CYCLE0_BEDROCK_20260921.md box-bedrock-derive): the session's derive stage runs the legacy five as it always
did, then the pinned traversal and projection for the pin's bedrock; derive.json carries `bedrock` and the pin
identity; the gate re-derives when the digest schema or the pin moved and REFUSES (receipted) a pin the request does
not carry. Stub session over the real modules and the real pinned producers; no model, box or host call."""
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import _producers as P  # noqa: E402
import test_frankie_box_bedrock as FX  # noqa: E402  (the journal-shaped fixture stream and its container)

BOX = TESTS.parent / 'deploy' / 'aws' / 'box'


def load(name):
    spec = importlib.util.spec_from_file_location(name, BOX / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


spec = importlib.util.spec_from_file_location('frankie_box_boss_session_derive_under_test', BOX / 'frankie_box_boss_session.py')
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)
PINS = TESTS.parent / 'research' / 'kalshi' / 'frankie_boss' / 'knowledge' / 'CYCLE_CALCULATION_PINS.json'
LEGACY = ('legacy_price', 'legacy_native_signed_flow', 'legacy_per_second_roll20', 'legacy_book_imbalance', 'legacy_structure_observables')
# The legacy five on the fixture stream, sha256 of each layer file as the session wrote them BEFORE the bedrock wiring
# (recorded 2026-09-21 from commit 2617d732); the bedrock rides beside them and must not move a byte of them.
LEGACY_WITNESS = {
    'legacy_price': 'b5a67254b6848dca08be8e28dea01556f9516d6e8bc7b9fd1bdf9768d94a0113',
    'legacy_native_signed_flow': 'e5bb17c1041ac0b7e15d299fa075784799b936c96990a4ab1c6a6b5604e0e213',
    'legacy_per_second_roll20': 'bbbc189c76b8258a4fc312128d610b95770804f102b4e9f7d3eb1bb1afaa06c9',
    'legacy_book_imbalance': 'c13b736fbfc019601669386c3899211dd608c2ef7201c400cfa875dbb9529cda',
    'legacy_structure_observables': '8a35036fea171651c081fad4ab29dca332e47cf14d78a7453375840bd129870c'
}


def pin_zero():
    """The committed pin for cycle 0 with the loader's derived fields, built here without the adapter package (torch)."""
    document = json.loads(PINS.read_bytes())
    pin = dict(next(p for p in document['pins'] if 0 in p['cycles']))
    pin['bedrock_layers'] = [layer for entry in pin.get('bedrock', []) for layer in entry['registry_layers']]
    pin['pins_witness'] = dict(path=str(PINS), bytes=PINS.stat().st_size, sha256=hashlib.sha256(PINS.read_bytes()).hexdigest())
    pin['cycle_index'] = 0
    return pin


def stub(tmp_path, monkeypatch, pin=None, request_pin_sha=None):
    producers = P.require_producers()
    monkeypatch.setattr(session, 'PRODUCERS', producers)
    monkeypatch.setattr(session, 'ROOT', tmp_path / 'root')
    load('frankie_box_bedrock').load_producers(producers)      # the Session's own __init__ does this in a fresh process on the box
    pin = pin or pin_zero()
    notes = []
    s = types.SimpleNamespace(work=tmp_path / 'work', out=tmp_path / 'out', cycle='00', day=FX.DAY, _notes=notes)
    s.work.mkdir(); s.out.mkdir()
    s.note = notes.append
    container = dict(FX.container(tmp_path), kinds=dict(INPUT=len(FX.stream()), APPLIED=len(FX.stream())), head='h' * 64, count=2 * len(FX.stream()),
                     format='C15_JOURNAL_PREFIX_SNAPSHOT_V1', head_is_request_source_hash=True, bytes=1)
    s._input_records = lambda rows_path: (FX.stream(), container)
    s._pin = lambda: pin
    s._producer_module = session.Session._producer_module
    s._producer_witnesses = session.Session._producer_witnesses
    s._pin_matches_request = lambda: session.Session._pin_matches_request(s)
    s._derive_needed = lambda: session.Session._derive_needed(s)
    s._derive_bedrock = lambda *args: session.Session._derive_bedrock(s, *args)
    s.request = dict(attachment=dict(feedback_contract=dict(source_hash='h' * 64),
                                     calculation_pin_witness=dict(sha256=request_pin_sha or pin['pins_witness']['sha256'], cycle_index=0, group=pin['group'])))
    return s


def test_derive_writes_the_legacy_five_and_the_twenty_bedrock_layers_and_records_the_bedrock(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    torch_before = 'torch' in sys.modules
    receipt = session.Session.derive(s)
    derived = s.work / 'derived'
    names = sorted(p.stem for p in derived.glob('*.json'))
    assert len(names) == 25 and set(LEGACY) <= set(names) and set(FX.BEDROCK_LAYERS) <= set(names)
    assert set(receipt['layers']) == set(names)
    assert receipt['bedrock']['layers'] == list(FX.BEDROCK_LAYERS)
    assert receipt['bedrock']['receipt']['sha256'] and (s.work / 'bedrock' / 'receipt.json').is_file()
    assert receipt['bedrock']['producers_commit'] == P.PIN and receipt['bedrock']['cadence_policy'] == 'NeverInvoke'
    assert receipt['bedrock']['candidate_warmup_seconds'] == 900 and receipt['bedrock']['span_seconds'] == pytest.approx(10.0)
    assert receipt['bedrock']['groups'] == 3 and receipt['bedrock']['sections_fed']['candidate_unit_events'] == 0
    assert receipt['bedrock']['bedrock_groups'] == ['derived_geometry', 'prebirth_opportunity', 'causal_clocks']
    for name in ('exact_member_rows.jsonl', 'exact_lifecycle_rows.jsonl', 'legacy_observable_rows.jsonl'):
        assert receipt['bedrock']['ledgers'][name]['sha256'] and (s.work / 'bedrock' / 'ledgers' / name).is_file()
    assert receipt['pin_identity'] == dict(sha256=pin_zero()['pins_witness']['sha256'], cycle_index=0, group='legacy_observable_crosswalk',
                                           bedrock_layers=list(FX.BEDROCK_LAYERS))
    for name in FX.BEDROCK_LAYERS:
        entry = receipt['layers'][name]
        assert entry['status'] in ('derived', 'could_not') and entry['path'] == str(derived / f'{name}.json') and len(entry['sha256']) == 64
        assert (entry['reason'] is None) == (entry['status'] == 'derived'), name
    assert receipt['layers']['clock_lock_time']['status'] == 'could_not' and receipt['layers']['clock_lock_time']['reason'].startswith('NO_PRODUCER_FOUND')
    assert receipt['layers']['prebirth_predecessor_at_risk_state']['status'] == 'could_not' and '900 s' in receipt['layers']['prebirth_predecessor_at_risk_state']['reason']
    assert receipt['layers']['derived_d_family_geometry']['status'] == 'derived'
    digest = (s.work / 'derivation-digest-full.md').read_text(encoding='utf-8')
    assert digest.startswith('# Derivation digest ')
    for name in FX.BEDROCK_LAYERS:
        assert f'- {name}: ' in digest
    assert any(n.startswith('bedrock: ') for n in s._notes)
    assert ('torch' in sys.modules) == torch_before   # this path never imports torch (the hidden-torch run proves it outright)


def test_the_legacy_five_do_not_move_a_byte(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    session.Session.derive(s)
    got = {name: hashlib.sha256((s.work / 'derived' / f'{name}.json').read_bytes()).hexdigest() for name in LEGACY}
    assert got == LEGACY_WITNESS


def test_a_pin_without_bedrock_derives_the_legacy_five_only(tmp_path, monkeypatch):
    pin = pin_zero()
    pin.pop('bedrock'); pin['bedrock_layers'] = []
    s = stub(tmp_path, monkeypatch, pin=pin)
    receipt = session.Session.derive(s)
    assert sorted(p.stem for p in (s.work / 'derived').glob('*.json')) == sorted(LEGACY)
    assert receipt['bedrock'] is None and not (s.work / 'bedrock').exists()


def test_derive_refuses_with_a_receipt_a_pin_the_request_does_not_carry(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch, request_pin_sha='0' * 64)
    with pytest.raises(ValueError, match='the request was rendered under a different calculation pin'):
        session.Session.derive(s)
    refusals = list(s.work.glob('derive-refusal-*.json'))
    assert len(refusals) == 1
    body = json.loads(refusals[0].read_bytes())
    assert body['schema'] == 'FRANKIE_BOX_DERIVE_REFUSAL_RECEIPT_V1' and body['request_pin_sha256'] == '0' * 64
    assert body['checkout_pin_sha256'] == pin_zero()['pins_witness']['sha256']
    assert not (s.work / 'derived').exists() or not list((s.work / 'derived').glob('*.json'))


def test_derive_refuses_a_request_that_carries_no_pin_witness(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    del s.request['attachment']['calculation_pin_witness']
    with pytest.raises(ValueError, match='carries no calculation pin witness'):
        session.Session.derive(s)


def test_the_derive_gate_re_derives_on_a_missing_or_stale_digest_or_a_moved_pin(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    sys.path.insert(0, str(BOX))
    import frankie_box_digest_render as DG
    digest = s.work / 'derivation-digest-full.md'
    assert s._derive_needed() == (True, 'no derivation digest')
    digest.write_text('# Derivation digest DIGEST_V1 (old)\n')
    assert s._derive_needed() == (True, 'the digest is not ' + DG.SCHEMA)
    digest.write_text('# Derivation digest ' + DG.SCHEMA + ' (current)\n')
    assert s._derive_needed() == (True, 'no derive.json')
    (s.work / 'derive.json').write_text(json.dumps(dict(layers={})))
    assert s._derive_needed() == (True, 'derive.json carries no pin identity')
    (s.work / 'derive.json').write_text(json.dumps(dict(layers={}, pin_identity=dict(sha256='0' * 64, cycle_index=0, group='legacy_observable_crosswalk', bedrock_layers=[]))))
    assert s._derive_needed() == (True, 'the calculation pin moved since the derivation')
    (s.work / 'derive.json').write_text(json.dumps(dict(layers={}, pin_identity=dict(sha256=pin_zero()['pins_witness']['sha256'], cycle_index=0,
                                                                                  group='legacy_observable_crosswalk', bedrock_layers=[]))))
    assert s._derive_needed() == (True, 'the derivation does not carry this pin\'s bedrock')
    (s.work / 'derive.json').write_text(json.dumps(dict(layers={}, bedrock=dict(layers=list(FX.BEDROCK_LAYERS)), pin_identity=dict(
        sha256=pin_zero()['pins_witness']['sha256'], cycle_index=0, group='legacy_observable_crosswalk', bedrock_layers=list(FX.BEDROCK_LAYERS)))))
    assert s._derive_needed() == (False, 'current')


def test_the_run_loop_uses_the_gate_and_the_docstring_names_the_bedrock():
    text = (BOX / 'frankie_box_boss_session.py').read_text()
    assert 'needed, why = self._derive_needed()' in text and 'if needed:' in text
    assert 'bedrock' in text.split('class Session')[0].lower()
