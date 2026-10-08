"""Validate a completed ROOT's retained output on the lane's CPUs before the next stage starts on it (Greg,
2026-10-08: "we put CPUs on validate in root before we move onto next step after we clean and move root data").

What is checked (design: research/kalshi/frankie_boss/E2E_ONE_DAY_20231018.md, "Session 6: ROOT clean/move + validate"):
every artifact the ROOT pinned, collected from the six documents that record pins under the attempt directory R
(calculations-receipt.json, work/derive.json, work/legacy-stage.json, work/native-stage.json, work/bedrock/receipt.json,
work/native-layer-records.json and work/derived/.projection-v2/plan.json; an absent document is listed, never an
error; old and new receipt forms both load), resolves at its recorded path THROUGH symlinks (the symlink chain is
recorded), has the recorded bytes and sha256 and, for a row spool, the recorded count (and the reference layer's row
index when one exists). ONE streamed read per file, never two: a .jsonl spool goes through
frankie_box_layer_spool.scan_spool (sha256 + newline count + index in one pass of 16 MiB reads), every other file
through frankie_box_filehash.witness (16 MiB reads); two pins that resolve to one real file share one read.

Placement: frankie_box_lane_pin.ordered_map over the lane (FRANKIE_LANE_CPUS or --cpus), one worker per file, the files
largest first; a dead worker's file is redone by ordered_map's rule. Save/restore as the ROOT: FRANKIE_LANE_STOP_FILE or
SIGTERM stops new submissions, the files in flight finish, the per-file results are saved (partial.json) and the exit is
75; a re-run skips a verified file whose symlink chain and target stat (dev, ino, size, mtime_ns, ctime_ns) are
unchanged. Progress: a FRANKIE_WORK_PROBE_V1 progress.json (frankie_box_progress.Probe) in <out dir>/root-validate/,
exported as FRANKIE_ROOT_VALIDATE_DIR so the stage heartbeat finds it by environment.

Not transparent: frankie_box_prepare_trading_day.safe_path refuses a symlink at a path or any parent, and it guards the
teacher stage's readers of the spools (frankie_box_market_timeline._local), the native ledgers/sections
(frankie_box_experiment_native._take_all, frankie_box_bedrock.ledger_path, frankie_box_segmented_ledger.ordered_chunks)
and the checkpoints (frankie_box_native_checkpoint.read_checkpoint). A pinned artifact whose chain holds a symlink under
one of those locations is verified AND listed under reader_refusals, and the exit is 4 (verified, not readable by the
next stage) instead of 0. An artifact archived to S3 (a <name>.s3.json pointer, frankie_box_root_move) is checked by
HeadObject (ContentLength and Metadata.sha256), recorded as a head check, never downloaded: exit 4 as well.

Exit: 0 every pinned artifact ok and locally readable; 3 any mismatch (each named); 4 verified but not readable by the
next stage; 75 stopped early (partial saved); 2 no receipt or bad arguments. Never modifies any artifact.

CLI: --root R [--cpus 0-31] [--out R/work/root-validate.json] [--moved-manifest path] [--run-dir <run>]
     or, for ANY stage (session 6, Greg: "carry this exact sequence from handoff to handoff between workflow pieces"):
     --receipt <file> [--receipt ...] [--stage name] --out <receipt path>: every {path, bytes, sha256[, count]} object
     found anywhere in those receipt files (walked recursively; the FRANKIE_*_V* receipts all record artifacts in that
     shape) is a pin, each receipt file itself is measured, and the same read-once engine runs (collect_generic).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

SCHEMA = 'FRANKIE_ROOT_VALIDATE_V1'
PARTIAL_SCHEMA = 'FRANKIE_ROOT_VALIDATE_PARTIAL_V1'
MANIFEST_SCHEMA = 'FRANKIE_ROOT_MOVE_MANIFEST_V1'
POINTER_SUFFIX = '.s3.json'
EXIT_OK, EXIT_USAGE, EXIT_MISMATCH, EXIT_NOT_READABLE, EXIT_SAVED = 0, 2, 3, 4, 75
MAX_LINKS = 40
MAX_UNPINNED = 5000
OK_STATUSES = ('ok', 'archived_s3_head_ok')
S3_CLIENT = None      # a test or caller may set an S3 client here; otherwise boto3 is built lazily in the worker

# Where safe_path-guarded readers read (relative to R): a symlink in the chain under one of these makes the next stage
# refuse the artifact although its bytes verify (the design note names each guard with its line).
READER_GUARDS = (
    ('work/derived/.rows/', ['frankie_box_market_timeline._local (safe_path rule; the shared market reader)']),
    ('work/bedrock/', ['frankie_box_experiment_native._take_all / _regular_under', 'frankie_box_bedrock.ledger_path',
                       'frankie_box_segmented_ledger.ordered_chunks', 'frankie_box_native_checkpoint.read_checkpoint']),
    ('work/derived/.projection-v2/', ['frankie_box_experiment_native._take_all']),
)


# ---------------------------------------------------------------------------------------------------------- pins

def _load(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        return None


def _has_witness(item):
    return isinstance(item, dict) and isinstance(item.get('sha256'), str) and isinstance(item.get('bytes'), int)


def _kind(path):
    name = Path(path).name
    if name.endswith('.jsonl'):
        return 'spool'
    return 'file'


class Pins:
    """{realpath: job} plus what each document gave. A job: path (as pinned), root, kind, claims (one per document),
    expected (the first claim's bytes/sha256/count/index), pre (problems found before any read)."""

    def __init__(self, root):
        self.root = Path(root)
        self.jobs = {}
        self.documents = []
        self.problems = []
        self.archives = []           # the moved-manifest's archived directories (checked by stat, never read)

    def claim(self, source, path, bytes_=None, sha256=None, count=None, index=None, kind=None, extra=None):
        if not path:
            return
        real = os.path.realpath(str(path))
        job = self.jobs.setdefault(real, dict(path=str(path), root=str(self.root), kind=kind or _kind(path),
                                              claims=[], expected={}, pre=[], realpath=real))
        claim = dict(source=source, bytes=bytes_, sha256=sha256)
        if count is not None:
            claim['count'] = count
        if index is not None:
            claim['index'] = index
        if extra:
            claim.update(extra)
        job['claims'].append(claim)
        exp = job['expected']
        for key in ('bytes', 'sha256', 'count', 'index'):
            value = claim.get(key)
            if value is None:
                continue
            if key not in exp:
                exp[key] = value
            elif exp[key] != value and 'claims_conflict' not in job['pre']:
                job['pre'].append('claims_conflict')

    def document(self, path, body, pins):
        self.documents.append(dict(document=str(path), present=body is not None,
                                   schema=(body or {}).get('schema') if isinstance(body, dict) else None, pins=pins))


def collect_pins(root, run_dir=None):
    """Every pin the ROOT recorded under R, from every document that is present. Raises ValueError without a receipt."""
    root = Path(root)
    pins = Pins(root)
    receipt_path = root / 'calculations-receipt.json'
    receipt = _load(receipt_path)
    if not isinstance(receipt, dict):
        raise ValueError('no calculations-receipt.json under %s' % root)
    n = 0
    for key, rel in (('source_binding', 'source-binding.json'), ('calculation_pins', 'calculation-pins.json'),
                     ('derivation', 'work/derive.json'), ('digest', 'work/derivation-digest-full.md'),
                     ('external_computation', 'external-computation.json')):
        item = receipt.get(key)
        if _has_witness(item):
            pins.claim('calculations-receipt.json:' + key, root / rel, item['bytes'], item['sha256'])
            n += 1
    overlap = (receipt.get('root_execution') or {}).get('native_overlap')
    if _has_witness(overlap):
        pins.claim('calculations-receipt.json:root_execution.native_overlap', root / 'work/native-overlap.json',
                   overlap['bytes'], overlap['sha256'])
        n += 1
    rebinds = receipt.get('checkout_rebinds')
    if isinstance(rebinds, list):
        files = sorted((root / 'checkout-rebinds').glob('*.json')) if (root / 'checkout-rebinds').is_dir() else []
        if len(files) != len(rebinds):
            pins.problems.append('checkout_rebinds: %d witnesses recorded, %d files present' % (len(rebinds), len(files)))
        for path, item in zip(files, rebinds):
            if _has_witness(item):
                pins.claim('calculations-receipt.json:checkout_rebinds', path, item['bytes'], item['sha256'])
                n += 1
    for name, item in (receipt.get('shared_market_sources') or {}).items():
        if _has_witness(item) and item.get('path'):
            pins.claim('calculations-receipt.json:shared_market_sources.' + name, item['path'], item['bytes'],
                       item['sha256'], kind='spool')
            n += 1
    pins.document(receipt_path, receipt, n)
    # the receipt itself: pinned by the Run's root.json when a run directory is given; measured otherwise
    expected_receipt = None
    if run_dir and receipt.get('day'):
        root_json = _load(Path(run_dir) / 'days' / str(receipt['day']) / 'root.json')
        if isinstance(root_json, dict):
            expected_receipt = root_json.get('receipt_sha256')
            if root_json.get('calculations') and os.path.realpath(root_json['calculations']) != os.path.realpath(str(root)):
                pins.problems.append('run root.json names another calculations directory: %s' % root_json['calculations'])
        pins.document(Path(run_dir) / 'days' / str(receipt.get('day')) / 'root.json', root_json,
                      1 if expected_receipt else 0)
    pins.claim('run root.json:receipt_sha256' if expected_receipt else 'self (measured; no run receipt given)',
               receipt_path, receipt_path.stat().st_size if receipt_path.is_file() else None, expected_receipt)

    derive_path = root / 'work/derive.json'
    derive = _load(derive_path)
    n = 0
    input_records = failure_count = None
    if isinstance(derive, dict):
        rows = derive.get('rows')
        if _has_witness(rows) and rows.get('path'):
            pins.claim('derive.json:rows (the sealed INPUT container; count is the journal record count, not newlines)',
                       rows['path'], rows['bytes'], rows['sha256'], kind='container',
                       extra=dict(journal_count=rows.get('count')))
            n += 1
        for rel, item in (derive.get('producers') or {}).items():
            if _has_witness(item) and item.get('path'):
                pins.claim('derive.json:producers.' + rel, item['path'], item['bytes'], item['sha256'], kind='producer')
                n += 1
        for name, entry in (derive.get('layers') or {}).items():
            if _has_witness(entry) and entry.get('path'):
                pins.claim('derive.json:layers.' + name, entry['path'], entry['bytes'], entry['sha256'], kind='layer',
                           extra=dict(form=entry.get('form'), layer_count=entry.get('count')))
                n += 1
                for key, spool in (entry.get('spools') or {}).items():
                    if _has_witness(spool) and spool.get('path'):
                        pins.claim('derive.json:layers.%s.spools.%s' % (name, key), spool['path'], spool['bytes'],
                                   spool['sha256'], count=spool.get('count'), kind='spool')
                        n += 1
                if entry.get('form') == 'spool_reference':
                    n += _reference_index_claims(pins, Path(entry['path']), name, entry.get('spools') or {})
        bedrock = derive.get('bedrock')
        if isinstance(bedrock, dict) and not bedrock.get('skipped'):
            for key in ('receipt', 'result'):
                item = bedrock.get(key)
                if _has_witness(item) and item.get('path'):
                    pins.claim('derive.json:bedrock.' + key, item['path'], item['bytes'], item['sha256'])
                    n += 1
            for name, item in (bedrock.get('ledgers') or {}).items():
                if _has_witness(item) and item.get('path'):
                    pins.claim('derive.json:bedrock.ledgers.' + name, item['path'], item['bytes'], item['sha256'],
                               kind='ledger', extra=dict(rows_recorded=item.get('rows')))
                    n += 1
        input_records, failure_count = derive.get('input_records'), derive.get('failure_count')
    pins.document(derive_path, derive, n)

    for rel, label in (('work/legacy-stage.json', 'legacy-stage.json'), ('work/native-stage.json', 'native-stage.json')):
        body = _load(root / rel)
        n = 0
        if isinstance(body, dict):
            for item in body.get('artifacts') or []:
                if _has_witness(item) and item.get('path'):
                    name = Path(item['path']).name
                    count = None
                    if label == 'legacy-stage.json' and name.startswith('input-') and name.endswith('.jsonl'):
                        count = input_records
                    elif label == 'legacy-stage.json' and name == 'failures.jsonl':
                        count = failure_count
                    pins.claim(label + ':artifacts', item['path'], item['bytes'], item['sha256'], count=count)
                    n += 1
        pins.document(root / rel, body, n)

    bedrock_receipt = _load(root / 'work/bedrock/receipt.json')
    n = 0
    if isinstance(bedrock_receipt, dict):
        item = bedrock_receipt.get('result')
        if _has_witness(item) and item.get('path'):
            pins.claim('bedrock/receipt.json:result', item['path'], item['bytes'], item['sha256'])
            n += 1
        for name, item in (bedrock_receipt.get('ledgers') or {}).items():
            if _has_witness(item) and item.get('path'):
                pins.claim('bedrock/receipt.json:ledgers.' + name, item['path'], item['bytes'], item['sha256'],
                           kind='ledger')
                n += 1
    pins.document(root / 'work/bedrock/receipt.json', bedrock_receipt, n)

    records = _load(root / 'work/native-layer-records.json')
    n = 0
    if isinstance(records, dict) and _has_witness(records.get('derive')) and records['derive'].get('path'):
        pins.claim('native-layer-records.json:derive', records['derive']['path'], records['derive']['bytes'],
                   records['derive']['sha256'])
        n = 1
    pins.document(root / 'work/native-layer-records.json', records, n)

    plan = _load(root / 'work/derived/.projection-v2/plan.json')
    n = 0
    if isinstance(plan, dict):
        for kind, item in (plan.get('ledgers') or {}).items():
            if _has_witness(item) and item.get('path'):
                pins.claim('projection-v2/plan.json:ledgers.' + kind, item['path'], item['bytes'], item['sha256'],
                           kind='ledger')
                n += 1
    pins.document(root / 'work/derived/.projection-v2/plan.json', plan, n)
    return pins


def _reference_index_claims(pins, layer_path, name, spools):
    """A reference layer's own document (a few KB): each spool's row index as a claim, and the reference's relative
    path must resolve to the pinned spool (load_retained_layers' resolve() rule) else reference_path_differs."""
    try:
        import frankie_box_layer_spool as LS
        document = LS.read_reference(layer_path)
    except (OSError, ValueError, ImportError):
        return 0
    if document is None:
        return 0
    n = 0
    for key, ref in LS.spool_refs(document).items():
        pinned = (spools.get(key) or {}).get('path')
        target = str(LS.spool_path(layer_path, ref))
        if pinned and os.path.realpath(target) != os.path.realpath(pinned):
            job = pins.jobs.get(os.path.realpath(pinned))
            if job is not None:
                job['pre'].append('reference_path_differs')
        pins.claim('layer %s (reference document):%s' % (name, key), pinned or target, ref.get('bytes'),
                   ref.get('sha256'), count=ref.get('count'), index=ref.get('index'), kind='spool')
        n += 1
    return n


def add_manifest(pins, manifest_path):
    """A CLEAN step's moved-manifest (FRANKIE_ROOT_MOVE_MANIFEST_V1): every move becomes a claim and a check that the
    symlink at old_path points at new_path (or that an S3 move left its pointer). The validator reads new_path ONCE,
    through the same job as the pin (one realpath)."""
    body = _load(manifest_path)
    moves = (body or {}).get('moves') if isinstance(body, dict) else None
    if not isinstance(moves, list):
        pins.problems.append('moved manifest unreadable or without moves: %s' % manifest_path)
        pins.document(manifest_path, body, 0)
        return
    n = 0
    archives = []
    for move in moves:
        old, new = move.get('old_path'), move.get('new_path')
        if not old:
            continue
        if move.get('kind') == 'bind_mount':
            # a guarded directory moved by bind mount (frankie_box_root_move.do_bind_mount): a real directory at old_path,
            # no symlink; its pinned files are ordinary jobs read once through the mount
            problems = []
            if not os.path.isdir(old) or os.path.islink(old):
                problems.append('bind_mount_missing' if not os.path.isdir(old) else 'bind_mount_is_symlink')
            archives.append(dict(old_path=old, new_path=new, kind='bind_mount', files=len(move.get('files') or []),
                                 ismount=os.path.ismount(old) if os.path.isdir(old) else None,
                                 status=problems[0] if problems else 'bind_mount_ok', problems=problems,
                                 check='stat (a real directory; the pins inside are read once as ordinary jobs)'))
            n += 1
            continue
        if move.get('kind') == 'archive':
            # a directory archived as one tar.zst (frankie_box_root_move): the symlink at old_path must point at it and
            # the archive's size must be the bytes written on its stream; never read here (one pass, no read-back)
            problems = []
            if not os.path.islink(old):
                problems.append('manifest_symlink_missing')
            elif new and os.path.realpath(old) != os.path.realpath(new):
                problems.append('manifest_target_differs')
            try:
                size = os.stat(new).st_size if new else None
            except OSError:
                size, problems = None, problems + ['missing']
            if size is not None and move.get('bytes_archived') is not None and size != move['bytes_archived']:
                problems.append('bytes_differ')
            archives.append(dict(old_path=old, new_path=new, bytes_archived=move.get('bytes_archived'), observed_bytes=size,
                                 sha256_recorded=move.get('sha256'), status=problems[0] if problems else 'archive_symlink_ok',
                                 problems=problems, check='stat (the archive is not read)'))
            n += 1
            continue
        if move.get('bucket'):
            pins.claim('moved-manifest:s3', old, move.get('bytes'), move.get('sha256'),
                       extra=dict(manifest_s3=dict(bucket=move['bucket'], key=move.get('key'))))
            n += 1
            continue
        if not new:
            continue
        job_real = os.path.realpath(old)
        checks = []
        if not os.path.islink(old):
            checks.append('manifest_symlink_missing')
        elif job_real != os.path.realpath(new):
            checks.append('manifest_target_differs')
        pins.claim('moved-manifest:%s' % new, old, move.get('bytes'), move.get('sha256'), extra=dict(manifest_new_path=new))
        job = pins.jobs[os.path.realpath(old)]
        for check in checks:
            if check not in job['pre']:
                job['pre'].append(check)
        job['manifest'] = dict(old_path=old, new_path=new)
        n += 1
    pins.archives = archives
    for item in archives:
        if item['problems']:
            pins.problems.append('archived %s: %s' % (item['old_path'], '; '.join(item['problems'])))
    pins.document(manifest_path, body, n)


def _walk_pins(pins, source, value, where):
    """Every {path, bytes, sha256[, count]} object anywhere inside a receipt value (the common FRANKIE_*_V* artifact
    shape) becomes one claim; lists and dicts are walked, nothing else is interpreted."""
    n = 0
    if isinstance(value, dict):
        if _has_witness(value) and isinstance(value.get('path'), str) and value['path'].startswith('/'):
            count = value.get('count') if isinstance(value.get('count'), int) and str(value['path']).endswith('.jsonl') else None
            pins.claim('%s:%s' % (source, where), value['path'], value['bytes'], value['sha256'], count=count)
            n += 1
        for key, item in value.items():
            if key == 'claims':
                continue
            n += _walk_pins(pins, source, item, '%s.%s' % (where, key) if where else str(key))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            n += _walk_pins(pins, source, item, '%s[%d]' % (where, i))
    return n


def collect_generic(receipt_paths, root=None):
    """The pins of ANY stage: every artifact object its receipt files record, plus each receipt file itself (measured;
    its own bytes become the expectation, so a later run sees it unchanged). Raises ValueError when no receipt loads."""
    pins = Pins(root or (Path(receipt_paths[0]).parent if receipt_paths else '/'))
    loaded = 0
    for path in receipt_paths:
        path = Path(path)
        body = _load(path)
        n = 0
        if body is not None:
            loaded += 1
            n = _walk_pins(pins, path.name, body, '')
            pins.claim('self (measured): ' + path.name, path, path.stat().st_size if path.is_file() else None, None)
        pins.document(path, body, n)
    if not loaded:
        raise ValueError('no receipt file loads among: %s' % ', '.join(str(p) for p in receipt_paths))
    return pins


# ------------------------------------------------------------------------------------------------------- one file

def symlink_chain(path):
    """([{path, target}...] for every link followed, final real path or None, error or None)."""
    chain, current = [], Path(path)
    for _ in range(MAX_LINKS):
        try:
            if not current.is_symlink():
                if current.exists():
                    return chain, str(current), None
                return chain, None, 'missing'
            target = os.readlink(current)
        except OSError as error:
            return chain, None, 'unresolvable_symlink (%s)' % error.__class__.__name__
        chain.append(dict(path=str(current), target=target))
        current = Path(os.path.normpath(os.path.join(current.parent, target)))
    return chain, None, 'unresolvable_symlink (loop or more than %d links)' % MAX_LINKS


def _stat_key(path):
    info = os.stat(path)
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def reader_refusals(root, path, chain_paths):
    """The safe_path-guarded readers that would refuse this artifact: a symlink at the path or any parent within R
    under a guarded location. [] when the chain holds no symlink there."""
    root, path = Path(root), Path(path)
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return []
    within = [path] + [p for p in path.parents if p != root and root in p.parents]
    linked = set(chain_paths)
    try:
        if not any(str(p) in linked or p.is_symlink() for p in within):
            return []
    except OSError:
        return []
    for prefix, guards in READER_GUARDS:
        if rel.startswith(prefix):
            return list(guards)
    return []


def _s3_head(job, pointer):
    """An S3-archived artifact: HeadObject against the pointer's bucket/key; bytes and Metadata.sha256 only. Never a
    download; the result says so."""
    expected = job['expected']
    bucket, key = pointer.get('bucket'), pointer.get('key')
    client = S3_CLIENT
    try:
        if client is None:
            import boto3
            client = boto3.client('s3', region_name=pointer.get('region'))
        head = client.head_object(Bucket=bucket, Key=key)
    except Exception as error:  # noqa: BLE001 - unreachable is a status, not a crash of the whole validation
        return dict(status='s3_unreachable', problems=['s3_unreachable: %s: %s' % (type(error).__name__, str(error)[:200])],
                    observed=dict(bucket=bucket, key=key), check='head')
    observed = dict(bucket=bucket, key=key, bytes=head.get('ContentLength'),
                    sha256=(head.get('Metadata') or {}).get('sha256'))
    problems = []
    if expected.get('bytes') is not None and observed['bytes'] != expected['bytes']:
        problems.append('s3_head_differs: bytes %s vs %s' % (observed['bytes'], expected['bytes']))
    if expected.get('sha256') and observed['sha256'] != expected['sha256']:
        problems.append('s3_head_differs: sha256 %s vs %s' % (observed['sha256'], expected['sha256']))
    if pointer.get('sha256') and expected.get('sha256') and pointer['sha256'] != expected['sha256']:
        problems.append('s3_head_differs: pointer sha256 %s vs pinned %s' % (pointer['sha256'], expected['sha256']))
    return dict(status='s3_head_differs' if problems else 'archived_s3_head_ok', problems=problems, observed=observed,
                check='head (not a read)')


def check_job(job):
    """Worker: one streamed read of the file at job['path'] (through its symlink chain), compared with job['expected'].
    Returns the artifact record (status, problems, observed, chain, stat, seconds, bytes_read)."""
    started = time.monotonic()
    path, expected = job['path'], job['expected']
    out = dict(path=path, kind=job['kind'], expected=expected, claims=job['claims'], problems=list(job.get('pre') or []),
               observed={}, chain=[], stat=None, bytes_read=0, check='read')
    chain, final, error = symlink_chain(path)
    out['chain'] = chain
    if error:
        pointer_path = Path(path).with_name(Path(path).name + POINTER_SUFFIX)
        pointer = _load(pointer_path) if error == 'missing' and pointer_path.is_file() else None
        if isinstance(pointer, dict) and pointer.get('bucket'):
            head = _s3_head(job, pointer)
            out.update(observed=head['observed'], check=head['check'], pointer=str(pointer_path))
            out['problems'] += head['problems']
            out['status'] = head['status'] if not out['problems'] or head['status'] != 'archived_s3_head_ok' \
                else out['problems'][0].split(':')[0]
            out['seconds'] = round(time.monotonic() - started, 3)
            return out
        out['problems'].append(error.split(' ')[0] if error.startswith('unresolvable') else error)
        out['status'] = out['problems'][0]
        out['seconds'] = round(time.monotonic() - started, 3)
        return out
    try:
        out['stat'] = _stat_key(final)
        if job['kind'] in ('spool', 'ledger') and final.endswith('.jsonl'):
            import frankie_box_layer_spool as LS
            try:
                scan = LS.scan_spool(final)
                observed = dict(bytes=scan['bytes'], sha256=scan['sha256'], count=scan['count'], index=scan['index'])
            except ValueError as refusal:
                if 'partial final record' not in str(refusal):
                    raise
                size = os.stat(final).st_size
                observed = dict(bytes=size, sha256=None, count=None)
                out['problems'].append('partial_final_record')
        else:
            import frankie_box_filehash as FH
            observed = FH.witness(final)
        out['bytes_read'] = observed.get('bytes') or 0
    except OSError as error:
        out['problems'].append('missing' if isinstance(error, FileNotFoundError) else 'unreadable: %s' % error)
        out['status'] = out['problems'][0].split(':')[0]
        out['seconds'] = round(time.monotonic() - started, 3)
        return out
    out['observed'] = {k: v for k, v in observed.items() if k != 'index'}
    if expected.get('bytes') is not None and observed.get('bytes') != expected['bytes']:
        out['problems'].append('bytes_differ')
    if expected.get('sha256') and observed.get('sha256') is not None and observed['sha256'] != expected['sha256']:
        out['problems'].append('sha256_differ')
    if expected.get('count') is not None and observed.get('count') is not None and observed['count'] != expected['count']:
        out['problems'].append('count_differ')
    if expected.get('index') is not None and observed.get('index') is not None and observed['index'] != expected['index']:
        out['problems'].append('index_differs')
    if out['problems'] and 'claims_conflict' in out['problems']:
        out['matches'] = [c['source'] for c in job['claims']
                          if all(c.get(k) is None or c[k] == observed.get(k) for k in ('bytes', 'sha256', 'count'))]
    if job['kind'] == 'ledger':
        recorded = next((c.get('rows_recorded') for c in job['claims'] if c.get('rows_recorded') is not None), None)
        out['ledger_rows_match'] = None if recorded is None or observed.get('count') is None else recorded == observed['count']
    out['reader_refusals'] = reader_refusals(job['root'], path, [c['path'] for c in chain])
    out['status'] = out['problems'][0].split(':')[0] if out['problems'] else 'ok'
    out['seconds'] = round(time.monotonic() - started, 3)
    return out


# ------------------------------------------------------------------------------------------------------ the run

def plan_jobs(pins):
    """Largest first (the pinned bytes; a size from lstat when no claim carries one)."""
    def size(job):
        if job['expected'].get('bytes') is not None:
            return job['expected']['bytes']
        try:
            return os.stat(job['path']).st_size
        except OSError:
            return 0
    return sorted(pins.jobs.values(), key=lambda j: (-size(j), j['path']))


def unpinned_present(root, pins, own):
    """Files under R no document pins: listed with their lstat size, never read, never a failure."""
    root = Path(root)
    listed, total = [], 0
    for path in root.rglob('*'):
        if path.is_dir() and not path.is_symlink():
            continue
        if os.path.realpath(str(path)) in pins.jobs or str(path) in own or str(path.parent) in own:
            continue
        total += 1
        if len(listed) < MAX_UNPINNED:
            try:
                listed.append(dict(path=str(path), bytes=path.lstat().st_size, symlink=path.is_symlink()))
            except OSError:
                listed.append(dict(path=str(path), bytes=None, symlink=None))
    return dict(count=total, listed=listed, truncated=total > len(listed), status='not_pinned_but_present')


def _parse_cpus(text):
    cpus = set()
    for part in (text or '').split(','):
        part = part.strip()
        if part:
            low, _, high = part.partition('-')
            cpus.update(range(int(low), int(high or low) + 1))
    return sorted(cpus)


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(value, indent=1, sort_keys=True, default=str) + '\n', encoding='utf-8')
    os.replace(pending, path)


def _reusable(entry, job):
    """A saved per-file result is reused when it was ok, its chain is the same and the target's stat is unchanged."""
    if not entry or entry.get('status') not in OK_STATUSES or entry.get('check') != 'read':
        return False
    chain, final, error = symlink_chain(job['path'])
    if error or chain != entry.get('chain'):
        return False
    try:
        return _stat_key(final) == entry.get('stat') and entry.get('expected') == job['expected']
    except OSError:
        return False


def validate(root=None, *, cpus=None, out=None, moved_manifest=None, run_dir=None, stop=None, say=print, pins=None,
             stage='root', roots=None):
    """Run the validation; returns (receipt dict, exit code). stop() -> True ends submissions (the lane stop file or
    SIGTERM when None). root: a ROOT attempt directory (its six documents are the pins); pins: prepared Pins of any
    stage (collect_generic) with `roots` the directories listed for unpinned files; stage names the receipt."""
    import frankie_box_lane_pin as LP
    root = Path(root) if root else None
    if root is not None and root.is_symlink():
        raise ValueError('the attempt directory itself is a symlink; refused (only its contents may move): %s' % root)
    if out is None and root is None:
        raise ValueError('--out is required without --root')
    out = Path(out) if out else root / 'work' / 'root-validate.json'
    state_dir = out.parent / ('%s-validate' % stage)
    os.environ['FRANKIE_ROOT_VALIDATE_DIR'] = str(state_dir)
    partial_path = state_dir / 'partial.json'
    started = time.time()
    if pins is None:
        pins = collect_pins(root, run_dir)
    roots = [Path(r) for r in (roots if roots is not None else ([root] if root is not None else []))]
    if moved_manifest:
        add_manifest(pins, moved_manifest)
    jobs = plan_jobs(pins)
    lane = list(cpus) if cpus else LP.lane_cpus()
    workers = max(1, len(lane) - 1)
    cpu_map = LP.record(workers, lane, what='%s-validate: one worker per file, largest first' % stage)

    saved = _load(partial_path) if partial_path.is_file() else None
    saved_entries = (saved or {}).get('entries') if isinstance(saved, dict) and saved.get('root') == str(pins.root) else {}
    results, skipped, pending = {}, [], []
    for job in jobs:
        entry = (saved_entries or {}).get(job['realpath'])
        if _reusable(entry, job):
            results[job['realpath']] = dict(entry, reused_from_partial=True)
            skipped.append(job['path'])
        else:
            pending.append(job)

    stop_file = os.environ.get('FRANKIE_LANE_STOP_FILE')
    marked = [False]
    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda *_: marked.__setitem__(0, True))

    def stopping():
        return marked[0] or bool(stop_file and Path(stop_file).exists()) or bool(stop and stop())

    probe = None
    try:
        import frankie_box_progress
        probe = frankie_box_progress.Probe(state_dir)
        probe.cpus, probe.workers = lane, workers
        probe.update('%s-validate' % stage, len(skipped), len(jobs))
    except Exception:  # noqa: BLE001 - the probe never changes the outcome
        probe = None

    def save_partial():
        _write_json(partial_path, dict(schema=PARTIAL_SCHEMA, root=str(pins.root), at=time.time(),
                                       entries={k: v for k, v in results.items()}))

    report = {}
    stopped = False
    try:
        if pending:
            for job, result in LP.ordered_map(check_job, pending, workers, cpus=lane, stop=stopping, report=report,
                                              poll=1.0):
                results[job['realpath']] = result
                save_partial()
                if probe is not None:
                    probe.update('%s-validate' % stage, len(results), len(jobs))
                say('%-22s %14s B %8.1f s  %s%s' % (result['status'], result['observed'].get('bytes'),
                                                   result.get('seconds') or 0, result['path'],
                                                   '  <- ' + '; '.join(result['problems']) if result['problems'] else ''))
        stopped = stopping() and len(results) < len(jobs)
    finally:
        signal.signal(signal.SIGTERM, previous)
    save_partial()

    artifacts = [results.get(job['realpath']) for job in jobs if results.get(job['realpath']) is not None]
    not_done = [job['path'] for job in jobs if job['realpath'] not in results]
    mismatches = [a for a in artifacts if a['status'] not in OK_STATUSES]
    not_readable = [a for a in artifacts if a['status'] in OK_STATUSES
                    and (a.get('reader_refusals') or a['status'] == 'archived_s3_head_ok')]
    if stopped or not_done:
        code = EXIT_SAVED
    elif mismatches or pins.problems:
        code = EXIT_MISMATCH
    elif not_readable:
        code = EXIT_NOT_READABLE
    else:
        code = EXIT_OK
    own = {str(out), str(state_dir), str(partial_path), str(state_dir / 'progress.json')}
    unpinned = [unpinned_present(r, pins, own) for r in roots]
    receipt = dict(schema=SCHEMA, at=started, root=str(root) if root else None, stage=stage, roots=[str(r) for r in roots],
                   seconds=round(time.time() - started, 3),
                   cpus=cpu_map, documents=pins.documents, document_problems=pins.problems,
                   artifacts=artifacts, not_done=not_done, skipped_unchanged=skipped,
                   unpinned=unpinned[0] if len(unpinned) == 1 else dict(
                       count=sum(u['count'] for u in unpinned), listed=[x for u in unpinned for x in u['listed']][:MAX_UNPINNED],
                       truncated=any(u['truncated'] for u in unpinned), status='not_pinned_but_present'),
                   totals=dict(pinned=len(jobs), checked=len(artifacts), ok=sum(1 for a in artifacts if a['status'] == 'ok'),
                               archived_s3=sum(1 for a in artifacts if a['status'] == 'archived_s3_head_ok'),
                               mismatches=len(mismatches), not_readable=len(not_readable),
                               bytes_read=sum(a.get('bytes_read') or 0 for a in artifacts if not a.get('reused_from_partial')),
                               reused_from_partial=len(skipped)),
                   mismatches=[dict(path=a['path'], status=a['status'], problems=a['problems']) for a in mismatches],
                   reader_refusals=[dict(path=a['path'], guards=a['reader_refusals']) for a in not_readable
                                    if a.get('reader_refusals')],
                   archives=pins.archives, pool=report, stopped=stopped, exit_code=code,
                   rule='every pinned artifact read once through its symlink chain; nothing modified; exit 0 only when '
                        'every pin is ok and readable by the next stage; 3 mismatch; 4 verified but behind a safe_path '
                        'reader\'s symlink or in S3; 75 stopped early (partial.json resumes it)')
    _write_json(out, receipt)
    if probe is not None:
        probe.update('%s-validate' % stage, len(results), len(jobs), state='complete' if not stopped else 'running')
    return receipt, code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    parser.add_argument('--root', help='the ROOT attempt directory R (its six pin documents)')
    parser.add_argument('--receipt', action='append', default=[], help='any stage: a receipt file to collect pins from (repeatable)')
    parser.add_argument('--stage', default='root', help='the stage name on the receipt and the probe')
    parser.add_argument('--dir', action='append', default=[], help='any stage: an output directory listed for unpinned files')
    parser.add_argument('--cpus', help='CPU ranges (0-31); default FRANKIE_LANE_CPUS / the affinity')
    parser.add_argument('--out', help='receipt path (default R/work/root-validate.json)')
    parser.add_argument('--moved-manifest', help='the CLEAN step\'s FRANKIE_ROOT_MOVE_MANIFEST_V1 to cross-check')
    parser.add_argument('--run-dir', help='the Run directory (days/<day>/root.json pins the receipt sha256)')
    args = parser.parse_args(argv)
    if not args.root and not args.receipt:
        parser.error('--root R or --receipt <file> required')
    try:
        pins = collect_generic(args.receipt) if args.receipt and not args.root else None
        receipt, code = validate(args.root, cpus=_parse_cpus(args.cpus) if args.cpus else None, out=args.out,
                                 moved_manifest=args.moved_manifest, run_dir=args.run_dir, pins=pins, stage=args.stage,
                                 roots=args.dir or None)
    except ValueError as error:
        print('REFUSED:', error, file=sys.stderr)
        return EXIT_USAGE
    t = receipt['totals']
    print('%s validate %s: pinned %d, ok %d, archived(S3 head) %d, mismatches %d, not readable %d, reused %d, '
          '%d bytes read in %.1f s; exit %d' % (receipt['stage'], receipt['root'] or ', '.join(receipt['roots']), t['pinned'], t['ok'], t['archived_s3'], t['mismatches'],
                                                t['not_readable'], t['reused_from_partial'], t['bytes_read'],
                                                receipt['seconds'], code))
    for item in receipt['mismatches']:
        print('  MISMATCH %s: %s' % (item['path'], '; '.join(item['problems'])))
    for item in receipt['reader_refusals']:
        print('  NOT READABLE by %s: %s' % (', '.join(item['guards']), item['path']))
    return code


if __name__ == '__main__':
    sys.exit(main())
