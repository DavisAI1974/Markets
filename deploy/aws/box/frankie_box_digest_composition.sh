# Where the Monday digest's tokens are (Greg, 2026-09-28: "every token stack possible and find some new ones").
# Read-only. One streaming pass over derivation-digest-full.md: bytes, lines and rows per section/table, the header
# lines (constants, scales, dictionary) per table; every EVERY-th row of each table is kept as a sample and tokenized
# with the pinned Granite tokenizer, per column and per cell kind (hex runs, digit runs, dictionary refs, absent '?',
# derived '=', text). Prints the ranking by estimated tokens. Canary-sized: the sample keeps the tokenizer to about a
# minute; bytes are exact, tokens are sample-extrapolated and labelled as such.
# Inputs: DIGEST (default the Monday ROOT digest), EVERY (default 400).
set -eu
export DIGEST="${DIGEST:-/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work/derivation-digest-full.md}"
export EVERY="${EVERY:-400}"
exec nice -n 5 /opt/frankie-box/venv/bin/python -B - <<'PY'
import hashlib, json, os, re, time
from collections import defaultdict
from pathlib import Path
from tokenizers import Tokenizer

DIGEST, EVERY = Path(os.environ['DIGEST']), int(os.environ['EVERY'])
raw = Path('/opt/frankie-box/tmp/granite_tokenizer.json').read_bytes()
if not hashlib.sha256(raw).hexdigest().startswith('883975314d587437'):
    raise SystemExit('pinned Granite tokenizer differs')
tok = Tokenizer.from_str(raw.decode())
HEX = re.compile(r'^[0-9a-f]{16,}$')
NUM = re.compile(r'^-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$')

def kind(cell):
    """Classify a DIGEST_V6 cell by its grammar prefix (frankie_box_digest_render / digest_stream)."""
    if cell == '?': return 'absent'
    if cell in ('^', '='): return 'same_or_derived'
    if cell == '-': return 'none'
    if cell in ('T', 'F'): return 'bool'
    head = cell[:1]
    if head == '@' and cell[1:].isdigit(): return 'dict_ref'
    if head in '+' or (head == '-' and cell[1:].replace('.', '', 1).isdigit()): return 'delta_or_negative'
    if head == '~': return 'paired_offset'
    if head in 'SJIKU' and len(cell) > 1: return {'S': 'string', 'J': 'json', 'I': 'int_list', 'K': 'positions', 'U': 'tuple'}[head]
    if '/' in cell and cell.replace('/', '', 1).lstrip('-').isdigit(): return 'fraction'
    if cell.isdigit():
        return 'int_16plus_digits' if len(cell) >= 16 else 'int'
    if NUM.match(cell): return 'number'
    return 'other'


def expanded(line, sep, kept):
    """Cells of one row matched to the kept columns; `^k` / `=k` runs expand to k single marks (TS._expanded)."""
    if not kept:
        return []
    out = []
    for cell in line.split(sep):
        count = int(cell[1:]) if len(cell) > 1 and cell[0] in '^=' and cell[1:].isdigit() else 1
        out.extend([(cell[0], True)] * count if count != 1 else [(cell, False)])
    return out if len(out) == len(kept) else None


t0 = time.time()
tables, order = {}, []
current = None
other = dict(bytes=0, lines=0, sample=[])
with DIGEST.open('r', encoding='utf-8', errors='replace', newline='\n') as handle:
    for line in handle:
        size = len(line.encode('utf-8'))
        if line.startswith('### table '):
            head = line[len('### table '):]
            name = head.split(':', 1)[0]
            sep = '\t' if 'sep=tab' in head else ' '
            declared = head.split('columns: ', 1)[1].rstrip('\n').split('\t') if 'columns: ' in head else []
            kept = [c for c in declared if c and c[0] not in '=^']
            current = tables.setdefault(name, dict(name=name, bytes=0, header_bytes=0, rows=0, sep=sep, columns=kept,
                                                    declared=len(declared), sample=[], header_lines=[], dict_sample=''))
            order.append(name)
            current['header_bytes'] += size
            current['bytes'] += size
            continue
        if line.startswith('#'):
            current = None
            other['bytes'] += size; other['lines'] += 1
            if other['lines'] % 50 == 0 and len(other['sample']) < 400:
                other['sample'].append(line)
            continue
        if current is None:
            other['bytes'] += size; other['lines'] += 1
            if other['lines'] % 50 == 0 and len(other['sample']) < 400:
                other['sample'].append(line)
            continue
        current['bytes'] += size
        if line.startswith(('constants: ', 'scales: ', 'dictionary: ')) and current['rows'] == 0:
            current['header_bytes'] += size
            current['header_lines'].append(line[:12] + '... %d bytes' % size)
            if line.startswith('dictionary: '):
                current['dictionary_bytes'] = current.get('dictionary_bytes', 0) + size
                current['dict_sample'] = line[:2_000_000]
            continue
        current['rows'] += 1
        if current['rows'] % EVERY == 1:
            current['sample'].append(line.rstrip('\n'))
read_seconds = time.time() - t0

total_bytes = DIGEST.stat().st_size
report = dict(schema='FRANKIE_DIGEST_COMPOSITION_V1', digest=str(DIGEST), bytes=total_bytes, every=EVERY,
              read_seconds=round(read_seconds, 1), tables=[], other=None)
t1 = time.time()
for t in tables.values():
    per_col_bytes, per_col_tokens = defaultdict(int), defaultdict(int)
    kind_bytes, kind_tokens = defaultdict(int), defaultdict(int)
    sample_bytes = sample_tokens = 0
    unmatched = 0
    for row in t['sample']:
        ids = tok.encode(row, add_special_tokens=False).ids
        sample_bytes += len(row.encode()) + 1
        sample_tokens += len(ids) + 1
        cells = expanded(row, t['sep'], t['columns'])
        if cells is None:
            unmatched += 1
            continue
        raw_cells = row.split(t['sep'])
        position = 0
        for cell in raw_cells:
            # the tokens of each written cell, counted with its separator (the separator is its own token before digits)
            n = len(tok.encode(t['sep'] + cell, add_special_tokens=False).ids) if cell else 1
            b = len(cell.encode()) + 1
            is_run = len(cell) > 1 and cell[0] in '^=' and cell[1:].isdigit()
            width = int(cell[1:]) if is_run else 1
            col = t['columns'][position] if position < len(t['columns']) else '#%d' % position
            label = ('run(%s x%d from %s)' % (cell[0], width, col)) if is_run else col
            per_col_bytes[label if not is_run else 'runs'] += b
            per_col_tokens[label if not is_run else 'runs'] += n
            k = 'run' if is_run else kind(cell)
            kind_bytes[k] += b; kind_tokens[k] += n
            position += width
    t['unmatched'] = unmatched
    body_bytes = t['bytes'] - t['header_bytes']
    tpb = sample_tokens / sample_bytes if sample_bytes else 0.0
    scale = (body_bytes / sample_bytes) if sample_bytes else 0.0
    head_tokens = 0
    report['tables'].append(dict(
        name=t['name'], rows=t['rows'], columns=len(t['columns']), bytes=t['bytes'], header_bytes=t['header_bytes'],
        dictionary_bytes=t.get('dictionary_bytes', 0), sample_rows=len(t['sample']), tokens_per_byte_sample=round(tpb, 4),
        dictionary_tokens_per_byte=round(len(tok.encode(t['dict_sample'], add_special_tokens=False).ids) / max(1, len(t['dict_sample'].encode())), 4) if t['dict_sample'] else None,
        tokens_estimate=int(body_bytes * tpb) + int(t['header_bytes'] * ((len(tok.encode(t['dict_sample'], add_special_tokens=False).ids) / max(1, len(t['dict_sample'].encode()))) if t['dict_sample'] else 0.5)),
        unmatched_sample_rows=t['unmatched'], declared_columns=t['declared'],
        top_columns=sorted(((c, int(per_col_tokens[c] * scale), per_col_bytes[c]) for c in per_col_tokens),
                           key=lambda x: -x[1])[:12],
        kinds={k: dict(tokens_est=int(kind_tokens[k] * scale), sample_bytes=kind_bytes[k]) for k in kind_tokens}))
ob = other['bytes']
osample = ''.join(other['sample'])
otpb = (len(tok.encode(osample, add_special_tokens=False).ids) / max(1, len(osample.encode()))) if osample else 0.0
report['other'] = dict(bytes=ob, lines=other['lines'], tokens_per_byte_sample=round(otpb, 4), tokens_estimate=int(ob * otpb))
report['tables'].sort(key=lambda x: -x['tokens_estimate'])
report['tokens_estimate_total'] = sum(t['tokens_estimate'] for t in report['tables']) + report['other']['tokens_estimate']
report['tokenize_seconds'] = round(time.time() - t1, 1)
out = Path('/opt/frankie-box/work/digest-canary') / ('composition-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '.json')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=1))
print('TOTAL bytes %d, tokens_est %d, read %.0fs, tokenize %.0fs' % (total_bytes, report['tokens_estimate_total'],
      read_seconds, report['tokenize_seconds']))
print('OTHER (non-table) bytes %d tokens_est %d' % (ob, report['other']['tokens_estimate']))
for t in report['tables'][:25]:
    print('TABLE %-40s rows %9d kept %4d/%4d bytes %12d tok_est %11d tpb %.3f dict %d (tpb %s) unmatched %d' % (
        t['name'], t['rows'], t['columns'], t['declared_columns'], t['bytes'], t['tokens_estimate'], t['tokens_per_byte_sample'],
        t['dictionary_bytes'], t['dictionary_tokens_per_byte'], t['unmatched_sample_rows']))
    print('   kinds ' + json.dumps({k: v['tokens_est'] for k, v in sorted(t['kinds'].items(), key=lambda kv: -kv[1]['tokens_est'])}))
    print('   top columns ' + json.dumps(t['top_columns'][:8]))
print('REPORT', out)
PY
