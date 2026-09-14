"""Synthetic AWS lifecycle tests: no cloud calls or provider inference."""
from copy import deepcopy
from pathlib import Path
import pytest
import granite_deployment as d
import granite_startup as s
import granite_run_artifacts as a


@pytest.fixture(autouse=True)
def synthetic_account(monkeypatch):
    import hashlib
    monkeypatch.setattr(a,'APPROVED_ACCOUNT_SHA256',hashlib.sha256(b'123456789012').hexdigest())


def plan():
    return d.make_plan(account_sha_checked='123456789012',run_id='test1',max_model_len=4096,
                       served_model='granite42-test',now=1000)


def test_plan_pins_one_gpu_model_bytes_bootstrap_and_absolute_cleanup_deadline():
    p=plan()
    assert p['delete_deadline_epoch']==3700
    variant=p['endpoint_config']['ProductionVariants'][0]
    assert variant['InstanceType']=='ml.g6e.2xlarge' and variant['InitialInstanceCount']==1
    assert variant['ContainerStartupHealthCheckTimeoutInSeconds']==1200
    assert p['model']['PrimaryContainer']['Image'].endswith('@'+s.IMAGE_DIGEST)
    assert p['model']['PrimaryContainer']['Environment']==s.launch_environment(max_model_len=4096,served_model='granite42-test')
    assert p['model']['PrimaryContainer']['AdditionalModelDataSources'][0]['ChannelName']=='bootstrap'
    assert p['compute_budget_usd']=='2.10195'


class Missing(Exception):
    response={'Error':{'Code':'ResourceNotFound'}}


class Client:
    def __init__(self):self.models={};self.configs={};self.endpoints={};self.deleted=[]
    def describe_model(self,ModelName):
        if ModelName not in self.models:raise Missing()
        return self.models[ModelName]
    def describe_endpoint_config(self,EndpointConfigName):
        if EndpointConfigName not in self.configs:raise Missing()
        return self.configs[EndpointConfigName]
    def describe_endpoint(self,EndpointName):
        if EndpointName not in self.endpoints:raise Missing()
        return self.endpoints[EndpointName]
    def create_model(self,**args):self.models[args['ModelName']]=deepcopy(args);return {'ModelArn':'synthetic'}
    def create_endpoint_config(self,**args):self.configs[args['EndpointConfigName']]=deepcopy(args);return {'EndpointConfigArn':'synthetic'}
    def create_endpoint(self,**args):self.endpoints[args['EndpointName']]={**args,'EndpointStatus':'InService'};return {'EndpointArn':'synthetic'}
    def delete_endpoint(self,EndpointName):self.deleted.append('endpoint');self.endpoints.pop(EndpointName,None)
    def delete_endpoint_config(self,EndpointConfigName):self.deleted.append('config');self.configs.pop(EndpointConfigName,None)
    def delete_model(self,ModelName):self.deleted.append('model');self.models.pop(ModelName,None)


def test_creation_intents_persist_and_cleanup_confirms_absence_in_order(tmp_path):
    p=plan();client=Client();path=tmp_path/'ledger.json'
    receipt=d.create_resources(client,p,path,now=lambda:1001)
    assert receipt['status']=='created'
    assert len(receipt['intents'])==3
    assert d.inspect_resources(client,p)['endpoint']['EndpointStatus']=='InService'
    cleanup=d.cleanup_resources(client,p,path,now=lambda:1002,sleep=lambda _:None)
    assert cleanup['status']=='deleted'
    assert client.deleted==['endpoint','config','model']
    assert not client.endpoints and not client.configs and not client.models


def test_expired_plan_never_creates_gpu(tmp_path):
    client=Client()
    with pytest.raises(ValueError,match='expired'):d.create_resources(client,plan(),tmp_path/'ledger.json',now=lambda:4000)
    assert not client.endpoints and not client.models


def test_preexisting_resource_is_not_taken_over(tmp_path):
    p=plan();client=Client();client.models[p['model']['ModelName']]={'other':'owner'}
    with pytest.raises(ValueError):d.create_resources(client,p,tmp_path/'ledger.json',now=lambda:1001)
    assert not client.configs and not client.endpoints


def test_uncertain_endpoint_creation_can_be_cleaned_from_saved_intent(tmp_path):
    p=plan();client=Client();path=tmp_path/'ledger.json';original=client.create_endpoint
    def fail(**args):original(**args);raise TimeoutError('lost ack')
    client.create_endpoint=fail
    with pytest.raises(TimeoutError):d.create_resources(client,p,path,now=lambda:1001)
    assert a.strict_json(path.read_bytes())['intents'][-1]=='endpoint'
    d.cleanup_resources(client,p,path,now=lambda:1002,sleep=lambda _:None)
    assert not client.endpoints


def test_cleanup_does_not_delete_endpoint_with_drifted_config(tmp_path):
    p=plan();client=Client();path=tmp_path/'ledger.json'
    d.create_resources(client,p,path,now=lambda:1001)
    client.endpoints[p['endpoint']['EndpointName']]['EndpointConfigName']='other'
    with pytest.raises(ValueError):d.cleanup_resources(client,p,path,now=lambda:1002,sleep=lambda _:None)
    assert not client.deleted


@pytest.mark.parametrize('damage',['gpu-count','instance','deadline','account','image'])
def test_modified_deployment_plan_cannot_expand_authority(tmp_path,damage):
    p=plan();client=Client()
    if damage=='gpu-count':p['endpoint_config']['ProductionVariants'][0]['InitialInstanceCount']=2
    if damage=='instance':p['endpoint_config']['ProductionVariants'][0]['InstanceType']='ml.g6e.48xlarge'
    if damage=='deadline':p['delete_deadline_epoch']+=3600
    if damage=='account':p['model']['ExecutionRoleArn']='arn:aws:iam::000000000000:role/FrankieGraniteExecutionRole'
    if damage=='image':p['model']['PrimaryContainer']['Image']='floating:latest'
    with pytest.raises(ValueError):d.create_resources(client,p,tmp_path/'ledger.json',now=lambda:1001)
    assert not client.models and not client.endpoints


def test_server_added_description_metadata_is_not_config_drift(tmp_path):
    p=plan();client=Client();d.create_resources(client,p,tmp_path/'ledger.json',now=lambda:1001)
    client.models[p['model']['ModelName']]['PrimaryContainer']['Mode']='SingleModel'
    assert d.inspect_resources(client,p)['model']['PrimaryContainer']['Mode']=='SingleModel'


def test_delete_ack_loss_reconciles_actual_absence(tmp_path):
    p=plan();client=Client();path=tmp_path/'ledger.json';d.create_resources(client,p,path,now=lambda:1001)
    original=client.delete_endpoint
    def fail(**kw):original(**kw);raise TimeoutError('lost delete ack')
    client.delete_endpoint=fail
    receipt=d.cleanup_resources(client,p,path,now=lambda:1002,sleep=lambda _:None)
    assert receipt['status']=='deleted' and receipt['delete_errors'][0]['type']=='TimeoutError'


def test_cleanup_timeout_retains_failure_and_does_not_delete_config_early(tmp_path):
    p=plan();client=Client();path=tmp_path/'ledger.json';d.create_resources(client,p,path,now=lambda:1001)
    client.delete_endpoint=lambda **kw:None
    ticks=iter([1002,1003,5000])
    with pytest.raises(TimeoutError):d.cleanup_resources(client,p,path,now=lambda:next(ticks),sleep=lambda _:None)
    assert client.configs and client.models
    assert a.strict_json(path.read_bytes())['status']=='cleanup_failed'


def test_startup_receipt_requires_exact_marker_and_unique_identity():
    import json
    receipt={'schema':'GRANITE_STARTUP_RUNTIME_V1','image_digest':s.IMAGE_DIGEST}
    class Logs:
        def describe_log_streams(self,**kw):
            assert kw['logGroupName']=='/aws/sagemaker/Endpoints/frankie-granite42-test1-endpoint'
            return {'logStreams':[{'logStreamName':'AllTraffic/instance'}]}
        def get_log_events(self,**kw):
            return {'events':[{'message':'ordinary log'},{'message':'GRANITE_STARTUP_RECEIPT '+json.dumps(receipt)}],
                    'nextForwardToken':kw.get('nextToken','end')}
    assert d.startup_receipt(Logs(),plan())==receipt


def test_startup_receipt_rejects_two_different_reports():
    import json
    class Logs:
        def describe_log_streams(self,**kw):return {'logStreams':[{'logStreamName':'AllTraffic/instance'}]}
        def get_log_events(self,**kw):
            return {'events':[{'message':'GRANITE_STARTUP_RECEIPT '+json.dumps({'schema':'GRANITE_STARTUP_RUNTIME_V1','attempt':i})} for i in (1,2)],'nextForwardToken':kw.get('nextToken','end')}
    with pytest.raises(ValueError):d.startup_receipt(Logs(),plan())
