"""Section 4.11: prebirth prediction and continuous H+N recognition.

Section 4.11 contains the sharpest prohibition in the contract: "A mean over only
successful detections must never be presented as the population detection time." That is
survivorship bias with a specific name, and it is the failure mode a detection system
produces naturally - the cases you failed to detect have no detection time, so they fall
out of the arithmetic and the remaining mean describes only the easy ones.

So there is no method here that returns a bare detection-time mean. `population_report`
always carries every outcome class with its own denominator, including missed and censored
members, and it reports the detected-only figure solely as one labelled row inside that
population - never as the answer.

The first-call rule is likewise structural. A recognition is recorded once, and a later
better-looking call is rejected rather than allowed to overwrite it, so a system cannot
improve its own record by noticing something a second time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    CENSORED,
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

CAUSAL_CLOCK = "ts_recv_ns"

PRIOR = "PRIOR"
T0 = "T0"
HORIZON = "H+N"
MISSED = "MISSED"
CENSORED_OUTCOME = "CENSORED"
DETECTED_OUTCOMES = frozenset({PRIOR, T0, HORIZON})
ALL_OUTCOMES = (PRIOR, T0, HORIZON, MISSED, CENSORED_OUTCOME)

# S121 item one: WHERE a recognition instant came from, on the record beside the instant.
# An H+N call made at `available_second` is on the candidate lane's second bin, which is
# not an F_LAST receive; a PRIOR call is the precursor finding's own instant. The basis
# travels so a reader can never mistake the one granularity for the other.
RECOGNIZED_BASIS_AVAILABLE_SECOND_BIN = "AVAILABLE_SECOND_BIN"
RECOGNIZED_BASIS_PRECURSOR_FINDING = "PRECURSOR_FINDING"


class RecognitionError(ValueError):
    """A recognition could not be recorded lawfully."""


@dataclass
class CandidateRecognition:
    """One candidate's recognition record, including the calls that failed.

    `failed_states` preserves earlier ambiguous or refuted causal states, which section 4.11
    requires: the path to a call is evidence about the call's reliability, and discarding it
    leaves a detection looking cleaner than it was.
    """

    candidate_id: str
    source_day: str
    source_role: str
    continuity_segment: int
    family_id: str
    side: str
    session_phase: str
    birth_recv_ns: int
    outcome: str | None = None
    recognized_recv_ns: int | None = None
    recognized_recv_ns_basis: str | None = None
    precursor_recv_ns: int | None = None
    failed_states: list[dict[str, Any]] = field(default_factory=list)
    superseded_attempts: int = 0

    @property
    def lead_ns(self) -> int | None:
        """Positive before birth, negative after. None when never recognized."""
        if self.recognized_recv_ns is None:
            return None
        return self.birth_recv_ns - self.recognized_recv_ns

    @property
    def detected(self) -> bool:
        return self.outcome in DETECTED_OUTCOMES

    def note_failed_state(self, *, label: str, recv_ns: int, reason: str) -> None:
        self.failed_states.append({"label": label, "recv_ns": recv_ns, "reason": reason})

    def record_call(self, *, recv_ns: int, basis: str | None = None) -> str:
        """Record the first lawful call. A later call cannot replace it.

        Section 2: "A later, better-looking recognition may not replace the first lawful
        call." Subsequent attempts are counted so the pressure to re-call is visible in the
        record rather than invisible in an improved number. `basis` says which clock the
        instant is on (see RECOGNIZED_BASIS_*); it is recorded with the first call only.
        """
        if self.outcome is not None:
            self.superseded_attempts += 1
            return self.outcome
        if recv_ns < self.birth_recv_ns:
            self.outcome = PRIOR
        elif recv_ns == self.birth_recv_ns:
            self.outcome = T0
        else:
            self.outcome = HORIZON
        self.recognized_recv_ns = recv_ns
        self.recognized_recv_ns_basis = basis
        return self.outcome

    def mark_missed(self) -> None:
        if self.outcome is not None:
            raise RecognitionError(f"candidate {self.candidate_id} already has outcome {self.outcome}")
        self.outcome = MISSED

    def mark_censored(self) -> None:
        if self.outcome is not None:
            raise RecognitionError(f"candidate {self.candidate_id} already has outcome {self.outcome}")
        self.outcome = CENSORED_OUTCOME

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_day": self.source_day,
            "source_role": self.source_role,
            "continuity_segment": self.continuity_segment,
            "family_id": self.family_id,
            "side": self.side,
            "session_phase": self.session_phase,
            "birth_recv_ns": self.birth_recv_ns,
            "outcome": self.outcome,
            "detected": self.detected,
            "recognized_recv_ns": self.recognized_recv_ns,
            "recognized_recv_ns_basis": self.recognized_recv_ns_basis,
            "precursor_recv_ns": self.precursor_recv_ns,
            "lead_ns": self.lead_ns,
            "failed_state_count": len(self.failed_states),
            "failed_states": list(self.failed_states),
            "superseded_attempts": self.superseded_attempts,
            "clock": CAUSAL_CLOCK,
        }


class RecognitionCalculator:
    """Streaming section 4.11 accumulator with the population always attached."""

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, status: str, missingness: str):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="candidates within the stratum and recognition outcome class",
                    causal_cutoff="recognition receive time on ts_recv_ns",
                    status=status,
                    missingness_rule=missingness,
                ),
                **kwargs,
            )

        self.prior_lead = measure(
            "prior_lead_ns",
            "birth - recognition, PRIOR members only",
            RESOLVED,
            "T0, H+N, missed and censored members are excluded here by construction",
        )
        self.horizon_delay = measure(
            "horizon_delay_ns",
            "recognition - birth, H+N members only",
            RESOLVED,
            "PRIOR, T0, missed and censored members are excluded here by construction",
        )
        self.failed_states = measure(
            "failed_state_count",
            "earlier ambiguous or refuted causal states before the first lawful call",
            RESOLVED,
            "every candidate contributes, including those never recognized",
        )

        self.outcome_counts: dict[str, int] = {name: 0 for name in ALL_OUTCOMES}
        self.stratum_outcomes: dict[tuple[str, ...], dict[str, int]] = {}
        self.recorded = 0
        self.superseded_attempts = 0

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (self.prior_lead, self.horizon_delay, self.failed_states)

    @staticmethod
    def _key(record: CandidateRecognition, outcome: str) -> StratumKey:
        return StratumKey(
            source_day=record.source_day,
            source_role=record.source_role,
            continuity_segment=record.continuity_segment,
            family_id=record.family_id,
            side_orientation=record.side,
            session_phase=record.session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=f"outcome={outcome}",
        )

    @staticmethod
    def _population_key(record: CandidateRecognition) -> tuple[str, ...]:
        """Outcome deliberately absent: this is the denominator across all outcomes."""
        return (
            record.source_day,
            record.source_role,
            str(record.continuity_segment),
            record.family_id,
            record.side,
            record.session_phase,
        )

    def record(self, candidate: CandidateRecognition) -> dict[str, Any]:
        """Fold in one candidate. Every candidate counts, detected or not."""
        if candidate.outcome is None:
            raise RecognitionError(
                f"candidate {candidate.candidate_id} has no outcome; mark it missed or censored "
                "rather than leaving it out of the population"
            )
        self.recorded += 1
        self.superseded_attempts += candidate.superseded_attempts
        self.outcome_counts[candidate.outcome] += 1

        bucket = self.stratum_outcomes.setdefault(
            self._population_key(candidate), {name: 0 for name in ALL_OUTCOMES}
        )
        bucket[candidate.outcome] += 1

        key = self._key(candidate, candidate.outcome)
        self.failed_states.observe(key, float(len(candidate.failed_states)))
        if candidate.outcome == PRIOR:
            self.prior_lead.observe(key, float(candidate.lead_ns or 0))
        elif candidate.outcome == HORIZON:
            self.horizon_delay.observe(key, float(-(candidate.lead_ns or 0)))
        return candidate.as_dict()

    def population_report(self) -> list[dict[str, Any]]:
        """Every outcome class with its own denominator, per stratum.

        There is no method that returns a detection-time mean on its own. The detected-only
        figure appears here as one labelled row beside the missed and censored counts that
        give it meaning, because presenting it alone is the exact error section 4.11 names.
        """
        rows = []
        for population_key, counts in sorted(self.stratum_outcomes.items()):
            total = sum(counts.values())
            detected = sum(counts[name] for name in DETECTED_OUTCOMES)
            rows.append(
                {
                    "stratum": {
                        "source_day": population_key[0],
                        "source_role": population_key[1],
                        "continuity_segment": int(population_key[2]),
                        "family_id": population_key[3],
                        "side_orientation": population_key[4],
                        "session_phase": population_key[5],
                        "clock": CAUSAL_CLOCK,
                    },
                    "population_denominator": total,
                    "outcome_counts": dict(counts),
                    "detected_count": detected,
                    "undetected_count": total - detected,
                    "detection_share": (detected / total) if total else None,
                    "detection_share_is_a_rate_not_a_mean": True,
                    "warning": (
                        "any statistic computed over detected members alone describes those "
                        f"{detected} of {total} candidates and is not the population detection time"
                    ),
                }
            )
        return rows

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        total = self.recorded
        detected = sum(self.outcome_counts[name] for name in DETECTED_OUTCOMES)
        return {
            "section": "4.11",
            "causal_clock": CAUSAL_CLOCK,
            "candidates_recorded": total,
            "outcome_counts": dict(self.outcome_counts),
            "detected_count": detected,
            "undetected_count": total - detected,
            "detection_share": (detected / total) if total else None,
            "superseded_call_attempts": self.superseded_attempts,
            "first_call_rule": "a later, better-looking recognition may not replace the first lawful call",
            "population_note": (
                "no method returns a detection-time mean alone; every lead or delay figure is "
                "reported inside population_report beside its missed and censored counts"
            ),
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
