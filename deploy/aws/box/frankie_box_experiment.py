"""The experiment orchestrator: one box-side run over a list of days, calling the existing steps in order.

Brief piece A (CHATGPT_BRIEF_EXPERIMENT_20260929.md), built by Claude on Greg's word ("I'm going to have you do
chatgpts part", 2026-09-29). Spec: research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md ("How the orchestrator
runs", "Days", "The classroom arm", "The teacher's Dipole rows: 1 day in 5"). It re-implements no step; each step is
the committed box script, run as a child with its own inputs, its output kept in a log beside its receipt:

  fetch    frankie_box_ingest_block.sh ACTION=fetch   (MAP_URL presigns every partition of the days; run this stage on
           its own while the short-lived URLs are live; a day whose sealed ingest exists is skipped)
  ingest   frankie_box_ingest_block.sh ACTION=ingest  (one day at a time: the script checks out the commit into the box's
           ingest checkout; never Monday 20211004, the gold standard: its sealed ingest is found, never rebuilt)
  root     frankie_box_experiment_root.sh             (bedrock off; DIGEST=on only on the classroom-arm days)
  teacher  frankie_box_experiment_teacher.sh DAYS=... (the Dipole rows, 1 day in 5: a batch of up to five days, each its
           own walk; a day whose rows exist is skipped; while the script is not built the batch stops here, listed)
  data     frankie_box_experiment_data.sh ACTION=export
  search   frankie_box_experiment_search.sh
  lessons  frankie_box_scientific_teacher.sh          (after each batch: every discovery-day search of the run so far,
           the committed historical claims, and Jev's / Frankie's claims where the plan names them)

NO DATA IS DROPPED (Greg, 2026-09-29): incomplete data never stops the run or skips a day. A calculation that cannot
use a piece of data (missing, incomplete) skips over that piece, and the step says what it skipped and why; every
other day and step goes on. So a day's gap is recorded on that day's steps and the rest runs:
  a day with no manifest and no sealed ingest: its fetch and ingest wait (listed); its later steps wait on the ingest;
  a day with no Dipole rows (the teacher batch not built or failed for it): exported and searched without them, the
    Dipole listed missing in its receipts (a later search with the rows would be a second search of the day: declined,
    so the receipt names it);
  a ROOT with producer failures: calculations_retained_with_failures, the failures listed, the day goes on.
WALLS (rules, not data gaps; each listed with its reason). Days are never pooled and classes never mix: a day of
another class than the run's is left out of this run (weekday: monday, midweek = Tue/Wed, thursday, friday; holidays
not modelled). Discovery = October days of 2021-2023, confirmation = October days of 2024-2025 (R15); a day outside
them is left out, and a confirmation day stays untouched until the frozen survivor list is given. Duplicate data
declines the run: a day listed twice; two sealed ingests or two finished ROOTs of one day decline that day's step,
naming both. No model call, no Granite, no Pod.

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
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCHEMA = 'FRANKIE_EXPERIMENT_RUN_V1'
STAGES = ('fetch', 'ingest', 'root', 'teacher', 'data', 'search', 'lessons')
FINISHED = ('done', 'reused', 'skipped')
BOX_ROOT = Path('/opt/frankie-box')
WORK = BOX_ROOT / 'work'
RUNS = WORK / 'experiment'
ROOTS = WORK / 'experiment-roots'
TEACHER_ROWS = WORK / 'experiment-teacher-rows'
DATA = WORK / 'experiment-data'
SEARCH = WORK / 'experiment-search'
ROWS_FILE = 'host-dipole-classroom-source.c15.json'
MONDAY = '20211004'                      # the gold standard: never re-ingested
MONDAY_RECOVERY = '/opt/frankie-box/work/sealed-recovery-35796793428/recovery-receipt.json'   # its ingest was recovered; checkpoint beside it
CYCLE = '00'
BATCH = 5                                # the teacher's Dipole rows: 1 day in 5 (Greg, 2026-09-29)
CLASS_OF_WEEKDAY = {0: 'monday', 1: 'midweek', 2: 'midweek', 3: 'thursday', 4: 'friday'}
ROLE_OF_YEAR = {2021: 'discovery', 2022: 'discovery', 2023: 'discovery', 2024: 'confirmation', 2025: 'confirmation'}
INGESTION_SCHEMA = 'BOSS_BLOCK_INGESTION_RECEIPT_V1'
OVERRIDES = ('ingest', 'calculations', 'launch', 'preparation', 'principal_inputs', 'host_config', 'run',
             'teacher_rows', 'jev_stamp', 'frankie_ledgers', 'opening_receipt')


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
    if not arm:
        # Greg, 2026-09-29: the classroom arm runs on days 1 and 2 of every five (they apply their findings), off on 3, 4
        # and 5, then on again: the run's discovery days of its class, in date order, position i on when i % 5 < 2
        # (--classroom-arm-cycle ON/OF, default 2/5; 5/5 = every day). An explicit list (--classroom-arm) wins.
        on, cycle = (int(x) for x in a.classroom_arm_cycle.split('/'))
        listed = sorted({str(e['day']) for e in entries if str(e['day']).isdigit() and len(str(e['day'])) == 8})
        discovery = [d for d in listed if d[4:6] == '10' and ROLE_OF_YEAR.get(int(d[:4])) == 'discovery'
                     and CLASS_OF_WEEKDAY.get(dt.date(int(d[:4]), int(d[4:6]), int(d[6:8])).weekday()) == klass]
        arm = [d for i, d in enumerate(discovery) if i % cycle < on]
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
            outs.append('only October days of 2021-2023 (discovery) and 2024-2025 (confirmation) are assigned (R15); '
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
    plan = dict(schema=SCHEMA, run=a.run, cls=klass, days=days, left_out=left_out, classroom_arm=arm,
                frozen_survivors=a.frozen_survivors or None, historical_claims=a.historical_claims or None,
                lags=a.lags, transforms=a.transforms or None, batch=BATCH)
    return plan, refused


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
            return Path(base), source
    if entry.get('run'):
        found = sorted(Path(entry['run']).glob('execution/cycle-*/host-dipole-classroom-source*.json'))
        if found:
            return Path(entry['run']), 'launch run'
    return None, None


# --------------------------------------------------------------------------------------------------------------- run

class Run:
    def __init__(self, a, plan, code_root, commit, log=print):
        self.a, self.plan, self.code_root, self.commit, self.log = a, plan, Path(code_root), commit, log
        self.dir = RUNS / plan['run']
        self.box = self.code_root / 'deploy' / 'aws' / 'box'
        self.floor = int(a.disk_floor_gb * 1024 ** 3)
        self.stopped = None
        sys.path.insert(0, str(self.box))
        from frankie_box_progress import Probe
        self.probe = Probe(self.dir, request_sha256=plan_digest(plan), phase='experiment')

    # receipts
    def receipt_path(self, stage, key):
        return self.dir / ('batches' if stage in ('teacher', 'lessons') else 'days') / key / (stage + '.json')

    def receipt(self, stage, key):
        path = self.receipt_path(stage, key)
        return json.loads(path.read_bytes()) if path.is_file() else None

    def finished(self, stage, key):
        r = self.receipt(stage, key)
        return bool(r and r['status'] in FINISHED)

    def record(self, stage, key, status, **fields):
        path = self.receipt_path(stage, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = self.receipt(stage, key)
        body = dict(schema='FRANKIE_EXPERIMENT_STEP_V1', run=self.plan['run'], stage=stage, key=key, status=status,
                    at=time.time(), commit=self.commit, plan_sha256=plan_digest(self.plan), **fields)
        if previous:
            body['previous_attempts'] = (previous.get('previous_attempts') or []) + [
                {k: previous.get(k) for k in ('status', 'at', 'reason', 'exit_code')}]
        tmp = path.with_suffix('.pending')
        tmp.write_text(json.dumps(body, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(tmp, path)
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
        logs = self.dir / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        log_path = logs / ('%s-%s.log' % (key, stage))
        full = dict(os.environ, MARKETS_SHA=self.commit, CODE_ROOT=str(self.code_root), **{k: str(v) for k, v in env.items()})
        with open(log_path, 'ab') as out:
            out.write(('\n### %s %s %s at %s\n' % (stage, key, script, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))).encode())
            out.flush()
            code = subprocess.run(['sh' if script.endswith('ingest_block.sh') else 'bash', str(self.box / script)],
                                  env=full, stdout=out, stderr=subprocess.STDOUT).returncode
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
            return self.record('ingest', e['day'], 'reused', ingest=str(receipt.parent), receipt=str(receipt),
                               receipt_sha256=sha256_file(receipt))
        if e['day'] == MONDAY:
            return self.record('ingest', e['day'], 'refused', reason='Monday 20211004 is the gold standard: never re-ingested; '
                                                                     'name its sealed ingest directory in the plan')
        if not e['manifest']:
            return self.record('ingest', e['day'], 'waiting', reason=e['manifest_gap'])
        # Greg, 2026-09-29 ("Do 1-5 now"): the experiment's journal is ingested by the parallel writer (saved passes, so a
        # stopped day resumes), with no full-book copy at a group close and the conformance drain deferred; days run side
        # by side (--parallel-days), the workers split between them
        share = max(1, self.a.ingest_workers // max(1, self.a.parallel_days))
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
        return self.record('ingest', e['day'], 'done', exit_code=code, log=log, ingest=str(receipt.parent),
                           receipt=str(receipt), receipt_sha256=sha256_file(receipt), new_bytes=new_bytes(receipt.parent))

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
        if e.get('opening_receipt'):
            return e['opening_receipt'], None
        prior = e['opens_after']
        if prior == MONDAY and Path(MONDAY_RECOVERY).is_file():
            return MONDAY_RECOVERY, None
        found = sealed_ingests(prior)
        if len(found) > 1:
            return None, ('two or more sealed ingests of %s, the day before %s (%s): name the one to open from in the plan '
                          '(opening_receipt)' % (prior, e['day'], ', '.join(str(p.parent) for p in found)))
        if not found:
            return None, None          # the day warms its own book from the tail partition (listed in its receipt)
        return found[0], None

    def root(self, e):
        calc, attempts = root_of(e, self.plan['run'])
        if calc:
            return self.record('root', e['day'], 'reused', calculations=str(calc), interrupted_attempts=attempts,
                               receipt_sha256=sha256_file(calc / 'calculations-receipt.json')
                               if (calc / 'calculations-receipt.json').is_file() else None)
        ing = self.receipt('ingest', e['day'])
        if not (ing and ing['status'] in FINISHED):
            return self.record('root', e['day'], 'waiting', reason='the day has no sealed ingest yet (stage ingest)')
        if not self.disk_ok('root'):
            return None
        output = ROOTS / ('%s-%s-a%d' % (self.plan['run'], e['day'], len(attempts) + 1))
        env = dict(INGESTION_RECEIPT=ing['receipt'], INGESTION_RECEIPT_SHA256=ing['receipt_sha256'], DAY=e['day'],
                   DAY_ROLE=e['role'], OUTPUT_ROOT=output, DATA_WORKERS=self.a.data_workers,
                   DIGEST='on' if e['classroom_arm'] else 'off')
        if self.plan['frozen_survivors']:
            env['FROZEN_SURVIVORS'] = self.plan['frozen_survivors']
        code, log = self.child('root', e['day'], 'frankie_box_experiment_root.sh', env)
        if code != 0 or not (output / 'calculations-receipt.json').is_file():
            return self.record('root', e['day'], 'failed', exit_code=code, log=log, output_root=str(output),
                               interrupted_attempts=attempts, reason='no calculations-receipt.json (the attempt is kept)')
        calc = json.loads((output / 'calculations-receipt.json').read_bytes())
        return self.record('root', e['day'], 'done', exit_code=code, log=log, calculations=str(output),
                           receipt_sha256=sha256_file(output / 'calculations-receipt.json'), new_bytes=new_bytes(output),
                           interrupted_attempts=attempts, digest=e['classroom_arm'],
                           root_status=calc.get('status'), producer_failures=calc.get('failure_count'))

    def teacher(self, batch_key, entries):
        todo = [e for e in entries if rows_of(e)[0] is None]
        if not todo:
            return self.record('teacher', batch_key, 'skipped', reason='every day of the batch has its Dipole rows',
                               days=[dict(day=e['day'], rows=str(rows_of(e)[0]), source=rows_of(e)[1]) for e in entries])
        if not (self.box / 'frankie_box_experiment_teacher.sh').is_file():
            return self.record('teacher', batch_key, 'not_built', days=[e['day'] for e in todo],
                               reason='frankie_box_experiment_teacher.sh is not in the staged checkout yet')
        receipts = []
        for e in todo:
            ing = self.receipt('ingest', e['day'])
            if not (ing and ing['status'] in FINISHED):
                continue                                  # that day waits on its ingest; the rest of the batch runs
            receipts.append((e['day'], ing['receipt']))
        waiting = [e['day'] for e in todo if e['day'] not in dict(receipts)]
        if not receipts:
            return self.record('teacher', batch_key, 'waiting', days=waiting, reason='no day of the batch has a sealed ingest yet')
        if not self.disk_ok('teacher'):
            return None
        code, log = self.child('teacher', batch_key, 'frankie_box_experiment_teacher.sh',
                               dict(DAYS=','.join(d for d, _ in receipts), INGESTION_RECEIPTS=','.join(r for _, r in receipts)))
        missing = [d for d, _ in receipts if rows_of(dict(day=d))[0] is None]
        return self.record('teacher', batch_key, 'done' if code == 0 and not missing and not waiting else 'failed',
                           exit_code=code, log=log, days=[d for d, _ in receipts], rows_missing=missing, waiting=waiting,
                           new_bytes=sum(new_bytes(TEACHER_ROWS / d) for d, _ in receipts),
                           reason=None if code == 0 and not missing and not waiting else
                           'rows missing for %s, waiting on ingest %s (those days go on without Dipole rows, listed)'
                           % (missing, waiting))

    def data(self, e):
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
        target = SEARCH / e['day'] / ('cycle-' + CYCLE) / e['role']
        if (target / 'MANIFEST.json').is_file():
            return self.record('search', e['day'], 'reused', target=str(target))
        d = self.receipt('data', e['day'])
        if not (d and d['status'] in FINISHED):
            return self.record('search', e['day'], 'waiting', reason='the day data is not exported yet')
        if not self.disk_ok('search'):
            return None
        env = dict(DAY=e['day'], CYCLE=CYCLE, DAY_ROLE=e['role'], LAGS=self.plan['lags'], WORKERS=self.a.search_workers)
        if self.plan['transforms']:
            env['TRANSFORMS'] = self.plan['transforms']
        if e['role'] == 'confirmation':
            env['FROZEN_SURVIVORS'] = self.plan['frozen_survivors']
        code, log = self.child('search', e['day'], 'frankie_box_experiment_search.sh', env)
        if code != 0 or not (target / 'MANIFEST.json').is_file():
            return self.record('search', e['day'], 'failed', exit_code=code, log=log, reason='no search MANIFEST.json')
        return self.record('search', e['day'], 'done', exit_code=code, log=log, target=str(target),
                           manifest_sha256=sha256_file(target / 'MANIFEST.json'), new_bytes=new_bytes(target))

    def lessons(self, batch_key, entries):
        searched = [e for e in self.plan['days'] if e['role'] == 'discovery' and self.finished('search', e['day'])]
        if not searched:
            return self.record('lessons', batch_key, 'waiting', reason='no discovery-day search finished yet')
        searches = ','.join(str(SEARCH / e['day'] / ('cycle-' + CYCLE) / 'discovery') for e in searched)
        calls = []
        if self.plan['historical_claims']:
            calls.append(('historical', dict(HISTORICAL_CLAIMS=self.plan['historical_claims'])))
        for e in entries:
            if e.get('jev_stamp'):
                calls.append(('jev-%s' % e['day'], dict(JEV_STAMP=e['jev_stamp'])))
            if e.get('frankie_ledgers'):
                calls.append(('frankie-%s' % e['day'], dict(FRANKIE_LEDGERS=e['frankie_ledgers'], FRANKIE_DAY=e['day'])))
        if not calls:
            return self.record('lessons', batch_key, 'skipped', reason='no claims named: no historical claims file and no '
                                                                       'Jev or Frankie claims for the days of this batch')
        results = []
        for name, env in calls:
            code, log = self.child('lessons', '%s-%s' % (batch_key, name), 'frankie_box_scientific_teacher.sh',
                                   dict(env, SEARCHES=searches))
            results.append(dict(claims=name, exit_code=code, log=log))
        bad = [r for r in results if r['exit_code'] != 0]
        return self.record('lessons', batch_key, 'failed' if bad else 'done', calls=results,
                           searched_days=[e['day'] for e in searched],
                           reason='%d teacher call(s) failed' % len(bad) if bad else None)

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

        for stage, parallel in (('fetch', 1), ('ingest', self.a.parallel_days), ('root', self.a.parallel_days)):
            if stage in stages and not self.stopped:
                per_day(stage, getattr(self, stage), parallel)
        by_role = [[e for e in days if e['role'] == role] for role in ('discovery', 'confirmation')]
        batches = [(role_days[0]['role'], i // BATCH + 1, role_days[i:i + BATCH])
                   for role_days in by_role if role_days for i in range(0, len(role_days), BATCH)]
        for role, n, entries in batches:
            if self.stopped:
                break
            key = '%s-%02d' % (role, n)
            if 'teacher' in stages and not self.finished('teacher', key):
                self.teacher(key, entries)
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
            if 'lessons' in stages and role == 'discovery' and not self.stopped and not self.finished('lessons', key):
                self.lessons(key, entries)
        return self.summary(stages)

    def summary(self, stages):
        rows = {}
        for e in self.plan['days']:
            rows[e['day']] = {s: (self.receipt(s, e['day']) or {}).get('status') for s in stages if s not in ('teacher', 'lessons')}
        batches = {}
        for p in sorted((self.dir / 'batches').glob('*/*.json')) if (self.dir / 'batches').is_dir() else ():
            r = json.loads(p.read_bytes())
            batches['%s/%s' % (r['key'], r['stage'])] = r['status']
        unfinished = sorted({(k, s) for k, v in rows.items() for s, st in v.items() if st not in FINISHED})
        out = dict(schema=SCHEMA, run=self.plan['run'], plan_sha256=plan_digest(self.plan), stages=list(stages), days=rows,
                   left_out=self.plan['left_out'],
                   batches=batches, stopped=self.stopped, free_bytes=shutil.disk_usage(BOX_ROOT).free,
                   unfinished=[dict(day=k, stage=s) for k, s in unfinished], model_calls=0)
        tmp = self.dir / 'summary.pending'
        tmp.write_text(json.dumps(out, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(tmp, self.dir / 'summary.json')
        state = 'stopped_disk_floor' if self.stopped else 'complete' if not unfinished else 'incomplete'
        self.probe.update('summary', state=state)
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
                        data='exported' if (target / 'MANIFEST.json').is_file() else 'to export',
                        search='searched' if (search / 'MANIFEST.json').is_file() else 'to search'))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--action', required=True, choices=('plan', 'start', 'status'))
    p.add_argument('--run', required=True, help='the run name: /opt/frankie-box/work/experiment/<run>')
    p.add_argument('--commit', required=True)
    p.add_argument('--code-root', required=True)
    p.add_argument('--plan', help='a plan JSON (days with overrides, class, classroom_arm), absolute or repo-relative')
    p.add_argument('--days', help='comma list of YYYYMMDD (added to the plan file\'s days)')
    p.add_argument('--day-class', help='monday | midweek | thursday | friday (classes never mix)')
    p.add_argument('--classroom-arm', help='comma list of the classroom-arm days (DIGEST=on for their ROOT); default the cycle')
    p.add_argument('--classroom-arm-cycle', default='2/5',
                   help='ON/CYCLE: the classroom arm on the first ON of every CYCLE discovery days in date order (Greg, '
                        '2026-09-29: days 1 and 2 on, 3-5 off; 5/5 = every day)')
    p.add_argument('--frozen-survivors', help='the frozen survivor list (required for any confirmation day)')
    p.add_argument('--historical-claims', help='a committed knowledge/HISTORICAL_CLAIMS_V1-*.json (repo-relative)')
    p.add_argument('--stages', default=','.join(STAGES), help='comma list, run in the fixed order %s' % ','.join(STAGES))
    p.add_argument('--lags', type=int, default=20)
    p.add_argument('--transforms', help='the search transforms (comma list; default all)')
    p.add_argument('--ingest-workers', type=int, default=31)
    p.add_argument('--ingest-mode', choices=('sequential', 'parallel'), default='parallel')
    p.add_argument('--ingest-observation', choices=('full', 'none'), default='none')
    p.add_argument('--ingest-verify', choices=('inline', 'deferred'), default='deferred')
    p.add_argument('--data-workers', type=int, default=1)
    p.add_argument('--search-workers', type=int, default=8)
    p.add_argument('--parallel-days', type=int, default=4, help='days at once for the root and data steps')
    p.add_argument('--disk-floor-gb', type=float, default=100.0)
    a = p.parse_args()
    import re
    if not re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run):
        raise SystemExit('--run: letters, digits, _ and - only')
    stages = [s for s in STAGES if s in set(a.stages.split(','))]
    unknown = set(a.stages.split(',')) - set(STAGES)
    if unknown:
        raise SystemExit('unknown stages %s' % sorted(unknown))
    run_dir = RUNS / a.run
    if a.action == 'status':
        summary = run_dir / 'summary.json'
        if not run_dir.is_dir():
            raise SystemExit('no run %s' % run_dir)
        steps = sorted(str(q.relative_to(run_dir)) + ': ' + json.loads(q.read_bytes())['status']
                       for q in run_dir.glob('*/*/*.json'))
        print(json.dumps(dict(run=a.run, plan=json.loads((run_dir / 'plan.json').read_bytes()) if (run_dir / 'plan.json').is_file() else None,
                              steps=steps, summary=json.loads(summary.read_bytes()) if summary.is_file() else None,
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
    if summary['unfinished'] or any(v not in FINISHED for v in summary['batches'].values()):
        raise SystemExit(3)


if __name__ == '__main__':
    main()
