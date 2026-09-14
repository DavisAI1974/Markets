"""Explicit-cadence updates for every registered target; no clock or feed service."""
from dataclasses import dataclass

try:
    from .forecast_contract import HashedContract, sha256_digest
    from .rolling_forecast import ForecastTarget, RefreshIntent, select_candidate
except ImportError:
    from forecast_contract import HashedContract, sha256_digest
    from rolling_forecast import ForecastTarget, RefreshIntent, select_candidate


@dataclass(frozen=True, slots=True)
class RefreshPolicy(HashedContract):
    # Inclusive maximum remaining horizon, minimum interval, both integer ns.
    bands: tuple[tuple[int, int], ...]

    def __post_init__(self):
        if type(self.bands) is not tuple or not self.bands:
            raise ValueError('explicit cadence bands required')
        previous_horizon = previous_interval = 0
        for band in self.bands:
            if (type(band) is not tuple or len(band) != 2 or
                    any(type(v) is not int or v <= 0 for v in band)):
                raise ValueError('cadence bands require positive integer nanoseconds')
            horizon, interval = band
            if horizon <= previous_horizon or interval < previous_interval:
                raise ValueError('horizons must increase and nearer cadence must be at least as frequent')
            previous_horizon, previous_interval = band

    def interval(self, remaining_ns):
        if type(remaining_ns) is not int or remaining_ns <= 0:
            raise ValueError('positive remaining horizon required')
        for maximum, interval in self.bands:
            if remaining_ns <= maximum:
                return interval
        raise ValueError('forecast horizon is not covered by the declared cadence')


class ForecastRefreshLoop:
    """Caller supplies trusted source state and a native candidate producer.

Material updates refresh every unexpired target regardless of cadence. Each target
commits separately: a later producer failure does not roll back earlier published
forecasts. Retry returns matching committed revisions without generating them again.
    The caller, not this module, decides what is material and when to supply data.
    generation_hash must bind actual model weights, ranker and generation settings,
    not merely a human version label; the native integration owns that computation.
"""

    def __init__(self, book, targets, policy):
        if (type(targets) is not tuple or not targets or
                any(not isinstance(t, ForecastTarget) for t in targets)):
            raise ValueError('nonempty immutable target registry required')
        keys = tuple((t.instrument, t.target_id) for t in targets)
        if len(set(keys)) != len(keys) or not isinstance(policy, RefreshPolicy):
            raise ValueError('unique target identities and typed refresh policy required')
        self.book, self.targets, self.policy = book, targets, policy

    def update(self, *, as_of, source_as_of, source_hash, arm_hash, generation_hash,
               produce, material=False):
        if (type(as_of) is not int or type(source_as_of) is not int or
                source_as_of > as_of or type(material) is not bool or not callable(produce)):
            raise ValueError('causal integer cutoffs, material flag and producer required')
        sha256_digest(source_hash, 'source_hash')
        sha256_digest(arm_hash, 'arm_hash')
        sha256_digest(generation_hash, 'generation_hash')
        active = [(target, self.policy.interval(target.target_ns-as_of))
                  for target in self.targets if target.target_ns > as_of]
        due, completed = [], []
        # Preflight all horizons before any producer call or durable write.
        for target, interval in active:
            last = self.book.latest(target, arm_hash=arm_hash)
            if last is not None and last.selected.as_of > as_of:
                raise ValueError('update as-of precedes a published revision')
            if last is not None and last.selected.as_of == as_of:
                if (last.selected.source_as_of != source_as_of or
                        last.selected.source_hash != source_hash or
                        last.refresh_policy_hash != self.policy.digest or
                        last.generation_hash != generation_hash):
                    raise ValueError('same as-of refresh has changed source or policy')
                completed.append(last)
            elif last is None or material or as_of-last.selected.as_of >= interval:
                due.append(target)
        self.book.bind_refresh(RefreshIntent(
            as_of, source_as_of, source_hash, arm_hash, generation_hash,
            self.policy.digest, material,
            tuple(sorted(self.targets, key=lambda t: (t.instrument, t.target_id)))))
        for target in due:
            candidates = produce(target=target, as_of=as_of, source_as_of=source_as_of,
                                 source_hash=source_hash, arm_hash=arm_hash)
            selected = select_candidate(candidates)
            if (selected.target != target or selected.as_of != as_of or
                    selected.source_as_of != source_as_of or selected.source_hash != source_hash or
                    selected.arm_hash != arm_hash):
                raise ValueError('producer forecast differs from requested target or source state')
            completed.append(self.book.publish(candidates, refresh_policy_hash=self.policy.digest,
                                                generation_hash=generation_hash))
        return tuple(sorted(completed, key=lambda p: (p.selected.target.target_ns,
                                                       p.selected.target.instrument,
                                                       p.selected.target.target_id)))
