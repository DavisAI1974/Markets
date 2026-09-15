"""Tiny synthetic CPU updates only; no production fit or remote model calls."""
import random
import sqlite3

import numpy as np
import pytest
import torch

from research.kalshi.frankie_boss.boss_training_checkpoint import BossTrainingCheckpoint, encode_state


PINS = dict(training_config_hash='a'*64, code_hash='b'*64, source_hash='c'*64, model_hash='d'*64)


def tiny():
    models = {name: torch.nn.Linear(2, 2).double() for name in ('native', 'decoder', 'teacher')}
    optimizer = torch.optim.AdamW([
        {'params': list(models['native'].parameters()), 'lr': .01},
        {'params': list(models['decoder'].parameters()) + list(models['teacher'].parameters()), 'lr': .02}],
        weight_decay=.03)
    return models, optimizer


def seed():
    random.seed(7)
    np.random.seed(7)
    torch.manual_seed(7)


def update(models, optimizer):
    optimizer.zero_grad(set_to_none=True)
    x = torch.randn(3, 2, dtype=torch.float64) + random.random() + float(np.random.rand())
    loss = (models['decoder'](models['native'](x)) - models['teacher'](x)).square().mean()
    loss.backward()
    optimizer.step()


def apply(store, models, optimizer, cursor):
    return store.apply_completed('request-'+str(cursor), controller_result_hash=str(cursor)*64,
        training_cursor=cursor, update=lambda: update(models, optimizer))


def test_actual_restore_continue_equals_uninterrupted_weights_optimizer_and_rng(tmp_path):
    seed()
    left, lo = tiny()
    continuous = BossTrainingCheckpoint(tmp_path/'continuous.sqlite', models=left, optimizer=lo,
                                        identities=PINS, create=True)
    apply(continuous, left, lo, 1)
    expected = apply(continuous, left, lo, 2)
    left_state = encode_state(dict(models={k: v.state_dict() for k, v in left.items()}, optimizer=lo.state_dict()))
    random_after = (random.random(), float(np.random.rand()), torch.rand(3))
    continuous.close()

    seed()
    right, ro = tiny()
    interrupted = BossTrainingCheckpoint(tmp_path/'resume.sqlite', models=right, optimizer=ro,
                                         identities=PINS, create=True)
    first = apply(interrupted, right, ro, 1)
    interrupted.close()
    restored, optimizer = tiny()  # construction consumes RNG; restore must replace it
    resumed = BossTrainingCheckpoint(tmp_path/'resume.sqlite', models=restored, optimizer=optimizer,
        identities=PINS, expected_checkpoint_hash=first['checkpoint_hash'])
    assert resumed.training_cursor == 1
    assert resumed.apply_completed('request-1', controller_result_hash='1'*64, training_cursor=1,
                                  update=lambda: pytest.fail('completed update replayed')) == first
    actual = apply(resumed, restored, optimizer, 2)
    assert encode_state(dict(models={k: v.state_dict() for k, v in restored.items()}, optimizer=optimizer.state_dict())) == left_state
    assert actual['checkpoint_hash'] == expected['checkpoint_hash']
    assert (random.random(), float(np.random.rand())) == random_after[:2]
    assert torch.equal(torch.rand(3), random_after[2])
    resumed.close()


def test_failed_mutation_requires_restore_and_restores_initial_seed_state(tmp_path):
    seed()
    models, optimizer = tiny()
    store = BossTrainingCheckpoint(tmp_path/'run.sqlite', models=models, optimizer=optimizer, identities=PINS, create=True)
    initial = store.checkpoint_hash
    weights = encode_state({k: v.state_dict() for k, v in models.items()})
    def fail():
        update(models, optimizer)
        raise RuntimeError('synthetic failure after parameter mutation')
    with pytest.raises(RuntimeError):
        store.apply_completed('request-1', controller_result_hash='1'*64, training_cursor=1, update=fail)
    with pytest.raises(RuntimeError, match='restore'):
        apply(store, models, optimizer, 1)
    store.close()
    restored, fresh_optimizer = tiny()
    resumed = BossTrainingCheckpoint(tmp_path/'run.sqlite', models=restored, optimizer=fresh_optimizer,
                                     identities=PINS, expected_checkpoint_hash=initial)
    assert resumed.training_cursor == -1
    assert encode_state({k: v.state_dict() for k, v in restored.items()}) == weights
    apply(resumed, restored, fresh_optimizer, 1)
    resumed.close()


def test_resume_preserves_modes_requires_grad_and_gradients(tmp_path):
    models, optimizer = tiny()
    models['teacher'].eval()
    models['teacher'].bias.requires_grad_(False)
    store = BossTrainingCheckpoint(tmp_path/'run.sqlite', models=models, optimizer=optimizer, identities=PINS, create=True)
    apply(store, models, optimizer, 1)
    grads = encode_state({role: {name: p.grad for name, p in model.named_parameters()} for role, model in models.items()})
    store.close()
    restored, fresh_optimizer = tiny()
    restored['teacher'].bias.requires_grad_(False)
    resumed = BossTrainingCheckpoint(tmp_path/'run.sqlite', models=restored, optimizer=fresh_optimizer, identities=PINS)
    assert not restored['teacher'].training
    assert not restored['teacher'].bias.requires_grad
    assert encode_state({role: {name: p.grad for name, p in model.named_parameters()} for role, model in restored.items()}) == grads
    resumed.close()


@pytest.mark.parametrize('damage', ['config', 'model_roster', 'optimizer_order', 'missing', 'digest'])
def test_missing_or_drifted_state_refuses(tmp_path, damage):
    models, optimizer = tiny()
    path = tmp_path/'run.sqlite'
    store = BossTrainingCheckpoint(path, models=models, optimizer=optimizer, identities=PINS, create=True)
    store.close()
    fresh, opt = tiny()
    pins = dict(PINS)
    if damage == 'config':
        pins['training_config_hash'] = 'e'*64
    elif damage == 'model_roster':
        fresh.pop('teacher')
    elif damage == 'optimizer_order':
        opt.param_groups[0]['params'].reverse()
    elif damage == 'missing':
        path = tmp_path/'missing.sqlite'
    else:
        with sqlite3.connect(path) as db:
            db.execute("UPDATE checkpoints SET payload=? WHERE sequence=0", (b'corrupt',))
    with pytest.raises(ValueError):
        BossTrainingCheckpoint(path, models=fresh, optimizer=opt, identities=pins)


def test_reused_request_drift_and_regressed_cursor_refuse_without_update(tmp_path):
    models, optimizer = tiny()
    store = BossTrainingCheckpoint(tmp_path/'run.sqlite', models=models, optimizer=optimizer, identities=PINS, create=True)
    apply(store, models, optimizer, 2)
    for request, result, cursor in [('request-2', '3'*64, 2), ('other', '1'*64, 1)]:
        with pytest.raises(ValueError):
            store.apply_completed(request, controller_result_hash=result, training_cursor=cursor,
                                  update=lambda: pytest.fail('invalid update executed'))
    store.close()


def test_persistence_failure_rolls_back_and_requires_restore(tmp_path, monkeypatch):
    models, optimizer = tiny()
    path = tmp_path/'run.sqlite'
    store = BossTrainingCheckpoint(path, models=models, optimizer=optimizer, identities=PINS, create=True)
    initial = store.checkpoint_hash
    original = store._insert
    def interrupted_insert(state):
        original(state)
        raise OSError('synthetic disk write failure before commit')
    monkeypatch.setattr(store, '_insert', interrupted_insert)
    with pytest.raises(OSError):
        apply(store, models, optimizer, 1)
    with pytest.raises(RuntimeError, match='restore'):
        apply(store, models, optimizer, 1)
    store.close()
    models, optimizer = tiny()
    resumed = BossTrainingCheckpoint(path, models=models, optimizer=optimizer, identities=PINS,
                                     expected_checkpoint_hash=initial)
    assert resumed.training_cursor == -1
    apply(resumed, models, optimizer, 1)
    resumed.close()


def test_learning_result_persists_with_update_and_replays_without_callback(tmp_path):
    models, optimizer = tiny()
    path = tmp_path/'learning.sqlite'
    store = BossTrainingCheckpoint(path, models=models, optimizer=optimizer, identities=PINS, create=True)
    learning = dict(objective='synthetic-test-only', loss=0.125,
                    lessons=('synthetic lesson',), evidence=b'exact local receipt')
    def train():
        update(models, optimizer)
        return learning
    committed = store.apply_completed('completed', controller_result_hash='e'*64, training_cursor=5, update=train)
    assert committed['update_result'] == learning
    learning['loss'] = 999
    assert committed['update_result']['loss'] == 0.125
    store.close()
    restored, opt = tiny()
    resumed = BossTrainingCheckpoint(path, models=restored, optimizer=opt, identities=PINS,
                                     expected_checkpoint_hash=committed['checkpoint_hash'])
    replay = resumed.apply_completed('completed', controller_result_hash='e'*64, training_cursor=5,
                                    update=lambda: pytest.fail('committed learning update replayed'))
    assert replay == committed
    replay['update_result']['loss'] = 321
    second = resumed.apply_completed('completed', controller_result_hash='e'*64, training_cursor=5,
                                     update=lambda: pytest.fail('committed learning update replayed'))
    assert second['update_result']['loss'] == 0.125
    resumed.close()
