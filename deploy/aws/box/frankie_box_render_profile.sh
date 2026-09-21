# Read-only: profile EVERY category the BOSS still reads after the lossless render (Greg, 2026-09-21 12:2xZ: "Are there
# any other categories on root that we should try. And remember to stack the stacks"), with the pinned Granite tokenizer:
# (1) tokenizer facts for the spellings a stack could choose; (2) the identity render of state / forecast / controller,
# token cost per JSON path (top contributors); (3) the critic's stacked envelope: tokens by node tag, and whether the
# pinned codec re-encodes its decoded root byte-identically (the gate for any re-spelling); (4) the large text leaves
# (source files delivered as configuration): whether their bytes equal a file in a checkout the box holds; (5) the head
# of prompt.md, section by section: shape, JSON lines, repeated prefixes; (6) the DIGEST_V3 tables column by column:
# tokens, cell marks, the separator's cost, run-length and fraction candidates, integer scale. Changes nothing;
# writes only under /opt/frankie-box/tmp/.
set -u
ROOT=/opt/frankie-box; T="$ROOT/tmp"; SAMPLES="${SAMPLES:-0}"; mkdir -p "$T"
"$ROOT/venv/bin/python" -c "import tokenizers" 2>/dev/null || "$ROOT/venv/bin/pip" install -q tokenizers >/dev/null 2>&1
TOK="$T/granite_tokenizer.json"
[ -s "$TOK" ] || curl -fsS -m 120 -L -o "$TOK" "https://huggingface.co/ibm-granite/granite-4.2-8b/resolve/f8de16cdcdbc6c779ca517604e050d82cc119e44/tokenizer.json"
M="$ROOT/tmp/markets-measure"; REF="${MARKETS_REF:-claude/cycle-0-frankie-box-rerun-od5sxk}"
if [ -d "$M/.git" ]; then git -C "$M" fetch -q --depth 1 origin "$REF" && git -C "$M" checkout -q FETCH_HEAD; else git clone -q --depth 1 --branch "$REF" https://github.com/DavisAI1974/Markets.git "$M"; fi
echo "profile checkout $(git -C "$M" rev-parse --short HEAD)"
export ROOT TOK M SAMPLES
"$ROOT/venv/bin/python" - <<'PY'
import base64, collections, hashlib, json, math, os, re, sys
from fractions import Fraction
sys.path.insert(0, os.environ['M']); sys.path.insert(0, os.environ['M'] + '/deploy/aws/box')
import frankie_box_reading_render as R
from tokenizers import Tokenizer
tok = Tokenizer.from_file(os.environ['TOK'])
def tk(text):
    return sum(len(tok.encode(text[i:i + (1 << 20)], add_special_tokens=False).ids) for i in range(0, len(text), 1 << 20))
def js(v):
    return json.dumps(v, separators=(',', ':'), ensure_ascii=True, default=R._jsonable)
ROOTD = os.environ['ROOT']
print('\n== (1) tokenizer facts: tokens of each spelling')
for s in ['\t', ' ', '\n', '^', '=', '-', '^\t^\t^\t^', '^4', '\t^\t^\t^', '["V","ts_event"]', 'V ts_event', '["D",1633298400329344207,[123,456,789]]',
          'D 1633298400329344207 123 456 789', '1633298400329344207', '+123456789', '+123456', '5412000000000', '5412000', '-0.12345678901234567',
          '-37/301', '0.5', 'T', 'F', '@7', 'S', 'd17184c95a2d55198053299d3cbcea8a9d19a832df0c492ee3bf361e88e0441a',
          '0XGEyUt2VUZgFMpnT0tvOzah2bmYqmm0vTUvKw7X8uQ=', '{"$ref":"', '"ts_recv_ns":', 'ts_recv_ns', '[1,2,3,4,5,6,7,8]', '1 2 3 4 5 6 7 8', '1,2,3,4,5,6,7,8']:
    print('   %-45r %3d' % (s, tk(s)))

data = open(ROOTD + '/request/prompt.md', 'rb').read()
marker = data.find(b'## BOSS/Granite producer evidence'); head = data[:marker].decode('utf-8', 'replace'); block = data[marker:]; start = block.find(b'{')
payload = json.loads(block[start:].decode('utf-8'))
members = {}
for key in ('manifest_base64', 'source_binding_base64', 'mapping_evidence_base64'):
    if isinstance(payload.get(key), str): members[key.replace('_base64', '')] = base64.b64decode(payload[key])
for name, b64 in (payload.get('files_base64') or {}).items():
    if isinstance(b64, str): members['files/' + name] = base64.b64decode(b64)
text, rep = R.render(members, tensor_mode='identity', tokenizer=None)
docs = {}
for m in re.finditer(r'\n### member (\S+) \(.*?\n#### document 0\n```json\n(.*?)\n```\n', text, re.S):
    docs[m.group(1)] = json.loads(m.group(2))

print('\n== (2) identity render: token cost per path (paths of >= 800 tokens; leaf kind)')
def walk(node, path, acc, depth):
    t = tk(js(node))
    if t >= 800 or depth == 0:
        kind = ('$' + node.get('$decoded', node.get('$tensors') and 'tensors' or '?')) if isinstance(node, dict) and any(k.startswith('$') for k in node) else type(node).__name__
        acc.append((t, len(js(node)), path, kind))
    if isinstance(node, dict) and depth < 6:
        for k, v in node.items(): walk(v, path + '.' + k, acc, depth + 1)
    elif isinstance(node, list) and depth < 6 and len(node) <= 64:
        for i, v in enumerate(node): walk(v, path + '[%d]' % i, acc, depth + 1)
for name in ('files/state.c15.json', 'files/forecast-000000.bin', 'files/controller.c15.jsonl'):
    if name not in docs: print('   (no document parsed for', name, ')'); continue
    acc = []; walk(docs[name], name, acc, 0)
    print('  --', name, 'document 0 total tokens', tk(js(docs[name])))
    for t, b, p, k in sorted(acc, reverse=True)[:24]:
        print('   %7d tok %8d B  %-9s %s' % (t, b, k, p[-110:]))

print('\n== (3) the stacked envelope (critic snapshot): tokens by tag; codec re-encode check')
from research.kalshi.frankie_boss import granite_context_stacked as stacked
snap = json.loads(members['files/critic-snapshot.txt'].decode('utf-8'))
env = snap['codec']
env_text = stacked._text(env)
print('   envelope bytes', len(env_text.encode()), 'tokens', tk(env_text), '; snapshot member tokens', tk(members['files/critic-snapshot.txt'].decode('utf-8')))
tags = collections.Counter(); tagtok = collections.Counter(); leafkinds = collections.Counter()
def tw(node, depth=0):
    if isinstance(node, list) and node and isinstance(node[0], str) and node[0] in 'MLTCSQNIDREBVFHXG' and len(node[0]) == 1:
        tag = node[0]; tags[tag] += 1
        if tag in 'VFHXG': tagtok[tag] += tk(stacked._text(node)); leafkinds[(tag, type(node[1]).__name__)] += 1; return
        for v in node[1:]: tw(v, depth + 1)
    elif isinstance(node, list):
        for v in node: tw(v, depth + 1)
tw(env['data'])
print('   node tags', dict(tags)); print('   leaf tokens by tag', dict(tagtok), 'leaf kinds', dict(leafkinds))
ctab = []
def ct(node):
    if isinstance(node, list) and node and node[0] == 'C' and isinstance(node[2], list):
        ctab.append((len(node[2]), tk(stacked._text(node)), node[2][:6]))
    if isinstance(node, list):
        for v in node: ct(v)
ct(env['data']); print('   C tables (fields, tokens, first fields):', [(n, t, f) for n, t, f in sorted(ctab, key=lambda x: -x[1])[:6]])
try:
    transformed = stacked._decode(env['data'], stacked._Budget(stacked.DEFAULT_LIMITS))
    recipe = transformed['packet_recipe']
    root = stacked.decode(env)
    again = stacked.encode(root, scope_public=(recipe or {}).get('scope_public'), prefix_seed=(recipe or {}).get('prefix_seed'))
    print('   re-encode of the decoded root equals the delivered envelope:', stacked._text(again) == env_text, '; recipe present:', recipe is not None,
          '; root keys', list(root)[:10], '; records', len(root.get('records', []) if isinstance(root, dict) else []))
except Exception as err:
    print('   re-encode check failed:', type(err).__name__, str(err)[:200])

print('\n== (4) large text leaves vs files in the box checkouts (sha256 equality, with and without a trailing newline)')
index = {}
for base in (ROOTD + '/markets', ROOTD + '/producers', os.environ['M']):
    for dp, dn, fn in os.walk(base):
        if '/.git' in dp or '/venv' in dp or '/node_modules' in dp: continue
        for f in fn:
            p = os.path.join(dp, f)
            try:
                if os.path.getsize(p) > 2_000_000: continue
                raw = open(p, 'rb').read()
            except OSError: continue
            index.setdefault(hashlib.sha256(raw).hexdigest(), p.replace(ROOTD + '/', '')); index.setdefault(hashlib.sha256(raw.rstrip(b'\n')).hexdigest(), p.replace(ROOTD + '/', '') + ' (rstrip)')
print('   indexed files', len(index))
def leaves(node, path, out):
    if isinstance(node, dict):
        if node.get('$decoded') == 'utf8' and isinstance(node.get('value'), str):
            out.append((node['bytes'], path, node['value'])); return
        for k, v in node.items(): leaves(v, path + '.' + k, out)
    elif isinstance(node, list):
        for i, v in enumerate(node): leaves(v, path + '[%d]' % i, out)
    elif isinstance(node, str) and len(node) >= 1500:
        out.append((len(node.encode()), path, node))
for name in ('files/state.c15.json', 'files/controller.c15.jsonl', 'files/forecast-000000.bin'):
    out = []; leaves(docs.get(name, {}), name, out)
    for b, p, s in sorted(out, reverse=True)[:14]:
        raw = s.encode('utf-8'); h = hashlib.sha256(raw).hexdigest(); h2 = hashlib.sha256(raw.rstrip(b'\n')).hexdigest(); h3 = hashlib.sha256(raw + b'\n').hexdigest()
        print('   %8d B %6d tok  %-95s -> %s' % (b, tk(s), p[-95:], index.get(h) or index.get(h2) or index.get(h3) or 'no file match'))

print('\n== (5) the head of prompt.md: %d bytes, %d tokens; sections >= 2 KB' % (len(head.encode()), tk(head)))
hs = [(m.start(), m.group(0).strip()) for m in re.finditer(r'^#{1,3} .*$', head, re.M)]
bounds = list(zip([0] + [s for s, _ in hs], [s for s, _ in hs] + [len(head)]))
titles = ['(preamble)'] + [t for _, t in hs]
for (s, e), title in zip(bounds, titles):
    sect = head[s:e]
    if len(sect.encode()) < 2048: continue
    lines = sect.split('\n')
    jl, keysets, mdrows, hexes = 0, collections.Counter(), 0, re.findall(r'\b[0-9a-f]{64}\b', sect)
    prefixes = collections.Counter(l[:24] for l in lines if len(l) > 24)
    for l in lines:
        ls = l.strip()
        if ls.startswith('{'):
            try: obj = json.loads(ls); jl += 1; keysets[tuple(sorted(obj))[:12]] += 1
            except Exception: pass
        if ls.startswith('|'): mdrows += 1
    print('  -- %7d B %6d tok %5d lines  %s' % (len(sect.encode()), tk(sect), len(lines), title[:90]))
    print('     json lines %d (key sets %d: %s); md table rows %d; 64-hex %d (distinct %d)' % (jl, len(keysets), [','.join(k)[:80] for k, _ in keysets.most_common(2)], mdrows, len(hexes), len(set(hexes))))
    print('     repeated line prefixes:', [(p[:24], n) for p, n in prefixes.most_common(4) if n >= 3])
    if os.environ.get('SAMPLES') == '1':          # raw head lines only on request: the workflow log is public
        for l in lines[1:4]: print('     |', l[:150])

print('\n== (6) DIGEST_V3 tables, column by column')
dense_path = os.path.join(ROOTD, 'tmp', 'derivation-digest-dense.md')
if not os.path.exists(dense_path):
    print('   no dense digest at', dense_path, '(run frankie_box_reading_render_measure.sh first)')
else:
    dense = open(dense_path, encoding='utf-8').read()
    for block in re.split(r'(?m)^### table ', dense)[1:]:
        lines = block.rstrip('\n').split('\n')
        m = re.match(r'(\S+): (\d+) rows, columns: (.*)$', lines[0]); name, n = m.group(1), int(m.group(2))
        if n < 100: continue
        declared = m.group(3).split('\t'); kept = [c for c in declared if c[:1] not in '=^']
        idx = 1
        while idx < len(lines) and (lines[idx].startswith('constants: ') or lines[idx].startswith('dictionary: ')): idx += 1
        rows = [l.split('\t') for l in lines[idx:idx + n]]
        body = '\n'.join(lines[idx:idx + n])
        print('  --', name, n, 'rows; block tokens', tk(block), '; header+dictionary tokens', tk('\n'.join(lines[:idx])), '; rows tokens', tk(body), '; tabs', body.count('\t'), '; kept columns', len(kept))
        any_space = any(' ' in c for r in rows for c in r)
        print('     rows with tabs->spaces: %d tokens (a cell contains a space: %s); tabs->"|": %d' % (tk(body.replace('\t', ' ')), any_space, tk(body.replace('\t', '|'))))
        def collapse(r):
            out, i = [], 0
            while i < len(r):
                j = i
                while j < len(r) and r[j] == r[i] and r[i] in ('^', '=', '-'): j += 1
                if j - i >= 2: out.append(r[i] + str(j - i)); i = j
                else: out.append(r[i]); i += 1
            return out
        collapsed = '\n'.join('\t'.join(collapse(r)) for r in rows)
        print('     rows with ^/=/- runs collapsed (^k): %d tokens; with runs collapsed AND tabs->spaces: %d' % (tk(collapsed), tk(collapsed.replace('\t', ' '))))
        cols = collections.defaultdict(lambda: dict(tok=0, same=0, derived=0, none=0, lit=0, frac_ok=0, frac_tok=0, lit_tok=0, scale=None, floats=0))
        for r in rows:
            for c, cell in zip(kept, r):
                d = cols[c]; d['tok'] += tk(cell)
                if cell == '^': d['same'] += 1
                elif cell == '=': d['derived'] += 1
                elif cell == '-': d['none'] += 1
                else:
                    d['lit'] += 1; d['lit_tok'] += tk(cell)
                    if re.fullmatch(r'[+-]?\d+', cell):
                        v = abs(int(cell))
                        if v:
                            k = 0
                            while v % 10 == 0 and k < 12: v //= 10; k += 1
                            d['scale'] = k if d['scale'] is None else min(d['scale'], k)
                    elif re.fullmatch(r'-?\d+\.\d+(e-?\d+)?', cell):
                        d['floats'] += 1; x = float(cell)
                        fr = Fraction(x).limit_denominator(1_000_000)
                        if fr.denominator > 1 and float(fr.numerator) / float(fr.denominator) == x:
                            d['frac_ok'] += 1; d['frac_tok'] += tk('%d/%d' % (fr.numerator, fr.denominator)) - tk(cell)
        for c in sorted(kept, key=lambda c: -cols[c]['tok'])[:14]:
            d = cols[c]
            print('     %-46s %6d tok  ^%-4d =%-4d -%-4d lit %-4d (lit tok %5d) int-scale 10^%s  floats %d exact-fraction %d (delta %+d tok)' % (
                c[-46:], d['tok'], d['same'], d['derived'], d['none'], d['lit'], d['lit_tok'], d['scale'], d['floats'], d['frac_ok'], d['frac_tok']))
        if os.environ.get('SAMPLES') == '1':
            for r in rows[1:3]: print('     |', '\t'.join(r)[:200].replace('\t', ' <t> '))
PY
