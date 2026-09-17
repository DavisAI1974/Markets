"""Conditional shared ownership for a retained Pod's start/stop transitions."""
import hashlib
import json
import re

MAX_RECORD_BYTES = 4096  # S3 active-run record size in BYTES; not a token context

from .granite_cloud_resume import _owned, _stop_result


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class ActiveRunStore:
    def __init__(self, client, bucket, pod_id):
        if not re.fullmatch('[a-z0-9]{1,64}', pod_id):
            raise ValueError('exact Pod identity required')
        self.client, self.bucket, self.pod_id = client, bucket, pod_id
        self.key = 'retained-granite-pods/'+pod_id+'/active-run.json'

    def read(self):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.key)
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404'):
                return None, None
            raise
        with response['Body'] as stream:
            raw = stream.read(MAX_RECORD_BYTES + 1)
        if len(raw) > MAX_RECORD_BYTES or len(raw) != response['ContentLength']:
            raise ValueError('invalid active-run record size')
        value = json.loads(raw)
        if (set(value) != {'schema', 'pod_id', 'startup_sha256', 'phase'}
                or value['schema'] != 'GRANITE_POD_ACTIVE_RUN_V1' or value['pod_id'] != self.pod_id
                or value['phase'] not in ('active', 'stopping', 'closed')
                or type(value['startup_sha256']) is not str
                or not re.fullmatch('[0-9a-f]{64}', value['startup_sha256'])
                or not response.get('ETag')):
            raise ValueError('invalid active-run identity')
        return value, response['ETag']

    def _write(self, value, etag):
        condition = {'IfNoneMatch': '*'} if etag is None else {'IfMatch': etag}
        self.client.put_object(Bucket=self.bucket, Key=self.key, Body=canonical(value),
            ServerSideEncryption='AES256', ContentType='application/json', **condition)
        actual, _ = self.read()
        if actual != value:
            raise ValueError('active-run conditional write changed concurrently')

    def claim(self, digest):
        if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('startup digest required')
        previous, etag = self.read()
        if previous is not None and previous['phase'] != 'closed':
            if previous['startup_sha256'] == digest and previous['phase'] == 'active':
                return
            raise ValueError('another active or stopping run owns this Pod')
        self._write(dict(schema='GRANITE_POD_ACTIVE_RUN_V1', pod_id=self.pod_id,
            startup_sha256=digest, phase='active'), etag)

    def begin_stop(self, digest):
        previous, etag = self.read()
        if previous is None or previous['startup_sha256'] != digest or previous['phase'] != 'active':
            return False
        self._write(dict(previous, phase='stopping'), etag)
        return True

    def finish_stop(self, digest):
        previous, etag = self.read()
        if previous is None or previous['startup_sha256'] != digest:
            raise ValueError('cannot release another run')
        if previous['phase'] == 'closed':
            return
        if previous['phase'] != 'stopping':
            raise ValueError('stop ownership must precede release')
        self._write(dict(previous, phase='closed'), etag)


def completion_cleanup(api, journal, active_runs, info, digest, stop, *, acknowledged_stop=False):
    def finish(result):
        if result['status'] == 'confirmed_stopped':
            receipt = dict(result, startup_sha256=digest)
            journal.put('retained-completion-cleanup.json', receipt, once=True)
            active_runs.finish_stop(digest)
            return receipt
        return result

    prior = journal.get('retained-completion-cleanup.json')
    if prior is not None:
        if (prior.get('startup_sha256') != digest or prior.get('status') != 'confirmed_stopped'
                or prior.get('pod_id') != active_runs.pod_id or prior.get('data_retained') is not True):
            raise ValueError('completion cleanup identity differs')
        # A crash after saving completion but before release must not wedge the Pod.
        current, _ = active_runs.read()
        if current is not None and current['startup_sha256'] == digest and current['phase'] == 'stopping':
            active_runs.finish_stop(digest)
        return prior
    if not active_runs.begin_stop(digest):
        current, _ = active_runs.read()
        if current is not None and current['startup_sha256'] == digest and current['phase'] == 'stopping':
            ack = journal.get('retained-stop-acknowledged.json') if acknowledged_stop else None
            if ack is not None:
                if ack != dict(startup_sha256=digest, pod_id=active_runs.pod_id, status='stop_acknowledged'):
                    raise ValueError('stop acknowledgement identity differs')
                # Only a successfully returned stop action permits later GET-only
                # confirmation. Unknown actions never enter this recovery path.
                pod = _owned(api.request('GET', '/v2/pods/'+active_runs.pod_id),
                    info['intent'], active_runs.pod_id)
                return finish(_stop_result(pod, active_runs.pod_id))
            # An earlier stop may still be in flight. Never issue a second stop,
            # nor release ownership while that operation's outcome is unknown.
            return dict(status='cleanup_pending', pod_id=active_runs.pod_id, startup_sha256=digest)
        return dict(status='not_active_run', pod_id=active_runs.pod_id, startup_sha256=digest)
    def acknowledge():
        name = 'retained-stop-acknowledged.json'
        receipt = dict(startup_sha256=digest, pod_id=active_runs.pod_id,
                       status='stop_acknowledged')
        # Retry only the durable acknowledgement, never the provider action.
        # A lost write readback may already have persisted the exact receipt.
        for attempt in range(2):
            try:
                prior_ack = journal.get(name)
                if prior_ack is not None:
                    if prior_ack != receipt:
                        raise ValueError('stop acknowledgement identity differs')
                    return
                journal.put(name, receipt, once=True)
                return
            except Exception:
                if attempt:
                    raise
    options = {'on_ack': acknowledge} if acknowledged_stop else {}
    return finish(stop(api, info['intent'], active_runs.pod_id, **options))
