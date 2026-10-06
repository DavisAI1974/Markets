"""Granite as the bounded post-class discussion coordinator (role V2): the meeting loop, code only around one small model.

Greg, 2026-10-06 (GRANITE_DISCUSSION_REPORT_20261006.md, confirming knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md
and CLASSROOM_RULES_V3.json R17). CCode: smaller-model facilitator integration; NOT workflow Step #5.

Three code/data seats already spoke in the three-way exchange (frankie_box_experiment_exchange.py): the BOSS teacher,
the scientific teacher and Frankie, each turn source-bound with cites. Granite is given Frankie's VIEW of that exchange
(Jev's raw items withheld: the lessons wall) and coordinates: it picks the open item, asks a seat to clarify its own
statement, points out a scope mismatch, asks the scientific seat which code test would settle a claim, keeps the list of
agreements, disagreements, missing evidence and requested tests. It adds no evidence:

  - every number in a coordinator turn must already be in the item's three turns (reusing the voice validator's number
    and wording checks: frankie_box_exchange_voice._allowed / POOLED / FORWARD); pooled, forward, trade, confirming or
    deciding wording is refused and listed, never kept;
  - a code seat's answer to a question is that seat's OWN retained record (its exchange turn and side fields), supplied
    by code; no new calculation happens in the meeting. A question that needs a new calculation becomes a REQUESTED TEST
    bound to an existing proposal_id / claim_id / listed untested text of the item, executed later by the proper code
    stage; an unbound request is listed, not executed;
  - RESOLVED is accepted only when the code seats' own records already say so (Frankie's resolution RESOLVED_* and no
    remaining disagreement, and nothing open on the item); otherwise Granite may only LEAVE_OPEN. Granite never decides;
  - every item is discussed or listed; the turn budget and the meeting time budget close an item as OPEN by code.

The durable record FRANKIE_GRANITE_MEETING_V1 keeps the four categories apart: seat_statements, coordinator_turns,
code_seat_answers, open_items/requested_tests. Publication into Frankie's brain (kind 'meeting') needs the brain writer
and entry-kind registration in frankie_box_brain.py (Codex): until then the record is retained and the receipt says so.

Runtime: llama.cpp llama-server, ephemeral, started here and stopped here; model/release pins and the runtime parameters
live in knowledge/GRANITE_MEETING_RUNTIME_V1.json and the gate refuses to call the model while a pin is null or the
parameters are unconfirmed. `--inputs-only` writes what Granite would be given, with zero model calls.
"""
import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BOX = Path(__file__).resolve().parent
REPO = BOX.parents[2]
sys.path.insert(0, str(BOX))
sys.path.insert(0, str(REPO))

SCHEMA = 'FRANKIE_GRANITE_MEETING_V1'
INPUT_SCHEMA = 'FRANKIE_GRANITE_MEETING_INPUT_V1'
RECEIPT_SCHEMA = 'FRANKIE_GRANITE_MEETING_RECEIPT_V1'
REQUEST_SCHEMA = 'FRANKIE_MEETING_TEST_REQUEST_V1'
CONFIG = REPO / 'research/kalshi/frankie_boss/knowledge/GRANITE_MEETING_RUNTIME_V1.json'
CHARTER = REPO / 'research/kalshi/frankie_boss/knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md'
SEATS = ('boss_teacher', 'scientific_teacher', 'frankie')
ACTIONS = ('ASK', 'REQUEST_TEST', 'NOTE_AGREEMENT', 'NOTE_DISAGREEMENT', 'NOTE_SCOPE_MISMATCH', 'LEAVE_OPEN', 'RESOLVED')
COORDINATOR_LABEL = 'Granite (coordinator; coordination only, never evidence)'
# Words that would make the coordinator decide, confirm, grade or promote (role V2 "must never"): refused in any turn.
DECIDING = ('confirm', 'proven', 'proves', 'survivor', 'promote', 'accept the claim', 'is true', 'is valid', 'is correct',
            'is wrong', 'reject', 'grade', 'score', 'tradable', 'signal is valid', 'i conclude', 'i decide', 'therefore the data')
ACTION_SCHEMA = {
    'type': 'object',
    'properties': {
        'item_id': {'type': 'string'},
        'action': {'type': 'string', 'enum': list(ACTIONS)},
        'seat': {'type': ['string', 'null'], 'enum': list(SEATS) + [None]},
        'text': {'type': 'string'},
        'cites': {'type': 'array', 'items': {'type': 'object',
                                             'properties': {'value': {'type': 'string'}, 'source_sha256': {'type': 'string'}},
                                             'required': ['value', 'source_sha256']}},
        'binds_to': {'type': ['string', 'null']},
    },
    'required': ['item_id', 'action', 'seat', 'text', 'cites', 'binds_to'],
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def witness_file(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=sha256_bytes(data))


def load_config(path=CONFIG):
    raw = Path(path).read_bytes()
    config = json.loads(raw)
    if config.get('schema') != 'FRANKIE_GRANITE_MEETING_RUNTIME_V1':
        raise ValueError('%s is not FRANKIE_GRANITE_MEETING_RUNTIME_V1' % path)
    return config, dict(path=str(path), bytes=len(raw), sha256=sha256_bytes(raw))


def gate(config, binary=None, model=None):
    """Every reason the model may NOT be called now; [] = the runtime may start. Explicit blanks refuse (Greg's habit)."""
    reasons = []
    pins = config.get('pins') or {}
    for key in ('model_repository', 'model_file', 'model_sha256', 'llama_cpp_release', 'llama_cpp_asset', 'llama_cpp_sha256'):
        if pins.get(key) in (None, ''):
            reasons.append('pin %s is an explicit blank in GRANITE_MEETING_RUNTIME_V1.json' % key)
    params = config.get('proposed_runtime_parameters') or {}
    if not params.get('confirmed') or not params.get('confirmed_by'):
        reasons.append('the runtime parameters are proposed, not confirmed (confirmed/confirmed_by)')
    if binary is not None:
        if not Path(binary).is_file():
            reasons.append('llama-server binary is not at %s' % binary)
        elif pins.get('llama_cpp_sha256') and sha256_bytes(Path(binary).read_bytes()) != pins['llama_cpp_sha256']:
            reasons.append('llama-server binary sha256 differs from the pin')
    if model is not None:
        if not Path(model).is_file():
            reasons.append('model file is not at %s' % model)
        elif pins.get('model_sha256') and witness_file(model)['sha256'] != pins['model_sha256']:
            reasons.append('model file sha256 differs from the pin')
    return reasons


# ------------------------------------------------------------------------------------------ what Granite is given
def _turn_fields(turn):
    """The seat's retained record fields a code answer may quote back (no private process, no grades: R09/R10)."""
    record = turn.get('record') or {}
    seat = turn.get('seat')
    common = dict(position=record.get('position'), reasoning=record.get('reasoning'),
                  evidence_checks=record.get('evidence_checks'), next_tests=record.get('next_tests'),
                  uncertainty=record.get('uncertainty'))
    if seat == 'boss_teacher':
        common.update(measured=turn.get('measured'), components=turn.get('components'), proposals=turn.get('proposals'))
    elif seat == 'scientific_teacher':
        common.update(counts_on_day=turn.get('counts_on_day'), counts_per_day=turn.get('counts_per_day'),
                      challenges_on_day=turn.get('challenges_on_day'), proposed_tests=turn.get('proposed_tests'),
                      untested=turn.get('untested'), cannot_test_yet=turn.get('cannot_test_yet'), day_text=turn.get('day_text'))
    elif seat == 'frankie':
        common.update(resolution=turn.get('resolution'), learned=record.get('learned'), next_steps=record.get('next_steps'),
                      remaining_disagreements=turn.get('remaining_disagreements'),
                      corrected_understanding=turn.get('corrected_understanding'))
    return {k: v for k, v in common.items() if v is not None}


def open_items_of(item, turns, side):
    """The open items code seeds from the seats' own records; Granite may add none of its own evidence to them."""
    out = []
    positions = {s: (t.get('record') or {}).get('position') for s, t in turns.items() if s != 'frankie'}
    if len(set(positions.values())) > 1:
        out.append(dict(kind='disagreement', seat=None, text='the BOSS teacher and the scientific teacher hold different '
                        'positions: %s' % json.dumps(positions, sort_keys=True), binds_to=None))
    science = side.get('scientific_teacher') or {}
    for p in science.get('proposed_tests') or []:
        out.append(dict(kind='proposed_test', seat='scientific_teacher', text=p.get('text'), binds_to=p.get('proposal_id')))
    for u in science.get('untested') or []:
        out.append(dict(kind='untested', seat='scientific_teacher', text=u, binds_to=u))
    for c in science.get('cannot_test_yet') or []:
        out.append(dict(kind='cannot_test_yet', seat='scientific_teacher',
                        text='%s: %s' % (c.get('series'), c.get('reason')) if isinstance(c, dict) else str(c),
                        binds_to=(c.get('series') if isinstance(c, dict) else str(c))))
    frankie = side.get('frankie') or {}
    for d in frankie.get('remaining_disagreements') or []:
        out.append(dict(kind='remaining_disagreement', seat='frankie', text=d, binds_to=d))
    return out


def meeting_input(exchange, knowledge_index=None):
    """Per item of Frankie's view: the three seats' voiced turns (text, lines, cites), their retained record fields,
    the code-seeded open items. Accumulated knowledge is listed by label and hash only (names, not content)."""
    import frankie_box_exchange_voice as V
    voiced = {i['item_id']: i for i in V.voice_input(exchange)['items']}
    items = []
    for item in exchange.get('items') or []:
        turns = {t['seat']: t for t in item.get('turns') or [] if t.get('seat') in SEATS and not t.get('withheld')}
        side = {s: _turn_fields(t) for s, t in turns.items()}
        items.append(dict(item_id=item['item_id'], author=item['author'], author_label=item['author_label'],
                          claim=item.get('claim'), lessons=item.get('lessons'),
                          voiced=voiced.get(item['item_id'], {}).get('turns') or [],
                          records=side, open_items=open_items_of(item, turns, side)))
    return dict(schema=INPUT_SCHEMA, day=exchange.get('day'), run=exchange.get('run'),
                exchange_hash=exchange.get('exchange_hash'), charter=witness_file(CHARTER) if CHARTER.is_file() else None,
                teachers_findings=[dict(finding_id=f.get('finding_id'), kind=f.get('kind'), status=f.get('status'),
                                        scope=f.get('scope')) for f in exchange.get('teachers_findings') or []],
                knowledge_index=knowledge_index or [], items=items,
                rule='Granite is given these turns and lists; it adds no empirical content (role V2); Jev raw items are '
                     'not in this view (the lessons wall)')


# ------------------------------------------------------------------------------------------ validation of a turn
def validate_action(value, item, turns_by_seat):
    """(accepted action, None) or (None, reason). Reuses the voice validator's number and wording rules."""
    import frankie_box_exchange_voice as V
    if not isinstance(value, dict) or set(value) != set(ACTION_SCHEMA['required']):
        return None, 'malformed coordinator turn (the contract is %s)' % sorted(ACTION_SCHEMA['required'])
    if value['item_id'] != item['item_id']:
        return None, 'the turn names another item (%r)' % value.get('item_id')
    if value['action'] not in ACTIONS:
        return None, 'unknown action %r' % value.get('action')
    text = value.get('text')
    if not isinstance(text, str) or not text.strip():
        return None, 'empty text'
    numbers, cited_all, shas_all = set(), {}, set()
    for turn in turns_by_seat.values():
        n, c, s = V._allowed(turn)
        numbers |= n
        for k, v in c.items():
            cited_all.setdefault(k, set()).update(v)
        shas_all |= s
    for token in V.NUMBER.findall(text):
        if token not in numbers:
            return None, 'the number %s is in no seat\'s turn on this item (role V2: never introduce empirical content)' % token
    for c in value.get('cites') or []:
        if not isinstance(c, dict) or 'value' not in c or 'source_sha256' not in c:
            return None, 'malformed cite'
        v = str(c['value'])
        if v in cited_all:
            if c['source_sha256'] not in cited_all[v]:
                return None, 'the cited value %s did not come from %s in any turn' % (v, c['source_sha256'])
        elif v in numbers:
            if c['source_sha256'] not in shas_all:
                return None, 'the cited value %s names a file no turn cites' % v
        else:
            return None, 'the cited value %s is in no turn' % v
    lower = text.lower()
    for w in V.POOLED:
        if w in lower:
            return None, 'pooled or computed wording %r (never calculate, pool or average)' % w
    for w in V.FORWARD:
        if w in lower:
            return None, 'forward or trade wording %r (never forecast, trade or advise)' % w
    for w in DECIDING:
        if w in lower:
            return None, 'deciding or confirming wording %r (Granite never grades, confirms, promotes or selects)' % w
    seat = value.get('seat')
    if value['action'] == 'ASK':
        if seat not in SEATS:
            return None, 'ASK needs a seat'
        if seat not in turns_by_seat:
            return None, 'the seat %s has no turn on this item' % seat
    if value['action'] == 'REQUEST_TEST':
        if seat != 'scientific_teacher':
            return None, 'a requested test is routed to the scientific teacher (the code test seat)'
        bound = value.get('binds_to')
        allowed = {o['binds_to'] for o in item['open_items'] if o.get('binds_to')}
        allowed |= {(item.get('claim') or {}).get('claim_id')}
        if bound not in allowed:
            return None, ('the requested test is unbound: binds_to must be an existing proposal_id, claim_id or listed '
                          'untested text of this item (%r given); Granite names no new test of its own' % bound)
    if value['action'] == 'RESOLVED':
        frankie = item['records'].get('frankie') or {}
        resolution = str(frankie.get('resolution') or '')
        if not resolution.startswith('RESOLVED_') or frankie.get('remaining_disagreements'):
            return None, ('RESOLVED refused: the code seats\' own records do not say so (Frankie\'s resolution %s, '
                          'remaining disagreements %s); Granite never decides' % (
                              resolution or 'none', json.dumps(frankie.get('remaining_disagreements') or [])))
    return dict(value, author=COORDINATOR_LABEL, evidentiary_weight=0), None


def seat_answer(seat, item):
    """The seat's own retained record, supplied by code. No new calculation; no private process (R09), no grades (R10)."""
    record = item['records'].get(seat)
    if record is None:
        return dict(seat=seat, kind='no_turn', content=None,
                    note='this seat has no turn on the item; nothing of its own to answer from')
    return dict(seat=seat, kind='retained_record', content=record,
                note='the seat\'s own exchange record, restated by code; a question needing a new calculation is a '
                     'requested test for the proper code stage, not an answer')


# ------------------------------------------------------------------------------------------ the model transport
class LlamaServer:
    """An ephemeral llama.cpp server: started for the meeting, stopped after it. Source-built, never run here."""

    def __init__(self, binary, model, params, log=print):
        self.binary, self.model, self.params, self.log = str(binary), str(model), params, log
        self.process, self.port, self.calls, self.tokens = None, None, 0, dict(prompt=0, completion=0)

    def start(self, wait_seconds=600):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]
        command = [self.binary, '-m', self.model, '--host', '127.0.0.1', '--port', str(self.port),
                   '--ctx-size', str(int(self.params['context_size'])), '--threads', str(int(self.params['threads'])),
                   '--parallel', '1', '--log-disable']
        self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('llama-server exited while starting: %s' % self.process.stderr.read().decode(errors='replace')[-2000:])
            try:
                with urllib.request.urlopen('http://127.0.0.1:%d/health' % self.port, timeout=5) as response:
                    if json.loads(response.read()).get('status') == 'ok':
                        return
            except (urllib.error.URLError, TimeoutError, ValueError, ConnectionError):
                pass
            time.sleep(2)
        self.stop()
        raise RuntimeError('llama-server did not report healthy within %d s' % wait_seconds)

    def chat(self, messages, schema):
        body = dict(messages=messages, temperature=self.params['temperature'], top_p=self.params['top_p'],
                    max_tokens=int(self.params['max_output_tokens_per_turn']),
                    response_format=dict(type='json_schema', json_schema=dict(name='coordinator_turn', schema=schema)),
                    stream=False)
        request = urllib.request.Request('http://127.0.0.1:%d/v1/chat/completions' % self.port,
                                         data=json.dumps(body).encode(), method='POST',
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=600) as response:
            reply = json.loads(response.read())
        self.calls += 1
        usage = reply.get('usage') or {}
        self.tokens['prompt'] += int(usage.get('prompt_tokens') or 0)
        self.tokens['completion'] += int(usage.get('completion_tokens') or 0)
        return reply['choices'][0]['message']['content']

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None


# ------------------------------------------------------------------------------------------ the meeting
def system_prompt(charter_text, rules_ids):
    return (charter_text + '\n\n## Output contract (code-enforced)\n'
            'Reply with ONE JSON object: {"item_id", "action", "seat", "text", "cites", "binds_to"}. action is one of '
            '%s. ASK names the seat whose OWN statement you want clarified. REQUEST_TEST names seat scientific_teacher and '
            'binds_to an existing proposal_id, claim_id or listed untested text of the item. NOTE_* records an agreement, '
            'disagreement or scope mismatch between seats using only their own words and values. LEAVE_OPEN ends the item '
            'with what stays open. RESOLVED is accepted only when the seats\' own records already resolve it. Every number '
            'you write must appear in a seat\'s turn and be listed in cites with that file\'s sha256. You never calculate, '
            'pool, average, forecast, trade, grade, confirm, promote or select. Classroom rules in force: %s.'
            % (list(ACTIONS), ', '.join(rules_ids)))


def discuss_item(server, item, system, params, log):
    """One item: rounds of coordinator turn -> code validation -> code seat answer, until LEAVE_OPEN/RESOLVED or budget."""
    turns_by_seat = {t['seat']: t for t in item['voiced']}
    coordinator, answers, requests, notes, refused = [], [], [], [], []
    outcome = None
    transcript = [dict(role='system', content=system),
                  dict(role='user', content=json.dumps(dict(item={k: item[k] for k in ('item_id', 'author', 'author_label',
                                                                                        'claim', 'voiced', 'records',
                                                                                        'open_items')},
                                                            instruction='Begin with this item. One action per reply.'),
                                                       sort_keys=True))]
    for round_number in range(1, int(params['max_coordinator_turns_per_item']) + 1):
        raw = server.chat(transcript, ACTION_SCHEMA)
        try:
            value = json.loads(raw)
        except ValueError as error:
            refused.append(dict(round=round_number, raw=raw[:2000], reason='not one JSON object (%s)' % error))
            transcript.append(dict(role='assistant', content=raw))
            transcript.append(dict(role='user', content='Refused by code: not one JSON object. Reply again with one object.'))
            continue
        action, why = validate_action(value, item, turns_by_seat)
        transcript.append(dict(role='assistant', content=raw))
        if action is None:
            refused.append(dict(round=round_number, turn=value, reason=why))
            transcript.append(dict(role='user', content='Refused by code: %s. Reply again within the contract.' % why))
            continue
        action['round'] = round_number
        coordinator.append(action)
        if action['action'] == 'ASK':
            answer = seat_answer(action['seat'], item)
            answer['round'] = round_number
            answers.append(answer)
            transcript.append(dict(role='user', content=json.dumps(dict(code_seat_answer=answer), sort_keys=True)))
        elif action['action'] == 'REQUEST_TEST':
            request = dict(schema=REQUEST_SCHEMA, item_id=item['item_id'], round=round_number, seat='scientific_teacher',
                           binds_to=action['binds_to'], text=action['text'], status='requested_not_run',
                           rule='executed only by the proper code stage; Granite never fabricates the answer')
            requests.append(request)
            transcript.append(dict(role='user', content=json.dumps(dict(recorded=request), sort_keys=True)))
        elif action['action'].startswith('NOTE_'):
            notes.append(dict(round=round_number, kind=action['action'], text=action['text'], cites=action['cites']))
            transcript.append(dict(role='user', content='Recorded (coordination only, never evidence). Continue.'))
        else:
            outcome = action['action']
            break
    open_items = list(item['open_items'])
    if outcome is None:
        outcome = 'LEFT_OPEN_BY_CODE'
        open_items.append(dict(kind='turn_budget', seat=None, binds_to=None,
                               text='the coordinator turn budget of %d was spent without LEAVE_OPEN/RESOLVED; the item stays '
                                    'open by code' % int(params['max_coordinator_turns_per_item'])))
    return dict(item_id=item['item_id'], author=item['author'], seat_statements=item['voiced'],
                coordinator_turns=coordinator, code_seat_answers=answers, notes=notes, requested_tests=requests,
                open_items=open_items, refused=refused, outcome=outcome,
                rule='four categories kept apart; agreement among voices is never confirmation (R17)')


def meeting(exchange_path, out_dir, *, config_path=CONFIG, binary=None, model=None, brain=None, inputs_only=False,
            log=print):
    import frankie_box_classroom_code as K
    from frankie_box_durable import write_json
    exchange_path, out_dir = Path(exchange_path), Path(out_dir)
    raw = exchange_path.read_bytes()
    exchange = json.loads(raw)
    if exchange.get('schema') != 'FRANKIE_EXPERIMENT_EXCHANGE_V1' or exchange.get('view') != 'frankie':
        raise SystemExit('the meeting is given Frankie\'s view of the exchange only (view frankie)')
    config, config_witness = load_config(config_path)
    _, rules = K.rules()
    rules_witness = dict(file=Path(rules['path']).name, sha256=rules['sha256'], bytes=rules['bytes'], rules=rules['rules'])
    knowledge_index = []
    if brain:
        import frankie_box_lane_state as LS
        selected = LS.learner_knowledge(str(exchange['day']), 'voice', brain=brain)
        knowledge_index = [{k: d[k] for k in ('label', 'day', 'kind', 'path', 'sha256')} for d in selected['documents']]
    given = meeting_input(exchange, knowledge_index)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / 'meeting-input.json', given)
    started = time.time()
    base = dict(schema=SCHEMA, day=exchange.get('day'), run=exchange.get('run'),
                exchange=dict(path=str(exchange_path), sha256=sha256_bytes(raw), exchange_hash=exchange.get('exchange_hash')),
                charter=given['charter'], rules=rules_witness, runtime_config=config_witness,
                coordinator=dict(label=COORDINATOR_LABEL, model_identity=config['settled']['model_identity'],
                                 quantization=config['settled']['quantization'], runtime=config['settled']['runtime']),
                knowledge_index=knowledge_index)
    refusals = gate(config, binary, model)
    if inputs_only or refusals:
        record = dict(base, status='inputs_only' if inputs_only else 'refused', refused_to_run=refusals,
                      items=[], model_calls=0, publication='none')
        write_json(out_dir / 'meeting.json', record)
        receipt = dict(schema=RECEIPT_SCHEMA, day=exchange.get('day'), status=record['status'], refused_to_run=refusals,
                       inputs=witness_file(out_dir / 'meeting-input.json'), record=witness_file(out_dir / 'meeting.json'),
                       model_calls=0, seconds=round(time.time() - started, 1))
        write_json(out_dir / 'receipt.json', receipt)
        log('meeting %s: %s (%s)' % (exchange.get('day'), record['status'], '; '.join(refusals) or 'inputs written'))
        return receipt
    params = config['proposed_runtime_parameters']
    server = LlamaServer(binary, model, params, log=log)
    server.start()
    items, not_discussed = [], []
    deadline = time.monotonic() + float(params['max_meeting_seconds'])
    try:
        system = system_prompt(CHARTER.read_text(encoding='utf-8'), rules_witness['rules'])
        for item in given['items']:
            if time.monotonic() > deadline:
                not_discussed.append(dict(item_id=item['item_id'], reason='meeting time budget of %s s spent; the item '
                                          'keeps its code-seeded open items' % params['max_meeting_seconds'],
                                          open_items=item['open_items']))
                continue
            items.append(discuss_item(server, item, system, params, log))
    finally:
        server.stop()
    record = dict(base, status='complete', items=items, not_discussed=not_discussed,
                  runtime=dict(binary=witness_file(binary), model=witness_file(model), parameters=params),
                  model_calls=server.calls, tokens=server.tokens, seconds=round(time.time() - started, 1),
                  counts=dict(items=len(items), coordinator_turns=sum(len(i['coordinator_turns']) for i in items),
                              code_seat_answers=sum(len(i['code_seat_answers']) for i in items),
                              requested_tests=sum(len(i['requested_tests']) for i in items),
                              open_items=sum(len(i['open_items']) for i in items),
                              refused=sum(len(i['refused']) for i in items), not_discussed=len(not_discussed)),
                  publication='retained; brain kind meeting has no writer yet (frankie_box_brain.py, Codex); '
                              'immediate filing follows that edit',
                  rule='coordination only; the seats\' records are the evidence; nothing open is dropped (role V2)')
    write_json(out_dir / 'meeting.json', record)
    receipt = dict(schema=RECEIPT_SCHEMA, day=exchange.get('day'), status='complete',
                   inputs=witness_file(out_dir / 'meeting-input.json'), record=witness_file(out_dir / 'meeting.json'),
                   counts=record['counts'], model_calls=record['model_calls'], tokens=record['tokens'],
                   publication=record['publication'], seconds=record['seconds'])
    write_json(out_dir / 'receipt.json', receipt)
    log('meeting %s: %d items, %d coordinator turns, %d requested tests, %d model calls' % (
        exchange.get('day'), len(items), record['counts']['coordinator_turns'], record['counts']['requested_tests'],
        record['model_calls']))
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--exchange', required=True, help='exchange-frankie.json of the day (FRANKIE_EXPERIMENT_EXCHANGE_V1, view frankie)')
    p.add_argument('--out-dir', required=True)
    p.add_argument('--config', default=str(CONFIG))
    p.add_argument('--binary', help='llama-server binary (pinned by sha256 in the config)')
    p.add_argument('--model', help='the Granite GGUF file (pinned by sha256 in the config)')
    p.add_argument('--brain', help='the plan brain: accumulated knowledge is listed by label and hash for the coordinator')
    p.add_argument('--inputs-only', action='store_true', help='write what Granite would be given; zero model calls')
    a = p.parse_args()
    if not a.inputs_only and not (a.binary and a.model):
        p.error('--binary and --model are required unless --inputs-only')
    receipt = meeting(a.exchange, a.out_dir, config_path=a.config, binary=a.binary, model=a.model, brain=a.brain,
                      inputs_only=a.inputs_only)
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
