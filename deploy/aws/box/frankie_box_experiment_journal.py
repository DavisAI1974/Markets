"""Whole ingest envelopes on existing ROOT F_LAST rows; no adapter or new axis.

Only INPUT/APPLIED from the selected sealed ingest enter columns. Other entries
and unplaceable groups remain in that exact journal with explicit ordinal ranges.
Original intermediate effects/orders/ranks are evidence; absent full snapshots
are never reconstructed. Pending evidence spans only not-yet-closed ROOT groups.
"""
import hashlib
import json
from pathlib import Path
import re
import sqlite3

SCHEMA = 'FRANKIE_JOURNAL_GROUP_SEARCH_V1'


def binding():
    here = Path(__file__).resolve()
    from frankie_box_market_timeline import binding as timeline_binding
    return dict(schema=SCHEMA, shared_timeline=timeline_binding(),
                helper_sha256=hashlib.sha256(here.read_bytes()).hexdigest(),
                extractor_sha256=hashlib.sha256(here.with_name('frankie_box_boss_session.py').read_bytes()).hexdigest())


def _integer(value):
    return type(value) is int


def _range_add(ranges, ordinal):
    # Dispositions can be decided at group close, after a later unplaced entry.
    # Keep exact ranges; do not assume decision order equals journal order.
    if ranges and ranges[-1][1] + 1 == ordinal:
        ranges[-1][1] = ordinal
    else:
        ranges.append([ordinal, ordinal])


def _frame_index(numeric, receive_times):
    # One shared membership contract for the raw journal and native producer views.
    from frankie_box_market_timeline import frame_index
    return frame_index(numeric, receive_times)


def read_columns(day_dir, columns, frame_numeric, receive_times, *, workers=15, frame_sha256=None):
    """Same-frame numeric/text channels plus exact source/disposition receipts.

    Uses the shared Session INPUT extractor unchanged. Journal ordinals, extracted
    INPUT indices and F_LAST positions remain three distinct identities.
    """
    from frankie_box_durable import witness
    from frankie_box_boss_session import Session
    from research.kalshi.frankie_boss.c15_journal import pack
    from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
    from research.kalshi.frankie_boss.verified_journal_reader import VerifiedJournalReader
    day_dir = Path(day_dir)
    manifest = json.loads((day_dir / 'MANIFEST.json').read_bytes())
    entries = {}
    for item in manifest['files']:
        path = Path(item['path'])
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('export path escapes its selected stage')
        key = (item['stage'], str(path))
        if key in entries:
            raise ValueError('duplicate exported artifact identity')
        entries[key] = item

    def artifact(stage, relative):
        relative = Path(relative)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('journal evidence path escapes selected ingest')
        item = entries.get((stage, str(relative)))
        if item is None:
            return None, None
        path = day_dir / stage / relative
        if any(value.is_symlink() for value in (path, *path.parents)):
            raise ValueError('journal evidence must be an owner-local regular artifact')
        return path, item

    def read_json(stage, relative):
        path, pin = artifact(stage, relative)
        if path is None:
            return None
        if witness(path) != {key: pin[key] for key in ('bytes', 'sha256')}:
            raise ValueError('selected journal metadata changed: ' + str(path))
        return json.loads(path.read_bytes())

    receipt_paths = [path for stage, path in entries
                     if stage == 'ingest' and Path(path).name == 'ingestion-receipt.json']
    if not receipt_paths:
        return {}, {}, [], [dict(source='journal.group', reason='unsupported export: no selected ingest receipt')]
    if len(receipt_paths) != 1:
        raise ValueError('journal search requires one selected ingest receipt')
    receipt = read_json('ingest', receipt_paths[0])
    relative = Path(receipt_paths[0]).parent / receipt['journal_file']
    journal, pin = artifact('ingest', relative)
    if journal is None:
        return {}, {}, [], [dict(source='journal.group', reason='unsupported export: sealed journal is not included')]
    root_binding = read_json('root', 'source-binding.json')
    derive = read_json('root', 'work/derive.json')
    if root_binding is None or derive is None:
        return {}, {}, [], [dict(source='journal.group', retained=str(journal), sha256=pin['sha256'],
                                reason='unsupported export: no complete ROOT source/derivation binding')]
    if (pin['sha256'] != receipt['journal_sha256']
            or root_binding['container']['sha256'] != pin['sha256']
            or root_binding['container']['bytes'] != pin['bytes']
            or root_binding['journal_count'] != receipt['journal_count']
            or root_binding['journal_hash'] != receipt['journal_hash']
            or root_binding['record_count'] != receipt['record_count']
            or derive.get('source_binding') != root_binding
            or str(root_binding['source']['trading_day']) != str(receipt['trading_day'])):
        raise ValueError('selected journal does not belong to this ROOT source')
    if witness(journal) != {key: pin[key] for key in ('bytes', 'sha256')}:
        raise ValueError('selected sealed journal physical bytes changed')
    frames_path, frames_pin = artifact('root', 'work/derived/.rows/frames.jsonl')
    if frames_pin is None:
        return {}, {}, [], [dict(source='journal.group', retained=str(journal), sha256=pin['sha256'],
                                reason='unsupported export: ROOT frame artifact is not manifest-bound')]
    if (witness(frames_path) != {key: frames_pin[key] for key in ('bytes', 'sha256')}
            or frame_sha256 != frames_pin['sha256']):
        raise ValueError('ROOT group membership differs from the selected frame artifact')
    report = dict(source='journal.group', schema=SCHEMA, implementation=binding(), path=str(journal),
                  sha256=pin['sha256'], bytes=pin['bytes'], journal_count=receipt['journal_count'],
                  journal_hash=receipt['journal_hash'], rows=0, searched_rows=0, groups_searched=0,
                  axis_rows=len(receive_times), dispositions={}, frame_dispositions={}, pairing={}, kinds={},
                  evidence_contract=dict(schema='FRANKIE_JOURNAL_EVIDENCE_ROLE_V1',
                      role='original_INPUT_APPLIED_envelopes',
                      artifact_identity=['sha256', 'bytes', 'journal_count', 'journal_hash'],
                      row_identity=['journal_sha256', 'journal_ordinal'],
                      input_identity='shared extractor INPUT index; distinct from journal ordinal and ROOT position',
                      group_identity='manifest-bound frame membership, closing INPUT cursor, instrument and receive time',
                      availability='original closed ROOT group; no new replay, backfill or completed-knowledge gate',
                      consumer='existing same-frame columns; row/frame dispositions state actual use',
                      additional_independent_observation=False),
                  placement='original INPUT ordinal -> exact extracted INPUT index -> original ROOT group membership',
                  observation_rule='original fields only; intermediate missing full-book observations remain None',
                  evidence_alias_rule='journal envelopes, raw records and frame/native projections represent the same evidence, not extra independent observations',
                  frames=dict(path=str(frames_path), bytes=frames_pin['bytes'], sha256=frames_pin['sha256']),
                  entity_rule='ordered group envelope slots retain identities; slots are not persistent entity tracks')
    if root_binding.get('frame_sections_schema') != derive.get('frame_sections_schema'):
        raise ValueError('ROOT frame projection and derivation identities differ')
    frames, owners = _frame_index(frame_numeric, receive_times)
    if frames is None:
        report['dispositions']['unsupported_root_group_membership'] = dict(
            rows=receipt['journal_count'], ordinal_ranges=[[0, receipt['journal_count'] - 1]] if receipt['journal_count'] else [])
        report['rows'] = receipt['journal_count']
        return {}, {}, [report], [dict(source='journal.group', reason='older ROOT has no exact group INPUT membership; source retained')]

    def disposition(reason, ordinal):
        target = report['dispositions'].setdefault(reason, dict(rows=0, ordinal_ranges=[]))
        target['rows'] += 1
        _range_add(target['ordinal_ranges'], ordinal)
        if reason == 'searched':
            report['searched_rows'] += 1

    def pairing(reason, ordinal):
        target = report['pairing'].setdefault(reason, dict(inputs=0, input_journal_ordinal_ranges=[]))
        target['inputs'] += 1
        _range_add(target['input_journal_ordinal_ranges'], ordinal)

    buckets, pending, next_position, extracted, input_count = {}, {}, 0, 0, 0

    def bucket(position):
        return buckets.setdefault(position, dict(entries=[], inputs=set(), input_ordinals=[],
                                                 closing_input_seen=False, closed=False, invalid=None))

    def finish(position):
        item = buckets.pop(position, None)
        if item is not None and any(ordinal in pending for ordinal in item['input_ordinals']):
            item['invalid'] = item['invalid'] or 'group_with_unpaired_input'
        reason = ('no_source_envelope_group' if item is None else
                  item['invalid'] or ('searched' if item['closed'] and item['inputs'] == frames[position]['members']
                                      else 'unclosed_or_incomplete_source_group'))
        target = report['frame_dispositions'].setdefault(reason, dict(frames=0, frame_ordinal_ranges=[]))
        target['frames'] += 1
        _range_add(target['frame_ordinal_ranges'], position)
        if item is None:
            return {}
        for ordinal in item['input_ordinals']:
            if ordinal in pending:
                pairing('unpaired_input_at_group_boundary', ordinal)
                del pending[ordinal]
        for entry in item['entries']:
            disposition(reason, entry['ordinal'])
        if reason == 'searched':
            report['groups_searched'] += 1
            return {'entries': item['entries']}
        return {}

    def aligned(reader):
        nonlocal next_position, extracted, input_count
        for entry in reader.entries():
            ordinal, kind, payload = entry['ordinal'], entry['kind'], entry.get('payload')
            if ordinal != report['rows']:
                raise ValueError('full journal reader changed native entry order')
            report['rows'] += 1
            report['kinds'][kind] = report['kinds'].get(kind, 0) + 1
            if kind == 'INPUT':
                # A following INPUT proves no earlier missing APPLIED may be
                # silently backfilled into an already-closed ROOT boundary.
                while next_position < len(frames) and buckets.get(next_position, {}).get('closing_input_seen'):
                    yield finish(next_position)
                    next_position += 1
                input_count += 1
                observation = Session._find_observation(payload, max_depth=None)
                if observation is None:
                    disposition('input_without_readable_observation', ordinal)
                    continue
                index = extracted
                extracted += 1
                while next_position < len(frames) and frames[next_position]['cursor'] < index:
                    yield finish(next_position)
                    next_position += 1
                position = owners.get(index)
                info = dict(payload=payload, index=index, position=position)
                pending[ordinal] = info
                if position is None:
                    disposition('input_without_root_group', ordinal)
                    continue
                if (position < next_position or not _integer(observation.get('instrument_id'))
                        or observation['instrument_id'] != frames[position]['instrument']):
                    raise ValueError('journal INPUT and ROOT group membership disagree')
                item = bucket(position)
                item['entries'].append(entry)
                item['inputs'].add(index)
                item['input_ordinals'].append(ordinal)
                item['closing_input_seen'] |= index == frames[position]['cursor']
                continue
            if kind not in ('APPLIED', 'FAILED'):
                disposition('unknown_entry_kind_retained', ordinal)
                continue
            input_ordinal = payload.get('input_ordinal') if isinstance(payload, dict) else None
            info = pending.pop(input_ordinal, None) if _integer(input_ordinal) else None
            if info is None:
                disposition('unpaired_' + kind.lower() + '_retained', ordinal)
                continue
            source = info['payload']
            if (not isinstance(source, dict)
                    or not {'record', 'cursor', 'source_member_index', 'session_id'} <= set(source)
                    or not _integer(source['cursor']) or payload.get('cursor') != source['cursor']
                    or (kind == 'APPLIED' and (not {'raw_record', 'cursor', 'source_member_index', 'session_id'} <= set(payload)
                        or pack(payload['raw_record']) != pack(source['record'])
                        or any(payload.get(key) != source.get(key) for key in ('source_member_index', 'session_id'))))):
                disposition('input_pair_identity_mismatch', ordinal)
                pairing('pair_identity_mismatch', input_ordinal)
                if info['position'] is not None:
                    bucket(info['position'])['invalid'] = 'group_with_mismatched_source_pair'
                continue
            pairing(kind.lower(), input_ordinal)
            if kind == 'FAILED':
                disposition('failed_source_record_retained', ordinal)
                if info['position'] is not None:
                    bucket(info['position'])['invalid'] = 'group_with_failed_source_record'
                continue
            position = info['position']
            if position is None or position < next_position:
                disposition('applied_without_open_root_group', ordinal)
                continue
            item, expected = bucket(position), frames[position]
            item['entries'].append(entry)
            normalized = payload.get('normalized')
            if (not isinstance(normalized, dict) or not _integer(normalized.get('instrument_id'))
                    or normalized['instrument_id'] != expected['instrument']):
                item['invalid'] = 'group_with_mismatched_source_instrument'
            frame = payload.get('frame')
            if info['index'] == expected['cursor']:
                item['closed'] = (isinstance(frame, dict)
                                  and _integer(frame.get('instrument_id')) and _integer(frame.get('ts_recv_ns'))
                                  and frame.get('instrument_id') == expected['instrument']
                                  and frame.get('ts_recv_ns') == expected['stamp'])
                if not item['closed']:
                    item['invalid'] = 'group_closing_applied_frame_differs'
            elif frame is not None:
                item['invalid'] = 'group_has_earlier_source_close'
            while next_position < len(frames) and buckets.get(next_position, {}).get('closed'):
                yield finish(next_position)
                next_position += 1
        while next_position < len(frames):
            yield finish(next_position)
            next_position += 1
        for ordinal in pending:
            pairing('unpaired_input_at_source_end', ordinal)
        if (report['rows'] != receipt['journal_count'] or input_count != receipt['record_count']
                or extracted != derive['input_records']
                or sum(value['rows'] for value in report['dispositions'].values()) != report['rows']):
            raise ValueError('journal envelope dispositions do not cover the exact source/ROOT counts')

    db = sqlite3.connect(journal.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        db.close()
    if 'seal' in tables:
        reader = FrankieCompactReader(journal, expected_count=receipt['journal_count'],
                                      expected_head_hash=receipt['journal_hash'], workers=workers)
        report['reader'] = dict(kind='FrankieCompactReader', requested_workers=workers,
                               worker_cpus=list(reader.worker_cpus), coordinator=True)
    elif 'entries' in tables:
        reader = VerifiedJournalReader(journal, expected_count=receipt['journal_count'],
                                       expected_head_hash=receipt['journal_hash'])
        report['reader'] = dict(kind='VerifiedJournalReader', requested_workers=workers,
                               worker_cpus=[], coordinator=True, reason='existing raw journal reader is sequential')
    else:
        raise ValueError('selected journal has no supported sealed evidence layout')
    with reader:
        numeric, text, mixed, count = columns(aligned(reader), '')
    if count != len(frames):
        raise ValueError('journal evidence changed the F_LAST axis length')
    numeric.pop('', None)
    text.pop('', None)
    report.update(numeric=sorted(numeric), text=sorted(text), mixed=mixed)
    return ({'journal.group.' + name: values for name, values in numeric.items()},
            {'journal.group.' + name: values for name, values in text.items()}, [report], [])
