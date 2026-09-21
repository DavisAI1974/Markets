"""The box classroom module (deploy/aws/box/frankie_box_classroom.py) against the REAL classroom validators and grader:
facts transcribed from a TEACH pre-message, the BOSS's interpretation parsed from its JSON answers, the four ledgers
assembled and graded by dipole_classroom_session.grade_initial_response (zero corrections, mastered), the correction
turn answered and finished by the host's own functions. The package is built torch-free from a hand-built snapshot
through the repo's own key/pre-message builders (no market data)."""
from __future__ import annotations

import json
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
for name, rel in (('research', 'research'), ('research.kalshi', 'research/kalshi'), ('research.kalshi.frankie_boss', 'research/kalshi/frankie_boss')):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(ROOT / rel)]
        sys.modules[name] = module
sys.path.insert(0, str(ROOT / 'deploy/aws/box'))
import frankie_box_classroom as C                                                       # noqa: E402

V = C.validators()                      # installs the torch-free shims before the classroom modules load
classroom, session_mod, final, resolution = V.classroom, V.session, V.final, V.resolution
from research.kalshi.frankie_boss import dipole_classroom_hardening as hardened         # noqa: E402
from research.kalshi.frankie_boss.c15_journal import evidence_hash                      # noqa: E402
from research.kalshi.frankie_boss.c15_normalizer import COLUMNS                         # noqa: E402

ROWS = 4
CURSORS = [2 * (i + 1) for i in range(ROWS)]


def snapshot():
    rows = []
    for r, c in enumerate(CURSORS):
        comps = []
        for idx, name in enumerate(COLUMNS):
            state, value, reason = 'PRESENT', 1234.5 + idx * 10 + r * 1.25 + (r % 3) * 0.5 * idx, ''
            if idx == 7:
                value = 500.0 - r * 2.0                                   # FALL
            if idx == 3 and r == 1:
                state, value, reason = 'MISSING', None, 'no far-side cohort in this step'
            if idx == 5 and r == 2:
                state, value, reason = 'ABLATED', None, 'ablated by policy'
            if idx == 9 and r > 0:
                state, value, reason = 'INVALID', None, 'invalid normalizer input'   # INSUFFICIENT direction
            comps.append(dict(name=name, unit='z_score', value=value, state=state, raw_reason=reason))
        rows.append(dict(cursor=c, target_hash=f'{c:064x}', source_manifest_hash='m' * 64, source_prefix_hash='p' * 64,
                         as_of_ts_recv_ns=1_000_000 + c, ts_recv_ns=1_000_000 + c, components=comps, step_receipt_hash='r' * 64))
    body = dict(schema=classroom.SOURCE_SCHEMA, request_id='run-cycle-00', cycle_index=0, cycle_count=19, source_hash='b' * 64,
                as_of=2_000_000, through_cursor=CURSORS[-1], teacher_attachment_hash='a' * 64, candidate_digest='c' * 64,
                processed_records=CURSORS[-1] + 1, context_cursors=tuple(CURSORS), rows=tuple(rows),
                coverage_columns=tuple(COLUMNS), coverage_count=len(COLUMNS))
    body['source_snapshot_hash'] = evidence_hash(body)
    return body


def build_package():
    snap = snapshot()
    key = hardened._harden_teacher_key_correlations(classroom.build_teacher_key(snap))
    message = classroom.build_pre_message(key, mode='TEACH', prior_grade=None)
    message = {k: v for k, v in message.items() if k != 'teacher_message_hash'}
    message['direction_definition'] = 'Graded direction means the first PRESENT observation versus the last PRESENT observation.'
    message['novelty_invitation'] = 'Report any relationship you believe is new.'
    message['teacher_message_hash'] = evidence_hash(message)
    binding = {'request_id': 'run-cycle-00', 'cycle_index': 0, 'cycle_count': 19, 'source_hash': 'b' * 64, 'as_of': 2_000_000,
               'through_cursor': CURSORS[-1], 'source_snapshot_hash': snap['source_snapshot_hash'], 'teacher_key_hash': key['teacher_key_hash'],
               'teacher_message_hash': message['teacher_message_hash'], 'teacher_attachment_hash': snap['teacher_attachment_hash'],
               'mode': 'TEACH', 'learning_measurement': 'INSTRUCTIONAL_COMPREHENSION', 'independent_discovery_eligible': False,
               'coverage_count': len(COLUMNS), 'relationship_pairs_required': classroom.PAIR_COUNT}
    binding['classroom_binding_hash'] = evidence_hash(binding)
    return dict(source=snap, teacher_key=key, pre_message=message, binding=binding)


def build_visible(package=None):
    """As the box holds it: the JSON form (lists, never tuples) of the model-visible classroom."""
    return json.loads(json.dumps(final.final_model_visible_classroom(package or build_package())))


@pytest.fixture(scope='module')
def package():
    return build_package()


@pytest.fixture(scope='module')
def visible(package):
    return build_visible(package)


def boss_component_answer(comp, rights, *, drop_state=None):
    states = sorted({p['state'] for p in comp['observations']})
    explanations = {s: f'{comp["name"]} {s.lower()} observation, read as opposing-pressure evidence' for s in states if s != drop_state}
    return json.dumps(dict(explanation=f'{comp["name"]}: what happened in my words', why='why it matters', market_behavior='market behaviour read',
                           fifo_full_book_order_link='FIFO and full-book link', evidence='the retained series above', uncertainty='what I cannot know yet',
                           state_explanations=explanations,
                           pairs=[dict(right=r, correlation_interpretation=f'{comp["name"]} vs {r}: descriptive only',
                                       developing_structure=('HYPOTHESIS: a developing structure to watch' if (comp['name'], r) == (COLUMNS[0], COLUMNS[1]) else None))
                                  for r in rights]))


def boss_summary_answer(*, with_novel=True, with_bad_novel=False):
    findings = []
    if with_novel:
        findings.append(dict(finding_id='nf-1', premise='far-side replenishment leads absorption inside this window', why_novel='not taught as a pair rule',
                             evidence_refs=[dict(kind='DIPOLE_RELATIONSHIP', left=COLUMNS[3], right=COLUMNS[7], claimed_relation='OPPOSITE_DIRECTION', reasoning='directions differ')]))
    if with_bad_novel:
        findings.append(dict(finding_id='nf-bad', premise='p', why_novel='w', evidence_refs=[]))       # no evidence: invalid by contract
    return json.dumps(dict(cycle_summary='the cycle in my words', correlation_review='what the pairs support and do not',
                           unresolved_questions=['what the next window shows'], novel_findings=findings))


def run_exchange(visible, **summary_kwargs):
    outputs = {}
    for comp in C.components(visible):
        rights = [p['right'] for p in C.pairs_of(visible, comp['name'])]
        outputs[comp['name']] = C.parse_component(boss_component_answer(comp, rights), comp, rights)
    summary = C.parse_summary(boss_summary_answer(**summary_kwargs))
    return C.assemble(visible, outputs, summary)


def test_component_prompt_carries_every_cursor_the_reason_legend_and_the_pairs(visible):
    comp = C.components(visible)[3]
    text = C.component_prompt(visible, comp['name'], cycle='00', request_id='run-cycle-00')
    for c in CURSORS:
        assert f'\n{c} ' in text
    assert 'R1 = "no far-side cohort in this step"' in text and '4 MISSING - R1' in text
    assert f'{ROWS} retained cursors' in text and 'OPPOSITE_DIRECTION' in text and COLUMNS[7] in text
    assert text.count('"right": "') == len(C.pairs_of(visible, comp['name'])) and 'ONE JSON object' in text
    assert len(C.pairs_of(visible, comp['name'])) == len(COLUMNS) - 4


def test_parse_component_refuses_a_missing_state_explanation_and_a_missing_pair(visible):
    comp = C.components(visible)[3]
    rights = [p['right'] for p in C.pairs_of(visible, comp['name'])]
    with pytest.raises(C.ClassroomOutput, match='state MISSING'):
        C.parse_component(boss_component_answer(comp, rights, drop_state='MISSING'), comp, rights)
    with pytest.raises(C.ClassroomOutput, match='pair'):
        C.parse_component(boss_component_answer(comp, rights[:-1]), comp, rights)
    with pytest.raises(C.ClassroomOutput, match='JSON'):
        C.parse_component('I cannot complete this request', comp, rights)


def test_assembled_ledgers_pass_the_real_grader_with_zero_corrections(package, visible):
    built = run_exchange(visible)
    ledgers = built['ledgers']
    assert set(ledgers) == {'dipole_teachback', 'dipole_observation_review', 'dipole_relationship_scan', 'dipole_novel_findings'}
    report = C.validate(visible, ledgers)
    assert report['components'] == 19 and report['pairs'] == 171 and report['observations'] == 19 * ROWS and report['consistent'] is True
    teachback, grade = session_mod.grade_initial_response(package, ledgers)
    grade = final.apply_relationship_view_crosscheck(grade, ledgers)
    assert grade['correction_ids'] == () and grade['mastered'] is True
    assert grade['exhaustive_audit']['observation_claims_reviewed'] == 19 * ROWS
    review = {c['name']: c for c in ledgers['dipole_observation_review']}
    missing = [o for o in review[COLUMNS[3]]['observations'] if o['state'] == 'MISSING'][0]
    assert missing['value'] is None and 'teacher reason: no far-side cohort in this step' in missing['explanation']
    present = review[COLUMNS[3]]['observations'][0]
    assert isinstance(present['value'], float) and 'teacher reason' not in present['explanation']
    first = ledgers['dipole_relationship_scan'][0]
    assert (first['left'], first['right']) == (COLUMNS[0], COLUMNS[1]) and first['developing_structure'].startswith('HYPOTHESIS')
    assert ledgers['dipole_teachback']['components'][0]['relationships'][0]['relation'] == first['direction_relation']
    assert len(ledgers['dipole_novel_findings']) == 1 and built['dropped_findings'] == []


def test_an_invalid_novel_finding_is_dropped_and_reported_not_filed(visible):
    built = run_exchange(visible, with_bad_novel=True)
    assert [f['finding_id'] for f in built['ledgers']['dipole_novel_findings']] == ['nf-1']
    assert built['dropped_findings'][0]['finding_id'] == 'nf-bad' and 'evidence' in built['dropped_findings'][0]['reason']
    C.validate(visible, built['ledgers'])


def test_validate_refuses_a_tampered_fact(visible):
    ledgers = run_exchange(visible)['ledgers']
    ledgers['dipole_relationship_scan'][5]['direction_relation'] = 'UNRESOLVED' if ledgers['dipole_relationship_scan'][5]['direction_relation'] != 'UNRESOLVED' else 'SAME_DIRECTION'
    with pytest.raises(ValueError, match='transcription'):
        C.validate(visible, ledgers)


def test_correction_turn_round_trip_finishes_the_classroom(package, visible):
    ledgers = run_exchange(visible)['ledgers']
    initial = dict(session_id='boss:frankie-box:test:cycle-00', model_identity_as_reported_by_session='granite42-smoke (test)', request_sha256='9' * 64, **ledgers)
    teachback, grade = session_mod.grade_initial_response(package, initial)
    grade = final.apply_relationship_view_crosscheck(grade, initial)
    novel = final.validate_novel_findings(initial['dipole_novel_findings'], package['pre_message'])
    novelty = final.investigate_novel_findings(package['teacher_key'], novel, mode='TEACH')
    correction = final.bind_final_resolution_requirement(final.build_final_correction_request(
        original_request_sha256='9' * 64, response=initial, grade=grade, key=package['teacher_key'], teachback=teachback, novelty_investigation=novelty))
    correction = json.loads(json.dumps(correction))                                   # as the box receives it
    text = C.correction_prompt(correction, ledgers, cycle='00')
    assert 'nf-1' in text and 'correction_resolutions' in text and correction['instruction'] in text
    parsed = C.parse_correction(json.dumps(dict(what_i_will_change='keep observation and interpretation apart', remaining_disagreements=[], correction_resolutions=[])), correction)
    response = C.correction_response(correction, parsed, session_id=initial['session_id'], model_identity=initial['model_identity_as_reported_by_session'])
    assert response['request_sha256'] == correction['request_sha256'] and response['dipole_acknowledgement']['resolved_correction_ids'] == []
    base = session_mod.validate_correction_response(correction=correction, response=response, initial_response=initial, grade=grade)
    ack = resolution.validate_correction_resolutions(response['dipole_acknowledgement'], grade, base)
    completion = session_mod.finish(package, teachback=teachback, grade=grade, acknowledgement=ack)
    assert completion['teacher_complete'] is True and completion['mastered'] is True
    assert C.attestation_request_sha256(correction) == C.adapter_digest(correction)
    with pytest.raises(C.ClassroomOutput, match='correction_id'):
        C.parse_correction(json.dumps(dict(what_i_will_change='x', remaining_disagreements=[], correction_resolutions=[dict(correction_id='ghost', corrected_understanding='y')])), correction)


def test_markdown_render_carries_the_narratives_not_the_per_cursor_review(visible):
    built = run_exchange(visible)
    text = C.render_markdown(built['ledgers'], built['dropped_findings'])
    assert '# Dipole classroom' in text and 'the cycle in my words' in text and COLUMNS[7] in text and 'nf-1' in text
    assert text.count('teacher reason') == 0 and f'{19 * ROWS} observations' in text
