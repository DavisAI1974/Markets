"""Exact teacher cursor placement on the existing ROOT frame axis.

Reuse the already-read, source-verified journal columns. A receive-time tie is
not a source identity. Ordered row slots retain intermediate target states;
entity-scoped closing rows retain stable field names across variable-size groups.
The existing component channels use the last available source cursor.
"""
import bisect
import hashlib
import json
from pathlib import Path
import re

SCHEMA = 'FRANKIE_DIPOLE_GROUP_SEARCH_V3'


def binding():
    from research.kalshi.frankie_boss import c15_journal, c15_normalizer
    return dict(schema=SCHEMA, helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                codec_sha256=hashlib.sha256(Path(c15_journal.__file__).read_bytes()).hexdigest(),
                state_sha256=hashlib.sha256(Path(c15_normalizer.__file__).read_bytes()).hexdigest())


def read_columns(day_dir, path, columns, journal_numeric, journal_text, receive_times):
    """Return exact group rows and cursor-aligned components, with row dispositions."""
    from frankie_box_durable import witness
    from research.kalshi.frankie_boss.c15_journal import evidence_hash, unpack
    from research.kalshi.frankie_boss.c15_normalizer import State

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
                    journal_text.get(prefix + 'terminal_prefix_hash'),
                    journal_numeric.get(prefix + 'normalized.publisher_id'),
                    journal_numeric.get(prefix + 'normalized.instrument_id'))
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
            cursor, stamp, digest, publisher, instrument = (values[position] for values in required)
            if any(type(value) is not int for value in (cursor, stamp, publisher, instrument)) or not isinstance(digest, str):
                raise ValueError('APPLIED target provenance is incomplete')
            if closes is not None and closes[position] is not None:
                if boundaries[position] is not None or closes[position] != int(receive_times[position]):
                    raise ValueError('journal target boundary differs from its exact ROOT frame')
                boundaries[position] = cursor
            if cursor in wanted:
                if cursor in original:
                    raise ValueError('teacher cursor has duplicate APPLIED source identities')
                original[cursor] = (position, stamp, digest, publisher, instrument)
    valid_boundaries = [value for value in boundaries if value is not None]
    if valid_boundaries != sorted(set(valid_boundaries)):
        raise ValueError('ROOT source cursor boundaries are not ordered')

    buckets, searched_rows, states, dispositions = {}, 0, {name: {} for name in names}, {}
    closing_rows, closing_slots = {}, {}
    unavailable_raw = {}
    def projection(row, ordinal):
        # Only the numeric view changes. The bound snapshot and its row mappings
        # remain original evidence; absence of a value says nothing about metadata.
        raw = row.get('raw_components')
        if raw is None:
            return row
        projected = dict(raw)
        for name, component in raw.items():
            state = component.get('state')
            if (type(state) is int and state == int(State.PRESENT)
                    or not isinstance(component.get('value'), (int, float))):
                continue
            projected[name] = dict(component, value=None)
            reason = component.get('reason')
            key = json.dumps([name, state, reason], sort_keys=True)
            item = unavailable_raw.setdefault(key, dict(component=name, state=state, reason=reason,
                rows=0, source_ranges=[]))
            item['rows'] += 1
            ranges, cursor = item['source_ranges'], row['cursor']
            # Paired ranges preserve the exact ordinal-to-cursor mapping without
            # listing the same missing observation twice for its closing alias.
            if ranges and ranges[-1]['ordinals'][1] + 1 == ordinal and ranges[-1]['cursors'][1] + 1 == cursor:
                ranges[-1]['ordinals'][1] = ordinal
                ranges[-1]['cursors'][1] = cursor
            else:
                ranges.append(dict(ordinals=[ordinal, ordinal], cursors=[cursor, cursor]))
        return dict(row, raw_components=projected)

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
        position, stamp, digest, publisher, instrument = entry
        if stamp != row['ts_recv_ns'] or digest != row['source_prefix_hash']:
            raise ValueError('Dipole target differs from its exact APPLIED source prefix')
        state = row.get('dstate')
        if state is not None:
            expected = dict(cursor=row['cursor'], ts_recv_ns=stamp, source_prefix_hash=digest,
                            publisher_id=publisher, instrument_id=instrument)
            if (any(state.get(key) != value for key, value in expected.items())
                    or (state.get('status') == 'GROUP_STATE') != (row['cursor'] == boundaries[position])):
                raise ValueError('Dipole DState differs from its exact APPLIED entity or closing cursor')
        projected = projection(row, ordinal)
        buckets.setdefault(position, []).append(projected)
        if row['cursor'] == boundaries[position]:
            # A group's final row changes list position with group length. Give
            # its unchanged fields stable names without replacing intermediate
            # evidence, carrying state forward, or mixing entity identities.
            entity = '%d:%d' % (publisher, instrument)
            closing_rows[position] = {'by_entity': {entity: projected}}
            slot = len(buckets[position]) - 1
            closing_slots[slot] = closing_slots.get(slot, 0) + 1
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
    closing_numeric, closing_text, closing_mixed, closing_count = columns(
        (closing_rows.get(position, {}) for position in range(n)), '')
    if closing_count != n:
        raise ValueError('Dipole closing-row projection changed the ROOT axis length')
    closing_numeric.pop('', None)
    closing_text.pop('', None)
    numeric.update({'dipole.group_close.' + key: values for key, values in closing_numeric.items()})
    text.update({'dipole.group_close.' + key: values for key, values in closing_text.items()})
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
        alias_rule='group rows, entity closing rows and current component channels project the same evidence; '
                   'none is an independent observation or another occurrence')
    report['raw_value_projection'] = dict(unavailable=list(unavailable_raw.values()),
        rule='only raw_components.<name>.value numeric leaves require the producer integer PRESENT state; '
             'other or undeclared states project to None, never measured zero; paired source ordinal/cursor '
             'ranges are inclusive and counted once across positional/closing aliases; original values, states '
             'and reasons remain in the hash-bound snapshot; independent metadata and incomplete-but-PRESENT '
             'values remain available; unplaced rows retain their separate dispositions')
    report['group_close'] = dict(rows=len(closing_rows), absent_frames=n - len(closing_rows),
        original_row_slots=closing_slots, numeric=sorted(closing_numeric), text=sorted(closing_text), mixed=closing_mixed,
        channels='dipole.group_close.by_entity[publisher:instrument].*',
        rule='only the exact APPLIED closing cursor; all original row leaves retained; no as-of fill or interpolation; '
             'other entities and missing closing rows remain absent on the unchanged F_LAST axis')
    report['dstate'] = dict(retained_group_states=sum(
        row.get('dstate', {}).get('status') == 'GROUP_STATE' for row in rows),
        searched_group_states=sum(row['cursor'] in original and row.get('dstate', {}).get('status') == 'GROUP_STATE'
                                  for row in rows),
        status='retained' if any('dstate' in row for row in rows) else 'not_retained_by_this_source',
        representation='exact numerator/denominator leaves for rational fields; no float reconstruction',
        channels='dipole.group.rows[position].dstate.*',
        closing_channels='dipole.group_close.by_entity[publisher:instrument].dstate.*',
        note='same teacher updates as the six target columns; frozen states remain frozen; '
             'NOT_F_LAST rows supply no new state; no independent observation or old-source backfill')
    notes = [dict(source='dipole', reason='teacher rows without exact journal group evidence remain in the bound source; '
                  'no timestamp fallback, tail backfill or synthetic target', dispositions=dispositions)] if searched_rows != len(rows) else []
    if unavailable_raw:
        notes.append(dict(source='dipole', reason='producer-declared unavailable raw numeric values are not observations; '
                          'see sources[dipole].raw_value_projection for exact source cursors, states and reasons'))
    return numeric, text, [report], notes
