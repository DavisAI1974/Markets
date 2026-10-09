"""Profile the external section of one sealed block (instrumentation only; Greg 2026-10-09: the science is never
weakened for speed, so first find where the time goes).

Runs ONLY the external section of block N exactly as the block session runs it (frankie_box_classroom_code
_BlockExternal: the section build, the pre-message and binding, Frankie's external answers, the grade and the correction
round, the markdown render), each phase under its own cProfile, from the inputs that already stand in a block directory
(a gauge directory or the real classroom's): the key, pre-message and binding (package.*.json), the learner context
(code-answers.json: the stage-knowledge and school checks; second_set.json), the block's snapshot (rebuilt from the
teacher's sealed block, the same way the session builds it) and the day file. Writes nothing into the block directory:
the section is built in a fresh --out directory. Prints, per phase, its wall seconds and the top functions by cumulative
and by own time (file:line(function)), then the counts that size the work (rows, series, points, pairs, prior checks,
knowledge documents, day file rows and bytes, answer and grade sizes). A JSON summary goes to <out>/profile.json.

  python3 frankie_box_block_profile.py --block-dir /opt/frankie-box/work/gauge-block1/<commit>-<stamp>/blocks/1 \\
      --day-file /opt/frankie-box/work/ingest-20231018-gh-36571235912-1/day-external.json
"""
import argparse
import cProfile
import io
import json
import pstats
import sys
import time
from pathlib import Path

BOX = Path(__file__).resolve().parent
ROOT = BOX.parents[2]
for path in (str(ROOT), str(BOX)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _bytes(value):
    return len(json.dumps(value, sort_keys=True, default=str))


def _profiled(name, function, top, report):
    profile = cProfile.Profile()
    began = time.monotonic()
    profile.enable()
    try:
        value = function()
    finally:
        profile.disable()
    seconds = round(time.monotonic() - began, 3)
    out = ['', '=' * 120, 'PHASE %s: %.3f s wall' % (name, seconds), '=' * 120]
    for order in ('cumulative', 'tottime'):
        text = io.StringIO()
        pstats.Stats(profile, stream=text).sort_stats(order).print_stats(top)
        out += ['--- top %d by %s ---' % (top, order), text.getvalue()]
    print('\n'.join(out), flush=True)
    report['phases'][name] = seconds
    return value


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--block-dir', required=True, help='a block directory holding package.*.json, code-answers.json, '
                                                      'second_set.json (and session.json)')
    p.add_argument('--day-file', required=True)
    p.add_argument('--day-sha256', help='default: the sha256 of the day file\'s receipt beside it (attached_day_file)')
    p.add_argument('--teacher-rows', default='/opt/frankie-box/work/experiment-teacher-rows/20231018')
    p.add_argument('--block', type=int, default=None, help='default: the block directory\'s name')
    p.add_argument('--day', default=None, help='default: session.json day, else the teacher rows directory name')
    p.add_argument('--brain', default=None, help='default: frankie_box_experiment.BRAIN')
    p.add_argument('--previous', default=None, help='default: session.json previous')
    p.add_argument('--out', default=None, help='a fresh directory for the section build (default <block dir>/../../'
                                               'profile-<block>-<stamp>)')
    p.add_argument('--top', type=int, default=40)
    a = p.parse_args(argv)
    import frankie_box_classroom as C
    import frankie_box_classroom_code as K
    import frankie_box_lane_state as LS
    import frankie_box_experiment as X
    from research.kalshi.frankie_boss import dipole_classroom_final_review as F
    from research.kalshi.frankie_boss import dipole_classroom_external as EXT
    from research.kalshi.frankie_boss.frankie_principal_adapter import digest
    import frankie_box_classroom_external_code as KX
    block_dir = Path(a.block_dir)
    session = json.loads((block_dir / 'session.json').read_bytes()) if (block_dir / 'session.json').is_file() else {}
    n = a.block or int(block_dir.name)
    day = a.day or session.get('day') or Path(a.teacher_rows).name
    brain = a.brain or str(X.BRAIN)
    previous = a.previous if a.previous is not None else session.get('previous')
    day_file = Path(a.day_file)
    sha = a.day_sha256
    if sha is None:
        found, sha, why = X.attached_day_file(day_file.parent)
        if sha is None:
            raise SystemExit('no sha256 for %s: %s (give --day-sha256)' % (day_file, why))
    out = Path(a.out) if a.out else block_dir.parent.parent / ('profile-%d-%s' % (n, time.strftime('%Y%m%dT%H%M%SZ',
                                                                                                    time.gmtime())))
    out.mkdir(parents=True, exist_ok=False)
    report = dict(block_dir=str(block_dir), day=day, block=n, day_file=str(day_file), day_sha256=sha, out=str(out),
                  phases={}, inputs={})
    clock = time.monotonic()
    snapshot, block = K.block_snapshot(a.teacher_rows, n, day=day)
    pkg = dict(source=snapshot, **{part: K.block_load(block_dir / ('package.%s.json' % part))
                                   for part in ('teacher_key', 'pre_message', 'binding')})
    mode = pkg['binding']['mode']
    visible = F.final_model_visible_classroom(pkg)
    code = K.block_load(block_dir / 'code-answers.json')
    lesson = K.block_load(block_dir / 'second_set.json')
    learner_context = dict(stage_knowledge=code['stage_knowledge'], school=code['school'],
                           second_set=K.second_set_context(lesson),
                           teacher_account=dict(checks=[], listed=[dict(teacher_account='day_end',
                                                                        reason=K.BLOCK_DAY_END[3]['why'])]))
    selected = LS.learner_knowledge(day, 'classroom', brain=brain, classroom_mode=mode)
    school, _ = LS.learner_school(day, brain=brain, versions=selected['versions'])
    knowledge = selected['documents']
    prior_external_grade = None
    if previous and (Path(previous) / 'external-post-grade.json').is_file():
        prior_external_grade = json.loads((Path(previous) / 'external-post-grade.json').read_bytes())
    session_id = 'experiment-%s-block-%02d' % (day, n)
    model = "Frankie's code (computed; no model)"
    report['inputs'] = dict(
        seconds=round(time.monotonic() - clock, 3), mode=mode, rows=len(snapshot['rows']),
        snapshot_matches_binding=snapshot['source_snapshot_hash'] == pkg['binding'].get('source_snapshot_hash'),
        knowledge_documents=len(knowledge), knowledge_bytes=_bytes([d.get('content') for d in knowledge]),
        school_documents=len(school), previous=previous, prior_external_grade=prior_external_grade is not None)
    raw = day_file.read_bytes()
    body = json.loads(raw)
    tables = {name: len(t.get('rows') or ()) for name, t in (body.get('points') or {}).items()}
    report['day_file'] = dict(bytes=len(raw), tables=len(tables), rows=sum(tables.values()), rows_per_table=tables,
                              inputs=len(body.get('inputs') or ()), missing=len(body.get('missing') or ()))
    del raw, body
    print('INPUTS %s' % json.dumps(dict(report['inputs'], day_file={k: v for k, v in report['day_file'].items()
                                                                       if k != 'rows_per_table'}), sort_keys=True),
          flush=True)

    key, section = _profiled('external.section', lambda: EXT.ensure_external_section(
        out, snapshot, day_file, sha, trading_day=day, built_by='profile block %d' % n), a.top, report)
    def pre_binding():
        pre = EXT.build_external_pre_message(key, mode=mode, prior_grade=prior_external_grade)
        binding = EXT.build_external_binding(key, pre, v1_binding=pkg['binding'])
        return pre, binding, EXT.model_visible_external(binding, pre)
    pre, binding, ext_visible = _profiled('external.pre_binding', pre_binding, a.top, report)
    ledgers = _profiled('external.answers', lambda: KX.answers(
        ext_visible, dipole_visible=visible, learner_context=learner_context, independent_evidence=None,
        knowledge=knowledge, school=school), a.top, report)

    def grade_correction():
        grade = EXT.grade_external(key, ledgers)
        request_v2 = {'attachment': {'dipole_classroom': visible, 'dipole_external': ext_visible}}
        correction = EXT.correction_request(original_request_sha256=digest(request_v2), session_id=session_id,
                                            model_identity=model, grade=grade)
        parsed = C.parse_correction(json.dumps(K.correction_answer(correction)), correction)
        reply = C.correction_response(correction, parsed, session_id=session_id, model_identity=model)
        ack, completion = EXT.finish_external(binding=binding, key=key, pre=pre, ledgers=ledgers, grade=grade,
                                              correction=correction, reply=reply, initial_session_id=session_id,
                                              model_identity=model)
        return grade, correction, reply, ack, completion
    grade, correction, reply, ack, completion = _profiled('external.grade_correction', grade_correction, a.top, report)
    _profiled('external.render_md', lambda: EXT.render_markdown(ledgers, grade), a.top, report)

    # the counts that size the work (outside the profiles)
    review = ((ext_visible.get('pre_message') or {}).get('relationship_review') or pre.get('relationship_review')
              or key.get('relationship_scan') or [])
    checks = K.stage_knowledge_reproduction(None, knowledge, evidence=dict(components=[], relationship_review=review),
                                            relationship_kind='EXTERNAL_RELATIONSHIP')['checks']
    tb = ledgers['external_teachback']
    scan = ledgers['external_relationship_scan']
    report['counts'] = dict(
        rows=key.get('rows'), series=key.get('series_count'), points=key.get('point_count'),
        pairs=key.get('relationship_pairs_scanned'), series_absent=len(key.get('series_absent') or ()),
        prior_checks=len(checks), prior_checks_with_pair=sum(1 for c in checks if c.get('pair')),
        prior_checks_bytes=_bytes(checks),
        key_bytes=_bytes(key), pre_message_bytes=_bytes(pre), visible_external_bytes=_bytes(ext_visible),
        ledgers_bytes={name: _bytes(value) for name, value in ledgers.items()},
        correlation_review_chars=len(tb.get('correlation_review') or ''),
        scan_interpretation_chars=sum(len(s.get('correlation_interpretation') or '') for s in scan),
        grade_bytes=_bytes(grade), correction_bytes=_bytes(correction), reply_bytes=_bytes(reply),
        mastered=grade.get('mastered'), section_reused=section.get('reused'))
    report['total_seconds'] = round(sum(report['phases'].values()), 3)
    print('\nCOUNTS %s' % json.dumps(report['counts'], sort_keys=True), flush=True)
    print('PHASES %s (total %.3f s)' % (json.dumps(report['phases'], sort_keys=True), report['total_seconds']), flush=True)
    (out / 'profile.json').write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + '\n')
    print('profile summary: %s' % (out / 'profile.json'), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
