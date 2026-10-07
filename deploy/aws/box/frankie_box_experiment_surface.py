"""Lossless search input from the retained journal, ordered by native entry ordinal.

This is an evidence read, not another ingest or adapter pass. Full-book/FIFO fields and byte-valued
fields omitted by the legacy JSON spool are read with the existing verified full-evidence reader.
"""
import json
from pathlib import Path


def journal_axis(day_dir, columns, workers=15):
    import numpy as np
    from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
    ingest = Path(day_dir) / 'ingest'
    receipt = json.loads((ingest / 'ingestion-receipt.json').read_bytes())
    external = json.loads((ingest / 'day-external.json').read_bytes())
    if external['trading_day'] != receipt['trading_day']:
        raise ValueError('external day file does not belong to this journal')
    journal = ingest / receipt['journal_file']
    axis, closed, trades, kinds, inputs = [], [], [], {}, 0
    kind_ordinals = {}
    now = external['open_ns']

    def records(reader):
        nonlocal now, inputs
        for entry in reader.entries():
            ordinal = entry['ordinal']
            if ordinal != len(axis):
                raise ValueError('journal axis ordinal discontinuity')
            kind, payload = entry['kind'], entry.get('payload') or {}
            kinds[kind] = kinds.get(kind, 0) + 1
            kind_ordinals.setdefault(kind, []).append(ordinal)
            record = payload.get('record') or payload.get('raw_record') or payload.get('normalized') or {}
            stamp = record.get('ts_recv')
            if isinstance(stamp, int):
                now = max(now, stamp)
            axis.append(now)
            if kind == 'INPUT':
                inputs += 1
            if kind == 'APPLIED':
                if payload.get('frame') is not None:
                    closed.append(ordinal)
                for row in payload.get('legacy_rows') or []:
                    if row.get('action') in ('T', b'T', 84):
                        trades.append(ordinal)
            # Exact envelope leaves, including every original record field and all resting orders.
            yield {kind: entry}

    with FrankieCompactReader(journal, expected_count=receipt['journal_count'],
                              expected_head_hash=receipt['journal_hash'], workers=workers) as reader:
        num, text, listed, count = columns(records(reader), 'ordinal')
    if inputs != receipt['record_count'] or count != receipt['journal_count']:
        raise ValueError('native axis does not cover the retained ingestion counts')
    source = dict(source='journal', path=str(journal), sha256=receipt['journal_sha256'],
                  rows=count, input_records=inputs, kinds=kinds, numeric=sorted(num), text=sorted(text),
                  listed=listed, ordering='native journal ordinal', groups=len(closed),
                  rule='full evidence reader; every entry/field; no re-ingest, replay, field cap or depth limit')
    return np.asarray(axis, dtype=np.int64), num, text, closed, trades, source, kind_ordinals


def ordinal_values(length, positions, values):
    """A computed group/trade result becomes known at its exact APPLIED ordinal, including timestamp ties."""
    import numpy as np
    if len(positions) != len(values):
        raise ValueError('computed spool cannot be bound to native ordinals: %d results for %d positions' % (
            len(values), len(positions)))
    indices = np.searchsorted(np.asarray(positions, dtype=np.int64), np.arange(length), side='right') - 1
    return np.asarray([values[i] if i >= 0 else None for i in indices], dtype=object)


# The day file's identity columns: ENTITY_COLUMNS partition a table's rows into entities (never pooled); CLOCK_COLUMNS
# (every table) and POINT_CLOCK_COLUMNS (per point) are clocks of a row, carried as identities and clocks, never a numeric
# signal (2026-10-07 night: the rebuilt day files carry event_time_ns on every table and storage.estimate its print_ns).
# A clock is not an entity key: partitioning by it would make every row its own entity.
ENTITY_COLUMNS = frozenset({'model', 'station', 'respondent', 'raw_symbol', 'symbol', 'instrument_id',
                            'publisher_id', 'horizon_days', 'rank', 'target_day', 'contract'})
CLOCK_COLUMNS = frozenset({'event_time_ns'})
POINT_CLOCK_COLUMNS = {'storage.estimate': frozenset({'print_ns'})}


def identity_and_clock_columns(point):
    """Every column of `point` that is an identity or a clock (ENTITY_COLUMNS, CLOCK_COLUMNS, the point's own clocks):
    carried as identities_and_clocks, never searched as a numeric signal. The stamp column is the caller's own check."""
    return ENTITY_COLUMNS | CLOCK_COLUMNS | POINT_CLOCK_COLUMNS.get(point, frozenset())


def external_fields(reader):
    """All table columns at native publication times, partitioned by explicit native entity identifiers.

    The legacy thirteen named series remain aliases. This view additionally carries every other column,
    including states and nested values, without interpreting missing values or pooling entities. The clock columns
    (identity_and_clock_columns) are carried as fields too; a consumer routes them to identities and clocks.
    """
    identity_columns = ENTITY_COLUMNS
    out = {}
    for point in reader.body['points']:
        table = reader.point(point)
        cols = table['columns']
        stamp = cols.index(table['stamp_column'])
        identities = [i for i, name in enumerate(cols) if name in identity_columns]
        grouped = {}
        for row in table['rows']:
            identity = json.dumps([(cols[i], row[i]) for i in identities], sort_keys=True, separators=(',', ':'))
            grouped.setdefault(identity, []).append(row)
        for identity, rows in grouped.items():
            for i, col in enumerate(cols):
                out[point + '.' + col + '.entity=' + identity] = (
                    [row[stamp] for row in rows], [row[i] for row in rows])
    return out


def state_masks(series, cells):
    """Existing exact categorical states plus numeric sign states, evaluated at the predictor's decision row."""
    import numpy as np
    import frankie_box_experiment_transforms as T
    masks = {('whole-day', None): None}
    for name, values in cells.items():
        for value in sorted({v for v in values[1:] if v is not None}, key=str):
            masks[(name, value)] = np.asarray([v == value for v in values[1:]], dtype=bool)
    for name, values in series.items():
        for sign, label in ((-1, 'negative'), (0, 'zero'), (1, 'positive')):
            mask = np.asarray([T.finite(v) and (1 if v > 0 else -1 if v < 0 else 0) == sign
                               for v in values[1:]], dtype=bool)
            if mask.any():
                masks[('state:' + name, label)] = mask
    return masks


SAVE_VALUE_CODE = ('journal_axis', 'ordinal_values', 'ENTITY_COLUMNS', 'CLOCK_COLUMNS', 'POINT_CLOCK_COLUMNS', 'identity_and_clock_columns', 'external_fields', 'state_masks')

def save_identity():
    """This module's value code for a saved search (frankie_box_bedrock.code_identity of the declared definitions, so a
    comment or an unrelated edit never refuses a save; frankie_box_experiment_search's continuation identity V2)."""
    try:
        import frankie_box_bedrock as B
    except ImportError:
        from deploy.aws.box import frankie_box_bedrock as B
    return B.code_identity(__file__, SAVE_VALUE_CODE)
