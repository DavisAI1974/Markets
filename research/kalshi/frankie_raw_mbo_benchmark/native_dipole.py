"""Section 4.12: dipole and opposing-pressure runway.

One sentence governs this section: "Direction comes from signed flow and causal mechanics,
not unsigned dipole magnitude." Magnitude tells you how lopsided the book is; it cannot
tell you which way. So magnitude here is a derived read-only property of the signed value
and there is no path that produces a direction from it - `direction` reads the sign of
signed flow, and a stage whose signed flow is zero reports no direction rather than
defaulting to one.

`SAME` and `FLIP` orientations never pool. They are the two ways a mirrored structure can
relate to its counterpart, and averaging across them cancels precisely the asymmetry the
measure exists to find, so orientation is part of the stratum identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

CAUSAL_CLOCK = "ts_recv_ns"

SAME = "SAME"
FLIP = "FLIP"
VALID_ORIENTATIONS = frozenset({SAME, FLIP})

LONG = "LONG"
SHORT = "SHORT"
NO_DIRECTION = "NO_DIRECTION"


class DipoleError(ValueError):
    """A dipole stage could not be measured."""


@dataclass(frozen=True)
class DipoleStage:
    """One runway stage's signed pressure state."""

    runway_id: str
    stage_index: int
    recv_ns: int
    orientation: str
    signed_flow: int
    bid_depth: int
    ask_depth: int
    bid_order_count: int
    ask_order_count: int
    bid_level_count: int
    ask_level_count: int
    price_raw: int

    def __post_init__(self) -> None:
        if self.orientation not in VALID_ORIENTATIONS:
            raise DipoleError(f"orientation must be one of {sorted(VALID_ORIENTATIONS)}")
        if self.stage_index < 0:
            raise DipoleError("stage_index must be non-negative")
        for name in ("bid_depth", "ask_depth", "bid_order_count", "ask_order_count"):
            if getattr(self, name) < 0:
                raise DipoleError(f"{name} must be non-negative")

    @property
    def direction(self) -> str:
        """From signed flow only. Zero flow yields no direction, never a default."""
        if self.signed_flow > 0:
            return LONG
        if self.signed_flow < 0:
            return SHORT
        return NO_DIRECTION

    @property
    def magnitude(self) -> int:
        """Unsigned. Derived from the signed value and never a direction source."""
        return abs(self.signed_flow)

    @property
    def normalized_imbalance(self) -> float | None:
        total = self.bid_depth + self.ask_depth
        if total == 0:
            return None
        return (self.bid_depth - self.ask_depth) / total

    def as_dict(self) -> dict[str, Any]:
        return {
            "runway_id": self.runway_id,
            "stage_index": self.stage_index,
            "recv_ns": self.recv_ns,
            "orientation": self.orientation,
            "signed_flow": self.signed_flow,
            "direction": self.direction,
            "magnitude": self.magnitude,
            "normalized_imbalance": self.normalized_imbalance,
            "bid_depth": self.bid_depth,
            "ask_depth": self.ask_depth,
            "bid_order_count": self.bid_order_count,
            "ask_order_count": self.ask_order_count,
            "bid_level_count": self.bid_level_count,
            "ask_level_count": self.ask_level_count,
            "price_raw": self.price_raw,
            "clock": CAUSAL_CLOCK,
        }


@dataclass(frozen=True)
class DipolePath:
    """A runway's ordered stages, with sign reversals kept exact."""

    runway_id: str
    stages: tuple[DipoleStage, ...]

    def __post_init__(self) -> None:
        if not self.stages:
            raise DipoleError("a dipole path needs at least one stage")
        indices = [s.stage_index for s in self.stages]
        if indices != sorted(indices) or len(set(indices)) != len(indices):
            raise DipoleError("stages must be strictly ordered by stage_index")
        if len({s.orientation for s in self.stages}) > 1:
            raise DipoleError("a path holds one orientation; SAME and FLIP never mix")

    @property
    def orientation(self) -> str:
        return self.stages[0].orientation

    @property
    def sign_reversals(self) -> list[dict[str, Any]]:
        """Every exact sign change, with the stage and time it happened."""
        reversals = []
        previous = None
        for stage in self.stages:
            direction = stage.direction
            if direction == NO_DIRECTION:
                continue
            if previous is not None and direction != previous:
                reversals.append(
                    {
                        "stage_index": stage.stage_index,
                        "recv_ns": stage.recv_ns,
                        "from_direction": previous,
                        "to_direction": direction,
                    }
                )
            previous = direction
        return reversals

    @property
    def persisted(self) -> bool:
        return not self.sign_reversals

    @property
    def inflection_recv_ns(self) -> int | None:
        reversals = self.sign_reversals
        return reversals[0]["recv_ns"] if reversals else None

    @property
    def price_coupling(self) -> int:
        """Price change across the path, unsigned by side here and signed by flow downstream."""
        return self.stages[-1].price_raw - self.stages[0].price_raw

    def as_dict(self) -> dict[str, Any]:
        return {
            "runway_id": self.runway_id,
            "orientation": self.orientation,
            "stage_count": len(self.stages),
            "sign_reversals": self.sign_reversals,
            "sign_reversal_count": len(self.sign_reversals),
            "persisted": self.persisted,
            "inflection_recv_ns": self.inflection_recv_ns,
            "price_coupling_raw": self.price_coupling,
            "stages": [s.as_dict() for s in self.stages],
        }


class DipoleCalculator:
    """Streaming section 4.12 accumulator. Stage-relative, orientation-separated."""

    def __init__(self, *, exact_cap: int | None = None, seed: int = 0) -> None:
        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, missingness: str):
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population="dipole runway stages within the stratum, orientation and stage index",
                    causal_cutoff="stage receive time on ts_recv_ns",
                    status=RESOLVED,
                    missingness_rule=missingness,
                ),
                **kwargs,
            )

        self.signed_flow = measure(
            "signed_flow",
            "aggressor-signed flow at the stage; sign is the direction, not the magnitude",
            "no exclusions",
        )
        self.normalized_imbalance = measure(
            "normalized_imbalance",
            "(bid depth - ask depth) / (bid depth + ask depth) at the stage",
            "stages with an empty book are excluded and counted",
        )
        self.magnitude = measure(
            "magnitude",
            "absolute signed flow; reported beside the signed measure, never instead of it",
            "no exclusions",
        )
        self.mirror_difference = measure(
            "paired_mirror_difference",
            "exact within-pair difference of signed flow, orientation preserved",
            "unpaired stages are excluded and counted; they are a different estimand",
        )

        self.stages_seen = 0
        self.direction_counts = {LONG: 0, SHORT: 0, NO_DIRECTION: 0}
        self.paths_seen = 0
        self.reversal_total = 0

    @property
    def measures(self) -> tuple[StratifiedMeasure, ...]:
        return (self.signed_flow, self.normalized_imbalance, self.magnitude, self.mirror_difference)

    @staticmethod
    def _key(
        stage: DipoleStage,
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        family_id: str,
        session_phase: str,
        event_phase: str,
    ) -> StratumKey:
        """Orientation is the side dimension here: SAME and FLIP never pool."""
        return StratumKey(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=family_id,
            side_orientation=stage.orientation,
            session_phase=session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=f"event_phase={event_phase}|stage={stage.stage_index}",
        )

    def observe_stage(
        self,
        stage: DipoleStage,
        *,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        family_id: str,
        session_phase: str,
        event_phase: str,
        mirror_signed_flow: int | None = None,
    ) -> dict[str, Any]:
        key = self._key(
            stage,
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=family_id,
            session_phase=session_phase,
            event_phase=event_phase,
        )
        self.stages_seen += 1
        self.direction_counts[stage.direction] += 1

        self.signed_flow.observe(key, float(stage.signed_flow))
        self.magnitude.observe(key, float(stage.magnitude))

        imbalance = stage.normalized_imbalance
        if imbalance is None:
            self.normalized_imbalance.exclude_missing(key)
        else:
            self.normalized_imbalance.observe(key, float(imbalance))

        if mirror_signed_flow is None:
            self.mirror_difference.exclude_missing(key)
        else:
            self.mirror_difference.observe(key, float(stage.signed_flow - mirror_signed_flow))
        return stage.as_dict()

    def observe_path(self, path: DipolePath) -> dict[str, Any]:
        self.paths_seen += 1
        self.reversal_total += len(path.sign_reversals)
        return path.as_dict()

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.measures:
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.12",
            "causal_clock": CAUSAL_CLOCK,
            "stages_seen": self.stages_seen,
            "paths_seen": self.paths_seen,
            "direction_counts": dict(self.direction_counts),
            "sign_reversals": self.reversal_total,
            "direction_source": "SIGNED_FLOW_AND_CAUSAL_MECHANICS",
            "magnitude_note": (
                "magnitude is derived from the signed value and is never a direction source; "
                "a zero-flow stage reports NO_DIRECTION rather than defaulting to one"
            ),
            "orientation_note": "SAME and FLIP are separate strata and never pool",
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
