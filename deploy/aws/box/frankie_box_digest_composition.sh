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
    if cell == '?': return 'absent'
    if cell.startswith('='): return 'derived'
    if cell.startswith('@') and cell[1:].isdigit(): return 'dict_ref'
    if HEX.match(cell): return 'hex'
    if NUM.match(cell): return 'number'
    if cell.startswith(('[', '{', '"')): return 'json'
    return 'text'

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
            cols = head.split('columns: ', 1)[1].rstrip('\n').split('\t') if 'columns: ' in head else []
            current = tables.setdefault(name, dict(name=name, bytes=0, header_bytes=0, rows=0, sep=sep, columns=cols,
                                                    sample=[], header_lines=[]))
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
    for row in t['sample']:
        cells = row.split(t['sep'])
        ids = tok.encode(row, add_special_tokens=False).ids
        sample_bytes += len(row.encode()) + 1
        sample_tokens += len(ids) + 1
        for i, cell in enumerate(cells):
            col = t['columns'][i] if i < len(t['columns']) else '#%d' % i
            n = len(tok.encode(cell, add_special_tokens=False).ids) if cell else 0
            b = len(cell.encode())
            per_col_bytes[col] += b; per_col_tokens[col] += n
            k = kind(cell); kind_bytes[k] += b; kind_tokens[k] += n
    body_bytes = t['bytes'] - t['header_bytes']
    tpb = sample_tokens / sample_bytes if sample_bytes else 0.0
    scale = (body_bytes / sample_bytes) if sample_bytes else 0.0
    head_tokens = 0
    report['tables'].append(dict(
        name=t['name'], rows=t['rows'], columns=len(t['columns']), bytes=t['bytes'], header_bytes=t['header_bytes'],
        dictionary_bytes=t.get('dictionary_bytes', 0), sample_rows=len(t['sample']), tokens_per_byte_sample=round(tpb, 4),
        tokens_estimate=int(body_bytes * tpb) + int(t['header_bytes'] * 0.5),
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
    print('TABLE %-40s rows %9d cols %4d bytes %12d tok_est %11d tpb %.3f dict %d' % (
        t['name'], t['rows'], t['columns'], t['bytes'], t['tokens_estimate'], t['tokens_per_byte_sample'], t['dictionary_bytes']))
    print('   kinds ' + json.dumps({k: v['tokens_est'] for k, v in sorted(t['kinds'].items(), key=lambda kv: -kv[1]['tokens_est'])}))
    print('   top columns ' + json.dumps(t['top_columns'][:8]))
print('REPORT', out)
PY
