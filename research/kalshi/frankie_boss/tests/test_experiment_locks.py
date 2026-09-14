from dataclasses import replace
import pytest
from experiment_locks import ArmLock, Pairing, ExperimentPlan, freeze_outputs, FACTORS

H = 'a' * 64
J = 'b' * 64


def arm(name, **changes):
    return ArmLock(name, **{field: changes.get(field, H) for field in FACTORS})


def plan(**changes):
    args = dict(arms=(arm('B0'), arm('B1', model_hash=J)),
                pairs=(Pairing('B0', 'B1', ('model_hash',)),),
                source_hash=H, partition_hash=H, schedule_hash=H,
                scorer_hash=H, exclusions_hash=H)
    return ExperimentPlan(**dict(args, **changes))


def test_plan_and_output_lock_are_order_independent():
    p = plan()
    other = plan(arms=tuple(reversed(p.arms)))
    assert p.digest == other.digest
    first = freeze_outputs(p, {'B0': b'null', 'B1': b'negative'})
    assert first == freeze_outputs(other, {'B1': b'negative', 'B0': b'null'})
    assert first.digest != freeze_outputs(p, {'B0': b'null', 'B1': b'changed'}).digest


@pytest.mark.parametrize('field', [f for f in FACTORS if f != 'model_hash'])
def test_undeclared_factor_differences_reject(field):
    with pytest.raises(ValueError, match='undeclared'):
        plan(arms=(arm('B0'), arm('B1', model_hash=J, **{field: J})))


def test_declared_memory_comparison_is_valid():
    p = plan(arms=(arm('clean'), arm('memory', memory_hash=J)),
             pairs=(Pairing('clean', 'memory', ('memory_hash',)),))
    assert p.digest


@pytest.mark.parametrize('arms', [(arm('B0'),), (arm('B0'), arm('B0')),
                                (arm('B0'), arm('B1'), arm('unpaired'))])
def test_incomplete_duplicate_and_unpaired_rosters_reject(arms):
    with pytest.raises(ValueError):
        plan(arms=arms)


@pytest.mark.parametrize('outputs', [{}, {'B0': b'a'}, {'B0': b'a', 'B1': b'b', 'extra': b'c'},
                                   {'B0': b'a', 'B1': 'text'}])
def test_output_roster_and_exact_bytes_required(outputs):
    with pytest.raises(ValueError):
        freeze_outputs(plan(), outputs)


def test_output_lock_owns_values():
    outputs = {'B0': b'a', 'B1': b'b'}
    lock = freeze_outputs(plan(), outputs)
    outputs['B1'] = b'changed'
    assert lock == freeze_outputs(plan(), {'B0': b'a', 'B1': b'b'})


@pytest.mark.parametrize('field', ['source_hash', 'partition_hash', 'schedule_hash',
                                 'scorer_hash', 'exclusions_hash'])
def test_shared_protocol_fields_are_bound(field):
    assert replace(plan(), **{field: J}).digest != plan().digest
    with pytest.raises(ValueError):
        replace(plan(), **{field: None})


def test_invalid_pairings_reject():
    for pair in [('B0', 'B0', ()), ('B0', 'B1', ('source_hash',)),
                 ('B0', 'B1', ('model_hash', 'model_hash'))]:
        with pytest.raises(ValueError):
            Pairing(*pair)
    with pytest.raises(ValueError):
        plan(pairs=(Pairing('B0', 'missing', ()),))
    with pytest.raises(ValueError):
        plan(pairs=(Pairing('B0', 'B1', ('model_hash',)),) * 2)
