"""STACKED_TEXT_V1 (deploy/aws/box/frankie_box_stacked_text.py): the stacked envelope's tagged tree in prefix notation,
parsed back to the identical tree; the codec's own encode builds the fixture from a hand-built root (no market data)."""
from __future__ import annotations

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
import frankie_box_stacked_text as ST                                          # noqa: E402
from research.kalshi.frankie_boss import granite_context_stacked as stacked   # noqa: E402


def _root():
    records = [dict(record=dict(publisher_id=1, instrument_id=111313, ts_event=1633298400329344207 + i * 1000, order_id=7000000000000 + i * 3,
                                price=5412000000000 + (i % 3) * 1000000, size=1 + i % 4, action='A' if i % 2 else 'C', side='B',
                                ts_recv=1633298400329344307 + i * 1000, flags=128 if i % 5 == 0 else 0, channel_id=0, ts_in_delta=17000 + i, sequence=1000 + i),
                    metadata=dict(source='x/y.dbn', note='has space "quoted" \t tab', f=1.5, h=-0.0, b=b'\x00\x01', n=None, t=True, empty=b'',
                                  g='d17184c95a2d55198053299d3cbcea8a9d19a832df0c492ee3bf361e88e0441a', arr=(1, 2, 3), key123='123', kw='null', neg=-7))
               for i in range(40)]
    return dict(records=records, receipt=dict(as_of=5, packet_hashes=['ab' * 32] * 40, layout=['x']), graph=dict(parent=[None] + list(range(39))),
                strings=['s' + str(i % 2) for i in range(20)], zeros=[0] * 70, scaled=[3000, 6000, 9000, 12000] * 5)


def test_round_trip_through_the_codec_and_every_atom_kind():
    root = _root()
    env = stacked.encode(root)
    text = ST.prove(env['data'])
    tree = ST.parse(text)
    assert ST.canonical(tree) == ST.canonical(env['data'])
    assert stacked._exact(stacked.decode(dict(env, data=tree))) == stacked._exact(root)
    assert 'V "has space \\"quoted\\" \\t tab"' in text and 'V "123"' in text and 'V "null"' in text and 'V null' in text and 'V true' in text and 'V -7' in text
    assert ST.spell(['X', '']) == 'X .\n' and ST.parse('X .') == ['X', ''] and ST.parse('X 00ff') == ['X', '00ff']   # the codec spells uniform empty bytes as B


def test_integer_recipes_carry_a_scale_only_when_every_value_is_a_multiple():
    assert ST.spell(['N', 'L', ['D', 5412000000000, [0, 1000000, -2000000]]]).strip() == 'N L D*6 5412000 3 0 1 -2'
    assert ST.spell(['N', 'L', ['I', [3000, 6000, 9000]]]).strip() == 'N L I*3 3 3 6 9'
    assert ST.spell(['N', 'L', ['I', [3000, 6001, 9000]]]).strip() == 'N L I 3 3000 6001 9000'
    assert ST.spell(['N', 'L', ['R', [[1000000, 5], [0, 7]]]]).strip() == 'N L R*6 2 1 5 0 7'          # counts are never scaled
    assert ST.spell(['N', 'L', ['E', 2000, [[1000, 3]]]]).strip() == 'N L E*3 2 1 1 3'
    assert ST.spell(['N', 'L', ['I', [0, 0]]]).strip() == 'N L I#1 2 00'                            # all zeros: no scale, a width
    for node in (['D', 5412000000000, [0, 1000000, -2000000]], ['I', [3000, 6000, 9000]], ['R', [[1000000, 5], [0, 7]]], ['E', 2000, [[1000, 3]]], ['I', [10 ** 14, 0]]):
        assert ST.parse(ST.spell(['N', 'L', node])) == ['N', 'L', node]


def test_fixed_width_digit_strings_for_small_non_negative_values():
    assert ST.spell(['N', 'L', ['I', [0, 1, 2, 0, 1, 2, 7]]]).strip() == 'N L I#1 7 0120127'
    assert ST.spell(['N', 'L', ['D', 1000, [1, 1, 12, 0, 99]]]).strip() == 'N L D#2 1000 5 0101120099'
    assert ST.spell(['N', 'L', ['I', [538, 100, 12, 7]]]).strip() == 'N L I#3 4 538100012007'
    assert ST.spell(['N', 'L', ['I', [538, 0, 12]]]).strip() == 'N L I#3 3 538000012'
    assert ST.spell(['N', 'L', ['I', [1538, 0, 12]]]).strip() == 'N L I 3 1538 0 12'              # four digits: no width, no scale
    assert ST.spell(['N', 'L', ['I', [1, -1, 2]]]).strip() == 'N L I 3 1 -1 2'                  # a negative value: spaced
    assert ST.spell(['N', 'L', ['I', [1000, 2000]]]).strip() == 'N L I*3 2 1 2'                 # four digits: the scale, not a width
    assert ST.spell(['N', 'L', ['I', [5]]]).strip() == 'N L I 1 5'                              # one value: the suffix would cost more
    for node in (['I', [0, 1, 2, 0, 1, 2, 7]], ['D', 1000, [1, 1, 12, 0, 99]], ['I', [538, 100, 12, 7]], ['D', -5, [0, 0, 0, 0]]):
        assert ST.parse(ST.spell(['N', 'L', node])) == ['N', 'L', node]
    for bad in ('N L I#1 3 12', 'N L I#4 1 0001', 'N L D#1 0 2 1x', 'N L R#1 1 1 1'):
        try:
            ST.parse(bad)
        except ValueError:
            continue
        raise AssertionError('accepted %r' % bad)


def test_malformed_text_refuses():
    for bad in ('V', 'M 2 a b V 1', 'N L D*x 1 2 3', 'L 1 V 1 V 2', 'Q L 1 V a I 1', 'C L 1 f', 'N L D*6 1 1 x'):
        try:
            ST.parse(bad)
        except ValueError:
            continue
        raise AssertionError('accepted %r' % bad)


def test_reader_rejects_non_ascii_digits_and_depth():
    for bad in ('V \u0661', 'N L I#1 2 \u0661\u0662', 'N L I 1 \u0661', 'L 1 ' * 300 + 'V 1', 'V 1 V 2', 'M 1 null V 1'):
        try:
            ST.parse(bad)
        except ValueError:
            continue
        raise AssertionError('accepted %r' % bad[:20])


def test_random_structural_trees_round_trip():
    import random
    rnd = random.Random(20260921)
    atoms = [None, True, False, 0, -7, 10 ** 15, '', 'a b', 'null', 'x.y', '"', 'I#1', '\u00e9', 'a\\b', 'tab\there']
    def ints():
        vals = [rnd.randint(-3, 9) * rnd.choice([1, 1000]) for _ in range(rnd.randint(0, 6))]
        k = rnd.random()
        if k < 0.3: return ['I', vals]
        if k < 0.6: return ['D', rnd.randint(-5, 5) * 1000, vals]
        if k < 0.8: return ['R', [[v, rnd.randint(1, 3)] for v in vals]]
        return ['E', rnd.randint(0, 9), [[v, rnd.randint(1, 3)] for v in vals]]
    def tree(depth=0):
        k = rnd.random() if depth < 4 else 0.0
        if k < 0.4: return ['V', rnd.choice(atoms)]
        if k < 0.5: return ['F', repr(rnd.choice([1.5, -0.0, 1e-7, 5.412]))]
        if k < 0.55: return ['X', rnd.choice(['', '00ff'])]
        if k < 0.62:
            n = rnd.randint(0, 3)
            return ['M', [rnd.choice(['a', 'b c', 'null', '1', 'k.k']) + str(i) for i in range(n)], [tree(depth + 1) for _ in range(n)]]
        if k < 0.7: return [rnd.choice(['L', 'T']), [tree(depth + 1) for _ in range(rnd.randint(0, 3))]]
        if k < 0.8: return ['N', rnd.choice(['L', 'T']), ints()]
        if k < 0.9: return ['S', 'L', rnd.randint(0, 3), tree(depth + 1)]
        return ['Q', 'L', [tree(depth + 1) for _ in range(rnd.randint(0, 3))], ints()]
    for _ in range(600):
        t = tree()
        assert ST.canonical(ST.parse(ST.spell(t))) == ST.canonical(t), t
