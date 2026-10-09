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
import bisect
import re
import sys
from pathlib import Path

# The one 99-entry registry (Greg, 2026-10-07): the entry list comes from frankie_box_all99_coverage; this piece keeps
# its own routes, consumers and dispositions below. The box directory holds every frankie_box_* module.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import frankie_box_all99_coverage as ALL99  # noqa: E402


def lane_cpus():
    """The CPUs booked for this day (Greg, 2026-10-07: a day gets all 32, or the 16 of a lane): FRANKIE_LANE_CPUS as
    the CPU ledger hands it (a comma list; a-b ranges accepted), else FRANKIE_BOOKED_CPUS (frankie_box_cores sets both
    from the booking's cpu_list; the stacks pass 2026-10-07 added this fallback, the order frankie_box_lane_pin reads
    them in), else this process's affinity mask. Every classroom pool sizes from this one list. The list is not
    intersected with the affinity: the SOCRATIC/VERIFY learner walk compares the two and refuses a difference."""
    import os
    text = os.environ.get('FRANKIE_LANE_CPUS') or os.environ.get('FRANKIE_BOOKED_CPUS') or ''
    cpus = set()
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        low, _, high = part.partition('-')
        if low.isdigit() and (not high or high.isdigit()):
            cpus.update(range(int(low), int(high or low) + 1))
    if not cpus and hasattr(os, 'sched_getaffinity'):
        cpus = set(os.sched_getaffinity(0))
    return sorted(cpus) or [0]


def lane_workers():
    """Workers beside the coordinator: the booked CPUs minus one (15 on a 16-CPU lane, 31 on the 32-CPU day)."""
    return max(1, len(lane_cpus()) - 1)


# Where this process's classroom work ran (Greg, 2026-10-07: every pool and thread pinned to the booked lane, physical
# cores first; frankie_box_lane_pin). Filled by the pass consumer, the native series threads and the 171-pair fork pool
# when they run in this process; receipt-only (classroom V2 received.cpu_pinning), never an input to an answer.
PINNING_RECORD = {}


def _lane_pin():
    import frankie_box_lane_pin as LP     # the one shared placement helper (same box directory; sys.path set above)
    return LP


def pinning_record():
    """Receipt view of PINNING_RECORD (per pool: its CPU map and outcome), with this process's OpenBLAS reduction
    setting (dipole_classroom_external.blas_reduction: the 32-thread bits of every Pearson dot product) whenever a
    Pearson ran here, else named as not run."""
    out = {name: dict(item) for name, item in PINNING_RECORD.items()}
    if 'blas_reduction' not in out:
        EXT = sys.modules.get('research.kalshi.frankie_boss.dipole_classroom_external')
        out['blas_reduction'] = (EXT.blas_reduction() if EXT is not None and getattr(EXT, '_BLAS', None) else
                                 dict(mode='NOT_RUN', threads=32, reason='no Pearson dot product ran in this process'))
    return out

# The stage heartbeat from inside the classroom's long sub-steps (FA-4 pattern; frankie_box_stage_progress.report_phase,
# read by the parent's Heartbeat: units, units/min and the report-only stall flag at 600 s). report_phase never raises;
# an import failure of the probe module is the one error left, and it is listed here (receipt: received.probe_errors in
# classroom V2), never swallowed quietly. A probe never changes a value, an order or a byte.
PROBE_ERRORS = {}


def heartbeat(phase, done, total=None, unit=None, every=None, **extra):
    try:
        import frankie_box_stage_progress as SP
    except Exception as error:  # noqa: BLE001 - listed, the stage goes on
        PROBE_ERRORS.setdefault('%s: %s' % (type(error).__name__, error), 0)
        PROBE_ERRORS['%s: %s' % (type(error).__name__, error)] += 1
        return
    SP.report_phase(phase, units_done=done, units_total=total, unit=unit, every=every, **extra)


# ---- periodic exact saves inside the long sub-steps (Greg, 2026-10-07 night: "every workflow piece needs their
# restore save code updated to match ROOT's"; the September 29 item 2 rule: exact state at a closed boundary every N
# units, so a crash loses at most one segment, and a requested save runs on to the next boundary, saves, exits 75).
# The boundary is an in-order arrival of an ordered computation (a native series chunk, a Dipole pair, an anchor
# picture text): every value before it is final. Each save writes ONLY the values since the last one, as one more
# segment file (parallel_teacher._save_raw_state: a sha256-prefixed pickle, fsynced, renamed), so saving is linear in
# the values and never rewrites an earlier segment. A resume loads the segments in order (each checked: its hash, its
# key, its start = the values before it) and computes only the rest with the same functions; a value comes back through
# the same pickle a saved phase uses, so the result is the same bytes. The key binds the classroom's code-free identity
# (set by the runner: its data identity and save format; Greg, 2026-10-09: the code version is recorded, never compared),
# the operation and its whole job list: another day, source or job list never matches; a code change does not. A segment
# directory saved under the earlier key (the digest of the whole saved identity, code fields included; legacy_identity)
# is adopted, never lost. A sub-step's segments are removed once it returns its whole value (its phase then saves it).
# Configured by the classroom V2 runner (SEGMENT_SAVES: directory, identity digest, legacy_identity, save_requested,
# every_s); without it nothing is saved here (as before).
SEGMENT_SCHEMA = 'FRANKIE_CLASSROOM_SEGMENT_SAVE_V1'
SEGMENT_SAVES = {}
SEGMENT_RECORD = {}
SEGMENT_EVERY_SECONDS = 120.0


def _job_key(job):
    """A job's stable text for the segment key: a function by its qualified name (never its address), else repr."""
    if isinstance(job, tuple):
        return [_job_key(part) for part in job]
    if callable(job):
        return '%s.%s' % (getattr(job, '__module__', '?'), getattr(job, '__qualname__', getattr(job, '__name__', '?')))
    return repr(job)


class _Segments:
    def __init__(self, operation, jobs_key):
        import time
        config = SEGMENT_SAVES
        self.operation, self.enabled = operation, bool(config.get('directory'))
        def key_of(identity):
            return hashlib.sha256(json.dumps([SEGMENT_SCHEMA, identity, operation, jobs_key],
                                             sort_keys=True, default=str).encode()).hexdigest()
        def directory_of(key):
            return Path(config['directory']) / 'segment-saves' / ('%s-%s' % (operation, key[:16]))
        self.key = key_of(config.get('identity'))
        self.directory = directory_of(self.key) if self.enabled else None
        adopted = None
        if self.enabled and not self.directory.is_dir() and config.get('legacy_identity') not in (None, config.get('identity')):
            legacy = key_of(config['legacy_identity'])
            if directory_of(legacy).is_dir():
                # segments saved under the earlier code-bound key: the same continuation, kept and continued there
                self.key, self.directory, adopted = legacy, directory_of(legacy), legacy
        self.every = float(config.get('every_s') or SEGMENT_EVERY_SECONDS)
        self.save_requested = config.get('save_requested')
        self.saved, self.last = 0, time.monotonic()
        self.record = SEGMENT_RECORD.setdefault(operation, dict(saves=0, resumed_values=0, segments_loaded=0))
        self.record.update(enabled=self.enabled, every_s=self.every,
                           directory=str(self.directory) if self.directory else None,
                           legacy_key_adopted=adopted is not None)

    def load(self):
        """The values saved by an earlier attempt, in order ([] when none). A segment that fails its checks refuses."""
        if not self.enabled or not self.directory.is_dir():
            return []
        from research.kalshi.frankie_boss.parallel_teacher import _load_raw_state
        values = []
        for path in sorted(self.directory.glob('seg-*.pkl')):
            body = _load_raw_state(path)
            if body.get('schema') != SEGMENT_SCHEMA or body.get('key') != self.key or body.get('start') != len(values):
                raise ValueError('saved classroom segment %s belongs to another continuation; retained for recovery' % path)
            values.extend(body['values'])
            self.record['segments_loaded'] += 1
        self.saved = len(values)
        self.record['resumed_values'] = len(values)
        return values

    def offer(self, values):
        """After an in-order arrival: `values` = every final value so far. Saves the new ones when the interval passed or
        a save was requested; on a requested save raises TeacherSaved (exit 75) after the segment is durable."""
        import time
        if not self.enabled:
            return
        requested = bool(self.save_requested and self.save_requested())
        if requested or time.monotonic() - self.last >= self.every:
            if len(values) > self.saved:
                from research.kalshi.frankie_boss.parallel_teacher import _save_raw_state
                _save_raw_state(self.directory / ('seg-%012d.pkl' % self.saved),
                                dict(schema=SEGMENT_SCHEMA, key=self.key, operation=self.operation, start=self.saved,
                                     values=list(values[self.saved:])))
                self.saved = len(values)
                self.record['saves'] += 1
                self.record['saved_values'] = self.saved
            self.last = time.monotonic()
        if requested:
            from research.kalshi.frankie_boss.parallel_teacher import TeacherSaved
            self.record['stopped_at'] = self.saved
            raise TeacherSaved('classroom %s saved at %d values (a closed boundary); a resume continues there'
                               % (self.operation, self.saved))

    def done(self):
        """The sub-step returned its whole value: its segments are no longer the resume point (its phase saves it)."""
        if self.enabled and self.directory.is_dir():
            import shutil
            shutil.rmtree(self.directory, ignore_errors=True)
            self.record['removed_after_completion'] = True


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


TEACHER_CARRY_SCHEMA = 'FRANKIE_CLASSROOM_TEACHER_CARRY_V1'


class TeacherPassCarry:
    """The classroom's whole-source work made on the TEACHER's walk (one pass, Greg 2026-10-09): per picture of the
    teacher's shared read, the all-99 arrivals (_Arrivals.note), the source status counts and the six native entries'
    pass (_NativeEntryArithmetic online: the teacher declares each Dipole roster cursor, the entity's rows of its
    contiguous equation prefix, before the picture that carries it). Saved with the teacher's receipt; the classroom's
    market_context takes it and reads the shared source only as far as its last anchor picture."""

    def __init__(self, timeline, limits=None):
        self.arrivals, self.counts, self.pictures = _Arrivals(), {}, 0
        # the anchor pictures (Greg, 2026-10-09: the classroom does not re-walk the market timeline): per Dipole
        # component its first PRESENT, running minimum and maximum, and last PRESENT row, each with the whole picture of
        # that instant. Kept only when the teacher feeds the row values (enable_anchors, then note_row per roster row);
        # a roster row's picture waits in anchor_pending until its values arrive (the teacher's row pipeline depth).
        self.anchor_on, self.anchor_pending, self.anchor = False, {}, {}
        self.anchor_pictures, self.anchor_rows, self.anchor_unvalued = {}, 0, []
        try:
            self.native = _NativeEntryArithmetic([], getattr(timeline, 'native_carriers', None),
                                                 getattr(timeline, 'layers', None) or {}, limits=limits, online=True)
            self.native_setup = None
        except Exception as error:  # noqa: BLE001 - recorded; the classroom then makes its own pass for the native entries
            self.native, self.native_setup = None, 'setting up: %s: %s' % (type(error).__name__, error)

    def enable_anchors(self):
        """The teacher will call note_row(cursor, components) for every roster row it declares (in roster order)."""
        self.anchor_on = True

    def note_row(self, cursor, components):
        """A roster row's Dipole values (the snapshot row's components: (name, state name, value) each, value a float
        when PRESENT): update each component's first / running minimum / running maximum / last PRESENT anchor with the
        same tie rules as market_context (minimum: lowest value, then earliest cursor; maximum: highest value, then
        earliest cursor), keep the pictures an anchor names, release the others. Pending rows before this cursor that
        never received values are listed (anchor_unvalued) and released."""
        held = self.anchor_pending.pop(cursor, None)
        for earlier in [c for c in self.anchor_pending if c < cursor]:
            self.anchor_unvalued.append(earlier)
            self.anchor_pending.pop(earlier)
        self.anchor_rows += 1
        for item in components:
            name, state, value = (item['name'], item['state'], item['value']) if isinstance(item, dict) else item
            if state != 'PRESENT' or value is None:
                continue
            point = (int(cursor), float(value))
            slot = self.anchor.get(name)
            if slot is None:
                self.anchor[name] = dict(first=point, last=point, minimum=point, maximum=point)
                continue
            slot['last'] = point
            if point[1] < slot['minimum'][1]:
                slot['minimum'] = point
            if point[1] > slot['maximum'][1]:
                slot['maximum'] = point
        named = {c for slot in self.anchor.values() for c, _ in slot.values()}
        if held is not None and int(cursor) in named:
            self.anchor_pictures[int(cursor)] = held
        for c in [c for c in self.anchor_pictures if c not in named]:
            del self.anchor_pictures[c]

    def note(self, item, row_cursor=None):
        import time
        picture = item['picture']
        if self.anchor_on and row_cursor is not None:
            # the whole picture of the instant (a new top-level mapping, its contents shared: the core never edits a
            # yielded picture), with the status record market_context keeps for an anchor
            self.anchor_pending[int(row_cursor)] = (dict(picture), dict(
                source_status=picture['source_status'], applied_evidence=item['evidence'] is not None,
                unpaired_outcomes=picture.get('unpaired_outcomes'), thinner=copy.deepcopy(picture.get('coverage'))))
        status = picture['source_status']
        key = status if isinstance(status, str) else json.dumps(status, sort_keys=True)
        self.counts[key] = self.counts.get(key, 0) + 1
        self.pictures += 1
        self.arrivals.note(picture, item['evidence'])
        native = self.native
        if native is None:
            return
        if row_cursor is not None:
            native.declare_row(row_cursor)
        if native.status is None:
            try:
                clock = time.perf_counter()
                native.note(picture, item['evidence'])
                native.note_seconds += time.perf_counter() - clock
            except Exception as error:  # noqa: BLE001 - blocks only this computation, as in the classroom's own pass
                native.status, native.reason = 'failed', 'at adapter cursor %s: %s: %s' % (
                    picture['at'].get('adapter_cursor'), type(error).__name__, error)

    def state(self, identity):
        """The carry to save beside the teacher's receipt (call once, after the walk exhausted the source)."""
        if self.native is not None:
            self.native.end_online()
        anchors = None
        if self.anchor_on:
            unvalued = sorted(self.anchor_unvalued + list(self.anchor_pending))
            anchors = dict(components={name: {k: list(v) for k, v in slot.items()} for name, slot in self.anchor.items()},
                           pictures={c: held[0] for c, held in self.anchor_pictures.items()},
                           statuses={c: held[1] for c, held in self.anchor_pictures.items()},
                           rows_valued=self.anchor_rows, rows_without_values=unvalued)
        return dict(schema=TEACHER_CARRY_SCHEMA, identity=identity, pictures=self.pictures,
                    source_status_counts=dict(self.counts), arrivals=self.arrivals.record(),
                    native=self.native.pass_state() if self.native is not None else None, native_setup=self.native_setup,
                    anchors=anchors)


def market_context(visible, timeline, *, save_requested, native_limits=None, carry=None, teacher_report=None):
    """Read the complete shared view once; retain full pictures at existing evidence anchors.

    Missing-coverage rule (Greg, 2026-10-07): the read exhausts the ordered source, and whatever
    picture the source holds at an anchor's original adapter cursor is retained with its source
    status (applied, failed, unpaired...). An anchor whose cursor has no picture is listed
    `unavailable`; its Dipole value from the teacher rows stands and the market picture at that
    instant is thinner. Nothing is fabricated for it. Exhaustion, layer coverage and integrity are
    reported separately. Same-day identity mismatches still refuse; they are not coverage.

    One pass (Greg, 2026-10-09): with `carry` (TeacherPassCarry.state from the teacher's walk of this same source,
    identity equal) and `teacher_report` (the teacher's exhausted shared read), the arrivals, the source status counts
    and the native entries' pass come from the teacher's walk, coverage from its report, and this read stops at the
    last anchor picture. A carry that does not match (identity, roster, carriers) makes the full pass as before.
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
    counts = {}
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
    # The six native entries as operands (Greg, 2026-10-07 night: "We want 18 of 18"): their values are taken on this
    # same pass, in source order, at their own cursors; computed against the Dipole rows after the pass (finish()).
    try:
        # native_limits: the cutoff (native_cutoff_limits; None = the defaults), recorded on the result
        native, native_setup = _NativeEntryArithmetic(_evidence(visible)['components'], getattr(timeline, 'native_carriers', None),
                                                      getattr(timeline, 'layers', None) or {}, limits=native_limits), None
    except Exception as error:  # noqa: BLE001 - blocks only the native entry arithmetic; recorded, never a measurement
        native, native_setup = None, 'setting up: %s: %s' % (type(error).__name__, error)
    carried, carry_note = _take_carry(carry, teacher_report, timeline, native, native_setup)
    if carried:
        arrivals_record, counts = carry['arrivals'], dict(carry['source_status_counts'])
    pictures, statuses = {}, {}
    held, held_note = (_carry_anchors(carry, anchors, wanted) if carried else (None, 'the carry is not taken'))
    carry_note = dict(carry_note, anchors=held_note)
    if held is not None:
        pictures, statuses = held
    iterator = (item for item in ()) if held is not None else timeline.iter_pictures()
    # The pass consumer on its own CPU (Greg, 2026-10-07: pin every step; research item: the full-read consumer on a
    # whole core). lane[0] is the CPU the readers leave free (frankie_journal_reader.worker_budget and the timeline's
    # decode take lane[1:]). The timeline sizes its decode pools from THIS thread's affinity when each stream starts,
    # so the pin waits until every stream generator has started, and the original mask is restored when the pass
    # ends, before the native series and pair pools are sized. The sibling thread of lane[0] stays in the readers'
    # list (that list is the ROOT-bound timeline's and the journal reader's; a whole idle core needs a change there).
    LP = _lane_pin()
    consumer, siblings, topology_basis = LP.consumer_core(lane_cpus())
    original_mask = LP.current_mask()
    consumer_pin = dict(cpu=consumer, sibling_threads=siblings, mask=sorted({consumer, *siblings}) if consumer is not None
                        else None, topology=topology_basis, outcome='waiting',
                        siblings_note='the consumer\'s whole core (its CPU and sibling threads); the sibling threads also '
                                      'stay in the reader/decode worker lists (ROOT-bound timeline and journal reader)')
    PINNING_RECORD['pass_consumer'] = consumer_pin
    waiting = consumer is not None
    try:
        for item in (() if carried and not wanted else iterator):
            if save_requested():
                raise TeacherSaved('shared classroom picture read interrupted; no completed reading claimed')
            if waiting:
                streams = getattr(timeline, 'streams', None)
                started_streams = LP.generators_started(streams) if streams is not None else None
                if started_streams is None:
                    waiting = False
                    consumer_pin.update(outcome='not_pinned', reason='cannot tell whether the reader sized its pools; '
                                        'the consumer keeps the lane mask')
                elif started_streams:
                    waiting = False
                    consumer_pin.update(LP.pin_core(consumer_pin['mask']), at_picture=seen + 1)
            picture = item['picture']
            status = picture['source_status']
            # The core yields a plain status string (applied, failed, unpaired_...); a structured status is
            # keyed by its sorted JSON. No per-picture JSON encoding on the hot path for the common case.
            seen += 1
            if carried:
                # one pass: the teacher's walk made the whole-source work; this read only retains the anchor pictures
                if not seen & 4095:
                    heartbeat('classroom: shared market read to the last anchor', seen, unit='pictures', every=1.0,
                              source_records=timeline.source.get('record_count'))
            else:
                key = status if isinstance(status, str) else json.dumps(status, sort_keys=True)
                counts[key] = counts.get(key, 0) + 1
            if not carried and not seen & 4095 and (native is None or native.status is not None):
                # the heartbeat while the native entries do not report the pass themselves (absent, failed, cut off)
                heartbeat('classroom: shared market read', seen, unit='pictures', every=1.0,
                          source_records=timeline.source.get('record_count'))
            if not carried:
                arrivals.note(picture, item['evidence'])
            if not carried and native is not None and native.status is None:
                try:
                    clock = time.perf_counter()
                    native.note(picture, item['evidence'])
                    native.note_seconds += time.perf_counter() - clock
                except Exception as error:  # noqa: BLE001 - blocks only this computation; recorded, never a measurement
                    native.status, native.reason = 'failed', 'at adapter cursor %s: %s: %s' % (
                        picture['at'].get('adapter_cursor'), type(error).__name__, error)
            cursor = picture['at']['adapter_cursor']
            if cursor in wanted:
                if cursor in pictures:
                    raise ValueError('identity: shared market holds two original INPUT pictures for one classroom adapter cursor')
                # Retained as yielded (a new top-level mapping, its contents shared): the core never changes a picture
                # or any update, state or envelope inside it once yielded (frankie_box_market_timeline.iter_pictures
                # builds each picture new per INPUT; a state is replaced, never edited), so this IS the picture at its
                # instant. Greg, 2026-10-07 night (the September 29 pattern; full data): a deep copy per anchor walked
                # every last-observed state again (up to 76 anchors, each the latest full book of every instrument), in
                # memory and in time; shared states now cost once, and the saved phase pickles them once.
                pictures[cursor] = dict(picture)
                # The core's per-instant thinner dict (absent layers, exact clocks, readable record) when present.
                statuses[cursor] = dict(source_status=status, applied_evidence=item['evidence'] is not None,
                                        unpaired_outcomes=picture.get('unpaired_outcomes'),
                                        thinner=copy.deepcopy(picture.get('coverage')))
                if len(pictures) == len(wanted):
                    last_anchor_seen_at = seen
                    if carried:
                        break               # one pass: nothing after the last anchor is needed from this read
    finally:
        try:
            iterator.close()
        finally:
            if consumer_pin.get('outcome') in ('pinned', 'fallback'):
                consumer_pin['restored'] = LP.restore_mask(original_mask)
            elif consumer_pin.get('outcome') == 'waiting':
                consumer_pin.update(outcome='not_pinned', reason='the reader streams never all started in this pass')
    if carried:
        total = carry.get('pictures')
        read = dict(seconds=round(time.monotonic() - started, 3), pictures_seen=seen, workers=lane_workers(),
                    consumer_pin=dict(consumer_pin),
                    wanted_anchor_cursors=len(wanted), max_wanted_adapter_cursor=(max(wanted) if wanted else None),
                    last_anchor_retained_at_picture=last_anchor_seen_at,
                    pictures_after_last_anchor=(total - last_anchor_seen_at if last_anchor_seen_at is not None
                                                and type(total) is int else None),
                    read_to_end=False, pictures_in_source=total, carry=carry_note,
                    anchors_from_carry=(len(pictures) if held is not None else 0),
                    note='one pass (Greg, 2026-10-09): the teacher\'s walk of this same source made the whole-source '
                         'work (arrivals, source status counts, the native entries\' pass) and its exhausted read is the '
                         'coverage; this read retained the anchor pictures and stopped at the last one')
    else:
        read = None
    read = read or dict(seconds=round(time.monotonic() - started, 3), pictures_seen=seen, workers=lane_workers(),
                consumer_pin=dict(consumer_pin),
                wanted_anchor_cursors=len(wanted), max_wanted_adapter_cursor=(max(wanted) if wanted else None),
                last_anchor_retained_at_picture=last_anchor_seen_at,
                pictures_after_last_anchor=(seen - last_anchor_seen_at if last_anchor_seen_at is not None else None),
                read_to_end=True, carry=carry_note,
                hot_path='per picture: status key, anchor membership test, arrivals.note (a few dict increments; '
                         'per update: source name, frame section presence, top-level field names); native.note (the six '
                         'native entries: per native member row the carrier leaves, per lifecycle row a count; its own '
                         'time is native_entries.hot_path_seconds); deepcopy only at wanted anchors. The core\'s decode '
                         'dominates; measure on the one-to-two-minute canary.',
                note='one full ordered read; the tail after the last anchor serves source_status_counts and this '
                     'consumer\'s own view of exhaustion. Measured here so the one-day test can show where the '
                     'classroom\'s time goes before any shortening is considered; no shortening is applied.')
    if native is None:
        native_entries = native_entries_failed(native_setup)
    else:
        try:
            native_entries = native.finish()
        except Exception as error:  # noqa: BLE001 - blocks only the native entry arithmetic; the classroom and the day go on
            native.status, native.reason = 'failed', 'computing the series: %s: %s' % (type(error).__name__, error)
            native_entries = native.finish()
    # Reaching here means the iterator ended without an integrity/identity exception. The core's
    # own exhaustion flag is read beside that fact, never used to reject a thinner day.
    if carried:
        # one pass: the teacher's exhausted read of this same source (identity checked) is the coverage record; the
        # teacher's own additions (its equation accounting, its carry note) are not part of the reader's report
        report = {k: copy.deepcopy(v) for k, v in teacher_report.items() if k not in ('equation', 'classroom_carry')}
    else:
        report = copy.deepcopy(timeline.report)
    coverage = coverage_disposition(report, journal_count=timeline.source.get('journal_count'),
                                    record_count=timeline.source.get('record_count'))
    coverage['classroom_iterator_ended'] = not carried
    if carried:
        coverage['classroom_read'] = ('not read: every anchor picture came from the teacher\'s walk (%s); coverage is the '
                                      'teacher\'s exhausted read' % held_note if held is not None else
                                      'stopped at the last anchor picture; coverage is the teacher\'s exhausted read')

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
                    interface='SharedMarketTimeline.iter_pictures', workers=lane_workers()),
                anchors=anchors, pictures=pictures, report=report,
                source_status_counts=counts, coverage=coverage, read=read,
                arrivals=(arrivals_record if carried else arrivals.record()),
                # the predecessor bootstrap as the ingestion receipt recorded it (seeded / absent / none recorded);
                # the core yields no opening-state picture element (named as a request to the core author)
                opening_book=(dict(status=opening.get('status'), listed=opening.get('listed'))
                              if opening is not None else dict(status='not_recorded_in_ingestion_receipt')),
                journal_witness=getattr(timeline, 'input_verification', None),
                anchor_pictures=dict(wanted=len(wanted), retained=len(pictures), unavailable=unavailable),
                # the six native entries' operands, computed against the Dipole rows (FRANKIE_CLASSROOM_NATIVE_ENTRY_ARITHMETIC_V1)
                native_entries=native_entries,
                use='full ordered source read to its end; first/last/min/max PRESENT anchor pictures, each with its source '
                    'status or listed unavailable, supplement unchanged Dipole mathematics; the six native entries\' own '
                    'values on the same pass are operands of the native entry arithmetic (native_entries)',
                limit='no claim that every market field changes a target or is interpreted; no claim that every layer was '
                      'present; no native training; the Dipole values and target equations are unchanged')


def component_anchors(visible):
    """{component: {first, last, minimum, maximum: (cursor, value)}} over its PRESENT observations, with market_context's
    tie rules; the anchor cursors the classroom retains pictures at."""
    out = {}
    for component in _evidence(visible)['components']:
        present = [(int(p['cursor']), float(p['value'])) for p in component['observations'] if p['state'] == 'PRESENT']
        out[component['name']] = {} if not present else dict(
            first=present[0], last=present[-1], minimum=min(present, key=lambda cv: (cv[1], cv[0])),
            maximum=max(present, key=lambda cv: (cv[1], -cv[0])))
    return out


def second_set_lesson(teacher_rows, directory, visible, snapshot_rows, *, teacher_receipt=None, day_file=None, as_of=None):
    """The teacher's second set handed to Frankie (frankie_box_teacher_rows.second_set_lesson): every row's second set
    whole in <directory>/package.second_set.jsonl (aligned on the classroom's own snapshot rows), the record with every
    absence listed in <directory>/package.second_set.json, and the second set at each component's anchor rows with its
    planes resolved by reading their references. Never raises for the data: a failure is the record's status."""
    import frankie_box_teacher_rows as TR
    directory = Path(directory)
    anchors = component_anchors(visible)
    cursors = sorted({c for chosen in anchors.values() for c, _ in chosen.values()})
    try:
        lesson = TR.second_set_lesson(teacher_rows, directory / 'package.second_set.jsonl', snapshot_rows,
                                      anchor_cursors=cursors, teacher_receipt=teacher_receipt, day_file=day_file,
                                      as_of=as_of)
    except Exception as error:  # noqa: BLE001 - the second set's failure is listed; the classroom goes on
        lesson = dict(schema=TR.SECOND_SET_LEDGER_SCHEMA, status='failed', reason='%s: %s' % (type(error).__name__, error))
    lesson['component_anchors'] = {name: {k: list(v) for k, v in chosen.items()} for name, chosen in anchors.items()}
    with (directory / 'package.second_set.json').open('w', encoding='utf-8') as handle:
        json.dump(lesson, handle, sort_keys=True, default=str)
    return lesson


def second_set_context(lesson):
    """The second set as a learner_context input: no prior checks; every absence, alignment difference, mismatch and
    unresolved reference listed (each becomes an open question of the summary)."""
    listed = []
    if not isinstance(lesson, dict) or lesson.get('status') != 'carried':
        listed.append(dict(second_set=(lesson or {}).get('status'), reason=(lesson or {}).get('reason')))
        return dict(checks=[], listed=listed, lesson=lesson)
    for role, listing in (lesson.get('absent') or {}).items():
        listed.append(dict(second_set='absent', role=role, rows=listing['rows'], ordinal_ranges=listing['ordinal_ranges']))
    differs = (lesson.get('alignment') or {}).get('differs') or []
    if differs:
        listed.append(dict(second_set='alignment', rows=len(differs), differs=differs))
    if lesson.get('key_cursor_differs'):
        listed.append(dict(second_set='key_cursor_differs', rows=len(lesson['key_cursor_differs']),
                           items=lesson['key_cursor_differs']))
    if lesson.get('mismatched_rows'):
        listed.append(dict(second_set='picture_identity_mismatch', rows=len(lesson['mismatched_rows']),
                           items=lesson['mismatched_rows']))
    if lesson.get('clock_after_cutoff'):
        listed.append(dict(second_set='clock_after_cutoff', items=lesson['clock_after_cutoff']))
    resolver = ((lesson.get('anchors_resolved') or {}).get('resolver') or {})
    if (resolver.get('counts') or {}).get('unresolved'):
        listed.append(dict(second_set='unresolved_plane_references', reasons=resolver.get('unresolved_reasons')))
    if (lesson.get('sidecar_check') or {}).get('status') == 'differs':
        listed.append(dict(second_set='sidecar_differs_from_teacher_receipt', check=lesson['sidecar_check']))
    return dict(checks=[], listed=listed, lesson=lesson)


def _second_set_text(learner_context, name):
    """The teacher's second set at this component's anchor rows (key, clocks, resolved planes, book columns), whole."""
    lesson = ((learner_context or {}).get('second_set') or {}).get('lesson') or {}
    if lesson.get('status') != 'carried':
        return None
    chosen = (lesson.get('component_anchors') or {}).get(name) or {}
    rows = (lesson.get('anchors_resolved') or {}).get('rows') or {}
    at = {kind: dict(cursor=cv[0], value=cv[1], second_set=rows.get(str(cv[0]))) for kind, cv in chosen.items()}
    return json.dumps(at, sort_keys=True, default=str)


def _carry_anchors(carry, anchors, wanted):
    """((pictures, statuses), note) when the teacher's carry holds every anchor this classroom computed (the same
    component, kind, cursor and value for every component) with its picture; else (None, why). Never raises."""
    try:
        held = (carry or {}).get('anchors')
        if not held:
            return None, 'the carry holds no anchors (a teacher that does not feed note_row)'
        mine = {name: {kind: [a['adapter_cursor'], a['value']] for kind, a in chosen.items()}
                for name, chosen in anchors.items() if chosen}
        theirs = {name: {kind: [int(v[0]), float(v[1])] for kind, v in slot.items()}
                  for name, slot in (held.get('components') or {}).items()}
        if mine != theirs:
            differs = sorted(set(mine) ^ set(theirs) | {n for n in set(mine) & set(theirs) if mine[n] != theirs[n]})
            return None, 'the carry\'s anchors differ from this classroom\'s for %d component(s): %s' % (
                len(differs), differs)
        pictures, statuses = held.get('pictures') or {}, held.get('statuses') or {}
        missing = sorted(c for c in wanted if c not in pictures or c not in statuses)
        if missing:
            return None, 'the carry lacks the pictures of %d anchor cursor(s): %s' % (len(missing), missing)
        return ({c: pictures[c] for c in wanted}, {c: statuses[c] for c in wanted}), (
            'carry anchors: %d (every anchor picture taken from the teacher\'s walk; the market timeline was not read '
            'again)' % len(wanted))
    except Exception as error:  # noqa: BLE001 - without the carry's anchors this read retains them itself
        return None, 'the carry\'s anchors are not usable (%s: %s)' % (type(error).__name__, error)


def _take_carry(carry, teacher_report, timeline, native, native_setup):
    """(True, note) when the teacher's carry stands in for this read's whole-source work: same identity as this reader,
    the teacher's report exhausted with the same identity, and the native entries' pass loaded (or not needed). Else
    (False, why). Never raises."""
    if carry is None:
        return False, dict(taken=False, reason='no teacher carry given (an older teacher, or none saved)')
    try:
        if carry.get('schema') != TEACHER_CARRY_SCHEMA or carry.get('identity') != timeline.identity:
            return False, dict(taken=False, reason='the teacher carry names another schema or source identity')
        if (not isinstance(teacher_report, dict) or teacher_report.get('identity') != timeline.identity
                or not source_exhausted(teacher_report, journal_count=timeline.source.get('journal_count'),
                                        record_count=timeline.source.get('record_count'))):
            return False, dict(taken=False, reason='the teacher\'s shared read is not this source exhausted')
        if native is not None:
            if carry.get('native') is None:
                return False, dict(taken=False, reason='the teacher carry holds no native pass (%s)' % carry.get('native_setup'))
            loaded, why = native.load_pass_state(carry['native'])
            if not loaded:
                return False, dict(taken=False, reason=why)
        return True, dict(taken=True, schema=TEACHER_CARRY_SCHEMA, pictures=carry.get('pictures'),
                          native=('loaded' if native is not None else 'not used: %s' % native_setup))
    except Exception as error:  # noqa: BLE001 - without the carry this read makes the whole pass
        return False, dict(taken=False, reason='%s: %s' % (type(error).__name__, error))


class ClassroomMarketContext:
    """Actual answer context: complete retained anchors plus access to the full exact source."""
    def __init__(self, calculations, day, retained):
        self.calculations, self.day, self.retained = calculations, day, retained
        self.picture_texts = None       # id(picture) -> (picture, text) while the component answers are written

    def prepare_picture_texts(self):
        """Encode every retained anchor picture once, on the lane (picture_texts); the component answers splice them.
        Returns the placement record (also on PINNING_RECORD['picture_texts'])."""
        self.picture_texts = picture_texts(self.retained['pictures'])
        return dict(PINNING_RECORD.get('picture_texts') or {})

    def release_picture_texts(self):
        self.picture_texts = None

    def iter_pictures(self):
        from frankie_box_market_timeline import SharedMarketTimeline
        # Efficiency (Greg, 2026-10-07): the sealed journal is measured in THIS process by the per-process,
        # changed-file-aware witness (frankie_box_filehash: one streamed sha256 per unchanged file, keyed on
        # path/device/inode/size/mtime/ctime), so a second reader open in the same process does not re-hash
        # tens of GB. The core still compares the witness to its pin and raises on a mismatch; the pin, the
        # identity and the chained head hash check are unchanged.
        from frankie_box_filehash import witness as measured
        journal = (self.retained.get('identity') or {}).get('journal') or {}
        witness = None
        if journal.get('path'):
            # bound to the measured file (review N1): the core accepts a caller's witness only for its pinned file
            stat = Path(journal['path']).stat()
            witness = dict(measured(journal['path']), path=journal['path'], dev=stat.st_dev, ino=stat.st_ino)
        reader = SharedMarketTimeline(self.calculations, day=self.day, workers=lane_workers(), input_witness=witness)
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

    def native_entries(self):
        """The six native entries' arithmetic, whole (every series, pair and cell), or None on a reading saved before it
        existed (named by native_entries_status)."""
        return self.retained.get('native_entries')

    def native_entries_status(self):
        result = self.retained.get('native_entries')
        if result is None:
            return dict(schema=NATIVE_ENTRY_SCHEMA, status='unavailable',
                        reason='the retained market reading was saved before the native entry arithmetic existed')
        return native_entries_compact(result)

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
                    arithmetic='the Dipole state counts, terminal state, first-to-last direction, Pearson and co-movement '
                               'use the teacher rows only; the six native entries\' own values read on this pass are the '
                               'operands of the native entry arithmetic (each series against every Dipole component, '
                               'dipole_classroom_external\'s equations); the Dipole values are not changed by them',
                    native_entries=self.native_entries_status(),
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


# ------------------------------------------- the six native entries as operands (Greg, 2026-10-07 night: "18 of 18")
# "Why is he only reading 12 of 18? We want 18 of 18." The six native-only entries that were context only now enter the
# classroom's arithmetic. Nothing new is invented: the operands are the native producers' own per-group values (the
# native member rows the shared reader yields at their GROUP_CLOSE emission, flattened by the joined teacher's leaf rule,
# frankie_box_joined_teacher._flatten: a mapping is walked by dotted key, a number or boolean is kept, a string is a
# category, a list is its length and stays whole in the picture; a FIFO queue list also enters per side and level,
# QUEUE_LEVEL_RULE below), the native lifecycle rows of the entry's own sections
# (counted per Dipole interval, the joined teacher's count-of-rows-in-the-window form), and the INPUT envelope's reset
# and session-scope carriers. The equations are the classroom's existing external-section arithmetic
# (dipole_classroom_external: the value in force at each Dipole row, _direction, _pair = relation, Pearson, co-movement),
# so each series is computed the way an external series is, against every Dipole component.
NATIVE_SIX = ('order_lifecycle_clears', 'contract_session_roll_state', 'complete_state_reset_bootstrap_receipts',
              'price_and_book_path', 'derived_price_flow_book_paths', 'derived_v4_mechanics_fifo_features')
NATIVE_ENTRY_SCHEMA = 'FRANKIE_CLASSROOM_NATIVE_ENTRY_ARITHMETIC_V1'
NATIVE_ENTRY_COMPUTATION = 'native_entry_arithmetic'
# the INPUT envelope's own carriers of three of the six (present on every picture, native pass or not): the thinner form
PICTURE_CARRIERS = {
    'order_lifecycle_clears': ('picture.reset_inputs',),
    'complete_state_reset_bootstrap_receipts': ('picture.reset_inputs',),
    'contract_session_roll_state': ('picture.session_scope_changes', 'picture.at.session_id', 'picture.at.source_member_index'),
}
PICTURE_SERIES_TEXT = {
    'picture.reset_inputs': 'INPUT pictures whose normalized action is R (the book clear / reset message), counted per '
                            'Dipole interval, per instrument',
    'picture.session_scope_changes': 'changes of (source_member_index, session_id) per instrument (the core\'s own '
                                     'source_scope_changed rule), counted per Dipole interval',
    'picture.at.session_id': 'the session_id in force per instrument at each Dipole row (a category: runs and cells)',
    'picture.at.source_member_index': 'the source member (DBN partition) index in force per instrument at each Dipole row '
                                      '(a category: runs and cells)',
}
NATIVE_ENTRY_RULE = ('a member value is placed at the INPUT cursor of its GROUP_CLOSE emission and is in force at every later '
                     'Dipole row until that instrument\'s next member row (the value in force, never backfilled; rows '
                     'carried forward are counted apart from rows with a new observation); a leaf missing from an '
                     'instrument\'s latest member row reads MISSING, never its older value; a lifecycle or envelope event '
                     'counts in the interval of the first Dipole row at or after its cursor (zero = measured none over the '
                     'exhausted source while the carrier was present); every series is per instrument (never pooled across '
                     'contracts); FINALIZE / unplaceable rows are counted and never placed; nothing averaged')


# Per-level FIFO queue lengths (Greg, 2026-10-07 night: "Do queue length however it will give a better output").
QUEUE_LEVEL_RULE = ('every list of book levels whose elements carry a fifo_queue list (book_full.bid_levels_full, '
                    'book_full.ask_levels_full, wherever the selected carrier holds one) adds one series per side and level: '
                    '<side>_levels_full[L<i>].fifo_queue#len = the number of orders queued at the i-th level of that list at '
                    'that instant, i counted from 1 in the producer\'s own level order (never re-sorted here; the V4 state '
                    'adapter lists each side from its best price outward, bids descending and asks ascending, '
                    'research/ng_exhaustion_mbo_v4_state_adapter_20260820.py _prices at this checkout; the pinned producers '
                    'checkout is not read here, so that order is carried as the producer\'s, not re-checked; L1 is the best '
                    'level at that instant, L2 the next, and so on: a distance from the best at each instant, not a fixed '
                    'price). The list\'s own '
                    'length series (#len, the number of levels) stays alongside. A level not present at an instant (the book '
                    'is shallower then) reads MISSING, never zero. As many levels as the data carries; no cap')
QUEUE_LEVEL_COST = ('expected, not measured: per member row, one extra leaf per level per side (depth D gives 2D series per '
                    'instrument); hot path about one dict write per level per member row plus a second walk of each selected '
                    'carrier\'s mappings (order of 1 to 3 minutes per 1M member rows at D = 100); memory at most n_dipole_rows x 17 bytes per series (about 170 MB per '
                    'instrument at D = 100 and 50k Dipole rows); 19 pairs per series after the pass (about 4 s per '
                    'instrument at D = 100 and 50k rows) and about 0.6 KB per pair in native-entry-arithmetic.json. No bound '
                    'is applied; if one is ever needed it is recorded here as a named limit, never a silent truncation')


def _queue_levels(node, prefix, out):
    """Per-level FIFO queue lengths under one selected carrier (QUEUE_LEVEL_RULE): mappings are walked by dotted key; a
    list whose elements are level mappings with a fifo_queue list yields one ('n', length) leaf per level, in list order.
    A level without a fifo_queue list yields nothing (it reads MISSING, never zero). Lists are not descended further."""
    if isinstance(node, dict):
        for key, value in node.items():
            _queue_levels(value, prefix + '.' + str(key) if prefix else str(key), out)
    elif isinstance(node, list):
        names = _LEVEL_NAMES.get(prefix)
        if names is None:
            names = _LEVEL_NAMES[prefix] = []
        for position, level in enumerate(node, 1):
            queue = level.get('fifo_queue') if isinstance(level, dict) else None
            if isinstance(queue, list):
                while len(names) < position:      # the leaf names of this list, built once per level (hot path)
                    names.append('%s[L%d].fifo_queue#len' % (prefix, len(names) + 1))
                out[names[position - 1]] = ('n', float(len(queue)))


# '<prefix>[L<i>].fifo_queue#len' per list prefix, index i - 1 (the same strings _queue_levels formatted per level before)
_LEVEL_NAMES = {}


# Identifiers among the carriers (review G-3): constant per instrument, so a series of them is degenerate. They are kept as
# identities per instrument (first / last value with cursors, every change with its cursor), as the search routes them.
IDENTITY_LEAVES = ('instrument_id', 'raw_symbol')
IDENTITY_RULE = ('instrument_id and raw_symbol are identities, not signals: recorded per instrument with first / last value '
                 'and every change (cursor, before, after) in native-entry-arithmetic.json; no numeric series or cell')


# The former cutoff (Greg, 2026-10-07 night) is RETIRED (Greg, 2026-10-09: "we can't make a size-based decision that
# makes science weaker"): the native entry arithmetic computes every series over every Dipole row, whatever the time or
# the memory it takes, and records both (elapsed native work, peak resident memory). The limits below are kept only as a
# recorded reading (a plan or an environment may still name them; they are listed, never applied); check_every is the
# probe's cadence in the pass. A series is listed unavailable only when its data is actually absent.
NATIVE_CUTOFF_DEFAULTS = dict(seconds=3600.0, rss_gb=48.0, check_every=10000)
NATIVE_CUTOFF_ENV = dict(seconds='FRANKIE_NATIVE_CUTOFF_SECONDS', rss_gb='FRANKIE_NATIVE_CUTOFF_RSS_GB',
                         check_every='FRANKIE_NATIVE_CUTOFF_CHECK_EVERY')
NATIVE_CUTOFF_RULE = ('no cutoff: the native entry work computes every series over every Dipole row; its time and '
                      'resident memory are read every check_every pictures in the pass and before every series after it, '
                      'for the probe and the record (elapsed native work, peak resident memory), never to stop it. The '
                      'seconds / rss_gb values are recorded as given and not applied (Greg, 2026-10-09)')


def native_cutoff_limits(environ=None):
    """The cutoff limits from the environment (NATIVE_CUTOFF_ENV), else NATIVE_CUTOFF_DEFAULTS; each with its source. A
    value that is not a positive number is not used: the default stands and the given value is listed."""
    environ = environ or {}
    out, listed = dict(rule=NATIVE_CUTOFF_RULE, env=dict(NATIVE_CUTOFF_ENV), source={}), []
    for key, default in NATIVE_CUTOFF_DEFAULTS.items():
        raw = environ.get(NATIVE_CUTOFF_ENV[key])
        value, source = default, 'default'
        if raw not in (None, ''):
            try:
                given = float(raw)
            except ValueError:
                given = None
            if given is not None and given > 0:
                value, source = (int(given) if key == 'check_every' else given), 'env ' + NATIVE_CUTOFF_ENV[key]
            else:
                listed.append(dict(env=NATIVE_CUTOFF_ENV[key], given=raw, reason='not a positive number; the default stands'))
        out[key], out['source'][key] = value, source
    out['check_every'] = max(1, int(out['check_every']))
    out['rss_bytes'] = int(out['rss_gb'] * 2 ** 30)
    out['listed'] = listed or None
    out['applied'] = False           # recorded, never a stop (NATIVE_CUTOFF_RULE)
    return out


def _rss_bytes():
    """(resident bytes of this process now, basis): /proc/self/statm, else the peak from getrusage. In a forked native
    series worker: the coordinator's resident bytes plus this worker's private pages (a forked worker maps the
    coordinator's pages shared, so its own statm would count them again); the classroom's footprint the limit guards."""
    import os
    coordinator = _RSS_COORDINATOR[0] if _RSS_COORDINATOR else None
    if coordinator is not None and coordinator != os.getpid():
        try:
            with open('/proc/%d/statm' % coordinator) as handle:
                resident = int(handle.read().split()[1]) * os.sysconf('SC_PAGE_SIZE')
            own = 0
            with open('/proc/self/smaps_rollup') as handle:
                for line in handle:
                    if line.startswith(('Private_Clean:', 'Private_Dirty:')):
                        own += int(line.split()[1]) * 1024
            return resident + own, ('coordinator resident (/proc/%d/statm) plus this worker\'s private pages '
                                    '(/proc/self/smaps_rollup)' % coordinator)
        except (OSError, ValueError, IndexError):
            pass
    try:
        with open('/proc/self/statm') as handle:
            return int(handle.read().split()[1]) * os.sysconf('SC_PAGE_SIZE'), 'current resident (/proc/self/statm)'
    except (OSError, ValueError, IndexError):
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024, 'peak resident (getrusage ru_maxrss)'


def _settle_numeric(s, limit):
    """Record a numeric series' state at the close of its open row (when that row is closed, i.e. below `limit`): one
    row with an update in its interval, and a run start when the state differs from the last recorded one. The same
    record the former per-row closing loop made."""
    k = s.open_k
    if k is None or k >= limit:
        return
    s.fresh += 1
    state = (s.code, s.value, s.reason)
    if state != s.rec:
        s.rows.append(k)
        s.codes.append(s.code)
        s.values.append(s.value if s.code == 0 else float('nan'))
        if s.code != 0:
            s.reasons[len(s.rows) - 1] = s.reason
        s.rec = state
    s.open_k = None


class _NumSeries:
    __slots__ = ('code', 'value', 'reason', 'rec', 'rows', 'codes', 'values', 'reasons', 'fresh', 'known', 'first', 'last',
                 'low', 'high', 'nonpresent', 'nulls', 'open_k')

    def __init__(self):
        from array import array
        self.code, self.value, self.reason, self.rec, self.open_k = None, None, None, None, None
        self.rows, self.codes, self.values, self.reasons = array('q'), array('b'), array('d'), {}
        self.fresh, self.known, self.first, self.last, self.low, self.high = 0, 0, None, None, None, None
        self.nonpresent, self.nulls = {}, 0


class _NativeEntryArithmetic:
    """One pass, inside the classroom's own full ordered read (market_context): the six entries' operands per Dipole row.

    `components`: the Dipole evidence (every component's observations, one shared adapter-cursor roster); `carriers`: the
    core's native carriers per entry (the ROOT projection plan's producers' crosswalk, else the retained carrier text);
    `layers`: the core's layer record (native.member / native.lifecycle present or absent, with the core's reason).
    Hot path: note() per picture is a few dict reads unless the picture carries a native update, an R action or a scope
    change. The per-row ledgers are stored as changes only (array-backed), materialized one series at a time at finish().
    """

    def __init__(self, components, carriers, layers, limits=None, online=False):
        """online (one pass, Greg 2026-10-09): the TEACHER's walk feeds note() over the same ordered pictures while the
        Dipole roster is still being made; the teacher declares each roster cursor (declare_row) before the picture
        that carries it, so every event lands on the row it would land on offline; end_online() closes the roster and
        moves what followed the last row to after_last. The classroom loads that pass state (load_pass_state) onto its
        own instance built from the Dipole components, checks the roster, and computes finish() unchanged."""
        self.status, self.reason = None, None
        self.online = online
        self.limits = limits or native_cutoff_limits({})
        self.cutoff, self.pictures, self.finish_clock = None, 0, None
        self.peak_rss, self.peak_rss_basis, self.peak_rss_phase = 0, None, None     # the largest reading _check took
        import threading
        self._probe_lock, self._probe_at = threading.Lock(), float('-inf')    # the stage-progress probe (_check)
        self.components = [(c['name'], c['observations']) for c in components]
        roster = [int(p['cursor']) for p in (self.components[0][1] if self.components else ())]
        for name, observations in (() if online else self.components):
            if [int(p['cursor']) for p in observations] != roster:
                self.status, self.reason = 'integrity_failure', ('the Dipole components do not share one cursor roster '
                                                                 '(%s differs); no row to align the native series on' % name)
        if not online and self.status is None and any(a >= b for a, b in zip(roster, roster[1:])):
            self.status, self.reason = 'integrity_failure', 'the Dipole cursor roster is not strictly increasing'
        if not online and self.status is None and not roster:
            self.status, self.reason = 'unavailable', 'no Dipole row on this day: no row to place a native value at'
        self.cursors, self.n, self.k, self.last_cursor, self.at_cursor = roster, len(roster), 0, None, None
        # the row index at or past which an event follows the last Dipole row: n offline; unknown (never) while the
        # teacher's walk is still making the roster (online); end_online() sets it
        self.limit = float('inf') if online else self.n
        if online:
            self.n = None
        self.layers = {name: dict(status=(layers.get(name) or {}).get('status', 'absent'),
                                  reason=(layers.get(name) or {}).get('reason')) for name in ('native.member', 'native.lifecycle')}
        self.carriers = {}
        self.head_entries, self.section_entries = {}, {}
        for entry in NATIVE_SIX:
            spec = (carriers or {}).get(entry) or ALL99.NATIVE_SERIES.get(entry) or {}
            heads = sorted({ALL99._member_head(p) for p in spec.get('member') or ()})
            sections = sorted(set(spec.get('sections') or ()))
            self.carriers[entry] = dict(member=list(spec.get('member') or ()), heads=heads, sections=sections,
                                        source=spec.get('source') or 'frankie_box_all99_coverage.NATIVE_SERIES')
            for head in heads:
                self.head_entries.setdefault(head, []).append(entry)
            for section in sections:
                self.section_entries.setdefault(section, []).append(entry)
        self.heads = sorted(self.head_entries)
        self.identity_heads = [leaf for leaf in IDENTITY_LEAVES if leaf in self.head_entries]
        self.num, self.cat, self.cnt = {}, {}, {}
        self.after_last = {}
        self.member_keys, self.scopes, self.identities = {}, {}, {}
        self.unplaced = {}
        self.member_rows, self.lifecycle_rows, self.reset_inputs = 0, 0, 0
        self.lifecycle_other_sections = 0
        self.note_seconds = 0.0          # hot-path time inside the classroom's pass (measured on the one-day canary)
        import math
        from frankie_box_joined_teacher import _flatten     # the joined teacher's leaf rule, reused (never restated)
        self._flatten, self._isfinite = _flatten, math.isfinite

    def __getstate__(self):
        """Picklable (the teacher's walk saves its online pass with each raw save, teacher resume 2026-10-09): the
        probe's lock is not state; a restored instance gets a fresh one."""
        state = dict(self.__dict__)
        state.pop('_probe_lock', None)
        return state

    def __setstate__(self, state):
        import threading
        self.__dict__.update(state)
        self._probe_lock = threading.Lock()

    # ---- hot path
    def note(self, picture, evidence):
        if self.status is not None:
            return
        self.pictures += 1
        if self.pictures % self.limits['check_every'] == 0 and self._check('pass'):
            return                                      # cutoff: stop feeding; what was closed is computed at finish()
        at = picture.get('at') or {}
        cursor = at.get('adapter_cursor')
        self.at_cursor = cursor if type(cursor) is int else None     # facts name the picture's own cursor (None: none)
        if type(cursor) is int:
            if self.last_cursor is not None and cursor < self.last_cursor:
                self.status, self.reason = 'integrity_failure', ('adapter cursor %d follows %d in the ordered source; '
                                                                 'native series are never re-sorted' % (cursor, self.last_cursor))
                return
            self.last_cursor = cursor
            if self.k < len(self.cursors) and self.cursors[self.k] < cursor:
                # every Dipole row before this cursor closes at once (bisect over the sorted roster; was a per-row loop)
                self.k = bisect.bisect_left(self.cursors, cursor, self.k)
        instrument = at.get('instrument_id')
        # the envelope carriers on exact pictures only (the core's own rule for reset / source_scope_changed)
        if type(instrument) is int and (picture.get('coverage') or {}).get('exact_clocks'):
            normalized = evidence.get('normalized') if isinstance(evidence, dict) else None
            action = normalized.get('action') if normalized else None
            if action in ('R', b'R'):
                self.reset_inputs += 1
                self._count(('picture.reset_inputs', instrument))
            scope = (at.get('source_member_index'), at.get('session_id'))
            previous = self.scopes.get(instrument)
            if previous is not None and previous != scope:
                self._count(('picture.session_scope_changes', instrument))
            self.scopes[instrument] = scope
            for field in ('session_id', 'source_member_index'):
                if at.get(field) is not None:        # not carried on this INPUT is not a change of state
                    self._category(('picture.at.' + field, instrument), at.get(field))
        for update in picture.get('updates') or ():
            source = update.get('source')
            if source not in ('native.member', 'native.lifecycle'):
                continue
            if update.get('placement'):
                self.unplaced[source] = self.unplaced.get(source, 0) + 1
                continue
            row, owner = update.get('value') or {}, update.get('instrument_id')
            if source == 'native.member':
                self.member_rows += 1
                self._member(row, owner)
            else:
                self.lifecycle_rows += 1
                section = row.get('emitting_section')
                if section in self.section_entries:
                    self._count(('native.lifecycle.' + str(section), owner))
                else:
                    self.lifecycle_other_sections += 1
        if type(cursor) is int and self.k < len(self.cursors) and self.cursors[self.k] == cursor:
            self._close_row()

    def _count(self, key):
        slot = self.cnt.get(key)
        if slot is None:
            from array import array
            slot = self.cnt[key] = dict(total=0, first=None, last=None, rows=array('q'), counts=array('q'))
        k = self.k
        if k >= self.limit:
            self.after_last[key] = self.after_last.get(key, 0) + 1
        elif slot['rows'] and slot['rows'][-1] == k:
            slot['counts'][-1] += 1             # the event's interval = the row it is closed with (no per-row loop)
        else:
            slot['rows'].append(k)
            slot['counts'].append(1)
        slot['total'] += 1
        cursor = self.at_cursor
        if slot['first'] is None:
            slot['first'] = cursor
        slot['last'] = cursor

    def _category(self, key, value):
        value = None if value is None else str(value)
        slot = self.cat.get(key)
        if slot is None:
            if value is None:
                return
            slot = self.cat[key] = dict(current=None, rec=None, changes=[], distinct=set(), known=0, open_k=None)
        if value is not None:
            slot['known'] += 1
            slot['distinct'].add(value)
        k = self.k
        if k >= self.limit:
            return                                  # after the last Dipole row: no row closes with it
        if slot['open_k'] != k:
            self._settle_category(slot, self.limit)     # the previous row's last value, recorded once (no per-row loop)
            slot['open_k'] = k
        slot['current'] = value

    def _numeric(self, key, code, value, reason):
        s = self.num.get(key)
        if s is None:
            s = self.num[key] = _NumSeries()
        k = self.k
        if k < self.limit:
            if s.open_k != k:
                _settle_numeric(s, self.limit)      # the previous row's last state, recorded once (no per-row loop)
                s.open_k = k
            s.code, s.value, s.reason = code, value, reason
        if code == 0:
            s.known += 1
            point = (self.at_cursor, value)
            if s.first is None:
                s.first = point
            s.last = point
            if s.low is None or value < s.low[1]:
                s.low = point
            if s.high is None or value > s.high[1]:
                s.high = point
        else:
            s.nonpresent[reason] = s.nonpresent.get(reason, 0) + 1

    def _member(self, row, instrument):
        _flatten, isfinite = self._flatten, self._isfinite
        leaves = {}
        for head in self.heads:
            node, found = row, True
            for part in head.split('.'):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    found = False
                    break
            if found:
                _flatten(node, head, leaves)
                _queue_levels(node, head, leaves)       # per-level FIFO queue lengths beside the list's own length
        for leaf in self.identity_heads:
            # an identifier is not a signal (review G-3): recorded per instrument with its changes, never a numeric series
            if leaves.pop(leaf, None) is not None or leaf in row:
                self._identity(instrument, leaf, row.get(leaf))
        seen = self.member_keys.setdefault(instrument, set())
        for leaf in seen - leaves.keys():
            key = ('native.member.row.' + leaf, instrument)
            if key in self.num:
                self._numeric(key, 1, None, 'NOT_IN_THIS_INSTRUMENT_LATEST_MEMBER_ROW')
            if key in self.cat:
                self._category(key, None)
        for leaf, (kind, value) in leaves.items():
            key = ('native.member.row.' + leaf, instrument)
            if kind == 'n':
                if isfinite(value):
                    self._numeric(key, 0, value, None)
                else:
                    self._numeric(key, 2, None, 'NOT_FINITE: %r' % value)
            elif kind == 's':
                self._category(key, value)
            else:                                        # a null leaf: MISSING where a series exists, else counted
                if key in self.num:
                    self._numeric(key, 1, None, 'VALUE_IS_NULL_IN_MEMBER_ROW')
                if key in self.cat:
                    self._category(key, None)
                if key not in self.num and key not in self.cat:
                    self.unplaced['null_leaf_before_any_value'] = self.unplaced.get('null_leaf_before_any_value', 0) + 1
        seen.update(leaves)

    def _check(self, phase):
        """The probe and the record, never a stop (the cutoff is retired, NATIVE_CUTOFF_RULE): reads the elapsed native
        work and the resident memory, reports them on the heartbeat, keeps the peak reading, and returns False. Elapsed =
        this work's own time in the pass plus the time since finish() began."""
        import time
        elapsed = self.note_seconds + (time.monotonic() - self.finish_clock if self.finish_clock is not None else 0.0)
        rss, basis = _rss_bytes()
        if rss > self.peak_rss:
            self.peak_rss, self.peak_rss_basis, self.peak_rss_phase = rss, basis, phase
        # Greg's probes on every step: the stage's own phase for the parent's heartbeat. _check also runs in the pair
        # threads (before every series), so the report is throttled to one per second under a lock (one writer of the
        # pid's pending file at a time). A probe never changes the pass.
        # Stacks pass (2026-10-07): only the coordinator writes it (a forked series worker's own count would alternate
        # with the coordinator's and hide a stall), and after the pass the units are the series completed, not the
        # pictures fed (constant then, so a 10-minute series phase read as STALLED).
        import os
        coordinator = _RSS_COORDINATOR[0] if _RSS_COORDINATOR else os.getpid()
        with self._probe_lock:
            now = time.monotonic()
            if now - self._probe_at >= 1.0 and os.getpid() == coordinator:
                self._probe_at = now
                if phase == 'pass':
                    heartbeat('classroom native entries: pass', self.pictures, unit='pictures', rss_bytes=rss,
                           native_elapsed_s=round(elapsed, 1))
                else:
                    heartbeat('classroom native entries: series', getattr(self, 'series_done', 0),
                           getattr(self, 'series_total', None), unit='series', rss_bytes=rss,
                           native_elapsed_s=round(elapsed, 1))
        return False

    # ---- one pass (Greg, 2026-10-09): the teacher's walk feeds this pass; the classroom computes
    PASS_FIELDS = ('status', 'reason', 'cutoff', 'pictures', 'k', 'last_cursor', 'at_cursor', 'num', 'cat', 'cnt',
                   'after_last', 'member_keys', 'scopes', 'identities', 'unplaced', 'member_rows', 'lifecycle_rows',
                   'reset_inputs', 'lifecycle_other_sections', 'note_seconds')

    def declare_row(self, cursor):
        """Online: the teacher's walk names a Dipole roster cursor before note() sees the picture that carries it."""
        if self.cursors and cursor <= self.cursors[-1]:
            if self.status is None:
                self.status, self.reason = 'integrity_failure', 'the Dipole cursor roster is not strictly increasing'
            return
        self.cursors.append(int(cursor))

    def end_online(self):
        """Online: the roster is complete. Events counted on the row past the last one move to after_last (where the
        offline pass counts them); every other series state is already what the offline pass holds."""
        self.n = len(self.cursors)
        self.limit = self.n
        for key, slot in self.cnt.items():
            while slot['rows'] and slot['rows'][-1] >= self.n:
                slot['rows'].pop()
                self.after_last[key] = self.after_last.get(key, 0) + slot['counts'].pop()
        if self.cutoff is not None:
            self.cutoff['dipole_rows'] = self.n
            self.reason = (self.reason or '').replace('of None Dipole rows', 'of %d Dipole rows' % self.n)
        self.online = False

    def pass_state(self):
        """The pass's state (picklable), with the roster and the carriers/layers it was made against."""
        state = {name: getattr(self, name) for name in self.PASS_FIELDS}
        state.update(cursors=list(self.cursors), carriers=self.carriers, layers=self.layers, limits=self.limits,
                     peak_rss=self.peak_rss, peak_rss_basis=self.peak_rss_basis, peak_rss_phase=self.peak_rss_phase)
        return state

    def load_pass_state(self, state):
        """Take a pass made by the teacher's walk over the same ordered source. (True, None) when loaded or when this
        instance's own construction already decided its status (an integrity failure or no Dipole row: the offline
        pass would feed nothing); else (False, why) and the caller makes its own pass. Never raises."""
        if self.status is not None:
            return True, 'not needed: %s at construction (%s)' % (self.status, self.reason)
        try:
            if list(state['cursors']) != list(self.cursors):
                return False, 'the teacher walk\'s roster differs from this classroom\'s Dipole roster'
            if state['carriers'] != self.carriers or state['layers'] != self.layers:
                return False, 'the teacher walk\'s native carriers or layers differ from this classroom\'s'
            if state.get('cutoff') is not None or state.get('status') == 'cutoff':
                # a pass saved under the retired cutoff stopped feeding early: never computed over a part of the day
                return False, ('the teacher walk\'s pass stopped at the retired cutoff (%s); the classroom makes its own '
                               'full pass' % (state.get('reason') or state.get('cutoff')))
            values = {name: state[name] for name in self.PASS_FIELDS}       # every field present before any is set
            for name, value in values.items():
                setattr(self, name, value)
            if (state.get('peak_rss') or 0) > self.peak_rss:
                self.peak_rss, self.peak_rss_basis = state['peak_rss'], state.get('peak_rss_basis')
                self.peak_rss_phase = 'teacher walk: %s' % state.get('peak_rss_phase')
        except (KeyError, TypeError) as error:
            return False, 'the teacher carry is malformed (%s: %s)' % (type(error).__name__, error)
        return True, None

    def _identity(self, instrument, leaf, value):
        slot = self.identities.setdefault(instrument, {}).get(leaf)
        if slot is None:
            self.identities[instrument][leaf] = dict(first=[self.at_cursor, value], last=[self.at_cursor, value],
                                                     changes=0, rows=1)
            return
        slot['rows'] += 1
        if slot['last'][1] != value:
            slot['changes'] += 1
            slot.setdefault('change_cursors', []).append([self.at_cursor, slot['last'][1], value])
        slot['last'] = [self.at_cursor, value]

    def _close_row(self):
        # Rows are recorded lazily (each series settles its last state of a row when a later row first touches it, and
        # at _compute), so closing a row is advancing the row index: the values are those the per-row loop recorded.
        self.k += 1

    @staticmethod
    def _settle_category(slot, limit):
        k = slot['open_k']
        if k is not None and k < limit and slot['current'] != slot['rec']:
            slot['changes'].append((k, slot['current']))
            slot['rec'] = slot['current']

    # ---- after the pass
    def finish(self):
        """Close the rows no picture reached (lawful: every picture had a smaller cursor), then compute."""
        import time
        started = self.finish_clock = time.monotonic()
        if self.status is None:
            self.k = self.n                         # the rows no picture reached close with what they hold
        # a cutoff in the pass computes what it holds over the rows it closed; a cutoff after it keeps what is done
        result = (self._compute() if self.status in (None, 'cutoff')
                  else _native_unavailable_entries(self.status, self.reason))
        out = dict(schema=NATIVE_ENTRY_SCHEMA, computation=NATIVE_ENTRY_COMPUTATION, author=AUTHOR, model_calls=0,
                   status=self.status or 'computed', reason=self.reason, entries_computed=list(NATIVE_SIX),
                   dipole_rows=self.n, dipole_components=[name for name, _ in self.components],
                   layers=self.layers, carriers=self.carriers,
                   read=dict(member_rows=self.member_rows, lifecycle_rows=self.lifecycle_rows,
                             lifecycle_rows_of_other_sections=self.lifecycle_other_sections,
                             reset_inputs=self.reset_inputs, unplaced=dict(self.unplaced),
                             events_after_last_dipole_row={'%s@instrument=%s' % k: v for k, v in sorted(
                                 self.after_last.items(), key=lambda kv: (kv[0][0], str(kv[0][1])))}),
                   rule=NATIVE_ENTRY_RULE,
                   equations=('dipole_classroom_external (the external section\'s own functions): the value in force at '
                              'each Dipole row; state counts, terminal state, first-to-last PRESENT direction (_direction); '
                              'per series x Dipole component: direction relation, Pearson over both-PRESENT rows, '
                              'co-movement counts (_pair). Categories: runs over the Dipole rows and, per value (a cell), '
                              'each Dipole component\'s rows, PRESENT count and first-to-last direction inside the cell'),
                   leaf_rule=('frankie_box_joined_teacher._flatten: mapping walked by dotted key; number / boolean kept; '
                              'string = category; list = its length (#len), the list itself stays whole in the picture. '
                              'Plus FIFO queues per level (Greg, 2026-10-07 night): ' + QUEUE_LEVEL_RULE),
                   limit=('descriptive for this day\'s window; no causation or outcome claimed (R01, R02); a list carrier '
                          'enters as its length, and a FIFO queue also per level (its length at that level), not order by '
                          'order; no level cap is applied (expected cost in queue_level_cost); lifecycle rows '
                          'enter as their count per Dipole interval, their fields stay in the pictures; the leaf rule '
                          'carries numbers as float64, so an integer above 2**53 (a ns clock, an id) is not exact in the '
                          'arithmetic (it stays exact in the picture and the ledger)'),
                   **result)
        out['seconds'] = round(time.monotonic() - started, 3)
        out['hot_path_seconds'] = round(self.note_seconds, 3)
        out['pair_threads'] = getattr(self, 'pair_threads', None)
        out['queue_level_cost'] = QUEUE_LEVEL_COST
        out['cutoff'] = self.cutoff                     # always None: the cutoff is retired (NATIVE_CUTOFF_RULE)
        out['cutoff_limits'] = self.limits              # recorded as given, applied: False
        import resource
        out['peak_rss'] = dict(
            sampled_bytes=self.peak_rss or None, sampled_basis=self.peak_rss_basis, sampled_phase=self.peak_rss_phase,
            process_max_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            largest_worker_max_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024 or None,
            basis=('sampled: the largest _check reading (every check_every pictures in the pass, before every series '
                   'after it); process_max: getrusage ru_maxrss of this process; largest_worker_max: ru_maxrss of the '
                   'largest waited-for child (a forked series worker counts the pages it shares with this process)'))
        out['elapsed_native_seconds'] = round(self.note_seconds + (time.monotonic() - started), 3)
        out['status'] = self.status or 'computed'       # a cutoff reached after the pass shows here too
        out['reason'] = self.reason
        out['timing'] = ('hot_path_seconds: note() inside the classroom\'s one ordered pass (part of read.seconds); seconds: '
                         'the per-series materialization and the pairs after the pass')
        return out

    def _compute(self):
        import frankie_box_classroom_external_code as KX
        from frankie_box_joined_teacher import CATEGORY_LIMIT
        EXT = KX._external_math()
        np = EXT._np()
        n = self.k              # the Dipole rows closed: all of them, or those before a cutoff in the pass
        dipole = {}
        for name, observations in self.components:
            observations = observations[:n]
            codes = np.array([STATES.index(p['state']) for p in observations], dtype=np.int8)
            values = np.array([float(p['value']) if p['state'] == 'PRESENT' else np.nan for p in observations], dtype=np.float64)
            dipole[name] = (codes, values, EXT._direction(np, codes, values))
        cursors = np.array(self.cursors[:n], dtype=np.int64)
        # settle each series' last open row when it is a closed row (a row at or past n is not closed: never recorded)
        for item in self.num.values():
            _settle_numeric(item, n)
        for slot in self.cat.values():
            self._settle_category(slot, n)
        rows = np.arange(n)
        series = []

        def name_of(key):
            return '%s@instrument=%s' % key

        def numeric(name, kind, codes, values, extra):
            direction = EXT._direction(np, codes, values)
            counts = {state: int(np.sum(codes == i)) for i, state in enumerate(STATES)}
            last = int(n - 1)
            pairs = [EXT._pair(np, name, comp, 'NATIVE_ENTRY_DIPOLE', (codes, values, direction), dipole[comp])
                     for comp, _ in self.components]
            return dict(name=name, kind=kind, state_counts=counts, terminal_state=STATES[int(codes[last])],
                        terminal_value=(float(values[last]) if int(codes[last]) == 0 else None),
                        first_to_last_present_direction=direction, pairs=pairs, **extra)

        def member_series(key):
            s = self.num[key]
            change_rows = np.frombuffer(s.rows, dtype=np.int64) if len(s.rows) else np.zeros(0, np.int64)
            position = np.searchsorted(change_rows, rows, side='right') - 1
            seen = position >= 0
            codes = np.full(n, 1, dtype=np.int8)
            values = np.full(n, np.nan, dtype=np.float64)
            if len(s.rows):
                codes[seen] = np.frombuffer(s.codes, dtype=np.int8)[position[seen]]
                values[seen] = np.frombuffer(s.values, dtype=np.float64)[position[seen]]
            reasons = {}
            for index, reason in s.reasons.items():
                start = int(s.rows[index])
                end = int(s.rows[index + 1]) if index + 1 < len(s.rows) else n
                reasons[reason] = reasons.get(reason, 0) + end - start
            before = int(np.sum(~seen))
            if before:
                reasons['NO_VALUE_AT_OR_BEFORE_THIS_ROW'] = before
            return numeric(name_of(key), 'member_value', codes, values, dict(
                facts=dict(values_known=s.known, first=s.first, last=s.last, lowest=s.low, highest=s.high,
                           nonpresent_updates=dict(sorted(s.nonpresent.items())),
                           # a row whose interval held an update of this series (a new member row, PRESENT or not)
                           # versus a row that carries the value of an earlier interval forward (never shown as new)
                           rows_with_an_update_in_their_interval=s.fresh, rows_carried_forward=int(np.sum(seen)) - s.fresh,
                           runs=len(s.rows)),
                nonpresent_rows_by_reason=dict(sorted(reasons.items()))))

        def count_series(key):
            slot = self.cnt[key]
            values = np.zeros(n, dtype=np.float64)       # zero = no event in the interval over the exhausted source
            event_rows = np.frombuffer(slot['rows'], dtype=np.int64) if len(slot['rows']) else np.zeros(0, np.int64)
            event_counts = np.frombuffer(slot['counts'], dtype=np.int64) if len(slot['counts']) else np.zeros(0, np.int64)
            closed = event_rows < n                      # an interval of a row not closed (cutoff) is not counted
            event_rows, event_counts = event_rows[closed], event_counts[closed]
            values[event_rows] = event_counts
            codes = np.zeros(n, dtype=np.int8)
            busiest = int(np.argmax(event_counts)) if event_counts.size else None    # the first interval with the most
            return numeric(name_of(key), 'events_per_dipole_interval', codes, values, dict(facts=dict(
                events=slot['total'], first_event_cursor=slot['first'], last_event_cursor=slot['last'],
                intervals_with_events=int(event_rows.size), after_last_dipole_row=self.after_last.get(key, 0),
                largest_interval=(dict(row_cursor=int(cursors[event_rows[busiest]]), events=int(event_counts[busiest]))
                                  if busiest is not None else None))))

        def category_series(key):
            slot = self.cat[key]
            changes = slot['changes']
            item = dict(name=name_of(key), kind='category', values_known=slot['known'], distinct=len(slot['distinct']),
                        runs=len(changes))
            if not changes:
                item.update(rows_before_first_value=n, segments=[], cells=[])
                return item
            starts = [k for k, _ in changes]
            ends = starts[1:] + [n]
            segments = [dict(value=v, first_cursor=int(cursors[a]), last_cursor=int(cursors[b - 1]), rows=b - a)
                        for (a, v), b in zip(changes, ends)]
            item['rows_before_first_value'] = starts[0]
            if len(slot['distinct']) > CATEGORY_LIMIT:
                # the joined teacher's rule: more distinct values than its limit is an identifier, not a cell
                item.update(identifier=True, cells=[], segments=dict(count=len(segments), first=segments[0], last=segments[-1]),
                            reason='more than %d distinct values: an identifier, not a cell (joined teacher CATEGORY_LIMIT)'
                                   % CATEGORY_LIMIT)
                return item
            label = np.full(n, -1, dtype=np.int64)
            names = sorted({v for _, v in changes if v is not None})
            index = {v: i for i, v in enumerate(names)}
            for (a, v), b in zip(changes, ends):
                label[a:b] = index[v] if v is not None else -1
            cells = []
            for v in names:
                mask = label == index[v]
                cell = dict(value=v, rows=int(np.sum(mask)), components={})
                for comp, (codes, values, _) in dipole.items():
                    sub_codes, sub_values = codes[mask], values[mask]
                    cell['components'][comp] = dict(rows=int(mask.sum()), present=int(np.sum(sub_codes == 0)),
                                                    first_to_last_present_direction=EXT._direction(np, sub_codes, sub_values))
                cells.append(cell)
            item.update(segments=segments, cells=cells)
            return item

        def not_computed(key, kind):
            return dict(name=name_of(key), kind=kind, status='unavailable',
                        reason='cutoff: %s' % self.reason if self.status == 'cutoff' else 'no Dipole row was closed')

        def run(job):
            """One series, or the NOT_COMPUTED marker (the parent names it with the one cutoff reason at the end)."""
            function, key, kind, phase = job
            if n == 0 or self._check(phase):
                return _NOT_COMPUTED
            return function(key)

        # Every series is independent and read-only over the pass's state (numeric members, event counts, categories,
        # the per-level FIFO queue series among them). Greg, 2026-10-07 night ("CPU calls for multiple processes, not
        # one process with threads"; the September 29 pattern: spread workers, a dead worker never stops or hangs a
        # stage): the series run on a pinned FORK pool over the booked CPUs (frankie_box_lane_pin.ordered_map: one
        # worker per CPU, physical cores first; ordered results; a dead worker's chunk is redone and the window shrinks
        # by one), the pass's state shared copy-on-write (gc.freeze, so a child's collector never touches the parent's
        # pages), each chunk of series computed by the SAME functions in sorted series order and placed back in that
        # order, so every series is the one a single thread computes. Fork is taken only on Linux while this process
        # runs one thread (a bounded wait for the reader's finished helper threads); otherwise the former pinned thread
        # pool runs (recorded). The cutoff: a worker that reaches it sets a shared flag (the others stop feeding) and
        # hands its record back; the coordinator adopts the first one, and every series left uncomputed is named
        # unavailable: cutoff with that one reason, as before.
        jobs = ([(member_series, key, 'member_value', 'pairs') for key in sorted(self.num, key=lambda k: (k[0], str(k[1])))]
                + [(count_series, key, 'events_per_dipole_interval', 'pairs')
                   for key in sorted(self.cnt, key=lambda k: (k[0], str(k[1])))]
                + [(category_series, key, 'category', 'categories')
                   for key in sorted(self.cat, key=lambda k: (k[0], str(k[1])))])
        lane = lane_cpus()
        self.pair_threads = max(1, min(len(lane), len(jobs) or 1))     # the booked CPUs (16 or 32)
        LP = _lane_pin()
        # the pairs' dot products carry the bits of exactly 32 OpenBLAS threads on every lane, settled once here before
        # any worker starts (EXT.blas_reduction: one OpenBLAS thread per caller + the proven 32-thread reduction order,
        # or 32 threads as they are when the self-check fails; a fork inherits the setting); received.cpu_pinning
        PINNING_RECORD['blas_reduction'] = EXT.blas_reduction()
        results = _native_series_parallel(self, run, jobs, lane, LP) if jobs else []
        if any(_is_not_computed(value) for value in results) and self.status != 'cutoff' and n > 0:
            # a worker reached the cutoff but its record was lost with it: the coordinator's own check names the limit
            if not self._check('pairs'):
                self.cutoff = dict(limit='reported_by_a_lost_worker', phase='pairs', cursor_reached=self.last_cursor,
                                   dipole_rows_closed=self.k, dipole_rows=self.n, pictures_fed=self.pictures,
                                   limits={k: self.limits[k] for k in ('seconds', 'rss_gb', 'check_every')})
                self.status, self.reason = 'cutoff', ('cutoff reached by a worker that was lost before handing its record '
                                                      'back; a named limit, not an integrity failure')
        series.extend(not_computed(job[1], job[2]) if _is_not_computed(value) else value
                      for job, value in zip(jobs, results))
        # attribution: a series belongs to every one of the six whose own carrier it is
        entries = {}
        # after a cutoff in the pass, an absence is measured only over the pictures fed before it
        partial = ('' if not (self.status == 'cutoff' and (self.cutoff or {}).get('phase') == 'pass') else
                   '; measured only up to the cutoff (adapter cursor %s), not over the whole day' % self.last_cursor)
        for entry in NATIVE_SIX:
            spec = self.carriers[entry]
            own, thin, stopped = [], [], []
            for s in series:
                base = s['name'].split('@', 1)[0]
                if s.get('status') == 'unavailable':
                    target = stopped                   # a series the cutoff left uncomputed (named in the file)
                else:
                    target = None
                if base.startswith('native.member.row.'):
                    leaf = base[len('native.member.row.'):]
                    if any(leaf == h or leaf.startswith(h + '.') or leaf.startswith(h + '#') or leaf.startswith(h + '[')
                           for h in spec['heads']):
                        (target if target is not None else own).append(s['name'])
                elif base.startswith('native.lifecycle.'):
                    if base[len('native.lifecycle.'):] in spec['sections']:
                        (target if target is not None else own).append(s['name'])
                elif base in PICTURE_CARRIERS.get(entry, ()):
                    (target if target is not None else thin).append(s['name'])
            missing, mine = [], set(own + thin)
            # a series the cutoff left uncomputed is not a measured absence: those carriers are listed as cutoff below
            if spec['heads'] and not any(x.startswith('native.member.') for x in own + stopped):
                missing.append(dict(carrier='native.member ' + ', '.join(spec['heads']), reason=(
                    'the native member ledger is absent on this ROOT: %s' % self.layers['native.member']['reason']
                    if self.layers['native.member']['status'] != 'present' else
                    'no member row of this day carried these fields (a measurement over the exhausted ledger)' + partial)))
            if spec['sections'] and not any(x.startswith('native.lifecycle.') for x in own + stopped):
                missing.append(dict(carrier='native.lifecycle ' + ', '.join(spec['sections']), reason=(
                    'the native lifecycle ledger is absent on this ROOT: %s' % self.layers['native.lifecycle']['reason']
                    if self.layers['native.lifecycle']['status'] != 'present' else
                    'no lifecycle row of these sections was placed on this day (a measurement)' + partial)))
            for carrier in PICTURE_CARRIERS.get(entry, ()):
                if not any(x.split('@', 1)[0] == carrier for x in thin + stopped):
                    missing.append(dict(carrier=carrier, reason='no such event or value on this day\'s INPUT pictures (a measurement)'
                                        + partial))
            if stopped:
                missing.append(dict(carrier='%d series of this entry' % len(stopped), reason='unavailable: cutoff (%s)' % (
                    (self.cutoff or {}).get('limit') or self.reason)))
            if self.status == 'cutoff' and n < self.n:
                missing.append(dict(carrier='Dipole rows %d to %d' % (n, self.n - 1), reason='unavailable: cutoff (%s); the '
                                    'computed series cover the first %d rows only' % ((self.cutoff or {}).get('limit'), n)))
            form = 'own_rows' if own else ('thin_carrier' if thin else None)
            entries[entry] = dict(use='computed' if form else 'unavailable', form=form,
                                  own_series=own, thin_series=thin, series=len(own) + len(thin),
                                  not_computed_series=stopped, not_computed=len(stopped),
                                  rows_covered=n, rows=self.n,
                                  pairs=sum(len(s.get('pairs') or ()) for s in series if s['name'] in mine),
                                  unavailable=missing or None,
                                  picture_carriers={c: PICTURE_SERIES_TEXT[c] for c in PICTURE_CARRIERS.get(entry, ())} or None,
                                  reason=None if form else '; '.join(m['reason'] for m in missing))
        for entry in NATIVE_SIX:
            leaves = [leaf for leaf in IDENTITY_LEAVES if leaf in self.carriers[entry]['heads']]
            if leaves:
                entries[entry]['identities'] = dict(leaves=leaves, instruments=sum(
                    1 for item in self.identities.values() if any(leaf in item for leaf in leaves)),
                    rule=IDENTITY_RULE)
        return dict(series=series, entries=entries,
                    series_count=sum(1 for s in series if s.get('status') != 'unavailable'),
                    series_not_computed=sum(1 for s in series if s.get('status') == 'unavailable'),
                    rows_covered=n, pair_count=sum(len(s.get('pairs') or ()) for s in series),
                    identities={str(k): v for k, v in sorted(self.identities.items(), key=lambda kv: str(kv[0]))})


# ---- the native series on pinned processes (Greg, 2026-10-07 night: the September 29 pattern for every serial walk) --
# A series job returns its dict, or this marker when the cutoff stopped it (a string: it survives the trip back from a
# worker; no series dict ever equals it). The coordinator names every marked series unavailable: cutoff with the one
# reason it adopted.
_NOT_COMPUTED = '__frankie_native_series_not_computed__'
_NATIVE_SHARED = {}
_RSS_COORDINATOR = []        # [coordinator pid] while forked series workers run (their memory reading, _rss_bytes)
FORK_READY_WAIT_SECONDS = 10.0


def _is_not_computed(value):
    return isinstance(value, str) and value == _NOT_COMPUTED


def _fork_ready(wait=FORK_READY_WAIT_SECONDS):
    """(True, seconds waited, None) when this Linux process runs one thread, after waiting up to `wait` seconds for the
    helper threads a finished reader is still closing (a queue feeder, a pool handler); else (False, waited, why). A
    fork is never taken beside a live thread (it can inherit a held lock)."""
    import threading
    import time
    if not sys.platform.startswith('linux'):
        return False, 0.0, 'not Linux'
    started = time.monotonic()
    # event-driven (2026-10-09: no coded wait times): each helper thread is JOINED (the join returns the instant it
    # ends), all within the one bound; no sleep step. A thread that cannot be joined (a foreign/dummy thread) ends the
    # wait at once and is named below.
    while threading.active_count() > 1:
        others = [t for t in threading.enumerate() if t is not threading.current_thread()]
        left = wait - (time.monotonic() - started)
        if not others or left <= 0:
            break
        try:
            others[0].join(left)
        except (RuntimeError, AssertionError):
            break
    waited = round(time.monotonic() - started, 3)
    if threading.active_count() > 1:
        return False, waited, 'live threads after %.1f s: %s' % (waited, sorted(
            t.name for t in threading.enumerate() if t is not threading.current_thread()))
    return True, waited, None


def _native_chunk(span):
    """Worker side: the series jobs[span[0]:span[1]] in order, by the coordinator's own `run` (inherited by fork).
    Returns (values, cutoff record or None). A worker that reaches the cutoff raises the shared flag so the others stop
    feeding; a worker that sees the flag marks its remaining series without computing them."""
    shared = _NATIVE_SHARED
    native, run, jobs, flag = shared['native'], shared['run'], shared['jobs'], shared['flag']
    values = []
    for index in range(span[0], span[1]):
        if flag.value and native.cutoff is None:
            values.append(_NOT_COMPUTED)
            continue
        values.append(run(jobs[index]))
        if native.cutoff is not None and not flag.value:
            flag.value = 1
    record = (dict(cutoff=native.cutoff, status=native.status, reason=native.reason)
              if native.cutoff is not None else None)
    return values, record


def _native_series_parallel(native, run, jobs, lane, LP):
    """Every series job in order: a pinned fork pool (frankie_box_lane_pin.ordered_map) on the booked CPUs, or the former
    pinned thread pool when no fork can be taken. Values in job order; the placement goes on PINNING_RECORD."""
    import gc
    import multiprocessing
    import os
    import time
    started = time.monotonic()
    workers = native.pair_threads
    # periodic exact saves at closed chunks (_Segments); a resume computes only the series after the saved ones. A
    # series the cutoff left uncomputed ends the saving (a marker is never saved: the cutoff record lives on `native`).
    segments = _Segments('native_series', [_job_key(j) for j in jobs])
    prefix = segments.load()
    start = len(prefix)
    saving = [True]

    def offer(values_so_far, new):
        if saving[0] and any(_is_not_computed(v) for v in new):
            saving[0] = False
            segments.record['stopped_saving'] = 'a series the cutoff left uncomputed; markers are never saved'
        if saving[0]:
            segments.offer(values_so_far)
    forkable, waited, why = _fork_ready() if workers > 1 else (False, 0.0, 'one CPU booked')
    if not forkable:
        PINNING_RECORD['native_series_threads'] = dict(
            LP.record(workers, lane, what='classroom native series threads (_compute; no fork: %s)' % why),
            waited_for_threads_s=waited, resumed_from_series=start)
        import threading
        lock = threading.Lock()
        native.series_done, native.series_total = start, len(jobs)

        def counted(job):                # the same run(job), counted for the heartbeat (map keeps job order)
            value = run(job)
            with lock:
                native.series_done += 1
            return value
        values = list(prefix)
        with LP.executor('thread', workers, lane) as pool:
            try:
                for value in pool.map(counted, jobs[start:]):      # map yields in job order
                    values.append(value)
                    offer(values, (value,))
            except BaseException:
                pool.shutdown(wait=False, cancel_futures=True)     # a save or failure never waits for queued series
                raise
        PINNING_RECORD['native_series_threads']['seconds'] = round(time.monotonic() - started, 3)
        segments.done()
        return values
    # chunks small enough to balance (about eight per worker), large enough that the hand-back is not per series
    size = max(1, -(-len(jobs) // (workers * 8)))
    spans = [(a, min(a + size, len(jobs))) for a in range(start, len(jobs), size)]
    workers = max(1, min(workers, len(spans)))
    context = multiprocessing.get_context('fork')
    flag = context.Value('i', 0, lock=False)
    report, values = {}, list(prefix) + [None] * (len(jobs) - start)
    _NATIVE_SHARED.update(native=native, run=run, jobs=jobs, flag=flag)
    _RSS_COORDINATOR[:] = [os.getpid()]
    native.series_done, native.series_total = start, len(jobs)
    gc.freeze()               # the pass's state stays shared: a worker's collector never writes the coordinator's pages
    mapped = LP.ordered_map(_native_chunk, spans, workers, context=context, cpus=lane, window=workers * 2, poll=5.0,
                            report=report) if spans else iter(())
    try:
        for span, (chunk, record) in mapped:
            values[span[0]:span[1]] = chunk
            native.series_done = span[1]          # chunks arrive in job order: every series before span[1] is back
            heartbeat('classroom native entries: series', native.series_done, len(jobs), unit='series',
                      every=1.0, chunk_workers=workers)
            if record is not None and native.cutoff is None:
                native.cutoff, native.status, native.reason = record['cutoff'], record['status'], record['reason']
            offer(values[:span[1]], chunk)
    finally:
        if hasattr(mapped, 'close'):
            mapped.close()                        # the pool is stopped now (bounded), not when the traceback is freed
        gc.unfreeze()
        _NATIVE_SHARED.clear()
        _RSS_COORDINATOR[:] = []
    segments.done()
    PINNING_RECORD['native_series_processes'] = dict(
        LP.record(workers, lane, what='classroom native series processes (_compute: member values, event counts, '
                                      'categories, per-level FIFO queues; fork pool, ordered_map)'),
        jobs=len(jobs), chunks=len(spans), series_per_chunk=size, window=workers * 2, waited_for_threads_s=waited,
        resumed_from_series=start,
        worker_deaths=report.get('worker_deaths'), redone=report.get('redone'),
        seconds=round(time.monotonic() - started, 3),
        rule='same functions, sorted series order, values placed back by job index: the series a single thread computes; '
             'a dead worker\'s chunk is redone and the window shrinks by one; it never stops or hangs the classroom')
    return values


def _native_unavailable_entries(status, reason):
    return dict(series=[], series_count=0, pair_count=0, entries={
        entry: dict(use='unavailable', form=None, own_series=[], thin_series=[], series=0, pairs=0, unavailable=None,
                    reason='%s: %s' % (status, reason)) for entry in NATIVE_SIX})


def native_entries_failed(reason):
    """The native entry arithmetic's record when it could not even be set up (only it is missing; the day goes on)."""
    return dict(schema=NATIVE_ENTRY_SCHEMA, computation=NATIVE_ENTRY_COMPUTATION, author=AUTHOR, model_calls=0,
                status='failed', reason=reason, entries_computed=list(NATIVE_SIX), rule=NATIVE_ENTRY_RULE,
                **_native_unavailable_entries('failed', reason))


def native_entries_compact(result):
    """The receipt-sized view of the native entry arithmetic: per entry its use, form, series and pair counts, its
    unavailable carriers with the reason; per series its kind and relation counts (no pair bodies, no cells)."""
    if not result:
        return None
    entries = {}
    by_name = {s['name']: s for s in result.get('series') or ()}
    for entry, item in (result.get('entries') or {}).items():
        relations, pearson = {}, 0
        for name in (item.get('own_series') or []) + (item.get('thin_series') or []):
            for p in by_name.get(name, {}).get('pairs') or ():
                relations[p['direction_relation']] = relations.get(p['direction_relation'], 0) + 1
                pearson += (p.get('correlation') or {}).get('pearson') is not None
        # counts only (review G-2: the compact view lands three times on the receipt and must stay small); every series
        # name, pair and cell is in the pinned native-entry-arithmetic.json
        entries[entry] = dict({k: v for k, v in item.items() if k not in ('own_series', 'thin_series', 'not_computed_series')},
                              own_series=len(item.get('own_series') or ()), thin_series=len(item.get('thin_series') or ()),
                              relations=dict(sorted(relations.items())), pearson_reported=pearson)
    out = dict({k: v for k, v in result.items() if k not in ('series', 'entries', 'identities')}, entries=entries,
               series_kinds={kind: sum(1 for s in result.get('series') or () if s['kind'] == kind and s.get('status') != 'unavailable')
                             for kind in ('member_value', 'events_per_dipole_interval', 'category')},
               names_at='native-entry-arithmetic.json (every series name, pair, cell and identity; pinned on the receipt)')
    read = dict(out.get('read') or {})
    after = read.pop('events_after_last_dipole_row', None)
    if after is not None:
        read['events_after_last_dipole_row'] = dict(series=len(after), events=sum(after.values()))
    out['read'] = read
    identities = result.get('identities')
    if identities is not None:
        out['identities'] = dict(instruments=len(identities), changes=sum(
            leaf.get('changes', 0) for item in identities.values() for leaf in item.values()))
    return out


def native_entries_for_component(result, component):
    """Per one Dipole component: each of the six's series paired with it (relation counts, Pearson reported count)."""
    if not result or result.get('status') not in ('computed', 'cutoff'):
        return None
    by_name = {s['name']: s for s in result.get('series') or ()}
    out = {}
    for entry, item in (result.get('entries') or {}).items():
        relations, pearson, paired = {}, 0, 0
        for name in (item.get('own_series') or []) + (item.get('thin_series') or []):
            for p in by_name.get(name, {}).get('pairs') or ():
                if p['right'] == component:
                    paired += 1
                    relations[p['direction_relation']] = relations.get(p['direction_relation'], 0) + 1
                    pearson += (p.get('correlation') or {}).get('pearson') is not None
        if paired:
            out[entry] = dict(form=item.get('form'), series_paired=paired, relations=dict(sorted(relations.items())),
                              pearson_reported=pearson)
    return out or None


def _native_file_text(shared_market):
    pinned = getattr(shared_market, 'native_file', None) or {}
    return '%s (sha256 %s)' % (pinned.get('name', 'native-entry-arithmetic.json'), pinned.get('sha256'))


def native_entries_text(shared_market):
    """The six native entries' arithmetic as the summary answer carries it (or why it was not computed)."""
    compact = shared_market.native_entries_status()
    if compact.get('status') not in ('computed', 'cutoff'):
        return ('Native entry arithmetic (the six native entries that were context) was not computed on this day: %s (%s). '
                'Their instants stay in the pictures; nothing is filled in.' % (compact.get('status'), compact.get('reason')))
    per_entry = {entry: {k: item.get(k) for k in ('use', 'form', 'own_series', 'thin_series', 'pairs', 'relations',
                                                   'pearson_reported', 'not_computed', 'rows_covered', 'reason')}
                 for entry, item in compact['entries'].items()}
    stopped = ('' if compact.get('status') != 'cutoff' else
               ' CUTOFF (a named limit, not an integrity failure): %s. What was not computed is listed unavailable: cutoff, '
               'never zero and never done.' % json.dumps(compact.get('cutoff'), sort_keys=True, default=str))
    return ('Native entry arithmetic computed by Frankie\'s code (no model) on the six native entries that were context, '
            'against the %d Dipole rows: %s. Series kinds %s. Every series, pair and cell is whole in %s. Values are in '
            'force from their own cursor on, never backfilled; per instrument, never pooled; descriptive, no outcome '
            'claimed (R02).' % (compact.get('dipole_rows') or 0, json.dumps(per_entry, sort_keys=True, default=str),
                                json.dumps(compact.get('series_kinds'), sort_keys=True), _native_file_text(shared_market))
            + stopped)


# ------------------------------------------------------------------- the all-99 registry routed into the classroom
# Greg, 2026-10-07: the 99 layers are combined for Frankie FIRST. The retained registry (99 union layers; content
# identity 239a1480...) is named by the retained crosswalk below, pinned in knowledge/CYCLE_CALCULATION_PINS.json.
# Every entry is routed to the picture element of SharedMarketTimeline.iter_pictures() that carries it (and so to the
# component answers through the untrimmed anchor pictures and the full reader), or to its own consumer in this piece
# (controls, knowledge, carry), or named sealed / disabled / output. Roles are not interchangeable numeric layers.
ALL99_SCHEMA = 'FRANKIE_CLASSROOM_ALL99_COVERAGE_V1'
ALL99_REGISTRY = dict(path=ALL99.CROSSWALK_PATH, bytes=ALL99.CROSSWALK_BYTES, sha256=ALL99.CROSSWALK_SHA256,
                      registry_sha256=ALL99.REGISTRY_SHA256, pinned_in=ALL99.PINNED_IN,
                      entries_from='frankie_box_all99_coverage.REGISTRY (the one registry)')
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
                      'output_analogue', 'output_not_produced_here', 'unrouted')
_NATIVE_ABSENT = 'the native member/lifecycle ledgers are the only producer of this layer and they are absent from this ROOT ' \
                 '(the ROOT runs the native pass by default since 2026-10-07; absent here means an explicit recorded override ' \
                 'or a native pass that did not complete; the core\'s own recorded reason is named where it exists)'
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
    entries, counts, requests, route_integrity = [], {}, [], []
    # The entry list is the one registry's (frankie_box_all99_coverage.REGISTRY, crosswalk order); the routes are this
    # piece's own. A registry entry without a route here, or a route whose group differs, is an integrity finding:
    # listed (the entry is kept as 'unrouted'), never filled in.
    for layer_id, group, _policy in ALL99.REGISTRY:
        role = ALL99_ROLES[group]
        routed = ALL99_ROUTES.get(layer_id)
        if routed is None:
            route_integrity.append(dict(kind='registry_entry_without_classroom_route', entry=layer_id))
            entry = dict(layer=layer_id, group=group, role=role, route=None, disposition='unrouted',
                         reason='no classroom route for this registry entry (integrity finding; listed, not filled in)',
                         registry_status=(file_layers.get(layer_id) or {}).get('status'),
                         registry_policy=(file_layers.get(layer_id) or {}).get('policy'))
            counts['unrouted'] = counts.get('unrouted', 0) + 1
            entries.append(entry)
            continue
        route_group, route = routed
        if route_group != group:
            route_integrity.append(dict(kind='classroom_route_group_differs', entry=layer_id, route_group=route_group,
                                        registry_group=group))
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
                # the core's own opening element (report.opening_state, also on every picture) when this reading carries
                # it; the ingestion-receipt field read above stays the fallback for a reading saved before it existed
                core_opening = (shared.get('report') or {}).get('opening_state')
                if isinstance(core_opening, dict):
                    entry['opening_state'] = {k: core_opening.get(k) for k in ('status', 'source', 'initial_last_observed_state')}
                    if core_opening.get('status') in ('seeded', 'warmed_from_partition'):
                        opening = dict(opening, status='seeded', core_status=core_opening.get('status'))
                    elif core_opening.get('status') is not None:
                        opening = dict(opening, status='absent', core_status=core_opening.get('status'),
                                       listed=((core_opening.get('initial_last_observed_state') or {}).get('reason')
                                               or opening.get('listed')))
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
    # Use (Greg, 2026-10-07: the classroom INGESTS, and "arrived" never overstates): per entry, whether it entered an
    # operand of a named computation of this piece ('computed', with each computation named), is in the pictures / the
    # received inputs only ('context'), or did not reach this piece ('absent', with the reason). Additive keys.
    use_counts = {}
    for entry in entries:
        entry.update(_classroom_use(entry, consumers))
        use_counts[entry['use']] = use_counts.get(entry['use'], 0) + 1
    by_role = {}
    for entry in entries:
        by_role.setdefault(entry['role'], {})
        by_role[entry['role']][entry['disposition']] = by_role[entry['role']].get(entry['disposition'], 0) + 1
    # Entries the core does not yield (requests to the core author, workflow_reports); never filled in here.
    requests.append(dict(file='deploy/aws/box/frankie_box_market_timeline.py', function='SharedMarketTimeline.__init__ / iter_pictures',
                         entry='canonical_predecessor_bootstrap_objects', status='built in the core (2026-10-07): report.opening_state and '
                         'picture.opening_state with initial_last_observed_state; the classroom route reads report.opening_state first '
                         '(2026-10-07 evening) and the ingestion receipt only for a reading saved before it existed',
                         what='yield the opening adapter state (opening-book pin, seeded / absent) as an identity element and the initial '
                              'last_observed_state disposition, so the predecessor bootstrap is a picture element rather than an ingestion-receipt field read here'))
    requests.append(dict(file='deploy/aws/box/frankie_box_market_timeline.py', function='SharedMarketTimeline.iter_pictures',
                         entry='legacy_native_signed_flow / legacy_per_second_roll20', status='named completed_only in the core report '
                         '(report.all99_coverage, report.layer_entries.completed); blocked on provenance, not on the reader',
                         what='the per-second aggregates are yielded as completed_sources metadata only; their values could enter the '
                              'picture once an exact contributing-cursor provenance exists (blocked on provenance, not on the reader)'))
    native_absent = [e['layer'] for e in entries if e.get('disposition') in ('absent', 'thin') and
                     (ALL99_ROUTES.get(e['layer'], (None, {}))[1].get('layer') or '').startswith('native.')]
    unrouted = sorted(set(file_layers) - set(ALL99_ROUTES))
    unlisted = sorted(set(ALL99_ROUTES) - set(file_layers)) if file_layers else None
    registry_names = {layer for layer, _, _ in ALL99.REGISTRY}
    route_integrity += [dict(kind='classroom_route_not_in_registry', entry=name)
                        for name in sorted(set(ALL99_ROUTES) - registry_names)]
    # The shared per-piece field (FRANKIE_ALL99_COVERAGE_V1), built and validated by the one registry module from the
    # same entries: no name, route or disposition changes; the classroom's own list above stays as it was.
    shared_field = ALL99.field(
        'classroom', ((shared or {}).get('identity') or {}).get('day'),
        [dict(entry=e['layer'], group=e['group'], disposition=e['disposition'],
              reason=e.get('reason') or e.get('note') or e.get('route'),
              consumer=e.get('consumer'), route=e.get('route'), piece_role=e['role'],
              count=e.get('count'), use=e['use'], use_reason=e['use_reason'], computations=e['computations'],
              **({'canonical': e['shared_word']} if e.get('shared_word') else {})) for e in entries],
        code_root=repo_root, stage='classroom',
        basis='the classroom shared-picture read (arrivals over the exhausted source) and its own consumers')
    return dict(schema=ALL99_SCHEMA, registry=registry, routed=len(entries), counts=counts, by_role=by_role,
                core_layers=core_layers, entries=entries, requests=requests,
                native_layers_absent_or_thin=native_absent,
                unrouted_in_file=unrouted, routed_not_in_file=unlisted,
                route_integrity=route_integrity, shared_field=shared_field,
                use_counts=use_counts, use_vocabulary=dict(USE_VOCABULARY),
                computations=dict(CLASSROOM_COMPUTATIONS),
                native_only_ingestion=_native_only_ingestion(entries),
                native_entries=consumers.get('native_entries'),
                exhaustion_d=_exhaustion_d_receipt(consumers.get('exhaustion_d')),
                external_points=consumers.get('external_points') or dict(
                    status='not_computed', reason='the external answers were not reached before this list was built'),
                decision_open=('%d layers carried only by the native member/lifecycle ledgers are absent or thin on this ROOT '
                               '(each entry names the core\'s recorded reason; the native pass runs by default, so absence means an '
                               'override or an incomplete native pass). Their instants stay in the picture, thinner.' % len(native_absent)
                               if native_absent else None),
                rule='every entry listed with a disposition; missing coverage thins the day and never rejects it; roles are not '
                     'interchangeable numeric layers; sealed answers stay sealed; nothing is fabricated to make an entry arrive',
                limit='a counted arrival is evidence yielded to the pictures beside the component answers (and to the full reader), '
                      'not proof that a Dipole equation used it. `use` says what entered arithmetic: the Dipole arithmetic uses the '
                      'teacher rows only (an entry whose teacher form is a Dipole component is computed in that partial form); the '
                      'exhaustion/D facts (frankie_box_teach.facts) use the completed whole-day bedrock rows named per entry; the '
                      'native entry arithmetic uses the six entries\' own member / lifecycle / envelope series named per entry. A '
                      'computed entry is not a claim that every field of it entered a target equation')


# ------------------------------------------- what entered arithmetic: computed / context / absent (Greg, 2026-10-07)
# "Frankie's classroom INGESTS the 99, not just sees them." Every entry of the all-99 list carries `use`: it entered an
# operand of a NAMED existing computation of this piece, it reached the pictures / received inputs only, or it did not
# reach this piece (with the reason). No computation below is new: the Dipole arithmetic is this module's own, the
# exhaustion/D facts are frankie_box_teach.facts (the box-side exhaustion/D classroom computation, built 2026-09-21 and
# not invoked on the experiment path until now), the learner checks are this module's reproductions.
USE_VOCABULARY = {
    'computed': 'entered an operand of a named computation of this piece (each computation, its operand and its form named: '
                'own_rows = the entry\'s own rows; teacher_form = the partial form the teacher computes for the entry; '
                'section_counts = the traversal\'s count of the entry\'s section rows, not the rows; thin_carrier = the '
                'INPUT envelope\'s own carrier of the entry (reset actions, session scope), not the native rows)',
    'context': 'reached this piece (market pictures, the full reader, received inputs, rules, cutoff); no computation of this '
               'piece reads it as an operand',
    'absent': 'did not reach this piece on this day, with the reason (missing coverage, no event, withheld by role, retired, '
              'disabled, an output, not an input of this piece); the day and the instant stay',
}
CLASSROOM_COMPUTATIONS = {
    'dipole_arithmetic': '_calculate_evidence / component_answer / summary_answer: per component state counts, terminal state, '
                         'first-to-last PRESENT direction, extremes and step counts; per pair Pearson, co-movement counts and '
                         'direction relation (dipole_classroom\'s own functions); operands: the teacher rows (the learner-owned '
                         'reading in SOCRATIC/VERIFY) of the Dipole components',
    'exhaustion_d_facts': 'frankie_box_teach.facts (code only, no model): the lineage D-depth histogram and statuses (4.13), the '
                          'ancestry gaps per event (4.14), the causal-clock order check per group, the family descriptor and '
                          'action-string counts and the candidate-lane verdict; operands: the ROOT\'s completed whole-day bedrock '
                          'layer files named by derive.json and derive.json\'s bedrock block',
    'learner_check': 'stage_knowledge_reproduction / school_reproduction: each lawful prior finding checked against today\'s '
                     'Dipole pair review; operands: the selected knowledge documents / completed school files and today\'s pairs',
    NATIVE_ENTRY_COMPUTATION: 'the classroom\'s external-section arithmetic (dipole_classroom_external) applied to the six '
                              'native entries that were context (order_lifecycle_clears, contract_session_roll_state, '
                              'complete_state_reset_bootstrap_receipts, price_and_book_path, derived_price_flow_book_paths, '
                              'derived_v4_mechanics_fifo_features): per series the value in force at each Dipole row, state '
                              'counts, terminal state, first-to-last direction, and per Dipole component the relation, Pearson '
                              'and co-movement counts; categories as runs and per-value cells of each Dipole component; '
                              'operands: the native member rows\' own fields (joined-teacher leaf rule, plus each FIFO queue\'s '
                              'length per side and level from the best, QUEUE_LEVEL_RULE), the lifecycle rows of '
                              'the entry\'s sections counted per Dipole interval, the INPUT envelope\'s reset and session-scope '
                              'carriers; per instrument, never pooled',
}
_CHAIN = ('unresolved_age_groups_log', 'extension_count_log', 'step_ratio_log', 'pullback_ticks_last_log',
          'step_duration_groups_log', 'pullback_ticks_prev_log')
# entry -> (Dipole components carrying its computed form (None = every component of the roster), form, where that mapping is
# recorded). Every mapping is an existing table's, never a new one: the teacher's TEACHER_FORMS and the search's PLANE_COVERAGE.
TEACHER_FORM_COMPONENTS = {
    'derived_roll20_and_dipole_state': (None, 'own_rows', 'the Dipole state rows themselves (every component, every cursor); '
                                        'the per-second roll20 aggregate stays completed-only'),
    'depletion_and_replenishment': (('far_replenish_log1p_64', 'far_replenish_log1p_1024', 'far_absorption_share_64',
                                     'far_absorption_share_1024'), 'teacher_form', 'frankie_box_experiment_teacher.TEACHER_FORMS'),
    'resilience_and_recovery': (('far_identity_survival_64', 'far_identity_survival_1024', 'far_size_retention_64',
                                 'far_size_retention_1024'), 'teacher_form', 'frankie_box_experiment_teacher.TEACHER_FORMS'),
    'derived_unresolved_age_chain_trajectory': (_CHAIN, 'teacher_form', 'frankie_box_experiment_teacher.TEACHER_FORMS'),
    'prebirth_unresolved_chain_extension_state': (('extension_count_log', 'step_ratio_log', 'pullback_ticks_last_log',
                                                   'pullback_ticks_prev_log'), 'teacher_form',
                                                  'frankie_box_experiment_teacher.TEACHER_FORMS (pullback_ticks_*)'),
    'order_lifecycle_fills': (('far_absorption_share_64', 'far_absorption_share_1024'), 'teacher_form',
                              'frankie_box_experiment_search.PLANE_COVERAGE (the teacher\'s far_absorption_share_64/1024)'),
    'order_lifecycle_modifies': (('far_priority_loss_rate_64', 'far_priority_loss_rate_1024'), 'teacher_form',
                                 'frankie_box_experiment_search.PLANE_COVERAGE (the teacher\'s far_priority_loss_rate_64/1024)'),
    'queue_concentration': (('far_size_hhi',), 'teacher_form', 'frankie_box_experiment_search.PLANE_COVERAGE (teacher far_size_hhi)'),
    'missingness_and_integrity_flags': (None, 'teacher_form', 'frankie_box_experiment_search.PLANE_COVERAGE (the Dipole rows\' '
                                        'states counted per column): the states and their reasons only, not the values'),
}
# The 18 entries carried only by the native member/lifecycle ledgers (frankie_box_boss_session.NATIVE_ONLY_ENTRIES).
NATIVE_ONLY_ENTRIES = (
    'order_lifecycle_fills', 'order_lifecycle_clears', 'contract_session_roll_state', 'complete_state_reset_bootstrap_receipts',
    'depletion_and_replenishment', 'resilience_and_recovery', 'price_and_book_path', 'derived_ancestry_gaps',
    'derived_unresolved_age_chain_trajectory', 'derived_price_flow_book_paths', 'derived_v4_mechanics_fifo_features',
    'prebirth_predecessor_at_risk_state', 'prebirth_unresolved_chain_extension_state', 'prebirth_ancestry_successor_opportunity',
    'prebirth_stopped_chain_false_context_controls', 'prebirth_negative_opportunity_cases',
    'clock_prospective_discovery_confirmation', 'clock_model_evaluation')
NATIVE_SEARCHED = ('frankie_box_bedrock.py (run, project, project_sections, SECTION_FILES, crosswalk_records); the pin\'s bedrock '
                   'and projection layers (knowledge/CYCLE_CALCULATION_PINS.json, frankie_principal_adapter projection_layers); '
                   'work/native-layer-records.json and frankie_box_boss_session NATIVE_ONLY_ENTRIES / NATIVE_ONLY_LIMITS; '
                   'frankie_box_teach.py (facts and its six streams); frankie_box_experiment_teacher.TEACHER_FORMS; '
                   'frankie_box_experiment_search.PLANE_COVERAGE; frankie_box_experiment_native.py; frankie_box_joined_teacher.py; '
                   'frankie_box_compare.py; frankie_box_digest_render.py; dipole_classroom.py ROLE_DEFINITIONS; this module '
                   '(Dipole arithmetic, learner checks) and frankie_box_classroom_reader.py')
# Where no computation of THIS piece takes the native rows of an entry: the closest existing consumer, for Greg to decide.
# Never wired here (that would be a new equation in the classroom).
NATIVE_ONLY_CLOSEST = {
    'order_lifecycle_fills': 'the native fill_disposition rows (a_memory_member_first_recalculation.fill_disposition) are read by no '
                             'classroom computation (their teacher form far_absorption_share_64/1024 is). Closest existing '
                             'consumers of the rows: frankie_box_experiment_search (structures.fill_disposition.* series and cells, '
                             'the ROOT legacy form) and frankie_box_joined_teacher couplings over every numeric leaf of the layer',
    # The six below are computed since 2026-10-07 night by native_entry_arithmetic (Greg: "18 of 18"). This text is shown
    # only on a day where their own rows did not enter it (the native ledger absent or a failure, named with the reason).
    'order_lifecycle_clears': 'own rows (capture_observations, integrity_delta, raw_actions) enter native_entry_arithmetic when '
                              'the native member ledger is present; the INPUT envelope\'s R actions (picture.reset_inputs) '
                              'enter it on every day (thin_carrier)',
    'contract_session_roll_state': 'own rows (session_phase, continuity_segment, raw_symbol, instrument_id) enter '
                                   'native_entry_arithmetic when the native member ledger is present; the INPUT envelope\'s '
                                   'session_id / source_member_index and their scope changes enter it on every day (thin_carrier)',
    'complete_state_reset_bootstrap_receipts': 'own rows (integrity_delta, capture_observations, snapshot_bootstrap_only) '
                                               'enter native_entry_arithmetic when the native member ledger is present; the '
                                               'INPUT envelope\'s R actions enter it on every day (thin_carrier)',
    'price_and_book_path': 'own rows (book_full, book_regime, structure.price_raw_*) and the lifecycle ladder rows enter '
                           'native_entry_arithmetic when the native ledgers are present; no thinner carrier is computed here',
    'derived_price_flow_book_paths': 'own rows (book_regime, book_full) and the lifecycle flow_substrate / ladder rows enter '
                                     'native_entry_arithmetic when the native ledgers are present; no thinner carrier here',
    'derived_v4_mechanics_fifo_features': 'own rows (activity_full, activity_since, book_full, capture_observations) and the '
                                          'lifecycle queue rows enter native_entry_arithmetic when the native ledgers are '
                                          'present; no thinner carrier here',
}
EXHAUSTION_D_SCHEMA = 'FRANKIE_CLASSROOM_EXHAUSTION_D_FACTS_V1'
# What frankie_box_teach.facts takes from each lifecycle section and each member layer (its own code: _job_sections reads
# lineage and recurrence; _job_clock / _job_evaluated / _job_families / _job_actions read these layers by name; the
# candidate lane reads bedrock.sections_fed). A registry entry is attributed by the sections the pinned crosswalk declares for it.
FACTS_SECTIONS = {
    'lineage': ('lineage', 'D-depth histogram and lineage status counts (terminated / censored / open) over the lineage rows (4.13)'),
    'recurrence': ('ancestry_gaps', 'ancestry gaps per event, every gap named, largest first (4.14)'),
    'candidate': ('candidate_lane', 'the candidate-lane verdict: candidate unit events the traversal fed (bedrock.sections_fed), '
                                    'against the warmup and the minimum; a count, not the rows'),
    'episode': ('candidate_lane', 'the candidate-lane verdict: episode rows the traversal fed to 4.10-4.12 '
                                  '(bedrock.sections_fed); a count, not the rows'),
}
FACTS_LAYERS = {
    'clock_event_known_by': 'the causal-clock order check per group: clocks.first_lawful_availability_ns as event known-by',
    'clock_feature_availability': 'the causal-clock order check per group: clocks.first_lawful_availability_ns as feature availability',
    'clock_model_evaluation': 'the causal-clock order check per group: clocks.decision_ts_recv_ns as model evaluation (a null '
                              'value reads unknown, never a violation); decision_basis counted',
    'derived_d_family_geometry': 'family descriptor counts: structure.candidate_family_id and structure.side_string per group',
    'legacy_structure_observables': 'action-string counts over the legacy structure groups',
}


def dipole_operands(visible):
    """Per Dipole component of today's lawful evidence: how many observations (and PRESENT ones) the Dipole arithmetic takes."""
    evidence = _evidence(visible)
    return {c['name']: dict(observations=len(c['observations']),
                            present=sum(1 for p in c['observations'] if p['state'] == 'PRESENT'),
                            states={s: int((c.get('state_counts') or {}).get(s, 0)) for s in STATES})
            for c in evidence['components']}


def _sections_of(work, derive_measured, producers, layers):
    """{registry entry: lifecycle sections the pinned crosswalk declares}, from work/native-layer-records.json when it is
    bound to the same derive.json bytes, else from the pinned producers' crosswalk; ({}, reason) when neither is readable."""
    path = Path(work) / 'native-layer-records.json'
    if path.is_file():
        try:
            doc = json.loads(path.read_bytes())
            bound = {k: (doc.get('derive') or {}).get(k) for k in ('bytes', 'sha256')}
            if doc.get('status') == 'built' and bound == {k: derive_measured[k] for k in ('bytes', 'sha256')}:
                return ({r['entry']: list((r.get('crosswalk') or {}).get('lifecycle_sections') or [])
                         for r in doc.get('records') or [] if isinstance(r, dict) and r.get('entry')},
                        {r['entry']: r.get('native_limit') for r in doc.get('records') or []
                         if isinstance(r, dict) and r.get('native_limit')},
                        'work/native-layer-records.json (bound to this derive.json)')
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            listed = 'native-layer-records.json unreadable (%s: %s); ' % (type(error).__name__, error)
        else:
            listed = 'native-layer-records.json not bound to this derive.json (status %s); ' % doc.get('status')
    else:
        listed = 'native-layer-records.json absent; '
    try:
        import frankie_box_bedrock as B
        records = B.crosswalk_records(producers, layers)
        return ({name: list(r.get('lifecycle_sections') or []) for name, r in records.items()}, {},
                listed + 'the pinned producers\' crosswalk (native_layer_crosswalk.LAYER_PRODUCERS)')
    except Exception as error:  # noqa: BLE001 - attribution basis only; recorded, never inferred
        return {}, {}, listed + 'pinned crosswalk unreadable (%s: %s): no section attribution' % (type(error).__name__, error)


def _facts_summary(f):
    A, C, F = f['ancestry_gaps'], f['clocks'], f['families']
    return dict(layers={name: dict(status=v.get('status'), count=v.get('count')) for name, v in f['layers'].items()},
                traversal=f.get('traversal'),
                lineage={k: f['lineage'].get(k) for k in ('nodes', 'terminated', 'censored', 'open', 'depth_histogram',
                                                          'status_counts')},
                ancestry_gaps=dict(events=A['events'], gaps=A['count'], smallest_ns=A['smallest_ns'], largest_ns=A['largest_ns'],
                                   largest=(A['largest'][0] if A['largest'] else None)),
                clocks=dict(groups=C['groups'], ordered=C['ordered'], unknown=C['unknown'], violations=len(C['violations']),
                            derived_clocks=C['derived_clocks'], decision_basis=C['decision_basis'], rule=C['rule']),
                families=dict(distinct_family_ids=F['distinct_family_ids'], side_strings=F['side_strings'],
                              action_string_kinds=len(F['action_strings'])),
                candidate_lane=f['candidate_lane'],
                frozen=[{k: x.get(k) for k in ('layer', 'name', 'source', 'bytes', 'sha256')} for x in f.get('frozen') or []],
                frozen_missing=f.get('frozen_missing') or [], frozen_integrity=f.get('frozen_integrity') or [])


def _facts_attribution(f, sections_of, limits):
    """Per registry entry: which operand of frankie_box_teach.facts it supplied and how many rows. An entry whose operand
    held no row on this day is 'absent' with the reason (a measurement), never 'computed'."""
    lane = f['candidate_lane']
    rows_of = dict(lineage=f['lineage']['nodes'], recurrence=f['ancestry_gaps']['events'],
                   candidate=lane.get('candidate_unit_events'), episode=lane.get('episode_rows'))
    operands = {}
    for name, sections in sections_of.items():
        for section in sections:
            if section in FACTS_SECTIONS:
                fact, text = FACTS_SECTIONS[section]
                operands.setdefault(name, []).append(dict(section=section, fact=fact, operand=text, rows=rows_of[section]))
    for name, text in FACTS_LAYERS.items():
        if name == 'legacy_structure_observables':
            rows = sum(int(a.get('count') or 0) for a in f['families']['action_strings'])
        else:
            record = f['layers'].get(name) or {}
            rows = record.get('count') if record.get('status') == 'derived' else 0
        operands.setdefault(name, []).append(dict(layer_file=name, operand=text, rows=rows))
    out = {}
    for name, items in operands.items():
        record = f['layers'].get(name) or {}
        held = sum(int(o['rows'] or 0) for o in items)
        # the candidate-lane operands are the traversal's fed counts of the section, not the rows themselves
        rows_read = any(int(o['rows'] or 0) > 0 and o.get('section') not in ('candidate', 'episode') for o in items)
        out[name] = dict(use='computed' if held > 0 else 'absent', form='own_rows' if rows_read else 'section_counts',
                         operands=items, layer_status=record.get('status'),
                         layer_rows=record.get('count'), layer_reason=record.get('reason'), limit=limits.get(name),
                         reason=('rows of this entry entered frankie_box_teach.facts' if held > 0 else
                                 'frankie_box_teach.facts ran over this entry\'s operand; it held no row on this day (%s)'
                                 % (record.get('reason') or 'no row recorded')))
    for item in f.get('frozen') or []:
        out.setdefault(item['layer'], dict(use='context', operands=[], files=[], reason=(
            'read whole as text by frankie_box_teach.facts from the brain\'s frozen learned-structure entry; text, not an '
            'arithmetic operand'))).setdefault('files', []).append({k: item.get(k) for k in ('name', 'sha256', 'bytes')})
    # a frozen file not there drops only its text; a differing one is an integrity finding (both listed, never computed)
    for key, word in (('frozen_missing', 'missing'), ('frozen_integrity', 'integrity')):
        for item in f.get(key) or []:
            slot = out.setdefault(item['layer'], dict(use='absent', operands=[], reason=(
                'frozen text not carried (%s): %s' % ('missing' if word == 'missing' else 'integrity finding', item['reason']))))
            slot.setdefault(word, []).append(item)
    return out


def exhaustion_d_facts(calculations, brain):
    """Invoke the EXISTING exhaustion/D classroom computation (frankie_box_teach.facts; code only, no model) on this day's
    completed ROOT, and attribute each registry entry it read. Missing-coverage rule: never raises for coverage; a ROOT
    without a native pass, an unreadable input or a refusal is 'unavailable' (or 'integrity_failure' / 'failed', each with
    the reason) and only these facts are missing; the Dipole classroom and the day go on. The rows are the ROOT's completed
    whole-day bedrock rows (GROUP_CLOSE emissions and the stream-end finalization), lawful at the classroom's whole-day
    cutoff (through_cursor = record_count - 1); they are never placed into an earlier picture."""
    import time
    calculations, brain = Path(calculations), Path(brain)
    work = calculations / 'work'
    result = dict(schema=EXHAUSTION_D_SCHEMA, computation='frankie_box_teach.facts', author=AUTHOR, model_calls=0,
                  inputs={}, attribution={}, status=None, reason=None,
                  cutoff='completed whole-day rows inside the classroom\'s whole-day cutoff; never backfilled into a picture',
                  rule='a missing input blocks only these facts; integrity mismatches are named as such, never as measurements')

    def stop(status, reason, **extra):
        result.update(status=status, reason=reason, **extra)
        return result
    try:
        receipt = json.loads((calculations / 'calculations-receipt.json').read_bytes())
        derive_path = work / 'derive.json'
        raw = derive_path.read_bytes()
    except (OSError, ValueError) as error:
        return stop('unavailable', 'the ROOT receipt or derive.json is unreadable: %s: %s' % (type(error).__name__, error))
    measured = dict(path=str(derive_path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    result['inputs']['derive'] = measured
    pin = receipt.get('derivation') if isinstance(receipt.get('derivation'), dict) else None
    if pin is None:
        return stop('unavailable', 'the ROOT receipt names no derivation pin; derive.json is never read unpinned')
    if {k: pin.get(k) for k in ('bytes', 'sha256')} != {k: measured[k] for k in ('bytes', 'sha256')}:
        return stop('integrity_failure', 'derive.json differs from the derivation pin in the ROOT receipt',
                    pinned={k: pin.get(k) for k in ('bytes', 'sha256')})
    derive = json.loads(raw)
    bedrock = derive.get('bedrock') if isinstance(derive.get('bedrock'), dict) else None
    if bedrock is None:
        return stop('unavailable', 'derive.json carries no native (bedrock) derivation on this ROOT')
    if bedrock.get('skipped'):
        return stop('unavailable', 'the native pass did not run on this ROOT (%s): %s' % (
            'an explicit recorded override' if bedrock.get('override') else 'recorded skipped',
            bedrock.get('reason') or bedrock.get('not_derived')))
    crosswalk = bedrock.get('crosswalk')
    if not crosswalk:
        return stop('unavailable', 'the bedrock block names no pinned producers crosswalk, so no producers checkout')
    producers = Path(crosswalk).parents[3]
    result['inputs']['producers'] = dict(path=str(producers), derivation_commit=bedrock.get('producers_commit'))
    if not producers.is_dir():
        return stop('unavailable', 'the pinned producers checkout %s is not on this box' % producers)
    try:
        import frankie_box_bedrock as B
        commit = B.producers_commit(producers)
        if bedrock.get('producers_commit') not in (None, commit):
            return stop('integrity_failure', 'the producers checkout is at %s; the derivation names %s' % (
                commit, bedrock.get('producers_commit')))
        result['inputs']['producers']['commit'] = commit
        B.load_producers(producers)
    except ValueError as error:
        return stop('integrity_failure', 'pinned producers: %s' % error)
    except Exception as error:  # noqa: BLE001 - the producers could not be loaded: these facts only, recorded
        return stop('failed', 'pinned producers could not be loaded: %s: %s' % (type(error).__name__, error))
    sections_of, limits, basis = _sections_of(work, measured, producers, list(bedrock.get('layers') or []))
    result['inputs']['sections_basis'] = basis
    frozen = brain / 'frozen-learned-structure' / 'MANIFEST.json'
    result['inputs']['frozen_manifest'] = (dict(path=str(frozen), bytes=frozen.stat().st_size,
                                                sha256=hashlib.sha256(frozen.read_bytes()).hexdigest())
                                           if frozen.is_file() else dict(path=str(frozen), status='absent'))
    import frankie_box_teach as T
    started = time.monotonic()
    try:
        facts = T.facts(work, brain, producers)
    except ValueError as error:
        text = str(error)
        kind = ('integrity_failure' if any(w in text for w in ('differs', 'outside', 'not the producers', 'not the pinned'))
                else 'unavailable')
        return stop(kind, 'frankie_box_teach.facts refused: ' + text, seconds=round(time.monotonic() - started, 3))
    except Exception as error:  # noqa: BLE001 - a failed worker is a failed computation, recorded; never a measurement
        return stop('failed', '%s: %s' % (type(error).__name__, error), seconds=round(time.monotonic() - started, 3))
    return stop('computed', None, seconds=round(time.monotonic() - started, 3), facts=facts, summary=_facts_summary(facts),
                attribution=_facts_attribution(facts, sections_of, limits))


def exhaustion_d_text(result):
    """The exhaustion/D facts as the summary answer carries them (or why they are not there)."""
    if not result:
        return None
    if result.get('status') != 'computed':
        return ('Exhaustion/D facts (frankie_box_teach.facts, code only) were not computed on this day: %s (%s). The bedrock '
                'entries they read stay in the market pictures as context where present; nothing is filled in.'
                % (result.get('status'), result.get('reason')))
    pinned = result.get('file') or {}
    return ('Exhaustion/D facts computed by Frankie\'s code (frankie_box_teach.facts; no model) from the ROOT\'s completed '
            'whole-day bedrock rows: ' + json.dumps(result['summary'], sort_keys=True, default=str)
            + '. Every gap, clock violation and family count is whole in %s (sha256 %s). These rows are completed whole-day '
              'knowledge inside the classroom\'s whole-day cutoff, never backfilled into an earlier picture; descriptive, no '
              'outcome claimed (R02).' % (pinned.get('name', 'exhaustion-d-facts.json'), pinned.get('sha256')))


def _facts_for_component(result, name):
    """Native rows computed by the facts for the registry entries whose teacher form is this component (the registry
    entry links the two; no new relation is claimed)."""
    if not result or result.get('status') != 'computed':
        return []
    out = []
    for entry, (components, _, _) in TEACHER_FORM_COMPONENTS.items():
        if components is None or name not in components:
            continue
        attributed = (result.get('attribution') or {}).get(entry)
        if attributed and attributed.get('use') == 'computed':
            out.append(dict(entry=entry, operands=attributed['operands'], limit=attributed.get('limit')))
    return out


def _exhaustion_d_receipt(result):
    return None if result is None else {k: v for k, v in result.items() if k != 'facts'}


def _classroom_use(entry, consumers):
    """`use`, `use_reason`, `computations` and the shared word for one all-99 entry (see USE_VOCABULARY)."""
    name, disposition = entry['layer'], entry['disposition']
    route = (ALL99_ROUTES.get(name) or (None, {}))[1]
    kind = route.get('kind')
    computations = []
    operands = consumers.get('dipole_operands') or {}
    form = TEACHER_FORM_COMPONENTS.get(name)
    if form is not None and operands:
        components, how, source = form
        wanted = list(operands) if components is None else list(components)
        seen = [c for c in wanted if c in operands]
        if seen:
            computations.append(dict(computation='dipole_arithmetic', form=how, components=seen,
                                     not_in_roster=[c for c in wanted if c not in operands] or None,
                                     observations=sum(operands[c]['observations'] for c in seen),
                                     present=sum(operands[c]['present'] for c in seen), mapping_source=source))
    facts = ((consumers.get('exhaustion_d') or {}).get('attribution') or {}).get(name)
    if facts and facts.get('use') == 'computed':
        computations.append(dict(computation='exhaustion_d_facts', form=facts.get('form', 'own_rows'),
                                 operands=facts['operands'], limit=facts.get('limit')))
    fed = [p for p in ((consumers.get('external_points') or {}).get('entries_fed') or {}).get(name) or []
           if p.get('use') == 'computed']
    if fed:
        # the day file declares these points feed this entry; their values entered the external section arithmetic
        # an exact mapping is the entry's own evidence; a closest mapping (Greg: no exact fit) is a partial form
        exact = all(p.get('mapping') == ['exact'] for p in fed)
        computations.append(dict(computation='external_section_arithmetic', form='own_rows' if exact else 'external_closest',
                                 points=[dict(point_id=p['point_id'], mapping=p.get('mapping'), note=p.get('note'))
                                         for p in fed], as_of=EXTERNAL_AS_OF))
    native_record = consumers.get('native_entries')
    native = ((native_record or {}).get('entries') or {}).get(name)
    if native is None and name in NATIVE_SIX and native_record is not None:
        native = dict(use='unavailable', reason='%s: %s' % (native_record.get('status'), native_record.get('reason')))
    if native and native.get('use') == 'computed':
        # the six native entries (Greg, 2026-10-07 night: 18 of 18): their own series entered the native entry arithmetic
        computations.append(dict(computation=NATIVE_ENTRY_COMPUTATION, form=native['form'],
                                 series=native.get('series'), own_series=native.get('own_series'),
                                 thin_series=native.get('thin_series'), pairs=native.get('pairs'),
                                 relations=native.get('relations'), pearson_reported=native.get('pearson_reported'),
                                 unavailable=native.get('unavailable'), not_computed=native.get('not_computed'),
                                 rows_covered=native.get('rows_covered'), rows=native.get('rows'),
                                 cutoff=(native_record or {}).get('cutoff'),
                                 file=(consumers.get('native_entries') or {}).get('file')))
    knowledge = consumers.get('knowledge') or {}
    if name == 'anchored_knowledge_manifest' and knowledge.get('stage_knowledge_checks'):
        computations.append(dict(computation='learner_check', form='own_rows', function='stage_knowledge_reproduction',
                                 checks=knowledge['stage_knowledge_checks'], documents=len(knowledge.get('documents') or [])))
    if name == 'lawful_prior_session_carry' and knowledge.get('school_checks'):
        computations.append(dict(computation='learner_check', form='own_rows', function='school_reproduction',
                                 checks=knowledge['school_checks'], school_days_read=len(knowledge.get('school_days_read') or []),
                                 note='the completed school files of earlier sessions read at this boundary'))
    shared = None
    if computations:
        own = any(c['form'] == 'own_rows' for c in computations)
        if kind in ('picture', 'dipole'):
            shared = 'arrived' if own else 'thin'
        return dict(use='computed', computations=computations, shared_word=shared, use_reason='; '.join(
            '%s (%s)' % (c['computation'], c['form']) for c in computations) + (
            '' if own else '; a partial form or a count only: the entry\'s own rows are not an operand of this piece'))
    if facts and facts.get('use') == 'context':
        return dict(use='context', computations=[], shared_word=None, use_reason=facts['reason'])
    if kind == 'picture':
        if disposition in ('arrived', 'thin'):
            return dict(use='context', computations=[], shared_word='exposed' if disposition == 'arrived' else 'thin',
                        use_reason='in the market pictures (the anchor pictures in the component evidence and the full reader), '
                                   'counted on the pass; no computation of this piece reads it as an operand' + (
                                       '; %s not computed: %s' % (NATIVE_ENTRY_COMPUTATION, native.get('reason'))
                                       if native else ''))
        if disposition == 'arrived_no_event':
            return dict(use='absent', computations=[], shared_word='exposed',
                        use_reason='carrier present; no event of this kind in the exhausted source on this day (a measurement, '
                                   'not a missing layer)')
        if facts:
            return dict(use='absent', computations=[], shared_word=None,
                        use_reason='%s; %s' % (entry.get('reason') or disposition, facts.get('reason')))
        if native:
            return dict(use='absent', computations=[], shared_word=None,
                        use_reason='%s; %s: %s' % (entry.get('reason') or disposition, NATIVE_ENTRY_COMPUTATION, native.get('reason')))
        return dict(use='absent', computations=[], shared_word=None, use_reason=entry.get('reason') or disposition)
    reasons = {
        'completed': 'completed-only: its values are never yielded into a picture; only its completed-source disposition is '
                     'listed in the summary',
        'stamped': 'the whole-day causal cutoff bounding every answer; a bound, not an arithmetic operand',
        'consumer': 'read and applied by this piece (directive, policy identity, rules, knowledge selection or carry); it '
                    'governs the answers, not an arithmetic operand on this day',
        'control': 'the mode and binding this piece was given; a control, not an operand',
    }
    if kind in reasons:
        return dict(use='absent' if kind == 'completed' else 'context', computations=[], shared_word=None,
                    use_reason=reasons[kind])
    if kind == 'dipole':
        return dict(use='absent', computations=[], shared_word=None,
                    use_reason='no Dipole component evidence was recorded for this all-99 list')
    absent = {'not_read': 'not an input of this piece: ' + str(route.get('via')),
              'retired': 'retired: ' + str(route.get('via')), 'sealed': 'withheld by role (a sealed answer; never read)',
              'disabled': 'disabled by the existing policy; never activated',
              'output': 'an append-only output, not an input of this piece: ' + str(route.get('via'))}
    return dict(use='absent', computations=[], shared_word=None,
                use_reason=absent.get(kind, entry.get('reason') or 'no classroom route (integrity finding)'))


def _native_only_ingestion(entries):
    """The 18 native-only entries: the computation that ingests each, or why none does here and the closest existing one."""
    by_name = {e['layer']: e for e in entries}
    out = []
    for name in NATIVE_ONLY_ENTRIES:
        e = by_name.get(name) or {}
        computations = e.get('computations') or []
        own = [c for c in computations if c['form'] == 'own_rows']
        out.append(dict(entry=name, use=e.get('use'), native_layer=e.get('disposition'),
                        computations=[dict(computation=c['computation'], form=c['form']) for c in computations],
                        own_rows_computed=bool(own),
                        closest_existing_consumer=(None if own else NATIVE_ONLY_CLOSEST.get(name) or (
                            'no computation of this piece reads this entry\'s own rows today (%s). frankie_box_teach.facts '
                            'reads the lineage / recurrence section rows and only the traversal\'s candidate/episode counts; '
                            'the episode / candidate / detector_coverage rows themselves are read by frankie_box_joined_teacher '
                            'couplings and the search, not by the classroom' % e.get('use_reason')))))
    return dict(entries=out, searched=NATIVE_SEARCHED,
                rule='an entry is computed only when an existing computation of this piece took its rows (own_rows), its '
                     'recorded teacher form (teacher_form) or its INPUT-envelope carrier (thin_carrier); the six that were '
                     'context enter native_entry_arithmetic (the external-section equations against the Dipole rows, Greg '
                     '2026-10-07 night: 18 of 18); where an entry\'s own rows are absent the reason is named')


# ------------------------------------------------ the 13 external points (Greg via Frankie, 2026-10-07: tie them to the 99)
EXTERNAL_POINTS_SCHEMA = 'FRANKIE_CLASSROOM_EXTERNAL_POINTS_USE_V1'
EXTERNAL_COMPUTATION = ('external_section_arithmetic: the classroom\'s existing external section (dipole_classroom_external '
                        'key; Frankie\'s code answers in frankie_box_classroom_external_code: TEACH transcribed, GUIDED '
                        'computed, SOCRATIC/VERIFY on the learner-owned reading): per series the values known at the '
                        'cutoff, first/last/extremes, state counts over the Dipole rows, terminal state and first-to-last '
                        'direction; per pair against each of the 19 Dipole columns and every other series the direction '
                        'relation, Pearson with its overlap count and the co-movement counts')
EXTERNAL_AS_OF = ('each Dipole row takes, per series, the latest value published at or before the row\'s own ts_recv_ns '
                  '(AsOfReader at the classroom cutoff; a later stamp reaching a row is a hard AsOfViolation); a value '
                  'published after the cutoff is counted not yet known and never read')


def external_points_use(ext_ledgers, day_file, day_file_sha256, *, cutoff_ns=None):
    """Per external point: how the classroom uses it (computed / context / absent, same rule as the native entries), the
    series that entered the external section arithmetic with their PRESENT row counts, and the registry entries the day
    file DECLARES the point feeds (frankie_box_all99_coverage.external_point_entries; no mapping is invented here). The
    day file is read for its declarations only (bytes checked against the sha256 given); a row-level declaration is taken
    only from rows published at or before the cutoff. Never raises for coverage."""
    from research.kalshi.frankie_boss import dipole_classroom_external as EXT
    components = {c['name']: c for c in ((ext_ledgers or {}).get('external_teachback') or {}).get('components') or []}
    declared, findings, body = {}, [], None
    try:
        raw = Path(day_file).read_bytes()
        if hashlib.sha256(raw).hexdigest() != day_file_sha256:
            findings.append(dict(kind='integrity', reason='the day file differs from its sha256; no declaration read'))
        else:
            body = json.loads(raw)
    except (OSError, ValueError) as error:
        findings.append(dict(kind='unreadable', reason='%s: %s' % (type(error).__name__, error)))
    reader = getattr(ALL99, 'external_point_mapping', None)
    if body is not None and reader is None:
        findings.append(dict(kind='contract_absent', reason='frankie_box_all99_coverage.external_point_mapping is not in this '
                                                            'checkout; no point-to-entry declaration read'))
    tables = (body or {}).get('points') or {}
    row_keys = (set(getattr(ALL99, 'EXTERNAL_ENTRY_KEYS', ())) | set(getattr(ALL99, 'EXTERNAL_EVENT_TIME_KEYS', ()))
                | set(getattr(ALL99, 'EXTERNAL_MAPPING_KEYS', ())) | set(getattr(ALL99, 'EXTERNAL_NOTE_KEYS', ())))

    def tie_of(names):
        """The point's tie to the 99 and its placement, as the day file records them (Greg, 2026-10-07: every point
        mapped, `mapping: closest` with its reason when no exact fit; a value with no intrinsic event time sits at 14:00
        ET of its trading day, or at its publication when later, with the note). A readable row whose reader stamp is
        EARLIER than its declared event time (or than the table's 14:00 ET placement_ns when it has none) would let the
        external section read it before Greg's placement: counted as `read_before_event_time` / `read_before_placement`,
        an integrity finding listed beside the use (review R-B; the use word still says whether a value entered the
        arithmetic). A table without event_time_ns is a superseded publication-stamp shape, named."""
        tie = dict(entries=[], mapping=[], mapping_reason=[], event_time_basis=[], note=[], rows_read=0,
                   read_before_event_time=0, rows_with_event_time=0, read_before_placement=0, carried_whole=[],
                   tables_without_event_time=[])
        def add(key, value):
            if value is not None and value not in tie[key]:
                tie[key].append(value)
        for tname in names:
            table = tables.get(tname)
            if reader is None or not isinstance(table, dict):
                continue
            base = reader(table)
            findings.extend(dict(item, table=tname) for item in base['findings'])
            for name in base['entries']:
                add('entries', name)
            for key in ('mapping', 'mapping_reason', 'event_time_basis', 'note'):
                add(key, base[key])
            columns = table.get('columns') or []
            stamp_column = table.get('stamp_column') or 'published_ns'
            stamp = columns.index(stamp_column) if stamp_column in columns else None
            if tname in EXT.ROWS_CARRIED_WHOLE:
                tie['carried_whole'].append(tname)
            if 'event_time_ns' not in columns:
                tie['tables_without_event_time'].append(tname)     # a superseded (publication-stamp) table
            placement = table.get('placement_ns')                  # the 14:00 ET placement of a default_1400 table
            per_row = any(key in columns for key in row_keys)
            for row in table.get('rows') or []:
                if cutoff_ns is not None and stamp is not None and row[stamp] is not None and row[stamp] > cutoff_ns:
                    continue          # a row stamped after the cutoff is never read, its declarations included
                tie['rows_read'] += 1
                tied = reader(table, row) if per_row else base
                if per_row:
                    findings.extend(dict(item, table=tname) for item in tied['findings'] if item not in base['findings'])
                    for name in tied['entries']:
                        add('entries', name)
                    for key in ('mapping', 'mapping_reason', 'event_time_basis', 'note'):
                        add(key, tied[key])
                if tied['event_time_ns'] is not None:
                    tie['rows_with_event_time'] += 1
                    if stamp is not None and type(row[stamp]) is int and row[stamp] < tied['event_time_ns']:
                        tie['read_before_event_time'] += 1
                elif (type(placement) is int and stamp is not None and type(row[stamp]) is int
                      and row[stamp] < placement):
                    tie['read_before_placement'] += 1     # no event time of its own, stamped before 14:00 ET
        return tie
    points = []
    for p in EXT.POINTS:
        series = [name for name in components if EXT._matches(name, p['series'])]
        operands = [dict(series=name, present_rows=int((components[name].get('state_counts') or {}).get('PRESENT', 0)),
                         state_counts=components[name].get('state_counts')) for name in series]
        for o in operands:     # an operand with no PRESENT value is listed unavailable, never a zero
            o['unavailable'] = None if o['present_rows'] else (
                'no PRESENT value reached a Dipole row (null in the day file, not yet published, or not in the file; the '
                'key\'s segments and the day file\'s missing list carry the reason); only arithmetic that needs it waits')
        present = sum(o['present_rows'] for o in operands)
        tie = tie_of(p['tables'])
        entries = tie['entries']
        early = tie['read_before_event_time'] + tie['read_before_placement']
        placement_integrity = None
        if early:
            # Review R-B: a reader stamp earlier than the declared event time (or the 14:00 ET placement) lets the
            # external section read the row before Greg's placement. That is an integrity finding of its own, listed
            # beside the use; the use word still says what happened (a value that entered the arithmetic is computed,
            # never relabelled absent).
            placement_integrity = ('integrity: %d readable row(s) carry a reader stamp earlier than their declared event '
                                   'time and %d earlier than the 14:00 ET placement; the external section read them from '
                                   'that earlier stamp' % (tie['read_before_event_time'], tie['read_before_placement']))
            findings.append(dict(kind='external_read_before_event_time', point_id=p['point_id'],
                                 rows=tie['read_before_event_time'], rows_before_placement=tie['read_before_placement']))
        if tie['tables_without_event_time']:
            findings.append(dict(kind='external_publication_stamp_shape', point_id=p['point_id'],
                                 tables=list(tie['tables_without_event_time']),
                                 reason=EXT.STAMP_SHAPE_NOTES[EXT.STAMP_SHAPE_PUBLICATION]))
        if present > 0:
            use, reason = 'computed', ('its series entered the external section arithmetic at the Dipole rows at or after '
                                       'the stamp its reader placed it at')
        elif any(t in EXT.ROWS_CONTEXT_ONLY for t in tie['carried_whole']):
            use, reason = 'context', ('a superseded day-file shape: no value of its series entered the arithmetic; its '
                                      'rows (%s) are carried whole in the point review, no arithmetic reads them'
                                      % ', '.join(t for t in tie['carried_whole'] if t in EXT.ROWS_CONTEXT_ONLY))
        elif not p['series']:
            use, reason = 'context', ('no numeric series for this point; its tables are carried in the point review; no '
                                      'arithmetic reads them')
        elif not series:
            use, reason = 'absent', 'none of its series is in today\'s external section (absent from the day file; see missing)'
        else:
            use, reason = 'absent', ('no value of its series was published at or before any Dipole row of the window (a '
                                     'measurement, not a filled-in zero); the day stays')
        points.append(dict(point_id=p['point_id'], name=p['name'], use=use, reason=reason,
                           computation=EXTERNAL_COMPUTATION.split(':')[0] if use == 'computed' else None,
                           series=operands, tables=list(p['tables']), feeds_entries=entries,
                           mapping=tie['mapping'], mapping_reason=tie['mapping_reason'],
                           event_time_basis=tie['event_time_basis'], note=tie['note'],
                           placement=dict(rows_read=tie['rows_read'], rows_with_event_time=tie['rows_with_event_time'],
                                          read_before_event_time=tie['read_before_event_time'],
                                          read_before_placement=tie['read_before_placement'],
                                          integrity=placement_integrity,
                                          stamp_shape=(EXT.STAMP_SHAPE_PUBLICATION if tie['tables_without_event_time']
                                                       else EXT.STAMP_SHAPE_READER),
                                          tables_without_event_time=tie['tables_without_event_time']),
                           carried_whole=tie['carried_whole'],
                           feeds_listed=(None if entries else 'unmapped: the day file declares no registry entry for this '
                                         'point (Greg: every point maps, closest with its reason); listed, never guessed '
                                         'here (request to the day-file agent)'),
                           closest_existing_consumer=(None if use == 'computed' else
                                                      'the external section arithmetic (when a value is published) and the '
                                                      'scientific search\'s external.<alias> series')))
    # No point is deferred (Greg, 2026-10-07 night: point 6 is one of the 13 and is read like the others; the only dropped
    # item is the squeeze 3-day calendar-front spread, not a point). A point still listed in DEFERRED by an older section
    # module reads absent with that module's reason; the dropped spread is named once beside the points, never as a point.
    for p in EXT.DEFERRED.get('points') or ():
        tie = tie_of(p['tables'])
        points.append(dict(point_id=p['point_id'], name=p['name'], use='absent', computation=None, series=[],
                           tables=list(p['tables']), feeds_entries=tie['entries'], mapping=tie['mapping'],
                           mapping_reason=tie['mapping_reason'], event_time_basis=tie['event_time_basis'], note=tie['note'],
                           reason='not read by the external section module: ' + EXT.DEFERRED['reason'],
                           closest_existing_consumer='the scientific search reads its table'))
    feeds = {}
    for item in points:
        for entry in item['feeds_entries']:
            feeds.setdefault(entry, []).append(dict(point_id=item['point_id'], use=item['use'], mapping=item.get('mapping'),
                                                    note=item.get('note')))
    counts = {}
    for item in points:
        counts[item['use']] = counts.get(item['use'], 0) + 1
    return dict(schema=EXTERNAL_POINTS_SCHEMA, points=points, counts=counts, entries_fed=feeds, findings=findings,
                computation=EXTERNAL_COMPUTATION, as_of=EXTERNAL_AS_OF,
                # Greg, 2026-10-07 night: all 13 points are used; the only dropped item is not a point
                dropped=[{k: d.get(k) for k in ('name', 'reason')} for d in EXT.DEFERRED.get('dropped') or ()] or None,
                rule='a point is computed only when a value of its series was published at or before a Dipole row and '
                     'entered the external section arithmetic; never before its publication time; a point the day file '
                     'ties to no registry entry is listed outside the 99, never mapped here')


_MARKET_TEXT_ENCODING = 'typed mapping entries; scalar tags c15_journal.pack'


def _market_encode(item, splice=None):
    """The typed tree of one value (see _exact_market_text). `splice(item)`, when given, returns a marker string for an
    item whose JSON text is already known (the anchor pictures), else None."""
    from research.kalshi.frankie_boss.c15_journal import SerializedObservation, pack

    def encode(item):
        if splice is not None:
            mark = splice(item)
            if mark is not None:
                return mark
        if isinstance(item, SerializedObservation):
            return encode(item.materialize())
        if isinstance(item, dict):
            # Reports can key dispositions by integer instrument identity. Preserve
            # key type explicitly instead of letting JSON silently stringify it.
            return ['mapping', [[pack(key), encode(child)] for key, child in item.items()]]
        if isinstance(item, (tuple, list)):
            return ['tuple' if isinstance(item, tuple) else 'list', [encode(child) for child in item]]
        return pack(item)
    return encode(item)


def _picture_text(picture):
    """The JSON text of one picture's typed tree, exactly as it sits inside _exact_market_text's output."""
    return json.dumps(_market_encode(picture), separators=(',', ':'))


def _exact_market_text(value, texts=None):
    """Carry all original fields, bytes and float bits; never numpy/repr truncation.

    `texts` (ClassroomMarketContext.picture_texts: id(picture) -> (picture, its _picture_text)): a picture already
    encoded is spliced in as its text instead of being walked again (Greg, 2026-10-07 night: the anchor pictures, the
    latest full book of every instrument, were encoded once per component that names them). The output is the same
    bytes: json.dumps with these separators writes a list element exactly as it writes that element alone, and each
    splice point is a fresh random marker that must occur exactly once in the text (else the plain walk runs)."""
    if texts:
        import uuid
        token, marks = uuid.uuid4().hex, {}

        def splice(item):
            hit = texts.get(id(item))
            if hit is None or hit[0] is not item:
                return None
            mark = '\x00frankie-picture:%s:%d\x00' % (token, len(marks))
            marks[json.dumps(mark)] = hit[1]
            return mark
        text = json.dumps(dict(encoding=_MARKET_TEXT_ENCODING, complete_value=_market_encode(value, splice)),
                          separators=(',', ':'))
        found = sorted((text.find(mark), mark) for mark in marks)
        if all(position >= 0 and text.count(mark) == 1 for position, mark in found):
            pieces, at = [], 0
            for position, mark in found:
                pieces += [text[at:position], marks[mark]]
                at = position + len(mark)
            pieces.append(text[at:])
            return ''.join(pieces)
    return json.dumps(dict(encoding=_MARKET_TEXT_ENCODING, complete_value=_market_encode(value)), separators=(',', ':'))


_PICTURE_SHARED = {}


def _picture_text_job(cursor):
    return _picture_text(_PICTURE_SHARED['pictures'][cursor])


def picture_texts(pictures):
    """{id(picture): (picture, text)} for every retained anchor picture (cursor -> picture), each encoded ONCE: on a
    pinned fork pool over the booked CPUs (frankie_box_lane_pin.ordered_map; a dead worker's picture is redone with
    one worker fewer) when this process can fork, else here one after another. The placement goes on PINNING_RECORD."""
    import gc
    import multiprocessing
    import time
    started = time.monotonic()
    cursors = [c for c in sorted(pictures) if isinstance(pictures[c], dict)]
    lane = lane_cpus()
    workers = min(len(lane), len(cursors))
    forkable, waited, why = _fork_ready() if workers > 1 else (False, 0.0, 'one picture or one CPU')
    texts, report = {}, {}
    # periodic exact saves per picture text in cursor order (_Segments); a resume encodes only the rest
    segments = _Segments('picture_texts', cursors)
    done = segments.load()                     # [(cursor, text)] in cursor order
    for cursor, text in done:
        texts[id(pictures[cursor])] = (pictures[cursor], text)
    arrived = list(done)
    rest = cursors[len(done):]
    if forkable and len(rest) > 1:
        LP = _lane_pin()
        _PICTURE_SHARED['pictures'] = pictures
        gc.freeze()
        mapped = LP.ordered_map(_picture_text_job, rest, max(1, min(workers, len(rest))), cpus=lane,
                                context=multiprocessing.get_context('fork'), poll=5.0, report=report)
        try:
            for cursor, text in mapped:
                texts[id(pictures[cursor])] = (pictures[cursor], text)
                arrived.append((cursor, text))
                heartbeat('classroom: anchor picture texts', len(texts), len(cursors), unit='pictures', every=1.0)
                segments.offer(arrived)
        finally:
            mapped.close()                     # the pool is stopped now (bounded)
            gc.unfreeze()
            _PICTURE_SHARED.clear()
        record = dict(LP.record(workers, lane, what='classroom anchor picture texts (fork pool, ordered_map)'),
                      worker_deaths=report.get('worker_deaths'), redone=report.get('redone'))
    else:
        for cursor in rest:
            text = _picture_text(pictures[cursor])
            texts[id(pictures[cursor])] = (pictures[cursor], text)
            arrived.append((cursor, text))
            segments.offer(arrived)
        record = dict(workers=1, where='this process, one picture after another', why=why or 'one picture left')
    segments.done()
    record['resumed_pictures'] = len(done)
    PINNING_RECORD['picture_texts'] = dict(record, pictures=len(cursors), waited_for_threads_s=waited,
                                           characters=sum(len(t) for _, t in texts.values()),
                                           seconds=round(time.monotonic() - started, 3),
                                           rule='each anchor picture encoded once and spliced into every component '
                                                'answer that names it; the answer text is the same bytes')
    return texts


# ---- the 19 component answers side by side (endings pass, 2026-10-08; Greg: "CPUs in every step of this ending
# process"). component_answer is a pure function of its arguments and of module state that is only READ here
# (_EVIDENCE_CACHE filled by the runner's guided_evidence phase, the spliced picture texts keyed by object identity,
# TEACHER_FORM_COMPONENTS, STATES): a process forked from the runner holds the same objects at the same addresses, so a
# worker computes the same value, and the value comes back through the pool's pickle with its object sharing intact,
# so the phase file the runner saves holds the same bytes as an in-process answer (toy-proven: endings/selftest). ----
_ANSWER_SHARED = {}


def _component_answer_job(name):
    s = _ANSWER_SHARED
    return component_answer(s['visible'], s['components'][name], s['rights'][name], learner_context=s['learner_context'],
                            shared_market=s['shared_market'], exhaustion_d=s['exhaustion_d'])


def component_answers_side_by_side(visible, names, components, rights, *, learner_context=None, shared_market=None,
                                   exhaustion_d=None, on_start=None):
    """Yield (name, component_answer(visible, components[name], rights[name], ...)) for `names` in that order: on a
    pinned fork pool over the booked lane (frankie_box_lane_pin.ordered_map; a dead worker's answer is redone with one
    worker fewer) when this process can fork and more than one answer is wanted, else here one after another with the
    reason recorded. on_start(), when given, is called once the workers are forked (or at the start of the serial path),
    so the caller can begin an independent computation on a thread beside the answers. The placement goes on
    PINNING_RECORD['component_answers']. A value is identical either way (see the section note)."""
    import gc
    import multiprocessing
    import time
    started = time.monotonic()
    names = list(names)
    lane = lane_cpus()
    workers = min(len(lane), len(names))
    forkable, waited, why = _fork_ready() if workers > 1 else (False, 0.0, 'one answer or one CPU')
    report, done = {}, 0
    if forkable:
        LP = _lane_pin()
        _ANSWER_SHARED.update(visible=visible, components=components, rights=rights, learner_context=learner_context,
                              shared_market=shared_market, exhaustion_d=exhaustion_d)
        gc.freeze()
        mapped = LP.ordered_map(_component_answer_job, names, workers, cpus=lane,
                                context=multiprocessing.get_context('fork'), poll=5.0, report=report,
                                on_start=(lambda pool: on_start()) if on_start is not None else None)
        try:
            for name, value in mapped:
                done += 1
                heartbeat('classroom: component answers', done, len(names), unit='components', every=1.0)
                yield name, value
        finally:
            mapped.close()                     # the pool is stopped now (bounded)
            gc.unfreeze()
            _ANSWER_SHARED.clear()
            PINNING_RECORD['component_answers'] = dict(
                LP.record(workers, lane, what='classroom component answers (fork pool, ordered_map)'),
                worker_deaths=report.get('worker_deaths'), redone=report.get('redone'), answers=len(names),
                yielded=done, waited_for_threads_s=waited, seconds=round(time.monotonic() - started, 3),
                rule='each component answer computed once on a worker and saved by the runner in name order; the '
                     'same value as an in-process answer')
    else:
        if on_start is not None:
            on_start()
        try:
            for name in names:
                yield name, component_answer(visible, components[name], rights[name], learner_context=learner_context,
                                             shared_market=shared_market, exhaustion_d=exhaustion_d)
                done += 1
                heartbeat('classroom: component answers', done, len(names), unit='components', every=1.0)
        finally:
            PINNING_RECORD['component_answers'] = dict(
                workers=1, where='this process, one answer after another', why=why, answers=len(names), yielded=done,
                waited_for_threads_s=waited, seconds=round(time.monotonic() - started, 3))


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
    order = [(left, right) for i, left in enumerate(names) for right in names[i + 1:]]
    measured = _pair_measures(math, ledgers, order)
    review = []
    for (left, right), (correlation, co_movement) in zip(order, measured):
        review.append(dict(left=left, right=right,
                           direction_relation=math._direction_relation(directions[left], directions[right]),
                           correlation=correlation, co_movement=co_movement,
                           interpretation_limit='DESCRIPTIVE_WITHIN_CAUSAL_WINDOW_NOT_CAUSATION_OR_FUTURE_PREDICTION',
                           computed_by=AUTHOR))
    return dict(pre, components=comps, relationship_review=review, evidence_source=origin)


# The 171 Dipole pairs on the lane's CPUs (Greg, 2026-10-07: every piece uses the lane). dipole_classroom._pearson and
# _co_movement are pure Python over the whole-day ledgers, so threads cannot help (GIL). A fork pool shares the ledgers
# copy-on-write (nothing pickled in), runs the SAME functions per pair and returns their dicts in pair order, so every
# value is the one the serial loop computes. Fork is taken only on Linux and only while this process runs one thread (a
# fork beside live threads can inherit a held lock); otherwise the serial loop runs. The choice is recorded in
# PAIR_POOL_RECORD for the receipt.
_PAIR_SHARED = {}
PAIR_POOL_RECORD = {}


def _pair_job(index):
    math, ledgers, order = _PAIR_SHARED['math'], _PAIR_SHARED['ledgers'], _PAIR_SHARED['order']
    left, right = order[index]
    return math._pearson(ledgers[left], ledgers[right]), math._co_movement(ledgers[left], ledgers[right])


def _pair_measures(math, ledgers, order):
    import os
    import threading
    import time
    started = time.monotonic()
    workers = min(len(lane_cpus()), len(order))         # the booked CPUs (16 or 32)
    use_fork = sys.platform.startswith('linux') and threading.active_count() == 1 and workers > 1
    if use_fork:
        import multiprocessing
        from concurrent.futures.process import BrokenProcessPool
        _PAIR_SHARED.update(math=math, ledgers=ledgers, order=order)
        context = multiprocessing.get_context('fork')
        LP = _lane_pin()
        lane = lane_cpus()
        # Every worker pinned to its own lane CPU, physical cores first (frankie_box_lane_pin.executor; a refused pin
        # falls back to the lane). A dead worker never stops or hangs the classroom (Greg, 2026-10-07): the pool reports
        # it (BrokenProcessPool), every pair already measured is kept, and the pairs it lost are measured again by a
        # new pool with one worker fewer; with one worker left (or a live thread beside, where no fork is taken) they
        # run in this process. Same functions, results placed by pair index: the values are the serial loop's.
        measured, live, rounds = [None] * len(order), workers, []
        # periodic exact saves of the measured pairs in pair order (_Segments); a resume measures only the rest
        segments = _Segments('dipole_pairs', [list(pair) for pair in order])
        resumed = segments.load()
        measured[:len(resumed)] = resumed
        contiguous = [len(resumed)]

        def offer():
            while contiguous[0] < len(measured) and measured[contiguous[0]] is not None:
                contiguous[0] += 1
            segments.offer(measured[:contiguous[0]])
        try:
            while any(m is None for m in measured):
                remaining = [i for i, m in enumerate(measured) if m is None]
                if live <= 1 or threading.active_count() > 1:
                    for i in remaining:
                        measured[i] = _pair_job(i)
                        offer()
                    rounds.append(dict(workers=1, pairs=len(remaining), where='this process (serial)'))
                    break
                futures, broken = [], None
                try:
                    with LP.executor('process', live, lane, mp_context=context) as pool:
                        futures = [(i, pool.submit(_pair_job, i)) for i in remaining]
                        try:
                            for i, future in futures:
                                try:
                                    measured[i] = future.result()
                                except BrokenProcessPool as error:
                                    broken = error
                                    break
                                heartbeat('classroom: dipole pairs', sum(m is not None for m in measured), len(order),
                                          unit='pairs', every=1.0)
                                offer()
                        except BaseException:
                            # a requested save (TeacherSaved) or a failure: queued pairs are cancelled, so the
                            # executor's exit waits only for the pairs already running (bounded)
                            pool.shutdown(wait=False, cancel_futures=True)
                            raise
                except BrokenProcessPool as error:
                    broken = broken or error
                if broken is None:
                    rounds.append(dict(workers=live, pairs=len(remaining), cpu_map=LP.record(live, lane)))
                    break
                for i, future in futures:          # keep every pair a worker finished before the pool broke
                    if measured[i] is None and future.done() and not future.cancelled() and future.exception() is None:
                        measured[i] = future.result()
                rounds.append(dict(workers=live, pairs=len(remaining), lost=sum(m is None for m in measured),
                                   broken='%s: %s' % (type(broken).__name__, broken)))
                live -= 1
        finally:
            _PAIR_SHARED.clear()
        segments.done()
        PINNING_RECORD['dipole_pair_processes'] = dict(workers=workers, rounds=rounds, resumed_pairs=len(resumed))
        basis = ('fork pool (%d workers, each pinned to one lane CPU, physical cores first%s); same functions, pair order '
                 'kept' % (workers, '' if len(rounds) <= 1 else '; a dead worker\'s pairs measured again with one worker '
                                                               'fewer (rounds in received.cpu_pinning)'))
    else:
        # the same per-pair calls in pair order, with the same periodic exact saves as the pool path (_Segments)
        segments = _Segments('dipole_pairs', [list(pair) for pair in order])
        measured = segments.load()
        for a, b in order[len(measured):]:
            measured.append((math._pearson(ledgers[a], ledgers[b]), math._co_movement(ledgers[a], ledgers[b])))
            segments.offer(measured)
        segments.done()
        basis = ('serial: %s' % ('more than one live thread (no fork beside threads)' if threading.active_count() > 1
                                 else 'one CPU or not Linux'))
    PAIR_POOL_RECORD.update(pairs=len(order), basis=basis, seconds=round(time.monotonic() - started, 3))
    return measured


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


def component_answer(visible, comp, rights, *, learner_context=None, shared_market=None, exhaustion_d=None):
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
            + _exact_market_text(shared_market.component(visible, name), getattr(shared_market, 'picture_texts', None))
            + '. These anchors supplement the full ordered source accessible through the answer context; an absent '
            'layer or picture makes the instant thinner, never removes it; the Dipole values and target equations '
            'are unchanged.')
        paired = native_entries_for_component(shared_market.native_entries(), name)
        if paired:
            # 18 of 18 (Greg, 2026-10-07 night): the six native entries' own series computed against this component
            result['evidence'] += (' Native entry arithmetic against this component (each series of the six native entries '
                'that were context, per instrument, with the external-section equations: relation, Pearson, co-movement): '
                + json.dumps(paired, sort_keys=True) + '. Every pair is whole in %s; descriptive for this window only, no '
                'causation or outcome claimed (rules R01, R02, R05).' % _native_file_text(shared_market))
    second = _second_set_text(learner_context, name)
    if second is not None:
        result['evidence'] += (' The teacher\'s second set at this component\'s anchor rows (first / last / minimum / '
            'maximum PRESENT): the row key, the seven causal clocks (clock_lock_time is the teacher\'s as_of), every '
            'plane the picture placed at that instant read by its reference, and the book columns: ' + second
            + '. Every row\'s second set is whole in package.second_set.jsonl; nothing in it changes a Dipole value.')
    native = _facts_for_component(exhaustion_d, name)
    if native:
        # The registry entries whose teacher form is this component also had their own native rows computed by
        # frankie_box_teach.facts today; their operands and row counts are carried here (no new relation claimed).
        result['evidence'] += (' The same registry entries\' own native rows, computed today by Frankie\'s code '
            '(frankie_box_teach.facts; completed whole-day bedrock rows): ' + json.dumps(native, sort_keys=True, default=str)
            + '. The registry entry links this component to those rows; no relation between them is computed or claimed.')
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


def summary_answer(visible, outputs, *, learner_context=None, shared_market=None, exhaustion_d=None):
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
    facts_text = exhaustion_d_text(exhaustion_d)
    if facts_text:
        cycle_summary += ' ' + facts_text
    if shared_market is not None:
        cycle_summary += ' ' + native_entries_text(shared_market)
    correlation_review =(f'{AUTHOR}: {len(review)} pairs ({pre["evidence_source"]}). Relation: {json.dumps(relations, sort_keys=True)}. Pearson reported '
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
        lesson = (learner_context.get('second_set') or {}).get('lesson')
        if isinstance(lesson, dict):
            resolver = (lesson.get('anchors_resolved') or {}).get('resolver') or {}
            cycle_summary += (' The teacher\'s second set read beside the Dipole rows: ' + json.dumps(dict(
                status=lesson.get('status'), rows=lesson.get('rows'), carried=lesson.get('carried'),
                plane_entries=len(lesson.get('planes') or {}), match_status=lesson.get('match_status'),
                clock_lock_time=lesson.get('clock_lock_time'), anchors=resolver.get('note'),
                file=(lesson.get('file') or {}).get('path')), sort_keys=True, default=str) + '.')
        correlation_review += (' Legal learner knowledge was applied before these answers. Each prior source and '
            'its individual check, with original scope retained: ' + json.dumps(notes, sort_keys=True, default=str)
            + '. Prior findings are not relabelled as observations from this window; unavailable conditions supply '
            'no new test and do not downgrade a checked finding.')
        for kind, result in learner_context.items():
            for item in result.get('listed', []):
                if kind == 'second_set':
                    questions.append('The teacher\'s second set, listed (not filled in): %s' %
                                     json.dumps(item, sort_keys=True, default=str))
                    continue
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
