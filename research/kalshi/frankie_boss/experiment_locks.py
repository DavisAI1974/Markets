"""Immutable paired software locks; no arm execution or outcome access."""
from dataclasses import asdict, dataclass
import hashlib

try:
    from .c15_journal import evidence_hash
    from .forecast_contract import sha256_digest
except ImportError:
    from c15_journal import evidence_hash
    from forecast_contract import sha256_digest

FACTORS = ('model_hash', 'initialization_hash', 'optimizer_hash', 'batch_order_hash',
           'seed_hash', 'memory_hash', 'qsv_hash', 'teacher_hash', 'controller_hash')


def _name(value):
    if type(value) is not str or not value.strip():
        raise ValueError('nonempty arm identifier required')


class _Identity:
    @property
    def digest(self):
        return evidence_hash(dict(schema='BOSS_EXPERIMENT_LOCKS_V1',
                                  kind=type(self).__name__, fields=asdict(self)))


@dataclass(frozen=True)
class ArmLock(_Identity):
    arm_id: str
    model_hash: str
    initialization_hash: str
    optimizer_hash: str
    batch_order_hash: str
    seed_hash: str
    memory_hash: str
    qsv_hash: str
    teacher_hash: str
    controller_hash: str

    def __post_init__(self):
        _name(self.arm_id)
        for field in FACTORS:
            sha256_digest(getattr(self, field), field)


@dataclass(frozen=True)
class Pairing(_Identity):
    left: str
    right: str
    varying: tuple[str, ...]

    def __post_init__(self):
        _name(self.left)
        _name(self.right)
        if (self.left == self.right or type(self.varying) is not tuple
                or any(type(f) is not str or f not in FACTORS for f in self.varying)
                or len(set(self.varying)) != len(self.varying)):
            raise ValueError('distinct pair and unique declared factors required')
        object.__setattr__(self, 'varying', tuple(sorted(self.varying)))


@dataclass(frozen=True)
class ExperimentPlan(_Identity):
    arms: tuple[ArmLock, ...]
    pairs: tuple[Pairing, ...]
    source_hash: str
    partition_hash: str
    schedule_hash: str
    scorer_hash: str
    exclusions_hash: str

    def __post_init__(self):
        for field in ('source_hash', 'partition_hash', 'schedule_hash',
                      'scorer_hash', 'exclusions_hash'):
            sha256_digest(getattr(self, field), field)
        if (type(self.arms) is not tuple or len(self.arms) < 2
                or any(type(a) is not ArmLock for a in self.arms)
                or type(self.pairs) is not tuple or not self.pairs
                or any(type(p) is not Pairing for p in self.pairs)):
            raise ValueError('complete typed roster and pairings required')
        arms = {a.arm_id: a for a in self.arms}
        if len(arms) != len(self.arms):
            raise ValueError('duplicate arm')
        seen, paired = set(), set()
        for pair in self.pairs:
            key = tuple(sorted((pair.left, pair.right)))
            if key in seen or not set(key) <= arms.keys():
                raise ValueError('duplicate or unknown pair')
            seen.add(key)
            paired.update(key)
            for field in FACTORS:
                if (field not in pair.varying and
                        getattr(arms[pair.left], field) != getattr(arms[pair.right], field)):
                    raise ValueError(f'undeclared {field} difference: {pair.left}/{pair.right}')
        if paired != arms.keys():
            raise ValueError('every arm must participate in a comparison')
        object.__setattr__(self, 'arms', tuple(sorted(self.arms, key=lambda a: a.arm_id)))
        object.__setattr__(self, 'pairs', tuple(sorted(self.pairs, key=lambda p: (p.left, p.right))))


@dataclass(frozen=True)
class FrozenOutputs(_Identity):
    plan_hash: str
    outputs: tuple[tuple[str, str], ...]

    def __post_init__(self):
        sha256_digest(self.plan_hash, 'plan_hash')
        if type(self.outputs) is not tuple or not self.outputs:
            raise ValueError('immutable output identities required')
        seen = set()
        for entry in self.outputs:
            if type(entry) is not tuple or len(entry) != 2:
                raise ValueError('typed output entry required')
            name, digest = entry
            _name(name)
            sha256_digest(digest, 'output_hash')
            if name in seen:
                raise ValueError('duplicate output arm')
            seen.add(name)
        object.__setattr__(self, 'outputs', tuple(sorted(self.outputs)))


def freeze_outputs(plan, outputs):
    """Freeze exact supplied bytes; hashes do not authenticate their origin."""
    if type(plan) is not ExperimentPlan or type(outputs) is not dict:
        raise ValueError('typed plan and complete output mapping required')
    if set(outputs) != {a.arm_id for a in plan.arms}:
        raise ValueError('output roster differs from plan')
    if any(type(payload) is not bytes for payload in outputs.values()):
        raise ValueError('exact output bytes required')
    return FrozenOutputs(plan.digest, tuple((name, hashlib.sha256(payload).hexdigest())
                                           for name, payload in outputs.items()))
