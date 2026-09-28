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

import copy
import json
import math
import re
from fractions import Fraction

SCHEMA = 'DIGEST_V9'   # V9: `L` lists with `*k` runs, `*k` runs in `I` lists, dictionary entries spelled as cells, `"k` ditto cells, `$d` trailing-number deltas of strings, `~d` integer deltas inside keys-once objects, `O` packed digits with outliers apart (Greg, 2026-09-28, the reducer stacks on top of the 6-hour run's); V8: the table grammar below (Greg, 2026-09-28, every token stack that works, all additive); V6: the bedrock tables (BR-5, 2026-09-21); V5: the sign of zero is a value (-0.0 never folds into 0.0), tuple cells, a self-checking parser
TABLE_GRAMMAR = 'DIGEST_V9'   # the table block grammar. V9: `L` lists, `*k` item runs, dictionary entries as cells. V7: `?k` runs of absent cells; deltas on every integer column whose name ends in
                              # recv_ns / event_ns and on group_index. V8 on top: keys-once objects (`shapes:`, `R` cells), packed digit
                              # lists (`P`), same-row integer references (`<i`), count columns derived as list lengths (`lengths:`), columns
                              # ordered by presence, and the dictionary only where it pays
BEDROCK_GROUP_KEY = ('group_index', 'ts_recv_ns', 'f_last_ts_recv_ns')
FRACTION_DENOMINATOR = 1_000_000   # DIGEST_V4: a float spelled n/d only when float(n)/float(d) is that float exactly and the spelling is shorter
SCALE_MIN, SCALE_MAX = 3, 9       # DIGEST_V4: a per-column power of ten every integer literal of the column divides by (declared once, checked)
RUN_MARKS = ('^', '=', '?')       # DIGEST_V4: k consecutive identical mark cells collapse to `^k` / `=k`; V7 adds `?k` (no other cell
                                  # starts with `?`, and no column name may); never `-`: `-3` is an integer

DELTA_KEYS = ('ts_recv_ns', 'ts_event_ns', 'ts_recv', 'ts_event', 'second', 'price_raw_min', 'price_raw_max',
              'bid_depth_full', 'ask_depth_full', 'bid_order_count_full', 'ask_order_count_full',
              'recv_ns', 'event_ns', 'group_index')   # V7: every lifecycle *_recv_ns / *_event_ns timestamp and the group index
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


def _recompute(row, column, prev=None, facts=None):
    source = facts.lengths.get(column) if facts is not None else None
    if source is not None:
        return len(row[source])                     # V8 `lengths:` rule: the count IS the length of that list column
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


def _derived(row, column, prev=None, facts=None):
    """True when `column` of this flat row is rendered `=`: the stored value equals the recomputation exactly (for the
    adapter's book columns, a None stored where an input is None also counts, as the adapter writes it)."""
    source = facts.lengths.get(column) if facts is not None else None
    if source is not None:
        return isinstance(row.get(source), list) and _is_int(row.get(column)) and row[column] == len(row[source])
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


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


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


# ---- DIGEST_V8 table grammar: ONE place for every writer, reader and verifier ----------------------------------------
# (review 2026-09-28: the serial, streamed and parallel writers each carried their own cell finisher, header writer and
# decoder; a grammar change in one could miss another. Every grammar decision now lives here; frankie_box_digest_stream
# and frankie_box_digest_parallel only orchestrate, and their code identity keys this file.)

_COST_RUN = re.compile(r'\d+|[A-Za-z]+|\s+|[^\dA-Za-z\s]+')


def _cost(text):
    """Estimated pinned-Granite tokens of a cell spelling (calibrated on the verified tokenizer, 2026-09-28: digit runs
    split into tokens of up to three digits, letters about four to a token, punctuation about two). A pure function of
    the text, so every writer makes the same choice; the choice changes only which exact spelling is written."""
    if text.isdigit():                                     # fast paths, the same values the runs give
        return -(-len(text) // 3)
    if text[:1] in '+-<~@' and text[1:].isdigit():
        return 1 + -(-(len(text) - 1) // 3)
    total = 0
    for m in _COST_RUN.finditer(text):
        run = m.group()
        if run[0].isdigit():
            total += -(-len(run) // 3)
        elif run[0].isalpha():
            total += -(-len(run) // 4)
        elif not run[0].isspace():
            total += -(-len(run) // 2)
    return max(total, 1)


def check_column(name):
    if not name or name[0] in '=^?' or '\t' in name or '\n' in name or '=' in name or ' ' in name:
        raise ValueError(f'column name {name!r} cannot be spelled in a table header')


def _spellable_key(key):
    return isinstance(key, str) and bool(key) and not any(ch in key for ch in ',;=\t\n')


class Facts:
    """Table-wide facts the planner needs before the first cell and the header declares: the column order, the keys-once
    shape of each list-of-objects column (V8 `shapes:`) and each count column that is the length of a list column (V8
    `lengths:`)."""
    __slots__ = ('columns', 'shapes', 'lengths')

    def __init__(self, columns, shapes=None, lengths=None):
        self.columns, self.shapes, self.lengths = list(columns), dict(shapes or {}), dict(lengths or {})


NO_FACTS = Facts(())


class Observer:
    """Collects Facts over a table's rows in order (the snapshot pass). Mergeable in part order (the parallel writer):
    presence counts add, shapes unite, length candidates intersect."""

    def __init__(self):
        self.presence = {}   # column -> rows carrying it, first-seen order
        self.shapes = {}     # column -> set of object keys, or None when some list of objects there cannot be keys-once
        self.lengths = {}    # column -> candidate list columns whose length it equals on every row carrying it

    def add(self, flat):
        by_length = {}
        for c, v in flat.items():
            if c not in self.presence:
                check_column(c)
                self.presence[c] = 0
            self.presence[c] += 1
            if isinstance(v, list):
                if not _is_derivable(c):
                    by_length.setdefault(len(v), set()).add(c)
                if v and all(isinstance(x, dict) for x in v) and self.shapes.get(c, ()) is not None:
                    if all(_spellable_key(k) for x in v for k in x) and _no_tuples(v):
                        keys = self.shapes.setdefault(c, set())
                        for x in v:
                            keys.update(x)
                    else:
                        self.shapes[c] = None
        for c, v in flat.items():
            if _is_derivable(c) or (c in self.lengths and not self.lengths[c]):
                continue
            found = by_length.get(v, set()) if _is_int(v) and v >= 0 else set()
            self.lengths[c] = (self.lengths[c] & found) if c in self.lengths else set(found)

    def merge(self, other):
        for c, count in other.presence.items():
            self.presence[c] = self.presence.get(c, 0) + count
        for c, keys in other.shapes.items():
            mine = self.shapes.get(c, set())
            self.shapes[c] = None if mine is None or keys is None else mine | keys
        for c, found in other.lengths.items():
            self.lengths[c] = (self.lengths[c] & found) if c in self.lengths else set(found)
        return self

    def facts(self):
        # V8: columns ordered by how many rows carry them (most first; ties keep first-seen order), so the columns a row
        # lacks sit together and collapse into one `?k` run; a table whose rows all carry every column keeps its order
        first_seen = list(self.presence)
        columns = sorted(first_seen, key=lambda c: -self.presence[c])
        shapes = {c: tuple(sorted(keys)) for c, keys in self.shapes.items() if keys}
        lengths = {c: min(found) for c, found in self.lengths.items() if found}
        return Facts(columns, shapes, lengths)


def _inner_literal(y):
    if y is None:
        return NONE
    if y is True:
        return TRUE
    if y is False:
        return FALSE
    if isinstance(y, int):
        return str(y)
    if isinstance(y, float):
        return 'nan' if math.isnan(y) else _float_text(y)
    if isinstance(y, str):
        return ('S' + y) if not any(ch in y for ch in ',;\t\n') else ('J' + json.dumps(y))
    return 'J' + json.dumps(y, separators=(',', ':'), sort_keys=True)


def _scalar_list(v):
    return isinstance(v, list) and all(y is None or isinstance(y, (bool, int, float, str)) for y in v)


def _list_item(y):
    """One `L` item: an inner literal, a string bare (`S<text>`) only when it holds none of `,` `*` `;` tab newline."""
    if isinstance(y, str):
        return ('S' + y) if not any(ch in y for ch in ',*;\t\n') else ('J' + json.dumps(y))
    return _inner_literal(y)


def _list_cell(v):
    """V9 `L`: a list of scalars, its items joined by `,`, k >= 2 equal consecutive items written once as `item*k`."""
    items, i = [], 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and _same(v[j + 1], v[i]):
            j += 1
        text = _list_item(v[i])
        items.append(text if j == i else '%s*%d' % (text, j - i + 1))
        i = j + 1
    return 'L' + ','.join(items)


_LIST_ITEM = re.compile(r'[^,*]*')
_LIST_RUN = re.compile(r'\*(\d+)')


def _read_list(body):
    out, pos = [], 0
    while pos < len(body):
        if body.startswith('J', pos):
            _, end = _JSON.raw_decode(body, pos + 1)
        else:
            end = _LIST_ITEM.match(body, pos).end()
        if end == pos:
            raise ValueError('list cell: an empty item')
        y, k = _scalar(body[pos:end]), 1
        pos = end
        m = _LIST_RUN.match(body, pos)
        if m is not None:
            k, pos = int(m.group(1)), m.end()
            if k < 2:
                raise ValueError('list cell: a run of %d' % k)
        out.extend([y] * k)
        if pos == len(body):
            break
        if body[pos] != ',':
            raise ValueError('list cell: an item is followed by %r' % body[pos])
        pos += 1
        if pos == len(body):
            raise ValueError('list cell: a trailing `,`')
    return out


_TRAILING = re.compile(r'(.*?)(\d+)', re.S)


def _trailing(s):
    """(prefix, number) of a string ending in a decimal number without a leading zero, else None."""
    m = _TRAILING.fullmatch(s) if isinstance(s, str) else None
    if m is None or (len(m.group(2)) > 1 and m.group(2)[0] == '0'):
        return None
    return m.group(1), int(m.group(2))


def _string_step(prev, v):
    """V9 `$<d>`: v is the previous row's string of this column with its trailing number moved by d (same prefix)."""
    a, b = _trailing(prev), _trailing(v)
    if a is None or b is None or a[0] != b[0] or b[1] == a[1]:
        return None
    return '$%+d' % (b[1] - a[1])


def _string_stepped(prev, cell):
    a = _trailing(prev)
    if a is None or not re.fullmatch(r'\$[+-]\d+', cell) or a[1] + int(cell[1:]) < 0:
        raise ValueError('a `$` cell needs a previous string ending in a number')
    return a[0] + str(a[1] + int(cell[1:]))


def _ditto(cells):
    """V9 `"k`: k further copies of the cell just before it in the row, when cheaper than writing them (never after a run
    mark); expand_cells repeats the preceding cell's text."""
    out, i = [], 0
    while i < len(cells):
        c, j = cells[i], i
        if c[:1] not in RUN_MARKS:
            while j + 1 < len(cells) and cells[j + 1] == c:
                j += 1
        k = j - i
        out.append(c)
        if k and _cost('"%d' % k) < k * _cost(c):
            out.append('"%d' % k)
        else:
            out.extend([c] * k)
        i = j + 1
    return out


def _runs(texts):
    """k >= 2 equal consecutive spellings written once as `text*k` (V9, inside `I` lists)."""
    out, i = [], 0
    while i < len(texts):
        j = i
        while j + 1 < len(texts) and texts[j + 1] == texts[i]:
            j += 1
        out.append(texts[i] if j == i else '%s*%d' % (texts[i], j - i + 1))
        i = j + 1
    return out


def entry_spelling(key):
    """V9: a dictionary entry is spelled as its inline cell (`S`, `J` or `L`; the key is the value's JSON)."""
    return inline_cell('str', json.loads(key)) if key.startswith('"') else inline_cell('json', key)


def entry_value(text):
    """The value of a dictionary entry spelled by entry_spelling."""
    if text.startswith('L'):
        return _read_list(text[1:])
    if text.startswith('S'):
        return text[1:]
    if text.startswith('J'):
        return json.loads(text[1:])
    raise ValueError('dictionary entry spelling %r' % text[:24])


def _objects_ref(prev_value):
    return prev_value[-1] if isinstance(prev_value, list) and prev_value and isinstance(prev_value[-1], dict) else None


def _objects(v, shape, prev_value):
    """V8 keys-once: a list of objects written `R` + objects joined by `;`, each object its values in the declared key
    order joined by `,` (the keys are on the header's `shapes:` line, never on a row). Each value is read against the
    previous object (the last object of the previous row's list for the first): `^` the same value, a signed delta for an
    integer key ending in recv_ns / event_ns, `<i` the same integer as this object's key i, `?` absent; runs collapse."""
    ref, objects = _objects_ref(prev_value), []
    for x in v:
        cells, seen = [], {}
        for i, k in enumerate(shape):
            if k not in x:
                cells.append('?')
                continue
            y = x[k]
            if ref is not None and k in ref and _same(ref[k], y):
                text = SAME
            elif ref is not None and _is_int(y) and _is_int(ref.get(k)) and k.endswith(DELTA_KEYS):
                text = '%+d' % (y - ref[k])
            else:
                text = _inner_literal(y)
                if ref is not None and _is_int(y) and _is_int(ref.get(k)):       # V9 `~d`: any integer key, when cheaper
                    moved = '~%+d' % (y - ref[k])
                    if _cost(moved) < _cost(text):
                        text = moved
            if _is_int(y):
                at = seen.get(y)
                if at is None:
                    seen[y] = i
                elif text != SAME and _cost(text) > _cost('<%d' % at):
                    text = '<%d' % at
            cells.append(text)
        objects.append(','.join(_collapse(cells)))
        ref = x
    return 'R' + ';'.join(objects)


_JSON = json.JSONDecoder()
_INNER_CELL = re.compile(r'[^,;]*')


def _read_objects(body, shape, prev_value):
    groups, cells, pos = [], [], 0
    while True:
        if body.startswith('J', pos):
            _, end = _JSON.raw_decode(body, pos + 1)
        else:
            end = _INNER_CELL.match(body, pos).end()
        cells.append(body[pos:end])
        pos = end
        if pos == len(body):
            groups.append(cells)
            break
        if body[pos] == ';':
            groups.append(cells)
            cells = []
        elif body[pos] != ',':
            raise ValueError('keys-once cell: a value is followed by %r' % body[pos])
        pos += 1
    ref, out = _objects_ref(prev_value), []
    for group in groups:
        cells = _expand(group)
        if len(cells) != len(shape):
            raise ValueError('keys-once cell: %d values for %d keys' % (len(cells), len(shape)))
        x = {}
        for k, text in zip(shape, cells):
            if text == '?':
                continue
            if text == SAME:
                if ref is None or k not in ref:
                    raise ValueError('keys-once cell: `^` without a previous value')
                y = copy.deepcopy(ref[k])
            elif text.startswith('<'):
                y = x[shape[int(text[1:])]]
            elif text[0] in '+-' and len(text) > 1 and text[1:].isdigit() and k.endswith(DELTA_KEYS) and ref is not None and _is_int(ref.get(k)):
                y = ref[k] + int(text)
            elif text.startswith('~'):
                if ref is None or not _is_int(ref.get(k)) or not re.fullmatch(r'~[+-]\d+', text):
                    raise ValueError('keys-once cell: `~` without a previous integer')
                y = ref[k] + int(text[1:])
            else:
                y = _scalar(text)
            x[k] = y
        out.append(x)
        ref = x
    return out


def _scalar(text):
    """A standalone scalar cell: `-` T F `S...` `J...` `nan`, an exact fraction, an integer, a float."""
    if text == NONE:
        return None
    if text == TRUE:
        return True
    if text == FALSE:
        return False
    if text.startswith('S'):
        return text[1:]
    if text.startswith('J'):
        return json.loads(text[1:])
    if text == 'nan':
        return float('nan')
    if _FRACTION.fullmatch(text):
        num, _, den = text.partition('/')
        return float(int(num)) / float(int(den))
    if _INT_CELL.fullmatch(text):
        return int(text)
    return float(text)


_FRACTION = re.compile(r'-?\d+/\d+')


def _packed(v, first):
    """V8 packed digits (the stacked_v2 P form): `P<first>:<lo>:<width>:<digits>`, the successive differences as one
    run of fixed-width decimal fields, each difference = field + lo. V9 (stacked_v2 O, outliers): when cheaper, up to
    eight of the largest differences are written apart, `O<first>:<lo>:<width>:<digits>:<i>=<d>;...` (their fields are
    zeros), so they do not widen every field."""
    steps = [b - a for a, b in zip(v, v[1:])]
    best = _packed_form(first, steps, {})
    order = sorted(range(len(steps)), key=lambda i: steps[i], reverse=True)
    for cut in range(1, min(8, len(steps) - 1) + 1):
        text = _packed_form(first, steps, {i: steps[i] for i in order[:cut]})
        if _cost(text) < _cost(best):
            best = text
    return best


def _packed_form(first, steps, apart):
    kept = [d for i, d in enumerate(steps) if i not in apart]
    lo = min(kept)
    width = max(1, len(str(max(kept) - lo)))
    digits = ''.join('0' * width if i in apart else str(d - lo).zfill(width) for i, d in enumerate(steps))
    if not apart:
        return 'P%s:%d:%d:%s' % (first, lo, width, digits)
    return 'O%s:%d:%d:%s:%s' % (first, lo, width, digits, ';'.join('%d=%d' % (i, apart[i]) for i in sorted(apart)))


def _unpacked_apart(text, column, prev_lists):
    first, lo, width, digits, apart = text[1:].split(':', 4)
    lo, width = int(lo), int(width)
    if width < 1 or not digits or len(digits) % width or not digits.isdigit() or not apart:
        raise ValueError('packed cell %r' % text[:40])
    steps = [int(digits[i:i + width]) + lo for i in range(0, len(digits), width)]
    for item in apart.split(';'):
        i, equal, d = item.partition('=')
        if not equal or not 0 <= int(i) < len(steps):
            raise ValueError('packed cell %r' % text[:40])
        steps[int(i)] = int(d)
    v = [_list_start(first, column, prev_lists)]
    for d in steps:
        v.append(v[-1] + d)
    return v


def _unpacked(text, column, prev_lists):
    first, lo, width, digits = text[1:].split(':')
    lo, width = int(lo), int(width)
    if width < 1 or len(digits) % width or not (digits.isdigit() or not digits):
        raise ValueError('packed cell %r' % text[:40])
    v = [_list_start(first, column, prev_lists)]
    for i in range(0, len(digits), width):
        v.append(v[-1] + int(digits[i:i + width]) + lo)
    return v


def _list_start(first, column, prev_lists):
    return prev_lists[column] + int(first) if first[:1] in '+-' and _is_int(prev_lists.get(column)) else int(first)


def _literal(v, column, r, prev_lists, shape=None, prev_value=None):
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
    if shape and isinstance(v, list) and v and all(isinstance(x, dict) and all(k in shape for k in x) for x in v):
        return 'lit', _objects(v, shape, prev_value)
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
        listed = 'I' + ','.join([first] + _runs(['%+d' % (b - a) for a, b in zip(v, v[1:])]))   # first (as a delta from the previous row's first when one exists), then successive differences (V9: `d*k` runs)
        if len(v) > 1:
            packed = _packed(v, first)
            if _cost(packed) < _cost(listed):
                return 'lit', packed
        return 'lit', listed
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


def _plan_row(r, columns, prev_row, prev_values, prev_ints, prev_lists, facts=NO_FACTS):
    """One row's cells before the dictionary pass: a list of (kind, text) and the state updates."""
    cells, same_row = [], {}
    for j, c in enumerate(columns):
        if c not in r:
            cells.append(('lit', '=' if _absent_is_derived(r, c) else '?'))
            continue
        v = r[c]
        if _derived(r, c, prev_row, facts):
            cell = ('lit', '=')
        elif c in prev_values and _same(prev_values[c], v):
            cell = ('lit', SAME)
        elif c in PAIRED and _is_int(v) and _is_int(r.get(PAIRED[c])):
            cell = ('lit', '~%+d' % (v - r[PAIRED[c]]))
        elif c.endswith(DELTA_KEYS) and _is_int(v) and isinstance(prev_ints.get(c), int):
            cell = ('lit', '%+d' % (v - prev_ints[c]))
        else:
            cell = _literal(v, c, r, prev_lists, facts.shapes.get(c), prev_values.get(c))
            moved = _string_step(prev_values.get(c), v) if cell[0] == 'str' else None
            if moved is not None and _cost(moved) < inline_cost('str', v):
                cell = ('lit', moved)
        if _is_int(v) and cell[1][0] not in '=~':
            # V8 same-row reference: `<i` = the integer of this row's column i (an earlier column the parser holds
            # before any offset or derivation), written when cheaper than the cell it replaces
            at = same_row.get(v)
            if at is None:
                same_row[v] = j
            elif cell[1] != SAME and _cost(cell[1]) > _cost('<%d' % at):
                cell = ('lit', '<%d' % at)
        cells.append(cell)
        prev_values[c] = v
        if _is_int(v):
            prev_ints[c] = v
        if _int_list(v):
            prev_lists[c] = v[0]
    return cells


def fold(state, flat):
    """The row-to-row state after a decoded (or planned) row: last value / integer / list head per column."""
    values, ints, lists = state
    for c, v in flat.items():
        values[c] = v
        if _is_int(v):
            ints[c] = v
        if _int_list(v):
            lists[c] = v[0]


def candidate_key(kind, text):
    """The dictionary key of a planned cell that is not final ('str' / 'json'): its JSON spelling."""
    return json.dumps(text) if kind == 'str' else text


def inline_cell(kind, text):
    """A dictionary candidate written inline (it does not repeat, or the dictionary would not pay)."""
    if kind == 'str':
        return ('S' + text) if ('\t' not in text and '\n' not in text) else ('J' + json.dumps(text))
    if text.startswith('['):                  # V9: a list of scalars as `L` when that is cheaper than its JSON
        v = json.loads(text)
        if _scalar_list(v):
            listed = _list_cell(v)
            if _cost(listed) < _cost('J' + text):
                return listed
    return 'J' + text


def inline_cost(kind, text):
    return _cost(inline_cell(kind, text))


def dictionary_pays(count, cost, number):
    """V8 dictionary cutoff: a repeating value (inline spelling of estimated cost `cost`) goes to the dictionary as entry
    `number` only when the entry plus `count` references cost fewer estimated tokens than `count` inline spellings (a
    two-letter string stays inline). Decided once, at the value's first occurrence, so every writer numbers alike."""
    ref = _cost('@%d' % number)
    return count >= 2 and ref * count + ref + 1 + cost < cost * count


def scale_step(state, text):
    """One literal cell's effect on its column's scale state [k, seen] (DIGEST_V4 per-column power of ten)."""
    if not _INT_CELL.fullmatch(text):
        return
    k = state[0]
    value, z = abs(int(text)), 0
    if value:
        while value % 10 == 0 and z < k:
            value //= 10
            z += 1
        k = min(k, z)
    state[0], state[1] = k, True


def scales_of(states, columns):
    """{column: 10^k} from {column index: [k, seen]}."""
    return {columns[j]: 10 ** k for j, (k, seen) in states.items() if seen and k >= SCALE_MIN}


def finish_row(cells, kept, columns, scales, number):
    """The written cells of one planned row: literals (scaled when the column has a scale), candidates as `@n` when
    number(kind, text, key) gives their dictionary number (else inline), runs collapsed."""
    out = []
    for j in kept:
        kind, text = cells[j]
        if kind == 'lit':
            scale = scales.get(columns[j])
            out.append(_scaled(text, scale) if scale and _INT_CELL.fullmatch(text) else text)
            continue
        n = number(kind, text, candidate_key(kind, text))
        out.append(inline_cell(kind, text) if n is None else '@%d' % n)
    return _ditto(_collapse(out))


def _constant_text(value):
    return ('U' + json.dumps(list(value), separators=(',', ':'), sort_keys=True)) if isinstance(value, tuple) \
        else json.dumps(value, separators=(',', ':'), sort_keys=True)   # a tuple constant keeps its U mark


def whole_marks(columns, n, derived, constant, cross=None):
    """The header's whole-column marks: `=` derived on every row (or, cross, copied row for row from an earlier table),
    `^` one value on every row (on the `constants:` line); such a column is omitted from the rows."""
    cross = cross or {}
    return {c: '=' if cross.get(c) or derived[c] else '^' for c in columns if cross.get(c) or (n and (derived[c] or constant[c]))}


def header_lines(name, n, sep, columns, whole, first, scales, facts):
    """The table's header lines before the dictionary: the column line, constants, scales, and the V8 shapes / lengths."""
    head = [f'### table {name}: {n} rows, sep={"space" if sep == " " else "tab"}, columns: ' + '\t'.join(whole.get(c, '') + c for c in columns)]
    constants = [c for c in columns if whole.get(c) == '^']
    if constants:
        head.append('constants: ' + '\t'.join('%s=%s' % (c, _constant_text(first[c])) for c in constants))
    if scales:
        head.append('scales: ' + '\t'.join('%s=%d' % (c, k) for c, k in scales.items()))
    shapes = [c for c in columns if c in facts.shapes and c not in whole]
    if shapes:
        head.append('shapes: ' + '\t'.join('%s=%s' % (c, ','.join(facts.shapes[c])) for c in shapes))
    lengths = [c for c in columns if c in facts.lengths and whole.get(c) != '^']
    if lengths:
        head.append('lengths: ' + '\t'.join('%s=%s' % (c, facts.lengths[c]) for c in lengths))
    return head


class Lines:
    """A header reader over a list of lines (the in-memory parser), with the streaming reader's interface."""

    def __init__(self, lines, start=0):
        self.lines, self.index = lines, start

    def starts(self, prefix):
        return self.index < len(self.lines) and self.lines[self.index].startswith(prefix)

    def skip(self, prefix):
        if not self.starts(prefix):
            raise ValueError('expected ' + prefix)
        self.lines[self.index] = self.lines[self.index][len(prefix):]

    def take(self, delimiters='\n'):
        if self.index >= len(self.lines):
            raise ValueError('truncated table (missing delimiter)')
        line = self.lines[self.index]
        if delimiters != '\n':
            cut = [p for p in (line.find(d) for d in delimiters if d != '\n') if p >= 0]
            if cut:
                self.lines[self.index] = line[min(cut) + 1:]
                return line[:min(cut)], line[min(cut)]
        self.index += 1
        return line, '\n'


class Header:
    """A parsed table header (every line before the dictionary)."""

    def __init__(self, reader):
        line, _ = reader.take()
        m = re.fullmatch(r'### table (\S+): (\d+) rows, (?:sep=(space|tab), )?columns: (.*)', line)
        if m is None:
            raise ValueError('table header expected')
        self.name, self.n = m.group(1), int(m.group(2))
        self.sep = ' ' if m.group(3) == 'space' else '\t'
        declared = m.group(4).split('\t') if m.group(4) else []
        self.columns = [c[1:] if c[:1] in '=^' else c for c in declared]
        self.whole = {c[1:]: c[0] for c in declared if c[:1] in '=^'}
        self.kept = [c for c in self.columns if c not in self.whole]
        self.constants, self.scales, shapes, lengths = {}, {}, {}, {}
        for prefix, into in (('constants: ', self.constants), ('scales: ', self.scales), ('shapes: ', shapes), ('lengths: ', lengths)):
            if reader.starts(prefix):
                reader.skip(prefix)
                text, _ = reader.take()
                for item in text.split('\t'):
                    k, _, value = item.partition('=')
                    if prefix == 'constants: ':
                        into[k] = tuple(json.loads(value[1:])) if value.startswith('U') else json.loads(value)
                    elif prefix == 'scales: ':
                        into[k] = int(value)
                    elif prefix == 'shapes: ':
                        into[k] = tuple(value.split(','))
                    else:
                        into[k] = value
        self.facts = Facts(self.columns, shapes, lengths)


def read_dictionary(reader, add):
    """The `dictionary:` line, one entry at a time (never the whole line held): add(number, json_text)."""
    if not reader.starts('dictionary: '):
        return 0
    reader.skip('dictionary: ')
    number = 0
    while True:
        item, delimiter = reader.take('\t\n')
        k, equal, value = item.partition('=')
        if not equal or k != '@%d' % number:
            raise ValueError('dictionary numbering mismatch')
        entry_value(value)
        add(number, value)
        number += 1
        if delimiter == '\n':
            return number


def expand_cells(line, sep, kept):
    """A row line's cells with every `^k` / `=k` / `?k` run expanded, checked against the kept column count."""
    if not kept:
        if line:
            raise ValueError('constant-only table carries unexpected cells')
        return []
    out = []
    for cell in line.split(sep):
        if len(cell) > 1 and cell[0] == '"' and cell[1:].isdigit():     # V9 ditto: the preceding cell k more times
            if not out or len(out) + int(cell[1:]) > len(kept):
                raise ValueError('table row: a ditto cell without room or a preceding cell')
            out.extend([out[-1]] * int(cell[1:]))
            continue
        count = int(cell[1:]) if len(cell) > 1 and cell[0] in RUN_MARKS and cell[1:].isdigit() else 1
        if len(out) + count > len(kept):
            raise ValueError('table row expands beyond declared columns')
        out.extend([cell[0]] * count if count != 1 else [cell])
    if len(out) != len(kept):
        raise ValueError(f'table row: {len(out)} cells for {len(kept)} columns')
    return out


class RowDecoder:
    """Decodes a table's row lines in order: entry(number) gives a dictionary value (a fresh object); seed is the
    row-to-row state before the first line (previous row, last values / integers / list heads), for a part."""

    def __init__(self, header, entry, seed=None):
        self.h, self.entry = header, entry
        prev_row, values, ints, lists = seed or (None, {}, {}, {})
        self.prev_row, self.state = prev_row, (dict(values), dict(ints), dict(lists))
        self.index = {c: j for j, c in enumerate(header.columns)}
        self.order = _derived_order(header.columns, header.facts)

    def decode(self, line, cross=None):
        """The flat row of one line; cross = {column: value} of the cross-table derived columns for this row."""
        h = self.h
        prev_values, prev_ints, prev_lists = self.state
        cells = expand_cells(line, h.sep, h.kept)
        row = copy.deepcopy(h.constants)
        cross = cross or {}
        for c, v in cross.items():
            row[c] = copy.deepcopy(v)
        derived_cols = {c for c, mark in h.whole.items() if mark == '=' and c not in cross}
        refs, positional, paired = [], {}, {}
        for c, cell in zip(h.kept, cells):
            if cell == '?':
                continue
            if cell == '=':
                derived_cols.add(c)
                continue
            if cell == SAME:
                if c not in prev_values:
                    raise ValueError(f'table {h.name}: `^` in column {c} with no previous value')
                v = copy.deepcopy(prev_values[c])
            elif cell.startswith('@'):
                v = self.entry(int(cell[1:]))
            elif cell.startswith('<'):
                refs.append((c, int(cell[1:])))
                continue
            elif cell.startswith('~'):
                paired[c] = int(cell[1:])      # resolved once every literal and reference of the row is in, whatever the column order
                continue
            elif cell.startswith('K'):
                positional[c] = [int(i) for i in cell[1:].split(',')] if cell[1:] else []
                continue
            elif cell.startswith('U'):
                v = tuple(json.loads(cell[1:]))
            elif cell.startswith('I'):
                parts = cell[1:].split(',')
                v = [_list_start(parts[0], c, prev_lists)]
                for d in parts[1:]:
                    d, _, k = d.partition('*')
                    for _ in range(int(k) if k else 1):
                        v.append(v[-1] + int(d))
            elif cell.startswith('L'):
                v = _read_list(cell[1:])
            elif cell.startswith('$'):
                v = _string_stepped(prev_values.get(c), cell)
            elif cell.startswith('P'):
                v = _unpacked(cell, c, prev_lists)
            elif cell.startswith('O'):
                v = _unpacked_apart(cell, c, prev_lists)
            elif cell.startswith('R'):
                if c not in h.facts.shapes:
                    raise ValueError(f'table {h.name}: keys-once cell in column {c} without a declared shape')
                v = _read_objects(cell[1:], h.facts.shapes[c], prev_values.get(c))
            elif cell.startswith('+') or (cell.startswith('-') and c.endswith(DELTA_KEYS) and isinstance(prev_ints.get(c), int) and re.fullmatch(r'-\d+', cell)):
                v = prev_ints[c] + int(cell) * h.scales.get(c, 1)
            elif re.fullmatch(r'-?\d+', cell):
                v = int(cell) * h.scales.get(c, 1)
            else:
                v = _scalar(cell)
            row[c] = v
        for c, at in refs:                      # in column order: a reference names an earlier column
            source = h.columns[at]
            if source not in row or not _is_int(row[source]):
                raise ValueError(f'table {h.name}: {c} refers to column {at}, which this row does not hold as an integer')
            row[c] = row[source]
        for c, offset in paired.items():
            if PAIRED[c] not in row:
                raise ValueError(f'table {h.name}: {c} is an offset from {PAIRED[c]}, which this row does not carry')
            row[c] = row[PAIRED[c]] + offset
        for c, pos in positional.items():
            row[c] = [row['order_ids'][i] for i in pos]
        for c in self.order:
            if c in derived_cols:
                value = _recompute(row, c, self.prev_row, h.facts)
                if c.startswith(('action_counts.', 'side_counts.')) and c not in h.facts.lengths and value == 0:
                    continue   # the producer's Counter holds no zero entries: the key is absent
                row[c] = value
        fold(self.state, row)
        self.prev_row = row
        return row


def plan_table(flat, facts):
    """Every row planned in order (the in-memory writer)."""
    prev_row, values, ints, lists, planned = None, {}, {}, {}, []
    for r in flat:
        planned.append(_plan_row(r, facts.columns, prev_row, values, ints, lists, facts))
        prev_row = r
    return planned


def render_table(name, rows, context=None):
    """rows: list of dicts (nested dicts flattened). Returns the text block. Two passes: the first plans every cell and
    counts the strings and JSON cells; the second writes them, a value through the dictionary only when it REPEATS in
    this table and the dictionary pays (`@n`), inline otherwise (`S<text>` for a string, `J<json>` for a JSON cell). A
    column derived on EVERY row is declared once in the header (`=name`) and omitted from the rows; a column holding one
    value on every row is declared `^name` with its value on the `constants:` line and omitted too."""
    flat = [_flatten(r) for r in rows]
    observer = Observer()
    for r in flat:
        observer.add(r)
    facts = observer.facts()
    columns = facts.columns
    planned = plan_table(flat, facts)
    cross, derived, constant = {}, {}, {}
    for j, c in enumerate(columns):
        source = (context or {}).get(CROSS_DERIVED.get((name, c), (None, None))[0])
        cross[c] = source is not None and len(source) == len(flat) and all(c in r and _same(r[c], _flatten(src).get(CROSS_DERIVED[(name, c)][1], object())) for r, src in zip(flat, source))
        derived[c] = all(cells[j][1] == '=' for cells in planned)
        constant[c] = all(c in r for r in flat) and all(_same(r[c], flat[0][c]) for r in flat)
    whole = whole_marks(columns, len(flat), derived, constant, cross)
    kept = [j for j, c in enumerate(columns) if c not in whole]
    counts = {}
    for cells in planned:
        for j in kept:
            kind, text = cells[j]
            if kind != 'lit':
                key = candidate_key(kind, text)
                counts[key] = counts.get(key, 0) + 1
    states = {j: [SCALE_MAX, False] for j in kept}
    for cells in planned:
        for j in kept:
            if cells[j][0] == 'lit':
                scale_step(states[j], cells[j][1])
    scales = scales_of(states, columns)
    numbers, order = {}, []

    def number(kind, text, key):
        if key not in numbers:
            numbers[key] = len(order) if dictionary_pays(counts[key], inline_cost(kind, text), len(order)) else None
            if numbers[key] is not None:
                order.append(key)
        return numbers[key]

    table = [finish_row(cells, kept, columns, scales, number) for cells in planned]
    sep = ' ' if not any(' ' in cell for row in table for cell in row) else '\t'
    head = header_lines(name, len(rows), sep, columns, whole, flat[0] if flat else {}, scales, facts)
    if order:
        head.append('dictionary: ' + '\t'.join('@%d=%s' % (i, entry_spelling(key)) for i, key in enumerate(order)))
    return '\n'.join(head + [sep.join(row) for row in table]) + '\n'


_INT_CELL = re.compile(r'[+-]?\d+')


def _scaled(text, scale):
    value = int(text) // scale if int(text) >= 0 else -((-int(text)) // scale)
    return ('%+d' % value) if text[0] in '+-' else str(value)


def _collapse(cells):
    """DIGEST_V4: k >= 2 consecutive identical `^` or `=` cells become one `^k` / `=k` cell (V7: `?k`)."""
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


def _derived_order(columns, facts=NO_FACTS):
    """Derived columns are recomputed after the literal ones: the V8 lengths first (they read decoded lists only), then
    the adapter's book columns and the character counts (they read literals only), then ROW_DERIVED in its declared
    order (a rule may read an earlier rule), then the rules that also read the previous row."""
    lengths = [c for c in columns if c in facts.lengths]
    first = [c for c in columns if c not in facts.lengths and (c in DERIVED or c.startswith(('action_counts.', 'side_counts.')))]
    rest = sorted((c for c in columns if c not in facts.lengths and c in _ROW_DERIVED_INDEX), key=_ROW_DERIVED_INDEX.get)
    return lengths + first + rest + [c for c in columns if c not in facts.lengths and c in PREV_DERIVED]


def parse_table(block, context=None):
    lines = block.split('\n')
    if lines and lines[-1] == '':
        lines.pop()                        # the block's final newline only; an empty row line (every column constant or derived) stays
    reader = Lines(lines)
    h = Header(reader)
    dictionary = []
    read_dictionary(reader, lambda number, text: dictionary.append(entry_value(text)))
    cross = {c: CROSS_DERIVED[(h.name, c)] for c, mark in h.whole.items() if mark == '=' and (h.name, c) in CROSS_DERIVED and (context or {}).get(CROSS_DERIVED[(h.name, c)][0]) is not None}
    body = lines[reader.index:]
    if len(body) < h.n:
        raise ValueError(f'table {h.name}: {h.n} rows declared, {len(body)} present')
    decoder = RowDecoder(h, lambda number: copy.deepcopy(dictionary[number]))
    rows = []
    for i, line in enumerate(body[:h.n]):
        try:
            row = decoder.decode(line, {c: _flatten(context[t][i])[col] for c, (t, col) in cross.items()})
        except ValueError as err:
            raise ValueError(f'table {h.name} row {i}: {err}') from err
        rows.append(_unflatten(row))
    return h.name, rows


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


def digest_header(receipt):
    """Small shared header; table/document streaming does not change its bytes."""
    lines = ['# Derivation digest ' + SCHEMA + ' (Frankie\'s own calculations on this cycle\'s rows; written by the session code; whole, no '
             'limits; every derived field, exact; `=` = the column the adapter computes from this row (spread = best_ask - best_bid, '
             'mid = 0.5*(best_bid + best_ask), depth_imbalance_full = (bid_depth_full - ask_depth_full)/(bid_depth_full + ask_depth_full)), '
             'checked equal before it is written that way, and likewise every structure column the pinned producer computes from the '
             'row\'s own action/side strings, order-id lists and counts (terminal action/side, component and character counts, mirror '
             'identity, fill disposition class and signature, price span, carried family, discovery status, candidate_family_id = '
             '"ow-" + sha256 of the canonical descriptor); tables: one header line, tab-separated rows; `^` = the same value as the '
             'previous row in this column; `?` = absent (the row carries no value at this path); every integer column whose name ends in '
             + ', '.join(DELTA_KEYS) + ' is written as a signed delta from the previous row\'s integer in that column (absolute when '
             'there is none); floats as shortest round-trip decimals; `-` = none; T/F = booleans; `S...` = a string; '
             '`@n` = dictionary entry n (only a value that repeats in the table is in the dictionary); `J...` = JSON; `U...` = a tuple, as JSON; `I<first>,<+d>,...` = '
             'a list of integers as its first value (a signed delta from the previous row\'s first when one exists) then successive '
             'differences; `K<i>,<j>` = the list of this row\'s order_ids at those positions; `~<d>` = ts_event as an offset from this '
             'row\'s ts_recv; a header column written `=name` is derived on every row and omitted from the rows, `^name` holds one '
             'value on every row (given on the `constants:` line) and is omitted too; `transition` = the sign of each book field\'s '
             'change from the previous frame, recomputed; roll20 = n/d, the exact fraction (b-s)/(b+s) of the '
             'trailing 20-second buy and sell sums, its float being that division; DIGEST_V4 on top: cells are separated by one '
             'space when no cell of the table holds a space (`sep=space` in the header, else tabs); `^k` / `=k` / `?k` (V7) = k consecutive '
             '`^` / `=` / `?` cells; a bare `n/d` float cell is the IEEE division of those two integers, which IS the stored float exactly '
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
             'cell; the three whole ledgers stay on the box under work/bedrock/ledgers/, witnessed by name, bytes and sha256 in the bundle index); '
             'DIGEST_V8 on top (every earlier form still applies): a column on the `shapes:` line (`name=k1,k2,...`) holds lists of '
             'objects written keys-once, `R` + the objects joined by `;`, each object its values in that key order joined by `,`, each '
             'value read against the previous object (for the first, the last object of the previous row\'s list): `^` the same value, a '
             'signed delta for an integer key ending in recv_ns / event_ns, `<i` the same integer as key i of this object, `?` absent, '
             '`^k` / `?k` runs, else `-` T F an integer, a float, `S<text>` or `J<json>`; `P<first>:<lo>:<width>:<digits>` = a list of '
             'integers as its first value (as in `I`) then each successive difference = one fixed-width decimal field + lo; `<i` in a '
             'row = the same integer as this row\'s column i (0-based over the header\'s columns); a column on the `lengths:` line '
             '(`name=list`) is the length of that list column, written `=` like any derived cell; columns are ordered by how many rows '
             'carry them; a repeated value is in the dictionary only when that is shorter than writing it each time; DIGEST_V9 on '
             'top: `L<item>,<item>,...` = a list of plain values, each item `-` T F an integer, a float, `S<text>` or `J<json>`, and '
             '`<item>*k` = that item k times in a row (`L` alone = the empty list); inside `I` a `<d>*k` = that difference k times in a '
             'row; a dictionary entry `@n=` is spelled like a cell (`S<text>`, `J<json>` or `L...`); `"k` = the cell just before it, k more '
             'times; `$<d>` = the previous row\'s string in this column with its trailing number moved by d (same prefix); inside a '
             'keys-once object `~<d>` = that key\'s integer in the previous object plus d; `O<first>:<lo>:<width>:<digits>:<i>=<d>;...` '
             '= `P` with the listed differences (0-based) given apart and their fields zeros', '',
             f'Rows: {receipt["rows"]["path"]} ({receipt["rows"]["count"]} entries, kinds {receipt["rows"]["kinds"]}, head {receipt["rows"]["head"][:16]}...; '
             f'head equals the request source_hash: {receipt["rows"]["head_is_request_source_hash"]}).',
             f'INPUT records fed to the V4 adapter: {receipt["input_records"]}; legacy control rows projected: {receipt["legacy_rows"]}; '
             f'F_LAST groups closed: {receipt["f_last_groups"]}; adapter failures: {receipt["failure_count"]}.', '',
             '## Layer status (pin group ' + receipt['pin_group'] + ')']
    for name, value in receipt['layers'].items():
        lines.append(f'- {name}: {value["status"]}' + (f' ({value["reason"]})' if value.get('reason') else '') + f'; producer: {value.get("producer")}; file {value["path"]} sha256 {value["sha256"][:16]}')
    return '\n'.join(lines) + '\n\n'


def bedrock_header(derived, total, verdict):
    head = ['', '## Bedrock (the pinned producers\' own traversal on this cycle\'s rows, projected by their crosswalk; '
            f'{derived} of {total} layers derived; every derived fact once, whole; the traversal\'s own verdict over this slice: '
            f'{verdict.get("verdict")}' + (f', failed gates {", ".join(verdict["failed_gates"])}' if verdict.get('failed_gates') else ', no failed gate') + ')', '']
    return '\n'.join(head) + '\n'


def digest_text(receipt, layers, prices, frames, structures, roll, first, buys, sells, bedrock=None):
    """The whole digest: layer status, then every derived layer as a dense exact table (all fields); with `bedrock`
    ({layer: file}), the V6 bedrock tables after them."""
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
    text = digest_header(receipt) + render_layers(tables)
    if bedrock:
        derived = sum(1 for f in bedrock.values() if f.get('status') == 'derived')
        verdict = next((f.get('traversal') for f in bedrock.values() if isinstance(f.get('traversal'), dict)), None) or {}
        text += bedrock_header(derived, len(bedrock), verdict) + render_layers(bedrock_tables(bedrock))
    return text
