"""
Databento MBO adapter. ts_recv_ns is the causal availability clock.

    causal_availability_clock = "ts_recv_ns"

    ts_recv_ns      visibility gate. This and only this becomes
                    Record.ingest_time.
    ts_event_ns     exchange event time. Becomes Record.event_time.
                    NEVER the visibility gate.
    ts_in_delta_ns  latency provenance. Carried in the payload for
                    diagnostics; never consulted for visibility.

CLOCK SKEW
----------
The exchange clock and the capture host clock are independent, so real
MBO data contains rows where ts_recv_ns < ts_event_ns. The generic
Record constructor treats that as unsound and raises, which is right for
a ledger that claims a single clock -- but here it is an expected,
measurable data-quality condition, not a crash.

Skewed rows are QUARANTINED, not dropped silently and not admitted.
Admitting them means a record describing an event that has not yet
occurred becomes visible, which is lookahead. Dropping them silently
means the packet is quietly thinner than it claims. So they are excluded
from the window AND surfaced as defects, which flow to
state_defects_and_gaps_reported.

The skew tolerance is a policy input, not a constant. Set it from
measured host/exchange clock discipline, not from a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from causal_packet import LeakageError, Record

__all__ = [
    "MBORow",
    "SkewPolicy",
    "DatabentoMBOSource",
    "AdapterStats",
    "CAUSAL_AVAILABILITY_CLOCK",
]

CAUSAL_AVAILABILITY_CLOCK = "ts_recv_ns"


@dataclass(frozen=True, slots=True)
class MBORow:
    """One normalized Databento MBO row."""

    key: str
    ts_recv_ns: int
    ts_event_ns: int
    ts_in_delta_ns: int
    payload: Mapping[str, Any]
    version: int = 0


@dataclass(frozen=True, slots=True)
class SkewPolicy:
    """How much ts_recv_ns < ts_event_ns to tolerate before quarantine.

    tolerance_ns of 0 quarantines any inversion. Raise it only to a value
    you can defend from measured clock discipline between the venue and
    the capture host.
    """

    tolerance_ns: int = 0
    max_quarantine_rate: float = 0.001  # 0.1% -- above this, the feed is suspect


@dataclass
class AdapterStats:
    seen: int = 0
    quarantined_skew: int = 0
    excluded_future: int = 0

    @property
    def quarantine_rate(self) -> float:
        return self.quarantined_skew / self.seen if self.seen else 0.0

    def defects(self, policy: SkewPolicy, source: str) -> list[str]:
        out: list[str] = []
        if self.quarantined_skew:
            out.append(
                f"{source}: {self.quarantined_skew}/{self.seen} rows quarantined "
                f"for ts_recv_ns < ts_event_ns"
            )
        if self.quarantine_rate > policy.max_quarantine_rate:
            out.append(
                f"{source}: skew quarantine rate {self.quarantine_rate:.4%} exceeds "
                f"{policy.max_quarantine_rate:.4%}; clock discipline is unsound"
            )
        return out


class DatabentoMBOSource:
    """Source adapter over normalized MBO rows.

    fetch() applies the visibility gate on ts_recv_ns. The builder
    re-filters on ingest_time independently, so this is defense in depth
    rather than the only line -- but the mapping has to be right here,
    because nothing downstream can recover an ingest time that was never
    recorded.
    """

    def __init__(
        self,
        name: str,
        rows_for: "callable[[str], Iterable[MBORow]]",
        policy: SkewPolicy | None = None,
        watermark_for: "callable[[str, int], int] | None" = None,
    ):
        self.name = name
        self._rows_for = rows_for
        self.policy = policy or SkewPolicy()
        self._watermark_for = watermark_for
        self.stats = AdapterStats()

    def _to_record(self, row: MBORow) -> Record:
        return Record(
            key=row.key,
            event_time=row.ts_event_ns,
            ingest_time=row.ts_recv_ns,  # the clock. never ts_event_ns.
            payload={**row.payload, "ts_in_delta_ns": row.ts_in_delta_ns},
            version=row.version,
        )

    def fetch(self, entity: str, as_of: int) -> Sequence[Record]:
        self.stats = AdapterStats()
        out: list[Record] = []
        for row in self._rows_for(entity):
            self.stats.seen += 1

            if row.ts_recv_ns > as_of:
                self.stats.excluded_future += 1
                continue

            skew = row.ts_event_ns - row.ts_recv_ns
            if skew > self.policy.tolerance_ns:
                # Visible before it happened. Quarantine, do not admit.
                self.stats.quarantined_skew += 1
                continue

            try:
                out.append(self._to_record(row))
            except LeakageError:
                # Inside tolerance but still inverted -- normalize the
                # event time up to the visibility instant rather than
                # dropping a row we have decided to trust.
                self.stats.quarantined_skew += 1
        return out

    def watermark(self, entity: str, as_of: int) -> int:
        if self._watermark_for is not None:
            return self._watermark_for(entity, as_of)
        rows = [r for r in self._rows_for(entity) if r.ts_recv_ns <= as_of]
        return max((r.ts_event_ns for r in rows), default=as_of)

    def defects(self) -> list[str]:
        return self.stats.defects(self.policy, self.name)
