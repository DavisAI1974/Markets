"""The experiment orchestrator: one box-side run over a list of days, calling the existing steps in order.

Brief piece A (CHATGPT_BRIEF_EXPERIMENT_20260929.md), built by Claude on Greg's word ("I'm going to have you do
chatgpts part", 2026-09-29). Spec: research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md ("How the orchestrator
runs", "Days", "The classroom arm", "The teacher's Dipole rows: 1 day in 5"). It re-implements no step; each step is
the committed box script, run as a child with its own inputs, its output kept in a log beside its receipt:

  fetch    frankie_box_ingest_block.sh ACTION=fetch   (MAP_URL presigns every partition of the days; run this stage on
           its own while the short-lived URLs are live; a day whose sealed ingest exists is skipped)
  ingest   frankie_box_ingest_block.sh ACTION=ingest  (one day at a time: the script checks out the commit into the box's
           ingest checkout; never Monday 20211004, the gold standard: its sealed ingest is found, never rebuilt)
  external frankie_box_day_external.sh ACTION=build|link (Frankie's historical data points, the day file
           FRANKIE_DAY_EXTERNAL_V1, attached beside the day's sealed ingest; reads S3 only through the dispatch's
           presigned map: getprefix frankie/day_history/<EXTERNAL_HISTORY_RUN>/ and nymex/ng_fut_parent_v0/, put slots
           frankie/day_external/<day>/day-external.json and day-external-receipt.json. A day whose history or curve is not
           in the map yet WAITS, listed: the day is never skipped, and a day file is never built without its pieces)
  root     frankie_box_experiment_root.sh             (every NEW run: SHARED_MARKET_POLICY with the native pass on, --bedrock
           on, so native.member/native.lifecycle exist for the 99; an older saved plan keeps its legacy bedrock-off ROOT;
           DIGEST=on)
  teacher  frankie_box_experiment_teacher.sh DAYS=... (the Dipole rows, 1 day in 5: a batch of up to five days, each its
           own walk; a day whose rows exist is skipped; while the script is not built the batch stops here, listed;
           it takes the day file beside the sealed ingest and builds the BOSS teacher's external section)
  classroom frankie_box_experiment_classroom_v2.sh    (classroom-arm days only, after root + teacher: the 19/171 classroom
           plus the external section; the arm days one after another in plan order, each carrying the previous arm
           day's work/classroom as PREVIOUS; the run's first arm day carries the latest earlier classroom day on the box,
           or the plan's previous_classroom)
           The day's report number N is reserved right after its classroom step (done, reused or refused), where the
           reports used to run, so the numbering is unchanged (frankie_box_experiment_day_reports.reserve_number)
  jev      frankie_box_jev_cpu.sh JEV_REQUEST=...     (classroom-arm discovery days: an ordinary stage of the day on the
           day's WHOLE held lane like every other stage (Greg, 2026-10-07 night; 32 CPUs on a 32-CPU day), llama-server
           threads from frankie_box_jev_cpu.JEV_THREADS (32, clamped to the lane), every other runtime row from Granite's
           shared definition; no box, host, Pod or relay of its own. Older
           receipts of the retired relay (waiting_for_pod) are read as they are and stay pending)
  data     frankie_box_experiment_data.sh ACTION=export
  search   frankie_box_experiment_search.sh
  lessons  frankie_box_scientific_teacher.sh          (after each batch: every discovery-day search of the run so far,
           the committed historical claims, and Jev's / Frankie's claims where the plan names them; on a classroom-arm
           day whose plan names no ledgers, Frankie's claims are the novel findings of that day's classroom ledgers.json,
           R09: the teacher reads nothing else of it; a call whose lessons file is already there is reused, not re-run)
  exchange frankie_box_experiment_exchange.sh         (classroom-arm discovery days, after the batch's lessons and the
           day's search: the three-way exchange, SPEC-scientific-teacher.md step 5. Per scientific-teacher result on a
           claim that tested the day: the BOSS teacher's turn from its own Dipole rows (targets, masks, controls), the
           scientific teacher's reply with the search counts, Frankie's reply by his code; the teachers' own findings
           filed, scoped, day named. Receipt and files under <run>/exchange/<day>/; Frankie's view into his brain as
           <day>-exchange. Code only)
  voice    frankie_box_granite_meeting.sh: the bounded CPU post-class coordinator (role V2), with immediate brain
           publication, inside the day's held booking on the WHOLE lane like Jev (Greg, 2026-10-07 night), llama-server
           threads from MEETING_THREADS (default the lane size). A missing/refused runtime is recorded as non-blocking;
           completed records are reused.
  school   frankie_box_school_knowledge.sh            (classroom-arm days after the exchange; never Monday 20211004):
           Frankie's SCHOOL KNOWLEDGE BASE, ONE file <brain>/school/<day>.json (FRANKIE_SCHOOL_KNOWLEDGE_V1) and its row
           in <brain>/school/index.json (day, file, sha256, bytes, report number N); the brain loader and the next
           classroom day read every earlier day's file
  reports  frankie_box_experiment_day_reports.sh      (classroom-arm days, after the exchange; Greg, 2026-09-29: "make
           sure classroom is printing out an analysis after every day has gone through it, and same with Frankie, and
           have them number their reports"; "There will be (3) #1's and so on"; "Write plain language interpreters to
           their code. I don't want you making interpretations"): reads the day's classroom outputs and its exchange and
           writes CLASSROOM REPORT #N and FRANKIE REPORT #N (N reserved after the classroom, shared with that day's JEV
           REPORT #N) into /opt/frankie-box/work/experiment-reports/ and the classroom dir, printed in full here and in
           its log. Reports written before the day's exchange existed are rebuilt once it does (a revision, same N). A
           report failure is recorded (retried on the next start) and never stops the run

FRANKIE'S FIFO QUEUE (frankie_box_frankie_queue.py; Greg, 2026-09-29: "I don't want any days dropped and moved forward
because he was busy"; "order by first in the pod first out the pod or box"; "Class days are sequential"). Two lines on the
box, each arrival-order FIFO (enqueued_at, then a monotonic seq): nothing dropped, skipped or reordered.
  ROOT line  (--root-queue on, the default): a day enters the moment its sealed ingest and day file are there
             (root_enqueue, after its external step and again at the root stage); days leave in arrival order to the next
             free day-run slot (a box slot, or a Pod through the root claims); this run's root stage then waits for its own
             days (bounded by --queue-worker-seconds; re-kicking the ROOT worker), so the plan order no longer decides ROOT
             order. --root-queue off: the ROOTs run here in plan order, as before.
  CLASS line (--frankie-queue on, the default, classroom-arm days): a day enters the moment its ROOT (digest) and teacher
             rows are done and its day file is attached (classroom_ready, the classroom step's own checks: enqueue_classroom);
             the one class worker runs classroom, frankie_lessons, exchange, voice, school and reports for ONE day at a
             time, carries the last class to finish (previous_of), gives each class its school-day number = its position in
             the class line = its report number N, and polls a waiting day instead of ending. This run then records the
             day's classroom as queued and leaves its class side to the worker (queue_owned). --frankie-queue off: the
             classroom side runs here as before, still one class at a time on the box (class-running.lock).
Every start kicks both workers (detached, bounded; a second worker of a line exits at once). Probe:
frankie_box_frankie_queue.sh ACTION=show (read-only, both lines).

NO DATA IS DROPPED (Greg, 2026-09-29): incomplete data never stops the run or skips a day. A calculation that cannot
use a piece of data (missing, incomplete) skips over that piece, and the step says what it skipped and why; every
other day and step goes on. So a day's gap is recorded on that day's steps and the rest runs:
  a day with no manifest and no sealed ingest: its fetch and ingest wait (listed); its later steps wait on the ingest;
  a day with no Dipole rows (the teacher batch not built or failed for it): exported and searched without them, the
    Dipole listed missing in its receipts (a later search with the rows would be a second search of the day: declined,
    so the receipt names it);
  a ROOT with producer failures: calculations_retained_with_failures, the failures listed, the day goes on;
  a day whose day file is not attached yet (history not on S3, or not presigned): its external step waits and so do its
    root, teacher, classroom, data and search (each reads the day file; a step run without it could not be run again:
    duplicate data); the ingest-only steps of every day go on. EXTERNAL_WAIT=off lets them run without it (listed).
WALLS (rules, not data gaps; each listed with its reason). Days are never pooled and classes never mix: a day of
another class than the run's is left out of this run (weekday: monday, midweek = Tue/Wed, thursday, friday; holidays
not modelled). All October 2021-2025 days share the discovery/learning route (Greg 2026-10-06, amended R15);
completed knowledge is usable in workflow order irrespective of market date. Days outside the assigned years/month
are listed separately. The older saved-plan confirmation route remains historical, not the new experiment. Duplicate data
declines the run: a day listed twice; two sealed ingests or two finished ROOTs of one day decline that day's step,
naming both. No model call, no Granite, no Pod.

CPU BOOKING (Greg, 2026-09-29: "Correct 16 and no double booking"; "They all get the same 16 and workers so we wait
until 16 are available"). Every day-run step (root, teacher, classroom, data, search, lessons, exchange, voice, school,
reports) runs through frankie_box_cores.py: it books EXACTLY 16 CPUs in the box's ledger and starts the step under
taskset -c <those 16>, so every worker it pins lands inside them; its workers = 15 (root DATA_WORKERS, search WORKERS; the
teacher splits its own 16). Fewer than 16 free: the step does not start and is recorded 'waiting: N free of 16 needed'
(a later start retries it). The ingest books its own per day process in frankie_box_ingest_block.sh (the same waiting).
A plan day_cpus of 32 (Greg, 2026-10-07: "Give the day 32 CPUs and that many workers"; night: "day 1 gets ALL 32 CPUs for
every step") makes the day's one held booking 32 CPUs and every stage of the day runs inside it on the whole lane: workers
31 (root DATA_WORKERS, data DATA_WORKERS, search WORKERS), the teacher's one day on all 32, the classroom, lessons, exchange
and its Jev context read on the lane's pinned pools, Jev and the meeting (voice) with llama-server threads from their one
setting each (JEV_THREADS, MEETING_THREADS; default the lane size). The ingest of a lone day takes the plan's day size
(Run.ingest_size; days side by side share the box), never the old fixed WORKERS=7 / 8 CPUs. Within a day the stages
still run one after another on the booking. Most later stages read an earlier one's output or the brain an earlier one
publishes into. Two pairs are data-independent: the classroom and the data export (held apart by the settled order,
"build/search the causal evidence only after Frankie's classroom work exists"), and the exchange's shared-market read
(jev_context_read's EXCHANGE_CONTEXT_ONLY read) and the lessons. Every member of both pairs is a pinned pool
sized to the whole lane, so side by side they would either share the same 32 CPUs (no measured gain) or split them into
disjoint halves (each step below the day's 32); neither runs side by side until a canary measures a gain.

RESUME. A receipt per day and step (per batch for teacher and lessons) under /opt/frankie-box/work/experiment/<run>/.
A restart with the same plan skips every step whose receipt says done or reused and runs the rest; a different plan
for the same run is refused. Steps that failed, were refused or are not built are retried on the next start.
DISK. Before every step the free bytes of /opt/frankie-box are measured; a step whose largest measured size so far
(this run, same step; the largest, never an average) would take free space below the floor is not started: the run
stops and saves, exit 4, with the numbers. The first step of each kind is the measurement (free must be above the floor).
PROGRESS. /opt/frankie-box/work/experiment/<run>/progress.json (FRANKIE_WORK_PROBE_V1) for
frankie_box_progress.sh DIRECTORY=/opt/frankie-box/work/experiment/<run>.

ACTION=plan (read-only: what each day and step would do), start, status (read-only: every receipt).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCHEMA = 'FRANKIE_EXPERIMENT_RUN_V1'
STAGES = ('fetch', 'ingest', 'external', 'root', 'teacher', 'classroom', 'jev', 'data', 'search', 'lessons', 'exchange',
          'voice', 'school', 'reports')
SAVED_EXIT = 75     # EX_TEMPFAIL: a stage child stopped at a save point on a requested save (the ROOT's convention; every stage
                    # with a save route exits 75 the same way: stacks pass 2026-10-07). Run.child_saved classifies it 'saved'.
PROBE_DIRS_ENV = 'FRANKIE_PROBE_DIRS'   # the stage's known probe directories, exported to the child (comma-separated;
                                        # frankie_box_stage_progress reads every absolute work directory a process names)
FINISHED = ('done', 'reused', 'skipped', 'not_run')   # not_run: a listed outcome (the step's equation had no operand on
                                                       # this day: a search with no causal axis); the day goes on
HANDED_OFF = 'waiting_for_pod'           # the jev step's end on the box: material relayed, the Pod is its own dispatch
BOX_ROOT = Path('/opt/frankie-box')


def _cores():
    """The box's CPU booking ledger module beside this file (frankie_box_cores: DAY_RUN_SIZES, DAY_RUN_CPUS, lane_for);
    the one source of every CPU size here, never a literal (session 8)."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import frankie_box_cores
    return frankie_box_cores
WORK = BOX_ROOT / 'work'
RUNS = WORK / 'experiment'
ROOTS = WORK / 'experiment-roots'
DIGEST_FILE = 'derivation-digest-full.md'     # Frankie's full-depth digest under <ROOT>/work (the classroom reads it)
RESUME_REFUSED_EXIT = 65    # frankie_box_experiment_root.RESUME_REFUSED_EXIT: a resume refused on identity (session 9)
TEACHER_ROWS = WORK / 'experiment-teacher-rows'
DATA = WORK / 'experiment-data'
SEARCH = WORK / 'experiment-search'
REPORTS = WORK / 'experiment-reports'     # the day reports: CLASSROOM / FRANKIE REPORT #N (one number per trade day)
REPORTS_SCHEMA = 'FRANKIE_EXPERIMENT_DAY_REPORTS_RECEIPT_V1'
LESSONS_ROOT = WORK / 'experiment-teacher'  # the scientific teacher's lessons (frankie_box_scientific_teacher.ROOT)
SCHOOL_RECEIPT_SCHEMA = 'FRANKIE_SCHOOL_KNOWLEDGE_RECEIPT_V1'
ROWS_FILE = 'host-dipole-classroom-source.c15.json'
DAY_EXTERNAL = WORK / 'day-external'
DAY_FILE, DAY_FILE_RECEIPT = 'day-external.json', 'day-external-receipt.json'
BRAIN = BOX_ROOT / 'brain'
ROWS_ROUTE = ('put right only by moving the retained publication under %s aside with a receipt (the teacher rows are '
              'not run-scoped; no run name and no code mints a replacement)')   # a refused teacher publication's one route
SHARED_MARKET_POLICY = 'FRANKIE_SHARED_MARKET_TIMELINE_V1'   # the one shared-market policy a NEW plan may select (Codex's
                                                             # frankie_box_market_timeline; ROOT and teacher wrappers forward it)
JEV_BRAIN = BOX_ROOT / 'jev-brain'          # Jev's own brain on the box (plan jev_brain overrides; the S3 lineage is clm-sidecar/jev-brain)
# THE ONE PINNED MODEL RUNTIME ON THE BOX (Greg, 2026-10-07): Granite 4.2 3B Q4_K_M under llama.cpp b11440, installed once by
# frankie_box_granite_meeting_setup.sh under GRANITE_DIR at the paths the meeting's runtime gate expects; the meeting
# (voice_route=local) AND Jev bind to that same definition (no second install, no second pin set; Jev improves with it)
GRANITE_DIR = BOX_ROOT / 'granite'
# THE ONE SETTING for the meeting's (voice) llama-server threads (Greg, 2026-10-07 night: "day 1 gets ALL 32 CPUs for every
# step"; the meeting runs inside the day's held booking on the whole lane, like Jev). None = the day's lane size
# (Run.day_cpus(): 32 on a 32-CPU day, 16 on a 16-CPU lane); an integer = that many. The meeting clamps it to its owning
# affinity and pins the server to that many lane CPUs in physical-core order (frankie_box_granite_meeting.threads_resolution,
# _server_cpus). The thread count is bound into the meeting's binding and record: it CAN change the meeting's text at the
# rounding level (llama.cpp's CPU flash-attention splits the KV range across threads; the same caveat as Jev's,
# frankie_box_jev_cpu.lane_threads), so a meeting at another thread count is another meeting, never compared as the same.
MEETING_THREADS = None
GRANITE_PROVENANCE_SCHEMA = 'FRANKIE_GRANITE_RUNTIME_PROVENANCE_V1'   # written by the setup script after every pin check passed
SHARED_RUNTIME_SCHEMA = 'FRANKIE_SHARED_MODEL_RUNTIME_V1'
# THE 99 LAYERS COMBINED FOR FRANKIE (Greg, 2026-10-07: "the biggest thing ... is making sure the 99 layers are combined for
# Frankie first"). The 99 identities, their roles and their settled per-entry market carriers come from ONE registry,
# frankie_box_all99_coverage (REGISTRY / entries / MARKET_CARRIERS / NATIVE_ENTRIES / FIXED_WORDS; review 2026-10-07: four
# copies had drifted); this file keeps only the ROOT's own reading of them. Every ROOT records, per entry, whether the day
# PRODUCED it and whether it is ADMITTED into the shared market timeline picture through its own carrier, or why not
# (thinner picture; the day stays), and the shared field FRANKIE_ALL99_COVERAGE_V1 beside it (all99_admission).
CYCLE_PINS = 'research/kalshi/frankie_boss/knowledge/CYCLE_CALCULATION_PINS.json'
ALL99_SCHEMA = 'FRANKIE_ALL99_ADMISSION_V1'
S3_BUCKET = 'bento-568968024170-us-east-2-an'
CURVE_PREFIX = 'nymex/ng_fut_parent_v0'
MONDAY = '20211004'                      # the gold standard: never re-ingested
MONDAY_RECOVERY = '/opt/frankie-box/work/sealed-recovery-35796793428/recovery-receipt.json'   # its ingest was recovered; checkpoint beside it
CYCLE = '00'
BATCH = 5                                # the teacher's Dipole rows: 1 day in 5 (Greg, 2026-09-29)
CLASS_OF_WEEKDAY = {0: 'monday', 1: 'midweek', 2: 'midweek', 3: 'thursday', 4: 'friday'}
# Greg 2026-10-06: all 30 days continuously learn from completed stages; no year-based holdout.
# Keep the existing discovery execution route and its mathematics for every assigned year.
ROLE_OF_YEAR = {year: 'discovery' for year in range(2021, 2026)}
INGESTION_SCHEMA = 'BOSS_BLOCK_INGESTION_RECEIPT_V1'
OVERRIDES = ('ingest', 'calculations', 'launch', 'preparation', 'principal_inputs', 'host_config', 'run',
             'teacher_rows', 'jev_stamp', 'frankie_ledgers', 'opening_receipt', 'previous_classroom')


def file_pin(path):
    """The {path, bytes, sha256} witness of a file as it is now (the Jev request's pins; frankie_box_jev_cpu re-reads them)."""
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha256_file(path))


# plan key -> the classroom child's environment variable (frankie_box_classroom_code.NATIVE_CUTOFF_ENV)
NATIVE_CUTOFF_ENV = dict(native_cutoff_seconds='FRANKIE_NATIVE_CUTOFF_SECONDS',
                         native_cutoff_rss_gb='FRANKIE_NATIVE_CUTOFF_RSS_GB',
                         native_cutoff_check_every='FRANKIE_NATIVE_CUTOFF_CHECK_EVERY')
NATIVE_CUTOFF_PLAN_KEYS = tuple(NATIVE_CUTOFF_ENV)


RANGE_BYTES = 16 << 20       # aws-storage skill / S3 performance guidance: concurrent 8-16 MB byte-range GETs
RANGE_STREAMS = 8            # the S3 day file is ~35 MB: a few ranges at once; the journal pull uses its own (15)


def ranged_fetch(url, target, size, streams=RANGE_STREAMS, range_bytes=RANGE_BYTES):
    """One presigned GET object written to target as concurrent byte ranges (os.pwrite at their offsets). Raises on any
    short range or non-206 answer; the caller checks the whole file's bytes and sha256 against its receipt as before."""
    import urllib.request
    total = max(1, (size + range_bytes - 1) // range_bytes)
    fd = os.open(target, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.ftruncate(fd, size)

        def one(i):
            start, end = i * range_bytes, min(size, (i + 1) * range_bytes) - 1
            request = urllib.request.Request(url, headers={'Range': 'bytes=%d-%d' % (start, end)})
            with urllib.request.urlopen(request, timeout=300) as response:
                if response.status != 206:
                    raise ValueError('range GET answered %s, not 206' % response.status)
                data = response.read()
            if len(data) != end - start + 1:
                raise ValueError('range %d returned %d of %d bytes' % (i, len(data), end - start + 1))
            os.pwrite(fd, data, start)
        with ThreadPoolExecutor(max(1, min(streams, total))) as pool:
            list(pool.map(one, range(total)))
        os.fsync(fd)
    finally:
        os.close(fd)


def pin_or_listed(path):
    """file_pin(path), or {path, unavailable: why} when the file cannot be read now (never raises; None for no path).
    For small metadata files only (manifests, receipts, the day file); a journal is pinned from its receipt instead."""
    if not path:
        return None
    try:
        return file_pin(path)
    except OSError as error:
        return dict(path=str(path), unavailable='%s: %s' % (type(error).__name__, error))


INGEST_RECEIPT_FACTS = ('schema', 'trading_day', 'record_count', 'journal_count', 'journal_file', 'journal_bytes',
                        'journal_sha256', 'partial_members', 'tail_members', 'opening_book', 'adapter_records',
                        'f_last_groups')


def ingest_receipt_facts(receipt):
    """The sealed ingest receipt's own recorded facts (INGEST_RECEIPT_FACTS: counts, the journal's pin as recorded, the
    tail/partial members, the opening book), for the one-day inspection; the journal itself is never re-read."""
    try:
        body = json.loads(Path(receipt).read_bytes())
    except (OSError, ValueError) as error:
        return dict(unavailable='%s: %s' % (type(error).__name__, error))
    return {k: body.get(k) for k in INGEST_RECEIPT_FACTS if k in body}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(64 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def new_bytes(path):
    """Bytes a step's output adds to the disk: every regular file under it counted once, hard links (other names of
    bytes that already exist, e.g. the day data export) not counted."""
    path = Path(path)
    if not path.exists():
        return 0
    seen, total = set(), 0
    for p in [path] if path.is_file() else path.rglob('*'):
        try:
            st = p.lstat()
        except OSError:
            continue
        if p.is_file() and not p.is_symlink() and st.st_nlink == 1 and st.st_ino not in seen:
            seen.add(st.st_ino)
            total += st.st_size
    return total


# ---------------------------------------------------------------------------------------------------------------- plan

def pair_units(days):
    """Midweek days into units (Greg, 2026-09-29): "we may not have equal amount of tue and wed. We'll pair them up like
    that for as many pairs as we can get. They probably won't all have consecutive dates though." First every Tuesday with
    the Wednesday of its own week; then the Tuesdays and Wednesdays left over, each in date order, the k-th Tuesday with
    the k-th Wednesday (a pair across weeks, its days in date order: the second applies the first's findings); what is
    still left is a single. Units are returned in date order of their first day. Nothing is dropped."""
    parse = lambda d: dt.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
    tues = sorted(d for d in days if parse(d).weekday() == 1)
    weds = sorted(d for d in days if parse(d).weekday() == 2)
    units, used = [], set()
    for t in tues:
        w = (parse(t) + dt.timedelta(days=1)).strftime('%Y%m%d')
        if w in weds:
            units.append(dict(kind='same_week', days=[t, w]))
            used.update((t, w))
    left_t = [d for d in tues if d not in used]
    left_w = [d for d in weds if d not in used]
    for t, w in zip(left_t, left_w):
        units.append(dict(kind='cross_week', days=sorted([t, w])))
    for d in left_t[len(left_w):] + left_w[len(left_t):]:
        units.append(dict(kind='single', days=[d]))
    units.sort(key=lambda u: u['days'][0])
    return units


def load_plan(a, code_root):
    """The run's plan: the days with their class and role, overrides per day, and the fixed settings. Only rule breaks
    refuse the plan (a day listed twice, a malformed day, an unknown class or field). A day outside the run's class or
    the assigned Octobers, or an unfrozen confirmation day, is left out of this run with its reasons; a day with no
    manifest stays in, its gap recorded, and its steps wait on it (a sealed ingest found on the box is used first)."""
    doc = {}
    if a.plan:
        path = Path(a.plan) if Path(a.plan).is_absolute() else Path(code_root) / a.plan
        doc = json.loads(path.read_bytes())
    entries = [dict(d) if isinstance(d, dict) else dict(day=str(d)) for d in doc.get('days') or []]
    entries += [dict(day=d) for d in (a.days or '').split(',') if d.strip()]
    klass = a.day_class or doc.get('class')
    arm = sorted(set((a.classroom_arm or '').split(',') if a.classroom_arm else doc.get('classroom_arm') or []) - {''})
    listed = sorted({str(e['day']) for e in entries if str(e['day']).isdigit() and len(str(e['day'])) == 8})
    units = {role: pair_units([d for d in listed if d[4:6] == '10' and ROLE_OF_YEAR.get(int(d[:4])) == role
                               and CLASS_OF_WEEKDAY.get(dt.date(int(d[:4]), int(d[4:6]), int(d[6:8])).weekday()) == klass])
             for role in ('discovery', 'confirmation')}
    if not arm:
        # Greg, 2026-09-29: the classroom arm runs on days 1 and 2 of every five (they apply their findings), off on 3, 4
        # and 5, then on again (--classroom-arm-cycle ON/CYCLE, default 2/5; 5/5 = every day). An explicit list
        # (--classroom-arm) wins. Then (Greg): "We'll pair them up like that for as many pairs as we can get. They probably
        # won't all have consecutive dates though": the cycle is counted in days over the discovery UNITS (pairs, then
        # singles) in date order, and a unit is on when the position of its first day is on, so a pair is never split:
        # with 2/5 and pairs the arm runs on units 1, 4, 6, 9, ... (2 days in 5 over the run, every arm unit a whole pair).
        on, cycle = (int(x) for x in a.classroom_arm_cycle.split('/'))
        position = 0
        for unit in units['discovery']:
            if position % cycle < on:
                arm.extend(unit['days'])
            position += len(unit['days'])
        arm = sorted(arm)
    refused, days, left_out = [], [], []
    names = [e['day'] for e in entries]
    for d in sorted({n for n in names if names.count(n) > 1}):
        refused.append(dict(day=d, reason='the day is listed %d times (duplicate data declines the run)' % names.count(d)))
    if klass not in set(CLASS_OF_WEEKDAY.values()):
        refused.append(dict(day=None, reason='the run class must be one of %s' % sorted(set(CLASS_OF_WEEKDAY.values()))))
    for e in entries:
        day = str(e['day'])
        unknown = sorted(set(e) - {'day', 'manifest', *OVERRIDES})
        if unknown:
            refused.append(dict(day=day, reason='unknown plan fields %s' % unknown))
        outs = []
        try:
            date = dt.date(int(day[:4]), int(day[4:6]), int(day[6:8]))
            if len(day) != 8 or not day.isdigit():
                raise ValueError
        except ValueError:
            refused.append(dict(day=day, reason='not a YYYYMMDD day'))
            continue
        cls = CLASS_OF_WEEKDAY.get(date.weekday())
        if cls != klass:
            outs.append('a %s day in a %s run: classes never mix (left out of this run)' % (cls or 'weekend', klass))
        role = ROLE_OF_YEAR.get(date.year) if date.month == 10 else None
        if role is None:
            outs.append('only October days of 2021-2025 are assigned to this continuous-learning experiment (R15); '
                        'widening to other months is a plan change for Greg')
        if role == 'confirmation' and not a.frozen_survivors:
            outs.append('a confirmation day stays untouched until the survivor list is frozen (give FROZEN_SURVIVORS)')
        if day in arm and role != 'discovery':
            outs.append('a classroom-arm day is always a discovery day')
        if outs:
            left_out.append(dict(day=day, reasons=outs))
            continue
        manifest = e.get('manifest') or 'research/kalshi/frankie_boss/blocks/BLOCK_%s_SOURCE_MANIFEST.json' % day
        mpath = Path(code_root) / manifest
        manifest_ok, gap, opens_after = False, None, None
        if mpath.is_file():
            m = json.loads(mpath.read_bytes())
            manifest_ok = str(m.get('trading_day')) == day
            # a day that opens at the prior day's halt (a tail member, Greg 2026-09-29): its ingest opens with the book the
            # prior trading day closed with when that day's sealed ingest exists, and otherwise warms its own book from the
            # tail partition (no wait: "we will just be running tue and weds for a while")
            tails = m.get('tail_members') or []
            if manifest_ok and tails:
                opens_after = tails[0]['member_key'].split('-')[-1].split('.')[0]
            if not manifest_ok:
                gap = ('%s is for trading day %s, not %s (a multi-day block manifest is not a day)'
                       % (manifest, m.get('trading_day'), day))
        elif not e.get('ingest'):
            gap = 'no committed per-day manifest %s and no sealed ingest named in the plan' % manifest
        days.append(dict(day=day, cls=cls, role=role, classroom_arm=day in arm, manifest=manifest if manifest_ok else None,
                         manifest_gap=gap, opens_after=opens_after, **{k: e[k] for k in OVERRIDES if e.get(k)}))
    for d in arm:
        if d not in names:
            refused.append(dict(day=d, reason='a classroom-arm day that is not in the day list'))
    # Greg 2026-10-06: days learn in supplied workflow order, not trading-date order.
    # Keep the submitted order (plan entries, then --days) in the saved plan/digest.
    # Pair units still define the same grouping and classroom-arm membership above;
    # they do not reorder the caller's randomized day sequence.
    plan = dict(schema=SCHEMA, run=a.run, cls=klass, days=days, left_out=left_out, classroom_arm=arm, units=units,
                knowledge_order='completed_workflow_stages_all_30_days_no_trading_date_or_year_holdout',
                frozen_survivors=a.frozen_survivors or None, historical_claims=a.historical_claims or None,
                lags=a.lags, transforms=a.transforms or None, batch=BATCH,
                external_history_run=a.external_history_run or None, external_wait=a.external_wait != 'off',
                brain=a.brain, previous_classroom=a.previous_classroom or None, directive=directive_of(code_root))
    for key in ('jev_brain',):     # only when given: earlier plans keep their digest (a saved plan's older jev_runtime
                                   # stays in it, recorded as superseded by Run.jev, never used)
        if getattr(a, key, None):
            plan[key] = str(Path(getattr(a, key)))
    # the per-piece status reports (Greg, 2026-10-07 session 2: for the ONE-day run only; an N-day run neither produces
    # nor keeps them): an explicit persisted flag, decided here once and saved with the plan, never inferred at call time.
    # 'auto' = one_day when the plan holds exactly one day, else off; one_day / off = the operator's explicit override.
    # None (a saved plan from before the flag) keeps the plan without the key, read as off by Run.inspection_on
    # the classroom's former native-entry cutoff (frankie_box_classroom_code.native_cutoff_limits; retired 2026-10-09:
    # recorded as given, never applied; check_every stays the probe cadence): saved only when given, so an older plan
    # without the keys keeps its digest
    for key in NATIVE_CUTOFF_PLAN_KEYS:
        if getattr(a, key, None) is not None:
            plan[key] = getattr(a, key)
    # the day slot size: saved only when not the ledger's default (16), so every older plan keeps its fingerprint
    if getattr(a, 'day_cpus', None) not in (None, _cores().DAY_RUN_CPUS):
        plan['day_cpus'] = int(a.day_cpus)
    inspection = getattr(a, 'inspection', None)
    if inspection is not None:
        plan['inspection'] = ('one_day' if len(days) == 1 else 'off') if inspection == 'auto' else inspection
    if getattr(a, 'shared_market_policy', None):              # a NEW request's policy, saved with the plan at its first
        plan['shared_market_policy'] = a.shared_market_policy   # start (a run keeps one plan: a legacy plan stays legacy)
    if getattr(a, 'voice_route', None) and a.voice_route != 'local':   # the meeting's host route (Step 6 caller): saved at
        plan['voice_route'] = a.voice_route                            # the first start; absent = the local configured child
    if getattr(a, 'external_eia930_history_run', None):       # only when given: earlier plans keep their digest
        plan['external_eia930_history_run'] = a.external_eia930_history_run
    if getattr(a, 'external_family_history_runs', None):      # family=<run id>,... (the gap-only fetch chunks)
        runs = {}
        for item in [x for x in a.external_family_history_runs.split(',') if x]:
            fam, _, rid = item.partition('=')
            if fam not in HISTORY_FAMILIES or not rid.isalnum():
                raise SystemExit('--external-family-history-runs: family=<alphanumeric run id> (a GitHub run id or a '
                                 'named pull such as asprinted20261007), family one of %s' % (HISTORY_FAMILIES,))
            runs[fam] = rid
        plan['external_family_history_runs'] = runs
    return plan, refused


DIRECTIVE = 'research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json'
# the day-file builder's families (frankie_box_day_external.FAMILIES): 'consensus' is no longer read; its captures reach
# the day file through the as_printed family (fetch_day_history.py as-printed); a family run id is alphanumeric (isalnum)
HISTORY_FAMILIES = ('calendar', 'cot', 'storage', 'weather_obs', 'mos', 'eia930', 'as_printed')


def directive_of(code_root):
    """The experiment's directive (Greg, 2026-09-29) this run works under: named in the plan and every step receipt."""
    path = Path(code_root) / DIRECTIVE
    if not path.is_file():
        return dict(path=DIRECTIVE, absent='not in the staged checkout')
    data = path.read_bytes()
    doc = json.loads(data)
    return dict(path=DIRECTIVE, sha256=hashlib.sha256(data).hexdigest(), schema=doc.get('schema'),
                directive=doc.get('directive'))


def plan_digest(plan):
    return hashlib.sha256(canonical(plan).encode()).hexdigest()


# ----------------------------------------------------------------------------------------------------------- discovery

def sealed_ingests(day):
    """Every sealed compact ingest of the day on the box: ingestion-receipt.json of the day + completion.json."""
    out = []
    for receipt in sorted(WORK.glob('ingest-*/ingestion-receipt.json')):
        try:
            r = json.loads(receipt.read_bytes())
        except (OSError, ValueError):
            continue
        if r.get('schema') == INGESTION_SCHEMA and r.get('writer') == 'compact' and str(r.get('trading_day')) == day \
                and (receipt.parent / 'completion.json').is_file():      # partial members = the trading-day cut: kept
            out.append(receipt)
    return out


DUPLICATES = {}     # day -> {'ingest'|'root': the duplicate candidates and the choice} (recorded on the day's step records)


def _mtime(path):
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return -1


def _referenced(run, day, stage, field):
    """The path this run's own step receipt of the day names (its earlier choice), or None."""
    if not run:
        return None
    try:
        r = json.loads((RUNS / run / 'days' / day / ('%s.json' % stage)).read_bytes())
        return str(Path(r[field])) if r.get(field) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _choose(kind, day, candidates, referenced, label):
    """2026-10-09 (Greg: fastest runtime, science unchanged): never a stop on duplicates. The one the owner binding or
    this run's own step receipt references, else the newest (receipt mtime); every candidate and the choice recorded
    (DUPLICATES, carried on the day's step records)."""
    by_path = {str(c): c for c in candidates}
    if referenced in by_path:
        chosen, why = by_path[referenced], 'referenced by %s' % label
    else:
        chosen = max(candidates, key=lambda c: (_mtime(c), str(c)))
        why = 'the newest sealed/receipted one (receipt mtime); none is referenced by %s' % label
    DUPLICATES.setdefault(day, {})[kind] = dict(duplicates=len(candidates), candidates=[str(c) for c in candidates],
                                                chosen=str(chosen), why=why)
    return chosen


def ingest_of(entry, run=None):
    """(receipt path, None) or (None, reason). Two or more sealed ingests of the day: one is chosen (_choose: the one
    this run's ingest step receipt names, else the newest), recorded, never a refusal."""
    if entry.get('ingest'):
        receipt = Path(entry['ingest']) / 'ingestion-receipt.json'
        return (receipt, None) if receipt.is_file() else (None, 'the plan names %s but it holds no ingestion-receipt.json'
                                                                % entry['ingest'])
    found = sealed_ingests(entry['day'])
    if len(found) > 1:
        named = _referenced(run, entry['day'], 'ingest', 'receipt')
        if named is None:
            ingest_dir = _referenced(run, entry['day'], 'ingest', 'ingest')
            named = str(Path(ingest_dir) / 'ingestion-receipt.json') if ingest_dir else None
        return _choose('ingest', entry['day'], found, named, 'this run\'s ingest step receipt'), None
    return (found[0], None) if found else (None, None)


def root_of(entry, run, prefer=None):
    """(calculations directory, attempts listed) of the day's finished ROOT, or (None, attempts). Two or more finished
    ROOTs: one is chosen (_choose: the owner binding's attempt `prefer`, else the one this run's root step receipt
    names, else the newest), recorded, never a refusal; the others are listed with the attempts."""
    remote = RUNS / run / 'days' / entry['day'] / 'root.json'
    if remote.is_file():
        receipt = json.loads(remote.read_bytes())
        if receipt.get('remote_calculations') and receipt.get('status') in FINISHED:
            return Path(receipt['calculations']), []
    if entry.get('calculations'):
        return Path(entry['calculations']), []
    attempts = sorted(ROOTS.glob('%s-%s*' % (run, entry['day'])))
    done = [p for p in attempts if (p / 'calculations-receipt.json').is_file()]
    if len(done) > 1:
        named = str(ROOTS / prefer) if prefer else _referenced(run, entry['day'], 'root', 'calculations')
        receipts = [p / 'calculations-receipt.json' for p in done]
        chosen = _choose('root', entry['day'], receipts, str(Path(named) / 'calculations-receipt.json') if named else None,
                         'the owner binding (attempt %s)' % prefer if prefer else 'this run\'s root step receipt').parent
        return chosen, [str(p) for p in attempts if p != chosen]
    return (done[0] if done else None), [str(p) for p in attempts if p not in done]


def rows_of(entry):
    """The day's Dipole rows: the plan's, a launch run's, or the teacher-only step's; (path, source) or (None, None)."""
    for base, source in ((entry.get('teacher_rows'), 'plan'), (TEACHER_ROWS / entry['day'], 'teacher-only step')):
        if base and (Path(base) / ROWS_FILE).is_file():
            if Path(base).is_relative_to(TEACHER_ROWS):
                receipt = Path(base) / 'receipt.json'
                if not receipt.is_file():
                    continue  # Rows are published before the complete teacher transaction.
                saved = json.loads(receipt.read_bytes())
                if saved.get('schema') != 'FRANKIE_EXPERIMENT_TEACHER_ROWS_V1' or saved.get('day') != entry['day']:
                    raise ValueError('retained teacher publication does not match this day')
                if not (Path(base) / 'teacher-attachment.pkl').is_file() or \
                        (saved.get('external_section') or {}).get('status') not in ('built', 'reused', 'absent'):
                    continue
            return Path(base), source
    if entry.get('run'):
        found = sorted(Path(entry['run']).glob('execution/cycle-*/host-dipole-classroom-source*.json'))
        if found:
            return Path(entry['run']), 'launch run'
    return None, None


_ATTACHED_CHECKED = {}      # {(day file, receipt, ingest receipt) stat keys: sha256} checked in this process


def _stat_key(path):
    try:
        st = os.stat(path)
        return (str(path), st.st_ino, st.st_size, st.st_mtime_ns)
    except OSError:
        return (str(path), None)


def attached_day_file(ingest_dir):
    """(day file, sha256, None) beside a sealed ingest when it and its receipt agree; (None, None, why) otherwise, and
    why starts with DIFFERS when a file is there but differs from its receipt (never overwritten: refused). One pass:
    a check that passed in this process is reused while the three files' stat keys are unchanged (every Run object)."""
    path, receipt = Path(ingest_dir) / DAY_FILE, Path(ingest_dir) / DAY_FILE_RECEIPT
    if not path.is_file():
        return None, None, 'no %s beside the sealed ingest %s' % (DAY_FILE, ingest_dir)
    if not receipt.is_file():
        return None, None, '%s beside %s has no %s' % (DAY_FILE, ingest_dir, DAY_FILE_RECEIPT)
    key = (_stat_key(path), _stat_key(receipt), _stat_key(Path(ingest_dir) / 'ingestion-receipt.json'))
    if key in _ATTACHED_CHECKED:
        return path, _ATTACHED_CHECKED[key], None
    want = json.loads(receipt.read_bytes()).get('sha256')
    have = sha256_file(path)
    if have != want:
        return None, None, 'DIFFERS: %s has sha256 %s, its receipt names %s' % (path, have, want)
    body = json.loads(path.read_bytes())
    ingest_receipt = Path(ingest_dir) / 'ingestion-receipt.json'
    if ingest_receipt.is_file():
        expected_day = json.loads(ingest_receipt.read_bytes()).get('trading_day')
        if body.get('trading_day') != expected_day:
            return None, None, 'DIFFERS: external file trading day %s, ingest trading day %s' % (
                body.get('trading_day'), expected_day)
    from research.kalshi.frankie_boss.operations.frankie_day_external import check_day_file
    check_day_file(body)
    _ATTACHED_CHECKED[key] = have
    return path, have, None


def latest_completed_classroom(day):
    """The most recently completed other classroom, regardless of trading-date order or old role: (directory, day) or
    (None, None). Two complete classrooms of that same day decline (duplicate data)."""
    found = {}
    for completion in ROOTS.glob('*/work/classroom/completion.json'):
        d = completion.parent
        try:
            r = json.loads((d / 'receipt.json').read_bytes())
        except (OSError, ValueError):
            continue
        source_day = str(r.get('day', ''))
        if r.get('status') == 'complete' and source_day != day:
            found.setdefault(str(r['day']), []).append(d)
    if not found:
        return None, None
    last = max(found, key=lambda date: max((d / 'receipt.json').stat().st_mtime for d in found[date]))
    if len(found[last]) > 1:
        raise SystemExit('two complete classrooms of %s (%s): duplicate data; name previous_classroom in the plan'
                         % (last, [str(p) for p in found[last]]))
    return found[last][0], last


def jev_stamp(plan, e):
    return e.get('jev_stamp') or '%s-jev-%s' % (plan['run'], e['day'])


def presign_items(plan, code_root):
    """The presign string one orchestrator dispatch carries (frankie_box_run.yml presign=...): every partition of every
    planned day's manifest (fetch), the day history and curve prefixes (read-only getprefix), the day-file upload slots
    of every day. Listed items only; nothing is presigned here. (Jev's material stays on the box: his stage runs on the
    day's held lane, so no material slot to another host is listed; Greg, 2026-10-07.)"""
    items = []
    for e in plan['days']:
        if not e.get('manifest'):
            items.append('# %s: no committed manifest yet (its partitions are named once the manifest is committed)' % e['day'])
            continue
        m = json.loads((Path(code_root) / e['manifest']).read_bytes())
        base = m.get('archive_prefix') or ''
        # a member's own archive_key (the sessions / tail_members entries) is the S3 key: the archive_prefix alone is not
        # (20211011-13 and 20221003-05 sit under a range folder, <prefix>/<YYYYMMDD_YYYYMMDD>/<member>; built from the
        # prefix they 404'd, 2026-09-29)
        archive_keys = {x['member_key']: x['archive_key'] for x in (m.get('sessions') or []) + (m.get('tail_members') or [])
                        if isinstance(x, dict) and x.get('member_key') and x.get('archive_key')}
        for member in m.get('sources') or []:
            key = member['member_key']
            if key in archive_keys:
                items.append('%s/%s' % (m.get('bucket') or S3_BUCKET, archive_keys[key]))
                continue
            part = key.split('-')[-1].split('.')[0]
            prefix = base
            if len(base) >= 7 and base[-7:-3].isdigit() and base[-3] == '-':      # .../YYYY-MM: the member's own month
                prefix = base[:-7] + '%s-%s' % (part[:4], part[4:6])
            items.append('%s/%s/%s' % (m.get('bucket') or S3_BUCKET, prefix, key))
    if plan.get('external_history_run'):
        items.append('getprefix:%s/frankie/day_history/%s/' % (S3_BUCKET, plan['external_history_run']))
        for rid in [plan.get('external_eia930_history_run')] + sorted((plan.get('external_family_history_runs') or {}).values()):
            if rid:
                items.append('getprefix:%s/frankie/day_history/%s/' % (S3_BUCKET, rid))
        items.append('getprefix:%s/%s/' % (S3_BUCKET, CURVE_PREFIX))
    else:
        items.append('# no EXTERNAL_HISTORY_RUN: the day files cannot be built in this dispatch (the external step waits)')
    for e in plan['days']:
        # the day key on S3 (frankie/day_external/<day>/): a read-only listing of what S3 already holds (a verified day
        # file is fetched and preferred by Run.external), and the two upload slots. The workflow presigns a day's PUT
        # slots only when S3 holds NEITHER day object (frankie_box_run.yml: a verified S3 day file is never overwritten,
        # never a pair half replaced); the as_printed family run, when named, is in the getprefix list above
        items.append('getprefix:%s/frankie/day_external/%s/' % (S3_BUCKET, e['day']))
        for name in (DAY_FILE, DAY_FILE_RECEIPT):
            items.append('put:%s/frankie/day_external/%s/%s' % (S3_BUCKET, e['day'], name))
    return list(dict.fromkeys(items))


# --------------------------------------------------------------------------------------------------------------- run

def classify_child_calls(results):
    """(saved, bad) over a list of child call records carrying exit_code (the lessons batch; stacks pass 2026-10-07,
    school R6): saved = the calls that exited SAVED_EXIT (a child stopped at a save point on a requested save: never a
    failure), bad = every other nonzero exit. Pure; the caller records the batch 'saved' when any call saved."""
    saved = [r for r in results if r.get('exit_code') == SAVED_EXIT]
    bad = [r for r in results if r.get('exit_code') not in (0, SAVED_EXIT)]
    return saved, bad


def probe_directories(stage, env, code_root, work_root=None, box_root=None):
    """The directories a stage child's FRANKIE_WORK_PROBE_V1 progress.json may be in, known BEFORE the child starts
    (stacks pass 2026-10-07: teacher 4, ingest X4, reports X6), in a fixed order, deduplicated, as strings. Pure: nothing
    is created or read except the ingest's committed manifest (its block name). Every absolute path a stage env value
    names under the work root (a directory, or a file's own directory; comma-separated lists split), then per stage:
      teacher   experiment-teacher-rows/<day> for every day of the batch (env DAYS)
      ingest    the block data directory <box>/data/block_<block> (outside the work root: the generic reader never finds
                it on its own) and RESUME_DIR when the ingest continues one
      reports   REPORTS_DIR/receipts/<run> beside REPORTS_DIR (the step's own receipt directory)
    The stage heartbeat checks these first (named), then what the process tree itself names. A directory that does not
    exist yet is named anyway (the reader skips what is not there). Never an input to the child."""
    work_root = str(work_root or WORK).rstrip('/') + '/'
    box = Path(box_root or BOX_ROOT)
    found = []
    for value in (env or {}).values():
        for part in str(value).split(','):
            part = part.strip()
            if not part.startswith(work_root):
                continue
            path = Path(part)
            found.append(str(path.parent) if (path.suffix and not path.is_dir()) or path.is_file() else str(path))
    if stage == 'teacher':
        found += [str(Path(work_root) / 'experiment-teacher-rows' / d) for d in str(env.get('DAYS') or '').split(',') if d]
    if stage in ('ingest', 'fetch') and env.get('MANIFEST'):
        try:
            block = json.loads((Path(code_root) / str(env['MANIFEST'])).read_bytes()).get('block')
        except (OSError, ValueError, TypeError):
            block = None
        if isinstance(block, str) and block and re.fullmatch(r'[0-9_]+', block):
            found.append(str(box / 'data' / ('block_' + block)))
        if env.get('RESUME_DIR'):
            found.append(str(env['RESUME_DIR']))
    if stage == 'reports' and env.get('REPORTS_DIR') and env.get('RUN'):
        found.append(str(Path(str(env['REPORTS_DIR'])) / 'receipts' / str(env['RUN'])))
    return [d for d in dict.fromkeys(found) if d and d.rstrip('/') != work_root.rstrip('/')]


def done_status(r):
    """A step is finished when done, reused, skipped or not_run (a listed outcome: the step's equation had no operand on
    this day, e.g. a search with no causal axis; nothing to retry, the day goes on); a retired Pod handoff is still pending."""
    return bool(r and r['status'] in FINISHED)


KEEP_RUNNING_SCHEMA = 'FRANKIE_KEEP_RUNNING_V1'
PROCESS_STARTED = time.time()           # this process's start (box_in_use: a kick before it is the one that started us)


def this_instance():
    """(instance id, region) of this box from IMDSv2 (a token PUT, then the identity document); (None, why) off a box."""
    import urllib.request
    try:
        req = urllib.request.Request('http://169.254.169.254/latest/api/token', method='PUT',
                                     headers={'X-aws-ec2-metadata-token-ttl-seconds': '60'})
        token = urllib.request.urlopen(req, timeout=2).read().decode()
        req = urllib.request.Request('http://169.254.169.254/latest/dynamic/instance-identity/document',
                                     headers={'X-aws-ec2-metadata-token': token})
        doc = json.loads(urllib.request.urlopen(req, timeout=2).read())
        return doc.get('instanceId'), doc.get('region')
    except Exception as error:  # noqa: BLE001 - not on a box, or IMDS unreachable: named
        return None, '%s: %s' % (type(error).__name__, str(error)[:200])


def box_in_use(run_name=None):
    """What keeps THIS box in use besides the caller: orchestrator starts alive (any run), a queue line worker holding its
    lock, a CPU controller holding its lock; [] when nothing. Read-only."""
    busy = []
    try:
        import subprocess as sp
        pids = sp.run(['pgrep', '-f', 'frankie_box_experiment.py --action start --run '], capture_output=True, text=True).stdout.split()
        pids = [x for x in pids if x != str(os.getpid())]
        if pids:
            busy.append('orchestrator start(s) alive: pids %s' % ' '.join(pids))
    except Exception as error:  # noqa: BLE001
        busy.append('pgrep unavailable (%s): assumed in use' % type(error).__name__)
    try:
        import frankie_box_frankie_queue as Q
        for line in Q.LINES:
            status, held = Q.worker_state(line)
            other = held and (status or {}).get('pid') != os.getpid()
            if other:
                busy.append('%s line worker holds its lock (pid %s)' % (line, (status or {}).get('pid')))
            # B3a (2026-10-07; 2026-10-09 the kick returns at once, never waiting on the lock): a kick this recent keeps
            # the box in use while its worker is still starting (Python start-up, imports)
            kick = Q.QUEUE / ('%s-kick.json' % line)
            if kick.is_file():
                try:
                    age = time.time() - float(json.loads(kick.read_bytes()).get('at') or 0)
                except (OSError, ValueError):
                    age, at = 0.0, time.time()           # unreadable: a fresh kick (in use), never idle on a guess
                else:
                    at = time.time() - age
                # the kick that started THIS process (a line worker ending) is not a new kick: ignored here
                mine = (status or {}).get('pid') == os.getpid() and at <= PROCESS_STARTED
                if age < Q.KICK_GRACE_SECONDS and not mine:
                    busy.append('%s line kicked %d s ago (its worker may still be starting)' % (line, int(age)))
            # unfinished entries of ANY run: running / unknown always keep the box (an uncertain day is never read as
            # idle); queued ones only while a worker of the line is alive or was kicked (nothing else would take them)
            entries = Q.load(line).get('entries') or []
            live = [x for x in entries if x.get('state') in ('running', 'unknown')]
            if live:
                busy.append('%s line: %d running/unknown entr%s (%s)' % (line, len(live), 'y' if len(live) == 1 else 'ies',
                                                                         ', '.join('%s %s' % (x.get('run'), x.get('day')) for x in live[:6])))
            queued = [x for x in entries if x.get('state') == 'queued']
            if queued and (other or any(b.startswith('%s line kicked' % line) for b in busy)):
                busy.append('%s line: %d queued entr%s with a live or just-kicked worker' % (line, len(queued), 'y' if len(queued) == 1 else 'ies'))
    except (Exception, SystemExit) as error:  # noqa: BLE001 - Q.load refuses with SystemExit: also in use, named
        busy.append('queue state unreadable (%s): assumed in use' % type(error).__name__)
    parent = WORK / 'cpu-controller'
    for lock in sorted(parent.glob('*/controller.lock')) if parent.is_dir() else ():
        try:
            import fcntl
            with open(lock, 'a') as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(handle, fcntl.LOCK_UN)
                except OSError:
                    busy.append('CPU controller of %s holds its lock' % lock.parent.name)
        except OSError:
            busy.append('CPU controller lock %s unreadable: assumed in use' % lock)
    # session 6 (frankie_box_stage_handoff): a stage's clean unit on the retained lane keeps the box in use while it runs,
    # so a line worker ending saved at a boundary never clears the tag mid-clean: the unit's process (the module's clean
    # action, under systemd-run as frankie-clean-* or as a detached session) and a day marker whose clean note is in progress
    try:
        import subprocess as sp
        out = sp.run(['pgrep', '-af', 'frankie_box_stage_handoff.py --action clean'], capture_output=True, text=True).stdout
        pids = [line.split(' ', 1)[0] for line in out.splitlines() if line.strip() and line.split(' ', 1)[0] != str(os.getpid())]
        if pids:
            busy.append('stage clean unit(s) running: pids %s' % ' '.join(pids))
        if shutil.which('systemctl'):
            out = sp.run(['systemctl', 'list-units', 'frankie-clean-*', '--all', '--plain', '--no-legend'],
                         capture_output=True, text=True).stdout
            units = [line.split()[0] for line in out.splitlines()
                     if line.split() and line.split()[0].startswith('frankie-clean-') and ('running' in line or 'activating' in line)]
            if units:
                busy.append('stage clean unit(s) live: %s' % ', '.join(units))
    except Exception as error:  # noqa: BLE001
        busy.append('clean unit check unavailable (%s): assumed in use' % type(error).__name__)
    try:
        import frankie_box_frankie_queue as Q
        notes = sorted(Q.SAVE_DIR.glob('*.save-request.json.clean.json')) if Q.SAVE_DIR.is_dir() else []
        for note in notes:
            try:
                body = json.loads(note.read_bytes())
                status, note_pid = body.get('status'), body.get('pid')
            except (OSError, ValueError):
                status, note_pid = 'unreadable', None
            # session 6 review finding 8 (Patch H): a 'running' note is live only while its recorded pid exists
            if status == 'unreadable' or (status == 'running' and note_pid and Path('/proc/%s' % note_pid).exists()):
                busy.append('a stage clean is in progress on %s (%s, pid %s)' % (note.name, status, note_pid))
    except Exception:  # noqa: BLE001 - the marker notes are a hint; the process/unit checks above are the record
        pass
    return busy


def keep_running(run_name, value, reason, by, log=print):
    """This box's KeepRunning tag (Greg, 2026-10-07: "keep running only when in use"): 'true' at a run's start, 'false' at
    the end of the run's last worker on this box when nothing else is in use (box_in_use lists what is); never silent:
    every call appends its record (the tag value asked, what was done, the reason, or the failure) to
    <run>/keep-running.json (FRANKIE_KEEP_RUNNING_V1) and prints it. The idle guard (deploy/aws/idle_instance_guard.py)
    stops a box whose tag is not 'true' and that holds no fresh lane lease. ec2:CreateTags on this instance is the one
    permission (the instance profile; a missing permission is recorded, never raised)."""
    instance, region = this_instance()
    doc = dict(schema=KEEP_RUNNING_SCHEMA, run=run_name, asked='true' if value else 'false', reason=reason, by=by, at=time.time(),
               instance=instance, region=region)
    if instance is None:
        doc.update(tagged=False, error='no instance identity: %s' % region)
    else:
        busy = [] if value else box_in_use(run_name)
        if busy:
            doc.update(tagged=False, kept='true', busy=busy, note='not cleared: the box is still in use by the above')
        else:
            try:
                import boto3
                boto3.client('ec2', region_name=region).create_tags(
                    Resources=[instance], Tags=[dict(Key='KeepRunning', Value=doc['asked']),
                                                dict(Key='KeepRunningReason', Value=('%s: %s' % (by, reason))[:255])])
                doc['tagged'] = True
            except Exception as error:  # noqa: BLE001 - a cost guard, never the run's outcome; named
                doc.update(tagged=False, error='%s: %s' % (type(error).__name__, str(error)[:300]))
    try:
        path = RUNS / run_name / 'keep-running.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        events = json.loads(path.read_bytes()) if path.is_file() else []
        events.append(doc)
        tmp = path.with_suffix('.pending')
        tmp.write_text(json.dumps(events, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(tmp, path)
    except (OSError, ValueError) as error:
        doc['record_error'] = '%s: %s' % (type(error).__name__, error)
    log('keep-running %s: %s' % (run_name, json.dumps(doc, sort_keys=True)))
    return doc


def all99_crosswalk(code_root):
    """The ONE registry (frankie_box_all99_coverage.registry) and its pin: (registry doc, pin). The pin records the
    crosswalk file's witness, the registry's integrity findings and whether CYCLE_CALCULATION_PINS.json binds the same
    crosswalk sha256 as the registry module; any difference is a SEPARATE VISIBLE integrity finding (never relabelled
    as missing coverage); the embedded identities are still the ones listed, so no entry is dropped."""
    import frankie_box_all99_coverage as A99
    reg = A99.registry(code_root)
    pin = dict(path=str(Path(code_root) / A99.CROSSWALK_PATH), crosswalk=reg.get('crosswalk'),
               expected_sha256=A99.CROSSWALK_SHA256, registry_sha256=A99.REGISTRY_SHA256,
               registry_integrity=list(reg.get('integrity') or []))
    try:
        pins = json.loads((Path(code_root) / CYCLE_PINS).read_bytes())
        pinned = (pins.get('crosswalk') or {}).get('sha256')
        pin['cycle_pins_sha256'] = pinned
        if pinned != A99.CROSSWALK_SHA256:
            pin['registry_integrity'].append(dict(kind='cycle_pins_crosswalk_differs', cycle_pins=pinned,
                                                  registry=A99.CROSSWALK_SHA256))
    except (OSError, ValueError) as error:
        pin['registry_integrity'].append(dict(kind='cycle_pins_unreadable', error='%s: %s' % (type(error).__name__, error)))
    pin['actual_sha256'] = (reg.get('crosswalk') or {}).get('sha256')
    pin['integrity'] = ('verified' if reg.get('crosswalk') and not pin['registry_integrity'] else
                        'not_in_checkout' if not reg.get('crosswalk') and all(f.get('kind') == 'crosswalk_not_in_checkout'
                                                                               for f in pin['registry_integrity'])
                        else 'differs')
    return reg, pin


def all99_admission(code_root, day, calc_dir, calc, plan_policy, policy_mismatch, ingest, brain, derive_doc=None):
    """Per day: every one of the 99 registry entries with its disposition for THIS ROOT (ALL99_SCHEMA), its own words:
      admitted   produced AND carried into the shared market timeline picture by the entry's OWN settled carrier
                 (frankie_box_all99_coverage.MARKET_CARRIERS: input / opening / clock / availability through the sealed
                 journal; root.frames / root.prices / root.structures from the ROOT's spool pins; native.member /
                 native.lifecycle from the completed native ledgers): row-level presence inside a carrier is the shared
                 reader's count (frankie_box_market_timeline), never claimed here
      thin       not admitted through its own carrier but its thinner settled carrier is present (the picture carries a
                 thinner form)
      absent     not produced (a native pass that did not complete or a legacy plan's native-off ROOT, no producer, a
                 producer failure) or produced but not in the picture: the picture is THINNER, the day stays
      completed_only  a post-stream aggregate (no contributing-cursor provenance), never a live value
      control / not_read_by_this_piece / retired / not_applicable / withheld_by_role / disabled / output_not_written_here /
                 produced: settled by role (the shared vocabulary; FIXED_WORDS for the sealed, shadow, Memory A, A-clean
                 and arm-profile entries)
      integrity  the carrier's evidence could not be verified (selected_files raised): a separate visible failure
    The same rows are the shared field FRANKIE_ALL99_COVERAGE_V1 (frankie_box_all99_coverage.field, piece 'root') on the
    receipt as all99['coverage'], validated (its findings beside it). Reads derive.json, the receipt's spool pins and
    selected_files only; it instantiates no timeline reader (no spool is read)."""
    import frankie_box_all99_coverage as A99
    reg, pin = all99_crosswalk(code_root)
    out = dict(schema=ALL99_SCHEMA, day=day, crosswalk=pin, plan_policy=plan_policy, entries=[], counts={},
               rule='no entry rejects the timeline or the day: an absent layer thins the picture with its reason; '
                    'disabled producers are listed, never activated; integrity failures stay separate and visible')
    calc = calc or {}
    derive, derive_why, derive_sha, derive_problem = {}, None, None, None
    try:
        dpath = (calc.get('derivation') or {}).get('path')
        pinned = (calc.get('derivation') or {}).get('sha256')
        if dpath and derive_doc is not None and derive_doc[0] is not None and pinned:
            # 2026-10-09 (one pass): the caller's one parse of derive.json; its sha256 is the receipt's derivation pin
            derive, derive_sha = derive_doc[0], pinned
        elif dpath:
            raw = Path(dpath).read_bytes()             # derive.json: a sealed record, read once (bytes and sha256 here)
            derive_sha = hashlib.sha256(raw).hexdigest()
            derive = json.loads(raw)
            pinned = (calc.get('derivation') or {}).get('sha256')
            if pinned and pinned != derive_sha:
                derive_problem = 'derive.json differs from the ROOT receipt\'s derivation pin'
        else:
            derive_why = 'the ROOT receipt names no derivation'
    except (OSError, ValueError) as error:
        derive_why = 'derive.json unreadable: %s: %s' % (type(error).__name__, error)
    layers = derive.get('layers') or {}
    bedrock = derive.get('bedrock') if isinstance(derive.get('bedrock'), dict) else {}
    failures = derive.get('failure_count')
    # the per-layer native records Session.derive writes right after derive.json (work/native-layer-records.json,
    # FRANKIE_ROOT_NATIVE_LAYER_RECORDS_V1; correction_consumer 2026-10-07): one record per native registry layer, bound to
    # derive.json's bytes; used only when that binding holds (else listed, never trusted)
    native_records, native_records_why, nl_doc = {}, None, None
    nl_path = Path(calc_dir) / 'work' / 'native-layer-records.json' if calc_dir else None
    if nl_path is not None and nl_path.is_file():
        try:
            nl = json.loads(nl_path.read_bytes())
            bound = derive_sha is not None and (nl.get('derive') or {}).get('sha256') == derive_sha
            if nl.get('status') == 'built' and bound:
                nl_doc = nl
                native_records = {r['entry']: r for r in nl.get('records') or [] if isinstance(r, dict) and r.get('entry')}
            else:
                native_records_why = 'native-layer-records.json is %s%s' % (nl.get('status'), '' if bound else ', not bound to this derive.json')
        except (OSError, ValueError, KeyError) as error:
            native_records_why = 'native-layer-records.json unreadable: %s: %s' % (type(error).__name__, error)
    else:
        native_records_why = 'no work/native-layer-records.json in this ROOT (written by Session.derive after derive.json)'
    in_picture = bool(plan_policy) and not policy_mismatch
    picture_why = (None if in_picture else 'an older saved legacy plan (no shared market policy, kept as saved): produced '
                   'layers are not in the shared picture' if not plan_policy else
                   'the ROOT is refused under the plan\'s policy: %s' % policy_mismatch)
    journal = bool(ingest and ingest.get('status') in FINISHED)
    carriers = {}
    for name in ('input', 'opening', 'clock', 'availability'):
        carriers[name] = (dict(status='present', via='the sealed journal of the day (the timeline\'s input)') if journal and in_picture
                          else dict(status='absent', reason='no sealed ingest of the day on this box' if not journal else picture_why))
    for role in ('frames', 'prices', 'structures'):
        spool = (calc.get('shared_market_sources') or {}).get(role)
        if not plan_policy:
            carriers['root.' + role] = dict(status='absent', reason='an older saved legacy plan: no shared market policy, no spool pin')
        elif spool is None:
            carriers['root.' + role] = dict(status='absent', reason='the completed ROOT recorded no %s spool pin' % role)
        elif isinstance(spool, dict) and spool.get('status') == 'absent':
            carriers['root.' + role] = dict(status='absent', reason=spool.get('reason') or 'the ROOT published no %s spool' % role)
        else:
            carriers['root.' + role] = dict(status='present', pin={k: spool.get(k) for k in ('path', 'bytes', 'sha256')} if isinstance(spool, dict) else spool)
    native_done = bool(bedrock) and not bedrock.get('skipped')
    # THE NATIVE CARRIERS FROM THE SEALED RECORDS ONLY (session 9, Greg 2026-10-08: "Stop it now and eliminate it"): no
    # native ledger is read or hashed here (frankie_box_all99_coverage.sealed_native_carriers: derive.json's bedrock block,
    # the bound bedrock receipt, the bound native-layer records, the projection plan, one stat per ledger). A carrier no
    # record covers is 'not_measured' and the day proceeds. The old whole re-hash (selected_files: a2's 193.7 GB member
    # ledger, ~25 min) runs only with FRANKIE_ALL99_SCAN=on, default off: the second pass Greg removed.
    scan = os.environ.get(getattr(A99, 'SCAN_SETTING', 'FRANKIE_ALL99_SCAN'), 'off') == 'on'
    record_reads = []
    if scan:
        try:
            from frankie_box_experiment_native import selected_files
            selected = {item['native_role']: item for item in selected_files(calc_dir, str(day))} if calc_dir else {}
            for role, name in (('exact_member_rows.jsonl', 'native.member'), ('exact_lifecycle_rows.jsonl', 'native.lifecycle')):
                item = selected.get(role)
                carriers[name] = (dict(status='present', basis='scan', pin=dict(path=item['source'], **item['expected'])) if item else
                                  dict(status='absent', basis='scan', reason=('the native pass did not run in this ROOT (%s)' % (
                                      bedrock.get('reason') if bedrock.get('skipped') else 'no bedrock record in derive.json'))
                                      if not selected else 'native ledger not selected'))
        except Exception as error:  # noqa: BLE001 - altered or incomplete native evidence is an integrity failure, listed as such
            for name in ('native.member', 'native.lifecycle'):
                carriers[name] = dict(status='integrity', basis='scan', reason='%s: %s' % (type(error).__name__, str(error)[:300]))
    else:
        try:
            sealed, record_reads = A99.sealed_native_carriers(calc_dir, derive, derive_problem=derive_problem,
                                                              records_doc=nl_doc, records_why=native_records_why)
            carriers.update(sealed)
        except Exception as error:  # noqa: BLE001 - informational: the carriers read not measured, the day proceeds
            for name in ('native.member', 'native.lifecycle'):
                carriers[name] = dict(status='not_measured', basis='not_measured', reason='%s (the record reader failed: %s: %s)' % (
                    getattr(A99, 'NOT_MEASURED', 'not measured'), type(error).__name__, str(error)[:300]))
    carriers['completed'] = dict(status='completed_only', note='post_stream_only: the aggregate has no exact contributor cursor '
                                                              'provenance (the timeline lists it so; never a live value)')
    brain_present = bool(brain) and Path(brain).is_dir()
    native_entries = set(getattr(A99, 'NATIVE_ENTRIES', ()))
    rows = []
    for entry in reg['layers']:
        layer, group, role = entry['entry'], entry['group'], entry['role']
        first, thinner = A99.MARKET_CARRIERS.get(layer, (None, None))
        row = dict(entry=layer, group=group, role=role, policy=entry.get('policy'),
                   historical_status=entry.get('historical_delivery_status'), carrier=first, thinner_carrier=thinner)
        record = layers.get(layer) if isinstance(layers, dict) else None
        native_record = native_records.get(layer)
        basis = 'derive_layer_record' if record is not None else None
        if record is None and native_record is not None:
            record = native_record                  # the derivation's own per-layer native status, by crosswalk id
            basis = 'native_layer_record'
        if native_record is not None:
            row.update(native_record={k: native_record.get(k) for k in ('status', 'reason', 'producer_named_by_crosswalk',
                                                                         'native_limit', 'projection') if k in native_record})
        if role == 'raw':
            row.update(produced=journal, source=dict(ingest=(ingest or {}).get('ingest'), receipt_sha256=(ingest or {}).get('receipt_sha256')))
            status = carriers.get(first, {}).get('status')
            row.update(disposition='admitted' if status == 'present' else 'absent',
                       reason=('carried by %s (%s)' % (first, A99.CARRIER_ELEMENTS.get(first, first))) if status == 'present'
                       else carriers.get(first, {}).get('reason'))
        elif role in ('calculation', 'clock'):
            if layer in A99.NOT_MARKET_CARRIED:
                row.update(produced=None if record is None else record.get('status') == 'derived',
                           disposition='not_read_by_this_piece', reason=A99.NOT_MARKET_CARRIED[layer])
            elif first == 'completed':
                row.update(produced=None if record is None else record.get('status') == 'derived', disposition='completed_only',
                           canonical='completed_only', reason=carriers['completed']['note'])
            else:
                if record is not None and record.get('status') == 'derived':
                    produced, how = True, dict(producer=record.get('producer'), sha256=record.get('sha256'))
                elif record is not None:
                    produced, how = False, '%s: %s' % (record.get('status'), record.get('reason') or 'no reason recorded')
                elif layer in native_entries and native_done and carriers.get(first, {}).get('status') == 'present':
                    # THE GROUP PROXY FALLBACK (second review F4, named): neither derive.json nor a bound
                    # work/native-layer-records.json carries this native entry's own record, so the completed native pass
                    # and its carrier ledger stand in for it. Named on the row (basis) with why the per-layer record was
                    # not used; never presented as a per-layer check
                    basis = 'group_proxy'
                    produced, how = True, ('GROUP PROXY (no per-layer record used: %s): the completed native pass (its %s '
                                           'ledger present); derive.json has no per-layer record' % (
                                               native_records_why or 'the bound native-layer records list no record for it', first))
                else:
                    produced, how = False, derive_why or ('the native pass did not complete in this ROOT' if layer in native_entries
                                                          else 'the ROOT derivation lists no record for this layer')
                row.update(produced=produced, producer_record=how, basis=basis or 'no_record')
                state = carriers.get(first, {}).get('status')
                thin_state = carriers.get(thinner, {}).get('status') if thinner else None
                if first in ('native.member', 'native.lifecycle'):
                    # per native-carried entry: which sealed record answered (frankie_box_all99_coverage.BASIS_TEXT)
                    kind = ('scan' if scan else 'not_measured' if state == 'not_measured' or (basis is None and native_done)
                            else 'receipt' if basis == 'group_proxy' else 'record')
                    row.update(coverage_basis=kind, coverage_basis_text=getattr(A99, 'BASIS_TEXT', {}).get(kind, kind))
                if state == 'integrity':
                    row.update(disposition='integrity', integrity=True,
                               reason='INTEGRITY (separate, visible; not missing coverage): ' + str(carriers[first].get('reason')))
                elif state == 'not_measured' or (row.get('coverage_basis') == 'not_measured' and not scan):
                    row.update(disposition='not_measured', canonical='unknown',
                               reason=str(carriers.get(first, {}).get('reason') if state == 'not_measured' else
                                          getattr(A99, 'NOT_MEASURED', 'not measured') + ' (no per-layer record and no group '
                                          'record for this entry: %s)' % how)
                               + ('; the thinner carrier %s is %s' % (thinner, thin_state) if thinner else ''))
                elif produced and in_picture and state == 'present':
                    row.update(disposition='admitted', reason='produced and carried by its own carrier %s' % first)
                elif in_picture and thin_state == 'present':
                    row.update(disposition='thin', reason='its own carrier %s is %s (%s); the thinner carrier %s is present' % (
                        first, state or 'absent', carriers.get(first, {}).get('reason') or how, thinner))
                else:
                    row.update(disposition='absent', reason=picture_why or ('produced, but its carrier %s is absent: %s' % (
                        first, carriers.get(first, {}).get('reason')) if produced else 'not produced: %s' % how))
        elif layer in A99.FIXED_WORDS:
            word = A99.FIXED_WORDS[layer]
            row.update(produced=None, disposition=word, reason={
                'withheld_by_role': 'a sealed answer/target: withheld by role (R09/R10), never a live discovery input',
                'disabled': 'a provisional shadow disabled by the existing policy: listed, never silently activated',
                'retired': 'Memory A is retired (Greg, 2026-09-27); H06-H08 stay historical/not_bound',
                'not_applicable': 'the A-clean overlay is NOT_APPLICABLE in the crosswalk (not Memory A); the plan selects no A-clean arm',
                'control': 'a DELIVERED binding control: the plan\'s arm/profile selection applied by the orchestrator, not market evidence',
            }.get(word, word))
        elif role in ('control', 'knowledge'):
            row.update(produced=None, disposition='not_read_by_this_piece', consumer='the learner and teacher readers (brain)',
                       brain=dict(path=str(brain), present=brain_present),
                       reason='not a ROOT input by role: a %s input carried by the brain to the learner/teacher readers; their '
                              'consumption is each reader\'s own receipt' % role)
        elif role == 'output':
            if layer == 'output_source_state_manifest_code_model_run_hashes' and calc.get('source_binding'):
                row.update(produced=True, disposition='produced', pin=dict(source_binding=calc.get('source_binding'),
                                                                           calculation_pins=calc.get('calculation_pins')),
                           reason='this ROOT wrote its source binding and calculation pins')
            else:
                row.update(produced=None, disposition='output_not_written_here',
                           reason='an append-only output filed by its own stage: %s' % (getattr(A99, 'OUTPUT_ROUTES', {}).get(layer) or 'another stage'))
        else:
            row.update(produced=None, disposition='not_read_by_this_piece', reason='role %s: not a ROOT input' % role)
        # THE CANONICAL WORD (the one 99 registry, frankie_box_all99_coverage, 9464189e): the shared vocabulary word and its
        # class on every row, from the registry module only (FIXED_WORDS first, then a row's explicit canonical, then
        # LEGACY_WORDS); no word of this list's own decides it. The ROOT word stays in `disposition` (the day reports read
        # it: 'admitted' is the producer-side picture admission, never a computation) and is the field's piece_disposition.
        # An integrity row is 'integrity_failure' (a separate visible failure), never 'unknown'
        word = row['disposition']
        canonical = A99.FIXED_WORDS.get(layer) or row.get('canonical') or (
            word if word in A99.VOCABULARY else A99.LEGACY_WORDS.get(word))
        if canonical not in A99.VOCABULARY:
            row['canonical_listed'] = 'the ROOT word %r is not in the shared vocabulary; recorded as unknown' % word
            canonical = 'unknown'
        row.update(canonical=canonical, **{'class': A99.WORD_CLASS[canonical]})
        out['counts'][row['disposition']] = out['counts'].get(row['disposition'], 0) + 1
        tally = out.setdefault('counts_canonical', {})
        tally[canonical] = tally.get(canonical, 0) + 1
        out['entries'].append(row)
        rows.append(row)
    native18 = sorted(native_entries)
    basis_counts = dict(record=0, receipt=0, scan=0, not_measured=0)
    for r in rows:
        if r.get('coverage_basis') in basis_counts:
            basis_counts[r['coverage_basis']] += 1
    out.update(basis_counts=basis_counts,
               native_basis=dict(setting='%s=%s' % (getattr(A99, 'SCAN_SETTING', 'FRANKIE_ALL99_SCAN'), 'on' if scan else 'off'),
                                 records_read=record_reads,
                                 carriers={k: carriers.get(k, {}).get('basis') for k in ('native.member', 'native.lifecycle')},
                                 rule='the native carriers come from the sealed records only (derive.json bedrock block, '
                                      'the bound bedrock receipt, the bound native-layer records, the projection plan, a '
                                      'stat per ledger); no ledger is read; an entry no record covers is not_measured and '
                                      'the day proceeds; ' + getattr(A99, 'SCAN_RULE', 'FRANKIE_ALL99_SCAN=on scans')))
    out.update(listed=len(out['entries']), carriers=carriers, in_picture=in_picture, picture_why=picture_why,
               derivation=dict(path=(calc.get('derivation') or {}).get('path'), failure_count=failures, read_error=derive_why,
                               bedrock=('skipped: %s' % bedrock.get('reason')) if bedrock.get('skipped') else
                               ('derived %d layer(s)' % len(bedrock.get('layers') or [])) if bedrock else 'none recorded'),
               native_only=dict(entries=native18, admitted=[r['entry'] for r in rows if r['entry'] in native_entries
                                                            and r['disposition'] == 'admitted'],
                                records=dict(path=str(nl_path) if nl_path else None, used=bool(native_records),
                                             listed=native_records_why,
                                             group_proxy=[r['entry'] for r in rows if r.get('basis') == 'group_proxy']),
                                rule='the 18 native-only entries are carried only by native.member / native.lifecycle (Greg, '
                                     '2026-10-07: they must reach Frankie and both teachers; every NEW run has the native pass ON)'),
               absent=[dict(entry=r['entry'], reason=r['reason']) for r in out['entries'] if r['disposition'] == 'absent'],
               disabled=[r['entry'] for r in out['entries'] if r['disposition'] == 'disabled'],
               integrity=[dict(entry=r['entry'], reason=r['reason']) for r in out['entries'] if r['disposition'] == 'integrity'],
               requests=sorted({r['entry'] for r in out['entries'] if r['disposition'] == 'absent' and r.get('produced') is False}))
    # the shared field (FRANKIE_ALL99_COVERAGE_V1) from the same rows, and its own validation (findings, never raised)
    field_rows = [dict({k: v for k, v in r.items() if k not in ('role', 'policy')}, consumer='the shared market timeline picture')
                  for r in rows]
    try:
        coverage = A99.field('root', day, field_rows, code_root=code_root, stage='root', registry_doc=reg,
                             basis=dict(plan_policy=plan_policy, in_picture=in_picture, derivation=out['derivation'],
                                        basis_counts=basis_counts))
        coverage['validation'] = A99.validate(coverage) if hasattr(A99, 'validate') else 'no validator in this checkout'
    except Exception as error:  # noqa: BLE001 - the field is accounting; its failure is recorded, never hidden
        coverage = dict(schema='FRANKIE_ALL99_COVERAGE_V1', error='%s: %s' % (type(error).__name__, error),
                        rule='the shared field could not be built; nothing is inferred')
    out['coverage'] = coverage
    return out


def all99_summary(doc):
    """The one-day inspection's projection of an all-99 list: counts, the absent/disabled/integrity entries, the pin, the
    native-only entries and the shared field's counts and validation."""
    if not doc:
        return None
    cov = doc.get('coverage') or {}
    return dict(counts=doc.get('counts'), counts_canonical=doc.get('counts_canonical'), listed=doc.get('listed'),
                in_picture=doc.get('in_picture'), picture_why=doc.get('picture_why'),
                absent=doc.get('absent'), disabled=doc.get('disabled'), integrity=doc.get('integrity'),
                native_only=doc.get('native_only'),
                crosswalk=dict(integrity=(doc.get('crosswalk') or {}).get('integrity'),
                               sha256=(doc.get('crosswalk') or {}).get('actual_sha256')),
                carriers={k: v.get('status') for k, v in (doc.get('carriers') or {}).items()},
                coverage=dict(schema=cov.get('schema'), counts=cov.get('counts'), integrity_ok=cov.get('integrity_ok'),
                              validation=cov.get('validation'), error=cov.get('error')))


def last_json_line(log):
    """The last non-empty line of a child's log parsed as a JSON object (a child prints its receipt last), else None."""
    try:
        with open(log, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 4 * 1024 * 1024))       # the tail holds the last line (a receipt is far smaller)
            lines = [z for z in f.read().decode('utf-8', 'replace').splitlines() if z.strip()]
        value = json.loads(lines[-1]) if lines else None
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def load_derive(output):
    """(derive.json parsed, None) or (None, why) of a ROOT output: read and parsed ONCE per Run.root, then passed along."""
    try:
        return json.loads((Path(output) / 'work' / 'derive.json').read_bytes()), None
    except (OSError, ValueError) as error:
        return None, '%s: %s' % (type(error).__name__, error)


def receipt_pins(calc, receipt_path, receipt_sha256):
    """{path: {bytes, sha256, not_after_ns}} of the files a ROOT receipt pins (derivation, digest, external computation)
    plus the receipt itself (hashed once by the caller): the brain stage takes them by claim (size and recorded sha256,
    the file not newer than the receipt) and reads nothing whole (2026-10-09, one pass)."""
    out = {}
    try:
        not_after = os.stat(receipt_path).st_mtime_ns
        out[str(receipt_path)] = dict(bytes=os.stat(receipt_path).st_size, sha256=receipt_sha256, not_after_ns=not_after,
                                      basis='hashed once by Run.root')
    except OSError:
        return out
    for field in ('derivation', 'digest', 'external_computation'):
        pin = (calc or {}).get(field)
        if isinstance(pin, dict) and pin.get('path') and isinstance(pin.get('bytes'), int) and pin.get('sha256'):
            out[str(pin['path'])] = dict(bytes=pin['bytes'], sha256=pin['sha256'], not_after_ns=not_after,
                                         basis='the ROOT receipt\'s %s pin' % field)
    return out


def native_pass_facts(output, calc, policy, child_seconds, derive=None):
    """What the ROOT's native pass (bedrock on under the shared policy) did, for the receipt and the one-day inspection:
    requested on/off, the derivation's own bedrock record (skipped/reason, its timings when recorded, the ledgers it
    produced), and the ROOT child's wall seconds on the held 16-CPU lane. The ADDED time of the native pass is this ROOT's
    seconds against a bedrock-off ROOT of the same day: none has run yet, so it is UNMEASURED (named, never estimated
    here). A failed native pass is listed with its reason; it never rejects the day by this caller."""
    out = dict(requested='on' if policy else 'off (legacy plan)', root_child_seconds=child_seconds, cpus=16,
               added_seconds='unmeasured: compare with a bedrock-off ROOT of the same day (none run)')
    derive, why = derive if derive is not None else load_derive(output)
    if derive is None:
        out.update(derive='unreadable or absent: %s' % why)
        return out
    b = derive.get('bedrock') if isinstance(derive.get('bedrock'), dict) else None
    if b is None:
        out.update(status='absent', reason='derive.json records no bedrock pass')
    elif b.get('skipped'):
        out.update(status='skipped', reason=b.get('reason'))
    else:
        out.update(status='derived', ledgers=sorted(b.get('ledgers') or {}),
                   **{k: b[k] for k in ('seconds', 'timings', 'phase_seconds', 'emission', 'failure', 'error') if k in b})
    for k in ('timings', 'phase_seconds', 'seconds'):
        if k in derive:
            out['derive_' + k] = derive[k]
    if calc:
        out['root_processes'] = calc.get('root_processes')
    return out


class Run:
    def __init__(self, a, plan, code_root, commit, log=print):
        self.a, self.plan, self.code_root, self.commit, self.log = a, plan, Path(code_root), commit, log
        self.dir = RUNS / plan['run']
        self.box = self.code_root / 'deploy' / 'aws' / 'box'
        self.floor = int(a.disk_floor_gb * 1024 ** 3)
        self.stopped = None
        self._cpu = {}                     # (stage, key) -> the CPU ledger's line for the child: booked, waiting, refused
        self._map = None
        self._attached = {}
        self._knowledge = {}
        self.queue_previous = None       # the class worker: (PREVIOUS, None, from) taken from the class line
        self.school_day = None           # the class worker: the class line's school-day number = the report number N
        self._school_recovery = set()    # recover_school: the days whose own successor drain holds drain.lock (no nested drain)
        self._root_rederived = {}        # day -> session 9: the root step record re-derived from the ROOT on disk (root_on_disk)
        self._teacher_rederived = None   # the current teacher call's days whose root record was re-derived (on its receipt)
        self._day_file_sha = {}          # (day, ingest dir) -> (the attached day file's sha256, why absent), read once (day_rows)
        self._identity_recorded = {}     # day -> [what differed on the day's retained outputs] (Greg, 2026-10-09: recorded
                                         # on every step record of the day, never a refusal)
        # THE OWNER BINDING (Step 8, 2026-10-07): a queue day carries its owner (run, day, host, attempt, commit, code root,
        # exact CPU set, booking, day-specific save marker), bound by the queue BEFORE dispatch. This Run reads the save
        # request from ITS OWN marker (never a process-global environment variable: the two main lanes are threads of one
        # process) and hands that marker to its children only. The Linux lane's agent sets the same variable per job.
        self.owner = None
        self.owned_attempt = None        # the main queue's exact ROOT attempt name (the Linux lane's is FRANKIE_LANE_ATTEMPT)
        self.stop_marker = os.environ.get('FRANKIE_LANE_STOP_FILE')
        sys.path.insert(0, str(self.box))
        from frankie_box_progress import Probe
        import frankie_box_cores
        self.cores = frankie_box_cores     # the box's CPU booking ledger (DAY_RUN_CPUS, ingest_workers, WAITING_EXIT)
        self.probe = Probe(self.dir, request_sha256=plan_digest(plan), phase='experiment')

    def bind_owner(self, owner):
        """The queue's owner binding for this Run: its attempt, its marker (its children inherit exactly that one)."""
        self.owner = owner
        if owner:
            self.owned_attempt = owner.get('attempt')
            self.stop_marker = owner.get('marker') or self.stop_marker

    def save_requested(self):
        marker = self.stop_marker
        return bool(marker and Path(marker).is_file())

    def successors(self, day):
        """Explicit owner corrections finish before this day's next dependent operation."""
        if day in self._school_recovery:
            # inside the day's own drain (recover_school, called by successor_dispatch.drain under drain.lock): that
            # caller holds drain.lock and re-entering it here would block on its own flock. Only the one recovery bound to
            # its operation skips it; nothing else does.
            return []
        import frankie_box_successor_dispatch as S
        completed = S.drain(self, day)
        if completed and (self.receipt('successors', day) or {}).get('acknowledgments') != completed:
            self.record('successors', day, 'done', acknowledgments=completed)
        return completed

    def check_save(self):
        if self.save_requested():
            self.log('day saved on its assigned lane; resume the retained attempt')
            raise SystemExit(75)

    def child_saved(self, stage, key, code, log=None, **fields):
        """The ONE classification of a stage child's exit 75 (stacks pass 2026-10-07: school R6, reports X5; every stage
        with a save route exits SAVED_EXIT the way the ROOT does): None unless code is SAVED_EXIT and the ledger did not
        print a 'waiting for a CPU booking' line for this call (that 75 is 'not started', the caller's own waiting
        record); else the step's 'saved' receipt, returned for the caller to return. A 75 on this owner's STANDING
        marker never reaches a step: child() raises SystemExit(75) right after the child, and the day thread
        (frankie_box_frankie_queue._thread_end) classifies the DAY saved with its booking retained. A 75 WITHOUT the
        standing marker is the child's own save route (a SIGTERM to the child: mark only, run to the next save point,
        exact durable state); it was recorded 'failed' (or counted as a failed teacher call) until this pass. Now:
        'saved', never a failure, never a requeue; nothing is booked or released here (a step inside the held slot never
        touches the booking; the slot is the day's). done_status is False for 'saved', so the next start re-runs the
        step, which reuses its saved pre-read and written work; the day's later steps read 'saved' as not finished and
        wait, exactly as they do for 'waiting'. The caller does not start a following step after it."""
        if code != SAVED_EXIT:
            return None
        if (self._cpu.get((stage, key)) or {}).get('status') == 'waiting':
            return None
        self.log('%s %s: the step saved at a save point (exit %d) without this owner\'s standing marker; kept, re-run on the '
                 'next start' % (stage, key, code))
        return self.record(stage, key, 'saved', exit_code=code, log=log,
                           reason='the step stopped at a save point on a requested save (exit 75) without this owner\'s '
                                  'standing marker; its saved state is kept; the next start re-runs the step, which reuses '
                                  'its saved pre-read and written work; never a failure or a requeue', **fields)

    # receipts
    def receipt_path(self, stage, key):
        return self.dir / ('batches' if stage in ('teacher', 'lessons', 'survivors') else 'days') / key / (stage + '.json')

    def receipt(self, stage, key):
        path = self.receipt_path(stage, key)
        return json.loads(path.read_bytes()) if path.is_file() else None

    def finished(self, stage, key):
        done = done_status(self.receipt(stage, key))
        if done and stage in ('exchange', 'voice', 'school', 'reports'):
            self.require_current_teacher_inputs(key)
        if done and stage in ('school', 'reports') and not self.school_current(key, stage)[0]:
            return False               # a checked school successor stands: the stage runs again on it (old artifacts stay)
        if done and stage == 'reports' and self.reports_school_stale(key):
            return False               # the reports were rendered on a school the school stage has since replaced
        return done

    def reports_school_stale(self, day):
        """The reports receipt records the school it was rendered on (sha256); once the school stage has re-recorded a
        different checked school, those reports are stale and get their revision under the same number. A reports receipt
        from before that field is not judged by it."""
        r, s = self.receipt('reports', day) or {}, self.receipt('school', day) or {}
        current = s.get('school_sha256') or (s.get('row') or {}).get('sha256')
        if s.get('status') not in ('done', 'reused') or not current:
            return False
        # what the reports were actually rendered with: the day-reports receipt's school_sha256 (the step's own file,
        # <reports-dir>/receipts/<run>/<day>.json; correction_consumer, 2026-10-07), else this run's recorded school
        step = Run.reports_receipt(None, day=day, run=self.plan['run']) or {}
        if 'school_sha256' in step or step.get('school_status') not in (None, 'not given'):
            rendered = step.get('school_sha256')
            return rendered != current             # none rendered (school not given then) while a school stands now: stale
        rendered = (r.get('school') or {}).get('sha256')
        return bool(rendered and rendered != current)

    def school_current(self, day, stage='school'):
        """(current, why) of the day's recorded school against the brain's checked school chain (Codex's
        frankie_box_school_knowledge.retained_school: the indexed original and its explicit checked successors). A
        done/reused school whose file is no longer the latest checked complete school is superseded: the school stage
        runs again through the owner operation and the reports get their revision under the same number; the old
        artifacts stay. A chain that still requires a successor supersedes the school stage only (the reports wait on
        the school stage's own run, never re-rendered on a stale school meanwhile). A corrupt chain raises; it is never
        read as absence."""
        s = self.receipt('school', day) or {}
        if s.get('status') not in ('done', 'reused'):
            return True, None
        import frankie_box_school_knowledge as SK
        retained = SK.retained_school(str(self.plan.get('brain') or BRAIN), day)
        if retained is None:
            return True, None              # nothing indexed for the day: nothing supersedes the recorded file
        if retained['status'] != 'complete':
            return stage != 'school', 'the school chain requires a checked successor of %s' % retained['original']['sha256'][:12]
        recorded = s.get('school_sha256') or (s.get('row') or {}).get('sha256')
        if recorded and recorded != retained['original']['sha256']:
            return False, 'superseded by the checked school successor %s' % retained['original']['sha256'][:12]
        return True, None

    def root_on_disk(self, e):
        """Session 9 (Greg: "stuff like that should never kill workflow"): a stage's readiness is judged from the ROOT ON
        DISK, never from a stale step record. When the day's root step record is not finished (a killed attempt's 'failed',
        a worker killed before it re-recorded the step) but root_of finds the day's completed calculations-receipt.json
        (the same resolution root()'s reused branch uses), root(e) re-records the step ('reused' with the receipt's
        policy; a policy mismatch stays its refusal, as today); the re-derivation is noted (the teacher receipt carries
        it). Returns the day's root step record (re-derived or as it stands). A save (int SystemExit) propagates."""
        r = self.receipt('root', e['day'])
        # 2026-10-09 (Greg: "use previously generated one"): a record 'refused' on a policy mismatch (retained_policy) is
        # never final: it is re-derived below from the retained receipt ('reused', the difference recorded)
        if r and (r.get('status') in FINISHED or r.get('remote_calculations')):
            return r
        calc = None
        try:
            calc, _ = root_of(e, self.plan['run'])
            if calc is None:
                return r
            fresh = self.root(e) or self.receipt('root', e['day']) or {}
        except (Exception, SystemExit) as error:  # noqa: BLE001 - listed on the record's reader, never kills the stage
            if isinstance(error, SystemExit) and isinstance(error.code, int):
                raise                                  # a requested save (exit 75) is honoured, never swallowed
            self._root_rederived[e['day']] = ('root step NOT re-recorded from the retained receipt %s (%s: %s); the record '
                                              'stays %s' % (calc, type(error).__name__, str(error)[:300],
                                                            (r or {}).get('status') or 'absent'))
            self.log('root %s %s: %s' % (self.plan['run'], e['day'], self._root_rederived[e['day']]))
            return r
        self._root_rederived[e['day']] = ('root step re-recorded from the retained receipt %s (was %s, now %s)' % (
            calc / 'calculations-receipt.json', (r or {}).get('status') or 'absent', fresh.get('status')))
        self.log('root %s %s: %s' % (self.plan['run'], e['day'], self._root_rederived[e['day']]))
        return fresh

    def remote_root(self, day):
        receipt = self.receipt('root', day)
        if receipt and receipt.get('remote_calculations') and receipt.get('status') in FINISHED:
            return receipt
        return None

    def remote_stage(self, stage, day):
        root = self.remote_root(day)
        if root is None:
            return None
        key = 'day-' + day if stage == 'teacher' else day
        receipt = self.receipt(stage, key)
        if receipt and done_status(receipt) and (receipt.get('remote_owner') == root['owner'] or
                                                 stage in ('fetch', 'ingest', 'external')):
            return receipt
        return self.record(stage, key, 'waiting', owner=root['owner'],
                           reason='the owning AWS lane has not published a completed %s receipt; its artifacts stay there' % stage)

    def brain_stage(self, day, stage, sources, summary=None, inline_limit=2 * 1024 * 1024, declined='record', known=None):
        """Immediately commit newly available stage knowledge to Frankie's brain before advancing. Session 9: each
        source's sha256 comes from its attempt's FRANKIE_FILE_CLAIM row when the claim still holds (stat + last 64 KiB;
        the ROOT's digest, layers, spools and ledgers), else from one whole read, after which a large source's claim row
        is written (frankie_box_brain.stage_source_witness); the basis per source is on this record (source_witness).
        An entry filed before the digest existed takes the digest as an attachment (status 'digest attached later';
        knowledge_sha256 is then the attached file's). The brain's own decline of DIFFERENT knowledge (R16) is a recorded
        outcome on the step's receipt (status 'declined', reason, the existing entry's hashes), never the day's failure;
        declined='raise' keeps the exception (E-5's caller moves the replaced day-file entry aside on it)."""
        import frankie_box_brain as BR
        brain = Path(self.plan.get('brain') or str(BRAIN))
        entry = brain / ('%s-%s' % (day, stage))
        try:
            manifest, reused = BR.write_stage_entry(brain, day, stage, sources, summary=summary, inline_limit=inline_limit,
                                                    known=known)
        except ValueError as error:
            if declined == 'raise' or 'different' not in str(error) or 'stage knowledge' not in str(error):
                raise
            have = {k: (sha256_file(entry / n) if (entry / n).is_file() else None)
                    for k, n in (('manifest_sha256', 'MANIFEST.json'), ('knowledge_sha256', 'stage-knowledge.json'))}
            self.log('brain %s %s: DECLINED (recorded, the day continues): %s' % (stage, day, error))
            return dict(path=str(entry), reused=False, status='declined', reason=str(error),
                        rule='the brain keeps the knowledge it holds (R16); this record names the decline', **have)
        witnessed = manifest.get('source_witness') or []
        status = manifest.get('attachment') or ('reused' if reused else 'written')
        self.log('brain %s %s: %s (%s); sources: %s' % (stage, day, entry, status,
                                                         ', '.join('%s %s' % (Path(w['path']).name, w['basis'])
                                                                   for w in witnessed)))
        return dict(path=str(entry), reused=reused, status=status,
                    manifest_sha256=sha256_file(entry / 'MANIFEST.json'),
                    knowledge_sha256=sha256_file(entry / (manifest.get('current_knowledge') or 'stage-knowledge.json')),
                    source_witness=witnessed)

    def record(self, stage, key, status, **fields):
        path = self.receipt_path(stage, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = self.receipt(stage, key)
        cpu = [self._cpu.pop(k) for k in sorted(self._cpu) if k[0] == stage and (k[1] == key or k[1].startswith(key + '-'))]
        if cpu:
            fields['cpu_booking'] = cpu if len(cpu) > 1 else cpu[0]
            waits = [c for c in cpu if c['status'] == 'waiting']
            refusals = [c for c in cpu if c['status'] == 'refused']
            if waits and status == 'failed':      # not started for want of CPUs: waiting, retried by a later start
                status, fields['reason'] = 'waiting', '; '.join(c['line'] for c in waits)
            elif refusals and status == 'failed':  # the sizing rule refused the booking: the rule is the reason
                fields['reason'] = '; '.join(c['line'] for c in refusals)
        # Successor completion already includes its checked publication/sync acknowledgment;
        # do not create another mailbox operation after that durable acknowledgment.
        # (the inspection reporter's receipt is operator review, not a stage knowledge boundary)
        if status in FINISHED and stage not in ('successors', 'inspection') and os.environ.get('FRANKIE_LANE_MAILBOX'):
            import frankie_box_lane_state as LS
            LS.boundary(os.environ.get('FRANKIE_LANE_DAY', key[:8]), stage, brain=self.plan.get('brain') or BRAIN)
        fields['knowledge_available'] = self._knowledge.pop((stage, key), None)
        if stage == 'teacher' and self._teacher_rederived:
            fields.setdefault('root_rederived', self._teacher_rederived)   # session 9: readiness from the ROOT on disk
        noted = self._identity_recorded.get(key[4:] if key.startswith('day-') else key)
        if noted:
            fields.setdefault('identity_recorded', list(noted))       # what differed; the run proceeded (Greg, 2026-10-09)
        chosen = DUPLICATES.get(key[4:] if key.startswith('day-') else key)
        if chosen:
            fields.setdefault('duplicates_chosen', dict(chosen))     # duplicate ingests/ROOTs: candidates and the choice
        body = dict(schema='FRANKIE_EXPERIMENT_STEP_V1', run=self.plan['run'], stage=stage, key=key, status=status,
                    at=time.time(), commit=self.commit, plan_sha256=plan_digest(self.plan),
                    directive_sha256=(self.plan.get('directive') or {}).get('sha256'), **fields)
        if previous:
            body['previous_attempts'] = (previous.get('previous_attempts') or []) + [
                {k: previous.get(k) for k in ('status', 'at', 'reason', 'exit_code')}]
        from frankie_box_durable import write_json
        write_json(path, body)
        if not previous or previous.get('status') != status:
            # 2026-10-09: a stage's status changed: every event-driven waiter on the box re-checks now (a repeated
            # 'waiting' record wakes nobody, so a waiter never wakes itself)
            try:
                import frankie_box_frankie_queue as Q
                Q.notify('stage-%s' % stage, run=self.plan['run'], key=key, status=status)
            except Exception:  # noqa: BLE001 - a wake never fails a record
                pass
        self.log('%s %s: %s%s' % (stage, key, status, (' (%s)' % fields['reason']) if fields.get('reason') else ''))
        return body

    # disk
    INLINE_SPOOL_LAYERS = ('legacy_book_imbalance', 'legacy_structure_observables')
    # session 6: the reason a ROOT ran without process 4 (the Markdown digest); on the root record and the brain entry
    DIGEST_NOT_BUILT = ('not built: no stage of this day reads the derivation digest for work (only the classroom does, '
                        'on a classroom-arm day; the plan key root_digest on builds it for every day)')

    @staticmethod
    def root_digest_setting(entry, plan, environ=None):
        """The ROOT's DIGEST (process 4, the Markdown digest) as a run setting (session 6, 2026-10-08): FRANKIE_ROOT_DIGEST
        on|off given at kick time (frankie_box_frankie_queue.sh exports every FRANKIE_* shell variable to the worker it
        starts, FA-6; Run.child hands the worker's whole environment to the ROOT) wins; any other value raises ValueError
        (root() refuses the day with the reason, nothing runs); unset = the day's rule: on for a classroom-arm day (the
        classroom is the only stage that reads the digest for work) or when the plan says root_digest on, else off.
        Returns dict(value, basis); recorded on the root record (digest_setting) and the inspection inputs."""
        environ = os.environ if environ is None else environ
        given = environ.get('FRANKIE_ROOT_DIGEST')
        if given is not None:
            if given not in ('on', 'off'):
                raise ValueError('FRANKIE_ROOT_DIGEST must be on or off, not %r' % given)
            return dict(value=given, basis='FRANKIE_ROOT_DIGEST=%s given at kick time (run setting)' % given)
        if entry.get('classroom_arm'):
            return dict(value='on', basis='classroom-arm day: the classroom reads the digest')
        if (plan or {}).get('root_digest') == 'on':
            return dict(value='on', basis='plan root_digest on')
        return dict(value='off', basis=Run.DIGEST_NOT_BUILT)

    def inline_spool_layer_bytes(self, record):
        """Bytes of a measured ROOT step's old-form (inline) spool layers: re-encodings of its spools that a ROOT on this
        code no longer writes (2026-10-08: frankie_box_layer_spool references, a few KB each). Recorded on the step when
        it was measured on this code; else read from its calculations directory (a reference layer counts 0)."""
        if isinstance(record.get('inline_spool_layer_bytes'), int):
            return record['inline_spool_layer_bytes']
        calculations = record.get('calculations')
        if not calculations:
            return 0
        from frankie_box_layer_spool import read_reference
        total = 0
        for name in self.INLINE_SPOOL_LAYERS:
            path = Path(calculations) / 'work' / 'derived' / (name + '.json')
            try:
                if path.is_file() and path.lstat().st_nlink == 1 and read_reference(path) is None:
                    total += path.lstat().st_size
            except (OSError, ValueError):
                continue
        return total

    def disk_ok(self, stage, resume=False):
        """False (self.stopped names why) only when the step's measured size would take free space below the floor. The
        numbers are recorded on self.disk_facts either way. 2026-10-09 (Greg: a gate we coded never blocks fine data):
        an owned ROOT RESUME is never gated (its bytes are on disk already), and a fresh ROOT reserves only what ROOTs
        measured on the current form wrote (a record carrying inline_spool_layer_bytes, since 2026-10-08); an older
        form's pre-clean size is listed, never reserved."""
        free = shutil.disk_usage(BOX_ROOT).free
        sizes, adjusted, old_form = [], 0, []
        for p in (self.dir / 'days').glob('*/%s.json' % stage) if (self.dir / 'days').is_dir() else ():
            r = json.loads(p.read_bytes())
            if r.get('status') == 'done' and isinstance(r.get('new_bytes'), int):
                if stage == 'root' and 'inline_spool_layer_bytes' not in r:
                    old_form.append(dict(day=p.parent.name, new_bytes=r['new_bytes']))
                    continue
                inline = self.inline_spool_layer_bytes(r) if stage == 'root' else 0
                adjusted += inline
                sizes.append(r['new_bytes'] - inline)
        for p in (self.dir / 'batches').glob('*/%s.json' % stage) if (self.dir / 'batches').is_dir() else ():
            r = json.loads(p.read_bytes())
            if r.get('status') == 'done' and isinstance(r.get('new_bytes'), int):
                sizes.append(r['new_bytes'])
        largest = max(sizes) if sizes else 0
        self.disk_facts = dict(stage=stage, free_bytes=free, largest_measured_step_bytes=largest, floor_bytes=self.floor,
                               measured_steps=len(sizes), old_form_not_reserved=old_form, resume=resume)
        if resume:
            self.disk_facts['decision'] = 'an owned resume: its bytes are on disk already; not gated'
            return True
        self.disk_facts['decision'] = 'gated' if free - largest < self.floor else 'fits'
        if free - largest < self.floor:
            self.stopped = dict(stage=stage, free_bytes=free, largest_measured_step_bytes=largest, floor_bytes=self.floor,
                                measured_steps=len(sizes), inline_spool_layer_bytes_not_reserved=adjusted,
                                old_form_not_reserved=old_form,
                                reason='the step would take free space below the floor (largest measured %s step %d '
                                       'bytes, free %d, floor %d)' % (stage, largest, free, self.floor))
            return False
        return True

    # children
    def child(self, stage, key, script, env):
        """One committed box script as a child; its whole output in <run>/logs/<key>-<stage>.log."""
        successor = script == 'frankie_box_teacher_successor.sh'
        if not successor and any(e['day'] == key[:8] for e in self.plan['days']):
            self.successors(key[:8])
        self.check_save()
        if self.remote_root(key[:8]):
            raise ValueError('this day belongs to its remote AWS lane; no local stage dispatch')
        logs = self.dir / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        log_path = logs / ('%s-%s.log' % (key, stage))
        import frankie_box_lane_state as LS
        self._knowledge[(stage, key)] = LS.boundary(os.environ.get('FRANKIE_LANE_DAY', key[:8]), stage,
                                                 brain=self.plan.get('brain') or BRAIN)
        if stage in ('lessons', 'exchange') and not successor:
            self.require_current_teacher_inputs(key[:8])
        if stage in ('voice', 'school', 'reports') and not successor:
            self.require_current_exchange(key[:8], env)
        full = dict(os.environ, MARKETS_SHA=self.commit, CODE_ROOT=str(self.code_root), **{k: str(v) for k, v in env.items()})
        # the day's own save marker reaches the child, and only the day's: a sibling lane's marker never leaks across threads
        full.pop('FRANKIE_LANE_STOP_FILE', None)
        if self.stop_marker:
            full['FRANKIE_LANE_STOP_FILE'] = str(self.stop_marker)
        # the stage's probe directories (stacks pass 2026-10-07: teacher 4, ingest X4, reports X6; probe_directories):
        # named to the heartbeat below (checked first) and exported to the child, whose forked/spawned workers inherit it
        # (frankie_box_stage_progress reads every absolute work directory a process's environment names). Not an input:
        # no stage reads it; the queue never carries it as a run setting (RUN_SETTING_IDENTITY)
        probe_dirs = probe_directories(stage, env, self.code_root)
        full.pop(PROBE_DIRS_ENV, None)
        if probe_dirs:
            full[PROBE_DIRS_ENV] = ','.join(probe_dirs)
        command = ['sh' if script.endswith('ingest_block.sh') else 'bash', str(self.box / script)]
        if stage in self.cores.DAY_RUN_STAGES:  # exactly 16 CPUs booked, the step under taskset -c <them> (frankie_box_cores.py)
            inside = getattr(self, 'slot_booking', None)   # the day's held slot (ROOT line): its steps never re-book
            command = [sys.executable, '-B', str(self.box / 'frankie_box_cores.py'), 'run', '--kind', 'day-run', '--day', key,
                       '--run', self.plan['run'], '--stage', stage, '--commit', self.commit,
                       '--size', str(self.day_cpus())] + \
                (['--inside', inside] if inside else []) + ['--'] + command
        # the stage heartbeat (Greg, 2026-10-07: probes on every step; frankie_box_stage_progress): one JSON line about
        # every 30 s to <run>/days/<day>/progress/<stage>.jsonl, measured from outside the child (its /proc tree and log)
        # plus what the child itself publishes; a final line with the exit code. It never changes the child, its
        # inputs, outputs or exit; a probe that cannot start is logged once and the stage runs without it
        heartbeat = None
        try:
            import frankie_box_stage_progress as SP
            # FA-4: a stage that names its output directory (the ROOT: OUTPUT_ROOT = experiment-roots/<attempt>) has its
            # FRANKIE_WORK_PROBE_V1 progress.json there; the heartbeat reads it (and its native-overlap/ beside it)
            # the stage's own directories follow (probe_directories above: the teacher's rows directories, the ingest's
            # block data directory and RESUME_DIR, the reports' receipt directory, every work directory the env names)
            heartbeat = SP.Heartbeat(self.dir, key, stage, log_path=log_path,
                                     probe_dirs=([str(env['OUTPUT_ROOT'])] if env.get('OUTPUT_ROOT') else []) + probe_dirs)
            full.update(heartbeat.env())
        except Exception as error:  # noqa: BLE001 - the probe is never the stage's outcome
            self.log('%s %s: no stage heartbeat (%s: %s)' % (stage, key, type(error).__name__, error))
        with open(log_path, 'ab') as out:
            out.write(('\n### %s %s %s at %s\n' % (stage, key, script, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))).encode())
            out.flush()
            start = out.tell()
            code = None
            try:
                with subprocess.Popen(command, env=full, stdout=out, stderr=subprocess.STDOUT) as proc:
                    if heartbeat is not None:
                        heartbeat.start(proc.pid)
                    try:
                        code = proc.wait()
                    except BaseException:
                        proc.kill()               # subprocess.run's own behaviour on an interrupted wait, unchanged
                        raise
            finally:
                if heartbeat is not None:
                    heartbeat.stop('exited' if code is not None else 'not started or interrupted', code)
        # Children with continuation hooks observe the same durable stop marker. Other children finish their
        # current retained operation. Never kill their workers or start a following stage after a save request.
        self.check_save()
        with open(log_path, 'rb') as read:
            read.seek(start)
            lines = read.read().decode('utf-8', 'replace').splitlines()
        # the ledger's own line from this run of the step (frankie_box_cores.py prints it): booked, waiting or refused
        for tag, status, exit_code in (('CPU_BOOKING_WAITING ', 'waiting', self.cores.WAITING_EXIT),
                                       ('CPU_BOOKING_REFUSED ', 'refused', self.cores.REFUSED_EXIT),
                                       ('CPU_BOOKING ', 'booked', None)):
            found = [line[len(tag):] for line in lines if line.startswith(tag)]
            if found and exit_code in (None, code):
                self._cpu[(stage, key)] = dict(status=status, line=found[-1], exit_code=code)
                break
        return code, str(log_path)

    # stages
    def fetch_inspection(self, e, use, outputs):
        """The fetch step's one-day inspection record: inputs (the day's committed manifest pinned, whether a presigned map
        was given: its URL is never recorded), how it was used, what it produced."""
        manifest = (Path(self.code_root) / e['manifest']) if e.get('manifest') else None
        return dict(inputs=dict(manifest=pin_or_listed(manifest) if manifest else dict(absent=e.get('manifest_gap')),
                                map_url_given=bool(os.environ.get('MAP_URL'))),
                    use=use, outputs=outputs)

    def fetch(self, e):
        receipt, why = ingest_of(e, self.plan['run'])
        if receipt or why:
            return self.record('fetch', e['day'], 'skipped' if receipt else 'refused',
                               reason='the day is ingested already: %s' % receipt.parent if receipt else why,
                               inspection=self.fetch_inspection(
                                   e, 'not fetched: %s' % ('the day has a sealed ingest (its partitions are not needed)'
                                                           if receipt else why),
                                   dict(sealed_ingest_receipt=pin_or_listed(receipt)) if receipt else {}))
        if not e['manifest']:
            return self.record('fetch', e['day'], 'waiting', reason=e['manifest_gap'],
                               inspection=self.fetch_inspection(e, 'waiting: no committed per-day manifest', {}))
        if not os.environ.get('MAP_URL'):
            return self.record('fetch', e['day'], 'refused', reason='MAP_URL not set: dispatch with presign=<bucket>/<key> '
                                                                    'for every partition of the days',
                               inspection=self.fetch_inspection(e, 'refused: no presigned map', {}))
        if not self.disk_ok('fetch'):
            return None
        code, log = self.child('fetch', e['day'], 'frankie_box_ingest_block.sh', dict(ACTION='fetch', MANIFEST=e['manifest']))
        return self.record('fetch', e['day'], 'done' if code == 0 else 'failed', exit_code=code, log=log,
                           reason=None if code == 0 else 'the fetch refused or failed a partition (its receipt is in the log)',
                           inspection=self.fetch_inspection(
                               e, 'every manifest partition fetched through the presigned map, sha256 and size verified '
                                  'by frankie_box_ingest_block.sh ACTION=fetch (per-partition receipts in the log)',
                               dict(exit_code=code, log=pin_or_listed(log))))

    def ingest(self, e):
        receipt, why = ingest_of(e, self.plan['run'])
        if why:
            return self.record('ingest', e['day'], 'refused', reason=why)
        if receipt:
            brain_entry = self.brain_stage(e['day'], 'ingest', [receipt],
                                           summary=dict(ingest=str(receipt.parent), receipt_sha256=sha256_file(receipt)))
            return self.record('ingest', e['day'], 'reused', ingest=str(receipt.parent), receipt=str(receipt),
                               receipt_sha256=sha256_file(receipt), brain_entry=brain_entry,
                               inspection=dict(inputs=dict(sealed_ingest=str(receipt.parent)),
                                               use='reused: the day\'s sealed ingest stands (never re-ingested)',
                                               outputs=dict(receipt=pin_or_listed(receipt),
                                                            recorded=ingest_receipt_facts(receipt))))
        if e['day'] == MONDAY:
            return self.record('ingest', e['day'], 'refused', reason='Monday 20211004 is the gold standard: never re-ingested; '
                                                                     'name its sealed ingest directory in the plan')
        if not e['manifest']:
            return self.record('ingest', e['day'], 'waiting', reason=e['manifest_gap'])
        # Greg, 2026-09-29 ("Do 1-5 now"): the experiment's journal is ingested by the parallel writer (saved passes, so a
        # stopped day resumes), with no full-book copy at a group close and the conformance drain deferred; days run side
        # by side (--parallel-days)
        # CPU booking (Greg, 2026-10-07 night: "day 1 gets ALL 32 CPUs for every step", the ingest included): each day
        # process books its own DAY_CPUS in the ledger (frankie_box_ingest_block.sh; it was a fixed WORKERS=7, which
        # pinned every ingest to 8 CPUs). ingest_size says how many; WORKERS = DAY_CPUS - 1 there (one pool at a time,
        # frankie_box_cores.INGEST_RULE) unless --ingest-workers is a lower ceiling. The output never depends on the count
        size, workers, sizing = self.ingest_size()
        env = dict(ACTION='ingest', MANIFEST=e['manifest'], DAY_CPUS=size, MODE=self.a.ingest_mode,
                   OBSERVATION=self.a.ingest_observation, VERIFY=self.a.ingest_verify)
        if workers is not None:
            env['WORKERS'] = workers
        resume = self.resume_dir(e)
        if resume:
            env['RESUME_DIR'] = str(resume)
        if e.get('opens_after'):
            opening, gap = self.opening_of(e)
            if gap:
                return self.record('ingest', e['day'], 'refused', reason=gap)
            if opening:
                env['OPENING_RECEIPT'] = str(opening)
        if not self.disk_ok('ingest'):
            return None
        inputs = dict(manifest=pin_or_listed(Path(self.code_root) / e['manifest']),
                      opening_receipt=pin_or_listed(env.get('OPENING_RECEIPT')) if env.get('OPENING_RECEIPT') else
                      dict(absent='no prior-day receipt named: the day warms its own book from its tail partition'),
                      resume_dir=env.get('RESUME_DIR'),
                      settings={k: env.get(k, 'DAY_CPUS - 1 (the wrapper\'s default)') for k in
                                ('DAY_CPUS', 'WORKERS', 'MODE', 'OBSERVATION', 'VERIFY')}, cpu_sizing=sizing)
        before = set(WORK.glob('ingest-*'))
        code, log = self.child('ingest', e['day'], 'frankie_box_ingest_block.sh', env)
        made = sorted(set(WORK.glob('ingest-*')) - before)
        receipt, why = ingest_of(e, self.plan['run'])
        cpu = self._cpu.get(('ingest', e['day']))     # the ledger's own line of this dispatch (booked / waiting / refused)
        if code == self.cores.WAITING_EXIT and (cpu or {}).get('status') == 'waiting' and not receipt:
            # not started: the day's CPUs were not free (a ROOT or another day holds them); visible, retried on a later
            # start, never a failure (the ledger's waiting line names the free and needed counts)
            return self.record('ingest', e['day'], 'waiting', exit_code=code, log=log, cpu_booking=cpu,
                               reason=cpu['line'], inspection=dict(inputs=inputs, use='waiting for its CPU booking: %s'
                                                                   % cpu['line'], outputs=dict(exit_code=code)))
        saved = self.child_saved('ingest', e['day'], code, log, directories=[str(p) for p in made], cpu_booking=cpu,
                                 resume_dir=str(self.resume_dir(e) or '') or None,
                                 inspection=dict(inputs=inputs, use='saved at a save point (INGEST_SAVED, ingest-saved-<ts>.json '
                                                                    'in its directory); the next start continues it (RESUME_DIR)',
                                                 outputs=dict(exit_code=code, directories=[str(p) for p in made])))
        if saved:
            return saved
        if code != 0 or not receipt or why:
            return self.record('ingest', e['day'], 'failed', exit_code=code, log=log, directories=[str(p) for p in made],
                               reason=why or 'no sealed ingest of the day after the step (its directory is kept)',
                               inspection=dict(inputs=inputs, use='the ingest did not seal (kept for resume)',
                                               outputs=dict(exit_code=code, directories=[str(p) for p in made])))
        brain_entry = self.brain_stage(e['day'], 'ingest', [receipt],
                                       summary=dict(ingest=str(receipt.parent), receipt_sha256=sha256_file(receipt)))
        return self.record('ingest', e['day'], 'done', exit_code=code, log=log, ingest=str(receipt.parent),
                           receipt=str(receipt), receipt_sha256=sha256_file(receipt), new_bytes=new_bytes(receipt.parent),
                           brain_entry=brain_entry,
                           inspection=dict(inputs=inputs,
                                           use='every manifest member decoded and journaled by the parallel writer '
                                               '(frankie_box_ingest_block.sh ACTION=ingest); %s' % (
                                                   'resumed from %s' % env['RESUME_DIR'] if env.get('RESUME_DIR') else 'a fresh ingest'),
                                           outputs=dict(receipt=pin_or_listed(receipt), recorded=ingest_receipt_facts(receipt),
                                                        directory=str(receipt.parent), new_bytes=new_bytes(receipt.parent))))

    @staticmethod
    def resume_dir(e):
        """A parallel ingest of the day that stopped before its receipt (its saved pass 1 is there): continued, not
        restarted. Two such directories are ambiguous: the newest is continued and the others are listed in the log."""
        found = sorted(p.parent.parent for p in WORK.glob('ingest-%s-ingest-*/segments/plan.json' % e['day'])
                       if not (p.parent.parent / 'ingestion-receipt.json').exists())
        return found[-1] if found else None

    @staticmethod
    def opening_of(e):
        """(the prior trading day's sealed ingest receipt, None); (None, None) when the prior day has none, so the day
        warms its own book from its tail partition; (None, why) only when the prior day is ambiguous (duplicate data).
        Monday's ingest was recovered: its receipt is the recovery receipt on the box (opening_book.py reads both)."""
        # every day warms its own book unless the plan names a prior receipt: a day's journal must not depend on whether
        # the day before happened to seal first when days run side by side (the review of 959c5e12, finding 11)
        return (e['opening_receipt'], None) if e.get('opening_receipt') else (None, None)

    def root(self, e):
        remote = self.remote_root(e['day'])
        if remote is not None:
            return remote
        calc, attempts = root_of(e, self.plan['run'], prefer=self.owned_attempt)
        owned_output = None
        if os.environ.get('FRANKIE_LANE_MAILBOX'):
            attempt = os.environ.get('FRANKIE_LANE_ATTEMPT', '')
            if not re.fullmatch(re.escape('%s-%s-a' % (self.plan['run'], e['day'])) + r'[0-9]+', attempt):
                raise ValueError('remote ROOT requires its original run/day/attempt identity')
            owned_output = ROOTS / attempt
            if owned_output.is_symlink() or any(Path(p) != owned_output for p in attempts):
                raise ValueError('retained ROOT directories differ from the claimed attempt; preserved')
            if calc is not None and calc != owned_output:
                raise ValueError('completed ROOT differs from the claimed attempt; preserved')
            if owned_output.exists() and not owned_output.is_dir():
                raise ValueError('claimed ROOT output is not a retained directory')
        elif self.owned_attempt and calc is None:
            # the main queue's owner binding: the exact attempt bound before dispatch, first dispatch and resume alike;
            # earlier interrupted attempts of the day may exist beside it (they are listed, never resumed as this one);
            # a completed ROOT is reused below whatever its name (the binding then records it, informationally)
            attempt = self.owned_attempt
            if not re.fullmatch(re.escape('%s-%s-a' % (self.plan['run'], e['day'])) + r'[0-9]+', attempt):
                raise ValueError('the owner binding names no run/day/attempt of this day: %s' % attempt)
            owned_output = ROOTS / attempt
            if owned_output.is_symlink() or (owned_output.exists() and not owned_output.is_dir()):
                raise ValueError('the owned ROOT output is not a retained directory: %s' % owned_output)
        policy = self.plan.get('shared_market_policy')
        if calc:
            retained_raw = (calc / 'calculations-receipt.json').read_bytes()     # read once: parsed and hashed
            retained = json.loads(retained_raw)
            if retained.get('day') != e['day'] or retained.get('day_role') != e['role']:
                raise ValueError('retained ROOT receipt belongs to another day/role')
            mismatch = self.shared_policy_mismatch(retained.get('shared_market_policy')) if policy else None
            if mismatch:
                # Greg, 2026-10-09 ("use previously generated one or override ... we know"): the day's completed,
                # receipted ROOT on disk is ALWAYS used. A policy difference (meaning fields only; the code hash is
                # recorded, never compared) is recorded on this step and every later step of the day; never refused,
                # never recomputed, never a new run name. Only data trouble (wrong day/role above, a missing or
                # unreadable receipt) stops here.
                self.note_identity(e['day'], 'root', 'the retained ROOT %s policy differs from the plan\'s: %s; used as '
                                                    'it is' % (calc, mismatch))
            sources = [calc / 'calculations-receipt.json', calc / 'work' / 'derive.json']
            # session 6: a ROOT without the digest (a day with no digest reader) is listed, never a missing source
            digest_path = calc / 'work' / 'derivation-digest-full.md'
            if digest_path.is_file():
                sources.append(digest_path)
            if (calc / 'external-computation.json').is_file():
                sources.append(calc / 'external-computation.json')
            receipt_path = calc / 'calculations-receipt.json'
            receipt_sha = hashlib.sha256(retained_raw).hexdigest()   # hashed once, from the bytes parsed above (2026-10-09)
            brain_entry = self.brain_stage(e['day'], 'root', sources, known=receipt_pins(retained, receipt_path, receipt_sha),
                                           summary=dict(calculations=str(calc), role=e['role'],
                                                        root_status=retained.get('status'),
                                                        producer_failures=retained.get('failure_count'),
                                                        digest=('attached' if digest_path.is_file() else
                                                                self.DIGEST_NOT_BUILT)))
            all99 = self.all99(e['day'], calc, retained, policy, None)
            return self.record('root', e['day'], 'reused', calculations=str(calc), interrupted_attempts=attempts,
                               receipt_sha256=receipt_sha,
                               shared_market_policy=retained.get('shared_market_policy'), plan_policy=policy,
                               policy_recorded=mismatch, brain_entry=brain_entry, all99=all99,
                               # the one-day inspection: a reused ROOT received the retained receipt and produced the
                               # same all-99 list; operator review only
                               inspection=dict(inputs=dict(calculations=str(calc), receipt_sha256=receipt_sha),
                                               use=dict(reused=True, plan_policy=policy or 'none (an older saved legacy plan, kept as saved: native pass off; every NEW run has it ON)',
                                                        interrupted_attempts=attempts),
                                               outputs=dict(root_status=retained.get('status'), producer_failures=retained.get('failure_count'),
                                                            shared_market_policy=retained.get('shared_market_policy'),
                                                            all99=all99_summary(all99))))
        ing = self.receipt('ingest', e['day'])
        if not (ing and ing['status'] in FINISHED):
            return self.record('root', e['day'], 'waiting', reason='the day has no sealed ingest yet (stage ingest)')
        ready, why = self.external_ready(e)
        if not ready:
            return self.record('root', e['day'], 'waiting', reason=why)
        # First dispatch and resume both use the central claim's exact directory.
        resume = owned_output is not None and owned_output.is_dir()
        if not self.disk_ok('root', resume=resume):
            return None
        output = owned_output or ROOTS / ('%s-%s-a%d' % (self.plan['run'], e['day'], len(attempts) + 1))
        held = self.claim_root(e, output)          # None = no claim store on the box: exactly as before
        if held is not None and not held[0]:
            return self.record('root', e['day'], 'waiting', reason=held[1], claim=held[2])
        # session 6 (Greg, 2026-10-08: "some of these end steps feel redundant"; a2's digest decoding the 496.7 GB frames
        # spool five times): ROOT process 4, the Markdown digest, is a RUN SETTING (root_digest_setting: FRANKIE_ROOT_DIGEST
        # on|off at kick time wins, else on for a classroom-arm day or plan root_digest on, else off). It is read FOR WORK
        # by the classroom only (classroom.py / classroom_v2.py / classroom_staged.py / classroom_cache.py; the teacher,
        # search, data, reports, exchange and inspection stages read the JSON layers and spools); every other reader
        # records its hash. Off = derive.json root_processes.digest 'skipped' with its not_run reason, the receipt's
        # digest null, listed as not built on the brain entry and this record, never a failure.
        try:
            digest_setting = self.root_digest_setting(e, self.plan)
        except ValueError as error:
            return self.record('root', e['day'], 'refused', reason=str(error))
        env = dict(INGESTION_RECEIPT=ing['receipt'], INGESTION_RECEIPT_SHA256=ing['receipt_sha256'], DAY=e['day'],
                   DAY_ROLE=e['role'], OUTPUT_ROOT=output, DATA_WORKERS=self.day_cpus() - 1,
                   DIGEST=digest_setting['value'],
                   RESUME='on' if resume else 'off',
                   # the ROOT's own finalize preflight keeps this Run's floor (2026-10-08; Session._finalize_projection)
                   FRANKIE_ROOT_DISK_FLOOR_GB=self.floor / 1024 ** 3)
        if self.plan['frozen_survivors']:
            env['FROZEN_SURVIVORS'] = self.plan['frozen_survivors']
        if policy:
            env['SHARED_MARKET_POLICY'] = policy     # the wrapper forwards --bedrock on --shared-market-policy; the same
                                                    # saved plan reaches the Linux lane's job, so its ROOT runs under it too
        child_started = time.time()
        code, log = self.child('root', e['day'], 'frankie_box_experiment_root.sh', env)
        child_seconds = round(time.time() - child_started, 1)
        derive = load_derive(output)                 # derive.json parsed ONCE for this ROOT step (2026-10-09, one pass)
        saved = self.child_saved('root', e['day'], code, log, output_root=str(output), interrupted_attempts=attempts,
                                 seconds=child_seconds, native_pass=native_pass_facts(output, None, policy, child_seconds,
                                                                                      derive=derive),
                                 claim='kept: the attempt resumes under it (claim_root retakes this box\'s own claim when no '
                                       'ROOT of the day runs)' if held else 'no claim store')
        if saved:
            return saved
        refused = output / 'work' / 'resume-refused.json'
        if resume and code == RESUME_REFUSED_EXIT and refused.is_file():
            # session 9 (Greg, 17:2xZ: "stuff like that should never kill workflow"): the ROOT child refused the RESUME on
            # identity (frankie_box_experiment_root.ResumeRefused: exit 65 after writing work/resume-refused.json,
            # FRANKIE_ROOT_RESUME_REFUSED_V1). A visible 'refused' outcome naming what differs, never the generic 'no
            # calculations-receipt.json' failure; the attempt directory and every saved document are kept as they are,
            # and the queue retains the owned day as unknown for ACTION=resume after the cause is fixed
            try:
                body = json.loads(refused.read_bytes())
            except (OSError, ValueError) as error:
                body = dict(reason='the refusal record %s is unreadable (%s: %s)' % (refused, type(error).__name__, error))
            stale = isinstance(body.get('at'), (int, float)) and body['at'] < child_started
            self.claim_end(e, output, None, 'the box ROOT resume was refused on identity (exit %s): %s' % (code, body.get('reason')))
            return self.record('root', e['day'], 'refused', exit_code=code, log=log, output_root=str(output),
                               interrupted_attempts=attempts, seconds=child_seconds, resume=True,
                               resume_refused=dict(body, record=str(refused), stale_record=stale),
                               reason='its resume was refused on identity: %s%s (record %s); the attempt %s is kept, nothing '
                                      'deleted or rewritten; ACTION=resume after the cause is fixed' % (
                                          body.get('reason'), ' (document %s)' % body['document'] if body.get('document') else '',
                                          refused, output.name))
        if code != 0 or not (output / 'calculations-receipt.json').is_file():
            self.claim_end(e, output, None, 'the box ROOT attempt ended without calculations-receipt.json (exit %s)' % code)
            return self.record('root', e['day'], 'failed', exit_code=code, log=log, output_root=str(output),
                               interrupted_attempts=attempts, seconds=child_seconds, resume=resume,
                               native_pass=native_pass_facts(output, None, policy, child_seconds, derive=derive),
                               reason='no calculations-receipt.json (the attempt is kept)%s' % (
                                   '; the native pass was ON (policy %s): its failure, if it is the cause, is named in the '
                                   'log and native_pass; no bedrock-off retry is substituted' % policy if policy else ''))
        receipt_path = output / 'calculations-receipt.json'
        receipt_raw = receipt_path.read_bytes()      # read once: parsed here, its sha256 from the same bytes
        calc = json.loads(receipt_raw)
        receipt_sha = hashlib.sha256(receipt_raw).hexdigest()
        native = native_pass_facts(output, calc, policy, child_seconds, derive=derive)
        self.claim_end(e, output, receipt_sha, None)
        # the 99 layers combined for Frankie: per entry produced / admitted / absent (thinner picture, the day stays) /
        # knowledge / retired / sealed / disabled / output, on this receipt and in the one-day inspection (Greg, 2026-10-07)
        all99 = self.all99(e['day'], output, calc, policy, self.shared_policy_mismatch(calc.get('shared_market_policy')) if policy else None,
                           derive=derive)
        digest_path = output / 'work' / 'derivation-digest-full.md'      # session 6: absent on a day with no digest reader
        # 2026-10-09 (one pass): the receipt's own pins (derivation, digest, external computation) and its sha256 are
        # taken by claim; the brain stage reads none of them whole again
        brain_entry = self.brain_stage(e['day'], 'root',
                                       [receipt_path, output / 'work' / 'derive.json'] +
                                       ([digest_path] if digest_path.is_file() else []) +
                                       ([output / 'external-computation.json']
                                        if (output / 'external-computation.json').is_file() else []),
                                       known=receipt_pins(calc, receipt_path, receipt_sha),
                                       summary=dict(calculations=str(output), role=e['role'],
                                                    root_status=calc.get('status'),
                                                    producer_failures=calc.get('failure_count'),
                                                    digest=('attached' if digest_path.is_file() else
                                                            self.DIGEST_NOT_BUILT)))
        finalize = (derive[0] or {}).get('finalize_projection')
        measured = dict(calculations=str(output))
        return self.record('root', e['day'], 'done', exit_code=code, log=log, calculations=str(output),
                           receipt_sha256=receipt_sha, new_bytes=new_bytes(output),
                           # 2026-10-08: what the ROOT's finalize projected and wrote, and its inline spool-layer bytes
                           # (0 on reference layers), which the root disk gate does not reserve again
                           finalize_projection=finalize, inline_spool_layer_bytes=self.inline_spool_layer_bytes(measured),
                           # session 6: digest = whether the ROOT built it (was a constant True), with the rule
                           interrupted_attempts=attempts, digest=digest_path.is_file(), digest_setting=digest_setting,
                           plan_policy=policy, seconds=child_seconds,
                           native_pass=native, shared_market_policy=calc.get('shared_market_policy'),
                           root_status=calc.get('status'), producer_failures=calc.get('failure_count'),
                           brain_entry=brain_entry, owner_binding=self.owner, all99=all99,
                           disk=getattr(self, 'disk_facts', None),
                           # the one-day inspection (frankie_box_workflow_inspection.py): what the ROOT child received,
                           # how this caller used it, what it produced; operator review only, never knowledge or a gate
                           inspection=dict(inputs=dict(ingestion_receipt=dict(path=ing['receipt'], sha256=ing['receipt_sha256']),
                                                       env={k: str(v) for k, v in env.items()}, owned_attempt=self.owned_attempt,
                                                       digest_setting=digest_setting),
                                           use=dict(resume=resume, plan_policy=policy or 'none (an older saved legacy plan, kept as saved: native pass off; every NEW run has it ON)',
                                                    interrupted_attempts=attempts, claim=held[2] if held else 'no claim store'),
                                           outputs=dict(calculations=str(output), exit_code=code,
                                                        receipt_sha256=receipt_sha,
                                                        root_status=calc.get('status'), producer_failures=calc.get('failure_count'),
                                                        shared_market_policy=calc.get('shared_market_policy'),
                                                        native_pass=native, seconds=child_seconds,
                                                        all99=all99_summary(all99))))

    def all99(self, day, calc_dir, calc, policy, mismatch, derive=None):
        """The day's all-99 production/admission list (all99_admission), never raising out of the ROOT step: a failure
        to build the list is itself listed (schema, error) so the receipt shows it instead of a missing field."""
        try:
            return all99_admission(self.code_root, day, calc_dir, calc, policy, mismatch, self.receipt('ingest', day),
                                   self.plan.get('brain') or str(BRAIN), derive_doc=derive)
        except Exception as error:  # noqa: BLE001 - the list is operator-visible accounting; its failure is recorded, not hidden
            self.log('all99 %s: the list could not be built (%s: %s)' % (day, type(error).__name__, error))
            return dict(schema=ALL99_SCHEMA, day=day, listed=0, counts={}, entries=[],
                        error='%s: %s' % (type(error).__name__, error), rule='the list could not be built; nothing is inferred')

    # The shared ROOT claim (frankie_box_root_claims.py; SPEC-pod-day-runner.md): the Pods, the worker boxes and this
    # orchestrator run the ROOT of a day only after claiming it once. Opt-in: while /opt/frankie-box/work/root-claims does
    # not exist nothing is claimed or checked (the orchestrator behaves exactly as before).
    def claim_root(self, e, output):
        """None (no claim store), (True, None, claim) when this box took the claim, or (False, why, holder)."""
        import frankie_box_root_claims as claims
        if os.environ.get('FRANKIE_LANE_MAILBOX'):
            return True, None, {'where': os.environ['FRANKIE_LANE_OWNER']}
        if not claims.active():
            return None
        run, day, me = self.plan['run'], e['day'], claims.this_box()
        ok, doc = claims.claim(run, day, me, output.name, self.commit, by='frankie_box_experiment.py')
        if not ok and doc and doc.get('where') == me and not doc.get('done') and not claims.root_running(day):
            # this box's own claim from an orchestrator that stopped (no ROOT of the day runs here): moved aside, retaken
            claims.release(run, day, 'stale: held by this box and no ROOT of the day runs here', me, expect_where=me)
            ok, doc = claims.claim(run, day, me, output.name, self.commit, by='frankie_box_experiment.py')
        if ok:
            return True, None, doc
        return False, ('the day is claimed by %s since %s (attempt %s%s): its ROOT runs there and lands under %s; the next '
                       'start reuses it' % (doc.get('where'), doc.get('started_utc'), doc.get('attempt'),
                                            ', done' if doc.get('done') else '', ROOTS)), doc

    def claim_end(self, e, output, receipt_sha256, failure):
        import frankie_box_root_claims as claims
        if os.environ.get('FRANKIE_LANE_MAILBOX'):
            return  # central claim remains held through the entire remote day, including failures
        if not claims.active():
            return
        run, day, me = self.plan['run'], e['day'], claims.this_box()
        if failure is None:
            claims.done(run, day, me, output.name, output, receipt_sha256)
        else:
            claims.release(run, day, failure, me, expect_where=me, expect_attempt=output.name)

    # Frankie's historical data points: the day file beside the sealed ingest
    def ingest_dir(self, e):
        ing = self.receipt('ingest', e['day'])
        if ing and ing['status'] in FINISHED and ing.get('ingest'):
            return Path(ing['ingest'])
        receipt, _ = ingest_of(e, self.plan['run'])
        return receipt.parent if receipt else None

    def external_ready(self, e):
        """(True, None) when THIS run's external step has settled the day file (or EXTERNAL_WAIT=off), else (False, why).
        E-1 (fifth follow-up review): an attached file is not enough, since it may be older than the verified S3 file. The
        step receipt must be finished AND say which file: the verified S3 file swapped in (action s3) or confirmed equal
        (s3.same_as_attached), or S3 holds none (s3.status absent: the attached or rebuilt file stands), or this run's
        ROOT/teacher/classroom already used the attached file (the recorded s3_day_file_differs_after_use finding). And
        the attached file's sha256 must be the one the step recorded. 2026-10-09 (Greg: a gate we coded never blocks fine
        data): without such a settled step (a waiting step, an S3 state unknown for want of a presigned map, a receipt
        from before the S3 check), an attached day file that matches its receipt is used and "S3 not checked" recorded;
        only a day file actually missing (or differing from its receipt) waits."""
        if not self.plan.get('external_wait', True):
            return True, None
        day = e['day']
        step = self.receipt('external', day) or {}
        s3 = step.get('s3') if isinstance(step.get('s3'), dict) else {}
        settled = step.get('status') in FINISHED and (
            step.get('action') == 's3' or s3.get('same_as_attached') is True or s3.get('status') == 'absent'
            or any(isinstance(f, dict) and f.get('kind') == 's3_day_file_differs_after_use' for f in step.get('findings') or []))
        if day in self._attached:
            path, sha = self._attached[day]       # checked once per Run object (attached_day_file read it whole)
        else:
            directory = self.ingest_dir(e)
            if directory is None:
                return False, 'the day has no sealed ingest yet, so no day file beside it (stages ingest, external)'
            path, sha, why = attached_day_file(directory)
            if path is None:
                return False, 'the day file of the historical data points is not attached (stage external): %s' % why
        if settled and sha != step.get('sha256'):
            return False, ('the attached day file (sha256 %s) is not the one this run\'s external step settled (%s); the '
                           'external step runs again' % (sha, step.get('sha256')))
        if not settled:
            # 2026-10-09 (Greg: a gate we coded never blocks fine data): the attached day file matches its receipt, so
            # the day proceeds on it; that S3 was not checked is RECORDED on the day's steps, never a wait
            self.note_identity(day, 'external', 'S3 not checked: the attached day file %s (sha256 %s) matches its receipt '
                                                'and is used (external step %s, S3 %s)' % (
                                                    path, sha, step.get('status') or 'not run', s3.get('status') or 'not checked'))
        self._attached[day] = (str(path), sha)
        return True, None

    def url_map(self):
        """The dispatch's presigned map (MAP_URL), read once: (map, None) or (None, why)."""
        if self._map is None:
            url = os.environ.get('MAP_URL')
            if not url:
                self._map = (None, 'MAP_URL not set: dispatch with the presign string ACTION=plan prints (getprefix for '
                                   'the day history and the curve, put slots under frankie/day_external/<day>/)')
            else:
                import urllib.request
                try:
                    self._map = (json.loads(urllib.request.urlopen(url, timeout=60).read()), None)
                except Exception as error:          # an expired or unreadable map: listed, the step waits
                    self._map = (None, 'the presigned map could not be read (%s: %s)' % (type(error).__name__, error))
        return self._map

    @staticmethod
    def history_lacking(day, url_map, history_run, eia930_run=None, family_runs=None):
        """The keys a day file needs that the map does not hold: the history manifest(s), the day's EIA-930 files (from
        eia930_run when given, else history_run), the curve's definition/statistics/mbo of the day's two UTC partitions.
        Empty = the history is on S3 and presigned."""
        hp = 'frankie/day_history/%s' % history_run
        family_runs = dict(family_runs or {})
        ep = 'frankie/day_history/%s' % (family_runs.get('eia930') or eia930_run or history_run)
        date = dt.date(int(day[:4]), int(day[4:6]), int(day[6:8]))
        lack = []
        for prefix in dict.fromkeys((hp, ep) + tuple('frankie/day_history/%s' % r for r in sorted(family_runs.values()))):
            if prefix + '/manifest.json' not in url_map:
                lack.append(prefix + '/manifest.json')
        if not any(k.startswith('%s/eia930/%s/' % (ep, date.isoformat())) for k in url_map):
            lack.append('%s/eia930/%s/*' % (ep, date.isoformat()))
        for part in ((date - dt.timedelta(days=1)).strftime('%Y%m%d'), day):
            for schema in ('definition', 'statistics', 'mbo'):
                key = '%s/%s/native/glbx-mdp3-%s.%s.dbn.zst' % (CURVE_PREFIX, schema, part, schema)
                if key not in url_map:
                    lack.append(key)
        if family_runs.get('as_printed'):
            # a NAMED as_printed pull (the storage estimate and its captures, values only) must be presigned whole: its
            # files under <prefix>/as_printed/. Not named: the builder reads as_printed from the main run when it has
            # them and lists the point missing otherwise (missing-coverage rule; never a wait for it)
            ap = 'frankie/day_history/%s/as_printed/' % family_runs['as_printed']
            if not any(k.startswith(ap) for k in url_map):
                lack.append(ap + '*')
        return lack

    def external(self, e):
        day = e['day']
        ing = self.receipt('ingest', day)
        if not (ing and ing['status'] in FINISHED):
            return self.record('external', day, 'waiting', reason='the day has no sealed ingest yet (the day file is '
                                                                  'attached beside it)')
        directory = Path(ing['ingest'])
        # the verified S3 day file is preferred (2026-10-07 night: Frankie's 13 points are rebuilt and verified on S3);
        # a rebuild is the fallback only when S3 holds none; S3's state comes from the dispatch's presigned listing
        s3 = self.s3_day_file(day)
        if s3['status'] == 'integrity':
            return self.record('external', day, 'refused', reason='integrity: %s' % s3['reason'], s3=s3,
                               inspection=dict(inputs=dict(ingest=str(directory), s3=s3), use='refused: %s' % s3['reason'],
                                               outputs={}))
        if s3['status'] == 'present':
            return self.external_from_s3(day, directory, s3)
        path, sha, why = attached_day_file(directory)
        if s3['status'] == 'unknown' and path is None:
            # an unknown S3 state with NO usable attached file: the step waits with the reason, retried on a dispatch
            # whose presigned map carries the day's frankie/day_external/<day>/ listing (ACTION=plan's presign string).
            # 2026-10-09 (Greg): an attached file that matches its receipt proceeds below, "S3 not checked" recorded
            return self.record('external', day, 'waiting', s3=s3,
                               reason='the S3 state of the day file is unknown (%s) and no day file is attached (%s)' % (
                                   s3['reason'], why),
                               inspection=dict(inputs=dict(ingest=str(directory), s3=s3),
                                               use='waiting: S3 state unknown, no attached day file', outputs={}))
        if s3['status'] == 'unknown':
            s3 = dict(s3, not_checked=True, note='S3 not checked: the attached day file matches its receipt and is used')
        if path is not None:
            day_receipt = directory / DAY_FILE_RECEIPT
            brain_entry = self.brain_stage(day, 'day-file', [path, day_receipt],
                                           summary=dict(day_file=str(path), sha256=sha))
            self._attached[day] = (str(path), sha)    # external_ready reuses this check (one read per Run object)
            return self.record('external', day, 'reused', day_file=str(path), sha256=sha, ingest=str(directory),
                               brain_entry=brain_entry, s3=s3,
                               inspection=dict(inputs=dict(ingest=str(directory), s3=s3),
                                               use='reused: the day file is attached beside the sealed ingest (never '
                                                   'rebuilt or overwritten); S3 %s' % s3['status'],
                                               outputs=self.external_outputs(path, day_receipt)))
        if why.startswith('DIFFERS'):
            return self.record('external', day, 'refused', reason=why + ' (a day file is never overwritten; move it aside '
                                                                          'with a receipt first)',
                               inspection=dict(inputs=dict(ingest=str(directory)), use='refused: %s' % why,
                                               outputs={}))
        history = self.plan.get('external_history_run')
        if not history:
            return self.record('external', day, 'waiting', reason='no EXTERNAL_HISTORY_RUN given (the day_history run '
                                                                  'whose objects the day file is built from)')
        attempts = sorted(DAY_EXTERNAL.glob('%s-ext-%s-a*' % (self.plan['run'], day)))
        built = [a for a in attempts if (a / day / DAY_FILE).is_file()]
        env = dict(DAYS=day, HISTORY_RUN=history, BRAIN=self.plan.get('brain') or str(BRAIN), WORKERS=1)
        if self.plan.get('external_eia930_history_run'):
            env['EIA930_HISTORY_RUN'] = self.plan['external_eia930_history_run']
        if self.plan.get('external_family_history_runs'):
            env['HISTORY_FAMILY_RUNS'] = ','.join('%s=%s' % kv for kv in sorted(self.plan['external_family_history_runs'].items()))
        if built:
            env.update(ACTION='link', RUN=built[-1].name)          # an earlier build of this run: attach it, never rebuild
        else:
            url_map, why = self.url_map()
            if url_map is None:
                return self.record('external', day, 'waiting', reason=why)
            lacking = self.history_lacking(day, url_map, history, self.plan.get('external_eia930_history_run'),
                                           self.plan.get('external_family_history_runs'))
            if lacking:
                return self.record('external', day, 'waiting', lacking=lacking,
                                   inspection=dict(inputs=dict(ingest=str(directory), history_run=history,
                                                               keys_lacking=lacking),
                                                   use='waiting: the day\'s history is not all presigned', outputs={}),
                                   reason='the day\'s history is not on S3 yet or not presigned (%d keys lacking); the day '
                                          'waits, never skipped, and no day file is built without its pieces' % len(lacking))
            if not self.disk_ok('external'):
                return None
            env.update(ACTION='build', RUN='%s-ext-%s-a%d' % (self.plan['run'], day, len(attempts) + 1))
        code, log = self.child('external', day, 'frankie_box_day_external.sh', env)
        saved = self.child_saved('external', day, code, log, action=env['ACTION'], external_run=env['RUN'])
        if saved:
            return saved
        path, sha, why = attached_day_file(directory)
        history_inputs = dict(ingest=str(directory), history_run=history,
                              eia930_history_run=self.plan.get('external_eia930_history_run'),
                              family_history_runs=self.plan.get('external_family_history_runs'),
                              action=env['ACTION'], external_run=env['RUN'])
        if path is None:
            return self.record('external', day, 'failed', exit_code=code, log=log, action=env['ACTION'], external_run=env['RUN'],
                               reason='no day file attached beside the sealed ingest after the step: %s' % why,
                               inspection=dict(inputs=history_inputs, use='no day file attached: %s' % why,
                                               outputs=dict(exit_code=code)))
        self._attached[day] = (str(path), sha)
        day_receipt = directory / DAY_FILE_RECEIPT
        brain_entry = self.brain_stage(day, 'day-file', [path, day_receipt],
                                       summary=dict(day_file=str(path), sha256=sha))
        return self.record('external', day, 'done', exit_code=code, log=log, action=env['ACTION'], external_run=env['RUN'],
                           day_file=str(path), sha256=sha, ingest=str(directory),
                           new_bytes=new_bytes(DAY_EXTERNAL / env['RUN']) if env['ACTION'] == 'build' else 0,
                           upload_or_brain_exit_code=code, brain_entry=brain_entry, s3=s3,
                           inspection=dict(inputs=history_inputs,
                                           use=('built from the presigned day history (frankie_box_day_external.sh '
                                                'ACTION=build), then attached beside the sealed ingest'
                                                if env['ACTION'] == 'build' else
                                                'an earlier build of this run attached (ACTION=link; never rebuilt)'),
                                           outputs=self.external_outputs(path, day_receipt)))

    def s3_day_file(self, day):
        """What S3 holds of the day file pair frankie/day_external/<day>/ (never a URL on a receipt), from the dispatch's
        presigned map: the workflow lists the day prefix (getprefix) and presigns the two upload slots only when S3 holds
        neither object. status: present (both objects listed, with their bytes), absent (both upload slots presigned),
        integrity (one object without the other: never half replaced, never built over), unknown (no map, or a map
        without this day's listing: the attached / build route runs as before)."""
        url_map, why = self.url_map()
        keys = {name: 'frankie/day_external/%s/%s' % (day, name) for name in (DAY_FILE, DAY_FILE_RECEIPT)}
        if url_map is None:
            return dict(status='unknown', keys=list(keys.values()), reason=why)
        listed = {name: url_map[k] for name, k in keys.items() if isinstance(url_map.get(k), dict)}
        slots = [name for name, k in keys.items() if ('put:' + k) in url_map]
        out = dict(keys=list(keys.values()), listed={n: v.get('bytes') for n, v in listed.items()}, put_slots=slots)
        if len(listed) == 2:
            return dict(out, status='present', reason='S3 holds the day file and its receipt')
        if listed:
            return dict(out, status='integrity', reason='S3 holds only %s of the day pair %s' % (sorted(listed), sorted(keys)))
        if len(slots) == 2:
            return dict(out, status='absent', reason='S3 holds neither object of the day pair (both upload slots presigned)')
        return dict(out, status='unknown', reason='the presigned map carries no S3 listing for this day (a dispatch without '
                                                  'the frankie/day_external/<day>/ listing)')

    def external_from_s3(self, day, directory, s3):
        """The verified S3 day file attached beside the sealed ingest. The S3 receipt is fetched first; when the attached
        pair already is that file (same sha256) it is reused with nothing downloaded. Otherwise the file is fetched into
        its own directory under DAY_EXTERNAL, checked (bytes and sha256 against its receipt, the trading day, check_day_file)
        and attached: the attached pair moved aside (<name>.superseded-<utc>, never deleted) and the S3 pair hard-linked in;
        the day-file brain entry of the old file, if any, moved aside the same way (<day>-day-file.superseded-<utc>, outside
        the brain's entry globs) so the new one is filed. Never swapped once this run's ROOT, teacher or classroom of the
        day finished on the attached file (completed science is never changed under it): then the attached file stays and
        the differing S3 sha256 is a visible finding. A failed download waits (retried); a check failure is an integrity
        refusal; both shas are recorded."""
        import urllib.request
        url_map, _ = self.url_map()
        keys = {name: 'frankie/day_external/%s/%s' % (day, name) for name in (DAY_FILE, DAY_FILE_RECEIPT)}
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        stage_dir = DAY_EXTERNAL / ('%s-s3-%s-%s' % (self.plan['run'], day, stamp)) / day
        inputs = dict(ingest=str(directory), s3={k: v for k, v in s3.items() if k != 'reason'})

        def fetch(name):
            item = url_map[keys[name]]
            stage_dir.mkdir(parents=True, exist_ok=True)
            target = stage_dir / name
            pending = target.with_name(name + '.pending')
            if (item.get('bytes') or 0) > 2 * RANGE_BYTES:
                ranged_fetch(item['url'], pending, item['bytes'])      # the day file: concurrent byte ranges
            else:
                with urllib.request.urlopen(item['url'], timeout=900) as response, open(pending, 'wb') as out:
                    shutil.copyfileobj(response, out, 8 * 1024 * 1024)
            if pending.stat().st_size != item.get('bytes'):
                raise ValueError('%s: %d bytes fetched, S3 listed %s' % (keys[name], pending.stat().st_size, item.get('bytes')))
            os.replace(pending, target)
            return target
        try:
            receipt_path = fetch(DAY_FILE_RECEIPT)
            receipt = json.loads(receipt_path.read_bytes())
        except (OSError, ValueError) as error:
            return self.record('external', day, 'waiting', reason='the S3 day receipt could not be fetched (%s: %s); retried'
                               % (type(error).__name__, error), s3=inputs['s3'],
                               inspection=dict(inputs=inputs, use='waiting: S3 receipt fetch', outputs={}))
        s3_sha = receipt.get('sha256')
        try:
            attached, attached_sha, attached_why = attached_day_file(directory)
        except (ValueError, KeyError, TypeError) as error:    # a malformed attached file: replaced below, never read
            attached, attached_sha, attached_why = None, None, 'malformed: %s: %s' % (type(error).__name__, error)
        if attached is not None and attached_sha == s3_sha:
            day_receipt = directory / DAY_FILE_RECEIPT
            brain_entry = self.brain_stage(day, 'day-file', [attached, day_receipt],
                                           summary=dict(day_file=str(attached), sha256=attached_sha))
            self._attached[day] = (str(attached), attached_sha)
            return self.record('external', day, 'reused', day_file=str(attached), sha256=attached_sha, ingest=str(directory),
                               brain_entry=brain_entry, s3=dict(inputs['s3'], sha256=s3_sha, same_as_attached=True),
                               inspection=dict(inputs=inputs, use='reused: the attached day file IS the verified S3 file '
                                                                  '(same sha256; nothing downloaded beyond its receipt)',
                                               outputs=self.external_outputs(attached, day_receipt)))
        used = [stage for stage in ('root', 'teacher', 'classroom') if self.finished(stage, day)]
        if attached is not None and used:
            day_receipt = directory / DAY_FILE_RECEIPT
            finding = dict(kind='s3_day_file_differs_after_use', attached_sha256=attached_sha, s3_sha256=s3_sha,
                           used_by=used, reason='this run\'s %s already finished on the attached file; completed results are '
                                                'never changed under them: an explicit successor run takes the S3 file'
                                                % ', '.join(used))
            self.log('external %s: %s' % (day, finding['reason']))
            return self.record('external', day, 'reused', day_file=str(attached), sha256=attached_sha, ingest=str(directory),
                               s3=dict(inputs['s3'], sha256=s3_sha, same_as_attached=False), findings=[finding],
                               inspection=dict(inputs=inputs, use='kept the attached file: %s' % finding['reason'],
                                               outputs=dict(self.external_outputs(attached, day_receipt), findings=[finding])))
        try:
            file_path = fetch(DAY_FILE)
        except (OSError, ValueError) as error:
            return self.record('external', day, 'waiting', reason='the S3 day file could not be fetched (%s: %s); retried'
                               % (type(error).__name__, error), s3=dict(inputs['s3'], sha256=s3_sha),
                               inspection=dict(inputs=inputs, use='waiting: S3 day file fetch', outputs={}))
        try:
            have = sha256_file(file_path)
            if have != s3_sha or file_path.stat().st_size != receipt.get('bytes'):
                raise ValueError('S3 day file sha256 %s / %d bytes differ from its receipt (%s / %s)' % (
                    have, file_path.stat().st_size, s3_sha, receipt.get('bytes')))
            body = json.loads(file_path.read_bytes())
            ingest_day = json.loads((directory / 'ingestion-receipt.json').read_bytes()).get('trading_day') \
                if (directory / 'ingestion-receipt.json').is_file() else day
            if str(body.get('trading_day')) != str(day) or str(ingest_day) != str(day):
                raise ValueError('S3 day file trading day %s, ingest %s, step day %s' % (body.get('trading_day'), ingest_day, day))
            from research.kalshi.frankie_boss.operations.frankie_day_external import check_day_file
            check_day_file(body)
        except (OSError, ValueError, KeyError, TypeError) as error:
            return self.record('external', day, 'refused', reason='integrity: the S3 day file failed its checks: %s: %s'
                               % (type(error).__name__, error), s3=dict(inputs['s3'], sha256=s3_sha), staged=str(stage_dir),
                               inspection=dict(inputs=inputs, use='refused (integrity): kept staged at %s' % stage_dir,
                                               outputs={}))
        moved = []
        for name in (DAY_FILE, DAY_FILE_RECEIPT):
            old = directory / name
            if old.exists():
                aside = old.with_name('%s.superseded-%s' % (name, stamp))
                os.rename(old, aside)
                moved.append(dict(file=str(old), moved_to=str(aside)))
        for name in (DAY_FILE, DAY_FILE_RECEIPT):
            try:
                os.link(stage_dir / name, directory / name)
            except OSError:
                shutil.copy2(stage_dir / name, directory / name)
        path, sha, why = attached_day_file(directory)
        if path is None:
            return self.record('external', day, 'failed', reason='the S3 pair did not attach: %s' % why, moved_aside=moved,
                               s3=dict(inputs['s3'], sha256=s3_sha))
        self._attached[day] = (str(path), sha)
        for key in [k for k in self._day_file_sha if k and k[0] == day]:
            self._day_file_sha.pop(key, None)
        brain_moved = None
        try:
            brain_entry = self.brain_stage(day, 'day-file', [path, directory / DAY_FILE_RECEIPT],
                                           summary=dict(day_file=str(path), sha256=sha), declined='raise')
        except ValueError as error:
            # E-5: ONLY the brain's own refusal "already holds different stage knowledge" (frankie_box_brain.
            # write_stage_entry, R16) moves the replaced file's entry aside (never deleted; outside ENTRY_GLOBS) so the
            # verified file's entry is filed; any other error is the step's own, raised unchanged
            entry = Path(self.plan.get('brain') or str(BRAIN)) / ('%s-day-file' % day)
            if 'already holds different stage knowledge' not in str(error) or not entry.is_dir():
                raise
            brain_moved = dict(entry=str(entry), moved_to=str(entry) + '.superseded-%s' % stamp, why=str(error))
            os.rename(entry, brain_moved['moved_to'])
            brain_entry = self.brain_stage(day, 'day-file', [path, directory / DAY_FILE_RECEIPT],
                                           summary=dict(day_file=str(path), sha256=sha))
        return self.record('external', day, 'done', action='s3', day_file=str(path), sha256=sha, ingest=str(directory),
                           previous=dict(sha256=attached_sha, why=attached_why, moved_aside=moved),
                           s3=dict(inputs['s3'], sha256=s3_sha, staged=str(stage_dir)), brain_entry=brain_entry,
                           brain_moved_aside=brain_moved, new_bytes=new_bytes(stage_dir.parent),
                           inspection=dict(inputs=inputs,
                                           use='the verified S3 day file attached (receipt sha256 and bytes, trading day and '
                                               'check_day_file checked); the previous pair moved aside, never deleted',
                                           outputs=dict(self.external_outputs(path, directory / DAY_FILE_RECEIPT),
                                                        previous_sha256=attached_sha, moved_aside=moved,
                                                        brain_moved_aside=brain_moved)))

    @staticmethod
    def external_outputs(path, day_receipt):
        """The attached day file and its receipt pinned, plus the file's stamp shape and per-point mapping as recorded in
        it (the 13 points: rows, 99 entry, mapping, event-time basis); missing/stale dispositions are the file's own."""
        out = dict(day_file=pin_or_listed(path), day_receipt=pin_or_listed(day_receipt))
        try:
            body = json.loads(Path(path).read_bytes())
            points = body.get('points') or {}
            out['points'] = {name: dict(rows=len(t.get('rows') or []), stamp_column=t.get('stamp_column'),
                                        registry_entries=t.get('registry_entries') or t.get('registry_entry'),
                                        mapping=t.get('registry_mapping') or t.get('mapping'),
                                        event_time_basis=t.get('event_time_basis'),
                                        has_event_time='event_time_ns' in (t.get('columns') or ()))
                             for name, t in sorted(points.items()) if isinstance(t, dict)}
            out['missing'] = body.get('missing')
        except (OSError, ValueError) as error:
            out['points_unavailable'] = '%s: %s' % (type(error).__name__, error)
        return out

    # the classroom arm (V2: the 19/171 classroom plus the external section) and Jev's material
    def previous_of(self, e):
        """(PREVIOUS classroom directory or None, why it waits or None, where it came from). The class line pins the
        selection in its entry; outside the line the selection is PERSISTED in the day's continuation
        (days/<day>/previous.json, create-only) the first time it is made, explicit none included, so a retry after a
        save or a failure carries the same PREVIOUS and never repicks a newer classroom."""
        if self.queue_previous is not None:        # the class worker: class k carries class k-1 of the class line
            return self.queue_previous
        kept = self.previous_kept(e['day'])
        if kept is not None:
            return kept['classroom'], None, kept['from'] + ' (kept from %s)' % kept['selected_utc']
        selection = None
        if e.get('previous_classroom'):
            selection = e['previous_classroom'], None, 'plan (the day)'
        else:
            arm_days = [x for x in self.plan['days'] if x['classroom_arm']]
            i = [x['day'] for x in arm_days].index(e['day'])
            if i > 0:
                prev = arm_days[i - 1]['day']
                r = self.receipt('classroom', prev)
                if not (r and r['status'] in ('done', 'reused') and r.get('classroom')):
                    return None, 'the previous arm day %s has no complete classroom yet (its history is carried in)' % prev, None
                selection = r['classroom'], None, 'the previous arm day of this run (%s)' % prev
            elif self.plan.get('previous_classroom'):
                selection = self.plan['previous_classroom'], None, 'plan (PREVIOUS_CLASSROOM)'
            else:
                found, found_day = latest_completed_classroom(e['day'])
                if found is None:
                    selection = None, None, 'none: no other complete classroom on the box (history starts here)'
                else:
                    selection = str(found), None, ('the most recently completed classroom on the box (%s; trading-date order '
                                                   'ignored)' % found_day)
        self.previous_keep(e['day'], selection)
        return selection

    def previous_path(self, day):
        return self.dir / 'days' / day / 'previous.json'

    def previous_kept(self, day):
        path = self.previous_path(day)
        if not path.is_file():
            return None
        kept = json.loads(path.read_bytes())
        if kept.get('schema') != 'FRANKIE_PREVIOUS_SELECTION_V1' or kept.get('day') != day or kept.get('run') != self.plan['run']:
            raise ValueError('%s is not this run/day\'s previous-classroom selection' % path)
        return kept

    def previous_keep(self, day, selection):
        """The selection written once (create-only) BEFORE the first child dispatch; a selection kept meanwhile wins."""
        body = dict(schema='FRANKIE_PREVIOUS_SELECTION_V1', run=self.plan['run'], day=day, classroom=selection[0],
                    **{'from': selection[2]}, selected_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    selected_by_commit=self.commit)
        try:
            self.cores.write_json(self.previous_path(day), body, exclusive=True)
        except FileExistsError:
            return

    def classroom_ready(self, e):
        """The classroom step's readiness checks, in its order: (None, None, facts) when the day may take its class now;
        ('reused', None, facts) when its classroom is complete already; else (status, reason, facts). facts carry calc,
        the classroom directory d and the teacher rows once known. Used by the step and by the class line's enqueue."""
        root = self.root_on_disk(e)                  # session 9: the ROOT on disk, never a stale step record
        if root and root.get('status') == 'refused' and 'retained_policy' in root:
            return 'refused', 'refused: the day\'s ROOT is refused under the plan\'s shared market policy: %s' % root.get('reason'), {}
        if not (root and root['status'] in FINISHED and root.get('calculations')):
            return 'waiting', 'the day has no ROOT yet (stage root)', {}
        calc = Path(root['calculations'])
        facts = dict(calc=calc, d=calc / 'work' / 'classroom')
        if root.get('remote_calculations'):
            classroom = self.receipt('classroom', e['day'])
            if classroom and classroom.get('remote_owner') == root['owner'] and done_status(classroom):
                return 'reused', None, facts
            return 'waiting', 'classroom remains on the owning AWS lane ' + root['owner'], facts
        receipt = facts['d'] / 'receipt.json'
        if receipt.is_file():
            saved = json.loads(receipt.read_bytes())
            complete_files = ('completion.json', 'history.json', 'post-grade.json',
                              'external-history.json', 'external-post-grade.json')
            if saved.get('status') == 'complete' and saved.get('day') == e['day'] and \
                    all((facts['d'] / name).is_file() for name in complete_files) and \
                    (Path(saved.get('brain_entry') or '') / 'MANIFEST.json').is_file():
                import frankie_box_lane_state as LS
                import frankie_box_experiment_review as REVIEW
                selected_path = facts['d'] / 'learner-knowledge.json'
                try:
                    if sha256_file(selected_path) != (saved.get('stage_knowledge') or {}).get('sha256'):
                        raise ValueError('completed classroom learner selection differs from its receipt')
                    selected = json.loads(selected_path.read_bytes())
                    REVIEW.require_current(
                        list(selected['documents']) + [dict(row, content=doc)
                                                      for row, doc in selected['school_documents']],
                        REVIEW.corrections(LS.knowledge_roots(self.plan.get('brain') or BRAIN)))
                except (OSError, ValueError, KeyError, TypeError) as error:
                    return 'refused', ('completed classroom preserved; checked successor required before reuse: '
                                       + str(error)), facts
                return 'reused', None, facts
        if not (calc / 'work' / DIGEST_FILE).is_file():
            # session 6: a ROOT run with the digest off (FRANKIE_ROOT_DIGEST / root_digest_setting) is a visible WAIT with
            # the way to put it right, re-evaluated every pass, never a silent failure of the day: the digest is rendered
            # later from the retained layers (frankie_box_render_digest.sh on this experiment root, every row whole)
            # session 9: inside the day's own booking (beside the teacher; the ROOT receipt is kept, the render's record
            # is work/digest-render.json); without FRANKIE_RENDER_BOOKING it takes only CPUs outside every booking
            # 2026-10-09: the reason names the digest file itself, so a parked wait watches <calc>/work (queue wait_of)
            return 'waiting', ('the ROOT %s has no derivation digest %s (its ROOT ran with the digest off); render it from the '
                               'retained layers, then the class line takes the day: MARKETS_SHA=<staged commit> '
                               'CODE_ROOT=<staged checkout> OUTPUT_ROOT=%s FRANKIE_RENDER_BOOKING=<the day\'s booking id '
                               '(live or retained; frankie_box_cores.py show)> bash deploy/aws/box/frankie_box_render_digest.sh'
                               % (calc, calc / 'work' / DIGEST_FILE, calc)), facts
        rows, source, why = self.day_rows(e)
        if rows is None and why and why.startswith('refused'):
            return 'refused', why, facts          # a legacy teacher result under the plan's shared policy (preserved)
        if rows is None or not str(rows).startswith(str(TEACHER_ROWS) + '/'):
            return 'waiting', why or 'no teacher-only Dipole rows under %s yet (stage teacher; found: %s)' % (
                TEACHER_ROWS, source), facts
        facts['rows'] = rows
        ready, why = self.external_ready(e)
        if not ready:
            return 'waiting', why, facts
        return None, None, facts

    def classroom(self, e):
        day = e['day']
        remote = self.remote_stage('classroom', day)
        if remote is not None:
            return remote
        if not e['classroom_arm']:
            return self.record('classroom', day, 'skipped', reason='not a classroom-arm day')
        status, why, facts = self.classroom_ready(e)
        d = facts.get('d')
        if status == 'reused':
            r = json.loads((d / 'receipt.json').read_bytes()) if (d / 'receipt.json').is_file() else {}
            return self.record('classroom', day, 'reused', classroom=str(d), receipt_schema=r.get('schema'),
                               receipt_status=r.get('status'))
        if status:
            return self.record('classroom', day, status, reason=why)
        calc, rows = facts['calc'], facts['rows']
        previous, why, previous_from = self.previous_of(e)
        if why:
            return self.record('classroom', day, 'waiting', reason=why)
        if previous and not (Path(previous) / 'completion.json').is_file():
            return self.record('classroom', day, 'waiting', reason='PREVIOUS %s holds no completion.json' % previous)
        # The BOSS teacher's measured knowledge must be in the brain BEFORE Frankie's classroom reads it, whichever path
        # brought the day here (a fresh teacher run, rows reused from an earlier run, or a ROOT found elsewhere that
        # entered the class line without a teacher call). Idempotent: an identical entry is reused, not rewritten.
        rows_path, why = self.rows_file(e)
        if rows_path is None:
            return self.record('classroom', day, 'waiting', reason=why)
        try:
            teacher_brain = self.teacher_knowledge(day, rows_path, self.day_rows(e)[1])
        except (ValueError, FileNotFoundError) as error:
            return self.record('classroom', day, 'refused', teacher_rows=str(rows_path),
                               reason='the teacher knowledge of the day could not be published before the classroom: %s'
                                      % error)
        if not self.disk_ok('classroom'):
            return None
        env = dict(DAY=day, CALCULATIONS=calc, TEACHER_ROWS=rows, BRAIN=self.plan.get('brain') or str(BRAIN))
        if previous:
            env['PREVIOUS'] = previous
        # the plan's native-entry cutoff, only when the plan carries it (else unset: the classroom's defaults apply)
        env.update({var: self.plan[key] for key, var in NATIVE_CUTOFF_ENV.items() if self.plan.get(key) is not None})
        lane_plan, lane_why = self.classroom_lane(day, d)   # session 8: the resolver + grow (all 64) before the child
        if lane_plan is None:
            return self.record('classroom', day, lane_why[0], reason=lane_why[1])
        import frankie_box_frankie_queue as Q
        with Q.class_running(self.log):              # exactly one class at a time on the box, queue or not
            code, log = self.child('classroom', day, 'frankie_box_experiment_classroom_v2.sh', env)
        r = json.loads((d / 'receipt.json').read_bytes()) if (d / 'receipt.json').is_file() else {}
        # Delivery witness: the classroom's own learner-knowledge.json names every document its learner inputs read; the
        # teacher entry counts as delivered only when that list carries its stage-knowledge.json sha256 (a receipt or a
        # rows file alone proves nothing).
        delivered, delivery_status, read = None, 'no_learner_receipt', d / 'learner-knowledge.json'
        if read.is_file():
            learner_read = json.loads(read.read_bytes())
            documents = learner_read.get('documents') or []
            delivered = any(doc.get('sha256') == teacher_brain['knowledge_sha256'] for doc in documents)
            withheld = any(x.get('label') == day + '-teacher' and
                           x.get('reason') == 'current-day teacher measurements contain answers withheld by this classroom mode'
                           for x in learner_read.get('listed') or [])
            delivery_status = 'delivered' if delivered else 'withheld_by_classroom_mode' if withheld else 'not_delivered'
            if not delivered and not withheld:
                self.log('classroom %s: the teacher entry %s is NOT among the %d learner documents read' % (
                    day, teacher_brain['path'], len(documents)))
        fields = dict(exit_code=code, log=log, classroom=str(d), previous=previous, previous_from=previous_from,
                      school_day=self.school_day,
                      receipt_status=r.get('status'), external=(r.get('external') or {}).get('completion_hash'),
                      brain_entry=r.get('brain_entry'), jev_material=r.get('jev_material'),
                      teacher_brain_entry=teacher_brain, teacher_knowledge_delivered=delivered,
                      teacher_knowledge_delivery_status=delivery_status)
        if code == 0 and self.classroom_ready(e)[0] == 'reused':
            return self.record('classroom', day, 'done', new_bytes=new_bytes(d), **fields)
        saved = self.child_saved('classroom', day, code, **{k: v for k, v in fields.items() if k != 'exit_code'})
        if saved:
            return saved
        if code == 3 and r.get('status') == 'refused':
            return self.record('classroom', day, 'refused', reason=r.get('reason'), **fields)
        return self.record('classroom', day, 'failed', reason='no completion.json after the step (its log names why)', **fields)

    # Frankie's FIFO queue (frankie_box_frankie_queue.py): the ROOT line and the CLASS line, arrival order
    def queue_owned(self, e):
        """True when the class line runs this arm day's class side (classroom, frankie_lessons, exchange, voice, school,
        reports), not this orchestrator: the queue is on and the day is in the line, or its classroom is not finished
        yet (it enters the line once ready; nothing class-side runs here before it). A day whose classroom finished
        before the line existed keeps its class side here, as before."""
        if not (getattr(self.a, 'frankie_queue', 'off') == 'on' and e['classroom_arm']):
            return False
        import frankie_box_frankie_queue as Q
        return Q.entry_of('class', self.plan['run'], e['day']) is not None or not self.finished('classroom', e['day'])

    def enqueue_classroom(self, e):
        """The class line's door: the classroom step's own readiness checks, then the day's entry (arrival order). The
        classroom receipt says queued with the entry's seq; the worker's classroom step replaces it."""
        import frankie_box_frankie_queue as Q
        day = e['day']
        if not e['classroom_arm']:
            return self.record('classroom', day, 'skipped', reason='not a classroom-arm day')
        prior = self.receipt('classroom', day)
        if self.finished('classroom', day) or (prior and prior['status'] != 'waiting' and
                                               Q.entry_of('class', self.plan['run'], day) is not None):
            return prior                             # in the line already (or its class is done): never recorded twice
        status, why, facts = self.classroom_ready(e)
        if status == 'waiting' and facts.get('calc') and not (Path(facts['calc']) / 'work' / DIGEST_FILE).is_file():
            # 2026-10-09 (Greg: the classroom reads Frankie's full-depth digest; a pause at the classroom boundary is fine,
            # proceeding without the digest is not): the owner waits HERE, in the day's held slot, for the digest (the
            # render beside the teacher, or one started now inside the same booking), event-driven, then re-checks
            rendered = self.await_digest(e, Path(facts['calc']))
            if rendered is not None:
                self.log('classroom %s: digest wait ended: %s' % (day, json.dumps(rendered, default=str, sort_keys=True)[:600]))
                status, why, facts = self.classroom_ready(e)
                if status == 'waiting' and rendered.get('reason'):
                    why = '%s; %s' % (why, rendered['reason'])
        if status == 'reused' and Q.entry_of('class', self.plan['run'], day) is None:
            return self.classroom(e)                 # complete before the line existed: recorded reused, as before
        if status == 'waiting':
            return self.record('classroom', day, status, reason='%s (the class line takes the day once it is ready)' % why)
        if status == 'refused' and str(why).startswith('refused'):
            # the plan's shared market policy refuses the day's ROOT or teacher rows (day_rows / a refused ROOT): recorded
            # here, NOT enqueued (the line would stop at a day no run of this code can put right); the reason names
            # what puts it right
            return self.record('classroom', day, 'refused', reason=why)
        # a refused day (a ROOT without the digest) enters the line too: never skipped, its class step refuses there with
        # the reason, its reports print it, and the line stops at it until the day is put right
        entry, outcome = Q.enqueue('class', self.plan['run'], day, self.commit, self.code_root, plan_digest(self.plan),
                                   Q.settings_of(self.a), dict(calculations=str(facts['calc']), classroom=str(facts['d']),
                                                               teacher_rows=str(facts.get('rows')), refused=why,
                                                               day_file=list(self._attached.get(day) or []) or None),
                                   by='frankie_box_experiment.py %s' % self.plan['run'])
        if entry is None:
            return self.record('classroom', day, 'refused', reason=outcome)
        return self.record('classroom', day, 'queued', queue_seq=entry['seq'], queue_state=entry['state'],
                           queue=str(Q.QUEUE), enqueued_utc=entry['enqueued_utc'],
                           reason='in Frankie\'s class line at seq %d (%s, %s): the class worker runs its class side in '
                                  'arrival order, one class at a time' % (entry['seq'], outcome, entry['state']))

    @staticmethod
    def digest_render_pids(calc):
        """The live digest renders of this experiment root (frankie_box_render_digest.py --output-root <calc>), by /proc."""
        want, out = str(Path(calc).resolve()), []
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                argv = [a.decode('utf-8', 'replace') for a in (proc / 'cmdline').read_bytes().split(b'\0')]
            except OSError:
                continue
            if not any(a.endswith('frankie_box_render_digest.py') for a in argv) or '--output-root' not in argv:
                continue
            i = argv.index('--output-root')
            if i + 1 < len(argv) and str(Path(argv[i + 1]).resolve()) == want:
                out.append(int(proc.name))
        return out

    def await_digest(self, e, calc):
        """The class door's digest wait (2026-10-09): only for a Run that holds the day's booking (the owner in its slot).
        While <calc>/work/derivation-digest-full.md is absent: a running render of this root is waited on (its pidfd, the
        work directory's inotify, the queue's wake directory and the day's save marker: no interval); with none running,
        ONE render is started inside the day's own booking (frankie_box_render_digest.sh FRANKIE_RENDER_BOOKING=<slot>,
        detached, its log under <run>/logs) and waited on the same way. A save request stops the wait (SystemExit 75 by
        check_save; a running render keeps running and is found again by the resume). Returns None when the Run holds no
        booking or the digest is there, else what happened (a render that ended without the digest is named, the class
        door then records its wait with that reason)."""
        digest = Path(calc) / 'work' / DIGEST_FILE
        booking = getattr(self, 'slot_booking', None)
        if digest.is_file() or not booking:
            return None
        import frankie_box_frankie_queue as Q
        import frankie_box_wake as W
        dirs = [Q.wake_dir(), Path(calc) / 'work']
        if self.stop_marker:
            dirs.append(Path(self.stop_marker).parent)
        for d in dirs:
            try:
                Path(d).mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        waiter = W.Waiter(dirs)
        started, out, clock = None, dict(day=e['day'], calc=str(calc), booking=booking), time.monotonic()
        try:
            while True:
                self.check_save()
                pids = self.digest_render_pids(calc)
                if digest.is_file() and not pids:
                    break                # published (one rename) and its render has written its claim row and record
                if started is not None and started.poll() is not None and not pids:
                    log_path = out.get('log')
                    out.update(status='render_ended_without_digest', exit_code=started.returncode,
                               reason='the digest render started at the class door ended (exit %s) without %s; its log: %s'
                                      % (started.returncode, digest, log_path))
                    return out
                if not pids and started is None and not digest.is_file():
                    logs = self.dir / 'logs'
                    logs.mkdir(parents=True, exist_ok=True)
                    log_path = logs / ('%s-digest-render.log' % e['day'])
                    env = dict(os.environ, MARKETS_SHA=self.commit, CODE_ROOT=str(self.code_root), OUTPUT_ROOT=str(calc),
                               FRANKIE_RENDER_BOOKING=str(booking))
                    with open(log_path, 'ab') as handle:
                        handle.write(('\n### digest render %s at %s (class door, inside booking %s)\n' % (
                            calc, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), booking)).encode())
                        handle.flush()
                        started = subprocess.Popen(['bash', str(self.box / 'frankie_box_render_digest.sh')], env=env,
                                                   stdout=handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                                   start_new_session=True)
                    out.update(started_pid=started.pid, log=str(log_path), started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
                    self.log('classroom %s: no digest under %s and no render running: render started inside booking %s '
                             '(pid %d, log %s); the class door waits on it' % (e['day'], calc, booking, started.pid, log_path))
                    pids = [started.pid]
                elif pids and 'waited_on' not in out:
                    out['waited_on'] = pids
                    self.log('classroom %s: the digest render of %s runs (pid %s); the class door waits on it' % (
                        e['day'], calc, ','.join(map(str, pids))))
                for pid in pids + ([started.pid] if started is not None and started.poll() is None else []):
                    waiter.watch_pid(pid)
                waiter.wait()
            out.update(status='digest_present', seconds=round(time.monotonic() - clock, 1))
            return out
        finally:
            waiter.close()
            if started is not None:
                started.poll()

    def root_enqueue(self, e):
        """The ROOT line's door: the root step's own readiness checks (a finished ROOT is recorded reused as before; the
        sealed ingest; the day file attached), then the day's entry (arrival order). The root receipt says queued."""
        import frankie_box_frankie_queue as Q
        day = e['day']
        prior = self.receipt('root', day)
        if self.finished('root', day) or (prior and prior['status'] == 'queued' and
                                          Q.entry_of('root', self.plan['run'], day) is not None):
            return prior                             # finished (its measured bytes kept) or in the line already
        calc, attempts = root_of(e, self.plan['run'])
        if calc:
            return self.root(e)                      # a refused ROOT: root() re-evaluates and returns the prior refusal
        ing = self.receipt('ingest', day)
        if not (ing and ing['status'] in FINISHED):
            return self.record('root', day, 'waiting', reason='the day has no sealed ingest yet (stage ingest); it enters '
                                                              'the ROOT line once it has one and its day file')
        ready, why = self.external_ready(e)
        if not ready:
            return self.record('root', day, 'waiting', reason='%s (it enters the ROOT line once ready)' % why)
        entry, outcome = Q.enqueue('root', self.plan['run'], day, self.commit, self.code_root, plan_digest(self.plan),
                                   Q.settings_of(self.a), dict(ingest=ing.get('ingest'), receipt=ing.get('receipt'),
                                                               receipt_sha256=ing.get('receipt_sha256'),
                                                               day_file=list(self._attached.get(day) or []) or None,
                                                               interrupted_attempts=attempts),
                                   by='frankie_box_experiment.py %s' % self.plan['run'])
        if entry is None:
            return self.record('root', day, 'refused', reason=outcome)
        if entry['state'] == 'done':
            return self.root(e)
        return self.record('root', day, 'queued', queue_seq=entry['seq'], queue_state=entry['state'], queue=str(Q.QUEUE),
                           enqueued_utc=entry['enqueued_utc'],
                           reason='in the ROOT line at seq %d (%s, %s): it runs in arrival order in the next free day-run '
                                  'slot (box or Pod)' % (entry['seq'], outcome, entry['state']))

    def scope_text(self):
        """The authorized scope of this run: its saved plan's days, exactly (a one-day plan is a one-day scope)."""
        return '%s:%s' % (self.plan['run'], ','.join(e['day'] for e in self.plan['days']))

    def kick(self, line):
        self.check_save()
        import frankie_box_frankie_queue as Q
        try:
            return Q.kick(line, self.code_root, self.commit, self.a.queue_worker_seconds, self.a.queue_poll_seconds,
                          by='frankie_box_experiment.py %s' % self.plan['run'], log=self.log, scope=self.scope_text())
        except (Exception, SystemExit) as error:     # listed (a scope refusal included); the next start kicks again
            self.log('the %s worker could not be kicked (%s: %s)' % (line, type(error).__name__, error))
            return None

    def await_roots(self, days):
        """This run's ROOT-line days: wait (event-driven, bounded only by --queue-worker-seconds, the orchestrator's own
        lifetime) until each has left the line done or failed, re-kicking the ROOT worker when none runs; each day's root
        receipt is then the worker's. A day still in the line at the bound stays queued (listed); the next start waits
        again. 2026-10-09: no poll interval; it wakes on any state change (the queue's wake directory)."""
        import frankie_box_frankie_queue as Q
        import frankie_box_wake as W
        limit = int(self.a.queue_worker_seconds or 0)      # 0 = no limit (the default, 2026-10-09)
        deadline = time.monotonic() + limit if limit else None
        waiter = W.Waiter([Q.wake_dir()])
        kicked_for = None
        while True:
            self.check_save()
            left = []
            for e in days:
                x = Q.entry_of('root', self.plan['run'], e['day'])
                if x is None:
                    continue
                if x['state'] == 'done' and (self.receipt('root', e['day']) or {}).get('status') not in FINISHED:
                    self.root(e)                     # finished elsewhere (a Pod): recorded reused here
                if x['state'] in ('queued', 'running'):
                    left.append('%s seq %d %s%s' % (e['day'], x['seq'], x['state'],
                                                     (' at %s' % x['where']) if x.get('where') else ''))
            if not left:
                waiter.close()
                return
            self.probe.update('root line: waiting on %d day(s)' % len(left), 0, None)
            status, held = Q.worker_state('root')
            if not held and kicked_for != left:
                # one kick per distinct line state: a worker that ends with nothing changed (an owner's resume pending)
                # is not re-kicked on its own end-of-worker wake; the next real change kicks again
                self.check_save()
                self.kick('root')
                kicked_for = list(left)
            remaining = None if deadline is None else deadline - time.monotonic()
            if (remaining is not None and remaining <= 0) or not waiter.wait(remaining):
                self.log('root line: %d day(s) still in the line at the bound (%s); they stay queued' % (len(left), left))
                waiter.close()
                return

    # the day reports (Greg, 2026-09-29: "make sure classroom is printing out an analysis after every day has gone through
    # it, and same with Frankie, and have them number their reports")
    @staticmethod
    def reports_receipt(log, day=None, run=None):
        """The day reports step's receipt: the file the step writes at <reports-dir>/receipts/<run>/<day>.json (its
        fields school, school_sha256, school_status, school_listed among them; correction_consumer, 2026-10-07) when
        given a day and run, else the last line of its log, or None."""
        if day and run:
            try:
                r = json.loads((REPORTS / 'receipts' / run / ('%s.json' % day)).read_bytes())
                if isinstance(r, dict) and r.get('schema') == REPORTS_SCHEMA and str(r.get('day')) == str(day):
                    return r
            except (OSError, ValueError):
                pass
        if log is None:
            return None
        try:
            lines = [x for x in Path(log).read_text(encoding='utf-8', errors='replace').splitlines() if x.strip()]
            r = json.loads(lines[-1]) if lines else None
        except (OSError, ValueError):
            return None
        return r if isinstance(r, dict) and r.get('schema') == REPORTS_SCHEMA else None

    def reports(self, e):
        """CLASSROOM REPORT #N and FRANKIE REPORT #N of an arm day, once its classroom step is done, reused or refused
        (a refused day is reported too, with the reason), after the day's exchange stage: the exchange is carried when it
        is done, otherwise its status is listed in both reports, and they are rebuilt (a revision, same N) once the
        exchange is there (reports_stale). Printed here in full. A failure is recorded (retried on the next start) and
        never stops the run; no disk-floor check (the reports are a few kilobytes)."""
        day = e['day']
        try:
            if not e['classroom_arm']:
                return self.record('reports', day, 'skipped', reason='not a classroom-arm day (no classroom ran, so no '
                                                                     'classroom or Frankie report)')
            c = self.receipt('classroom', day)
            if not (c and c['status'] in ('done', 'reused', 'refused')):
                return self.record('reports', day, 'waiting', reason='the day\'s classroom step is %s (the reports follow '
                                   'a done, reused or refused classroom)' % ((c or {}).get('status') or 'not run'))
            env, why = self.reports_invocation(day, c, e.get('cls'))
            if env is None:
                return self.record('reports', day, 'failed', reason=why)
            classroom, x = env['CLASSROOM'], self.receipt('exchange', day)
            code, log = self.child('reports', day, 'frankie_box_experiment_day_reports.sh', env)
            r = self.reports_receipt(log, day=day, run=self.plan['run'])
            # reports X4 (stacks pass 2026-10-07): the child's log already holds both reports in full (it prints them);
            # they are not read back here. Each report is named once from the step's receipt with its sha256
            for item in (r or {}).get('reports') or []:
                self.log('reports %s: %s #%s%s %s sha256 %s%s' % (
                    day, item.get('kind'), item.get('number'), ('.%s' % item['revision']) if item.get('revision') else '',
                    item.get('file'), item.get('sha256'), ' (existing)' if item.get('existing') else ''))
            school = self.receipt('school', day) or {}
            fields = dict(exit_code=code, log=log, classroom=classroom, classroom_status=c['status'],
                          exchange_status=(x or {}).get('status'), exchange=env.get('EXCHANGE'),
                          meeting=(r or {}).get('meeting'),
                          school=dict(status=school.get('status'), file=school.get('file'),
                                      sha256=school.get('school_sha256') or (school.get('row') or {}).get('sha256')),
                          report_number=(r or {}).get('report_number'),
                          reports=[{k: item.get(k) for k in ('kind', 'number', 'revision', 'file', 'sha256', 'existing')}
                                   for item in (r or {}).get('reports') or []],
                          problems=(r or {}).get('problems'),
                          # the one-day inspection (frankie_box_workflow_inspection.py): what the report step received,
                          # what the reports carry (and do not), what it produced; operator review only, never a gate
                          inspection=dict(inputs=dict(env={k: str(v) for k, v in env.items()},
                                                      classroom=dict(path=classroom, status=c['status']),
                                                      exchange=dict(status=(x or {}).get('status'), path=env.get('EXCHANGE'),
                                                                    sha256=(x or {}).get('exchange_sha256'),
                                                                    listed=env.get('EXCHANGE_LISTED')),
                                                      school=dict(status=school.get('status'), file=school.get('file'),
                                                                  sha256=school.get('school_sha256') or (school.get('row') or {}).get('sha256'))),
                                          use=dict(carried='the classroom directory, the exchange and its meeting (read by the '
                                                           'report step itself)',
                                                   school='recorded for currentness only: the reports do not read the school '
                                                          'file; a later checked school successor gets a revision under '
                                                          'the same number (reports_school_stale)',
                                                   meeting_status=((r or {}).get('meeting') or {}).get('status')),
                                          outputs=dict(report_number=(r or {}).get('report_number'),
                                                       reports=[{k: item.get(k) for k in ('kind', 'number', 'revision', 'file', 'sha256')}
                                                                for item in (r or {}).get('reports') or []],
                                                       exit_code=code)))
            if code == 0 and r:
                return self.record('reports', day, 'done', **fields)
            # reports X5: the step exits 75 at a report boundary on a requested save (its written reports are reused on
            # the re-run): saved, never failed or requeued, exactly as the ROOT's 75 (child_saved)
            saved = self.child_saved('reports', day, code, **{k: v for k, v in fields.items() if k != 'exit_code'})
            if saved:
                return saved
            return self.record('reports', day, 'failed', reason='the report step exited %d%s (its log names why)' % (
                code, '' if r else ' without a receipt'), **fields)
        except Exception as error:        # a report failure never stops the run: recorded, retried on the next start
            return self.record('reports', day, 'failed', reason='%s: %s' % (type(error).__name__, error))

    def guarded(self, stage, e):
        """A step after the lessons (exchange, voice, school, reports): an error is recorded as the step's failure with its
        reason (retried on the next start); it never stops the run or the other days."""
        try:
            self.successors(e['day'])
            self.check_save()
            remote = self.remote_stage(stage, e['day'])
            if remote is not None:
                return remote
            return getattr(self, stage)(e)
        except Exception as error:
            return self.record(stage, e['day'], 'failed', reason='%s: %s' % (type(error).__name__, error))

    INSPECTION_SECONDS = 900          # the reporter reads recorded metadata only (8 MiB ceiling per file); never a long job

    def day_cpus(self):
        """The run's day slot size (Greg, 2026-10-07: "Give the day 32 CPUs and that many workers"; session 8: 64 = the whole
        64-vCPU box). While this Run HOLDS its day booking, the booking's live size is the answer (the ledger made it
        agree with the plan at booking, or refused; a booking grown at the classroom boundary (FRANKIE_CLASSROOM_CPUS)
        is wider than the plan and every later stage scales to it); before the booking, plan day_cpus, else the
        ledger's DAY_RUN_CPUS (16, Greg 2026-09-29: "Correct 16"). Every worker count the orchestrator hands a stage is
        this minus one coordinator; the stages that read their affinity or FRANKIE_LANE_CPUS scale too."""
        booking = getattr(self, 'slot_booking', None)
        if booking:
            try:
                held, _why = self.cores.held_booking(booking)
            except (OSError, ValueError):
                held = None
            if held and held.get('cpus'):
                return len(held['cpus'])
        return int(self.plan.get('day_cpus') or self.cores.DAY_RUN_CPUS)

    def classroom_lane(self, day, out_dir):
        """Session 8 (Greg: "a classroom day gets all 64"): the classroom day's CPU set from the ONE resolver
        (frankie_box_cores.lane_for 'classroom-day'): FRANKIE_CLASSROOM_CPUS (a run setting given at kick time, FA-6)
        held (default: the day's booking, unchanged) | all | one of DAY_RUN_SIZES. A wider set is reached by GROWING the
        day's held booking in the ledger before the classroom child starts (same booking, the extra CPUs taken when
        free, else the day WAITS visibly); the child then runs under taskset of the grown booking (cmd_run_inside reads
        it fresh) and day_cpus() scales the later stages. The answer and the grow outcome are written to
        <classroom dir>/cpu-plan.json. Returns (plan, None) or (None, (state, reason))."""
        booking = getattr(self, 'slot_booking', None)
        held = None
        if booking:
            try:
                held, _why = self.cores.held_booking(booking)
            except (OSError, ValueError):
                held = None
        try:
            plan = self.cores.lane_for('classroom-day', run=self.plan['run'], day=day, held=held)
        except self.cores.PlanRefused as error:
            return None, ('refused', 'classroom CPU plan: %s' % error)
        if plan.get('grow_to'):
            if not booking:
                return None, ('refused', 'classroom CPU plan asks %d CPUs but this Run holds no day booking to grow' % plan['grow_to'])
            _b, outcome = self.cores.grow(booking, plan['grow_to'], 'classroom day: %s' % plan['basis'][-1])
            plan['grow'] = outcome
            if outcome['status'] != 'grown':
                try:
                    Path(out_dir).mkdir(parents=True, exist_ok=True)
                    (Path(out_dir) / 'cpu-plan.json').write_text(json.dumps(plan, indent=1, sort_keys=True))
                except OSError:
                    pass
                return None, ('waiting' if outcome['status'] == 'waiting' else 'refused', 'classroom CPU plan: ' + outcome['reason'])
        try:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            (Path(out_dir) / 'cpu-plan.json').write_text(json.dumps(plan, indent=1, sort_keys=True))
        except OSError as error:
            self.log('classroom cpu-plan.json not written (%s); the plan: %s' % (error, plan['cpu_list']))
        self.log('classroom %s CPUs %s (%s)' % (day, plan['cpu_list'], '; '.join(plan['basis'])))
        return plan, None

    def ingest_size(self):
        """(DAY_CPUS, WORKERS or None, how) for one ingest day process (frankie_box_ingest_block.sh). A plan with a day
        slot size (plan day_cpus, the one-day run's 32) gives each ingest that size when it runs alone; days ingesting side
        by side (--parallel-days, the days of the plan not yet ingested) share the box: the largest ledger size (8/16/24/32)
        within its CPUs divided by them, so two days never ask the same CPUs and wait on each other. Alone without a plan
        size: 'auto' (the wrapper sizes from the ledger's free CPUs at its start). WORKERS is given only when
        --ingest-workers is a lower ceiling than DAY_CPUS - 1 (then the smallest size that fits it, the wrapper's rule)."""
        sizes = self.cores.INGEST_SIZES
        pending = [x for x in self.plan['days'] if not self.finished('ingest', x['day'])]
        at_once = max(1, min(int(self.a.parallel_days or 1), len(pending) or 1))
        online = len(self.cores.online_cpus()) or (os.cpu_count() or sizes[0])
        ceiling = int(self.a.ingest_workers)
        if ceiling + 1 < max(sizes) and ceiling + 1 <= online // at_once:
            size = min(s for s in sizes if s >= ceiling + 1)
            return size, max(1, ceiling), ('--ingest-workers %d is a ceiling below the box: the smallest size that fits it '
                                           '(%d CPUs, WORKERS + 1)' % (ceiling, size))
        if at_once == 1:
            if self.plan.get('day_cpus'):
                size = int(self.plan['day_cpus'])
                return size, None, ('the plan\'s day slot size %d (one ingest at a time: the day gets all of it; WORKERS = '
                                    '%d)' % (size, size - 1))
            return 'auto', None, ('one ingest at a time, no plan day size: DAY_CPUS=auto (the free CPUs at the wrapper\'s '
                                  'start, rounded down to %s)' % '/'.join(map(str, sizes)))
        share = max([s for s in sizes if s <= online // at_once] or [sizes[0]])
        return share, None, ('%d days ingesting side by side on %d CPUs: %d each (WORKERS = %d)'
                             % (at_once, online, share, share - 1))

    def meeting_threads(self):
        """(the meeting's llama-server threads, how): MEETING_THREADS, else the day's lane size (day_cpus). The meeting
        clamps it to its owning affinity (the claimed lane) and pins in physical-core order; a count above the lane never
        starts a server on CPUs outside it."""
        if MEETING_THREADS:
            return int(MEETING_THREADS), 'MEETING_THREADS=%d (the one setting), clamped by the meeting to the lane' % int(MEETING_THREADS)
        return self.day_cpus(), 'MEETING_THREADS None: the day\'s lane size (%d CPUs held for the day)' % self.day_cpus()

    def inspection_on(self):
        """True only when the saved plan is the one-day test (plan['inspection'] == 'one_day', decided once at plan time;
        Greg 2026-10-07: the per-piece status reports are for the ONE-day run only). Otherwise the skip is logged ONCE per
        Run and nothing is written per day (no reporter, no inspection receipt)."""
        if self.plan.get('inspection') == 'one_day':
            return True
        if not getattr(self, '_inspection_skip_logged', False):
            self._inspection_skip_logged = True
            self.log('inspection: off for run %s (plan inspection=%s; the per-piece status reports are for the one-day run '
                     'only); no per-day reports are written' % (self.plan['run'], self.plan.get('inspection') or 'absent'))
        return False

    def inspect_day(self, day, trigger):
        """The one-day inspection reporter (frankie_box_workflow_inspection.py --run-dir <run> --day <day> --write) after
        the day's last step on its lane: one markdown per canonical workflow piece under days/<day>/inspection plus
        index.md, from recorded receipts and known metadata contracts only (Greg, 2026-10-07: after the ONE-day test every
        piece shows what it received, how it used it and what it produced, before the THREE-day run). Temporary operator
        review: not knowledge, not evidence, not a gate, never read by a step. A previous inspection directory is moved
        aside (inspection.<utc>), never overwritten, so a retried day keeps what its earlier end showed. The reporter runs
        pinned to the day's held CPUs when they are known, under the same interpreter, -I (no project imports, by its own
        contract). Its failure, timeout or partial write is recorded on the day's 'inspection' receipt with the log;
        it never fails, waits or requeues the day. Returns the receipt."""
        script = self.box / 'frankie_box_workflow_inspection.py'
        out_dir = self.dir / 'days' / day / 'inspection'
        logs = self.dir / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        log_path = logs / ('%s-inspection.log' % day)
        moved_aside = None
        if out_dir.is_dir():
            moved_aside = str(out_dir) + '.' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
            try:
                os.rename(out_dir, moved_aside)
            except OSError as error:
                moved_aside = 'not moved aside (%s: %s); the reporter replaces the files in place' % (type(error).__name__, error)
        cpus, cpus_why = None, None
        booking = getattr(self, 'slot_booking', None)
        if booking:
            try:
                held, why = self.cores.held_booking(booking)
                cpus = sorted(held['cpus']) if held and held.get('cpus') else None
                cpus_why = None if cpus else 'held booking %s not live: %s; unpinned' % (booking, why)
            except Exception as error:  # noqa: BLE001 - the pin is a courtesy to the lane rule, named when it is not possible
                cpus_why = 'ledger not read (%s: %s); unpinned' % (type(error).__name__, error)
        elif self.owner and self.owner.get('cpus'):
            cpus = sorted(self.owner['cpus'])
        else:
            cpus_why = 'no held booking or owner CPU set known to this Run; unpinned'
        command = [sys.executable, '-I', '-B', str(script), '--run-dir', str(self.dir), '--day', day, '--write']
        # F10 (second review): no preexec_fn (unsafe in this threaded process: the child can deadlock before exec). The
        # pin is taskset in the command itself, as the stage children pin; without taskset the reporter runs unpinned,
        # named on the receipt
        if cpus:
            taskset = shutil.which('taskset')
            if taskset:
                command = [taskset, '-c', ','.join(str(c) for c in cpus)] + command
            else:
                cpus_why = 'taskset not found on this host; the reporter ran unpinned (held CPUs %s)' % cpus
                cpus = None
        code, reason = None, None
        started = time.time()
        try:
            with open(log_path, 'ab') as out:
                out.write(('\n### inspection %s at %s (%s)\n' % (day, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                                                 trigger)).encode())
                out.flush()
                # the reporter's own heartbeat (stage 'inspection'), the same contract as Run.child
                heartbeat = None
                try:
                    import frankie_box_stage_progress as SP
                    heartbeat = SP.Heartbeat(self.dir, day, 'inspection', log_path=log_path)
                except Exception:  # noqa: BLE001 - the probe is never the reporter's outcome
                    heartbeat = None
                with subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT, start_new_session=True,
                                      env=dict(os.environ, **(heartbeat.env() if heartbeat else {}))) as proc:
                    if heartbeat is not None:
                        heartbeat.start(proc.pid)
                    try:
                        code = proc.wait(timeout=self.INSPECTION_SECONDS)
                    except BaseException:
                        proc.kill()               # subprocess.run's behaviour on a timeout or an interrupted wait
                        raise
                    finally:
                        if heartbeat is not None:
                            heartbeat.stop('exited' if code is not None else 'stopped (timeout or interrupted)', code)
        except subprocess.TimeoutExpired:
            reason = 'the reporter exceeded %d s and was stopped; the files written so far stand' % self.INSPECTION_SECONDS
        except OSError as error:
            reason = 'the reporter could not be started: %s: %s' % (type(error).__name__, error)
        written = sorted(p.name for p in out_dir.glob('*.md')) if out_dir.is_dir() else []
        if reason is None and code != 0:
            reason = 'the reporter exited %s (its log names why); the files written so far stand' % code
        elif reason is None and 'index.md' not in written:
            reason = 'the reporter exited 0 without writing index.md under %s' % out_dir
        status = 'done' if reason is None else 'failed'
        return self.record('inspection', day, status, trigger=trigger, exit_code=code, log=str(log_path),
                           directory=str(out_dir), written=written, pieces_written=len([w for w in written if w != 'index.md']),
                           moved_aside=moved_aside, cpus=cpus, cpus_note=cpus_why, seconds=round(time.time() - started, 1),
                           reason=reason, rule='temporary operator review; not knowledge, not a gate; a reporter failure '
                                               'never fails the day')

    def reports_invocation(self, day, c=None, cls=None):
        """THE ONE builder of the day reports' invocation (the wrapper's environment), used by Run.reports to render and by
        Run.reports_stale to ask late_pieces_changed what the reports would read NOW (one source, so the check never
        compares against an invocation the render would not use). c: the day's classroom step receipt (read when None);
        cls: the day class (from the plan when None). Returns (env, None), or (None, why) when no classroom directory is
        named by the classroom or the root step. Reads receipts only; renders nothing."""
        c = c if c is not None else (self.receipt('classroom', day) or {})
        if cls is None:
            cls = next((x.get('cls') for x in self.plan.get('days') or [] if x.get('day') == day), None)
        classroom = c.get('classroom')
        if not classroom:                    # refused before the classroom step named its directory (e.g. no digest)
            root = self.receipt('root', day) or {}
            classroom = str(Path(root['calculations']) / 'work' / 'classroom') if root.get('calculations') else None
        if not classroom:
            return None, 'neither the classroom step nor the root step names the day\'s classroom directory'
        env = dict(DAY=day, CLASSROOM=classroom, RUN=self.plan['run'], REPORTS_DIR=REPORTS)
        if cls is not None:
            env['DAY_CLASS'] = cls
        if c.get('status') == 'refused' and c.get('reason'):
            env['REFUSED_REASON'] = c['reason']      # used only when the classroom wrote no receipt of its own
        x = self.receipt('exchange', day)
        if x and x['status'] in ('done', 'reused') and x.get('exchange'):
            env['EXCHANGE'] = x['exchange']
        else:
            env['EXCHANGE_LISTED'] = 'the day\'s exchange stage is %s%s' % (
                (x or {}).get('status') or 'not run', (': ' + x['reason']) if (x or {}).get('reason') else '')
        # the school file (correction_consumer, stage 12, 2026-10-07): the day's FRANKIE_SCHOOL_KNOWLEDGE_V1 file when
        # the school stage is done/reused (the wrapper passes --school), else why there is none (--school-listed);
        # without it the FRANKIE report's school section reads "not given"
        school = self.receipt('school', day) or {}
        if school.get('status') in ('done', 'reused') and school.get('file'):
            env['SCHOOL'] = school['file']
        else:
            env['SCHOOL_LISTED'] = 'the day\'s school stage is %s%s' % (
                school.get('status') or 'not run', (': ' + school['reason']) if school.get('reason') else '')
        # the FRANKIE report's "The 99 layers" section (correction_consumer, 2026-10-07): the run directory and the piece
        # receipts that carry an all-99 list; each only when its stage finished with that receipt (else the report lists it)
        env['RUN_DIR'] = self.dir
        batch = self.batch_of(day)
        sv = self.receipt('survivors', batch) if batch else None
        if sv and sv.get('status') == 'done' and isinstance(sv.get('receipt'), dict) and sv['receipt'].get('path'):
            env['CANDIDATES_RECEIPT'] = sv['receipt']['path']
        al = self.receipt('accumulated_lessons', day) or {}
        if al.get('status') == 'done' and al.get('receipt'):
            env['CARRIED_CLAIMS_RECEIPT'] = al['receipt']
        jv = self.receipt('jev', day) or {}
        if jv.get('receipt') and Path(jv['receipt']).is_file():
            env['JEV_RECEIPT'] = jv['receipt']
        return env, None

    def reports_stale(self, e):
        """Do the day's done reports need a revision under the existing number? True when:
          - a done exchange has returned since the reports were rendered without one;
          - the school they were rendered on was replaced by a checked successor (school_current / reports_school_stale);
          - the meeting the exchange carries changed (record sha256 or status);
          - the 99-layer join's input set changed (frankie_box_experiment_day_reports.late_pieces_changed, F9a: a late
            Jev, candidates or carried-claims receipt, a lessons list, an exchange). This check runs whatever the
            exchange's state (the reports render on a waiting or not_run exchange too, so a late piece is never hidden
            behind it), with the invocation the render would use NOW (reports_invocation, the one builder).
        late_pieces_changed 'unknown' is never a change: no revision, its reason logged. The check's result is recorded on
        the reports step receipt (late_pieces) for the one-day inspection, only when it differs from the recorded one."""
        day = e['day']
        r, x = self.receipt('reports', day), self.receipt('exchange', day)
        if not (r and r['status'] == 'done'):
            return False
        exchange_done = bool(x and x['status'] in ('done', 'reused'))
        if exchange_done and r.get('exchange_status') not in ('done', 'reused'):
            return True
        if exchange_done:
            if not self.school_current(day, 'reports')[0] or self.reports_school_stale(day):
                return True                # the reports were rendered on a school that a checked successor replaced
            if x.get('frankie_view'):
                import frankie_box_brain as BR
                meeting = BR.read_meeting_for_exchange(x['frankie_view'])
                current = ((meeting.get('receipt') or {}).get('record') or {}).get('sha256')
                prior = r.get('meeting') or {}
                if prior.get('sha256') != current or prior.get('status') != meeting['status']:
                    return True
        return self.reports_late_pieces(day, r) == 'changed'

    def unacknowledged_corrections(self, day):
        """The day's successor requests (successors/<day>/requests/*.json) without an acknowledgment
        (work/<name>/ack.json), by name; read only, no lock, no drain."""
        directory = self.dir / 'successors' / day
        requests = sorted((directory / 'requests').glob('*.json')) if (directory / 'requests').is_dir() else []
        return [p.name for p in requests if not (directory / 'work' / p.stem / 'ack.json').is_file()]

    def reports_late_pieces(self, day, step=None):
        """late_pieces_changed (correction_consumer's contract, FRANKIE_DAY_REPORTS_LATE_PIECES_V1) on the day reports
        receipt <REPORTS>/receipts/<run>/<day>.json with `current` built from reports_invocation (every INVOCATION_KEYS
        key given, None included, so nothing falls back to the recorded value). Returns its outcome ('changed' |
        'unchanged' | 'unknown'). An unknown is logged with its reason. The summary (outcome, reason, differences,
        reasons_only count, invocation source, checked_at) is written onto the reports step receipt as late_pieces when
        it differs from the one recorded there (a durable rewrite of the same receipt: no new attempt, no knowledge
        boundary). Never raises: a failure of the check itself is an unknown."""
        import frankie_box_experiment_day_reports as DR
        try:
            env, why = self.reports_invocation(day)
            if env is None:
                late = dict(schema=getattr(DR, 'LATE_PIECES_SCHEMA', None), outcome='unknown', differences=[],
                            reason='no invocation can be built now: %s' % why)
            else:
                pieces = dict(candidates=env.get('CANDIDATES_RECEIPT'), carried_claims=env.get('CARRIED_CLAIMS_RECEIPT'),
                              jev=env.get('JEV_RECEIPT'))
                current = dict(classroom=env['CLASSROOM'], refused_reason=env.get('REFUSED_REASON'),
                               exchange=env.get('EXCHANGE'), exchange_listed=env.get('EXCHANGE_LISTED'),
                               school=env.get('SCHOOL'), school_listed=env.get('SCHOOL_LISTED'), run_dir=str(env['RUN_DIR']),
                               piece_receipts={k: str(v) for k, v in pieces.items() if v})
                late = DR.late_pieces_changed(DR.reports_receipt_path(REPORTS, self.plan['run'], day), current)
        except Exception as error:      # noqa: BLE001 - the check is accounting; its own failure is an unknown, named
            late = dict(outcome='unknown', differences=[], reason='the late-pieces check failed: %s: %s' % (
                type(error).__name__, error))
        outcome = late.get('outcome') if late.get('outcome') in ('changed', 'unchanged', 'unknown') else 'unknown'
        if outcome == 'unknown':
            self.log('reports %s: late pieces unknown (no revision): %s' % (day, late.get('reason')))
        summary = dict(schema=late.get('schema'), outcome=outcome, reason=late.get('reason'),
                       differences=late.get('differences') or [], reasons_only=len(late.get('reasons_only') or []),
                       invocation_source=(late.get('invocation') or {}).get('source'),
                       recorded_all99_sha256=(late.get('recorded') or {}).get('all99_sha256'),
                       current_all99_sha256=(late.get('current') or {}).get('all99_sha256'),
                       rule='changed = a revision under the same number; unknown = no revision, reason logged; '
                            'operator review only, never a gate')
        try:
            step = step if step is not None else self.receipt('reports', day)
            if step and {k: v for k, v in (step.get('late_pieces') or {}).items() if k != 'checked_at'} != summary:
                from frankie_box_durable import write_json
                # N-1 (fresh review): re-read right before the write and write only when the step is the one read (its
                # `at` unchanged), so a reports render recorded meanwhile is never written over (its own next check
                # records the result instead)
                fresh = self.receipt('reports', day)
                if not fresh or fresh.get('at') != step.get('at'):
                    self.log('reports %s: the step was re-recorded during the late-pieces check; result not written '
                             'over it (outcome %s)' % (day, outcome))
                    return outcome
                step = fresh
                checked = dict(summary, checked_at=time.time())
                # also under the step's `inspection` (projected whole by frankie_box_workflow_inspection)
                write_json(self.receipt_path('reports', day), dict(step, late_pieces=checked,
                                                                   inspection=dict(step.get('inspection') or {},
                                                                                   late_pieces=checked)))
        except Exception as error:      # noqa: BLE001 - recording is for the inspection; its failure is logged, not hidden
            self.log('reports %s: the late-pieces result could not be recorded (%s: %s)' % (day, type(error).__name__, error))
        return outcome

    def report_number(self, e):
        """The day's report number N: reserved once, right after its classroom step, in the reports' own index
        (frankie_box_experiment_day_reports.reserve_number), so the numbering is what it was when the reports ran there."""
        import frankie_box_experiment_day_reports as R
        # the class worker: N is the class line's school-day number (the queue assigns it; a day holding another N refuses)
        return R.reserve_number(REPORTS, self.plan['run'], e['day'], number=self.school_day)[0]

    def reserve_after_classroom(self, e):
        c = self.receipt('classroom', e['day'])
        if not (e['classroom_arm'] and c and c['status'] in ('done', 'reused', 'refused')):
            return
        try:
            self.log('report number %s: #%d (reserved after the classroom)' % (e['day'], self.report_number(e)))
        except Exception as error:        # the reports step assigns it then; never stops the run
            self.log('report number %s not reserved here (%s: %s); the reports step assigns it' % (
                e['day'], type(error).__name__, error))

    # The three-way exchange, its bounded coordinator meeting and the school knowledge base.
    def rows_file(self, e):
        """(the BOSS teacher's Dipole rows file of the day, None) or (None, why)."""
        base, source, why = self.day_rows(e)
        if base is None:
            return None, why or 'no Dipole rows of the day (teacher batch: %s)' % (
                (self.receipt('teacher', self.batch_of(e['day'])) or {}).get('status') or 'not run')
        if source == 'launch run':
            found = sorted(Path(base).glob('execution/cycle-*/host-dipole-classroom-source*.json'))
            if len(found) != 1:
                return None, '%d Dipole sources in the launch run %s (one is needed; none is chosen)' % (len(found), base)
            return found[0], None
        return Path(base) / ROWS_FILE, None

    def lessons_files(self, e, lessons):
        """(the lessons files of the day's batch that may have tested the day, listed): Frankie's of the day, Jev's of
        the day, the historical lessons of the batch's searched days (the exchange re-checks each file's days)."""
        day, files, listed = e['day'], [], []
        mine = LESSONS_ROOT / 'frankie' / ('%s-frankie.json' % day)
        if mine.is_file():
            files.append(mine)
        else:
            listed.append('no FRANKIE_LESSONS_V1 of %s (no novel findings of his were tested for the day)' % day)
        files += sorted((LESSONS_ROOT / 'jev').glob('%s-*.json' % day))
        if self.plan.get('historical_claims'):
            path = self.historical_lessons(lessons.get('searched_days') or [])
            (files.append(path) if path and path.is_file() else
             listed.append('no historical lessons for the searched days %s (%s)' % (lessons.get('searched_days'), path)))
        return files, listed

    def historical_lessons(self, searched_days):
        """The HISTORICAL_LESSONS_V1 file the scientific teacher writes for these searched days (its own name rule)."""
        if not searched_days:
            return None
        claims = json.loads((self.code_root / self.plan['historical_claims']).read_bytes())
        return LESSONS_ROOT / 'historical' / ('%s-%s.json' % ('-'.join(sorted(searched_days)), claims['catalog_sha256'][:12]))

    def require_current_teacher_inputs(self, day):
        """After knowledge sync and before reuse/dispatch: frozen errors need checked successors."""
        import frankie_box_lane_state as LS
        brain = self.plan.get('brain') or BRAIN
        exchange = self.receipt('exchange', day) or {}
        successor = exchange.get('successor_inputs')
        if successor:
            import frankie_box_experiment_review as REVIEW
            REVIEW._read_pin(successor)
        paths = (self.dir / 'scientific-knowledge' / day / 'inputs.json',
                 Path(successor['path']) if successor else self.dir / 'exchange' / day / 'scientific-knowledge' / 'inputs.json',
                 Path(successor['path']) if successor else self.dir / 'exchange' / day / 'learner-knowledge.json')
        for path in dict.fromkeys(paths):
            LS.require_current_selection(path, brain=brain)

    def require_current_exchange(self, day, env):
        """Do not launch a consumer with sources captured before child() drained corrections."""
        import frankie_box_experiment_review as REVIEW
        current = self.receipt('exchange', day) or {}
        selected = [(field, name) for field, name in (('EXCHANGE_VIEW', 'frankie_view'), ('EXCHANGE', 'exchange'))
                    if env.get(field)]
        if not selected:
            if current.get('status') in ('done', 'reused') and current.get('frankie_view'):
                raise ValueError('exchange became available at the child boundary; rebuild consumer inputs')
            return
        self.require_current_teacher_inputs(day)
        if current.get('status') not in ('done', 'reused'):
            raise ValueError('consumer exchange is no longer complete; rebuild inputs')
        receipt_path = Path(current['frankie_view']).parent / 'receipt.json'
        published = json.loads(receipt_path.read_bytes())
        for field, name in selected:
            if str(env[field]) != current.get(name):
                raise ValueError('exchange changed at the child boundary; rebuild consumer inputs')
            pin = published['full' if name == 'exchange' and current.get('successor_inputs') else name]
            if pin['path'] != str(env[field]):
                raise ValueError('consumer exchange differs from its publication receipt')
            REVIEW._read_pin(pin)

    def exchange(self, e):
        day = e['day']
        if not e['classroom_arm']:
            return self.record('exchange', day, 'skipped', reason='not a classroom-arm day')
        if e['role'] != 'discovery':
            return self.record('exchange', day, 'skipped', reason='discovery days only (R15)')
        target = self.dir / 'exchange' / day
        self.require_current_teacher_inputs(day)
        successor = self.receipt('exchange', day) or {}
        if successor.get('successor_inputs'):
            import frankie_box_experiment_review as REVIEW
            REVIEW._read_pin(successor['successor_inputs'])
            delivered = Path(successor['frankie_view'])
            if sha256_file(delivered) != successor['exchange_sha256']:
                raise ValueError('retained exchange successor changed')
            return successor
        if (target / 'receipt.json').is_file():
            r = json.loads((target / 'receipt.json').read_bytes())
            return self.record('exchange', day, 'reused', exchange=r['exchange']['path'], frankie_view=r['frankie_view']['path'],
                               exchange_sha256=r['exchange']['sha256'], brain_entry=r.get('brain_entry'), counts=r.get('counts'))
        key = self.batch_of(day)
        lessons = self.receipt('lessons', key)
        if not (lessons and lessons['status'] in FINISHED):
            return self.record('exchange', day, 'waiting', reason='the lessons of the batch %s are %s' % (
                key, (lessons or {}).get('status') or 'not run'))
        search = self.receipt('search', day)
        if not (search and search['status'] in FINISHED):
            return self.record('exchange', day, 'waiting', reason='the day\'s search is %s' % ((search or {}).get('status')
                                                                                              or 'not run'))
        if search['status'] == 'not_run':
            # B5: the exchange's scientific turn replies with the day's search counts; with no search of the day the
            # exchange is not run (listed with the search's reason); voice, school and reports go on without it
            return self.record('exchange', day, 'not_run', reason='the day\'s search is not_run (%s): no search counts for '
                                                                 'the exchange; listed' % search.get('reason'))
        files, listed = self.lessons_files(e, lessons)
        import frankie_box_experiment_review as REVIEW
        import frankie_box_lane_state as LS
        brain = self.plan.get('brain') or BRAIN
        corrections = REVIEW.corrections(LS.knowledge_roots(brain))
        corrected_files = []
        for path in files:
            raw = Path(path).read_bytes()
            delivered = REVIEW.current_document(dict(path=str(path), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(), content=json.loads(raw)),
                corrections, brain, day=day, stage='exchange')
            corrected_files.append(Path(delivered['path']))
        files = corrected_files
        # Completed accumulated lessons are also actual exchange inputs, even without a new lesson of this day.
        rows, rows_why = self.rows_file(e)
        if rows is None and rows_why and rows_why.startswith(('refused', 'waiting')):
            return self.record('exchange', day, rows_why.split(':')[0], reason=rows_why)
        env = dict(DAY=day, RUN=self.plan['run'], LESSONS=','.join(str(f) for f in files), OUT_DIR=target,
                   BRAIN=self.plan.get('brain') or str(BRAIN),
                   SEARCH_DIR=SEARCH / day / ('cycle-' + CYCLE) / 'discovery')
        if rows is not None:
            env['TEACHER_ROWS'] = rows
        code, log = self.child('exchange', day, 'frankie_box_experiment_exchange.sh', env)
        saved = self.child_saved('exchange', day, code, log, lessons=[str(f) for f in files], listed=listed)
        if saved:
            return saved
        if code != 0 or not (target / 'receipt.json').is_file():
            return self.record('exchange', day, 'failed', exit_code=code, log=log, lessons=[str(f) for f in files],
                               listed=listed, reason='no exchange receipt after the step (its log names why)')
        r = json.loads((target / 'receipt.json').read_bytes())
        return self.record('exchange', day, 'done', exit_code=code, log=log, exchange=r['exchange']['path'],
                           frankie_view=r['frankie_view']['path'], exchange_sha256=r['exchange']['sha256'],
                           brain_entry=r.get('brain_entry'), counts=r.get('counts'), lessons=[str(f) for f in files],
                           accumulated_claim_tests=r.get('accumulated_claim_tests'),
                           listed=listed, teacher_rows=str(rows) if rows else None, teacher_rows_listed=rows_why,
                           new_bytes=new_bytes(target))

    def voice(self, e):
        """Run or reuse the bounded meeting; a recorded runtime refusal never blocks school/reports.

        One meeting child per DECISION, never per call: the main stage loop (every start), the owner school recovery
        (every drain) and the class worker all reach this step. A standing non-blocking receipt (waiting, non_blocking,
        the meeting refused / inputs_only) bound to the current exchange and to the same retained meeting record is
        returned as it is while the decision that refused it stands (standing_voice); the class worker's passed('voice')
        already treats it as passed. A voice receipt the day's own successor drain wrote during this call (recover_school
        -> voice) is this call's result, never followed by a second dispatch. The step's receipt carries inspection=
        {inputs, use, outputs} for the one-day report."""
        import frankie_box_brain as BR
        import frankie_box_granite_meeting as GM
        day = e['day']
        if not e['classroom_arm']:
            return self.record('voice', day, 'skipped', reason='not a classroom-arm day')
        own_receipt = self.receipt_path('voice', day)
        before = own_receipt.read_bytes() if own_receipt.is_file() else None
        self.successors(day)
        after = own_receipt.read_bytes() if own_receipt.is_file() else None
        if after is not None and after != before:
            self.log('voice %s: recorded by the day\'s successor drain (the owner school recovery) during this call; '
                     'not dispatched again' % day)
            return json.loads(after)
        self.check_save()
        x = self.receipt('exchange', day)
        if not (x and x['status'] in ('done', 'reused') and x.get('frankie_view')):
            status = (x or {}).get('status')
            return self.record('voice', day, status if status in ('skipped', 'not_run') else 'waiting',
                               reason='the day\'s exchange is %s%s' % (status or 'not run',
                                                                       (': ' + x['reason']) if (x or {}).get('reason') else ''))
        self.require_current_exchange(day, dict(EXCHANGE_VIEW=x['frankie_view']))
        target = BR.meeting_directory(x['frankie_view'], owner_dir=self.dir)
        brain = self.plan.get('brain') or str(BRAIN)
        existing = target / 'meeting.json'
        reused, code, log = False, 0, None
        use = 'the meeting child dispatched (no retained meeting record for this exchange)'
        inputs = dict(exchange_view=x['frankie_view'], exchange_sha256=x.get('exchange_sha256'), brain=brain,
                      meeting_directory=str(target), retained_record=None, runtime_config=None)
        if existing.is_file():
            record = BR.read_meeting_record(existing, exchange_path=x['frankie_view'], complete=False)
            inputs.update(retained_record=dict(path=str(existing), sha256=sha256_file(existing), status=record['status']),
                          runtime_config=record.get('runtime_config'))
            if record['status'] == 'complete':
                GM.publish_meeting_record(x['frankie_view'], target, brain)
                reused = True
                use = 'the retained complete meeting record of this exchange published again; no child'
            else:
                standing, why = self.standing_voice(day, existing, record)
                if standing is not None:
                    self.log('voice %s: standing %s meeting kept (%s); not dispatched again' % (day, record['status'], why))
                    return standing
                use = 'the meeting child dispatched (the retained record is %s and the decision that left it so has changed: %s)' % (
                    record['status'], why)
        if not reused and self.plan.get('voice_route') == 'github':
            return self.voice_remote(e, x, target, brain, inputs)
        if not reused and not getattr(self, 'slot_booking', None):
            # Greg, 2026-10-07: the meeting is an ordinary stage of the day on the day's held lane (frankie_box_cores
            # STAGE_SLOTS 'adviser', now the WHOLE lane: Greg, 2026-10-07 night, every step gets the day's CPUs; the claim
            # keeps two meeting children of one day from running at once); a Run that holds no day slot (the --root-queue off
            # batch path) has no lane to place it on: waiting, non-blocking, named; never a booking of its own
            return self.record('voice', day, 'waiting', non_blocking=True,
                               reason='the meeting runs on the day\'s held lane (the adviser slot: the whole lane); this Run holds no '
                                      'day slot (the ROOT line or the class line runs it)',
                               inspection=dict(inputs=inputs, use='not dispatched: no held day lane on this Run',
                                               outputs=dict(meeting_status=None)))
        if not reused:
            receipt_path = target / 'receipt.json'
            prior_receipt = receipt_path.read_bytes() if receipt_path.is_file() else None
            # MEETING_THREADS: the meeting's llama-server threads from the one setting (default the day's lane size: 32 on
            # a 32-CPU day; every other runtime row from Granite's definition), on the whole held lane claimed by the child
            # wrapper (cores cmd_run_step, the 'adviser' slot = every CPU of the booking). The count is bound into the
            # meeting's binding and can change its text at the rounding level (as with Jev): recorded, never assumed
            threads, threads_basis = self.meeting_threads()
            env = dict(EXCHANGE_VIEW=x['frankie_view'], OUT_DIR=target, BRAIN=brain, MEETING_THREADS=threads)
            inputs['meeting_threads'] = dict(
                threads=threads, basis=threads_basis, setting=MEETING_THREADS, lane_size=self.day_cpus(),
                text_caveat='the llama-server thread count can change the meeting\'s text at the rounding level (CPU '
                            'flash-attention splits the KV range across threads, as with Jev); it is bound into the meeting '
                            'binding and record, so a meeting at another count is another meeting')
            # the one pinned runtime on the box (shared_runtime): its paths reach the wrapper as LLAMA_SERVER/GGUF_MODEL
            # when the gate is ready; otherwise the wrapper runs the local route on the canonical paths and the meeting's
            # gate REFUSES visibly (a refused record; the reasons also on this receipt; the day goes on, non-blocking)
            runtime = self.shared_runtime()
            if runtime['status'] == 'ready':
                env.update(LLAMA_SERVER=runtime['binary'], GGUF_MODEL=runtime['model'])
            inputs['env'] = {k: str(v) for k, v in env.items()}
            inputs['runtime_binary_and_model_set'] = runtime['status'] == 'ready'
            inputs['shared_runtime'] = dict(status=runtime['status'], reasons=runtime['reasons'], binary=runtime['binary'],
                                            model=runtime['model'], provenance=runtime['provenance'])
            code, log = self.child('voice', day, 'frankie_box_granite_meeting.sh', env)
            inputs['adviser_slot'] = (self._cpu.get(('voice', day)) or {}).get('line') or 'no claim line (the child did not reach the ledger)'
            inputs['adviser_slot_cpus'] = 'the whole held lane (frankie_box_cores.SLOT_CPUS adviser=None)'
            if code != 0:
                current = receipt_path.read_bytes() if receipt_path.is_file() else None
                if (current is None or current == prior_receipt
                        or json.loads(current).get('status') != 'runtime_failed'):
                    # 2026-10-09 (Greg: the meeting never blocks the classroom): a failed meeting child is LISTED on a
                    # non-blocking receipt (meeting_status runtime_failed, the class side passes it); school and the
                    # reports go on, the retained artifacts stay for the next attempt, the reports are rebuilt when the
                    # meeting arrives
                    return self.record('voice', day, 'waiting', non_blocking=True, meeting_status='runtime_failed',
                                       meeting_child_failed=True, exit_code=code, log=log,
                                       refused_to_run=['the meeting child exited %s (its log %s)' % (code, log)],
                                       reason='meeting child failed (exit %s); listed, the day goes on; retained artifacts are '
                                              'kept for recovery' % code,
                                       inspection=dict(inputs=inputs, use=use,
                                                       outputs=dict(exit_code=code, meeting_receipt_changed=current != prior_receipt)))
        result = BR.read_meeting_for_exchange(x['frankie_view'], owner_dir=self.dir)
        if result['status'] == 'missing':
            return self.record('voice', day, 'waiting', non_blocking=True, meeting_status='runtime_failed',
                               meeting_child_failed=True, exit_code=code, log=log, refused_to_run=[result['reason']],
                               reason='%s; listed, the day goes on' % result['reason'],
                               inspection=dict(inputs=inputs, use=use, outputs=dict(exit_code=code, meeting='missing')))
        r = result['receipt']
        fields = dict(exit_code=code, log=log, meeting_status=result['status'], meeting=result['path'],
                      meeting_sha256=(r.get('record') or {}).get('sha256'), model_calls=r.get('model_calls', 0),
                      publication=r.get('publication'), brain_entry=r.get('brain_entry'),
                      counts=r.get('counts'), receipt=str(target / 'receipt.json'),
                      runtime_evidence=r.get('evidence'), binding=r.get('binding'))
        outputs = dict(meeting_status=result['status'], meeting=result['path'], model_calls=r.get('model_calls', 0),
                       counts=r.get('counts'), refused_to_run=r.get('refused_to_run'), publication=r.get('publication'),
                       brain_entry=r.get('brain_entry'), seconds=r.get('seconds'))
        if result['status'] == 'complete':
            return self.record('voice', day, 'reused' if reused else 'done', inspection=dict(inputs=inputs, use=use, outputs=outputs),
                               **fields)
        return self.record('voice', day, 'waiting', non_blocking=True,
                           refused_to_run=r.get('refused_to_run') or [result['reason']],
                           reason=result['reason'] or 'the runtime gate refused the meeting',
                           inspection=dict(inputs=inputs, use=use, outputs=outputs,
                                           standing_rule='kept as it is on later calls while the refusing decision stands '
                                                         '(runtime config gate / LLAMA_SERVER+GGUF_MODEL); see standing_voice'),
                           **fields)

    def standing_voice(self, day, existing, record):
        """(the standing voice receipt, why it stands) when the meeting is NOT to be dispatched again, else (None, why).
        It stands when the day's voice receipt is waiting + non_blocking with meeting_status equal to the retained
        record's (refused / inputs_only), names this meeting record (its path and the sha256 of its bytes now; the record
        itself binds the current exchange, read_meeting_record raised otherwise), and the decision that refused it still
        stands: for 'refused', frankie_box_granite_meeting.gate on the current runtime config still names a reason (or
        the config cannot be read); for 'inputs_only', LLAMA_SERVER / GGUF_MODEL are still not both set in this process
        (the wrapper runs inputs-only without them). A record refused only for a missing binary/model file passes the
        config gate and is dispatched again at the next call (the child's own gate refuses it again without a model
        call): bounded to one child per start, named here. The receipt is not rewritten while it stands."""
        import frankie_box_granite_meeting as GM
        v = self.receipt('voice', day) or {}
        if not (v.get('status') == 'waiting' and v.get('non_blocking') and v.get('meeting_status') == record['status']
                and v.get('meeting') == str(existing) and v.get('meeting_sha256') == sha256_file(existing)):
            return None, 'no standing non-blocking voice receipt bound to this %s record' % record['status']
        if record['status'] == 'refused':
            try:
                config, witness = GM.load_config()
                reasons = GM.gate(config)
                stands = ('the runtime config %s (sha256 %s) still refuses: %s' % (witness['path'], witness['sha256'][:12],
                                                                                  '; '.join(reasons))) if reasons else None
                changed = 'the runtime config %s (sha256 %s) no longer refuses by itself' % (witness['path'], witness['sha256'][:12])
                if stands is None:
                    # the local route's refusal of a runtime not installed (the wrapper no longer runs inputs-only without
                    # LLAMA_SERVER/GGUF_MODEL): it stands while the one shared runtime is still refused on this box
                    runtime = self.shared_runtime()
                    if runtime['status'] != 'ready':
                        stands = 'the shared model runtime is still refused: %s' % '; '.join(runtime['reasons'])[:600]
                    else:
                        changed = 'the shared model runtime is ready now (%s)' % runtime['binary']
            except (OSError, ValueError) as error:
                stands, changed = 'the runtime config cannot be read (%s: %s)' % (type(error).__name__, error), None
        elif record['status'] == 'inputs_only':
            runtime = self.shared_runtime()               # the one pinned runtime on the box, gated once per Run
            stands = None if runtime['status'] == 'ready' else ('the shared model runtime is still refused: %s: the wrapper would '
                                                                 'run inputs-only again' % '; '.join(runtime['reasons'])[:600])
            changed = 'the shared model runtime is ready now (%s)' % runtime['binary']
        else:
            return None, 'the retained record is %s: not a standing refusal' % record['status']
        if stands is None:
            return None, changed
        return dict(v, standing=dict(kept=True, because=stands, at=time.time())), stands

    # The remote (GitHub standard CPU runner) meeting route: the Step 6 caller contract (STEP6_COMPLETION_20261007.md,
    # "Exact remaining caller contract"). The owner writes an IMMUTABLE dispatch intent before any dispatch; the dispatch
    # itself is the operator's (workflow_dispatch of frankie_granite_meeting.yml by hand, with the presigned exchange GET,
    # inputs_only=false and a presigned GET of this owner's admission file); the operator records the exact GitHub run
    # (voice-dispatched), which writes the admission the runner must receive and verify BEFORE model setup/start (the
    # runner helper's `admit`); the return archive is recorded (voice-returned) and imported through the existing owner
    # importer (frankie_box_granite_runner.py import); an unknown outcome is reconciled to its attempt, never resent under
    # a new identity; a continuation binds its complete predecessor archive. No scheduler, lock service, token or GitHub
    # API call lives here: nothing in this file dispatches a workflow.
    VOICE_INTENT_SCHEMA = 'FRANKIE_VOICE_DISPATCH_INTENT_V1'
    VOICE_DISPATCH_SCHEMA = 'FRANKIE_VOICE_DISPATCH_V1'
    VOICE_ADMISSION_SCHEMA = 'FRANKIE_VOICE_ADMISSION_V1'
    VOICE_RETURN_SCHEMA = 'FRANKIE_VOICE_RETURN_V1'

    def voice_dispatch_dir(self, day, exchange_sha256):
        return self.dir / 'days' / day / 'voice-dispatch' / exchange_sha256

    def voice_attempts(self, base):
        """The attempt directories a1, a2, ... in order, each with what it has recorded (dispatched / admission / returned)."""
        out = []
        if not (base / 'attempts').is_dir():
            return out
        for d in sorted((base / 'attempts').glob('a[0-9]*'), key=lambda q: int(q.name[1:])):
            rec = dict(name=d.name, directory=str(d))
            for name in ('dispatched', 'admission', 'returned'):
                path = d / (name + '.json')
                rec[name] = json.loads(path.read_bytes()) if path.is_file() else None
                rec[name + '_pin'] = file_pin(path) if path.is_file() else None
            out.append(rec)
        return out

    def voice_intent(self, e, x, target, brain, write=True):
        """The immutable dispatch intent of the current exchange (create-only; a retained intent whose bound fields differ is
        refused, never rewritten): the exchange bytes/source/hash, run/day/owner, the meeting directory, the dispatched
        source commit and code root, the runtime config and classroom rules witnesses, the meeting-input witness the
        runner will compute from the same exchange (brain=None on the runner: no knowledge index, as frankie_box_granite_
        meeting._meeting does without --brain), the workflow's expected inputs. Returns (intent, pin, refusal)."""
        import frankie_box_granite_meeting as GM
        import frankie_box_classroom_code as K
        day = e['day']
        view = Path(x['frankie_view'])
        raw = view.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if x.get('exchange_sha256') and x['exchange_sha256'] != sha:
            return None, None, 'refused: the exchange receipt\'s sha256 (%s) differs from the bytes of %s (%s)' % (
                x['exchange_sha256'], view, sha)
        exchange = json.loads(raw)
        try:
            config, config_witness = GM.load_config()
        except (OSError, ValueError) as error:
            return None, None, ('waiting: the meeting runtime config cannot be read (%s: %s); no dispatch intent is written '
                                'without its witness' % (type(error).__name__, error))
        _, rules = K.rules()
        render_notes = {}       # the item-render pool's CPU placement (frankie_box_granite_meeting.meeting_input notes=)
        given = GM.meeting_input(exchange, [], notes=render_notes)
        input_bytes = GM._durable_json_bytes(given)
        owner = self.owner or dict(schema='FRANKIE_LANE_OWNER_V1', host=os.uname().nodename,
                                   attempt=self.owned_attempt or os.environ.get('FRANKIE_LANE_ATTEMPT'),
                                   marker=self.stop_marker, lane_owner=os.environ.get('FRANKIE_LANE_OWNER'))
        intent = dict(schema=self.VOICE_INTENT_SCHEMA, run=self.plan['run'], day=day, plan_sha256=plan_digest(self.plan),
                      owner=owner, host=os.uname().nodename,
                      exchange=dict(path=str(view), bytes=len(raw), sha256=sha, exchange_hash=exchange.get('exchange_hash')),
                      meeting_directory=str(target), brain=str(brain),
                      source=dict(commit=self.commit, code_root=str(self.code_root)),
                      runtime_config=config_witness,
                      rules=dict(file=Path(rules['path']).name, sha256=rules['sha256'], bytes=rules['bytes']),
                      meeting_input=dict(bytes=len(input_bytes), sha256=hashlib.sha256(input_bytes).hexdigest(),
                                         knowledge_index=[], note='what the runner computes from the same exchange without a brain'),
                      # where the caller's render of the meeting input ran (CPU map of the item-render pool); a record
                      # only, never part of the input bytes and not a bound identity field of the intent
                      meeting_input_placement=render_notes.get('item_render_pool') or
                      'not recorded (the render ran without a pool, or the meeting module recorded no placement)',
                      workflow=dict(file='.github/workflows/frankie_granite_meeting.yml',
                                    inputs=dict(exchange_sha256=sha, inputs_only='false', commit_must_equal=self.commit,
                                                admission_get_url='a presigned GET of the attempt\'s admission.json (voice-dispatched writes it)',
                                                prior_state='the predecessor attempt\'s returned archive URL and sha256, for a continuation')),
                      rule='written before any dispatch, create-only; the dispatch is the operator\'s by hand; an unknown '
                           'outcome is reconciled to its attempt (voice-returned), never resent under a new identity')
        base = self.voice_dispatch_dir(day, sha)
        path = base / 'intent.json'
        bound = ('schema', 'run', 'day', 'plan_sha256', 'exchange', 'meeting_directory', 'source', 'runtime_config', 'rules',
                 'meeting_input')
        if path.is_file():
            retained = json.loads(path.read_bytes())
            differ = [k for k in bound if retained.get(k) != intent.get(k)]
            if differ:
                return None, file_pin(path), ('refused: the retained dispatch intent %s binds another %s; it is never '
                                              'rewritten (a changed source/config/exchange is a new intent under a new '
                                              'exchange, or an explicit owner decision)' % (path, ', '.join(differ)))
            return retained, file_pin(path), None
        if not write:
            return None, None, None
        self.cores.write_json(path, intent, exclusive=True)
        return intent, file_pin(path), None

    def voice_remote(self, e, x, target, brain, inputs):
        """The remote route's state, read from the intent and its attempts; the only write here is the intent itself
        (before any dispatch). Every state is a visible receipt: waiting + non_blocking + meeting_status 'remote_pending'
        names exactly what the operator does next (dispatch, record the run, record the return, import), or refused
        with the reason. The day's school/reports go on (the class worker's passed('voice') passes remote_pending; the
        reports are rebuilt once the meeting returns: reports_stale)."""
        day = e['day']
        intent, intent_pin, refusal = self.voice_intent(e, x, target, brain)
        if refusal and refusal.startswith('waiting'):
            return self.record('voice', day, 'waiting', non_blocking=True, meeting_status='remote_pending', route='github',
                               reason=refusal, refused_to_run=[refusal], model_calls=0,
                               inspection=dict(inputs=inputs, use='remote route: no intent yet (its witness is missing)', outputs=dict(waiting=refusal)))
        if refusal:
            # an integrity mismatch (a retained intent binding other bytes, an exchange receipt whose sha differs from its
            # bytes): a visible refusal that holds the day's class side, never relabelled a wait
            return self.record('voice', day, 'refused', route='github', reason=refusal, intent=intent_pin,
                               inspection=dict(inputs=inputs, use='remote route: no intent, no dispatch', outputs=dict(refused=refusal)))
        base = self.voice_dispatch_dir(day, intent['exchange']['sha256'])
        attempts = self.voice_attempts(base)
        latest = attempts[-1] if attempts else None
        common = dict(route='github', intent=intent_pin, exchange_sha256=intent['exchange']['sha256'],
                      attempts=[dict(name=a['name'], github_run=(a['dispatched'] or {}).get('github_run_id'),
                                     admitted=bool(a['admission']), returned=(a['returned'] or {}).get('conclusion'))
                                for a in attempts],
                      operator_dispatch=dict(workflow=intent['workflow']['file'], inputs=intent['workflow']['inputs'],
                                             exchange_file=intent['exchange']['path'],
                                             then='frankie_box_experiment.sh ACTION=voice-dispatched RUN=%s VOICE_DAY=%s '
                                                  'VOICE_GITHUB_RUN=<id> [VOICE_GITHUB_ATTEMPT=<n>]' % (self.plan['run'], day)))
        use = 'remote route: the intent stands (%s); the dispatch, admission and return are recorded per attempt' % intent_pin['sha256'][:12]
        def pending(reason, **more):
            return self.record('voice', day, 'waiting', non_blocking=True, meeting_status='remote_pending', reason=reason,
                               refused_to_run=[reason], model_calls=0,
                               inspection=dict(inputs=dict(inputs, intent=intent_pin), use=use,
                                               outputs=dict(attempts=common['attempts'], next=reason)), **common, **more)
        if latest is None:
            return pending('no dispatch recorded for this intent: dispatch the workflow by hand with exchange_sha256=%s, '
                           'inputs_only=false, at commit %s, then record the exact GitHub run (voice-dispatched); the runner holds '
                           'before any model setup until that admission is served to it' % (intent['exchange']['sha256'][:12], self.commit))
        if latest['dispatched'] and not latest['admission']:
            return pending('attempt %s records GitHub run %s without its admission (an interrupted record): run voice-dispatched '
                           'again with the same run id (create-only; another id is refused)' % (
                               latest['name'], latest['dispatched'].get('github_run_id')))
        if latest['admission'] and not latest['returned']:
            return pending('attempt %s: GitHub run %s attempt %s admitted (%s); its return is not recorded: an unknown outcome '
                           'is reconciled, never resent (no new attempt until voice-returned records this one: the archive, its '
                           'sha256 and the run\'s conclusion)' % (latest['name'], latest['admission']['github_run_id'],
                                                                 latest['admission']['github_run_attempt'],
                                                                 latest['admission_pin']['sha256'][:12]),
                           admission=latest['admission_pin'])
        returned = latest['returned'] or {}
        if returned.get('conclusion') == 'success':
            return pending('attempt %s returned success (archive %s); the complete record is not under %s yet: import it on '
                           'this lane with frankie_box_granite_runner.py import --exchange %s --exchange-sha256 %s --commit %s '
                           '--archive %s --archive-sha256 %s --out <intake dir>; the next start reuses the imported complete '
                           'meeting' % (latest['name'], (returned.get('archive') or {}).get('sha256', '')[:12], target,
                                        intent['exchange']['path'], intent['exchange']['sha256'], intent['source']['commit'],
                                        (returned.get('archive') or {}).get('path'), (returned.get('archive') or {}).get('sha256')),
                           returned=latest['returned_pin'])
        return pending('attempt %s returned %s (archive %s, concluded): a continuation is a new attempt under this intent, '
                       'dispatched by hand with prior_state_get_url/prior_state_sha256 = that archive, then voice-dispatched; '
                       'its admission binds that predecessor' % (latest['name'], returned.get('conclusion'),
                                                                  (returned.get('archive') or {}).get('sha256', 'none')[:12]),
                       returned=latest['returned_pin'])

    def voice_dispatched(self, day, github_run_id, github_run_attempt, by):
        """The operator's record of the exact GitHub run dispatched for the standing intent: the attempt's dispatched.json
        and the ADMISSION the runner must receive before model setup/start, both create-only. Refused when no intent stands
        (the day's voice step writes it before any dispatch), when the latest attempt is not returned (an unknown outcome
        is never followed by a new identity), or when the predecessor's return is not concluded. The same run id again
        returns the existing record; another id for the same open attempt is refused."""
        e = next((d for d in self.plan['days'] if d['day'] == day), None)
        if e is None or not e.get('classroom_arm'):
            return dict(status='refused', reason='no classroom-arm day %s in the plan' % day)
        if not (str(github_run_id).isdigit() and str(github_run_attempt).isdigit()):
            return dict(status='refused', reason='the GitHub run id and attempt are digits')
        x = self.receipt('exchange', day) or {}
        if not (x.get('status') in ('done', 'reused') and x.get('frankie_view')):
            return dict(status='refused', reason='the day\'s exchange is %s; no meeting to dispatch' % (x.get('status') or 'not run'))
        import frankie_box_brain as BR
        target = BR.meeting_directory(x['frankie_view'], owner_dir=self.dir)
        intent, intent_pin, refusal = self.voice_intent(e, x, target, self.plan.get('brain') or str(BRAIN), write=False)
        if refusal:
            return dict(status='refused', reason=refusal)
        if intent is None:
            return dict(status='refused', reason='no dispatch intent stands for the current exchange: run the day to its voice '
                                                 'step first (the intent is written before any dispatch); nothing is admitted '
                                                 'for a dispatch made before it')
        base = self.voice_dispatch_dir(day, intent['exchange']['sha256'])
        attempts = self.voice_attempts(base)
        latest = attempts[-1] if attempts else None
        predecessor = None

        def predecessor_of(prior):
            returned = prior['returned'] or {}
            if not (returned.get('concluded') and (returned.get('archive') or {}).get('sha256')):
                return None, ('the predecessor attempt %s is returned without a concluded conclusion and archive witness; a '
                              'continuation needs both' % prior['name'])
            return dict(attempt=prior['name'], github_run_id=returned.get('github_run_id'),
                        github_run_attempt=returned.get('github_run_attempt'), conclusion=returned['conclusion'],
                        archive=returned['archive'], returned=prior['returned_pin']), None
        if latest is not None:
            if latest['dispatched'] and str(latest['dispatched'].get('github_run_id')) == str(github_run_id) \
                    and str(latest['dispatched'].get('github_run_attempt')) == str(github_run_attempt):
                if latest['admission']:
                    return dict(status='recorded', attempt=latest['name'], dispatched=latest['dispatched_pin'],
                                admission=latest['admission_pin'], reason='already recorded; nothing rewritten')
                attempt_dir = Path(latest['directory'])   # an interrupted record: the admission is written now, bound to
                if len(attempts) > 1:                     # the same predecessor its dispatch had (the attempt before it)
                    predecessor, why = predecessor_of(attempts[-2])
                    if why:
                        return dict(status='refused', reason=why)
            elif not latest['returned']:
                return dict(status='refused', attempt=latest['name'],
                            reason='attempt %s (GitHub run %s) is not returned: an unknown outcome is reconciled with '
                                   'voice-returned, never resent under a new identity' % (
                                       latest['name'], (latest['dispatched'] or {}).get('github_run_id')))
            else:
                predecessor, why = predecessor_of(latest)
                if why:
                    return dict(status='refused', reason=why)
                attempt_dir = base / 'attempts' / ('a%d' % (len(attempts) + 1))
        else:
            attempt_dir = base / 'attempts' / 'a1'
        dispatched = dict(schema=self.VOICE_DISPATCH_SCHEMA, intent=intent_pin, run=self.plan['run'], day=day,
                          github_run_id=str(github_run_id), github_run_attempt=str(github_run_attempt),
                          workflow=intent['workflow']['file'], dispatched_by=by, recorded_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        if not (attempt_dir / 'dispatched.json').is_file():
            self.cores.write_json(attempt_dir / 'dispatched.json', dispatched, exclusive=True)
        admission = dict(schema=self.VOICE_ADMISSION_SCHEMA, intent=intent_pin, run=self.plan['run'], day=day,
                         owner=intent['owner'], host=intent['host'], exchange_sha256=intent['exchange']['sha256'],
                         exchange_hash=intent['exchange']['exchange_hash'], commit=intent['source']['commit'],
                         meeting_input_sha256=intent['meeting_input']['sha256'],
                         github_run_id=str(github_run_id), github_run_attempt=str(github_run_attempt),
                         predecessor=predecessor, attempt=attempt_dir.name, admitted_by=by,
                         admitted_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                         rule='the runner (frankie_box_granite_runner.py admit) verifies run id, attempt, exchange sha256, '
                              'commit and predecessor against its own GITHUB_RUN_ID / GITHUB_RUN_ATTEMPT / GITHUB_SHA / '
                              'prior_state_sha256 before any model setup or call')
        self.cores.write_json(attempt_dir / 'admission.json', admission, exclusive=True)
        return dict(status='recorded', attempt=attempt_dir.name, dispatched=file_pin(attempt_dir / 'dispatched.json'),
                    admission=file_pin(attempt_dir / 'admission.json'), predecessor=predecessor,
                    next='serve %s to the runner as the workflow\'s admission_get_url (a presigned GET); the runner verifies '
                         'it before model setup; after the run, record its return with voice-returned' % (attempt_dir / 'admission.json'))

    def voice_returned(self, day, archive, archive_sha256, conclusion, by):
        """The operator's record of an admitted attempt's return: the downloaded runner-state.zip witness (its sha256 must
        equal the given one and the file must be owner-local), the GitHub run's conclusion and concluded=True. Create-only;
        a different return for the same attempt is refused. The import of a successful archive is the existing owner
        importer (named in the result); this records only."""
        e = next((d for d in self.plan['days'] if d['day'] == day), None)
        if e is None or not e.get('classroom_arm'):
            return dict(status='refused', reason='no classroom-arm day %s in the plan' % day)
        x = self.receipt('exchange', day) or {}
        if not (x.get('status') in ('done', 'reused') and x.get('frankie_view')):
            return dict(status='refused', reason='the day\'s exchange is %s' % (x.get('status') or 'not run'))
        sha = x.get('exchange_sha256') or sha256_file(Path(x['frankie_view']))
        base = self.voice_dispatch_dir(day, sha)
        attempts = self.voice_attempts(base)
        latest = attempts[-1] if attempts else None
        if latest is None or not latest['admission']:
            return dict(status='refused', reason='no admitted attempt stands under %s; nothing to return' % base)
        archive = Path(archive)
        if not archive.is_absolute() or not archive.is_file() or any(q.is_symlink() for q in (archive, *archive.parents)):
            return dict(status='refused', reason='the archive must be an existing owner-local absolute, symlink-free file: %s' % archive)
        if not str(archive).startswith(str(RUNS) + '/'):
            return dict(status='refused', reason='the archive must be downloaded under %s (owner-local evidence)' % RUNS)
        witness = file_pin(archive)
        if not re.fullmatch('[0-9a-f]{64}', str(archive_sha256)) or witness['sha256'] != archive_sha256:
            return dict(status='refused', reason='the archive sha256 %s differs from the given %s (the run\'s runner-state.json '
                                                 'names the exact one)' % (witness['sha256'], archive_sha256))
        record = dict(schema=self.VOICE_RETURN_SCHEMA, intent=latest['admission']['intent'], run=self.plan['run'], day=day,
                      attempt=latest['name'], admission=latest['admission_pin'],
                      github_run_id=latest['admission']['github_run_id'], github_run_attempt=latest['admission']['github_run_attempt'],
                      conclusion=conclusion, concluded=True, archive=witness, returned_by=by,
                      recorded_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        path = Path(latest['directory']) / 'returned.json'
        if path.is_file():
            retained = json.loads(path.read_bytes())
            if any(retained.get(k) != record.get(k) for k in ('attempt', 'github_run_id', 'github_run_attempt', 'conclusion', 'archive')):
                return dict(status='refused', reason='attempt %s already records another return (%s, archive %s); never rewritten' % (
                    latest['name'], retained.get('conclusion'), (retained.get('archive') or {}).get('sha256', '')[:12]))
            return dict(status='recorded', attempt=latest['name'], returned=file_pin(path), reason='already recorded')
        self.cores.write_json(path, record, exclusive=True)
        importer = ('python deploy/aws/box/frankie_box_granite_runner.py import --exchange %s --exchange-sha256 %s --commit %s '
                    '--archive %s --archive-sha256 %s --out %s' % (x['frankie_view'], sha, latest['admission']['commit'], archive,
                                                                   archive_sha256, Path(latest['directory']) / 'intake'))
        return dict(status='recorded', attempt=latest['name'], returned=file_pin(path), conclusion=conclusion,
                    next=importer if conclusion == 'success' else
                    'a continuation is a new attempt: dispatch by hand with prior_state = this archive, then voice-dispatched')

    def school(self, e):
        day = e['day']
        if not e['classroom_arm']:
            return self.record('school', day, 'skipped', reason='not a classroom-arm day')
        if day == MONDAY:
            return self.record('school', day, 'skipped', reason='Monday 20211004 is out of the school (it starts with the '
                                                                'first school day)')
        brain = Path(self.plan.get('brain') or str(BRAIN))
        # the checked school chain (Codex's frankie_box_school_knowledge.retained_school): the indexed original and its
        # explicit checked successors; a corrupt chain raises (never read as absence). A complete chain of THIS run is
        # reused as its latest checked school; one that requires a successor goes through the school child, whose CLI
        # runs the owner operation (the original index row is never rewritten here); another run's same-day school
        # is never reused
        import frankie_box_school_knowledge as SK
        retained = SK.retained_school(str(brain), day)
        if retained is not None and retained['content'].get('run') != self.plan['run']:
            return self.record('school', day, 'refused', school_sha256=retained['original']['sha256'],
                               reason='the day\'s indexed school belongs to run %s, not this run; another run\'s same-day '
                                      'school is never reused' % retained['content'].get('run'))
        if retained is not None and retained['status'] == 'complete':
            return self.record('school', day, 'reused', file=retained['original']['path'],
                               row=dict(retained['row'], **retained['original']), school_sha256=retained['original']['sha256'],
                               corrections=retained['corrections'],
                               # the one-day inspection (frankie_box_workflow_inspection.py): what this reuse received
                               # (the indexed original row and the chain), what it reused and what it recorded
                               inspection=dict(inputs=dict(brain=str(brain), index_row=retained['row'],
                                                           indexed_original=dict(path=str(brain / 'school' / retained['row']['file']),
                                                                                 bytes=retained['row'].get('bytes'),
                                                                                 sha256=retained['row'].get('sha256')),
                                                           chain='retained_school: the indexed original and its explicit checked '
                                                                 'successors (school_transition records only)'),
                                               use=dict(reused='the latest checked complete school of the chain',
                                                        superseded_links=len(retained['corrections']),
                                                        superseded=[c.get('sha256') for c in retained['corrections']],
                                                        corrections_carried=len(retained['corrections']),
                                                        not_run='no school child, no model call, no index row rewritten'),
                                               outputs=dict(file=retained['original']['path'], school_sha256=retained['original']['sha256'],
                                                            bytes=retained['original'].get('bytes'),
                                                            report_number=retained['row'].get('report_number'),
                                                            school_day=retained['row'].get('school_day'))))
        c = self.receipt('classroom', day)
        if not (c and c['status'] in ('done', 'reused', 'refused')):
            return self.record('school', day, 'waiting', reason='the day\'s classroom step is %s' % (
                (c or {}).get('status') or 'not run'))
        x = self.receipt('exchange', day)
        if not (x and x['status'] in ('done', 'reused', 'skipped', 'not_run')):
            return self.record('school', day, 'waiting', reason='the day\'s exchange is %s (the school file is written '
                                                                'once, with it)' % ((x or {}).get('status') or 'not run'))
        if retained is not None:
            # requires_successor: the owner operation needs the completed corrected meeting when the school's discussion
            # is bound to a replaced exchange (frankie_box_school_knowledge._successor_projection); until the day's voice
            # is done or reused on the current exchange the successor waits, never a failed child
            import frankie_box_experiment_review as REVIEW
            import frankie_box_lane_state as LS
            records = REVIEW.corrections(LS.knowledge_roots(str(brain)))
            meetings = [i for i in retained['content']['sections']['exchange']['items'] if i['name'] == 'discussion (meeting)']
            needs_meeting = any(((i.get('content') or {}).get('exchange') or {}).get('sha256') in records for i in meetings)
            v = self.receipt('voice', day) or {}
            if needs_meeting and v.get('status') not in ('done', 'reused'):
                return self.record('school', day, 'waiting', school_sha256=retained['original']['sha256'],
                                   reason='the checked school successor awaits the completed corrected meeting; the day\'s '
                                          'voice is %s' % (v.get('status') or 'not run'))
        classroom = c.get('classroom') or (str(Path(self.receipt('root', day)['calculations']) / 'work' / 'classroom')
                                           if (self.receipt('root', day) or {}).get('calculations') else None)
        if not classroom:
            return self.record('school', day, 'failed', reason='no classroom directory named for the day')
        try:
            number = self.report_number(e)
        except SystemExit as error:     # the numbering rule refused (reserve_number: a day is never renumbered, a number
            if error.code == 75:        # never given to two days): the step's own refusal, visible on its receipt; never an
                raise                   # exit that escapes guarded() and the successor drain (both catch Exception only)
            return self.record('school', day, 'refused', reason='the day\'s report number could not be reserved as its '
                                                                'school day: %s' % error)
        env = dict(DAY=day, RUN=self.plan['run'], REPORT_NUMBER=number, CLASSROOM=classroom, BRAIN=brain)
        if self.school_day is not None:
            env['SCHOOL_DAY'] = self.school_day        # the class line's school-day number (= REPORT_NUMBER), in the row
        if x['status'] in ('done', 'reused'):
            env['EXCHANGE_VIEW'] = x['frankie_view']
        else:
            env['EXCHANGE_LISTED'] = 'the exchange was %s: %s' % (x['status'], x.get('reason'))
        mine = LESSONS_ROOT / 'frankie' / ('%s-frankie.json' % day)
        if mine.is_file():
            env['LESSONS'] = mine
        base, source, why = self.day_rows(e)
        if base is None and why:
            return self.record('school', day, 'refused' if why.startswith('refused') else 'waiting', reason=why)
        if base is not None and source != 'launch run':
            env['TEACHER_ROWS'] = base
        code, log = self.child('school', day, 'frankie_box_school_knowledge.sh', env)
        saved = self.child_saved('school', day, code, log, report_number=number)
        if saved:
            return saved
        try:
            lines = [z for z in Path(log).read_text(encoding='utf-8', errors='replace').splitlines() if z.strip()]
            r = json.loads(lines[-1]) if lines else None
        except (OSError, ValueError):
            r = None
        if code != 0 or not (isinstance(r, dict) and r.get('schema') == SCHOOL_RECEIPT_SCHEMA):
            return self.record('school', day, 'failed', exit_code=code, log=log, reason='no school receipt after the step '
                                                                                        '(its log names why)')
        return self.record('school', day, 'done', exit_code=code, log=log, file=r['file'], row=r['row'],
                           school_sha256=(r.get('row') or {}).get('sha256'), reused_by_child=r.get('reused'),
                           sections=r.get('sections'), missing=r.get('missing'), withheld=r.get('withheld'),
                           successor=r.get('successor'), correction=r.get('correction'), corrections=r.get('corrections'),
                           # the child's own lists and piece report (school_recovery, 2026-10-07: FRANKIE_SCHOOL_KNOWLEDGE_RECEIPT_V1
                           # missing_listed / withheld_listed / workflow_report), carried as given for the one-day reporter
                           missing_listed=r.get('missing_listed'), withheld_listed=r.get('withheld_listed'),
                           workflow_report=r.get('workflow_report'),
                           # the one-day inspection (frankie_box_workflow_inspection.py): what the school child received,
                           # how it used it (a new school, the owner successor operation, or the child's own reuse) and what
                           # it produced; operator review only, never knowledge or a gate
                           inspection=dict(inputs=dict(env={k: str(v) for k, v in env.items()},
                                                       teacher_rows=dict(path=str(base) if base else None, source=source, listed=why),
                                                       exchange=dict(status=x['status'], view=x.get('frankie_view'),
                                                                     sha256=x.get('exchange_sha256')),
                                                       lessons=str(mine) if mine.is_file() else 'none: no FRANKIE_LESSONS_V1 of the day',
                                                       chain=('requires_successor: the indexed school %s has a replaced source' %
                                                              retained['original']['sha256'][:12]) if retained else
                                                             'none indexed: a new school is written once'),
                                           use=dict(school=('the owner successor operation (frankie_box_school_knowledge.'
                                                            'rebuild_successor): only checked copied sources and their '
                                                            'projections change; the original file and index row stay')
                                                           if r.get('successor') else
                                                           ('the child reused the indexed school (same bytes)' if r.get('reused')
                                                            else 'a new school written and indexed'),
                                                    corrections_carried=len(r.get('corrections') or []),
                                                    sections=r.get('sections'), missing=r.get('missing'), withheld=r.get('withheld')),
                                           outputs=dict(file=r['file'], school_sha256=(r.get('row') or {}).get('sha256'),
                                                        bytes=(r.get('row') or {}).get('bytes'), report_number=number,
                                                        school_day=self.school_day, successor=r.get('successor'),
                                                        correction=r.get('correction'), exit_code=code)))

    def recover_school(self, day, recovery_intent):
        """The owner's recovery of a day's school under a checked source successor (successor_dispatch.rebuild_dependents
        -> 'waiting_school', called from its drain under the drain lock, on this same owner/day/held lane): the existing
        voice then school steps, with the nested successor drain skipped for exactly this recovery (the caller holds
        drain.lock). Save, currentness and held-slot checks stay the steps' own. 'complete' only when the school stage ended
        done/reused on the checked successor; a refused or still-pending meeting leaves it 'waiting' (never a completed
        school, requeue or invented discussion); a failed voice/school child or a raised error is 'failed' = the stage's
        own failed receipt (visible, separate from a wait, retried by the ordinary path, never the operation's
        failure.json). Returns status, stage, recovery_intent, reason and inspection={inputs, use, outputs} (receipt
        paths and statuses only, never receipt bodies). No second drain, scheduler or model runtime."""
        e = next((x for x in self.plan['days'] if x['day'] == day), None)
        if e is None or not e.get('classroom_arm'):
            return dict(status='refused', reason='no classroom-arm day %s in the plan' % day, recovery_intent=recovery_intent)
        if self.save_requested():
            return dict(status='saved', reason='save requested on the owner; the recovery resumes with the day',
                        recovery_intent=recovery_intent)
        self._school_recovery.add(day)
        # Every drain of the day calls this (child boundaries, the class worker's keep(), close_day's one drain), so a child
        # is dispatched here AT MOST ONCE PER INVALIDATION, never once per call: only an absent voice or the
        # invalidation's own blocking wait runs the meeting child; a failed voice or school (any child failure) is the
        # step's own failure, retried by the ordinary path (guarded() on the next start, the class worker's next poll),
        # and a non-blocking refused meeting is the owner's decision. Re-dispatching per call is the unbounded
        # model-child dispatch the fifth pass closed; repeated drains (keep(), every boundary) would reach it again. A drain
        # call itself runs at most one 'complete' recovery per operation (successor_dispatch, second review F7).
        use = dict(voice='not dispatched here', school='not dispatched here')
        paths = dict(voice=self.receipt_path('voice', day).as_posix(), school=self.receipt_path('school', day).as_posix())
        stage = 'voice'
        try:
            v = self.receipt('voice', day) or {}
            if not v or (v.get('status') == 'waiting' and not v.get('non_blocking')):
                use['voice'] = 'the meeting child dispatched (voice was %s)' % (v.get('status') or 'absent')
                v = self.voice(e) or {}
            elif v.get('status') == 'failed':
                use['voice'] = 'failed voice not re-dispatched by the recovery; the next start or class poll retries it'
            elif v.get('status') == 'waiting':
                use['voice'] = 'non-blocking refused meeting not re-dispatched; the owner\'s decision changes it'
            else:
                use['voice'] = 'the %s meeting used as it is' % v.get('status')
            if v.get('status') not in ('done', 'reused', 'skipped'):
                return dict(status='failed' if v.get('status') == 'failed' else 'waiting', stage='voice',
                            inspection=dict(inputs=dict(recovery_intent=recovery_intent, **paths), use=use,
                                            outputs=dict(voice_status=v.get('status'),
                                                         school_status=(self.receipt('school', day) or {}).get('status'))),
                            recovery_intent=recovery_intent, voice_status=v.get('status'),
                            reason='the corrected meeting is %s: %s' % (v.get('status'), v.get('reason')))
            stage = 'school'
            s = self.receipt('school', day) or {}
            if s.get('status') == 'failed':
                use['school'] = 'failed school not re-dispatched by the recovery; the next start or class poll retries it'
                return dict(status='failed', stage='school',
                            inspection=dict(inputs=dict(recovery_intent=recovery_intent, **paths), use=use,
                                            outputs=dict(voice_status=v.get('status'), school_status='failed')),
                            recovery_intent=recovery_intent, school_status='failed',
                            reason='the school step failed: %s' % s.get('reason'))
            use['school'] = 'the school step run on the checked chain (school was %s)' % (s.get('status') or 'absent')
            s = self.school(e) or {}
            return dict(status='complete' if done_status(s) else (s.get('status') or 'waiting'), stage='school',
                        inspection=dict(inputs=dict(recovery_intent=recovery_intent, **paths), use=use,
                                        outputs=dict(voice_status=v.get('status'), school_status=s.get('status'),
                                                     school_sha256=s.get('school_sha256'), successor=s.get('successor'),
                                                     correction=s.get('correction'), corrections=s.get('corrections'))),
                        recovery_intent=recovery_intent, school_status=s.get('status'), reason=s.get('reason'))
        except Exception as error:      # noqa: BLE001 - the stage's own failure, recorded as guarded() records it:
            # visible on the day's receipt and separate from a wait (a corrupt school chain, a changed exchange at the
            # child boundary); never the operation's failure.json and never relabelled as waiting
            r = self.record(stage, day, 'failed', reason='%s: %s (in the owner school recovery)' % (type(error).__name__, error))
            return dict(status='failed', stage=stage,
                        inspection=dict(inputs=dict(recovery_intent=recovery_intent, **paths), use=use,
                                        outputs={stage + '_status': 'failed'}),
                        recovery_intent=recovery_intent, reason=r['reason'])
        finally:
            self._school_recovery.discard(day)

    def jev(self, e):
        """Jev's day: an ordinary stage of the day, run inside the day's held booking on the WHOLE lane like teacher,
        classroom, search and the exchange (Greg, 2026-10-07 night: "just have jev operate in that box like everyone else";
        32 CPUs on a 32-CPU day), llama-server threads from frankie_box_jev_cpu.JEV_THREADS (32, clamped to the lane, pinned
        in physical-core order), every other runtime row from Granite's shared definition (frankie_box_jev_cpu.bind_runtime);
        no box, host or lane of his own; the lane's CPU line and the threads are on this record (cpu_booking, lane_threads). The
        immutable JEV_CPU_REQUEST_V1 is persisted under the day BEFORE the first dispatch and reused byte for byte (a retained
        request that binds another identity is refused, never re-minted; a REBOOK'd day runs the explicit successor chain);
        the child runs inside the day's held booking with the day's own save marker; its receipt or status is checked
        against the request chain before any status is recorded (an exit code alone is nothing). A shared runtime that is
        absent or differs from its pins is waiting, never skipped or done. The existing knowledge boundary runs before the
        dispatch (child) and again once both local deliveries are read back."""
        day = e['day']
        remote = self.remote_stage('jev', day)
        if remote is not None:
            return remote
        if not e['classroom_arm']:
            return self.record('jev', day, 'skipped', reason='not a classroom-arm day (Jev sits in on the arm days only)')
        if e.get('role') != 'discovery':
            return self.record('jev', day, 'waiting', reason='a %s day has no authorized Jev route (the CPU route takes '
                                                             'discovery classroom-arm days only)' % e.get('role'))
        done = self.jev_done_receipt(e)
        if done is not None:
            # F1 (second review): a done Jev is returned unchanged, never rebuilt on a later booking (a retried finish
            # binds a new booking; rebuilding compared slot_booking/cpus and relabelled completed evidence as refused)
            return done
        c = self.receipt('classroom', day)
        if not (c and c['status'] in ('done', 'reused') and c.get('classroom')):
            return self.record('jev', day, 'waiting', reason='the day\'s classroom is not complete yet (its material is '
                                                             'written by the classroom step)')
        producer = Path(c['classroom']) / 'receipt.json'      # the classroom PRODUCER's receipt, never this step's record
        if not producer.is_file():
            return self.record('jev', day, 'failed', reason='no classroom producer receipt at %s' % producer)
        s = self.receipt('search', day) or {}
        if s.get('status') == 'not_run':
            # B5 (2026-10-07): no causal axis on this day, so no search to test Jev's claims on: the missing operand blocks
            # this equation only; listed with the search's own reason and the day goes on (never a permanent wait)
            return self.record('jev', day, 'not_run', reason='the owning day\'s search is not_run (%s): Jev has no search of '
                                                            'the day to test his claims on; listed' % s.get('reason'))
        manifest = Path(s['target']) / 'MANIFEST.json' if s.get('status') in ('done', 'reused') and s.get('target') else None
        if manifest is None or not manifest.is_file():
            return self.record('jev', day, 'waiting', reason='the owning day\'s search is %s (Jev tests his claims on it)'
                               % (s.get('status') or 'not run'))
        # Greg, 2026-10-07: Jev uses Granite's settings, ALL of them (one pinned runtime on the box: Granite 4.2 3B Q4_K_M
        # under llama.cpp b11440 at the paths the meeting's gate expects), so he improves with it. Run.jev passes no
        # separate binary/model/budget: the request binds the shared runtime definition (the staged GRANITE_MEETING_RUNTIME_V1
        # config, the install's provenance, the gated paths) and the helper reads every row from it; a plan's older
        # jev_runtime (JEV_CPU_RUNTIME_V1) is recorded as superseded and NOT used.
        shared = self.shared_runtime()
        superseded = self.plan.get('jev_runtime') or (str(self.dir / 'jev-runtime.json') if (self.dir / 'jev-runtime.json').is_file() else None)
        if shared['status'] != 'ready':
            return self.record('jev', day, 'waiting', shared_runtime=shared, superseded_jev_runtime=superseded,
                               reason='the one pinned model runtime (Granite 4.2 3B Q4_K_M under llama.cpp b11440, shared with the '
                                      'meeting) is not ready on this box: %s; a missing runtime is waiting, never skipped or borrowed'
                                      % '; '.join(shared['reasons'])[:900])
        runtime = (shared['config'] or {}).get('path')
        jev_brain = Path(self.plan.get('jev_brain') or str(JEV_BRAIN))
        for label, p in (('runtime config', Path(runtime)), ('binary', Path(shared['binary'])), ('model', Path(shared['model'])),
                         ('jev_brain', jev_brain)):
            if not p.is_absolute() or any(q.is_symlink() for q in (p, *p.parents)):
                # the helper refuses a relative or symlinked path, and the request is written once: refused BEFORE it
                # is written (a corrected install is the setup script's; a corrected brain path is a new run)
                return self.record('jev', day, 'refused', reason='Jev\'s %s path must be absolute and symlink-free: %s' % (label, p))
        marker = self.stop_marker
        if not marker:
            return self.record('jev', day, 'waiting', reason='no day-bound save marker on this Run (the owner binding or '
                                                             'FRANKIE_LANE_STOP_FILE): Jev binds the exact marker')
        booking = getattr(self, 'slot_booking', None)
        held, why = self.cores.held_booking(booking) if booking else (None, 'no held day booking on this Run')
        if held is None or held.get('run') != self.plan['run'] or held.get('day') != day or \
                len(held.get('cpus') or []) not in self.cores.DAY_RUN_SIZES:
            return self.record('jev', day, 'waiting', reason='Jev needs the day\'s live held day-run booking (%s CPUs): %s' % (
                '/'.join(str(n) for n in self.cores.DAY_RUN_SIZES), why))
        attempt = self.owned_attempt or os.environ.get('FRANKIE_LANE_ATTEMPT') or ''
        if not attempt:
            root = self.receipt('root', day) or {}
            attempt = Path(root['calculations']).name if root.get('calculations') else ''
        if not re.fullmatch(re.escape('%s-%s-a' % (self.plan['run'], day)) + r'[0-9]+', attempt):
            return self.record('jev', day, 'waiting', reason='the original ROOT attempt of the day is not established on '
                                                             'this Run (%r)' % attempt)
        stamp = jev_stamp(self.plan, e)
        number = self.report_number(e)
        brain = Path(self.plan.get('brain') or str(BRAIN))
        out = self.dir / 'days' / day / 'jev' / stamp
        owner = self.owner or dict(schema='FRANKIE_LANE_OWNER_V1', host=os.uname().nodename, attempt=attempt,
                                   marker=str(marker), lane_owner=os.environ.get('FRANKIE_LANE_OWNER'))
        request = dict(schema='JEV_CPU_REQUEST_V1', run=self.plan['run'], day=day, day_role='discovery', stamp=stamp,
                       attempt=attempt, owner=owner, host=os.uname().nodename, plan_sha256=plan_digest(self.plan),
                       slot_booking=booking, cpus=list(held['cpus']),      # the day's lane (identity); Jev runs on all of
                       # it (frankie_box_cores cmd_run_inside: taskset of the held booking)
                       source=dict(commit=self.commit, code_root=str(self.code_root)), save_marker=str(marker),
                       output=str(out), brain=str(brain), jev_brain=str(jev_brain), report_number=number,
                       classroom_receipt=file_pin(producer), search=file_pin(manifest), runtime=file_pin(Path(runtime)),
                       # the shared runtime definition Jev binds to (the same install the meeting runs on): the config
                       # pin above, the install's provenance pin, the gated binary/model paths; no separate pin set
                       shared_runtime=dict(schema=SHARED_RUNTIME_SCHEMA, provenance=shared['provenance'], binary=shared['binary'],
                                           model=shared['model'], superseded_jev_runtime=superseded))
        # optional (efficiency): the exchange's retained read of the same shared market source at the teachers' cutoff;
        # the helper reuses it only when its identity and scope are this cutoff's (else a fresh read, recorded). Listed
        # when the exchange has not written it yet (in the class order Jev runs before the exchange).
        exchange_context = self.dir / 'exchange' / day / 'shared-market-context.json'
        context_read = self.jev_context_read(e, exchange_context)
        if exchange_context.is_file() and not exchange_context.is_symlink():
            request['shared_market_context'] = file_pin(exchange_context)
        path = self.dir / 'days' / day / ('jev-request-%s.json' % stamp)
        if path.is_file():
            retained = json.loads(path.read_bytes())
            # 2026-10-09 (Greg): `source` (commit, code root) is RECORDED on the request, NEVER COMPARED: a resumed day on
            # a newer staged checkout runs its retained Jev request (the helper then runs on this checkout, recorded)
            bound = ('schema', 'run', 'day', 'day_role', 'stamp', 'attempt', 'host', 'plan_sha256', 'output',
                     'brain', 'jev_brain', 'report_number', 'slot_booking', 'cpus')
            differ = [k for k in bound if retained.get(k) != request.get(k)]
            if not differ and retained.get('source') != request.get('source'):
                self.log('jev %s: the retained request was made on %s; this step runs on %s (recorded, never compared)' % (
                    day, (retained.get('source') or {}).get('commit'), self.commit))
            if differ:
                # a REBOOK'd day (ACTION=resume REBOOK=on: the same attempt on another free 16-CPU booking) runs its Jev
                # on the explicit rebook successor of the retained request; anything else differing is refused as before
                successor, why = self.jev_rebooked(path, request, differ)
                if successor is None:
                    # X6 (exchange owner, stacks pass 2026-10-07): a RESTAGE differs in `source` (commit, code root) alone
                    # while every bound content is equal (identity is content, not location: experiment_root.content_rebinds
                    # over the bound keys less source, and the pinned inputs' sha256). MEASURED and named on the refusal;
                    # not yet accepted here, because the helper binds source.commit itself (frankie_box_jev_cpu.py: the
                    # held booking's commit, MARKETS_SHA, bind_owner's retained identity); the accepting form is a joint
                    # change (a .sourceN successor the helper's request_chain follows). Old requests load unchanged.
                    source_rebind = self.jev_source_rebind(retained, request, bound, differ)
                    return self.record('jev', day, 'refused', request=str(path), differs=differ, rebook=why,
                                       source_rebind=source_rebind,
                                       reason='the retained Jev request binds another %s; the same request resumes byte for '
                                              'byte or an explicit owner recovery decides (never re-minted); REBOOK successor: %s%s'
                                              % (', '.join(differ), why,
                                                 '; a restage with equal bound content (source alone differs): accepted only '
                                                 'with the helper\'s source binding (X6, listed)' if source_rebind.get('content_equal') else ''))
                path, request = successor
                out = Path(request['output'])
        else:
            self.cores.write_json(path, request, exclusive=True)      # create-only: the request is written once
        # the helper pins the request as given (status.json) and resolved (owner.json / receipt.json): both are this file;
        # a REBOOK successor that resumes retained progress keeps the ORIGINAL owner (its request pin is an earlier link
        # of the chain), so every link's exact pin binds too
        request_pins = [file_pin(path)] + ([file_pin(path.resolve())] if path.resolve() != path else [])
        link = request.get('rebook')
        while isinstance(link, dict) and isinstance(link.get('of'), dict):
            request_pins.append(link['of'])
            try:
                link = json.loads(Path(link['of']['path']).read_bytes()).get('rebook')
            except (OSError, ValueError):
                break
        status_path, receipt_path = out / 'status.json', out / 'receipt.json'

        def read(p):
            try:
                return json.loads(p.read_bytes()) if p.is_file() else None
            except ValueError:
                return None

        def bound_receipt(doc):
            return isinstance(doc, dict) and doc.get('schema') == 'JEV_CPU_RECEIPT_V1' and \
                (doc.get('owner') or {}).get('request_pin') in request_pins

        def bound_status(doc):
            return isinstance(doc, dict) and doc.get('schema') == 'JEV_CPU_STATUS_V1' and doc.get('request') in request_pins
        status, receipt = read(status_path), read(receipt_path)
        if bound_receipt(receipt) and receipt.get('status') != 'done' and receipt.get('pending'):
            # a complete receipt whose dispositions await the owner: nothing but that decision changes it; not re-run
            return self.record('jev', day, 'waiting', request=str(path), receipt=str(receipt_path), stamp=stamp,
                               pending=receipt.get('pending'), report=receipt.get('report'),
                               reason='Jev\'s receipt awaits the owner\'s disposition: %s' % '; '.join(receipt.get('pending') or []))
        # Greg, 2026-10-07 night (supersedes "none is retried or erased"): an interrupted Jev call is RE-DONE. A retained
        # state listing unresolved calls is re-dispatched from its saved inputs; the helper (sit_in.recorded_chat) stamps
        # the interrupted intent unknown_completion, lists it in state interrupted_calls and re-sends the byte-identical
        # request; nothing is counted answered until it completes. (stacks pass, the Jev owner's scoped edit)
        redispatched_unresolved = (status['unresolved_calls'] if not receipt_path.is_file() and bound_status(status)
                                   and status.get('unresolved_calls') else None)
        # the same LLAMA_SERVER / GGUF_MODEL the meeting child gets: one runtime, one install (the helper reads the request's
        # shared_runtime binding; the environment names the same paths for its wrapper)
        code, log = self.child('jev', day, 'frankie_box_jev_cpu.sh', dict(JEV_REQUEST=path, LLAMA_SERVER=shared['binary'],
                                                                           GGUF_MODEL=shared['model']))
        receipt, status = read(receipt_path), read(status_path)
        slot = self._cpu.get(('jev', day))        # the ledger's CPU_BOOKING line: inside the held lane, its CPUs
        lane_threads = (receipt or {}).get('lane_threads') if bound_receipt(receipt) else None
        fields = dict(exit_code=code, log=log, request=str(path), stamp=stamp, output=str(out), report_number=number,
                      redispatched_unresolved=redispatched_unresolved,
                      request_pins=request_pins, rebook=request.get('rebook'), cpu_booking=slot,
                      lane_cpus=list(held['cpus']), lane_threads=lane_threads or
                      'not recorded: no receipt bound to the request on this attempt (the helper writes it with its receipt)',
                      # the one-day inspection (frankie_box_workflow_inspection.py): what this caller gave the helper, how
                      # the answer was bound, what came back; operator review only, never knowledge or a gate
                      inspection=dict(inputs=dict(request=request_pins, classroom_receipt=request['classroom_receipt'],
                                                  search_manifest=request['search'], runtime=request['runtime'],
                                                  attempt=attempt, booking=booking, cpus=request['cpus'], marker=str(marker),
                                                  brain=str(brain), jev_brain=str(jev_brain), report_number=number,
                                                  shared_market_context=request.get('shared_market_context') or
                                                  'not supplied: the exchange has not retained its read yet (the helper reads)',
                                                  shared_market_context_read=context_read),
                                      use=dict(exit_code=code, receipt_bound=bound_receipt(receipt), status_bound=bound_status(status),
                                               cpu_booking=(slot or {}).get('line') or 'no booking line (the child did not reach the ledger)',
                                               lane_cpus=list(held['cpus']),
                                               lane_threads=lane_threads or 'not recorded (no bound receipt on this attempt)',
                                               binding='a receipt counts only with owner.request_pin in request_pins; a status '
                                                       'only with request in request_pins; an exit code alone is nothing'),
                                      outputs=dict(receipt=str(receipt_path) if receipt_path.is_file() else None,
                                                   status_file=str(status_path) if status_path.is_file() else None,
                                                   receipt_status=(receipt or {}).get('status') if bound_receipt(receipt) else None,
                                                   child_status=(status or {}).get('status') if bound_status(status) else None)))
        if bound_receipt(receipt):
            fields.update(receipt=str(receipt_path), receipt_status=receipt.get('status'), claims_seal=receipt.get('claims_seal'),
                          scientific_result=receipt.get('scientific_result'), deliveries=receipt.get('deliveries'),
                          report=receipt.get('report'), client_receipt=receipt.get('client_receipt'),
                          pending=receipt.get('pending'), unparsed=receipt.get('unparsed'))
            if receipt.get('deliveries'):
                # both local deliveries read back (Jev's lesson reader, Frankie's jev-tested publication): the existing
                # knowledge boundary runs now whatever the comparison disposition; a pending one keeps the stage waiting
                # and never erases the delivered evidence
                import frankie_box_lane_state as LS
                fields['knowledge_after_delivery'] = LS.boundary(day, 'jev', brain=str(brain))
            if code == 0 and receipt.get('status') == 'done':
                return self.record('jev', day, 'done', **fields)
            return self.record('jev', day, 'waiting', reason='Jev\'s receipt is %s (exit %d): %s' % (
                receipt.get('status'), code, '; '.join(receipt.get('pending') or []) or 'see the receipt'), **fields)
        if bound_status(status):
            # status_file, never 'status': record() takes the stage status positionally (a duplicate keyword raised
            # TypeError here, which classed the day failed instead of waiting)
            fields.update(status_file=str(status_path), child=status.get('child'), unresolved_calls=status.get('unresolved_calls'),
                          child_reason=status.get('reason'))
            # exit 75 on the day's standing marker never reaches here: child() raised SystemExit(75) on it and the day's
            # own save classifies the thread (_thread_end); a 75 without a standing marker (the helper's signal path) is
            # waiting with the child's reason, never recorded as saved
            return self.record('jev', day, 'waiting' if code in (5, 75) else 'failed',
                               reason='Jev\'s status is %s (exit %d): %s' % (status.get('status'), code, status.get('reason')),
                               **fields)
        return self.record('jev', day, 'waiting' if code in (5, 75) else 'failed',
                           reason='exit %d without a receipt or status bound to the request %s' % (code, path), **fields)

    def jev_context_read(self, e, context):
        """The shared market picture at the teachers' cutoff, read ONCE on the day's held lane before Jev (exchange owner,
        EXCHANGE_CONTEXT_ONLY=1, frankie_box_experiment_exchange.context_only): the same reader, pins and cutoff as the
        exchange, retained as exchange/<day>/shared-market-context.json, the file the exchange's own read and Jev's helper
        reuse. Context-only writes no receipt.json, so the later exchange step runs in full. An efficiency only: whatever
        happens here, Jev's helper reads for itself when no retained file is there (as before); the outcome is listed on
        the Jev record and never decides the stage. Its log/heartbeat key is '<day>-context' (logs/<day>-context-
        exchange.log; heartbeat lines keyed '<day>-context'), so the real exchange's <day>-exchange.log is never touched.
        Returns one dict: status reused | retained | retained_nonzero_exit | not_read | failed, with the reason or pin."""
        day = e['day']
        target = context.parent
        if context.is_file() and not context.is_symlink():
            return dict(status='reused', shared_market_context=file_pin(context),
                        reason='already retained (an earlier context read or the exchange itself)')
        x = self.receipt('exchange', day) or {}
        if (target / 'receipt.json').is_file() or x.get('status') in ('done', 'reused'):
            # the exchange is complete without a retained read (no teacher rows then): its directory is not written to
            return dict(status='not_read', reason='the day\'s exchange is already complete (%s) with no retained context'
                                                  % (x.get('status') or 'receipt.json present'))
        rows, why = self.rows_file(e)
        if rows is None:
            return dict(status='not_read', reason='no teacher Dipole rows for the cutoff read: %s' % why)
        env = dict(DAY=day, RUN=self.plan['run'], LESSONS='', OUT_DIR=target, BRAIN=self.plan.get('brain') or str(BRAIN),
                   SEARCH_DIR=SEARCH / day / ('cycle-' + CYCLE) / 'discovery', TEACHER_ROWS=rows, EXCHANGE_CONTEXT_ONLY='1')
        key = '%s-context' % day
        try:
            code, log = self.child('exchange', key, 'frankie_box_experiment_exchange.sh', env)
        except ValueError as error:
            # child()'s own boundary checks (teacher inputs not current, a remote lane): nothing ran; Jev reads for itself
            return dict(status='not_read', reason='the cutoff read was not started: %s' % error, teacher_rows=str(rows))
        cpu = self._cpu.get(('exchange', key))
        if context.is_file() and not context.is_symlink():
            # the request pins whatever file is retained there (the exchange's own reader wrote it); a nonzero exit
            # beside it is listed, never hidden
            return dict(status='retained' if code == 0 else 'retained_nonzero_exit', exit_code=code, log=log,
                        teacher_rows=str(rows), cpu_booking=cpu, shared_market_context=file_pin(context))
        return dict(status='failed', exit_code=code, log=log, teacher_rows=str(rows), cpu_booking=cpu,
                    reason='no retained shared-market-context.json after the cutoff read (exit %s; its log names why); '
                           'Jev\'s helper reads for itself' % code)

    def jev_done_receipt(self, e):
        """The day's existing 'done' jev receipt when it still stands on its own evidence, else None. It stands when its
        request is this day's retained request (days/<day>/jev-request-<stamp>.json or one of its .rebookN successors) and
        that request file's bytes still match the pin recorded on the receipt, and the helper's JEV_CPU_RECEIPT_V1 at the
        recorded path is 'done' with owner.request_pin among the recorded request_pins. Nothing is re-recorded: the receipt
        is returned as it is. Anything less (no receipt, not done, a changed request or helper receipt) is None and the
        ordinary path runs, with its own checks."""
        prior = self.receipt('jev', e['day'])
        if not (prior and prior.get('status') == 'done' and prior.get('request') and prior.get('receipt')):
            return None
        stem = 'jev-request-%s' % jev_stamp(self.plan, e)
        request = Path(prior['request'])
        if request.parent != self.dir / 'days' / e['day'] or not re.fullmatch(re.escape(stem) + r'(\.rebook[0-9]+)?\.json', request.name):
            return None
        pins = [p for p in prior.get('request_pins') or [] if isinstance(p, dict)]
        try:
            if not request.is_file() or file_pin(request) not in pins:
                return None
            helper = json.loads(Path(prior['receipt']).read_bytes())
        except (OSError, ValueError):
            return None
        if not (isinstance(helper, dict) and helper.get('schema') == 'JEV_CPU_RECEIPT_V1' and helper.get('status') == 'done'
                and (helper.get('owner') or {}).get('request_pin') in pins):
            return None
        return prior

    def jev_source_rebind(self, retained, request, bound, differ):
        """X6 (stacks pass 2026-10-07): the content identity of a retained Jev request against the one this checkout
        builds when they differ: content_equal when `source` (commit, code root) is the ONLY bound difference, every other
        bound key is equal (frankie_box_experiment_root.content_rebinds: equal, or checkout moves of equal-bytes
        witnesses only) and the pinned inputs (classroom receipt, search manifest, runtime config) carry the same sha256.
        Report only: the caller still refuses (the helper binds source.commit); nothing saved is rewritten."""
        out = dict(saved_source=retained.get('source'), current_source=request.get('source'), differs=differ,
                   content_equal=False)
        try:
            import frankie_box_experiment_root as XR
            moves = XR.content_rebinds({k: retained.get(k) for k in bound if k != 'source'},
                                       {k: request.get(k) for k in bound if k != 'source'})
        except Exception as error:  # noqa: BLE001 - a report only
            out['error'] = '%s: %s' % (type(error).__name__, error)
            return out
        pins = {k: ((retained.get(k) or {}).get('sha256'), (request.get(k) or {}).get('sha256'))
                for k in ('classroom_receipt', 'search', 'runtime')}
        out.update(bound_moves=moves, pins_equal={k: a == b and a is not None for k, (a, b) in pins.items()},
                   content_equal=(differ == ['source'] and moves is not None and all(a == b and a is not None for a, b in pins.values())))
        return out

    def jev_rebooked(self, original, request, differ):
        """The explicit REBOOK successor of a retained Jev request: ((path, request) to run, None) or (None, why).
        ACTION=resume REBOOK=on records on the owner binding the booking/CPUs it replaced (frankie_box_frankie_queue.
        resume_owner: owner.rebooked). The ORIGINAL request is never changed. The chain is jev-request-<stamp>.json, then
        .rebook1.json, .rebook2.json ...; the successor for the live booking is reused when it stands; else one is minted
        create-only ONLY when the retained request differs in booking/CPUs alone and the rebook decision names exactly the
        booking/CPUs the newest retained request bound. Its output: the newest request's own output when that holds Jev
        progress (state, claims, seal, status, receipt or runtime evidence): the helper (frankie_box_jev_cpu.request_chain /
        bind_owner) then RESUMES that progress under the retained original owner identity, nothing repeated or re-minted,
        the resume recorded beside it; else a fresh output beside the old one (<output>.rebook<n>), nothing to resume."""
        if set(differ) - {'slot_booking', 'cpus'}:
            return None, 'the request differs in %s, not in the booking/CPUs alone' % ', '.join(differ)
        decision = (self.owner or {}).get('rebooked')
        if not decision:
            return None, ('no REBOOK decision on the owner binding (ACTION=resume REBOOK=on, or the queue\'s retry of a waiting '
                          'finish, records one); the retained booking is required')
        chain = [original] + sorted((q for q in original.parent.glob(original.stem + '.rebook*.json')
                                     if re.fullmatch(re.escape(original.stem) + r'\.rebook[0-9]+\.json', q.name)),
                                    key=lambda q: int(re.search(r'\.rebook([0-9]+)\.json$', q.name).group(1)))
        newest_path = chain[-1]
        newest = json.loads(newest_path.read_bytes())
        if newest.get('slot_booking') == request['slot_booking'] and newest.get('cpus') == request['cpus']:
            return (newest_path, newest), None           # the successor for this booking stands already (reused byte for byte)
        # the decision replaced the newest request's booking: named as previous_booking/CPUs (ACTION=resume REBOOK=on), or
        # among held_bookings, every booking the SAME owner binding held (the queue's own retry of a waiting finish,
        # frankie_box_frankie_queue._rebook_owner; second review F1). A booking this owner never held stays refused.
        held = [(h.get('booking'), sorted(h.get('cpus') or [])) for h in decision.get('held_bookings') or [] if isinstance(h, dict)]
        if (newest.get('slot_booking'), sorted(newest.get('cpus') or [])) not in held and \
                (decision.get('previous_booking'), decision.get('previous_cpus')) != (newest.get('slot_booking'), newest.get('cpus')):
            return None, ('the REBOOK decision replaced booking %s (CPUs %s), not the newest retained request\'s %s (%s); the '
                          'chain is broken, an explicit owner decision is required' % (
                              decision.get('previous_booking'), decision.get('previous_cpus'), newest.get('slot_booking'), newest.get('cpus')))
        previous_out = Path(newest['output'])
        progress = [name for name in ('state.json', 'claims.json', 'claims-seal.json', 'status.json', 'receipt.json', 'runtime-evidence')
                    if (previous_out / name).exists()]
        n = len(chain)
        successor = dict(newest, slot_booking=request['slot_booking'], cpus=request['cpus'],
                         output=str(previous_out) if progress else '%s.rebook%d' % (newest['output'], n),
                         rebook=dict(n=n, of=file_pin(newest_path), previous_booking=newest.get('slot_booking'),
                                     previous_cpus=newest.get('cpus'), decision=decision,
                                     resumes=progress or None,
                                     rule='the original request stands unchanged; this successor binds the rebooked lane'
                                          + ('; it resumes the retained progress under the original owner' if progress else '')))
        path = original.with_name('%s.rebook%d.json' % (original.stem, n))
        self.cores.write_json(path, successor, exclusive=True)
        self.log('jev %s: REBOOK successor %s minted for booking %s (the original %s stands unchanged%s)' % (
            request['day'], path.name, request['slot_booking'], original.name,
            '; resumes %s' % ', '.join(progress) if progress else ''))
        return (path, successor), None

    def teacher(self, batch_key, entries):
        refused = {}                                     # day -> why its retained teacher knowledge is not taught again
        self.check_save()
        remote = {e['day']: self.remote_stage('teacher', e['day']) for e in entries if self.remote_root(e['day'])}
        if len(entries) == 1 and entries[0]['day'] in remote and batch_key == 'day-' + entries[0]['day']:
            return remote[entries[0]['day']]
        local = [e for e in entries if e['day'] not in remote]
        for e in local:
            self.root_on_disk(e)                         # session 9: a stale root step record never holds the teacher
        self._teacher_rederived = {e['day']: self._root_rederived[e['day']] for e in local
                                   if e['day'] in self._root_rederived} or None
        remote_waiting = [day for day, r in remote.items() if not done_status(r)]
        todo = [e for e in local if rows_of(e)[0] is None]
        brain_entries = {}
        policy = self.plan.get('shared_market_policy')
        root_waiting = {}                                # day -> why its retained or new teacher waits under the policy
        for e in local:
            rows, source = rows_of(e)
            if rows is not None:
                if policy:
                    state, why = self.shared_teacher_compatible(e, rows, source)
                    if state == 'refused':
                        refused[e['day']] = why        # a legacy or other-source teacher result never satisfies the policy
                        continue
                    if state == 'waiting':
                        root_waiting[e['day']] = why   # its ROOT or ingest is not complete here yet: not judged, not reused
                        continue
                rows_path, why = self.rows_file(e)
                if rows_path is None:
                    raise ValueError(why)
                try:
                    brain_entries[e['day']] = self.teacher_knowledge(e['day'], rows_path, source)
                except ValueError as error:
                    refused[e['day']] = str(error)     # the other days of the batch are not held back by this one
        if not todo:
            policy_refused = {d: w for d, w in refused.items() if str(w).startswith('refused')}
            status = ('refused' if policy_refused else 'waiting' if remote_waiting or root_waiting else 'skipped')
            return self.record('teacher', batch_key, status,
                               reason=('retained teacher results refused under the plan\'s shared market policy (preserved): %s'
                                       % '; '.join('%s: %s' % kv for kv in sorted(policy_refused.items()))[:1500])
                                      if policy_refused else 'waiting for owning lane teacher receipts' if remote_waiting else
                                      'waiting for the days\' completed shared-policy ROOTs' if root_waiting else
                                      'each day has local rows or its owning lane completed teacher receipt',
                               remote_days=remote, waiting=remote_waiting + sorted(root_waiting), refused_days=refused or None,
                               root_waiting=root_waiting or None, shared_market_policy=policy, brain_entries=brain_entries,
                               days=[dict(day=e['day'], rows=str(rows_of(e)[0]), source=rows_of(e)[1]) for e in local])
        if not (self.box / 'frankie_box_experiment_teacher.sh').is_file():
            return self.record('teacher', batch_key, 'not_built', days=[e['day'] for e in todo],
                               reason='frankie_box_experiment_teacher.sh is not in the staged checkout yet')
        receipts, external_waiting, roots = [], {}, {}
        for e in todo:
            if e['day'] in refused:
                continue                                  # its retained result is preserved; no re-run beside it
            ing = self.receipt('ingest', e['day'])
            if not (ing and ing['status'] in FINISHED):
                continue                                  # that day waits on its ingest; the rest of the batch runs
            ready, why = self.external_ready(e)
            if not ready:
                external_waiting[e['day']] = why          # the teacher builds the external section: it waits for the file
                continue
            if policy:
                # the shared policy: the teacher reads the day's completed OWNER-LOCAL ROOT under the same policy (the
                # wrapper forwards --calculations ROOT --shared-market-policy per day); a day without it waits, a ROOT
                # computed under another policy refuses the day (preserved; explicit compatible successor)
                root, why = self.shared_root_of(e)
                if root is None:
                    (refused if why.startswith('refused') else root_waiting)[e['day']] = why
                    continue
                stale_path = TEACHER_ROWS / e['day'] / 'receipt.json'
                if stale_path.is_file():
                    # a retained teacher publication the rows reader does not accept (partial or failed): the producer
                    # would refuse it after reading the whole journal unless it binds exactly this ROOT and ingest;
                    # judged here on the same witnesses, before any dispatch; unreadable = refused, never raised
                    try:
                        stale = json.loads(stale_path.read_bytes())
                    except (OSError, ValueError) as error:
                        refused[e['day']] = 'refused: unreadable retained teacher publication at %s (%s); %s' % (
                            stale_path, error, ROWS_ROUTE % stale_path.parent)
                        continue
                    identity = stale.get('shared_market_identity') or {}
                    if (identity.get('schema') != policy or identity.get('day') != e['day']
                            or (identity.get('calculations') or {}).get('sha256') != sha256_file(Path(root) / 'calculations-receipt.json')
                            or (stale.get('ingestion_receipt') or {}).get('sha256') != ing['receipt_sha256']):
                        refused[e['day']] = ('refused: a retained teacher publication that does not bind this ROOT and ingest under the '
                                             'plan\'s shared identity stands at %s; preserved; %s' % (stale_path, ROWS_ROUTE % stale_path.parent))
                        continue
                roots[e['day']] = root
            receipts.append((e['day'], ing['receipt']))
        waiting = sorted(set(e['day'] for e in todo if e['day'] not in dict(receipts) and e['day'] not in refused)
                         | set(remote_waiting) | set(root_waiting))
        if not receipts:
            return self.record('teacher', batch_key, 'waiting' if waiting else 'refused', days=waiting,
                               refused_days=refused or None, root_waiting=root_waiting or None,
                               external_waiting=external_waiting or None,
                               reason='no day of the batch is ready for its teacher (sealed ingest, day file%s)'
                                      % (', completed shared-policy ROOT' if policy else '') if waiting else
                                      'every day of the batch is refused: %s' % '; '.join('%s: %s' % kv for kv in sorted(refused.items()))[:1500])
        if not self.disk_ok('teacher'):
            return None
        env = dict(DAYS=','.join(d for d, _ in receipts), INGESTION_RECEIPTS=','.join(r for _, r in receipts))
        if policy:
            env.update(SHARED_MARKET_POLICY=policy, CALCULATION_ROOTS=','.join(roots[d] for d, _ in receipts))
        code, log = self.child('teacher', batch_key, 'frankie_box_experiment_teacher.sh', env)
        saved = self.child_saved('teacher', batch_key, code, log, days=[d for d, _ in receipts], waiting=waiting,
                                 remote_days=remote, refused_days=refused or None, shared_market_policy=policy,
                                 calculation_roots=roots or None, root_waiting=root_waiting or None,
                                 external_waiting=external_waiting)
        if saved:
            return saved
        by_day = {e['day']: e for e in todo}
        # the teacher step's LISTED outcomes (workflow_reports, 2026-10-07): a day whose experiment-teacher-rows/<day>/
        # receipt.json says equation_not_run (exit 5: no operand for the pinned equation on this day, no rows file) is a
        # listed day WITHOUT Dipole rows, not a failed batch; exit 4 (rows published, external section listed) is listed
        # too; the step exits 3 only on a failed day. missing = days with neither accepted rows nor such a receipt
        listed = {}
        for d, _ in receipts:
            if self.day_rows(by_day[d])[0] is not None:
                continue
            try:
                published = json.loads((TEACHER_ROWS / d / 'receipt.json').read_bytes())
            except (OSError, ValueError):
                published = None
            if isinstance(published, dict) and published.get('day') == d and published.get('status') == 'equation_not_run':
                listed[d] = dict(status='equation_not_run', reason=(published.get('equation_not_run') or {}).get('reason'),
                                 operand=(published.get('equation_not_run') or {}).get('operand'))
        missing = [d for d, _ in receipts if self.day_rows(by_day[d])[0] is None and d not in listed]   # the gate: accepted rows only
        if listed:
            self.log('teacher %s: no Dipole rows for %s (equation_not_run: listed, the days go on without them)' % (batch_key, sorted(listed)))
        for d, _ in receipts:
            rows, source, _ = self.day_rows(by_day[d])
            if rows is not None:
                rows = Path(rows)
                try:
                    brain_entries[d] = self.teacher_knowledge(d, rows / ROWS_FILE, source)
                except ValueError as error:
                    refused[d] = str(error)             # recorded per day; the batch's other entries stay
        if refused:
            self.log('teacher %s: knowledge not taught again for %s (explicit checked successor required): %s' % (
                batch_key, sorted(refused), '; '.join('%s: %s' % kv for kv in sorted(refused.items()))[:1500]))
        # a day refused by teacher_knowledge (producer identity) is recorded on the batch (refused_days) and refuses its
        # own classroom with the same reason; the batch's other days are not held back by it (the batch status is the
        # child's and the rows', as before). A day refused by the plan's SHARED MARKET POLICY (why starts with 'refused')
        # makes the batch refused: never FINISHED, its other days ran
        status = 'done' if code == 0 and not missing and not waiting else 'failed'
        if status == 'done' and any(str(w).startswith('refused') for w in refused.values()):
            status = 'refused'
        return self.record('teacher', batch_key, status,
                           exit_code=code, log=log, days=[d for d, _ in receipts], rows_missing=missing, waiting=waiting,
                           rows_listed=listed or None,
                           remote_days=remote, refused_days=refused or None, shared_market_policy=policy,
                           calculation_roots=roots or None, root_waiting=root_waiting or None,
                           external_waiting=external_waiting, brain_entries=brain_entries,
                           new_bytes=sum(new_bytes(TEACHER_ROWS / d) for d, _ in receipts),
                           # the one-day inspection (frankie_box_workflow_inspection.py): per day what the teacher child
                           # received, every disposition this caller applied, and what came back; operator review only
                           inspection=dict(inputs=dict(env=env, days={d: dict(ingestion_receipt=r, calculation_root=roots.get(d))
                                                                     for d, r in receipts}),
                                           use=dict(policy=policy or 'none (legacy plan)', refused=refused or None,
                                                    root_waiting=root_waiting or None, external_waiting=external_waiting or None,
                                                    rows_missing=missing, rows_listed=listed or None, waiting=waiting,
                                                    skipped_days=sorted(set(by_day) - set(dict(receipts)))),
                                           outputs=dict(exit_code=code, rows={d: str(self.day_rows(by_day[d])[0]) for d, _ in receipts},
                                                        brain_entries=sorted(brain_entries))),
                           reason=None if code == 0 and not missing and not waiting else
                           'rows missing for %s, waiting on ingest %s (those days go on without Dipole rows, listed)'
                           % (missing, waiting))

    def shared_runtime(self):
        """THE ONE pinned model runtime on the box (Greg, 2026-10-07: Jev uses the same weights, code and setup as Granite):
        {status: ready|refused, config, provenance, binary, model, reasons, rule} built once per Run from the staged
        knowledge/GRANITE_MEETING_RUNTIME_V1.json (frankie_box_granite_meeting.load_config), the setup script's provenance
        receipt under GRANITE_DIR (exactly one FRANKIE_GRANITE_RUNTIME_PROVENANCE_V1 names llama-server and the GGUF)
        and the meeting's own runtime gate on those paths (binary and every extracted file against llama_cpp_files, the
        model against model_sha256). 'refused' names every reason VISIBLY until the pinned install exists; nothing is
        installed, guessed or borrowed. The meeting child (LLAMA_SERVER/GGUF_MODEL) and Jev bind to this same result."""
        cached = getattr(self, '_shared_runtime', None)
        if cached is not None:
            return cached
        started = time.time()
        out = dict(schema=SHARED_RUNTIME_SCHEMA, status='refused', config=None, provenance=None, binary=None, model=None, reasons=[],
                   rule='one pinned runtime (Granite 4.2 3B Q4_K_M, llama.cpp b11440) for the meeting and Jev; refused visibly '
                        'until frankie_box_granite_meeting_setup.sh installed it under %s' % GRANITE_DIR)
        try:
            import frankie_box_granite_meeting as GM
            config, witness = GM.load_config()
            out['config'] = witness
            found = sorted(p for p in GRANITE_DIR.glob('*/provenance.json') if not p.is_symlink()) if GRANITE_DIR.is_dir() else []
            docs = []
            for p in found:
                try:
                    doc = json.loads(p.read_bytes())
                except (OSError, ValueError) as error:
                    out['reasons'].append('unreadable provenance %s (%s: %s)' % (p, type(error).__name__, error))
                    continue
                if doc.get('schema') == GRANITE_PROVENANCE_SCHEMA:
                    docs.append((p, doc))
            if not docs:
                out['reasons'].append('no %s under %s: the pinned runtime is not installed on this box (the setup script '
                                      'writes it after every pin check passed)' % (GRANITE_PROVENANCE_SCHEMA, GRANITE_DIR))
            elif len(docs) > 1:
                out['reasons'].append('%d provenance receipts under %s (%s): exactly one pinned runtime is expected; none chosen'
                                      % (len(docs), GRANITE_DIR, ', '.join(str(p) for p, _ in docs)))
            else:
                p, doc = docs[0]
                binary, model = doc.get('server'), doc.get('model')
                out.update(provenance=file_pin(p), binary=binary, model=model)
                pins = config.get('pins') or {}
                for key, have in (('release', 'llama_cpp_release'), ('asset', 'llama_cpp_asset'), ('server_sha256', 'llama_server_sha256'),
                                  ('model_sha256', 'model_sha256')):
                    if doc.get(key) != pins.get(have):
                        out['reasons'].append('provenance %s %s differs from the staged pin %s %s' % (key, doc.get(key), have, pins.get(have)))
                if not binary or not str(binary).startswith(str(GRANITE_DIR) + '/') or not model or not str(model).startswith(str(GRANITE_DIR) + '/'):
                    out['reasons'].append('provenance names a server/model outside %s (%s, %s)' % (GRANITE_DIR, binary, model))
                else:
                    out['reasons'].extend(GM.gate(config, binary=binary, model=model))   # the meeting's own gate: binary, files, model sha256
        except Exception as error:  # noqa: BLE001 - an unreadable config or gate is a visible refusal, never a silent inputs-only
            out['reasons'].append('%s: %s' % (type(error).__name__, str(error)[:300]))
        out['status'] = 'ready' if not out['reasons'] else 'refused'
        out['seconds'] = round(time.time() - started, 1)
        self._shared_runtime = out
        self.log('shared model runtime: %s%s (%.1f s)' % (out['status'], ('' if out['status'] == 'ready' else ': ' + '; '.join(out['reasons'])[:600]),
                                                          out['seconds']))
        return out

    TEACHER_KNOWLEDGE_PRODUCERS = ('research/kalshi/frankie_boss/dipole_classroom.py',
                                   'research/kalshi/frankie_boss/dipole_classroom_integration.py',
                                   'research/kalshi/frankie_boss/c15_journal.py',
                                   'deploy/aws/box/frankie_box_experiment_teacher.py')

    def teacher_producer_identity(self):
        """The exact producers a teacher-knowledge summary is bound to: the sha256 of the modules that compute the
        teacher key from the rows and of the teacher step that wrote the rows. The commit is recorded beside it, not
        compared: a commit that leaves these modules byte-identical is the same producer."""
        return dict(modules={name: sha256_file(self.code_root / name) for name in self.TEACHER_KNOWLEDGE_PRODUCERS})

    def shared_policy_mismatch(self, retained):
        """None when a ROOT's retained shared_market_policy is the staged timeline policy, else what differs (a RECORD,
        never a refusal: Greg, 2026-10-09). Meaning fields only (frankie_box_market_timeline.policy_differs: schema,
        order, clocks, required_native, representation, completed_knowledge, missing_coverage); implementation_sha256
        (the module's bytes) is recorded, never compared: a code hash is not data identity."""
        import frankie_box_market_timeline as MT
        if not isinstance(retained, dict) or not retained:
            return 'no shared market policy (a legacy ROOT)'
        differ = MT.policy_differs(retained)
        return ('the retained policy differs from the staged %s in %s' % (MT.SCHEMA, ', '.join(differ))) if differ else None

    def note_identity(self, day, stage, what):
        """Record (never refuse) a policy/identity difference on the day's retained outputs: it is carried on every step
        record of the day written by this Run (identity_recorded) and logged once (Greg, 2026-10-09: "use previously
        generated one or override ... we know")."""
        notes = self._identity_recorded.setdefault(day, [])
        line = '%s: %s' % (stage, what)
        if line not in notes:
            notes.append(line)
            self.log('%s %s: RECORDED, the run proceeds: %s' % (stage, day, what))

    def shared_root_of(self, e):
        """(the day's completed owner-local ROOT directory, None) or (None, why): 'waiting ...' while the ROOT is not
        complete here; 'refused ...' only for data trouble (a remote owner's ROOT is that lane's, never a caller-local
        alias). Greg, 2026-10-09: the existing receipted ROOT on disk is ALWAYS used; a policy difference is recorded
        (note_identity), never a refusal and never a new run name."""
        r = self.root_on_disk(e) or {}                # session 9: the ROOT on disk, never a stale step record
        if r.get('remote_calculations'):
            return None, 'refused: the day\'s ROOT belongs to its remote owner %s; its teacher runs there' % r.get('owner')
        if r.get('status') not in ('done', 'reused', 'refused') or not r.get('calculations'):
            return None, 'waiting for the day\'s completed ROOT (root is %s)' % (r.get('status') or 'not run')
        calc = Path(r['calculations'])
        receipt = calc / 'calculations-receipt.json'
        if not receipt.is_file():
            return None, 'waiting: the ROOT %s has no calculations-receipt.json' % calc
        try:
            retained = json.loads(receipt.read_bytes())
        except (OSError, ValueError) as error:
            return None, 'refused: data trouble: the ROOT receipt %s is unreadable (%s: %s)' % (receipt, type(error).__name__, error)
        if retained.get('day') != e['day']:
            return None, 'refused: data trouble: the ROOT receipt %s belongs to day %s, not %s' % (receipt, retained.get('day'), e['day'])
        mismatch = self.shared_policy_mismatch(retained.get('shared_market_policy'))
        if mismatch:
            self.note_identity(e['day'], 'root', 'the completed ROOT %s: %s; used as it is' % (calc, mismatch))
        return str(calc), None

    def day_rows(self, e):
        """The ONE gate every consumer of the day's teacher rows passes (rows_file, classroom_ready, the classroom's
        knowledge publication, school, data): (rows, source, None), or (None, None, why) when there are none, or when the
        plan's shared market policy does not accept them (why starts with 'waiting' or 'refused')."""
        base, source = rows_of(e)
        if base is None:
            return None, None, None
        if self.plan.get('shared_market_policy'):
            state, why = self.shared_teacher_compatible(e, base, source)
            if state != 'ok':
                return None, None, why
        return base, source, None

    def shared_teacher_compatible(self, e, rows, source):
        """('ok', None) when the day's retained teacher rows are used; ('waiting', why) while the day's ROOT or ingest is
        not complete here (not judged yet); ('refused', why) ONLY for data trouble: an unreadable (missing/corrupt)
        teacher receipt, rows of another day, a shared read that did not complete, an integrity failure of the day file.
        Greg, 2026-10-09 ("use previously generated one or override ... we know"): a policy or identity difference on the
        retained rows (no shared identity, another schema, another ROOT witness, another ingestion receipt, another
        external publication) is RECORDED on the day's step records (note_identity) and the rows are used; never a
        refusal and never a new run name."""
        policy = self.plan.get('shared_market_policy')
        day = e['day']

        def note(what):
            self.note_identity(day, 'teacher', '%s (rows %s); used as they are' % (what, rows))
        if source != 'teacher-only step':
            note('the %s rows carry no shared-market teacher receipt; the plan selects %s' % (source, policy))
            return 'ok', None
        try:
            saved = json.loads((Path(rows) / 'receipt.json').read_bytes())
        except (OSError, ValueError) as error:
            return 'refused', 'refused: data trouble: unreadable teacher receipt under %s (%s); %s' % (rows, error, ROWS_ROUTE % rows)
        identity, read = saved.get('shared_market_identity') or {}, saved.get('shared_market_read') or {}
        if saved.get('day') not in (None, day) or identity.get('day') not in (None, day):
            return 'refused', 'refused: data trouble: the teacher receipt under %s belongs to day %s, not %s' % (
                rows, identity.get('day') or saved.get('day'), day)
        if not identity:
            note('a legacy teacher receipt (no shared_market_identity) under the plan\'s %s' % policy)
            return 'ok', None
        if identity.get('schema') != policy:
            note('the teacher receipt\'s shared identity is %s, not %s' % (identity.get('schema'), policy))
        root, why = self.shared_root_of(e)
        if root is None:
            return ('refused' if why.startswith('refused') else 'waiting'), why
        want = file_pin(Path(root) / 'calculations-receipt.json')
        have = identity.get('calculations') or {}
        if (have.get('sha256'), have.get('bytes')) != (want['sha256'], want['bytes']):
            note('the teacher receipt binds another ROOT witness (%s) than the day\'s completed ROOT (%s)' % (
                have.get('sha256'), want['sha256']))
        if read.get('identity') != identity or not read.get('complete'):
            return 'refused', 'refused: data trouble: the teacher\'s shared read is not the complete read of its identity'
        ing = self.receipt('ingest', day) or {}
        if ing.get('status') not in FINISHED or not ing.get('receipt_sha256'):
            return 'waiting', 'waiting: the day\'s ingest is %s here; its teacher result is not judged until it is sealed' % (ing.get('status') or 'not run')
        if (saved.get('ingestion_receipt') or {}).get('sha256') != ing['receipt_sha256']:
            note('the teacher receipt binds another ingestion receipt than the day\'s')
        directory = self.ingest_dir(e)
        key = (day, str(directory))
        if key not in self._day_file_sha:                 # read once per Run: what the ROOT and the teacher both saw
            try:
                self._day_file_sha[key] = attached_day_file(directory)[1:] if directory is not None else (None, None)
            except OSError as error:                # a witness that cannot be read (absent, I/O) is not judged: waiting
                return 'waiting', 'waiting: the day file beside the sealed ingest could not be read (%s: %s)' % (type(error).__name__, error)
            except (ValueError, KeyError, TypeError) as error:   # F8: malformed content: integrity failure, never a wait
                return 'refused', 'refused: integrity failure: the day file beside the sealed ingest is malformed (%s: %s)' % (
                    type(error).__name__, error)
        attached, absent = self._day_file_sha[key]
        section = saved.get('external_section') or {}
        bound = section.get('sha256') or section.get('sha256_expected')
        if attached is None and bound and absent and not absent.startswith('DIFFERS'):
            # the witness is MISSING now (not an integrity mismatch): a missing witness is carried as missing, never
            # relabelled a differing publication; the retained result is not judged until the file is readable again
            return 'waiting', 'waiting: the day file beside the sealed ingest is missing (%s) while the teacher receipt binds %s; not judged by it' % (absent, bound)
        if bound != attached:
            note('the teacher receipt\'s external publication (%s) differs from the day file beside the sealed ingest (%s)' % (
                section.get('sha256') or section.get('sha256_expected'), attached))
        return 'ok', None

    def teacher_knowledge(self, day, rows_path, source):
        """Publish every measured component/pair result; per-cursor teacher evidence stays on its owning box. A new summary
        is bound to the exact producer identities that made it; a retained summary whose producer identity differs from
        the current one, or is not established (an older summary without one), is NOT reused and NOT regenerated here: the
        old result is preserved and an explicit checked successor (the correction route) is required."""
        from research.kalshi.frankie_boss import dipole_classroom as DC, dipole_classroom_integration as I
        from research.kalshi.frankie_boss.c15_journal import unpack
        from research.kalshi.frankie_boss.frankie_principal_adapter import json_form
        import frankie_box_lane_state as LS
        rows_path = Path(rows_path)
        # 2026-10-09 (one pass over the data): the rows file's sha256 from its claim row or the teacher's own receipt
        # (rows_file.sha256, with a stat check), read whole only when neither holds
        source_sha, source_basis = self.teacher_rows_sha256(rows_path)
        try:                                       # brain_stage's witness of the rows file is then a cache hit, no read
            from frankie_box_filehash import remember
            remember(rows_path, dict(bytes=rows_path.stat().st_size, sha256=source_sha))
        except Exception:  # noqa: BLE001 - without it brain_stage witnesses as before
            pass
        path = rows_path.parent / 'teacher-knowledge.json'
        producer = self.teacher_producer_identity()
        producer_note = None
        if path.exists():
            body = json.loads(path.read_bytes())
            if body['source']['sha256'] != source_sha or body['day'] != day:
                raise ValueError('retained teacher knowledge belongs to another source/day')
            retained = body.get('producer')
            # 2026-10-09 (Greg): the code version is RECORDED, NEVER COMPARED: retained knowledge made by other producer
            # modules (or before producer identities were recorded) is reused for the same rows; the difference is listed
            if retained is None:
                producer_note = 'retained knowledge carries no producer identity (made before it was recorded): reused'
            elif retained.get('modules') != producer['modules']:
                changed = sorted(k for k in set(retained.get('modules') or {}) | set(producer['modules'])
                                 if (retained.get('modules') or {}).get(k) != producer['modules'].get(k))
                producer_note = ('retained knowledge made at commit %s by other producer modules (%s): reused, the code '
                                 'version recorded, never compared' % (body.get('made_at_commit'), ', '.join(changed)))
            if producer_note:
                self.log('teacher knowledge %s: %s' % (day, producer_note))
            reused = self.teacher_entry_reuse(day, rows_path, source_sha, path)
            if reused is not None:
                return dict(reused, source_basis=source_basis, producer_note=producer_note)
        else:
            snapshot = unpack(json.loads(rows_path.read_bytes()))
            key = I._repin_teacher_key_correlations(DC.build_teacher_key(snapshot))
            findings = []
            for dimension in key['dimensions']:
                # These are the reviewed teacher's measured outputs, not a summary replacing the retained observations.
                measured = {k: v for k, v in dimension.items() if k not in ('observations', 'nonpresent_explanations')}
                findings.append(dict(finding_id='teacher-component:' + dimension['name'],
                                     scope=dict(day=day, component=dimension['name']), measurement=measured))
            for pair in key['relationship_scan']:
                findings.append(dict(finding_id='teacher-pair:%s:%s' % (pair['left'], pair['right']),
                                     scope=dict(day=day, pair=[pair['left'], pair['right']]), measurement=pair))
            body = dict(schema='FRANKIE_TEACHER_KNOWLEDGE_V1', day=day, author='BOSS teacher',
                        source=dict(path=str(rows_path), sha256=source_sha, bytes=rows_path.stat().st_size,
                                    owner=os.environ.get('FRANKIE_LANE_OWNER', 'main'),
                                    snapshot_hash=key['source_snapshot_hash']),
                        producer=producer, made_at_commit=self.commit,
                        findings=json_form(findings),
                        rule='all component/pair measured outputs individually; every cursor/state/reason remains '
                             'in the exact source, consumed by the teacher; no host grade or student decision process')
            body['cutoff_ns'] = snapshot['as_of']
            body['through_cursor'] = snapshot['through_cursor']
            LS.write(path, body)
        # The summary is part of the immutable entry bytes: it names the exact rows file, never the label of the path
        # that found it ('plan' / 'teacher-only step'), so the same rows reached by another label reuse the entry
        # instead of declining it as different knowledge. The label stays in the step receipt (days=[... source]).
        out = self.brain_stage(day, 'teacher', [rows_path, path],
                               summary=dict(rows=str(rows_path)), inline_limit=path.stat().st_size)
        return dict(out, source_basis=source_basis, producer_note=producer_note) if isinstance(out, dict) else out

    @staticmethod
    def teacher_rows_sha256(rows_path):
        """(sha256, basis) of the teacher's rows file without a second whole read when one is not needed: (1) a
        FRANKIE_FILE_CLAIM row in the rows directory that still holds (inode, size, mtime_ns, filesystem, last 64 KiB);
        (2) the teacher receipt beside it (receipt.json rows_file.sha256 naming this file) when the rows file was not
        modified after that receipt was written; (3) else one whole read."""
        rows_path = Path(rows_path)
        try:
            import frankie_box_brain as BR
            from research.kalshi.frankie_boss.operations.ingest_block_sources import claim_still_holds
            st = os.stat(rows_path)
            row = BR.file_claims(rows_path.parent).get((st.st_ino, st.st_size, st.st_mtime_ns))
            if row is not None and claim_still_holds(row, rows_path) is not None:
                return row['sha256'], 'claim (%s)' % row.get('claim_file')
        except Exception:  # noqa: BLE001 - no claim: the next basis
            st = None
        try:
            receipt = rows_path.parent / 'receipt.json'
            rf = (json.loads(receipt.read_bytes()).get('rows_file') or {})
            st = st or os.stat(rows_path)
            if (rf.get('sha256') and rf.get('file') == rows_path.name
                    and st.st_mtime_ns <= receipt.stat().st_mtime_ns):
                return rf['sha256'], 'teacher receipt rows_file.sha256 (rows not modified after %s)' % receipt
        except (OSError, ValueError, AttributeError):
            pass
        return sha256_file(rows_path), 'hashed (no claim, no usable teacher receipt)'

    def teacher_entry_reuse(self, day, rows_path, source_sha, knowledge_path):
        """The brain's <day>-teacher entry when it already holds EQUAL knowledge (its rows source = this rows file and
        sha256, its teacher-knowledge source = this file's bytes): the brain_stage record, without witnessing the rows
        file again; else None (brain_stage files it as before)."""
        brain = Path(self.plan.get('brain') or str(BRAIN))
        entry = brain / ('%s-teacher' % day)
        try:
            body = json.loads((entry / 'stage-knowledge.json').read_bytes())
            manifest = json.loads((entry / 'MANIFEST.json').read_bytes())
        except (OSError, ValueError):
            return None
        sources = {str(r.get('path')): r for r in body.get('sources') or []}
        rows = sources.get(str(rows_path))
        know = sources.get(str(knowledge_path))
        if not (rows and know and rows.get('sha256') == source_sha and know.get('sha256') == sha256_file(knowledge_path)):
            return None
        self.log('brain teacher %s: %s holds equal knowledge (rows %s, knowledge %s): reused, the rows not read again' % (
            day, entry, source_sha[:12], know['sha256'][:12]))
        return dict(path=str(entry), reused=True, status='reused',
                    manifest_sha256=sha256_file(entry / 'MANIFEST.json'),
                    knowledge_sha256=sha256_file(entry / (manifest.get('current_knowledge') or 'stage-knowledge.json')),
                    source_witness=[dict(path=str(rows_path), basis='the brain entry\'s own equal record')])

    def data(self, e):
        remote = self.remote_stage('data', e['day'])
        if remote is not None:
            return remote
        target = DATA / e['day'] / ('cycle-' + CYCLE)
        root = self.root_on_disk(e)                  # session 9: the ROOT on disk, never a stale step record
        if (target / 'MANIFEST.json').is_file():
            # an existing export is reused only when it was built from THIS run's ROOT of the day; one from another ROOT
            # (an earlier or partial run) is a second export of the day: declined with both named, never reused blind
            made_from = (json.loads((target / 'MANIFEST.json').read_bytes()).get('directories') or {}).get('root')
            ours = (root or {}).get('calculations')
            if ours and made_from and str(Path(made_from)) != str(Path(ours)):
                # 2026-10-09 (Greg: our own gate never blocks a run on fine data): an export made from ANOTHER ROOT of the
                # day is not this ROOT's data. It is moved aside with a receipt (nothing deleted), together with the
                # day's search built on it, and the day is exported from its own ROOT below; never a refusal of the day
                moved = self.move_aside_other_export(e, target, made_from, ours)
                self.log('data %s: the export under %s was made from another ROOT (%s, this ROOT %s): moved aside (%s); '
                         'exported again from this ROOT' % (e['day'], target, made_from, ours, moved))
            else:
                return self.record('data', e['day'], 'reused', target=str(target), exported_from=made_from,
                                   manifest_sha256=sha256_file(target / 'MANIFEST.json'))
        ing = self.receipt('ingest', e['day'])
        if root and root.get('status') == 'refused' and 'retained_policy' in root:
            return self.record('data', e['day'], 'refused', reason='refused: the day\'s ROOT is refused under the plan\'s '
                                                                   'shared market policy: %s' % root.get('reason'))
        if not (root and root['status'] in FINISHED and ing and ing['status'] in FINISHED):
            return self.record('data', e['day'], 'waiting', reason='the day has no ROOT or no sealed ingest yet')
        ready, why = self.external_ready(e)
        if not ready:
            return self.record('data', e['day'], 'waiting', reason=why)
        rows, source, why = self.day_rows(e)
        if rows is None and why:
            return self.record('data', e['day'], 'refused' if why.startswith('refused') else 'waiting', reason=why)
        dipole_missing = None
        if rows is None:
            dipole_missing = ('no Dipole rows for the day (teacher batch: %s); exported and searched without them, listed '
                              'missing; a later search with the rows would be a second search of the day (declined)'
                              % ((self.receipt('teacher', self.batch_of(e['day'])) or {}).get('status') or 'not run'))
        # DATA_WORKERS: the export pins its hashing in a largest-first process pool (workflow_reports, 2026-10-07); the
        # 15 workers of the held 16-CPU lane, as ROOT and search; without it the export hashes serially
        env = dict(ACTION='export', DAY=e['day'], CYCLE=CYCLE, CALCULATIONS=root['calculations'], INGEST=ing['ingest'],
                   DATA_WORKERS=self.day_cpus() - 1)
        for key, var in (('launch', 'LAUNCH'), ('preparation', 'PREPARATION'), ('principal_inputs', 'PRINCIPAL_INPUTS'),
                         ('host_config', 'HOST_CONFIG'), ('run', 'RUN')):
            if e.get(key):
                env[var] = e[key]
        if rows is not None and source != 'launch run':
            env['TEACHER'] = rows
        if not self.disk_ok('data'):
            return None
        code, log = self.child('data', e['day'], 'frankie_box_experiment_data.sh', env)
        saved = self.child_saved('data', e['day'], code, log, target=str(target))
        if saved:
            return saved
        if code != 0 or not (target / 'MANIFEST.json').is_file():
            return self.record('data', e['day'], 'failed', exit_code=code, log=log, reason='no exported MANIFEST.json')
        return self.record('data', e['day'], 'done', exit_code=code, log=log, target=str(target), dipole=source,
                           dipole_missing=dipole_missing, manifest_sha256=sha256_file(target / 'MANIFEST.json'),
                           new_bytes=new_bytes(target))

    def move_aside_other_export(self, e, target, made_from, ours):
        """An export of the day made from another ROOT (and the day's searches, built on it) moved aside, never deleted:
        <dir> -> <dir>.other-root-<stamp>, a FRANKIE_EXPORT_MOVED_ASIDE_V1 receipt written beside it. Returns the moves."""
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        moves = []
        for directory in (Path(target), SEARCH / e['day'] / ('cycle-' + CYCLE)):
            if not directory.exists():
                continue
            aside = directory.with_name('%s.other-root-%s' % (directory.name, stamp))
            os.rename(directory, aside)
            moves.append(dict(moved=str(directory), to=str(aside)))
        receipt = dict(schema='FRANKIE_EXPORT_MOVED_ASIDE_V1', run=self.plan['run'], day=e['day'], at_utc=stamp,
                       exported_from=made_from, this_root=ours, moves=moves, commit=self.commit,
                       rule='an export (and the searches on it) of another ROOT of the day is moved aside, never reused, '
                            'never deleted; the day is exported again from its own ROOT')
        for move in moves:
            try:
                (Path(move['to']) / 'MOVED_ASIDE.json').write_text(json.dumps(receipt, indent=1, sort_keys=True) + '\n')
            except OSError as error:
                self.log('moved-aside receipt under %s not written (%s)' % (move['to'], error))
        return moves

    def search(self, e):
        remote = self.remote_stage('search', e['day'])
        if remote is not None:
            return remote
        target = SEARCH / e['day'] / ('cycle-' + CYCLE) / e['role']
        if (target / 'MANIFEST.json').is_file():
            brain_entry = self.search_knowledge(e, target)
            return self.record('search', e['day'], 'reused', target=str(target), brain_entry=brain_entry)
        d = self.receipt('data', e['day'])
        if not (d and d['status'] in FINISHED):
            return self.record('search', e['day'], 'waiting', reason='the day data is not exported yet')
        ready, why = self.external_ready(e)
        if not ready:
            return self.record('search', e['day'], 'waiting', reason=why)
        # no causal axis: a day whose ROOT published no book-frame spool (frames.jsonl under work/derived/.rows) has no
        # per-day causal axis, and the search refuses before its manifest (build_series: frames_pin None, SystemExit).
        # Under the missing-coverage rule that is a listed outcome of THIS step, never the day's failure: not_run with
        # the reason, the day goes on (Jev and the lessons name it when they need the search)
        root = self.root_on_disk(e) or {}            # session 9: the ROOT on disk, never a stale step record
        calc = Path(root['calculations']) if root.get('calculations') else None
        frames = (calc / 'work' / 'derived' / '.rows' / 'frames.jsonl') if calc else None
        if frames is None or not frames.is_file() or frames.stat().st_size == 0:
            pin = ((root.get('all99') or {}).get('carriers') or {}).get('root.frames') or {}
            return self.record('search', e['day'], 'not_run', target=str(target), calculations=str(calc) if calc else None,
                               frames_spool=str(frames) if frames else None,
                               reason='no causal axis: the day\'s ROOT published no book-frame spool (%s%s); the search has no '
                                      'per-day axis and is not run; the day goes on without a search (listed)' % (
                                          frames if frames else 'no ROOT calculations named',
                                          ('; the ROOT lists root.frames ' + pin.get('status') + ': ' + str(pin.get('reason')))
                                          if pin else ''))
        if not self.disk_ok('search'):
            return None
        env = dict(DAY=e['day'], CYCLE=CYCLE, DAY_ROLE=e['role'], LAGS=self.plan['lags'], WORKERS=self.day_cpus() - 1)
        if self.plan['transforms']:
            env['TRANSFORMS'] = self.plan['transforms']
        if e['role'] == 'confirmation':
            env['FROZEN_SURVIVORS'] = self.plan['frozen_survivors']
        code, log = self.child('search', e['day'], 'frankie_box_experiment_search.sh', env)
        saved = self.child_saved('search', e['day'], code, log, target=str(target))
        if saved:
            return saved
        if code != 0 or not (target / 'MANIFEST.json').is_file():
            return self.record('search', e['day'], 'failed', exit_code=code, log=log, reason='no search MANIFEST.json')
        brain_entry = self.search_knowledge(e, target)
        return self.record('search', e['day'], 'done', exit_code=code, log=log, target=str(target),
                           manifest_sha256=sha256_file(target / 'MANIFEST.json'), new_bytes=new_bytes(target),
                           brain_entry=brain_entry)

    def search_knowledge(self, e, target):
        """Check existing arithmetic/roles before publication; reuse is never independent confirmation."""
        import frankie_box_experiment_review as REVIEW
        from frankie_box_durable import write_json
        manifest_path = target / 'MANIFEST.json'
        checked = REVIEW.search_findings(target, e['day'])
        if checked['role'] != e['role']:
            raise ValueError('search review differs from the planned day role')
        review_body = {k: v for k, v in checked.items() if k != 'findings'}
        review_path = target / ('knowledge-review-' + REVIEW.digest(REVIEW.canonical(review_body)) + '.json')
        if not review_path.exists():
            write_json(review_path, review_body)
        elif json.loads(review_path.read_bytes()) != review_body:
            raise ValueError('retained search review differs from its content address')
        if checked['review']['listed']:
            raise ValueError('search evidence needs source correction before teaching; every affected row is listed in '
                             + str(review_path))
        # Preserve the established findings bytes when checking valid retained work. Adding a
        # review does not invent a new finding identity or invalidate an unaffected old lesson.
        body = dict(schema='FRANKIE_SEARCH_FINDINGS_V1', day=e['day'], role=e['role'], findings=checked['findings'],
                    manifest_sha256=checked['manifest_sha256'],
                    status='search candidates; scientific double-checks and survivor treatment occur in their code stages',
                    rule='every beyond-chance row retained individually; no rarity gate or pooling; all counts remain in the parts')
        path = target / 'knowledge-findings.json'
        raw = (json.dumps(body, sort_keys=True, indent=1) + '\n').encode()
        if path.exists() and path.read_bytes() != raw:
            raise ValueError('retained search findings changed: %s' % path)
        if not path.exists():
            import frankie_box_lane_state as LS
            LS.write(path, body)
        publication = self.brain_stage(e['day'], 'search', [manifest_path, path],
                                      summary=dict(target=str(target), role=e['role']), inline_limit=len(raw))
        publication['source_review'] = dict(path=str(review_path), sha256=sha256_file(review_path),
                                           independent_observations_added=0)
        return publication

    def accumulated_lessons(self, e):
        """Non-classroom days use the existing owner-local accumulated scientific reader too."""
        day = e['day']
        self.check_save()
        remote = self.remote_stage('accumulated_lessons', day)
        if remote is not None:
            return remote
        if e['classroom_arm']:
            return self.record('accumulated_lessons', day, 'skipped',
                               reason='the classroom exchange already consumes accumulated claims on this owning search')
        search = self.receipt('search', day)
        if (search or {}).get('status') == 'not_run':
            return self.record('accumulated_lessons', day, 'not_run', reason='the owning day\'s search is not_run (%s): no '
                                                                            'search to retest accumulated claims on; listed'
                                                                            % search.get('reason'))
        if not (search and search['status'] in FINISHED and search.get('target')):
            return self.record('accumulated_lessons', day, 'waiting', reason='the owning day search is not complete')
        target = self.dir / 'scientific-knowledge' / day
        self.require_current_teacher_inputs(day)
        key = day + '-accumulated'
        code, log = self.child('lessons', key, 'frankie_box_scientific_teacher.sh',
                               dict(SEARCHES=search['target'], BRAIN=self.plan.get('brain') or str(BRAIN),
                                    ACCUMULATED_DAY=day, ACCUMULATED_OUT=target))
        # Retain the existing lesson CPU booking and knowledge boundary under this day-local receipt.
        for retained in (self._cpu, self._knowledge):
            if ('lessons', key) in retained:
                retained[('accumulated_lessons', day)] = retained.pop(('lessons', key))
        receipt = target / 'receipt.json'
        saved = self.child_saved('accumulated_lessons', day, code, log, accumulated_out=str(target))
        if saved:
            return saved
        if code != 0 or not receipt.is_file():
            return self.record('accumulated_lessons', day, 'failed', exit_code=code, log=log,
                               reason='no completed accumulated scientific lesson receipt after the call')
        result = json.loads(receipt.read_bytes())
        if (result.get('schema') != 'FRANKIE_ACCUMULATED_LESSONS_V1' or result.get('day') != day or
                result.get('status') != 'complete' or
                result['search']['sha256'] != sha256_file(Path(search['target']) / 'MANIFEST.json')):
            raise ValueError('accumulated scientific lesson receipt differs from its owning day search')
        return self.record('accumulated_lessons', day, 'done', exit_code=code, log=log,
                           receipt=str(receipt), receipt_sha256=sha256_file(receipt),
                           accumulated_claim_tests=result['accumulated_claim_tests'])

    def lessons(self, batch_key, entries):
        self.check_save()
        # the searched days: a finished search WITH a manifest; a not_run search (no causal axis) is finished for the day
        # but supplies no search to test claims on: listed, never passed as a path to the teacher
        searched = [e for e in self.plan['days'] if e['role'] == 'discovery' and self.finished('search', e['day'])
                    and (self.receipt('search', e['day']) or {}).get('status') != 'not_run']
        not_run = [e['day'] for e in self.plan['days'] if (self.receipt('search', e['day']) or {}).get('status') == 'not_run']
        if not_run:
            self.log('lessons %s: no search to test on for %s (search not_run: no causal axis); listed' % (batch_key, not_run))
        remote = [e['day'] for e in searched if self.remote_root(e['day'])]
        if remote:
            return self.record('lessons', batch_key, 'waiting', remote_days=remote,
                               reason='shared batch claim testing must consume each owning lane result; '
                                      'remote search receipts do not make worker-local artifacts readable here')
        if not searched:
            return self.record('lessons', batch_key, 'waiting', reason='no discovery-day search finished yet')
        searches = ','.join(str(SEARCH / e['day'] / ('cycle-' + CYCLE) / 'discovery') for e in searched)
        calls = []
        if self.plan['historical_claims']:
            calls.append(('historical', dict(HISTORICAL_CLAIMS=self.plan['historical_claims'])))
        for e in entries:
            if e.get('jev_stamp'):
                calls.append(('jev-%s' % e['day'], dict(JEV_STAMP=e['jev_stamp'])))
            ledgers = e.get('frankie_ledgers')
            if not ledgers and e['classroom_arm'] and not self.queue_owned(e):   # queued days: the class worker calls it
                # the day's own classroom ledgers: the scientific teacher reads only their novel findings (R09)
                c = self.receipt('classroom', e['day'])
                if c and c['status'] in ('done', 'reused') and c.get('classroom') and \
                        (Path(c['classroom']) / 'ledgers.json').is_file():
                    ledgers = str(Path(c['classroom']) / 'ledgers.json')
            if ledgers:
                calls.append(('frankie-%s' % e['day'], dict(FRANKIE_LEDGERS=ledgers, FRANKIE_DAY=e['day'])))
        if not calls:
            rec = self.record('lessons', batch_key, 'skipped', reason='no claims named: no historical claims file and no '
                                                                      'Jev or Frankie claims for the days of this batch')
            self.survivors(batch_key, entries)     # the batch boundary still updates over every earlier lesson in the brain
            return rec
        results = []
        for name, env in calls:
            try:
                written = self.lessons_written(name, [e['day'] for e in searched],
                                               frankie_ledgers=env.get('FRANKIE_LEDGERS'),
                                               jev_stamp=env.get('JEV_STAMP'))
            except (ValueError, OSError) as error:
                return self.record('lessons', batch_key, 'waiting', calls=results, pending_claims=name,
                                   requested_search_days=[e['day'] for e in searched], reason=str(error))
            if written:                           # already taught: a second call would decline (duplicate data)
                import frankie_box_scientific_teacher as ST
                for path in written:
                    if name.startswith('jev-'):
                        ST.upload_jev_lessons(path, os.environ.get('MAP_URL'), log=self.log)
                    ST.publish_lessons(path, brain_dir=self.plan.get('brain') or str(BRAIN), log=self.log)
                results.append(dict(claims=name, exit_code=0, reused=[str(w) for w in written]))
                continue
            code, log = self.child('lessons', '%s-%s' % (batch_key, name), 'frankie_box_scientific_teacher.sh',
                                   dict(env, SEARCHES=searches, BRAIN=self.plan.get('brain') or str(BRAIN)))
            # the teacher child's own receipt (FRANKIE_SCIENTIFIC_TEACHER_RECEIPT_V1, printed as its last line; school_recovery
            # 2026-10-07): carried on the call for the one-day reporter; absent = None (never inferred from the exit code)
            results.append(dict(claims=name, exit_code=code, log=log, receipt=last_json_line(log)))
            if code == SAVED_EXIT and (self._cpu.get(('lessons', '%s-%s' % (batch_key, name))) or {}).get('status') != 'waiting':
                # school R6 (stacks pass 2026-10-07): the teacher child saved at a save point (exit 75, its pre-read and
                # written documents kept): no following call is started after a save; the calls not started are listed
                results += [dict(claims=later, exit_code=None, not_started='a teacher call before it saved') for later, _ in
                            calls[[c[0] for c in calls].index(name) + 1:]]
                break
        saved, bad = classify_child_calls(results)
        if saved:
            # never a failure or a requeue: the batch is 'saved' (not FINISHED), re-run on the next start; the finished
            # calls' written lessons are reused there (lessons_written), the saved call resumes its own saved state
            return self.record('lessons', batch_key, 'saved', calls=results, exit_code=SAVED_EXIT,
                               searched_days=[e['day'] for e in searched], not_run_days=not_run or None,
                               reason='%d teacher call(s) saved at a save point (exit 75): kept; the next start re-runs the '
                                      'batch, which reuses the written lessons and the saved pre-read' % len(saved))
        rec = self.record('lessons', batch_key, 'failed' if bad else 'done', calls=results,
                          searched_days=[e['day'] for e in searched], not_run_days=not_run or None,
                          reason='%d teacher call(s) failed' % len(bad) if bad else None)
        if not bad:
            self.survivors(batch_key, entries)
        return rec

    def survivors(self, batch_key, entries):
        """Stage 10 at the batch boundary (frankie_box_survivor_update.sh; school_recovery 2026-10-07): after the batch's
        lessons are recorded finished, the survivor/candidate update over every brain entry at the boundary, keyed by the
        batch's LAST day in plan order (a batch of one day is a boundary), on the day's held lane ('survivors' in
        cores.DAY_RUN_STAGES). Recorded as stage 'survivors' under the batch key with the child's printed receipt
        (FRANKIE_SURVIVOR_UPDATE_RECEIPT_V1, its last line). The update freezes its selection once (inputs.json): a
        repeated call reproduces the same bytes; consumed only by LATER classrooms. Never a gate on the day."""
        if self.finished('survivors', batch_key):
            return self.receipt('survivors', batch_key)
        days = [e['day'] for e in entries]
        if not days:
            return self.record('survivors', batch_key, 'skipped', reason='an empty batch has no boundary')
        searches = []
        listed = []
        for d in days:
            r = self.receipt('search', d) or {}
            if r.get('status') in ('done', 'reused') and r.get('target') and (Path(r['target']) / 'MANIFEST.json').is_file():
                searches.append('%s=%s' % (d, r['target']))
            else:
                listed.append('%s: search %s' % (d, r.get('status') or 'not run'))
        env = dict(RUN=self.plan['run'], BOUNDARY_DAY=days[-1], BATCH_DAYS=','.join(days),
                   BRAIN=self.plan.get('brain') or str(BRAIN))
        if searches:
            env['SEARCHES'] = ','.join(searches)
        try:
            code, log = self.child('survivors', batch_key, 'frankie_box_survivor_update.sh', env)
        except (ValueError, OSError) as error:   # a refusal of the dispatch is this stage's own failure, never the batch's
            return self.record('survivors', batch_key, 'failed', boundary_day=days[-1], batch_days=days,
                               reason='%s: %s' % (type(error).__name__, error))
        saved = self.child_saved('survivors', batch_key, code, log, boundary_day=days[-1], batch_days=days)
        if saved:
            return saved
        receipt = last_json_line(log)
        bound = isinstance(receipt, dict) and receipt.get('schema') == 'FRANKIE_SURVIVOR_UPDATE_RECEIPT_V1' and \
            receipt.get('boundary_day') == days[-1] and receipt.get('run') == self.plan['run']
        fields = dict(exit_code=code, log=log, boundary_day=days[-1], batch_days=days, searches_listed=listed or None,
                      inspection=dict(inputs=dict(env={k: str(v) for k, v in env.items()}, listed=listed),
                                      use=dict(bound_receipt=bound, rule='the child\'s printed receipt counts only when its '
                                                                         'schema, run and boundary day are this call\'s'),
                                      outputs=dict(receipt=(receipt or {}).get('receipt') if bound else None,
                                                   counts=(receipt or {}).get('counts') if bound else None,
                                                   publication=(receipt or {}).get('publication') if bound else None)))
        if code == 0 and bound:
            done = self.record('survivors', batch_key, 'done', receipt=receipt.get('receipt'), survivors=receipt.get('survivors'),
                               counts=receipt.get('counts'), publication=receipt.get('publication'),
                               listed_count=receipt.get('listed'), integrity_failures=receipt.get('integrity_failures'),
                               late_knowledge=receipt.get('late_knowledge'), all99_coverage=receipt.get('all99_coverage'),
                               workflow_report=receipt.get('workflow_report'), **fields)
            # R-A (fresh review) with F-1 (follow-up review): the candidates receipt is a late piece of the batch's arm days
            # whose reports are done. Nothing is rendered from this boundary slot (a day stays on its own lane; guarded()
            # would run that day's successor drain here, which refuses off its held lane): a day with an unacknowledged
            # correction is skipped (its own drain revises it); for the others the read-only check (reports_stale) runs and
            # a 'changed' outcome is recorded on that day's reports step as late_pieces (Run.reports_late_pieces), so that
            # day's own lane revises it at its next finish/start. A finished reports step is never re-recorded here.
            notes = []
            for entry in entries:
                if not entry.get('classroom_arm') or (self.receipt('reports', entry['day']) or {}).get('status') != 'done':
                    continue
                pending = self.unacknowledged_corrections(entry['day'])
                if pending:
                    notes.append(dict(day=entry['day'], disposition='skipped', reason='unacknowledged correction(s) %s: '
                                      'the day\'s own drain revises its reports' % ', '.join(pending)))
                    continue
                try:
                    stale = self.reports_stale(entry)
                    notes.append(dict(day=entry['day'], disposition='stale_recorded' if stale else 'current',
                                      reason='revised on the day\'s own lane at its next finish/start' if stale else None))
                except Exception as error:  # noqa: BLE001 - never this stage's outcome and never the day's reports step
                    notes.append(dict(day=entry['day'], disposition='not_checked', reason='%s: %s' % (type(error).__name__, error)))
            if notes:
                self.log('survivors %s: reports of the batch\'s arm days: %s' % (batch_key, json.dumps(notes, sort_keys=True)))
                try:
                    from frankie_box_durable import write_json
                    write_json(self.receipt_path('survivors', batch_key), dict(done, reports_late_pieces=notes))
                    done = dict(done, reports_late_pieces=notes)
                except Exception as error:  # noqa: BLE001 - accounting only; logged
                    self.log('survivors %s: the reports note could not be recorded (%s: %s)' % (batch_key, type(error).__name__, error))
            return done
        return self.record('survivors', batch_key, 'failed', reason='no survivor update receipt bound to this boundary after the '
                                                                    'step (exit %s; its log names why)' % code, **fields)

    def lessons_written(self, name, searched_days, *, frankie_ledgers=None, jev_stamp=None):
        """Reuse only a completed standalone operation covering these exact current inputs.

        Existing but changed/legacy work remains intact and requires an explicit successor;
        absence alone returns [] and permits the ordinary first call.
        """
        import frankie_box_scientific_teacher as ST
        import frankie_box_experiment_review as REVIEW
        import frankie_box_lane_state as LS
        if name == 'historical':
            path = self.historical_lessons(searched_days)
        else:
            kind, _, day = name.partition('-')
            if kind not in ('frankie', 'jev'):
                return []
            if kind == 'jev' and not jev_stamp:
                raise ValueError('Jev lesson reuse needs the exact requested stamp')
            path = (LESSONS_ROOT / 'jev' / ('%s-%s.json' % (day, jev_stamp)) if kind == 'jev' else
                    LESSONS_ROOT / 'frankie' / ('%s-frankie.json' % day))
        if path is None or not path.is_file():
            return []
        lesson = json.loads(path.read_bytes())
        operation_pin = (lesson.get('scientific_operation') or {}).get('inputs')
        if not operation_pin or not searched_days:
            raise ValueError('retained lessons lack exact requested operation coverage; checked successor required: %s' % path)
        frozen = json.loads(REVIEW._read_pin(operation_pin))
        if name == 'historical':
            current = ST.historical_claims(self.code_root / self.plan['historical_claims'], records_selection=[])
        elif kind == 'frankie':
            if frankie_ledgers is None:
                raise ValueError('Frankie lesson reuse needs the exact current ledgers')
            current = ST.frankie_claims(frankie_ledgers, day)
        else:
            current = ST.jev_claims(frozen['selection']['doc']['source'])
            if current['stamp'] != jev_stamp or current['day'] != day:
                raise ValueError('retained Jev lessons belong to another claim request')
        searches = ST.load_searches([SEARCH / d / ('cycle-' + CYCLE) / 'discovery' for d in searched_days])
        # The existing operation freezer is read-only for a retained result: it refuses
        # changed claims/searches/readers/records and never invents a legacy operation.
        brain = self.plan.get('brain') or str(BRAIN)
        operation, _ = ST.freeze_operation(current, searches, LESSONS_ROOT, brain)
        if operation != operation_pin:
            raise ValueError('retained lesson belongs to another frozen scientific operation')
        REVIEW._validate_operation(REVIEW._transition_operation(operation, lesson), lesson)
        REVIEW.require_current([dict(path=str(path), sha256=sha256_file(path), content=lesson)],
                               REVIEW.corrections(LS.knowledge_roots(brain)))
        return [path]

    def batch_of(self, day):
        for role in ('discovery', 'confirmation'):
            role_days = [e['day'] for e in self.plan['days'] if e['role'] == role]
            if day in role_days:
                return '%s-%02d' % (role, role_days.index(day) // BATCH + 1)
        return None

    # the loop
    def start(self, stages):
        days = self.plan['days']
        total = len(days) * sum(s not in ('teacher', 'lessons') for s in stages)
        done = [0]

        def tick(stage, key):
            done[0] += 1
            self.probe.update('%s:%s' % (stage, key), min(done[0], total) if total else 0, total or None)

        def per_day(stage, fn, parallel):
            # E-1: a finished external step that has not settled the day file (an older receipt without the S3 check,
            # or one recorded on a dispatch without the S3 listing) runs again; the rest of the day waits on it
            todo = [e for e in days if not self.finished(stage, e['day'])
                    or (stage == 'external' and not self.external_ready(e)[0])]
            for e in days:
                if e not in todo:
                    tick(stage, e['day'])
            if parallel > 1:
                with ThreadPoolExecutor(parallel) as pool:
                    for e, r in zip(todo, pool.map(fn, todo)):
                        tick(stage, e['day'])
            else:
                for e in todo:
                    if self.stopped:
                        return
                    fn(e)
                    tick(stage, e['day'])

        # the ROOT line (--root-queue on): a day enters it the moment it is ROOT-ready (right after its external step), and
        # the ROOTs run in arrival order in the free day-run slots; this run then waits for its own days
        root_line = 'root' in stages and getattr(self.a, 'root_queue', 'off') == 'on'

        def external_then_line(e):
            r = self.external(e)
            if root_line and not self.stopped and (self.root_enqueue(e) or {}).get('status') == 'queued':
                self.kick('root')
            return r

        for stage, parallel in (('fetch', 1), ('ingest', self.a.parallel_days), ('external', self.a.parallel_days),
                                ('root', self.a.parallel_days)):
            if stage in stages and not self.stopped:
                if stage == 'external' and root_line:
                    per_day(stage, external_then_line, parallel)
                elif stage == 'root' and root_line:
                    todo = [e for e in days if not self.finished('root', e['day'])]
                    for e in todo:
                        if not self.stopped:
                            self.root_enqueue(e)
                    # the whole day is the ROOT line's (Greg, 2026-09-30: a day never leaves its slot until every kept
                    # step of the run table is done): its worker runs ROOT, teacher, data, search, lessons, the class and
                    # Jev in the day's one held slot, so this start neither waits for the ROOTs nor runs any later step
                    self.kick('root')
                    for e in days:
                        tick(stage, e['day'])
                else:
                    per_day(stage, getattr(self, stage), parallel)
        by_role = [[e for e in days if e['role'] == role] for role in ('discovery', 'confirmation')]
        batches = [(role_days[0]['role'], i // BATCH + 1, role_days[i:i + BATCH])
                   for role_days in by_role if role_days for i in range(0, len(role_days), BATCH)]
        inspected = set()
        for role, n, entries in batches:
            if self.stopped or root_line:            # with the ROOT line on, every step after ROOT runs in the day's slot
                break
            key = '%s-%02d' % (role, n)
            if 'teacher' in stages and not self.finished('teacher', key):
                self.teacher(key, entries)
            # the classroom arm: the arm days one after another in plan order (each carries the previous arm day's
            # history; the day's report number is reserved right after it), then Jev's material; other days skip
            # with the class line on (--frankie-queue on), an arm day ENTERS the line here instead (arrival order, one class
            # at a time by the class worker, which also reserves its report number = its school day)
            enqueued = False
            for stage in ('classroom', 'jev'):
                if stage in stages and not self.stopped:
                    for e in entries:
                        owned = stage == 'classroom' and self.queue_owned(e)
                        if not self.stopped and not self.finished(stage, e['day']):
                            r = self.enqueue_classroom(e) if owned else getattr(self, stage)(e)
                            enqueued = enqueued or (owned and (r or {}).get('status') == 'queued')
                        if stage == 'classroom' and not owned and {'jev', 'school', 'reports'} & set(stages):
                            self.reserve_after_classroom(e)
                        tick(stage, e['day'])
            if enqueued:
                self.kick('class')
            for stage, parallel in (('data', self.a.parallel_days), ('search', 1)):
                if stage in stages and not self.stopped:
                    todo = [e for e in entries if not self.finished(stage, e['day'])]
                    if parallel > 1:
                        with ThreadPoolExecutor(parallel) as pool:
                            list(pool.map(getattr(self, stage), todo))
                    else:
                        for e in todo:
                            if not self.stopped:
                                getattr(self, stage)(e)
                    for e in entries:
                        tick(stage, e['day'])
            if 'lessons' in stages and not self.stopped:
                for e in entries:
                    if not e['classroom_arm'] and not self.finished('accumulated_lessons', e['day']):
                        self.guarded('accumulated_lessons', e)
            if 'lessons' in stages and role == 'discovery' and not self.stopped and not self.finished('lessons', key):
                self.lessons(key, entries)
            elif 'lessons' in stages and role == 'discovery' and not self.stopped and not self.finished('survivors', key):
                self.survivors(key, entries)       # the boundary of a batch whose lessons finished before stage 10 existed
            # after the lessons: the three-way exchange of each arm day, its meeting, the school knowledge
            # base, then the day reports (they carry the exchange; rebuilt once when it arrives after them)
            for stage in ('exchange', 'voice', 'school', 'reports'):
                if stage in stages and not self.stopped:
                    for e in entries:
                        if not self.stopped and not self.queue_owned(e) and (not self.finished(stage, e['day']) or
                                                                             (stage == 'reports' and self.reports_stale(e))):
                            self.guarded(stage, e)       # a class-line day's class side is the class worker's
                        tick(stage, e['day'])
            # the one-day inspection after the batch's last stage loop (the ROOT line writes its own after _finish_day):
            # every piece's record of what it received, used and produced, whatever the day's outcome; never a gate
            if {'reports', 'lessons'} & set(stages) and not self.stopped:
                for e in entries:
                    if not self.queue_owned(e) and self.inspection_on():
                        self.inspect_day(e['day'], 'start: after the batch %s last stage loop' % key)
                        inspected.add(e['day'])
        if self.stopped and self.inspection_on():
            # F3 (second review): the disk floor stopped this start; every day it owns still gets its inspection, the
            # trigger naming the stop (the reporter writes small markdown only; its own failure is on its receipt)
            for e in days:
                if e['day'] not in inspected and not self.queue_owned(e):
                    self.inspect_day(e['day'], 'start: stopped at the disk floor before the day\'s last stage (stage %s, free %s '
                                               'bytes, floor %s bytes)' % (self.stopped.get('stage'), self.stopped.get('free_bytes'),
                                                                           self.stopped.get('floor_bytes')))
        # every start kicks the workers of lines that hold days not done (a waiting day resumes without a dispatch)
        import frankie_box_frankie_queue as Q
        for line, on in (('root', getattr(self.a, 'root_queue', 'off')), ('class', getattr(self.a, 'frankie_queue', 'off'))):
            try:
                pending = on == 'on' and any(x['state'] != 'done' for x in Q.load(line)['entries'])
            except (OSError, ValueError, SystemExit) as error:
                self.log('the %s line could not be read (%s)' % (line, error))
                pending = False
            if pending:
                self.kick(line)
        return self.summary(stages)

    def queue_listing(self):
        """This run's days in Frankie's two lines (seq, state, reason, school day), for the summary; a day of the run that
        is in neither line is not listed here (its steps are in `days` above)."""
        import frankie_box_frankie_queue as Q
        out = {}
        for line in Q.LINES:
            try:
                doc = Q.load(line)
            except (OSError, ValueError, SystemExit) as error:
                out[line] = dict(unreadable=str(error))
                continue
            out[line] = [{k: x.get(k) for k in ('seq', 'day', 'state', 'reason', 'where', 'school_day', 'done_seq')}
                         for x in Q.ordered(doc) if x['run'] == self.plan['run']]
        return out

    def summary(self, stages):
        import frankie_box_successor_dispatch as S
        successors = S.status(self.dir)
        rows = {}
        for e in self.plan['days']:
            rows[e['day']] = {s: (self.receipt(s, e['day']) or {}).get('status') for s in stages if s not in ('teacher', 'lessons')}
        batches = {}
        for p in sorted((self.dir / 'batches').glob('*/*.json')) if (self.dir / 'batches').is_dir() else ():
            r = json.loads(p.read_bytes())
            batches['%s/%s' % (r['key'], r['stage'])] = r['status']
        unfinished = sorted({(k, s) for k, v in rows.items() for s, st in v.items()
                             if not done_status(self.receipt(s, k)) and not (self.receipt(s, k) or {}).get('not_wired')
                             and not (s == 'voice' and (self.receipt(s, k) or {}).get('non_blocking'))})
        unfinished = sorted(set(unfinished) | {(r['day'], 'successors') for r in successors if r['status'] != 'done'})
        not_wired = sorted({(k, s) for k, v in rows.items() for s, st in v.items()
                            if (self.receipt(s, k) or {}).get('not_wired') and not done_status(self.receipt(s, k))})
        unfinished_batches = sorted(k for k, status in batches.items() if status not in FINISHED)
        # This is operational accounting for the requested stages, never an E2E verdict.
        # Keep non-blocking meeting semantics, but unimplemented work cannot imply completion.
        state = ('stopped_disk_floor' if self.stopped else
                 'incomplete' if unfinished or not_wired or unfinished_batches else 'complete')
        handed_off = sorted(k for k in rows if (self.receipt('jev', k) or {}).get('status') == HANDED_OFF)
        out = dict(schema=SCHEMA, run=self.plan['run'], plan_sha256=plan_digest(self.plan), stages=list(stages), days=rows,
                   completion_scope='requested_stages', omitted_stages=[s for s in STAGES if s not in stages],
                   status=state, unfinished_batches=unfinished_batches,
                   left_out=self.plan['left_out'], successors=successors,
                   batches=batches, stopped=self.stopped, free_bytes=shutil.disk_usage(BOX_ROOT).free,
                   unfinished=[dict(day=k, stage=s) for k, s in unfinished],
                   not_wired=[dict(day=k, stage=s, reason=(self.receipt(s, k) or {}).get('reason')) for k, s in not_wired],
                   meeting_waiting=[dict(day=k, reason=r.get('reason'), meeting_status=r.get('meeting_status'))
                                    for k in rows for r in [self.receipt('voice', k) or {}]
                                    if r.get('non_blocking')],
                   waiting_for_pod=[dict(day=k, material_sent=(self.receipt('jev', k) or {}).get('material_sent'),
                                         pod=((self.receipt('jev', k) or {}).get('dispatches') or {}).get('pod'))
                                    for k in handed_off],
                   frankie_queue=self.queue_listing(),
                   model_calls=sum((self.receipt('voice', k) or {}).get('model_calls', 0) for k in rows))
        tmp = self.dir / 'summary.pending'
        tmp.write_text(json.dumps(out, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(tmp, self.dir / 'summary.json')
        self.probe.update('summary:requested_stages', state=state)
        return out


def preview(plan):
    """ACTION=plan: what each day and step would do, from what is on the box. Writes nothing."""
    out = []
    for e in plan['days']:
        receipt, why = ingest_of(e)
        rows, source = rows_of(e)
        target = DATA / e['day'] / ('cycle-' + CYCLE)
        search = SEARCH / e['day'] / ('cycle-' + CYCLE) / (e['role'] or '?')
        out.append(dict(day=e['day'], cls=e['cls'], role=e['role'], classroom_arm=e['classroom_arm'],
                        manifest=e['manifest'],
                        ingest=str(receipt.parent) if receipt else ('REFUSED: ' + why if why else 'to ingest'),
                        root=next((str(p) for p in ROOTS.glob('%s-%s*' % (plan['run'], e['day']))
                                   if (p / 'calculations-receipt.json').is_file()), e.get('calculations') or 'to run'),
                        dipole_rows=('%s (%s)' % (rows, source)) if rows else 'batch (1 day in 5)',
                        external=(lambda d: ('attached ' + str(attached_day_file(d)[0])) if d and attached_day_file(d)[0]
                                  else 'to attach')(receipt.parent if receipt else None),
                        classroom=('V2, PREVIOUS carried' if e['classroom_arm'] else 'not an arm day'),
                        exchange=('after the batch lessons (three-way, code only)' if e['classroom_arm'] and
                                  e['role'] == 'discovery' else 'not an arm day'),
                        voice='bounded meeting; missing runtime is non-blocking' if e['classroom_arm'] else 'not an arm day',
                        school=('<brain>/school/%s.json after the exchange' % e['day'] if e['classroom_arm'] and
                                e['day'] != MONDAY else 'not in the school'),
                        data='exported' if (target / 'MANIFEST.json').is_file() else 'to export',
                        search='searched' if (search / 'MANIFEST.json').is_file() else 'to search'))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--action', required=True, choices=('plan', 'start', 'status', 'successor-request',
                                                      'successor-decision', 'successor-retry', 'successor-save',
                                                      'successor-resume', 'voice-dispatched', 'voice-returned'))
    p.add_argument('--voice-day', help='the classroom-arm day of a remote (GitHub) meeting dispatch record')
    p.add_argument('--voice-github-run', help='voice-dispatched: the GitHub run id the operator dispatched for the standing intent')
    p.add_argument('--voice-github-attempt', default='1', help='voice-dispatched: that run\'s attempt number (default 1)')
    p.add_argument('--voice-archive', help='voice-returned: the downloaded runner-state.zip (owner-local absolute path)')
    p.add_argument('--voice-archive-sha256', help='voice-returned: its SHA256 from the run\'s runner-state.json')
    p.add_argument('--voice-conclusion', choices=('success', 'failure', 'cancelled', 'timed_out', 'lost'),
                   help='voice-returned: the GitHub run\'s conclusion as read by the operator (lost = expired/unreadable state)')
    p.add_argument('--voice-by', default='operator', help='who records the dispatch/return')
    p.add_argument('--successor-day', help='existing owner day for explicit successor intake')
    p.add_argument('--successor-file', help='JSON request, decision, or exact failure witness; no execution at intake')
    p.add_argument('--successor-id', help='content-addressed request id for decision/retry')
    p.add_argument('--run', required=True, help='the run name: /opt/frankie-box/work/experiment/<run>')
    p.add_argument('--commit', required=True)
    p.add_argument('--code-root', required=True)
    p.add_argument('--plan', help='a plan JSON (days with overrides, class, classroom_arm), absolute or repo-relative')
    p.add_argument('--days', help='comma list of YYYYMMDD (added to the plan file\'s days)')
    p.add_argument('--day-class', help='monday | midweek | thursday | friday (classes never mix)')
    p.add_argument('--classroom-arm', help='comma list of the classroom-arm days (DIGEST=on for their ROOT); default the cycle')
    p.add_argument('--classroom-arm-cycle', default='5/5',
                   help='ON/CYCLE: the classroom arm on the first ON of every CYCLE discovery days in date order. Default '
                        '5/5 = every day (Greg, 2026-09-29, later: "Just run every pair will get teach and class. It\'s '
                        'easier that way unless we see that process is taking a long time"); 2/5 = days 1 and 2 of five')
    p.add_argument('--frozen-survivors', help='the frozen survivor list (required for any confirmation day)')
    p.add_argument('--historical-claims',
                   default='research/kalshi/frankie_boss/knowledge/HISTORICAL_CLAIMS_V1-9dc79ca359e9.json',
                   help='a committed knowledge/HISTORICAL_CLAIMS_V1-*.json (repo-relative); default the combined Dipole collection')
    p.add_argument('--stages', default=','.join(STAGES), help='comma list, run in the fixed order %s' % ','.join(STAGES))
    p.add_argument('--lags', type=int, default=20)
    p.add_argument('--transforms', help='the search transforms (comma list; default all)')
    p.add_argument('--ingest-workers', type=int, default=31,
                   help='a ceiling on the WORKERS of each ingest day process; a lone day books the plan\'s day size (32 on a '
                        '--day-cpus 32 run) or auto, days side by side share the box (Run.ingest_size); WORKERS = its CPUs '
                        'less one unless this ceiling is lower')
    # full + sequential until observation_replay feeds the teacher's walk: the Dipole teacher reads the stored observation
    # (a none-mode day would get no Dipole rows); the parallel writer is none-mode only (--ingest-mode parallel then)
    p.add_argument('--ingest-mode', choices=('sequential', 'parallel'), default='sequential')
    p.add_argument('--ingest-observation', choices=('full', 'none'), default='full')
    p.add_argument('--ingest-verify', choices=('inline', 'deferred'), default='deferred')
    # the CPU booking sets these (Greg, 2026-09-29: "They all get the same 16 and workers"): every day-run step books 16
    # CPUs and runs 15 workers; the three flags are kept so a dispatch that names them still parses, and are not used
    p.add_argument('--data-workers', type=int, default=1, help='not used: ROOT runs 15 workers in its booked 16 CPUs')
    p.add_argument('--search-workers', type=int, default=8, help='not used: the search runs 15 workers in its booked 16')
    p.add_argument('--teacher-cpus', type=int, default=0, help='not used: the teacher splits its booked 16 CPUs')
    p.add_argument('--parallel-days', type=int, default=2,
                   help='days at once for the ingest, external, root and data steps (2 = the two main-box lanes); each day-run '
                        'step books 16 CPUs, so a day that cannot book them waits (32 CPUs = two at once)')
    p.add_argument('--external-history-run', help='the frankie_day_history GitHub run id whose S3 objects the day files '
                                                  'are built from (frankie/day_history/<id>/)')
    p.add_argument('--external-eia930-history-run', help='optional second day_history run id the eia930 family of the '
                                                         'day files is read from (both ids recorded in each day file)')
    p.add_argument('--external-family-history-runs', help='optional family=<run id>,... families of the day files read '
                                                          'from other day_history runs (the gap-only fetch chunks)')
    p.add_argument('--external-wait', choices=('on', 'off'), default='on',
                   help='on: a day\'s root, teacher, classroom, data and search wait for its day file (default)')
    p.add_argument('--brain', default=str(BRAIN), help='Frankie\'s brain (the classroom and day-file entries)')
    p.add_argument('--jev-brain', help='Jev\'s brain directory on the box (default %s)' % JEV_BRAIN)
    p.add_argument('--shared-market-policy', choices=(SHARED_MARKET_POLICY,),
                   help='the synchronized shared market input of a NEW run (Greg, 2026-10-07): saved with the plan at its '
                        'first start; every ROOT runs --bedrock on under it (the native pass that produces native.member and '
                        'native.lifecycle, the only carriers of 18 of the 99 entries) and every teacher reads it; a completed '
                        'legacy ROOT or teacher result never satisfies it (preserved; an explicit compatible successor is '
                        'required). DEFAULT for every NEW run (no saved plan yet); an existing run keeps its saved plan\'s '
                        'value (an old saved request is never mutated)')
    p.add_argument('--previous-classroom', help='the run\'s first arm day: PREVIOUS = this <root>/work/classroom '
                                                '(default: the latest earlier classroom day on the box)')
    p.add_argument('--voice-route', choices=('local', 'github'), default='local',
                   help='the bounded meeting\'s host (Step 6): local = the configured meeting child on the owning lane '
                        '(default); github = the standard CPU runner workflow, dispatched BY HAND against the immutable '
                        'intent Run.voice writes first and admitted for that exact GitHub run (voice-dispatched / '
                        'voice-returned); saved with the plan at the first start')
    p.add_argument('--native-cutoff-seconds', type=float, help='the classroom native-entry pass wall-time cutoff (saved with '
                   'the plan; default unset = the classroom\'s 3600 s)')
    p.add_argument('--native-cutoff-rss-gb', type=float, help='the classroom native-entry pass resident-memory cutoff in GB '
                   '(saved with the plan; default unset = 48)')
    p.add_argument('--native-cutoff-check-every', type=int, help='check the cutoff every N pictures (saved with the plan; '
                   'default unset = 10000)')
    p.add_argument('--day-cpus', type=int, choices=_cores().DAY_RUN_SIZES,
                   help='the day slot size, saved with the plan at the first start: one of %s (frankie_box_cores.DAY_RUN_SIZES; '
                        '16 = the default, one lane; 32 = Greg 2026-10-07, ONE booking the day holds across all its stages; '
                        '64 = the whole 64-vCPU box, session 8)' % (_cores().DAY_RUN_SIZES,))
    p.add_argument('--inspection', choices=('auto', 'one_day', 'off'), default='auto',
                   help='the per-piece status reports (frankie_box_workflow_inspection, Greg 2026-10-07: the ONE-day run '
                        'only), saved with the plan at the first start: auto = one_day when the plan holds exactly one '
                        'day, else off; one_day / off = explicit override; an existing run keeps its saved value')
    p.add_argument('--disk-floor-gb', type=float, default=100.0)
    p.add_argument('--frankie-queue', choices=('on', 'off'), default='on',
                   help='on: classroom-arm days enter Frankie\'s class line (arrival FIFO, one class at a time, the class '
                        'worker runs their class side); off: the classroom side runs in this run as before')
    p.add_argument('--root-queue', choices=('on', 'off'), default='on',
                   help='on: ROOT-ready days enter the ROOT line (arrival FIFO to the next free day-run slot, box or Pod) '
                        'and this run waits for its own; off: the ROOTs run here in plan order as before')
    p.add_argument('--queue-worker-seconds', type=int, default=0,
                   help='opt-in (0 = none, the default): the limit of this run\'s wait on its ROOT-line days; a kicked '
                        'worker\'s limit comes only from FRANKIE_QUEUE_MAX_SECONDS (frankie_box_experiment.sh exports it)')
    p.add_argument('--queue-poll-seconds', type=int, default=60,
                   help='accepted for older callers and recorded; nothing polls on it (2026-10-09: every wait is event-driven)')
    a = p.parse_args()
    import re
    if not re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run):
        raise SystemExit('--run: letters, digits, _ and - only')
    stages = [s for s in STAGES if s in set(a.stages.split(','))]
    unknown = set(a.stages.split(',')) - set(STAGES)
    if unknown:
        raise SystemExit('unknown stages %s' % sorted(unknown))
    run_dir = RUNS / a.run
    if a.action.startswith('voice-'):
        if not a.voice_day:
            p.error('%s needs --voice-day' % a.action)
        saved_plan = json.loads((run_dir / 'plan.json').read_bytes())
        run = Run(a, saved_plan, a.code_root, a.commit)
        if a.action == 'voice-dispatched':
            if not a.voice_github_run:
                p.error('voice-dispatched needs --voice-github-run')
            result = run.voice_dispatched(a.voice_day, a.voice_github_run, a.voice_github_attempt, a.voice_by)
        else:
            if not (a.voice_archive and a.voice_archive_sha256 and a.voice_conclusion):
                p.error('voice-returned needs --voice-archive, --voice-archive-sha256 and --voice-conclusion')
            result = run.voice_returned(a.voice_day, a.voice_archive, a.voice_archive_sha256, a.voice_conclusion, a.voice_by)
        print(json.dumps(result, indent=1, sort_keys=True))
        if result.get('status') == 'refused':
            raise SystemExit(3)
        return
    if a.action.startswith('successor-'):
        if not a.successor_day:
            p.error('successor intake needs --successor-day')
        import frankie_box_successor_dispatch as S
        saved_plan = json.loads((run_dir / 'plan.json').read_bytes())
        run = Run(a, saved_plan, a.code_root, a.commit)
        if a.action in ('successor-save', 'successor-resume'):
            print(json.dumps(S.control(run, a.successor_day, a.action == 'successor-save'), sort_keys=True))
            return
        if not a.successor_file:
            p.error('successor request/decision/retry needs --successor-file')
        value = json.loads(Path(a.successor_file).read_bytes())
        import frankie_box_scientific_teacher as ST
        if a.action == 'successor-request':
            result = ST.submit_correction_work(run, a.successor_day, request=value)
        elif a.action == 'successor-decision':
            result = ST.submit_correction_work(run, a.successor_day, successor_id=a.successor_id, decision=value)
        else:
            result = S.retry(run, a.successor_day, a.successor_id, value)
        print(json.dumps(result, sort_keys=True))
        return
    if a.action == 'status':
        summary = run_dir / 'summary.json'
        if not run_dir.is_dir():
            raise SystemExit('no run %s' % run_dir)
        steps = sorted(str(q.relative_to(run_dir)) + ': ' + r['status']
                       for q in run_dir.glob('*/*/*.json') for r in [json.loads(q.read_bytes())]
                       if r.get('schema') == 'FRANKIE_EXPERIMENT_STEP_V1')
        import frankie_box_successor_dispatch as S
        print(json.dumps(dict(run=a.run, plan=json.loads((run_dir / 'plan.json').read_bytes()) if (run_dir / 'plan.json').is_file() else None,
                              steps=steps, summary=json.loads(summary.read_bytes()) if summary.is_file() else None,
                              successors=S.status(run_dir),
                              free_bytes=shutil.disk_usage(BOX_ROOT).free), indent=1, sort_keys=True))
        return
    if a.action in ('plan', 'start') and (run_dir / 'plan.json').is_file():
        # a run keeps one plan: the saved cutoff values stand when none is given (absent stays absent)
        saved_cutoff = json.loads((run_dir / 'plan.json').read_bytes())
        if getattr(a, 'day_cpus', None) is None:
            a.day_cpus = saved_cutoff.get('day_cpus')
        for key in NATIVE_CUTOFF_PLAN_KEYS:
            if getattr(a, key, None) is None:
                setattr(a, key, saved_cutoff.get(key))
    if a.action in ('plan', 'start') and getattr(a, 'inspection', 'auto') == 'auto' and (run_dir / 'plan.json').is_file():
        # a run keeps one plan: its saved inspection flag stands (absent in an older saved plan stays absent = off)
        a.inspection = json.loads((run_dir / 'plan.json').read_bytes()).get('inspection')
    if a.action in ('plan', 'start') and getattr(a, 'shared_market_policy', None) is None:
        # Greg, 2026-10-07: every NEW request selects the shared market timeline with the native pass ON (bedrock on) for
        # every day, so the ROOT produces native.member/native.lifecycle (the only carriers of 18 of the 99 entries). A run
        # with a saved plan keeps exactly that plan's value: an old saved request is never mutated in place.
        saved_plan = run_dir / 'plan.json'
        a.shared_market_policy = (json.loads(saved_plan.read_bytes()).get('shared_market_policy') if saved_plan.is_file()
                                  else SHARED_MARKET_POLICY)
    plan, refused = load_plan(a, a.code_root)
    if refused:        # only rule breaks decline the run (a day listed twice, a bad day, an unknown class or field)
        print(json.dumps(dict(refused=refused, plan=plan), indent=1, sort_keys=True))
        raise SystemExit('the plan is refused (%d reasons above); nothing started' % len(refused))
    if not plan['days']:
        print(json.dumps(dict(left_out=plan['left_out']), indent=1, sort_keys=True))
        raise SystemExit('every day of the plan is left out (reasons above); nothing to run')
    if a.action == 'plan':
        print(json.dumps(dict(plan=plan, plan_sha256=plan_digest(plan), days=preview(plan), stages=stages,
                              presign=' '.join(i for i in presign_items(plan, a.code_root) if not i.startswith('#')),
                              presign_notes=[i for i in presign_items(plan, a.code_root) if i.startswith('#')],
                              free_bytes=shutil.disk_usage(BOX_ROOT).free), indent=1, sort_keys=True))
        return
    saved = run_dir / 'plan.json'
    if saved.is_file():
        if json.loads(saved.read_bytes()) != plan:
            raise SystemExit('%s holds a different plan for this run: a run keeps one plan (start a new run name)' % saved)
    else:
        run_dir.mkdir(parents=True, exist_ok=True)
        saved.write_text(json.dumps(plan, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    run = Run(a, plan, a.code_root, a.commit, log=lambda text: print(text, flush=True))
    # this box is IN USE from the run's start (KeepRunning=true, Greg 2026-10-07); the run's work continues in the
    # detached queue line workers after start() returns, so the clear is theirs (frankie_box_frankie_queue worker end:
    # cleared only when no orchestrator start, line worker or CPU controller is alive on the box; else kept, named)
    keep_running(a.run, True, 'orchestrator start of run %s (stages %s)' % (a.run, ','.join(stages)), 'frankie_box_experiment.py start',
                 log=lambda text: print(text, flush=True))
    try:
        summary = run.start(stages)
    finally:
        keep_running(a.run, False, 'orchestrator start of run %s ended (the line workers keep the box while they run)' % a.run,
                     'frankie_box_experiment.py start', log=lambda text: print(text, flush=True))
    print(json.dumps(summary, indent=1, sort_keys=True))
    if summary['stopped']:
        raise SystemExit(4)
    if summary['unfinished'] or summary['not_wired'] or summary['unfinished_batches']:
        raise SystemExit(3)


if __name__ == '__main__':
    main()
