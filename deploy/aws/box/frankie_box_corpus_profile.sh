# Read-only: profile the reading corpus (session/work/reading-corpus-full.md) member by member so a LOSSLESS reading
# render can be designed (Greg, 2026-09-21: reduce the 22.6 MB read without dropping any data). For every "### member"
# section: bytes, lines, the first two lines (cut), the distinct JSON key sets and their counts when the lines are JSON,
# the count and share of 64-hex strings and of repeated string values (dictionary candidates), and whitespace share.
# Prints nothing but statistics and short samples; changes nothing.
set -u
ROOT=/opt/frankie-box; F="$ROOT/session/work/reading-corpus-full.md"
[ -s "$F" ] || { echo "no corpus at $F"; exit 2; }
"$ROOT/venv/bin/python" - "$F" <<'PY'
import collections, json, re, sys
data = open(sys.argv[1], 'rb').read()
print('corpus bytes', len(data))
heads = [m.start() for m in re.finditer(rb'\n### member ', data)]
bounds = list(zip(heads, heads[1:] + [len(data)]))
print('head (before the first member) bytes', heads[0] if heads else len(data))
hexre = re.compile(r'\b[0-9a-f]{64}\b')
for s, e in bounds:
    sect = data[s:e]
    title = sect.split(b'\n', 2)[1].decode('utf-8', 'replace')[:120]
    body = sect.split(b'\n', 3)[3] if sect.count(b'\n') >= 3 else b''
    text = body.decode('utf-8', 'replace')
    lines = text.split('\n')
    print('\n==', title)
    print('   bytes', len(body), 'lines', len(lines), 'avg line', round(len(body) / max(1, len(lines))), 'whitespace share %.1f%%' % (100 * sum(text.count(c) for c in ' \n\t') / max(1, len(text))))
    for l in lines[:2]:
        print('   |', l[:300])
    keysets, jsonlines, values = collections.Counter(), 0, collections.Counter()
    for l in lines[:200000]:
        l = l.strip()
        if not l.startswith('{'):
            continue
        try:
            obj = json.loads(l)
        except Exception:
            continue
        jsonlines += 1
        keysets[tuple(sorted(obj))] += 1
        for v in obj.values():
            if isinstance(v, str) and len(v) >= 16:
                values[v] += 1
    if jsonlines:
        print('   json lines', jsonlines, 'distinct key sets', len(keysets))
        for ks, n in keysets.most_common(4):
            print('     x%d keys=%s' % (n, ','.join(ks)[:200]))
        rep = [(v, n) for v, n in values.items() if n >= 2]
        saved = sum((n - 1) * (len(v) - 4) for v, n in rep)
        print('   repeated long string values: %d distinct, %d occurrences, dictionary would save ~%d bytes' % (len(rep), sum(n for _, n in rep), saved))
    hx = hexre.findall(text)
    print('   64-hex strings', len(hx), 'distinct', len(set(hx)), 'bytes %.1f%%' % (100 * 64 * len(hx) / max(1, len(text))))
    if title.startswith('member files/forecast') or title.startswith('member files/state'):
        try:
            obj = json.loads(text)
            def walk(o, d=0, acc=None):
                acc = acc if acc is not None else collections.Counter()
                if isinstance(o, dict):
                    for k, v in o.items(): acc[('key', k)] += 1; walk(v, d + 1, acc)
                elif isinstance(o, list):
                    acc[('list_len', min(len(o), 1000) // 100 * 100)] += 1
                    for v in o[:50]: walk(v, d + 1, acc)
                else:
                    acc[('leaf', type(o).__name__)] += 1
                return acc
            acc = walk(obj)
            print('   JSON document: top keys', list(obj)[:20] if isinstance(obj, dict) else type(obj).__name__)
            print('   leaves by type', {k[1]: n for k, n in acc.items() if k[0] == 'leaf'}, 'list-length buckets', {k[1]: n for k, n in acc.items() if k[0] == 'list_len'})
            print('   most frequent keys', [(k[1], n) for k, n in acc.most_common(12) if k[0] == 'key'])
        except Exception as err:
            print('   not one JSON document:', type(err).__name__)
PY
