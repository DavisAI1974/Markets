"""The A-arm candidate unit: a causally-detected dipole flow event (D66).

**What a candidate IS, and why it is not an F_LAST group.** D53 made the traversal's MEMBER
unit one F_LAST-closed group - 4,256,603 of them over four days - and that is right for
identity, families, mirrors, clocks, queue, replenishment, absorption, ladder, lineage and
recurrence, which are all group-shaped. It is wrong for 4.10, 4.11, 4.12 and 4.16, which need
an event with a before and an after. Those four are exactly the four that were blocked, and
that split fell out of the code rather than being designed - which is the evidence behind
D66's ruling that there are TWO unit levels, not one.

The frozen exhaustion program's candidate is a **locally prominent spike in per-second signed
aggressor imbalance** - 3,429 of them over 54/55 weeks, roughly nine a week. Price is never
used to find or orient it. `ng_exhaustion_chain_canonical_table_20260817.detect_week_events`
is the frozen construction and this is its causal port.

**WHAT IS PORTED VERBATIM.** The rolling window (20s), the peak quantile (0.85), the local
radius (5s), the refractory (45s), the prominence baseline (median of |flow| over t-30..t-9,
which is already causal in the frozen code), and polarity from the sign of the flow.

**WHAT CANNOT BE PORTED, MEASURED, because Greg's rule is that Frankie sees it as we would in
RT** (*"I don't want to limit that just on our wrong coding or assumptions. It should see that
as we would in rt."*):

1. **The threshold.** The frozen code sets `day_thresholds[d] = quantile(|roll20| over the
   WHOLE DAY, 0.85)` at line 194-198. **The bar for 09:00 is set using 15:00's data.** That is
   hindsight. Here the bar is a TRAILING quantile over what has already been seen, and no
   candidate may fire before a declared warmup, because a quantile over four observations is
   not a bar, it is noise.
2. **The selection.** The frozen code sorts every candidate in the day by prominence and then
   applies the refractory greedily, so a LATER, more prominent spike suppresses an earlier
   one. That is hindsight twice over. Two lawful rules are offered instead and the choice
   travels on every candidate as `selection_rule`, because a caveat living only in prose
   expires:
   * `CAUSAL_WINDOWED_PROMINENCE` **(the default, and the measurement that decided it)** -
     buffer qualifying peaks for one refractory window and emit the most prominent. Costs
     `t + REFRACTORY` availability instead of `t + LOCAL_RADIUS`.
   * `CAUSAL_FIRST_COME` - the first qualifying peak wins its window. Earliest lawful
     availability, and **it destroys signal.** Measured on a two-spike stream: a background
     peak of magnitude **0.04** arriving seven seconds earlier shadowed a real spike of
     magnitude **0.9** - twenty-two times larger - and the spike was never emitted at all.
     Windowed prominence kept both. An 85th-percentile bar admits roughly 15% of seconds by
     construction, so trivial peaks are always in the buffer competing for the window; under
     first-come, whichever noise arrives first wins it. Greg's rule is that Frankie must not
     be limited by our coding choices, and losing a 22x spike to a coin flip on arrival order
     is exactly that. `CAUSAL_FIRST_COME` is retained because it is the earliest lawful
     answer and someone may want it, never because it is safe.
3. **The endpoint.** `endpoint()` walks FORWARD until flow persists on the opposite polarity.
   That is an OUTCOME and it is not computed here at all: nothing in this module may be
   available at a decision point earlier than the fact it describes.

**CONSEQUENCE, DECLARED RATHER THAN DISCOVERED LATER: this will not reproduce the frozen
3,429.** A causal bar finds a different set than a hindsight bar, and a causal selection keeps
different members of a cluster. Reporting the same count would be the warning sign, not the
goal.

**AVAILABILITY IS THE POINT, not a detail.** A spike at `t` needs `t +/- LOCAL_RADIUS` to be
known as a local maximum, so it is not knowable until `t + LOCAL_RADIUS`. Every candidate
carries `event_second` (when it happened) and `available_second` (when we could first have
said so) as separate fields, because 4.11 measures PRIOR, T0 and H+N against the second one
and collapsing them would make every recognition look instant.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterator, Sequence

# Ported verbatim from ng_exhaustion_chain_canonical_table_20260817.
ROLL_WINDOW = 20
PEAK_QUANTILE = 0.85
LOCAL_RADIUS = 5
REFRACTORY = 45
BASELINE_LAG = 9
BASELINE_START = 30
BASELINE_POINTS = BASELINE_START - BASELINE_LAG
"""t-30 .. t-10 inclusive: TWENTY-ONE points, which is what `range(t-30, t-9)` yields.

The first version used `t-30 <= s <= t-9`, twenty-two points, including one observation
closer to the peak than the frozen baseline ever sees. It changed prominence on 63 of 63
emitted candidates in a 4,000-second comparison - and prominence is the windowed rule's sort
key, so it decides which member of a cluster survives, not merely a reported number. The
module claimed this was ported verbatim; it was not.
"""

ZERO_FLOW_EPSILON = 1e-12
"""The frozen zero-magnitude guard, which the first version did not port.

`ng_exhaustion_chain_canonical_table_20260817.py:313` drops a mark whose magnitude is below
this. Without it, a balanced thin tape - equal buy and sell volume in the window, so `roll20`
is exactly 0.0 - makes the trailing bar 0.0 too, and then `abs(0.0) < 0.0` is False and
`0.0 < 0.0 - 1e-12` is False, so EVERY such second is a qualifying peak with polarity 0.
Measured on `[0.0]*300` with one 0.9 spike: the frozen emits exactly one event; the unguarded
port emitted a stream of direction-less zeros and, under first-come, lost the real spike
entirely to a zero-magnitude tie.
"""

DAY_SECONDS = 86400

CAUSAL_FIRST_COME = "CAUSAL_FIRST_COME"
CAUSAL_WINDOWED_PROMINENCE = "CAUSAL_WINDOWED_PROMINENCE"
SELECTION_RULES = frozenset({CAUSAL_FIRST_COME, CAUSAL_WINDOWED_PROMINENCE})

FROZEN_HINDSIGHT_THRESHOLD = "FROZEN_WHOLE_DAY_QUANTILE_NOT_RT_LAWFUL"
"""Only for reconciliation against the frozen corpus. Never for a causal run - see below."""

TRAILING_QUANTILE = "TRAILING_CAUSAL_QUANTILE"


class CandidateError(ValueError):
    """A candidate could not be detected lawfully."""


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def quantile(values: Sequence[float], q: float) -> float:
    """The frozen `quantile`, ported so the bar is computed the same way it always was."""
    ordered = sorted(float(v) for v in values if _finite(v))
    if not ordered:
        return float("nan")
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[int(pos)]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


@dataclass(frozen=True)
class Candidate:
    """One dipole flow event, with the two clocks kept apart."""

    candidate_id: str
    event_second: int
    """When the spike occurred."""
    available_second: int
    """The first second we could lawfully have said so. NEVER equal to event_second here."""
    polarity: int
    """+1 or -1, from the SIGN of signed flow. Never from magnitude, never from price."""
    magnitude: float
    prominence: float
    threshold: float
    threshold_rule: str
    selection_rule: str
    continuity_segment: int
    baseline: float
    observations_behind_threshold: int
    """FINITE observations behind the trailing bar. Not seconds - NaN seconds never enter it."""
    window_truncated: bool = False
    """True when the segment ended before this candidate's window closed.

    `finish()` forces every buffered window open, so the last one's winner is the maximum over
    a PARTIAL window and its availability lies past the segment end. Without this flag a
    consumer measuring H+N against `available_second` indexes past the data - a complete
    window and a truncated one would look identical.
    """

    @property
    def detection_lag_seconds(self) -> int:
        return self.available_second - self.event_second

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "event_second": self.event_second,
            "available_second": self.available_second,
            "detection_lag_seconds": self.detection_lag_seconds,
            "polarity": self.polarity,
            "magnitude": self.magnitude,
            "prominence": self.prominence,
            "threshold": self.threshold,
            "threshold_rule": self.threshold_rule,
            "selection_rule": self.selection_rule,
            "continuity_segment": self.continuity_segment,
            "baseline": self.baseline,
            "observations_behind_threshold": self.observations_behind_threshold,
            "window_truncated": self.window_truncated,
            "direction_note": (
                "polarity is the SIGN of signed flow; magnitude is reported beside it and "
                "never instead of it, because two spikes with opposite signs have the same "
                "magnitude"
            ),
            "availability_note": (
                "a spike at t needs t +/- LOCAL_RADIUS to be a local maximum, so it is not "
                "knowable until t + LOCAL_RADIUS; PRIOR/T0/H+N are measured against "
                "available_second, never against event_second"
            ),
        }


class CausalPeakDetector:
    """Streaming, forward-only detection of dipole flow events. Bounded memory.

    Fed one second at a time in order. Emits a candidate only once every input it depends on
    has arrived, which is what makes `available_second` a fact rather than an assertion.
    """

    def __init__(
        self,
        *,
        continuity_segment: int,
        selection_rule: str = CAUSAL_WINDOWED_PROMINENCE,
        peak_quantile: float = PEAK_QUANTILE,
        local_radius: int = LOCAL_RADIUS,
        refractory: int = REFRACTORY,
        threshold_observations: int = DAY_SECONDS,
        warmup_seconds: int = 900,
        min_threshold_observations: int = 600,
    ) -> None:
        if selection_rule not in SELECTION_RULES:
            raise CandidateError(
                f"selection_rule must be one of {sorted(SELECTION_RULES)}; it shapes which "
                "member of a cluster survives and is never defaulted silently"
            )
        if local_radius < 1 or refractory < 1:
            raise CandidateError("local radius and refractory must be positive second counts")
        if warmup_seconds < local_radius + BASELINE_START:
            raise CandidateError(
                "warmup must cover the baseline lookback; a bar computed from a handful of "
                "observations is noise wearing a threshold's name"
            )
        self.continuity_segment = continuity_segment
        self.selection_rule = selection_rule
        self.peak_quantile = peak_quantile
        self.local_radius = local_radius
        self.refractory = refractory
        # A COUNT OF FINITE OBSERVATIONS, not a wall-clock span. NaN seconds never enter the
        # buffer, so on a half-quiet tape a "86400" buffer carries about two days of history
        # while the frozen bar was strictly one day. The name says what it is now; the first
        # version called it `threshold_window` and published it as `threshold_window_seconds`.
        self.threshold_observations = threshold_observations
        self.warmup_seconds = warmup_seconds
        # The warmup the constructor's error text always described but never enforced: it
        # gated on how many times `observe` had been CALLED, and NaN seconds count there. On
        # 905 NaN seconds followed by one finite 0.42, the bar was built from that single
        # observation, which then cleared itself. Overnight NG has stretches of that shape.
        self.min_threshold_observations = min_threshold_observations

        self._flow: deque[tuple[int, float]] = deque()
        self._trailing: deque[float] = deque()
        self._seconds_seen = 0
        self._last_accepted: int | None = None
        self._previous_second: int | None = None
        self._pending: list[Candidate] = []
        self.emitted = 0
        self.rejected_below_threshold = 0
        self.rejected_zero_magnitude = 0
        self.rejected_not_local_max = 0
        self.rejected_in_refractory = 0
        self.suppressed_by_prominence = 0
        self.seconds_in_warmup = 0

    # --- the pass ---------------------------------------------------------
    def observe(self, second: int, flow: float) -> list[Candidate]:
        """Fold one second in. Returns the candidates that became lawful AT THIS SECOND.

        EVERY second must be supplied, including the ones with no trades - a quiet second is
        NaN, not absent. The local-max window is sliced POSITIONALLY while `available_second`
        is computed TEMPORALLY, so a skipped stretch silently turns a long wait into a short
        claim: measured on a feed that jumped from second 204 to second 5000, a candidate at
        second 200 was stamped available at 205 after a 4,800-second wait. That is a
        4,800-second lookahead recorded as a five-second one, which is the exact failure this
        module exists to prevent. A real discontinuity is what `continuity_segment` is for:
        start a new detector.
        """
        if self._previous_second is not None and second != self._previous_second + 1:
            raise CandidateError(
                f"seconds must arrive contiguously; got {second} after {self._previous_second}. "
                "A quiet second is NaN, not skipped, and a real break starts a new segment"
            )
        self._previous_second = second
        self._flow.append((second, float(flow) if _finite(flow) else float("nan")))
        if _finite(flow):
            self._trailing.append(abs(float(flow)))
            while len(self._trailing) > self.threshold_observations:
                self._trailing.popleft()
        self._seconds_seen += 1
        # Keep only what a decision at the centre can still need.
        span = 2 * self.local_radius + BASELINE_START + 1
        while len(self._flow) > span:
            self._flow.popleft()

        released: list[Candidate] = []
        centre = self._centre_index()
        if centre is not None:
            found = self._judge(centre)
            if found is not None:
                released.extend(self._select(found))
        released.extend(self._release_ready(second))
        return released

    def finish(self, last_second: int) -> list[Candidate]:
        """Release anything still buffered, MARKED as truncated where the window never closed.

        Forcing a window open at stream end makes its winner the maximum over a partial
        window and stamps an availability the segment never reaches. That is unavoidable at a
        boundary; presenting it as a completed window is not, so every such release carries
        `window_truncated`.
        """
        complete = self._release_ready(last_second)
        return complete + self._release_ready(last_second, truncating=True)

    # --- internals --------------------------------------------------------
    def _centre_index(self) -> int | None:
        """The index whose full local window has now arrived, or None."""
        need = self.local_radius
        if len(self._flow) < need + 1:
            return None
        idx = len(self._flow) - 1 - need
        return idx if idx - need >= 0 else None

    def _judge(self, idx: int) -> Candidate | None:
        second, value = self._flow[idx]
        # Counted BEFORE the finiteness check, so the reported figure is the number of
        # seconds actually spent in warmup rather than the number of finite ones.
        if (
            self._seconds_seen <= self.warmup_seconds
            or len(self._trailing) < self.min_threshold_observations
        ):
            self.seconds_in_warmup += 1
            return None
        if not _finite(value):
            return None
        if abs(value) < ZERO_FLOW_EPSILON:
            # The frozen zero-magnitude guard. A balanced window is not a peak, and calling
            # it one manufactures direction-less events that then consume refractory windows.
            self.rejected_zero_magnitude += 1
            return None
        threshold = quantile(self._trailing, self.peak_quantile)
        # A bar of exactly 0.0 is NOT rejected, and this is a deliberate divergence from the
        # review's suggested fix. The frozen detector admits any non-zero magnitude against a
        # zero bar - on `[0.0]*300` with one 0.9 spike it emits exactly that spike - and
        # rejecting a zero bar drops the real event with the noise. The zero-magnitude guard
        # above is the frozen's own defence and it is sufficient: the zeros are refused as
        # values, not by disqualifying the threshold they produced.
        if not _finite(threshold) or abs(value) < threshold:
            self.rejected_below_threshold += 1
            return None
        window = [
            abs(v)
            for _, v in list(self._flow)[idx - self.local_radius: idx + self.local_radius + 1]
            if _finite(v)
        ]
        if not window or abs(value) < max(window) - 1e-12:
            self.rejected_not_local_max += 1
            return None
        history = [
            abs(v)
            for s, v in self._flow
            if _finite(v) and second - BASELINE_START <= s < second - BASELINE_LAG
        ]
        baseline = _median(history) if history else 0.0
        if not _finite(baseline):
            baseline = 0.0
        return Candidate(
            candidate_id=f"dip-{self.continuity_segment}-{second}",
            event_second=second,
            available_second=second + self.local_radius,
            polarity=1 if value > 0 else (-1 if value < 0 else 0),
            magnitude=abs(value),
            prominence=abs(value) - baseline,
            threshold=threshold,
            threshold_rule=TRAILING_QUANTILE,
            selection_rule=self.selection_rule,
            continuity_segment=self.continuity_segment,
            baseline=baseline,
            observations_behind_threshold=len(self._trailing),
            window_truncated=False,
        )

    def _select(self, candidate: Candidate) -> list[Candidate]:
        # The refractory is enforced against what was ACCEPTED, under BOTH rules, and here
        # rather than only at release. Filtering the buffer at release was not enough: a
        # candidate judged AFTER the winner's window closed was never in the buffer to be
        # filtered, so it opened a fresh window inside the winner's shadow. Measured before
        # this line existed: emitted events 33 seconds apart against a 45-second refractory.
        if (
            self._last_accepted is not None
            and candidate.event_second - self._last_accepted < self.refractory
        ):
            self.rejected_in_refractory += 1
            return []
        if self.selection_rule == CAUSAL_FIRST_COME:
            self._last_accepted = candidate.event_second
            self.emitted += 1
            return [candidate]
        self._pending.append(candidate)
        return []

    def _release_ready(self, now_second: int, *, truncating: bool = False) -> list[Candidate]:
        """Windowed-prominence only: a buffered peak becomes lawful once its window closes.

        Three defects the first version had, all found by adversarial review and each
        reproduced before being fixed:

        1. **It did not enforce the refractory it exists to enforce.** It partitioned on
           `window_open` and then emitted a winner that could sit anywhere inside the window,
           so the next window opened at `window_open + refractory` rather than at
           `winner + refractory`. Measured: emitted events seven seconds apart against a
           forty-five second refractory. The frozen greedy loop compares against what was
           actually PICKED, and so does this now.
        2. **The window closed before its own members had been judged.** `observe(S)` judges
           the centre at `S - local_radius`, so at `S = window_open + refractory` the last
           `local_radius` seconds of the window are not in the buffer yet - they were
           systematically removed from the competition and then seeded a new window.
        3. **`available_second` was a property of the winner, not of the window.** It is one
           instant, and it is when the window that produced the decision actually closed.
        """
        if self.selection_rule != CAUSAL_WINDOWED_PROMINENCE or not self._pending:
            return []
        out: list[Candidate] = []
        while self._pending:
            window_open = self._pending[0].event_second
            closes_at = window_open + self.refractory + self.local_radius
            if not truncating and now_second < closes_at:
                break
            group = [c for c in self._pending if c.event_second < window_open + self.refractory]
            winner = max(group, key=lambda c: (c.prominence, c.magnitude))
            # The next window may not open until a full refractory after what was PICKED.
            self._pending = [
                c for c in self._pending
                if c.event_second >= winner.event_second + self.refractory
            ]
            self._last_accepted = winner.event_second
            self.suppressed_by_prominence += len(group) - 1
            self.emitted += 1
            out.append(
                Candidate(
                    **{
                        **{f: getattr(winner, f) for f in winner.__dataclass_fields__},
                        "available_second": closes_at,
                        "window_truncated": truncating,
                    }
                )
            )
        return out

    def summary(self) -> dict[str, Any]:
        return {
            "unit": "DIPOLE_FLOW_EVENT",
            "continuity_segment": self.continuity_segment,
            "selection_rule": self.selection_rule,
            "threshold_rule": TRAILING_QUANTILE,
            "peak_quantile": self.peak_quantile,
            "local_radius_seconds": self.local_radius,
            "refractory_seconds": self.refractory,
            "threshold_observation_cap": self.threshold_observations,
            "min_threshold_observations": self.min_threshold_observations,
            "warmup_seconds": self.warmup_seconds,
            "seconds_observed": self._seconds_seen,
            "candidates_emitted": self.emitted,
            "seconds_in_warmup": self.seconds_in_warmup,
            "rejected_below_threshold": self.rejected_below_threshold,
            "rejected_zero_magnitude": self.rejected_zero_magnitude,
            "rejected_not_local_max": self.rejected_not_local_max,
            "rejected_in_refractory": self.rejected_in_refractory,
            "suppressed_by_prominence": self.suppressed_by_prominence,
            "not_the_frozen_population": (
                "a causal bar finds a different set than the frozen whole-day quantile and a "
                "causal selection keeps a different member of a cluster; reproducing the "
                "frozen 3,429 would be the warning sign, not the goal"
            ),
            "endpoint_note": (
                "the episode endpoint walks forward and is an OUTCOME; it is not computed "
                "here and is never available at a decision point"
            ),
        }


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return float("nan")
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def detect(
    flow: Sequence[float],
    *,
    first_second: int,
    continuity_segment: int,
    **kwargs: Any,
) -> tuple[list[Candidate], CausalPeakDetector]:
    """Convenience for a complete per-second series. Streams it exactly as a live feed would."""
    detector = CausalPeakDetector(continuity_segment=continuity_segment, **kwargs)
    found: list[Candidate] = []
    last = first_second
    for offset, value in enumerate(flow):
        last = first_second + offset
        found.extend(detector.observe(last, value))
    found.extend(detector.finish(last))
    return found, detector
