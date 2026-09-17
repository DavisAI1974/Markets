"""Coordinate the existing Granite lifecycle/controller with complete runtime admission.

No Frankie calculations or training are implemented here. The hosted probe proves
connectivity before real source operation. Private AWS evidence stays outside Git.
"""
import datetime
import hashlib
from pathlib import Path
import re
import time
import traceback
from . import granite_run_artifacts as a, granite_startup as s, granite_deployment as d

PACKAGES = {'torch':'2.11.0+cu130','transformers':'5.8.0','tokenizers':'0.22.2',
            'vllm':'0.20.2','model-hosting-container-standards':'0.1.15'}


def save(path, value):
    """Retain SDK dates explicitly; never stringify unknown values silently."""
    def normalize(obj):
        if isinstance(obj, datetime.datetime):
            return {'aws_datetime_iso8601':obj.isoformat()}
        if type(obj) is dict:return {k:normalize(v) for k,v in obj.items()}
        if type(obj) in (list,tuple):return [normalize(v) for v in obj]
        return obj
    a.save_receipt(path,normalize(value))


def validate_startup(receipt, plan, manifest):
    """Compare every static receipt field and explicitly validate measured hardware facts."""
    d.validate_plan(plan)
    env=plan['model']['PrimaryContainer']['Environment']
    mount=dict(schema='GRANITE_MOUNT_VERIFICATION_V1',manifest_sha256=a.manifest_digest(manifest),
        files=manifest['files'],bytes=sum(r['size'] for r in manifest['files']),verifier_sha256=s.digest_file(a.__file__))
    argv=['python3','-m','vllm.entrypoints.openai.api_server','--host','0.0.0.0','--port','8080',
        '--model','/opt/ml/model','--tokenizer','/opt/ml/model','--served-model-name',env['GRANITE_SERVED_MODEL'],
        '--dtype','bfloat16','--tensor-parallel-size','1','--pipeline-parallel-size','1','--data-parallel-size','1',
        '--max-num-seqs','1','--max-model-len',env['GRANITE_MAX_MODEL_LEN'],'--gpu-memory-utilization','0.9',
        '--generation-config','vllm']
    if env['GRANITE_MAX_MODEL_LEN']==str(s.MAX_MODEL_LEN):  # the long-context prefill pin granite_startup adds
        argv+=['--enable-chunked-prefill','--max-num-batched-tokens','2048']
    expected=dict(schema='GRANITE_STARTUP_RUNTIME_V1',mount=mount,image_digest=s.IMAGE_DIGEST,
        bootstrap_sha256=s.digest_file(s.__file__),argv=argv,environment=env,
        generation_policy=dict(temperature=0,thinking=False,output_limit='explicit request max_tokens',
                               quantization='none',adapters=False,speculative_decoding=False))
    if type(receipt) is not dict or set(receipt)!=set(expected)|{'runtime'}:
        raise ValueError('runtime receipt roster mismatch')
    if any(a.canonical(receipt[k])!=a.canonical(v) for k,v in expected.items()):
        raise ValueError('runtime receipt differs from pinned source/model/configuration')
    facts=receipt['runtime']
    if (type(facts) is not dict or set(facts)!={'packages','python','cuda','gpu_count','gpu','gpu_total_memory','driver','source_sha256'}
        or facts['packages']!=PACKAGES or facts['source_sha256']!=a.strict_json(s.IMAGE_IDENTITY_FILE.read_bytes())['source_sha256']
        or type(facts['gpu_count']) is not int or facts['gpu_count']!=1 or facts['gpu']!='NVIDIA L40S'
        or type(facts['gpu_total_memory']) is not int or not 40_000_000_000<=facts['gpu_total_memory']<=52_000_000_000
        or facts['cuda']!='13.0' or not re.fullmatch(r'3\.12\.[0-9]+',str(facts['python']))
        or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',str(facts['driver']))):
        raise ValueError('measured runtime source/packages/hardware mismatch')


def hosted_sequence(client, logs, plan, manifest, directory, invoke, *, now=time.time, sleep=time.sleep):
    """All creation outcomes, including lost replies, flow through finally cleanup."""
    directory=Path(directory)
    ledger=directory/'deployment-ledger.json'
    if ledger.exists():raise ValueError('existing ledger requires cleanup, never another run')
    save(directory/'deployment-plan.json',plan)
    try:
        d.create_resources(client,plan,ledger,now=now)
        poll=[0]
        def retain_descriptor(event):
            poll[0]+=1
            save(directory/'startup-descriptors'/f'{poll[0]:05d}.json',event)
        save(directory/'ready-descriptors.json',d.wait_ready(client,plan,now=now,sleep=sleep,observe=retain_descriptor))
        receipt=None
        deadline=min(plan['created_at_epoch']+20*60,plan['delete_deadline_epoch']-120)
        while receipt is None and now()<deadline:
            receipt=d.startup_receipt(logs,plan)
            if receipt is None:sleep(5)
        if receipt is None:raise TimeoutError('startup receipt was not observed before admission deadline')
        save(directory/'startup-receipt.json',receipt)
        validate_startup(receipt,plan,manifest)
        save(directory/'pre-inference-descriptors.json',d.inspect_resources(client,plan))
        if now()+120>=plan['delete_deadline_epoch']:raise TimeoutError('no remaining bounded inference budget')
        result=invoke(receipt)
        if result['integration_status']!='complete':raise ValueError('real controller returned incomplete integration; inspect retained evidence')
        return result
    except BaseException as exc:
        save(directory/'failure.json',{**d.failure_evidence(exc),'traceback':d.sanitize_diagnostic(traceback.format_exc())})
        raise
    finally:
        if logs is not None and ledger.exists():
            try:
                d.startup_receipt(logs,plan)
            except Exception as exc:
                save(directory/'final-log-error.json',d.failure_evidence(exc))
        try:
            save(directory/'cleanup.json',d.cleanup_resources(client,plan,ledger,now=now,sleep=sleep))
        except BaseException as exc:
            save(directory/'cleanup-failure.json',{**d.failure_evidence(exc),'traceback':d.sanitize_diagnostic(traceback.format_exc())})
            raise

class RecordedLogs:
    """Retain every raw SDK log page, including pages without a startup receipt."""
    def __init__(self, client, directory):
        self.client,self.directory,self.counter=client,Path(directory),0
    def __getattr__(self,name):
        if name not in ('describe_log_streams','get_log_events'):raise AttributeError(name)
        def call(**kwargs):
            self.counter+=1
            event=dict(operation=name,observed_at_epoch=time.time(),request=kwargs)
            try:
                result=getattr(self.client,name)(**kwargs)
            except Exception as exc:
                save(self.directory/f'logs-{self.counter:05d}.json',
                     d.sanitize_diagnostic({**event,'failure':d.failure_evidence(exc)}))
                raise
            save(self.directory/f'logs-{self.counter:05d}.json',d.sanitize_diagnostic({**event,'response':result}))
            return result
        return call


def prerequisites(clients, directory):
    """Fresh scoped inventory, quota, image manifest and unchanged compute rate."""
    from decimal import Decimal
    from . import sagemaker_inventory as inventory
    directory=Path(directory)
    report={}
    for name,fn in (
        ('endpoints',lambda:inventory.endpoints(clients['sagemaker'])),
        ('quota',lambda:inventory.quotas(clients['service-quotas'])),
        ('price',lambda:inventory.prices(clients['pricing'],'us-east-1')),
        ('image',lambda:inventory.image(clients['ecr']))):
        report[name]=fn()
        save(directory/'fresh-prerequisites.json',report)
        if report[name]['status']!='complete':raise ValueError('incomplete prerequisite: '+name)
    if report['endpoints']['items']:raise ValueError('owned endpoint already exists; inspect it before another launch')
    if report['quota']['items'][0]['Value']<1:raise ValueError('endpoint quota unavailable')
    if Decimal(report['price']['endpoint_rates'][0]['usd_per_instance_hour'])!=Decimal('2.8026000000'):
        raise ValueError('hosting rate differs from approved budget')
    if report['image']['images'][0]['imageId']['imageDigest']!=s.IMAGE_DIGEST:
        raise ValueError('registry image differs from pinned image')
    return report


def clients():
    import boto3
    from botocore.config import Config
    cfg=Config(connect_timeout=10,read_timeout=60,retries={'total_max_attempts':1,'mode':'standard'})
    return {name:boto3.client(name,region_name='us-east-1',config=cfg)
            for name in ('sts','s3','sagemaker','logs','service-quotas','pricing','ecr')}


def run(directory, run_id):
    import asyncio
    import platform
    import subprocess
    from . import granite_live_controller as live
    from .granite_sagemaker import SageMakerConfig
    if platform.system()!='Linux':raise ValueError('coordinator requires the Linux checkout used for bootstrap staging')
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    fixture=None
    try:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        subprocess.run(['git','diff','--exit-code','HEAD','--'],check=True,capture_output=True)
        files=subprocess.check_output(['git','ls-files','research/kalshi/frankie_boss'],text=True).splitlines()
        save(directory/'source-identity.json',dict(commit=commit,files={p:s.digest_file(p) for p in files if p.endswith(('.py','.json'))}))
        cloud=clients()
        account=cloud['sts'].get_caller_identity()['Account']
        if hashlib.sha256(account.encode()).hexdigest()!=a.APPROVED_ACCOUNT_SHA256:raise ValueError('foreign AWS account')
        bucket=f'frankie-granite42-{account}-us-east-1'
        manifest=a.strict_json(a.DEFAULT_MANIFEST.read_bytes())
        print('Verifying exact staged model bytes; no GPU exists for this run yet',flush=True)
        save(directory/'model-s3-verification.json',a.verify_s3(cloud['s3'],bucket,manifest))
        # Same Linux source bytes generate both the staged bootstrap and launch pins.
        s.stage_bootstrap(cloud['s3'],bucket,directory/'bootstrap-verification.json')
        tokenizer=directory/'tokenizer';tokenizer.mkdir()
        for row in manifest['files']:
            if row['path'] not in live.TOKENIZER_FILES:continue
            result=cloud['s3'].get_object(Bucket=bucket,Key=a.prefix_for(manifest)+row['path'])
            try:
                if result['ContentLength']!=row['size']:raise ValueError('tokenizer S3 size mismatch')
                with (tokenizer/row['path']).open('xb') as output:
                    size=0
                    while block:=result['Body'].read(a.BLOCK):
                        size+=len(block)
                        if size>row['size']:raise ValueError('tokenizer object exceeds pinned size')
                        output.write(block)
            finally:result['Body'].close()
            a.verify_file(tokenizer/row['path'],row)
        fixture=live.prepare_fixture(directory/'fixture')
        admission=live.measure_fixture(fixture,tokenizer)
        print('Actual tokenizer admission:',admission['input_tokens'],'input tokens;',admission['max_model_len'],'total',flush=True)
        prerequisites(cloud,directory)
        plan=d.make_plan(account_sha_checked=account,run_id=run_id,max_model_len=admission['max_model_len'],
                         served_model='granite42-verified',now=time.time())
        logs=RecordedLogs(cloud['logs'],directory/'logs')
        def invoke(receipt):
            identity=live.identity_from_runtime(receipt,admission)
            config=SageMakerConfig('us-east-1',plan['endpoint']['EndpointName'],'granite42-verified',True,10.,65.,70.)
            return asyncio.run(live.run_fixture(fixture,config=config,identity=identity,
                expected_prompt_sha256=admission['prompt_sha256'],admission=admission))
        print('Starting one bounded endpoint after verified admission',flush=True)
        result=hosted_sequence(cloud['sagemaker'],logs,plan,manifest,directory,invoke)
        save(directory/'summary.json',dict(status=result['integration_status'],source_commit=commit,
            input_tokens=admission['input_tokens'],provider_calls=result['calls']['provider_calls'],
            token_count_matches=result['token_count_matches'],cleanup='confirmed',evidence_class=result['evidence_class']))
        print('Real hosted controller result retained; endpoint cleanup confirmed',flush=True)
    except BaseException as exc:
        save(directory/'coordinator-failure.json',{**d.failure_evidence(exc),'traceback':d.sanitize_diagnostic(traceback.format_exc())})
        raise
    finally:
        if fixture is not None:fixture.close()


def cleanup(directory):
    """Independent CI always path; never create resources or rebuild a plan."""
    directory=Path(directory)
    path=directory/'deployment-ledger.json'
    if not path.exists():
        save(directory/'independent-cleanup.json',dict(status='no_creation_intent'))
        return
    ledger=a.strict_json(path.read_bytes());plan=ledger['plan']
    cloud=clients()
    account=cloud['sts'].get_caller_identity()['Account']
    if hashlib.sha256(account.encode()).hexdigest()!=a.APPROVED_ACCOUNT_SHA256:raise ValueError('foreign cleanup account')
    logs=RecordedLogs(cloud['logs'],directory/'cleanup-logs')
    try:
        if d.describe(cloud['sagemaker'],'endpoint',plan) is not None:
            try:d.startup_receipt(logs,plan)
            except Exception as exc:save(directory/'cleanup-log-error.json',d.failure_evidence(exc))
    finally:
        save(directory/'independent-cleanup.json',d.cleanup_resources(cloud['sagemaker'],plan,path))


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('run','cleanup'))
    parser.add_argument('--directory',required=True)
    parser.add_argument('--run-id')
    args=parser.parse_args()
    if args.operation=='cleanup':cleanup(args.directory)
    else:
        if not args.run_id:parser.error('--run-id required for run')
        run(args.directory,args.run_id)


if __name__=='__main__':main()
