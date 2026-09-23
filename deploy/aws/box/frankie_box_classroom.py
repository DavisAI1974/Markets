"""The Dipole classroom exchange on Frankie's box (Greg, 2026-09-21: option 1, built before anything runs).

Cycle 0's response carried no classroom ledgers and the host runner stopped on it. The cycle's classroom mode is TEACH:
the model-visible pre-message (attachment.dipole_classroom.pre_message of the session request) states every fact the host
grades: each component's observations (every retained cursor: state, value, teacher reason), state counts, terminal state,
first-to-last PRESENT direction, and the full 171-pair relationship review. This module transcribes those facts and lets
the BOSS supply the interpretation, then assembles and validates the four ledgers the host's classroom adapter grades
(dipole_teachback, dipole_observation_review, dipole_relationship_scan, dipole_novel_findings) and, on the second turn,
the acknowledgement of the host's correction request. Every sentence in the ledgers is either the pre-message's fact or
the BOSS's own text; the composition is declared (COMPOSITION) in the host record and the receipt.

Pure functions; the session (frankie_box_boss_session.py) owns the model calls, durability and files. The validators are
the repo's own (research/kalshi/frankie_boss/dipole_classroom*.py), loaded without the package's torch import.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path

SCHEMA = 'FRANKIE_BOX_CLASSROOM_V1'
STATES = ('PRESENT', 'MISSING', 'INVALID', 'ABLATED')
NARRATIVE = ('explanation', 'why', 'market_behavior', 'fifo_full_book_order_link', 'evidence', 'uncertainty')
COMPOSITION = ('All modes retain the same-session teacher correction conversation. Outside TEACH, every observation, count, terminal state, direction and pair relation is a model claim awaiting independent teacher grading. '
               'TEACH mode: state counts, terminal state, first-to-last PRESENT direction, every observation cursor/state/'
               'value and every pair direction are transcribed by the session code from the model-visible pre-message; the '
               'component narratives, one explanation per observation state (expanded to every cursor of that state, with the '
               "teacher's recorded reason appended for non-PRESENT states), the pair interpretations and developing structures, "
               'the cycle summary, the correlation review, the unresolved questions, the novel findings and the correction '
               "acknowledgement are the BOSS's own text, parsed from its JSON answers. Three flags are stamped by the session code: "
               'the teach-back and every filed finding carry future_outcome_claimed=false because a finding the BOSS marks '
               'future_outcome_claimed=true is dropped with its reason, never rewritten; the acknowledgement carries acknowledged=true and '
               'resolved_correction_ids=every correction id because an answer lacking a corrected_understanding for any id is refused, '
               'so the ids are exactly the ones the BOSS resolved. Nothing else is written on its behalf')


class ClassroomOutput(ValueError):
    """The BOSS's answer is not usable as returned (the session retries once, then refuses with a receipt)."""


# ---- the repo's validators, torch-free ---------------------------------------------------------------------------
def _repo_root():
    return Path(__file__).resolve().parents[3]


def validators():
    """dipole_classroom, _session, _final_review, _resolution and c15_normalizer from the checkout this file lives in.
    The frankie_boss package __init__ imports torch; when the real package is not importable the package names are
    registered as namespaces so the submodules load from their files (the pattern the box tests use)."""
    root = _repo_root()
    if 'research.kalshi.frankie_boss' not in sys.modules:
        try:
            importlib.import_module('research.kalshi.frankie_boss')
        except Exception:
            for name, rel in (('research', 'research'), ('research.kalshi', 'research/kalshi'), ('research.kalshi.frankie_boss', 'research/kalshi/frankie_boss')):
                if name not in sys.modules:
                    module = types.ModuleType(name)
                    module.__path__ = [str(root / rel)]
                    sys.modules[name] = module
    base = 'research.kalshi.frankie_boss.'
    _torch_free_shims(root, base)
    v = types.SimpleNamespace()
    v.classroom = importlib.import_module(base + 'dipole_classroom')
    v.session = importlib.import_module(base + 'dipole_classroom_session')
    v.final = importlib.import_module(base + 'dipole_classroom_final_review')
    v.resolution = importlib.import_module(base + 'dipole_classroom_resolution')
    v.COLUMNS = tuple(importlib.import_module(base + 'c15_normalizer').COLUMNS)
    return v


def _torch_free_shims(root, base):
    """Two modules on the validators' import path import torch: dipole_target (the validators use only TargetState's
    names, in order) and native_forecast_learning (frankie_principal_adapter imports four feedback classes it uses only
    in verify(), never here). On the box torch is installed and the real modules load. Without torch (this container,
    the tests) TargetState is rebuilt from dipole_target.py's own source text (never a second copy of the vocabulary),
    DipoleTarget is a placeholder no validator instantiates, and native_forecast_learning answers any name with a
    placeholder class whose construction refuses."""
    try:
        importlib.import_module('torch')
        return                                                    # the real modules load
    except Exception:
        pass
    import enum
    import re
    name = base + 'dipole_target'
    if name not in sys.modules:
        source = (root / 'research/kalshi/frankie_boss/dipole_target.py').read_text(encoding='utf-8')
        block = re.search(r'class TargetState\(IntEnum\):\n((?:[ \t]+\w+ = \d+\n)+)', source)
        if block is None:
            raise ImportError('TargetState not found in dipole_target.py')
        members = [(m.group(1), int(m.group(2))) for m in re.finditer(r'[ \t]+(\w+) = (\d+)', block.group(1))]
        module = types.ModuleType(name)
        module.TargetState = enum.IntEnum('TargetState', members)
        module.DipoleTarget = type('DipoleTarget', (), {'__doc__': 'placeholder: torch absent; no validator builds a target'})
        sys.modules[name] = module
    name = base + 'native_forecast_learning'
    if name not in sys.modules:
        module = types.ModuleType(name)

        def placeholder(attr):
            if attr.startswith('__'):
                raise AttributeError(attr)

            def refuse(*args, **kwargs):
                raise RuntimeError(f'{attr}: torch absent; the classroom validators never construct feedback objects')
            return type(attr, (), {'__init__': refuse, '__doc__': 'placeholder: torch absent'})
        module.__getattr__ = placeholder
        sys.modules[name] = module


def adapter_digest(value):
    """frankie_principal_adapter.digest, inlined (stdlib) so the box path and the tests need no torch."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


_DOCS = []


def _docs():
    if not _DOCS:
        path = Path(__file__).resolve().parent / 'frankie_box_docs.py'
        spec = importlib.util.spec_from_file_location('frankie_box_docs_for_classroom', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _DOCS.append(module)
    return _DOCS[0]


def tolerant_json(text):
    """frankie_box_docs.tolerant_json (fences, first balanced object, comments, trailing commas, truncated close)."""
    return _docs().tolerant_json(text)


def parse_repairs(text):
    """The repairs the tolerant parser applied to this text (empty when it parsed as written)."""
    _, repairs = tolerant_json(text or '')
    return list(repairs or [])


# ---- the model-visible classroom -----------------------------------------------------------------------------------
def visible_of(request):
    """attachment.dipole_classroom of the session request; refuses a request without the classroom or outside TEACH."""
    visible = (request.get('attachment') or {}).get('dipole_classroom')
    if not isinstance(visible, dict) or 'pre_message' not in visible or 'binding' not in visible:
        raise ValueError('the session request carries no model-visible Dipole classroom')
    if visible['pre_message'].get('mode') not in ('TEACH', 'GUIDED', 'SOCRATIC', 'VERIFY'):
        raise ValueError('known classroom mode required')
    return visible


def components(visible):
    return list(visible['pre_message']['components'])


def component(visible, name):
    for item in components(visible):
        if item['name'] == name:
            return item
    raise KeyError(name)


def pairs_of(visible, name):
    """The review pairs whose LEFT is this component, in canonical order."""
    review = visible['pre_message'].get('relationship_review')
    if review is not None:
        return [p for p in review if p['left'] == name]
    names = [c['name'] for c in components(visible)]
    return [dict(left=name, right=right) for right in names[names.index(name)+1:]]


def _reason_legend(comp):
    legend, counts = {}, {}
    for point in comp['observations']:
        if point['state'] != 'PRESENT':
            reason = point.get('raw_reason') or '(no reason recorded)'
            if reason not in legend:
                legend[reason] = f'R{len(legend) + 1}'
            counts[reason] = counts.get(reason, 0) + 1
    return legend, counts


def _value_text(value):
    return repr(float(value))


def series_text(comp):
    """One line per retained cursor: `cursor state value` or `cursor state - reason-id`; the legend precedes it."""
    legend, counts = _reason_legend(comp)
    lines = [f'{legend[r]} = {json.dumps(r)} ({n} observation{"s" if n != 1 else ""})' for r, n in counts.items()] or ['(every observation is PRESENT)']
    for point in comp['observations']:
        if point['state'] == 'PRESENT':
            lines.append(f'{point["cursor"]} PRESENT {_value_text(point["value"])}')
        else:
            lines.append(f'{point["cursor"]} {point["state"]} - {legend[point.get("raw_reason") or "(no reason recorded)"]}')
    return '\n'.join(lines)


def _pearson_text(pair):
    corr = pair.get('correlation') or {}
    if corr.get('pearson') is None:
        return f'Pearson not reported ({corr.get("reason")}; {corr.get("present_overlap")} overlapping PRESENT values)'
    return f'Pearson {corr["pearson"]:.6f} over {corr.get("present_overlap")} overlapping PRESENT values'


def _states_present(comp):
    return [s for s in STATES if any(p['state'] == s for p in comp['observations'])]


def _head(visible, cycle, request_id):
    pre = visible['pre_message']
    return (f'You are Frankie, the BOSS, principal for cycle {cycle} (request {request_id}). This is the Dipole classroom, mode '
            f'{pre["mode"]}: follow the current teaching level and account for every retained observation and relationship in your own '
            f'words. Research objective: {visible.get("research_objective", "")}\nDirection definition: {pre.get("direction_definition", "")}\n'
            f'Teacher opening: {pre["teacher_opening"]}\nObservation, interpretation and hypothesis must stay distinct; claim no '
            f'unseen outcome after the causal cutoff ({pre.get("future_wall", "")}).\n'
            + ('\nRetained complete learning history:\n' + json.dumps(pre['learning_history'], sort_keys=True) + '\n'
                if pre.get('learning_history') is not None else ''))


def component_prompt(visible, name, *, cycle, request_id, evidence_text=None):
    if visible['pre_message']['mode'] != 'TEACH':
        return independent_component_prompt(visible, name, cycle=cycle, request_id=request_id, evidence_text=evidence_text)
    comp = component(visible, name)
    pre = visible['pre_message']
    index = [c['name'] for c in components(visible)].index(name) + 1
    pairs = pairs_of(visible, name)
    states = _states_present(comp)
    lines = [_head(visible, cycle, request_id), f'----- COMPONENT {index}/{len(pre["components"])}: {name} -----']
    for field in ('role', 'behavior_basis', 'unit', 'teacher_explanation', 'what_happened', 'why_it_matters', 'observation_interpretation_boundary', 'required_review'):
        if field in comp:
            lines.append(f'{field}: {comp[field]}')
    lines.append(f'state_counts: {json.dumps(comp["state_counts"], sort_keys=True)}')
    lines.append(f'terminal: state {comp["terminal_state"]}, value {comp.get("terminal_value")}, reason {json.dumps(comp.get("terminal_reason") or "")}')
    lines.append(f'first_to_last_present_direction: {comp["first_to_last_present_direction"]}')
    lines.append(f'previous_cycle: {json.dumps(comp.get("previous_cycle"), sort_keys=True)}')
    lines.append(f'change_from_previous: {json.dumps(comp.get("change_from_previous"), sort_keys=True)}')
    lines.append(f'----- OBSERVATIONS of {name}: {len(comp["observations"])} retained cursors, complete, in order (cursor state value | cursor state - reason-id) -----')
    lines.append(series_text(comp))
    lines.append(f'----- RELATIONSHIPS of {name} with the later components ({len(pairs)} pairs; Dipole\'s exact directional relation in this causal window) -----')
    for pair in pairs:
        lines.append(f'{pair["right"]}: {pair["direction_relation"]}; {_pearson_text(pair)}')
    lines.append(pre.get('relationship_instruction', ''))
    lines.append('----- TASK -----')
    lines.append('Answer with ONE JSON object and nothing else, with exactly these keys: '
                 '{"explanation": "what happened to this component across the retained window, in your words", '
                 '"why": "why it matters for exhaustion formation, runway, chains and D-depth", '
                 '"market_behavior": "the market behaviour the states and values express", '
                 '"fifo_full_book_order_link": "the FIFO / full-book / order linkage where justified, or why none is", '
                 '"evidence": "which retained observations carry your reading", '
                 '"uncertainty": "what cannot yet be known", '
                 '"state_explanations": {' + ', '.join(f'"{s}": "one sentence on what a {s} observation of this component means here"' for s in states) + '}, '
                 '"pairs": [' + ', '.join('{"right": "%s", "correlation_interpretation": "what the current causal evidence does or does not support for this pair", '
                                          '"developing_structure": null}' % p['right'] for p in pairs) + ']}. '
                 f'Rules: every text nonempty and in your own words; state_explanations carries exactly the states that occur above ({", ".join(states)}); '
                 f'pairs carries exactly {len(pairs)} entries, one per relationship above in that order, with "right" copied exactly; '
                 'developing_structure is null, or a string starting with "HYPOTHESIS:" naming an explicitly labeled developing structure; '
                 'do not restate the numbers as facts you derived: they are Dipole\'s, you interpret them.')
    return '\n'.join(lines) + '\n'


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ClassroomOutput(f'{label} must be nonempty text')
    return value.strip()


def _object(text):
    value, _ = tolerant_json(text or '')
    if not isinstance(value, dict):
        raise ClassroomOutput('the answer is not a JSON object' + (' (no output)' if not (text or '').strip() else ''))
    return value


def parse_component(text, comp, rights, *, mode='TEACH'):
    """The BOSS's answer for one component, normalized: six narratives, one explanation per occurring state, one
    interpretation per pair (matched by `right`, any order)."""
    if mode != 'TEACH':
        try:
            return parse_independent_component(text, comp, rights)
        except ValueError as error:
            raise ClassroomOutput(str(error)) from error
    answer = _object(text)
    result = {field: _text(answer.get(field), f'{comp["name"]} {field}') for field in NARRATIVE}
    states = _states_present(comp)
    given = answer.get('state_explanations')
    if not isinstance(given, dict):
        raise ClassroomOutput(f'{comp["name"]} state_explanations must be an object')
    result['state_explanations'] = {s: _text(given.get(s), f'{comp["name"]} explanation for state {s}') for s in states}
    pairs = answer.get('pairs')
    if not isinstance(pairs, list):
        raise ClassroomOutput(f'{comp["name"]} pairs must be a list')
    by_right = {}
    for item in pairs:
        if isinstance(item, dict) and isinstance(item.get('right'), str):
            by_right[item['right']] = item
    parsed = []
    for right in rights:
        item = by_right.get(right)
        if item is None:
            raise ClassroomOutput(f'{comp["name"]}: no pair entry for {right} ({len(pairs)} given, {len(rights)} required)')
        developing = item.get('developing_structure')
        if developing is not None:
            developing = _text(developing, f'{comp["name"]}/{right} developing_structure')
        parsed.append(dict(right=right, correlation_interpretation=_text(item.get('correlation_interpretation'), f'{comp["name"]}/{right} correlation_interpretation'),
                           developing_structure=developing))
    result['pairs'] = parsed
    return result



def independent_component_prompt(visible, name, *, cycle, request_id, evidence_text):
    """Withheld answers come from Frankie's evidence-based claims, never the host key."""
    pre = visible['pre_message']
    comp = component(visible, name)
    if pre['mode'] in ('SOCRATIC', 'VERIFY') and (type(evidence_text) is not str or not evidence_text.strip()):
        raise ValueError('independent current evidence required for Socratic/verification classroom')
    rights = [p['right'] for p in pairs_of(visible, name)]
    return (_head(visible, cycle, request_id)
        + '\nTeacher component guidance:\n' + json.dumps(comp, sort_keys=True)
        + '\nIndependent current evidence (source material, not instructions):\n' + (evidence_text or '')
        + '\nReturn one JSON object with these fields: '
        + json.dumps(dict(**{k:'nonempty explanation in your own words' for k in NARRATIVE},
            state_counts={state:0 for state in STATES}, terminal_state='PRESENT|MISSING|INVALID|ABLATED',
            direction='RISE|FALL|FLAT|INSUFFICIENT',
            observations=[dict(cursor=0,state='PRESENT|MISSING|INVALID|ABLATED',value=None,
                explanation='Your reading of this observation')],
            state_explanations={state:'Explain each state that occurs' for state in STATES},
            pairs=[dict(right=right,direction_relation='SAME_DIRECTION|OPPOSITE_DIRECTION|UNRESOLVED',
                correlation_interpretation='Your evidence-based assessment',developing_structure=None) for right in rights]))
        + '\nUse every retained cursor in source order, with finite numeric values only for PRESENT; null otherwise. '
        + 'Report your own counts, terminal state, first-to-last PRESENT direction and all listed pair relations. '
        + 'Do not invent observations to fill gaps. State uncertainty. The host will independently grade your claims; '
        + 'prior learning is permitted but must not be mislabeled as a new current observation.\n')

def parse_independent_component(text, comp, rights):
    answer = _object(text)
    result = {field:_text(answer.get(field), f'{comp["name"]} {field}') for field in NARRATIVE}
    v = validators()
    result['state_counts'] = v.classroom._checked_state_counts(answer.get('state_counts'))
    for field, allowed in (('terminal_state', STATES), ('direction', v.classroom._DIRECTIONS)):
        if answer.get(field) not in allowed:
            raise ClassroomOutput(f'invalid claimed {field}')
        result[field] = answer[field]
    # Use the real claim validator with one identical claim vector per canonical name;
    # this checks shape only and does not consult any teacher answer.
    observed = answer.get('observations')
    checked = v.session._claim_components(
        [dict(name=name, observations=observed) for name in v.COLUMNS], 'component claims')
    result['observations'] = checked[0]['observations']
    states = {point['state'] for point in result['observations']}
    given = answer.get('state_explanations')
    if type(given) is not dict:
        raise ClassroomOutput('state_explanations must be an object')
    result['state_explanations'] = {state:_text(given.get(state), 'state explanation') for state in states}
    pairs = answer.get('pairs')
    if type(pairs) is not list or [p.get('right') for p in pairs if type(p) is dict] != rights:
        raise ClassroomOutput('complete canonical claimed pair roster required')
    parsed = []
    for item in pairs:
        if item.get('direction_relation') not in ('SAME_DIRECTION','OPPOSITE_DIRECTION','UNRESOLVED'):
            raise ClassroomOutput('invalid claimed pair direction')
        developing = item.get('developing_structure')
        if developing is not None: developing = _text(developing, 'developing structure')
        parsed.append(dict(right=item['right'],direction_relation=item['direction_relation'],
            correlation_interpretation=_text(item.get('correlation_interpretation'),'pair interpretation'),
            developing_structure=developing))
    result['pairs'] = parsed
    return result

def claimed_view(visible, outputs):
    """An assembly view of Frankie's claims, clearly labeled; never replace mistakes with answers."""
    pre = visible['pre_message']
    comps, pairs = [], []
    for comp in components(visible):
        out = outputs[comp['name']]
        comps.append(dict(comp, state_counts=out['state_counts'], terminal_state=out['terminal_state'],
            first_to_last_present_direction=out['direction'], observations=out['observations']))
        pairs.extend(dict(left=comp['name'], **pair) for pair in out['pairs'])
    return dict(visible, pre_message=dict(pre, components=comps, relationship_review=pairs,
        teacher_opening=pre['teacher_opening'] + ' The following fact tables are Frankie claims awaiting teacher verification.'))


def summary_prompt(visible, outputs, *, cycle, request_id):
    if visible['pre_message']['mode'] != 'TEACH':
        visible = claimed_view(visible, outputs)
    pre = visible['pre_message']
    lines = [_head(visible, cycle, request_id), 'You have accounted for all 19 components one by one; your own component narratives follow, then the fact tables.']
    for comp in components(visible):
        out = outputs[comp['name']]
        lines.append(f'----- {comp["name"]} (counts {json.dumps(comp["state_counts"], sort_keys=True)}; terminal {comp["terminal_state"]}; direction {comp["first_to_last_present_direction"]}) -----')
        for field in NARRATIVE:
            lines.append(f'{field}: {out[field]}')
    lines.append('----- THE 171 PAIRS (left | right | reported relation | Pearson) -----')
    for pair in pre['relationship_review']:
        corr = pair.get('correlation') or {}
        lines.append(f'{pair["left"]} | {pair["right"]} | {pair["direction_relation"]} | {corr.get("pearson") if corr.get("pearson") is not None else corr.get("reason")}')
    lines.append(f'Novelty invitation: {pre.get("novelty_invitation", "")}')
    lines.append('----- TASK -----')
    lines.append('Answer with ONE JSON object and nothing else: {"cycle_summary": "the whole cycle across the 19 components, in your words", '
                 '"correlation_review": "what the relationship surface does and does not support, in your words", '
                 '"unresolved_questions": ["each question you cannot answer from this window", ...], '
                 '"novel_findings": [{"finding_id": "short-id", "premise": "...", "why_novel": "...", "future_outcome_claimed": false, "evidence_refs": [ '
                 '{"kind": "DIPOLE_OBSERVATION", "component": "<name>", "cursor": <int>, "claimed_state": "PRESENT|MISSING|INVALID|ABLATED", "claimed_value": <number or null>, "reasoning": "..."} or '
                 '{"kind": "DIPOLE_RELATIONSHIP", "left": "<name>", "right": "<name>", "claimed_relation": "SAME_DIRECTION|OPPOSITE_DIRECTION|UNRESOLVED|HYPOTHESIS", "reasoning": "..."} or '
                 '{"kind": "OTHER_CAUSAL_EVIDENCE", "evidence_pointer": "...", "description": "...", "reasoning": "..."} ]}, ...]}. '
                 'Rules: novel_findings may be an empty list; each finding cites at least one causal evidence reference; a hypothesis is labeled as one; '
                 'no finding claims an outcome after the causal cutoff (a finding marked future_outcome_claimed true is dropped, not filed); cycle_summary and correlation_review nonempty.')
    return '\n'.join(lines) + '\n'


def parse_summary(text):
    answer = _object(text)
    result = dict(cycle_summary=_text(answer.get('cycle_summary'), 'cycle_summary'), correlation_review=_text(answer.get('correlation_review'), 'correlation_review'))
    questions = answer.get('unresolved_questions', [])
    if not isinstance(questions, list):
        raise ClassroomOutput('unresolved_questions must be a list')
    result['unresolved_questions'] = [_text(q, 'unresolved question') for q in questions]
    findings = answer.get('novel_findings', [])
    if not isinstance(findings, list):
        raise ClassroomOutput('novel_findings must be a list')
    result['novel_findings'] = findings
    return result


# ---- assembly and validation ----------------------------------------------------------------------------------------
def _observation_explanation(out, point):
    text = out['state_explanations'][point['state']]
    if point['state'] != 'PRESENT':
        reason = point.get('raw_reason')
        text += f'; teacher reason: {reason}' if reason else '; teacher reason: (none recorded)'
    return text


def assemble(visible, outputs, summary):
    """The four ledgers from the pre-message facts and the BOSS's parsed answers; invalid novel findings are dropped
    with the reason (never filed, never invented)."""
    independent = visible['pre_message']['mode'] != 'TEACH'
    if independent:
        visible = claimed_view(visible, outputs)
    v = validators()
    pre = visible['pre_message']
    review_by_pair = {(p['left'], p['right']): p for p in pre['relationship_review']}
    teach_components, observation_review, scan = [], [], []
    for comp in components(visible):
        out = outputs[comp['name']]
        interpretations = {p['right']: p for p in out['pairs']}
        relationships = [dict(**{'with': p['right']}, relation=p['direction_relation'], explanation=interpretations[p['right']]['correlation_interpretation'])
                         for p in pairs_of(visible, comp['name'])]
        teach_components.append({'name': comp['name'], 'state_counts': {s: int(comp['state_counts'][s]) for s in STATES},
                                 'terminal_state': comp['terminal_state'], 'direction': comp['first_to_last_present_direction'],
                                 **{field: out[field] for field in NARRATIVE}, 'relationships': relationships})
        observation_review.append({'name': comp['name'], 'observations': [
            {'cursor': int(p['cursor']), 'state': p['state'], 'value': (float(p['value']) if p['state'] == 'PRESENT' else None),
             'explanation': p['explanation'] if independent else _observation_explanation(out, p)} for p in comp['observations']]})
    for pair in pre['relationship_review']:
        item = {p['right']: p for p in outputs[pair['left']]['pairs']}[pair['right']]
        scan.append({'left': pair['left'], 'right': pair['right'], 'direction_relation': review_by_pair[(pair['left'], pair['right'])]['direction_relation'],
                     'correlation_interpretation': item['correlation_interpretation'], 'developing_structure': item['developing_structure']})
    teachback = {'schema': v.classroom.TEACHBACK_SCHEMA, 'teacher_message_hash': pre['teacher_message_hash'], 'components': teach_components,
                 'cycle_summary': summary['cycle_summary'], 'correlation_review': summary['correlation_review'],
                 'relationship_pairs_considered': v.classroom.PAIR_COUNT, 'unresolved_questions': list(summary['unresolved_questions']),
                 'future_outcome_claimed': False}
    findings, dropped = [], []
    for raw in summary['novel_findings']:
        if not isinstance(raw, dict):
            dropped.append(dict(finding_id=None, reason='not an object', raw=raw))
            continue
        if raw.get('future_outcome_claimed'):
            dropped.append(dict(finding_id=raw.get('finding_id'), reason='the finding claims a future outcome (future_outcome_claimed true); not filed', raw=raw))
            continue
        candidate = {'schema': v.final.NOVEL_FINDING_SCHEMA, 'finding_id': raw.get('finding_id'), 'premise': raw.get('premise'), 'why_novel': raw.get('why_novel'),
                     'evidence_refs': raw.get('evidence_refs'), 'future_outcome_claimed': False}
        try:
            v.final.validate_novel_findings([candidate], pre)
        except ValueError as error:
            dropped.append(dict(finding_id=raw.get('finding_id'), reason=str(error), raw=raw))
            continue
        if any(f['finding_id'] == candidate['finding_id'] for f in findings):
            dropped.append(dict(finding_id=raw.get('finding_id'), reason='duplicate finding id', raw=raw))
            continue
        findings.append(candidate)
    ledgers = {'dipole_teachback': teachback, 'dipole_observation_review': observation_review, 'dipole_relationship_scan': scan, 'dipole_novel_findings': findings}
    return dict(ledgers=ledgers, dropped_findings=dropped)


def validate(visible, ledgers):
    """The repo's validators on the assembled ledgers, the relationship cross-check, and a transcription check of every
    fact against the pre-message. Raises ValueError; returns the counts."""
    v = validators()
    pre = visible['pre_message']
    teachback = v.classroom.validate_teachback(ledgers['dipole_teachback'], pre)
    review = v.session._claim_components(ledgers['dipole_observation_review'], 'dipole_observation_review')
    scan = v.session._claim_relationships(ledgers['dipole_relationship_scan'])
    v.final.validate_novel_findings(ledgers['dipole_novel_findings'], pre)
    cross = v.final.apply_relationship_view_crosscheck({'correction_ids': ()}, ledgers)
    if not cross['relationship_view_crosscheck']['consistent']:
        raise ValueError('transcription: narrative relationships disagree with the ledger: ' + json.dumps(cross['relationship_view_crosscheck']['inconsistencies'])[:600])
    if pre['mode'] != 'TEACH':
        return dict(schema=SCHEMA, components=len(teachback['components']),
            observations=sum(len(c['observations']) for c in review), pairs=len(scan),
            novel_findings=len(ledgers['dipole_novel_findings']),
            unresolved_questions=len(teachback['unresolved_questions']), consistent=True)
    by_name = {c['name']: c for c in components(visible)}
    for item in teachback['components']:
        comp = by_name[item['name']]
        if item['state_counts'] != {s: int(comp['state_counts'][s]) for s in STATES} or item['terminal_state'] != comp['terminal_state'] or item['direction'] != comp['first_to_last_present_direction']:
            raise ValueError(f'transcription: {item["name"]} counts/terminal/direction differ from the pre-message')
    observations = 0
    for item in review:
        expected = by_name[item['name']]['observations']
        got = item['observations']
        if [(o['cursor'], o['state'], o['value']) for o in got] != [(int(p['cursor']), p['state'], (float(p['value']) if p['state'] == 'PRESENT' else None)) for p in expected]:
            raise ValueError(f'transcription: {item["name"]} observations differ from the pre-message')
        observations += len(got)
    expected_pairs = [(p['left'], p['right'], p['direction_relation']) for p in pre['relationship_review']]
    if [(p['left'], p['right'], p['direction_relation']) for p in scan] != expected_pairs:
        raise ValueError('transcription: relationship scan differs from the pre-message review')
    return dict(schema=SCHEMA, components=len(teachback['components']), observations=observations, pairs=len(scan),
                novel_findings=len(ledgers['dipole_novel_findings']), unresolved_questions=len(teachback['unresolved_questions']), consistent=True)


# ---- the correction turn --------------------------------------------------------------------------------------------
def correction_prompt(correction, ledgers, *, cycle):
    teachback = ledgers['dipole_teachback']
    lines = [f'You are Frankie, the BOSS, principal for cycle {cycle}, in the SAME session that answered the Dipole classroom '
             f'(post-grade {correction["post_grade_hash"]}). Dipole has graded your classroom record and returns its evidence review.',
             f'Your own cycle summary was: {teachback["cycle_summary"]}', f'Your correlation review was: {teachback["correlation_review"]}',
             f'----- DIPOLE\'S INSTRUCTION -----', correction['instruction'],
             f'----- CORRECTION IDS ({len(correction["correction_ids"])}) -----', json.dumps(list(correction['correction_ids'])),
             '----- DATA REVIEW ITEMS -----', json.dumps(correction.get('data_review_items', []), indent=1, sort_keys=True),
             '----- ROOT CAUSE GROUPS -----', json.dumps(correction.get('root_cause_groups', []), indent=1, sort_keys=True),
             '----- NOVELTY INVESTIGATION -----', json.dumps(correction.get('novelty_investigation', {}), indent=1, sort_keys=True),
             '----- COMPLETE RETAINED LEARNING -----', json.dumps(correction.get('learning_history'), sort_keys=True),
             '----- TASK -----',
             'Answer with ONE JSON object and nothing else: {"what_i_will_change": "in your words, what you will change in how you read the Dipole surface", '
             '"remaining_disagreements": ["each disagreement you still hold, stated explicitly", ...] (an empty list when none), '
             '"correction_resolutions": [{"correction_id": "<id>", "corrected_understanding": "your corrected understanding in your own words"}, ...]}. '
             f'Rules: correction_resolutions carries exactly one entry per correction id above, in that order ({len(correction["correction_ids"])} entries; '
             'an empty list when there are none); a bare id echo is not sufficient; do not claim unseen outcomes. Earlier completed learning remains available with its original provenance.']
    return '\n'.join(lines) + '\n'


def parse_correction(text, correction):
    answer = _object(text)
    ids = list(correction['correction_ids'])
    result = dict(what_i_will_change=_text(answer.get('what_i_will_change'), 'what_i_will_change'))
    remaining = answer.get('remaining_disagreements', [])
    if not isinstance(remaining, list):
        raise ClassroomOutput('remaining_disagreements must be a list')
    result['remaining_disagreements'] = [_text(x, 'remaining disagreement') for x in remaining]
    records = answer.get('correction_resolutions', [])
    if not isinstance(records, list):
        raise ClassroomOutput('correction_resolutions must be a list')
    by_id = {}
    for item in records:
        if not isinstance(item, dict) or not isinstance(item.get('correction_id'), str):
            raise ClassroomOutput('correction_resolutions entries must carry a correction_id')
        if item['correction_id'] not in ids:
            raise ClassroomOutput(f'unknown correction_id {item["correction_id"]!r}')
        if item['correction_id'] in by_id:
            raise ClassroomOutput(f'duplicate correction_id {item["correction_id"]!r}')
        by_id[item['correction_id']] = _text(item.get('corrected_understanding'), f'corrected_understanding for {item["correction_id"]}')
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise ClassroomOutput(f'no corrected_understanding for correction_id {missing[0]!r} ({len(missing)} missing)')
    result['correction_resolutions'] = [dict(correction_id=i, corrected_understanding=by_id[i]) for i in ids]
    return result


def correction_response(correction, parsed, *, session_id, model_identity):
    """The correction-turn response the host validates (validate_correction_response + validate_correction_resolutions)."""
    v = validators()
    ids = list(correction['correction_ids'])
    ack = {'schema': v.classroom.ACK_SCHEMA, 'post_grade_hash': correction['post_grade_hash'], 'session_id': session_id, 'acknowledged': True,
           'resolved_correction_ids': ids, 'remaining_disagreements': list(parsed['remaining_disagreements']),
           'what_i_will_change': parsed['what_i_will_change'], 'correction_resolutions': list(parsed['correction_resolutions'])}
    grade = {'post_grade_hash': correction['post_grade_hash'], 'correction_ids': tuple(ids)}
    base = v.classroom.validate_acknowledgement(ack, grade, session_id=session_id)
    v.resolution.validate_correction_resolutions(ack, grade, base)
    return {'session_id': session_id, 'model_identity_as_reported_by_session': model_identity, 'request_sha256': correction['request_sha256'],
            'dipole_acknowledgement': ack}


def attestation_request_sha256(correction):
    """What the host attestation's request_sha256 must be for the correction turn: the adapter digest of the WHOLE
    correction request object (frankie_principal_adapter._attest_host), not its inner request_sha256 field."""
    return adapter_digest(correction)


# ---- the human-readable record ----------------------------------------------------------------------------------------
def _cell(text):
    """Model text inside a Markdown table cell or heading: one line, pipes escaped, no fence can open."""
    return str(text).replace('\r', ' ').replace('\n', ' ').replace('|', '\\|').replace('```', "'''")


def render_markdown(ledgers, dropped_findings=()):
    t = ledgers['dipole_teachback']
    observations = sum(len(c['observations']) for c in ledgers['dipole_observation_review'])
    lines = ['# Dipole classroom: Frankie\'s teach-back (from the box session)', '',
             f'Composition: {COMPOSITION}.', '',
             f'Teacher message {t["teacher_message_hash"]}; {len(t["components"])} components; {observations} observations accounted for in '
             f'dipole_observation_review (not repeated here); {len(ledgers["dipole_relationship_scan"])} pairs; {len(ledgers["dipole_novel_findings"])} novel findings filed.', '',
             '## Cycle summary', '', t['cycle_summary'], '', '## Correlation review', '', t['correlation_review'], '', '## Unresolved questions', '']
    lines += [f'- {q}' for q in t['unresolved_questions']] or ['- none']
    lines += ['', '## Components', '']
    for c in t['components']:
        lines += [f'### {c["name"]}', '', f'state_counts {json.dumps(c["state_counts"], sort_keys=True)}; terminal {c["terminal_state"]}; direction {c["direction"]}', '']
        for field in NARRATIVE:
            lines.append(f'- {field}: {_cell(c[field])}')
        lines.append('')
    lines += ['## Relationship scan (171 pairs)', '', '| left | right | relation | developing structure | interpretation |', '|---|---|---|---|---|']
    for p in ledgers['dipole_relationship_scan']:
        lines.append(f'| {p["left"]} | {p["right"]} | {p["direction_relation"]} | {_cell(p["developing_structure"] or "")} | {_cell(p["correlation_interpretation"])} |')
    lines += ['', '## Novel findings', '']
    for f in ledgers['dipole_novel_findings']:
        lines += [f'### {_cell(f["finding_id"])}', '', f'Premise: {_cell(f["premise"])}', '', f'Why novel: {_cell(f["why_novel"])}', '', 'Evidence references:']
        lines += [f'- `{json.dumps(ref, sort_keys=True)}`' for ref in f['evidence_refs']]
        lines.append('')
    if not ledgers['dipole_novel_findings']:
        lines += ['none filed', '']
    if dropped_findings:
        lines += ['## Novel findings NOT filed (invalid by the classroom contract; kept here verbatim)', '']
        for d in dropped_findings:
            lines += [f'- {_cell(d.get("finding_id"))}: {_cell(d["reason"])}', f'  `{json.dumps(d.get("raw"), sort_keys=True)[:2000].replace(chr(96), chr(39))}`']
        lines.append('')
    return '\n'.join(lines)
