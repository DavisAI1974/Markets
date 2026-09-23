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
# (recorded 2026-09-21 at commit 2617d732, whose derive() is the base 082e2ec9's unchanged); the bedrock rides beside them
# and must not move a byte of them. The paired-run test below pins the same invariant without a recorded constant.
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
    load('frankie_box_bedrock').load_producers(producers)      # on the box, run()/crosswalk_records do this inside the fresh session process
    pin = pin or pin_zero()
    notes = []
    s = types.SimpleNamespace(work=tmp_path / 'work', out=tmp_path / 'out', cycle='00', day=FX.DAY, _notes=notes)
    s.work.mkdir(parents=True); s.out.mkdir(parents=True)
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
    s._write_digest = lambda *args: session.Session._write_digest(s, *args)
    s.request = dict(attachment=dict(feedback_contract=dict(source_hash='h' * 64),
                                     calculation_pin_witness=dict(sha256=request_pin_sha or pin['pins_witness']['sha256'], cycle_index=0, group=pin['group'])))
    return s


def test_derive_writes_the_legacy_five_and_the_twenty_bedrock_layers_and_records_the_bedrock(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    torch_before = 'torch' in sys.modules
    receipt = session.Session.derive(s)
    derived = s.work / 'derived'
    names = sorted(p.stem for p in derived.glob('*.json'))
    assert len(names) == 27 and set(LEGACY) <= set(names) and set(FX.BEDROCK_LAYERS) <= set(names)
    assert {'bedrock_section_4_2', 'bedrock_section_4_4'} <= set(names)        # BR-9: the two dropped sections as files beside the twenty layers
    assert set(receipt['layers']) == set(names)
    for name in ('bedrock_section_4_2', 'bedrock_section_4_4'):
        entry = receipt['layers'][name]
        assert entry['bedrock'] is True and entry['status'] == 'derived' and entry['reason'] is None and len(entry['sha256']) == 64
    assert receipt['layers']['bedrock_section_4_2']['count'] == 7 and receipt['layers']['bedrock_section_4_4']['count'] == 6
    assert receipt['bedrock']['sections'] == dict(bedrock_section_4_2='derived', bedrock_section_4_4='derived')
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
    for table in ('bedrock.lifecycle.mirror', 'bedrock.companions.4.2', 'bedrock.declarations.4.2', 'bedrock.first_last.4.2', 'bedrock.matching_rule.4.4'):
        assert f'### table {table}: ' in digest, table                              # BR-9: the two sections read as TABLES
    assert '### table bedrock.lifecycle.mirror: 6 rows' in digest and '### table bedrock.companions.4.2: 6 rows' in digest
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


# ---- BR-5: the digest carries the bedrock tables; ACTION=derive_only measures it (checkpoint E) ----------------------

def test_derive_writes_a_v6_digest_with_the_bedrock_tables(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    session.Session.derive(s)
    sys.path.insert(0, str(BOX))
    import frankie_box_digest_render as DG
    text = (s.work / 'derivation-digest-full.md').read_text(encoding='utf-8')
    assert text.startswith('# Derivation digest DIGEST_V6 ')
    assert '## Bedrock' in text and '### table bedrock.layers' in text and '### table bedrock.members' in text and '### table bedrock.run' in text
    assert 'verdict over this slice: ACCEPTED, no failed gate' in text
    assert '### table bedrock.lifecycle.lineage' in text and '### table bedrock.lifecycle.flow_substrate' in text
    parsed = DG.parse_digest(text)
    assert [r['group_index'] for r in parsed['bedrock.members']] == [0, 1, 2]
    assert 'candidate_family_id' in parsed['bedrock.members'][0]['structure'] and 'decision_ts_recv_ns' in parsed['bedrock.members'][0]['clocks']
    index = {r['layer']: r for r in parsed['bedrock.layers']}
    assert set(index) == set(FX.BEDROCK_LAYERS) | {'bedrock_section_4_2', 'bedrock_section_4_4'} and index['clock_lock_time']['status'] == 'could_not'
    assert 'episode' in index['derived_roll20_and_dipole_state']['partial']
    # BR-9: the two sections as tables, the fixture run's own counts (6 companion rows = one per 4.2 measure, 1 first/last pair,
    # 6 mirror rows = 3 PENDING offers at GROUP_CLOSE + 3 UNMATCHED at STREAM_END)
    assert index['bedrock_section_4_2']['status'] == 'derived' and index['bedrock_section_4_4']['lifecycle_sections'] == 'mirror'
    assert len(parsed['bedrock.companions.4.2']) == 6 and sorted(r['measure'] for r in parsed['bedrock.companions.4.2']) == [
        'actions_per_group', 'book_level_count', 'book_order_count', 'book_spread_raw', 'book_total_depth', 'relative_imbalance']
    assert len(parsed['bedrock.declarations.4.2']) == 6 and len(parsed['bedrock.first_last.4.2']) == 1
    assert parsed['bedrock.first_last.4.2'][0]['source_day'] == FX.DAY
    assert [r['disposition'] for r in parsed['bedrock.lifecycle.mirror']] == ['PENDING'] * 3 + ['UNMATCHED'] * 3
    assert parsed['bedrock.matching_rule.4.4'][0]['rule_id'] == 'MIRROR_EXACT_SIDE_SWAP_NEAREST_COORDINATE_V1'


def test_measure_digest_reports_tokens_and_parts_and_files_the_measurement(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    s._measure_digest = lambda: session.Session._measure_digest(s)
    (s.work / 'derivation-digest-full.md').write_text('# Derivation digest DIGEST_V6 (x)\n' + 'row ' * 100_000, encoding='utf-8')
    measurement = s._measure_digest()
    assert measurement['schema'] == 'FRANKIE_BOX_DERIVE_ONLY_MEASUREMENT_V1' and measurement['digest']['bytes'] == (s.work / 'derivation-digest-full.md').stat().st_size
    assert measurement['digest']['tokens'] > 0 and measurement['digest']['token_basis'] in ('granite tokenizer', 'estimate: bytes / %s' % session.BYTES_PER_TOKEN)
    assert measurement['digest']['parts_at_%d_tokens' % session.PART_INPUT_TOKENS] == -(-measurement['digest']['tokens'] // session.PART_INPUT_TOKENS)
    assert json.loads((s.work / 'derive-only-measurement.json').read_bytes())['digest']['tokens'] == measurement['digest']['tokens']
    assert any(n.startswith('DERIVE_ONLY digest ') for n in s._notes)


def test_derive_only_is_a_stage_that_derives_and_measures_without_the_engine():
    text = (BOX / 'frankie_box_boss_session.py').read_text()
    assert "choices=('run', 'preflight', 'correction', 'derive_only')" in text
    block = text.split("if stage == 'derive_only':")[1].split("self.phase('verified'")[0]
    assert 'self.derive()' in block and 'self._measure_digest()' in block and 'engine_reach' not in block and 'serverless' not in block and 'return' in block
    sh = (BOX / 'frankie_box_session.sh').read_text()
    assert 'derive_only) derive_only ;;' in sh and '--stage derive_only' in sh and 'derive_only()' in sh
    assert 'ACTION must be start, status, preflight, verify, restart_session, fetch_correction, correction or derive_only' in sh
    derive = sh.split('derive_only() {', 1)[1].split('fetch_correction() {', 1)[0]
    assert 'checkout_markets || return 2' in derive
    assert derive.index('checkout_markets || return 2') < derive.index('--stage derive_only')
    assert '"frankie-heartbeat-$CYCLE" "frankie-correction-$CYCLE"' in derive
    assert 'M="$S/work-$CYCLE/derive-only-measurement.json"' in sh and 'git worktree' not in sh


def test_the_legacy_five_are_byte_identical_with_and_without_the_bedrock(tmp_path, monkeypatch):
    """The bedrock rides BESIDE the legacy five, never through them: the same stream derived with the bedrock and without
    it writes the same five files, byte for byte (no recorded constant needed)."""
    with_bedrock = stub(tmp_path / 'a', monkeypatch)
    session.Session.derive(with_bedrock)
    pin = pin_zero(); pin.pop('bedrock'); pin['bedrock_layers'] = []
    without = stub(tmp_path / 'b', monkeypatch, pin=pin)
    session.Session.derive(without)
    for name in LEGACY:
        assert (with_bedrock.work / 'derived' / f'{name}.json').read_bytes() == (without.work / 'derived' / f'{name}.json').read_bytes(), name


def test_a_current_derivation_under_a_pin_the_request_does_not_carry_is_refused_not_reused(tmp_path, monkeypatch):
    """Review finding: the gate compared derive.json with the CHECKOUT pin only; a current derivation could be reused under a
    request rendered for another pin. The request's pin is checked first, whatever the derivation's state."""
    s = stub(tmp_path, monkeypatch)
    session.Session.derive(s)
    assert s._derive_needed() == (False, 'current')
    s.request['attachment']['calculation_pin_witness']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='the request was rendered under a different calculation pin'):
        s._derive_needed()
    assert len(list(s.work.glob('derive-refusal-*.json'))) == 1
    s.request['attachment']['calculation_pin_witness']['sha256'] = pin_zero()['pins_witness']['sha256']
    s.request['attachment']['calculation_pin_witness']['group'] = 'derived_geometry'
    with pytest.raises(ValueError, match='names cycle 0 group derived_geometry; this checkout derives cycle 0 group legacy_observable_crosswalk'):
        s._derive_needed()
    refusals = list(s.work.glob('derive-refusal-*.json'))
    assert len(refusals) == 2 and len({p.name for p in refusals}) == 2


def test_the_run_loop_checks_the_request_pin_right_after_verify_before_any_engine_reach():
    text = (BOX / 'frankie_box_boss_session.py').read_text()
    run = text.split('    def _run(self, stage):')[1]
    assert run.index('self.verify()') < run.index('self._pin_matches_request()') < run.index('self.brain_ready()') < run.index('self.engine_reach()')


def test_a_second_derive_moves_the_earlier_derived_files_aside_with_a_receipt(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    session.Session.derive(s)
    first = (s.work / 'derived' / 'legacy_price.json').read_bytes()
    session.Session.derive(s)
    moved = [p for p in s.work.iterdir() if p.name.startswith('derived-superseded-')]
    receipts = list(s.work.glob('derived-supersede-*.json'))
    assert len(moved) == 1 and len(receipts) == 1 and (moved[0] / 'legacy_price.json').read_bytes() == first
    assert json.loads(receipts[0].read_bytes())['moved_to'] == str(moved[0])
    assert any('moved aside' in n for n in s._notes) and (s.work / 'derived' / 'legacy_price.json').read_bytes() == first
    # the derivation's receipt (derive.json) is moved with its directory, never overwritten in place
    receipt = json.loads(receipts[0].read_bytes())
    assert (moved[0] / 'derive.json').is_file() and 'derive.json' in [Path(x).name for x in receipt['moved_files']]
    assert json.loads((moved[0] / 'derive.json').read_bytes())['pin_identity'] == json.loads((s.work / 'derive.json').read_bytes())['pin_identity']
    assert receipt['reason'].startswith('the layers are derived again')


def test_a_derive_that_fails_after_the_move_aside_never_leaves_a_current_derivation(tmp_path, monkeypatch):
    s = stub(tmp_path, monkeypatch)
    session.Session.derive(s)
    assert s._derive_needed()[0] is False
    monkeypatch.setattr(s, '_derive_bedrock', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('traversal died')))
    with pytest.raises(RuntimeError, match='traversal died'):
        session.Session.derive(s)
    needed, why = s._derive_needed()
    assert needed is True and why == 'no derivation digest'                                  # the earlier receipt and digest moved with the directory
    assert not (s.work / 'derive.json').exists()


def test_move_aside_moves_named_sibling_files_even_without_a_directory_and_never_collides_on_the_receipt(tmp_path):
    B = FX.B
    (tmp_path / 'derive.json').write_text('{"a": 1}')
    moved = B._move_aside(tmp_path / 'derived', siblings=[tmp_path / 'derive.json', tmp_path / 'absent.md'])
    assert moved and (Path(moved) / 'derive.json').read_text() == '{"a": 1}' and not (tmp_path / 'derive.json').exists()
    receipt = json.loads(next(tmp_path.glob('derived-supersede-*.json')).read_bytes())
    assert [Path(x).name for x in receipt['moved_files']] == ['derive.json'] and receipt['moved_to'] == moved
    assert B._move_aside(tmp_path / 'derived', siblings=[tmp_path / 'absent.md']) is None


def test_the_restore_script_refuses_to_overwrite_a_different_file_at_a_pinned_destination():
    text = (BOX / 'frankie_box_restore_data_plane.sh').read_text(encoding='utf-8')
    refusal = "not overwritten (move it aside with a receipt first)"
    assert refusal in text
    body = text.split('for key, entry in m.items():')[1]
    assert body.index(refusal) < body.index("part = dest + '.part'") < body.index('os.replace(part, dest)')
    assert "os.replace(part, dest + '.rejected')" not in text and ".rejected-" in text      # a rejected download never overwrites an earlier one


def test_measure_digest_uses_the_granite_tokenizer_when_present_and_records_a_failing_one(tmp_path, monkeypatch):
    import types
    s = stub(tmp_path, monkeypatch)
    s._measure_digest = lambda: session.Session._measure_digest(s)
    (s.work / 'derivation-digest-full.md').write_text('# Derivation digest DIGEST_V6 (x)\nrow row row\n', encoding='utf-8')
    tok = session.ROOT / 'tmp' / 'granite_tokenizer.json'
    tok.parent.mkdir(parents=True, exist_ok=True)
    tok.write_bytes(b'{"stub": true}')
    real = session.sha256_bytes
    monkeypatch.setattr(session, 'sha256_bytes', lambda data: '883975314d587437' + 'f' * 48 if data == b'{"stub": true}' else real(data))
    class Encoded:
        ids = list(range(37))
    class Tokenizer:
        @staticmethod
        def from_file(path):
            return types.SimpleNamespace(encode=lambda text: Encoded())
    monkeypatch.setitem(sys.modules, 'tokenizers', types.SimpleNamespace(Tokenizer=Tokenizer))
    m = s._measure_digest()
    assert m['digest']['tokens'] == 37 and m['digest']['token_basis'] == 'granite tokenizer' and m['digest']['tokenizer_present'] is True and m['digest']['tokenizer_error'] is None
    class Broken:
        @staticmethod
        def from_file(path):
            raise RuntimeError('vocab file truncated')
    monkeypatch.setitem(sys.modules, 'tokenizers', types.SimpleNamespace(Tokenizer=Broken))
    m = s._measure_digest()
    assert m['digest']['token_basis'].startswith('estimate') and m['digest']['tokenizer_present'] is True and 'vocab file truncated' in m['digest']['tokenizer_error']
    assert any('TOKENIZER PRESENT BUT FAILED' in n for n in s._notes)


# Work probes are telemetry only: no input filtering, calculation changes or resume cursor.
def test_work_probe_counts_after_consumption_and_preserves_every_record(tmp_path, monkeypatch):
    probe_module = load('frankie_box_progress')
    monkeypatch.setattr(probe_module, 'process_token', lambda pid: 'boot:start')
    probe = probe_module.Probe(tmp_path, 'request', 'deriving')
    records = [object(), object(), object()]
    iterator = probe.track(records, len(records), 'root-records')
    assert next(iterator) is records[0]
    first = probe_module.snapshot(tmp_path, 'request', 'deriving')
    assert first['completed'] == 0 and first['percent'] == 0 and first['process_alive']
    assert list(iterator) == records[1:]
    final = probe_module.snapshot(tmp_path, 'request', 'deriving')
    assert final['completed'] == 3 and final['percent'] == 100 and final['state'] == 'complete'
    assert probe_module.snapshot(tmp_path, 'different', 'deriving')['status'] == 'identity_or_phase_mismatch'
    assert probe_module.snapshot(tmp_path, 'request', 'classroom')['status'] == 'identity_or_phase_mismatch'
    monkeypatch.setattr(probe_module, 'process_token', lambda pid: 'boot:reused')
    assert probe_module.snapshot(tmp_path, 'request', 'deriving')['process_alive'] is False


def test_work_probe_unknown_and_mismatched_totals_are_not_success(tmp_path):
    module = load('frankie_box_progress')
    probe = module.Probe(tmp_path)
    probe.update('root-projection')
    assert module.snapshot(tmp_path)['percent'] is None
    assert list(probe.track([1], 2, 'root-records')) == [1]
    result = module.snapshot(tmp_path)
    assert result['percent'] == 50 and result['state'] == 'count_mismatch'
    assert list(probe.track([], 0, 'empty')) == []
    assert module.snapshot(tmp_path)['percent'] is None
    with pytest.raises(ValueError):
        probe.update('bad', 2, 1)


def test_probe_highlights_are_honest_and_ignore_invalid_snapshots(tmp_path):
    module = load('frankie_box_progress')
    (tmp_path / 'progress.json').write_text('[]')
    assert module.snapshot(tmp_path)['status'] == 'identity_or_phase_mismatch'
    probe = module.Probe(tmp_path, 'request', 'classroom')
    probe.update('classroom-tasks', 1, 4, in_flight=1)
    probe.checkpoint('read_verified', 'part.json')
    text = module.highlight(module.snapshot(tmp_path))
    assert '1/4 (25.0%)' in text and 'verified_reads=1' in text
    assert 'worker_alive=' in text and 'in_flight=1' in text
    probe.update('root-digest')
    assert '(unknown)' in module.highlight(module.snapshot(tmp_path))


def _two_member_mapping_fixture(tmp_path):
    """A real hash-verified journal; the synthetic source needs no SDK or model."""
    from dataclasses import asdict
    from research.kalshi.frankie_boss.causal_prefix import SourceMember
    from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
    members = [asdict(SourceMember(i, f"member-{i}.dbn", str(i + 1) * 64, 112, 2))
               for i in range(2)]
    directory = tmp_path / "mapping"
    directory.mkdir()
    journal_path = tmp_path / "source.sqlite"
    journal = EvidenceJournal(journal_path, create=True)
    groups, wires = [], []
    for cursor in range(4):
        member = cursor // 2
        wire = bytes([cursor + 1]) * 56
        wires.append(hashlib.sha256(wire).hexdigest())
        record = dict(dbn_wire_bytes=wire, dbn_extraction_hash="e" * 64,
                      ts_recv=cursor + 101, ts_event=cursor + 100,
                      flags=128 if cursor % 2 else 0)
        journal.append("INPUT", dict(cursor=cursor, record=record))
        journal.append("APPLIED", dict(cursor=cursor, raw_record=record,
            source_member_index=member, normalized=dict(source_dbn_sha256=members[member]["sha256"]),
            terminal_prefix_hash=str(cursor + 5) * 64, receipt={} if cursor % 2 else None))
        if cursor % 2:
            groups.append(dict(cursor_start=cursor - 1, cursor_end=cursor,
                source_member_index=member, plain_offset=member * 10, plain_bytes=10,
                wire_sha256=wires[-2:]))
    checkpoint = dict(count=journal.count, head_hash=journal.head_hash)
    journal.close()
    index = b"".join(json.dumps(g, sort_keys=True).encode() + b"\n" for g in groups)
    (directory / "index.jsonl").write_bytes(index)
    body = dict(schema="FRANKIE_SOURCE_MEMBERS_MAPPING_V2", sources=members,
        extraction_hash="e" * 64, record_count=4, group_count=2,
        member_ledger=dict(plain=dict(bytes=20, sha256="d" * 64)),
        index=dict(bytes=len(index), sha256=hashlib.sha256(index).hexdigest()),
        boss_prefix_bound=False)
    (directory / "mapping.json").write_text(json.dumps(body))
    source = dict(prefix_hash="8" * 64, through_cursor=3, as_of=104,
                  source_as_of=103, arm_hash="a" * 64)
    return dict(mapping_directory=directory,
        expected_mapping_sha256=hashlib.sha256((directory / "mapping.json").read_bytes()).hexdigest(),
        boss_journal_path=journal_path, journal_checkpoint=checkpoint,
        boss_source=source, output_path=tmp_path / "binding.json")


def test_two_member_source_binding_covers_the_whole_day_without_writing_source(tmp_path):
    from research.kalshi.frankie_boss import frankie_source_mapping as mapping
    args = _two_member_mapping_fixture(tmp_path)
    before = args["boss_journal_path"].read_bytes()
    result = mapping.bind_prefix(**args)
    assert result["schema"] == "FRANKIE_BOSS_BYTE_PREFIX_MAPPING_V2"
    assert result["matched_records"] == 4 and result["matched_groups"] == 2
    assert [m["member_index"] for m in result["sources"]] == [0, 1]
    assert result["matched_records_by_member"] == [2, 2]
    assert args["boss_journal_path"].read_bytes() == before


@pytest.mark.parametrize("damage", ["swapped_member", "missing_member", "wrong_count", "wrong_identity"])
def test_two_member_mapping_rejects_invalid_member_coverage(tmp_path, damage):
    from research.kalshi.frankie_boss import frankie_source_mapping as mapping
    args = _two_member_mapping_fixture(tmp_path)
    directory = args["mapping_directory"]
    body = json.loads((directory / "mapping.json").read_bytes())
    if damage == "swapped_member":
        rows = [json.loads(line) for line in (directory / "index.jsonl").read_bytes().splitlines()]
        rows[1]["source_member_index"] = 0
        raw = b"".join(json.dumps(row).encode() + b"\n" for row in rows)
        (directory / "index.jsonl").write_bytes(raw)
        body["index"].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    elif damage == "missing_member":
        body["sources"].pop()
    elif damage == "wrong_count":
        body["sources"][1]["mbo_records"] += 1
    else:
        body["sources"][1]["sha256"] = "f" * 64
    raw = json.dumps(body).encode()
    (directory / "mapping.json").write_bytes(raw)
    args["expected_mapping_sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):
        mapping.bind_prefix(**args)
    assert not args["output_path"].exists()


def test_two_member_prefix_checks_full_mapping_but_selects_only_closed_prefix(tmp_path):
    from research.kalshi.frankie_boss import frankie_source_mapping as mapping
    args = _two_member_mapping_fixture(tmp_path)
    args["boss_source"].update(through_cursor=1, prefix_hash="6" * 64, as_of=102, source_as_of=101)
    result = mapping.bind_prefix(**args)
    assert result["matched_records_by_member"] == [2, 0]
    assert result["matched_records"] == 2 and result["matched_groups"] == 1
    assert result["selected_member_plain_end"] == 10


@pytest.mark.parametrize("damage", ["open_group", "index_hash", "journal_pin", "causal_clock"])
def test_two_member_binding_refuses_unverified_or_noncausal_prefix(tmp_path, damage):
    from research.kalshi.frankie_boss import frankie_source_mapping as mapping
    args = _two_member_mapping_fixture(tmp_path)
    if damage == "open_group":
        args["boss_source"].update(through_cursor=2, prefix_hash="7" * 64)
    elif damage == "index_hash":
        with (args["mapping_directory"] / "index.jsonl").open("ab") as handle:
            handle.write(b"\n")
    elif damage == "journal_pin":
        args["journal_checkpoint"]["head_hash"] = "f" * 64
    else:
        args["boss_source"].update(as_of=101, source_as_of=100)
    with pytest.raises(ValueError):
        mapping.bind_prefix(**args)
    assert not args["output_path"].exists()
