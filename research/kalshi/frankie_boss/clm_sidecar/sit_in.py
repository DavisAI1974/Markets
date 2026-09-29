"""Jev, the blind outside student in the experiment (Greg, 2026-09-29: "yes, include him").

Spec: research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md, section "Jev". Runs on Jev's OWN Pod (Qwen3-8B
chat, JEV_CHAT_URL), on the three classroom-arm days of the experiment only. Jev is NOT one of the three classroom seats
and never speaks in the classroom (rule R17). No Granite call of any kind: Frankie is code, and his answers are read
from his classroom files, never asked for.

One day, in this order (the blind wall is enforced here, not only by the relay):
  1. MATERIAL: the day's JEV_DAY_MATERIAL_V1 bundle (the classroom package and the search's survivor list so far,
     written by deploy/aws/box/frankie_box_jev_relay.sh ACTION=material). A day not declared discovery is refused (R15).
  2. STUDENT: Jev reads the material whole (in note packs when it is longer than one prompt, nothing cut) and files
     CLAIMS only, labelled as his: mechanisms, novel findings, and tests to run next, each naming the series, cells,
     condition, lag, target and the numbers from the material it rests on. No grades, no corrections, no teaching.
  3. FILE: the claims go up as JEV_CLAIMS_V1 (sha256 recorded, filed_at stamped) BEFORE anything of Frankie's is read.
     The scientific teacher (the experiment's search) tests every claim like Frankie's and reports counts; nothing
     here is a verdict (R11, R14).
  4. COMPARE: only after the claims are filed, Frankie's code-classroom outputs (JEV_FRANKIE_OUTPUTS_V1: his ledgers,
     classroom receipt and analysis, written by the relay ACTION=frankie) are read, and Jev lists where his claims and
     Frankie's findings agree, differ or contradict. Orientation for the search, never a result.
  5. REPORT: every claim individually, the comparison, and the counts (filed, unparsed, duplicates), plus the
     transcript and a receipt.
  6. BRAIN (Greg, 2026-09-29: "his outputs should go into his knowledge base in his brain too", "and his lessons from
     the teacher while he's learning"): his day is written to his brain as JEV_BRAIN_ENTRY_V1 (his claims whole, the
     material pins, what he carried in). On his next day every earlier entry is read whole, with the scientific
     teacher's lessons on those claims (JEV_LESSONS_V1: per claim, the tests run, the counts and days, the challenge
     "the data is showing this instead", the tests not yet run), so he learns from what the tests showed. A day whose
     lessons are not written yet is carried as "lessons pending". His brain NEVER carries Frankie's answers or the
     comparison: that would make his next claims lean on Frankie's and end their independence (the blind wall).

Nothing is cut (Greg): material longer than one Jev prompt is READ IN PIECES a little under the limit, every piece
into its own note, notes kept as MULTIPLE NOTE PACKS, every step run once per pack and every answer kept. A cut-off
answer (finish_reason length) is regenerated from its input in halves until whole. An answer that is not JSON is asked
again once and, if still not JSON, kept whole under "unparsed" (listed, never dropped). A claim repeated in the same
words is kept and marked duplicate_of (listed, not dropped). Progress is saved to STATE_PATH after every step, so a
restart picks up where it stopped. Oversize bundles arrive as JEV_FEED_PART_V1 parts over consecutive slots and are
joined and checked (sha256) here.
"""
import gzip
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request

JEV_CONTEXT = 32768
JEV_PIECE_CHARS = 54000          # one piece or note pack per Jev prompt: a little under the input room (~18k of 32,768 tokens)
JEV_PROMPT_CHARS = JEV_CONTEXT * 3
JEV_MODEL = 'Qwen3-8B'
STATE_PATH = os.environ.get('SIT_IN_STATE', '/workspace/jev-sit-in/state.json')
CLAIM_KINDS = ('mechanism', 'novel_finding', 'test_next')
CALLS = [0]                      # every Jev model call this process made (retries and note reading included)


class Incomplete(Exception):
    """The model stopped at its output bound (finish_reason length): the answer is cut and is regenerated."""


def log(*parts):
    print(time.strftime('%H:%M:%SZ', time.gmtime()), *parts, flush=True)


def get_json(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            return None
        raise


def put(url, data, content_type='application/octet-stream'):
    request = urllib.request.Request(url, data=data, method='PUT', headers={'Content-Type': content_type})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.status


def sha(data):
    return hashlib.sha256(data).hexdigest()


def jev(prompt):
    """Jev's own model: Qwen3-8B chat served on this Pod. Output = the remaining context; a cut-off answer raises Incomplete."""
    if len(prompt) > JEV_PROMPT_CHARS:
        raise ValueError('Jev prompt of %d chars does not fit; the caller reads it in pieces (nothing is cut)' % len(prompt))
    max_tokens = JEV_CONTEXT - len(prompt) // 3 - 256
    if max_tokens < 1024:
        raise Incomplete('no output room left for a %d-char prompt' % len(prompt))
    body = json.dumps(dict(model='jev', messages=[dict(role='user', content=prompt)],
                           temperature=0, max_tokens=max_tokens, chat_template_kwargs=dict(enable_thinking=False))).encode()
    request = urllib.request.Request(os.environ.get('JEV_CHAT_URL', 'http://127.0.0.1:8091/v1/chat/completions'),
                                     data=body, headers={'Content-Type': 'application/json'})
    CALLS[0] += 1
    with urllib.request.urlopen(request, timeout=900) as response:
        choice = json.loads(response.read())['choices'][0]
    if choice.get('finish_reason') == 'length':
        raise Incomplete('Jev stopped at %d output tokens' % max_tokens)
    return choice['message']['content']


def parse_json(text):
    match = re.search(r'\{.*\}', text or '', re.S)
    try:
        return json.loads(match.group(0)) if match else None
    except ValueError:
        return None


def pieces(text, size=JEV_PIECE_CHARS):
    """The whole text in pieces a little under the limit, cut on a line boundary where one is near."""
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = text.rfind('\n', start + size // 2, end)
            if cut > start:
                end = cut + 1
        out.append(text[start:end])
        start = end
    return out or ['']


def complete(make_prompt, piece, ask=None, depth=0):
    """Answers for one piece, every one complete: a cut-off answer is regenerated from the piece in halves (more room to
    answer), again, until each comes back whole. Returns the answers in order."""
    ask = ask or jev
    try:
        return [ask(make_prompt(piece))]
    except Incomplete as error:
        if len(piece) < 200 or depth >= 16:
            raise
        halves = pieces(piece, (len(piece) + 1) // 2)
        log('answer cut off (%s); regenerating from %d halves of %d chars' % (error, len(halves), len(piece)))
        return [a for half in halves for a in complete(make_prompt, half, ask, depth + 1)]


def notes(material, purpose):
    """Material as MULTIPLE NOTE PACKS, each a little under one Jev prompt. Material that fits is its own single pack;
    longer material is read piece by piece, every piece into its own note (complete, regenerated when cut), and the notes
    are packed in order; nothing is folded or shortened again."""
    text = material or ''
    if len(text) <= JEV_PIECE_CHARS:
        return [text]
    parts = pieces(text)
    written = []
    for number, piece in enumerate(parts, 1):
        for k, note in enumerate(complete(lambda p: (
                'You are Jev. Read piece %d of %d of the material below for this purpose: %s\nWrite notes that keep '
                'every number, name and relation that bears on it, in full; say what the piece covers.\n\nPIECE:\n%s'
                % (number, len(parts), purpose, p)), piece)):
            written.append('[note on piece %d/%d%s]\n%s' % (number, len(parts), '' if k == 0 else ', continued %d' % k, note))
    packs, current = [], ''
    for note in written:
        for chunk in pieces(note):
            if current and len(current) + len(chunk) + 2 > JEV_PIECE_CHARS:
                packs.append(current)
                current = ''
            current = chunk if not current else current + '\n\n' + chunk
    if current:
        packs.append(current)
    log('read %d chars in %d pieces -> %d note packs (%d chars of notes, none folded)' % (
        len(text), len(parts), len(packs), sum(len(p) for p in packs)))
    return packs


def json_asker():
    """A Jev call that wants a JSON object: an answer that is not JSON is asked again once, stated plainly; if it is still
    not JSON it is kept whole as {"raw": text} (listed as unparsed by the caller, never dropped)."""
    answers = []

    def ask(prompt):
        text = jev(prompt)
        value = parse_json(text)
        if value is None:
            text = jev(prompt + '\n\nYour previous answer was not JSON. Return the JSON object only.')
            value = parse_json(text)
        answers.append(text)
        return value if value is not None else dict(raw=text)
    return ask, answers


def save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH + '.tmp', 'w') as handle:
            json.dump(state, handle)
        os.replace(STATE_PATH + '.tmp', STATE_PATH)
    except OSError as error:
        log('state not saved:', error)


def load_state():
    try:
        with open(STATE_PATH) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def read_bundle(slots, schema):
    """The bundle in the first slot (joined from JEV_FEED_PART_V1 parts over consecutive slots, checked by sha256), or
    None while it has not fully landed."""
    first = get_json(slots[0]) if slots else None
    if first is None:
        return None
    if first.get('schema') == 'JEV_FEED_PART_V1':
        parts = [first]
        while len(parts) < first['parts']:
            if len(parts) >= len(slots):
                raise ValueError('bundle parts run past the slots')
            part = get_json(slots[len(parts)])
            if part is None:
                return None
            if (part.get('schema') != 'JEV_FEED_PART_V1' or part.get('sha256') != first['sha256']
                    or part.get('part') != len(parts) or part.get('parts') != first['parts']):
                raise ValueError('part %d out of order for bundle %s' % (len(parts), first['sha256']))
            parts.append(part)
        raw = ''.join(p['data'] for p in parts).encode()
        if sha(raw) != first['sha256'] or len(raw) != first['bytes']:
            raise ValueError('joined bundle differs from its sha256')
        first = json.loads(raw)
    if first.get('schema') != schema:
        raise ValueError('expected %s, got %s' % (schema, first.get('schema')))
    return first


def wait_bundle(slots, schema, seconds, poll):
    started = time.time()
    while True:
        bundle = read_bundle(slots, schema)
        if bundle is not None or time.time() - started >= seconds:
            return bundle
        time.sleep(poll)


def material_text(material):
    parts = ['===== CLASSROOM PACKAGE (%s, %s, sha256 %s) =====\n%s' % (
        material['material'].get('source'), material['material'].get('path'), material['material'].get('sha256'),
        json.dumps(material['material'].get('dipole_classroom'), sort_keys=True))]
    if material.get('survivors'):
        parts.append('===== SEARCH SURVIVORS SO FAR (%s, sha256 %s) =====\n%s' % (
            material['survivors'].get('path'), material['survivors'].get('sha256'),
            json.dumps(material['survivors'].get('list'), sort_keys=True)))
    for item in material.get('unavailable') or []:
        parts.append('===== NOT AVAILABLE: %s (%s) =====' % (item.get('item'), item.get('reason')))
    return '\n\n'.join(parts)


def load_brain(config, day):
    """Every earlier brain entry and every lessons file, whole, checked; returns (text for the student, pins)."""
    entries, lessons, pins = [], {}, []
    for item in config.get('brain') or []:
        raw = urllib.request.urlopen(item['url'], timeout=120).read()
        value = json.loads(raw)
        pins.append(dict(kind=item['kind'], key=item['key'], bytes=len(raw), sha256=sha(raw)))
        if item['kind'] == 'entries':
            if value.get('schema') != 'JEV_BRAIN_ENTRY_V1':
                raise ValueError('%s is not a JEV_BRAIN_ENTRY_V1' % item['key'])
            if value.get('day') == day:
                raise ValueError('%s is an entry for this same day %s: the same day is not run twice' % (item['key'], day))
            if value.get('include', True):
                entries.append(value)
        else:
            if value.get('schema') != 'JEV_LESSONS_V1':
                raise ValueError('%s is not a JEV_LESSONS_V1' % item['key'])
            lessons[value.get('claims_sha256')] = dict(value, key=item['key'])
    if not entries:
        return '', pins
    blocks = []
    for entry in sorted(entries, key=lambda e: (e.get('day'), e.get('filed_at') or 0)):
        taught = lessons.get(entry.get('claims_sha256'))
        by_claim = {r.get('claim_id'): r for r in (taught or {}).get('results') or []}
        lines = ['===== YOUR EARLIER DAY %s (%s): %d claims; the teacher\'s lessons: %s =====' % (
            entry.get('day'), entry.get('stamp'), len(entry.get('claims') or []),
            'written (%s)' % taught['key'] if taught else 'pending (not tested yet)')]
        for claim in entry.get('claims') or []:
            lines.append('CLAIM %s [%s]: %s' % (claim.get('id'), claim.get('kind'), json.dumps(
                {k: claim.get(k) for k in ('statement', 'series', 'cells', 'condition', 'lag', 'target', 'direction', 'evidence')},
                sort_keys=True)))
            result = by_claim.get(claim.get('id'))
            if result is not None:
                lines.append('  TEACHER\'S LESSON: %s' % json.dumps(result, sort_keys=True))
            elif taught:
                lines.append('  TEACHER\'S LESSON: none written for this claim (listed, not filled in)')
        for other in [r for r in (taught or {}).get('results') or [] if r.get('claim_id') not in
                      {c.get('id') for c in entry.get('claims') or []}]:
            lines.append('  TEACHER\'S LESSON on an unmatched claim id: %s' % json.dumps(other, sort_keys=True))
        blocks.append('\n'.join(lines))
    return ('===== YOUR BRAIN: your own earlier claims and what the scientific teacher\'s tests showed (never anyone '
            'else\'s answers) =====\n' + '\n\n'.join(blocks)), pins


def student_claims(day, text):
    """Jev's claims from the material, one JSON answer per note pack, every claim kept and labelled as his."""
    packs = notes(text, 'finding mechanisms, novel findings and tests to run in the dipole classroom material for the '
                        'natural gas trading day %s' % day)
    ask, raw = json_asker()
    answers = [a for number, pack in enumerate(packs, 1) for a in complete(lambda p: (
        'You are Jev, an independent student reading the Dipole classroom material for the natural gas trading day %s '
        '(pack %d of %d: the whole material, or notes read from every piece of it). You work alone: you have not seen '
        'anyone else\'s answer. File CLAIMS for a scientist to test on the data; you do not grade or teach. If the '
        'material carries YOUR BRAIN (your earlier claims and the teacher\'s lessons on them), learn from it: build on '
        'what held, and where the data showed something else, say what you now claim instead.\n'
        'Return JSON only: {"claims": [{"kind": "mechanism" | "novel_finding" | "test_next", "statement": "one '
        'falsifiable sentence", "series": ["the dipole components, pairs or survivor series it uses, by their names in '
        'the material"], "cells": ["where it should hold, e.g. a component, pair, session phase or side"], "condition": '
        '"when it applies", "lag": "the lead or lag, or null", "target": "what it predicts or explains", "direction": '
        '"the sign or relation claimed", "evidence": ["the numbers from the material it rests on, quoted"]}]}.\n'
        'Every claim must name its series and quote its numbers. A claim about a later outcome is a test_next, never a '
        'fact.\n\nMATERIAL:\n%s' % (day, number, len(packs), p)), pack, ask)]
    claims, unparsed, seen = [], [], {}
    for pack_number, answer in enumerate(answers, 1):
        if 'raw' in answer and len(answer) == 1:
            unparsed.append(dict(pack=pack_number, text=answer['raw']))
            continue
        items = answer.get('claims')
        if not isinstance(items, list):
            unparsed.append(dict(pack=pack_number, text=json.dumps(answer, sort_keys=True)))
            continue
        for item in items:
            if not isinstance(item, dict) or not str(item.get('statement') or '').strip():
                unparsed.append(dict(pack=pack_number, text=json.dumps(item, sort_keys=True)))
                continue
            statement = ' '.join(str(item['statement']).split())
            base = sha(('jev:%s:%s' % (day, statement)).encode())[:16]
            seen[base] = seen.get(base, 0) + 1
            claim = dict(item, id=base if seen[base] == 1 else '%s-%d' % (base, seen[base]), author='jev', model=JEV_MODEL,
                         day=day, pack=pack_number, statement=statement,
                         kind=item.get('kind') if item.get('kind') in CLAIM_KINDS else 'unstated:%s' % item.get('kind'),
                         duplicate_of=base if seen[base] > 1 else None)
            claims.append(claim)
    return claims, unparsed, raw


def compare(day, claims, frankie):
    """After the claims are filed: where Jev's claims and Frankie's code findings agree, differ or contradict."""
    files = frankie.get('files') or {}
    text = 'JEV CLAIMS (filed before Frankie was read):\n%s\n\nFRANKIE (his code classroom: ledgers, receipt, analysis):\n%s' % (
        json.dumps([dict(id=c['id'], kind=c['kind'], statement=c['statement'], series=c.get('series'),
                         direction=c.get('direction')) for c in claims], sort_keys=True),
        '\n\n'.join('===== %s (%s, sha256 %s) =====\n%s' % (name, f.get('path'), f.get('sha256'), f.get('text'))
                    for name, f in sorted(files.items())))
    packs = notes(text, 'comparing Jev\'s claims with Frankie\'s classroom findings for the trading day %s' % day)
    ask, raw = json_asker()
    verdicts = [v for pack in packs for v in complete(lambda p: (
        'You are Jev. Your claims were filed before you read Frankie\'s classroom findings. Compare them (below whole, or '
        'one pack of notes read from every piece). This is orientation for a scientist who will test both; it is not a '
        'verdict. Return JSON only: {"agree": [{"jev_claim_id": "..", "frankie": "the ledger entry or line", "why": ".."}], '
        '"differ": [{"jev_claim_id": "..", "frankie": "..", "how": ".."}], "contradict": [{"jev_claim_id": "..", '
        '"frankie": "..", "values": ["the numbers on each side"]}], "only_jev": [".."], "only_frankie": [".."]}.\n\n%s'
        % p), pack, ask)]
    return verdicts, raw


def main():
    config = get_json(os.environ['CONFIG_URL'])
    stamp, day = os.environ.get('STAMP', ''), os.environ['DAY']
    wait, poll = int(os.environ.get('WAIT_SECONDS', '21600')), int(os.environ.get('POLL_SECONDS', '60'))
    state = load_state() or {}
    if state.get('stamp') not in (None, stamp) or state.get('day') not in (None, day):
        state = {}                                   # another sit-in's progress: start fresh, never mix
    state.update(stamp=stamp, day=day)
    calls = lambda: state.get('model_calls_before_restart', 0) + CALLS[0]
    state['model_calls_before_restart'] = state.get('model_calls', 0)

    # 0. BRAIN: his earlier days and the teacher's lessons on them, whole (never Frankie's)
    brain_text, brain_pins = load_brain(config, day)
    log('brain: %d files carried (%d chars)' % (len(brain_pins), len(brain_text)))

    # 1. MATERIAL (never Frankie's)
    material = wait_bundle(config['material'], 'JEV_DAY_MATERIAL_V1', wait, poll)
    if material is None:
        raise SystemExit('no JEV_DAY_MATERIAL_V1 bundle within %d s' % wait)
    if material.get('day') != day or material.get('day_role') != 'discovery':
        raise SystemExit('material is for day %s (%s), this sit-in is day %s: refused (Jev runs on discovery days only, R15)'
                         % (material.get('day'), material.get('day_role'), day))
    log('material: %s bytes sha256 %s; survivors %s; unavailable %s' % (
        material['material'].get('bytes'), material['material'].get('sha256'),
        'yes' if material.get('survivors') else 'no', [u.get('item') for u in material.get('unavailable') or []]))

    # 2-3. STUDENT, then FILE the claims before anything of Frankie's is read
    if not state.get('claims_filed'):
        text = material_text(material) + ('\n\n' + brain_text if brain_text else '')
        claims, unparsed, raw = student_claims(day, text)
        filed_at = time.time()
        document = dict(schema='JEV_CLAIMS_V1', stamp=stamp, day=day, author='jev', model=JEV_MODEL, filed_at=filed_at,
                        blind=dict(frankie_read=False, statement='filed before any of Frankie\'s outputs were read'),
                        material=dict((k, material['material'].get(k)) for k in ('path', 'bytes', 'sha256', 'source')),
                        survivors=dict((k, (material.get('survivors') or {}).get(k)) for k in ('path', 'bytes', 'sha256'))
                        if material.get('survivors') else None,
                        unavailable=material.get('unavailable') or [], claims=claims, unparsed=unparsed,
                        counts=dict(claims=len(claims), unparsed=len(unparsed),
                                    duplicates=sum(1 for c in claims if c.get('duplicate_of')),
                                    by_kind={k: sum(1 for c in claims if c['kind'] == k) for k in sorted({c['kind'] for c in claims})}))
        data = json.dumps(document, sort_keys=True, indent=1).encode()
        log('claims filed -> HTTP %d (%d claims, %d unparsed)' % (put(config['claims'], data, 'application/json'),
                                                                  len(claims), len(unparsed)))
        state.update(claims_filed=dict(sha256=sha(data), bytes=len(data), at=filed_at), claims=claims, unparsed=unparsed,
                     student_raw=raw, model_calls=calls())
        save_state(state)
    claims = state['claims']

    # 4. COMPARE, only now (the blind wall: the claims are filed and pinned above)
    if not state.get('compared'):
        assert state.get('claims_filed'), 'the blind wall: Frankie is read only after the claims are filed'
        frankie = wait_bundle(config['frankie'], 'JEV_FRANKIE_OUTPUTS_V1', wait, poll)
        if frankie is None:
            comparison = dict(schema='JEV_COMPARISON_V1', stamp=stamp, day=day, available=False,
                              reason='no JEV_FRANKIE_OUTPUTS_V1 bundle within %d s' % wait)
        else:
            frankie_read_at = time.time()
            verdicts, raw = compare(day, claims, frankie)
            comparison = dict(schema='JEV_COMPARISON_V1', stamp=stamp, day=day, available=True, orientation_only=True,
                              claims_sha256=state['claims_filed']['sha256'], claims_filed_at=state['claims_filed']['at'],
                              frankie_read_at=frankie_read_at,
                              frankie_files={k: dict(path=v.get('path'), bytes=v.get('bytes'), sha256=v.get('sha256'))
                                             for k, v in (frankie.get('files') or {}).items()},
                              frankie_unavailable=frankie.get('unavailable') or [],
                              packs=verdicts, raw=raw,
                              agree=[x for v in verdicts for x in (v.get('agree') or [])],
                              differ=[x for v in verdicts for x in (v.get('differ') or [])],
                              contradict=[x for v in verdicts for x in (v.get('contradict') or [])],
                              only_jev=[x for v in verdicts for x in (v.get('only_jev') or [])],
                              only_frankie=[x for v in verdicts for x in (v.get('only_frankie') or [])],
                              unparsed=[v['raw'] for v in verdicts if 'raw' in v and len(v) == 1])
        data = json.dumps(comparison, sort_keys=True, indent=1).encode()
        log('comparison -> HTTP %d' % put(config['comparison'], data, 'application/json'))
        state.update(compared=comparison, model_calls=calls())
        save_state(state)
    comparison = state['compared']

    # 5. REPORT, transcript, receipt
    cell = lambda value: str(value).replace('|', '/').replace('\n', ' ')
    rows = ['| # | id | kind | statement | series | direction | evidence | duplicate of |', '|---|---|---|---|---|---|---|---|']
    for number, c in enumerate(claims, 1):
        rows.append('| %d | %s | %s | %s | %s | %s | %s | %s |' % (
            number, c['id'], c['kind'], cell(c['statement']), cell('; '.join(map(str, c.get('series') or []))),
            cell(c.get('direction')), cell('; '.join(map(str, c.get('evidence') or []))), c.get('duplicate_of') or ''))
    lines = ['# Jev, blind outside student: day %s (%s)' % (day, stamp), '',
             'Model %s on his own Pod; no Granite call. Claims filed %s, before Frankie was read (sha256 %s). Every claim '
             'is a CLAIM for the scientific teacher (the experiment\'s search) to test; search results: pending.' % (
                 JEV_MODEL, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(state['claims_filed']['at'])),
                 state['claims_filed']['sha256']), '',
             'Counts: %d claims, %d unparsed answers (kept whole below), %d repeated in the same words.' % (
                 len(claims), len(state.get('unparsed') or []), sum(1 for c in claims if c.get('duplicate_of'))),
             'Not available for this day: %s.' % (', '.join('%s (%s)' % (u.get('item'), u.get('reason'))
                                                             for u in material.get('unavailable') or []) or 'nothing'), '',
             '## Claims', ''] + rows + ['', '## Beside Frankie (orientation only, not a verdict)', '']
    if comparison.get('available'):
        for key in ('agree', 'differ', 'contradict', 'only_jev', 'only_frankie'):
            lines.append('- %s: %d' % (key, len(comparison.get(key) or [])))
            lines += ['  - %s' % cell(json.dumps(x, sort_keys=True)) for x in comparison.get(key) or []]
    else:
        lines.append('Frankie\'s classroom outputs not available: %s' % comparison.get('reason'))
    if state.get('unparsed'):
        lines += ['', '## Unparsed answers (kept whole)', ''] + ['### pack %s\n\n%s' % (u['pack'], u['text'])
                                                               for u in state['unparsed']]
    report = '\n'.join(lines) + '\n'
    log('report -> HTTP %d' % put(config['report'], report.encode(), 'text/markdown'))
    transcript = [dict(step='student', answers=state.get('student_raw')), dict(step='compare', answers=comparison.get('raw'))]
    put(config['transcript'], gzip.compress('\n'.join(json.dumps(t, sort_keys=True) for t in transcript).encode()))
    receipt = dict(schema='JEV_SIT_IN_RECEIPT_V1', stamp=stamp, day=day, model=JEV_MODEL, granite_calls=0,
                   jev_model_calls=calls(), claims=state['claims_filed'],
                   claims_count=len(claims), unparsed=len(state.get('unparsed') or []),
                   comparison_available=bool(comparison.get('available')),
                   report=dict(bytes=len(report.encode()), sha256=sha(report.encode())), status='done')
    # 6. BRAIN: this day's entry, his claims whole, never the comparison (the blind wall)
    if not state.get('brain_written'):
        entry = dict(schema='JEV_BRAIN_ENTRY_V1', stamp=stamp, day=day, author='jev', model=JEV_MODEL, include=True,
                     filed_at=state['claims_filed']['at'], claims_sha256=state['claims_filed']['sha256'],
                     claims=claims, unparsed=state.get('unparsed') or [],
                     material=dict((k, material['material'].get(k)) for k in ('path', 'bytes', 'sha256', 'source')),
                     unavailable=material.get('unavailable') or [], brain_carried=brain_pins,
                     lessons_key=config.get('lessons_key'), lessons='pending: the scientific teacher writes JEV_LESSONS_V1 '
                     'to lessons_key, bound to claims_sha256',
                     excluded=dict(comparison='never carried: his next claims must not lean on Frankie\'s answers'))
        data = json.dumps(entry, sort_keys=True, indent=1).encode()
        log('brain entry %s -> HTTP %d' % (config['brain_entry']['key'], put(config['brain_entry']['url'], data,
                                                                            'application/json')))
        state.update(brain_written=dict(key=config['brain_entry']['key'], sha256=sha(data), bytes=len(data)))
        save_state(state)
    receipt.update(brain_carried=len(brain_pins), brain_entry=state['brain_written'])
    log('receipt -> HTTP %d' % put(config['receipt'], json.dumps(receipt, sort_keys=True).encode(), 'application/json'))


if __name__ == '__main__':
    main()
