"""Atomic CPU BOSS training state between completed controller requests.

No objective, data selection or Granite weight update is defined here. The caller
supplies a local-gradient-only callback after a completed controller result. The
model_hash pin identifies initial weights/architecture; changing trained weights
receive new checkpoint hashes, never a replacement initial identity.
"""
import hashlib
import json
import math
from pathlib import Path
import random
import sqlite3
import sys
import threading

import numpy as np
import torch

from .c15_journal import canonical_bytes, pack, unpack
from .forecast_contract import sha256_digest

SCHEMA = 'BOSS_TRAINING_CHECKPOINT_V1'
IDENTITIES = {'training_config_hash', 'code_hash', 'source_hash', 'model_hash'}
DTYPES = {str(value): value for value in (torch.float64, torch.float32, torch.float16,
    torch.bfloat16, torch.int64, torch.int32, torch.int16, torch.int8, torch.uint8, torch.bool)}


def _tree(value):
    if isinstance(value, torch.Tensor):
        if value.device.type != 'cpu' or value.layout != torch.strided or str(value.dtype) not in DTYPES:
            raise ValueError('supported dense CPU training tensors required')
        if value.is_floating_point() and not torch.isfinite(value).all():
            raise ValueError('nonfinite training tensor')
        tensor = value.detach().contiguous()
        return ('tensor', str(tensor.dtype), tuple(tensor.shape), tensor.reshape(-1).view(torch.uint8).numpy().tobytes())
    if isinstance(value, dict):
        if any(type(key) not in (str, int) for key in value):
            raise ValueError('explicit optimizer or model state keys required')
        return ('mapping', tuple((key, _tree(item)) for key, item in value.items()))
    if type(value) in (list, tuple):
        return ('list' if type(value) is list else 'tuple', tuple(_tree(item) for item in value))
    if value is None or type(value) in (str, bytes, bool, int, float):
        if type(value) is float and not math.isfinite(value):
            raise ValueError('nonfinite training scalar')
        return ('scalar', value)
    raise ValueError('unsupported training state; explicit representation required')


def _untree(value):
    kind = value[0]
    if kind == 'tensor':
        _, name, shape, raw = value
        dtype = DTYPES[name]
        if (type(shape) is not tuple or any(type(n) is not int or n < 0 for n in shape)
                or type(raw) is not bytes or len(raw) != math.prod(shape)*torch.empty((), dtype=dtype).element_size()):
            raise ValueError('invalid training tensor dimensions')
        return (torch.frombuffer(bytearray(raw), dtype=dtype).clone().reshape(shape)
                if raw else torch.empty(shape, dtype=dtype))
    if kind == 'mapping':
        return {key: _untree(item) for key, item in value[1]}
    if kind in ('list', 'tuple'):
        result = [_untree(item) for item in value[1]]
        return result if kind == 'list' else tuple(result)
    if kind == 'scalar':
        return value[1]
    raise ValueError('unknown training state encoding')


def encode_state(value):
    """Existing exact evidence encoding, with explicit tensor/int-key map nodes."""
    return canonical_bytes(pack(_tree(value)))


def _decode(raw):
    try:
        value = _untree(unpack(json.loads(raw)))
        if encode_state(value) != raw:
            raise ValueError('noncanonical training state')
        return value
    except (ValueError, KeyError, TypeError, IndexError, OverflowError, RuntimeError) as exc:
        raise ValueError('invalid exact training state') from exc


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _class(value):
    return type(value).__module__ + '.' + type(value).__qualname__


def _rng():
    name, keys, position, gaussian, cached = np.random.get_state()
    return dict(python=random.getstate(), torch=torch.get_rng_state(),
                numpy=(name, keys.tobytes(), position, gaussian, cached))


def _set_rng(value):
    name, keys, position, gaussian, cached = value['numpy']
    np.random.set_state((name, np.frombuffer(keys, dtype=np.uint32).copy(), position, gaussian, cached))
    random.setstate(value['python'])
    torch.set_rng_state(value['torch'])


class BossTrainingCheckpoint:
    """Single writer with atomic completed updates and exact caller-owned restore.

    Models must contain native and decoder and may contain teacher. CPU modules
    are supplied by the caller; no constructors or pickle code are loaded from
    the checkpoint. Retain checkpoint_hash separately when independent rollback
    detection is needed and pass it as expected_checkpoint_hash on restore.
    Never reuse an instance after a failed/uncertain update: close and restore.
    training_cursor is the monotonically increasing causal training boundary,
    initially -1. A request ID can commit at most one gradient callback.
    """

    def __init__(self, path, *, models, optimizer, identities, create=False, expected_checkpoint_hash=None):
        if type(identities) is not dict or set(identities) != IDENTITIES:
            raise ValueError('explicit training/config/code/source/initial-model identities required')
        for name, digest in identities.items():
            sha256_digest(digest, name)
        if (type(models) is not dict or set(models) not in ({'native', 'decoder'}, {'native', 'decoder', 'teacher'})
                or any(not isinstance(model, torch.nn.Module) for model in models.values())
                or not isinstance(optimizer, torch.optim.Optimizer)):
            raise ValueError('caller-owned native, decoder, optional teacher and optimizer required')
        self.models, self.optimizer = dict(models), optimizer
        self._identities = dict(identities)  # detached from the caller's mutable mapping
        self._binding = self._layout()
        self._lock, self._failed = threading.Lock(), False
        path = Path(path)
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb'):
                pass
        elif not path.is_file():
            raise ValueError('training checkpoint is missing')
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA synchronous=FULL')
        try:
            if create:
                self.db.execute('CREATE TABLE checkpoints (sequence INTEGER PRIMARY KEY, request_id TEXT UNIQUE, payload BLOB NOT NULL, digest TEXT NOT NULL)')
                state = self._envelope(0, None, None, -1, None)
                self._insert(state)
                self.db.commit()
            previous = None
            last = None
            for sequence, request_id, raw, digest in self.db.execute('SELECT sequence,request_id,payload,digest FROM checkpoints ORDER BY sequence'):
                if _sha(raw) != digest:
                    raise ValueError('training checkpoint digest differs')
                state = _decode(raw)
                if (set(state) != {'schema', 'identities', 'binding', 'sequence', 'request_id', 'controller_result_hash',
                                  'training_cursor', 'previous_hash', 'models', 'optimizer', 'rng', 'update_result'}
                        or state['schema'] != SCHEMA or type(state['sequence']) is not int or state['sequence'] != sequence
                        or state['request_id'] != request_id or type(state['training_cursor']) is not int
                        or sequence != (0 if last is None else last['sequence']+1)
                        or state['previous_hash'] != previous
                        or state['identities'] != self._identities or encode_state(state['binding']) != encode_state(self._binding)
                        or (last is not None and state['training_cursor'] <= last['training_cursor'])):
                    raise ValueError('training checkpoint identity or chain differs')
                if sequence == 0:
                    if (request_id is not None or state['controller_result_hash'] is not None
                            or state['training_cursor'] != -1 or state['update_result'] is not None):
                        raise ValueError('initial seed checkpoint differs')
                else:
                    if type(request_id) is not str or not request_id or len(request_id) > 256:
                        raise ValueError('completed training request identity missing')
                    sha256_digest(state['controller_result_hash'], 'controller_result_hash')
                previous, last = digest, state
            if last is None or (expected_checkpoint_hash is not None and previous != expected_checkpoint_hash):
                raise ValueError('training checkpoint missing or differs from retained hash')
            self._restore(last)
            self._head = self._receipt(last, previous)
        except BaseException:
            self.db.close()
            raise

    def _layout(self):
        names, models = {}, {}
        for role, model in self.models.items():
            for name, parameter in model.named_parameters():
                if id(parameter) in names:
                    raise ValueError('shared parameters across training models are unsupported')
                names[id(parameter)] = role+'.'+name
            tensors = model.state_dict()
            _tree(tensors)  # Refuse unsupported device/dtype before creating state.
            models[role] = dict(kind=_class(model), representation=repr(model),
                tensors={name: (str(t.dtype), tuple(t.shape)) for name, t in tensors.items()},
                parameters=tuple(name for name, _ in model.named_parameters()),
                modules=tuple((name, _class(module)) for name, module in model.named_modules()))
        groups = []
        seen = set()
        for group in self.optimizer.param_groups:
            group_names = []
            for parameter in group['params']:
                if id(parameter) not in names or id(parameter) in seen:
                    raise ValueError('optimizer parameters must bind uniquely to supplied models')
                seen.add(id(parameter))
                group_names.append(names[id(parameter)])
            groups.append(tuple(group_names))
        if any(parameter.requires_grad and id(parameter) not in seen
               for model in self.models.values() for parameter in model.parameters()):
            raise ValueError('trainable model parameter missing from optimizer')
        return dict(models=models, optimizer=_class(self.optimizer), groups=tuple(groups),
            runtime=dict(python=sys.version, torch=str(torch.__version__), numpy=np.__version__, byteorder=sys.byteorder,
                threads=torch.get_num_threads(), deterministic=torch.are_deterministic_algorithms_enabled(),
                code=_sha(Path(__file__).read_bytes())))

    def _envelope(self, sequence, request_id, result_hash, cursor, previous, update_result=None):
        return dict(schema=SCHEMA, identities=dict(self._identities), binding=self._binding, sequence=sequence,
            request_id=request_id, controller_result_hash=result_hash, training_cursor=cursor, previous_hash=previous,
            models={role: dict(weights=model.state_dict(),
                modes={name: module.training for name, module in model.named_modules()},
                requires_grad={name: p.requires_grad for name, p in model.named_parameters()},
                gradients={name: p.grad for name, p in model.named_parameters()}) for role, model in self.models.items()},
            optimizer=self.optimizer.state_dict(), rng=_rng(), update_result=update_result)

    def _restore(self, state):
        if set(state['models']) != set(self.models):
            raise ValueError('saved model state is missing')
        for role, model in self.models.items():
            saved = state['models'][role]
            parameters, modules = dict(model.named_parameters()), dict(model.named_modules())
            if (set(saved) != {'weights', 'modes', 'requires_grad', 'gradients'}
                    or set(saved['weights']) != set(model.state_dict()) or set(saved['modes']) != set(modules)
                    or set(saved['requires_grad']) != set(parameters) or set(saved['gradients']) != set(parameters)):
                raise ValueError('saved model state is incomplete')
            for name, tensor in model.state_dict().items():
                stored = saved['weights'][name]
                if not isinstance(stored, torch.Tensor) or stored.dtype != tensor.dtype or stored.shape != tensor.shape:
                    raise ValueError('saved model dtype or shape differs')
            if any(type(flag) is not bool for flag in (*saved['modes'].values(), *saved['requires_grad'].values())):
                raise ValueError('saved model mode flags differ')
            model.load_state_dict(saved['weights'], strict=True)
            if encode_state(model.state_dict()) != encode_state(saved['weights']):
                raise ValueError('model restore changed exact state')
            for name, module in modules.items():
                module.training = saved['modes'][name]
            for name, parameter in parameters.items():
                parameter.requires_grad_(saved['requires_grad'][name])
                parameter.grad = saved['gradients'][name]
        if set(state['optimizer']) != {'state', 'param_groups'}:
            raise ValueError('saved optimizer state is incomplete')
        self.optimizer.load_state_dict(state['optimizer'])
        # load_state_dict may cast optimizer tensors; require exact roundtrip.
        if encode_state(self.optimizer.state_dict()) != encode_state(state['optimizer']):
            raise ValueError('optimizer restore changed exact state')
        _set_rng(state['rng'])

    @staticmethod
    def _receipt(state, digest):
        return {name: state[name] for name in ('sequence', 'request_id', 'controller_result_hash', 'training_cursor')} | dict(
            checkpoint_hash=digest, update_result=_decode(encode_state(state['update_result'])))

    def _insert(self, state):
        raw = encode_state(state)
        digest = _sha(raw)
        self.db.execute('INSERT INTO checkpoints VALUES (?,?,?,?)', (state['sequence'], state['request_id'], raw, digest))
        return self._receipt(state, digest)

    @property
    def identities(self):
        """Admitted identities as a fresh plain dict: callers cannot mutate the admitted mapping,
        and the exact-type (dict) serialization/binding paths keep working unchanged."""
        return dict(self._identities)

    @property
    def checkpoint_hash(self):
        return self._head['checkpoint_hash']

    @property
    def training_cursor(self):
        return self._head['training_cursor']

    def apply_completed(self, request_id, *, controller_result_hash, training_cursor, update):
        if (type(request_id) is not str or not request_id or len(request_id) > 256
                or type(training_cursor) is not int or training_cursor < 0 or not callable(update)):
            raise ValueError('completed request, causal cursor and local gradient callback required')
        sha256_digest(controller_result_hash, 'controller_result_hash')
        with self._lock:
            if self._failed:
                raise RuntimeError('training state uncertain; close and restore checkpoint')
            self.db.execute('BEGIN IMMEDIATE')
            mutated = False
            try:
                head = self.db.execute('SELECT digest FROM checkpoints ORDER BY sequence DESC LIMIT 1').fetchone()
                if head is None or head[0] != self.checkpoint_hash:
                    self._failed = True
                    raise RuntimeError('training checkpoint advanced elsewhere; restore required')
                old = self.db.execute('SELECT payload,digest FROM checkpoints WHERE request_id=?', (request_id,)).fetchone()
                if old is not None:
                    saved = _decode(old[0])
                    if (saved['controller_result_hash'] != controller_result_hash or saved['training_cursor'] != training_cursor
                            or _sha(old[0]) != old[1]):
                        raise ValueError('completed training request identity changed')
                    self.db.rollback()
                    return self._receipt(saved, old[1])
                if training_cursor <= self.training_cursor:
                    raise ValueError('training cursor must advance')
                if encode_state(self._layout()) != encode_state(self._binding):
                    raise ValueError('training architecture or runtime changed')
                mutated = True
                update_result = update()
                state = self._envelope(self._head['sequence']+1, request_id, controller_result_hash,
                                       training_cursor, self.checkpoint_hash, update_result)
                result = self._insert(state)
                self.db.commit()
                self._head = result
                return dict(result)
            except BaseException:
                if mutated:
                    self._failed = True
                self.db.rollback()
                raise

    def close(self):
        self.db.close()
