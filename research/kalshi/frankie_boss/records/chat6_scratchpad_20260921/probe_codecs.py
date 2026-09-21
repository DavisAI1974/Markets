import sys, types, pathlib, json, hashlib, math, importlib.util
ROOT = pathlib.Path('/home/user/Markets')
for name, rel in (('research','research'),('research.kalshi','research/kalshi'),('research.kalshi.frankie_boss','research/kalshi/frankie_boss')):
    m = types.ModuleType(name); m.__path__ = [str(ROOT/rel)]; sys.modules[name] = m
sys.path.insert(0, str(ROOT/'deploy/aws/box'))
import frankie_box_digest_render as DG, frankie_box_stacked_text as ST, frankie_box_reading_render as R, frankie_box_head_render as HR
from research.kalshi.frankie_boss import granite_context_stacked as stacked
from research.kalshi.frankie_boss.c15_journal import pack
from research.kalshi.frankie_boss.causal_packet import canonical_bytes

def probe(label, fn):
    try:
        print(f'[{label}] ->', fn())
    except Exception as e:
        print(f'[{label}] RAISES {type(e).__name__}: {str(e)[:160]}')

# 1 empty inputs
probe('parse_digest("")', lambda: DG.parse_digest(''))
probe('render_layers({})', lambda: repr(DG.render_layers({})))
probe('render_layers empty table', lambda: repr(DG.render_layers({'t': []})))
probe('parse_table(render_table("t", []))', lambda: DG.parse_table(DG.render_table('t', [])))
# 2 non-ASCII digits accepted by the DIGEST parser? (tamper case; ST refuses them)
blk = DG.render_table('t', [dict(a=12, b=1), dict(a=13, b=2)])
print('block:', repr(blk))
probe('digest parse Arabic-Indic digit cell', lambda: DG.parse_table(blk.replace('12 1', '١٢ 1'))[1])
probe('digest _expand ^ with Arabic digit', lambda: DG._expand(['^٢']))
probe('digest fraction cell with Arabic digits', lambda: DG.parse_table(blk.replace('12 1', '١/٢ 1'))[1])
# 3 empty containers as values
probe('render_layers empty dict value', lambda: repr(DG.render_layers({'t': [dict(a={}, b=1)]}))[:120])
probe('render_table empty dict value (no proof)', lambda: (DG.render_table('t', [dict(a={}, b=1)]), DG.parse_table(DG.render_table('t', [dict(a={}, b=1)]))[1]))
probe('render_layers empty list value', lambda: DG._same(DG.parse_table(DG.render_table('t', [dict(a=[], b=1), dict(a=[], b=2)]))[1], [dict(a=[], b=1), dict(a=[], b=2)]))
probe('render_layers empty tuple value', lambda: DG._same(DG.parse_table(DG.render_table('t', [dict(a=(), b=1), dict(a=(), b=2)]))[1], [dict(a=(), b=1), dict(a=(), b=2)]))
probe('render_layers empty string key', lambda: DG.render_layers({'t': [{'': 1}]}))
probe('nested dict key with dot via reading _blocks_pass', lambda: (lambda blocks, notes: (R._blocks_pass(dict(rows=[dict(a=i, n={'b.c': i}) for i in range(20)]), blocks, 'doc', notes), len(blocks), notes))([], []))
# 4 row count / header mismatches
probe('parse_table rows declared 2 present 3 (extra row)', lambda: DG.parse_table(blk + '99 9\n'))
probe('parse_table header says 5 rows', lambda: DG.parse_table(blk.replace('2 rows', '5 rows')))
probe('parse_table garbage', lambda: DG.parse_table('hello\n'))
probe('parse_digest text with no tables', lambda: DG.parse_digest('# nothing here\n'))
# 5 very long row / very wide
import random
rows = [dict(**{f'c{j}': (i*j) % 7 for j in range(3000)}) for i in range(5)]
probe('3000 columns x 5 rows round trip', lambda: DG._same(DG.parse_table(DG.render_table('t', rows))[1], rows))
big = [dict(ids=list(range(0, 200000, 3)), k=1)]
probe('one int list of 66k entries round trip', lambda: DG._same(DG.parse_table(DG.render_table('t', big))[1], big))
# 6 sign-of-zero in constants line and dictionary
probe('constant -0.0 column', lambda: [math.copysign(1, r['x']) for r in DG.parse_table(DG.render_table('t', [dict(x=-0.0, y=1), dict(x=-0.0, y=2)]))[1]])
probe('render_layers constant -0.0 column', lambda: 'ok' if DG.render_layers({'t': [dict(x=-0.0, y=1), dict(x=-0.0, y=2)]}) else 'no')
probe('tuple constant with -0.0', lambda: 'ok' if DG.render_layers({'t': [dict(x=(-0.0, 1), y=1), dict(x=(-0.0, 1), y=2)]}) else 'no')
probe('JSON list cell with -0.0', lambda: 'ok' if DG.render_layers({'t': [dict(x=[-0.0, 1.5], y=1), dict(x=[0.0, 1.5], y=2)]}) else 'no')
probe('JSON dict-in-list cell with nan', lambda: 'ok' if DG.render_layers({'t': [dict(x=[{'a': float('nan')}], y=1)]}) else 'no')
# 7 mixed int/float in the same column, big ints beyond float precision
probe('mixed int/float column', lambda: DG._same(DG.parse_table(DG.render_table('t', [dict(x=1), dict(x=1.0), dict(x=2**63), dict(x=True)]))[1], [dict(x=1), dict(x=1.0), dict(x=2**63), dict(x=True)]))
probe('float column of 1e16 and 10000000000000000 (int)', lambda: [type(r['x']).__name__ for r in DG.parse_table(DG.render_table('t', [dict(x=1e16), dict(x=10**16)]))[1]])
# 8 L5 containment: is the test's assertion satisfied by the legend alone?
records = [dict(record=dict(publisher_id=1, instrument_id=111313, ts_event=1633298400329344207 + i * 1000, order_id=7000000000000 + i * 3,
                            price=5412000000000 + (i % 3) * 1000000, size=1 + i % 4, action='A' if i % 2 else 'C', side='B',
                            ts_recv=1633298400329344307 + i * 1000, flags=128 if i % 5 == 0 else 0, channel_id=0, ts_in_delta=17000 + i, sequence=1000 + i),
                metadata=dict(source='x/y.dbn', note='has space "quoted" \t tab', f=1.5, n=None, t=True, key123='123', kw='null',
                              g='d17184c95a2d55198053299d3cbcea8a9d19a832df0c492ee3bf361e88e0441a', arr=(1, 2, 3))) for i in range(40)]
root = dict(records=records, receipt=dict(as_of=5, packet_hashes=['ab' * 32] * 40, layout=['x']), graph=dict(parent=[None] + list(range(39))))
env = stacked.encode(root)
snapshot = json.dumps(dict(schema='S', native_hash='ab' * 32, codec=env), separators=(',', ':')).encode()
prompt = ('GRAMMAR ' * 40 + '\nsnapshot_hash: ' + 'ab' * 32 + '\nstacked_native_context:\n').encode() + snapshot
print('fixture snapshot bytes', len(snapshot), 'prompt bytes', len(prompt), 'DEDUP_BYTES', R.DEDUP_BYTES)
state = dict(request_hash='cd' * 32, critic_intent=dict(snapshot_text=snapshot, prompt_text=prompt), small=b'tiny')
text, report = R.render({'files/state.c15.json': canonical_bytes(pack(state))}, tensor_mode='identity')
legend_hits = text.count('<<contains sha256:')
print('occurrences of "<<contains sha256:" in the render:', legend_hits, '(1 = the legend only, L5 did not fire)')
print('L5 marker with a real digest present:', bool(__import__('re').search(r'<<contains sha256:[0-9a-f]{64} ', text)))
# 9 a c15-canonical member carrying the envelope as a DICT (the untested _blocks_pass dict-envelope success path, lines 507-514)
doc = dict(schema='S', codec=env)
text2, report2 = R.render({'files/x.c15.json': canonical_bytes(pack(doc))}, tensor_mode='identity')
print('dict-envelope path: stacked_blocks', report2.stacked_blocks, 'notes', report2.block_notes, 'all_exact', report2.proof['all_exact'])
# 10 known file whose sha256 index entry points to a file that is missing / a size below FILE_MIN
idx = {hashlib.sha256(b'x' * 2000).hexdigest(): dict(path='gone/missing.py', checkout='markets', commit=None)}
t3, r3 = R.render({'files/y.c15.json': canonical_bytes(pack(dict(code={'a.py': b'x' * 2000})))}, tensor_mode='identity', known_files=idx)
print('known-file ref to a path that no longer exists on disk: file_refs', r3.file_refs, 'proof', r3.proof['all_exact'], '($file is by digest; the render cannot know the path is gone)')
# 11 HEAD render: empty text, CRLF, a table at EOF with no trailing newline
probe('HR.render("")', lambda: HR.render(''))
probe('HR.parse("")', lambda: repr(HR.parse('')))
crlf = '## T\r\n\r\n| a | b |\r\n|---|---|\r\n' + ''.join(f'| keepprefix_{i} | v |\r\n' for i in range(10))
probe('HR crlf round trip', lambda: (HR.parse(HR.render(crlf)[0]) == crlf, HR.render(crlf)[1]['transformed']))
noeol = '## T\n\n| a | b |\n|---|---|\n' + '\n'.join(f'| keepprefix_{i} | v |' for i in range(10))
probe('HR table at EOF without newline', lambda: (HR.parse(HR.render(noeol)[0]) == noeol, HR.render(noeol)[1]['transformed']))
uni = '## T\n\n| a | b |\n|---|---|\n' + ''.join(f'| café_prefix_{i} | ١ |\n' for i in range(10))
probe('HR unicode table', lambda: (HR.parse(HR.render(uni)[0]) == uni, HR.render(uni)[1]['transformed']))
# 12 ST: empty text, only whitespace, trailing garbage, unicode digit inside a quoted string is fine
probe('ST.parse("")', lambda: ST.parse(''))
probe('ST.parse("   ")', lambda: ST.parse('   '))
probe('ST.parse("V 1 extra")', lambda: ST.parse('V 1 extra'))
probe('ST quoted unicode digits', lambda: ST.parse(ST.spell(['V', '١٢'])))
probe('ST float atom in V refuses', lambda: ST.spell(['V', 1.5]))
probe('ST bool/int atom int subclass', lambda: ST.spell(['V', True]))
# 13 botocore: is an EMPTY AWS_SESSION_TOKEN treated as absent?
try:
    import os, botocore.session
    os.environ.update(AWS_ACCESS_KEY_ID='AKIAEXAMPLEEXAMPLE00', AWS_SECRET_ACCESS_KEY='x' * 40, AWS_SESSION_TOKEN='')
    c = botocore.session.get_session().get_credentials()
    print('botocore empty AWS_SESSION_TOKEN -> token =', repr(c.token), 'method', c.method)
except Exception as e:
    print('botocore probe skipped:', type(e).__name__, e)
