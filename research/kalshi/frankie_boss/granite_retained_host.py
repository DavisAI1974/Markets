"""GitHub independent watchdog and retained-Pod readiness; never inference.

The local controller reads the safe readiness artifact, obtains its own private
service credential in memory, performs its journaled critic call, then stops the
Pod. These GitHub jobs independently enforce the same bounded lease.
"""
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request

from . import granite_run_artifacts as artifacts
from . import granite_runpod_cloud as cloud
from . import granite_runpod_cloud_control as control
from . import granite_cloud_resume as retained
from . import granite_retained_lifecycle as lifecycle
from .granite_runpod_tokenizer import LocalTokenizerAdmission, MAX_REQUEST_BYTES
from .granite_runpod_admission import TOKENIZER_FILES
from .granite_runpod_probe import https_exchange
from .granite_active_run import ActiveRunStore, completion_cleanup
from .granite_startup_pins import persist_configuration

OUT = Path('work/retained-granite')
INFO_SHA256 = 'c6c151ddc5ad252a04c34a533e8bc4d9f46c24778372c9bb84f34e748832020a'
PRIOR_RUN = '34928264918'
REQUEST_BUCKET = 'bento-568968024170-us-east-2-an'
REQUEST_PREFIX = 'nymex/ng_mbo_5y_v0/frankie/boss_requests/'


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_bytes(artifacts.canonical(value))


def info_from_journal(journal):
    prior = object.__new__(cloud.Journal)
    prior.client, prior.bucket = journal.client, journal.bucket
    prior.prefix = 'runpod-smoke/'+PRIOR_RUN+'/'
    raw = prior.get_bytes('pod-info.json')
    if raw is None or hashlib.sha256(raw).hexdigest() != INFO_SHA256:
        raise ValueError('accepted retained Pod receipt differs')
    return artifacts.strict_json(raw)


def request_digest():
    digest = os.environ.get('REQUEST_SHA256', '')
    if not digest:
        value = artifacts.strict_json(Path('.github/frankie-retained-lease-request.json').read_bytes())
        if set(value) not in ({'request_sha256', 'local_ready'},
                              {'request_sha256', 'local_ready', 'runtime_configuration'}):
            raise ValueError('explicit exact request digest required')
        digest = value['request_sha256']
    if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('exact actual request digest required')
    return digest


def read_object(journal, bucket, key, maximum):
    response = journal.client.get_object(Bucket=bucket, Key=key)
    with response['Body'] as stream:
        if response['ContentLength'] > maximum:
            raise ValueError('request or tokenizer object exceeds its explicit byte bound')
        raw = stream.read(maximum+1)
    if len(raw) != response['ContentLength']:
        raise ValueError('incomplete staged object')
    return raw


def tokenizer(journal, manifest, *, context=4096):
    directory = Path('work/retained-tokenizer')
    directory.mkdir(parents=True, exist_ok=False)
    for row in manifest['files']:
        if row['path'] in TOKENIZER_FILES:
            raw = read_object(journal, journal.bucket,
                artifacts.prefix_for(manifest)+row['path'], row['size'])
            (directory/row['path']).write_bytes(raw)
            artifacts.verify_file(directory/row['path'], row)
    return LocalTokenizerAdmission(directory, served_model_name='granite42-smoke', context=context)


def watchdog_identity():
    """Get actual job ID/start from GitHub, not a caller-provided liveness label."""
    repository, run_id = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_RUN_ID']
    if repository != 'DavisAI1974/Markets' or not run_id.isdecimal():
        raise ValueError('authorized repository/run required')
    request = urllib.request.Request('https://api.github.com/repos/'+repository+'/actions/runs/'+run_id+'/jobs?per_page=100',
        headers={'Authorization': 'Bearer '+os.environ['GH_TOKEN'], 'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(1024*1024+1)
    if len(raw) > 1024*1024:
        raise ValueError('oversized GitHub job response')
    jobs = [job for job in json.loads(raw)['jobs'] if job['name'] == 'retained-watchdog']
    if len(jobs) != 1 or jobs[0]['status'] != 'in_progress':
        raise ValueError('actual independent watchdog job is not running')
    job = jobs[0]
    started = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00')).timestamp()
    return dict(run_id=run_id, job_id=str(job['id']), job_deadline=started+360*60)


def keep_startup_frame(records, frame, lease):
    try:
        _keep_startup_frame(records, frame, lease)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        records['malformed_frames'] = records.get('malformed_frames', 0)+1


def _keep_startup_frame(records, frame, lease):
    # Runpod v2 OpenAPI defines SSE data {source,line,ts}; validate the
    # provider event timestamp as well as requesting its since-filter.
    if frame.get('source') != 'container' or type(frame.get('ts')) is not str:
        return
    stamp = datetime.fromisoformat(frame['ts'].replace('Z', '+00:00'))
    if stamp.tzinfo is None or not lease['start'] <= stamp.timestamp() <= time.time():
        return
    line = frame.get('line', '')
    if not isinstance(line, str):
        return
    if line.startswith('GRANITE_PROGRESS '):
        progress = artifacts.strict_json(line[len('GRANITE_PROGRESS '):].encode())
        if (progress.get('schema') == 'GRANITE_PROGRESS_V1'
                and progress.get('correlation_id') == '4e2ecee03d7b2bb77da16180aba4f98d'
                and progress.get('role') in ('bootstrap', 'stage', 'verify')):
            fields = ('role', 'phase', 'file_processed_bytes', 'bytes_present', 'verified_file_count')
            records.setdefault('progress', {})[progress['role']] = {key: progress[key] for key in fields}
            records['progress_event_at'] = stamp.timestamp()
    for prefix, key in [('GRANITE_RUNPOD_STARTUP ', 'startup'), ('GRANITE_DISK ', 'disk')]:
        if line.startswith(prefix):
            records[key] = artifacts.strict_json(line[len(prefix):].encode())
            records[key+'_event_at'] = stamp.timestamp()


def fresh_startup(api, lease):
    """Read only logs after lease start; keep only accepted non-secret receipts."""
    since = datetime.fromtimestamp(lease['start'], timezone.utc).isoformat().replace('+00:00', 'Z')
    path = '/v2/pods/'+lifecycle.POD_ID+'/logs?'+urllib.parse.urlencode(dict(source='container', since=since))
    connection = http.client.HTTPSConnection('api.runpod.io', timeout=4)
    records, consumed, deadline = {}, 0, time.monotonic()+8
    try:
        connection.request('GET', path, headers={'Authorization':'Bearer '+api.key, 'Accept':'text/event-stream'})
        response = connection.getresponse()
        if response.status != 200:
            return records
        while time.monotonic() < deadline and consumed < 1024*1024:
            if connection.sock:
                connection.sock.settimeout(max(.05, min(1, deadline-time.monotonic())))
            raw = response.readline(65537)
            consumed += len(raw)
            if not raw or len(raw) > 65536:
                break
            if not raw.startswith(b'data:'):
                continue
            try:
                frame = json.loads(raw[5:])
            except (ValueError, UnicodeError):
                records['malformed_frames'] = records.get('malformed_frames', 0)+1
                continue
            keep_startup_frame(records, frame, lease)
    except (TimeoutError, OSError):
        pass
    finally:
        connection.close()
    return records


def request_inputs():
    digest = request_digest()
    if os.environ.get('LOCAL_READY_JSON'):
        witness = json.loads(os.environ['LOCAL_READY_JSON'])
    else:
        marker = artifacts.strict_json(Path('.github/frankie-retained-lease-request.json').read_bytes())
        witness = marker['local_ready']
    return digest, witness


def runtime_configuration(journal):
    supplied = None
    if os.environ.get('RUNTIME_CONFIGURATION_JSON'):
        supplied = artifacts.strict_json(os.environ['RUNTIME_CONFIGURATION_JSON'].encode())
    else:
        path = Path('.github/frankie-retained-lease-request.json')
        if path.exists():
            marker = artifacts.strict_json(path.read_bytes())
            if marker.get('request_sha256') == request_digest():
                supplied = marker.get('runtime_configuration')
    return persist_configuration(journal, supplied)


def observer_handoff(phase):
    save('observer-handoff.json', dict(status='observer_handoff_required', phase=phase,
        pod_id=lifecycle.POD_ID, at=time.time(), pod_stop_requested=False,
        reason='GitHub hosted observer limit; not a startup or runtime deadline'))


def validate_runtime_or_fail(records, manifest):
    try:
        pin = artifacts.strict_json((OUT/'startup-bootstrap-pin.json').read_bytes())
        cloud.validate_runtime(records, dict(model_manifest_sha256=artifacts.manifest_digest(manifest),
                                            context=pin['service_context']))
        actual = records['startup']
        if (actual.get('lifetime_seconds', 'missing') is not None
                or actual.get('bootstrap_bundle_sha256') != pin['bundle_sha256']
                or actual.get('supervisor_command_sha256') != pin['supervisor_command_sha256']
                or (pin['transport_protocol'] == 'jobs_v1' and actual.get('durable_job_protocol') != 'jobs_v1')):
            raise ValueError('actual open bootstrap differs from the pinned candidate')
    except ValueError:
        save('confirmed-fatal.json', dict(reason='verified_runtime_or_model_integrity_failure'))
        raise


def prepare(journal, api, info, manifest):
    digest, witness = request_inputs()
    configuration = runtime_configuration(journal)
    body = read_object(journal, REQUEST_BUCKET, REQUEST_PREFIX+digest+'.json', MAX_REQUEST_BYTES)
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('actual staged request differs from its trusted digest')
    admit = tokenizer(journal, manifest, context=configuration['service_context'])
    admission = admit(body)
    rows = configuration['files']
    bundle_hash = configuration['bundle_sha256']
    if journal.get('retained-start-intent.json') is None:
        if {row['path'] for row in rows} != set(cloud.package.FILES):
            raise ValueError('initial bootstrap roster differs from reviewed source')
        for row in rows:
            raw = (Path(__file__).parent/row['path']).read_bytes()
            if len(raw) != row['size'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('initial bootstrap bytes differ from reviewed source')
    pod = retained._owned(api.request('GET', '/v2/pods/'+lifecycle.POD_ID), info['intent'], lifecycle.POD_ID)
    environment = pod['env']
    command_hash = hashlib.sha256(environment.get('SUPERVISOR_PROGRAM__APP_COMMAND', '').encode()).hexdigest()
    # Replacements use original durable pins, not a later checkout's command.
    if journal.get('retained-start-intent.json') is None:
        expected_command = cloud.bootstrap_command(rows, bundle_hash, journal.bucket,
            directory=configuration['bootstrap_directory'], open_ended=True)
        if hashlib.sha256(expected_command.encode()).hexdigest() != configuration['supervisor_command_sha256']:
            raise ValueError('initial supervisor command differs from reviewed pin')
    if (environment.get('RUNPOD_GRANITE_LIFETIME_SECONDS') != 'none'
            or environment.get('RUNPOD_BUNDLE_SHA256') != bundle_hash
            or environment.get('RUNPOD_SUPERVISOR_COMMAND_SHA256') != command_hash
            or command_hash != configuration['supervisor_command_sha256']
            or environment.get('GRANITE_MAX_MODEL_LEN') != str(configuration['service_context'])
            or environment.get('GRANITE_TRANSPORT_PROTOCOL', 'direct_v1') != configuration['transport_protocol']):
        raise ValueError('retained Pod needs the reviewed open bootstrap rollout before start')
    save('startup-bootstrap-pin.json', configuration)
    startup = journal.get('retained-startup.json')
    if startup is None:
        startup = lifecycle.make_startup(info, start=time.time(), request_sha256=digest, local_ready=witness)
        journal.put('retained-startup.json', startup, once=True)
    lifecycle.check_startup(startup, info)
    if startup['request_sha256'] != digest or startup['local_ready'] != witness:
        raise ValueError('observer request/local-host admission differs from initial start')
    save('pod-info.json', info)
    save('startup-intent.json', startup)
    identity = watchdog_identity()
    observer_end = identity['job_deadline']-120
    while time.time() < observer_end:
        arm = journal.get('retained-observer.json')
        if arm and arm.get('watchdog_identity') == identity and 0 <= time.time()-arm.get('at', 0) <= 20:
            break
        time.sleep(3)
    else:
        observer_handoff('awaiting_independent_observer')
        return
    while time.time() < observer_end:
        try:
            result = lifecycle.start_once(api, journal, info, manifest, startup, now=time.time(),
                request_body=body, tokenizer_admission=admit, expected_watchdog_identity=identity,
                active_runs=ActiveRunStore(journal.client, journal.bucket, lifecycle.POD_ID),
                runtime_configuration=configuration)
            break
        except control.ProviderError as error:
            if error.status != 400:
                raise
            pod = retained._owned(api.request('GET', '/v2/pods/'+lifecycle.POD_ID),
                info['intent'], lifecycle.POD_ID)
            if pod['status'] != 'EXITED':
                result = dict(status='observe_existing_start', pod_id=lifecycle.POD_ID)
                break
            save('capacity-wait.json', dict(status='waiting_for_retained_host_capacity',
                pod_id=lifecycle.POD_ID, observed_at=time.time()))
            time.sleep(20)
    else:
        observer_handoff('retained_host_capacity')
        return
    save('start.json', result)
    records = {}
    previous_progress = None
    while time.time() < observer_end:
        try:
            records.update(fresh_startup(api, startup))
            current_progress = records.get('progress')
            save('startup-progress.json', dict(at=time.time(),
                milestones=sorted(records), progress_evidence='provider startup/disk milestones and per-role file counters',
                actual_counters=current_progress,
                counters_changed=current_progress is not None and current_progress != previous_progress,
                responsive_health_is_not_progress=True))
            previous_progress = current_progress
            if {'startup', 'disk'} <= set(records):
                validate_runtime_or_fail(records, manifest)
                pod = retained._owned(api.request('GET', '/v2/pods/'+lifecycle.POD_ID), info['intent'], lifecycle.POD_ID)
                key = pod['env']['RUNPOD_GRANITE_API_KEY']
                observed = time.time()
                status, health = https_exchange(lifecycle.POD_ID, 'GET', '/health', b'', key, 10)
                if status == 200 and health == b'{"status":"ok"}':
                    run = lifecycle.make_run(info, startup, ready_at=observed)
                    runtime = dict(outcome='service_ready', pod_id=lifecycle.POD_ID, model='granite42-smoke',
                        ready_at=time.time(), deadline=None, runtime=records,
                        startup_event_at=records['startup_event_at'],
                        startup_event_time_basis='Runpod v2 container SSE event ts',
                        startup_intent_sha256=lifecycle.check_startup(startup, info),
                        monitor_identity=identity, health=dict(method='GET', path='/health', status=200, observed_at=observed),
                        inference_sent=False)
                    # Re-observing an existing ready run preserves its identity;
                    # there is no new start, execution budget, or inference.
                    prior = journal.get('service-ready.json')
                    prior_run = journal.get('retained-run.json')
                    if prior is not None:
                        runtime, run = prior, prior_run
                    elif prior_run is not None:
                        run = prior_run
                    runtime_hash = hashlib.sha256(artifacts.canonical(runtime)).hexdigest()
                    bindings = lifecycle.verified_service_inputs(info, manifest, run, runtime_receipt=runtime,
                        expected_runtime_sha256=runtime_hash, tokenizer_admission=admit,
                        output_tokens=admission['output_tokens'], startup_intent=startup,
                        context_encoding=configuration['context_encoding'],
                        service_context=configuration['service_context'],
                        transport_protocol=configuration['transport_protocol'])
                    if prior is None:
                        if prior_run is None:
                            journal.put('retained-run.json', run, once=True)
                        journal.put('service-ready.json', runtime, once=True)
                    save('run.json', run)
                    save('observer.json', journal.get('retained-observer.json'))
                    save('service-ready.json', runtime)
                    save('service-pins.json', dict(runtime_sha256=runtime_hash,
                        config_hash=bindings['config'].config_hash, identity_hash=bindings['identity'].identity_hash,
                        request_sha256=digest, admission=admission))
                    return
        except (TimeoutError, OSError) as error:
            save('startup-attention.json', dict(at=time.time(), error_type=type(error).__name__,
                status='observation_unavailable', pod_stop_requested=False))
        time.sleep(5)
    observer_handoff('startup_or_readiness')


def watchdog(journal, api, info):
    identity = watchdog_identity()
    startup = None
    last_ready_hash = None
    while time.time() < identity['job_deadline']-120:
        try:
            startup = journal.get('retained-startup.json')
            if startup:
                digest = lifecycle.check_startup(startup, info)
                save('pod-info.json', info)
                save('startup-intent.json', startup)
                journal.put('retained-observer.json', dict(startup_sha256=digest,
                    at=time.time(), watchdog_identity=identity))
                finished = journal.get('retained-finished.json') == {'startup_sha256': digest}
                fatal = journal.get('retained-confirmed-fatal.json') == {'startup_sha256': digest}
                if finished or fatal:
                    result = completion_cleanup(api, journal,
                        ActiveRunStore(journal.client, journal.bucket, lifecycle.POD_ID),
                        info, digest, retained.stop_owned_once, acknowledged_stop=True)
                    save('completion-cleanup.json', result)
                    if result['status'] in ('confirmed_stopped', 'not_active_run'):
                        return
                    # Keep reconciling this stop; an unrelated EXITED sample
                    # must not bypass the acknowledgement/memo/release protocol.
                    time.sleep(10)
                    continue
                ready = journal.get('service-ready.json')
                ready_hash = hashlib.sha256(artifacts.canonical(ready)).hexdigest() if ready else None
                new_ready = ready_hash is not None and ready_hash != last_ready_hash
                last_ready_hash = ready_hash
                pod = retained._owned(api.request('GET', '/v2/pods/'+lifecycle.POD_ID), info['intent'], lifecycle.POD_ID)
                result = dict(at=time.time(), pod_status=pod['status'],
                    status='observing', startup_verified=bool(ready),
                    actual_progress='service_readiness_completed' if new_ready else 'no_new_verified_milestone',
                    progress_assessment='milestone_advanced' if new_ready else 'progress_unknown_attention_if_persistent',
                    elapsed_time_stop=False, responsive_health_is_not_progress=True,
                    watchdog_identity=identity)
                if ready and pod['status'] != 'EXITED':
                    try:
                        health_status, health_body = https_exchange(lifecycle.POD_ID, 'GET', '/health', b'',
                            pod['env']['RUNPOD_GRANITE_API_KEY'], 10)
                        result['health_responsive'] = health_status == 200 and health_body == b'{"status":"ok"}'
                    except (TimeoutError, OSError):
                        result['health_responsive'] = None
                if pod['status'] == 'EXITED' and ready:
                    result['status'] = 'confirmed_stopped'
                save('watchdog.json', result)
                if result['status'] == 'confirmed_stopped':
                    return
        except Exception as error:
            save('watchdog-attention.json', dict(error_type=type(error).__name__, at=time.time(),
                status='observation_unavailable', pod_stop_requested=False))
        time.sleep(10)
    observer_handoff('monitoring')


def hold(journal, api, info):
    if not (OUT/'run.json').exists():
        return  # Startup observer handoff; no automatic stop.
    identity = watchdog_identity()
    while time.time() < identity['job_deadline']-120:
        try:
            pod = retained._owned(api.request('GET', '/v2/pods/'+lifecycle.POD_ID), info['intent'], lifecycle.POD_ID)
            if pod['status'] == 'EXITED':
                return
        except (TimeoutError, OSError):
            pass
        time.sleep(10)
    observer_handoff('ready_run')


def cleanup(api):
    # Elapsed time, absent progress, and observer exhaustion are NOT stop reasons.
    if not (OUT/'confirmed-fatal.json').exists():
        return
    info = artifacts.strict_json((OUT/'pod-info.json').read_bytes())
    if hashlib.sha256(artifacts.canonical(info)).hexdigest() != INFO_SHA256:
        raise ValueError('cached retained ownership receipt changed')
    startup = artifacts.strict_json((OUT/'startup-intent.json').read_bytes())
    digest = lifecycle.check_startup(startup, info)
    journal = cloud.Journal()
    journal.prefix = 'retained-granite/'+startup['request_sha256']+'/'
    journal.put('retained-confirmed-fatal.json', {'startup_sha256': digest})
    result = completion_cleanup(api, journal,
        ActiveRunStore(journal.client, journal.bucket, lifecycle.POD_ID), info, digest,
        retained.stop_owned_once, acknowledged_stop=True)
    save('cleanup.json', result)
    if result['status'] != 'confirmed_stopped':
        raise RuntimeError('retained cleanup requires follow-up')


def main():
    role = sys.argv[1]
    api = control.Runpod(os.environ['RUNPOD_API_KEY'])
    if role == 'cleanup':
        cleanup(api)
        return
    journal = cloud.Journal()
    info = info_from_journal(journal)
    # Request-specific journal survives observer job replacement. A prior start
    # intent always selects observation; it can never submit a second start.
    journal.prefix = 'retained-granite/'+request_digest()+'/'
    manifest = artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes())
    try:
        if role == 'prepare':
            prepare(journal, api, info, manifest)
        elif role == 'watchdog':
            watchdog(journal, api, info)
        elif role == 'hold':
            hold(journal, api, info)
        else:
            raise ValueError('unknown retained host role')
    except ValueError:
        # Only validate_runtime_or_fail marks confirmed fatal model/runtime
        # evidence. Observer identity/configuration errors preserve the Pod.
        raise


if __name__ == '__main__':
    main()
