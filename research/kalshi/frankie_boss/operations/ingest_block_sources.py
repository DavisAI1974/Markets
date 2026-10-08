"""Ingest a staged multi-day block (or the Sunday day) as ONE continuous stream, straight into the compact container.

The members replay in manifest order with no gap between them, Sunday reopen through the last file,
exactly as the tape ran. Two things the Sunday build did differently are changed here and nothing else:

- the writer: the builder's journal is CompactBuildJournal, so the 2 TB raw journal a 6.47M-record
  block would need is never written; the container is what the Sunday host already reads;
- the session identity: declared per run through --session-policy (Greg's call, review 2.7), because
  DChain and the teacher reset on a session change and the string is inside every journal row:
    per_member_file    one session per UTC day file (what the Sunday build did; the day from the member key)
    cme_trading_day    the CME trading day (Greg, 2026-09-16, standing). CME's Henry Hub Natural Gas
                       futures specification, CME Globex hours, verbatim: "Sunday - Friday 6:00 p.m. -
                       5:00 p.m. (5:00 p.m. - 4:00 p.m. CT) with a 60-minute break each day beginning at
                       5:00 p.m. (4:00 p.m. CT)" (natural-gas.contractSpecs.html, read 2026-09-16), so a
                       session opens at 6:00 p.m. ET and carries the trade date of the afternoon it ends
                       on; Monday's opens on Sunday evening. In this policy a record before the 17:00 ET
                       halt belongs to its date, a record at or after it to the next date, so the 18:00 ET
                       reopen is the next day's evening session; after Friday's halt, on Saturday and on
                       Sunday before the reopen the next trading day is Monday. 17:00 ET is 21:00Z under
                       EDT; the manifest declares the halt hour and that every halt boundary closes an
                       F_LAST group. Exchange holidays are not modelled (the October block crosses none)
    constant:<id>      one literal session for every record (the Sunday run used 'supplied-source')

source_dbn_object, which the normaliser carries into the prefix chain, is the member KEY for a block
(never a machine path, D34); --source-object path records str(path) only to reproduce the Sunday
run's own prefix hash in the both-ways proof.

    python operations/ingest_block_sources.py --manifest blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json \
        --sources-dir <dir> --fetch --output-dir <dir> --session-policy cme_trading_day
    python operations/ingest_block_sources.py --manifest ... --sources-dir <dir> --output-dir <scratch> \
        --session-policy cme_trading_day --canary-records 20000          # rate only, no completion claim
    python operations/ingest_block_sources.py --sunday --source-path <delivery-compressed file> --output-dir <scratch> \
        --session-policy constant:supplied-source --source-object path --writer both   # the both-ways proof

--canary-records stops after N records and reports the rate and the extrapolation; it writes no
completion and its output directory name must say scratch or canary. --writer both runs the raw
EvidenceJournal path and the compact path on the same inputs and compares every row.
"""
import argparse
import datetime as dt
import hashlib
import itertools
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
for entry in (str(ROOT),):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from research.kalshi.frankie_boss import mbo_source                                   # noqa: E402
from research.kalshi.frankie_boss.block_source_scope import block_source_scope          # noqa: E402
from research.kalshi.frankie_boss.c15_journal import evidence_hash, pack, unpack, canonical_bytes  # noqa: E402
from research.kalshi.frankie_boss.compact_build_journal import conformance_driver_with_compact_journal  # noqa: E402
from research.kalshi.frankie_boss.compact_journal import CompactReader, MAX_BYTES      # noqa: E402
from research.kalshi.frankie_boss.box_standard import partition_entries_for            # noqa: E402
from research.kalshi.frankie_boss.compact_conformance_reader import CompactConformanceReader     # noqa: E402
from research.kalshi.frankie_boss.selected_source_scope import source_manifest, source_scope  # noqa: E402
from research.kalshi.frankie_boss.source_conformance import SourceConformanceDriver     # noqa: E402
from research.kalshi.frankie_boss import opening_book as opening_books                  # noqa: E402
from research.kalshi.frankie_boss import fast_mbo_decode                                # noqa: E402
from research.kalshi.frankie_boss.operations import parallel_ingest                     # noqa: E402
from research.kalshi.frankie_boss.operations import ingest_cpus                         # noqa: E402

RECEIPT_SCHEMA = 'BOSS_BLOCK_INGESTION_RECEIPT_V1'
CANARY_SCHEMA = 'BOSS_BLOCK_INGESTION_CANARY_V1'
PROOF_SCHEMA = 'BOSS_COMPACT_BUILD_BOTH_WAYS_PROOF_V1'
DEFAULT_HALT_UTC_HOUR = 21
_DAY = re.compile(r'(\d{8})')


def load_env_file(path):
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'\s*(?:export\s+)?([A-Z_]+)\s*=\s*"?([^"\n]+)"?', line)
        if m and m.group(1).startswith('AWS_'):
            os.environ[m.group(1)] = m.group(2).strip()


def member_day(member):
    match = _DAY.search(member.member_key)
    if match is None:
        raise ValueError('member key carries no UTC day: ' + member.member_key)
    return match.group(1)


def session_policy(name, *, halt_utc_hour):
    """Return (policy_name, callable(member, raw) -> session id)."""
    if name == 'per_member_file':
        return name, lambda member, raw: member_day(member)
    if name == 'cme_trading_day':
        if type(halt_utc_hour) is not int or not 0 <= halt_utc_hour < 24:
            raise ValueError('halt hour required for the trading-day policy')

        def trading_day(member, raw):
            moment = dt.datetime.fromtimestamp(raw['ts_recv'] // 10**9, tz=dt.timezone.utc)
            day = moment.date() + (dt.timedelta(days=1) if moment.hour >= halt_utc_hour else dt.timedelta())
            # The CME week: Friday's 17:00 ET halt is followed by no reopen, Saturday is closed, and
            # Sunday's 18:00 ET reopen is Monday's trade date, so a date that lands on Saturday or
            # Sunday rolls to Monday. Exchange holidays are a calendar this block does not cross.
            if day.weekday() >= 5:
                day += dt.timedelta(days=7 - day.weekday())
            return day.strftime('%Y%m%d')
        return name, trading_day
    if name.startswith('constant:') and len(name) > len('constant:'):
        literal = name[len('constant:'):]
        return name, lambda member, raw: literal
    raise ValueError('session policy must be per_member_file, cme_trading_day or constant:<id>')


def partial_takes(manifest, *, policy_name):
    """The manifest's partial members (Greg, 2026-09-22: the TRADING DAY is the unit, a UTC partition is not): each names a
    member whose declared mbo_records is the TAKE, the records of that partition that belong to this trading day (the
    ones before the halt), with the partition's own count beside it. The take must end at a trading-day boundary, which
    the ingest verifies on the next record; so the trading-day policy is required."""
    raw = manifest.get('partial_members')
    if not raw:
        return {}
    if policy_name != 'cme_trading_day':
        raise ValueError('partial members need the cme_trading_day policy (the take ends at a trading-day boundary)')
    by_key = {m['member_key']: m for m in manifest['sources']}
    if len(raw) != 1:
        # the ship review 2026-09-22: after a take the stream ENDS (the take closes the trading day), so a second partial member
        # could never be reached and a manifest naming two is not the declaration it looks like
        raise ValueError('a manifest declares at most one partial member (the take ends the stream)')
    takes = {}
    for entry in raw:
        if (type(entry) is not dict or entry.get('member_key') not in by_key
                or type(entry.get('take')) is not int or entry['take'] <= 0
                or type(entry.get('partition_mbo_records')) is not int or entry['take'] >= entry['partition_mbo_records']
                or by_key[entry['member_key']]['mbo_records'] != entry['take']):
            raise ValueError('a partial member must name a source whose mbo_records is its take, below the partition count')
        if entry['member_key'] != manifest['sources'][-1]['member_key']:
            # the ship review 2026-09-22: a member after the take would be ingested whole after it and the container would
            # claim completion holding another trading day's records
            raise ValueError('the partial member must be the last member of the manifest (the take ends the stream)')
        takes[entry['member_key']] = dict(take=entry['take'], partition_mbo_records=entry['partition_mbo_records'])
    return takes


def tail_skips(manifest, *, policy_name):
    """The manifest's tail member (derive_trading_day_manifest; Greg, 2026-09-29: "build the remaining missing hrs for
    Tuesday"): the FIRST member, whose declared mbo_records is the TAKE (the records at or after the halt that open this
    trading day) after SKIP records that are the prior trading day's (decoded to reach the cut, never appended, never
    counted). The cut must be a trading-day boundary on both sides, which the ingest verifies on the records themselves;
    so the trading-day policy is required."""
    raw = manifest.get('tail_members')
    if not raw:
        return {}
    if policy_name != 'cme_trading_day':
        raise ValueError('a tail member needs the cme_trading_day policy (the skip ends at a trading-day boundary)')
    if len(raw) != 1:
        raise ValueError('a manifest declares at most one tail member (the tail opens the stream)')
    entry, first = raw[0], manifest['sources'][0]
    if (type(entry) is not dict or entry.get('member_key') != first['member_key']
            or any(type(entry.get(k)) is not int or entry[k] <= 0 for k in ('skip', 'take', 'partition_mbo_records'))
            or entry['skip'] + entry['take'] != entry['partition_mbo_records'] or first['mbo_records'] != entry['take']):
        raise ValueError('a tail member must be the first member, its mbo_records the take, skip + take its partition count')
    return {entry['member_key']: dict(skip=entry['skip'], take=entry['take'], partition_mbo_records=entry['partition_mbo_records'])}


def opening_adapter(adapter_state):
    """The prior day's closing book as a live adapter: restored exactly (mbo_resume_state validates and round-trips it),
    its two counters zeroed so the day's record and group counts are the day's own; the books are untouched."""
    from research.kalshi.frankie_boss.mbo_resume_state import restore_adapter_state
    adapter = restore_adapter_state(adapter_state)
    adapter.record_count = 0
    adapter.completed_event_group_count = 0
    return adapter


def ingest(scope, paths, *, expected_scope_hash, pin, session, source_object, journal_path,
           writer='compact', canary_records=None, block_bytes=MAX_BYTES // 2, workers=0, event=None, takes=None, block_rows=None,
           tails=None, opening=None, opening_descriptor=None, observation_mode='full', verify='inline', fast_decode=True):
    """The ingest_sources loop with a chosen writer, a per-record session policy and member-key naming.

    Returns dict(kind='canary'|'complete', ...). The record decode is mbo_source's pinned extractor,
    untouched; the builder is the lawful C15Builder through SourceConformanceDriver. `takes` (from
    partial_takes) stops a partial member after its declared take and refuses a take that does not end
    at a trading-day boundary; the pinned conformance stack then reconciles the declared counts as ever. `tails` (from
    tail_skips) skips the first member's prior-day records up to the halt and verifies the cut on both sides; `opening`
    (opening_adapter, from the prior day's sealed ingest) is the book the day opens with, and `opening_descriptor` says
    where it came from (its prior_end must be this cut: the same member and a take equal to the skip). Without `opening`
    the day WARMS its own book (Greg, 2026-09-29: "we will just be running tue and weds for a while", so a Tuesday cannot
    wait on a Monday ingest): the tail partition's prior-day records are applied to the book only (never journaled,
    never counted), from the partition's first record (its 00:00Z book snapshot, which is checked and listed) up to the
    halt; the book at the halt is then the day's opening book. Either way the opening book is written beside the journal
    (opening-book.c15.json, sha256 in the receipt) so the day's ROOT opens from the same bytes without the prior day.
    """
    SourceConformanceDriver._check_scope(scope, expected_scope_hash)
    takes = dict(takes or {})
    tails = dict(tails or {})
    dbn, zstd = mbo_source._check_pin(pin)
    if type(paths) is not tuple or len(paths) != len(scope.members):
        raise ValueError('complete ordered source paths required')
    if writer not in ('compact', 'raw'):
        raise ValueError('writer must be compact or raw')
    if canary_records is not None and (type(canary_records) is not int or canary_records <= 0):
        raise ValueError('canary record count must be a positive integer')
    total = sum(member.mbo_records for member in scope.members)
    # THE BOX STANDARD (box_standard.py; Greg, 2026-09-17: TARGET_BOXES = 1189 for every day we ingest; 2026-09-22: "turn the single lines
    # into boxes"): rows per box derived from the day's entry count (two entries per record: INPUT and APPLIED), clamped by
    # the format; the bytes per box at the format's ceiling. The ingest writer cut 4 MiB blocks of its own before this.
    if block_rows is None:
        block_rows = partition_entries_for(2 * total)
    packing = dict(block_rows=block_rows, block_bytes=block_bytes,
                   standard='box_standard.TARGET_BOXES 1189: rows per box = partition_entries_for(2 x declared records), '
                            'bytes per box = the format ceiling')
    started, cpu_started = time.perf_counter(), time.process_time()
    # CPU placement (Greg, 2026-10-07 night: every ingest process pinned): the parent on the booking's lowest CPU, each
    # encoder on one worker CPU (physical cores first), the reader's workers on cpus[1:] as the first run's reader pins
    # them; placement only (operations/ingest_cpus.py)
    place = ingest_cpus.placement(workers)
    if event is not None:
        event(ingest_cpus.record(workers))
    with ExitStack() as stack:
        # every member verified and decompressed side by side before any record is read (parallel_ingest.prepared_sources)
        prepared = parallel_ingest.prepared_sources(paths, scope.members, pin, dbn, zstd, stack, event=event)
        streams, metadata = [p[0] for p in prepared], [p[1] for p in prepared]
        if writer == 'compact':
            driver = conformance_driver_with_compact_journal(scope, journal_path,
                expected_scope_hash=expected_scope_hash, block_bytes=block_bytes,
                workers=len(place['workers']) if workers > 0 and place['workers'] else workers,   # one encoder per worker CPU
                block_rows=block_rows, cpus=place['workers'], note=event)
        else:
            driver = SourceConformanceDriver(scope, journal_path, expected_scope_hash=expected_scope_hash)
        stack.callback(driver.close)
        if observation_mode == 'none':
            # item 4: no full-book copy at a group close; a subclass, so c15_builder.py (and the pinned identity) is unchanged
            from research.kalshi.frankie_boss.c15_builder_none import C15BuilderNoObservation
            driver._builder.__class__ = C15BuilderNoObservation
        member_counts = [0] * len(scope.members)
        if opening is not None:
            # the day opens with the prior day's closing book (opening_book.py), set before the first record is applied;
            # the conformance drain replays the prefix chain only, never the book, so the seed is inside its checks
            driver._builder.adapter = opening
        cursor, sessions_seen, stopped, partials, skipped = 0, [], False, [], []
        opening_result, opening_file = None, None
        ingest_cpus.pin_parent()               # the causal sequence on the parent CPU; the encoders hold the others
        if event is not None:
            event(dict(phase='ingestion', records=0, total_records=total))
        for index, (stream, (_, ts_out), member, path) in enumerate(zip(streams, metadata, scope.members, paths)):
            name = member.member_key if source_object == 'member_key' else str(path)
            take = takes.get(member.member_key)
            taken = 0
            # item 5 (Greg, 2026-09-29): many records per decoder call, every per-record check kept (fast_mbo_decode.py)
            records = (fast_mbo_decode.records if fast_decode else mbo_source._records)(stream, pin, ts_out, dbn)
            tail = tails.get(member.member_key)
            if tail is not None:
                # the prior trading day's records of this partition: decoded to reach the cut, never appended or counted;
                # without a prior day's book they are applied to the BOOK ONLY (the warm start), nothing else
                warming = opening is None
                adapter = driver._builder.adapter
                last_skipped, first_flags, snapshots, warm_started = None, None, 0, time.perf_counter()
                for position in range(tail['skip']):
                    last_skipped = next(records, None)
                    if last_skipped is None:
                        raise ValueError(f'{member.member_key} ends inside its declared skip of {tail["skip"]} records')
                    if warming:
                        flags = last_skipped.get('flags')
                        if position == 0:
                            first_flags = flags
                        if type(flags) is int and flags & 32:          # F_SNAPSHOT
                            snapshots += 1
                        adapter.apply(last_skipped, None, name, member.sha256)
                        if event is not None and (position + 1) % 100000 == 0:
                            event(dict(phase='opening_book_warm', records=position + 1, of=tail['skip'],
                                       seconds=round(time.perf_counter() - warm_started, 3)))
                first_taken = next(records, None)
                if first_taken is None:
                    raise ValueError(f'{member.member_key} ends at its skip; the declared take of {tail["take"]} is absent')
                before, after = session(member, last_skipped), session(member, first_taken)
                if after <= before:
                    raise ValueError(f'the declared skip of {member.member_key} does not end at a trading-day boundary '
                                     f'(record {tail["skip"] + 1} is still {after})')
                if opening_descriptor is not None and opening_descriptor.get('status') == 'seeded':
                    end = opening_descriptor.get('prior_end') or {}
                    if (end.get('member_key') != member.member_key or end.get('take') != tail['skip']
                            or opening_descriptor.get('prior_last_session') != before):
                        raise ValueError(f'the opening book ends at {end} (session {opening_descriptor.get("prior_last_session")}); '
                                         f'this day opens after {tail["skip"]} records of {member.member_key} (session {before}): '
                                         'the opening book is not the prior day of this cut')
                skipped.append(dict(member_key=member.member_key, skip=tail['skip'], take=tail['take'],
                                    declared_partition_mbo_records=tail['partition_mbo_records'],
                                    last_skipped_session_id=before, first_session_id=after, boundary='trading_day'))
                if warming:
                    adapter.assert_groups_closed()                   # the halt closes every group (declared, now checked)
                    adapter.record_count = 0                         # the day's counts are its own; the book is the book
                    adapter.completed_event_group_count = 0
                    starts = type(first_flags) is int and bool(first_flags & 32)
                    opening_result = dict(status='warmed_from_partition', member_key=member.member_key,
                                          records_applied_to_book=tail['skip'], first_record_flags=first_flags,
                                          snapshot_records=snapshots, starts_with_snapshot=starts,
                                          seconds=round(time.perf_counter() - warm_started, 3),
                                          rule='the prior trading day\'s records of this partition applied to the book only '
                                               '(not journaled, not counted), from its first record to the halt')
                    if not starts:
                        opening_result['listed'] = ('the partition does not open with a book snapshot (F_SNAPSHOT); orders '
                                                    'resting before its first record are not in the book until they '
                                                    'trade, are modified or cancelled')
                else:
                    opening_result = dict(opening_descriptor or {}, status='seeded')
                from research.kalshi.frankie_boss.mbo_resume_state import export_adapter_state
                book_state = export_adapter_state(adapter)
                book_raw = canonical_bytes(pack(book_state))
                book_path = Path(journal_path).parent / 'opening-book.c15.json'
                with book_path.open('xb') as stream:
                    stream.write(book_raw); stream.flush(); os.fsync(stream.fileno())
                opening_file = dict(file=book_path.name, bytes=len(book_raw), sha256=hashlib.sha256(book_raw).hexdigest(),
                                    adapter_state_hash=book_state['state_hash'])
                opening_result.update(file=opening_file, instruments=len(book_state['books']),
                                      resting_orders=sum(len(b['orders']) for b in book_state['books']))
                records = itertools.chain((first_taken,), records)
            for raw in records:
                session_id = session(member, raw)
                if not sessions_seen or sessions_seen[-1][0] != session_id:
                    sessions_seen.append((session_id, cursor, index))
                driver.append(raw, cursor=cursor, source_member_index=index, source_sha256=member.sha256,
                              session_id=session_id, raw_symbol=None, source_dbn_object=name)
                cursor += 1
                taken += 1
                member_counts[index] += 1
                if canary_records is not None and cursor >= canary_records:
                    # the canary stop comes BEFORE the take (the ship review 2026-09-22): a canary of exactly the take once ran
                    # complete() and wrote an ingestion receipt inside a canary directory; a canary verifies no boundary
                    stopped = True
                    break
                if take is not None and taken == take['take']:
                    following = next(records, None)                     # the take ends here; the next record must open a later trading day
                    if following is None:
                        # the manifest declared take < partition count, so a partition that ENDS at the take contradicts its own
                        # declaration and the boundary cannot be verified on a record that does not exist (the ship review 2026-09-22)
                        raise ValueError(f'{member.member_key} ends at its take of {take["take"]} records; the manifest declares '
                                         f'{take["partition_mbo_records"]} in the partition, so the trading-day boundary is unverified')
                    next_session = session(member, following)
                    if next_session <= session_id:
                        raise ValueError(f'the declared take of {member.member_key} does not end at a trading-day boundary '
                                         f'(record {take["take"] + 1} is still {next_session})')
                    partials.append(dict(member_key=member.member_key, take=take['take'],
                                         declared_partition_mbo_records=take['partition_mbo_records'],   # declared: the remainder is never counted
                                         next_session_id=next_session, boundary='trading_day'))
                    break
                if event is not None and (cursor % 10000 == 0 or cursor == total):
                    event(dict(phase='ingestion', records=cursor, total_records=total,
                               seconds=round(time.perf_counter() - started, 3)))
            if stopped:
                break
        ingest_seconds, ingest_cpu = time.perf_counter() - started, time.process_time() - cpu_started
        journal = driver._builder.journal
        worker_cpu = getattr(journal, 'worker_cpu_seconds', 0.0)
        sessions = [dict(session_id=s, first_cursor=c, member_index=m) for s, c, m in sessions_seen]
        if stopped:
            journal_count, head = journal.count, journal.head_hash
            return dict(kind='canary', records=cursor, total_records=total, seconds=round(ingest_seconds, 3),
                        cpu_seconds=round(ingest_cpu, 3), records_per_second=round(cursor / ingest_seconds, 2),
                        ms_per_record=round(1000 * ingest_seconds / cursor, 3),
                        extrapolated_hours_for_total=round(total * ingest_seconds / cursor / 3600, 2),
                        journal_count=journal_count, journal_head_hash=head, sessions=sessions, workers=workers,
                        worker_cpu_seconds=round(worker_cpu, 3), ingested_records=cursor, completion_claimed=False,
                        partial_members=partials, tail_members=skipped, opening_book=opening_result,
                        opening_book_file=opening_file, packing=packing)
        if event is not None:
            event(dict(phase='source_verification', records=cursor, total_records=total))
        verify_started = time.perf_counter()
        early_hash = None
        if verify == 'deferred' and writer == 'compact':
            # item 3 (Greg, 2026-09-29): the seal now, the conformance drain later (--conform on this directory); the
            # completion is the builder's own state, the same fields complete() would claim after the drain
            journal.seal()
            early_hash = _hash_beside(journal_path)          # the receipt's journal_sha256, read beside the next step
            completion, state = parallel_ingest.completion_from(scope, driver._builder, member_counts)
        elif writer == 'compact' and workers > 0:
            # Seal at the writer's tail, then run the one conformance drain through the first run's
            # conformance reader: workers verify every original body and hash, then send only
            # the conformance fields. Full book observations do not cross IPC. The seal
            # states what was written; complete() is the claim, made after it.
            journal.seal()                       # the encoders end here; the reader takes their CPUs
            early_hash = _hash_beside(journal_path)          # the receipt's journal_sha256, read beside the drain

            def drain(n):
                # the first-run reader (not edited) sizes its pinned workers from the calling thread's affinity: built on
                # the whole booking, then the ordered consumer back on the parent CPU (cpus[0], the CPU it reserves).
                # complete() re-derives its claim from the builder and the journal each time (no state is consumed),
                # so a drain whose reader lost a worker is run again with one worker fewer (ingest_cpus.resilient)
                with ingest_cpus.lane_affinity():
                    reader = CompactConformanceReader(journal_path, expected_count=journal.count,
                                                      expected_head_hash=journal.head_hash, workers=n, emit=event)
                ingest_cpus.pin_parent()
                stack.callback(reader.close)
                driver._builder.journal = reader
                return driver.complete()
            completion = ingest_cpus.resilient(drain, workers, note=event, label='conformance reader')
            state = driver._builder.export_state()
        else:
            completion = driver.complete()                 # one full conformance drain, inline
            state = driver._builder.export_state()         # the same state complete() verified, no second drain
            if writer == 'compact':
                journal.seal()
        verify_seconds = time.perf_counter() - verify_started
        result = dict(kind='complete', completion=asdict(completion), completion_digest=completion.digest,
                      state=state, ingest_seconds=round(ingest_seconds, 3), ingest_cpu_seconds=round(ingest_cpu, 3),
                      records_per_second=round(cursor / ingest_seconds, 2),
                      ms_per_record=round(1000 * ingest_seconds / cursor, 3),
                      conformance_seconds=round(verify_seconds, 3), sessions=sessions, records=cursor,
                      conformance='deferred' if (verify == 'deferred' and writer == 'compact') else 'inline',
                      workers=workers, worker_cpu_seconds=round(worker_cpu, 3), partial_members=partials, tail_members=skipped,
                      opening_book=opening_result, opening_book_file=opening_file, packing=packing,
                      journal_sha256_early=early_hash)
        if event is not None:
            event(dict(phase='source_saved', records=cursor, total_records=total, journal_hash=completion.journal_hash))
        return result


def profiled(call, report_path, *, top=40):
    """Run `call` under cProfile (the parent process only; the encoders are separate processes) and file the report:
    the top functions by own time, then by cumulative time. The result of `call` is returned unchanged; profiling
    changes nothing that is written to the journal. Greg, 2026-09-22: the ingest must take minutes, so first measure
    where the parent's 8.9 ms per record go."""
    import cProfile
    import io
    import pstats
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        return call()
    finally:
        profiler.disable()
        out = io.StringIO()
        for key in ('tottime', 'cumulative'):
            out.write(f'### top {top} by {key}\n')
            pstats.Stats(profiler, stream=out).sort_stats(key).print_stats(top)
        Path(report_path).write_text(out.getvalue(), encoding='utf-8')
        print(f'### profile ({report_path})')
        print('\n'.join(line for line in out.getvalue().splitlines()[:top + 12]))


def _boxes(journal_path):
    """The measured box count of a compact container (the outcome beside the packing bounds in the receipt)."""
    db = sqlite3.connect(Path(journal_path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        return next(db.execute('SELECT count(*) FROM blocks'))[0]
    finally:
        db.close()


class _HashBeside:
    """The sealed journal's whole-file sha256 computed on a thread BESIDE the conformance drain (session 5, an idle-CPU
    spot: the receipt's journal_sha256 used to be one more serial read after the drain). The file is sealed (rollback
    journal, every commit done) and only read after; value() returns the digest only if the file's (size, mtime_ns,
    inode) are what they were when the hash started, else None and the caller hashes again (never a stale value)."""

    def __init__(self, path):
        import threading
        self.path, self.digest, self.error = Path(path), None, None
        info = self.path.stat()
        self.key = (info.st_size, info.st_mtime_ns, info.st_ino)
        self.thread = threading.Thread(target=self._run, name='journal-sha256', daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self.digest = sha256_file(self.path)
        except Exception as error:  # noqa: BLE001 - the caller hashes again
            self.error = error

    def value(self):
        self.thread.join()
        info = self.path.stat()
        if self.digest is None or (info.st_size, info.st_mtime_ns, info.st_ino) != self.key:
            return None
        return self.digest


def _journal_sha256(result, journal):
    """The receipt's journal_sha256: the digest hashed beside the drain when the file is unchanged since, else read now."""
    early = result.get('journal_sha256_early')
    value = early.value() if isinstance(early, _HashBeside) else None
    return value or sha256_file(journal)


FILE_CLAIM_SCHEMA = 'FRANKIE_FILE_CLAIM_V2'
FILE_CLAIM_SCHEMAS = ('FRANKIE_FILE_CLAIM_V1', FILE_CLAIM_SCHEMA)      # both read; V2 written (session 8, 2026-10-08)
FILE_CLAIMS_NAME = 'file-claims.jsonl'
CLAIM_TAIL_BYTES = 64 << 10
CLAIM_RULE = ('taken by a later stage only when inode, size, mtime_ns, the filesystem identity and the last 64 KiB '
              'match; else that stage hashes in full')
_FS_IDENTITY_CACHE = {}       # st_dev -> (identity, basis) for this process: a device does not renumber while it runs


def filesystem_identity(path, info=None):
    """(identity, basis) of the filesystem holding `path`: the identity that survives a reboot where st_dev does not
    (session 8, 2026-10-08: a2's two NVMe volumes enumerated in the other order after a restart, root 66305 -> 66306,
    so every FRANKIE_FILE_CLAIM_V1 row failed on st_dev alone and ~1.2 TB fell to "read whole"). In order: the
    filesystem UUID from /dev/disk/by-uuid (the link whose device number is the file's st_dev; basis 'by-uuid'),
    `findmnt -no UUID,SOURCE -T <path>` (basis 'findmnt-uuid', or 'mount-source' when the mount has no UUID), the
    mount's source from /proc/self/mounts (basis 'mount-source'), else 'st_dev:<n>' (basis 'st_dev': the old identity,
    recorded as such). Cached per st_dev for the process. Raises only the path's own OSError."""
    info = info or os.stat(path)
    if info.st_dev in _FS_IDENTITY_CACHE:
        return _FS_IDENTITY_CACHE[info.st_dev]
    found = None
    try:
        by_uuid = Path('/dev/disk/by-uuid')
        for link in (sorted(by_uuid.iterdir()) if by_uuid.is_dir() else ()):
            try:
                if os.stat(link).st_rdev == info.st_dev:
                    found = (link.name, 'by-uuid')
                    break
            except OSError:
                continue
    except OSError:
        found = None
    if found is None:
        try:
            out = subprocess.run(['findmnt', '-no', 'UUID,SOURCE', '-T', str(path)], capture_output=True, text=True,
                                 timeout=20)
            fields = out.stdout.split() if out.returncode == 0 else []
            if len(fields) >= 2 and fields[0]:
                found = (fields[0], 'findmnt-uuid')
            elif len(fields) == 1 and fields[0]:
                found = (fields[0], 'mount-source')
        except (OSError, subprocess.SubprocessError, ValueError):
            found = None
    if found is None:
        try:
            best = None
            for line in Path('/proc/self/mounts').read_text().splitlines():
                parts = line.split()
                if len(parts) < 2:
                    continue
                try:
                    if os.stat(parts[1]).st_dev == info.st_dev and (best is None or len(parts[1]) > len(best[1])):
                        best = (parts[0], parts[1])
                except OSError:
                    continue
            if best is not None:
                found = (best[0], 'mount-source')
        except OSError:
            found = None
    if found is None:
        found = ('st_dev:%d' % info.st_dev, 'st_dev')
    _FS_IDENTITY_CACHE[info.st_dev] = found
    return found


def claim_identity(row):
    """(inode, size, mtime_ns) of a claim row of either schema, else None. A V1 row stores stat as
    [st_dev, ino, size, mtime_ns]; a V2 row as [ino, size, mtime_ns] with the filesystem under fs_uuid."""
    if not isinstance(row, dict) or row.get('schema') not in FILE_CLAIM_SCHEMAS:
        return None
    stat = row.get('stat')
    if not isinstance(stat, list) or not all(type(v) is int for v in stat):
        return None
    if row['schema'] == 'FRANKIE_FILE_CLAIM_V1' and len(stat) == 4:
        return (stat[1], stat[2], stat[3])
    if row['schema'] == FILE_CLAIM_SCHEMA and len(stat) == 3:
        return (stat[0], stat[1], stat[2])
    return None


def _claim_tail(path, info):
    with Path(path).open('rb') as handle:
        handle.seek(max(0, info.st_size - CLAIM_TAIL_BYTES))
        return handle.read()


def file_claim(path, bytes_, sha256, claimed_by):
    """One FRANKIE_FILE_CLAIM_V2 row for a sealed file this step measured whole: its path, bytes and sha256 (the claim)
    plus the file's identity now (inode, size, mtime_ns, and the filesystem's identity under fs_uuid / fs_basis,
    filesystem_identity) and the sha256 of its last 64 KiB. Dedupe pass 2026-10-08: a later stage that would hash the
    same unchanged file again (the data export pins every linked file from byte 0) may take this claim when the
    identity and the tail still match, exactly ROOT's unchanged-file rule (frankie_box_boss_session._resume_row_spool:
    claim + stat + last line) and the export's own after-save rule; anything else is one full pass there. Session 8
    (2026-10-08): st_dev is no longer part of the identity (it renumbers across a reboot); it rides beside the row as
    st_dev_observed, informational only. The claim is a hint: a missing or unreadable claims file costs the full hash,
    never a refusal. Written only after the whole-file hash and the seal; the row names who measured."""
    path = Path(path)
    info = path.stat()
    if info.st_size != bytes_:
        raise ValueError('file claim refused: %s is %d bytes, the measured claim says %d' % (path, info.st_size, bytes_))
    tail = _claim_tail(path, info)
    fs_uuid, fs_basis = filesystem_identity(path, info)
    return dict(schema=FILE_CLAIM_SCHEMA, path=str(path.resolve()), bytes=bytes_, sha256=sha256,
                stat=[info.st_ino, info.st_size, info.st_mtime_ns], fs_uuid=fs_uuid, fs_basis=fs_basis,
                st_dev_observed=info.st_dev, tail_bytes=len(tail),
                tail_sha256=hashlib.sha256(tail).hexdigest(), claimed_by=claimed_by, at=time.time(), rule=CLAIM_RULE)


def claim_still_holds(row, path=None):
    """Whether a saved claim row (either schema) still describes the file at `path` (the row's own path when None):
    inode, size and mtime_ns equal, bytes equal to the size, and the sha256 of the last 64 KiB equal (one 64 KiB read,
    the only read). A V2 row must also sit on the filesystem whose identity it names (fs_uuid). A V1 row (st_dev in
    its identity) is accepted on inode + size + mtime_ns + tail alone, st_dev being renumberable across a reboot, and
    the result carries the same claim rewritten as V2 (`refreshed`) for the caller to persist (refresh_file_claims);
    a tail that differs is never accepted. Returns None when the claim does not hold (the caller reads the file
    whole), else dict(basis='v2' | 'v1-compat', text=<the receipt basis>, refreshed=<V2 row or None>). Never raises."""
    try:
        identity = claim_identity(row)
        if identity is None:
            return None
        path = Path(path if path is not None else row['path'])
        info = path.stat()
        if (info.st_ino, info.st_size, info.st_mtime_ns) != identity or info.st_size != int(row['bytes']):
            return None
        tail = _claim_tail(path, info)
        if (len(tail), hashlib.sha256(tail).hexdigest()) != (row['tail_bytes'], row['tail_sha256']):
            return None
        fs_uuid, fs_basis = filesystem_identity(path, info)
        if row['schema'] == FILE_CLAIM_SCHEMA:
            if row.get('fs_uuid') != fs_uuid:
                return None
            return dict(basis='v2', refreshed=None,
                        text='the saved claim (v2) with its inode, size, mtime_ns, filesystem (%s) and last 64 KiB '
                             'unchanged; not read whole here' % fs_basis)
        refreshed = dict(row, schema=FILE_CLAIM_SCHEMA, stat=[info.st_ino, info.st_size, info.st_mtime_ns],
                         fs_uuid=fs_uuid, fs_basis=fs_basis, st_dev_observed=info.st_dev,
                         upgraded_from='FRANKIE_FILE_CLAIM_V1', upgraded_at=time.time(), rule=CLAIM_RULE)
        return dict(basis='v1-compat', refreshed=refreshed,
                    text='the saved claim (v1-compat: st_dev %s at the seal, %d now, no longer part of the identity) '
                         'with its inode, size, mtime_ns and last 64 KiB unchanged; not read whole here; row rewritten '
                         'as %s on filesystem (%s)' % (row['stat'][0], info.st_dev, FILE_CLAIM_SCHEMA, fs_basis))
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None


_CLAIMS_WRITE_LOCK = threading.Lock()


def _write_claims_atomic(target, data):
    """Temp beside the target, fsync, rename: a reader sees the old file or the new one, never a partial."""
    with _CLAIMS_WRITE_LOCK:
        temporary = target.with_name(target.name + '.pending')
        with temporary.open('wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)


def write_file_claims(directory, rows):
    """<directory>/file-claims.jsonl, one claim row per line (rewritten whole). Returns the receipt note; never raises."""
    target = Path(directory) / FILE_CLAIMS_NAME
    try:
        _write_claims_atomic(target, ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode())
        return dict(file=target.name, schema=FILE_CLAIM_SCHEMA, rows=len(rows), status='written')
    except (OSError, ValueError, TypeError) as error:
        return dict(file=target.name, schema=FILE_CLAIM_SCHEMA, rows=len(rows), status='not_written',
                    reason='%s: %s' % (type(error).__name__, error))


def refresh_file_claims(directory, refreshed):
    """Rewrite <directory>/file-claims.jsonl with every non-V2 row whose path is in `refreshed` ({resolved path: V2
    row}) replaced in place: order kept, every other line byte-for-byte, atomically (_write_claims_atomic). Session 8:
    a V1 row matched on inode/size/mtime_ns/tail is rewritten as V2 so a stale st_dev row never persists for a later
    stage. Nothing is written when no row changes. Returns the note dict; never raises (a failed refresh leaves the old
    file, still readable as V1)."""
    target = Path(directory) / FILE_CLAIMS_NAME
    try:
        lines, out, replaced = target.read_text(encoding='utf-8').splitlines(), [], 0
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                out.append(line + '\n'); continue
            new = refreshed.get(str(row.get('path'))) if isinstance(row, dict) else None
            if new is not None and row.get('schema') != FILE_CLAIM_SCHEMA:
                out.append(json.dumps(new, sort_keys=True) + '\n'); replaced += 1
            else:
                out.append(line + '\n')
        if replaced:
            _write_claims_atomic(target, ''.join(out).encode())
        return dict(file=target.name, schema=FILE_CLAIM_SCHEMA, rows=len(lines), refreshed=replaced, status='written')
    except (OSError, ValueError, TypeError) as error:
        return dict(file=target.name, schema=FILE_CLAIM_SCHEMA, refreshed=0, status='not_written',
                    reason='%s: %s' % (type(error).__name__, error))


def _hash_beside(path):
    try:
        return _HashBeside(path)
    except OSError:
        return None


def _child_default_sigterm():
    import signal
    try:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
    except (ValueError, OSError):
        pass


def write_once(path, value):
    raw = json.dumps(value, indent=1, sort_keys=True, default=str).encode()
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def compare_raw_and_compact(raw_path, compact_path, *, expected_count, expected_head_hash):
    """Row-for-row byte equality of the raw journal and the compact container: ordinal, kind, body, digest."""
    db = sqlite3.connect(Path(raw_path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        raw_rows = db.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal')
        with CompactReader(compact_path, expected_count=expected_count, expected_head_hash=expected_head_hash) as reader:
            compared = 0
            for raw_row, compact_row in zip(raw_rows, reader.rows()):
                if tuple(raw_row) != tuple(compact_row):
                    raise ValueError(f'raw and compact rows differ at ordinal {raw_row[0]}')
                compared += 1
            if next(raw_rows, None) is not None or compared != expected_count:
                raise ValueError('raw journal and compact container hold different row counts')
    finally:
        db.close()
    return compared


def _transport():
    """deploy/aws/box/frankie_box_s3_transport (the ONE shared transport: CRT first, classic fallback, reason recorded)."""
    box = str(ROOT / 'deploy' / 'aws' / 'box')
    if box not in sys.path:
        sys.path.insert(0, box)
    import frankie_box_s3_transport
    return frankie_box_s3_transport


def fetch_sources(manifest, sources_dir, *, env_file, emit=None):
    """--fetch: the members missing (or different) under sources_dir downloaded from the manifest bucket, side by side,
    through frankie_box_s3_transport.download (the CRT transfer client first where awscrt imports, 128 MiB parts x 16;
    the classic multipart client after it; the reason for any fallback on the transport receipt). A member already
    present is hashed again in full (no skip by stat: Greg's open call (c)). Each transport receipt is an event
    (progress.jsonl) and fetch-receipts.json in sources_dir lists them all. The sha256 check is unchanged."""
    if Path(env_file).is_file():
        load_env_file(env_file)
    import boto3
    from concurrent.futures import ThreadPoolExecutor
    T = _transport()
    s3 = boto3.client('s3', region_name='us-east-2')
    receipts = []

    def one(member):
        target = Path(sources_dir) / member['member_key']
        if target.is_file() and target.stat().st_size == member['size_bytes'] and sha256_file(target) == member['sha256']:
            return None, dict(member_key=member['member_key'], status='present', sha256=member['sha256'])
        if target.exists():
            return ('a different file is already at ' + member['member_key'] + '; not overwritten'), dict(
                member_key=member['member_key'], status='refused', reason='different file present')
        key = manifest['prefix'] + '/' + member['member_key']
        target.parent.mkdir(parents=True, exist_ok=True)
        r = T.download(manifest['bucket'], key, str(target), region='us-east-2', expected_bytes=member['size_bytes'],
                       expected_sha256=member['sha256'], client=s3)
        r['member_key'] = member['member_key']
        if r['status'] != 'restored':
            return 'downloaded member refused (%s): %s' % (r.get('reason'), member['member_key']), r
        return None, r
    with ThreadPoolExecutor(max_workers=max(1, min(4, len(manifest['sources'])))) as pool:
        outcomes = list(pool.map(one, manifest['sources']))
    for why, r in outcomes:
        receipts.append(r)
        if emit is not None:
            emit(dict(phase='fetch_member', **{k: v for k, v in r.items() if k not in ('schema',)}))
    try:
        (Path(sources_dir) / ('fetch-receipts-%d.json' % int(time.time()))).write_text(
            json.dumps(dict(schema='BOSS_BLOCK_FETCH_RECEIPTS_V1', manifest_hash=manifest['manifest_hash'],
                            members=receipts), indent=1, sort_keys=True, default=str))
    except OSError:
        pass
    refused = [why for why, _ in outcomes if why]
    if refused:
        raise SystemExit('; '.join(refused))


_PROBE_STAGES = {'ingestion': 'ingest records', 'parallel_pass1': 'pass 1 records', 'opening_book_warm': 'opening book warm',
                 'parallel_pass2': 'pass 2 segments', 'parallel_pass3': 'pass 3 entries', 'source_verification': 'seal + conformance',
                 'source_saved': 'saved'}


def _emitter(output):
    """Every event is a progress.jsonl line (as before) and, for the counted phases, a FRANKIE_WORK_PROBE_V1 progress.json
    beside the journal (session 5, FA-4 pattern: the stage heartbeat frankie_box_stage_progress finds a work probe beside
    the files the tree holds open and computes units/min and its report-only 600 s stall flag). The probe counts are
    stage-local: records for decode / pass 1 / ingest, segments for pass 2, entries for pass 3. A probe that cannot be
    written never changes the ingest (report-only)."""
    probe = [None]

    def work_probe(value):
        stage = _PROBE_STAGES.get(value.get('phase'))
        if stage is None:
            return
        try:
            if probe[0] is None:
                box = str(ROOT / 'deploy' / 'aws' / 'box')
                if box not in sys.path:
                    sys.path.insert(0, box)
                import frankie_box_progress
                probe[0] = frankie_box_progress.Probe(output, phase='ingest')
            if value.get('phase') == 'parallel_pass2':
                done, total = value.get('segment', 0) + 1, None
            elif value.get('phase') == 'parallel_pass3':
                done, total = value.get('entries', 0), None
            else:
                done, total = value.get('records', 0), value.get('total_records')
            if type(done) is int and (total is None or (type(total) is int and total >= done)):
                probe[0].update(stage, done, total, force=value.get('phase') in ('source_verification', 'source_saved'),
                                state='complete' if value.get('phase') == 'source_saved' else 'running')
        except Exception:  # noqa: BLE001 - the probe never changes the ingest
            pass

    def emit(value):
        value = dict(value, unix=round(time.time(), 3))
        line = json.dumps(value, sort_keys=True, default=str)
        print(line, flush=True)
        with (output / 'progress.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(line + '\n')
        work_probe(value)
    return emit


def conform_directory(directory, *, workers):
    """Item 3's later half: the conformance drain on a sealed ingest whose conformance was deferred; writes
    conformance.json beside it (the completion the drain claims, and whether it equals completion.json). The day's
    manifest is the committed one whose hash the receipt names."""
    receipt = json.loads((directory / 'ingestion-receipt.json').read_bytes())
    _, manifest = opening_books._manifest_by_hash(receipt['manifest_hash'])
    scope = block_source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])
    raw = (directory / 'builder-checkpoint.c15.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt['checkpoint_sha256']:
        raise SystemExit('the builder checkpoint differs from the receipt')
    state = unpack(json.loads(raw))
    started = time.perf_counter()
    emit = _emitter(directory)
    emit(ingest_cpus.record(max(1, workers)))
    completion, verified = ingest_cpus.resilient(
        lambda n: parallel_ingest.conform(scope, directory / receipt['journal_file'], state, workers=n, emit=emit),
        max(1, workers), note=emit, label='conformance reader')
    claimed = json.loads((directory / 'completion.json').read_bytes())
    same = all(claimed.get(k) == v for k, v in asdict(completion).items() if k != 'member_counts') \
        and list(claimed.get('member_counts') or []) == list(completion.member_counts)
    result = dict(schema='BOSS_BLOCK_INGESTION_CONFORMANCE_V1', completion=asdict(completion), completion_digest=completion.digest,
                  state_hash=verified['state_hash'], equals_deferred_completion=same, seconds=round(time.perf_counter() - started, 3),
                  at=int(time.time()))
    write_once(directory / 'conformance.json', result)
    print(json.dumps(dict(status='conformed' if same else 'CONFORMANCE_DIFFERS', directory=str(directory), **result), default=str))
    return 0 if same else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--manifest', help='committed block manifest (BOSS_BLOCK_SOURCE_MANIFEST_V1)')
    parser.add_argument('--sunday', action='store_true', help='the Sunday single-source scope instead of a block')
    parser.add_argument('--source-path', help='--sunday: the local Sunday DBN file (read only)')
    parser.add_argument('--sources-dir', help='directory holding the block members by member_key')
    parser.add_argument('--fetch', action='store_true', help='download missing members from the manifest bucket')
    parser.add_argument('--env-file', default=str(ROOT / 'scratchpad' / 'aws.env'))
    parser.add_argument('--output-dir')
    parser.add_argument('--session-policy', help='per_member_file | cme_trading_day | constant:<id> (required except with --conform)')
    parser.add_argument('--source-object', choices=('member_key', 'path'), default='member_key')
    parser.add_argument('--writer', choices=('compact', 'raw', 'both'), default='compact')
    parser.add_argument('--canary-records', type=int)
    parser.add_argument('--block-bytes', type=int, default=MAX_BYTES // 2, help='bytes of bodies per box; default the format ceiling')
    parser.add_argument('--block-rows', type=int, help='rows per box; default the standard, partition_entries_for(2 x declared records)')
    parser.add_argument('--workers', type=int, default=0, help='encode blocks on this many spawned processes; 0 = inline')
    parser.add_argument('--opening-receipt',
                        help='the PRIOR trading day\'s sealed ingest receipt (BOSS_BLOCK_INGESTION_RECEIPT_V1, or Monday\'s '
                             'FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1): the day opens with its closing book (opening_book.py). '
                             'Without it a day with a tail member warms its own book from the tail partition (its 00:00Z '
                             'snapshot to the halt), so no prior day needs to be ingested')
    parser.add_argument('--mode', choices=('sequential', 'parallel'), default='sequential',
                        help='parallel (item 2): operations/parallel_ingest.py, three saved passes, 31 workers; needs '
                             '--observation none and the compact writer')
    parser.add_argument('--observation', choices=('full', 'none'), default='full',
                        help='none (item 4, the experiment): no full-book copy at a group close; the book is the INPUT '
                             'records replayed from opening-book.c15.json. full: Frankie\'s journal, as before')
    parser.add_argument('--verify', choices=('inline', 'deferred'), default='inline',
                        help='deferred (item 3): seal and write the completion from the builder state; run the drain later '
                             'with --conform <this directory>')
    parser.add_argument('--resume', action='store_true',
                        help='parallel mode: continue in an existing --output-dir (saved pass 1 and finished segments reused)')
    parser.add_argument('--segment-records', type=int, default=parallel_ingest.SEGMENT_RECORDS)
    parser.add_argument('--conform', help='a sealed ingest directory with conformance deferred: run the drain now, write '
                                          'conformance.json beside it (needs --manifest)')
    parser.add_argument('--profile', action='store_true',
                        help='run the ingest under cProfile and file profile.txt (top functions by own time and by cumulative time) '
                             'in the output directory; a measurement of where the parent\'s time goes, no change to what is written')
    args = parser.parse_args()
    if args.conform:
        return conform_directory(Path(args.conform).resolve(), workers=args.workers)
    if not args.output_dir or not args.session_policy:
        raise SystemExit('--output-dir and --session-policy required')
    output = Path(args.output_dir).resolve()
    if args.canary_records is not None and not any(word in output.name.lower() for word in ('scratch', 'canary')):
        raise SystemExit('a canary output directory must say scratch or canary in its name')
    if args.mode == 'parallel' and (args.observation != 'none' or args.writer != 'compact' or args.canary_records is not None
                                    or args.sunday):
        raise SystemExit('--mode parallel runs the compact writer, --observation none, a block day, no canary')
    if args.resume and args.mode != 'parallel':
        raise SystemExit('--resume is the parallel mode\'s (its passes are saved)')
    if args.resume and (output / 'ingestion-receipt.json').exists():
        raise SystemExit(f'{output} already holds a sealed ingest; nothing to resume')
    output.mkdir(parents=True, exist_ok=args.resume)
    emit = _emitter(output)
    # ROOT's save request route (frankie_box_experiment_root.calculate_day): SIGTERM (the queue's ACTION=save, forwarded
    # by frankie_box_cores.py run) or FRANKIE_LANE_STOP_FILE only MARKS the save; the parallel ingest runs on to its next
    # save point (a pass-1 group-closed state, or a pass-2/3 segment boundary), then exits 75. The sequential writer has
    # no save point (it is canary-or-whole by design), so it keeps the default SIGTERM (a stop = a fresh run), stated.
    requested = [False]
    stop_file = os.environ.get('FRANKIE_LANE_STOP_FILE')

    def save_requested():
        return requested[0] or bool(stop_file and Path(stop_file).exists())
    if args.mode == 'parallel':
        import signal
        signal.signal(signal.SIGTERM, lambda *_: requested.__setitem__(0, True))
        # every forked child (the pinned pass-2/3 pool, its replacements after a dead worker, any helper) starts with
        # the DEFAULT SIGTERM, never the mark-only handler (the a2 shard hang): an at-fork hook runs in each child
        os.register_at_fork(after_in_child=_child_default_sigterm)
        emit(dict(phase='save_route', handler='mark-only SIGTERM', stop_file=stop_file,
                  rule='a save request is honoured at the next save point, then exit 75'))
    else:
        emit(dict(phase='save_route', handler='default SIGTERM', rule='the sequential writer has no save point; a stop '
                  'ends it and the day is ingested again from its start (canary-or-whole by design)'))

    if args.sunday:
        if not args.source_path:
            raise SystemExit('--sunday requires --source-path')
        manifest = source_manifest()
        scope = source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])
        paths = (Path(args.source_path),)
        halt = DEFAULT_HALT_UTC_HOUR
        source_label = dict(scope='sunday', member_keys=[m.member_key for m in scope.members])
    else:
        if not args.manifest or not args.sources_dir:
            raise SystemExit('a block run requires --manifest and --sources-dir')
        manifest = json.loads(Path(args.manifest).read_bytes())
        scope = block_source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])
        if args.fetch:
            fetch_sources(manifest, args.sources_dir, env_file=args.env_file, emit=emit)
        paths = tuple(Path(args.sources_dir) / member.member_key for member in scope.members)
        halt = manifest['halt_utc_hour']
        source_label = dict(scope='block', block=manifest['block'], bucket=manifest['bucket'], prefix=manifest['prefix'],
                            member_keys=[m.member_key for m in scope.members])
    policy_name, session = session_policy(args.session_policy, halt_utc_hour=halt)
    takes = partial_takes(manifest, policy_name=policy_name) if not args.sunday else {}
    tails = tail_skips(manifest, policy_name=policy_name) if not args.sunday else {}
    opening, opening_descriptor = None, None
    if args.opening_receipt:
        adapter_state, opening_descriptor = opening_books.load(args.opening_receipt)
        opening_descriptor['used_for'] = 'writer run(s) of this ingest, each restored afresh'
    # without --opening-receipt a day with a tail member warms its own book from the tail partition (ingest())
    pin = mbo_source.MboSourcePin(3, mbo_source.runtime_hash())
    common = dict(schema=None, manifest_hash=manifest['manifest_hash'], scope_hash=scope.genesis_hash(),
                  scope_kind=scope.kind.value, session_policy=policy_name, halt_utc_hour=halt,
                  source_object_naming=args.source_object, extraction_pin=asdict(pin), extraction_hash=pin.digest,
                  total_mbo_records=sum(m.mbo_records for m in scope.members), python=sys.version.split()[0], **source_label,
                  trading_day=manifest.get('trading_day'), partial_members=list(manifest.get('partial_members') or []),
                  tail_members=list(manifest.get('tail_members') or []), opening_book=opening_descriptor,
                  mode=args.mode, observation_mode=args.observation, verify=args.verify)

    writers = ('raw', 'compact') if args.writer == 'both' else (args.writer,)
    results = {}
    for writer in writers:
        directory = output / writer if args.writer == 'both' else output
        directory.mkdir(exist_ok=True)
        journal = directory / ('source.sqlite' if writer == 'raw' else 'journal.compact.sqlite')
        emit(dict(phase='start', writer=writer, journal=str(journal), canary_records=args.canary_records))
        if args.mode == 'parallel':
            total = sum(member.mbo_records for member in scope.members)
            run_ingest = lambda: parallel_ingest.ingest_parallel(
                scope, paths, pin=pin, session=session, source_names=[m.member_key for m in scope.members],
                journal_path=journal, output=directory, takes=takes, tails=tails,
                opening_state=(adapter_state if args.opening_receipt else None), opening_descriptor=opening_descriptor,
                workers=max(1, args.workers), encoders=args.workers, block_rows=args.block_rows or partition_entries_for(2 * total),
                block_bytes=args.block_bytes, verify=args.verify, resume=args.resume, manifest_hash=manifest['manifest_hash'],
                segment_records=args.segment_records, event=emit, save_requested=save_requested)
        else:
            run_ingest = lambda: ingest(scope, paths, expected_scope_hash=scope.genesis_hash(), pin=pin, session=session,
                                        source_object=args.source_object, journal_path=journal, writer=writer,
                                        canary_records=args.canary_records, block_bytes=args.block_bytes, workers=args.workers, event=emit, takes=takes,
                                        block_rows=args.block_rows, tails=tails, opening_descriptor=opening_descriptor,
                                        opening=(opening_adapter(adapter_state) if args.opening_receipt else None),
                                        observation_mode=args.observation, verify=args.verify)
        try:
            if args.profile:
                result = profiled(run_ingest, directory / 'profile.txt')
            else:
                result = run_ingest()
        except parallel_ingest.IngestSaved as saved:
            # ROOT's route (frankie_box_experiment_root.calculate_day -> TeacherSaved -> exit 75): the save was honoured
            # at a save point; the directory is the resume point (RESUME_DIR=<it> / --resume); exit 75 is never a
            # failure and never a requeue of a fresh day
            record = dict(schema='BOSS_BLOCK_INGESTION_SAVED_V1', at=round(time.time(), 3), directory=str(directory),
                          where=saved.where, resume='ACTION=ingest MODE=parallel RESUME_DIR=%s' % directory)
            write_once(directory / ('ingest-saved-%d.json' % int(time.time())), record)
            emit(dict(phase='saved', **saved.where))
            print('INGEST_SAVED ' + json.dumps(record, sort_keys=True, default=str), flush=True)
            return 75
        results[writer] = result
        if result['kind'] == 'canary':
            receipt = dict(common, schema=CANARY_SCHEMA, writer=writer, **{k: v for k, v in result.items() if k != 'kind'})
            write_once(directory / 'canary-receipt.json', receipt)
            emit(dict(phase='canary_done', writer=writer, records_per_second=result['records_per_second'],
                      ms_per_record=result['ms_per_record'], extrapolated_hours_for_total=result['extrapolated_hours_for_total']))
            continue
        state = result['state']
        checkpoint_raw = canonical_bytes(pack(state))
        checkpoint = directory / 'builder-checkpoint.c15.json'
        if args.resume and checkpoint.exists():          # an attempt that stopped between its checkpoint and its receipt
            checkpoint.rename(checkpoint.with_name(checkpoint.name + f'.stopped-{int(time.time())}'))
            for stale in ('completion.json',):
                if (directory / stale).exists():
                    (directory / stale).rename(directory / f'{stale}.stopped-{int(time.time())}')
        with checkpoint.open('xb') as stream:
            stream.write(checkpoint_raw); stream.flush(); os.fsync(stream.fileno())
        write_once(directory / 'completion.json', dict(result['completion'], conformance=result.get('conformance', 'inline')))
        journal_sha256 = _journal_sha256(result, journal)
        # dedupe pass 2026-10-08: the sealed journal's claim (bytes, sha256, stat, last 64 KiB) beside the receipt, for the
        # stages that pin the same unchanged file again (file_claim); additive, a hint only, never a refusal
        try:
            file_claims = write_file_claims(directory, [file_claim(journal, journal.stat().st_size, journal_sha256,
                                                                   'ingest_block_sources (hashed whole beside the drain)')])
        except (OSError, ValueError) as error:
            file_claims = dict(file=FILE_CLAIMS_NAME, schema=FILE_CLAIM_SCHEMA, rows=0, status='not_written',
                               reason='%s: %s' % (type(error).__name__, error))
        receipt = dict(common, schema=RECEIPT_SCHEMA, writer=writer,
                       record_count=result['completion']['record_count'], journal_count=result['completion']['journal_count'],
                       journal_hash=result['completion']['journal_hash'], group_count=result['completion']['group_count'],
                       source_prefix_hash=result['completion']['source_prefix_hash'],
                       completion_digest=result['completion_digest'],
                       checkpoint_sha256=hashlib.sha256(checkpoint_raw).hexdigest(), checkpoint_state_hash=state['state_hash'],
                       journal_file=journal.name, journal_sha256=journal_sha256, journal_bytes=journal.stat().st_size,
                       file_claims=file_claims,
                       ingest_seconds=result['ingest_seconds'], ingest_cpu_seconds=result['ingest_cpu_seconds'],
                       records_per_second=result['records_per_second'], ms_per_record=result['ms_per_record'],
                       conformance_seconds=result['conformance_seconds'], sessions=result['sessions'],
                       partial_members_ingested=result['partial_members'], tail_members_ingested=result['tail_members'],
                       opening_book=result['opening_book'], opening_book_file=result['opening_book_file'],
                       packing=result['packing'], boxes=(_boxes(journal) if writer == 'compact' else None),
                       conformance=result.get('conformance', 'inline'), parallel=result.get('parallel'),
                       ingested_unix=int(time.time()), model_calls=0, training_updates=0)
        write_once(directory / 'ingestion-receipt.json', receipt)
        emit(dict(phase='complete', writer=writer, journal_count=receipt['journal_count'], journal_hash=receipt['journal_hash'],
                  source_prefix_hash=receipt['source_prefix_hash'], group_count=receipt['group_count'],
                  records_per_second=receipt['records_per_second'], conformance_seconds=receipt['conformance_seconds'],
                  journal_bytes=receipt['journal_bytes']))
    if args.writer == 'both' and all(r['kind'] == 'complete' for r in results.values()):
        raw, compact = results['raw'], results['compact']
        compared = compare_raw_and_compact(output / 'raw' / 'source.sqlite', output / 'compact' / 'journal.compact.sqlite',
                                           expected_count=raw['completion']['journal_count'],
                                           expected_head_hash=raw['completion']['journal_hash'])
        proof = dict(schema=PROOF_SCHEMA, rows_compared=compared,
                     same_completion=raw['completion'] == compact['completion'],
                     same_state_hash=raw['state']['state_hash'] == compact['state']['state_hash'],
                     completion=raw['completion'], state_hash=raw['state']['state_hash'],
                     raw_journal_bytes=(output / 'raw' / 'source.sqlite').stat().st_size,
                     compact_bytes=(output / 'compact' / 'journal.compact.sqlite').stat().st_size,
                     raw_ingest_seconds=raw['ingest_seconds'], compact_ingest_seconds=compact['ingest_seconds'])
        if not (proof['same_completion'] and proof['same_state_hash']):
            write_once(output / 'both-ways-proof-FAILED.json', proof)
            raise SystemExit('raw and compact builds differ')
        write_once(output / 'both-ways-proof.json', proof)
        emit(dict(phase='both_ways_proof', **{k: v for k, v in proof.items() if k not in ('completion', 'schema')}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
