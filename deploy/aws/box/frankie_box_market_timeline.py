"""One sparse, causal market picture over the retained source's original order.

This reader combines existing calculation outputs; it performs no scientific replay.
INPUT cursor/ordinal orders arrivals. Exact event/receive clocks remain distinct; no
sorting by a retrograde event clock, timestamp rounding, dense nanosecond rows or
future-dependent backfill is permitted. Existing F_LAST science is a view of this
source, not replaced by a different lag axis. Only raw/ROOT market evidence enters
this module: host answers, private decisions, school and other agents' claims do not.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:     # the box directory: every frankie_box_* module
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import frankie_box_all99_coverage as ALL99  # noqa: E402

SCHEMA = 'FRANKIE_SHARED_MARKET_TIMELINE_V1'


LAYERS = ('root.frames', 'root.prices', 'root.structures', 'native.member', 'native.lifecycle', 'external')

# Greg, 2026-10-07 (supersedes earlier completeness wording): no day or time is rejected
# from the reconstruction because data is missing. The instant stays, thinner, with explicit
# dispositions. Integrity corruption (altered pinned bytes, contradictory identities) is a
# separate visible failure and is never relabelled as missing coverage.
MISSING_COVERAGE_RULE = 'every_authentic_boundary_kept_with_thinner_explicit_picture'

# The 99-entry registry through this reader (Greg, 2026-10-07: the 99 layers combined for Frankie FIRST). The entry
# list, the settled per-entry carriers (MARKET_CARRIERS: entry -> (carrier, thinner carrier or None)), the picture
# element of each carrier and the native-only entries' own ledger fields/sections all live in the ONE registry module
# (frankie_box_all99_coverage); this reader yields exactly those carriers. Carriers: the six LAYERS plus 'input' (the
# original INPUT envelope, its outcomes and matched APPLIED), 'clock' (picture.at), 'availability' (known_at_ns /
# availability_basis on every update), 'opening' (the opening adapter state) and 'completed' (post-stream aggregates,
# metadata only). 'external' carries the day file's publications, which are outside the 99.
CARRIER_ELEMENTS = ALL99.CARRIER_ELEMENTS
CARRIERS = ALL99.MARKET_CARRIERS
NOT_CORE = ALL99.NOT_MARKET_CARRIED
OPENING_SEEDED = ('seeded', 'warmed_from_partition')
COMPLETED_ONLY_REASON = ('post-stream aggregate without exact contributing-cursor availability under reversing clocks: '
                         'completed-only until correct provenance exists (blocked on provenance, not on the reader); its '
                         'values are never yielded into a live picture and never backfilled')


def binding():
    return dict(schema=SCHEMA, implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                order='original_INPUT_cursor_and_journal_ordinal',
                clocks='exact_original_event_and_receive_nanoseconds', required_native=False,
                representation='sparse_changes_and_last_observed_state',
                completed_knowledge='post_stream_only_no_earlier_backfill',
                missing_coverage=MISSING_COVERAGE_RULE)


def frame_index(numeric, receive_times):
    """The shared exact F_LAST view. This is the pre-existing membership contract."""
    cursors, instruments = numeric.get('input_cursor'), numeric.get('native_frame.instrument_id')
    slots = sorted((int(match.group(1)), name) for name in numeric
                   if (match := re.fullmatch(r'input_record_indices\[(\d+)\]', name)))
    if cursors is None or instruments is None or not slots:
        return None, None
    if any(len(values) != len(receive_times) for values in (cursors, instruments, *(numeric[name] for _, name in slots))):
        raise ValueError('ROOT group membership columns have different lengths')
    if [slot for slot, _ in slots] != list(range(len(slots))):
        raise ValueError('ROOT group INPUT positions have gaps')
    frames, owners, previous = [], {}, -1
    for position, stamp in enumerate(receive_times):
        cursor, instrument = cursors[position], instruments[position]
        if type(cursor) is not int or type(instrument) is not int or cursor <= previous:
            raise ValueError('ROOT frame INPUT cursor/instrument identity is not exact and ordered')
        members, ended = [], False
        for slot, name in slots:
            index = numeric[name][position]
            if index is None:
                ended = True
                continue
            if (ended or type(index) is not int or index < 0 or index > cursor
                    or index in owners or (members and index <= members[-1])):
                raise ValueError('ROOT group INPUT membership is duplicated or out of order')
            record_instruments = numeric.get('input_records[%d].instrument_id' % slot)
            if record_instruments is None or record_instruments[position] != instrument:
                raise ValueError('ROOT group INPUT instrument differs from its frame')
            members.append(index)
            owners[index] = position
        if not members or members[-1] != cursor:
            raise ValueError('ROOT group does not end at its declared INPUT cursor')
        frames.append(dict(cursor=cursor, instrument=instrument, stamp=int(stamp), members=set(members)))
        previous = cursor
    return frames, owners


def _local(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('shared evidence must be an absolute owner-local regular path')
    return path


def _json(pin):
    raw = _local(pin['path']).read_bytes()
    if len(raw) != pin['bytes'] or hashlib.sha256(raw).hexdigest() != pin['sha256']:
        raise ValueError('shared market metadata differs from its source pin: ' + pin['path'])
    return json.loads(raw)


def _rows(pin, *, packed, timing=None, verify=True):
    """Check the exact consumed bytes; caller must exhaust before claiming completion. `timing` (optional dict)
    accumulates the seconds spent reading, hashing and decoding rows: an inspection measurement, never a value.
    verify=False (one pass, 2026-10-09): the stream's pin is held by the ROOT's FRANKIE_FILE_CLAIM_V2 row (stat,
    filesystem and last 64 KiB unchanged), so the bytes are not hashed again and not compared at exhaustion."""
    from research.kalshi.frankie_boss.c15_journal import unpack
    from time import perf_counter
    hashed, size = hashlib.sha256(), 0
    spent = 0.0
    with _local(pin['path']).open('rb') as stream:
        mark = perf_counter()
        for ordinal, raw in enumerate(stream):
            if verify:
                hashed.update(raw)
            size += len(raw)
            row = json.loads(raw)
            row = unpack(row) if packed else row
            if timing is not None:
                now = perf_counter()
                spent += now - mark
                timing['decode_seconds'] = round(spent, 3)
            yield ordinal, row
            mark = perf_counter()
    if verify and (size != pin['bytes'] or hashed.hexdigest() != pin['sha256']):
        raise ValueError('shared market rows differ from their source pin: ' + pin['path'])


# ---- layer-row decode on the lane (Greg, 2026-10-07: CPUs pinned to the jobs and workers) --------------------------
# A layer spool's rows are decoded (json.loads, plus the journal codec's unpack for ROOT spools) one by one in the
# consumer's process; the frame spool alone runs to hundreds of GB on a full day. The decode is per row and
# order-free: workers pinned one per lane CPU decode ordered line-aligned byte ranges and hand the rows back; this
# process yields them in file order with the same ordinals. The bytes are hashed in file order on a thread here and
# checked against the pin at exhaustion, as _rows does; a range that fails to decode hands back the rows before the
# failing line and the error, so the same rows are yielded before the same error. Same rows, same order, same
# ordinals, same errors. Below PARALLEL_DECODE_MIN_BYTES or with one worker it is _rows itself.
PARALLEL_DECODE_MIN_BYTES = 64 << 20
DECODE_RANGE_BYTES = 16 << 20
DECODE_WINDOW_PER_WORKER = 2


def lane_cpus():
    """The held lane's CPUs, never the host count: FRANKIE_LANE_CPUS or FRANKIE_BOOKED_CPUS (cores' cpu_list)
    intersected with this process's affinity; the affinity alone when neither names a CPU of it."""
    import os
    affinity = set(os.sched_getaffinity(0))
    for name in ('FRANKIE_LANE_CPUS', 'FRANKIE_BOOKED_CPUS'):
        listed = set()
        try:
            for part in (os.environ.get(name) or '').split(','):
                if part.strip():
                    low, _, high = part.strip().partition('-')
                    listed.update(range(int(low), int(high or low) + 1))
        except ValueError:
            continue
        if listed & affinity:
            return sorted(listed & affinity)
    return sorted(affinity)


def _decode_pin(handout):
    import os
    os.sched_setaffinity(0, {handout.get()})


def _decode_range(args):
    """Rows of one byte range, decoded exactly as _rows decodes them; (rows, error) where error is the exception the
    first undecodable line raised (rows hold every row before it)."""
    path, start, end, packed = args
    from research.kalshi.frankie_boss.c15_journal import unpack
    rows = []
    try:
        with open(path, 'rb') as stream:
            stream.seek(start)
            position = start
            for raw in stream:
                if position >= end:
                    break
                position += len(raw)
                row = json.loads(raw)
                rows.append(unpack(row) if packed else row)
    except Exception as error:  # noqa: BLE001 - handed back and raised in order by the consumer
        return rows, error
    return rows, None


def _decode_ranges(path, size):
    cuts = [0]
    with open(path, 'rb') as stream:
        while cuts[-1] + DECODE_RANGE_BYTES < size:
            stream.seek(cuts[-1] + DECODE_RANGE_BYTES - 1)
            stream.readline()
            cut = stream.tell()
            if cut >= size:
                break
            cuts.append(cut)
    cuts.append(size)
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if b > a]


def _frontier_hasher():
    try:
        from frankie_box_experiment_search import FrontierHasher
    except ImportError:
        from deploy.aws.box.frankie_box_experiment_search import FrontierHasher
    return FrontierHasher


def _rows_parallel(pin, *, packed, timing, workers, verify=True):
    """_rows with the decode on pinned lane workers (see above). One pass (2026-10-09): the bytes are hashed in file
    order by the search's FrontierHasher, held at most one decode window past the consumed frontier, so the hash reads
    the pages the decode workers just read (one disk pass, not a second unbounded read of the whole stream racing
    ahead). verify=False (the ROOT's claim holds for this pin): no hash at all and no check at exhaustion."""
    import collections
    import multiprocessing
    from time import perf_counter
    path = str(_local(pin['path']))
    lane = lane_cpus()
    cpus = (lane[1:] if len(lane) > workers else lane)[:workers] or lane
    context = multiprocessing.get_context('spawn')      # spawn: this process already runs reader workers and threads
    handout = context.Queue()
    for cpu in cpus:
        handout.put(cpu)
    cut = _decode_ranges(path, _local(pin['path']).stat().st_size)
    ranges = iter(cut)
    pool = context.Pool(len(cpus), initializer=_decode_pin, initargs=(handout,))
    window = len(cpus) * DECODE_WINDOW_PER_WORKER
    hasher = (_frontier_hasher()(path, window * max((b - a for a, b in cut), default=1), name='layer-sha256')
              if verify else None)
    if hasher is not None:
        hasher.start()
    pending, ordinal, spent, finished = collections.deque(), 0, 0.0, False
    timing.update(mode='pinned_lane_workers', workers=len(cpus), cpus=cpus, range_bytes=DECODE_RANGE_BYTES)
    try:
        def fill():
            while len(pending) < window:
                item = next(ranges, None)
                if item is None:
                    return
                pending.append((item[1], pool.apply_async(_decode_range, ((path, item[0], item[1], packed),))))
        fill()
        while pending:
            mark = perf_counter()
            end, job = pending.popleft()
            rows, error = job.get()
            if hasher is not None:
                hasher.advance(end)
            fill()
            spent += perf_counter() - mark
            timing['decode_seconds'] = round(spent, 3)
            for row in rows:
                yield ordinal, row
                ordinal += 1
            if error is not None:
                raise error
        if hasher is not None:
            hashed_bytes, digest = hasher.finish()
            timing['hashing'] = hasher.report()
            if hashed_bytes != pin['bytes'] or digest != pin['sha256']:
                raise ValueError('shared market rows differ from their source pin: ' + pin['path'])
        finished = True
    finally:
        if hasher is not None and not finished:
            hasher.stop()
        pool.terminate()
        pool.join()


def _stream_claim(pin, claims, work):
    """(verify, verification) for one stream's pin: when the ROOT's work/file-claims.jsonl row for the path names the
    pin's bytes and sha256 and still holds (inode, size, mtime_ns, filesystem, last 64 KiB: one 64 KiB read), the
    stream is decoded without a hash (basis 'by claim'); else it is hashed in lockstep with the decode. Never raises."""
    if claims is None:
        return True, dict(basis='hashed with the decode', reason='no claims were consulted')
    try:
        try:
            from frankie_box_experiment_native import _claim_basis, _claims_mode
        except ImportError:
            from deploy.aws.box.frankie_box_experiment_native import _claim_basis, _claims_mode
        if _claims_mode() == 'full':
            return True, dict(basis='hashed with the decode', reason='FRANKIE_ROOT_LEGACY_REUSE_CHECK=full')
        held, why = _claim_basis(pin['path'], pin, claims, work)
    except Exception as error:  # noqa: BLE001 - a claim is a hint: without one the stream is hashed with the decode
        held, why = None, 'claim not taken (%s: %s)' % (type(error).__name__, error)
    if held is None:
        return True, dict(basis='hashed with the decode', reason=why)
    return False, dict(basis='by claim', claim=held, claim_file=str(Path(work) / 'file-claims.jsonl'))


class _Changes:
    """One existing ordered producer stream; no completion-order merge or row cap."""
    def __init__(self, name, pin, *, kind, state, workers=1, claims=None, work=None, verified=None):
        self.name, self.pin, self.kind, self.state = name, pin, kind, state
        self.timing = dict(decode_seconds=0.0, mode='serial')
        packed = kind in ('frame', 'price', 'structure')
        # one pass (Greg, 2026-10-09): a pin held by the ROOT's claim (or witnessed by selected_files in this process,
        # `verified`) is not hashed again; else it is hashed with the decode
        if verified is not None:
            verify, self.verification = False, dict(basis='witnessed in this process', by=verified)
        else:
            verify, self.verification = _stream_claim(pin, claims, work)
        self.rows = (_rows_parallel(pin, packed=packed, timing=self.timing, workers=workers, verify=verify)
                     if workers > 1 and pin['bytes'] >= PARALLEL_DECODE_MIN_BYTES else
                     _rows(pin, packed=packed, timing=self.timing, verify=verify))
        self.pending = None
        self.previous = -1
        self.finished = False
        self.terminal = None
        self.counts = dict(read=0, presented=0, post_stream=0, unsupported=0)
        self.dispositions = {}

    def _listed(self, reason, ordinal):
        ranges = self.dispositions.setdefault(reason, [])
        if ranges and ranges[-1][1] + 1 == ordinal:
            ranges[-1][1] = ordinal
        else:
            ranges.append([ordinal, ordinal])

    def _next(self):
        while not self.finished and self.pending is None and self.terminal is None:
            try:
                ordinal, row = next(self.rows)
            except StopIteration:
                self.finished = True
                return
            self.counts['read'] += 1
            if self.kind == 'frame':
                cursor, instrument, stamp = row.get('input_cursor'), (row.get('native_frame') or {}).get('instrument_id'), row.get('ts_recv_ns')
            elif self.kind in ('price', 'structure'):
                provenance = row.get('provenance') or {}
                wanted = 'FRANKIE_ROOT_PRICE_ROW_PROVENANCE_V2' if self.kind == 'price' else 'FRANKIE_ROOT_ROW_PROVENANCE_V1'
                if provenance.get('schema') != wanted:
                    raise ValueError('shared legacy row lacks its original exact provenance')
                cursor = provenance.get('group_close_input_index' if self.kind == 'price' else 'input_cursor')
                instrument = provenance.get('instrument_id')
                # Price timestamps describe the original trade. Its explicit
                # emission cursor supplies availability; never backdate the row.
                stamp = None if self.kind == 'price' else row.get('ts_recv_ns')
            else:
                emission = row.get('frankie_emission') or {}
                if emission.get('schema') != 'FRANKIE_NATIVE_EMISSION_V1':
                    raise ValueError('native update lacks the selected exact emission contract')
                if emission.get('phase') == 'FINALIZE':
                    self.terminal = ordinal, row
                    return
                if emission.get('phase') != 'GROUP_CLOSE':
                    raise ValueError('native update has an unknown emission phase')
                cursor, instrument, stamp = (emission.get(k) for k in ('input_cursor', 'instrument_id', 'ts_recv_ns'))
                group = emission.get('group_index')
                if type(group) is not int or group < 0:
                    raise ValueError('native live update has no exact group identity')
                if self.name == 'native.member':
                    if (group != ordinal or row.get('group_index') != group
                            or row.get('instrument_id') != instrument or row.get('ts_recv_ns') != stamp
                            or (row.get('clocks') or {}).get('first_lawful_availability_ns') != stamp):
                        raise ValueError('native member row disagrees with its emission identity/clocks')
                elif row.get('emitted_at_recv_ns') != stamp:
                    raise ValueError('native lifecycle row disagrees with its emission clock')
            identities = (cursor, instrument) if self.kind == 'price' else (cursor, instrument, stamp)
            if any(type(value) is not int for value in identities) or cursor < self.previous:
                raise ValueError('shared source has missing/noninteger/backwards causal identity')
            self.previous = cursor
            self.pending = dict(source=self.name, source_ordinal=ordinal, input_cursor=cursor,
                                instrument_id=instrument, known_at_ns=stamp, value=row)

    def through(self, cursor, instrument, stamp):
        self._next()
        while self.pending is not None and self.pending['input_cursor'] <= cursor:
            update = self.pending
            if (update['input_cursor'] != cursor or update['instrument_id'] != instrument
                    or (update['known_at_ns'] is not None and update['known_at_ns'] != stamp)):
                raise ValueError('derived update does not match its exact original INPUT boundary')
            if update['known_at_ns'] is None:
                update = dict(update, known_at_ns=stamp, availability_basis='exact_declared_emitting_INPUT_cursor')
            self.pending = None
            self.counts['presented'] += 1
            yield update
            self._next()

    def unplaced_at(self, cursor):
        self._next()
        while self.pending is not None and self.pending['input_cursor'] <= cursor:
            update = self.pending
            if update['input_cursor'] != cursor:
                raise ValueError('derived row was missed before the current original INPUT')
            self.pending = None
            self.counts['unsupported'] += 1
            self._listed('unplaceable_original_input_clock_or_identity', update['source_ordinal'])
            yield dict(update, placement='unplaceable_original_input_clock_or_identity')
            self._next()

    def finish(self):
        self._next()
        if self.pending is not None:
            raise ValueError('derived update has no INPUT in the complete shared source')
        if self.terminal is not None:
            from itertools import chain
            for ordinal, row in chain((self.terminal,), self.rows):
                emission = row.get('frankie_emission') or {}
                if (emission.get('schema') != 'FRANKIE_NATIVE_EMISSION_V1'
                        or emission.get('phase') != 'FINALIZE'
                        or emission.get('group_index') is not None or emission.get('instrument_id') is not None
                        or type(emission.get('ts_recv_ns')) is not int
                        or row.get('emitted_at_recv_ns') != emission.get('ts_recv_ns')):
                    raise ValueError('post-stream row has inconsistent finalization identity/clock')
                if ordinal != self.terminal[0]:
                    self.counts['read'] += 1
                self.counts['post_stream'] += 1
                self._listed('post_stream_not_a_live_input', ordinal)
            self.finished = True

    def close(self):
        self.rows.close()


class _Publications:
    """Every external row at the later of its recorded event time and its publication clock (Greg, 2026-10-07; at
    publication when no event time is recorded), in original tie order, with the 99 entries it declares it feeds."""
    IDENTITIES = {'model', 'station', 'respondent', 'raw_symbol', 'symbol', 'instrument_id',
                  'publisher_id', 'horizon_days', 'rank', 'target_day', 'contract'}

    def __init__(self, pin, day):
        from research.kalshi.frankie_boss.operations.frankie_day_external import check_day_file
        body = _json(pin)
        check_day_file(body)
        if str(body['trading_day']) != str(day):
            raise ValueError('shared external publications belong to another day')
        self.pin, self.rows, self.position, self.states = pin, [], 0, {}
        self.report = dict(source=pin, presented=0, not_yet_public={},
                           missing=body.get('missing'), after_halt={}, points={}, entry_findings=[])
        for table_ordinal, (name, table) in enumerate(body['points'].items()):
            columns = table['columns']
            stamp = columns.index(table['stamp_column'])
            identities = [i for i, key in enumerate(columns) if key in self.IDENTITIES]
            self.report['after_halt'][name] = table.get('after_halt')
            # the registry entries this point declares it feeds (frankie_box_all99_coverage.external_point_entries:
            # table metadata or a per-row column; a name outside the 99 is a finding, never entered)
            point = ALL99.external_point_mapping(table)
            declared, findings = point['entries'], point['findings']
            self.report['points'][name] = dict(stamp_column=table['stamp_column'], declared_entries=declared,
                                               mapping=point['mapping'], mapping_reason=point['mapping_reason'],
                                               event_time_basis=point['event_time_basis'], note=point['note'],
                                               rows=len(table['rows']), presented=0,
                                               placement='at the later of its recorded event time and its publication '
                                                         'clock (stamp_column), once the receive frontier reaches it; '
                                                         'never earlier than publication, never backfilled')
            self.report['entry_findings'].extend(dict(f, point=name) for f in findings)
            for ordinal, row in enumerate(table['rows']):
                known = row[stamp]
                if type(known) is not int:
                    raise ValueError('external publication clock is not exact integer nanoseconds')
                entity = [(columns[i], row[i]) for i in identities]
                value = dict(columns=columns, row=row, entity=entity,
                             table_metadata={k: v for k, v in table.items() if k not in ('rows', 'columns')})
                mapped = ALL99.external_point_mapping(table, row)
                self.report['entry_findings'].extend(dict(f, point=name, row=ordinal) for f in mapped['findings']
                                                     if f not in findings)
                # Greg, 2026-10-07: a point sits at its recorded event time (e.g. default_1400 for a value without an
                # intrinsic time), never earlier than its publication; without a recorded event time, at publication
                event = mapped['event_time_ns']
                placed = max(event, known) if event is not None else known
                placement = dict(publication_ns=known, event_time_ns=event, event_time_basis=mapped['event_time_basis'],
                                 as_of=mapped['as_of'], note=mapped['note'], mapping=mapped['mapping'],
                                 mapping_reason=mapped['mapping_reason'],
                                 placed_by=('publication (no event time recorded)' if event is None else
                                            'event_time' if event >= known else 'publication_after_event_time'))
                self.rows.append((placed, table_ordinal, ordinal, name, value, mapped['entries'], placement))
        self.rows.sort(key=lambda item: item[:3])

    def through(self, frontier, cursor):
        while self.position < len(self.rows) and self.rows[self.position][0] <= frontier:
            known, _, ordinal, name, value, entries, placement = self.rows[self.position]
            self.position += 1
            update = dict(source='external.' + name, source_ordinal=ordinal, known_at_ns=known,
                          presented_at_input_cursor=cursor, value=value, entries=list(entries), placement=placement,
                          availability_basis=('original_publication_clock_at_observed_receive_frontier'
                                              if placement['event_time_ns'] is None else
                                              'recorded_event_time_not_before_publication_at_observed_receive_frontier'))
            self.report['points'][name]['presented'] += 1
            key = name, json.dumps(value['entity'], sort_keys=True, separators=(',', ':'))
            self.states[key] = update
            self.report['presented'] += 1
            yield update

    def finish(self):
        for _, _, ordinal, name, _, _, _ in self.rows[self.position:]:
            self.report['not_yet_public'].setdefault(name, []).append(ordinal)
        self.report['rows'] = len(self.rows)


class SharedMarketTimeline:
    """Read a completed shared-policy ROOT as one shared market input.

    `iter_applied()` yields the original C15 payload (or None, with an explicit
    arithmetic disposition) and a point-in-time picture. The payload is unchanged, so
    existing teacher formulas/masks receive identical raw evidence. Consumers must
    explicitly choose/use the picture values; this reader's `presented` counts are not
    claims that every target used every field. Last-observed state always retains its
    original cursor: a prior group snapshot is never advertised as a newly
    reconstructed intermediate book. Absent layers (native when the native pass did not complete or an older saved legacy
    plan ran it off, a spool
    the ROOT did not publish, no day file) thin the picture and are listed in
    `report['coverage']`; `report['complete']` means only that the whole available
    source was exhausted with its pins verified.

    The 99 (2026-10-07): `report['layer_entries']` names per carrier (each layer, the
    INPUT envelope, the clocks, availability stamps, the opening state, the completed
    aggregates) the registry entries it yields; every picture carries the same map as
    `coverage.carried_entries`; `report['all99_coverage']` is the day's shared field
    FRANKIE_ALL99_COVERAGE_V1 (made at open, replaced at exhaustion with the rows each
    carrier yielded). `opening_state` (on the report and on every picture) is the
    predecessor bootstrap as an identity element with its initial last-observed
    disposition. legacy_native_signed_flow / legacy_per_second_roll20 stay completed_only
    (blocked on contributing-cursor provenance, not on this reader).
    """
    def __init__(self, calculations, *, day, workers=15, input_witness=None):
        """`input_witness`: an optional {path, bytes, sha256[, dev, ino]} the caller measured on the sealed journal in
        this same process (the teacher hashes it against its ingestion receipt before opening this reader). When it
        equals the ROOT's container pin AND names the pinned file (_caller_witness) the full re-read is skipped and `report['input_verification']` says whose
        measurement stood; anything else (absent, different, malformed) falls back to this reader's own full
        hash. The pin, the identity and the integrity rule are unchanged: a mismatch still raises."""
        from frankie_box_durable import witness
        from frankie_box_experiment_native import selected_files
        root = _local(Path(calculations).absolute()).resolve()
        source_pin = dict(path=str(root / 'source-binding.json'), **witness(root / 'source-binding.json'))
        self.source = _json(source_pin)
        if self.source.get('shared_market_policy') != binding():
            raise ValueError('ROOT has no matching shared-market policy; retain old result and use an explicit compatible successor')
        if str(self.source['source']['trading_day']) != str(day):
            raise ValueError('shared market ROOT belongs to another day')
        calculation_pin = dict(path=str(root / 'calculations-receipt.json'), **witness(root / 'calculations-receipt.json'))
        calculation = _json(calculation_pin)
        if calculation['source_binding'] != source_pin:
            raise ValueError('shared ROOT completion differs from its source binding')
        derive = _json(calculation['derivation'])
        if (derive.get('source_binding') != self.source or type(derive.get('input_records')) is not int
                or not 0 <= derive['input_records'] <= self.source['record_count']):
            raise ValueError('shared ROOT did not account for every original INPUT')
        if calculation.get('shared_market_policy') != self.source['shared_market_policy']:
            raise ValueError('completed shared market policy differs from its source')
        # Layers. A layer the completed ROOT did not produce is listed absent and the
        # picture is thinner there; a pin that names another path, or pinned bytes that
        # differ (checked on read), is a contradiction and stays an error.
        self.layers, self.streams = {}, []
        pins = calculation.get('shared_market_sources') or {}
        # one pass (Greg, 2026-10-09): the ROOT sealed and claimed every spool (work/file-claims.jsonl,
        # FRANKIE_FILE_CLAIM_V2); a stream whose pin the claim still holds is decoded without a second hash
        try:
            from frankie_box_experiment_native import _session_claims
        except ImportError:
            from deploy.aws.box.frankie_box_experiment_native import _session_claims
        try:
            claims = _session_claims()._load_file_claims(root / 'work')
        except Exception:  # noqa: BLE001 - no claims: every stream is hashed with its decode
            claims = {}
        for role, kind, state in (('frames', 'frame', True), ('prices', 'price', False), ('structures', 'structure', False)):
            name, pin = 'root.' + role, pins.get(role)
            if pin is None:
                self.layers[name] = dict(status='absent', reason='the completed ROOT recorded no ' + role + ' spool pin')
                continue
            if not isinstance(pin, dict):
                raise ValueError('completed shared source has a malformed ' + role + ' spool pin')
            if pin.get('status') == 'absent':
                self.layers[name] = dict(status='absent', reason=pin.get('reason') or 'the ROOT published no ' + role + ' spool',
                                         path=pin.get('path'))
                continue
            if Path(pin['path']) != root / 'work/derived/.rows' / (role + '.jsonl'):
                raise ValueError('completed shared source pins another path as its ' + role + ' spool')
            self.layers[name] = dict(status='present', source=pin)
            self.streams.append(_Changes(name, pin, kind=kind, state=state, workers=workers, claims=claims,
                                         work=root / 'work'))
        # Native: absent only when the native pass did not complete or an older saved legacy plan ran it
        # off (selected_files returns nothing); every NEW run has it ON;
        # a bedrock-on ROOT whose artifacts are incomplete or altered raises inside selected_files.
        selected = {item['native_role']: item for item in selected_files(root, str(day))}
        for role, name, state in (('exact_member_rows.jsonl', 'native.member', True),
                                  ('exact_lifecycle_rows.jsonl', 'native.lifecycle', False)):
            item = selected.get(role)
            if item is None:
                self.layers[name] = dict(status='absent', reason=('no completed native calculation in this ROOT (the native pass did not complete, or an older saved '
                                                                  'legacy plan ran it off)'
                                                                  if not selected else 'native ledger not selected'))
                continue
            pin = dict(path=item['source'], **item['expected'])
            self.layers[name] = dict(status='present', source=pin)
            # selected_files witnessed this ledger in this process (its claim, or one whole read that left a claim
            # behind): the decode does not hash it again (one pass, 2026-10-09)
            self.streams.append(_Changes(name, pin, kind='native', state=state, workers=workers,
                                         verified='selected_files: ' + (item.get('selection_basis') or 'witnessed')))
        external = self.source.get('external') or {}
        self.publications = _Publications(external, day) if external.get('status') == 'attached' else None
        self.layers['external'] = (dict(status='present', source=external) if self.publications is not None else
                                   dict(status='absent', reason=external.get('reason') or 'no day file attached to this ROOT',
                                        recorded=external))
        self.absent_layers = sorted(name for name, layer in self.layers.items() if layer['status'] == 'absent')
        self.completed_sources = [dict(role=role, **derive['layers'][role],
            disposition='post_stream_only: aggregate has no exact contributor cursor provenance')
            for role in ('legacy_native_signed_flow', 'legacy_per_second_roll20') if role in derive['layers']]
        self.day, self.workers = str(day), workers
        # the ROOT's own record of every layer (status / reason / count), as derive.json carries it; read, never re-derived
        self.derive_layers = {k: {f: v.get(f) for f in ('status', 'reason', 'count', 'producer', 'bedrock')}
                              for k, v in (derive.get('layers') or {}).items() if isinstance(v, dict)}
        # The predecessor bootstrap (canonical_predecessor_bootstrap_objects) as an identity element: the opening adapter
        # state the ROOT legacy pass replayed this day onto (derive.json, else the source binding), with the initial
        # last-observed disposition. Source-bound and pinned through derive.json / source-binding.json; nothing is
        # re-derived, and an absent opening book is a thinner start, never a rejected day.
        opening = (derive.get('opening_book') if isinstance(derive.get('opening_book'), dict) else
                   self.source.get('opening_book') if isinstance(self.source.get('opening_book'), dict) else None)
        status = (opening or {}).get('status')
        if status in OPENING_SEEDED:
            initial = dict(disposition='opening_book_in_root_adapter',
                           reason='the orders resting at the open are in the ROOT adapter state; they reach the picture through '
                                  'root.frames at each instrument\'s first group close; until a layer row arrives, '
                                  'last_observed_state holds no row (not an empty book, not a zero)')
        elif status in ('absent', 'empty'):
            initial = dict(disposition='empty_book_at_open',
                           reason=(opening or {}).get('listed') or (opening or {}).get('reason') or
                                  'the legacy pass started from an empty book; orders resting at the prior halt appear only '
                                  'when they trade, are modified or cancelled, or a snapshot resets the book')
        else:
            initial = dict(disposition='opening_not_recorded',
                           reason='neither derive.json nor the source binding records the opening book of this ROOT')
        self.opening_state = dict(entry='canonical_predecessor_bootstrap_objects', element='opening_state',
                                  status=status or 'not_recorded', descriptor=opening,
                                  source=('derive.json opening_book' if isinstance(derive.get('opening_book'), dict) else
                                          'source-binding.json opening_book' if opening is not None else None),
                                  tail_members=self.source.get('tail_members'),
                                  initial_last_observed_state=initial,
                                  rule='identity element; the opening book is never re-derived here, never fabricated, and '
                                       'never promoted to a fresh observation')
        # The native-only entries' own carriers: the producers' per-layer crosswalk from the ROOT projection plan when
        # it was selected (bound to the same ledgers by selected_files), else the retained crosswalk's carrier text.
        from frankie_box_experiment_native import PROJECTION_PLAN, entry_carriers, plan_document
        plan_item = selected.get(PROJECTION_PLAN)
        plan_carriers = None
        if plan_item:
            # one pass (T3): the plan selected_files just read and parsed in this process (plan_document), not re-read
            plan_pin, plan_doc = plan_document(_local(plan_item['source']))
            if {k: plan_pin[k] for k in ('bytes', 'sha256')} != plan_item['expected']:
                raise ValueError('shared market metadata differs from its source pin: ' + plan_item['source'])
            plan_carriers = entry_carriers(plan_doc)
        self.native_carriers = {name: (dict(plan_carriers[name]) if plan_carriers and name in plan_carriers else
                                       dict(ALL99.NATIVE_SERIES[name], source='retained crosswalk carrier text '
                                            '(frankie_box_all99_coverage.NATIVE_SERIES)'))
                                for name in ALL99.NATIVE_ENTRIES}
        self.extracted_count = derive['input_records']
        self.input_pin = self.source['container']
        expected = {k: self.input_pin[k] for k in ('bytes', 'sha256')}
        verification = self._caller_witness(input_witness, expected)
        if verification is None:
            # one pass (2026-10-09): the ingest's own FRANKIE_FILE_CLAIM_V2 row for the sealed journal (beside its
            # receipt), naming the pin's bytes and sha256 and still holding, stands in for the whole read
            try:
                from frankie_box_experiment_journal import _holding_claim
            except ImportError:
                from deploy.aws.box.frankie_box_experiment_journal import _holding_claim
            held = _holding_claim(self.input_pin['path'], expected, [Path(self.input_pin['path']).parent])
            if held is not None:
                verification = dict(basis='claim', re_read=False, path=self.input_pin['path'], claim=held,
                                    caller_witness=('absent' if input_witness is None else 'not bound to the pinned file '
                                                    'or differs from the pin'),
                                    note='the ingest\'s file claim (stat, filesystem, last 64 KiB) holds for the pin')
        if verification is None:
            if witness(self.input_pin['path']) != expected:
                raise ValueError('shared input journal differs from its exact sealed source bytes')
            verification = dict(basis='full_read_by_this_reader', re_read=True,
                                caller_witness=('absent' if input_witness is None else 'not bound to the pinned file (path / '
                                                'device / inode / size) or differs from the pin; the reader measured the bytes itself'))
        self.input_verification = verification
        self.identity = dict(schema=SCHEMA, day=self.day, source_binding=source_pin,
                             calculations=calculation_pin, journal=self.input_pin,
                             sources={stream.name: stream.pin for stream in self.streams}, external=external,
                             completed_sources=self.completed_sources, absent_layers=self.absent_layers)
        self.report = dict(identity=self.identity, complete=False, presented_inputs=0,
                           input_verification=verification,
                           interpretation='actual shared-reader input delivery; target/learner arithmetic coverage is separate',
                           completeness=dict(
                               complete='source exhausted: every journal envelope, every pinned layer row and every external '
                                        'row read, with bytes, hashes and counts verified against their pins',
                               not_implied='all-layer coverage, all-input application or any consumer arithmetic; '
                                           'those are in coverage, journal.dispositions and the consumer\'s own receipt',
                               rule=MISSING_COVERAGE_RULE),
                           coverage=dict(layers=self.layers, absent_layers=self.absent_layers,
                                         present_layers=sorted(name for name in self.layers if name not in self.absent_layers),
                                         inputs=None, basis='layers known at open; input dispositions counted at exhaustion'),
                           completed_native=[dict(role=role, path=item['source'], **item['expected'])
                                             for role, item in selected.items()
                                             if role not in ('exact_member_rows.jsonl', 'exact_lifecycle_rows.jsonl')])
        self.report['opening_state'] = self.opening_state
        self.report['layer_entries'] = self.layer_entries()
        # per carrier present at open: the registry entries its picture element carries (a reference on every picture)
        self.carried_entries = {carrier: list(item['entries'] + item['thin_for'])
                                for carrier, item in self.report['layer_entries'].items() if item['status'] == 'present'}
        self.thin_for = {carrier: list(item['thin_for']) for carrier, item in self.report['layer_entries'].items()
                         if item['status'] == 'present' and item['thin_for']}
        # per registry entry: the updates that carried it over this read (counted as yielded; never a value)
        self.entry_counts = {}
        self.external_entry_counts = {}     # entries fed by day-file points, counted when presented (at/after publication)
        self.report['native_carriers'] = dict(
            entries=self.native_carriers,
            rule='the 18 native-only entries are yielded by native.member / native.lifecycle updates at their GROUP_CLOSE '
                 'emission (exact INPUT cursor, instrument, receive clock); FINALIZE rows are post-stream only; every update '
                 'names its entries (update.entries)')
        self.report['all99_coverage'] = self.all99_coverage(exhausted=False)
        self.started = False

    def _caller_witness(self, supplied, expected):
        """The caller's measurement stands in for this reader's full hash only when it is bound to THE pinned file
        (review N1, 2026-10-07): {path, bytes, sha256} with the path resolving to the pin's path or naming the same
        file (os.path.samefile), the file's current size equal to the pin, and, when the caller recorded them, the
        same device and inode. Anything else returns None (the reader hashes the file itself)."""
        import os
        if not isinstance(supplied, dict) or {k: supplied.get(k) for k in ('bytes', 'sha256')} != expected:
            return None
        path = supplied.get('path')
        if not isinstance(path, str) or not path:
            return None
        pinned = Path(self.input_pin['path'])
        try:
            same = Path(path).resolve() == pinned.resolve() or os.path.samefile(path, pinned)
            stat = os.stat(pinned)
        except OSError:
            return None
        if not same or stat.st_size != expected['bytes']:
            return None
        if supplied.get('dev') is not None and (supplied.get('dev'), supplied.get('ino')) != (stat.st_dev, stat.st_ino):
            return None
        # The caller measured these exact bytes of this exact file in this process; a second full read of the sealed
        # journal (tens of GB on a big day) would re-measure the same pin. The chained head hash is still verified by
        # the compact reader as the envelopes are read.
        if supplied.get('basis') == 'claim':
            # the caller took the ingest's file claim (stat, filesystem, last 64 KiB) rather than hashing the journal
            return dict(basis='claim', re_read=False, path=str(pinned),
                        bound_by=('path, size, device and inode' if supplied.get('dev') is not None else 'path and size'),
                        claim=supplied.get('claim'), note='the caller took the ingest\'s file claim for the sealed journal')
        return dict(basis='caller_measured_witness_equal_to_pin', re_read=False, path=str(pinned),
                    bound_by=('path, size, device and inode' if supplied.get('dev') is not None else 'path and size'),
                    note='the caller hashed the sealed journal in this process')

    def _native_note(self, name):
        """The entry's own native carriers and the ROOT's own record of the projected layer (derive.json layers)."""
        if name not in ALL99.NATIVE_SERIES:
            return ''
        carriers = self.native_carriers.get(name) or {}
        recorded = self.derive_layers.get(name) or {}
        return ('; carriers member %s, sections %s (%s); derive.json layers[%s]: status %s, %s rows%s' % (
            list(carriers.get('member') or ()), list(carriers.get('sections') or ()), carriers.get('source'), name,
            recorded.get('status'), recorded.get('count'),
            ' (%s)' % recorded.get('reason') if recorded.get('reason') else ''))

    def _entries_of(self, source, row):
        """The registry entries one update carries (frankie_box_all99_coverage.update_entries with this ROOT's native
        carriers), plus the entries a ROOT layer carries thinner because their own carrier is absent here."""
        return ALL99.update_entries(source, row, self.native_carriers) + self.thin_for.get(source, [])

    def _carrier(self, carrier):
        """(status present/absent, reason) of one carrier as known at open."""
        if carrier in self.layers:
            layer = self.layers[carrier]
            return layer['status'], layer.get('reason')
        if carrier in ('input', 'clock'):
            return 'present', None
        if carrier == 'availability':
            present = [s.name for s in self.streams]
            return (('present', None) if present or self.publications is not None else
                    ('absent', 'no derived layer is present in this ROOT, so no update carries known_at_ns'))
        if carrier == 'opening':
            return (('present', None) if self.opening_state['status'] in OPENING_SEEDED else
                    ('absent', self.opening_state['initial_last_observed_state']['reason']))
        if carrier == 'completed':
            return (('present', None) if self.completed_sources else
                    ('absent', 'no completed per-second aggregate in this ROOT'))
        return 'absent', 'unknown carrier'

    def layer_entries(self):
        """Per carrier: its picture element, the registry entries it carries, the entries it carries thinner when their
        own carrier is absent, and whether it is present in this ROOT (with the absence reason)."""
        out = {}
        for carrier, element in CARRIER_ELEMENTS.items():
            status, reason = self._carrier(carrier)
            out[carrier] = dict(element=element, status=status, reason=reason,
                                entries=[e for e, (first, _) in CARRIERS.items() if first == carrier],
                                thin_for=[e for e, (first, thin) in CARRIERS.items()
                                          if thin == carrier and self._carrier(first)[0] == 'absent'])
        out['external']['registry'] = ('the day file\'s 13 points map to 99 entries (closest, with the reason; '
                                       'frankie_box_all99_coverage.external_point_mapping): each publication carries its '
                                       'entries, and an entry it feeds reads yielded once presented (external_points / '
                                       'external_presented on the entry\'s row); the day reports list each point under its '
                                       'entries')
        return out

    def _rows_yielded(self, carrier):
        """Rows this carrier yielded over the exhausted source (None = not counted for this carrier)."""
        outputs = self.report.get('outputs') or {}
        if carrier in self.layers and carrier != 'external':
            return ((self.report.get('sources') or {}).get(carrier) or {}).get('counts', {}).get('presented')
        if carrier == 'external':
            return outputs.get('publications_presented')
        if carrier == 'input':
            return ((self.report.get('coverage') or {}).get('inputs') or {}).get('extracted')
        if carrier == 'clock':
            return outputs.get('exact_placed')
        if carrier == 'availability':
            return outputs.get('updates_presented')
        return None

    def all99_coverage(self, *, exhausted):
        """The core's per-day FRANKIE_ALL99_COVERAGE_V1 (piece 'market_timeline'): every registry entry with the picture
        element that carries it, built and validated by the one registry module. At open (exhausted=False) a present
        carrier reads 'carrier_present'; after exhaustion 'yielded' (rows yielded) or 'yielded_no_rows' (carrier present,
        no row of it on this day: a measurement, not a zero filled in). An absent carrier with a thinner carrier present
        reads 'thin'; with none, 'absent' with the reason. The two legacy per-second aggregates read 'completed_only'."""
        rows = []
        for layer in ALL99.entries():
            name, role = layer['entry'], layer['role']
            if name in CARRIERS:
                first, thin = CARRIERS[name]
                status, reason = self._carrier(first)
                consumer = 'SharedMarketTimeline.iter_pictures: ' + CARRIER_ELEMENTS[first]
                if first == 'completed':
                    listed = [c for c in self.completed_sources if c.get('role') == name]
                    row = (dict(disposition='completed_only', reason=COMPLETED_ONLY_REASON, consumer='report.completed_sources',
                                completed=[{k: c.get(k) for k in ('role', 'path', 'bytes', 'sha256', 'disposition')} for c in listed])
                           if listed else dict(disposition='absent', reason='no completed %s aggregate in this ROOT' % name))
                elif first == 'opening':
                    row = (dict(disposition='yielded', reason='opening adapter state %s (%s)' % (
                                    self.opening_state['status'], self.opening_state['source']), consumer=consumer)
                           if status == 'present' else
                           dict(disposition='thin', reason='opening state %s: %s' % (self.opening_state['status'], reason),
                                consumer=consumer))
                elif status == 'present':
                    per_entry = first.startswith(('root.', 'native.'))
                    count = ((self.entry_counts.get(name, 0) if per_entry else self._rows_yielded(first))
                             if exhausted else None)
                    if not exhausted:
                        row = dict(disposition='carrier_present', reason='carrier present at open; rows counted at exhaustion',
                                   consumer=consumer)
                    elif count and count > 0:
                        row = dict(disposition='yielded', reason='%s update(s) of %s carrying this entry yielded over the '
                                   'exhausted source%s' % (count, first, self._native_note(name)), consumer=consumer, rows=count)
                    elif name in ALL99.NATIVE_SERIES:
                        row = dict(disposition='yielded_no_rows', canonical='thin', consumer=consumer, rows=count,
                                   reason='native carrier %s present; no update of this entry\'s own carriers on this day%s'
                                          % (first, self._native_note(name)))
                    elif first in ('input', 'clock'):
                        row = dict(disposition='thin', reason='no INPUT of the exhausted source carried a readable record / exact '
                                   'clock for this carrier (%s); every envelope was still presented' % first,
                                   consumer=consumer, rows=count)
                    else:
                        row = dict(disposition='yielded_no_rows', reason='carrier %s present; no row of it on this day '
                                   '(a measurement over the exhausted source, not a zero filled in)' % first,
                                   consumer=consumer, rows=count)
                elif thin is not None and self._carrier(thin)[0] == 'present':
                    row = dict(disposition='thin', reason='%s absent (%s); carried thinner through %s%s' % (
                                   first, reason, thin, self._native_note(name)),
                               consumer='SharedMarketTimeline.iter_pictures: ' + CARRIER_ELEMENTS[thin], thin_carrier=thin)
                else:
                    row = dict(disposition='absent', reason='%s absent: %s%s' % (first, reason, self._native_note(name)))
                row.update(carrier=first)
            elif name in NOT_CORE:
                row = dict(disposition='not_a_core_layer', reason=NOT_CORE[name])
            elif name == 'selected_same_arm_profile':
                row = dict(disposition='control', reason='a delivered binding control applied by the orchestrator\'s plan; '
                                                         'not market evidence of this reader')
            elif name == 'a_clean_promoted_positive_capsule':
                row = dict(disposition='not_applicable', reason='NOT_APPLICABLE in the crosswalk (the A-clean overlay; not Memory A)')
            elif role == 'sealed_answer':
                row = dict(disposition='withheld_by_role', reason='a sealed answer/target; never an element of the market picture')
            elif role == 'shadow':
                row = dict(disposition='disabled', reason='a provisional shadow disabled by the existing policy; never activated here')
            elif layer['group'] == 'a_memory_overlay':
                row = dict(disposition='retired', reason='Memory A retired (Greg, 2026-09-27); H06-H08 historical / not_bound')
            elif role == 'output':
                row = dict(disposition='output_not_produced_here', reason='an append-only output of a later stage; this reader '
                                                                         'writes no output')
            else:
                row = dict(disposition='not_a_core_layer', reason='a %s input read by its consuming piece; only raw/ROOT market '
                                                                  'evidence enters this reader' % role)
            fed = self.external_entry_counts.get(name, 0) if exhausted else 0
            declared = sorted(point for point, item in ((self.publications.report.get('points') or {}) if self.publications else {}).items()
                              if name in item['declared_entries'])
            if fed or declared:
                # a day-file point declares it feeds this entry: arrived only when its value was presented in the picture,
                # at or after its own publication clock (never earlier, never backfilled)
                row = dict(row, external_points=declared, external_presented=fed)
                if fed and row['disposition'] not in ('yielded',):
                    row.update(disposition='yielded', canonical='arrived',
                               consumer='SharedMarketTimeline.iter_pictures: ' + CARRIER_ELEMENTS['external'])
                row['reason'] = str(row.get('reason')) + ('; day-file point(s) %s declare this entry: %d publication(s) '
                                                          'presented at/after their publication clock' % (declared, fed))
            rows.append(dict(row, entry=name))
        return ALL99.field('market_timeline', self.day, rows, stage='shared_market_timeline',
                           basis=('pins verified and every source exhausted' if exhausted else
                                  'layers known at open; rows counted at exhaustion'))

    def _inputs(self, reader):
        """Original journal envelopes, including failed/unpaired/unknown outcomes.

        ROOT's extracted INPUT index and the ingestion adapter's cursor are different
        identities after a failed application. Neither is inferred from the other.
        Only the original matching APPLIED payload is usable by a raw teacher.
        """
        from frankie_box_boss_session import Session
        from research.kalshi.frankie_boss.c15_journal import pack
        pending, inputs, extracted, entries = None, 0, 0, 0
        accounting = self.report.setdefault('journal', dict(entries=0, inputs=0, extracted=0,
            dispositions={}, unclosed_instruments={}))
        def listed(reason, ordinal):
            ranges = accounting['dispositions'].setdefault(reason, [])
            if ranges and ranges[-1][1] + 1 == ordinal:
                ranges[-1][1] = ordinal
            else:
                ranges.append([ordinal, ordinal])
        for entry in reader.entries():
            ordinal, kind, payload = entry['ordinal'], entry['kind'], entry.get('payload')
            if ordinal != entries:
                raise ValueError('shared journal changed original envelope order')
            entries += 1
            accounting['entries'] = entries
            if kind == 'INPUT':
                if pending is not None:
                    if pending['evidence'] is None and pending['status'] == 'pending':
                        pending['status'] = 'unpaired_input'
                        listed(pending['status'], pending['entry']['ordinal'])
                    yield pending
                inputs += 1
                raw = Session._find_observation(payload, max_depth=None)
                index = extracted if raw is not None else None
                if raw is not None:
                    extracted += 1
                pending = dict(entry=entry, source_input_index=inputs - 1, input_cursor=index,
                               raw=raw, evidence=None, status='pending', outcomes=[], unpaired_outcomes=0)
                listed('input_readable' if raw is not None else 'input_without_readable_observation', ordinal)
                accounting.update(inputs=inputs, extracted=extracted)
                continue
            if pending is None:
                listed('unpaired_' + str(kind).lower(), ordinal)
                # The envelope remains an explicit original-order diagnostic, not a
                # fabricated market event or a retrospectively repaired INPUT pair.
                yield dict(entry=entry, source_input_index=None, input_cursor=None,
                           raw=None, evidence=None, status='unpaired_' + str(kind).lower(), outcomes=[], unpaired_outcomes=1)
                continue
            pending['outcomes'].append(entry)
            original = pending['entry']['payload']
            pair = (isinstance(payload, dict) and isinstance(original, dict)
                    and payload.get('input_ordinal') == pending['entry']['ordinal']
                    and payload.get('cursor') == original.get('cursor'))
            if kind == 'APPLIED' and pair:
                pair = (pack(payload.get('raw_record')) == pack(original.get('record'))
                        and all(payload.get(key) == original.get(key)
                                for key in ('source_member_index', 'session_id')))
            if kind == 'APPLIED' and pair and pending['status'] == 'pending':
                pending.update(evidence=payload, status='applied')
                listed('applied', ordinal)
            elif kind == 'FAILED' and pair and pending['status'] == 'pending':
                pending['status'] = 'failed'
                listed('failed', ordinal)
            else:
                pending['unpaired_outcomes'] += 1
                listed('unpaired_or_unknown_outcome', ordinal)
        if pending is not None:
            if pending['evidence'] is None and pending['status'] == 'pending':
                pending['status'] = 'unpaired_input'
                listed(pending['status'], pending['entry']['ordinal'])
            yield pending
        if (entries != self.source['journal_count'] or inputs != self.source['record_count']
                or extracted != self.extracted_count):
            raise ValueError('shared source dispositions differ from sealed INPUT/extraction counts')

    def iter_pictures(self):
        """Full live-like input interface, including non-APPLIED original evidence."""
        from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
        if self.started:
            raise ValueError('shared timeline iterator has one owner; open a fresh reader for another consumer')
        self.started = True
        reader = FrankieCompactReader(self.input_pin['path'], expected_count=self.source['journal_count'],
                                      expected_head_hash=self.source['journal_hash'], workers=self.workers)
        states, scopes, open_groups, frontier = {}, {}, {}, None
        # Inspection accounting (Greg, 2026-10-07: every piece reports what it received, how it
        # used it and what it produced). Counts and extents only; no evidence is copied here.
        outputs = self.report.setdefault('outputs', dict(
            pictures_yielded=0, exact_placed=0, extracted_without_exact_clock=0, envelopes_without_record=0,
            updates_presented=0, invalidations=0, publications_presented=0, publication_frontier_ns=None,
            cursor_domains=dict(source_input_index=None, input_cursor=None, adapter_cursor=None, input_journal_ordinal=None),
            basis='what the iterator yielded; a yielded picture is not proof that a consumer used it'))
        # Where the read's time goes (observability for the one-day canary; never an input to a picture): seconds inside
        # this iterator (journal decode on the reader's workers, layer-row decode, placement) against seconds the
        # consumer held each yielded picture. Per-stream decode seconds are in report['sources'][name]['timing'].
        from time import perf_counter
        clock = dict(started=perf_counter(), inside=0.0)
        clock['mark'] = clock['started']
        timing = self.report.setdefault('timing', dict(
            reader_workers=self.workers, basis='perf_counter seconds of this process; inspection only, never a value'))
        def extent(name, value):
            if type(value) is int:
                current = outputs['cursor_domains'][name]
                outputs['cursor_domains'][name] = ([value, value] if current is None
                                                   else [min(current[0], value), max(current[1], value)])
        try:
            with reader:
                for source in self._inputs(reader):
                    raw, evidence, entry = source['raw'], source['evidence'], source['entry']
                    payload = entry.get('payload') or {}
                    cursor = source['input_cursor']
                    normalized = evidence.get('normalized') if evidence is not None else None
                    instrument = (normalized.get('instrument_id') if normalized else
                                  raw.get('instrument_id') if raw is not None else None)
                    stamp = (normalized.get('ts_recv_ns') if normalized else
                             raw.get('ts_recv') if raw is not None else None)
                    updates, invalidated, member = [], [], None
                    exact = (type(cursor) is int and type(instrument) is int and type(stamp) is int)
                    if exact:
                        scope = payload.get('source_member_index'), payload.get('session_id')
                        reset = (normalized.get('action') if normalized else raw.get('action')) in ('R', b'R')
                        if reset or (instrument in scopes and scopes[instrument] != scope):
                            for key in [key for key in states if key[1] == instrument]:
                                invalidated.append(dict(source=key[0], reason='reset' if reset else 'source_scope_changed'))
                                del states[key]
                        scopes[instrument] = scope
                        open_groups.setdefault(instrument, dict(first_input_cursor=cursor, input_count=0))['input_count'] += 1
                        for stream in self.streams:
                            for update in stream.through(cursor, instrument, stamp):
                                emission = update['value'].get('frankie_emission') or {}
                                if stream.name == 'native.member':
                                    member = (emission.get('group_index'), cursor, instrument, stamp)
                                elif stream.name == 'native.lifecycle' and member != (emission.get('group_index'), cursor, instrument, stamp):
                                    raise ValueError('native lifecycle update lacks its exact same-boundary member')
                                # the registry entries this update carries, at its own causal availability (never backfilled)
                                update['entries'] = self._entries_of(stream.name, update['value'])
                                for name in update['entries']:
                                    self.entry_counts[name] = self.entry_counts.get(name, 0) + 1
                                updates.append(update)
                                if stream.state:
                                    states[(stream.name, instrument)] = update
                        if evidence is not None and evidence.get('frame') is not None:
                            open_groups.pop(instrument, None)
                            if not any(update['source'] == 'root.frames' for update in updates):
                                self.report.setdefault('closed_source_without_root_frame', []).append(entry['ordinal'])
                    elif cursor is not None:
                        self.report.setdefault('unplaceable_input_clocks', []).append(entry['ordinal'])
                        for stream in self.streams:
                            for update in stream.unplaced_at(cursor):
                                update['entries'] = self._entries_of(stream.name, update['value'])   # named, not counted as placed
                                updates.append(update)
                    if type(stamp) is int:
                        frontier = stamp if frontier is None else max(frontier, stamp)
                        if self.publications is not None:
                            for update in self.publications.through(frontier, cursor):
                                for name in update['entries']:
                                    self.external_entry_counts[name] = self.external_entry_counts.get(name, 0) + 1
                                updates.append(update)
                    point = dict(input_cursor=cursor, source_input_index=source['source_input_index'],
                                 input_journal_ordinal=entry['ordinal'], adapter_cursor=payload.get('cursor'),
                                 source_member_index=payload.get('source_member_index'), session_id=payload.get('session_id'),
                                 instrument_id=instrument,
                                 ts_event_ns=(normalized.get('ts_event_ns') if normalized else raw.get('ts_event') if raw else None),
                                 ts_recv_ns=stamp, publication_frontier_ns=frontier, raw_event_clock=raw.get('ts_event') if raw else None,
                                 raw_receive_clock=raw.get('ts_recv') if raw else None)
                    # The instant is always presented. What is missing at it is named here,
                    # per Greg's rule: a thinner picture, never a rejected time.
                    thinner = dict(absent_layers=self.absent_layers, source_status=source['status'],
                                   exact_clocks=exact, normalized_evidence=normalized is not None,
                                   readable_record=raw is not None,
                                   placement=('exact' if exact else 'extracted_input_without_exact_clock_or_identity'
                                              if cursor is not None else 'original_envelope_without_readable_record'),
                                   # the registry entries each present carrier yields (one shared reference)
                                   carried_entries=self.carried_entries,
                                   # a previously known row keeps its original cursor; before any row, the opening
                                   # disposition says what the start of the day holds (never an empty book filled in)
                                   last_observed_state=('rows_with_original_cursors' if states else
                                                        self.opening_state['initial_last_observed_state']['disposition']),
                                   active_instrument_state=('rows_with_original_cursors'
                                                            if any(entity == instrument for (_, entity) in states)
                                                            else 'no_layer_row_for_this_instrument_since_open'))
                    picture = dict(schema=SCHEMA, at=point, updates=updates, invalidated_state=invalidated,
                                   opening_state=self.opening_state,
                                   last_observed_state=list(states.values()),
                                   active_instrument_state=[value for (_, entity), value in states.items() if entity == instrument],
                                   published_state=list(self.publications.states.values()) if self.publications else [],
                                   source_status=source['status'], unpaired_outcomes=source['unpaired_outcomes'], original_input=entry,
                                   original_outcomes=source['outcomes'], original_applied=evidence, coverage=thinner)
                    if source['source_input_index'] is not None:
                        self.report['presented_inputs'] += 1
                    outputs['pictures_yielded'] += 1
                    outputs[('exact_placed' if exact else 'extracted_without_exact_clock' if cursor is not None
                             else 'envelopes_without_record')] += 1
                    outputs['updates_presented'] += sum(1 for update in updates if not update['source'].startswith('external.'))
                    outputs['publications_presented'] += sum(1 for update in updates if update['source'].startswith('external.'))
                    outputs['invalidations'] += len(invalidated)
                    outputs['publication_frontier_ns'] = frontier
                    for name in ('source_input_index', 'input_cursor', 'adapter_cursor', 'input_journal_ordinal'):
                        extent(name, point[name])
                    clock['inside'] += perf_counter() - clock['mark']
                    clock['mark'] = None                    # the consumer holds the picture: not this reader's time
                    yield dict(evidence=evidence, picture=picture)
                    clock['mark'] = perf_counter()
            for stream in self.streams:
                stream.finish()
            if self.publications is not None:
                self.publications.finish()
                self.report['external_publications'] = self.publications.report
            self.report['completed_sources'] = self.completed_sources
            self.report['journal']['unclosed_instruments'] = [dict(instrument_id=instrument, **details)
                                                            for instrument, details in open_groups.items()]
            self.report['journal']['unclosed_basis'] = 'INPUTs since last original matched APPLIED frame; missing ROOT projections are separate'
            dispositions = self.report['journal']['dispositions']
            counted = {reason: sum(last - first + 1 for first, last in ranges) for reason, ranges in dispositions.items()}
            self.report['coverage']['inputs'] = dict(
                envelopes=self.report['journal']['entries'], inputs=self.report['journal']['inputs'],
                extracted=self.report['journal']['extracted'], applied=counted.get('applied', 0),
                failed=counted.get('failed', 0), unpaired_input=counted.get('unpaired_input', 0),
                input_without_readable_observation=counted.get('input_without_readable_observation', 0),
                unplaceable_input_clocks=len(self.report.get('unplaceable_input_clocks', [])),
                closed_source_without_root_frame=len(self.report.get('closed_source_without_root_frame', [])),
                all_inputs_applied=counted.get('applied', 0) == self.report['journal']['inputs'])
            self.report['coverage']['all_layers_present'] = not self.absent_layers
            # Exhaustion only. Thinner coverage above never withholds this flag; a pin,
            # count or identity contradiction raised instead and leaves it False.
            self.report['complete'] = True
        except GeneratorExit:
            self.report['stopped'] = dict(reason='consumer closed the iterator before exhaustion',
                                          pictures_yielded=outputs['pictures_yielded'])
            raise
        except Exception as error:
            # Integrity corruption and contradictions stay visible in the report, distinct
            # from the missing-coverage listings above; they are never relabelled.
            self.report['integrity_failure'] = dict(error_type=type(error).__name__, error=str(error),
                                                    pictures_yielded_before_failure=outputs['pictures_yielded'],
                                                    disposition='separate visible failure; not missing coverage')
            raise
        finally:
            if clock['mark'] is not None:
                clock['inside'] += perf_counter() - clock['mark']
            wall = perf_counter() - clock['started']
            timing.update(wall_seconds=round(wall, 3), inside_iterator_seconds=round(clock['inside'], 3),
                          consumer_seconds=round(wall - clock['inside'], 3),
                          layer_decode_seconds=round(sum(stream.timing['decode_seconds'] for stream in self.streams), 3))
            self.report['sources'] = {stream.name: dict(source=stream.pin, counts=dict(stream.counts),
                                                       dispositions=stream.dispositions, timing=dict(stream.timing),
                                                       verification=dict(stream.verification))
                                      for stream in self.streams}
            for stream in self.streams:
                stream.close()
            if self.report.get('complete'):
                # the per-day all-99 list with the rows each carrier actually yielded over the exhausted source;
                # a stopped or failed read keeps the list made at open (its basis says so)
                self.report['all99_coverage'] = self.all99_coverage(exhausted=True)

    def iter_applied(self):
        """Teacher-facing view: every instant, with its arithmetic evidence present or absent.

        Nothing is refused and nothing is fabricated. `evidence` is the unchanged original
        APPLIED payload when the INPUT applied cleanly; otherwise it is None and
        `arithmetic` says why (failed, unpaired, unreadable, or an APPLIED beside unknown
        outcomes). A consumer's existing equation runs only where its own operands exist
        and lists the rest; this reader never derives a replacement or a target.
        """
        listing = self.report.setdefault('arithmetic', dict(present=0, absent=0, absent_by_status={}, absent_ordinals={},
            rule='absent operands block only the equation that needs them, never the instant or unrelated evidence'))

        def listed(status, ordinal):
            ranges = listing['absent_ordinals'].setdefault(status, [])
            if ranges and ranges[-1][1] + 1 == ordinal:
                ranges[-1][1] = ordinal
            else:
                ranges.append([ordinal, ordinal])
        pictures = self.iter_pictures()
        try:
            for item in pictures:
                picture = item['picture']
                if item['evidence'] is not None and not picture['unpaired_outcomes']:
                    status, arithmetic = 'present', dict(status='present', basis='original matched APPLIED payload')
                else:
                    status = (picture['source_status'] if item['evidence'] is None
                              else 'applied_with_unknown_outcomes')
                    arithmetic = dict(status='absent', reason=status, basis='no original APPLIED operand at this instant',
                                      unpaired_outcomes=picture['unpaired_outcomes'])
                    listing['absent_by_status'][status] = listing['absent_by_status'].get(status, 0) + 1
                    listed(status, picture['at']['input_journal_ordinal'])
                listing['present' if status == 'present' else 'absent'] += 1
                yield dict(item, arithmetic=arithmetic)
        finally:
            pictures.close()


class SharedFrameView:
    """The existing F_LAST scientific projection of the same market picture.

    All placed channels are handed to search together. Exact original group identity
    and clocks remain available to consumers; the search lag axis stays unchanged.
    This is a projection, not an assertion that unclosed/failed INPUTs became usable
    target rows. Their source-reader dispositions remain authoritative.
    """
    def __init__(self, frame_numeric, receive_times, series, cells, *, policy, sources):
        if policy != binding():
            raise ValueError('search shared-market implementation differs from the selected ROOT')
        # Exact membership (input_cursor, native_frame.instrument_id, input_record_indices[*]) is a layer of
        # the frame spool. A spool without it (an older legacy pass) thins the view: the axis is still the
        # spool's F_LAST closes in their original order and the search runs on it; the exact per-group
        # membership is listed absent, never guessed from timestamps. A spool WITH contradictory membership
        # raises inside frame_index: that is corruption, not missing coverage (Greg, 2026-10-07).
        self.frames, _ = frame_index(frame_numeric, receive_times)
        self.count = len(receive_times)
        if self.frames is not None and len(self.frames) != self.count:
            raise ValueError('shared search membership does not cover the frame axis')
        if any(len(values) != self.count for values in (*series.values(), *cells.values())):
            raise ValueError('shared search channels do not share the exact group axis')
        self.series, self.cells = series, cells
        self.event_times = frame_numeric.get('ts_event_ns')
        self.receive_times = receive_times
        self.sources = sources
        self.exact_membership = (dict(status='present', basis='ROOT input_cursor / instrument / input_record_indices columns')
                                 if self.frames is not None else
                                 dict(status='absent', reason='the frame spool carries no exact ROOT group membership columns; '
                                      'the F_LAST axis stands in spool order with its receive clocks, the per-group INPUT '
                                      'membership is not available to this view (thinner picture, not a rejected day)'))
        self.report = dict(source='shared_market', schema=SCHEMA, policy=policy,
            view='existing exact F_LAST projection; original source cursor and ties retained',
            frames=self.count, numeric_channels=len(series), cell_channels=len(cells),
            exact_membership=self.exact_membership,
            consumer='actual shared series/cell mappings returned to search transforms and couplings',
            limitation='fixed target axis; unclosed/failed source records and completed-only products retain source dispositions',
            rule=MISSING_COVERAGE_RULE)

    def iter_pictures(self):
        for position in range(self.count):
            frame = self.frames[position] if self.frames is not None else None
            yield dict(schema=SCHEMA, at=dict(input_cursor=frame['cursor'] if frame else None,
                instrument_id=frame['instrument'] if frame else None,
                ts_recv_ns=frame['stamp'] if frame else int(self.receive_times[position]),
                ts_event_ns=self.event_times[position] if self.event_times is not None else None),
                input_record_indices=sorted(frame['members']) if frame else None,
                membership=self.exact_membership['status'],
                values={name: values[position] for name, values in self.series.items()},
                cells={name: values[position] for name, values in self.cells.items()})
