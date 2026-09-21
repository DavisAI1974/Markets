# Read-only: build the LOSSLESS reading render (deploy/aws/box/frankie_box_reading_render.py) of the real delivered
# members on this box, in both tensor modes, and print the report: bytes and exact Granite tokens per member before
# and after, dictionary references, tensors, and the byte-exact reconstruction proof per member. Writes the renders
# under /opt/frankie-box/tmp/ for inspection; touches nothing under session/. Inputs: MODE (identity | values | both).
set -u
ROOT=/opt/frankie-box; T="$ROOT/tmp"; MODE="${MODE:-both}"; mkdir -p "$T"
"$ROOT/venv/bin/python" -c "import tokenizers" 2>/dev/null || "$ROOT/venv/bin/pip" install -q tokenizers >/dev/null 2>&1
TOK="$T/granite_tokenizer.json"
[ -s "$TOK" ] || curl -fsS -m 120 -L -o "$TOK" "https://huggingface.co/ibm-granite/granite-4.2-8b/resolve/f8de16cdcdbc6c779ca517604e050d82cc119e44/tokenizer.json"
export ROOT TOK MODE
"$ROOT/venv/bin/python" - <<'PY'
import base64, json, os, sys, time
sys.path.insert(0, os.environ['ROOT'] + '/markets'); sys.path.insert(0, os.environ['ROOT'] + '/markets/deploy/aws/box')
import frankie_box_reading_render as R
from tokenizers import Tokenizer
tok = Tokenizer.from_file(os.environ['TOK'])
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
    if mode == 'identity':
        i = text.find('$tensors'); print('--- tensor table head:', text[i:i + 700].replace('\n', ' ')[:700])
PY
