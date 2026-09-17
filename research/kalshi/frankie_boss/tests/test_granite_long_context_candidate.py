"""New explicit long-context startup seams, no real server or model calls."""
import json
import pytest
import granite_startup as startup
import granite_runpod as runpod
from test_granite_run_artifacts import fixture
from test_granite_startup import runtime_fixture
from research.kalshi.frankie_boss.granite_runpod_service import RunpodConfig


def test_explicit_open_ended_long_candidate_preserves_legacy_finite_hash():
    legacy=RunpodConfig('retainedpod','granite42',60,'a'*64)
    assert legacy.config_hash=='7bd357cc175fc4bef45232268f0b1ba8ee26e385799845bc4a6c1b6f0db72b3b'
    candidate=RunpodConfig('retainedpod','granite42',None,'a'*64,131072)
    assert candidate.config_hash!=legacy.config_hash
    with pytest.raises(ValueError):RunpodConfig('retainedpod','granite42',60,'a'*64,131072)


@pytest.mark.parametrize('length',[8192,65536,131073])
def test_unsupported_context_rejected_in_startup_and_service(length):
    with pytest.raises(ValueError):startup.launch_environment(max_model_len=length,served_model='granite42')
    with pytest.raises(ValueError):RunpodConfig('retainedpod','granite42',None,'a'*64,length)


def test_long_startup_parent_exact_prefill_argv_and_override_rejection(tmp_path,monkeypatch):
    manifest,_=fixture(tmp_path)
    manifest_path=tmp_path/'packaged-manifest.json';manifest_path.write_text(json.dumps(manifest))
    # Startup's verified model fixture must have no extra manifest file.
    manifest_path=tmp_path.parent/(tmp_path.name+'-manifest.json');manifest_path.write_text(json.dumps(manifest))
    (tmp_path/'packaged-manifest.json').unlink()
    monkeypatch.setattr(startup.artifacts,'DEFAULT_MANIFEST',manifest_path)
    env=startup.launch_environment(max_model_len=131072,served_model='granite42')
    receipt=startup.prepare_startup(tmp_path,manifest,env,runtime_facts=runtime_fixture)
    assert receipt['argv'][-3:]==['--enable-chunked-prefill','--max-num-batched-tokens','2048']
    with pytest.raises(ValueError):startup.launch_environment(max_model_len=4096,served_model='granite42')
    class Child:
        def wait(self,timeout):return 0
    def spawn(argv,**kwargs):
        from pathlib import Path
        Path(argv[-1]).write_text(json.dumps(receipt));return Child()
    monkeypatch.setattr(runpod,'stop_children',lambda _:None)
    assert runpod.prepare_process(tmp_path,manifest,env,deadline=None,popen=spawn)['argv']==receipt['argv']
    receipt['argv'][-1]='8192'
    with pytest.raises(ValueError,match='arguments'):runpod.prepare_process(tmp_path,manifest,env,deadline=None,popen=spawn)
    with pytest.raises(ValueError,match='override'):
        startup.prepare_startup(tmp_path,manifest,dict(env,VLLM_ENABLE_CHUNKED_PREFILL='0'),runtime_facts=runtime_fixture)


def test_long_tokenizer_candidate_measures_entire_request_at_explicit_boundary(tmp_path):
    from test_granite_runpod_tokenizer import synthetic,request
    from research.kalshi.frankie_boss import granite_runpod_tokenizer as tokenizer
    ids=[1]*(131072-1200)
    options,calls,loads=synthetic(tmp_path,ids)
    candidate=tokenizer.LocalTokenizerAdmission(tmp_path,context=131072,**options)
    receipt=candidate(request('actual full request remains unchanged'))
    assert receipt['context']==131072 and receipt['input_tokens']==129872
    assert len(loads)==1 and len(calls)==1 and calls[0][1]['truncation'] is False
    ids.append(2)
    with pytest.raises(ValueError,match='exceed admitted context'):candidate(request('different full input'))
    assert len(calls)==2
