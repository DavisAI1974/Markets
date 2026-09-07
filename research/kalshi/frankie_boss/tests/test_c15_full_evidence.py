"""Preservation proofs: real unchanged adapter, synthetic records only."""
import math
import json
import struct

import pytest

from causal_prefix import ScopeKind
from c15_journal import EvidenceJournal
from test_causal_prefix_records import member, scope, SHA_A, SHA_B


def row(seq, *, action="A", side="A", oid=1, price=101, size=10,
        flags=128, iid=1):
    return dict(instrument_id=iid, publisher_id=1, channel_id=1, order_id=oid,
                action=action, side=side, price=price, size=size, flags=flags,
                sequence=seq, ts_event=seq * 100 + 1, ts_recv=seq * 100 + 2,
                ts_in_delta=1)


def build(tmp_path, count=10000, members=None):
    from c15_builder import C15Builder
    return C15Builder(scope(kind=ScopeKind.PROBE_ONLY,
                            members=members or (member(0, SHA_A, count),)),
                      tmp_path / "evidence.sqlite")


def submit(builder, record, *, member_index=0, session="s"):
    return builder.apply(record, source_member_index=member_index, session_id=session,
                         source_dbn_object="synthetic", raw_symbol="NG")


def test_every_record_and_group_survives_past_old_caps(tmp_path):
    builder = build(tmp_path)
    for i in range(4200):
        result = submit(builder, row(i, action="N", side="N", oid=0))
    rows = list(builder.journal.entries())
    assert sum(e["kind"] == "INPUT" for e in rows) == 4200
    groups = [e["payload"] for e in rows if e["kind"] == "APPLIED"]
    assert len(groups) == 4200
    assert [g["receipt"]["global_group_ordinal"] for g in groups] == list(range(4200))
    assert result.observation["orders"] == []
    assert result.receipt.global_group_ordinal == 4199
    assert rows[0]["payload"]["record"] == row(0, action="N", side="N", oid=0)
    # The downstream evidence surface must deliver every event, not just keep
    # it in storage. Incomplete/neutral evidence is not masked or filtered.
    delivered = list(builder.evidence_stream())
    assert [e["cursor"] for e in delivered] == list(range(4200))
    assert all(e["raw_record"]["action"] == "N" for e in delivered)


def test_full_depth_every_order_and_snapshot_origin_fields_retained(tmp_path):
    builder = build(tmp_path)
    for i in range(20):
        result = submit(builder, row(i, oid=i + 1, price=100 + i, flags=128 | 32))
    assert len(result.observation["orders"]) == 20
    assert len(result.observation["levels"]["A"]) == 20
    assert result.observation["orders"][-1]["order_id"] == 20
    assert "unknown" not in result.observation
    assert len(list(builder.order_history(instrument_id=1, publisher_id=1, order_id=20))) == 1
    record = list(builder.order_history(instrument_id=1, publisher_id=1, order_id=20))[0]
    assert record["normalized"]["is_snapshot"] is True
    assert record["order_after"]["priority_recv_ns"] == row(19)["ts_recv"]


def test_fill_cancel_reset_and_session_history_is_not_cleared(tmp_path):
    builder = build(tmp_path)
    records = [row(0), row(1, action="F", size=3), row(2, action="C", size=3),
               row(3, action="F", size=7), row(4, action="R", side="N", oid=0),
               row(5, oid=1, price=99)]
    for i, record in enumerate(records):
        result = submit(builder, record, session="next" if i >= 4 else "s")
    history = list(builder.order_history(instrument_id=1, publisher_id=1, order_id=1))
    assert [r["normalized"]["action"] for r in history] == ["A", "F", "C", "F", "R", "A"]
    assert history[2]["order_after"]["size"] == 7
    applied = [e["payload"] for e in builder.journal.entries() if e["kind"] == "APPLIED"]
    assert applied[4]["boundary"]["previous_session"] == "s"
    assert applied[4]["observation"]["orders"] == []
    assert applied[3]["effect"]["action"] == "F"
    assert len(result.observation["orders"]) == 1


def test_float_bits_bytes_and_extra_raw_fields_are_preserved(tmp_path):
    journal = EvidenceJournal(tmp_path / "raw.sqlite", create=True)
    value = dict(value=1.1234567890123457, negative_zero=-0.0, huge=10**100,
                 raw=b"\x00\xff", nested={"float": "not a type tag"})
    journal.append("RAW", value)
    recovered = list(journal.entries())[0]["payload"]
    assert recovered == value
    assert recovered["value"].hex() == value["value"].hex()
    assert math.copysign(1, recovered["negative_zero"]) == -1
    builder = build(tmp_path)
    raw = row(0)
    raw["additional_source_field"] = value
    submit(builder, raw)
    assert list(builder.journal.entries())[0]["payload"]["record"] == raw


@pytest.mark.parametrize("bits", ["7ff8000000000001", "7ff8000000000002", "fff8000000000001"])
def test_nan_payload_and_sign_bits_are_preserved(tmp_path, bits):
    journal = EvidenceJournal(tmp_path / "nan.sqlite", create=True)
    value = struct.unpack(">d", bytes.fromhex(bits))[0]
    journal.append("RAW", dict(value=value))
    restored = list(journal.entries())[0]["payload"]["value"]
    assert struct.pack(">d", restored).hex() == bits


def test_altered_journal_bytes_are_rejected_even_if_json_semantics_match(tmp_path):
    journal = EvidenceJournal(tmp_path / "tampered.sqlite", create=True)
    journal.append("RAW", dict(value=1))
    body = journal.connection.execute("SELECT body FROM entries").fetchone()[0]
    # Simulate external file modification, not a supported journal write.
    journal.connection.execute("DROP TRIGGER forbid_update")
    journal.connection.execute("UPDATE entries SET body=?", (json.dumps(json.loads(body), indent=2).encode(),))
    journal.connection.commit()
    with pytest.raises(ValueError, match="hash mismatch"):
        list(journal.entries())


def test_rejected_record_is_retained_and_builder_stops(tmp_path):
    builder = build(tmp_path)
    raw = row(0, action="?")
    with pytest.raises(ValueError):
        submit(builder, raw)
    entries = list(builder.journal.entries())
    assert entries[0]["payload"]["record"] == raw
    assert entries[1]["kind"] == "FAILED"
    with pytest.raises(ValueError):
        submit(builder, row(1))
    with pytest.raises(ValueError, match="unprocessed"):
        list(builder.evidence_stream())
    assert len(list(builder.journal.entries())) == 2


def test_write_failure_stops_before_any_book_or_prefix_update(tmp_path, monkeypatch):
    builder = build(tmp_path)
    def fail(*args, **kwargs):
        raise OSError("synthetic storage failure")
    monkeypatch.setattr(builder.journal, "append", fail)
    with pytest.raises(OSError):
        submit(builder, row(0))
    assert builder.chain.next_cursor == builder.adapter.record_count == 0
    with pytest.raises(ValueError, match="stopped"):
        submit(builder, row(1))


def test_consumer_gets_nonterminal_records_and_incomplete_order_fields(tmp_path):
    builder = build(tmp_path)
    first = submit(builder, row(0, flags=32, size=7))
    assert first.frame is None and first.receipt is None
    assert first.evidence["raw_record"]["flags"] == 32
    assert first.evidence["order_after"]["size"] == 7
    assert list(builder.evidence_stream())[0]["raw_record"]["order_id"] == 1
    last = submit(builder, row(1, action="M", oid=999, size=11))
    assert last.evidence["effect"]["missing_reference"] is True
    assert last.evidence["order_after"]["order_id"] == 999
    assert {o["order_id"] for o in last.observation["orders"]} == {1, 999}
    assert len(list(builder.evidence_stream())) == 2


def test_interleaved_groups_keep_all_cursors_and_reject_midgroup_checkpoint(tmp_path):
    builder = build(tmp_path)
    submit(builder, row(0, flags=0))
    b = submit(builder, row(1, iid=2))
    with pytest.raises(ValueError):
        builder.export_state()
    a = submit(builder, row(2, action="M"))
    assert b.receipt.record_cursors == (1,)
    assert a.receipt.record_cursors == (0, 2)
    assert len(list(builder.journal.entries())) == 6


def test_adapter_output_and_state_are_unchanged(tmp_path):
    from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter
    from mbo_resume_state import export_adapter_state
    builder, baseline = build(tmp_path), V4MboAdapter()
    records = [row(0, side="B", price=99), row(1, oid=2),
               row(2, action="M", oid=2, size=20), row(3, action="C", oid=2, size=3),
               row(4, action="T", side="B", oid=0), row(5, action="R", side="N", oid=0)]
    for record in records:
        result = submit(builder, record)
        expected = baseline.apply(record, raw_symbol="NG", source_dbn_object="synthetic", source_dbn_sha256=SHA_A)
        assert (result.frame, result.legacy_rows) == expected
    assert export_adapter_state(builder.adapter) == export_adapter_state(baseline)


def test_restart_binds_whole_archive_and_never_truncates_tail(tmp_path):
    from c15_builder import C15Builder
    continuous = build(tmp_path / "continuous")
    split = build(tmp_path / "split")
    for i in range(8):
        record = row(i, action="A" if i == 0 else "M", size=i + 10)
        submit(continuous, record)
        submit(split, record)
    state = split.export_state()
    split.journal.close()
    resumed = C15Builder.restore(split.scope, tmp_path / "split/evidence.sqlite", state,
                                 expected_hash=state["state_hash"])
    for i in range(8, 12):
        record = row(i, action="M", size=i + 10)
        a, b = submit(continuous, record), submit(resumed, record)
        assert a == b
    assert continuous.export_state() == resumed.export_state()
    resumed.journal.close()
    with pytest.raises(ValueError, match="retained"):
        C15Builder.restore(split.scope, tmp_path / "split/evidence.sqlite", state,
                           expected_hash=state["state_hash"])
    archive = EvidenceJournal(tmp_path / "split/evidence.sqlite")
    assert len(list(archive.entries())) == 24


def test_member_boundary_keeps_prior_order_evidence(tmp_path):
    builder = build(tmp_path, members=(member(0, SHA_A, 1), member(1, SHA_B, 1)))
    submit(builder, row(0))
    result = submit(builder, row(1, action="C", size=10), member_index=1)
    history = list(builder.order_history(instrument_id=1, publisher_id=1, order_id=1))
    assert len(history) == 2
    assert result.observation["orders"] == []
    assert history[1]["boundary"]["previous_member_index"] == 0
