"""The experiment's classroom arm V2 for ONE day: the classroom arm (frankie_box_experiment_classroom.py, unchanged) plus
Frankie's historical data points (Greg, 2026-09-29: "we should be able to unlock classroom and teachers for today. We're
the ones who made the locks"). Swap, not edit: every pinned file keeps its bytes; the V1 script stays as it was.

The same calls as the V1 arm, in the same order and with the same arguments, for the 19 components and 171 pairs: the
package (prepare_integrated_cycle, through dipole_classroom_v2.prepare_cycle_v2), Frankie's code answers
(frankie_box_classroom_code), the assembly and validation (frankie_box_classroom), the host's grade, the relationship-view
cross-check, the novel findings, the correction and its answer, the acknowledgement, the completion and the transcript.
The V1 request identity stays the digest of the V1 model-visible request, so the V1 grade, correction, acknowledgement
and completion are exactly what the V1 arm computes.

Added beside them (dipole_classroom_external.py): the BOSS teacher's external section (built once per day in the teacher
rows directory, by the teacher-only step or here), its model-visible part, Frankie's code answers for it
(frankie_box_classroom_external_code), the host's exact grade, the correction turn (Frankie's code's correction answer,
the classroom's acknowledgement and resolution validators), the external completion. The day file (FRANKIE_DAY_EXTERNAL_V1)
is given as --day-external + --day-external-sha256 (a mismatch is refused) or taken from beside the sealed ingest named in
the teacher rows receipt (its day-external-receipt.json sha256 must match the bytes).

Jev's material is the V2 model-visible classroom ({'dipole_classroom', 'dipole_external'}), written BEFORE any answer to
<calculations>/jev-material/classroom-request.json. Frankie's brain entry <day>-cycle-00 is written by frankie_box_brain
(unchanged), then carries his external teach-back (classroom-external.md, include true) and lists the day file as an
attachment (name, sha256, bytes, path, S3 key; not copied into his corpus, the same way the day-external step lists it).
Wednesday takes PREVIOUS = Tuesday's work/classroom: the V1 history and grade as the V1 arm does, and the external
history and grade the same way (only the correction ids travel, rule R10).

THE SCHOOL (Greg, 2026-09-29): before the answers are filed, the classroom reads Frankie's school knowledge base, every
EARLIER classroom day's <brain>/school/<day>.json checked against its index row (frankie_box_brain.school_rows; a missing
or changed file is listed, never read), and Frankie's code checks each hypothesis filed there on today's TEACH evidence
(frankie_box_classroom_code.school_reproduction: his earlier novel findings and the teachers' own findings, per earlier
day, counts only). The result travels in code-answers.json ("school") and the receipt ("school_knowledge"); it is not
part of the model-visible request, so Jev's material never carries it.
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
SCHEMA = 'FRANKIE_EXPERIMENT_CLASSROOM_RECEIPT_V2'
MODEL_IDENTITY = "Frankie's code (computed; no model)"


def _box(name):
    spec = importlib.util.spec_from_file_location(name, BOX / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(64 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _dump(path, body):
    Path(path).write_text(json.dumps(body, indent=1, sort_keys=True, default=str))


DIRECTIVE_PATH = ROOT / 'research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json'


def directive():
    """The experiment's directive (Greg, 2026-09-29: "make sure frankie and teachers and classroom has the directive of
    what we're shooting for with this experiment"), loaded whole, and its witness for the receipt."""
    data = DIRECTIVE_PATH.read_bytes()
    value = json.loads(data)
    if value.get('schema') != 'FRANKIE_EXPERIMENT_DIRECTIVE_V1' or not value.get('directive'):
        raise ValueError('%s is not the experiment directive' % DIRECTIVE_PATH)
    return value, dict(path=str(DIRECTIVE_PATH), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def _attach_to_brain_entry(entry_dir, classroom_external_md, day_file, day_sha, day_receipt, day):
    """His external teach-back into the entry (include true) and the day file listed as an attachment; MANIFEST rewritten."""
    manifest_path = Path(entry_dir) / 'MANIFEST.json'
    manifest = json.loads(manifest_path.read_bytes())
    data = Path(classroom_external_md).read_bytes()
    name = 'classroom-external.md'
    with (Path(entry_dir) / name).open('xb') as f:
        f.write(data)
    manifest['entries'].append(dict(name=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                    source=str(classroom_external_md), include=True,
                                    kind="the Dipole classroom's external section: Frankie's own teach-back of his historical "
                                         "data points beside the 19 dimensions for this cycle"))
    receipt = json.loads(Path(day_receipt).read_bytes()) if day_receipt and Path(day_receipt).is_file() else {}
    manifest.setdefault('attachments', []).append(dict(
        name='day-external.json', sha256=day_sha, bytes=Path(day_file).stat().st_size, path=str(day_file),
        s3_key=receipt.get('s3_key'), brain_attachment=f'{day}-external', schema='FRANKIE_DAY_EXTERNAL_V1', included=False,
        note='the day file of his historical data points, listed (not copied into his reading corpus); every reader of '
             'the ingest reads it through operations/frankie_day_external.AsOfReader at its own cutoff'))
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def run(day, calculations, teacher_rows, previous, brain, day_external, day_external_sha256):
    from research.kalshi.frankie_boss import dipole_classroom_final_review as F
    from research.kalshi.frankie_boss import dipole_classroom_session as S, dipole_classroom_resolution as R
    from research.kalshi.frankie_boss import dipole_classroom_external as EXT, dipole_classroom_v2 as V2
    from research.kalshi.frankie_boss import sunday_execution as SE
    from research.kalshi.frankie_boss.frankie_principal_adapter import digest, json_form
    C, K, BR = _box('frankie_box_classroom'), _box('frankie_box_classroom_code'), _box('frankie_box_brain')
    KX = _box('frankie_box_classroom_external_code')

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
    entry = Path(brain) / BR.entry_name(day, '00')
    if entry.exists():
        raise SystemExit('the brain already holds %s (duplicate data declines, R16)' % entry)

    # the day file: given (path + sha256) or beside the sealed ingest the teacher rows were walked from
    teacher_receipt = json.loads((teacher_rows / 'receipt.json').read_bytes())
    if teacher_receipt.get('day') != day:
        raise SystemExit('the teacher rows are for day %s, not %s' % (teacher_receipt.get('day'), day))
    attachment_sha = _sha256(teacher_rows / 'teacher-attachment.pkl')
    if attachment_sha != teacher_receipt['attachment_file']['sha256']:
        raise SystemExit('teacher-attachment.pkl differs from its teacher rows receipt; refused')
    try:
        day_file, day_sha, day_source = EXT.resolve_day_file(day_external, day_external_sha256,
                                                             teacher_receipt['ingestion_receipt']['path'])
    except EXT.DayExternalRefused as error:
        raise SystemExit('the day file of the historical data points: %s' % error)
    if _sha256(day_file) != day_sha:
        raise SystemExit('the day file %s differs from the sha256 %s (%s); refused' % (day_file, day_sha, day_source))
    day_receipt = Path(day_file).parent / 'day-external-receipt.json'

    d.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    p = pickle.loads((teacher_rows / 'teacher-attachment.pkl').read_bytes())
    history, prior_grade, carried = [], None, None
    external_history, prior_external_grade, external_carried = [], None, None
    if previous:
        prev = Path(previous)
        history = json.loads((prev / 'history.json').read_bytes())
        prior_grade = json.loads((prev / 'post-grade.json').read_bytes())
        carried = dict(directory=str(prev), history_entries=len(history), history_sha256=_sha256(prev / 'history.json'),
                       grade_sha256=_sha256(prev / 'post-grade.json'))
        if (prev / 'external-history.json').is_file() and (prev / 'external-post-grade.json').is_file():
            external_history = json.loads((prev / 'external-history.json').read_bytes())
            prior_external_grade = json.loads((prev / 'external-post-grade.json').read_bytes())
            external_carried = dict(directory=str(prev), history_entries=len(external_history),
                                    history_sha256=_sha256(prev / 'external-history.json'),
                                    grade_sha256=_sha256(prev / 'external-post-grade.json'))
        else:
            external_carried = dict(directory=str(prev), listed='the previous classroom day has no external section '
                                    '(it ran before V2); the external section starts without a prior correction')
    started = time.time()
    try:
        pkg2 = V2.prepare_cycle_v2(p['attachment'], request_id=p['request_id'], cycle_index=0, cycle_count=1,
                                   source_hash=p['source_hash'], as_of=p['as_of'], through_cursor=p['through_cursor'],
                                   history=history, prior_grade=prior_grade, section_directory=teacher_rows,
                                   day_file=day_file, day_file_sha256=day_sha, trading_day=day,
                                   prior_external_grade=prior_external_grade, built_by='classroom V2')
    except EXT.DayExternalRefused as error:
        raise SystemExit('the day file of the historical data points: %s' % error)
    pkg, ext = pkg2['v1'], pkg2['external']
    for part in ('source', 'teacher_key', 'pre_message', 'binding'):
        SE._save(d / f'package.{part}.c15.json', pkg[part])
    _dump(d / 'package.external.pre_message.json', ext['pre_message'])
    _dump(d / 'package.external.binding.json', ext['binding'])
    mode = pkg['binding']['mode']
    visible = F.final_model_visible_classroom(pkg)
    request = {'attachment': {'dipole_classroom': visible}}                     # the V1 request, unchanged
    ext_visible = EXT.model_visible_external(ext['binding'], ext['pre_message'])
    the_directive, directive_witness = directive()
    request_v2 = {'attachment': {'dipole_classroom': visible, 'dipole_external': ext_visible,
                                 'experiment_directive': the_directive}}
    # Jev's material: the SAME model-visible classroom Frankie answers (V2: the 19/171 and the external section), written
    # BEFORE any answer and OUTSIDE work/classroom/ (the blind wall of frankie_box_jev_relay.sh ACTION=material)
    jev_dir = calculations / 'jev-material'
    jev_dir.mkdir(exist_ok=True)
    jev_path = jev_dir / 'classroom-request.json'
    jev_raw = json.dumps(request_v2, indent=1, sort_keys=True, default=str).encode('utf-8')
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
        ext_ledgers = KX.answers(ext_visible)
    except (K.ModeNotAnswerable, KX.ModeNotAnswerable) as error:
        refusal = dict(schema=SCHEMA, day=day, status='refused', mode=mode, reason=str(error),
                       listed='Frankie\'s code answers TEACH only; this classroom day is refused with the reason, the run goes on')
        _dump(d / 'receipt.json', refusal)
        print(json.dumps(refusal), flush=True)
        return 3
    school, school_listed = BR.school_rows(brain, before_day=day)
    reproduction = K.school_reproduction(visible, school)
    school_witness = dict(read=reproduction['school_days_read'],
                          listed=[dict(day=(x.get('row') or {}).get('day'), reason=x['reason']) for x in school_listed],
                          counts_per_earlier_day=reproduction['counts_per_earlier_day'],
                          index=str(Path(brain) / BR.SCHOOL_DIR / 'index.json'))
    built = C.assemble(visible, outputs, summary)
    report = C.validate(visible, built['ledgers'])
    ext_report = EXT.validate_external_ledgers(ext_ledgers, ext['pre_message'])
    _dump(d / 'code-answers.json', dict(schema=K.SCHEMA, rules=rules_witness, outputs=outputs, summary=summary,
                                        school=reproduction, model_calls=0))
    _dump(d / 'ledgers.json', built['ledgers'])
    (d / 'classroom.md').write_text(C.render_markdown(built['ledgers'], built['dropped_findings']))
    _dump(d / 'external-code-answers.json', dict(schema=KX.SCHEMA, rules=rules_witness, ledgers=ext_ledgers, model_calls=0))

    # ---- the 19 components and 171 pairs: exactly the V1 arm's calls
    request_sha256 = digest(request)
    request_v2_sha256 = digest(request_v2)
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

    # ---- the external section: the host's exact grade and its correction turn
    ext_grade = EXT.grade_external(ext['teacher_key'], ext_ledgers)
    ext_correction = EXT.correction_request(original_request_sha256=request_v2_sha256, session_id=session_id,
                                            model_identity=MODEL_IDENTITY, grade=ext_grade)
    ext_parsed = C.parse_correction(json.dumps(K.correction_answer(ext_correction)), ext_correction)
    ext_reply = C.correction_response(ext_correction, ext_parsed, session_id=session_id, model_identity=MODEL_IDENTITY)
    ext_ack, ext_completion = EXT.finish_external(binding=ext['binding'], key=ext['teacher_key'], pre=ext['pre_message'],
                                                  ledgers=ext_ledgers, grade=ext_grade, correction=ext_correction,
                                                  reply=ext_reply, initial_session_id=session_id, model_identity=MODEL_IDENTITY)

    files = dict(teachback=teachback, **{'post-grade': grade}, **{'novel-findings': list(novel)},
                 **{'novelty-investigation': novelty}, **{'correction-request': correction},
                 **{'correction-response': reply}, acknowledgement=ack, completion=completion,
                 **{'external-post-grade': ext_grade}, **{'external-correction-request': ext_correction},
                 **{'external-correction-response': ext_reply}, **{'external-acknowledgement': ext_ack},
                 **{'external-completion': ext_completion})
    for name, body in files.items():
        (d / f'{name}.json').write_text(json.dumps(json_form(body), indent=1, sort_keys=True))
    (d / 'transcript.md').write_text(transcript)
    (d / 'classroom-external.md').write_text(EXT.render_markdown(ext_ledgers, ext_grade))
    (d / 'history.json').write_text(json.dumps(json_form(list(history) + [completion]), indent=1, sort_keys=True))
    (d / 'external-history.json').write_text(json.dumps(json_form(list(external_history) + [ext_completion]), indent=1,
                                                        sort_keys=True))

    manifest = BR.write_entry(work, out, brain, '00', day=day)
    manifest = _attach_to_brain_entry(entry, d / 'classroom-external.md', day_file, day_sha, day_receipt, day)
    directive_bytes = DIRECTIVE_PATH.read_bytes()
    with (Path(entry) / 'experiment-directive.json').open('xb') as f:
        f.write(directive_bytes)
    manifest['entries'].append(dict(name='experiment-directive.json', bytes=len(directive_bytes),
                                    sha256=hashlib.sha256(directive_bytes).hexdigest(), source=str(DIRECTIVE_PATH),
                                    include=True, kind="the experiment's directive (Greg): what we are shooting for"))
    (Path(entry) / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    key = ext['teacher_key']
    result = dict(schema=SCHEMA, day=day, status='complete', mode=mode, components=report['components'],
                  observations=report['observations'], pairs=report['pairs'], novel_findings=len(novel),
                  dropped_findings=len(built['dropped_findings']), correction_ids=len(correction.get('correction_ids') or ()),
                  teacher_complete=completion.get('teacher_complete'), completion_hash=completion.get('completion_hash'),
                  carried_from_previous=carried, school_knowledge=school_witness, classroom_rules=rules_witness,
                  teacher_rows=str(teacher_rows),
                  experiment_directive=directive_witness, v1_unchanged=pkg2['v1_unchanged'],
                  external=dict(day_file=dict(path=str(day_file), sha256=day_sha, found=day_source,
                                              receipt=str(day_receipt) if day_receipt.is_file() else None),
                                section=ext['section_receipt'], external_key_hash=key['external_key_hash'],
                                points=[dict(point_id=q['point_id'], name=q['name'], series=len(q['series']),
                                             missing=len(q['missing'])) for q in key['points']],
                                deferred=key['deferred'], series=key['series_count'], series_absent=key['series_absent'],
                                missing_not_assigned=key['missing_not_assigned'], rows=key['rows'], cutoff_ns=key['cutoff_ns'],
                                ledgers=ext_report, correction_ids=len(ext_grade['correction_ids']),
                                mastered=ext_grade['mastered'], teacher_complete=ext_completion['teacher_complete'],
                                completion_hash=ext_completion['completion_hash'], carried_from_previous=external_carried),
                  jev_material=dict(path=str(jev_path), sha256=hashlib.sha256(jev_raw).hexdigest(), bytes=len(jev_raw),
                                    carries=['dipole_classroom', 'dipole_external', 'experiment_directive']),
                  stand_ins=dict(request_sha256=request_sha256, request_v2_sha256=request_v2_sha256, session_id=session_id,
                                 model_identity=MODEL_IDENTITY,
                                 why='the experiment has no principal request; the V1 request identity is the digest of the '
                                     'V1 model-visible request (unchanged), the external correction names the digest of the '
                                     'V2 request'),
                  brain_entry=str(entry), brain_manifest=manifest, seconds=round(time.time() - started, 1), model_calls=0)
    _dump(d / 'receipt.json', result)
    print(json.dumps(dict((k, v) for k, v in result.items() if k != 'brain_manifest'), sort_keys=True, default=str), flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--day', required=True)
    ap.add_argument('--calculations', required=True, help='the day\'s experiment ROOT (DIGEST=on)')
    ap.add_argument('--teacher-rows', required=True, help='experiment-teacher-rows/<day>/ (teacher-attachment.pkl)')
    ap.add_argument('--previous', help='the previous classroom day\'s work/classroom/ (its histories and grades carried in)')
    ap.add_argument('--brain', default='/opt/frankie-box/brain')
    ap.add_argument('--day-external', help='the day file (FRANKIE_DAY_EXTERNAL_V1); default: beside the sealed ingest')
    ap.add_argument('--day-external-sha256', help='its sha256 (given together with --day-external; a mismatch is refused)')
    a = ap.parse_args()
    if (a.day_external is None) != (a.day_external_sha256 is None):
        ap.error('--day-external and --day-external-sha256 are given together')
    return run(a.day, a.calculations, a.teacher_rows, a.previous, a.brain, a.day_external, a.day_external_sha256)


if __name__ == '__main__':
    sys.exit(main())
