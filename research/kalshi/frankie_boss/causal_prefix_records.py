"""C15 global per-record causal-prefix chain for interleaved MBO groups.

This is the Round-2 R-B design, revised in Round 3 (patch 0005): advance
once for every normalized source record in physical replay order.
Completed-group receipts bind the exact cursor tuple accumulated for that
instrument, so groups may interleave without inventing contiguous spans.

The module is pure and additive.  It reads no files, environment variables,
AWS state, clocks, model state, book state, or Frankie inputs/calculations.

Normalized-action contract (Round 3 ruling on Codex Q4)
-------------------------------------------------------
A `RecordInput.action` must be EXACTLY the `NormalizedMbo.public_dict()`
field set of the bound adapter revision -- no missing keys, no extra keys,
scalar types enforced per field.  The three derived fields (`price`,
`is_snapshot`, `is_last`) must reconcile with their primitives
(`price_raw`, `flags`).  The hash preimage is the public dict minus the
local materialization path `source_dbn_object` only; derived fields stay
in the preimage because they are deterministic functions of bound
primitives, and keeping them leaves Round-2 evidence identity unchanged.

The field set is pinned to `SUPPORTED_ADAPTER_REVISION`.  A scope bound to
any other adapter revision is refused at construction: a new adapter
revision must mint a new field-set constant here, never be accepted
silently.

Receipt authority (Round 3 ruling on the latest-receipt-only boundary)
---------------------------------------------------------------------
Result-bearing authorization is chain context, never a self-hash.  The
chain retains, per instrument, only the (`receipt_hash`,
`global_group_ordinal`) of the last receipt it minted for that instrument
-- bounded by instrument count, no receipt bodies -- plus the single
latest receipt object.  A receipt is authorized while it is still that
instrument's latest completed group.  Consumers bind receipts
synchronously at the F_LAST callback, which is exactly when the real
replay fires.

Export / restore (Round 3 contract for the restart proof)
---------------------------------------------------------
`export_state()` is permitted only when every per-instrument group is
closed, mirroring `mbo_resume_state.export_adapter_state`.  The exported
mapping is bounded (O(instruments)) and self-hashed;
`RecordPrefixChain.restore(scope, state)` verifies the hash and the scope
genesis before accepting it.  Continuous replay and export/restore
replay must yield byte-identical prefix and receipt hashes; any
difference is a coverage defect in this state, fixed by adding the missing
field, never by relaxing the check.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from types import MappingProxyType
from typing import Any, Mapping

try:
    from .causal_prefix import (
        PREFIX_SCHEME,
        ActionError,
        CausalPrefixError,
        ContiguityError,
        ReceiptError,
        ResultBearingError,
        ScopeError,
        ScopeKind,
        SourceScope,
        _domain_hash,
        _require_int,
        _require_sha256_hex,
        _stable_action,
    )
    from .causal_packet import canonical_bytes
except ImportError:  # Direct contract-test execution from this directory.
    from causal_prefix import (  # type: ignore[no-redef]
        PREFIX_SCHEME,
        ActionError,
        CausalPrefixError,
        ContiguityError,
        ReceiptError,
        ResultBearingError,
        ScopeError,
        ScopeKind,
        SourceScope,
        _domain_hash,
        _require_int,
        _require_sha256_hex,
        _stable_action,
    )
    from causal_packet import canonical_bytes  # type: ignore[no-redef]

__all__ = [
    "SUPPORTED_ADAPTER_REVISION",
    "NORMALIZED_MBO_FIELDS_V1",
    "RECORD_STATE_SCHEMA",
    "RecordInput",
    "RecordGroupReceipt",
    "RecordPrefixChain",
    "RecordStateError",
]

_DOMAIN_RECORD = PREFIX_SCHEME + "/RECORD"
_DOMAIN_GROUP_ACTIONS = PREFIX_SCHEME + "/RECORD_GROUP_ACTIONS"
_DOMAIN_GROUP_RECEIPT = PREFIX_SCHEME + "/RECORD_GROUP_RECEIPT"
_DOMAIN_STATE = PREFIX_SCHEME + "/RECORD_CHAIN_STATE"

RECORD_STATE_SCHEMA = "BOSS_CAUSAL_PREFIX_RECORD_STATE_V1"

# Mirrors research/ng_exhaustion_mbo_v4_state_adapter_20260820.py at the
# base commit. Values are copied, not imported: this module must stay pure
# and must not import the adapter package.
SUPPORTED_ADAPTER_REVISION = "NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823"
_F_LAST = 1 << 7
_F_SNAPSHOT = 1 << 5
_PRICE_SCALE = 1_000_000_000
_UNDEF_PRICE = 9_000_000_000_000_000_000
_VALID_ACTIONS = frozenset("ACMRTFN")
_VALID_SIDES = frozenset("ABN")

# Exact NormalizedMbo.public_dict() key set for SUPPORTED_ADAPTER_REVISION.
NORMALIZED_MBO_FIELDS_V1: tuple[str, ...] = (
    "instrument_id",
    "publisher_id",
    "channel_id",
    "order_id",
    "action",
    "side",
    "price_raw",
    "size",
    "flags",
    "sequence",
    "ts_event_ns",
    "ts_recv_ns",
    "ts_in_delta_ns",
    "raw_symbol",
    "source_dbn_object",
    "source_dbn_sha256",
    "price",
    "is_snapshot",
    "is_last",
)
_FIELD_SET = frozenset(NORMALIZED_MBO_FIELDS_V1)
_NON_NEGATIVE_INTS = (
    "instrument_id",
    "publisher_id",
    "channel_id",
    "order_id",
    "size",
    "flags",
    "sequence",
    "ts_event_ns",
    "ts_recv_ns",
)
_ANY_INTS = ("price_raw", "ts_in_delta_ns")  # sign-carrying in DBN


class RecordStateError(CausalPrefixError):
    """Exported/restored chain state is malformed, mismatched, or unsafe."""


def _decimal_price(raw: int) -> float | None:
    if abs(raw) >= _UNDEF_PRICE:
        return None
    return raw / _PRICE_SCALE


def _validate_normalized_action(action: Mapping[str, Any]) -> dict[str, Any]:
    """Enforce the exact NormalizedMbo.public_dict() contract."""
    if not isinstance(action, Mapping):
        raise ActionError("normalized action must be a mapping")
    keys = set(action)
    missing = _FIELD_SET - keys
    extra = keys - _FIELD_SET
    if missing or extra:
        raise ActionError(
            "normalized action must carry exactly the NormalizedMbo field set; "
            f"missing={sorted(missing)} extra={sorted(str(k) for k in extra)}"
        )
    out: dict[str, Any] = {}
    try:
        for name in _NON_NEGATIVE_INTS:
            out[name] = _require_int(action[name], f"action {name}", minimum=0)
        for name in _ANY_INTS:
            out[name] = _require_int(action[name], f"action {name}")
    except CausalPrefixError as exc:
        raise ActionError(str(exc)) from exc
    if out["instrument_id"] <= 0:
        raise ActionError("action instrument_id must be positive")
    for name, allowed in (("action", _VALID_ACTIONS), ("side", _VALID_SIDES)):
        value = action[name]
        if not isinstance(value, str) or value not in allowed:
            raise ActionError(f"action {name}={value!r} not in {sorted(allowed)}")
        out[name] = value
    for name in ("raw_symbol", "source_dbn_object"):
        value = action[name]
        if value is not None and not isinstance(value, str):
            raise ActionError(f"action {name} must be str or None")
        out[name] = value
    try:
        out["source_dbn_sha256"] = _require_sha256_hex(
            action["source_dbn_sha256"], "action source_dbn_sha256"
        )
    except CausalPrefixError as exc:
        raise ActionError(str(exc)) from exc

    # Derived fields: present, typed, and reconciled with their primitives.
    flags = out["flags"]
    for name, bit in (("is_last", _F_LAST), ("is_snapshot", _F_SNAPSHOT)):
        declared = action[name]
        if not isinstance(declared, bool):
            raise ActionError(f"normalized action {name} must be bool")
        if declared != bool(flags & bit):
            raise ActionError(f"normalized action {name} disagrees with flags")
        out[name] = declared
    price = action["price"]
    expected_price = _decimal_price(out["price_raw"])
    if price is None:
        if expected_price is not None:
            raise ActionError("action price is None but price_raw is defined")
    else:
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise ActionError("action price must be float or None")
        if expected_price is None or float(price) != expected_price:
            raise ActionError("action price does not equal price_raw / 1e9")
    out["price"] = expected_price
    try:
        canonical_bytes(out)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ActionError(f"action is not canonically serializable: {exc}") from exc
    return out


@dataclass(frozen=True)
class RecordInput:
    """One normalized MBO record plus its authoritative replay cursor.

    `cursor` is the 0-based global index of this record among MBO records
    in declared source-member order (the replay's `record_count` before
    it is incremented for this record).
    """

    cursor: int
    source_member_index: int
    action: Mapping[str, Any]
    adapter_revision: str
    instrument_id: int | None = None
    publisher_id: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cursor", _require_int(self.cursor, "cursor", minimum=0))
        object.__setattr__(
            self,
            "source_member_index",
            _require_int(self.source_member_index, "source_member_index", minimum=0),
        )
        if not isinstance(self.adapter_revision, str) or not self.adapter_revision:
            raise ScopeError("adapter_revision must be a non-empty str")
        validated = _validate_normalized_action(self.action)
        object.__setattr__(self, "action", MappingProxyType(validated))
        for name in ("instrument_id", "publisher_id"):
            action_value = validated[name]
            envelope_value = getattr(self, name)
            if envelope_value is None:
                object.__setattr__(self, name, action_value)
                continue
            envelope_value = _require_int(envelope_value, name, minimum=0)
            if envelope_value != action_value:
                raise ActionError(
                    f"action {name}={action_value} does not match envelope {envelope_value}"
                )

    @property
    def is_last(self) -> bool:
        return bool(self.action["is_last"])

    def stable_action(self) -> dict[str, Any]:
        return _stable_action(self.action)


@dataclass(frozen=True)
class RecordGroupReceipt:
    """Receipt for one F_LAST group closed by the global record chain."""

    scheme: str
    scope_kind: ScopeKind
    scope_id: str
    adapter_revision: str
    source_member_index: int
    source_member_sha256: str
    global_group_ordinal: int
    record_cursors: tuple[int, ...]
    action_count: int
    instrument_id: int
    publisher_id: int
    instrument_group_ordinal: int
    terminal_sequence: int
    terminal_ts_recv_ns: int
    actions_hash: str
    terminal_prefix_hash: str
    receipt_hash: str = field(default="", compare=True)

    def __post_init__(self) -> None:
        try:
            if self.scheme != PREFIX_SCHEME:
                raise ReceiptError(f"receipt scheme {self.scheme!r} != {PREFIX_SCHEME!r}")
            if not isinstance(self.scope_kind, ScopeKind):
                raise ReceiptError("scope_kind must be a ScopeKind")
            if not isinstance(self.adapter_revision, str) or not self.adapter_revision:
                raise ReceiptError("adapter_revision must be a non-empty str")
            for name in (
                "source_member_index",
                "global_group_ordinal",
                "action_count",
                "instrument_id",
                "publisher_id",
                "instrument_group_ordinal",
                "terminal_sequence",
                "terminal_ts_recv_ns",
            ):
                _require_int(getattr(self, name), name, minimum=0)

            cursors = tuple(self.record_cursors)
            if not cursors:
                raise ReceiptError("record_cursors must not be empty")
            for index, cursor in enumerate(cursors):
                _require_int(cursor, f"record_cursors[{index}]", minimum=0)
            if any(left >= right for left, right in zip(cursors, cursors[1:])):
                raise ReceiptError("record_cursors must be strictly increasing")
            object.__setattr__(self, "record_cursors", cursors)
            if self.action_count != len(cursors):
                raise ReceiptError("action_count must equal len(record_cursors)")

            for name in ("scope_id", "source_member_sha256", "actions_hash", "terminal_prefix_hash"):
                _require_sha256_hex(getattr(self, name), name)
            if self.receipt_hash:
                _require_sha256_hex(self.receipt_hash, "receipt_hash")
        except ReceiptError:
            raise
        except CausalPrefixError as exc:
            raise ReceiptError(str(exc)) from exc

    def _governed_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for item in fields(self):
            if item.name == "receipt_hash":
                continue
            value = getattr(self, item.name)
            if isinstance(value, ScopeKind):
                value = value.value
            elif isinstance(value, tuple):
                value = list(value)
            payload[item.name] = value
        return payload

    def governed_hash(self) -> str:
        return _domain_hash(_DOMAIN_GROUP_RECEIPT, self._governed_payload())

    def verify(self) -> None:
        if self.receipt_hash != self.governed_hash():
            raise ReceiptError("receipt_hash does not match governed payload")

    def public_dict(self) -> dict[str, Any]:
        payload = self._governed_payload()
        payload["receipt_hash"] = self.receipt_hash
        return payload


class _OpenGroup:
    """Mutable per-instrument accumulator; owned exclusively by the chain.

    Lists are appended in place after validation, so a group of N records
    costs O(N), not O(N^2). Mirrors the adapter's own `event_group` list.
    """

    __slots__ = ("member_index", "publisher_id", "cursors", "actions")

    def __init__(self, member_index: int, publisher_id: int) -> None:
        self.member_index = member_index
        self.publisher_id = publisher_id
        self.cursors: list[int] = []
        self.actions: list[dict[str, Any]] = []


@dataclass(frozen=True)
class _InstrumentAuth:
    """Bounded per-instrument authority: the last minted receipt's identity."""

    next_ordinal: int
    last_receipt_hash: str | None
    last_global_group_ordinal: int | None


class RecordPrefixChain:
    """One global chain advanced exactly once per normalized source record."""

    def __init__(self, scope: SourceScope) -> None:
        if not isinstance(scope, SourceScope):
            raise ScopeError("RecordPrefixChain requires a SourceScope")
        if scope.adapter_revision != SUPPORTED_ADAPTER_REVISION:
            raise ScopeError(
                f"scope adapter_revision {scope.adapter_revision!r} is not the "
                f"supported normalized-action schema {SUPPORTED_ADAPTER_REVISION!r}"
            )
        self._scope = scope
        self._prefix_hash = scope.genesis_hash()
        self._next_cursor = 0
        self._member_index = 0
        self._next_global_group_ordinal = 0
        self._instruments: dict[int, _InstrumentAuth] = {}
        self._open_groups: dict[int, _OpenGroup] = {}
        self._last_receipt: RecordGroupReceipt | None = None

    # -- read-only views ----------------------------------------------------

    @property
    def scope(self) -> SourceScope:
        return self._scope

    @property
    def prefix_hash(self) -> str:
        return self._prefix_hash

    @property
    def next_cursor(self) -> int:
        return self._next_cursor

    @property
    def member_index(self) -> int:
        return self._member_index

    @property
    def next_global_group_ordinal(self) -> int:
        return self._next_global_group_ordinal

    @property
    def open_instruments(self) -> tuple[int, ...]:
        return tuple(sorted(self._open_groups))

    @property
    def last_receipt(self) -> RecordGroupReceipt | None:
        """Latest receipt minted by this chain; callers own durable history."""
        return self._last_receipt

    def instrument_next_ordinal(self, instrument_id: int) -> int:
        auth = self._instruments.get(instrument_id)
        return 0 if auth is None else auth.next_ordinal

    # -- transition ---------------------------------------------------------

    def _expected_member_index(self, cursor: int) -> int:
        current = self._member_index
        _, end = self._scope.member_cursor_bounds(current)
        if cursor < end:
            return current
        if cursor == end and current + 1 < len(self._scope.members):
            return current + 1
        raise ScopeError(f"cursor {cursor} lies outside the declared source scope")

    def advance(self, record: RecordInput) -> RecordGroupReceipt | None:
        """Advance one global record; return a receipt only when F_LAST closes.

        Transactional: every check runs before any state is touched.
        """
        if not isinstance(record, RecordInput):
            raise ActionError("advance() requires a RecordInput")
        scope = self._scope
        if record.adapter_revision != scope.adapter_revision:
            raise ScopeError(
                f"record adapter_revision {record.adapter_revision!r} "
                f"!= scope {scope.adapter_revision!r}"
            )
        if record.cursor != self._next_cursor:
            kind = "gap" if record.cursor > self._next_cursor else "reversal"
            raise ContiguityError(
                f"cursor {kind}: expected {self._next_cursor}, got {record.cursor}"
            )

        expected_member = self._expected_member_index(record.cursor)
        if record.source_member_index != expected_member:
            raise ScopeError(
                f"cursor {record.cursor} belongs to source member "
                f"{expected_member}, got {record.source_member_index}"
            )
        if expected_member != self._member_index and self._open_groups:
            raise ScopeError("source member transition with an open group")
        member = scope.members[expected_member]
        if record.action["source_dbn_sha256"] != member.sha256:
            raise ScopeError("action source_dbn_sha256 does not match active member")

        instrument_id = record.instrument_id
        open_group = self._open_groups.get(instrument_id)
        if open_group is not None and (
            open_group.member_index != expected_member
            or open_group.publisher_id != record.publisher_id
        ):
            raise ActionError("instrument group identity changed before F_LAST")

        stable_action = record.stable_action()
        new_prefix = _domain_hash(
            _DOMAIN_RECORD,
            {
                "scheme": PREFIX_SCHEME,
                "record_kind": "NORMALIZED_MBO_RECORD",
                "previous_prefix_hash": self._prefix_hash,
                "scope_kind": scope.kind.value,
                "scope_id": scope.scope_id,
                "source_member_index": expected_member,
                "source_member_sha256": member.sha256,
                "cursor": record.cursor,
                "instrument_id": instrument_id,
                "publisher_id": record.publisher_id,
                "action": stable_action,
                "adapter_revision": scope.adapter_revision,
            },
        )

        receipt: RecordGroupReceipt | None = None
        if record.is_last:
            cursors = (open_group.cursors if open_group else []) + [record.cursor]
            actions = (open_group.actions if open_group else []) + [stable_action]
            auth = self._instruments.get(instrument_id)
            instrument_ordinal = 0 if auth is None else auth.next_ordinal
            unsigned = RecordGroupReceipt(
                scheme=PREFIX_SCHEME,
                scope_kind=scope.kind,
                scope_id=scope.scope_id,
                adapter_revision=scope.adapter_revision,
                source_member_index=expected_member,
                source_member_sha256=member.sha256,
                global_group_ordinal=self._next_global_group_ordinal,
                record_cursors=tuple(cursors),
                action_count=len(actions),
                instrument_id=instrument_id,
                publisher_id=record.publisher_id,
                instrument_group_ordinal=instrument_ordinal,
                terminal_sequence=record.action["sequence"],
                terminal_ts_recv_ns=record.action["ts_recv_ns"],
                actions_hash=_domain_hash(_DOMAIN_GROUP_ACTIONS, {"actions": actions}),
                terminal_prefix_hash=new_prefix,
            )
            receipt = RecordGroupReceipt(
                **{**unsigned.__dict__, "receipt_hash": unsigned.governed_hash()}
            )
            receipt.verify()

        # ---- commit: nothing above mutated self ----------------------------
        if receipt is None:
            if open_group is None:
                open_group = _OpenGroup(expected_member, record.publisher_id)
                self._open_groups[instrument_id] = open_group
            open_group.cursors.append(record.cursor)
            open_group.actions.append(stable_action)
        else:
            self._open_groups.pop(instrument_id, None)
            self._instruments[instrument_id] = _InstrumentAuth(
                next_ordinal=receipt.instrument_group_ordinal + 1,
                last_receipt_hash=receipt.receipt_hash,
                last_global_group_ordinal=receipt.global_group_ordinal,
            )
            self._next_global_group_ordinal += 1
            self._last_receipt = receipt
        self._prefix_hash = new_prefix
        self._next_cursor = record.cursor + 1
        self._member_index = expected_member
        return receipt

    # -- result-bearing authority -------------------------------------------

    def validate_result_bearing(self, receipt: RecordGroupReceipt) -> RecordGroupReceipt:
        """Authorize a receipt against this chain's own bounded context.

        The receipt must be the latest one this chain minted for its
        instrument. Authority comes from the chain having minted it, not
        from the receipt's self-hash.
        """
        if not isinstance(receipt, RecordGroupReceipt):
            raise ReceiptError("expected a RecordGroupReceipt")
        receipt.verify()
        if self._scope.kind is not ScopeKind.RESULT_BEARING:
            raise ResultBearingError(
                f"scope {self._scope.kind.value} cannot enter a result-bearing path"
            )
        if (
            receipt.scope_kind is not ScopeKind.RESULT_BEARING
            or receipt.scope_id != self._scope.scope_id
            or receipt.adapter_revision != self._scope.adapter_revision
        ):
            raise ReceiptError("receipt scope does not match authoritative chain")
        auth = self._instruments.get(receipt.instrument_id)
        if (
            auth is None
            or auth.last_receipt_hash != receipt.receipt_hash
            or auth.last_global_group_ordinal != receipt.global_group_ordinal
        ):
            raise ReceiptError(
                "receipt does not match authoritative chain context for instrument "
                f"{receipt.instrument_id}"
            )
        return receipt

    # -- export / restore ---------------------------------------------------

    def export_state(self) -> dict[str, Any]:
        """Bounded, self-hashed chain state at an all-groups-closed boundary."""
        if self._open_groups:
            raise RecordStateError(
                "chain state export requires every instrument group to be closed; "
                f"open instruments: {self.open_instruments}"
            )
        state: dict[str, Any] = {
            "schema": RECORD_STATE_SCHEMA,
            "scheme": PREFIX_SCHEME,
            "scope_kind": self._scope.kind.value,
            "scope_id": self._scope.scope_id,
            "scope_genesis_hash": self._scope.genesis_hash(),
            "adapter_revision": self._scope.adapter_revision,
            "prefix_hash": self._prefix_hash,
            "next_cursor": self._next_cursor,
            "member_index": self._member_index,
            "next_global_group_ordinal": self._next_global_group_ordinal,
            "instruments": [
                {
                    "instrument_id": iid,
                    "next_ordinal": auth.next_ordinal,
                    "last_receipt_hash": auth.last_receipt_hash,
                    "last_global_group_ordinal": auth.last_global_group_ordinal,
                }
                for iid, auth in sorted(self._instruments.items())
            ],
            "last_receipt": None if self._last_receipt is None else self._last_receipt.public_dict(),
            "state_hash": "",
        }
        state["state_hash"] = _domain_hash(_DOMAIN_STATE, {**state, "state_hash": ""})
        return state

    @classmethod
    def restore(cls, scope: SourceScope, state: Mapping[str, Any]) -> "RecordPrefixChain":
        """Rebuild a chain from `export_state()` output under the same scope."""
        chain = cls(scope)
        try:
            if not isinstance(state, Mapping):
                raise RecordStateError("state must be a mapping")
            expected_keys = {
                "schema", "scheme", "scope_kind", "scope_id", "scope_genesis_hash",
                "adapter_revision", "prefix_hash", "next_cursor", "member_index",
                "next_global_group_ordinal", "instruments", "last_receipt", "state_hash",
            }
            if set(state) != expected_keys:
                raise RecordStateError("state has unexpected or missing keys")
            if state["schema"] != RECORD_STATE_SCHEMA or state["scheme"] != PREFIX_SCHEME:
                raise RecordStateError("state schema/scheme mismatch")
            recomputed = _domain_hash(_DOMAIN_STATE, {**dict(state), "state_hash": ""})
            if state["state_hash"] != recomputed:
                raise RecordStateError("state_hash does not match state payload")
            if (
                state["scope_kind"] != scope.kind.value
                or state["scope_id"] != scope.scope_id
                or state["scope_genesis_hash"] != scope.genesis_hash()
                or state["adapter_revision"] != scope.adapter_revision
            ):
                raise RecordStateError("state was exported under a different scope")

            prefix = _require_sha256_hex(state["prefix_hash"], "prefix_hash")
            next_cursor = _require_int(state["next_cursor"], "next_cursor", minimum=0)
            member_index = _require_int(state["member_index"], "member_index", minimum=0)
            next_gord = _require_int(
                state["next_global_group_ordinal"], "next_global_group_ordinal", minimum=0
            )
            if member_index >= len(scope.members):
                raise RecordStateError("member_index outside declared scope")
            start, end = scope.member_cursor_bounds(member_index)
            if not (start <= next_cursor <= end) or (next_cursor > 0 and next_cursor == start):
                raise RecordStateError("next_cursor lies outside the active member span")
            if next_cursor == 0 and (
                prefix != scope.genesis_hash() or next_gord != 0 or member_index != 0
            ):
                raise RecordStateError("empty chain must sit at genesis")
            if next_cursor > 0 and not (1 <= next_gord <= next_cursor):
                raise RecordStateError("non-empty closed chain requires completed groups")

            instruments: dict[int, _InstrumentAuth] = {}
            last_ordinals: set[int] = set()
            rows = state["instruments"]
            if not isinstance(rows, list):
                raise RecordStateError("instruments must be a list")
            for row in rows:
                if not isinstance(row, Mapping) or set(row) != {
                    "instrument_id", "next_ordinal", "last_receipt_hash", "last_global_group_ordinal",
                }:
                    raise RecordStateError("instrument row has unexpected keys")
                iid = _require_int(row["instrument_id"], "instrument_id", minimum=1)
                if iid in instruments:
                    raise RecordStateError(f"duplicate instrument {iid}")
                nxt = _require_int(row["next_ordinal"], "next_ordinal", minimum=1)
                rh = _require_sha256_hex(row["last_receipt_hash"], "last_receipt_hash")
                gord = _require_int(
                    row["last_global_group_ordinal"], "last_global_group_ordinal", minimum=0
                )
                if gord >= next_gord:
                    raise RecordStateError("instrument ordinal exceeds global ordinal")
                if gord in last_ordinals or nxt > gord + 1:
                    raise RecordStateError("impossible per-instrument group history")
                last_ordinals.add(gord)
                instruments[iid] = _InstrumentAuth(nxt, rh, gord)
            total_groups = sum(a.next_ordinal for a in instruments.values())
            if total_groups != next_gord:
                raise RecordStateError("per-instrument ordinals do not sum to the global ordinal")

            last_receipt: RecordGroupReceipt | None = None
            raw_last = state["last_receipt"]
            if raw_last is not None:
                if not isinstance(raw_last, Mapping):
                    raise RecordStateError("last_receipt must be a mapping or None")
                payload = dict(raw_last)
                payload["scope_kind"] = ScopeKind(payload["scope_kind"])
                payload["record_cursors"] = tuple(payload["record_cursors"])
                last_receipt = RecordGroupReceipt(**payload)
                last_receipt.verify()
                auth = instruments.get(last_receipt.instrument_id)
                if (
                    auth is None
                    or auth.last_receipt_hash != last_receipt.receipt_hash
                    or auth.last_global_group_ordinal != last_receipt.global_group_ordinal
                    or auth.next_ordinal != last_receipt.instrument_group_ordinal + 1
                    or last_receipt.global_group_ordinal != next_gord - 1
                    or last_receipt.terminal_prefix_hash != prefix
                    or last_receipt.scope_kind is not scope.kind
                    or last_receipt.scope_id != scope.scope_id
                    or last_receipt.adapter_revision != scope.adapter_revision
                    or last_receipt.source_member_index != member_index
                    or last_receipt.source_member_sha256 != scope.members[member_index].sha256
                    or any(not start <= cursor < end for cursor in last_receipt.record_cursors)
                    # All groups are closed at export, so the last record
                    # chained was the terminal record of the last receipt.
                    or last_receipt.record_cursors[-1] + 1 != next_cursor
                ):
                    raise RecordStateError("last_receipt is not the terminal receipt of this state")
            elif next_gord != 0:
                raise RecordStateError("last_receipt missing for a non-empty chain")
        except RecordStateError:
            raise
        except (CausalPrefixError, KeyError, TypeError, ValueError) as exc:
            raise RecordStateError(f"malformed chain state: {exc}") from exc

        chain._prefix_hash = prefix
        chain._next_cursor = next_cursor
        chain._member_index = member_index
        chain._next_global_group_ordinal = next_gord
        chain._instruments = instruments
        chain._last_receipt = last_receipt
        return chain
