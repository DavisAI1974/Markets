"""Tests for research/kalshi/frankie_boss/causal_prefix.py (C15 Round 2).

Synthetic fixtures only. No DBN, no real MBO frames, no environment,
no network. Numbered to match Codex Round 2 section 7.2.
"""
from __future__ import annotations

import dataclasses
import inspect
import sys
from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).resolve().parents[1]
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import causal_prefix as cp
from causal_prefix import (
    ActionError,
    CompletedGroup,
    ContiguityError,
    OrdinalError,
    ProbeGroupPrefixChain,
    PrefixReceipt,
    ReceiptError,
    ResultBearingError,
    ScopeError,
    ScopeKind,
    SourceMember,
    SourceScope,
)

# ---------------------------------------------------------------------------
# Synthetic fixtures (hand-verified, no market data)
# ---------------------------------------------------------------------------

ADAPTER = "NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823"
SHA_A = "a" * 64
SHA_B = "b" * 64
SCOPE_ID = "5" * 64

# Known-answer hashes, pinned against the repository canonical_bytes
# authority at base commit beb548b8. Re-pinned in patch 0005 because the
# fixture scope is now PROBE_ONLY (scope kind is bound into the genesis and
# every prefix). The Round-2 RESULT_BEARING pins were
# f3799ed6.../46d148b8.../2447ffec... . On mismatch the failure prints the
# computed triple so it can be re-pinned in the same reviewed patch.
KNOWN_GENESIS = "cd2dc91652d8e1f5e5f8e2823ba8095cb0175a59e8000964f5d3c2578319f8e2"
KNOWN_PREFIX_0 = "cff6ee437a8d37772ad5bcccdd196e27989059e099590e5ce9bdc42a5d8c6874"
KNOWN_RECEIPT_0 = "ea55ebf1e09285dd8c8117a154db38bfa84b69085fb1cd2e38473d65a6785673"


def member(
    idx: int = 0,
    sha: str = SHA_A,
    key: str = "oct1.mbo.dbn.zst",
    records: int = 10_000,
) -> SourceMember:
    return SourceMember(
        member_index=idx,
        member_key=key,
        sha256=sha,
        size_bytes=100 + idx,
        mbo_records=records,
    )


def scope(kind: ScopeKind = ScopeKind.PROBE_ONLY, members=None) -> SourceScope:
    return SourceScope(
        kind=kind,
        scope_id=SCOPE_ID,
        members=tuple(members) if members is not None else (member(),),
        adapter_revision=ADAPTER,
    )


def act(action: str, side: str, price_raw: int, size: int, order_id: int, ts: int, seq: int) -> dict:
    # NormalizedMbo.public_dict()-shaped, normalized logical evidence.
    return {
        "action": action,
        "side": side,
        "price_raw": price_raw,
        "size": size,
        "order_id": order_id,
        "ts_recv_ns": ts,
        "sequence": seq,
        "flags": 128 if action != "A" else 0,
    }


def group(
    *,
    inst: int = 1,
    inst_ord: int = 0,
    glob_ord: int = 0,
    member_idx: int = 0,
    start: int = 0,
    actions: list[dict],
    ts: int | None = None,
    seq: int | None = None,
    declared: int | None = None,
    adapter: str = ADAPTER,
    end: int | None = None,
    force_terminal: bool = True,
) -> CompletedGroup:
    prepared = [dict(action) for action in actions]
    if force_terminal and prepared:
        for action in prepared[:-1]:
            action["flags"] = int(action.get("flags", 0)) & ~128
            if "is_last" in action:
                action["is_last"] = False
        prepared[-1]["flags"] = int(prepared[-1].get("flags", 0)) | 128
        if "is_last" in prepared[-1]:
            prepared[-1]["is_last"] = True
    terminal_ts = (
        int(prepared[-1].get("ts_recv_ns", 1_000))
        if ts is None and prepared
        else (1_000 if ts is None else ts)
    )
    terminal_sequence = (
        int(prepared[-1].get("sequence", 10))
        if seq is None and prepared
        else (10 if seq is None else seq)
    )
    if prepared:
        if "ts_recv_ns" in prepared[-1]:
            prepared[-1]["ts_recv_ns"] = terminal_ts
        if "sequence" in prepared[-1]:
            prepared[-1]["sequence"] = terminal_sequence
    n = len(prepared)
    return CompletedGroup(
        instrument_id=inst,
        publisher_id=1,
        instrument_group_ordinal=inst_ord,
        global_group_ordinal=glob_ord,
        source_member_index=member_idx,
        cursor_start=start,
        cursor_end=end if end is not None else start + n,
        terminal_sequence=terminal_sequence,
        terminal_ts_recv_ns=terminal_ts,
        declared_action_count=declared if declared is not None else n,
        actions=tuple(prepared),
        adapter_revision=adapter,
    )


ACTIONS_0 = [
    act("A", "B", 100, 10, 1, 1_000, 8),
    act("A", "A", 101, 5, 2, 1_000, 9),
    act("T", "A", 101, 2, 0, 1_000, 10),
]


# ---------------------------------------------------------------------------
# 1. deterministic known-answer prefix and receipt hash
# ---------------------------------------------------------------------------


def test_01_known_answer_prefix_and_receipt_hash():
    chain = ProbeGroupPrefixChain(scope())
    genesis = chain.prefix_hash
    r = chain.advance(group(actions=ACTIONS_0))
    # Deterministic across two independent chains.
    chain2 = ProbeGroupPrefixChain(scope())
    r2 = chain2.advance(group(actions=ACTIONS_0))
    assert r == r2 and r.prefix_hash == r2.prefix_hash and r.receipt_hash == r2.receipt_hash
    assert r.previous_prefix_hash == genesis
    got = (genesis, r.prefix_hash, r.receipt_hash)
    want = (KNOWN_GENESIS, KNOWN_PREFIX_0, KNOWN_RECEIPT_0)
    assert got == want, f"known-answer mismatch; computed (genesis, prefix, receipt) = {got}"


# ---------------------------------------------------------------------------
# 2. mapping key-order invariance under canonical serialization
# ---------------------------------------------------------------------------


def test_02_key_order_invariance():
    a = ACTIONS_0[0]
    reordered = {k: a[k] for k in reversed(list(a.keys()))}
    assert list(reordered.keys()) != list(a.keys())
    r1 = ProbeGroupPrefixChain(scope()).advance(group(actions=[a]))
    r2 = ProbeGroupPrefixChain(scope()).advance(group(actions=[reordered]))
    assert r1.prefix_hash == r2.prefix_hash and r1 == r2


# ---------------------------------------------------------------------------
# 3. action-order sensitivity
# ---------------------------------------------------------------------------


def test_03_action_order_sensitivity():
    swapped = [ACTIONS_0[1], ACTIONS_0[0], ACTIONS_0[2]]
    r1 = ProbeGroupPrefixChain(scope()).advance(group(actions=ACTIONS_0))
    r2 = ProbeGroupPrefixChain(scope()).advance(group(actions=swapped))
    assert r1.actions_hash != r2.actions_hash
    assert r1.prefix_hash != r2.prefix_hash


# ---------------------------------------------------------------------------
# 4. single-action mutation sensitivity
# ---------------------------------------------------------------------------


def test_04_single_action_mutation_sensitivity():
    mutated = [dict(a) for a in ACTIONS_0]
    mutated[2]["size"] = 3  # 2 -> 3
    r1 = ProbeGroupPrefixChain(scope()).advance(group(actions=ACTIONS_0))
    r2 = ProbeGroupPrefixChain(scope()).advance(group(actions=mutated))
    assert r1.prefix_hash != r2.prefix_hash and r1.receipt_hash != r2.receipt_hash


# ---------------------------------------------------------------------------
# 5. two raw prefixes leading to the same book summary yield different hashes
# ---------------------------------------------------------------------------


def test_05_same_book_summary_different_prefix():
    # Both prefixes end with 15 resting at bid 100: one order of 15 vs two of 10+5.
    one_order = [act("A", "B", 100, 15, 1, 1_000, 1), act("T", "A", 101, 1, 0, 1_000, 2)]
    two_orders = [act("A", "B", 100, 10, 1, 1_000, 1), act("A", "B", 100, 5, 2, 1_000, 2)]
    r1 = ProbeGroupPrefixChain(scope()).advance(group(actions=one_order))
    r2 = ProbeGroupPrefixChain(scope()).advance(group(actions=two_orders))
    assert r1.prefix_hash != r2.prefix_hash


# ---------------------------------------------------------------------------
# 6. cursor gap / overlap / reversal rejected
# ---------------------------------------------------------------------------


def _chain_after_first() -> ProbeGroupPrefixChain:
    c = ProbeGroupPrefixChain(scope())
    c.advance(group(actions=ACTIONS_0))  # cursors [0, 3)
    return c


@pytest.mark.parametrize(
    "start, n_actions, label",
    [(4, 1, "gap"), (2, 2, "overlap"), (0, 1, "reversal")],
)
def test_06_cursor_gap_overlap_reversal_rejected(start, n_actions, label):
    c = _chain_after_first()
    before = (c.prefix_hash, c.next_cursor, c.next_global_ordinal)
    with pytest.raises(ContiguityError) as ei:
        c.advance(group(inst_ord=1, glob_ord=1, start=start, actions=ACTIONS_0[:n_actions]))
    assert label in str(ei.value)
    assert (c.prefix_hash, c.next_cursor, c.next_global_ordinal) == before  # transactional


def test_06b_group_not_contiguous_in_source_span_rejected():
    # Span of 4 records but only 3 actions: some record in the span is not
    # part of this group -> the group is not contiguous in global order.
    with pytest.raises(ContiguityError):
        group(actions=ACTIONS_0, end=4)


# ---------------------------------------------------------------------------
# 7. global group gap / reversal rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("glob_ord", [2, 0])
def test_07_global_ordinal_gap_reversal_rejected(glob_ord):
    c = _chain_after_first()
    with pytest.raises(OrdinalError):
        c.advance(group(inst_ord=1, glob_ord=glob_ord, start=3, actions=[ACTIONS_0[0]]))


# ---------------------------------------------------------------------------
# 8. cross-instrument interleaving preserves one global order
# ---------------------------------------------------------------------------


def test_08_cross_instrument_interleaving_one_global_order():
    c = ProbeGroupPrefixChain(scope())
    r0 = c.advance(group(inst=1, inst_ord=0, glob_ord=0, start=0, actions=ACTIONS_0))
    r1 = c.advance(group(inst=2, inst_ord=0, glob_ord=1, start=3, actions=[ACTIONS_0[0]]))
    r2 = c.advance(group(inst=1, inst_ord=1, glob_ord=2, start=4, actions=[ACTIONS_0[1]]))
    r3 = c.advance(group(inst=2, inst_ord=1, glob_ord=3, start=5, actions=[ACTIONS_0[2]]))
    # One chain: each receipt links to the previous regardless of instrument.
    assert r1.previous_prefix_hash == r0.prefix_hash
    assert r2.previous_prefix_hash == r1.prefix_hash
    assert r3.previous_prefix_hash == r2.prefix_hash
    receipts = (r0, r1, r2, r3)
    assert [r.global_group_ordinal for r in receipts] == [0, 1, 2, 3]
    assert [r.instrument_group_ordinal for r in receipts] == [0, 0, 1, 1]
    # Reordering the interleaving changes the prefix: per-instrument ordinals
    # are metadata, not ordering authority.
    d = ProbeGroupPrefixChain(scope())
    d.advance(group(inst=2, inst_ord=0, glob_ord=0, start=0, actions=[ACTIONS_0[0]]))
    d.advance(group(inst=1, inst_ord=0, glob_ord=1, start=1, actions=ACTIONS_0))
    assert d.prefix_hash != r1.prefix_hash


# ---------------------------------------------------------------------------
# 9. equal timestamps are ordered by cursor and do not collide
# ---------------------------------------------------------------------------


def test_09_equal_timestamps_ordered_by_cursor_no_collision():
    c = ProbeGroupPrefixChain(scope())
    same_ts = 7_777
    r0 = c.advance(group(inst=1, inst_ord=0, glob_ord=0, start=0, actions=[ACTIONS_0[0]], ts=same_ts, seq=1))
    r1 = c.advance(group(inst=1, inst_ord=1, glob_ord=1, start=1, actions=[ACTIONS_0[0]], ts=same_ts, seq=1))
    # Identical actions, identical terminal ts and sequence: only the cursor
    # and ordinals differ, and that is sufficient to separate them.
    assert r0.terminal_ts_recv_ns == r1.terminal_ts_recv_ns
    assert r0.actions_hash == r1.actions_hash
    assert r0.prefix_hash != r1.prefix_hash and r0.receipt_hash != r1.receipt_hash
    assert (r0.cursor_start, r1.cursor_start) == (0, 1)


# ---------------------------------------------------------------------------
# 10. source-member transition is bound
# ---------------------------------------------------------------------------


def test_10_source_member_transition_bound():
    two = scope(
        members=(
            member(0, SHA_A, "oct1", records=1),
            member(1, SHA_B, "oct3"),
        )
    )
    c = ProbeGroupPrefixChain(two)
    r0 = c.advance(group(member_idx=0, glob_ord=0, inst_ord=0, start=0, actions=[ACTIONS_0[0]]))
    r1 = c.advance(group(member_idx=1, glob_ord=1, inst_ord=1, start=1, actions=[ACTIONS_0[0]]))
    assert r0.previous_member_index is None and r0.source_member_sha256 == SHA_A
    assert r1.previous_member_index == 0 and r1.source_member_sha256 == SHA_B
    # Regression to an earlier member and an undeclared member are rejected.
    with pytest.raises(ScopeError):
        c.advance(group(member_idx=0, glob_ord=2, inst_ord=2, start=2, actions=[ACTIONS_0[0]]))
    with pytest.raises(ScopeError):
        c.advance(group(member_idx=5, glob_ord=2, inst_ord=2, start=2, actions=[ACTIONS_0[0]]))


# ---------------------------------------------------------------------------
# 11. declared action count mismatch rejected
# ---------------------------------------------------------------------------


def test_11_declared_action_count_mismatch_rejected():
    with pytest.raises(ActionError):
        group(actions=ACTIONS_0, declared=2)
    with pytest.raises(ActionError):
        group(actions=[], declared=0, end=1)


# ---------------------------------------------------------------------------
# 12. per-instrument ordinal regression rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("inst_ord", [0, 2])
def test_12_per_instrument_ordinal_regression_or_gap_rejected(inst_ord):
    c = _chain_after_first()  # instrument 1 at ordinal 0
    with pytest.raises(OrdinalError):
        c.advance(group(inst=1, inst_ord=inst_ord, glob_ord=1, start=3, actions=[ACTIONS_0[0]]))
    assert c.instrument_next_ordinal(1) == 1


# ---------------------------------------------------------------------------
# 13. PROBE_ONLY receipt rejected for result-bearing use
# ---------------------------------------------------------------------------


def test_13_result_bearing_scope_is_refused_mechanically():
    """Round 3: the per-group seam is PROBE_ONLY by construction.

    Real GLBX groups interleave, so a per-group chain can never be the
    production provenance chain. It must not be able to mint a
    RESULT_BEARING receipt, and the module must expose no result-bearing
    validation path at all.
    """
    completed = group(actions=ACTIONS_0)
    probe = ProbeGroupPrefixChain(scope(kind=ScopeKind.PROBE_ONLY)).advance(completed)
    assert probe.scope_kind is ScopeKind.PROBE_ONLY
    with pytest.raises(ResultBearingError, match="RecordPrefixChain"):
        ProbeGroupPrefixChain(scope(kind=ScopeKind.RESULT_BEARING))
    assert not hasattr(cp, "validate_result_bearing_receipt")
    assert not hasattr(cp, "PrefixChain")
    # A receipt can still not be relabelled into authority: the relabelled
    # copy has a different governed hash and fails verify().
    relabelled = dataclasses.replace(probe, scope_kind=ScopeKind.RESULT_BEARING)
    with pytest.raises(ReceiptError):
        relabelled.verify()


# ---------------------------------------------------------------------------
# 14. receipt mutation changes its governed hash or fails validation
# ---------------------------------------------------------------------------


def test_14_receipt_mutation_detected():
    completed = group(actions=ACTIONS_0)
    r = ProbeGroupPrefixChain(scope()).advance(completed)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.cursor_end = 99  # type: ignore[misc]
    with pytest.raises(ReceiptError):
        dataclasses.replace(r, cursor_end=99)
    # Re-signing a mutated copy yields a self-consistent receipt that is not
    # the one the chain minted; the chain's last_receipt is the authority.
    resigned = dataclasses.replace(
        dataclasses.replace(r, receipt_hash=""), receipt_hash=""
    )
    resigned = dataclasses.replace(resigned, receipt_hash=resigned.governed_hash())
    resigned.verify()
    assert resigned == r  # honest copy
    forged_unsigned = dataclasses.replace(r, terminal_sequence=r.terminal_sequence + 1, receipt_hash="")
    forged = dataclasses.replace(forged_unsigned, receipt_hash=forged_unsigned.governed_hash())
    forged.verify()
    assert forged != r
    # Value equality holds for an honest copy.
    assert dataclasses.replace(r) == r


# ---------------------------------------------------------------------------
# 15. no timestamp-only cutoff API exists
# ---------------------------------------------------------------------------

_CURSOR_PARAM_MARKERS = ("cursor", "group", "ordinal")


def _is_ts_like(param: str) -> bool:
    p = param.lower()
    return (
        p == "ts"
        or p.startswith("ts_")
        or p.endswith("_ts")
        or "_ts_" in p
        or "timestamp" in p
        or "cutoff" in p
        or "as_of" in p
    )


def _public_callables():
    # Only objects defined by the module itself (not re-exported stdlib).
    for name in dir(cp):
        if name.startswith("_"):
            continue
        obj = getattr(cp, name)
        if getattr(obj, "__module__", None) != cp.__name__:
            continue
        if inspect.isfunction(obj):
            yield name, obj
        elif inspect.isclass(obj):
            for mname, m in inspect.getmembers(obj):
                if mname.startswith("_") or not callable(m):
                    continue
                if getattr(m, "__module__", cp.__name__) != cp.__name__:
                    continue
                yield f"{name}.{mname}", m


def test_15_no_timestamp_only_cutoff_api():
    names = [n for n, _ in _public_callables()]
    for n in names:
        low = n.lower()
        assert "cutoff" not in low and "timestamp" not in low and "at_ts" not in low, n
    for n, fn in _public_callables():
        try:
            params = list(inspect.signature(fn).parameters)
        except (TypeError, ValueError):
            continue
        ts_like = [p for p in params if _is_ts_like(p)]
        if ts_like:
            has_cursor = any(any(m in p.lower() for m in _CURSOR_PARAM_MARKERS) for p in params)
            assert has_cursor, f"{n} accepts a timestamp-like argument without a cursor: {params}"
    # The only transition takes a CompletedGroup, whose span is cursor-bound.
    assert list(inspect.signature(ProbeGroupPrefixChain.advance).parameters) == ["self", "group"]
    ann = inspect.signature(ProbeGroupPrefixChain.advance).parameters["group"].annotation
    assert ann in (CompletedGroup, "CompletedGroup")


# ---------------------------------------------------------------------------
# Supporting invariants (not numbered in 7.2, kept small)
# ---------------------------------------------------------------------------


def test_adapter_revision_mismatch_rejected():
    with pytest.raises(ScopeError):
        ProbeGroupPrefixChain(scope()).advance(group(actions=ACTIONS_0, adapter="OTHER_REVISION"))


def test_scope_kind_and_scheme_in_receipt_public_dict():
    r = ProbeGroupPrefixChain(scope()).advance(group(actions=ACTIONS_0))
    d = r.public_dict()
    assert d["scheme"] == cp.PREFIX_SCHEME == "BOSS_CAUSAL_PREFIX_V1"
    assert d["scope_kind"] == "PROBE_ONLY"
    assert d["receipt_hash"] == r.receipt_hash
    assert isinstance(r, PrefixReceipt)


def test_module_has_no_io_surface():
    src = inspect.getsource(cp)
    for forbidden in ("os.environ", "boto3", "open(", "import os", "import time", "datetime", "AWS_"):
        assert forbidden not in src, forbidden


# ---------------------------------------------------------------------------
# Codex integration regressions discovered against the brownfield adapter
# ---------------------------------------------------------------------------


def test_local_materialization_path_does_not_change_evidence_identity():
    """NormalizedMbo.public_dict() carries a local source path.

    The physical member is already governed by its stable manifest identity
    and SHA-256, so two runners materializing that same member at different
    local paths must produce the same prefix.
    """
    left = [dict(ACTIONS_0[0], source_dbn_object="/runner-a/oct1.dbn")]
    right = [dict(ACTIONS_0[0], source_dbn_object="/runner-b/oct1.dbn")]
    r1 = ProbeGroupPrefixChain(scope()).advance(group(actions=left))
    r2 = ProbeGroupPrefixChain(scope()).advance(group(actions=right))
    assert r1.prefix_hash == r2.prefix_hash


def test_incomplete_non_f_last_group_is_rejected():
    incomplete = [dict(ACTIONS_0[0], is_last=False, flags=0)]
    with pytest.raises(ActionError, match="F_LAST"):
        ProbeGroupPrefixChain(scope()).advance(group(actions=incomplete, force_terminal=False))


def test_group_metadata_must_match_terminal_normalized_action():
    contradictory = [
        dict(
            ACTIONS_0[0],
            instrument_id=999,
            publisher_id=888,
            sequence=777,
            ts_recv_ns=2_222,
            is_last=True,
            flags=128,
        )
    ]
    with pytest.raises(ActionError, match="instrument_id"):
        ProbeGroupPrefixChain(scope()).advance(group(actions=contradictory))


def test_action_source_hash_must_match_active_member():
    contradictory = [dict(ACTIONS_0[0], source_dbn_sha256=SHA_B)]
    with pytest.raises(ScopeError, match="source_dbn_sha256"):
        ProbeGroupPrefixChain(scope()).advance(group(actions=contradictory))


def test_source_member_key_must_not_be_a_local_path_or_uri():
    with pytest.raises(ScopeError, match="manifest key"):
        member(key="/tmp/oct1.mbo.dbn.zst")
    with pytest.raises(ScopeError, match="manifest key"):
        member(key="s3://bucket/oct1.mbo.dbn.zst")


def test_resigned_structurally_invalid_receipt_is_rejected():
    receipt = ProbeGroupPrefixChain(scope()).advance(group(actions=ACTIONS_0))
    with pytest.raises(ReceiptError):
        malformed = dataclasses.replace(receipt, cursor_end=True, receipt_hash="")
        malformed = dataclasses.replace(malformed, receipt_hash=malformed.governed_hash())
        malformed.verify()


def test_source_member_transition_cannot_skip_declared_member():
    three = scope(
        members=(
            member(0, SHA_A, "oct1", records=3),
            member(1, SHA_B, "oct3"),
            member(2, "c" * 64, "oct4"),
        )
    )
    chain = ProbeGroupPrefixChain(three)
    chain.advance(group(member_idx=0, actions=ACTIONS_0))
    with pytest.raises(ScopeError, match="skip"):
        chain.advance(
            group(
                member_idx=2,
                glob_ord=1,
                inst_ord=1,
                start=3,
                actions=[ACTIONS_0[0]],
            )
        )


def test_source_member_transition_requires_prior_member_exhaustion():
    two = scope(
        members=(
            member(0, SHA_A, "oct1", records=4),
            member(1, SHA_B, "oct3"),
        )
    )
    chain = ProbeGroupPrefixChain(two)
    chain.advance(group(member_idx=0, actions=ACTIONS_0))
    with pytest.raises(ScopeError, match="outside|begin"):
        chain.advance(
            group(
                member_idx=1,
                glob_ord=1,
                inst_ord=1,
                start=3,
                actions=[ACTIONS_0[0]],
            )
        )


def test_chain_does_not_retain_unbounded_receipt_history():
    chain = ProbeGroupPrefixChain(scope())
    latest = None
    for i in range(100):
        latest = chain.advance(
            group(
                inst_ord=i,
                glob_ord=i,
                start=i,
                actions=[ACTIONS_0[0]],
                ts=1_000 + i,
                seq=10 + i,
            )
        )
    assert chain.last_receipt == latest
    assert not hasattr(chain, "receipts")
