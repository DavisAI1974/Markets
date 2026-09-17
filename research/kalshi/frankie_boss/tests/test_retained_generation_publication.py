"""A completed native outcome must reach its reviewed observer generation."""
import hashlib
import io
import json
from pathlib import Path
import boto3
import yaml
from research.kalshi.frankie_boss.granite_retained_completion import CompletionJournal, publish_completion, canonical
from research.kalshi.frankie_boss.granite_retained_host import JOURNAL_GENERATION

def test_completion_keeps_failed_generation_untouched(monkeypatch):
    request = 'a' * 64
    old = 'retained-granite/' + request + '/migration-ycf4v6lmave6xw/'
    current = 'retained-granite/' + request + '/' + JOURNAL_GENERATION + '/'
    startup = dict(request_sha256=request, pod_id='ycf4v6lmave6xw', local_ready={'host_instance_id': 'new'})
    old_body = canonical(dict(request_sha256=request, pod_id='ycf4v6lmave6xw', local_ready={'host_instance_id': 'old'}))
    objects = {old + 'retained-startup.json': old_body, current + 'retained-startup.json': canonical(startup)}
    class Missing(Exception):
        response = {'Error': {'Code': 'NoSuchKey'}}
    class Client:
        def get_object(self, **kwargs):
            if kwargs['Key'] not in objects:
                raise Missing()
            body = objects[kwargs['Key']]
            return dict(Body=io.BytesIO(body), ContentLength=len(body))
        def put_object(self, **kwargs):
            assert kwargs['IfNoneMatch'] == '*' and kwargs['ServerSideEncryption'] == 'AES256'
            assert kwargs['Key'] not in objects
            objects[kwargs['Key']] = kwargs['Body']
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: Client())
    journal = CompletionJournal(request)
    fields = dict(request_sha256=request, startup_sha256=hashlib.sha256(canonical(startup)).hexdigest(),
                  outcome_sha256='b'*64, job_id='c'*64, code_commit='d'*40)
    publish_completion(journal, fields)
    assert objects[old + 'retained-startup.json'] == old_body
    assert old + 'retained-finished.json' not in objects
    assert json.loads(objects[current + 'retained-finished.json']) == {'startup_sha256': fields['startup_sha256']}

def test_publication_workflow_keeps_native_checkout_validation():
    root = Path(__file__).resolve().parents[4]
    value = yaml.safe_load((root/'.github/workflows/frankie_retained_completion.yml').read_text())
    steps = value['jobs']['publish']['steps']
    native = next(step for step in steps if step.get('with', {}).get('path') == 'native')
    publisher = next(step for step in steps if step.get('with', {}).get('path') == 'publication')
    execution = next(step for step in steps if step.get('name') == 'Publish exact completed outcome to independent observer')
    assert native['with']['ref'] == '${{ inputs.code_commit }}'
    assert publisher['with']['ref'] == '${{ github.sha }}'
    assert execution['working-directory'] == 'native'
    assert execution['run'] == 'python ../publication/research/kalshi/frankie_boss/granite_retained_completion.py'
