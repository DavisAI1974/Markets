"""Jev sits in with Frankie (Greg, 2026-09-28): two roles, talking with Frankie every few minutes, a report every 30 min.

Runs on Jev's Pod. Inputs arrive through one presigned config object (CONFIG_URL): the GET URLs of the box relay's
feed slots (clm-sidecar/<stamp>/feed/NNNN.json, written by deploy/aws/box/frankie_box_jev_relay.sh) and the PUT URLs
of the report slots and the transcript. Jev's own model is Qwen3-8B chat on this Pod (JEV_CHAT_URL). Frankie is Granite
on the reading Pods (GRANITE_PODS, never the BOSS Pod), asked through the same jobs_v1 protocol the box uses.

Each turn takes the next new thing Frankie produced (a classroom answer first, else the latest reading note):
  1. STUDENT (Jev): answers the same topic from the dipole classroom material alone, without seeing Frankie's answer;
  2. OBSERVER (Jev): compares the student and Frankie against the dipole material, as JSON (agree, disagreements,
     evidence, question_for_frankie);
  3. FRANKIE (Granite): answers the observer's question about his own answer;
  4. OBSERVER (Jev): closes the turn (settled or open, and why).
Every REPORT_MINUTES the report lists every turn individually (topic, agree, the disagreement, settled/open, the
question and Frankie's reply) plus a short synthesis. Nothing Jev writes goes into Frankie's session; Frankie's replies
to Jev are recorded here only. Rough by design; zero synthetic data (every input is the run's own material).

Nothing is cut (Greg, 2026-09-28): the dipole material, Frankie's answers, the queue and the report go whole. Jev's model
has a 32,768-token context, so anything longer than one Jev prompt is READ IN PIECES a little under the limit: every piece
becomes its own note, and the notes are kept as MULTIPLE NOTE PACKS each a little under the limit (never folded into
shorter notes). Every step then runs once per pack and every answer is kept. Jev's output is the remaining context; an
answer cut off by the model (finish_reason length) is REGENERATED from its input in halves, again, until every answer is
complete; the same for Frankie's replies. An observer answer that is not JSON is asked again. Every queued item is
discussed (classroom items first, then reading notes oldest first). The sit-in's progress (feed position, queue, turns,
the dipole material) is saved to STATE_PATH after every step and loaded at start, so a restart picks up where it stopped. Oversize relay bundles arrive as JEV_FEED_PART_V1
parts over consecutive slots and are joined and checked (sha256) here.
"""
import gzip
import hashlib
import http.client
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request

CONTEXT = 131072                 # Granite's only context; output = the remaining context (Greg, 2026-09-16)
JEV_CONTEXT = 32768
JEV_PIECE_CHARS = 54000          # one piece or note pack per Jev prompt: a little under the input room (~18k of 32,768 tokens)
JEV_PROMPT_CHARS = JEV_CONTEXT * 3
STATE_PATH = os.environ.get('SIT_IN_STATE', '/workspace/jev-sit-in/state.json')


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
    with urllib.request.urlopen(request, timeout=900) as response:
        choice = json.loads(response.read())['choices'][0]
    if choice.get('finish_reason') == 'length':
        raise Incomplete('Jev stopped at %d output tokens' % max_tokens)
    return choice['message']['content']


def frankie(prompt, pod):
    """Frankie = Granite on a reading Pod, jobs_v1 (POST /v1/jobs/<id>, poll, GET result). Output = remaining context."""
    key, model = os.environ['GRANITE_KEY'], os.environ.get('GRANITE_MODEL', 'granite42-smoke')
    max_tokens = max(1024, CONTEXT - len(prompt) // 3 - 512)
    body = json.dumps(dict(model=model, messages=[dict(role='user', content=prompt)], temperature=0, max_tokens=max_tokens,
                           stream=False, chat_template_kwargs=dict(enable_thinking=False)), sort_keys=True).encode()
    digest = hashlib.sha256(body).hexdigest()
    job = hashlib.sha256(('jev-sit-in:%s:%s' % (os.environ.get('STAMP', ''), digest)).encode()).hexdigest()

    def call(method, path, payload=b''):
        connection = http.client.HTTPSConnection(pod + '-8081.proxy.runpod.net', 443, timeout=80,
                                                 context=ssl.create_default_context())
        try:
            headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'Connection': 'close'}
            if method == 'POST':
                headers['X-Granite-Request-SHA256'] = digest
            connection.request(method, path, payload if method == 'POST' else None, headers)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    path = '/v1/jobs/' + job
    started = time.time()
    while time.time() - started < 3600:
        try:
            status, raw = call('GET', path)
            if status == 404:
                status, raw = call('POST', path, body)
                if status != 202:
                    return None, 'job create refused: HTTP %d %s' % (status, raw.decode('utf-8', errors='replace'))
            elif status == 200:
                state = json.loads(raw)
                if state.get('state') == 'completed':
                    status, raw = call('GET', path + '/result')
                    if status == 200:
                        result = json.loads(raw)
                        choice = (result.get('choices') or [{}])[0]
                        if choice.get('finish_reason') == 'length':
                            raise Incomplete('Frankie stopped at %d output tokens' % max_tokens)
                        return (choice.get('message') or {}).get('content'), None
                if state.get('state') in ('failed', 'ambiguous'):
                    return None, 'job ' + str(state.get('state'))
            elif status in (401, 403):
                return None, 'Granite credential refused (HTTP %d)' % status
        except (OSError, ValueError, http.client.HTTPException) as error:
            log('frankie call retry:', type(error).__name__)
        time.sleep(5)
    return None, 'no answer within an hour'


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


def each_pack(packs, make_prompt):
    """One complete answer (or more, when regenerated in halves) per pack; every answer kept, in order."""
    return [a for pack in packs for a in complete(make_prompt, pack)]


def observer_json():
    """The observer's JSON for one pack; an answer that is not JSON is asked again once, stated plainly."""
    answers = []
    def ask(p):
        text = jev(p)
        value = parse_json(text)
        if value is None:
            text = jev(p + '\n\nYour previous answer was not JSON. Return the JSON object only.')
            value = parse_json(text)
        answers.append(text)
        return value if value is not None else dict(raw=text)
    return ask, answers


def save_state(state):
    try:
        path = STATE_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + '.tmp', 'w') as handle:
            json.dump(state, handle)
        os.replace(path + '.tmp', path)
    except OSError as error:
        log('state not saved:', error)


def load_state():
    try:
        with open(STATE_PATH) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def join_bundle(first, feed, position):
    """A JEV_FEED_PART_V1 bundle: every part from consecutive slots, joined and checked; None until all have landed."""
    parts = [first]
    while len(parts) < first['parts']:
        if position + len(parts) >= len(feed):
            raise ValueError('bundle parts run past the feed slots')
        part = get_json(feed[position + len(parts)])
        if part is None:
            return None, 0
        if (part.get('schema') != 'JEV_FEED_PART_V1' or part.get('sha256') != first['sha256']
                or part.get('part') != len(parts) or part.get('parts') != first['parts']):
            raise ValueError('feed part %d out of order for bundle %s' % (len(parts), first['sha256']))
        parts.append(part)
    raw = ''.join(p['data'] for p in parts).encode()
    if hashlib.sha256(raw).hexdigest() != first['sha256'] or len(raw) != first['bytes']:
        raise ValueError('joined feed bundle differs from its sha256')
    return json.loads(raw), len(parts)


def is_classroom(item):
    name = (item.get('name') or '').lower()
    return item.get('kind') == 'classroom' or any(word in name for word in ('classroom', 'component', 'summary', 'science',
                                                                             'teach', 'observation', 'dipole'))


def main():
    config = get_json(os.environ['CONFIG_URL'])
    feed, reports, transcript_url = config['feed'], config['reports'], config['transcript']
    pods = [p for p in os.environ['GRANITE_PODS'].split(',') if p]
    discuss, report_every = int(os.environ.get('DISCUSS_SECONDS', '180')), int(os.environ.get('REPORT_MINUTES', '30')) * 60
    state = load_state() or {}
    if state.get('stamp') not in (None, os.environ.get('STAMP')):
        state = {}                                   # another sit-in's progress: start fresh, never mix
    dipole, queue, turns = state.get('dipole', ''), state.get('queue', []), state.get('turns', [])
    next_feed, report_index, final = state.get('next_feed', 0), state.get('report_index', 0), state.get('final', False)
    window_start, pod_turn, last_report = state.get('window_start', 0), state.get('pod_turn', 0), time.time()
    if state:
        log('resumed: feed %d, %d queued, %d turns, report %d' % (next_feed, len(queue), len(turns), report_index))

    def checkpoint():
        save_state(dict(stamp=os.environ.get('STAMP'), dipole=dipole, queue=queue, turns=turns, next_feed=next_feed,
                        report_index=report_index, final=final, window_start=window_start, pod_turn=pod_turn))

    while True:
        # 1. read every feed bundle the relay has written since the last pass
        while next_feed < len(feed):
            bundle, used = get_json(feed[next_feed]), 1
            if bundle is None:
                break
            if bundle.get('schema') == 'JEV_FEED_PART_V1':
                bundle, used = join_bundle(bundle, feed, next_feed)
                if bundle is None:
                    break                      # the remaining parts have not landed yet; read again next pass
            if bundle.get('dipole') and bundle['dipole'].get('dipole_classroom') is not None and not dipole:
                dipole = json.dumps(bundle['dipole']['dipole_classroom'])
                log('dipole material: %d chars (whole)' % len(dipole))
            for name, text in (bundle.get('classroom') or {}).items():
                queue.append(dict(kind='classroom', name=name, text=text or ''))
            for answer in bundle.get('answers') or []:
                if answer.get('text'):
                    queue.append(dict(kind='answer', name=answer.get('name'), text=answer['text']))
            log('feed %04d phase=%s queue=%d' % (next_feed, bundle.get('phase'), len(queue)))
            final = bundle.get('phase') in ('pushed', 'done', 'complete', 'completed', 'refused', 'failed', 'stopped')
            next_feed += used
            checkpoint()
        # 2. one discussion turn per item, every item: classroom first, then the reading notes oldest first
        item = next((q for q in queue if is_classroom(q)), None) or (queue[0] if queue else None)
        if item is not None:
            pod = pods[pod_turn % len(pods)]
            pod_turn += 1
            topic = item.get('name') or item['kind']
            frankie_text = item['text']
            turn = dict(at=time.time(), topic=topic, kind=item['kind'], pod=pod)
            try:
                purpose = 'the Dipole classroom topic "%s" for the Monday 2021-10-04 natural gas trading day' % topic
                material = notes(dipole, purpose) if dipole else ['(not received yet)']
                # STUDENT: one complete answer per material pack, every answer kept
                answers = each_pack(material, lambda pack: (
                    'You are Jev, a student in the Dipole classroom for the Monday 2021-10-04 natural gas trading day. '
                    'Topic: %s.\nAnswer it yourself from the dipole classroom material below (the whole material, or one '
                    'pack of notes read from every piece of it): what the dipole components and their pair relations show, '
                    'with the numbers you rely on.\n\nDIPOLE MATERIAL:\n%s' % (topic, pack)))
                turn['student'] = '\n\n'.join('[student answer %d/%d]\n%s' % (k, len(answers), a)
                                                for k, a in enumerate(answers, 1))
                # OBSERVER: the three texts whole in one comparison document, as note packs; one JSON per pack
                comparison = notes('STUDENT:\n%s\n\nFRANKIE:\n%s\n\nDIPOLE MATERIAL:\n%s' % (
                    turn['student'], frankie_text, '\n\n'.join(material)),
                    'comparing the STUDENT and FRANKIE answers against the DIPOLE MATERIAL on ' + purpose)
                ask, raw = observer_json()
                verdicts = [v for pack in comparison for v in complete(lambda p: (
                    'You are Jev, the classroom observer. Compare the STUDENT answer and FRANKIE\'s answer on the topic '
                    '"%s" against the DIPOLE MATERIAL (below whole, or one pack of notes read from every piece). Return JSON '
                    'only: {"agree": true|false, "disagreements": [..], "evidence": [..numbers from the material..], '
                    '"question_for_frankie": "one pointed question"}.\n\n%s' % (topic, p)), pack, ask)]
                questions = [v.get('question_for_frankie') for v in verdicts if v.get('question_for_frankie')]
                turn['observer'] = dict(agree=all(v.get('agree') is True for v in verdicts) if verdicts else None,
                                        disagreements=[d for v in verdicts for d in (v.get('disagreements') or [])],
                                        evidence=[d for v in verdicts for d in (v.get('evidence') or [])],
                                        question_for_frankie=' | '.join(questions), packs=verdicts, raw=raw)
                question = '\n'.join('%d. %s' % (k, q) for k, q in enumerate(questions, 1)) or \
                    'Which dipole evidence most supports your answer?'
                # FRANKIE: his whole answer and every question; a cut-off reply is regenerated from his answer in halves
                def ask_frankie(prompt):
                    text, error = frankie(prompt, pod)
                    if error:
                        raise RuntimeError(error)
                    return text
                replies = complete(lambda part: (
                    'You are Frankie, reviewing your own Dipole classroom answer for the Monday 2021-10-04 trading day with a '
                    'classroom observer. Your answer on "%s" (whole, or one part of it when it is long):\n%s\n\nThe observer '
                    'asks:\n%s\nAnswer directly, citing the dipole evidence; say plainly if you would change your answer.'
                    % (topic, part, question)), frankie_text, ask_frankie)
                turn['frankie_reply'] = '\n\n'.join('[Frankie reply %d/%d]\n%s' % (k, len(replies), r)
                                                      for k, r in enumerate(replies, 1))
                turn['frankie_error'] = None
                ask, raw = observer_json()
                closings = [v for pack in notes(turn['frankie_reply'], 'Frankie\'s reply to: ' + question)
                            for v in complete(lambda p: (
                                'You are Jev, the classroom observer. Frankie replied to your questions:\n%s\n\nHis reply '
                                '(whole, or one pack of notes read from every piece):\n%s\n\nReturn JSON only: '
                                '{"settled": true|false, "why": "one sentence"}.' % (question, p)), pack, ask)]
                turn['closing'] = dict(settled=all(c.get('settled') is True for c in closings) if closings else None,
                                       why=' | '.join(str(c.get('why')) for c in closings if c.get('why')), packs=closings, raw=raw)
            except Exception as error:  # noqa: BLE001  -- a failed turn is recorded, never hidden; the item stays queued
                turn['error'] = '%s: %s' % (type(error).__name__, error)
            turns.append(turn)
            if 'error' not in turn:
                queue = [q for q in queue if q is not item]
            else:
                queue = [q for q in queue if q is not item] + [item]      # tried again after the others, never dropped
            checkpoint()
            log('turn %d topic=%s agree=%s settled=%s' % (len(turns), topic, (turn.get('observer') or {}).get('agree'),
                                                         (turn.get('closing') or {}).get('settled')))
        # 3. the scheduled report, every REPORT_MINUTES, whole
        if time.time() - last_report >= report_every or (final and not queue):
            window = turns[window_start:]
            cell = lambda value: str(value).replace('|', '/').replace('\n', ' ')   # whole, one table line
            rows = ['| # | topic | kind | agree | settled | disagreements | question | Frankie replied |', '|---|---|---|---|---|---|---|---|']
            for number, turn in enumerate(window, window_start + 1):
                observer, closing = turn.get('observer') or {}, turn.get('closing') or {}
                rows.append('| %d | %s | %s | %s | %s | %s | %s | %s |' % (
                    number, cell(turn['topic']), turn['kind'], observer.get('agree'), closing.get('settled'),
                    cell('; '.join(str(d) for d in observer.get('disagreements') or [])),
                    cell(observer.get('question_for_frankie', '')),
                    'yes' if turn.get('frankie_reply') else cell(turn.get('frankie_error') or turn.get('error') or 'no')))
            table = '\n'.join(rows)
            syntheses = each_pack(notes(table, 'the classroom turns table for the operator summary'), lambda pack: (
                'Summarize for the operator what Jev learned in this window from the classroom turns below (the whole table, '
                'or one pack of notes read from every piece): where Jev and Frankie agree, where they differ, what stayed '
                'open, and what to look at next. Name turns by number.\n\n' + pack)) if window else ['No turns yet.']
            synthesis = '\n\n'.join(syntheses)
            report = '# Jev sit-in report %d (%s)\n\nFeed bundles read: %d. Turns this window: %d (total %d).\n\n%s\n\n## Turns\n\n%s\n' % (
                report_index, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), next_feed, len(window), len(turns),
                synthesis, table)
            if report_index < len(reports):
                log('report %d -> HTTP %d' % (report_index, put(reports[report_index], report.encode(), 'text/markdown')))
            else:
                log('report %d has no slot left (%d report slots); kept in the transcript and the saved state' % (
                    report_index, len(reports)))
                turns.append(dict(at=time.time(), kind='report', topic='report %d' % report_index, report=report))
            put(transcript_url, gzip.compress('\n'.join(json.dumps(t, sort_keys=True) for t in turns).encode()))
            report_index, window_start, last_report = report_index + 1, len(turns), time.time()
            checkpoint()
            if final and not queue:
                log('session final and nothing queued; sit-in ends')
                return
        time.sleep(discuss if item is None or not queue or 'error' in turns[-1] else 5)


if __name__ == '__main__':
    main()
