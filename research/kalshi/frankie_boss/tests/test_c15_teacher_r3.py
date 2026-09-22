"""Six approved teacher equations, exercised on synthetic public book evidence."""
import copy
import pytest
from test_c15_full_evidence import build, submit, row
from c15_teacher_r3 import RawJournalTeacherR3
from c15_normalizer import State


ALL_FIXTURE_ROWS = 1 << 20   # a declared window larger than any fixture: the row window has no default (Greg, 2026-09-22)

def attach(builder, evidence=None):
    evidence = list(builder.evidence_stream()) if evidence is None else evidence
    return RawJournalTeacherR3().attach(evidence, context_cursors=(evidence[-1]['cursor'],),
        as_of=evidence[-1]['normalized']['ts_recv_ns'],
        source_manifest_hash=builder.scope.genesis_hash(),
        expected_prefix_hash=evidence[-1]['terminal_prefix_hash'])


@pytest.mark.parametrize('horizon', [64, 1024])
def test_quiet_cohort_survives_both_horizons(tmp_path, horizon):
    builder = build(tmp_path)
    submit(builder, row(0, size=10))
    for i in range(1, horizon+1):
        submit(builder, row(i, action='T', side='B', oid=0, size=1))
    result = attach(builder)
    offset = int(horizon == 1024)
    values = result['rows'][0]['columns']
    assert values[offset] == dict(value=0., state=int(State.MISSING), mask=0, reason='NO_REMOVALS')
    assert values[2+offset]['value'] == values[4+offset]['value'] == 1.
    assert values[2+offset]['mask'] == values[4+offset]['mask'] == 1
    assert attach(builder) == result


def test_fill_fraction_and_partial_cancel_terminates_identity(tmp_path):
    builder = build(tmp_path)
    submit(builder, row(0, size=10))
    for i in range(1, 63): submit(builder, row(i, action='T', side='B', oid=0, size=1))
    submit(builder, row(63, action='F', size=2, flags=0))
    submit(builder, row(64, action='M', size=8))
    submit(builder, row(65, action='C', size=2))
    values = attach(builder)['rows'][0]['columns']
    assert values[0]['value'] == .5
    assert values[2]['value'] == values[4]['value'] == 0.
    assert values[2]['mask'] == 1


def test_prefix_gap_future_and_expected_identity_fail_closed(tmp_path):
    builder = build(tmp_path)
    submit(builder, row(0))
    evidence = list(builder.evidence_stream())
    with pytest.raises(ValueError, match='prefix'):
        RawJournalTeacherR3().attach(evidence, context_cursors=(0,), as_of=2,
            source_manifest_hash=builder.scope.genesis_hash(), expected_prefix_hash='0'*64)
    broken = copy.deepcopy(evidence)
    broken[0]['cursor'] = 1
    with pytest.raises(ValueError, match='cursor'):
        attach(builder, broken)
    with pytest.raises(ValueError, match='future'):
        RawJournalTeacherR3().attach(evidence, context_cursors=(0,), as_of=1,
            source_manifest_hash=builder.scope.genesis_hash(),
            expected_prefix_hash=evidence[-1]['terminal_prefix_hash'])


@pytest.mark.parametrize('ending,identity,retention', [
    ([dict(action='M', price=110, size=5)], 1., .5),
    ([dict(action='M', price=110, size=20)], 1., 1.),
    ([dict(action='C', size=10), dict(action='A', size=10)], 0., 0.),
])
def test_cohort_reprice_increase_and_id_reuse(tmp_path, ending, identity, retention):
    builder = build(tmp_path)
    submit(builder, row(0))
    for i in range(1, 64): submit(builder, row(i, action='T', side='B', oid=0, size=1))
    for i, kwargs in enumerate(ending, 64): submit(builder, row(i, **kwargs))
    columns = attach(builder)['rows'][0]['columns']
    assert columns[2]['value'] == identity
    assert columns[4]['value'] == retention
    assert columns[2]['mask'] == columns[4]['mask'] == 1


@pytest.mark.parametrize('ending,reason', [
    (dict(action='F', size=2), 'UNRECONCILED_FILL'),
    (dict(action='M', oid=999, size=2), 'LEVEL_INTEGRITY'),
    (dict(action='R', side='N', oid=0), 'MISSING_REFERENCE_OR_RESET'),
    (dict(action='T', side='N', oid=0), 'UNKNOWN_SIDE'),
])
def test_absorption_integrity_masks(tmp_path, ending, reason):
    builder = build(tmp_path)
    submit(builder, row(0))
    for i in range(1, 64): submit(builder, row(i, action='T', side='B', oid=0, size=1))
    submit(builder, row(64, **ending))
    result = attach(builder)['rows'][0]['columns'][0]
    assert result == dict(value=0., mask=0, state=int(State.INVALID), reason=reason)


def test_session_boundary_invalidates_cohort(tmp_path):
    builder = build(tmp_path)
    submit(builder, row(0))
    for i in range(1, 64): submit(builder, row(i, action='T', side='B', oid=0, size=1))
    submit(builder, row(64, action='T', side='B', oid=0, size=1), session='new')
    columns = attach(builder)['rows'][0]['columns']
    assert columns[2]['reason'] == columns[4]['reason'] == 'SCOPE_BOUNDARY'


def test_cutoff_integrity_cannot_produce_present_target(tmp_path):
    builder = build(tmp_path)
    submit(builder, row(0))
    for i in range(1, 64): submit(builder, row(i, action='T', side='B', oid=0, size=1))
    submit(builder, row(64, oid=2, side='B', price=102))
    columns = attach(builder)['rows'][0]['columns']
    assert all(c['state'] == int(State.INVALID) for c in columns)


def test_unresolvable_publisher_scope_is_rejected(tmp_path):
    builder = build(tmp_path)
    submit(builder, row(0))
    changed = row(1, action='T', side='B', oid=0)
    changed['publisher_id'] = 2
    submit(builder, changed)
    with pytest.raises(ValueError, match='publisher'):
        attach(builder)


def test_weighted_snapshot_cohort_and_nonterminal_masks(tmp_path):
    builder = build(tmp_path)
    submit(builder, row(0, oid=1, size=10, flags=32))
    submit(builder, row(1, oid=2, size=30, flags=128|32))
    for i in range(2, 65): submit(builder, row(i, action='T', side='B', oid=0, size=1))
    submit(builder, row(65, action='C', oid=1, size=10))
    columns = attach(builder)['rows'][0]['columns']
    assert columns[2]['value'] == columns[4]['value'] == .75
    assert columns[2]['mask'] == columns[4]['mask'] == 1
    submit(builder, row(66, action='N', side='N', oid=0, flags=0))
    assert all(c['reason'] == 'NOT_F_LAST' and c['mask'] == 0
               for c in attach(builder)['rows'][0]['columns'])


def test_empty_cohort_and_short_window_remain_missing(tmp_path):
    builder = build(tmp_path)
    submit(builder, row(0, action='T', side='B', oid=0, size=1))
    assert all(c['reason'] == 'WINDOW_SHORT' for c in attach(builder)['rows'][0]['columns'])
    for i in range(1, 65): submit(builder, row(i, action='T', side='B', oid=0, size=1))
    columns = attach(builder)['rows'][0]['columns']
    assert columns[2]['reason'] == columns[4]['reason'] == 'COHORT_EMPTY'
    assert columns[3]['reason'] == columns[5]['reason'] == 'WINDOW_SHORT'


def test_r3_normalizer_all_columns_exclusive_update_freeze_restore():
    from c15_normalizer_r3 import NormalizerR3
    from c15_normalizer import NormalizerConfig, COLUMNS, Normalizer
    config = NormalizerConfig((1,), n_warm=2, n_norm=4)
    norm = NormalizerR3(config)
    for column in COLUMNS:
        assert norm.observe(1, column, .25).reason == 'NORM_WARMUP'
        assert norm.observe(1, column, .25).reason == 'NORM_WARMUP'
        assert norm.observe(1, column, .25).value == 0.
    assert len(norm.export()['windows']) == 19
    restored = NormalizerR3.restore(config, norm.export(), norm.state_hash)
    assert restored.export() == norm.export()
    restored.freeze()
    before = restored.state_hash
    restored.observe(1, COLUMNS[7], .75)
    assert restored.state_hash == before
    assert NormalizerR3.restore(restored.config, restored.export(), before).state_hash == before
    with pytest.raises(ValueError): Normalizer.restore(config, norm.export(), norm.state_hash)
    corrupted = copy.deepcopy(norm.export())
    corrupted['windows'][7]['values'][0] = .75
    with pytest.raises(ValueError): NormalizerR3.restore(config, corrupted, norm.state_hash)


def test_governed_r3_attachment_preserves_control_and_retries(tmp_path):
    from c15_teacher_r3 import JournalTeacherR3
    from c15_normalizer_r3 import IdentityNormalizerR3
    from c15_teacher import JournalTeacher
    from c15_normalizer import IdentityNormalizer
    builder = build(tmp_path)
    submit(builder, row(0))
    for i in range(1, 65): submit(builder, row(i, action='T', side='B', oid=0, size=1))
    evidence = list(builder.evidence_stream())
    control = JournalTeacher({1: 1}, normalizer=IdentityNormalizer((1,)))
    teacher = JournalTeacherR3({1: 1}, normalizer=IdentityNormalizerR3((1,)))
    kwargs = dict(as_of=evidence[-1]['normalized']['ts_recv_ns'],
                  source_manifest_hash=builder.scope.genesis_hash())
    old = control.attach(evidence, evidence[-1:], **kwargs)
    first = teacher.attach(evidence, evidence[-1:], **kwargs)
    again = teacher.attach(evidence, evidence[-1:], **kwargs)
    assert first['attachment_hash'] == again['attachment_hash']
    assert teacher.binding != control.binding
    target = first['targets'][0]
    assert target.values.shape == (1, 1, 19)
    assert target.values[0, 0, 9].item() == 1.
    assert target.mask[0, 0, 9].item() == 1.
    assert old['targets'][0].states[0, 0, 9].item() == State.ABLATED
    for index in tuple(range(7))+tuple(range(13,19)):
        assert target.values[0,0,index] == old['targets'][0].values[0,0,index]


def test_governed_normalization_consumes_full_prefix_without_mutating_checkpoint(tmp_path):
    from c15_teacher_r3 import JournalTeacherR3
    from c15_normalizer_r3 import NormalizerR3
    from c15_normalizer import NormalizerConfig
    builder = build(tmp_path)
    submit(builder, row(0))
    for i in range(1, 66): submit(builder, row(i, action='T', side='B', oid=0, size=1))
    evidence = list(builder.evidence_stream())
    norm = NormalizerR3(NormalizerConfig((1,), n_warm=1))
    teacher = JournalTeacherR3({1:1}, normalizer=norm)
    before = norm.state_hash
    kwargs = dict(as_of=evidence[-1]['normalized']['ts_recv_ns'],
                  source_manifest_hash=builder.scope.genesis_hash())
    result = teacher.attach(evidence, evidence[-2:], **kwargs)
    assert result['targets'][0].states[0,0,9].item() == State.MISSING
    assert result['targets'][1].states[0,0,9].item() == State.PRESENT
    assert norm.state_hash == before
    assert teacher.attach(evidence, evidence[-2:], **kwargs)['attachment_hash'] == result['attachment_hash']
    norm.freeze()
    frozen = teacher.attach(evidence, evidence[-2:], **kwargs)
    assert all(t.states[0,0,9].item() == State.MISSING for t in frozen['targets'])
    changed = copy.deepcopy(evidence[-1:])
    changed[0]['order_after'] = {'tampered': True}
    with pytest.raises(ValueError, match='exact verified'):
        teacher.attach(evidence, changed, **kwargs)


def test_existing_session_explicit_r3_attachment_restores_exact_receipt(tmp_path):
    from context_session import ContextSessionRunner
    from test_context_session import model
    from c15_teacher_r3 import JournalTeacherR3
    from c15_normalizer_r3 import IdentityNormalizerR3
    builder = build(tmp_path)
    for i in range(3): submit(builder, row(i, oid=i+1))
    teacher = JournalTeacherR3({1:1}, normalizer=IdentityNormalizerR3((1,)))
    native = model()
    session = ContextSessionRunner(native,builder,entity=(1,1),t_ctx=2,teacher=teacher)
    result = session.run(as_of=202)
    assert result.receipt.teacher_hash == result.teacher['attachment_hash']
    assert result.receipt.teacher_binding == teacher.binding
    restored = ContextSessionRunner.restore(native,builder,session.export(),teacher=teacher,
        expected_input_hash=result.receipt.input_hash,expected_model_hash=result.receipt.model_hash)
    assert restored.run(as_of=202).receipt == result.receipt


@pytest.mark.parametrize('identity', [True, False])
def test_r3_normalizer_code_change_changes_existing_teacher_binding(monkeypatch, identity):
    from pathlib import Path
    from c15_teacher_r3 import JournalTeacherR3
    from c15_normalizer_r3 import IdentityNormalizerR3, NormalizerR3
    from c15_normalizer import NormalizerConfig
    norm = IdentityNormalizerR3((1,)) if identity else NormalizerR3(NormalizerConfig((1,)))
    teacher = JournalTeacherR3({1:1}, normalizer=norm)
    before = teacher.binding
    read = Path.read_bytes
    def changed(path):
        content = read(path)
        return content+b'\n# synthetic identity mutation\n' if path.name == 'c15_normalizer_r3.py' else content
    monkeypatch.setattr(Path, 'read_bytes', changed)
    assert teacher.binding != before
