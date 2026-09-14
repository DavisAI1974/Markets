import asyncio
import hashlib
import io
import json

import pytest

from research.kalshi.frankie_boss import granite_live_controller as live
from research.kalshi.frankie_boss.granite_context_route import context_route
from research.kalshi.frankie_boss.granite_contract import SCHEMA_VERSION
from research.kalshi.frankie_boss.granite_shadow import GraniteIdentity
from research.kalshi.frankie_boss.granite_sagemaker import SageMakerConfig


def identity():
    route = context_route('compact_v1')
    # Test-only runtime pins; hosted harness must derive real manifest identities.
    return GraniteIdentity('a'*64,None,'b'*64,'none','TEST_ONLY_RUNTIME',False,0,1200,
        hashlib.sha256(route.system_text.encode()).hexdigest(),SCHEMA_VERSION,route.parser_code_hash(),None)


def config():
    return SageMakerConfig('us-east-1','frankie-granite42-test','granite-test',True,1.,2.,3.)


def test_preparation_freezes_identical_source_context_and_state_without_forward(tmp_path, monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError('predeployment preparation must not infer')
    monkeypatch.setattr(live.B1Reasoner, 'forward_decision', forbidden)
    first = live.prepare_fixture(tmp_path/'one')
    second = live.prepare_fixture(tmp_path/'two')
    try:
        assert first.snapshot.text == second.snapshot.text
        assert first.manifest == second.manifest
        assert first.bridge.book.checkpoint()['count'] == 0
        assert first.manifest['source']['records'] == 1
        assert first.manifest['source']['kind'] == 'SYNTHETIC_PROBE_ONLY'
        for member in first.manifest['files']:
            assert (first.directory/member['path']).read_bytes() == (second.directory/member['path']).read_bytes()
    finally:
        first.close(); second.close()


@pytest.mark.parametrize('malformed', [False,True])
def test_actual_service_and_controller_keep_outcome_and_zero_work_retry(tmp_path, malformed):
    fixture = live.prepare_fixture(tmp_path/'fixture')
    requests = []
    class SDK:
        def invoke_endpoint(self, **kwargs):
            payload = json.loads(kwargs['Body'])
            requests.append(kwargs)
            assert payload['messages'] == [{'role':'user','content':fixture.prompt.text}]
            output = dict(schema_version=SCHEMA_VERSION,snapshot_hash=fixture.snapshot.hash,evidence_refs=[],
                contradictions=[],missing_evidence=[],hypotheses=[dict(label='synthetic',support=[],against=[])],
                evidence_verdict='INSUFFICIENT')
            text = 'not json' if malformed else json.dumps(output)
            response = dict(object='chat.completion',model='granite-test',choices=[dict(index=0,
                finish_reason='stop',message=dict(role='assistant',content=text))])
            return dict(ContentType='application/json', Body=io.BytesIO(json.dumps(response).encode()))
    try:
        receipt = asyncio.run(live.run_fixture(fixture,config=config(),identity=identity(),
            expected_prompt_sha256=fixture.manifest['prompt_sha256'],client_factory=lambda _:SDK()))
        assert receipt['calls'] == dict(native_forwards=3,provider_calls=1)
        assert receipt['result']['status'] == ('incomplete' if malformed else 'complete')
        assert len(receipt['result']['records']) == 3
        assert len(requests) == 1 and receipt['retry_identical']
        assert (fixture.directory/'provider-requests.c15.json').is_file()
    finally:
        fixture.close()


@pytest.mark.parametrize('kind',['prompt','file','source','request','endpoint','identity'])
def test_refuses_bad_admission_before_any_provider_or_native_publication(tmp_path, kind):
    from dataclasses import replace
    fixture = live.prepare_fixture(tmp_path/'fixture')
    pin = fixture.manifest['prompt_sha256']
    selected_config, selected_identity = config(), identity()
    if kind == 'prompt': pin = '0'*64
    if kind == 'file': (fixture.directory/'compact-prompt.txt').write_bytes(b'changed')
    if kind == 'source': (fixture.directory/'synthetic-source.c15.json').write_bytes(b'changed')
    if kind == 'request': fixture.request['metadata'][0][1]['reasoning'] = 'changed after freeze'
    if kind == 'endpoint': selected_config = replace(selected_config,region='us-west-2')
    if kind == 'identity': selected_identity = replace(selected_identity,parser_code_hash='0'*64)
    def forbidden(*args):
        pytest.fail('refused input must not make SDK client')
    try:
        with pytest.raises(ValueError):
            asyncio.run(live.run_fixture(fixture,config=selected_config,identity=selected_identity,
                expected_prompt_sha256=pin,client_factory=forbidden))
        assert fixture.bridge.book.checkpoint()['count'] == 0
    finally:
        fixture.close()


def test_real_client_default_refuses_unmeasured_input(tmp_path):
    fixture = live.prepare_fixture(tmp_path/'fixture')
    try:
        with pytest.raises(ValueError, match='measured tokenizer admission'):
            asyncio.run(live.run_fixture(fixture,config=config(),identity=identity(),
                expected_prompt_sha256=fixture.manifest['prompt_sha256']))
        assert fixture.bridge.book.checkpoint()['count'] == 0
    finally:
        fixture.close()


@pytest.mark.parametrize('output_tokens',[1200,4096])
def test_capacity_counts_complete_template_and_refuses_oversize(tmp_path,monkeypatch,output_tokens):
    import sys
    from types import SimpleNamespace
    from research.kalshi.frankie_boss import granite_run_artifacts as artifacts
    fixture = live.prepare_fixture(tmp_path/'fixture')
    directory = tmp_path/'tokenizer'
    directory.mkdir()
    rows = []
    for name in sorted(artifacts.FILES):
        data = json.dumps({'max_position_embeddings':4096}).encode() if name == 'config.json' else name.encode()
        rows.append(dict(path=name,size=len(data),sha256=hashlib.sha256(data).hexdigest()))
        if name in live.TOKENIZER_FILES:
            (directory/name).write_bytes(data)
    manifest_path = tmp_path/'manifest.json'
    manifest_path.write_text(json.dumps(dict(schema='GRANITE_ARTIFACT_MANIFEST_V1',
        repository=artifacts.REPOSITORY,revision=artifacts.REVISION,files=rows)))
    monkeypatch.setattr(artifacts,'DEFAULT_MANIFEST',manifest_path)
    monkeypatch.setattr(live.importlib.metadata,'version',lambda name:live.TOKENIZER_VERSIONS[name])
    class Tokenizer:
        @staticmethod
        def from_pretrained(path,**kwargs):
            assert path == str(directory) and kwargs == dict(local_files_only=True,trust_remote_code=False)
            return Tokenizer()
        def apply_chat_template(self,messages,**kwargs):
            assert messages == [dict(role='user',content=fixture.prompt.text)]
            assert kwargs == dict(tokenize=True,add_generation_prompt=True,enable_thinking=False)
            return [17,18,19]
    monkeypatch.setitem(sys.modules,'transformers',SimpleNamespace(AutoTokenizer=Tokenizer))
    try:
        if output_tokens == 4096:
            with pytest.raises(ValueError,match='exceed model positional limit'):
                live.measure_fixture(fixture,directory,output_tokens=output_tokens)
            assert not (fixture.directory/'token-admission.json').exists()
        else:
            admission=live.measure_fixture(fixture,directory,output_tokens=output_tokens)
            assert admission['max_model_len'] == admission['input_tokens']+output_tokens == 1203
            assert json.loads((fixture.directory/'chat-token-ids.json').read_bytes()) == [17,18,19]
    finally:
        fixture.close()
