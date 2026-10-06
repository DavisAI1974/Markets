"""Exact teacher cursor placement on the existing ROOT frame axis.

Reuse the already-read, source-verified journal columns. A receive-time tie is
not a source identity. Ordered row slots retain intermediate target states;
the existing component channels use the last available source cursor.
"""
import bisect
import hashlib
import json
from pathlib import Path
import re

SCHEMA = 'FRANKIE_DIPOLE_GROUP_SEARCH_V1'


def binding():
    from research.kalshi.frankie_boss import c15_journal
    return dict(schema=SCHEMA, helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                codec_sha256=hashlib.sha256(Path(c15_journal.__file__).read_bytes()).hexdigest())


def read_columns(day_dir, path, columns, journal_numeric, journal_text, receive_times):
    """Return exact group rows and cursor-aligned components, with row dispositions."""
    from frankie_box_durable import witness
    from research.kalshi.frankie_boss.c15_journal import evidence_hash, unpack

    day_dir, path = Path(day_dir), Path(path)
    manifest = json.loads((day_dir / 'MANIFEST.json').read_bytes())
    relative = str(path.relative_to(day_dir))
    pins = [item for item in manifest['files']
            if str(Path(item['stage']) / item['path']) == relative]
    if len(pins) != 1:
        raise ValueError('Dipole source is not uniquely bound by the export')
    raw = path.read_bytes()
    if (len(raw) != pins[0]['bytes'] or hashlib.sha256(raw).hexdigest() != pins[0]['sha256']):
        raise ValueError('exported Dipole source changed')
    source = unpack(json.loads(raw))
    if (source.get('schema') != 'DIPOLE_CLASSROOM_SOURCE_V1'
            or source.get('source_snapshot_hash') != evidence_hash(
                {k: v for k, v in source.items() if k != 'source_snapshot_hash'})):
        raise ValueError('Dipole snapshot schema or content identity differs')
    rows, names = source['rows'], list(source['coverage_columns'])
    cursors = [row['cursor'] for row in rows]
    if (any(type(cursor) is not int or cursor < 0 for cursor in cursors)
            or cursors != sorted(set(cursors)) or list(source['context_cursors']) != cursors
            or len(names) != len(set(names)) or source['coverage_count'] != len(names)):
        raise ValueError('Dipole rows or component identities are not exact ordered source members')
    receipts = [item for item in manifest['files']
                if item['stage'] == 'ingest' and Path(item['path']).name == 'ingestion-receipt.json']
    if len(receipts) != 1:
        raise ValueError('Dipole placement requires the selected ingestion receipt')
    pin = receipts[0]
    receipt_path = day_dir / 'ingest' / pin['path']
    if witness(receipt_path) != {key: pin[key] for key in ('bytes', 'sha256')}:
        raise ValueError('Dipole ingestion identity changed')
    receipt = json.loads(receipt_path.read_bytes())
    if (type(source['through_cursor']) is not int or source['through_cursor'] < 0
            or source['through_cursor'] >= receipt['record_count']
            or any(cursor > source['through_cursor'] for cursor in cursors)
            or (source['through_cursor'] == receipt['record_count'] - 1
                and source['source_hash'] != receipt['source_prefix_hash'])):
        raise ValueError('Dipole snapshot names a different source prefix')

    n, wanted = len(receive_times), set(cursors)
    boundaries, original = [None] * n, {}
    slots = sorted((int(match.group(1)), name) for name in journal_text
                   if (match := re.fullmatch(r'journal\.group\.entries\[(\d+)\]\.kind', name)))
    for _, key in slots:
        prefix = key[:-4] + 'payload.'
        required = (journal_numeric.get(prefix + 'cursor'),
                    journal_numeric.get(prefix + 'normalized.ts_recv_ns'),
                    journal_text.get(prefix + 'terminal_prefix_hash'))
        if any(values is None for values in required):
            if 'APPLIED' in journal_text[key]:
                raise ValueError('APPLIED target slot lacks source provenance')
            continue  # This slot contains INPUT only; it has no target-producing APPLIED.
        if any(len(values) != n for values in (journal_text[key], *required)):
            raise ValueError('journal target provenance changed the ROOT axis length')
        closes = journal_numeric.get(prefix + 'frame.ts_recv_ns')
        for position, kind in enumerate(journal_text[key]):
            if kind != 'APPLIED':
                continue
            cursor, stamp, digest = (values[position] for values in required)
            if type(cursor) is not int or type(stamp) is not int or not isinstance(digest, str):
                raise ValueError('APPLIED target provenance is incomplete')
            if closes is not None and closes[position] is not None:
                if boundaries[position] is not None or closes[position] != int(receive_times[position]):
                    raise ValueError('journal target boundary differs from its exact ROOT frame')
                boundaries[position] = cursor
            if cursor in wanted:
                if cursor in original:
                    raise ValueError('teacher cursor has duplicate APPLIED source identities')
                original[cursor] = (position, stamp, digest)
    valid_boundaries = [value for value in boundaries if value is not None]
    if valid_boundaries != sorted(set(valid_boundaries)):
        raise ValueError('ROOT source cursor boundaries are not ordered')

    buckets, searched_rows, states, dispositions = {}, 0, {name: {} for name in names}, {}
    def disposition(reason, ordinal):
        item = dispositions.setdefault(reason, dict(rows=0, ordinal_ranges=[]))
        item['rows'] += 1
        ranges = item['ordinal_ranges']
        if ranges and ranges[-1][1] + 1 == ordinal:
            ranges[-1][1] = ordinal
        else:
            ranges.append([ordinal, ordinal])

    for ordinal, row in enumerate(rows):
        if ([component['name'] for component in row['components']] != names
                or row['source_manifest_hash'] != receipt['manifest_hash']
                or type(row['ts_recv_ns']) is not int or type(row['as_of_ts_recv_ns']) is not int
                or row['as_of_ts_recv_ns'] != row['ts_recv_ns'] or row['ts_recv_ns'] > source['as_of']):
            raise ValueError('Dipole target columns, source manifest or causal clocks differ')
        for component in row['components']:
            counts = states[component['name']]
            state = component['state']
            counts[state] = counts.get(state, 0) + 1
        entry = original.get(row['cursor'])
        if entry is None:
            disposition('no_exact_applied_root_group', ordinal)
            continue
        position, stamp, digest = entry
        if stamp != row['ts_recv_ns'] or digest != row['source_prefix_hash']:
            raise ValueError('Dipole target differs from its exact APPLIED source prefix')
        buckets.setdefault(position, []).append(row)
        searched_rows += 1
        disposition('searched', ordinal)

    numeric, text, mixed, count = columns(
        ({'rows': buckets[position]} if position in buckets else {} for position in range(n)), '')
    if count != n:
        raise ValueError('Dipole group placement changed the ROOT axis length')
    numeric.pop('', None)
    text.pop('', None)
    numeric = {'dipole.group.' + key: values for key, values in numeric.items()}
    text = {'dipole.group.' + key: values for key, values in text.items()}
    current = [bisect.bisect_right(cursors, cursor) - 1 if cursor is not None else -1
               for cursor in boundaries]
    for index, name in enumerate(names):
        components = [rows[i]['components'][index] if i >= 0 and rows[i]['cursor'] in original else None
                      for i in current]
        numeric['dipole.' + name] = [component['value'] if component is not None
            and component['state'] == 'PRESENT' else None for component in components]
        for field, suffix in (('state', '.state'), ('raw_reason', '.reason')):
            text['dipole.' + name + suffix] = [component[field] if component is not None else None
                                              for component in components]
    report = dict(source='dipole', schema=source['schema'], placement_schema=SCHEMA,
        implementation=binding(), path=str(path), rows=len(rows), searched_rows=searched_rows,
        sha256=hashlib.sha256(raw).hexdigest(), through_cursor=source['through_cursor'],
        components=names, states_per_component=states, dispositions=dispositions,
        mixed=mixed, unbound_root_frames=sum(cursor is None for cursor in boundaries),
        note='all exact original target rows on their INPUT group; current components select the latest source cursor '
             'available at each exact frame boundary; equal receive times never select a later cursor',
        alias_rule='group rows and current component channels are projections of the same targets, not independent observations')
    report['dstate'] = dict(retained_group_states=sum(
        row.get('dstate', {}).get('status') == 'GROUP_STATE' for row in rows),
        searched_group_states=sum(row['cursor'] in original and row.get('dstate', {}).get('status') == 'GROUP_STATE'
                                  for row in rows),
        status='retained' if any('dstate' in row for row in rows) else 'not_retained_by_this_source',
        representation='exact numerator/denominator leaves for rational fields; no float reconstruction',
        channels='dipole.group.rows[position].dstate.*',
        note='same teacher updates as the six target columns; frozen states remain frozen; '
             'NOT_F_LAST rows supply no new state; no independent observation or old-source backfill')
    notes = [dict(source='dipole', reason='teacher rows without exact journal group evidence remain in the bound source; '
                  'no timestamp fallback, tail backfill or synthetic target', dispositions=dispositions)] if searched_rows != len(rows) else []
    return numeric, text, [report], notes
