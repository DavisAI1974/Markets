"""Explicit single-session units and causal observations; no calendar inference.

All absolute clocks are integer UTC nanoseconds. Production callers must supply
approved conventions and certified observations; synthetic manifests prove software only.
"""
from dataclasses import dataclass
try:
    from .forecast_contract import HashedContract, finite_number, sha256_digest, unique_names
    from .forecast_heads import KnotPolicy
except ImportError:
    from forecast_contract import HashedContract, finite_number, sha256_digest, unique_names
    from forecast_heads import KnotPolicy


@dataclass(frozen=True, slots=True)
class PriceObservation(HashedContract):
    event_ns: int
    receive_ns: int
    price: float
    evidence_hash: str

    def __post_init__(self):
        if (type(self.event_ns) is not int or type(self.receive_ns) is not int
                or self.event_ns > self.receive_ns):
            raise ValueError('certified observation requires causal integer clocks')
        finite_number(self.price, 'price')
        sha256_digest(self.evidence_hash, 'observation evidence')


@dataclass(frozen=True, slots=True)
class ForecastSession(HashedContract):
    instrument: str
    session_id: str
    open_ns: int
    close_ns: int
    event_cutoff_ns: int
    receive_cutoff_ns: int
    usd_per_price_unit: float
    tick_size: float
    convention_hash: str
    calendar_hash: str
    source_hash: str
    knot_policy: KnotPolicy
    prior_close: PriceObservation | None = None
    opening: PriceObservation | None = None
    known_marks: tuple[PriceObservation, ...] = ()

    def __post_init__(self):
        unique_names((self.instrument,), 'instrument')
        unique_names((self.session_id,), 'session')
        if (any(type(v) is not int for v in (self.open_ns, self.close_ns,
                self.event_cutoff_ns, self.receive_cutoff_ns))
                or not self.open_ns < self.close_ns
                or not self.event_cutoff_ns <= self.receive_cutoff_ns < self.close_ns):
            raise ValueError('causal cutoffs and an unfinished single session required')
        for name in ('usd_per_price_unit', 'tick_size'):
            finite_number(getattr(self, name), name)
            if getattr(self, name) <= 0:
                raise ValueError(f'{name} must be positive')
        for name in ('convention_hash', 'calendar_hash', 'source_hash'):
            sha256_digest(getattr(self, name), name)
        if (not isinstance(self.knot_policy, KnotPolicy) or self.duration_ns > 2**53
                or self.duration_ns % self.knot_policy.quantum_ns):
            raise ValueError('session must fit the exact locked timestamp quantum')
        if type(self.known_marks) is not tuple:
            raise ValueError('immutable observed marks required')
        observations = tuple(v for v in (self.prior_close, self.opening) if v is not None) + self.known_marks
        for mark in observations:
            if (not isinstance(mark, PriceObservation) or mark.event_ns > self.event_cutoff_ns
                    or mark.receive_ns > self.receive_cutoff_ns):
                raise ValueError('observation is missing certification or is not causally available')
        if self.prior_close is not None and self.prior_close.event_ns >= self.open_ns:
            raise ValueError('prior close must precede open')
        if self.event_cutoff_ns < self.open_ns:
            if self.opening is not None or self.known_marks:
                raise ValueError('preopen cannot contain future open or path observations')
        else:
            if self.prior_close is None or self.opening is None or self.opening.event_ns != self.open_ns:
                raise ValueError('postopen requires certified prior close and opening anchors')
            times = (self.open_ns,) + tuple(m.event_ns for m in self.known_marks)
            if (any(a >= b for a, b in zip(times, times[1:])) or times[-1] != self.event_cutoff_ns
                    or any((t - self.open_ns) % self.knot_policy.quantum_ns for t in times)):
                raise ValueError('observed path must be ordered and end at the exact current anchor')
            finite_number(self.observed_gap, 'observed gap')
            for mark in self.known_marks:
                finite_number(self.movement(mark), 'observed movement')

    @property
    def duration_ns(self):
        return self.close_ns - self.open_ns

    @property
    def features(self):
        day_ns = 86_400_000_000_000
        return ((self.open_ns-self.receive_cutoff_ns)/day_ns, self.duration_ns/day_ns,
                self.usd_per_price_unit, self.tick_size)

    @property
    def anchor_ns(self):
        return max(self.open_ns, self.event_cutoff_ns)

    @property
    def observed_gap(self):
        return (self.opening.price - self.prior_close.price) * self.usd_per_price_unit

    def movement(self, mark):
        return (mark.price - self.opening.price) * self.usd_per_price_unit
