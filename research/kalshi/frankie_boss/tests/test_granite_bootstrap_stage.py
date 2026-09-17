import hashlib
import io
import json
import pytest

from research.kalshi.frankie_boss import granite_bootstrap_stage as stage


class Missing(Exception):
    response = {'Error': {'Code': 'NoSuchKey'}}


class Client:
    def __init__(self): self.objects = {}; self.puts = []
    def get_object(self, *, Bucket, Key):
        if Key not in self.objects: raise Missing()
        body = self.objects[Key]
        return dict(Body=io.BytesIO(body), ContentLength=len(body), ServerSideEncryption='AES256')
    def put_object(self, **kwargs):
        assert kwargs['IfNoneMatch'] == '*'
        assert kwargs['ServerSideEncryption'] == 'AES256'
        assert kwargs['Key'] not in self.objects
        assert kwargs['ChecksumSHA256'] == stage.base64.b64encode(hashlib.sha256(kwargs['Body']).digest()).decode()
        self.objects[kwargs['Key']] = kwargs['Body']; self.puts.append(kwargs)
    def generate_presigned_url(self, operation, *, Params, ExpiresIn, HttpMethod):
        assert operation == 'get_object' and HttpMethod == 'GET'
        return 'https://'+Params['Bucket']+'.s3.us-east-1.amazonaws.com/'+Params['Key']+'?X-Amz-Expires='+str(ExpiresIn)


def bundle(tmp_path):
    rows = []
    for name in stage.package.FILES:
        body = ('synthetic '+name).encode(); (tmp_path/name).write_bytes(body)
        rows.append(dict(path=name, size=len(body), sha256=hashlib.sha256(body).hexdigest()))
    raw = stage.canonical(dict(schema='GRANITE_RUNPOD_BUNDLE_V1', files=rows))
    (tmp_path/'runpod_bundle.json').write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_conditional_writes_readback_and_existing_reuse(tmp_path):
    digest = bundle(tmp_path); client = Client()
    result = stage.stage_bundle(client, tmp_path, digest, now=lambda: 1000)
    staged = len(stage.package.FILES)+1  # the roster plus runpod_bundle.json
    assert len(client.puts) == staged and len(result['urls']) == staged
    assert result['expires_at'] == 1900 and result['pod_actions'] == 0
    stage.stage_bundle(client, tmp_path, digest)
    assert len(client.puts) == staged


def test_changed_local_file_refused_before_any_remote_operation(tmp_path):
    digest = bundle(tmp_path); client = Client()
    (tmp_path/stage.package.FILES[-1]).write_bytes(b'changed')
    with pytest.raises(ValueError, match='bytes differ'): stage.stage_bundle(client, tmp_path, digest)
    assert not client.puts and not client.objects


def test_existing_digest_object_collision_is_preserved_and_refused(tmp_path):
    digest = bundle(tmp_path); client = Client()
    key = stage.PREFIX+digest+'/'+stage.package.FILES[0]
    client.objects[key] = b'collision'
    with pytest.raises(ValueError, match='stored bootstrap differs'): stage.stage_bundle(client, tmp_path, digest)
    assert client.objects[key] == b'collision' and not client.puts


def test_download_origins_match_retained_cloud_bootstrap_verifier(tmp_path):
    import ast
    import shlex
    from research.kalshi.frankie_boss import granite_runpod_cloud as cloud
    digest = bundle(tmp_path)
    result = stage.stage_bundle(Client(), tmp_path, digest)
    command = cloud.bootstrap_command(result['files'], digest, stage.BUCKET,
        directory=stage.DIRECTORY, open_ended=True)
    wrapper = ast.parse(shlex.split(command)[2])
    hex_source = wrapper.body[0].value.args[0].func.value.args[0].value
    source = bytes.fromhex(hex_source).decode()
    origin_guard = next(line for line in source.splitlines() if 'bootstrap origin refused' in line)
    for url in result['urls'].values():
        host = stage.urlsplit(url).hostname
        assert repr(host) in origin_guard
    assert stage.BUCKET == 'frankie-granite42-568968024170-us-east-1'
