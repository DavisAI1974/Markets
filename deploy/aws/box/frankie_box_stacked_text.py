"""STACKED_TEXT_V1: an exact, token-dense spelling of a stacked native-context envelope (granite_context_stacked).

The critic's stacked snapshot is the largest single value the BOSS reads after the lossless render (about 91k tokens
of the state member, Greg 2026-09-21 12:2xZ: shrink every category, stack the stacks). The codec already delta- and
run-encodes every column (D / R / E recipes, Q dictionaries, C tables), so what the tokenizer pays for is the JSON
syntax around them: `["V","ts_event"]` is eight tokens for one field name, `[123,456]` two tokens per delta. This
module spells the SAME tagged tree in prefix notation with explicit counts and whitespace between atoms, and
`parse` inverts it to the identical tree; `prove` compares the canonical JSON of both before a render may use it.

Grammar (every node is a tag followed by its parts; whitespace separates atoms; counts make it unambiguous):
  V <atom>                    a primitive: null | true | false | an integer | a string (bare when it starts with a letter
                              or underscore and holds only [A-Za-z0-9_.:/@+-], JSON-quoted otherwise)
  F <repr>  H <hex16>  X <hex|.>  G <base64>     the codec's float / bits / bytes / 256-bit spellings, verbatim (`.` = empty hex)
  M <n> <key>*n <node>*n      an ordered map (keys are string atoms)
  L <n> <node>*n   T <n> <node>*n                a list / a tuple
  C <L|T> <n> <field>*n <column node>*n          a named-column table
  S <L|T> <count> <node>      one node repeated
  Q <L|T> <n> <node>*n <ints>     a dictionary of nodes and an integer recipe of indexes
  N <L|T> <ints>              an integer sequence
  B <L|T> <count> <n> <ints>*n   byte strings transposed into n integer columns
  ints: I <n> <int>*n | D <seed> <n> <delta>*n | R <n> (<value> <count>)*n | E <seed> <n> (<delta> <count>)*n
  A recipe tag may carry `*k` (I*6, D*6, R*6, E*6): every value of the recipe (the seed, the values, the deltas; never
  a run count) is written divided by 10^k, all of them being exact multiples (checked when spelled; the parser
  multiplies back). Measured with the pinned tokenizer: a delta of 1000000 is three tokens, 1 is one.
  An I or D recipe may instead carry `#w` (w = 1..3): its values (the D seed stays a separate atom) are one token of
  n*w decimal digits, each value zero-padded to width w, all of them non-negative and below 10^w (checked when
  spelled). Measured (run 35605419072): the action, side, flags, sequence and size columns of the record table are
  3,262 single digits each, 6.5k tokens spaced, about 1.1k as one digit string (the tokenizer packs three digits).
Newlines are whitespace: the spelling starts a new line before every M, C and column so the reading parts (line-based)
cut between values. The text is a projection of the JSON, not a new encoding: nothing is reduced or summarized.
"""
from __future__ import annotations

import json
import re

SCHEMA = 'STACKED_TEXT_V1'
BARE = re.compile(r'[A-Za-z_][A-Za-z0-9_.:/@+-]*')
KEYWORDS = {'null', 'true', 'false'}
LEAF = {'V', 'F', 'H', 'X', 'G'}
INT_TAGS = {'I', 'D', 'R', 'E'}
_DECODER = json.JSONDecoder()


def canonical(tree):
    """The codec's own text of a tree (granite_context_stacked._text): the equality the proof compares."""
    return json.dumps(tree, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def _atom(value):
    if value is None:
        return 'null'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if type(value) is int:
        return str(value)
    if type(value) is str:
        if BARE.fullmatch(value) and value not in KEYWORDS:
            return value
        return json.dumps(value, ensure_ascii=True)
    raise ValueError('atom must be null, bool, int or str: %r' % type(value).__name__)


SCALE_MIN, SCALE_MAX = 3, 12


def _scale(values):
    """The largest k (SCALE_MIN..SCALE_MAX) with every value a multiple of 10^k, else 0."""
    k, seen = SCALE_MAX, False
    for v in values:
        if v == 0:
            continue
        seen = True
        z, a = 0, abs(v)
        while a % 10 == 0 and z < k:
            a //= 10; z += 1
        k = min(k, z)
        if k < SCALE_MIN:
            return 0
    return k if seen else 0


def _div(v, k):
    q = 10 ** k
    if v % q:
        raise ValueError('scaled value is not a multiple of its scale')
    return v // q


WIDTH_MAX = 3


def _width(values):
    """The fixed digit width w (1..WIDTH_MAX) for a list of at least two non-negative ints all below 10^w, else 0.
    Measured with the pinned tokenizer: a spaced value costs about two tokens (`1 2 3 4 5 6 7 8` = 15), a digit
    string one token per three digits, so the string wins for every width up to WIDTH_MAX."""
    if len(values) < 2 or any(v < 0 for v in values):
        return 0
    w = max(len(str(v)) for v in values)
    return w if w <= WIDTH_MAX else 0


def _ints(node, out):
    tag = node[0]
    if tag == 'I':
        values = node[1]; w = _width(values)
        if w:
            out.append('%s#%d %d %s' % (tag, w, len(values), ''.join('%0*d' % (w, v) for v in values)))
            return
        k = _scale(values); t = tag + ('*%d' % k if k else '')
        out.append('%s %d' % (t, len(values))); out.extend(str(_div(v, k)) for v in values)
    elif tag == 'D':
        w = _width(node[2])
        if w:
            out.append('%s#%d %d %d %s' % (tag, w, node[1], len(node[2]), ''.join('%0*d' % (w, v) for v in node[2])))
            return
        k = _scale([node[1]] + list(node[2])); t = tag + ('*%d' % k if k else '')
        out.append('%s %d %d' % (t, _div(node[1], k), len(node[2]))); out.extend(str(_div(v, k)) for v in node[2])
    elif tag == 'R':
        k = _scale([v for v, c in node[1]]); t = tag + ('*%d' % k if k else '')
        out.append('%s %d' % (t, len(node[1]))); out.extend('%d %d' % (_div(v, k), c) for v, c in node[1])
    elif tag == 'E':
        k = _scale([node[1]] + [v for v, c in node[2]]); t = tag + ('*%d' % k if k else '')
        out.append('%s %d %d' % (t, _div(node[1], k), len(node[2]))); out.extend('%d %d' % (_div(v, k), c) for v, c in node[2])
    else:
        raise ValueError('unknown integer recipe %r' % tag)


def _spell(node, out):
    tag = node[0]
    if tag == 'V':
        out.append('V ' + _atom(node[1]))
    elif tag in ('F', 'H', 'G'):
        out.append(tag + ' ' + node[1])
    elif tag == 'X':
        out.append('X ' + (node[1] or '.'))
    elif tag == 'M':
        keys, values = node[1], node[2]
        out.append('\nM %d %s' % (len(keys), ' '.join(_atom(k) for k in keys)))
        for v in values:
            _spell(v, out)
    elif tag in ('L', 'T'):
        out.append('%s %d' % (tag, len(node[1])))
        for v in node[1]:
            _spell(v, out)
    elif tag == 'C':
        keys, columns = node[2], node[3]
        out.append('\nC %s %d %s' % (node[1], len(keys), ' '.join(_atom(k) for k in keys)))
        for column in columns:
            out.append('\n')
            _spell(column, out)
    elif tag == 'S':
        out.append('S %s %d' % (node[1], node[2]))
        _spell(node[3], out)
    elif tag == 'Q':
        out.append('Q %s %d' % (node[1], len(node[2])))
        for v in node[2]:
            _spell(v, out)
        _ints(node[3], out)
    elif tag == 'N':
        out.append('N %s' % node[1])
        _ints(node[2], out)
    elif tag == 'B':
        out.append('B %s %d %d' % (node[1], node[2], len(node[3])))
        for column in node[3]:
            _ints(column, out)
    else:
        raise ValueError('unknown stacked node %r' % tag)


def spell(tree):
    """The STACKED_TEXT_V1 text of a stacked tree (the envelope's `data`, or any node)."""
    out = []
    _spell(tree, out)
    text = ' '.join(out).replace(' \n ', '\n').replace(' \n', '\n').replace('\n ', '\n')
    return text.strip('\n') + '\n'


class _Cursor:
    def __init__(self, text):
        self.text, self.pos, self.n = text, 0, len(text)

    def token(self):
        text, i = self.text, self.pos
        while i < self.n and text[i] in ' \n\t\r':
            i += 1
        if i >= self.n:
            raise ValueError('unexpected end of stacked text')
        if text[i] == '"':
            value, end = _DECODER.raw_decode(text, i)
            self.pos = end
            return ('str', value)
        j = i
        while j < self.n and text[j] not in ' \n\t\r':
            j += 1
        self.pos = j
        return ('bare', text[i:j])

    def atom(self):
        kind, value = self.token()
        if kind == 'str':
            return value
        if value == 'null':
            return None
        if value == 'true':
            return True
        if value == 'false':
            return False
        if re.fullmatch(r'-?\d+', value):
            return int(value)
        if BARE.fullmatch(value):
            return value
        raise ValueError('unreadable atom %r' % value[:40])

    def string(self):
        kind, value = self.token()
        if kind == 'str':
            return value
        if BARE.fullmatch(value) and value not in KEYWORDS:
            return value
        raise ValueError('string atom expected, got %r' % value[:40])

    def bare(self):
        kind, value = self.token()
        if kind != 'bare':
            raise ValueError('bare token expected')
        return value

    def int(self):
        value = self.bare()
        if not re.fullmatch(r'-?\d+', value):
            raise ValueError('integer expected, got %r' % value[:40])
        return int(value)

    def done(self):
        return not self.text[self.pos:].strip()


def _digits(c, n, w):
    token = c.bare()
    if len(token) != n * w or not token.isdigit():
        raise ValueError('fixed-width digit string of %d x %d digits expected' % (n, w))
    return [int(token[i * w:(i + 1) * w]) for i in range(n)]


def _parse_ints(c):
    tag = c.bare()
    if '#' in tag:
        tag, _, w = tag.partition('#')
        if tag not in ('I', 'D') or not re.fullmatch(r'[1-3]', w):
            raise ValueError('fixed-width digits are I#w or D#w with w in 1..3')
        w = int(w)
        if tag == 'I':
            n = c.int()
            return ['I', _digits(c, n, w)]
        seed, n = c.int(), c.int()
        return ['D', seed, _digits(c, n, w)]
    tag, star, k = tag.partition('*')
    if star and not re.fullmatch(r'\d{1,2}', k):
        raise ValueError('integer recipe scale must be *k')
    q = 10 ** int(k) if star else 1
    if tag == 'I':
        n = c.int()
        return ['I', [c.int() * q for _ in range(n)]]
    if tag == 'D':
        seed, n = c.int() * q, c.int()
        return ['D', seed, [c.int() * q for _ in range(n)]]
    if tag == 'R':
        n = c.int()
        return ['R', [[c.int() * q, c.int()] for _ in range(n)]]
    if tag == 'E':
        seed, n = c.int() * q, c.int()
        return ['E', seed, [[c.int() * q, c.int()] for _ in range(n)]]
    raise ValueError('unknown integer recipe %r' % tag)


def _kind(c):
    kind = c.bare()
    if kind not in ('L', 'T'):
        raise ValueError('sequence kind L or T expected, got %r' % kind[:10])
    return kind


def _parse(c, depth=0):
    if depth > 256:
        raise ValueError('stacked text nests too deep')
    tag = c.bare()
    if tag == 'V':
        return ['V', c.atom()]
    if tag in ('F', 'H', 'G'):
        return [tag, c.bare()]
    if tag == 'X':
        value = c.bare()
        return ['X', '' if value == '.' else value]
    if tag == 'M':
        n = c.int()
        keys = [c.string() for _ in range(n)]
        return ['M', keys, [_parse(c, depth + 1) for _ in range(n)]]
    if tag in ('L', 'T'):
        n = c.int()
        return [tag, [_parse(c, depth + 1) for _ in range(n)]]
    if tag == 'C':
        kind, n = _kind(c), c.int()
        keys = [c.string() for _ in range(n)]
        return ['C', kind, keys, [_parse(c, depth + 1) for _ in range(n)]]
    if tag == 'S':
        kind, count = _kind(c), c.int()
        return ['S', kind, count, _parse(c, depth + 1)]
    if tag == 'Q':
        kind, n = _kind(c), c.int()
        items = [_parse(c, depth + 1) for _ in range(n)]
        return ['Q', kind, items, _parse_ints(c)]
    if tag == 'N':
        kind = _kind(c)
        return ['N', kind, _parse_ints(c)]
    if tag == 'B':
        kind, count, n = _kind(c), c.int(), c.int()
        return ['B', kind, count, [_parse_ints(c) for _ in range(n)]]
    raise ValueError('unknown stacked node %r' % tag[:10])


def parse(text):
    """The tree the text spells; raises when a token is left over or the text is malformed."""
    c = _Cursor(text)
    tree = _parse(c)
    if not c.done():
        raise ValueError('stacked text carries tokens after the tree')
    return tree


def prove(tree):
    """spell then parse; returns the text only when the parsed tree's canonical JSON equals the original's."""
    text = spell(tree)
    if canonical(parse(text)) != canonical(tree):
        raise ValueError('STACKED_TEXT_V1 spelling does not parse back to the same tree')
    return text


def is_envelope(node):
    """A stacked envelope dict (schema, prompt_version, grammar_sha256, data) as the codec builds it."""
    return (isinstance(node, dict) and set(node) == {'schema', 'prompt_version', 'grammar_sha256', 'data'}
            and node.get('schema') == 'BOSS_GRANITE_NATIVE_STACKED_CONTEXT_V1' and isinstance(node.get('data'), list))
