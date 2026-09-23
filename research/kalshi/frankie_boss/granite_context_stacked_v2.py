"""Stacked V2: the stacked V1 codec plus token-minimal exact forms, stacked ON TOP of V1 (Greg, 2026-09-23).

V1 is untouched and still byte-identical. V2 adds forms the Sunday cycle-0 packet measured as the largest token
costs (every row paid about two tokens per single-digit value): packed digit strings, one-letter strings, a tick
scale with literal exceptions, a packed dictionary, and the order-parent graph derived instead of shipped. Each
candidate spelling is chosen by the pinned Granite tokenizer's count, not by characters. Encoding refuses unless
the decode reproduces the exact native bytes, as V1 does.
"""
import copy
import hashlib
import math
import json
from pathlib import Path

from . import granite_context_stacked as v1

SCHEMA = 'BOSS_GRANITE_NATIVE_STACKED_CONTEXT_V2'
PROMPT_VERSION = 'BOSS_GRANITE_NATIVE_STACKED_PROMPT_V2'
GRAMMAR = v1.GRAMMAR + """Stacked V2 adds exact forms. P lo width digits: an integer sequence written as one string of fixed-width decimal fields, each value = field + lo. Y text: a sequence of one-character strings, one per character. K scale recipe exceptions: integers = scale x the recipe's values, except positions listed in exceptions, which hold their literal values. U dictionary indexes: like Q, with the dictionary values given as one sequence node and indexes as an integer node. O base outliers: the base integer recipe with listed positions replaced by their literal values. A P, O, K or D recipe may stand wherever an integer recipe stands. graph_recipe PARENT_BY_ORDER_V1: graph is not shipped; graph[i] is the index of the latest earlier evidence row with the same publisher_id, instrument_id and nonzero order_id, else -1.
"""
GRAPH_RULE = 'PARENT_BY_ORDER_V1'
TOKENIZER = (Path(__file__).parent / 'sunday_20260915_package/C_Codex/2026-09-14/if-you-mean-claude-code-a/'
             'work/verified-tokenizer/tokenizer.json')
TOKENIZER_SHA256 = '883975314d587437'  # prefix of the verified tokenizer.json digest, checked at load


def grammar_hash():
    return hashlib.sha256(GRAMMAR.encode()).hexdigest()


_tokenizer = None


def _cost(node):
    """Pinned Granite token count of a node's exact spelling."""
    global _tokenizer
    if _tokenizer is None:
        raw = TOKENIZER.read_bytes()
        if not hashlib.sha256(raw).hexdigest().startswith(TOKENIZER_SHA256):
            raise ValueError('pinned Granite tokenizer bytes differ')
        from tokenizers import Tokenizer
        _tokenizer = Tokenizer.from_str(raw.decode())
    return len(_tokenizer.encode(v1._text(node)).ids)


def _packed(values):
    lo = min(values)
    natural = max(1, len(str(max(values) - lo)))
    # Keep the existing P grammar, but choose the field width by the pinned
    # tokenizer.  Zero padding is lossless and can change how Granite groups
    # a digit run, so the character-shortest spelling is not always the
    # token-shortest spelling.
    candidates = []
    for width in range(1, natural + 1):
        digits = ''.join(str(v - lo).zfill(width) for v in values)
        candidates.append(['P', lo, width, digits])
    return min(candidates, key=_cost)


def _outliers(values):
    """Narrow packed fields with the rare values outside them listed literally (a few wide deltas no longer
    widen every field)."""
    out = []
    ordered = sorted(values)
    lo = ordered[len(ordered) // 100]
    for width in (1, 2, 3):
        hi = lo + 10**width - 1
        exceptions = [[i, v] for i, v in enumerate(values) if not lo <= v <= hi]
        if exceptions and len(exceptions) * 20 < len(values):
            listed = {i for i, _ in exceptions}
            base = ''.join(str((lo if i in listed else v) - lo).zfill(width) for i, v in enumerate(values))
            out.append(['O', ['P', lo, width, base], exceptions])
    return out


def _int_recipes(values):
    choices = [v1._integers(values)]
    if values:
        choices.append(_packed(values))
        choices += _outliers(values)
        deltas = [b - a for a, b in zip(values, values[1:])]
        if deltas:
            choices.append(['D', values[0], _packed(deltas)])
            choices += [['D', values[0], o] for o in _outliers(deltas)]
        scale = 0
        for v in values:
            if v and abs(v) < 2**62:
                scale = abs(v) if not scale else math.gcd(scale, v)
        if scale > 1:
            exceptions = [[i, v] for i, v in enumerate(values) if v % scale or abs(v) >= 2**62]
            if len(exceptions) * 4 < len(values):
                listed = {i for i, _ in exceptions}
                scaled = [0 if i in listed else v // scale for i, v in enumerate(values)]
                inner = min(_int_recipes_plain(scaled), key=_cost)
                choices.append(['K', scale, inner, exceptions])
    return choices


def _int_recipes_plain(values):
    choices = [v1._integers(values), _packed(values)] if values else [v1._integers(values)]
    if values:
        choices += _outliers(values)
    deltas = [b - a for a, b in zip(values, values[1:])]
    if deltas:
        choices.append(['D', values[0], _packed(deltas)])
        choices += [['D', values[0], o] for o in _outliers(deltas)]
    return choices


def _encode(value):
    kind = type(value)
    if kind is dict:
        if not all(type(key) is str for key in value):
            raise ValueError('string map keys required')
        return ['M', list(value), [_encode(v) for v in value.values()]]
    if kind in (list, tuple):
        outer = 'L' if kind is list else 'T'
        items = list(value)
        if not items:
            return [outer, []]
        if type(items[0]) is dict and items[0] and all(type(v) is dict and list(v) == list(items[0]) for v in items):
            return ['C', outer, list(items[0]), [_encode([v[key] for v in items]) for key in items[0]]]
        choices = [v1._encode(value)]
        if all(type(v) is int for v in items):
            choices += [['N', outer, r] for r in _int_recipes(items)]
        if all(type(v) is str and len(v) == 1 for v in items):
            choices.append(['Y', outer, ''.join(items)])
        seen, dictionary, indexes = {}, [], []
        for item in items:
            key = v1._text(v1._encode(item))
            if key not in seen:
                seen[key] = len(dictionary)
                dictionary.append(item)
            indexes.append(seen[key])
        if len(dictionary) < len(items):
            index_node = min(_int_recipes_plain(indexes), key=_cost)
            choices.append(['U', outer, _encode(dictionary), index_node])
        return min(choices, key=_cost)
    return v1._encode(value)


def _ints(node, budget):
    tag = node[0] if type(node) is list and node else None
    if tag == 'P' and len(node) == 4:
        lo, width, digits = node[1:]
        if (type(lo) is not int or type(width) is not int or width < 1 or type(digits) is not str
                or len(digits) % width or not digits.isdigit()):
            raise ValueError('exact packed digits required')
        budget.take(len(digits) // width, len(digits))
        return [int(digits[i:i + width]) + lo for i in range(0, len(digits), width)]
    if tag == 'D' and len(node) == 3 and type(node[2]) is list and node[2] and node[2][0] in ('P', 'O'):
        if type(node[1]) is not int:
            raise ValueError('integer seed required')
        result = [node[1]]
        for delta in _ints(node[2], budget):
            result.append(result[-1] + delta)
        return result
    if tag == 'O' and len(node) == 3:
        values = _ints(node[1], budget)
        if type(node[2]) is not list:
            raise ValueError('exact outlier list required')
        for pair in node[2]:
            if type(pair) is not list or len(pair) != 2 or type(pair[0]) is not int or type(pair[1]) is not int \
                    or not 0 <= pair[0] < len(values):
                raise ValueError('exact outlier required')
            values[pair[0]] = pair[1]
        return values
    if tag == 'K' and len(node) == 4:
        scale, inner, exceptions = node[1:]
        if type(scale) is not int or scale < 2 or type(exceptions) is not list:
            raise ValueError('exact tick scale required')
        values = [v * scale for v in _ints(inner, budget)]
        for pair in exceptions:
            if type(pair) is not list or len(pair) != 2 or type(pair[0]) is not int or type(pair[1]) is not int \
                    or not 0 <= pair[0] < len(values):
                raise ValueError('exact scale exception required')
            values[pair[0]] = pair[1]
        return values
    return v1._ints(node, budget)


def _decode(node, budget, depth=0):
    if type(node) is list and node and node[0] in ('N', 'Q', 'Y', 'U') and len(node) >= 3 and node[1] in ('L', 'T'):
        tag, kind = node[0], node[1]
        budget.take()
        if tag == 'N' and len(node) == 3:
            values = _ints(node[2], budget)
        elif tag == 'Y' and len(node) == 3 and type(node[2]) is str:
            budget.take(len(node[2]), len(node[2]))
            values = list(node[2])
        elif tag in ('Q', 'U') and len(node) == 4:
            dictionary = node[2] if tag == 'Q' else _decode(node[2], budget, depth + 1)
            if type(dictionary) is not list:
                raise ValueError('dictionary sequence required')
            indexes = _ints(node[3], budget)
            if any(i < 0 or i >= len(dictionary) for i in indexes):
                raise ValueError('dictionary index outside values')
            values = [_decode(dictionary[i], budget, depth + 1) for i in indexes] if tag == 'Q' \
                else [copy.deepcopy(dictionary[i]) for i in indexes]
        else:
            raise ValueError('invalid V2 sequence recipe')
        return tuple(values) if kind == 'T' else values
    if type(node) is list and node and node[0] == 'M' and len(node) == 3:
        keys, values = node[1:]
        if type(keys) is not list or type(values) is not list or len(keys) != len(values) or len(set(keys)) != len(keys):
            raise ValueError('ordered unique string keys required')
        budget.take(len(keys))
        return dict(zip(keys, [_decode(v, budget, depth + 1) for v in values]))
    if type(node) is list and node and node[0] in ('L', 'T') and len(node) == 2 and type(node[1]) is list:
        budget.take(len(node[1]))
        values = [_decode(v, budget, depth + 1) for v in node[1]]
        return tuple(values) if node[0] == 'T' else values
    if type(node) is list and node and node[0] == 'C' and len(node) == 4 and node[1] in ('L', 'T'):
        keys, columns = node[2:]
        columns = [_decode(c, budget, depth + 1) for c in columns]
        if type(keys) is not list or len(columns) != len(keys) or len({len(c) for c in columns}) != 1:
            raise ValueError('named column dimensions differ')
        rows = [dict(zip(keys, row)) for row in zip(*columns)]
        return tuple(rows) if node[1] == 'T' else rows
    return v1._decode(node, budget, depth)


def _parents(rows):
    previous, parents = {}, []
    for i, row in enumerate(rows):
        record = row['record'] if type(row) is dict and type(row.get('record')) is dict else {}
        order = record.get('order_id')
        key = (record.get('publisher_id'), record.get('instrument_id'), order)
        has = order is not None and order != 0
        parents.append(previous.get(key, -1) if has else -1)
        if has:
            previous[key] = i
    return parents


def encode(value, *, scope_public=None, prefix_seed=None, limits=v1.DEFAULT_LIMITS):
    if type(limits) is not v1.DecodeLimits:
        raise ValueError('explicit decode limits required')
    expected = v1._exact(value)
    base = v1.encode(value, scope_public=scope_public, prefix_seed=prefix_seed, limits=limits)
    transformed = v1._decode(base['data'], v1._Budget(limits))
    root = transformed['root']
    graph_recipe = None
    if (type(root) is dict and type(root.get('evidence')) in (list, tuple) and type(root.get('graph')) in (list, tuple)
            and list(root['graph']) == _parents(root['evidence'])):
        graph_recipe = dict(rule=GRAPH_RULE, container='L' if type(root['graph']) is list else 'T',
                            layout=list(root))
        root = {k: v for k, v in root.items() if k != 'graph'}
    data = dict(record_recipe=transformed['record_recipe'], packet_recipe=transformed['packet_recipe'],
                graph_recipe=graph_recipe, root=root)
    envelope = dict(schema=SCHEMA, prompt_version=PROMPT_VERSION, grammar_sha256=grammar_hash(), data=_encode(data))
    if v1._exact(decode(envelope, limits=limits)) != expected:
        raise ValueError('stacked V2 exact native inverse differs')
    return envelope


def decode(envelope, *, limits=v1.DEFAULT_LIMITS):
    if (type(envelope) is not dict or set(envelope) != {'schema', 'prompt_version', 'grammar_sha256', 'data'}
            or envelope['schema'] != SCHEMA or envelope['prompt_version'] != PROMPT_VERSION
            or envelope['grammar_sha256'] != grammar_hash()):
        raise ValueError('stacked V2 envelope identity differs')
    if len(v1._text(envelope).encode()) > limits.max_input_bytes:
        raise ValueError('encoded input exceeds decoder limit')
    try:
        data = _decode(envelope['data'], v1._Budget(limits))
        if type(data) is not dict or set(data) != {'record_recipe', 'packet_recipe', 'graph_recipe', 'root'}:
            raise ValueError('exact V2 reconstruction envelope required')
        root = data['root']
        recipe = data['graph_recipe']
        if recipe is not None:
            if type(recipe) is not dict or recipe.get('rule') != GRAPH_RULE or set(recipe) != {'rule', 'container', 'layout'}:
                raise ValueError('unknown graph recipe')
            parents = _parents(root['evidence'])
            root = dict(root, graph=parents if recipe['container'] == 'L' else tuple(parents))
            if set(recipe['layout']) != set(root):
                raise ValueError('graph layout differs')
            root = {k: root[k] for k in recipe['layout']}
        base = dict(schema=v1.SCHEMA, prompt_version=v1.PROMPT_VERSION, grammar_sha256=v1.grammar_hash(),
                    data=v1._encode(dict(record_recipe=data['record_recipe'], packet_recipe=data['packet_recipe'],
                                         root=root)))
        return v1.decode(base, limits=limits)
    except (KeyError, TypeError, IndexError, OverflowError, RecursionError) as error:
        raise ValueError('malformed stacked V2 context') from error
