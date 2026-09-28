# Token-stack canary on the Monday digest (Greg, 2026-09-28: "if they even reduce a little they're getting used").
# Read-only. One streaming pass over derivation-digest-full.md keeps, per table, the header, the dictionary line and
# a CONTIGUOUS block of BLOCK rows starting after SKIP rows (a block, not a stride, so deltas and runs see real
# neighbours). On each block it measures with the pinned Granite tokenizer:
#   v6          the rows as written;
#   v7          the same rows re-spelled under DIGEST_V7 (`?k` runs; deltas on *recv_ns / *event_ns / group_index);
#   json_keys   V7 plus every JSON list-of-objects / object cell (inline or through the dictionary) with its keys
#               declared once per column (the values in key order), the stack proposed next;
# and a census of the JSON and integer-list cells per column (shape, key sets, lengths, how often a list extends or
# repeats the previous row's), plus three sample rows per table (first 700 characters) to design the next forms.
# Textual simulations of lossless re-spellings, labelled as such; bytes and tokens are of the block only.
# Inputs: DIGEST (default the Monday ROOT digest), BLOCK (default 1500), SKIP (default 20000), TABLES (optional
# comma list; default every table).
set -eu
export DIGEST="${DIGEST:-/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work/derivation-digest-full.md}"
export BLOCK="${BLOCK:-1500}" SKIP="${SKIP:-20000}" TABLES="${TABLES:-}"
exec nice -n 5 /opt/frankie-box/venv/bin/python -B - <<'PY'
import hashlib, json, os, re, time
from collections import Counter, defaultdict
from pathlib import Path
from tokenizers import Tokenizer

DIGEST, BLOCK, SKIP = Path(os.environ['DIGEST']), int(os.environ['BLOCK']), int(os.environ['SKIP'])
WANT = {t for t in os.environ['TABLES'].split(',') if t}
raw = Path('/opt/frankie-box/tmp/granite_tokenizer.json').read_bytes()
if not hashlib.sha256(raw).hexdigest().startswith('883975314d587437'):
    raise SystemExit('pinned Granite tokenizer differs')
tok = Tokenizer.from_str(raw.decode())
ntok = lambda text: len(tok.encode(text, add_special_tokens=False).ids)
V7_DELTA = ('recv_ns', 'event_ns', 'group_index')
OLD_DELTA = ('ts_recv_ns', 'ts_event_ns', 'ts_recv', 'ts_event', 'second', 'price_raw_min', 'price_raw_max',
             'bid_depth_full', 'ask_depth_full', 'bid_order_count_full', 'ask_order_count_full')
INT = re.compile(r'-?\d+')

t0 = time.time()
tables = {}
current = None
with DIGEST.open('r', encoding='utf-8', errors='replace', newline='\n') as handle:
    for line in handle:
        if line.startswith('### table '):
            head = line[len('### table '):]
            name = head.split(':', 1)[0]
            if WANT and name not in WANT:
                current = None
                continue
            declared = head.split('columns: ', 1)[1].rstrip('\n').split('\t') if 'columns: ' in head else []
            current = tables.setdefault(name, dict(name=name, sep='\t' if 'sep=tab' in head else ' ', declared=declared,
                                                   kept=[c for c in declared if c and c[0] not in '=^'],
                                                   dictionary={}, rows=0, block=[]))
            continue
        if line.startswith('#'):
            current = None
            continue
        if current is None:
            continue
        if current['rows'] == 0 and line.startswith(('constants: ', 'scales: ')):
            continue
        if current['rows'] == 0 and line.startswith('dictionary: '):
            for item in line[len('dictionary: '):].rstrip('\n').split('\t'):
                key, _, value = item.partition('=')
                current['dictionary'][key] = value
            continue
        current['rows'] += 1
        if current['rows'] > SKIP and len(current['block']) < BLOCK:
            current['block'].append(line.rstrip('\n'))
        elif current['rows'] <= BLOCK:
            current.setdefault('head_block', []).append(line.rstrip('\n'))   # a table shorter than SKIP + BLOCK: its first rows
read_seconds = time.time() - t0


def expand(cells):
    out = []
    for cell in cells:
        if len(cell) > 1 and cell[0] in '^=?' and cell[1:].isdigit():
            out.extend([cell[0]] * int(cell[1:]))
        else:
            out.append(cell)
    return out


def collapse(cells, marks):
    out, i = [], 0
    while i < len(cells):
        j = i
        while cells[i] in marks and j < len(cells) and cells[j] == cells[i]:
            j += 1
        if j - i >= 2:
            out.append(cells[i] + str(j - i)); i = j
        else:
            out.append(cells[i]); i += 1
    return out


def json_of(cell, dictionary):
    """The JSON value behind a J cell or a dictionary reference to a JSON entry, else None."""
    text = None
    if cell.startswith('J'):
        text = cell[1:]
    elif cell.startswith('@') and cell[1:].isdigit():
        entry = dictionary.get(cell)
        if entry is not None and entry[:1] in '[{':
            text = entry
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def keys_of(value):
    if isinstance(value, dict):
        return ('obj',) + tuple(value)
    if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
        first = tuple(value[0])
        if all(tuple(x) == first for x in value):
            return ('rows',) + first
    return None


def spell_keys_once(value):
    """Values only, key order declared once per column: an object as `D` + values, a list of same-keyed objects as
    `R` + rows of values (';' between rows, ',' between values), each value as compact JSON."""
    dump = lambda v: json.dumps(v, separators=(',', ':'))
    if isinstance(value, dict):
        return 'D' + ','.join(dump(v) for v in value.values())
    return 'R' + ';'.join(','.join(dump(v) for v in row.values()) for row in value)


report = dict(schema='FRANKIE_DIGEST_STACKS_V1', digest=str(DIGEST), block=BLOCK, skip=SKIP, read_seconds=round(read_seconds, 1),
              note='textual re-spellings of real contiguous rows; tokens of the block only', tables=[])
for t in sorted(tables.values(), key=lambda x: -x['rows']):
    block = t['block'] or t.get('head_block', [])
    if not block:
        continue
    kept, sep, dictionary = t['kept'], t['sep'], t['dictionary']
    v6_text = '\n'.join(block) + '\n'
    rows = [expand(line.split(sep)) for line in block]
    good = [r for r in rows if len(r) == len(kept)]
    census = defaultdict(Counter)
    col_keys = defaultdict(Counter)
    prev_int, prev_list = {}, {}
    v7_rows, jk_rows = [], []
    json_dict_entries = set()
    examples = defaultdict(list)
    same_row = Counter()
    for r in good:
        longs = {}
        for j, cell in enumerate(r):
            if len(cell) >= 10 and cell.isdigit():
                longs.setdefault(cell, []).append(kept[j])
        for names in longs.values():
            for a in names[1:]:
                same_row['%s == %s' % (a, names[0])] += 1
        for j, cell in enumerate(r):
            if cell[:1] in 'JIK@' and len(examples[kept[j]]) < 2 and (cell[:1] != '@' or json_of(cell, dictionary) is not None):
                examples[kept[j]].append((cell if cell[:1] != '@' else cell + '=' + dictionary[cell])[:420])
        v7 = list(r)
        for j, c in enumerate(kept):
            cell = r[j]
            if c.endswith(V7_DELTA) and not c.endswith(OLD_DELTA):
                if INT.fullmatch(cell):
                    value = int(cell)
                    if j in prev_int:
                        v7[j] = '%+d' % (value - prev_int[j])
                    prev_int[j] = value
            value = json_of(cell, dictionary)
            if value is not None:
                shape = keys_of(value)
                census[c]['json_' + ('rows' if shape and shape[0] == 'rows' else 'obj' if shape else 'other')] += 1
                if shape:
                    col_keys[c][shape] += 1
                if cell.startswith('@'):
                    json_dict_entries.add(cell)
            elif cell.startswith('I') and len(cell) > 1:
                census[c]['int_list'] += 1
                parts = cell[1:].split(',')
                census[c]['int_list_items'] += len(parts)
            elif cell.startswith('K'):
                census[c]['positions'] += 1
            elif cell == '?':
                census[c]['absent'] += 1
            elif cell == '^':
                census[c]['same'] += 1
        v7_rows.append(v7)
    # keys-once: a column whose JSON cells (inline or dictionary) all share one key shape
    one_shape = {c: next(iter(k)) for c, k in col_keys.items() if len(k) == 1}
    for v7 in v7_rows:
        jk = list(v7)
        for j, c in enumerate(kept):
            if c in one_shape and v7[j].startswith('J'):
                value = json_of(v7[j], dictionary)
                if value is not None and keys_of(value) == one_shape[c]:
                    jk[j] = spell_keys_once(value)
        jk_rows.append(jk)
    v7_text = '\n'.join(sep.join(collapse(r, ('^', '=', '?'))) for r in v7_rows) + '\n'
    jk_text = '\n'.join(sep.join(collapse(r, ('^', '=', '?'))) for r in jk_rows) + '\n'
    # the dictionary entries this block references, as written and keys-once (the dictionary is written once per table)
    used = sorted(json_dict_entries)
    dict_v6 = '\t'.join('%s=%s' % (k, dictionary[k]) for k in used)
    dict_jk = []
    for k in used:
        value = json.loads(dictionary[k])
        shapes = [c for c, s in one_shape.items() if keys_of(value) == s]
        dict_jk.append('%s=%s' % (k, spell_keys_once(value) if shapes else dictionary[k]))
    dict_jk = '\t'.join(dict_jk)
    header_keys = ' '.join('%s:%s' % (c, ','.join(s[1:])) for c, s in one_shape.items())
    entry = dict(name=t['name'], rows=t['rows'], block_rows=len(block), matched_rows=len(good), columns=len(kept),
                 v6=dict(bytes=len(v6_text.encode()), tokens=ntok(v6_text)),
                 v7=dict(bytes=len(v7_text.encode()), tokens=ntok(v7_text)),
                 json_keys=dict(bytes=len(jk_text.encode()), tokens=ntok(jk_text) + ntok(header_keys)),
                 dictionary_json_entries=dict(count=len(used), v6_tokens=ntok(dict_v6) if dict_v6 else 0,
                                              keys_once_tokens=ntok(dict_jk) if dict_jk else 0),
                 census={c: dict(v) for c, v in census.items()},
                 key_shapes={c: [[list(s), n] for s, n in k.most_common(3)] for c, k in col_keys.items()},
                 kept_columns=kept, samples=[line[:700] for line in block[:3]],
                 same_row_equal=same_row.most_common(12), examples=dict(examples),
                 absent_every_block_row=[c for c in kept if census[c].get('absent', 0) == len(good)])
    report['tables'].append(entry)
    print('TABLE %-38s rows %9d block %5d/%5d  v6 %8d tok  v7 %8d tok (%.1f%%)  json_keys %8d tok (%.1f%%)  dictJSON %d: %d -> %d tok' % (
        t['name'], t['rows'], len(good), len(block), entry['v6']['tokens'], entry['v7']['tokens'],
        100.0 * (entry['v7']['tokens'] - entry['v6']['tokens']) / max(1, entry['v6']['tokens']),
        entry['json_keys']['tokens'], 100.0 * (entry['json_keys']['tokens'] - entry['v6']['tokens']) / max(1, entry['v6']['tokens']),
        len(used), entry['dictionary_json_entries']['v6_tokens'], entry['dictionary_json_entries']['keys_once_tokens']), flush=True)
    print('   columns %d' % len(kept))
    print('   census ' + json.dumps({c: dict(v) for c, v in census.items() if set(v) - {'same', 'absent'}})[:1500])
    print('   shapes ' + json.dumps(entry['key_shapes'])[:1500])
    for s in entry['samples'][:1]:
        print('   row ' + s[:300])
    print('   same-row equal ' + json.dumps(entry['same_row_equal']))
    print('   absent on every block row: %d of %d columns' % (len(entry['absent_every_block_row']), len(kept)))
    for c, cells in examples.items():
        for cell in cells:
            print('   eg %s: %s' % (c, cell))
out = Path('/opt/frankie-box/work/digest-canary') / ('stacks-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '.json')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=1))
print('READ %.0fs TOTAL %.0fs REPORT %s' % (read_seconds, time.time() - t0, out))
PY
