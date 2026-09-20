"""Prepare a replacement retained Granite Pod on a host with free L40S stock (Greg, 2026-09-20).

    python research/kalshi/frankie_boss/operations/pod_prepare.py --source-pod ycf4v6lmave6xw
        --runtime-configuration <reviewed runtime configuration json> [--data-centers US-TX-4,...]
        [--cost-ceiling 1.25] [--wait-seconds 1800] [--stop-after-ready]
    ... --resume-pod hhxs2fk7511cz5     (start an EXITED replacement created earlier and watch it instead)
    ... --watch-pod hhxs2fk7511cz5      (watch a RUNNING replacement; no create, no start)
    ... --on-timeout keep|stop          (default keep: a Pod still bootstrapping at the horizon stays RUNNING)

The retained Pod ycf4v6lmave6xw is pinned to a host whose L40S is taken ("There are not enough free
GPUs on the host machine to start this pod", run 35503440103). This prepares a second Pod the
retained observer can adopt through the existing migration receipt mechanism
(granite_retained_migration_receipt.json -> info_from_journal -> POD_ID / JOURNAL_GENERATION):

1. reads the source Pod and verifies its environment against the reviewed runtime configuration
   (bundle sha, supervisor command sha, open lifetime, context, transport, fresh bootstrap URLs);
2. picks data centers with L40S stock from GET /v2/catalog/gpus (or takes --data-centers);
3. creates ONE Pod with the source's name, image, GPU, disk, persistent /opt/ml mount, port and its
   environment copied verbatim (the copy never leaves memory; nothing of it is printed);
4. watches the container log for the bootstrap's GRANITE_RUNPOD_STARTUP / GRANITE_DISK evidence,
   validates it exactly as the observer does, then waits for an authenticated /health 200;
5. writes the sanitized Pod facts, the migration-receipt candidate and the INFO_SHA256 the re-mint
   commit must carry, and prints FRANKIE_POD_PREPARE_RECEIPT_V1.

Run 35504624757 created hhxs2fk7511cz5 (EUR-IS-2, LOW stock everywhere) and saw no bootstrap line
in 30 minutes; --resume-pod restarts such a Pod on its now-cached host instead of creating another,
and the watch prints the scrubbed Pod state plus a short raw tail of the container and system logs
every five minutes so a silent bootstrap is diagnosable. Run 35506279203 then showed that the GPU
of a stop-retained Pod is taken within minutes under LOW stock, so the horizon no longer stops a
Pod by default (--on-timeout keep) and --watch-pod lets short runs read progress without touching
the Pod. The source Pod is only ever read. The new Pod is left RUNNING (it holds its GPU) unless
--stop-after-ready is given; a Pod whose bootstrap evidence fails validation or times out is stopped
(stop-retain), never terminated here. No inference is sent.
"""
import argparse
import hashlib
import http.client
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode

from research.kalshi.frankie_boss import granite_cloud_resume as resume
from research.kalshi.frankie_boss import granite_run_artifacts as artifacts
from research.kalshi.frankie_boss import granite_runpod_cloud as cloud
from research.kalshi.frankie_boss import granite_runpod_cloud_control as control
from research.kalshi.frankie_boss.granite_runpod_probe import https_exchange
from research.kalshi.frankie_boss.granite_startup_pins import validate_configuration, validate_url_freshness

CONTROL = 'api.runpod.io'
GPU = 'NVIDIA L40S'
STOCK_RANK = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
DIAGNOSTIC_DELAY = 60
PRIOR_RUN = '34928264918'            # the accepted retained receipt every migration receipt chains from
PRIOR_INFO_SHA256 = 'c6c151ddc5ad252a04c34a533e8bc4d9f46c24778372c9bb84f34e748832020a'
OUT = Path('work/pod-prepare')


def control_call(key, method, path, body=None):
    connection = http.client.HTTPSConnection(CONTROL, timeout=30)
    try:
        raw = None if body is None else json.dumps(body, allow_nan=False).encode()
        connection.request(method, path, raw, {'Authorization': 'Bearer ' + key, 'Accept': 'application/json',
                                               'Content-Type': 'application/json'})
        response = connection.getresponse()
        return response.status, response.read(4194305)
    finally:
        connection.close()


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes(artifacts.canonical(value))


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if not any(s in k.lower() for s in ('key', 'secret', 'token', 'password', 'env'))}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def log_tail(key, pod_id, source, lines=3):
    """A few raw provider log lines for diagnosis only; bootstrap and vLLM print no secret, and any
    line carrying a signed URL or a key assignment is dropped anyway."""
    connection = http.client.HTTPSConnection(CONTROL, timeout=4)
    kept = []
    try:
        connection.request('GET', '/v2/pods/' + pod_id + '/logs?' + urlencode(dict(source=source, tail=20)),
                           headers={'Authorization': 'Bearer ' + key, 'Accept': 'text/event-stream'})
        response = connection.getresponse()
        if response.status != 200:
            return ['HTTP %d' % response.status]
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            connection.sock.settimeout(max(.05, deadline - time.monotonic()))
            raw = response.readline(65537)
            if not raw:
                break
            if raw.startswith(b'data:'):
                try:
                    line = str(json.loads(raw[5:]).get('line', ''))
                except ValueError:
                    continue
                if 'X-Amz' in line or 'KEY=' in line or 'URLS' in line:
                    continue
                kept.append(line[:200])
    except (TimeoutError, OSError):
        kept.append('(log stream unavailable)')
    finally:
        connection.close()
    return kept[-lines:]


def facts_of(pod, intent):
    return resume._pod_info(pod, intent)     # sanitized: id, name, image, status, dataCenterId, gpu, disk, mounts, cost


def verify_source(source, configuration, now):
    environment = source['env']
    command_hash = hashlib.sha256(environment.get('SUPERVISOR_PROGRAM__APP_COMMAND', '').encode()).hexdigest()
    if (environment.get('RUNPOD_GRANITE_LIFETIME_SECONDS') != 'none'
            or environment.get('RUNPOD_BUNDLE_SHA256') != configuration['bundle_sha256']
            or environment.get('RUNPOD_SUPERVISOR_COMMAND_SHA256') != command_hash
            or command_hash != configuration['supervisor_command_sha256']
            or environment.get('GRANITE_MAX_MODEL_LEN') != str(configuration['service_context'])
            or environment.get('GRANITE_TRANSPORT_PROTOCOL', 'direct_v1') != configuration['transport_protocol']):
        raise SystemExit('source Pod environment differs from the reviewed runtime configuration')
    expiry = validate_url_freshness(environment, configuration, now=now)
    if expiry - now < 3600:
        raise SystemExit('source bootstrap URLs expire within the hour; refresh them first')
    nonce = environment.get('RUNPOD_SMOKE_OWNER', '')
    # validate_intent admits only its bounded deadline spans; the span is never used here (stop-retain only).
    intent = dict(schema='GRANITE_CLOUD_INTENT_V1', nonce=nonce, name=source['name'], image=source['image'],
                  start=now, deadline=now + 1800, cleanup_mode='stop_retain')
    control.validate_intent(intent)
    if not source['name'].endswith('-migration'):
        raise SystemExit('source Pod is not the migrated retained Pod')
    if not control.owned_pod(source, intent):
        raise SystemExit('source Pod ownership differs')
    return intent, expiry


def choose_data_centers(key, requested):
    status, data = control_call(key, 'GET', '/v2/catalog/gpus?' + urlencode(dict(include='AVAILABILITY', product='POD', count=1, cloud='SECURE')))
    if status != 200:
        raise SystemExit('catalog read -> HTTP %d: %s' % (status, data[:1000].decode('utf-8', 'replace')))
    entry = next((g for g in json.loads(data).get('gpus', []) if g.get('id') == GPU), None)
    if entry is None:
        raise SystemExit('catalog has no ' + GPU)
    stock = {dc.get('id'): dc.get('availability', 'NONE') for dc in entry.get('dataCenters', []) if dc.get('id')}
    print('CATALOG ' + json.dumps(dict(gpu=GPU, availability=entry.get('availability'), data_centers=stock), sort_keys=True))
    if requested:
        chosen = [dc for dc in requested if dc]
    else:
        chosen = sorted((dc for dc, level in stock.items() if level in STOCK_RANK), key=lambda dc: STOCK_RANK[stock[dc]])
    if not chosen:
        raise SystemExit('no data center reports ' + GPU + ' stock; pass --data-centers to override')
    return chosen, stock


def create(key, source, intent, data_centers):
    body = {'name': intent['name'], 'image': intent['image'], 'cloud': 'SECURE',
            'gpu': {'id': GPU, 'count': 1, 'minCudaVersion': '13.0'},
            'dataCenterIds': data_centers, 'disk': source['disk'],
            'mounts': {'persistent': {'path': source['mounts']['persistent']['path'], 'size': source['mounts']['persistent']['size']}},
            'ports': list(source.get('ports') or ['8081/http']), 'env': source['env'],
            'startSsh': False, 'startJupyter': False}
    status, data = control_call(key, 'POST', '/v2/pods', body)
    text = data[:4000].decode('utf-8', 'replace')
    if status not in (200, 201):
        print('CREATE_REFUSED HTTP %d body=%s' % (status, text.strip()))
        print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_PREPARE_RECEIPT_V1', outcome='create_refused',
                                          http_status=status, provider_body=text, data_centers=data_centers)))
        raise SystemExit(2)
    pod = json.loads(data)
    if not control.owned_pod(pod, intent):
        raise SystemExit('created Pod identity differs from the intent: ' + json.dumps(pod.get('id')))
    return pod


def startup_evidence(records, configuration):
    manifest = artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes())
    cloud.validate_runtime(records, dict(model_manifest_sha256=artifacts.manifest_digest(manifest),
                                         context=configuration['service_context']))
    actual = records['startup']
    if (actual.get('lifetime_seconds', 'missing') is not None
            or actual.get('bootstrap_bundle_sha256') != configuration['bundle_sha256']
            or actual.get('supervisor_command_sha256') != configuration['supervisor_command_sha256']
            or (configuration['transport_protocol'] == 'jobs_v1' and actual.get('durable_job_protocol') != 'jobs_v1')):
        raise ValueError('actual open bootstrap differs from the pinned candidate')


def migration_candidate(facts):
    """Chain the new Pod from the accepted retained receipt exactly as info_from_journal will read it."""
    journal = cloud.Journal()
    journal.prefix = 'runpod-smoke/' + PRIOR_RUN + '/'
    raw = journal.get_bytes('pod-info.json')
    if raw is None or hashlib.sha256(raw).hexdigest() != PRIOR_INFO_SHA256:
        raise SystemExit('accepted retained Pod receipt differs')
    info = artifacts.strict_json(raw)
    receipt = dict(schema='GRANITE_POD_MIGRATION_V1', source_info_sha256=PRIOR_INFO_SHA256,
                   source_pod_id=info['pod_id'], pod=facts)
    info['intent']['name'] = facts['name']
    info['pod_id'] = facts['id']
    info['pod'] = facts
    info['base_url'] = 'https://' + facts['id'] + '-8081.proxy.runpod.net/v1'
    return receipt, hashlib.sha256(artifacts.canonical(info)).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-pod', required=True)
    parser.add_argument('--runtime-configuration', required=True)
    parser.add_argument('--data-centers', default='')
    parser.add_argument('--cost-ceiling', type=float, default=1.25)
    parser.add_argument('--wait-seconds', type=int, default=1800)
    parser.add_argument('--stop-after-ready', action='store_true')
    parser.add_argument('--resume-pod', default='')
    parser.add_argument('--watch-pod', default='')
    parser.add_argument('--on-timeout', choices=('keep', 'stop'), default='keep')
    args = parser.parse_args()
    key = os.environ['RUNPOD_API_KEY']
    api = control.Runpod(key)
    configuration = validate_configuration(json.load(open(args.runtime_configuration, 'rb')))

    source = api.request('GET', '/v2/pods/' + args.source_pod)
    if source.get('id') != args.source_pod:
        raise SystemExit('source Pod identity differs')
    intent, expiry = verify_source(source, configuration, time.time())
    save('source-facts.json', facts_of(source, intent))
    print('SOURCE ' + json.dumps(dict(pod=source['id'], status=source.get('status'), env_keys=len(source['env']),
                                      bootstrap_urls_expire_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(expiry)))))

    if args.watch_pod:
        pod = api.request('GET', '/v2/pods/' + args.watch_pod)
        if pod.get('id') != args.watch_pod or not control.owned_pod(pod, intent):
            raise SystemExit('watch Pod identity or ownership differs')
        if pod.get('status') != 'RUNNING':
            raise SystemExit('watch requires RUNNING, Pod is %r' % (pod.get('status'),))
        data_centers, stock = [pod.get('dataCenterId')], {}
        created_at = time.time()
        pod_id = args.watch_pod
        print('WATCHING ' + json.dumps(facts_of(pod, intent), sort_keys=True))
    elif args.resume_pod:
        pod = api.request('GET', '/v2/pods/' + args.resume_pod)
        if pod.get('id') != args.resume_pod or not control.owned_pod(pod, intent):
            raise SystemExit('resume Pod identity or ownership differs')
        if pod.get('status') != 'EXITED':
            raise SystemExit('resume requires EXITED, Pod is %r' % (pod.get('status'),))
        data_centers, stock = [pod.get('dataCenterId')], {}
        created_at = time.time()
        status, data = control_call(key, 'POST', '/v2/pods/' + args.resume_pod + '/action', {'action': 'start'})
        text = data[:4000].decode('utf-8', 'replace')
        if status not in (200, 201, 204):
            print('RESUME_REFUSED HTTP %d body=%s' % (status, text.strip()))
            print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_PREPARE_RECEIPT_V1', outcome='resume_refused', pod=args.resume_pod,
                                              http_status=status, provider_body=text)))
            raise SystemExit(2)
        pod_id = args.resume_pod
        pod = api.request('GET', '/v2/pods/' + pod_id)
        print('RESUMED ' + json.dumps(facts_of(pod, intent), sort_keys=True))
    else:
        data_centers, stock = choose_data_centers(key, [dc.strip() for dc in args.data_centers.split(',') if dc.strip()])
        created_at = time.time()
        pod = create(key, source, intent, data_centers)
        pod_id = pod['id']
    facts = facts_of(pod, intent)
    save('pod-facts.json', facts)
    print('CREATED ' + json.dumps(facts, sort_keys=True))
    if type(facts['cost']) not in (int, float) or not 0 < facts['cost'] <= args.cost_ceiling:
        result = resume.stop_owned_once(api, intent, pod_id)
        print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_PREPARE_RECEIPT_V1', outcome='cost_outside_ceiling',
                                          pod=pod_id, cost=facts['cost'], ceiling=args.cost_ceiling, stop=result)))
        raise SystemExit(2)

    records = {}
    seen = set()
    health = None
    deadline = created_at + args.wait_seconds
    outcome = 'startup_incomplete'
    next_diagnostic = created_at + DIAGNOSTIC_DELAY
    while time.time() < deadline:
        try:
            pod = api.request('GET', '/v2/pods/' + pod_id)
            if not control.owned_pod(pod, intent):
                raise SystemExit('Pod identity changed during bootstrap')
            if time.time() >= next_diagnostic:
                next_diagnostic = time.time() + 300
                print('POD_STATE ' + json.dumps(dict(elapsed=int(time.time() - created_at), status=pod.get('status'),
                                                    runtime=scrub(pod.get('runtime')), milestones=sorted(records),
                                                    telemetry_lines=len(seen)), sort_keys=True), flush=True)
                for log_source in ('system', 'container'):   # never shadow `source`, the Pod being copied
                    for line in log_tail(key, pod_id, log_source):
                        print('LOG_TAIL %s %s' % (log_source, line), flush=True)
            incoming = cloud.startup_logs(api, pod_id)
            for line in incoming.pop('telemetry', []):
                if line not in seen:
                    seen.add(line)
                    if line.startswith('GRANITE_DIAGNOSTIC ') or len(seen) % 10 == 1:
                        print('TELEMETRY ' + line[:600], flush=True)
            records.update(incoming)
            save('startup-progress.json', dict(at=time.time(), status=pod.get('status'), milestones=sorted(records),
                                               telemetry_lines=len(seen)))
        except TimeoutError:
            pass
        if {'startup', 'disk'} <= set(records):
            try:
                startup_evidence(records, configuration)
            except ValueError as error:
                save('confirmed-fatal.json', dict(reason=str(error)))
                outcome = 'runtime_evidence_refused'
                break
            observed = time.time()
            try:
                status, body = https_exchange(pod_id, 'GET', '/health', b'', source['env']['RUNPOD_GRANITE_API_KEY'], 10)
            except (TimeoutError, OSError):
                status, body = None, b''
            if status == 200 and body == b'{"status":"ok"}':
                health = dict(method='GET', path='/health', status=200, observed_at=observed)
                outcome = 'service_ready'
                break
        time.sleep(10)

    save('startup-records.json', dict(startup=records.get('startup'), disk=records.get('disk')))
    facts = facts_of(api.request('GET', '/v2/pods/' + pod_id), intent)
    stop = None
    if outcome == 'service_ready':
        receipt, info_sha256 = migration_candidate(facts)
        save('migration-receipt-candidate.json', receipt)
        save('info-sha256.json', dict(INFO_SHA256=info_sha256, POD_ID=pod_id,
                                      JOURNAL_GENERATION='migration-' + pod_id + '-' + configuration['bundle_sha256'][:12]))
        save('health.json', health)
        if args.stop_after_ready:
            stop = resume.stop_owned_once(api, intent, pod_id)
    elif outcome == 'runtime_evidence_refused' or args.on_timeout == 'stop':
        stop = resume.stop_owned_once(api, intent, pod_id)
    facts = facts_of(api.request('GET', '/v2/pods/' + pod_id), intent)
    save('pod-facts.json', facts)
    print('RECEIPT ' + json.dumps(dict(schema='FRANKIE_POD_PREPARE_RECEIPT_V1', outcome=outcome, pod=pod_id,
                                      source_pod=args.source_pod, facts=facts, data_centers_offered=data_centers,
                                      stock=stock, created_at=created_at, ready_at=health and health['observed_at'],
                                      startup_event=records.get('startup', {}).get('started_at'), stop=stop,
                                      on_timeout=args.on_timeout, telemetry_lines=len(seen),
                                      info_sha256=(json.loads((OUT / 'info-sha256.json').read_bytes()) if outcome == 'service_ready' else None)),
                                 sort_keys=True))
    if outcome != 'service_ready':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
