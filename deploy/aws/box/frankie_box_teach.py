"""The exhaustion/D teach-back (SPEC_CYCLE0_BEDROCK_20260921.md box-teach-exhaustion; Greg, 2026-09-21: "All 3", the
classroom also teaches exhaustion and D, box-side, beside the 19-dimension Dipole classroom; host grader unchanged).

One BOSS call on the Pod (no output limit), asked once more if unusable, then refused with a receipt. The FACTS are
computed by code from the session's own files (the bedrock layer statuses, the lineage rows' D-depth histogram and open
vs closed lineages, the ancestry gaps listed per event with the largest named and never averaged, the causal-clock
order check per group, the family descriptor counts, the candidate lane's measured verdict) plus the TEXT of the frozen
learned-structure files that define D and exhaustion, from the brain's frozen entry, whole. Every number the BOSS cites
must appear in the facts (the classroom's transcription check applied to numbers); a missing topic or a foreign number
is an unusable answer. Filed under work/teach/, in the docs bundle, the brain entry and a section of analysis.md;
NEVER a key of response.json (the host's response schema and classroom grader stay as they are). Stdlib only."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

SCHEMA = 'FRANKIE_BOX_TEACHBACK_V1'
FACTS_SCHEMA = 'FRANKIE_BOX_TEACH_FACTS_V1'
TOPICS = ('exhaustion', 'd_depth', 'families', 'prebirth', 'clocks')
FIELDS = ('what_it_is', 'how_this_cycle_shows_it', 'what_this_cycle_cannot_show', 'relation_to_dipole_state')
FROZEN_LAYERS = ('learned_d_structures_and_families', 'learned_dipoles_and_geometry',
                 'learned_chains_extensions_reappearances_ancestry', 'predecessor_ancestry_unresolved_chain_state')
FROZEN_DIR = 'frozen-learned-structure'
CLOCK_RULE = 'event_known_by <= feature_availability <= model_evaluation'
LARGEST_GAPS = 20
_NUMBER = re.compile(r'\d+(?:\.\d+)?')
_THOUSANDS = re.compile(r'(?<=\d),(?=\d{3}(?!\d))')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _load(path):
    return json.loads(Path(path).read_bytes())


def _layer_file(derive, name):
    entry = (derive.get('layers') or {}).get(name)
    if not entry or not entry.get('path') or not Path(entry['path']).is_file():
        return None
    return _load(entry['path'])


def _section_rows(derive, bedrock_layers, section):
    """The rows of one lifecycle section, from the first derived bedrock layer file that carries them (identical copies)."""
    for name in bedrock_layers:
        f = _layer_file(derive, name)
        if f and section in (f.get('lifecycle_sections') or []):
            rows = [r for r in (f.get('lifecycle_rows') or []) if r.get('emitting_section') == section]
            if rows:
                return rows
    return []


def _members(derive, name):
    f = _layer_file(derive, name)
    return list((f or {}).get('member_rows') or [])


def facts(work, brain):
    """The pre-message facts, exact and small, from work/derive.json, the bedrock layer files, the legacy structure
    observables and the brain's frozen entry. Refuses without a bedrock or without an included frozen file for each of
    the four layers that define D and exhaustion."""
    work, brain = Path(work), Path(brain)
    derive = _load(work / 'derive.json')
    bedrock = derive.get('bedrock')
    if not bedrock:
        raise ValueError('derive.json carries no bedrock; the teach-back needs the bedrock derivation')
    names = list(bedrock.get('layers') or [])
    layers = {}
    for name in names:
        entry = (derive.get('layers') or {}).get(name) or {}
        layers[name] = dict(status=entry.get('status'), count=entry.get('count', 0), reason=entry.get('reason'))
    lineage_rows = _section_rows(derive, names, 'lineage')
    depth = Counter(int(r.get('depth')) for r in lineage_rows if r.get('depth') is not None)
    status = Counter(str(r.get('status')) for r in lineage_rows)
    lineage = dict(nodes=len(lineage_rows), depth_histogram={str(k): depth[k] for k in sorted(depth)}, status_counts=dict(sorted(status.items())),
                   closed=status.get('CLOSED', 0), open=sum(v for k, v in status.items() if k != 'CLOSED'))
    recurrence_rows = _section_rows(derive, names, 'recurrence')
    per_event, every = [], []
    for i, row in enumerate(recurrence_rows):
        gaps = [int(g) for g in (row.get('gaps') or [])]
        per_event.append(dict(event=i, gap_count=row.get('gap_count', len(gaps)), gaps_ns=gaps))
        every.extend(dict(gap_ns=g, event=i) for g in gaps)
    largest = sorted(every, key=lambda g: (-g['gap_ns'], g['event']))[:LARGEST_GAPS]
    ancestry = dict(events=len(recurrence_rows), count=len(every), per_event=per_event, largest=largest,
                    smallest_ns=min((g['gap_ns'] for g in every), default=None), largest_ns=max((g['gap_ns'] for g in every), default=None))
    known = {r.get('group_index'): r.get('clocks.first_lawful_availability_ns') for r in _members(derive, 'clock_event_known_by')}
    avail = {r.get('group_index'): r.get('clocks.first_lawful_availability_ns') for r in _members(derive, 'clock_feature_availability')}
    evaluation = _members(derive, 'clock_model_evaluation')
    decided = {r.get('group_index'): r.get('clocks.decision_ts_recv_ns') for r in evaluation}
    basis = Counter(str(r.get('decision_basis')) for r in evaluation)
    ordered, violations = 0, []
    groups = sorted(set(known) | set(avail) | set(decided), key=lambda g: (g is None, g))
    for g in groups:
        k, a, e = known.get(g), avail.get(g), decided.get(g)
        if None not in (k, a, e) and k <= a <= e:
            ordered += 1
        else:
            violations.append(dict(group_index=g, known_by_ns=k, availability_ns=a, evaluation_ns=e))
    clocks = dict(groups=len(groups), ordered=ordered, violations=violations, rule=CLOCK_RULE, decision_basis=dict(sorted(basis.items())))
    geometry = _members(derive, 'derived_d_family_geometry')
    family_ids = Counter(str(r.get('structure.candidate_family_id')) for r in geometry if r.get('structure.candidate_family_id') is not None)
    sides = Counter(str(r.get('structure.side_string')) for r in geometry if r.get('structure.side_string') is not None)
    legacy = _layer_file(derive, 'legacy_structure_observables') or {}
    actions = Counter(str(g.get('action_string')) for g in (legacy.get('groups') or []) if g.get('action_string') is not None)
    families = dict(distinct_family_ids=len(family_ids), family_id_counts=dict(sorted(family_ids.items())), side_strings=dict(sorted(sides.items())),
                    action_strings=[dict(action_string=k, count=v) for k, v in sorted(actions.items(), key=lambda kv: (-kv[1], kv[0]))])
    fed = bedrock.get('sections_fed') or {}
    span, warmup, minimum = bedrock.get('span_seconds'), bedrock.get('candidate_warmup_seconds'), bedrock.get('candidate_min_observations')
    candidates, episodes = fed.get('candidate_unit_events', 0), fed.get('4.10_4.11_4.12_episode_rows', 0)
    if candidates:
        verdict = f'the candidate lane opened on this cycle\'s rows: {candidates} candidate events, {episodes} episode rows over {span:.1f} s'
    else:
        verdict = (f'the candidate lane cannot open on this cycle\'s rows: {span:.1f} s of rows against a {warmup} s warmup and {minimum} observations; '
                   'the dipole state and the pre-birth cases have no rows here')
    lane = dict(span_seconds=span, warmup_seconds=warmup, min_observations=minimum, candidate_unit_events=candidates, episode_rows=episodes, verdict=verdict)
    frozen = []
    manifest_path = brain / FROZEN_DIR / 'MANIFEST.json'
    entries = _load(manifest_path).get('entries', []) if manifest_path.is_file() else []
    for layer in FROZEN_LAYERS:
        found = [e for e in entries if e.get('include') and layer in (e.get('layers') or [])]
        if not found:
            raise ValueError(f'no included frozen learned-structure file for {layer} in the brain\'s frozen entry ({manifest_path})')
        for e in found:
            path = brain / FROZEN_DIR / e['name']
            data = path.read_bytes() if path.is_file() else None
            if data is None or sha256_bytes(data) != e.get('sha256'):
                raise ValueError(f'the frozen file {e["name"]} for {layer} is absent or differs from its manifest digest')
            frozen.append(dict(layer=layer, name=e['name'], source=e.get('source'), bytes=len(data), sha256=e['sha256'],
                               text=data.decode('utf-8', errors='replace')))
    return dict(schema=FACTS_SCHEMA, layers=layers, bedrock=dict(layers=names, derived=bedrock.get('derived'), could_not=bedrock.get('could_not'),
                                                                   groups=bedrock.get('groups'), records=bedrock.get('records')),
                lineage=lineage, ancestry_gaps=ancestry, clocks=clocks, families=families, candidate_lane=lane, frozen=frozen)


def facts_text(f):
    """The facts as the BOSS reads them: deterministic Markdown, every number exact, the frozen files whole."""
    lines = ['# FACTS (computed by the session code from this cycle\'s own files; every number here is exact)', '',
             f'## The bedrock layers ({f["bedrock"]["derived"]} derived, {f["bedrock"]["could_not"]} could_not; {f["bedrock"]["groups"]} F_LAST groups on {f["bedrock"]["records"]} INPUT records)']
    for name, v in f['layers'].items():
        lines.append(f'- {name}: {v["status"]}, {v["count"]} rows' + (f' ({v["reason"]})' if v.get('reason') else ''))
    L = f['lineage']
    lines += ['', f'## D-depth from the lineage rows (4.13): {L["nodes"]} nodes; {L["closed"]} closed, {L["open"]} open or censored',
              '- depth histogram (depth: nodes): ' + ', '.join(f'D{k}: {v}' for k, v in L['depth_histogram'].items()),
              '- status counts: ' + ', '.join(f'{k}: {v}' for k, v in L['status_counts'].items())]
    A = f['ancestry_gaps']
    lines += ['', f'## Ancestry gaps from the recurrence rows (4.14): {A["count"]} gaps over {A["events"]} events (listed per event; the largest named; no average)']
    for e in A['per_event']:
        lines.append(f'- event {e["event"]}: {e["gap_count"]} gaps: ' + ', '.join(str(g) for g in e['gaps_ns']) + ' ns')
    lines.append('- the largest gaps: ' + ', '.join(f'{g["gap_ns"]} ns (event {g["event"]})' for g in A['largest']) if A['largest'] else '- no gaps')
    C = f['clocks']
    lines += ['', f'## The causal clocks per group: rule {C["rule"]}; {C["ordered"]} of {C["groups"]} groups ordered; decision basis: '
              + ', '.join(f'{k}: {v}' for k, v in C['decision_basis'].items())]
    for v in C['violations']:
        lines.append(f'- violation at group {v["group_index"]}: known_by {v["known_by_ns"]}, availability {v["availability_ns"]}, evaluation {v["evaluation_ns"]}')
    F = f['families']
    lines += ['', f'## Families: {F["distinct_family_ids"]} distinct candidate_family_id values; counts: '
              + ', '.join(f'{k}: {v}' for k, v in F['family_id_counts'].items()) + '; side strings: ' + ', '.join(f'{k}: {v}' for k, v in F['side_strings'].items()),
              '- action strings (legacy structure observables): ' + ', '.join(f'{a["action_string"]}: {a["count"]}' for a in F['action_strings'])]
    T = f['candidate_lane']
    lines += ['', f'## The candidate lane: rows span {T["span_seconds"]} s; warmup {T["warmup_seconds"]} s; minimum {T["min_observations"]} observations; '
              f'{T["candidate_unit_events"]} candidate events; {T["episode_rows"]} episode rows', f'- verdict: {T["verdict"]}']
    for fr in f['frozen']:
        lines += ['', f'## Frozen learned structure for {fr["layer"]}: {fr["source"]} ({fr["bytes"]} bytes, sha256 {fr["sha256"]}), whole', '', fr['text'].rstrip('\n')]
    return '\n'.join(lines) + '\n'


def prompt(text, *, cycle, request_id):
    return (f'You are Frankie, the BOSS, in cycle {cycle} of the 20211003 two-cycle run (request {request_id}). Beside the Dipole '
            'classroom you teach back EXHAUSTION and D from your own bedrock derivation of this cycle and from the frozen learned '
            'structure that defined them. Read the FACTS below; they are computed by code from your own files and are exact. '
            'Answer with ONE JSON object and nothing else: {"exhaustion": {"what_it_is", "how_this_cycle_shows_it", '
            '"what_this_cycle_cannot_show", "relation_to_dipole_state"}, "d_depth": {the same four}, "families": {the same four}, '
            '"prebirth": {the same four}, "clocks": {the same four}, "questions": [strings]}. Every field is a non-empty string. '
            'RULE: every number you cite must appear in the facts below, exactly as written there (a number not in the facts makes the '
            'whole answer unusable); do not invent a count, a rate or a percentage; say what the rows cannot show rather than guessing.\n\n'
            + text)


def numbers_in(text):
    return set(_NUMBER.findall(_THOUSANDS.sub('', text or '')))


def missing_numbers(answer_text, facts_text_):
    allowed = numbers_in(facts_text_)
    seen, out = set(), []
    for n in _NUMBER.findall(_THOUSANDS.sub('', answer_text or '')):
        if n not in allowed and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _object(text):
    try:
        value = json.loads(text)
    except Exception:
        start, end = text.find('{'), text.rfind('}')
        if start < 0 or end <= start:
            raise ValueError('the answer is not a JSON object')
        value = json.loads(text[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError('the answer is not a JSON object')
    return value


def parse_answer(body, facts_text_, error=ValueError):
    """The answer, or `error` naming what is missing: a topic, a field, or a number that is not in the facts."""
    try:
        answer = _object(body)
    except (ValueError, TypeError) as err:
        raise error(f'answer unusable: {err}')
    out = {}
    cited = []
    for topic in TOPICS:
        block = answer.get(topic)
        if not isinstance(block, dict):
            raise error(f'answer unusable: topic {topic} missing')
        out[topic] = {}
        for field in FIELDS:
            value = block.get(field)
            if not isinstance(value, str) or not value.strip():
                raise error(f'answer unusable: {topic}.{field} missing or empty')
            out[topic][field] = value
            cited.append(value)
    questions = answer.get('questions', [])
    if not isinstance(questions, list) or not all(isinstance(q, str) for q in questions):
        raise error('answer unusable: questions must be a list of strings')
    out['questions'] = questions
    cited.extend(questions)
    foreign = missing_numbers('\n'.join(cited), facts_text_)
    if foreign:
        raise error('answer unusable: numbers not in the facts: ' + ', '.join(foreign))
    return out


def markdown(record):
    a = record['answer']
    lines = [f'# The exhaustion and D teach-back (cycle {record["cycle"]}; the BOSS on its own bedrock facts; numbers checked against the facts by code)', '',
             f'Facts sha256 {record["facts_sha256"]}; call {record["call"].get("attempt")} on the {record["call"].get("lane")} lane; '
             f'frozen files: ' + ', '.join(f'{f["source"]} ({f["layer"]})' for f in record.get('frozen', [])), '']
    for topic in TOPICS:
        lines += [f'## {topic}', '']
        for field in FIELDS:
            lines += [f'**{field}**: {a[topic][field]}', '']
    lines += ['## questions', ''] + [f'- {q}' for q in a.get('questions', [])] + ['', '## The facts the answer was checked against', '', record['facts_text'].rstrip('\n'), '']
    return '\n'.join(lines)
