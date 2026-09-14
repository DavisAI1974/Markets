"""Single-writer durable reveal intent; an uncertain attempt is never repeated."""
from dataclasses import asdict

try:
    from .c15_journal import EvidenceJournal, evidence_hash
    from .experiment_locks import ExperimentPlan, freeze_outputs
except ImportError:
    from c15_journal import EvidenceJournal, evidence_hash
    from experiment_locks import ExperimentPlan, freeze_outputs

SCHEMA = 'BOSS_EXPERIMENT_REVEAL_V1'


class RevealLedger:
    def __init__(self, path, plan, *, outputs=None, create=False, checkpoint=None):
        if type(plan) is not ExperimentPlan or type(create) is not bool:
            raise ValueError('typed plan and explicit create flag required')
        if create:
            if checkpoint is not None:
                raise ValueError('new ledger cannot use a checkpoint')
            lock = freeze_outputs(plan, outputs)
        elif outputs is not None or type(checkpoint) is not dict or set(checkpoint) != {'count', 'head_hash'}:
            raise ValueError('restore requires exact trusted checkpoint')
        self._plan = plan
        self._journal = EvidenceJournal(path, create=create)
        self._uncertain = False
        self._phase = 'empty'
        self._result = None
        try:
            if create:
                # Canonical roster order also makes the retained ledger deterministic.
                self._journal.append(SCHEMA, dict(kind='lock', plan=asdict(plan),
                    outputs={name: outputs[name] for name, _ in lock.outputs}, lock_hash=lock.digest))
            else:
                self._journal.verify(**checkpoint)
            self._trusted = dict(count=self._journal.count, head_hash=self._journal.head_hash)
            self._verify()
        except BaseException:
            self._journal.close()
            raise

    def _verify(self):
        if self._uncertain:
            raise ValueError('journal append uncertain; restore from independently verified checkpoint')
        self._journal.verify(**self._trusted)
        phase, lock_hash, result = 'empty', None, None
        for entry in self._journal.entries():
            p = entry['payload']
            if entry['kind'] != SCHEMA or type(p) is not dict:
                raise ValueError('unexpected reveal ledger entry')
            if phase == 'empty':
                if (set(p) != {'kind', 'plan', 'outputs', 'lock_hash'} or p['kind'] != 'lock'
                        or evidence_hash(p['plan']) != evidence_hash(asdict(self._plan))):
                    raise ValueError('reveal plan mismatch')
                lock_hash = freeze_outputs(self._plan, p['outputs']).digest
                if lock_hash != p['lock_hash']:
                    raise ValueError('output lock mismatch')
                phase = 'locked'
            elif phase == 'locked':
                if p != dict(kind='intent', lock_hash=lock_hash):
                    raise ValueError('invalid reveal intent')
                phase = 'pending'
            elif phase == 'pending':
                if (set(p) != {'kind', 'lock_hash', 'outcomes'} or p['kind'] != 'result'
                        or p['lock_hash'] != lock_hash or type(p['outcomes']) is not bytes):
                    raise ValueError('invalid reveal result')
                result, phase = p['outcomes'], 'complete'
            else:
                raise ValueError('reveal already complete')
        if phase == 'empty':
            raise ValueError('missing output lock')
        self._phase, self._lock_hash, self._result = phase, lock_hash, result

    def _append(self, payload):
        self._uncertain = True
        self._journal.append(SCHEMA, payload)
        self._trusted = dict(count=self._journal.count, head_hash=self._journal.head_hash)
        self._uncertain = False
        self._verify()

    def reveal(self, load_outcomes, *, authorized=False):
        """Require explicit run authorization, persist intent, then invoke once.

        Loader failures leave an irreversible pending intent. No automatic retry or
        administrative trust adoption is supplied. A local ledger cannot guarantee
        exactly-once external access; the pending state exposes that uncertainty.
        """
        if authorized is not True:
            raise ValueError('explicit reveal authorization required')
        self._verify()
        if self._phase == 'complete':
            return self._result
        if self._phase == 'pending':
            raise ValueError('reveal outcome uncertain; cannot reopen outcomes')
        if not callable(load_outcomes):
            raise ValueError('outcome loader required')
        self._append(dict(kind='intent', lock_hash=self._lock_hash))
        result = load_outcomes()
        if type(result) is not bytes:
            raise ValueError('outcome loader must return exact bytes; reveal is uncertain')
        self._append(dict(kind='result', lock_hash=self._lock_hash, outcomes=result))
        return result

    def checkpoint(self):
        self._verify()
        return dict(self._trusted)

    def close(self):
        self._journal.close()
