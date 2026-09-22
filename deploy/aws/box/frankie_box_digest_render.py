"""Dense, LOSSLESS render of Frankie's derivation layers (the digest the BOSS reads; Greg, 2026-09-21: shrink every
read, drop nothing; reads cost by the minute).

The first digest (1,344,422 B for cycle 0) spelled every row as prose with 19-digit nanosecond timestamps and field
names repeated on every line, and it printed a SUBSET of each layer's fields with roll20 rounded to 6 decimals. This
render carries EVERY field of every derived layer (work/derived/<layer>.json is the source of truth), exactly:
  - one header line per table (the column names once), then one row per line;
  - integer timestamp columns as deltas from the previous row (`+123456` ; the first row absolute), exact;
  - floats as shortest round-trip decimals (float(repr(x)) == x), None as `-`, booleans as T/F;
  - strings through a per-table dictionary when a value repeats (`@7` = dictionary entry 7), rendered once;
  - nested dicts flattened to dotted columns; lists rendered as JSON.
`parse(text)` inverts the render; `render_layers` checks parse(render(x)) == x for every table before returning, so
the digest is a projection the code can prove, not prose.
DIGEST_V4 (Greg, 2026-09-21 12:2xZ: stack the stacks) adds four exact transforms on top of V3, measured with the pinned
tokenizer on the real tables (run 35603160044): one space between cells instead of a tab when no cell holds a space (the
tokenizer merges a space into the next number, a tab never does: 75.8k -> 57.4k tokens on the book table); k consecutive
`^` or `=` cells as `^k` / `=k`; a float as the exact fraction `n/d` when the IEEE division of those integers IS the float
and the spelling is shorter (1,082 of the 1,101 depth_imbalance_n literals); a per-column power-of-ten scale declared
once when every integer literal of the column is a multiple of it (price_raw_min/max are multiples of 10^6).
roll20 is (b - s) / (b + s) over the trailing window of per-second volumes (native_roll20.roll20): its float is the
IEEE division of two integers, so the per-second table carries the exact fraction `n/d` and the float is recomputed
from it (checked equal to the producer's float for every second).
"""
from __future__ import annotations

import json
import math
import re
from fractions import Fraction

SCHEMA = 'DIGEST_V6'   # V6: the bedrock tables (BR-5, 2026-09-21); V5: the sign of zero is a value (-0.0 never folds into 0.0), tuple cells, a self-checking parser
TABLE_GRAMMAR = 'DIGEST_V5'   # the table block grammar (cells, marks, dictionary, scales): unchanged by V6, which adds tables, not marks
BEDROCK_GROUP_KEY = ('group_index', 'ts_recv_ns', 'f_last_ts_recv_ns')
FRACTION_DENOMINATOR = 1_000_000   # DIGEST_V4: a float spelled n/d only when float(n)/float(d) is that float exactly and the spelling is shorter
SCALE_MIN, SCALE_MAX = 3, 9       # DIGEST_V4: a per-column power of ten every integer literal of the column divides by (declared once, checked)
RUN_MARKS = ('^', '=')            # DIGEST_V4: k consecutive identical mark cells collapse to `^k` / `=k` (never `-`: `-3` is an integer)

DELTA_KEYS = ('ts_recv_ns', 'ts_event_ns', 'ts_recv', 'ts_event', 'second', 'price_raw_min', 'price_raw_max',
              'bid_depth_full', 'ask_depth_full', 'bid_order_count_full', 'ask_order_count_full')
PAIRED = {'ts_event_ns': 'ts_recv_ns', 'ts_event': 'ts_recv'}   # written as `~<offset>` from the paired column of the SAME row
BOOK_FIELDS = ('spread', 'depth_imbalance_full', 'bid_depth_full', 'ask_depth_full', 'bid_order_count_full', 'ask_order_count_full',
               'bid_price_level_count_full', 'ask_price_level_count_full')   # a_memory_member_first_recalculation_20260828.BOOK_FIELDS, in order
# Columns the pinned adapter computes from other columns of the same row (ng_exhaustion_mbo_v4_state_adapter_20260820
# book_snapshot): rendered as `=` when the recomputation equals the stored value exactly, else literal. Exact by check.
DERIVED = {
    'spread': (('best_ask', 'best_bid'), lambda a, b: a - b),
    'mid': (('best_bid', 'best_ask'), lambda b, a: 0.5 * (b + a)),
    'depth_imbalance_full': (('bid_depth_full', 'ask_depth_full'), lambda b, a: None if abs(float(b + a)) < 1e-15 else float(b - a) / float(b + a)),
}
# Columns the pinned structure producer (a_memory_member_first_recalculation_20260828.describe_structure, fill_disposition,
# native_mirror.mirror_identity, canonical_hash; runtime pin 2ebb8ce8) computes from OTHER columns of the same row. Each
# is an ordered (column, function of the flat row) pair; the parser recomputes them in this order, so a rule may read a
# column an earlier rule produced. A rule that raises or disagrees with the stored value leaves the value literal.
_SIDE_SWAP = str.maketrans({'A': 'B', 'B': 'A'})
_DISPOSITION_LISTS = ('fill_disposition.filled_order_ids', 'fill_disposition.cancelled_fill_order_ids', 'fill_disposition.modified_fill_order_ids',
                      'fill_disposition.same_id_cancel_modify_order_ids', 'fill_disposition.unresolved_fill_order_ids')   # subsets of order_ids
_SIGNATURE = ('fill_id_count', 'cancelled_fill_id_count', 'modified_fill_id_count', 'same_id_cancel_modify_count', 'unresolved_fill_id_count')


def _canonical_hash(value):
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')).hexdigest()


def _fill_class(r):
    fills, cancelled, modified = r['fill_disposition.filled_order_ids'], r['fill_disposition.cancelled_fill_order_ids'], r['fill_disposition.modified_fill_order_ids']
    both, unresolved = r['fill_disposition.same_id_cancel_modify_order_ids'], r['fill_disposition.unresolved_fill_order_ids']
    if not fills:
        label = 'NO_FILL_IDS'
    elif both:
        label = 'SAME_ID_CANCEL_AND_MODIFY'
    elif cancelled and modified:
        label = 'SPLIT_CANCEL_MODIFY'
    elif cancelled:
        label = 'CANCEL'
    elif modified:
        label = 'MODIFY'
    else:
        label = 'UNRESOLVED'
    if unresolved and label != 'UNRESOLVED':
        label += '_WITH_UNRESOLVED'
    return label


def _descriptor(r):
    def counts(prefix):
        return {k[len(prefix):]: r[k] for k in r if k.startswith(prefix) and r[k] is not None}
    return {'action_string': r['action_string'], 'side_string': r['side_string'], 'action_counts': counts('action_counts.'),
            'side_counts': counts('side_counts.'), 'terminal_action': r['terminal_action'], 'terminal_side': r['terminal_side'],
            'component_count': r['component_count'], 'distinct_price_count': r['distinct_price_count'],
            'distinct_order_id_count': r['distinct_order_id_count'], 'fill_disposition_signature': {k: r['fill_disposition_signature.' + k] for k in _SIGNATURE}}


def _sign(value):
    if value is None:
        return 'NA'
    return '+' if value > 0 else ('-' if value < 0 else '0')


def _transition(r, prev):
    """book_transition(previous_book, book)['sign_signature']: the sign of each BOOK_FIELD's change from the previous
    frame (row), NA when either side is None or there is no previous row."""
    signs = []
    for key in BOOK_FIELDS:
        left = None if prev is None else prev.get(key)
        right = r.get(key)
        signs.append(f'{key}:{_sign(None if left is None or right is None else right - left)}')
    return '|'.join(signs)


ROW_DERIVED = [
    ('terminal_action', lambda r: r['action_string'][-1]),
    ('terminal_side', lambda r: r['side_string'][-1]),
    ('component_count', lambda r: len(r['action_string'])),
    ('mirror.side_string', lambda r: r['side_string']),
    ('mirror.mirror_side_string', lambda r: r['side_string'].translate(_SIDE_SWAP)),
    ('mirror.mirror_pair_key', lambda r: '|'.join(sorted((r['side_string'], r['side_string'].translate(_SIDE_SWAP))))),
    ('mirror.orientation', lambda r: 'CANONICAL' if r['side_string'] == sorted((r['side_string'], r['side_string'].translate(_SIDE_SWAP)))[0] else 'MIRROR'),
    ('fill_disposition.same_id_cancel_modify_order_ids', lambda r: sorted(set(r['fill_disposition.cancelled_fill_order_ids']) & set(r['fill_disposition.modified_fill_order_ids']))),
    ('fill_disposition_signature.fill_id_count', lambda r: len(r['fill_disposition.filled_order_ids'])),
    ('fill_disposition_signature.cancelled_fill_id_count', lambda r: len(r['fill_disposition.cancelled_fill_order_ids'])),
    ('fill_disposition_signature.modified_fill_id_count', lambda r: len(r['fill_disposition.modified_fill_order_ids'])),
    ('fill_disposition_signature.same_id_cancel_modify_count', lambda r: len(r['fill_disposition.same_id_cancel_modify_order_ids'])),
    ('fill_disposition_signature.unresolved_fill_id_count', lambda r: len(r['fill_disposition.unresolved_fill_order_ids'])),
    ('fill_disposition.class', _fill_class),
] + [('fill_disposition.signature.' + k, (lambda k: lambda r: r['fill_disposition_signature.' + k])(k)) for k in _SIGNATURE] + [
    ('price_raw_span', lambda r: r['price_raw_max'] - r['price_raw_min']),
    ('distinct_order_id_count', lambda r: len(r['order_ids'])),
    ('carried_native_family', lambda r: r['action_string'] if r['matches_carried_native_family'] else None),
    ('discovery_status', lambda r: 'CARRIED_SEED_MATCH' if r['matches_carried_native_family'] else 'OPEN_WORLD_CANDIDATE'),
    ('candidate_family_id', lambda r: 'ow-' + _canonical_hash(_descriptor(r))[:20]),
]
_ROW_DERIVED_INDEX = {c: i for i, (c, _) in enumerate(ROW_DERIVED)}
PREV_DERIVED = {'transition': _transition}   # rules that read this row AND the previous (decoded) row
# Columns equal, row for row, to a column of a table rendered EARLIER in the same digest: the structure groups close on the
# same F_LAST frames as the book table, so their timestamps are the book table's. Declared `=name` in the header when every
# row matches (checked), and the parser copies them from the earlier table.
CROSS_DERIVED = {('legacy_structure_observables', 'ts_recv_ns'): ('legacy_book_imbalance', 'ts_recv_ns'),
                 ('legacy_structure_observables', 'ts_event_ns'): ('legacy_book_imbalance', 'ts_event_ns')}


def _prefix_derived(column, r):
    """action_counts.<c> / side_counts.<c> = the count of the single character <c> in the row's string. The producer
    builds these from a Counter, so the key is present exactly when the count is positive."""
    for prefix, source in (('action_counts.', 'action_string'), ('side_counts.', 'side_string')):
        if column.startswith(prefix):
            key = column[len(prefix):]
            if len(key) == 1 and isinstance(r.get(source), str):
                return True, r[source].count(key)
            return True, None
    return False, None


def _equal_typed(value, stored):
    if isinstance(value, bool) or isinstance(stored, bool):
        return type(value) is type(stored) and value == stored
    if isinstance(value, float) and isinstance(stored, (int, float)):
        return _same(value, float(stored))
    return type(value) is type(stored) and _same(value, stored)


def _recompute(row, column, prev=None):
    spec = DERIVED.get(column)
    if spec:
        keys, fn = spec
        return None if any(row.get(k) is None for k in keys) else fn(*[row[k] for k in keys])
    hit, value = _prefix_derived(column, row)
    if hit:
        return value
    if column in PREV_DERIVED:
        return PREV_DERIVED[column](row, prev)
    return ROW_DERIVED[_ROW_DERIVED_INDEX[column]][1](row)


def _is_derivable(column):
    return column in DERIVED or column in _ROW_DERIVED_INDEX or column in PREV_DERIVED or column.startswith(('action_counts.', 'side_counts.'))


def _derived(row, column, prev=None):
    """True when `column` of this flat row is rendered `=`: the stored value equals the recomputation exactly (for the
    adapter's book columns, a None stored where an input is None also counts, as the adapter writes it)."""
    if not _is_derivable(column):
        return False
    try:
        value = _recompute(row, column, prev)
    except Exception:
        return False
    stored = row.get(column)
    if column in DERIVED and value is None:
        return stored is None
    if column.startswith(('action_counts.', 'side_counts.')):
        return value is not None and value > 0 and _equal_typed(value, stored)
    return (value is None and stored is None) or (stored is not None and _equal_typed(value, stored))


def _absent_is_derived(row, column):
    """A missing count key is the derivation yielding 0 (the producer's Counter holds no zero entries)."""
    if column not in row and column.startswith(('action_counts.', 'side_counts.')):
        hit, value = _prefix_derived(column, row)
        return hit and value == 0
    return False


NONE, TRUE, FALSE, SAME = '-', 'T', 'F', '^'


def _flatten(row, prefix=''):
    out = {}
    for k, v in row.items():
        key = f'{prefix}{k}'
        if isinstance(v, dict):
            out.update(_flatten(v, key + '.'))
        else:
            out[key] = v
    return out


def _int_list(v):
    return isinstance(v, list) and bool(v) and all(isinstance(x, int) and not isinstance(x, bool) for x in v)


def _no_tuples(value):
    if isinstance(value, tuple):
        return False
    if isinstance(value, dict):
        return all(_no_tuples(v) for v in value.values())
    if isinstance(value, list):
        return all(_no_tuples(v) for v in value)
    return True


def _literal(v, column, r, prev_lists):
    """The inline text of a value that is neither derived, repeated from the previous row, nor a delta:
    (kind, text) with kind 'lit' (final), 'str' (a string; dictionary candidate) or 'json' (a JSON cell; candidate)."""
    if v is None:
        return 'lit', NONE
    if v is True:
        return 'lit', TRUE
    if v is False:
        return 'lit', FALSE
    if isinstance(v, int):
        return 'lit', str(v)
    if isinstance(v, float):
        return 'lit', 'nan' if math.isnan(v) else _float_text(v)
    if isinstance(v, str):
        return 'str', v
    if isinstance(v, tuple):
        if not _no_tuples(list(v)):
            raise ValueError('a tuple nested in a tuple has no exact cell')     # render_layers / the caller leaves such a value as it was
        return 'lit', 'U' + json.dumps(list(v), separators=(',', ':'), sort_keys=True)   # DIGEST_V4: a tuple cell, parsed back as a tuple
    if _int_list(v):
        if column in _DISPOSITION_LISTS and _int_list(r.get('order_ids')):
            index, pos = {}, []
            for i, x in enumerate(r['order_ids']):
                index.setdefault(x, i)                                    # first occurrence, one pass (O(n), not ids.index per element)
            for x in v:
                i = index.get(x)
                if i is None or (pos and i <= pos[-1]):
                    break
                pos.append(i)
            else:
                return 'lit', 'K' + ','.join(str(i) for i in pos)      # positions in this row's order_ids
        first = ('%+d' % (v[0] - prev_lists[column])) if isinstance(prev_lists.get(column), int) else str(v[0])
        return 'lit', 'I' + ','.join([first] + ['%+d' % (b - a) for a, b in zip(v, v[1:])])   # first (as a delta from the previous row's first when one exists), then successive differences
    return 'json', json.dumps(v, separators=(',', ':'), sort_keys=True)


def _float_text(v):
    """repr(v), or the exact fraction `n/d` (the IEEE division of two integers that IS this float, checked) when shorter."""
    text = repr(v)
    if math.isfinite(v) and not v.is_integer():
        fr = Fraction(v).limit_denominator(FRACTION_DENOMINATOR)
        if fr.denominator > 1 and float(fr.numerator) / float(fr.denominator) == v:
            frac = '%d/%d' % (fr.numerator, fr.denominator)
            if len(frac) < len(text):
                return frac
    return text


def _plan_row(r, columns, prev_row, prev_values, prev_ints, prev_lists):
    """One row's cells before the dictionary pass: a list of (kind, text) and the state updates."""
    cells = []
    for c in columns:
        if c not in r:
            cells.append(('lit', '=' if _absent_is_derived(r, c) else '?'))
            continue
        v = r[c]
        if _derived(r, c, prev_row):
            cells.append(('lit', '='))
        elif c in prev_values and _same(prev_values[c], v):
            cells.append(('lit', SAME))
        elif c in PAIRED and isinstance(v, int) and not isinstance(v, bool) and isinstance(r.get(PAIRED[c]), int) and not isinstance(r.get(PAIRED[c]), bool):
            cells.append(('lit', '~%+d' % (v - r[PAIRED[c]])))
        elif c.endswith(DELTA_KEYS) and isinstance(v, int) and not isinstance(v, bool) and isinstance(prev_ints.get(c), int):
            cells.append(('lit', '%+d' % (v - prev_ints[c])))
        else:
            cells.append(_literal(v, c, r, prev_lists))
        prev_values[c] = v
        if isinstance(v, int) and not isinstance(v, bool):
            prev_ints[c] = v
        if _int_list(v):
            prev_lists[c] = v[0]
    return cells


def render_table(name, rows, context=None):
    """rows: list of dicts (nested dicts flattened). Returns the text block. Two passes: the first plans every cell and
    counts the strings and JSON cells; the second writes them, a value through the dictionary only when it REPEATS in
    this table (`@n`), inline otherwise (`S<text>` for a string, `J<json>` for a JSON cell). A column derived on EVERY
    row is declared once in the header (`=name`) and omitted from the rows; a column holding one value on every row is
    declared `^name` with its value on the `constants:` line and omitted too."""
    flat = [_flatten(r) for r in rows]
    columns = []
    for r in flat:
        for k in r:
            if k not in columns:
                columns.append(k)
    for k in columns:
        if not k or k[0] in '=^' or '\t' in k or '\n' in k or '=' in k or ' ' in k:
            raise ValueError(f'column name {k!r} cannot be spelled in a table header')
    prev_row, prev_values, prev_ints, prev_lists, planned = None, {}, {}, {}, []
    for r in flat:
        planned.append(_plan_row(r, columns, prev_row, prev_values, prev_ints, prev_lists))
        prev_row = r
    whole = {}
    for j, c in enumerate(columns):
        source = (context or {}).get(CROSS_DERIVED.get((name, c), (None, None))[0])
        if source is not None and len(source) == len(flat) and all(c in r and _same(r[c], _flatten(src).get(CROSS_DERIVED[(name, c)][1], object())) for r, src in zip(flat, source)):
            whole[c] = '='
        elif flat and all(cells[j][1] == '=' for cells in planned):
            whole[c] = '='
        elif flat and all(c in r for r in flat) and all(_same(r[c], flat[0][c]) for r in flat):
            whole[c] = '^'
    kept = [j for j, c in enumerate(columns) if c not in whole]
    counts = {}
    for cells in planned:
        for j in kept:
            kind, text = cells[j]
            if kind != 'lit':
                key = json.dumps(text) if kind == 'str' else text
                counts[key] = counts.get(key, 0) + 1
    scales = _scales(planned, kept, columns)
    dictionary, order, table = {}, [], []
    for cells in planned:
        out = []
        for j in kept:
            kind, text = cells[j]
            if kind == 'lit':
                scale = scales.get(columns[j])
                out.append(_scaled(text, scale) if scale and _INT_CELL.fullmatch(text) else text)
                continue
            key = json.dumps(text) if kind == 'str' else text
            if counts[key] >= 2:
                if key not in dictionary:
                    dictionary[key] = len(order)
                    order.append(key)
                out.append('@%d' % dictionary[key])
            elif kind == 'str':
                out.append(('S' + text) if ('\t' not in text and '\n' not in text) else ('J' + key))
            else:
                out.append('J' + text)
        table.append(_collapse(out))
    sep = ' ' if not any(' ' in cell for row in table for cell in row) else '\t'
    lines = [sep.join(row) for row in table]
    head = [f'### table {name}: {len(rows)} rows, sep={"space" if sep == " " else "tab"}, columns: ' + '\t'.join(whole.get(c, '') + c for c in columns)]
    constants = [c for c in columns if whole.get(c) == '^']
    if constants:
        head.append('constants: ' + '\t'.join('%s=%s' % (c, ('U' + json.dumps(list(flat[0][c]), separators=(',', ':'), sort_keys=True)) if isinstance(flat[0][c], tuple)
                                                       else json.dumps(flat[0][c], separators=(',', ':'), sort_keys=True)) for c in constants))   # a tuple constant keeps its U mark
    if scales:
        head.append('scales: ' + '\t'.join('%s=%d' % (c, k) for c, k in scales.items()))
    if order:
        head.append('dictionary: ' + '\t'.join('@%d=%s' % (i, key) for i, key in enumerate(order)))
    return '\n'.join(head + lines) + '\n'


_INT_CELL = re.compile(r'[+-]?\d+')


def _scales(planned, kept, columns):
    """DIGEST_V4 per-column scale: when every integer literal of a column (absolute or signed delta) is a multiple of
    10^k, k >= SCALE_MIN, the column is declared `scales: name=10^k` once and its cells are written divided by it."""
    scales = {}
    for j in kept:
        k, seen = SCALE_MAX, False
        for cells in planned:
            kind, text = cells[j]
            if kind != 'lit' or not _INT_CELL.fullmatch(text):
                continue
            value = abs(int(text))
            if value == 0:
                seen = True
                continue
            z = 0
            while value % 10 == 0 and z < k:
                value //= 10; z += 1
            k, seen = min(k, z), True
            if k < SCALE_MIN:
                break
        if seen and k >= SCALE_MIN:
            scales[columns[j]] = 10 ** k
    return scales


def _scaled(text, scale):
    value = int(text) // scale if int(text) >= 0 else -((-int(text)) // scale)
    return ('%+d' % value) if text[0] in '+-' else str(value)


def _collapse(cells):
    """DIGEST_V4: k >= 2 consecutive identical `^` or `=` cells become one `^k` / `=k` cell."""
    out, i = [], 0
    while i < len(cells):
        j = i
        while cells[i] in RUN_MARKS and j < len(cells) and cells[j] == cells[i]:
            j += 1
        if j - i >= 2:
            out.append(cells[i] + str(j - i)); i = j
        else:
            out.append(cells[i]); i += 1
    return out


def _expand(cells):
    out = []
    for cell in cells:
        if len(cell) > 1 and cell[0] in RUN_MARKS and cell[1:].isdigit():
            out.extend([cell[0]] * int(cell[1:]))
        else:
            out.append(cell)
    return out


def _derived_order(columns):
    """Derived columns are recomputed after the literal ones: the adapter's book columns and the character counts
    first (they read literals only), then ROW_DERIVED in its declared order (a rule may read an earlier rule), then
    the rules that also read the previous row."""
    first = [c for c in columns if c in DERIVED or c.startswith(('action_counts.', 'side_counts.'))]
    rest = sorted((c for c in columns if c in _ROW_DERIVED_INDEX), key=_ROW_DERIVED_INDEX.get)
    return first + rest + [c for c in columns if c in PREV_DERIVED]


def parse_table(block, context=None):
    import copy
    lines = block.split('\n')
    if lines and lines[-1] == '':
        lines.pop()                        # the block's final newline only; an empty row line (every column constant or derived) stays
    m = re.match(r'### table (\S+): (\d+) rows, (?:sep=(space|tab), )?columns: (.*)$', lines[0])
    if m is None:
        raise ValueError('table header expected')
    name, n = m.group(1), int(m.group(2))
    sep = ' ' if m.group(3) == 'space' else '\t'
    declared = m.group(4).split('\t') if m.group(4) else []
    columns = [c.lstrip('=^') for c in declared]
    whole = {c.lstrip('=^'): c[0] for c in declared if c[:1] in '=^'}
    kept = [c for c in columns if c not in whole]
    idx, constants, dictionary, scales = 1, {}, [], {}
    if idx < len(lines) and lines[idx].startswith('constants: '):
        for item in lines[idx][len('constants: '):].split('\t'):
            k, _, val = item.partition('=')
            constants[k] = tuple(json.loads(val[1:])) if val.startswith('U') else json.loads(val)
        idx += 1
    if idx < len(lines) and lines[idx].startswith('scales: '):
        for item in lines[idx][len('scales: '):].split('\t'):
            k, _, val = item.partition('=')
            scales[k] = int(val)
        idx += 1
    if idx < len(lines) and lines[idx].startswith('dictionary: '):
        for item in lines[idx][len('dictionary: '):].split('\t'):
            k, _, val = item.partition('=')
            dictionary.append(json.loads(val))
        idx += 1
    rows, prev_row, prev_values, prev_ints, prev_lists = [], None, {}, {}, {}
    cross = {c: CROSS_DERIVED[(name, c)] for c, mark in whole.items() if mark == '=' and (name, c) in CROSS_DERIVED and (context or {}).get(CROSS_DERIVED[(name, c)][0]) is not None}
    if len(lines) < idx + n:
        raise ValueError(f'table {name}: {n} rows declared, {len(lines) - idx} present')
    for i, line in enumerate(lines[idx:idx + n]):
        cells = _expand(line.split(sep)) if kept else []
        if len(cells) != len(kept):
            raise ValueError(f'table {name} row {i}: {len(cells)} cells for {len(kept)} columns')
        row, derived_cols, positional, paired = {}, set(c for c, mark in whole.items() if mark == '=' and c not in cross), {}, {}
        for c in constants:
            row[c] = copy.deepcopy(constants[c])
        for c, (table, column) in cross.items():
            row[c] = copy.deepcopy(_flatten(context[table][i])[column])
        for c, cell in zip(kept, cells):
            if cell == '?':
                continue
            if cell == NONE:
                v = None
            elif cell == TRUE:
                v = True
            elif cell == FALSE:
                v = False
            elif cell == '=':
                derived_cols.add(c); continue
            elif cell == SAME:
                v = copy.deepcopy(prev_values[c])
            elif cell.startswith('@'):
                v = copy.deepcopy(dictionary[int(cell[1:])])
            elif cell.startswith('S'):
                v = cell[1:]
            elif cell.startswith('J'):
                v = json.loads(cell[1:])
            elif cell.startswith('U'):
                v = tuple(json.loads(cell[1:]))
            elif cell.startswith('K'):
                positional[c] = [int(i) for i in cell[1:].split(',')] if cell[1:] else []; continue
            elif cell.startswith('I'):
                parts = cell[1:].split(',')
                start = prev_lists[c] + int(parts[0]) if parts[0][:1] in '+-' and isinstance(prev_lists.get(c), int) else int(parts[0])
                v = [start]
                for d in parts[1:]:
                    v.append(v[-1] + int(d))
            elif cell.startswith('~'):
                paired[c] = int(cell[1:]); continue      # resolved once every literal of the row is in, whatever the column order
            elif cell == 'nan':
                v = float('nan')
            elif re.fullmatch(r'-?\d+/\d+', cell):
                num, _, den = cell.partition('/')
                v = float(int(num)) / float(int(den))      # DIGEST_V4 exact fraction: the IEEE division that is the float
            elif cell.startswith('+') or (cell.startswith('-') and c.endswith(DELTA_KEYS) and isinstance(prev_ints.get(c), int) and re.fullmatch(r'-\d+', cell)):
                v = prev_ints[c] + int(cell) * scales.get(c, 1)
            elif re.fullmatch(r'-?\d+', cell):
                v = int(cell) * scales.get(c, 1)
            else:
                v = float(cell)
            row[c] = v
        for c, offset in paired.items():
            if PAIRED[c] not in row:
                raise ValueError(f'table {name} row {i}: {c} is an offset from {PAIRED[c]}, which this row does not carry')
            row[c] = row[PAIRED[c]] + offset
        for c, pos in positional.items():
            row[c] = [row['order_ids'][i] for i in pos]
        for c in _derived_order(columns):
            if c in derived_cols:
                value = _recompute(row, c, prev_row)
                if c.startswith(('action_counts.', 'side_counts.')) and value == 0:
                    continue   # the producer's Counter holds no zero entries: the key is absent
                row[c] = value
        for c, v in row.items():
            prev_values[c] = v
            if isinstance(v, int) and not isinstance(v, bool):
                prev_ints[c] = v
            if _int_list(v):
                prev_lists[c] = v[0]
        rows.append(_unflatten(row))
        prev_row = row
    return name, rows


def _unflatten(flat):
    out = {}
    for k, v in flat.items():
        parts = k.split('.')
        node = out
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = v
    return out


def _same(a, b):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == b and math.copysign(1.0, a) == math.copysign(1.0, b)   # -0.0 is not 0.0: the sign of zero is a value
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return type(a) is type(b) and len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b and type(a) is type(b)


def render_layers(tables):
    """tables: {name: list_of_row_dicts}. Every table is rendered, parsed back and compared; a mismatch raises. The
    tables parsed so far are the context of the next (CROSS_DERIVED), on both sides."""
    out, context = [], {}
    for name, rows in tables.items():
        block = render_table(name, rows, context)
        try:
            parsed_name, parsed = parse_table(block, context)
        except Exception as err:
            raise ValueError(f'digest table {name} does not parse back: {type(err).__name__}: {err}; header: {block.split(chr(10))[0][:400]}') from err
        if parsed_name != name or not _same(parsed, [dict(r) for r in rows]):
            bad = next((k for k, (a, b) in enumerate(zip(parsed, rows)) if not _same(a, dict(b))), None)
            raise ValueError(f'digest table {name} does not round-trip (first differing row {bad} of {len(rows)}; parsed {len(parsed)})')
        out.append(block)
        context[name] = parsed
    return '\n'.join(out)


def parse_digest(text):
    """Every table of a digest, parsed in order with the same context the renderer used: {name: rows}."""
    context = {}
    for block in re.split(r'(?m)^### table ', text)[1:]:
        name, rows = parse_table('### table ' + block, context)
        context[name] = rows
    return context


def per_second_rows(first, buys, sells, roll, window=20):
    """Per-second table with roll20 as the exact fraction of window sums (n/d), verified against the producer's float."""
    cb = [0.0] * (len(buys) + 1); cs = [0.0] * (len(sells) + 1)
    for i in range(len(buys)):
        cb[i + 1] = cb[i] + buys[i]; cs[i + 1] = cs[i] + sells[i]
    rows = []
    for t in range(len(buys)):
        lo = max(0, t - window + 1)
        b = cb[t + 1] - cb[lo]; sv = cs[t + 1] - cs[lo]; z = b + sv
        if z > 0:
            n, d = b - sv, z
            frac = f'{int(n)}/{int(d)}' if float(n).is_integer() and float(d).is_integer() else f'{n!r}/{d!r}'
            value = (float(n) / float(d))
            if not (isinstance(roll[t], float) and value == roll[t]):
                raise ValueError(f'roll20 fraction at second {t} does not reproduce the producer float')
        else:
            frac = None
            if not (isinstance(roll[t], float) and math.isnan(roll[t])):
                raise ValueError(f'roll20 at second {t} expected undefined')
        rows.append(dict(second=first + t, buy=buys[t], sell=sells[t], roll20=frac))
    return rows


def _spellable(key):
    return bool(key) and isinstance(key, str) and key[0] not in '=^' and not any(ch in key for ch in '\t\n= .')   # a dot would re-nest differently on parse-back


def _spell(value):
    """A value the table can carry exactly: a mapping whose every key the header can spell stays a mapping (flattened
    to dotted columns by the codec); an EMPTY mapping, or one with a key the header cannot spell, becomes one JSON
    string cell (`S{...}`), exact and declared in the V6 header. Lists are left whole (J / I cells)."""
    if isinstance(value, dict):
        if value and all(_spellable(k) for k in value):
            return {k: _spell(v) for k, v in value.items()}
        return json.dumps(value, separators=(',', ':'), sort_keys=True)
    return value


def _leaf_count(value):
    if isinstance(value, list):
        return sum(_leaf_count(v) for v in value) if any(isinstance(v, list) for v in value) else len(value)
    return 1 if value is not None else 0


def _nest(flat):
    out = {}
    for path, value in flat.items():
        parts = path.split('.')
        node = out
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return out


def bedrock_tables(files):
    """DIGEST_V6 (BR-5): the bedrock layer files (frankie_box_bedrock.project's shape, {layer: file}) as dense exact
    tables, every derived fact once: `bedrock.layers` (one row per layer: status, reason, producer, carrier columns,
    sections, counts, partial), `bedrock.members` (one row per F_LAST group: the group key and the UNION of every
    derived layer's member_paths, a column once however many layers name it; a disagreement between layers on a
    group's value refuses), and `bedrock.lifecycle.<section>` (one table per lifecycle section a derived layer names,
    its rows whole, in ledger order, taken once). The whole ledgers stay in work/bedrock/ledgers/ and ride the bundle."""
    tables = {}
    index = []
    verdicts = [f.get('traversal') for f in files.values() if isinstance(f.get('traversal'), dict)]
    if verdicts:
        v = verdicts[0]
        tables['bedrock.run'] = [dict(verdict=v.get('verdict'), failed_gates=' '.join(v.get('failed_gates') or []), groups=v.get('groups'),
                                      records=v.get('records'), span_seconds=v.get('span_seconds'),
                                      candidate_warmup_seconds=v.get('candidate_warmup_seconds'), candidate_min_observations=v.get('candidate_min_observations'))]
    for name, f in files.items():
        index.append(dict(layer=name, status=f.get('status'), reason=f.get('reason'), producer=f.get('producer'),
                          member_paths=' '.join(f.get('member_paths') or []), lifecycle_sections=' '.join(f.get('lifecycle_sections') or []),
                          section_counts=json.dumps(f.get('section_counts') or {}, separators=(',', ':'), sort_keys=True),
                          member_count=len(f.get('member_rows') or []), lifecycle_count=len(f.get('lifecycle_rows') or []), count=f.get('count'),
                          partial=' '.join(p['section'] for p in (f.get('partial') or []))))
    tables['bedrock.layers'] = index
    members = {}
    for name, f in files.items():
        if f.get('status') != 'derived':
            continue
        for row in f.get('member_rows') or []:
            if 'group_index' not in row:
                raise ValueError(f'bedrock member projection of {name} carries a row without the group key group_index')
            key = row.get('group_index')
            merged = members.setdefault(key, {})
            for column, value in row.items():
                if '[]' in column and not column.endswith('#count'):
                    # a LIST-valued carrier path (`name[]`) is carried by its leaf COUNT (`<path>#count`); the values stay whole
                    # in the layer file and the ledger (the reading cost: the FIFO queue of every level per group is the bulk)
                    column, value = column + '#count', _leaf_count(value)
                if column in merged:
                    if not _same(merged[column], value):
                        raise ValueError(f'bedrock member projection conflict: group {key} column {column} differs between layers ({name})')
                    continue
                merged[column] = value
    if members:
        # nested by path segment (`structure.mirror.orientation` -> structure: {mirror: {orientation}}; `*` and `name[]` are
        # literal segments), so the codec's flattened column IS the crosswalk path and the parse-back rebuilds the same row
        tables['bedrock.members'] = [_nest({c: _spell(v) for c, v in members[k].items()}) for k in sorted(members, key=lambda g: (g is None, g))]
    sections = {}
    for name, f in files.items():
        if f.get('status') != 'derived':
            continue
        for section in f.get('lifecycle_sections') or []:
            rows = [r for r in (f.get('lifecycle_rows') or []) if r.get('emitting_section') == section]
            if rows and section not in sections:
                sections[section] = rows
    for section in sorted(sections):
        tables[f'bedrock.lifecycle.{section}'] = [{c: _spell(v) for c, v in r.items()} for r in sections[section]]
    # BR-9 (Greg, 2026-09-22): a SECTION file (frankie_box_bedrock.project_sections: 4.2, 4.4) adds, when derived, its companion
    # rows as `bedrock.companions.<section>` (the declaration and the section label lifted out: the declaration is one row per
    # measure in `bedrock.declarations.<section>`), its first/last books as `bedrock.first_last.<section>`, and its matching
    # rule as the one row of `bedrock.matching_rule.<section>`; its lifecycle rows rode `bedrock.lifecycle.<section>` above.
    for name, f in files.items():
        section = f.get('section')
        if f.get('status') != 'derived' or not section:
            continue
        if f.get('companion_rows'):
            tables[f'bedrock.companions.{section}'] = [{c: _spell(v) for c, v in r.items() if c not in ('declaration', 'section')} for r in f['companion_rows']]
        if f.get('declarations'):
            tables[f'bedrock.declarations.{section}'] = [{c: _spell(v) for c, v in r.items()} for r in f['declarations']]
        if f.get('first_last_pairs'):
            tables[f'bedrock.first_last.{section}'] = [{c: _spell(v) for c, v in r.items()} for r in f['first_last_pairs']]
        if f.get('matching_rule'):
            tables[f'bedrock.matching_rule.{section}'] = [{c: _spell(v) for c, v in f['matching_rule'].items()}]
    return tables


def digest_text(receipt, layers, prices, frames, structures, roll, first, buys, sells, bedrock=None):
    """The whole digest: layer status, then every derived layer as a dense exact table (all fields); with `bedrock`
    ({layer: file}), the V6 bedrock tables after them."""
    lines = ['# Derivation digest ' + SCHEMA + ' (Frankie\'s own calculations on this cycle\'s rows; written by the session code; whole, no '
             'limits; every derived field, exact; `=` = the column the adapter computes from this row (spread = best_ask - best_bid, '
             'mid = 0.5*(best_bid + best_ask), depth_imbalance_full = (bid_depth_full - ask_depth_full)/(bid_depth_full + ask_depth_full)), '
             'checked equal before it is written that way, and likewise every structure column the pinned producer computes from the '
             'row\'s own action/side strings, order-id lists and counts (terminal action/side, component and character counts, mirror '
             'identity, fill disposition class and signature, price span, carried family, discovery status, candidate_family_id = '
             '"ow-" + sha256 of the canonical descriptor); tables: one header line, tab-separated rows; `^` = the same value as the '
             'previous row in this column; integer timestamp, price_raw and depth/order-count columns as signed deltas from the '
             'previous row (first row absolute); floats as shortest round-trip decimals; `-` = none; T/F = booleans; `S...` = a string; '
             '`@n` = dictionary entry n (only a value that repeats in the table is in the dictionary); `J...` = JSON; `U...` = a tuple, as JSON; `I<first>,<+d>,...` = '
             'a list of integers as its first value (a signed delta from the previous row\'s first when one exists) then successive '
             'differences; `K<i>,<j>` = the list of this row\'s order_ids at those positions; `~<d>` = ts_event as an offset from this '
             'row\'s ts_recv; a header column written `=name` is derived on every row and omitted from the rows, `^name` holds one '
             'value on every row (given on the `constants:` line) and is omitted too; `transition` = the sign of each book field\'s '
             'change from the previous frame, recomputed; roll20 = n/d, the exact fraction (b-s)/(b+s) of the '
             'trailing 20-second buy and sell sums, its float being that division; DIGEST_V4 on top: cells are separated by one '
             'space when no cell of the table holds a space (`sep=space` in the header, else tabs); `^k` / `=k` = k consecutive '
             '`^` / `=` cells; a bare `n/d` float cell is the IEEE division of those two integers, which IS the stored float exactly '
             '(checked; used only when shorter than its decimal); a column on the `scales:` line has every integer literal (absolute '
             'or delta) written divided by that power of ten, all of them being exact multiples (checked)); DIGEST_V6 on top: the BEDROCK '
             'tables, when this cycle\'s pin carries a bedrock (Greg, 2026-09-21): `bedrock.layers` = one row per bedrock layer (status, '
             'reason, producer, its carrier member paths, its lifecycle sections, counts, the sections left empty by the candidate lane), '
             '`bedrock.members` = one row per F_LAST group with the group key (group_index, ts_recv_ns, f_last_ts_recv_ns) and the union '
             'of every derived bedrock layer\'s member paths as columns (each once; a LIST-valued path `name[]` is carried as its leaf '
             'count in `<path>#count`, its values staying whole in the layer file and the ledger), `bedrock.lifecycle.<section>` = every exact '
             'lifecycle row of that section, whole, in ledger order, once, `bedrock.run` = the traversal\'s own verdict and failed gates over '
             'this slice; the two SECTION files (4.2 the daily book regime companion, 4.4 the mirror matcher; Greg, 2026-09-22) add '
             '`bedrock.companions.<section>` = one row per measure per stratum (the section\'s averaged rows, whole), '
             '`bedrock.declarations.<section>` = one row per measure (numerator formula, population, causal cutoff, missingness rule, once), '
             '`bedrock.first_last.<section>` = the exact first and last book of each day-segment-phase, `bedrock.matching_rule.<section>` = '
             'the one rule the mirror pairs were formed under, and the mirror\'s own rows as `bedrock.lifecycle.mirror`; a mapping cell whose '
             'keys the header cannot spell (a dot, a space, `=`), or an empty mapping, is one JSON string '
             'cell; the three whole ledgers stay on the box under work/bedrock/ledgers/, witnessed by name, bytes and sha256 in the bundle index)', '',
             f'Rows: {receipt["rows"]["path"]} ({receipt["rows"]["count"]} entries, kinds {receipt["rows"]["kinds"]}, head {receipt["rows"]["head"][:16]}...; '
             f'head equals the request source_hash: {receipt["rows"]["head_is_request_source_hash"]}).',
             f'INPUT records fed to the V4 adapter: {receipt["input_records"]}; legacy control rows projected: {receipt["legacy_rows"]}; '
             f'F_LAST groups closed: {receipt["f_last_groups"]}; adapter failures: {receipt["failure_count"]}.', '',
             '## Layer status (pin group ' + receipt['pin_group'] + ')']
    for name, value in receipt['layers'].items():
        lines.append(f'- {name}: {value["status"]}' + (f' ({value["reason"]})' if value.get('reason') else '') + f'; producer: {value.get("producer")}; file {value["path"]} sha256 {value["sha256"][:16]}')
    families = {}
    for st in structures:
        families[st['action_string']] = families.get(st['action_string'], 0) + 1
    tables = {
        'legacy_price': list(prices),
        'per_second_flow_and_roll20': per_second_rows(first, buys, sells, roll),
        'legacy_book_imbalance': list(frames),
        'legacy_structure_observables': list(structures),
        'structure_families': [dict(action_string=k, count=v) for k, v in sorted(families.items(), key=lambda kv: -kv[1])],
    }
    text = '\n'.join(lines) + '\n\n' + render_layers(tables)
    if bedrock:
        derived = sum(1 for f in bedrock.values() if f.get('status') == 'derived')
        verdict = next((f.get('traversal') for f in bedrock.values() if isinstance(f.get('traversal'), dict)), None) or {}
        head = ['', '## Bedrock (the pinned producers\' own traversal on this cycle\'s rows, projected by their crosswalk; '
                f'{derived} of {len(bedrock)} layers derived; every derived fact once, whole; the traversal\'s own verdict over this slice: '
                f'{verdict.get("verdict")}' + (f', failed gates {", ".join(verdict["failed_gates"])}' if verdict.get('failed_gates') else ', no failed gate') + ')', '']
        text += '\n'.join(head) + '\n' + render_layers(bedrock_tables(bedrock))
    return text
