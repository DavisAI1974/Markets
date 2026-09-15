"""Runpod smoke boot: verified public artifacts, bounded local processes, no API client.

Executing main is a future paid-Pod operation. Importing and bundle preparation
are local only. Process exit does not terminate a billable Runpod Pod.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import signal
import sys
import time
import tempfile
import urllib.request
try:
    from . import granite_startup as startup
    from . import granite_run_artifacts as artifacts
except ImportError:
    import granite_startup as startup
    import granite_run_artifacts as artifacts

IMAGE = 'public.ecr.aws/deep-learning-containers/vllm@' + startup.IMAGE_DIGEST
BOOT = '/opt/ml/additional-model-data-sources/bootstrap/granite_runpod.py'
PROXY = '/opt/ml/additional-model-data-sources/bootstrap/granite_runpod_proxy.py'


def remaining(deadline, clock=time.monotonic):
    value=deadline-clock()
    if value <= 0:
        raise TimeoutError('approved process lifetime exhausted')
    return value


class TimedResponse:
    def __init__(self, response, deadline, clock):
        self.response,self.deadline,self.clock=response,deadline,clock
        self.status,self.headers=response.status,response.headers
    def __enter__(self):return self
    def __exit__(self,*args):self.response.close()
    def read(self,size):
        remaining(self.deadline,self.clock)
        data=self.response.read(size)
        remaining(self.deadline,self.clock)
        return data


def stage_model(directory, manifest, *, deadline, opener=None, clock=time.monotonic):
    """One download attempt/file; existing verifier owns roster, bytes and resume."""
    artifacts.validate_manifest(manifest)
    if opener is None:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({})).open
    def bounded(request,timeout):
        response=opener(request,timeout=min(timeout,remaining(deadline,clock)))
        return TimedResponse(response,deadline,clock)
    for row in manifest['files']:
        remaining(deadline,clock)
        artifacts.download_file(row,directory,opener=bounded)
    receipt=artifacts.verify_directory(directory,manifest)
    remaining(deadline,clock)
    return receipt


def verify_bundle(directory, expected_digest):
    directory=Path(directory)
    raw=(directory/'runpod_bundle.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_digest:
        raise ValueError('bootstrap bundle identity differs')
    bundle=artifacts.strict_json(raw)
    expected={'granite_runpod.py','granite_runpod_proxy.py','granite_startup.py',
              'granite_run_artifacts.py','granite_artifacts_manifest.json','granite_image_identity.json'}
    rows=bundle.get('files',[])
    if (bundle.get('schema')!='GRANITE_RUNPOD_BUNDLE_V1' or len(rows)!=len(expected)
            or {r.get('path') for r in rows}!=expected
            or directory.is_symlink()):
        raise ValueError('exact bootstrap bundle required')
    for row in rows:artifacts.verify_file(directory/row['path'],row)
    return bundle


def _signal_group(child, force=False):
    if os.name=='posix':
        try:os.killpg(child.pid,signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:pass
    elif child.poll() is None:
        child.kill() if force else child.terminate()


def stop_children(children):
    # Signal groups even if the direct leader exited: descendants can remain.
    errors=[]
    for child in children:
        try:_signal_group(child)
        except BaseException as error:errors.append(error)
    for child in children:
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:_signal_group(child,True);child.wait(timeout=5)
            except BaseException as error:errors.append(error)
        except BaseException as error:errors.append(error)
        finally:
            try:_signal_group(child,True)
            except BaseException as error:errors.append(error)
    if errors:raise RuntimeError('subprocess cleanup failed') from None


def stage_process(directory, manifest, *, deadline, clock=time.monotonic,
                  popen=subprocess.Popen):
    # Bound the complete stage, including DNS, dribbling reads and hashing.
    # Manifest is the already verified packaged manifest, never a caller-selected URL.
    if manifest!=artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes()):
        raise ValueError('packaged model manifest required')
    env=dict(os.environ);env.pop('RUNPOD_GRANITE_API_KEY',None)
    child=popen(['python3',str(Path(__file__)),'stage',str(directory),
                 str(remaining(deadline,clock))],env=env,start_new_session=True)
    try:
        if child.wait(timeout=remaining(deadline,clock))!=0:
            raise RuntimeError('model staging failed; no deployment retry')
        remaining(deadline,clock)
    finally:stop_children([child])


def prepare_process(directory, manifest, environment, *, deadline, clock=time.monotonic,
                    popen=subprocess.Popen):
    if manifest!=artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes()):
        raise ValueError('packaged model manifest required')
    env=dict(environment);env.pop('RUNPOD_GRANITE_API_KEY',None)
    with tempfile.TemporaryDirectory(prefix='granite-verify-') as scratch:
        path=Path(scratch)/'startup.json'
        child=popen(['python3',str(Path(__file__)),'verify',str(directory),str(path)],
                    env=env,start_new_session=True)
        try:
            if child.wait(timeout=remaining(deadline,clock))!=0:
                raise RuntimeError('startup verification failed')
            remaining(deadline,clock)
            if path.stat().st_size>65536:raise ValueError('oversized startup receipt')
            receipt=artifacts.strict_json(path.read_bytes())
            if (receipt.get('schema')!='GRANITE_STARTUP_RUNTIME_V1'
                    or receipt.get('image_digest')!=startup.IMAGE_DIGEST
                    or receipt.get('environment')!={k:environment[k] for k in startup.launch_environment(
                        max_model_len=int(environment['GRANITE_MAX_MODEL_LEN']),served_model=environment['GRANITE_SERVED_MODEL'])}
                    or receipt.get('mount',{}).get('manifest_sha256')!=artifacts.manifest_digest(manifest)):
                raise ValueError('child startup receipt binding mismatch')
            expected_argv=['python3','-m','vllm.entrypoints.openai.api_server','--host','0.0.0.0','--port','8080',
                '--model',str(directory),'--tokenizer',str(directory),'--served-model-name',environment['GRANITE_SERVED_MODEL'],
                '--dtype','bfloat16','--tensor-parallel-size','1','--pipeline-parallel-size','1',
                '--data-parallel-size','1','--max-num-seqs','1','--max-model-len',environment['GRANITE_MAX_MODEL_LEN'],
                '--gpu-memory-utilization','0.9','--generation-config','vllm']
            if receipt.get('argv')!=expected_argv:
                raise ValueError('child executable/arguments differ from pinned startup')
            return receipt
        finally:stop_children([child])


def supervise(backend_argv, proxy_argv, *, environment, deadline,
              popen=subprocess.Popen, clock=time.monotonic, sleep=time.sleep):
    """No autorestart; any process exit or deadline stops both process groups."""
    children=[]
    backend_env=dict(environment)
    backend_env.pop('RUNPOD_GRANITE_API_KEY',None)
    try:
        remaining(deadline,clock)
        children.append(popen(backend_argv,env=backend_env,start_new_session=True))
        remaining(deadline,clock)
        children.append(popen(proxy_argv,env=dict(environment),start_new_session=True))
        while True:
            remaining(deadline,clock)
            if any(child.poll() is not None for child in children):
                raise RuntimeError('smoke subprocess exited; no restart')
            sleep(min(.25,remaining(deadline,clock)))
    finally:
        stop_children(children)


def boot(environment, *, directory='/opt/ml/model', bundle_directory=None,
         clock=time.monotonic, prepare=prepare_process, stage=stage_process,
         runner=supervise):
    """Called only inside an explicitly authorized Pod; tests inject all effects."""
    started=clock()
    text=environment.get('RUNPOD_GRANITE_LIFETIME_SECONDS','')
    if not text.isascii() or not text.isdecimal() or int(text)<=0:
        raise ValueError('explicit positive process lifetime required')
    deadline=started+int(text)
    secret=environment.get('RUNPOD_GRANITE_API_KEY','')
    if re.fullmatch(r'[A-Za-z0-9_-]{32,256}',secret) is None:
        raise ValueError('resolved private API key required')
    verify_bundle(bundle_directory or Path(__file__).parent,environment.get('RUNPOD_BUNDLE_SHA256'))
    manifest=artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes())
    restored=dict(environment)
    if hashlib.sha256(restored.get('SUPERVISOR_PROGRAM__APP_COMMAND','').encode()).hexdigest()!=environment.get('RUNPOD_SUPERVISOR_COMMAND_SHA256'):
        raise ValueError('Runpod supervisor command differs')
    restored['SUPERVISOR_PROGRAM__APP_COMMAND']=startup.COMMAND
    expected=startup.launch_environment(max_model_len=int(restored.get('GRANITE_MAX_MODEL_LEN','0')),
                                       served_model=restored.get('GRANITE_SERVED_MODEL'))
    if any(restored.get(key)!=value for key,value in expected.items()):
        raise ValueError('startup configuration differs before staging')
    controlled=('SUPERVISOR_','SM_VLLM_','GRANITE_','STANDARD_','HF_MODEL_ID')
    if any(key.startswith(controlled) and key not in expected for key in restored):
        raise ValueError('unapproved controlled environment before staging')
    stage(directory,manifest,deadline=deadline,clock=clock)
    receipt=prepare(directory,manifest,restored,deadline=deadline,clock=clock)
    # Keep the reused receipt intact; record the explicit network restriction separately.
    backend=list(receipt['argv']);backend[backend.index('--host')+1]='127.0.0.1'
    evidence={'schema':'GRANITE_RUNPOD_STARTUP_V1','startup':receipt,
              'backend_argv':backend,'proxy_port':8081,'lifetime_seconds':int(text),
              'budget_enforcement':'external Pod teardown required'}
    print('GRANITE_RUNPOD_STARTUP '+artifacts.canonical(evidence).decode(),flush=True)
    remaining(deadline,clock)
    runner(backend,['python3',PROXY],environment=environment,deadline=deadline,clock=clock)
    return evidence


def terminate_signal(signum,frame):
    raise SystemExit(128+signum)


if __name__=='__main__':
    signal.signal(signal.SIGTERM,terminate_signal)
    try:
        if len(sys.argv)==4 and sys.argv[1]=='stage':
            stage_model(sys.argv[2],artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes()),
                        deadline=time.monotonic()+float(sys.argv[3]))
        elif len(sys.argv)==4 and sys.argv[1]=='verify':
            receipt=startup.prepare_startup(sys.argv[2],artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes()),os.environ)
            artifacts.save_receipt(sys.argv[3],receipt)
        elif len(sys.argv)==1:boot(os.environ)
        else:raise ValueError('unsupported bootstrap invocation')
    except BaseException as error:
        # Never print environment, credentials, backend text or traceback.
        print('GRANITE_RUNPOD_STOP '+type(error).__name__,flush=True)
        raise SystemExit(1) from None
