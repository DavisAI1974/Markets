"""The raw MBO delivered to the principal exactly as it would arrive in real time. D81.

Greg, 2026-09-02: *"he gets every record of every field for Sunday, the date and time we are
running. and Monday will get the same thing for Monday and so on."* and *"this has to
exactly mimic how it's going to come in rt."*

**What this is.** A forward-only cursor over the exact member ledger the traversal retained
(`exact_member_rows.jsonl`, one row per F_LAST-closed native event group, written by
`RowSink` in emission order). `next_group()` hands over the next group as the byte-identical
dict the ledger holds - every field of every row, nothing reshaped (D60) - visible only once
its F_LAST record has been received, never ahead. There is no random access, no rewind and
no peek: every such attempt RAISES, because a principal who can look ahead is not computing
the sixteen sections under the causal clock the mission's section 3 binds him to.

**Why it exists.** Mission section 3 says "at every F_LAST-closed group, receive and study the
complete lawful envelope", and 55 of the registry's 99 layers carry `principal_route:
CAUSAL_GROUP_STREAM` / `activation_stage: EACH_F_LAST_CUTOFF`. The registry even shipped a
validator for the per-group delivery receipt, `validate_causal_group_delivery_receipt`, and
NOTHING CALLED IT - the same shape S119 closed seven instances of. Every session built to
mission section 5's "the runner calculates; you interpret" instead, so the principal received
a ~34 MB result and the 10.6 GB member ledger stayed on the box. This module is the route the
registry declared, and it is the caller the validator never had.

**The clock is the row's own.** The cutoff stamped on each delivery is
`clocks.first_lawful_availability_ns`, which `native_clocks.member_clock_row` sets to the
group's F_LAST `ts_recv_ns`; the row also declares `causal_availability_clock: "ts_recv_ns"`
and a row declaring any other clock is refused rather than reinterpreted. Ordering is
enforced on `ts_recv_ns`, the clock the traversal's own guard enforces, and a ledger whose
receive clock moves backwards is refused at the row where it happens.

**Sidecars ride by their own clocks, never by the group's.** Lifecycle rows (the runner's
exact per-section rows) and legacy rows (the adapter's ten-level projections) are attached to
a group only when their own availability is at or before the group's cutoff. The lifecycle
ledger carries NO uniform availability stamp - every section names its clocks differently and
two name none - so availability is resolved by a DECLARED rule, `lifecycle_availability`,
which is a fact about this ledger as written and is reported rather than hidden:

- `emitted_on` in `SEGMENT_CLOSE` / `STREAM_END`: the row's content (a censoring status, a
  final disposition) was fixed at a close instant the row does not carry, so delivering it at
  its latest named clock would state, at that clock, that nothing followed - the future.
  Withheld from every group, counted, and released only after the stream is exhausted.
- `SECOND_COMPLETE` (4.0): a second is knowable once it has ended, `(second + 1) * 1e9`.
- a `candidate` row: its own `available_second`, the clock 4.11 measures against.
- otherwise: the LATEST receive clock the row names, at any depth (`recv_ns` or `*_recv_ns`,
  integers only; a null is not a clock). A row naming none - the mirror rows, as written -
  cannot be placed on the causal clock and is withheld and counted, never dropped.

A legacy row carries `ts_recv` in float SECONDS, as `_legacy_control_row` wrote it
(`msg.ts_recv_ns / 1e9`), so it is compared in the same arithmetic: attached when
`ts_recv <= cutoff_ns / 1e9`. Division by 1e9 is monotone, so the ledger's own ordering is
preserved exactly; two rows closer than float resolution (~100 ns at this epoch) are not
separable by the row's own clock, and that is a property of the row, stated here.

**Nothing withheld is dropped.** Every sidecar row read is attached, or withheld under a
named reason and counted, and the stream receipt proves `read == attached + withheld +
pending` per ledger. Withheld rows are released by `drain_withheld()` after exhaustion.

**Every delivery is receipted through the registry.** For each group a
`FRANKIE_NATIVE_RAW_MBO_CAUSAL_GROUP_DELIVERY_V1` receipt is built, chained to the previous
receipt's hash (the first to `GENESIS_PREVIOUS_RECEIPT_SHA256`), and passed through
`validate_causal_group_delivery_receipt`, which requires all 55 causal-stream layers of the
arm. The per-layer `evidence_receipt_sha256` is a hash of the CARRIER bytes delivered at
that cutoff under `LAYER_CARRIERS` - the member line for the raw-record, lifecycle, book,
mechanics and clock groups; the attached legacy lines for the legacy crosswalk; member plus
attached lifecycle lines for the derived and prebirth groups. It is a hash of what was
handed over, not a per-field extraction, and says so.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import (
    CAUSAL_CLOCK_LAYER_IDS,
    NOT_ON_THIS_ROW,
    ClockError,
    causal_clock_layers_from_legacy_clocks,
    check_causal_clock_order,
    validate_causal_clock_layers,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    GROUP_DELIVERY_SCHEMA,
    canonical_hash,
    load_registry,
    validate_causal_group_delivery_receipt,
    validate_registry,
)

__all__ = ["NOT_ON_THIS_ROW"]  # re-exported for readers of the delivery: the declared absence

NS_PER_SECOND = 1_000_000_000
CAUSAL_CLOCK = "ts_recv_ns"
STREAM_RECEIPT_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_CAUSAL_STREAM_RECEIPT_V1"
GENESIS_PREVIOUS_RECEIPT_SHA256 = hashlib.sha256(b"").hexdigest()
"""The first group has no predecessor receipt. The chain starts from the hash of nothing,
declared here rather than left as a magic string in the first receipt."""

CLOSE_OCCASIONS = frozenset({"SEGMENT_CLOSE", "STREAM_END"})

# S121 item one: the seven registry clocks ride on every delivery BY NAME, beside a receipt
# whose four-key `clocks` object the registry validator still checks exactly (that module is
# owned elsewhere, so the seven ride beside it, never inside it).
CAUSAL_CLOCKS_CARRIER = "member.causal_clocks"
CAUSAL_CLOCKS_ROW_OWN = "ROW_OWN"
CAUSAL_CLOCKS_DERIVED_FROM_LEGACY = "DERIVED_FROM_LEGACY_CLOCKS_OBJECT"

MEMBER = "member"
LIFECYCLE = "lifecycle"
LEGACY = "legacy"
LAYER_CARRIERS: dict[str, tuple[str, ...]] = {
    "canonical_raw_dbn_mbo": (MEMBER,),
    "order_lifecycle": (MEMBER,),
    "full_book_fifo_queue": (MEMBER,),
    "microstructure_mechanics": (MEMBER,),
    "causal_clocks": (MEMBER,),
    "legacy_observable_crosswalk": (LEGACY,),
    "derived_geometry": (MEMBER, LIFECYCLE),
    "prebirth_opportunity": (MEMBER, LIFECYCLE),
}
"""Which delivered bytes carry each CAUSAL_STREAM_REQUIRED registry group. A declaration."""

AVAILABILITY_RULES = {
    "CLOSE_OCCASION": "emitted_on in {SEGMENT_CLOSE, STREAM_END}: withheld from every group; released after exhaustion",
    "SECOND_COMPLETE": "(second + 1) * 1e9 on the row's declared ts_recv_ns clock",
    "CANDIDATE_AVAILABLE_SECOND": "available_second * 1e9, the clock 4.11 measures against",
    "OWN_CLOCK": "the latest integer recv_ns / *_recv_ns the row names at any depth",
    "NO_OWN_CLOCK": "no receive clock named: withheld and counted, never dropped",
    "LEGACY": "ts_recv (float seconds) <= cutoff_ns / 1e9, the adapter's own arithmetic",
}


class CausalStreamError(ValueError):
    """The stream refused: disorder, an unclosed group, a look-ahead, or a closed cursor."""


class EndOfStream(CausalStreamError):
    """No further group. Raised by `next_group()`; `iterate()` ends cleanly instead."""


@dataclass(frozen=True)
class GroupDelivery:
    """One F_LAST-closed group as handed to the principal, with its receipt."""

    group_index: int
    first_lawful_availability_ns: int
    group: dict[str, Any]
    group_line: bytes
    lifecycle_rows: tuple[dict[str, Any], ...]
    legacy_rows: tuple[dict[str, Any], ...]
    bytes_delivered: int
    group_sha256: str
    receipt: dict[str, Any]
    gate: dict[str, Any]
    causal_clocks: dict[str, Any]
    """The seven registry clocks by layer id (native_clocks.CAUSAL_CLOCK_LAYER_IDS)."""
    causal_clocks_basis: str
    """ROW_OWN when the row carried them; DERIVED_FROM_LEGACY_CLOCKS_OBJECT for a pre-S121 ledger."""
    causal_clock_chain: dict[str, Any]
    """event_known_by <= feature_availability <= model_evaluation, checked on the delivered values."""


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _latest_recv_clock(value: Any) -> int | None:
    """The latest integer `recv_ns` / `*_recv_ns` anywhere in a row. Nulls are not clocks."""
    latest: int | None = None
    if isinstance(value, Mapping):
        for key, inner in value.items():
            if isinstance(key, str) and (key == "recv_ns" or key.endswith("_recv_ns")):
                candidate = _int_or_none(inner)
                if candidate is not None and (latest is None or candidate > latest):
                    latest = candidate
            nested = _latest_recv_clock(inner)
            if nested is not None and (latest is None or nested > latest):
                latest = nested
    elif isinstance(value, list):
        for inner in value:
            nested = _latest_recv_clock(inner)
            if nested is not None and (latest is None or nested > latest):
                latest = nested
    return latest


def lifecycle_availability(row: Mapping[str, Any]) -> tuple[str, int | None]:
    """When a lifecycle row became lawfully knowable, under the declared rule (see module doc).

    Returns `(rule, availability_ns)`; `availability_ns` is None for CLOSE_OCCASION and
    NO_OWN_CLOCK, which are withheld rather than placed.
    """
    occasion = row.get("emitted_on")
    if occasion in CLOSE_OCCASIONS:
        return "CLOSE_OCCASION", None
    if occasion == "SECOND_COMPLETE":
        second = _int_or_none(row.get("second"))
        if second is not None and row.get("clock") == CAUSAL_CLOCK:
            return "SECOND_COMPLETE", (second + 1) * NS_PER_SECOND
    if row.get("emitting_section") == "candidate":
        available = _int_or_none(row.get("available_second"))
        if available is not None:
            return "CANDIDATE_AVAILABLE_SECOND", available * NS_PER_SECOND
    latest = _latest_recv_clock(row)
    if latest is None:
        return "NO_OWN_CLOCK", None
    return "OWN_CLOCK", latest


def _legacy_lawful(row: Mapping[str, Any], cutoff_ns: int) -> bool | None:
    """True/False by the row's own `ts_recv`; None when the row carries no `ts_recv`."""
    value = row.get("ts_recv")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) <= cutoff_ns / 1e9


def _open_jsonl(path: Path):
    handle = path.open("rb")
    head = handle.read(2)
    handle.seek(0)
    if head == b"\x1f\x8b":
        handle.close()
        raise CausalStreamError(
            f"{path} is gzip-compressed; gunzip it first (fetch_frankie_ledgers does, and "
            "verifies the plain bytes against the box's PLAIN_SHA256SUMS on the way)"
        )
    return handle


class _Sidecar:
    """A forward-only reader over a lifecycle or legacy ledger with one pending row.

    Head-of-line: the file is in emission order, so a row whose availability is beyond the
    current cutoff blocks the rows behind it until a later group's cutoff reaches it. Rows
    that cannot be placed on the clock are withheld under a named reason and counted.
    """

    def __init__(self, path: Path | None, *, kind: str) -> None:
        self.kind = kind
        self.path = path
        self._handle = _open_jsonl(path) if path is not None else None
        self._pending: tuple[bytes, dict[str, Any]] | None = None
        self.rows_read = 0
        self.rows_attached = 0
        self.bytes_attached = 0
        self.late_arrivals = 0
        self.withheld_no_own_clock: dict[str, int] = {}
        self.withheld_close_occasion: dict[str, int] = {}
        self.withheld_beyond_last_cutoff = 0
        self.withheld: list[dict[str, Any]] = []
        self.exhausted = path is None

    def _read_next(self) -> tuple[bytes, dict[str, Any]] | None:
        if self._handle is None:
            return None
        while True:
            line = self._handle.readline()
            if not line:
                self._handle.close()
                self._handle = None
                self.exhausted = True
                return None
            if not line.strip():
                continue
            self.rows_read += 1
            return line, json.loads(line)

    def _withhold(self, line: bytes, row: dict[str, Any], reason: str, detail: str) -> None:
        self.withheld.append({"reason": reason, "detail": detail, "row": row, "bytes": len(line)})

    def take_lawful(self, cutoff_ns: int, previous_cutoff_ns: int | None) -> list[tuple[bytes, dict[str, Any]]]:
        taken: list[tuple[bytes, dict[str, Any]]] = []
        while True:
            item = self._pending if self._pending is not None else self._read_next()
            self._pending = None
            if item is None:
                return taken
            line, row = item
            if self.kind == LIFECYCLE:
                rule, available = lifecycle_availability(row)
                section = str(row.get("emitting_section"))
                if rule == "CLOSE_OCCASION":
                    key = f"{section}|{row.get('emitted_on')}"
                    self.withheld_close_occasion[key] = self.withheld_close_occasion.get(key, 0) + 1
                    self._withhold(line, row, "CLOSE_OCCASION", key)
                    continue
                if rule == "NO_OWN_CLOCK":
                    self.withheld_no_own_clock[section] = self.withheld_no_own_clock.get(section, 0) + 1
                    self._withhold(line, row, "NO_OWN_CLOCK", section)
                    continue
                lawful = available <= cutoff_ns
                late = previous_cutoff_ns is not None and available <= previous_cutoff_ns
            else:
                verdict = _legacy_lawful(row, cutoff_ns)
                if verdict is None:
                    self.withheld_no_own_clock["ts_recv"] = self.withheld_no_own_clock.get("ts_recv", 0) + 1
                    self._withhold(line, row, "NO_OWN_CLOCK", "ts_recv")
                    continue
                lawful = verdict
                late = previous_cutoff_ns is not None and _legacy_lawful(row, previous_cutoff_ns) is True
            if not lawful:
                self._pending = (line, row)
                return taken
            if late:
                self.late_arrivals += 1
            self.rows_attached += 1
            self.bytes_attached += len(line)
            taken.append((line, row))

    def close(self) -> None:
        """Account for everything not yet placed. Called once the member stream is done."""
        if self._pending is not None:
            line, row = self._pending
            self._pending = None
            self.withheld_beyond_last_cutoff += 1
            self._withhold(line, row, "BEYOND_LAST_CUTOFF", "availability after the last delivered cutoff")
        while True:
            item = self._read_next()
            if item is None:
                break
            line, row = item
            if self.kind == LIFECYCLE:
                rule, _available = lifecycle_availability(row)
                section = str(row.get("emitting_section"))
                if rule == "CLOSE_OCCASION":
                    key = f"{section}|{row.get('emitted_on')}"
                    self.withheld_close_occasion[key] = self.withheld_close_occasion.get(key, 0) + 1
                    self._withhold(line, row, "CLOSE_OCCASION", key)
                    continue
                if rule == "NO_OWN_CLOCK":
                    self.withheld_no_own_clock[section] = self.withheld_no_own_clock.get(section, 0) + 1
                    self._withhold(line, row, "NO_OWN_CLOCK", section)
                    continue
            elif _legacy_lawful(row, 0) is None:
                self.withheld_no_own_clock["ts_recv"] = self.withheld_no_own_clock.get("ts_recv", 0) + 1
                self._withhold(line, row, "NO_OWN_CLOCK", "ts_recv")
                continue
            self.withheld_beyond_last_cutoff += 1
            self._withhold(line, row, "BEYOND_LAST_CUTOFF", "availability after the last delivered cutoff")
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def receipt(self) -> dict[str, Any]:
        withheld_total = (
            sum(self.withheld_no_own_clock.values())
            + sum(self.withheld_close_occasion.values())
            + self.withheld_beyond_last_cutoff
        )
        pending = 1 if self._pending is not None else 0
        return {
            "path": None if self.path is None else str(self.path),
            "supplied": self.path is not None,
            "exhausted": self.exhausted,
            "rows_read": self.rows_read,
            "rows_attached": self.rows_attached,
            "bytes_attached": self.bytes_attached,
            "late_arrivals": self.late_arrivals,
            "withheld_no_own_clock": dict(sorted(self.withheld_no_own_clock.items())),
            "withheld_close_occasion": dict(sorted(self.withheld_close_occasion.items())),
            "withheld_beyond_last_cutoff": self.withheld_beyond_last_cutoff,
            "withheld_total": withheld_total,
            "pending_unplaced": pending,
            "retention_identity_holds": self.rows_read == self.rows_attached + withheld_total + pending,
        }


class CausalGroupStream:
    """Forward-only delivery of F_LAST-closed groups in `ts_recv_ns` order. See module doc."""

    def __init__(
        self,
        member_ledger_path: Path | str,
        lifecycle_ledger_path: Path | str | None = None,
        legacy_ledger_path: Path | str | None = None,
        *,
        run_id: str,
        arm: str,
        registry: Mapping[str, Any] | None = None,
    ) -> None:
        if not isinstance(run_id, str) or not run_id.strip():
            raise CausalStreamError("run_id must be a non-empty string")
        self.run_id = run_id
        self.arm = arm
        self.registry = dict(load_registry() if registry is None else registry)
        registry_gate = validate_registry(self.registry)
        self.registry_sha256 = registry_gate["registry_sha256"]
        self._layer_ids_by_group = self._causal_layers_for_arm()
        self.member_path = Path(member_ledger_path)
        self._member = _open_jsonl(self.member_path)
        self._lifecycle = _Sidecar(None if lifecycle_ledger_path is None else Path(lifecycle_ledger_path), kind=LIFECYCLE)
        self._legacy = _Sidecar(None if legacy_ledger_path is None else Path(legacy_ledger_path), kind=LEGACY)
        self._last_recv_ns: int | None = None
        self._last_cutoff_ns: int | None = None
        self._previous_receipt_sha256 = GENESIS_PREVIOUS_RECEIPT_SHA256
        self._cutoffs: list[int] = []
        self._groups = 0
        self._bytes = 0
        self._digest = hashlib.sha256()
        self._member_bytes = 0
        self._member_digest = hashlib.sha256()
        self._exhausted = False
        self._closed = False
        self._groups_with_row_own_clocks = 0
        self._groups_with_derived_clocks = 0

    # --- what is refused by construction -----------------------------------

    def _no_random_access(self, verb: str) -> CausalStreamError:
        return CausalStreamError(
            f"{verb} is not available: the stream is forward-only under the causal clock; a "
            "group is visible once its F_LAST record has been received and never before or again"
        )

    def peek(self, *_args: Any, **_kwargs: Any) -> Any:
        raise self._no_random_access("peek")

    def seek(self, *_args: Any, **_kwargs: Any) -> Any:
        raise self._no_random_access("seek")

    def rewind(self, *_args: Any, **_kwargs: Any) -> Any:
        raise self._no_random_access("rewind")

    def __getitem__(self, _index: Any) -> Any:
        raise self._no_random_access("indexing")

    def __len__(self) -> int:
        raise self._no_random_access("len")

    def __reversed__(self) -> Any:
        raise self._no_random_access("reversed")

    # --- delivery ------------------------------------------------------------

    def _causal_layers_for_arm(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for group in self.registry["groups"]:
            if group["policy"] != "CAUSAL_STREAM_REQUIRED" or self.arm not in group["arms"]:
                continue
            if group["group_id"] not in LAYER_CARRIERS:
                raise CausalStreamError(
                    f"registry group {group['group_id']!r} is CAUSAL_STREAM_REQUIRED and has no "
                    "declared carrier in LAYER_CARRIERS; declare which delivered bytes carry it"
                )
            out[group["group_id"]] = [entry["layer_id"] for entry in group["entries"]]
        return out

    def _read_member(self) -> tuple[bytes, dict[str, Any]] | None:
        while True:
            line = self._member.readline()
            if not line:
                return None
            if line.strip():
                return line, json.loads(line)

    def next_group(self) -> GroupDelivery:
        if self._closed:
            raise CausalStreamError("the stream is closed; its receipt has been taken")
        if self._exhausted:
            raise EndOfStream("no further F_LAST-closed group")
        item = self._read_member()
        if item is None:
            self._exhausted = True
            self._member.close()
            self._lifecycle.close()
            self._legacy.close()
            raise EndOfStream("no further F_LAST-closed group")
        line, row = item
        index = _int_or_none(row.get("group_index"))
        if index is None or index < 0:
            raise CausalStreamError("a member row carries no non-negative integer group_index")
        if row.get("causal_availability_clock") != CAUSAL_CLOCK:
            raise CausalStreamError(
                f"group {index} declares causal_availability_clock="
                f"{row.get('causal_availability_clock')!r}; this stream orders on {CAUSAL_CLOCK!r} "
                "and will not reinterpret a row's own clock declaration"
            )
        if row.get("event_group_complete_f_last") is not True:
            raise CausalStreamError(f"group {index} is not F_LAST-closed; an open group has no lawful availability")
        recv_ns = _int_or_none(row.get(CAUSAL_CLOCK))
        clocks = row.get("clocks")
        cutoff = _int_or_none(clocks.get("first_lawful_availability_ns")) if isinstance(clocks, Mapping) else None
        if recv_ns is None or cutoff is None:
            raise CausalStreamError(f"group {index} carries no integer {CAUSAL_CLOCK} / clocks.first_lawful_availability_ns")
        if self._last_recv_ns is not None and (recv_ns < self._last_recv_ns or cutoff < (self._last_cutoff_ns or 0)):
            raise CausalStreamError(
                f"receive clock moved backwards at group {index}: {recv_ns} after {self._last_recv_ns}; "
                "the ledger is not in ts_recv_ns order and cannot be delivered causally"
            )
        # The seven clocks by registry id. A row that carries them is validated and its chain
        # checked; a row that does not (the delivered Sunday ledger predates the field) gets
        # the three the legacy object can support and four declared absences. Refused when
        # partial or disordered - never patched into shape.
        own_clocks = row.get("causal_clocks")
        try:
            if own_clocks is not None:
                causal_clocks = validate_causal_clock_layers(own_clocks)
                causal_clocks_basis = CAUSAL_CLOCKS_ROW_OWN
            else:
                causal_clocks = causal_clock_layers_from_legacy_clocks(clocks, ts_event_ns=int(row["ts_event_ns"]))
                causal_clocks_basis = CAUSAL_CLOCKS_DERIVED_FROM_LEGACY
            causal_clock_chain = check_causal_clock_order(causal_clocks)
        except ClockError as exc:
            raise CausalStreamError(f"group {index} causal_clocks refused: {exc}") from exc
        if int(causal_clock_chain["event_known_by_ns"]) != cutoff:
            raise CausalStreamError(
                f"group {index} clock_event_known_by {causal_clock_chain['event_known_by_ns']} disagrees "
                f"with clocks.first_lawful_availability_ns {cutoff}"
            )

        previous_cutoff = self._last_cutoff_ns
        lifecycle = self._lifecycle.take_lawful(cutoff, previous_cutoff)
        legacy = self._legacy.take_lawful(cutoff, previous_cutoff)

        member_bytes = line
        lifecycle_bytes = b"".join(item_line for item_line, _ in lifecycle)
        legacy_bytes = b"".join(item_line for item_line, _ in legacy)
        delivered = member_bytes + lifecycle_bytes + legacy_bytes
        group_sha256 = hashlib.sha256(delivered).hexdigest()
        carriers = {MEMBER: member_bytes, LIFECYCLE: lifecycle_bytes, LEGACY: legacy_bytes}
        delivered_layers = []
        for group_id, layer_ids in self._layer_ids_by_group.items():
            evidence = hashlib.sha256(b"".join(carriers[c] for c in LAYER_CARRIERS[group_id])).hexdigest()
            for layer_id in layer_ids:
                delivered_layers.append({"layer_id": layer_id, "model_visible": True, "evidence_receipt_sha256": evidence})
        receipt: dict[str, Any] = {
            "schema": GROUP_DELIVERY_SCHEMA,
            "run_id": self.run_id,
            "arm": self.arm,
            "registry_sha256": self.registry_sha256,
            "group_id": index,
            "group_sha256": group_sha256,
            "f_last_closed": True,
            "clocks": {
                "event_time_ns": int(row["ts_event_ns"]),
                "receive_time_ns": recv_ns,
                "availability_time_ns": cutoff,
                "decision_time_ns": int(clocks["decision_ts_recv_ns"]),
            },
            "delivered_layers": delivered_layers,
            "previous_delivery_receipt_sha256": self._previous_receipt_sha256,
            "receipt_sha256": "",
        }
        receipt["receipt_sha256"] = canonical_hash(receipt, omit="receipt_sha256")
        gate = validate_causal_group_delivery_receipt(receipt, registry=self.registry)

        self._last_recv_ns = recv_ns
        self._last_cutoff_ns = cutoff
        self._previous_receipt_sha256 = receipt["receipt_sha256"]
        self._cutoffs.append(cutoff)
        self._groups += 1
        self._bytes += len(delivered)
        self._digest.update(delivered)
        self._member_bytes += len(member_bytes)
        self._member_digest.update(member_bytes)
        if causal_clocks_basis == CAUSAL_CLOCKS_ROW_OWN:
            self._groups_with_row_own_clocks += 1
        else:
            self._groups_with_derived_clocks += 1
        return GroupDelivery(
            group_index=index,
            first_lawful_availability_ns=cutoff,
            group=row,
            group_line=line,
            lifecycle_rows=tuple(r for _, r in lifecycle),
            legacy_rows=tuple(r for _, r in legacy),
            bytes_delivered=len(delivered),
            group_sha256=group_sha256,
            receipt=receipt,
            gate=gate,
            causal_clocks=causal_clocks,
            causal_clocks_basis=causal_clocks_basis,
            causal_clock_chain=causal_clock_chain,
        )

    def iterate(self) -> Iterator[GroupDelivery]:
        while True:
            try:
                yield self.next_group()
            except EndOfStream:
                return

    __iter__ = iterate

    def drain_withheld(self) -> dict[str, list[dict[str, Any]]]:
        """Every sidecar row that could not ride inside a group, with its reason. After exhaustion only."""
        if not self._exhausted:
            raise CausalStreamError(
                "withheld rows are released only once the stream is exhausted; reading them "
                "earlier would be a look-ahead"
            )
        return {LIFECYCLE: list(self._lifecycle.withheld), LEGACY: list(self._legacy.withheld)}

    def stream_receipt(self) -> dict[str, Any]:
        """Close the stream and account for everything delivered and withheld."""
        if not self._closed:
            self._closed = True
            if not self._exhausted:
                self._member.close()
                self._lifecycle.close()
                self._legacy.close()
        receipt: dict[str, Any] = {
            "schema": STREAM_RECEIPT_SCHEMA,
            "run_id": self.run_id,
            "arm": self.arm,
            "registry_sha256": self.registry_sha256,
            "causal_clock": CAUSAL_CLOCK,
            "complete": self._exhausted,
            "groups_delivered": self._groups,
            "bytes_delivered": self._bytes,
            "sha256_delivered": self._digest.hexdigest(),
            "member_ledger": {
                "path": str(self.member_path),
                "rows_delivered": self._groups,
                "bytes": self._member_bytes,
                "sha256": self._member_digest.hexdigest(),
            },
            "lifecycle_ledger": self._lifecycle.receipt(),
            "legacy_ledger": self._legacy.receipt(),
            "first_cutoff_ns": self._cutoffs[0] if self._cutoffs else None,
            "last_cutoff_ns": self._cutoffs[-1] if self._cutoffs else None,
            "cutoffs": list(self._cutoffs),
            "genesis_previous_receipt_sha256": GENESIS_PREVIOUS_RECEIPT_SHA256,
            "last_delivery_receipt_sha256": self._previous_receipt_sha256,
            "layer_carriers": {k: list(v) for k, v in LAYER_CARRIERS.items()},
            "availability_rules": dict(AVAILABILITY_RULES),
            "causal_clock_layers": {
                "carrier": CAUSAL_CLOCKS_CARRIER,
                "layer_ids": list(CAUSAL_CLOCK_LAYER_IDS),
                "groups_with_row_own": self._groups_with_row_own_clocks,
                "groups_with_derived_from_legacy_clocks": self._groups_with_derived_clocks,
            },
            "receipt_sha256": "",
        }
        receipt["receipt_sha256"] = canonical_hash(receipt, omit="receipt_sha256")
        return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stream a whole member ledger in causal order and print the receipt.")
    parser.add_argument("--member-ledger", required=True)
    parser.add_argument("--lifecycle-ledger", default=None)
    parser.add_argument("--legacy-ledger", default=None)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arm", required=True, choices=("A_CLEAN", "A_MEMORY"))
    parser.add_argument("--limit", type=int, default=None, help="deliver at most this many groups (receipt says complete=false)")
    parser.add_argument("--receipt", default=None, help="write the receipt here; stdout then carries it without the cutoff list")
    parser.add_argument("--progress-every", type=int, default=0, help="log a line every N groups to stderr")
    args = parser.parse_args(argv)
    try:
        stream = CausalGroupStream(
            args.member_ledger, args.lifecycle_ledger, args.legacy_ledger,
            run_id=args.run_id, arm=args.arm,
        )
        delivered = 0
        for delivery in stream.iterate():
            delivered += 1
            if args.progress_every and delivered % args.progress_every == 0:
                print(f"delivered {delivered:,} groups; cutoff {delivery.first_lawful_availability_ns}", file=sys.stderr)
            if args.limit is not None and delivered >= args.limit:
                break
        receipt = stream.stream_receipt()
    except CausalStreamError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    if args.receipt:
        Path(args.receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary = {k: v for k, v in receipt.items() if k != "cutoffs"}
        summary["cutoffs_count"] = len(receipt["cutoffs"])
        summary["receipt_path"] = args.receipt
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
