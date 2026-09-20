"""Actual Sunday host. Import is inert; never pass credentials as CLI arguments.

Run with --configuration pointing to the host configuration with a host_runtime
section. The first unfinished cycle prepares full bytes and token admission, then
waits for one bounded JSON line on stdin containing the actual readiness witness
and service key. A principal handoff waits for an actual host-attested response
while retaining the prepared context and a separate process ownership lock.

The host-progress probe answers which phase owns work, whether native preparation
is advancing, and whether the same durable job or principal response is pending.
Its possible_stall warnings are advisory observations, never elapsed stop budgets.
Operation journals remain authoritative if diagnostic persistence fails.
"""
from __future__ import annotations
import argparse
import asyncio
import base64
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import traceback
import uuid
from types import SimpleNamespace


class HostProbe:
    """Advisory telemetry cannot replace an operation's durable outcome."""
    def __init__(self,probe):self.probe,self.warned=probe,False

    def call(self,method,*args,**kwargs):
        try:return getattr(self.probe,method)(*args,**kwargs)
        except Exception:
            if not self.warned:
                self.warned=True
                try:print(json.dumps(dict(status='HOST_DIAGNOSTICS_UNAVAILABLE',operation_journals_authoritative=True)),flush=True)
                except Exception:pass

    def advance(self,phase,**values):return self.call('advance',phase,**values)

    def data(self,value):
        allowed = {'phase','entries','total','percent','records_per_second','worker_cpus',
                   'worker_cpu_seconds','queued_blocks','oldest_queue_age_seconds'}
        safe = {key: value[key] for key in allowed if key in value}
        try: print('FRANKIE_DATA_PROGRESS '+json.dumps(safe,sort_keys=True),flush=True)
        except OSError: pass

    def controller(self,value):
        # Never forward arbitrary service fields, prompt text or exception text.
        allowed={'source_validation','native_reasoning','native_complete','critic_request',
            'critic_complete','output_persisted','completed_result_reused','request_failed'}
        if type(value) is not dict or value.get('phase') not in allowed:return
        safe={'phase':value['phase']}
        for name in ('through_cursor','count'):
            if type(value.get(name)) is int and value[name]>=0:safe[name]=value[name]
        return self.call('controller_event',safe)

    def job(self,value):
        allowed={'job_not_found_same_id_create','job_accepted','job_running','job_completed',
            'job_not_dispatched','job_ambiguous','job_failed','job_result_persisted',
            'job_http_not_dispatched','job_http_outcome_unknown_query_same_id',
            'remote_job_credential_rejected','local_job_request_refused_not_dispatched',
            'remote_backend_not_dispatched_requires_attention'}
        if type(value) is not dict or value.get('phase') not in allowed:return
        safe=dict(schema='FRANKIE_ACTUAL_JOB_PROGRESS_V1',run_id=self.probe.run_id,phase=value['phase'])
        for name in ('job_id','request_hash','body_sha256'):
            if type(value.get(name)) is str and re.fullmatch('[0-9a-f]{64}',value[name]):safe[name]=value[name]
        try:print('FRANKIE_JOB_PROGRESS '+json.dumps(safe,sort_keys=True),flush=True)
        except Exception:pass
        # Job observations do not reset the progress clock or authorize retries.
        self.call('sample')

    def __enter__(self):
        self.probe.__enter__()  # Initial attachment must succeed before execution.
        return self

    def __exit__(self,*args):
        self.call('__exit__',*args)
        return False


class ReleasableHostLock:
    """Release the recorder lock only while a separate lifetime lock is held."""
    def __init__(self,factory,path):
        self.factory,self.path,self.context=factory,path,None

    def acquire(self,wait=False):
        if self.context is not None:raise RuntimeError('host lock already held')
        while True:
            candidate=self.factory(self.path)
            try:candidate.__enter__()
            except OSError as error:
                if not wait or error.errno not in (errno.EACCES,errno.EAGAIN,errno.EDEADLK):raise
                time.sleep(1)
                continue
            self.context=candidate
            return self

    def release(self):
        if self.context is None:raise RuntimeError('host lock is not held')
        context,self.context=self.context,None
        context.__exit__(None,None,None)

    def __enter__(self):return self.acquire()
    def __exit__(self,*args):
        if self.context is not None:self.release()


def await_recorded_principal(request,directory,host_lock,probe=None):
    """Observe only; this callback never dispatches or fabricates a session."""
    matches=[]
    for index in range(19):
        path=Path(directory)/'execution'/f'cycle-{index:02d}'/'principal'/'session-request.json'
        if path.exists() and json.loads(path.read_bytes())==request:matches.append(path)
    if len(matches)!=1:raise ValueError('unique retained principal request required')
    request_path=matches[0];response_path=request_path.with_name('session-response.json')
    if probe is not None:probe.advance('frankie_calculation',unit='outputs')
    print(json.dumps(dict(status='actual_frankie_session_pending',request_id=request['request_id'],
        request_path=str(request_path),prepared_context_retained=True)),flush=True)
    host_lock.release()
    try:
        while not response_path.exists():time.sleep(1)
    finally:
        # Recorder holds this lock through its immutable write. Reacquiring also
        # prevents observing a partially written response or a moving request.
        host_lock.acquire(wait=True)
    if json.loads(request_path.read_bytes())!=request:raise ValueError('principal request changed while awaiting response')
    result=json.loads(response_path.read_bytes())
    if type(result) is not dict or set(result)!={'response','host_attestation'}:
        raise ValueError('recorded principal response envelope differs')
    if probe is not None:probe.advance('frankie_calculation',completed=1,total=1,unit='outputs')
    return result


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def verified(witness):
    path=Path(witness['path'])
    if sha(path)!=witness['sha256'] or ('bytes' in witness and path.stat().st_size!=witness['bytes']):
        raise ValueError('host file differs from independently supplied witness')
    return path


def verified_json(witness):return json.loads(verified(witness).read_bytes())


def imports(repo):
    sys.path.insert(0,str(repo))
    from research.kalshi.frankie_boss import sunday_execution as driver
    from research.kalshi.frankie_boss import sunday_native_runtime as native
    from research.kalshi.frankie_boss import boss_training_checkpoint as training
    from research.kalshi.frankie_boss import c15_journal as journal
    from research.kalshi.frankie_boss import granite_run_artifacts as artifacts
    from research.kalshi.frankie_boss.online_source_prefix import OnlinePrefix,PrefixCursor
    from research.kalshi.frankie_boss.verified_journal_reader import VerifiedJournalReader
    from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
    from research.kalshi.frankie_boss.prepared_context_cache import prepare_context_cache
    from research.kalshi.frankie_boss.selected_source_scope import source_scope
    from research.kalshi.frankie_boss.feedback_cycle import CycleCoordinator,_exclusive
    from research.kalshi.frankie_boss.forecast_refresh import RefreshPolicy
    from research.kalshi.frankie_boss.frankie_controller import native_model_pin
    from research.kalshi.frankie_boss.granite_runpod_tokenizer import LocalTokenizerAdmission
    from research.kalshi.frankie_boss.granite_retained_lifecycle import verified_service_inputs
    from research.kalshi.frankie_boss.granite_runpod_service import build_runpod_service
    from research.kalshi.frankie_boss.granite_durable_job_client import https_exchange_jobs,RequestNotDispatched,JobAttention
    from research.kalshi.frankie_boss.retained_preparation_recovery import recover_retained_preparation
    from research.kalshi.frankie_boss.granite_shadow import PendingTransport,IncompleteModelOutput
    from research.kalshi.frankie_boss.frankie_principal_adapter import PrincipalPending
    from research.kalshi.frankie_boss.full_run_progress import RunProbe
    return SimpleNamespace(**locals())


class PreparationComplete(Exception):pass


def read_trigger(schema,fields):
    """Only stdin carries credentials; neither its bytes nor exception text is saved."""
    raw=sys.stdin.buffer.readline(32769)
    if len(raw)>32768 or not raw.endswith(b'\n'):raise ValueError('bounded stdin execution trigger required')
    trigger=json.loads(raw)
    if type(trigger) is not dict or set(trigger)!={'schema','service_key'}|set(fields) or trigger['schema']!=schema:
        raise ValueError('explicit host execution trigger required')
    key=trigger.pop('service_key')
    if type(key) is not str or not re.fullmatch('[A-Za-z0-9_-]{32,256}',key):
        raise ValueError('private in-memory service credential required')
    return key,trigger


def admitted_jobs_exchange(exchange,expected_sha256,*,not_dispatched=None):
    """Allow only bounded jobs operations, binding every POST to admitted bytes."""
    active_job=None
    def refuse(message):
        if not_dispatched is None:raise ValueError(message)
        raise not_dispatched(message,local_validation=True)
    def guarded(pod,method,path,body,key,timeout):
        nonlocal active_job
        match=re.fullmatch(r'/v1/jobs/([0-9a-f]{64})(/result)?',path)
        if (match is None or method not in ('GET','POST') or type(body) is not bytes or
            type(timeout) not in (int,float) or not 0<timeout<=80 or
            (method=='GET' and body) or (method=='POST' and (match[2] or hashlib.sha256(body).hexdigest()!=expected_sha256))):
            refuse('actual durable job operation differs from admitted request')
        if active_job is not None and active_job!=match[1]:refuse('one stable admitted job required')
        active_job=match[1]
        return exchange(pod,method,path,body,key,timeout)
    return guarded


def retained_admission(admission,request_bytes):
    """Reuse the one actual tokenizer measurement only for the identical body."""
    accepted=dict(admission)
    def exact(body):
        if type(body) is not bytes or len(body)!=request_bytes or hashlib.sha256(body).hexdigest()!=accepted['request_sha256']:
            raise ValueError('critic bytes differ from the actually measured request')
        return dict(accepted)
    return exact


def incomplete_output_alert(error):
    """Make the physical-context exhaustion visible without exposing raw output."""
    details=error.details
    return dict(status='INCOMPLETE_RESPONSE_CONTEXT_EXHAUSTED',
        message='Incomplete response: context capacity exhausted.',
        input_tokens=details.get('input_tokens'),output_token_limit=details.get('requested_output_tokens'),
        context_tokens=details.get('context'),actual_usage=details.get('usage_counts',{}),
        finish_reason=details.get('finish_reason'),result_sha256=details.get('result_sha256'),
        artifact_path=error.artifact_path,cleanup_pending=details.get('cleanup_pending'))


class ActualHost:
    def __init__(self,configuration,*,prepare_only=False,probe=None):
        self.probe=probe
        self.config=configuration;self.host=configuration['host_runtime']
        self.repo=Path(self.host['repository']).resolve()
        self.api=imports(self.repo);self.prepare_only=prepare_only
        self.directory=Path(configuration['run_directory']);self.directory.mkdir(parents=True,exist_ok=True)
        self.instance_id=self.retained_instance_id()
        self.builder=self.context=self.decoder=self.optimizer=self.checkpoint=self.admit=None
        self.scope=None;self.cache=None;self.original_prepare=None
        self.coordinator=None
        actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.repo,text=True).strip()
        if actual!=self.host['boss_commit']:raise ValueError('explicit current BOSS commit required')
        subprocess.run(['git','diff','--exit-code','HEAD','--','research/kalshi/frankie_boss','research/refrag'],cwd=self.repo,check=True,stdout=subprocess.DEVNULL)
        self.code={str(p.relative_to(self.repo)):sha(p) for root in ('research/kalshi/frankie_boss','research/refrag')
                   for p in sorted((self.repo/root).rglob('*.py')) if 'tests' not in p.parts}
        self.code['host_script']=sha(__file__)
        self.save('host-identity.c15.json',dict(configuration=configuration,code=self.code))

    def save(self,name,value):self.api.driver._save(self.directory/name,value)
    def load(self,name):return self.api.driver._load(self.directory/name)

    def read_execution_trigger(self,schema,fields,request_id):
        """SSM supplies the private key once; request-bound readiness stays public.

        The operator publishes an immutable, credential-free trigger at
        <trigger_directory>/<request_id>/<schema>.json after the retained service
        observer has produced its actual readiness. All existing readiness and
        same-job checks below still apply. No timeout authorizes another attempt.
        """
        source=self.host.get('pod_credential_ssm')
        if source is None:return read_trigger(schema,fields)
        if (type(source) is not dict or set(source)!={'name','region','trigger_directory'}
                or not re.fullmatch(r'/[A-Za-z0-9_./-]{1,1000}',str(source['name']))
                or not re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-\d',str(source['region']))
                or not source['trigger_directory']
                or not (re.fullmatch('[0-9a-f]{64}',str(request_id)) or
                    (re.fullmatch(r'[A-Za-z0-9_-]{1,128}',str(getattr(self,'config',{}).get('run_id',''))) and
                     request_id in {f"{self.config['run_id']}-cycle-{index:02d}" for index in range(19)}))
                or schema not in ('FRANKIE_ACTUAL_EXECUTE_V1','FRANKIE_ACTUAL_RESUME_JOB_V1')):
            raise ValueError('explicit SSM credential source and request identity required')
        path=Path(source['trigger_directory'])/request_id/(schema+'.json')
        print(json.dumps(dict(status='waiting_for_request_bound_service_trigger',request_id=request_id)),flush=True)
        while not path.exists():time.sleep(1)
        with path.open('rb') as stream:raw=stream.read(32769)
        if len(raw)>32768:raise ValueError('bounded execution trigger required')
        try:trigger=json.loads(raw)
        except (ValueError,UnicodeError):raise ValueError('valid public execution trigger required') from None
        if type(trigger) is not dict or set(trigger)!={'schema'}|set(fields) or trigger['schema']!=schema:
            raise ValueError('credential-free explicit host execution trigger required')
        if not hasattr(self,'_ssm_pod_key'):
            import boto3
            from botocore.config import Config
            try:
                client=boto3.client('ssm',region_name=source['region'],
                    config=Config(connect_timeout=5,read_timeout=10,retries={'total_max_attempts':1}))
                parameter=client.get_parameter(Name=source['name'],WithDecryption=True)['Parameter']
                key=parameter['Value']
                if parameter['Type']!='SecureString' or type(key) is not str or not re.fullmatch('[A-Za-z0-9_-]{32,256}',key):
                    raise ValueError('invalid private parameter')
            except Exception:
                raise ValueError('private SSM credential unavailable or invalid') from None
            self._ssm_pod_key=key
        return self._ssm_pod_key,trigger

    def progress(self,phase,**values):
        if getattr(self,'probe',None) is not None:self.probe.advance(phase,**values)

    def recovery_progress(self,completed,total):
        self.progress('boss_reasoning',completed=completed,total=total,unit='records')
        print(json.dumps(dict(status='retained_preparation_recovery',completed=completed,total=total)),flush=True)

    def retained_instance_id(self):
        name='host-instance.c15.json'
        if (self.directory/name).exists():record=self.load(name)
        else:
            record=dict(schema='FRANKIE_ACTUAL_HOST_INSTANCE_V1',run_id=self.config['run_id'],instance_id=uuid.uuid4().hex)
            self.save(name,record)
        if (set(record)!={'schema','run_id','instance_id'} or record['schema']!='FRANKIE_ACTUAL_HOST_INSTANCE_V1' or
            record['run_id']!=self.config['run_id'] or type(record['instance_id']) is not str or
            not re.fullmatch('[0-9a-f]{32}',record['instance_id'])):
            raise ValueError('retained logical host instance differs')
        return record['instance_id']

    def retained_ready_signal(self,cycle_directory,fields):
        path=cycle_directory/('host-ready-'+self.instance_id+'.c15.json')
        name=path.relative_to(self.directory)
        if path.exists():
            record=self.load(name)
            if {k:v for k,v in record.items() if k!='admitted_at'}!=fields:
                raise ValueError('retained readiness differs from actual admission')
        else:
            record=dict(fields,admitted_at=time.time());self.save(name,record)
        return record

    def source(self):
        if self.scope is not None:return
        for key in ('memory','contract','mapping','retained_witnesses','delivery_receipt','calculation_result','source_manifest'):
            verified(self.config[key])
        source=Path(self.config['source_directory']);schedule=Path(self.config['schedule_directory'])
        if (source/'failure.json').exists() or (schedule/'failure.json').exists():
            raise ValueError('source or schedule failure evidence requires explicit recovery')
        receipt=verified_json(self.host['ingestion_receipt']);outer=verified_json(self.host['schedule_receipt'])
        if verified(self.host['ingestion_receipt']).resolve()!= (source/'ingestion-receipt.json').resolve():
            raise ValueError('source receipt outside declared execution')
        completion=json.loads((source/'completion.json').read_bytes())
        if (receipt['record_count']!=57027 or completion['record_count']!=57027 or
            outer['source_records']!=57027 or outer['steps']!=19 or outer['source_completion']!=completion):
            raise ValueError('full Sunday source and nineteen-step schedule required')
        checkpoint=source/'builder-checkpoint.c15.json'
        if sha(checkpoint)!=receipt['checkpoint_sha256'] or outer['source_checkpoint_sha256']!=receipt['checkpoint_sha256']:
            raise ValueError('complete source checkpoint bytes changed')
        state=self.api.journal.unpack(json.loads(checkpoint.read_bytes()))
        if (state['state_hash']!=receipt['checkpoint_state_hash'] or
            completion['builder_state_hash']!=state['state_hash'] or
            outer['source_checkpoint_state_hash']!=state['state_hash']):
            raise ValueError('complete source state identity changed')
        actual_schedule=verified(self.host['schedule'])
        if actual_schedule.resolve()!=(schedule/'schedule.json').resolve() or sha(actual_schedule)!=outer['schedule_file_sha256']:
            raise ValueError('full schedule differs from verified execution receipt')
        from research.kalshi.frankie_boss.verified_sunday_schedule import verified_schedule
        verified_schedule(json.loads(actual_schedule.read_bytes()), expected_digest=outer['schedule_sha256'])
        manifest=verified_json(self.config['source_manifest'])
        scope=self.api.source_scope(manifest,expected_manifest_hash=manifest['manifest_hash'])
        if (state['scope_genesis_hash']!=scope.genesis_hash() or completion['scope_hash']!=scope.genesis_hash()):
            raise ValueError('complete source scope differs from actual selected source')
        if (state['journal_count']!=completion['journal_count'] or state['journal_hash']!=completion['journal_hash']):
            raise ValueError('complete source checkpoint journal differs from receipt')
        self.scope=scope
        self.full_source_completion=completion
        self.ingestion_receipt_sha256=self.host['ingestion_receipt']['sha256']
        self.completion_sha256=sha(source/'completion.json')
        self.source_origins={str((source/'source.sqlite').resolve()):completion['journal_count']}
        recovery_path=source/'recovery-receipt.json'
        if 'source_lineage' in self.host:
            self.source_lineage(source,receipt)
        elif 'recovery_receipt_sha256' in receipt:
            if sha(recovery_path)!=receipt['recovery_receipt_sha256']:
                raise ValueError('full ingestion recovery lineage changed')
            recovery=json.loads(recovery_path.read_bytes())
            parent=Path(recovery['parent_path']).resolve()
            if (Path(recovery['recovered_path']).resolve()!=(source/'source.sqlite').resolve() or
                sha(parent)!=recovery['parent']['sha256'] or recovery['existing_entries_rewritten']!=0):
                raise ValueError('retained parent source differs from verified recovery lineage')
            self.source_origins[str(parent)]=recovery['parent']['count']//2*2

    def source_lineage(self,source,ingestion):
        lineage=verified_json(self.host['source_lineage'])
        if (lineage.get('schema')!='FRANKIE_CLOSED_SOURCE_LINEAGE_V1' or
            Path(lineage['final_source_path']).resolve()!=(source/'source.sqlite').resolve() or not lineage['links']):
            raise ValueError('explicit closed source lineage required')
        child=(source/'source.sqlite').resolve();seen=set()
        for index,link in enumerate(lineage['links']):
            witness=link['recovery_receipt'];recovery=verified_json(witness);parent=link['closed_parent']
            path=Path(parent['path']).resolve()
            if (str(path) in seen or path==child or Path(recovery['recovered_path']).resolve()!=child or
                Path(recovery['parent_path']).resolve()!=path or recovery['existing_entries_rewritten']!=0 or
                any(parent[k]!=recovery['parent'][k] for k in ('sha256','count','head_hash')) or
                (index==0 and witness['sha256']!=ingestion['recovery_receipt_sha256'])):
                raise ValueError('closed lineage differs from actual recovery receipts')
            if any(Path(str(path)+suffix).exists() for suffix in ('-wal','-shm','-journal')):
                raise ValueError('lineage parent must be closed before verification')
            verified(parent)
            connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
            try:tail=connection.execute('SELECT ordinal,digest FROM entries ORDER BY ordinal DESC LIMIT 1').fetchone()
            finally:connection.close()
            if tail is None or (tail[0]+1,tail[1])!=(parent['count'],parent['head_hash']):
                raise ValueError('closed lineage parent differs from independently supplied tail')
            connection=sqlite3.connect(child.as_uri()+'?mode=ro',uri=True)
            try:anchor=connection.execute('SELECT digest FROM entries WHERE ordinal=?',(recovery['journal_count']-1,)).fetchone()
            finally:connection.close()
            if anchor is None or anchor[0]!=recovery['journal_hash']:
                raise ValueError('child no longer contains its verified rehydration boundary')
            self.source_origins[str(path)]=parent['count']//2*2
            seen.add(str(path));child=path
        self.save('verified-source-lineage.c15.json',dict(witness=self.host['source_lineage'],lineage=lineage))

    def prefix(self,binding,cycle_directory):
        self.close_cache()
        # Prefix files are created and pinned by the external source host before
        # any paid lease. The first observation of its witness is retained here.
        witness_path=Path(self.host['prefixes_directory'])/f"prefix-{binding['cycle_index']:02d}-witness.json"
        value=json.loads(witness_path.read_bytes())
        if set(value)!={'snapshot','receipt'}:raise ValueError('explicit prefix file witnesses required')
        self.api.driver._save(cycle_directory/'host-prefix.c15.json',dict(witness_path=str(witness_path.resolve()),
            witness_sha256=sha(witness_path),files=value))
        snapshot=verified(value['snapshot']);receipt=verified_json(value['receipt'])
        origin=Path(receipt['original_journal']).resolve()
        if receipt.get('schema') in ('C15_JOURNAL_PREFIX_SNAPSHOT_V1','C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1'):
            if (receipt['snapshot_sha256']!=value['snapshot']['sha256'] or
                receipt['through_cursor']!=binding['through_cursor']):
                raise ValueError('new snapshot bytes/cursor differ from actual witness')
            # Preserve the copier's original receipt. Derive the two scope fields
            # in a new, separately saved outer lineage record from final source.
            outer=dict(schema='FRANKIE_SOURCE_LINKED_PREFIX_V1',snapshot_receipt=receipt,
                snapshot_receipt_sha256=value['receipt']['sha256'],
                ingestion_receipt_sha256=self.ingestion_receipt_sha256,
                source_completion_sha256=self.completion_sha256,
                source_scope_hash=self.scope.genesis_hash(),source_records_expected=self.full_source_completion['record_count'])
            self.api.driver._save(cycle_directory/'host-prefix-source-lineage.c15.json',outer)
            receipt=dict(receipt,source_scope_hash=outer['source_scope_hash'],source_records_expected=outer['source_records_expected'])
        if (str(origin) not in self.source_origins or receipt['journal_count']>self.source_origins[str(origin)] or
            Path(receipt['snapshot_journal']).resolve()!=snapshot.resolve() or
            receipt['source_scope_hash']!=self.scope.genesis_hash() or
            receipt['records_in_prefix']!=binding['through_cursor']+1 or
            receipt['source_prefix_hash']!=binding['source_hash'] or
            receipt['as_of']!=binding['as_of'] or receipt['source_as_of']!=binding['source_as_of'] or
            receipt['source_records_expected']!=57027):
            raise ValueError('actual prefix snapshot differs from full source and authored cutoff')
        connection=sqlite3.connect(origin.as_uri()+'?mode=ro',uri=True)
        try:
            row=connection.execute('SELECT digest FROM entries WHERE ordinal=?',(receipt['journal_count']-1,)).fetchone()
            if row is None or row[0]!=receipt['journal_head_hash']:
                raise ValueError('snapshot head differs from original immutable source prefix')
        finally:connection.close()
        if receipt['journal_count']!=2*receipt['records_in_prefix']:
            raise ValueError('prefix record denominator differs')
        reader = self.api.VerifiedJournalReader
        reader_options = {}
        if receipt.get('schema') == 'C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1':
            reader = self.api.FrankieCompactReader
            reader_options = dict(workers=self.host.get('data_workers', 1),
                emit=None if self.probe is None else self.probe.data)
        journal=reader(snapshot,expected_count=receipt['journal_count'],
            expected_head_hash=receipt['journal_head_hash'],**reader_options)
        old=self.builder
        self.builder=self.api.OnlinePrefix(self.scope,journal,self.api.PrefixCursor(receipt['records_in_prefix'],receipt['source_prefix_hash']))
        self.source_checkpoint=dict(count=receipt['journal_count'],head_hash=receipt['journal_head_hash'])
        self.source_journal_path=str(snapshot.resolve())
        if self.context is not None:self.context.builder=self.builder
        if old is not None:old.journal.close()

    def _training(self):
        """Precommit exact serialized states before every training SQLite insert."""
        t=self.api.training;j=self.api.journal
        self.context,self.decoder,self.optimizer,identity=self.api.native.initialize(self.builder)
        self.identity=identity
        identities=dict(training_config_hash=j.evidence_hash(self.api.native.DEVELOPMENT),
            code_hash=j.evidence_hash(self.code),source_hash=self.scope.genesis_hash(),
            model_hash=j.evidence_hash(dict(native=identity['native_hash'],decoder=sha_state(t,self.decoder))))
        self.save('initialization.c15.json',dict(identity=identity,identities=identities))
        directory=self.directory/'training-witnesses';directory.mkdir(exist_ok=True)
        path=self.directory/'training.sqlite'
        records=sorted(directory.glob('state-*.c15.json'));previous=None;allowed=[]
        for n,witness in enumerate(records):
            value=self.api.driver._load(witness)
            if (witness.name!=f'state-{n:08d}.c15.json' or value['sequence']!=n or value['before']!=previous):
                raise ValueError('independent training witness chain changed')
            allowed=[previous,value['after']];previous=value['after']
        expected=None
        if path.exists():
            db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
            try:row=db.execute('SELECT digest FROM checkpoints ORDER BY sequence DESC LIMIT 1').fetchone()
            finally:db.close()
            if row is None or row[0] not in allowed:raise ValueError('training state has no independent precommit witness')
            expected=row[0]
        elif records:raise ValueError('previously witnessed training database disappeared')
        original=t.BossTrainingCheckpoint._insert
        def insert(owner,state):
            digest=hashlib.sha256(t.encode_state(state)).hexdigest()
            self.api.driver._save(directory/f"state-{state['sequence']:08d}.c15.json",
                dict(sequence=state['sequence'],request_id=state['request_id'],before=state['previous_hash'],after=digest))
            result=original(owner,state)
            if result['checkpoint_hash']!=digest:raise ValueError('actual training insert differs from precommit')
            return result
        # Constructor initial insert must be witnessed too. The whole host has an
        # exclusive process lock; restore the class before exposing the instance.
        t.BossTrainingCheckpoint._insert=insert
        try:
            self.checkpoint=t.BossTrainingCheckpoint(path,models={'native':self.context.model,'decoder':self.decoder},
                optimizer=self.optimizer,identities=identities,create=not path.exists(),expected_checkpoint_hash=expected)
        finally:t.BossTrainingCheckpoint._insert=original
        self.checkpoint._insert=lambda state:insert(self.checkpoint,state)

    def close_cache(self):
        if self.cache is not None:
            cache=self.cache
            self.context._prepare=self.original_prepare
            self.cache=None;self.original_prepare=None
            cache.close()

    def prime_cache(self,binding,cycle_directory):
        self.close_cache()
        self.progress('boss_reasoning',unit='records')
        original=self.context._prepare
        recovery=self.host.get('retained_preparation_recovery') if binding['cycle_index']==0 else None
        if recovery is not None:
            if self.checkpoint.training_cursor!=-1:raise ValueError('first preparation recovery requires unchanged initial training')
            witness=verified_json(recovery)
            initial=self.api.journal.unpack(json.loads(verified(witness['initialization']).read_bytes()))
            if self.context._model_hash()!=initial['native_hash'] or self.context.teacher.binding!=initial['teacher_binding']:
                raise ValueError('retained preparation differs from initial native and teacher identities')
            def recover(as_of,through_cursor):
                if (as_of,through_cursor)!=(binding['as_of'],binding['through_cursor']):
                    raise ValueError('retained preparation requested for different cutoff')
                return self.api.recover_retained_preparation(self.context,witness,as_of=as_of,through_cursor=through_cursor,
                    progress=self.recovery_progress)
            self.context._prepare=recover
        try:
            cache=self.api.prepare_context_cache(self.context,as_of=binding['as_of'],through_cursor=binding['through_cursor'],
                expected_source_checkpoint=self.source_checkpoint,expected_model_hash=self.context._model_hash(),
                expected_teacher_binding=None if self.context.teacher is None else self.context.teacher.binding,
                checkpoint_hash=self.checkpoint.checkpoint_hash,current_checkpoint_hash=lambda:self.checkpoint.checkpoint_hash)
        finally:self.context._prepare=original
        try:self.api.driver._save(cycle_directory/'host-context-cache.c15.json',cache.receipt)
        except BaseException:cache.close();raise
        self.original_prepare=original;self.cache=cache
        self.context._prepare=cache.prepare
        self.progress('boss_reasoning',completed=1,total=1,unit='outputs')

    def phase(self,phase,**values):
        # Sunday learning uses the prediction's exact as_of/through_cursor/input
        # tuple; only feedback availability advances. Cache.prepare still checks
        # source/model/teacher/checkpoint identity before handing out fresh clones.
        # Release after the update is committed; runtime.release also closes on
        # failure, and prefix() closes before any later-cutoff builder is installed.
        if phase=='checkpoint_readback':self.close_cache()
        mapping={'boss_reasoning':'boss_reasoning','causal_handoff':'causal_delivery',
            'frankie_calculations':'frankie_calculation','native_learning':'boss_training',
            'checkpoint_readback':'readback','saved_completion':'output_persistence'}
        if phase in mapping:self.progress(mapping[phase],unit='steps')

    def encoding_options(self,binding):
        if self.host['context_encoding'] != 'stacked_v1':
            return None
        if self.host.get('prefix_seeds'):
            raise ValueError('raw prefix seeds require independently verified sidecar witnesses')
        index=binding['cycle_index'];seed=None
        # The original first request began at genesis. Preserve its exact options.
        if index==0:return dict(scope_public=self.scope.public_dict(),prefix_seed=None)
        manifest=verified_json(self.host['prefix_manifest'])
        full = manifest.get('schema') == 'FRANKIE_FULL_SUNDAY_PREFIX_WITNESSES_V1' and manifest.get('prefixes') == 19
        pilot = (manifest.get('schema') == 'FRANKIE_SUNDAY_PREFIX_BATCH_V1'
            and manifest.get('prefixes') == 2 and manifest.get('scheduled_cycles') == 19
            and getattr(self, 'cycle_limit', 19) <= 2)
        if (not (full or pilot) or manifest.get('source_records') != 57027
                or len(manifest.get('witnesses', [])) != manifest.get('prefixes')
                or index >= manifest['prefixes']):
            raise ValueError('independently pinned Sunday prefix manifest covering the requested cycles required')
        files=verified_json(manifest['witnesses'][index])
        receipt=verified_json(files['receipt'])
        selection=verified_json(manifest['prefix_seed_witnesses'][str(index)])
        batch=verified_json(manifest['binding'])
        if (batch.get('schema')!='FRANKIE_REMAINING_SUNDAY_PREFIXES_V1'
                or any(batch[key]['sha256']!=self.host[key]['sha256']
                       for key in ('ingestion_receipt','schedule_receipt','schedule','source_lineage'))
                or batch['source_count']!=self.full_source_completion['journal_count']
                or batch['source_head_hash']!=self.full_source_completion['journal_hash']):
            raise ValueError('prefix seed batch differs from independently pinned completed source')
        code=Path(self.repo)/'research/kalshi/frankie_boss'
        selection_code=sha(code/'context_session.py');runtime_code=sha(code/'sunday_native_runtime.py')
        if (batch['context_selection']!=dict(entity=list(self.context.entity),t_ctx=self.context.t_ctx,
                runtime_code_sha256=runtime_code,selection_code_sha256=selection_code)
                or selection.get('schema')!='FRANKIE_VERIFIED_CONTEXT_PREFIX_SEED_V1'
                or selection['selection']!='TOP_T_CTX_BY_RECEIVE_TIME_AND_CURSOR'
                or selection['cycle_index']!=index or selection['t_ctx']!=self.context.t_ctx
                or selection['entity']!=list(self.context.entity)
                or selection['source_scope_hash']!=self.scope.genesis_hash()
                or selection['source_prefix_hash']!=binding['source_hash']
                or selection['through_cursor']!=binding['through_cursor']
                or selection['as_of']!=binding['as_of'] or selection['source_as_of']!=binding['source_as_of']
                or selection['verified_records']!=binding['through_cursor']+1
                or selection['selection_code_sha256']!=selection_code or selection['runtime_code_sha256']!=runtime_code
                or selection['batch_binding_sha256']!=manifest['binding']['sha256']
                or selection['snapshot_receipt_sha256']!=files['receipt']['sha256']
                or selection['snapshot_sha256']!=files['snapshot']['sha256']
                or receipt['snapshot_sha256']!=files['snapshot']['sha256']
                or Path(files['snapshot']['path']).resolve()!=Path(self.source_journal_path).resolve()
                or receipt['journal_count']!=self.source_checkpoint['count']
                or receipt['journal_head_hash']!=self.source_checkpoint['head_hash']
                or receipt['source_prefix_hash']!=binding['source_hash']
                or receipt['through_cursor']!=binding['through_cursor']):
            raise ValueError('prefix seed differs from verified current snapshot/context selection')
        cursors=selection['context_cursors']
        if (type(cursors) is not list or len(cursors)>self.context.t_ctx
                or any(type(cursor) is not int or not 0<=cursor<=binding['through_cursor'] for cursor in cursors)
                or len(set(cursors))!=len(cursors)
                or selection['context_cursors_sha256']!=self.api.journal.evidence_hash(tuple(cursors))):
            raise ValueError('prefix seed context cursor witness invalid')
        if self.cache is not None and tuple(cursors)!=self.cache.receipt['context_cursors']:
            raise ValueError('seed selection differs from actual prepared context rows')
        ordered=sorted(cursors)
        if not cursors:reason='no_entity_context'
        elif ordered!=list(range(ordered[0],ordered[0]+len(ordered))):reason='noncontiguous_source_cursors'
        elif ordered[-1]!=binding['through_cursor']:reason='context_omits_terminal_cursor'
        else:reason=None
        if type(selection['derivable']) is not bool or selection['derivable']!=(reason is None) or selection['reason']!=reason:
            raise ValueError('seed derivability differs from exact context row coverage')
        seed=selection['seed']
        if reason is not None:
            if seed is not None:raise ValueError('missing source rows cannot authorize a prefix seed')
        elif (type(seed) is not dict or set(seed)!={'next_cursor','previous_prefix_hash','scope_genesis_hash'}
                or seed['next_cursor']!=ordered[0] or seed['scope_genesis_hash']!=self.scope.genesis_hash()
                or type(seed['previous_prefix_hash']) is not str
                or re.fullmatch('[0-9a-f]{64}',seed['previous_prefix_hash']) is None
                or (ordered[0]==0 and seed['previous_prefix_hash']!=self.scope.genesis_hash())):
            raise ValueError('exact independently witnessed preceding source prefix required')
        return dict(scope_public=self.scope.public_dict(), prefix_seed=seed)

    def prepared_input(self,binding,cycle_directory):
        path=Path(self.host['prefixes_directory'])/f"prefix-{binding['cycle_index']:02d}-preparation.json"
        if not path.exists() or (binding['cycle_index']==0 and self.host.get('retained_preparation_recovery') is not None):
            return self.api.native.prepare_critic_request(self.context,
                **{k:binding[k] for k in ('as_of','through_cursor','source_as_of')},
                output_tokens=1 if self.host.get('output_budget')=='remaining_context' else self.host['output_tokens'],
                service_context=self.host['service_context'],
                context_encoding=self.host['context_encoding'],context_encoding_options=self.encoding_options(binding))
        value=json.loads(path.read_bytes())
        if set(value)!={'body','receipt','initialization','prefix_receipt','training_checkpoint_hash'}:
            raise ValueError('explicit actual preparation witnesses required')
        body=verified(value['body']).read_bytes();receipt=verified_json(value['receipt'])
        identity=self.api.journal.unpack(json.loads(verified(value['initialization']).read_bytes()))
        prefix=verified_json(value['prefix_receipt'])
        live_hash=self.context._model_hash()
        current=self.checkpoint.checkpoint_hash
        checkpoint_ok=(value['training_checkpoint_hash']==current or
            (value['training_checkpoint_hash'] is None and self.checkpoint.training_cursor==-1
             and live_hash==self.identity['native_hash']))
        info=receipt['context']
        if (receipt.get('context_encoding','compact_v1')!=self.host['context_encoding'] or
            self.api.journal.pack(receipt.get('context_encoding_options'))!=self.api.journal.pack(self.encoding_options(binding))):
            raise ValueError('retained preparation uses a different explicit encoding/derivation identity')
        if (not checkpoint_ok or self.api.journal.pack(identity)!=self.api.journal.pack(self.identity) or
            receipt.get('model_forward_performed') is not False or receipt.get('inference_performed') is not False or
            info['model_hash']!=live_hash or receipt['request_sha256']!=hashlib.sha256(body).hexdigest() or
            receipt['request_bytes']!=len(body) or info['scope_hash']!=self.scope.genesis_hash() or
            info['source_prefix_hash']!=binding['source_hash'] or info['as_of']!=binding['as_of'] or
            info['prefix_rows']!=binding['through_cursor']+1 or info['journal_entries']!=self.source_checkpoint['count'] or
            info['journal_prefix_hash']!=self.source_checkpoint['head_hash'] or
            info['t_ctx']!=self.context.t_ctx or info['consumed_rows']!=min(info['entity_rows'],self.context.t_ctx) or
            info['teacher_binding']!=self.context.teacher.binding or
            prefix['journal_count']!=self.source_checkpoint['count'] or prefix['journal_head_hash']!=self.source_checkpoint['head_hash'] or
            prefix['source_prefix_hash']!=binding['source_hash'] or prefix['as_of']!=binding['as_of'] or
            prefix['source_as_of']!=binding['source_as_of'] or prefix['records_in_prefix']!=binding['through_cursor']+1 or
            (self.host.get('output_budget')!='remaining_context' and json.loads(body)['max_tokens']!=self.host['output_tokens'])):
            raise ValueError('retained preparation differs from current source/model/teacher/checkpoint')
        self.api.driver._save(cycle_directory/'host-preparation-reuse.c15.json',dict(
            witness_path=str(path.resolve()),witness_sha256=sha(path),witness=value,current_checkpoint_hash=current))
        return body,receipt

    def admit_preparation(self,body,receipt):
        policy=self.host.get('output_budget','explicit')
        if policy=='remaining_context':
            if 'output_tokens' in self.host:raise ValueError('remaining-context policy cannot also declare a fixed output cap')
            body,admission=self.admit.with_remaining_output(body)
            receipt=dict(receipt,request_sha256=hashlib.sha256(body).hexdigest(),request_bytes=len(body),
                output_budget='remaining_context')
        elif policy=='explicit':admission=self.admit(body)
        else:raise ValueError('explicit known output budget policy required')
        return body,receipt,admission

    def prepared_before_restart(self,binding,request_id,path):
        if not path.exists():return None
        prepared=self.api.driver._load(path)
        body=Path(prepared['request_path']).read_bytes()
        admission=prepared['admission'];receipt=prepared['receipt'];info=receipt['context']
        native_pin=self.api.native_model_pin(SimpleNamespace(context=self.context,decoder=self.decoder))
        if (prepared['request_id']!=request_id or prepared['initial_checkpoint_hash']!=self.checkpoint.checkpoint_hash or
            prepared['native_pin']!=native_pin or prepared['source_checkpoint']!=self.source_checkpoint or
            receipt['request_sha256']!=hashlib.sha256(body).hexdigest() or receipt['request_bytes']!=len(body) or
            admission['request_sha256']!=receipt['request_sha256'] or admission['tokenizer_sha256']!=self.admit.tokenizer_sha256 or
            admission['context']!=self.host['service_context'] or json.loads(body)['max_tokens']!=admission['output_tokens'] or
            info['input_hash']!=self.cache.receipt['input_hash'] or info['as_of']!=binding['as_of'] or
            info['source_prefix_hash']!=binding['source_hash'] or
            (self.host.get('output_budget')=='remaining_context' and
             (receipt.get('output_budget')!='remaining_context' or admission['input_tokens']+admission['output_tokens']!=admission['context']))):
            raise ValueError('retained pre-dispatch preparation differs from current host identities')
        return prepared

    def publish_completion(self,cycle_directory,startup,outcome):
        """Publish only persisted model outcome pins through the separate workflow."""
        directory=cycle_directory/'completion-publication'
        marker=directory/'intent.c15.json';result_path=directory/'dispatch-accepted.c15.json'
        try:
            directory.mkdir(exist_ok=True)
            if outcome['protocol']!='jobs_v1' or outcome['request_sha256']!=startup['request_sha256']:
                raise ValueError('completion differs from exact admitted startup request')
            path=Path(outcome['outcome_path']).resolve()
            if not path.is_relative_to((cycle_directory/'critic-spool').resolve()):
                raise ValueError('completion must use this cycle persisted critic outcome')
            raw=path.read_bytes();saved=json.loads(raw)
            if self.api.artifacts.canonical(saved)!=raw:
                raise ValueError('persisted completion outcome is noncanonical')
            if (saved['binding']['job_id']!=outcome['job_id'] or
                saved['binding']['body_sha256']!=outcome['request_sha256']):
                raise ValueError('completion outcome binding differs from startup')
            kind=outcome['outcome_kind']
            if kind=='model_response':
                body=base64.b64decode(saved['body_base64'],validate=True)
                if (saved['status']!='response' or saved['http_status']!=outcome['http_status'] or
                    hashlib.sha256(body).hexdigest()!=saved['body_sha256'] or saved['body_sha256']!=outcome['outcome_sha256']):
                    raise ValueError('completion model outcome bytes differ')
            elif kind=='terminal_control':
                control=saved['control']
                if (saved['status']!='fatal' or control.get('schema')!='GRANITE_DURABLE_JOB_V1' or
                    control.get('job_id')!=outcome['job_id'] or control.get('request_sha256')!=outcome['request_sha256'] or
                    control.get('state')!='failed' or
                    hashlib.sha256(self.api.artifacts.canonical(control)).hexdigest()!=saved['control_sha256'] or
                    saved['control_sha256']!=outcome['outcome_sha256']):
                    raise ValueError('completion terminal control identity differs')
            else:raise ValueError('known persisted outcome kind required')
            inputs=dict(request_sha256=outcome['request_sha256'],
                startup_sha256=hashlib.sha256(self.api.artifacts.canonical(startup)).hexdigest(),
                outcome_sha256=outcome['outcome_sha256'],job_id=outcome['job_id'],code_commit=self.host['boss_commit'])
            if any(type(value) is not str or not re.fullmatch('[0-9a-f]{40}' if name=='code_commit' else '[0-9a-f]{64}',value)
                for name,value in inputs.items()):raise ValueError('exact public completion pins required')
            intent=dict(schema='FRANKIE_RETAINED_COMPLETION_PUBLICATION_V1',inputs=inputs,
                workflow='frankie_retained_completion.yml',repository='DavisAI1974/Markets',
                ref=self.host['completion_workflow_ref'],outcome_kind=kind)
            self.api.driver._save(marker,intent)
            if result_path.exists():
                if self.api.driver._load(result_path)!=dict(intent=intent,status='workflow_dispatch_accepted'):
                    raise ValueError('retained completion publication differs')
                return
            args=['gh','workflow','run',intent['workflow'],'--repo',intent['repository'],'--ref',intent['ref']]
            for name,value in inputs.items():args+=['-f',name+'='+value]
            result=subprocess.run(args,cwd=self.repo,capture_output=True,timeout=80)
            if result.returncode!=0:
                self.api.driver._save(directory/('attempt-'+uuid.uuid4().hex+'.c15.json'),dict(intent=intent,
                    status='dispatch_not_confirmed',returncode=result.returncode,
                    stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),stderr_sha256=hashlib.sha256(result.stderr).hexdigest()))
                raise RuntimeError('completion workflow dispatch not confirmed')
            self.api.driver._save(result_path,dict(intent=intent,status='workflow_dispatch_accepted'))
        except Exception:
            raise self.api.JobAttention('RETAINED_COMPLETION_PUBLICATION_PENDING',outcome['job_id'],str(marker.resolve())) from None

    def runtime(self,binding,cycle_directory,retained_plan):
        self.progress('input_inventory',completed=binding['cycle_index'],total=19,unit='steps')
        self.source()
        self.prefix(binding,cycle_directory)
        if self.context is None:self._training()
        if self.admit is None:
            self.admit=self.api.LocalTokenizerAdmission(self.host['tokenizer_directory'],served_model_name='granite42-smoke',context=self.host['service_context'])
            if self.admit.tokenizer_sha256!=self.host['expected_tokenizer_sha256']:
                raise ValueError('actual tokenizer differs from independent accepted identity')
        key=None
        request_id=f"{self.config['run_id']}-cycle-{binding['cycle_index']:02d}"
        controller_done=self.coordinator._load(request_id,'controller') is not None
        if not controller_done:self.prime_cache(binding,cycle_directory)
        preparation=cycle_directory/'host-preparation.c15.json'
        service_record=cycle_directory/'host-service.c15.json'
        recovering_critic=not controller_done and retained_plan is not None and service_record.exists() and any((cycle_directory/'critic-spool').glob('*/dispatch.json'))
        if not controller_done and not service_record.exists():
            prepared=self.prepared_before_restart(binding,request_id,preparation)
            if prepared is None:
                body,receipt=self.prepared_input(binding,cycle_directory)
                request_path=cycle_directory/'actual-critic-request.json'
                try:body,receipt,admission=self.admit_preparation(body,receipt)
                except Exception as error:
                    self.api.driver._save(cycle_directory/'host-capacity-rejected.c15.json',
                        dict(request_id=request_id,request_sha256=hashlib.sha256(body).hexdigest(),
                             request_bytes=len(body),error_type=type(error).__name__,model_forward_performed=False))
                    raise
                if request_path.exists() and request_path.read_bytes()!=body:raise ValueError('retained actual critic request changed')
                if not request_path.exists():
                    with request_path.open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
                native_pin=self.api.native_model_pin(SimpleNamespace(context=self.context,decoder=self.decoder))
                prepared=dict(request_id=request_id,receipt=receipt,admission=admission,
                    initial_checkpoint_hash=self.checkpoint.checkpoint_hash,native_pin=native_pin,
                    request_path=str(request_path.resolve()),source_checkpoint=self.source_checkpoint)
                self.api.driver._save(preparation,prepared)
            admission=prepared['admission'];request_path=Path(prepared['request_path'])
            ready_path=cycle_directory/('host-ready-'+self.instance_id+'.c15.json')
            self.retained_ready_signal(cycle_directory,dict(status='ACTUAL_INPUT_ADMITTED_WAITING_FOR_RETAINED_SERVICE',
                host_instance_id=self.instance_id,
                request_id=request_id,request_sha256=admission['request_sha256'],request_path=str(request_path.resolve()),
                checkpoint_hash=self.checkpoint.checkpoint_hash,admission=admission,model_forward_performed=False))
            print(json.dumps(dict(status='actual_input_admitted',request_id=request_id,request_sha256=admission['request_sha256'],
                ready_path=str(ready_path))),flush=True)
            if self.prepare_only:raise PreparationComplete()
            self.progress('granite_request',unit='requests')
            # This is the only credential entrance. No credential is copied to any
            # config, artifact, exception text, environment, subprocess or log.
            key,trigger=self.read_execution_trigger('FRANKIE_ACTUAL_EXECUTE_V1',('readiness_directory','service_pins_sha256'),request_id)
            ready=Path(trigger['readiness_directory']).resolve()
            pins=verified_json(dict(path=str(ready/'service-pins.json'),sha256=trigger['service_pins_sha256']))
            service=dict(directory=str(ready),pins_sha256=trigger['service_pins_sha256'],
                files={name:sha(ready/name) for name in ('pod-info.json','startup-intent.json','run.json','service-ready.json','observer.json')})
            self.api.driver._save(service_record,service)
        else:
            prepared=self.prepared_before_restart(binding,request_id,preparation) if not controller_done else self.api.driver._load(preparation)
            if prepared is None:raise ValueError('retained readiness has no admitted preparation')
            service=self.api.driver._load(service_record)
            ready=Path(service['directory'])
            pins=verified_json(dict(path=str(ready/'service-pins.json'),sha256=service['pins_sha256']))
            dispatches=list((cycle_directory/'critic-spool').glob('*/dispatch.json'))
            if not controller_done and (not dispatches or any(not p.with_name('outcome.json').exists() for p in dispatches)):
                print(json.dumps(dict(status='same_job_recovery_requires_in_memory_credential',request_id=request_id)),flush=True)
                key,trigger=self.read_execution_trigger('FRANKIE_ACTUAL_RESUME_JOB_V1',('request_id','service_pins_sha256'),request_id)
                if trigger['request_id']!=request_id or trigger['service_pins_sha256']!=service['pins_sha256']:
                    raise ValueError('same-job recovery differs from retained service witness')
        for name,digest in service['files'].items():verified(dict(path=str(ready/name),sha256=digest))
        if pins['request_sha256']!=prepared['admission']['request_sha256'] or pins['admission']!=prepared['admission']:
            raise ValueError('startup admission differs from the actual prepared request')
        info=json.loads((ready/'pod-info.json').read_bytes())
        open_run='run.json' in service['files']
        run=json.loads((ready/('run.json' if open_run else 'lease.json')).read_bytes())
        startup=json.loads((ready/'startup-intent.json').read_bytes()) if open_run else None
        if not controller_done and not recovering_critic and (not open_run or startup['local_ready']['host_instance_id']!=self.instance_id):
            raise ValueError('actual open run must follow this admitted live host instance')
        runtime=json.loads((ready/'service-ready.json').read_bytes())
        manifest=json.loads(self.api.artifacts.DEFAULT_MANIFEST.read_bytes())
        service_inputs=self.api.verified_service_inputs(info,manifest,run,runtime_receipt=runtime,
            expected_runtime_sha256=pins['runtime_sha256'],tokenizer_admission=self.admit,
            output_tokens=prepared['admission']['output_tokens'],
            startup_intent=startup,request_timeout=None if open_run else 80,
            context_encoding=self.host['context_encoding'],service_context=self.host['service_context'],
            transport_protocol=self.host['transport_protocol'])
        service_inputs['admit_request']=retained_admission(prepared['admission'],prepared['receipt']['request_bytes'])
        if (service_inputs['config'].config_hash!=pins['config_hash'] or
            service_inputs['identity'].identity_hash!=pins['identity_hash']):raise ValueError('trusted host service pins differ')
        def critic():
            if (key is None and not recovering_critic) or not open_run or self.host['transport_protocol']!='jobs_v1':
                raise ValueError('actual in-memory credential and verified open run required')
            exchange=admitted_jobs_exchange(self.api.https_exchange_jobs,prepared['admission']['request_sha256'],
                not_dispatched=self.api.RequestNotDispatched)
            return self.api.build_runpod_service(enabled=True,api_key=key,exchange=exchange,
                event=None if self.probe is None else self.probe.job,
                spool_directory=cycle_directory/'critic-spool',recovery_only=recovering_critic,
                outcome_ready=lambda outcome:self.publish_completion(cycle_directory,startup,outcome),**service_inputs)
        policy=self.api.RefreshPolicy(tuple(tuple(band) for band in self.host['refresh_policy_bands']))
        return self.api.driver.SundayRuntime(context=self.context,decoder=self.decoder,optimizer=self.optimizer,
            checkpoint=self.checkpoint,expected_checkpoint_hash=self.checkpoint.checkpoint_hash,
            development_identity=self.identity,refresh_policy=policy,input_hash=prepared['receipt']['context']['input_hash'],
            expected_native_hash=prepared['native_pin'],expected_critic_config_hash=pins['config_hash'],
            expected_critic_identity_hash=pins['identity_hash'],critic_factory=critic,
            source_journal_path=self.source_journal_path,source_journal_checkpoint=self.source_checkpoint,release=self.close_cache,
            controller_event=None if self.probe is None else self.probe.controller,
            context_encoding=self.host['context_encoding'],context_encoding_options=self.encoding_options(binding))

    async def run(self):
        c=self.config;h=self.host
        self.coordinator=self.api.CycleCoordinator(self.directory/'cycles.sqlite',lessons_path=self.directory/'lessons.sqlite',
            frozen_memory_path=c['memory']['path'],frozen_memory_sha256=c['memory']['sha256'],
            create=not (self.directory/'cycles.sqlite').exists(),phase_callback=self.phase)
        principal=dict(mapping_directory=str(Path(c['mapping']['path']).parent),expected_mapping_sha256=c['mapping']['sha256'],
            receiver_root=c['receiver_root'],receiver_commit=c['receiver_commit'],python=sys.executable,
            admission=c.get('principal_admission'),  # audit finding 4: declared per run; undeclared refuses at use
            retained_directory=str(Path(c['retained_witnesses']['path']).parent),expected_retained_witnesses_sha256=c['retained_witnesses']['sha256'],
            delivery_receipt=c['delivery_receipt']['path'],expected_delivery_file_sha256=c['delivery_receipt']['sha256'],
            result_path=c['calculation_result']['path'],
            session_executor=lambda request:await_recorded_principal(request,self.directory,self.principal_host_lock,self.probe))
        runner=self.api.driver.SundayExecution(directory=self.directory/'execution',run_id=c['run_id'],coordinator=self.coordinator,
            contract_path=c['contract']['path'],expected_contract_sha256=c['contract']['sha256'],
            schedule_path=h['schedule']['path'],expected_schedule_sha256=h['schedule']['sha256'],runtime_factory=self.runtime,
            principal_configuration=principal,boss_commit=h['boss_commit'],agent_commit=c['receiver_commit'],
            state_defects_and_gaps_reported=h['state_defects_and_gaps_reported'])
        return await runner.run_remaining()

    def close(self):
        if hasattr(self,'_ssm_pod_key'):del self._ssm_pod_key
        self.close_cache()
        for obj in (self.checkpoint,self.coordinator):
            if obj is not None:obj.close()
        if self.builder is not None:self.builder.journal.close()


def sha_state(training,model):return hashlib.sha256(training.encode_state(model.state_dict())).hexdigest()


def stop_frames(error,limit=12):
    """Code locations of an exception and its chain: repo-relative file (bare name outside the
    repository), line and function, innermost last. No message, argument, local or path root."""
    root=Path(__file__).resolve().parents[4]
    frames=[];seen=set()
    while error is not None and id(error) not in seen and len(frames)<2*limit:
        seen.add(id(error))
        for frame in traceback.extract_tb(error.__traceback__)[-limit:]:
            path=Path(frame.filename)
            try:name=path.resolve().relative_to(root).as_posix()
            except ValueError:name=path.name
            frames.append(dict(error_type=type(error).__name__,file=name,line=frame.lineno,function=frame.name))
        error=error.__cause__ if error.__cause__ is not None else (None if error.__suppress_context__ else error.__context__)
    return frames[:2*limit]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration',required=True)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args();configuration=json.loads(Path(args.configuration).read_bytes())
    # The configuration must remain secret-free. Credential only enters later via stdin.
    if any(word in json.dumps(configuration).lower() for word in ('service_key','api_key','bearer ')):
        raise ValueError('host configuration must contain no service credentials')
    host=None
    try:
        repo=Path(configuration['host_runtime']['repository']);api=imports(repo)
        Path(configuration['run_directory']).mkdir(parents=True,exist_ok=True)
        with api._exclusive(Path(configuration['run_directory'])/'actual-host-session.lock'), \
                ReleasableHostLock(api._exclusive,Path(configuration['run_directory'])/'actual-host.lock') as host_lock, \
                HostProbe(api.RunProbe(Path(configuration['run_directory'])/'host-progress',configuration['run_id'],
                    resume=(Path(configuration['run_directory'])/'host-progress'/'progress.json').exists())) as probe:
            host=ActualHost(configuration,prepare_only=args.prepare_only,probe=probe)
            host.principal_host_lock=host_lock
            try:
                result=asyncio.run(host.run())
                probe.advance('complete',completed=len(result),total=19,unit='steps')
                print(json.dumps(dict(status='all_nineteen_cycles_complete',cycles=len(result))),flush=True)
                return 0
            except PreparationComplete:return 0
            except api.JobAttention as error:
                message=('Same durable job requires a fresh in-memory credential; no new job or Pod start.'
                    if error.code=='REMOTE_JOB_CREDENTIAL_REJECTED' else
                    'Remote job ended in terminal failure; no fragment was scored or retried.'
                    if error.code=='REMOTE_JOB_TERMINAL_FAILURE' else
                    'Same durable job requires attention; retained evidence prevents another inference.')
                print(json.dumps(dict(status=error.code,message=message,job_id=error.job_id,artifact_path=error.artifact_path,
                    cleanup_pending=error.details.get('cleanup_pending'))),flush=True)
                return 4
            except api.PendingTransport:
                print(json.dumps(dict(status='same_critic_attempt_pending_or_ambiguous',run_directory=configuration['run_directory'])),flush=True)
                return 4
            except api.PrincipalPending:
                print(json.dumps(dict(status='actual_frankie_session_pending',run_directory=configuration['run_directory'])),flush=True)
                return 3
            except api.IncompleteModelOutput as error:
                print(json.dumps(incomplete_output_alert(error)),flush=True)
                return 5
            finally:host.close()
    except Exception as error:
        # Never interpolate exception messages, locals or received stdin. The frames carry code
        # locations only (repo-relative file, line, function) for the exception and its chain: a
        # type-only stop record left run 35514761496 (2026-09-20) undiagnosable from the log.
        print(json.dumps(dict(status='stopped',error_type=type(error).__name__,frames=stop_frames(error))),flush=True)
        return 1


if __name__=='__main__':raise SystemExit(main())
