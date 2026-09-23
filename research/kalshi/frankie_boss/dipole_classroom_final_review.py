"""Final review hardening for the Dipole classroom.

This layer does not change the governed Dipole teacher mathematics, Frankie inputs,
or the lawful Sunday host. It narrows the classroom boundary so the human-readable
record matches the model-visible exchange, gives Frankie a protected innovation
channel, and makes Dipole evidence review local and non-punitive.

Policy:
- complete 19/19 + 171/171 curriculum coverage remains invariant;
- TEACH/GUIDED are instructional-comprehension phases, not independent-discovery proof;
- SOCRATIC/VERIFY are eligible for independent-discovery attribution;
- novel findings are never marked incorrect merely for being outside Dipole's curriculum;
- Dipole investigates cited causal evidence before responding;
- when a factual subclaim differs, the response is "the data is showing this instead"
  and applies only to the specific contradicted subclaim, not the whole premise;
- the complete host grade and teacher key remain host-only.
"""
from __future__ import annotations
import json
import math
from typing import Any, Mapping, Sequence
from . import dipole_classroom as classroom
from . import dipole_classroom_hardening as hardened
from .c15_journal import evidence_hash
from .c15_normalizer import COLUMNS
from .dipole_classroom_render import render_acknowledgement, render_pre_message, render_teachback
from .dipole_classroom_resolution import validate_correction_resolutions
from .dipole_classroom_session import CORRECTION_REQUEST_SCHEMA, finish, grade_initial_response, validate_correction_response, validate_package
from .frankie_principal_adapter import FrankiePrincipalAdapter, PrincipalPending, digest, file_witness, _write, json_form
NOVEL_FINDING_SCHEMA = 'FRANKIE_DIPOLE_NOVEL_FINDING_V1'
NOVELTY_INVESTIGATION_SCHEMA = 'DIPOLE_NOVELTY_INVESTIGATION_V1'
PRIOR_CORRECTION_SCHEMA = hardened.PRIOR_CORRECTION_SCHEMA
_FACTUAL_RELATIONS = ('SAME_DIRECTION', 'OPPOSITE_DIRECTION', 'UNRESOLVED')
_STATES = ('PRESENT', 'MISSING', 'INVALID', 'ABLATED')

def _nonempty(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f'{label} must be nonempty text')
    return value

def _same_value(claimed: Any, actual: Any) -> bool:
    if actual is None:
        return claimed is None
    return claimed is not None and type(claimed) in (int, float) and (not isinstance(claimed, bool)) and math.isfinite(float(claimed)) and math.isclose(float(claimed), float(actual), rel_tol=1e-06, abs_tol=1e-06)

def _independent_discovery_eligible(mode: str) -> bool:
    """TEACH/GUIDED show the evidence, so a mastered cycle there measures comprehension of instruction;
    only SOCRATIC/VERIFY, where Frankie answers before the key is shown, can measure independent recognition."""
    return mode in (classroom.ClassroomMode.SOCRATIC.value, classroom.ClassroomMode.VERIFY.value)

def _learning_measurement(mode: str) -> str:
    return 'INDEPENDENT_RECOGNITION_ELIGIBLE' if _independent_discovery_eligible(mode) else 'INSTRUCTIONAL_COMPREHENSION'

def prepare_final_cycle(teacher: Mapping[str, Any], *, request_id: str, cycle_index: int, cycle_count: int, source_hash: str, as_of: int, through_cursor: int, previous_snapshot: Mapping[str, Any] | None=None, history: Sequence[Mapping[str, Any]]=(), prior_grade: Mapping[str, Any] | None=None) -> dict:
    """cycle_count is owned by the retained runtime schedule (the host reads its steps); never a classroom constant."""
    snapshot = classroom.snapshot_teacher_attachment(teacher, request_id=request_id, cycle_index=cycle_index, cycle_count=cycle_count, source_hash=source_hash, as_of=as_of, through_cursor=through_cursor)
    key = hardened._harden_teacher_key_correlations(classroom.build_teacher_key(snapshot, previous_snapshot))
    mode = hardened.select_hardened_mode(history)
    # The core builder emits the prior-correction SUMMARY (never the prior grade) and the Pearson-floor text.
    message = classroom.build_pre_message(key, mode=mode, prior_grade=prior_grade)
    message = {k: v for k, v in message.items() if k != 'teacher_message_hash'}
    message['direction_definition'] = 'Graded direction means the first PRESENT observation versus the last PRESENT observation in this retained cycle window. Intrawindow rises, falls, reversals, and excursions may still exist even when that endpoint direction is FLAT.'
    message['novelty_invitation'] = 'After completing the required Dipole curriculum, report any relationship, structure, mechanism, or hypothesis you believe is new or not explicitly taught. A new idea is not a classroom error merely because Dipole did not teach it. Cite the causal evidence that led you to it and keep future outcomes outside the wall.'
    message['teacher_message_hash'] = evidence_hash(message)
    binding = {'request_id': request_id, 'cycle_index': cycle_index, 'cycle_count': cycle_count, 'source_hash': source_hash, 'as_of': as_of, 'through_cursor': through_cursor, 'source_snapshot_hash': snapshot['source_snapshot_hash'], 'teacher_key_hash': key['teacher_key_hash'], 'teacher_message_hash': message['teacher_message_hash'], 'teacher_attachment_hash': snapshot['teacher_attachment_hash'], 'mode': mode, 'learning_measurement': _learning_measurement(mode), 'independent_discovery_eligible': _independent_discovery_eligible(mode), 'coverage_count': len(COLUMNS), 'relationship_pairs_required': classroom.PAIR_COUNT}
    binding['classroom_binding_hash'] = evidence_hash(binding)
    return {'source': snapshot, 'teacher_key': key, 'pre_message': message, 'binding': binding}

def final_model_visible_classroom(package: Mapping[str, Any]) -> dict:
    package = validate_package(package)
    mode = package['binding']['mode']
    independent = package['binding'].get('independent_discovery_eligible', _independent_discovery_eligible(mode))
    measurement = package['binding'].get('learning_measurement', _learning_measurement(mode))
    value = {'binding': package['binding'], 'pre_message': package['pre_message'], 'audit_key_object_withheld': True, 'independent_discovery_eligible': independent, 'learning_measurement': measurement, 'coverage_invariant': 'ALL_19_DIPOLE_DIMENSIONS_EVERY_CYCLE', 'required_response_ledgers': {'dipole_observation_review': 'EVERY_RETAINED_OBSERVATION_FOR_ALL_19_DIMENSIONS', 'dipole_relationship_scan': classroom.PAIR_COUNT, 'dipole_novel_findings': 'ZERO_OR_MORE_STRUCTURED_CANDIDATES_AFTER_REQUIRED_COVERAGE'}}
    value['model_visible_hash'] = evidence_hash(value)
    return value

def validate_novel_findings(raw: Any, pre_message: Mapping[str, Any]) -> tuple[dict, ...]:
    if type(raw) is not list:
        raise ValueError('dipole_novel_findings must be a list; use an empty list when none')
    checked = []
    seen = set()
    for item in raw:
        if type(item) is not dict or set(item) != {'schema', 'finding_id', 'premise', 'why_novel', 'evidence_refs', 'future_outcome_claimed'}:
            raise ValueError('novel finding fields differ from classroom contract')
        if item.get('schema') != NOVEL_FINDING_SCHEMA:
            raise ValueError('novel finding schema differs')
        finding_id = _nonempty(item.get('finding_id'), 'finding_id')
        if finding_id in seen:
            raise ValueError('novel finding ids must be unique')
        _nonempty(item.get('premise'), 'novel premise')
        _nonempty(item.get('why_novel'), 'why_novel')
        if item.get('future_outcome_claimed') is not False:
            raise ValueError('novel finding may not claim a future outcome at the same cutoff')
        refs = item.get('evidence_refs')
        if type(refs) is not list or not refs:
            raise ValueError('novel finding must cite at least one causal evidence reference')
        normalized_refs = []
        for ref in refs:
            if type(ref) is not dict or 'kind' not in ref:
                raise ValueError('novel evidence reference must be a structured object')
            kind = ref['kind']
            if kind == 'DIPOLE_OBSERVATION':
                if set(ref) != {'kind', 'component', 'cursor', 'claimed_state', 'claimed_value', 'reasoning'}:
                    raise ValueError('Dipole observation novelty reference fields differ')
                if ref['component'] not in COLUMNS or type(ref['cursor']) is not int or ref['cursor'] < 0:
                    raise ValueError('novel Dipole observation reference is invalid')
                if ref['claimed_state'] not in _STATES:
                    raise ValueError('novel observation state outside governed vocabulary')
                if ref['claimed_state'] == 'PRESENT':
                    value = ref['claimed_value']
                    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(float(value)):
                        raise ValueError('novel PRESENT observation requires finite value')
                elif ref['claimed_value'] is not None:
                    raise ValueError('novel non-PRESENT observation value must be null')
                _nonempty(ref['reasoning'], 'novel observation reasoning')
            elif kind == 'DIPOLE_RELATIONSHIP':
                if set(ref) != {'kind', 'left', 'right', 'claimed_relation', 'reasoning'}:
                    raise ValueError('Dipole relationship novelty reference fields differ')
                if ref['left'] not in COLUMNS or ref['right'] not in COLUMNS or ref['left'] == ref['right']:
                    raise ValueError('novel Dipole relationship reference is invalid')
                _nonempty(ref['claimed_relation'], 'novel claimed_relation')
                _nonempty(ref['reasoning'], 'novel relationship reasoning')
            elif kind == 'OTHER_CAUSAL_EVIDENCE':
                if set(ref) != {'kind', 'evidence_pointer', 'description', 'reasoning'}:
                    raise ValueError('other causal novelty reference fields differ')
                _nonempty(ref['evidence_pointer'], 'novel evidence pointer')
                _nonempty(ref['description'], 'novel evidence description')
                _nonempty(ref['reasoning'], 'novel evidence reasoning')
            else:
                raise ValueError('unknown novel evidence reference kind')
            normalized_refs.append(dict(ref))
        body = {'schema': NOVEL_FINDING_SCHEMA, 'finding_id': finding_id, 'premise': item['premise'], 'why_novel': item['why_novel'], 'evidence_refs': normalized_refs, 'future_outcome_claimed': False, 'teacher_message_hash': pre_message['teacher_message_hash']}
        body['finding_hash'] = evidence_hash(body)
        checked.append(body)
        seen.add(finding_id)
    return tuple(checked)

def _teacher_observations(key: Mapping[str, Any]) -> dict[tuple[str, int], Mapping[str, Any]]:
    result = {}
    for dimension in key['dimensions']:
        for point in dimension['observations']:
            result[dimension['name'], point['cursor']] = point
    return result

def _teacher_pairs(key: Mapping[str, Any]) -> tuple[dict[tuple[str, str], Mapping[str, Any]], dict[str, int]]:
    order = {name: index for index, name in enumerate(COLUMNS)}
    result = {(item['left'], item['right']): item for item in key['relationship_scan']}
    return result, order

def investigate_novel_findings(key: Mapping[str, Any], findings: Sequence[Mapping[str, Any]], *, mode: str, learning_policy=None) -> dict:
    from .critic_knowledge import validate_learning_policy
    validate_learning_policy(learning_policy)
    observations = _teacher_observations(key)
    pairs, order = _teacher_pairs(key)
    investigations = []
    for finding in findings:
        inspected = []
        differences = []
        not_testable = []
        for ref in finding['evidence_refs']:
            kind = ref['kind']
            if kind == 'DIPOLE_OBSERVATION':
                actual = observations.get((ref['component'], ref['cursor']))
                if actual is None:
                    record = {'kind': kind, 'scope': f"{ref['component']}@{ref['cursor']}", 'status': 'OUTSIDE_CURRENT_DIPOLE_AUDIT'}
                    not_testable.append(record)
                    inspected.append(record)
                    continue
                state_matches = ref['claimed_state'] == actual['state']
                value_matches = _same_value(ref['claimed_value'], actual['value'])
                if state_matches and value_matches:
                    inspected.append({'kind': kind, 'scope': f"{ref['component']}@{ref['cursor']}", 'status': 'CURRENT_DATA_MATCHES_CITED_SUBCLAIM'})
                else:
                    difference = {'kind': kind, 'scope': f"{ref['component']}@{ref['cursor']}", 'frankie_said': {'state': ref['claimed_state'], 'value': ref['claimed_value']}, 'data_shows': {'state': actual['state'], 'value': actual['value']}, 'message': f"For {ref['component']} at cursor {ref['cursor']}, the data is showing state {actual['state']} and value {actual['value']} instead. This finding applies only to that cited subclaim; it does not reject the broader premise."}
                    differences.append(difference)
                    inspected.append({**difference, 'status': 'DATA_SHOWS_DIFFERENT_SUBCLAIM'})
                continue
            if kind == 'DIPOLE_RELATIONSHIP':
                left, right = (ref['left'], ref['right'])
                if order[left] > order[right]:
                    left, right = (right, left)
                actual = pairs.get((left, right))
                if actual is None or ref['claimed_relation'] not in _FACTUAL_RELATIONS:
                    record = {'kind': kind, 'scope': f'{left}<->{right}', 'status': 'NOVEL_RELATIONSHIP_NOT_DIRECTLY_TESTABLE_BY_DIPOLE_DIRECTION_KEY'}
                    not_testable.append(record)
                    inspected.append(record)
                    continue
                if ref['claimed_relation'] == actual['direction_relation']:
                    inspected.append({'kind': kind, 'scope': f'{left}<->{right}', 'status': 'CURRENT_DATA_MATCHES_CITED_SUBCLAIM'})
                else:
                    difference = {'kind': kind, 'scope': f'{left}<->{right}', 'frankie_said': ref['claimed_relation'], 'data_shows': actual['direction_relation'], 'message': f"For the cited {left} / {right} directional relation, the data is showing {actual['direction_relation']} instead. This changes only that directional subclaim; the broader novel premise remains open."}
                    differences.append(difference)
                    inspected.append({**difference, 'status': 'DATA_SHOWS_DIFFERENT_SUBCLAIM'})
                continue
            record = {'kind': kind, 'scope': ref['evidence_pointer'], 'status': 'OUTSIDE_DIPOLE_CLASSROOM_FACT_KEY_RETAIN_FOR_LATER_REVIEW'}
            not_testable.append(record)
            inspected.append(record)
        if differences:
            status = 'DATA_DIFFERS_ON_SPECIFIC_CITED_SUBCLAIMS'
        elif not_testable:
            status = 'PARTIALLY_TESTABLE_NOVEL_HYPOTHESIS'
        else:
            status = 'CURRENT_CAUSAL_REFERENCES_MATCH'
        independent = learning_policy is None and _independent_discovery_eligible(mode)
        item = {'schema': NOVELTY_INVESTIGATION_SCHEMA, 'finding_id': finding['finding_id'], 'finding_hash': finding['finding_hash'], 'premise': finding['premise'], 'status': status, 'premise_disposition': 'RETAIN_AS_NOVEL_HYPOTHESIS', 'independent_discovery_eligible': independent, 'teacher_exposure_context': ('CUMULATIVE_LEARNING_REPLAY' if learning_policy is not None else 'INDEPENDENT_DISCOVERY_ATTRIBUTION_ELIGIBLE' if independent else 'INSTRUCTIONAL_PHASE_DISCOVERY_CANDIDATE'), 'inspected_evidence': tuple(inspected), 'specific_data_differences': tuple(differences), 'not_yet_testable': tuple(not_testable), 'teacher_response': 'I investigated the causal references you cited. ' + ('The specific differences listed below are places where the data is showing something else. I am not rejecting your whole premise; keep the broader idea as a hypothesis and revise only the contradicted subclaims.' if differences else 'I found no contradiction in the Dipole facts I can test here. That does not prove the broader premise; retain it as a hypothesis and look for reproduction in later causal windows.'), 'scored_for_classroom_mastery': False, 'promotion_rule': 'Do not promote this to Dipole curriculum merely because it appeared once. Track reproduction and later causally available evidence separately.'}
        item['investigation_hash'] = evidence_hash(item)
        investigations.append(item)
    body = {'schema': NOVELTY_INVESTIGATION_SCHEMA, 'mode': mode, 'findings': tuple(investigations), 'finding_count': len(investigations), 'scored_for_classroom_mastery': False}
    if learning_policy is not None: body['learning_policy'] = learning_policy
    body['investigation_bundle_hash'] = evidence_hash(body)
    return body

def apply_relationship_view_crosscheck(grade: Mapping[str, Any], response: Mapping[str, Any]) -> dict:
    """The exhaustive 171-pair ledger is authoritative. A factual relation stated in the component
    narrative must agree with it. A narrative HYPOTHESIS is an ADDITIONAL hypothesis only when the
    ledger also marks a developing_structure for that pair; otherwise it competes with the ledger's
    factual classification and must be reconciled (Greg: HYPOTHESIS in the narrative and
    SAME_DIRECTION in the ledger cannot coexist without a correction)."""
    scan = {(item['left'], item['right']): item for item in response.get('dipole_relationship_scan', ())}
    order = {name: index for index, name in enumerate(COLUMNS)}
    inconsistencies = []
    for component in response.get('dipole_teachback', {}).get('components', ()):
        left = component.get('name')
        for relation in component.get('relationships', ()):
            right = relation.get('with')
            a, b = (left, right) if order[left] < order[right] else (right, left)
            ledger = scan.get((a, b))
            if ledger is None:
                continue
            claimed = relation.get('relation')
            if claimed == 'HYPOTHESIS':
                if ledger.get('developing_structure') is not None:
                    continue
                inconsistencies.append({'correction_id': f'representation:{a}:{b}', 'left': a, 'right': b, 'component_view': 'HYPOTHESIS', 'exhaustive_scan_view': ledger['direction_relation'], 'message': "Frankie's component narrative calls this pair a hypothesis while the exhaustive ledger classifies it factually and records no developing structure. Reconcile this pair: mark the developing structure in the ledger, or state the same classification in both records."})
                continue
            if ledger['direction_relation'] != claimed:
                inconsistencies.append({'correction_id': f'representation:{a}:{b}', 'left': a, 'right': b, 'component_view': claimed, 'exhaustive_scan_view': ledger['direction_relation'], 'message': "Frankie's two factual records disagree for this pair. Reconcile the records before treating either statement as settled."})
    body = {k: v for k, v in grade.items() if k != 'post_grade_hash'}
    existing = tuple(body.get('correction_ids', ()))
    added = tuple((item['correction_id'] for item in inconsistencies))
    body['correction_ids'] = tuple(dict.fromkeys(existing + added))
    body['relationship_view_crosscheck'] = {'inconsistencies': tuple(inconsistencies), 'consistent': not inconsistencies}
    if inconsistencies:
        body['mastered'] = False
    body['post_grade_hash'] = evidence_hash(body)
    return body

def _component_claims(teachback: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {item['name']: item for item in teachback['components']}

def _observation_claims(teachback: Mapping[str, Any]) -> dict[tuple[str, int], Mapping[str, Any]]:
    result = {}
    for component in teachback['observation_review']:
        for point in component['observations']:
            result[component['name'], point['cursor']] = point
    return result

def _teacher_dimensions(key: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {item['name']: item for item in key['dimensions']}

def _teacher_pair_map(key: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {(item['left'], item['right']): item for item in key['relationship_scan']}

def evidence_review_items(grade: Mapping[str, Any], key: Mapping[str, Any], teachback: Mapping[str, Any]) -> tuple[dict, ...]:
    dimensions = _teacher_dimensions(key)
    component_claims = _component_claims(teachback)
    observation_claims = _observation_claims(teachback)
    pair_map = _teacher_pair_map(key)
    audit = grade.get('exhaustive_audit', {})
    observation_grades = {item['name']: item for item in audit.get('observation_grades', ())}
    relationship_grades = {(item['left'], item['right']): item for item in audit.get('relationship_grades', ())}
    cross = {item['correction_id']: item for item in grade.get('relationship_view_crosscheck', {}).get('inconsistencies', ())}
    items = []
    for correction_id in grade.get('correction_ids', ()):
        if correction_id.startswith('component:'):
            name = correction_id.split(':', 1)[1]
            actual = dimensions[name]
            claimed = component_claims[name]
            differences = []
            for field, claimed_value, actual_value in (('state_counts', claimed['state_counts'], actual['state_counts']), ('terminal_state', claimed['terminal_state'], actual['terminal_state']), ('first_to_last_present_direction', claimed['direction'], actual['first_to_last_present_direction'])):
                if claimed_value != actual_value:
                    differences.append({'field': field, 'frankie_said': claimed_value, 'data_shows': actual_value})
            items.append({'correction_id': correction_id, 'kind': 'COMPONENT_DATA_REVIEW', 'subject': name, 'specific_differences': tuple(differences), 'message': f'For {name}, the data is showing the listed values/states instead. Change only these specific subclaims; do not discard a broader premise that is not itself contradicted.'})
            continue
        if correction_id.startswith('observation-set:'):
            name = correction_id.split(':', 1)[1]
            record = observation_grades[name]
            items.append({'correction_id': correction_id, 'kind': 'OBSERVATION_SET_DATA_REVIEW', 'subject': name, 'frankie_said_count': record['claimed_count'], 'data_shows_count': record['expected_count'], 'message': 'The retained causal cursor set contains the data-shown count instead. Reconcile only the cursor-set claim.'})
            continue
        if correction_id.startswith('observation-extra:'):
            name = correction_id.split(':', 1)[1]
            record = observation_grades[name]
            items.append({'correction_id': correction_id, 'kind': 'OBSERVATION_EXTRA_DATA_REVIEW', 'subject': name, 'extra_cursors': tuple(record['extra_cursors']), 'message': 'These cursors are not in the retained causal set. Remove only those specific references; no broader premise is rejected by that fact alone.'})
            continue
        if correction_id.startswith('observation:'):
            _, name, cursor_text = correction_id.split(':', 2)
            cursor = int(cursor_text)
            record = observation_grades[name]
            actual = next((item for item in record['grades'] if item['cursor'] == cursor))
            claimed = observation_claims.get((name, cursor))
            items.append({'correction_id': correction_id, 'kind': 'OBSERVATION_DATA_REVIEW', 'subject': name, 'cursor': cursor, 'frankie_said': None if claimed is None else {'state': claimed['state'], 'value': claimed['value']}, 'data_shows': {'state': actual['state'], 'value': actual['value']}, 'message': f"For {name} at cursor {cursor}, the data is showing state {actual['state']} and value {actual['value']} instead. This addresses only that cited observation."})
            continue
        if correction_id.startswith('relationship:'):
            _, left, right = correction_id.split(':', 2)
            record = relationship_grades[left, right]
            items.append({'correction_id': correction_id, 'kind': 'RELATIONSHIP_DATA_REVIEW', 'left': left, 'right': right, 'frankie_said': record['claimed'], 'data_shows': record['actual'], 'message': f"For {left} / {right}, the current causal data is showing {record['actual']} instead. This changes only this pairwise directional subclaim; it does not invalidate a larger hypothesis."})
            continue
        if correction_id.startswith('representation:'):
            record = cross[correction_id]
            left, right = (record['left'], record['right'])
            actual = pair_map[left, right]['direction_relation']
            items.append({'correction_id': correction_id, 'kind': 'REPRESENTATION_CONSISTENCY_REVIEW', 'left': left, 'right': right, 'component_view': record['component_view'], 'exhaustive_scan_view': record['exhaustive_scan_view'], 'data_shows': actual, 'message': 'Your two records disagree. The data is showing the listed canonical direction instead; reconcile this pair only.'})
            continue
        items.append({'correction_id': correction_id, 'kind': 'LOCAL_DATA_REVIEW', 'message': 'Revisit this specific claim against the same causal evidence. No wider premise should be discarded unless separate evidence contradicts it.'})
    return tuple(items)

def group_review_items(items: Sequence[Mapping[str, Any]]) -> tuple[dict, ...]:
    component_roots = {item['subject']: item['correction_id'] for item in items if item['kind'] == 'COMPONENT_DATA_REVIEW' and any((diff['field'] == 'first_to_last_present_direction' for diff in item['specific_differences']))}
    groups: dict[str, list[str]] = {}
    for item in items:
        correction_id = item['correction_id']
        root = correction_id
        if item['kind'] in ('RELATIONSHIP_DATA_REVIEW', 'REPRESENTATION_CONSISTENCY_REVIEW'):
            roots = [component_roots[name] for name in (item['left'], item['right']) if name in component_roots]
            if roots:
                root = 'derived-from:' + '+'.join(roots)
        groups.setdefault(root, []).append(correction_id)
    return tuple(({'root_cause_id': root, 'member_review_ids': tuple(members)} for root, members in groups.items()))

def build_final_correction_request(*, original_request_sha256: str, response: Mapping[str, Any], grade: Mapping[str, Any], key: Mapping[str, Any], teachback: Mapping[str, Any], novelty_investigation: Mapping[str, Any], learning_history: Mapping[str, Any] | None = None) -> dict:
    if type(original_request_sha256) is not str or len(original_request_sha256) != 64:
        raise ValueError('original principal request sha256 required')
    if type(response) is not dict or not isinstance(response.get('session_id'), str) or not response['session_id'].strip():
        raise ValueError('initial Frankie session identity required')
    if grade.get('schema') != classroom.GRADE_SCHEMA or grade.get('exhaustive_audit', {}).get('coverage_proven') is not True:
        raise ValueError('complete Dipole post-grade required')
    items = evidence_review_items(grade, key, teachback)
    ids = tuple(grade.get('correction_ids', ()))
    if tuple((item['correction_id'] for item in items)) != ids:
        raise ValueError('learner evidence-review order differs from host grade')
    body = {'schema': CORRECTION_REQUEST_SCHEMA, 'original_request_sha256': original_request_sha256, 'session_id': response['session_id'], 'model_identity_as_reported_by_session': response['model_identity_as_reported_by_session'], 'post_grade_hash': grade['post_grade_hash'], 'correction_ids': ids, 'data_review_items': items, 'root_cause_groups': group_review_items(items), 'novelty_investigation': novelty_investigation, 'instruction': "Dipole investigated the specific causal evidence before responding. Review each data_review_item locally. Where a claim differs, the wording is 'the data is showing this instead'; do not infer that Frankie's whole premise is rejected. Novel findings are not scored as errors merely for being new. Stay in this exact session, resolve every correction_id in your own words, and state any remaining disagreement explicitly."}
    if learning_history is not None:
        from .dipole_classroom_learning import validate_history
        body['learning_history'] = validate_history(learning_history)
        body['instruction'] += ' Build on the complete retained learning history, preserving source identities, uncertainty and corrections.'
    body['request_sha256'] = evidence_hash(body)
    return body

def bind_final_resolution_requirement(correction: Mapping[str, Any]) -> dict:
    if type(correction) is not dict or correction.get('schema') != CORRECTION_REQUEST_SCHEMA:
        raise ValueError('Dipole correction request required')
    body = {k: v for k, v in correction.items() if k != 'request_sha256'}
    body['instruction'] += ' Your dipole_acknowledgement must include correction_resolutions: one ordered object {correction_id, corrected_understanding} for every correction_id in data_review_items. If there are no correction_ids, correction_resolutions must be an empty list. A bare ID echo is not sufficient.'
    body['request_sha256'] = evidence_hash(body)
    return body

def _render_final_pre(message: Mapping[str, Any]) -> str:
    stripped = dict(message)
    prior = stripped.get('prior_cycle_correction')
    stripped['prior_cycle_correction'] = None
    rendered = render_pre_message(stripped)
    extras = ['# Classroom interpretation notes', '', f"Direction definition: {message['direction_definition']}", '', f"Novelty invitation: {message['novelty_invitation']}", '']
    if prior is not None:
        extras += ['## Prior-cycle correction summary', '', prior['guidance'], '', f"Prior correction IDs: `{prior['correction_ids']}`", f"Prior-cycle mastery: `{prior['prior_cycle_mastered']}`", '']
    from .dipole_classroom_learning import learning_text
    return rendered + '\n\n' + '\n'.join(extras) + learning_text(message.get('learning_history'))

def _render_novel_findings(findings: Sequence[Mapping[str, Any]]) -> str:
    parts = ["# Frankie's novel findings", '']
    if not findings:
        parts += ['No novel finding was asserted in this cycle.', '']
        return '\n'.join(parts)
    for finding in findings:
        parts += [f"## {finding['finding_id']}", '', f"Premise: {finding['premise']}", f"Why Frankie believes it is new: {finding['why_novel']}", 'Causal evidence references:']
        for ref in finding['evidence_refs']:
            parts.append(f'- `{ref}`')
        parts.append('')
    return '\n'.join(parts)

def _render_dipole_review(correction: Mapping[str, Any]) -> str:
    parts = ["# Dipole's actual same-session evidence review", '', 'This section is exactly the evidence review sent back to Frankie. The complete host grade and teacher key are deliberately not printed here.', '']
    if correction['data_review_items']:
        for item in correction['data_review_items']:
            parts += [f"## {item['correction_id']}", '', item['message'], '']
            # Every field of the item was sent to Frankie; print them so the transcript IS the exchange.
            for field, value in item.items():
                if field not in ('correction_id', 'message'):
                    parts.append(f"- {field}: `{value}`")
            parts.append('')
    else:
        parts += ['No curriculum factual subclaim required a data-difference review.', '']
    parts += ['## Root-cause grouping', '']
    if correction['root_cause_groups']:
        for group in correction['root_cause_groups']:
            parts.append(f"- `{group['root_cause_id']}` -> `{group['member_review_ids']}`")
    else:
        parts.append('- none')
    parts += ['', "## Dipole investigates Frankie's novel findings", '']
    novelty = correction['novelty_investigation']
    if not novelty['findings']:
        parts += ['No novel finding required investigation.', '']
    else:
        for finding in novelty['findings']:
            parts += [f"### {finding['finding_id']}", '', finding['teacher_response'], '', f"Status: `{finding['status']}`", f"Premise disposition: `{finding['premise_disposition']}`", f"Independent-discovery eligible: `{finding['independent_discovery_eligible']}`", '']
            for inspected in finding['inspected_evidence']:
                parts.append(f"- inspected `{inspected['scope']}`: `{inspected['status']}`")
            for difference in finding['specific_data_differences']:
                parts.append(f"- {difference['message']}")
            if finding['not_yet_testable']:
                parts.append(f"- Not yet testable by this Dipole fact key: `{finding['not_yet_testable']}`")
            parts.append('')
    return '\n'.join(parts)

def render_final_transcript(pre_message: Mapping[str, Any], teachback: Mapping[str, Any], novel_findings: Sequence[Mapping[str, Any]], correction: Mapping[str, Any], acknowledgement: Mapping[str, Any]) -> str:
    header = '\n'.join(['# Dipole classroom — actual exchange transcript', '', "This transcript contains the model-visible teaching/correction exchange and Frankie's responses only. The full host grade and teacher key are excluded.", '', 'Narrative prose and novel hypotheses are retained for audit but are not part of the deterministic classroom mastery score. Novelty is evaluated separately.'])
    return '\n\n---\n\n'.join((header, _render_final_pre(pre_message), render_teachback(teachback), _render_novel_findings(novel_findings), _render_dipole_review(correction), render_acknowledgement(acknowledgement))) + '\n'

class FinalDipoleClassroomPrincipalAdapter(hardened.HardenedDipoleClassroomPrincipalAdapter):
    """Leak-resistant classroom plus protected novelty and local evidence review."""
    def prepare(self, handoff_directory):
        attachment = FrankiePrincipalAdapter.prepare(self, handoff_directory)
        visible = final_model_visible_classroom(self.classroom_package)
        attachment = dict(attachment)
        attachment['dipole_classroom'] = visible
        attachment['attachment_hash'] = digest({k: v for k, v in attachment.items() if k != 'attachment_hash'})
        self._retain_audit('dipole-classroom-source.json', self.classroom_package['source'])
        self._retain_audit('dipole-classroom-teacher-key.audit.json', self.classroom_package['teacher_key'])
        self._retain('dipole-classroom-pre-message.json', self.classroom_package['pre_message'])
        self._retain('dipole-classroom-model-visible.json', visible)
        return attachment
    def _request(self, request_id, attachment):
        request = FrankiePrincipalAdapter._request(self, request_id, attachment)
        visible = attachment.get('dipole_classroom')
        # A retained attachment (session-request.json) holds lists where the c15-loaded package holds tuples: compare in
        # json_form, as every retained-versus-live comparison does (recorder refusals, 2026-09-21, run 35632927377).
        if json_form(visible) != json_form(final_model_visible_classroom(self.classroom_package)):
            raise ValueError('principal attachment Dipole classroom differs from final model-visible contract')
        request = dict(request)
        request['instruction'] += ' Before giving feedback, complete the attached Dipole classroom. Your response must include dipole_teachback with schema DIPOLE_CLASSROOM_TEACHBACK_V1 and cover all 19 dimensions in governed order. For every dimension provide state_counts for PRESENT/MISSING/INVALID/ABLATED, terminal_state, first-to-last PRESENT direction, explanation, why, market_behavior, fifo_full_book_order_link, evidence, uncertainty, and relationships. Graded direction means first PRESENT versus last PRESENT in this retained cycle window; intrawindow excursions may still exist. Set relationship_pairs_considered to 171 and future_outcome_claimed false. Also provide dipole_observation_review as exactly 19 ordered objects {name,observations}; each observations list must account for every retained cursor as {cursor,state,value,explanation}, with null value for non-PRESENT states. Also provide dipole_relationship_scan as exactly 171 canonical ordered pair objects {left,right,direction_relation,correlation_interpretation,developing_structure}; direction_relation must be SAME_DIRECTION, OPPOSITE_DIRECTION, or UNRESOLVED. After the required review, include dipole_novel_findings as a list (empty when none). Each novel finding must use schema FRANKIE_DIPOLE_NOVEL_FINDING_V1 and contain {schema,finding_id,premise,why_novel,evidence_refs,future_outcome_claimed}. A new idea is not a classroom error merely because Dipole did not teach it. Cite causal evidence, distinguish hypothesis from fact, and set future_outcome_claimed false. Do not skip repetitive, neutral, missing, invalid, or ablated evidence.'
        request['dipole_classroom_model_visible_hash'] = visible['model_visible_hash']
        return request
    def _recover_with_classroom(self, request_id, attachment, *, dispatch_followup):
        envelope = FrankiePrincipalAdapter.recover(self, request_id, attachment)
        request = json.loads((self.directory / 'session-request.json').read_bytes())
        retained = json.loads((self.directory / 'session-response.json').read_bytes())
        initial_response = retained['response']
        teachback, grade = grade_initial_response(self.classroom_package, initial_response)
        grade = apply_relationship_view_crosscheck(grade, initial_response)
        novel_findings = validate_novel_findings(initial_response.get('dipole_novel_findings'), self.classroom_package['pre_message'])
        novelty = investigate_novel_findings(self.classroom_package['teacher_key'], novel_findings, mode=self.classroom_package['binding']['mode'], learning_policy=self.classroom_package['binding'].get('learning_policy'))
        self._retain('dipole-classroom-teachback.json', teachback)
        self._retain_audit('dipole-classroom-post-grade.json', grade)
        self._retain('dipole-classroom-novel-findings.json', novel_findings)
        self._retain('dipole-classroom-novelty-investigation.json', novelty)
        correction = bind_final_resolution_requirement(build_final_correction_request(original_request_sha256=digest(request), response=initial_response, grade=grade, key=self.classroom_package['teacher_key'], teachback=teachback, novelty_investigation=novelty, learning_history=self.classroom_package['pre_message'].get('learning_history')))
        correction_path = self.directory / 'classroom-correction-request.json'
        created = False
        if correction_path.exists():
            if json.loads(correction_path.read_bytes()) != json_form(correction):
                raise ValueError('retained Dipole classroom correction request changed')
        else:
            _write(correction_path, correction)
            created = True
        response_path = self.directory / 'classroom-correction-response.json'
        if not response_path.exists():
            if not created or not dispatch_followup or self.session_executor is None:
                raise PrincipalPending('same Frankie session must consume Dipole classroom correction')
            dispatched = self.session_executor(correction)
            self._record_correction_response(correction, dispatched)
        correction_envelope = json.loads(response_path.read_bytes())
        self._attest_host(correction_envelope['response'], correction_envelope['host_attestation'], correction)
        base_acknowledgement = validate_correction_response(correction=correction, response=correction_envelope['response'], initial_response=initial_response, grade=grade)
        acknowledgement = validate_correction_resolutions(correction_envelope['response'].get('dipole_acknowledgement'), grade, base_acknowledgement)
        self._retain('dipole-classroom-acknowledgement.json', acknowledgement)
        completion = finish(self.classroom_package, teachback=teachback, grade=grade, acknowledgement=acknowledgement)
        self._retain('dipole-classroom-completion.json', completion)
        transcript = render_final_transcript(self.classroom_package['pre_message'], teachback, novel_findings, correction, acknowledgement)
        transcript_path = self._retain_text('dipole-classroom-transcript.md', transcript)
        self._retain('dipole-classroom-receipt.json', {'schema': 'FRANKIE_DIPOLE_CLASSROOM_RECEIPT_V2', 'classroom_binding_hash': self.classroom_package['binding']['classroom_binding_hash'], 'teacher_key_hash': self.classroom_package['teacher_key']['teacher_key_hash'], 'completion_hash': completion['completion_hash'], 'exhaustive_audit_hash': completion['exhaustive_audit_hash'], 'observation_claims_reviewed': completion['observation_claims_reviewed'], 'relationship_pairs_explicitly_reviewed': completion['relationship_pairs_explicitly_reviewed'], 'correction_resolutions': len(acknowledgement['correction_resolutions']), 'novel_findings': len(novel_findings), 'novelty_investigation_hash': novelty['investigation_bundle_hash'], 'independent_discovery_eligible': final_model_visible_classroom(self.classroom_package)['independent_discovery_eligible'], 'transcript_scope': 'MODEL_VISIBLE_EXCHANGE_ONLY', 'transcript': file_witness(transcript_path), 'initial_session_id': initial_response['session_id'], 'correction_session_id': correction_envelope['response']['session_id'], 'teacher_complete': completion['teacher_complete']})
        return envelope
