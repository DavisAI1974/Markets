"""Authenticated workflow transport for an already retained day-pipeline WAIT.

No event creates execution authority. Source/configuration/receipt commits are separate;
only raw JSON receipt files are overlaid from the latter. The existing DayPipeline
and host readers remain the admission authorities.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WAIT = load_module('_workflow_event_wait', HERE/'workflow_wait.py')
DELIVERY = load_module('_workflow_event_delivery', HERE/'workflow_delivery.py')
canonical = WAIT.canonical
FIELDS = {'schema','event_id','action','source_commit','receipts_commit','day',
          'pipeline_configuration','runs_root','go','context','payload'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def full_sha(value, length=64):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(length)+'}', value) is not None


def relative(value):
    if (type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_./-]+',value)
            or any(part in ('','.','..') for part in value.split('/'))):
        raise ValueError('explicit repository-relative path required')
    return value


def seal(event):
    body = {key:value for key,value in event.items() if key != 'event_id'}
    return dict(body, event_id=sha(canonical(body)))


def validate_shape(event):
    if (type(event) is not dict or set(event)!=FIELDS
            or event['schema']!='FRANKIE_WORKFLOW_EVENT_V1'
            or event['action'] not in ('archive','readiness','principal')
            or event != seal(event)
            or not full_sha(event['source_commit'],40) or not full_sha(event['receipts_commit'],40)
            or not full_sha(event['go']) or not re.fullmatch(r'[0-9]{8}',str(event['day']))):
        raise ValueError('exact retained workflow event required')
    pin=event['pipeline_configuration']
    if type(pin) is not dict or set(pin)!={'path','sha256'} or not full_sha(pin['sha256']):
        raise ValueError('exact pipeline configuration pin required')
    relative(pin['path']); relative(event['runs_root'])
    DELIVERY.validate_context(event['context'])
    if type(event['payload']) is not dict:
        raise ValueError('explicit action payload required')
    return event


def expected_context(pipeline, pending):
    automation=pipeline.c.get('workflow_automation')
    if type(automation) is not dict or set(automation)!={'context','archive','workflow_ref'}:
        raise ValueError('predeclared workflow automation required')
    static=automation['context']
    if type(static) is not dict or set(static)!={'configuration_path','tools_root','tools_commit','python'}:
        raise ValueError('predeclared tooling context required')
    gate=pending['gate']; wait=gate['wait_receipt']; index=wait['cycle_index']
    member=(f'execution/cycle-{index:02d}/actual-critic-request.json'
            if wait['kind'] in ('readiness','service_resume') else
            f'execution/cycle-{index:02d}/principal/'+
            ('classroom-correction-request.json' if wait['kind']=='principal_correction' else 'session-request.json'))
    expected=dict(static,configuration_sha256=gate['prepared_configuration_sha256'],
        wait_receipt_path=gate['receipt_path'],wait_receipt_sha256=gate['receipt_sha256'],
        request_id=wait['request_id'],request_sha256=wait['artifacts'][member]['sha256'])
    return DELIVERY.validate_context(expected)


def validate_event(event,pipeline):
    validate_shape(event)
    pending=pipeline.pending()
    if not pending or pending['status']!='WAIT' or pending['gate']['wait_receipt']['state']!='WAIT':
        raise ValueError('event requires an existing resumable WAIT')
    gate=pending['gate']; wait=gate['wait_receipt']
    pin=event['pipeline_configuration']
    raw=WAIT._read(pin['path'])
    if sha(raw)!=pin['sha256'] or json.loads(raw)!=pipeline.c:
        raise ValueError('pipeline configuration changed')
    if (event['day']!=pipeline.day or Path(event['runs_root']).resolve()/pipeline.day!=pipeline.directory.resolve()
            or event['go']!=pipeline.receipt('stage-sources')['gate']['manifest_hash']
            or event['context']!=expected_context(pipeline,pending)):
        raise ValueError('event differs from retained pipeline and request')
    prepared=pipeline.receipt('schedule-prefixes')['gate']['configuration']
    if (event['context']['configuration_path']!=prepared['path']
            or event['context']['configuration_sha256']!=prepared['sha256']):
        raise ValueError('event differs from independently prepared configuration')
    payload=event['payload']; action=event['action']; archive=pipeline.c['workflow_automation']['archive']
    if payload.get('instance')!=pipeline.c['instance']:
        raise ValueError('event cannot select a different host')
    if action=='archive':
        required={'request_sha256','cycle_index','instance','day','run_root','bucket','key_parameter'}
        if (set(payload)!=required or wait['kind']!='readiness'
                or payload!=dict(archive,request_sha256=event['context']['request_sha256'],
                    cycle_index=f"{wait['cycle_index']:02d}",day=pipeline.day)):
            raise ValueError('archive event differs from exact existing request')
    elif action=='readiness':
        if (set(payload)!={'ready_run_id','ready_source_commit','instance'}
                or wait['kind'] not in ('readiness','service_resume')
                or type(payload['ready_run_id']) is not str or not re.fullmatch('[1-9][0-9]*',payload['ready_run_id'])
                or not full_sha(payload['ready_source_commit'],40)):
            raise ValueError('readiness event requires exact authenticated producer')
    else:
        required={'source_ref','response_path','attestation_path','record_path','turn','instance','bucket'}
        if (set(payload)!=required or wait['kind'] not in ('principal','principal_correction')
                or payload['turn']!=('initial' if wait['kind']=='principal' else 'correction')
                or not full_sha(payload['source_ref'],40) or payload['bucket']!=archive['bucket']):
            raise ValueError('principal event differs from retained turn')
        for name in ('response_path','attestation_path','record_path'):relative(payload[name])
    return event


def verify_release(pipeline,wait):
    if not pipeline.c.get('workflow_automation'):
        return False
    pin=pipeline.c.get('owner_release')
    if pin is None:return False
    if type(pin) is not dict or set(pin)!={'path','sha256'} or not full_sha(pin['sha256']):
        raise ValueError('pinned owner release required')
    path=Path(pin['path'])
    if not path.exists():return False
    raw=WAIT._read(path)
    if sha(raw)!=pin['sha256']:raise ValueError('owner release bytes changed')
    value=json.loads(raw)
    fields={'schema','run_id','prepared_configuration_sha256','source_manifest_hash','schedule_sha256',
            'final_workflow_task','owner_release','allowed_action','execution_scope_sha256'}
    pending=pipeline.pending()
    if not pending or pending['gate']['wait_receipt']!=wait:
        raise ValueError('owner release requires current retained WAIT')
    gate=pending['gate']
    task=value.get('final_workflow_task') if type(value) is dict else None
    scope=wait['artifacts'].get('workflow-execution-scope.json')
    if (type(value) is not dict or set(value)!=fields
            or value['schema']!='FRANKIE_WORKFLOW_OWNER_RELEASE_V1'
            or value['owner_release'] is not True or value['allowed_action']!='resume_existing_wait'
            or type(task) is not dict or set(task)!={'id','completed'} or task['completed'] is not True
            or type(task['id']) is not str or not task['id'].strip()
            or not scope or value['execution_scope_sha256']!=scope['sha256']
            or value['run_id']!=wait['run_id']
            or value['prepared_configuration_sha256']!=gate['prepared_configuration_sha256']
            or value['source_manifest_hash']!=pipeline.receipt('stage-sources')['gate']['manifest_hash']
            or value['schedule_sha256']!=gate['schedule_sha256']):
        raise ValueError('owner final task and exact existing execution scope must be released')
    return True


def dispatch_event(directory,event,dispatch):
    validate_shape(event)
    directory=Path(directory)
    intent=dict(schema='FRANKIE_WORKFLOW_EVENT_OUTBOX_V1',event=event)
    WAIT._publish(directory/'intent.json',intent)
    accepted=dict(status='workflow_dispatch_accepted',event_id=event['event_id'],event_sha256=sha(canonical(event)))
    marker=directory/'accepted.json'
    if marker.exists():
        WAIT._publish(marker,accepted)
        return accepted
    try:
        if dispatch(json.loads(canonical(event))) is not True:
            raise RuntimeError('workflow dispatch not confirmed')
    except Exception:
        WAIT._publish(directory/('attempt-'+uuid.uuid4().hex+'.json'),
                      dict(status='dispatch_not_confirmed',event_id=event['event_id']))
        raise
    WAIT._publish(marker,accepted)
    return accepted


def load_pipeline(event,*,overlay=True):
    validate_shape(event)
    current=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if current!=event['source_commit']:
        raise ValueError('workflow implementation differs from exact source commit')
    pin=event['pipeline_configuration']
    raw=WAIT._read(pin['path'])
    if sha(raw)!=pin['sha256'] or subprocess.check_output(['git','show','HEAD:'+pin['path']])!=raw:
        raise ValueError('pipeline configuration must be pinned in the source checkout')
    configuration=json.loads(raw)
    release=configuration.get('owner_release')
    if release is not None:
        release_path=relative(release['path'])
        if Path(release_path).exists():
            source_release=subprocess.check_output(['git','show','HEAD:'+release_path])
            if source_release!=WAIT._read(release_path) or sha(source_release)!=release['sha256']:
                raise ValueError('owner release must be pinned by the source checkout')
    if overlay:
        subprocess.run(['git','fetch','--no-tags','--depth=1','origin',event['receipts_commit']],check=True,
                       stdout=subprocess.DEVNULL)
        folder=event['runs_root']+'/'+event['day']
        entries=subprocess.check_output(['git','ls-tree','-r',event['receipts_commit'],'--',folder],text=True).splitlines()
        stage_names={'00-stage-sources.json':'stage-sources','01-host-start.json':'host-start',
                     '02-ingest.json':'ingest','03-schedule-prefixes.json':'schedule-prefixes',
                     '04-cycles.json':'cycles','05-package-upload.json':'package-upload',
                     '06-snapshot-stop.json':'snapshot-stop'}
        for entry in entries:
            metadata,name=entry.split('\t',1); mode,kind,blob=metadata.split()
            relative(name)
            base=Path(name).name
            if Path(name).parent.as_posix()!=folder:continue
            stage=stage_names.get(base)
            if re.fullmatch(r'04-cycles-wait-[0-9a-f]{64}\.json',base):stage='cycles'
            if re.fullmatch(r'04-cycles-batch-[0-9]+\.json',base):stage='cycles'
            if stage is None:continue
            if name==pin['path'] or (release is not None and name==release['path']) or mode!='100644' or kind!='blob':
                raise ValueError('receipt overlay cannot substitute source or linked evidence')
            raw=subprocess.check_output(['git','show',event['receipts_commit']+':'+name])
            value=json.loads(raw)
            if (type(value) is not dict or value.get('schema')!='FRANKIE_DAY_PIPELINE_RECEIPT_V1'
                    or value.get('day')!=event['day'] or value.get('stage')!=stage):
                raise ValueError('only exact day-pipeline receipt schemas may be overlaid')
            path=DELIVERY.checked_path(name)
            if path.exists():
                if WAIT._read(path)!=raw:raise ValueError('immutable receipt overlay differs')
            else:DELIVERY.publish_bytes(path,raw)
    module=load_module('_workflow_event_pipeline',HERE/'day_pipeline.py')
    pipeline=module.DayPipeline(configuration,event['day'],runs_root=event['runs_root'])
    validate_event(event,pipeline)
    return pipeline


def archive_event(pipeline,*,source_commit,receipts_commit,configuration_path,runs_root,go):
    pending=pipeline.pending()
    if not pipeline.c.get('workflow_automation') or not pending or pending['status']!='WAIT':
        return None
    wait=pending['gate']['wait_receipt']
    if wait['kind']!='readiness':return None
    context=expected_context(pipeline,pending)
    event=seal(dict(schema='FRANKIE_WORKFLOW_EVENT_V1',action='archive',source_commit=source_commit,
        receipts_commit=receipts_commit,day=pipeline.day,pipeline_configuration=dict(path=configuration_path,
        sha256=sha(WAIT._read(configuration_path))),runs_root=runs_root,go=go,context=context,
        payload=dict(pipeline.c['workflow_automation']['archive'],request_sha256=context['request_sha256'],
                     cycle_index=f"{wait['cycle_index']:02d}",day=pipeline.day)))
    return validate_event(event,pipeline)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('validate','resume','prepare-outbox','dispatch','emit-archive'))
    parser.add_argument('--event')
    parser.add_argument('--directory',default='workflow-event-outbox')
    parser.add_argument('--configuration')
    parser.add_argument('--day')
    parser.add_argument('--source-commit')
    parser.add_argument('--receipts-commit')
    parser.add_argument('--runs-root')
    parser.add_argument('--go')
    args=parser.parse_args()
    if args.mode=='emit-archive':
        module=load_module('_workflow_event_pipeline',HERE/'day_pipeline.py')
        pipeline=module.DayPipeline(json.loads(WAIT._read(args.configuration)),args.day,runs_root=args.runs_root)
        event=archive_event(pipeline,source_commit=args.source_commit,receipts_commit=args.receipts_commit,
                            configuration_path=args.configuration,runs_root=args.runs_root,go=args.go)
        if event is None:
            print(json.dumps(dict(status='no_automatic_archive_event')))
            return
    else:
        event=validate_shape(json.loads(WAIT._read(args.event)))
        pipeline=load_pipeline(event)
    directory=Path(args.directory)
    if args.mode in ('prepare-outbox','emit-archive'):
        WAIT._publish(directory/'event.json',event)
        WAIT._publish(directory/'intent.json',dict(schema='FRANKIE_WORKFLOW_EVENT_OUTBOX_V1',event=event))
        print(json.dumps(dict(status='dispatch_intent_retained',event_id=event['event_id'])))
    elif args.mode=='dispatch':
        # Caller must upload this exact intent as an artifact successfully before this invocation.
        if os.environ.get('WORKFLOW_OUTBOX_ARTIFACT_CONFIRMED')!='true':
            raise ValueError('durable uploaded outbox artifact required before dispatch')
        expected=dict(schema='FRANKIE_WORKFLOW_EVENT_OUTBOX_V1',event=event)
        if json.loads(WAIT._read(directory/'intent.json'))!=expected:
            raise ValueError('retained dispatch intent differs')
        ref=pipeline.c['workflow_automation']['workflow_ref']
        if type(ref) is not str or not re.fullmatch(r'[A-Za-z0-9_./-]+',ref) or ref.startswith('-'):
            raise ValueError('explicit workflow branch or tag required')
        def send(value):
            command=['gh','workflow','run','frankie_journal_stack.yml','--repo','DavisAI1974/Markets','--ref',ref,
                     '-f','continuation_event='+canonical(value).decode(),'-f','day='+value['day'],
                     '-f','checks_only=true','-f','keep_compute=true']
            result=subprocess.run(command,capture_output=True,timeout=80)
            return result.returncode==0
        print(json.dumps(dispatch_event(directory,event,send)))
    elif args.mode=='resume':
        wait=pipeline.pending()['gate']['wait_receipt']
        if not verify_release(pipeline,wait):
            print(json.dumps(dict(status='HELD',reason='owner_final_workflow_release_required')))
            return
        result=pipeline.run_stage('cycles',go=event['go'],resume_wait=event['context']['wait_receipt_sha256'])
        print(json.dumps(dict(status=result,pending=pipeline.pending())))
    else:
        released=verify_release(pipeline,pipeline.pending()['gate']['wait_receipt'])
        output=dict(event=event,released=released)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as stream:
                stream.write('event='+canonical(event).decode()+'\n')
                stream.write('released='+str(released).lower()+'\n')
        print(json.dumps(output,sort_keys=True))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='workflow_event_refused',error_type=type(error).__name__)))
        raise SystemExit(1)
