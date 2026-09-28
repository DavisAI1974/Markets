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

import sys

SCHEMA = 'FRANKIE_BOX_TEACHBACK_V1'          # the retired Granite teach-back (records filed before 2026-09-28 read as they were)
CODE_SCHEMA = 'FRANKIE_BOX_TEACH_PRIMING_V1'   # the code-only priming (Greg, 2026-09-28: Granite is a reasoning boost only)
FACTS_SCHEMA = 'FRANKIE_BOX_TEACH_FACTS_V1'
TOPICS = ('exhaustion', 'd_depth', 'families', 'prebirth', 'clocks')
FIELDS = ('what_it_is', 'how_this_cycle_shows_it', 'what_this_cycle_cannot_show', 'relation_to_dipole_state')
FROZEN_LAYERS = ('learned_d_structures_and_families', 'learned_dipoles_and_geometry',
                 'learned_chains_extensions_reappearances_ancestry', 'predecessor_ancestry_unresolved_chain_state')
FROZEN_DIR = 'frozen-learned-structure'
CLOCK_RULE = 'event_known_by <= feature_availability <= model_evaluation'
# no caps (Greg, 2026-09-28: the caps on groups, families and D's count were removed because we expect to learn things
# we have not before): every gap is named in size order, every clock violation is printed, and Frankie's questions are
# kept whatever their number or length
_NUMBER = re.compile(r'(?:(?<![\d.])-)?\d+(?:\.\d+)?')   # a minus stays with its number; a hyphen after a digit is a range or a date
_THOUSANDS = re.compile(r'(?<=\d),(?=\d{3}(?!\d))')
_HEX = re.compile(r'\b(?=[0-9]*[a-f])[0-9a-f]{8,}\b')    # sha256 values and their prefixes (8+ hex chars with a letter among them) never license a number; a 19-digit ns clock is a NUMBER


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _load(path):
    return json.loads(Path(path).read_bytes())


def _stream_layer(derive, name, wanted):
    """Read one layer file's top-level object ONCE, streamed (Monday's layers are gzip-json and many GB; the member
    ledger they project is 537 GB): wanted maps a key to a row consumer (each array element is passed to it, never
    collected) or to None (the value is decoded and returned). Stops as soon as every wanted key is read; other keys are
    skipped without materializing them. None when the layer file is absent. Same values json.loads would have given."""
    entry = (derive.get('layers') or {}).get(name)
    if not entry or not entry.get('path') or not Path(entry['path']).is_file():
        return None
    box = str(Path(__file__).resolve().parent)
    if box not in sys.path:
        sys.path.insert(0, box)
    import gzip
    from frankie_box_digest_sources import _JSON
    if entry.get('encoding') not in (None, 'gzip-json'):
        raise ValueError(f'unknown layer encoding for {name}: {entry.get("encoding")!r}')
    opener = gzip.open if entry.get('encoding') == 'gzip-json' else open
    found, remaining = {}, set(wanted)
    with opener(entry['path'], mode='rt', encoding='utf-8') as handle:
        parser = _JSON(handle)
        parser.expect('{')
        while remaining and parser.peek() != '}':
            key = parser.value()
            parser.expect(':')
            if key in remaining:
                consume = wanted[key]
                if consume is None:
                    found[key] = parser.value()
                elif parser.peek() == '[':
                    for row in parser.array():
                        consume(row)
                else:
                    for row in (parser.value() or []):
                        consume(row)
                remaining.discard(key)
            elif parser.peek() == '[':
                for _ in parser.array():     # an unwanted row array: C-decoded one element at a time, never collected
                    pass
            else:
                parser.skip()
            if remaining and parser.peek() != '}':
                parser.expect(',')
    return found


def lineage_vocabulary(producers):
    """The pinned producers' own lineage status names (native_lineage), never restated here."""
    producers = Path(producers).resolve()
    if str(producers) not in sys.path:
        sys.path.append(str(producers))
    from research.kalshi.frankie_raw_mbo_benchmark import native_lineage as L
    if not Path(L.__file__).resolve().is_relative_to(producers):
        raise ValueError(f'native_lineage loaded from {L.__file__}, not the pinned checkout {producers}')
    return dict(terminated=L.TERMINATED, censored=sorted(L.CENSORED_STATUSES), open=L.OPEN, statuses=sorted(L.LINEAGE_STATUSES))


def _sections_rows(derive, bedrock_layers, sections):
    """{section: rows} for each lifecycle section, each from the first derived bedrock layer file that declares it and
    carries rows for it (identical copies), all sections gathered in one streamed pass per layer. lifecycle_rows sort
    before lifecycle_sections in the projected layers, so matching rows are kept while streaming and kept only when the
    file declares the section."""
    result, pending = {}, list(sections)
    for name in bedrock_layers:
        if not pending:
            break
        rows = {section: [] for section in pending}
        def keep(row, rows=rows):
            bucket = rows.get(row.get('emitting_section'))
            if bucket is not None:
                bucket.append(row)
        found = _stream_layer(derive, name, {'lifecycle_rows': keep, 'lifecycle_sections': None})
        if found is None:
            continue
        declared = found.get('lifecycle_sections') or []
        for section in list(pending):
            if section in declared and rows[section]:
                result[section] = rows[section]
                pending.remove(section)
    return {section: result.get(section, []) for section in sections}


def _each_member(derive, name, consume):
    """Pass each member row of one layer to consume, in file order; nothing when the layer file is absent."""
    _stream_layer(derive, name, {'member_rows': consume})


# ---- the six layer streams, each in its own process (Greg, 2026-09-28: nothing on one CPU that need not be) -------
# facts() used to stream the lifecycle sections, the three clock layers, the family geometry and the legacy structure
# observables one after another on the main thread: six passes over many-GB gzip-json files, Python-decoded per row.
# The streams are independent, so each runs in its own process and returns only what facts() keeps from it; the parent
# combines them exactly as before. Same values, same order of use.
def _job_sections(derive, names):
    return _sections_rows(derive, names, ('lineage', 'recurrence'))


def _job_clock(derive, name, field):
    values = {}
    _each_member(derive, name, lambda r: values.__setitem__(r.get('group_index'), r.get(field)))
    return values


def _job_evaluated(derive):
    decided, basis = {}, Counter()
    def evaluated(r):
        decided[r.get('group_index')] = r.get('clocks.decision_ts_recv_ns')
        basis[str(r.get('decision_basis'))] += 1
    _each_member(derive, 'clock_model_evaluation', evaluated)
    return decided, basis


def _job_families(derive):
    family_ids, sides = Counter(), Counter()
    def described(r):
        if r.get('structure.candidate_family_id') is not None:
            family_ids[str(r.get('structure.candidate_family_id'))] += 1
        if r.get('structure.side_string') is not None:
            sides[str(r.get('structure.side_string'))] += 1
    _each_member(derive, 'derived_d_family_geometry', described)
    return family_ids, sides


def _job_actions(derive):
    actions = Counter()
    def acted(g):
        if g.get('action_string') is not None:
            actions[str(g.get('action_string'))] += 1
    _stream_layer(derive, 'legacy_structure_observables', {'groups': acted})
    return actions


def _streams(derive, names):
    """The six streams at once, one spawn process each; results in the order facts() uses them. The functions come
    from this module imported by name (the session loads it by path without registering it, so its own function
    objects cannot be pickled)."""
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing
    box = str(Path(__file__).resolve().parent)
    if box not in sys.path:
        sys.path.insert(0, box)
    import frankie_box_teach as T
    jobs = dict(sections=(T._job_sections, derive, names),
                known=(T._job_clock, derive, 'clock_event_known_by', 'clocks.first_lawful_availability_ns'),
                avail=(T._job_clock, derive, 'clock_feature_availability', 'clocks.first_lawful_availability_ns'),
                evaluated=(T._job_evaluated, derive),
                families=(T._job_families, derive),
                actions=(T._job_actions, derive))
    with ProcessPoolExecutor(max_workers=len(jobs), mp_context=multiprocessing.get_context('spawn')) as pool:
        futures = {key: pool.submit(*job) for key, job in jobs.items()}
        return {key: future.result() for key, future in futures.items()}


def facts(work, brain, producers):
    """The pre-message facts, exact and small, from work/derive.json, the bedrock layer files (the pinned producers' own
    row shapes: recurrence gaps are mappings with gap_ns/from_node/to_node/recv_ns; lineage statuses are
    native_lineage's TERMINATED / CENSORED_* / OPEN), the legacy structure observables and the brain's frozen entry.
    Refuses without a bedrock or without an included frozen file for each of the four layers that define D and
    exhaustion. A clock layer that was not derived is reported as unknown, never as an order violation."""
    work, brain = Path(work), Path(brain)
    derive = _load(work / 'derive.json')
    bedrock = derive.get('bedrock')
    if not bedrock:
        raise ValueError('derive.json carries no bedrock; the teach-back needs the bedrock derivation')
    vocabulary = lineage_vocabulary(producers)
    names = list(bedrock.get('layers') or [])
    layers = {}
    for name in names:
        entry = (derive.get('layers') or {}).get(name) or {}
        layers[name] = dict(status=entry.get('status'), count=entry.get('count', 0), reason=entry.get('reason'))
    streamed = _streams(derive, names)
    section_rows = streamed['sections']
    lineage_rows = section_rows['lineage']
    depth = Counter(int(r.get('depth')) for r in lineage_rows if r.get('depth') is not None)
    status = Counter(str(r.get('status')) for r in lineage_rows)
    unknown_status = sorted(k for k in status if k not in vocabulary['statuses'])
    if unknown_status:
        raise ValueError(f'lineage rows carry a status outside the pinned vocabulary {vocabulary["statuses"]}: {unknown_status}')
    lineage = dict(nodes=len(lineage_rows), depth_histogram={str(k): depth[k] for k in sorted(depth)}, status_counts=dict(sorted(status.items())),
                   terminated=status.get(vocabulary['terminated'], 0), censored=sum(status.get(s, 0) for s in vocabulary['censored']),
                   open=status.get(vocabulary['open'], 0), vocabulary=vocabulary)
    recurrence_rows = section_rows['recurrence']
    per_event, every = [], []
    for i, row in enumerate(recurrence_rows):
        gaps = []
        for g in (row.get('gaps') or []):
            if not isinstance(g, dict) or 'gap_ns' not in g:
                raise ValueError('a recurrence gap is not the producers\' mapping (gap_ns, from_node, to_node, recv_ns)')
            gaps.append(dict(gap_ns=int(g['gap_ns']), from_node=g.get('from_node'), to_node=g.get('to_node'), recv_ns=g.get('recv_ns'),
                             continuity_segment=g.get('continuity_segment')))
        per_event.append(dict(event=i, gap_count=row.get('gap_count', len(gaps)), gaps=gaps))
        every.extend(dict(event=i, **g) for g in gaps)
    largest = sorted(every, key=lambda g: (-g['gap_ns'], g['event'], g['recv_ns'] or 0))
    ancestry = dict(events=len(recurrence_rows), count=len(every), per_event=per_event, largest=largest,
                    smallest_ns=min((g['gap_ns'] for g in every), default=None), largest_ns=max((g['gap_ns'] for g in every), default=None))
    derived_clocks = {name: layers.get(name, {}).get('status') == 'derived'
                      for name in ('clock_event_known_by', 'clock_feature_availability', 'clock_model_evaluation')}
    known, avail = streamed['known'], streamed['avail']
    decided, basis = streamed['evaluated']
    ordered, unknown, violations = 0, 0, []
    groups = sorted(set(known) | set(avail) | set(decided), key=lambda g: (g is None, g))
    for g in groups:
        k, a, e = known.get(g), avail.get(g), decided.get(g)
        if None in (k, a, e):
            unknown += 1                      # a clock not derived for this group is unknown, not a violation
        elif k <= a <= e:
            ordered += 1
        else:
            violations.append(dict(group_index=g, known_by_ns=k, availability_ns=a, evaluation_ns=e))
    clocks = dict(groups=len(groups), ordered=ordered, unknown=unknown, violations=violations, derived_clocks=derived_clocks,
                  rule=CLOCK_RULE, decision_basis=dict(sorted(basis.items())))
    family_ids, sides = streamed['families']
    actions = streamed['actions']
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
    traversal = dict(verdict=bedrock.get('verdict'), failed_gates=list(bedrock.get('failed_gates') or []),
                     note='the pinned run\'s own acceptance verdict over this slice (gates in native_calculation_runner); the layers are filed by their rows either way')
    frozen = []
    manifest_path = brain / FROZEN_DIR / 'MANIFEST.json'
    entries = _load(manifest_path).get('entries', []) if manifest_path.is_file() else []
    for layer in FROZEN_LAYERS:
        found = [e for e in entries if e.get('include') and layer in (e.get('layers') or [])]
        if not found:
            raise ValueError(f'no included frozen learned-structure file for {layer} in the brain\'s frozen entry ({manifest_path})')
        for e in found:
            name = str(e.get('name') or '')
            path = (brain / FROZEN_DIR / name)
            if not name or '/' in name or '\\' in name or name in ('.', '..') or path.resolve().parent != (brain / FROZEN_DIR).resolve():
                raise ValueError(f'the frozen entry names a file outside {FROZEN_DIR}: {name!r}')
            data = path.read_bytes() if path.is_file() else None
            if data is None or sha256_bytes(data) != e.get('sha256'):
                raise ValueError(f'the frozen file {e["name"]} for {layer} is absent or differs from its manifest digest')
            frozen.append(dict(layer=layer, name=e['name'], source=e.get('source'), bytes=len(data), sha256=e['sha256'],
                               text=data.decode('utf-8', errors='replace')))
    return dict(schema=FACTS_SCHEMA, layers=layers, bedrock=dict(layers=names, derived=bedrock.get('derived'), could_not=bedrock.get('could_not'),
                                                                   groups=bedrock.get('groups'), records=bedrock.get('records')),
                traversal=traversal, lineage=lineage, ancestry_gaps=ancestry, clocks=clocks, families=families, candidate_lane=lane, frozen=frozen)


def facts_text(f):
    """The facts as the BOSS reads them: deterministic Markdown, every number exact, the frozen files whole."""
    lines = ['# FACTS (computed by the session code from this cycle\'s own files; every number here is exact)', '',
             f'## The bedrock layers ({f["bedrock"]["derived"]} derived, {f["bedrock"]["could_not"]} could_not; {f["bedrock"]["groups"]} F_LAST groups on {f["bedrock"]["records"]} INPUT records)']
    for name, v in f['layers'].items():
        lines.append(f'- {name}: {v["status"]}, {v["count"]} rows' + (f' ({v["reason"]})' if v.get('reason') else ''))
    V = f.get('traversal') or {}
    lines += ['', f'## The traversal\'s own verdict over this slice: {V.get("verdict")}' + (f'; failed gates: {", ".join(V["failed_gates"])}' if V.get('failed_gates') else '; no failed gate')]
    L = f['lineage']
    lines += ['', f'## D-depth from the lineage rows (4.13): {L["nodes"]} nodes; {L["terminated"]} terminated, {L["censored"]} censored, {L["open"]} open '
              f'(the producers\' own statuses: {", ".join(L["vocabulary"]["statuses"])})',
              '- depth histogram (depth: nodes): ' + ', '.join(f'D{k}: {v}' for k, v in L['depth_histogram'].items()),
              '- status counts: ' + ', '.join(f'{k}: {v}' for k, v in L['status_counts'].items())]
    A = f['ancestry_gaps']
    lines += ['', f'## Ancestry gaps from the recurrence rows (4.14): {A["count"]} gaps over {A["events"]} events (listed per event; the largest named; no average)']
    for e in A['per_event']:
        lines.append(f'- event {e["event"]}: {e["gap_count"]} gaps: ' + ', '.join(f'{g["gap_ns"]} ns ({g["from_node"]} -> {g["to_node"]} at {g["recv_ns"]})' for g in e['gaps']))
    lines.append('- the largest gaps: ' + ', '.join(f'{g["gap_ns"]} ns (event {g["event"]}, {g["from_node"]} -> {g["to_node"]})' for g in A['largest']) if A['largest'] else '- no gaps')
    C = f['clocks']
    lines += ['', f'## The causal clocks per group: rule {C["rule"]}; {C["ordered"]} of {C["groups"]} groups ordered, {C["unknown"]} unknown (a clock layer '
              'not derived), ' + f'{len(C["violations"])} violations; derived clock layers: '
              + ', '.join(f'{k}: {"yes" if v else "no"}' for k, v in C['derived_clocks'].items()) + '; decision basis: '
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


def _number_tokens(text):
    """The number literals of a text, thousands separators removed and hex digests (8+ hex chars with at least one letter)
    removed first: a digit run inside a sha256 never licenses a number, and a pure-decimal run (a ns clock, a gap) is never
    mistaken for one. A leading minus stays with its number; a hyphen after a digit (0-2, 2026-09-21) is not a minus."""
    cleaned = _HEX.sub(' ', _THOUSANDS.sub('', text or ''))
    return _NUMBER.findall(cleaned)


def _value(token):
    from decimal import Decimal
    return Decimal(token)


def numbers_in(text):
    return {_value(n) for n in _number_tokens(text)}


def missing_numbers(answer_text, facts_text_):
    """The answer's numbers that are not in the facts, compared as VALUES (13 and 13.0 agree; -5 and 5 do not), once each."""
    allowed = numbers_in(facts_text_)
    seen, out = set(), []
    for n in _number_tokens(answer_text):
        v = _value(n)
        if v not in allowed and v not in seen:
            seen.add(v)
            out.append(n)
    return out


def _object(text):
    try:
        value = json.loads(text)
    except RecursionError:
        raise ValueError('the answer nests too deeply')
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


def _line(value):
    """Model text as ONE Markdown line: no line breaks (a heading or list marker inside a value cannot forge structure)."""
    return ' '.join(str(value).split())


def markdown(record):
    a = record['answer']
    lines = [f'# The exhaustion and D teach-back (cycle {record["cycle"]}; the BOSS on its own bedrock facts; numbers checked against the facts by code)', '',
             f'Facts sha256 {record["facts_sha256"]}; call {record["call"].get("attempt")} on the {record["call"].get("lane")} lane; '
             f'frozen files: ' + ', '.join(f'{f["source"]} ({f["layer"]})' for f in record.get('frozen', [])), '']
    for topic in TOPICS:
        lines += [f'## {topic}', '']
        for field in FIELDS:
            lines += [f'**{field}**: {_line(a[topic][field])}', '']
    lines += ['## questions', ''] + [f'- {_line(q)}' for q in a.get('questions', [])] + ['', '## The facts the answer was checked against', '', record['facts_text'].rstrip('\n'), '']
    return '\n'.join(lines)


def facts_markdown(record):
    """The code-only priming as the brain carries it: the facts text and the frozen files, whole (no model answer)."""
    return (f'# The exhaustion and D priming (cycle {record["cycle"]}; computed by code from this cycle\'s bedrock files; no model call)\n\n'
            f'Facts sha256 {record["facts_sha256"]}; frozen files: ' + ', '.join(f'{f["source"]} ({f["layer"]})' for f in record.get('frozen', []))
            + '\n\n' + record['facts_text'].rstrip('\n') + '\n')
