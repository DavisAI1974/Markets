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
from pathlib import Path

SCHEMA = 'FRANKIE_SHARED_MARKET_TIMELINE_V1'


LAYERS = ('root.frames', 'root.prices', 'root.structures', 'native.member', 'native.lifecycle', 'external')

# Greg, 2026-10-07 (supersedes earlier completeness wording): no day or time is rejected
# from the reconstruction because data is missing. The instant stays, thinner, with explicit
# dispositions. Integrity corruption (altered pinned bytes, contradictory identities) is a
# separate visible failure and is never relabelled as missing coverage.
MISSING_COVERAGE_RULE = 'every_authentic_boundary_kept_with_thinner_explicit_picture'


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


def _rows(pin, *, packed):
    """Check the exact consumed bytes; caller must exhaust before claiming completion."""
    from research.kalshi.frankie_boss.c15_journal import unpack
    hashed, size = hashlib.sha256(), 0
    with _local(pin['path']).open('rb') as stream:
        for ordinal, raw in enumerate(stream):
            hashed.update(raw)
            size += len(raw)
            row = json.loads(raw)
            yield ordinal, unpack(row) if packed else row
    if size != pin['bytes'] or hashed.hexdigest() != pin['sha256']:
        raise ValueError('shared market rows differ from their source pin: ' + pin['path'])


class _Changes:
    """One existing ordered producer stream; no completion-order merge or row cap."""
    def __init__(self, name, pin, *, kind, state):
        self.name, self.pin, self.kind, self.state = name, pin, kind, state
        self.rows = _rows(pin, packed=kind in ('frame', 'price', 'structure'))
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
    """Every external row at its existing publication clock, in original tie order."""
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
                           missing=body.get('missing'), after_halt={})
        for table_ordinal, (name, table) in enumerate(body['points'].items()):
            columns = table['columns']
            stamp = columns.index(table['stamp_column'])
            identities = [i for i, key in enumerate(columns) if key in self.IDENTITIES]
            self.report['after_halt'][name] = table.get('after_halt')
            for ordinal, row in enumerate(table['rows']):
                known = row[stamp]
                if type(known) is not int:
                    raise ValueError('external publication clock is not exact integer nanoseconds')
                entity = [(columns[i], row[i]) for i in identities]
                value = dict(columns=columns, row=row, entity=entity,
                             table_metadata={k: v for k, v in table.items() if k not in ('rows', 'columns')})
                self.rows.append((known, table_ordinal, ordinal, name, value))
        self.rows.sort(key=lambda item: item[:3])

    def through(self, frontier, cursor):
        while self.position < len(self.rows) and self.rows[self.position][0] <= frontier:
            known, _, ordinal, name, value = self.rows[self.position]
            self.position += 1
            update = dict(source='external.' + name, source_ordinal=ordinal, known_at_ns=known,
                          presented_at_input_cursor=cursor, value=value,
                          availability_basis='original_publication_clock_at_observed_receive_frontier')
            key = name, json.dumps(value['entity'], sort_keys=True, separators=(',', ':'))
            self.states[key] = update
            self.report['presented'] += 1
            yield update

    def finish(self):
        for _, _, ordinal, name, _ in self.rows[self.position:]:
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
    reconstructed intermediate book. Absent layers (native with bedrock off, a spool
    the ROOT did not publish, no day file) thin the picture and are listed in
    `report['coverage']`; `report['complete']` means only that the whole available
    source was exhausted with its pins verified.
    """
    def __init__(self, calculations, *, day, workers=15):
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
            self.streams.append(_Changes(name, pin, kind=kind, state=state))
        # Native: absent when the ROOT ran with bedrock off (selected_files returns nothing);
        # a bedrock-on ROOT whose artifacts are incomplete or altered raises inside selected_files.
        selected = {item['native_role']: item for item in selected_files(root, str(day))}
        for role, name, state in (('exact_member_rows.jsonl', 'native.member', True),
                                  ('exact_lifecycle_rows.jsonl', 'native.lifecycle', False)):
            item = selected.get(role)
            if item is None:
                self.layers[name] = dict(status='absent', reason=('no completed native calculation in this ROOT (bedrock off)'
                                                                  if not selected else 'native ledger not selected'))
                continue
            pin = dict(path=item['source'], **item['expected'])
            self.layers[name] = dict(status='present', source=pin)
            self.streams.append(_Changes(name, pin, kind='native', state=state))
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
        self.extracted_count = derive['input_records']
        self.input_pin = self.source['container']
        if witness(self.input_pin['path']) != {k: self.input_pin[k] for k in ('bytes', 'sha256')}:
            raise ValueError('shared input journal differs from its exact sealed source bytes')
        self.identity = dict(schema=SCHEMA, day=self.day, source_binding=source_pin,
                             calculations=calculation_pin, journal=self.input_pin,
                             sources={stream.name: stream.pin for stream in self.streams}, external=external,
                             completed_sources=self.completed_sources, absent_layers=self.absent_layers)
        self.report = dict(identity=self.identity, complete=False, presented_inputs=0,
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
        self.started = False

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
                            updates.extend(stream.unplaced_at(cursor))
                    if type(stamp) is int:
                        frontier = stamp if frontier is None else max(frontier, stamp)
                        if self.publications is not None:
                            updates.extend(self.publications.through(frontier, cursor))
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
                                              if cursor is not None else 'original_envelope_without_readable_record'))
                    picture = dict(schema=SCHEMA, at=point, updates=updates, invalidated_state=invalidated,
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
                    yield dict(evidence=evidence, picture=picture)
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
            self.report['sources'] = {stream.name: dict(source=stream.pin, counts=dict(stream.counts),
                                                       dispositions=stream.dispositions) for stream in self.streams}
            for stream in self.streams:
                stream.close()

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
        self.frames, _ = frame_index(frame_numeric, receive_times)
        if self.frames is None:
            raise ValueError('shared search requires exact original ROOT group membership')
        if any(len(values) != len(self.frames) for values in (*series.values(), *cells.values())):
            raise ValueError('shared search channels do not share the exact group axis')
        self.series, self.cells = series, cells
        self.event_times = frame_numeric.get('ts_event_ns')
        self.sources = sources
        self.report = dict(source='shared_market', schema=SCHEMA, policy=policy,
            view='existing exact F_LAST projection; original source cursor and ties retained',
            frames=len(self.frames), numeric_channels=len(series), cell_channels=len(cells),
            consumer='actual shared series/cell mappings returned to search transforms and couplings',
            limitation='fixed target axis; unclosed/failed source records and completed-only products retain source dispositions')

    def iter_pictures(self):
        for position, frame in enumerate(self.frames):
            yield dict(schema=SCHEMA, at=dict(input_cursor=frame['cursor'],
                instrument_id=frame['instrument'], ts_recv_ns=frame['stamp'],
                ts_event_ns=self.event_times[position] if self.event_times is not None else None),
                input_record_indices=sorted(frame['members']),
                values={name: values[position] for name, values in self.series.items()},
                cells={name: values[position] for name, values in self.cells.items()})
