"""Original-calculation reproduction for the historical Dipole claims: stage, plan, run, compare, record.

CCode slice B (CCODE_NEXT_SOURCE_TASKS_20261006.md B; Greg's priority amendment 2026-10-06: old dead/no-good/discarded
conclusions are CLAIMS; both teachers reproduce the original calculations, investigate failure causes and try repairs or
reformulations; nothing closes until reworked). This module is the CAPABILITY the teachers use when execution is
authorized. It is NEVER invoked under the hold: run() refuses unless its caller passes the AUTHORIZATION literal, and
nothing here is called by any lane, launcher, workflow or teacher step today. CCode performs no research with it.

The bindings it executes are the declared tables of frankie_box_historical_claims (REPRODUCTIONS, REFORMULATIONS):
sources at exact revisions with sha256, the entry point, the inputs and the recorded outputs (what the original author
wrote down). Everything is bytes-bound:
  stage(entry, out_dir)      git show <revision>:<path> for every declared source and committed input, sha256 verified
                             (frankie_box_historical_claims.read_source: the working tree only on an equal sha), written
                             under <out_dir>/tree/<path>; a source that cannot be read with its declared bytes is listed
                             (the box has no history: there, everything is listed and nothing is staged);
  plan(entry, staging, out_dir)   HISTORICAL_REPRODUCTION_PLAN_V1: the command, the staged bytes, the missing inputs,
                             the recorded outputs to compare, executable yes/no; written once (same bytes reuse);
  run(plan, staging, out_dir, authorized=...)   the entry script in the staged tree, stdout/stderr/returncode captured,
                             produced files hashed; HISTORICAL_REPRODUCTION_RUN_V1; status not_run without authorization
                             or with missing inputs (the missing inputs named), never a synthetic stand-in;
  compare(entry, run, staging)    field by field against the recorded outputs: 'printed' = a regex with named groups over
                             stdout and the expected values (tolerance where the record itself is approximate); 'json_file'
                             = the produced file against the recorded file at its pin, leaf by leaf over the declared
                             fields; 'prose' = declared, not comparable by code; per field matched / differs / not_found;
  record(entry, plan, run, comparison, records_dir)   HISTORICAL_REPRODUCTION_V1: status performed_matched |
                             performed_differs | not_run (missing inputs or not authorized), the pins, the comparison,
                             record_sha256 over the record; written once under <records_dir>/<entry id>-<sha12>.json.
  records_for(claim_id, records_dir)   what the teachers read: every record covering the claim whose record_sha256 holds
                             and whose source pins equal the declared table's (hash-bound); others listed, never dropped.

A record is a teacher's reproduction of the ORIGINAL calculation on its ORIGINAL inputs. It is not a test of the claim on
the search's series (frankie_box_scientific_teacher.test does that on stored counts), not a repair and not a
reformulation (REFORMULATIONS names what those need; none is performed here). A matched record does not make the claim
true, a differing record does not make it false: both are evidence with their counts (R11, R14).
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import frankie_box_historical_claims as HC

PLAN_SCHEMA = 'HISTORICAL_REPRODUCTION_PLAN_V1'
RUN_SCHEMA = 'HISTORICAL_REPRODUCTION_RUN_V1'
STAGING_SCHEMA = 'HISTORICAL_REPRODUCTION_STAGING_V1'
RECORD_SCHEMA = 'HISTORICAL_REPRODUCTION_V1'
AUTHORIZATION = 'EXECUTION AUTHORIZED BY GREG'     # the exact literal run() requires; the launch HOLD stands otherwise
STATUSES = ('performed_matched', 'performed_differs', 'not_run')


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


def pins_of(entry):
    """The exact source pins of a binding (path, revision, sha256), the identity a record is bound to."""
    pins = [dict(path=s['path'], revision=s['revision'], sha256=s['sha256']) for s in entry.get('sources') or []]
    return sorted(pins, key=lambda d: (d['path'], d['revision'], d['sha256']))


# ------------------------------------------------------------------------------------------------------------- stage
def stage(entry, out_dir):
    """Stage the declared bytes under <out_dir>/tree/<path>. Nothing is fetched from anywhere but git history (or the
    working tree on an equal sha256); a declared input that is not in the repository is listed as missing."""
    tree = Path(out_dir) / 'tree'
    staged, missing = [], []
    if entry['status'] == 'not_bound':
        return dict(schema=STAGING_SCHEMA, entry_id=entry['id'], tree=str(tree), staged=[], complete=False,
                    missing=[dict(reason='binding not bound: ' + str(entry.get('reason')))])
    declared = [dict(s, what='source') for s in entry['sources']]
    for inp in entry.get('inputs') or []:
        if inp.get('status') == 'committed':
            declared.append(dict(inp, what='input'))
        else:
            missing.append(dict(inp, what='input', reason='not in the repository; the teachers supply it where named'))
    for item in declared:
        data, how = HC.read_source(dict(revision=item['revision'], path=item['path'], sha256=item['sha256']))
        if data is None:
            missing.append(dict(item, reason=how))
            continue
        target = tree / item['path']
        if target.exists() and target.read_bytes() != data:
            raise ValueError('%s is staged with other bytes: duplicate data declines (R16)' % target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(data)
        staged.append(dict(path=item['path'], revision=item['revision'], sha256=item['sha256'], what=item['what'],
                           read=how, staged=str(target)))
    return dict(schema=STAGING_SCHEMA, entry_id=entry['id'], tree=str(tree), staged=staged, missing=missing,
                complete=not missing)


# -------------------------------------------------------------------------------------------------------------- plan
def plan(entry, staging, out_dir):
    doc = dict(schema=PLAN_SCHEMA, entry_id=entry['id'], claims=list(entry['claims']), binding_status=entry['status'],
               calculation=entry.get('calculation'), command=entry.get('entry'),
               staged=[{k: s[k] for k in ('path', 'revision', 'sha256', 'what')} for s in staging['staged']],
               missing=staging['missing'], recorded_outputs=entry.get('recorded_outputs') or [],
               pins=pins_of(entry), binding_tables_sha256=HC.binding_tables_sha256(),
               capability_sha256=sha256_bytes(Path(__file__).read_bytes()),
               executable=bool(staging['complete'] and entry['status'] == 'defined' and entry.get('entry')),
               rule='a plan stages declared bytes and names the recorded outputs; it runs nothing and marks nothing reproduced')
    data = (json.dumps(doc, indent=1, sort_keys=True) + '\n').encode()
    ok, why = write_once(Path(out_dir) / 'plan.json', data)
    if not ok:
        raise SystemExit(why)
    return doc, Path(out_dir) / 'plan.json'


# --------------------------------------------------------------------------------------------------------------- run
def run(plan_doc, staging, out_dir, authorized=None, timeout=3600):
    """Run the staged entry script only when authorized (the exact AUTHORIZATION literal) and executable. Otherwise a
    not_run record naming why; no stand-in computation of any kind."""
    out = Path(out_dir)
    base = dict(schema=RUN_SCHEMA, entry_id=plan_doc['entry_id'], plan_sha256=sha256_bytes(canonical(plan_doc)))
    if authorized != AUTHORIZATION:
        doc = dict(base, status='not_run', reason='execution not authorized: the launch HOLD stands (Greg\'s explicit go '
                                                     'required); nothing was run and nothing stands in for the result')
    elif not plan_doc['executable']:
        doc = dict(base, status='not_run', reason='inputs or sources missing: ' + '; '.join(
            '%s (%s)' % (m.get('path'), m.get('reason')) for m in plan_doc['missing']) or 'binding not executable')
    else:
        command = plan_doc['command']
        cwd = Path(staging['tree']) / command['cwd']
        argv = [sys.executable, '-B', command['script']] + list(command.get('argv') or [])
        started = time.time()
        try:
            done = subprocess.run(argv, cwd=str(cwd), capture_output=True, timeout=timeout)
            result = dict(returncode=done.returncode, stdout=done.stdout.decode('utf-8', 'replace'),
                          stderr=done.stderr.decode('utf-8', 'replace')[-20000:], timed_out=False)
        except subprocess.TimeoutExpired as error:
            result = dict(returncode=None, stdout=(error.stdout or b'').decode('utf-8', 'replace'),
                          stderr=(error.stderr or b'').decode('utf-8', 'replace')[-20000:], timed_out=True)
        produced = []
        for rel in command.get('produces') or []:
            path = cwd / rel
            if path.is_file():
                produced.append(dict(path=rel, sha256=sha256_bytes(path.read_bytes()), bytes=path.stat().st_size, at=str(path)))
            else:
                produced.append(dict(path=rel, missing=True))
        doc = dict(base, status='run', argv=argv[1:], cwd=str(cwd), seconds=round(time.time() - started, 1),
                   produced=produced, **result)
    data = (json.dumps(doc, indent=1, sort_keys=True) + '\n').encode()
    ok, why = write_once(out / 'run.json', data)
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


def _compare_json(produced, recorded, fields):
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
    extra = sum(1 for k in got if k not in want and _selected(k, fields))
    status = 'differs' if differs or not_found else 'matched' if matched else 'not_comparable'
    return dict(status=status, leaves_recorded=len(want), matched=matched, differs=differs[:200],
                differs_count=len(differs), not_found=not_found[:200], not_found_count=len(not_found),
                produced_only_leaves=extra)


def compare(entry, run_doc, staging):
    """Field by field against the recorded outputs. Never alters a value; a tolerance applies only where the record
    itself is approximate and the table says so."""
    outputs = []
    if run_doc.get('status') != 'run':
        return dict(status='not_run', outputs=[], reason=run_doc.get('reason'))
    tree = Path(staging['tree'])
    cwd = tree / (entry['entry'] or {}).get('cwd', '.')
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
            produced_path = cwd / rec['produced']
            recorded = next((s for s in entry['sources'] if s['path'].endswith(rec['recorded'])), None)
            if not produced_path.is_file():
                item.update(status='not_found', reason='the run produced no %s' % rec['produced'])
            elif recorded is None or not (tree / recorded['path']).is_file():
                item.update(status='not_comparable', reason='the recorded file is not staged')
            else:
                recorded_bytes = (tree / recorded['path']).read_bytes()
                if sha256_bytes(recorded_bytes) != recorded['sha256']:
                    raise ValueError('staged recorded output differs from its pin: %s' % recorded['path'])
                item.update(_compare_json(json.loads(produced_path.read_bytes()), json.loads(recorded_bytes), rec.get('fields')),
                            recorded_sha256=recorded['sha256'], produced_sha256=sha256_bytes(produced_path.read_bytes()))
        else:
            item.update(status='declared_not_comparable_by_code', recorded_in=rec.get('recorded_in'), note=rec.get('note'))
        outputs.append(item)
    comparable = [o for o in outputs if o['status'] in ('matched', 'differs', 'not_found')]
    status = ('performed_differs' if any(o['status'] in ('differs', 'not_found') for o in comparable)
              else 'performed_matched' if comparable else 'performed_not_comparable')
    return dict(status=status, outputs=outputs, returncode=run_doc.get('returncode'), timed_out=run_doc.get('timed_out'),
                rule='a match reproduces the recorded numbers on the original inputs; it is not a verdict on the claim; '
                     'a difference is evidence with its fields named, not a rejection (R11, R14)')


# ------------------------------------------------------------------------------------------------------------ record
def record(entry, plan_doc, run_doc, comparison, records_dir):
    status = 'not_run' if run_doc.get('status') != 'run' else comparison['status']
    if status == 'performed_not_comparable':
        status = 'not_run'       # a run whose outputs nothing could be compared to establishes no reproduction
    doc = dict(schema=RECORD_SCHEMA, entry_id=entry['id'], claims=list(entry['claims']), status=status,
               binding_status=entry['status'], pins=pins_of(entry), binding_tables_sha256=plan_doc['binding_tables_sha256'],
               capability_sha256=sha256_bytes(Path(__file__).read_bytes()),
               plan_sha256=sha256_bytes(canonical(plan_doc)), run_sha256=sha256_bytes(canonical(run_doc)),
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


def records_for(claim_id, records_dir):
    """(records, listed): every HISTORICAL_REPRODUCTION_V1 under records_dir that covers the claim, its record_sha256
    holding and its pins equal to the declared table's for that entry (hash-bound); anything else listed with its reason.
    An absent directory is simply no record."""
    records, listed = [], []
    directory = Path(records_dir)
    if not directory.is_dir():
        return records, listed
    for path in sorted(directory.glob('*.json')):
        raw = path.read_bytes()
        try:
            doc = json.loads(raw)
        except ValueError as error:
            listed.append(dict(path=str(path), reason='not JSON: %s' % error))
            continue
        if doc.get('schema') != RECORD_SCHEMA:
            continue
        if claim_id not in (doc.get('claims') or []):
            continue
        body = {k: v for k, v in doc.items() if k != 'record_sha256'}
        if sha256_bytes(canonical(body)) != doc.get('record_sha256'):
            listed.append(dict(path=str(path), claim_id=claim_id, reason='record_sha256 does not hold; not read'))
            continue
        try:
            entry = entry_by_id(doc.get('entry_id'))
        except KeyError:
            listed.append(dict(path=str(path), claim_id=claim_id, reason='record names a binding the tables do not declare'))
            continue
        if doc.get('pins') != pins_of(entry):
            listed.append(dict(path=str(path), claim_id=claim_id, entry_id=entry['id'],
                               reason='record pins differ from the declared binding; the record belongs to another binding'))
            continue
        if doc.get('status') not in STATUSES:
            listed.append(dict(path=str(path), claim_id=claim_id, reason='unknown record status %r' % doc.get('status')))
            continue
        records.append(dict(path=str(path), sha256=sha256_bytes(raw), record_sha256=doc['record_sha256'],
                            entry_id=entry['id'], status=doc['status'], not_run_reason=doc.get('not_run_reason'),
                            comparison_status=(doc.get('comparison') or {}).get('status'),
                            outputs=[dict(what=o.get('what'), status=o.get('status')) for o in
                                     (doc.get('comparison') or {}).get('outputs') or []],
                            binding_tables_sha256=doc.get('binding_tables_sha256')))
    return records, listed


def status_of(records):
    """One status word over a claim's hash-bound records: performed_differs if any differs, else performed_matched if any
    matched, else not_run if any record, else pending_teacher_work. Every record stays listed beside it."""
    statuses = {r['status'] for r in records}
    for word in STATUSES:
        if word in statuses:
            return word
    return 'pending_teacher_work'
