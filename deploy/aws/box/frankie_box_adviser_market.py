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
import struct
from pathlib import Path

SCHEMA = 'FRANKIE_ADVISER_MARKET_CONTEXT_V1'
REFERENCE_SCHEMA = 'FRANKIE_ADVISER_MARKET_CONTEXT_REFERENCE_V1'
WORKFLOW_REPORT_SCHEMA = 'FRANKIE_PIECE_WORKFLOW_REPORT_V1'
RENDER_SCHEMA = 'FRANKIE_ADVISER_PICTURE_RENDER_V1'
ALL_99_SCHEMA = 'FRANKIE_ALL_99_COVERAGE_V1'
MISSING_COVERAGE_RULE = 'every_authentic_boundary_kept_with_thinner_explicit_picture'
WORKERS = 15
USE = 'complete same-time picture at the existing original source cutoff; no target-derived selection'
LIMIT = ('model receives this complete cutoff picture, not every historical picture; full ordered reader remains '
         'available to owner code; no time-addressable model query protocol or new scientific calculation')
REPO = Path(__file__).resolve().parents[3]
# The pinned 99-layer registry (content identity 239a1480...) is named by the committed crosswalk of run
# 33746436209; the crosswalk file is pinned by knowledge/CYCLE_CALCULATION_PINS.json (path, bytes, sha256).
# The registry JSON itself is not in this checkout; the crosswalk carries every layer_id and group_id.
REGISTRY_SHA256 = '239a14808850d9cc9ba589165e4263c0e3f11a0c574052f39bfaa133adf296b1'
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
    """Typed picture tree -> stacked tree, choosing at every sequence the candidate that spells shortest."""

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
            if all(v[0] == 'int' for v in items):
                choices.append(('N', ['N', kind, self._integers([v[1] for v in items])]))
            if all(v[0] == 'mapping' and v[1] and all(k[0] == 'str' for k, _ in v[1]) for v in items):
                keys = [k[1] for k, _ in items[0][1]]
                if keys and all([k[1] for k, _ in v[1]] == keys for v in items):
                    columns = [self.sequence([v[1][j][1] for v in items], 'L') for j in range(len(keys))]
                    choices.append(('C', ['C', kind, [_esc(k) for k in keys], columns]))
                    digest = self.digest_table(items, keys, kind)
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
    if tag == 'X':
        return ['bytes', node[1]]
    if tag == 'M':
        keys, values = node[1], node[2]
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


def _dedup(tree, canonical):
    """L3 of the reading render on the stacked tree: a subtree spelled identically more than once is kept once
    under $dictionary and referenced where it recurs, only where the arithmetic says it saves characters."""
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
    'order_lifecycle_fills': ('stream', 'root.structures', ('fill_disposition',)),
    'order_lifecycle_clears': ('stream', 'root.frames', ('observation', 'native_frame', 'integrity')),
    'order_identity_transitions': ('bedrock',),
    'contract_session_roll_state': ('bedrock',),
    # full_book_fifo_queue (8)
    'full_bid_ask_depth': ('stream', 'root.frames', ('book', 'bid_depth_full', 'ask_depth_full')),
    'price_level_and_order_counts': ('stream', 'root.frames', ('book', 'bid_order_count_full', 'bid_price_level_count_full')),
    'fifo_queues': ('stream', 'root.frames', ('book', 'observation')),
    'queue_age_and_survival': ('stream', 'root.frames', ('book', 'observation')),
    'queue_concentration': ('stream', 'root.frames', ('book', 'observation')),
    'orders_and_volume_ahead': ('stream', 'root.frames', ('book', 'observation')),
    'spread_and_depth_imbalance': ('stream', 'root.frames', ('book', 'spread', 'depth_imbalance_n', 'depth_imbalance_full')),
    'complete_state_reset_bootstrap_receipts': ('input', ('flags', 'action')),
    # microstructure_mechanics (7)
    'mechanics_actions_by_side_and_level': ('stream', 'root.structures', ('action_counts', 'side_counts')),
    'aggressor_and_native_signed_flow': ('completed', 'legacy_native_signed_flow'),
    'depletion_and_replenishment': ('teacher', 'far_replenish_log1p_64/1024, far_absorption_share_64/1024'),
    'resilience_and_recovery': ('teacher', 'far_identity_survival_64/1024, far_size_retention_64/1024'),
    'churn_and_queue_turnover': ('stream', 'root.frames', ('activity',)),
    'price_and_book_path': ('stream', 'root.prices', ('price', 'provenance')),
    'missingness_and_integrity_flags': ('stream', 'root.frames', ('integrity',)),
    # legacy_observable_crosswalk (5)
    'legacy_price': ('stream', 'root.prices', ('price', 'size', 'provenance')),
    'legacy_native_signed_flow': ('completed', 'legacy_native_signed_flow'),
    'legacy_per_second_roll20': ('completed', 'legacy_per_second_roll20'),
    'legacy_book_imbalance': ('stream', 'root.frames', ('book', 'depth_imbalance_n', 'best_bid', 'mid')),
    'legacy_structure_observables': ('stream', 'root.structures', ('action_counts', 'side_counts', 'component_count', 'price_raw_min')),
    # derived_geometry (8)
    'derived_roll20_and_dipole_state': ('completed', 'legacy_per_second_roll20'),
    'derived_d_family_geometry': ('stream', 'root.structures', ('candidate_family_id', 'mirror', 'carried_native_family')),
    'derived_open_world_predecessor_state': ('stream', 'root.structures', ('discovery_status',)),
    'derived_ancestry_gaps': ('bedrock',),
    'derived_unresolved_age_chain_trajectory': ('teacher', 'unresolved_age_groups_log, extension_count_log, step_ratio_log, '
                                                           'pullback_ticks_last_log, step_duration_groups_log, pullback_ticks_prev_log'),
    'derived_price_flow_book_paths': ('stream', 'root.frames', ('book', 'best_bid', 'mid', 'spread')),
    'derived_v4_mechanics_fifo_features': ('bedrock',),
    'derived_feature_availability_timestamps': ('availability',),
    # prebirth_opportunity (5)
    'prebirth_predecessor_at_risk_state': ('bedrock',),
    'prebirth_unresolved_chain_extension_state': ('teacher', 'extension_count_log, step_ratio_log, pullback_ticks_*'),
    'prebirth_ancestry_successor_opportunity': ('bedrock',),
    'prebirth_stopped_chain_false_context_controls': ('bedrock',),
    'prebirth_negative_opportunity_cases': ('bedrock',),
    # causal_clocks (7)
    'clock_event_time': ('clock', ('ts_event_ns', 'raw_event_clock')),
    'clock_receive_time': ('clock', ('ts_recv_ns', 'raw_receive_clock')),
    'clock_event_known_by': ('availability',),
    'clock_feature_availability': ('availability',),
    'clock_prospective_discovery_confirmation': ('consumer', 'lessons'),
    'clock_model_evaluation': ('host_clock',),
    'clock_lock_time': ('host_clock',),
    # binding_common_controls (4)
    'controlling_rt_mission': ('consumer', 'directive'),
    'native_calculation_contract': ('identity', 'policy'),
    'anchored_knowledge_manifest': ('consumer', 'knowledge'),
    'selected_same_arm_profile': ('retired',),
    # a_clean_overlay (1), a_memory_overlay (3)
    'a_clean_promoted_positive_capsule': ('not_applicable',),
    'a_memory_promoted_positive_capsule': ('retired',),
    'a_memory_prior_lessons_package': ('retired',),
    'a_memory_prior_package_proof': ('retired',),
    # current_brain_runtime (5)
    'authoritative_s135_construction': ('consumer', 'brain'),
    'complete_s105_9_brain': ('consumer', 'brain'),
    'doctrine_reasoning_play_index_evidence': ('consumer', 'brain'),
    'lawful_prior_session_carry': ('consumer', 'carry'),
    'october_outcome_wall_enforcement': ('rule', 'walls'),
    # frozen_learned_structure (9)
    'learned_d_structures_and_families': ('consumer', 'knowledge'),
    'learned_dipoles_and_geometry': ('consumer', 'knowledge'),
    'learned_pair_triplet_recurrence': ('consumer', 'knowledge'),
    'learned_chains_extensions_reappearances_ancestry': ('consumer', 'knowledge'),
    'phase1_discoveries_structural_falsifiers': ('consumer', 'knowledge'),
    'phase2_findings_modules_timing_pox_negatives': ('consumer', 'knowledge'),
    'predecessor_ancestry_unresolved_chain_state': ('consumer', 'knowledge'),
    'historical_timing_lifespan_context': ('consumer', 'knowledge'),
    'learned_structure_proposal_index_material': ('consumer', 'knowledge'),
    # corrected_extra_agent_carryforward (1)
    'extra_agent_corrected_information_and_gap_diagnoses': ('consumer', 'knowledge'),
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
ROLES = {'canonical_raw_dbn_mbo': 'raw', 'order_lifecycle': 'calculation', 'full_book_fifo_queue': 'calculation',
         'microstructure_mechanics': 'calculation', 'legacy_observable_crosswalk': 'calculation',
         'derived_geometry': 'calculation', 'prebirth_opportunity': 'calculation', 'causal_clocks': 'clock',
         'binding_common_controls': 'control', 'a_clean_overlay': 'arm', 'a_memory_overlay': 'arm',
         'current_brain_runtime': 'knowledge', 'frozen_learned_structure': 'knowledge',
         'corrected_extra_agent_carryforward': 'knowledge', 'sealed_target_timing': 'sealed_answer',
         'sealed_step1_answer': 'sealed_answer', 'provisional_shadow': 'shadow', 'append_only_outputs': 'output'}


def registry_layers():
    """(rows of {layer_id, group_id, role}, source note) from the pinned crosswalk; when the pinned file is absent
    or its bytes differ, the committed code lists (49 calculation layers, 9 learned structures, 10 outputs) stand
    in and the note says which names are unavailable in this checkout. Never invented."""
    pins = json.loads(CALCULATION_PINS.read_bytes()) if CALCULATION_PINS.is_file() else {}
    pin = pins.get('crosswalk') or {}
    path = REPO / pin['path'] if pin.get('path') else None
    if path is not None and path.is_file():
        raw = path.read_bytes()
        if _sha256(raw) == pin.get('sha256') and len(raw) == pin.get('bytes'):
            crosswalk = json.loads(raw)
            if crosswalk.get('registry_sha256') == REGISTRY_SHA256 and len(crosswalk.get('layers') or []) == 99:
                rows = [dict(layer_id=l['layer_id'], group_id=l['group_id'], role=ROLES.get(l['group_id'], 'unknown'),
                             historical_delivery_status=l.get('status')) for l in crosswalk['layers']]
                return rows, dict(source='pinned crosswalk', path=str(path), sha256=pin['sha256'], bytes=pin['bytes'],
                                  registry_sha256=REGISTRY_SHA256, layers=99)
            note = 'crosswalk file names another registry or layer count'
        else:
            note = 'crosswalk bytes differ from their pin (integrity: separate visible failure, not missing coverage)'
    else:
        note = 'crosswalk file absent from this checkout'
    from research.kalshi.frankie_boss import frankie_principal_adapter as PA
    rows = [dict(layer_id=layer, group_id=group, role=ROLES.get(group, 'calculation'), historical_delivery_status=None)
            for group, layers in PA.REGISTRY_CALCULATION_SET for layer in layers]
    rows += [dict(layer_id=l, group_id='frozen_learned_structure', role='knowledge', historical_delivery_status=None)
             for l in PA.FROZEN_LEARNED_STRUCTURE]
    rows += [dict(layer_id=l, group_id='append_only_outputs', role='output', historical_delivery_status=None)
             for l in PA.OUTPUT_LEDGERS]
    return rows, dict(source='committed code lists (fallback)', reason=note, registry_sha256=REGISTRY_SHA256,
                      layers_named=len(rows), layers_unnamed=99 - len(rows),
                      unnamed_groups='canonical_raw_dbn_mbo (6), binding_common_controls (4), a_clean/a_memory overlays (4), '
                                     'current_brain_runtime (5), corrected_extra_agent_carryforward (1), sealed (9), shadow (2)')


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
    loaded, or None/absent = not loaded by this piece)."""
    rows, registry = registry_layers()
    identity = identity or (reader.identity if reader is not None else None) or {}
    layers = getattr(reader, 'layers', None) or {}
    source = getattr(reader, 'source', None) or {}
    consumer = consumer or {}
    at = (picture or {}).get('at') or {}
    boundary = at.get('input_cursor')
    observed = {}
    if picture is not None:
        for update in list(picture.get('updates') or []) + list(picture.get('last_observed_state') or []):
            entry = observed.setdefault(update['source'], dict(instruments=set(), at_boundary=0, previously_known=0, keys=set()))
            entry['instruments'].add(update.get('instrument_id'))
            entry['at_boundary' if update.get('input_cursor') == boundary else 'previously_known'] += 1
            if isinstance(update.get('value'), dict):
                entry['keys'].update(update['value'].keys())
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
        if picture is None and kind in ('identity', 'source', 'input', 'stream', 'clock', 'availability', 'completed', 'bedrock'):
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
        out.append(dict(entry=row['layer_id'], group=row['group_id'], role=row['role'], route=kind,
                        disposition=disposition, reason=reason, **({'where': where} if where is not None else {})))
    counts = {}
    for item in out:
        counts[item['disposition']] = counts.get(item['disposition'], 0) + 1
    return dict(schema=ALL_99_SCHEMA, registry=registry, at=dict(input_cursor=boundary, adapter_cursor=at.get('adapter_cursor'),
                                                                 ts_recv_ns=at.get('ts_recv_ns')),
                consumer=consumer.get('piece'), entries=len(out), counts=counts, rows=out,
                rule='roles are not interchangeable numeric layers; a thin or absent entry keeps the instant with its disposition; '
                     'a listed arrival is not proof that a consumer computed on it (' + MISSING_COVERAGE_RULE + ')')


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
        counts[row['disposition']] = counts.get(row['disposition'], 0) + 1
    out.update(consumer=consumer.get('piece'), counts=counts)
    return out


# ------------------------------------------------------------------------------------ the context
class AdviserMarketContext:
    def __init__(self, identity, *, day, source_hash, as_of, through_cursor):
        from frankie_box_durable import witness
        from frankie_box_market_timeline import SharedMarketTimeline, _json
        if type(as_of) is not int or type(through_cursor) is not int or through_cursor < 0:
            raise ValueError('adviser cutoff requires the original explicit integer as_of and through_cursor')
        self.root = Path(identity['calculations']['path']).parent
        self.day = str(day)
        self.reader = SharedMarketTimeline(self.root, day=self.day, workers=WORKERS)
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
        for name, pin in pinned.items():
            if witness(pin['path']) != {k: pin[k] for k in ('bytes', 'sha256')}:
                raise ValueError('pinned shared layer bytes differ from their source pin: ' + name)
        self.pins_verified = sorted(['journal', *pinned])
        self.scope = dict(day=self.day, source_hash=source_hash, as_of=as_of, through_cursor=through_cursor,
                          record_count=record_count,
                          position=('last_sealed_input' if through_cursor == record_count - 1
                                    else 'before_sealed_source_end'),
                          origin='the measurement\'s own explicit source scope; no target-derived selection')

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
        stream = self.reader.iter_pictures()
        try:
            for item in stream:
                check_save()
                picture = item['picture']
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
        reader = SharedMarketTimeline(self.root, day=self.day, workers=WORKERS)
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


def from_teacher(rows_path, day, measure, *, retain=None, check_save=lambda: None):
    """(context, None) from the teacher's own explicit source/as-of/cursor, never its answers;
    (None, why) when the teacher source carries no shared identity or its rows were not readable."""
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
    if retain is not None and Path(retain).is_file():
        return load_context(retain, identity=reader.reader.identity, scope=reader.scope), None
    context = reader.read(check_save=check_save)
    if retain is not None:
        retain_context(retain, context)
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
