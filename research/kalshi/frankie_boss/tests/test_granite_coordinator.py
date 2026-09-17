"""Coordinator admission and cleanup tests; all runtime/AWS evidence is synthetic."""
from copy import deepcopy
import hashlib
import pytest
from research.kalshi.frankie_boss import granite_coordinator as c
from research.kalshi.frankie_boss import granite_deployment as d, granite_startup as s, granite_run_artifacts as a


def runtime():
    return dict(packages={'torch':'2.11.0+cu130','transformers':'5.8.0','tokenizers':'0.22.2',
        'vllm':'0.20.2','model-hosting-container-standards':'0.1.15'}, python='3.12.9',cuda='13.0',
        gpu_count=1,gpu='NVIDIA L40S',gpu_total_memory=48_000_000_000,driver='580.1',
        source_sha256=a.strict_json(s.IMAGE_IDENTITY_FILE.read_bytes())['source_sha256'])


@pytest.fixture
def evidence(monkeypatch):
    monkeypatch.setattr(a,'APPROVED_ACCOUNT_SHA256',hashlib.sha256(b'123456789012').hexdigest())
    plan=d.make_plan(account_sha_checked='123456789012',run_id='test',max_model_len=s.MAX_MODEL_LEN,served_model='granite42-test',now=1000)
    manifest=a.strict_json(a.DEFAULT_MANIFEST.read_bytes())
    mount=dict(schema='GRANITE_MOUNT_VERIFICATION_V1',manifest_sha256=a.manifest_digest(manifest),
        files=manifest['files'],bytes=sum(r['size'] for r in manifest['files']),verifier_sha256=s.digest_file(a.__file__))
    monkeypatch.setattr(a,'verify_directory',lambda *args,**kwargs:mount)
    receipt=s.prepare_startup('/opt/ml/model',manifest,plan['model']['PrimaryContainer']['Environment'],runtime_facts=runtime)
    receipt['argv']=[v.replace('\\','/') for v in receipt['argv']]
    return plan,manifest,receipt


def test_complete_runtime_receipt_admits(evidence):
    plan,manifest,receipt=evidence
    c.validate_startup(receipt,plan,manifest)


@pytest.mark.parametrize('damage',['extra','manifest','bytes','roster','verifier','image','bootstrap','argv','env',
    'generation','package','gpu_count','gpu','gpu_memory','cuda','source','python','driver'])
def test_full_runtime_mutations_refuse(evidence,damage):
    plan,manifest,receipt=evidence
    receipt=deepcopy(receipt)
    if damage=='extra':receipt['extra']='unapproved'
    elif damage=='manifest':receipt['mount']['manifest_sha256']='0'*64
    elif damage=='bytes':receipt['mount']['bytes']-=1
    elif damage=='roster':receipt['mount']['files']=receipt['mount']['files'][:-1]
    elif damage=='verifier':receipt['mount']['verifier_sha256']='0'*64
    elif damage=='image':receipt['image_digest']='sha256:'+'0'*64
    elif damage=='bootstrap':receipt['bootstrap_sha256']='0'*64
    elif damage=='argv':receipt['argv']+=['--enable-lora']
    elif damage=='env':receipt['environment']['HF_HUB_OFFLINE']='0'
    elif damage=='generation':receipt['generation_policy']['thinking']=True
    elif damage=='package':receipt['runtime']['packages']['tokenizers']='0.0.0'
    elif damage=='gpu_count':receipt['runtime']['gpu_count']=2
    elif damage=='gpu':receipt['runtime']['gpu']='OTHER'
    elif damage=='gpu_memory':receipt['runtime']['gpu_total_memory']=1
    elif damage=='cuda':receipt['runtime']['cuda']='12.0'
    elif damage=='source':receipt['runtime']['source_sha256']={}
    elif damage=='python':receipt['runtime']['python']='3.11.1'
    elif damage=='driver':receipt['runtime']['driver']=''
    with pytest.raises(ValueError):c.validate_startup(receipt,plan,manifest)


@pytest.mark.parametrize('failure',['create','ready','receipt','validate','invoke',None])
def test_hosted_sequence_always_cleans_up_and_retains_failures(tmp_path,monkeypatch,evidence,failure):
    plan,manifest,receipt=evidence
    events=[]
    def step(name,result=None):
        def call(*args,**kwargs):
            events.append(name)
            if failure==name:raise RuntimeError(name+' failed')
            return result
        return call
    monkeypatch.setattr(d,'create_resources',step('create'))
    monkeypatch.setattr(d,'wait_ready',step('ready',{'endpoint':{'EndpointStatus':'InService'}}))
    monkeypatch.setattr(d,'startup_receipt',step('receipt',receipt))
    monkeypatch.setattr(c,'validate_startup',step('validate'))
    monkeypatch.setattr(d,'inspect_resources',step('inspect',{}))
    monkeypatch.setattr(d,'cleanup_resources',step('cleanup',{'status':'deleted','absence_confirmed':['endpoint','endpoint_config','model']}))
    invoke=step('invoke',{'integration_status':'complete'})
    if failure:
        with pytest.raises(RuntimeError):c.hosted_sequence(None,None,plan,manifest,tmp_path,invoke,now=lambda:1001,sleep=lambda _:None)
        assert a.strict_json((tmp_path/'failure.json').read_bytes())['type']=='RuntimeError'
    else:
        assert c.hosted_sequence(None,None,plan,manifest,tmp_path,invoke,now=lambda:1001,sleep=lambda _:None)['integration_status']=='complete'
    assert events[-1]=='cleanup'
    assert (tmp_path/'cleanup.json').exists()


def test_existing_ledger_refuses_before_cleanup_of_someone_elses_run(tmp_path,evidence):
    plan,manifest,_=evidence
    (tmp_path/'deployment-ledger.json').write_text('{}')
    with pytest.raises(ValueError,match='existing'):
        c.hosted_sequence(None,None,plan,manifest,tmp_path,lambda _:pytest.fail('invoked'))


def test_runtime_boolean_cannot_impersonate_numeric_policy(evidence):
    plan,manifest,receipt=evidence
    receipt['generation_policy']['temperature']=False
    with pytest.raises(ValueError):c.validate_startup(receipt,plan,manifest)


def test_cleanup_failure_is_retained_not_reported_as_success(tmp_path,monkeypatch,evidence):
    plan,manifest,receipt=evidence
    monkeypatch.setattr(d,'create_resources',lambda *args,**kwargs:None)
    monkeypatch.setattr(d,'wait_ready',lambda *args,**kwargs:{})
    monkeypatch.setattr(d,'startup_receipt',lambda *args,**kwargs:receipt)
    monkeypatch.setattr(d,'inspect_resources',lambda *args,**kwargs:{})
    def failed(*args,**kwargs):raise TimeoutError('not deleted')
    monkeypatch.setattr(d,'cleanup_resources',failed)
    with pytest.raises(TimeoutError):
        c.hosted_sequence(None,None,plan,manifest,tmp_path,lambda _:dict(integration_status='complete'),now=lambda:1001)
    assert a.strict_json((tmp_path/'cleanup-failure.json').read_bytes())['type']=='TimeoutError'


def test_log_failure_retained_with_service_details_and_redaction(tmp_path):
    class Failure(Exception):
        response={'Error':{'Code':'ResourceNotFoundException','Message':'log group absent'},
                  'ResponseMetadata':{'RequestId':'log-request'}}
    class Logs:
        def describe_log_streams(self,**kwargs):raise Failure('Bearer private-value')
    with pytest.raises(Failure):c.RecordedLogs(Logs(),tmp_path).describe_log_streams(logGroupName='owned')
    result=a.strict_json((tmp_path/'logs-00001.json').read_bytes())
    assert result['failure']['response']['Error']['Message']=='log group absent'
    assert result['failure']['response']['ResponseMetadata']['RequestId']=='log-request'
    assert 'private-value' not in str(result)
