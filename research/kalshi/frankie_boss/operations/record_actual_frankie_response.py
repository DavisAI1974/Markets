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
    view=SimpleNamespace(directory=candidate.directory,recover=initial_recover,
        feedback_contract=getattr(adapter, 'feedback_contract', {}))
    feedback=FrankiePrincipalAdapter.verify(view,envelope,request_id=request['request_id'],input_hash=input_hash,
        source_hash=binding['source_hash'],learning_cutoff_ns=binding['learning_cutoff_ns'])
    if type(envelope['lessons']) not in (list,tuple):
        raise ValueError('principal feedback chronology, roster or lessons differ')
    if feedback is not None:
        if (not binding['as_of']<=feedback.available_ns<=binding['learning_cutoff_ns'] or
            tuple(s.session_id for s in feedback.sessions)!=tuple(s.session_id for _,s in binding['sessions'])):
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


def retained_outcome_coordinator(config, run):
    """Reuse the actual host's exact lineage loading without constructing its runtime.

    Requiring the existing lineage first prevents the coordinator constructor from
    adopting or migrating a legacy database. No models, source readers or remote
    services are constructed by the host's coordinator initialization method.
    """
    import sqlite3
    from research.kalshi.frankie_boss.feedback_cycle import CycleCoordinator
    from research.kalshi.frankie_boss.operations.run_actual_sunday import ActualHost
    from research.kalshi.frankie_boss.sunday_execution import _load
    run=Path(run)
    if not all((run/name).is_file() for name in ('cycles.sqlite','lessons.sqlite')):
        raise ValueError('outcome recording requires retained cycle and lessons databases')
    db=sqlite3.connect((run/'cycles.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    try:
        saved=CycleCoordinator._load(SimpleNamespace(db=db),
            CycleCoordinator.LINEAGE_REQUEST,CycleCoordinator.LINEAGE_STAGE)
        if saved is None:
            raise ValueError('outcome recording cannot initialize missing knowledge lineage')
    finally:
        db.close()
    def verify_saved(name,body):
        if _load(run/name)!=body:
            raise ValueError('retained historical priming provenance differs')
    # A minimal receiver for this one existing host method. Its create flag is
    # necessarily false because both retained databases were required above.
    host=SimpleNamespace(config=config,host=config['host_runtime'],directory=run,
        api=SimpleNamespace(CycleCoordinator=CycleCoordinator),save=verify_saved,phase=None)
    ActualHost._initialize_coordinator(host)
    host.coordinator.db.execute('PRAGMA query_only=ON')
    host.coordinator.lessons.execute('PRAGMA query_only=ON')
    return host.coordinator


def record_outcome(adapter,config,run,plan,binding,*,learning_cutoff_ns,
                   prepare=False,response=None,attestation=None):
    """Prepare or record only the later outcome turn under existing host locks."""
    from research.kalshi.frankie_boss.feedback_cycle import _exclusive, _plain
    from research.kalshi.frankie_boss.c15_journal import evidence_hash
    from research.kalshi.frankie_boss.frankie_principal_adapter import PrincipalPending
    from research.kalshi.frankie_boss.pending_target_feedback import PendingTargetFeedbackAdapter
    from research.kalshi.frankie_boss.sunday_execution import _adapter_identity
    if type(learning_cutoff_ns) is not int:
        raise ValueError('outcome turn requires explicit integer learning cutoff')
    if plan['principal_adapter_identity']!=_adapter_identity(type(adapter)):
        raise ValueError('outcome recorder requires the original concrete principal adapter')
    with _exclusive(str(Path(run)/'cycles.sqlite')+'.lock'):
        coordinator=retained_outcome_coordinator(config,run)
        try:
            request_id=plan['request_id']
            original=coordinator._load(request_id,'principal_output')
            retained_binding=coordinator._load(request_id,'binding')
            if original is None or retained_binding is None:
                raise ValueError('original pending principal and learning binding required')
            if evidence_hash(retained_binding['learning'])!=evidence_hash(plan['learning_kwargs']):
                raise ValueError('retained request plan and learning binding differ')
            learning=dict(retained_binding['learning'],sessions=binding['sessions'],
                learning_cutoff_ns=learning_cutoff_ns)
            continuation=coordinator._pending_continuation(request_id,learning)
            saved=coordinator._load(request_id,'feedback_continuation')
            if saved is not None and saved!=continuation:
                raise ValueError('outcome continuation already has a different immutable identity')
            if evidence_hash(dict(_plain(learning),learning_cutoff_ns=None))!=evidence_hash(plan['learning_kwargs']):
                raise ValueError('outcome follow-up changed original request inputs or session roster')
            outcome=PendingTargetFeedbackAdapter(adapter,original_envelope=original,
                sessions=binding['sessions'],expected_sessions_hash=binding['expected_sessions_hash'])
            if prepare:
                try:
                    envelope=outcome.recover_pending_feedback(request_id,continuation)
                except PrincipalPending:
                    envelope=None
                request_path,_=outcome._paths(continuation)
                return dict(status=('outcome_request_prepared' if envelope is None else 'outcome_response_already_recorded'),
                    request_id=request_id,continuation_hash=evidence_hash(continuation),
                    request_path=str(request_path),native_learning_performed=False)
            envelope=outcome.record_pending_feedback_response(response,host_attestation=attestation,
                request_id=request_id,continuation=continuation)
            return dict(status='actual_outcome_response_recorded',request_id=request_id,
                continuation_hash=evidence_hash(continuation),
                principal_receipt_sha256=envelope['principal_receipt']['receipt_sha256'],
                native_learning_performed=False)
        finally:
            coordinator.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('configuration','configuration-sha256'):
        parser.add_argument('--'+name,required=True)
    for name in ('response','response-sha256','host-attestation','host-attestation-sha256'):
        parser.add_argument('--'+name)
    parser.add_argument('--cycle-index',type=int,required=True)
    parser.add_argument('--turn',choices=('initial','correction','outcome','knowledge_correction'),default='initial')
    parser.add_argument('--knowledge-correction-sha256')
    parser.add_argument('--learning-cutoff-ns',type=int)
    parser.add_argument('--prepare-outcome',action='store_true')
    args=parser.parse_args()
    if (args.turn=='knowledge_correction') != bool(args.knowledge_correction_sha256):
        parser.error('knowledge_correction turn requires its exact request SHA256 only')
    response_args=(args.response,args.response_sha256,args.host_attestation,args.host_attestation_sha256)
    if args.prepare_outcome and args.turn!='outcome':
        parser.error('--prepare-outcome requires --turn outcome')
    if args.turn=='outcome' and args.learning_cutoff_ns is None:
        parser.error('--turn outcome requires --learning-cutoff-ns')
    if args.turn!='outcome' and args.learning_cutoff_ns is not None:
        parser.error('--learning-cutoff-ns is only valid for --turn outcome')
    if args.prepare_outcome and any(value is not None for value in response_args):
        parser.error('--prepare-outcome creates intent only; omit response and attestation arguments')
    if not args.prepare_outcome and not all(response_args):
        parser.error('recording requires response and host-attestation files and their independent SHA256 hashes')
    config=verified_json(args.configuration,args.configuration_sha256);h=config['host_runtime']
    sys.path.insert(0,h['repository'])
    from research.kalshi.frankie_boss.sunday_execution import _load
    from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle,make_principal_adapter
    from research.kalshi.frankie_boss.frankie_principal_adapter import canonical
    from research.kalshi.frankie_boss.feedback_cycle import _exclusive
    from research.kalshi.frankie_boss.dipole_classroom_integration import IntegratedDipoleClassroomPrincipalAdapter
    schedule=verified_json(h['schedule']['path'],h['schedule']['sha256'])
    steps=schedule['steps'] if type(schedule) is dict else schedule
    if not 0<=args.cycle_index<len(steps):raise ValueError('authored cycle index required')
    binding=bind_cycle(config['contract']['path'],config['contract']['sha256'],args.cycle_index,steps[args.cycle_index])
    run=Path(config['run_directory']);directory=run/'execution'/f'cycle-{args.cycle_index:02d}'
    with _exclusive(run/'actual-host.lock'):
        plan=_load(directory/'request-plan.c15.json');export=_load(directory/'principal-export.c15.json')
        principal=directory/'principal'
        # Recording cannot initiate source binding, receiver preparation or a session.
        if (not (principal/'session-request.json').exists() or
                args.turn!='knowledge_correction' and not (principal/'bound-mapping.json').exists()):
            raise ValueError('actual retained principal request and mapping required')
        request=json.loads((principal/'session-request.json').read_bytes())
        if request['request_id']!=plan['request_id']:raise ValueError('retained principal request differs from plan')
        if args.turn=='knowledge_correction':
            # This response is independent of pending outcomes/native training. Do
            # not rebuild the classroom or native adapter merely to record it.
            from research.kalshi.frankie_boss.frankie_principal_adapter import RetainedKnowledgeCorrectionAdapter
            correction_adapter=RetainedKnowledgeCorrectionAdapter(principal)
            response=verified_json(args.response,args.response_sha256)
            attestation=verified_json(args.host_attestation,args.host_attestation_sha256)
            correction_adapter.record_knowledge_correction_response(response,
                host_attestation=attestation,request_sha256=args.knowledge_correction_sha256)
            print(json.dumps(correction_adapter.recover_knowledge_correction(args.knowledge_correction_sha256)))
            return
        # Host-only package loading: withheld targets are never printed or placed
        # in the model-facing response. The actual host still grades both turns.
        classroom_package={
            name.replace('-','_'): _load(directory/('host-dipole-classroom-'+name+'.c15.json'))
            for name in ('source','teacher-key','pre-message','binding')}
        from research.kalshi.frankie_boss.dipole_classroom_final_review import final_model_visible_classroom
        from research.kalshi.frankie_boss.frankie_principal_adapter import json_form
        print('attachment dipole_classroom: '+live_classroom(request,classroom_package,final_model_visible_classroom,json_form))
        normalize=classroom_normalizer(classroom_package,final_model_visible_classroom,json_form)
        shared_knowledge=None
        if config.get('shared_knowledge') is not None:
            from research.kalshi.frankie_boss.dipole_shared_knowledge import load_snapshot, descriptor
            shared=config['shared_knowledge']
            shared_knowledge=descriptor(load_snapshot(shared['directory'],shared['snapshot_hash']))
        from research.kalshi.frankie_boss.source_contract_runtime import principal_inputs
        adapter=make_principal_adapter(binding=binding,handoff_directory=export['directory'],
            expected_manifest_sha256=export['manifest_sha256'],boss_journal_path=plan['source_journal_path'],
            source_journal_checkpoint=plan['source_journal_checkpoint'],
            **principal_inputs(config), python=sys.executable, directory=principal, session_executor=None,
            classroom_package=classroom_package,adapter_class=IntegratedDipoleClassroomPrincipalAdapter,
            shared_knowledge=shared_knowledge)
        if args.prepare_outcome:
            print(json.dumps(record_outcome(adapter,config,run,plan,binding,
                learning_cutoff_ns=args.learning_cutoff_ns,prepare=True)))
            return
        response=verified_json(args.response,args.response_sha256)
        attestation=verified_json(args.host_attestation,args.host_attestation_sha256)
        if args.turn=='outcome':
            print(json.dumps(record_outcome(adapter,config,run,plan,binding,
                learning_cutoff_ns=args.learning_cutoff_ns,response=response,attestation=attestation)))
            return
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
