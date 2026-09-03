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

D-10, FROM THE FIRST FULL SUNDAY RUN (33605852433). The section ran with `value_names` =
`["price_response"]` - one of the seven channels the contract names - and reported a clean
null: median response exactly 0 at H+1s in all 28 strata, 20 strata all-zero covering 52 of
90 observations, and only dispersion (not direction) by H+60s. **A null on one channel is
uninformative about whether the structure had any consequence at all.** Price can be pinned
while the book behind it empties, so "nothing happened to price" and "nothing happened" are
different findings and the artifact could not tell them apart. Three things follow, and they
are the three things this module now enforces.

1. THE CHANNEL VOCABULARY IS DECLARED, AND THE ONES WE CANNOT FEED ARE REFUSED BY NAME.
   `CONTRACT_CHANNELS` is the seven the contract requires. Four are reachable from what the
   traversal already holds; three are not, and each of those carries its refusal reason, so
   asking for one raises instead of quietly producing an empty channel. An empty channel and
   a channel that measured nothing look identical downstream - that is the whole defect.

2. THE HORIZON SET IS VERSIONED IN CODE, NOT IN A CALL SITE. `HORIZON_SETS` names each
   version's horizons, and a registered version whose horizons do not match is refused. The
   Sunday run's `a-arm-h1` is frozen byte-for-byte; the sub-second ladder is `a-arm-h2`, a
   NEW version, because mutating a version in place makes two runs incomparable while both
   claim the same label.

3. A READING'S LATENESS TRAVELS ON THE READING. The traversal matures horizons on whole
   seconds, so a horizon can be due long before anyone looks. That is late, not early, and
   late is a measurement property - but at 1 ms the lateness can be a thousand times the
   horizon, which would make an "H+1ms response" a relabelled H+1s response. So every
   matured observation carries `read_recv_ns`, `read_lateness_ns` and a resolution class,
   and `LATE_BEYOND_HORIZON` says outright that the traversal cannot resolve that horizon at
   its current advance granularity.
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

# --- the seven channels section 4.16 names ---------------------------------------------
#
# "native price, flow, full-book, queue, survival, transition, and completion changes".
PRICE_RESPONSE = "price_response"
FLOW_RESPONSE = "flow_response"
FULL_BOOK_RESPONSE = "full_book_response"
QUEUE_RESPONSE = "queue_response"
SURVIVAL_RESPONSE = "survival_response"
TRANSITION_RESPONSE = "transition_response"
COMPLETION_RESPONSE = "completion_response"

CONTRACT_CHANNELS = (
    PRICE_RESPONSE,
    FLOW_RESPONSE,
    FULL_BOOK_RESPONSE,
    QUEUE_RESPONSE,
    SURVIVAL_RESPONSE,
    TRANSITION_RESPONSE,
    COMPLETION_RESPONSE,
)

FEEDABLE_CHANNELS: dict[str, str] = {
    PRICE_RESPONSE: (
        "midpoint change in raw price from the track's first lawful instant; the traversal "
        "holds it as BookState.price_raw"
    ),
    FLOW_RESPONSE: (
        "change in cumulative signed aggressor flow in lots from the track's first lawful "
        "instant; the traversal holds it as the roll20 signed flow it already hands 4.12"
    ),
    FULL_BOOK_RESPONSE: (
        "change in TOTAL resting depth across the whole book, bid plus ask, from the track's "
        "first lawful instant; the traversal holds it as BookState.bid_depth + ask_depth at "
        "FULL_BOOK scope. Deliberately a LEVEL and not an imbalance: 4.9 and 4.12 both "
        "compute (bid-ask)/(bid+ask) and disagreed with each other on the Sunday run, and a "
        "third copy of a contested estimand adds a third disagreement, not a third view"
    ),
    QUEUE_RESPONSE: (
        "change in resting depth at the best price on the CANDIDATE'S OWN side - the queue a "
        "same-side maker would have to stand behind - from the track's first lawful instant; "
        "the traversal holds the full ladder it already hands 4.9"
    ),
}

REFUSED_CHANNELS: dict[str, str] = {
    SURVIVAL_RESPONSE: (
        "REFUSED_DEGENERATE_BY_CONSTRUCTION: a channel is only ever read at a horizon that "
        "MATURED, and a horizon matures only for a track that was not censored before it, so "
        "a per-track survival indicator here would be 1.0 on every row it could ever occupy. "
        "Survival is already carried, correctly denominated, by at_risk_table(): entered, "
        "observed and censored per horizon per stratum. Emitting it as a channel would add a "
        "constant beside a real measurement and invite it to be read as one"
    ),
    TRANSITION_RESPONSE: (
        "REFUSED_NOT_REACHABLE: the structure's transition state lives in 4.10's phase and "
        "4.14's edge graph, and neither is passed to this section. The reading callback is "
        "given a track and a horizon and nothing else. Feeding a zero here would be a "
        "fabricated measurement of 'no transition' where none was taken"
    ),
    COMPLETION_RESPONSE: (
        "REFUSED_NOT_REACHABLE: completion is 4.10's episode terminal, and this section is "
        "not joined to 4.10 - the principal filed that missing join separately. A completion "
        "channel cannot be fed until the episode's terminal reaches the reading callback"
    ),
}

DEPTH_SCOPE_FULL_BOOK = "FULL_BOOK"
"""The only scope from which a depth-derived channel may be computed.

D-5 was 4.9 computing ladder topology on a group-local, effectively one-sided book -
`relative_imbalance` exactly +/-1.0 on 152 of 154 readings. A depth response taken off the
ten-level projection is that same truncation wearing a different name, so the helper below
refuses it by scope rather than trusting the caller to remember.
"""
DEPTH_SCOPE_UNDECLARED = "DEPTH_SCOPE_UNDECLARED"

# --- versioned horizon sets --------------------------------------------------------------
NS_PER_MS = 1_000_000
NS_PER_S = 1_000_000_000

HORIZON_SETS: dict[str, tuple[int, ...]] = {
    # FROZEN. What run 33605852433 actually used. It is not edited to add the sub-second
    # horizon: a version whose contents change is a label that no longer identifies anything,
    # and the Sunday findings are quoted against this one.
    "a-arm-h1": (1 * NS_PER_S, 10 * NS_PER_S, 60 * NS_PER_S),
    # The sub-second ladder, sited on measured mechanics rather than round numbers. 4.7 on the
    # same day: median time-to-restoration 1.775 ms AT_TOUCH (n=556) against 673.1 ms
    # BEHIND_TOUCH (n=7,636). So 1 ms is BEFORE a defended touch has typically come back,
    # 10 ms is after it, and 100 ms is still well before the behind-touch population restores
    # - three horizons that bracket the two restoration populations instead of straddling
    # both. The existing 1 s / 10 s / 60 s are kept unchanged above them so an a-arm-h2 run
    # answers the h1 questions too and the two are comparable where they overlap.
    "a-arm-h2": (
        1 * NS_PER_MS,
        10 * NS_PER_MS,
        100 * NS_PER_MS,
        1 * NS_PER_S,
        10 * NS_PER_S,
        60 * NS_PER_S,
    ),
}

EXACT_AT_HORIZON = "EXACT_AT_HORIZON"
LATE_WITHIN_HORIZON = "LATE_WITHIN_HORIZON"
LATE_BEYOND_HORIZON = "LATE_BEYOND_HORIZON"

REGIME_BASIS_UNDECLARED = "REGIME_BASIS_UNDECLARED_BY_CALLER"
"""What `starting_liquidity_regime` was derived from, named by the caller.

The principal could not settle D-10's constant regime from the artifact: "I read that as
downstream of the same one-sided book, but I cannot prove the derivation from this artifact
and do not claim it." The regime arrived as a bare string with no provenance, so a reader
could not tell a genuinely one-regime day from a regime computed off a truncated book. The
basis rides with it now. Undeclared is itself a declaration and says so by name.
"""

REGIME_CONDITIONS = "CONDITIONS_ON_MORE_THAN_ONE_REGIME"
REGIME_CONSTANT = "CONDITIONS_ON_A_CONSTANT"


class ResponseError(ValueError):
    """A response observation violated the causal ordering or channel rules."""


def horizons_for_version(horizon_version: str) -> tuple[int, ...]:
    """The registered horizons for a version, so a call site cannot retype them wrong."""
    try:
        return HORIZON_SETS[horizon_version]
    except KeyError:
        raise ResponseError(
            f"horizon version {horizon_version!r} is not registered; register it in "
            f"HORIZON_SETS rather than passing horizons a reader cannot resolve to a version"
        ) from None


@dataclass(frozen=True)
class ChannelReading:
    """The raw quantities one instant supplies, exactly as the traversal already holds them.

    This is the shape the reading callback should build from; `channel_values` turns a
    baseline and a current one into the channel mapping. It lives here rather than in the
    traversal so the arithmetic of every channel is in the section that declares them, and so
    it can be tested without a book.

    Every field defaults to None because absence is a real state and must be expressible.
    None becomes an EXCLUDED AND COUNTED reading, never a zero - a zero here is a measurement
    that the structure moved nothing, which is the opposite claim.
    """

    price_raw: int | None = None
    signed_flow_lots: int | None = None
    resting_depth_total: int | None = None
    same_side_touch_depth: int | None = None
    depth_scope: str = DEPTH_SCOPE_UNDECLARED


_CHANNEL_FIELDS: dict[str, str] = {
    PRICE_RESPONSE: "price_raw",
    FLOW_RESPONSE: "signed_flow_lots",
    FULL_BOOK_RESPONSE: "resting_depth_total",
    QUEUE_RESPONSE: "same_side_touch_depth",
}

_DEPTH_DERIVED_CHANNELS = frozenset({FULL_BOOK_RESPONSE, QUEUE_RESPONSE})


def channel_values(
    baseline: ChannelReading, current: ChannelReading, *, channels: Sequence[str]
) -> dict[str, float | None]:
    """Baseline-to-current change for each requested channel, None where unmeasurable.

    Every requested channel appears as a key. That is the contract the calculator enforces:
    an OMITTED channel means the feed does not produce it at all and is refused, while a key
    holding None means this instant had nothing to measure and is excluded and counted. The
    two are different facts and the Sunday artifact could not distinguish them.
    """
    if baseline.depth_scope != current.depth_scope:
        raise ResponseError(
            f"depth scopes differ between the baseline ({baseline.depth_scope}) and the "
            f"reading ({current.depth_scope}); a response is a change in ONE quantity, and "
            "differencing two scopes measures the scope change instead"
        )
    values: dict[str, float | None] = {}
    for name in channels:
        if name in _DEPTH_DERIVED_CHANNELS and baseline.depth_scope != DEPTH_SCOPE_FULL_BOOK:
            raise ResponseError(
                f"{name} needs {DEPTH_SCOPE_FULL_BOOK} depth and was handed "
                f"{baseline.depth_scope}; D-5 was exactly this - a truncated book presented "
                "as the book, which reads as present, typed and in range"
            )
        field_name = _CHANNEL_FIELDS.get(name)
        if field_name is None:
            raise ResponseError(f"{name} has no reading field; it is not a feedable channel")
        was = getattr(baseline, field_name)
        now = getattr(current, field_name)
        values[name] = None if was is None or now is None else float(now - was)
    return values


@dataclass
class HorizonObservation:
    """One structure's reading at one fixed horizon. Written once."""

    horizon_ns: int
    due_recv_ns: int
    status: str = PENDING
    observed_recv_ns: int | None = None
    read_recv_ns: int | None = None
    read_lateness_ns: int | None = None
    reading_resolution: str | None = None
    values: dict[str, float] = field(default_factory=dict)
    absent_channels: list[str] = field(default_factory=list)

    @property
    def observed(self) -> bool:
        return self.status == MATURED

    def record(
        self,
        *,
        read_recv_ns: int,
        values: Mapping[str, float],
        absent_channels: Sequence[str] = (),
    ) -> None:
        """Write the earliest observation, and say when the traversal actually looked.

        `observed_recv_ns` stays the DUE time - the causal cutoff, which a late look must
        never postdate. `read_recv_ns` is the stream instant the traversal was standing on
        when it took the reading. They differed by up to a full second on the Sunday run,
        because the driver matures horizons on whole seconds, and nothing recorded it.
        """
        if self.status != PENDING:
            raise ResponseError(
                f"horizon {self.horizon_ns} already has a {self.status} observation; a later "
                "reading may not substitute for the earliest one"
            )
        if read_recv_ns < self.due_recv_ns:
            raise ResponseError(
                f"horizon {self.horizon_ns} is not due until {self.due_recv_ns}; recording at "
                f"{read_recv_ns} would read the future"
            )
        self.status = MATURED
        self.observed_recv_ns = self.due_recv_ns
        self.read_recv_ns = read_recv_ns
        self.read_lateness_ns = read_recv_ns - self.due_recv_ns
        self.reading_resolution = resolution_of(self.horizon_ns, self.read_lateness_ns)
        self.values = dict(values)
        self.absent_channels = list(absent_channels)

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
            "read_recv_ns": self.read_recv_ns,
            "read_lateness_ns": self.read_lateness_ns,
            "reading_resolution": self.reading_resolution,
            "values": dict(self.values),
            "absent_channels": list(self.absent_channels),
        }


def resolution_of(horizon_ns: int, lateness_ns: int) -> str:
    """How much of this reading is the horizon and how much is the traversal's granularity.

    A reading taken one second after a 1 ms horizon is not an H+1ms reading; it is an H+1s
    reading wearing the shorter label. The class says so on every row, so a sub-second horizon
    added to the version set cannot silently report the granularity it was measured at.
    """
    if lateness_ns == 0:
        return EXACT_AT_HORIZON
    if lateness_ns <= horizon_ns:
        return LATE_WITHIN_HORIZON
    return LATE_BEYOND_HORIZON


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
    starting_liquidity_regime_basis: str = REGIME_BASIS_UNDECLARED
    horizons: dict[int, HorizonObservation] = field(default_factory=dict)
    change_points: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False

    def add_change_point(self, *, recv_ns: int, values: Mapping[str, Any]) -> None:
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
            "starting_liquidity_regime_basis": self.starting_liquidity_regime_basis,
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
        if sorted(set(value_names)) != sorted(value_names):
            raise ResponseError("response channels must be unique")
        for name in value_names:
            if name in REFUSED_CHANNELS:
                raise ResponseError(
                    f"channel {name} is refused by this section: {REFUSED_CHANNELS[name]}"
                )
            if name not in FEEDABLE_CHANNELS:
                raise ResponseError(
                    f"channel {name} is not one of the seven the contract names "
                    f"({', '.join(CONTRACT_CHANNELS)}); a channel outside the vocabulary "
                    "cannot be reconciled against the contract that requires them"
                )
        # A registered version is its horizons. Passing a version's name beside different
        # horizons is how two runs come to share one label while measuring different things,
        # so it is refused here rather than discovered when the artifacts disagree.
        registered = HORIZON_SETS.get(horizon_version)
        if registered is not None and tuple(sorted(horizons_ns)) != registered:
            raise ResponseError(
                f"horizon version {horizon_version!r} is registered as {registered} and was "
                f"passed {tuple(sorted(horizons_ns))}; register a NEW version instead of "
                "changing what an existing one means"
            )
        self.horizons_ns = tuple(sorted(horizons_ns))
        self.horizon_version = horizon_version
        self.horizon_version_registered = registered is not None
        self.value_names = tuple(value_names)
        self.omitted_feedable_channels = tuple(
            name for name in FEEDABLE_CHANNELS if name not in self.value_names
        )

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
                        numerator_formula=f"{FEEDABLE_CHANNELS[name]}, at + {horizon} ns",
                        population=(
                            f"structures still at risk at H+{horizon}ns within the stratum; "
                            "this denominator is specific to this horizon"
                        ),
                        causal_cutoff=f"first lawful availability + {horizon} ns on {CAUSAL_CLOCK}",
                        status=RESOLVED,
                        missingness_rule=(
                            "structures censored before this horizon are excluded here and "
                            "counted in the at-risk table; a channel the feed declares "
                            "unmeasurable at this instant is excluded and counted too, never "
                            "recorded as a zero"
                        ),
                    ),
                    **kwargs,
                )

        self._open: dict[str, ResponseTrack] = {}
        self._at_risk: dict[tuple[str, ...], dict[int, dict[str, int]]] = {}
        self._regime_counts: dict[str, int] = {}
        self._regime_bases: dict[str, int] = {}
        self._channel_readings: dict[str, int] = {name: 0 for name in self.value_names}
        self._channel_absences: dict[str, int] = {name: 0 for name in self.value_names}
        self._resolution_counts: dict[int, dict[str, int]] = {
            horizon: {EXACT_AT_HORIZON: 0, LATE_WITHIN_HORIZON: 0, LATE_BEYOND_HORIZON: 0}
            for horizon in self.horizons_ns
        }
        self.change_points_observed = 0
        self.change_point_feed_enabled: bool | None = None
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

    def _validate_reading(self, values: Mapping[str, Any], *, where: str) -> None:
        """An omitted channel is NOT WIRED; a None channel is unmeasurable. Different facts.

        Nothing enforced this before, so declaring a channel the feed never produced would
        have accumulated a full run of exclusions and emitted an empty measure - which is
        indistinguishable from a channel that was fed and found nothing. That is D-10's
        second half, and it is caught on the FIRST maturation rather than at the end of a
        fourteen-hour traversal.
        """
        if not values:
            return
        supplied = set(values)
        missing = sorted(name for name in self.value_names if name not in supplied)
        if missing:
            raise ResponseError(
                f"{where}: the feed supplied {sorted(supplied)} and omitted {missing}. A "
                "declared channel the feed does not produce is not wired; supply the key "
                "with None to declare an absence, which is excluded and counted"
            )
        extra = sorted(name for name in supplied if name not in self.value_names)
        if extra:
            raise ResponseError(
                f"{where}: the feed supplied {extra}, which this table was not told to emit. "
                "D60: a value that reaches the calculator is emitted or refused by name, "
                "never dropped on the floor"
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
        starting_liquidity_regime_basis: str = REGIME_BASIS_UNDECLARED,
    ) -> ResponseTrack:
        if structure_id in self._open:
            raise ResponseError(f"track {structure_id} is already open")
        if not starting_liquidity_regime:
            raise ResponseError(
                "starting_liquidity_regime is a stratum key and may not be empty; an empty "
                "key field reads as 'not recorded' and collides with every other one"
            )
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
            starting_liquidity_regime_basis=starting_liquidity_regime_basis,
        )
        for horizon in self.horizons_ns:
            track.horizons[horizon] = HorizonObservation(
                horizon_ns=horizon, due_recv_ns=first_lawful_recv_ns + horizon
            )
        self._open[structure_id] = track
        self.tracks_opened += 1
        self._regime_counts[starting_liquidity_regime] = (
            self._regime_counts.get(starting_liquidity_regime, 0) + 1
        )
        self._regime_bases[starting_liquidity_regime_basis] = (
            self._regime_bases.get(starting_liquidity_regime_basis, 0) + 1
        )

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
                self._validate_reading(
                    values, where=f"H+{horizon}ns on track {track.structure_id}"
                )
                measured = {
                    name: float(value)
                    for name, value in values.items()
                    if value is not None
                }
                absent = [name for name in self.value_names if name not in measured]
                # `read_recv_ns` is the instant the traversal is standing on, NOT the due
                # instant. Passing the due instant made the "would read the future" guard in
                # `record` unfalsifiable from here, because it compared a value against
                # itself.
                observation.record(
                    read_recv_ns=recv_ns, values=measured, absent_channels=absent
                )
                self._resolution_counts[horizon][observation.reading_resolution] += 1
                buckets[horizon]["observed"] += 1
                key = self._key(track, horizon)
                for name in self.value_names:
                    if name in measured:
                        self.response[(horizon, name)].observe(key, measured[name])
                        self._channel_readings[name] += 1
                    else:
                        self.response[(horizon, name)].exclude_missing(key)
                        self._channel_absences[name] += 1
                recorded.append(
                    {
                        "structure_id": track.structure_id,
                        "horizon_ns": horizon,
                        "observation": observation.as_dict(),
                    }
                )
        return recorded

    def declare_change_point_feed(self, *, enabled: bool) -> None:
        """Record whether the traversal is feeding event-driven change points.

        Direct calculator use may leave this undeclared; a traversal must declare it once so
        an explicit comparison-off state can never be mistaken for an observed zero.
        """
        self.change_point_feed_enabled = bool(enabled)

    def observe_change_point(self, recv_ns: int, *, values_for: Any) -> int:
        """The event-driven half of 4.16's emission rule, which nothing has ever called.

        The contract requires emission "at every available event-driven change point AND at
        versioned fixed H+N horizons"; run 33605852433 emitted only the three fixed horizons,
        because `add_change_point` had no caller outside its own test. This is the entry
        point a traversal calls when the observable state it feeds this section changes.

        Readings go through the same channel validation as a horizon, so a change point
        cannot carry a channel set the horizons do not. Note the cost before wiring it:
        every change point is RETAINED on its track under D60 and travels into the lifecycle
        row, so the retained volume is (open tracks x changes), not (tracks).
        """
        written = 0
        for track in list(self._open.values()):
            if recv_ns < track.first_lawful_recv_ns:
                continue
            values = values_for(track)
            self._validate_reading(
                values, where=f"change point at {recv_ns} on track {track.structure_id}"
            )
            track.add_change_point(recv_ns=recv_ns, values=values)
            written += 1
        self.change_points_observed += written
        return written

    def _close(self, track: ResponseTrack, *, status: str, recv_ns: int) -> dict[str, Any]:
        buckets = self._at_risk[self._risk_key(track)]
        for horizon in self.horizons_ns:
            observation = track.horizons[horizon]
            if observation.status == PENDING:
                observation.censor(status=status, recv_ns=recv_ns)
                buckets[horizon]["censored"] += 1
                # EVERY channel, not `value_names[0]`. With one channel the two are the same
                # expression and the run that exposed this emitted exactly one; with more,
                # only the first channel's denominator would have learned about the censoring
                # and the channels of one horizon would silently disagree about how many
                # structures were at risk.
                for name in self.value_names:
                    self.response[(horizon, name)].exclude_missing(self._key(track, horizon))
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

    def regime_conditioning(self) -> dict[str, Any]:
        """Whether `starting_liquidity_regime` conditioned anything, as a measured fact.

        On run 33605852433 it was DEPTH_SKEW_BID on all 84 at-risk rows and all 91 candidates.
        The cause is NOT this section and not the D-5 truncated book: the regime is computed
        upstream from the full-book depths and handed in as a string, and it is a bare sign
        comparison of two absolute depths on one instrument. Bid depth exceeded ask depth for
        the whole slice - the reopen snapshot alone carries 154 bid adds against 90 ask adds
        and about 121 occupied bid prices against 76 - so the sign never flipped. A sign that
        does not change state carries no information however it is spelled, which is the D23
        defect applied to a stratum key instead of a trigger.

        This section cannot fix the derivation; it can refuse to present a constant as a
        conditioning dimension. The status rides on the at-risk rows and in the summary.
        """
        distinct = len(self._regime_counts)
        return {
            "distinct_values": distinct,
            "counts": dict(sorted(self._regime_counts.items())),
            "basis_counts": dict(sorted(self._regime_bases.items())),
            "status": REGIME_CONSTANT if distinct <= 1 else REGIME_CONDITIONS,
            "note": (
                "a stratum dimension with one value partitions nothing; the strata it appears "
                "in are the strata the other key fields already made"
            ),
        }

    def channel_report(self) -> dict[str, Any]:
        """What was emitted, what was refused and why, and what was never fed."""
        never_fed = sorted(
            name for name in self.value_names if self._channel_readings[name] == 0
        )
        return {
            "contract_channels": list(CONTRACT_CHANNELS),
            "emitted": list(self.value_names),
            "readings_per_channel": dict(sorted(self._channel_readings.items())),
            "declared_absences_per_channel": dict(sorted(self._channel_absences.items())),
            "channels_never_fed": never_fed,
            "refused": dict(sorted(REFUSED_CHANNELS.items())),
            "omitted_feedable": list(self.omitted_feedable_channels),
            "omission_rule": (
                "a feedable channel not requested is NOT emitted empty; it is named here so "
                "a null on an emitted channel cannot be read as a null on the structure"
            ),
        }

    def horizon_resolution_report(self) -> dict[str, Any]:
        """How much of each horizon's reading is horizon and how much is advance granularity.

        A horizon whose readings are all LATE_BEYOND_HORIZON was not measured at its own
        length. That is the honest gate on a sub-second horizon: it is emitted, and it says
        for itself whether the traversal could resolve it.
        """
        return {
            str(horizon): {
                **counts,
                "resolved_at_its_own_length": counts[LATE_BEYOND_HORIZON] == 0,
            }
            for horizon, counts in sorted(self._resolution_counts.items())
        }

    def at_risk_table(self) -> list[dict[str, Any]]:
        """Every horizon's own denominator, never shared across horizons."""
        conditioning = self.regime_conditioning()
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
                        # The qualifier travels on the value. Read off the artifact alone,
                        # DEPTH_SKEW_BID on every row looks like a finding about the book
                        # until you count the distinct values, and nothing counted them.
                        "starting_liquidity_regime_conditioning": conditioning["status"],
                        "starting_liquidity_regime_distinct_values": (
                            conditioning["distinct_values"]
                        ),
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
            "horizon_version_registered": self.horizon_version_registered,
            "horizon_resolution": self.horizon_resolution_report(),
            "value_names": list(self.value_names),
            "channels": self.channel_report(),
            "starting_liquidity_regime_conditioning": self.regime_conditioning(),
            "tracks_opened": self.tracks_opened,
            "tracks_closed": self.tracks_closed,
            "tracks_open": len(self._open),
            "event_driven_change_points": {
                "observed": self.change_points_observed,
                "enabled": self.change_point_feed_enabled,
                "status": (
                    "DISABLED_BY_DECLARED_COMPARISON"
                    if self.change_point_feed_enabled is False
                    else "FED_BY_THE_TRAVERSAL"
                    if self.change_points_observed > 0
                    else "ENABLED_NO_CHANGE_POINTS_OBSERVED"
                    if self.change_point_feed_enabled is True
                    else "NOT_FED_BY_THE_TRAVERSAL"
                ),
                "rule": (
                    "the canonical traversal enables event-driven change points under D83/D88; "
                    "an explicit comparison may disable them and is named as such. Enabled with "
                    "zero observations means no eligible event fired, not that the feed was off"
                ),
            },
            "emission": "DEFERRED_UNTIL_HORIZON_ELAPSED_IN_STREAM_TIME",
            "earliest_observation_rule": (
                "each horizon is written once; a later reading may not substitute for the "
                "earliest observation taken at that horizon"
            ),
            "denominator_rule": (
                "every horizon carries its own at-risk denominator; reusing one across "
                "horizons would report the survivors as though they were all of them"
            ),
            "reading_lateness_rule": (
                "observed_recv_ns is the causal cutoff and never moves; read_recv_ns is when "
                "the traversal actually looked, and a reading later than its own horizon is "
                "classed LATE_BEYOND_HORIZON rather than reported at the shorter label"
            ),
        }
