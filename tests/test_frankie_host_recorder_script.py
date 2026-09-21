"""The recorder fix and its delivery: stage_admission_inputs copies the admission inputs into the candidate, and the
host script carries the recorder source verbatim (the host tools checkout is not moved mid-run)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORDER = ROOT / 'research' / 'kalshi' / 'frankie_boss' / 'operations' / 'record_actual_frankie_response.py'
SCRIPT = ROOT / 'deploy' / 'aws' / 'host' / 'frankie_host_record_principal_response.ps1'


def load_recorder():
    spec = importlib.util.spec_from_file_location('record_actual_frankie_response_under_test', RECORDER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_candidate_answers_the_admission_record_with_the_principal_directory_and_everything_else_with_its_own(tmp_path):
    m = load_recorder()

    class Adapter:
        def __init__(self, directory):
            self.directory = Path(directory)

        def _admission_record(self):
            return dict(sealed_absence=dict(path=str((self.directory / 'sealed-proof.json').resolve())))

        def where(self):
            return str(self.directory)
    principal = tmp_path / 'principal'
    principal.mkdir()
    real = Adapter(principal)
    cand = m.candidate_of(real, principal / 'response-check-x')
    assert cand.directory == principal / 'response-check-x' and cand.where() == str(principal / 'response-check-x')
    assert cand._admission_record() == real._admission_record()               # the principal's record, its own path
    assert real.directory == principal and not hasattr(Adapter, 'x')          # the real adapter untouched


def test_live_classroom_puts_the_live_block_in_the_attachment_only_when_json_equal():
    import json
    m = load_recorder()
    json_form = lambda v: json.loads(json.dumps(v))
    live = {'binding': {'mode': 'TEACH', 'pairs': ('a', 'b')}, 'model_visible_hash': 'h' * 64}
    request = {'attachment': {'dipole_classroom': json_form(live)}}
    assert m.live_classroom(request, {'pkg': 1}, lambda pkg: live, json_form) == 'live'
    assert request['attachment']['dipole_classroom'] is live                       # the live object, tuples and all
    other = {'attachment': {'dipole_classroom': {'binding': {'mode': 'OTHER'}}}}
    assert m.live_classroom(other, {}, lambda pkg: live, json_form) == 'unchanged' and other['attachment']['dipole_classroom'] == {'binding': {'mode': 'OTHER'}}
    assert m.live_classroom({'attachment': {}}, {}, lambda pkg: live, json_form) == 'unchanged'


def test_classroom_normalizer_applies_to_every_attachment_handed_to_recover():
    import json
    m = load_recorder()
    json_form = lambda v: json.loads(json.dumps(v))
    live = {'binding': {'pairs': ('a', 'b')}, 'model_visible_hash': 'h' * 64}
    normalize = m.classroom_normalizer({'pkg': 1}, lambda pkg: live, json_form)
    from_file = {'dipole_classroom': json_form(live), 'other': 1}
    out = normalize(from_file)
    assert out['dipole_classroom'] is live and out['other'] == 1 and from_file['dipole_classroom'] is not live   # the input is not mutated
    assert normalize({'dipole_classroom': {'x': 1}})['dipole_classroom'] == {'x': 1}


def test_the_host_script_carries_the_recorder_source_verbatim():
    text = SCRIPT.read_text(encoding='utf-8')
    start = text.index("$recorderSource = @'\n") + len("$recorderSource = @'\n")
    end = text.index("'@\n$shippedTool", start)
    assert text[start:end] == RECORDER.read_text(encoding='utf-8')
    assert "'@" not in RECORDER.read_text(encoding='utf-8')       # a here-string terminator inside the source would truncate it


def test_the_recorder_refusal_carries_its_message():
    assert "error=str(error)[:800]" in RECORDER.read_text(encoding='utf-8')


def _classroom_setup(tmp_path):
    """The synthetic TEACH package (tests/test_frankie_box_classroom.py) graded by the host's own functions, a correction
    request as the runner retains it, and a fake adapter over a temp principal directory (the base _attest_host and
    _record_correction_response are the real ones, unbound)."""
    import json
    from types import SimpleNamespace
    from test_frankie_box_classroom import build_package, build_visible, boss_component_answer, boss_summary_answer, C
    V = C.validators()
    import research.kalshi.frankie_boss.frankie_principal_adapter as base
    import research.kalshi.frankie_boss.frankie_dipole_classroom_adapter as classroom_adapter
    package = build_package(); visible = build_visible(package)
    outputs = {}
    for comp in C.components(visible):
        rights = [p['right'] for p in C.pairs_of(visible, comp['name'])]
        outputs[comp['name']] = C.parse_component(boss_component_answer(comp, rights), comp, rights)
    ledgers = C.assemble(visible, outputs, C.parse_summary(boss_summary_answer()))['ledgers']
    initial = dict(session_id='boss:frankie-box:test:cycle-00', model_identity_as_reported_by_session='granite42-smoke (test)', request_sha256='9' * 64, **ledgers)
    teachback, grade = V.session.grade_initial_response(package, initial)
    grade = V.final.apply_relationship_view_crosscheck(grade, initial)
    novel = V.final.validate_novel_findings(initial['dipole_novel_findings'], package['pre_message'])
    novelty = V.final.investigate_novel_findings(package['teacher_key'], novel, mode='TEACH')
    correction = V.final.bind_final_resolution_requirement(V.final.build_final_correction_request(
        original_request_sha256='9' * 64, response=initial, grade=grade, key=package['teacher_key'], teachback=teachback, novelty_investigation=novelty))
    principal = tmp_path / 'principal'; principal.mkdir(); audit = tmp_path / 'classroom-audit'; audit.mkdir()
    (principal / 'session-response.json').write_bytes(base.canonical(dict(response=initial, host_attestation={})))
    (principal / 'classroom-correction-request.json').write_bytes(base.canonical(correction))
    (audit / 'dipole-classroom-post-grade.json').write_bytes(base.canonical(grade))
    adapter = SimpleNamespace(directory=principal, audit_directory=audit)
    adapter._attest_host = lambda response, attestation, request: base.FrankiePrincipalAdapter._attest_host(adapter, response, attestation, request)
    adapter._record_correction_response = lambda correction, dispatched: classroom_adapter.DipoleClassroomPrincipalAdapter._record_correction_response(adapter, correction, dispatched)
    correction_as_read = json.loads((principal / 'classroom-correction-request.json').read_bytes())
    reply = C.correction_response(correction_as_read, C.parse_correction(json.dumps(dict(what_i_will_change='keep observation and interpretation apart', remaining_disagreements=[], correction_resolutions=[])), correction_as_read),
                                  session_id=initial['session_id'], model_identity=initial['model_identity_as_reported_by_session'])
    record_path = tmp_path / 'host-correction-record.json'
    expected = dict(schema='FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1', mechanism='AGENT_SESSION', request_sha256=C.attestation_request_sha256(correction_as_read),
                    response_sha256=C.adapter_digest(reply), session_id=initial['session_id'], model_identity_as_reported_by_session=initial['model_identity_as_reported_by_session'])
    record_path.write_bytes(base.canonical(dict(expected, host_authority='test host')))
    attestation = dict(expected, host_record=dict(path=str(record_path), **{k: v for k, v in base.file_witness(record_path).items()}))
    return SimpleNamespace(package=package, initial=initial, correction=correction_as_read, adapter=adapter, principal=principal, reply=reply, attestation=attestation, base=base)


def test_record_correction_validates_and_writes_the_immutable_correction_response(tmp_path):
    import json
    m = load_recorder()
    s = _classroom_setup(tmp_path)
    result = m.record_correction(s.adapter, s.principal, s.reply, s.attestation, 'run-cycle-00')
    assert result['resolutions'] == 0 and result['remaining_disagreements'] == [] and result['mastered'] is True
    assert result['correction_request_sha256'] == s.correction['request_sha256']
    written = json.loads((s.principal / 'classroom-correction-response.json').read_bytes())
    assert written == json.loads(s.base.canonical(dict(response=s.reply, host_attestation=s.attestation)))
    assert m.record_correction(s.adapter, s.principal, s.reply, s.attestation, 'run-cycle-00') == result       # idempotent on the same bytes
    other = dict(s.reply, session_id='someone-else')
    import pytest
    with pytest.raises(ValueError):
        m.record_correction(s.adapter, s.principal, other, s.attestation, 'run-cycle-00')


def test_record_correction_refuses_without_the_retained_request_or_the_initial_response(tmp_path):
    import pytest
    m = load_recorder()
    s = _classroom_setup(tmp_path)
    (s.principal / 'classroom-correction-request.json').unlink()
    with pytest.raises(ValueError, match='no Dipole classroom correction request'):
        m.record_correction(s.adapter, s.principal, s.reply, s.attestation, 'run-cycle-00')
    (s.principal / 'session-response.json').unlink()
    with pytest.raises(ValueError, match='cannot precede'):
        m.record_correction(s.adapter, s.principal, s.reply, s.attestation, 'run-cycle-00')


def test_classroom_pregrade_is_the_runners_grade_and_refuses_a_response_without_a_teachback(tmp_path):
    import pytest
    m = load_recorder()
    s = _classroom_setup(tmp_path)
    grade = m.classroom_pregrade(s.package)
    pre = grade(s.initial)
    assert pre['mastered'] is True and pre['correction_ids'] == [] and pre['novel_findings'] == 1 and pre['relationship_pairs_reviewed'] == 171
    with pytest.raises(ValueError, match='teach-back required'):
        grade({k: v for k, v in s.initial.items() if k != 'dipole_teachback'})


def test_host_script_and_workflow_carry_the_turn():
    text = SCRIPT.read_text(encoding='utf-8')
    assert "'correction' {" in text and "--turn $Turn" in text and 'classroom-correction-response.json' in text
    workflow = (ROOT / '.github' / 'workflows' / 'frankie_host_record_principal_response.yml').read_text(encoding='utf-8')
    assert "options: ['initial', 'correction']" in workflow and '--set "Turn=$TURN"' in workflow and 'dipole_acknowledgement' in workflow
