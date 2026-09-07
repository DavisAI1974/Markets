"""Contract tests for the C15 global per-record causal-prefix chain.

Synthetic normalized MBO only: no DBN, AWS, environment, clocks, or book.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).resolve().parents[1]
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from causal_prefix import (
    ActionError,
    ContiguityError,
    ReceiptError,
    ResultBearingError,
    ScopeError,
    ScopeKind,
    SourceMember,
    SourceScope,
)
from causal_prefix_records import (
    RecordGroupReceipt,
    RecordInput,
    RecordPrefixChain,
)

ADAPTER = "NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823"
SHA_A = "a" * 64
SHA_B = "b" * 64
SCOPE_ID = "5" * 64


def member(index: int, sha: str, records: int) -> SourceMember:
    return SourceMember(
        member_index=index,
        member_key=f"day-{index}.mbo.dbn.zst",
        sha256=sha,
        size_bytes=100 + index,
        mbo_records=records,
    )


def scope(
    kind: ScopeKind = ScopeKind.RESULT_BEARING,
    members: tuple[SourceMember, ...] | None = None,
) -> SourceScope:
    return SourceScope(
        kind=kind,
        scope_id=SCOPE_ID,
        members=members or (member(0, SHA_A, 100),),
        adapter_revision=ADAPTER,
    )


def action(
    *,
    instrument: int,
    sequence: int,
    last: bool,
    source_sha: str = SHA_A,
    source_path: str = "/tmp/day-0.mbo.dbn.zst",
) -> dict:
    return {
        "instrument_id": instrument,
        "publisher_id": 1,
        "channel_id": 1,
        "order_id": sequence,
        "action": "A",
        "side": "B",
        "price_raw": 100,
        "size": 1,
        "flags": 128 if last else 0,
        "sequence": sequence,
        "ts_event_ns": 1_000 + sequence,
        "ts_recv_ns": 2_000 + sequence,
        "ts_in_delta_ns": 0,
        "raw_symbol": "NGZ6",
        "source_dbn_object": source_path,
        "source_dbn_sha256": source_sha,
        "price": 0.0000001,
        "is_snapshot": False,
        "is_last": last,
    }


def record(
    cursor: int,
    *,
    instrument: int = 1,
    sequence: int | None = None,
    last: bool = True,
    member_index: int = 0,
    source_sha: str = SHA_A,
    source_path: str = "/tmp/day-0.mbo.dbn.zst",
) -> RecordInput:
    seq = cursor + 1 if sequence is None else sequence
    return RecordInput(
        cursor=cursor,
        source_member_index=member_index,
        action=action(
            instrument=instrument,
            sequence=seq,
            last=last,
            source_sha=source_sha,
            source_path=source_path,
        ),
        adapter_revision=ADAPTER,
    )


def test_interleaved_open_groups_bind_exact_global_record_order():
    chain = RecordPrefixChain(scope())

    assert chain.advance(record(0, instrument=1, last=False)) is None
    b = chain.advance(record(1, instrument=2, last=True))
    a = chain.advance(record(2, instrument=1, last=True))

    assert isinstance(a, RecordGroupReceipt)
    assert isinstance(b, RecordGroupReceipt)
    assert b.record_cursors == (1,)
    assert a.record_cursors == (0, 2)
    assert b.global_group_ordinal == 0
    assert a.global_group_ordinal == 1
    assert b.terminal_prefix_hash != a.terminal_prefix_hash
    assert chain.next_cursor == 3


def test_record_order_and_single_mutation_change_terminal_prefix():
    first = RecordPrefixChain(scope())
    first.advance(record(0, instrument=1, last=False))
    r1 = first.advance(record(1, instrument=2, last=True))

    second = RecordPrefixChain(scope())
    second.advance(record(0, instrument=2, last=True))
    r2 = second.advance(record(1, instrument=1, last=False))

    assert r1 is not None and r2 is None
    assert first.prefix_hash != second.prefix_hash

    mutated_action = action(instrument=2, sequence=2, last=True)
    mutated_action["size"] = 2
    third = RecordPrefixChain(scope())
    third.advance(record(0, instrument=1, last=False))
    r3 = third.advance(
        RecordInput(
            cursor=1,
            source_member_index=0,
            action=mutated_action,
            adapter_revision=ADAPTER,
        )
    )
    assert r3 is not None and r1.terminal_prefix_hash != r3.terminal_prefix_hash


def test_local_materialization_path_is_not_evidence_identity():
    left = RecordPrefixChain(scope()).advance(
        record(0, source_path="/runner-a/day.dbn")
    )
    right = RecordPrefixChain(scope()).advance(
        record(0, source_path="/runner-b/day.dbn")
    )
    assert left == right


@pytest.mark.parametrize("cursor", [2, 0])
def test_cursor_gap_or_reversal_is_rejected_transactionally(cursor: int):
    chain = RecordPrefixChain(scope())
    first = chain.advance(record(0))
    before = (chain.prefix_hash, chain.next_cursor, chain.last_receipt)
    with pytest.raises(ContiguityError):
        chain.advance(record(cursor))
    assert first is not None
    assert (chain.prefix_hash, chain.next_cursor, chain.last_receipt) == before


def test_member_transition_requires_exact_boundary_and_no_open_group():
    scoped = scope(
        members=(member(0, SHA_A, 2), member(1, SHA_B, 2))
    )

    early = RecordPrefixChain(scoped)
    with pytest.raises(ScopeError):
        early.advance(record(0, member_index=1, source_sha=SHA_B))

    open_group = RecordPrefixChain(scoped)
    open_group.advance(record(0, last=False))
    open_group.advance(record(1, instrument=2, last=True))
    with pytest.raises(ScopeError, match="open group"):
        open_group.advance(record(2, member_index=1, source_sha=SHA_B))

    clean = RecordPrefixChain(scoped)
    clean.advance(record(0))
    clean.advance(record(1))
    transitioned = clean.advance(
        record(2, member_index=1, source_sha=SHA_B)
    )
    assert transitioned is not None
    assert transitioned.source_member_index == 1


def test_action_identity_and_source_hash_must_match_envelope():
    bad_instrument = action(instrument=7, sequence=1, last=True)
    with pytest.raises(ActionError, match="instrument_id"):
        RecordInput(
            cursor=0,
            source_member_index=0,
            instrument_id=8,
            publisher_id=1,
            action=bad_instrument,
            adapter_revision=ADAPTER,
        )

    chain = RecordPrefixChain(scope())
    with pytest.raises(ScopeError, match="sha256"):
        chain.advance(record(0, source_sha=SHA_B))


def test_result_bearing_validation_uses_authoritative_chain_context():
    result_chain = RecordPrefixChain(scope())
    receipt = result_chain.advance(record(0))
    assert receipt is not None
    assert result_chain.validate_result_bearing(receipt) is receipt

    unsigned = dataclasses.replace(
        receipt,
        terminal_prefix_hash="c" * 64,
        receipt_hash="",
    )
    forged = dataclasses.replace(
        unsigned,
        receipt_hash=unsigned.governed_hash(),
    )
    forged.verify()
    with pytest.raises(ReceiptError, match="authoritative"):
        result_chain.validate_result_bearing(forged)

    probe_chain = RecordPrefixChain(scope(kind=ScopeKind.PROBE_ONLY))
    probe = probe_chain.advance(record(0))
    assert probe is not None
    with pytest.raises(ResultBearingError):
        probe_chain.validate_result_bearing(probe)


def test_receipt_structure_and_memory_are_bounded():
    chain = RecordPrefixChain(scope())
    latest = None
    for cursor in range(100):
        latest = chain.advance(record(cursor))
    assert chain.last_receipt == latest
    assert not hasattr(chain, "receipts")
    with pytest.raises(ReceiptError):
        dataclasses.replace(latest, record_cursors=(True,))


def test_adapter_revision_mismatch_and_non_boolean_is_last_rejected():
    wrong = dataclasses.replace(record(0), adapter_revision="OTHER")
    with pytest.raises(ScopeError):
        RecordPrefixChain(scope()).advance(wrong)

    bad = action(instrument=1, sequence=1, last=True)
    bad["is_last"] = 1
    with pytest.raises(ActionError, match="is_last"):
        RecordInput(
            cursor=0,
            source_member_index=0,
            action=bad,
            adapter_revision=ADAPTER,
        )


# ---------------------------------------------------------------------------
# Round 3 (patch 0005) additions
# ---------------------------------------------------------------------------

from causal_prefix_records import (  # noqa: E402
    NORMALIZED_MBO_FIELDS_V1,
    SUPPORTED_ADAPTER_REVISION,
    RecordStateError,
)


def _input(act: dict, cursor: int = 0) -> RecordInput:
    return RecordInput(
        cursor=cursor,
        source_member_index=0,
        action=act,
        adapter_revision=ADAPTER,
    )


def test_r3_action_must_be_exact_normalized_mbo_field_set():
    base = action(instrument=1, sequence=1, last=True)
    assert set(base) == set(NORMALIZED_MBO_FIELDS_V1)
    for name in NORMALIZED_MBO_FIELDS_V1:
        trimmed = dict(base)
        del trimmed[name]
        with pytest.raises(ActionError, match="exactly"):
            _input(trimmed)
    padded = dict(base)
    padded["book_top"] = 1
    with pytest.raises(ActionError, match="extra"):
        _input(padded)


@pytest.mark.parametrize(
    "name,value",
    [
        ("size", "1"),
        ("size", -1),
        ("sequence", 1.0),
        ("flags", True),
        ("instrument_id", 0),
        ("action", "X"),
        ("side", "b"),
        ("raw_symbol", 7),
        ("source_dbn_sha256", "abc"),
        ("price", "0.0000001"),
    ],
)
def test_r3_scalar_types_and_domains_enforced(name: str, value):
    bad = action(instrument=1, sequence=1, last=True)
    bad[name] = value
    with pytest.raises(ActionError):
        _input(bad)


def test_r3_derived_fields_must_reconcile_with_primitives():
    price = action(instrument=1, sequence=1, last=True)
    price["price"] = 0.0000002
    with pytest.raises(ActionError, match="price"):
        _input(price)

    undefined = action(instrument=1, sequence=1, last=True)
    undefined["price_raw"] = 9_000_000_000_000_000_000
    with pytest.raises(ActionError, match="price"):
        _input(undefined)
    undefined["price"] = None
    assert _input(undefined).action["price"] is None

    snap = action(instrument=1, sequence=1, last=True)
    snap["is_snapshot"] = True
    with pytest.raises(ActionError, match="is_snapshot"):
        _input(snap)
    snap["flags"] = 128 | 32
    assert _input(snap).action["is_snapshot"] is True


def test_r3_unsupported_adapter_revision_is_refused_at_construction():
    other = SourceScope(
        kind=ScopeKind.RESULT_BEARING,
        scope_id=SCOPE_ID,
        members=(member(0, SHA_A, 100),),
        adapter_revision="NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V3_FUTURE",
    )
    assert ADAPTER == SUPPORTED_ADAPTER_REVISION
    with pytest.raises(ScopeError, match="supported"):
        RecordPrefixChain(other)


def test_r3_interleaved_receipts_stay_authorized_per_instrument():
    chain = RecordPrefixChain(scope())
    chain.advance(record(0, instrument=1, last=False))
    b1 = chain.advance(record(1, instrument=2, last=True))
    a1 = chain.advance(record(2, instrument=1, last=True))
    # B closed before A but is still B's latest group: authorized.
    assert chain.validate_result_bearing(b1) is b1
    assert chain.validate_result_bearing(a1) is a1

    b2 = chain.advance(record(3, instrument=2, last=True))
    assert chain.validate_result_bearing(b2) is b2
    with pytest.raises(ReceiptError, match="instrument 2"):
        chain.validate_result_bearing(b1)  # superseded
    assert chain.validate_result_bearing(a1) is a1  # still A's latest

    # A receipt minted by a different chain over different evidence is not
    # authorized here even though it self-verifies.
    other = RecordPrefixChain(scope())
    foreign = other.advance(record(0, instrument=2, last=True))
    foreign.verify()
    with pytest.raises(ReceiptError, match="authoritative"):
        chain.validate_result_bearing(foreign)


def test_r3_rejected_advance_leaves_open_groups_untouched():
    chain = RecordPrefixChain(scope())
    chain.advance(record(0, instrument=1, last=False))
    before = (
        chain.prefix_hash,
        chain.next_cursor,
        chain.open_instruments,
        chain.next_global_group_ordinal,
    )
    with pytest.raises(ContiguityError):
        chain.advance(record(5, instrument=1, last=True))
    with pytest.raises(ScopeError, match="sha256"):
        chain.advance(record(1, instrument=1, last=True, source_sha=SHA_B))
    assert (
        chain.prefix_hash,
        chain.next_cursor,
        chain.open_instruments,
        chain.next_global_group_ordinal,
    ) == before
    closed = chain.advance(record(1, instrument=1, last=True))
    assert closed is not None and closed.record_cursors == (0, 1)


def test_r3_large_group_accumulates_linearly_and_binds_every_cursor():
    n = 3_000
    scoped = scope(members=(member(0, SHA_A, n),))
    chain = RecordPrefixChain(scoped)
    receipt = None
    for cursor in range(n):
        receipt = chain.advance(record(cursor, instrument=1, last=(cursor == n - 1)))
    assert receipt is not None
    assert receipt.record_cursors == tuple(range(n))
    assert receipt.action_count == n
    assert chain.open_instruments == ()
    assert not hasattr(chain, "receipts")


def _drive(chain: RecordPrefixChain, records: list[RecordInput]) -> list[tuple[str, str | None]]:
    trace = []
    for rec in records:
        receipt = chain.advance(rec)
        trace.append((chain.prefix_hash, None if receipt is None else receipt.receipt_hash))
    return trace


def test_r3_export_restore_reproduces_continuous_replay():
    scoped = scope(members=(member(0, SHA_A, 4), member(1, SHA_B, 4)))
    stream = [
        record(0, instrument=1, last=False),
        record(1, instrument=2, last=True),
        record(2, instrument=1, last=True),
        record(3, instrument=3, last=True),
        record(4, instrument=2, last=False, member_index=1, source_sha=SHA_B),
        record(5, instrument=1, last=True, member_index=1, source_sha=SHA_B),
        record(6, instrument=2, last=True, member_index=1, source_sha=SHA_B),
        record(7, instrument=3, last=True, member_index=1, source_sha=SHA_B),
    ]
    continuous = RecordPrefixChain(scoped)
    expected = _drive(continuous, stream)

    # Cut at every all-groups-closed boundary, including the member boundary.
    for cut in (3, 4, 7, 8):
        head = RecordPrefixChain(scoped)
        trace = _drive(head, stream[:cut])
        state = head.export_state()
        tail = RecordPrefixChain.restore(scoped, state)
        assert tail.prefix_hash == head.prefix_hash
        assert tail.last_receipt == head.last_receipt
        trace += _drive(tail, stream[cut:])
        assert trace == expected, f"cut={cut}"
        assert tail.export_state() == continuous.export_state()


def test_r3_export_refused_mid_group_and_restore_fails_closed():
    scoped = scope()
    chain = RecordPrefixChain(scoped)
    chain.advance(record(0, instrument=1, last=False))
    with pytest.raises(RecordStateError, match="open"):
        chain.export_state()
    chain.advance(record(1, instrument=1, last=True))
    state = chain.export_state()
    assert set(state["instruments"][0]) == {
        "instrument_id", "next_ordinal", "last_receipt_hash", "last_global_group_ordinal",
    }

    tampered = dict(state)
    tampered["next_cursor"] = 5
    with pytest.raises(RecordStateError, match="state_hash"):
        RecordPrefixChain.restore(scoped, tampered)

    resigned = dict(tampered)
    resigned["state_hash"] = ""
    from causal_prefix import _domain_hash, PREFIX_SCHEME
    resigned["state_hash"] = _domain_hash(PREFIX_SCHEME + "/RECORD_CHAIN_STATE", resigned)
    with pytest.raises(RecordStateError, match="terminal receipt"):
        RecordPrefixChain.restore(scoped, resigned)

    other_scope = scope(kind=ScopeKind.PROBE_ONLY)
    with pytest.raises(RecordStateError, match="different scope"):
        RecordPrefixChain.restore(other_scope, state)

    with pytest.raises(RecordStateError, match="keys"):
        RecordPrefixChain.restore(scoped, {**state, "extra": 1})


def _resign_state(state):
    from causal_prefix import _domain_hash, PREFIX_SCHEME
    state["state_hash"] = _domain_hash(
        PREFIX_SCHEME + "/RECORD_CHAIN_STATE", {**state, "state_hash": ""}
    )
    return state


def test_normalized_record_cannot_be_mutated_after_validation():
    rec = record(0, instrument=1, last=True)
    with pytest.raises(TypeError):
        rec.action["size"] = "malformed"
    chain = RecordPrefixChain(scope())
    assert chain.advance(rec).action_count == 1


def test_restore_empty_state_cannot_skip_source_records():
    scoped = scope()
    state = RecordPrefixChain(scoped).export_state()
    state["next_cursor"] = 7
    with pytest.raises(RecordStateError):
        RecordPrefixChain.restore(scoped, _resign_state(state))


@pytest.mark.parametrize("field,value", [
    ("scope_id", "d" * 64),
    ("source_member_sha256", "d" * 64),
    ("adapter_revision", "OTHER"),
    ("instrument_group_ordinal", 4),
])
def test_restore_rejects_terminal_receipt_context_mismatch(field, value):
    from dataclasses import replace
    scoped = scope()
    chain = RecordPrefixChain(scoped)
    receipt = chain.advance(record(0, instrument=1, last=True))
    state = chain.export_state()
    forged = replace(receipt, **{field: value, "receipt_hash": ""})
    forged = replace(forged, receipt_hash=forged.governed_hash())
    state["last_receipt"] = forged.public_dict()
    state["instruments"][0]["last_receipt_hash"] = forged.receipt_hash
    with pytest.raises(RecordStateError):
        RecordPrefixChain.restore(scoped, _resign_state(state))


def test_restore_rejects_impossible_per_instrument_group_history():
    scoped = scope()
    chain = RecordPrefixChain(scoped)
    chain.advance(record(0, instrument=1, last=True))
    chain.advance(record(1, instrument=2, last=True))
    state = chain.export_state()
    state["instruments"][0]["last_global_group_ordinal"] = 1
    with pytest.raises(RecordStateError):
        RecordPrefixChain.restore(scoped, _resign_state(state))


@pytest.mark.parametrize("bad_sha", ["-" + "a" * 63, "+" + "a" * 63, " " + "a" * 63])
def test_source_hash_requires_exact_hex_characters(bad_sha):
    with pytest.raises(ScopeError):
        member(0, bad_sha, 10)
    with pytest.raises(ActionError):
        record(0, instrument=1, last=True, source_sha=bad_sha)
