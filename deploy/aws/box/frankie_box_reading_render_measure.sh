# Read-only: build the LOSSLESS reading render (deploy/aws/box/frankie_box_reading_render.py) of the real delivered
# members on this box, in both tensor modes, and print the report: bytes and exact Granite tokens per member before
# and after, dictionary references, tensors, and the byte-exact reconstruction proof per member. Writes the renders
# under /opt/frankie-box/tmp/ for inspection; touches nothing under session/. Inputs: MODE (identity | values | both).
set -u
ROOT=/opt/frankie-box; T="$ROOT/tmp"; MODE="${MODE:-both}"; mkdir -p "$T"
"$ROOT/venv/bin/python" -c "import tokenizers" 2>/dev/null || "$ROOT/venv/bin/pip" install -q tokenizers >/dev/null 2>&1
TOK="$T/granite_tokenizer.json"
[ -s "$TOK" ] || curl -fsS -m 120 -L -o "$TOK" "https://huggingface.co/ibm-granite/granite-4.2-8b/resolve/f8de16cdcdbc6c779ca517604e050d82cc119e44/tokenizer.json"
# The running session's checkout ($ROOT/markets) is refreshed only by the session's own start; this measurement uses its
# own fresh checkout of the branch so the running session's code is never touched.
M="$ROOT/tmp/markets-measure"; REF="${MARKETS_REF:-claude/cycle-0-frankie-box-rerun-od5sxk}"
if [ -d "$M/.git" ]; then git -C "$M" fetch -q --depth 1 origin "$REF" && git -C "$M" checkout -q FETCH_HEAD; else git clone -q --depth 1 --branch "$REF" https://github.com/DavisAI1974/Markets.git "$M"; fi
echo "measure checkout $(git -C "$M" rev-parse --short HEAD)"
export ROOT TOK MODE M
"$ROOT/venv/bin/python" - <<'PY'
import base64, json, os, sys, time
sys.path.insert(0, os.environ['M']); sys.path.insert(0, os.environ['M'] + '/deploy/aws/box')
import frankie_box_reading_render as R
import re
from tokenizers import Tokenizer
tok = Tokenizer.from_file(os.environ['TOK'])
def tok_n(text):
    return sum(len(tok.encode(text[i:i + (1 << 20)], add_special_tokens=False).ids) for i in range(0, len(text), 1 << 20))
data = open(os.environ['ROOT'] + '/request/prompt.md', 'rb').read()
marker = data.find(b'## BOSS/Granite producer evidence'); block = data[marker:]; start = block.find(b'{')
payload = json.loads(block[start:].decode('utf-8'))
members = {}
for key in ('manifest_base64', 'source_binding_base64', 'mapping_evidence_base64'):
    if isinstance(payload.get(key), str): members[key.replace('_base64', '')] = base64.b64decode(payload[key])
for name, b64 in (payload.get('files_base64') or {}).items():
    if isinstance(b64, str): members['files/' + name] = base64.b64decode(b64)
modes = ('identity', 'values') if os.environ['MODE'] == 'both' else (os.environ['MODE'],)
for mode in modes:
    t0 = time.time()
    text, rep = R.render(members, tensor_mode=mode, tokenizer=tok)
    out = os.path.join(os.environ['ROOT'], 'tmp', f'reading-render-{mode}.md'); open(out, 'w', encoding='utf-8').write(text)
    d_tok = sum(m['delivered_tokens'] for m in rep.members.values()); r_tok = sum(m['rendered_tokens'] for m in rep.members.values())
    print(f'\n=== mode {mode}: delivered {rep.delivered_bytes} B / {d_tok} tok -> rendered {rep.rendered_bytes} B / {r_tok} tok ({r_tok / max(1, d_tok):.3f}x); '
          f'parts of ~87k tokens: {d_tok // 87000 + 1} -> {r_tok // 87000 + 1}; dictionary {rep.dictionary_entries} entries, {rep.refs} refs saving {rep.saved_bytes} B; '
          f'tensors {rep.tensors} ({rep.tensor_bytes} B raw); PROOF all_exact={rep.proof["all_exact"]}; {time.time() - t0:.0f}s; written {out}')
    print('%-30s %10s %9s -> %10s %9s' % ('member', 'B', 'tok', 'B', 'tok'))
    for n, m in rep.members.items():
        print('%-30s %10d %9d -> %10d %9d   exact=%s' % (n[:30], m['delivered_bytes'], m['delivered_tokens'], m.get('rendered_bytes', 0), m['rendered_tokens'], rep.proof[n]['exact']))
    print('   L7: derivable vectors', rep.derived_vectors, 'ranges', rep.ranges)
    if mode == 'identity':
        i = text.find('{"$tensors"'); print('--- tensor table head:', text[i:i + 900].replace('\n', ' ')[:900])
# the dense digest, from the derived layers on this box (read-only: written under tmp/, never under session/)
import frankie_box_digest_render as DG, math
work = os.path.join(os.environ['ROOT'], 'session', 'work')
receipt = json.load(open(os.path.join(work, 'derive.json')))
L = {n: json.load(open(os.path.join(work, 'derived', n + '.json'))) for n in ('legacy_price', 'legacy_native_signed_flow', 'legacy_per_second_roll20', 'legacy_book_imbalance', 'legacy_structure_observables')}
prices = L['legacy_price'].get('first', []) and None
old = open(os.path.join(work, 'derivation-digest-full.md'), 'rb').read()
ps = L['legacy_native_signed_flow']['per_second']; buys = [r['buy'] for r in ps]; sells = [r['sell'] for r in ps]; first = ps[0]['second'] if ps else L['legacy_per_second_roll20'].get('first_second', 0)
roll = [float('nan') if v is None else v for v in L['legacy_per_second_roll20']['series']]
# legacy_price rows are not kept whole in the layer file (first/last only): re-derive from the old digest's lines for the measurement
price_rows = []
for line in old.decode('utf-8', 'replace').split('\n'):
    mm = re.match(r'^(\d+) (\S+) x(\S+) bid (\S+) ask (\S+)$', line)
    if mm:
        price_rows.append(dict(ts_recv=int(mm.group(1)), price=float(mm.group(2)), size=int(mm.group(3)), bid_px_00=float(mm.group(4)), ask_px_00=float(mm.group(5))))
t0 = time.time()
dense = DG.digest_text(receipt, L, price_rows, L['legacy_book_imbalance']['frames'], L['legacy_structure_observables']['groups'], roll, first, buys, sells)
open(os.path.join(os.environ['ROOT'], 'tmp', 'derivation-digest-dense.md'), 'w', encoding='utf-8').write(dense)
print(f'\n=== digest: old {len(old)} B / {tok_n(old.decode("utf-8", "replace"))} tok -> dense (ALL fields, self-checked) {len(dense.encode())} B / {tok_n(dense)} tok; {time.time() - t0:.0f}s')
print(dense[:1200].replace('\n', ' | ')[:1200])
PY
