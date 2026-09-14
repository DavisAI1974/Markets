"""Best-candidate publication and append-only rolling forecast revisions.

Forecast artifacts must already be validated by their producing contract. This
layer preserves their exact bytes; it neither generates forecasts nor interprets
their domain-specific contents. All clocks are integer UTC nanoseconds.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

try:
    from .c15_journal import EvidenceJournal, evidence_hash
    from .forecast_contract import HashedContract, finite_number, sha256_digest, unique_names
except ImportError:
    from c15_journal import EvidenceJournal, evidence_hash
    from forecast_contract import HashedContract, finite_number, sha256_digest, unique_names

SCHEMA = 'BOSS_ROLLING_FORECAST_V1'
REFRESH_SCHEMA = 'BOSS_FORECAST_REFRESH_INTENT_V1'


@dataclass(frozen=True, slots=True)
class ForecastTarget(HashedContract):
    instrument: str
    target_id: str
    target_ns: int

    def __post_init__(self):
        unique_names((self.instrument,), 'instrument')
        unique_names((self.target_id,), 'target_id')
        if type(self.target_ns) is not int:
            raise ValueError('target_ns must be integer nanoseconds')


@dataclass(frozen=True, slots=True)
class RefreshIntent(HashedContract):
    as_of: int
    source_as_of: int
    source_hash: str
    arm_hash: str
    generation_hash: str
    refresh_policy_hash: str
    material: bool
    targets: tuple[ForecastTarget, ...]

    def __post_init__(self):
        if (type(self.as_of) is not int or type(self.source_as_of) is not int or
                self.source_as_of > self.as_of or type(self.material) is not bool):
            raise ValueError('causal integer cutoffs and boolean material flag required')
        for name in ('source_hash', 'arm_hash', 'generation_hash', 'refresh_policy_hash'):
            sha256_digest(getattr(self, name), name)
        if (type(self.targets) is not tuple or not self.targets or
                any(not isinstance(t, ForecastTarget) for t in self.targets)):
            raise ValueError('immutable full refresh target registry required')
        keys = tuple((t.instrument, t.target_id) for t in self.targets)
        if len(set(keys)) != len(keys) or keys != tuple(sorted(keys)):
            raise ValueError('refresh target registry must be unique and canonical')


@dataclass(frozen=True, slots=True)
class ForecastCandidate(HashedContract):
    candidate_id: str
    target: ForecastTarget
    as_of: int
    source_as_of: int
    source_hash: str
    arm_hash: str
    model_hash: str
    forecast_artifact: bytes
    score: float | None
    ranker_hash: str | None
    ranking_policy_hash: str | None

    def __post_init__(self):
        unique_names((self.candidate_id,), 'candidate_id')
        if not isinstance(self.target, ForecastTarget):
            raise ValueError('typed forecast target required')
        if (type(self.as_of) is not int or type(self.source_as_of) is not int or
                self.source_as_of > self.as_of or self.as_of >= self.target.target_ns):
            raise ValueError('source cutoff <= as-of < target required')
        for name in ('source_hash', 'arm_hash', 'model_hash'):
            sha256_digest(getattr(self, name), name)
        if type(self.forecast_artifact) is not bytes or not self.forecast_artifact:
            raise ValueError('nonempty immutable forecast artifact bytes required')
        if self.score is None:
            if self.ranker_hash is not None or self.ranking_policy_hash is not None:
                raise ValueError('missing score must have absent ranker identities')
        else:
            finite_number(self.score, 'score')
            sha256_digest(self.ranker_hash, 'ranker_hash')
            sha256_digest(self.ranking_policy_hash, 'ranking_policy_hash')

    @property
    def comparison_key(self):
        return (self.target, self.as_of, self.source_as_of, self.source_hash,
                self.arm_hash, self.ranker_hash, self.ranking_policy_hash)


def select_candidate(candidates):
    """Use the sole valid candidate, or maximum comparable score; no score floor."""
    if type(candidates) is not tuple or not candidates:
        raise ValueError('nonempty immutable candidate set required')
    if any(not isinstance(c, ForecastCandidate) for c in candidates):
        raise ValueError('typed forecast candidates required')
    unique_names(tuple(c.candidate_id for c in candidates), 'candidate ids')
    if len(candidates) == 1:
        return candidates[0]
    if any(c.score is None or c.comparison_key != candidates[0].comparison_key for c in candidates):
        raise ValueError('multiple candidates require comparable scores, source, target and arm')
    return min(candidates, key=lambda c: (-c.score, c.candidate_id))


@dataclass(frozen=True, slots=True)
class PublishedForecast:
    selected: ForecastCandidate
    revision: int
    previous_hash: str | None
    receipt_hash: str
    request_hash: str
    refresh_policy_hash: str | None
    generation_hash: str | None

    @property
    def remaining_ns(self):
        return self.selected.target.target_ns - self.selected.as_of


class RollingForecastBook:
    """Single-writer publication ledger, separate from the C15 input journal.

The returned publication is available only after its complete candidate set is
durably appended. Restore requires a trusted count/head checkpoint, not just a
self-consistent database. External delivery/acknowledgement is a separate layer.
"""

    def __init__(self, path, *, create=False, checkpoint=None):
        if (type(create) is not bool or (create and checkpoint is not None)
                or (not create and checkpoint is None)):
            raise ValueError('create a new ledger or supply a trusted checkpoint')
        self.journal = EvidenceJournal(path, create=create)
        self._latest = {}
        self._requests = {}
        self._targets = {}
        self._refresh_locks = {}
        self._failed = False
        try:
            if checkpoint is not None:
                if (type(checkpoint) is not dict or
                        set(checkpoint) != {'schema', 'count', 'head_hash'} or
                        checkpoint['schema'] != SCHEMA or
                        type(checkpoint['count']) is not int or checkpoint['count'] < 0):
                    raise ValueError('invalid forecast checkpoint')
                sha256_digest(checkpoint['head_hash'], 'checkpoint head_hash')
                self.journal.verify(count=checkpoint['count'], head_hash=checkpoint['head_hash'])
                for entry in self.journal.entries():
                    self._replay(entry)
        except Exception:
            self.journal.close()
            raise

    @staticmethod
    def _stream(candidate):
        return candidate.arm_hash, candidate.target.digest

    @staticmethod
    def _request(candidates, refresh_policy_hash, generation_hash):
        return dict(schema=SCHEMA,
                    refresh_policy_hash=refresh_policy_hash,
                    generation_hash=generation_hash,
                    candidates=tuple(asdict(c) for c in sorted(candidates, key=lambda c: c.candidate_id)))

    def _prepare(self, candidates, refresh_policy_hash=None, generation_hash=None):
        if refresh_policy_hash is not None:
            sha256_digest(refresh_policy_hash, 'refresh_policy_hash')
        if generation_hash is not None:
            sha256_digest(generation_hash, 'generation_hash')
        selected = select_candidate(candidates)
        target_key = (selected.arm_hash, selected.target.instrument, selected.target.target_id)
        if target_key in self._targets and self._targets[target_key] != selected.target:
            raise ValueError('an existing target identity cannot move to a different time')
        stream = self._stream(selected)
        intent = stream + (selected.as_of,)
        request = self._request(candidates, refresh_policy_hash, generation_hash)
        request_hash = evidence_hash(request)
        if intent in self._requests:
            old = self._requests[intent]
            if old.request_hash != request_hash:
                raise ValueError('same as-of revision has changed candidates or settings')
            return old, None
        previous = self._latest.get(stream)
        if previous is not None and selected.as_of <= previous.selected.as_of:
            raise ValueError('cannot publish an older forecast revision')
        if previous is not None and selected.source_as_of < previous.selected.source_as_of:
            raise ValueError('source cutoff cannot regress across forecast revisions')
        payload = dict(**request, request_hash=request_hash,
                       selected_id=selected.candidate_id,
                       revision=1 if previous is None else previous.revision+1,
                       previous_hash=None if previous is None else previous.receipt_hash)
        return selected, payload

    def _remember(self, selected, payload, receipt_hash):
        result = PublishedForecast(selected, payload['revision'], payload['previous_hash'],
                                   receipt_hash, payload['request_hash'], payload['refresh_policy_hash'],
                                   payload['generation_hash'])
        stream = self._stream(selected)
        self._latest[stream] = result
        self._requests[stream + (selected.as_of,)] = result
        self._targets[(selected.arm_hash, selected.target.instrument, selected.target.target_id)] = selected.target
        return result

    def _replay(self, entry):
        payload = entry['payload']
        if entry['kind'] == REFRESH_SCHEMA:
            try:
                intent = RefreshIntent(**dict(payload, targets=tuple(
                    ForecastTarget(**t) for t in payload['targets'])))
            except (TypeError, KeyError) as exc:
                raise ValueError('malformed refresh intent') from exc
            key = (intent.arm_hash, intent.as_of)
            if key in self._refresh_locks or evidence_hash(asdict(intent)) != evidence_hash(payload):
                raise ValueError('refresh intent replay mismatch')
            self._refresh_locks[key] = intent
            return
        if entry['kind'] != SCHEMA or type(payload) is not dict:
            raise ValueError('unexpected forecast ledger entry')
        try:
            candidates = tuple(ForecastCandidate(**dict(c, target=ForecastTarget(**c['target'])))
                               for c in payload['candidates'])
            selected, expected = self._prepare(candidates, payload['refresh_policy_hash'], payload['generation_hash'])
        except (TypeError, KeyError) as exc:
            raise ValueError('malformed forecast ledger entry') from exc
        if expected is None or evidence_hash(expected) != evidence_hash(payload):
            raise ValueError('forecast ledger selection or revision mismatch')
        self._remember(selected, payload, evidence_hash(entry))

    def bind_refresh(self, intent):
        """Durably freeze the whole refresh request before any generation starts."""
        if self._failed:
            raise ValueError('publication state uncertain; restart from verified checkpoint')
        if not isinstance(intent, RefreshIntent):
            raise ValueError('typed refresh intent required')
        key = (intent.arm_hash, intent.as_of)
        previous = self._refresh_locks.get(key)
        if previous is not None:
            if previous.digest != intent.digest:
                raise ValueError('refresh intent changed after initial attempt')
            return
        self._failed = True
        self.journal.append(REFRESH_SCHEMA, asdict(intent))
        self._refresh_locks[key] = intent
        self._failed = False

    def publish(self, candidates, *, refresh_policy_hash=None, generation_hash=None):
        if self._failed:
            raise ValueError('publication state uncertain; restart from verified checkpoint')
        selected, payload = self._prepare(candidates, refresh_policy_hash, generation_hash)
        if payload is None:
            return selected
        # If storage commits then throws, do not expose or retry an uncertain write.
        self._failed = True
        receipt_hash = self.journal.append(SCHEMA, payload)
        result = self._remember(selected, payload, receipt_hash)
        self._failed = False
        return result

    def latest(self, target, *, arm_hash):
        if not isinstance(target, ForecastTarget):
            raise ValueError('typed forecast target required')
        sha256_digest(arm_hash, 'arm_hash')
        return self._latest.get((arm_hash, target.digest))

    def checkpoint(self):
        if self._failed:
            raise ValueError('publication state uncertain; restart before checkpointing')
        return dict(schema=SCHEMA, count=self.journal.count, head_hash=self.journal.head_hash)

    def close(self):
        self.journal.close()
