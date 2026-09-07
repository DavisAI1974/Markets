"""BOSS causal-prefix shared types plus the PROBE_ONLY per-group reference seam.

STATUS (C15 Round 3, patch 0005): the per-group chain in this module is a
REFERENCE / SINGLE-INSTRUMENT-PROBE seam only. Real GLBX MBO event groups are
maintained per instrument and interleave in the global record stream, so a
completed group does not own a contiguous global cursor span. The production
global chain is `RecordPrefixChain` in `causal_prefix_records.py`, which
advances once per normalized source record. `ProbeGroupPrefixChain` below
refuses RESULT_BEARING scopes mechanically; there is no result-bearing
validation path in this module at all.

What stays authoritative here and is shared by both modules: `ScopeKind`,
`SourceMember`, `SourceScope`, the error hierarchy, and the domain-separated
hash helpers.

Owner: Stage 4 evidence-identity producer. C15 target builders and the
Stage 4 input builder both CONSUME receipts; neither may mint its own.

What this module is
-------------------
A pure, frozen hash chain over the ordered GLOBAL replay stream of
completed F_LAST groups. One chain per source scope. Every completed-group
transition binds, in this order:

  scheme tag, previous prefix hash, source-scope identity and kind,
  active source member (index + sha256) and any member transition,
  global completed-group ordinal, global source record cursor span
  [cursor_start, cursor_end), declared action count, instrument and
  publisher identity, per-instrument completed-group ordinal (metadata,
  never ordering authority), terminal sequence and terminal ts_recv_ns,
  the ordered normalized actions, and the adapter revision.

What this module is NOT
-----------------------
It does not read DBN, environment variables, AWS, paths, clocks, or any
mutable book state. It does not order anything by timestamp: the global
source record cursor is the only ordering authority, and equal-timestamp
records are distinguished by cursor. There is deliberately no API that
accepts a timestamp-only cutoff (see test 15).

Normalized actions are `NormalizedMbo.public_dict()`-shaped mappings.
They are normalized logical evidence, NOT literal raw DBN bytes. The
physical source object is bound by the member sha256 plus the cursor
span; the normalized group hash binds replay semantics. Do not describe
either as "raw-byte identity".

Contiguity is a CHECKED PRECONDITION, not an assumption. If the owning
replay cannot supply a contiguous global cursor span per completed group
(the confirmed case for multi-instrument GLBX MBO),
`ProbeGroupPrefixChain.advance` raises `ContiguityError`; the caller must
use `RecordPrefixChain` rather than relax the check.

Hashing: SHA-256 over `DOMAIN || 0x00 || canonical_bytes(record)` using the
existing canonical JSON-bytes authority in `causal_packet`. Domain
separation is explicit for the scope genesis record, each group
transition record, the ordered-actions digest, and the receipt digest.
"""
from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass, field, fields
from typing import Any, Mapping, Sequence

try:  # Package import in Markets.
    from .causal_packet import canonical_bytes
except ImportError:  # Direct contract-test execution from this directory.
    from causal_packet import canonical_bytes

__all__ = [
    "PREFIX_SCHEME",
    "ScopeKind",
    "SourceMember",
    "SourceScope",
    "CompletedGroup",
    "PrefixReceipt",
    "ProbeGroupPrefixChain",
    "CausalPrefixError",
    "ContiguityError",
    "OrdinalError",
    "ScopeError",
    "ActionError",
    "ReceiptError",
    "ResultBearingError",
]

PREFIX_SCHEME = "BOSS_CAUSAL_PREFIX_V1"

_DOMAIN_GENESIS = PREFIX_SCHEME + "/GENESIS"
_DOMAIN_GROUP = PREFIX_SCHEME + "/GROUP"
_DOMAIN_ACTIONS = PREFIX_SCHEME + "/ACTIONS"
_DOMAIN_RECEIPT = PREFIX_SCHEME + "/RECEIPT"

_SHA256_HEX_LEN = 64
_F_LAST = 1 << 7
_UNSTABLE_ACTION_FIELDS = frozenset({"source_dbn_object"})


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class CausalPrefixError(ValueError):
    """Base class for every rejection raised by this module."""


class ContiguityError(CausalPrefixError):
    """Global cursor span is not monotonically contiguous with the chain."""


class OrdinalError(CausalPrefixError):
    """Global or per-instrument completed-group ordinal is out of order."""


class ScopeError(CausalPrefixError):
    """Source scope / member / adapter-revision binding violated."""


class ActionError(CausalPrefixError):
    """Ordered normalized actions are missing, malformed, or miscounted."""


class ReceiptError(CausalPrefixError):
    """A receipt does not verify against its own governed hash."""


class ResultBearingError(CausalPrefixError):
    """A non-result-bearing receipt reached a result-bearing boundary."""


# --------------------------------------------------------------------------
# Hash helpers
# --------------------------------------------------------------------------


def _domain_hash(domain: str, payload: Mapping[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(domain.encode("ascii"))
    h.update(b"\x00")
    h.update(canonical_bytes(payload))
    return h.hexdigest()


def _require_sha256_hex(value: Any, what: str) -> str:
    if not isinstance(value, str) or len(value) != _SHA256_HEX_LEN:
        raise ScopeError(f"{what} must be a 64-char hex sha256, got {value!r}")
    if any(char not in "0123456789abcdefABCDEF" for char in value):
        raise ScopeError(f"{what} is not hex: {value!r}")
    return value.lower()


def _require_int(value: Any, what: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CausalPrefixError(f"{what} must be int, got {type(value).__name__}")
    if minimum is not None and value < minimum:
        raise CausalPrefixError(f"{what} must be >= {minimum}, got {value}")
    return value


# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------


class ScopeKind(str, enum.Enum):
    """PROBE_ONLY receipts can never enter a result-bearing path."""

    PROBE_ONLY = "PROBE_ONLY"
    RESULT_BEARING = "RESULT_BEARING"


@dataclass(frozen=True)
class SourceMember:
    """One pinned physical source object inside a scope, in replay order."""

    member_index: int
    member_key: str  # e.g. the S3 key or manifest member name; identity, not a path to open
    sha256: str
    size_bytes: int
    mbo_records: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_index", _require_int(self.member_index, "member_index", minimum=0))
        if not isinstance(self.member_key, str) or not self.member_key:
            raise ScopeError("member_key must be a non-empty str")
        if (
            self.member_key.startswith("/")
            or "\\" in self.member_key
            or "://" in self.member_key
            or any(part in ("", ".", "..") for part in self.member_key.split("/"))
        ):
            raise ScopeError(
                "member_key must be a stable manifest key, not a local path or URI"
            )
        object.__setattr__(self, "sha256", _require_sha256_hex(self.sha256, "member sha256"))
        object.__setattr__(self, "size_bytes", _require_int(self.size_bytes, "size_bytes", minimum=1))
        object.__setattr__(
            self,
            "mbo_records",
            _require_int(self.mbo_records, "mbo_records", minimum=1),
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "member_index": self.member_index,
            "member_key": self.member_key,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "mbo_records": self.mbo_records,
        }


@dataclass(frozen=True)
class SourceScope:
    """Explicitly typed source-scope identity.

    `scope_id` is the caller's declared identity for the scope. For a
    RESULT_BEARING scope it must be the canonical manifest hash from
    `raw_mbo_source_manifest`. For a PROBE_ONLY scope it is a
    SourceScopeReceipt identity that references a pinned member of the
    canonical manifest. This module binds what it is given; it does not
    build manifests.
    """

    kind: ScopeKind
    scope_id: str
    members: tuple[SourceMember, ...]
    adapter_revision: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ScopeKind):
            raise ScopeError("kind must be a ScopeKind")
        object.__setattr__(self, "scope_id", _require_sha256_hex(self.scope_id, "scope_id"))
        members = tuple(self.members)
        if not members:
            raise ScopeError("scope must declare at least one source member")
        for expected, m in enumerate(members):
            if not isinstance(m, SourceMember):
                raise ScopeError("members must be SourceMember instances")
            if m.member_index != expected:
                raise ScopeError(f"members must be indexed 0..n-1 in order; got {m.member_index} at {expected}")
        object.__setattr__(self, "members", members)
        if not isinstance(self.adapter_revision, str) or not self.adapter_revision:
            raise ScopeError("adapter_revision must be a non-empty str")

    def public_dict(self) -> dict[str, Any]:
        return {
            "scheme": PREFIX_SCHEME,
            "kind": self.kind.value,
            "scope_id": self.scope_id,
            "members": [m.public_dict() for m in self.members],
            "adapter_revision": self.adapter_revision,
        }

    def genesis_hash(self) -> str:
        return _domain_hash(_DOMAIN_GENESIS, self.public_dict())

    def member_cursor_bounds(self, member_index: int) -> tuple[int, int]:
        """Return the member's half-open cursor span in the declared scope."""
        member_index = _require_int(member_index, "member_index", minimum=0)
        if member_index < 0 or member_index >= len(self.members):
            raise ScopeError(f"source_member_index {member_index} not in scope")
        start = sum(member.mbo_records for member in self.members[:member_index])
        return start, start + self.members[member_index].mbo_records


# --------------------------------------------------------------------------
# Completed group input
# --------------------------------------------------------------------------


def _freeze_actions(actions: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    if isinstance(actions, (str, bytes, Mapping)) or not isinstance(actions, Sequence):
        raise ActionError("actions must be an ordered sequence of mappings")
    out = []
    for i, a in enumerate(actions):
        if not isinstance(a, Mapping):
            raise ActionError(f"action {i} is not a mapping")
        # Canonicalize eagerly so a non-serializable action fails at construction.
        try:
            canonical_bytes(dict(a))
        except (TypeError, ValueError) as exc:
            raise ActionError(f"action {i} is not canonically serializable: {exc}") from exc
        out.append(dict(a))
    return tuple(out)


def _stable_action(action: Mapping[str, Any]) -> dict[str, Any]:
    """Return the path-independent logical evidence used by the chain.

    ``NormalizedMbo.public_dict()`` carries ``source_dbn_object``, which the
    brownfield replay populates with the local materialization path.  The
    stable source member key and SHA-256 are governed separately, so hashing
    that path would make identical evidence differ across runners.
    """
    return {
        key: value
        for key, value in action.items()
        if key not in _UNSTABLE_ACTION_FIELDS
    }


def _validate_completed_group_actions(group: "CompletedGroup") -> None:
    actions = group.actions
    if not actions:
        raise ActionError("a completed group must contain at least one action")
    for index, action in enumerate(actions):
        flags = action.get("flags")
        if isinstance(flags, bool) or not isinstance(flags, int):
            raise ActionError(f"action {index} flags must be an int")
        flag_is_last = bool(flags & _F_LAST)
        declared_is_last = action.get("is_last")
        if declared_is_last is not None:
            if not isinstance(declared_is_last, bool):
                raise ActionError(f"action {index} is_last must be bool when present")
            if declared_is_last != flag_is_last:
                raise ActionError(f"action {index} is_last disagrees with F_LAST flag")
        if index < len(actions) - 1 and flag_is_last:
            raise ActionError(f"action {index} sets F_LAST before the terminal action")
        if index == len(actions) - 1 and not flag_is_last:
            raise ActionError("completed group terminal action must set F_LAST")

        for field_name, expected in (
            ("instrument_id", group.instrument_id),
            ("publisher_id", group.publisher_id),
        ):
            if field_name in action and action[field_name] != expected:
                raise ActionError(
                    f"action {index} {field_name}={action[field_name]!r} "
                    f"does not match group {expected!r}"
                )

    terminal = actions[-1]
    for field_name, expected in (
        ("sequence", group.terminal_sequence),
        ("ts_recv_ns", group.terminal_ts_recv_ns),
    ):
        if field_name in terminal and terminal[field_name] != expected:
            raise ActionError(
                f"terminal action {field_name}={terminal[field_name]!r} "
                f"does not match group {expected!r}"
            )


@dataclass(frozen=True)
class CompletedGroup:
    """One completed F_LAST group as handed over by the owning replay.

    `cursor_start`/`cursor_end` are GLOBAL source record cursors over the
    ordered replay stream (half-open). `global_group_ordinal` is the
    0-based ordinal of this completed group across ALL instruments.
    `instrument_group_ordinal` is the per-instrument ordinal and is bound
    as metadata only.
    """

    instrument_id: int
    publisher_id: int
    instrument_group_ordinal: int
    global_group_ordinal: int
    source_member_index: int
    cursor_start: int
    cursor_end: int
    terminal_sequence: int
    terminal_ts_recv_ns: int
    declared_action_count: int
    actions: tuple[Mapping[str, Any], ...]
    adapter_revision: str

    def __post_init__(self) -> None:
        for name in (
            "instrument_id",
            "publisher_id",
            "instrument_group_ordinal",
            "global_group_ordinal",
            "source_member_index",
            "cursor_start",
            "cursor_end",
            "terminal_sequence",
            "terminal_ts_recv_ns",
            "declared_action_count",
        ):
            object.__setattr__(self, name, _require_int(getattr(self, name), name, minimum=0))
        object.__setattr__(self, "actions", _freeze_actions(self.actions))
        if not isinstance(self.adapter_revision, str) or not self.adapter_revision:
            raise ScopeError("adapter_revision must be a non-empty str")
        if self.cursor_end <= self.cursor_start:
            raise ContiguityError(
                f"cursor span must be non-empty half-open, got [{self.cursor_start}, {self.cursor_end})"
            )
        if self.declared_action_count != len(self.actions):
            raise ActionError(
                f"declared_action_count={self.declared_action_count} but {len(self.actions)} actions supplied"
            )
        if self.declared_action_count == 0:
            raise ActionError("a completed group must contain at least one action")
        span = self.cursor_end - self.cursor_start
        if span != self.declared_action_count:
            # Contiguity precondition: every record in the span is an action of
            # this group. A mismatch means the group is NOT contiguous in the
            # global source order; stop and escalate (per-record chain).
            raise ContiguityError(
                f"cursor span {span} != action count {self.declared_action_count}; "
                "completed group is not contiguous in global source order"
            )
        _validate_completed_group_actions(self)

    def actions_hash(self) -> str:
        return _domain_hash(
            _DOMAIN_ACTIONS,
            {"actions": [_stable_action(a) for a in self.actions]},
        )

    def stable_actions(self) -> tuple[dict[str, Any], ...]:
        return tuple(_stable_action(action) for action in self.actions)


# --------------------------------------------------------------------------
# Receipt
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PrefixReceipt:
    """Immutable, value-equal receipt for one completed-group transition.

    `receipt_hash` is the governed digest over every other field. Mutating
    any field (via `dataclasses.replace`) yields a receipt whose stored
    hash no longer matches `governed_hash()`, and `verify()` fails.
    """

    scheme: str
    scope_kind: ScopeKind
    scope_id: str
    adapter_revision: str
    source_member_index: int
    source_member_sha256: str
    previous_member_index: int | None
    global_group_ordinal: int
    cursor_start: int
    cursor_end: int
    action_count: int
    instrument_id: int
    publisher_id: int
    instrument_group_ordinal: int
    terminal_sequence: int
    terminal_ts_recv_ns: int
    actions_hash: str
    previous_prefix_hash: str
    prefix_hash: str
    receipt_hash: str = field(default="", compare=True)

    def __post_init__(self) -> None:
        try:
            if self.scheme != PREFIX_SCHEME:
                raise ReceiptError(
                    f"receipt scheme {self.scheme!r} != {PREFIX_SCHEME!r}"
                )
            if not isinstance(self.scope_kind, ScopeKind):
                raise ReceiptError("scope_kind must be a ScopeKind")
            if not isinstance(self.adapter_revision, str) or not self.adapter_revision:
                raise ReceiptError("adapter_revision must be a non-empty str")

            for name in (
                "source_member_index",
                "global_group_ordinal",
                "cursor_start",
                "cursor_end",
                "action_count",
                "instrument_id",
                "publisher_id",
                "instrument_group_ordinal",
                "terminal_sequence",
                "terminal_ts_recv_ns",
            ):
                _require_int(getattr(self, name), name, minimum=0)
            if self.previous_member_index is not None:
                _require_int(
                    self.previous_member_index,
                    "previous_member_index",
                    minimum=0,
                )
            if self.cursor_end <= self.cursor_start:
                raise ReceiptError("receipt cursor span must be non-empty")
            if self.cursor_end - self.cursor_start != self.action_count:
                raise ReceiptError("receipt cursor span must equal action_count")
            if self.action_count == 0:
                raise ReceiptError("receipt action_count must be positive")

            for name in (
                "scope_id",
                "source_member_sha256",
                "actions_hash",
                "previous_prefix_hash",
                "prefix_hash",
            ):
                _require_sha256_hex(getattr(self, name), name)
            if self.receipt_hash:
                _require_sha256_hex(self.receipt_hash, "receipt_hash")
        except ReceiptError:
            raise
        except CausalPrefixError as exc:
            raise ReceiptError(str(exc)) from exc

    def _governed_payload(self) -> dict[str, Any]:
        payload = {}
        for f in fields(self):
            if f.name == "receipt_hash":
                continue
            v = getattr(self, f.name)
            payload[f.name] = v.value if isinstance(v, ScopeKind) else v
        return payload

    def governed_hash(self) -> str:
        return _domain_hash(_DOMAIN_RECEIPT, self._governed_payload())

    def verify(self) -> None:
        if self.scheme != PREFIX_SCHEME:
            raise ReceiptError(f"receipt scheme {self.scheme!r} != {PREFIX_SCHEME!r}")
        if self.receipt_hash != self.governed_hash():
            raise ReceiptError("receipt_hash does not match governed payload")

    def public_dict(self) -> dict[str, Any]:
        d = self._governed_payload()
        d["receipt_hash"] = self.receipt_hash
        return d


def _receipt_for_group(
    *,
    scope: SourceScope,
    group: CompletedGroup,
    previous_prefix_hash: str,
    previous_member_index: int | None,
) -> PrefixReceipt:
    """Reconstruct the one valid receipt for trusted transition inputs."""
    if group.adapter_revision != scope.adapter_revision:
        raise ScopeError(
            f"group adapter_revision {group.adapter_revision!r} "
            f"!= scope {scope.adapter_revision!r}"
        )
    if group.source_member_index >= len(scope.members):
        raise ScopeError(f"source_member_index {group.source_member_index} not in scope")
    previous_prefix_hash = _require_sha256_hex(
        previous_prefix_hash,
        "previous_prefix_hash",
    )
    if previous_member_index is not None:
        previous_member_index = _require_int(
            previous_member_index,
            "previous_member_index",
            minimum=0,
        )

    member = scope.members[group.source_member_index]
    member_start, member_end = scope.member_cursor_bounds(group.source_member_index)
    if group.cursor_start < member_start or group.cursor_end > member_end:
        raise ScopeError(
            f"group cursor [{group.cursor_start}, {group.cursor_end}) lies outside "
            f"source member {group.source_member_index} span "
            f"[{member_start}, {member_end})"
        )
    if previous_member_index is not None:
        if previous_member_index + 1 != group.source_member_index:
            raise ScopeError(
                "previous_member_index must identify the immediately prior member"
            )
        if group.cursor_start != member_start:
            raise ScopeError(
                f"source member {group.source_member_index} must begin at cursor "
                f"{member_start}, got {group.cursor_start}"
            )
    for index, action in enumerate(group.actions):
        action_sha = action.get("source_dbn_sha256")
        if action_sha is not None and _require_sha256_hex(
            action_sha,
            f"action {index} source_dbn_sha256",
        ) != member.sha256:
            raise ScopeError(
                f"action {index} source_dbn_sha256 does not match active member"
            )
    actions_hash = group.actions_hash()
    record = {
        "scheme": PREFIX_SCHEME,
        "record_kind": "COMPLETED_GROUP",
        "previous_prefix_hash": previous_prefix_hash,
        "scope_kind": scope.kind.value,
        "scope_id": scope.scope_id,
        "source_member_index": group.source_member_index,
        "source_member_sha256": member.sha256,
        "previous_member_index": previous_member_index,
        "global_group_ordinal": group.global_group_ordinal,
        "cursor_start": group.cursor_start,
        "cursor_end": group.cursor_end,
        "action_count": group.declared_action_count,
        "instrument_id": group.instrument_id,
        "publisher_id": group.publisher_id,
        "instrument_group_ordinal": group.instrument_group_ordinal,
        "terminal_sequence": group.terminal_sequence,
        "terminal_ts_recv_ns": group.terminal_ts_recv_ns,
        "actions": list(group.stable_actions()),
        "actions_hash": actions_hash,
        "adapter_revision": scope.adapter_revision,
    }
    new_prefix = _domain_hash(_DOMAIN_GROUP, record)
    unsigned = PrefixReceipt(
        scheme=PREFIX_SCHEME,
        scope_kind=scope.kind,
        scope_id=scope.scope_id,
        adapter_revision=scope.adapter_revision,
        source_member_index=group.source_member_index,
        source_member_sha256=member.sha256,
        previous_member_index=previous_member_index,
        global_group_ordinal=group.global_group_ordinal,
        cursor_start=group.cursor_start,
        cursor_end=group.cursor_end,
        action_count=group.declared_action_count,
        instrument_id=group.instrument_id,
        publisher_id=group.publisher_id,
        instrument_group_ordinal=group.instrument_group_ordinal,
        terminal_sequence=group.terminal_sequence,
        terminal_ts_recv_ns=group.terminal_ts_recv_ns,
        actions_hash=actions_hash,
        previous_prefix_hash=previous_prefix_hash,
        prefix_hash=new_prefix,
    )
    return PrefixReceipt(
        **{**unsigned.__dict__, "receipt_hash": unsigned.governed_hash()}
    )


# --------------------------------------------------------------------------
# Chain
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _ChainState:
    prefix_hash: str
    next_cursor: int
    next_global_ordinal: int
    member_index: int
    per_instrument_next_ordinal: tuple[tuple[int, int], ...]  # ((instrument_id, next), ...) sorted


class ProbeGroupPrefixChain:
    """PROBE_ONLY per-completed-group reference chain.

    Mechanically restricted: a RESULT_BEARING scope is rejected at
    construction, so no receipt minted here can carry result-bearing scope
    kind. Use `causal_prefix_records.RecordPrefixChain` for the production
    global chain.

    `advance()` is the only mutator and is transactional: on any rejection
    the chain state is unchanged. State is otherwise immutable value data.
    """

    def __init__(self, scope: SourceScope) -> None:
        if not isinstance(scope, SourceScope):
            raise ScopeError("ProbeGroupPrefixChain requires a SourceScope")
        if scope.kind is not ScopeKind.PROBE_ONLY:
            raise ResultBearingError(
                "ProbeGroupPrefixChain is a reference/probe seam and refuses "
                f"scope kind {scope.kind.value}; use RecordPrefixChain"
            )
        self._scope = scope
        self._state = _ChainState(
            prefix_hash=scope.genesis_hash(),
            next_cursor=0,
            next_global_ordinal=0,
            member_index=0,
            per_instrument_next_ordinal=(),
        )
        self._last_receipt: PrefixReceipt | None = None

    # -- read-only views ----------------------------------------------------

    @property
    def scope(self) -> SourceScope:
        return self._scope

    @property
    def prefix_hash(self) -> str:
        return self._state.prefix_hash

    @property
    def next_cursor(self) -> int:
        return self._state.next_cursor

    @property
    def next_global_ordinal(self) -> int:
        return self._state.next_global_ordinal

    @property
    def member_index(self) -> int:
        return self._state.member_index

    @property
    def last_receipt(self) -> PrefixReceipt | None:
        """Latest transition receipt; callers own any durable history."""
        return self._last_receipt

    def instrument_next_ordinal(self, instrument_id: int) -> int:
        return dict(self._state.per_instrument_next_ordinal).get(instrument_id, 0)

    # -- transition ---------------------------------------------------------

    def advance(self, group: CompletedGroup) -> PrefixReceipt:
        if not isinstance(group, CompletedGroup):
            raise ActionError("advance() requires a CompletedGroup")
        st = self._state
        scope = self._scope

        # Adapter revision binding.
        if group.adapter_revision != scope.adapter_revision:
            raise ScopeError(
                f"group adapter_revision {group.adapter_revision!r} != scope {scope.adapter_revision!r}"
            )

        # Global cursor contiguity: no gap, no overlap, no reversal.
        if group.cursor_start != st.next_cursor:
            if group.cursor_start > st.next_cursor:
                kind = "gap"
            elif group.cursor_end > st.next_cursor:
                kind = "overlap"  # straddles already-chained records
            else:
                kind = "reversal"  # lies entirely inside the chained past
            raise ContiguityError(
                f"cursor {kind}: expected cursor_start={st.next_cursor}, got "
                f"[{group.cursor_start}, {group.cursor_end})"
            )

        # Global ordinal continuity.
        if group.global_group_ordinal != st.next_global_ordinal:
            raise OrdinalError(
                f"global_group_ordinal must be {st.next_global_ordinal}, got {group.global_group_ordinal}"
            )

        # Source member: exists, never regresses; transitions are bound.
        if group.source_member_index >= len(scope.members):
            raise ScopeError(f"source_member_index {group.source_member_index} not in scope")
        if group.source_member_index < st.member_index:
            raise ScopeError(
                f"source member regression: {st.member_index} -> {group.source_member_index}"
            )
        if group.source_member_index > st.member_index + 1:
            raise ScopeError(
                f"source member skip: {st.member_index} -> {group.source_member_index}"
            )
        previous_member_index: int | None = (
            st.member_index if group.source_member_index != st.member_index else None
        )
        member = scope.members[group.source_member_index]
        member_start, member_end = scope.member_cursor_bounds(
            group.source_member_index
        )
        if group.cursor_start < member_start or group.cursor_end > member_end:
            raise ScopeError(
                f"group cursor [{group.cursor_start}, {group.cursor_end}) lies outside "
                f"source member {group.source_member_index} span "
                f"[{member_start}, {member_end})"
            )
        if previous_member_index is not None and group.cursor_start != member_start:
            raise ScopeError(
                f"source member {group.source_member_index} must begin at cursor "
                f"{member_start}, got {group.cursor_start}"
            )

        # Per-instrument ordinal: exact successor of the last seen (metadata).
        per_inst = dict(st.per_instrument_next_ordinal)
        expected_inst = per_inst.get(group.instrument_id, 0)
        if group.instrument_group_ordinal != expected_inst:
            raise OrdinalError(
                f"instrument {group.instrument_id} ordinal must be {expected_inst}, "
                f"got {group.instrument_group_ordinal}"
            )

        receipt = _receipt_for_group(
            scope=scope,
            group=group,
            previous_prefix_hash=st.prefix_hash,
            previous_member_index=previous_member_index,
        )
        receipt.verify()

        # Commit (transactional: nothing above mutated self).
        per_inst[group.instrument_id] = expected_inst + 1
        self._state = _ChainState(
            prefix_hash=receipt.prefix_hash,
            next_cursor=group.cursor_end,
            next_global_ordinal=group.global_group_ordinal + 1,
            member_index=group.source_member_index,
            per_instrument_next_ordinal=tuple(sorted(per_inst.items())),
        )
        self._last_receipt = receipt
        return receipt
