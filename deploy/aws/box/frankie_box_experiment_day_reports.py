"""The experiment's day reports (Greg, 2026-09-29: "make sure classroom is printing out an analysis after every day has
gone through it, and same with Frankie, and have them number their reports"; "There will be (3) #1's and so on";
"Write plain language interpreters to their code. I don't want you making interpretations").

For ONE classroom day this step READS the classroom's outputs (frankie_box_experiment_classroom_v2.py writes them into
<calculations>/work/classroom/; that step and everything it imports are not touched or re-run) and the brain entry its
receipt names, and writes two reports. The writers are deterministic TRANSLATORS of what the code recorded: every
recorded field becomes a fixed plain-English sentence or table row defined here (a template per field), so the same
input always gives the same text. No interpretation, no conclusion, no ranking, no judgement, no average or pooled
coefficient (D37); values are shown exactly as recorded; anything absent is stated as "not recorded" with the recorded
reason where there is one; the glossary is constant text; hashes and paths appear only in the Evidence section.

  CLASSROOM REPORT #N  classroom-report-NNNN.md  the recorded counts; what the teacher taught; the grade per component
                       (graded correct or incorrect and the recorded difference); the corrections and their recorded
                       messages; the acknowledgement; the novel and dropped findings; teacher completion; what was
                       carried in from the previous day; the external section (Greg's 13 historical data points: per
                       point its series and missing counts with the recorded reasons, graded correct or incorrect, the
                       external corrections, mastered)
  FRANKIE REPORT #N    frankie-report-NNNN.md    Frankie's recorded answers per component and their grade, his recorded
                       correction answers and acknowledgement, his external answers and their grade, the novel findings
                       he filed, and the brain entry written for the day (path, files, bytes)

A refused classroom day still gets both reports, stating the recorded refusal and its reason (the classroom's own
receipt, or the orchestrator's reason given as --refused-reason when the classroom never wrote one).

THE THREE-WAY EXCHANGE (2026-09-29): the orchestrator runs this step after the day's exchange stage
(frankie_box_experiment_exchange.py) and gives its exchange.json as --exchange (or --exchange-listed, the reason there is
none). Both reports then carry "The three-way exchange": the recorded counts, every item with the BOSS teacher's and the
scientific teacher's recorded turns (position, reasoning, checks, proposed tests), the teachers' own findings; the
FRANKIE report adds his recorded reply per item (position, resolution, his corrected understanding, the disagreement he
still holds, or the recorded reason his turn is withheld). The same fixed templates; nothing interpreted. The exchange's
sha256 is part of the reports' source: reports built before it, or from another exchange, are superseded by a revision
with the same N.

NUMBERING (Greg: "There will be (3) #1's and so on"). N is ONE number per trade day, shared by that day's Classroom,
Frankie and Jev reports. The orchestrator reserves it right after the day's classroom step (reserve_number, the same
rule and index), where this step used to run, so the numbering is unchanged now that the reports follow the exchange.
It is assigned once per (run, day) under an exclusive lock on <reports-dir>/.lock: an existing
(run, day) entry in <reports-dir>/index.json is reused, never renumbered; otherwise N = 1 + the highest day number in the
index or in any report file name there. A number is never given to another day. With Frankie's class line
(frankie_box_frankie_queue.py) the class worker reserves N = the day's SCHOOL-DAY number (its position in the class line)
when it takes the day, before the classroom, so this step, the school step and Jev's dispatch all read that N. A report file is never overwritten
(written 'xb'): when the day's reports already exist and were built from the same classroom receipt they are printed
again; when the classroom has changed since (refused, then run again) the new reports keep N and are written as
revision r2, r3, ... (classroom-report-NNNN-r2.md), naming the file they supersede. Each report goes into the reports
dir (default /opt/frankie-box/work/experiment-reports) and into the classroom dir, and both are PRINTED in full to
stdout (how Greg sees them in the workflow log; ssm_run_sh.py pages long output, nothing is cut here). The last two lines
are REPORT_NUMBER=N and a small receipt JSON (the number, each file and its sha256). The Jev Pod dispatch of the same day
takes REPORT_NUMBER=N so his report is JEV REPORT #N (research/kalshi/frankie_boss/clm_sidecar/jev_report.py).
No model call or Pod. A receipt-verified completed Granite discussion is translated only in the Frankie report;
it has no evidentiary authority, and requested tests remain requests, not results.

THE SCHOOL FILE (2026-10-07, stage 12 of SPEC-experiment-orchestrator section 0: the end of day consolidates the brain,
lessons and exchange already written during the day into school knowledge AND the numbered reports; never the first
knowledge write). The orchestrator runs the school step before this one and gives the day's FRANKIE_SCHOOL_KNOWLEDGE_V1
file as --school (<brain>/school/<day>.json, or a retained checked successor <brain>/school/successors/<day>/<op>/
school.json) or --school-listed, the reason there is none. The FRANKIE report then carries "The school file": per section
its author and items (how each was carried: inline, a stated subset, or a pointer with its reason), and every item the
school listed missing or withheld with its recorded reason. Fixed templates, nothing interpreted. The file is read once
and hashed once; an indexed original is checked against its index row, a successor against its receipt. A mismatch is an
INTEGRITY failure (stated in the report, on the receipt and in the exit code), never a missing-data disposition; a day
without a school file is a thinner picture, reported as such. The school file's sha256 is part of the reports' source
(a report built before it is superseded by a revision with the same N). The reports are never knowledge.

THE RECEIPT FILE and the one-day inspection (Greg, 2026-10-07: every input received, how it was used, what was produced,
and nothing silent). Besides the last stdout line, run() writes the same receipt to <reports-dir>/receipts/<run>/<day>.json
(the path frankie_box_workflow_inspection.artifact_paths reads for the 'school' piece): every file read with its path,
bytes and sha256 (inputs), every absent or unreadable file with its reason, the exchange/meeting/school dispositions, the
reuse decision and why, the problems, the phase timings (seconds; receipt only, so the report bytes stay deterministic),
and a FRANKIE_PIECE_WORKFLOW_REPORT_V1 (inputs / use / outputs). The receipt is diagnostic and never knowledge.

THE 99 LAYERS (2026-10-07, Greg: "the 99 layers combined for Frankie FIRST"). The FRANKIE report carries "The 99 layers
(what reached Frankie today)": ONE per-day table of the 99 entries of the shared registry (frankie_box_all99_coverage,
imported, never copied), joined from the list every piece already records (ALL99_PIECES: the ROOT's admission list on its
step receipt, the classroom receipt's all99_coverage, the pinned FRANKIE_ALL99_COVERAGE_V1 lists the scientific teacher's
lessons / the carried claims / the candidate update name, the exchange / meeting / Jev workflow_report.use.all_99_coverage).
Each list is read once (a pinned list is checked against its pin; the school file's whole inline copy of a lessons file is
used instead of a re-read); nothing is recomputed. Per entry: the word each piece recorded, the final disposition for Frankie
(FINALS: classroom / classroom_thin / other_computation / consumer / nothing / unknown), every entry no Frankie piece
recorded in a computation with every piece's recorded reason, and every disagreement between pieces under fixed rules
(JOIN_RULES). A piece without a list reads "not reported by <piece>" with its reason (unknown, never zero); integrity
failures stay separate. The ROOT and Jev's pieces are listed and never decide what reached Frankie. The full join is
receipt['all99'] (ALL99_JOIN_SCHEMA); its sha256 over the pieces' inputs is part of the reports' source (a changed list
gives a revision with the same N). Diagnostic only, never knowledge. Nothing here keys on how many days a run holds: the
numbering is 1 + the highest number held (N=1 for a one-day run, any N after) and reuse is per (run, day).

LATE PIECES (2026-10-07 second review F9; correction_consumer). Jev and the cross-day candidates normally finish after the
reports. late_pieces_changed(receipt, current) is a pure read (no write, no lock, no report rendering): it recomputes
the join's input set (join_inputs: piece, status, file, sha256, basis; collect_all99 itself, on a Day read join_only) from
the invocation the receipt recorded (all99_invocation), overridden key by key by `current` (what the orchestrator would
pass now), and compares it with the input set the receipt recorded. Three outcomes: 'changed' (a revision with the same N
is due), 'unchanged', 'unknown' (it could not read what it needs; the reason is returned). The scientific teacher's lessons
list is the lesson inputs the exchange document itself records (sources.lessons; current after a reused or successor
exchange), its basis recorded beside it (LESSONS_BASIS), so a possibly stale list is never shown as a current one.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import signal
import sys
import time
from pathlib import Path

SCHEMA = 'FRANKIE_EXPERIMENT_DAY_REPORTS_RECEIPT_V1'
INDEX_SCHEMA = 'FRANKIE_EXPERIMENT_DAY_REPORTS_INDEX_V1'
SCHOOL_SCHEMA = 'FRANKIE_SCHOOL_KNOWLEDGE_V1'              # frankie_box_school_knowledge.SCHEMA (read, never written here)
SCHOOL_INDEX_SCHEMA = 'FRANKIE_SCHOOL_INDEX_V1'             # frankie_box_brain.SCHOOL_INDEX_SCHEMA
PIECE_WORKFLOW_REPORT = 'FRANKIE_PIECE_WORKFLOW_REPORT_V1'  # the one-day inspection record (frankie_box_workflow_inspection)
REPORTS = Path('/opt/frankie-box/work/experiment-reports')
# THE 99 LAYERS (Greg, 2026-10-07: "the 99 layers combined for Frankie FIRST"): the join of every piece's own all-99 list
ALL99_JOIN_SCHEMA = 'FRANKIE_DAY_REPORTS_ALL99_JOIN_V1'
STEP_SCHEMA = 'FRANKIE_EXPERIMENT_STEP_V1'                # frankie_box_experiment.Run.record (read, never written here)
RUNS = Path('/opt/frankie-box/work/experiment')           # frankie_box_experiment.RUNS: <run>/days/<day>/<stage>.json
SURVIVORS = Path('/opt/frankie-box/work/experiment-survivors')   # frankie_box_survivor_update.ROOT: <run>/<boundary>/receipt.json
LESSONS_ROOT = Path('/opt/frankie-box/work/experiment-teacher')  # frankie_box_experiment.LESSONS_ROOT
# (piece, reaches Frankie?, where its list is read). Every piece is read once, from what it recorded; nothing is recomputed.
ALL99_PIECES = (
    ('root', False, 'the ROOT step receipt <run-dir>/days/<day>/root.json, field all99 (FRANKIE_ALL99_ADMISSION_V1): what '
                    'the ROOT produced and admitted into the shared picture (a producer, not a consumer)'),
    ('classroom', True, 'the classroom receipt.json, field all99_coverage (FRANKIE_CLASSROOM_ALL99_COVERAGE_V1)'),
    ('scientific_teacher[frankie]', True, 'Frankie\'s lessons file the exchange consumed, field all99_coverage.by_day[<day>]: '
                                          'the pinned FRANKIE_ALL99_COVERAGE_V1 list'),
    ('scientific_teacher[historical]', True, 'the historical lessons file the exchange consumed, field '
                                             'all99_coverage.by_day[<day>]: the pinned FRANKIE_ALL99_COVERAGE_V1 list'),
    ('scientific_teacher[jev]', False, 'Jev\'s lessons file the exchange consumed, field all99_coverage.by_day[<day>]: the '
                                       'pinned FRANKIE_ALL99_COVERAGE_V1 list (Jev\'s claims; Frankie\'s view withholds them)'),
    ('carried_claims', True, 'the accumulated-lessons step receipt <run-dir>/days/<day>/accumulated_lessons.json names its '
                             'receipt; workflow_report.outputs.all99_coverage_files[<day>]: the pinned list'),
    ('candidates', True, 'the survivor/candidate update receipt (<survivors>/<run>/<day>/receipt.json at a boundary day, or '
                         'given): workflow_report.outputs.all99_coverage_files[<day>]: the pinned list'),
    ('exchange', True, 'the exchange receipt.json beside exchange.json, workflow_report.use.all_99_coverage'),
    ('meeting', True, 'the meeting receipt (read once by frankie_box_brain.read_meeting_for_exchange), '
                      'workflow_report.use.all_99_coverage'),
    ('jev', False, 'the Jev step receipt <run-dir>/days/<day>/jev.json names JEV_CPU_RECEIPT_V1: '
                   'workflow_report.use.all_99_coverage'),
    ('jev_sit_in', False, 'the Jev client receipt pinned by JEV_CPU_RECEIPT_V1: workflow_report.use.all_99_coverage'),
)
PICTURE_READERS = ('classroom', 'exchange', 'meeting', 'jev', 'jev_sit_in')     # pieces that read the shared picture
# How a recorded word is read (correction_consumer, 2026-10-07 second pass): the CANONICAL word and its class come from the
# one registry (frankie_box_all99_coverage, 9464189e; never a local vocabulary here): the shared field's own `disposition`
# when the row carries one (computed and settled by frankie_box_all99_coverage.field), else the registry's LEGACY_WORDS
# mapping of the piece's word, then the registry's FIXED_WORDS settlement of the entry; the class is the registry's
# WORD_CLASS of that canonical word. The refinements below read the PIECE's own word (`piece_disposition`, the word the
# piece recorded) and only split the registry's 'arrived' class (so a consumer or a rule is not counted as a computation)
# and its thin / completed-only classes; both words are always shown:
#   computation / computation_thin   reached what the piece computes on, wholly / partially (thin, completed-only)
#   consumer / governs               reached the piece's own consumer / a rule the piece enforces; not a computation
#   picture                          ROOT only: admitted into the shared picture (producer side)
#   exposed / absent / unknown / not_this_piece / withheld / disabled / retired / output / unmapped   the registry classes
#   integrity / unclassified         the registry's integrity class / a word the registry does not map
REACH_REFINE = {'knowledge_consumer': 'consumer', 'arrived_at_consumer': 'consumer', 'enforced_by_rule': 'governs',
                'admitted': 'picture'}
REACHED = ('computation', 'computation_thin', 'consumer', 'governs')


def canonical_of(A99, entry, piece_word, recorded_word=None, recorded_class=None):
    """(canonical word, class, settled, class_differs) of one row from the one registry module A99. recorded_word: the
    shared field's own `disposition` (None for a piece's legacy list); recorded_class: the row's `class` as recorded.
    settled: the registry's FIXED_WORDS correction of the entry's word (listed, as frankie_box_all99_coverage.field lists
    it); class_differs: a recorded class that contradicts the registry's class of the word (an integrity finding of the
    piece's field, never relabelled). Both None when there is nothing to say."""
    vocabulary, legacy = getattr(A99, 'VOCABULARY', {}), getattr(A99, 'LEGACY_WORDS', {})
    canon = (recorded_word if recorded_word in vocabulary else piece_word if piece_word in vocabulary
             else legacy.get(piece_word))
    settled = differs = None
    fixed = (getattr(A99, 'FIXED_WORDS', None) or {}).get(entry)
    if fixed is not None and canon is not None and canon != fixed:
        settled = 'the registry settles %s as %s (FIXED_WORDS); the piece\'s word %s maps to %s' % (entry, fixed, piece_word,
                                                                                                    canon)
        canon = fixed
    klass = (getattr(A99, 'WORD_CLASS', None) or {}).get(canon) if canon else None
    if recorded_class is not None and klass is not None and recorded_class != klass:
        differs = 'the row recorded class %s; the registry\'s class of %s is %s (the registry\'s is used)' % (
            recorded_class, canon, klass)
    return canon, klass or 'unclassified', settled, differs


def reach_of(piece_word, klass):
    """The reach group of one row: the registry class (canonical_of), split by the piece's own word (REACH_REFINE)."""
    if klass is None or klass == 'unclassified':
        return 'unclassified'
    if klass == 'arrived':
        return REACH_REFINE.get(piece_word, 'computation')
    if klass in ('thin', 'completed_only'):
        return 'computation_thin'
    return klass
KINDS = ('classroom', 'frankie', 'teacher', 'root')
FILE_RE = re.compile(r'^(classroom|frankie|teacher|root)-report-(\d{4,})(?:-r(\d+))?\.md$')
CLASS_OF_WEEKDAY = {0: 'monday', 1: 'midweek', 2: 'midweek', 3: 'thursday', 4: 'friday'}   # the orchestrator's classes
JSON_FILES = ('code-answers.json', 'ledgers.json', 'post-grade.json', 'novel-findings.json', 'novelty-investigation.json',
              'correction-request.json', 'correction-response.json', 'acknowledgement.json', 'completion.json',
              'external-code-answers.json', 'external-post-grade.json', 'external-correction-request.json',
              'external-correction-response.json', 'external-acknowledgement.json', 'external-completion.json',
              'package.external.pre_message.json')
NOT_RECORDED = 'not recorded'

# ---------------------------------------------------------------------------------------- the glossary (constant text)
# The plain meaning of each term, as the code defines it. Never generated per day.
GLOSSARY = (
    ('Dipole', 'the teacher. Its key holds 19 components, each recorded at every retained cursor of the day, and the '
               'direction relation of every pair of components.'),
    ('component', 'one of the 19 Dipole measurements (the table "What the teacher taught" gives each one\'s description as '
                  'the teacher recorded it).'),
    ('cursor', 'the recorded position of one retained row; an observation is one component at one cursor.'),
    ('observation state', 'PRESENT = a value was recorded; MISSING = no value was available; INVALID = a value was '
                          'produced but failed its validity rule; ABLATED = the input was deliberately removed.'),
    ('state counts', 'how many of a component\'s observations are in each state.'),
    ('last state', 'the state of a component at its last cursor (the code calls it terminal_state).'),
    ('direction', 'the change from a component\'s first PRESENT value to its last PRESENT value: RISE, FALL, FLAT, or '
                  'INSUFFICIENT (no PRESENT value, or the first and last PRESENT values are at the same cursor).'),
    ('pair', 'two components compared; 19 components make 171 pairs.'),
    ('direction relation', 'for a pair: SAME_DIRECTION, OPPOSITE_DIRECTION, or UNRESOLVED; in Frankie\'s notes also '
                           'HYPOTHESIS (kept as a hypothesis, not graded as a fact).'),
    ('mode', 'TEACH = the teacher shows all the evidence and Frankie gives it back; GUIDED, SOCRATIC and VERIFY withhold '
             'parts of it. Frankie\'s code answers TEACH only; any other mode is refused with its reason.'),
    ('graded correct / incorrect', 'the host compares each answer exactly with the teacher\'s record.'),
    ('mastered', 'recorded yes when every graded answer was correct.'),
    ('correction', 'one answer graded incorrect, sent back with the teacher\'s recorded message; its id names what it '
                   'covers (component:, observation:, relationship:, representation:, and external-... on the external '
                   'section).'),
    ('acknowledgement', 'Frankie\'s recorded reply to the corrections: one corrected understanding per correction id, '
                        'what he will change, and any disagreement he still holds.'),
    ('novel finding', 'a hypothesis Frankie\'s code files beyond the lesson (a pair whose first-to-last relation and its '
                      'step-by-step co-movement counts point different ways). Not scored for mastery; the teacher records '
                      'an investigation status for each.'),
    ('dropped finding', 'a finding that broke the classroom contract; not filed, listed with its recorded reason.'),
    ('teacher complete', 'recorded yes when every component, observation and pair was covered and every correction '
                         'was acknowledged with no disagreement left.'),
    ('learning measurement', 'INSTRUCTIONAL_COMPREHENSION = recorded for TEACH and GUIDED days; '
                             'INDEPENDENT_RECOGNITION_ELIGIBLE = recorded for SOCRATIC and VERIFY days.'),
    ('external section', 'the second lesson of the day: Greg\'s 13 historical data points, each value read only as it was '
                         'known at the classroom cutoff.'),
    ('series', 'one data stream of an external point (a point can have several, or none).'),
    ('known values', 'the values of a series published at or before the cutoff, each with its publication time.'),
    ('missing entry', 'a piece the day\'s data file lacks, with its recorded reason.'),
    ('deferred', 'left out of the section by Greg for now; not missing.'),
    ('brain entry', 'the folder written for the day that Frankie\'s later days read; its MANIFEST lists each file, its '
                    'bytes, and whether it is included in his later reading.'),
    ('three-way exchange', 'after the day\'s lessons: for each claim the scientific teacher tested, the BOSS teacher answers '
                           'from its own Dipole rows, the scientific teacher answers back with the search\'s counts, and '
                           'Frankie\'s code replies; all three are code, each turn labelled with its author.'),
    ('BOSS teacher', 'the teacher code: its own Dipole rows of the day, its targets, masks and controls.'),
    ('scientific teacher', 'the experiment\'s search: every claim tested with its own chance check, reported as counts per '
                           'day.'),
    ('position', 'AGREE, DISAGREE or UNRESOLVED, as each turn recorded it toward the turn before it.'),
    ('the teachers\' own finding', 'a pair both teachers measured the same way on the day (the BOSS teacher\'s step counts '
                                    'and a search row beyond chance); a hypothesis, scoped, its day named.'),
    ('resolution', 'Frankie\'s recorded reply per item: RESOLVED_HELD_ON_DAY, RESOLVED_SHOWN_OTHERWISE_ON_DAY or '
                   'KEPT_AS_HYPOTHESIS.'),
)
# Greg's 13 historical data points: the plain meaning of each point id (constant text; the recorded name is shown beside it)
POINT_GLOSSARY = (
    (1, 'CFTC Commitments of Traders, NYMEX natural gas: managed-money net position, percentile over 1 year'),
    (2, 'weather forecast: gas-weighted heating degree days from the forecast models (GFS, NAM, MEX)'),
    (3, 'CFTC Commitments of Traders, NYMEX natural gas: managed-money net position, change week over week'),
    (4, 'CFTC Commitments of Traders, NYMEX natural gas: managed-money net position, percentile over 3 years'),
    (5, 'EIA-930 grid data: US-48 wind generation'),
    (6, 'contract calendar: sessions since the front contract\'s expiry (one of the 13; it stays)'),
    (7, 'EIA-930 grid data: US-48 estimated natural gas burn for power'),
    (8, 'CFTC Commitments of Traders, ICE Henry Hub LD1: managed-money net position, percentile over 1 year'),
    (9, 'weather forecast model disagreement: the largest spread between models on gas-weighted heating degree days'),
    (10, 'observed weather: gas-weighted heating degree days and station temperatures'),
    (11, 'EIA weekly natural gas storage: level, weekly change, difference from the 5-year average'),
    (12, 'storage estimate against the EIA actual'),
    (13, 'the NYMEX natural gas futures curve: settled and traded prices across contract months'),
)
POINT_PLAIN = dict(POINT_GLOSSARY)


def glossary_lines():
    lines = ['## Glossary (fixed text)', '']
    lines += ['- %s: %s' % (term, meaning) for term, meaning in GLOSSARY]
    lines += ['', 'The 13 historical data points (point id: plain meaning):', '']
    lines += ['- %d: %s' % (pid, meaning) for pid, meaning in POINT_GLOSSARY]
    return lines + ['']


# ------------------------------------------------------------------------------------------------------------ helpers
def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def yn(value):
    return 'yes' if value is True else 'no' if value is False else NOT_RECORDED


def cell(text):
    """One line of text safe inside a Markdown table cell (the characters of the recorded text otherwise unchanged)."""
    return str(text).replace('\r', ' ').replace('\n', ' ').replace('|', '/')


def rec(value):
    """A recorded value exactly as recorded; None is 'not recorded'."""
    return NOT_RECORDED if value is None else str(value)


def listing(items):
    items = list(items or [])
    return ', '.join(str(x) for x in items) if items else 'none'


def table(header, rows):
    out = ['| ' + ' | '.join(header) + ' |', '|' + '|'.join('---' for _ in header) + '|']
    out += ['| ' + ' | '.join(cell(c) for c in row) + ' |' for row in rows]
    return out


def counts_text(counts):
    """State counts exactly as recorded, every state named: 'PRESENT 812, MISSING 3, INVALID 0, ABLATED 0'."""
    if not isinstance(counts, dict):
        return NOT_RECORDED
    return ', '.join('%s %s' % (k, v) for k, v in counts.items()) or 'none'


def ok(value):
    return 'correct' if value is True else 'incorrect' if value is False else NOT_RECORDED


def teacher_words(explanation):
    """The teacher's recorded description of a component, as it appears in the grade's explanation after 'Why: ' or
    'Why it matters: '; None when the grade carries none."""
    for marker in ('Why it matters: ', 'Why: '):
        if marker in (explanation or ''):
            return explanation.split(marker, 1)[1].strip()
    return None


def recorded_difference(explanation):
    """The recorded difference of a component graded incorrect ('Correction: <difference>. Why it matters: ...')."""
    text = explanation or ''
    if text.startswith('Correction: '):
        return text[len('Correction: '):].split('. Why it matters:', 1)[0].strip()
    return None


def ref_text(ref):
    """A finding's evidence reference, each recorded field under a fixed label."""
    kind = ref.get('kind')
    if kind == 'DIPOLE_RELATIONSHIP':
        return ('pair %s / %s; claimed relation (recorded): %s; reasoning (recorded): %s'
                % (ref.get('left'), ref.get('right'), rec(ref.get('claimed_relation')), rec(ref.get('reasoning'))))
    if kind == 'DIPOLE_OBSERVATION':
        return ('component %s at cursor %s; claimed state (recorded): %s; claimed value (recorded): %s; reasoning '
                '(recorded): %s' % (ref.get('component'), ref.get('cursor'), rec(ref.get('claimed_state')),
                                    rec(ref.get('claimed_value')), rec(ref.get('reasoning'))))
    if kind == 'OTHER_CAUSAL_EVIDENCE':
        return ('evidence pointer (recorded): %s; description (recorded): %s; reasoning (recorded): %s'
                % (rec(ref.get('evidence_pointer')), rec(ref.get('description')), rec(ref.get('reasoning'))))
    if kind == 'EXTERNAL_RELATIONSHIP':
        steps = ref.get('steps') or {}
        return 'pair %s / %s; step counts (recorded): %s' % (ref.get('left'), ref.get('right'),
                                                            listing('%s %s' % (k, v) for k, v in sorted(steps.items())))
    return 'reference of kind %s' % rec(kind)


# --------------------------------------------------------------------------------------------------------- the facts
class Day:
    """What the reports translate, read from the classroom directory (and the brain entry its receipt names)."""

    def __init__(self, day, classroom, refused_reason, exchange=None, exchange_listed=None, school=None,
                 school_listed=None, *, join_only=False):
        """join_only (late_pieces_changed): read only what the 99-layer join reads (the classroom receipt, the exchange
        and its meeting, the school file); the classroom's own output files, classroom.md and the brain MANIFEST that
        only the rendered reports use are not read."""
        self.day, self.dir = day, Path(classroom)
        self.docs, self.absent = {}, []
        self.inputs = []                        # every file this step read: kind, path, bytes, sha256 (read once, hashed once)
        self.exchange, self.exchange_sha256, self.exchange_path = None, None, exchange
        self.exchange_listed = exchange_listed
        self.meeting = dict(status='missing', record=None, path=None, receipt=None,
                            reason=exchange_listed or 'no Frankie exchange was given for this day')
        if exchange:
            raw = self._read('exchange', exchange)
            self.exchange, self.exchange_sha256 = json.loads(raw), sha256_bytes(raw)
            if str(self.exchange.get('day')) != str(day):
                raise SystemExit('the exchange %s is for day %s, not %s' % (exchange, self.exchange.get('day'), day))
            if self.exchange.get('view') == 'frankie':
                from frankie_box_brain import read_meeting_for_exchange
                self.meeting = read_meeting_for_exchange(exchange)
            else:
                frankie_path = Path(exchange).with_name('exchange-frankie.json')
                if not frankie_path.is_file():
                    self.meeting['reason'] = 'the supplied full exchange has no sibling exchange-frankie.json'
                else:
                    frankie_view = json.loads(self._read('exchange-frankie view', frankie_path))
                    if (self.exchange.get('schema') != 'FRANKIE_EXPERIMENT_EXCHANGE_V1'
                            or frankie_view.get('view') != 'frankie'
                            or not self.exchange.get('run') or not self.exchange.get('exchange_hash')
                            or any(frankie_view.get(k) != self.exchange.get(k)
                                   for k in ('schema', 'day', 'run', 'exchange_hash'))):
                        raise ValueError('the sibling Frankie view does not match this full exchange identity')
                    from frankie_box_brain import read_meeting_for_exchange
                    self.meeting = read_meeting_for_exchange(frankie_path)
        self.meeting_sha256 = ((self.meeting.get('receipt') or {}).get('record') or {}).get('sha256')
        if self.meeting.get('path'):            # read by frankie_box_brain.read_meeting_for_exchange; witnessed from its receipt
            self.inputs.append(dict(kind='meeting record', path=self.meeting['path'], bytes=None, sha256=self.meeting_sha256,
                                    read_by='frankie_box_brain.read_meeting_for_exchange (receipt-verified)'))
        self._school(school, school_listed)
        receipt_path = self.dir / 'receipt.json'
        if receipt_path.is_file():
            raw = self._read('classroom receipt', receipt_path)
            self.receipt = json.loads(raw)
            self.source = dict(kind='classroom receipt', path=str(receipt_path), sha256=sha256_bytes(raw))
            if str(self.receipt.get('day')) != str(day):
                raise SystemExit('the classroom receipt %s is for day %s, not %s' % (receipt_path, self.receipt.get('day'), day))
        elif refused_reason:
            self.receipt = dict(day=day, status='refused', reason=refused_reason,
                                listed='refused by the experiment orchestrator before the classroom wrote a receipt')
            self.source = dict(kind='orchestrator refusal', path=None,
                               sha256=sha256_bytes(('orchestrator-refusal:%s' % refused_reason).encode()))
        else:
            raise SystemExit('%s holds no receipt.json: the classroom has not run for this day (give --refused-reason '
                             'when the orchestrator refused it)' % self.dir)
        self.status = self.receipt.get('status')
        self._teacher(join_only)
        self.dropped, self.brain, self.brain_why = None, None, None
        if self.status != 'complete' or join_only:
            return                              # a refused day: the answers, grade and completion were never written
        for name in JSON_FILES:
            path = self.dir / name
            if not path.is_file():
                self.docs[name] = None
                self.absent.append((name, 'the file is not in the classroom directory'))
                continue
            try:
                self.docs[name] = json.loads(self._read(name, path))
            except ValueError as error:
                self.docs[name] = None
                self.absent.append((name, 'the file is not readable JSON (%s)' % error))
        self.dropped = self._dropped_from_markdown()
        self.brain, self.brain_why = self._brain()

    def load_pieces(self, run_dir):
        """What the pieces' own accounts read (each file read once and witnessed): the ROOT's calculations receipt,
        derive.json, the native runtime-workers receipt and pre-traversal gates, and every stage heartbeat of the day
        (<run>/days/<day>/progress/<stage>.jsonl). A file that is not there is None (its account says so)."""
        import frankie_box_piece_accounts as PA
        self.run_dir = Path(run_dir)
        calc = self.receipt.get('calculations') or (self.receipt.get('received') or {}).get('calculations')
        self.root_dir = Path(calc) if calc else self.dir.parent.parent
        self.root_sources, self.root_docs = {}, {}

        def load(role, path):
            self.root_sources[role] = str(path)
            try:
                self.root_docs[role] = json.loads(self._read('ROOT ' + role, path)) if Path(path).is_file() else None
            except (OSError, ValueError) as error:
                self.root_docs[role] = None
                self.absent.append((str(path), 'not readable (%s)' % error))
        load('receipt', self.root_dir / PA.ROOT_FIELDS['receipt'])
        load('derive', self.root_dir / PA.ROOT_FIELDS['derive'])
        for role in ('workers', 'gates'):
            name = PA.ROOT_FIELDS[role]
            found = sorted((self.root_dir / 'work').glob('*/' + name)) + sorted((self.root_dir / 'work').glob('*/*/' + name))
            load(role, found[0] if found else self.root_dir / 'work' / 'bedrock' / name)
        self.root_sha256 = next((i['sha256'] for i in reversed(self.inputs) if i['kind'] == 'ROOT receipt'), None)
        progress = self.run_dir / 'days' / str(self.day) / 'progress'
        self.beats, self.beat_paths = {}, {}
        for stage in PA.HEARTBEAT_STAGE.values():
            path = progress / ('%s.jsonl' % stage)
            self.beat_paths[stage] = str(path)
            self.beats[stage] = PA.read_heartbeats(path)

    def _teacher(self, join_only):
        """The teacher receipt beside the teacher rows the classroom receipt names (read once, witnessed): the TEACHER
        REPORT renders its account. Not read for the join-only view (the 99-layer join reads it elsewhere)."""
        self.teacher, self.teacher_sha256, self.teacher_pin, self.teacher_why = None, None, None, None
        if join_only:
            self.teacher_why = 'not read for the join-only view'
            return
        rows_dir = self.receipt.get('teacher_rows')
        if not rows_dir:
            self.teacher_why = 'the classroom receipt names no teacher rows directory'
            return
        path = Path(rows_dir) / TEACHER_RECEIPT
        try:
            raw = self._read('teacher receipt', path)
            self.teacher = json.loads(raw)
        except (OSError, ValueError) as error:
            self.teacher_why = '%s: %s (%s)' % (type(error).__name__, error, path)
            return
        self.teacher_sha256 = sha256_bytes(raw)
        self.teacher_pin = dict(path=str(path), sha256=self.teacher_sha256, bytes=len(raw))

    def _read(self, kind, path):
        """Read a file ONCE and witness it (bytes, sha256) in self.inputs; the caller parses the same bytes."""
        raw = Path(path).read_bytes()
        self.inputs.append(dict(kind=kind, path=str(path), bytes=len(raw), sha256=sha256_bytes(raw)))
        return raw

    def _school(self, school, school_listed):
        """The day's FRANKIE_SCHOOL_KNOWLEDGE_V1 file: read once, hashed once, checked against its index row (an indexed
        original) or its receipt (a retained checked successor). Status: 'read', 'not given' (a thinner picture, with the
        orchestrator's reason), 'unreadable' or 'integrity_mismatch' (visible failures, never a missing-data disposition;
        the content is not consolidated into the report)."""
        self.school, self.school_path, self.school_sha256, self.school_bytes = None, school, None, None
        self.school_status, self.school_listed, self.school_row, self.school_receipt = 'not given', None, None, None
        self.school_kind, self.school_problems = None, []
        if not school:
            self.school_listed = school_listed or 'no school file was given for this day'
            return
        path = Path(school)
        self.school_kind = 'retained checked successor' if 'successors' in path.parts else 'indexed original'
        try:
            raw = self._read('school file', path)
        except OSError as error:
            self.school_status, self.school_listed = 'unreadable', '%s: %s' % (type(error).__name__, error)
            self.school_problems.append('the school file %s could not be read: %s' % (path, self.school_listed))
            return
        self.school_sha256, self.school_bytes = sha256_bytes(raw), len(raw)
        try:
            doc = json.loads(raw)
        except ValueError as error:
            self.school_status, self.school_listed = 'unreadable', 'the school file is not readable JSON (%s)' % error
            self.school_problems.append('the school file %s is not readable JSON' % path)
            return
        if not isinstance(doc, dict) or doc.get('schema') != SCHOOL_SCHEMA or str(doc.get('day')) != str(self.day):
            self.school_status = 'integrity_mismatch'
            self.school_listed = 'the file is not a %s of day %s (schema %s, day %s)' % (
                SCHOOL_SCHEMA, self.day, (doc or {}).get('schema') if isinstance(doc, dict) else type(doc).__name__,
                (doc or {}).get('day') if isinstance(doc, dict) else None)
            self.school_problems.append('school file integrity: ' + self.school_listed)
            return
        if self.school_kind == 'indexed original':
            index_path = path.with_name('index.json')
            if index_path.is_file():
                try:
                    index = json.loads(self._read('school index', index_path))
                    rows = [r for r in (index.get('rows') or []) if str(r.get('day')) == str(self.day)] \
                        if index.get('schema') == SCHOOL_INDEX_SCHEMA else None
                except ValueError as error:
                    index, rows = None, None
                    self.school_problems.append('the school index %s is not readable JSON (%s)' % (index_path, error))
                if rows is None and index is not None:
                    self.school_problems.append('the school index %s is not a %s' % (index_path, SCHOOL_INDEX_SCHEMA))
                elif rows:
                    self.school_row = rows[-1]
                    if self.school_row.get('sha256') != self.school_sha256:
                        self.school_status = 'integrity_mismatch'
                        self.school_listed = ('the school index row records sha256 %s for day %s; the file read has %s'
                                              % (self.school_row.get('sha256'), self.day, self.school_sha256))
                        self.school_problems.append('school file integrity: ' + self.school_listed)
                        return
                else:
                    self.school_listed = 'the school index has no row for the day (the file is carried unindexed)'
            else:
                self.school_listed = 'no school index beside the file (the file is carried unindexed)'
        else:
            receipt_path = path.with_name('receipt.json')
            if receipt_path.is_file():
                try:
                    self.school_receipt = json.loads(self._read('school successor receipt', receipt_path))
                except ValueError as error:
                    self.school_problems.append('the successor receipt %s is not readable JSON (%s)' % (receipt_path, error))
            else:
                self.school_listed = 'no receipt beside the successor school file (carried unverified)'
        self.school, self.school_status = doc, 'read'

    def doc(self, name):
        return self.docs.get(name)

    def why_absent(self, name):
        return dict(self.absent).get(name, 'the file is empty')

    def _dropped_from_markdown(self):
        """The dropped findings as classroom.md lists them (id: reason); the receipt carries only their count."""
        path = self.dir / 'classroom.md'
        if not path.is_file():
            self.absent.append(('classroom.md', 'the file is not in the classroom directory (it lists the dropped '
                                                'findings\' reasons)'))
            return None
        out, inside = [], False
        for line in self._read('classroom.md', path).decode('utf-8', errors='replace').splitlines():
            if line.startswith('## '):
                inside = line.startswith('## Novel findings NOT filed')
                continue
            if inside and line.startswith('- '):
                out.append(line[2:])
        return out

    def _brain(self):
        entry = self.receipt.get('brain_entry')
        if not entry:
            return None, 'the classroom receipt names no brain entry'
        path = Path(entry) / 'MANIFEST.json'
        if path.is_file():
            try:
                raw = self._read('brain MANIFEST', path)
                return dict(path=str(entry), manifest=json.loads(raw), manifest_sha256=sha256_bytes(raw),
                            source='the entry\'s MANIFEST.json'), None
            except ValueError as error:
                return None, '%s is not readable JSON (%s)' % (path, error)
        if isinstance(self.receipt.get('brain_manifest'), dict):
            return dict(path=str(entry), manifest=self.receipt['brain_manifest'], manifest_sha256=None,
                        source='the copy in the classroom receipt (the entry\'s MANIFEST.json is not on this disk)'), None
        return None, '%s is not on this disk and the classroom receipt carries no copy' % path


def component_facts(d):
    """Per component: the teacher's recorded description, the observations taught by state, the grade."""
    grade = d.doc('post-grade.json') or {}
    audit = grade.get('exhaustive_audit') or {}
    obs = {g['name']: g for g in audit.get('observation_grades') or []}
    out = []
    for g in grade.get('component_grades') or []:
        o = obs.get(g['name']) or {}
        taught = {}
        for p in o.get('grades') or []:
            taught[p['state']] = taught.get(p['state'], 0) + 1
        out.append(dict(name=g['name'], words=teacher_words(g.get('explanation')),
                        difference=recorded_difference(g.get('explanation')),
                        counts_ok=g.get('state_counts_correct'), state_ok=g.get('state_correct'),
                        direction_ok=g.get('direction_correct'),
                        correct=bool(g.get('state_counts_correct') and g.get('state_correct') and g.get('direction_correct')),
                        taught=taught, expected=o.get('expected_count'), claimed=o.get('claimed_count'),
                        wrong_obs=[p for p in o.get('grades') or [] if not p.get('correct')],
                        extra=o.get('extra_cursors') or []))
    return out


def pair_facts(d):
    audit = (d.doc('post-grade.json') or {}).get('exhaustive_audit') or {}
    grades = audit.get('relationship_grades') or []
    recorded = {}
    for p in grades:
        recorded[p['actual']] = recorded.get(p['actual'], 0) + 1
    return grades, [p for p in grades if not p.get('correct')], recorded


def point_facts(d):
    """Per point of the external section: the receipt's counts, the recorded reasons from the pre-message, the grade."""
    ext = d.receipt.get('external') or {}
    pre = d.doc('package.external.pre_message.json') or {}
    pre_points = {p.get('point_id'): p for p in pre.get('points') or []}
    grade = d.doc('external-post-grade.json') or {}
    graded = {p.get('point_id'): p for p in grade.get('point_grades') or []}
    series_grade = {s['name']: s for s in grade.get('component_grades') or []}
    out = []
    for p in ext.get('points') or []:
        pid = p.get('point_id')
        pp = pre_points.get(pid)
        g = graded.get(pid)
        members = (pp or {}).get('series') or []
        out.append(dict(point_id=pid, name=p.get('name'), series=p.get('series'), missing=p.get('missing'),
                        missing_entries=None if pp is None else (pp.get('missing') or []),
                        correct=None if g is None else bool(g.get('correct')),
                        failing=sorted(k for k, v in (g or {}).get('checks', {}).items() if not v),
                        wrong_series=[s for s in members if s in series_grade and not series_grade[s].get('correct')]))
    return out


def external_series_facts(d):
    ledgers = (d.doc('external-code-answers.json') or {}).get('ledgers') or {}
    grade = d.doc('external-post-grade.json') or {}
    graded = {c['name']: c for c in grade.get('component_grades') or []}
    values = {v['name']: v for v in grade.get('value_grades') or []}
    out = []
    for c in (ledgers.get('external_teachback') or {}).get('components') or []:
        g = graded.get(c['name'])
        v = values.get(c['name']) or {}
        out.append(dict(name=c['name'], counts=c.get('state_counts'), terminal=c.get('terminal_state'),
                        direction=c.get('direction'), correct=None if g is None else bool(g.get('correct')),
                        failing=sorted(k for k, x in (g or {}).get('checks', {}).items() if not x),
                        values_given=v.get('claimed'), values_expected=v.get('expected'), values_ok=v.get('correct')))
    return out


def header(title, d, run, cls, other_title, other_file):
    return [title, '', 'Trade day: %s. Day class: %s. Experiment run: %s.' % (d.day, cls, run),
            'Classroom mode (recorded): %s. Classroom status (recorded): %s.' % (rec(d.receipt.get('mode')), rec(d.status)),
            'The other report for this trade day: %s (%s).' % (other_title, other_file), '']


def refused_lines(d):
    return ['## Refusal (recorded)', '', 'The classroom was refused on this day. Recorded reason: %s' % rec(d.receipt.get('reason')),
            '', 'Recorded note: %s' % rec(d.receipt.get('listed')), '',
            'Only the classroom receipt is written on a refused day, so no answers, grade, corrections, completion or '
            'brain entry are recorded for it.', '']


# ------------------------------------------------------------------------------------------------ the teacher report
# TEACHER REPORT #N (Greg, 2026-10-09: the teacher's own account of the day): rendered from the teacher receipt's
# `account` (FRANKIE_TEACHER_ACCOUNT_V1, written by frankie_box_experiment_teacher._teacher_account) in the teacher's
# first person. Every sentence carries a recorded number or a listed name of the account, and ends with the field it came
# from in brackets. Lists are rendered whole (tables), never cut to a top-N here; where the account itself records only
# part of a list, the sentence says how many it records of how many. The field names are read through ACCOUNT_FIELDS:
# a rename on the teacher side is one place here.
ACCOUNT_FIELDS = dict(
    account='account', format='format',
    read_together='read_together', rows='rows', planes='planes', clocks='clocks', clock_rows='carried_rows',
    clock_fields='fields', book_columns='book_columns', state_split='state_split',
    missing='missing_or_thin', never='planes_never_carried', partial='planes_partial',
    clock_mismatches='clock_mismatches', walk_rows='rows_read_in_walk', restored='rows_restored_from_save',
    merged='rows_merged_at_publication', book_read='book_read', reconciliation='reconciliation', guard='guard',
    wants='wants', want_list='wants', questions='questions',
    runtime='runtime', science='science', pinned='pinned_columns', book_vs_events='book_vs_events')
TEACHER_RECEIPT = 'receipt.json'


def _af(name):
    return ACCOUNT_FIELDS[name]


def _cite(*path):
    return ' [%s]' % '.'.join(str(p) for p in path)


def _flat_rows(value, prefix=''):
    """Every leaf of a nested record as (dotted field, value) rows, in order (nothing dropped)."""
    if isinstance(value, dict):
        out = []
        for key, item in value.items():
            out += _flat_rows(item, '%s.%s' % (prefix, key) if prefix else str(key))
        return out or [(prefix, '{}')]
    if isinstance(value, (list, tuple)) and value and all(isinstance(v, (dict, list, tuple)) for v in value):
        out = []
        for i, item in enumerate(value):
            out += _flat_rows(item, '%s[%d]' % (prefix, i))
        return out
    return [(prefix, json.dumps(value, sort_keys=True, default=str) if not isinstance(value, str) else value)]


def teacher_account_lines(d):
    """The teacher's own account, as headed sections in its first person."""
    teacher = getattr(d, 'teacher', None)
    if teacher is None:
        return ['The teacher receipt was not read: %s.' % rec(getattr(d, 'teacher_why', None)), '']
    account = teacher.get(_af('account'))
    if not isinstance(account, dict):
        return ['The teacher receipt carries no account (a teacher before FRANKIE_TEACHER_ACCOUNT_V1); its recorded '
                'content follows.', ''] + teacher_legacy_lines(teacher)
    A = _af('account')
    L = ['Account format (recorded): %s%s.' % (rec(account.get(_af('format'))), _cite(A, _af('format'))),
         'How it was counted (recorded): %s%s.' % (rec(account.get('basis')), _cite(A, 'basis')), '']
    # ---- what I read together
    R = account.get(_af('read_together')) or {}
    L += ['## I read these together', '']
    if R.get('status'):
        L += ['I did not read a second set on this day: %s (%s)%s.' % (rec(R.get('status')), rec(R.get('reason')),
                                                                    _cite(A, _af('read_together'))), '']
    else:
        rows = R.get(_af('rows'))
        L += ['I read %s rows together with the 99 planes on the same clocks%s.' % (rec(rows), _cite(A, _af('read_together'), _af('rows'))), '']
        planes = R.get(_af('planes')) or {}
        L += ['I read %d plane entries per row; for each, the rows I had it on, the rows I did not, and why I did not%s:' % (
            len(planes), _cite(A, _af('read_together'), _af('planes'))), '']
        L += table(['entry', 'carrier', 'rows I had it', 'rows I did not', 'why I did not (rows)'],
                   [(entry, rec(v.get('carrier')), rec(v.get('rows_present')), rec(v.get('rows_absent')),
                     listing('%s (%d)' % (why, n) for why, n in sorted((v.get('absent_reasons') or {}).items())) or 'none')
                    for entry, v in planes.items()]) + ['']
        clocks = R.get(_af('clocks')) or {}
        for clock in clocks.get(_af('clock_fields')) or []:
            L.append('- I carried the clock %s on %s of %s rows%s.' % (
                clock, rec((clocks.get(_af('clock_rows')) or {}).get(clock, 0)), rec(rows),
                _cite(A, _af('read_together'), _af('clocks'), _af('clock_rows'), clock)))
        lock = (teacher.get('teacher_second_set') or {}).get('clock_lock_time')
        lock = lock if isinstance(lock, dict) else dict(value=lock)
        L.append('- clock_lock_time is my as_of, %s, stamped once at publication (%s): lock time does not exist before '
                 'Frankie reads%s.' % (rec(lock.get('value')), rec(lock.get('basis')),
                                       _cite('teacher_second_set', 'clock_lock_time')))
        L += ['- I read these book columns beside the pinned functions: %s%s.' % (
            listing(R.get(_af('book_columns')) or []) or 'none', _cite(A, _af('read_together'), _af('book_columns')))]
        split = R.get(_af('state_split')) or {}
        L += ['- The per-state split: %s (%s)%s.' % (rec(split.get('status')), rec(split.get('reason')),
                                                     _cite(A, _af('read_together'), _af('state_split'))), '']
    # ---- what I did not see
    M = account.get(_af('missing')) or {}
    L += ['## I did not see', '']
    never = M.get(_af('never')) or []
    L += ['I did not see %d registry entries on any row; each with its recorded reason%s:' % (
        len(never), _cite(A, _af('missing'), _af('never'))), '']
    L += table(['entry', 'group', 'role', 'reason'],
               [((n.get('entry'), n.get('group'), n.get('role'), n.get('reason')) if isinstance(n, dict) else (n, '', '', ''))
                for n in never]) + ['']
    partial = M.get(_af('partial')) or {}
    L += ['I saw %d entries on some rows and not on others%s:' % (len(partial), _cite(A, _af('missing'), _af('partial'))), '']
    L += table(['entry', 'carrier', 'rows I had it', 'rows I did not', 'why I did not (rows)'],
               [(entry, rec(v.get('carrier')), rec(v.get('rows_present')), rec(v.get('rows_absent')),
                 listing('%s (%d)' % (why, n) for why, n in sorted((v.get('absent_reasons') or {}).items())) or 'none')
                for entry, v in partial.items()]) + ['']
    cm = M.get(_af('clock_mismatches')) or {}
    examples = cm.get('examples') or []
    L += ['On %s rows the picture\'s clocks or identity did not match my row%s; the account records %d of them as '
          'examples%s:' % (rec(cm.get('rows')), _cite(A, _af('missing'), _af('clock_mismatches'), 'rows'), len(examples),
                           _cite(A, _af('missing'), _af('clock_mismatches'), 'examples')), '']
    L += table(['cursor', 'field', 'the picture', 'my row'],
               [tuple(rec(x) for x in (list(e) + [None] * 4)[:4]) for e in examples]) + ['']
    L += ['I read %s rows in my own walk, restored %s from a save and merged %s at publication%s%s%s.' % (
        rec(M.get(_af('walk_rows'))), rec(M.get(_af('restored'))), rec(M.get(_af('merged'))),
        _cite(A, _af('missing'), _af('walk_rows')), _cite(A, _af('missing'), _af('restored')),
        _cite(A, _af('missing'), _af('merged'))), '']
    book = M.get(_af('book_read'))
    if book:
        L += ['How I read the book (every recorded field)%s:' % _cite(A, _af('missing'), _af('book_read')), '']
        L += table(['field', 'value'], _flat_rows(book)) + ['']
    rc = M.get(_af('reconciliation')) or {}
    L += ['Book and event counts differed %s times%s; by measure and reason%s:' % (
        rec(rc.get('differences')), _cite(A, _af('missing'), _af('reconciliation'), 'differences'),
        _cite(A, _af('missing'), _af('reconciliation'), 'by_measure_reason')), '']
    L += table(['measure:reason', 'count'], sorted((rc.get('by_measure_reason') or {}).items())) + ['']
    largest = rc.get('largest') or []
    L += ['The account records %d of the %s differences with their values%s:' % (
        len(largest), rec(rc.get('all_differences')), _cite(A, _af('missing'), _af('reconciliation'), 'largest')), '']
    L += table(['cursor', 'side', 'measure', 'book', 'events', 'reasons'],
               [(rec(x.get('cursor')), rec(x.get('side')), rec(x.get('measure')), rec(x.get('book')),
                 rec(x.get('events')), listing(x.get('reasons') or [])) for x in largest]) + ['']
    guard = M.get(_af('guard'))
    L += ['My guard (every recorded field)%s:' % _cite(A, _af('missing'), _af('guard')), '']
    L += (table(['field', 'value'], _flat_rows(guard)) if guard else ['- none recorded.']) + ['']
    # ---- what I would want
    W = account.get(_af('wants')) or {}
    wants = W.get(_af('want_list')) or []
    L += ['## I would want', '', 'I would want %d things, each from what I did not see%s:' % (
        len(wants), _cite(A, _af('wants'), _af('want_list'))), '']
    L += table(['I would want', 'because'], [(rec(w.get('want')), rec(w.get('reason'))) for w in wants]) + ['']
    questions = W.get(_af('questions')) or []
    L += ['I would ask %d questions%s:' % (len(questions), _cite(A, _af('wants'), _af('questions'))), '']
    L += table(['question', 'rows'], [(rec(q.get('question')), rec(q.get('rows'))) for q in questions]) + ['']
    if W.get('rule'):
        L += ['How the wants were derived (recorded): %s%s.' % (W['rule'], _cite(A, _af('wants'), 'rule')), '']
    # ---- what would give better outputs
    T = account.get(_af('runtime')) or {}
    L += ['## What would give better outputs', '',
          'I worked %s rows in %s seconds of walk, %s rows per second%s%s%s.' % (
              rec(T.get('rows')), rec(T.get('walk_seconds')), rec(T.get('rows_per_second')),
              _cite(A, _af('runtime'), 'rows'), _cite(A, _af('runtime'), 'walk_seconds'),
              _cite(A, _af('runtime'), 'rows_per_second')),
          'My memory peak was %s KiB%s.' % (rec(T.get('memory_peak_kib')), _cite(A, _af('runtime'), 'memory_peak_kib')), '']
    L += ['Where my time went, by phase (seconds)%s:' % _cite(A, _af('runtime'), 'phase_seconds'), '']
    L += table(['phase', 'seconds'], list((T.get('phase_seconds') or {}).items())) + ['']
    for name in ('raw_batches', 'evidence_precompute', 'saves', 'one_pass'):
        value = T.get(name)
        L += ['%s (every recorded field)%s:' % (name.replace('_', ' ').capitalize(), _cite(A, _af('runtime'), name)), '']
        L += (table(['field', 'value'], _flat_rows(value)) if value else ['- none recorded.']) + ['']
    # ---- what I found
    S = account.get(_af('science')) or {}
    L += ['## What I found', '']
    pinned = S.get(_af('pinned')) or {}
    L += ['Each of my %d pinned columns over every row: its states and the reasons recorded%s:' % (
        len(pinned), _cite(A, _af('science'), _af('pinned'))), '']
    L += table(['column', 'states (rows)', 'reasons (rows)'],
               [(name, counts_text(v.get('states') or {}), listing('%s (%d)' % (r, n) for r, n in (v.get('reasons') or {}).items()) or 'none')
                for name, v in pinned.items()]) + ['']
    sides = S.get(_af('book_vs_events')) or {}
    for side, v in sides.items():
        measures = sorted(set(v.get('book') or {}) | set(v.get('events') or {}))
        L += ['Side %s: what the book shows against what the events show, per measure%s:' % (
            side, _cite(A, _af('science'), _af('book_vs_events'), side)), '']
        L += table(['measure', 'book', 'events'], [(m, rec((v.get('book') or {}).get(m)), rec((v.get('events') or {}).get(m)))
                                                   for m in measures]) + ['']
    split = S.get(_af('state_split')) or {}
    if split:
        L += ['The per-state split of my sums: %s%s.' % (rec(split.get('status')), _cite(A, _af('science'), _af('state_split'))), '']
    return L


def teacher_legacy_lines(teacher):
    """An older teacher receipt (no account): its recorded top-level counts and records, every field as recorded."""
    keep = ('status', 'day', 'rows', 'processed', 'entity_rows', 'as_of', 'through_cursor', 'walk_seconds', 'seconds',
            'teacher_second_set', 'rows_sidecar', 'equation_not_run')
    rows = []
    for key in keep:
        if key in teacher:
            rows += _flat_rows(teacher[key], key)
    return table(['field (teacher receipt)', 'value'], rows) + ['']


def both_teachers_second_set_lines(d):
    """What each teacher read of the teacher's second set (Greg, 2026-10-09: BOTH teachers get it), one sentence each
    from its own recorded reading (frankie_box_teacher_rows.reading_sentence): the BOSS teacher's knowledge step (the
    reading beside the rows), the exchange's two teacher seats (the exchange's teacher_second_set_read) and the
    scientific teacher's lessons (its reading of the day under the lessons root, or the accumulated reader's)."""
    import frankie_box_teacher_rows as TR
    L = ['## The second set each teacher read', '']

    def kept(kind, path):
        if not Path(path).is_file():
            return None, 'not written at %s' % path
        doc, _, why = _json_once(d, kind, path)
        return doc, why
    rows_dir = d.receipt.get('teacher_rows') if isinstance(d.receipt, dict) else None
    if rows_dir:
        path = Path(rows_dir) / TR.READING_FILES['boss_teacher']
        doc, why = kept('BOSS teacher second-set reading', path)
        L.append('- The BOSS teacher (its knowledge step, beside its pinned key; filed as the brain entry %s-teacher-'
                 'second-set): %s [%s].' % (d.day, TR.reading_sentence(doc) if doc else 'not recorded (%s)' % why, path))
    else:
        L.append('- The BOSS teacher: not recorded (the classroom receipt names no teacher rows).')
    x = getattr(d, 'exchange', None)
    if isinstance(x, dict) and isinstance(x.get('teacher_second_set_read'), dict):
        ref = x['teacher_second_set_read']
        L.append('- Both teacher seats of the three-way exchange (the BOSS teacher\'s turn and the scientific teacher\'s '
                 'turn each carry it, and each seat\'s voice says it to the meeting): %s [%s].' % (
                     TR.reading_sentence(ref), (ref.get('reading') or {}).get('path')))
    else:
        L.append('- The teacher seats of the three-way exchange: not recorded (%s).' % (
            'no exchange was given for this day' if not isinstance(x, dict) else
            'this exchange carries no teacher_second_set_read (an exchange before it)'))
    run_dir = getattr(d, 'run_dir', None)
    found = None
    for path in [LESSONS_ROOT / 'teacher-second-set' / ('%s.json' % d.day)] + (
            [Path(run_dir) / 'scientific-knowledge' / str(d.day) / 'teacher-second-set-read.json'] if run_dir else []):
        if Path(path).is_file():
            found = path
            break
    if found is not None:
        doc, why = kept('scientific teacher second-set reading', found)
        L.append('- The scientific teacher (its lessons call, beside its claim tests): %s [%s].' % (
            TR.reading_sentence(doc) if doc else 'not readable (%s)' % why, found))
    else:
        L.append('- The scientific teacher (its lessons call): not recorded yet for this day (no reading under %s).'
                 % (LESSONS_ROOT / 'teacher-second-set'))
    return L + ['']


def teacher_report(d, number, revision, run, cls, files):
    title = '# TEACHER REPORT #%d%s' % (number, '' if revision == 1 else ' (revision %d)' % revision)
    L = header(title, d, run, cls, 'CLASSROOM REPORT #%d' % number, files['classroom'])
    L += ['The teacher\'s own account of the day, in its words: every sentence is a recorded number or a listed name of '
          'the teacher receipt\'s account, and the field it came from is given in brackets.', '']
    L += teacher_account_lines(d)
    try:
        L += both_teachers_second_set_lines(d)
    except Exception as error:  # noqa: BLE001 - the report states it; the other sections stand
        L += ['## The second set each teacher read', '', '- Not rendered: %s: %s.' % (type(error).__name__, error), '']
    import frankie_box_teacher_findings as TF
    teacher = getattr(d, 'teacher', None)
    rows_dir = Path(d.receipt.get('teacher_rows')) if d.receipt.get('teacher_rows') else None
    if rows_dir is not None and teacher is not None:
        try:
            findings = TF.load_or_compute(rows_dir)
            pairs, pairs_why = TF.correlations(rows_dir)
            L += TF.finding_lines(findings, pairs, pairs_why, teacher.get('account'), teacher,
                                  str(rows_dir / TF.FINDINGS_FILE), (getattr(d, 'teacher_pin', None) or {}).get('path')
                                  or 'teacher receipt.json')
        except Exception as error:  # noqa: BLE001 - the report states it; the other sections stand
            L += ['## What I found: discovery and correlations', '',
                  '- Not rendered: %s: %s.' % (type(error).__name__, error), '']
    else:
        L += ['## What I found: discovery and correlations', '', '- Not recorded by my step: %s.' % (
            'the classroom receipt names no teacher rows' if rows_dir is None else getattr(d, 'teacher_why', None)), '']
    import frankie_box_piece_accounts as PA
    acc = PA.Account()
    source = (getattr(d, 'teacher_pin', None) or {}).get('path') or 'teacher receipt.json'
    PA.teacher_actions(acc, getattr(d, 'teacher', None), source, getattr(d, 'beats', {}).get('teacher'),
                       getattr(d, 'beat_paths', {}).get('teacher', 'progress/teacher.jsonl'))
    L += acc.lines()
    teacher_pin = getattr(d, 'teacher_pin', None)
    L += ['## Evidence', '', '- The teacher receipt: %s.' % (
        '%s (sha256 %s, %s bytes)' % (teacher_pin['path'], teacher_pin['sha256'], teacher_pin['bytes'])
        if teacher_pin else 'not read (%s)' % rec(getattr(d, 'teacher_why', None))), '']
    return L


def root_report(d, number, revision, run, cls, files):
    import frankie_box_piece_accounts as PA
    title = '# ROOT REPORT #%d%s' % (number, '' if revision == 1 else ' (revision %d)' % revision)
    L = header(title, d, run, cls, 'CLASSROOM REPORT #%d' % number, files['classroom'])
    docs, sources = getattr(d, 'root_docs', {}), dict(getattr(d, 'root_sources', {}))
    sources['heartbeat'] = getattr(d, 'beat_paths', {}).get('root', 'progress/root.jsonl')
    L += ['The ROOT\'s own account of the day: every sentence is a recorded fact of its receipts, derive.json and '
          'heartbeats, with the field it came from in brackets.', '']
    acc = PA.root_account(docs.get('receipt'), docs.get('derive'), docs.get('workers'), docs.get('gates'),
                          getattr(d, 'beats', {}).get('root'), sources)
    L += acc.lines()
    L += PA.root_found(docs.get('receipt'), docs.get('derive'), sources)
    L += ['## Evidence', ''] + ['- %s: %s' % (role, path) for role, path in sorted(sources.items())] + ['']
    return L


def second_set_received_lines(d):
    """The classroom report's view of the teacher's second set it received (the classroom receipt's second_set)."""
    second = d.receipt.get('second_set') or (d.receipt.get('received') or {}).get('second_set')
    L = ['## The teacher\'s second set received', '']
    if not isinstance(second, dict):
        return L + ['Not recorded: the classroom receipt carries no second_set (a classroom before it).', '']
    if second.get('status') != 'carried':
        return L + ['Second set status (recorded): %s. Reason (recorded): %s.' % (rec(second.get('status')),
                                                                                  rec(second.get('reason'))), '']
    rows = second.get('rows')
    L += ['Rows received with the second set (recorded): %s; classroom rows: %s; rows aligned on cursor and target '
          'hash: %s; rows that differ: %s.' % (rec(rows), rec(second.get('classroom_rows')),
                                               rec((second.get('alignment') or {}).get('matched')),
                                               len((second.get('alignment') or {}).get('differs') or [])), '']
    L += table(['part of the second set', 'rows carrying it', 'rows without it'],
               [(role, rec(n), rec(((second.get('absent') or {}).get(role) or {}).get('rows', 0)))
                for role, n in (second.get('carried') or {}).items()]) + ['']
    L += ['Picture identity per row (recorded): %s. Key cursor different from the row cursor: %d rows.' % (
        counts_text(second.get('match_status') or {}), len(second.get('key_cursor_differs') or [])), '']
    clocks = second.get('clocks') or {}
    L += table(['clock', 'rows carrying it', 'absent: reason (rows)'],
               [(c, rec(n), listing('%s (%d)' % (r, k) for r, k in ((clocks.get('absent_reasons') or {}).get(c) or {}).items()) or 'none')
                for c, n in (clocks.get('carried_rows') or {}).items()]) + ['']
    lock = second.get('clock_lock_time') or {}
    L += ['clock_lock_time (recorded): %s, the teacher\'s as_of (lock time does not exist before Frankie reads).' %
          rec(lock.get('value')), '']
    planes = second.get('planes') or {}
    L += ['Plane entries received: %d; per entry the rows with plane references, the references, the rows carried by '
          'the row itself, and the rows without it with their reasons:' % len(planes), '']
    L += table(['entry', 'rows with references', 'references', 'rows (element)', 'rows without', 'reasons (rows)'],
               [(e, rec(v.get('rows_with_references')), rec(v.get('references')), rec(v.get('rows_element')),
                 rec(v.get('rows_absent')), listing('%s (%d)' % (r, k) for r, k in (v.get('absent_reasons') or {}).items()) or 'none')
                for e, v in planes.items()]) + ['']
    resolver = ((second.get('anchors_resolved') or {}).get('resolver') or {})
    L += ['Anchor rows whose planes were read by their references: %s.' % rec(resolver.get('note')), '']
    return L


# ------------------------------------------------------------------------------------------------ the classroom report
def classroom_counts(d, comps, wrong_pairs, pairs, points):
    """The opening summary: recorded counts in fixed sentences."""
    audit = (d.doc('post-grade.json') or {}).get('exhaustive_audit') or {}
    ext = d.receipt.get('external') or {}
    ack = d.doc('acknowledgement.json') or {}
    wrong_obs = sum(len(c['wrong_obs']) for c in comps)
    return ['## Summary (recorded counts)', '',
            '- Components taught: %s. Observations taught: %s. Pairs taught: %s.' % (
                rec(d.receipt.get('components')), rec(d.receipt.get('observations')), rec(d.receipt.get('pairs'))),
            '- Components graded correct: %d. Components graded incorrect: %d.' % (
                sum(1 for c in comps if c['correct']), sum(1 for c in comps if not c['correct'])),
            '- Observations graded correct: %s of %s. Pair directions graded correct: %d of %d.' % (
                (audit.get('observation_claims_expected') or 0) - wrong_obs if audit else NOT_RECORDED,
                rec(audit.get('observation_claims_expected')), len(pairs) - len(wrong_pairs), len(pairs)),
            '- Mastered (recorded): %s.' % yn((d.doc('post-grade.json') or {}).get('mastered')),
            '- Corrections sent: %s. Corrections resolved in the acknowledgement: %d. Disagreements still held: %d.' % (
                rec(d.receipt.get('correction_ids')), len(ack.get('resolved_correction_ids') or []),
                len(ack.get('remaining_disagreements') or [])),
            '- Novel findings filed: %s. Findings dropped: %s.' % (rec(d.receipt.get('novel_findings')),
                                                                   rec(d.receipt.get('dropped_findings'))),
            '- Teacher complete (recorded): %s.' % yn(d.receipt.get('teacher_complete')),
            '- External section: points in the section: %d. Points graded correct: %d. Points graded incorrect: %d. '
            'External corrections sent: %s. External mastered (recorded): %s. External teacher complete (recorded): %s.' % (
                len(points), sum(1 for p in points if p['correct'] is True), sum(1 for p in points if p['correct'] is False),
                rec(ext.get('correction_ids')), yn(ext.get('mastered')), yn(ext.get('teacher_complete'))), '']


def classroom_report(d, number, revision, run, cls, frankie_file):
    title = '# CLASSROOM REPORT #%d%s' % (number, '' if revision == 1 else ' (revision %d)' % revision)
    L = header(title, d, run, cls, 'FRANKIE REPORT #%d' % number, frankie_file)
    import frankie_box_piece_accounts as PA
    piece = PA.classroom_account(d.receipt, str(d.dir / 'receipt.json'), getattr(d, 'beats', {}).get('classroom'),
                                 getattr(d, 'beat_paths', {}).get('classroom', 'progress/classroom.jsonl')).lines()
    if d.status != 'complete':
        return L + refused_lines(d) + piece + exchange_lines(d, False) + glossary_lines() + evidence(d)
    L += piece
    comps = component_facts(d)
    pairs, wrong_pairs, recorded = pair_facts(d)
    points = point_facts(d)
    L += classroom_counts(d, comps, wrong_pairs, pairs, points)

    L += ['## What the teacher taught', '']
    if not comps:
        L += ['Not recorded: post-grade.json (%s).' % d.why_absent('post-grade.json'), '']
    else:
        L += table(['component', 'the teacher\'s recorded description', 'observations taught, by state'],
                   [(c['name'], c['words'] or NOT_RECORDED, counts_text(c['taught'])) for c in comps]) + ['']
    L += ['Pair direction relations recorded by the teacher: %s.' % listing(
        '%s %d' % (k, v) for k, v in sorted(recorded.items())), '']
    carried = d.receipt.get('carried_from_previous')
    if isinstance(carried, dict) and carried.get('directory'):
        L += ['Carried in from the previous classroom day (recorded): directory %s; history entries: %s; that day\'s '
              'grade file.' % (carried['directory'], rec(carried.get('history_entries'))), '']
    else:
        L += ['Carried in from the previous classroom day (recorded): none.', '']
    L += second_set_received_lines(d)

    grade = d.doc('post-grade.json')
    L += ['## The grade', '']
    if grade is None:
        L += ['Not recorded: post-grade.json (%s).' % d.why_absent('post-grade.json'), '']
    else:
        audit = grade.get('exhaustive_audit') or {}
        L += ['Mastered (recorded): %s. All component facts correct (recorded): %s. All observations correct (recorded): '
              '%s. All pair directions correct (recorded): %s.' % (
                  yn(grade.get('mastered')), yn(grade.get('factual_components_correct')),
                  yn(audit.get('all_observations_correct')), yn(audit.get('all_relationship_directions_correct'))), '']
        L += table(['component', 'state counts', 'last state', 'direction', 'observations graded correct', 'component'],
                   [(c['name'], ok(c['counts_ok']), ok(c['state_ok']), ok(c['direction_ok']),
                     '%s of %s' % ((c['expected'] or 0) - len(c['wrong_obs']), rec(c['expected'])),
                     ok(c['correct'])) for c in comps]) + ['']
        for c in comps:
            if not c['correct']:
                L.append('- Component %s was graded incorrect. The recorded difference: %s.' % (
                    c['name'], rec(c['difference'])))
            for p in c['wrong_obs']:
                L.append('- The observation of %s at cursor %s was graded incorrect. The recorded explanation: %s' % (
                    c['name'], p.get('cursor'), rec(p.get('explanation'))))
            if c['extra']:
                L.append('- Frankie\'s answer for %s listed cursors that are not in the teacher\'s record: %s.' % (
                    c['name'], listing(c['extra'])))
        L += ['', 'Pair directions graded incorrect: %d.' % len(wrong_pairs), '']
        if wrong_pairs:
            L += table(['pair', 'Frankie\'s answer', 'the teacher\'s recorded relation'],
                       [('%s / %s' % (p['left'], p['right']), p['claimed'], p['actual']) for p in wrong_pairs]) + ['']
        cross = (grade.get('relationship_view_crosscheck') or {}).get('inconsistencies') or []
        L += ['Pairs where Frankie\'s component notes and his pair list disagree (recorded): %d.' % len(cross), '']
        L += ['- Pair %s / %s: the component notes say %s; the pair list says %s.' % (
            x['left'], x['right'], x['component_view'], x['exhaustive_scan_view']) for x in cross]
        if cross:
            L.append('')

    L += ['## Corrections', '']
    correction = d.doc('correction-request.json')
    if correction is None:
        L += ['Not recorded: correction-request.json (%s).' % d.why_absent('correction-request.json'), '']
    else:
        items = correction.get('data_review_items') or []
        L += ['Corrections sent by the teacher: %d.' % len(correction.get('correction_ids') or []), '']
        L += ['- Correction %s. The teacher\'s recorded message: %s' % (i.get('correction_id'), rec(i.get('message')))
              for i in items]
        if items:
            L.append('')
    L += ['## Acknowledgement', '']
    ack = d.doc('acknowledgement.json')
    if ack is None:
        L += ['Not recorded: acknowledgement.json (%s).' % d.why_absent('acknowledgement.json'), '']
    else:
        L += ['Acknowledged (recorded): %s. Correction ids resolved: %d. Disagreements still held: %d.' % (
            yn(ack.get('acknowledged')), len(ack.get('resolved_correction_ids') or []),
            len(ack.get('remaining_disagreements') or [])), '',
              'What Frankie will change, as recorded: %s' % rec(ack.get('what_i_will_change')), '']
        L += ['- Disagreement still held, as recorded: %s' % x for x in ack.get('remaining_disagreements') or []]
        if ack.get('remaining_disagreements'):
            L.append('')

    L += ['## Novel findings', ''] + novel_lines(d)
    L += ['## Dropped findings', '', 'Findings dropped (recorded count): %s.' % rec(d.receipt.get('dropped_findings')), '']
    if d.receipt.get('dropped_findings'):
        if d.dropped is None:
            L += ['The dropped findings\' reasons: not recorded here (%s).' % d.why_absent('classroom.md'), '']
        else:
            L += ['- Dropped finding, as listed in classroom.md: %s' % x for x in d.dropped] + ['']

    completion = d.doc('completion.json')
    L += ['## Teacher completion', '']
    if completion is None:
        L += ['Not recorded: completion.json (%s).' % d.why_absent('completion.json'), '']
    else:
        L += ['Teacher complete (recorded): %s. Mastered (recorded in the completion): %s. Learning measurement '
              '(recorded): %s. Unresolved disagreements (recorded in the completion audit): %s.' % (
                  yn(completion.get('teacher_complete')), yn(completion.get('mastered')),
                  rec(completion.get('learning_measurement')),
                  rec((completion.get('audit') or {}).get('unresolved_disagreements'))), '']
    L += external_classroom_lines(d, points)
    L += exchange_lines(d, False)
    return L + glossary_lines() + evidence(d)


def novel_lines(d):
    findings = d.doc('novel-findings.json')
    if findings is None:
        return ['Not recorded: novel-findings.json (%s).' % d.why_absent('novel-findings.json'), '']
    investigation = {f.get('finding_id'): f for f in (d.doc('novelty-investigation.json') or {}).get('findings') or []}
    out = ['Novel findings filed: %d.' % len(findings), '']
    for i, f in enumerate(findings, 1):
        inv = investigation.get(f.get('finding_id'))
        out += ['%d. Novel finding %s.' % (i, f.get('finding_id')),
                '   - Premise, as recorded: %s' % rec(f.get('premise')),
                '   - Why novel, as recorded: %s' % rec(f.get('why_novel'))]
        out += ['   - Evidence cited: %s' % ref_text(r) for r in f.get('evidence_refs') or []]
        if inv is None:
            out.append('   - The teacher\'s investigation: not recorded (novelty-investigation.json holds no entry for it).')
        else:
            out += ['   - The teacher\'s investigation status (recorded): %s. Cited details that differ from the data: %d. '
                    'Cited details not yet testable: %d.' % (rec(inv.get('status')),
                                                            len(inv.get('specific_data_differences') or []),
                                                            len(inv.get('not_yet_testable') or [])),
                    '   - The teacher\'s recorded response: %s' % rec(inv.get('teacher_response'))]
    return out + ['']


def external_classroom_lines(d, points):
    ext = d.receipt.get('external') or {}
    grade = d.doc('external-post-grade.json')
    L = ['## The external section: Greg\'s 13 historical data points', '',
         'Series in the section (recorded): %s. Dipole rows (recorded): %s. Points in the section: %d.' % (
             rec(ext.get('series')), rec(ext.get('rows')), len(points)), '']
    L += table(['point id', 'recorded name', 'series', 'missing entries', 'point graded', 'series graded incorrect'],
               [(p['point_id'], p['name'], rec(p['series']), rec(p['missing']), ok(p['correct']),
                 listing(p['wrong_series'])) for p in points]) + ['']
    for p in points:
        if p['correct'] is False:
            L.append('- Point %s was graded incorrect. Checks recorded as incorrect: %s.' % (p['point_id'],
                                                                                           listing(p['failing'])))
    if any(p['correct'] is False for p in points):
        L.append('')
    L += ['Missing entries and their recorded reasons:', '']
    lines = []
    for p in points:
        if p['missing_entries'] is None:
            lines.append('- Point %s: %s missing entries; their reasons are not recorded here (%s).' % (
                p['point_id'], rec(p['missing']), d.why_absent('package.external.pre_message.json')))
        for m in p['missing_entries'] or []:
            lines.append('- Point %s, entry %s, day %s. Recorded reason: %s' % (p['point_id'], rec(m.get('point')),
                                                                                rec(m.get('day')), rec(m.get('reason'))))
    L += (lines or ['- none recorded']) + ['']
    absent = ext.get('series_absent') or []
    L += ['Series absent from the day file (recorded): %d.' % len(absent), '']
    L += ['- Series %s (table %s). Recorded reason: %s' % (rec(a.get('series')), rec(a.get('table')), rec(a.get('reason')))
          for a in absent]
    unassigned = ext.get('missing_not_assigned') or []
    L += (([''] if absent else []) + ['Missing entries not assigned to a point (recorded): %d.' % len(unassigned), ''])
    L += ['- Entry %s, day %s. Recorded reason: %s' % (rec(m.get('point')), rec(m.get('day')), rec(m.get('reason')))
          for m in unassigned]
    deferred = ext.get('deferred') or {}
    dropped = [q for q in deferred.get('dropped') or [] if isinstance(q, dict)]
    old_points = [q for q in deferred.get('points') or [] if isinstance(q, dict)]   # an older key's deferral, as recorded
    lines = []
    if dropped:
        lines.append('Dropped by Greg (not one of the 13): %s.' % listing(
            '%s (%s)' % (q.get('name'), q.get('reason')) if q.get('reason') else str(q.get('name')) for q in dropped))
    if old_points:
        lines.append('Deferred by an older key (recorded reason: %s): %s.' % (
            rec(deferred.get('reason')), listing('%s (%s)' % (rec(q.get('point_id')), q.get('name')) for q in old_points)))
    if lines:
        L += ([''] if unassigned else []) + lines + ['']
    if grade is None:
        L += ['The external grade: not recorded (external-post-grade.json: %s).' % d.why_absent('external-post-grade.json'), '']
    else:
        comps = grade.get('component_grades') or []
        values = grade.get('value_grades') or []
        rels = grade.get('relationship_grades') or []
        kinds = {}
        for r in rels:
            k = kinds.setdefault(r.get('kind'), [0, 0])
            k[0 if r.get('correct') else 1] += 1
        L += ['External series graded correct: %d of %d. Series whose known values were graded correct: %d of %d. Known '
              'values checked (recorded): %s. External pair directions graded correct: %d of %d (%s). External mastered '
              '(recorded): %s.' % (
                  sum(1 for c in comps if c.get('correct')), len(comps), sum(1 for v in values if v.get('correct')),
                  len(values), rec(grade.get('values_checked')), sum(1 for r in rels if r.get('correct')), len(rels),
                  listing('%s: %d correct, %d incorrect' % (k, v[0], v[1]) for k, v in sorted(kinds.items(), key=lambda kv: str(kv[0]))),
                  yn(grade.get('mastered'))), '']
        for c in comps:
            if not c.get('correct'):
                L.append('- External series %s was graded incorrect. Checks recorded as incorrect: %s.' % (
                    c['name'], listing(sorted(k for k, v in (c.get('checks') or {}).items() if not v))))
        for v in values:
            if not v.get('correct'):
                L.append('- The known values of external series %s were graded incorrect: %s given, %s recorded.' % (
                    v['name'], rec(v.get('claimed')), rec(v.get('expected'))))
        wrong_rels = [r for r in rels if not r.get('correct')]
        if wrong_rels:
            L += [''] + table(['external pair', 'Frankie\'s answer', 'the recorded relation'],
                              [('%s / %s' % (r['left'], r['right']), r['claimed'], r['actual']) for r in wrong_rels])
        L.append('')
    correction = d.doc('external-correction-request.json')
    if correction is None:
        L += ['External corrections: not recorded (external-correction-request.json: %s).' % d.why_absent(
            'external-correction-request.json'), '']
    else:
        items = correction.get('data_review_items') or []
        L += ['External corrections sent: %d.' % len(correction.get('correction_ids') or []), '']
        L += ['- External correction %s. The teacher\'s recorded message: %s' % (i.get('correction_id'), rec(i.get('message')))
              for i in items]
        if items:
            L.append('')
    ack = d.doc('external-acknowledgement.json')
    if ack is None:
        L += ['External acknowledgement: not recorded (external-acknowledgement.json: %s).' % d.why_absent(
            'external-acknowledgement.json'), '']
    else:
        L += ['External acknowledgement (recorded): %s. Correction ids resolved: %d. Disagreements still held: %d.' % (
            yn(ack.get('acknowledged')), len(ack.get('resolved_correction_ids') or []),
            len(ack.get('remaining_disagreements') or [])), '']
    carried = ext.get('carried_from_previous')
    if isinstance(carried, dict) and carried.get('history_entries') is not None:
        carried_text = 'directory %s; history entries: %s' % (carried.get('directory'), carried['history_entries'])
    elif isinstance(carried, dict) and carried.get('listed'):
        carried_text = carried['listed']
    else:
        carried_text = 'none'
    L += ['External teacher complete (recorded): %s. Carried in from the previous day (recorded): %s.' % (
        yn(ext.get('teacher_complete')), carried_text), '']
    return L


# -------------------------------------------------------------------------------------------------- the Frankie report
def frankie_counts(d, comps, wrong_pairs, pairs, ext_series, ext_points):
    code = d.doc('code-answers.json') or {}
    response = (d.doc('correction-response.json') or {}).get('dipole_acknowledgement') or {}
    ext_findings = ((d.doc('external-code-answers.json') or {}).get('ledgers') or {}).get('external_novel_findings') or []
    return ['## Summary (recorded counts)', '',
            '- Frankie\'s answers were computed by (recorded): %s. Model calls (recorded): %s.' % (
                rec((d.receipt.get('stand_ins') or {}).get('model_identity')), rec(code.get('model_calls'))),
            '- Components answered: %d. Graded correct: %d. Graded incorrect: %d.' % (
                len(comps), sum(1 for c in comps if c['correct']), sum(1 for c in comps if not c['correct'])),
            '- Observations graded incorrect: %d. Pair directions graded correct: %d of %d.' % (
                sum(len(c['wrong_obs']) for c in comps), len(pairs) - len(wrong_pairs), len(pairs)),
            '- Mastered (recorded): %s.' % yn((d.doc('post-grade.json') or {}).get('mastered')),
            '- Corrections received: %s. Corrections resolved in his reply: %d. Disagreements he still holds: %d.' % (
                rec(d.receipt.get('correction_ids')), len(response.get('correction_resolutions') or []),
                len(response.get('remaining_disagreements') or [])),
            '- External series answered: %d. Graded correct: %d. Graded incorrect: %d.' % (
                len(ext_series), sum(1 for s in ext_series if s['correct'] is True),
                sum(1 for s in ext_series if s['correct'] is False)),
            '- External points answered: %d. Graded correct: %d. Graded incorrect: %d.' % (
                len(ext_points), sum(1 for p in ext_points if p['correct'] is True),
                sum(1 for p in ext_points if p['correct'] is False)),
            '- Novel findings filed on the lesson: %d. Hypotheses filed on the external section: %d.' % (
                len(d.doc('novel-findings.json') or []), len(ext_findings)),
            '- Brain entry written (recorded): %s.' % ('yes' if d.brain else 'not recorded (%s)' % d.brain_why), '']


def frankie_report(d, number, revision, run, cls, classroom_file):
    title = '# FRANKIE REPORT #%d%s' % (number, '' if revision == 1 else ' (revision %d)' % revision)
    L = header(title, d, run, cls, 'CLASSROOM REPORT #%d' % number, classroom_file)
    if d.status != 'complete':
        return (L + refused_lines(d) + all99_lines(d) + school_lines(d, number) + exchange_lines(d, True) + glossary_lines()
                + evidence(d, True))
    comps = component_facts(d)
    pairs, wrong_pairs, _ = pair_facts(d)
    ext_series = external_series_facts(d)
    ext_points = point_facts(d)
    L += frankie_counts(d, comps, wrong_pairs, pairs, ext_series, ext_points)
    L += all99_lines(d)
    code = d.doc('code-answers.json') or {}
    rules = code.get('rules') or {}
    L += ['## The rules his code answered under', '',
          'Classroom rules file (recorded): %s. Rule ids (recorded): %s.' % (
              Path(rules['path']).name if rules.get('path') else NOT_RECORDED, listing(rules.get('rules'))), '']

    ledgers = d.doc('ledgers.json') or {}
    teachback = ledgers.get('dipole_teachback') or {}
    his = {c['name']: c for c in teachback.get('components') or []}
    review = {c['name']: c for c in ledgers.get('dipole_observation_review') or []}
    L += ['## His answers per component', '']
    if not his:
        L += ['Not recorded: ledgers.json (%s).' % d.why_absent('ledgers.json'), '']
    else:
        L += table(['component', 'his state counts', 'his last state', 'his direction', 'observations he listed',
                    'graded'],
                   [(c['name'], counts_text((his.get(c['name']) or {}).get('state_counts')),
                     rec((his.get(c['name']) or {}).get('terminal_state')), rec((his.get(c['name']) or {}).get('direction')),
                     len((review.get(c['name']) or {}).get('observations') or []), ok(c['correct'])) for c in comps]) + ['']
        for c in comps:
            if not c['correct']:
                L.append('- Frankie\'s answer for component %s was graded incorrect. The recorded difference: %s.' % (
                    c['name'], rec(c['difference'])))
            for p in c['wrong_obs']:
                L.append('- Frankie\'s answer for %s at cursor %s was graded incorrect. The recorded explanation: %s' % (
                    c['name'], p.get('cursor'), rec(p.get('explanation'))))
        relations = {}
        for p in ledgers.get('dipole_relationship_scan') or []:
            relations[p['direction_relation']] = relations.get(p['direction_relation'], 0) + 1
        L += ['', 'His pair direction relations (recorded counts): %s.' % listing(
            '%s %d' % (k, v) for k, v in sorted(relations.items())), '']
        for p in wrong_pairs:
            L.append('- Frankie\'s answer for pair %s / %s was graded incorrect. His answer: %s. The recorded relation: %s.'
                     % (p['left'], p['right'], p['claimed'], p['actual']))
        if wrong_pairs:
            L.append('')
        L += ['His recorded cycle summary: %s' % rec(teachback.get('cycle_summary')), '',
              'His recorded correlation review: %s' % rec(teachback.get('correlation_review')), '']
        questions = teachback.get('unresolved_questions') or []
        L += ['Unresolved questions he recorded: %d.' % len(questions), '']
        L += ['- %s' % q for q in questions]
        if questions:
            L.append('')

    response = (d.doc('correction-response.json') or {}).get('dipole_acknowledgement')
    L += ['## His answers to the corrections', '']
    if not response:
        L += ['Not recorded: correction-response.json (%s).' % d.why_absent('correction-response.json'), '']
    else:
        resolutions = response.get('correction_resolutions') or []
        L += ['Acknowledged (recorded): %s. Corrected understandings recorded: %d. Disagreements still held: %d.' % (
            yn(response.get('acknowledged')), len(resolutions), len(response.get('remaining_disagreements') or [])), '',
              'What he will change, as recorded: %s' % rec(response.get('what_i_will_change')), '']
        L += ['- Correction %s. His recorded corrected understanding: %s' % (r.get('correction_id'),
                                                                            rec(r.get('corrected_understanding')))
              for r in resolutions]
        L += ['- Disagreement still held, as recorded: %s' % x for x in response.get('remaining_disagreements') or []]
        if resolutions or response.get('remaining_disagreements'):
            L.append('')
    L += ['The teacher\'s validated acknowledgement (acknowledgement.json): %s.' % (
        'recorded' if d.doc('acknowledgement.json') is not None else
        'not recorded (%s)' % d.why_absent('acknowledgement.json')), '']

    L += ['## His external answers (Greg\'s 13 historical data points)', '']
    if not ext_series:
        L += ['Not recorded: external-code-answers.json (%s).' % d.why_absent('external-code-answers.json'), '']
    else:
        L += table(['series', 'his state counts', 'his last state', 'his direction', 'known values he gave / recorded',
                    'series facts', 'known values'],
                   [(s['name'], counts_text(s['counts']), rec(s['terminal']), rec(s['direction']),
                     '%s / %s' % (rec(s['values_given']), rec(s['values_expected'])), ok(s['correct']), ok(s['values_ok']))
                    for s in ext_series]) + ['']
        for s in ext_series:
            if s['correct'] is False:
                L.append('- Frankie\'s answer for external series %s was graded incorrect. Checks recorded as incorrect: '
                         '%s.' % (s['name'], listing(s['failing'])))
        point_review = {p['point_id']: p for p in (((d.doc('external-code-answers.json') or {}).get('ledgers') or {}).get(
            'external_teachback') or {}).get('point_review') or []}
        L += ([''] if any(s['correct'] is False for s in ext_series) else [])
        L += table(['point id', 'recorded name', 'series he named', 'tables he named', 'missing entries he counted',
                    'graded'],
                   [(p['point_id'], p['name'], len((point_review.get(p['point_id']) or {}).get('series') or []),
                     len((point_review.get(p['point_id']) or {}).get('tables') or []),
                     rec((point_review.get(p['point_id']) or {}).get('missing_count')), ok(p['correct']))
                    for p in ext_points]) + ['']
        for p in ext_points:
            if p['correct'] is False:
                L.append('- Frankie\'s answer for point %s was graded incorrect. Checks recorded as incorrect: %s.' % (
                    p['point_id'], listing(p['failing'])))
        rels = (d.doc('external-post-grade.json') or {}).get('relationship_grades') or []
        wrong_rels = [r for r in rels if not r.get('correct')]
        L += ['', 'His external pair directions graded correct: %d of %d.' % (len(rels) - len(wrong_rels), len(rels)), '']
        for r in wrong_rels:
            L.append('- Frankie\'s answer for external pair %s / %s was graded incorrect. His answer: %s. The recorded '
                     'relation: %s.' % (r['left'], r['right'], r['claimed'], r['actual']))
        if wrong_rels:
            L.append('')
    ext_response = (d.doc('external-correction-response.json') or {}).get('dipole_acknowledgement')
    if ext_response is None:
        L += ['His answers to the external corrections: not recorded (external-correction-response.json: %s).' % (
            d.why_absent('external-correction-response.json')), '']
    else:
        resolutions = ext_response.get('correction_resolutions') or []
        L += ['His answers to the external corrections: corrected understandings recorded: %d. Disagreements still '
              'held: %d.' % (len(resolutions), len(ext_response.get('remaining_disagreements') or [])), '',
              'What he will change, as recorded: %s' % rec(ext_response.get('what_i_will_change')), '']
        L += ['- External correction %s. His recorded corrected understanding: %s' % (
            r.get('correction_id'), rec(r.get('corrected_understanding'))) for r in resolutions]
        if resolutions:
            L.append('')

    L += ['## Novel findings he filed', '', 'On the 19-component lesson:', ''] + novel_lines(d)
    ext_findings = ((d.doc('external-code-answers.json') or {}).get('ledgers') or {}).get('external_novel_findings') or []
    L += ['On the external section: hypotheses filed: %d.' % len(ext_findings), '']
    for i, f in enumerate(ext_findings, 1):
        L += ['%d. Hypothesis %s.' % (i, f.get('finding_id')), '   - Premise, as recorded: %s' % rec(f.get('premise')),
              '   - Why novel, as recorded: %s' % rec(f.get('why_novel'))]
        L += ['   - Evidence cited: %s' % ref_text(r) for r in f.get('evidence_refs') or []]
    if ext_findings:
        L.append('')

    L += ['## The brain entry written for this day', '']
    if d.brain is None:
        L += ['Not recorded: %s.' % d.brain_why, '']
    else:
        m = d.brain['manifest']
        entries = m.get('entries') or []
        attachments = m.get('attachments') or []
        L += ['Entry folder: %s. Read from: %s. Files: %d. Bytes of the files (sum of the recorded sizes): %d. Files '
              'included in his later reading: %d. Attachments listed: %d. Items listed as unavailable: %d.' % (
                  Path(d.brain['path']).name, d.brain['source'], len(entries), sum(e.get('bytes') or 0 for e in entries),
                  sum(1 for e in entries if e.get('include')), len(attachments), len(m.get('unavailable') or [])), '']
        L += table(['file', 'bytes', 'included in his later reading'],
                   [(e.get('name'), rec(e.get('bytes')), yn(e.get('include'))) for e in entries]) + ['']
        if attachments:
            L += table(['attachment', 'bytes', 'included'], [(a.get('name'), rec(a.get('bytes')), yn(a.get('included')))
                                                           for a in attachments]) + ['']
        for u in m.get('unavailable') or []:
            L.append('- Unavailable (recorded): %s' % (u if isinstance(u, str) else listing(
                '%s: %s' % (k, v) for k, v in sorted(u.items())) if isinstance(u, dict) else u))
        if m.get('unavailable'):
            L.append('')
    L += school_lines(d, number) + exchange_lines(d, True)
    return L + glossary_lines() + evidence(d, True)


# ---------------------------------------------------------------------------------------------- the school section
def school_lines(d, number):
    """The school file translated field by field (the FRANKIE report only: it is his knowledge base). Per section the
    recorded author and items, how each item was carried, and every item the school listed missing or withheld with its
    recorded reason. Paths and hashes appear only in the Evidence section."""
    L = ['## The school file (what the day consolidated)', '',
         'The school file is Frankie\'s knowledge base for this day, written by the school step before these reports. '
         'This section translates what it recorded; these reports are never knowledge.', '']
    if d.school_status == 'not given':
        return L + ['Not recorded: %s.' % d.school_listed, '']
    if d.school_status != 'read':
        return L + ['INTEGRITY FAILURE (recorded; this is not a missing-data disposition and the file\'s content is not '
                    'consolidated here): %s. Recorded status: %s.' % (d.school_listed, d.school_status), '']
    doc = d.school
    sections = doc.get('sections') or {}
    if not isinstance(sections, dict):
        sections = {}
    missing, withheld = doc.get('missing') or [], doc.get('withheld') or []
    items = sum(len(v.get('items') or []) for v in sections.values() if isinstance(v, dict))
    L += ['Kind: %s. The file records: run %s, report number %s (this report: #%d), classroom status %s, written by %s. '
          'Sections: %d. Items: %d. Items listed missing: %d. Items listed withheld: %d. Model calls recorded: %s.' % (
              d.school_kind, rec(doc.get('run')), rec(doc.get('report_number')), number, rec(doc.get('classroom_status')),
              rec(doc.get('written_by')), len(sections), items, len(missing), len(withheld), rec(doc.get('model_calls'))), '']
    if d.school_listed:
        L += ['Noted: %s.' % d.school_listed, '']
    if d.school_kind == 'retained checked successor':
        r = d.school_receipt or {}
        L += ['Successor receipt (recorded): status %s; owner operation %s; source corrections applied (recorded count): '
              '%d; scientific retests recorded: %s.' % (rec(r.get('status')), rec(r.get('operation_sha256')),
                                                       len(r.get('source_corrections') or []), rec(r.get('scientific_retests'))), '']
    L += table(['section', 'author (recorded)', 'items'],
               [(name, rec((v or {}).get('author_label') or (v or {}).get('author')), len((v or {}).get('items') or []))
                for name, v in sorted(sections.items()) if isinstance(v, dict)]) + ['']
    for name, v in sorted(sections.items()):
        if not isinstance(v, dict):
            continue
        for item in v.get('items') or []:
            if item.get('inline') and item.get('holds'):
                how = 'a stated subset, inline; holds: %s' % item['holds']
            elif item.get('inline'):
                how = 'the whole file, inline'
            else:
                how = 'a pointer (recorded reason: %s)' % rec(item.get('pointer_reason'))
            L.append('- %s / %s (author recorded: %s): %s; bytes recorded: %s.' % (
                name, rec(item.get('name')), rec(item.get('author')), how, rec(item.get('bytes'))))
    if any(isinstance(v, dict) and v.get('items') for v in sections.values()):
        L.append('')
    L += ['### Listed missing in the school file', '']
    L += ['- %s / %s. Recorded reason: %s.' % (rec(m.get('section')), rec(m.get('item')), rec(m.get('reason')))
          for m in missing if isinstance(m, dict)] or ['None listed.']
    L += ['', '### Listed withheld in the school file', '']
    L += ['- %s / %s. Recorded reason: %s.' % (rec(w.get('section')), rec(w.get('item')), rec(w.get('reason')))
          for w in withheld if isinstance(w, dict)] or ['None listed.']
    return L + ['']


# ----------------------------------------------------------------------------- the 99 layers (what reached Frankie today)
# Greg, 2026-10-07: "the 99 layers combined for Frankie FIRST". Every piece already records its own all-99 list (the ROOT's
# admission list, the classroom's routes, the scientific teacher's / carried claims' / candidates' coverage files, the
# adviser pieces' rows). This step READS each list once, from the file the piece wrote (pinned files are checked against
# their pin), and joins them into ONE per-day table of the 99 entries of the shared registry (frankie_box_all99_coverage,
# imported, never copied): per entry, which pieces carried it and the word each recorded, the final disposition for
# Frankie, every entry that reached no computation with every piece's recorded reason, and every disagreement between
# pieces under fixed rules. Nothing is recomputed, nothing is inferred from a file read; a piece without a list is "not
# reported by <piece>" with the reason; an absent list is unknown, never zero; integrity failures stay separate.
FINALS = (
    ('classroom', 'the classroom recorded it reaching its pictures/computation (arrived, arrived with no event, stamped)'),
    ('classroom_thin', 'the classroom recorded it reaching its pictures partially (thin, completed-only)'),
    ('other_computation', 'another Frankie piece recorded it reaching what that piece computes on (the scientific '
                          'teacher\'s test rows, the exchange or meeting picture); the classroom did not'),
    ('consumer', 'a Frankie piece recorded it at its own consumer (knowledge, carry, teacher seat) or as a rule it '
                 'enforces; no Frankie piece recorded it in a computation'),
    ('exposed_only', 'a Frankie piece recorded it present in what it received and not used by its computation '
                     '(exposed); none recorded it in a computation or at a consumer'),
    ('nothing', 'every Frankie piece that listed it recorded it absent, withheld, disabled, retired, an output or not '
                'evaluated (each reason below)'),
    ('unknown', 'no Frankie piece reported a list that names it (not reported is unknown, never zero)'),
)
JOIN_RULES = ('the shared registry (frankie_box_all99_coverage.REGISTRY) is the list of the 99 entries; a piece row whose '
              'id is not in it is listed as unregistered, a repeated id as a duplicate (both integrity), never dropped '
              'silently; each piece\'s recorded word is shown as recorded beside its canonical word '
              'from the shared registry (the shared field\'s disposition, else LEGACY_WORDS, settled by FIXED_WORDS) and '
              'grouped by the registry\'s WORD_CLASS of the canonical word, refined only by REACH_REFINE on the piece\'s '
              'own word; a recorded class that contradicts the registry is an integrity finding; '
              'different words from different pieces are not a disagreement (the pieces compute on different things). '
              'Disagreement rules: group (a piece lists the entry under another registry group than the shared '
              'registry); lawful_role (one piece records it withheld/disabled/retired while another records it '
              'reaching a computation, consumer or rule); picture_admitted_not_arrived (the ROOT admitted a raw or '
              'calculation entry into the shared picture and every picture-reading piece that listed it recorded it '
              'absent); picture_arrived_not_admitted (the ROOT recorded it absent and a picture-reading piece recorded '
              'it arrived); summary_vs_list (a lessons file\'s carried summary counts differ from the counts of the '
              'pinned list it names). Jev\'s pieces and the ROOT are listed but never decide what reached Frankie.')


def _shared_registry():
    """The shared 99-entry registry module (frankie_box_all99_coverage, the single registry): (module, None) or (None,
    why). A missing module is stated in the report, never replaced by a local copy of the registry."""
    try:
        import frankie_box_all99_coverage as A99
    except Exception as error:  # noqa: BLE001 - stated, never replaced
        return None, 'the shared registry module frankie_box_all99_coverage could not be imported (%s: %s)' % (
            type(error).__name__, error)
    if not getattr(A99, 'REGISTRY', None) or not isinstance(getattr(A99, 'GROUP_ROLES', None), dict):
        return None, 'the shared registry module exposes no REGISTRY / GROUP_ROLES at this checkout'
    return A99, None


def _json_once(d, kind, path):
    """One read of a JSON file, witnessed in d.inputs: (doc, witness, None) or (None, None, why)."""
    try:
        raw = d._read(kind, path)
    except OSError as error:
        return None, None, '%s could not be read (%s: %s)' % (path, type(error).__name__, error)
    try:
        return json.loads(raw), d.inputs[-1], None
    except ValueError as error:
        return None, d.inputs[-1], '%s is not readable JSON (%s)' % (path, error)


def _pinned_once(d, kind, pin):
    """A file named by a pin {path, bytes, sha256}, read once: (doc, witness, why, integrity). Absent -> why (a thinner
    picture); bytes that differ from the pin or unreadable JSON -> integrity (a separate visible failure)."""
    path = pin.get('path') if isinstance(pin, dict) else None
    if not path:
        return None, None, 'no pin names the file', None
    if not Path(path).is_file():
        return None, None, 'the pinned file %s is not on this disk' % path, None
    doc, seen, why = _json_once(d, kind, path)
    if seen is None:
        return None, None, why, None
    differ = {k: (pin.get(k), seen.get(k)) for k in ('bytes', 'sha256') if pin.get(k) is not None and pin.get(k) != seen.get(k)}
    if differ:
        return None, seen, None, '%s differs from its pin: %s' % (path, listing('%s recorded %s, read %s' % (k, a, b)
                                                                              for k, (a, b) in sorted(differ.items())))
    if why:
        return None, seen, None, why
    return doc, seen, None, None


def _step(d, run_dir, run_name, stage):
    """The orchestrator's step receipt of the day for one stage: (doc, witness, why, integrity)."""
    path = Path(run_dir) / 'days' / d.day / (stage + '.json')
    if not path.is_file():
        return None, None, 'no %s step receipt for the day (%s)' % (stage, path), None
    doc, seen, why = _json_once(d, '%s step receipt' % stage, path)
    if doc is None:
        return None, seen, None, why
    if (doc.get('schema') != STEP_SCHEMA or doc.get('run') != run_name or doc.get('stage') != stage
            or str(doc.get('key')) != str(d.day)):
        return None, seen, None, '%s is not the %s step receipt of run %s day %s (schema %s, run %s, stage %s, key %s)' % (
            path, stage, run_name, d.day, doc.get('schema'), doc.get('run'), doc.get('stage'), doc.get('key'))
    return doc, seen, None, None


def _use_all99(receipt):
    """A piece's workflow_report.use.all_99_coverage (the adviser pieces' recorded field), or None."""
    report = receipt.get('workflow_report') if isinstance(receipt, dict) else None
    use = report.get('use') if isinstance(report, dict) else None
    return use.get('all_99_coverage') if isinstance(use, dict) else None


def collect_all99(d, run_name, run_dir, piece_receipts):
    """Read every piece's recorded all-99 list for the day, once each. Sets d.all99_sources: one dict per piece
    (piece, for_frankie, status read / not_reported / integrity, reason, file, sha256, doc, summary, basis) and
    d.all99_lessons_source (where the scientific teacher's lessons list came from: LESSONS_BASIS)."""
    frankie_of = {p: f for p, f, _ in ALL99_PIECES}
    sources, problems = [], []

    def src(piece, status, reason=None, doc=None, seen=None, summary=None, for_frankie=None, basis=None):
        sources.append(dict(piece=piece, for_frankie=frankie_of.get(piece, True) if for_frankie is None else for_frankie,
                            status=status, reason=reason, doc=doc, summary=summary, basis=basis,
                            file=(seen or {}).get('path'), sha256=(seen or {}).get('sha256')))

    def from_step(piece, stage, field):
        doc, seen, why, bad = _step(d, run_dir, run_name, stage)
        if bad:
            return src(piece, 'integrity', bad, seen=seen)
        if doc is None:
            return src(piece, 'not_reported', why)
        if not isinstance(doc.get(field), dict):
            return src(piece, 'not_reported', 'the %s step receipt (status %s) carries no %s list%s' % (
                stage, doc.get('status'), field, (': ' + str(doc['reason'])) if doc.get('reason') else ''), seen=seen)
        # the list's own identity (path#field, sha256 of its canonical JSON), not the step receipt's bytes: a step receipt
        # rewritten by a restart ('reused') with the same list is the same join input (late_pieces_changed)
        return src(piece, 'read', doc=doc[field], seen=dict(path='%s#%s' % (seen.get('path'), field),
                                                           sha256=sha256_bytes(json.dumps(doc[field], sort_keys=True).encode())))

    def coverage_file(piece, receipt_kind, receipt_doc, receipt_seen):
        """workflow_report.outputs.all99_coverage_files[<day>] of a scientific receipt: the pinned list, read once."""
        files = (((receipt_doc or {}).get('workflow_report') or {}).get('outputs') or {}).get('all99_coverage_files') or {}
        pin = files.get(d.day) if isinstance(files, dict) else None
        if pin is None:
            return src(piece, 'not_reported', 'the %s names no all-99 list for day %s (its lists: %s)' % (
                receipt_kind, d.day, listing(sorted(files)) if isinstance(files, dict) else 'none'), seen=receipt_seen)
        doc, seen, why, bad = _pinned_once(d, '%s all-99 list' % piece, pin)
        if bad:
            return src(piece, 'integrity', bad, seen=seen)
        if doc is None:
            return src(piece, 'not_reported', why)
        summary = ((receipt_doc.get('workflow_report') or {}).get('use') or {}).get('all99_coverage')
        return src(piece, 'read', doc=doc, seen=seen, summary=(summary or {}).get(d.day) if isinstance(summary, dict) else None)

    # the ROOT (producer side: what it produced and admitted into the shared picture)
    from_step('root', 'root', 'all99')
    # the classroom (its receipt was read once by Day; a refused classroom records its list too)
    if d.source.get('kind') != 'classroom receipt':
        src('classroom', 'not_reported', 'the classroom wrote no receipt: %s' % d.receipt.get('reason'))
    elif not isinstance(d.receipt.get('all99_coverage'), dict):
        src('classroom', 'not_reported', 'the classroom receipt (status %s) carries no all99_coverage (recorded before the '
                                         'list existed)' % d.status,
            seen=dict(path=d.source.get('path'), sha256=d.source.get('sha256')))
    else:
        src('classroom', 'read', doc=d.receipt['all99_coverage'],
            seen=dict(path=d.source.get('path'), sha256=d.source.get('sha256')))
    # the scientific teacher: every current-day lessons file the exchange consumed, each read once (F9b, 2026-10-07 second
    # pass). The list comes from, in order (LESSONS_BASIS; the basis is recorded on each piece and in the join inputs, so
    # a list that may be stale is distinguishable from a current one):
    #   exchange_record        the exchange document this step read (d.exchange) records its own lesson inputs in
    #                          sources.lessons, delivered path/bytes/sha256 (the original exchange and a checked successor
    #                          alike): current after a reused exchange receipt or a successor rebuild; each file is read
    #                          against that pin (other bytes are an integrity failure). Accumulated lesson documents
    #                          (accumulated: true) are counted and listed, not joined (their days are other days).
    #   exchange_step_receipt  no exchange document was read: the exchange step receipt's lessons list (a reused or
    #                          successor step records none, so the list may be stale)
    #   conventional_path      neither: Frankie's lessons at their conventional path (may be stale)
    # (the school file's whole inline copy is used when it carries that path: the bytes the school read, not a re-read;
    # a copy whose source_sha256 differs from the exchange's pin is an integrity failure, never a silent substitute)
    xstep, _, xwhy, xbad = _step(d, run_dir, run_name, 'exchange')
    if xbad:
        problems.append('exchange step receipt integrity: ' + xbad)
    record = d.exchange.get('sources') if isinstance(d.exchange, dict) else None
    accumulated = []
    if isinstance(record, dict) and isinstance(record.get('lessons'), list):
        named = [x for x in record['lessons'] if isinstance(x, dict)]
        accumulated = [dict(path=x.get('path'), sha256=x.get('sha256'), author=x.get('author'))
                       for x in named if x.get('accumulated')]
        pins = [{k: x.get(k) for k in ('path', 'bytes', 'sha256')} for x in named if not x.get('accumulated')]
        basis = 'exchange_record'
        origin = ('the exchange document read by this step (%s, sha256 %s): its sources.lessons, %d current-day lessons '
                  'file(s) joined, %d accumulated lesson document(s) listed, not joined' % (
                      d.exchange_path, d.exchange_sha256, len(pins), len(accumulated)))
    elif (xstep or {}).get('lessons'):
        pins, basis = [dict(path=str(x)) for x in xstep['lessons']], 'exchange_step_receipt'
        origin = ('the exchange step receipt\'s lessons list (no exchange document was read by this step: %s); MAY BE '
                  'STALE: a reused or successor exchange step records no list' % (d.exchange_listed or 'none given'))
    else:
        mine = LESSONS_ROOT / 'frankie' / ('%s-frankie.json' % d.day)
        pins, basis = ([dict(path=str(mine))], 'conventional_path') if mine.is_file() else ([], None)
        origin = ('the conventional path of Frankie\'s lessons (no exchange document and no exchange lessons list: %s); '
                  'MAY BE STALE' % (xwhy or (xstep or {}).get('status')) if mine.is_file() else
                  'no exchange document, no exchange lessons list and no lessons file at the conventional path (%s)' % (
                      xwhy or (xstep or {}).get('status')))
    d.all99_lessons_source = dict(basis=basis, current=basis == 'exchange_record', origin=origin,
                                  exchange=(dict(path=d.exchange_path, sha256=d.exchange_sha256)
                                            if d.exchange is not None else None),
                                  named=pins, accumulated_not_joined=accumulated)
    paths = [str(x.get('path')) for x in pins]
    inline = {}
    if d.school_status == 'read':
        for item in ((d.school.get('sections') or {}).get('scientific_teacher') or {}).get('items') or []:
            if isinstance(item, dict) and item.get('inline') and 'holds' not in item and item.get('path') \
                    and isinstance(item.get('content'), dict):
                inline[item['path']] = item
    seen_authors = set()
    for pin in pins:
        path = str(pin.get('path'))
        if path in inline:
            copy_sha = inline[path].get('source_sha256') or inline[path].get('sha256')
            if pin.get('sha256') and copy_sha != pin['sha256']:
                problems.append('lessons file %s: the school file\'s inline copy records sha256 %s; %s pins %s (integrity: '
                                'two records of one file disagree; not joined)' % (path, copy_sha, basis, pin['sha256']))
                continue
            lesson = inline[path]['content']
            d.inputs.append(dict(kind='lessons file (the school file\'s whole inline copy)', path=path,
                                 bytes=inline[path].get('bytes'), sha256=copy_sha, read_by='the school file read once above'))
            lseen = d.inputs[-1]
        elif pin.get('sha256'):
            lesson, lseen, why, bad = _pinned_once(d, 'lessons file', pin)
            if lesson is None:
                problems.append('lessons file %s: %s' % (path, bad or why))
                continue
        else:
            lesson, lseen, why = _json_once(d, 'lessons file', path)
            if lesson is None:
                problems.append('lessons file %s: %s' % (path, why))
                continue
        if not isinstance(lesson, dict):
            problems.append('lessons file %s is a %s, not a lessons document' % (path, type(lesson).__name__))
            continue
        author = str(lesson.get('author') or Path(path).parent.name)
        piece = 'scientific_teacher[%s]' % author
        same = sum(1 for s in sources if s['piece'] == piece or s['piece'].startswith(piece + ' #'))
        if same:                                    # a second lessons file of the same author (two Jev stamps): its own column
            piece = '%s #%d' % (piece, same + 1)
        seen_authors.add(author)
        by_day = (lesson.get('all99_coverage') or {}).get('by_day') if isinstance(lesson.get('all99_coverage'), dict) else None
        pin_day = (by_day or {}).get(d.day) if isinstance(by_day, dict) else None
        if pin_day is None:
            src(piece, 'not_reported', 'the lessons file (%s) carries no all-99 list for day %s%s' % (
                lesson.get('schema'), d.day, '' if by_day else ' (lessons written before the list existed)'),
                seen=lseen, for_frankie=author != 'jev', basis=basis)
            continue
        doc, seen, why, bad = _pinned_once(d, '%s all-99 list' % piece, pin_day)
        if bad:
            src(piece, 'integrity', bad, seen=seen, for_frankie=author != 'jev', basis=basis)
        elif doc is None:
            src(piece, 'not_reported', why, for_frankie=author != 'jev', basis=basis)
        else:
            src(piece, 'read', doc=doc, seen=seen, summary=pin_day.get('summary'), for_frankie=author != 'jev', basis=basis)
    for author in ('frankie', 'historical', 'jev'):
        if author not in seen_authors:
            src('scientific_teacher[%s]' % author, 'not_reported',
                'no %s lessons file among %s (%s)' % (author, origin, listing(paths) if paths else 'none named'), basis=basis)
    # carried claims (the accumulated-lessons step; on a classroom-arm day the exchange carries them, listed there)
    given = piece_receipts.get('carried_claims')
    if given:
        doc, seen, why = _json_once(d, 'carried claims receipt', given)
        if doc is None:
            src('carried_claims', 'integrity' if seen else 'not_reported', why, seen=seen)
        else:
            coverage_file('carried_claims', 'carried claims receipt', doc, seen)
    else:
        step, sseen, why, bad = _step(d, run_dir, run_name, 'accumulated_lessons')
        if bad:
            src('carried_claims', 'integrity', bad, seen=sseen)
        elif step is None or not step.get('receipt'):
            src('carried_claims', 'not_reported', why or 'the accumulated-lessons step (status %s) names no receipt%s' % (
                step.get('status'), (': ' + str(step['reason'])) if step.get('reason') else ''))
        else:
            doc, seen, why, bad = _pinned_once(d, 'carried claims receipt', dict(path=step['receipt'],
                                                                                  sha256=step.get('receipt_sha256')))
            if bad:
                src('carried_claims', 'integrity', bad, seen=seen)
            elif doc is None:
                src('carried_claims', 'not_reported', why)
            else:
                coverage_file('carried_claims', 'carried claims receipt', doc, seen)
    # the survivor/candidate update (a cross-day boundary piece: present when this day is a boundary or one is given)
    given = piece_receipts.get('candidates') or (SURVIVORS / run_name / d.day / 'receipt.json')
    if not Path(given).is_file():
        src('candidates', 'not_reported', 'no survivor/candidate update receipt for this day (%s): the update runs at a '
                                          'cross-day batch boundary and none was given' % given)
    else:
        doc, seen, why = _json_once(d, 'candidates receipt', given)
        if doc is None:
            src('candidates', 'integrity' if seen else 'not_reported', why, seen=seen)
        else:
            coverage_file('candidates', 'candidate update receipt', doc, seen)
    # the exchange: its receipt beside exchange.json (the exchange given to this step, else the step's own path)
    exchange_path = d.exchange_path or (xstep or {}).get('exchange')
    if not exchange_path:
        src('exchange', 'not_reported', d.exchange_listed or 'no exchange for the day')
    else:
        doc, seen, why = _json_once(d, 'exchange receipt', Path(exchange_path).with_name('receipt.json'))
        if doc is None:
            src('exchange', 'integrity' if seen else 'not_reported', why, seen=seen)
        elif str(doc.get('day')) != str(d.day):
            src('exchange', 'integrity', 'the exchange receipt is for day %s, not %s' % (doc.get('day'), d.day), seen=seen)
        elif not isinstance(_use_all99(doc), dict):
            src('exchange', 'not_reported', 'the exchange receipt carries no workflow_report.use.all_99_coverage', seen=seen)
        else:
            src('exchange', 'read', doc=_use_all99(doc), seen=seen)
    # the meeting: the receipt frankie_box_brain.read_meeting_for_exchange already read and verified
    meeting_receipt = d.meeting.get('receipt') if isinstance(d.meeting.get('receipt'), dict) else None
    mseen = dict(path=str(Path(d.meeting['path']).with_name('receipt.json')) if d.meeting.get('path') else None,
                 sha256=None)
    if meeting_receipt is None:
        src('meeting', 'not_reported', 'no meeting receipt (%s: %s)' % (d.meeting.get('status'), d.meeting.get('reason')))
    elif not isinstance(_use_all99(meeting_receipt), dict):
        src('meeting', 'not_reported', 'the meeting receipt (status %s) carries no workflow_report.use.all_99_coverage'
            % meeting_receipt.get('status'), seen=mseen)
    else:
        src('meeting', 'read', doc=_use_all99(meeting_receipt), seen=mseen)
    # Jev (listed; never decides what reached Frankie): his CPU receipt and the client receipt it pins
    given, jev, jseen, jwhy, jbad = piece_receipts.get('jev'), None, None, None, None
    if not given:
        step, jseen, jwhy, jbad = _step(d, run_dir, run_name, 'jev')
        if step is not None and step.get('receipt'):
            given = step['receipt']
        elif step is not None:
            jwhy = 'the Jev step (status %s) names no receipt%s' % (step.get('status'),
                                                                  (': ' + str(step['reason'])) if step.get('reason') else '')
    if given and not jbad:
        jev, jseen, jwhy = _json_once(d, 'Jev receipt', given)
        if jev is None and jseen is not None:
            jbad = jwhy
    if jbad:
        src('jev', 'integrity', jbad, seen=jseen)
        src('jev_sit_in', 'not_reported', 'the Jev receipt that pins the client receipt failed its integrity check')
    elif jev is None:
        src('jev', 'not_reported', jwhy, seen=jseen)
        src('jev_sit_in', 'not_reported', 'no Jev receipt to name the client receipt (%s)' % jwhy)
    else:
        src('jev', 'read', doc=_use_all99(jev), seen=jseen) if isinstance(_use_all99(jev), dict) else \
            src('jev', 'not_reported', 'the Jev receipt (status %s) carries no workflow_report.use.all_99_coverage'
                % jev.get('status'), seen=jseen)
        client, cseen, cwhy, cbad = _pinned_once(d, 'Jev client receipt', jev.get('client_receipt'))
        if cbad:
            src('jev_sit_in', 'integrity', cbad, seen=cseen)
        elif client is None:
            src('jev_sit_in', 'not_reported', cwhy)
        elif not isinstance(_use_all99(client), dict):
            src('jev_sit_in', 'not_reported', 'the Jev client receipt carries no workflow_report.use.all_99_coverage',
                seen=cseen)
        else:
            src('jev_sit_in', 'read', doc=_use_all99(client), seen=cseen)
    order = {p: i for i, (p, _, _) in enumerate(ALL99_PIECES)}
    sources.sort(key=lambda s: (order.get(s['piece'].split(' #')[0], len(order)), s['piece']))
    d.all99_sources, d.all99_problems = sources, problems
    # Frankie's 13 day-file points: each piece's own per-point record (part of the join's input set)
    collect_external_points(d, run_name, run_dir)


def _rows(doc, shared_schema):
    """(rows, None, used) from a piece's recorded list, or (None, why, used). The shared field FRANKIE_ALL99_COVERAGE_V1
    is preferred: the document itself when it is one, else its nested `shared_field` (the pieces carry both); otherwise
    the piece's own shape (entries[] of the ROOT and the classroom, rows[] of the adviser pieces). `used` names the shared
    field read (dict(where, doc)) or None. Fields are taken as recorded."""
    if not isinstance(doc, dict):
        return None, 'the recorded list is not a mapping', None
    used = None
    if shared_schema and doc.get('schema') == shared_schema:
        used = dict(where='the list itself (%s)' % shared_schema, doc=doc)
    elif shared_schema and isinstance(doc.get('shared_field'), dict) and doc['shared_field'].get('schema') == shared_schema:
        used = dict(where='its shared_field (%s)' % shared_schema, doc=doc['shared_field'])
        doc = doc['shared_field']
    if doc.get('present') is False:
        return None, 'the piece recorded no per-entry rows: %s (counts recorded: %s)' % (
            rec(doc.get('reason')), json.dumps(doc.get('counts'), sort_keys=True)), used
    items = doc['entries'] if isinstance(doc.get('entries'), list) else doc['rows'] if isinstance(doc.get('rows'), list) else None
    if not items and doc.get('error'):
        return None, 'the piece recorded that its list could not be built: %s' % doc['error'], used
    if items is None:
        return None, 'the recorded list (schema %s) carries no entries[] or rows[]' % rec(doc.get('schema')), used
    # disposition = the piece's own word as recorded (a shared field carries it as piece_disposition); shared = the shared
    # field's canonical word (None for a piece's own legacy list; canonical_of maps it through the registry then)
    shared = used is not None
    return [dict(entry=item.get('entry') or item.get('layer'), group=item.get('group'),
                 disposition=(item.get('piece_disposition') or item.get('disposition')) if shared else item.get('disposition'),
                 shared=item.get('disposition') if shared else None,
                 reason=item.get('reason'), consumer=item.get('consumer'), count=item.get('count'), **{'class': item.get('class')})
            if isinstance(item, dict) else dict(entry=None) for item in items], None, used



# ------------------------------------------------------------- Frankie's 13 day-file points under their 99 entries
# Greg, 2026-10-07 night: the 13 points MUST be attached to the 99-layer combination. Each point's own sub-row sits under
# every 99 entry the day file maps it to (the day file receipt's point_registry_map: points, registry entries, mapping,
# reason, event-time basis), with each consuming piece's OWN recorded per-point disposition. Additive: the per-entry rows
# are unchanged. A piece that records nothing per point is not_reported (never inferred from its per-entry row).
EXTERNAL_POINT_PIECES = (
    ('shared_reader', 'the shared market reader\'s external publications as the BOSS teacher\'s full read recorded them '
                      '(teacher receipt shared_market_read.external_publications.points: per table rows and presented)'),
    ('teacher', 'the BOSS teacher receipt external_points (FRANKIE_TEACHER_EXTERNAL_POINTS_V1, from its external section '
                'key: per point used / missing, rows used, series, missing with reason)'),
    ('classroom', 'the classroom receipt all99_coverage.external_points.points (computed / context / absent, with reason)'),
    ('search', 'the search MANIFEST external source: searched fields and alias series per day-file table, absent series'),
    ('scientific_teacher', 'the lessons files: per-entry lists only (no per-point record)'),
    ('exchange', 'the exchange receipt: per-entry list only (no per-point record)'),
    ('meeting', 'the meeting receipt (Granite): per-entry list only (no per-point record)'),
    ('jev', 'the Jev receipts: per-entry list only (no per-point record)'),
)
POINT_PIECE_PREFIX = 'external_points[%s]'


def _point_declaration(d, run_dir, run_name):
    """The 13 points as the day file used today declares them: {point_id: point}, and the source record. Read once: the
    day file receipt beside the day file the classroom (else the external step) recorded; its point_registry_map (table or
    table-prefix -> points, registry entries, mapping, reason, event-time basis, note) and point_mappings (per table rows).
    Without that receipt: the builder's POINT_REGISTRY_MAP (the module constant), named as the basis."""
    day_file = ((d.receipt.get('external') or {}).get('day_file') or {}).get('path') if isinstance(d.receipt, dict) else None
    origin = 'the classroom receipt\'s external.day_file'
    if not day_file:
        step, _, why, bad = _step(d, run_dir, run_name, 'external')
        day_file = (step or {}).get('day_file')
        origin = 'the external step receipt\'s day_file'
    registry, mappings, src = None, {}, dict(piece=POINT_PIECE_PREFIX % 'declaration', for_frankie=True, basis=None,
                                             status='not_reported', reason=None, file=None, sha256=None)
    if day_file:
        doc, seen, why = _json_once(d, 'day file receipt', Path(day_file).with_name('day-external-receipt.json'))
        if doc is None:
            src.update(status='integrity' if seen else 'not_reported', reason=why)
        elif str(doc.get('trading_day')) != str(d.day):
            src.update(status='integrity', reason='the day file receipt is for day %s, not %s' % (doc.get('trading_day'), d.day),
                       file=seen.get('path'), sha256=seen.get('sha256'))
        else:
            registry, mappings = doc.get('point_registry_map'), doc.get('point_mappings') or {}
            src.update(status='read' if isinstance(registry, dict) else 'not_reported', file=seen.get('path'),
                       sha256=seen.get('sha256'), basis='day_file_receipt',
                       reason=('%s (%s)' % (origin, day_file)) if isinstance(registry, dict) else
                       'the day file receipt carries no point_registry_map (a day file built before the 99 mapping)')
    else:
        src.update(reason='no day file is recorded for the day (classroom receipt or external step)')
    if not isinstance(registry, dict):
        try:
            from research.kalshi.frankie_boss.operations.frankie_day_external import POINT_REGISTRY_MAP
            registry = POINT_REGISTRY_MAP
            src['basis'] = 'builder_constant'
            src['reason'] = '%s; the builder\'s POINT_REGISTRY_MAP is used for the mapping (not this day\'s file)' % src['reason']
        except Exception as error:  # noqa: BLE001 - no declaration: the points are listed by name only
            registry = {}
            src['reason'] = '%s; the builder constant is not importable (%s: %s)' % (src['reason'], type(error).__name__, error)
    names, default_tables = {}, {}
    try:
        from research.kalshi.frankie_boss import dipole_classroom_external as EXT
        for item in tuple(EXT.POINTS) + tuple(EXT.DEFERRED['points']):
            if item.get('point_id') is not None:
                names[item['point_id']] = item['name']
                default_tables[item['point_id']] = list(item.get('tables') or ())
    except Exception:  # noqa: BLE001 - names are a convenience; the ids and the mapping stand without them
        pass

    def map_key(table):
        if table in registry:
            return table
        prefixes = [k for k in registry if k.endswith('.') and table.startswith(k)]
        return max(prefixes, key=len) if prefixes else None
    points = {}

    def point(pid):
        return points.setdefault(pid, dict(point_id=pid, name=names.get(pid), tables=[], rows=0, declared_by=[],
                                           entries=[], mapping=[], mapping_reason=[], event_time_basis=[], note=[]))
    for key, item in sorted(registry.items()):
        for pid in item.get('points') or []:
            p = point(pid)
            p['declared_by'].append(key)
            for field, value in (('entries', item.get('registry_entries') or []), ('mapping', [item.get('registry_mapping')]),
                                 ('mapping_reason', [item.get('registry_mapping_reason')]),
                                 ('event_time_basis', [item.get('event_time_basis')]), ('note', [item.get('event_time_note')])):
                for v in value:
                    if v is not None and v not in p[field]:
                        p[field].append(v)
    for table, item in sorted(mappings.items()):
        key = map_key(table)
        for pid in (registry.get(key) or {}).get('points') or []:
            point(pid)['tables'].append(table)
            point(pid)['rows'] += int((item or {}).get('rows') or 0)
    for pid in sorted(set(names) | set(points)):
        p = point(pid)
        if not p['tables']:
            p['tables'] = list(default_tables.get(pid) or [])
            p['tables_basis'] = 'the classroom\'s point table list (the day file receipt names no table rows for it)'
        if not p['entries']:
            p['unmapped'] = 'the day file declares no 99 entry for this point: listed here, never guessed'
    return points, src


def collect_external_points(d, run_name, run_dir):
    """Every consuming piece's OWN per-point record of the day's 13 points, read once each. Sets d.all99_point_sources
    (one source per piece: piece, status, reason, file, sha256, basis, points {point_id: dict(disposition, reason)}) and
    d.all99_points (the declaration). Only recorded per-point facts: a piece without one is not_reported."""
    points, decl = _point_declaration(d, run_dir, run_name)
    sources = [decl]
    tables_of = {pid: list(p['tables']) for pid, p in points.items()}

    def add(piece, status, reason=None, seen=None, per=None, basis=None):
        sources.append(dict(piece=POINT_PIECE_PREFIX % piece, for_frankie=piece not in ('jev',), status=status,
                            reason=reason, file=(seen or {}).get('path'), sha256=(seen or {}).get('sha256'), basis=basis,
                            points=per or {}))
    # the shared reader, as the BOSS teacher's full read recorded it
    rows_dir = d.receipt.get('teacher_rows') if isinstance(d.receipt, dict) else None
    teacher, tseen, twhy = (None, None, 'the classroom receipt names no teacher rows') if not rows_dir else \
        _json_once(d, 'teacher receipt', Path(rows_dir) / 'receipt.json')
    pubs = ((teacher or {}).get('shared_market_read') or {}).get('external_publications') if isinstance(teacher, dict) else None
    if teacher is None:
        add('shared_reader', 'integrity' if tseen else 'not_reported', twhy, seen=tseen)
    elif not isinstance(pubs, dict) or not isinstance(pubs.get('points'), dict):
        add('shared_reader', 'not_reported', 'the teacher receipt records no shared external publications (no shared '
                                             'read, or a read without the day file)', seen=tseen)
    else:
        per = {}
        for pid, tables in tables_of.items():
            have = {t: pubs['points'][t] for t in tables if isinstance(pubs['points'].get(t), dict)}
            presented = sum(int(v.get('presented') or 0) for v in have.values())
            rows = sum(int(v.get('rows') or 0) for v in have.values())
            gone = [t for t in tables if t not in have]
            if presented:
                per[pid] = dict(disposition='presented', presented=presented, rows=rows,
                                reason='%d publication(s) of %s presented in the picture at/after their placement' % (
                                    presented, listing(sorted(have))) + ('; not in the read: %s' % listing(gone) if gone else ''))
            elif have:
                waiting = {t: len((pubs.get('not_yet_public') or {}).get(t) or []) for t in have}
                per[pid] = dict(disposition='missing', presented=0, rows=rows,
                                reason='none of its %d row(s) was presented by the halt (not yet public: %s; after halt: %s)'
                                       % (rows, json.dumps(waiting, sort_keys=True),
                                          json.dumps({t: (pubs.get('after_halt') or {}).get(t) for t in have}, sort_keys=True)))
            else:
                per[pid] = dict(disposition='missing', reason='its tables (%s) are not in the day file the reader read'
                                                                % listing(tables))
        add('shared_reader', 'read', seen=tseen, per=per, basis='teacher_receipt')
    # the BOSS teacher's own use of the day file: its receipt's external_points (FRANKIE_TEACHER_EXTERNAL_POINTS_V1, from
    # its external section key), read like the classroom's list; a receipt from before the field is not_reported
    tpoints = teacher.get('external_points') if isinstance(teacher, dict) else None
    if not isinstance(teacher, dict):
        add('teacher', 'not_reported', twhy)
    elif not isinstance(tpoints, dict):
        add('teacher', 'not_reported', 'the BOSS teacher receipt records no per-point list (written before the field; its '
                                       'external section status %s)' % rec((teacher.get('external_section') or {}).get('status')),
            seen=tseen)
    elif not isinstance(tpoints.get('points'), list) or (tpoints.get('status') != 'built' and not tpoints.get('points')):
        add('teacher', 'not_reported', 'the BOSS teacher built no per-point list: %s (%s)' % (
            rec(tpoints.get('status')), rec(tpoints.get('reason'))),
            seen=dict(path='%s#external_points' % (tseen or {}).get('path'),
                      sha256=sha256_bytes(json.dumps(tpoints, sort_keys=True).encode())))
    else:
        per = {}
        for item in tpoints['points']:
            if isinstance(item, dict) and item.get('point_id') is not None:
                per[item['point_id']] = dict(disposition=item.get('use'), reason=item.get('reason'),
                                             rows_used=item.get('rows_used'),
                                             series=[x.get('series') for x in item.get('series') or [] if isinstance(x, dict)],
                                             missing=[x.get('reason') for x in item.get('missing') or [] if isinstance(x, dict)])
        add('teacher', 'read', seen=dict(path='%s#external_points' % (tseen or {}).get('path'),
                                         sha256=sha256_bytes(json.dumps(tpoints, sort_keys=True).encode())),
            per=per, basis='teacher_receipt')
    # the classroom
    ext = ((d.receipt.get('all99_coverage') or {}).get('external_points') if isinstance(d.receipt, dict) else None) or {}
    if d.source.get('kind') != 'classroom receipt':
        add('classroom', 'not_reported', 'the classroom wrote no receipt: %s' % d.receipt.get('reason'))
    elif not isinstance(ext.get('points'), list):
        add('classroom', 'not_reported', 'the classroom receipt records no per-point list (%s)' % rec(ext.get('reason') or ext.get('status')),
            seen=dict(path=d.source.get('path'), sha256=d.source.get('sha256')))
    else:
        per = {}
        for item in ext['points']:
            if isinstance(item, dict) and item.get('point_id') is not None:
                per[item['point_id']] = dict(disposition=item.get('use'), reason=item.get('reason'),
                                             present_rows=sum(int(o.get('present_rows') or 0) for o in item.get('series') or []
                                                              if isinstance(o, dict)))
        add('classroom', 'read', seen=dict(path='%s#all99_coverage.external_points' % d.source.get('path'),
                                           sha256=sha256_bytes(json.dumps(ext, sort_keys=True).encode())),
            per=per, basis='classroom_receipt')
    # the search
    step, sseen, swhy, sbad = _step(d, run_dir, run_name, 'search')
    if sbad:
        add('search', 'integrity', sbad, seen=sseen)
    elif step is None or not step.get('target'):
        add('search', 'not_reported', swhy or 'the search step (status %s) names no target' % (step or {}).get('status'))
    else:
        manifest, mseen, mwhy = _json_once(d, 'search MANIFEST', Path(step['target']) / 'MANIFEST.json')
        source = next((x for x in (manifest or {}).get('sources') or [] if isinstance(x, dict) and x.get('source') == 'external'),
                      None) if isinstance(manifest, dict) else None
        if manifest is None:
            add('search', 'integrity' if mseen else 'not_reported', mwhy, seen=mseen)
        elif source is None:
            add('search', 'not_reported', 'the search MANIFEST records no external source (no day file beside its ingest)',
                seen=mseen)
        else:
            searched = (source.get('all_fields') or {}).get('searched') or []
            aliases = (source.get('all_fields') or {}).get('alias_definitions') or []
            absent = source.get('absent') or []
            per = {}
            for pid, tables in tables_of.items():
                fields = sum(1 for f in searched if any(str(f).startswith('external.%s.' % t) for t in tables))
                named = [a.get('name') for a in aliases if isinstance(a, dict) and a.get('point') in tables
                         and a.get('name') in (source.get('series') or [])]
                gone = [a for a in absent if isinstance(a, dict) and a.get('point') in tables]
                if fields or named:
                    per[pid] = dict(disposition='searched', fields=fields, alias_series=named,
                                    reason='%d field series and %d alias series of its tables entered the coupling search'
                                           % (fields, len(named)))
                else:
                    per[pid] = dict(disposition='missing', reason=('absent: %s' % listing('%s (%s)' % (a.get('series'), a.get('reason'))
                                                                                       for a in gone)) if gone else
                                    'no searched series of its tables (%s)' % listing(tables))
            add('search', 'read', seen=mseen, per=per, basis='search_manifest')
    for piece in ('scientific_teacher', 'exchange', 'meeting', 'jev'):
        add(piece, 'not_reported', 'this piece records a per-entry list only; no per-point record (its per-entry row is '
                                   'in the 99 table)')
    d.all99_points, d.all99_point_sources = points, sources


def external_points_rows(points, point_sources):
    """Per point (point-major): its declaration and every piece's own disposition (not_reported where the piece recorded
    none, never inferred)."""
    out = []
    for pid in sorted(points, key=lambda x: (str(type(x)), x)):
        p = points[pid]
        per = []
        for s in point_sources[1:]:
            name = s['piece'][len('external_points['):-1]
            if s['status'] != 'read':
                per.append(dict(piece=name, disposition=s['status'], reason=s['reason']))
            else:
                got = s['points'].get(pid)
                per.append(dict(piece=name, **got) if got else
                           dict(piece=name, disposition='not_reported', reason='the piece\'s list has no row for this point'))
        out.append(dict(p, pieces=per))
    return out


def join_inputs(sources):
    """The join's input set: one row per piece list (piece, status, file, sha256, reason, basis). Its sha256 is the join's
    join_sha256 (the reports' reuse key); late_pieces_changed compares it by JOIN_COMPARED (no reason text)."""
    return [dict(piece=s['piece'], status=s['status'], file=s['file'], sha256=s['sha256'], reason=s['reason'],
                 basis=s.get('basis')) for s in sources]


def all99_join(day, sources, problems, lessons_source=None, point_sources=None, points=None):
    """The ONE per-day table of the 99 entries from the pieces' recorded lists (ALL99_JOIN_SCHEMA). Returns the join
    document; its sha256 over the inputs (join_inputs) binds the reports' reuse. lessons_source: where the scientific
    teacher's lessons list came from (collect_all99's d.all99_lessons_source), carried as recorded."""
    A99, registry_why = _shared_registry()
    inputs = join_inputs(list(sources) + list(point_sources or []))   # the ONE formula (late_pieces_changed uses the same)
    join_sha256 = sha256_bytes(json.dumps(inputs, sort_keys=True).encode())
    pieces, per, integrity = [], {}, [dict(kind='problem', detail=p) for p in problems]
    known = {layer: group for layer, group, _ in A99.REGISTRY} if A99 else {}
    validate = getattr(A99, 'validate', None)
    for s in sources:
        if s['status'] == 'read' and not isinstance(s['doc'], dict):
            s = dict(s, status='integrity', reason='the recorded list is a %s, not a JSON object' % type(s['doc']).__name__)
        summary = dict(piece=s['piece'], for_frankie=s['for_frankie'], status=s['status'], reason=s['reason'],
                       file=s['file'], sha256=s['sha256'], basis=s.get('basis'),
                       schema=s['doc'].get('schema') if isinstance(s['doc'], dict) else None)
        if s['status'] == 'integrity':
            integrity.append(dict(kind='piece', piece=s['piece'], detail=s['reason']))
        if s['status'] == 'read':
            # the registry pin each piece recorded on its own list (the ROOT's crosswalk integrity, the classroom's registry
            # status, the shared lists' registry_integrity): a difference stays a visible integrity finding
            pin_state = ((s['doc'].get('crosswalk') or {}).get('integrity') if isinstance(s['doc'].get('crosswalk'), dict) else None,
                         (s['doc'].get('registry') or {}).get('status') if isinstance(s['doc'].get('registry'), dict) else None)
            if pin_state[0] in ('differs', 'unreadable') or str(pin_state[1] or '').startswith(('integrity', 'unreadable')):
                integrity.append(dict(kind='registry', piece=s['piece'], detail='the piece recorded its registry pin as %s'
                                      % listing(x for x in pin_state if x)))
            found = [x for x in s['doc'].get('registry_integrity') or []
                     if not (isinstance(x, dict) and x.get('kind') == 'crosswalk_not_in_checkout')]   # listed, not a failure
            if found:
                integrity.append(dict(kind='registry', piece=s['piece'], detail='registry_integrity recorded: %s'
                                      % json.dumps(found, sort_keys=True)))
        if s['status'] == 'read' and A99:
            rows, why, used = _rows(s['doc'], getattr(A99, 'SCHEMA', None))
            if used is not None:
                summary['read_from'] = used['where']
                # validated at this boundary by the one registry module (frankie_box_all99_coverage.validate) and the
                # piece's own recorded build findings carried: both visible integrity findings, never relabelled
                findings = list(validate(used['doc'])) if callable(validate) else []
                recorded = used['doc'].get('integrity') if isinstance(used['doc'].get('integrity'), list) else []
                for label, values in (('the shared validator found', findings), ('the piece recorded', recorded)):
                    if values:
                        integrity.append(dict(kind='field', piece=s['piece'], detail='%s %d finding(s): %s' % (
                            label, len(values), listing('%s %s' % (f.get('kind'), f.get('entry') or '') if isinstance(f, dict)
                                                        else str(f) for f in values))))
            if rows is None:
                summary.update(status='not_reported', reason=why)
            else:
                by, duplicates, unregistered, unknown_words, malformed = {}, [], [], set(), 0
                for r in rows:
                    if not r.get('entry'):
                        malformed += 1
                    elif r['entry'] not in known:
                        unregistered.append(r['entry'])
                    elif r['entry'] in by:
                        duplicates.append(r['entry'])
                    else:
                        # the canonical word and class from the one registry (canonical_of); the piece's word kept
                        r = dict(r)
                        r['canonical'], r['klass'], r['settled'], differs = canonical_of(
                            A99, r['entry'], str(r['disposition']), r.get('shared'), r.get('class'))
                        if r['klass'] == 'unclassified':
                            unknown_words.add(str(r['disposition']))
                        if differs:
                            integrity.append(dict(kind='field', piece=s['piece'], entry=r['entry'], detail=differs))
                        by[r['entry']] = r
                counts, shared_counts = {}, {}
                for r in by.values():
                    counts[str(r['disposition'])] = counts.get(str(r['disposition']), 0) + 1
                    shared_counts[str(r['canonical'])] = shared_counts.get(str(r['canonical']), 0) + 1
                per[s['piece']] = by
                summary.update(listed=len(by), counts=counts, shared_counts=shared_counts,
                               not_listed=[e for e in known if e not in by],
                               unregistered=unregistered, duplicates=duplicates, unknown_words=sorted(unknown_words),
                               malformed_rows=malformed, limit=s['doc'].get('limit'))
                for kind, values in (('unregistered entries', unregistered), ('duplicate entries', duplicates)):
                    if values:
                        integrity.append(dict(kind='piece', piece=s['piece'], detail='%s: %s' % (kind, listing(values))))
                if malformed:
                    integrity.append(dict(kind='piece', piece=s['piece'], detail='%d rows carry no entry id' % malformed))
                # the carried summary (frankie_box_all99_coverage.summary) counts the piece's own words (counts) and the
                # shared words (shared_counts): each compared with the same kind of count of the pinned list
                carried = s.get('summary') if isinstance(s.get('summary'), dict) else {}
                differ = {}
                for name, mine in (('counts', counts), ('shared_counts', shared_counts)):
                    recorded = carried.get(name)
                    if isinstance(recorded, dict) and {k: v for k, v in recorded.items() if v} != mine:
                        differ[name] = dict(carried_summary=recorded, list=mine)
                if differ:
                    summary['summary_vs_list'] = differ
        pieces.append(summary)
    doc = dict(schema=ALL99_JOIN_SCHEMA, day=str(day), join_sha256=join_sha256, inputs=inputs, pieces=pieces,
               lessons_source=lessons_source,
               rules=JOIN_RULES, finals_meaning=dict(FINALS), reach_refine=REACH_REFINE,
               class_source='the registry (frankie_box_all99_coverage): the shared field\'s disposition, else LEGACY_WORDS '
                            'of the piece\'s word, settled by FIXED_WORDS; class = WORD_CLASS of that canonical word; '
                            'REACH_REFINE reads the piece\'s own word',
               rule='diagnostic only, never knowledge: a recorded arrival is what the piece recorded, not proof that a '
                    'particular equation used the entry; missing lists read as unknown, never zero')
    # Frankie's 13 day-file points (additive): point-major, each with its declaration and every piece's own disposition
    point_rows = external_points_rows(points or {}, list(point_sources or [])) if point_sources else []
    decl = (point_sources or [None])[0]
    doc.update(external_points=point_rows,
               external_points_declaration=({k: decl.get(k) for k in ('status', 'reason', 'file', 'sha256', 'basis')}
                                            if decl else None),
               external_points_pieces=[{k: s.get(k) for k in ('piece', 'status', 'reason', 'file', 'sha256', 'basis')}
                                       for s in (point_sources or [])[1:]],
               external_points_unmapped=[r['point_id'] for r in point_rows if r.get('unmapped')],
               external_points_rule='one sub-row per day-file point under every 99 entry the day file maps it to; each '
                                    'piece\'s own recorded per-point word (presented / computed / context / searched / '
                                    'absent / missing, with its reason); not_reported where the piece records nothing per '
                                    'point (never inferred from its per-entry row); an unmapped point is listed apart')
    for ps in point_sources or []:
        if ps.get('status') == 'integrity':          # a visible failure of the piece's per-point record, listed once
            integrity.append(dict(kind='external_point', piece=ps['piece'], detail=ps.get('reason')))
    if A99 is None:
        doc.update(status='not_built', reason=registry_why, entries=[], finals={}, no_computation=[], disagreements=[],
                   integrity=integrity)
        return doc
    roles = A99.GROUP_ROLES
    entries, finals, disagreements = [], {}, []
    for n, (entry, group, policy) in enumerate(A99.REGISTRY, 1):
        role = roles.get(group)
        carried, not_listed = [], []
        for s in pieces:
            if s['piece'] not in per:
                continue
            r = per[s['piece']].get(entry)
            if r is None:
                not_listed.append(s['piece'])
                continue
            word = str(r['disposition'])
            carried.append(dict(piece=s['piece'], for_frankie=s['for_frankie'], disposition=word, canonical=r['canonical'],
                                reach=reach_of(word, r['klass']), klass=r['klass'], settled=r.get('settled'),
                                reason=r.get('reason'),
                                consumer=r.get('consumer'), count=r.get('count'), group=r.get('group')))
        frankie = [c for c in carried if c['for_frankie']]
        classroom = next((c for c in frankie if c['piece'] == 'classroom'), None)
        if classroom and classroom['reach'] == 'computation':
            final = 'classroom'
        elif classroom and classroom['reach'] == 'computation_thin':
            final = 'classroom_thin'
        elif any(c['reach'] in ('computation', 'computation_thin') for c in frankie):
            final = 'other_computation'
        elif any(c['reach'] in REACHED for c in frankie):
            final = 'consumer'
        elif any(c['reach'] == 'exposed' for c in frankie):
            final = 'exposed_only'
        elif frankie:
            final = 'nothing'
        else:
            final = 'unknown'
        finals[final] = finals.get(final, 0) + 1
        row = dict(n=n, entry=entry, group=group, policy=policy, role=role, carried=carried, not_listed_by=not_listed,
                   final=final, reached_by=['%s=%s' % (c['piece'], c['disposition']) for c in frankie if c['reach'] in REACHED],
                   computation=any(c['reach'] in ('computation', 'computation_thin') for c in frankie))
        for c in carried:
            if c['reach'] == 'integrity':
                integrity.append(dict(kind='entry', entry=entry, piece=c['piece'], detail=c['reason']))
        found = []
        other_groups = sorted({str(c['group']) for c in carried if c.get('group') and c['group'] != group})
        if other_groups:
            found.append(dict(rule='group', detail='%s list it under %s; the shared registry: %s' % (
                listing(c['piece'] for c in carried if c.get('group') and c['group'] != group), listing(other_groups), group)))
        lawful = [c for c in carried if c['reach'] in ('withheld', 'disabled', 'retired')]
        reached = [c for c in carried if c['reach'] in REACHED]
        if lawful and reached:
            found.append(dict(rule='lawful_role', detail='%s; while %s' % (
                listing('%s records %s' % (c['piece'], c['disposition']) for c in lawful),
                listing('%s records %s' % (c['piece'], c['disposition']) for c in reached))))
        if role in ('raw', 'calculation', 'clock'):
            root = next((c for c in carried if c['piece'] == 'root'), None)
            readers = [c for c in carried if c['piece'] in PICTURE_READERS]
            if root and root['reach'] == 'picture' and readers and all(c['reach'] == 'absent' for c in readers):
                found.append(dict(rule='picture_admitted_not_arrived', detail='the ROOT recorded %s; %s' % (
                    root['disposition'], listing('%s records %s' % (c['piece'], c['disposition']) for c in readers))))
            if root and root['reach'] == 'absent' and any(c['reach'] == 'computation' for c in readers):
                found.append(dict(rule='picture_arrived_not_admitted', detail='the ROOT recorded %s (%s); %s' % (
                    root['disposition'], rec(root['reason']), listing('%s records %s' % (c['piece'], c['disposition'])
                                                                     for c in readers if c['reach'] == 'computation'))))
        for f in found:
            disagreements.append(dict(entry=entry, **f))
        row['disagreements'] = found
        # the day-file points mapped to this entry: one sub-row each (additive; the entry's own row is unchanged)
        row['external_points'] = [dict(point_id=x['point_id'], name=x['name'], tables=x['tables'],
                                       mapping=x['mapping'], mapping_reason=x['mapping_reason'],
                                       event_time_basis=x['event_time_basis'], note=x['note'], pieces=x['pieces'])
                                  for x in point_rows if entry in (x.get('entries') or [])]
        entries.append(row)
    for s in pieces:
        if s.get('summary_vs_list'):
            disagreements.append(dict(entry=None, rule='summary_vs_list', piece=s['piece'], detail=listing(
                '%s: carried summary %s; the pinned list %s' % (name, json.dumps(v['carried_summary'], sort_keys=True),
                                                                json.dumps(v['list'], sort_keys=True))
                for name, v in sorted(s['summary_vs_list'].items()))))
    doc.update(status='built', registry=dict(module='frankie_box_all99_coverage', schema=getattr(A99, 'SCHEMA', None),
                                             registry_sha256=getattr(A99, 'REGISTRY_SHA256', None),
                                             crosswalk_sha256=getattr(A99, 'CROSSWALK_SHA256', None),
                                             entries=len(A99.REGISTRY)),
               entries=entries, finals=finals, no_computation=[e['entry'] for e in entries if not e['computation']],
               disagreements=disagreements, integrity=integrity)
    return doc


def all99_summary(join):
    """The compact projection the receipt's workflow report carries (the full join is receipt['all99'])."""
    return dict(schema=ALL99_JOIN_SCHEMA + '_SUMMARY', status=join.get('status'), join_sha256=join.get('join_sha256'),
                pieces={p['piece']: dict(status=p['status'], listed=p.get('listed'), reason=p['reason'] if p['status'] != 'read' else None)
                        for p in join.get('pieces') or []},
                lessons_basis=(join.get('lessons_source') or {}).get('basis'),
                lessons_current=(join.get('lessons_source') or {}).get('current'),
                finals=join.get('finals'), no_computation=len(join.get('no_computation') or []),
                external_points={str(x['point_id']): {c['piece']: c.get('disposition') for c in x['pieces']}
                                 for x in join.get('external_points') or []},
                external_points_unmapped=join.get('external_points_unmapped'),
                disagreements=len(join.get('disagreements') or []), integrity=len(join.get('integrity') or []))


def all99_lines(d):
    """The FRANKIE report's section: fixed templates over the join; paths and hashes stay in the Evidence section."""
    j = d.all99
    L = ['## The 99 layers (what reached Frankie today)', '',
         'Every one of the 99 registry entries, joined from each piece\'s own recorded all-99 list (each list read once, '
         'never recomputed). Diagnostic only; never knowledge. A recorded arrival is what the piece recorded; it is not '
         'proof that a particular equation used the entry. A piece that recorded no list is "not reported" (unknown, '
         'never zero).', '']
    L += table(['piece', 'reaches Frankie', 'status', 'entries listed', 'words recorded (counts as recorded)'],
               [(p['piece'], 'yes' if p['for_frankie'] else 'no (listed only)', p['status'], rec(p.get('listed')),
                 listing('%s %s' % (k, v) for k, v in sorted((p.get('counts') or {}).items())) if p.get('counts') else '-')
                for p in j['pieces']]) + ['']
    for p in j['pieces']:
        if p['status'] == 'not_reported':
            L.append('- Not reported by %s: %s.' % (p['piece'], rec(p['reason'])))
        elif p['status'] == 'integrity':
            L.append('- INTEGRITY FAILURE at %s (separate, visible; not a missing-data disposition): %s.' % (p['piece'], rec(p['reason'])))
        elif p.get('not_listed'):
            L.append('- %s listed %s of the 99 entries; not listed by it: %s.' % (p['piece'], rec(p.get('listed')),
                                                                                 listing(p['not_listed'])))
        if p.get('unknown_words'):
            L.append('- %s recorded words this report\'s table does not group (shown as recorded, grouped unclassified): %s.'
                     % (p['piece'], listing(p['unknown_words'])))
    ls = j.get('lessons_source') or {}
    if ls:
        L.append('- The scientific teacher\'s lessons list (%s): %s.' % (
            'current: the lesson inputs the exchange itself recorded' if ls.get('current') else
            'MAY BE STALE: not the exchange\'s own record' if ls.get('basis') else 'none', rec(ls.get('origin'))))
    L.append('')
    for p in j['pieces']:
        if p.get('limit'):
            L += ['The %s recorded this limit on its list: %s' % (p['piece'], p['limit']), '']
    if j.get('status') != 'built':
        return L + ['The per-entry join is not built: %s.' % rec(j.get('reason')), '']
    L += ['Final for Frankie (counts of entries): %s.' % listing('%s %d' % (k, j['finals'].get(k, 0)) for k, _ in FINALS), '']
    L += ['- %s: %s.' % (k, meaning) for k, meaning in FINALS] + ['']
    read = [p['piece'] for p in j['pieces'] if p['status'] == 'read' and p.get('counts') is not None]
    rows = []
    for e in j['entries']:
        words = {c['piece']: c['disposition'] if c.get('canonical') in (None, c['disposition']) else
                 '%s (%s)' % (c['disposition'], c['canonical']) for c in e['carried']}
        rows.append([e['n'], e['entry'], rec(e['role'])] + [words.get(p, 'not listed') for p in read]
                    + [e['final'], listing(e['reached_by'])])
    L += ['### The 99 entries', '']
    L += table(['#', 'entry', 'role'] + read + ['final for Frankie', 'reached (Frankie pieces)'], rows) + ['']
    L += external_points_lines(j)
    L += ['### Entries that reached no computation (every piece\'s recorded word and reason)', '',
          'Entries no Frankie piece recorded in a computation: %d.' % len(j['no_computation']), '']
    for e in j['entries']:
        if e['computation']:
            continue
        parts = ['%s: %s (%s%s)%s%s' % (c['piece'], c['disposition'],
                                        '' if c.get('canonical') in (None, c['disposition']) else c['canonical'] + ', ',
                                        c['reach'], (': ' + str(c['reason'])) if c.get('reason') else '',
                                        ('; ' + c['settled']) if c.get('settled') else '') for c in e['carried']]
        L.append('- %s (%s; final %s). %s%s' % (
            e['entry'], rec(e['role']), e['final'], '; '.join(parts) if parts else 'No piece listed it',
            ('. Not listed by: ' + listing(e['not_listed_by'])) if e['not_listed_by'] else ''))
    L += ['', '### Disagreements between pieces', '', 'Recorded under the fixed rules: %d.' % len(j['disagreements']), '']
    L += ['- %s%s: %s.' % (x['rule'], (' (entry %s)' % x['entry']) if x.get('entry') else (' (piece %s)' % x.get('piece')),
                          x['detail']) for x in j['disagreements']]
    L += ['', '### Integrity (separate visible failures)', '']
    L += ['- %s: %s.' % (x.get('piece') or x.get('entry') or x['kind'], x['detail']) for x in j['integrity']] or ['None recorded.']
    return L + ['', 'The join rules (fixed text): %s.' % JOIN_RULES, '']


def external_points_lines(j):
    """Frankie's 13 day-file points under their 99 entries: one sub-row per point under each mapped entry, each piece's
    own recorded word (fixed templates; paths and hashes stay in the Evidence section)."""
    points = j.get('external_points') or []
    decl = j.get('external_points_declaration') or {}
    L = ['### Frankie\'s 13 points under their 99 entries', '',
         'Each day-file point sits under every 99 entry the day file maps it to (mapping, reason, event-time basis as the '
         'day file declares them; declaration %s: %s). Each piece\'s word is its own recorded per-point disposition; '
         '"not_reported" means the piece records nothing per point (never inferred).' % (rec(decl.get('status')),
                                                                                          rec(decl.get('reason'))), '']
    if not points:
        return L + ['No point is declared for this day.', '']
    pieces = [c['piece'] for c in points[0]['pieces']]
    rows = []
    for e in j.get('entries') or []:
        for x in e.get('external_points') or []:
            words = {c['piece']: c.get('disposition') for c in x['pieces']}
            rows.append([e['n'], e['entry'], 'point %s %s' % (x['point_id'], rec(x.get('name'))), listing(x.get('mapping')),
                         listing(x.get('event_time_basis'))] + [rec(words.get(p)) for p in pieces])
    L += table(['#', 'entry', 'point', 'mapping', 'event-time basis'] + pieces, rows) + ['']
    for x in points:
        L.append('- Point %s (%s): entries %s; mapping %s: %s; tables %s. %s' % (
            x['point_id'], rec(x.get('name')), listing(x.get('entries')), listing(x.get('mapping')),
            listing(x.get('mapping_reason')), listing(x.get('tables')),
            '; '.join('%s %s%s' % (c['piece'], rec(c.get('disposition')), (' (%s)' % c['reason']) if c.get('reason') else '')
                      for c in x['pieces'])))
    unmapped = j.get('external_points_unmapped') or []
    if unmapped:
        L.append('- Unmapped points (the day file declares no 99 entry; listed, never guessed): %s.' % listing(unmapped))
    return L + ['']


# ------------------------------------------------------------------------------------------------- the exchange section
def exchange_lines(d, with_frankie):
    """The three-way exchange, translated field by field (both reports; the FRANKIE report adds his turn per item)."""
    L = ['## The three-way exchange', '']
    x = d.exchange
    if x is None:
        return L + ['Not recorded: %s.' % (d.exchange_listed or 'no exchange was given for this day'), ''] + meeting_lines(d, with_frankie)
    c = x.get('counts') or {}
    fmt = lambda m: listing('%s %s' % (k, v) for k, v in sorted((m or {}).items()))
    L += ['Items discussed (recorded): %s (by author: %s). The BOSS teacher\'s positions: %s. The scientific teacher\'s '
          'positions: %s. Frankie\'s resolutions: %s. The teachers\' own findings: %s (by kind: %s).' % (
              rec(c.get('items')), fmt(c.get('by_author')), fmt(c.get('boss_positions')), fmt(c.get('science_positions')),
              fmt(c.get('frankie_resolutions')), rec(c.get('teachers_findings')), fmt(c.get('teachers_findings_by_kind'))), '']
    if x.get('sources', {}).get('teacher_rows_listed'):
        L += ['The BOSS teacher\'s rows (recorded): %s.' % x['sources']['teacher_rows_listed'], '']
    if isinstance(x.get('teacher_second_set_read'), dict):
        import frankie_box_teacher_rows as TR
        L += ['The teacher\'s second set, as both teacher seats read it (recorded on each seat\'s turn): %s.' %
              TR.reading_sentence(x['teacher_second_set_read']), '']
    for item in x.get('items') or []:
        claim = item.get('claim') or {}
        L += ['### Item %s (%s)' % (item.get('item_id'), rec(item.get('author_label'))), '',
              '- The claim, as recorded: %s. Claimed direction (recorded): %s. Days tested (recorded): %s. The scientific '
              'teacher\'s disposition word (recorded; orientation only): %s.' % (
                  rec(claim.get('statement')), rec(claim.get('direction')), listing(claim.get('days_tested')),
                  rec(claim.get('disposition')))]
        for t in item.get('turns') or []:
            if t.get('seat') == 'frankie' and not with_frankie:
                continue
            who = {'boss_teacher': 'the BOSS teacher', 'scientific_teacher': 'the scientific teacher',
                   'frankie': 'Frankie'}.get(t.get('seat'), rec(t.get('seat')))
            if t.get('withheld'):
                L.append('- Turn %s, %s: withheld. Recorded reason: %s' % (rec(t.get('turn')), who, rec(t.get('reason'))))
                continue
            r = t.get('record') or {}
            L.append('- Turn %s, %s (%s): position %s. Recorded reasoning: %s' % (
                rec(t.get('turn')), who, rec(t.get('author_label')), rec(r.get('position')), rec(r.get('reasoning'))))
            for chk in r.get('evidence_checks') or []:
                L.append('  - Check, result %s (recorded): %s' % (rec(chk.get('result')), rec(chk.get('check'))))
            if t.get('seat') == 'frankie':
                L.append('  - His resolution (recorded): %s. His corrected understanding, as recorded: %s' % (
                    rec(t.get('resolution')), rec(t.get('corrected_understanding'))))
                held = t.get('remaining_disagreements') or []
                L += ['  - Disagreement he still holds, as recorded: %s' % z for z in held] or [
                    '  - Disagreement he still holds, as recorded: none']
                L += ['  - What he learned, as recorded: %s' % z for z in r.get('learned') or []]
            for z in r.get('next_tests') or r.get('next_steps') or []:
                L.append('  - Next (recorded): %s' % z)
        L.append('')
    findings = x.get('teachers_findings') or []
    L += ['### The teachers\' own findings', '', 'Recorded: %d.' % len(findings), '']
    for f in findings:
        L.append('- %s (kind recorded: %s; days named: %s; status recorded: %s): %s' % (
            rec(f.get('finding_id')), rec(f.get('kind')), listing(f.get('days_named')), rec(f.get('status')),
            rec(f.get('statement'))))
    if findings:
        L.append('')
    withheld = x.get('jev_withheld')
    if withheld:
        L += ['Jev\'s items withheld from Frankie\'s view (recorded): %s items, %s findings. Recorded reason: %s' % (
            rec(withheld.get('items')), rec(withheld.get('findings')), rec(withheld.get('reason'))), '']
    return L + meeting_lines(d, with_frankie)


def meeting_record_lines(value):
    """The recorded fields, without clipping, interpretation or combining items; safe Markdown even for code in text."""
    text = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False)
    fence = '`' * max(3, 1 + max((len(m.group()) for m in re.finditer(r'`+', text)), default=0))
    return [fence + 'json', text, fence, '']


def meeting_lines(d, with_frankie):
    L = ['### The discussion (meeting)', '']
    if not with_frankie:
        return L + ["Withheld here: the meeting contains Frankie's discussion and appears only in his report.", '']
    meeting = d.meeting
    L += ['Recorded status: %s. Discussion has no evidentiary authority; the original code-seat evidence remains '
          'authoritative. Requested tests are requests, not executed tests or results.' % meeting['status'], '']
    record = meeting.get('record') or {}
    if meeting['status'] != 'complete':
        L += ['No completed discussion: %s.' % (meeting.get('reason') or meeting['status']), '']
        return L + meeting_record_lines(dict(refused_to_run=record.get('refused_to_run') or []))
    categories = (('Seat statements', ('seat_statements',)),
                  ('Coordinator turns (coordination only)', ('coordinator_turns',)),
                  ('Code-seat answers', ('code_seat_answers',)),
                  ('Open items and requested tests (not results)', ('open_items', 'requested_tests')))
    for item in record['items']:
        L += ['#### Discussion item %s' % rec(item.get('item_id')), '']
        for label, keys in categories:
            L += ['**%s**' % label, ''] + meeting_record_lines({k: item.get(k) for k in keys})
        category_keys = {k for _, keys in categories for k in keys}
        L += ['**Other recorded item fields (including outcome, notes and refusals)**', '']
        L += meeting_record_lines({k: v for k, v in item.items() if k not in category_keys})
    L += ['#### Items not discussed (retained, including their open items)', '']
    L += meeting_record_lines(record.get('not_discussed') or [])
    L += ['#### Other recorded meeting fields', '']
    L += meeting_record_lines({k: v for k, v in record.items() if k not in ('items', 'not_discussed')})
    return L


# ------------------------------------------------------------------------------------------------------ the evidence
def evidence(d, with_frankie=False):
    L = ['## Evidence', '', '- classroom directory: %s' % d.dir,
         '- built from: %s%s, sha256 %s' % (d.source['kind'], ' %s' % d.source['path'] if d.source['path'] else '',
                                             d.source['sha256'])]
    r = d.receipt
    ext = r.get('external') or {}
    carried = r.get('carried_from_previous') if isinstance(r.get('carried_from_previous'), dict) else {}
    for label, value in (('completion hash', r.get('completion_hash')),
                         ('external completion hash', ext.get('completion_hash')),
                         ('external key hash', ext.get('external_key_hash')),
                         ('day file', (ext.get('day_file') or {}).get('path')),
                         ('day file sha256', (ext.get('day_file') or {}).get('sha256')),
                         ('teacher rows', r.get('teacher_rows')),
                         ('experiment directive sha256', (r.get('experiment_directive') or {}).get('sha256')),
                         ('classroom rules sha256', (r.get('classroom_rules') or {}).get('sha256')),
                         ('Jev material', (r.get('jev_material') or {}).get('path')),
                         ('previous classroom history sha256', carried.get('history_sha256')),
                         ('brain entry', r.get('brain_entry')),
                         ('brain MANIFEST sha256', (d.brain or {}).get('manifest_sha256'))):
        if value:
            L.append('- %s: %s' % (label, value))
    if d.exchange is not None:
        L.append('- the three-way exchange: %s, sha256 %s' % (d.exchange_path, d.exchange_sha256))
    if with_frankie and d.meeting.get('path'):
        L.append('- the discussion record (%s): %s, sha256 %s; verified against its receipt and Frankie exchange' % (
            d.meeting['status'], d.meeting['path'], d.meeting_sha256))
    if d.school_path:
        L.append('- the school file (%s, status %s): %s, sha256 %s, bytes %s' % (
            d.school_kind, d.school_status, d.school_path, d.school_sha256, d.school_bytes))
        if d.school_row:
            L.append('- the school index row: file %s, sha256 %s, bytes %s, report number %s' % (
                d.school_row.get('file'), d.school_row.get('sha256'), d.school_row.get('bytes'),
                d.school_row.get('report_number')))
    else:
        L.append('- no school file was given: %s' % d.school_listed)
    if with_frankie and getattr(d, 'all99', None):
        L.append('- the 99-layer join: %d piece lists named, %d read; join sha256 %s' % (
            len(d.all99.get('pieces') or []), sum(1 for p in d.all99.get('pieces') or [] if p['status'] == 'read'),
            d.all99_sha256))
        L += ['  - %s: %s, sha256 %s' % (p['piece'], p['file'], p['sha256'])
              for p in d.all99.get('pieces') or [] if p.get('file')]
    L.append('- files read by this step: %d (each with bytes and sha256 on the step\'s receipt)' % len(d.inputs))
    if d.absent:
        L += ['- files not found or not readable (each section above states what is not recorded):']
        L += ['  - %s: %s' % (name, why) for name, why in d.absent]
    elif d.status == 'complete':
        L.append('- every classroom output these reports read was present')
    else:
        L.append('- a refused day writes only its receipt; nothing else was read')
    return L + ['']


# --------------------------------------------------------------------------------------- numbering, index and writing
def read_index(reports):
    path = reports / 'index.json'
    if not path.is_file():
        return dict(schema=INDEX_SCHEMA, days=[], reports=[])
    index = json.loads(path.read_bytes())
    if index.get('schema') != INDEX_SCHEMA:
        raise SystemExit('%s is not a %s index; refused' % (path, INDEX_SCHEMA))
    index.setdefault('days', [])
    index.setdefault('reports', [])
    return index


def write_index(reports, index):
    tmp = reports / 'index.json.pending'
    tmp.write_text(json.dumps(index, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, reports / 'index.json')


def day_number(reports, index, run, day):
    """(number, assigned now?): the (run, day) entry's number, or 1 + the highest day number in the index or in any
    report file name in the reports dir."""
    for entry in index['days']:
        if entry['run'] == run and entry['day'] == day:
            return entry['number'], False
    used = [e['number'] for e in index['days']] + [int(m.group(2)) for p in reports.iterdir()
                                                    for m in [FILE_RE.match(p.name)] if m]
    return (max(used) if used else 0) + 1, True


def reserve_number(reports, run_name, day, number=None):
    """The day's report number N, assigned now or already there, under the same lock and rule as run() (the orchestrator
    reserves it right after the day's classroom step, so the Jev Pod dispatch carries it and the numbering is unchanged
    now that the reports follow the exchange). Returns (number, assigned now?).
    number (Frankie's class line, frankie_box_frankie_queue.py; Greg, 2026-09-29: "Class days are sequential"): the
    day's SCHOOL-DAY number, which N must equal. A day already holding another N, or an N another day holds, refuses
    (SystemExit): a number is never given to two days and a day is never renumbered."""
    reports = Path(reports)
    reports.mkdir(parents=True, exist_ok=True)
    with open(reports / '.lock', 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        index = read_index(reports)
        have, new_day = day_number(reports, index, run_name, day)
        if number is not None:
            if not new_day and have != number:
                raise SystemExit('%s %s holds report number %d already; its school day is %d (never renumbered)'
                                 % (run_name, day, have, number))
            if new_day:
                taken = [e for e in index['days'] if e['number'] == number] + \
                        [p.name for p in reports.iterdir() for m in [FILE_RE.match(p.name)] if m and int(m.group(2)) == number]
                if taken:
                    raise SystemExit('report number %d (the school day of %s %s) is held already: %s' % (
                        number, run_name, day, taken))
                have = number
        if new_day:
            index['days'].append(dict(run=run_name, day=day, number=have, at=time.time(),
                                      commit=os.environ.get('MARKETS_SHA'),
                                      reserved_by='orchestrator after the classroom' if number is None else
                                      'frankie class line: school day %d' % number,
                                      **({} if number is None else dict(school_day=number))))
            write_index(reports, index)
    return have, new_day


def file_name(kind, number, revision):
    return '%s-report-%04d%s.md' % (kind, number, '' if revision == 1 else '-r%d' % revision)


KEPT_EXISTING = 'kept the existing report'


def write_new(path, raw):
    """Write bytes to a new file (never overwrite): (True, None), (True, why) when the file is already there (same
    bytes, or other bytes: the saved report is KEPT, never refused and never overwritten; Greg, 2026-10-09: a save is
    never refused because the code that renders it changed; the caller reads the kept bytes back) or (False, why)."""
    try:
        with open(path, 'xb') as f:
            f.write(raw)
        return True, None
    except FileExistsError:
        if Path(path).read_bytes() == raw:
            return True, 'already there with the same bytes'
        return True, '%s: %s exists with other bytes (never overwritten; this render is not used)' % (KEPT_EXISTING, path)
    except OSError as error:
        return False, '%s: %s' % (type(error).__name__, error)


# ---------------------------------------------------------------------------- side by side + save points (stacks pass)
# Stacks pass (2026-10-07 night, session 5; the Sept-29 templates: pieces side by side, exact saves at boundaries).
# The two numbered reports of a day are independent translations of the same Day (read once, hashed once in Day): they
# are rendered side by side on pinned fork workers of the booked lane (frankie_box_lane_pin.ordered_map: placement from
# the lane, ordered hand-off, a dead worker's report redone with one fewer, the coordinator renders it after the third
# loss), and each written report is a save point: <reports>/receipts/<run>/<day>.reports-save.json names every report
# already written for this number, revision and these exact inputs, so a stopped step resumes at the next report
# (the written report is re-read once and hash-checked, never re-rendered). The text is the same function of the same
# Day either way: bytes, file names, numbering and the index rows are those of the serial path.
# FRANKIE_REPORTS_SIDE_BY_SIDE=off renders in-process one after the other (the earlier path).
SAVE_SCHEMA = 'FRANKIE_DAY_REPORTS_SAVE_V1'
_RENDER = {}


def _render_one(kind):
    """One report's lines from the Day the coordinator built before the fork (module state, read-only here)."""
    d, number, revision, run_name, cls, files = _RENDER['args']
    if kind == 'classroom':
        return classroom_report(d, number, revision, run_name, cls, files['frankie'])
    if kind == 'teacher':
        return teacher_report(d, number, revision, run_name, cls, files)
    if kind == 'root':
        return root_report(d, number, revision, run_name, cls, files)
    return frankie_report(d, number, revision, run_name, cls, files['classroom'])


def _render_job(kind):
    """The worker side: ('ok', lines) or ('error', text). A rendering error is returned (the coordinator re-renders that
    report in-process, so the real exception and traceback surface there), never confused with a lost worker. A forked
    worker never keeps the coordinator's mark-only SIGTERM handler (the a2 shard hang): default here, and the handler
    itself ends any process that is not the coordinator."""
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    try:
        return 'ok', _render_one(kind)
    except Exception as error:  # noqa: BLE001 - re-raised in the coordinator by rendering again
        return 'error', '%s: %s' % (type(error).__name__, error)


def render_side_by_side(kinds, args, record):
    """Yield (kind, lines) in the order of kinds; side by side on the lane when there are two or more to render and the
    lane has two or more CPUs, else in-process. record gets mode, reason, the CPU map (lane_pin.record) and the pool
    recovery (worker_deaths, redone); a pool that cannot start, or dies, continues in-process for the rest."""
    _RENDER['args'] = args
    kinds = list(kinds)
    record.update(mode='in-process, one after the other', kinds=kinds, pool_recovery=None, cpu_placement=None)
    LP, why = None, None
    if len(kinds) < 2:
        why = 'one report or none to render'
    elif os.environ.get('FRANKIE_REPORTS_SIDE_BY_SIDE', 'on') == 'off':
        why = 'FRANKIE_REPORTS_SIDE_BY_SIDE=off'
    else:
        try:
            try:
                import frankie_box_lane_pin as LP
            except ImportError:
                from deploy.aws.box import frankie_box_lane_pin as LP
            if len(LP.lane_cpus()) < 2:
                why, LP = 'the lane has one CPU', None
        except Exception as error:  # noqa: BLE001 - placement is never a reason to stop; listed
            why, LP = 'the pin helper is unavailable (%s: %s)' % (type(error).__name__, error), None
    done = []
    if LP is not None:
        recovery = dict(worker_deaths=[], redone=[])
        record.update(mode='side by side on pinned fork workers', pool_recovery=recovery,
                      cpu_placement=LP.record(len(kinds), what='day reports: one worker per numbered report'))
        try:
            for kind, (status, value) in LP.ordered_map(_render_job, kinds, len(kinds), window=len(kinds),
                                                         report=recovery, fallback=_render_job):
                done.append(kind)
                yield kind, (value if status == 'ok' else _render_one(kind))
        except GeneratorExit:
            raise
        except Exception as error:  # noqa: BLE001 - the pool itself failed: the rest in-process, listed
            if any(k not in done for k in kinds) and not isinstance(error, (SystemExit, KeyboardInterrupt)):
                record['pool_failure'] = '%s: %s (the reports not yet yielded were rendered in-process)' % (
                    type(error).__name__, error)
            else:
                raise
    else:
        record['reason'] = why
    for kind in kinds:
        if kind not in done:
            yield kind, _render_one(kind)


# THE SAVE REQUEST ROUTE (ROOT's contract, frankie_box_experiment_root.calculate_day): the queue's save marker
# (FRANKIE_LANE_STOP_FILE) or SIGTERM MARKS the save; the step runs on to the next report boundary, whose save point is
# already on disk, and exits 75 (never a failure or a requeue). A save requested after the last report is not a
# boundary: the step completes (index and receipt) and exits as usual.
SAVED_EXIT = 75
_SAVE = dict(requested=False, coordinator=None, stop_file=None)


def _mark_save(signum, frame):
    if os.getpid() != _SAVE['coordinator']:
        os._exit(128 + signum)                  # a forked child: the default action, never a mark-only hang
    _SAVE['requested'] = True


def save_requested():
    return _SAVE['requested'] or bool(_SAVE['stop_file'] and Path(_SAVE['stop_file']).exists())


def _code_sha256():
    """The templates' code identity in a save point: this file's bytes (every report template lives here). RECORDED,
    NEVER COMPARED (Greg, 2026-10-09): a save under other code is reused like any other (load_save compares the inputs,
    number and revision only), and an existing report is kept (write_new)."""
    return sha256_bytes(Path(__file__).resolve().read_bytes())


SAVE_RECORDED_CODE = ('code_sha256',)


def _compared_save_identity(identity):
    """A save-point identity without its recorded-only code field."""
    if not isinstance(identity, dict):
        return identity
    return {k: v for k, v in identity.items() if k not in SAVE_RECORDED_CODE}


def _save_path(reports, run_name, day):
    return Path(reports) / 'receipts' / str(run_name) / ('%s.reports-save.json' % day)


def _save_identity(d, number, revision):
    return dict(number=number, revision=revision, code_sha256=_code_sha256(),
                source_sha256=d.source['sha256'], exchange_sha256=d.exchange_sha256,
                meeting_sha256=d.meeting_sha256, meeting_status=d.meeting['status'], school_sha256=d.school_sha256,
                school_status=d.school_status, all99_sha256=d.all99_sha256, teacher_sha256=d.teacher_sha256,
                root_sha256=d.root_sha256)


def load_save(reports, run_name, day, identity):
    """{kind: saved write} of a save point for exactly this number, revision and inputs, else {} (with why)."""
    path = _save_path(reports, run_name, day)
    if not path.is_file():
        return {}, None
    try:
        save = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        return {}, 'the save point %s is unreadable (%s); every report is rendered' % (path, error)
    if save.get('schema') != SAVE_SCHEMA or _compared_save_identity(save.get('identity')) != _compared_save_identity(identity):
        return {}, 'the save point %s is for other inputs or another number/revision; every report is rendered' % path
    return dict(save.get('written') or {}), None


def write_save(reports, run_name, day, identity, written):
    path = _save_path(reports, run_name, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.pending')
    tmp.write_text(json.dumps(dict(schema=SAVE_SCHEMA, run=run_name, day=day, identity=identity, written=written,
                                   at=time.time()), indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def run(day, classroom, run_name, reports, cls, refused_reason, exchange=None, exchange_listed=None, *, return_receipt=False,
        school=None, school_listed=None, run_dir=None, piece_receipts=None):
    """The step (see the module note); the save request route marks a save for the duration (ROOT's contract)."""
    _SAVE.update(requested=False, coordinator=os.getpid(), stop_file=os.environ.get('FRANKIE_LANE_STOP_FILE'))
    try:
        previous = signal.signal(signal.SIGTERM, _mark_save)
    except ValueError:                          # not the main thread: the stop file alone marks a save
        previous = None
    try:
        return _run(day, classroom, run_name, reports, cls, refused_reason, exchange, exchange_listed,
                    return_receipt=return_receipt, school=school, school_listed=school_listed, run_dir=run_dir,
                    piece_receipts=piece_receipts)
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


def _run(day, classroom, run_name, reports, cls, refused_reason, exchange=None, exchange_listed=None, *, return_receipt=False,
         school=None, school_listed=None, run_dir=None, piece_receipts=None):
    started = time.monotonic()
    d = Day(day, classroom, refused_reason, exchange, exchange_listed, school, school_listed)
    d.load_pieces(Path(run_dir) if run_dir else RUNS / run_name)
    timings = dict(read_inputs=round(time.monotonic() - started, 6))
    # the 99 layers: every piece's recorded list read once (pinned files checked), then joined; no recomputation
    collect_all99(d, run_name, Path(run_dir) if run_dir else RUNS / run_name, dict(piece_receipts or {}))
    d.all99 = all99_join(day, d.all99_sources, d.all99_problems, d.all99_lessons_source,
                         point_sources=d.all99_point_sources, points=d.all99_points)
    d.all99_sha256 = d.all99['join_sha256']
    timings['all99_join'] = round(time.monotonic() - started - timings['read_inputs'], 6)
    try:                                     # the stage heartbeat (frankie_box_stage_progress); never changes the stage
        import frankie_box_stage_progress as _SP
        _SP.report_phase('reports: inputs read and 99-layer join built', units_done=1, units_total=2, unit='boundaries')
    except Exception:  # noqa: BLE001
        pass
    reports.mkdir(parents=True, exist_ok=True)
    out, printed, problems = [], [], list(d.school_problems)
    reuse_why = None
    rendering = dict(mode='not rendered: the existing reports were reused')   # additive receipt field (stacks pass)
    with open(reports / '.lock', 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        index = read_index(reports)
        number, new_day = day_number(reports, index, run_name, day)
        if new_day:     # recorded before any report is written, so a stopped step keeps the day's number
            index['days'].append(dict(run=run_name, day=day, number=number, at=time.time(),
                                      commit=os.environ.get('MARKETS_SHA')))
            write_index(reports, index)
        mine = {k: [r for r in index['reports'] if r['run'] == run_name and r['day'] == day and r['kind'] == k]
                for k in KINDS}
        latest = {k: (mine[k][-1] if mine[k] else None) for k in KINDS}
        match = {k: dict(source=bool(latest[k]) and latest[k]['source_sha256'] == d.source['sha256'],
                         exchange=bool(latest[k]) and latest[k].get('exchange_sha256') == d.exchange_sha256,
                         meeting=bool(latest[k]) and latest[k].get('meeting_sha256') == d.meeting_sha256
                                 and latest[k].get('meeting_status') == d.meeting['status'],
                         school=bool(latest[k]) and latest[k].get('school_sha256') == d.school_sha256
                                and latest[k].get('school_status', 'not given') == d.school_status,
                         all99=bool(latest[k]) and latest[k].get('all99_sha256') == d.all99_sha256,
                         teacher=bool(latest[k]) and latest[k].get('teacher_sha256') == d.teacher_sha256,
                         root=bool(latest[k]) and latest[k].get('root_sha256') == d.root_sha256)
                 for k in KINDS}
        reuse = all(all(m.values()) for m in match.values())
        reuse_why = ('the existing reports were built from the same classroom receipt, exchange, meeting, school file and '
                     'pieces\' all-99 lists'
                     if reuse else 'no earlier reports for this run and day' if not any(latest.values()) else
                     'rebuilt as a revision: changed since the last build: ' + listing(
                         sorted({name for m in match.values() for name, same in m.items() if not same})))
        if reuse:
            for k in KINDS:
                path = Path(latest[k]['file'])
                raw = path.read_bytes() if path.is_file() else None
                matches = raw is not None and sha256_bytes(raw) == latest[k]['sha256']
                if not matches:
                    problems.append('%s differs from the index or is gone (sha256 %s in the index)' % (path, latest[k]['sha256']))
                if raw is not None and latest[k].get('classroom_copy') and not Path(latest[k]['classroom_copy']).is_file():
                    written, why = write_new(latest[k]['classroom_copy'], raw)
                    if not written:
                        problems.append(why)
                printed.append((k, raw.decode('utf-8', errors='replace') if raw is not None else
                                '(%s: the report file is gone; the index names sha256 %s)' % (path, latest[k]['sha256'])))
                out.append(dict(kind=k, number=number, revision=latest[k].get('revision', 1), file=str(path),
                                classroom_copy=latest[k].get('classroom_copy'), sha256=latest[k]['sha256'],
                                existing=True, matches_index=matches))
        else:
            revision = 1 + max([r.get('revision', 1) for k in KINDS for r in mine[k]] or [0])
            files = {k: file_name(k, number, revision) for k in KINDS}
            identity = _save_identity(d, number, revision)
            saved, save_why = load_save(reports, run_name, day, identity)
            rendering['save_point'] = str(_save_path(reports, run_name, day))
            rendering['save_listed'] = save_why
            resumed = {}
            for k in KINDS:            # a report written before a stop: re-read once, hash-checked, never re-rendered
                entry = saved.get(k)
                central = reports / files[k]
                if isinstance(entry, dict) and central.is_file():
                    raw = central.read_bytes()
                    if sha256_bytes(raw) == entry.get('sha256') and len(raw) == entry.get('bytes'):
                        resumed[k] = raw
            rendering['resumed_from_save'] = sorted(resumed)
            written_so_far = {k: saved[k] for k in resumed}
            rendered = render_side_by_side([k for k in KINDS if k not in resumed],
                                           (d, number, revision, run_name, cls, files), rendering)
            for k in KINDS:
                if k in resumed:
                    raw = resumed[k]
                else:
                    kind, lines = next(rendered)
                    assert kind == k, 'reports are handed over in KINDS order'
                    raw = ('\n'.join(lines).rstrip('\n') + '\n').encode('utf-8')
                central = reports / files[k]
                written, why = write_new(central, raw)
                if not written:
                    raise SystemExit('the %s report %s could not be written: %s' % (k, central, why))
                if why and why.startswith(KEPT_EXISTING):
                    raw = central.read_bytes()     # the saved report stands; everything below names its bytes
                    rendering.setdefault('kept_existing', []).append(dict(kind=k, file=str(central), why=why))
                if k not in resumed:   # the save point after each report (the Sept-29 exact save at a boundary)
                    written_so_far[k] = dict(file=str(central), sha256=sha256_bytes(raw), bytes=len(raw))
                    try:
                        write_save(reports, run_name, day, identity, written_so_far)
                    except OSError as error:
                        problems.append('the save point could not be written: %s: %s' % (type(error).__name__, error))
                try:                   # the heartbeat continues from the saved cursor: resumed reports count as done
                    import frankie_box_stage_progress as _SP
                    _SP.report_phase('reports: %s report written' % k, units_done=len(written_so_far),
                                     units_total=len(KINDS), unit='reports', resumed=sorted(resumed))
                except Exception:  # noqa: BLE001
                    pass
                if save_requested() and len(written_so_far) < len(KINDS):
                    rendering['saved_at'] = sorted(written_so_far)
                    print('SAVED reports %s %s: %s written, the save point %s resumes at the next report' % (
                        run_name, day, ', '.join(sorted(written_so_far)), _save_path(reports, run_name, day)), flush=True)
                    raise SystemExit(SAVED_EXIT)
                copy, copy_why = None, None
                if d.dir.is_dir():
                    copy = str(d.dir / files[k])
                    copied, copy_why = write_new(copy, raw)
                    if not copied:
                        problems.append(copy_why)
                        copy = None
                else:
                    copy_why = 'the classroom directory %s does not exist; the report is in the reports dir only' % d.dir
                superseded = latest[k]['file'] if latest[k] else None
                entry = dict(run=run_name, day=day, kind=k, number=number, revision=revision, file=str(central),
                             classroom_copy=copy, classroom_copy_listed=copy_why, sha256=sha256_bytes(raw),
                             bytes=len(raw), source=d.source['kind'], source_sha256=d.source['sha256'],
                             classroom=str(d.dir), classroom_status=d.status, supersedes=superseded, at=time.time(),
                             commit=os.environ.get('MARKETS_SHA'), exchange_sha256=d.exchange_sha256,
                             meeting_sha256=d.meeting_sha256, meeting_status=d.meeting['status'],
                             school=d.school_path, school_sha256=d.school_sha256, school_status=d.school_status,
                             all99_sha256=d.all99_sha256, teacher_sha256=d.teacher_sha256,
                             root_sha256=d.root_sha256)
                index['reports'].append(entry)
                printed.append((k, raw.decode('utf-8')))
                out.append(dict(kind=k, number=number, revision=revision, file=str(central), classroom_copy=copy,
                                sha256=entry['sha256'], bytes=len(raw), existing=False, supersedes=superseded))
            for _ in rendered:     # nothing is left; lets the pool end through its own bounded path
                pass
            # the seal check: every report the index now names equals the save point's claim for it
            for entry in index['reports'][-len(KINDS):]:
                claim = written_so_far.get(entry['kind'])
                if not claim or claim.get('sha256') != entry['sha256'] or claim.get('bytes') != entry['bytes']:
                    problems.append('the %s report differs from its save point claim (%s)' % (entry['kind'], claim))
        write_index(reports, index)
        timings['build_and_write'] = round(time.monotonic() - started - timings['read_inputs'] - timings['all99_join'], 6)
        try:                                     # the stage heartbeat (frankie_box_stage_progress); never changes the stage
            import frankie_box_stage_progress as _SP
            _SP.report_phase('reports: reports built and written', units_done=2, units_total=2, unit='boundaries', reports=len(out))
        except Exception:  # noqa: BLE001
            pass

    for k, text in printed:
        print('=' * 100)
        print(text, end='' if text.endswith('\n') else '\n')
    print('=' * 100)
    receipt = dict(schema=SCHEMA, run=run_name, day=day, report_number=number, number_assigned_now=new_day,
                   classroom=str(d.dir), classroom_status=d.status, built_from=d.source, reports=out,
                   exchange=dict(path=d.exchange_path, sha256=d.exchange_sha256) if d.exchange is not None else
                   dict(listed=d.exchange_listed),
                   exchange_sha256=d.exchange_sha256,
                   meeting=dict(status=d.meeting['status'], path=d.meeting.get('path'), sha256=d.meeting_sha256,
                                reason=d.meeting.get('reason')),
                   meeting_status=d.meeting['status'], meeting_sha256=d.meeting_sha256,
                   school=d.school_path, school_sha256=d.school_sha256, school_status=d.school_status,
                   school_listed=d.school_listed, school_kind=d.school_kind, school_row=d.school_row,
                   school_successor_receipt_status=(d.school_receipt or {}).get('status') if d.school_receipt else None,
                   absent=[dict(file=name, reason=why) for name, why in d.absent],
                   inputs=d.inputs, reused=bool(out) and all(o.get('existing') for o in out), reuse_why=reuse_why,
                   index=str(reports / 'index.json'), problems=problems, model_calls=0,
                   # stacks pass (additive): how the reports were rendered (side by side or in-process, with the reason),
                   # the CPU map (frankie_box_lane_pin.record), pool recovery and the save point resumed from
                   report_rendering=rendering,
                   # the 99 layers joined for the FRANKIE report (diagnostic, never knowledge): the full per-entry join
                   all99=d.all99, all99_sha256=d.all99_sha256,
                   # what late_pieces_changed re-reads to recompute the join's input set (F9): this build's invocation
                   all99_invocation=dict(classroom=str(classroom), refused_reason=refused_reason,
                                         exchange=exchange and str(exchange), exchange_listed=exchange_listed,
                                         school=school and str(school), school_listed=school_listed,
                                         run_dir=str(Path(run_dir) if run_dir else RUNS / run_name),
                                         piece_receipts={k: str(v) for k, v in sorted((piece_receipts or {}).items())}))
    receipt['workflow_report'] = workflow_report(d, receipt)
    receipt_path = reports / 'receipts' / run_name / (day + '.json')
    receipt['receipt_path'] = str(receipt_path)
    try:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        previous = sha256_file(receipt_path) if receipt_path.is_file() else None
        receipt['previous_receipt_sha256'] = previous        # the index keeps every build; the receipt file is the latest
        timings['total'] = round(time.monotonic() - started, 6)
        receipt['timings_seconds'] = timings
        tmp = receipt_path.with_name(receipt_path.name + '.pending')
        tmp.write_text(json.dumps(receipt, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(tmp, receipt_path)
    except OSError as error:
        problems.append('the receipt file %s could not be written: %s: %s' % (receipt_path, type(error).__name__, error))
        receipt['timings_seconds'] = dict(timings, total=round(time.monotonic() - started, 6))
    print('REPORT_NUMBER=%d' % number)
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return receipt if return_receipt else (1 if problems else 0)


# ---------------------------------------------------------------------------- late pieces (F9a; Run.reports_stale reads it)
LATE_PIECES_SCHEMA = 'FRANKIE_DAY_REPORTS_LATE_PIECES_V1'
# Per piece: a list read (or an integrity failure) is compared on (status, file, sha256, basis); a piece that reported no
# list on (status, basis) only, because the file it names then is the step/receipt that carries NO list, whose bytes change
# while a stage waits (a rewritten waiting step receipt is not a late piece). The reason text is reported, never compared.
JOIN_COMPARED = ('status', 'file', 'sha256', 'basis')
JOIN_COMPARED_NOT_REPORTED = ('status', 'basis')
LESSONS_BASIS = ('exchange_record', 'exchange_step_receipt', 'conventional_path')
INVOCATION_KEYS = ('classroom', 'refused_reason', 'exchange', 'exchange_listed', 'school', 'school_listed', 'run_dir',
                   'piece_receipts')


def reports_receipt_path(reports, run_name, day):
    """The day reports receipt run() writes: <reports-dir>/receipts/<run>/<day>.json."""
    return Path(reports) / 'receipts' / str(run_name) / ('%s.json' % day)


def late_pieces_changed(receipt, current=None):
    """Has the 99-layer join's input set changed since the day's reports were built? Pure: reads only, writes nothing,
    takes no lock, renders nothing, makes no model call.

    receipt  the path of the day reports receipt, reports_receipt_path(reports, run, day)
             (FRANKIE_EXPERIMENT_DAY_REPORTS_RECEIPT_V1).
    current  optional dict, keys from INVOCATION_KEYS: what the orchestrator would pass to the reports NOW (classroom,
             refused_reason, exchange, exchange_listed, school, school_listed, run_dir, piece_receipts {candidates,
             carried_claims, jev: path}). A key present (even None) replaces the value the receipt recorded in
             all99_invocation; a key absent keeps the recorded value.

    Returns LATE_PIECES_SCHEMA, always (it never raises for an unreadable input):
      outcome   'changed' | 'unchanged' | 'unknown'; changed True | False | None (the same, as a boolean or None)
      reason    one sentence: why this outcome
      day, run
      recorded  dict(receipt=dict(path, bytes, sha256), all99_sha256, inputs=[join_inputs rows as recorded])
      current   dict(all99_sha256, inputs=[join_inputs rows now], lessons_source) or None when unknown
      differences  [dict(piece, recorded=dict | None, current=dict | None)]: a piece whose compared fields differ
                (JOIN_COMPARED for a list read or an integrity failure; JOIN_COMPARED_NOT_REPORTED, status and basis,
                for a piece that reported no list), or that is listed on one side only
      reasons_only  [dict(piece, recorded, current)]: nothing compared differs, only the reason text or the bytes of a
                receipt that carries no list (reported, not a change)
      invocation  dict(values=the invocation used, source={key: 'recorded' | 'current' | 'default'})
      read      [every file read: kind, path, bytes, sha256] (the receipt first)
      compared  dict(list=JOIN_COMPARED, not_reported=JOIN_COMPARED_NOT_REPORTED); seconds
    Semantics: 'changed' when any piece's compared fields differ (a list arrived, went, or its bytes or basis changed; a
    piece went from not reported to read or integrity), a piece appears or disappears, or the
    receipt carries no recorded join (reports built before the join existed: a rebuild adds it). 'unchanged' otherwise.
    'unknown' when the receipt cannot be read or is not a day reports receipt, or the day's inputs cannot be read now
    (the classroom receipt, the exchange, the school file, an exchange of another day): the error is named in reason;
    an unknown is never a change and never a zero. The caller decides what an unknown does (Run.reports_stale: no
    revision, the reason logged); a rebuild itself states every integrity failure it meets."""
    started = time.monotonic()
    path = Path(receipt)
    out = dict(schema=LATE_PIECES_SCHEMA, outcome='unknown', changed=None, reason=None, day=None, run=None,
               recorded=dict(receipt=dict(path=str(path), bytes=None, sha256=None), all99_sha256=None, inputs=None),
               current=None, differences=[], reasons_only=[], invocation=None, read=[],
               compared=dict(list=list(JOIN_COMPARED), not_reported=list(JOIN_COMPARED_NOT_REPORTED)),
               rule='a pure read of what the reports\' 99-layer join reads; never knowledge; never a gate on the day')

    def done(outcome, reason):
        out.update(outcome=outcome, changed=dict(changed=True, unchanged=False).get(outcome), reason=reason,
                   seconds=round(time.monotonic() - started, 6))
        return out
    try:
        raw = path.read_bytes()
    except OSError as error:
        return done('unknown', 'the reports receipt %s could not be read (%s: %s)' % (path, type(error).__name__, error))
    out['recorded']['receipt'].update(bytes=len(raw), sha256=sha256_bytes(raw))
    out['read'].append(dict(kind='day reports receipt', path=str(path), bytes=len(raw), sha256=sha256_bytes(raw)))
    try:
        rec_doc = json.loads(raw)
    except ValueError as error:
        return done('unknown', 'the reports receipt %s is not readable JSON (%s)' % (path, error))
    if not isinstance(rec_doc, dict) or rec_doc.get('schema') != SCHEMA:
        return done('unknown', 'the file %s is not a %s' % (path, SCHEMA))
    day, run_name = str(rec_doc.get('day')), str(rec_doc.get('run'))
    out.update(day=day, run=run_name)
    join = rec_doc.get('all99') if isinstance(rec_doc.get('all99'), dict) else None
    recorded_inputs = join.get('inputs') if join else None
    out['recorded'].update(all99_sha256=rec_doc.get('all99_sha256'), inputs=recorded_inputs)
    # the invocation: as recorded by the build (all99_invocation; older receipts: the fields the receipt carries), then
    # replaced key by key by `current`
    inv = rec_doc.get('all99_invocation') if isinstance(rec_doc.get('all99_invocation'), dict) else None
    exchange_rec = rec_doc.get('exchange') if isinstance(rec_doc.get('exchange'), dict) else {}
    fallback = dict(classroom=rec_doc.get('classroom'),
                    refused_reason=('recorded refusal (its reason is not on this receipt)'
                                    if (rec_doc.get('built_from') or {}).get('kind') == 'orchestrator refusal' else None),
                    exchange=exchange_rec.get('path'), exchange_listed=exchange_rec.get('listed'),
                    school=rec_doc.get('school'), school_listed=rec_doc.get('school_listed'),
                    run_dir=str(RUNS / run_name), piece_receipts={})
    values, source = {}, {}
    for key in INVOCATION_KEYS:
        if isinstance(current, dict) and key in current:
            values[key], source[key] = current[key], 'current'
        elif inv is not None and key in inv:
            values[key], source[key] = inv[key], 'recorded'
        else:
            values[key], source[key] = fallback[key], 'default'
    values['piece_receipts'] = {k: str(v) for k, v in sorted(dict(values['piece_receipts'] or {}).items()) if v}
    out['invocation'] = dict(values=values, source=source)
    if not values['classroom']:
        return done('unknown', 'no classroom directory is recorded on the receipt or given')
    if recorded_inputs is None or not isinstance(recorded_inputs, list):
        return done('changed', 'the reports were built before the 99-layer join existed (the receipt records no join '
                               'inputs); a revision adds it')
    d = None
    try:
        d = Day(day, values['classroom'], values['refused_reason'], values['exchange'], values['exchange_listed'],
                values['school'], values['school_listed'], join_only=True)
        collect_all99(d, run_name, Path(values['run_dir']), values['piece_receipts'])
    except (SystemExit, Exception) as error:      # noqa: BLE001 - every failure to read is an unknown, named
        out['read'] += [dict(i) for i in getattr(d, 'inputs', None) or []]
        return done('unknown', 'the day\'s inputs could not be read now (%s: %s)' % (type(error).__name__, error))
    out['read'] += [dict(i) for i in d.inputs]
    now = join_inputs(list(d.all99_sources) + list(getattr(d, 'all99_point_sources', None) or []))   # all99_join's formula
    out['current'] = dict(all99_sha256=sha256_bytes(json.dumps(now, sort_keys=True).encode()), inputs=now,
                          lessons_source=d.all99_lessons_source)

    def keyed(rows):
        return {str(r.get('piece')): r for r in rows if isinstance(r, dict)}

    def compared(row):
        if row is None:
            return None
        keys = JOIN_COMPARED_NOT_REPORTED if row.get('status') == 'not_reported' else JOIN_COMPARED
        return {k: row.get(k) for k in keys}
    before, after = keyed(recorded_inputs), keyed(now)
    for piece in sorted(set(before) | set(after)):
        a, b = before.get(piece), after.get(piece)
        pa, pb = compared(a), compared(b)
        if pa != pb:
            out['differences'].append(dict(piece=piece, recorded=pa, current=pb))
        elif a.get('reason') != b.get('reason') or a.get('sha256') != b.get('sha256'):
            out['reasons_only'].append(dict(piece=piece, recorded=a.get('reason'), current=b.get('reason'),
                                            recorded_sha256=a.get('sha256'), current_sha256=b.get('sha256')))
    if out['differences']:
        return done('changed', 'the join\'s input set changed since the reports were built: %s' % listing(
            '%s %s -> %s' % (x['piece'], (x['recorded'] or {}).get('status', 'absent'),
                             (x['current'] or {}).get('status', 'absent')) for x in out['differences']))
    return done('unchanged', 'every piece list the join reads has the same status, file, sha256 and basis as when the '
                             'reports were built%s' % (' (reason text or a no-list receipt differs for %d piece(s); '
                                                       'reported, not a change)' % len(out['reasons_only'])
                                                       if out['reasons_only'] else ''))


def workflow_report(d, receipt):
    """FRANKIE_PIECE_WORKFLOW_REPORT_V1 for the one-day inspection: what this step received, how it used it and what it
    produced, from the receipt's own values only. A receipt records what was read and written; it is not proof that a
    reader consumed the reports, and the reports are never knowledge."""
    sections_from = {
        'classroom report: counts, teacher, grade, corrections, acknowledgement, novel/dropped, carried, external':
            ['classroom receipt'] + list(JSON_FILES) + ['classroom.md'],
        'frankie report: his answers, corrections, acknowledgement, external, novel, brain entry':
            ['classroom receipt', 'code-answers.json', 'ledgers.json', 'post-grade.json', 'correction-request.json',
             'correction-response.json', 'acknowledgement.json', 'completion.json', 'external-code-answers.json',
             'external-post-grade.json', 'external-correction-request.json', 'external-correction-response.json',
             'external-acknowledgement.json', 'external-completion.json', 'novel-findings.json', 'brain MANIFEST'],
        'both: the three-way exchange': ['exchange', 'exchange-frankie view'],
        'frankie report: the discussion (meeting)': ['meeting record'],
        'frankie report: the school file': ['school file', 'school index', 'school successor receipt'],
        'frankie report: the 99 layers (what reached Frankie today)':
            ['root step receipt', 'classroom receipt', 'exchange step receipt', 'lessons file',
             'lessons file (the school file\'s whole inline copy)'] + ['%s all-99 list' % p for p, _, _ in ALL99_PIECES]
            + ['accumulated_lessons step receipt', 'carried claims receipt', 'candidates receipt', 'exchange receipt',
               'jev step receipt', 'Jev receipt', 'Jev client receipt', 'meeting record']}
    read = {i['kind'] for i in d.inputs}
    dispositions = [dict(input=name, disposition='absent or unreadable', reason=why) for name, why in d.absent]
    if d.exchange is None:
        dispositions.append(dict(input='exchange', disposition='not given', reason=d.exchange_listed))
    if d.meeting['status'] != 'complete':
        dispositions.append(dict(input='meeting record', disposition=d.meeting['status'], reason=d.meeting.get('reason')))
    if d.school_status != 'read':
        dispositions.append(dict(input='school file', disposition=d.school_status, reason=d.school_listed,
                                 integrity_failure=d.school_status in ('integrity_mismatch', 'unreadable')))
    elif d.school_listed:
        dispositions.append(dict(input='school file', disposition='read with a note', reason=d.school_listed))
    if d.status != 'complete':
        dispositions.append(dict(input='classroom outputs', disposition='not read',
                                 reason='the classroom was %s: %s' % (d.status, d.receipt.get('reason'))))
    for p in d.all99.get('pieces') or []:
        if p['status'] != 'read':
            dispositions.append(dict(input='all-99 list of %s' % p['piece'], disposition=p['status'], reason=p['reason'],
                                     integrity_failure=p['status'] == 'integrity'))
    return dict(
        schema=PIECE_WORKFLOW_REPORT, piece='day_reports',
        inputs=dict(files=d.inputs, built_from=d.source, exchange_sha256=d.exchange_sha256, meeting_sha256=d.meeting_sha256,
                    school_sha256=d.school_sha256, school_row=d.school_row,
                    all99_invocation=receipt.get('all99_invocation')),
        use=dict(sections_from={k: sorted(set(v) & read) for k, v in sections_from.items()},
                 not_read={k: sorted(set(v) - read) for k, v in sections_from.items() if set(v) - read},
                 dispositions=dispositions, reuse=receipt['reused'], reuse_why=receipt['reuse_why'],
                 all99=all99_summary(d.all99),
                 # F9b: where the scientific teacher's lessons list came from (LESSONS_BASIS; current or may be stale)
                 all99_lessons_source=d.all99.get('lessons_source'),
                 withheld=['the answer key\'s content and the exhaustive grade are never in the reports (R10); hashes and '
                           'paths appear only in the Evidence section; the meeting appears only in the Frankie report'],
                 rule='fixed templates per recorded field; no interpretation, ranking, average or pooled value (D37); '
                      'absent reads as not recorded with its reason, never as zero; an integrity failure is stated as '
                      'such, never as a thinner picture'),
        outputs=dict(reports=receipt['reports'], report_number=receipt['report_number'],
                     number_assigned_now=receipt['number_assigned_now'], index=receipt['index'],
                     problems=receipt['problems'], refusals=[], waits=[], model_calls=0,
                     exit_code=1 if receipt['problems'] else 0),
        rule='temporary operator review of one day; the reports and this receipt are diagnostic and never knowledge; a '
             'recorded write is not proof any reader consumed it')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--day', required=True)
    ap.add_argument('--classroom', required=True, help='the day\'s classroom directory (<calculations>/work/classroom)')
    ap.add_argument('--run', required=True, help='the experiment orchestrator run name')
    ap.add_argument('--reports-dir', default=str(REPORTS))
    ap.add_argument('--day-class', help='the run\'s day class (default: from the weekday, as the orchestrator assigns it)')
    ap.add_argument('--refused-reason', help='the orchestrator\'s reason when it refused the classroom before a receipt '
                                             'was written (used only when the classroom holds no receipt.json)')
    ap.add_argument('--exchange', help='the day\'s exchange.json (FRANKIE_EXPERIMENT_EXCHANGE_V1, the orchestrator\'s exchange '
                                       'stage)')
    ap.add_argument('--exchange-listed', help='why there is no exchange for the day (the orchestrator\'s reason)')
    ap.add_argument('--school', help='the day\'s %s file the school step wrote (<brain>/school/<day>.json or a retained '
                                     'checked successor <brain>/school/successors/<day>/<op>/school.json)' % SCHOOL_SCHEMA)
    ap.add_argument('--school-listed', help='why there is no school file for the day (the orchestrator\'s reason)')
    ap.add_argument('--run-dir', help='the orchestrator run directory whose days/<day>/<stage>.json step receipts name the '
                                      'pieces\' all-99 lists (default %s/<run>)' % RUNS)
    ap.add_argument('--piece-receipt', action='append', default=[], metavar='PIECE=PATH',
                    help='a piece receipt given directly for the 99-layer join: candidates=<survivor update receipt.json> '
                         '(a boundary day other than this one), carried_claims=<accumulated lessons receipt.json>, '
                         'jev=<JEV_CPU_RECEIPT_V1 receipt.json>')
    a = ap.parse_args()
    if not re.fullmatch('[0-9]{8}', a.day):
        ap.error('--day must be YYYYMMDD')
    if not re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run):
        ap.error('--run: letters, digits, _ and - only')
    piece_receipts = {}
    for item in a.piece_receipt:
        piece, sep, path = item.partition('=')
        if not sep or piece not in ('candidates', 'carried_claims', 'jev') or not Path(path).is_absolute() \
                or '..' in Path(path).parts or piece in piece_receipts:
            ap.error('--piece-receipt needs one PIECE=ABSOLUTE_PATH per piece, PIECE one of candidates, carried_claims, jev')
        piece_receipts[piece] = path
    if a.run_dir and (not Path(a.run_dir).is_absolute() or '..' in Path(a.run_dir).parts):
        ap.error('--run-dir must be an absolute path without ..')
    cls = a.day_class or CLASS_OF_WEEKDAY.get(dt.date(int(a.day[:4]), int(a.day[4:6]), int(a.day[6:])).weekday(),
                                               'weekend')
    return run(a.day, a.classroom, a.run, Path(a.reports_dir), cls, a.refused_reason, a.exchange, a.exchange_listed,
               school=a.school, school_listed=a.school_listed, run_dir=a.run_dir, piece_receipts=piece_receipts)


if __name__ == '__main__':
    sys.exit(main())
