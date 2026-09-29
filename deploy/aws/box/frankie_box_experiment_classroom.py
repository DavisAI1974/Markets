"""The experiment's classroom arm for ONE day (Greg, 2026-09-29: "Build the arm now to run on tues and wed. We are running
an experiment. 2 less data days is a weaker result"; the arm runs on discovery days 1 and 2 of every five).

The launch is not called. The same calls the full run makes, in one process on the box, no model, no Pod, no Granite:
  1. the classroom package: dipole_classroom_integration.prepare_integrated_cycle on the teacher's attachment of the day
     (the teacher-only step, experiment-teacher-rows/<day>/teacher-attachment.pkl), no shared knowledge (the scientific
     dialogue is unwired); the day before's completion and grade carried in (history, prior_grade) so the second day
     applies the first day's findings the way the code allows (the mode and the prior correction ids);
  2. the model-visible classroom (dipole_classroom_final_review.final_model_visible_classroom) answered by FRANKIE'S CODE
     (frankie_box_classroom_code, under knowledge/CLASSROOM_RULES_V1.json): the 19 component answers and the summary,
     assembled and validated by frankie_box_classroom exactly as the full run's session does;
  3. the host's deterministic grade and correction (the calls of final_review._recover_with_classroom): grade, the
     relationship-view cross-check, the novel findings investigated, the correction request, Frankie's code's correction
     answer, the acknowledgement, the completion and the transcript;
  4. Frankie's brain entry (frankie_box_brain.write_entry, day-keyed <day>-cycle-00): the day's calculation findings (the
     derivation digest, so the day's ROOT must have run with DIGEST=on) and his classroom teach-back.
No principal request exists in the experiment: the request identity is the digest of the model-visible request and the
session is named experiment-<day>-classroom (listed in the receipt as stand-ins). GUIDED, SOCRATIC and VERIFY modes are
refused by Frankie's code (it answers TEACH only): such a day is refused with the reason, listed, and the run goes on.
Files: <calculations>/work/classroom/ (R09: the day-data export keeps work/classroom/** from the teachers), and Jev's
material <calculations>/jev-material/classroom-request.json (the model-visible classroom, written before the answers).
"""
import argparse
import hashlib
import importlib.util
import json
import pickle
import sys
import time
from pathlib import Path

BOX = Path(__file__).resolve().parent
ROOT = BOX.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BOX))
SCHEMA = 'FRANKIE_EXPERIMENT_CLASSROOM_RECEIPT_V1'
MODEL_IDENTITY = "Frankie's code (computed; no model)"


def _box(name):
    spec = importlib.util.spec_from_file_location(name, BOX / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(day, calculations, teacher_rows, previous, brain):
    from research.kalshi.frankie_boss import dipole_classroom_integration as I, dipole_classroom_final_review as F
    from research.kalshi.frankie_boss import dipole_classroom_session as S, dipole_classroom_resolution as R
    from research.kalshi.frankie_boss import sunday_execution as SE
    from research.kalshi.frankie_boss.frankie_principal_adapter import digest, json_form
    C, K, BR = _box('frankie_box_classroom'), _box('frankie_box_classroom_code'), _box('frankie_box_brain')

    calculations, teacher_rows = Path(calculations), Path(teacher_rows)
    work, out = calculations / 'work', calculations / 'out'
    receipt = json.loads((calculations / 'calculations-receipt.json').read_bytes())
    if receipt.get('day') != day:
        raise SystemExit('the calculations are for day %s, not %s' % (receipt.get('day'), day))
    if not (work / 'derivation-digest-full.md').is_file():
        raise SystemExit('the day\'s ROOT ran without the digest; the classroom day needs DIGEST=on (the brain entry takes it)')
    d = work / 'classroom'
    if (d / 'completion.json').exists():
        raise SystemExit('%s already holds this day\'s classroom (duplicate data declines)' % d)
    d.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    entry = Path(brain) / BR.entry_name(day, '00')
    if entry.exists():
        raise SystemExit('the brain already holds %s (duplicate data declines, R16)' % entry)

    p = pickle.loads((teacher_rows / 'teacher-attachment.pkl').read_bytes())
    history, prior_grade, carried = [], None, None
    if previous:
        prev = Path(previous)
        history = json.loads((prev / 'history.json').read_bytes())
        prior_grade = json.loads((prev / 'post-grade.json').read_bytes())
        carried = dict(directory=str(prev), history_entries=len(history), history_sha256=_sha256(prev / 'history.json'),
                       grade_sha256=_sha256(prev / 'post-grade.json'))
    started = time.time()
    pkg = I.prepare_integrated_cycle(p['attachment'], request_id=p['request_id'], cycle_index=0, cycle_count=1,
                                     source_hash=p['source_hash'], as_of=p['as_of'], through_cursor=p['through_cursor'],
                                     history=history, prior_grade=prior_grade)
    for part in ('source', 'teacher_key', 'pre_message', 'binding'):
        SE._save(d / f'package.{part}.c15.json', pkg[part])
    mode = pkg['binding']['mode']
    visible = F.final_model_visible_classroom(pkg)
    request = {'attachment': {'dipole_classroom': visible}}
    # Jev's material (the blind outside student; SPEC "Jev"): the SAME model-visible classroom Frankie answers, written
    # BEFORE Frankie's code answers and OUTSIDE work/classroom/ (frankie_box_jev_relay.sh ACTION=material refuses anything
    # under a classroom or out directory: the blind wall); his claims are filed before he reads Frankie's outputs
    jev_dir = calculations / 'jev-material'
    jev_dir.mkdir(exist_ok=True)
    jev_path = jev_dir / 'classroom-request.json'
    jev_raw = json.dumps(request, indent=1, sort_keys=True, default=str).encode('utf-8')
    if jev_path.exists() and jev_path.read_bytes() != jev_raw:
        raise SystemExit('%s exists with other bytes; refused' % jev_path)
    if not jev_path.exists():
        jev_path.write_bytes(jev_raw)
    rules, rules_witness = K.rules()
    names = [c['name'] for c in C.components(visible)]
    try:
        outputs = {n: K.component_answer(visible, C.component(visible, n), [q['right'] for q in C.pairs_of(visible, n)])
                   for n in names}
        summary = K.summary_answer(visible, outputs)
    except K.ModeNotAnswerable as error:
        refusal = dict(schema=SCHEMA, day=day, status='refused', mode=mode, reason=str(error),
                       listed='Frankie\'s code answers TEACH only; this classroom day is refused with the reason, the run goes on')
        (d / 'receipt.json').write_text(json.dumps(refusal, indent=1, sort_keys=True))
        print(json.dumps(refusal), flush=True)
        return 3
    built = C.assemble(visible, outputs, summary)
    report = C.validate(visible, built['ledgers'])
    (d / 'code-answers.json').write_text(json.dumps(dict(schema=K.SCHEMA, rules=rules_witness, outputs=outputs, summary=summary,
                                                         model_calls=0), indent=1, sort_keys=True, default=str))
    (d / 'ledgers.json').write_text(json.dumps(built['ledgers'], indent=1, sort_keys=True, default=str))
    (d / 'classroom.md').write_text(C.render_markdown(built['ledgers'], built['dropped_findings']))

    request_sha256 = digest(request)
    session_id = 'experiment-%s-classroom' % day
    response = dict(built['ledgers'], request_sha256=request_sha256, session_id=session_id,
                    model_identity_as_reported_by_session=MODEL_IDENTITY)
    teachback, grade = S.grade_initial_response(pkg, response)
    grade = F.apply_relationship_view_crosscheck(grade, response)
    novel = F.validate_novel_findings(response.get('dipole_novel_findings'), pkg['pre_message'])
    novelty = F.investigate_novel_findings(pkg['teacher_key'], novel, mode=mode, learning_policy=pkg['binding'].get('learning_policy'))
    correction = F.bind_final_resolution_requirement(F.build_final_correction_request(
        original_request_sha256=request_sha256, response=response, grade=grade, key=pkg['teacher_key'], teachback=teachback,
        novelty_investigation=novelty))
    parsed = C.parse_correction(json.dumps(K.correction_answer(correction)), correction)
    reply = C.correction_response(correction, parsed, session_id=session_id, model_identity=MODEL_IDENTITY)
    base = S.validate_correction_response(correction=correction, response=reply, initial_response=response, grade=grade)
    ack = R.validate_correction_resolutions(reply.get('dipole_acknowledgement'), grade, base)
    completion = S.finish(pkg, teachback=teachback, grade=grade, acknowledgement=ack)
    transcript = F.render_final_transcript(pkg['pre_message'], teachback, novel, correction, ack,
                                           reply.get('dipole_scientific_exchange'))
    files = dict(teachback=teachback, **{'post-grade': grade}, **{'novel-findings': list(novel)},
                 **{'novelty-investigation': novelty}, **{'correction-request': correction},
                 **{'correction-response': reply}, acknowledgement=ack, completion=completion)
    for name, body in files.items():
        (d / f'{name}.json').write_text(json.dumps(json_form(body), indent=1, sort_keys=True))
    (d / 'transcript.md').write_text(transcript)
    (d / 'history.json').write_text(json.dumps(json_form(list(history) + [completion]), indent=1, sort_keys=True))

    manifest = BR.write_entry(work, out, brain, '00', day=day)
    result = dict(schema=SCHEMA, day=day, status='complete', mode=mode, components=report['components'],
                  observations=report['observations'], pairs=report['pairs'], novel_findings=len(novel),
                  dropped_findings=len(built['dropped_findings']), correction_ids=len(correction.get('correction_ids') or ()),
                  teacher_complete=completion.get('teacher_complete'), completion_hash=completion.get('completion_hash'),
                  carried_from_previous=carried, classroom_rules=rules_witness, teacher_rows=str(teacher_rows),
                  jev_material=dict(path=str(jev_path), sha256=hashlib.sha256(jev_raw).hexdigest(), bytes=len(jev_raw)),
                  stand_ins=dict(request_sha256=request_sha256, session_id=session_id, model_identity=MODEL_IDENTITY,
                                 why='the experiment has no principal request; the request identity is the digest of the '
                                     'model-visible request'),
                  brain_entry=str(Path(brain) / BR.entry_name(day, '00')), brain_manifest=manifest,
                  seconds=round(time.time() - started, 1), model_calls=0)
    (d / 'receipt.json').write_text(json.dumps(result, indent=1, sort_keys=True, default=str))
    print(json.dumps(dict((k, v) for k, v in result.items() if k != 'brain_manifest'), sort_keys=True, default=str), flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--day', required=True)
    ap.add_argument('--calculations', required=True, help='the day\'s experiment ROOT (DIGEST=on)')
    ap.add_argument('--teacher-rows', required=True, help='experiment-teacher-rows/<day>/ (teacher-attachment.pkl)')
    ap.add_argument('--previous', help='the previous classroom day\'s work/classroom/ (its history and grade carried in)')
    ap.add_argument('--brain', default='/opt/frankie-box/brain')
    a = ap.parse_args()
    return run(a.day, a.calculations, a.teacher_rows, a.previous, a.brain)


if __name__ == '__main__':
    sys.exit(main())
