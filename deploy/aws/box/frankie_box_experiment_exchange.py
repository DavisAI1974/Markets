"""The three-way exchange for ONE classroom-arm discovery day: the BOSS teacher, the scientific teacher and Frankie.

Greg, 2026-09-29 (go for the code-only exchange). Spec: research/kalshi/frankie_boss/SPEC-scientific-teacher.md step 5
("The BOSS teacher answers the scientific teacher's results within its own role (its targets, masks, controls), and the
scientific teacher answers back; each turn builds on the other's. A new discovery from the exchange is filed as the
teachers' own finding, scoped, with its days named. Frankie is taught from the exchange.") and
knowledge/CLASSROOM_RULES_V1.json (R01-R17; R17: every seat's output is code, calculations or a measured test).

The old model-voiced discussion (research/kalshi/frankie_boss/dipole_teacher_discussion.py, dipole_scientific_review.py,
deploy/aws/box/frankie_box_teacher_discussion.py) is REUSED, not edited: its roles (boss_teacher_scientific,
scientific_teacher, principal), its positions (AGREE, DISAGREE, UNRESOLVED), its dispositions, its turn schemas and its
validators (dipole_teacher_discussion.parse_teacher for both teacher turns, parse_frankie for Frankie's reply, each bound
to the exact prior turn by responds_to_hash). Only what produces a turn changes: code over measurements, never a prompt.

Reads, per scientific-teacher result on a claim (the lessons of the day's batch: FRANKIE_LESSONS_V1, JEV_LESSONS_V1,
HISTORICAL_LESSONS_V1 written by frankie_box_scientific_teacher.py), one item, three turns:
  1 the BOSS teacher (code; its own Dipole rows of the day, host-dipole-classroom-source.c15.json, JournalTeacherR3):
    for each pair of the claim that is a pair of its 19 components, its own measurement is named (the step counts over
    consecutive both-PRESENT cursors, the first-to-last relation, the Pearson coefficient with its overlap count, per pair
    and per day, never pooled: R05), agreeing with or qualifying the claim; its masks (the non-PRESENT state pairings,
    ABLATED / INVALID cursors) and its control (the pair on its own cursor axis beside the search's F_LAST axis) are
    proposed. A series that is not one of its components has no teacher measurement: said so, never filled in. It never
    sees Frankie's decision process (R09: the claim reaches it through the scientific teacher's reader, which reads only
    his novel findings) or any graded outcome (R10).
  2 the scientific teacher (code; the search's counts as the lessons carry them): answers the BOSS teacher's turn with
    the search rows of the day for the same pair (counts, lag, the chance check), the counts per discovery day tested
    (held / shown_otherwise / unresolved / counts_only, per day, never pooled), the day's challenges ("the data is showing
    this instead", R07), every test the BOSS teacher proposed listed as proposed and untested (R13), the lessons'
    untested and cannot-test-yet lists. A combination both teachers measured the same way on the day (the teacher's step
    counts and a search row beyond chance point the same way) is filed as THE TEACHERS' OWN FINDING: a HYPOTHESIS, scoped
    (day, cell, lag, transforms, the two axes), with its day named; the counts are the finding, the disposition word is
    orientation only (R06, R14).
  3 Frankie (his code, frankie_box_classroom_code.exchange_reply): per item resolved in his own words (R08) or kept as a
    hypothesis (R06), remaining disagreement stated explicitly, no future-outcome claim (R02). Jev's claims are labelled
    claims (R11); Jev takes no seat, and Frankie gives no reply to the raw claims in this exchange. The blind wall keeps
    Jev's untested claims out of Frankie's reply/view. After Jev's own claims are sealed and the scientific teacher tests
    them, that tested result is filed separately into Frankie's brain as <day>-jev-tested (Greg, 2026-10-06: no knowledge
    handicap after the independent claim is fixed). The teachers' turns on raw Jev claims stay in the full exchange.

Every turn carries its author (R11) and a voice-ready turn list (voice_turns: seat, author, text, and every value the
text cites with the sha256 of the file it came from), the input the later 'voice' stage is given
(knowledge/GRANITE_DISCUSSION_VOICE_ROLE_V1.md; frankie_box_exchange_voice.py holds its validator). No model is called
here.

The BOSS also accounts for every supplied current-day search row's transformed
movement margins and teaches that accounting through the existing learner reply.
These shared counts remain separate from its own measurements and joint findings;
they neither change governed targets nor establish a PRESENT mask or new validity.

Writes, under the orchestrator run (/opt/frankie-box/work/experiment/<run>/exchange/<day>/):
  exchange.json          FRANKIE_EXPERIMENT_EXCHANGE_V1, view full (every item, Jev's included, labelled)
  exchange-frankie.json  the same schema, view frankie (Jev's items and the findings from them withheld, counted)
  receipt.json           FRANKIE_EXPERIMENT_EXCHANGE_RECEIPT_V1 (sources, sha256s, counts, the brain entry)
and files Frankie's view into his brain as <brain>/<day>-exchange/ (frankie_box_brain.write_exchange_entry). Both
exchange files are deterministic (no clock inside), so a restart that stopped after writing them reproduces the same bytes
and goes on; other bytes decline (duplicate data, R16). Counts, never averages; nothing dropped: whatever is not measured
or not readable is listed with its reason (R04).
"""
import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

BOX = Path(__file__).resolve().parent
ROOT = BOX.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BOX))
SCHEMA = 'FRANKIE_EXPERIMENT_EXCHANGE_V1'
RECEIPT_SCHEMA = 'FRANKIE_EXPERIMENT_EXCHANGE_RECEIPT_V1'
FINDING_SCHEMA = 'FRANKIE_TEACHERS_FINDING_V1'
LESSONS = {'FRANKIE_LESSONS_V1': 'frankie', 'JEV_LESSONS_V1': 'jev', 'HISTORICAL_LESSONS_V1': 'historical',
           'SEARCH_CANDIDATE_LESSONS_V1': 'search'}
AUTHOR_LABEL = {
    'frankie': "Frankie's claim (his novel finding; a claim, never truth: R11)",
    'jev': "Jev's claim (the blind outside student; a labelled claim, R11; he takes no seat)",
    'historical': "a historical Dipole claim (the committed catalog; a labelled claim, R11)",
    'search': "the search's candidate (source-bound counts, a claim, never truth: R11)",
}
BOSS_AUTHOR = "the BOSS teacher's code (its own Dipole rows and accounting of shared search results; no model)"
SCIENCE_AUTHOR = "the scientific teacher's code (the experiment's search counts; no model)"
HISTORICAL_REWORK = ('Reproduce the original source-bound research calculation; inspect assumptions and failure '
                    'causes; investigate a repair or reformulation. Old rejection labels do not close this '
                    'research; record missing inputs and unfinished work.')
WHOLE_DAY = 'whole-day'
JEV_WALL = ("Jev's raw claims stay out of Frankie's replies and exchange view while Jev is blind; after Jev's own claim "
            "is sealed and scientifically tested, the tested result may enter Frankie's brain separately as jev-tested; "
            "the teachers' turns on raw Jev claims stay in the full exchange of the receipt")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def finite(value):
    """The value with every non-finite float written as text ('NaN', 'Infinity', '-Infinity'), so the canonical digest of
    the discussion schemas (allow_nan=False) can bind it; nothing else changes."""
    if isinstance(value, float) and not math.isfinite(value):
        return 'NaN' if value != value else ('Infinity' if value > 0 else '-Infinity')
    if isinstance(value, dict):
        return {k: finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(v) for v in value]
    return value


def num(value):
    """A value as the text says it: an int as digits, a float by repr (exactly as recorded), anything else by str."""
    if isinstance(value, bool) or value is None:
        return str(value).lower() if isinstance(value, bool) else 'none'
    if isinstance(value, float):
        return repr(value)
    return str(value)


class Said:
    """A seat's words and the values they cite: every value put into the text through v() is listed in cites with the
    sha256 of the file it came from, so the text and its cites agree by construction (the voice charter's input)."""

    def __init__(self):
        self.cites = []

    def v(self, value, sha, what):
        text = num(value)
        cite = dict(value=text, source_sha256=sha, what=what)
        if cite not in self.cites:
            self.cites.append(cite)
        return text


# ------------------------------------------------------------------------------------------------------------- inputs
def load_lessons(paths, day):
    """[(doc, source)] for the lessons files that tested the day; listed = the files given that did not, with the reason."""
    docs, listed = [], []
    for path in paths:
        raw = Path(path).read_bytes()
        doc = json.loads(raw)
        author = LESSONS.get(doc.get('schema'))
        if author is None or doc.get('author') != author:
            raise SystemExit('%s is not a supported scientific lesson schema of its author' % path)
        tested = sorted(str(s.get('day')) for s in doc.get('searches') or [])
        if day not in tested:
            listed.append(dict(path=str(path), reason='these lessons did not test %s (days tested: %s)' % (day, tested)))
            continue
        docs.append((doc, dict(path=str(path), sha256=sha256_bytes(raw), bytes=len(raw), author=author,
                               schema=doc['schema'], day=doc.get('day'), stamp=doc.get('stamp'), days_tested=tested,
                               claims_sha256=doc.get('claims_sha256'), claims_source=doc.get('claims_source'),
                               source_id='lessons:%s:%s' % (author, Path(path).name))))
    return docs, listed


def lesson_context(doc):
    """Preserve the whole collection/evidence context once per source lesson.

    The lesson's byte hash binds these declarations. A native reference is not
    a new measurement, and transporting it does not prove a semantic calculation.
    """
    context = {key: doc[key] for key in ('reconsideration', 'completed_native_evidence') if key in doc}
    collection = context.get('reconsideration')
    if collection is not None and (collection.get('schema') != 'FRANKIE_HISTORICAL_RECONSIDERATION_V1'
            or collection.get('claims_file_sha256') != doc.get('claims_sha256')):
        raise ValueError('historical reconsideration differs from its lesson claims binding')
    return context


def context_checks(item, day, src, said):
    """Both seats state the same source-scoped obligations before their turn is hashed."""
    checks, words = [], []
    context = item.get('lesson_context') or {}
    collection = context.get('reconsideration')
    if item['author'] == 'historical':
        if collection is None:
            words.append('This older historical lesson has no collection reconsideration summary; '
                         'its mapped results do not establish collection coverage or completed rework.')
        else:
            words.append('Historical collection: mapped %s claims among %s candidate statements; '
                         'catalog sha256 %s; statuses %s. Counts retain their source categories and are not '
                         'a disjoint coverage percentage. Original-calculation reproduction and repair remain open.' % (
                said.v(collection.get('mapped_claims'), src['sha256'], 'collection mapped claims'),
                said.v(collection.get('candidates'), src['sha256'], 'collection candidate statements'),
                said.v(collection.get('catalog_sha256'), src['sha256'], 'collection catalog sha256'),
                said.v(json.dumps(collection.get('statuses'), sort_keys=True), src['sha256'], 'collection statuses')))
    native = context.get('completed_native_evidence')
    if native is not None:
        reference = (native.get('by_day') or {}).get(day)
        if reference is not None:
            if str(reference.get('day')) != day:
                raise ValueError('completed native reference names a different day')
            words.append('Completed native evidence for this day, as declared by the bound scientific lesson: %s. '
                         'Exact fields and post-stream rows remain completed-day knowledge; averages are labelled '
                         'supplements only. This reference adds no independent measurement and does not establish '
                         'a new semantic calculation or a live search step.' %
                         said.v(json.dumps(reference, sort_keys=True), src['sha256'], 'completed native reference'))
        else:
            words.append('This lesson has no completed-native reference for the current day; '
                         'references for other days remain in their original scope.')
        if native.get('listed'):
            words.append('Completed-native coverage still listed: %s.' %
                         said.v(json.dumps(native['listed'], sort_keys=True), src['sha256'], 'native coverage listed'))
    for text in words:
        checks.append(dict(source_id=src['source_id'], claim='collection and completed-native scope',
                           check=text, result='unresolved'))
    return checks, words


def accumulated_lessons(day, run, paths, brain, input_path, rows_path, rules_witness):
    """Freeze the actual lesson inputs before any seat runs; never expose whole student brain documents to teachers."""
    import frankie_box_lane_state as LS
    import frankie_box_brain as BR
    import frankie_box_scientific_teacher as ST
    import frankie_box_classroom_code as K
    import frankie_box_experiment_search as SEARCH
    from research.kalshi.frankie_boss import dipole_classroom as DC
    from frankie_box_durable import write_json
    from frankie_box_durable import witness
    identity = dict(day=day, run=run,
                    lessons=[dict(path=str(p), **witness(p)) for p in paths], brain=str(brain),
                    teacher_rows=dict(path=str(rows_path), **witness(rows_path)) if rows_path else None,
                    rules=rules_witness, producer_sha256=sha256_bytes(Path(__file__).read_bytes()),
                    reader_sha256={m.__name__: sha256_bytes(Path(m.__file__).read_bytes())
                                   for m in (LS, BR, ST, K, SEARCH, DC)})
    input_path = Path(input_path)
    if input_path.is_file():
        retained = json.loads(input_path.read_bytes())
        if retained.get('identity') != identity:
            raise ValueError('retained exchange learner inputs belong to another source selection or producer')
        return retained
    docs, listed = load_lessons(paths, day)
    selected = LS.learner_knowledge(day, 'exchange', brain=brain)
    school, school_listed = LS.learner_school(day, brain=brain, versions=selected['versions'])
    seen = {src['sha256'] for _, src in docs}

    def take(doc, source, address=()):
        if not isinstance(doc, dict):
            return
        schema = doc.get('schema')
        if schema in LESSONS:
            author = LESSONS[schema]
            if doc.get('author') != author or not isinstance(doc.get('results'), list):
                raise ValueError('accumulated scientific lesson schema/author/results differ')
            if source['sha256'] in seen:
                return
            seen.add(source['sha256'])
            docs.append((doc, dict(path=source['path'], sha256=source['sha256'], author=author, schema=schema,
                day=doc.get('day'), stamp=doc.get('stamp'), days_tested=[s['day'] for s in doc.get('searches') or []],
                claims_sha256=doc.get('claims_sha256'), claims_source=doc.get('claims_source'),
                source_id='accumulated-lessons:' + source['sha256'], accumulated=True,
                container_sha256=source.get('container_sha256', source['sha256']), address=list(address))))
        elif schema == 'FRANKIE_STAGE_KNOWLEDGE_V1':
            for i, member in enumerate(doc.get('sources') or []):
                if member.get('inline') and isinstance(member.get('content'), dict):
                    take(member['content'], dict(path=member['path'], sha256=member['sha256'],
                         container_sha256=source['sha256']), address + ('sources', i, 'content'))
        else:
            listed.append(dict(path=source['path'], sha256=source['sha256'], schema=schema,
                               reason='retained knowledge is not a scientific lesson result consumed by this exchange'))

    for source in selected['documents']:
        take(source['content'], source)
    for row, doc in school:
        # School also contains private student reasoning. Only its scientific-teacher lesson documents cross R09.
        for i, item in enumerate((doc.get('sections', {}).get('scientific_teacher') or {}).get('items') or []):
            content = item.get('content')
            if item.get('inline') and isinstance(content, dict) and content.get('schema') in LESSONS:
                take(content, dict(path=item.get('path') or str(row.get('file')), sha256=item['sha256'],
                     container_sha256=row['sha256']), ('sections', 'scientific_teacher', 'items', i, 'content'))
    claims_by_source = {}
    for doc, source in docs:
        claims, why = claims_of(doc)
        claims_by_source[source['source_id']] = dict(claims=claims, listed=why)
    retained = dict(schema='FRANKIE_EXCHANGE_KNOWLEDGE_INPUTS_V1', identity=identity,
                    documents=docs, listed=listed, versions=selected['versions'],
                    claims_by_source=claims_by_source,
                    selection_listed=selected['listed'], school_listed=school_listed,
                    rule='completed learning accumulates by availability; original days/scopes remain explicit; '
                         'only scientific lesson results reach these teacher seats, never student decision traces')
    write_json(input_path, retained)
    return retained


def claims_of(doc):
    """{claim_id: claim} from the bound legal inputs, or legacy scientific teacher readers (only statement, series,
    direction, lag, cells and transforms; for Frankie only his novel findings: R09), bound to the lessons' claims_sha256;
    ({}, why) when the source is not readable or has changed."""
    import frankie_box_scientific_teacher as ST
    source, author = doc.get('claims_source'), doc.get('author')
    if 'claim_inputs' in doc:
        claims = doc['claim_inputs']
        if sha256_bytes(json.dumps(claims, sort_keys=True).encode()) != doc.get('claim_inputs_sha256') or \
                claims.get('schema') != 'FRANKIE_SCIENTIFIC_CLAIM_INPUTS_V1' or \
                claims.get('author') != author or claims.get('claims_sha256') != doc.get('claims_sha256'):
            raise ValueError('retained legal claim projection differs from the scientific lesson binding')
        ids = [c['id'] for c in claims['claims']]
        if len(ids) != len(set(ids)) or ids != [r['claim_id'] for r in doc['results']]:
            raise ValueError('retained legal claims do not match the scientific lesson results in order')
        return {c['id']: c for c in claims['claims']}, None
    if author == 'historical' and source and not Path(source).is_file() and 'research/' in source:
        # a committed file read from an earlier staged checkout: the same repo path in this one (claims_sha256 checks it)
        source = str(ROOT / source[source.index('research/'):])
    try:
        if author == 'frankie':
            claims = ST.frankie_claims(source, doc.get('day'))
        elif author == 'jev':
            claims = ST.jev_claims(source)
        else:
            claims = ST.historical_claims(source)
    except (OSError, ValueError, KeyError, TypeError, SystemExit) as error:
        return {}, 'the claims source %s could not be read (%s: %s); the claimed direction is listed unknown' % (
            source, type(error).__name__, error)
    if claims['claims_sha256'] != doc.get('claims_sha256'):
        return {}, ('the claims source %s now has claims sha256 %s, the lessons were written from %s; the claimed '
                    'direction is listed unknown' % (source, claims['claims_sha256'], doc.get('claims_sha256')))
    return {c['id']: c for c in claims['claims']}, None


def teacher_rows(path):
    """(the BOSS teacher's measurement of the day, None) or (None, why): its Dipole rows snapshot, checked against its
    own source_snapshot_hash, read into the per-component ledgers the teacher key is built from."""
    from research.kalshi.frankie_boss import dipole_classroom as DC
    from research.kalshi.frankie_boss.c15_journal import unpack, evidence_hash
    from research.kalshi.frankie_boss.c15_normalizer import COLUMNS
    if not path:
        return None, 'no Dipole rows of the day were given (the teacher-only step has not written them)'
    path = Path(path)
    if not path.is_file():
        return None, '%s is not on the box' % path
    raw = path.read_bytes()
    try:
        snapshot = unpack(json.loads(raw))
        if snapshot.get('schema') != DC.SOURCE_SCHEMA or tuple(snapshot.get('coverage_columns') or ()) != tuple(COLUMNS):
            return None, '%s is not a complete %s' % (path, DC.SOURCE_SCHEMA)
        if evidence_hash({k: v for k, v in snapshot.items() if k != 'source_snapshot_hash'}) != snapshot.get('source_snapshot_hash'):
            return None, '%s differs from its own source_snapshot_hash' % path
        ledgers = {name: DC._dimension_ledger(snapshot, i) for i, name in enumerate(COLUMNS)}
    except (ValueError, KeyError, TypeError) as error:
        return None, '%s could not be read (%s: %s)' % (path, type(error).__name__, error)
    return dict(path=str(path), sha256=sha256_bytes(raw), bytes=len(raw), rows=len(snapshot['rows']),
                source_snapshot_hash=snapshot['source_snapshot_hash'], as_of=snapshot['as_of'],
                through_cursor=snapshot['through_cursor'], ledgers=ledgers, columns=tuple(COLUMNS),
                retained_rows=snapshot['rows']), None


def retained_evidence_counts(measure, names):
    """Existing teacher count arithmetic on exactly named retained numeric leaves.

    This is a separate descriptive route. PRESENT in the temporary arithmetic
    ledger means a numeric value exists, never a governed target validity mask.
    No coefficient, new transform, claim verdict or independent test is produced.
    """
    from research.kalshi.frankie_boss import dipole_classroom as DC
    from research.kalshi.frankie_boss.c15_normalizer import State
    import frankie_box_experiment_search as SEARCH

    out = dict(schema='FRANKIE_RETAINED_DIPOLE_COUNTS_V1', fields=[], pairs=[], listed=[],
               source_sha256=measure['sha256'] if measure else None,
               source_snapshot_hash=measure['source_snapshot_hash'] if measure else None,
               as_of=measure['as_of'] if measure else None,
               through_cursor=measure['through_cursor'] if measure else None,
               axis='successive available observations on the retained teacher cursor sequence; '
                    'missing rows are bridged by the existing teacher co-movement calculation, '
                    'unlike adjacent F_LAST cells in search; no axis equivalence is claimed',
               units='original retained scalar representation; target normalized units are not inherited; '
                     'numerator/denominator leaves are separate quantities, not the fraction',
               rule='descriptive source-bound counts only; no target mask, independent confirmation, '
                    'joint finding, survivor promotion or original-research reproduction')
    if measure is None:
        out['listed'].append(dict(reason='no retained teacher snapshot available'))
        return out
    if '_retained_evidence_producers' not in measure:
        measure['_retained_evidence_producers'] = {
            m.__name__: sha256_bytes(Path(m.__file__).read_bytes()) for m in (DC, SEARCH)}
    out['arithmetic_sources'] = measure['_retained_evidence_producers']
    retained = measure['retained_rows']
    cursors = [row['cursor'] for row in retained]
    if (any(type(c) is not int or not 0 <= c <= measure['through_cursor'] for c in cursors)
            or cursors != sorted(set(cursors))
            or any(type(row['ts_recv_ns']) is not int or row['ts_recv_ns'] > measure['as_of'] for row in retained)):
        raise ValueError('retained teacher numeric evidence is not an ordered causal cursor sequence')
    cache = {}  # Per claim only: do not retain a whole-day ledger for every discovered field.
    selected = {}
    for name in dict.fromkeys(names):
        if not str(name).startswith('dipole.group'):
            continue  # The unchanged target/non-Dipole paths account for other names.
        match = re.fullmatch(r'dipole\.group_close\.by_entity\.(-?\d+):(-?\d+)\.(raw_components\..+|dstate\.state\..+)', str(name))
        if match is None:
            out['listed'].append(dict(series=name, reason='no exact entity-scoped closing-row numeric binding; '
                                     'positional rows and other field roles are not silently aliased'))
            continue
        entity = (int(match[1]), int(match[2]))
        leaf = match[3]
        if ('%d:%d' % entity) != '%s:%s' % (match[1], match[2]):
            out['listed'].append(dict(series=name, reason='entity spelling differs from the exact search field'))
            continue
        parts = leaf.split('.')
        if (leaf in ('dstate.state.anchor_dir', 'dstate.state.armed', 'dstate.state.broken',
                     'dstate.state.g_E', 'dstate.state.g_E_prev')
                or parts[0] == 'raw_components' and len(parts) == 3 and parts[-1] in ('state', 'mask')):
            out['listed'].append(dict(series=name, reason='retained categorical/flag/group-identity field; '
                                     'a numerical scientific meaning has not been declared'))
            continue
        if name not in cache:
            ledger, reasons = [], {}
            for row in retained:
                state = row.get('dstate')
                value, why = None, None
                if state is None:
                    why = 'source has no DState identity/closure binding'
                else:
                    if (state.get('schema') != 'FRANKIE_TEACHER_DSTATE_ROWS_V1'
                            or any(state.get(k) != row[k] for k in ('cursor', 'source_prefix_hash', 'ts_recv_ns'))
                            or any(type(state.get(k)) is not int for k in ('publisher_id', 'instrument_id'))
                            or state.get('status') not in ('GROUP_STATE', 'NOT_F_LAST')
                            or (state['status'] == 'GROUP_STATE') != isinstance(state.get('state'), dict)):
                        raise ValueError('retained teacher evidence has inconsistent row/entity/closure identity')
                    if (state['publisher_id'], state['instrument_id']) != entity:
                        why = 'another entity'
                    elif state['status'] != 'GROUP_STATE':
                        why = 'not a closing-row observation'
                    else:
                        nums, texts, _, _ = SEARCH.columns((row,), '')
                        value = nums.get(leaf, [None])[0]
                        if parts[0] == 'raw_components' and len(parts) == 3 and parts[-1] == 'value':
                            raw = (row.get('raw_components') or {}).get(parts[1]) or {}
                            if type(raw.get('state')) is not int or raw['state'] != int(State.PRESENT):
                                why = 'producer value unavailable (state=%s, reason=%s); placeholder not measured' % (
                                    raw.get('state'), raw.get('reason'))
                        if why is None and (type(value) not in (int, float)
                                            or type(value) is float and not math.isfinite(value)):
                            why = ('text field, not a numeric measurement' if leaf in texts and texts[leaf][0] is not None
                                   else 'absent, boolean or nonfinite numeric leaf')
                if why is not None:
                    reasons[why] = reasons.get(why, 0) + 1
                ledger.append(dict(cursor=row['cursor'], value=value if why is None else None,
                                   state='PRESENT' if why is None else 'MISSING'))
            available = sum(p['state'] == 'PRESENT' for p in ledger)
            summary = dict(series=name, entity=list(entity), leaf=leaf, rows=len(ledger), available=available,
                           unavailable=reasons, direction=DC._direction(ledger),
                           representation='retained numeric scalar; units not inferred from target names')
            cache[name] = (ledger, summary)
        ledger, summary = cache[name]
        out['fields'].append(summary)
        if summary['available']:
            selected[name] = (ledger, summary)
        else:
            out['listed'].append(dict(series=name, reason='no available numeric observation for this exact field'))
    for i, (left, (la, a)) in enumerate(selected.items()):
        for right, (lb, b) in list(selected.items())[i + 1:]:
            if a['entity'] != b['entity']:
                out['listed'].append(dict(pair=[left, right], reason='different entities; no cross-entity pairing defined'))
                continue
            co = DC._co_movement(la, lb)
            out['pairs'].append(dict(pair=[left, right], entity=a['entity'],
                aligned_cursors=co['aligned_cursors'], both_available=co['both_present'],
                steps_between_successive_available=co['steps_between_consecutive_both_present'], steps=co['steps'],
                availability_pairs={k.replace('PRESENT', 'NUMERIC').replace('MISSING', 'UNAVAILABLE'): v
                                    for k, v in co['state_pairs'].items()},
                direction_relation=DC._direction_relation(a['direction'], b['direction'])))
    if selected and not out['pairs']:
        out['listed'].append(dict(reason='no pair of available exact numeric fields for the same entity; '
                                 'governed targets are not implicitly mixed with this evidence axis'))
    return out


def retained_evidence_checks(item, said):
    evidence = item.get('retained_evidence')
    if not evidence or not (evidence['fields'] or evidence['listed']):
        return [], []
    text = 'BOSS retained-input accounting (the scientific seat reads the same measurement, not another test): ' + said.v(
        json.dumps(evidence, sort_keys=True), evidence['source_sha256'] or item['lesson_sha256'],
        'source-bound retained Dipole numeric counts and limits')
    return [dict(source_id=item['evidence_source_id'], claim='retained Dipole input measurements',
                 check=text, result='unresolved')], [text]


def component_of(name, columns):
    """The teacher's component a claimed or searched series name is, or None (the search names it dipole.<component>)."""
    n = str(name)
    if n.startswith('dipole.'):
        n = n[len('dipole.'):]
    if n in columns:
        return n
    key = re.sub(r'[^a-z0-9]', '', n.lower())
    hits = [c for c in columns if re.sub(r'[^a-z0-9]', '', c.lower()) == key]
    return hits[0] if len(hits) == 1 else None


def measure_component(measure, name):
    from research.kalshi.frankie_boss import dipole_classroom as DC
    ledger = measure['ledgers'][name]
    reasons = {}
    for p in ledger:
        if p['state'] != 'PRESENT':
            key = '%s: %s' % (p['state'], p.get('raw_reason') or '(no reason recorded)')
            reasons[key] = reasons.get(key, 0) + 1
    return dict(name=name, cursors=len(ledger), state_counts=DC._state_counts(ledger), direction=DC._direction(ledger),
                terminal_state=ledger[-1]['state'] if ledger else None, nonpresent_reasons=reasons)


def measure_pair(measure, a, b):
    """The teacher's own pair measurement, exactly as its key computes it (dipole_classroom._direction_relation, _pearson,
    _co_movement): the coefficient over its own overlap and the co-movement counts, per pair and per day."""
    from research.kalshi.frankie_boss import dipole_classroom as DC
    la, lb = measure['ledgers'][a], measure['ledgers'][b]
    return dict(direction_relation=DC._direction_relation(DC._direction(la), DC._direction(lb)),
                correlation=DC._pearson(la, lb), co_movement=DC._co_movement(la, lb))


def claimed_names(result):
    """The claim's series names as the lessons carry them: the matched ones, then those not in the search."""
    names = list(result.get('series_matched') or {})
    names += [m['series'] for m in result.get('cannot_test_yet') or [] if m.get('series') not in names]
    return names


def way_of(same, opposite):
    return 'same' if same > opposite else 'opposite' if opposite > same else None


def relation_way(relation):
    return {'SAME_DIRECTION': 'same', 'OPPOSITE_DIRECTION': 'opposite'}.get(relation)


def against(claimed, measured):
    """A check's result: the measured way against the claimed way."""
    if claimed is None or measured is None:
        return 'unresolved'
    return 'supports' if claimed == measured else 'contradicts'


def position_of(results):
    supports, contradicts = results.count('supports'), results.count('contradicts')
    return 'AGREE' if supports and not contradicts else 'DISAGREE' if contradicts and not supports else 'UNRESOLVED'


# ------------------------------------------------------------------------------------------------ turn 1: BOSS teacher
def count_margins(row):
    """The exact-integer checks and complements shared_count_accounting applies to one search row: (reasons, margins)
    where margins = dict(steps, both, x, y, complements) when the row is well formed, else None."""
    counts = row.get('counts')
    reasons = []
    for field in ('x', 'y', 'x_transform', 'y_transform', 'cell'):
        if not isinstance(row.get(field), str) or not row[field]:
            reasons.append('missing exact ' + field)
    if 'cell_value' not in row or type(row.get('lag')) is not int:
        reasons.append('missing exact cell value or integer lag')
    names = ('same_way', 'opposite', 'both_moving', 'x_moves', 'y_moves')
    margins = None
    if (not isinstance(counts, dict) or type(row.get('steps')) is not int
            or any(type(counts.get(name)) is not int for name in names)):
        reasons.append('steps and movement counts must be integers, excluding booleans')
    else:
        steps, both = row['steps'], counts['both_moving']
        x, y = counts['x_moves'], counts['y_moves']
        if any(value < 0 for value in (steps, *(counts[name] for name in names))):
            reasons.append('negative movement count or step count')
        if counts['same_way'] + counts['opposite'] != both:
            reasons.append('same-way plus opposite counts differ from both-moving')
        if both > min(x, y) or max(x, y) > steps or x + y - both > steps:
            reasons.append('movement margins do not form a partition of the supplied steps')
        margins = dict(steps=steps, both=both, x=x, y=y,
                       complements=dict(x_only=x - both, y_only=y - both, neither=steps - x - y + both))
    return reasons, margins


def origin_evidence_accounting(result, day, src):
    """The candidate's own discovery rows on this day (the scientific reader's origin_evidence), accounted with the same
    exact margins as the shared search counts and delivered to both seats: ORIGIN EVIDENCE, listed, never a test, never
    an independent measurement, never a confirmation or an occurrence (R06; Greg, 2026-10-06). Each row keeps its exact
    identity (where: part sha256, ordinal, raw-line sha256) and whether it IS the candidate's discovery row.

    The margins are the shared route's: nonzero transformed-step counts at the retained circular shift, never PRESENT
    masks or known physical inactivity (zero may be stationary, missing or unclassified). A current-day origin row whose
    arithmetic cannot be performed is listed with its source row and reason AND taught as such, distinguishing identified
    discovery evidence from arithmetic that could not be performed; no result is invented and no such row is marked
    tested. The same object is consumed by BOTH seats and the lawful Frankie reply: one accounting, not a second
    measurement."""
    said = Said()
    schema = 'FRANKIE_ORIGIN_EVIDENCE_ACCOUNTING_V1'
    arithmetic = dict(x_only='x_moves - both_moving', y_only='y_moves - both_moving',
                      neither='steps - x_moves - y_moves + both_moving')
    rows = result.get('origin_evidence')
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        text = 'Origin evidence accounting unavailable: origin_evidence is not a row list; nothing is marked tested.'
        return dict(schema=schema, rows=[], listed=[dict(reason='origin_evidence is not a row list', teaching=text)],
                    teaching=[text], cites=[], independent_measurements=0, counts_as_test=False,
                    discovery_row_found=False, listed_on_day=1)
    entries, listed, teaching, found = [], [], [], False
    listed_on_day = 0

    def identified(row, where):
        """What the reader identified this row as, independent of whether its arithmetic can be performed."""
        if row.get('discovery_row') is True:
            return 'the exact discovery row (part sha256, ordinal and raw-line sha256 all equal to the candidate\'s origin)'
        if row.get('mark') == 'origin_evidence_mirror':
            return 'the mirror of a discovery-day row of the same pair'
        if row.get('fields_equal') is True:
            return 'a discovery-day row of the same pair with fields equal to the candidate\'s, not bound to its exact row'
        if where is not None:
            return 'a discovery-day row of the same pair (exact where record present), not the discovery row'
        return None
    for ordinal, row in enumerate(rows):
        origin = dict(lesson_sha256=src['sha256'], source_id=src['source_id'], claim_id=result.get('claim_id'),
                      origin_ordinal=ordinal,
                      origin_sha256=sha256_bytes(json.dumps(finite(row), sort_keys=True, separators=(',', ':')).encode()))
        if not isinstance(row, dict):
            text = ('Origin evidence accounting is unavailable for origin row %s: it is not an object. No discovery '
                    'evidence is identified by it, no arithmetic was performed and nothing is marked tested.'
                    % said.v(ordinal, src['sha256'], 'origin row ordinal in the lessons'))
            listed.append(dict(origin, reason='origin row is not an object', source_row=row, identified=None,
                               teaching=text))
            teaching.append(text)
            listed_on_day += 1
            continue
        if row.get('day') != day:
            listed.append(dict(origin, day=row.get('day'), reason='outside current day; original status unchanged'))
            continue
        reasons, margins = count_margins(row)
        where = row.get('where') if isinstance(row.get('where'), dict) else None
        if where is None:
            reasons.append('no exact where record (part sha256, ordinal, raw-line sha256)')
        what = identified(row, where)
        if reasons:
            # Listed, never dropped (R04, R13): the reader's identification is kept apart from the arithmetic that
            # could not be performed; the source row and the reason stay; nothing is invented or marked tested.
            text = ('Origin evidence accounting is unavailable for a retained current-day origin row (%s%s): %s. %s '
                    'No arithmetic was performed on it; its original reader status is unchanged and it is not marked tested.' % (
                        said.v('the reader identified it as ' + what if what else 'not identified as discovery evidence',
                               src['sha256'], 'origin row identification'),
                        ('; part %s row %s' % (said.v(str(where.get('part_sha256'))[:12], src['sha256'], 'origin part sha256'),
                                               said.v(where.get('row'), src['sha256'], 'origin row ordinal'))) if where else '',
                        '; '.join(reasons),
                        'It remains identified discovery evidence whose margins cannot be stated.' if what
                        else 'It cannot be identified as discovery evidence and its margins cannot be stated.'))
            listed.append(dict(origin, reason='; '.join(reasons), source_row=row, identified=what, where=where,
                               discovery_row=row.get('discovery_row') is True, counts_as_test=False, teaching=text))
            teaching.append(text)
            listed_on_day += 1
            continue
        discovery = row.get('discovery_row') is True
        found = found or discovery
        scope = {key: row[key] for key in ('day', 'x', 'y', 'x_transform', 'y_transform', 'cell', 'cell_value', 'lag')}
        scope_text = ('on %s, %s -> %s (%s / %s), cell %s=%s, lag %s' % tuple(
            said.v(scope[key], src['sha256'], 'origin row ' + key)
            for key in ('day', 'x', 'y', 'x_transform', 'y_transform', 'cell', 'cell_value', 'lag')))
        c = margins['complements']
        text = ('Origin evidence %s (%s; part %s row %s): the candidate\'s own discovery day; at the retained circular '
                'shift, of %s transformed steps, same way %s, opposite %s, both nonzero %s, x alone nonzero %s, y alone '
                'nonzero %s, neither %s. These are exact complements of the supplied movement counts; they add no '
                'observation or scientific confirmation. Zero does not distinguish stationary from missing or '
                'unclassified inputs, so these margins are not known physical inactivity and do not supply a target '
                'mask. Listed as the evidence the candidate was read from: not a test, not an independent measurement, '
                'not another occurrence and not a confirmation.' % (
                    scope_text,
                    said.v(what, src['sha256'], 'origin row identity'),
                    said.v(str(where.get('part_sha256'))[:12], src['sha256'], 'origin part sha256'),
                    said.v(where.get('row'), src['sha256'], 'origin row ordinal'),
                    said.v(margins['steps'], src['sha256'], 'origin steps'),
                    said.v(row['counts']['same_way'], src['sha256'], 'origin same_way'),
                    said.v(row['counts']['opposite'], src['sha256'], 'origin opposite'),
                    said.v(margins['both'], src['sha256'], 'origin both_moving'),
                    said.v(c['x_only'], src['sha256'], 'derived accounting: x_moves - both_moving'),
                    said.v(c['y_only'], src['sha256'], 'derived accounting: y_moves - both_moving'),
                    said.v(c['neither'], src['sha256'], 'derived accounting: steps - x_moves - y_moves + both_moving')))
        entries.append(dict(origin, scope=scope, where=where, discovery_row=discovery, mark=row.get('mark'),
                            mirror_of=row.get('mirror_of'), fields_equal=row.get('fields_equal'),
                            origin_part_in_search=row.get('origin_part_in_search'),
                            counts=dict(row['counts'], steps=margins['steps']), accounting=c, formulas=arithmetic,
                            alignment='original search circular shift at the retained lag and cell',
                            chance_check=row.get('chance_check'), beyond_chance=row.get('beyond_chance'),
                            basis='origin_evidence', independent_measurement=False, counts_as_test=False,
                            scientific_status_changed=False, teaching=text))
        teaching.append(text)
    return dict(schema=schema, rows=entries, listed=listed, teaching=teaching, cites=said.cites,
                independent_measurements=0, counts_as_test=False, discovery_row_found=found,
                listed_on_day=listed_on_day,
                limitation='nonzero transformed-step margins at the retained circular shift, not PRESENT masks or known '
                           'physical inactivity: zero may be stationary, missing or unclassified (the shared route\'s '
                           'qualification, same formulas)',
                rule='origin rows are read, never counted: the disposition, tests and days_tested cover other days only; '
                     'no occurrence minimum, rarity label or promotion follows from them (R06); a row whose arithmetic '
                     'cannot be performed is listed and taught with its reason, never marked tested')


def shared_count_accounting(result, day, src):
    """Exact complements of supplied search counts, never another scientific measurement.

    Each row remains on its original day/cell/transform/lag scope. Nonzero
    transformed movements are not PRESENT masks: zero can also encode an
    unclassified input. No target, mask, score or validity rule is constructed.
    """
    said = Said()
    measurements, listed, teaching, proposals = [], [], [], []
    schema = 'FRANKIE_BOSS_SHARED_COUNT_ACCOUNTING_V1'
    tests = result.get('tests')
    if tests is None:
        tests = []
    if not isinstance(tests, list):
        return dict(schema=schema, measurements=[], listed=[dict(reason='tests is not a row list')],
                    teaching=['Shared search count accounting unavailable: tests is not a row list.'],
                    proposals=[], cites=[], independent_measurements=0)
    for ordinal, row in enumerate(tests):
        origin = dict(lesson_sha256=src['sha256'], source_id=src['source_id'],
                      claim_id=result.get('claim_id'), test_ordinal=ordinal,
                      test_sha256=sha256_bytes(json.dumps(finite(row), sort_keys=True,
                                                         separators=(',', ':')).encode()))
        if not isinstance(row, dict):
            listed.append(dict(origin, reason='test is not an object', source_test=row))
            continue
        if row.get('day') != day:
            listed.append(dict(origin, day=row.get('day'), reason='outside current day; original status unchanged'))
            continue
        counts = row.get('counts')
        reasons, margins = count_margins(row)
        if margins is not None:
            steps, both, x, y = margins['steps'], margins['both'], margins['x'], margins['y']
        if reasons:
            listed.append(dict(origin, reason='; '.join(reasons), source_test=row))
            teaching.append('Shared count accounting is unavailable for a retained current-day search row: '
                            + '; '.join(reasons) + '. Its original scientific status is unchanged.')
            continue
        complements = dict(x_only=x - both, y_only=y - both, neither=steps - x - y + both)
        scope = {key: row[key] for key in ('day', 'x', 'y', 'x_transform', 'y_transform', 'cell', 'cell_value', 'lag')}
        scope_text = ('on %s, %s -> %s (%s / %s), cell %s=%s, lag %s' % tuple(
            said.v(scope[key], src['sha256'], 'shared search row ' + key)
            for key in ('day', 'x', 'y', 'x_transform', 'y_transform', 'cell', 'cell_value', 'lag')))
        arithmetic = dict(x_only='x_moves - both_moving', y_only='y_moves - both_moving',
                          neither='steps - x_moves - y_moves + both_moving')
        text = ('Shared search accounting %s: at the retained circular shift, of %s transformed steps, x alone is nonzero %s times, '
                'y alone %s, neither %s, and both %s. These are exact complements of the supplied movement counts; '
                'they add no observation or scientific confirmation. Zero does not distinguish stationary from '
                'missing or unclassified inputs, so these margins do not supply a target mask.' % (
                    scope_text, said.v(steps, src['sha256'], 'shared search steps'),
                    said.v(complements['x_only'], src['sha256'], 'derived accounting: ' + arithmetic['x_only']),
                    said.v(complements['y_only'], src['sha256'], 'derived accounting: ' + arithmetic['y_only']),
                    said.v(complements['neither'], src['sha256'], 'derived accounting: ' + arithmetic['neither']),
                    said.v(both, src['sha256'], 'shared search both_moving')))
        scope_not_tested = row.get('scope_not_tested')
        if scope_not_tested:
            text += ' Original untested scope remains: ' + json.dumps(scope_not_tested, sort_keys=True) + '.'
        entry = dict(origin, scope=scope, source_test=row, original_status=row.get('mark'),
                     scope_not_tested=scope_not_tested, chance_check=row.get('chance_check'),
                     counts=dict(counts, steps=steps), accounting=complements, formulas=arithmetic,
                     alignment='original search circular shift at the retained lag and cell',
                     basis='shared_search_count_accounting', independent_measurement=False,
                     scientific_status_changed=False, teaching=text)
        measurements.append(entry)
        teaching.append(text)
        proposals.append(dict(proposal_id='control:shared-counts:' + origin['test_sha256'] + ':' + str(ordinal),
            kind='control', pair=[row['x'], row['y']], scope=scope, origin=origin,
            basis='shared_search_count_accounting', target_changes='NONE',
            text='Proposed control %s: preserve the exact condition and lag when examining the underlying source '
                 'states and feature availability before constructing any training target or mask. The supplied '
                 'zero/nonzero margins do not determine those states; no control or target change is applied.' % scope_text))
    return dict(schema=schema, measurements=measurements, listed=listed, teaching=teaching,
                proposals=proposals, cites=said.cites, independent_measurements=0)


def boss_turn(D, S, item, result, claim, measure, measure_why, day, src, rows_id, *, shared=None, origin=None):
    """The BOSS teacher's turn on one scientific-teacher result, within its own role: its measurement, its masks and
    controls. Returns (the turn in the discussion schema, the measured pairs and components, the proposals, cites)."""
    said = Said()
    shared = shared if shared is not None else shared_count_accounting(result, day, src)
    origin = origin if origin is not None else origin_evidence_accounting(result, day, src)
    rsha = measure['sha256'] if measure else None
    names = claimed_names(result)
    direction = claim.get('direction') if claim else None
    label = '%s %s' % (AUTHOR_LABEL[item['author']], item['claim_id'])
    checks, reasoning, measured, proposals, components = [], [], [], [], {}
    if measure is None:
        reasoning.append('The BOSS teacher has no measurement of %s: %s.' % (said.v(day, src['sha256'], 'day'), measure_why))
        checks.append(dict(source_id=src['source_id'], claim=label, result='unresolved',
                           check='the BOSS teacher has no Dipole rows of %s: %s' % (day, measure_why)))
    columns = measure['columns'] if measure else ()
    comps = {n: component_of(n, columns) for n in names} if measure else {}
    for n, c in comps.items():
        if c and c not in components:
            components[c] = measure_component(measure, c)
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
    if measure is not None and not pairs:
        checks.append(dict(source_id=src['source_id'], claim=label, result='unresolved',
                           check='the claim names %d series; the BOSS teacher measures pairs of its 19 components, so there '
                                 'is no pair to measure' % len(names)))
        reasoning.append('The claim names %s series, so the BOSS teacher has no pair of its own to measure.'
                         % said.v(len(names), src['sha256'], 'series named by the claim'))
    for a, b in pairs if measure is not None else ():
        ca, cb = comps.get(a), comps.get(b)
        if not (ca and cb) or ca == cb:
            outside = [x for x, c in ((a, ca), (b, cb)) if not c]
            why = ('%s %s not one of the teacher\'s 19 Dipole components' % (', '.join(outside), 'is' if len(outside) == 1 else 'are')
                   if outside else 'both names are the same component %s' % ca)
            checks.append(dict(source_id=rows_id, claim='%s: %s / %s' % (label, a, b), result='unresolved',
                               check='no teacher measurement of the pair on %s: %s' % (day, why)))
            reasoning.append('On the pair %s / %s the BOSS target-ledger comparison has no measurement: %s; '
                             'retained-input accounting, where supported, is stated separately from the scientific '
                             'teacher\'s counts.' % (said.v(a, src['sha256'], 'claimed series'),
                                                                     said.v(b, src['sha256'], 'claimed series'), why))
            continue
        m = measure_pair(measure, ca, cb)
        co, corr = m['co_movement'], m['correlation']
        st = co['steps']
        same, opposite = st['same_direction'], st['opposite_direction']
        steps = co['steps_between_consecutive_both_present']
        teacher_way = way_of(same, opposite)
        rel_way = relation_way(m['direction_relation'])
        claimed = direction
        pair_text = '%s / %s' % (said.v(ca, rsha, 'component'), said.v(cb, rsha, 'component'))
        steps_text = ('over %s consecutive both-PRESENT cursors of %s the two moved the same way %s times and the opposite '
                      'way %s times (%s only %s, %s only %s, neither %s)' % (
                          said.v(steps, rsha, 'consecutive both-PRESENT steps'), said.v(day, rsha, 'day'),
                          said.v(same, rsha, 'steps: same_direction'), said.v(opposite, rsha, 'steps: opposite_direction'),
                          ca, said.v(st['left_moved_only'], rsha, 'steps: left_moved_only'),
                          cb, said.v(st['right_moved_only'], rsha, 'steps: right_moved_only'),
                          said.v(st['neither_moved'], rsha, 'steps: neither_moved')))
        dir_a, dir_b = components[ca]['direction'], components[cb]['direction']
        relation_text = 'first-to-last PRESENT: %s %s, %s %s, relation %s' % (
            ca, said.v(dir_a, rsha, 'first_to_last_present_direction of %s' % ca),
            cb, said.v(dir_b, rsha, 'first_to_last_present_direction of %s' % cb),
            said.v(m['direction_relation'], rsha, 'direction_relation'))
        corr_text = ('Pearson %s over %s overlapping PRESENT values' % (
            said.v(corr['pearson'], rsha, 'pearson'), said.v(corr['present_overlap'], rsha, 'present_overlap'))
            if corr.get('pearson') is not None else
            'Pearson not reported (%s; %s overlapping PRESENT values)' % (
                said.v(corr.get('reason'), rsha, 'pearson not reported: reason'),
                said.v(corr.get('present_overlap'), rsha, 'present_overlap')))
        checks.append(dict(source_id=rows_id, claim='%s: %s / %s move %s' % (label, a, b, claimed or '(no direction stated '
                                                                              'in a testable form)'),
                           check='the teacher\'s steps on %s: %s' % (day, steps_text), result=against(claimed, teacher_way)))
        checks.append(dict(source_id=rows_id, claim='%s: %s / %s move %s' % (label, a, b, claimed or '(no direction stated '
                                                                              'in a testable form)'),
                           check='the teacher\'s %s on %s' % (relation_text, day), result=against(claimed, rel_way)))
        verb = {'supports': 'agrees with', 'contradicts': 'qualifies'}.get(against(claimed, teacher_way), 'leaves open')
        reasoning.append('On %s the BOSS teacher\'s own rows of %s: %s; %s; %s. Its step counts %s the claimed direction '
                         '(%s); the counts are per pair and per day, never pooled (R05).'
                         % (pair_text, said.v(day, rsha, 'day'), steps_text, relation_text, corr_text, verb,
                            said.v(claimed or 'none stated', src['sha256'], 'claimed direction')))
        measured.append(dict(pair=[ca, cb], claimed=[a, b], day=day, teacher_way=teacher_way, relation_way=rel_way,
                             direction_relation=m['direction_relation'], correlation=corr, co_movement=co,
                             directions={ca: dir_a, cb: dir_b}))
        # masks: the teacher's state mask on the pair, and its ablated / invalid cursors per component
        not_both = {k: v for k, v in co['state_pairs'].items() if k != 'PRESENT|PRESENT'}
        if not_both:
            proposals.append(dict(
                proposal_id='mask:both_present:%s:%s' % (ca, cb), kind='mask', pair=[ca, cb], counts=not_both,
                text='the BOSS teacher\'s state mask on %s / %s: count only cursors where both are PRESENT; on %s, %s of %s '
                     'aligned cursors are not both PRESENT (%s)' % (
                         ca, cb, said.v(day, rsha, 'day'), said.v(sum(not_both.values()), rsha, 'aligned cursors not both PRESENT'),
                         said.v(co['aligned_cursors'], rsha, 'aligned_cursors'),
                         ', '.join('%s %s' % (k, said.v(v, rsha, 'state_pairs %s' % k)) for k, v in sorted(not_both.items())))))
        for c in (ca, cb):
            counts = components[c]['state_counts']
            masked = {k: counts[k] for k in ('ABLATED', 'INVALID') if counts.get(k)}
            if masked and not any(p['proposal_id'] == 'mask:state:%s' % c for p in proposals):
                every = masked.get('ABLATED') == components[c]['cursors']
                proposals.append(dict(
                    proposal_id='mask:state:%s' % c, kind='mask', component=c, counts=masked,
                    reasons=components[c]['nonpresent_reasons'],
                    text=('the BOSS teacher\'s governed mask: %s is ABLATED at all %s cursors of %s, so it carries no '
                          'measurement that day; any count on it is over carried missing values' % (
                              c, said.v(components[c]['cursors'], rsha, 'cursors of %s' % c), said.v(day, rsha, 'day')))
                    if every else
                    'the BOSS teacher\'s mask on %s: exclude its %s cursors of %s (%s)' % (
                        c, ' and '.join('%s %s' % (k, said.v(v, rsha, '%s cursors of %s' % (k, c))) for k, v in sorted(masked.items())),
                        said.v(day, rsha, 'day'),
                        '; '.join('%s x%d' % (k, v) for k, v in sorted(components[c]['nonpresent_reasons'].items())))))
        proposals.append(dict(
            proposal_id='control:teacher_cursor_axis:%s:%s' % (ca, cb), kind='control', pair=[ca, cb],
            counts=dict(same_direction=same, opposite_direction=opposite, steps=steps),
            text='the BOSS teacher\'s control on the axis: %s / %s counted on its own cursors (consecutive both-PRESENT, '
                 'lag 0: same %s, opposite %s over %s steps) beside the search\'s F_LAST group-close axis at every lag; the '
                 'two axes are not the same steps and are not reconciled here' % (
                     ca, cb, said.v(same, rsha, 'steps: same_direction'), said.v(opposite, rsha, 'steps: opposite_direction'),
                     said.v(steps, rsha, 'consecutive both-PRESENT steps'))))
    # Shared accounting cannot turn agreement into another empirical check.
    own_position = position_of([c['result'] for c in checks])
    retained_checks, retained_words = retained_evidence_checks(item, said)
    checks.extend(retained_checks)
    reasoning.extend(retained_words)
    context_evidence, context_words = context_checks(item, day, src, said)
    checks.extend(context_evidence)
    reasoning.extend(context_words)
    for text in shared['teaching']:
        checks.append(dict(source_id=src['source_id'], claim='accounting of the retained shared search counts',
                           check=text, result='unresolved'))
    reasoning.extend(shared['teaching'])
    proposals.extend(shared['proposals'])
    said.cites.extend(c for c in shared['cites'] if c not in said.cites)
    for text in origin['teaching']:
        checks.append(dict(source_id=src['source_id'], claim='origin evidence of the candidate (listed, never a test)',
                           check=text, result='unresolved'))
    reasoning.extend(origin['teaching'])
    said.cites.extend(c for c in origin['cites'] if c not in said.cites)
    turn = dict(item_id=item['item_id'], responds_to_hash=S.digest(item['prior']), position=own_position,
                reasoning=' '.join(reasoning) or 'The BOSS teacher has nothing of its own to measure on this item.',
                evidence_checks=checks,
                build_forward=['the BOSS teacher\'s targets, masks and controls are unchanged by this exchange '
                               '(target_changes NONE); its proposals are tests for the search, listed, never applied here'],
                teaching_implications=['Frankie is shown the teacher\'s own counts for the pairs of this claim on %s beside '
                                       'the search\'s; nothing here grades him (R10)' % day] + shared['teaching']
                                      + origin['teaching'],
                proposed_training_experiments=[],
                uncertainty=['one day, %s; the teacher\'s counts are over its own cursors, the search\'s over F_LAST group '
                             'closes at lags; agreement between the two is orientation, never predictive or economic '
                             'proof' % day] + ([measure_why] if measure is None else []),
                next_tests=[p['text'] for p in proposals] or ['none proposed by the BOSS teacher on this item: it has no '
                                                             'pair of its own components to mask or control'],
                original_duties='PRESERVED', target_changes='NONE', predictive_status='UNESTABLISHED',
                economic_status='UNESTABLISHED')
    if item['author'] == 'historical':
        turn['next_tests'].append(HISTORICAL_REWORK)
    turn = D.parse_teacher(S.canonical(finite(turn)).decode(), item['request'], dict(item_id=item['item_id']), item['prior'])
    return turn, measured, components, proposals, said.cites


# ----------------------------------------------------------------------------------------- turn 2: scientific teacher
def per_day_marks(result):
    """{day: {tests, held, shown_otherwise, unresolved, counts_only}}: counts per day, never pooled across days."""
    out = {}
    for t in result.get('tests') or []:
        d = out.setdefault(t['day'], dict(tests=0, held=0, shown_otherwise=0, unresolved=0, counts_only=0))
        d['tests'] += 1
        d[t['mark']] = d.get(t['mark'], 0) + 1
    return dict(sorted(out.items()))


def science_turn(D, S, item, result, claim, boss, measured, proposals, day, src, *, origin=None):
    """The scientific teacher's reply to the BOSS teacher's turn: the search's counts on the same pairs, the counts per
    day, the challenges, the proposed tests listed untested. Returns (turn, sidecar, the teachers' findings, cites).

    origin: the ALREADY COMPUTED origin_evidence_accounting of this result (the object the BOSS seat stated). This seat
    consumes its arithmetic and listed reasons in its own record (evidence_checks, reasoning, teaching_implications,
    cites) before validation/hashing: the same counts, explicitly not a second measurement; unresolved, outside
    `compared`, findings, promotion and target masks (CCODE_NEXT_SOURCE_TASKS slice A follow-up 1)."""
    said = Said()
    lsha = src['sha256']
    origin = origin if origin is not None else origin_evidence_accounting(result, day, src)
    tests_day = [t for t in result.get('tests') or [] if t['day'] == day]
    origin_day = [o for o in result.get('origin_evidence') or [] if isinstance(o, dict) and o.get('day') == day]
    marks = per_day_marks(result)
    tx = (claim or {}).get('x_transform', 'sign_of_step')
    ty = (claim or {}).get('y_transform', 'sign_of_step')
    columns = tuple(m for pair in measured for m in pair['pair'])
    checks, reasoning, findings, compared = [], [], [], []
    for m in measured:
        ca, cb = m['pair']
        rows = [t for t in tests_day if t['cell'] == WHOLE_DAY and (t['x_transform'], t['y_transform']) == (tx, ty)
                and {component_of(t['x'], columns), component_of(t['y'], columns)} == {ca, cb}]
        st = m['co_movement']['steps']
        teacher_text = 'the BOSS teacher\'s steps on %s: %s / %s same %s, opposite %s' % (
            day, ca, cb, st['same_direction'], st['opposite_direction'])
        if not rows:
            checks.append(dict(source_id=src['source_id'], claim=teacher_text, result='unresolved',
                               check='the search holds no whole-day %s -> %s row of %s / %s on %s (the lessons carry %d rows of '
                                     'this claim on the day)' % (tx, ty, ca, cb, day, len(tests_day))))
            reasoning.append('The search holds no whole-day %s -> %s row of %s / %s on %s to set beside the BOSS teacher\'s '
                             'counts.' % (tx, ty, ca, cb, said.v(day, lsha, 'day')))
            continue
        for t in rows:
            c, ch = t['counts'], t['chance_check']
            beyond = bool(ch.get('shifts')) and ch.get('reached') == 0
            search_way = way_of(c['same_way'], c['opposite'])
            # The scientific reader retains counts for unsupported claim scopes.
            # Their chance result cannot promote them into a joint finding here.
            unsupported_scope = t.get('mark') == 'counts_only' or bool(t.get('scope_not_tested'))
            result_ = ('unresolved' if unsupported_scope or not beyond
                       else against(m['teacher_way'], search_way))
            row_text = ('on %s, whole day, %s -> %s (%s / %s) at lag %s: same way %s, opposite %s, both moving %s over %s '
                        'steps; chance check: %s of %s far shifts reached it' % (
                            said.v(day, lsha, 'day'), said.v(t['x'], lsha, 'x'), said.v(t['y'], lsha, 'y'),
                            said.v(t['x_transform'], lsha, 'x_transform'), said.v(t['y_transform'], lsha, 'y_transform'),
                            said.v(t['lag'], lsha, 'lag'), said.v(c['same_way'], lsha, 'same_way'),
                            said.v(c['opposite'], lsha, 'opposite'), said.v(c['both_moving'], lsha, 'both_moving'),
                            said.v(t['steps'], lsha, 'steps'), said.v(ch.get('reached'), lsha, 'chance: reached'),
                            said.v(ch.get('shifts'), lsha, 'chance: shifts')))
            if unsupported_scope:
                row_text += ('; retained scientific scope is %s, with untested scope %s; no joint finding is made '
                             'from this unsupported scope' % (
                                 said.v(t.get('mark'), lsha, 'scientific scope mark'),
                                 said.v(json.dumps(t.get('scope_not_tested') or [], sort_keys=True), lsha,
                                        'scientific scope not tested')))
            checks.append(dict(source_id=src['source_id'], claim=teacher_text, check='the search ' + row_text, result=result_))
            compared.append(result_)
            reasoning.append('To the BOSS teacher\'s counts on %s / %s: the search %s (%s).' % (
                ca, cb, row_text, {'supports': 'the same way as the teacher\'s steps',
                                   'contradicts': 'the other way from the teacher\'s steps'}.get(
                    result_, 'not beyond chance or no way to compare')))
            if result_ != 'supports':
                continue
            joint = m['teacher_way']
            claimed = (claim or {}).get('direction')
            kind = ('both_teachers_measured' if claimed is None else
                    'both_teachers_measured_the_claimed_way' if claimed == joint else 'both_teachers_measured_otherwise')
            fsaid = Said()
            rsha = item['rows_sha256']
            statement = (
                'HYPOTHESIS (the teachers\' own finding, R06): on %s, %s and %s moved %s: the BOSS teacher\'s rows over %s '
                'consecutive both-PRESENT cursors, same %s and opposite %s; the search %s -> %s (%s / %s) at lag %s on the '
                'whole day, same way %s, opposite %s, both moving %s, with %s of %s far shifts reaching it.' % (
                    fsaid.v(day, lsha, 'day'), fsaid.v(ca, rsha, 'component'), fsaid.v(cb, rsha, 'component'),
                    fsaid.v('the same way' if joint == 'same' else 'the opposite way', rsha, 'the teachers\' joint way'),
                    fsaid.v(m['co_movement']['steps_between_consecutive_both_present'], rsha, 'consecutive both-PRESENT steps'),
                    fsaid.v(st['same_direction'], rsha, 'steps: same_direction'),
                    fsaid.v(st['opposite_direction'], rsha, 'steps: opposite_direction'),
                    fsaid.v(t['x'], lsha, 'x'), fsaid.v(t['y'], lsha, 'y'), fsaid.v(t['x_transform'], lsha, 'x_transform'),
                    fsaid.v(t['y_transform'], lsha, 'y_transform'), fsaid.v(t['lag'], lsha, 'lag'),
                    fsaid.v(c['same_way'], lsha, 'same_way'), fsaid.v(c['opposite'], lsha, 'opposite'),
                    fsaid.v(c['both_moving'], lsha, 'both_moving'), fsaid.v(ch.get('reached'), lsha, 'chance: reached'),
                    fsaid.v(ch.get('shifts'), lsha, 'chance: shifts')))
            if kind == 'both_teachers_measured_otherwise':
                statement += ' The data is showing this instead of the claimed %s way (R07); only this subclaim on %s.' % (
                    fsaid.v(claimed, lsha, 'claimed direction'), day)
            findings.append(dict(
                schema=FINDING_SCHEMA, finding_id='teachers:%s:%s:%s:%s->%s:%s-%s:lag%s' % (
                    day, ca, cb, t['x'], t['y'], t['x_transform'], t['y_transform'], t['lag']),
                authors=[D.BOSS_ROLE, D.CLASSROOM_ROLE],
                author_label="the teachers' own finding (the BOSS teacher and the scientific teacher; not Frankie's, not Jev's)",
                from_item=item['item_id'], from_claim_author=item['author'], kind=kind, statement=statement,
                joint_way=joint, scope=dict(days=[day], pair=[ca, cb], cell=WHOLE_DAY, lag=t['lag'], x=t['x'], y=t['y'], x_transform=t['x_transform'],
                           y_transform=t['y_transform'], teacher_axis='consecutive both-PRESENT cursors of the teacher rows',
                           search_axis='F_LAST group closes'),
                counts=dict(teacher=dict(m['co_movement']['steps'], steps=m['co_movement']['steps_between_consecutive_both_present']),
                            search=dict(t['counts'], steps=t['steps'], chance_shifts=ch.get('shifts'), chance_reached=ch.get('reached'))),
                days_named=[day], disposition='SUPPORTED_SCOPED',
                disposition_note='orientation only (R14): the counts and the day are the finding',
                status='HYPOTHESIS',
                status_reason='the broader claim still requires mathematics, source, causal-timing and scientific '
                              'double-checks; this exchange does not complete survivor promotion',
                promotion='after those double-checks hold, one occurrence receives the same validity, certainty, '
                          'survivor, teaching and knowledge treatment as multiple occurrences; no minimum-occurrence '
                          'or minimum-days gate, rarity penalty or automatic hypothesis-only restriction (R06)',
                future_outcome_claimed=False, cites=fsaid.cites))
    day_count = marks.get(day) or dict(tests=0, held=0, shown_otherwise=0, unresolved=0, counts_only=0)
    day_text = ('on %s the search carries %s rows of this claim: held %s, shown otherwise %s, unresolved %s, counts only %s' % (
        said.v(day, lsha, 'day'), said.v(day_count['tests'], lsha, 'rows on the day'), said.v(day_count['held'], lsha, 'held'),
        said.v(day_count['shown_otherwise'], lsha, 'shown_otherwise'), said.v(day_count['unresolved'], lsha, 'unresolved'),
        said.v(day_count.get('counts_only', 0), lsha, 'counts_only')))
    if origin_day or origin['listed_on_day']:
        # the same source-bound accounting the BOSS seat stated: its counts are reused here, not measured again
        day_text += ('; origin evidence on this day: %s rows of the candidate\'s own discovery day (exact discovery row '
                     'found: %s; margins stated for %s, arithmetic unavailable and listed for %s), listed and never '
                     'counted as a test' % (
                         said.v(len(origin_day), lsha, 'origin rows on the day'),
                         said.v('yes' if origin['discovery_row_found'] else 'no', lsha, 'exact discovery row found'),
                         said.v(len(origin['rows']), lsha, 'origin rows with margins stated'),
                         said.v(origin['listed_on_day'], lsha, 'origin rows listed without arithmetic')))
    claim_result = ('unresolved' if not day_count['tests'] else
                    'supports' if day_count['held'] and not day_count['shown_otherwise'] else
                    'contradicts' if day_count['shown_otherwise'] and not day_count['held'] else 'unresolved')
    checks.append(dict(source_id=src['source_id'], claim='%s %s' % (AUTHOR_LABEL[item['author']], item['claim_id']),
                       check='the search\'s counts ' + day_text, result=claim_result))
    per_day_text = '; '.join('%s: %s rows, held %s, shown otherwise %s, unresolved %s, counts only %s' % (
        said.v(d, lsha, 'day'), said.v(c['tests'], lsha, 'rows on %s' % d), said.v(c['held'], lsha, 'held on %s' % d),
        said.v(c['shown_otherwise'], lsha, 'shown_otherwise on %s' % d), said.v(c['unresolved'], lsha, 'unresolved on %s' % d),
        said.v(c.get('counts_only', 0), lsha, 'counts_only on %s' % d)) for d, c in marks.items()) or 'no rows on any day'
    challenges = [x for x in result.get('challenge') or [] if re.search(r'\bon %s\b' % day, x)]
    reasoning.append('For the claim: %s. Per discovery day tested, each on its own and never pooled: %s. The disposition '
                     'word %s is orientation only (R14).' % (day_text, per_day_text,
                                                              said.v(result.get('disposition'), lsha, 'disposition')))
    if challenges:
        reasoning.append(' '.join(challenges))
    proposed = [dict(proposal_id=p['proposal_id'], kind=p['kind'], by=D.BOSS_ROLE, status='proposed_untested',
                     text='proposed by the BOSS teacher, not run by the search yet (listed, never dropped: R13): ' + p['text'])
                for p in proposals]
    untested = list(result.get('untested') or [])
    cannot = list(result.get('cannot_test_yet') or [])
    retained_checks, retained_words = retained_evidence_checks(item, said)
    checks.extend(retained_checks)
    reasoning.extend(retained_words)
    context_evidence, context_words = context_checks(item, day, src, said)
    checks.extend(context_evidence)
    reasoning.extend(context_words)
    # Origin evidence: the BOSS seat's source-bound accounting consumed by this seat too (the same counts and the same
    # listed reasons; not a second measurement). Unresolved: never in `compared`, findings, promotion or target masks.
    for text in origin['teaching']:
        checks.append(dict(source_id=src['source_id'],
                           claim='origin evidence of the candidate (listed, never a test; the BOSS seat\'s accounting reused)',
                           check=text, result='unresolved'))
    reasoning.extend(origin['teaching'])
    said.cites.extend(c for c in origin['cites'] if c not in said.cites)
    turn = dict(item_id=item['item_id'], responds_to_hash=S.digest(boss), position=position_of(compared),
                reasoning=' '.join(reasoning), evidence_checks=checks,
                build_forward=[f['statement'] for f in findings],
                teaching_implications=['Frankie is taught the counts and the days named here; the search never grades him '
                                       '(fact grading stays the deterministic classroom grade)'] + origin['teaching'],
                proposed_training_experiments=[],
                uncertainty=['beyond chance means none of the far circular shifts reached the observed count; that label is '
                             'orientation, the counts are the result',
                             'the search counts over the F_LAST group-close axis at lags -L..L; the BOSS teacher\'s over its own '
                             'cursors at lag 0'],
                next_tests=[p['text'] for p in proposed] + ['untested (the lessons): ' + u for u in untested] +
                           ['cannot test yet: %s (%s)' % (x.get('series'), x.get('reason')) for x in cannot] +
                           ['double-check the mathematics, source evidence, causal timing and scientific work; one '
                            'checked occurrence is eligible for the same promotion as multiple occurrences (R06)',
                            'test later discovery days when the scoped condition occurs; a day without that condition '
                            'supplies no new test and does not downgrade a checked finding'],
                original_duties='PRESERVED', target_changes='NONE', predictive_status='UNESTABLISHED',
                economic_status='UNESTABLISHED')
    if item['author'] == 'historical':
        turn['next_tests'].append(HISTORICAL_REWORK)
    turn = D.parse_teacher(S.canonical(finite(turn)).decode(), item['request'], dict(item_id=item['item_id']), boss)
    side = dict(counts_on_day=tests_day, counts_per_day=marks, challenges_on_day=challenges, proposed_tests=proposed,
                untested=untested, cannot_test_yet=cannot, day_text=day_text, origin_on_day=origin_day,
                origin_accounting_consumed=dict(rows_with_margins=len(origin['rows']), listed_on_day=origin['listed_on_day'],
                                                discovery_row_found=origin['discovery_row_found'],
                                                independent_measurements=0, counts_as_test=False,
                                                basis='the BOSS seat\'s origin_evidence_accounting reused in this seat\'s '
                                                      'record before hashing; not a second measurement'))
    return turn, side, findings, said.cites


# ------------------------------------------------------------------------------------------------------------ the run
def exchange(day, run, lessons_paths, rows_path, rules_witness, log=print, *, brain=None, input_path=None):
    from research.kalshi.frankie_boss import dipole_teacher_discussion as D
    from research.kalshi.frankie_boss import dipole_scientific_review as S
    import frankie_box_classroom_code as K
    knowledge = None
    if brain is not None:
        if input_path is None:
            raise ValueError('accumulated exchange knowledge requires a retained input path')
        knowledge = accumulated_lessons(day, run, lessons_paths, brain, input_path, rows_path, rules_witness)
        docs, listed = knowledge['documents'], list(knowledge['listed'])
    else:
        docs, listed = load_lessons(lessons_paths, day)
    if not docs:
        listed.append(dict(reason='no current or accumulated scientific lessons are available; no claim turns produced'))
    measure, measure_why = teacher_rows(rows_path)
    rows_id = 'teacher-dipole-rows:%s' % day
    request = dict(shared_knowledge=dict(sources=[dict(source_id=rows_id)] + [dict(source_id=s['source_id']) for _, s in docs]))
    items, findings, seen, seen_results = [], [], set(), set()
    lesson_contexts = []
    for doc, src in docs:
        context = lesson_context(doc)
        lesson_contexts.append(dict(source=src, context=context,
                                    blind_jev=src['author'] == 'jev' and not src.get('accumulated')))
        if knowledge is None:
            claims, claims_why = claims_of(doc)
        else:
            retained_claims = knowledge['claims_by_source'][src['source_id']]
            claims, claims_why = retained_claims['claims'], retained_claims['listed']
        if claims_why:
            listed.append(dict(path=src['path'], reason=claims_why))
        for result in doc.get('results') or []:
            result_hash = S.digest(finite(result))
            result_identity = (src['author'], src.get('claims_sha256'), result_hash)
            if result_identity in seen_results:
                listed.append(dict(path=src['path'], sha256=src['sha256'], claim_id=result['claim_id'],
                                   result_digest=result_hash, reason='identical source-bound lesson result already supplied'))
                continue
            seen_results.add(result_identity)
            item_id = '%s:%s' % (src['author'], result['claim_id'])
            if src.get('accumulated'):
                item_id += ':knowledge:' + src['sha256']
            if item_id in seen:
                raise SystemExit('%s is answered by two lessons files for %s: duplicate data declines the exchange (R16)'
                                 % (item_id, day))
            seen.add(item_id)
            prior = finite(result)
            claim = claims.get(result['claim_id'])
            item = dict(item_id=item_id, author=src['author'], claim_id=result['claim_id'], prior=prior, request=request,
                        rows_sha256=measure['sha256'] if measure else None, lesson_context=context)
            item.update(retained_evidence=retained_evidence_counts(measure, claimed_names(prior)),
                        evidence_source_id=rows_id, lesson_sha256=src['sha256'])
            shared = shared_count_accounting(prior, day, src)
            origin = origin_evidence_accounting(prior, day, src)
            boss, measured, components, proposals, boss_cites = boss_turn(D, S, item, prior, claim, measure, measure_why,
                                                                          day, src, rows_id, shared=shared, origin=origin)
            science, side, found, science_cites = science_turn(D, S, item, prior, claim, boss, measured, proposals, day, src,
                                                               origin=origin)
            rework = None
            if src['author'] == 'historical':
                # Scoped measurements remain evidence. Neither seat may turn an
                # inherited rejection (or a counts-only reassessment) into closure.
                # A PERFORMED reproduction status the reader took from a hash-bound HISTORICAL_REPRODUCTION_V1 record
                # (performed_matched / performed_differs, with the record listed) is kept, never overwritten by this
                # exchange, which itself establishes nothing; any other value is not established here (slice B).
                prior_rework = result.get('research_rework') or {}
                reproduction = prior_rework.get('original_calculation_reproduction')
                records = (prior_rework.get('reproduction_records') or {}).get('records') or []
                performed = (isinstance(reproduction, str) and reproduction.startswith('performed_')
                             and any(isinstance(r, dict) and r.get('record_sha256') and r.get('status') == reproduction
                                     for r in records))
                rework = dict(prior_rework, status='OPEN_REWORK_REQUIRED', closed=False,
                    claim_id=result['claim_id'], lesson_sha256=src['sha256'],
                    collection=context.get('reconsideration'),
                    prior_disposition=result.get('disposition'),
                    original_calculation_reproduction=reproduction if performed else 'not_established_by_this_exchange',
                    reproduction_status_source=('the reader\'s hash-bound HISTORICAL_REPRODUCTION_V1 record(s), kept as read'
                                                if performed else 'none: no performed record was read by the lessons'),
                    repair_or_reformulation='not_established_by_this_exchange',
                    note='existing search counts may reassess a mapped claim; they do not establish '
                         'reproduction or repair of the original discarded research; a performed reproduction is the '
                         'teachers\' own recorded execution and is reported, not re-established, here')
                side['untested'].append(
                    ('Original research reproduction is recorded by the teachers\' own execution (%s, hash-bound record); '
                     'repair/reformulation remains open; the current count comparison establishes neither.' % reproduction)
                    if performed else
                    'Original research reproduction and repair/reformulation remain open; '
                    'the current count comparison does not establish their completion.')
            findings += found
            turns = [dict(turn=1, seat='boss_teacher', author=D.BOSS_ROLE, author_label=BOSS_AUTHOR,
                          responds_to='the scientific teacher\'s lessons result on the claim', record=boss,
                          measured=finite(measured), components=components, proposals=proposals,
                          shared_accounting=finite(shared), origin_accounting=finite(origin), research_rework=rework),
                     dict(turn=2, seat='scientific_teacher', author=D.CLASSROOM_ROLE, author_label=SCIENCE_AUTHOR,
                          responds_to='the BOSS teacher\'s turn', record=science, research_rework=rework,
                          origin_accounting=finite(origin), **finite(side))]
            voice = [dict(seat='boss_teacher', author=D.BOSS_ROLE, author_label=BOSS_AUTHOR, text=boss['reasoning'],
                          lines=[c['check'] for c in boss['evidence_checks']] + boss['next_tests'], cites=boss_cites),
                     dict(seat='scientific_teacher', author=D.CLASSROOM_ROLE, author_label=SCIENCE_AUTHOR,
                          text=science['reasoning'], lines=[c['check'] for c in science['evidence_checks']] + science['next_tests'],
                          cites=science_cites)]
            blind_jev = src['author'] == 'jev' and not src.get('accumulated')
            if blind_jev:
                turns.append(dict(turn=3, seat='frankie', author='frankie', withheld=True, reason=JEV_WALL))
            else:
                final = D.final_turn(boss, science)
                reply, frankie_side = K.exchange_reply(
                    item_id=item_id, author=src['author'], day=day, final=final,
                    joint=[f for f in found], day_text=side['day_text'], marks=side['counts_per_day'],
                    lessons_sha256=src['sha256'], proposed=[p['text'] for p in side['proposed_tests']])
                # The existing reply previously used joint findings/count totals
                # only. Deliver the BOSS's actual shared arithmetic and limitations
                # to this learner turn without changing its scientific resolution.
                reply['learned'].extend(shared['teaching'])
                retained_said = Said()
                _, retained_words = retained_evidence_checks(item, retained_said)
                reply['learned'].extend(retained_words)
                frankie_side['retained_evidence'] = item['retained_evidence']
                frankie_side['cites'].extend(c for c in retained_said.cites if c not in frankie_side['cites'])
                if rework is not None:
                    frankie_side['research_rework'] = rework
                    reply['learned'].append('Historical conclusions are source-scoped claims, not final truth. '
                        'This research remains open for original-calculation reproduction and repair or reformulation.')
                if shared['teaching']:
                    reply['reasoning'] += (' I retain the BOSS teacher\'s shared count accounting and its original '
                                           'scope limits as teaching; it adds no measurement or confirmation.')
                frankie_side['shared_accounting'] = dict(schema=shared['schema'],
                    lesson_sha256=src['sha256'], test_origins=[{key: value[key] for key in
                        ('test_ordinal', 'test_sha256', 'lesson_sha256')} for value in shared['measurements']],
                    listed=shared['listed'], independent_measurements=0, scientific_status_changed=False)
                frankie_side['cites'].extend(c for c in shared['cites'] if c not in frankie_side['cites'])
                if origin['rows'] or origin['listed']:
                    reply['learned'].extend(origin['teaching'])
                    reply['learned'].append('Origin evidence is what a candidate was read from; reading it again is not '
                                            'an independent check, another occurrence or a confirmation (R06).')
                    frankie_side['origin_evidence'] = dict(schema=origin['schema'], lesson_sha256=src['sha256'],
                        rows=[{key: value[key] for key in ('origin_ordinal', 'origin_sha256', 'where', 'discovery_row',
                                                           'mark', 'scope')} for value in origin['rows']],
                        listed=origin['listed'], discovery_row_found=origin['discovery_row_found'],
                        independent_measurements=0, counts_as_test=False, scientific_status_changed=False)
                    frankie_side['cites'].extend(c for c in origin['cites'] if c not in frankie_side['cites'])
                if src.get('accumulated') and not side['counts_on_day']:
                    # The unchanged seat calculation describes today's available checks. A missing new test
                    # must not turn an already checked historical finding back into an untested hypothesis.
                    retained_note = ('No scientific test of this claim was supplied for the current day. '
                        'The retained lesson keeps its original scope and disposition %s with test days %s; '
                        'today supplies no downgrade or additional confirmation.' %
                        (result.get('disposition'), json.dumps(result.get('days_tested') or [])))
                    reply['reasoning'] = reply['reasoning'].replace(
                        'I keep it as a hypothesis with these counts named (R06).', retained_note)
                    frankie_side['corrected_understanding'] = frankie_side['corrected_understanding'].replace(
                        'I keep it as a hypothesis with these counts named (R06).', retained_note)
                    for i, disagreement in enumerate(frankie_side['remaining_disagreements']):
                        retained_disagreement = disagreement.replace(
                            'and this stays open', 'without changing the retained disposition')
                        frankie_side['remaining_disagreements'][i] = retained_disagreement
                        reply['reasoning'] = reply['reasoning'].replace(disagreement, retained_disagreement)
                    reply['learned'].append(retained_note)
                    # Keep the existing resolution vocabulary for the new current-day retest. It never changes
                    # the separately recorded status of the accumulated finding.
                    frankie_side['resolution_scope'] = 'current_day_retest_only'
                    frankie_side['current_test_status'] = 'NO_NEW_SCIENTIFIC_TEST'
                    frankie_side['prior_finding_status'] = dict(disposition=result.get('disposition'), unchanged=True,
                        days_tested=result.get('days_tested') or [], lesson_sha256=src['sha256'],
                        result_digest=result_hash)
                    for retained_day in result.get('days_tested') or []:
                        cite = dict(value=str(retained_day), source_sha256=src['sha256'], what='retained lesson test day')
                        if cite not in frankie_side['cites']:
                            frankie_side['cites'].append(cite)
                reply = D.parse_frankie(S.canonical(dict(reply, responds_to_hash=S.digest(final))).decode(),
                                        dict(item_id=item_id), final)
                turns.append(dict(turn=3, seat='frankie', author='frankie', author_label=K.AUTHOR,
                                  responds_to='both teachers\' turns', record=reply,
                                  **{k: v for k, v in frankie_side.items() if k != 'cites'}))
                voice.append(dict(seat='frankie', author='frankie', author_label=K.AUTHOR, text=reply['reasoning'],
                                  lines=reply['learned'] + reply['next_steps'], cites=frankie_side['cites']))
            items.append(dict(item_id=item_id, author=src['author'], author_label=AUTHOR_LABEL[src['author']],
                              claim=dict(claim_id=result['claim_id'], statement=result.get('statement'),
                                         day_made=result.get('day_made'), direction=(claim or {}).get('direction'),
                                         direction_text=(claim or {}).get('direction_text'),
                                         x_transform=(claim or {}).get('x_transform', 'sign_of_step'),
                                         y_transform=(claim or {}).get('y_transform', 'sign_of_step'),
                                         series=claimed_names(prior), days_tested=prior.get('days_tested'),
                                         disposition=prior.get('disposition')),
                              lessons=dict(path=src['path'], sha256=src['sha256'], result_digest=result_hash,
                                           accumulated=bool(src.get('accumulated')),
                                           current_day_test_rows=len(side['counts_on_day']),
                                           origin_rows_on_day=len(side.get('origin_on_day') or []),
                                           retained_test_days=sorted(side['counts_per_day'])),
                              lesson_context=context,
                              retained_evidence=item['retained_evidence'],
                              blind_jev=blind_jev,
                              turns=turns, voice_turns=voice))
    counts = dict(items=len(items), by_author={a: sum(i['author'] == a for i in items) for a in sorted(set(LESSONS.values()))},
                  boss_positions=tally(t['record']['position'] for i in items for t in i['turns'] if t['turn'] == 1),
                  science_positions=tally(t['record']['position'] for i in items for t in i['turns'] if t['turn'] == 2),
                  frankie_resolutions=tally(t.get('resolution') for i in items for t in i['turns']
                                            if t['turn'] == 3 and not t.get('withheld')),
                  teachers_findings=len(findings), teachers_findings_by_kind=tally(f['kind'] for f in findings))
    rows_source = None if measure is None else {k: measure[k] for k in ('path', 'sha256', 'bytes', 'rows',
                                                                       'source_snapshot_hash', 'as_of', 'through_cursor')}
    full = dict(schema=SCHEMA, view='full', run=run, day=day, day_role='discovery', rules=rules_witness,
                roles=dict(boss_teacher=D.BOSS_ROLE, scientific_teacher=D.CLASSROOM_ROLE, frankie='frankie'),
                positions=list(D.POSITIONS), dispositions=list(S.DISPOSITIONS),
                sources=dict(lessons=[s for _, s in docs], teacher_rows=rows_source, teacher_rows_listed=measure_why),
                items=items, lesson_contexts=lesson_contexts,
                teachers_findings=findings, counts=counts, listed=listed, model_calls=0,
                rule='each turn labelled with its author (R11); counts per day, never pooled or averaged (R04, R05); '
                     'the disposition word is orientation only (R14); no future-outcome claim (R02)')
    if knowledge is not None:
        full['knowledge_inputs'] = dict(path=str(input_path), sha256=sha256_bytes(Path(input_path).read_bytes()),
            versions=knowledge['versions'], sources=[src for _, src in docs],
            applied_to=['boss_turn', 'science_turn', 'frankie_exchange_reply'],
            selection_listed=knowledge['selection_listed'], school_listed=knowledge['school_listed'],
            rule='retained test counts remain on their original days; current teacher measurements are named separately; '
                 'zero current-day tests means no new scientific test, not rejection of a previously checked finding')
    full['exchange_hash'] = S.digest(finite(full))
    jev_items = [i for i in items if i['blind_jev']]
    blind_items = {i['item_id'] for i in jev_items}
    view = dict(full, view='frankie', items=[i for i in items if not i['blind_jev']],
                lesson_contexts=[c for c in lesson_contexts if not c['blind_jev']],
                teachers_findings=[f for f in findings if f['from_item'] not in blind_items],
                jev_withheld=dict(items=len(jev_items), findings=sum(f['from_item'] in blind_items for f in findings),
                                  reason=JEV_WALL),
                full_exchange_hash=full['exchange_hash'])
    view.pop('exchange_hash')
    view['exchange_hash'] = S.digest(finite(view))
    return finite(full), finite(view)


def tally(values):
    out = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))


def write_once(path, data):
    """(True, None) written or already there with these bytes; (False, why) when other bytes are there (never overwritten)."""
    path = Path(path)
    if path.exists():
        return (True, 'already there with the same bytes') if path.read_bytes() == data else (
            False, '%s exists with other bytes: duplicate data declines (R16)' % path)
    with path.open('xb') as f:
        f.write(data)
    return True, None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--day', required=True)
    p.add_argument('--run', required=True)
    p.add_argument('--lessons', action='append', default=[], help='a current-day lessons file (repeat); completed brain lessons also accumulate')
    p.add_argument('--teacher-rows', help='the BOSS teacher\'s Dipole rows of the day (host-dipole-classroom-source*.json)')
    p.add_argument('--out-dir', required=True, help='/opt/frankie-box/work/experiment/<run>/exchange/<day>')
    p.add_argument('--brain', default='/opt/frankie-box/brain')
    p.add_argument('--search', required=True, help='the owning day completed search for accumulated native claim tests')
    a = p.parse_args()
    if not re.fullmatch('[0-9]{8}', a.day) or not re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run):
        p.error('--day YYYYMMDD and --run of letters, digits, _ and - required')
    import frankie_box_brain as BR
    import frankie_box_classroom_code as K
    _, rules = K.rules()
    rules_witness = dict(file=Path(rules['path']).name, sha256=rules['sha256'], bytes=rules['bytes'], rules=rules['rules'])
    started = time.time()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    import frankie_box_teacher_knowledge as TK
    accumulated_claim_tests = TK.teach_accumulated(a.day, a.search, a.brain, out / 'scientific-knowledge')
    full, view = exchange(a.day, a.run, a.lessons, a.teacher_rows, rules_witness,
                          brain=a.brain, input_path=out / 'learner-knowledge.json')
    written = {}
    for name, doc in (('exchange.json', full), ('exchange-frankie.json', view)):
        data = (json.dumps(doc, indent=1, sort_keys=True) + '\n').encode('utf-8')
        ok, why = write_once(out / name, data)
        if not ok:
            raise SystemExit(why)
        written[name] = dict(path=str(out / name), sha256=sha256_bytes(data), bytes=len(data), existing=bool(why))
    entry = Path(a.brain) / ('%s-exchange' % a.day)
    manifest_path = entry / 'MANIFEST.json'
    have = json.loads(manifest_path.read_bytes()) if manifest_path.is_file() else {}
    brain_reused = any(e.get('sha256') == written['exchange-frankie.json']['sha256'] for e in have.get('entries') or [])
    if not brain_reused:
        BR.write_exchange_entry(a.brain, a.day, out / 'exchange-frankie.json')
    receipt = dict(schema=RECEIPT_SCHEMA, run=a.run, day=a.day, status='complete', exchange=written['exchange.json'],
                   frankie_view=written['exchange-frankie.json'], brain_entry=str(entry), brain_reused=brain_reused,
                   exchange_hash=full['exchange_hash'], counts=full['counts'], listed=full['listed'],
                   teacher_rows=full['sources']['teacher_rows'], teacher_rows_listed=full['sources']['teacher_rows_listed'],
                   lessons=full['sources']['lessons'], jev_withheld=view['jev_withheld'], rules=rules_witness,
                   knowledge_inputs=full.get('knowledge_inputs'),
                   accumulated_claim_tests=accumulated_claim_tests,
                   seconds=round(time.time() - started, 1), at=time.time(), model_calls=0)
    tmp = out / 'receipt.pending'
    tmp.write_text(json.dumps(receipt, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(out / 'receipt.json')
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
