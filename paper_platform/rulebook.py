"""The saved print-pair rules. All operands come from three named, already-observed rows."""
import json
import operator
from pathlib import Path


RULES = Path(__file__).with_name('rules')
OPS = {'<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge,
       '==': operator.eq, '!=': operator.ne}
CONSTANTS = {'0': 0, 'B': 'B', 'A': 'A'}


def catalogue():
    return {path.stem: json.loads(path.read_text(encoding='utf8')) for path in sorted(RULES.glob('*.json'))}


def operand(term, rows):
    if term in CONSTANTS:
        return CONSTANTS[term]
    name, field = term.split('.')
    return rows[name][field]


def evaluate(conditions, rows, *, conjunction):
    """Return decision and unavailable fields. A nontrade row cannot satisfy a print condition."""
    outcomes, missing = [], []
    for condition in conditions:
        left, op, right = condition.split()
        if 't.price' in (left, right) and not rows['t']['trade']:
            outcomes.append(False)
            continue
        a, b = operand(left, rows), operand(right, rows)
        if a is None or b is None:
            missing.extend(term for term, value in ((left, a), (right, b)) if value is None)
            outcomes.append(None)
        else:
            outcomes.append(OPS[op](a, b))
    if conjunction:
        if False in outcomes:
            return False, []
        return not missing, missing
    if True in outcomes:
        return True, []
    return False, missing


def confirmation(rule, p, q):
    """For a manager the returned side is the required side of its existing trade."""
    rows = {'p': p, 'q': q}
    ok, missing = evaluate(rule['confirm_all'], rows, conjunction=True)
    if not ok:
        return None, missing
    if rule['direction'] != 'aggressor':
        return rule['direction'], []
    missing = []
    for side, conditions in rule['directional_confirm'].items():
        ok, gaps = evaluate(conditions, rows, conjunction=True)
        if ok:
            return side, []
        missing.extend(gaps)
    return None, missing


def management(rule, side, p, q, t):
    rows = {'p': p, 'q': q, 't': t}
    closes = rule.get('directional_close', {}).get(side, rule['close_any'])
    close, missing = evaluate(closes, rows, conjunction=False)
    if close:
        return 'exit', []
    release, gaps = evaluate(rule.get('release_any', []), rows, conjunction=False)
    if release and not missing:
        return 'release warning', []
    return None, sorted(set(missing + gaps))


def manager_action(rule, position, p, q):
    """The same identified open position must exist at p and q; a manager never creates it."""
    if rule['role'] != 'manager' or position['closed'] or position['opened_at'] > p['position']:
        return None, []
    if position['side'] != rule['direction']:
        return None, []
    side, missing = confirmation(rule, p, q)
    return (rule['when_confirmed'] if side else None), missing

