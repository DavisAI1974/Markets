import hashlib
from types import SimpleNamespace
import pytest
import torch

from research.kalshi.frankie_boss.boss_training_checkpoint import BossTrainingCheckpoint, encode_state
from research.kalshi.frankie_boss.sunday_native_runtime import current_training_identity


def test_next_identity_requires_new_committed_model_and_optimizer_pin(tmp_path):
    native, decoder = torch.nn.Linear(1, 1).double(), torch.nn.Linear(1, 1).double()
    optimizer = torch.optim.AdamW(list(native.parameters())+list(decoder.parameters()), lr=0.0001)
    context = SimpleNamespace(model=native, _model_hash=lambda:
        hashlib.sha256(encode_state(native.state_dict())).hexdigest())
    checkpoint = BossTrainingCheckpoint(tmp_path/'training.sqlite',
        models={'native': native, 'decoder': decoder}, optimizer=optimizer,
        identities={k:'a'*64 for k in ('training_config_hash','code_hash','source_hash','model_hash')}, create=True)
    old_pin = checkpoint.checkpoint_hash
    before = current_training_identity(context, decoder, optimizer, checkpoint, expected_checkpoint_hash=old_pin)
    def update():
        for p in (*native.parameters(), *decoder.parameters()):
            p.grad = torch.ones_like(p)
        optimizer.step()
        return {'local_update': True}
    checkpoint.apply_completed('first', controller_result_hash='b'*64, training_cursor=1, update=update)
    with pytest.raises(ValueError, match='current trusted'):
        current_training_identity(context, decoder, optimizer, checkpoint, expected_checkpoint_hash=old_pin)
    after = current_training_identity(context, decoder, optimizer, checkpoint,
                                      expected_checkpoint_hash=checkpoint.checkpoint_hash)
    assert after['checkpoint_hash'] != before['checkpoint_hash']
    assert after['native_hash'] != before['native_hash']
    with torch.no_grad():
        native.weight.add_(1)
    with pytest.raises(ValueError, match='live model'):
        current_training_identity(context, decoder, optimizer, checkpoint,
                                  expected_checkpoint_hash=checkpoint.checkpoint_hash)
    checkpoint.close()
