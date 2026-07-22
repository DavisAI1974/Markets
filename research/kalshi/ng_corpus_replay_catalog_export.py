#!/usr/bin/env python3
"""Export exact audited G15/G16 pairs into deterministic replay catalogs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_coverage_audit as coverage
import ng_g15_replay_manifest_bridge as g15
import ng_g16_historical_replay as g16

SCHEMA = "ng_corpus_replay_catalog_export.v1"
DATASET = coverage.DATASET
LANES = ("l1_trades", "mbo")
GROUPS = {
    15: (coverage.G15_DATES, coverage.G15_CONTRACT_MAP),
    16: (coverage.G16_DATES, coverage.G16_CONTRACT_MAP),
}


class ReplayCatalogExportError(ValueError):
    pass


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode()).hexdigest()


def _entries(catalog: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for corpus in catalog.get("corpora") or []:
        for raw in corpus.get("entries") or []:
            row = copy.deepcopy(dict(raw))
            source_id = str(row.get("source_id") or "")
            if not source_id or source_id in out:
                raise ReplayCatalogExportError(f"invalid or duplicate source_id {source_id!r}")
            out[source_id] = row
    return out


def _pairs(audit: Mapping[str, Any], group: int) -> dict[str, dict[str, Any]]:
    dates, _ = GROUPS[group]
    report = (audit.get("exact_intersections") or {}).get(f"g{group}")
    if not isinstance(report, Mapping):
        raise ReplayCatalogExportError(f"audit lacks G{group}")
    if report.get("status") != "MATCHED_L1_MBO_READY" or report.get("can_run_exact_replay") is not True:
        raise ReplayCatalogExportError(f"G{group} exact intersection is not replay-ready")
    rows = report.get("day_reports")
    if not isinstance(rows, list) or [row.get("day") for row in rows] != list(dates):
        raise ReplayCatalogExportError(f"G{group} canonical day order mismatch")
    out = {}
    for row in rows:
        if row.get("status") != "READY" or not isinstance(row.get("selected_pair"), Mapping):
            raise ReplayCatalogExportError(f"G{group} {row.get('day')} pair is not READY")
        out[str(row["day"])] = copy.deepcopy(dict(row["selected_pair"]))
    return out


def _identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(row.get(name) for name in (
        "dataset", "publisher_id", "instrument_id", "raw_symbol",
        "definition_date", "definition_start_s", "definition_end_s",
    ))


def _definition(group: int, symbol: str, pairs, entries) -> dict[str, Any]:
    dates, contract_map = GROUPS[group]
    rows = []
    for day in dates:
        if contract_map[day]["raw_symbol"] == symbol:
            pair = pairs[day]
            rows += [entries[pair["l1_source_id"]], entries[pair["mbo_source_id"]]]
    identities = {_identity(row) for row in rows}
    if len(identities) != 1:
        raise ReplayCatalogExportError(f"G{group} {symbol} definition identity disagrees across days")
    dataset, publisher, instrument, raw_symbol, definition_date, start, end = next(iter(identities))
    observed = sorted({str(row.get("inventory_observed_at") or "") for row in rows})
    if not observed or not observed[0]:
        raise ReplayCatalogExportError(f"G{group} {symbol} lacks observation time")
    return {
        "dataset": dataset, "publisher_id": publisher, "instrument_id": instrument,
        "raw_symbol": raw_symbol, "definition_date": definition_date,
        "definition_start_s": start, "definition_end_s": end,
        "observed_at": observed[-1],
        "source": "ng_corpus_catalog.v1 selected exact-pair metadata",
        "source_ids": sorted({str(row["source_id"]) for row in rows}),
        "source_metadata_fingerprint": _fp(sorted(
            ({"source_id": row["source_id"], "identity": _identity(row)} for row in rows),
            key=lambda item: item["source_id"],
        )),
    }


def _fill(template: dict[str, Any], group: int, pairs, entries, catalog_fp, audit_fp):
    out = copy.deepcopy(template)
    out.pop("fingerprint", None)
    out["status"] = "READY" if group == 15 else "PRESENT"
    out["coverage_catalog_fingerprint"] = catalog_fp
    out["coverage_audit_fingerprint"] = audit_fp
    out["selected_pair_fingerprint"] = _fp(pairs)
    out["export_schema"] = SCHEMA
    dates, contract_map = GROUPS[group]
    definitions = {
        symbol: _definition(group, symbol, pairs, entries)
        for symbol in sorted({contract_map[day]["raw_symbol"] for day in dates})
    }
    if group == 15:
        out["definitions"] = definitions
    else:
        out["definition"] = definitions["NGK26"]
    filled = []
    for raw in out["sources"]:
        source = copy.deepcopy(raw)
        day, lane = str(source["day"]), str(source["source_kind"])
        source_id = pairs[day]["l1_source_id" if lane == "l1_trades" else "mbo_source_id"]
        observed = entries.get(source_id)
        if not observed or str(observed.get("status") or "").upper() != "PRESENT":
            raise ReplayCatalogExportError(f"G{group} {day}:{lane} source is not PRESENT")
        if (observed.get("day"), observed.get("lane")) != (day, lane):
            raise ReplayCatalogExportError(f"G{group} {day}:{lane} selected lane mismatch")
        target = contract_map[day]
        if (observed.get("dataset"), observed.get("raw_symbol"), observed.get("instrument_id")) != (
            DATASET, target["raw_symbol"], target["instrument_id"]
        ):
            raise ReplayCatalogExportError(f"G{group} {day}:{lane} basis mismatch")
        fields = (
            "location", "publisher_id", "definition_date", "definition_start_s",
            "definition_end_s", "event_start_s", "event_end_s", "record_count",
            "size_bytes", "sha256", "inventory_observed_at",
        )
        missing = [name for name in fields if observed.get(name) in (None, "")]
        if missing:
            raise ReplayCatalogExportError(f"G{group} {day}:{lane} missing {', '.join(missing)}")
        source.update({name: observed[name] for name in fields})
        source.update({
            "status": "PRESENT", "dataset": DATASET,
            "publisher_id": observed["publisher_id"],
            "instrument_id": target["instrument_id"], "raw_symbol": target["raw_symbol"],
            "coverage_source_id": source_id,
            "coverage_entry_fingerprint": _fp(observed),
            "coverage_pair_fingerprint": _fp(pairs[day]),
        })
        filled.append(source)
    out["sources"] = filled
    out["note"] = "Filled only from deterministic PRESENT exact pairs; UNKNOWN was not promoted."
    out["fingerprint"] = _fp(out)
    return out


def build_export_bundle(catalog, audit, g15_inventory, g16_inventory):
    before = copy.deepcopy((catalog, audit, g15_inventory, g16_inventory))
    coverage.validate_audit(audit)
    if coverage.build_audit(catalog) != audit:
        raise ReplayCatalogExportError("audit is not the deterministic rebuild of catalog")
    entries = _entries(catalog)
    p15, p16 = _pairs(audit, 15), _pairs(audit, 16)
    c15 = _fill(g15.build_catalog_template(g15_inventory), 15, p15, entries,
                catalog["catalog_fingerprint"], audit["fingerprint"])
    c16 = _fill(g16.build_catalog_template(g16_inventory), 16, p16, entries,
                catalog["catalog_fingerprint"], audit["fingerprint"])
    b15 = g15.build_replay_manifest(g15_inventory, c15)
    m16 = g16.build_manifest(g16_inventory, c16)
    bundle = {
        "schema": SCHEMA, "status": "READY", "market": "NG", "dataset": DATASET,
        "coverage_catalog_fingerprint": catalog["catalog_fingerprint"],
        "coverage_audit_fingerprint": audit["fingerprint"],
        "selected_day_pair_count": len(coverage.G15_DATES) + len(coverage.G16_DATES),
        "selected_source_lane_count": 2 * (len(coverage.G15_DATES) + len(coverage.G16_DATES)),
        "g15_catalog": c15, "g16_catalog": c16,
        "g15_bridge_fingerprint": b15["fingerprint"],
        "g16_manifest_fingerprint": m16["fingerprint"],
        "unknown_promoted_to_present": False, "actual_outcomes_used": False,
        "paid_live_data_assumed": False, "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True, "may_update_ng_brain": False,
        "execution_authority": False, "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr", "options_lane_started": False,
        "next_permitted_stage": "G15_G16_PREPARATION_AND_DETERMINISTIC_REPLAY",
    }
    bundle["fingerprint"] = _fp(bundle)
    if (catalog, audit, g15_inventory, g16_inventory) != before:
        raise ReplayCatalogExportError("export mutated an input artifact")
    validate_export_bundle(bundle)
    return bundle


def validate_export_bundle(bundle):
    checked = copy.deepcopy(bundle)
    observed = checked.pop("fingerprint", None)
    if observed != _fp(checked) or checked.get("schema") != SCHEMA or checked.get("status") != "READY":
        raise ReplayCatalogExportError("export fingerprint or schema mismatch")
    for field in (
        "unknown_promoted_to_present", "actual_outcomes_used", "paid_live_data_assumed",
        "may_update_ng_brain", "execution_authority", "options_lane_started",
    ):
        if checked.get(field) is not False:
            raise ReplayCatalogExportError(f"export must keep {field}=false")
    if checked.get("cme_event_contracts_mode") != "SHADOW":
        raise ReplayCatalogExportError("CME event contracts must remain SHADOW")
    if checked.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise ReplayCatalogExportError("brokerage must remain tastytrade, not IBKR")
    if checked.get("one_signal_authority_preserved") is not True:
        raise ReplayCatalogExportError("single signal authority must remain preserved")
    if checked.get("blind_forecasts_immutable") is not True:
        raise ReplayCatalogExportError("blind forecasts must remain immutable")
    expected_days = len(coverage.G15_DATES) + len(coverage.G16_DATES)
    if checked.get("selected_day_pair_count") != expected_days:
        raise ReplayCatalogExportError("selected day-pair count mismatch")
    if checked.get("selected_source_lane_count") != 2 * expected_days:
        raise ReplayCatalogExportError("selected source-lane count mismatch")
    expected_catalogs = (("g15_catalog", 24, "READY"), ("g16_catalog", 22, "PRESENT"))
    selected_ids: list[str] = []
    for field, expected_count, expected_status in expected_catalogs:
        catalog = checked.get(field)
        if not isinstance(catalog, Mapping):
            raise ReplayCatalogExportError(f"{field} is missing")
        nested = copy.deepcopy(dict(catalog))
        nested_fp = nested.pop("fingerprint", None)
        if nested_fp != _fp(nested):
            raise ReplayCatalogExportError(f"{field} fingerprint mismatch")
        if nested.get("status") != expected_status:
            raise ReplayCatalogExportError(f"{field} status mismatch")
        sources = nested.get("sources")
        if not isinstance(sources, list) or len(sources) != expected_count:
            raise ReplayCatalogExportError(f"{field} source-lane count mismatch")
        keys = [(str(row.get("day") or ""), str(row.get("source_kind") or "")) for row in sources]
        if len(keys) != len(set(keys)):
            raise ReplayCatalogExportError(f"{field} contains duplicate source lanes")
        for row in sources:
            if row.get("status") != "PRESENT":
                raise ReplayCatalogExportError(f"{field} contains a non-PRESENT source")
            source_id = str(row.get("coverage_source_id") or "")
            if not source_id:
                raise ReplayCatalogExportError(f"{field} source lacks coverage provenance")
            selected_ids.append(source_id)
    if len(selected_ids) != len(set(selected_ids)):
        raise ReplayCatalogExportError("a coverage source was selected for multiple replay lanes")
    return checked


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        i15 = g15._fixture_inventory()
        i16, d16 = g16._fixture_inventory(root)
        entries = {lane: [] for lane in LANES}
        for day in coverage.G15_DATES:
            row = g15._inventory_rows(i15)[day]
            target = coverage.G15_CONTRACT_MAP[day]
            for lane in LANES:
                start, end = g15._inventory_event_range(row, lane)
                count = g15._expected_inventory_count(row, lane)
                entries[lane].append(_fixture_row(day, lane, target, start, end, count))
        for day in coverage.G16_DATES:
            row = g16._inventory_rows(i16)[day]
            for lane in LANES:
                start, end = g16._inventory_range(row, lane)
                item = _fixture_row(day, lane, coverage.G16_CONTRACT_MAP[day], start, end,
                                    g16._expected_count(row, lane))
                item.update(definition_date=d16["definition_date"],
                            definition_start_s=d16["definition_start_s"],
                            definition_end_s=d16["definition_end_s"])
                entries[lane].append(item)
        catalog = coverage.expected_catalog_template(publisher_id=1)
        for corpus in catalog["corpora"]:
            corpus["entries"] = entries[corpus["lane"]]
            corpus["expected_days"] = list(coverage.G15_DATES + coverage.G16_DATES)
            corpus["expected_object_count"] = corpus["observed_object_count"] = len(corpus["entries"])
            corpus["remote_inventory_verified"] = corpus["inventory_complete"] = True
            corpus["inventory_observed_at"] = "2026-07-22T20:00:00Z"
        catalog.pop("catalog_fingerprint")
        catalog["catalog_fingerprint"] = coverage._fp(catalog)
        bundle = build_export_bundle(catalog, coverage.build_audit(catalog), i15, i16)
        assert len(bundle["g15_catalog"]["sources"]) == 24
        assert len(bundle["g16_catalog"]["sources"]) == 22
    print("[ng_corpus_replay_catalog_export] selftest PASS")
    return 0


def _fixture_row(day, lane, target, start, end, count):
    symbol = target["raw_symbol"]
    return {
        "day": day, "lane": lane, "source_id": f"{lane}:{day}:{symbol}",
        "status": "PRESENT", "location": f"file:///fixture/{day}-{lane}.dbn",
        "dataset": DATASET, "publisher_id": 1,
        "instrument_id": target["instrument_id"], "raw_symbol": symbol,
        "definition_date": "2026-03-01" if symbol == "NGJ26" else "2026-03-20",
        "definition_start_s": 0.0, "definition_end_s": 2_000_000_000.0,
        "event_start_s": start, "event_end_s": end, "record_count": count,
        "size_bytes": 1000 + count,
        "sha256": hashlib.sha256(f"{lane}:{day}:{symbol}".encode()).hexdigest(),
        "inventory_observed_at": "2026-07-22T20:00:00Z",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    for name in ("catalog", "audit", "g15-inventory", "g16-inventory",
                 "g15-out", "g16-out", "bundle-out"):
        parser.add_argument(f"--{name}", type=Path)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = (args.catalog, args.audit, args.g15_inventory, args.g16_inventory,
                args.g15_out, args.g16_out, args.bundle_out)
    if any(value is None for value in required):
        parser.error("all catalog, audit, inventory, and output arguments are required")
    bundle = build_export_bundle(_load(args.catalog), _load(args.audit),
                                 _load(args.g15_inventory), _load(args.g16_inventory))
    _write(args.g15_out, bundle["g15_catalog"])
    _write(args.g16_out, bundle["g16_catalog"])
    _write(args.bundle_out, bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
