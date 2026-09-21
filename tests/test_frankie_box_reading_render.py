"""The lossless reading render (deploy/aws/box/frankie_box_reading_render.py) layers L8 (known files), L9 (the stacked
envelope as a STACKED_TEXT_V1 block) and L10 (same-keyed dict lists as DIGEST_V4 table blocks), on hand-built members
shaped like the delivered ones (c15-packed documents with bytes values that decode to text and JSON). Every layer is a
reference to a value the reader can check by digest or a block parsed back to the same value; the member itself must
still rebuild byte-exact (`reconstruct_proof`). The package's __init__ imports torch, so the codec modules are loaded
as a namespace package here, as the box does through the checkout."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
for name, rel in (('research', 'research'), ('research.kalshi', 'research/kalshi'), ('research.kalshi.frankie_boss', 'research/kalshi/frankie_boss')):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(ROOT / rel)]
        sys.modules[name] = module
sys.path.insert(0, str(ROOT / 'deploy/aws/box'))
import frankie_box_reading_render as R          # noqa: E402
import frankie_box_stacked_text as ST           # noqa: E402
from research.kalshi.frankie_boss import granite_context_stacked as stacked   # noqa: E402
from research.kalshi.frankie_boss.c15_journal import pack                     # noqa: E402
from research.kalshi.frankie_boss.causal_packet import canonical_bytes        # noqa: E402


def _envelope():
    records = [dict(record=dict(publisher_id=1, instrument_id=111313, ts_event=1633298400329344207 + i * 1000, order_id=7000000000000 + i * 3,
                                price=5412000000000 + (i % 3) * 1000000, size=1 + i % 4, action='A' if i % 2 else 'C', side='B',
                                ts_recv=1633298400329344307 + i * 1000, flags=128 if i % 5 == 0 else 0, channel_id=0, ts_in_delta=17000 + i, sequence=1000 + i),
                    metadata=dict(source='x/y.dbn', note='has space "quoted" \t tab', f=1.5, n=None, t=True, key123='123', kw='null',
                                  g='d17184c95a2d55198053299d3cbcea8a9d19a832df0c492ee3bf361e88e0441a', arr=(1, 2, 3)))
               for i in range(40)]
    root = dict(records=records, receipt=dict(as_of=5, packet_hashes=['ab' * 32] * 40, layout=['x']), graph=dict(parent=[None] + list(range(39))))
    return stacked.encode(root), root


def _members(tmp_path):
    checkout = tmp_path / 'markets'
    (checkout / '.git').mkdir(parents=True)
    (checkout / '.git' / 'HEAD').write_text('ref: refs/heads/main\n')
    (checkout / '.git' / 'refs' / 'heads').mkdir(parents=True)
    (checkout / '.git' / 'refs' / 'heads' / 'main').write_text('0123456789abcdef0123456789abcdef01234567\n')
    (checkout / 'research').mkdir()
    source = ('"""A delivered configuration file."""\n' + ''.join(f'def f{i}(x):\n    return x + {i}\n\n' for i in range(60))).encode()
    (checkout / 'research' / 'controller.py').write_bytes(source)
    env, root = _envelope()
    snapshot = json.dumps(dict(schema='S', native_hash='ab' * 32, codec=env), separators=(',', ':')).encode()
    prompt = ('GRAMMAR ' * 40 + '\nsnapshot_hash: ' + 'ab' * 32 + '\nstacked_native_context:\n').encode() + snapshot
    points = [dict(t=1633298400 + i, p50=5.41 + i * 0.001, quantiles=[5.4, 5.41, 5.42], side='B' if i % 2 else 'A') for i in range(20)]
    state = dict(request_hash='cd' * 32, intent=dict(configuration=dict(code={'controller.py': source})),
                 critic_intent=dict(snapshot_text=snapshot, prompt_text=prompt), points=points, small=b'tiny')
    controller = dict(schema='C15_FULL_EVIDENCE_V1', ordinal=0, payload=dict(configuration=dict(code={'controller.py': source})))
    members = {'files/state.c15.json': canonical_bytes(pack(state)),
               'files/controller.c15.jsonl': canonical_bytes(pack(controller)) + b'\n'}
    return members, checkout, env, source, points, snapshot


def test_known_files_stacked_text_and_table_blocks_render_and_rebuild(tmp_path):
    members, checkout, env, source, points, snapshot = _members(tmp_path)
    index = R.known_files_index({'markets': str(checkout)})
    assert index[hashlib.sha256(source).hexdigest()] == dict(path='research/controller.py', checkout='markets', commit='0123456789abcdef0123456789abcdef01234567')
    text, report = R.render(members, tensor_mode='identity', known_files=index)
    assert report.proof['all_exact'] is True
    assert report.file_refs == 2 and report.file_saved_bytes == 2 * len(source)          # the same file in both members: a $file both times
    assert report.stacked_blocks == 1 and report.table_blocks == 1 and report.table_rows == 20
    assert '"$file":"research/controller.py"' in text and '"commit":"0123456789abcdef0123456789abcdef01234567"' in text
    assert source.decode() not in text                                                     # the file's text is not spelled out
    # the stacked block parses back to the envelope's data, the table block to the points
    block = text.split('#### block stacked-', 1)[1].split('```\n', 1)[1].split('```', 1)[0]
    assert ST.canonical(ST.parse(block)) == ST.canonical(env['data'])
    assert '"$stacked_text":"STACKED_TEXT_V1"' in text and '"schema":"BOSS_GRANITE_NATIVE_STACKED_CONTEXT_V1"' in text and '"native_hash":"' in text
    import frankie_box_digest_render as DG
    table = text.split('#### block table-', 1)[1].split('```\n', 1)[1].split('```', 1)[0]
    assert DG._same(DG.parse_table(table)[1], points)
    assert '"$table":"DIGEST_V4"' in text and '"columns":["t","p50","quantiles","side"]' in text
    # the snapshot text is rendered once (in the $decoded node) and the prompt contains it (L5 marker)
    assert text.count('"$stacked_text":"STACKED_TEXT_V1"') == 1 and '<<contains sha256:' in text   # once in a node (the legend names the key without its value)
    # the node carries the snapshot text's own digest (the proof that the block puts the text back ran before the
    # node was written; the render then sorts JSON keys for reading, so the wrapper is checked by digest here)
    node = json.loads(text.split('#### document 0\n```json\n', 1)[1].split('\n```', 1)[0])['critic_intent']['snapshot_text']
    assert node['$decoded'] == 'utf8' and node['value']['bytes'] == len(snapshot)
    assert node['value']['sha256'] == node['sha256'] == hashlib.sha256(snapshot).hexdigest()
    assert node['value']['json']['codec']['data'] == {'$stacked': 'STACKED_TEXT_V1', 'block': node['value']['block']}


def test_a_stacked_text_block_that_cannot_put_the_text_back_refuses(monkeypatch):
    env, root = _envelope()
    text = json.dumps(dict(schema='S', codec=env), separators=(',', ':'))
    monkeypatch.setattr(ST, 'parse', lambda spelled: ['M', [], []])          # a broken parser: the text would not come back
    try:
        R._stacked_text_block(text, 'x')
    except ValueError as err:
        assert 'does not' in str(err)                                   # prove() refuses first (its own parse-back), else the text check
    else:
        raise AssertionError('a block that does not reproduce the text must refuse')
    assert R._stacked_text_block(text[:-1] + ' }', 'x') is None               # not the exact spelling of what it parses to: left alone


def test_without_known_files_the_source_is_spelled_and_a_short_list_stays_json(tmp_path):
    members, checkout, env, source, points, snapshot = _members(tmp_path)
    text, report = R.render(members, tensor_mode='identity')
    assert report.file_refs == 0 and 'def f59(x):' in text and report.proof['all_exact'] is True
    short = dict(points=[dict(a=i) for i in range(R.TABLE_MIN - 1)])
    text, report = R.render({'files/x.json': canonical_bytes(pack(short))}, tensor_mode='identity')
    assert report.table_blocks == 0 and '"$table":"DIGEST_V4","block":"table-' not in text and report.proof['all_exact'] is True


def test_a_tuple_of_dicts_becomes_a_table_block_and_says_so():
    rows = tuple(dict(time_ns=1633298400000000000 + i * 1000, observed=i % 2 == 0, quantiles=[5.4, 5.41, 5.42]) for i in range(20))
    blocks = []
    out = R._blocks_pass(dict(points=rows), blocks)
    assert len(blocks) == 1 and blocks[0]['rows'] == 20 and out['points']['container'] == 'tuple' and out['points']['$table'] == 'DIGEST_V4'
    import frankie_box_digest_render as DG
    assert DG._same(DG.parse_table(blocks[0]['text'])[1], [dict(r) for r in rows])


def test_a_table_that_does_not_round_trip_stays_json(monkeypatch):
    import frankie_box_digest_render as DG
    rows = [dict(a=i, b=(i, i)) for i in range(20)]        # tuples parse back as lists: not the same rows
    doc = dict(rows=rows)
    blocks = []
    out = R._blocks_pass(doc, blocks)
    assert blocks == [] and out == doc
