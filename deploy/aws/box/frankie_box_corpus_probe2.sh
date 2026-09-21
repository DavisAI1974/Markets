# Read-only: what is left after the lossless render (run 35595034331), so the next layers can be designed.
# (1) the derivation digest: its sections and their sizes, the row shapes of its tables (repeated headers, timestamp
# columns, float formats); (2) whether the critic prompt embeds the snapshot codec JSON verbatim (containment did not
# fire on the whole snapshot_text); (3) the context_receipt's keys and the packet_hashes / context_cursors shapes;
# (4) the head of prompt.md: its ## sections and sizes (the 18 retained sections). Changes nothing.
set -u
ROOT=/opt/frankie-box; export ROOT
"$ROOT/venv/bin/python" - <<'PY'
import base64, collections, json, os, re, sys
sys.path.insert(0, os.environ['ROOT'] + '/markets')
from research.kalshi.frankie_boss.c15_journal import unpack
D = open(os.environ['ROOT'] + '/session/work/derivation-digest-full.md', 'rb').read().decode('utf-8', 'replace')
print('== derivation digest', len(D.encode()), 'bytes,', D.count('\n'), 'lines')
secs = [(m.start(), m.group(0).strip()) for m in re.finditer(r'^#{1,4} .*$', D, re.M)]
bounds = list(zip([s for s, _ in secs], [s for s, _ in secs[1:]] + [len(D)]))
for (s, e), (_, title) in zip(bounds, secs):
    body = D[s:e]
    if len(body) < 20000: continue
    lines = body.split('\n')
    tab = [l for l in lines if l.startswith('|')]
    print('  %8d B %6d lines %6d table rows  %s' % (len(body.encode()), len(lines), len(tab), title[:90]))
    for l in tab[:3]: print('      |', l[:220])
    nums = re.findall(r'-?\d+\.\d+', body); ints = re.findall(r'\b\d{15,20}\b', body)
    print('      floats', len(nums), 'avg len', round(sum(map(len, nums)) / max(1, len(nums)), 1), '; 15-20 digit ints', len(ints))
data = open(os.environ['ROOT'] + '/request/prompt.md', 'rb').read()
marker = data.find(b'## BOSS/Granite producer evidence'); head = data[:marker].decode('utf-8', 'replace'); block = data[marker:]; start = block.find(b'{')
print('\n== head', len(head.encode()), 'bytes; sections:')
hs = [(m.start(), m.group(0).strip()) for m in re.finditer(r'^#{1,3} .*$', head, re.M)]
for (s, e), (_, t) in zip(zip([s for s, _ in hs], [s for s, _ in hs[1:]] + [len(head)]), hs):
    print('  %8d B  %s' % (len(head[s:e].encode()), t[:100]))
payload = json.loads(block[start:].decode('utf-8'))
files = {n: base64.b64decode(b) for n, b in payload['files_base64'].items()}
prompt = files['critic-prompt.txt'].decode('utf-8'); snap = files['critic-snapshot.txt'].decode('utf-8')
print('\n== critic prompt', len(prompt), 'chars; snapshot', len(snap), 'chars; snapshot in prompt:', snap in prompt)
sj = json.loads(snap)
for key in sj:
    txt = json.dumps(sj[key], separators=(',', ':'), sort_keys=True)
    print('   snapshot[%s] %d chars; verbatim in prompt: %s' % (key, len(txt), txt in prompt), '; sort_keys=False:', json.dumps(sj[key], separators=(',', ':')) in prompt)
i = prompt.find('{"codec"'); j = prompt.find('"data"'); print('   prompt: first {"codec" at', i, '; "data" at', j, '; prompt head 300:', repr(prompt[:300]))
print('   prompt tail 400:', repr(prompt[-400:]))
fc = unpack(json.loads(files['forecast-000000.bin']))
cr = unpack(json.loads(fc['context_receipt']))
print('\n== context_receipt keys', list(cr), '; context keys', list(cr.get('context', {}))[:30])
ctx = cr.get('context', {})
for k, v in ctx.items():
    if isinstance(v, (list, tuple)): print('   ', k, 'len', len(v), 'first', str(v[:2])[:100], 'monotone-range' if all(isinstance(x, int) for x in v) and list(v) == list(range(v[0], v[0] + len(v))) else '')
    elif isinstance(v, str) and len(v) > 80: print('   ', k, 'str', len(v))
sc = json.loads(snap); print('   snapshot codec top:', str(sc['codec'])[:400])
PY
