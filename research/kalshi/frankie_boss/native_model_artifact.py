"""Exact local native/B1 snapshots; serialization is not evidence of fitting."""
from dataclasses import asdict, dataclass, fields
import json
import math
from pathlib import Path
import torch
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY

try:
    from .b1_reasoner import B1Reasoner, B1Config
    from .c15_journal import canonical_bytes, pack, unpack, evidence_hash
    from .context_session import tensor_identity
    from .forecast_artifact import runtime_hash as decoder_runtime_hash
    from .forecast_contract import HashedContract, sha256_digest
    from .native_forecast_refresh import native_execution_hash
    from .native_mbo_encoder import NativeTrunk, NativeRegistry
    from .trunk import TrunkConfig
except ImportError:
    from b1_reasoner import B1Reasoner, B1Config
    from c15_journal import canonical_bytes, pack, unpack, evidence_hash
    from context_session import tensor_identity
    from forecast_artifact import runtime_hash as decoder_runtime_hash
    from forecast_contract import HashedContract, sha256_digest
    from native_forecast_refresh import native_execution_hash
    from native_mbo_encoder import NativeTrunk, NativeRegistry
    from trunk import TrunkConfig


def decode_exact(payload):
    """Decode existing evidence encoding without accepting lossy/duplicate nodes."""
    if type(payload) is not bytes:
        raise ValueError('immutable encoded bytes required')
    try:
        value = unpack(json.loads(payload))
        if canonical_bytes(pack(value)) != payload:
            raise ValueError('noncanonical evidence encoding')
        return value
    except (TypeError, KeyError, IndexError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid evidence encoding') from exc


def runtime_hash():
    names = ('native_model_artifact.py', 'trunk.py', 'b1_reasoner.py',
             'native_mbo_encoder.py', 'native_forecast_refresh.py', 'context_session.py',
             'c15_journal.py', 'causal_packet.py')
    return evidence_hash(dict(decoder_runtime=decoder_runtime_hash(), qsv_registry=QSV_FEATURE_REGISTRY,
        code={name: Path(__file__).with_name(name).read_bytes() for name in names}))


def _construct(config):
    if (type(config) is not dict or set(config) !=
            {'kind', 'trunk', 'registry', 'qsv_ablated', 'recurrence'}):
        raise ValueError('complete native configuration required')
    trunk = config['trunk']
    if type(trunk) is not dict or set(trunk) != {f.name for f in fields(TrunkConfig)}:
        raise ValueError('complete trunk configuration required')
    for name, value in trunk.items():
        if name in ('use_delta_memory', 'use_qsv'):
            valid = type(value) is bool
        elif name == 'window':
            valid = value is None or type(value) is int and value > 0
        elif name == 'categorical_cardinalities':
            valid = type(value) is tuple and all(type(n) is int and n > 0 for n in value)
        else:
            valid = type(value) is int and value > 0
        if not valid:
            raise ValueError('invalid trunk configuration type or dimension')
    if type(config['qsv_ablated']) is not bool:
        raise ValueError('explicit QSV ablation required')
    if (type(config['registry']) is not dict or
            set(config['registry']) != {f.name for f in fields(NativeRegistry)}):
        raise ValueError('complete native registry configuration required')
    registry = NativeRegistry(**config['registry'])
    with torch.random.fork_rng(devices=[]), torch.device('cpu'):
        native = NativeTrunk(registry, **trunk).double().eval()
        if pack(asdict(native.cfg)) != pack(trunk):
            raise ValueError('native fixed input configuration differs')
        if config['qsv_ablated']:
            native.encoder.ablate_qsv()
        if native.encoder._qsv_ablated != config['qsv_ablated']:
            raise ValueError('QSV ablation differs from configured architecture')
        if config['kind'] == 'native' and config['recurrence'] is None:
            return native
        recurrence = config['recurrence']
        if (config['kind'] != 'b1' or type(recurrence) is not dict
                or set(recurrence) != {f.name for f in fields(B1Config)}):
            raise ValueError('complete native or B1 configuration required')
        return B1Reasoner(native, B1Config(**recurrence)).double().eval()


@dataclass(frozen=True, slots=True)
class NativeModelSnapshot(HashedContract):
    configuration: bytes
    weights: bytes
    execution_hash: str
    runtime: str

    def __post_init__(self):
        if type(self.configuration) is not bytes or type(self.weights) is not bytes:
            raise ValueError('immutable configuration and tensor bytes required')
        sha256_digest(self.execution_hash, 'execution_hash')
        sha256_digest(self.runtime, 'runtime')

    @classmethod
    def capture(cls, model):
        native = model.trunk if type(model) is B1Reasoner else model
        if (type(native) is not NativeTrunk or type(model) not in (NativeTrunk, B1Reasoner)
                or any(m.training for m in model.modules())
                or any(t.dtype != torch.float64 or t.device.type != 'cpu'
                       or not torch.isfinite(t).all() for t in model.state_dict().values())):
            raise ValueError('finite CPU float64 eval-mode native or B1 model required')
        config = dict(kind='b1' if type(model) is B1Reasoner else 'native',
            trunk=asdict(native.cfg), registry=asdict(native.registry),
            qsv_ablated=native.encoder._qsv_ablated,
            recurrence=asdict(model.config) if type(model) is B1Reasoner else None)
        canonical = _construct(config)
        expected_modules = dict(canonical.named_modules())
        if (native_execution_hash(model) != native_execution_hash(canonical)
                or any(type(module) is not type(expected_modules.get(name))
                    or any(callable(v) for v in vars(module).values())
                    for name, module in model.named_modules())):
            raise ValueError('native effective module configuration differs')
        return cls(canonical_bytes(pack(config)),
            canonical_bytes(pack(tensor_identity(model.state_dict()))),
            native_execution_hash(model), runtime_hash())

    def restore(self):
        if self.runtime != runtime_hash():
            raise ValueError('native runtime or code differs')
        model = _construct(decode_exact(self.configuration))
        if native_execution_hash(model) != self.execution_hash:
            raise ValueError('native effective module configuration differs')
        weights = decode_exact(self.weights)
        expected = model.state_dict()
        if type(weights) is not dict or set(weights) != set(expected):
            raise ValueError('native tensor keys differ')
        tensors = {}
        for name, target in expected.items():
            value = weights[name]
            if (type(value) is not dict or set(value) != {'dtype', 'shape', 'bytes'}
                    or value['dtype'] != 'torch.float64'
                    or type(value['shape']) is not tuple
                    or any(type(n) is not int for n in value['shape'])
                    or value['shape'] != tuple(target.shape)
                    or type(value['bytes']) is not bytes
                    or len(value['bytes']) != math.prod(target.shape)*8):
                raise ValueError('native tensor shape, dtype or byte length differs')
            tensor = torch.frombuffer(bytearray(value['bytes']), dtype=torch.float64).reshape(target.shape).clone()
            if not torch.isfinite(tensor).all():
                raise ValueError('nonfinite native tensor')
            tensors[name] = tensor
        model.load_state_dict(tensors, strict=True)
        model.requires_grad_(False)
        return model
