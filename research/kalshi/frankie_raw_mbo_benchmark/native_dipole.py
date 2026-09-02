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

**D-12. The within-path stage INDEX is binned; the event PHASE is not.** The two were being
treated as one rule and they are not the same rule. "Never average across phases of the same
event" is about BIRTH / PERSISTENCE / REVERSAL - three qualitatively different states of a
runway - and it stands untouched here: `event_phase` is still a raw component of the stratum
key. `stage=k` is an ordinal position inside a phase, and putting it in the key raw shattered
the population: run 33605852433 produced 1,692 strata for 3,454 observations, 848 of them
(50.1%) at n=1, 1,307 (77.2%) at n<=2, and not one reaching n=30, which is 6,768 averaged
rows - 41.5% of the entire 16,293-row averaged layer - describing a population whose modal
average was a single member restating itself. Stage index is now bucketed by `stage_bin`,
the exact index survives on the member row, and the bin's covered range travels in the key.
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


STAGE_BIN_RULE = "OCTAVE_DOUBLING_FROM_STAGE_ZERO"
"""How `stage_bin` widens, named on every summary so the rule is never only in prose.

Bin b covers stage indices [2^(b-1), 2^b - 1] for b >= 1, with index 0 alone in the first
bin: 0 | 1 | 2-3 | 4-7 | 8-15 | 16-31 | 32-63 | 64-127 | 128-255 | ... The doubling is not a
round number picked by reflex, it is read off the shape of the population being binned.

**What the population actually is.** The members of a stage-index stratum are the paths in
that stratum's own (family, orientation, phase) context that were STILL RUNNING at index k,
so the count at k is a survival curve, monotone decreasing, never a sample of fixed size.
Measured on run 33605852433: 90 paths carried 3,454 stages, a mean path of 38.4 stages, and
4.10 on the same runways records the persistence phase spanning 3 s to 190 s - stages are
second-quantized, so that is a 63-fold spread of path length inside one population. 4.10
holds 28 (family, side) contexts, about 3.2 paths each, while 4.12 produced 1,692 strata:
roughly 60 distinct stage indices per context against roughly 3 paths to fill them. That
ratio IS the shattering, and it is not a coding error - it is what stratifying an ordinal
position on a heavy-tailed survival population does.

**Why doubling and not a fixed width.** Under a decaying survival count, any fixed width
leaves the tail exactly where it was: the widest-index bin still holds only the single
longest path, and the defect survives the fix. A width that doubles as the survivor count
roughly halves keeps successive bins within about one halving of each other, so no bin is
systematically the leftover. Applied to the measured shape - about 3.2 paths per context
reaching a maximum of roughly 190 stages - a context spans at most nine bins instead of
about sixty, and the members that were spread one-per-stratum across indices 32-63 land in
one stratum of about 30.

**Every bin is a CLOSED range.** There is no open-ended final bin, because an unbounded bin
would pool an unbounded stretch of the path and reintroduce the averaging this measure is
built to refuse. The bins tile the non-negative integers exactly once each.
"""


class DipoleError(ValueError):
    """A dipole stage could not be measured."""


def stage_bin(stage_index: int) -> tuple[str, int, int]:
    """Label, first index covered, last index covered - for one within-path stage index.

    The label carries both bounds so a reader of a single averaged row can tell which stage
    indices that row covers without holding this module in their head. `STAGE_4_7` is stages
    four through seven and says so; a bare bin ordinal would not.
    """
    if not isinstance(stage_index, int) or isinstance(stage_index, bool):
        raise DipoleError("stage_index must be an int")
    if stage_index < 0:
        raise DipoleError("stage_index must be non-negative")
    if stage_index == 0:
        first = last = 0
    else:
        exponent = stage_index.bit_length() - 1
        first = 1 << exponent
        last = (1 << (exponent + 1)) - 1
    return f"STAGE_{first}_{last}", first, last


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
    def stage_bin(self) -> str:
        """The octave this stage's index falls in. Part of the stratum key, per D-12."""
        return stage_bin(self.stage_index)[0]

    @property
    def stage_bin_first_index(self) -> int:
        return stage_bin(self.stage_index)[1]

    @property
    def stage_bin_last_index(self) -> int:
        return stage_bin(self.stage_index)[2]

    @property
    def normalized_imbalance(self) -> float | None:
        total = self.bid_depth + self.ask_depth
        if total == 0:
            return None
        return (self.bid_depth - self.ask_depth) / total

    def as_dict(self) -> dict[str, Any]:
        return {
            "runway_id": self.runway_id,
            # D60. The EXACT index stays on the exact member row. Binning happens in the
            # averaged layer's key and nowhere else, so nothing about a stage becomes
            # unrecoverable - a consumer that wants stage 37 specifically still has it, and
            # the three fields beside it say which averaged row that member fed.
            "stage_index": self.stage_index,
            "stage_bin": self.stage_bin,
            "stage_bin_first_index": self.stage_bin_first_index,
            "stage_bin_last_index": self.stage_bin_last_index,
            "stage_bin_rule": STAGE_BIN_RULE,
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
                    population=(
                        "dipole runway stages within the stratum, orientation, event phase "
                        f"and stage-index bin ({STAGE_BIN_RULE}); the exact within-path stage "
                        "index is carried on every member row"
                    ),
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
        # D60. Binning is not dropping, and the way to show that is to count. Each bin
        # records how many stages it took and the lowest and highest exact index it actually
        # saw, so a reader can tell an empty stretch of a bin from a full one instead of
        # inferring occupancy from the bin's declared width.
        self.stage_bin_counts: dict[str, dict[str, int]] = {}
        # An absent event phase is an ABSENCE, so it is missing from this dict rather than
        # present at zero. Run 33605852433 emitted BIRTH 220 and PERSISTENCE 3,234 and no
        # REVERSAL stage at all, against 90 reversed runways in 4.10, and nothing in 4.12's
        # own output said so - the discrepancy was only visible by reading 4.10 beside it.
        self.event_phase_counts: dict[str, int] = {}
        # The failure mode binning INTRODUCES, counted rather than hoped away. A wide bin can
        # be filled by one long runway's consecutive seconds - a path alone in STAGE_64_127
        # contributes up to 64 members by itself - and an n of 64 drawn from one episode is
        # not the population an n of 64 implies. So every stratum's contributing runways are
        # tracked and reported as a histogram. Bounded by concurrent episodes, which the same
        # run measured at 91 across a whole day.
        self._stratum_runways: dict[StratumKey, set[str]] = {}

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
        """Orientation is the side dimension here: SAME and FLIP never pool.

        `event_phase` is raw and stays raw. The stage INDEX is BINNED. D-12 was read the first time
        as one rule about "phase" and it is two: BIRTH, PERSISTENCE and REVERSAL are
        qualitatively different states and averaging across them destroys the distinction the
        measure exists to make, while `stage=k` is an ordinal position whose raw use put 848
        strata at n=1 with nothing left to average. Binning the index does not weaken the
        phase rule - a BIRTH stage 4 and a PERSISTENCE stage 5 sit in the same bin and still
        land in two different strata.
        """
        return StratumKey(
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=family_id,
            side_orientation=stage.orientation,
            session_phase=session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=f"event_phase={event_phase}|stage_bin={stage.stage_bin}",
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
        self.event_phase_counts[event_phase] = self.event_phase_counts.get(event_phase, 0) + 1
        self._stratum_runways.setdefault(key, set()).add(stage.runway_id)
        label, first, last = stage_bin(stage.stage_index)
        seen = self.stage_bin_counts.get(label)
        if seen is None:
            self.stage_bin_counts[label] = {
                "covers_first_index": first,
                "covers_last_index": last,
                "stages_seen": 1,
                "min_stage_index_seen": stage.stage_index,
                "max_stage_index_seen": stage.stage_index,
            }
        else:
            seen["stages_seen"] += 1
            seen["min_stage_index_seen"] = min(seen["min_stage_index_seen"], stage.stage_index)
            seen["max_stage_index_seen"] = max(seen["max_stage_index_seen"], stage.stage_index)

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
        runway_histogram: dict[int, int] = {}
        for runways in self._stratum_runways.values():
            runway_histogram[len(runways)] = runway_histogram.get(len(runways), 0) + 1
        runway_histogram = dict(sorted(runway_histogram.items()))
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
            "event_phase_counts": dict(self.event_phase_counts),
            "event_phase_note": (
                "a phase with no stages is absent from event_phase_counts rather than present "
                "at zero; 4.12 can only report the phases its stages were observed under, and "
                "which phases a runway passed through is 4.10's record"
            ),
            "stage_binning": {
                "rule": STAGE_BIN_RULE,
                "binned_field": "stage_index",
                "phase_still_raw": True,
                "note": (
                    "the within-path stage index is binned into closed octaves and the exact "
                    "index is retained on every member row; event phase is NOT binned"
                ),
                "bins": {label: dict(seen) for label, seen in sorted(self.stage_bin_counts.items())},
                "distinct_runways_per_stratum": runway_histogram,
                "single_runway_strata": runway_histogram.get(1, 0),
                "single_runway_note": (
                    "a stratum drawing all its members from ONE runway is that runway's "
                    "consecutive seconds, not a population of episodes; counted here because "
                    "binning is what makes it possible"
                ),
            },
            "stratum_counts": {m.name: m.stratum_count for m in self.measures},
        }
