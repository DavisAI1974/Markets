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
roll20 is (b - s) / (b + s) over the trailing window of per-second volumes (native_roll20.roll20): its float is the
IEEE division of two integers, so the per-second table carries the exact fraction `n/d` and the float is recomputed
from it (checked equal to the producer's float for every second).
"""
from __future__ import annotations

import json
import math
import re

DELTA_KEYS = ('ts_recv_ns', 'ts_event_ns', 'ts_recv', 'ts_event', 'second')
NONE, TRUE, FALSE = '-', 'T', 'F'


def _flatten(row, prefix=''):
    out = {}
    for k, v in row.items():
        key = f'{prefix}{k}'
        if isinstance(v, dict):
            out.update(_flatten(v, key + '.'))
        else:
            out[key] = v
    return out


def _cell(v, dictionary, order):
    if v is None:
        return NONE
    if v is True:
        return TRUE
    if v is False:
        return FALSE
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v):
            return 'nan'
        return repr(v)
    if isinstance(v, str):
        if v not in dictionary:
            dictionary[v] = len(order)
            order.append(v)
        return '@%d' % dictionary[v]
    return 'J' + json.dumps(v, separators=(',', ':'), sort_keys=True)


def render_table(name, rows):
    """rows: list of dicts (nested dicts flattened). Returns the text block."""
    flat = [_flatten(r) for r in rows]
    columns = []
    for r in flat:
        for k in r:
            if k not in columns:
                columns.append(k)
    dictionary, order, lines = {}, [], []
    previous = {}
    for r in flat:
        cells = []
        for c in columns:
            v = r.get(c, None)
            missing = c not in r
            if missing:
                cells.append('?')
                continue
            if c.endswith(DELTA_KEYS) and isinstance(v, int) and not isinstance(v, bool) and isinstance(previous.get(c), int):
                cells.append('+%d' % (v - previous[c]) if v >= previous[c] else '%d' % (v - previous[c]))
            else:
                cells.append(_cell(v, dictionary, order))
            if isinstance(v, int) and not isinstance(v, bool):
                previous[c] = v
        lines.append('\t'.join(cells))
    head = [f'### table {name}: {len(rows)} rows, columns: ' + '\t'.join(columns)]
    if order:
        head.append('dictionary: ' + '\t'.join('@%d=%s' % (i, json.dumps(s)) for i, s in enumerate(order)))
    return '\n'.join(head + lines) + '\n'


def parse_table(block):
    lines = block.rstrip('\n').split('\n')
    m = re.match(r'### table (\S+): (\d+) rows, columns: (.*)$', lines[0])
    name, n, columns = m.group(1), int(m.group(2)), m.group(3).split('\t') if m.group(3) else []
    idx = 1
    dictionary = []
    if idx < len(lines) and lines[idx].startswith('dictionary: '):
        for item in lines[idx][len('dictionary: '):].split('\t'):
            k, _, val = item.partition('=')
            dictionary.append(json.loads(val))
        idx += 1
    rows, previous = [], {}
    for line in lines[idx:idx + n]:
        cells = line.split('\t') if columns else []
        row = {}
        for c, cell in zip(columns, cells):
            if cell == '?':
                continue
            if cell == NONE:
                v = None
            elif cell == TRUE:
                v = True
            elif cell == FALSE:
                v = False
            elif cell.startswith('@'):
                v = dictionary[int(cell[1:])]
            elif cell.startswith('J'):
                v = json.loads(cell[1:])
            elif cell == 'nan':
                v = float('nan')
            elif (cell.startswith('+') or (cell.startswith('-') and c.endswith(DELTA_KEYS))) and isinstance(previous.get(c), int) and re.fullmatch(r'[+-]\d+', cell):
                v = previous[c] + int(cell)
            elif re.fullmatch(r'-?\d+', cell):
                v = int(cell)
            else:
                v = float(cell)
            if isinstance(v, int) and not isinstance(v, bool):
                previous[c] = v
            row[c] = v
        rows.append(_unflatten(row))
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
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b and type(a) is type(b)


def render_layers(tables):
    """tables: {name: list_of_row_dicts}. Every table is rendered, parsed back and compared; a mismatch raises."""
    out = []
    for name, rows in tables.items():
        block = render_table(name, rows)
        parsed_name, parsed = parse_table(block)
        if parsed_name != name or not _same(parsed, [dict(r) for r in rows]):
            raise ValueError(f'digest table {name} does not round-trip')
        out.append(block)
    return '\n'.join(out)


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


def digest_text(receipt, layers, prices, frames, structures, roll, first, buys, sells):
    """The whole digest: layer status, then every derived layer as a dense exact table (all fields)."""
    lines = ['# Derivation digest DIGEST_V2 (Frankie\'s own calculations on this cycle\'s rows; written by the session code; whole, no '
             'limits; every derived field, exact; tables: one header line, tab-separated rows, integer timestamp columns as deltas '
             'from the previous row (first row absolute), floats as shortest round-trip decimals, `-` = none, T/F = booleans, '
             '`@n` = dictionary string n, `J...` = JSON; roll20 = n/d, the exact fraction (b-s)/(b+s) of the trailing 20-second '
             'buy and sell sums, its float being that division)', '',
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
    return '\n'.join(lines) + '\n\n' + render_layers(tables)
