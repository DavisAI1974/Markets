"""Record an actual host-attested Frankie response; inert until explicitly invoked.

This helper neither invokes an agent nor creates session provenance. The root
host must supply the real response and independent session attestation witnesses.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid
from types import SimpleNamespace


def verified_json(path,digest):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('independent file witness differs')
    return json.loads(raw)


def record_checked(adapter,request,response,attestation,binding,input_hash,canonical):
    """Validate in a retained candidate directory before the immutable final write."""
    final=adapter.directory/'session-response.json'
    expected=dict(response=response,host_attestation=attestation)
    candidate=copy.copy(adapter)
    candidate.directory=adapter.directory/('response-check-'+uuid.uuid4().hex)
    candidate.directory.mkdir()
    (candidate.directory/'receiver').mkdir()
    (candidate.directory/'session-request.json').write_bytes(canonical(request))
    (candidate.directory/'session-response.json').write_bytes(canonical(expected))
    for name in request['attachment']['preparation_receipt']['outputs']:
        if Path(name).name!=name:raise ValueError('receiver output must be a direct member')
        shutil.copyfile(adapter.directory/'receiver'/name,candidate.directory/'receiver'/name)
    envelope=candidate.recover(request['request_id'],request['attachment'])
    feedback=candidate.verify(envelope,request_id=request['request_id'],input_hash=input_hash,
        source_hash=binding['source_hash'],learning_cutoff_ns=binding['learning_cutoff_ns'])
    if (not binding['as_of']<=feedback.available_ns<=binding['learning_cutoff_ns'] or
        tuple(s.session_id for s in feedback.sessions)!=tuple(s.session_id for _,s in binding['sessions']) or
        type(envelope['lessons']) not in (list,tuple)):
        raise ValueError('principal feedback chronology, roster or lessons differ')
    # Use the learner's exact pure label checks without constructing a model,
    # optimizer, context, or source reader. In particular, a censored tail does
    # not establish STOP; STOP requires observations through the session close.
    from research.kalshi.frankie_boss.native_forecast_learning import NativeForecastLearner
    validator=object.__new__(NativeForecastLearner)
    validator.config=SimpleNamespace(session_weights=tuple((s.session_id,1.0) for _,s in binding['sessions']))
    validator._validate(binding['sessions'],feedback,binding['as_of'],binding['learning_cutoff_ns'])
    if final.exists():
        if final.read_bytes()!=canonical(expected):raise ValueError('retained final principal response differs')
    else:adapter.record_session_response(response,host_attestation=attestation)
    return adapter.recover(request['request_id'],request['attachment'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('configuration','configuration-sha256','response','response-sha256','host-attestation','host-attestation-sha256'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--cycle-index',type=int,required=True)
    args=parser.parse_args()
    config=verified_json(args.configuration,args.configuration_sha256);h=config['host_runtime']
    sys.path.insert(0,h['repository'])
    from research.kalshi.frankie_boss.sunday_execution import _load
    from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle,make_principal_adapter
    from research.kalshi.frankie_boss.frankie_principal_adapter import canonical
    from research.kalshi.frankie_boss.feedback_cycle import _exclusive
    if not 0<=args.cycle_index<19:raise ValueError('authored cycle index required')
    schedule=verified_json(h['schedule']['path'],h['schedule']['sha256'])
    steps=schedule['steps'] if type(schedule) is dict else schedule
    binding=bind_cycle(config['contract']['path'],config['contract']['sha256'],args.cycle_index,steps[args.cycle_index])
    run=Path(config['run_directory']);directory=run/'execution'/f'cycle-{args.cycle_index:02d}'
    with _exclusive(run/'actual-host.lock'):
        plan=_load(directory/'request-plan.c15.json');export=_load(directory/'principal-export.c15.json')
        principal=directory/'principal'
        # Recording cannot initiate source binding, receiver preparation or a session.
        if not (principal/'bound-mapping.json').exists() or not (principal/'session-request.json').exists():
            raise ValueError('actual retained principal request and mapping required')
        request=json.loads((principal/'session-request.json').read_bytes())
        if request['request_id']!=plan['request_id']:raise ValueError('retained principal request differs from plan')
        adapter=make_principal_adapter(binding=binding,handoff_directory=export['directory'],
            expected_manifest_sha256=export['manifest_sha256'],boss_journal_path=plan['source_journal_path'],
            source_journal_checkpoint=plan['source_journal_checkpoint'],mapping_directory=str(Path(config['mapping']['path']).parent),
            expected_mapping_sha256=config['mapping']['sha256'],receiver_root=config['receiver_root'],
            receiver_commit=config['receiver_commit'],python=sys.executable,directory=principal,admission=config.get('principal_admission'),
            retained_directory=str(Path(config['retained_witnesses']['path']).parent),
            expected_retained_witnesses_sha256=config['retained_witnesses']['sha256'],
            delivery_receipt=config['delivery_receipt']['path'],expected_delivery_file_sha256=config['delivery_receipt']['sha256'],
            result_path=config['calculation_result']['path'],session_executor=None)
        response=verified_json(args.response,args.response_sha256)
        attestation=verified_json(args.host_attestation,args.host_attestation_sha256)
        result=record_checked(adapter,request,response,attestation,binding,plan['input_hash'],canonical)
        print(json.dumps(dict(status='actual_principal_response_recorded',request_id=request['request_id'],
            principal_receipt_sha256=result['principal_receipt']['receipt_sha256'])))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='refused',error_type=type(error).__name__)))
        raise SystemExit(1)
