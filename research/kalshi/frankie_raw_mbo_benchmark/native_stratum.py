"""Section 3 of the native calculation contract, as a function rather than a sentence.

`per_event.py` exists because the no-average rule had been written in the docs since S80,
re-derived by hand in S108, S111 and S113, and still got broken. This module is the same
move for the raw-MBO calculation contract's parallel-view rule.

Section 3 requires every average to declare nine things, forbids pooling across families,
subfamilies, sides, sessions, phases, continuity segments, cluster identities, chain
signatures, causal clocks and source days, and says counts, rates, quantiles, survival
curves, ratios of sums and paired differences "are not silently called arithmetic means".

Here that is structural. A `StratumKey` carries the non-poolable identity, so combining two
strata is a type error rather than an oversight. A `DeclaredAverage` cannot be constructed
without its numerator formula, population, cutoff, status and missingness rule. Every
distribution keeps exact `n`, `min`, `max` and quantiles, because section 4.5 states that a
mean alone cannot expose a heavy tail. Where a bound forces approximation, the accumulator
records that it approximated rather than quietly returning a number that looks exact.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

EXACT_QUANTILE_CAP = 50_000
QUANTILE_BASIS_EXACT = "EXACT_ALL_VALUES"
QUANTILE_BASIS_RESERVOIR = "BOUNDED_RESERVOIR_SAMPLE"
COMPLEMENTARY = "COMPLEMENTARY_SCOPE_DIFFERENCE"

RESOLVED = "RESOLVED"
CENSORED = "CENSORED"
STILL_OPEN = "STILL_OPEN"
VALID_STATUS = frozenset({RESOLVED, CENSORED, STILL_OPEN})


class StratumError(ValueError):
    """A parallel-view rule was violated."""


CLUSTERING_NOT_RUN = "NO_CLUSTERING_D5"
"""The declared value of `cluster_version` when no clustering was frozen for a run.

D-14. Contract section 3 requires every average to declare family, subfamily AND cluster
version. `cluster_version` defaulted to the empty string and only 84 rows - 4.16's - ever set
it, so 16,209 of 16,293 averaged rows declared nothing. An empty string is not a statement
that clustering did not run; it is the absence of a statement, and the two are exactly what
this contract exists to keep apart. So the default is a DECLARATION, and the empty string is
refused outright.
"""


@dataclass(frozen=True, order=True)
class StratumKey:
    """The identity an average may never be pooled across.

    Every field here appears in section 3's prohibition list. Equality and hashing are
    structural, so two observations land in the same accumulator only when every
    non-poolable dimension agrees.
    """

    source_day: str
    source_role: str
    continuity_segment: int
    family_id: str
    side_orientation: str
    session_phase: str
    clock: str
    subfamily_id: str = ""
    cluster_version: str = CLUSTERING_NOT_RUN
    chain_signature: str = ""

    def __post_init__(self) -> None:
        # D-14. `cluster_version` joins the mandatory six. It is not in the loop below
        # because its FAILURE mode is different: the others were never silently empty, while
        # this one was empty on 99.5% of rows and passed every gate.
        if not isinstance(self.cluster_version, str) or not self.cluster_version:
            raise StratumError(
                "StratumKey.cluster_version must be a declaration; pass CLUSTERING_NOT_RUN "
                "when no clustering was frozen, never the empty string"
            )
        for name in ("source_day", "source_role", "family_id", "side_orientation", "session_phase", "clock"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise StratumError(f"StratumKey.{name} must be a non-empty string")
        if not isinstance(self.continuity_segment, int) or isinstance(self.continuity_segment, bool):
            raise StratumError("StratumKey.continuity_segment must be an int")
        if self.continuity_segment < 0:
            raise StratumError("StratumKey.continuity_segment must be non-negative")

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_day": self.source_day,
            "source_role": self.source_role,
            "continuity_segment": self.continuity_segment,
            "family_id": self.family_id,
            "subfamily_id": self.subfamily_id,
            "side_orientation": self.side_orientation,
            "session_phase": self.session_phase,
            "clock": self.clock,
            "cluster_version": self.cluster_version,
            "chain_signature": self.chain_signature,
        }


@dataclass(frozen=True)
class Declaration:
    """Section 3's nine mandatory declarations, minus the six carried by StratumKey."""

    numerator_formula: str
    population: str
    causal_cutoff: str
    status: str
    missingness_rule: str

    def __post_init__(self) -> None:
        for name in ("numerator_formula", "population", "causal_cutoff", "missingness_rule"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise StratumError(f"Declaration.{name} is mandatory and must be non-empty")
        if self.status not in VALID_STATUS:
            raise StratumError(f"Declaration.status must be one of {sorted(VALID_STATUS)}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "numerator_formula": self.numerator_formula,
            "population": self.population,
            "causal_cutoff": self.causal_cutoff,
            "status": self.status,
            "missingness_rule": self.missingness_rule,
        }


def _quantile(sorted_values: Sequence[float], p: float) -> float | None:
    """Nearest-rank quantile, matching `per_event._q` so two desks report the same number."""
    if not sorted_values:
        return None
    return sorted_values[int(p * (len(sorted_values) - 1))]


class StreamingDistribution:
    """Exact n/sum/min/max always; quantiles exact until a declared bound is crossed.

    Section 4.5 requires empirical quantiles and maxima "because a mean alone cannot expose
    a heavy tail". Retaining every value across every stratum of a 4.26M-group stream is not
    bounded, so past `exact_cap` this switches to a reservoir sample and says so in
    `quantile_basis`. `n`, `sum`, `minimum` and `maximum` are never approximated - the
    maximum in particular is the heavy-tail evidence and is tracked directly.
    """

    def __init__(self, *, exact_cap: int = EXACT_QUANTILE_CAP, seed: int = 0) -> None:
        if exact_cap <= 0:
            raise StratumError("exact_cap must be positive")
        self._exact_cap = exact_cap
        self._values: list[float] = []
        self._rng = random.Random(seed)
        self._seed = seed
        self.n = 0
        self.total = 0.0
        self.minimum: float | None = None
        self.maximum: float | None = None
        self._sum_squares = 0.0

    def add(self, value: float) -> None:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            raise StratumError("distribution values must be numeric and non-NaN; count missing separately")
        value = float(value)
        self.n += 1
        self.total += value
        self._sum_squares += value * value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)
        if len(self._values) < self._exact_cap:
            self._values.append(value)
            return
        index = self._rng.randrange(self.n)
        if index < self._exact_cap:
            self._values[index] = value

    @property
    def quantile_basis(self) -> str:
        return QUANTILE_BASIS_EXACT if self.n <= self._exact_cap else QUANTILE_BASIS_RESERVOIR

    def as_dict(self) -> dict[str, Any]:
        ordered = sorted(self._values)
        return {
            "n": self.n,
            "sum": self.total,
            # D60: `_sum_squares` is maintained on EVERY add and was emitted nowhere - the
            # dispersion of every stratum computed and thrown away at no saving. Emitted raw
            # rather than as a variance, because a variance is a summary and this is the
            # quantity it would be summarized from.
            "sum_of_squares": self._sum_squares,
            "arithmetic_mean": (self.total / self.n) if self.n else None,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "p10": _quantile(ordered, 0.10),
            "p50": _quantile(ordered, 0.50),
            "p90": _quantile(ordered, 0.90),
            "p99": _quantile(ordered, 0.99),
            "quantile_basis": self.quantile_basis,
            "quantile_sample_size": len(ordered),
            "quantile_reservoir_seed": self._seed if self.quantile_basis == QUANTILE_BASIS_RESERVOIR else None,
        }


class RatioPair:
    """Section 4.8's coequal pair: mean of member ratios, and ratio of aggregate sums.

    They answer different questions, so neither substitutes for the other and their
    difference is labeled rather than reconciled. Members whose denominator is zero are
    excluded from the mean but still counted, because dropping them silently is what makes
    a ratio look better-supported than it is.
    """

    def __init__(self, *, exact_cap: int = EXACT_QUANTILE_CAP, seed: int = 0) -> None:
        self.member_ratios = StreamingDistribution(exact_cap=exact_cap, seed=seed)
        self.numerator_total = 0.0
        self.denominator_total = 0.0
        self.zero_denominator_members = 0
        self.indeterminate_members = 0

    def add(self, numerator: float, denominator: float) -> None:
        self.numerator_total += float(numerator)
        self.denominator_total += float(denominator)
        if denominator == 0:
            self.zero_denominator_members += 1
            return
        self.member_ratios.add(float(numerator) / float(denominator))

    def add_indeterminate(self) -> None:
        self.indeterminate_members += 1

    def as_dict(self) -> dict[str, Any]:
        aggregate = (self.numerator_total / self.denominator_total) if self.denominator_total else None
        member_mean = self.member_ratios.as_dict()["arithmetic_mean"]
        difference = None
        if aggregate is not None and member_mean is not None:
            difference = member_mean - aggregate
        return {
            "mean_of_member_ratios": member_mean,
            "member_ratio_distribution": self.member_ratios.as_dict(),
            "ratio_of_aggregate_sums": aggregate,
            "numerator_total": self.numerator_total,
            "denominator_total": self.denominator_total,
            "zero_denominator_members": self.zero_denominator_members,
            "indeterminate_members": self.indeterminate_members,
            "difference": difference,
            "difference_label": COMPLEMENTARY,
            "coequal": True,
        }


class SurvivalAccumulator:
    """Kaplan-Meier with at-risk counts at every time, per section 4.6.

    Section 4.6 forbids an arithmetic mean for time-to-exit under censoring and requires "a
    declared survival/hazard estimator ... with at-risk counts at every time". Censored and
    still-open observations enter the risk set and leave it without an event, so they lower
    the at-risk denominator instead of being discarded.
    """

    ESTIMATOR = "KAPLAN_MEIER_PRODUCT_LIMIT"

    def __init__(self) -> None:
        self._events: dict[float, int] = {}
        self._censored: dict[float, int] = {}
        self.observed_events = 0
        self.censored_observations = 0

    def add(self, time_to_exit: float, *, event_observed: bool) -> None:
        if time_to_exit < 0:
            raise StratumError("time_to_exit must be non-negative")
        bucket = self._events if event_observed else self._censored
        bucket[float(time_to_exit)] = bucket.get(float(time_to_exit), 0) + 1
        if event_observed:
            self.observed_events += 1
        else:
            self.censored_observations += 1

    @property
    def total_observations(self) -> int:
        return self.observed_events + self.censored_observations

    def curve(self) -> list[dict[str, Any]]:
        times = sorted(set(self._events) | set(self._censored))
        at_risk = self.total_observations
        survival = 1.0
        rows: list[dict[str, Any]] = []
        for time_point in times:
            events = self._events.get(time_point, 0)
            censored = self._censored.get(time_point, 0)
            if at_risk > 0 and events:
                survival *= 1.0 - (events / at_risk)
            rows.append(
                {
                    "time": time_point,
                    "at_risk": at_risk,
                    "events": events,
                    "censored": censored,
                    "survival": survival,
                }
            )
            at_risk -= events + censored
        return rows

    def as_dict(self) -> dict[str, Any]:
        return {
            "estimator": self.ESTIMATOR,
            "observed_events": self.observed_events,
            "censored_observations": self.censored_observations,
            "total_observations": self.total_observations,
            "curve": self.curve(),
            "arithmetic_mean_forbidden": "section 4.6: censored time-to-exit uses a survival estimator",
        }


@dataclass
class StratifiedMeasure:
    """One declared measure accumulated independently within every stratum.

    Nothing here can merge two `StratumKey` values, which is the point: pooling becomes
    something you would have to write on purpose rather than something you forget not to do.
    """

    name: str
    declaration: Declaration
    kind: str = "DISTRIBUTION"
    exact_cap: int = EXACT_QUANTILE_CAP
    seed: int = 0
    _strata: dict[StratumKey, Any] = field(default_factory=dict, init=False, repr=False)
    _excluded: dict[StratumKey, int] = field(default_factory=dict, init=False, repr=False)

    _KINDS = ("DISTRIBUTION", "RATIO_PAIR", "SURVIVAL")

    def __post_init__(self) -> None:
        if self.kind not in self._KINDS:
            raise StratumError(f"kind must be one of {self._KINDS}")

    def _accumulator(self, key: StratumKey) -> Any:
        if not isinstance(key, StratumKey):
            raise StratumError("observations must be keyed by a StratumKey")
        if key not in self._strata:
            if self.kind == "DISTRIBUTION":
                self._strata[key] = StreamingDistribution(exact_cap=self.exact_cap, seed=self.seed)
            elif self.kind == "RATIO_PAIR":
                self._strata[key] = RatioPair(exact_cap=self.exact_cap, seed=self.seed)
            else:
                self._strata[key] = SurvivalAccumulator()
        return self._strata[key]

    def observe(self, key: StratumKey, *args: Any, **kwargs: Any) -> None:
        self._accumulator(key).add(*args, **kwargs)

    def observe_indeterminate(self, key: StratumKey) -> None:
        accumulator = self._accumulator(key)
        if not isinstance(accumulator, RatioPair):
            raise StratumError("indeterminate members are only defined for a RATIO_PAIR measure")
        accumulator.add_indeterminate()

    def exclude_missing(self, key: StratumKey, count: int = 1) -> None:
        """Record a member the measure could not use, per declaration 9."""
        self._accumulator(key)
        self._excluded[key] = self._excluded.get(key, 0) + count

    def rows(self) -> list[dict[str, Any]]:
        """One row per stratum, each carrying its full identity and declarations."""
        rows = []
        for key in sorted(self._strata):
            rows.append(
                {
                    "measure": self.name,
                    "kind": self.kind,
                    "stratum": key.as_dict(),
                    "declaration": self.declaration.as_dict(),
                    "excluded_missing_members": self._excluded.get(key, 0),
                    "value": self._strata[key].as_dict(),
                }
            )
        return rows

    @property
    def stratum_count(self) -> int:
        return len(self._strata)


def cross_day_synthesis(
    measure: StratifiedMeasure,
    *,
    justification: str,
) -> dict[str, Any]:
    """Section 3's guarded cross-day view.

    Permitted "only after every day-level result remains present", so the per-day rows are
    carried inside the synthesis rather than replaced by it, and the result is explicitly
    labeled non-primary. This deliberately reports no pooled scalar: commensurability is a
    judgement the caller must argue in `justification`, and a pooled number printed here
    would be quoted without it.
    """
    if not justification.strip():
        raise StratumError("a cross-day synthesis must state why the populations are commensurable")
    rows = measure.rows()
    days = sorted({row["stratum"]["source_day"] for row in rows})
    return {
        "measure": measure.name,
        "view": "CROSS_DAY_SYNTHESIS",
        "primary": False,
        "source_days": days,
        "commensurability_justification": justification,
        "per_day_rows_retained": rows,
        "pooled_scalar": None,
        "pooled_scalar_withheld_because": (
            "section 3 forbids pooling across source days in the primary view; a scalar here "
            "would be quoted without its commensurability argument"
        ),
    }
