# Read-only measurement (Greg, 2026-09-21: shrink the 22.6 MB read with every LOSSLESS layer we have; drop nothing).
# For every delivered member of the request (the receiver's producer-evidence payload in request/prompt.md) it measures
# bytes and exact Granite tokens (the pinned tokenizer, sha-verified) in three forms:
#   L0  as delivered: c15-packed canonical JSON (every value type-tagged, floats as IEEE hex);
#   L1  unpacked: the same document as plain canonical JSON (c15_journal.unpack; round trip pack->bytes == original);
#   L2  stacked: granite_context_stacked.encode of the unpacked document (the repo's reversible named-column codec;
#       encode verifies decode(encode(x)) == x itself).
# Every layer is proven reversible on the real bytes before its size is reported. Also prints the structure of the
# biggest journal entries (kind, payload keys, largest lists) so the render can be designed. Installs `tokenizers`
# into the box venv if absent; writes nothing under session/. Changes nothing else.
set -u
ROOT=/opt/frankie-box; T="$ROOT/tmp"; mkdir -p "$T"
"$ROOT/venv/bin/python" -c "import tokenizers" 2>/dev/null || "$ROOT/venv/bin/pip" install -q tokenizers >/dev/null 2>&1 || echo "tokenizers install failed (tokens will be estimated)"
TOK="$T/granite_tokenizer.json"
[ -s "$TOK" ] || curl -fsS -m 120 -L -o "$TOK" "https://huggingface.co/ibm-granite/granite-4.2-8b/resolve/f8de16cdcdbc6c779ca517604e050d82cc119e44/tokenizer.json" || echo "tokenizer download failed"
echo "tokenizer sha256 $(sha256sum "$TOK" 2>/dev/null | cut -c1-16) (pinned 883975314d587437)"
export ROOT TOK
"$ROOT/venv/bin/python" - <<'PY'
import base64, collections, json, os, re, sys, time
sys.path.insert(0, os.environ['ROOT'] + '/markets')
from research.kalshi.frankie_boss.c15_journal import pack, unpack
from research.kalshi.frankie_boss.causal_packet import canonical_bytes
from research.kalshi.frankie_boss import granite_context_stacked as stacked
try:
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(os.environ['TOK'])
    def ntok(b):
        n = 0
        for i in range(0, len(b), 1 << 20):
            n += len(tok.encode(b[i:i + (1 << 20)].decode('utf-8', 'replace'), add_special_tokens=False).ids)
        return n
except Exception as err:
    print('token counts ESTIMATED (bytes/1.6):', type(err).__name__)
    def ntok(b): return int(len(b) / 1.6)
data = open(os.environ['ROOT'] + '/request/prompt.md', 'rb').read()
marker = data.find(b'## BOSS/Granite producer evidence'); block = data[marker:]; start = block.find(b'{')
payload = json.loads(block[start:].decode('utf-8'))
members = {}
for key in ('manifest_base64', 'source_binding_base64', 'mapping_evidence_base64'):
    if isinstance(payload.get(key), str): members[key.replace('_base64', '')] = base64.b64decode(payload[key])
for name, b64 in (payload.get('files_base64') or {}).items():
    if isinstance(b64, str): members['files/' + name] = base64.b64decode(b64)
def plain(doc): return json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
def biggest(doc, path='', acc=None, depth=0):
    acc = acc if acc is not None else []
    if isinstance(doc, dict):
        for k, v in doc.items(): biggest(v, f'{path}.{k}', acc, depth + 1)
    elif isinstance(doc, (list, tuple)):
        acc.append((len(plain(doc)), len(doc), path))
        for i, v in enumerate(doc[:3]): biggest(v, f'{path}[{i}]', acc, depth + 1)
    return acc
tot = collections.Counter()
print('%-32s %10s %8s | %10s %8s | %10s %8s' % ('member', 'L0 bytes', 'L0 tok', 'L1 bytes', 'L1 tok', 'L2 bytes', 'L2 tok'))
for name, raw in members.items():
    t0 = time.time()
    lines = raw.split(b'\n') if name.endswith('.jsonl') else [raw]
    lines = [l for l in lines if l.strip()]
    l1, l2, docs, ok1, ok2 = [], [], [], 0, 0
    for line in lines:
        try:
            packed = json.loads(line)
            doc = unpack(packed) if isinstance(packed, list) and packed and isinstance(packed[0], str) else packed
        except Exception as err:
            doc = None
        if doc is None:
            l1.append(line); l2.append(line); continue
        docs.append(doc)
        if isinstance(packed, list) and canonical_bytes(pack(doc)) == line.strip(): ok1 += 1
        elif not isinstance(packed, list) and plain(doc) == plain(json.loads(line)): ok1 += 1
        l1.append(plain(doc))
        try:
            env = stacked.encode(doc)          # verifies decode(encode(doc)) == doc itself
            l2.append(stacked._text(env).encode()); ok2 += 1
        except Exception as err:
            l2.append(plain(doc)); print('   stacked refused for', name, type(err).__name__, str(err)[:120])
    b0, b1, b2 = raw, b'\n'.join(l1), b'\n'.join(l2)
    n0, n1, n2 = ntok(b0), ntok(b1), ntok(b2)
    tot.update(dict(b0=len(b0), b1=len(b1), b2=len(b2), n0=n0, n1=n1, n2=n2))
    print('%-32s %10d %8d | %10d %8d | %10d %8d   round-trip L1 %d/%d L2 %d/%d  %.0fs' % (name[:32], len(b0), n0, len(b1), n1, len(b2), n2, ok1, len(lines), ok2, len(lines), time.time() - t0), flush=True)
    if name.endswith('.jsonl') and docs:
        kinds = collections.Counter(d.get('kind') for d in docs if isinstance(d, dict))
        print('     entries', len(docs), 'kinds', dict(kinds))
        for d in sorted(docs, key=lambda d: -len(plain(d)))[:2]:
            pk = list(d.get('payload', {})) if isinstance(d.get('payload'), dict) else type(d.get('payload')).__name__
            big = sorted(biggest(d), reverse=True)[:4]
            print('     entry kind', d.get('kind'), 'ordinal', d.get('ordinal'), 'bytes', len(plain(d)), 'payload keys', pk[:12])
            for sz, ln, path in big: print('        list', path[:90], 'len', ln, 'bytes', sz)
    elif docs and isinstance(docs[0], dict) and len(plain(docs[0])) > 200000:
        big = sorted(biggest(docs[0]), reverse=True)[:6]
        print('     top keys', list(docs[0])[:15])
        for sz, ln, path in big: print('        list', path[:90], 'len', ln, 'bytes', sz)
print('%-32s %10d %8d | %10d %8d | %10d %8d' % ('TOTAL', tot['b0'], tot['n0'], tot['b1'], tot['n1'], tot['b2'], tot['n2']))
if tot['n0']:
    print('tokens: L1/L0 = %.2f, L2/L0 = %.2f; parts of ~87k input tokens: L0 %d, L1 %d, L2 %d' % (tot['n1'] / tot['n0'], tot['n2'] / tot['n0'], tot['n0'] // 87000 + 1, tot['n1'] // 87000 + 1, tot['n2'] // 87000 + 1))
PY
