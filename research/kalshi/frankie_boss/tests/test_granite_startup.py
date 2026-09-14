"""Startup receipt tests use injected runtime facts, not GPU claims."""
from pathlib import Path
import hashlib
import json
import pytest
import granite_startup as s
import granite_run_artifacts as a
from test_granite_run_artifacts import fixture


def runtime_fixture():
    return {'packages':{'vllm':'0.20.2','model-hosting-container-standards':'0.1.15'},
            'gpu_count':1,'gpu':'synthetic-only',
            'source_sha256':a.strict_json(s.IMAGE_IDENTITY_FILE.read_bytes())['source_sha256']}


def test_bootstrap_environment_uses_pinned_supervisor_command_and_no_model_download():
    env=s.launch_environment(max_model_len=4096,served_model='granite42-test')
    assert env['SUPERVISOR_PROGRAM__APP_COMMAND']=='python3 /opt/ml/additional-model-data-sources/bootstrap/granite_startup.py'
    assert env['HF_HUB_OFFLINE']=='1'
    assert env['STANDARD_AUTO_INSTALL_REQ']=='false'
    assert env['SUPERVISOR_PROGRAM__APP_AUTORESTART']=='false'
    assert env['GRANITE_MAX_MODEL_LEN']=='4096'
    assert all(len(k.encode())<=1024 and len(v.encode())<=1024 for k,v in env.items())
    assert sum(len(k.encode())+len(v.encode()) for k,v in env.items())<32768


@pytest.mark.parametrize('length',[True,0,-1,1.5,'4096'])
def test_bootstrap_requires_explicit_positive_runtime_context(length):
    with pytest.raises(ValueError):s.launch_environment(max_model_len=length,served_model='granite42-test')


def test_bootstrap_uses_real_file_receipt_and_explicit_generation_limits(tmp_path):
    manifest,_=fixture(tmp_path)
    env=s.launch_environment(max_model_len=4096,served_model='granite42-test')
    env['GRANITE_MANIFEST_SHA256']=a.manifest_digest(manifest)
    facts=runtime_fixture()
    receipt=s.prepare_startup(tmp_path,manifest,env,runtime_facts=lambda:facts)
    assert receipt['mount']['manifest_sha256']==a.manifest_digest(manifest)
    assert receipt['runtime']==facts
    args=receipt['argv']
    assert args[0:3]==['python3','-m','vllm.entrypoints.openai.api_server']
    assert args[args.index('--model')+1]==str(tmp_path)
    assert args[args.index('--max-model-len')+1]=='4096'
    assert args[args.index('--max-num-seqs')+1]=='1'
    assert '--trust-remote-code' not in args
    assert '--enable-lora' not in args
    assert '--speculative-config' not in args
    assert args[args.index('--generation-config')+1]=='vllm'


@pytest.mark.parametrize('damage',['model','manifest-pin','source-pin','extra-supervisor','zero-gpu','two-gpu','runtime-source'])
def test_startup_fails_before_server_on_any_identity_or_gpu_mismatch(tmp_path,damage):
    manifest,_=fixture(tmp_path)
    env=s.launch_environment(max_model_len=4096,served_model='granite42-test')
    env['GRANITE_MANIFEST_SHA256']=a.manifest_digest(manifest)
    facts=runtime_fixture()
    if damage=='model':(tmp_path/'config.json').write_bytes(b'corrupt')
    if damage=='manifest-pin':env['GRANITE_MANIFEST_SHA256']='0'*64
    if damage=='source-pin':env['GRANITE_VERIFIER_SHA256']='0'*64
    if damage=='extra-supervisor':env['SUPERVISOR_PROGRAM__OTHER_COMMAND']='unapproved'
    if damage=='zero-gpu':facts['gpu_count']=0
    if damage=='two-gpu':facts['gpu_count']=2
    if damage=='runtime-source':facts['source_sha256']={}
    with pytest.raises(ValueError):s.prepare_startup(tmp_path,manifest,env,runtime_facts=lambda:facts)


def test_bootstrap_stages_only_its_four_files_and_verifies_readback(tmp_path):
    from test_granite_run_artifacts import S3
    manifest=s.bootstrap_manifest();digest=hashlib.sha256(a.canonical(manifest)).hexdigest()
    prefix='models/bootstrap/'+digest+'/'
    client=S3({},prefix)
    def upload_file(path,bucket,key,**kwargs):client.blobs[key]=Path(path).read_bytes()
    client.upload_file=upload_file
    receipt=s.stage_bootstrap(client,'synthetic-bucket',tmp_path/'receipt.json')
    assert receipt['status']=='verified'
    assert set(client.blobs)=={prefix+row['path'] for row in manifest['files']}
    assert len(receipt['files'])==4


def test_existing_bootstrap_corruption_rejects_before_any_new_upload(tmp_path):
    from test_granite_run_artifacts import S3
    manifest=s.bootstrap_manifest();digest=hashlib.sha256(a.canonical(manifest)).hexdigest()
    prefix='models/bootstrap/'+digest+'/'
    row=next(row for row in manifest['files'] if row['path']=='granite_startup.py')
    client=S3({row['path']:b'!'*row['size']},prefix)
    client.upload_file=lambda *args,**kwargs:pytest.fail('verify existing bytes before writes')
    with pytest.raises(ValueError):s.stage_bootstrap(client,'synthetic-bucket',tmp_path/'receipt.json')
