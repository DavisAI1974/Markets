"""Publish the local host's durable outcome witness to the independent watchdog.

This writer never calls a Pod or model API. The authenticated workflow accepts
only hashes, after the actual host has persisted the complete backend outcome.
"""
import hashlib
import json
import os
import re


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


FIELDS = {'request_sha256', 'startup_sha256', 'outcome_sha256', 'job_id', 'code_commit'}


def publish_completion(journal, fields):
    if (type(fields) is not dict or set(fields) != FIELDS
            or any(type(value) is not str or not re.fullmatch(
                '[0-9a-f]{40}' if key == 'code_commit' else '[0-9a-f]{64}', value)
                for key, value in fields.items())):
        raise ValueError('exact completion hashes required')
    startup = journal.get('retained-startup.json')
    if (type(startup) is not dict or startup.get('request_sha256') != fields['request_sha256']
            or startup.get('pod_id') != 'jvs75m56w8f73q'
            or hashlib.sha256(canonical(startup)).hexdigest() != fields['startup_sha256']):
        raise ValueError('completion differs from retained startup')
    for name, value in (
            ('retained-completed-outcome.json', fields),
            ('retained-finished.json', {'startup_sha256': fields['startup_sha256']})):
        previous = journal.get(name)
        if previous is not None:
            if previous != value:
                raise ValueError('existing completion evidence differs')
        else:
            journal.put(name, value, once=True)
    return {'status': 'completion_published', **fields}


def main():
    fields = {key: os.environ[key.upper()] for key in FIELDS}
    if fields['code_commit'] != os.environ['GITHUB_SHA']:
        raise ValueError('completion workflow checkout differs from actual host code')
    # Validate before placing user-supplied bytes in a journal path.
    if not re.fullmatch('[0-9a-f]{64}', fields['request_sha256']):
        raise ValueError('exact request digest required')
    journal = CompletionJournal(fields['request_sha256'])
    print(canonical(publish_completion(journal, fields)).decode())


class CompletionJournal:
    """Only the existing scoped bucket and this request's three journal objects."""
    def __init__(self, request_sha256):
        import boto3
        from botocore.config import Config
        self.client = boto3.client('s3', region_name='us-east-1', config=Config(
            connect_timeout=5, read_timeout=10,
            retries={'total_max_attempts': 2, 'mode': 'standard'}))
        self.bucket = 'frankie-granite42-568968024170-us-east-1'
        self.prefix = 'retained-granite/' + request_sha256 + '/'

    def get(self, name):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.prefix+name)
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404'):
                return None
            raise
        with response['Body'] as stream:
            raw = stream.read(8193)
        if len(raw) > 8192 or len(raw) != response['ContentLength']:
            raise ValueError('invalid completion journal size')
        return json.loads(raw)

    def put(self, name, value, *, once):
        if not once or name not in ('retained-completed-outcome.json', 'retained-finished.json'):
            raise ValueError('only immutable completion witnesses may be written')
        self.client.put_object(Bucket=self.bucket, Key=self.prefix+name,
            Body=canonical(value), IfNoneMatch='*', ServerSideEncryption='AES256',
            ContentType='application/json')
        if self.get(name) != value:
            raise ValueError('completion write readback differs')


if __name__ == '__main__':
    main()
