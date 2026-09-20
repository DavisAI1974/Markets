"""Inspect, or explicitly start, the retained Granite Pod through the Runpod v2 control plane.

    python research/kalshi/frankie_boss/operations/pod_control.py --pod ycf4v6lmave6xw --action inspect
    python research/kalshi/frankie_boss/operations/pod_control.py --pod ycf4v6lmave6xw --action start [--wait-seconds 300]
        [--retry-seconds 0]

The retained observer (granite_retained_host prepare) submits POST /v2/pods/{id}/action {"action":"start"}
exactly once per request journal and discards the provider's response body, so a refused start
(HTTP 400 on 2026-09-20, run 35502980177) leaves no reason on record and can never be retried by the
observer itself. This is the operator-level retry: it prints the Pod's observed state (env and any
credential-looking field removed), and with --action start requires the Pod to be EXITED, submits the
same v2 action, prints the provider's status AND body verbatim on refusal (the body is provider prose,
never our secret), polls the status transition, and prints a receipt line. It never stops, patches or
deletes anything, and it never prints an environment value.

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
    parser.add_argument('--action', choices=('inspect', 'start'), default='inspect')
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
