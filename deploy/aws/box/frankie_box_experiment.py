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
  root     frankie_box_experiment_root.sh             (bedrock off; DIGEST=on only on the classroom-arm days)
  teacher  frankie_box_experiment_teacher.sh DAYS=... (the Dipole rows, 1 day in 5: a batch of up to five days, each its
           own walk; a day whose rows exist is skipped; while the script is not built the batch stops here, listed;
           it takes the day file beside the sealed ingest and builds the BOSS teacher's external section)
  classroom frankie_box_experiment_classroom_v2.sh    (classroom-arm days only, after root + teacher: the 19/171 classroom
           plus the external section; the arm days one after another in plan order, each carrying the previous arm
           day's work/classroom as PREVIOUS; the run's first arm day carries the latest earlier classroom day on the box,
           or the plan's previous_classroom)
           The day's report number N is reserved right after its classroom step (done, reused or refused), where the
           reports used to run, so the numbering is unchanged (frankie_box_experiment_day_reports.reserve_number)
  jev      frankie_box_jev_relay.sh ACTION=material   (classroom-arm days: Jev's material, relayed when the dispatch
           presigned the slots putrange:<jev bucket>/clm-sidecar/<stamp>/material:8; the Jev Pod is its own workflow step
           and cannot be started from the box, so the step records waiting_for_pod with the exact dispatches)
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
           publication. A missing/refused runtime is recorded as non-blocking; completed records are reused.
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
(a later start retries it). The ingest books its own 8 per day process in frankie_box_ingest_block.sh (the same waiting).

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
FINISHED = ('done', 'reused', 'skipped')
HANDED_OFF = 'waiting_for_pod'           # the jev step's end on the box: material relayed, the Pod is its own dispatch
BOX_ROOT = Path('/opt/frankie-box')
WORK = BOX_ROOT / 'work'
RUNS = WORK / 'experiment'
ROOTS = WORK / 'experiment-roots'
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
S3_BUCKET = 'bento-568968024170-us-east-2-an'
JEV_BUCKET = 'frankie-granite42-568968024170-us-east-1'
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
    if getattr(a, 'external_eia930_history_run', None):       # only when given: earlier plans keep their digest
        plan['external_eia930_history_run'] = a.external_eia930_history_run
    if getattr(a, 'external_family_history_runs', None):      # family=<run id>,... (the gap-only fetch chunks)
        runs = {}
        for item in [x for x in a.external_family_history_runs.split(',') if x]:
            fam, _, rid = item.partition('=')
            if fam not in HISTORY_FAMILIES or not rid.isdigit():
                raise SystemExit('--external-family-history-runs: family=<numeric run id>, family one of %s'
                                 % (HISTORY_FAMILIES,))
            runs[fam] = rid
        plan['external_family_history_runs'] = runs
    return plan, refused


DIRECTIVE = 'research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json'
HISTORY_FAMILIES = ('calendar', 'cot', 'storage', 'consensus', 'weather_obs', 'mos', 'eia930')


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


def ingest_of(entry):
    """(receipt path, None) or (None, reason)."""
    if entry.get('ingest'):
        receipt = Path(entry['ingest']) / 'ingestion-receipt.json'
        return (receipt, None) if receipt.is_file() else (None, 'the plan names %s but it holds no ingestion-receipt.json'
                                                                % entry['ingest'])
    found = sealed_ingests(entry['day'])
    if len(found) > 1:
        return None, 'two or more sealed ingests of %s (%s): duplicate data declines the day; name one in the plan' % (
            entry['day'], ', '.join(str(p.parent) for p in found))
    return (found[0], None) if found else (None, None)


def root_of(entry, run):
    """(calculations directory, attempts listed) of the day's finished ROOT, or (None, attempts)."""
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
        raise SystemExit('two finished ROOTs of %s (%s): duplicate data declines the run' % (entry['day'], done))
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


def attached_day_file(ingest_dir):
    """(day file, sha256, None) beside a sealed ingest when it and its receipt agree; (None, None, why) otherwise, and
    why starts with DIFFERS when a file is there but differs from its receipt (never overwritten: refused)."""
    path, receipt = Path(ingest_dir) / DAY_FILE, Path(ingest_dir) / DAY_FILE_RECEIPT
    if not path.is_file():
        return None, None, 'no %s beside the sealed ingest %s' % (DAY_FILE, ingest_dir)
    if not receipt.is_file():
        return None, None, '%s beside %s has no %s' % (DAY_FILE, ingest_dir, DAY_FILE_RECEIPT)
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
    of every day, and Jev's material slots of every classroom-arm day. Listed items only; nothing is presigned here."""
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
        for name in (DAY_FILE, DAY_FILE_RECEIPT):
            items.append('put:%s/frankie/day_external/%s/%s' % (S3_BUCKET, e['day'], name))
    for e in plan['days']:
        if e['classroom_arm']:
            items.append('putrange:%s/clm-sidecar/%s/material:8' % (JEV_BUCKET, jev_stamp(plan, e)))
    return list(dict.fromkeys(items))


# --------------------------------------------------------------------------------------------------------------- run

def done_status(r):
    """A step is finished when done, reused or skipped; a retired Pod handoff is still pending."""
    return bool(r and r['status'] in FINISHED)


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
        sys.path.insert(0, str(self.box))
        from frankie_box_progress import Probe
        import frankie_box_cores
        self.cores = frankie_box_cores     # the box's CPU booking ledger (DAY_RUN_CPUS, ingest_workers, WAITING_EXIT)
        self.probe = Probe(self.dir, request_sha256=plan_digest(plan), phase='experiment')

    def save_requested(self):
        marker = os.environ.get('FRANKIE_LANE_STOP_FILE')
        return bool(marker and Path(marker).is_file())

    def successors(self, day):
        """Explicit owner corrections finish before this day's next dependent operation."""
        import frankie_box_successor_dispatch as S
        completed = S.drain(self, day)
        if completed and (self.receipt('successors', day) or {}).get('acknowledgments') != completed:
            self.record('successors', day, 'done', acknowledgments=completed)
        return completed

    def check_save(self):
        if self.save_requested():
            self.log('day saved on its assigned lane; resume the retained attempt')
            raise SystemExit(75)

    # receipts
    def receipt_path(self, stage, key):
        return self.dir / ('batches' if stage in ('teacher', 'lessons') else 'days') / key / (stage + '.json')

    def receipt(self, stage, key):
        path = self.receipt_path(stage, key)
        return json.loads(path.read_bytes()) if path.is_file() else None

    def finished(self, stage, key):
        done = done_status(self.receipt(stage, key))
        if done and stage in ('exchange', 'voice', 'school', 'reports'):
            self.require_current_teacher_inputs(key)
        return done

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

    def brain_stage(self, day, stage, sources, summary=None, inline_limit=2 * 1024 * 1024):
        """Immediately commit newly available stage knowledge to Frankie's brain before advancing."""
        import frankie_box_brain as BR
        brain = Path(self.plan.get('brain') or str(BRAIN))
        manifest, reused = BR.write_stage_entry(brain, day, stage, sources, summary=summary, inline_limit=inline_limit)
        entry = brain / ('%s-%s' % (day, stage))
        self.log('brain %s %s: %s%s' % (stage, day, entry, ' (reused)' if reused else ''))
        return dict(path=str(entry), reused=reused,
                    manifest_sha256=sha256_file(entry / 'MANIFEST.json'),
                    knowledge_sha256=sha256_file(entry / 'stage-knowledge.json'))

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
        if status in FINISHED and stage != 'successors' and os.environ.get('FRANKIE_LANE_MAILBOX'):
            import frankie_box_lane_state as LS
            LS.boundary(os.environ.get('FRANKIE_LANE_DAY', key[:8]), stage, brain=self.plan.get('brain') or BRAIN)
        fields['knowledge_available'] = self._knowledge.pop((stage, key), None)
        body = dict(schema='FRANKIE_EXPERIMENT_STEP_V1', run=self.plan['run'], stage=stage, key=key, status=status,
                    at=time.time(), commit=self.commit, plan_sha256=plan_digest(self.plan),
                    directive_sha256=(self.plan.get('directive') or {}).get('sha256'), **fields)
        if previous:
            body['previous_attempts'] = (previous.get('previous_attempts') or []) + [
                {k: previous.get(k) for k in ('status', 'at', 'reason', 'exit_code')}]
        from frankie_box_durable import write_json
        write_json(path, body)
        self.log('%s %s: %s%s' % (stage, key, status, (' (%s)' % fields['reason']) if fields.get('reason') else ''))
        return body

    # disk
    def disk_ok(self, stage):
        free = shutil.disk_usage(BOX_ROOT).free
        sizes = []
        for p in (self.dir / 'days').glob('*/%s.json' % stage) if (self.dir / 'days').is_dir() else ():
            r = json.loads(p.read_bytes())
            if r.get('status') == 'done' and isinstance(r.get('new_bytes'), int):
                sizes.append(r['new_bytes'])
        for p in (self.dir / 'batches').glob('*/%s.json' % stage) if (self.dir / 'batches').is_dir() else ():
            r = json.loads(p.read_bytes())
            if r.get('status') == 'done' and isinstance(r.get('new_bytes'), int):
                sizes.append(r['new_bytes'])
        largest = max(sizes) if sizes else 0
        if free - largest < self.floor:
            self.stopped = dict(stage=stage, free_bytes=free, largest_measured_step_bytes=largest, floor_bytes=self.floor,
                                measured_steps=len(sizes),
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
        command = ['sh' if script.endswith('ingest_block.sh') else 'bash', str(self.box / script)]
        if stage in self.cores.DAY_RUN_STAGES:  # exactly 16 CPUs booked, the step under taskset -c <them> (frankie_box_cores.py)
            inside = getattr(self, 'slot_booking', None)   # the day's held slot (ROOT line): its steps never re-book
            command = [sys.executable, '-B', str(self.box / 'frankie_box_cores.py'), 'run', '--kind', 'day-run', '--day', key,
                       '--run', self.plan['run'], '--stage', stage, '--commit', self.commit] + \
                (['--inside', inside] if inside else []) + ['--'] + command
        with open(log_path, 'ab') as out:
            out.write(('\n### %s %s %s at %s\n' % (stage, key, script, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))).encode())
            out.flush()
            start = out.tell()
            code = subprocess.run(command, env=full, stdout=out, stderr=subprocess.STDOUT).returncode
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
    def fetch(self, e):
        receipt, why = ingest_of(e)
        if receipt or why:
            return self.record('fetch', e['day'], 'skipped' if receipt else 'refused',
                               reason='the day is ingested already: %s' % receipt.parent if receipt else why)
        if not e['manifest']:
            return self.record('fetch', e['day'], 'waiting', reason=e['manifest_gap'])
        if not os.environ.get('MAP_URL'):
            return self.record('fetch', e['day'], 'refused', reason='MAP_URL not set: dispatch with presign=<bucket>/<key> '
                                                                    'for every partition of the days')
        if not self.disk_ok('fetch'):
            return None
        code, log = self.child('fetch', e['day'], 'frankie_box_ingest_block.sh', dict(ACTION='fetch', MANIFEST=e['manifest']))
        return self.record('fetch', e['day'], 'done' if code == 0 else 'failed', exit_code=code, log=log,
                           reason=None if code == 0 else 'the fetch refused or failed a partition (its receipt is in the log)')

    def ingest(self, e):
        receipt, why = ingest_of(e)
        if why:
            return self.record('ingest', e['day'], 'refused', reason=why)
        if receipt:
            brain_entry = self.brain_stage(e['day'], 'ingest', [receipt],
                                           summary=dict(ingest=str(receipt.parent), receipt_sha256=sha256_file(receipt)))
            return self.record('ingest', e['day'], 'reused', ingest=str(receipt.parent), receipt=str(receipt),
                               receipt_sha256=sha256_file(receipt), brain_entry=brain_entry)
        if e['day'] == MONDAY:
            return self.record('ingest', e['day'], 'refused', reason='Monday 20211004 is the gold standard: never re-ingested; '
                                                                     'name its sealed ingest directory in the plan')
        if not e['manifest']:
            return self.record('ingest', e['day'], 'waiting', reason=e['manifest_gap'])
        # Greg, 2026-09-29 ("Do 1-5 now"): the experiment's journal is ingested by the parallel writer (saved passes, so a
        # stopped day resumes), with no full-book copy at a group close and the conformance drain deferred; days run side
        # by side (--parallel-days)
        # CPU booking: each day process books its own 8 CPUs, so WORKERS is per day process, never split: the most the 8
        # fit (inline verify 3, deferred 7; frankie_box_cores.INGEST_RULE), capped by --ingest-workers
        share = max(1, min(self.a.ingest_workers, self.cores.ingest_workers(self.a.ingest_verify)))
        env = dict(ACTION='ingest', MANIFEST=e['manifest'], WORKERS=share, MODE=self.a.ingest_mode,
                   OBSERVATION=self.a.ingest_observation, VERIFY=self.a.ingest_verify)
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
        before = set(WORK.glob('ingest-*'))
        code, log = self.child('ingest', e['day'], 'frankie_box_ingest_block.sh', env)
        made = sorted(set(WORK.glob('ingest-*')) - before)
        receipt, why = ingest_of(e)
        if code != 0 or not receipt or why:
            return self.record('ingest', e['day'], 'failed', exit_code=code, log=log, directories=[str(p) for p in made],
                               reason=why or 'no sealed ingest of the day after the step (its directory is kept)')
        brain_entry = self.brain_stage(e['day'], 'ingest', [receipt],
                                       summary=dict(ingest=str(receipt.parent), receipt_sha256=sha256_file(receipt)))
        return self.record('ingest', e['day'], 'done', exit_code=code, log=log, ingest=str(receipt.parent),
                           receipt=str(receipt), receipt_sha256=sha256_file(receipt), new_bytes=new_bytes(receipt.parent),
                           brain_entry=brain_entry)

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
        calc, attempts = root_of(e, self.plan['run'])
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
        if calc:
            retained = json.loads((calc / 'calculations-receipt.json').read_bytes())
            if retained.get('day') != e['day'] or retained.get('day_role') != e['role']:
                raise ValueError('retained ROOT receipt belongs to another day/role')
            sources = [calc / 'calculations-receipt.json', calc / 'work' / 'derive.json',
                       calc / 'work' / 'derivation-digest-full.md']
            if (calc / 'external-computation.json').is_file():
                sources.append(calc / 'external-computation.json')
            brain_entry = self.brain_stage(e['day'], 'root', sources,
                                           summary=dict(calculations=str(calc), role=e['role'],
                                                        root_status=retained.get('status'),
                                                        producer_failures=retained.get('failure_count')))
            return self.record('root', e['day'], 'reused', calculations=str(calc), interrupted_attempts=attempts,
                               receipt_sha256=sha256_file(calc / 'calculations-receipt.json')
                               if (calc / 'calculations-receipt.json').is_file() else None,
                               brain_entry=brain_entry)
        ing = self.receipt('ingest', e['day'])
        if not (ing and ing['status'] in FINISHED):
            return self.record('root', e['day'], 'waiting', reason='the day has no sealed ingest yet (stage ingest)')
        ready, why = self.external_ready(e)
        if not ready:
            return self.record('root', e['day'], 'waiting', reason=why)
        if not self.disk_ok('root'):
            return None
        output = owned_output or ROOTS / ('%s-%s-a%d' % (self.plan['run'], e['day'], len(attempts) + 1))
        # First dispatch and resume both use the central claim's exact directory.
        resume = owned_output is not None and owned_output.is_dir()
        held = self.claim_root(e, output)          # None = no claim store on the box: exactly as before
        if held is not None and not held[0]:
            return self.record('root', e['day'], 'waiting', reason=held[1], claim=held[2])
        env = dict(INGESTION_RECEIPT=ing['receipt'], INGESTION_RECEIPT_SHA256=ing['receipt_sha256'], DAY=e['day'],
                   DAY_ROLE=e['role'], OUTPUT_ROOT=output, DATA_WORKERS=self.cores.DAY_RUN_CPUS - 1,
                   DIGEST='on', RESUME='on' if resume else 'off')
        if self.plan['frozen_survivors']:
            env['FROZEN_SURVIVORS'] = self.plan['frozen_survivors']
        code, log = self.child('root', e['day'], 'frankie_box_experiment_root.sh', env)
        if code != 0 or not (output / 'calculations-receipt.json').is_file():
            self.claim_end(e, output, None, 'the box ROOT attempt ended without calculations-receipt.json (exit %s)' % code)
            return self.record('root', e['day'], 'failed', exit_code=code, log=log, output_root=str(output),
                               interrupted_attempts=attempts, reason='no calculations-receipt.json (the attempt is kept)')
        calc = json.loads((output / 'calculations-receipt.json').read_bytes())
        self.claim_end(e, output, sha256_file(output / 'calculations-receipt.json'), None)
        brain_entry = self.brain_stage(e['day'], 'root',
                                       [output / 'calculations-receipt.json', output / 'work' / 'derive.json',
                                        output / 'work' / 'derivation-digest-full.md'] +
                                       ([output / 'external-computation.json']
                                        if (output / 'external-computation.json').is_file() else []),
                                       summary=dict(calculations=str(output), role=e['role'],
                                                    root_status=calc.get('status'),
                                                    producer_failures=calc.get('failure_count')))
        return self.record('root', e['day'], 'done', exit_code=code, log=log, calculations=str(output),
                           receipt_sha256=sha256_file(output / 'calculations-receipt.json'), new_bytes=new_bytes(output),
                           interrupted_attempts=attempts, digest=True,
                           root_status=calc.get('status'), producer_failures=calc.get('failure_count'),
                           brain_entry=brain_entry)

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
        receipt, _ = ingest_of(e)
        return receipt.parent if receipt else None

    def external_ready(self, e):
        """(True, None) when the day file is attached beside the sealed ingest (or EXTERNAL_WAIT=off), else (False, why)."""
        if not self.plan.get('external_wait', True):
            return True, None
        if e['day'] in self._attached:
            return True, None
        directory = self.ingest_dir(e)
        if directory is None:
            return False, 'the day has no sealed ingest yet, so no day file beside it (stages ingest, external)'
        path, sha, why = attached_day_file(directory)
        if path is None:
            return False, 'the day file of the historical data points is not attached yet (stage external): %s' % why
        self._attached[e['day']] = (str(path), sha)
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
        return lack

    def external(self, e):
        day = e['day']
        ing = self.receipt('ingest', day)
        if not (ing and ing['status'] in FINISHED):
            return self.record('external', day, 'waiting', reason='the day has no sealed ingest yet (the day file is '
                                                                  'attached beside it)')
        directory = Path(ing['ingest'])
        path, sha, why = attached_day_file(directory)
        if path is not None:
            day_receipt = directory / DAY_FILE_RECEIPT
            brain_entry = self.brain_stage(day, 'day-file', [path, day_receipt],
                                           summary=dict(day_file=str(path), sha256=sha))
            return self.record('external', day, 'reused', day_file=str(path), sha256=sha, ingest=str(directory),
                               brain_entry=brain_entry)
        if why.startswith('DIFFERS'):
            return self.record('external', day, 'refused', reason=why + ' (a day file is never overwritten; move it aside '
                                                                          'with a receipt first)')
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
                                   reason='the day\'s history is not on S3 yet or not presigned (%d keys lacking); the day '
                                          'waits, never skipped, and no day file is built without its pieces' % len(lacking))
            if not self.disk_ok('external'):
                return None
            env.update(ACTION='build', RUN='%s-ext-%s-a%d' % (self.plan['run'], day, len(attempts) + 1))
        code, log = self.child('external', day, 'frankie_box_day_external.sh', env)
        path, sha, why = attached_day_file(directory)
        if path is None:
            return self.record('external', day, 'failed', exit_code=code, log=log, action=env['ACTION'], external_run=env['RUN'],
                               reason='no day file attached beside the sealed ingest after the step: %s' % why)
        self._attached[day] = (str(path), sha)
        day_receipt = directory / DAY_FILE_RECEIPT
        brain_entry = self.brain_stage(day, 'day-file', [path, day_receipt],
                                       summary=dict(day_file=str(path), sha256=sha))
        return self.record('external', day, 'done', exit_code=code, log=log, action=env['ACTION'], external_run=env['RUN'],
                           day_file=str(path), sha256=sha, ingest=str(directory),
                           new_bytes=new_bytes(DAY_EXTERNAL / env['RUN']) if env['ACTION'] == 'build' else 0,
                           upload_or_brain_exit_code=code, brain_entry=brain_entry)

    # the classroom arm (V2: the 19/171 classroom plus the external section) and Jev's material
    def previous_of(self, e):
        """(PREVIOUS classroom directory or None, why it waits or None, where it came from)."""
        if self.queue_previous is not None:        # the class worker: class k carries class k-1 of the class line
            return self.queue_previous
        if e.get('previous_classroom'):
            return e['previous_classroom'], None, 'plan (the day)'
        arm_days = [x for x in self.plan['days'] if x['classroom_arm']]
        i = [x['day'] for x in arm_days].index(e['day'])
        if i > 0:
            prev = arm_days[i - 1]['day']
            r = self.receipt('classroom', prev)
            if not (r and r['status'] in ('done', 'reused') and r.get('classroom')):
                return None, 'the previous arm day %s has no complete classroom yet (its history is carried in)' % prev, None
            return r['classroom'], None, 'the previous arm day of this run (%s)' % prev
        if self.plan.get('previous_classroom'):
            return self.plan['previous_classroom'], None, 'plan (PREVIOUS_CLASSROOM)'
        found, found_day = latest_completed_classroom(e['day'])
        if found is None:
            return None, None, 'none: no other complete classroom on the box (history starts here)'
        return str(found), None, 'the most recently completed classroom on the box (%s; trading-date order ignored)' % found_day

    def classroom_ready(self, e):
        """The classroom step's readiness checks, in its order: (None, None, facts) when the day may take its class now;
        ('reused', None, facts) when its classroom is complete already; else (status, reason, facts). facts carry calc,
        the classroom directory d and the teacher rows once known. Used by the step and by the class line's enqueue."""
        root = self.receipt('root', e['day'])
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
        if not (calc / 'work' / 'derivation-digest-full.md').is_file():
            return 'refused', ('the ROOT %s ran without the digest; a classroom-arm day needs DIGEST=on (its brain entry '
                               'takes it)' % calc), facts
        rows, source = rows_of(e)
        if rows is None or not str(rows).startswith(str(TEACHER_ROWS) + '/'):
            return 'waiting', 'no teacher-only Dipole rows under %s yet (stage teacher; found: %s)' % (TEACHER_ROWS,
                                                                                                    source), facts
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
            teacher_brain = self.teacher_knowledge(day, rows_path, rows_of(e)[1])
        except (ValueError, FileNotFoundError) as error:
            return self.record('classroom', day, 'refused', teacher_rows=str(rows_path),
                               reason='the teacher knowledge of the day could not be published before the classroom: %s'
                                      % error)
        if not self.disk_ok('classroom'):
            return None
        env = dict(DAY=day, CALCULATIONS=calc, TEACHER_ROWS=rows, BRAIN=self.plan.get('brain') or str(BRAIN))
        if previous:
            env['PREVIOUS'] = previous
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
        if status == 'reused' and Q.entry_of('class', self.plan['run'], day) is None:
            return self.classroom(e)                 # complete before the line existed: recorded reused, as before
        if status == 'waiting':
            return self.record('classroom', day, status, reason='%s (the class line takes the day once it is ready)' % why)
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
            return self.root(e)
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

    def kick(self, line):
        self.check_save()
        import frankie_box_frankie_queue as Q
        try:
            return Q.kick(line, self.code_root, self.commit, self.a.queue_worker_seconds, self.a.queue_poll_seconds,
                          by='frankie_box_experiment.py %s' % self.plan['run'], log=self.log)
        except Exception as error:                   # listed; the next start kicks again
            self.log('the %s worker could not be kicked (%s: %s)' % (line, type(error).__name__, error))
            return None

    def await_roots(self, days):
        """This run's ROOT-line days: wait (polling, bounded by --queue-worker-seconds) until each has left the line done
        or failed, re-kicking the ROOT worker when none runs; each day's root receipt is then the worker's. A day still
        in the line at the bound stays queued (listed); the next start waits again."""
        import frankie_box_frankie_queue as Q
        deadline = time.monotonic() + self.a.queue_worker_seconds
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
                return
            self.probe.update('root line: waiting on %d day(s)' % len(left), 0, None)
            if time.monotonic() + self.a.queue_poll_seconds > deadline:
                self.log('root line: %d day(s) still in the line at the bound (%s); they stay queued' % (len(left), left))
                return
            status, held = Q.worker_state('root')
            if not held:
                self.check_save()
                self.kick('root')
            time.sleep(self.a.queue_poll_seconds)

    # the day reports (Greg, 2026-09-29: "make sure classroom is printing out an analysis after every day has gone through
    # it, and same with Frankie, and have them number their reports")
    @staticmethod
    def reports_receipt(log):
        """The day reports step's receipt: the last line of its log, or None."""
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
            classroom = c.get('classroom')
            if not classroom:                    # refused before the classroom step named its directory (e.g. no digest)
                root = self.receipt('root', day) or {}
                classroom = str(Path(root['calculations']) / 'work' / 'classroom') if root.get('calculations') else None
            if not classroom:
                return self.record('reports', day, 'failed', reason='neither the classroom step nor the root step names '
                                                                    'the day\'s classroom directory')
            env = dict(DAY=day, CLASSROOM=classroom, RUN=self.plan['run'], REPORTS_DIR=REPORTS, DAY_CLASS=e['cls'])
            if c['status'] == 'refused' and c.get('reason'):
                env['REFUSED_REASON'] = c['reason']      # used only when the classroom wrote no receipt of its own
            x = self.receipt('exchange', day)
            if x and x['status'] in ('done', 'reused') and x.get('exchange'):
                env['EXCHANGE'] = x['exchange']
            else:
                env['EXCHANGE_LISTED'] = 'the day\'s exchange stage is %s%s' % (
                    (x or {}).get('status') or 'not run', (': ' + x['reason']) if (x or {}).get('reason') else '')
            code, log = self.child('reports', day, 'frankie_box_experiment_day_reports.sh', env)
            r = self.reports_receipt(log)
            for item in (r or {}).get('reports') or []:
                try:
                    self.log(Path(item['file']).read_text(encoding='utf-8', errors='replace'))
                except OSError as error:
                    self.log('reports %s: %s could not be read back (%s)' % (day, item.get('file'), error))
            fields = dict(exit_code=code, log=log, classroom=classroom, classroom_status=c['status'],
                          exchange_status=(x or {}).get('status'), exchange=env.get('EXCHANGE'),
                          meeting=(r or {}).get('meeting'),
                          report_number=(r or {}).get('report_number'),
                          reports=[{k: item.get(k) for k in ('kind', 'number', 'revision', 'file', 'sha256', 'existing')}
                                   for item in (r or {}).get('reports') or []],
                          problems=(r or {}).get('problems'))
            if code == 0 and r:
                return self.record('reports', day, 'done', **fields)
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

    def reports_stale(self, e):
        """A newly returned meeting or exchange gets a report revision under the existing number."""
        r, x = self.receipt('reports', e['day']), self.receipt('exchange', e['day'])
        if not (r and r['status'] == 'done' and x and x['status'] in ('done', 'reused')):
            return False
        if r.get('exchange_status') not in ('done', 'reused'):
            return True
        if x.get('frankie_view'):
            import frankie_box_brain as BR
            meeting = BR.read_meeting_for_exchange(x['frankie_view'])
            current = ((meeting.get('receipt') or {}).get('record') or {}).get('sha256')
            prior = r.get('meeting') or {}
            return prior.get('sha256') != current or prior.get('status') != meeting['status']
        return False

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
        base, source = rows_of(e)
        if base is None:
            return None, 'no Dipole rows of the day (teacher batch: %s)' % (
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
        env = dict(DAY=day, RUN=self.plan['run'], LESSONS=','.join(str(f) for f in files), OUT_DIR=target,
                   BRAIN=self.plan.get('brain') or str(BRAIN),
                   SEARCH_DIR=SEARCH / day / ('cycle-' + CYCLE) / 'discovery')
        if rows is not None:
            env['TEACHER_ROWS'] = rows
        code, log = self.child('exchange', day, 'frankie_box_experiment_exchange.sh', env)
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
        """Run or reuse the bounded meeting; a recorded runtime refusal never blocks school/reports."""
        import frankie_box_brain as BR
        import frankie_box_granite_meeting as GM
        day = e['day']
        if not e['classroom_arm']:
            return self.record('voice', day, 'skipped', reason='not a classroom-arm day')
        self.successors(day)
        self.check_save()
        x = self.receipt('exchange', day)
        if not (x and x['status'] in ('done', 'reused') and x.get('frankie_view')):
            return self.record('voice', day, 'skipped' if (x or {}).get('status') == 'skipped' else 'waiting',
                               reason='the day\'s exchange is %s' % ((x or {}).get('status') or 'not run'))
        self.require_current_exchange(day, dict(EXCHANGE_VIEW=x['frankie_view']))
        target = BR.meeting_directory(x['frankie_view'], owner_dir=self.dir)
        brain = self.plan.get('brain') or str(BRAIN)
        existing = target / 'meeting.json'
        reused, code, log = False, 0, None
        if existing.is_file():
            record = BR.read_meeting_record(existing, exchange_path=x['frankie_view'], complete=False)
            if record['status'] == 'complete':
                GM.publish_meeting_record(x['frankie_view'], target, brain)
                reused = True
        if not reused:
            receipt_path = target / 'receipt.json'
            prior_receipt = receipt_path.read_bytes() if receipt_path.is_file() else None
            env = dict(EXCHANGE_VIEW=x['frankie_view'], OUT_DIR=target, BRAIN=brain)
            code, log = self.child('voice', day, 'frankie_box_granite_meeting.sh', env)
            if code != 0:
                current = receipt_path.read_bytes() if receipt_path.is_file() else None
                if (current is None or current == prior_receipt
                        or json.loads(current).get('status') != 'runtime_failed'):
                    return self.record('voice', day, 'failed', exit_code=code, log=log,
                                       reason='meeting child failed; retained artifacts are kept for recovery')
        result = BR.read_meeting_for_exchange(x['frankie_view'], owner_dir=self.dir)
        if result['status'] == 'missing':
            return self.record('voice', day, 'failed', exit_code=code, log=log, reason=result['reason'])
        r = result['receipt']
        fields = dict(exit_code=code, log=log, meeting_status=result['status'], meeting=result['path'],
                      meeting_sha256=(r.get('record') or {}).get('sha256'), model_calls=r.get('model_calls', 0),
                      publication=r.get('publication'), brain_entry=r.get('brain_entry'),
                      counts=r.get('counts'), receipt=str(target / 'receipt.json'),
                      runtime_evidence=r.get('evidence'), binding=r.get('binding'))
        if result['status'] == 'complete':
            return self.record('voice', day, 'reused' if reused else 'done', **fields)
        return self.record('voice', day, 'waiting', non_blocking=True,
                           refused_to_run=r.get('refused_to_run') or [result['reason']],
                           reason=result['reason'] or 'the runtime gate refused the meeting', **fields)

    def school(self, e):
        day = e['day']
        if not e['classroom_arm']:
            return self.record('school', day, 'skipped', reason='not a classroom-arm day')
        if day == MONDAY:
            return self.record('school', day, 'skipped', reason='Monday 20211004 is out of the school (it starts with the '
                                                                'first school day)')
        brain = Path(self.plan.get('brain') or str(BRAIN))
        index = brain / 'school' / 'index.json'
        rows = [r for r in (json.loads(index.read_bytes()).get('rows') or [])
                if r.get('day') == day] if index.is_file() else []
        if rows:
            return self.record('school', day, 'reused', file=str(brain / 'school' / rows[-1]['file']), row=rows[-1])
        c = self.receipt('classroom', day)
        if not (c and c['status'] in ('done', 'reused', 'refused')):
            return self.record('school', day, 'waiting', reason='the day\'s classroom step is %s' % (
                (c or {}).get('status') or 'not run'))
        x = self.receipt('exchange', day)
        if not (x and x['status'] in ('done', 'reused', 'skipped')):
            return self.record('school', day, 'waiting', reason='the day\'s exchange is %s (the school file is written '
                                                                'once, with it)' % ((x or {}).get('status') or 'not run'))
        classroom = c.get('classroom') or (str(Path(self.receipt('root', day)['calculations']) / 'work' / 'classroom')
                                           if (self.receipt('root', day) or {}).get('calculations') else None)
        if not classroom:
            return self.record('school', day, 'failed', reason='no classroom directory named for the day')
        env = dict(DAY=day, RUN=self.plan['run'], REPORT_NUMBER=self.report_number(e), CLASSROOM=classroom, BRAIN=brain)
        if self.school_day is not None:
            env['SCHOOL_DAY'] = self.school_day        # the class line's school-day number (= REPORT_NUMBER), in the row
        if x['status'] in ('done', 'reused'):
            env['EXCHANGE_VIEW'] = x['frankie_view']
        else:
            env['EXCHANGE_LISTED'] = 'the exchange was skipped: %s' % x.get('reason')
        mine = LESSONS_ROOT / 'frankie' / ('%s-frankie.json' % day)
        if mine.is_file():
            env['LESSONS'] = mine
        base, source = rows_of(e)
        if base is not None and source != 'launch run':
            env['TEACHER_ROWS'] = base
        code, log = self.child('school', day, 'frankie_box_school_knowledge.sh', env)
        try:
            lines = [z for z in Path(log).read_text(encoding='utf-8', errors='replace').splitlines() if z.strip()]
            r = json.loads(lines[-1]) if lines else None
        except (OSError, ValueError):
            r = None
        if code != 0 or not (isinstance(r, dict) and r.get('schema') == SCHOOL_RECEIPT_SCHEMA):
            return self.record('school', day, 'failed', exit_code=code, log=log, reason='no school receipt after the step '
                                                                                        '(its log names why)')
        return self.record('school', day, 'done', exit_code=code, log=log, file=r['file'], row=r['row'],
                           sections=r.get('sections'), missing=r.get('missing'), withheld=r.get('withheld'))

    def jev(self, e):
        day = e['day']
        remote = self.remote_stage('jev', day)
        if remote is not None:
            return remote
        if not e['classroom_arm']:
            return self.record('jev', day, 'skipped', reason='not a classroom-arm day (Jev sits in on the arm days only)')
        c = self.receipt('classroom', day)
        if not (c and c['status'] in ('done', 'reused') and c.get('classroom')):
            return self.record('jev', day, 'waiting', reason='the day\'s classroom is not complete yet (its material is '
                                                             'written by the classroom step)')
        calc = Path(c['classroom']).parent.parent
        material = calc / 'jev-material' / 'classroom-request.json'
        if not material.is_file():
            return self.record('jev', day, 'failed', reason='no Jev material at %s' % material)
        stamp = jev_stamp(self.plan, e)
        return self.record('jev', day, 'waiting', stamp=stamp, material=str(material),
                           reason='Pods are retired; wire Jev blind comparison on an authorized CPU transport, '
                                  'then seal/test his claims before publishing tested knowledge')

    def teacher(self, batch_key, entries):
        self.check_save()
        remote = {e['day']: self.remote_stage('teacher', e['day']) for e in entries if self.remote_root(e['day'])}
        if len(entries) == 1 and entries[0]['day'] in remote and batch_key == 'day-' + entries[0]['day']:
            return remote[entries[0]['day']]
        local = [e for e in entries if e['day'] not in remote]
        remote_waiting = [day for day, r in remote.items() if not done_status(r)]
        todo = [e for e in local if rows_of(e)[0] is None]
        brain_entries = {}
        for e in local:
            rows, source = rows_of(e)
            if rows is not None:
                rows_path, why = self.rows_file(e)
                if rows_path is None:
                    raise ValueError(why)
                brain_entries[e['day']] = self.teacher_knowledge(e['day'], rows_path, source)
        if not todo:
            return self.record('teacher', batch_key, 'waiting' if remote_waiting else 'skipped',
                               reason='waiting for owning lane teacher receipts' if remote_waiting else
                                      'each day has local rows or its owning lane completed teacher receipt',
                               remote_days=remote, waiting=remote_waiting,
                               brain_entries=brain_entries,
                               days=[dict(day=e['day'], rows=str(rows_of(e)[0]), source=rows_of(e)[1]) for e in local])
        if not (self.box / 'frankie_box_experiment_teacher.sh').is_file():
            return self.record('teacher', batch_key, 'not_built', days=[e['day'] for e in todo],
                               reason='frankie_box_experiment_teacher.sh is not in the staged checkout yet')
        receipts, external_waiting = [], {}
        for e in todo:
            ing = self.receipt('ingest', e['day'])
            if not (ing and ing['status'] in FINISHED):
                continue                                  # that day waits on its ingest; the rest of the batch runs
            ready, why = self.external_ready(e)
            if not ready:
                external_waiting[e['day']] = why          # the teacher builds the external section: it waits for the file
                continue
            receipts.append((e['day'], ing['receipt']))
        waiting = [e['day'] for e in todo if e['day'] not in dict(receipts)] + remote_waiting
        if not receipts:
            return self.record('teacher', batch_key, 'waiting', days=waiting, reason='no day of the batch has a sealed ingest yet')
        if not self.disk_ok('teacher'):
            return None
        code, log = self.child('teacher', batch_key, 'frankie_box_experiment_teacher.sh',
                               dict(DAYS=','.join(d for d, _ in receipts), INGESTION_RECEIPTS=','.join(r for _, r in receipts)))
        missing = [d for d, _ in receipts if rows_of(dict(day=d))[0] is None]
        for d, _ in receipts:
            rows, source = rows_of(dict(day=d))
            if rows is not None:
                rows = Path(rows)
                brain_entries[d] = self.teacher_knowledge(d, rows / ROWS_FILE, source)
        return self.record('teacher', batch_key, 'done' if code == 0 and not missing and not waiting else 'failed',
                           exit_code=code, log=log, days=[d for d, _ in receipts], rows_missing=missing, waiting=waiting,
                           remote_days=remote,
                           external_waiting=external_waiting, brain_entries=brain_entries,
                           new_bytes=sum(new_bytes(TEACHER_ROWS / d) for d, _ in receipts),
                           reason=None if code == 0 and not missing and not waiting else
                           'rows missing for %s, waiting on ingest %s (those days go on without Dipole rows, listed)'
                           % (missing, waiting))

    def teacher_knowledge(self, day, rows_path, source):
        """Publish every measured component/pair result; per-cursor teacher evidence stays on its owning box."""
        from research.kalshi.frankie_boss import dipole_classroom as DC, dipole_classroom_integration as I
        from research.kalshi.frankie_boss.c15_journal import unpack
        from research.kalshi.frankie_boss.frankie_principal_adapter import json_form
        import frankie_box_lane_state as LS
        rows_path = Path(rows_path)
        source_sha = sha256_file(rows_path)
        path = rows_path.parent / 'teacher-knowledge.json'
        if path.exists():
            body = json.loads(path.read_bytes())
            if body['source']['sha256'] != source_sha or body['day'] != day:
                raise ValueError('retained teacher knowledge belongs to another source/day')
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
                        findings=json_form(findings),
                        rule='all component/pair measured outputs individually; every cursor/state/reason remains '
                             'in the exact source, consumed by the teacher; no host grade or student decision process')
            body['cutoff_ns'] = snapshot['as_of']
            body['through_cursor'] = snapshot['through_cursor']
            LS.write(path, body)
        # The summary is part of the immutable entry bytes: it names the exact rows file, never the label of the path
        # that found it ('plan' / 'teacher-only step'), so the same rows reached by another label reuse the entry
        # instead of declining it as different knowledge. The label stays in the step receipt (days=[... source]).
        return self.brain_stage(day, 'teacher', [rows_path, path],
                                summary=dict(rows=str(rows_path)), inline_limit=path.stat().st_size)

    def data(self, e):
        remote = self.remote_stage('data', e['day'])
        if remote is not None:
            return remote
        target = DATA / e['day'] / ('cycle-' + CYCLE)
        root = self.receipt('root', e['day'])
        if (target / 'MANIFEST.json').is_file():
            # an existing export is reused only when it was built from THIS run's ROOT of the day; one from another ROOT
            # (an earlier or partial run) is a second export of the day: declined with both named, never reused blind
            made_from = (json.loads((target / 'MANIFEST.json').read_bytes()).get('directories') or {}).get('root')
            ours = (root or {}).get('calculations')
            if ours and made_from and str(Path(made_from)) != str(Path(ours)):
                return self.record('data', e['day'], 'refused', target=str(target), exported_from=made_from, this_root=ours,
                                   reason='the day was exported from another ROOT; duplicate data declines the day (move '
                                          'that export aside with a receipt, or name its ROOT in the plan)')
            return self.record('data', e['day'], 'reused', target=str(target), exported_from=made_from,
                               manifest_sha256=sha256_file(target / 'MANIFEST.json'))
        ing = self.receipt('ingest', e['day'])
        if not (root and root['status'] in FINISHED and ing and ing['status'] in FINISHED):
            return self.record('data', e['day'], 'waiting', reason='the day has no ROOT or no sealed ingest yet')
        ready, why = self.external_ready(e)
        if not ready:
            return self.record('data', e['day'], 'waiting', reason=why)
        rows, source = rows_of(e)
        dipole_missing = None
        if rows is None:
            dipole_missing = ('no Dipole rows for the day (teacher batch: %s); exported and searched without them, listed '
                              'missing; a later search with the rows would be a second search of the day (declined)'
                              % ((self.receipt('teacher', self.batch_of(e['day'])) or {}).get('status') or 'not run'))
        env = dict(ACTION='export', DAY=e['day'], CYCLE=CYCLE, CALCULATIONS=root['calculations'], INGEST=ing['ingest'])
        for key, var in (('launch', 'LAUNCH'), ('preparation', 'PREPARATION'), ('principal_inputs', 'PRINCIPAL_INPUTS'),
                         ('host_config', 'HOST_CONFIG'), ('run', 'RUN')):
            if e.get(key):
                env[var] = e[key]
        if rows is not None and source != 'launch run':
            env['TEACHER'] = rows
        if not self.disk_ok('data'):
            return None
        code, log = self.child('data', e['day'], 'frankie_box_experiment_data.sh', env)
        if code != 0 or not (target / 'MANIFEST.json').is_file():
            return self.record('data', e['day'], 'failed', exit_code=code, log=log, reason='no exported MANIFEST.json')
        return self.record('data', e['day'], 'done', exit_code=code, log=log, target=str(target), dipole=source,
                           dipole_missing=dipole_missing, manifest_sha256=sha256_file(target / 'MANIFEST.json'),
                           new_bytes=new_bytes(target))

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
        if not self.disk_ok('search'):
            return None
        env = dict(DAY=e['day'], CYCLE=CYCLE, DAY_ROLE=e['role'], LAGS=self.plan['lags'], WORKERS=self.cores.DAY_RUN_CPUS - 1)
        if self.plan['transforms']:
            env['TRANSFORMS'] = self.plan['transforms']
        if e['role'] == 'confirmation':
            env['FROZEN_SURVIVORS'] = self.plan['frozen_survivors']
        code, log = self.child('search', e['day'], 'frankie_box_experiment_search.sh', env)
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
        searched = [e for e in self.plan['days'] if e['role'] == 'discovery' and self.finished('search', e['day'])]
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
            return self.record('lessons', batch_key, 'skipped', reason='no claims named: no historical claims file and no '
                                                                       'Jev or Frankie claims for the days of this batch')
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
            results.append(dict(claims=name, exit_code=code, log=log))
        bad = [r for r in results if r['exit_code'] != 0]
        return self.record('lessons', batch_key, 'failed' if bad else 'done', calls=results,
                           searched_days=[e['day'] for e in searched],
                           reason='%d teacher call(s) failed' % len(bad) if bad else None)

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
            todo = [e for e in days if not self.finished(stage, e['day'])]
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
            # after the lessons: the three-way exchange of each arm day, its meeting, the school knowledge
            # base, then the day reports (they carry the exchange; rebuilt once when it arrives after them)
            for stage in ('exchange', 'voice', 'school', 'reports'):
                if stage in stages and not self.stopped:
                    for e in entries:
                        if not self.stopped and not self.queue_owned(e) and (not self.finished(stage, e['day']) or
                                                                             (stage == 'reports' and self.reports_stale(e))):
                            self.guarded(stage, e)       # a class-line day's class side is the class worker's
                        tick(stage, e['day'])
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
                                                      'successor-resume'))
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
                   help='a ceiling on the WORKERS of each ingest day process; each books 8 CPUs, so the most that fit is used '
                        '(inline verify 3, deferred 7)')
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
    p.add_argument('--previous-classroom', help='the run\'s first arm day: PREVIOUS = this <root>/work/classroom '
                                                '(default: the latest earlier classroom day on the box)')
    p.add_argument('--disk-floor-gb', type=float, default=100.0)
    p.add_argument('--frankie-queue', choices=('on', 'off'), default='on',
                   help='on: classroom-arm days enter Frankie\'s class line (arrival FIFO, one class at a time, the class '
                        'worker runs their class side); off: the classroom side runs in this run as before')
    p.add_argument('--root-queue', choices=('on', 'off'), default='on',
                   help='on: ROOT-ready days enter the ROOT line (arrival FIFO to the next free day-run slot, box or Pod) '
                        'and this run waits for its own; off: the ROOTs run here in plan order as before')
    p.add_argument('--queue-worker-seconds', type=int, default=43200,
                   help='the bound of a kicked queue worker and of this run\'s wait on its ROOT-line days')
    p.add_argument('--queue-poll-seconds', type=int, default=60, help='the queue workers\' and the wait\'s poll interval')
    a = p.parse_args()
    import re
    if not re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run):
        raise SystemExit('--run: letters, digits, _ and - only')
    stages = [s for s in STAGES if s in set(a.stages.split(','))]
    unknown = set(a.stages.split(',')) - set(STAGES)
    if unknown:
        raise SystemExit('unknown stages %s' % sorted(unknown))
    run_dir = RUNS / a.run
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
    summary = run.start(stages)
    print(json.dumps(summary, indent=1, sort_keys=True))
    if summary['stopped']:
        raise SystemExit(4)
    if summary['unfinished'] or summary['not_wired'] or summary['unfinished_batches']:
        raise SystemExit(3)


if __name__ == '__main__':
    main()
