"""Physical DBN/member-ledger mapping and later actual BOSS prefix binding.

No market calculations, model calls, data acquisition or receiver modification.
The complete member gzip is streamed once; its small index supports later cutoffs.
Caller pins must come from the frozen source/delivery witnesses, not this output.
"""
import argparse
from contextlib import ExitStack
from dataclasses import asdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import tempfile

from . import mbo_source
from .causal_prefix import SourceMember
from .c15_journal import EvidenceJournal, pack

SCHEMA = 'FRANKIE_SOURCE_MEMBER_MAPPING_V1'
BINDING_SCHEMA = 'FRANKIE_BOSS_BYTE_PREFIX_MAPPING_V1'
ALIASES = {'price': 'price_raw', 'ts_event': 'ts_event_ns', 'ts_recv': 'ts_recv_ns',
           'ts_in_delta': 'ts_in_delta_ns'}
INTEGER_FIELDS = ('publisher_id', 'instrument_id', 'ts_event', 'order_id', 'price',
                  'size', 'flags', 'channel_id', 'ts_recv', 'ts_in_delta', 'sequence')


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _witness(value):
    if (type(value) is not dict or set(value) != {'bytes', 'sha256'}
            or type(value['bytes']) is not int or value['bytes'] <= 0
            or type(value['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', value['sha256'])):
        raise ValueError('independent positive byte count and SHA256 required')
    return dict(value)


def _plain(path):
    path = Path(path)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink() or info.st_nlink != 1
            or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
        raise ValueError('ordinary unlinked evidence file required')
    return path


def _output(path):
    path = Path(path).absolute()
    if path.resolve().is_relative_to(Path(__file__).resolve().parents[3]):
        raise ValueError('mapping output must be outside the executing checkout')
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError('new output and existing parent required')
    return path


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field in physical evidence')
        result[key] = value
    return result


def _load(raw):
    return json.loads(raw, object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


class _HashingReader(io.RawIOBase):
    def __init__(self, source):
        self.source, self.digest, self.size = source, hashlib.sha256(), 0

    def readable(self):
        return True

    def readinto(self, buffer):
        raw = self.source.read(len(buffer))
        buffer[:len(raw)] = raw
        self.digest.update(raw)
        self.size += len(raw)
        return len(raw)


def _action_wire(action, dbn):
    if type(action) is not dict:
        raise ValueError('member action must be an object')
    original = action.get('source_record')
    if type(original) is dict and 'wire_bytes_hex' in original:
        value = original['wire_bytes_hex']
        if type(value) is not str or not re.fullmatch('(?:[0-9a-f]{112}|[0-9a-f]{128})', value):
            raise ValueError('original source wire is malformed')
        return bytes.fromhex(value), 'source_record_wire'
    # The 56-byte MBOMsg header/layout is fixed by the pinned decoder. Every
    # variable field must exist on this action; no row-level/default values fill gaps.
    values = {name: action.get(ALIASES.get(name, name)) for name in INTEGER_FIELDS}
    values.update(action=action.get('action'), side=action.get('side'))
    if (any(type(values[name]) is not int for name in INTEGER_FIELDS)
            or any(type(values[name]) is not str or len(values[name]) != 1 for name in ('action', 'side'))):
        missing = [ALIASES.get(name, name) for name in values if values[name] is None]
        raise ValueError('member lacks complete typed wire fields; missing=' + ','.join(sorted(missing))
                         + '; available=' + ','.join(sorted(action)))
    try:
        values['action'], values['side'] = dbn.Action(values['action']), dbn.Side(values['side'])
        wire = bytes(dbn.MBOMsg(**values))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('member fields cannot be reencoded by pinned MBOMsg') from exc
    if len(wire) != 56:
        raise ValueError('legacy fields do not witness an optional wire tail')
    return wire, 'normalized_fields_reencoded'


def build_mapping(*, source_path, source_member, extraction_pin, member_ledger_path,
                  member_ledger_witness, output_directory, max_line_bytes=256*1024*1024, event=None):
    """Preserve the historical complete single-member mapping contract."""
    if type(source_member) is not SourceMember or source_member.member_index != 0:
        raise ValueError('one explicit source member at index zero required')
    source_member.__post_init__()
    return _build_mapping(sources=((source_path, source_member),), extraction_pin=extraction_pin,
        member_ledger_path=member_ledger_path, member_ledger_witness=member_ledger_witness,
        output_directory=output_directory, max_line_bytes=max_line_bytes, event=event)


def build_scope_mapping(*, source_paths, source_scope, extraction_pin, member_ledger_path,
                        member_ledger_witness, output_directory, max_line_bytes=256*1024*1024, event=None):
    """Map every record in an explicitly declared source scope, including partial physical members.

    Physical files are checked in full against their supplied hashes. Only the
    already-authored per-member record counts select prefixes; no time/row limit
    is invented here. This is source verification, not source ingestion.
    """
    from .causal_prefix import SourceScope
    if type(source_scope) is not SourceScope:
        raise ValueError('explicit typed source scope required')
    source_scope.__post_init__()
    if type(source_paths) not in (tuple, list) or len(source_paths) != len(source_scope.members):
        raise ValueError('one source path per declared member required')
    return _build_mapping(sources=tuple(zip(source_paths, source_scope.members)), source_scope=source_scope,
        extraction_pin=extraction_pin, member_ledger_path=member_ledger_path,
        member_ledger_witness=member_ledger_witness, output_directory=output_directory,
        max_line_bytes=max_line_bytes, event=event)


def _build_mapping(*, sources, extraction_pin, member_ledger_path, member_ledger_witness,
                   output_directory, max_line_bytes, event, source_scope=None):
    """Shared exact physical ledger comparison; a mismatch publishes nothing."""
    output = _output(output_directory)
    sources = tuple((_plain(path), member) for path, member in sources)
    ledger_path = _plain(member_ledger_path)
    total = sum(member.mbo_records for _, member in sources)
    expected = _witness(member_ledger_witness)
    if type(max_line_bytes) is not int or max_line_bytes <= 0:
        raise ValueError('positive line capacity required; oversized rows are refused, not dropped')
    if event is not None and not callable(event):
        raise ValueError('mapping progress callback must be callable')
    dbn, zstd = mbo_source._check_pin(extraction_pin)
    with ExitStack() as stack:
        temporary = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='frankie-map-', dir=output.parent)))
        metadata_hashes = []
        def source_records():
            for path, member in sources:
                with ExitStack() as member_stack:
                    snapshot = mbo_source._verified_copy(path, member, member_stack)
                    stream = mbo_source._decompressed(snapshot, zstd, member_stack)
                    metadata, ts_out = mbo_source._metadata(stream, extraction_pin, dbn)
                    metadata_hashes.append(_sha(metadata))
                    decoded = iter(mbo_source._records(stream, extraction_pin, ts_out, dbn))
                    for _ in range(member.mbo_records):
                        raw = next(decoded, None)
                        if raw is None:
                            raise ValueError('physical source is shorter than declared member')
                        yield member.member_index, raw
                    if source_scope is None and next(decoded, None) is not None:
                        raise ValueError('complete single-member source has extra records')
        records = source_records()
        stack.callback(records.close)
        source_file = stack.enter_context(ledger_path.open('rb'))
        physical = _HashingReader(source_file)
        buffered = stack.enter_context(io.BufferedReader(physical))
        compressed = buffered.peek(2)[:2] == b'\x1f\x8b'
        ledger = stack.enter_context(gzip.GzipFile(fileobj=buffered)) if compressed else buffered
        plain_hash, index_hash = hashlib.sha256(), hashlib.sha256()
        plain_size = cursor = groups = line_number = index_size = 0
        entity, encodings = None, {}
        index = stack.enter_context((temporary/'index.jsonl').open('wb'))
        while raw_line := ledger.readline(max_line_bytes + 1):
            offset = plain_size
            plain_size += len(raw_line)
            plain_hash.update(raw_line)
            line_number += 1
            if len(raw_line) > max_line_bytes or plain_size > expected['bytes']:
                raise ValueError('member physical bytes exceed approved capacity or witness')
            if not raw_line.strip():
                continue
            row = _load(raw_line)
            actions = row.get('raw_actions') if type(row) is dict else None
            if type(actions) is not list or not actions:
                raise ValueError('every member row must retain its complete raw_actions')
            start, hashes, final, group_member = cursor, [], None, None
            for action_index, action in enumerate(actions):
                selected = next(records, None)
                if selected is None:
                    raise ValueError('member ledger contains extra source records')
                member_index, raw = selected
                if group_member is not None and member_index != group_member:
                    raise ValueError('ledger group crosses a source member seam')
                group_member = member_index
                wire, mode = _action_wire(action, dbn)
                if wire != raw['dbn_wire_bytes']:
                    raise ValueError(f'full source wire differs at cursor {cursor}')
                current_entity = (raw['publisher_id'], raw['instrument_id'])
                if entity is not None and current_entity != entity:
                    raise ValueError('single-entity mapping refuses interleaved sources')
                entity = current_entity
                if bool(raw['flags'] & 128) != (action_index == len(actions)-1):
                    raise ValueError('member boundaries differ from physical F_LAST groups')
                encodings[mode] = encodings.get(mode, 0) + 1
                hashes.append(_sha(wire))
                cursor += 1
                final = raw
            record = dict(cursor_start=start, cursor_end=cursor-1, line_number=line_number,
                plain_offset=offset, plain_bytes=len(raw_line), line_sha256=_sha(raw_line),
                wire_sha256=hashes, last_ts_recv_ns=final['ts_recv'], last_ts_event_ns=final['ts_event'])
            if source_scope is not None:
                record['source_member_index'] = group_member
            encoded = _json(record) + b'\n'
            index.write(encoded)
            index_hash.update(encoded)
            index_size += len(encoded)
            groups += 1
            if event is not None:
                event(dict(phase='mapping', plain_bytes=plain_size, records=cursor, groups=groups))
        if (next(records, None) is not None or cursor != total
                or plain_size != expected['bytes'] or plain_hash.hexdigest() != expected['sha256']):
            raise ValueError('complete source/member byte witness or record coverage differs')
        receipt = dict(schema=SCHEMA, source=asdict(sources[0][1]), extraction_pin=asdict(extraction_pin),
            extraction_hash=extraction_pin.digest, metadata_sha256=metadata_hashes[0],
            member_ledger=dict(plain=expected, physical=dict(bytes=physical.size, sha256=physical.digest.hexdigest()),
                               encoding='gzip' if compressed else 'plain'),
            record_count=cursor, group_count=groups, entity=list(entity), encodings=encodings,
            index=dict(path='index.jsonl', bytes=index_size, sha256=index_hash.hexdigest()),
            boss_prefix_bound=False, market_calculations=False)
        if source_scope is not None:
            receipt.pop('source')
            receipt.pop('metadata_sha256')
            receipt.update(schema='FRANKIE_SOURCE_MEMBERS_MAPPING_V2',
                           sources=[asdict(member) for _, member in sources],
                           source_scope=source_scope.public_dict(), metadata_sha256_by_member=metadata_hashes)
        index.close()
        (temporary/'mapping.json').write_bytes(_json(receipt))
        # Both members have closed, fully verified bytes before the output appears.
        output.mkdir()
        for name in ('index.jsonl', 'mapping.json'):
            (temporary/name).replace(output/name)
    return receipt


def _bind_members_prefix(mapping, directory, output, expected_mapping_sha256,
                         boss_journal_path, journal_checkpoint, boss_source, reader_factory):
    """Stream a complete multi-member mapping against an independently pinned journal."""
    from .verified_journal_reader import VerifiedJournalReader
    sources = mapping.get('sources')
    if type(sources) is not list or not sources:
        raise ValueError('ordered source member roster required')
    members = [SourceMember(**member) for member in sources]
    if any(m.member_index != i for i, m in enumerate(members)):
        raise ValueError('source members must retain their original contiguous order')
    total = sum(m.mbo_records for m in members)
    if (mapping.get('record_count') != total or journal_checkpoint['count'] != 2 * total
            or type(mapping.get('group_count')) is not int or mapping['group_count'] < 1
            or boss_source['through_cursor'] >= total):
        raise ValueError('complete source member coverage differs')
    if not re.fullmatch('[0-9a-f]{64}', str(mapping.get('extraction_hash', ''))):
        raise ValueError('pinned source extraction hash required')
    index_pin = _witness({k: mapping['index'][k] for k in ('bytes', 'sha256')})
    ledger_pin = _witness(mapping['member_ledger']['plain'])
    matched = [0] * len(members)
    selected_groups = selected_end = 0

    def indexed_records():
        nonlocal selected_groups, selected_end
        digest, size, cursor, groups, plain_end = hashlib.sha256(), 0, 0, 0, 0
        member_index, member_end = 0, members[0].mbo_records
        with _plain(directory/'index.jsonl').open('rb') as stream:
            for line in stream:
                digest.update(line)
                size += len(line)
                if size > index_pin['bytes']:
                    raise ValueError('mapping index exceeds pinned size')
                row = _load(line)
                while cursor == member_end and member_index + 1 < len(members):
                    member_index += 1
                    member_end += members[member_index].mbo_records
                hashes = row.get('wire_sha256')
                start, end = row.get('cursor_start'), row.get('cursor_end')
                offset, length = row.get('plain_offset'), row.get('plain_bytes')
                if (type(start) is not int or type(end) is not int or start != cursor
                        or type(hashes) is not list or not hashes or end - start + 1 != len(hashes)
                        or row.get('source_member_index') != member_index or end >= member_end
                        or type(offset) is not int or type(length) is not int or length <= 0
                        or offset < plain_end or offset + length > ledger_pin['bytes']):
                    raise ValueError('mapping index member, cursor or physical coverage differs')
                if start <= boss_source['through_cursor'] < end:
                    raise ValueError('BOSS cutoff must be an indexed closed member group')
                plain_end = offset + length
                groups += 1
                if end <= boss_source['through_cursor']:
                    selected_groups += 1
                    selected_end = plain_end
                for ordinal, wire_hash in enumerate(hashes):
                    if type(wire_hash) is not str or not re.fullmatch('[0-9a-f]{64}', wire_hash):
                        raise ValueError('malformed mapped wire digest')
                    yield member_index, wire_hash, ordinal == len(hashes) - 1
                    cursor += 1
        if (size != index_pin['bytes'] or digest.hexdigest() != index_pin['sha256']
                or cursor != total or groups != mapping['group_count']):
            raise ValueError('mapping index bytes or complete source coverage differs')

    records = indexed_records()
    reader_factory = reader_factory or VerifiedJournalReader
    journal = reader_factory(_plain(boss_journal_path), expected_count=journal_checkpoint['count'],
                             expected_head_hash=journal_checkpoint['head_hash'])
    count, pending, terminal = 0, None, None
    try:
        for entry in journal.entries():
            value = entry['payload']
            if entry['kind'] == 'INPUT':
                if pending is not None:
                    raise ValueError('unpaired source journal input')
                pending = value
            elif entry['kind'] == 'APPLIED':
                if (pending is None or value['cursor'] != count or pending['cursor'] != count
                        or pack(pending['record']) != pack(value['raw_record'])):
                    raise ValueError('actual applied input continuity differs')
                expected = next(records, None)
                if expected is None:
                    raise ValueError('journal exceeds complete mapped source')
                member_index, wire_hash, group_end = expected
                record = value['raw_record']
                wire = record.get('dbn_wire_bytes')
                if (type(wire) is not bytes or _sha(wire) != wire_hash
                        or value['source_member_index'] != member_index
                        or value['normalized']['source_dbn_sha256'] != members[member_index].sha256
                        or record.get('dbn_extraction_hash') != mapping['extraction_hash']
                        or bool(record['flags'] & 128) != group_end):
                    raise ValueError('actual BOSS raw bytes, member identity or closed group differs')
                if count <= boss_source['through_cursor']:
                    if record['ts_recv'] > boss_source['as_of'] or record['ts_event'] > boss_source['source_as_of']:
                        raise ValueError('actual BOSS causal clock differs')
                    matched[member_index] += 1
                    terminal = value
                count += 1
                pending = None
            else:
                raise ValueError('failed or unknown source journal entry')
        if (next(records, None) is not None or count != total or pending is not None
                or terminal is None or terminal['receipt'] is None
                or terminal['terminal_prefix_hash'] != boss_source['prefix_hash']):
            raise ValueError('actual BOSS selected prefix is incomplete or differs')
    finally:
        records.close()
        journal.close()
    bound = dict(schema='FRANKIE_BOSS_BYTE_PREFIX_MAPPING_V2', mapping_sha256=expected_mapping_sha256,
        sources=sources, member_ledger=mapping['member_ledger'], index=mapping['index'],
        boss_source=dict(boss_source), journal_checkpoint=dict(journal_checkpoint),
        matched_records=sum(matched), matched_records_by_member=matched, matched_groups=selected_groups,
        selected_member_plain_end=selected_end, market_calculations=False,
        mapping_status='EXACT_WIRE_BYTES_AND_ACTUAL_BOSS_PREFIX')
    with output.open('xb') as handle:
        handle.write(_json(bound))
    return bound


def bind_prefix(*, mapping_directory, expected_mapping_sha256, boss_journal_path,
                journal_checkpoint, boss_source, output_path, reader_factory=None):
    """Bind a closed selected member prefix to actual independently pinned journal bytes.

    Original DBN and large member ledger are not opened again. Complete journal
    hash verification remains required even when a smaller causal prefix is selected.
    """
    output = _output(output_path)
    directory = Path(mapping_directory)
    raw = _plain(directory/'mapping.json').read_bytes()
    if _sha(raw) != expected_mapping_sha256:
        raise ValueError('mapping differs from independent pin')
    mapping = _load(raw)
    if mapping.get('schema') not in (SCHEMA, 'FRANKIE_SOURCE_MEMBERS_MAPPING_V2') or mapping.get('boss_prefix_bound') is not False:
        raise ValueError('complete source/member mapping required')
    source_keys = {'prefix_hash', 'through_cursor', 'as_of', 'source_as_of', 'arm_hash'}
    if (type(boss_source) is not dict or set(boss_source) != source_keys
            or any(type(boss_source[k]) is not int or boss_source[k] < 0 for k in ('through_cursor', 'as_of', 'source_as_of'))
            or any(type(boss_source[k]) is not str or not re.fullmatch('[0-9a-f]{64}', boss_source[k]) for k in ('prefix_hash', 'arm_hash'))
            or boss_source['source_as_of'] > boss_source['as_of']):
        raise ValueError('explicit actual BOSS prefix, clocks and arm required')
    if (type(journal_checkpoint) is not dict or set(journal_checkpoint) != {'count', 'head_hash'}
            or type(journal_checkpoint['count']) is not int or journal_checkpoint['count'] <= 0
            or type(journal_checkpoint['head_hash']) is not str
            or not re.fullmatch('[0-9a-f]{64}', journal_checkpoint['head_hash'])):
        raise ValueError('independently trusted journal checkpoint required')
    if mapping['schema'] == 'FRANKIE_SOURCE_MEMBERS_MAPPING_V2':
        return _bind_members_prefix(mapping, directory, output, expected_mapping_sha256,
                                    boss_journal_path, journal_checkpoint, boss_source, reader_factory)
    if reader_factory is not None:
        raise ValueError('explicit reader factories require the multi-member mapping schema')
    index_raw = _plain(directory/'index.jsonl').read_bytes()
    if (len(index_raw) != mapping['index']['bytes'] or _sha(index_raw) != mapping['index']['sha256']):
        raise ValueError('mapping index physical bytes changed')
    hashes, selected, expected_cursor = [], [], 0
    for line in index_raw.splitlines():
        row = _load(line)
        if row['cursor_start'] != expected_cursor or row['cursor_end']-row['cursor_start']+1 != len(row['wire_sha256']):
            raise ValueError('mapping index cursor continuity differs')
        expected_cursor = row['cursor_end']+1
        if row['cursor_end'] <= boss_source['through_cursor']:
            selected.append(row)
            hashes.extend(row['wire_sha256'])
    if (not selected or selected[-1]['cursor_end'] != boss_source['through_cursor']
            or expected_cursor != mapping['record_count']):
        raise ValueError('BOSS cutoff must be an indexed closed member group')
    journal = EvidenceJournal(_plain(boss_journal_path))
    count, pending, terminal = 0, None, None
    try:
        if (journal.count, journal.head_hash) != (journal_checkpoint['count'], journal_checkpoint['head_hash']):
            raise ValueError('actual journal differs from independent checkpoint')
        for entry in journal.entries():
            value = entry['payload']
            if entry['kind'] == 'INPUT':
                if pending is not None:
                    raise ValueError('unpaired source journal input')
                pending = value
            elif entry['kind'] == 'APPLIED':
                if (pending is None or value['cursor'] != count or pending['cursor'] != count
                        or pack(pending['record']) != pack(value['raw_record'])):
                    raise ValueError('actual applied input continuity differs')
                if count < len(hashes):
                    record = value['raw_record']
                    wire = record.get('dbn_wire_bytes')
                    if (type(wire) is not bytes or _sha(wire) != hashes[count]
                            or value['source_member_index'] != mapping['source']['member_index']
                            or value['normalized']['source_dbn_sha256'] != mapping['source']['sha256']
                            or record.get('dbn_extraction_hash') != mapping['extraction_hash']
                            or record['ts_recv'] > boss_source['as_of']
                            or record['ts_event'] > boss_source['source_as_of']):
                        raise ValueError('actual BOSS raw bytes, extraction or causal clock differs')
                    terminal = value
                count += 1
                pending = None
            else:
                raise ValueError('failed or unknown source journal entry')
        if (pending is not None or count < len(hashes) or terminal is None or terminal['receipt'] is None
                or terminal['terminal_prefix_hash'] != boss_source['prefix_hash']):
            raise ValueError('actual BOSS selected prefix is incomplete or differs')
    finally:
        journal.close()
    bound = dict(schema=BINDING_SCHEMA, mapping_sha256=expected_mapping_sha256,
        source=mapping['source'], member_ledger=mapping['member_ledger'], index=mapping['index'],
        boss_source=dict(boss_source), journal_checkpoint=dict(journal_checkpoint),
        matched_records=len(hashes), matched_groups=len(selected),
        selected_member_plain_end=selected[-1]['plain_offset']+selected[-1]['plain_bytes'],
        market_calculations=False, mapping_status='EXACT_WIRE_BYTES_AND_ACTUAL_BOSS_PREFIX')
    with output.open('xb') as handle:
        handle.write(_json(bound))
    return bound


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build')
    for name in ('source-path', 'source-member', 'extraction-pin', 'member-ledger-path', 'member-ledger-witness', 'output-directory'):
        build.add_argument('--'+name, required=True)
    bind = sub.add_parser('bind')
    for name in ('mapping-directory', 'expected-mapping-sha256', 'boss-journal-path', 'journal-checkpoint', 'boss-source', 'output-path'):
        bind.add_argument('--'+name, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    for name in (('source_member', 'extraction_pin', 'member_ledger_witness') if command == 'build' else ('journal_checkpoint', 'boss_source')):
        args[name] = _load(_plain(args[name]).read_bytes())
    if command == 'build':
        args['source_member'] = SourceMember(**args['source_member'])
        args['extraction_pin'] = mbo_source.MboSourcePin(**args['extraction_pin'])
    result = (build_mapping if command == 'build' else bind_prefix)(**args)
    print(_json(result).decode())


if __name__ == '__main__':
    main()
