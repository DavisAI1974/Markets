"""The parallel, resumable trading-day ingest (Greg, 2026-09-29: "Do 1-5 now. We are supposed to have save code so we can
pick up where we left off"). Spec: SPEC-ingest-parallel-replay.md, built for the experiment's journal (observation mode
'none', item 4), with the conformance drain optional (item 3) and every pass saved so a stopped run resumes.

The sequential writer (ingest_block_sources.ingest) keeps ONE process on the causal sequence: decode, INPUT entry, prefix
chain, book, APPLIED entry, digest chain. Only two of those are sequential by construction: the book/prefix-chain state
and the digest chain. So:

PASS 1 (the parent, causal, cheap): decode every record (fast_mbo_decode), cut the trading day exactly as the sequential
  writer does (tail skip / warm start, partial takes, both boundaries verified on the records), and advance ONLY the
  state: the prefix chain and the V4 book, with the builder's own checks (session change inside an open group, F_LAST
  agreement). Every SEGMENT_RECORDS records, at the first record after which no instrument group is open, the full state
  is saved (chain.export_state, export_adapter_state, the per-instrument sessions): these are the exact-resume states the
  builder's own checkpoint is made of. Saved to segments/states.c15.json + segments/plan.json.
PASS 2 (31 workers, parallel): worker k restores segment k's state into a C15Builder (observation 'none') and replays its
  records through the builder's own apply, writing each entry's canonical body with a fixed placeholder where
  previous_hash goes (the only field that depends on earlier entries' bytes) to segments/spool-<k>.bin. At its end the
  worker's chain and book state must EQUAL pass 1's state at the next boundary, else the segment is refused. A finished
  segment is renamed into place with a .done.json (entries, bytes, sha256): a resumed run skips it.
PASS 3 (the parent, sequential, cheap): each spool in order, the placeholder replaced by the real previous hash, the
  digest chained, the box cut and encoded exactly as CompactBuildJournal.append does (append_body): the same rows,
  digests, head hash and boxes as the sequential writer given the same observation mode. Then the seal.
COMPLETION: 'inline' runs the conformance drain as today (CompactConformanceReader + SourceConformanceDriver.complete);
  'deferred' writes the completion from the builder state (the same fields) marked conformance: deferred, and
  conform() runs the drain later on the sealed ingest and writes conformance.json.

RESUME: run again with --resume on the same output directory: a complete pass 1 (plan.json) is reused (the sources are
decoded again to hold the records, no state is recomputed), finished spools are reused after their sha256 is checked,
pass 3 always rebuilds the container (a partial one is moved aside, never deleted).
Nothing is dropped: every record is journaled; a record a step cannot process raises, as in the sequential writer.
"""
import gc
import hashlib
import json
import multiprocessing
import os
import pickle
import struct
import time
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path

from research.kalshi.frankie_boss import fast_mbo_decode, mbo_source
from research.kalshi.frankie_boss.c15_builder import C15Builder
from research.kalshi.frankie_boss.c15_builder_none import C15BuilderNoObservation
from research.kalshi.frankie_boss.c15_journal import SCHEMA, canonical_bytes, pack, unpack
from research.kalshi.frankie_boss.c15_registry import implementation_identity
from research.kalshi.frankie_boss.causal_prefix_records import RecordInput, RecordPrefixChain
from research.kalshi.frankie_boss.compact_build_journal import CompactBuildJournal
from research.kalshi.frankie_boss.compact_conformance_reader import CompactConformanceReader
from research.kalshi.frankie_boss.mbo_resume_state import export_adapter_state, restore_adapter_state
from research.kalshi.frankie_boss.source_conformance import SourceCompletion, SourceConformanceDriver
from research.kalshi.frankie_boss.verified_journal_reader import canonical_tagged_bytes
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import ADAPTER_REVISION, InstrumentBook, V4MboAdapter

PLACEHOLDER = 'f' * 64
SEGMENT_RECORDS = 20000
PLAN_SCHEMA = 'FRANKIE_PARALLEL_INGEST_PLAN_V1'
_HEADER = struct.Struct('<BQ')


class SpoolJournal:
    """The builder's journal interface for a pass-2 worker: each entry's canonical body (placeholder previous_hash) to a
    file. Ordinals continue from the segment's first entry (two entries per record: INPUT, APPLIED)."""
    accepts_spliced = False

    def __init__(self, path, start_ordinal):
        self.count, self.entries, self.bytes = start_ordinal, 0, 0
        self.stream = open(path, 'xb')
        self.sha = hashlib.sha256()

    head_hash = PLACEHOLDER

    def append(self, kind, payload, *, spliced=None):
        if spliced is not None:
            raise ValueError('the parallel writer runs observation mode none: nothing to splice')
        envelope = dict(schema=SCHEMA, ordinal=self.count, previous_hash=PLACEHOLDER, kind=kind, payload=payload)
        body = canonical_tagged_bytes(pack(envelope))
        name = kind.encode('ascii')
        chunk = _HEADER.pack(len(name), len(body)) + name + body
        self.stream.write(chunk)
        self.sha.update(chunk)
        self.count += 1
        self.entries += 1
        self.bytes += len(chunk)
        return PLACEHOLDER

    def close(self):
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()


def read_spool(path):
    with open(path, 'rb') as stream:
        while head := stream.read(_HEADER.size):
            if len(head) != _HEADER.size:
                raise ValueError(f'{path}: truncated entry header')
            name_length, body_length = _HEADER.unpack(head)
            name = stream.read(name_length)
            body = stream.read(body_length)
            if len(name) != name_length or len(body) != body_length:
                raise ValueError(f'{path}: truncated entry')
            yield name.decode('ascii'), body


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(16 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _state(chain, adapter, sessions, cursor, pickles):
    """The canonical state (for the equality checks and the opening book) plus the adapter PICKLED: a restore from the
    canonical export rebuilds integrity counters and the activity windows' counters in another key order, and those
    dicts reach the APPLIED bodies in their order (the review of 959c5e12, finding 2); the pickle keeps every dict,
    Counter, defaultdict and deque exactly as the live adapter holds them, so a worker's bodies are the sequential
    writer's bytes."""
    pickles.append(pickle.dumps(adapter, protocol=pickle.HIGHEST_PROTOCOL))
    return dict(cursor=cursor, chain=chain.export_state(), adapter=export_adapter_state(adapter),
                sessions=[[iid, session] for iid, session in sessions.items()])


def pass_one(scope, paths, pin, session, *, takes, tails, opening_state, source_names, evolve=True,
             segment_records=SEGMENT_RECORDS, event=None, opening_descriptor=None):
    """The decoded records of the trading day, in order, plus (evolve) the saved states. Cuts the day exactly as
    ingest_block_sources.ingest does, with the same boundary checks."""
    dbn, zstd = mbo_source._check_pin(pin)
    records, states, partials, skipped, sessions_seen, pickles = [], [], [], [], [], []
    member_counts = [0] * len(scope.members)
    adapter = V4MboAdapter()
    if opening_state is not None:
        adapter = restore_adapter_state(opening_state)
        adapter.record_count = adapter.completed_event_group_count = 0
    chain, sessions, opening_result = RecordPrefixChain(scope), {}, None
    started, since = time.perf_counter(), 0
    with ExitStack() as stack:
        snapshots = [mbo_source._verified_copy(path, member, stack) for path, member in zip(paths, scope.members)]
        streams = [mbo_source._decompressed(snapshot, zstd, stack) for snapshot in snapshots]
        metadata = [mbo_source._metadata(stream, pin, dbn) for stream in streams]
        for index, (stream, (_, ts_out), member) in enumerate(zip(streams, metadata, scope.members)):
            name = source_names[index]
            iterator = fast_mbo_decode.records(stream, pin, ts_out, dbn)
            tail, take = tails.get(member.member_key), takes.get(member.member_key)
            if tail is not None:
                warming = evolve and opening_state is None
                last, first_flags, snapshot_records, warm_started = None, None, 0, time.perf_counter()
                for position in range(tail['skip']):
                    last = next(iterator, None)
                    if last is None:
                        raise ValueError(f'{member.member_key} ends inside its declared skip of {tail["skip"]} records')
                    if warming:
                        flags = last.get('flags')
                        if position == 0:
                            first_flags = flags
                        if type(flags) is int and flags & 32:
                            snapshot_records += 1
                        adapter.apply(last, None, name, member.sha256)
                first = next(iterator, None)
                if first is None:
                    raise ValueError(f'{member.member_key} ends at its skip; the declared take of {tail["take"]} is absent')
                before, after = session(member, last), session(member, first)
                if after <= before:
                    raise ValueError(f'the declared skip of {member.member_key} does not end at a trading-day boundary')
                if opening_state is not None and opening_descriptor is not None and opening_descriptor.get('status') == 'seeded':
                    end = opening_descriptor.get('prior_end') or {}          # the sequential writer's check, the same refusal
                    if (end.get('member_key') != member.member_key or end.get('take') != tail['skip']
                            or opening_descriptor.get('prior_last_session') != before):
                        raise ValueError(f'the opening book ends at {end} (session {opening_descriptor.get("prior_last_session")}); '
                                         f'this day opens after {tail["skip"]} records of {member.member_key} (session {before}): '
                                         'the opening book is not the prior day of this cut')
                skipped.append(dict(member_key=member.member_key, skip=tail['skip'], take=tail['take'],
                                    declared_partition_mbo_records=tail['partition_mbo_records'],
                                    last_skipped_session_id=before, first_session_id=after, boundary='trading_day'))
                if warming:
                    adapter.assert_groups_closed()
                    adapter.record_count = adapter.completed_event_group_count = 0
                    starts = type(first_flags) is int and bool(first_flags & 32)
                    opening_result = dict(status='warmed_from_partition', member_key=member.member_key,
                                          records_applied_to_book=tail['skip'], first_record_flags=first_flags,
                                          snapshot_records=snapshot_records, starts_with_snapshot=starts,
                                          seconds=round(time.perf_counter() - warm_started, 3))
                    if not starts:
                        opening_result['listed'] = ('the partition does not open with a book snapshot (F_SNAPSHOT); orders '
                                                    'resting before its first record are not in the book until they trade, '
                                                    'are modified or cancelled')
                iterator = _chain_first(first, iterator)
            taken = 0
            for raw in iterator:
                cursor = len(records)
                session_id = session(member, raw)
                if not sessions_seen or sessions_seen[-1][0] != session_id:
                    sessions_seen.append((session_id, cursor, index))
                if evolve:
                    if cursor == 0:
                        states.append(_state(chain, adapter, sessions, 0, pickles))       # the day's opening state
                    msg = adapter.normalize(raw, None, name, member.sha256)
                    previous_session = sessions.get(msg.instrument_id)
                    if msg.instrument_id in chain.open_instruments and session_id != previous_session:
                        raise ValueError('session changed inside an unfinished group')
                    receipt = chain.advance(RecordInput(cursor, index, msg.public_dict(), ADAPTER_REVISION))
                    book = adapter.books.setdefault(msg.instrument_id, InstrumentBook(msg.instrument_id))
                    effect, frame, legacy = book.apply(msg)
                    adapter.record_count += 1
                    if frame is not None:
                        adapter.completed_event_group_count += 1
                    if (receipt is None) != (frame is None):
                        raise ValueError('adapter and prefix disagree on F_LAST closure')
                    sessions[msg.instrument_id] = session_id
                records.append((raw, index, session_id))
                member_counts[index] += 1
                taken += 1
                if evolve and cursor + 1 - states[-1]['cursor'] >= segment_records and not chain.open_instruments:
                    try:
                        adapter.assert_groups_closed()               # both the chain and the book must be group-closed
                    except RuntimeError:
                        pass
                    else:
                        states.append(_state(chain, adapter, sessions, cursor + 1, pickles))
                if take is not None and taken == take['take']:
                    following = next(iterator, None)
                    if following is None:
                        raise ValueError(f'{member.member_key} ends at its take of {take["take"]} records')
                    next_session = session(member, following)
                    if next_session <= session_id:
                        raise ValueError(f'the declared take of {member.member_key} does not end at a trading-day boundary')
                    partials.append(dict(member_key=member.member_key, take=take['take'],
                                         declared_partition_mbo_records=take['partition_mbo_records'],
                                         next_session_id=next_session, boundary='trading_day'))
                    break
                if event is not None and len(records) - since >= 50000:
                    since = len(records)
                    event(dict(phase='parallel_pass1', records=len(records), states=len(states),
                               seconds=round(time.perf_counter() - started, 3)))
    if evolve:
        if states[-1]['cursor'] != len(records):
            states.append(_state(chain, adapter, sessions, len(records), pickles))
    return dict(records=records, states=states, pickles=pickles, partials=partials, skipped=skipped, sessions_seen=sessions_seen,
                member_counts=member_counts, opening_result=opening_result, seconds=round(time.perf_counter() - started, 3))


def _chain_first(first, rest):
    yield first
    yield from rest


_SHARED = {}


def _segment(k):
    """Pass-2 worker: replay segment k from its saved state through the builder; its end state must equal pass 1's."""
    s = _SHARED
    start_state, end_state = s['states'][k], s['states'][k + 1]
    started = time.process_time()
    b = C15BuilderNoObservation.__new__(C15BuilderNoObservation)
    b.scope, b.identity, b._failed = s['scope'], implementation_identity(), False
    b.chain = RecordPrefixChain.restore(s['scope'], start_state['chain'])
    b.adapter = pickle.loads(s['pickles'][k])                   # the live adapter, exactly (key order included)
    if export_adapter_state(b.adapter) != start_state['adapter']:
        raise ValueError(f'segment {k}: the pickled adapter differs from its canonical state; refused')
    b._sessions = {int(iid): session for iid, session in start_state['sessions']}
    final = s['spools'] / f'spool-{k:05d}.bin'
    part = final.with_name(final.name + '.part')
    if part.exists():
        part.rename(part.with_name(part.name + f'.stopped-{int(time.time())}'))   # an interrupted attempt: kept aside
    b.journal = SpoolJournal(part, 2 * start_state['cursor'])
    for cursor in range(start_state['cursor'], end_state['cursor']):
        raw, member_index, session_id = s['records'][cursor]
        b.apply(raw, source_member_index=member_index, session_id=session_id, raw_symbol=None,
                source_dbn_object=s['names'][member_index])
    b.journal.close()
    if (b.chain.export_state() != end_state['chain'] or export_adapter_state(b.adapter) != end_state['adapter']
            or [[iid, v] for iid, v in b._sessions.items()] != end_state['sessions']):
        raise ValueError(f'segment {k}: the replayed end state differs from pass 1 at cursor {end_state["cursor"]}; refused')
    os.replace(part, final)
    done = dict(segment=k, start_cursor=start_state['cursor'], end_cursor=end_state['cursor'], entries=b.journal.entries,
                bytes=b.journal.bytes, sha256=b.journal.sha.hexdigest(), cpu_seconds=round(time.process_time() - started, 3))
    final.with_name(final.name + '.done.json').write_text(json.dumps(done, sort_keys=True))
    return done


def _done(spools, k):
    marker = spools / f'spool-{k:05d}.bin.done.json'
    if not marker.is_file():
        return None
    done = json.loads(marker.read_bytes())
    spool = spools / f'spool-{k:05d}.bin'
    if not spool.is_file() or spool.stat().st_size != done['bytes'] or _sha256_file(spool) != done['sha256']:
        return None
    return done


def _builder_at(scope, state, journal):
    b = C15Builder.__new__(C15Builder)
    b.scope, b.identity, b._failed, b.journal = scope, implementation_identity(), False, journal
    b.chain = RecordPrefixChain.restore(scope, state['chain'] if 'chain' in state else state['prefix'])
    b.adapter = restore_adapter_state(state['adapter'])
    b._sessions = {int(iid): session for iid, session in state['sessions']}
    return b


class _Tail:
    """The journal interface export_state reads (count, head_hash) for a deferred completion."""
    def __init__(self, count, head_hash):
        self.count, self.head_hash = count, head_hash


def completion_from(scope, builder, member_counts):
    """The completion complete() would claim, from the builder state, with complete()'s own count refusals (the review of
    959c5e12, finding 4): every declared record of every member ingested, no more, no less."""
    expected = [member.mbo_records for member in scope.members]
    if builder.chain.next_cursor != sum(expected) or list(member_counts) != expected:
        raise ValueError(f'source record count is incomplete or does not reconcile: ingested {list(member_counts)} '
                         f'(cursor {builder.chain.next_cursor}), declared {expected}')
    state = builder.export_state()
    completion = SourceCompletion('BOSS_SOURCE_CONFORMANCE_V1', scope.kind.value, scope.genesis_hash(), sum(member_counts),
                                  tuple(member_counts), builder.chain.next_global_group_ordinal, builder.chain.prefix_hash,
                                  state['journal_count'], state['journal_hash'], state['state_hash'])
    return completion, state


def conform(scope, journal_path, checkpoint_state, *, workers, emit=None):
    """The conformance drain on a sealed container (inline, or later for a deferred ingest): the builder at its final
    state reads every entry back through CompactConformanceReader and SourceConformanceDriver.complete()."""
    reader = CompactConformanceReader(journal_path, expected_count=checkpoint_state['journal_count'],
                                      expected_head_hash=checkpoint_state['journal_hash'], workers=workers, emit=emit)
    try:
        b = _builder_at(scope, dict(chain=checkpoint_state['prefix'], adapter=checkpoint_state['adapter'],
                                    sessions=checkpoint_state['sessions']), reader)
        driver = SourceConformanceDriver.__new__(SourceConformanceDriver)
        driver._builder = b
        driver._stopped = driver._completed = driver._closed = False
        completion = driver.complete()
        return completion, b.export_state()
    finally:
        reader.close()


def ingest_parallel(scope, paths, *, pin, session, source_names, journal_path, output, takes, tails, opening_state,
                    opening_descriptor, workers, encoders, block_rows, block_bytes, verify, resume, manifest_hash,
                    segment_records=SEGMENT_RECORDS, event=None):
    started, cpu_started = time.perf_counter(), time.process_time()
    output = Path(output)
    seg_dir = output / 'segments'
    seg_dir.mkdir(exist_ok=True)
    plan_path, states_path, pickles_path = seg_dir / 'plan.json', seg_dir / 'states.c15.json', seg_dir / 'adapters.pickle'
    identity = implementation_identity()
    plan = json.loads(plan_path.read_bytes()) if (resume and plan_path.is_file()) else None
    if plan is not None and (plan.get('schema') != PLAN_SCHEMA or plan.get('manifest_hash') != manifest_hash
                             or plan.get('implementation') != identity or plan.get('segment_records') != segment_records
                             or _sha256_file(states_path) != plan.get('states_sha256')
                             or _sha256_file(pickles_path) != plan.get('adapters_sha256')):
        raise ValueError('the saved pass-1 plan is for another manifest, code identity or segment size; refused '
                         '(move segments/ aside to start over)')
    if plan is None:
        if plan_path.exists():
            raise ValueError(f'{plan_path} exists; resume with --resume or move segments/ aside')
        one = pass_one(scope, paths, pin, session, takes=takes, tails=tails, opening_state=opening_state,
                       source_names=source_names, segment_records=segment_records, event=event,
                       opening_descriptor=opening_descriptor)
        states_raw = canonical_bytes(pack(one['states']))
        with states_path.open('xb') as stream:
            stream.write(states_raw); stream.flush(); os.fsync(stream.fileno())
        pickles_raw = pickle.dumps(one['pickles'], protocol=pickle.HIGHEST_PROTOCOL)
        with pickles_path.open('xb') as stream:
            stream.write(pickles_raw); stream.flush(); os.fsync(stream.fileno())
        plan = dict(schema=PLAN_SCHEMA, manifest_hash=manifest_hash, implementation=identity, segment_records=segment_records,
                    records=len(one['records']), segments=len(one['states']) - 1, states_sha256=hashlib.sha256(states_raw).hexdigest(),
                    adapters_sha256=hashlib.sha256(pickles_raw).hexdigest(),
                    partials=one['partials'], skipped=one['skipped'], sessions_seen=one['sessions_seen'],
                    member_counts=one['member_counts'], opening_result=one['opening_result'], pass1_seconds=one['seconds'])
        with plan_path.open('x') as stream:
            json.dump(plan, stream, sort_keys=True)
        states, pickles = one['states'], one['pickles']
        records = one['records']
    else:
        states = unpack(json.loads(states_path.read_bytes()))
        pickles = pickle.loads(pickles_path.read_bytes())
        one = pass_one(scope, paths, pin, session, takes=takes, tails=tails, opening_state=opening_state,
                       source_names=source_names, evolve=False, event=event)          # the records again; no state recomputed
        records = one['records']
        if len(records) != plan['records'] or one['member_counts'] != plan['member_counts']:
            raise ValueError('the sources decode to a different record count than the saved plan; refused')
    if event is not None:
        event(dict(phase='parallel_pass1_done', records=len(records), segments=plan['segments']))
    # the day's opening book beside the journal (the same bytes the sequential writer writes)
    book_raw = canonical_bytes(pack(states[0]['adapter']))
    book_path = output / 'opening-book.c15.json'
    if book_path.exists():
        if book_path.read_bytes() != book_raw:
            raise ValueError('an opening-book.c15.json from another attempt differs; refused')
    else:
        with book_path.open('xb') as stream:
            stream.write(book_raw); stream.flush(); os.fsync(stream.fileno())
    opening_file = dict(file=book_path.name, bytes=len(book_raw), sha256=hashlib.sha256(book_raw).hexdigest(),
                        adapter_state_hash=states[0]['adapter']['state_hash'])
    opening_result = dict(plan['opening_result'] or dict(opening_descriptor or {}, status='seeded')) if (plan['opening_result'] or opening_descriptor) else None
    if opening_result is not None:
        opening_result.update(file=opening_file, instruments=len(states[0]['adapter']['books']),
                              resting_orders=sum(len(b['orders']) for b in states[0]['adapter']['books']))
    # PASS 2
    pass2_started = time.perf_counter()
    pending = [k for k in range(plan['segments']) if _done(seg_dir, k) is None]
    _SHARED.update(scope=scope, states=states, pickles=pickles, records=records, names=source_names, spools=seg_dir)
    del one
    worker_cpu = 0.0
    if pending:
        gc.collect()
        gc.freeze()          # the forked workers share the records without the collector touching (and copying) every page
        with multiprocessing.get_context('fork').Pool(workers) as pool:
            for done in pool.imap_unordered(_segment, pending):
                worker_cpu += done['cpu_seconds']
                if event is not None:
                    event(dict(phase='parallel_pass2', segment=done['segment'], entries=done['entries']))
    pass2_seconds = time.perf_counter() - pass2_started
    _SHARED.clear()
    del records
    gc.unfreeze()
    # PASS 3
    pass3_started = time.perf_counter()
    if Path(journal_path).exists():
        Path(journal_path).rename(Path(str(journal_path) + f'.partial-{int(time.time())}'))   # never deleted
    journal = CompactBuildJournal(journal_path, block_bytes=block_bytes, workers=encoders, block_rows=block_rows)
    try:
        for k in range(plan['segments']):
            spool = seg_dir / f'spool-{k:05d}.bin'
            for kind, body in read_spool(spool):
                journal.append_body(kind, body, PLACEHOLDER)
            if event is not None:
                event(dict(phase='parallel_pass3', segment=k, entries=journal.count))
        journal.seal()
        worker_cpu += journal.worker_cpu_seconds
    finally:
        journal.close()
    pass3_seconds = time.perf_counter() - pass3_started
    if journal.count != 2 * plan['records']:
        raise ValueError(f'the container holds {journal.count} entries for {plan["records"]} records; refused')
    # the spools are the workers' intermediate bytes, every entry of which is now in the sealed container; they are
    # removed (listed with their sha256) so a day does not hold its journal twice on the box
    spools_removed = []
    for k in range(plan['segments']):
        spool = seg_dir / f'spool-{k:05d}.bin'
        done = _done(seg_dir, k)
        spools_removed.append(dict(segment=k, bytes=done['bytes'], sha256=done['sha256']))
        spool.unlink()
    final_state = states[-1]
    verify_started = time.perf_counter()
    if verify == 'inline':
        checkpoint = _builder_at(scope, final_state, _Tail(journal.count, journal.head_hash)).export_state()
        completion, state = conform(scope, journal_path, checkpoint, workers=encoders or 1, emit=event)
        conformance = 'inline'
    else:
        builder = _builder_at(scope, final_state, _Tail(journal.count, journal.head_hash))
        completion, state = completion_from(scope, builder, plan['member_counts'])
        conformance = 'deferred'
    verify_seconds = time.perf_counter() - verify_started
    seconds = time.perf_counter() - started
    records_total = plan['records']
    sessions = [dict(session_id=s, first_cursor=c, member_index=m) for s, c, m in plan['sessions_seen']]
    return dict(kind='complete', completion=asdict(completion), completion_digest=completion.digest, state=state,
                ingest_seconds=round(seconds, 3), ingest_cpu_seconds=round(time.process_time() - cpu_started, 3),
                records_per_second=round(records_total / seconds, 2), ms_per_record=round(1000 * seconds / records_total, 3),
                conformance_seconds=round(verify_seconds, 3), conformance=conformance, sessions=sessions,
                records=records_total, workers=workers, worker_cpu_seconds=round(worker_cpu, 3),
                partial_members=plan['partials'], tail_members=plan['skipped'], opening_book=opening_result,
                opening_book_file=opening_file,
                packing=dict(block_rows=block_rows, block_bytes=block_bytes,
                             standard='box_standard.TARGET_BOXES 1189: rows per box = partition_entries_for(2 x declared '
                                      'records), bytes per box = the format ceiling (the same cut as the sequential writer)'),
                parallel=dict(segments=plan['segments'], segment_records=segment_records, resumed_segments=plan['segments'] - len(pending),
                              pass1_seconds=plan.get('pass1_seconds'), pass2_seconds=round(pass2_seconds, 3),
                              pass3_seconds=round(pass3_seconds, 3), placeholder=PLACEHOLDER,
                              spools_removed_after_seal=spools_removed))
