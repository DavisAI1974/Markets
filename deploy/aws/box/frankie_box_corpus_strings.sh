# Read-only: the largest STRING (and bytes) values inside the delivered members, because the lossless structural
# layers measured 1% (run 35593909809): the bulk must be a few giant scalar values. For each member: the ten largest
# string/bytes leaves with their path, length, character class (hex / base64 / json / text), a 100-character head,
# and whether the string itself parses as JSON or c15 (double encoding). Changes nothing.
set -u
ROOT=/opt/frankie-box; export ROOT
"$ROOT/venv/bin/python" - <<'PY'
import base64, collections, json, os, re, sys
sys.path.insert(0, os.environ['ROOT'] + '/markets')
from research.kalshi.frankie_boss.c15_journal import unpack
data = open(os.environ['ROOT'] + '/request/prompt.md', 'rb').read()
marker = data.find(b'## BOSS/Granite producer evidence'); block = data[marker:]; start = block.find(b'{')
payload = json.loads(block[start:].decode('utf-8'))
members = {}
for name, b64 in (payload.get('files_base64') or {}).items():
    if isinstance(b64, str): members['files/' + name] = base64.b64decode(b64)
def leaves(doc, path='', acc=None):
    acc = acc if acc is not None else []
    if isinstance(doc, dict):
        for k, v in doc.items(): leaves(v, f'{path}.{k}', acc)
    elif isinstance(doc, (list, tuple)):
        for i, v in enumerate(doc): leaves(v, f'{path}[{i}]', acc)
    elif isinstance(doc, (str, bytes)):
        acc.append((len(doc), path, doc))
    return acc
def cls(s):
    if isinstance(s, bytes): return 'bytes'
    if re.fullmatch(r'[0-9a-f]+', s): return 'hex'
    if re.fullmatch(r'[A-Za-z0-9+/=\n]+', s): return 'base64?'
    if s[:1] in '{[': return 'json-like'
    return 'text'
for name, raw in members.items():
    if len(raw) < 100000: continue
    lines = [l for l in (raw.split(b'\n') if name.endswith('.jsonl') else [raw]) if l.strip()]
    print('\n==', name, len(raw), 'bytes')
    for li, line in enumerate(lines):
        try:
            packed = json.loads(line)
            doc = unpack(packed) if isinstance(packed, list) and isinstance(packed[0], str) else packed
        except Exception as err:
            print('   line', li, 'not parseable:', type(err).__name__); continue
        big = sorted(leaves(doc), reverse=True)[:10]
        total = sum(n for n, _, _ in leaves(doc))
        print('   line', li, 'string+bytes leaves total', total, 'bytes')
        for n, path, s in big:
            if n < 2000: break
            head = (s[:100] if isinstance(s, str) else s[:50].hex())
            inner = ''
            if isinstance(s, str) and s[:1] in '{[':
                try:
                    j = json.loads(s); inner = ' -> JSON ' + (type(j).__name__) + (' c15-tagged' if isinstance(j, list) and j and isinstance(j[0], str) else '') + ' keys ' + str(list(j)[:8] if isinstance(j, dict) else '')
                except Exception: inner = ' -> not JSON'
            print('     %10d %-8s %s' % (n, cls(s), path[:110]))
            print('                 head: %r%s' % (head, inner))
PY
