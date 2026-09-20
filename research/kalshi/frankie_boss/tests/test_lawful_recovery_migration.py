import hashlib
import json
from pathlib import Path

from research.kalshi.frankie_boss import granite_cloud_resume as resume
from research.kalshi.frankie_boss import granite_retained_lifecycle as lifecycle
from research.kalshi.frankie_boss import granite_runpod
from research.kalshi.frankie_boss import granite_runpod_cloud_control as control
from research.kalshi.frankie_boss.journal_prefix_snapshot import _sidecars


def _intent(*, migrated=True):
    nonce='4e2ecee03d7b2bb77da16180aba4f98d'
    return dict(schema='GRANITE_CLOUD_INTENT_V1', nonce=nonce,
        name='granite-smoke-'+nonce+('-migration' if migrated else ''),
        image=granite_runpod.IMAGE, start=100.0, deadline=700.0,
        cleanup_mode='stop_retain')


def test_migrated_intent_name_is_explicitly_accepted():
    intent=_intent()
    assert control.validate_intent(intent) is intent


def test_retained_migration_receipt_pins_current_pod():
    path=Path(__file__).resolve().parents[1]/'granite_retained_migration_receipt.json'
    value=json.loads(path.read_bytes())
    assert value['schema']=='GRANITE_POD_MIGRATION_V1'
    assert value['source_pod_id']=='jvs75m56w8f73q'
    assert value['pod']['id']==lifecycle.POD_ID=='8vqdacl5t61rjx'
    assert value['pod']['status']=='RUNNING'


def test_validate_running_migration_restores_recorded_status(monkeypatch):
    info=dict(intent=dict(name='granite-smoke-x-migration'),pod=dict(status='RUNNING'))
    observed=dict(status='RUNNING')
    calls=[]
    def fake_validate(current,pod,manifest):
        calls.append((current['pod']['status'],pod['status'],manifest))
        return dict(pod=dict(status='EXITED'))
    monkeypatch.setattr(resume,'validate_resume',fake_validate)
    result=resume.validate_running_migration(info,observed,{'manifest':1})
    assert calls==[('EXITED','EXITED',{'manifest':1})]
    assert info['pod']['status']=='RUNNING'
    assert result['pod']['status']=='RUNNING'


def test_running_migration_is_observed_without_second_start(monkeypatch):
    request_body=b'lawful-request'
    request_hash=hashlib.sha256(request_body).hexdigest()
    digest='d'*64

    class Admission:
        evidence_class='LOCAL_TOKENIZER_ADMISSION'
        def __call__(self,body):
            assert body==request_body
            return dict(request_sha256=request_hash,context=4096,input_tokens=1,output_tokens=1)
    monkeypatch.setattr(lifecycle,'LocalTokenizerAdmission',Admission)
    monkeypatch.setattr(lifecycle,'check_startup',lambda startup,info:digest)
    monkeypatch.setattr(lifecycle,'_watchdog',lambda identity,lease:None)

    from research.kalshi.frankie_boss import granite_startup_pins
    monkeypatch.setattr(granite_startup_pins,'validate_configuration',lambda value:{'service_context':4096})
    monkeypatch.setattr(granite_startup_pins,'validate_url_freshness',lambda pod,configuration,now:999.0)
    monkeypatch.setattr(resume,'validate_running_migration',lambda info,pod,manifest:dict(info))

    class Journal:
        def __init__(self): self.values={}
        def get(self,name):
            if name=='retained-start-intent.json': return None
            if name=='retained-observer.json':
                return dict(startup_sha256=digest,watchdog_identity={'id':1},at=10.0)
            return self.values.get(name)
        def put(self,name,value,once=False): self.values[name]=value
    class API:
        def __init__(self): self.calls=[]
        def request(self,method,path,body=None):
            self.calls.append((method,path,body))
            assert method=='GET'
            return dict(status='RUNNING',env={})
    class Runs:
        pod_id=lifecycle.POD_ID
        def __init__(self): self.claimed=[]
        def claim(self,digest_value): self.claimed.append(digest_value)

    journal=Journal();api=API();runs=Runs()
    info=dict(intent=_intent())
    startup=dict(request_sha256=request_hash)
    result=lifecycle.start_once(api,journal,info,{},startup,now=10.0,
        request_body=request_body,tokenizer_admission=Admission(),
        expected_watchdog_identity={'id':1},active_runs=runs,runtime_configuration={})

    assert result==dict(status='observe_migrated_start',pod_id=lifecycle.POD_ID,startup_sha256=digest)
    assert api.calls==[('GET','/v2/pods/'+lifecycle.POD_ID,None)]
    assert runs.claimed==[digest]
    assert journal.values['retained-start-result.json']==result


def test_read_only_sidecar_residue_is_not_hot(tmp_path):
    source=tmp_path/'source.sqlite'
    Path(str(source)+'-shm').write_bytes(b'header-only-shm-residue')
    wal=Path(str(source)+'-wal')
    wal.write_bytes(b'')
    assert _sidecars(source)==[]
    wal.write_bytes(b'x'*32)
    assert _sidecars(source)==[]
    wal.write_bytes(b'x'*33)
    assert _sidecars(source)==[wal]
    wal.unlink()
    journal=Path(str(source)+'-journal')
    journal.write_bytes(b'')
    assert _sidecars(source)==[journal]
