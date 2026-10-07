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
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

SCHEMA = 'FRANKIE_EXPERIMENT_DAY_REPORTS_RECEIPT_V1'
INDEX_SCHEMA = 'FRANKIE_EXPERIMENT_DAY_REPORTS_INDEX_V1'
SCHOOL_SCHEMA = 'FRANKIE_SCHOOL_KNOWLEDGE_V1'              # frankie_box_school_knowledge.SCHEMA (read, never written here)
SCHOOL_INDEX_SCHEMA = 'FRANKIE_SCHOOL_INDEX_V1'             # frankie_box_brain.SCHOOL_INDEX_SCHEMA
PIECE_WORKFLOW_REPORT = 'FRANKIE_PIECE_WORKFLOW_REPORT_V1'  # the one-day inspection record (frankie_box_workflow_inspection)
REPORTS = Path('/opt/frankie-box/work/experiment-reports')
KINDS = ('classroom', 'frankie')
FILE_RE = re.compile(r'^(classroom|frankie)-report-(\d{4,})(?:-r(\d+))?\.md$')
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
    (6, 'squeeze watch: sessions since the front contract\'s expiry (deferred by Greg)'),
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
                 school_listed=None):
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
        self.dropped, self.brain, self.brain_why = None, None, None
        if self.status != 'complete':
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
    if d.status != 'complete':
        return L + refused_lines(d) + exchange_lines(d, False) + glossary_lines() + evidence(d)
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
    L += ([''] if unassigned else []) + ['Deferred (recorded reason): %s. Deferred points: %s.' % (
        rec(deferred.get('reason')), listing('%s (%s)' % (rec(q.get('point_id')), q.get('name'))
                                              for q in deferred.get('points') or [])), '']
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
        return L + refused_lines(d) + school_lines(d, number) + exchange_lines(d, True) + glossary_lines() + evidence(d, True)
    comps = component_facts(d)
    pairs, wrong_pairs, _ = pair_facts(d)
    ext_series = external_series_facts(d)
    ext_points = point_facts(d)
    L += frankie_counts(d, comps, wrong_pairs, pairs, ext_series, ext_points)
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


def write_new(path, raw):
    """Write bytes to a new file (never overwrite): (True, None) or (False, why)."""
    try:
        with open(path, 'xb') as f:
            f.write(raw)
        return True, None
    except FileExistsError:
        if Path(path).read_bytes() == raw:
            return True, 'already there with the same bytes'
        return False, '%s exists with other bytes (never overwritten)' % path
    except OSError as error:
        return False, '%s: %s' % (type(error).__name__, error)


def run(day, classroom, run_name, reports, cls, refused_reason, exchange=None, exchange_listed=None, *, return_receipt=False,
        school=None, school_listed=None):
    started = time.monotonic()
    d = Day(day, classroom, refused_reason, exchange, exchange_listed, school, school_listed)
    timings = dict(read_inputs=round(time.monotonic() - started, 6))
    reports.mkdir(parents=True, exist_ok=True)
    out, printed, problems = [], [], list(d.school_problems)
    reuse_why = None
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
                                and latest[k].get('school_status', 'not given') == d.school_status)
                 for k in KINDS}
        reuse = all(all(m.values()) for m in match.values())
        reuse_why = ('the existing reports were built from the same classroom receipt, exchange, meeting and school file'
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
            texts = dict(classroom=classroom_report(d, number, revision, run_name, cls, files['frankie']),
                         frankie=frankie_report(d, number, revision, run_name, cls, files['classroom']))
            for k in KINDS:
                raw = ('\n'.join(texts[k]).rstrip('\n') + '\n').encode('utf-8')
                central = reports / files[k]
                written, why = write_new(central, raw)
                if not written:
                    raise SystemExit('the %s report %s could not be written: %s' % (k, central, why))
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
                             school=d.school_path, school_sha256=d.school_sha256, school_status=d.school_status)
                index['reports'].append(entry)
                printed.append((k, raw.decode('utf-8')))
                out.append(dict(kind=k, number=number, revision=revision, file=str(central), classroom_copy=copy,
                                sha256=entry['sha256'], bytes=len(raw), existing=False, supersedes=superseded))
        write_index(reports, index)
        timings['build_and_write'] = round(time.monotonic() - started - timings['read_inputs'], 6)
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
                   index=str(reports / 'index.json'), problems=problems, model_calls=0)
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
        'frankie report: the school file': ['school file', 'school index', 'school successor receipt']}
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
    return dict(
        schema=PIECE_WORKFLOW_REPORT, piece='day_reports',
        inputs=dict(files=d.inputs, built_from=d.source, exchange_sha256=d.exchange_sha256, meeting_sha256=d.meeting_sha256,
                    school_sha256=d.school_sha256, school_row=d.school_row),
        use=dict(sections_from={k: sorted(set(v) & read) for k, v in sections_from.items()},
                 not_read={k: sorted(set(v) - read) for k, v in sections_from.items() if set(v) - read},
                 dispositions=dispositions, reuse=receipt['reused'], reuse_why=receipt['reuse_why'],
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
    a = ap.parse_args()
    if not re.fullmatch('[0-9]{8}', a.day):
        ap.error('--day must be YYYYMMDD')
    if not re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run):
        ap.error('--run: letters, digits, _ and - only')
    cls = a.day_class or CLASS_OF_WEEKDAY.get(dt.date(int(a.day[:4]), int(a.day[4:6]), int(a.day[6:])).weekday(),
                                               'weekend')
    return run(a.day, a.classroom, a.run, Path(a.reports_dir), cls, a.refused_reason, a.exchange, a.exchange_listed,
               school=a.school, school_listed=a.school_listed)


if __name__ == '__main__':
    sys.exit(main())
