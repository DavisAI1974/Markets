"""Review fix L3: admitted checkpoint identities are detached from callers in both directions."""
import torch

import pytest

from research.kalshi.frankie_boss.boss_training_checkpoint import BossTrainingCheckpoint, encode_state


PINS = dict(training_config_hash='a'*64, code_hash='b'*64, source_hash='c'*64, model_hash='d'*64)


def tiny():
    models = {name: torch.nn.Linear(1, 1) for name in ('native', 'decoder')}
    optimizer = torch.optim.SGD([p for m in models.values() for p in m.parameters()], lr=.1)
    return models, optimizer


def test_identities_detached_from_supplied_and_returned_mappings(tmp_path):
    supplied = dict(PINS)
    models, optimizer = tiny()
    store = BossTrainingCheckpoint(tmp_path/'run.sqlite', models=models, optimizer=optimizer,
                                   identities=supplied, create=True)
    supplied['model_hash'] = 'e'*64
    assert store.identities == PINS
    view = store.identities
    view['source_hash'] = 'f'*64
    view['extra'] = 'g'*64
    assert store.identities == PINS
    assert type(store.identities) is dict and encode_state(store.identities) == encode_state(PINS)
    receipt = store.apply_completed('request-1', controller_result_hash='1'*64, training_cursor=1,
                                    update=lambda: dict(updated=True))
    store.close()
    reopened = BossTrainingCheckpoint(tmp_path/'run.sqlite', models=models, optimizer=optimizer,
                                      identities=dict(PINS), expected_checkpoint_hash=receipt['checkpoint_hash'])
    assert reopened.identities == PINS
    reopened.close()
    with pytest.raises(ValueError, match='identity or chain differs'):
        BossTrainingCheckpoint(tmp_path/'run.sqlite', models=models, optimizer=optimizer, identities=supplied)
