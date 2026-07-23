from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import ng_corpus_inspection as inspection
import ng_corpus_target_day_slicer as slicer
from ng_corpus_quarantine_storage import _fp, _sha256


def _ts(day: str, hour: int = 12) -> float:
    return datetime(
        int(day[:4]), int(day[4:6]), int(day[6:8]), hour, tzinfo=timezone.utc
    ).timestamp()


def _definition(symbol: str, instrument: int) -> dict:
    return inspection.definition_observation(
        dataset="GLBX.MDP3",
        publisher_id=1,
        instrument_id=instrument,
        raw_symbol=symbol,
        definition_date="2026-03-01",
        definition_start_s=_ts("20260301", 0),
        definition_end_s=_ts("20260701", 0),
        observed_from=f"fixture:{symbol}",
        observed_at="2026-07-23T00:00:00Z",
        source_sha256="a" * 64,
        source_size_bytes=1,
    )


def _trade(day: str, symbol: str, instrument: int, sequence: int, *, hour: int = 12, price: float = 3.0) -> dict:
    return {
        "event_type": "trade",
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": instrument,
        "raw_symbol": symbol,
        "definition_date": "2026-03-01",
        "ts_event_s": _ts(day, hour),
        "source_sequence": sequence,
        "price": price,
        "size": 1,
        "side": "B",
    }


def _mbo(day: str, symbol: str, instrument: int, sequence: int, *, hour: int = 12, price: float = 3.0) -> dict:
    return {
        "event_type": "mbo",
        "source_schema": "MBO",
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": instrument,
        "raw_symbol": symbol,
        "definition_date": "2026-03-01",
        "ts_event_s": _ts(day, hour),
        "source_sequence": sequence,
        "action": "ADD",
        "side": "B",
        "price": price,
        "size": 1,
        "order_id": sequence,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _object(tmp_path: Path, object_id: str, lane: str, definition: dict, rows: list[dict]) -> tuple[dict, dict, dict]:
    path = tmp_path / f"{object_id}.jsonl"
    _write_jsonl(path, rows)
    quarantine = {
        "object_id": object_id,
        "location": f"s3://fixture/{object_id}",
        "quarantine_path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "quarantine_object_fingerprint": f"q-{object_id}",
    }
    evidence = {
        "object_id": object_id,
        "location": quarantine["location"],
        "status": "UNIQUE_DEFINITION_MATCH",
        "proposed_lane": lane,
        "unique_definition": definition,
        "probe_object_fingerprint": f"p-{object_id}",
        "evidence_fingerprint": f"e-{object_id}",
    }
    binding = {
        "object_id": object_id,
        "skip_nonmatching": lane == "l1_trades",
        "binding_fingerprint": f"b-{object_id}",
    }
    return quarantine, evidence, binding


def _all_days_for(symbol: str) -> list[str]:
    return [
        day
        for day in slicer._target_days()
        if slicer._target_identity(day)["raw_symbol"] == symbol
    ]


def _complete_objects(tmp_path: Path, *, mbo_hour: int = 12, conflict: bool = False) -> list[tuple[dict, dict, dict]]:
    ngj = _definition("NGJ26", 1008)
    ngk = _definition("NGK26", 996)
    objects = []
    sequence = 0
    for definition, symbol, instrument in ((ngj, "NGJ26", 1008), (ngk, "NGK26", 996)):
        days = _all_days_for(symbol)
        trade_rows = []
        mbo_rows = []
        for day in days:
            sequence += 1
            trade_rows.append(_trade(day, symbol, instrument, sequence))
            mbo_rows.append(_mbo(day, symbol, instrument, sequence, hour=mbo_hour))
        objects.append(_object(tmp_path, f"{symbol}-l1", "l1_trades", definition, trade_rows))
        objects.append(_object(tmp_path, f"{symbol}-mbo", "mbo", definition, mbo_rows))
    if conflict:
        rows = [
            _trade(day, "NGJ26", 1008, index + 1, price=4.0)
            for index, day in enumerate(_all_days_for("NGJ26"))
        ]
        objects.append(_object(tmp_path, "NGJ26-l1-conflict", "l1_trades", ngj, rows))
    return objects


def _patch_chain(monkeypatch: pytest.MonkeyPatch, objects: list[tuple[dict, dict, dict]]) -> dict:
    gate = {"gate_fingerprint": "gate"}
    snapshot = {"snapshot_fingerprint": "snapshot", "observed_at": "2026-07-23T00:00:00Z"}
    quarantine = {
        "quarantine_fingerprint": "quarantine",
        "objects": [row[0] for row in objects],
    }
    catalog = {"catalog_fingerprint": "catalog"}
    probe = {"probe_fingerprint": "probe", "objects": [row[1] for row in objects]}
    bindings = {
        "binding_manifest_fingerprint": "bindings",
        "bindings": [row[2] for row in objects],
    }

    def fake_validate_chain(**kwargs):
        return gate, snapshot, quarantine, catalog, probe, bindings

    monkeypatch.setattr(slicer, "_validate_chain", fake_validate_chain)
    return {
        "gate": gate,
        "snapshot": snapshot,
        "quarantine": quarantine,
        "definition_catalog": catalog,
        "probe": probe,
        "proposed_bindings": bindings,
    }


def _build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, objects=None, **kwargs):
    objects = _complete_objects(tmp_path, **kwargs) if objects is None else objects
    chain = _patch_chain(monkeypatch, objects)
    bundle, plan = slicer.build_target_day_slices(
        **chain,
        output_root=tmp_path / "slices",
        confirm_slice=True,
        verify_definition_files=False,
    )
    return bundle, plan, chain, objects


def test_complete_cumulative_sources_produce_exact_anchor_g15_g16_plan(tmp_path, monkeypatch):
    bundle, plan, _, _ = _build(tmp_path, monkeypatch)
    assert bundle["status"] == "ANCHOR_G15_G16_TARGET_SLICES_READY"
    assert bundle["candidate_count"] == len(slicer._target_days()) * 2
    assert all(row["status"] == "MATCHED_L1_MBO_READY" for row in bundle["pairs"])
    assert sum(len(corpus["sources"]) for corpus in plan["corpora"]) == 48
    assert plan["target_day_slices_only"] is True
    assert plan["broad_corpus_completeness_asserted"] is False


def test_friday_anchor_is_sliced_separately(tmp_path, monkeypatch):
    bundle, _, _, _ = _build(tmp_path, monkeypatch)
    anchor = [row for row in bundle["pairs"] if row["day"] == slicer.ANCHOR_DAY]
    assert len(anchor) == 1
    assert anchor[0]["target"] == "G15_ANCHOR"
    assert anchor[0]["status"] == "MATCHED_L1_MBO_READY"


def test_identical_duplicate_candidates_use_deterministic_tie_break(tmp_path, monkeypatch):
    objects = _complete_objects(tmp_path)
    ngj = _definition("NGJ26", 1008)
    rows = [
        _trade(day, "NGJ26", 1008, index + 1)
        for index, day in enumerate(_all_days_for("NGJ26"))
    ]
    objects.append(_object(tmp_path, "NGJ26-l1-copy", "l1_trades", ngj, rows))
    bundle, _, _, _ = _build(tmp_path, monkeypatch, objects=objects)
    rows = [
        row
        for row in bundle["selections"]
        if row["lane"] == "l1_trades" and row["day"] in _all_days_for("NGJ26")
    ]
    assert all(row["status"] == "IDENTICAL_DUPLICATE_SLICES_READY" for row in rows)
    assert all(row["automatic_selection_basis"].startswith("BYTE_IDENTICAL") for row in rows)


def test_conflicting_duplicate_candidates_stand_down(tmp_path, monkeypatch):
    bundle, _, _, _ = _build(tmp_path, monkeypatch, conflict=True)
    conflicted = [
        row
        for row in bundle["selections"]
        if row["lane"] == "l1_trades" and row["day"] in _all_days_for("NGJ26")
    ]
    assert all(row["status"] == "CONFLICTING_SLICE_CANDIDATES" for row in conflicted)
    assert bundle["status"] == "BLOCKED"
    assert all(row["selected_candidate_fingerprint"] is None for row in conflicted)


def test_pair_event_time_nonoverlap_is_visible(tmp_path, monkeypatch):
    bundle, _, _, _ = _build(tmp_path, monkeypatch, mbo_hour=13)
    assert bundle["status"] == "BLOCKED"
    assert all("EVENT_TIME_NONOVERLAP" in row["blockers"] for row in bundle["pairs"])


def test_wrong_contract_records_do_not_enter_target_day(tmp_path, monkeypatch):
    ngj = _definition("NGJ26", 1008)
    rows = [_trade("20260320", "NGJ26", 1008, 1)]
    objects = [_object(tmp_path, "wrong-day", "l1_trades", ngj, rows)]
    bundle, _, _, _ = _build(tmp_path, monkeypatch, objects=objects)
    assert bundle["candidate_count"] == 0
    assert bundle["status"] == "BLOCKED"


def test_explicit_confirmation_is_required(tmp_path, monkeypatch):
    objects = _complete_objects(tmp_path)
    chain = _patch_chain(monkeypatch, objects)
    with pytest.raises(slicer.TargetDaySliceError, match="explicit confirmation"):
        slicer.build_target_day_slices(
            **chain,
            output_root=tmp_path / "slices",
            confirm_slice=False,
            verify_definition_files=False,
        )


def test_backward_source_chronology_is_rejected(tmp_path, monkeypatch):
    definition = _definition("NGJ26", 1008)
    rows = [
        _trade("20260315", "NGJ26", 1008, 2, hour=13),
        _trade("20260315", "NGJ26", 1008, 1, hour=12),
    ]
    objects = [_object(tmp_path, "backward", "l1_trades", definition, rows)]
    chain = _patch_chain(monkeypatch, objects)
    with pytest.raises(slicer.TargetDaySliceError, match="moved backwards"):
        slicer.build_target_day_slices(
            **chain,
            output_root=tmp_path / "slices",
            confirm_slice=True,
            verify_definition_files=False,
        )


def test_definition_period_is_enforced(tmp_path, monkeypatch):
    definition = _definition("NGJ26", 1008)
    definition["definition_end_s"] = _ts("20260314", 0)
    definition.pop("definition_fingerprint")
    definition["definition_fingerprint"] = inspection._fp(definition)
    rows = [_trade("20260315", "NGJ26", 1008, 1)]
    objects = [_object(tmp_path, "outside", "l1_trades", definition, rows)]
    chain = _patch_chain(monkeypatch, objects)
    with pytest.raises(slicer.TargetDaySliceError, match="outside observed definition"):
        slicer.build_target_day_slices(
            **chain,
            output_root=tmp_path / "slices",
            confirm_slice=True,
            verify_definition_files=False,
        )


def test_raw_sources_remain_immutable(tmp_path, monkeypatch):
    objects = _complete_objects(tmp_path)
    before = {
        row[0]["object_id"]: (
            Path(row[0]["quarantine_path"]).read_bytes(),
            _sha256(Path(row[0]["quarantine_path"])),
        )
        for row in objects
    }
    _build(tmp_path, monkeypatch, objects=objects)
    for row in objects:
        path = Path(row[0]["quarantine_path"])
        assert path.read_bytes() == before[row[0]["object_id"]][0]
        assert _sha256(path) == before[row[0]["object_id"]][1]


def test_input_artifacts_are_not_mutated(tmp_path, monkeypatch):
    objects = _complete_objects(tmp_path)
    chain = _patch_chain(monkeypatch, objects)
    before = copy.deepcopy(chain)
    slicer.build_target_day_slices(
        **chain,
        output_root=tmp_path / "slices",
        confirm_slice=True,
        verify_definition_files=False,
    )
    assert chain == before


def test_candidate_file_tampering_is_rejected(tmp_path, monkeypatch):
    bundle, _, chain, _ = _build(tmp_path, monkeypatch)
    path = Path(bundle["candidates"][0]["materialized_path"])
    path.write_text(path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    with pytest.raises(slicer.TargetDaySliceError, match="file verification failed"):
        slicer.validate_slice_bundle(
            bundle,
            **chain,
            verify_files=True,
            verify_definition_files=False,
        )


def test_bundle_tampering_is_rejected(tmp_path, monkeypatch):
    bundle, _, chain, _ = _build(tmp_path, monkeypatch)
    altered = copy.deepcopy(bundle)
    altered["status"] = "BLOCKED"
    with pytest.raises(slicer.TargetDaySliceError, match="fingerprint mismatch"):
        slicer.validate_slice_bundle(
            altered,
            **chain,
            verify_files=False,
            verify_definition_files=False,
        )


def test_refingerprinted_selection_tampering_is_recomputed(tmp_path, monkeypatch):
    bundle, _, chain, _ = _build(tmp_path, monkeypatch)
    altered = copy.deepcopy(bundle)
    altered["selections"][0]["status"] = "MISSING"
    altered["selections"][0].pop("selection_fingerprint")
    altered["selections"][0]["selection_fingerprint"] = _fp(altered["selections"][0])
    altered.pop("slice_bundle_fingerprint")
    altered["slice_bundle_fingerprint"] = _fp(altered)
    with pytest.raises(slicer.TargetDaySliceError, match="selections were not reproduced"):
        slicer.validate_slice_bundle(
            altered,
            **chain,
            verify_files=False,
            verify_definition_files=False,
        )


def test_authority_is_permanently_disabled(tmp_path, monkeypatch):
    bundle, plan, _, _ = _build(tmp_path, monkeypatch)
    for artifact in (bundle, plan):
        assert artifact["actual_outcomes_used"] is False
        assert artifact["paid_live_data_assumed"] is False
        assert artifact["may_update_ng_brain"] is False
        assert artifact["may_change_blind_forecast"] is False
        assert artifact["may_change_posterior"] is False
        assert artifact["execution_authority"] is False
        assert artifact["cme_event_contracts_mode"] == "SHADOW"
        assert artifact["brokerage_contract"] == "tastytrade_not_ibkr"
        assert artifact["options_lane_started"] is False
    assert bundle["random_shuffle_used"] is False
