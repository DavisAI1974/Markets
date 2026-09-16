"""Ingest a staged multi-day block (or the Sunday day) as ONE continuous stream, straight into the compact container.

The members replay in manifest order with no gap between them, Sunday reopen through the last file,
exactly as the tape ran. Two things the Sunday build did differently are changed here and nothing else:

- the writer: the builder's journal is CompactBuildJournal, so the 2 TB raw journal a 6.47M-record
  block would need is never written; the container is what the Sunday host already reads;
- the session identity: declared per run through --session-policy (Greg's call, review 2.7), because
  DChain and the teacher reset on a session change and the string is inside every journal row:
    per_member_file    one session per UTC day file (what the Sunday build did; the day from the member key)
    cme_trading_day    the CME trading day (Greg, 2026-09-16, standing): a record before the 17:00 ET
                       halt belongs to its date, a record at or after it to the next date, so the 18:00 ET
                       reopen is the next day's evening session; 17:00 ET is 21:00Z under EDT, the manifest
                       declares the halt hour and that every halt boundary closes an F_LAST group
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
import json
import os
import re
import sqlite3
import sys
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
from research.kalshi.frankie_boss.c15_journal import evidence_hash, pack, canonical_bytes  # noqa: E402
from research.kalshi.frankie_boss.compact_build_journal import conformance_driver_with_compact_journal  # noqa: E402
from research.kalshi.frankie_boss.compact_journal import CompactReader                 # noqa: E402
from research.kalshi.frankie_boss.selected_source_scope import source_manifest, source_scope  # noqa: E402
from research.kalshi.frankie_boss.source_conformance import SourceConformanceDriver     # noqa: E402

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
            return day.strftime('%Y%m%d')
        return name, trading_day
    if name.startswith('constant:') and len(name) > len('constant:'):
        literal = name[len('constant:'):]
        return name, lambda member, raw: literal
    raise ValueError('session policy must be per_member_file, cme_trading_day or constant:<id>')


def ingest(scope, paths, *, expected_scope_hash, pin, session, source_object, journal_path,
           writer='compact', canary_records=None, block_bytes=4 * 1024 * 1024, event=None):
    """The ingest_sources loop with a chosen writer, a per-record session policy and member-key naming.

    Returns dict(kind='canary'|'complete', ...). The record decode is mbo_source's pinned extractor,
    untouched; the builder is the lawful C15Builder through SourceConformanceDriver.
    """
    SourceConformanceDriver._check_scope(scope, expected_scope_hash)
    dbn, zstd = mbo_source._check_pin(pin)
    if type(paths) is not tuple or len(paths) != len(scope.members):
        raise ValueError('complete ordered source paths required')
    if writer not in ('compact', 'raw'):
        raise ValueError('writer must be compact or raw')
    if canary_records is not None and (type(canary_records) is not int or canary_records <= 0):
        raise ValueError('canary record count must be a positive integer')
    total = sum(member.mbo_records for member in scope.members)
    started, cpu_started = time.perf_counter(), time.process_time()
    with ExitStack() as stack:
        snapshots = [mbo_source._verified_copy(path, member, stack) for path, member in zip(paths, scope.members)]
        streams = [mbo_source._decompressed(snapshot, zstd, stack) for snapshot in snapshots]
        metadata = [mbo_source._metadata(stream, pin, dbn) for stream in streams]
        if writer == 'compact':
            driver = conformance_driver_with_compact_journal(scope, journal_path,
                expected_scope_hash=expected_scope_hash, block_bytes=block_bytes)
        else:
            driver = SourceConformanceDriver(scope, journal_path, expected_scope_hash=expected_scope_hash)
        stack.callback(driver.close)
        cursor, sessions_seen, stopped = 0, [], False
        if event is not None:
            event(dict(phase='ingestion', records=0, total_records=total))
        for index, (stream, (_, ts_out), member, path) in enumerate(zip(streams, metadata, scope.members, paths)):
            name = member.member_key if source_object == 'member_key' else str(path)
            for raw in mbo_source._records(stream, pin, ts_out, dbn):
                session_id = session(member, raw)
                if not sessions_seen or sessions_seen[-1][0] != session_id:
                    sessions_seen.append((session_id, cursor, index))
                driver.append(raw, cursor=cursor, source_member_index=index, source_sha256=member.sha256,
                              session_id=session_id, raw_symbol=None, source_dbn_object=name)
                cursor += 1
                if event is not None and (cursor % 10000 == 0 or cursor == total):
                    event(dict(phase='ingestion', records=cursor, total_records=total,
                               seconds=round(time.perf_counter() - started, 3)))
                if canary_records is not None and cursor >= canary_records:
                    stopped = True
                    break
            if stopped:
                break
        ingest_seconds, ingest_cpu = time.perf_counter() - started, time.process_time() - cpu_started
        journal = driver._builder.journal
        sessions = [dict(session_id=s, first_cursor=c, member_index=m) for s, c, m in sessions_seen]
        if stopped:
            journal_count, head = journal.count, journal.head_hash
            return dict(kind='canary', records=cursor, total_records=total, seconds=round(ingest_seconds, 3),
                        cpu_seconds=round(ingest_cpu, 3), records_per_second=round(cursor / ingest_seconds, 2),
                        ms_per_record=round(1000 * ingest_seconds / cursor, 3),
                        extrapolated_hours_for_total=round(total * ingest_seconds / cursor / 3600, 2),
                        journal_count=journal_count, journal_head_hash=head, sessions=sessions,
                        ingested_records=cursor, completion_claimed=False)
        if event is not None:
            event(dict(phase='source_verification', records=cursor, total_records=total))
        verify_started = time.perf_counter()
        completion = driver.complete()                     # one full conformance drain
        state = driver._builder.export_state()             # the same state complete() verified, no second drain
        verify_seconds = time.perf_counter() - verify_started
        if writer == 'compact':
            journal.seal()
        result = dict(kind='complete', completion=asdict(completion), completion_digest=completion.digest,
                      state=state, ingest_seconds=round(ingest_seconds, 3), ingest_cpu_seconds=round(ingest_cpu, 3),
                      records_per_second=round(cursor / ingest_seconds, 2),
                      ms_per_record=round(1000 * ingest_seconds / cursor, 3),
                      conformance_seconds=round(verify_seconds, 3), sessions=sessions, records=cursor)
        if event is not None:
            event(dict(phase='source_saved', records=cursor, total_records=total, journal_hash=completion.journal_hash))
        return result


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


def fetch_sources(manifest, sources_dir, *, env_file):
    if Path(env_file).is_file():
        load_env_file(env_file)
    import boto3
    s3 = boto3.client('s3', region_name='us-east-2')
    for member in manifest['sources']:
        target = Path(sources_dir) / member['member_key']
        if target.is_file() and target.stat().st_size == member['size_bytes'] and sha256_file(target) == member['sha256']:
            continue
        key = manifest['prefix'] + '/' + member['member_key']
        target.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(manifest['bucket'], key, str(target))
        if sha256_file(target) != member['sha256']:
            raise SystemExit('downloaded member differs from the manifest: ' + member['member_key'])


def _emitter(output):
    def emit(value):
        value = dict(value, unix=round(time.time(), 3))
        line = json.dumps(value, sort_keys=True)
        print(line, flush=True)
        with (output / 'progress.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(line + '\n')
    return emit


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--manifest', help='committed block manifest (BOSS_BLOCK_SOURCE_MANIFEST_V1)')
    parser.add_argument('--sunday', action='store_true', help='the Sunday single-source scope instead of a block')
    parser.add_argument('--source-path', help='--sunday: the local Sunday DBN file (read only)')
    parser.add_argument('--sources-dir', help='directory holding the block members by member_key')
    parser.add_argument('--fetch', action='store_true', help='download missing members from the manifest bucket')
    parser.add_argument('--env-file', default=str(ROOT / 'scratchpad' / 'aws.env'))
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--session-policy', required=True, help='per_member_file | cme_trading_day | constant:<id>')
    parser.add_argument('--source-object', choices=('member_key', 'path'), default='member_key')
    parser.add_argument('--writer', choices=('compact', 'raw', 'both'), default='compact')
    parser.add_argument('--canary-records', type=int)
    parser.add_argument('--block-bytes', type=int, default=4 * 1024 * 1024)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    if args.canary_records is not None and not any(word in output.name.lower() for word in ('scratch', 'canary')):
        raise SystemExit('a canary output directory must say scratch or canary in its name')
    output.mkdir(parents=True, exist_ok=False)
    emit = _emitter(output)

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
            fetch_sources(manifest, args.sources_dir, env_file=args.env_file)
        paths = tuple(Path(args.sources_dir) / member.member_key for member in scope.members)
        halt = manifest['halt_utc_hour']
        source_label = dict(scope='block', block=manifest['block'], bucket=manifest['bucket'], prefix=manifest['prefix'],
                            member_keys=[m.member_key for m in scope.members])
    policy_name, session = session_policy(args.session_policy, halt_utc_hour=halt)
    pin = mbo_source.MboSourcePin(3, mbo_source.runtime_hash())
    common = dict(schema=None, manifest_hash=manifest['manifest_hash'], scope_hash=scope.genesis_hash(),
                  scope_kind=scope.kind.value, session_policy=policy_name, halt_utc_hour=halt,
                  source_object_naming=args.source_object, extraction_pin=asdict(pin), extraction_hash=pin.digest,
                  total_mbo_records=sum(m.mbo_records for m in scope.members), python=sys.version.split()[0], **source_label)

    writers = ('raw', 'compact') if args.writer == 'both' else (args.writer,)
    results = {}
    for writer in writers:
        directory = output / writer if args.writer == 'both' else output
        directory.mkdir(exist_ok=True)
        journal = directory / ('source.sqlite' if writer == 'raw' else 'journal.compact.sqlite')
        emit(dict(phase='start', writer=writer, journal=str(journal), canary_records=args.canary_records))
        result = ingest(scope, paths, expected_scope_hash=scope.genesis_hash(), pin=pin, session=session,
                        source_object=args.source_object, journal_path=journal, writer=writer,
                        canary_records=args.canary_records, block_bytes=args.block_bytes, event=emit)
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
        with checkpoint.open('xb') as stream:
            stream.write(checkpoint_raw); stream.flush(); os.fsync(stream.fileno())
        write_once(directory / 'completion.json', result['completion'])
        receipt = dict(common, schema=RECEIPT_SCHEMA, writer=writer,
                       record_count=result['completion']['record_count'], journal_count=result['completion']['journal_count'],
                       journal_hash=result['completion']['journal_hash'], group_count=result['completion']['group_count'],
                       source_prefix_hash=result['completion']['source_prefix_hash'],
                       completion_digest=result['completion_digest'],
                       checkpoint_sha256=hashlib.sha256(checkpoint_raw).hexdigest(), checkpoint_state_hash=state['state_hash'],
                       journal_file=journal.name, journal_sha256=sha256_file(journal), journal_bytes=journal.stat().st_size,
                       ingest_seconds=result['ingest_seconds'], ingest_cpu_seconds=result['ingest_cpu_seconds'],
                       records_per_second=result['records_per_second'], ms_per_record=result['ms_per_record'],
                       conformance_seconds=result['conformance_seconds'], sessions=result['sessions'],
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
