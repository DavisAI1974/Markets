"""Owner-local native evidence selection and exact F_LAST placement, without a replay.

The authoritative ledgers are read once. Existing compressed section products remain
completed-knowledge evidence; they are not repeated observations or early live features.
"""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

SCHEMA = 'FRANKIE_NATIVE_SEARCH_INPUTS_V1'
EMISSION_SCHEMA = 'FRANKIE_NATIVE_EMISSION_V1'
LEDGERS = ('exact_member_rows.jsonl', 'exact_lifecycle_rows.jsonl', 'legacy_observable_rows.jsonl')
SECTIONS = ('bedrock_section_4_2', 'bedrock_section_4_4')
# The ROOT projection's plan (frankie_box_projection.project: work/derived/.projection-v2/plan.json) carries the producers'
# own crosswalk (native_layer_crosswalk.LAYER_PRODUCERS at the pin) for every projected bedrock layer: member_paths and
# lifecycle_sections. Optional (an older ROOT or a projection not yet run lacks it: listed); bound to the same ledgers.
PROJECTION_PLAN = 'projection_plan'


def entry_carriers(plan_doc):
    """{registry entry: dict(member=paths, sections=names, source)} from a projection plan's crosswalk, for every projected
    layer; None when no plan is given (callers fall back to frankie_box_all99_coverage.NATIVE_SERIES, the retained
    crosswalk's carrier text). Only the producers' recorded fields; nothing inferred."""
    if not isinstance(plan_doc, dict):
        return None
    out = {}
    for layer, record in (plan_doc.get('crosswalk') or {}).items():
        if isinstance(record, dict):
            out[layer] = dict(member=tuple(record.get('member_paths') or ()), sections=tuple(record.get('lifecycle_sections') or ()),
                              source='projection plan crosswalk (%s)' % (record.get('carrier') or record.get('kind')))
    return out


def evidence_contract(role):
    """Describe existing evidence roles; this does not admit a new consumer."""
    common = dict(schema='FRANKIE_NATIVE_EVIDENCE_ROLE_V1', role=role,
                  artifact_identity=['sha256', 'bytes'], additional_independent_observation=False)
    if role in LEDGERS[:2]:
        return dict(common, representation='exact_ordered_ledger_rows',
                    row_identity=['artifact_sha256', 'zero_based_ledger_ordinal'],
                    group_join=['input_cursor', 'instrument_id', 'ts_recv_ns'],
                    availability='GROUP_CLOSE at checked emission time; FINALIZE is post-stream knowledge only',
                    entity_identity='original row identities retained; section/list slots are not entity trajectories',
                    consumer='existing exact ROOT F_LAST placement; per-row dispositions state actual use')
    if role == LEDGERS[2]:
        return dict(common, representation='exact_ordered_ledger_rows',
                    row_identity=['artifact_sha256', 'zero_based_ledger_ordinal'],
                    availability='original row clocks retained; no new live placement',
                    consumer='retained source alias; not an additional live search observation')
    if role == PROJECTION_PLAN:
        return dict(common, representation='the producers\' own per-layer crosswalk (member_paths, lifecycle_sections) '
                                           'the ROOT projection ran with (frankie_box_projection plan.json)',
                    availability='static description of which ledger fields/sections carry which registry layer; no values',
                    consumer='names the registry entry of each native series and update (frankie_box_all99_coverage.NATIVE_SERIES '
                             'is the retained-crosswalk fallback); never a series itself')
    if role in ('receipt', 'result', *SECTIONS):
        return dict(common, representation=('completion_receipt' if role == 'receipt'
                                           else 'completed_calculation_product'),
                    availability='completed calculation; no whole-day backfill onto earlier live groups',
                    consumer='retained metadata or completed evidence; no new scientific consumer supplied')
    raise ValueError('unknown native evidence role')


def _witness(path):
    # one pass (2026-10-09): the process-cached witness (frankie_box_filehash: once per unchanged file per process)
    try:
        import frankie_box_filehash as F
    except ImportError:
        try:
            from deploy.aws.box import frankie_box_filehash as F
        except ImportError:
            from frankie_box_durable import witness
            return witness(path)
    return F.witness(path)


_PLAN_CACHE = {}


def plan_document(path):
    """(pin {path, bytes, sha256}, parsed document) of the ROOT projection plan (~150 MB), read ONCE per unchanged file
    per process (Greg, 2026-10-09: one pass): the same bytes are hashed and parsed; the witness is remembered in
    frankie_box_filehash so a later witness() of the unchanged file reads nothing. selected_files, the shared market
    timeline and the data export all take it here."""
    path = Path(path)
    info = os.stat(path)
    key = (str(path.resolve()), info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    hit = _PLAN_CACHE.get(key)
    if hit is not None:
        return dict(hit[0]), hit[1]
    raw = path.read_bytes()
    pin = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    if (os.stat(path).st_ino, os.stat(path).st_size, os.stat(path).st_mtime_ns) != key[2:]:
        raise ValueError('the projection plan changed while it was read: ' + str(path))
    document = json.loads(raw)
    _PLAN_CACHE.clear()                  # one plan per process at a time (the day's)
    _PLAN_CACHE[key] = (pin, document)
    try:
        try:
            import frankie_box_filehash as F
        except ImportError:
            from deploy.aws.box import frankie_box_filehash as F
        F.remember(path, {k: pin[k] for k in ('bytes', 'sha256')})
    except Exception:  # noqa: BLE001 - the cache is a convenience
        pass
    return dict(pin), document


def _check(path, pin, measured=None):
    if (measured if measured is not None else _witness(path)) != {k: pin[k] for k in ('bytes', 'sha256')}:
        raise ValueError('selected native evidence changed: ' + str(path))


# The selection checks of the large artifacts side by side (Greg, 2026-10-07 night: every serial pass on the lane's
# CPUs). selected_files verifies each selected ledger and section product against its derivation pin, one after the
# other; the three ledgers and two section products are the multi-GB ones. Their witnesses (bytes + sha256 of the same
# file, frankie_box_durable.witness) are computed up front on pinned lane threads (hashlib releases the GIL), only for
# paths that already pass take()'s own path rules; take() then runs every rule and comparison in its original order
# with the measured witness, so the selected list, the errors and their precedence are the serial ones. Where it ran
# and how long it took: LAST_SELECTION_CHECK (the export records it in MANIFEST.hashing.native_selection_check).
LAST_SELECTION_CHECK = {}


def _regular_under(root, pin, name, directory):
    """True when take() would accept this pin's path (absolute, no '..', no symbolic link, the expected name, inside
    its directory) and it is a regular file: only then is it read before take() runs."""
    try:
        path = Path(pin['path'])
        return (path.is_absolute() and '..' not in path.parts
                and not any(p.is_symlink() for p in (path, *path.parents))
                and path.name == name and path.relative_to(root).is_relative_to(directory) and path.is_file())
    except (KeyError, TypeError, ValueError, OSError):
        return False


# Session 9 (Greg: "fix before we get there so we don't have to stop"; one pass over the data, never two): the ROOT
# sealed and claimed every native ledger and section product (work/file-claims.jsonl, FRANKIE_FILE_CLAIM_V2: path,
# bytes, sha256, inode/size/mtime_ns/filesystem identity, sha256 of the last 64 KiB). The teacher's shared market
# timeline and the data stage each called selected_files, which hashed every ledger whole again (a2's member ledger is
# 193.7 GB, ~25 min at 131 MB/s, per stage). Now each large artifact takes its claim when one holds (the row's bytes and
# sha256 equal to the derivation pin, stat and tail unchanged: frankie_box_boss_session._claim_still_holds, one 64 KiB
# read); only a file with no holding claim is hashed whole (pinned lane threads as before), and that whole read, when
# it equals the pin with the stat unchanged across it, appends its claim row (existing rows byte for byte) so the next
# consumer takes it. The witness handed to take() is the same {bytes, sha256}; its basis rides on the future and on the
# selected item ('selection_basis'). FRANKIE_ROOT_LEGACY_REUSE_CHECK=full (or FRANKIE_ROOT_NATIVE_REUSE_CHECK=full)
# restores the whole reads.
_CLAIM_APPEND_LOCK = threading.Lock()


class _Known:
    """A finished witness with its basis (the claim), shaped like the future take() reads."""
    def __init__(self, value, basis):
        self.value, self.basis = value, basis

    def result(self):
        return self.value


class _Later:
    """One whole read computed when take() reaches it (the serial order), shaped like the future take() reads."""
    def __init__(self, function, basis):
        self.function, self.basis, self.done = function, basis, None

    def result(self):
        if self.done is None:
            self.done = (self.function(),)
        return self.done[0]


def _claims_mode():
    return 'full' if 'full' in (os.environ.get('FRANKIE_ROOT_LEGACY_REUSE_CHECK'),
                                os.environ.get('FRANKIE_ROOT_NATIVE_REUSE_CHECK')) else 'claim'


def _session_claims():
    try:
        import frankie_box_boss_session as S
    except ImportError:
        from deploy.aws.box import frankie_box_boss_session as S
    return S


def _claim_basis(path, pin, claims, work):
    """The basis text when the saved claim row for this path still holds and names the pin's bytes and sha256; else
    (None, why it is read whole). Never raises."""
    try:
        row = claims.get(str(Path(path).resolve()))
        if row is None:
            return None, 'no claim row for this path in work/file-claims.jsonl'
        if (row.get('bytes'), row.get('sha256')) != (pin['bytes'], pin['sha256']):
            return None, 'the claim row names other bytes/sha256 than the derivation pin'
        held = _session_claims()._claim_still_holds(row, claims_dir=work, claims=claims)
        if held is None:
            return None, 'the claim row no longer holds (inode, size, mtime_ns, filesystem or last 64 KiB changed)'
        return held, None
    except Exception as error:  # noqa: BLE001 - a claim is a hint: without one the file is read whole
        return None, 'claim not taken (%s: %s)' % (type(error).__name__, error)


def _whole_then_claim(path, pin, work):
    """The whole-file witness; when it equals the pin and the file's stat did not move across the read, its
    FRANKIE_FILE_CLAIM_V2 row is appended to work/file-claims.jsonl (existing rows byte for byte, one atomic rewrite)
    so the next consumer takes the claim. The append is a hint: it never raises; its outcome is listed."""
    before = Path(path).stat()
    seen = _witness(path)
    note = dict(path=str(path))
    try:
        if seen != {k: pin[k] for k in ('bytes', 'sha256')}:
            note['claim'] = 'not appended: the whole read differs from the pin (raised by the check)'
        else:
            from research.kalshi.frankie_boss.operations.ingest_block_sources import (file_claim, FILE_CLAIMS_NAME,
                                                                                       _write_claims_atomic)
            row = file_claim(path, seen['bytes'], seen['sha256'],
                             'native selection (selected_files) whole read at %s'
                             % time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
            if row['stat'] != [before.st_ino, before.st_size, before.st_mtime_ns]:
                note['claim'] = 'not appended: the file\'s stat moved during the whole read'
            else:
                target = Path(work) / FILE_CLAIMS_NAME
                with _CLAIM_APPEND_LOCK:
                    text = target.read_text(encoding='utf-8') if target.is_file() else ''
                    if text and not text.endswith('\n'):
                        text += '\n'
                    _write_claims_atomic(target, (text + json.dumps(row, sort_keys=True) + '\n').encode())
                note['claim'] = 'appended to ' + str(target)
    except Exception as error:  # noqa: BLE001 - the claim is a hint for the next consumer, never this check's outcome
        note['claim'] = 'not appended (%s: %s)' % (type(error).__name__, error)
    LAST_SELECTION_CHECK.setdefault('claims_appended', []).append(note)
    return seen


def _prefetch_witnesses(root, wanted):
    """(pool or None, {path: future-like of its witness}) for the (pin, name, directory) entries take() would read:
    a holding claim is the witness (no read); the rest are hashed whole on pinned threads (two or more) or when take()
    reaches them (one). Each future-like carries .basis ('by claim: ...' | 'read whole: <why>')."""
    LAST_SELECTION_CHECK.clear()
    work = Path(root) / 'work'
    mode = _claims_mode()
    claims = {}
    if mode == 'claim':
        try:
            claims = _session_claims()._load_file_claims(work)
        except Exception:  # noqa: BLE001 - no claims: every file is read whole
            claims = {}
    known, whole, bases = {}, [], {}
    for pin, name, directory in wanted:
        if not (isinstance(pin, dict) and _regular_under(root, pin, name, directory)):
            continue
        path = pin['path']
        if path in known or any(path == p for p, _, _ in whole):
            continue
        if mode == 'full':
            held, why = None, 'FRANKIE_ROOT_LEGACY_REUSE_CHECK=full (or FRANKIE_ROOT_NATIVE_REUSE_CHECK=full)'
        else:
            held, why = _claim_basis(path, pin, claims, work)
        if held is not None:
            known[path] = _Known({k: pin[k] for k in ('bytes', 'sha256')}, 'by claim: ' + held)
        else:
            whole.append((path, pin, 'read whole: ' + why))
        bases[path] = known[path].basis if path in known else whole[-1][2]
    LAST_SELECTION_CHECK.update(files=len(known) + len(whole), by_claim=len(known), read_whole=len(whole),
                                basis=bases, started=time.time())
    if len(whole) < 2:
        for path, pin, basis in whole:
            known[path] = _Later(lambda p=path, q=pin: _whole_then_claim(p, q, work), basis)
        return None, known
    try:
        import frankie_box_lane_pin as LP
    except ImportError:
        from deploy.aws.box import frankie_box_lane_pin as LP
    lane = LP.lane_cpus()
    count = max(1, min(len(whole), len(lane)))
    pool = LP.executor('thread', count, lane)
    LAST_SELECTION_CHECK.update(threads=count,
                                cpu_placement=LP.record(count, lane, what='native selection witnesses (pinned threads)'))
    for path, pin, basis in whole:
        future = pool.submit(_whole_then_claim, path, pin, work)
        future.basis = basis
        known[path] = future
    return pool, known


def selected_files(root, day):
    """Only completed, source-bound scientific artifacts, never checkpoints/staging."""
    root = Path(root).resolve()
    binding_path, calculation_path = root / 'source-binding.json', root / 'calculations-receipt.json'
    if not binding_path.is_file():
        return []
    binding = json.loads(binding_path.read_bytes())
    policy = binding.get('native_calculation_policy') or {}
    if policy.get('bedrock') is not True:
        return []
    if not calculation_path.is_file():
        raise ValueError('selected native ROOT has no completed calculation receipt')
    calculation = json.loads(calculation_path.read_bytes())
    if (str(calculation.get('day')) != str(day)
            or calculation.get('native_calculation_policy') != policy
            or calculation.get('status') not in ('calculations_retained', 'calculations_retained_with_failures')):
        raise ValueError('selected native ROOT completion or source policy differs')
    _check(binding_path, calculation['source_binding'])
    derive_path = root / 'work' / 'derive.json'
    _check(derive_path, calculation['derivation'])
    derive = json.loads(derive_path.read_bytes())
    if derive.get('source_binding') != binding:
        raise ValueError('native derivation belongs to another source binding')
    native = derive.get('bedrock') or {}
    if native.get('skipped') or not native.get('result') or set(native.get('ledgers') or {}) != set(LEDGERS):
        raise ValueError('native derivation lacks its completed authoritative ledgers')
    selected = []
    layers = derive.get('layers') or {}
    # one pass (T3, 2026-10-09): result.json (~225 MB) takes the ROOT's claim with the ledgers and sections
    pool, measured = _prefetch_witnesses(root, [(native['ledgers'].get(name), name, 'work/bedrock') for name in LEDGERS]
                                         + [(native.get('result'), 'result.json', 'work/bedrock')]
                                         + [(layers.get(name), name + '.json.gz', 'work/derived/.projection-v2')
                                            for name in SECTIONS])
    try:
        return _take_all(root, binding, native, derive, policy, selected, measured)
    finally:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
        if LAST_SELECTION_CHECK.get('started'):
            LAST_SELECTION_CHECK['seconds'] = round(time.time() - LAST_SELECTION_CHECK.pop('started'), 3)


def _take_all(root, binding, native, derive, policy, selected, measured):
    """selected_files' selection, in its original order (the witnesses of `measured` are used where present)."""
    def take(role, pin, name, directory):
        path = Path(pin['path'])
        if (not path.is_absolute() or '..' in path.parts
                or any(p.is_symlink() for p in (path, *path.parents))):
            raise ValueError('native artifact path is not a regular owner-local path')
        relative = path.relative_to(root)
        if path.name != name or not relative.is_relative_to(directory):
            raise ValueError('native artifact is outside its selected scientific directory')
        future = measured.get(pin['path'])
        _check(path, pin, future.result() if future is not None else None)
        selected.append(dict(stage='root', path=str(relative), source=str(path),
            pattern='completed native derivation:' + role, what='existing exact native calculation evidence',
            native_role=role, evidence_contract=evidence_contract(role),
            expected={k: pin[k] for k in ('bytes', 'sha256')},
            selection_basis=getattr(future, 'basis', None) or 'read whole: a small artifact (claims are taken for the '
                                                               'ledgers and section products)'))

    take('receipt', native['receipt'], 'receipt.json', 'work/bedrock')
    take('result', native['result'], 'result.json', 'work/bedrock')
    run = json.loads(Path(native['receipt']['path']).read_bytes())
    if run.get('result') != native['result'] or run.get('ledgers') != native['ledgers']:
        raise ValueError('native completion and derivation disagree on scientific artifacts')
    if run.get('emission') != native.get('emission') or native.get('emission') != policy.get('emission'):
        raise ValueError('native emission implementation is not bound by the selected source policy')
    for name in LEDGERS:
        take(name, native['ledgers'][name], name, 'work/bedrock')
    for name in SECTIONS:
        entry = derive['layers'].get(name)
        if not entry or not entry.get('bedrock') or entry.get('encoding') != 'gzip-json':
            raise ValueError('native derivation lacks its exact compressed section product: ' + name)
        take(name, entry, name + '.json.gz', 'work/derived/.projection-v2')
    plan_path = root / 'work/derived/.projection-v2/plan.json'
    if plan_path.is_file() and not plan_path.is_symlink():
        # the producers' per-layer crosswalk; it must name the very ledgers selected above (else integrity, raised)
        plan_pin, plan_doc = plan_document(plan_path)      # read once per process: hashed and parsed from one read
        measured[plan_pin['path']] = _Known({k: plan_pin[k] for k in ('bytes', 'sha256')},
                                            'read once (plan_document: hashed and parsed from the same bytes)')
        for kind, name in (('member', LEDGERS[0]), ('lifecycle', LEDGERS[1])):
            if {k: (plan_doc.get('ledgers') or {}).get(kind, {}).get(k) for k in ('path', 'bytes', 'sha256')} != \
                    {k: native['ledgers'][name][k] for k in ('path', 'bytes', 'sha256')}:
                raise ValueError('the projection plan names other native ledgers than the selected derivation')
        take(PROJECTION_PLAN, plan_pin, 'plan.json', 'work/derived/.projection-v2')
    return selected


def _ranges_add(ranges, ordinal):
    if ranges and ranges[-1][1] + 1 == ordinal:
        ranges[-1][1] = ordinal
    else:
        ranges.append([ordinal, ordinal])


# ---- the ledger decode on the held lane (Greg, 2026-10-07 night: every piece pinned to its lane, concurrent) ---------
# The member and lifecycle ledgers are read once, in ledger order. The JSON decode of each line is independent of every
# other line, so above NATIVE_PARALLEL_MIN_BYTES the file is cut at line starts into ordered byte ranges and pinned
# forked workers decode them (json.loads of the same bytes); the parent receives the decoded rows range by range IN
# FILE ORDER and runs every check below unchanged and in order (emission provenance, exact member/lifecycle identities,
# the members map, the monotone ROOT position, dispositions with their ordinal ranges, the bucketing and columns()).
# A line that does not decode stops its range at that line: the rows before it are checked first, then the same
# decode error is raised, so the first failure is the serial one. The bytes are hashed in file order beside the
# workers and checked against the pin after the last row, as the serial read does. At most NATIVE_WINDOW_PER_WORKER
# ranges per worker are in flight (bounded memory). One worker or a small ledger: the serial read itself.
NATIVE_PARALLEL_MIN_BYTES = 64 << 20
NATIVE_RANGE_BYTES = 16 << 20
NATIVE_WINDOW_PER_WORKER = 2


def _line_ranges(path, size, piece_bytes):
    """Ordered [start, end) byte ranges of the file, each starting at a line start (cut just after a newline)."""
    cuts = [0]
    with open(path, 'rb') as handle:
        nominal = piece_bytes
        while nominal < size:
            handle.seek(nominal - 1)
            handle.readline()
            cut = handle.tell()
            if cuts[-1] < cut < size:
                cuts.append(cut)
            nominal = max(cut, nominal) + piece_bytes
    cuts.append(size)
    return [(str(path), a, b) for a, b in zip(cuts, cuts[1:]) if b > a]


def _decode_range(args):
    """(decoded rows of the range in order, the first decode error or None)."""
    try:                       # a forked worker never keeps the search's mark-only SIGTERM handler (ROOT's contract)
        from frankie_box_experiment_search import _worker_default_sigterm
    except ImportError:
        from deploy.aws.box.frankie_box_experiment_search import _worker_default_sigterm
    _worker_default_sigterm()
    path, start, end = args
    rows, position = [], start
    with open(path, 'rb') as handle:
        handle.seek(start)
        for raw in handle:
            if position >= end:
                break
            position += len(raw)
            try:
                rows.append(json.loads(raw))
            except Exception as error:  # noqa: BLE001 - re-raised by the parent after the rows before it are checked
                return rows, error
    return rows, None


def _decoded_lines(path, workers):
    """Yield (ordinal, decoded row) of the ledger in file order; (bytes, sha256) of every byte read, via `done`."""
    done = {}
    size = path.stat().st_size

    def serial():
        hashed, total = hashlib.sha256(), 0
        with path.open('rb') as handle:
            for ordinal, raw in enumerate(handle):
                hashed.update(raw)
                total += len(raw)
                yield ordinal, json.loads(raw)
        done.update(bytes=total, sha256=hashed.hexdigest(), mode='serial', workers=1)

    def parallel():
        import multiprocessing
        try:
            import frankie_box_lane_pin as LP
        except ImportError:
            from deploy.aws.box import frankie_box_lane_pin as LP
        ranges = _line_ranges(path, size, NATIVE_RANGE_BYTES)
        count = min(workers, len(ranges))
        try:
            from frankie_box_experiment_search import FrontierHasher
        except ImportError:
            from deploy.aws.box.frankie_box_experiment_search import FrontierHasher
        # the search's shared hasher (stacks pass): the hash reads the pages the decode workers read (one disk pass),
        # and an early stop is bounded (no wait on the rest of the ledger after a failure)
        window = count * NATIVE_WINDOW_PER_WORKER
        hasher = FrontierHasher(path, window * max(b - a for _, a, b in ranges), name='native-ledger-sha256')
        ordinal, finished, recovery = 0, False, dict(worker_deaths=[], redone=[])
        try:
            # pinned, in file order, at most NATIVE_WINDOW_PER_WORKER ranges per worker in flight; the hasher starts
            # after the fork; a dead worker's range is decoded again, never a hang (frankie_box_lane_pin.ordered_map)
            for job, (rows, error) in LP.ordered_map(_decode_range, ranges, count,
                                                      context=multiprocessing.get_context('fork'),
                                                      window=window, on_start=hasher.start, report=recovery):
                for row in rows:
                    yield ordinal, row
                    ordinal += 1
                if error is not None:
                    raise error
                hasher.advance(job[2])
            finished = True
        finally:
            if not finished:
                recovery['hasher_ended_after_stop'] = hasher.stop()
        hashed_bytes, digest = hasher.finish()
        state = dict(bytes=hashed_bytes)
        done.update(bytes=state['bytes'], sha256=digest, mode='fork_pool_line_ranges', workers=count, hashing=hasher.report(),
                    ranges=len(ranges), pool_recovery=recovery,
                    cpu_placement=LP.record(count, what='native ledger decode workers'))

    use_parallel = workers > 1 and size >= NATIVE_PARALLEL_MIN_BYTES
    return (parallel() if use_parallel else serial()), done


def read_columns(day_dir, columns, frame_numeric, receive_times, *, workers=1):
    """Return native numeric/text columns on the unchanged ROOT frame axis and receipts.

    Lifecycle slots retain emission order within each section/group. A slot is not
    a persistent entity track. All entity identifiers and row fields remain present.
    Unplaced/post-stream rows stay in their hash-bound original ledger, with exact
    ordinal ranges reported; none are silently assigned an earlier timestamp.
    """
    day_dir = Path(day_dir)
    manifest = json.loads((day_dir / 'MANIFEST.json').read_bytes())
    selected = {}
    for item in manifest['files']:
        if item.get('native_role'):
            role = item['native_role']
            if role in selected or item['stage'] != 'root':
                raise ValueError('duplicate or non-ROOT native export role')
            # Older exports have no role descriptor. Keep their existing read
            # path; a supplied descriptor must describe this same interpretation.
            if ('evidence_contract' in item
                    and item['evidence_contract'] != evidence_contract(role)):
                raise ValueError('native export evidence role contract differs')
            path = Path(item['path'])
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('native export path escapes the owning export')
            selected[role] = (day_dir / 'root' / path, item)
    if not selected:
        return {}, {}, [], [dict(source='native', reason='no selected completed native evidence in this export')]
    required = {'receipt', 'result', *LEDGERS, *SECTIONS}
    if not required <= set(selected) <= required | {PROJECTION_PLAN}:
        raise ValueError('native export has an incomplete or unknown artifact set')
    # The registry entry of each native series: the producers' per-layer crosswalk in the projection plan when the export
    # carries it (bound to these ledgers by selected_files), else the retained crosswalk's carrier text. Listed per entry.
    import frankie_box_all99_coverage as ALL99
    plan_carriers = None
    if PROJECTION_PLAN in selected:
        plan_path, plan_item = selected[PROJECTION_PLAN]
        raw = plan_path.read_bytes()
        if len(raw) != plan_item['bytes'] or hashlib.sha256(raw).hexdigest() != plan_item['sha256']:
            raise ValueError('exported projection plan differs from its pin')
        plan_carriers = entry_carriers(json.loads(raw))
    carriers = {name: (dict(plan_carriers[name]) if plan_carriers and name in plan_carriers else
                       dict(ALL99.NATIVE_SERIES[name], source='retained crosswalk carrier text (NATIVE_SERIES)'))
                for name in ALL99.NATIVE_ENTRIES}
    n = len(receive_times)
    from frankie_box_market_timeline import frame_index
    frames, _ = frame_index(frame_numeric, receive_times)
    index = {(frame['cursor'], frame['instrument'], frame['stamp']): position
             for position, frame in enumerate(frames or [])}
    members = {}
    numeric, text, sources, notes = {}, {}, [], []

    def load(ledger, source):
        path, pin = selected[ledger]
        report = dict(source=source, schema=SCHEMA, path=str(path), sha256=pin['sha256'],
            bytes=pin['bytes'], rows=0, searched_rows=0, dispositions={}, sections={},
            evidence_contract=evidence_contract(ledger),
            export_contract_present='evidence_contract' in pin,
            placement='exact emitting INPUT cursor + instrument + receive time on existing F_LAST axis',
            entity_rule='all identities retained; section/list positions are not identity-linked trajectories')
        sources.append(report)

        def disposition(reason, ordinal, row):
            target = report['dispositions'].setdefault(reason, dict(rows=0, ordinal_ranges=[]))
            target['rows'] += 1
            _ranges_add(target['ordinal_ranges'], ordinal)
            section = str(row.get('emitting_section') or 'member')
            counts = report['sections'].setdefault(section, {})
            counts[reason] = counts.get(reason, 0) + 1

        def rows():
            previous = -1
            started = time.time()
            decoded, read = _decoded_lines(path, workers)
            try:
                for ordinal, row in decoded:
                    if not isinstance(row, dict):
                        raise ValueError('native ledger row is not an object')
                    report['rows'] += 1
                    provenance = row.get('frankie_emission')
                    if not isinstance(provenance, dict) or provenance.get('schema') != EMISSION_SCHEMA:
                        disposition('unsupported_emission_provenance', ordinal, row)
                        continue
                    phase = provenance.get('phase')
                    if phase == 'FINALIZE':
                        if (provenance.get('group_index') is not None
                                or provenance.get('instrument_id') is not None):
                            raise ValueError('finalization falsely names a live group')
                        if row.get('emitted_at_recv_ns') != provenance.get('ts_recv_ns'):
                            raise ValueError('finalization row and emission clocks disagree')
                        disposition('post_stream_knowledge_only', ordinal, row)
                        continue
                    if phase != 'GROUP_CLOSE':
                        disposition('unsupported_emission_phase', ordinal, row)
                        continue
                    values = [provenance.get(k) for k in ('group_index', 'input_cursor', 'instrument_id', 'ts_recv_ns')]
                    if any(isinstance(v, bool) or not isinstance(v, int) for v in values) or min(values[:2]) < 0:
                        raise ValueError('native emission provenance is not exact integer identity')
                    group, cursor, instrument, stamp = values
                    key = (cursor, instrument, stamp)
                    if ledger == LEDGERS[0]:
                        if (group != ordinal or row.get('group_index') != group
                                or row.get('instrument_id') != instrument or row.get('ts_recv_ns') != stamp
                                or (row.get('clocks') or {}).get('first_lawful_availability_ns') != stamp):
                            raise ValueError('native member and emission identities disagree')
                        members[group] = key
                    elif members.get(group) != key:
                        raise ValueError('native lifecycle emission does not name its exact member')
                    elif row.get('emitted_at_recv_ns') != stamp:
                        raise ValueError('native lifecycle availability and emission clocks disagree')
                    position = index.get(key)
                    if position is None:
                        disposition('no_matching_root_frame', ordinal, row)
                        continue
                    if position < previous:
                        raise ValueError('native emission order moves backwards on the ROOT axis')
                    previous = position
                    disposition('searched', ordinal, row)
                    report['searched_rows'] += 1
                    yield position, row
            finally:
                decoded.close()   # an early check failure stops the decode workers and the hasher now
            if read.get('bytes') != pin['bytes'] or read.get('sha256') != pin['sha256']:
                raise ValueError('native exported ledger changed during its single read')
            report['parse'] = dict({k: v for k, v in read.items() if k not in ('bytes', 'sha256')},
                                   seconds=round(time.time() - started, 3),
                                   basis='ordered line ranges decoded by pinned workers; every check in the parent in '
                                         'ledger order; bytes hashed in file order against the pin'
                                         if read.get('mode') != 'serial' else 'one serial read')

        def aligned():
            iterator = iter(rows())
            pending = next(iterator, None)
            for position in range(n):
                bucket = {}
                while pending is not None and pending[0] == position:
                    row = pending[1]
                    if ledger == LEDGERS[0]:
                        if bucket:
                            raise ValueError('two native members claim one ROOT frame')
                        bucket = {'row': row}
                    else:
                        bucket.setdefault(str(row['emitting_section']), []).append(row)
                    pending = next(iterator, None)
                yield bucket
            if pending is not None:
                raise ValueError('native row placement is outside the ROOT frame axis')

        nums, strings, mixed, count = columns(aligned(), '')
        if count != n:
            raise ValueError('native reader changed the ROOT axis length')
        # columns preserves an empty mapping as a categorical leaf. Here the
        # empty outer mapping is only our absent-group placeholder, not a native
        # observation. Original member fields are nested under row; lifecycle
        # rows under their section, so no original field is removed here.
        nums.pop('', None)
        strings.pop('', None)
        numeric.update({source + '.' + k: v for k, v in nums.items()})
        text.update({source + '.' + k: v for k, v in strings.items()})
        report.update(numeric=sorted(nums), text=sorted(strings), mixed=mixed)

    load(LEDGERS[0], 'native.member')
    load(LEDGERS[1], 'native.lifecycle')
    for report in sources:
        report['registry_entries'] = {name: dict(member=list(c.get('member') or ()), sections=list(c.get('sections') or ()),
                                                 source=c.get('source')) for name, c in carriers.items()}
    if PROJECTION_PLAN not in selected:
        notes.append(dict(source='native', role=PROJECTION_PLAN, listed='no projection plan in this export: the native '
                          'entries are named by the retained crosswalk carrier text (NATIVE_SERIES)'))
    for role in ('result', 'receipt', LEDGERS[2], *SECTIONS) + ((PROJECTION_PLAN,) if PROJECTION_PLAN in selected else ()):
        path, item = selected[role]
        notes.append(dict(source='native', retained=str(path), sha256=item['sha256'], bytes=item['bytes'],
            role=role, disposition='retained_not_live_search',
            evidence_contract=evidence_contract(role),
            export_contract_present='evidence_contract' in item,
            reason=('legacy row evidence aliases the shared source; no duplicate observation' if role == LEDGERS[2]
                    else 'completed calculation/section evidence; no whole-day summary backfill or duplicate projected rows')))
    return numeric, text, sources, notes


SAVE_VALUE_CODE = ('SCHEMA', 'EMISSION_SCHEMA', 'LEDGERS', 'SECTIONS', 'PROJECTION_PLAN', 'entry_carriers', 'evidence_contract', '_witness', '_check', '_regular_under', 'selected_files', '_take_all', '_ranges_add', '_line_ranges', '_decode_range', '_decoded_lines', 'read_columns')

def save_identity():
    """This module's value code for a saved search (frankie_box_bedrock.code_identity of the declared definitions, so a
    comment or an unrelated edit never refuses a save; frankie_box_experiment_search's continuation identity V2)."""
    try:
        import frankie_box_bedrock as B
    except ImportError:
        from deploy.aws.box import frankie_box_bedrock as B
    return B.code_identity(__file__, SAVE_VALUE_CODE)
