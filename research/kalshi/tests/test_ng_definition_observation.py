from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import ng_definition_observation as definitions


def _row(
    *,
    raw_symbol: str = "NGJ26",
    instrument_id: int = 1008,
    publisher_id: int = 1,
    event_s: float = 1773500000.0,
    start_s: float = 1773000000.0,
    end_s: float = 1775000000.0,
    dataset: str | None = "GLBX.MDP3",
    definition_date: str | None = None,
) -> dict:
    row = {
        "event_type": "definition",
        "publisher_id": publisher_id,
        "instrument_id": instrument_id,
        "raw_symbol": raw_symbol,
        "ts_event_s": event_s,
        "activation": start_s,
        "expiration": end_s,
    }
    if dataset is not None:
        row["dataset"] = dataset
    if definition_date is not None:
        row["definition_date"] = definition_date
    return row


def _write(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def _catalog(tmp_path: Path, rows: list[dict], **kwargs) -> tuple[dict, Path]:
    path = _write(tmp_path / "opaque.jsonl", rows)
    value = definitions.build_catalog(
        [path],
        observed_at="2026-07-22T00:00:00Z",
        **kwargs,
    )
    return value, path


def _refingerprint(value: dict, field: str) -> None:
    value.pop(field, None)
    value[field] = definitions._fp(value)


def test_builds_exact_g15_g16_definition_catalog(tmp_path):
    value, _ = _catalog(
        tmp_path,
        [_row(), _row(raw_symbol="NGK26", instrument_id=996, event_s=1773500001.0)],
        raw_symbols=["NGJ26", "NGK26"],
    )
    assert value["status"] == "OBSERVED_DEFINITIONS_READY"
    assert [row["raw_symbol"] for row in value["definitions"]] == ["NGJ26", "NGK26"]
    assert value["definition_count"] == 2
    definitions.validate_catalog(value, verify_files=True)


def test_ignores_non_exact_and_continuous_symbols(tmp_path):
    value, _ = _catalog(tmp_path, [_row(raw_symbol="NG.n.0"), _row()])
    assert value["definition_count"] == 1
    assert value["sources"][0]["ignored_non_exact_record_count"] == 1


def test_raw_symbol_filter_is_exact_and_visible(tmp_path):
    value, _ = _catalog(
        tmp_path,
        [_row(), _row(raw_symbol="NGK26", instrument_id=996)],
        raw_symbols=["NGK26"],
    )
    assert value["raw_symbol_filter"] == ["NGK26"]
    assert [row["raw_symbol"] for row in value["definitions"]] == ["NGK26"]
    assert value["sources"][0]["filtered_exact_record_count"] == 1


def test_definition_date_defaults_to_observed_event_utc_date(tmp_path):
    value, _ = _catalog(tmp_path, [_row(event_s=1773500000.0)])
    expected = definitions.dt.datetime.fromtimestamp(1773500000.0, tz=definitions.dt.timezone.utc).strftime("%Y%m%d")
    assert value["definitions"][0]["definition_date"] == expected


def test_explicit_definition_date_is_normalized(tmp_path):
    value, _ = _catalog(tmp_path, [_row(definition_date="2026-03-13")])
    assert value["definitions"][0]["definition_date"] == "20260313"


def test_missing_dataset_is_rejected(tmp_path):
    path = _write(tmp_path / "opaque.jsonl", [_row(dataset=None)])
    with pytest.raises(definitions.DefinitionObservationError, match="dataset is unobserved"):
        definitions.build_catalog([path], observed_at="2026-07-22T00:00:00Z")


def test_wrong_dataset_is_rejected(tmp_path):
    path = _write(tmp_path / "opaque.jsonl", [_row(dataset="XNAS.ITCH")])
    with pytest.raises(definitions.DefinitionObservationError, match="dataset"):
        definitions.build_catalog([path], observed_at="2026-07-22T00:00:00Z")


def test_missing_or_backward_definition_period_is_rejected(tmp_path):
    missing = _row()
    missing.pop("expiration")
    path = _write(tmp_path / "missing.jsonl", [missing])
    with pytest.raises(definitions.DefinitionObservationError, match="missing activation/expiration"):
        definitions.build_catalog([path], observed_at="2026-07-22T00:00:00Z")
    path = _write(tmp_path / "backward.jsonl", [_row(start_s=20.0, end_s=10.0)])
    with pytest.raises(definitions.DefinitionObservationError, match="backwards"):
        definitions.build_catalog([path], observed_at="2026-07-22T00:00:00Z")


def test_repeated_identical_definition_is_deduplicated(tmp_path):
    value, _ = _catalog(tmp_path, [_row(), _row(event_s=1773500001.0)])
    assert value["definition_count"] == 1
    assert value["evidence_groups"][0]["duplicate_observation_count"] == 2


def test_distinct_overlapping_periods_remain_separate(tmp_path):
    value, _ = _catalog(
        tmp_path,
        [_row(start_s=1773000000.0, end_s=1775000000.0), _row(start_s=1773100000.0, end_s=1775100000.0)],
    )
    assert value["definition_count"] == 2
    assert value["overlapping_distinct_periods_preserved"] is True


def test_source_bytes_are_immutable(tmp_path):
    rows = [_row()]
    path = _write(tmp_path / "opaque.jsonl", rows)
    before = path.read_bytes()
    definitions.build_catalog([path], observed_at="2026-07-22T00:00:00Z")
    assert path.read_bytes() == before


def test_duplicate_source_paths_are_rejected(tmp_path):
    path = _write(tmp_path / "opaque.jsonl", [_row()])
    with pytest.raises(definitions.DefinitionObservationError, match="unique"):
        definitions.build_catalog([path, path], observed_at="2026-07-22T00:00:00Z")


def test_catalog_and_nested_source_tampering_are_detected(tmp_path):
    value, _ = _catalog(tmp_path, [_row()])
    changed = copy.deepcopy(value)
    changed["status"] = "BLOCKED"
    with pytest.raises(definitions.DefinitionObservationError, match="catalog_fingerprint"):
        definitions.validate_catalog(changed)
    changed = copy.deepcopy(value)
    changed["sources"][0]["exact_ng_record_count"] = 99
    _refingerprint(changed, "catalog_fingerprint")
    with pytest.raises(definitions.DefinitionObservationError, match="source_fingerprint"):
        definitions.validate_catalog(changed)


def test_tampered_evidence_group_is_detected_even_after_outer_refingerprint(tmp_path):
    value, _ = _catalog(tmp_path, [_row()])
    changed = copy.deepcopy(value)
    changed["evidence_groups"][0]["duplicate_observation_count"] = 99
    _refingerprint(changed, "catalog_fingerprint")
    with pytest.raises(definitions.DefinitionObservationError, match="evidence_group_fingerprint"):
        definitions.validate_catalog(changed)


def test_file_tampering_is_detected_when_requested(tmp_path):
    value, path = _catalog(tmp_path, [_row()])
    path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(definitions.DefinitionObservationError, match="verification failed"):
        definitions.validate_catalog(value, verify_files=True)


def test_authority_remains_shadow_tastytrade_and_options_unstarted(tmp_path):
    value, _ = _catalog(tmp_path, [_row()])
    assert value["actual_outcomes_used"] is False
    assert value["may_change_blind_forecast"] is False
    assert value["may_change_posterior"] is False
    assert value["may_update_ng_brain"] is False
    assert value["execution_authority"] is False
    assert value["cme_event_contracts_mode"] == "SHADOW"
    assert value["brokerage_contract"] == "tastytrade_not_ibkr"
    assert value["options_lane_started"] is False


def test_exact_contract_must_come_from_definition_evidence(tmp_path):
    row = _row()
    row["event_type"] = "trade"
    path = _write(tmp_path / "opaque.jsonl", [row])
    with pytest.raises(definitions.DefinitionObservationError, match="not definition evidence"):
        definitions.build_catalog([path], observed_at="2026-07-22T00:00:00Z")


def test_observed_at_must_be_timezone_aware_iso_timestamp(tmp_path):
    path = _write(tmp_path / "opaque.jsonl", [_row()])
    with pytest.raises(definitions.DefinitionObservationError, match="include a timezone"):
        definitions.build_catalog([path], observed_at="2026-07-22T00:00:00")


def test_refingerprinted_evidence_identity_tampering_is_detected(tmp_path):
    value, _ = _catalog(tmp_path, [_row()])
    changed = copy.deepcopy(value)
    changed["evidence_groups"][0]["identity_period"]["instrument_id"] = 996
    _refingerprint(changed["evidence_groups"][0], "evidence_group_fingerprint")
    _refingerprint(changed, "catalog_fingerprint")
    with pytest.raises(definitions.DefinitionObservationError, match="identity-period mismatch"):
        definitions.validate_catalog(changed)
