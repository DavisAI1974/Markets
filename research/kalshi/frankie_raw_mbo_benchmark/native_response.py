"""Section 4.16: fixed causal future-response table.

The instruction that shapes the design is "Preserve the earliest observation and do not
substitute a later horizon." A response table is built by waiting, and waiting creates the
temptation to report whatever the data eventually showed. So a horizon here records its
observation once and refuses a second write: a later, cleaner reading of the same horizon
cannot replace the first one taken at that horizon.

Each horizon carries its own at-risk denominator, because they are not the same population.
A structure censored at a session boundary was at risk at H+1s and not at H+60s, and a
response curve that silently reuses one denominator across horizons reports the surviving
structures as though they were all of them.

Emission is deferred exactly as in section 4.7: horizons mature in stream time, so nothing
in this table is computed from data the calculator has not yet reached.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    CENSORED,
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
)

CAUSAL_CLOCK = "ts_recv_ns"

MATURED = "MATURED"
CENSORED_BOUNDARY = "CENSORED_BOUNDARY"
CENSORED_STREAM_END = "CENSORED_STREAM_END"
PENDING = "PENDING"


class ResponseError(ValueError):
    """A response observation violated the causal ordering rules."""


@dataclass
class HorizonObservation:
    """One structure's reading at one fixed horizon. Written once."""

    horizon_ns: int
    due_recv_ns: int
    status: str = PENDING
    observed_recv_ns: int | None = None
    values: dict[str, float] = field(default_factory=dict)

    @property
    def observed(self) -> bool:
        return self.status == MATURED

    def record(self, *, recv_ns: int, values: Mapping[str, float]) -> None:
        if self.status != PENDING:
            raise ResponseError(
                f"horizon {self.horizon_ns} already has a {self.status} observation; a later "
                "reading may not substitute for the earliest one"
            )
        if recv_ns < self.due_recv_ns:
            raise ResponseError(
                f"horizon {self.horizon_ns} is not due until {self.due_recv_ns}; recording at "
                f"{recv_ns} would read the future"
            )
        self.status = MATURED
        self.observed_recv_ns = recv_ns
        self.values = dict(values)

    def censor(self, *, status: str, recv_ns: int) -> None:
        if self.status != PENDING:
            return
        self.status = status
        self.observed_recv_ns = recv_ns

    def as_dict(self) -> dict[str, Any]:
        return {
            "horizon_ns": self.horizon_ns,
            "due_recv_ns": self.due_recv_ns,
            "status": self.status,
            "observed": self.observed,
            "observed_recv_ns": self.observed_recv_ns,
            "values": dict(self.values),
        }


@dataclass
class ResponseTrack:
    """One structure's response trajectory from its first lawful availability."""

    structure_id: str
    first_lawful_recv_ns: int
    source_day: str
    source_role: str
    continuity_segment: int
    family_id: str
    side_orientation: str
    session_phase: str
    cluster_version: str
    starting_liquidity_regime: str
    horizons: dict[int, HorizonObservation] = field(default_factory=dict)
    change_points: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False

    def add_change_point(self, *, recv_ns: int, values: Mapping[str, float]) -> None:
        """An event-driven observation, kept beside the fixed horizons."""
        if recv_ns < self.first_lawful_recv_ns:
            raise ResponseError("a change point cannot precede first lawful availability")
        self.change_points.append({"recv_ns": recv_ns, "values": dict(values)})

    def as_dict(self) -> dict[str, Any]:
        return {
            "structure_id": self.structure_id,
            "first_lawful_recv_ns": self.first_lawful_recv_ns,
            "source_day": self.source_day,
            "source_role": self.source_role,
            "continuity_segment": self.continuity_segment,
            "family_id": self.family_id,
            "side_orientation": self.side_orientation,
            "session_phase": self.session_phase,
            "cluster_version": self.cluster_version,
            "starting_liquidity_regime": self.starting_liquidity_regime,
            "closed": self.closed,
            "change_point_count": len(self.change_points),
            "change_points": list(self.change_points),
            "horizons": [self.horizons[h].as_dict() for h in sorted(self.horizons)],
            "clock": CAUSAL_CLOCK,
        }


class ResponseTableCalculator:
    """Streaming section 4.16 accumulator with per-horizon at-risk denominators."""

    def __init__(
        self,
        *,
        horizons_ns: Sequence[int],
        horizon_version: str,
        value_names: Sequence[str],
        exact_cap: int | None = None,
        seed: int = 0,
    ) -> None:
        if not horizons_ns:
            raise ResponseError("at least one horizon is required")
        if sorted(set(horizons_ns)) != sorted(horizons_ns):
            raise ResponseError("horizons must be unique")
        if any(h <= 0 for h in horizons_ns):
            raise ResponseError("horizons must be positive")
        if not value_names:
            raise ResponseError("at least one response value is required")
        self.horizons_ns = tuple(sorted(horizons_ns))
        self.horizon_version = horizon_version
        self.value_names = tuple(value_names)

        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap
        self._measure_kwargs = kwargs

        self.response: dict[tuple[int, str], StratifiedMeasure] = {}
        for horizon in self.horizons_ns:
            for name in self.value_names:
                self.response[(horizon, name)] = StratifiedMeasure(
                    name=f"response[{name}]@H+{horizon}ns",
                    declaration=Declaration(
                        numerator_formula=f"{name} at first lawful availability + {horizon} ns",
                        population=(
                            f"structures still at risk at H+{horizon}ns within the stratum; "
                            "this denominator is specific to this horizon"
                        ),
                        causal_cutoff=f"first lawful availability + {horizon} ns on {CAUSAL_CLOCK}",
                        status=RESOLVED,
                        missingness_rule=(
                            "structures censored before this horizon are excluded here and "
                            "counted in the at-risk table"
                        ),
                    ),
                    **kwargs,
                )

        self._open: dict[str, ResponseTrack] = {}
        self._at_risk: dict[tuple[str, ...], dict[int, dict[str, int]]] = {}
        self.tracks_opened = 0
        self.tracks_closed = 0

    def _key(self, track: ResponseTrack, horizon: int) -> StratumKey:
        """Horizon and its version are in the key: horizons are separate populations."""
        return StratumKey(
            source_day=track.source_day,
            source_role=track.source_role,
            continuity_segment=track.continuity_segment,
            family_id=track.family_id,
            side_orientation=track.side_orientation,
            session_phase=track.session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=(
                f"regime={track.starting_liquidity_regime}"
                f"|horizon={horizon}|horizon_version={self.horizon_version}"
            ),
            cluster_version=track.cluster_version,
        )

    @staticmethod
    def _risk_key(track: ResponseTrack) -> tuple[str, ...]:
        return (
            track.source_day,
            track.source_role,
            str(track.continuity_segment),
            track.family_id,
            track.side_orientation,
            track.session_phase,
            track.cluster_version,
            track.starting_liquidity_regime,
        )

    def open_track(
        self,
        *,
        structure_id: str,
        first_lawful_recv_ns: int,
        source_day: str,
        source_role: str,
        continuity_segment: int,
        family_id: str,
        side_orientation: str,
        session_phase: str,
        cluster_version: str,
        starting_liquidity_regime: str,
    ) -> ResponseTrack:
        if structure_id in self._open:
            raise ResponseError(f"track {structure_id} is already open")
        track = ResponseTrack(
            structure_id=structure_id,
            first_lawful_recv_ns=first_lawful_recv_ns,
            source_day=source_day,
            source_role=source_role,
            continuity_segment=continuity_segment,
            family_id=family_id,
            side_orientation=side_orientation,
            session_phase=session_phase,
            cluster_version=cluster_version,
            starting_liquidity_regime=starting_liquidity_regime,
        )
        for horizon in self.horizons_ns:
            track.horizons[horizon] = HorizonObservation(
                horizon_ns=horizon, due_recv_ns=first_lawful_recv_ns + horizon
            )
        self._open[structure_id] = track
        self.tracks_opened += 1

        buckets = self._at_risk.setdefault(self._risk_key(track), {})
        for horizon in self.horizons_ns:
            row = buckets.setdefault(horizon, {"entered": 0, "observed": 0, "censored": 0})
            row["entered"] += 1
        return track

    def advance(self, recv_ns: int, *, values_for: Any) -> list[dict[str, Any]]:
        """Record every horizon that has matured in stream time.

        `values_for(track, horizon)` supplies the reading. It is a callback so the calculator
        never reaches forward for data itself - it asks only at the moment a horizon is due.
        """
        recorded = []
        for track in list(self._open.values()):
            buckets = self._at_risk[self._risk_key(track)]
            for horizon in self.horizons_ns:
                observation = track.horizons[horizon]
                if observation.status != PENDING or recv_ns < observation.due_recv_ns:
                    continue
                values = values_for(track, horizon)
                observation.record(recv_ns=observation.due_recv_ns, values=values)
                buckets[horizon]["observed"] += 1
                key = self._key(track, horizon)
                for name in self.value_names:
                    if name in values:
                        self.response[(horizon, name)].observe(key, float(values[name]))
                    else:
                        self.response[(horizon, name)].exclude_missing(key)
                recorded.append(
                    {
                        "structure_id": track.structure_id,
                        "horizon_ns": horizon,
                        "observation": observation.as_dict(),
                    }
                )
        return recorded

    def _close(self, track: ResponseTrack, *, status: str, recv_ns: int) -> dict[str, Any]:
        buckets = self._at_risk[self._risk_key(track)]
        for horizon in self.horizons_ns:
            observation = track.horizons[horizon]
            if observation.status == PENDING:
                observation.censor(status=status, recv_ns=recv_ns)
                buckets[horizon]["censored"] += 1
                self.response[(horizon, self.value_names[0])].exclude_missing(
                    self._key(track, horizon)
                )
        track.closed = True
        self._open.pop(track.structure_id, None)
        self.tracks_closed += 1
        return track.as_dict()

    def close_continuity_segment(self, *, segment: int, recv_ns: int) -> list[dict[str, Any]]:
        """Section 4.16: stop or mark censored at source, session and continuity boundaries."""
        stranded = [t for t in self._open.values() if t.continuity_segment == segment]
        return [self._close(t, status=CENSORED_BOUNDARY, recv_ns=recv_ns) for t in stranded]

    def finalize(self, *, recv_ns: int) -> list[dict[str, Any]]:
        return [
            self._close(t, status=CENSORED_STREAM_END, recv_ns=recv_ns)
            for t in list(self._open.values())
        ]

    def at_risk_table(self) -> list[dict[str, Any]]:
        """Every horizon's own denominator, never shared across horizons."""
        rows = []
        for risk_key, buckets in sorted(self._at_risk.items()):
            for horizon in self.horizons_ns:
                row = buckets.get(horizon, {"entered": 0, "observed": 0, "censored": 0})
                rows.append(
                    {
                        "stratum": {
                            "source_day": risk_key[0],
                            "source_role": risk_key[1],
                            "continuity_segment": int(risk_key[2]),
                            "family_id": risk_key[3],
                            "side_orientation": risk_key[4],
                            "session_phase": risk_key[5],
                            "cluster_version": risk_key[6],
                            "starting_liquidity_regime": risk_key[7],
                        },
                        "horizon_ns": horizon,
                        "horizon_version": self.horizon_version,
                        "entered_at_risk": row["entered"],
                        "observed": row["observed"],
                        "censored_before_horizon": row["censored"],
                        "still_pending": row["entered"] - row["observed"] - row["censored"],
                        "denominator_is_horizon_specific": True,
                    }
                )
        return rows

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in self.response.values():
            rows.extend(measure.rows())
        return rows

    def summary(self) -> dict[str, Any]:
        return {
            "section": "4.16",
            "causal_clock": CAUSAL_CLOCK,
            "horizons_ns": list(self.horizons_ns),
            "horizon_version": self.horizon_version,
            "value_names": list(self.value_names),
            "tracks_opened": self.tracks_opened,
            "tracks_closed": self.tracks_closed,
            "tracks_open": len(self._open),
            "emission": "DEFERRED_UNTIL_HORIZON_ELAPSED_IN_STREAM_TIME",
            "earliest_observation_rule": (
                "each horizon is written once; a later reading may not substitute for the "
                "earliest observation taken at that horizon"
            ),
            "denominator_rule": (
                "every horizon carries its own at-risk denominator; reusing one across "
                "horizons would report the survivors as though they were all of them"
            ),
        }
