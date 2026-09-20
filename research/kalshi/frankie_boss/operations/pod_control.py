"""Inspect, or explicitly start, the retained Granite Pod through the Runpod v2 control plane.

    python research/kalshi/frankie_boss/operations/pod_control.py --pod ycf4v6lmave6xw --action inspect
    python research/kalshi/frankie_boss/operations/pod_control.py --pod ycf4v6lmave6xw --action start [--wait-seconds 300]
    python research/kalshi/frankie_boss/operations/pod_control.py --pod hhxs2fk7511cz5 --action terminate
    python research/kalshi/frankie_boss/operations/pod_control.py --pod 8vqdacl5t61rjx --action restart
        --wait-journal-key retained-granite/<request_sha256>/<generation>/retained-start-intent.json [--wait-seconds 900]
        [--retry-seconds 0]

The retained observer (granite_retained_host prepare) submits POST /v2/pods/{id}/action {"action":"start"}
exactly once per request journal and discards the provider's response body, so a refused start
(HTTP 400 on 2026-09-20, run 35502980177) leaves no reason on record and can never be retried by the
observer itself. This is the operator-level retry: it prints the Pod's observed state (env and any
credential-looking field removed), and with --action start requires the Pod to be EXITED, submits the
same v2 action, prints the provider's status AND body verbatim on refusal (the body is provider prose,
never our secret), polls the status transition, and prints a receipt line. It never stops, patches or
deletes anything, and it never prints an environment value. The one exception is --action terminate
(Greg, 2026-09-20, for the stranded replacement hhxs2fk7511cz5): DELETE /v2/pods/{id} of an EXITED
Pod that is NOT the retained Pod, confirmed by a 404 readback, with a receipt.

--action restart is the adoption step for a RUNNING replacement: the retained observer's
`observe_migrated_start` branch never starts the Pod and reads only container frames stamped after
its own retained-startup record, so the container is restarted on the same host (the GPU stays
allocated) once the observer has written the request's `retained-start-intent.json`, i.e. after it
has validated the Pod and claimed the run. The key is polled in the private journal bucket.

Run 35503440103 put the refusal on record: "There are not enough free GPUs on the host machine to
start this pod." The Pod is pinned to its host by its pod volume, so the only remedy short of
abandoning the retained model is to re-submit once a GPU frees up there. --retry-seconds N keeps
re-submitting every 60 s for at most N seconds while, and only while, the refusal is exactly that
host-busy message; any other refusal aborts at once. Every attempt is counted in the receipt.
"""
import argparse
import http.client
import json
import os
import time

CONTROL = 'api.runpod.io'
SENSITIVE = ('key', 'secret', 'token', 'password', 'env')
HOST_BUSY = 'not enough free GPUs on the host machine'
RETAINED_POD = '8vqdacl5t61rjx'   # never terminated here: it holds the retained model
RETRY_INTERVAL = 60


def control_call(key, method, path, body=None):
    connection = http.client.HTTPSConnection(CONTROL, timeout=20)
    try:
        raw = None if body is None else json.dumps(body, allow_nan=False).encode()
        connection.request(method, path, raw, {'Authorization': 'Bearer ' + key, 'Accept': 'application/json',
                                               'Content-Type': 'application/json'})
        response = connection.getresponse()
        data = response.read(1048577)
        return response.status, data
    finally:
        connection.close()


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if not any(s in k.lower() for s in SENSITIVE)}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def get_pod(key, pod_id):
    status, data = control_call(key, 'GET', '/v2/pods/' + pod_id)
    if status != 200:
        raise SystemExit('GET pod -> HTTP %d: %s' % (status, data[:2000].decode('utf-8', 'replace')))
    pod = json.loads(data)
    if pod.get('id') != pod_id:
        raise SystemExit('pod identity differs')
    return pod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pod', required=True)
    parser.add_argument('--action', choices=('inspect', 'start', 'terminate', 'restart'), default='inspect')
    parser.add_argument('--wait-journal-key', default='')
    parser.add_argument('--wait-seconds', type=int, default=300)
    parser.add_argument('--retry-seconds', type=int, default=0)
    args = parser.parse_args()
    key = os.environ['RUNPOD_API_KEY']

    pod = get_pod(key, args.pod)
    print('POD_STATE ' + json.dumps(scrub(pod), sort_keys=True))
    if args.action == 'inspect':
        print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_INSPECT_RECEIPT_V1', pod=args.pod,
                                          status=pod.get('status'), at=int(time.time()))))
        return
    if args.action == 'restart':
        if args.pod != RETAINED_POD:
            raise SystemExit('restart is only for the retained Pod')
        if pod.get('status') != 'RUNNING' or not str(pod.get('name', '')).endswith('-migration'):
            raise SystemExit('restart requires the RUNNING migrated Pod; status=%r' % (pod.get('status'),))
        seen_at = None
        if args.wait_journal_key:
            import boto3
            account = boto3.client('sts', region_name='us-east-1').get_caller_identity()['Account']
            bucket = 'frankie-granite42-' + account + '-us-east-1'
            s3 = boto3.client('s3', region_name='us-east-1')
            deadline = time.time() + args.wait_seconds
            while True:
                try:
                    head = s3.head_object(Bucket=bucket, Key=args.wait_journal_key)
                    seen_at = time.time()
                    print('JOURNAL_KEY_PRESENT %s last_modified=%s' % (args.wait_journal_key, head['LastModified'].isoformat()))
                    break
                except Exception as error:
                    code = getattr(error, 'response', {}).get('Error', {}).get('Code')
                    if code not in ('404', 'NoSuchKey', 'NotFound'):
                        raise
                if time.time() > deadline:
                    print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_RESTART_RECEIPT_V1', pod=args.pod, outcome='journal_key_absent',
                                                      journal_key=args.wait_journal_key, waited_seconds=args.wait_seconds)))
                    raise SystemExit(2)
                time.sleep(5)
            pod = get_pod(key, args.pod)
            if pod.get('status') != 'RUNNING':
                raise SystemExit('Pod left RUNNING while waiting: %r' % (pod.get('status'),))
        submitted_at = time.time()
        status, data = control_call(key, 'POST', '/v2/pods/' + args.pod + '/action', {'action': 'restart'})
        text = data[:2000].decode('utf-8', 'replace')
        if status not in (200, 201, 204):
            print('RESTART_REFUSED HTTP %d body=%s' % (status, text.strip()))
            print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_RESTART_RECEIPT_V1', pod=args.pod, outcome='refused', http_status=status,
                                              provider_body=text, journal_key=args.wait_journal_key, key_seen_at=seen_at)))
            raise SystemExit(2)
        transitions, last = [], None
        for _ in range(12):
            current = get_pod(key, args.pod).get('status')
            if current != last:
                transitions.append(dict(at=time.time(), status=current)); last = current
            time.sleep(5)
        print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_RESTART_RECEIPT_V1', pod=args.pod, outcome='accepted', http_status=status,
                                          journal_key=args.wait_journal_key, key_seen_at=seen_at, submitted_at=submitted_at,
                                          transitions=transitions, final_status=last)))
        return
    if args.action == 'terminate':
        if args.pod == RETAINED_POD:
            raise SystemExit('refusing to terminate the retained Pod')
        if pod.get('status') != 'EXITED' or not str(pod.get('name', '')).endswith('-migration'):
            raise SystemExit('terminate requires an EXITED replacement Pod; status=%r name=%r' % (pod.get('status'), pod.get('name')))
        submitted_at = time.time()
        status, data = control_call(key, 'DELETE', '/v2/pods/' + args.pod)
        text = data[:2000].decode('utf-8', 'replace')
        if status not in (200, 202, 204):
            print('TERMINATE_REFUSED HTTP %d body=%s' % (status, text.strip()))
            raise SystemExit(2)
        readback, _ = control_call(key, 'GET', '/v2/pods/' + args.pod)
        print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_TERMINATE_RECEIPT_V1', pod=args.pod, http_status=status,
                                          readback_http_status=readback, confirmed_absent=readback == 404,
                                          submitted_at=submitted_at, data_center=pod.get('dataCenterId'))))
        if readback != 404:
            raise SystemExit(2)
        return

    retry_until = time.time() + max(0, args.retry_seconds)
    attempts = []
    while True:
        if pod.get('status') != 'EXITED':
            raise SystemExit('refusing to start: Pod status is %r, resume requires EXITED' % (pod.get('status'),))
        submitted_at = time.time()
        status, data = control_call(key, 'POST', '/v2/pods/' + args.pod + '/action', {'action': 'start'})
        text = data[:4000].decode('utf-8', 'replace')
        attempts.append(dict(at=submitted_at, http_status=status))
        if status in (200, 201, 204):
            break
        # The body is the provider's explanation of the refusal; this is exactly what the observer discards.
        host_busy = status == 400 and HOST_BUSY in text
        print('START_REFUSED attempt=%d HTTP %d host_busy=%s body=%s' % (len(attempts), status, host_busy, text.strip()))
        if not host_busy or time.time() + RETRY_INTERVAL > retry_until:
            print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_START_RECEIPT_V1', pod=args.pod, outcome='refused',
                                              http_status=status, provider_body=text, attempts=len(attempts),
                                              first_submitted_at=attempts[0]['at'], last_submitted_at=submitted_at,
                                              retry_seconds=args.retry_seconds)))
            raise SystemExit(2)
        time.sleep(RETRY_INTERVAL)
        pod = get_pod(key, args.pod)
    accepted = {}
    try:
        accepted = json.loads(data) if data else {}
    except ValueError:
        pass
    print('START_ACCEPTED attempt=%d HTTP %d status_after_submit=%r' % (len(attempts), status,
          accepted.get('status') if isinstance(accepted, dict) else None))

    transitions = []
    last = None
    deadline = time.time() + args.wait_seconds
    while time.time() < deadline:
        current = get_pod(key, args.pod).get('status')
        if current != last:
            transitions.append(dict(at=time.time(), status=current))
            print('POD_STATUS %s' % current)
            last = current
        if current == 'RUNNING':
            break
        time.sleep(10)
    print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_START_RECEIPT_V1', pod=args.pod, outcome='accepted',
                                      http_status=status, submitted_at=submitted_at, attempts=len(attempts),
                                      first_submitted_at=attempts[0]['at'], transitions=transitions,
                                      final_status=last, reached_running=last == 'RUNNING')))


if __name__ == '__main__':
    main()
