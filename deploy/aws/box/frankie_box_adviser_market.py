"""Exact existing-cutoff market context for governed adviser inputs.

Contract (FRANKIE_ADVISER_MARKET_CONTEXT_V1)
  Input: the shared reader identity a teacher or classroom already published, the day, and that
  measurement's ORIGINAL explicit source scope (source_hash, as_of, through_cursor). Never a Frankie
  private target selection, answer, grade, claim or private reasoning.
  Output: one complete picture at the INPUT whose original adapter cursor equals through_cursor, as
  exact typed text with its sha256; a `read` block saying what was read and verified and where the
  read stopped; a `coverage` block naming what is thin at that instant; a `picture_render` block (the
  same picture spelled through every token stack that shortens it, each proven by parse-back to the
  exact typed bytes; Greg, 2026-09-28: every stack that works gets used); an `all_99` block (every
  entry of the pinned 99-layer registry with its route into this picture and its disposition at this
  instant; Greg, 2026-10-07: the 99 layers are combined for Frankie first, nothing silent).
  Material (FRANKIE_ADVISER_MATERIAL_RENDER_V1, render_material / unstack_material_text): everything else an adviser
  reads (exchange items, seat records, findings, the classroom package, Jev's brain, the comparison material) through
  every existing lossless stack, layered where each still shortens, each layer proven by parse-back, the size after
  every layer recorded for the consumer's server token counts; nothing dropped, truncated or summarized.
  Errors, one way: ValueError for contradictions of identity, pinned bytes or scope. Those are
  integrity failures and stay visible. Missing layers, a failed/unpaired/unknown outcome at the
  cutoff, an unavailable clock or an absent external day file never raise: the instant stays in,
  thinner, with its dispositions written down (Greg, 2026-10-07).

The full ordered reader stays owner-local and accessible (`iter_pictures`). This module selects no
target extrema and no new scientific window, serializes one instant (not a day) and makes no model
call. Reaching a prompt is not proof a model experienced every historical picture. Nothing here keys
on how many days a run holds: one instant of one day, whatever the run's length.
"""
import copy
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

# The one 99-entry registry (Greg, 2026-10-07): the entry list and the group roles come from
# frankie_box_all99_coverage; this piece keeps its own ROUTES and dispositions below.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import frankie_box_all99_coverage as ALL99  # noqa: E402

SCHEMA = 'FRANKIE_ADVISER_MARKET_CONTEXT_V1'
REFERENCE_SCHEMA = 'FRANKIE_ADVISER_MARKET_CONTEXT_REFERENCE_V1'
WORKFLOW_REPORT_SCHEMA = 'FRANKIE_PIECE_WORKFLOW_REPORT_V1'
RENDER_SCHEMA = 'FRANKIE_ADVISER_PICTURE_RENDER_V1'
ALL_99_SCHEMA = 'FRANKIE_ALL_99_COVERAGE_V1'
MISSING_COVERAGE_RULE = 'every_authentic_boundary_kept_with_thinner_explicit_picture'
WORKERS = 15      # the former fixed reader worker count; kept for reference (the reader now sizes from the lane, below)
PINNED_TASK_SECONDS = 1800.0   # per-result wait on a pinned pool (L-2): past it the pool is ended and the rest run in-process
USE ='complete same-time picture at the existing original source cutoff; no target-derived selection'
LIMIT = ('model receives this complete cutoff picture, not every historical picture; full ordered reader remains '
         'available to owner code; no time-addressable model query protocol or new scientific calculation')
REPO = Path(__file__).resolve().parents[3]
# The pinned 99-layer registry (content identity 239a1480...) is named by the committed crosswalk of run
# 33746436209; the crosswalk file is pinned by knowledge/CYCLE_CALCULATION_PINS.json (path, bytes, sha256).
# The registry JSON itself is not in this checkout; the crosswalk carries every layer_id and group_id.
REGISTRY_SHA256 = ALL99.REGISTRY_SHA256
CALCULATION_PINS = REPO / 'research/kalshi/frankie_boss/knowledge/CYCLE_CALCULATION_PINS.json'
STACK_GRAMMAR = 'STACKED_TEXT_V1'
DIGEST_GRAMMAR = 'DIGEST_V9'
LEGEND = ('PICTURE GRAMMAR (' + STACK_GRAMMAR + ' over the exact typed picture; parse-back proven byte-exact): '
          'V literal (null, true, false, integer or string); H float64 as IEEE-754 hex bits; X byte hex (. = empty); '
          'M n keys values = ordered map; L n / T n = list / tuple of n nodes; C L|T n fields columns = table, row i '
          'takes item i of every column; S kind count node = node repeated count times; Q kind n nodes recipe = '
          'dictionary of n nodes and an integer recipe of indexes; N kind recipe = integers. Recipes: I literal, '
          'D seed then deltas, R value/count runs, E seed then delta/count runs; *k means every value divided by 10^k; '
          '#w means packed w-digit values. Conventions: a map with the single key $keyed holds a list of (key, value) '
          'tuples (non-string keys); a key written $$x is the literal key $x; a top map {$dictionary, $value} holds '
          'shared subtrees, each referenced by M 1 $ref V r<hash>; a map {$digest, $keys, $kind} holds a '
          + DIGEST_GRAMMAR + ' table block of the same rows. Nothing is sampled, rounded or omitted.')


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------------------------ the token stacks
# The picture text is frankie_box_classroom_code._exact_market_text: {"encoding": ..., "complete_value": T}
# where T is the typed tree ['mapping', [[pack(key), T]...]] | ['list'|'tuple', [T...]] | c15_journal.pack(scalar)
# (["int", v] ["str", s] ["null"] ["bool", b] ["float64", hex16] ["bytes", hex]). The stacks below spell the
# SAME tree in frankie_box_stacked_text's grammar (L1 of the reading render: every tag becomes its plain
# atom; the stacked_v1/v2 column tables, repeats, dictionaries and integer recipes; L3 content-addressed
# dedup of repeated subtrees; the DIGEST_V9 table grammar where it spells a flat table shorter) and prove
# the spelling by parsing it back to the identical typed bytes before anything may read it.

def _esc(key):
    return '$' + key if key.startswith('$') else key


def _unesc(key):
    return key[1:] if key.startswith('$$') else key


def _slots(node):
    """(container, index) of every child of a stacked node, so a child can be replaced in place; leaves have none."""
    tag = node[0]
    if tag == 'M':
        container = node[2]
    elif tag in ('L', 'T'):
        container = node[1]
    elif tag == 'C':
        container = node[3]
    elif tag == 'Q':
        container = node[2]
    elif tag == 'S':
        return [(node, 3)]
    else:
        return []
    return [(container, i) for i in range(len(container))]


def _expand_ints(node):
    tag = node[0]
    if tag == 'I':
        return list(node[1])
    if tag == 'D':
        out, value = [node[1]], node[1]
        for delta in node[2]:
            value += delta
            out.append(value)
        return out
    if tag == 'R':
        return [v for v, count in node[1] for _ in range(count)]
    if tag == 'E':
        out, value = [node[1]], node[1]
        for delta, count in node[2]:
            for _ in range(count):
                value += delta
                out.append(value)
        return out
    raise ValueError('unknown integer recipe %r' % tag)


def _float_bits(value):
    return struct.pack('>d', value).hex()


class _Stacker:
    """Typed picture tree -> stacked tree, choosing at every sequence the candidate that spells shortest.
    RECIPES / DIGEST (both True for the picture, unchanged): whether the N integer-recipe and DIGEST table candidates
    are offered; the material stacks below turn them on layer by layer and measure each."""
    RECIPES = True
    DIGEST = True

    def __init__(self):
        import frankie_box_stacked_text as ST
        from research.kalshi.frankie_boss.granite_context_stacked import _integers
        self.ST, self._integers = ST, _integers
        self.counts = dict(tables=0, repeats=0, dictionaries=0, integer_sequences=0, keyed_maps=0, digest_tables=0,
                           digest_refused=0)

    def _length(self, node):
        return len(self.ST.spell(node))

    def stack(self, node):
        tag = node[0]
        if tag == 'mapping':
            items = node[1]
            if all(k[0] == 'str' for k, _ in items):
                return ['M', [_esc(k[1]) for k, _ in items], [self.stack(v) for _, v in items]]
            self.counts['keyed_maps'] += 1
            return ['M', ['$keyed'], [['L', [['T', [self.stack(k), self.stack(v)]] for k, v in items]]]]
        if tag in ('list', 'tuple'):
            return self.sequence(node[1], 'L' if tag == 'list' else 'T')
        if tag in ('int', 'str', 'bool'):
            return ['V', node[1]]
        if tag == 'null':
            return ['V', None]
        if tag == 'float64':
            return ['H', node[1]]
        if tag == 'bytes':
            return ['X', node[1]]
        raise ValueError('typed picture carries an unknown scalar tag %r' % tag)

    def sequence(self, items, kind):
        encoded = [self.stack(v) for v in items]
        choices = [(kind, [kind, encoded])]
        if len(items) >= 2:
            spellings = [self.ST.canonical(e) for e in encoded]
            if len(set(spellings)) == 1:
                choices.append(('S', ['S', kind, len(items), encoded[0]]))
            seen, dictionary, indexes = {}, [], []
            for spelling, item in zip(spellings, encoded):
                if spelling not in seen:
                    seen[spelling] = len(dictionary)
                    dictionary.append(item)
                indexes.append(seen[spelling])
            if len(dictionary) < len(items):
                choices.append(('Q', ['Q', kind, dictionary, self._integers(indexes)]))
            if all(v[0] == 'int' for v in items) and self.RECIPES:
                choices.append(('N', ['N', kind, self._integers([v[1] for v in items])]))
            if all(v[0] == 'mapping' and v[1] and all(k[0] == 'str' for k, _ in v[1]) for v in items):
                keys = [k[1] for k, _ in items[0][1]]
                if keys and all([k[1] for k, _ in v[1]] == keys for v in items):
                    columns = [self.sequence([v[1][j][1] for v in items], 'L') for j in range(len(keys))]
                    choices.append(('C', ['C', kind, [_esc(k) for k in keys], columns]))
                    digest = self.digest_table(items, keys, kind) if self.DIGEST else None
                    if digest is not None:
                        choices.append(('digest', digest))
        label, best = min(choices, key=lambda choice: self._length(choice[1]))
        counter = {'S': 'repeats', 'Q': 'dictionaries', 'N': 'integer_sequences', 'C': 'tables', 'digest': 'digest_tables'}.get(label)
        if counter:
            self.counts[counter] += 1
        return best

    def digest_table(self, items, keys, kind):
        """The DIGEST_V9 spelling of a flat table (every cell a scalar, no dotted key): a candidate only when
        it parses back to the identical rows, float bits included; a refusal is counted, never silent."""
        import frankie_box_digest_render as DG
        if not keys or any('.' in k for k in keys):
            return None
        rows = []
        for v in items:
            row = {}
            for key, cell in v[1]:
                tag = cell[0]
                if tag == 'int' or tag == 'str' or tag == 'bool':
                    row[key[1]] = cell[1]
                elif tag == 'null':
                    row[key[1]] = None
                elif tag == 'float64':
                    row[key[1]] = struct.unpack('>d', bytes.fromhex(cell[1]))[0]
                else:
                    return None
            rows.append(row)
        try:
            block = DG.render_table('picture', rows, None)
            _, parsed = DG.parse_table(block, None)
        except Exception:
            self.counts['digest_refused'] += 1
            return None
        if len(parsed) != len(rows) or not all(DG._same(a, b) for a, b in zip(parsed, rows)):
            self.counts['digest_refused'] += 1
            return None
        for a, b in zip(parsed, rows):
            for key in keys:
                if isinstance(b[key], float) and (not isinstance(a[key], float) or _float_bits(a[key]) != _float_bits(b[key])):
                    self.counts['digest_refused'] += 1
                    return None
                if type(a[key]) is not type(b[key]):
                    self.counts['digest_refused'] += 1
                    return None
        return ['M', ['$digest', '$keys', '$kind'], [['V', block], ['L', [['V', k] for k in keys]], ['V', kind]]]


def _unstack(node):
    """Stacked tree -> typed picture tree (the exact inverse of _Stacker.stack for every candidate)."""
    tag = node[0]
    if tag == 'V':
        value = node[1]
        if value is None:
            return ['null']
        if value is True or value is False:
            return ['bool', value]
        if type(value) is int:
            return ['int', value]
        if type(value) is str:
            return ['str', value]
        raise ValueError('stacked literal of an unexpected type')
    if tag == 'H':
        return ['float64', node[1]]
    if tag == 'F':
        # material stacks only: a float written as its shortest round-trip decimal (float(repr(x)) == x)
        return ['float64', _float_bits(float(node[1]))]
    if tag == 'X':
        return ['bytes', node[1]]
    if tag == 'M':
        keys, values = node[1], node[2]
        if keys == ['$json_text', '$value']:
            # material stacks only (L2): a text that is exactly this JSON value in the named layout
            return ['jsontext', values[0][1], _unstack(values[1])]
        if keys == ['$concat']:
            # material stacks only (L5): one string written as the concatenation of its parts
            parts = [_unstack(part) for part in values[0][1]]
            if any(part[0] != 'str' for part in parts):
                raise ValueError('a $concat part is not a string')
            return ['str', ''.join(part[1] for part in parts)]
        if keys == ['$keyed']:
            pairs = _unstack(values[0])
            return ['mapping', [[k, v] for k, v in (pair[1] for pair in pairs[1])]]
        if keys == ['$digest', '$keys', '$kind']:
            import frankie_box_digest_render as DG
            _, rows = DG.parse_table(values[0][1], None)
            columns = [k[1] for k in values[1][1]]
            kind = 'list' if values[2][1] == 'L' else 'tuple'
            out = []
            for row in rows:
                items = []
                for key in columns:
                    cell = row[key]
                    if cell is None:
                        typed = ['null']
                    elif cell is True or cell is False:
                        typed = ['bool', cell]
                    elif type(cell) is int:
                        typed = ['int', cell]
                    elif type(cell) is float:
                        typed = ['float64', _float_bits(cell)]
                    else:
                        typed = ['str', cell]
                    items.append([['str', key], typed])
                out.append(['mapping', items])
            return [kind, out]
        return ['mapping', [[['str', _unesc(k)], _unstack(v)] for k, v in zip(keys, values)]]
    if tag in ('L', 'T'):
        return ['list' if tag == 'L' else 'tuple', [_unstack(v) for v in node[1]]]
    if tag == 'C':
        kind, keys, columns = node[1], node[2], node[3]
        expanded = [_unstack(column)[1] for column in columns]
        count = len(expanded[0]) if expanded else 0
        rows = [['mapping', [[['str', _unesc(k)], expanded[j][i]] for j, k in enumerate(keys)]] for i in range(count)]
        return ['list' if kind == 'L' else 'tuple', rows]
    if tag == 'S':
        kind, count, item = node[1], node[2], node[3]
        typed = _unstack(item)
        return ['list' if kind == 'L' else 'tuple', [copy.deepcopy(typed) for _ in range(count)]]
    if tag == 'Q':
        kind, dictionary, recipe = node[1], node[2], node[3]
        typed = [_unstack(v) for v in dictionary]
        return ['list' if kind == 'L' else 'tuple', [copy.deepcopy(typed[i]) for i in _expand_ints(recipe)]]
    if tag == 'N':
        return ['list' if node[1] == 'L' else 'tuple', [['int', v] for v in _expand_ints(node[2])]]
    raise ValueError('stacked node %r has no typed inverse here' % tag)


def _dedup(tree, canonical, forced=None):
    """L3 of the reading render on the stacked tree: a subtree spelled identically more than once is kept once
    under $dictionary and referenced where it recurs, only where the arithmetic says it saves characters.
    forced {name: ['V', text]} (the material stacks' L5 containment only; None for the picture, unchanged): those
    strings are dictionary entries already referenced by $concat parts; every literal occurrence becomes a reference."""
    forced = dict(forced or {})
    forced_key = {_sha256(canonical(node).encode()): name for name, node in forced.items()}
    counts, length = {}, {}
    def visit(node):
        if node[0] in ('V', 'H', 'X'):
            return
        text = canonical(node)
        key = _sha256(text.encode())
        counts[key] = counts.get(key, 0) + 1
        length[key] = len(text)
        for container, i in _slots(node):
            visit(container[i])
    visit(tree)
    dictionary, order, refs = {}, [], 0
    ref_cost, entry_overhead = 34, 26
    def replace(node):
        nonlocal refs
        if node[0] in ('V', 'H', 'X'):
            if forced_key and node[0] == 'V' and type(node[1]) is str:
                name = forced_key.get(_sha256(canonical(node).encode()))
                if name is not None:
                    refs += 1
                    return ['M', ['$ref'], [['V', name]]]
            return node
        key = _sha256(canonical(node).encode())
        count, size = counts[key], length[key]
        if count >= 2 and (count - 1) * size - count * ref_cost - entry_overhead > 0:
            name = 'r' + key[:20]
            if name not in dictionary:
                dictionary[name] = node
                order.append(name)
            refs += 1
            return ['M', ['$ref'], [['V', name]]]
        for container, i in _slots(node):
            container[i] = replace(container[i])
        return node
    tree = replace(tree)
    for name, node in forced.items():
        if name not in dictionary:
            dictionary[name] = node
            order.append(name)
    if not dictionary:
        return tree, 0, 0
    return (['M', ['$dictionary', '$value'], [['M', order, [dictionary[name] for name in order]], tree]],
            len(dictionary), refs)


def _resolve(node, dictionary):
    if node[0] == 'M' and node[1] == ['$ref']:
        return _resolve(copy.deepcopy(dictionary[node[2][0][1]]), dictionary)
    for container, i in _slots(node):
        container[i] = _resolve(container[i], dictionary)
    return node


def unstack_text(text):
    """The exact typed picture text the stacked text spells (the reader for every consumer; raises on a
    malformed or inconsistent spelling)."""
    import frankie_box_stacked_text as ST
    tree = ST.parse(text)
    if tree[0] == 'M' and tree[1] == ['$dictionary', '$value']:
        entries = tree[2][0]
        dictionary = dict(zip(entries[1], entries[2]))
        tree = _resolve(tree[2][1], dictionary)
    typed = _unstack(tree)
    if typed[0] != 'mapping' or [k[1] for k, _ in typed[1]] != ['encoding', 'complete_value']:
        raise ValueError('stacked picture does not spell the typed picture envelope')
    encoding = typed[1][0][1]
    if encoding[0] != 'str':
        raise ValueError('stacked picture envelope has no encoding string')
    return json.dumps(dict(encoding=encoding[1], complete_value=typed[1][1][1]), separators=(',', ':'))


def render_stacks(picture_text):
    """Every token stack that shortens the exact typed picture text, applied and PROVEN: the result parses back
    to the identical bytes (unstack_text(text) == picture_text) before it is returned. Character counts are the
    proxy recorded here; the token count is measured where the text enters a prompt (the server's own
    tokenizer, recorded by that piece) and the canary comparison is that measurement."""
    import frankie_box_stacked_text as ST
    source = json.loads(picture_text)
    if not isinstance(source, dict) or list(source) != ['encoding', 'complete_value']:
        raise ValueError('picture text is not the exact typed envelope')
    typed = ['mapping', [[['str', 'encoding'], ['str', source['encoding']]], [['str', 'complete_value'], source['complete_value']]]]
    stacker = _Stacker()
    plain = stacker.stack(typed)
    plain_text = ST.spell(plain)
    layers = [dict(layer='L1_typed_tags_to_atoms_plus_column_tables_repeats_dictionaries_integer_recipes',
                   grammar=STACK_GRAMMAR, applied=True, counts=dict(stacker.counts),
                   chars_before=len(picture_text), chars_after=len(plain_text))]
    deduped, entries, refs = _dedup(copy.deepcopy(plain), ST.canonical)
    deduped_text = ST.spell(deduped) if entries else plain_text
    use_dedup = bool(entries) and len(deduped_text) < len(plain_text)
    if use_dedup:
        text, chosen = deduped_text, deduped
        layers.append(dict(layer='L3_content_addressed_dedup_of_repeated_subtrees', applied=True,
                           dictionary_entries=entries, references=refs,
                           chars_before=len(plain_text), chars_after=len(deduped_text)))
    else:
        text, chosen = plain_text, plain
        layers.append(dict(layer='L3_content_addressed_dedup_of_repeated_subtrees', applied=False,
                           reason=('no repeated subtree saves characters' if not entries else
                                   'dedup spelled longer than the plain stacking; plain kept'),
                           chars_before=len(plain_text), chars_after=len(plain_text)))
    if ST.canonical(ST.parse(text)) != ST.canonical(chosen):
        raise ValueError('stacked picture does not parse back to its stacked tree')
    if unstack_text(text) != picture_text:
        raise ValueError('stacked picture does not parse back to the exact typed picture bytes')
    return dict(schema=RENDER_SCHEMA, grammar=STACK_GRAMMAR, digest_grammar=DIGEST_GRAMMAR, text=text,
                sha256=_sha256(text.encode()), chars=len(text), source_chars=len(picture_text),
                source_sha256=_sha256(picture_text.encode()), layers=layers,
                proof=dict(parse_back='byte_exact', reader='frankie_box_adviser_market.unstack_text',
                           rule='every stack that shortens is used; each is proven by parse-back before use; '
                                'nothing is dropped, rounded or summarized'),
                tokens=dict(measured_here=False,
                            rule='the consuming piece records the server-counted tokens of the prompt this text enters; '
                                 'that measurement against source_chars is the canary; no number is guessed here'))


def verify_render(context):
    """Re-prove the retained render against the retained exact text before any prompt reads it."""
    render = context.get('picture_render')
    if render is None:
        return None
    if (render.get('schema') != RENDER_SCHEMA or _sha256(render['text'].encode()) != render.get('sha256')
            or render.get('source_sha256') != context['picture_sha256']
            or unstack_text(render['text']) != context['picture_text']):
        raise ValueError('retained picture render does not parse back to its exact typed picture')
    return render


# ------------------------------------------------------------------------------------ the material stacks
# Contract FRANKIE_ADVISER_MATERIAL_RENDER_V1 (Greg, 2026-09-28 "every token stack that works gets used"; 2026-10-07
# the optimizers restored on every workflow piece, "use what we already have too, try to stack as many as possible",
# "do not secretly shrink back down to top 10 or drop any data whatsoever"). Everything Granite and Jev read BESIDE
# the picture (exchange items, seat records, findings, the knowledge index, the classroom package, the directive,
# Jev's brain entries and lessons, the comparison material) goes through every existing lossless stack, layered on
# top of each other wherever each still shortens, each layer proven by parse-back to the exact source before it may
# be adopted, and its size recorded (render_material(...)['layers']; the consumer adds the server token count of
# every layer's text):
#   L0  legacy: the consumer's own text (json.dumps(sort_keys) or the file text), the baseline;
#   L1  compact JSON (the reading render's compact separators), json.loads equal to L0;
#   L2+L9  STACKED_TEXT_V1 with keys once: an ordered map writes its keys once (M), a list of same-keyed maps is a
#       column table (C), a repeated node is written once with its count (S), a list with repeated items writes each
#       distinct item once and the order as an index recipe (Q) (the _Stacker candidates); the reading render's L2
#       nested decoding: a text that is exactly a JSON value in a known layout is that value, its layout recorded;
#   R   value recipes (the stacked context's codec): integer sequences as I/D/R/E recipes with *k scales and #w digit
#       packing (N), a float written as its IEEE bits (H) where that is shorter than its decimal (F);
#   L10 DIGEST_V10 table blocks (frankie_box_digest_render) for flat same-keyed rows where they spell shorter, each
#       parsed back to the identical rows, float bits included, before it is a candidate;
#   L3  content-addressed dedup of repeated subtrees under $dictionary (the repeated-content dedupe);
#   L5  containment: a long string that contains another long string of the same block writes that span as a
#       reference to it.
# The brain dedupe (frankie_box_brain.load: identical bytes written once, later copies a one-line reference) is
# applied by the consumer across documents with dedupe_documents. Not applicable here, each for a recorded reason:
# L1 c15 unpack and L4 tensors (no c15 values or decoder tensors in this material), L6 cross-cycle ledger and L8
# known files (the model holds no earlier cycle and opens no file: the content would leave its view); L7 ranges are
# subsumed by the R integer recipes (a consecutive run is a D/E recipe). A layer that does not prove or does not
# shorten is not adopted and the reason is listed. Nothing is dropped, truncated, sampled or summarized.
MATERIAL_SCHEMA = 'FRANKIE_ADVISER_MATERIAL_RENDER_V1'
MATERIAL_ENCODING = 'STACKED_TEXT_V1_MATERIAL'
MATERIAL_DIGEST_GRAMMAR = 'DIGEST_V10'     # frankie_box_digest_render.TABLE_GRAMMAR (V9 tables read unchanged)
MATERIAL_LEGEND = (
    'MATERIAL GRAMMAR (' + STACK_GRAMMAR + '; every [material ...] text below parses back byte-exact to the JSON or '
    'text it replaces): V literal (null, true, false, integer or string; a string is bare or JSON-quoted); F float as '
    'its decimal; H float64 as IEEE-754 hex bits; M n keys values = map, keys written once; L n nodes = list; C L n '
    'fields columns = table, row i takes item i of every column, field names written once; S L count node = node '
    'repeated count times; Q L n nodes recipe = the n distinct items once, then the order as an index recipe; N L '
    'recipe = integers. Recipes: I literal values, D seed then deltas, R value/count runs, E seed then delta/count '
    'runs; *k = every value written divided by 10^k (multiply back); #w = values packed as one string of w-digit '
    'numbers. A map {$dictionary, $value} holds shared subtrees once, each referenced where it recurs by M 1 $ref V '
    'r<hash>; M 1 $concat L n parts = one string written as its parts in order (a part may be a $ref); M 2 $json_text '
    '$value = a text that is exactly that JSON value written in the named layout; a map {$digest, $keys, $kind} holds '
    'a ' + MATERIAL_DIGEST_GRAMMAR + ' table block of the same rows (header once, ^ = the cell above, deltas, @n dictionary, as '
    'its own header says); a key written $$x is the key $x. A [block k/n path=P rows=R] line starts part k: the value '
    'at path P (rows R = items R[0]..R[1]-1 of the list at P). Nothing is sampled, rounded or omitted.')
JSON_TEXT_MIN = 64           # L2: a text at least this long may be a JSON value in a known layout
CONTAIN_MIN = 256            # L5: a string at least this long may be written as a reference inside a longer one
CONTAIN_MAX_CANDIDATES = 4000   # L5 is O(n^2) in long strings; above this count it is not attempted (listed, lossless)
STACKED_LAYERS = (           # (layer, integer/float recipes offered, DIGEST tables offered), applied cumulatively
    ('L2_L9_keys_once_STACKED_TEXT_V1', False, False),
    ('R_value_recipes', True, False),
    ('L10_' + MATERIAL_DIGEST_GRAMMAR + '_tables', True, True))
_JSON_LAYOUTS = (           # (name, json.dumps keywords); a trailing newline is the '+nl' form of each
    ('sorted_indent1', dict(indent=1, sort_keys=True)), ('sorted_indent2', dict(indent=2, sort_keys=True)),
    ('sorted', dict(sort_keys=True)), ('sorted_compact', dict(sort_keys=True, separators=(',', ':'))),
    ('indent1', dict(indent=1)), ('indent2', dict(indent=2)), ('plain', {}), ('compact', dict(separators=(',', ':'))))
_LAYOUTS = dict(_JSON_LAYOUTS)


def _compact(value):
    return json.dumps(value, separators=(',', ':'))


def _layout_dump(value, layout):
    name, newline = (layout[:-3], '\n') if layout.endswith('+nl') else (layout, '')
    return json.dumps(value, **_LAYOUTS[name]) + newline


def _json_text(text, minimum=JSON_TEXT_MIN):
    """L2: ['jsontext', layout, typed] when text is exactly a JSON object/list in one of the known layouts; else None."""
    if len(text) < minimum or text.lstrip()[:1] not in ('{', '['):
        return None
    try:
        value = json.loads(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(value, (dict, list)):
        return None
    for name, keywords in _JSON_LAYOUTS:
        try:
            spelled = json.dumps(value, **keywords)
        except (ValueError, TypeError):
            return None
        for layout, candidate in ((name, spelled), (name + '+nl', spelled + '\n')):
            if candidate == text:
                return ['jsontext', layout, _material_typed(value)]
    return None


def _material_typed(value):
    """A JSON value (as json.loads gives it: key order kept) -> the typed tree the stacker reads."""
    if isinstance(value, dict):
        return ['mapping', [[['str', key], _material_typed(item)] for key, item in value.items()]]
    if isinstance(value, list):
        return ['list', [_material_typed(item) for item in value]]
    if value is None:
        return ['null']
    if value is True or value is False:
        return ['bool', value]
    if type(value) is int:
        return ['int', value]
    if type(value) is float:
        return ['float64', _float_bits(value)]
    if type(value) is str:
        found = _json_text(value)
        return found if found is not None else ['str', value]
    raise ValueError('material carries a non-JSON value of type %s' % type(value).__name__)


def _material_plain(typed):
    """The typed tree -> the JSON value it stands for (L2 nodes re-encoded to their exact text)."""
    tag = typed[0]
    if tag == 'mapping':
        out = {}
        for key, item in typed[1]:
            if key[0] != 'str':
                raise ValueError('material map key is not a string')
            out[key[1]] = _material_plain(item)
        return out
    if tag in ('list', 'tuple'):
        return [_material_plain(item) for item in typed[1]]
    if tag in ('int', 'str', 'bool'):
        return typed[1]
    if tag == 'null':
        return None
    if tag == 'float64':
        return struct.unpack('>d', bytes.fromhex(typed[1]))[0]
    if tag == 'jsontext':
        return _layout_dump(_material_plain(typed[2]), typed[1])
    raise ValueError('material typed node %r has no JSON value' % tag)


class _MaterialStacker(_Stacker):
    """The picture stacker's candidates on material: keys once, tables, repeats, dictionaries always; the value
    recipes (N, H) and DIGEST tables only when their layer is on (STACKED_LAYERS)."""

    def __init__(self, recipes, digest):
        super().__init__()
        self.RECIPES, self.DIGEST = recipes, digest

    def stack(self, node):
        tag = node[0]
        if tag == 'float64':
            decimal = repr(struct.unpack('>d', bytes.fromhex(node[1]))[0])
            return ['H', node[1]] if self.RECIPES and len(node[1]) < len(decimal) else ['F', decimal]
        if tag == 'jsontext':
            self.counts['json_texts'] = self.counts.get('json_texts', 0) + 1
            return ['M', ['$json_text', '$value'], [['V', node[1]], self.stack(node[2])]]
        return super().stack(node)


def _contain(tree, canonical):
    """L5 on a stacked tree, in place: a long V string that contains another long V string of the same tree writes
    that span as a $ref (the contained string becomes a forced dictionary entry). Returns (forced, contained, note)."""
    strings = {}
    def table(node):
        # a DIGEST table node's block text is read whole by its own parser: never a containment candidate or target
        return node[0] == 'M' and node[1] == ['$digest', '$keys', '$kind']

    def collect(node):
        if node[0] == 'V':
            if type(node[1]) is str and len(node[1]) >= CONTAIN_MIN:
                strings.setdefault(node[1], None)
            return
        if table(node):
            return
        for container, i in _slots(node):
            collect(container[i])
    collect(tree)
    if len(strings) > CONTAIN_MAX_CANDIDATES:
        return {}, 0, 'L5 not attempted: %d long strings (budget %d; O(n^2)); written as they are' % (
            len(strings), CONTAIN_MAX_CANDIDATES)
    ordered = sorted(strings, key=len, reverse=True)
    inner = {}
    for s in ordered:
        for t in ordered:
            if len(t) < len(s) and t in s:
                inner[s] = t                   # the longest long string it contains (the reading render takes one)
                break
    if not inner:
        return {}, 0, None
    targets = set(inner.values())     # a contained string stays one literal V (its occurrences become references)
    forced, contained = {}, 0
    def replace(node):
        nonlocal contained
        if node[0] == 'V':
            t = inner.get(node[1]) if type(node[1]) is str and node[1] not in targets else None
            if t is None:
                return node
            name = 'r' + _sha256(canonical(['V', t]).encode())[:20]
            forced[name] = ['V', t]
            parts = []
            for k, piece in enumerate(node[1].split(t)):
                if k:
                    parts.append(['M', ['$ref'], [['V', name]]])
                if piece:
                    parts.append(['V', piece])
            contained += 1
            return ['M', ['$concat'], [['L', parts]]]
        if table(node):
            return node
        for container, i in _slots(node):
            container[i] = replace(container[i])
        return node
    tree[:] = replace(tree)
    return forced, contained, None


def _material_tree_text(text):
    """A stacked material block -> the JSON value it spells (resolving $dictionary references)."""
    import frankie_box_stacked_text as ST
    tree = ST.parse(text)
    if tree[0] == 'M' and tree[1] == ['$dictionary', '$value']:
        entries = tree[2][0]
        tree = _resolve(tree[2][1], dict(zip(entries[1], entries[2])))
    return _material_plain(_unstack(tree))


def _layered(value):
    """Every stacked layer on one JSON value, cumulative: (best, trace). best = (text, facts) of the shortest proven
    spelling (None when no stacked layer proved); trace = one row per layer {layer, chars, adopted, reason, text}.
    A layer is adopted when it parses back to the exact value AND spells shorter than the layer before it."""
    import frankie_box_stacked_text as ST
    exact = _compact(value)
    typed = _material_typed(value)
    trace, best = [], None             # best: (tree, text, facts)

    def consider(layer, tree, facts):
        nonlocal best
        row = dict(layer=layer)
        try:
            text = ST.spell(tree)
            if ST.canonical(ST.parse(text)) != ST.canonical(tree):
                raise ValueError('the text does not parse back to its stacked tree')
            if _compact(_material_tree_text(text)) != exact:
                raise ValueError('the text does not parse back to the exact value')
        except (ValueError, RecursionError, KeyError, IndexError, TypeError) as error:
            row.update(chars=None, adopted=False, reason='parse-back refused: %s: %s' % (type(error).__name__, str(error)[:160]))
            trace.append(row)
            return
        adopted = best is None or len(text) < len(best[1])
        row.update(chars=len(text), adopted=adopted, text=text,
                   reason=None if adopted else 'not shorter than the layer before it (%d chars); not adopted' % len(best[1]))
        trace.append(row)
        if adopted:
            best = (tree, text, dict(facts, layers=[r['layer'] for r in trace if r['adopted']]))

    for layer, recipes, digest in STACKED_LAYERS:
        stacker = _MaterialStacker(recipes, digest)
        tree = stacker.stack(typed)
        consider(layer, tree, dict(counts=dict(stacker.counts), dedup_entries=0, dedup_refs=0, contained=0))
    if best is None:
        return None, trace
    base_tree, base_facts = best[0], best[2]
    deduped, entries, refs = _dedup(copy.deepcopy(base_tree), ST.canonical)
    if entries:
        consider('L3_dedup', deduped, dict(base_facts, dedup_entries=entries, dedup_refs=refs))
    else:
        trace.append(dict(layer='L3_dedup', chars=None, adopted=False, reason='no repeated subtree saves characters'))
    contained_tree = copy.deepcopy(base_tree)
    forced, contained, note = _contain(contained_tree, ST.canonical)
    if contained:
        both, entries, refs = _dedup(contained_tree, ST.canonical, forced=forced)
        consider('L5_containment', both, dict(base_facts, dedup_entries=entries, dedup_refs=refs, contained=contained))
    else:
        trace.append(dict(layer='L5_containment', chars=None, adopted=False,
                          reason=note or 'no long string contains another long string'))
    return (best[1], best[2]), trace


def _best_body(value, layered=None):
    """(body, encoding, facts, compact chars): the shorter of the value's best proven stacked text and compact JSON.
    layered: an already computed _layered(value) (the whole material's, reused for its first block)."""
    compact = _compact(value)
    try:
        best, trace = layered if layered is not None else _layered(value)
    except (ValueError, RecursionError) as error:
        return compact, 'json', dict(refused='%s: %s' % (type(error).__name__, str(error)[:200])), len(compact)
    if best is not None and len(best[0]) < len(compact):
        return best[0].rstrip('\n'), 'stacked', best[1], len(compact)
    return compact, 'json', dict(not_shorter=True, trace=[{k: v for k, v in r.items() if k != 'text'} for r in trace]), len(compact)


def _splittable(value):
    """A map or list that can be written as more than one self-contained block."""
    if not isinstance(value, (dict, list)) or not value:
        return False
    if len(value) >= 2:
        return True
    only = next(iter(value.values())) if isinstance(value, dict) else value[0]
    return _splittable(only)


def _split_blocks(value, path, max_chars, out, layered=None):
    """Self-contained blocks of at most max_chars each (Jev reads material in pieces: every block keeps its own keys,
    columns and dictionary, so no block holds a reference into another). A map splits by key, a list by row ranges,
    one item too large for a block recurses into it; a scalar that alone is larger stays one block (cut by the
    reader's pieces exactly as before). Each block is the shorter of its best proven stacked text and compact JSON."""
    body, encoding, facts, json_chars = _best_body(value, layered)
    if max_chars is None or len(body) <= max_chars or not _splittable(value):
        out.append(dict(path=path, rows=None, encoding=encoding, body=body, facts=facts, json_chars=json_chars))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _split_blocks(item, path + [key], max_chars, out)
        return
    start, size = 0, len(value)
    while start < len(value):
        end = min(len(value), start + max(1, 2 * size))      # the last range's size doubled: no re-spelling from the end
        while True:
            found = _best_body(value[start:end])
            if len(found[0]) <= max_chars or end - start == 1:
                break
            end = start + max(1, (end - start) // 2)
        size = end - start
        if len(found[0]) > max_chars and _splittable(value[start]):
            _split_blocks(value[start], path + [start], max_chars, out)     # one item too large: its own blocks
        else:
            out.append(dict(path=path, rows=[start, end], encoding=found[1], body=found[0], facts=found[2],
                            json_chars=found[3]))
        start = end


def _assemble(blocks):
    """The JSON value the ordered blocks spell (the inverse of _split_blocks); raises on any inconsistency."""
    root = {'v': None}
    def container(path):
        node, key = root, 'v'
        for part in path:
            if node[key] is None:
                node[key] = [] if type(part) is int else {}
            parent = node[key]
            if type(part) is int:
                if not isinstance(parent, list) or part > len(parent):
                    raise ValueError('material block path skips a list position')
                if part == len(parent):
                    parent.append(None)
            elif not isinstance(parent, dict):
                raise ValueError('material block path names a key inside a list')
            elif part not in parent:
                parent[part] = None
            node, key = parent, part
        return node, key
    for block in blocks:
        node, key = container(block['path'])
        if block['rows'] is None:
            if node[key] is not None:
                raise ValueError('material block sets a value twice')
            node[key] = block['value']
        else:
            first, last = block['rows']
            if node[key] is None:
                node[key] = []
            if not isinstance(node[key], list) or len(node[key]) != first or len(block['value']) != last - first:
                raise ValueError('material row block out of order')
            node[key].extend(block['value'])
    return root['v']


def _material_header(label, kind, source_chars, source_sha, blocks, layout):
    return ('[material %s %s: %d block(s) for %d chars of %s%s, sha256 %s; parse-back proven byte-exact]' % (
        json.dumps(str(label)), MATERIAL_ENCODING, blocks, source_chars, kind,
        (' (JSON text, layout %s)' % layout) if layout else '', source_sha))


def _block_header(k, n, path, rows, encoding):
    return '[block %d/%d path=%s rows=%s enc=%s]' % (k, n, json.dumps(path, separators=(',', ':')),
                                                    json.dumps(rows, separators=(',', ':')), encoding)


_BLOCK_LINE = re.compile(r'^\[block (\d+)/(\d+) path=(.*) rows=(\S*) enc=(stacked|json)\]$')
_MATERIAL_LINE = re.compile(r'^\[material (".*") ' + MATERIAL_ENCODING + r': (\d+) block\(s\) for (\d+) chars of (json|text)'
                            r'(?: \(JSON text, layout ([a-z0-9_+]+)\))?, sha256 ([0-9a-f]{64}); parse-back proven byte-exact\]$')


def _material_text(label, kind, source, layout, blocks):
    parts = [_material_header(label, kind, len(source), _sha256(source.encode()), len(blocks), layout)]
    for k, block in enumerate(blocks, 1):
        parts += [_block_header(k, len(blocks), block['path'], block['rows'], block['encoding']), block['body']]
    return '\n'.join(parts) + '\n'


def unstack_material_text(text):
    """The exact source the stacked material text spells: the compact JSON text (keys as given) for kind json, the
    original text for kind text. The reader for every consumer and the proof; raises on a malformed or inconsistent
    text."""
    lines = text.split('\n')
    head = _MATERIAL_LINE.match(lines[0])
    if head is None:
        raise ValueError('material text has no [material ...] line')
    count, kind, layout = int(head.group(2)), head.group(4), head.group(5)
    blocks, current = [], None
    for line in lines[1:]:
        match = _BLOCK_LINE.match(line)
        if match is not None and len(blocks) < count:
            current = dict(k=int(match.group(1)), n=int(match.group(2)), path=json.loads(match.group(3)),
                           rows=json.loads(match.group(4)), encoding=match.group(5), lines=[])
            blocks.append(current)
            continue
        if current is None:
            raise ValueError('material text carries content before its first block line')
        current['lines'].append(line)
    if len(blocks) != count or any(b['k'] != i + 1 or b['n'] != count for i, b in enumerate(blocks)):
        raise ValueError('material blocks are not numbered 1..%d' % count)
    for block in blocks:
        body = '\n'.join(block['lines'])
        block['value'] = _material_tree_text(body) if block['encoding'] == 'stacked' else json.loads(body)
    value = _assemble(blocks)
    if kind == 'text':
        if layout is None:
            raise ValueError('a stacked text material names no JSON layout')
        return _layout_dump(value, layout)
    return _compact(value)


def render_material(value, *, label, legacy_text=None, max_chars=None, keep_texts=False):
    """Every existing lossless stack on one piece of non-picture material, layered and PROVEN (see the section head).

    value: the JSON value the consumer serialized (kind json), or a str the consumer wrote as raw text (kind text: a
    file's text; a text that is exactly a JSON value in a known layout is stacked as that value, any other text stays
    as it is). legacy_text: the exact text the consumer wrote before the stacks (default json.dumps(value,
    sort_keys=True), or the text itself). max_chars: the reader's piece size (Jev): the material is then written as
    self-contained blocks of at most that size; None = one block (Granite reads the whole prompt or refuses it over
    the cap). keep_texts: also return every layer's text (`layer_texts`) so the consumer can count each with the
    server tokenizer; the texts are never retained in a summary.
    Returns {schema, label, encoding: stacked|compact_json|legacy, text, sha256, chars, legacy, source, layers, blocks,
    refused, proof}; `text` is what the prompt carries. A layer that does not prove is never used (its reason in
    `layers`/`refused`); the result is always lossless."""
    import frankie_box_stacked_text as ST  # noqa: F401  (fail here, not mid-render, when the grammar is absent)
    refused = []
    if isinstance(value, str):
        kind, source = 'text', value
        legacy = value if legacy_text is None else legacy_text
        decoded = _json_text(value, minimum=1)
        layout = decoded[1] if decoded is not None else None
        normalized = _material_plain(decoded[2]) if decoded is not None else None
        if decoded is None:
            refused.append('L2: the text is not exactly a JSON value in a known layout; written as it is (no stack applies)')
        compact = None
    else:
        kind, layout = 'json', None
        normalized = json.loads(json.dumps(value, sort_keys=True))     # the consumer's value as its sorted JSON reads back
        source = _compact(normalized)
        legacy = json.dumps(value, sort_keys=True) if legacy_text is None else legacy_text
        compact = source
    source_sha = _sha256(source.encode())
    layers = [dict(layer='L0_legacy', chars=len(legacy), adopted=True, reason='the consumer\'s own text (baseline)')]
    texts = [('L0_legacy', legacy)]
    candidates = [('legacy', legacy)]
    if compact is not None:
        if json.loads(compact) != json.loads(legacy):
            layers.append(dict(layer='L1_compact_json', chars=len(compact), adopted=False,
                               reason='does not read back equal to the legacy JSON; not used'))
        else:
            adopted = len(compact) < len(legacy)
            layers.append(dict(layer='L1_compact_json', chars=len(compact), adopted=adopted,
                               reason=None if adopted else 'not shorter than L0'))
            texts.append(('L1_compact_json', compact))
            if adopted:
                candidates.append(('compact_json', compact))
    blocks = []
    if normalized is not None:
        try:
            # every stacked layer on the whole material as one block: the per-layer record and the texts to count
            layered = _layered(normalized)
            for row in layered[1]:
                if row.get('text') is not None:
                    full = _material_text(label, kind, source, layout,
                                          [dict(path=[], rows=None, encoding='stacked', body=row['text'].rstrip('\n'))])
                    texts.append((row['layer'], full))
                    layers.append(dict({k: v for k, v in row.items() if k != 'text'}, chars=len(full),
                                       scope='whole material as one block, with its header'))
                else:
                    layers.append(dict(row, scope='whole material as one block'))
            _split_blocks(normalized, [], None if max_chars is None else max(256, max_chars - 200), blocks, layered)
            stacked = _material_text(label, kind, source, layout, blocks)
            if unstack_material_text(stacked) != source:
                raise ValueError('the stacked material does not parse back to the exact source')
            candidates.append(('stacked', stacked))
        except (ValueError, RecursionError, KeyError, IndexError, TypeError) as error:
            blocks = []
            refused.append('stacked: refused, not used: %s: %s' % (type(error).__name__, str(error)[:200]))
    encoding, text = min(candidates, key=lambda c: len(c[1]))
    if encoding != 'stacked' and 'stacked' in dict(candidates):
        refused.append('the stacked spelling (%d chars) is not shorter than %s (%d chars); not used' % (
            len(dict(candidates)['stacked']), encoding, len(text)))
    layers.append(dict(layer='delivered', chars=len(text), adopted=True, encoding=encoding,
                       scope=('%d self-contained block(s) of at most %s chars' % (len(blocks), max_chars)
                              if encoding == 'stacked' else 'the consumer\'s text' if encoding == 'legacy' else 'compact JSON')))
    texts.append(('delivered', text))
    facts = [b.get('facts') or {} for b in blocks] if encoding == 'stacked' else []
    result = dict(
        schema=MATERIAL_SCHEMA, label=label, encoding=encoding, text=text, sha256=_sha256(text.encode()), chars=len(text),
        legacy=dict(chars=len(legacy), sha256=_sha256(legacy.encode())),
        source=dict(kind=kind, chars=len(source), sha256=source_sha, layout=layout),
        layers=layers,
        blocks=[dict(path=b['path'], rows=b['rows'], encoding=b['encoding'], chars=len(b['body']), json_chars=b['json_chars'],
                     layers=(b.get('facts') or {}).get('layers')) for b in blocks] if encoding == 'stacked' else [],
        counts=dict(dedup_entries=sum(f.get('dedup_entries') or 0 for f in facts),
                    dedup_refs=sum(f.get('dedup_refs') or 0 for f in facts),
                    contained=sum(f.get('contained') or 0 for f in facts),
                    **{name: sum((f.get('counts') or {}).get(name, 0) for f in facts)
                       for name in ('json_texts', 'tables', 'repeats', 'dictionaries', 'integer_sequences', 'digest_tables',
                                    'digest_refused')}),
        not_applicable=['L1 c15 unpack and L4 tensors: no c15 values or decoder tensors in this material',
                        'L6 cross-cycle ledger and L8 known files: the model holds no earlier cycle and opens no file, so '
                        'the content would leave its view',
                        'L7 ranges: subsumed by the R integer recipes (a consecutive run is a D/E recipe)',
                        'brain dedupe: applied by the consumer across documents (dedupe_documents)'],
        refused=refused,
        proof=dict(parse_back='byte_exact', reader='frankie_box_adviser_market.unstack_material_text',
                   rule='every stacked layer: its text parses back to the exact value before it may be adopted; the delivered '
                        'stacked text: unstack_material_text(text) == the exact source; compact_json: json.loads equal to '
                        'the legacy JSON; legacy: the consumer\'s own text; nothing dropped, rounded or summarized'),
        tokens=dict(measured_here=False, rule='the consuming piece counts every layer text with the server tokenizer '
                                              '(layer_texts) and records the count after each layer'))
    if keep_texts:
        result['layer_texts'] = texts
    return result


def material_summary(render):
    """The render's facts without its texts (for inputs, receipts and reports)."""
    return {k: v for k, v in render.items() if k not in ('text', 'layer_texts')}


def dedupe_documents(documents):
    """The brain dedupe (frankie_box_brain.load, Greg 2026-09-28: identical bytes are read by the model once) across
    whole documents: [(label, value)] -> [(label, value, first_label_or_None, sha256)]; a document whose canonical JSON
    (or text) equals an earlier one's is carried by reference to the first, never repeated, never dropped."""
    seen, out = {}, []
    for label, value in documents:
        digest = _sha256((value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(',', ':'))).encode())
        first = seen.get(digest)
        if first is None:
            seen[digest] = label
        out.append((label, value, first, digest))
    return out


def measure_layers(render, count):
    """The server token count after each layer: count(text) -> int for every layer text of a keep_texts render.
    A failed count is recorded as such (None with its reason), never guessed; returns one row per layer."""
    rows = []
    for layer, text in render.get('layer_texts') or []:
        try:
            tokens, reason = count(text), None
        except Exception as error:  # noqa: BLE001 - a measurement never changes what the prompt carries
            tokens, reason = None, '%s: %s' % (type(error).__name__, str(error)[:200])
        rows.append(dict(layer=layer, chars=len(text), tokens=tokens, **({'reason': reason} if reason else {})))
    return rows


# ------------------------------------------------------------------------------------ the 99 registry entries
# Every layer_id of the pinned 99-layer registry, by its group, with the route by which it reaches (or lawfully
# does not reach) the shared market picture or this piece's own consumer. Roles are not interchangeable numeric
# layers: a control/knowledge/arm entry reaches its own consumer, a sealed answer is withheld by rule, a
# shadow is disabled, an output is produced, never read as input. Route kinds:
#   identity    the entry is the sealed source/day identity the reader is bound to (journal pin, source binding)
#   source      a field of the ROOT's source binding (the opening/predecessor book)
#   input       fields of the ORIGINAL raw record at this instant (picture.original_input)
#   stream      a pinned ROOT/native layer: present when its row at or before this instant carries the named keys
#   clock       a field of picture.at
#   availability  the known_at_ns / availability_basis of every update at this instant
#   completed   a completed-only aggregate without contributor cursors (identity.completed_sources)
#   teacher     a Dipole teacher column; it reaches the teacher seat, not this raw picture
#   bedrock     produced only by the native traversal/projection (bedrock); arrives only through native.member
#   carrier     the one registry's settled carrier (frankie_box_all99_coverage.MARKET_CARRIERS / NATIVE_SERIES): arrives
#               only when an update or last-observed row at or before this instant names THIS entry (update.entries,
#               set by the shared reader per row), never because its layer is present (review 2026-10-07)
#   stamped     the cutoff this context stamps (the lock clock): its adapter cursor
#   model_clock the day's model-evaluation clock records (frankie_box_model_clock.coverage_row)
#   control     a delivered binding control (selected_same_arm_profile), applied by the orchestrator; not market evidence
#   not_read    a registry knowledge entry this piece does not read (its analogue consumer named); arrives only when the
#               consumer reports reading that entry's own content (consumer['registry_content'][entry]) (review B4)
#   consumer    a knowledge/control input read by the consuming piece itself (it reports what it loaded)
#   rule        a wall the piece enforces (answer/outcome walls)
#   retired     Memory A (retired by Greg, 2026-09-27); historical / not_bound
#   not_applicable, withheld, disabled, output, host_clock
ROUTES = {
    # canonical_raw_dbn_mbo (6)
    'canonical_sep_nov_2021_dbn_mbo_objects': ('identity', 'journal'),
    'october_first_source_window': ('identity', 'day'),
    'canonical_predecessor_bootstrap_objects': ('source', ('opening_book', 'tail_members', 'opening_receipt')),
    'native_acmrtfn_messages': ('input', ('action', 'side', 'price', 'size', 'order_id')),
    'snapshot_bootstrap_reset_messages': ('input', ('flags', 'action')),
    'raw_source_identity_provenance_clocks_integrity': ('input', ('ts_recv', 'ts_event', 'sequence', 'publisher_id')),
    # order_lifecycle (9)
    'order_lifecycle_adds': ('stream', 'root.frames', ('activity', 'input_records', 'native_frame')),
    'order_lifecycle_cancels': ('stream', 'root.frames', ('activity', 'input_records', 'native_frame')),
    'order_lifecycle_modifies': ('stream', 'root.frames', ('activity', 'input_records', 'native_frame')),
    'order_lifecycle_replaces': ('stream', 'root.frames', ('activity', 'input_records', 'native_frame')),
    'order_lifecycle_trades': ('stream', 'root.prices', ('price', 'size', 'provenance')),
    'order_lifecycle_fills': ('carrier',),
    'order_lifecycle_clears': ('carrier',),
    'order_identity_transitions': ('carrier',),
    'contract_session_roll_state': ('carrier',),
    # full_book_fifo_queue (8)
    'full_bid_ask_depth': ('stream', 'root.frames', ('book', 'bid_depth_full', 'ask_depth_full')),
    'price_level_and_order_counts': ('stream', 'root.frames', ('book', 'bid_order_count_full', 'bid_price_level_count_full')),
    'fifo_queues': ('stream', 'root.frames', ('book', 'observation')),
    'queue_age_and_survival': ('stream', 'root.frames', ('book', 'observation')),
    'queue_concentration': ('stream', 'root.frames', ('book', 'observation')),
    'orders_and_volume_ahead': ('stream', 'root.frames', ('book', 'observation')),
    'spread_and_depth_imbalance': ('stream', 'root.frames', ('book', 'spread', 'depth_imbalance_n', 'depth_imbalance_full')),
    'complete_state_reset_bootstrap_receipts': ('carrier',),
    # microstructure_mechanics (7)
    'mechanics_actions_by_side_and_level': ('carrier',),
    'aggressor_and_native_signed_flow': ('carrier',),
    'depletion_and_replenishment': ('carrier',),
    'resilience_and_recovery': ('carrier',),
    'churn_and_queue_turnover': ('stream', 'root.frames', ('activity',)),
    'price_and_book_path': ('carrier',),
    'missingness_and_integrity_flags': ('stream', 'root.frames', ('integrity',)),
    # legacy_observable_crosswalk (5)
    'legacy_price': ('stream', 'root.prices', ('price', 'size', 'provenance')),
    'legacy_native_signed_flow': ('completed', 'legacy_native_signed_flow'),
    'legacy_per_second_roll20': ('completed', 'legacy_per_second_roll20'),
    'legacy_book_imbalance': ('stream', 'root.frames', ('book', 'depth_imbalance_n', 'best_bid', 'mid')),
    'legacy_structure_observables': ('stream', 'root.structures', ('action_counts', 'side_counts', 'component_count', 'price_raw_min')),
    # derived_geometry (8)
    'derived_roll20_and_dipole_state': ('teacher', 'the Dipole component states of the teacher rows (roll20 itself stays completed-only)'),
    'derived_d_family_geometry': ('stream', 'root.structures', ('candidate_family_id', 'mirror', 'carried_native_family')),
    'derived_open_world_predecessor_state': ('stream', 'root.structures', ('discovery_status',)),
    'derived_ancestry_gaps': ('carrier',),
    'derived_unresolved_age_chain_trajectory': ('carrier',),
    'derived_price_flow_book_paths': ('carrier',),
    'derived_v4_mechanics_fifo_features': ('carrier',),
    'derived_feature_availability_timestamps': ('availability',),
    # prebirth_opportunity (5)
    'prebirth_predecessor_at_risk_state': ('carrier',),
    'prebirth_unresolved_chain_extension_state': ('carrier',),
    'prebirth_ancestry_successor_opportunity': ('carrier',),
    'prebirth_stopped_chain_false_context_controls': ('carrier',),
    'prebirth_negative_opportunity_cases': ('carrier',),
    # causal_clocks (7)
    'clock_event_time': ('clock', ('ts_event_ns', 'raw_event_clock')),
    'clock_receive_time': ('clock', ('ts_recv_ns', 'raw_receive_clock')),
    'clock_event_known_by': ('availability',),
    'clock_feature_availability': ('availability',),
    'clock_prospective_discovery_confirmation': ('carrier',),
    'clock_model_evaluation': ('model_clock',),
    'clock_lock_time': ('stamped',),
    # binding_common_controls (4)
    'controlling_rt_mission': ('consumer', 'directive'),
    'native_calculation_contract': ('identity', 'policy'),
    'anchored_knowledge_manifest': ('consumer', 'knowledge'),
    'selected_same_arm_profile': ('control',),
    # a_clean_overlay (1), a_memory_overlay (3)
    'a_clean_promoted_positive_capsule': ('not_applicable',),
    'a_memory_promoted_positive_capsule': ('retired',),
    'a_memory_prior_lessons_package': ('retired',),
    'a_memory_prior_package_proof': ('retired',),
    # current_brain_runtime (5)
    'authoritative_s135_construction': ('not_read', 'the Kalshi NG brain construction is not an input of the adviser pieces; its statements reach the scientific tests only through the historical claims crosswalk'),
    'complete_s105_9_brain': ('not_read', 'the Kalshi NG brain is not an input of the adviser pieces; Frankie\'s brain entries (the knowledge index, learner documents) are a different thing'),
    'doctrine_reasoning_play_index_evidence': ('not_read', 'the play index is in the historical catalog; it reaches tests only through the historical claims crosswalk'),
    'lawful_prior_session_carry': ('consumer', 'carry'),
    'october_outcome_wall_enforcement': ('rule', 'walls'),
    # frozen_learned_structure (9)
    'learned_d_structures_and_families': ('not_read', 'registry file not read by the adviser pieces; analogue consumer: the learner knowledge documents / school files the piece loads'),
    'learned_dipoles_and_geometry': ('not_read', 'registry file not read by the adviser pieces; analogue consumer: the learner knowledge documents / school files the piece loads'),
    'learned_pair_triplet_recurrence': ('not_read', 'registry file not read by the adviser pieces; analogue consumer: the learner knowledge documents / school files the piece loads'),
    'learned_chains_extensions_reappearances_ancestry': ('not_read', 'registry file not read by the adviser pieces; analogue consumer: the learner knowledge documents / school files the piece loads'),
    'phase1_discoveries_structural_falsifiers': ('not_read', 'registry file not read by the adviser pieces; analogue consumer: the learner knowledge documents / school files the piece loads'),
    'phase2_findings_modules_timing_pox_negatives': ('not_read', 'registry file not read by the adviser pieces; analogue consumer: the learner knowledge documents / school files the piece loads'),
    'predecessor_ancestry_unresolved_chain_state': ('not_read', 'registry file not read by the adviser pieces; analogue consumer: the learner knowledge documents / school files the piece loads'),
    'historical_timing_lifespan_context': ('not_read', 'registry file not read by the adviser pieces; analogue consumer: the learner knowledge documents / school files the piece loads'),
    'learned_structure_proposal_index_material': ('not_read', 'registry file not read by the adviser pieces; analogue consumer: the learner knowledge documents / school files the piece loads'),
    # corrected_extra_agent_carryforward (1)
    'extra_agent_corrected_information_and_gap_diagnoses': ('not_read', 'registry file not read by the adviser pieces; analogue consumer: the learner knowledge documents / school files the piece loads'),
    # sealed_target_timing (2), sealed_step1_answer (7)
    'later_outcome_reveal': ('withheld',), 'target_ground_truth_onset_time': ('withheld',),
    'step1_existing_october_seconds': ('withheld',), 'step1_populations': ('withheld',), 'step1_crosswalks': ('withheld',),
    'step1_target_membership_receipts': ('withheld',), 'step1_labels_and_classifications': ('withheld',),
    'step1_result_prefixes': ('withheld',), 'step1_reconciliation_outputs': ('withheld',),
    # provisional_shadow (2)
    's137_cognitive_shadow_runtime': ('disabled',), 'hipporag_associative_retrieval': ('disabled',),
    # append_only_outputs (10)
    'output_state_and_state_delta_movie': ('output',), 'output_frankie_reasoning_movie': ('output',),
    'output_probability_movie': ('output',), 'output_candidate_discoveries': ('output',),
    'output_first_locks_and_no_locks': ('output',), 'output_negative_sparse_inconclusive_ledger': ('output',),
    'output_knowledge_retrieval_receipts': ('output',), 'output_provider_invocation_response_receipts': ('output',),
    'output_answer_wall_access_receipts': ('output',), 'output_source_state_manifest_code_model_run_hashes': ('output',),
}
ROLES = ALL99.GROUP_ROLES          # the one registry's group roles (identical to the list this piece carried)


def registry_layers():
    """(rows of {layer_id, group_id, role, historical_delivery_status}, source note) from the one registry
    (frankie_box_all99_coverage): always the 99 embedded identities, bound to the crosswalk sha256, in crosswalk order.
    The crosswalk file of this checkout is checked against them and against CYCLE_CALCULATION_PINS.json; every
    difference is in the note's `integrity` (a separate visible failure, never missing coverage), never relabelled."""
    reg = ALL99.registry(REPO)
    integrity = list(reg['integrity'])
    try:
        pin = (json.loads(CALCULATION_PINS.read_bytes()).get('crosswalk') or {}) if CALCULATION_PINS.is_file() else {}
    except ValueError as error:
        pin = {}
        integrity.append(dict(kind='calculation_pins_unreadable', error=str(error)))
    if pin and (pin.get('sha256') != ALL99.CROSSWALK_SHA256 or pin.get('bytes') != ALL99.CROSSWALK_BYTES):
        integrity.append(dict(kind='calculation_pins_name_another_crosswalk', pinned=pin,
                              registry=dict(sha256=ALL99.CROSSWALK_SHA256, bytes=ALL99.CROSSWALK_BYTES)))
    rows = [dict(layer_id=l['entry'], group_id=l['group'], role=l['role'], historical_delivery_status=l['historical_delivery_status'])
            for l in reg['layers']]
    crosswalk = reg['crosswalk'] or {}
    return rows, dict(source=('pinned crosswalk' if crosswalk and not integrity else
                              'one registry (frankie_box_all99_coverage; embedded identities bound to the crosswalk sha256)'),
                      path=crosswalk.get('path'), sha256=crosswalk.get('sha256'), bytes=crosswalk.get('bytes'),
                      registry_sha256=REGISTRY_SHA256, layers=len(rows), integrity=integrity,
                      entries_from='frankie_box_all99_coverage.REGISTRY')


def _has(value, keys):
    """Which of the named keys (one level, or dotted) the row value carries; a value is never fabricated."""
    found = []
    for key in keys:
        node, ok = value, True
        for part in key.split('.'):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                ok = False
                break
        if ok:
            found.append(key)
    return found


def all_99_coverage(picture, *, reader=None, identity=None, consumer=None):
    """One row per registry entry: how it reaches (or lawfully does not reach) THIS instant's picture or this
    piece's consumer, with an explicit disposition. picture=None means no shared picture reached the piece
    (legacy source): every picture route is then absent, said so. consumer: what the piece itself loaded
    ({'piece', 'brain', 'knowledge', 'directive', 'lessons', 'carry', 'walls'}: a value describing what was
    loaded, or None/absent = not loaded by this piece; 'registry_content': {entry: what of THAT registry entry's own content
    the piece read}, the only way a registry knowledge entry arrives here, review B4; 'model_clock': the day's
    clock_model_evaluation row, or 'run_dir' to read it)."""
    rows, registry = registry_layers()
    identity = identity or (reader.identity if reader is not None else None) or {}
    layers = getattr(reader, 'layers', None) or {}
    source = getattr(reader, 'source', None) or {}
    consumer = consumer or {}
    at = (picture or {}).get('at') or {}
    boundary = at.get('input_cursor')
    observed, carried, tagged = {}, {}, False
    if picture is not None:
        for update in list(picture.get('updates') or []) + list(picture.get('last_observed_state') or []):
            entry = observed.setdefault(update['source'], dict(instruments=set(), at_boundary=0, previously_known=0, keys=set()))
            entry['instruments'].add(update.get('instrument_id'))
            when = 'at_boundary' if update.get('input_cursor') == boundary else 'previously_known'
            entry[when] += 1
            if isinstance(update.get('value'), dict):
                entry['keys'].update(update['value'].keys())
            # the registry entries the shared reader named on this row (frankie_box_market_timeline: update.entries)
            if 'entries' in update:
                tagged = True
                for name in update.get('entries') or ():
                    slot = carried.setdefault(name, dict(at_boundary=0, previously_known=0, sources=set()))
                    slot[when] += 1
                    slot['sources'].add(update['source'])
    raw_record = None
    if picture is not None:
        payload = (picture.get('original_input') or {}).get('payload') or {}
        raw_record = payload.get('record') if isinstance(payload, dict) else None
        if raw_record is None and isinstance(payload, dict):
            # the same extraction the core applies to the ORIGINAL envelope; never a repaired record
            from frankie_box_boss_session import Session
            raw_record = Session._find_observation(payload, max_depth=None)
        if raw_record is not None and hasattr(raw_record, 'materialize'):
            raw_record = raw_record.materialize()
    out = []
    for row in rows:
        route = ROUTES.get(row['layer_id'], ('unmapped',))
        kind = route[0]
        disposition, reason, where = None, None, None
        if picture is None and kind in ('identity', 'source', 'input', 'stream', 'clock', 'availability', 'completed', 'bedrock',
                                        'carrier', 'stamped'):
            disposition, reason = 'absent', 'no shared market picture reached this piece (legacy teacher source without a shared identity)'
        elif kind == 'identity':
            if route[1] == 'journal':
                where = identity.get('journal')
            elif route[1] == 'day':
                where = dict(day=identity.get('day'))
            else:
                where = dict(shared_market_policy=(source.get('shared_market_policy') or {}).get('schema'),
                             native_calculation_policy=source.get('native_calculation_policy'))
            disposition = 'arrived' if where and any(v is not None for v in (where.values() if isinstance(where, dict) else [where])) else 'thin'
            reason = 'bound in the shared reader identity' if disposition == 'arrived' else 'identity field not recorded by this core version'
        elif kind == 'source':
            present = [k for k in route[1] if source.get(k) is not None]
            disposition = 'arrived' if present else 'thin'
            reason = ('source binding carries ' + ', '.join(present) if present else
                      'the ingest opened without a recorded predecessor book (warmed from its own tail or none); the instant stays')
        elif kind == 'input':
            if raw_record is None:
                disposition, reason = 'thin', 'this instant has no readable original record (envelope without readable observation); kept with its disposition'
            else:
                present = _has(raw_record, route[1])
                disposition = 'arrived' if present else 'thin'
                reason = 'original raw record carries ' + ', '.join(present) if present else 'raw record lacks ' + ', '.join(route[1])
        elif kind == 'stream':
            name, keys = route[1], route[2]
            layer = layers.get(name)
            if layer is None:
                disposition, reason = 'thin', 'layer status not reported by this core version'
            elif layer.get('status') == 'absent':
                disposition, reason = 'absent', str(layer.get('reason'))
            elif name not in observed:
                disposition, reason = 'thin', 'layer present in the source; no row observed at or before this instant yet'
            else:
                entry = observed[name]
                present = [k for k in keys if k in entry['keys']]
                where = dict(instruments=len(entry['instruments']), observed_at_this_boundary=entry['at_boundary'],
                             previously_known=entry['previously_known'], keys_present=present)
                if present:
                    disposition = 'arrived'
                    reason = ('row keys ' + ', '.join(present) + ' at this instant'
                              + ('' if entry['at_boundary'] else ' (previously known last-observed values, not a new observation)'))
                else:
                    disposition, reason = 'thin', 'rows of this layer lack ' + ', '.join(keys) + ' (older ROOT projection)'
        elif kind == 'clock':
            present = [k for k in route[1] if type(at.get(k)) is int]
            disposition = 'arrived' if present else 'thin'
            reason = 'picture.at carries ' + ', '.join(present) if present else 'no exact clock at this instant (unplaceable input clock); kept'
        elif kind == 'availability':
            stamped = sum(1 for u in (picture.get('updates') or []) if type(u.get('known_at_ns')) is int)
            disposition = 'arrived' if stamped or type(at.get('publication_frontier_ns')) is int else 'thin'
            reason = ('%d updates carry known_at_ns/availability_basis at this instant; publication_frontier_ns %s; the registry\'s derived '
                      'availability layer itself is a bedrock projection' % (stamped, at.get('publication_frontier_ns')))
        elif kind == 'completed':
            completed = [c for c in identity.get('completed_sources') or [] if c.get('role') == route[1]]
            disposition = 'completed_only' if completed else 'absent'
            reason = ('post-stream aggregate without exact contributor cursors; not a live instant value' if completed
                      else 'no completed ' + route[1] + ' aggregate in this ROOT')
        elif kind == 'bedrock':
            native = layers.get('native.member') or {}
            if native.get('status') == 'present' and 'native.member' in observed:
                disposition, reason = 'arrived_partial', 'native.member frankie_emission at this instant; identity-linked lineage across groups stays a bedrock projection'
            elif native.get('status') == 'present':
                disposition, reason = 'thin', 'native layer present; no member row at or before this instant yet'
            else:
                disposition, reason = 'absent', 'bedrock projection only; ' + str(native.get('reason') or 'native layer absent') + ' (disabled producer not activated silently)'
        elif kind == 'carrier':
            first, thin = ALL99.MARKET_CARRIERS[row['layer_id']]
            hit = carried.get(row['layer_id'])
            if hit:
                # its own carrier, or only the thinner carrier the reader names when the own carrier is absent
                disposition = ('arrived' if first in hit['sources'] or any(x.startswith('external.') for x in hit['sources'])
                               else 'thin')     # a day-file point that declares this entry, presented at/after publication
                where = dict(at_this_boundary=hit['at_boundary'], previously_known=hit['previously_known'],
                             sources=sorted(hit['sources']))
                reason = ('%d row(s) naming this entry at this instant' % hit['at_boundary'] if hit['at_boundary'] else
                          'previously known last-observed row(s) naming this entry, not a new observation')
                if disposition == 'thin':
                    reason += '; carried only by the thinner carrier (%s absent)' % first
            elif not tagged and observed:
                disposition, reason = 'thin', 'the shared reader of this picture names no entries per row (an older core); not established per entry'
            elif (layers.get(first) or {}).get('status') == 'absent':
                if thin is not None and ((thin == 'input' and raw_record is not None)
                                         or (layers.get(thin) or {}).get('status') == 'present'):
                    disposition = 'thin'
                    reason = '%s absent (%s); its thinner carrier %s is in the picture' % (first, layers[first].get('reason'), thin)
                else:
                    disposition, reason = 'absent', '%s absent: %s (a disabled producer is never activated silently)' % (
                        first, layers[first].get('reason'))
            else:
                disposition, reason = 'thin', 'carrier %s present; no row naming this entry at or before this instant' % first
        elif kind == 'model_clock':
            # the day's model-evaluation clock (frankie_box_model_clock.coverage_row; remaining_consumers 2026-10-07): the
            # consumer's own row when it carries one, else read from its run directory; the native member field stays the
            # declared null
            clock = consumer.get('model_clock')
            if not isinstance(clock, dict) and consumer.get('run_dir'):
                clock = ALL99.model_clock_row(consumer['run_dir'], identity.get('day'))
            if isinstance(clock, dict):
                disposition, reason, where = clock.get('disposition'), clock.get('reason'), clock.get('where')
            else:
                disposition, reason = 'not_reported_by_this_piece', ('no model clock row given to this piece (consumer '
                                                                     'model_clock / run_dir); never a zero clock')
        elif kind == 'stamped':
            disposition = 'stamped'
            reason = 'the cutoff this context stamps: adapter cursor %s at receive clock %s' % (at.get('adapter_cursor'), at.get('ts_recv_ns'))
        elif kind == 'control':
            disposition, reason = 'control', ('a delivered binding control (DELIVERED in the crosswalk): the orchestrator\'s plan '
                                              'selects the arm/day; not market evidence and not retired')
        elif kind == 'not_read':
            content = (consumer.get('registry_content') or {}).get(row['layer_id'])
            if content:
                disposition, reason, where = 'arrived_at_consumer', str(consumer.get('piece')) + ' read this entry\'s own content', content
            else:
                disposition, reason = 'not_read_by_this_piece', route[1]
        elif kind == 'teacher':
            disposition, reason = 'teacher_seat', 'Dipole teacher columns (' + route[1] + ') reach the teacher seat/rows, not this raw picture'
        elif kind == 'consumer':
            loaded = consumer.get(route[1])
            if consumer.get('piece') is None:
                disposition, reason = 'consumer_not_reported', 'evaluated by the consuming piece (' + route[1] + ')'
            elif loaded:
                disposition, reason, where = 'arrived_at_consumer', str(consumer.get('piece')) + ' loaded ' + route[1], loaded
            else:
                disposition, reason = 'not_loaded_by_this_piece', str(consumer.get('piece')) + ' did not load ' + route[1] + ' (role input not applicable here or not supplied)'
        elif kind == 'rule':
            walls = consumer.get('walls')
            disposition = 'enforced_by_rule' if walls else 'consumer_not_reported'
            reason, where = 'answer/outcome walls enforced by the piece', walls
        elif kind == 'retired':
            disposition, reason = 'historical_not_bound', 'Memory A / arm profile retired (Greg, 2026-09-27); H06-H08 stay historical'
        elif kind == 'not_applicable':
            disposition, reason = 'not_applicable', 'NOT_APPLICABLE in the pinned crosswalk; not an input of this experiment'
        elif kind == 'withheld':
            disposition, reason = 'withheld_by_rule', 'sealed answer/timing boundary; never a live discovery input'
        elif kind == 'disabled':
            disposition, reason = 'disabled', 'provisional shadow disabled by the existing policy; not activated'
        elif kind == 'output':
            outputs = consumer.get('outputs')
            disposition, reason, where = 'append_only_output', 'produced by stages, never read as an input of this piece', outputs
        elif kind == 'host_clock':
            disposition, reason = 'not_on_experiment_path', 'host/model-evaluation/lock clock; not an experiment picture clock'
        else:
            disposition, reason = 'unmapped', 'no route authored for this layer id; named, not dropped'
        fed = [x for x in (carried.get(row['layer_id']) or {}).get('sources', ()) if x.startswith('external.')]
        if fed and disposition not in ('arrived', 'arrived_at_consumer'):
            # a day-file point declares it feeds this entry and its value is in this picture (presented at or after its
            # publication clock by the shared reader): arrived through that point, the route's own word kept in the reason
            reason = 'day-file point(s) %s in this picture feed this entry; route %s: %s' % (sorted(fed), kind, reason)
            disposition = 'arrived'
        out.append(dict(entry=row['layer_id'], group=row['group_id'], role=row['role'], route=kind,
                        disposition=disposition, reason=reason, **({'where': where} if where is not None else {})))
    counts = {}
    for item in out:
        counts[item['disposition']] = counts.get(item['disposition'], 0) + 1
    return dict(schema=ALL_99_SCHEMA, registry=registry, at=dict(input_cursor=boundary, adapter_cursor=at.get('adapter_cursor'),
                                                                 ts_recv_ns=at.get('ts_recv_ns')),
                consumer=consumer.get('piece'), entries=len(out), counts=counts, rows=out,
                shared_field=_shared_field(out, consumer.get('piece'), identity.get('day')),
                rule='roles are not interchangeable numeric layers; a thin or absent entry keeps the instant with its disposition; '
                     'a listed arrival is not proof that a consumer computed on it (' + MISSING_COVERAGE_RULE + ')')


def _shared_field(rows, piece, day):
    """The shared per-piece field FRANKIE_ALL99_COVERAGE_V1 from this block's rows (names, routes and dispositions
    unchanged), built and validated by the one registry module."""
    reaching = ('arrived', 'arrived_partial', 'completed_only', 'arrived_at_consumer', 'enforced_by_rule')
    return ALL99.field('adviser:' + str(piece or 'picture'), day,
                       [dict(entry=r['entry'], group=r['group'], disposition=r['disposition'], reason=r.get('reason'),
                             consumer=(None if r['disposition'] not in reaching else
                                       str(piece) if piece else 'the adviser market picture at this cutoff'),
                             route=r.get('route')) for r in rows],
                       code_root=REPO, stage='adviser_market',
                       basis='one complete picture at the existing original source cutoff and the consuming piece\'s own loads')


def all_99_with_consumer(coverage, consumer):
    """The piece's own consumer rows overlaid on a context's picture-derived rows."""
    if coverage is None:
        return all_99_coverage(None, consumer=consumer)
    out = copy.deepcopy(coverage)
    consumer = consumer or {}
    counts = {}
    for row in out['rows']:
        kind = row['route']
        if kind in ('consumer', 'rule', 'output'):
            key = ROUTES.get(row['entry'], (None, None))[1] if kind == 'consumer' else ('walls' if kind == 'rule' else 'outputs')
            loaded = consumer.get(key)
            if kind == 'consumer':
                row['disposition'] = 'arrived_at_consumer' if loaded else 'not_loaded_by_this_piece'
                row['reason'] = str(consumer.get('piece')) + (' loaded ' if loaded else ' did not load ') + str(key)
            elif kind == 'rule':
                row['disposition'] = 'enforced_by_rule' if loaded else 'not_reported_by_this_piece'
            row['where'] = loaded
        elif kind == 'model_clock':
            clock = consumer.get('model_clock')
            if not isinstance(clock, dict) and consumer.get('run_dir'):
                clock = ALL99.model_clock_row(consumer['run_dir'], (out.get('shared_field') or {}).get('day'))
            if isinstance(clock, dict):
                row.update(disposition=clock.get('disposition'), reason=clock.get('reason'), where=clock.get('where'))
        elif kind == 'not_read':
            # review B4: a truthy brain/knowledge load never makes a registry knowledge entry arrive; only the consumer's
            # report that it read THIS entry's own content does
            content = (consumer.get('registry_content') or {}).get(row['entry'])
            row['disposition'] = 'arrived_at_consumer' if content else 'not_read_by_this_piece'
            row['reason'] = (str(consumer.get('piece')) + ' read this entry\'s own content' if content
                             else ROUTES[row['entry']][1])
            if content:
                row['where'] = content
            else:
                row.pop('where', None)
        counts[row['disposition']] = counts.get(row['disposition'], 0) + 1
    out.update(consumer=consumer.get('piece'), counts=counts,
               shared_field=_shared_field(out['rows'], consumer.get('piece'), (out.get('shared_field') or {}).get('day')))
    return out


# ------------------------------------------------------------------------------------ the context
# ---- CPU placement for the input assembly (Greg, 2026-10-07: every process, pool and thread pinned to its share of
# the booked lane, physical-core aware, nothing floating or idle). Placement only: no value, order or byte of any
# picture, count or prompt depends on it; it is recorded for the one-day inspection and never enters an identity.
def lane_cpus():
    """The held lane's CPUs this process may use: FRANKIE_LANE_CPUS / FRANKIE_BOOKED_CPUS intersected with the affinity
    (the shared reader's own rule, frankie_box_market_timeline.lane_cpus, imported, never re-implemented)."""
    from frankie_box_market_timeline import lane_cpus as timeline_lane
    return timeline_lane()


def core_order(cpus):
    """(cpus ordered first thread of every physical core, then the second threads; {cpu: its sibling cpus in the list};
    basis): the order is frankie_box_lane_pin.core_order (the one lane pin helper, imported), the siblings come from
    frankie_box_boss_session.cpu_topology / core_groups (imported). Unreadable topology keeps the plain sorted order
    and says so."""
    cpus = sorted(cpus)
    try:
        import frankie_box_lane_pin as LP
        ordered, basis = LP.core_order(cpus)
        topology = LP._session().cpu_topology(cpus)
        groups = LP._session().core_groups(cpus, topology) if topology is not None else []
    except Exception as error:  # noqa: BLE001 - placement falls back to the plain order, recorded
        return cpus, {}, 'plain sorted order (lane pin helpers unavailable: %s)' % type(error).__name__
    return ordered, {cpu: [c for c in g if c != cpu] for g in groups for cpu in g}, basis


def reader_plan(cpus=None):
    """The shared-reader placement on the lane: the ordered picture consumer (this process's main thread) on a WHOLE
    physical core (its sibling thread left out of the reader set), the reader's decode workers on every other lane CPU.
    One CPU (Jev's claimed adviser slot): one reader worker, no pool oversubscribing the slot. Returns a dict with
    consumer, idle, reader_set (the affinity the reader is constructed and spawned under) and workers."""
    lane = sorted(lane_cpus() if cpus is None else cpus)
    if len(lane) <= 2:
        return dict(lane=lane, consumer=lane[0] if lane else None, idle=[], reader_set=lane, workers=1,
                    basis='%d lane CPU(s): one reader worker; the slot is not oversubscribed' % len(lane))
    _, siblings, basis = core_order(lane)
    consumer = lane[0]
    idle = [cpu for cpu in siblings.get(consumer, []) if cpu in lane]
    reader_set = [cpu for cpu in lane if cpu not in idle]
    return dict(lane=lane, consumer=consumer, idle=idle, reader_set=reader_set, workers=max(1, len(reader_set) - 1),
                basis='consumer on a whole physical core (sibling %s idle); %d reader workers on the other lane CPUs; %s'
                      % (idle or 'none', max(1, len(reader_set) - 1), basis))


def _set_affinity(cpus, record, what):
    """sched_setaffinity of the calling thread; a refusal keeps the inherited affinity and is recorded (L-2)."""
    import os
    try:
        os.sched_setaffinity(0, set(cpus))
        return True
    except (OSError, ValueError) as error:
        record.setdefault('affinity_fallbacks', []).append(dict(what=what, cpus=sorted(cpus), error=repr(error)))
        return False


_POOL_SHARED = None     # the fork-inherited read-only input of a PinnedMap pool (never pickled per task)


def _pool_task(function, index, argument):
    try:
        return index, True, function(_POOL_SHARED, argument)
    except BaseException as error:  # noqa: BLE001 - the parent recomputes in-process so the same error raises in order
        return index, False, repr(error)


class PinnedMap:
    """function(shared, argument) over arguments on an ordered pinned pool; results() returns them IN ORDER.

    The pool starts (forks) in the constructor, so a caller can start it, do other work (the shared read), then collect.
    Fork, so `shared` is inherited and never pickled per task; workers pinned one per given CPU in physical-core order
    by frankie_box_lane_pin.pinned_pool (respawn-safe, lane fallback). Used only when this process is single-threaded at
    the fork (fork safety), with two or more CPUs and two or more arguments; otherwise nothing starts and the caller
    computes in-process, in order. A worker value is returned as (True, value); anything else as (False, reason), and
    the caller computes that argument in-process at its own turn, so the same value or the same exception arises
    exactly where the serial loop raised it. Greg's rule (2026-10-07): a dead pool worker never stops or hangs the
    piece: the death is seen at the next poll (frankie_box_lane_pin.check_alive), the pool is ended and every task not
    yet collected (the lost one included) is redone on a fresh pool with one worker fewer (in-process below two). A
    result not back within `timeout` from a live pool (a hung worker) ends the pool; that task and every later one run
    in-process. `function` must be a module-level function, deterministic in (shared, argument)."""

    POLL_SECONDS = 15.0

    def __init__(self, function, shared, arguments, *, label, cpus=None, timeout=PINNED_TASK_SECONDS):
        import frankie_box_lane_pin as LP
        self.function, self.shared, self.arguments, self.timeout = function, shared, list(arguments), timeout
        self.pool, self.pending = None, {}
        self.cpus = sorted(LP.lane_cpus() if cpus is None else cpus)
        self.record = dict(label=label, tasks=len(self.arguments), lane=self.cpus, mode='in_process', workers=1,
                           cpus=None, timeout_seconds=timeout, poll_seconds=self.POLL_SECONDS, fallbacks=[], restarts=[],
                           rule='placement only: values, order and errors are the in-process ones (results in argument '
                                'order; a failed, lost or late worker result is recomputed)')
        self._start(range(len(self.arguments)), min(len(self.cpus), len(self.arguments)))

    def _start(self, indexes, workers):
        global _POOL_SHARED
        import multiprocessing
        import threading
        import frankie_box_lane_pin as LP
        indexes = list(indexes)
        why = ('one CPU' if workers < 2 or len(self.cpus) < 2 else 'fewer than two tasks' if len(indexes) < 2 else
               'this process runs other threads (fork unsafe)' if threading.active_count() > 1 else None)
        if why is not None:
            self.record.update(mode='in_process', workers=1, cpus=None, reason=why)
            return False
        _POOL_SHARED = self.shared          # kept until close(): a worker the pool respawns forks with the same input
        try:
            self.pool = LP.pinned_pool(multiprocessing.get_context('fork'), workers, cpus=self.cpus)
            self.pending = {i: self.pool.apply_async(_pool_task, (self.function, i, self.arguments[i])) for i in indexes}
            self.record.update(mode='pinned_fork_pool', workers=workers,
                               cpus=LP.record(workers, self.cpus, self.record['label'])['worker_cpus'])
            return True
        except (OSError, ValueError) as error:
            self.record.update(mode='in_process', workers=1, cpus=None, reason='pool could not start: %r' % error)
            self.close()
            return False

    def results(self):
        out = [(False, 'in_process')] * len(self.arguments)
        try:
            i = 0
            while i < len(self.arguments):
                job = self.pending.get(i)
                if job is None:
                    i += 1
                    continue
                outcome = self._wait(i, job)
                if outcome[0] == 'restarted':
                    continue                      # the same task on the fresh pool (or in-process)
                if outcome[0] == 'value':
                    out[i] = outcome[1]
                i += 1
        finally:
            self.close()
        return out

    def _wait(self, i, job):
        import multiprocessing
        import frankie_box_lane_pin as LP
        waited = 0.0
        while True:
            try:
                _, ok, value = job.get(timeout=self.POLL_SECONDS)
            except multiprocessing.TimeoutError:
                waited += self.POLL_SECONDS
                try:
                    LP.check_alive(self.pool)
                except RuntimeError as died:
                    left = [j for j in sorted(self.pending) if j >= i]
                    workers = self.record['workers'] - 1
                    self.record['restarts'].append(dict(at_task=i, tasks_redone=len(left), workers=workers,
                                                        reason=str(died)[:300]))
                    self.close()
                    self.pending = {}
                    self._start(left, workers)    # one worker fewer; in-process below two
                    return ('restarted',)
                if waited >= self.timeout:
                    self.record['fallbacks'].append(dict(task=i, reason='no result within %s s from a live pool; pool '
                                                                        'ended, task %d and later run in-process'
                                                                        % (self.timeout, i)))
                    self.close()
                    self.pending = {}
                    return ('in_process',)
                continue
            except Exception as error:  # noqa: BLE001 - an unpicklable result or a broken pool: in-process at its turn
                self.record['fallbacks'].append(dict(task=i, reason=repr(error)[:300]))
                return ('in_process',)
            if not ok:
                self.record['fallbacks'].append(dict(task=i, reason='worker raised %s; recomputed in-process' % value[:300]))
            return ('value', (ok, value))

    def close(self):
        global _POOL_SHARED
        if self.pool is not None:
            self.pool.terminate()
            self.pool.join()
            self.pool = None
        _POOL_SHARED = None


class AdviserMarketContext:
    def __init__(self, identity, *, day, source_hash, as_of, through_cursor):
        from frankie_box_durable import witness
        from frankie_box_market_timeline import SharedMarketTimeline, _json
        if type(as_of) is not int or type(through_cursor) is not int or through_cursor < 0:
            raise ValueError('adviser cutoff requires the original explicit integer as_of and through_cursor')
        self.root = Path(identity['calculations']['path']).parent
        self.day = str(day)
        # Reader workers from the lane (research item 5, 2026-10-07): every lane CPU but the consumer's whole core on a
        # day lane (30 on a 32-CPU booking), 1 on Jev's one claimed CPU (15 decode processes time-sharing one CPU were
        # pure overhead). The reader's own contract: same rows, same order, same ordinals, same errors for any count.
        self.plan = reader_plan()
        self.placement = dict(reader=dict(self.plan, former_fixed_workers=WORKERS))
        self.reader = SharedMarketTimeline(self.root, day=self.day, workers=self.plan['workers'])
        if self.reader.identity != identity:
            raise ValueError('adviser source differs from the shared market reader identity')
        ingestion = _json(self.reader.source['ingestion_receipt'])
        if ingestion['source_prefix_hash'] != source_hash:
            raise ValueError('adviser cutoff names another sealed source')
        record_count = ingestion['record_count']
        if type(record_count) is not int or not through_cursor < record_count:
            raise ValueError('adviser cutoff lies outside the sealed source record count')
        # Every pinned layer is checked whole before the read, so a read that stops exactly at
        # the cutoff loses no byte integrity. Row identities and clocks are checked by the core on
        # every consumed row. A mismatch here is corruption, never thin coverage.
        pinned = dict(identity['sources'])
        if (identity.get('external') or {}).get('status') == 'attached':
            pinned['external'] = identity['external']
        # The whole-file checks run concurrently on pinned threads (research item 2a; hashlib and file reads release the
        # GIL), largest file first; the verdicts are then taken IN THE PIN ORDER, so the first mismatch or read error
        # raised is the one the serial loop raised. Every byte of every pin is still hashed (skipping a re-hash on an
        # unchanged stat is Greg's open call, not done here).
        seen = self._witness_all(pinned, witness)
        for name, pin in pinned.items():
            ok, value = seen[name]
            if not ok:
                raise value
            if value != {k: pin[k] for k in ('bytes', 'sha256')}:
                raise ValueError('pinned shared layer bytes differ from their source pin: ' + name)
        self.pins_verified = sorted(['journal', *pinned])
        self.scope = dict(day=self.day, source_hash=source_hash, as_of=as_of, through_cursor=through_cursor,
                          record_count=record_count,
                          position=('last_sealed_input' if through_cursor == record_count - 1
                                    else 'before_sealed_source_end'),
                          origin='the measurement\'s own explicit source scope; no target-derived selection')

    def _witness_all(self, pinned, witness):
        """{name: (True, witness) | (False, exception)} for every pin, hashed on threads pinned one per lane CPU in
        physical-core order (two threads on a one-CPU slot, so a disk wait overlaps a hash)."""
        import os
        import queue
        import threading
        from time import perf_counter
        ordered, _, basis = core_order(lane_cpus())
        names = sorted(pinned, key=lambda n: -int(pinned[n].get('bytes') or 0))
        threads = max(1, min(len(names), max(2, len(ordered))))
        record = dict(threads=threads, cpus=[ordered[i % len(ordered)] for i in range(threads)] if ordered else None,
                      placement_basis=basis, files=len(names), bytes=sum(int(pinned[n].get('bytes') or 0) for n in names),
                      order='largest first; verdicts taken in the pin order')
        work, seen = queue.Queue(), {}
        for name in names:
            work.put(name)

        def run(cpu):
            if cpu is not None:
                try:
                    os.sched_setaffinity(threading.get_native_id(), {cpu})
                except (OSError, ValueError) as error:
                    record.setdefault('affinity_fallbacks', []).append(dict(cpu=cpu, error=repr(error)))
            while True:
                try:
                    name = work.get_nowait()
                except queue.Empty:
                    return
                try:
                    seen[name] = (True, witness(pinned[name]['path']))
                except BaseException as error:  # noqa: BLE001 - raised in pin order by the caller
                    seen[name] = (False, error)
        started = perf_counter()
        pool = [threading.Thread(target=run, args=(record['cpus'][i] if record['cpus'] else None,),
                                 name='adviser-pin-sha256-%d' % i, daemon=True) for i in range(threads)]
        for thread in pool:
            thread.start()
        for thread in pool:
            thread.join()
        record['seconds'] = round(perf_counter() - started, 3)
        self.placement['pin_hashing'] = record
        for name in names:
            seen.setdefault(name, (False, RuntimeError('pin %s was not hashed' % name)))
        return seen

    def _coverage(self, picture):
        """What is present and what is thin at this instant, from the picture alone; nothing invented."""
        at = picture['at']
        boundary = at['input_cursor']
        last_observed = {}
        for update in picture['last_observed_state']:
            age = ('observed_at_this_boundary' if update.get('input_cursor') == boundary
                   else 'previously_known_last_observed_value')
            last_observed.setdefault(update['source'], []).append(dict(
                instrument_id=update.get('instrument_id'), input_cursor=update.get('input_cursor'),
                known_at_ns=update.get('known_at_ns'), age=age))
        updates = {}
        for update in picture['updates']:
            updates[update['source']] = updates.get(update['source'], 0) + 1
        clock, frontier, as_of = at['ts_recv_ns'], at['publication_frontier_ns'], self.scope['as_of']
        clocks = dict(
            receive_clock='exact' if type(clock) is int else 'no_exact_receive_clock_at_cutoff_input',
            raw_receive_clock_present=at.get('raw_receive_clock') is not None,
            receive_clock_vs_declared_as_of=(None if type(clock) is not int else
                                             'at_or_before' if clock <= as_of else 'after_declared_row_as_of'),
            publication_frontier=('exact' if type(frontier) is int else 'no_exact_receive_clock_observed_yet'),
            publication_frontier_vs_declared_as_of=(None if type(frontier) is not int else
                                                    'at_or_before' if frontier <= as_of else 'after_declared_row_as_of'),
            basis='through_cursor is the binding scope; as_of is the measurement\'s declared last row clock and is '
                  'carried, not used to move the cutoff')
        layers = getattr(self.reader, 'layers', None)
        return dict(rule=MISSING_COVERAGE_RULE, source_status=picture['source_status'],
                    unpaired_outcomes=picture['unpaired_outcomes'],
                    original_applied_present=picture['original_applied'] is not None,
                    core_instant_coverage=picture.get('coverage', 'not reported by this core version'),
                    layers_known_to_reader=(layers if layers is not None else 'not reported by this core version'),
                    absent_layers=getattr(self.reader, 'absent_layers', 'not reported by this core version'),
                    updates_at_boundary=updates, last_observed=last_observed,
                    active_instrument_sources=sorted({u['source'] for u in picture['active_instrument_state']}),
                    invalidated_state=copy.deepcopy(picture['invalidated_state']),
                    published_rows=len(picture['published_state']), clocks=clocks,
                    interpretation='a missing or stale part makes this instant thinner, never absent; a previously known '
                                   'value is named as such and is not a new observation; a failed or unpaired outcome is '
                                   'carried as its original disposition, not a measurement')

    def read(self, *, check_save=lambda: None):
        from frankie_box_classroom_code import _exact_market_text
        wanted = self.scope['through_cursor']
        exhaust = self.scope['position'] == 'last_sealed_input'
        selected, matched, cursorless = None, 0, 0
        # The thinner tail (core request, 2026-10-07): the last instant at or before the
        # cutoff that carries an original APPLIED operand, and every instant after it.
        last_applied, tail_after = None, {}
        # Placement (research item 4, 2026-10-07): the reader's pools are spawned from this thread under the reader set
        # (the lane without the consumer core's sibling), so its workers take every other lane CPU; once the first exact
        # instant has started every stream (each stream is advanced at every exact input), this thread, the ordered
        # consumer, is pinned to its whole physical core. Restored at the end. Placement only; a refusal is recorded.
        import os
        plan = self.plan
        consumer = dict(plan=dict(consumer=plan['consumer'], idle=plan['idle'], reader_set=plan['reader_set'],
                                  workers=plan['workers']), pinned_at_picture=None)
        self.placement['consumer'] = consumer
        before = sorted(os.sched_getaffinity(0))
        narrowed = len(plan['reader_set']) > 1 and _set_affinity(plan['reader_set'], consumer, 'reader set')
        pinned_consumer = len(plan['reader_set']) <= 1
        presented = 0
        stream = self.reader.iter_pictures()
        try:
            for item in stream:
                check_save()
                picture = item['picture']
                presented += 1
                if not pinned_consumer:
                    at = picture['at']
                    if all(type(at.get(k)) is int for k in ('input_cursor', 'instrument_id', 'ts_recv_ns')):
                        pinned_consumer = True
                        if _set_affinity([plan['consumer']], consumer, 'consumer core'):
                            consumer['pinned_at_picture'] = presented
                cursor = picture['at']['adapter_cursor']
                if type(cursor) is not int:
                    cursorless += 1
                    continue
                if cursor > wanted and selected is None:
                    raise ValueError('sealed source has no INPUT at the adviser cutoff adapter cursor %d '
                                     '(%d INPUT envelopes without an adapter cursor seen)' % (wanted, cursorless))
                if cursor <= wanted:
                    if picture['original_applied'] is not None:
                        last_applied = dict(at=copy.deepcopy(picture['at']), source_status=picture['source_status'])
                        tail_after = {}
                    else:
                        status = picture['source_status']
                        tail_after[status] = tail_after.get(status, 0) + 1
                if cursor == wanted:
                    matched += 1
                    if matched > 1:
                        raise ValueError('adviser cutoff adapter cursor %d names more than one original INPUT' % wanted)
                    # Any disposition is kept: applied, failed, unpaired or unknown. The
                    # instant is the teacher's own scope boundary and is never rejected.
                    selected = copy.deepcopy(picture)
                    if not exhaust:
                        break      # nothing after the cutoff is decoded or retained
        finally:
            stream.close()
            if narrowed or consumer['pinned_at_picture'] is not None:
                _set_affinity(before, consumer, 'restore')
        if selected is None:
            raise ValueError('sealed source ended before the adviser cutoff adapter cursor %d' % wanted)
        tail = dict(cutoff_input_has_applied_operand=selected['original_applied'] is not None,
                    last_applied_at_or_before_cutoff=last_applied,
                    inputs_after_last_applied_through_cutoff=tail_after,
                    basis='the cutoff instant is the picture; its last-observed states come from earlier exact '
                          'boundaries; an absent APPLIED operand at or after the last applied instant blocks only '
                          'the arithmetic that needs it, never this instant or its unrelated evidence')
        report = copy.deepcopy(self.reader.report)
        read = dict(stopped='source_exhausted' if exhaust else 'at_cutoff_input',
                    source_exhausted=bool(exhaust and report.get('complete') is True),
                    core_report_complete=report.get('complete'),
                    pins_verified=self.pins_verified,
                    pins_basis='whole-file bytes/sha256 before the read; row identity/clock checks on every consumed row',
                    inputs_presented_through_cutoff=report.get('presented_inputs'),
                    inputs_without_adapter_cursor_seen=cursorless,
                    after_cutoff=('the cutoff is the last sealed INPUT; the journal was exhausted for the sealed-count '
                                  'check and no later picture exists' if exhaust else
                                  'no picture after the cutoff was decoded or retained; report dispositions cover the '
                                  'source through the cutoff only'),
                    rule=MISSING_COVERAGE_RULE,
                    not_implied='all-layer coverage or any consumer arithmetic; see coverage')
        text = _exact_market_text(selected)
        return dict(schema=SCHEMA, identity=self.reader.identity, scope=self.scope,
                    at=copy.deepcopy(selected['at']), picture_text=text, picture_sha256=_sha256(text.encode()),
                    picture_render=render_stacks(text),
                    all_99=all_99_coverage(selected, reader=self.reader),
                    coverage=dict(self._coverage(selected), tail=tail), read=read, report=report,
                    reader=dict(module='frankie_box_market_timeline', interface='SharedMarketTimeline.iter_pictures',
                                calculations=str(self.root), day=self.day, identity=self.reader.identity),
                    use=USE, limit=LIMIT)

    def iter_pictures(self):
        """Full exact owner-local history; never silently replace it with the cutoff snapshot."""
        from frankie_box_market_timeline import SharedMarketTimeline
        reader = SharedMarketTimeline(self.root, day=self.day, workers=self.plan['workers'])
        if reader.identity != self.reader.identity:
            raise ValueError('adviser full history changed from its original selected source')
        yield from reader.iter_pictures()


def check(context):
    """The context is whole and self-consistent; an integrity question, not a coverage one."""
    if (not isinstance(context, dict) or context.get('schema') != SCHEMA
            or not isinstance(context.get('picture_text'), str)
            or _sha256(context['picture_text'].encode()) != context.get('picture_sha256')
            or not isinstance(context.get('read'), dict) or not context['read'].get('pins_verified')
            or not isinstance(context.get('coverage'), dict)
            or any(type(context.get('scope', {}).get(k)) is not int for k in ('as_of', 'through_cursor', 'record_count'))):
        raise ValueError('adviser market context differs from its retained complete picture')
    render = context.get('picture_render')
    if render is not None and (render.get('schema') != RENDER_SCHEMA or not isinstance(render.get('text'), str)
                               or _sha256(render['text'].encode()) != render.get('sha256')
                               or render.get('source_sha256') != context['picture_sha256']):
        raise ValueError('adviser picture render differs from its retained exact picture')
    return context


def retain_context(path, context):
    """Durable owner-local copy; existing other bytes are a contradiction, never overwritten."""
    from frankie_box_durable import witness, write_bytes
    check(context)
    path, data = Path(path), _canonical(context)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('retained adviser market context differs; explicit owner recovery required: ' + str(path))
    else:
        write_bytes(path, data)
    return dict(path=str(path), **witness(path))


def load_context(path, *, identity, scope):
    """Reuse a retained context only for the identical source identity and explicit scope."""
    context = check(json.loads(Path(path).read_bytes()))
    if context['identity'] != identity or context['scope'] != scope:
        raise ValueError('retained adviser market context belongs to another source or original cutoff')
    return context


def from_teacher(rows_path, day, measure, *, retain=None, check_save=lambda: None, placement=None):
    """(context, None) from the teacher's own explicit source/as-of/cursor, never its answers;
    (None, why) when the teacher source carries no shared identity or its rows were not readable.
    placement: an optional dict the caller owns; the reader's CPU placement (lane plan, pin hashing, consumer core) and
    whether the context was read or reused are put there for the receipt, never into the context."""
    receipt_path = Path(rows_path).parent / 'receipt.json'
    if not receipt_path.is_file():
        return None, 'no teacher receipt beside the Dipole rows; no shared market scope to bind'
    receipt = json.loads(receipt_path.read_bytes())
    identity = receipt.get('shared_market_identity')
    if identity is None:
        return None, 'teacher receipt carries no shared market identity (legacy source; its actual scope is unchanged)'
    if measure is None:
        return None, 'shared teacher rows were not readable, so their explicit source scope cannot bind a cutoff'
    if (str(receipt.get('day')) != str(day)
            or receipt.get('rows_file', {}).get('sha256') != measure['sha256']
            or any(receipt.get(k) != measure[k] for k in ('as_of', 'through_cursor'))):
        raise ValueError('shared exchange context requires its exact teacher source')
    ingestion_pin = receipt['ingestion_receipt']
    raw = Path(ingestion_pin['path']).read_bytes()
    if _sha256(raw) != ingestion_pin['sha256']:
        raise ValueError('shared teacher ingestion receipt changed')
    reader = AdviserMarketContext(identity, day=day, source_hash=json.loads(raw)['source_prefix_hash'],
                                  as_of=measure['as_of'], through_cursor=measure['through_cursor'])
    if placement is not None:
        placement.update(reader.placement)
    if retain is not None and Path(retain).is_file():
        if placement is not None:
            placement['context'] = 'reused the retained read of the same source and cutoff: %s' % retain
        return load_context(retain, identity=reader.reader.identity, scope=reader.scope), None
    context = reader.read(check_save=check_save)
    if retain is not None:
        retain_context(retain, context)
    if placement is not None:
        placement.update(reader.placement, context='read by this piece from the owner-local shared reader')
    return context, None


def render_summary(context):
    """The render's facts without its text (for references and reports)."""
    render = (context or {}).get('picture_render')
    if render is None:
        return dict(present=False, reason='legacy context without a proven render; the exact typed text is what prompts read')
    return dict(present=True, grammar=render['grammar'], sha256=render['sha256'], chars=render['chars'],
                source_chars=render['source_chars'], layers=render['layers'], proof=render['proof'], tokens=render['tokens'])


def all_99_summary(context):
    coverage = (context or {}).get('all_99')
    if coverage is None:
        return dict(present=False, reason='context carries no all-99 coverage (older context); the consuming piece lists it from the picture')
    return dict(present=True, registry=coverage['registry'], entries=coverage['entries'], counts=coverage['counts'])


def reference(context):
    """Bounded exact reference to a context: identity, scope, clocks, hash and dispositions, no picture body.
    For records and coordination prompts that must not carry the evidence itself."""
    check(context)
    coverage = context['coverage']
    return dict(schema=REFERENCE_SCHEMA, day=context['scope']['day'], scope=context['scope'], at=context['at'],
                picture_sha256=context['picture_sha256'], picture_chars=len(context['picture_text']),
                render=render_summary(context), all_99=all_99_summary(context),
                journal=context['identity'].get('journal'), read=context['read'],
                coverage=dict(source_status=coverage['source_status'], unpaired_outcomes=coverage['unpaired_outcomes'],
                              absent_layers=coverage['absent_layers'], updates_at_boundary=coverage['updates_at_boundary'],
                              last_observed={name: [dict(input_cursor=v['input_cursor'], age=v['age']) for v in values]
                                             for name, values in coverage['last_observed'].items()},
                              published_rows=coverage['published_rows'], clocks=coverage['clocks'],
                              tail=coverage.get('tail')),
                use=context['use'], limit=context['limit'],
                rule='reference only: the complete typed picture is the retained context named by picture_sha256')


def workflow_report(piece, *, context, inputs, use, outputs, consumer=None):
    """One piece's inputs / use / outputs record for the one-day operator review (Greg, 2026-10-07).

    Recorded facts only: which picture values reached which prompt or record, what a role or
    the privacy wall withheld, every missing/stale/unavailable disposition, every cap that
    refused, model calls made or refused, waits; and the per-day all-99 coverage list (every
    registry entry, its role, arrived/absent/disabled/thin, the reason) with this piece's own
    consumer rows. Temporary operator review, not knowledge. `context` may be None (legacy
    source without a shared context) or a context/reference. Nothing here keys on the number
    of days a run holds."""
    picture = None
    if isinstance(context, dict) and context.get('schema') == SCHEMA:
        picture = reference(context)
    elif isinstance(context, dict) and context.get('schema') == REFERENCE_SCHEMA:
        picture = context
    consumer = dict(consumer or {}, piece=piece)
    if isinstance(context, dict) and context.get('schema') == REFERENCE_SCHEMA:
        all_99 = dict(schema=ALL_99_SCHEMA, present=False, consumer=piece,
                      reason='reference-only context: the per-entry rows are on the retained full context named by '
                             'picture_sha256; counts repeated here',
                      counts=(context.get('all_99') or {}).get('counts'))
    else:
        coverage = context.get('all_99') if isinstance(context, dict) and context.get('schema') == SCHEMA else None
        all_99 = all_99_with_consumer(coverage, consumer)
    return dict(schema=WORKFLOW_REPORT_SCHEMA, piece=piece,
                inputs=dict(inputs, shared_market_picture=picture,
                            shared_market_dispositions=(None if picture is None else
                                                        dict(coverage=picture['coverage'], read=picture['read'])),
                            shared_market_render=(None if picture is None else picture.get('render'))),
                use=dict(use, all_99_coverage=all_99),
                outputs=outputs,
                rule='recorded inputs, use and outputs of this piece for the one-day review; '
                     'reaching a prompt or record is not proof of consumption or learning; '
                     'missing evidence means unknown, never zero; the all-99 list names every registry entry '
                     'with its disposition at this instant, roles kept apart')


def text(context):
    """The prompt text: scope, read, coverage and the picture spelled through the proven stacks (re-proven here);
    a context without a render carries the exact typed text and says so."""
    check(context)
    render = verify_render(context)
    all_99 = context.get('all_99')
    head = ('Shared market picture at the original explicit source cutoff (%s). ' % context['scope']['position']
            + context['use'] + '. ' + context['limit'] + '\n'
            + 'SCOPE: ' + json.dumps(context['scope'], sort_keys=True) + '\n'
            + 'READ: ' + json.dumps(context['read'], sort_keys=True) + '\n'
            + 'COVERAGE AT THIS INSTANT (explicit missing/stale/previously-known dispositions; nothing invented): '
            + json.dumps(context['coverage'], sort_keys=True, default=str) + '\n'
            + ('ALL-99 REGISTRY ENTRIES AT THIS INSTANT (counts by disposition; the full list is on the receipt): '
               + json.dumps(all_99['counts'], sort_keys=True) + '\n' if all_99 else
               'ALL-99 REGISTRY ENTRIES: not listed in this retained context (older context)\n'))
    if render is None:
        return (head + 'PICTURE (exact typed text, encoding typed mapping entries with c15_journal.pack scalar tags; sha256 '
                + context['picture_sha256'] + '):\n' + context['picture_text'])
    return (head + LEGEND + '\n'
            + 'PICTURE (' + render['grammar'] + '; %d chars for %d chars of exact typed text; sha256 of the exact typed text %s; '
              'parse-back proven byte-exact before this read):\n' % (render['chars'], render['source_chars'], context['picture_sha256'])
            + render['text'])
