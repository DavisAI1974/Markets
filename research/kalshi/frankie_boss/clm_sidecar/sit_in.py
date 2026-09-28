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
DIPOLE_CHARS = 60000             # the dipole material each Jev prompt carries (Qwen3-8B context)
ANSWER_CHARS = 20000


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
    body = json.dumps(dict(model='jev', messages=[dict(role='user', content=prompt[:JEV_CONTEXT * 3])],
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
                    return None, 'job create refused: HTTP %d %s' % (status, raw[:200])
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
            bundle = get_json(feed[next_feed])
            if bundle is None:
                break
            if bundle.get('dipole') and bundle['dipole'].get('dipole_classroom') is not None:
                dipole = json.dumps(bundle['dipole']['dipole_classroom'])[:DIPOLE_CHARS]
                log('dipole material: %d chars' % len(dipole))
            for name, text in (bundle.get('classroom') or {}).items():
                queue.append(dict(kind='classroom', name=name, text=text or ''))
            for answer in bundle.get('answers') or []:
                if answer.get('text'):
                    queue.append(dict(kind='answer', name=answer.get('name'), text=answer['text']))
            log('feed %04d phase=%s queue=%d' % (next_feed, bundle.get('phase'), len(queue)))
            final = bundle.get('phase') in ('pushed', 'done', 'complete', 'completed', 'refused', 'failed', 'stopped')
            next_feed += 1
        # 2. one discussion turn on the most useful new item: classroom first, else the latest reading note
        item = next((q for q in queue if is_classroom(q)), None) or (queue[-1] if queue else None)
        if item is not None:
            queue = [q for q in queue if q is not item and is_classroom(q)]   # only the newest reading note is discussed
            pod = pods[pod_turn % len(pods)]
            pod_turn += 1
            topic = item.get('name') or item['kind']
            frankie_text = item['text'][:ANSWER_CHARS]
            turn = dict(at=time.time(), topic=topic, kind=item['kind'], pod=pod)
            try:
                turn['student'] = jev('You are Jev, a student in the Dipole classroom for the Monday 2021-10-04 natural gas '
                                      'trading day. Topic: %s.\nAnswer it yourself from the dipole classroom material below: '
                                      'what the dipole components and their pair relations show, with the numbers you rely '
                                      'on.\n\nDIPOLE MATERIAL:\n%s' % (topic, dipole or '(not received yet)'))
                observed = jev('You are Jev, the classroom observer. Compare the STUDENT answer and FRANKIE\'s answer on the '
                               'topic "%s" against the DIPOLE MATERIAL. Return JSON only: {"agree": true|false, '
                               '"disagreements": [..], "evidence": [..numbers from the material..], '
                               '"question_for_frankie": "one pointed question"}.\n\nSTUDENT:\n%s\n\nFRANKIE:\n%s\n\n'
                               'DIPOLE MATERIAL:\n%s' % (topic, turn['student'][:8000], frankie_text[:12000], dipole[:30000]))
                turn['observer'] = parse_json(observed) or dict(raw=observed)
                question = turn['observer'].get('question_for_frankie') or 'Which dipole evidence most supports your answer?'
                turn['frankie_reply'], turn['frankie_error'] = frankie(
                    'You are Frankie, reviewing your own Dipole classroom answer for the Monday 2021-10-04 trading day '
                    'with a classroom observer. Your answer on "%s":\n%s\n\nThe observer asks: %s\nAnswer directly, '
                    'citing the dipole evidence; say plainly if you would change your answer.' % (topic, frankie_text, question), pod)
                closing = jev('You are Jev, the classroom observer. Frankie replied to your question "%s":\n%s\n\nReturn JSON '
                              'only: {"settled": true|false, "why": "one sentence"}.' % (question, (turn['frankie_reply'] or
                                                                                       turn['frankie_error'] or '')[:12000]))
                turn['closing'] = parse_json(closing) or dict(raw=closing)
            except Exception as error:  # noqa: BLE001  -- a failed turn is recorded, never hidden
                turn['error'] = '%s: %s' % (type(error).__name__, str(error)[:300])
            turns.append(turn)
            log('turn %d topic=%s agree=%s settled=%s' % (len(turns), topic, (turn.get('observer') or {}).get('agree'),
                                                         (turn.get('closing') or {}).get('settled')))
        # 3. the scheduled report, every REPORT_MINUTES
        if time.time() - last_report >= report_every or (final and not queue):
            window = turns[window_start:]
            rows = ['| # | topic | kind | agree | settled | disagreement | question | Frankie replied |', '|---|---|---|---|---|---|---|---|']
            for number, turn in enumerate(window, window_start + 1):
                observer, closing = turn.get('observer') or {}, turn.get('closing') or {}
                rows.append('| %d | %s | %s | %s | %s | %s | %s | %s |' % (
                    number, str(turn['topic'])[:50], turn['kind'], observer.get('agree'), closing.get('settled'),
                    str((observer.get('disagreements') or [''])[0])[:120].replace('|', '/'),
                    str(observer.get('question_for_frankie', ''))[:120].replace('|', '/'),
                    'yes' if turn.get('frankie_reply') else (turn.get('frankie_error') or turn.get('error') or 'no')[:60]))
            synthesis = jev('Summarize for the operator, in under 200 words, what Jev learned in this window from the '
                            'classroom turns below: where Jev and Frankie agree, where they differ, what stayed open, and '
                            'what to look at next. Name turns by number.\n\n' + '\n'.join(rows)) if window else 'No turns yet.'
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
