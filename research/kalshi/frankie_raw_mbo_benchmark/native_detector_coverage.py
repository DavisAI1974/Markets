"""Section 4.0b: detector coverage and rejection accounting - the denominator nobody carried.

**Why this exists.** The population that defines 4.10, 4.11, 4.12 and 4.16 is created by a
selection function the contract never mentioned: a trailing causal quantile of 0.85 over at
least 600 finite observations after a 900 s warm-up, a 45 s refractory, a 5 s local radius,
and causal windowed prominence. On run 33605852433 that function observed 17,991 seconds,
held 11,399 of them in warm-up, considered 4,462 second-events and promoted **91 - 2.04%**.
Every exhaustion rate in the artifact had the 91 as its denominator, and 4.11's
`detection_share = 1.0` was unfalsifiable precisely because the 4,371 it rejected lived
outside the contract, in a traversal counter block no section owned. The principal, in the
assessment for that run: *"The selection function that creates a population belongs in the
contract that governs the population."* This is that section.

**What it does and does not do.** It ACCOUNTS for the detector; it never selects. No branch
of `CausalPeakDetector` is consulted here and no flow value is ever seen - the section reads
the detector's own integer counters after every second the traversal feeds it, attributes the
change to the stratum the traversal is in, and at every segment close proves two identities:

1. **Partition.** Every judged second ended in exactly one named outcome:
   `seconds_judged == warm-up + no finite flow + the five named rejections + the release-time
   refractory + still pending + emitted`. A nonzero residual is an outcome the vocabulary does
   not name, and the section REFUSES rather than binning it as "other" - D60 applied to a
   population instead of a row.
2. **Reconciliation.** The section's per-segment totals equal the detector's own counters,
   key for key. The per-second attribution is a second reading of the same quantities, and
   a gauge that disagrees with its source is not a gauge.

**The vocabulary is the detector's, verbatim, and it is CLOSED.** A counter the detector
exposes that this module does not name refuses at `open_segment`, so a rejection path cannot
be added to the detector without also being accounted for here. No name is invented: the
five rejection reasons are the five the detector has always had, and the two the detector
gained for this section (`seconds_without_finite_flow`, `rejected_in_refractory_at_release`)
were added TO THE DETECTOR as counters on branches that already existed, because a path the
detector does not count is a path nothing can reconcile. The second of those was a real
uncounted exit, found while writing this: a peak judged at exactly `window_open + refractory`
was outside the window's group and inside the winner's shadow, and left by neither door.

**Average decision: no.** These are counts and ratios of counts. `promotion_rate` is
`candidates_emitted / considered` with both integers on the row beside it, and the
COUNT_PARTITION kind this module uses cannot form an arithmetic mean at all.

**On the stratum.** The detector searches the per-second flow substrate, which has no family
and no side - every family's trades land in the same one-second bin. So the family slot says
`ALL_FAMILIES_DETECTOR_SEARCH` and the side slot says `BOTH`, on the 4.2 principle that a row
states its own coarseness rather than leaving a blank for a reader to misread. Day, role,
segment and phase key normally. An outcome is attributed to the stratum the traversal was in
when the outcome became KNOWN: a windowed peak's fate is decided when its window closes, so a
judgement and its outcome can fall in adjacent phases at a boundary. The partition identity is
therefore exact per continuity segment - where it is asserted - and per-phase rows are a
distribution of that segment's outcomes, never a second identity.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

SECTION = "4.0b"
CAUSAL_CLOCK = "ts_recv_ns"
UNIT = "DETECTOR_SECOND"

SEARCH_FAMILY = "ALL_FAMILIES_DETECTOR_SEARCH"
"""The family slot for a search that runs over every family's flow at once.

Named rather than left blank for the reason 4.2 names its own: a blank family on a row that
legitimately spans families is indistinguishable from a blank on a row that lost one.
"""
SEARCH_SIDE = "BOTH"
"""Both polarities are searched by one bar; a rejection has no side the detector counts by."""

FED = "FED_BY_THE_TRAVERSAL"
NOT_FED = "NOT_FED_BY_THE_TRAVERSAL"

# --- the detector's accounting vocabulary, VERBATIM from `CausalPeakDetector.counters` -----
COVERAGE_COUNTERS: tuple[str, ...] = ("seconds_observed", "seconds_judged")
"""Seconds fed to the detector, and seconds whose full local window arrived and were judged."""

WINDOW_INCOMPLETE = "seconds_window_incomplete"
COVERAGE_OUTCOMES: tuple[str, ...] = ("seconds_judged", WINDOW_INCOMPLETE)
"""How the coverage row partitions SECONDS FED, so its `n` is a population and not a sum of
two overlapping counts. A fed second either produced a judgement in the same reading or it did
not; over a closed segment the second bin is exactly the first and last `local_radius` seconds,
whose local window never completes. `seconds_observed` and `seconds_judged` themselves are
reconciled against the detector at close, not re-derived from these bins.
"""

REJECTION_REASONS: tuple[str, ...] = (
    "rejected_zero_magnitude",
    "rejected_below_threshold",
    "rejected_not_local_max",
    "rejected_in_refractory",
    "rejected_in_refractory_at_release",
    "suppressed_by_prominence",
)
"""Every named way a considered second-event fails to be promoted. The detector's names."""

PROMOTED = "candidates_emitted"
NOT_CONSIDERED: tuple[str, ...] = ("seconds_in_warmup", "seconds_without_finite_flow")
"""Judged seconds on which nothing was evaluated: the bar was not yet live, or the reading was NaN."""

TERMINAL_OUTCOMES: tuple[str, ...] = NOT_CONSIDERED + REJECTION_REASONS + (PROMOTED,)
"""The closed set every judged second ends in, exactly once - plus the pending gauge below."""

PENDING_GAUGE = "candidates_pending_in_window"
"""Judged and buffered, not yet decided. A gauge, not a counter; zero after `finish()`."""

KNOWN_COUNTERS = frozenset(COVERAGE_COUNTERS + TERMINAL_OUTCOMES + (PENDING_GAUGE,))
REJECTION_PREFIXES = ("rejected_", "suppressed_")

PARTITION_FORMULA = (
    "seconds_judged == seconds_in_warmup + seconds_without_finite_flow + "
    "rejected_zero_magnitude + rejected_below_threshold + rejected_not_local_max + "
    "rejected_in_refractory + rejected_in_refractory_at_release + suppressed_by_prominence + "
    "candidates_emitted + candidates_pending_in_window"
)


class DetectorCoverageError(ValueError):
    """The detector's accounting could not be consumed lawfully."""


def _int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DetectorCoverageError(f"detector counter {name} must be an int, got {value!r}")
    if value < 0:
        raise DetectorCoverageError(f"detector counter {name} is negative: {value}")
    return value


def _ratio(numerator: int, denominator: int, formula: str) -> dict[str, Any]:
    """A rate as a ratio of two exact counts, both on the row. Never a mean of anything."""
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": (numerator / denominator) if denominator else None,
        "formula": formula,
        "basis": "RATIO_OF_EXACT_COUNTS",
    }


def derive(counts: Mapping[str, int]) -> dict[str, Any]:
    """The reading a consumer wants from one set of counts, with every denominator beside it.

    `considered` is the sum of the named outcomes a considered second can end in - never
    `searched` minus something - so it is a count, not a residual. `searched_seconds` is the
    judged seconds on which the bar was live; the principal reported it as observed minus
    warm-up, which counts the seconds that never completed a window as searched. They were
    not, and the difference is `seconds_window_never_completed`, reported beside it.
    """
    rejected_by_reason = {reason: int(counts.get(reason, 0)) for reason in REJECTION_REASONS}
    promoted = int(counts.get(PROMOTED, 0))
    pending = int(counts.get(PENDING_GAUGE, 0))
    rejected_total = sum(rejected_by_reason.values())
    considered = rejected_total + promoted + pending
    without_finite = int(counts.get("seconds_without_finite_flow", 0))
    searched = considered + without_finite
    judged = int(counts.get("seconds_judged", 0))
    observed = int(counts.get("seconds_observed", 0))
    return {
        "seconds_observed": observed,
        "seconds_judged": judged,
        "seconds_window_never_completed": observed - judged,
        "seconds_in_warmup": int(counts.get("seconds_in_warmup", 0)),
        "searched_seconds": searched,
        "seconds_without_finite_flow": without_finite,
        "considered": considered,
        "promoted": promoted,
        "candidates_pending_in_window": pending,
        "rejected_total": rejected_total,
        "rejected_by_reason": rejected_by_reason,
        "promotion_rate": _ratio(promoted, considered, "candidates_emitted / considered"),
        "searched_share_of_observed": _ratio(
            searched, observed, "searched_seconds / seconds_observed"
        ),
        "considered_share_of_searched": _ratio(
            considered, searched, "considered / searched_seconds"
        ),
        "rejection_share_by_reason": {
            reason: _ratio(count, considered, f"{reason} / considered")
            for reason, count in rejected_by_reason.items()
        },
    }


def parameter_signature(parameters: Mapping[str, Any]) -> str:
    """One string a reader can compare across runs without reading the block."""
    return json.dumps(dict(parameters), sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class _SegmentLedger:
    """What the section knows about one detector: its parameters, its last reading, its totals."""

    segment: int
    parameters: dict[str, Any]
    signature: str
    snapshot: dict[str, int]
    totals: dict[str, int] = field(default_factory=dict)
    seconds_fed: int = 0
    closed: bool = False


class DetectorCoverageCalculator:
    """Streaming section 4.0b accumulator over the candidate detector's own counters.

    One observation per second the traversal feeds the detector, attributed as a DELTA of the
    detector's counters between two readings, so the section carries exactly what the
    detector counted and nothing it invented. The `exact_cap` and `seed` arguments are
    accepted for uniform construction with every other section and are unused: a count has
    no reservoir.
    """

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        del exact_cap, seed
        population = (
            "seconds judged by the causal candidate detector within the day, role, "
            "continuity segment and session phase the traversal was in when the outcome "
            "became known; families and sides are deliberately pooled, because the search "
            "runs over every family's flow in one one-second bin"
        )
        self.outcomes = StratifiedMeasure(
            name="detector_second_outcome",
            kind="COUNT_PARTITION",
            outcomes=TERMINAL_OUTCOMES,
            declaration=Declaration(
                numerator_formula=(
                    "count of judged seconds ending in each named outcome, read as the change "
                    "in CausalPeakDetector.counters() across one observe() call"
                ),
                population=population,
                causal_cutoff=(
                    "the second the outcome became known: judgement for a rejection at the "
                    "bar, window close for a windowed release or prominence suppression"
                ),
                status=RESOLVED,
                missingness_rule=(
                    "no exclusions: every judged second ends in exactly one declared outcome "
                    "or the pending gauge, asserted per segment at close; a residual REFUSES "
                    "the run rather than becoming an unnamed bin"
                ),
            ),
        )
        self.coverage = StratifiedMeasure(
            name="detector_seconds_coverage",
            kind="COUNT_PARTITION",
            outcomes=COVERAGE_OUTCOMES,
            declaration=Declaration(
                numerator_formula=(
                    "seconds fed to the detector, partitioned into those whose full local "
                    "window had arrived and were judged in the same reading, and those whose "
                    "window was still incomplete; over a closed segment the latter are the "
                    "first and last local_radius seconds, whose window never completes"
                ),
                population=population,
                causal_cutoff="the second fed; a quiet second is fed as NaN, never skipped",
                status=RESOLVED,
                missingness_rule=(
                    "no exclusions: a second the traversal did not feed is not a second the "
                    "detector could have searched, and is absent from seconds_observed by "
                    "construction rather than counted as missing"
                ),
            ),
        )
        self._ledgers: dict[int, _SegmentLedger] = {}
        self.segments_opened = 0
        self.segments_closed = 0
        self.seconds_accounted = 0

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (self.outcomes, self.coverage)

    # --- the vocabulary check ----------------------------------------------
    @staticmethod
    def _read(detector: Any) -> dict[str, int]:
        counters = detector.counters()
        if not isinstance(counters, Mapping):
            raise DetectorCoverageError("detector.counters() must return a mapping")
        return {name: _int(value, name) for name, value in counters.items()}

    @classmethod
    def _check_vocabulary(cls, detector: Any) -> None:
        """Refuse a detector whose accounting this section cannot name, key for key.

        The refusal is the mechanism: an unnamed rejection counter would otherwise be read
        as zero here and reported as a clean partition, which is the exact shape - present,
        typed, in range and measuring nothing - this programme exists to catch.
        """
        counters = cls._read(detector)
        unknown = sorted(set(counters) - KNOWN_COUNTERS)
        if unknown:
            raise DetectorCoverageError(
                f"the detector exposes accounting this section does not name: {unknown}; "
                "name it here or it becomes an unnamed bin"
            )
        missing = sorted(KNOWN_COUNTERS - set(counters))
        if missing:
            raise DetectorCoverageError(
                f"the detector no longer exposes {missing}; the partition cannot be reconciled"
            )
        summary = detector.summary()
        stray = sorted(
            key for key in summary
            if key.startswith(REJECTION_PREFIXES) and key not in REJECTION_REASONS
        )
        if stray:
            raise DetectorCoverageError(
                f"the detector's summary names a rejection this section does not: {stray}"
            )

    def _ledger(self, detector: Any) -> _SegmentLedger:
        segment = int(detector.continuity_segment)
        ledger = self._ledgers.get(segment)
        if ledger is None:
            raise DetectorCoverageError(
                f"detector for segment {segment} was never opened; a reading with no "
                "baseline is a delta from nothing"
            )
        if ledger.closed:
            raise DetectorCoverageError(f"segment {segment} is closed; it does not reopen")
        return ledger

    # --- the pass ---------------------------------------------------------
    def open_segment(self, detector: Any) -> None:
        """Begin accounting for one detector. Called when the traversal builds it."""
        segment = int(detector.continuity_segment)
        if segment in self._ledgers:
            raise DetectorCoverageError(
                f"segment {segment} already has a detector; segments are trade-date "
                "ordinals and do not repeat within a run"
            )
        self._check_vocabulary(detector)
        parameters = dict(detector.parameters())
        self._ledgers[segment] = _SegmentLedger(
            segment=segment,
            parameters=parameters,
            signature=parameter_signature(parameters),
            snapshot=self._read(detector),
            totals={name: 0 for name in COVERAGE_COUNTERS + TERMINAL_OUTCOMES},
        )
        self.segments_opened += 1

    @staticmethod
    def _key(
        *, source_day: str, source_role: str, continuity_segment: int, session_phase: str
    ) -> StratumKey:
        return StratumKey(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=SEARCH_FAMILY,
            side_orientation=SEARCH_SIDE,
            session_phase=session_phase,
            clock=CAUSAL_CLOCK,
        )

    def _fold(
        self,
        ledger: _SegmentLedger,
        detector: Any,
        *,
        source_day: str,
        source_role: str,
        session_phase: str,
    ) -> dict[str, int]:
        """Attribute the change in the detector's counters since the last reading."""
        now = self._read(detector)
        delta: dict[str, int] = {}
        for name in COVERAGE_COUNTERS + TERMINAL_OUTCOMES:
            change = now[name] - ledger.snapshot[name]
            if change < 0:
                raise DetectorCoverageError(
                    f"detector counter {name} moved backwards ({ledger.snapshot[name]} -> "
                    f"{now[name]}); counters are monotone and a decrease is a reset nobody "
                    "declared"
                )
            delta[name] = change
        if any(delta.values()):
            key = self._key(
                source_day=source_day,
                source_role=source_role,
                continuity_segment=ledger.segment,
                session_phase=session_phase,
            )
            for name in TERMINAL_OUTCOMES:
                if delta[name]:
                    self.outcomes.observe(key, name, delta[name])
            # The coverage row partitions seconds FED. A judgement never happens outside an
            # observe() call, so fed minus judged cannot be negative; if it is, the detector
            # judged a second nobody fed it, which is refused rather than absorbed.
            incomplete = delta["seconds_observed"] - delta["seconds_judged"]
            if incomplete < 0:
                raise DetectorCoverageError(
                    f"segment {ledger.segment}: {delta['seconds_judged']} judgements across "
                    f"{delta['seconds_observed']} fed seconds; a judgement without a fed second"
                )
            if delta["seconds_judged"]:
                self.coverage.observe(key, "seconds_judged", delta["seconds_judged"])
            if incomplete:
                self.coverage.observe(key, WINDOW_INCOMPLETE, incomplete)
            for name, change in delta.items():
                ledger.totals[name] += change
        ledger.snapshot = now
        delta[PENDING_GAUGE] = now[PENDING_GAUGE]
        return delta

    def observe_second(
        self,
        detector: Any,
        *,
        second: int,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        session_phase: str,
    ) -> dict[str, Any]:
        """Fold in what the detector decided across the second it was just fed.

        Returns the delta so a caller can see what moved, in the 4.2 shape of returning what
        was read rather than None. The traversal's segment must be the detector's: a section
        keying on one while the detector counts under another is two populations under one
        name.
        """
        ledger = self._ledger(detector)
        if int(continuity_segment) != ledger.segment:
            raise DetectorCoverageError(
                f"the traversal is in segment {continuity_segment} but the detector counts "
                f"under segment {ledger.segment}"
            )
        delta = self._fold(
            ledger, detector, source_day=source_day, source_role=source_role,
            session_phase=session_phase,
        )
        ledger.seconds_fed += 1
        self.seconds_accounted += 1
        return {"second": int(second), "continuity_segment": ledger.segment, **delta}

    def close_segment(
        self,
        detector: Any,
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        session_phase: str,
        recv_ns: int,
        occasion: str,
    ) -> dict[str, Any]:
        """Fold the releases `finish()` forced, then prove the two identities and return the row.

        Must be called AFTER the detector's `finish()`: the forced releases are the segment's
        last outcomes, and closing before them would reconcile against a detector still
        holding peaks in its buffer. The returned row is the exact evidence beneath this
        section's summary - the detector's counters, the section's totals and the verdict on
        both identities - and the caller retains it, because every other `close_*` on this
        path once returned a row that was dropped.
        """
        ledger = self._ledger(detector)
        if int(continuity_segment) != ledger.segment:
            raise DetectorCoverageError(
                f"closing segment {continuity_segment} against a detector for {ledger.segment}"
            )
        self._fold(
            ledger, detector, source_day=source_day, source_role=source_role,
            session_phase=session_phase,
        )
        now = ledger.snapshot
        # Identity 2: the per-second attribution lost nothing and invented nothing.
        disagreements = {
            name: (ledger.totals[name], now[name])
            for name in COVERAGE_COUNTERS + TERMINAL_OUTCOMES
            if ledger.totals[name] != now[name]
        }
        if disagreements:
            raise DetectorCoverageError(
                f"segment {ledger.segment}: the section's totals disagree with the detector's "
                f"counters (section, detector): {disagreements}"
            )
        # Identity 1: every judged second is in exactly one named bin or still pending.
        accounted = sum(now[name] for name in TERMINAL_OUTCOMES) + now[PENDING_GAUGE]
        residual = now["seconds_judged"] - accounted
        if residual:
            raise DetectorCoverageError(
                f"segment {ledger.segment}: {residual} judged second(s) ended in an outcome "
                f"the vocabulary does not name ({PARTITION_FORMULA}); refused rather than "
                "binned as other"
            )
        ledger.closed = True
        self.segments_closed += 1
        return {
            "section": SECTION,
            "unit": UNIT,
            "continuity_segment": ledger.segment,
            "source_day": source_day,
            "source_role": source_role,
            "session_phase_at_close": session_phase,
            "recv_ns": int(recv_ns),
            "occasion": occasion,
            "seconds_fed_to_section": ledger.seconds_fed,
            "detector_counters": dict(now),
            "section_totals": dict(ledger.totals),
            "partition_identity_holds": True,
            "partition_formula": PARTITION_FORMULA,
            "reconciled_with_detector": True,
            "detector_parameters": dict(ledger.parameters),
            "parameter_signature": ledger.signature,
            "derived": derive(now),
            "clock": CAUSAL_CLOCK,
        }

    # --- the views --------------------------------------------------------
    def _parameters_for(self, segment: int) -> tuple[dict[str, Any], str]:
        ledger = self._ledgers.get(int(segment))
        if ledger is None:  # pragma: no cover - a row cannot exist without its ledger
            raise DetectorCoverageError(f"no detector was opened for segment {segment}")
        return dict(ledger.parameters), ledger.signature

    def companion_rows(self) -> list[dict[str, Any]]:
        """One row per stratum per measure, each carrying the detector's constants and rates.

        The parameters ride ON the row rather than in the summary alone because a row is what
        gets quoted; a caveat that lives only beside it expires. Rates on an outcome row are
        ratios of that row's own counts.
        """
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            for row in measure.rows():
                parameters, signature = self._parameters_for(row["stratum"]["continuity_segment"])
                value = dict(row["value"])
                value["detector_parameters"] = parameters
                value["parameter_signature"] = signature
                if measure is self.outcomes:
                    counts = dict(value["counts"])
                    derived = derive(counts)
                    value["rates"] = {
                        "promotion_rate": derived["promotion_rate"],
                        "considered_share_of_searched": derived["considered_share_of_searched"],
                        "rejection_share_by_reason": derived["rejection_share_by_reason"],
                        "considered": derived["considered"],
                        "searched_seconds": derived["searched_seconds"],
                        "rejected_total": derived["rejected_total"],
                    }
                    value["attribution_note"] = (
                        "an outcome is counted in the stratum the traversal was in when it "
                        "became known; a windowed peak judged in one phase and released in "
                        "the next appears in the second, and the partition identity is exact "
                        "per continuity segment, not per phase"
                    )
                rows.append({**row, "value": value})
        return rows

    def summary(self) -> dict[str, Any]:
        per_segment = []
        totals = {name: 0 for name in COVERAGE_COUNTERS + TERMINAL_OUTCOMES + (PENDING_GAUGE,)}
        signatures: dict[str, dict[str, Any]] = {}
        for segment in sorted(self._ledgers):
            ledger = self._ledgers[segment]
            counters = dict(ledger.snapshot)
            for name in totals:
                totals[name] += counters.get(name, 0)
            signatures.setdefault(ledger.signature, ledger.parameters)
            per_segment.append({
                "continuity_segment": segment,
                "closed": ledger.closed,
                "seconds_fed_to_section": ledger.seconds_fed,
                "counters": counters,
                "derived": derive(counters),
                "parameter_signature": ledger.signature,
            })
        derived = derive(totals)
        uniform = len(signatures) <= 1
        return {
            "section": SECTION,
            "unit": UNIT,
            "causal_clock": CAUSAL_CLOCK,
            "status": FED if self.segments_opened else NOT_FED,
            "segments_opened": self.segments_opened,
            "segments_closed": self.segments_closed,
            "seconds_accounted": self.seconds_accounted,
            # The counts every downstream exhaustion rate is a survivor of. `promoted` is the
            # population 4.10, 4.11, 4.12 and 4.16 report on; `considered` is what it was
            # selected from; `rejected_by_reason` is the 4,371 that had no home.
            "seconds_observed": derived["seconds_observed"],
            "seconds_judged": derived["seconds_judged"],
            "seconds_window_never_completed": derived["seconds_window_never_completed"],
            "seconds_in_warmup": derived["seconds_in_warmup"],
            "searched_seconds": derived["searched_seconds"],
            "seconds_without_finite_flow": derived["seconds_without_finite_flow"],
            "considered": derived["considered"],
            "promoted": derived["promoted"],
            "candidates_pending_in_window": derived["candidates_pending_in_window"],
            "rejected_total": derived["rejected_total"],
            "rejected_by_reason": derived["rejected_by_reason"],
            "promotion_rate": derived["promotion_rate"],
            "searched_share_of_observed": derived["searched_share_of_observed"],
            "considered_share_of_searched": derived["considered_share_of_searched"],
            "rejection_share_by_reason": derived["rejection_share_by_reason"],
            "totals_note": (
                "sums of exact counts over continuity segments; not an average and not the "
                "primary view - per_segment carries each segment's own counts and the "
                "averaged companions carry them per day, role, segment and phase"
            ),
            "per_segment": per_segment,
            "parameters": next(iter(signatures.values())) if uniform and signatures else None,
            "parameters_uniform_across_segments": uniform,
            "parameter_signatures_seen": sorted(signatures),
            "partition_identity": {
                "formula": PARTITION_FORMULA,
                "asserted_at": "every segment close; a residual refuses the run",
                "segments_verified": self.segments_closed,
            },
            "vocabulary": {
                "coverage": list(COVERAGE_COUNTERS),
                "not_considered": list(NOT_CONSIDERED),
                "rejection_reasons": list(REJECTION_REASONS),
                "promoted": PROMOTED,
                "pending_gauge": PENDING_GAUGE,
                "closed": True,
            },
            "definitions": {
                "seconds_observed": "every second fed to the detector, quiet seconds as NaN",
                "seconds_judged": (
                    "seconds whose full local window arrived; the first and last "
                    "local_radius seconds of a segment never do"
                ),
                "searched_seconds": (
                    "judged seconds on which the trailing bar was live; the principal's "
                    "figure was observed minus warm-up, which counts window-building seconds "
                    "as searched - the difference is seconds_window_never_completed"
                ),
                "considered": (
                    "searched seconds with a finite reading: the sum of every named "
                    "rejection, the promoted, and the pending gauge - a count, never a "
                    "residual"
                ),
                "promoted": "candidates emitted, including window_truncated releases at a boundary",
            },
            "population_note": (
                "4.10, 4.11, 4.12 and 4.16 report on the PROMOTED set; every rate they carry "
                "has `promoted` as its denominator, and 4.11's detection_share is measured "
                "over it. `considered` and `rejected_by_reason` here are the population that "
                "set was selected from, which is what makes a detection share of 1.0 "
                "falsifiable"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
