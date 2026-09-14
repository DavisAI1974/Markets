"""Paired native controls and exact scoring over synthetic evidence only."""
import json
from dataclasses import replace
import hashlib

import pytest

from experiment_runner import PairedExperimentRunner, SharedInput, callable_hash
from experiment_locks import ExperimentPlan, ArmLock, Pairing, FACTORS


def digest(value):
    return hashlib.sha256(value).hexdigest()


def native_callback(request):
    import torch
    from native_mbo_encoder import NativeTrunk, NativeRegistry, encode
    torch.manual_seed(json.loads(dict(request.artifacts)['seed_hash']))
    config = json.loads(dict(request.artifacts)['model_hash'])
    model = NativeTrunk(NativeRegistry(), d_model=8, n_heads=2, n_layers=1).double().eval()
    tokens = encode(json.loads(request.common.source), as_of=2, registry=model.registry)
    with torch.no_grad():
        if config['recurrent']:
            from b1_reasoner import B1Reasoner, B1Config
            model = B1Reasoner(model, B1Config(k_max=1, k_fixed=1)).double().eval()
            output = model.forward_decision(tokens=tokens, numeric=tokens['numeric'], packet_hash=digest(request.common.source))
        else:
            output = model(tokens=tokens, numeric=tokens['numeric'])
    return json.dumps({'p_up': output['p_up'].tolist()}, sort_keys=True).encode()


def score_callback(request):
    value = json.loads(request.output)['p_up'][0]
    observed = json.loads(request.outcomes)['observed']
    return json.dumps({'absolute_error': abs(value-observed), 'arm': request.arm_id}, sort_keys=True).encode()


def fails_callback(request):
    raise RuntimeError('synthetic failure')


def case(callback=native_callback):
    raw = [dict(instrument_id=1, publisher_id=1, channel_id=1, order_id=1, action='A',
                side='A', price=100, size=2, flags=128, sequence=0, ts_event=1, ts_recv=2, ts_in_delta=1)]
    common = SharedInput(json.dumps(raw).encode(), b'synthetic-partition', b'["B0","B1"]', b'no-exclusions')
    artifacts = {}
    arms = []
    for name, recurrent in [('B0', False), ('B1', True)]:
        fields = {field: b'common' for field in FACTORS if field != 'controller_hash'}
        fields['model_hash'] = json.dumps({'recurrent': recurrent}).encode()
        fields['seed_hash'] = b'7'
        artifacts[name] = tuple(sorted(fields.items()))
        arms.append(ArmLock(name, **{field: digest(value) for field, value in fields.items()},
                            controller_hash=callable_hash(callback)))
    plan = ExperimentPlan(tuple(arms), (Pairing('B0', 'B1', ('model_hash',)),),
                          digest(common.source), digest(common.partition), digest(common.schedule),
                          callable_hash(score_callback), digest(common.exclusions))
    return plan, common, artifacts


def test_actual_native_pair_freezes_reveals_scores_and_restarts(tmp_path):
    plan, common, artifacts = case()
    path = tmp_path/'run.sqlite'
    runner = PairedExperimentRunner(path, plan, common=common, create=True)
    a = runner.run_arm('B0', native_callback, artifacts['B0'])
    b = runner.run_arm('B1', native_callback, artifacts['B1'])
    assert a != b
    frozen = runner.freeze()
    assert set(frozen) == {'B0', 'B1'}
    calls = []
    result = runner.reveal_and_score(lambda: calls.append(1) or b'{"observed":1}', score_callback, authorized=True)
    assert set(result) == {'B0', 'B1'}
    assert len(calls) == 1
    checkpoint = runner.checkpoint()
    runner.close()
    restored = PairedExperimentRunner(path, plan, common=common, checkpoint=checkpoint)
    assert restored.run_arm('B0', native_callback, artifacts['B0']) == a
    assert restored.reveal_and_score(lambda: pytest.fail('no rereveal'), score_callback, authorized=True) == result
    assert restored.checkpoint() == checkpoint
    restored.close()


def test_partial_roster_never_reveals(tmp_path):
    plan, common, artifacts = case()
    runner = PairedExperimentRunner(tmp_path/'run.sqlite', plan, common=common, create=True)
    runner.run_arm('B0', native_callback, artifacts['B0'])
    with pytest.raises(ValueError):
        runner.reveal_and_score(lambda: pytest.fail('no reveal'), score_callback, authorized=True)
    runner.close()


def test_failed_arm_intent_blocks_automatic_repeat_after_restart(tmp_path):
    plan, common, artifacts = case(fails_callback)
    path = tmp_path/'run.sqlite'
    runner = PairedExperimentRunner(path, plan, common=common, create=True)
    with pytest.raises(RuntimeError):
        runner.run_arm('B0', fails_callback, artifacts['B0'])
    checkpoint = runner.checkpoint()
    runner.close()
    runner = PairedExperimentRunner(path, plan, common=common, checkpoint=checkpoint)
    with pytest.raises(ValueError, match='uncertain'):
        runner.run_arm('B0', fails_callback, artifacts['B0'])
    runner.close()


def test_wrong_source_artifacts_or_callable_reject_before_callback(tmp_path):
    plan, common, artifacts = case()
    with pytest.raises(ValueError):
        PairedExperimentRunner(tmp_path/'bad.sqlite', plan, common=replace(common, source=b'changed'), create=True)
    runner = PairedExperimentRunner(tmp_path/'run.sqlite', plan, common=common, create=True)
    with pytest.raises(ValueError):
        runner.run_arm('B0', fails_callback, artifacts['B0'])
    with pytest.raises(ValueError):
        runner.run_arm('B0', native_callback, artifacts['B0'][:-1])
    with pytest.raises(ValueError):
        runner.run_arm('B1', native_callback, artifacts['B1'])
    assert runner.checkpoint()['count'] == 1
    runner.close()


def isolated_callback(request):
    assert not hasattr(request, 'outcomes') and not hasattr(request, 'outputs')
    assert tuple(name for name, _ in request.artifacts) == tuple(sorted(set(FACTORS)-{'controller_hash'}))
    return dict(request.artifacts)['model_hash']


def null_negative_scorer(request):
    assert request.outcomes == b'fixed synthetic outcome'
    return b'null' if request.arm_id == 'B0' else b'-1'


def failing_scorer(request):
    if request.arm_id == 'B1':
        raise RuntimeError('synthetic score failure')
    return b'first score'


def invalid_callback(request):
    return {'not': 'bytes'}


def prepared(tmp_path, scorer=null_negative_scorer):
    plan, common, artifacts = case(isolated_callback)
    plan = replace(plan, scorer_hash=callable_hash(scorer))
    runner = PairedExperimentRunner(tmp_path/'run.sqlite', plan, common=common, create=True)
    for arm in ('B0', 'B1'):
        runner.run_arm(arm, isolated_callback, artifacts[arm])
    return runner, plan, common, artifacts


def test_isolated_callbacks_preserve_null_negative_scores_and_owned_outputs(tmp_path):
    runner, _, _, _ = prepared(tmp_path)
    outputs = runner.freeze()
    outputs['B0'] = b'changed'
    assert runner.freeze()['B0'] != b'changed'
    scores = runner.reveal_and_score(lambda: b'fixed synthetic outcome', null_negative_scorer, authorized=True)
    assert scores == {'B0': b'null', 'B1': b'-1'}
    scores['B0'] = b'changed'
    assert runner.reveal_and_score(None, null_negative_scorer, authorized=True)['B0'] == b'null'
    runner.close()


def test_explicit_authorization_and_exact_scorer_required(tmp_path):
    runner, _, _, _ = prepared(tmp_path)
    before = runner.checkpoint()
    with pytest.raises(ValueError):
        runner.reveal_and_score(lambda: pytest.fail('not authorized'), null_negative_scorer)
    with pytest.raises(ValueError):
        runner.reveal_and_score(lambda: pytest.fail('wrong scorer'), score_callback, authorized=True)
    assert runner.checkpoint() == before
    runner.close()


def test_failed_reveal_requires_independent_newer_checkpoint_and_never_repeats(tmp_path):
    from c15_journal import EvidenceJournal
    runner, plan, common, _ = prepared(tmp_path)
    calls = []
    def fail():
        calls.append(1)
        raise RuntimeError('synthetic reveal failure')
    with pytest.raises(RuntimeError):
        runner.reveal_and_score(fail, null_negative_scorer, authorized=True)
    checkpoint = runner.checkpoint()
    runner.close()
    runner = PairedExperimentRunner(tmp_path/'run.sqlite', plan, common=common, checkpoint=checkpoint)
    with pytest.raises(ValueError):
        runner.reveal_and_score(fail, null_negative_scorer, authorized=True)
    witness = EvidenceJournal(runner.reveal_path)
    explicit_checkpoint = {'count': witness.count, 'head_hash': witness.head_hash}
    witness.close()
    with pytest.raises(ValueError, match='uncertain'):
        runner.reveal_and_score(fail, null_negative_scorer, authorized=True, reveal_checkpoint=explicit_checkpoint)
    assert calls == [1]
    runner.close()


def test_partial_scoring_is_retained_and_uncertain_scorer_not_repeated(tmp_path):
    runner, plan, common, _ = prepared(tmp_path, scorer=failing_scorer)
    with pytest.raises(RuntimeError):
        runner.reveal_and_score(lambda: b'outcome', failing_scorer, authorized=True)
    checkpoint = runner.checkpoint()
    runner.close()
    runner = PairedExperimentRunner(tmp_path/'run.sqlite', plan, common=common, checkpoint=checkpoint)
    with pytest.raises(ValueError, match='uncertain'):
        runner.reveal_and_score(lambda: pytest.fail('no reveal'), failing_scorer, authorized=True)
    assert runner._state()['scores'] == {'B0': b'first score'}
    runner.close()


def test_nonbyte_arm_result_leaves_uncertain_intent(tmp_path):
    plan, common, artifacts = case(invalid_callback)
    runner = PairedExperimentRunner(tmp_path/'run.sqlite', plan, common=common, create=True)
    with pytest.raises(ValueError, match='uncertain'):
        runner.run_arm('B0', invalid_callback, artifacts['B0'])
    with pytest.raises(ValueError, match='uncertain'):
        runner.run_arm('B0', invalid_callback, artifacts['B0'])
    runner.close()


def test_changed_plan_and_unknown_newer_terminal_reject(tmp_path):
    runner, plan, common, _ = prepared(tmp_path)
    checkpoint = runner.checkpoint()
    runner.journal.append('unknown', {})
    with pytest.raises(ValueError):
        runner.checkpoint()
    runner.close()
    with pytest.raises(ValueError):
        PairedExperimentRunner(tmp_path/'run.sqlite', plan, common=common, checkpoint=checkpoint)


def test_closure_controller_cannot_claim_stable_code_identity():
    x = 'mutable closure'
    def callback(request):
        return x
    with pytest.raises(ValueError):
        callable_hash(callback)


async def async_callback(request):
    return b'unsupported'


def test_async_callback_rejected_before_any_intent():
    with pytest.raises(ValueError):
        callable_hash(async_callback)


def test_checkpoint_count_cannot_be_boolean(tmp_path):
    plan, common, _ = case()
    path = tmp_path/'run.sqlite'
    runner = PairedExperimentRunner(path, plan, common=common, create=True)
    checkpoint = runner.checkpoint()
    runner.close()
    checkpoint['count'] = True
    with pytest.raises(ValueError):
        PairedExperimentRunner(path, plan, common=common, checkpoint=checkpoint)


REVEAL_MUTATION_PATH = None


def mutating_scorer(request):
    from c15_journal import EvidenceJournal
    witness = EvidenceJournal(REVEAL_MUTATION_PATH)
    try:
        witness.append('foreign', {'changed': True})
    finally:
        witness.close()
    return b'cannot accept'


def test_foreign_reveal_append_during_scorer_prevents_result_commit(tmp_path, monkeypatch):
    runner, _, _, _ = prepared(tmp_path, scorer=mutating_scorer)
    monkeypatch.setattr(__import__(__name__), 'REVEAL_MUTATION_PATH', runner.reveal_path)
    with pytest.raises(ValueError):
        runner.reveal_and_score(lambda: b'outcome', mutating_scorer, authorized=True)
    assert runner._state()['scores'] == {}
    assert runner._state()['pending'] == ('score', 'B0')
    runner.close()


def test_completed_score_replay_rejects_changed_reveal(tmp_path):
    from c15_journal import EvidenceJournal
    runner, plan, common, _ = prepared(tmp_path)
    runner.reveal_and_score(lambda: b'fixed synthetic outcome', null_negative_scorer, authorized=True)
    checkpoint = runner.checkpoint()
    witness = EvidenceJournal(runner.reveal_path)
    witness.append('foreign', {})
    witness.close()
    runner.close()
    runner = PairedExperimentRunner(tmp_path/'run.sqlite', plan, common=common, checkpoint=checkpoint)
    with pytest.raises(ValueError):
        runner.reveal_and_score(None, null_negative_scorer, authorized=True)
    runner.close()
