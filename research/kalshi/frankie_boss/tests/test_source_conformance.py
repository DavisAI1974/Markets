"""Synthetic explicit-mapping driver proofs; no providers or market data."""
from dataclasses import FrozenInstanceError

import pytest

from test_causal_prefix_records import member, scope, SHA_A, SHA_B
from test_c15_full_evidence import row
from causal_prefix import ScopeKind
from c15_builder import C15Builder
from c15_journal import pack
from source_conformance import SourceConformanceDriver


def create(tmp_path, counts=(3,), name="source.sqlite"):
    declared = scope(kind=ScopeKind.PROBE_ONLY, members=tuple(
        member(i, (SHA_A, SHA_B)[i], count) for i, count in enumerate(counts)))
    return SourceConformanceDriver(declared, tmp_path / name,
                                   expected_scope_hash=declared.genesis_hash())


def append(driver, cursor, raw=None, member_index=0, **changes):
    args = dict(cursor=cursor, source_member_index=member_index,
                source_sha256=(SHA_A, SHA_B)[member_index], session_id="s",
                raw_symbol="NG", source_dbn_object="synthetic")
    args.update(changes)
    return driver.append(raw if raw is not None else row(cursor), **args)


def test_stream_preserves_every_mapping_and_original_control_outputs(tmp_path):
    records = [row(0, flags=0), row(1, iid=2), row(2, action="M", size=9),
               row(3, action="F", size=2), row(4, action="C", size=2),
               row(5, action="C", oid=999), row(6, action="R", side="N", oid=0)]
    records[0]["extra"] = dict(bytes=b"\x00\xff", signed_zero=-0.0, nested=[1, None])
    driver = create(tmp_path, (len(records),))
    control = C15Builder(driver.scope, tmp_path / "control.sqlite")
    try:
        for cursor, raw in enumerate(records):
            output = append(driver, cursor, raw)
            expected = control.apply(raw, source_member_index=0, session_id="s",
                                     raw_symbol="NG", source_dbn_object="synthetic")
            assert pack(output.evidence) == pack(expected.evidence)
        delivered = list(driver.evidence_stream())
        assert [pack(e["raw_record"]) for e in delivered] == [pack(r) for r in records]
        assert delivered[0]["frame"] is None
        assert delivered[5]["integrity"]
        receipt = driver.complete()
        assert receipt.record_count == len(records)
        assert receipt.member_counts == (len(records),)
        assert receipt.scope_kind == "PROBE_ONLY"
        assert receipt.source_prefix_hash == control.chain.prefix_hash
        assert driver.complete() == receipt
        with pytest.raises(FrozenInstanceError):
            receipt.record_count = 1
        with pytest.raises(ValueError, match="completed"):
            append(driver, len(records))
    finally:
        driver.close()
        control.journal.close()


@pytest.mark.parametrize("changes", [dict(cursor=1), dict(cursor=True),
    dict(source_sha256=SHA_B), dict(source_member_index=True),
    dict(source_member_index=1)])
def test_bad_source_coordinates_stop_driver_without_success_receipt(tmp_path, changes):
    driver = create(tmp_path)
    try:
        args = dict(cursor=0, source_member_index=0, source_sha256=SHA_A, session_id="s")
        args.update(changes)
        with pytest.raises(ValueError):
            driver.append(row(0), **args)
        with pytest.raises(ValueError, match="stopped"):
            driver.complete()
        with pytest.raises(ValueError, match="stopped"):
            driver.checkpoint()
    finally:
        driver.close()


def test_missing_records_and_open_group_never_complete(tmp_path):
    driver = create(tmp_path, (2,))
    try:
        append(driver, 0)
        with pytest.raises(ValueError, match="count"):
            driver.complete()
        append(driver, 1, row(1, flags=0))
        with pytest.raises(ValueError):
            driver.complete()
    finally:
        driver.close()


def test_extra_record_stops_driver(tmp_path):
    driver = create(tmp_path, (1,))
    try:
        append(driver, 0)
        with pytest.raises(ValueError):
            append(driver, 1)
        with pytest.raises(ValueError, match="stopped"):
            driver.complete()
    finally:
        driver.close()


def test_builder_failure_preserves_original_rejected_mapping(tmp_path):
    driver = create(tmp_path, (1,))
    raw = row(0, action="?")
    try:
        with pytest.raises(ValueError):
            append(driver, 0, raw)
        entries = list(driver._builder.journal.entries())
        assert entries[0]["payload"]["record"] == raw
        assert entries[1]["kind"] == "FAILED"
        with pytest.raises(ValueError, match="stopped"):
            driver.complete()
    finally:
        driver.close()


def test_scope_hash_checked_before_creating_journal(tmp_path):
    declared = scope()
    path = tmp_path / "should-not-exist.sqlite"
    with pytest.raises(ValueError, match="scope"):
        SourceConformanceDriver(declared, path, expected_scope_hash=SHA_A)
    assert not path.exists()


def test_restart_and_member_transition_match_continuous_ingestion(tmp_path):
    continuous = create(tmp_path, (2, 2), "continuous.sqlite")
    interrupted = create(tmp_path, (2, 2), "interrupted.sqlite")
    try:
        for cursor in range(4):
            append(continuous, cursor, member_index=cursor // 2)
        for cursor in range(2):
            append(interrupted, cursor)
        checkpoint = interrupted.checkpoint()
        interrupted.close()
        interrupted = SourceConformanceDriver.restore(
            continuous.scope, tmp_path / "interrupted.sqlite", checkpoint,
            expected_scope_hash=continuous.scope.genesis_hash(),
            expected_state_hash=checkpoint["state_hash"])
        for cursor in range(2, 4):
            append(interrupted, cursor, member_index=1)
        assert interrupted.complete() == continuous.complete()
    finally:
        continuous.close()
        interrupted.close()


def test_tampered_journal_prevents_receipt_even_after_completion(tmp_path):
    driver = create(tmp_path, (1,))
    try:
        append(driver, 0)
        driver.complete()
        connection = driver._builder.journal.connection
        connection.execute("DROP TRIGGER forbid_update")
        connection.execute("UPDATE entries SET digest=? WHERE ordinal=0", (SHA_B,))
        connection.commit()
        with pytest.raises(ValueError, match="hash"):
            driver.complete()
    finally:
        driver.close()


def test_duplicate_raw_records_are_not_deduplicated(tmp_path):
    driver = create(tmp_path, (2,))
    raw = row(0, action="N", side="N", oid=0)
    try:
        append(driver, 0, raw)
        append(driver, 1, raw)
        assert len(list(driver.evidence_stream())) == 2
        assert driver.complete().record_count == 2
    finally:
        driver.close()


def test_source_boundary_with_open_group_retains_failure(tmp_path):
    driver = create(tmp_path, (1, 1))
    try:
        append(driver, 0, row(0, flags=0))
        with pytest.raises(ValueError, match="open group"):
            append(driver, 1, member_index=1)
        assert list(driver._builder.journal.entries())[-1]["kind"] == "FAILED"
        with pytest.raises(ValueError, match="stopped"):
            driver.complete()
    finally:
        driver.close()


def test_wrong_checkpoint_trust_root_and_later_suffix_rejected(tmp_path):
    driver = create(tmp_path, (2,))
    declared = driver.scope
    try:
        append(driver, 0)
        checkpoint = driver.checkpoint()
        with pytest.raises(ValueError, match="identity"):
            SourceConformanceDriver.restore(declared, tmp_path / "source.sqlite", checkpoint,
                expected_scope_hash=declared.genesis_hash(), expected_state_hash=SHA_B)
        append(driver, 1)
        with pytest.raises(ValueError, match="checkpoint"):
            SourceConformanceDriver.restore(declared, tmp_path / "source.sqlite", checkpoint,
                expected_scope_hash=declared.genesis_hash(),
                expected_state_hash=checkpoint["state_hash"])
        assert driver.complete().record_count == 2
    finally:
        driver.close()


def test_earlier_delivered_prefix_unchanged_by_suffix(tmp_path):
    driver = create(tmp_path, (2,))
    try:
        append(driver, 0)
        earlier = pack(list(driver.evidence_stream(through_cursor=0)))
        append(driver, 1)
        assert pack(list(driver.evidence_stream(through_cursor=0))) == earlier
        driver.complete()
    finally:
        driver.close()
