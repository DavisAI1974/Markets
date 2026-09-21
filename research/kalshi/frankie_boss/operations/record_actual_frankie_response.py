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


def candidate_of(adapter,directory):
    """The candidate adapter that validates in `directory` before the immutable final write. The admission record is
    provenance of the PRINCIPAL directory: sealed_absence() records the proof's resolved path, file_witness() refuses a
    link, and the attachment carries the record prepared there; so a candidate can neither copy nor link the proof
    (runs 35630974458, 35632243715, 35632610025, 2026-09-21). The candidate answers _admission_record with the real
    adapter's own bound method (an instance attribute shadows the class method), everything else in its own directory."""
    candidate=copy.copy(adapter)
    candidate.directory=Path(directory)
    candidate._admission_record=adapter._admission_record
    return candidate


def live_classroom(request,classroom_package,derive,json_form):
    """The attachment's Dipole classroom block in its LIVE form. The classroom adapter compares
    attachment['dipole_classroom'] with final_model_visible_classroom(package) by Python equality; the package comes
    from the c15 loader (tuples), the attachment from session-request.json (lists), so the retained request could never
    pass ('principal attachment Dipole classroom differs from final model-visible contract', run 35632927377,
    2026-09-21). Every comparison of a retained file against a live object goes through json_form (the adapter's own
    rule): when the two agree in JSON form, the live object is put into the attachment; otherwise the attachment is
    left as read and the adapter refuses as before. Returns 'live' or 'unchanged'."""
    attachment=request.get('attachment') or {}
    if 'dipole_classroom' not in attachment:return 'unchanged'
    live=derive(classroom_package)
    if json_form(live)!=attachment['dipole_classroom']:return 'unchanged'
    attachment['dipole_classroom']=live
    return 'live'


def classroom_normalizer(classroom_package,derive,json_form):
    """A function attachment -> attachment with the Dipole classroom block in its live form (see live_classroom). The
    adapter re-reads session-request.json inside verify() and recovers again (run 35633328702), so every recover the
    recorder makes goes through this, not only the first."""
    def normalize(attachment):
        holder={'attachment':dict(attachment)}
        live_classroom(holder,classroom_package,derive,json_form)
        return holder['attachment']
    return normalize


def record_checked(adapter,request,response,attestation,binding,input_hash,canonical,normalize_attachment=lambda attachment:attachment,classroom_grade=None):
    """Validate in a retained candidate directory before the immutable final write. classroom_grade, when given, is the
    runner's own Dipole classroom grade of the response (turn 1): a response the runner would stop on (run 35633661236's
    response carried no dipole_teachback; the runner raised inside validate_teachback) is refused HERE, nothing written."""
    from research.kalshi.frankie_boss.frankie_principal_adapter import FrankiePrincipalAdapter
    final=adapter.directory/'session-response.json'
    expected=dict(response=response,host_attestation=attestation)
    candidate=candidate_of(adapter,adapter.directory/('response-check-'+uuid.uuid4().hex))
    candidate.directory.mkdir()
    (candidate.directory/'receiver').mkdir()
    (candidate.directory/'session-request.json').write_bytes(canonical(request))
    (candidate.directory/'session-response.json').write_bytes(canonical(expected))
    for name in request['attachment']['preparation_receipt']['outputs']:
        if Path(name).name!=name:raise ValueError('receiver output must be a direct member')
        shutil.copyfile(adapter.directory/'receiver'/name,candidate.directory/'receiver'/name)
    # Validate the initial durable response without pretending that the mandatory
    # second classroom turn has already completed. The live host owns grading.
    initial_recover=lambda request_id,attachment: FrankiePrincipalAdapter.recover(candidate,request_id,normalize_attachment(attachment))
    envelope=initial_recover(request['request_id'],request['attachment'])
    view=SimpleNamespace(directory=candidate.directory,recover=initial_recover)
    feedback=FrankiePrincipalAdapter.verify(view,envelope,request_id=request['request_id'],input_hash=input_hash,
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
    pregrade=None if classroom_grade is None else classroom_grade(response)
    if final.exists():
        if final.read_bytes()!=canonical(expected):raise ValueError('retained final principal response differs')
    else:adapter.record_session_response(response,host_attestation=attestation)
    result=FrankiePrincipalAdapter.recover(adapter,request['request_id'],normalize_attachment(request['attachment']))
    if pregrade is not None:result=dict(result,classroom_pregrade=pregrade)
    return result


def classroom_pregrade(classroom_package):
    """The host runner's classroom grade of an initial response (grade_initial_response + the relationship cross-check +
    the novel-findings validation, exactly what _recover_with_classroom runs), reduced to what the record receipt carries."""
    from research.kalshi.frankie_boss.dipole_classroom_session import grade_initial_response
    from research.kalshi.frankie_boss.dipole_classroom_final_review import apply_relationship_view_crosscheck,validate_novel_findings
    def grade(response):
        teachback,graded=grade_initial_response(classroom_package,response)
        graded=apply_relationship_view_crosscheck(graded,response)
        findings=validate_novel_findings(response.get('dipole_novel_findings'),classroom_package['pre_message'])
        return dict(mastered=graded['mastered'],correction_ids=list(graded['correction_ids']),novel_findings=len(findings),
            observation_claims_reviewed=graded['exhaustive_audit']['observation_claims_reviewed'],
            relationship_pairs_reviewed=graded['exhaustive_audit']['relationship_pairs_reviewed'],post_grade_hash=graded['post_grade_hash'])
    return grade


def record_correction(adapter,principal,response,attestation,request_id):
    """Turn 2: record the same session's answer to the Dipole classroom correction request the runner retained. The
    runner (PrincipalPending, 'same Frankie session must consume Dipole classroom correction') waits for
    classroom-correction-response.json; this validates the answer exactly as _recover_with_classroom will (host attestation
    bound to the correction request, validate_correction_response against the retained post-grade,
    validate_correction_resolutions) and writes it through the adapter's own immutable recorder."""
    from research.kalshi.frankie_boss.dipole_classroom_session import CORRECTION_REQUEST_SCHEMA,validate_correction_response
    from research.kalshi.frankie_boss.dipole_classroom_resolution import validate_correction_resolutions
    principal=Path(principal)
    request_path=principal/'classroom-correction-request.json';initial_path=principal/'session-response.json'
    if not initial_path.exists():raise ValueError('the initial principal response is not recorded; the correction turn cannot precede it')
    if not request_path.exists():raise ValueError('no Dipole classroom correction request is retained; the runner writes it after grading the initial response')
    correction=json.loads(request_path.read_bytes())
    if correction.get('schema')!=CORRECTION_REQUEST_SCHEMA:raise ValueError('retained correction request schema differs')
    initial=json.loads(initial_path.read_bytes())['response']
    grade_path=Path(adapter.audit_directory)/'dipole-classroom-post-grade.json'
    if not grade_path.exists():raise ValueError('no retained Dipole post-grade in the audit directory; the runner grades before it asks for a correction')
    grade=json.loads(grade_path.read_bytes())
    if grade.get('post_grade_hash')!=correction.get('post_grade_hash'):raise ValueError('retained post-grade differs from the correction request')
    adapter._attest_host(response,attestation,correction)
    base=validate_correction_response(correction=correction,response=response,initial_response=initial,grade=grade)
    ack=validate_correction_resolutions(response.get('dipole_acknowledgement'),grade,base)
    adapter._record_correction_response(correction,dict(response=response,host_attestation=attestation))
    return dict(request_id=request_id,correction_request_sha256=correction['request_sha256'],post_grade_hash=correction['post_grade_hash'],
        resolutions=len(ack['correction_resolutions']),remaining_disagreements=list(ack['remaining_disagreements']),mastered=grade.get('mastered'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('configuration','configuration-sha256','response','response-sha256','host-attestation','host-attestation-sha256'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--cycle-index',type=int,required=True)
    parser.add_argument('--turn',choices=('initial','correction'),default='initial')
    args=parser.parse_args()
    config=verified_json(args.configuration,args.configuration_sha256);h=config['host_runtime']
    sys.path.insert(0,h['repository'])
    from research.kalshi.frankie_boss.sunday_execution import _load
    from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle,make_principal_adapter
    from research.kalshi.frankie_boss.frankie_principal_adapter import canonical
    from research.kalshi.frankie_boss.feedback_cycle import _exclusive
    from research.kalshi.frankie_boss.dipole_classroom_integration import IntegratedDipoleClassroomPrincipalAdapter
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
        # Host-only package loading: withheld targets are never printed or placed
        # in the model-facing response. The actual host still grades both turns.
        classroom_package={
            name.replace('-','_'): _load(directory/('host-dipole-classroom-'+name+'.c15.json'))
            for name in ('source','teacher-key','pre-message','binding')}
        from research.kalshi.frankie_boss.dipole_classroom_final_review import final_model_visible_classroom
        from research.kalshi.frankie_boss.frankie_principal_adapter import json_form
        print('attachment dipole_classroom: '+live_classroom(request,classroom_package,final_model_visible_classroom,json_form))
        normalize=classroom_normalizer(classroom_package,final_model_visible_classroom,json_form)
        adapter=make_principal_adapter(binding=binding,handoff_directory=export['directory'],
            expected_manifest_sha256=export['manifest_sha256'],boss_journal_path=plan['source_journal_path'],
            source_journal_checkpoint=plan['source_journal_checkpoint'],mapping_directory=str(Path(config['mapping']['path']).parent),
            expected_mapping_sha256=config['mapping']['sha256'],receiver_root=config['receiver_root'],
            receiver_commit=config['receiver_commit'],python=sys.executable,directory=principal,admission=config.get('principal_admission'),
            retained_directory=str(Path(config['retained_witnesses']['path']).parent),
            expected_retained_witnesses_sha256=config['retained_witnesses']['sha256'],
            delivery_receipt=config['delivery_receipt']['path'],expected_delivery_file_sha256=config['delivery_receipt']['sha256'],
            result_path=config['calculation_result']['path'],session_executor=None,
            classroom_package=classroom_package,adapter_class=IntegratedDipoleClassroomPrincipalAdapter)
        response=verified_json(args.response,args.response_sha256)
        attestation=verified_json(args.host_attestation,args.host_attestation_sha256)
        if args.turn=='correction':
            result=record_correction(adapter,principal,response,attestation,request['request_id'])
            print(json.dumps(dict(status='actual_classroom_correction_recorded',**result)))
            return
        result=record_checked(adapter,request,response,attestation,binding,plan['input_hash'],canonical,normalize_attachment=normalize,
            classroom_grade=classroom_pregrade(classroom_package))
        print(json.dumps(dict(status='actual_principal_response_recorded',request_id=request['request_id'],
            principal_receipt_sha256=result['principal_receipt']['receipt_sha256'],classroom_pregrade=result.get('classroom_pregrade'))))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='refused',error_type=type(error).__name__,error=str(error)[:800])))
        raise SystemExit(1)
