"""Synthetic filesystem/process tests; no model download, GPU or Runpod call."""
import hashlib
import json
import subprocess
from pathlib import Path
import pytest
import granite_runpod as r
from test_granite_run_artifacts import fixture


def test_existing_exact_model_is_reused_without_http(tmp_path):
    manifest,_=fixture(tmp_path)
    def forbidden(*a,**kw):pytest.fail('unexpected download')
    result=r.stage_model(tmp_path,manifest,deadline=10,clock=lambda:1,opener=forbidden)
    assert len(result['files'])==13


@pytest.mark.parametrize('damage',['corrupt','extra','deadline'])
def test_bad_model_or_expired_stage_never_accepts(tmp_path,damage):
    manifest,_=fixture(tmp_path)
    if damage=='corrupt':(tmp_path/'config.json').write_bytes(b'bad')
    if damage=='extra':(tmp_path/'unapproved').write_bytes(b'bad')
    with pytest.raises((ValueError,TimeoutError)):
        r.stage_model(tmp_path,manifest,deadline=1 if damage=='deadline' else 10,clock=lambda:1,
                      opener=lambda *a,**kw:pytest.fail('unexpected download'))


def test_bundle_rejects_tamper_and_unsafe_roster(tmp_path):
    names=['granite_runpod.py','granite_runpod_proxy.py','granite_startup.py',
           'granite_run_artifacts.py','granite_artifacts_manifest.json','granite_image_identity.json',
           'granite_runpod_progress.py']
    rows=[]
    for name in names:
        data=('synthetic '+name).encode();(tmp_path/name).write_bytes(data)
        rows.append(dict(path=name,size=len(data),sha256=hashlib.sha256(data).hexdigest()))
    raw=json.dumps(dict(schema='GRANITE_RUNPOD_BUNDLE_V1',files=rows)).encode()
    (tmp_path/'runpod_bundle.json').write_bytes(raw)
    pin=hashlib.sha256(raw).hexdigest()
    assert r.verify_bundle(tmp_path,pin)['files']==rows
    (tmp_path/names[0]).write_bytes(b'changed')
    with pytest.raises(ValueError):r.verify_bundle(tmp_path,pin)
    with pytest.raises(ValueError):r.verify_bundle(tmp_path,'a'*64)


class Child:
    def __init__(self,status=None):self.status=status;self.waits=[]
    def poll(self):return self.status
    def wait(self,timeout):self.waits.append(timeout);return self.status


def test_process_exit_stops_both_and_backend_never_receives_proxy_secret(monkeypatch):
    children=[Child(),Child(1)];calls=[];stopped=[]
    def spawn(argv,**kw):calls.append((argv,kw));return children[len(calls)-1]
    monkeypatch.setattr(r,'stop_children',lambda value:stopped.extend(value))
    with pytest.raises(RuntimeError):
        r.supervise(['backend'],['proxy'],environment={'RUNPOD_GRANITE_API_KEY':'secret'},
                    deadline=10,clock=lambda:1,popen=spawn)
    assert stopped==children
    assert 'RUNPOD_GRANITE_API_KEY' not in calls[0][1]['env']
    assert calls[1][1]['env']['RUNPOD_GRANITE_API_KEY']=='secret'
    assert all(c[1]['start_new_session'] for c in calls)


def test_second_spawn_error_stops_already_started_backend(monkeypatch):
    child=Child();calls=[];stopped=[]
    def spawn(*a,**kw):
        calls.append(1)
        if len(calls)==2:raise OSError('synthetic spawn failure')
        return child
    monkeypatch.setattr(r,'stop_children',lambda value:stopped.extend(value))
    with pytest.raises(OSError):r.supervise(['b'],['p'],environment={},deadline=10,clock=lambda:1,popen=spawn)
    assert stopped==[child]


def test_stage_whole_process_timeout_stops_it(monkeypatch,tmp_path):
    child=Child();stopped=[];calls=[]
    def wait(timeout):raise subprocess.TimeoutExpired('stage',timeout)
    child.wait=wait
    def spawn(argv,**kw):calls.append((argv,kw));return child
    monkeypatch.setattr(r,'stop_children',lambda value:stopped.extend(value))
    manifest=r.artifacts.strict_json(r.artifacts.DEFAULT_MANIFEST.read_bytes())
    with pytest.raises(subprocess.TimeoutExpired):
        r.stage_process(tmp_path,manifest,deadline=3,clock=lambda:1,popen=spawn)
    assert stopped==[child] and calls[0][0][2]=='stage'


def test_cleanup_attempts_every_group_after_leader_exit(monkeypatch):
    children=[Child(0),Child(1)];signals=[]
    monkeypatch.setattr(r,'_signal_group',lambda child,force=False:signals.append((child,force)))
    r.stop_children(children)
    assert signals==[(children[0],False),(children[1],False),(children[0],True),(children[1],True)]


@pytest.mark.parametrize('env',[{}, {'RUNPOD_GRANITE_LIFETIME_SECONDS':'0'},
    {'RUNPOD_GRANITE_LIFETIME_SECONDS':'10','RUNPOD_GRANITE_API_KEY':'{{ RUNPOD_SECRET_key }}'}])
def test_boot_missing_controls_refuses_before_staging(env):
    with pytest.raises(ValueError):r.boot(env,stage=lambda *a,**k:pytest.fail('must not stage'))


def test_boot_reuses_startup_and_keeps_secret_out_of_evidence(tmp_path,monkeypatch,capsys):
    from test_granite_startup import runtime_fixture
    model=tmp_path/'model';model.mkdir()
    manifest,_=fixture(model)
    manifest_path=tmp_path/'manifest.json';manifest_path.write_bytes(r.artifacts.canonical(manifest))
    monkeypatch.setattr(r.artifacts,'DEFAULT_MANIFEST',manifest_path)
    monkeypatch.setattr(r,'verify_bundle',lambda *a: {})
    env=r.startup.launch_environment(max_model_len=4096,served_model='granite42-smoke')
    env.update(RUNPOD_GRANITE_API_KEY='test-private-secret-'*3,RUNPOD_GRANITE_LIFETIME_SECONDS='60',
               SUPERVISOR_PROGRAM__APP_COMMAND='python3 '+r.BOOT)
    env['RUNPOD_SUPERVISOR_COMMAND_SHA256']=hashlib.sha256(env['SUPERVISOR_PROGRAM__APP_COMMAND'].encode()).hexdigest()
    calls=[]
    result=r.boot(env,directory=model,clock=lambda:1,prepare=lambda d,m,e,**kw:r.startup.prepare_startup(d,m,e,runtime_facts=runtime_fixture),
                  stage=lambda *a,**kw:None,runner=lambda *a,**kw:calls.append((a,kw)))
    assert result['startup']['argv'][4]=='0.0.0.0'
    assert result['backend_argv'][4]=='127.0.0.1'
    assert result['startup']['environment']['SUPERVISOR_PROGRAM__APP_COMMAND']==r.startup.COMMAND
    assert env['RUNPOD_GRANITE_API_KEY'] not in capsys.readouterr().out
    assert env['RUNPOD_GRANITE_API_KEY'] not in json.dumps(result)
    assert len(calls)==1 and calls[0][1]['deadline']==61
    env['SUPERVISOR_PROGRAM__APP_COMMAND']='unexpected'
    with pytest.raises(ValueError):r.boot(env,clock=lambda:1,stage=lambda *a,**kw:pytest.fail('bad control staged'))


def test_preexec_checks_every_file_before_any_bundle_code_runs(tmp_path):
    import sys
    import granite_runpod_package as package
    source=tmp_path/'source';source.mkdir()
    marker=tmp_path/'executed'
    for name in package.FILES:
        (source/name).write_text('# synthetic inert source\n',encoding='utf-8',newline='\n')
    (source/'granite_runpod.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n',encoding='utf-8',newline='\n')
    target=tmp_path/'bundle'
    info=package.package(source,target,runtime_directory=target)
    import shlex
    command=info['supervisor_command']
    assert '\n' not in command and '\r' not in command and '%' not in command
    argv=shlex.split(command);argv[0]=sys.executable
    assert subprocess.run(argv,capture_output=True).returncode==0
    assert marker.exists();marker.unlink()
    (target/'granite_startup.py').write_text('raise RuntimeError("tampered import")')
    assert subprocess.run(argv,capture_output=True).returncode!=0
    assert not marker.exists()


def test_packaging_refuses_crlf_and_missing_file(tmp_path):
    import granite_runpod_package as package
    for name in package.FILES:(tmp_path/name).write_bytes(b'# synthetic\r\n')
    with pytest.raises(ValueError):package.package(tmp_path,tmp_path/'out')


def test_sigterm_enters_cleanup(monkeypatch):
    child=Child();stopped=[]
    monkeypatch.setattr(r,'stop_children',lambda children:stopped.extend(children))
    def sleeping(_):r.terminate_signal(15,None)
    with pytest.raises(SystemExit):
        r.supervise(['b'],['p'],environment={},deadline=10,clock=lambda:1,
                    popen=lambda *a,**kw:child,sleep=sleeping)
    assert len(stopped)==2


@pytest.mark.parametrize('key',['a'*257,'!'*40,'contains space'+ 'a'*40])
def test_invalid_proxy_secret_refuses_before_staging(key):
    with pytest.raises(ValueError):r.boot({'RUNPOD_GRANITE_LIFETIME_SECONDS':'10','RUNPOD_GRANITE_API_KEY':key},
                                       stage=lambda *a,**kw:pytest.fail('invalid key staged'))


def test_verification_whole_process_timeout_stops_it(monkeypatch,tmp_path):
    child=Child();stopped=[]
    child.wait=lambda timeout: (_ for _ in ()).throw(subprocess.TimeoutExpired('verify',timeout))
    monkeypatch.setattr(r,'stop_children',lambda value:stopped.extend(value))
    manifest=r.artifacts.strict_json(r.artifacts.DEFAULT_MANIFEST.read_bytes())
    with pytest.raises(subprocess.TimeoutExpired):
        r.prepare_process(tmp_path,manifest,{},deadline=3,clock=lambda:1,popen=lambda *a,**kw:child)
    assert stopped==[child]


def test_unapproved_controlled_environment_refuses_before_stage(monkeypatch):
    monkeypatch.setattr(r,'verify_bundle',lambda *a:{})
    env=r.startup.launch_environment(max_model_len=4096,served_model='granite42-smoke')
    env.update(RUNPOD_GRANITE_API_KEY='x'*40,RUNPOD_GRANITE_LIFETIME_SECONDS='60',
               SUPERVISOR_PROGRAM__APP_COMMAND='python3 '+r.BOOT,SM_VLLM_UNAPPROVED='yes')
    env['RUNPOD_SUPERVISOR_COMMAND_SHA256']=hashlib.sha256(env['SUPERVISOR_PROGRAM__APP_COMMAND'].encode()).hexdigest()
    with pytest.raises(ValueError):r.boot(env,stage=lambda *a,**kw:pytest.fail('override staged'))
