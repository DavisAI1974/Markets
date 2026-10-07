"""The Dipole classroom answered by Frankie's code (Greg, 2026-09-29: "Granite has absolutely nothing to do with
classroom anymore"; SPEC-decouple-granite.md decision 3; knowledge/CLASSROOM_RULES_V3.json).

No model call. Every answer is computed from the model-visible classroom the request carries and is returned in exactly
the shapes frankie_box_classroom.parse_component / parse_summary / parse_correction return, so the repository's
validators, the assembly, the host grade and the correction contract are unchanged. Every text says what it is: a count
or a value computed here, the teacher's own wording quoted as the teacher's, or something this code does not compute
(listed as unknown, never filled in). No average, no smoothing, no normalization of any dipole result: counts,
extremes and the teacher's own coefficients per pair only (rules R04, R05).

TEACH shows the evidence, so the code transcribes and counts it. GUIDED (Greg, 2026-10-06: the lawful TEACH -> GUIDED
progression) still shows every observation, the state counts and the non-present reasons, but withholds each
component's terminal state and first-to-last direction and the whole 171-pair review: the code COMPUTES exactly those
from the visible observations with the teacher's own measurement functions (dipole_classroom._direction, _pearson,
_co_movement, _direction_relation), per component and per pair, and answers in the independent shape the classroom
grades (parse_independent_component). The host key is never read. SOCRATIC and VERIFY withhold the observations
themselves; the runner supplies a separate learner-owned sealed-journal reading. Accumulated findings are applied
before answers. This is source-built, not runtime-verified or independent scientific confirmation.
"""
from __future__ import annotations

import hashlib
import copy
import json
import re
import sys
from pathlib import Path

SCHEMA = 'FRANKIE_BOX_CLASSROOM_CODE_V1'
# V3 = V2 with R17 amended for Granite's active bounded post-class facilitator role (Greg, 2026-10-06)
RULES_PATH = Path(__file__).resolve().parents[3] / 'research/kalshi/frankie_boss/knowledge/CLASSROOM_RULES_V3.json'
RULES_SCHEMA = 'FRANKIE_CLASSROOM_RULES_V3'
STATES = ('PRESENT', 'MISSING', 'INVALID', 'ABLATED')
STATE_MEANING = {
    'PRESENT': 'a measured value at that cursor',
    'MISSING': 'no value was available at that cursor; the teacher\'s recorded reason is kept with it',
    'INVALID': 'a value was produced at that cursor but failed its validity rule; the teacher\'s recorded reason is kept with it',
    'ABLATED': 'the input was deliberately removed at that cursor (ablation); the teacher\'s recorded reason is kept with it',
}
AUTHOR = 'Frankie\'s code (computed; no model)'
COMPOSITION = ('All four classroom modes, answered by Frankie\'s code (no model call). TEACH: state counts, terminal state, '
               'first-to-last PRESENT direction, every observation cursor/state/value and every pair direction are transcribed '
               'from the model-visible pre-message. GUIDED: the same observations are shown but the terminal state, the direction '
               'and the pair review are withheld, so the code computes them from the visible observations with the teacher\'s own '
               'functions (per component, per pair; never from the key). Each narrative states what it is (a count or value '
               'computed by code, the teacher\'s wording quoted as the teacher\'s, or UNKNOWN where the code computes nothing); '
               'pair texts carry the coefficient and the co-movement counts per pair; novel findings are only what a computation '
               'surfaces (a pair whose first-to-last relation and its step counts point different ways), filed as hypotheses; the '
               'SOCRATIC/VERIFY use a separate learner-owned journal reading and apply accumulated findings before answers. '
               'The correction takes the data the teacher shows for each corrected subclaim. Governed by '
               'knowledge/CLASSROOM_RULES_V3.json')
MODES_ANSWERED = ('TEACH', 'GUIDED', 'SOCRATIC', 'VERIFY')
_EVIDENCE_CACHE = {}


class ModeNotAnswerable(ValueError):
    """The classroom mode asks for independent claims the code has no source for (refused with the reason)."""


def rules():
    """The classroom rules file, loaded whole, and its witness for the receipt."""
    data = RULES_PATH.read_bytes()
    value = json.loads(data)
    if value.get('schema') != RULES_SCHEMA or not isinstance(value.get('rules'), list) or not value['rules']:
        raise ValueError(f'{RULES_PATH} is not the classroom rules file ({RULES_SCHEMA})')
    return value, dict(path=str(RULES_PATH), bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                       rules=[r['id'] for r in value['rules']])


def _classroom_math():
    """dipole_classroom from this checkout: the teacher's own measurement functions, loaded through
    frankie_box_classroom.validators() (the torch-free namespace loader the box uses)."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import frankie_box_classroom as C
    return C.validators().classroom


def _evidence(visible):
    """The evidence the code answers from, in the TEACH pre-message's shape (components with terminal state and
    direction, the 171-pair relationship_review), plus `evidence_source` saying where each came from.

    TEACH: the pre-message as shown; the code transcribes.
    GUIDED: the teacher shows every observation, the state counts and the non-present reasons and withholds the
    terminal state, the first-to-last PRESENT direction and the pair review. Those are computed here from the visible
    observations with the teacher's own functions (dipole_classroom._direction, _pearson, _co_movement,
    _direction_relation), per component and per pair (R05); the host key is never read. The result is cached per
    teacher message, so the 19 component answers, the summary and the reproductions read one computation.
    SOCRATIC / VERIFY: the observations are supplied by the runner's learner-owned sealed-day read,
    bound to this request. A missing reading refuses; the host key is never a fallback.
    """
    pre = visible['pre_message']
    mode = pre['mode']
    if mode == 'TEACH':
        return dict(pre, evidence_source='TEACH: states, values, terminal states, directions and the pair review as the '
                                         'teacher shows them, transcribed')
    if mode in ('SOCRATIC', 'VERIFY'):
        own = visible.get('learner_evidence')
        if own is None or own['classroom_binding_hash'] != visible['binding']['classroom_binding_hash']:
            raise ModeNotAnswerable(f'{mode} requires the learner-owned sealed-journal reading; no host key fallback')
        return own['evidence']
    if mode != 'GUIDED':
        raise ModeNotAnswerable(f'unknown classroom mode {mode}')
    cached = _EVIDENCE_CACHE.get(pre.get('teacher_message_hash'))
    if cached is not None:
        return cached
    evidence = _calculate_evidence(pre, 'GUIDED: computed from the visible observations with the existing '
                                       'measurement functions; nothing read from the key')
    _EVIDENCE_CACHE[pre.get('teacher_message_hash')] = evidence
    return evidence


def independent_evidence(visible, snapshot, witness):
    """Bind learner-produced rows to the request, without consulting host answers."""
    math = _classroom_math()
    binding, pre = visible['binding'], visible['pre_message']
    for field in ('source_hash', 'as_of', 'through_cursor', 'request_id', 'cycle_index', 'cycle_count'):
        if snapshot[field] != binding[field]:
            raise ValueError('learner evidence has another ' + field)
    if snapshot['source_snapshot_hash'] != witness['source_snapshot_hash']:
        raise ValueError('learner snapshot differs from its own reading witness')
    if tuple(c['name'] for c in pre['components']) != tuple(snapshot['coverage_columns']):
        raise ValueError('learner evidence does not cover the governed component roster')
    comps = []
    for i, guidance in enumerate(pre['components']):
        ledger = math._dimension_ledger(snapshot, i)
        comps.append(dict(guidance, observations=ledger, state_counts=math._state_counts(ledger)))
    evidence = _calculate_evidence(dict(pre, components=comps),
        'learner-owned sealed-journal reading; same measurement mathematics, no host answer or scientific independence claim')
    return dict(classroom_binding_hash=binding['classroom_binding_hash'], witness=witness, evidence=evidence)


COVERAGE_SCHEMA = 'FRANKIE_CLASSROOM_COVERAGE_V1'
# The producer streams the d6af990 core opens for every shared read. A stream not in a later
# read is listed "not in this read"; that is a thinner picture, never a rejected day.
_D6AF990_STREAMS = ('root.frames', 'root.prices', 'root.structures', 'native.member', 'native.lifecycle')
_COVERAGE_READ_KEYS = {'identity', 'complete', 'source_exhausted', 'presented_inputs', 'interpretation', 'completed_native',
                       'journal', 'sources', 'external_publications', 'completed_sources',
                       'closed_source_without_root_frame', 'unplaceable_input_clocks',
                       # the core's revised reader (eff34d5): coverage, completeness, arithmetic, the iterator's own
                       # outputs accounting, whose journal measurement stood, and the two visible stop/failure records
                       'coverage', 'completeness', 'arithmetic', 'layers', 'absent_layers',
                       'outputs', 'input_verification', 'stopped', 'integrity_failure'}


def source_exhausted(report, *, journal_count=None, record_count=None):
    """Whether one shared read reached the end of its source. Exhaustion is not layer coverage.

    d6af990 records exhaustion as report['complete'], set only after the iterator, the byte/hash/
    count checks and every producer finish ran. The core author is revising report semantics for
    the missing-coverage rule; a later explicit `source_exhausted` flag, or the journal accounting
    equalling the sealed envelope/INPUT counts, is accepted the same way. A missing layer or a
    failed input never reads as non-exhaustion here, and exhaustion never reads as full coverage.
    """
    if not isinstance(report, dict):
        return False
    if report.get('complete') is True or report.get('source_exhausted') is True:
        return True
    journal = report.get('journal') or {}
    return (journal_count is not None and record_count is not None
            and journal.get('entries') == journal_count and journal.get('inputs') == record_count)


def _span_counts(ranges):
    return {reason: sum(int(hi) - int(lo) + 1 for lo, hi in spans) for reason, spans in (ranges or {}).items()}


def coverage_disposition(report, *, journal_count=None, record_count=None):
    """Two separate readings of one shared read: was the whole source read, and what was present.

    Missing-coverage rule (Greg, 2026-10-07): a day or instant is never rejected for missing
    layers, clocks, derived updates or publications; it stays in with a thinner picture whose
    missing/unavailable/stale parts are named. This disposition names them from the core's
    report as it is, counts only. It claims neither that every field entered a target equation
    nor that an absent layer does not exist. Integrity/identity failures raise inside the core
    and the classroom; they never appear here relabelled as coverage.
    """
    if not isinstance(report, dict):
        return dict(schema=COVERAGE_SCHEMA, source_exhausted=False, reason='no shared read report was supplied')
    identity = report.get('identity') or {}
    journal = report.get('journal') or {}
    layers = {name: dict(counts=dict(stream.get('counts') or {}), dispositions=_span_counts(stream.get('dispositions')))
              for name, stream in (report.get('sources') or {}).items()}
    external = identity.get('external') or {}
    publications = report.get('external_publications')
    if external.get('status') == 'attached' and isinstance(publications, dict):
        external_layer = dict(status='attached', presented=publications.get('presented'), rows=publications.get('rows'),
                              not_yet_public={k: len(v) for k, v in (publications.get('not_yet_public') or {}).items()},
                              missing=publications.get('missing'), after_halt=publications.get('after_halt'))
    else:
        external_layer = dict(status=external.get('status'), disposition='external_layer_absent_in_shared_source',
                              listed='no external publication reached any picture of this read')
    return dict(schema=COVERAGE_SCHEMA,
                source_exhausted=source_exhausted(report, journal_count=journal_count, record_count=record_count),
                core_report_complete=report.get('complete'),
                presented_inputs=report.get('presented_inputs'),
                journal=dict(entries=journal.get('entries'), inputs=journal.get('inputs'), extracted=journal.get('extracted'),
                             sealed_journal_count=journal_count, sealed_record_count=record_count,
                             input_dispositions=_span_counts(journal.get('dispositions')),
                             unclosed_instruments=len(journal.get('unclosed_instruments') or [])),
                layers=layers,
                layers_not_in_read=[name for name in _D6AF990_STREAMS if name not in layers],
                # The core author's revised reader records its own dispositions: report['coverage']
                # (layers, absent_layers, present_layers, inputs, all_layers_present), identity
                # ['absent_layers'] and, on an iter_applied read, report['arithmetic'] (present/absent
                # operands by status). They travel verbatim when present; None on a d6af990 report.
                core_coverage=copy.deepcopy(report.get('coverage')),
                core_absent_layers=copy.deepcopy(identity.get('absent_layers')),
                core_arithmetic=copy.deepcopy(report.get('arithmetic')),
                core_completeness=copy.deepcopy(report.get('completeness')),
                # the iterator's own counts (pictures yielded, exact/unclocked/unreadable placements, updates,
                # publications, cursor domains); whose journal hash stood (caller witness or the reader's own read);
                # a consumer stop or an integrity failure as the core recorded it (None when none happened)
                core_outputs=copy.deepcopy(report.get('outputs')),
                core_input_verification=copy.deepcopy(report.get('input_verification')),
                core_stopped=copy.deepcopy(report.get('stopped')),
                core_integrity_failure=copy.deepcopy(report.get('integrity_failure')),
                external=external_layer,
                completed_only=[dict(role=item.get('role'), disposition=item.get('disposition'))
                                for item in (report.get('completed_sources') or [])],
                closed_source_without_root_frame=len(report.get('closed_source_without_root_frame') or []),
                unplaceable_input_clocks=len(report.get('unplaceable_input_clocks') or []),
                not_interpreted=sorted(key for key in report if key not in _COVERAGE_READ_KEYS),
                interpretation=('source_exhausted: every original envelope of the sealed source was read; layers/external: '
                                'which producer rows and publications were present, counted from the read; neither is a claim '
                                'that every field entered a target equation; a previously observed state is last-observed, '
                                'not a new observation; integrity and identity failures raise separately'))


def market_context(visible, timeline, *, save_requested):
    """Read the complete shared view once; retain full pictures at existing evidence anchors.

    Missing-coverage rule (Greg, 2026-10-07): the read exhausts the ordered source, and whatever
    picture the source holds at an anchor's original adapter cursor is retained with its source
    status (applied, failed, unpaired...). An anchor whose cursor has no picture is listed
    `unavailable`; its Dipole value from the teacher rows stands and the market picture at that
    instant is thinner. Nothing is fabricated for it. Exhaustion, layer coverage and integrity are
    reported separately. Same-day identity mismatches still refuse; they are not coverage.
    """
    from research.kalshi.frankie_boss.parallel_teacher import TeacherSaved
    ingest = timeline.source['ingestion_receipt']
    raw = Path(ingest['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ingest['sha256']:
        raise ValueError('identity: shared classroom ingestion receipt differs from its retained source')
    source = json.loads(raw)
    binding = visible['binding']
    if (source['source_prefix_hash'] != binding['source_hash']
            or source['record_count'] - 1 != binding['through_cursor']
            or binding['cycle_index'] != 0 or binding['cycle_count'] != 1):
        # The sealed day's INPUT count includes failed inputs; this is the causal cutoff and
        # source identity of the classroom, not a requirement that every input applied.
        raise ValueError('identity: shared classroom context and the sealed day do not name the same source and whole-day cutoff')
    anchors, wanted = {}, set()
    for component in _evidence(visible)['components']:
        present = [(int(p['cursor']), float(p['value'])) for p in component['observations'] if p['state'] == 'PRESENT']
        chosen = {} if not present else dict(first=present[0], last=present[-1],
            minimum=min(present, key=lambda cv: (cv[1], cv[0])),
            maximum=max(present, key=lambda cv: (cv[1], -cv[0])))
        anchors[component['name']] = {name: dict(adapter_cursor=value[0], value=value[1])
                                      for name, value in chosen.items()}
        wanted.update(value[0] for value in chosen.values())
    pictures, statuses, counts = {}, {}, {}
    # Where the classroom's own pass spends its time (Greg, 2026-10-07: make it run faster, measure first):
    # pictures seen, when the last wanted anchor was retained, and how many pictures followed it. The pass
    # still reads to the end (the published guarantee: one full ordered read, the exhaustion seen by this
    # consumer itself); these numbers let the one-day test say whether that tail is where the time goes.
    import time
    started = time.monotonic()
    seen, last_anchor_seen_at = 0, None
    # All-99 arrivals (Greg, 2026-10-07: the 99 layers combined for Frankie first): what each picture of this
    # one pass carried, counted per registry route (actions, clocks, invalidations, layer updates, frame
    # sections, price row kinds, top-level fields seen). Counts of what was yielded, never of what any
    # equation used; the all-99 list is built from them by all99_coverage().
    arrivals = _Arrivals()
    iterator = timeline.iter_pictures()
    try:
        for item in iterator:
            if save_requested():
                raise TeacherSaved('shared classroom picture read interrupted; no completed reading claimed')
            picture = item['picture']
            status = picture['source_status']
            # The core yields a plain status string (applied, failed, unpaired_...); a structured status is
            # keyed by its sorted JSON. No per-picture JSON encoding on the hot path for the common case.
            key = status if isinstance(status, str) else json.dumps(status, sort_keys=True)
            counts[key] = counts.get(key, 0) + 1
            seen += 1
            arrivals.note(picture, item['evidence'])
            cursor = picture['at']['adapter_cursor']
            if cursor in wanted:
                if cursor in pictures:
                    raise ValueError('identity: shared market holds two original INPUT pictures for one classroom adapter cursor')
                pictures[cursor] = copy.deepcopy(picture)
                # The core's per-instant thinner dict (absent layers, exact clocks, readable record) when present.
                statuses[cursor] = dict(source_status=status, applied_evidence=item['evidence'] is not None,
                                        unpaired_outcomes=picture.get('unpaired_outcomes'),
                                        thinner=copy.deepcopy(picture.get('coverage')))
                if len(pictures) == len(wanted):
                    last_anchor_seen_at = seen
    finally:
        iterator.close()
    read = dict(seconds=round(time.monotonic() - started, 3), pictures_seen=seen, workers=15,
                wanted_anchor_cursors=len(wanted), max_wanted_adapter_cursor=(max(wanted) if wanted else None),
                last_anchor_retained_at_picture=last_anchor_seen_at,
                pictures_after_last_anchor=(seen - last_anchor_seen_at if last_anchor_seen_at is not None else None),
                read_to_end=True,
                hot_path='per picture: status key, anchor membership test, arrivals.note (a few dict increments; '
                         'per update: source name, frame section presence, top-level field names); deepcopy only '
                         'at wanted anchors. The core\'s decode dominates; measure on the one-to-two-minute canary.',
                note='one full ordered read; the tail after the last anchor serves source_status_counts and this '
                     'consumer\'s own view of exhaustion. Measured here so the one-day test can show where the '
                     'classroom\'s time goes before any shortening is considered; no shortening is applied.')
    # Reaching here means the iterator ended without an integrity/identity exception. The core's
    # own exhaustion flag is read beside that fact, never used to reject a thinner day.
    report = copy.deepcopy(timeline.report)
    coverage = coverage_disposition(report, journal_count=timeline.source.get('journal_count'),
                                    record_count=timeline.source.get('record_count'))
    coverage['classroom_iterator_ended'] = True
    if coverage.get('core_coverage') is None:
        # A reader between d6af990 and the core's revised report: carry its layer attributes as read, never inferred.
        for attribute in ('layers', 'absent_layers'):
            if getattr(timeline, attribute, None) is not None:
                coverage['core_' + attribute] = copy.deepcopy(getattr(timeline, attribute))
    unavailable = sorted(wanted - set(pictures))
    for selected in anchors.values():
        for anchor in selected.values():
            cursor = anchor['adapter_cursor']
            if cursor in pictures:
                anchor.update(picture='retained', **statuses[cursor])
            else:
                anchor.update(picture='unavailable',
                              reason='no original INPUT of the exhausted shared source carries this adapter cursor; the '
                                     'Dipole value stands on the teacher rows and the market picture at this instant is thinner')
    opening = source.get('opening_book') if isinstance(source.get('opening_book'), dict) else None
    return dict(schema='FRANKIE_CLASSROOM_SHARED_MARKET_V1', classroom_binding_hash=visible['binding']['classroom_binding_hash'],
                identity=timeline.identity, reader=dict(module='frankie_box_market_timeline',
                    interface='SharedMarketTimeline.iter_pictures', workers=15),
                anchors=anchors, pictures=pictures, report=report,
                source_status_counts=counts, coverage=coverage, read=read,
                arrivals=arrivals.record(),
                # the predecessor bootstrap as the ingestion receipt recorded it (seeded / absent / none recorded);
                # the core yields no opening-state picture element (named as a request to the core author)
                opening_book=(dict(status=opening.get('status'), listed=opening.get('listed'))
                              if opening is not None else dict(status='not_recorded_in_ingestion_receipt')),
                journal_witness=getattr(timeline, 'input_verification', None),
                anchor_pictures=dict(wanted=len(wanted), retained=len(pictures), unavailable=unavailable),
                use='full ordered source read to its end; first/last/min/max PRESENT anchor pictures, each with its source '
                    'status or listed unavailable, supplement unchanged Dipole mathematics',
                limit='no claim that every market field changes a target or is interpreted; no claim that every layer was '
                      'present; no native training')


class ClassroomMarketContext:
    """Actual answer context: complete retained anchors plus access to the full exact source."""
    def __init__(self, calculations, day, retained):
        self.calculations, self.day, self.retained = calculations, day, retained

    def iter_pictures(self):
        from frankie_box_market_timeline import SharedMarketTimeline
        # Efficiency (Greg, 2026-10-07): the sealed journal is measured in THIS process by the per-process,
        # changed-file-aware witness (frankie_box_filehash: one streamed sha256 per unchanged file, keyed on
        # path/device/inode/size/mtime/ctime), so a second reader open in the same process does not re-hash
        # tens of GB. The core still compares the witness to its pin and raises on a mismatch; the pin, the
        # identity and the chained head hash check are unchanged.
        from frankie_box_filehash import witness as measured
        journal = (self.retained.get('identity') or {}).get('journal') or {}
        witness = measured(journal['path']) if journal.get('path') else None
        reader = SharedMarketTimeline(self.calculations, day=self.day, workers=15, input_witness=witness)
        if reader.identity != self.retained['identity']:
            raise ValueError('classroom full market reader changed from its retained selection')
        yield from reader.iter_pictures()

    def component(self, visible, name):
        if self.retained['classroom_binding_hash'] != visible['binding']['classroom_binding_hash']:
            raise ValueError('shared market answer context belongs to another classroom')
        selected = self.retained['anchors'][name]
        pictures = {}
        for anchor in selected.values():
            cursor = anchor['adapter_cursor']
            picture = self.retained['pictures'].get(cursor)
            # An anchor without a picture stays an anchor: its disposition travels, nothing is filled in.
            pictures[str(cursor)] = picture if picture is not None else dict(
                picture='unavailable', adapter_cursor=cursor, reason=anchor.get('reason'))
        coverage = self.retained.get('coverage') or {}
        return dict(reader=self.retained['reader'], identity=self.retained['identity'], anchors=selected, pictures=pictures,
                    coverage=dict(source_exhausted=coverage.get('source_exhausted'),
                                  layers_present=sorted(coverage.get('layers') or {}),
                                  layers_not_in_read=coverage.get('layers_not_in_read'),
                                  core_absent_layers=coverage.get('core_absent_layers'),
                                  external=(coverage.get('external') or {}).get('status')),
                    use=self.retained['use'], limit=self.retained['limit'])

    def summary(self):
        # `read` (wall-clock timing of the pass) is deliberately not here: summary() enters the summary answer
        # text, and a timing is not evidence. It travels through use() for the inspection report only.
        return {key: self.retained.get(key) for key in ('reader', 'identity', 'report', 'source_status_counts', 'coverage',
                                                        'anchor_pictures', 'use', 'limit')}

    def use(self):
        """For the one-day inspection report (Greg, 2026-10-07): what this context received, how each
        component used it, and what stayed partial, missing, stale or completed-only. Receipt-sized: the
        anchors with their dispositions, not the pictures themselves (those sit in the saved reading and
        in each component's evidence text)."""
        coverage = self.retained.get('coverage') or {}
        return dict(schema='FRANKIE_CLASSROOM_SHARED_MARKET_USE_V1',
                    received=dict(reader=self.retained['reader'], identity=self.retained['identity'],
                                  source_exhausted=coverage.get('source_exhausted'),
                                  source_status_counts=self.retained.get('source_status_counts'),
                                  anchor_pictures=self.retained.get('anchor_pictures'),
                                  # where the classroom's own full pass spent its time (None on a reading saved
                                  # before this field existed)
                                  read=self.retained.get('read'),
                                  # whose measurement of the sealed journal stood at the core's open (None on a
                                  # reading saved before this field existed)
                                  journal_witness=self.retained.get('journal_witness'),
                                  opening_book=self.retained.get('opening_book'),
                                  # per-day arrivals of the pass (actions, clocks, layer updates, frame sections,
                                  # price row kinds, fields seen); the all-99 list is derived from these
                                  arrivals=self.retained.get('arrivals')),
                    entered=dict(component_answer=['evidence'], summary_answer=['cycle_summary']),
                    arithmetic='state counts, terminal state, first-to-last direction, Pearson and co-movement use the '
                               'teacher rows only; no shared-picture field is an operand of any Dipole equation',
                    components={name: copy.deepcopy(selected) for name, selected in self.retained['anchors'].items()},
                    partial_missing_stale=dict(
                        input_dispositions=(coverage.get('journal') or {}).get('input_dispositions'),
                        layers_not_in_read=coverage.get('layers_not_in_read'),
                        core_absent_layers=coverage.get('core_absent_layers'),
                        external=coverage.get('external'),
                        unavailable_anchor_cursors=(self.retained.get('anchor_pictures') or {}).get('unavailable'),
                        last_observed_state='each picture\'s last_observed_state keeps its original cursor/clock; it is a '
                                            'previously observed state, never presented as a new observation'),
                    completed_only=coverage.get('completed_only'),
                    limit=self.retained['limit'])


class _Arrivals:
    """Per-day counts of what the shared pictures carried, per all-99 route (one pass, hot path).

    Counts are of yielded evidence only: an update counted here reached the picture; whether any
    equation used it is the consumer's own receipt (the classroom's Dipole arithmetic uses the
    teacher rows only). Field names are top-level keys of each layer's rows, capped per layer so a
    pathological row cannot grow the receipt; the overflow is counted, never dropped silently.
    """
    FRAME_SECTIONS = ('book', 'activity', 'integrity', 'native_frame', 'observation', 'input_records', 'input_record_indices')
    FIELD_CAP = 256

    def __init__(self):
        self.pictures = 0
        self.exact_clocks = 0
        self.readable_record = 0
        self.normalized = 0
        self.actions = {}
        self.action_not_normalized = 0
        self.invalidations = {}
        self.updates = {}
        self.updates_with_known_at = 0
        self.availability_basis = {}
        self.frame_sections = {name: 0 for name in self.FRAME_SECTIONS}
        self.frame_book_full_depth = 0
        self.frame_fifo_queue = 0
        self.price_row_kinds = {}
        self.price_origins = {}
        self.publications = 0
        self.fields_seen = {}
        self.fields_overflow = {}
        self.pictures_with_updates = 0

    def note(self, picture, evidence):
        self.pictures += 1
        thinner = picture.get('coverage') or {}
        if thinner.get('exact_clocks'):
            self.exact_clocks += 1
        if thinner.get('readable_record'):
            self.readable_record += 1
        normalized = evidence.get('normalized') if isinstance(evidence, dict) else None
        if normalized:
            self.normalized += 1
            action = normalized.get('action')
            action = action.decode('ascii', 'replace') if isinstance(action, bytes) else str(action)
            self.actions[action] = self.actions.get(action, 0) + 1
        else:
            self.action_not_normalized += 1
        for item in picture.get('invalidated_state') or ():
            reason = str(item.get('reason'))
            self.invalidations[reason] = self.invalidations.get(reason, 0) + 1
        updates = picture.get('updates') or ()
        if updates:
            self.pictures_with_updates += 1
        for update in updates:
            source = str(update.get('source'))
            if source.startswith('external.'):
                self.publications += 1
                source = 'external'
            self.updates[source] = self.updates.get(source, 0) + 1
            if update.get('known_at_ns') is not None:
                self.updates_with_known_at += 1
            basis = str(update.get('availability_basis'))
            self.availability_basis[basis] = self.availability_basis.get(basis, 0) + 1
            value = update.get('value')
            if not isinstance(value, dict):
                continue
            seen = self.fields_seen.setdefault(source, {})
            for name in value:
                name = str(name)
                if name in seen:
                    seen[name] += 1
                elif len(seen) < self.FIELD_CAP:
                    seen[name] = 1
                else:
                    self.fields_overflow[source] = self.fields_overflow.get(source, 0) + 1
            if source == 'root.frames':
                for name in self.FRAME_SECTIONS:
                    if value.get(name) is not None:
                        self.frame_sections[name] += 1
                book = value.get('book')
                if isinstance(book, dict):
                    full = book.get('bid_levels_full') or book.get('ask_levels_full')
                    if full is not None:
                        self.frame_book_full_depth += 1
                        first = full[0] if isinstance(full, list) and full else None
                        if isinstance(first, dict) and 'fifo_queue' in first:
                            self.frame_fifo_queue += 1
            elif source == 'root.prices':
                provenance = value.get('provenance') or {}
                kind, origin = str(provenance.get('row_kind')), str(provenance.get('origin'))
                self.price_row_kinds[kind] = self.price_row_kinds.get(kind, 0) + 1
                self.price_origins[origin] = self.price_origins.get(origin, 0) + 1

    def record(self):
        return dict(schema='FRANKIE_CLASSROOM_ARRIVALS_V1', pictures=self.pictures, exact_clocks=self.exact_clocks,
                    readable_record=self.readable_record, normalized=self.normalized, actions=dict(self.actions),
                    action_not_normalized=self.action_not_normalized, invalidations=dict(self.invalidations),
                    updates=dict(self.updates), pictures_with_updates=self.pictures_with_updates,
                    updates_with_known_at=self.updates_with_known_at, availability_basis=dict(self.availability_basis),
                    frame_sections=dict(self.frame_sections), frame_book_full_depth=self.frame_book_full_depth,
                    frame_fifo_queue=self.frame_fifo_queue, price_row_kinds=dict(self.price_row_kinds),
                    price_origins=dict(self.price_origins), publications=self.publications,
                    fields_seen={k: dict(v) for k, v in self.fields_seen.items()},
                    fields_overflow=dict(self.fields_overflow), field_cap=self.FIELD_CAP,
                    basis='counts of evidence the shared pictures yielded on this one full pass; not proof that an '
                          'equation consumed a field; absence of an event is a measurement over the exhausted source')


# ------------------------------------------------------------------- the all-99 registry routed into the classroom
# Greg, 2026-10-07: the 99 layers are combined for Frankie FIRST. The retained registry (99 union layers; content
# identity 239a1480...) is named by the retained crosswalk below, pinned in knowledge/CYCLE_CALCULATION_PINS.json.
# Every entry is routed to the picture element of SharedMarketTimeline.iter_pictures() that carries it (and so to the
# component answers through the untrimmed anchor pictures and the full reader), or to its own consumer in this piece
# (controls, knowledge, carry), or named sealed / disabled / output. Roles are not interchangeable numeric layers.
ALL99_SCHEMA = 'FRANKIE_CLASSROOM_ALL99_COVERAGE_V1'
ALL99_REGISTRY = dict(path='research/kalshi/frankie_boss/audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json',
                      bytes=112545, sha256='ece9c624d9969166e81876e7705d0c47054e46b6aa3e5485803a218648184de9',
                      registry_sha256='239a14808850d9cc9ba589165e4263c0e3f11a0c574052f39bfaa133adf296b1',
                      pinned_in='research/kalshi/frankie_boss/knowledge/CYCLE_CALCULATION_PINS.json')
ALL99_ROLES = {'canonical_raw_dbn_mbo': 'raw',
               'order_lifecycle': 'calculation_clock', 'full_book_fifo_queue': 'calculation_clock',
               'microstructure_mechanics': 'calculation_clock', 'legacy_observable_crosswalk': 'calculation_clock',
               'derived_geometry': 'calculation_clock', 'prebirth_opportunity': 'calculation_clock',
               'causal_clocks': 'calculation_clock',
               'binding_common_controls': 'control_knowledge_arm', 'a_clean_overlay': 'control_knowledge_arm',
               'a_memory_overlay': 'control_knowledge_arm', 'current_brain_runtime': 'control_knowledge_arm',
               'frozen_learned_structure': 'control_knowledge_arm', 'corrected_extra_agent_carryforward': 'control_knowledge_arm',
               'sealed_target_timing': 'sealed_answer', 'sealed_step1_answer': 'sealed_answer',
               'provisional_shadow': 'disabled_shadow', 'append_only_outputs': 'append_only_output'}
ALL99_DISPOSITIONS = ('arrived', 'arrived_no_event', 'thin', 'absent', 'completed_only', 'stamped', 'knowledge_consumer',
                      'control_of_orchestrator', 'not_read_by_this_piece', 'retired', 'sealed', 'disabled',
                      'output_analogue', 'output_not_produced_here')
_NATIVE_ABSENT = 'the native member/lifecycle ledgers are the only producer of this layer; they are absent from this ROOT ' \
                 '(experiment ROOT runs with bedrock off: a disabled producer is never activated silently)'
# layer_id -> (group_id, route). route kinds:
#   picture: via = picture element; layer = core layer that carries it (None = the INPUT envelope itself); probe = an
#            arrivals counter; thin_via/thin_layer = a partial carrier used when the named layer is absent
#   consumer / control / not_read / retired / stamped / completed / sealed / disabled / output
def _p(group, via, probe, layer=None, note=None, thin_via=None, thin_layer=None):
    return group, dict(kind='picture', via=via, probe=probe, layer=layer, note=note, thin_via=thin_via, thin_layer=thin_layer)


ALL99_ROUTES = {
    # raw (6)
    'canonical_sep_nov_2021_dbn_mbo_objects': _p('canonical_raw_dbn_mbo', 'identity.journal (the sealed container pin) and source_binding.source (the DBN partitions)', 'pictures'),
    'october_first_source_window': _p('canonical_raw_dbn_mbo', 'source_binding trading_day / record_count; coverage.journal counts over the exhausted source', 'pictures'),
    'canonical_predecessor_bootstrap_objects': _p('canonical_raw_dbn_mbo', 'ingestion receipt opening_book; root.prices rows with provenance.origin=open_group_before_this_source', 'opening', layer='root.prices',
                                                  note='the core yields no opening-state picture element; the opening status is read from the ingestion receipt (request to the core author)'),
    'native_acmrtfn_messages': _p('canonical_raw_dbn_mbo', 'every INPUT picture: original_input (the sealed record) and original_applied.normalized.action', 'actions'),
    'snapshot_bootstrap_reset_messages': _p('canonical_raw_dbn_mbo', 'action R inputs: invalidated_state reason=reset at the picture; actions.R', 'invalidations.reset'),
    'raw_source_identity_provenance_clocks_integrity': _p('canonical_raw_dbn_mbo', 'at.ts_event_ns / ts_recv_ns / raw clocks, identity pins, coverage.exact_clocks; root.frames.integrity', 'exact_clocks'),
    # order lifecycle (9)
    'order_lifecycle_adds': _p('order_lifecycle', 'actions.A at INPUT pictures; root.frames.observation (every resting order) and book at each group close', 'actions.A', layer='root.frames', thin_via='actions.A only (frame spool absent)'),
    'order_lifecycle_cancels': _p('order_lifecycle', 'actions.C at INPUT pictures; root.frames.observation / book at each group close', 'actions.C', layer='root.frames', thin_via='actions.C only (frame spool absent)'),
    'order_lifecycle_modifies': _p('order_lifecycle', 'actions.M at INPUT pictures; root.frames.observation / book at each group close', 'actions.M', layer='root.frames', thin_via='actions.M only (frame spool absent)'),
    'order_lifecycle_replaces': _p('order_lifecycle', 'actions.M (the pinned producer folds replace into _modify); root.frames.observation / book', 'actions.M', layer='root.frames', thin_via='actions.M only (frame spool absent)'),
    'order_lifecycle_trades': _p('order_lifecycle', 'actions.T at INPUT pictures; root.prices rows row_kind=trade (the legacy control row of a T)', 'actions.T', layer='root.prices', thin_via='actions.T only (price spool absent)'),
    'order_lifecycle_fills': _p('order_lifecycle', 'actions.F at INPUT pictures; the fill_disposition recalculation is native', 'actions.F', layer='native.member', thin_via='actions.F at INPUT pictures and root.frames.observation', thin_layer='root.frames'),
    'order_lifecycle_clears': _p('order_lifecycle', 'actions.R / invalidated_state reason=reset; the clear observation is native', 'invalidations.reset', layer='native.member', thin_via='invalidated_state reason=reset and root.frames.integrity', thin_layer='root.frames'),
    'order_identity_transitions': _p('order_lifecycle', 'root.structures rows (describe_structure at each group close)', 'updates.root.structures', layer='root.structures'),
    'contract_session_roll_state': _p('order_lifecycle', 'at.session_id / source_member_index and invalidated_state reason=source_scope_changed; ExchangeSessionRule rows are native', 'invalidations.source_scope_changed', layer='native.member', thin_via='at.session_id / source_member_index on every picture and source_scope_changed invalidations', thin_layer=None),
    # full book / FIFO (8)
    'full_bid_ask_depth': _p('full_book_fifo_queue', 'root.frames.book.bid_levels_full / ask_levels_full at each group close', 'frame_book_full_depth', layer='root.frames'),
    'price_level_and_order_counts': _p('full_book_fifo_queue', 'root.frames.book (*_price_level_count_full, *_order_count_full, bid/ask_levels)', 'frame_sections.book', layer='root.frames'),
    'fifo_queues': _p('full_book_fifo_queue', 'root.frames.book.*_levels_full[i].fifo_queue[j]', 'frame_fifo_queue', layer='root.frames'),
    'queue_age_and_survival': _p('full_book_fifo_queue', 'root.frames.book.*_levels_full[i].fifo_queue[j] (priority stamp / age) and observation', 'frame_fifo_queue', layer='root.frames'),
    'queue_concentration': _p('full_book_fifo_queue', 'root.frames.book.*_levels_full[i].fifo_queue[j]', 'frame_fifo_queue', layer='root.frames'),
    'orders_and_volume_ahead': _p('full_book_fifo_queue', 'root.frames.book.*_levels_full[i].fifo_queue[j] (orders / volume ahead)', 'frame_fifo_queue', layer='root.frames'),
    'spread_and_depth_imbalance': _p('full_book_fifo_queue', 'root.frames.book (spread, mid, depth_imbalance_n / _full, bid/ask_depth_full)', 'frame_sections.book', layer='root.frames'),
    'complete_state_reset_bootstrap_receipts': _p('full_book_fifo_queue', 'invalidated_state reason=reset and root.frames.integrity; the enriched receipts are native', 'invalidations.reset', layer='native.member', thin_via='invalidated_state reason=reset and root.frames.integrity', thin_layer='root.frames'),
    # microstructure (7)
    'mechanics_actions_by_side_and_level': _p('microstructure_mechanics', 'root.frames.activity (the rolling activity window at each group close)', 'frame_sections.activity', layer='root.frames'),
    'aggressor_and_native_signed_flow': _p('microstructure_mechanics', 'root.frames.activity (signed flow in the rolling window)', 'frame_sections.activity', layer='root.frames'),
    'depletion_and_replenishment': _p('microstructure_mechanics', 'native replay driver replenishment rows', 'updates.native.member', layer='native.member', thin_via='root.frames.activity / book', thin_layer='root.frames'),
    'resilience_and_recovery': _p('microstructure_mechanics', 'native replay driver absorption rows', 'updates.native.member', layer='native.member', thin_via='root.frames.activity / book', thin_layer='root.frames'),
    'churn_and_queue_turnover': _p('microstructure_mechanics', 'root.frames.activity (rolling window)', 'frame_sections.activity', layer='root.frames'),
    'price_and_book_path': _p('microstructure_mechanics', 'native book regime rows', 'updates.native.member', layer='native.member', thin_via='root.prices rows and root.frames.book at each group close', thin_layer='root.prices'),
    'missingness_and_integrity_flags': _p('microstructure_mechanics', 'root.frames.integrity and the core\'s coverage dispositions on every picture', 'frame_sections.integrity', layer='root.frames'),
    # legacy crosswalk (5)
    'legacy_price': _p('legacy_observable_crosswalk', 'root.prices rows (row_kind trade / projection_at_event_group_end, V2 provenance)', 'updates.root.prices', layer='root.prices'),
    'legacy_native_signed_flow': ('legacy_observable_crosswalk', dict(kind='completed', via='derive.json layer legacy_native_signed_flow (completed_sources): post-stream aggregate', note='no exact contributing-cursor provenance under reversing clocks; explicitly completed-only until it exists')),
    'legacy_per_second_roll20': ('legacy_observable_crosswalk', dict(kind='completed', via='derive.json layer legacy_per_second_roll20 (completed_sources): post-stream aggregate', note='no exact contributing-cursor provenance under reversing clocks; explicitly completed-only until it exists')),
    'legacy_book_imbalance': _p('legacy_observable_crosswalk', 'root.prices rows (the legacy control row carries the book imbalance fields; see fields_seen[root.prices])', 'updates.root.prices', layer='root.prices'),
    'legacy_structure_observables': _p('legacy_observable_crosswalk', 'root.structures rows (describe_structure)', 'updates.root.structures', layer='root.structures'),
    # derived geometry (8)
    'derived_roll20_and_dipole_state': ('derived_geometry', dict(kind='dipole', via='the teacher rows: the Dipole component observations the classroom computes on (every component, every cursor); roll20 itself is completed-only', note='the classroom\'s own curriculum; the one all-99 layer that is the target arithmetic\'s operand')),
    'derived_d_family_geometry': _p('derived_geometry', 'root.structures rows (describe_structure)', 'updates.root.structures', layer='root.structures'),
    'derived_open_world_predecessor_state': _p('derived_geometry', 'root.structures rows (describe_structure)', 'updates.root.structures', layer='root.structures'),
    'derived_ancestry_gaps': _p('derived_geometry', 'native lifecycle rows (LineageGraph)', 'updates.native.lifecycle', layer='native.lifecycle'),
    'derived_unresolved_age_chain_trajectory': _p('derived_geometry', 'native lifecycle rows (episode retention)', 'updates.native.lifecycle', layer='native.lifecycle'),
    'derived_price_flow_book_paths': _p('derived_geometry', 'native book regime rows', 'updates.native.member', layer='native.member', thin_via='root.prices rows and root.frames.book / activity', thin_layer='root.prices'),
    'derived_v4_mechanics_fifo_features': _p('derived_geometry', 'native window extras', 'updates.native.member', layer='native.member', thin_via='root.frames.activity and fifo_queue', thin_layer='root.frames'),
    'derived_feature_availability_timestamps': _p('derived_geometry', 'every update\'s known_at_ns / availability_basis; the native member clock row is absent', 'updates_with_known_at', layer=None, note='carried on every update of every present layer'),
    # prebirth (5)
    'prebirth_predecessor_at_risk_state': _p('prebirth_opportunity', 'native replay driver candidate rows', 'updates.native.member', layer='native.member'),
    'prebirth_unresolved_chain_extension_state': _p('prebirth_opportunity', 'native lifecycle rows (LineageGraph)', 'updates.native.lifecycle', layer='native.lifecycle'),
    'prebirth_ancestry_successor_opportunity': _p('prebirth_opportunity', 'native lifecycle rows (lineage signature)', 'updates.native.lifecycle', layer='native.lifecycle'),
    'prebirth_stopped_chain_false_context_controls': _p('prebirth_opportunity', 'native recognition rows', 'updates.native.lifecycle', layer='native.lifecycle'),
    'prebirth_negative_opportunity_cases': _p('prebirth_opportunity', 'native recognition rows', 'updates.native.lifecycle', layer='native.lifecycle'),
    # causal clocks (7)
    'clock_event_time': _p('causal_clocks', 'at.ts_event_ns and raw_event_clock on every picture', 'exact_clocks'),
    'clock_receive_time': _p('causal_clocks', 'at.ts_recv_ns and raw_receive_clock on every picture', 'exact_clocks'),
    'clock_event_known_by': _p('causal_clocks', 'at.publication_frontier_ns (running max receive clock) on every picture', 'exact_clocks'),
    'clock_feature_availability': _p('causal_clocks', 'every update\'s known_at_ns and availability_basis', 'updates_with_known_at', layer=None),
    'clock_prospective_discovery_confirmation': _p('causal_clocks', 'native recognition call records', 'updates.native.lifecycle', layer='native.lifecycle'),
    'clock_model_evaluation': _p('causal_clocks', 'native member clock row', 'updates.native.member', layer='native.member'),
    'clock_lock_time': ('causal_clocks', dict(kind='stamped', via='the classroom binding: as_of and through_cursor (the whole-day causal cutoff) stamped by this piece', note='PRINCIPAL_STAMPED in the registry; here the cutoff is the sealed day\'s record_count - 1')),
    # binding controls (4)
    'controlling_rt_mission': ('binding_common_controls', dict(kind='consumer', via='the experiment directive (EXPERIMENT_DIRECTIVE_V1) loaded whole and witnessed', consumer='directive')),
    'native_calculation_contract': ('binding_common_controls', dict(kind='consumer', via='source_binding.shared_market_policy and the ROOT\'s native_calculation_policy (identity-checked at open)', consumer='policy')),
    'anchored_knowledge_manifest': ('binding_common_controls', dict(kind='consumer', via='learner-knowledge.json: the documents and versions this classroom selected at its boundary', consumer='knowledge')),
    'selected_same_arm_profile': ('binding_common_controls', dict(kind='control', via='the orchestrator plan names the classroom-arm day; this piece records the classroom mode and binding it was given')),
    # overlays (4): Memory A retired (Greg, 2026-09-27); A-clean NOT_APPLICABLE in the registry
    'a_clean_promoted_positive_capsule': ('a_clean_overlay', dict(kind='retired', via='A-clean overlay: NOT_APPLICABLE in the registry; Memory A / A-clean retired (Greg, 2026-09-27)')),
    'a_memory_promoted_positive_capsule': ('a_memory_overlay', dict(kind='retired', via='Memory A retired (Greg, 2026-09-27); H06-H08 historical / not_bound')),
    'a_memory_prior_lessons_package': ('a_memory_overlay', dict(kind='retired', via='Memory A retired (Greg, 2026-09-27)')),
    'a_memory_prior_package_proof': ('a_memory_overlay', dict(kind='retired', via='Memory A retired (Greg, 2026-09-27); DEGENERATE_PROOF_SAME_AS_SUBJECT in the registry')),
    # current brain runtime (5)
    'authoritative_s135_construction': ('current_brain_runtime', dict(kind='not_read', via='native A-arm knowledge delivery; no experiment classroom consumer. The lawful knowledge read today is listed in learner-knowledge.json')),
    'complete_s105_9_brain': ('current_brain_runtime', dict(kind='not_read', via='the Kalshi NG brain is not an input of the experiment classroom (Frankie\'s brain entries under /opt/frankie-box/brain are)')),
    'doctrine_reasoning_play_index_evidence': ('current_brain_runtime', dict(kind='not_read', via='native A-arm knowledge delivery; no experiment classroom consumer')),
    'lawful_prior_session_carry': ('current_brain_runtime', dict(kind='consumer', via='PREVIOUS classroom carry (history.json / post-grade.json pins; correction ids only, R10) and the brain entries before this boundary', consumer='carry')),
    'october_outcome_wall_enforcement': ('current_brain_runtime', dict(kind='consumer', via='rules R02 (no outcome after the cutoff), the binding through_cursor, the day file AsOfReader cutoff; same-day teacher/school answers listed excluded by lane_state', consumer='rules')),
    # frozen learned structure (9) and carry-forward (1): the registry's files are not read; the experiment's learned
    # structures are the learner documents and school files, checked by stage_knowledge_reproduction / school_reproduction
    'learned_d_structures_and_families': ('frozen_learned_structure', dict(kind='not_read', via='registry file not read; analogue consumer: stage_knowledge_reproduction / school_reproduction over the listed documents', consumer='knowledge')),
    'learned_dipoles_and_geometry': ('frozen_learned_structure', dict(kind='not_read', via='registry file not read; analogue consumer: stage_knowledge_reproduction / school_reproduction', consumer='knowledge')),
    'learned_pair_triplet_recurrence': ('frozen_learned_structure', dict(kind='not_read', via='registry file not read; analogue consumer: stage_knowledge_reproduction / school_reproduction', consumer='knowledge')),
    'learned_chains_extensions_reappearances_ancestry': ('frozen_learned_structure', dict(kind='not_read', via='registry file not read; analogue consumer: stage_knowledge_reproduction / school_reproduction', consumer='knowledge')),
    'phase1_discoveries_structural_falsifiers': ('frozen_learned_structure', dict(kind='not_read', via='registry file not read; analogue consumer: stage_knowledge_reproduction / school_reproduction', consumer='knowledge')),
    'phase2_findings_modules_timing_pox_negatives': ('frozen_learned_structure', dict(kind='not_read', via='registry file not read; analogue consumer: stage_knowledge_reproduction / school_reproduction', consumer='knowledge')),
    'predecessor_ancestry_unresolved_chain_state': ('frozen_learned_structure', dict(kind='not_read', via='registry file not read; analogue consumer: stage_knowledge_reproduction / school_reproduction', consumer='knowledge')),
    'historical_timing_lifespan_context': ('frozen_learned_structure', dict(kind='not_read', via='registry file not read; analogue consumer: stage_knowledge_reproduction / school_reproduction', consumer='knowledge')),
    'learned_structure_proposal_index_material': ('frozen_learned_structure', dict(kind='not_read', via='registry file not read; analogue consumer: stage_knowledge_reproduction / school_reproduction', consumer='knowledge')),
    'extra_agent_corrected_information_and_gap_diagnoses': ('corrected_extra_agent_carryforward', dict(kind='not_read', via='registry file not read; the experiment\'s checked corrections reach this classroom through frankie_box_experiment_review.require_current (a stale input refuses visibly)', consumer='knowledge')),
    # sealed (9)
    'later_outcome_reveal': ('sealed_target_timing', dict(kind='sealed', via='never read; no timeline path; R02')),
    'target_ground_truth_onset_time': ('sealed_target_timing', dict(kind='sealed', via='never read; no timeline path; R02')),
    'step1_existing_october_seconds': ('sealed_step1_answer', dict(kind='sealed', via='never read; the classroom\'s own answer wall is the host key, never read by this code')),
    'step1_populations': ('sealed_step1_answer', dict(kind='sealed', via='never read')),
    'step1_crosswalks': ('sealed_step1_answer', dict(kind='sealed', via='never read')),
    'step1_target_membership_receipts': ('sealed_step1_answer', dict(kind='sealed', via='never read')),
    'step1_labels_and_classifications': ('sealed_step1_answer', dict(kind='sealed', via='never read')),
    'step1_result_prefixes': ('sealed_step1_answer', dict(kind='sealed', via='never read')),
    'step1_reconciliation_outputs': ('sealed_step1_answer', dict(kind='sealed', via='never read')),
    # disabled shadows (2)
    's137_cognitive_shadow_runtime': ('provisional_shadow', dict(kind='disabled', via='disabled by the existing policy; not activated')),
    'hipporag_associative_retrieval': ('provisional_shadow', dict(kind='disabled', via='disabled by the existing policy; not activated')),
    # append-only outputs (10): the native principal's outputs; this piece's analogue output is named where one exists
    'output_state_and_state_delta_movie': ('append_only_outputs', dict(kind='output', via='native principal output; this piece produces no state movie')),
    'output_frankie_reasoning_movie': ('append_only_outputs', dict(kind='output', via='native principal output; this piece is code with no model and no reasoning movie; private reasoning is withheld (R09)')),
    'output_probability_movie': ('append_only_outputs', dict(kind='output', via='native principal output; this piece produces no probabilities')),
    'output_candidate_discoveries': ('append_only_outputs', dict(kind='output', via='analogue: the classroom\'s novel findings', outputs=('novel-findings.json', 'external-novel-findings.json'))),
    'output_first_locks_and_no_locks': ('append_only_outputs', dict(kind='output', via='native principal output; this piece locks nothing')),
    'output_negative_sparse_inconclusive_ledger': ('append_only_outputs', dict(kind='output', via='analogue: non-PRESENT observations and UNRESOLVED pairs in the component answers', outputs=('code-answers.json',))),
    'output_knowledge_retrieval_receipts': ('append_only_outputs', dict(kind='output', via='analogue: the learner knowledge selection', outputs=('learner-knowledge.json',))),
    'output_provider_invocation_response_receipts': ('append_only_outputs', dict(kind='output', via='no provider: model_calls=0 on this piece')),
    'output_answer_wall_access_receipts': ('append_only_outputs', dict(kind='output', via='analogue: the receipt records that the host key is never read (independent_scientific_verification=False; grading is the host\'s)', outputs=('receipt.json',))),
    'output_source_state_manifest_code_model_run_hashes': ('append_only_outputs', dict(kind='output', via='analogue: the receipt\'s received pins, producers and brain manifest', outputs=('receipt.json',))),
}


def _probe(arrivals, name):
    """An arrivals counter: `counter` or `table.key` (the key may itself contain dots, e.g. updates.root.frames).

    None when no arrivals record exists; 0 when the record exists and holds no such key (no event of that
    kind was yielded on the exhausted source: a measurement, not a filled-in zero)."""
    if not isinstance(arrivals, dict):
        return None
    head, _, rest = name.partition('.')
    node = arrivals.get(head)
    if not rest:
        if isinstance(node, dict):          # a table probe (e.g. actions): every event of the table
            return sum(v for v in node.values() if isinstance(v, int))
        return node if isinstance(node, int) else (0 if node is None else None)
    if not isinstance(node, dict):
        return None
    value = node.get(rest)
    return value if isinstance(value, int) else (0 if value is None else None)


def all99_coverage(shared, consumers, *, repo_root):
    """The per-day all-99 list: every registry entry with its role, route and disposition on this day.

    `shared` is market_context's retained reading (None on a legacy no-policy source); `consumers` names
    this piece's own knowledge/control inputs (directive, rules, policy, knowledge documents, carry,
    binding, mode, dipole components). Nothing here is an operand: it is the account of what reached
    the pictures the component answers compute beside, what reached its own consumer, and what did not.
    """
    registry_path = Path(repo_root) / ALL99_REGISTRY['path']
    registry = dict(ALL99_REGISTRY, status='absent', layers_in_file=None)
    file_layers = {}
    if registry_path.is_file():
        raw = registry_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        registry.update(status=('pinned' if (len(raw), digest) == (ALL99_REGISTRY['bytes'], ALL99_REGISTRY['sha256'])
                                else 'integrity: retained crosswalk bytes differ from their pin (separate visible failure; '
                                     'the route table below is this code\'s own)'),
                        measured=dict(bytes=len(raw), sha256=digest))
        try:
            body = json.loads(raw)
            file_layers = {x['layer_id']: x for x in body.get('layers') or [] if isinstance(x, dict) and x.get('layer_id')}
            registry.update(layers_in_file=len(file_layers), file_registry_sha256=body.get('registry_sha256'),
                            registry_matches=(body.get('registry_sha256') == ALL99_REGISTRY['registry_sha256']))
        except ValueError as error:
            registry.update(status='unreadable: ' + str(error))
    coverage = (shared or {}).get('coverage') or {}
    present = set(coverage.get('layers') or {})                      # streams the core opened on this read
    if (coverage.get('external') or {}).get('status') == 'attached':
        present.add('external')
    core_reasons = (coverage.get('core_coverage') or {}).get('layers') or {}   # the core's own absent reasons
    core_layers = {}
    for name in ('root.frames', 'root.prices', 'root.structures', 'native.member', 'native.lifecycle', 'external'):
        if shared is None:
            core_layers[name] = dict(status='absent', reason='no shared market policy on this ROOT; the classroom read no shared picture')
        elif name in present:
            core_layers[name] = dict(status='present')
        else:
            recorded = core_reasons.get(name) if isinstance(core_reasons.get(name), dict) else {}
            core_layers[name] = dict(status='absent', reason=recorded.get('reason') or (
                _NATIVE_ABSENT if name.startswith('native.') else 'the core listed this layer absent (no pinned spool / no day file)'))
    arrivals = (shared or {}).get('arrivals') if shared else None
    entries, counts, requests = [], {}, []
    for layer_id, (group, route) in ALL99_ROUTES.items():
        role = ALL99_ROLES[group]
        entry = dict(layer=layer_id, group=group, role=role, route=route['via'],
                     registry_status=(file_layers.get(layer_id) or {}).get('status'),
                     registry_policy=(file_layers.get(layer_id) or {}).get('policy'))
        kind = route['kind']
        if kind == 'picture':
            carrier = route.get('layer')
            if shared is None:
                entry.update(disposition='absent', reason='no shared market policy on this ROOT; no picture was read',
                             consumer='component_answer evidence (anchor pictures) / full reader')
            elif route['probe'] == 'opening':
                # the predecessor bootstrap: read from the ingestion receipt (the core yields no opening element) plus
                # any price rows the opening state carried in; judged before the price-spool presence check
                opening = (shared.get('opening_book') or {})
                rows = _probe(arrivals, 'price_origins.open_group_before_this_source')
                if opening.get('status') == 'seeded' or (rows or 0) > 0:
                    entry.update(disposition='arrived', count=rows, opening_book=opening)
                elif opening.get('status') == 'absent':
                    entry.update(disposition='thin', reason=opening.get('listed') or 'the ingest had no opening book',
                                 opening_book=opening, count=rows)
                else:
                    entry.update(disposition='thin', reason='opening state not recorded in the ingestion receipt',
                                 opening_book=opening, count=rows)
                entry['consumer'] = 'component_answer evidence (anchor pictures) / full reader'
            elif carrier is not None and core_layers[carrier]['status'] == 'absent':
                thin_layer = route.get('thin_layer')
                if route.get('thin_via') and (thin_layer is None or core_layers[thin_layer]['status'] == 'present'):
                    count = _probe(arrivals, route['probe'])
                    entry.update(disposition='thin', reason=core_layers[carrier]['reason'],
                                 thin_carrier=route['thin_via'], count=count)
                else:
                    entry.update(disposition='absent', reason=core_layers[carrier]['reason'])
                entry['consumer'] = 'component_answer evidence (anchor pictures) / full reader'
            else:
                count = _probe(arrivals, route['probe'])
                if count is None:
                    entry.update(disposition='absent', reason='the retained reading carries no arrivals record for this probe (reading saved before this field existed)')
                elif count > 0:
                    entry.update(disposition='arrived', count=count)
                else:
                    entry.update(disposition='arrived_no_event', count=0,
                                 reason='carrier present; no event of this kind in the exhausted source on this day (a measurement, not a zero filled in)')
                entry['consumer'] = 'component_answer evidence (anchor pictures) / full reader'
            if route.get('note'):
                entry['note'] = route['note']
        elif kind == 'completed':
            listed = [item for item in ((shared or {}).get('coverage') or {}).get('completed_only') or [] if item.get('role') == layer_id]
            entry.update(disposition='completed_only', note=route['note'], listed=listed or None,
                         consumer='summary_answer (completed_sources dispositions only; values not yielded)')
        elif kind == 'dipole':
            entry.update(disposition='arrived', count=consumers.get('dipole_components'), note=route['note'],
                         consumer='component_answer / summary_answer (the Dipole arithmetic: state counts, direction, Pearson, co-movement)')
        elif kind == 'stamped':
            entry.update(disposition='stamped', binding=consumers.get('binding'), note=route['note'], consumer='every answer (the causal cutoff)')
        elif kind == 'consumer':
            entry.update(disposition='knowledge_consumer', consumer=route['consumer'], detail=consumers.get(route['consumer']))
        elif kind == 'control':
            entry.update(disposition='control_of_orchestrator', mode=consumers.get('mode'), binding=consumers.get('binding'))
        elif kind == 'not_read':
            entry.update(disposition='not_read_by_this_piece', consumer=route.get('consumer'),
                         detail=consumers.get(route['consumer']) if route.get('consumer') else None)
        elif kind == 'retired':
            entry.update(disposition='retired')
        elif kind == 'sealed':
            entry.update(disposition='sealed')
        elif kind == 'disabled':
            entry.update(disposition='disabled')
        elif kind == 'output':
            entry.update(disposition='output_analogue' if route.get('outputs') else 'output_not_produced_here',
                         outputs=list(route.get('outputs') or ()))
        else:
            raise ValueError('unknown all-99 route kind ' + kind)
        if entry['disposition'] not in ALL99_DISPOSITIONS:
            raise ValueError('unknown all-99 disposition ' + entry['disposition'])
        counts[entry['disposition']] = counts.get(entry['disposition'], 0) + 1
        entries.append(entry)
    by_role = {}
    for entry in entries:
        by_role.setdefault(entry['role'], {})
        by_role[entry['role']][entry['disposition']] = by_role[entry['role']].get(entry['disposition'], 0) + 1
    # Entries the core does not yield (requests to the core author, workflow_reports); never filled in here.
    requests.append(dict(file='deploy/aws/box/frankie_box_market_timeline.py', function='SharedMarketTimeline.__init__ / iter_pictures',
                         entry='canonical_predecessor_bootstrap_objects',
                         what='yield the opening adapter state (opening-book pin, seeded / absent) as an identity element and the initial '
                              'last_observed_state disposition, so the predecessor bootstrap is a picture element rather than an ingestion-receipt field read here'))
    requests.append(dict(file='deploy/aws/box/frankie_box_market_timeline.py', function='SharedMarketTimeline.iter_pictures',
                         entry='legacy_native_signed_flow / legacy_per_second_roll20',
                         what='the per-second aggregates are yielded as completed_sources metadata only; their values could enter the '
                              'picture once an exact contributing-cursor provenance exists (blocked on provenance, not on the reader)'))
    native_absent = [e['layer'] for e in entries if e.get('disposition') in ('absent', 'thin') and
                     (ALL99_ROUTES[e['layer']][1].get('layer') or '').startswith('native.')]
    unrouted = sorted(set(file_layers) - set(ALL99_ROUTES))
    unlisted = sorted(set(ALL99_ROUTES) - set(file_layers)) if file_layers else None
    return dict(schema=ALL99_SCHEMA, registry=registry, routed=len(entries), counts=counts, by_role=by_role,
                core_layers=core_layers, entries=entries, requests=requests,
                native_layers_absent_or_thin=native_absent,
                unrouted_in_file=unrouted, routed_not_in_file=unlisted,
                decision_open=('%d layers are carried only by the native member/lifecycle ledgers, which the experiment ROOT does not '
                               'produce (bedrock off). Their instants stay in the picture, thinner; producing them is a plan/policy '
                               'decision for Greg, never a silent activation here.' % len(native_absent)),
                rule='every entry listed with a disposition; missing coverage thins the day and never rejects it; roles are not '
                     'interchangeable numeric layers; sealed answers stay sealed; nothing is fabricated to make an entry arrive',
                limit='a counted arrival is evidence yielded to the pictures beside the component answers (and to the full reader), '
                      'not proof that a Dipole equation used it; the Dipole arithmetic uses the teacher rows only')


def _exact_market_text(value):
    """Carry all original fields, bytes and float bits; never numpy/repr truncation."""
    from research.kalshi.frankie_boss.c15_journal import SerializedObservation, pack
    def encode(item):
        if isinstance(item, SerializedObservation):
            return encode(item.materialize())
        if isinstance(item, dict):
            # Reports can key dispositions by integer instrument identity. Preserve
            # key type explicitly instead of letting JSON silently stringify it.
            return ['mapping', [[pack(key), encode(child)] for key, child in item.items()]]
        if isinstance(item, (tuple, list)):
            return ['tuple' if isinstance(item, tuple) else 'list', [encode(child) for child in item]]
        return pack(item)
    return json.dumps(dict(encoding='typed mapping entries; scalar tags c15_journal.pack', complete_value=encode(value)),
                      separators=(',', ':'))


def _calculate_evidence(pre, origin):
    """One unchanged per-component/per-pair calculation for every lawful observation source."""
    math = _classroom_math()
    comps, ledgers, directions = [], {}, {}
    for comp in pre['components']:
        ledger = [dict(cursor=int(p['cursor']), state=p['state'], value=p['value'], raw_reason=p.get('raw_reason'))
                  for p in comp['observations']]
        if not ledger:
            raise ValueError(f'{comp["name"]}: no lawful observation to compute from')
        counts = {s: sum(p['state'] == s for p in ledger) for s in STATES}
        if {s: int(comp['state_counts'][s]) for s in STATES} != counts:
            raise ValueError(f'{comp["name"]}: the shown state counts differ from the shown observations')
        direction = math._direction(ledger)
        last = ledger[-1]
        ledgers[comp['name']], directions[comp['name']] = ledger, direction
        comps.append(dict(comp, terminal_state=last['state'], terminal_value=last['value'],
                          terminal_reason=last.get('raw_reason'), first_to_last_present_direction=direction))
    names = [c['name'] for c in comps]
    review = []
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            review.append(dict(left=left, right=right,
                               direction_relation=math._direction_relation(directions[left], directions[right]),
                               correlation=math._pearson(ledgers[left], ledgers[right]),
                               co_movement=math._co_movement(ledgers[left], ledgers[right]),
                               interpretation_limit='DESCRIPTIVE_WITHIN_CAUSAL_WINDOW_NOT_CAUSATION_OR_FUTURE_PREDICTION',
                               computed_by=AUTHOR))
    return dict(pre, components=comps, relationship_review=review, evidence_source=origin)


def _component_evidence(visible, name):
    for comp in _evidence(visible)['components']:
        if comp['name'] == name:
            return comp
    raise KeyError(name)


def _basis(visible):
    """How a relation / direction is attributed in the texts: the teacher's (TEACH) or computed here (GUIDED)."""
    return ('Dipole\'s relation' if visible['pre_message']['mode'] == 'TEACH' else
            'relation computed by Frankie\'s code from its lawful current observations')


def _observation_note(p):
    if p['state'] == 'PRESENT':
        return f'{AUTHOR}: cursor {int(p["cursor"])} PRESENT = {_num(p["value"])}'
    return f'{AUTHOR}: cursor {int(p["cursor"])} {p["state"]} ({p.get("raw_reason") or "no reason recorded"})'


def _num(value):
    return repr(float(value))


def _steps(present):
    """Counts of how consecutive PRESENT values moved: rises, falls, unchanged."""
    rises = falls = same = 0
    for (_, a), (_, b) in zip(present, present[1:]):
        if b > a:
            rises += 1
        elif b < a:
            falls += 1
        else:
            same += 1
    return rises, falls, same


def _reasons(comp):
    found = {}
    for p in comp['observations']:
        if p['state'] != 'PRESENT':
            key = (p['state'], p.get('raw_reason') or '(no reason recorded)')
            found[key] = found.get(key, 0) + 1
    return found


def _knowledge_notes(learner_context, component=None):
    """Prior checks used by the answer, separately scoped from today's measured observations."""
    notes = []
    for kind, result in (learner_context or {}).items():
        for check in result.get('checks', []):
            pair = check.get('pair') or [check.get('left'), check.get('right')]
            if component is not None and check.get('component') != component and component not in pair:
                continue
            # Today's complete observations are already in the governed ledgers. Keep the exact prior finding,
            # source binding and computed check here, without copying today's entire pair window into every answer.
            note = {k: v for k, v in check.items() if k != 'today_evidence'}
            notes.append(dict(input_kind=kind, **note))
    return notes


def _recognize_pattern(finding, pair):
    """Recognize only the exact retained structure whose predicate this reader implements.

    A teacher exchange includes a separate F_LAST/lag search claim. Its unlagged
    teacher-row step pattern can be compared here, but that does not test the search claim.
    """
    if pair is None or pair.get('co_movement') is None:
        return dict(result='not_measurable', reason='no current pair co-movement evidence')
    steps = dict(pair['co_movement']['steps'])
    if str(finding.get('finding_id', '')).startswith('steps-vs-endpoints:'):
        match = re.search(r'end this window (SAME_DIRECTION|OPPOSITE_DIRECTION) first-to-last',
                          finding.get('premise') or '')
        if match is None or finding.get('scope'):
            return dict(result='not_measurable', reason='endpoint-pattern predicate or its additional scope is not implemented')
        relation = match.group(1)
        result = ('relation_differs' if relation != pair['direction_relation'] else
                  'pattern_again' if _step_disagreement(pair) is not None else 'pattern_not_seen')
        return dict(result=result, earlier_relation=relation, today_relation=pair['direction_relation'],
                    today_steps=steps, evaluated_structure='endpoint relation versus consecutive both-PRESENT steps',
                    independent_scientific_verification=False)
    if finding.get('joint_way') in ('same', 'opposite'):
        same, opposite = steps['same_direction'], steps['opposite_direction']
        now = 'same' if same > opposite else 'opposite' if opposite > same else None
        return dict(result='even_today' if now is None else 'same_teacher_steps_today'
                    if now == finding['joint_way'] else 'other_teacher_steps_today',
                    earlier_way=finding['joint_way'], today_steps=steps,
                    evaluated_structure='teacher-row consecutive both-PRESENT step direction only',
                    full_claim_tested=False, independent_scientific_verification=False,
                    reason='the retained search axis, transforms, lag, cell, conditions and chance check require the scientific engine')
    return dict(result='today_pair_measured', today_relation=pair['direction_relation'], today_steps=steps,
                full_claim_tested=False, reason='pair measured; no implemented structure predicate for this finding')


def component_answer(visible, comp, rights, *, learner_context=None, shared_market=None):
    """One component. TEACH: parse_component's shape (six narratives, one explanation per occurring state, one
    interpretation per pair in the order of `rights`). GUIDED: parse_independent_component's shape, which adds the
    claimed state counts, terminal state, direction, every observation with its note and each pair's relation, all
    computed by this code from the visible observations (the teacher withholds them in GUIDED)."""
    mode = visible['pre_message']['mode']
    comp = _component_evidence(visible, comp['name'])
    name = comp['name']
    present = [(int(p['cursor']), float(p['value'])) for p in comp['observations'] if p['state'] == 'PRESENT']
    counts = {s: int(comp['state_counts'][s]) for s in STATES}
    rises, falls, same = _steps(present)
    if present:
        first, last = present[0], present[-1]
        low = min(present, key=lambda cv: (cv[1], cv[0]))
        high = max(present, key=lambda cv: (cv[1], -cv[0]))
        span = (f'first PRESENT at cursor {first[0]} = {_num(first[1])}, last PRESENT at cursor {last[0]} = {_num(last[1])}; '
                f'lowest {_num(low[1])} at cursor {low[0]}, highest {_num(high[1])} at cursor {high[0]}; '
                f'between consecutive PRESENT observations: {rises} rises, {falls} falls, {same} unchanged')
        evidence = (f'cursors {first[0]} and {last[0]} (first and last PRESENT), {low[0]} and {high[0]} (the extremes); every one '
                    f'of the {len(comp["observations"])} retained cursors is listed in dipole_observation_review')
    else:
        span = 'no PRESENT observation in the window, so no value, extreme or step can be counted'
        evidence = f'every one of the {len(comp["observations"])} retained cursors is listed in dipole_observation_review (none PRESENT)'
    reasons = _reasons(comp)
    reason_text = '; '.join(f'{n} {state} ({reason})' for (state, reason), n in sorted(reasons.items())) or 'none'
    terminal = (f'terminal state {comp["terminal_state"]}'
                + (f' = {_num(comp["terminal_value"])}' if comp['terminal_state'] == 'PRESENT' and comp.get('terminal_value') is not None else '')
                + (f' ({comp.get("terminal_reason")})' if comp.get('terminal_reason') else ''))
    teacher = ' '.join(str(comp[f]) for f in ('role', 'behavior_basis') if comp.get(f))
    computed = '' if mode == 'TEACH' else ' (terminal state and direction computed by Frankie\'s code from its lawful current observations)'
    result = dict(
        explanation=(f'{AUTHOR}: {name} over {len(comp["observations"])} retained cursors; state counts '
                     f'{json.dumps(counts, sort_keys=True)}; {span}; {terminal}; first-to-last PRESENT direction '
                     f'{comp["first_to_last_present_direction"]}{computed}.'),
        why=(f'The teacher\'s definition of this component, quoted as the teacher\'s (not a claim of Frankie\'s): {teacher or "(none given)"} '
             f'Frankie\'s code adds no interpretation of its own (rule R01).'),
        market_behavior=('Not interpreted by Frankie\'s code: the market meaning of these states and values is interpretation, '
                         f'left open (rule R01). What was measured: {json.dumps(counts, sort_keys=True)}; {span}.'),
        fifo_full_book_order_link=('Not computed by Frankie\'s code from this component\'s window; listed as unknown, not filled in '
                                   '(rule R04).'),
        evidence=evidence + '.',
        uncertainty=(f'Non-PRESENT observations: {reason_text}. Change from the previous cycle as the teacher recorded it: '
                     f'{json.dumps(comp.get("change_from_previous"), sort_keys=True)}. No outcome after the causal cutoff is '
                     'known or claimed (rule R02).'),
    )
    if shared_market is not None:
        result['evidence'] += (' Shared market pictures retained at these original PRESENT anchors, each with its source '
            'status (exact clocks, the updates present at that boundary, last-observed states) or listed unavailable: '
            + _exact_market_text(shared_market.component(visible, name))
            + '. These anchors supplement the full ordered source accessible through the answer context; an absent '
            'layer or picture makes the instant thinner, never removes it; the Dipole values and target equations '
            'are unchanged.')
    occurring = [s for s in STATES if any(p['state'] == s for p in comp['observations'])]
    result['state_explanations'] = {s: f'{name}: {STATE_MEANING[s]}' + (f' (unit {comp["unit"]})' if s == 'PRESENT' and comp.get('unit') else '')
                                    for s in occurring}
    by_right = {p['right']: p for p in _pairs(visible, name)}
    # Every prior check once per component, not once per pair (the same list filtered 18 times gave the
    # same notes; the recognized set per pair is unchanged).
    all_notes = _knowledge_notes(learner_context)
    pairs = []
    for right in rights:
        p = by_right[right]
        corr = p.get('correlation') or {}
        coefficient = (f'Pearson {corr["pearson"]!r} over {corr.get("present_overlap")} overlapping PRESENT values'
                       if corr.get('pearson') is not None else
                       f'Pearson not reported ({corr.get("reason")}; {corr.get("present_overlap")} overlapping PRESENT values)')
        moves = p.get('co_movement')
        moves_text = ('co-movement counts not carried by this package' if moves is None else
                      f'co-movement over {moves["steps_between_consecutive_both_present"]} consecutive both-PRESENT steps: '
                      f'{json.dumps(moves["steps"], sort_keys=True)}; state pairings {json.dumps(moves["state_pairs"], sort_keys=True)}')
        pair = dict(right=right, developing_structure=None, correlation_interpretation=(
            f'{AUTHOR}: {_basis(visible)} {p["direction_relation"]}; {coefficient}; {moves_text}. Descriptive for this pair and '
            'window only; no causation or outcome claimed (rules R01, R02, R05).'))
        recognized = [note for note in all_notes
                      if note.get('result') in ('pattern_again', 'same_teacher_steps_today') and
                      set(note.get('pair') or [note.get('left'), note.get('right')]) == {name, right}]
        if recognized:
            pair['correlation_interpretation'] += (' Accumulated patterns recognized in this window: '
                + json.dumps(recognized, sort_keys=True, default=str)
                + '. This is a current scoped pattern match, not a new independent scientific confirmation.')
        if mode != 'TEACH':
            pair['direction_relation'] = p['direction_relation']       # the claimed relation the host grades
        pairs.append(pair)
    result['pairs'] = pairs
    notes = _knowledge_notes(learner_context, component=name)
    if notes:
        result['evidence'] += (' Legal prior knowledge applied to this component and its pairs, each with its source '
            'and check result: ' + json.dumps(notes, sort_keys=True, default=str)
            + '. A measured component/pair is descriptive evidence, not a scientific confirmation of the prior claim.')
    if mode != 'TEACH':
        # parse_independent_component's shape: the claims the host grades against its withheld key, every one of them
        # computed above from the visible observations (R01: observations stay observations; R04: every cursor listed).
        result['state_counts'] = counts
        result['terminal_state'] = comp['terminal_state']
        result['direction'] = comp['first_to_last_present_direction']
        result['observations'] = [dict(cursor=int(p['cursor']), state=p['state'],
                                       value=(float(p['value']) if p['state'] == 'PRESENT' else None),
                                       explanation=_observation_note(p)) for p in comp['observations']]
    return result


def _pairs(visible, name):
    return [p for p in (_evidence(visible).get('relationship_review') or []) if p['left'] == name]


def _step_disagreement(pair):
    """A pair whose first-to-last relation and its step-by-step counts point different ways, or None."""
    moves = pair.get('co_movement')
    if moves is None:
        return None
    same, opposite = moves['steps']['same_direction'], moves['steps']['opposite_direction']
    relation = pair['direction_relation']
    if relation == 'SAME_DIRECTION' and opposite > same:
        return same, opposite
    if relation == 'OPPOSITE_DIRECTION' and same > opposite:
        return same, opposite
    return None


def summary_answer(visible, outputs, *, learner_context=None, shared_market=None):
    """The summary in parse_summary's shape. Novel findings are only what a computation here surfaces: a pair whose
    first-to-last relation and its step-by-step co-movement counts point different ways (filed as a HYPOTHESIS)."""
    pre = _evidence(visible)
    comps = list(pre['components'])
    by_direction, by_terminal = {}, {}
    for c in comps:
        by_direction.setdefault(c['first_to_last_present_direction'], []).append(c['name'])
        by_terminal.setdefault(c['terminal_state'], []).append(c['name'])
    review = list(pre.get('relationship_review') or [])
    relations = {}
    for p in review:
        relations[p['direction_relation']] = relations.get(p['direction_relation'], 0) + 1
    reported = sum(1 for p in review if (p.get('correlation') or {}).get('pearson') is not None)
    not_reported = {}
    for p in review:
        corr = p.get('correlation') or {}
        if corr.get('pearson') is None:
            not_reported[str(corr.get('reason'))] = not_reported.get(str(corr.get('reason')), 0) + 1
    disagreements = [(p, d) for p in review for d in [_step_disagreement(p)] if d is not None]
    cycle_summary = (f'{AUTHOR}: {len(comps)} components. First-to-last PRESENT direction: '
                     + '; '.join(f'{k} {len(v)} ({", ".join(v)})' for k, v in sorted(by_direction.items()))
                     + '. Terminal state: ' + '; '.join(f'{k} {len(v)} ({", ".join(v)})' for k, v in sorted(by_terminal.items())) + '.')
    if shared_market is not None:
        cycle_summary += (' Shared ordered market source, its source-exhaustion and layer-coverage dispositions used by '
            'this review: ' + _exact_market_text(shared_market.summary())
            + '. Component anchor pictures are carried in the component evidence; they do not replace access to the '
            'full ordered view. Unsupported/failed/unpaired inputs, absent layers and unavailable anchor pictures '
            'remain source dispositions of a thinner instant, not invented Dipole measurements, not a rejected day, '
            'and not claims of native training.')
    correlation_review = (f'{AUTHOR}: {len(review)} pairs ({pre["evidence_source"]}). Relation: {json.dumps(relations, sort_keys=True)}. Pearson reported '
                          f'on {reported} pairs; not reported on {len(review) - reported} ({json.dumps(not_reported, sort_keys=True)}). '
                          f'{len(disagreements)} pairs whose first-to-last relation and step-by-step co-movement counts point different '
                          'ways (filed as hypotheses). Every coefficient and count is per pair and per window, never pooled or '
                          'averaged (rule R05).')
    questions = []
    for c in comps:
        if c['first_to_last_present_direction'] in ('FLAT', 'INSUFFICIENT') or c['terminal_state'] != 'PRESENT':
            questions.append(f'{c["name"]}: direction {c["first_to_last_present_direction"]}, terminal {c["terminal_state"]}; '
                             'what drives it is not computed by Frankie\'s code from this window.')
    unresolved = [f'{p["left"]}/{p["right"]}' for p in review if p['direction_relation'] == 'UNRESOLVED']
    if unresolved:
        questions.append(f'{len(unresolved)} pairs are UNRESOLVED in this window: {", ".join(unresolved)}.')
    if learner_context is not None:
        prior_correction = pre.get('prior_cycle_correction')
        if prior_correction is not None:
            cycle_summary += (' Previous-class correction locations were carried into this review: '
                + json.dumps(prior_correction, sort_keys=True, default=str)
                + '. Current observations and relationships were recomputed from this window; no prior grade '
                'values or answer key were used.')
        notes = _knowledge_notes(learner_context)
        recognized = [n for n in notes if n.get('result') in ('pattern_again', 'same_teacher_steps_today')]
        cycle_summary += (' Accumulated structures matched in the current observations, with each evaluated part '
                          'and source retained: ' + json.dumps(recognized, sort_keys=True, default=str) + '.')
        correlation_review += (' Legal learner knowledge was applied before these answers. Each prior source and '
            'its individual check, with original scope retained: ' + json.dumps(notes, sort_keys=True, default=str)
            + '. Prior findings are not relabelled as observations from this window; unavailable conditions supply '
            'no new test and do not downgrade a checked finding.')
        for kind, result in learner_context.items():
            for item in result.get('listed', []):
                questions.append('Legal knowledge input not evaluated by this classroom check (%s): %s' %
                                 (kind, json.dumps(item, sort_keys=True, default=str)))
        for note in notes:
            if note.get('result') == 'not_measurable':
                questions.append('Prior finding has no applicable classroom measurement: ' +
                                 json.dumps(note, sort_keys=True, default=str))
    findings = []
    for p, (same, opposite) in disagreements:
        findings.append(dict(
            finding_id=f'steps-vs-endpoints:{p["left"]}:{p["right"]}',
            premise=(f'HYPOTHESIS: {p["left"]} and {p["right"]} end this window {p["direction_relation"]} first-to-last, while their '
                     f'consecutive both-PRESENT steps moved the same way {same} times and the opposite way {opposite} times.'),
            why_novel=('Computed by Frankie\'s code from the pair\'s co-movement counts; the classroom key grades the first-to-last '
                       'relation only, so a step-by-step pattern running the other way is not in the curriculum. '
                       'The scientific work needs a double-check; once it holds, this finding receives the same treatment '
                       'regardless of occurrence count (rule R06).'),
            future_outcome_claimed=False,
            evidence_refs=[dict(kind='DIPOLE_RELATIONSHIP', left=p['left'], right=p['right'], claimed_relation='HYPOTHESIS',
                                reasoning=(f'Dipole relation {p["direction_relation"]}; co-movement steps '
                                           f'{json.dumps(p["co_movement"]["steps"], sort_keys=True)}.'))]))
    return dict(cycle_summary=cycle_summary, correlation_review=correlation_review, unresolved_questions=questions,
                novel_findings=findings)


def correction_answer(correction):
    """The correction in parse_correction's shape: each correction id resolved by taking the data the teacher shows for
    exactly that subclaim (rule R07, R08). The code holds no disagreement it could state, so none is claimed."""
    items = {item['correction_id']: item for item in correction.get('data_review_items') or []}
    resolutions = []
    for cid in correction['correction_ids']:
        item = items.get(cid)
        if item is None:
            detail = 'no data review item carries this id; the id is resolved as the teacher listed it, with nothing else changed'
        else:
            shown = {k: v for k, v in item.items() if k not in ('correction_id', 'message')}
            detail = f'{item.get("message", "")} Frankie\'s code takes the data shown for exactly this subclaim: {json.dumps(shown, sort_keys=True, default=list)}'
        resolutions.append(dict(correction_id=cid, corrected_understanding=f'{AUTHOR}: {detail}'))
    change = (f'{AUTHOR}: the {len(resolutions)} corrected subclaims are read from the data the teacher shows for each; nothing '
              'broader is discarded. The code transcribes TEACH evidence or computes answers from lawful current '
              'observations with the teacher\'s own functions, so a correction here points at a transcription, computation or '
              'assembly difference to be traced in the code.' if resolutions else
              f'{AUTHOR}: no correction ids; nothing changes.')
    return dict(what_i_will_change=change, remaining_disagreements=[], correction_resolutions=resolutions)


# ------------------------------------------------------------------------------------ the three-way exchange (his reply)
EXCHANGE_RESOLUTIONS = ('RESOLVED_HELD_ON_DAY', 'RESOLVED_SHOWN_OTHERWISE_ON_DAY', 'KEPT_AS_HYPOTHESIS')


def exchange_reply(*, item_id, author, day, final, joint, day_text, marks, lessons_sha256, proposed):
    """Frankie's reply in the three-way exchange (frankie_box_experiment_exchange.py; SPEC-scientific-teacher.md step 5),
    computed by his code from the two teachers' turns only: the BOSS teacher's and the scientific teacher's positions, the
    teachers' own findings on this item (each with its counts, its day and its cites), the search's counts per day.
    Returned in dipole_scientific_review.parse_reply's shape (item_id, position, reasoning, learned, next_steps; the
    exchange binds responds_to_hash and validates it with dipole_teacher_discussion.parse_frankie), plus his resolution:
      RESOLVED_HELD_ON_DAY            both teachers measured the claimed way on the day: resolved for that day in his words,
                                      eligible for the same treatment after mathematical/scientific double-check (R06);
      RESOLVED_SHOWN_OTHERWISE_ON_DAY both teachers measured the other way: "the data is showing this instead" is taken for
                                      that subclaim on that day only; the claim as made on its own day stays (R07, R08);
      KEPT_AS_HYPOTHESIS              no combination both teachers support, or their rows point both ways (R06).
    Remaining disagreement is stated explicitly (an empty list is said in words). No future-outcome claim (R02)."""
    boss, science = final['boss_teacher'], final['classroom_teacher']
    whose = {'frankie': 'my finding', 'historical': 'the historical claim'}.get(author, 'the claim')
    kinds = sorted({f['kind'] for f in joint})
    cites = [c for f in joint for c in f.get('cites') or []]
    remaining = []
    if joint and kinds == ['both_teachers_measured_the_claimed_way']:
        position, resolution = 'AGREE', 'RESOLVED_HELD_ON_DAY'
        understanding = (f'{AUTHOR}: on {day} both teachers measured {whose} {item_id} the claimed way. '
                         + ' '.join(f['statement'] for f in joint)
                         + f' I retain the measured scope on {day}. After the mathematical and scientific work is '
                           'double-checked, this finding receives the same treatment regardless of occurrence count (R06).')
    elif joint and kinds == ['both_teachers_measured_otherwise']:
        position, resolution = 'AGREE', 'RESOLVED_SHOWN_OTHERWISE_ON_DAY'
        understanding = (f'{AUTHOR}: the data is showing this instead on {day} for {whose} {item_id}. '
                         + ' '.join(f['statement'] for f in joint)
                         + f' I take that for this subclaim on {day} only (R07); the claim as it was made on its own day '
                           'stays as it was measured there.')
    elif joint:
        position, resolution = 'UNRESOLVED', 'KEPT_AS_HYPOTHESIS'
        understanding = (f'{AUTHOR}: the teachers measured {whose} {item_id} jointly on {day}, but their joint rows are of '
                         f'kinds {", ".join(kinds)}. ' + ' '.join(f['statement'] for f in joint)
                         + ' I keep it as a hypothesis (R06).')
        if len(kinds) > 1:
            remaining.append(f'the teachers\' joint rows on {day} point both ways ({", ".join(kinds)}); I set neither above '
                             'the other')
    else:
        position, resolution = 'UNRESOLVED', 'KEPT_AS_HYPOTHESIS'
        understanding = (f'{AUTHOR}: no combination both teachers support on {day} for {whose} {item_id} (the BOSS teacher\'s '
                         f'position {boss["position"]}, the scientific teacher\'s position {science["position"]}); {day_text}. '
                         'I keep it as a hypothesis with these counts named (R06).')
        if {boss['position'], science['position']} == {'AGREE', 'DISAGREE'}:
            remaining.append(f'the BOSS teacher\'s position is {boss["position"]} and the scientific teacher\'s is '
                             f'{science["position"]} on {day}; I hold neither over the other')
    held = [d for d, c in marks.items() if c.get('held')]
    other = [d for d, c in marks.items() if c.get('shown_otherwise')]
    if held and other:
        remaining.append(f'across the discovery days tested it held on {", ".join(held)} and was shown otherwise on '
                         f'{", ".join(other)}; each day stays on its own, never pooled (R05), and this stays open')
        for d in held + other:
            cite = dict(value=str(d), source_sha256=lessons_sha256, what='day tested')
            if cite not in cites:
                cites.append(cite)
    if resolution != 'RESOLVED_HELD_ON_DAY' and not joint:
        for token in re.findall(r'(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])', day_text):
            cite = dict(value=token, source_sha256=lessons_sha256, what='the search\'s counts on the day')
            if cite not in cites:
                cites.append(cite)
    if understanding.strip() in (item_id, f'{AUTHOR}: {item_id}'):
        raise ValueError('a bare id echo is not a resolution (R08)')
    reasoning = (understanding + ' ' + ('Remaining disagreement: ' + '; '.join(remaining) + '.' if remaining else
                                        'I hold no remaining disagreement on this item.')
                 + ' No outcome after the causal cutoff is known or claimed (R02).')
    learned = [f['statement'] for f in joint] or [f'on {day}: {day_text}']
    next_steps = list(proposed) + [f're-test {whose} on each later discovery day as it is searched (R06)']
    reply = dict(item_id=item_id, position=position, reasoning=reasoning, learned=learned, next_steps=next_steps)
    side = dict(resolution=resolution, correction_id=item_id, corrected_understanding=understanding,
                remaining_disagreements=remaining, future_outcome_claimed=False, rules=['R02', 'R06', 'R07', 'R08'],
                cites=cites)
    if resolution not in EXCHANGE_RESOLUTIONS:
        raise ValueError('unknown exchange resolution')
    return reply, side


# ------------------------------------------------------------------------------ the school: reproduction across days
REPRODUCTION_SCHEMA = 'FRANKIE_SCHOOL_REPRODUCTION_V1'


def school_reproduction(visible, school):
    """Read completed discovery school files selected at this workflow boundary, regardless of trading-date order.
    Each previously filed hypothesis is checked on today's TEACH evidence (R06). The retained `earlier_day` fields
    mean earlier learning, not a chronological market-date restriction. Two kinds, each on its own day, never pooled:
      his novel findings (steps-vs-endpoints: a pair whose first-to-last relation and step counts pointed different ways):
        pattern_again     today the pair has the same relation and its steps again point the other way;
        pattern_not_seen  today the pair has the same relation and its steps do not point the other way;
        relation_differs  today the pair's first-to-last relation is another one;
      the teachers' own findings (a pair both teachers measured one way on the day):
        same_teacher_steps_today / other_teacher_steps_today / even_today: the teacher-row substructure only;
        its separate search lag, axis, conditions and chance claim still need the scientific engine;
      and not_measurable (the pair is not in today's review, or carries no co-movement counts), with the reason.
    Every check carries today's counts and the earlier day's file sha256. Counts, never a rate or an average (R05)."""
    pre = _evidence(visible)
    review = {(p['left'], p['right']): p for p in pre.get('relationship_review') or []}

    def today(left, right):
        p = review.get((left, right)) or review.get((right, left))
        if p is None:
            return None, 'the pair is not in today\'s relationship review'
        if p.get('co_movement') is None:
            return None, 'today\'s review carries no co-movement counts for the pair'
        return p, None

    checks, read, listed = [], [], []
    for row, doc in school:
        read.append(dict(day=row['day'], file=row.get('file'), sha256=row['sha256'], report_number=row.get('report_number')))
        sections = doc.get('sections') or {}
        for section, body in sections.items():
            for item in body.get('items') or []:
                supported = (section == 'frankie_classwork' and item.get('name') == 'novel_findings' or
                             section == 'exchange' and isinstance(item.get('content'), dict) and
                             'teachers_findings' in item['content'])
                if not item.get('inline') or not supported:
                    listed.append(dict(earlier_day=row['day'], earlier_sha256=row['sha256'], section=section,
                                       item=item.get('name'), reason=('source pointer; bytes not supplied to this check'
                                       if not item.get('inline') else
                                       'school source read; this reproduction checks novel and teachers findings only')))
        for item in (sections.get('frankie_classwork') or {}).get('items') or []:
            if item.get('name') != 'novel_findings' or not item.get('inline'):
                continue
            for f in item.get('content') or []:
                refs = [r for r in f.get('evidence_refs') or [] if r.get('kind') == 'DIPOLE_RELATIONSHIP']
                for r in refs:
                    p, why = today(r['left'], r['right'])
                    base = dict(kind='novel_finding', earlier_day=row['day'], earlier_sha256=row['sha256'],
                                finding_id=f.get('finding_id'), left=r['left'], right=r['right'], finding=f)
                    if p is None:
                        checks.append(dict(base, result='not_measurable', reason=why))
                        continue
                    checks.append(dict(base, **_recognize_pattern(f, p)))
        for item in (sections.get('exchange') or {}).get('items') or []:
            if not item.get('inline'):
                continue
            for f in (item.get('content') or {}).get('teachers_findings') or []:
                pair = (f.get('scope') or {}).get('pair')
                way = f.get('joint_way')
                base = dict(kind='teachers_finding', earlier_day=row['day'], earlier_sha256=row['sha256'],
                            finding_id=f.get('finding_id'), pair=pair, finding=f)
                if not pair or way is None:
                    checks.append(dict(base, result='not_measurable', reason='the finding names no pair or way this code reads'))
                    continue
                p, why = today(pair[0], pair[1])
                if p is None:
                    checks.append(dict(base, result='not_measurable', reason=why))
                    continue
                checks.append(dict(base, **_recognize_pattern(f, p)))
    per_day = {}
    for c in checks:
        d = per_day.setdefault(c['earlier_day'], {})
        d[c['result']] = d.get(c['result'], 0) + 1
    return dict(schema=REPRODUCTION_SCHEMA, author=AUTHOR, school_days_read=read, checks=checks, listed=listed,
                counts_per_earlier_day=dict(sorted(per_day.items())), model_calls=0,
                rule='each earlier day and each hypothesis on its own; counts, never pooled (R05); a hypothesis is tracked '
                     'for scientific checking; checked single-occurrence findings receive equal treatment (R06)')


def stage_knowledge_reproduction(visible, knowledge, *, evidence=None, relationship_kind='DIPOLE_RELATIONSHIP'):
    """Apply legal stage findings to current Dipole evidence or the caller's lawful external pair view.

    This learner check never substitutes for the scientific teacher's lag/condition/equation tests. Full source
    documents are input, not version-only witnesses. No prior claim is relabelled as today's observation.
    """
    pre = _evidence(visible) if evidence is None else evidence
    review = {(p['left'], p['right']): p for p in pre.get('relationship_review') or []}
    components = {c['name']: c for c in pre['components']}
    checks, sources, listed = [], [], []

    def claims(value, address=()):
        if isinstance(value, dict):
            if value.get('finding_id') or value.get('claim_id') or ('x' in value and 'y' in value):
                yield address, value
            else:
                for key, item in value.items():
                    yield from claims(item, address + (key,))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                yield from claims(item, address + (i,))

    for source in knowledge:
        sources.append({k: source[k] for k in ('label', 'day', 'kind', 'path', 'sha256')})
        content = source['content']
        found = False
        for bound in content.get('sources', []) if isinstance(content, dict) else []:
            if not bound.get('inline'):
                listed.append(dict(label=source['label'], source=bound,
                                   reason='retained source pointer; source bytes are not supplied to this learner check'))
        for address, finding in claims(content):
            found = True
            binding = dict(source_label=source['label'], source_day=source['day'], source_kind=source['kind'],
                           source_sha256=source['sha256'], address=address, finding=finding)
            refs = [r for r in finding.get('evidence_refs') or [] if r.get('kind') == relationship_kind]
            pairs = [(r.get('left'), r.get('right')) for r in refs]
            pair = (finding.get('scope') or {}).get('pair')
            component = (finding.get('scope') or {}).get('component')
            if component:
                measured = components.get(component)
                checks.append(dict(binding,
                                   component=component, result='today_component_measured' if measured else 'not_measurable',
                                   today_evidence=measured,
                                   reason=None if measured else 'the exact component is not in today\'s Dipole curriculum'))
            if pair and len(pair) == 2:
                pairs.append(tuple(pair))
            if 'x' in finding and 'y' in finding:
                pairs.append((finding['x'], finding['y']))
            if not pairs and not component:
                checks.append(dict(binding,
                                   result='not_measurable', reason='the finding has no %s pair binding' % relationship_kind))
            for left, right in pairs:
                today = review.get((left, right)) or review.get((right, left))
                measured = today is not None and today.get('co_movement') is not None
                checks.append(dict(binding, pair=[left, right], today_evidence=today if measured else None,
                                   **_recognize_pattern(finding, today if measured else None)))
        if not found:
            listed.append(dict(label=source['label'], day=source['day'], sha256=source['sha256'],
                               reason='source read; it has no finding/claim binding this Dipole reproduction can evaluate'))
    return dict(schema='FRANKIE_STAGE_KNOWLEDGE_REPRODUCTION_V1', author=AUTHOR, sources=sources,
                checks=checks, listed=listed, model_calls=0,
                rule='apply source-bound findings individually; no occurrence gates, validity downgrade or pooled outputs')
