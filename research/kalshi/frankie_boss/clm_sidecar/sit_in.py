"""Jev, the blind outside student in the experiment (Greg, 2026-09-29: "yes, include him").

Spec: research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md, section "Jev". The Pod route is retired;
the CPU launcher/runtime is not yet wired. This client uses JEV_CHAT_URL on classroom-arm days. Jev is NOT one of the three classroom seats
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
restart reuses recorded replies and prepared uploads. A pending call with unknown completion refuses an automatic
retry. Run this client as a repository module so the shared durable writer is available. Oversize bundles arrive as JEV_FEED_PART_V1 parts over consecutive slots and are
joined and checked (sha256) here.
"""
import base64
import gzip
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

JEV_CONTEXT = 32768
JEV_PIECE_CHARS = 54000          # one piece or note pack per Jev prompt: a little under the input room (~18k of 32,768 tokens)
JEV_PROMPT_CHARS = JEV_CONTEXT * 3
JEV_MODEL = 'Qwen3-8B'
STATE_PATH = os.environ.get('SIT_IN_STATE', '/workspace/jev-sit-in/state.json')
CLAIM_KINDS = ('mechanism', 'novel_finding', 'test_next')
PROGRESS = None                  # required before model work; the current durable phase and replay cursor
LOCAL = None                    # explicit owner-local CPU adapter; absent preserves retained client behavior


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
    if LOCAL is not None:
        return LOCAL['put'](url, data)
    request = urllib.request.Request(url, data=data, method='PUT', headers={'Content-Type': content_type})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.status


def sha(data):
    return hashlib.sha256(data).hexdigest()


def jev(prompt):
    """Jev's configured chat endpoint. Recorded replies replay without another model call."""
    if LOCAL is None and len(prompt) > JEV_PROMPT_CHARS:
        raise ValueError('Jev prompt of %d chars does not fit; the caller reads it in pieces (nothing is cut)' % len(prompt))
    if LOCAL is not None:
        state = PROGRESS['state']
        key = sha(prompt.encode())
        counts = state.setdefault('token_counts', {})
        if key not in counts:
            counts[key] = LOCAL['count_tokens']([dict(role='user', content=prompt)])
            save_state(state)
        max_tokens = min(LOCAL['max_output_tokens'], JEV_CONTEXT - counts[key] - LOCAL['token_margin'])
    else:
        max_tokens = JEV_CONTEXT - len(prompt) // 3 - 256
    if max_tokens < (LOCAL['min_output_tokens'] if LOCAL is not None else 1024):
        raise Incomplete('no output room left for a %d-char prompt' % len(prompt))
    if LOCAL is None:
        payload = dict(model='jev', messages=[dict(role='user', content=prompt)], temperature=0,
                       max_tokens=max_tokens, chat_template_kwargs=dict(enable_thinking=False))
    else:
        payload = dict(messages=[dict(role='user', content=prompt)], temperature=0, max_tokens=max_tokens)
    body = json.dumps(payload).encode()
    reply = recorded_chat(body)
    value = json.loads(reply)
    choices = value.get('choices') if isinstance(value, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError('recorded Jev reply has no usable choices; original bytes retained')
    if LOCAL is not None and (value.get('usage') or {}).get('prompt_tokens') != counts[key]:
        raise ValueError('Jev server prompt usage differs from its exact template/token count; reply retained')
    choice = choices[0]
    if choice.get('finish_reason') == 'length':
        raise Incomplete('Jev stopped at %d output tokens' % max_tokens)
    message = choice.get('message')
    if not isinstance(message, dict) or not isinstance(message.get('content'), str):
        raise ValueError('recorded Jev reply has no text content; original bytes retained')
    return message['content']


def parse_json(text):
    match = re.search(r'\{.*\}', text or '', re.S)
    try:
        return json.loads(match.group(0)) if match else None
    except ValueError:
        return None


def pieces(text, size=None):
    """The whole text in pieces a little under the limit, cut on a line boundary where one is near."""
    size = JEV_PIECE_CHARS if size is None else size
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
    from deploy.aws.box.frankie_box_durable import write_json
    write_json(STATE_PATH, state)       # failure propagates before any subsequent model work or answer access


def load_state():
    path = Path(STATE_PATH)
    if not path.exists():
        return None
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError('retained Jev state is not an object; refused, never reset')
    return value


def bind_inputs(state, name, value):
    """Freeze actual selected contents before model work, including phases reconstructed on restart."""
    if name in state and state[name] != value:
        raise ValueError('retained Jev %s differs; an explicit successor is required' % name)
    if name not in state:
        state[name] = value
        save_state(state)


def begin_phase(state, phase):
    global PROGRESS
    state.setdefault('calls', {}).setdefault(phase, [])
    PROGRESS = dict(state=state, phase=phase, cursor=0)


def recorded_chat(body):
    """Durable pre-send intent, then whole response bytes. Unknown outcomes never trigger a repeated call.

    Replaying the deterministic note/claim traversal consumes retained replies in order; changed
    requests refuse. The intent records possibility of dispatch, not proof the server received it.
    """
    if PROGRESS is None:
        raise ValueError('Jev model work requires a bound durable phase')
    state, phase, cursor = PROGRESS['state'], PROGRESS['phase'], PROGRESS['cursor']
    calls = state['calls'][phase]
    body_text = body.decode('utf-8')
    if cursor < len(calls):
        call = calls[cursor]
        if call['request'] != body_text or call['request_sha256'] != sha(body):
            raise ValueError('retained Jev request differs at %s/%d' % (phase, cursor))
        if call['status'] != 'replied':
            raise ValueError('Jev %s/%d has an unresolved or failed request; retained evidence requires owner review, no retry'
                             % (phase, cursor))
        raw = base64.b64decode(call['response_base64'], validate=True)
        if sha(raw) != call['response_sha256'] or len(raw) != call['response_bytes']:
            raise ValueError('retained Jev response bytes differ')
    else:
        if LOCAL is not None:
            LOCAL['check_save']()
        call = dict(request=body_text, request_sha256=sha(body), status='pending', intent_at=time.time())
        calls.append(call)
        save_state(state)
        request = urllib.request.Request(os.environ.get('JEV_CHAT_URL', 'http://127.0.0.1:8091/v1/chat/completions'),
                                         data=body, headers={'Content-Type': 'application/json'})
        chunks = []
        try:
            if LOCAL is not None:
                raw = LOCAL['chat'](body)
            else:
                with urllib.request.urlopen(request, timeout=900) as response:
                    read_reply(response, chunks)
                raw = b''.join(chunks)
        except Exception as error:
            partial = getattr(error, 'partial', b'')
            if isinstance(partial, bytes) and partial:
                chunks.append(partial)
            if isinstance(error, urllib.error.HTTPError):
                try:
                    read_reply(error, chunks)
                except Exception as read_error:
                    partial = getattr(read_error, 'partial', b'')
                    if isinstance(partial, bytes) and partial:
                        chunks.append(partial)
                    call['error_body_read_failure'] = repr(read_error)
                finally:
                    error.close()
            partial = b''.join(chunks)
            call.update(status='failed', error=repr(error), observed_at=time.time(),
                        transport_evidence=getattr(error, 'evidence', None), possible_send=getattr(error, 'sent', None),
                        partial_base64=base64.b64encode(partial).decode('ascii'),
                        partial_bytes=len(partial), partial_sha256=sha(partial))
            save_state(state)
            raise
        call.update(status='replied', response_base64=base64.b64encode(raw).decode('ascii'),
                    response_sha256=sha(raw), response_bytes=len(raw), received_at=time.time())
        save_state(state)              # preserve even malformed/cut-off responses before interpretation
    PROGRESS['cursor'] += 1
    return raw


def read_reply(response, chunks):
    """Keep received chunks accessible even when a later read fails; never replace them with error prose."""
    while True:
        chunk = response.read1(65536)
        if not chunk:
            break
        chunks.append(chunk)
    length = response.headers.get('Content-Length')
    if length is not None and sum(map(len, chunks)) != int(length):
        raise ValueError('Jev reply body differs from declared Content-Length')


def end_phase():
    if PROGRESS['cursor'] != len(PROGRESS['state']['calls'][PROGRESS['phase']]):
        raise ValueError('Jev phase ended before every retained request was consumed')


def prepared_json(state, name, value=None):
    """Exact upload bytes retained before PUT; retries reuse the same bytes and timestamps."""
    if name not in state:
        if value is None:
            raise ValueError('missing prepared Jev artifact: ' + name)
        data = json.dumps(value, sort_keys=True, indent=1).encode()
        state[name] = dict(text=data.decode(), bytes=len(data), sha256=sha(data))
        save_state(state)
    saved = state[name]
    data = saved['text'].encode()
    if len(data) != saved['bytes'] or sha(data) != saved['sha256']:
        raise ValueError('prepared Jev artifact differs: ' + name)
    if value is not None and json.loads(data) != value:
        raise ValueError('prepared Jev artifact is not the supplied document: ' + name)
    return data


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


def material_parts(material):
    """The material's labelled sections, whole, in the order Jev reads them. Nothing is cut or summarized."""
    parts = [('classroom_package', '===== CLASSROOM PACKAGE (%s, %s, sha256 %s) =====\n%s' % (
        material['material'].get('source'), material['material'].get('path'), material['material'].get('sha256'),
        json.dumps(material['material'].get('dipole_classroom'), sort_keys=True)))]
    if material['material'].get('dipole_external') is not None:
        parts.append(('external_section',
                      '===== EXTERNAL SECTION: THE HISTORICAL DATA POINTS BESIDE THE 19 DIPOLE COLUMNS (same material, '
                      'sha256 %s) =====\n%s' % (material['material'].get('sha256'),
                                                 json.dumps(material['material']['dipole_external'], sort_keys=True))))
    if material['material'].get('experiment_directive') is not None:
        parts.append(('experiment_directive', '===== GOVERNED EXPERIMENT DIRECTIVE =====\n' +
                      json.dumps(material['material']['experiment_directive'], sort_keys=True)))
    if material['material'].get('shared_market_context') is not None:
        if LOCAL is None:
            raise ValueError('shared raw market context requires its governed owner-local CPU source binding')
        import frankie_box_adviser_market as AM
        parts.append(('shared_market_picture_at_original_cutoff',
                      '===== SHARED MARKET PICTURE AT THE ORIGINAL CUTOFF (NO ANSWERS OR GRADES) =====\n'
                      + AM.text(material['material']['shared_market_context'])))
    if material.get('survivors'):
        parts.append(('search_survivors', '===== SEARCH SURVIVORS SO FAR (%s, sha256 %s) =====\n%s' % (
            material['survivors'].get('path'), material['survivors'].get('sha256'),
            json.dumps(material['survivors'].get('list'), sort_keys=True))))
    for item in material.get('unavailable') or []:
        parts.append(('not_available:' + str(item.get('item')),
                      '===== NOT AVAILABLE: %s (%s) =====' % (item.get('item'), item.get('reason'))))
    return parts


def material_text(material):
    return '\n\n'.join(text for _, text in material_parts(material))


def material_use(material, student_text, brain_chars):
    """What reached Jev's student prompt, by section and size (one-day review record; no prompt content)."""
    parts = material_parts(material)
    shared = material['material'].get('shared_market_context')
    return dict(sections=[dict(section=label, chars=len(text)) for label, text in parts],
                brain_chars=brain_chars, student_text_chars=len(student_text), note_packs=len(pieces(student_text)),
                shared_market_picture=(None if shared is None else dict(
                    scope=shared.get('scope'), at=shared.get('at'), picture_sha256=shared.get('picture_sha256'),
                    dispositions=dict(coverage=shared.get('coverage'), read=shared.get('read')),
                    delivered='whole typed picture text with its scope, read and coverage dispositions, in the '
                              'student material; never answers, grades, claims or private reasoning')),
                withheld=['Frankie classroom outputs until the blind seal', 'the comparison from the brain entry'],
                rule='the whole material is read in note packs; nothing is cut; a prompt without output room refuses')


def load_brain(config, day):
    """Every selected entry and teacher lesson, whole; return actual consumed-byte witnesses.

    More than one lesson may concern the same claims under different circumstances. Preserve
    all of them; neither arrival order nor age chooses a winning lesson. The config's optional
    byte/hash witnesses are checked when supplied; legacy unpinned selections remain explicit.
    """
    entries, lessons, pins = [], [], []
    for item in config.get('brain') or []:
        raw = urllib.request.urlopen(item['url'], timeout=120).read()
        if (('bytes' in item and item['bytes'] != len(raw))
                or ('sha256' in item and item['sha256'] != sha(raw))):
            raise ValueError('%s differs from its selected brain bytes' % item['key'])
        value = json.loads(raw)
        pins.append(dict(kind=item['kind'], key=item['key'], bytes=len(raw), sha256=sha(raw),
                         selection_hash_bound='sha256' in item))
        if item['kind'] == 'entries':
            if value.get('schema') != 'JEV_BRAIN_ENTRY_V1':
                raise ValueError('%s is not a JEV_BRAIN_ENTRY_V1' % item['key'])
            if value.get('day') == day:
                raise ValueError('%s is an entry for this same day %s: the same day is not run twice' % (item['key'], day))
            if value.get('include', True):
                entries.append(dict(key=item['key'], content=value))
        elif item['kind'] == 'lessons':
            if value.get('schema') != 'JEV_LESSONS_V1':
                raise ValueError('%s is not a JEV_LESSONS_V1' % item['key'])
            lessons.append(dict(key=item['key'], content=value))
        else:
            raise ValueError('unknown Jev brain kind: %s' % item['kind'])
    blocks = []
    for saved in entries:
        entry = saved['content']
        taught = [t['key'] for t in lessons if t['content'].get('claims_sha256') == entry.get('claims_sha256')]
        blocks.append('===== YOUR ENTRY %s; matching teacher lessons: %s =====\n%s' % (
            saved['key'], json.dumps(taught) if taught else 'pending (not supplied)',
            json.dumps(entry, sort_keys=True)))
    entry_hashes = {e['content'].get('claims_sha256') for e in entries}
    for saved in lessons:
        lesson = saved['content']
        matched = lesson.get('claims_sha256') in entry_hashes
        blocks.append('===== TEACHER LESSON %s; matching carried entry: %s =====\n%s' % (
            saved['key'], 'present' if matched else 'not supplied; lesson retained with its own claims binding',
            json.dumps(lesson, sort_keys=True)))
    if not blocks:
        return '', pins
    return ('===== YOUR BRAIN: your own claims and their scientific-teacher lessons; every selected lesson retained. '
            'Older lessons stay available. Conflicts about the same thing require research; keep both accounts and '
            'their circumstances while unresolved. A checked partial replacement preserves unaffected knowledge. '
            'Age or a newer result alone never establishes replacement. =====\n' + '\n\n'.join(blocks)), pins


def student_claims(day, text):
    """Jev's claims from the material, one JSON answer per note pack, every claim kept and labelled as his."""
    packs = notes(text, 'finding mechanisms, novel findings and tests to run in the dipole classroom material for the '
                        'natural gas trading day %s' % day)
    ask, raw = json_asker()
    answers = [a for number, pack in enumerate(packs, 1) for a in complete(lambda p: (
        'You are Jev, an independent student reading the Dipole classroom material for the natural gas trading day %s '
        '(pack %d of %d: the whole material, or notes read from every piece of it). You work alone: you have not seen '
        'anyone else\'s answer. File CLAIMS for a scientist to test on the data; you do not grade or teach. If the '
        'material carries YOUR BRAIN (your earlier claims and all the teacher\'s lessons on them), use older lessons '
        'as well. For conflicting knowledge about the same thing, propose research into the circumstances and scope; '
        'keep both accounts while unresolved. A replacement can be partial and must preserve unaffected knowledge. '
        'A newer result alone does not establish replacement, and you cannot declare a claim scientifically checked.\n'
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


def main(config=None):
    config = get_json(os.environ['CONFIG_URL']) if config is None else config
    stamp, day = os.environ.get('STAMP', ''), os.environ['DAY']
    wait, poll = int(os.environ.get('WAIT_SECONDS', '21600')), int(os.environ.get('POLL_SECONDS', '60'))
    retained = load_state()
    state = {} if retained is None else retained
    if retained is not None and (state.get('schema') != 'JEV_SIT_IN_PROGRESS_V2' or 'inputs' not in state):
        raise ValueError('legacy Jev progress lacks the durable call/input binding; owner review required, never reset')
    if retained is not None and (state.get('stamp') != stamp or state.get('day') != day):
        raise ValueError('retained Jev progress belongs to another day/stamp; refused, never reset')
    state.update(schema='JEV_SIT_IN_PROGRESS_V2', stamp=stamp, day=day)
    calls = lambda: sum(c['status'] == 'replied' for records in state.get('calls', {}).values() for c in records)

    if LOCAL is not None:
        if retained is not None and 'cpu_owner' not in state:
            raise ValueError('legacy Jev state has no CPU owner; preserve it for explicit recovery')
        if retained is not None and state['cpu_owner'] != LOCAL['identity']:
            raise ValueError('retained Jev CPU owner differs; explicit recovery required')
        # First durable input binding below writes owner and complete inputs together.
        state['cpu_owner'] = LOCAL['identity']
        LOCAL['check_save']()

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

    def destination(url):
        # A refreshed presigned credential for the same object is transport, not new research input.
        parsed = urllib.parse.urlsplit(url)
        query = [(key, value) for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
                 if not key.lower().startswith('x-amz-') and key.lower() not in ('awsaccesskeyid', 'signature', 'expires')]
        return parsed._replace(query=urllib.parse.urlencode(sorted(query)), fragment='').geturl()

    targets = {key: [destination(url) for url in config[key]] for key in ('material', 'frankie')}
    targets.update({key: destination(config[key]) for key in ('claims', 'comparison', 'report', 'transcript', 'receipt')})
    targets['brain_entry'] = dict(key=config['brain_entry']['key'], url=destination(config['brain_entry']['url']))
    targets['lessons_key'] = config.get('lessons_key')
    bind_inputs(state, 'inputs', dict(day=day, stamp=stamp, material=material, brain_text=brain_text,
        brain_pins=brain_pins, targets=targets, client_sha256=sha(Path(__file__).read_bytes()),
        chat_endpoint=destination(os.environ.get('JEV_CHAT_URL', 'http://127.0.0.1:8091/v1/chat/completions')),
        model=JEV_MODEL, context=JEV_CONTEXT, piece_chars=JEV_PIECE_CHARS, prompt_chars=JEV_PROMPT_CHARS))

    # 2-3. STUDENT, then FILE the claims before anything of Frankie's is read
    if 'prepared_claims' not in state:
        if state.get('claims_filed'):
            raise ValueError('claims were filed without their retained exact bytes; refused')
        begin_phase(state, 'student')
        text = material_text(material) + ('\n\n' + brain_text if brain_text else '')
        claims, unparsed, raw = student_claims(day, text)
        end_phase()
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
        state.update(claims=claims, unparsed=unparsed, student_raw=raw, model_calls=calls())
        prepared_json(state, 'prepared_claims', document)
    data = prepared_json(state, 'prepared_claims')
    document = json.loads(data)
    if (document.get('schema') != 'JEV_CLAIMS_V1' or document.get('day') != day
            or document.get('stamp') != stamp or document.get('claims') != state.get('claims')
            or document.get('unparsed') != state.get('unparsed')
            or document.get('blind', {}).get('frankie_read') is not False):
        raise ValueError('prepared Jev claims do not match their bound blind state')
    seal = dict(sha256=sha(data), bytes=len(data), at=document['filed_at'])
    if not state.get('claims_filed'):
        log('claims filed -> HTTP %d (%d claims, %d unparsed)' % (put(config['claims'], data, 'application/json'),
                                                                  len(document['claims']), len(document['unparsed'])))
        state.update(claims_filed=seal, model_calls=calls())
        save_state(state)
    if state['claims_filed'] != seal:
        raise ValueError('filed Jev seal does not name the prepared claims; Frankie remains unread')
    if LOCAL is not None:
        LOCAL['seal'](data, state)  # consuming-owner readback before any Frankie access
        LOCAL['check_save']()
    claims = state['claims']

    # 4. COMPARE, only now (the blind wall: the claims are filed and pinned above)
    if 'prepared_comparison' not in state:
        if state.get('compared'):
            raise ValueError('comparison lacks retained prepared bytes; refused')
        frankie = (LOCAL['frankie']() if LOCAL is not None else
                   wait_bundle(config['frankie'], 'JEV_FRANKIE_OUTPUTS_V1', wait, poll))
        if frankie is None:
            if 'frankie_input' in state:
                raise ValueError('selected Frankie comparison material is missing; retained model work is not discarded')
            comparison = dict(schema='JEV_COMPARISON_V1', stamp=stamp, day=day, available=False,
                              reason='no JEV_FRANKIE_OUTPUTS_V1 bundle within %d s' % wait)
        else:
            if frankie.get('day') != day:
                raise ValueError('Frankie comparison material belongs to another day')
            bind_inputs(state, 'frankie_input', frankie)
            if 'frankie_read_at' not in state:
                state['frankie_read_at'] = time.time()
                save_state(state)
            frankie_read_at = state['frankie_read_at']
            begin_phase(state, 'comparison')
            verdicts, raw = compare(day, claims, frankie)
            end_phase()
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
        prepared_json(state, 'prepared_comparison', comparison)
    data = prepared_json(state, 'prepared_comparison')
    comparison = json.loads(data)
    if not state.get('compared'):
        log('comparison -> HTTP %d' % put(config['comparison'], data, 'application/json'))
        state.update(compared=comparison, model_calls=calls())
        save_state(state)
    if state['compared'] != comparison:
        raise ValueError('retained comparison does not match its prepared bytes')
    comparison = state['compared']

    # 5. REPORT, transcript, receipt
    cell = lambda value: str(value).replace('|', '/').replace('\n', ' ')
    rows = ['| # | id | kind | statement | series | direction | evidence | duplicate of |', '|---|---|---|---|---|---|---|---|']
    for number, c in enumerate(claims, 1):
        rows.append('| %d | %s | %s | %s | %s | %s | %s | %s |' % (
            number, c['id'], c['kind'], cell(c['statement']), cell('; '.join(map(str, c.get('series') or []))),
            cell(c.get('direction')), cell('; '.join(map(str, c.get('evidence') or []))), c.get('duplicate_of') or ''))
    lines = ['# Jev, blind outside student: day %s (%s)' % (day, stamp), '',
             'Model %s through Jev\'s configured endpoint; no Granite call. Claims filed %s, before Frankie was read (sha256 %s). Every claim '
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
    put(config['transcript'], gzip.compress('\n'.join(json.dumps(t, sort_keys=True) for t in transcript).encode(), mtime=0))
    receipt = dict(schema='JEV_SIT_IN_RECEIPT_V1', stamp=stamp, day=day, model=JEV_MODEL, granite_calls=0,
                   jev_model_calls=calls(), claims=state['claims_filed'],
                   call_accounting=dict(completed_replies=calls(),
                       intents_without_reply=sum(c['status'] != 'replied' for records in state.get('calls', {}).values() for c in records),
                       rule='counts span retained phases and retries; an intent alone is not proof of dispatch'),
                   claims_count=len(claims), unparsed=len(state.get('unparsed') or []),
                   comparison_available=bool(comparison.get('available')),
                   report=dict(bytes=len(report.encode()), sha256=sha(report.encode())), status='done')
    # One-day review record (Greg, 2026-10-07): what this piece received, how it used it, what it produced.
    student_text = material_text(material) + ('\n\n' + brain_text if brain_text else '')
    receipt['workflow_report'] = dict(
        schema='FRANKIE_PIECE_WORKFLOW_REPORT_V1', piece='jev_sit_in',
        inputs=dict(material=dict((k, material['material'].get(k)) for k in ('path', 'bytes', 'sha256', 'source')),
                    material_sections=[label for label, _ in material_parts(material)],
                    unavailable=material.get('unavailable') or [], brain_files=len(brain_pins),
                    shared_market_picture=(material['material'].get('shared_market_context') or {}).get('scope')),
        use=dict(material_text=material_use(material, student_text, len(brain_text)),
                 model=JEV_MODEL, context=JEV_CONTEXT, piece_chars=JEV_PIECE_CHARS, prompt_chars=JEV_PROMPT_CHARS,
                 local_cpu=LOCAL is not None, model_calls=receipt['call_accounting'],
                 comparison=dict(available=bool(comparison.get('available')), reason=comparison.get('reason'),
                                 read_after_seal=bool(state.get('frankie_read_at'))),
                 caps='no output room or a length-stopped reply raises Incomplete and is retained; nothing is cut'),
        outputs=dict(claims=state['claims_filed'], claims_count=len(claims), unparsed=len(state.get('unparsed') or []),
                     report=receipt['report'], transcript='put to the configured transcript target',
                     comparison_prepared='prepared_comparison' in state, brain_entry='written below',
                     waits=[] if comparison.get('available') else ['comparison unavailable: ' + str(comparison.get('reason'))]),
        rule='recorded inputs, use and outputs for the one-day review; reaching the prompt is not proof of learning; '
             'missing evidence means unknown, never zero')
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
    return receipt


if __name__ == '__main__':
    main()
