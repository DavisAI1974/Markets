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
has a 32,768-token context, so anything longer than one Jev prompt is READ IN PIECES: every piece of it becomes notes
(read_whole), notes are folded again until they fit, and the answer is written from the notes. Every queued item is
discussed (classroom items first, then reading notes oldest first). Oversize relay bundles arrive as JEV_FEED_PART_V1
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
JEV_PIECE_CHARS = 60000          # one piece of material per Jev prompt (~20k tokens of 32,768, room for the reply)


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


def jev(prompt, max_tokens=2048):
    """Jev's own model: Qwen3-8B chat served on this Pod."""
    if len(prompt) > JEV_CONTEXT * 3:
        raise ValueError('Jev prompt of %d chars does not fit; the caller reads it in pieces (nothing is cut)' % len(prompt))
    body = json.dumps(dict(model='jev', messages=[dict(role='user', content=prompt)],
                           temperature=0, max_tokens=max_tokens, chat_template_kwargs=dict(enable_thinking=False))).encode()
    request = urllib.request.Request(os.environ.get('JEV_CHAT_URL', 'http://127.0.0.1:8091/v1/chat/completions'),
                                     data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read())['choices'][0]['message']['content']


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
                        text = ((result.get('choices') or [{}])[0].get('message') or {}).get('content')
                        return text, None
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


def read_whole(material, purpose):
    """Every piece of material read by Jev into notes; notes folded until they fit one piece. Never truncated."""
    text = material or ''
    rounds = 0
    while len(text) > JEV_PIECE_CHARS:
        pieces = [text[i:i + JEV_PIECE_CHARS] for i in range(0, len(text), JEV_PIECE_CHARS)]
        notes = []
        for number, piece in enumerate(pieces, 1):
            notes.append('[piece %d/%d] ' % (number, len(pieces)) + jev(
                'You are Jev. Read piece %d of %d of the material below for this purpose: %s\nWrite notes that keep '
                'every number, name and relation that bears on it, in full; say what the piece covers.\n\nPIECE:\n%s'
                % (number, len(pieces), purpose, piece)))
        text = '\n\n'.join(notes)
        rounds += 1
        log('read %d chars in %d pieces (round %d) -> %d chars of notes' % (len(material or ''), len(pieces), rounds, len(text)))
    return text


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
    dipole, queue, turns, next_feed, report_index, final = '', [], [], 0, 0, False
    window_start, pod_turn, last_report = 0, 0, time.time()
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
        # 2. one discussion turn per item, every item: classroom first, then the reading notes oldest first
        item = next((q for q in queue if is_classroom(q)), None) or (queue[0] if queue else None)
        if item is not None:
            queue = [q for q in queue if q is not item]
            pod = pods[pod_turn % len(pods)]
            pod_turn += 1
            topic = item.get('name') or item['kind']
            frankie_text = item['text']
            turn = dict(at=time.time(), topic=topic, kind=item['kind'], pod=pod)
            try:
                purpose = 'the Dipole classroom topic "%s" for the Monday 2021-10-04 natural gas trading day' % topic
                material = read_whole(dipole, purpose) if dipole else '(not received yet)'
                turn['student'] = jev('You are Jev, a student in the Dipole classroom for the Monday 2021-10-04 natural gas '
                                      'trading day. Topic: %s.\nAnswer it yourself from the dipole classroom material below '
                                      '(read whole; notes where it was longer than one prompt): what the dipole components '
                                      'and their pair relations show, with the numbers you rely on.\n\nDIPOLE MATERIAL:\n%s'
                                      % (topic, material))
                # the three texts whole in one comparison document; read in pieces when it is longer than one prompt
                comparison = read_whole('STUDENT:\n%s\n\nFRANKIE:\n%s\n\nDIPOLE MATERIAL:\n%s' % (turn['student'], frankie_text, material),
                                        'comparing the STUDENT and FRANKIE answers against the DIPOLE MATERIAL on ' + purpose)
                observed = jev('You are Jev, the classroom observer. Compare the STUDENT answer and FRANKIE\'s answer on the '
                               'topic "%s" against the DIPOLE MATERIAL (below whole, or as notes read from every piece). '
                               'Return JSON only: {"agree": true|false, "disagreements": [..], "evidence": [..numbers from '
                               'the material..], "question_for_frankie": "one pointed question"}.\n\n%s' % (topic, comparison))
                turn['observer'] = parse_json(observed) or dict(raw=observed)
                question = turn['observer'].get('question_for_frankie') or 'Which dipole evidence most supports your answer?'
                turn['frankie_reply'], turn['frankie_error'] = frankie(
                    'You are Frankie, reviewing your own Dipole classroom answer for the Monday 2021-10-04 trading day '
                    'with a classroom observer. Your answer on "%s":\n%s\n\nThe observer asks: %s\nAnswer directly, '
                    'citing the dipole evidence; say plainly if you would change your answer.' % (topic, frankie_text, question), pod)
                closing = jev('You are Jev, the classroom observer. Frankie replied to your question "%s":\n%s\n\nReturn JSON '
                              'only: {"settled": true|false, "why": "one sentence"}.' % (question, read_whole(
                                  turn['frankie_reply'] or turn['frankie_error'] or '', 'Frankie\'s reply to: ' + question)))
                turn['closing'] = parse_json(closing) or dict(raw=closing)
            except Exception as error:  # noqa: BLE001  -- a failed turn is recorded, never hidden
                turn['error'] = '%s: %s' % (type(error).__name__, error)
            turns.append(turn)
            log('turn %d topic=%s agree=%s settled=%s' % (len(turns), topic, (turn.get('observer') or {}).get('agree'),
                                                         (turn.get('closing') or {}).get('settled')))
        # 3. the scheduled report, every REPORT_MINUTES
        if time.time() - last_report >= report_every or (final and not queue):
            window = turns[window_start:]
            rows = ['| # | topic | kind | agree | settled | disagreement | question | Frankie replied |', '|---|---|---|---|---|---|---|---|']
            for number, turn in enumerate(window, window_start + 1):
                observer, closing = turn.get('observer') or {}, turn.get('closing') or {}
                cell = lambda value: str(value).replace('|', '/').replace('\n', ' ')   # whole, one table line
                rows.append('| %d | %s | %s | %s | %s | %s | %s | %s |' % (
                    number, cell(turn['topic']), turn['kind'], observer.get('agree'), closing.get('settled'),
                    cell('; '.join(str(d) for d in observer.get('disagreements') or [])),
                    cell(observer.get('question_for_frankie', '')),
                    'yes' if turn.get('frankie_reply') else cell(turn.get('frankie_error') or turn.get('error') or 'no')))
            synthesis = jev('Summarize for the operator, in under 200 words, what Jev learned in this window from the '
                            'classroom turns below: where Jev and Frankie agree, where they differ, what stayed open, and '
                            'what to look at next. Name turns by number.\n\n' + read_whole(
                                '\n'.join(rows), 'the classroom turns table for the operator summary')) if window else 'No turns yet.'
            report = '# Jev sit-in report %d (%s)\n\nFeed bundles read: %d. Turns this window: %d (total %d).\n\n%s\n\n## Turns\n\n%s\n' % (
                report_index, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), next_feed, len(window), len(turns),
                synthesis, '\n'.join(rows))
            if report_index < len(reports):
                log('report %d -> HTTP %d' % (report_index, put(reports[report_index], report.encode(), 'text/markdown')))
            put(transcript_url, gzip.compress('\n'.join(json.dumps(t, sort_keys=True) for t in turns).encode()))
            report_index, window_start, last_report = report_index + 1, len(turns), time.time()
            if final and not queue:
                log('session final and nothing queued; sit-in ends')
                return
        time.sleep(discuss if item is None or not queue else 5)


if __name__ == '__main__':
    main()
