"""The voice of the post-class discussion: what it would be given, and the pure-code validator of what it would say.

research/kalshi/frankie_boss/knowledge/GRANITE_DISCUSSION_VOICE_ROLE_V1.md (a DRAFT charter for Greg's confirmation) has a
model speak the three seats of the three-way exchange (frankie_box_experiment_exchange.py) from their code turns only.
NOTHING HERE CALLS A MODEL, and the orchestrator's 'voice' stage is NOT WIRED: the confirmed classroom rules
(knowledge/CLASSROOM_RULES_V1.json, R17) say no model voice in the classroom, and an amendment needs Greg's own
confirmation (with the build-plan component and the Pod). The stage records waiting, not wired, and never blocks the
school or the reports. What is built, code only:

  voice_input(exchange)       per item of Frankie's view of the exchange, the three seats' turns exactly as the charter
                              says the voice is given them: seat, author, the turn's text and lines, and every value the
                              turn cites with the sha256 of the file it came from (Jev's items are not in Frankie's view:
                              the lessons wall);
  parse_output(text)          one JSON object of the charter's output format (a surrounding code fence is removed; nothing
                              else is repaired);
  validate(exchange, outputs) every line checked against the SPEAKING seat's own turn: its seat must have a turn on the
                              item; every number in its text and every cited value must appear in that seat's turn (its
                              cites or its own words); every cite's source_sha256 must be the file that value came from
                              in that turn; no pooling, rate or average words, no prediction, trade or advice phrases
                              (charter rules 1-5). A line that breaks any of these is REFUSED and listed with the reason,
                              never kept. The close may only use numbers found in the item's three turns. Items not spoken,
                              seats with no accepted line, and items the output names that the exchange does not hold are
                              listed (charter rule 10: never drop anything). Agreement between voiced seats is never a
                              confirmation (charter rule 9): the validator marks every accepted line orientation only.
"""
import hashlib
import json
import re
from pathlib import Path

CHARTER = Path(__file__).resolve().parents[3] / 'research/kalshi/frankie_boss/knowledge/GRANITE_DISCUSSION_VOICE_ROLE_V1.md'
VALIDATION_SCHEMA = 'FRANKIE_EXCHANGE_VOICE_VALIDATION_V1'
INPUT_SCHEMA = 'FRANKIE_EXCHANGE_VOICE_INPUT_V1'
SEATS = ('boss_teacher', 'scientific_teacher', 'frankie')
VOICE_LABEL = 'Granite (voice)'
NUMBER = re.compile(r'(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])')
POOLED = ('average', 'averag', 'on the whole', 'mostly', 'percent', '%', 'in total', 'overall rate', 'the mean')
FORWARD = ('will rise', 'will fall', 'will go up', 'will go down', 'will move', 'is going to', 'going to rise',
           'going to fall', 'recommend', 'should trade', 'should buy', 'should sell', 'take a position')
NOT_WIRED = ("not wired: the voice of the post-class discussion needs Greg's own confirmation of an amendment to R17 "
             "(knowledge/CLASSROOM_RULES_V1.json: no model voice in the classroom), the build-plan component and the Pod; "
             "the exchange's voice_turns are ready for it and this validator is built (code only)")


def charter_witness():
    """The charter file by name, sha256 and bytes; (None) when it is not in the checkout."""
    if not CHARTER.is_file():
        return None
    data = CHARTER.read_bytes()
    return dict(file=CHARTER.name, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def voice_input(exchange):
    """[{item_id, author, author_label, turns: [{seat, author, author_label, text, lines, cites}]}] of Frankie's view."""
    if exchange.get('schema') != 'FRANKIE_EXPERIMENT_EXCHANGE_V1' or exchange.get('view') != 'frankie':
        raise ValueError('the voice is given only Frankie\'s view of the exchange (FRANKIE_EXPERIMENT_EXCHANGE_V1, view frankie)')
    out = []
    for item in exchange.get('items') or []:
        out.append(dict(item_id=item['item_id'], author=item['author'], author_label=item['author_label'],
                        turns=[{k: t.get(k) for k in ('seat', 'author', 'author_label', 'text', 'lines', 'cites')}
                               for t in item.get('voice_turns') or []]))
    return dict(schema=INPUT_SCHEMA, day=exchange.get('day'), run=exchange.get('run'),
                exchange_hash=exchange.get('exchange_hash'), charter=charter_witness(), items=out)


def parse_output(text):
    """(object, None) or (None, why): one JSON object; a surrounding ``` fence is removed, nothing else is repaired."""
    body = (text or '').strip()
    fence = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', body, re.S)
    if fence:
        body = fence.group(1)
    try:
        value = json.loads(body)
    except ValueError as error:
        return None, 'not one JSON object (%s)' % error
    if not isinstance(value, dict):
        return None, 'the output is not a JSON object'
    return value, None


def _allowed(turn):
    """(numbers the seat's turn holds, {cited value: {sha256}}, every sha256 the turn cites)."""
    words = ' '.join([turn.get('text') or ''] + [str(x) for x in turn.get('lines') or []])
    cited = {}
    for c in turn.get('cites') or []:
        cited.setdefault(str(c.get('value')), set()).add(c.get('source_sha256'))
    numbers = set(NUMBER.findall(words)) | {v for v in cited if NUMBER.fullmatch(v)}
    return numbers, cited, {s for shas in cited.values() for s in shas}


def _line_problem(line, turns):
    if not isinstance(line, dict) or set(line) - {'seat', 'text', 'cites'} or not isinstance(line.get('text'), str) \
            or not line['text'].strip() or not isinstance(line.get('cites', []), list):
        return 'malformed line (the charter\'s line is {seat, text, cites})'
    seat = line.get('seat')
    if seat not in SEATS:
        return 'unknown seat %r' % seat
    turn = turns.get(seat)
    if turn is None:
        return 'the seat %s has no turn on this item (nothing of its own to speak)' % seat
    numbers, cited, shas = _allowed(turn)
    for token in NUMBER.findall(line['text']):
        if token not in numbers:
            return 'the number %s is not in the %s\'s turn (charter rules 1-2: never calculate, never bring in a number)' % (
                token, seat)
    for c in line.get('cites') or []:
        if not isinstance(c, dict) or 'value' not in c or 'source_sha256' not in c:
            return 'malformed cite (the charter\'s cite is {value, source_sha256})'
        value = str(c['value'])
        if value in cited:
            if c['source_sha256'] not in cited[value]:
                return 'the cited value %s did not come from %s in the %s\'s turn' % (value, c['source_sha256'], seat)
        elif value in numbers:
            if c['source_sha256'] not in shas:
                return 'the cited value %s names %s, a file the %s\'s turn does not cite' % (value, c['source_sha256'], seat)
        else:
            return 'the cited value %s is not in the %s\'s turn' % (value, seat)
    lower = line['text'].lower()
    for w in POOLED:
        if w in lower:
            return 'pooled or computed wording %r (charter rules 1 and 3: never average or pool)' % w
    for w in FORWARD:
        if w in lower:
            return 'forward or trade wording %r (charter rules 4-5: never predict, trade or advise)' % w
    return None


def validate(exchange, outputs):
    """The charter's outputs checked against Frankie's view of the exchange. outputs: [parsed object or raw text]."""
    items = {i['item_id']: {t['seat']: t for t in i['turns']} for i in voice_input(exchange)['items']}
    accepted, refused, not_spoken, unknown, closes = [], [], [], [], []
    spoken = set()
    for index, out in enumerate(outputs):
        value, why = (out, None) if isinstance(out, dict) else parse_output(out)
        if value is None:
            refused.append(dict(output=index, item_id=None, line=None, seat=None, text=None, reason=why))
            continue
        item_id = value.get('item_id')
        turns = items.get(item_id)
        if turns is None:
            unknown.append(dict(output=index, item_id=item_id, reason='the exchange holds no such item (Frankie\'s view)'))
            continue
        if item_id in spoken:
            refused.append(dict(output=index, item_id=item_id, line=None, seat=None, text=None,
                                reason='the item is spoken twice; the first output is kept'))
            continue
        spoken.add(item_id)
        kept = []
        for n, line in enumerate(value.get('lines') or []):
            problem = _line_problem(line, turns)
            if problem:
                refused.append(dict(output=index, item_id=item_id, line=n, seat=(line or {}).get('seat') if isinstance(line, dict) else None,
                                    text=(line or {}).get('text') if isinstance(line, dict) else None, reason=problem))
            else:
                kept.append(dict(line, author=VOICE_LABEL, orientation_only=True))
        close = value.get('close')
        numbers = set().union(*(_allowed(t)[0] for t in turns.values())) if turns else set()
        close_text = ' '.join(str(close.get(k)) for k in ('agreed', 'open', 'next_tests')) if isinstance(close, dict) else ''
        bad = [t for t in NUMBER.findall(close_text) if t not in numbers]
        if not isinstance(close, dict) or set(close) != {'agreed', 'open', 'next_tests'}:
            closes.append(dict(item_id=item_id, accepted=False, reason='malformed close (the charter\'s close is {agreed, open, next_tests})'))
            close = None
        elif bad:
            closes.append(dict(item_id=item_id, accepted=False, reason='the close says %s, not in the item\'s turns' % bad))
            close = None
        elif any(w in close_text.lower() for w in POOLED + FORWARD):
            closes.append(dict(item_id=item_id, accepted=False, reason='pooled, forward or trade wording in the close'))
            close = None
        else:
            closes.append(dict(item_id=item_id, accepted=True))
        accepted.append(dict(item_id=item_id, lines=kept, close=close, author=VOICE_LABEL,
                             note='orientation only: the seats voiced by one model agreeing is never a confirmation'))
        for seat in turns:
            if not any(l['seat'] == seat for l in kept):
                not_spoken.append(dict(item_id=item_id, seat=seat, reason='no accepted line of this seat (refused or absent)'))
    for item_id in items:
        if item_id not in spoken:
            not_spoken.append(dict(item_id=item_id, seat=None, reason='the item was not spoken'))
    return dict(schema=VALIDATION_SCHEMA, exchange_hash=exchange.get('exchange_hash'), charter=charter_witness(),
                accepted=accepted, refused=refused, closes=closes, not_spoken=not_spoken, unknown_items=unknown,
                counts=dict(items=len(items), spoken=len(spoken), lines_accepted=sum(len(a['lines']) for a in accepted),
                            lines_refused=sum(1 for r in refused if r.get('line') is not None),
                            outputs_refused=sum(1 for r in refused if r.get('line') is None)),
                model_calls=0)
