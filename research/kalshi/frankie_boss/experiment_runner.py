"""Durable paired arm execution and explicit scoring; no built-in data loaders."""
from dataclasses import asdict, dataclass
import hashlib
import inspect
import json
import marshal
from pathlib import Path

try:
    from .c15_journal import EvidenceJournal, evidence_hash
    from .experiment_locks import ExperimentPlan, FACTORS, freeze_outputs
    from .experiment_reveal import RevealLedger
except ImportError:
    from c15_journal import EvidenceJournal, evidence_hash
    from experiment_locks import ExperimentPlan, FACTORS, freeze_outputs
    from experiment_reveal import RevealLedger

SCHEMA = 'BOSS_PAIRED_EXECUTION_V1'


def _hash(value):
    if type(value) is not bytes:
        raise ValueError('exact immutable bytes required')
    return hashlib.sha256(value).hexdigest()


def callable_hash(callback):
    """Pin supported function code, not its external dependency behavior."""
    if (not inspect.isfunction(callback) or callback.__closure__ is not None
            or callback.__defaults__ or callback.__kwdefaults__
            or '<locals>' in callback.__qualname__ or inspect.iscoroutinefunction(callback)
            or inspect.isgeneratorfunction(callback)):
        raise ValueError('module-level Python callback without closure/defaults required')
    source = inspect.getsourcefile(callback)
    if source is None or not Path(source).is_file():
        raise ValueError('callback must have an auditable source file')
    return evidence_hash(dict(schema=SCHEMA, name=callback.__qualname__,
        module=Path(source).read_bytes(), code=marshal.dumps(callback.__code__)))


def _checkpoint(value):
    if (type(value) is not dict or set(value) != {'count', 'head_hash'}
            or type(value['count']) is not int or value['count'] < 0
            or type(value['head_hash']) is not str or len(value['head_hash']) != 64
            or any(c not in '0123456789abcdef' for c in value['head_hash'])):
        raise ValueError('exact trusted count/head checkpoint required')
    return value


@dataclass(frozen=True)
class SharedInput:
    source: bytes
    partition: bytes
    schedule: bytes
    exclusions: bytes

    def validate(self, plan):
        for field in ('source', 'partition', 'schedule', 'exclusions'):
            if _hash(getattr(self, field)) != getattr(plan, field + '_hash'):
                raise ValueError(f'shared {field} differs from plan')
        try:
            order = json.loads(self.schedule)
        except (ValueError, UnicodeError) as exc:
            raise ValueError('execution schedule must be a JSON roster') from exc
        if (type(order) is not list or any(type(name) is not str for name in order)
                or len(order) != len(plan.arms) or set(order) != {arm.arm_id for arm in plan.arms}):
            raise ValueError('execution schedule must contain every arm exactly once')
        return tuple(order)


@dataclass(frozen=True)
class ArmRequest:
    arm_id: str
    plan_hash: str
    common: SharedInput
    artifacts: tuple[tuple[str, bytes], ...]


@dataclass(frozen=True)
class ScoreRequest:
    arm_id: str
    output: bytes
    outcomes: bytes
    partition: bytes
    exclusions: bytes


class PairedExperimentRunner:
    def __init__(self, path, plan, *, common, create=False, checkpoint=None):
        if type(plan) is not ExperimentPlan or type(common) is not SharedInput:
            raise ValueError('typed plan and shared input required')
        if type(create) is not bool or (create and checkpoint is not None) or (not create and checkpoint is None):
            raise ValueError('create or independently trusted restart checkpoint required')
        self.plan, self.common = plan, common
        self.order = common.validate(plan)
        self.arms = {arm.arm_id: arm for arm in plan.arms}
        self.reveal_path = Path(str(path) + '.reveal.sqlite')
        self.journal = EvidenceJournal(path, create=create)
        self.uncertain = False
        try:
            if create:
                self.journal.append(SCHEMA, dict(kind='init', plan=asdict(plan), common=asdict(common)))
            else:
                self.journal.verify(**_checkpoint(checkpoint))
            self.trusted = dict(count=self.journal.count, head_hash=self.journal.head_hash)
            self._state()
        except BaseException:
            self.journal.close()
            raise

    def _artifacts(self, arm_id, artifacts):
        if arm_id not in self.arms or type(artifacts) is not tuple:
            raise ValueError('known arm and immutable factor artifacts required')
        if any(type(item) is not tuple or len(item) != 2 or type(item[0]) is not str for item in artifacts):
            raise ValueError('typed factor artifacts required')
        values = dict(artifacts)
        if len(values) != len(artifacts) or set(values) != set(FACTORS)-{'controller_hash'}:
            raise ValueError('complete unique arm factor artifacts required')
        for name, value in values.items():
            if _hash(value) != getattr(self.arms[arm_id], name):
                raise ValueError(f'arm {name} differs from locked identity')
        return tuple(sorted(values.items()))

    def _state(self):
        if self.uncertain:
            raise ValueError('append uncertain; independently verified restart required')
        self.journal.verify(**self.trusted)
        if self.journal.count == 0:
            raise ValueError('missing execution plan initialization')
        state = dict(outputs={}, artifacts={}, scores={}, pending=None, frozen=False,
                     reveal_checkpoint=None, outcomes_hash=None)
        for index, entry in enumerate(self.journal.entries()):
            p = entry['payload']
            if entry['kind'] != SCHEMA or type(p) is not dict:
                raise ValueError('unexpected execution entry')
            kind = p.get('kind')
            if index == 0:
                if evidence_hash(p) != evidence_hash(dict(kind='init', plan=asdict(self.plan), common=asdict(self.common))):
                    raise ValueError('execution source or plan changed')
            elif kind == 'arm_intent' and set(p) == {'kind', 'arm_id', 'artifacts'}:
                if state['pending'] or state['frozen'] or p['arm_id'] != self.order[len(state['outputs'])]:
                    raise ValueError('invalid arm intent order')
                state['artifacts'][p['arm_id']] = self._artifacts(p['arm_id'], p['artifacts'])
                state['pending'] = ('arm', p['arm_id'])
            elif kind == 'arm_result' and set(p) == {'kind', 'arm_id', 'output'}:
                if state['pending'] != ('arm', p['arm_id']) or type(p['output']) is not bytes:
                    raise ValueError('arm result differs from pending intent')
                state['outputs'][p['arm_id']] = p['output']
                state['pending'] = None
            elif kind == 'freeze' and set(p) == {'kind', 'lock_hash'}:
                if state['pending'] or state['frozen'] or freeze_outputs(self.plan, state['outputs']).digest != p['lock_hash']:
                    raise ValueError('invalid complete output freeze')
                state['frozen'] = True
            elif kind == 'reveal_ready' and set(p) == {'kind', 'checkpoint'}:
                if not state['frozen'] or state['reveal_checkpoint'] is not None:
                    raise ValueError('invalid reveal coordination')
                state['reveal_checkpoint'] = _checkpoint(p['checkpoint'])
            elif kind == 'score_intent' and set(p) == {'kind', 'arm_id', 'reveal_checkpoint', 'outcomes_hash'}:
                if (not state['frozen'] or state['pending'] or p['arm_id'] != self.order[len(state['scores'])]
                        or state['outcomes_hash'] not in (None, p['outcomes_hash'])):
                    raise ValueError('invalid paired score intent')
                state['reveal_checkpoint'], state['outcomes_hash'] = _checkpoint(p['reveal_checkpoint']), p['outcomes_hash']
                state['pending'] = ('score', p['arm_id'])
            elif kind == 'score_result' and set(p) == {'kind', 'arm_id', 'score'}:
                if state['pending'] != ('score', p['arm_id']) or type(p['score']) is not bytes:
                    raise ValueError('score differs from pending intent')
                state['scores'][p['arm_id']] = p['score']
                state['pending'] = None
            else:
                raise ValueError('unknown or invalid execution transition')
        return state

    def _append(self, payload):
        self.uncertain = True
        self.journal.append(SCHEMA, payload)
        self.trusted = dict(count=self.journal.count, head_hash=self.journal.head_hash)
        self.uncertain = False
        return self._state()

    def run_arm(self, arm_id, callback, artifacts):
        artifacts = self._artifacts(arm_id, artifacts)
        if callable_hash(callback) != self.arms[arm_id].controller_hash:
            raise ValueError('arm callback differs from locked controller')
        state = self._state()
        if arm_id in state['outputs']:
            if artifacts != state['artifacts'][arm_id]:
                raise ValueError('retry artifact mismatch')
            return state['outputs'][arm_id]
        if state['pending']:
            raise ValueError('arm attempt uncertain; cannot auto-repeat')
        if state['frozen'] or arm_id != self.order[len(state['outputs'])]:
            raise ValueError('arm differs from frozen execution schedule')
        self._append(dict(kind='arm_intent', arm_id=arm_id, artifacts=artifacts))
        result = callback(ArmRequest(arm_id, self.plan.digest, self.common, artifacts))
        if type(result) is not bytes:
            raise ValueError('arm output must be exact bytes; attempt uncertain')
        self._append(dict(kind='arm_result', arm_id=arm_id, output=result))
        return result

    def freeze(self):
        state = self._state()
        if state['pending']:
            raise ValueError('uncertain attempt cannot freeze')
        lock = freeze_outputs(self.plan, state['outputs'])
        if not state['frozen']:
            self._append(dict(kind='freeze', lock_hash=lock.digest))
        return dict(state['outputs'])

    def reveal_and_score(self, load_outcomes, scorer, *, authorized=False, reveal_checkpoint=None):
        if authorized is not True:
            raise ValueError('explicit reveal authorization required')
        if callable_hash(scorer) != self.plan.scorer_hash:
            raise ValueError('scorer differs from locked identity')
        state = self._state()
        if len(state['scores']) == len(self.order):
            self._verify_reveal(state['reveal_checkpoint'], state['outputs'])
            return dict(state['scores'])
        if state['pending']:
            raise ValueError('attempt uncertain; cannot automatically repeat')
        outputs = self.freeze()
        state = self._state()
        checkpoint = reveal_checkpoint if reveal_checkpoint is not None else state['reveal_checkpoint']
        if self.reveal_path.exists():
            if checkpoint is None:
                raise ValueError('existing reveal requires independent checkpoint')
            self._verify_reveal(checkpoint, outputs)
            reveal = RevealLedger(self.reveal_path, self.plan, checkpoint=checkpoint)
        else:
            if checkpoint is not None:
                raise ValueError('coordinated reveal ledger missing')
            reveal = RevealLedger(self.reveal_path, self.plan, outputs=outputs, create=True)
        try:
            if state['reveal_checkpoint'] is None:
                self._append(dict(kind='reveal_ready', checkpoint=reveal.checkpoint()))
            outcomes = reveal.reveal(load_outcomes, authorized=True)
            completed_checkpoint = reveal.checkpoint()
        finally:
            reveal.close()
        for arm_id in self.order:
            state = self._state()
            if arm_id in state['scores']:
                continue
            self._verify_reveal(completed_checkpoint, outputs)
            self._append(dict(kind='score_intent', arm_id=arm_id,
                              reveal_checkpoint=completed_checkpoint, outcomes_hash=_hash(outcomes)))
            score = scorer(ScoreRequest(arm_id, outputs[arm_id], outcomes,
                                        self.common.partition, self.common.exclusions))
            if type(score) is not bytes:
                raise ValueError('score must be exact bytes; attempt uncertain')
            self._verify_reveal(completed_checkpoint, outputs)
            self._append(dict(kind='score_result', arm_id=arm_id, score=score))
        self._verify_reveal(completed_checkpoint, outputs)
        return dict(self._state()['scores'])

    def _verify_reveal(self, checkpoint, outputs):
        """Re-read retained evidence; callbacks may have changed a second handle."""
        witness = EvidenceJournal(self.reveal_path)
        try:
            witness.verify(**_checkpoint(checkpoint))
            first = next(witness.entries())['payload']
            if freeze_outputs(self.plan, first['outputs']).digest != freeze_outputs(self.plan, outputs).digest:
                raise ValueError('reveal output lock belongs to another execution')
        finally:
            witness.close()

    def checkpoint(self):
        self._state()
        return dict(self.trusted)

    def close(self):
        self.journal.close()
