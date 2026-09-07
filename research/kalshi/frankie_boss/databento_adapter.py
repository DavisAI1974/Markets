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
Exchange and capture clocks are independent. Every received row is retained,
with both original timestamps and an explicit clock-domain declaration.
Inversions are reported as defects; they neither rewrite time nor remove rows.
Receive time remains the sole visibility gate. SkewPolicy thresholds describe
feed diagnostics only and cannot authorize evidence exclusion.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping, Sequence

try:  # Package import in Markets.
    from .causal_packet import CaptureClockContract, Record
except ImportError:  # Direct checkpoint execution with this directory on PYTHONPATH.
    from causal_packet import CaptureClockContract, Record

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
    """Legacy diagnostic policy; neither threshold excludes received evidence."""

    tolerance_ns: int = 0
    max_quarantine_rate: float = 0.001  # 0.1% -- above this, the feed is suspect


@dataclass
class AdapterStats:
    received_asof: int = 0
    inspected: int = 0
    quarantined_skew: int = 0
    excluded_future: int = 0
    retained_skew: int = 0

    @property
    def seen(self):
        """Compatibility alias: received rows, never unavailable future rows."""
        return self.received_asof

    @property
    def quarantine_rate(self) -> float:
        return self.quarantined_skew / self.seen if self.seen else 0.0

    def defects(self, policy: SkewPolicy, source: str) -> list[str]:
        out: list[str] = []
        if self.retained_skew:
            out.append(
                f"{source}: {self.retained_skew}/{self.seen} received rows retained "
                "with ts_recv_ns < ts_event_ns; independent clock mismatch"
            )
        if self.seen and self.retained_skew / self.seen > policy.max_quarantine_rate:
            out.append(f"{source}: clock discipline is unsound; all received rows retained")
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
        self.clock_contract = CaptureClockContract(name)
        self._rows_for = rows_for
        self.policy = policy or SkewPolicy()
        self._watermark_for = watermark_for
        self.stats = AdapterStats()
        self._fetch_history = []

    def _to_record(self, row: MBORow) -> Record:
        return Record(
            key=row.key,
            event_time=row.ts_event_ns,
            ingest_time=row.ts_recv_ns,  # the clock. never ts_event_ns.
            payload={**row.payload, "ts_in_delta_ns": row.ts_in_delta_ns},
            version=row.version,
            independent_clocks=True,
            clock_contract=self.clock_contract,
        )

    def fetch(self, entity: str, as_of: int) -> Sequence[Record]:
        self.stats = AdapterStats()
        out: list[Record] = []
        for row in self._rows_for(entity):
            self.stats.inspected += 1
            if row.ts_recv_ns > as_of:
                self.stats.excluded_future += 1
                continue

            self.stats.received_asof += 1
            if row.ts_event_ns > row.ts_recv_ns:
                self.stats.retained_skew += 1
            # Independent clocks do not authorize rewriting either timestamp
            # or discarding a row already observed by the capture host.
            out.append(self._to_record(row))
        self._fetch_history.append((entity, as_of, replace(self.stats)))
        return out

    def fetch_history(self):
        """All fetch diagnostics, for operators only.

        Future-row counts cannot enter an as-of model packet: doing so would
        leak information about evidence not yet received at that cutoff.
        """
        return tuple((entity, cutoff, replace(stats))
                     for entity, cutoff, stats in self._fetch_history)

    def watermark(self, entity: str, as_of: int) -> int | None:
        if self._watermark_for is not None:
            return self._watermark_for(entity, as_of)
        # A maximum observed timestamp proves neither gap-free coverage nor
        # completeness. Never reread a potentially different live snapshot.
        return None

    def defects(self) -> list[str]:
        return self.stats.defects(self.policy, self.name)
