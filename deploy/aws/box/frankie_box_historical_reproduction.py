"""Original-calculation reproduction for the historical Dipole claims: stage, plan, run, compare, record.

CCode slice B (CCODE_NEXT_SOURCE_TASKS_20261006.md B; Greg's priority amendment 2026-10-06: old dead/no-good/discarded
conclusions are CLAIMS; both teachers reproduce the original calculations, investigate failure causes and try repairs or
reformulations; nothing closes until reworked). This module is the CAPABILITY the teachers use when execution is
authorized. It is NEVER invoked under the hold: run() refuses unless its caller passes the AUTHORIZATION literal, and
nothing here is called by any lane, launcher, workflow or teacher step today. CCode performs no research with it.

The bindings it executes are the declared tables of frankie_box_historical_claims (REPRODUCTIONS, REFORMULATIONS,
MARKET_ADMISSION): sources at exact revisions with sha256, the entry point, the inputs, the recorded outputs (what the
original author wrote down) and what the original calculation is admissible as. Everything is bytes-bound
(Codex's integration review 2026-10-06, B2-B5, applied 2026-10-07):
  stage(entry, out_dir)      git show <revision>:<path> for every declared source and committed input, sha256 verified
                             (frankie_box_historical_claims.read_source: the working tree only on an equal sha). The
                             driver's tree is <out_dir>/tree/<path>; a RECORDED OUTPUT (the immutable reference the run
                             is compared to) is staged APART under <out_dir>/recorded/<path>, never into the tree the
                             command runs in, so the child can neither overwrite the reference nor leave an old reference
                             looking like a fresh output (B2). A source that cannot be read with its declared bytes is
                             listed (the box has no history: there, everything is listed and nothing is staged);
  plan(entry, staging, out_dir)   HISTORICAL_REPRODUCTION_PLAN_V2: the command, the staged bytes, the recorded references,
                             the missing inputs, the recorded outputs to compare, executable yes/no with every reason it
                             is not; bound to the staging document's sha256; written once (same bytes reuse);
  run(plan, staging, out_dir, authorized=...)   BEFORE any dispatch (B3): the written plan.json must equal the plan given,
                             the staging must be the plan's and every staged file must still carry its declared bytes,
                             executability is re-derived from those facts (the plan's boolean alone is never trusted), a
                             completed run.json of this exact plan is REUSED without rerunning, a run.json of another plan
                             refuses, and a dispatch marker of an earlier dispatch that never completed refuses (no implicit
                             retry: inspect it and move it aside). Then a durable dispatch marker is written, the entry
                             script runs in the staged tree, stdout/stderr/returncode are captured, produced files are
                             hashed; HISTORICAL_REPRODUCTION_RUN_V2; status not_run without authorization or with missing
                             inputs (the missing inputs named), never a synthetic stand-in;
  compare(entry, run, staging)    only a COMPLETED run (status run, returncode 0, not timed out) is compared; anything else
                             is performed_failed with the facts kept. Produced files are read back and must still hash to
                             the bytes the run captured; the recorded reference is read from <out_dir>/recorded/ at its
                             pin. 'printed' = a regex with named groups over stdout and the expected values (tolerance
                             where the record itself is approximate); 'json_file' = the produced file against the recorded
                             file leaf by leaf over the declared fields, within the declared scope (the recorded multi-day
                             NG file is compared only on the days the driver ran, legs aligned by entry_idx, never by list
                             position; unaligned members are listed); 'prose' = declared, not comparable by code;
  record(entry, plan, run, comparison, records_dir, operation_dir)   HISTORICAL_REPRODUCTION_V2: status performed_matched |
                             performed_differs | performed_not_comparable | performed_failed | not_run, the pins (sources
                             AND committed inputs), the operation evidence (plan.json / run.json paths with their file
                             sha256 and canonical hashes), the admission, record_sha256 over the record; written once
                             under <records_dir>/<entry id>-<sha12>.json;
  records_for(claim_id, records_dir, selection=None)   what the teachers read: every record covering the claim whose
                             record_sha256 holds, whose entry, claims, binding status, pins and binding tables equal the
                             declared tables (hash-bound) and, for a performed status, whose operation evidence is retained
                             and consistent and whose binding is defined; others listed with their identity and reason,
                             never dropped. With a frozen `selection` (record_selection() taken at the owner's freeze), only
                             those files are read and any later arrival is listed apart (B5).

A record is a teacher's reproduction of the ORIGINAL calculation on its ORIGINAL inputs. It is not a test of the claim on
the search's series (frankie_box_scientific_teacher.test does that on stored counts), not a repair and not a
reformulation (REFORMULATIONS names what those need; none is performed here). A matched record does not make the claim
true, a differing record does not make it false: both are evidence with their counts (R11, R14); and a record of a
COST-SELECTED calculation (MARKET_ADMISSION) is identified historical context, never market evidence (B7).
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import frankie_box_historical_claims as HC

PLAN_SCHEMA = 'HISTORICAL_REPRODUCTION_PLAN_V2'
RUN_SCHEMA = 'HISTORICAL_REPRODUCTION_RUN_V2'
DISPATCH_SCHEMA = 'HISTORICAL_REPRODUCTION_DISPATCH_V1'
STAGING_SCHEMA = 'HISTORICAL_REPRODUCTION_STAGING_V2'
RECORD_SCHEMA = 'HISTORICAL_REPRODUCTION_V2'
AUTHORIZATION = 'EXECUTION AUTHORIZED BY GREG'     # the exact literal run() requires; the launch HOLD stands otherwise
# precedence for the one-word summary (status_of): a difference is never hidden by a match; a performed fact (even an
# incomparable or failed one) is never reported as not_run
STATUSES = ('performed_differs', 'performed_matched', 'performed_not_comparable', 'performed_failed', 'not_run')
PERFORMED = tuple(s for s in STATUSES if s.startswith('performed_'))
RECORDED_OUTPUT_ROLE = 'recorded output'   # a source whose role starts with this is an immutable reference, never a tree file


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def write_once(path, data):
    """(True, None) written or already there with these bytes; (False, why) when other bytes are there (never overwritten)."""
    path = Path(path)
    if path.exists():
        return (True, 'already there with the same bytes') if path.read_bytes() == data else (
            False, '%s exists with other bytes: duplicate data declines (R16)' % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(data)
    return True, None


def entry_by_id(entry_id):
    entry = next((e for e in HC.REPRODUCTIONS if e['id'] == entry_id), None)
    if entry is None:
        raise KeyError('no reproduction binding %s' % entry_id)
    return entry


def is_recorded_reference(src):
    return str(src.get('role') or '').startswith(RECORDED_OUTPUT_ROLE)


def pins_of(entry):
    """The exact pins of a binding: every source (path, revision, sha256, what=source) AND every committed input
    (what=input), the identity a record is bound to (B4: an input pin is part of the binding, not only the sources)."""
    pins = [dict(path=s['path'], revision=s['revision'], sha256=s['sha256'], what='source') for s in entry.get('sources') or []]
    pins += [dict(path=i['path'], revision=i['revision'], sha256=i['sha256'], what='input')
             for i in entry.get('inputs') or [] if i.get('status') == 'committed']
    return sorted(pins, key=lambda d: (d['what'], d['path'], d['revision'], d['sha256']))


# ------------------------------------------------------------------------------------------------------------- stage
def stage(entry, out_dir):
    """Stage the declared bytes: the driver's sources and committed inputs under <out_dir>/tree/<path>; the recorded
    references (role 'recorded output...') APART under <out_dir>/recorded/<path> (B2). Nothing is fetched from anywhere
    but git history (or the working tree on an equal sha256); a declared input that is not in the repository is listed
    as missing with the exact gap (B6: no settled interface supplies it)."""
    out = Path(out_dir)
    tree, recorded_dir = out / 'tree', out / 'recorded'
    staged, recorded, missing = [], [], []
    if entry['status'] == 'not_bound':
        return dict(schema=STAGING_SCHEMA, entry_id=entry['id'], tree=str(tree), recorded_dir=str(recorded_dir), staged=[],
                    recorded=[], complete=False, missing=[dict(reason='binding not bound: ' + str(entry.get('reason')))])
    declared = [dict(s, what='reference' if is_recorded_reference(s) else 'source') for s in entry['sources']]
    for inp in entry.get('inputs') or []:
        if inp.get('status') == 'committed':
            declared.append(dict(inp, what='input'))
        else:
            missing.append(dict(inp, what='input',
                                reason='not in the repository; no settled interface supplies an original input to this '
                                       'capability (B6): until one exists the binding is not executable'))
    for item in declared:
        data, how = HC.read_source(dict(revision=item['revision'], path=item['path'], sha256=item['sha256']))
        if data is None:
            missing.append(dict(item, reason=how))
            continue
        root = recorded_dir if item['what'] == 'reference' else tree
        target = root / item['path']
        if target.exists() and target.read_bytes() != data:
            raise ValueError('%s is staged with other bytes: duplicate data declines (R16)' % target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(data)
        row = dict(path=item['path'], revision=item['revision'], sha256=item['sha256'], what=item['what'], read=how,
                   staged=str(target))
        (recorded if item['what'] == 'reference' else staged).append(row)
    return dict(schema=STAGING_SCHEMA, entry_id=entry['id'], tree=str(tree), recorded_dir=str(recorded_dir), staged=staged,
                recorded=recorded, missing=missing, complete=not missing,
                rule='recorded references live apart from the tree the driver runs in: the driver can only produce fresh '
                     'output paths; a reference is never a produced file and a produced file is never a reference')


def verify_staging(staging):
    """Every staged file (tree and recorded) still carries its declared bytes; the reasons it does not, else []."""
    problems = []
    for row in list(staging.get('staged') or []) + list(staging.get('recorded') or []):
        path = Path(row['staged'])
        if not path.is_file():
            problems.append(dict(path=row['path'], reason='staged file is gone: ' + row['staged']))
        elif sha256_bytes(path.read_bytes()) != row['sha256']:
            problems.append(dict(path=row['path'], reason='staged bytes differ from the declared sha256'))
    return problems


# -------------------------------------------------------------------------------------------------------------- plan
def executability(entry, staging):
    """(executable, reasons): re-derived from the facts, never read from a boolean."""
    reasons = []
    if entry['status'] != 'defined':
        reasons.append('binding status is %s, not defined' % entry['status'])
    if not staging.get('complete'):
        reasons.append('staging incomplete: ' + '; '.join('%s (%s)' % (m.get('path'), m.get('reason')) for m in staging.get('missing') or []))
    if not entry.get('entry'):
        reasons.append('the binding declares no entry point')
    if staging.get('entry_id') != entry['id']:
        reasons.append('the staging belongs to binding %s' % staging.get('entry_id'))
    return not reasons, reasons


def input_supply(entry, staging):
    """B6: the exact state of the original-input supply for this binding. There is NO settled interface by which a
    teacher supplies an input that is not in the repository (realbins/, the S3 NG MBP-10 tapes, the regime caches):
    stage() lists them missing and executability() refuses, so supplying the bytes has no implemented path today. The
    missing interface is named precisely; it is not built here (no data fetched, no AWS source activated, no input
    invented) and nothing claims runnable reproduction for a missing_inputs binding."""
    missing = [m for m in staging.get('missing') or [] if m.get('what') == 'input']
    if not missing:
        return dict(status='no_external_input_needed' if entry['status'] == 'defined' else 'not_applicable', missing=[])
    return dict(status='no_settled_interface', missing=[dict(path=m.get('path'), where=m.get('where')) for m in missing],
                interface_needed='an authorized local-input receipt per declared input, bound into the staging as '
                                 'what=input, status=supplied: {path (the declared input), local_path, bytes, sha256, '
                                 'read_from (the source the teacher read it from), authorization (the explicit go)}; '
                                 'stage() would verify the bytes against it at staging and run() again before dispatch; '
                                 'the sha256 of the supplied bytes would then join pins_of() so a record names them',
                nearest_existing_contracts=['frankie_box_boss_session.Session.source_binding: container {path, bytes, '
                                            'sha256, journal_count, journal_hash} pinned per cycle and re-verified in derive()',
                                            'the search MANIFEST couplings.parts: {path, bytes, sha256} per evidence part, '
                                            'verified by frankie_box_teacher_knowledge before the first test',
                                            'frankie_box_durable.witness(path): {bytes, sha256}'],
                decision='whether the teachers may read these inputs at all (S3 credentials, the realbins archive) and under '
                         'which authorization is Greg\'s; no reformulation definition is implied by it')


def plan(entry, staging, out_dir):
    executable, reasons = executability(entry, staging)
    doc = dict(schema=PLAN_SCHEMA, entry_id=entry['id'], claims=list(entry['claims']), binding_status=entry['status'],
               calculation=entry.get('calculation'), command=entry.get('entry'),
               staged=[{k: s[k] for k in ('path', 'revision', 'sha256', 'what')} for s in staging['staged']],
               recorded_references=[{k: s[k] for k in ('path', 'revision', 'sha256')} for s in staging.get('recorded') or []],
               missing=staging['missing'], recorded_outputs=entry.get('recorded_outputs') or [],
               pins=pins_of(entry), binding_tables_sha256=HC.binding_tables_sha256(),
               market_admission=HC.MARKET_ADMISSION.get(entry['id'], dict(status='undeclared')).get('status'),
               staging_sha256=sha256_bytes(canonical(staging)),
               capability_sha256=sha256_bytes(Path(__file__).read_bytes()),
               executable=executable, not_executable_reasons=reasons,
               input_supply=input_supply(entry, staging),
               rule='a plan stages declared bytes and names the recorded outputs; it runs nothing and marks nothing reproduced')
    data = (json.dumps(doc, indent=1, sort_keys=True) + '\n').encode()
    ok, why = write_once(Path(out_dir) / 'plan.json', data)
    if not ok:
        raise SystemExit(why)
    return doc, Path(out_dir) / 'plan.json'


# --------------------------------------------------------------------------------------------------------------- run
def run(plan_doc, staging, out_dir, authorized=None, timeout=3600):
    """Run the staged entry script only when authorized (the exact AUTHORIZATION literal) and executable, after the
    pre-dispatch identity checks of B3 (see the module docstring). Otherwise a not_run record naming why; no stand-in
    computation of any kind. A completed run of this exact plan is returned as it is, never rerun."""
    out = Path(out_dir)
    plan_sha = sha256_bytes(canonical(plan_doc))
    base = dict(schema=RUN_SCHEMA, entry_id=plan_doc['entry_id'], plan_sha256=plan_sha,
                capability_sha256=sha256_bytes(Path(__file__).read_bytes()))
    # --- identity before anything else (B3) ---
    plan_path = out / 'plan.json'
    if not plan_path.is_file():
        raise ValueError('no written plan.json under %s: run() takes the plan that plan() wrote' % out)
    if canonical(json.loads(plan_path.read_bytes())) != canonical(plan_doc):
        raise ValueError('the plan given differs from the written plan.json: refused')
    if plan_doc.get('staging_sha256') != sha256_bytes(canonical(staging)):
        raise ValueError('the staging given is not the one the plan was made from: refused')
    entry = entry_by_id(plan_doc['entry_id'])
    executable, reasons = executability(entry, staging)
    if executable != bool(plan_doc.get('executable')):
        raise ValueError('the plan\'s executable flag does not follow from the binding and staging: refused')
    problems = verify_staging(staging)
    if problems:
        raise ValueError('staged bytes no longer match their declaration: ' + json.dumps(problems, sort_keys=True))
    run_path, dispatch_path = out / 'run.json', out / 'dispatch.json'
    if run_path.is_file():
        existing = json.loads(run_path.read_bytes())
        if existing.get('plan_sha256') == plan_sha and existing.get('schema') == RUN_SCHEMA:
            return existing                       # completed state reused; nothing is rerun
        raise ValueError('run.json under %s belongs to another plan (%s): refused' % (out, existing.get('plan_sha256')))
    if dispatch_path.is_file():
        raise ValueError('an earlier dispatch under %s never completed (dispatch.json without run.json): no implicit retry; '
                         'inspect it and move the operation aside' % out)
    # --- not_run without dispatch ---
    if authorized != AUTHORIZATION:
        doc = dict(base, status='not_run', reason='execution not authorized: the launch HOLD stands (Greg\'s explicit go '
                                                     'required); nothing was run and nothing stands in for the result')
    elif not executable:
        doc = dict(base, status='not_run', reason='not executable: ' + '; '.join(reasons))
    else:
        command = plan_doc['command']
        cwd = Path(staging['tree']) / command['cwd']
        argv = [sys.executable, '-B', command['script']] + list(command.get('argv') or [])
        started = time.time()
        marker = dict(base, schema=DISPATCH_SCHEMA, status='dispatched', argv=argv[1:], cwd=str(cwd), started_at=started,
                      authorized=True, rule='durable in-progress state written before dispatch; run.json completes it')
        ok, why = write_once(dispatch_path, (json.dumps(marker, indent=1, sort_keys=True) + '\n').encode())
        if not ok:
            raise SystemExit(why)
        try:
            done = subprocess.run(argv, cwd=str(cwd), capture_output=True, timeout=timeout)
            raw_out, raw_err, returncode, timed_out = done.stdout, done.stderr, done.returncode, False
        except subprocess.TimeoutExpired as error:
            raw_out, raw_err, returncode, timed_out = error.stdout or b'', error.stderr or b'', None, True
        # B1: the ORIGINAL bytes of both streams are retained whole (write-once files, hash-bound in this document); the
        # decoded text is a convenience for the printed-pattern comparison, never a reduction of the evidence.
        streams = {}
        for name, raw in (('stdout', raw_out), ('stderr', raw_err)):
            ok, why = write_once(out / (name + '.bin'), raw)
            if not ok:
                raise SystemExit(why)
            streams[name] = dict(path=str(out / (name + '.bin')), bytes=len(raw), sha256=sha256_bytes(raw))
        result = dict(returncode=returncode, timed_out=timed_out, streams=streams,
                      stdout=raw_out.decode('utf-8', 'replace'), stderr=raw_err.decode('utf-8', 'replace'),
                      streams_rule='stdout.bin / stderr.bin hold every original byte; the text fields are a replacement '
                                   'decoding of the same bytes, whole, not a cap')
        produced = []
        for rel in command.get('produces') or []:
            path = cwd / rel
            if path.is_file():
                produced.append(dict(path=rel, sha256=sha256_bytes(path.read_bytes()), bytes=path.stat().st_size, at=str(path)))
            else:
                produced.append(dict(path=rel, missing=True))
        doc = dict(base, status='run', argv=argv[1:], cwd=str(cwd), seconds=round(time.time() - started, 1),
                   started_at=started, dispatch_sha256=sha256_bytes(dispatch_path.read_bytes()), produced=produced, **result)
    data = (json.dumps(doc, indent=1, sort_keys=True) + '\n').encode()
    ok, why = write_once(run_path, data)
    if not ok:
        raise SystemExit(why)
    return doc


# ----------------------------------------------------------------------------------------------------------- compare
def _leaves(node, path=''):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _leaves(v, '%s.%s' % (path, k) if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _leaves(v, '%s.%d' % (path, i) if path else str(i))
    else:
        yield path, node


def _selected(path, fields):
    if not fields:
        return True
    parts = path.split('.')
    for field in fields:
        want = field.split('.')
        if len(want) <= len(parts) and all(w == '*' or w == p for w, p in zip(want, parts)):
            return True
    return False


def _aligned(produced, recorded, scope, argv):
    """The comparable (produced, recorded) pair within the declared scope (B2): top-level keys restricted to the
    driver's argv when scope.top_level == 'argv'; list members aligned by scope.member_key, never by position; lists of
    unequal length without a member key are not comparable. Returns (produced, recorded, notes)."""
    notes = dict(out_of_scope_recorded_keys=[], argv_keys_absent_from_recorded=[], unaligned_members=[], not_comparable_lists=[])
    scope = scope or {}
    if scope.get('top_level') == 'argv' and isinstance(recorded, dict) and isinstance(produced, dict):
        keys = [str(a) for a in argv or []]
        notes['out_of_scope_recorded_keys'] = sorted(k for k in recorded if k not in keys)
        notes['argv_keys_absent_from_recorded'] = [k for k in keys if k not in recorded]
        recorded = {k: recorded[k] for k in keys if k in recorded}
        produced = {k: produced[k] for k in keys if k in produced}
    member_key = scope.get('member_key')

    def align(p, r, where):
        if isinstance(p, dict) and isinstance(r, dict):
            ap, ar = dict(p), dict(r)
            for k in p:
                if k in r:
                    ap[k], ar[k] = align(p[k], r[k], where + (str(k),))
            return ap, ar
        if isinstance(p, list) and isinstance(r, list):
            if member_key and all(isinstance(m, dict) and member_key in m for m in p + r):
                pm = {str(m[member_key]): m for m in p}
                rm = {str(m[member_key]): m for m in r}
                if len(pm) != len(p) or len(rm) != len(r):
                    notes['not_comparable_lists'].append(dict(where='.'.join(where), reason='%s is not unique' % member_key))
                    return {}, {}
                for key in sorted(set(pm) ^ set(rm)):
                    notes['unaligned_members'].append(dict(where='.'.join(where), member=key,
                                                           side='produced_only' if key in pm else 'recorded_only'))
                return ({k: pm[k] for k in pm if k in rm}, {k: rm[k] for k in rm if k in pm})
            if len(p) != len(r):
                notes['not_comparable_lists'].append(dict(where='.'.join(where), produced=len(p), recorded=len(r),
                                                          reason='unequal lengths and no member key: positions are unrelated'))
                return [], []
            return p, r
        return p, r
    produced, recorded = align(produced, recorded, ())
    return produced, recorded, notes


def _compare_json(produced, recorded, fields, scope=None, argv=None):
    produced, recorded, notes = _aligned(produced, recorded, scope, argv)
    got = dict(_leaves(produced))
    want = {k: v for k, v in _leaves(recorded) if _selected(k, fields)}
    matched, differs, not_found = 0, [], []
    for key, value in want.items():
        if key not in got:
            not_found.append(key)
        elif got[key] == value:
            matched += 1
        else:
            differs.append(dict(field=key, recorded=value, produced=got[key]))
    # B1: every differing, missing and produced-only leaf is kept (no cap, no sampling); counts beside the lists
    produced_only = sorted(k for k in got if k not in want and _selected(k, fields))
    status = 'differs' if differs or not_found else 'matched' if matched else 'not_comparable'
    return dict(status=status, leaves_recorded=len(want), matched=matched, differs=differs,
                differs_count=len(differs), not_found=not_found, not_found_count=len(not_found),
                produced_only=produced_only, produced_only_leaves=len(produced_only), scope=scope, alignment=notes)


def compare(entry, run_doc, staging):
    """Field by field against the recorded outputs, from a COMPLETED run only (B2): the produced files are read back and
    must still hash to the bytes the run captured; the recorded reference is read from the staging's recorded/ at its pin.
    Never alters a value; a tolerance applies only where the record itself is approximate and the table says so."""
    outputs = []
    if run_doc.get('status') != 'run':
        return dict(status='not_run', outputs=[], reason=run_doc.get('reason'))
    facts = dict(returncode=run_doc.get('returncode'), timed_out=run_doc.get('timed_out'),
                 produced=run_doc.get('produced'), seconds=run_doc.get('seconds'))
    if run_doc.get('timed_out') or run_doc.get('returncode') != 0:
        return dict(status='performed_failed', outputs=[], **facts,
                    reason='the run did not complete (timed out or nonzero returncode): nothing is compared; a failed run '
                           'establishes no reproduction and its produced files are not read as results')
    captured = {p['path']: p for p in run_doc.get('produced') or []}
    cwd = Path(run_doc['cwd'])
    recorded_dir = Path(staging.get('recorded_dir') or (Path(staging['tree']).parent / 'recorded'))
    references = {s['path']: s for s in staging.get('recorded') or []}
    argv = (entry.get('entry') or {}).get('argv') or []
    for rec in entry.get('recorded_outputs') or []:
        item = dict(kind=rec['kind'], what=rec.get('what'), claims=rec.get('claims', entry['claims']))
        if rec['kind'] == 'printed':
            m = re.search(rec['pattern'], run_doc.get('stdout') or '', re.M)
            if m is None:
                item.update(status='not_found', reason='the pattern did not match the run\'s stdout')
            else:
                fields = []
                for name, expected in rec['expected'].items():
                    actual = int(m.group(name))
                    tol = (rec.get('tolerance') or {}).get(name, 0)
                    fields.append(dict(field=name, expected=expected, actual=actual, tolerance=tol,
                                       status='matched' if abs(actual - expected) <= tol else 'differs'))
                item.update(status='differs' if any(f['status'] == 'differs' for f in fields) else 'matched',
                            fields=fields, also_printed={k: v for k, v in m.groupdict().items() if k not in rec['expected']})
        elif rec['kind'] == 'json_file':
            produced_entry = captured.get(rec['produced'])
            reference = next((references[p] for p in references if p.endswith(rec['recorded'])), None)
            if produced_entry is None or produced_entry.get('missing'):
                item.update(status='not_found', reason='the run produced no %s' % rec['produced'])
            elif reference is None:
                item.update(status='not_comparable', reason='the recorded reference %s is not staged apart' % rec['recorded'])
            else:
                produced_path = cwd / rec['produced']
                if not produced_path.is_file():
                    item.update(status='not_comparable', reason='the produced file is gone since the run: %s' % produced_path)
                    outputs.append(item)
                    continue
                produced_bytes = produced_path.read_bytes()
                if sha256_bytes(produced_bytes) != produced_entry['sha256']:
                    raise ValueError('produced file changed since the run captured it: %s' % produced_path)
                recorded_bytes = (recorded_dir / reference['path']).read_bytes()
                if sha256_bytes(recorded_bytes) != reference['sha256']:
                    raise ValueError('staged recorded output differs from its pin: %s' % reference['path'])
                item.update(_compare_json(json.loads(produced_bytes), json.loads(recorded_bytes), rec.get('fields'),
                                          scope=rec.get('scope'), argv=argv),
                            recorded_sha256=reference['sha256'], produced_sha256=produced_entry['sha256'],
                            recorded_path=str(recorded_dir / reference['path']), produced_path=str(produced_path))
        else:
            item.update(status='declared_not_comparable_by_code', recorded_in=rec.get('recorded_in'), note=rec.get('note'))
        outputs.append(item)
    comparable = [o for o in outputs if o['status'] in ('matched', 'differs', 'not_found')]
    status = ('performed_differs' if any(o['status'] in ('differs', 'not_found') for o in comparable)
              else 'performed_matched' if comparable else 'performed_not_comparable')
    return dict(status=status, outputs=outputs, **facts,
                rule='a match reproduces the recorded numbers on the original inputs; it is not a verdict on the claim; '
                     'a difference is evidence with its fields named, not a rejection (R11, R14); a cost-selected '
                     'calculation\'s match is historical context, never market evidence (MARKET_ADMISSION)')


# ------------------------------------------------------------------------------------------------------------ record
def _operation_evidence(operation_dir, plan_doc, run_doc):
    out = Path(operation_dir)
    evidence = dict(dir=str(out))
    for name, doc in (('plan', plan_doc), ('run', run_doc)):
        path = out / (name + '.json')
        if not path.is_file():
            raise ValueError('operation evidence missing: %s' % path)
        raw = path.read_bytes()
        if canonical(json.loads(raw)) != canonical(doc):
            raise ValueError('operation evidence differs from the document given: %s' % path)
        evidence[name] = dict(path=str(path), sha256=sha256_bytes(raw), bytes=len(raw), canonical_sha256=sha256_bytes(canonical(doc)))
    dispatch = out / 'dispatch.json'
    evidence['dispatch'] = dict(path=str(dispatch), sha256=sha256_bytes(dispatch.read_bytes())) if dispatch.is_file() else None
    return evidence


def record(entry, plan_doc, run_doc, comparison, records_dir, operation_dir):
    """The record of one operation (B4): every performed fact kept (performed_not_comparable and performed_failed are
    statuses, never folded into not_run), bound to the entry, its claims, its pins (sources and inputs), the binding
    tables, the admission and the retained operation evidence under operation_dir."""
    status = 'not_run' if run_doc.get('status') != 'run' else comparison['status']
    if status not in STATUSES:
        raise ValueError('comparison status %r is not a record status' % status)
    doc = dict(schema=RECORD_SCHEMA, entry_id=entry['id'], claims=list(entry['claims']), status=status,
               binding_status=entry['status'], calculation=entry.get('calculation'), pins=pins_of(entry),
               binding_tables_sha256=plan_doc['binding_tables_sha256'],
               market_admission=HC.MARKET_ADMISSION.get(entry['id'], dict(status='undeclared')).get('status'),
               capability_sha256=sha256_bytes(Path(__file__).read_bytes()),
               plan_sha256=sha256_bytes(canonical(plan_doc)), run_sha256=sha256_bytes(canonical(run_doc)),
               operation=_operation_evidence(operation_dir, plan_doc, run_doc),
               not_run_reason=run_doc.get('reason') if status == 'not_run' else None,
               missing=plan_doc['missing'], comparison=comparison,
               performed_by='the teachers\' governed execution (authorized)' if run_doc.get('status') == 'run' else None,
               is_a_test_of_the_claim=False, is_a_repair_or_reformulation=False,
               rule='reproduction of the original calculation on its original inputs; the claim\'s truth is not decided here')
    doc['record_sha256'] = sha256_bytes(canonical(doc))
    data = (json.dumps(doc, indent=1, sort_keys=True) + '\n').encode()
    path = Path(records_dir) / ('%s-%s.json' % (entry['id'], doc['record_sha256'][:12]))
    ok, why = write_once(path, data)
    if not ok:
        raise SystemExit(why)
    return doc, path


def record_selection(records_dir):
    """The owner's record files as they are NOW (path, bytes, sha256), the selection an owner freezes with its other
    inputs (B5); an absent directory is an empty selection."""
    directory = Path(records_dir)
    if not directory.is_dir():
        return []
    out = []
    for path in sorted(directory.glob('*.json')):
        raw = path.read_bytes()
        out.append(dict(path=str(path), bytes=len(raw), sha256=sha256_bytes(raw)))
    return out


def _admit(doc, path, claim_id):
    """The reason a record is not admitted, or None (B4: the full declared binding and the operation evidence)."""
    body = {k: v for k, v in doc.items() if k != 'record_sha256'}
    if sha256_bytes(canonical(body)) != doc.get('record_sha256'):
        return 'record_sha256 does not hold; not read'
    try:
        entry = entry_by_id(doc.get('entry_id'))
    except KeyError:
        return 'record names a binding the tables do not declare'
    if list(doc.get('claims') or []) != list(entry['claims']):
        return 'record claims %s differ from the binding\'s %s' % (doc.get('claims'), entry['claims'])
    if doc.get('binding_status') != entry['status']:
        return 'record binding status %r differs from the declared %r' % (doc.get('binding_status'), entry['status'])
    if doc.get('pins') != pins_of(entry):
        return 'record pins differ from the declared binding (sources and inputs); the record belongs to another binding'
    if doc.get('binding_tables_sha256') != HC.binding_tables_sha256():
        return 'record was written against other binding tables (%s)' % doc.get('binding_tables_sha256')
    if doc.get('status') not in STATUSES:
        return 'unknown record status %r' % doc.get('status')
    if doc.get('status') in PERFORMED:
        if entry['status'] != 'defined':
            return 'performed status on a binding that is %s: inadmissible (nothing executable was declared)' % entry['status']
        operation = doc.get('operation') or {}
        for name, want in (('plan', doc.get('plan_sha256')), ('run', doc.get('run_sha256'))):
            item = operation.get(name) or {}
            opath = Path(item.get('path') or '')
            if not opath.is_file():
                return 'performed status without retained operation evidence: %s missing' % (item.get('path') or name)
            raw = opath.read_bytes()
            if sha256_bytes(raw) != item.get('sha256') or sha256_bytes(canonical(json.loads(raw))) != want:
                return 'performed status whose %s evidence differs from the record\'s hashes' % name
        run_doc = json.loads(Path(operation['run']['path']).read_bytes())
        if run_doc.get('status') != 'run':
            return 'performed status but the retained run is %r' % run_doc.get('status')
        if (doc.get('comparison') or {}).get('status') != doc.get('status'):
            return 'record status %r differs from its comparison status %r' % (doc.get('status'), (doc.get('comparison') or {}).get('status'))
    elif (doc.get('comparison') or {}).get('status') not in (None, 'not_run'):
        return 'not_run record carries a performed comparison'
    return None


def records_for(claim_id, records_dir, selection=None):
    """(records, listed): every HISTORICAL_REPRODUCTION_V2 under records_dir (or, with a frozen `selection`, only those
    files, bytes-verified) that covers the claim and passes _admit; anything else listed with its identity and reason,
    never dropped; with a selection, files that arrived after it are listed apart as late, never read."""
    records, listed = [], []
    directory = Path(records_dir)
    if selection is not None:
        frozen = {s['path']: s for s in selection}
        paths = [Path(p) for p in sorted(frozen)]
        if directory.is_dir():
            for path in sorted(directory.glob('*.json')):
                if str(path) not in frozen:
                    listed.append(dict(path=str(path), claim_id=claim_id, late=True,
                                       reason='arrived after the owner froze its record selection; not consumed by it'))
    else:
        frozen = None
        paths = sorted(directory.glob('*.json')) if directory.is_dir() else []
    for path in paths:
        if not path.is_file():
            listed.append(dict(path=str(path), claim_id=claim_id, reason='frozen record file is gone'))
            continue
        raw = path.read_bytes()
        if frozen is not None and (len(raw) != frozen[str(path)]['bytes'] or sha256_bytes(raw) != frozen[str(path)]['sha256']):
            listed.append(dict(path=str(path), claim_id=claim_id, reason='frozen record file changed since the selection; not read'))
            continue
        try:
            doc = json.loads(raw)
        except ValueError as error:
            listed.append(dict(path=str(path), reason='not JSON: %s' % error))
            continue
        if doc.get('schema') != RECORD_SCHEMA:
            if str(doc.get('schema') or '').startswith('HISTORICAL_REPRODUCTION_V'):
                listed.append(dict(path=str(path), claim_id=claim_id, schema=doc.get('schema'),
                                   reason='an older record schema; its admission semantics are superseded, not read'))
            continue
        if claim_id not in (doc.get('claims') or []):
            continue
        why = _admit(doc, path, claim_id)
        if why:
            listed.append(dict(path=str(path), claim_id=claim_id, entry_id=doc.get('entry_id'), status=doc.get('status'),
                               record_sha256=doc.get('record_sha256'), reason=why))
            continue
        records.append(dict(path=str(path), sha256=sha256_bytes(raw), record_sha256=doc['record_sha256'],
                            entry_id=doc['entry_id'], status=doc['status'], not_run_reason=doc.get('not_run_reason'),
                            market_admission=doc.get('market_admission'),
                            comparison_status=(doc.get('comparison') or {}).get('status'),
                            outputs=[dict(what=o.get('what'), status=o.get('status')) for o in
                                     (doc.get('comparison') or {}).get('outputs') or []],
                            operation=doc.get('operation'), binding_tables_sha256=doc.get('binding_tables_sha256')))
    return records, listed


def status_of(records):
    """One status word over a claim's admitted records, by STATUSES precedence (differs first, then matched, then the
    other performed facts, then not_run), else pending_teacher_work. Every record stays listed beside it (status_summary)."""
    statuses = {r['status'] for r in records}
    for word in STATUSES:
        if word in statuses:
            return word
    return 'pending_teacher_work'


def status_summary(records):
    """The word AND every record's own status, so a summary never hides an entry (B4)."""
    by_status = {}
    for r in records:
        by_status[r['status']] = by_status.get(r['status'], 0) + 1
    return dict(word=status_of(records), by_status=dict(sorted(by_status.items())),
                entries=[dict(entry_id=r['entry_id'], status=r['status'], path=r['path'], record_sha256=r['record_sha256'],
                              market_admission=r.get('market_admission')) for r in records],
                precedence=list(STATUSES))
