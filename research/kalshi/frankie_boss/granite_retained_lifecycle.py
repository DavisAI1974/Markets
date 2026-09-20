"""Bounded reuse of the accepted Granite Pod; never creates or deletes a Pod.

The caller runs watchdog_tick from an independent runner and stores its arm in
the shared journal. resume_once must execute only after full request admission.
The accepted model bootstrap and mounted files are left intact.
"""
import hashlib
import math
import re

from .granite_cloud_resume import validate_resume, stop_owned_once
from .granite_run_artifacts import canonical
from .granite_runpod_admission import CONTEXT
from .granite_runpod_tokenizer import LocalTokenizerAdmission

from .granite_retained_identity import POD_ID
SCHEMA = 'GRANITE_RETAINED_LEASE_V1'


def make_startup(info, *, start, request_sha256, local_ready):
    # Reuse exact retained ownership/request validation without attaching a
    # deadline to startup. Local native input admission authorizes this start.
    checked = make_lease(info, start=start, duration_seconds=1800, request_sha256=request_sha256)
    if (type(local_ready) is not dict
            or set(local_ready) != {'request_sha256', 'host_instance_id', 'admitted_at'}
            or local_ready['request_sha256'] != request_sha256
            or type(local_ready['host_instance_id']) is not str
            or not re.fullmatch('[A-Za-z0-9_-]{16,128}', local_ready['host_instance_id'])
            or type(local_ready['admitted_at']) not in (int, float)
            or not math.isfinite(local_ready['admitted_at'])
            or not 0 < local_ready['admitted_at'] <= start):
        raise ValueError('actual local input-admitted witness required')
    return dict(schema='GRANITE_RETAINED_STARTUP_V1', pod_id=POD_ID, start=start,
        retained_info_sha256=checked['retained_info_sha256'], request_sha256=request_sha256,
        local_ready=dict(local_ready), startup_deadline=None)


def check_startup(startup, info):
    expected = make_startup(info, start=startup['start'],
        request_sha256=startup['request_sha256'], local_ready=startup['local_ready'])
    if canonical(startup) != canonical(expected):
        raise ValueError('retained startup identity changed')
    return hashlib.sha256(canonical(startup)).hexdigest()


def make_run(info, startup, *, ready_at):
    digest = check_startup(startup, info)
    if type(ready_at) not in (int, float) or not math.isfinite(ready_at) or ready_at < startup['start']:
        raise ValueError('actual readiness time required')
    return dict(schema='GRANITE_RETAINED_OPEN_RUN_V1', pod_id=POD_ID,
        start=ready_at, deadline=None, request_sha256=startup['request_sha256'],
        retained_info_sha256=startup['retained_info_sha256'], startup_intent_sha256=digest)


def start_once(api, journal, info, manifest, startup, *, now, request_body,
               tokenizer_admission, expected_watchdog_identity, active_runs=None,
               runtime_configuration=None):
    digest = check_startup(startup, info)
    prior = journal.get('retained-start-intent.json')
    intent = dict(startup_sha256=digest, pod_id=POD_ID)
    if prior is not None:
        if prior != intent:
            raise ValueError('another startup owns this request journal')
        return dict(status='observe_existing_start', pod_id=POD_ID)
    if (type(tokenizer_admission) is not LocalTokenizerAdmission
            or tokenizer_admission.evidence_class != 'LOCAL_TOKENIZER_ADMISSION'
            or type(request_body) is not bytes
            or hashlib.sha256(request_body).hexdigest() != startup['request_sha256']):
        raise ValueError('actual pinned tokenizer and exact request required')
    from .granite_startup_pins import validate_configuration, validate_url_freshness
    configuration = validate_configuration(runtime_configuration)
    context = configuration['service_context']
    if active_runs is None or active_runs.pod_id != POD_ID:
        raise ValueError('shared Pod run ownership required before start')
    admitted = tokenizer_admission(request_body)
    if (admitted.get('request_sha256') != startup['request_sha256']
            or admitted.get('context') != context
            or type(admitted.get('input_tokens')) is not int or admitted['input_tokens'] <= 0
            or type(admitted.get('output_tokens')) is not int or admitted['output_tokens'] <= 0
            or admitted['input_tokens'] + admitted['output_tokens'] > context):
        raise ValueError('full actual request admission required')
    _watchdog(expected_watchdog_identity, {'deadline': now})
    arm = journal.get('retained-observer.json')
    if (type(arm) is not dict or arm.get('startup_sha256') != digest
            or arm.get('watchdog_identity') != expected_watchdog_identity
            or not 0 <= now-arm.get('at', 0) <= 20):
        raise ValueError('fresh independent startup observer required')
    pod = api.request('GET', '/v2/pods/'+POD_ID)
    migrated_live = pod['status'] == 'RUNNING' and info['intent']['name'].endswith('-migration')
    if migrated_live:
        from .granite_cloud_resume import validate_running_migration
        validate_running_migration(info, pod, manifest)
    else:
        validate_resume(info, pod, manifest)
    expiry = validate_url_freshness(pod['env'], configuration, now=now)
    journal.put('startup-capability-expiry.json', dict(earliest_expiry=expiry))
    active_runs.claim(digest)
    journal.put('retained-start-intent.json', intent, once=True)
    if migrated_live:
        result = dict(status='observe_migrated_start', pod_id=POD_ID, startup_sha256=digest)
        journal.put('retained-start-result.json', result, once=True)
        return result
    try:
        api.request('POST', '/v2/pods/'+POD_ID+'/action', {'action': 'start'})
    except Exception as error:
        journal.put('retained-start-failure.json', dict(startup_sha256=digest,
            error_type=type(error).__name__, status='start_outcome_unknown'), once=True)
        raise
    result = dict(status='start_submitted', pod_id=POD_ID, startup_sha256=digest)
    journal.put('retained-start-result.json', result, once=True)
    return result


def make_lease(info, *, start, duration_seconds, request_sha256):
    if (info['pod_id'] != POD_ID or type(start) not in (float, int)
            or not math.isfinite(start) or type(duration_seconds) is not int
            or duration_seconds not in (600, 900, 1200, 1800)
            or type(request_sha256) is not str or len(request_sha256) != 64
            or any(c not in '0123456789abcdef' for c in request_sha256)):
        raise ValueError('exact accepted Pod, request digest and bounded lease required')
    return dict(schema=SCHEMA, pod_id=POD_ID, retained_info_sha256=hashlib.sha256(canonical(info)).hexdigest(),
                start=start, deadline=start+duration_seconds, request_sha256=request_sha256)


def _check(lease, info):
    duration = lease['deadline']-lease['start']
    if duration not in (600, 900, 1200, 1800):
        raise ValueError('invalid retained lease duration')
    expected = make_lease(info, start=lease['start'],
                          duration_seconds=int(duration),
                          request_sha256=lease['request_sha256'])
    if canonical(expected) != canonical(lease):
        raise ValueError('retained lease identity changed')
    return hashlib.sha256(canonical(lease)).hexdigest()


def _watchdog(identity, lease):
    if (type(identity) is not dict or set(identity) != {'run_id', 'job_id', 'job_deadline'}
            or type(identity['run_id']) is not str or not re.fullmatch('[0-9]+', identity['run_id'])
            or type(identity['job_id']) is not str or not re.fullmatch('[A-Za-z0-9_-]+', identity['job_id'])
            or type(identity['job_deadline']) not in (int, float)
            or not math.isfinite(identity['job_deadline'])
            or identity['job_deadline'] < lease['deadline']+30):
        raise ValueError('independent watchdog run/job and sufficient job deadline required')


def watchdog_tick(api, journal, info, lease, *, now, watchdog_identity):
    """One bounded watchdog iteration, retaining cleanup after journal loss.

    Cache info and lease before entering the independent watchdog loop. Keep
    invoking this every <=10 seconds through deadline+30 until stopped.
    Never interpret Pod absence as successful retained cleanup.
    """
    digest = _check(lease, info)
    _watchdog(watchdog_identity, lease)
    if now < lease['start']:
        raise ValueError('watchdog precedes lease')
    finished = False
    try:
        finished = journal.get('retained-finished.json') == {'lease_sha256': digest}
    except Exception:
        pass  # Deadline cleanup remains independent of S3 availability.
    if finished or now >= lease['deadline']-120:
        result = stop_owned_once(api, info['intent'], POD_ID)
        try:
            journal.put('retained-cleanup.json', dict(result, lease_sha256=digest))
        except Exception:
            pass
        return result
    arm = dict(lease_sha256=digest, at=now, watchdog_identity=dict(watchdog_identity))
    journal.put('retained-armed.json', arm)
    return dict(status='armed', **arm)


def resume_once(api, journal, info, manifest, lease, *, now, request_body,
                tokenizer_admission, expected_watchdog_identity):
    """Persist intent before one start; interrupted starts are never resubmitted.

    An existing intent returns an explicit recovery state. The orchestrator must
    inspect the existing Pod and startup evidence, not invoke another start.
    """
    digest = _check(lease, info)
    prior = journal.get('retained-start-intent.json')
    if prior is not None:
        if prior != {'lease_sha256': digest, 'pod_id': POD_ID}:
            raise ValueError('another retained lease already owns this journal')
        return dict(status='recover_existing_start', pod_id=POD_ID,
                    requires_startup_verification=True)
    if (type(tokenizer_admission) is not LocalTokenizerAdmission
            or tokenizer_admission.evidence_class != 'LOCAL_TOKENIZER_ADMISSION'
            or type(request_body) is not bytes
            or hashlib.sha256(request_body).hexdigest() != lease['request_sha256']):
        raise ValueError('actual pinned local tokenizer and exact request bytes required')
    admitted_request = tokenizer_admission(request_body)
    if (admitted_request.get('request_sha256') != lease['request_sha256']
            or admitted_request.get('context') != CONTEXT
            or type(admitted_request.get('input_tokens')) is not int
            or type(admitted_request.get('output_tokens')) is not int
            or admitted_request['input_tokens'] < 1 or admitted_request['output_tokens'] < 1
            or admitted_request['input_tokens']+admitted_request['output_tokens'] > CONTEXT):
        raise ValueError('full actual request admission required before resuming compute')
    arm = journal.get('retained-armed.json')
    _watchdog(expected_watchdog_identity, lease)
    if (type(arm) is not dict or arm.get('lease_sha256') != digest
            or arm.get('watchdog_identity') != expected_watchdog_identity
            or not lease['start'] <= now < lease['deadline']-180
            or not 0 <= now-arm.get('at', 0) <= 20):
        raise ValueError('fresh independent watchdog arm required')
    pod = api.request('GET', '/v2/pods/'+POD_ID)
    validate_resume(info, pod, manifest)
    journal.put('retained-start-intent.json', {'lease_sha256': digest, 'pod_id': POD_ID}, once=True)
    api.request('POST', '/v2/pods/'+POD_ID+'/action', {'action': 'start'})
    # No environment patch, model download, inference or acceptance rerun.
    result = dict(status='start_submitted', pod_id=POD_ID, lease_sha256=digest,
                  requires_startup_verification=True)
    journal.put('retained-start-result.json', result, once=True)
    return result


def verified_service_inputs(info, manifest, lease, *, runtime_receipt,
                            expected_runtime_sha256, tokenizer_admission,
                            output_tokens, request_timeout=None, startup_intent=None,
                            context_encoding='compact_v1', service_context=CONTEXT,
                            transport_protocol='direct_v1'):
    """Assemble transport only from this lease's complete startup/health receipt.

    The independent hosting runner must capture the new bootstrap's accepted
    13-file verification and an authenticated health response after resume.
    It persists that receipt and its trusted digest before calling this helper.
    """
    from .granite_runpod_service import RunpodConfig, _hash, _runtime
    from .granite_context_route import context_route
    from .granite_shadow import GraniteIdentity
    from .granite_contract import SCHEMA_VERSION
    from .granite_run_artifacts import manifest_digest
    open_run = lease.get('schema') == 'GRANITE_RETAINED_OPEN_RUN_V1'
    if open_run:
        if startup_intent is None or canonical(lease) != canonical(make_run(info, startup_intent, ready_at=lease['start'])):
            raise ValueError('exact open run and startup required')
    else:
        _check(lease, info)
    startup_lower_bound = lease['start']
    if startup_intent is not None:
        startup_digest = check_startup(startup_intent, info)
        if (startup_intent['request_sha256'] != lease['request_sha256']
                or runtime_receipt.get('startup_intent_sha256') != startup_digest
                or startup_intent['start'] > lease['start']):
            raise ValueError('execution lease differs from admitted startup')
        startup_lower_bound = startup_intent['start']
    if (type(tokenizer_admission) is not LocalTokenizerAdmission
            or tokenizer_admission.evidence_class != 'LOCAL_TOKENIZER_ADMISSION'
            or _hash(runtime_receipt) != expected_runtime_sha256):
        raise ValueError('actual tokenizer and independently pinned current runtime required')
    startup = runtime_receipt['runtime']['startup']['startup']
    mount = startup['mount']
    health = runtime_receipt.get('health')
    if (mount.get('schema') != 'GRANITE_MOUNT_VERIFICATION_V1'
            or mount.get('manifest_sha256') != manifest_digest(manifest)
            or mount.get('files') != manifest['files']
            or mount.get('bytes') != sum(row['size'] for row in manifest['files'])
            or type(health) is not dict or health.get('status') != 200
            or health.get('method') != 'GET' or health.get('path') != '/health'
            or not startup_lower_bound <= runtime_receipt.get('startup_event_at', 0) <= health.get('observed_at', 0)
            or not lease['start'] <= health.get('observed_at', 0) <= runtime_receipt.get('ready_at', 0)
            or not lease['start'] <= runtime_receipt.get('ready_at', 0)
            or (not open_run and runtime_receipt.get('ready_at', 0) >= lease['deadline']-120)):
        raise ValueError('fresh full model-file verification and authenticated health required')
    route = context_route(context_encoding)
    if tokenizer_admission.context != service_context:
        raise ValueError('selected service capacity differs from actual tokenizer admission')
    identity = GraniteIdentity(manifest_digest(manifest), None,
        tokenizer_admission.tokenizer_sha256, 'none', canonical(startup).decode(),
        False, 0, output_tokens, hashlib.sha256(route.system_text.encode()).hexdigest(),
        SCHEMA_VERSION, route.parser_code_hash(), None)
    config = RunpodConfig(POD_ID, 'granite42-smoke', request_timeout, expected_runtime_sha256,
        context=service_context, transport_protocol=transport_protocol)
    _runtime(config, identity, runtime_receipt)
    return dict(config=config, identity=identity, runtime_receipt=runtime_receipt,
                admit_request=tokenizer_admission)
