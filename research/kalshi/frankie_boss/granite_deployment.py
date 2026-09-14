"""Bounded one-GPU SageMaker resource lifecycle; no model invocation.

Caller must verify staging/admission before create, and call cleanup in finally
AND an independent CI always step. Resource intents persist before every mutation.
https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateModel.html
https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DeleteEndpoint.html
"""
import hashlib
from pathlib import Path
import re
import time

try:
    from . import granite_run_artifacts as a, granite_startup as startup
except ImportError:
    import granite_run_artifacts as a
    import granite_startup as startup


def make_plan(*, account_sha_checked, run_id, max_model_len, served_model, now):
    account = account_sha_checked
    if type(account) is not str or hashlib.sha256(account.encode()).hexdigest() != a.APPROVED_ACCOUNT_SHA256:
        raise ValueError('approved account required')
    if type(run_id) is not str or not re.fullmatch('[a-z0-9-]{1,32}', run_id):
        raise ValueError('scoped run identifier required')
    if type(now) not in (int, float) or not 0 < now < 10**12:
        raise ValueError('finite creation timestamp required')
    stem = 'frankie-granite42-' + run_id
    bucket = f'frankie-granite42-{account}-us-east-1'
    manifest = a.strict_json(a.DEFAULT_MANIFEST.read_bytes())
    bootstrap_sha = hashlib.sha256(a.canonical(startup.bootstrap_manifest())).hexdigest()
    source = lambda prefix: {'S3Uri': f's3://{bucket}/{prefix}', 'S3DataType': 'S3Prefix', 'CompressionType': 'None'}
    return {'schema': 'GRANITE_BOUNDED_DEPLOYMENT_V1', 'region': 'us-east-1', 'created_at_epoch': now,
            'delete_deadline_epoch': now + 45 * 60, 'cleanup_deadline_epoch': now + 60 * 60,
            'hourly_compute_usd': '2.8026000000', 'compute_budget_usd': '2.10195',
            'model': {'ModelName': stem + '-model', 'ExecutionRoleArn': f'arn:aws:iam::{account}:role/FrankieGraniteExecutionRole',
                'PrimaryContainer': {'Image': '763104351884.dkr.ecr.us-east-1.amazonaws.com/vllm@' + startup.IMAGE_DIGEST,
                    'ModelDataSource': {'S3DataSource': source(a.prefix_for(manifest))},
                    'AdditionalModelDataSources': [{'ChannelName': 'bootstrap',
                        'S3DataSource': source('models/bootstrap/' + bootstrap_sha + '/')}],
                    'Environment': startup.launch_environment(max_model_len=max_model_len, served_model=served_model)}},
            'endpoint_config': {'EndpointConfigName': stem + '-config', 'ProductionVariants': [
                {'VariantName': 'AllTraffic', 'ModelName': stem + '-model', 'InstanceType': 'ml.g6e.2xlarge',
                 'InitialInstanceCount': 1, 'InitialVariantWeight': 1.0,
                 'ModelDataDownloadTimeoutInSeconds': 1200, 'ContainerStartupHealthCheckTimeoutInSeconds': 1200}]},
            'endpoint': {'EndpointName': stem + '-endpoint', 'EndpointConfigName': stem + '-config'}}


def plan_hash(plan):
    return hashlib.sha256(a.canonical(plan)).hexdigest()


def validate_plan(plan):
    try:
        role = re.fullmatch(r'arn:aws:iam::([0-9]{12}):role/FrankieGraniteExecutionRole', plan['model']['ExecutionRoleArn'])
        name = re.fullmatch(r'frankie-granite42-([a-z0-9-]{1,32})-model', plan['model']['ModelName'])
        env = plan['model']['PrimaryContainer']['Environment']
        if role is None or name is None:
            raise ValueError('deployment scope mismatch')
        expected = make_plan(account_sha_checked=role[1], run_id=name[1],
            max_model_len=int(env['GRANITE_MAX_MODEL_LEN']), served_model=env['GRANITE_SERVED_MODEL'],
            now=plan['created_at_epoch'])
        if plan != expected:
            raise ValueError('deployment plan was changed')
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('invalid deployment plan') from exc


def missing(exc, name):
    error = getattr(exc, 'response', {}).get('Error', {})
    if error.get('Code') in ('ResourceNotFound', 'ResourceNotFoundException'):
        return True
    return (error.get('Code') == 'ValidationException' and name in error.get('Message', '') and
            any(text in error['Message'].lower() for text in ('could not find', 'does not exist', 'not found')))


def describe(client, kind, plan):
    key = {'model': 'ModelName', 'endpoint_config': 'EndpointConfigName', 'endpoint': 'EndpointName'}[kind]
    name = plan[kind][key]
    try:
        return getattr(client, 'describe_' + kind)(**{key: name})
    except Exception as exc:
        if missing(exc, name):
            return None
        raise


def check_description(kind, observed, plan):
    expected = plan[kind]
    keys = {'model': ('ModelName', 'ExecutionRoleArn', 'PrimaryContainer'),
            'endpoint_config': ('EndpointConfigName', 'ProductionVariants'),
            'endpoint': ('EndpointName', 'EndpointConfigName')}[kind]
    def matches(actual, wanted, key=None):
        if key == 'Environment':
            return actual == wanted
        if type(wanted) is dict:
            return type(actual) is dict and all(k in actual and matches(actual[k], v, k) for k, v in wanted.items())
        if type(wanted) is list:
            return type(actual) is list and len(actual) == len(wanted) and all(matches(x, y) for x, y in zip(actual, wanted))
        return actual == wanted
    if any(not matches(observed.get(key), expected[key], key) for key in keys):
        raise ValueError('owned resource configuration drift: ' + kind)


def create_resources(client, plan, ledger_path, *, now=time.time):
    validate_plan(plan)
    if now() >= plan['delete_deadline_epoch']:
        raise ValueError('expired deployment plan')
    path = Path(ledger_path)
    if path.exists():
        raise ValueError('existing deployment ledger requires inspect/cleanup, not another create')
    # All names must be absent before intent is created; never take over another run.
    if any(describe(client, kind, plan) is not None for kind in ('model', 'endpoint_config', 'endpoint')):
        raise ValueError('resource name already exists')
    ledger = {'schema': 'GRANITE_DEPLOYMENT_LEDGER_V1', 'plan': plan, 'plan_sha256': plan_hash(plan),
              'status': 'creating', 'intents': [], 'responses': {}}
    a.save_receipt(path, ledger)
    for kind in ('model', 'endpoint_config', 'endpoint'):
        if now() >= plan['delete_deadline_epoch']:
            raise ValueError('expired deployment plan')
        ledger['intents'].append(kind)
        a.save_receipt(path, ledger)
        response = getattr(client, 'create_' + kind)(**plan[kind])
        ledger['responses'][kind] = response
        a.save_receipt(path, ledger)
    ledger['status'] = 'created'
    a.save_receipt(path, ledger)
    return ledger


def inspect_resources(client, plan):
    results = {}
    for kind in ('model', 'endpoint_config', 'endpoint'):
        observed = describe(client, kind, plan)
        if observed is None:
            raise ValueError('missing deployment resource: ' + kind)
        check_description(kind, observed, plan)
        results[kind] = observed
    endpoint = results['endpoint']
    if endpoint.get('EndpointStatus') == 'InService':
        variants = endpoint.get('ProductionVariants', [])
        if (len(variants) != 1 or variants[0].get('VariantName') != 'AllTraffic' or
                variants[0].get('CurrentInstanceCount') != 1 or variants[0].get('DesiredInstanceCount') != 1):
            raise ValueError('runtime endpoint replica count drift')
    return results


def wait_ready(client, plan, *, now=time.time, sleep=time.sleep):
    deadline = min(plan['created_at_epoch'] + 20 * 60, plan['delete_deadline_epoch'])
    while now() < deadline:
        observed = describe(client, 'endpoint', plan)
        if observed is None:
            raise ValueError('endpoint absent during startup')
        check_description('endpoint', observed, plan)
        status = observed['EndpointStatus']
        if status == 'InService':
            return inspect_resources(client, plan)
        if status != 'Creating':
            raise ValueError('endpoint startup failed: ' + status)
        sleep(10)
    raise TimeoutError('bounded endpoint startup expired')


def cleanup_resources(client, plan, ledger_path, *, now=time.time, sleep=time.sleep):
    path = Path(ledger_path)
    if not path.exists():
        return {'status': 'no_creation_intent'}
    ledger = a.strict_json(path.read_bytes())
    if ledger['plan_sha256'] != plan_hash(plan) or ledger['plan'] != plan:
        raise ValueError('cleanup plan/ledger mismatch')
    ledger['status'] = 'cleaning'
    a.save_receipt(path, ledger)
    for kind in ('endpoint', 'endpoint_config', 'model'):
        if kind not in ledger['intents']:
            continue
        key = {'model': 'ModelName', 'endpoint_config': 'EndpointConfigName', 'endpoint': 'EndpointName'}[kind]
        while True:
            observed = describe(client, kind, plan)
            if observed is None:
                break
            check_description(kind, observed, plan)
            if now() >= plan['cleanup_deadline_epoch']:
                ledger['status'] = 'cleanup_failed'
                a.save_receipt(path, ledger)
                raise TimeoutError('resource deletion not confirmed before cleanup deadline: ' + kind)
            if kind != 'endpoint' or observed.get('EndpointStatus') != 'Deleting':
                ledger['pending_delete'] = kind
                a.save_receipt(path, ledger)
                try:
                    getattr(client, 'delete_' + kind)(**{key: plan[kind][key]})
                except Exception as exc:
                    # Reconcile a lost acknowledgement on the next read. Failures
                    # remain retained and never count as confirmed deletion.
                    ledger.setdefault('delete_errors', []).append({'kind': kind, 'type': type(exc).__name__,
                        'code': getattr(exc, 'response', {}).get('Error', {}).get('Code')})
                    a.save_receipt(path, ledger)
            sleep(5)
        ledger.setdefault('absence_confirmed', []).append(kind)
        ledger.pop('pending_delete', None)
        a.save_receipt(path, ledger)
    ledger['status'] = 'deleted'
    a.save_receipt(path, ledger)
    return ledger


def startup_receipt(logs, plan):
    """Read only this endpoint's logs; caller validates receipt against admission.

    None means not yet visible. Pagination overflow and conflicting receipts fail.
    https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_GetLogEvents.html
    """
    group = '/aws/sagemaker/Endpoints/' + plan['endpoint']['EndpointName']
    streams, token, seen = [], None, set()
    for _ in range(20):
        args = {'logGroupName': group, 'limit': 50}
        if token:
            args['nextToken'] = token
        response = logs.describe_log_streams(**args)
        streams.extend(item['logStreamName'] for item in response.get('logStreams', []))
        token = response.get('nextToken')
        if not token:
            break
        if token in seen:
            raise ValueError('log stream pagination repeated')
        seen.add(token)
    else:
        raise ValueError('log stream pagination bound exceeded')
    receipts = {}
    for stream in streams:
        token, seen = None, set()
        for _ in range(100):
            args = {'logGroupName': group, 'logStreamName': stream, 'startFromHead': True, 'limit': 10000}
            if token:
                args['nextToken'] = token
            response = logs.get_log_events(**args)
            for event in response.get('events', []):
                message = event['message']
                marker = 'GRANITE_STARTUP_RECEIPT '
                if message.startswith(marker):
                    receipt = a.strict_json(message[len(marker):])
                    if receipt.get('schema') != 'GRANITE_STARTUP_RUNTIME_V1':
                        raise ValueError('invalid startup receipt schema')
                    receipts[hashlib.sha256(a.canonical(receipt)).hexdigest()] = receipt
            next_token = response.get('nextForwardToken')
            if not next_token or next_token == token:
                break
            if next_token in seen:
                raise ValueError('log event pagination repeated')
            seen.add(next_token)
            token = next_token
        else:
            raise ValueError('log event pagination bound exceeded')
    if len(receipts) > 1:
        raise ValueError('conflicting startup receipts')
    return next(iter(receipts.values()), None)
