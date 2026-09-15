"""Capture scoped Pod facts and stop compute while preserving its attached disk."""
import copy
import math
import re

from . import granite_cloud_diagnostics as telemetry
from . import granite_run_artifacts as artifacts
from . import granite_runpod_cloud_control as control


SCHEMA = 'GRANITE_POD_INFO_V1'
INTENT_FIELDS = {'schema', 'nonce', 'name', 'image', 'start', 'deadline'}
INFO_FIELDS = {'schema', 'intent', 'pod_id', 'pod', 'model', 'launch_deadline',
               'cleanup_mode', 'retained_directory', 'base_url', 'diagnostics',
               'runtime', 'resume_requires_status'}
STATUSES = {'PROVISIONING', 'STARTING', 'RUNNING', 'EXITED', 'ERROR', 'TERMINATED'}
PACKAGES = {'torch', 'transformers', 'tokenizers', 'vllm', 'model-hosting-container-standards'}


def _refuse():
    raise ValueError('invalid retained Granite Pod identity or evidence')


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _safe_id(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        _refuse()
    return value


def _owned(pod, intent, pod_id=None):
    if (type(pod) is not dict or type(pod.get('env')) is not dict
            or type(pod.get('id')) is not str or not control.owned_pod(pod, intent)
            or (pod_id is not None and pod['id'] != pod_id)):
        _refuse()
    return pod


def _mount(pod):
    mounts = pod.get('mounts')
    value = mounts.get('persistent') if type(mounts) is dict else None
    if (type(value) is not dict or value.get('path') != '/opt/ml'
            or not _integer(value.get('size'), 10, 10**6) or mounts.get('network')):
        _refuse()
    return {'persistent': {'path': '/opt/ml', 'size': value['size']}}


def _stop_result(pod, pod_id):
    if pod.get('status') not in STATUSES or pod['status'] in ('ERROR', 'TERMINATED'):
        _refuse()
    if pod['status'] == 'EXITED':
        _mount(pod)
        return {'status': 'confirmed_stopped', 'pod_id': pod_id, 'data_retained': True}
    return {'status': 'stop_pending', 'pod_id': pod_id, 'data_retained': False}


def stop_owned_once(api, intent, pod_id=None, on_discovered=None, on_ack=None):
    """One stop action, then exact readback. Absence is never retained success.

    The caller retries pending cleanup. A conflicting stop is accepted only when
    a fresh exact read proves EXITED. This helper never issues DELETE or start.
    """
    control.validate_intent(intent)
    if pod_id is None:
        pod = control.find_owned(api, intent)
        if pod is None:
            return {'status': 'absent_in_inventory', 'pod_id': None, 'data_retained': False}
        pod_id = _safe_id(pod['id'])
    else:
        pod_id = _safe_id(pod_id)
        pod = api.request('GET', '/v2/pods/' + pod_id)
    _owned(pod, intent, pod_id)
    if on_discovered is not None:
        on_discovered(pod_id)
    path = '/v2/pods/' + pod_id
    current = _owned(api.request('GET', path), intent, pod_id)
    result = _stop_result(current, pod_id)
    if result['status'] == 'confirmed_stopped':
        return result
    conflict = None
    try:
        api.request('POST', path + '/action', {'action': 'stop'})
        if on_ack is not None:
            on_ack()
    except control.ProviderError as error:
        if error.status != 409:
            raise
        conflict = error
    current = _owned(api.request('GET', path), intent, pod_id)
    result = _stop_result(current, pod_id)
    if conflict is not None and result['status'] != 'confirmed_stopped':
        raise conflict
    return result


def _pod_info(pod, intent):
    _owned(pod, intent)
    gpu = pod.get('gpu')
    location = pod.get('dataCenterId')
    cost = pod.get('cost')
    if (type(gpu) is not dict or gpu.get('id') != 'NVIDIA L40S'
            or gpu.get('count') != 1 or type(gpu.get('count')) is not int
            or not _integer(pod.get('disk'), 1, 10**6)
            or pod.get('status') not in STATUSES
            or (location is not None and (type(location) is not str
                 or not re.fullmatch('[A-Z]{2,4}-[A-Z]{2,4}-[0-9]{1,3}', location)))
            or type(cost) not in (int, float) or not math.isfinite(cost) or not 0 <= cost <= 100):
        _refuse()
    return dict(id=pod['id'], name=pod['name'], image=pod['image'], status=pod['status'],
                dataCenterId=location, gpu={'id': gpu['id'], 'count': gpu['count']},
                disk=pod['disk'], mounts=_mount(pod), cost=cost)


def _diagnostics(value, intent, manifest):
    if (type(value) is not dict or set(value) != {'schema', 'correlation_id', 'latest',
            'active_diagnostics', 'diagnostics'} or value.get('schema') != 'GRANITE_DIAGNOSTICS_SNAPSHOT_V1'
            or value.get('correlation_id') != intent['nonce']):
        _refuse()
    result = {'schema': value['schema'], 'correlation_id': intent['nonce']}
    for key in ('latest', 'active_diagnostics'):
        group = value[key]
        if type(group) is not dict or not set(group) <= telemetry.ROLES:
            _refuse()
        result[key] = {}
        for role, record in group.items():
            checked = _telemetry(record, intent, manifest)
            if checked['role'] != role or (key == 'active_diagnostics'
                    and checked['schema'] != 'GRANITE_DIAGNOSTIC_V1'):
                _refuse()
            result[key][role] = checked
    history = value['diagnostics']
    if type(history) is not list or len(history) > 100:
        _refuse()
    result['diagnostics'] = []
    for record in history:
        checked = _telemetry(record, intent, manifest)
        if checked['schema'] != 'GRANITE_DIAGNOSTIC_V1':
            _refuse()
        result['diagnostics'].append(checked)
    return result


def _telemetry(record, intent, manifest):
    if type(record) is not dict:
        _refuse()
    prefix = {'GRANITE_PROGRESS_V1': b'GRANITE_PROGRESS ',
              'GRANITE_DIAGNOSTIC_V1': b'GRANITE_DIAGNOSTIC '}.get(record.get('schema'))
    if prefix is None:
        _refuse()
    return telemetry.parse_line(prefix + artifacts.canonical(record), intent['nonce'], manifest)[1]


def _runtime(value):
    if value is None:
        return None
    if type(value) is not dict:
        _refuse()
    # Accept either startup-log records or an already sanitized retained subset.
    if 'startup' in value:
        startup = value['startup']
        if type(startup) is not dict:
            _refuse()
        startup = startup.get('startup', startup)
        facts = startup.get('runtime', {})
        context = startup.get('environment', {}).get('GRANITE_MAX_MODEL_LEN')
    else:
        facts, context = value, value.get('context_length')
    if type(facts) is not dict:
        _refuse()
    packages = facts.get('packages', {})
    if type(packages) is not dict:
        _refuse()
    result = {'packages': {}}
    for name in sorted(PACKAGES & packages.keys()):
        version = packages[name]
        if type(version) is not str or not re.fullmatch(r'[0-9][A-Za-z0-9.+_-]{0,63}', version):
            _refuse()
        result['packages'][name] = version
    for name in ('gpu_count', 'gpu_total_memory'):
        if name in facts:
            if not _integer(facts[name], 0, 10**13):
                _refuse()
            result[name] = facts[name]
    if 'gpu' in facts:
        if facts['gpu'] not in ('NVIDIA L40S', None):
            _refuse()
        result['gpu'] = facts['gpu']
    for name in ('python', 'cuda', 'driver'):
        if name in facts:
            version = facts[name]
            if version is not None and (type(version) is not str
                    or not re.fullmatch(r'[0-9][0-9.]{0,31}', version)):
                _refuse()
            result[name] = version
    if context is not None:
        if type(context) is str and re.fullmatch('[0-9]{1,7}', context):
            context = int(context)
        if not _integer(context, 1, 10**7):
            _refuse()
        result['context_length'] = context
    return result


def capture_pod_info(pod, intent, manifest, diagnostics, runtime=None):
    """Sanitize facts for durable retention. No credential or private URL survives."""
    control.validate_intent(intent)
    digest = artifacts.manifest_digest(manifest)
    safe_intent = {name: intent[name] for name in INTENT_FIELDS}
    safe_pod = _pod_info(pod, safe_intent)
    return dict(schema=SCHEMA, intent=safe_intent, pod_id=safe_pod['id'], pod=safe_pod,
        model=dict(manifest_sha256=digest, repository=manifest['repository'],
                   revision=manifest['revision'], files=copy.deepcopy(manifest['files'])),
        launch_deadline=intent['deadline'], cleanup_mode='stop_retain',
        retained_directory='/opt/ml/model',
        base_url='https://' + safe_pod['id'] + '-8081.proxy.runpod.net/v1',
        diagnostics=_diagnostics(diagnostics, safe_intent, manifest), runtime=_runtime(runtime),
        resume_requires_status='EXITED')


def validate_resume(info, pod, manifest):
    """Validate trusted-journal info against fresh provider read; performs no I/O."""
    if type(info) is not dict or set(info) != INFO_FIELDS or info.get('schema') != SCHEMA:
        _refuse()
    intent = info.get('intent')
    if type(intent) is not dict or set(intent) != INTENT_FIELDS or type(info.get('pod')) is not dict:
        _refuse()
    control.validate_intent(intent)
    recorded = dict(info['pod'], env={'RUNPOD_SMOKE_OWNER': intent['nonce']})
    expected = capture_pod_info(recorded, intent, manifest, info['diagnostics'], info['runtime'])
    if artifacts.canonical(expected) != artifacts.canonical(info):
        _refuse()
    actual = _pod_info(pod, intent)
    if actual['status'] != 'EXITED' or actual['id'] != info['pod_id']:
        _refuse()
    if pod['env'].get('GRANITE_MANIFEST_SHA256') != info['model']['manifest_sha256']:
        _refuse()
    # Status and cost change on stop; placement, compute and disk identity must not.
    stable = set(actual) - {'status', 'cost'}
    if any(actual[key] != info['pod'][key] for key in stable):
        _refuse()
    return copy.deepcopy(info)
