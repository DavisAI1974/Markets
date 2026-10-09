"""The hub's SPOKES (Greg, 2026-10-09, session 12: one teacher hub, a spoke to each workflow piece; read-calc-write under
one turn lock). One spoke per piece: root, teacher, classroom (Frankie), teacher-2 (the teacher's second turn after the
classroom: Frankie's lessons, the novelty investigation), exchange, jev, school, reports (the day-reports render) and the
forecaster (the go-live last spoke: no consumer yet). Turns are ordered by the hub core's prerequisites
(frankie_box_hub.PREREQUISITES), and a piece's send carries what its prerequisites (transitively) have written.

Greg, 2026-10-09: "Let's get spokes built while the teacher is finishing, and we won't disconnect any info the other
pieces get natively until we compare what is sent to them also includes everything they are getting fed to them
currently." So nothing here is called by the workflow: no existing module is edited and no call site changes. The
comparison (frankie_box_hub_compare) reads this module's inventory and send sets.

Each spoke carries:
  NATIVE_INPUTS[piece]  every input the piece reads TODAY, traced from the code: name, kind, producer, the reading code
                        (repo file and an anchor text; the line is found at use, so a moved line is still found), how it
                        is filtered, how it is located on the box (`locate`), how it is compared (`compare`: file = the
                        bytes streamed and hashed; pin = by the pin the readers already use (path, bytes, sha256), for
                        the giant files; value = the JSON value at a field), and its class: data (in the verdict), own
                        (the piece's own retained resume state, not something another piece feeds it) or mechanism
                        (claim caches, run settings, control files, model runtime: how a piece reads, not what).
  send_set(piece, sources)   the hub additions that piece would RECEIVE: the hub's pinned sources, the knowledge store,
                        and every earlier piece's publications, each BY REFERENCE (path, bytes, sha256; never a copy),
                        each carrying the receiving piece's filter rule as a FIELD. The spoke does not apply the rule:
                        the hub sends, and the piece's own rule applies on read, as today.
  run_spoke(piece, hub_dir, sources)   take_turn, read, calc (placeholder: the piece's own outputs, by reference), write,
                        release, through the hub core (frankie_box_hub, imported lazily). Not called by anything yet.

Addition format (FRANKIE_HUB_PIECE_V1 additions): {"kind", "content_sha256", "path", "bytes", "sha256"} for a file or
{"kind", "content_sha256", "value"} for a value, plus "name", "producer", "filter" and, when known, "known_by".
"""
import fnmatch
import hashlib
import json
import os
import re
import sys
from pathlib import Path

BOX = Path(__file__).resolve().parent
REPO = BOX.parents[2]
if str(BOX) not in sys.path:
    sys.path.insert(0, str(BOX))

SPOKES_SCHEMA = 'FRANKIE_HUB_SPOKES_V1'
# The hub core's pieces (frankie_box_hub.DEFAULT_PIECES): teacher-2 is the teacher's second turn after the classroom
# (Frankie's lessons, the novelty investigation); reports is the day-reports render. Turns are ordered by the hub core's
# prerequisites (frankie_box_hub.PREREQUISITES), not by this tuple; this tuple is only the listing order.
PIECES = ('root', 'teacher', 'classroom', 'teacher-2', 'exchange', 'jev', 'school', 'reports', 'forecaster')
# A copy of frankie_box_hub.PREREQUISITES for when the core is not importable; prerequisites() prefers the core's own.
_PREREQUISITES_FALLBACK = {
    'root': (), 'teacher': ('root',), 'classroom': ('teacher',), 'teacher-2': ('classroom',),
    'exchange': ('teacher', 'classroom', 'teacher-2'), 'jev': ('teacher', 'classroom', 'exchange'),
    'school': ('classroom', 'exchange', 'jev'),
    'reports': ('root', 'teacher', 'classroom', 'teacher-2', 'exchange', 'jev', 'school'), 'forecaster': ('school',)}
BOX_ROOT = Path('/opt/frankie-box')
WORK = BOX_ROOT / 'work'
DEFAULT_ROOTS = dict(
    experiment_roots=WORK / 'experiment-roots', teacher_rows=WORK / 'experiment-teacher-rows',
    runs=WORK / 'experiment', brain=BOX_ROOT / 'brain', jev_brain=BOX_ROOT / 'jev-brain',
    search=WORK / 'experiment-search', lessons=WORK / 'experiment-teacher', lane_state=WORK / 'lane-state', repo=REPO,
    survivors=WORK / 'experiment-survivors', reports=WORK / 'experiment-reports')
CYCLE, SEARCH_ROLE = '00', 'discovery'
HASH_MAX = 64 << 20          # send_set hashes an unpinned file up to this size; larger ones carry sha256 None (stated)

ROWS_FILE = 'host-dipole-classroom-source.c15.json'
SIDECAR_FILE = 'host-dipole-classroom-source.c15.rows.jsonl'
DIRECTIVE = 'research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json'
RULES = 'research/kalshi/frankie_boss/knowledge/CLASSROOM_RULES_V3.json'
MANIFEST = 'research/kalshi/frankie_boss/blocks/BLOCK_{day}_SOURCE_MANIFEST.json'
NATIVE_LEDGERS = ('exact_member_rows.jsonl', 'exact_lifecycle_rows.jsonl', 'legacy_observable_rows.jsonl')
NATIVE_SECTIONS = ('bedrock_section_4_2', 'bedrock_section_4_4')
SPOOLS = ('frames', 'prices', 'structures')

# The filter rule each receiving piece applies on its own read (stated on every addition sent to it; never applied here)
FILTERS = dict(
    root='none: ROOT reads the sealed day whole',
    teacher='none: the teacher reads the sealed day and the ROOT whole (the pinned grading key never built from the '
            'classroom role\'s findings)',
    classroom=('withheld on read by the classroom: the sealed answers and targets (the teacher key split off the package '
               'by final_model_visible_classroom; post-grade content), the current-day teacher and teacher-account brain '
               'entries and the current-day teacher account in any mode but TEACH, this day\'s later-stage entries and '
               'its own school day; the per-lesson reveal opens a lesson\'s answers at its discussion'),
    exchange=('the teachers\' explicit cutoff: the teacher receipt\'s as_of / through_cursor (the cutoff context and the '
              'second set at the cutoff); this day\'s later-stage entries walled at the exchange boundary'),
    jev=('Jev\'s cutoff: the classroom teacher binding\'s source_hash / as_of / through_cursor (the second set to his '
         'cutoff, blind-wall audit 0 rows after it); Frankie\'s outputs read only after his blind seal; Jev-only peer '
         'knowledge, never Frankie\'s brain'),
    school=('R10 withholdings: the exhaustive grades (post-grade.json, external-post-grade.json) and the teacher key\'s '
            'content (hash only); Jev\'s claims stay out (the lessons wall)'),
    forecaster='no consumer yet (go-live: the hub feeds the forecaster last)',
    **{'teacher-2': ('R09: of Frankie\'s ledgers only the novel findings (dipole_novel_findings) and the external novel '
                     'findings are read; the teacher key is the teacher\'s own (sealed from Frankie, not from the teacher)'),
       'reports': ('none: the reports render every piece as recorded (one-way in; nothing reads the reports into a '
                   'calculation); the exhaustive grades are rendered in the CLASSROOM report, not in Frankie\'s')})


def _i(name, kind, producer, at, anchor, locate, *, compare='file', klass='data', filter=None, note=None):
    return dict(name=name, kind=kind, producer=producer, at=at, anchor=anchor, locate=locate, compare=compare,
                klass=klass, filter=filter or 'none', note=note)


_ROOT_PY = 'deploy/aws/box/frankie_box_experiment_root.py'
_TEACHER_PY = 'deploy/aws/box/frankie_box_experiment_teacher.py'
_TIMELINE_PY = 'deploy/aws/box/frankie_box_market_timeline.py'
_NATIVE_PY = 'deploy/aws/box/frankie_box_experiment_native.py'
_V2_PY = 'deploy/aws/box/frankie_box_experiment_classroom_v2.py'
_K_PY = 'deploy/aws/box/frankie_box_classroom_code.py'
_LS_PY = 'deploy/aws/box/frankie_box_lane_state.py'
_TR_PY = 'deploy/aws/box/frankie_box_teacher_rows.py'
_EX_PY = 'deploy/aws/box/frankie_box_experiment_exchange.py'
_AM_PY = 'deploy/aws/box/frankie_box_adviser_market.py'
_JEV_PY = 'deploy/aws/box/frankie_box_jev_cpu.py'
_SCH_PY = 'deploy/aws/box/frankie_box_school_knowledge.py'
_BR_PY = 'deploy/aws/box/frankie_box_brain.py'
_REV_PY = 'deploy/aws/box/frankie_box_experiment_review.py'
_EXT_PY = 'research/kalshi/frankie_boss/dipole_classroom_external.py'

_CR = '{attempt}/calculations-receipt.json'
_SB = '{attempt}/source-binding.json'
_DERIVE = '{attempt}/work/derive.json'
_TRC = '{rows}/receipt.json'


def _root_reader_inputs(at, producer='ROOT (frankie_box_experiment_root)', filter=None):
    """The ROOT as SharedMarketTimeline (and selected_files) reads it: every file that reader opens, pinned."""
    via = ' (through SharedMarketTimeline)' if at != _TIMELINE_PY else ''
    out = [
        _i('ROOT source-binding.json' + via, 'receipt', producer, _TIMELINE_PY,
           "source_pin = dict(path=str(root / 'source-binding.json')", ('path', _SB), filter=filter),
        _i('ROOT calculations-receipt.json' + via, 'receipt', producer, _TIMELINE_PY,
           "calculation_pin = dict(path=str(root / 'calculations-receipt.json')", ('path', _CR), filter=filter),
        _i('ROOT derive.json' + via, 'file', producer, _TIMELINE_PY, "derive = _json(calculation['derivation'])",
           ('pin', _CR, 'derivation'), filter=filter),
    ]
    for role in SPOOLS:
        out.append(_i('ROOT %s spool (work/derived/.rows/%s.jsonl)%s' % (role, role, via), 'stream', producer,
                      _TIMELINE_PY, "for role, kind, state in (('frames', 'frame', True)",
                      ('pin', _CR, ('shared_market_sources', role)), compare='pin', filter=filter,
                      note='compared by pin (path, bytes, sha256: the pin the reader checks); never read whole here'))
    for name in NATIVE_LEDGERS:
        out.append(_i('ROOT native ledger %s%s' % (name, via), 'stream', producer, _NATIVE_PY,
                      "pool, measured = _prefetch_witnesses(root, [(native['ledgers'].get(name)",
                      ('pin', _DERIVE, ('bedrock', 'ledgers', name)), compare='pin', filter=filter,
                      note='compared by pin (the derivation\'s ledger pin, which selected_files witnesses)'))
    out.append(_i('ROOT native result.json' + via, 'file', producer, _NATIVE_PY,
                  "+ [(native.get('result'), 'result.json', 'work/bedrock')]", ('pin', _DERIVE, ('bedrock', 'result')),
                  compare='pin', filter=filter))
    for name in NATIVE_SECTIONS:
        out.append(_i('ROOT native section %s.json.gz%s' % (name, via), 'file', producer, _NATIVE_PY,
                      "+ [(layers.get(name), name + '.json.gz', 'work/derived/.projection-v2')",
                      ('pin', _DERIVE, ('layers', name)), compare='pin', filter=filter))
    out.append(_i('day file publications (the external layer)' + via, 'file', 'day-external (frankie_box_day_external)',
                  _TIMELINE_PY, "self.publications = _Publications(external, day)", ('pin', _SB, 'external'),
                  filter=filter, note='the day file the ROOT attached, by the source binding\'s pin'))
    out.append(_i('ROOT work/file-claims.jsonl (stream claims)' + via, 'claims', producer, _TIMELINE_PY,
                  "claims = _session_claims()._load_file_claims(root / 'work')", ('path', '{attempt}/work/file-claims.jsonl'),
                  klass='mechanism', note='how the reader skips a second hash; never a value'))
    return out


NATIVE_INPUTS = {}

NATIVE_INPUTS['root'] = [
    _i('ingestion receipt (BOSS_BLOCK_INGESTION_RECEIPT_V1)', 'receipt', 'ingest (frankie_box_ingest_block)', _ROOT_PY,
       "receipt = json.loads(Path(receipt_path).read_bytes())", ('path', '{ingest_receipt}')),
    _i('sealed journal (compact)', 'stream', 'ingest (frankie_box_ingest_block)', _ROOT_PY,
       "journal = directory / receipt['journal_file']", ('journal', '{ingest_receipt}'), compare='pin',
       note='compared by pin (the receipt\'s journal_bytes / journal_sha256, the witness the ROOT checks)'),
    _i('opening book beside the journal (opening_book_file)', 'file', 'ingest (frankie_box_ingest_block)', _ROOT_PY,
       "raw = (directory / own['file']).read_bytes()", ('pin_rel', '{ingest_receipt}', 'opening_book_file', '{ingest}')),
    _i('seeded opening book record (prior day\'s closing book, receipt.opening_book)', 'field',
       'ingest (frankie_box_ingest_block)', _ROOT_PY, "opening_state, again = opening_books.load(opening_book['receipt'])",
       ('field', '{ingest_receipt}', 'opening_book'), compare='value'),
    _i('completion.json (sealed day completion)', 'receipt', 'ingest (frankie_box_ingest_block)', _ROOT_PY,
       "completion = json.loads(completion_path.read_bytes())", ('path', '{ingest}/completion.json')),
    _i('day-external.json (the 13 historical points)', 'file', 'day-external (frankie_box_day_external)', _ROOT_PY,
       "raw_external = ext_path.read_bytes()", ('path', '{ingest}/day-external.json')),
    _i('day-external-receipt.json', 'receipt', 'day-external (frankie_box_day_external)', _ROOT_PY,
       "raw_receipt = ext_receipt.read_bytes()", ('path', '{ingest}/day-external-receipt.json')),
    _i('day source manifest (blocks/BLOCK_<day>_SOURCE_MANIFEST.json)', 'file', 'repository (committed manifest)',
       _ROOT_PY, "own = BLOCKS / ('BLOCK_%s_SOURCE_MANIFEST.json' % day)", ('path', '{repo}/' + MANIFEST)),
    _i('frozen survivors (a confirmation day only)', 'file', 'survivors stage', _ROOT_PY,
       "if day_role == 'confirmation' and not (frozen_survivors", ('path', '{frozen_survivors}'),
       note='a discovery day takes none (not present)'),
    _i('ingest file-claims.jsonl (journal witness by claim)', 'claims', 'ingest (frankie_box_ingest_block)', _ROOT_PY,
       "for directory in (Path(journal).parent, Path(output_root) / 'work'):", ('path', '{ingest}/file-claims.jsonl'),
       klass='mechanism'),
    _i('run settings (day role, data workers, digest, bedrock, shared market policy)', 'setting',
       'orchestrator (frankie_box_experiment Run.root)', _ROOT_PY, "p.add_argument('--day-role', required=True",
       ('field', _SB, 'day_role'), compare='value', klass='mechanism'),
    _i('lane stop file (FRANKIE_LANE_STOP_FILE)', 'control', 'orchestrator', _ROOT_PY,
       "stop_file = os.environ.get('FRANKIE_LANE_STOP_FILE')", ('none',), klass='mechanism'),
    _i('retained derive.json / legacy-stage.json / spools (resume)', 'own state', 'ROOT itself', _ROOT_PY,
       "result = json.loads(retained.read_bytes())", ('path', _DERIVE), klass='own'),
    _i('retained work/file-claims.jsonl (resume)', 'own state', 'ROOT itself', _ROOT_PY,
       "claims, mode = _load_file_claims(session.work), _reuse_check_mode(LEGACY_REUSE_CHECK_SETTING)",
       ('path', '{attempt}/work/file-claims.jsonl'), klass='own'),
]

NATIVE_INPUTS['teacher'] = [
    _i('ingestion receipt', 'receipt', 'ingest (frankie_box_ingest_block)', _TEACHER_PY,
       "rc = json.loads(receipt_path.read_bytes())", ('path', '{ingest_receipt}')),
    _i('sealed journal (compact; the raw walk)', 'stream', 'ingest (frankie_box_ingest_block)', _TEACHER_PY,
       "reader = FrankieCompactReader(journal, expected_count=rc['journal_count']", ('journal', '{ingest_receipt}'),
       compare='pin', note='compared by pin (journal_bytes / journal_sha256)'),
    _i('day-external.json (resolved beside the sealed ingest)', 'file', 'day-external (frankie_box_day_external)',
       _TEACHER_PY, "day_file, day_sha, day_source = EXT.resolve_day_file(day_external, day_external_sha256, receipt_path)",
       ('path', '{ingest}/day-external.json')),
    _i('day-external-receipt.json (the day file\'s sha256)', 'receipt', 'day-external (frankie_box_day_external)',
       _EXT_PY, "receipt = Path(day_file).parent / 'day-external-receipt.json'",
       ('path', '{ingest}/day-external-receipt.json')),
    _i('experiment directive (EXPERIMENT_DIRECTIVE_V1.json)', 'file', 'repository (Greg\'s directive)', _TEACHER_PY,
       "research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json'", ('path', '{repo}/' + DIRECTIVE)),
] + _root_reader_inputs(_TEACHER_PY) + [
    _i('ingest file-claims.jsonl (journal prefetch by claim)', 'claims', 'ingest', _TEACHER_PY,
       "journal_prefetch = _journal_prefetch(receipt_path)", ('path', '{ingest}/file-claims.jsonl'), klass='mechanism'),
    _i('native cutoff limits (FRANKIE_NATIVE_CUTOFF_*)', 'setting', 'environment', _TEACHER_PY,
       "K.TeacherPassCarry(market, K.native_cutoff_limits(os.environ))", ('none',), klass='mechanism',
       note='instrumentation only (no cutoff: never stops the work)'),
    _i('retained teacher receipt / raw state / walk cache / carry / tracker (resume)', 'own state', 'teacher itself',
       _TEACHER_PY, "retained_receipt_path = out / 'receipt.json'", ('path', _TRC), klass='own'),
]

NATIVE_INPUTS['classroom'] = [
    _i('ROOT calculations-receipt.json', 'receipt', 'ROOT', _V2_PY,
       "receipt = json.loads((calculations / 'calculations-receipt.json').read_bytes())", ('path', _CR)),
    _i('ROOT source-binding.json', 'receipt', 'ROOT', _V2_PY,
       "source = json.loads((calculations / 'source-binding.json').read_bytes())", ('path', _SB)),
    _i('sealed journal (witness: the source binding\'s container pin)', 'stream', 'ingest', _V2_PY,
       "journal_pin = (source.get('container') or {})", ('pin', _SB, 'container'), compare='pin'),
    _i('Frankie\'s full-depth digest (work/derivation-digest-full.md; into his brain entry)', 'file', 'ROOT', _V2_PY,
       "if not (work / 'derivation-digest-full.md').is_file():", ('pin', _CR, 'digest'), compare='pin',
       note='compared by the ROOT receipt\'s digest pin'),
    _i('teacher receipt.json', 'receipt', 'teacher', _V2_PY,
       "teacher_receipt = json.loads((teacher_rows / 'receipt.json').read_bytes())", ('path', _TRC)),
    _i('teacher-attachment.pkl (the classroom package source)', 'file', 'teacher', _V2_PY,
       "attachment_raw = (teacher_rows / 'teacher-attachment.pkl').read_bytes()",
       ('pin_rel', _TRC, 'attachment_file', '{rows}'), filter=FILTERS['classroom']),
    _i('teacher receipt shared_market_identity / shared_market_read (identity check)', 'field', 'teacher', _V2_PY,
       "if (teacher_receipt.get('shared_market_identity') != market.identity", ('field', _TRC, 'shared_market_identity'),
       compare='value'),
    _i('day-external.json', 'file', 'day-external', _V2_PY,
       "day_file, day_sha, day_source = EXT.resolve_day_file(day_external, day_external_sha256,",
       ('path', '{ingest}/day-external.json')),
    _i('day-external-receipt.json', 'receipt', 'day-external', _V2_PY,
       "day_receipt = Path(day_file).parent / 'day-external-receipt.json'", ('path', '{ingest}/day-external-receipt.json')),
    _i('teacher external section (external-section/host-dipole-external-section.json)', 'file', 'teacher', _V2_PY,
       "section_directory=teacher_rows,", ('path', '{rows}/external-section/host-dipole-external-section.json')),
    _i('teacher external section receipt (external-section/receipt.json)', 'receipt', 'teacher', _V2_PY,
       "section_directory=teacher_rows,", ('path', '{rows}/external-section/receipt.json')),
    _i('teacher classroom-carry.pkl (the walk\'s anchor pictures)', 'file', 'teacher', _V2_PY,
       "carry = _load_raw_state(path)", ('path', '{rows}/classroom-carry.pkl')),
] + _root_reader_inputs(_V2_PY) + [
    _i('teacher rows sidecar (the second set, row by row)', 'stream', 'teacher', _K_PY,
       "lesson = TR.second_set_lesson(teacher_rows, directory / 'package.second_set.jsonl', snapshot_rows,",
       ('pin_rel', _TRC, 'rows_sidecar', '{rows}'), filter=FILTERS['classroom'], note='TR.second_set_lesson (K.second_set_lesson); plane values by reference to the '
                                         'ROOT stream rows listed above'),
    _i('teacher account (teacher-account.json)', 'file', 'teacher (frankie_box_teacher_findings)', _K_PY,
       "account_raw, md_raw = paths[0].read_bytes(), paths[1].read_bytes()", ('path', '{rows}/teacher-account.json'),
       filter=FILTERS['classroom']),
    _i('teacher account report (teacher-account.md)', 'file', 'teacher (frankie_box_teacher_findings)', _K_PY,
       "account_raw, md_raw = paths[0].read_bytes(), paths[1].read_bytes()", ('path', '{rows}/teacher-account.md'),
       filter=FILTERS['classroom']),
    _i('classroom rules (CLASSROOM_RULES_V3.json)', 'file', 'repository', _K_PY, "data = RULES_PATH.read_bytes()",
       ('path', '{repo}/' + RULES)),
    _i('experiment directive', 'file', 'repository', _V2_PY, "data = DIRECTIVE_PATH.read_bytes()",
       ('path', '{repo}/' + DIRECTIVE)),
    _i('brain entries (learner_knowledge, stage classroom)', 'brain entry', 'brain (every writer of entries)', _LS_PY,
       "for label, m, d in BR.entries_before(root, '00', day=day):", ('brain', 'classroom'), filter=FILTERS['classroom']),
    _i('brain school days (learner_school: earlier days)', 'brain entry', 'school', _LS_PY,
       "index = BR._school_index(root)['rows']", ('school', 'classroom'), filter=FILTERS['classroom']),
    _i('brain school index (school/index.json)', 'file', 'school', _BR_PY,
       "path = Path(brain) / SCHOOL_DIR / 'index.json'", ('path', '{brain}/school/index.json')),
    _i('brain correction records (corrections/*.json)', 'brain entry', 'review (frankie_box_experiment_review)', _REV_PY,
       "for path in sorted((Path(root) / 'corrections').glob('*.json')):", ('glob', '{brain}/corrections/*.json')),
    _i('knowledge versions (lane-state/knowledge/*/version.json)', 'file', 'lane state', _LS_PY,
       "return [json.loads(p.read_bytes()) for p in sorted((STATE / 'knowledge').glob('*/version.json'))]",
       ('glob', '{lane_state}/knowledge/*/version.json')),
    _i('frozen learned structure manifest (exhaustion/D facts)', 'file', 'brain', _K_PY,
       "frozen = brain / 'frozen-learned-structure' / 'MANIFEST.json'",
       ('path', '{brain}/frozen-learned-structure/MANIFEST.json')),
    _i('previous classroom day history.json (carry)', 'file', 'classroom (previous day)', _V2_PY,
       "history = json.loads((prev / 'history.json').read_bytes())", ('path', '{previous}/history.json')),
    _i('previous classroom day post-grade.json (carry)', 'file', 'classroom (previous day)', _V2_PY,
       "prior_grade = json.loads((prev / 'post-grade.json').read_bytes())", ('path', '{previous}/post-grade.json')),
    _i('previous classroom day external-history.json (carry)', 'file', 'classroom (previous day)', _V2_PY,
       "external_history = json.loads((prev / 'external-history.json').read_bytes())",
       ('path', '{previous}/external-history.json')),
    _i('previous classroom day external-post-grade.json (carry)', 'file', 'classroom (previous day)', _V2_PY,
       "prior_external_grade = json.loads((prev / 'external-post-grade.json').read_bytes())",
       ('path', '{previous}/external-post-grade.json')),
    _i('ingest file-claims.jsonl (journal witness by claim)', 'claims', 'ingest', _V2_PY, "ingest_claim = _holding_claim(",
       ('path', '{ingest}/file-claims.jsonl'), klass='mechanism'),
    _i('native cutoff limits (FRANKIE_NATIVE_CUTOFF_*)', 'setting', 'environment', _V2_PY,
       "native_limits = K.native_cutoff_limits(os.environ)", ('field', '{classroom}/receipt.json', ('received', 'native_cutoff')),
       compare='value', klass='mechanism', note='instrumentation only (no cutoff)'),
    _i('retained phase state / side saves / journal-witness.json (resume)', 'own state', 'classroom itself', _V2_PY,
       "state_path = d / 'phase-state.pkl'", ('path', '{classroom}/phase-state.pkl'), klass='own'),
]

NATIVE_INPUTS['exchange'] = [
    _i('teacher rows (host-dipole-classroom-source.c15.json)', 'file', 'teacher', _EX_PY,
       "snapshot, stream = TR.load(path)", ('pin_rel', _TRC, 'rows_file', '{rows}')),
    _i('teacher receipt.json (the cutoff: as_of / through_cursor, shared identity)', 'receipt', 'teacher', _AM_PY,
       "receipt_path = Path(rows_path).parent / 'receipt.json'", ('path', _TRC), filter=FILTERS['exchange']),
    _i('ingestion receipt (source_prefix_hash for the cutoff scope)', 'receipt', 'ingest', _AM_PY,
       "raw = Path(ingestion_pin['path']).read_bytes()", ('path', '{ingest_receipt}')),
    _i('teacher-kept cutoff context (shared-market-context.json beside the teacher receipt)', 'file', 'teacher', _AM_PY,
       "kept = Path(rows_path).parent / TEACHER_CONTEXT_NAME", ('path', '{rows}/shared-market-context.json'),
       filter=FILTERS['exchange']),
] + _root_reader_inputs(_AM_PY, filter=FILTERS['exchange']) + [
    _i('teacher rows sidecar (second set at the cutoff, leaf ledgers, the reading)', 'stream', 'teacher', _EX_PY,
       "at_cutoff, at_cutoff_why = AM.teacher_second_set_at_cutoff(rows_path, measure)",
       ('pin_rel', _TRC, 'rows_sidecar', '{rows}'), filter=FILTERS['exchange']),
    _i('teacher-second-set.pkl (the reading: pinned by the receipt)', 'file', 'teacher', _TR_PY,
       "path = rows_dir / (second.get('file') or SECOND_SET_PKL)", ('pin_rel', _TRC, 'teacher_second_set', '{rows}'),
       compare='pin'),
    _i('teacher-state-split.json', 'file', 'teacher', _TR_PY,
       "path = rows_dir / (split.get('day_file') or STATE_SPLIT_DAY_FILE)", ('path', '{rows}/teacher-state-split.json')),
    _i('teacher-second-set-mismatches.jsonl', 'file', 'teacher', _TR_PY, "guarded('mismatches_list'",
       ('path', '{rows}/teacher-second-set-mismatches.jsonl')),
    _i('teacher-book-event-differences.jsonl', 'file', 'teacher', _TR_PY, "guarded('book_event_differences_list'",
       ('path', '{rows}/teacher-book-event-differences.jsonl')),
    _i('teacher-reconciliation-differences.jsonl', 'file', 'teacher (frankie_box_teacher_findings)', _TR_PY,
       "guarded('reconciliation_differences_list'", ('path', '{rows}/teacher-reconciliation-differences.jsonl')),
    _i('teacher account (in the teacher receipt)', 'field', 'teacher', _TR_PY, "value = receipt.get('account')",
       ('field', _TRC, 'account'), compare='value'),
    _i('current-day lessons (Frankie\'s FRANKIE_LESSONS_V1)', 'file', 'teacher: scientific seat (lessons)', _EX_PY,
       "raw = Path(path).read_bytes()", ('path', '{lessons}/frankie/{day}-frankie.json')),
    _i('current-day lessons (Jev\'s)', 'file', 'teacher: scientific seat (lessons)', _EX_PY,
       "raw = Path(path).read_bytes()", ('glob', '{lessons}/jev/{day}-*.json')),
    _i('the day\'s search (MANIFEST.json; accumulated claim tests)', 'file', 'teacher: scientific seat (search)', _EX_PY,
       "accumulated_claim_tests = TK.teach_accumulated(a.day, a.search, a.brain", ('path', '{search}/MANIFEST.json')),
    _i('brain entries (learner_knowledge, stage exchange)', 'brain entry', 'brain', _EX_PY,
       "selected = LS.learner_knowledge(day, 'exchange', brain=brain)", ('brain', 'exchange'), filter=FILTERS['exchange']),
    _i('brain school days (learner_school, stage exchange)', 'brain entry', 'school', _EX_PY,
       "school, school_listed = LS.learner_school(day, brain=brain, versions=selected['versions'], stage='exchange')",
       ('school', 'exchange'), filter=FILTERS['exchange']),
    _i('brain correction records', 'brain entry', 'review', _REV_PY,
       "for path in sorted((Path(root) / 'corrections').glob('*.json')):", ('glob', '{brain}/corrections/*.json')),
    _i('classroom rules', 'file', 'repository', _EX_PY, "_, rules = K.rules()", ('path', '{repo}/' + RULES)),
    _i('teacher rows file-claims.jsonl (rows pin by claim)', 'claims', 'teacher', _EX_PY,
       "teacher_claim = _claimed_file_pin(path)", ('path', '{rows}/file-claims.jsonl'), klass='mechanism'),
    _i('retained learner-knowledge.json / ledger save / cutoff context (resume)', 'own state', 'exchange itself', _EX_PY,
       "knowledge = accumulated_lessons(day, run, lessons_paths, brain, input_path, rows_path, rules_witness)",
       ('path', '{exchange}/learner-knowledge.json'), klass='own'),
]

NATIVE_INPUTS['jev'] = [
    _i('classroom receipt (work/classroom/receipt.json)', 'receipt', 'classroom', _JEV_PY,
       "classroom = json.loads(classroom_path.read_bytes())", ('path', '{classroom}/receipt.json')),
    _i('Jev material (jev-material/classroom-request.json)', 'file', 'classroom', _JEV_PY,
       "material_request = json.loads(material_path.read_bytes())", ('path', '{attempt}/jev-material/classroom-request.json'),
       filter=FILTERS['jev']),
    _i('the day\'s search MANIFEST.json', 'file', 'teacher: scientific seat (search)', _JEV_PY,
       "search_manifest = json.loads(search_path.read_bytes())", ('path', '{search}/MANIFEST.json')),
    _i('exchange\'s retained cutoff context (shared-market-context.json)', 'file', 'exchange', _JEV_PY,
       "exchange_retained = out.parents[3] / 'exchange' / request['day'] / 'shared-market-context.json'",
       ('path', '{exchange}/shared-market-context.json'), filter=FILTERS['jev']),
] + _root_reader_inputs(_AM_PY, filter=FILTERS['jev']) + [
    _i('exchange.json (claim names for the second set)', 'file', 'exchange', _JEV_PY,
       "texts = [p.read_text(errors='replace') for p in (exchange_dir / 'exchange.json'", ('path', '{exchange}/exchange.json')),
    _i('exchange-frankie.json (claim names for the second set)', 'file', 'exchange', _JEV_PY,
       "texts = [p.read_text(errors='replace') for p in (exchange_dir / 'exchange.json'",
       ('path', '{exchange}/exchange-frankie.json')),
    _i('teacher rows sidecar (second set to his cutoff)', 'stream', 'teacher', _JEV_PY,
       "second = AM.jev_second_set(teacher_dir, cut['through_cursor']", ('pin_rel', _TRC, 'rows_sidecar', '{rows}'),
       filter=FILTERS['jev']),
    _i('day-external.json (external.* planes at the cutoff)', 'file', 'day-external', _JEV_PY,
       "day_file = ((classroom.get('external') or {}).get('day_file') or {}).get('path')",
       ('path', '{ingest}/day-external.json'), filter=FILTERS['jev']),
    _i('Frankie\'s ledgers.json (after the blind seal)', 'file', 'classroom', _JEV_PY,
       "paths = {'ledgers': classroom_path.parent / 'ledgers.json'", ('path', '{classroom}/ledgers.json'),
       filter=FILTERS['jev']),
    _i('Frankie\'s external-code-answers.json (after the blind seal)', 'file', 'classroom', _JEV_PY,
       "'external_ledgers': classroom_path.parent / 'external-code-answers.json'",
       ('path', '{classroom}/external-code-answers.json'), filter=FILTERS['jev']),
    _i('Frankie\'s out/analysis.md (after the blind seal)', 'file', 'classroom', _JEV_PY,
       "'analysis': classroom_path.parents[2] / 'out' / 'analysis.md'", ('path', '{attempt}/out/analysis.md'),
       filter=FILTERS['jev']),
    _i('Jev-only peer knowledge (brain/jev-peer/*)', 'brain entry', 'jev (previous turns)', _JEV_PY,
       "for manifest_path in sorted((Path(root) / 'jev-peer').glob('*/MANIFEST.json')):", ('jevpeer',),
       filter=FILTERS['jev']),
    _i('Jev\'s own brain (jev-brain/entries, jev-brain/lessons)', 'brain entry', 'jev (previous turns)', _JEV_PY,
       "for path in sorted((jev_brain / kind).glob('*.json')):", ('glob', '{jev_brain}/*/*.json'), filter=FILTERS['jev']),
    _i('brain <day>-jev-tested/stage-knowledge.json (delivery readback)', 'brain entry', 'jev / scientific teacher',
       _JEV_PY, "frankie_knowledge = brain / (request['day'] + '-jev-tested') / 'stage-knowledge.json'",
       ('path', '{brain}/{day}-jev-tested/stage-knowledge.json')),
    _i('brain correction records', 'brain entry', 'review', _REV_PY,
       "for path in sorted((Path(root) / 'corrections').glob('*.json')):", ('glob', '{brain}/corrections/*.json')),
    _i('Jev request (JEV_CPU_REQUEST_V1)', 'control', 'orchestrator (Run.jev)', _JEV_PY,
       "request = json.loads(request_path.read_bytes())", ('path', '{jev_request}'), klass='mechanism'),
    _i('model runtime config (Granite under llama.cpp)', 'runtime', 'setup (frankie_box_granite_meeting_setup)', _JEV_PY,
       "runtime_path = pinned(request['runtime'])", ('none',), klass='mechanism'),
    _i('retained second-set-at-cutoff.json / material.json / client-config.json / state (resume)', 'own state',
       'jev itself', _JEV_PY, "second_path = out / 'second-set-at-cutoff.json'",
       ('path', '{jev_out}/second-set-at-cutoff.json'), klass='own'),
]

_SCHOOL_CLASSWORK = ('code-answers.json', 'ledgers.json', 'external-code-answers.json', 'novel-findings.json',
                     'correction-response.json', 'acknowledgement.json', 'external-correction-response.json',
                     'external-acknowledgement.json', 'completion.json', 'external-completion.json')
NATIVE_INPUTS['school'] = [
    _i('classroom receipt', 'receipt', 'classroom', _SCH_PY,
       "receipt = json.loads(receipt_path.read_bytes()) if receipt_path.is_file() else {}",
       ('path', '{classroom}/receipt.json')),
] + [_i('classroom %s' % f, 'file', 'classroom', _SCH_PY, "fw.whole(name, classroom / file)",
        ('path', '{classroom}/' + f)) for f in _SCHOOL_CLASSWORK] + [
    _i('classroom correction-request.json (corrections received)', 'file', 'classroom (teacher\'s corrections)', _SCH_PY,
       "fw.subset(name, path, corrections(json.loads(path.read_bytes())),", ('path', '{classroom}/correction-request.json')),
    _i('classroom external-correction-request.json', 'file', 'classroom (teacher\'s corrections)', _SCH_PY,
       "fw.subset(name, path, corrections(json.loads(path.read_bytes())),",
       ('path', '{classroom}/external-correction-request.json')),
    _i('teacher rows (pointer)', 'file', 'teacher', _SCH_PY, "bt.pointer('dipole_rows', rows_dir / TEACHER_ROWS_FILE",
       ('pin_rel', _TRC, 'rows_file', '{rows}'), compare='pin'),
    _i('teacher receipt.json (whole)', 'receipt', 'teacher', _SCH_PY,
       "bt.whole('teacher_rows_receipt', rows_dir / 'receipt.json'", ('path', _TRC)),
    _i('teacher rows sidecar (pointer)', 'stream', 'teacher', _SCH_PY, "bt.pointer('rows_sidecar', TR.sidecar_of(rows_dir)",
       ('pin_rel', _TRC, 'rows_sidecar', '{rows}'), compare='pin'),
    _i('BOSS teacher second-set reading (teacher-second-set-read.boss.json)', 'file', 'teacher (knowledge step)', _SCH_PY,
       "bt.whole('boss_teacher_second_set_reading', rows_dir / TR.READING_FILES['boss_teacher']",
       ('path', '{rows}/teacher-second-set-read.boss.json')),
    _i('classroom package.second_set.jsonl (pointer)', 'stream', 'classroom', _SCH_PY,
       "bt.pointer('second_set_rows', classroom / 'package.second_set.jsonl'",
       ('path', '{classroom}/package.second_set.jsonl')),
    _i('classroom package.second_set.json', 'file', 'classroom', _SCH_PY,
       "second_path = classroom / 'package.second_set.json'", ('path', '{classroom}/package.second_set.json')),
    _i('classroom package.teacher_key.c15.json (identity only)', 'file', 'classroom (teacher key)', _SCH_PY,
       "key_path = classroom / 'package.teacher_key.c15.json'", ('path', '{classroom}/package.teacher_key.c15.json'),
       filter=FILTERS['school']),
    _i('classroom novelty-investigation.json', 'file', 'teacher (novelty investigation)', _SCH_PY,
       "bt.whole('novelty_investigation', classroom / 'novelty-investigation.json'",
       ('path', '{classroom}/novelty-investigation.json')),
    _i('exchange-frankie.json (the exchange view)', 'file', 'exchange', _SCH_PY,
       "view = json.loads(Path(exchange_view).read_bytes())", ('path', '{exchange}/exchange-frankie.json')),
    _i('Frankie\'s lessons of the day', 'file', 'teacher: scientific seat (lessons)', _SCH_PY,
       "doc = sc.whole('frankie_lessons', lessons,", ('path', '{lessons}/frankie/{day}-frankie.json')),
    _i('scientific teacher second-set reading (experiment-teacher/teacher-second-set/<day>.json)', 'file',
       'teacher: scientific seat', _SCH_PY, "Path('/opt/frankie-box/work/experiment-teacher') / 'teacher-second-set'",
       ('path', '{lessons}/teacher-second-set/{day}.json')),
    _i('the meeting record (meeting/<day>/meeting.json)', 'file', 'exchange (voice / meeting)', _BR_PY,
       "path, receipt_path = directory / 'meeting.json', directory / 'receipt.json'", ('path', '{meeting}/meeting.json')),
    _i('the meeting receipt (meeting/<day>/receipt.json)', 'receipt', 'exchange (voice / meeting)', _BR_PY,
       "path, receipt_path = directory / 'meeting.json', directory / 'receipt.json'", ('path', '{meeting}/receipt.json')),
    _i('day-external-receipt.json (S3 key of the day file pointer)', 'receipt', 'day-external', _SCH_PY,
       "s3 = json.loads(Path(day_file['receipt']).read_bytes()).get('s3_key')",
       ('path', '{ingest}/day-external-receipt.json')),
    _i('day-external.json (pointer)', 'file', 'day-external', _SCH_PY, "df.pointer('day_external', day_file['path']",
       ('path', '{ingest}/day-external.json')),
    _i('brain school index (school/index.json)', 'file', 'school (previous days)', _BR_PY,
       "path = Path(brain) / SCHOOL_DIR / 'index.json'", ('path', '{brain}/school/index.json')),
    _i('brain correction records', 'brain entry', 'review', _REV_PY,
       "for path in sorted((Path(root) / 'corrections').glob('*.json')):", ('glob', '{brain}/corrections/*.json')),
    _i('pointer digests by claim (file-claims.jsonl beside each pointer)', 'claims', 'each producer', _SCH_PY,
       "row = BR.file_claims(Path(path).parent).get((observed.st_ino, observed.st_size, observed.st_mtime_ns))",
       ('path', '{rows}/file-claims.jsonl'), klass='mechanism'),
]

_SCI_PY = 'deploy/aws/box/frankie_box_scientific_teacher.py'
_Q_PY = 'deploy/aws/box/frankie_box_frankie_queue.py'
_X_PY = 'deploy/aws/box/frankie_box_experiment.py'
_REP_PY = 'deploy/aws/box/frankie_box_experiment_day_reports.py'

# teacher-2: the teacher's second turn (the hub map, HUB_CALC_ORDER_MAP_20261009.md section 6 turn 4): Frankie's lessons
# (frankie_box_frankie_queue.frankie_lessons -> frankie_box_scientific_teacher.sh with FRANKIE_LEDGERS / SEARCHES; the
# batch lessons call the same for a non-queued day) and the novelty investigation (computed today inside the classroom
# process, frankie_box_experiment_classroom_v2.py, on the package key and his novel findings).
NATIVE_INPUTS['teacher-2'] = [
    _i('Frankie\'s ledgers.json (only dipole_novel_findings, R09)', 'file', 'classroom', _SCI_PY,
       "findings = ledgers.get('dipole_novel_findings') or []", ('path', '{classroom}/ledgers.json'),
       filter=None, note='located by frankie_box_frankie_queue.frankie_lessons (ledgers = Path(c[\'classroom\']) / '
                         '\'ledgers.json\')'),
    _i('Frankie\'s external-code-answers.json (the external novel findings)', 'file', 'classroom', _SCI_PY,
       "source_raw = source_path.read_bytes()", ('path', '{classroom}/external-code-answers.json')),
    _i('external-novel-findings.json (the retained projection, when present)', 'file', 'classroom', _SCI_PY,
       "projection_path = Path(path).with_name('external-novel-findings.json')",
       ('path', '{classroom}/external-novel-findings.json')),
    _i('every finished discovery-day search MANIFEST.json (SEARCHES)', 'file', 'teacher: scientific seat (search)',
       _SCI_PY, "manifest_raw = (d / 'MANIFEST.json').read_bytes()",
       ('glob', '{search_root}/*/cycle-' + CYCLE + '/' + SEARCH_ROLE + '/MANIFEST.json'),
       note='the searched days: frankie_box_frankie_queue.frankie_lessons (searched = every finished discovery search)'),
    _i('the searches\' coupling parts (MANIFEST couplings.parts, pinned)', 'stream', 'teacher: scientific seat (search)',
       _SCI_PY, "for pin in manifest['couplings']['parts']:", ('manifest_parts', '{search_root}/*/cycle-' + CYCLE + '/'
                                                                 + SEARCH_ROLE + '/MANIFEST.json'), compare='pin'),
    _i('completed native evidence of the searched day: ROOT native receipt', 'file', 'ROOT', _SCI_PY,
       "NATIVE_ROLES = ('receipt', 'result', 'bedrock_section_4_2', 'bedrock_section_4_4')",
       ('pin', _DERIVE, ('bedrock', 'receipt')), compare='pin'),
    _i('completed native evidence: ROOT native result.json', 'file', 'ROOT', _SCI_PY,
       "NATIVE_ROLES = ('receipt', 'result', 'bedrock_section_4_2', 'bedrock_section_4_4')",
       ('pin', _DERIVE, ('bedrock', 'result')), compare='pin'),
] + [_i('completed native evidence: ROOT %s.json.gz' % n, 'file', 'ROOT', _SCI_PY,
        "NATIVE_ROLES = ('receipt', 'result', 'bedrock_section_4_2', 'bedrock_section_4_4')",
        ('pin', _DERIVE, ('layers', n)), compare='pin') for n in NATIVE_SECTIONS] + [
    _i('completed native evidence: ROOT %s (FINALIZE rows)' % n, 'stream', 'ROOT', _SCI_PY,
       "NATIVE_LEDGERS = ('native.member', 'native.lifecycle')", ('pin', _DERIVE, ('bedrock', 'ledgers', n)),
       compare='pin') for n in NATIVE_LEDGERS[:2]] + [
    _i('brain <day>-teacher/stage-knowledge.json (names the teacher rows)', 'brain entry', 'teacher (knowledge step)',
       _SCI_PY, "entry = root / ('%s-teacher' % day) / 'stage-knowledge.json'",
       ('path', '{brain}/{day}-teacher/stage-knowledge.json')),
    _i('teacher receipt.json (its second set reading)', 'receipt', 'teacher', _SCI_PY,
       "record, pin, how = TR.second_set_reading_file(Path(rows).parent, target, 'scientific_teacher')", ('path', _TRC)),
    _i('teacher rows sidecar (the whole second set, streamed)', 'stream', 'teacher', _SCI_PY,
       "record, pin, how = TR.second_set_reading_file(Path(rows).parent, target, 'scientific_teacher')",
       ('pin_rel', _TRC, 'rows_sidecar', '{rows}')),
    _i('teacher-second-set.pkl (pinned by the receipt)', 'file', 'teacher', _TR_PY,
       "path = rows_dir / (second.get('file') or SECOND_SET_PKL)", ('pin_rel', _TRC, 'teacher_second_set', '{rows}'),
       compare='pin'),
    _i('teacher-state-split.json', 'file', 'teacher', _TR_PY,
       "path = rows_dir / (split.get('day_file') or STATE_SPLIT_DAY_FILE)", ('path', '{rows}/teacher-state-split.json')),
    _i('teacher-second-set-mismatches.jsonl', 'file', 'teacher', _TR_PY, "guarded('mismatches_list'",
       ('path', '{rows}/teacher-second-set-mismatches.jsonl')),
    _i('teacher-book-event-differences.jsonl', 'file', 'teacher', _TR_PY, "guarded('book_event_differences_list'",
       ('path', '{rows}/teacher-book-event-differences.jsonl')),
    _i('teacher-reconciliation-differences.jsonl', 'file', 'teacher (frankie_box_teacher_findings)', _TR_PY,
       "guarded('reconciliation_differences_list'", ('path', '{rows}/teacher-reconciliation-differences.jsonl')),
    _i('novelty investigation: the package teacher key (package.teacher_key.c15.json)', 'file',
       'classroom (the package split off the teacher attachment)', _V2_PY,
       "novelty = phase('novelty_investigation', lambda: F.investigate_novel_findings(pkg['teacher_key']",
       ('path', '{classroom}/package.teacher_key.c15.json'),
       note='today computed in memory inside the classroom process from pkg[\'teacher_key\']; the file is the same key'),
    _i('novelty investigation: his novel findings validated against the pre-message (package.pre_message.c15.json)',
       'file', 'classroom', _V2_PY,
       "novel = phase('novel_findings', lambda: F.validate_novel_findings(response.get('dipole_novel_findings')",
       ('path', '{classroom}/package.pre_message.c15.json')),
    _i('novelty investigation: the mode and learning policy (package.binding.c15.json)', 'file', 'classroom', _V2_PY,
       "novelty = phase('novelty_investigation', lambda: F.investigate_novel_findings(pkg['teacher_key']",
       ('path', '{classroom}/package.binding.c15.json')),
    _i('brain correction records', 'brain entry', 'review', _REV_PY,
       "for path in sorted((Path(root) / 'corrections').glob('*.json')):", ('glob', '{brain}/corrections/*.json')),
    _i('knowledge versions (lane-state/knowledge/*/version.json)', 'file', 'lane state', _LS_PY,
       "return [json.loads(p.read_bytes()) for p in sorted((STATE / 'knowledge').glob('*/version.json'))]",
       ('glob', '{lane_state}/knowledge/*/version.json')),
    _i('the run\'s search step receipts (which searches finished)', 'control', 'orchestrator (Run.record)', _Q_PY,
       "s = run.receipt('search', day)", ('path', '{run_dir}/days/{day}/search.json'), klass='mechanism'),
    _i('retained lessons (lessons_written: an already-written frankie-<day> lesson is reused)', 'own state',
       'teacher-2 itself', _Q_PY, "written = run.lessons_written('frankie-%s' % day, searched, frankie_ledgers=ledgers)",
       ('path', '{lessons}/frankie/{day}-frankie.json'), klass='own'),
]

_REPORT_JSON = ('code-answers.json', 'ledgers.json', 'post-grade.json', 'novel-findings.json', 'novelty-investigation.json',
                'correction-request.json', 'correction-response.json', 'acknowledgement.json', 'completion.json',
                'external-code-answers.json', 'external-post-grade.json', 'external-correction-request.json',
                'external-correction-response.json', 'external-acknowledgement.json', 'external-completion.json',
                'package.external.pre_message.json')
# reports: frankie_box_experiment_day_reports.py (run once after Jev under the hub; every piece one-way in)
NATIVE_INPUTS['reports'] = [
    _i('classroom receipt.json', 'receipt', 'classroom', _REP_PY, "raw = self._read('classroom receipt', receipt_path)",
       ('path', '{classroom}/receipt.json')),
] + [_i('classroom %s' % f, 'file', 'classroom', _REP_PY, "self.docs[name] = json.loads(self._read(name, path))",
        ('path', '{classroom}/' + f)) for f in _REPORT_JSON] + [
    _i('classroom.md (the dropped findings)', 'file', 'classroom', _REP_PY, "path = self.dir / 'classroom.md'",
       ('path', '{classroom}/classroom.md')),
    _i('Frankie\'s brain entry MANIFEST.json (<day>-cycle-00)', 'brain entry', 'classroom (brain publication)', _REP_PY,
       "raw = self._read('brain MANIFEST', path)", ('path', '{brain}/{day}-cycle-' + CYCLE + '/MANIFEST.json')),
    _i('exchange.json', 'file', 'exchange', _REP_PY, "raw = self._read('exchange', exchange)",
       ('path', '{exchange}/exchange.json')),
    _i('exchange-frankie.json', 'file', 'exchange', _REP_PY,
       "frankie_view = json.loads(self._read('exchange-frankie view', frankie_path))", ('path', '{exchange}/exchange-frankie.json')),
    _i('exchange receipt.json', 'receipt', 'exchange', _REP_PY,
       "doc, seen, why = _json_once(d, 'exchange receipt', Path(exchange_path).with_name('receipt.json'))",
       ('path', '{exchange}/receipt.json')),
    _i('the meeting record (meeting/<day>/meeting.json)', 'file', 'exchange (meeting)', _REP_PY,
       "self.meeting = read_meeting_for_exchange(frankie_path)", ('path', '{meeting}/meeting.json')),
    _i('the meeting receipt (meeting/<day>/receipt.json)', 'receipt', 'exchange (meeting)', _REP_PY,
       "self.meeting = read_meeting_for_exchange(frankie_path)", ('path', '{meeting}/receipt.json')),
    _i('ROOT calculations-receipt.json', 'receipt', 'ROOT', _REP_PY,
       "load('receipt', self.root_dir / PA.ROOT_FIELDS['receipt'])", ('path', _CR)),
    _i('ROOT derive.json', 'file', 'ROOT', _REP_PY, "load('derive', self.root_dir / PA.ROOT_FIELDS['derive'])",
       ('pin', _CR, 'derivation'), compare='pin'),
    _i('ROOT native runtime-workers-receipt.json', 'receipt', 'ROOT (native pass)', _REP_PY,
       "for role in ('workers', 'gates'):", ('glob', '{attempt}/work/*/runtime-workers-receipt.json')),
    _i('ROOT native pre-traversal-gates.json', 'receipt', 'ROOT (native pass)', _REP_PY,
       "for role in ('workers', 'gates'):", ('glob', '{attempt}/work/*/pre-traversal-gates.json')),
    _i('teacher receipt.json (the TEACHER REPORT renders its account)', 'receipt', 'teacher', _REP_PY,
       "raw = self._read('teacher receipt', path)", ('path', _TRC)),
    _i('BOSS teacher second-set reading (teacher-second-set-read.boss.json)', 'file', 'teacher (knowledge step)', _REP_PY,
       "doc, why = kept('BOSS teacher second-set reading', path)", ('path', '{rows}/teacher-second-set-read.boss.json')),
    _i('scientific teacher second-set reading (experiment-teacher/teacher-second-set/<day>.json)', 'file',
       'teacher-2 (lessons)', _REP_PY, "for path in [LESSONS_ROOT / 'teacher-second-set' / ('%s.json' % d.day)] + (",
       ('path', '{lessons}/teacher-second-set/{day}.json')),
    _i('accumulated reader\'s second-set reading (scientific-knowledge/<day>/teacher-second-set-read.json)', 'file',
       'exchange (accumulated claim tests)', _REP_PY,
       "[Path(run_dir) / 'scientific-knowledge' / str(d.day) / 'teacher-second-set-read.json'] if run_dir else []",
       ('path', '{run_dir}/scientific-knowledge/{day}/teacher-second-set-read.json')),
    _i('Frankie\'s lessons file (all99_coverage)', 'file', 'teacher-2 (lessons)', _REP_PY,
       "mine = LESSONS_ROOT / 'frankie' / ('%s-frankie.json' % d.day)", ('path', '{lessons}/frankie/{day}-frankie.json')),
    _i('carried claims receipt (scientific-knowledge/<day>/receipt.json)', 'receipt', 'accumulated lessons', _REP_PY,
       "doc, seen, why = _json_once(d, 'carried claims receipt', given)",
       ('path', '{run_dir}/scientific-knowledge/{day}/receipt.json')),
    _i('candidates receipt (experiment-survivors/<run>/<day>/receipt.json)', 'receipt', 'survivors', _REP_PY,
       "given = piece_receipts.get('candidates') or (SURVIVORS / run_name / d.day / 'receipt.json')",
       ('path', '{survivors}/{run}/{day}/receipt.json')),
    _i('the day\'s search MANIFEST.json (external points)', 'file', 'teacher: scientific seat (search)', _REP_PY,
       "manifest, mseen, mwhy = _json_once(d, 'search MANIFEST', Path(step['target']) / 'MANIFEST.json')",
       ('path', '{search}/MANIFEST.json')),
    _i('Jev receipt.json', 'receipt', 'jev', _REP_PY, "jev, jseen, jwhy = _json_once(d, 'Jev receipt', given)",
       ('path', '{jev_out}/receipt.json')),
    _i('Jev client-receipt.json', 'receipt', 'jev', _REP_PY,
       "client, cseen, cwhy, cbad = _pinned_once(d, 'Jev client receipt', jev.get('client_receipt'))",
       ('path', '{jev_out}/client-receipt.json')),
    _i('the school file (<brain>/school/<day>.json)', 'file', 'school', _REP_PY, "raw = self._read('school file', path)",
       ('path', '{brain}/school/{day}.json')),
    _i('the school index (school/index.json)', 'file', 'school', _REP_PY,
       "index = json.loads(self._read('school index', index_path))", ('path', '{brain}/school/index.json')),
    _i('orchestrator step receipts <run>/days/<day>/<stage>.json (each piece\'s all99 list and pins)', 'receipt',
       'orchestrator (Run.record)', _REP_PY, "path = Path(run_dir) / 'days' / d.day / (stage + '.json')",
       ('glob', '{run_dir}/days/{day}/*.json', 'jev-request-*.json'),
       note='the all-99 join reads each piece\'s list through these records; no hub piece publishes them'),
    _i('stage heartbeats <run>/days/<day>/progress/<stage>.jsonl', 'stream', 'each stage (frankie_box_stage_progress)',
       _REP_PY, "progress = self.run_dir / 'days' / str(self.day) / 'progress'",
       ('glob', '{run_dir}/days/{day}/progress/*.jsonl'), klass='mechanism',
       note='instrumentation the piece accounts render (seconds, heartbeats), not a calculation input'),
    _i('reports index / save / earlier revision (resume)', 'own state', 'reports itself', _REP_PY,
       "path = reports / 'index.json'", ('path', '{reports_dir}/index.json'), klass='own'),
]

NATIVE_INPUTS['forecaster'] = []        # no consumer yet: the go-live last spoke (the hub feeds the forecaster)
FORECASTER_NOTE = 'no consumer yet: the forecaster is the go-live last spoke; nothing reads the hub for it today'


# ---------------------------------------------------------------------------------------------------------------------
# inventory (with the line of each reading code found now)

def _line_of(at, anchor, cache={}):
    """'path:line' of the anchor in the repo file (the first occurrence), else 'path:?' with the reason."""
    path = REPO / at
    if at not in cache:
        try:
            cache[at] = path.read_text(encoding='utf-8')
        except OSError:
            cache[at] = None
    text = cache[at]
    if text is None:
        return '%s:? (file not found)' % at
    where = text.find(anchor)
    if where < 0:
        return '%s:? (anchor not found: %r)' % (at, anchor[:60])
    return '%s:%d' % (at, text.count('\n', 0, where) + 1)


def inventory(piece=None):
    """Every native input (of one piece or all), each with reads_at = 'repo-file:line' found now."""
    out = {}
    for name in ([piece] if piece else PIECES):
        rows = []
        for item in NATIVE_INPUTS[name]:
            row = {k: v for k, v in item.items() if k != 'anchor'}
            row['reads_at'] = _line_of(item['at'], item['anchor'])
            row['locate'] = list(item['locate'])
            rows.append(row)
        out[name] = rows
    return out


# ---------------------------------------------------------------------------------------------------------------------
# the day's sources (the box directories of one run/day)

def _json(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        return None


def dig(doc, path):
    """The value at a dotted path or a tuple of keys; (found, value)."""
    keys = path if isinstance(path, (tuple, list)) else str(path).split('.')
    value = doc
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and str(key).isdigit() and int(key) < len(value):
            value = value[int(key)]
        else:
            return False, None
    return True, value


def _newest(paths):
    paths = [p for p in paths if p.exists()]
    return max(paths, key=lambda p: (p.stat().st_mtime_ns, str(p))) if paths else None


def day_sources(day, run=None, *, attempt=None, previous=None, frozen_survivors=None, roots=None):
    """The resolved directories and files of one run/day (absent ones None, with `listed` naming why)."""
    r = dict(DEFAULT_ROOTS, **{k: Path(v) for k, v in (roots or {}).items() if v})
    s = dict(day=str(day), run=run, listed=[], roots={k: str(v) for k, v in r.items()})
    if attempt is None:
        pattern = '%s-%s-a*' % (run, day) if run else '*-%s-a*' % day
        found = [p for p in Path(r['experiment_roots']).glob(pattern) if re.search(r'-a[0-9]+$', p.name)]
        attempt = max(found, key=lambda p: int(re.search(r'-a([0-9]+)$', p.name).group(1))) if found else None
        if attempt is None:
            s['listed'].append('no ROOT attempt %s under %s' % (pattern, r['experiment_roots']))
    s['attempt'] = Path(attempt) if attempt else None
    binding = _json(s['attempt'] / 'source-binding.json') if s['attempt'] else None
    ingest = ((binding or {}).get('ingestion_receipt') or {}).get('path')
    s['ingest_receipt'] = Path(ingest) if ingest else None
    s['ingest'] = s['ingest_receipt'].parent if ingest else None
    if not ingest:
        s['listed'].append('the ROOT source binding names no ingestion receipt')
    s['rows'] = Path(r['teacher_rows']) / str(day)
    s['classroom'] = s['attempt'] / 'work' / 'classroom' if s['attempt'] else None
    s['run_dir'] = Path(r['runs']) / run if run else None
    s['exchange'] = s['run_dir'] / 'exchange' / str(day) if run else None
    s['meeting'] = s['run_dir'] / 'meeting' / str(day) if run else None
    jev_days = s['run_dir'] / 'days' / str(day) if run else None
    s['jev_out'] = _newest(list((jev_days / 'jev').glob('*'))) if jev_days and (jev_days / 'jev').is_dir() else None
    s['jev_request'] = _newest(list(jev_days.glob('jev-request-*.json'))) if jev_days and jev_days.is_dir() else None
    s['search'] = Path(r['search']) / str(day) / ('cycle-' + CYCLE) / SEARCH_ROLE
    s['lessons'] = Path(r['lessons'])
    s['search_root'] = Path(r['search'])
    s['survivors'], s['reports_dir'] = Path(r['survivors']), Path(r['reports'])
    s['brain'], s['jev_brain'], s['lane_state'], s['repo'] = (Path(r['brain']), Path(r['jev_brain']),
                                                               Path(r['lane_state']), Path(r['repo']))
    if previous is None and s['classroom'] is not None:
        receipt = _json(s['classroom'] / 'receipt.json') or {}
        for path in (('consumers', 'carry', 'previous', 'directory'), ('received', 'carry', 'previous', 'directory'),
                     ('carry', 'previous', 'directory')):
            ok, value = dig(receipt, path)
            if ok and value:
                previous = value
                break
    s['previous'] = Path(previous) if previous else None
    s['frozen_survivors'] = Path(frozen_survivors) if frozen_survivors else None
    return s


def _fill(template, sources):
    """The template with the sources filled in, or (None, why) when one it names is absent."""
    try:
        values = {k: v for k, v in sources.items() if v is not None and not isinstance(v, (list, dict))}
        return template.format(**values), None
    except KeyError as error:
        return None, 'the day has no %s' % error.args[0]


def _pin_path(pin, base):
    if not isinstance(pin, dict):
        return None
    if pin.get('path'):
        return Path(pin['path'])
    if pin.get('file') and base is not None:
        return Path(base) / pin['file']
    return None


# ---------------------------------------------------------------------------------------------------------------------
# resolve: a native input -> the concrete things on disk the piece reads

def resolve(item, sources):
    """[{label, path?, pin?, value?, present, reason?}] for one native input on this day. Reads small receipts only
    (to find pins and fields); never a data file whole."""
    loc = item['locate']
    op = loc[0]
    if op == 'none':
        return [dict(label=item['name'], present=False, reason='not a file or field on disk (a setting or control)')]
    if op == 'path':
        path, why = _fill(loc[1], sources)
        if path is None:
            return [dict(label=item['name'], present=False, reason=why)]
        p = Path(path)
        return [dict(label=item['name'], path=str(p), present=p.is_file(), reason=None if p.is_file() else 'not on disk')]
    if op == 'glob':
        pattern, why = _fill(loc[1], sources)
        if pattern is None:
            return [dict(label=item['name'], present=False, reason=why)]
        base = Path(pattern)
        anchor = Path(base.anchor)
        found = sorted(p for p in anchor.glob(str(base.relative_to(anchor))) if p.is_file()
                       and not (len(loc) > 2 and fnmatch.fnmatch(p.name, loc[2])))
        if not found:
            return [dict(label=item['name'], present=False, reason='nothing matches %s' % pattern)]
        return [dict(label='%s [%s]' % (item['name'], p.name), path=str(p), present=True) for p in found]
    if op in ('pin', 'pin_rel', 'field', 'journal'):
        doc_path, why = _fill(loc[1], sources)
        if doc_path is None:
            return [dict(label=item['name'], present=False, reason=why)]
        doc = _json(doc_path)
        if doc is None:
            return [dict(label=item['name'], present=False, reason='%s is not on disk or not JSON' % doc_path)]
        if op == 'journal':
            if not doc.get('journal_file'):
                return [dict(label=item['name'], present=False, reason='the receipt names no journal_file')]
            p = Path(doc_path).parent / doc['journal_file']
            pin = dict(path=str(p), bytes=doc.get('journal_bytes'), sha256=doc.get('journal_sha256'))
            return [dict(label=item['name'], path=str(p), pin=pin, present=p.exists(),
                         reason=None if p.exists() else 'not on disk')]
        ok, value = dig(doc, loc[2])
        if not ok:
            return [dict(label=item['name'], present=False, reason='%s carries no %s' % (doc_path, loc[2]))]
        if op == 'field':
            return [dict(label=item['name'], container=doc_path, field=loc[2], value=value, present=True)]
        base = None
        if op == 'pin_rel':
            base, why = _fill(loc[3], sources)
        p = _pin_path(value, base)
        if p is None:
            return [dict(label=item['name'], present=False,
                         reason='%s %s is not a pin (%s)' % (doc_path, loc[2], json.dumps(value, default=str)[:120]))]
        pin = dict(path=str(p), bytes=value.get('bytes'), sha256=value.get('sha256'))
        return [dict(label=item['name'], path=str(p), pin=pin, present=p.exists(),
                     reason=None if p.exists() else 'pinned but not on disk')]
    if op in ('brain', 'school'):
        return _brain_items(item, sources, op, loc[1])
    if op == 'manifest_parts':
        pattern, why = _fill(loc[1], sources)
        if pattern is None:
            return [dict(label=item['name'], present=False, reason=why)]
        base = Path(pattern)
        anchor = Path(base.anchor)
        found = []
        for manifest_path in sorted(anchor.glob(str(base.relative_to(anchor)))):
            m = _json(manifest_path) or {}
            for pin in ((m.get('couplings') or {}).get('parts') or []):
                p = manifest_path.parent / str(pin.get('path'))
                found.append(dict(label='%s [%s/%s]' % (item['name'], manifest_path.parent.parent.parent.name,
                                                         pin.get('path')),
                                  path=str(p), pin=dict(path=str(p), bytes=pin.get('bytes'), sha256=pin.get('sha256')),
                                  present=p.is_file()))
        return found or [dict(label=item['name'], present=False, reason='no search part pinned under %s' % pattern)]
    if op == 'jevpeer':
        found = []
        for manifest_path in sorted(Path(sources['brain']).glob('jev-peer/*/MANIFEST.json')):
            m = _json(manifest_path) or {}
            for e in m.get('entries') or []:
                p = manifest_path.parent / str(e.get('name'))
                found.append(dict(label='%s [%s/%s]' % (item['name'], manifest_path.parent.name, e.get('name')),
                                  path=str(p), pin=dict(path=str(p), bytes=e.get('bytes'), sha256=e.get('sha256')),
                                  present=p.is_file()))
        return found or [dict(label=item['name'], present=False, reason='no Jev peer knowledge in the brain')]
    return [dict(label=item['name'], present=False, reason='unknown locate %r' % (op,))]


def _brain_items(item, sources, op, stage):
    """The brain files the stage's own reader can select (frankie_box_lane_state.learner_knowledge / learner_school
    walls copied: same-day later stages, same-day teacher entries outside TEACH), each with its manifest pin."""
    import frankie_box_brain as BR
    brain, day = Path(sources['brain']), sources['day']
    mode = ((_json(sources['classroom'] / 'receipt.json') or {}).get('mode')
            if sources.get('classroom') is not None else None)
    before = {'root': -20, 'teacher': -10, 'classroom': 0, 'search': 10, 'lessons': 20, 'exchange': 40, 'voice': 40,
              'meeting': 45, 'school': 50}.get(stage, 100)
    out = []
    if op == 'school':
        index = (_json(brain / BR.SCHOOL_DIR / 'index.json') or {}).get('rows') or []
        for row in index:
            if str(row.get('day')) == day:
                continue                               # this classroom cannot consume its own end-of-day school answers
            p = brain / BR.SCHOOL_DIR / str(row.get('file'))
            out.append(dict(label='%s [%s]' % (item['name'], row.get('file')), path=str(p), present=p.is_file(),
                            pin=dict(path=str(p), bytes=row.get('bytes'), sha256=row.get('sha256'))))
        return out or [dict(label=item['name'], present=False, reason='no earlier school day in the index')]
    own = BR.entry_name(day, CYCLE)
    dirs = sorted({p for pattern in BR.ENTRY_GLOBS for p in brain.glob(pattern) if p.is_dir()}) if brain.is_dir() else []
    for d in dirs:
        parsed = BR.parse_entry_name(d.name)
        manifest = _json(d / 'MANIFEST.json')
        if parsed is None or manifest is None or d.name == own:
            continue
        eday, kind = parsed
        if eday == day and stage == 'classroom' and kind in ('teacher', 'teacher-account') and mode != 'TEACH':
            continue
        if eday == day and (BR.DAY_KINDS.get(kind, 0) > before or kind.isdigit() and before <= 0):
            continue
        for e in manifest.get('entries') or []:
            if not e.get('include'):
                continue
            p = d / str(e.get('name'))
            out.append(dict(label='%s [%s/%s]' % (item['name'], d.name, e.get('name')), path=str(p), present=p.is_file(),
                            pin=dict(path=str(p), bytes=e.get('bytes'), sha256=e.get('sha256'))))
    return out or [dict(label=item['name'], present=False, reason='no brain entry the %s reader selects' % stage)]


# ---------------------------------------------------------------------------------------------------------------------
# the hub side: pinned sources, the knowledge store, each piece's publications; send_set

def _sha256_small(path, hash_max=HASH_MAX):
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError:
        return None, None, 'not on disk'
    if hash_max is not None and size > hash_max:
        return size, None, 'not hashed by the spoke (over %d bytes); the comparison streams it' % hash_max
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return size, h.hexdigest(), 'hashed by the spoke'


def _file_addition(name, kind, producer, path, *, pin=None, hash_max=HASH_MAX, known_by=None):
    """A reference addition for a file: the producer's pin when it recorded one (no hashing), else hashed when small."""
    path = Path(os.path.abspath(str(path)))
    if not path.exists() or not path.is_file():
        return None
    if pin and pin.get('sha256'):
        size, sha, basis = pin.get('bytes'), pin['sha256'], 'the producer\'s pin'
        if size is None:
            size = path.stat().st_size
    else:
        size, sha, basis = _sha256_small(path, hash_max)
    add = dict(kind=kind, name=name, producer=producer, path=str(path), bytes=size, sha256=sha, content_sha256=sha,
               sha256_basis=basis)
    if known_by is not None:
        add['known_by'] = known_by
    return add


def _value_addition(name, kind, producer, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()
    return dict(kind=kind, name=name, producer=producer, value=value, content_sha256=hashlib.sha256(raw).hexdigest())


def _files_in(directory, patterns=('*.json', '*.jsonl', '*.md', '*.pkl', '*.gz')):
    d = Path(directory) if directory else None
    if d is None or not d.is_dir():
        return []
    return sorted({p for pat in patterns for p in d.glob(pat) if p.is_file() and not p.name.endswith('.pending')})


def pinned_sources(sources, hash_max=HASH_MAX):
    """hub.json's pinned sources: the sealed day (ingestion receipt, journal by its pin, completion, opening book), the
    day file and its receipt, the committed day manifest, the directive and the classroom rules, the previous classroom
    day's carry and the frozen survivors when the day has them, the orchestrator's step receipts of the day and the
    survivors candidates receipt (sealed_records)."""
    out, ing = [], sources.get('ingest_receipt')
    rc = _json(ing) if ing else None
    def add(a):
        if a is not None:
            out.append(a)
    if ing:
        add(_file_addition('ingestion receipt', 'receipt', 'ingest', ing, hash_max=hash_max))
    if rc:
        if rc.get('journal_file'):
            add(_file_addition('sealed journal', 'stream', 'ingest', Path(ing).parent / rc['journal_file'],
                               pin=dict(bytes=rc.get('journal_bytes'), sha256=rc.get('journal_sha256')), hash_max=hash_max))
        own = rc.get('opening_book_file') or {}
        if own.get('file'):
            add(_file_addition('opening book beside the journal', 'file', 'ingest', Path(ing).parent / own['file'],
                               pin=own, hash_max=hash_max))
    if sources.get('ingest'):
        for name in ('completion.json', 'day-external.json', 'day-external-receipt.json'):
            add(_file_addition(name, 'file', 'ingest' if name == 'completion.json' else 'day-external',
                               Path(sources['ingest']) / name, hash_max=hash_max))
    repo = Path(sources['repo'])
    add(_file_addition('day source manifest', 'file', 'repository', repo / MANIFEST.format(day=sources['day']),
                       hash_max=hash_max))
    add(_file_addition('experiment directive', 'file', 'repository', repo / DIRECTIVE, hash_max=hash_max))
    add(_file_addition('classroom rules', 'file', 'repository', repo / RULES, hash_max=hash_max))
    if sources.get('previous'):
        for p in _files_in(sources['previous'], ('history.json', 'post-grade.json', 'external-history.json',
                                                 'external-post-grade.json')):
            add(_file_addition('previous classroom carry ' + p.name, 'file', 'classroom (previous day)', p,
                               hash_max=hash_max))
    if sources.get('frozen_survivors'):
        add(_file_addition('frozen survivors', 'file', 'survivors stage', sources['frozen_survivors'], hash_max=hash_max))
    for a in sealed_records(sources, hash_max)[0]:
        add(a)
    return out


# The orchestrator's sealed step receipts of a day (frankie_box_experiment.Run.record: <run>/days/<day>/<stage>.json;
# frankie_box_experiment.STAGES plus the day-keyed records the queue writes) and the survivors stage's candidates receipt
# (frankie_box_survivor_update: experiment-survivors/<run>/<day>/receipt.json). Coordinator's decision, 2026-10-09: the hub
# CARRIES both as pinned base references (not spokes); every one present by reference, an absent one listed, never fatal.
STEP_RECEIPT_STAGES = ('fetch', 'ingest', 'external', 'root', 'teacher', 'classroom', 'jev', 'data', 'search', 'lessons',
                       'exchange', 'voice', 'school', 'reports', 'accumulated_lessons', 'frankie_lessons')


def sealed_records(sources, hash_max=HASH_MAX):
    """(additions, absent): every step receipt present under <run>/days/<day>/ (any <stage>.json there, the Jev request
    excluded: it is the Jev stage's own request, not a step receipt) and the survivors candidates receipt, by reference;
    absent = [{name, path, status: 'absent', reason}] for each expected one not on disk."""
    out, absent = [], []
    run_dir, run, day = sources.get('run_dir'), sources.get('run'), sources['day']
    if run_dir is not None:
        days = Path(run_dir) / 'days' / day
        present = sorted(p for p in days.glob('*.json') if p.is_file() and not fnmatch.fnmatch(p.name, 'jev-request-*'))
        for p in present:
            a = _file_addition('orchestrator step receipt ' + p.name, 'receipt', 'orchestrator (Run.record)', p,
                               hash_max=hash_max)
            if a is not None:
                out.append(a)
        names = {p.stem for p in present}
        absent += [dict(name='orchestrator step receipt %s.json' % st, path=str(days / (st + '.json')), status='absent',
                        reason='no %s step receipt for this day (the stage has not recorded, or is batch-keyed)' % st)
                   for st in STEP_RECEIPT_STAGES if st not in names]
    else:
        absent.append(dict(name='orchestrator step receipts', path=None, status='absent', reason='no run named'))
    if run and sources.get('survivors') is not None:
        cand = Path(sources['survivors']) / run / day / 'receipt.json'
        a = _file_addition('survivors candidates receipt', 'receipt', 'survivors stage', cand, hash_max=hash_max)
        if a is not None:
            out.append(a)
        else:
            absent.append(dict(name='survivors candidates receipt', path=str(cand), status='absent',
                               reason='the survivors stage has written no candidates receipt for this day'))
    return out, absent


def knowledge_store(sources, hash_max=HASH_MAX):
    """The knowledge store the hub carries (whole, unfiltered; each reader's wall applies on its own read): every
    included member of every brain entry by its manifest pin, the school index and days, the correction records, the
    frozen learned structure manifest, the knowledge versions, Jev's peer knowledge and Jev's own brain."""
    out = []
    brain = Path(sources['brain'])
    try:
        import frankie_box_brain as BR
        dirs = sorted({p for pattern in BR.ENTRY_GLOBS for p in brain.glob(pattern) if p.is_dir()}) \
            if brain.is_dir() else []
        school_dir = BR.SCHOOL_DIR
    except Exception:  # noqa: BLE001 - without the brain module the entries are listed by their manifests alone
        dirs = sorted(p.parent for p in brain.glob('*/MANIFEST.json')) if brain.is_dir() else []
        school_dir = 'school'
    for d in dirs:
        manifest = _json(d / 'MANIFEST.json') or {}
        if (d / 'MANIFEST.json').is_file():
            out.append(_file_addition('brain entry %s/MANIFEST.json' % d.name, 'brain entry', 'brain', d / 'MANIFEST.json',
                                      hash_max=hash_max))
        for e in manifest.get('entries') or []:
            a = _file_addition('brain entry %s/%s' % (d.name, e.get('name')), 'brain entry', 'brain', d / str(e.get('name')),
                               pin=dict(bytes=e.get('bytes'), sha256=e.get('sha256')), hash_max=hash_max)
            if a is not None:
                a['include'] = bool(e.get('include'))
                out.append(a)
    index = brain / school_dir / 'index.json'
    if index.is_file():
        out.append(_file_addition('brain school index', 'file', 'school', index, hash_max=hash_max))
        for row in (_json(index) or {}).get('rows') or []:
            a = _file_addition('brain school day %s' % row.get('file'), 'brain entry', 'school',
                               brain / school_dir / str(row.get('file')),
                               pin=dict(bytes=row.get('bytes'), sha256=row.get('sha256')), hash_max=hash_max)
            if a is not None:
                out.append(a)
    for p in sorted(brain.glob('corrections/*.json')):
        out.append(_file_addition('brain correction ' + p.name, 'brain entry', 'review', p, hash_max=hash_max))
    frozen = brain / 'frozen-learned-structure' / 'MANIFEST.json'
    if frozen.is_file():
        out.append(_file_addition('frozen learned structure manifest', 'file', 'brain', frozen, hash_max=hash_max))
    for p in sorted(Path(sources['lane_state']).glob('knowledge/*/version.json')):
        out.append(_file_addition('knowledge version ' + p.parent.name, 'file', 'lane state', p, hash_max=hash_max))
    for manifest_path in sorted(brain.glob('jev-peer/*/MANIFEST.json')):
        for e in (_json(manifest_path) or {}).get('entries') or []:
            a = _file_addition('jev peer %s/%s' % (manifest_path.parent.name, e.get('name')), 'brain entry', 'jev',
                               manifest_path.parent / str(e.get('name')),
                               pin=dict(bytes=e.get('bytes'), sha256=e.get('sha256')), hash_max=hash_max)
            if a is not None:
                out.append(a)
    search_root = sources.get('search_root')
    if search_root is not None:
        # the run's searches of every day (the scientific seat tests claims over all of them): each MANIFEST.json and
        # the coupling parts it pins, by the manifest's pins
        for manifest_path in sorted(Path(search_root).glob('*/cycle-%s/%s/MANIFEST.json' % (CYCLE, SEARCH_ROLE))):
            day_name = manifest_path.parents[2].name
            out.append(_file_addition('search %s MANIFEST.json' % day_name, 'file', 'teacher: scientific seat (search)',
                                      manifest_path, hash_max=hash_max))
            for pin in ((_json(manifest_path) or {}).get('couplings') or {}).get('parts') or []:
                out.append(_file_addition('search %s %s' % (day_name, pin.get('path')), 'stream',
                                          'teacher: scientific seat (search)', manifest_path.parent / str(pin.get('path')),
                                          pin=dict(bytes=pin.get('bytes'), sha256=pin.get('sha256')), hash_max=hash_max))
    for p in sorted(Path(sources['jev_brain']).glob('*/*.json')):
        out.append(_file_addition('jev brain %s/%s' % (p.parent.name, p.name), 'brain entry', 'jev', p,
                                  hash_max=hash_max))
    return [a for a in out if a is not None]


def publications(piece, sources, hash_max=HASH_MAX):
    """The additions a piece contributes to the hub (its outputs on disk), by reference, with the producer's own pins
    where it recorded them. The run_spoke calc placeholder returns these."""
    out = []
    def add(a):
        if a is not None:
            out.append(a)
    if piece == 'root':
        a = sources.get('attempt')
        if a is None:
            return out
        cr = _json(a / 'calculations-receipt.json') or {}
        derive = _json(a / 'work' / 'derive.json') or {}
        for name in ('calculations-receipt.json', 'source-binding.json'):
            add(_file_addition('ROOT ' + name, 'receipt', 'ROOT', a / name, hash_max=hash_max))
        for key in ('calculation_pins', 'external_computation', 'derivation', 'digest'):
            pin = cr.get(key)
            p = _pin_path(pin, a)
            if p is not None:
                add(_file_addition('ROOT %s' % key, 'file', 'ROOT', p, pin=pin, hash_max=hash_max))
        for role, pin in sorted((cr.get('shared_market_sources') or {}).items()):
            p = _pin_path(pin, a) if (pin or {}).get('status') != 'absent' else None
            if p is not None:
                add(_file_addition('ROOT %s spool' % role, 'stream', 'ROOT', p, pin=pin, hash_max=hash_max))
        native = derive.get('bedrock') if isinstance(derive.get('bedrock'), dict) else {}
        for name, pin in sorted((native.get('ledgers') or {}).items()):
            p = _pin_path(pin, a)
            if p is not None:
                add(_file_addition('ROOT native ledger ' + name, 'stream', 'ROOT', p, pin=pin, hash_max=hash_max))
        for key in ('result', 'receipt'):
            p = _pin_path(native.get(key), a)
            if p is not None:
                add(_file_addition('ROOT native ' + key, 'file', 'ROOT', p, pin=native.get(key), hash_max=hash_max))
        for name, pin in sorted((derive.get('layers') or {}).items()):
            p = _pin_path(pin, a)
            if p is not None:
                add(_file_addition('ROOT layer ' + name, 'file', 'ROOT', p, pin=pin, hash_max=hash_max))
        for name in ('native-layer-records.json', 'native-overlap.json'):
            add(_file_addition('ROOT ' + name, 'file', 'ROOT', a / 'work' / name, hash_max=hash_max))
        for name in ('runtime-workers-receipt.json', 'pre-traversal-gates.json'):
            for p in sorted((a / 'work').glob('*/' + name)) + sorted((a / 'work').glob('*/*/' + name)):
                add(_file_addition('ROOT native ' + '/'.join(p.parts[-2:]), 'receipt', 'ROOT (native pass)', p,
                                   hash_max=hash_max))
        return out
    if piece == 'teacher':
        rows = Path(sources['rows'])
        rc = _json(rows / 'receipt.json') or {}
        add(_file_addition('teacher receipt.json', 'receipt', 'teacher', rows / 'receipt.json', hash_max=hash_max))
        for key in ('rows_file', 'rows_sidecar', 'attachment_file', 'teacher_second_set', 'classroom_carry'):
            pin = rc.get(key) if isinstance(rc.get(key), dict) else None
            p = _pin_path(pin, rows)
            if p is not None:
                add(_file_addition('teacher ' + key, 'file', 'teacher', p, pin=pin, hash_max=hash_max))
        second = rc.get('teacher_second_set') if isinstance(rc.get('teacher_second_set'), dict) else {}
        split = second.get('state_split') if isinstance(second.get('state_split'), dict) else {}
        add(_file_addition('teacher state split', 'file', 'teacher', rows / (split.get('day_file') or
                                                                            'teacher-state-split.json'),
                           pin=dict(sha256=split.get('day_file_sha256')) if split.get('day_file_sha256') else None,
                           hash_max=hash_max))
        for name in ('teacher-second-set-mismatches.jsonl', 'teacher-book-event-differences.jsonl',
                     'teacher-reconciliation-differences.jsonl', 'teacher-account.json', 'teacher-account.md',
                     'shared-market-context.json', 'teacher-second-set-read.boss.json'):
            add(_file_addition('teacher ' + name, 'file', 'teacher', rows / name, hash_max=hash_max))
        for p in _files_in(rows / 'external-section'):
            add(_file_addition('teacher external-section/' + p.name, 'file', 'teacher', p, hash_max=hash_max))
        if isinstance(rc.get('account'), dict):
            add(_value_addition('teacher account (receipt.account)', 'field', 'teacher', rc['account']))
        # the scientific seat of the one teacher core: the day's search and lessons
        search = Path(sources['search'])
        for p in _files_in(search, ('MANIFEST.json', 'knowledge-findings.json', 'knowledge-review-*.json')):
            add(_file_addition('teacher (scientific seat) search ' + p.name, 'file', 'teacher: scientific seat', p,
                               hash_max=hash_max))
        return out
    if piece == 'teacher-2':
        # the teacher's second turn: Frankie's lessons (FRANKIE_LESSONS_V1), the scientific seat's reading of the second
        # set, Jev's lessons of the day when the batch lessons have written them; the novelty investigation is on disk
        # in the classroom directory today (published with the classroom) until it moves to this turn
        lessons, day = Path(sources['lessons']), sources['day']
        for p in [lessons / 'frankie' / ('%s-frankie.json' % day)] + sorted((lessons / 'jev').glob('%s-*.json' % day)) + \
                [lessons / 'teacher-second-set' / ('%s.json' % day)]:
            add(_file_addition('teacher-2 (lessons) ' + '/'.join(p.parts[-2:]), 'file', 'teacher-2: scientific seat',
                               p, hash_max=hash_max))
        brain = Path(sources['brain'])
        for p in sorted(brain.glob('%s-lessons/*' % day)):
            add(_file_addition('teacher-2 brain %s-lessons/%s' % (day, p.name), 'brain entry', 'teacher-2', p,
                               hash_max=hash_max))
        return out
    if piece == 'classroom':
        c, a = sources.get('classroom'), sources.get('attempt')
        for p in _files_in(c):
            if p.name.startswith('side-') or p.name == 'phase-state.pkl':
                continue                                  # the classroom's own resume state, never a publication
            add(_file_addition('classroom ' + p.name, 'file', 'classroom', p, hash_max=hash_max))
        if a is not None:
            add(_file_addition('classroom jev material', 'file', 'classroom', a / 'jev-material' / 'classroom-request.json',
                               hash_max=hash_max))
            for p in _files_in(a / 'out', ('*.md', '*.json')):
                add(_file_addition('classroom out/' + p.name, 'file', 'classroom', p, hash_max=hash_max))
        return out
    if piece == 'exchange':
        run_dir, day = sources.get('run_dir'), sources['day']
        if run_dir is not None:
            for p in _files_in(Path(run_dir) / 'scientific-knowledge' / day, ('*.json',)):
                add(_file_addition('exchange accumulated ' + p.name, 'file', 'exchange (accumulated claim tests)', p,
                                   hash_max=hash_max))
        for p in _files_in(sources.get('exchange'), ('*.json',)):
            add(_file_addition('exchange ' + p.name, 'file', 'exchange', p, hash_max=hash_max))
        for p in _files_in(sources.get('meeting'), ('*.json',)):
            add(_file_addition('exchange meeting ' + p.name, 'file', 'exchange (meeting)', p, hash_max=hash_max))
        return out
    if piece == 'jev':
        for p in _files_in(sources.get('jev_out'), ('*.json', '*.md')):
            add(_file_addition('jev ' + p.name, 'file', 'jev', p, hash_max=hash_max))
        return out
    if piece == 'school':
        brain, day = Path(sources['brain']), sources['day']
        add(_file_addition('school day %s.json' % day, 'brain entry', 'school', brain / 'school' / ('%s.json' % day),
                           hash_max=hash_max))
        return out
    if piece == 'reports':
        rd, run, day = sources.get('reports_dir'), sources.get('run'), sources['day']
        if rd is not None and run:
            add(_file_addition('reports receipt', 'receipt', 'reports', Path(rd) / 'receipts' / run / ('%s.json' % day),
                               hash_max=hash_max))
            receipt = _json(Path(rd) / 'receipts' / run / ('%s.json' % day)) or {}
            for value in (receipt.get('written') or {}).values() if isinstance(receipt.get('written'), dict) else []:
                if isinstance(value, str) and Path(value).is_file():
                    add(_file_addition('report ' + Path(value).name, 'file', 'reports', value, hash_max=hash_max))
        return out
    return out                                   # forecaster: no publication yet


def prerequisites():
    """{piece: (pieces it needs this round)}: the hub core's own table (frankie_box_hub.PREREQUISITES) restricted to
    PIECES, else the copy above."""
    try:
        table = dict(_hub().PREREQUISITES)
    except Exception:  # noqa: BLE001 - the core not importable: the copy
        table = dict(_PREREQUISITES_FALLBACK)
    return {p: tuple(q for q in table.get(p, ()) if q in PIECES and q != p) for p in PIECES}


def before(piece, table=None):
    """The pieces whose write is guaranteed in the hub at `piece`'s turn: its prerequisites, transitively (listing
    order)."""
    table = table or prerequisites()
    seen, stack = set(), list(table.get(piece, ()))
    while stack:
        q = stack.pop()
        if q not in seen:
            seen.add(q)
            stack.extend(table.get(q, ()))
    return [p for p in PIECES if p in seen]


def hub_set(sources, upto=None, hash_max=HASH_MAX):
    """The merged hub set at a piece's turn: the pinned sources, the knowledge store and the publications of every
    piece the hub core guarantees has written before it (its prerequisites, transitively). upto=None: everything."""
    out = [dict(a, group='pinned source') for a in pinned_sources(sources, hash_max)]
    out += [dict(a, group='knowledge store') for a in knowledge_store(sources, hash_max)]
    for piece in (PIECES if upto is None else before(upto)):
        out += [dict(a, group='publication of ' + piece) for a in publications(piece, sources, hash_max)]
    return out


def send_set(piece, sources, hash_max=HASH_MAX):
    """The hub additions `piece` would RECEIVE: the merged hub set at its turn, by reference, each carrying the piece's
    filter rule as a field (stated, not applied: the piece's own rule applies on read, as today)."""
    if piece not in PIECES:
        raise ValueError('unknown piece %r' % piece)
    rule = FILTERS[piece]
    return [dict(a, filter=rule, receiver=piece) for a in hub_set(sources, upto=piece, hash_max=hash_max)]


# ---------------------------------------------------------------------------------------------------------------------
# the spoke turn (through the hub core; not called by anything yet)

def _hub():
    try:
        import frankie_box_hub as H
    except ImportError:
        from deploy.aws.box import frankie_box_hub as H
    return H


def run_spoke(piece, hub_dir, sources, *, pid=None):
    """One read-calc-write turn of `piece` under the hub's turn lock: take_turn (a waiter is recorded and woken by the
    holder's release), read the hub set, calc (placeholder: the piece's own outputs on disk, by reference), write the
    additions, release. Returns {piece, token, read, written}. Not called by the workflow yet."""
    H = _hub()
    token = H.take_turn(hub_dir, piece, pid=pid if pid is not None else os.getpid())
    try:
        received = H.read(hub_dir, piece, token)
        additions = publications(piece, sources, hash_max=None) if piece != 'forecaster' else [
            _value_addition('forecaster', 'note', 'forecaster', FORECASTER_NOTE)]
        H.write(hub_dir, piece, token, additions)
        return dict(piece=piece, token=token, read=received, written=len(additions))
    finally:
        H.release(hub_dir, piece, token)


def open_day_hub(hub_root, sources, hash_max=HASH_MAX):
    """open_hub with this day's pinned sources, every piece and the hub core's default prerequisites (so nothing is
    listed in prerequisites_dropped)."""
    pins = [{k: a.get(k) for k in ('name', 'path', 'bytes', 'sha256')} for a in pinned_sources(sources, hash_max)]
    pins += sealed_records(sources, hash_max)[1]                  # the absent sealed records, listed on their pins
    H = _hub()
    table = {p: list(q) for p, q in prerequisites().items()}      # the core's default table over these pieces
    return H.open_hub(hub_root, sources.get('run'), sources['day'], pins, pieces=list(PIECES), prerequisites=table)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Print the spokes\' native-input inventory (JSON).')
    ap.add_argument('--piece', choices=PIECES)
    a = ap.parse_args()
    print(json.dumps(dict(schema=SPOKES_SCHEMA, inventory=inventory(a.piece), filters=FILTERS), indent=1, sort_keys=True))
