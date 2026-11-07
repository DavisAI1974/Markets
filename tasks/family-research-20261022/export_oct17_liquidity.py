"""Project a pinned compact ingest from a verified local journal."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/sqlite-triage/20261022/families'
EXPORTS = BASE / 'trade-lifecycle-targeted-v1'
PIN_REF = 'c28a4de13263b6354662cd376fecc7733b47a991'
RUN_ID = '36571235912'
SOURCE_REF = 'af36937d1e478831d4c7bc612c98d969e9a0848b'
DAY = '20231017'
SESSIONS = ('20231003', DAY)


def git_blob(ref, path):
    return subprocess.check_output(['git', 'show', f'{ref}:{path}'], cwd=ROOT)


def load_codec():
    # Load only the reviewed decoder and its stdlib-only dependencies at the ingest commit.
    prefix = '_oct17_ingest_codec'
    package = types.ModuleType(prefix)
    package.__path__ = []
    sys.modules[prefix] = package
    for name in ('causal_packet', 'c15_journal', 'verified_journal_reader', 'compact_journal'):
        path = f'research/kalshi/frankie_boss/{name}.py'
        module = types.ModuleType(f'{prefix}.{name}')
        module.__package__ = prefix
        sys.modules[module.__name__] = module
        exec(compile(git_blob(SOURCE_REF, path), f'{SOURCE_REF}:{path}', 'exec'), module.__dict__)
    return sys.modules[f'{prefix}.compact_journal'], sys.modules[f'{prefix}.c15_journal'].pack


def price_sizes(observation):
    orders = {r['order_id']: r for r in observation['orders']}
    visited, result = set(), {}
    for side in ('B', 'A'):
        levels = {}
        for level in observation['levels'][side]:
            price = level['price_raw']
            ids = level['order_ids']
            if type(price) is not int or price in levels or not ids:
                raise ValueError('invalid or duplicate observed level')
            size = 0
            for oid in ids:
                order = orders[oid]
                qty = order['size']
                if oid in visited or order['side'] != side or order['price_raw'] != price or type(qty) is not int or qty <= 0:
                    raise ValueError('inconsistent observed order membership')
                visited.add(oid)
                size += qty
            levels[price] = (size, len(ids))
        if list(levels) != sorted(levels, reverse=side == 'B'):
            raise ValueError('source levels out of price order')
        result[side] = levels
    if visited != orders.keys() or len(orders) != len(observation['orders']):
        raise ValueError('observed orders not reconciled')
    return result


def view_sides(book, prior):
    result = {}
    for side, levels in book.items():
        old = prior[side] if prior is not None else None
        best = next(iter(levels), None)
        old_best = next(iter(old), None) if old is not None else None
        result[side] = dict(
            best_price_raw=best, full_size=sum(qty for qty, _ in levels.values()), full_level_count=len(levels),
            first_ten=[[p, *level] for p, level in list(levels.items())[:10]],
            prior_best_price_raw=old_best,
            prior_best_size_in_current_full_book=None if old_best is None else levels.get(old_best, (0, 0))[0],
            current_best_size_in_prior_full_book=None if old is None or best is None else old.get(best, (0, 0))[0])
    return result


def project(entries, pack, *, expected_records, expected_groups, expected_day=DAY):
    pending, previous, input_row = {}, {}, None
    records = groups = 0
    for entry, digest in entries:
        kind, payload, ordinal = entry['kind'], entry['payload'], entry['ordinal']
        if kind == 'INPUT' and input_row is None:
            if payload['session_id'] != expected_day or payload['cursor'] != records:
                raise ValueError('source session or cursor disagrees with the pinned ingest')
            input_row = (payload, ordinal, digest)
            continue
        if kind != 'APPLIED' or input_row is None:
            raise ValueError('unexpected journal row or unresolved action; no complete export')
        original, input_ordinal, input_hash = input_row
        input_row = None
        if (payload['input_ordinal'], payload['cursor'], payload['session_id'], payload['source_member_index']) != (
                input_ordinal, records, expected_day, original['source_member_index']) or pack(payload['raw_record']) != pack(original['record']):
            raise ValueError('INPUT and APPLIED bindings differ')
        normalized = payload['normalized']
        iid, event_ns, receive_ns = (normalized[k] for k in ('instrument_id', 'ts_event_ns', 'ts_recv_ns'))
        if any(type(v) is not int for v in (iid, event_ns, receive_ns)):
            raise ValueError('noninteger source identity or clocks')
        ref = [records, input_ordinal, ordinal]
        records += 1
        actions, retained = pending.setdefault(iid, ([], []))
        actions.append(ref)
        effect = payload['effect']
        if normalized['action'] == 'T' or original['record'].get('action') in ('T', b'T') or effect.get('missing_reference'):
            retained.append(dict(reference=ref, input_sha256=input_hash, applied_sha256=digest,
                event_ns=event_ns, receive_ns=receive_ns, source_action=normalized['action'],
                original_tagged=pack({k: payload[k] for k in ('raw_record', 'normalized', 'effect', 'order_before', 'order_after', 'integrity')})))
        receipt, book = payload['receipt'], payload['observation']
        if receipt is None and book is None:
            continue
        if receipt is None or book is None or list(receipt['record_cursors']) != [a[0] for a in actions]:
            raise ValueError('incomplete or mismatched group evidence')
        if (receipt['global_group_ordinal'], receipt['instrument_id'], receipt['terminal_ts_recv_ns'], book['instrument_id']) != (groups, iid, receive_ns, iid):
            raise ValueError('group receipt coordinate disagreement')
        levels = price_sizes(book)
        prior = previous.get(iid)
        row = dict(session_id=expected_day, instrument_id=iid, group_ordinal=groups, input_cursor=ref[0],
            event_ns=event_ns, receive_ns=receive_ns, known_by_ns=receipt['terminal_ts_recv_ns'],
            prior_observed_group_ordinal=None if prior is None else prior[0], source_group_receipt=receipt,
            group_close_applied_sha256=digest, source_observation_integrity=book['integrity'],
            source_action_refs=actions, original_trade_and_missing_reference_rows=retained,
            sides=view_sides(levels, None if prior is None else prior[1]))
        previous[iid] = (groups, levels)
        del pending[iid]
        groups += 1
        yield row
    if input_row is not None or pending or (records, groups) != (expected_records, expected_groups):
        raise ValueError('export did not reach the pinned record/group totals')


def verified_entries(reader, codec):
    last_digest = None

    def tracked_rows():
        nonlocal last_digest
        for row in reader.rows():
            last_digest = row[3]
            yield row

    for envelope in codec.verified_rows(tracked_rows(), reader.count, reader.head_hash):
        yield envelope, last_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('verified_local_sqlite', type=Path, help='Existing authorized read-only journal; never downloaded by this program')
    parser.add_argument('--session', choices=SESSIONS, default=DAY, help='Pinned trading session (default: %(default)s)')
    args = parser.parse_args()
    source = args.verified_local_sqlite.resolve(strict=True)
    day = args.session
    output = EXPORTS / f'oct{day[-2:]}-liquidity-export-v1'
    pin_path = f'ingest_pointers/{day}-gh-{RUN_ID}-1.json'
    pin = json.loads(git_blob(PIN_REF, pin_path))
    receipt = pin['receipt']
    witness, = [f for f in pin['files'] if f['path'] == 'journal.compact.sqlite']
    if (pin['day'], pin['block'], pin['status'], pin['runner']['commit']) != (day, day, 'sealed', SOURCE_REF):
        raise ValueError('unexpected ingest provenance')
    if (receipt['trading_day'], receipt['conformance'], receipt['observation_mode']) != (day, 'inline', 'full'):
        raise ValueError('unexpected ingest receipt')
    if any(Path(str(source) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('closed journal without sidecars required')
    if source.stat().st_size != witness['bytes'] or output.exists():
        raise ValueError('source size differs or output already exists')
    with source.open('rb') as f:
        if hashlib.file_digest(f, 'sha256').hexdigest() != witness['sha256']:
            raise ValueError('source SHA-256 differs from the independently committed pointer')
    codec, pack = load_codec()
    counts = collections.Counter()
    output.mkdir()
    parts = []
    with codec.CompactReader(source, expected_count=receipt['journal_count'], expected_head_hash=receipt['journal_hash']) as reader:
        stream = project(verified_entries(reader, codec), pack, expected_day=day,
                         expected_records=receipt['record_count'], expected_groups=receipt['group_count'])
        part, size = None, 0
        try:
            for row in stream:
                data = (json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n').encode()
                if len(data) > 32 * 1024 * 1024:
                    raise ValueError('single group exceeds part byte budget')
                if part is None or size + len(data) > 32 * 1024 * 1024:
                    if part is not None:
                        part.close()
                    name = f'groups-{len(parts):04d}.jsonl.gz'
                    part = gzip.GzipFile(output / name, mode='wb', mtime=0)
                    parts.append(name)
                    size = 0
                part.write(data)
                size += len(data)
                counts['groups'] += 1
                counts['action_refs'] += len(row['source_action_refs'])
                counts['retained_trade_and_missing_reference_rows'] += len(row['original_trade_and_missing_reference_rows'])
        finally:
            if part is not None:
                part.close()
    (output / 'COMPLETE.json').write_text(json.dumps(dict(
        status='COMPLETE', source_pointer_commit=PIN_REF, source_pointer_path=pin_path, source=pin,
        decoder_commit=SOURCE_REF, parts=parts, counts=dict(counts),
        master='../../completed-run-source-list.json', frankie='../local-liquidity-v1/frankie-local-liquidity-use.json',
        scope='Consecutive source groups, no invented opening transition; source cursor and raw integer clocks retained.',
        semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED'), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
