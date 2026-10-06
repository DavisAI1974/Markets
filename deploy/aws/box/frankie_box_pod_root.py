"""The main box's side of the Pod ROOT path (SPEC-pod-day-runner.md; Greg, 2026-09-29: "A100s immediately after to start
running ROOT; when that day is done, clean up after the day by deleting garbage and moving data to the big box to be
read by other processes"; "The pod stays and brings the next people in, and as space frees up on other boxes they do
the same").

Actions (frankie_box_pod_root.sh ACTION=..., called over SSM by the runner-side controller pod_root/controller.py; every
action prints one line POD_ROOT_RESULT <json> last):
  enable   create the claim store /opt/frankie-box/work/root-claims (from then on the orchestrator's root stage claims
           every day before its ROOT: frankie_box_root_claims.py); idempotent.
  queue    RUN: the orchestrator run's saved plan (/opt/frankie-box/work/experiment/<RUN>/plan.json) read day by day, each
           with its state: root_done, claimed, root_running_on_box, waiting_ingest, waiting_day_file, box_only, or ready
           (its files with bytes and sha256, the ROOT directory name it would get, its role and digest). Read-only.
  claim    RUN DAY WHERE: the day's gate re-checked (sealed ingest + the day file attached beside it, the orchestrator's own
           attached_day_file rule), then the create-only claim; prints the claim and the day's files.
  export   RUN DAY WHERE ATTEMPT FILES (comma basenames) + MAP_URL: the named files of the day's sealed ingest uploaded to
           the presigned PUT slots put:pod-root/<RUN>/<ATTEMPT>/in/<file>.part-NNNN (4 GiB parts; the box's role writes
           nothing in S3 itself). Read-only on the ingest.
  import   RUN DAY WHERE ATTEMPT + MAP_URL (manifest GET + chunk GETs): the Pod's zstd tar chunks streamed, each chunk's
           sha256 checked, extracted into a dot-named staging directory, EVERY file re-read and checked against the Pod's
           manifest (bytes + sha256, nothing missing, nothing extra); the ROOT checked to be the day's (its source binding
           names this box's journal path and sha256, its day file is the one attached here); then the ROOT directory is
           renamed whole into /opt/frankie-box/work/experiment-roots/<ATTEMPT> (the name root_of() finds: the orchestrator
           reuses it at its next start) and the Pod's evidence to /opt/frankie-box/work/experiment-pod-roots/<ATTEMPT>/.
           A finished ROOT marks the claim done; an attempt without calculations-receipt.json is kept (as the orchestrator
           keeps a failed attempt) and the claim is released so the day can run again.
  release  RUN DAY WHERE ATTEMPT REASON: the claim renamed aside with the reason (never deleted).
  status   RUN: every claim (open, done, released) and every import receipt. Read-only.
No model call, no Pod call, no Databento. Monday 20211004 is refused (its ROOT exists; the gold standard is never rebuilt).
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / 'research' / 'kalshi' / 'frankie_boss' / 'pod_root'))
import frankie_box_experiment as X        # noqa: E402  (the orchestrator's own rules: ingest_of, root_of, attached_day_file)
import frankie_box_root_claims as claims  # noqa: E402
import frankie_box_frankie_queue as Q     # noqa: E402  (Frankie's ROOT line: arrival order for every claim)
import pod_transfer as T                  # noqa: E402

PROTOCOL = '1'
POD_ROOTS = X.WORK / 'experiment-pod-roots'
TRANSFER_PREFIX = 'pod-root'
MONDAY = X.MONDAY


def result(**fields):
    print('POD_ROOT_RESULT ' + json.dumps(fields, sort_keys=True, separators=(',', ':'), default=str), flush=True)


def plan_of(run):
    path = X.RUNS / run / 'plan.json'
    if not path.is_file():
        raise SystemExit('no saved plan %s: start the orchestrator once for this run (e.g. STAGES=fetch,ingest,external) '
                         'so its plan (days, roles, classroom arm) is saved; the Pods follow that plan' % path)
    return json.loads(path.read_bytes())


def entry_of(plan, day):
    for e in plan['days']:
        if e['day'] == day:
            return e
    raise SystemExit('day %s is not in the run\'s plan' % day)


def _file(role, path, sha256=None):
    path = Path(path)
    st = path.stat()
    return dict(role=role, path=str(path), name=path.name, bytes=st.st_size, sha256=sha256 or T.sha256_file(path))


def day_state(run, plan, e, ignore_claim=False):
    """The day's state for the Pod queue; 'ready' carries everything a Pod needs to run the same ROOT."""
    day = e['day']
    if day == MONDAY:
        return dict(day=day, state='box_only', reason='Monday 20211004 is the gold standard; its ROOT exists and is never rebuilt')
    try:
        calc, attempts = X.root_of(e, run)
    except SystemExit as refusal:
        return dict(day=day, state='refused', reason=str(refusal))
    if calc:
        return dict(day=day, state='root_done', calculations=str(calc))
    held = claims.holder(run, day) if claims.active() else None
    if held and not ignore_claim:
        return dict(day=day, state='done' if held.get('done') else 'claimed', claim=held)
    if claims.root_running(day):
        return dict(day=day, state='root_running_on_box', reason='a frankie_box_experiment_root.py for this day runs here')
    fresh_attempts = [a for a in attempts if time.time() - max((p.stat().st_mtime for p in Path(a).rglob('*')),
                                                               default=Path(a).stat().st_mtime) < 1800]
    if fresh_attempts and not ignore_claim:
        return dict(day=day, state='root_running_on_box', reason='an unfinished ROOT attempt of the day was written in the '
                    'last 30 min (%s): an orchestrator without the claim hook may be running it' % fresh_attempts)
    step = X.RUNS / run / 'days' / day / 'ingest.json'
    receipt = None
    if step.is_file():
        s = json.loads(step.read_bytes())
        if s.get('status') in X.FINISHED and s.get('receipt'):
            receipt = Path(s['receipt'])
    if receipt is None:
        receipt, why = X.ingest_of(e)
        if receipt is None:
            return dict(day=day, state='waiting_ingest', reason=why or 'no sealed ingest of the day on this box yet')
    directory = receipt.parent
    path, day_sha, why = X.attached_day_file(directory)
    if path is None:
        return dict(day=day, state='waiting_day_file', ingest=str(directory),
                    reason='the day file is not attached beside the sealed ingest: %s' % why)
    r = json.loads(receipt.read_bytes())
    if r.get('schema') != X.INGESTION_SCHEMA or r.get('writer') != 'compact' or str(r.get('trading_day')) != day:
        return dict(day=day, state='refused', reason='the ingestion receipt is not a compact receipt of %s' % day)
    journal = directory / r['journal_file']
    if journal.stat().st_size != r['journal_bytes']:
        return dict(day=day, state='refused', reason='the journal bytes differ from the receipt')
    files = [_file('receipt', receipt), _file('completion', directory / 'completion.json'),
             dict(role='journal', path=str(journal), name=journal.name, bytes=r['journal_bytes'], sha256=r['journal_sha256'])]
    own = r.get('opening_book_file')
    if own:
        files.append(_file('opening_book', directory / own['file'], own['sha256']))
    elif (r.get('opening_book') or {}).get('status') == 'seeded':
        return dict(day=day, state='box_only', reason='the day opens with another day\'s closing book read from outside its '
                    'ingest directory (%s); its ROOT runs on the box' % (r['opening_book'].get('receipt')))
    files.append(_file('day_file', path, day_sha))
    files.append(_file('day_file_receipt', directory / X.DAY_FILE_RECEIPT))
    frozen = None
    if e['role'] == 'confirmation':
        if not plan.get('frozen_survivors') or not Path(plan['frozen_survivors']).is_file():
            return dict(day=day, state='box_only', reason='a confirmation day without the frozen survivor list on the box')
        frozen = _file('frozen_survivors', plan['frozen_survivors'])
        files.append(frozen)
    runner = None
    if directory.name.startswith('ingest-%s-gh-' % day):
        runner = 'frankie/ingest/%s/%s/' % (day, directory.name[len('ingest-%s-' % day):])
    return dict(day=day, state='ready', role=e['role'], digest='on',
                ingest_dir=str(directory), ingestion_receipt=str(receipt), ingestion_receipt_sha256=files[0]['sha256'],
                files=files, frozen_survivors=frozen and frozen['path'],
                attempt='%s-%s-a%d' % (run, day, len(attempts) + 1), interrupted_attempts=[str(a) for a in attempts],
                conformance=r.get('conformance'), conformed=(directory / 'conformance.json').is_file(),
                runner_prefix=runner, day_external_sha256=day_sha, plan=plan, settings=(Q.entry_of('root', run, day) or {}).get('settings', Q.SETTINGS))


def line_order(run, days):
    """Frankie's ROOT line (frankie_box_frankie_queue.py; Greg: "Whichever trade date hits that spot first goes first"):
    when the run has entries in the line, its days are listed in LINE order (arrival seq), and a ready day may be claimed
    only when no earlier entry of the line is still waiting to start (root_gate): its state becomes behind_in_root_line
    or not_in_root_line otherwise, with the reason. The controller takes the first ready day, so it takes the front. A
    run with no entry in the line is listed in plan order, as before."""
    doc = Q.load('root')
    seq = {x['day']: x['seq'] for x in doc['entries'] if x['run'] == run}
    if not seq:
        return days
    for d in days:
        if d['state'] == 'ready':
            ok, why = Q.root_gate(run, d['day'])
            if not ok:
                d.update(state=why.split(':')[0], reason=why)
        d['root_line_seq'] = seq.get(d['day'])
    return sorted(days, key=lambda d: (d['root_line_seq'] is None, d['root_line_seq'] or 0))


def url_map():
    url = os.environ.get('MAP_URL')
    if not url:
        raise SystemExit('MAP_URL required (the runner presigns the slots)')
    return json.loads(T.get_bytes(url))


def held_by(run, day, where, attempt):
    doc = claims.holder(run, day)
    if not doc or doc.get('where') != where or doc.get('attempt') != attempt or doc.get('done'):
        raise SystemExit('the claim of %s %s is not an open claim of %s for %s: %s' % (run, day, where, attempt, doc))
    return doc


def preparation_identity(state):
    return {k: state[k] for k in ('day', 'role', 'digest', 'ingest_dir', 'ingestion_receipt',
            'ingestion_receipt_sha256', 'files', 'frozen_survivors', 'day_external_sha256', 'plan', 'settings')}


def act_export(run, plan, day, where, attempt, names):
    held = held_by(run, day, where, attempt)
    st = day_state(run, plan, entry_of(plan, day), ignore_claim=True)
    if st['state'] != 'ready':
        raise SystemExit('the day is no longer ready: %s' % st)
    if held.get('preparation') and held['preparation'] != preparation_identity(st):
        raise SystemExit('the retained claim source changed; no export or replacement')
    m = url_map()
    out = {}
    for f in st['files']:
        if f['name'] not in names:
            continue
        parts = []
        for i, (off, ln) in enumerate(T.plan_parts(f['bytes'])):
            key = '%s/%s/%s/in/%s.part-%04d' % (TRANSFER_PREFIX, run, attempt, f['name'], i)
            slot = m.get('put:' + key)
            if not slot:
                raise SystemExit('no upload slot for %s' % key)
            started = time.time()
            # Completed S3 PUTs are whole objects; the controller checked their byte counts.
            # The worker still checks the complete file against the retained source SHA before use.
            digest = None if slot.get('present_bytes') == ln else T.put_range(slot['url'], f['path'], off, ln)
            parts.append(dict(key=key, bytes=ln, sha256=digest, seconds=round(time.time() - started, 1)))
            print('exported %s part %d: %d bytes in %.0f s' % (f['name'], i, ln, parts[-1]['seconds']), flush=True)
        out[f['name']] = dict(path=f['path'], bytes=f['bytes'], sha256=f['sha256'], parts=parts)
    missing = sorted(set(names) - set(out))
    if missing:
        raise SystemExit('files not in the day\'s inputs: %s' % missing)
    return out


def act_import(run, plan, day, where, attempt, floor_gb):
    e = entry_of(plan, day)
    target = X.ROOTS / attempt
    base = POD_ROOTS / attempt
    if not (base / 'import-receipt.json').exists():
        held_by(run, day, where, attempt)
    if (base / 'import-receipt.json').exists():          # imported before (the runner then died before cleaning): the same receipt
        return dict(json.loads((base / 'import-receipt.json').read_bytes()), again=True)
    if target.exists():
        raise SystemExit('%s exists: a ROOT directory is never overwritten' % target)
    m = url_map()
    manifest_raw = T.get_bytes(m['manifest']['url'])
    manifest = json.loads(manifest_raw)
    if manifest.get('schema') != T.TRANSFER_SCHEMA or manifest.get('name') != attempt or manifest.get('day') != day \
            or manifest.get('run') != run:
        raise SystemExit('the transfer manifest is not the one of %s %s %s' % (run, day, attempt))
    if len(m.get('chunks') or []) != len(manifest['chunks']):
        raise SystemExit('the map holds %d chunk URLs, the manifest names %d chunks' % (len(m.get('chunks') or []),
                                                                                       len(manifest['chunks'])))
    total = sum(f['bytes'] for f in manifest['files'])
    free = shutil.disk_usage(X.BOX_ROOT).free
    if free - total < floor_gb * 1024 ** 3:
        raise SystemExit('free %d bytes; the ROOT is %d bytes; the floor is %d GB: not imported (the Pod keeps it)'
                         % (free, total, floor_gb))
    chunks = [dict(url=u['url'], bytes=c['bytes'], sha256=c['sha256']) for u, c in zip(m['chunks'], manifest['chunks'])]
    POD_ROOTS.mkdir(parents=True, exist_ok=True)
    staging = POD_ROOTS / ('.incoming-%s-%d' % (attempt, int(time.time())))
    started = time.time()
    reader = T.ChunkReader(chunks)
    try:
        T.unpack(reader, staging)
    except Exception as error:
        shutil.rmtree(staging, ignore_errors=True)
        raise SystemExit('the transfer stream failed (%s: %s); nothing placed, the claim stays, the Pod keeps the ROOT'
                         % (type(error).__name__, error))
    check = T.verify(staging, manifest['files'], manifest['dirs'])
    receipt = dict(schema='FRANKIE_POD_ROOT_IMPORT_V1', run=run, day=day, where=where, attempt=attempt,
                   manifest_sha256=__import__('hashlib').sha256(manifest_raw).hexdigest(), chunks=len(chunks),
                   compressed_bytes=sum(c['bytes'] for c in chunks), bytes=total, files=len(manifest['files']),
                   seconds=round(time.time() - started, 1), verification=dict(check, problems=check['problems'][:200],
                                                                             problem_count=len(check['problems'])),
                   root_exit=manifest.get('root_exit'), pod=manifest.get('host'))
    if check['problems']:
        shutil.rmtree(staging, ignore_errors=True)
        result(action='import', status='verification_failed', receipt=receipt)
        raise SystemExit('%d files differ from the Pod\'s manifest; nothing placed, the claim stays, the Pod keeps the ROOT'
                         % len(check['problems']))
    root_dir = staging / 'root' / attempt
    calc_path = root_dir / 'calculations-receipt.json'
    problems = []
    if calc_path.is_file():
        calc = json.loads(calc_path.read_bytes())
        binding = json.loads((root_dir / 'source-binding.json').read_bytes())
        st = day_state(run, plan, e, ignore_claim=True)
        journal = next((f for f in st.get('files') or [] if f['role'] == 'journal'), None) if st['state'] == 'ready' else None
        container = binding.get('container') or {}
        if calc.get('day') != day:
            problems.append('calculations receipt day %s' % calc.get('day'))
        if journal is None:
            problems.append('the day is not ready on this box any more: %s' % st.get('state'))
        elif container.get('path') != journal['path'] or container.get('sha256') != journal['sha256']:
            problems.append('the ROOT read %s (%s), this box holds %s (%s)' % (container.get('path'), container.get('sha256'),
                                                                               journal['path'], journal['sha256']))
        ext = calc.get('external') or {}
        if ext.get('status') != 'attached' or ext.get('sha256') != st.get('day_external_sha256'):
            problems.append('the ROOT\'s day file is %s %s; the one attached here is %s' % (ext.get('status'), ext.get('sha256'),
                                                                                          st.get('day_external_sha256')))
    receipt['root_checks'] = problems
    base.mkdir(parents=True, exist_ok=True)
    if problems:
        os.rename(staging, base / 'refused')
        receipt['status'] = 'refused_not_this_days_root'
        receipt['kept'] = str(base / 'refused')
        T_write(base / 'import-receipt.json', receipt)
        claims.release(run, day, 'the Pod ROOT is not this day\'s (%s); kept under %s' % (problems, base / 'refused'),
                       'frankie_box_pod_root.py import', expect_where=where, expect_attempt=attempt)
        result(action='import', status=receipt['status'], receipt=receipt)
        raise SystemExit(3)
    if root_dir.is_dir():
        X.ROOTS.mkdir(parents=True, exist_ok=True)
        os.rename(root_dir, target)                  # whole, one rename: root_of() never sees a partial ROOT
    if (staging / 'pod').is_dir():
        os.rename(staging / 'pod', base / 'pod')
    (base / 'transfer-manifest.json').write_bytes(manifest_raw)
    shutil.rmtree(staging)                           # empty now: only the root/ and pod/ shells were left
    final = target / 'calculations-receipt.json'
    if final.is_file():
        receipt_sha = T.sha256_file(final)
        receipt.update(status='placed', calculations=str(target), calculations_receipt_sha256=receipt_sha,
                       root_status=json.loads(final.read_bytes()).get('status'))
        ok, why = claims.done(run, day, where, attempt, target, receipt_sha, imported_by='frankie_box_pod_root.py')
        receipt['claim_done'] = ok if ok else why
    else:
        receipt.update(status='placed_interrupted_attempt' if target.is_dir() else 'no_root_output',
                       calculations=str(target) if target.is_dir() else None)
        ok, why = claims.release(run, day, 'the Pod attempt ended without calculations-receipt.json (exit %s); the attempt is '
                                 'kept as %s' % (manifest.get('root_exit'), target), 'frankie_box_pod_root.py import',
                                 expect_where=where, expect_attempt=attempt)
        receipt['claim_released'] = why
    T_write(base / 'import-receipt.json', receipt)
    return receipt


def T_write(path, doc):
    with open(path, 'x', encoding='utf-8') as f:
        f.write(json.dumps(doc, indent=1, sort_keys=True, default=str) + '\n')


def main():
    env = os.environ
    action = env.get('ACTION')
    if env.get('PROTOCOL') != PROTOCOL:
        raise SystemExit('protocol %s, this module speaks %s (script and staged checkout differ)' % (env.get('PROTOCOL'), PROTOCOL))
    if action == 'coordinate':
        import frankie_box_lane_state as LS
        import urllib.request
        urls = url_map()
        body = json.loads(urllib.request.urlopen(urls['rpc']['url'], timeout=120).read())
        try:
            reply = LS.coordinate(body, env['CODE_ROOT'], env['CODE_COMMIT'])
        except Exception as error:
            reply = dict(id=body['id'], error='%s: %s' % (type(error).__name__, error))
        urllib.request.urlopen(urllib.request.Request(urls['reply']['url'], json.dumps(reply).encode(), method='PUT'), timeout=120).close()
        return result(action=action, id=body['id'], error=reply.get('error'))
    if action == 'enable':
        claims.enable()
        return result(action='enable', claims=str(claims.CLAIMS), active=claims.active())
    run = env.get('RUN') or ''
    if action == 'status':
        receipts = []
        for p in sorted(POD_ROOTS.glob('*/import-receipt.json')) if POD_ROOTS.is_dir() else ():
            r = json.loads(p.read_bytes())
            if not run or r.get('run') == run:
                receipts.append({k: r.get(k) for k in ('attempt', 'day', 'where', 'status', 'bytes', 'seconds', 'files')})
        return result(action='status', active=claims.active(), claims=claims.listing(run or None), imports=receipts,
                      free_bytes=shutil.disk_usage(X.BOX_ROOT).free)
    plan = plan_of(run)
    if action == 'queue':
        days = line_order(run, [day_state(run, plan, e) for e in plan['days']])
        counts = {}
        for d in days:
            counts[d['state']] = counts.get(d['state'], 0) + 1
        return result(action='queue', run=run, active=claims.active(), counts=counts, days=days,
                      code_commit=env.get('CODE_COMMIT'), free_bytes=shutil.disk_usage(X.BOX_ROOT).free)
    day, where = env.get('DAY') or '', env.get('WHERE') or ''
    if not (len(day) == 8 and day.isdigit()) or not where:
        raise SystemExit('DAY (YYYYMMDD) and WHERE required')
    if action == 'claim':
        if not claims.active():
            raise SystemExit('the claim store is not enabled (ACTION=enable first)')
        st = day_state(run, plan, entry_of(plan, day))
        if st['state'] != 'ready':
            return result(action='claim', claimed=False, state=st)
        gate, why = Q.root_gate(run, day)            # Frankie's ROOT line: days leave in arrival order (never skipped)
        if not gate:
            return result(action='claim', claimed=False, state=dict(st, state=why.split(':')[0], reason=why))
        ok, doc = claims.claim(run, day, where, st['attempt'], env.get('COMMIT') or env.get('CODE_COMMIT'),
                               by='frankie_box_pod_root.py', preparation=preparation_identity(st))
        if ok:
            Q.root_claimed(run, day, where, st['attempt'], by='frankie_box_pod_root.py claim')
        return result(action='claim', claimed=ok, claim=doc, state=st, root_line=why)
    attempt = env.get('ATTEMPT') or ''
    if action == 'prepare':
        held = held_by(run, day, where, attempt)
        if held.get('commit') != env.get('CODE_COMMIT'):
            raise SystemExit('preparation must use the retained claim commit')
        st = day_state(run, plan, entry_of(plan, day), ignore_claim=True)
        if st['state'] != 'ready':
            raise SystemExit('retained day is not ready for preparation: %s' % st)
        if not held.get('preparation') or held['preparation'] != preparation_identity(st):
            raise SystemExit('claim source binding is missing or changed; original claim retained, no replacement')
        st['attempt'] = attempt
        Q.root_claimed(run, day, where, attempt, by='retained Linux preparation')
        return result(action=action, state=st, claim=held)
    if action == 'export':
        names = [n for n in (env.get('FILES') or '').split(',') if n]
        return result(action='export', files=act_export(run, plan, day, where, attempt, names))
    if action == 'import':
        return result(action='import', receipt=act_import(run, plan, day, where, attempt, float(env.get('DISK_FLOOR_GB') or 100)))
    if action == 'release':
        ok, why = claims.release(run, day, env.get('REASON') or 'released by the runner', 'frankie_box_pod_root.py release',
                                 expect_where=where, expect_attempt=attempt or None)
        return result(action='release', released=ok, detail=why)
    raise SystemExit('unknown ACTION %s' % action)


if __name__ == '__main__':
    main()
