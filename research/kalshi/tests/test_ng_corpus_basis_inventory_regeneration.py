from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ng_corpus_basis_inventory_regeneration as mod
import ng_corpus_coverage_audit as coverage
import ng_corpus_inspection as inspection
import ng_corpus_target_day_slicer as slicer


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ts(day: str, second: int) -> float:
    dt = datetime(
        int(day[:4]), int(day[4:6]), int(day[6:8]), tzinfo=timezone.utc
    )
    return dt.timestamp() + second


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _definition(symbol: str, instrument_id: int) -> dict:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    end = datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()
    return inspection.definition_observation(
        dataset=coverage.DATASET,
        publisher_id=1,
        instrument_id=instrument_id,
        raw_symbol=symbol,
        definition_date="2026-01-01" if symbol == "NGJ26" else "2026-03-01",
        definition_start_s=start,
        definition_end_s=end,
        observed_from=f"s3://observed/definitions/{symbol}.dbn",
        observed_at="2026-07-23T00:00:00Z",
        source_sha256=("a" if symbol == "NGJ26" else "b") * 64,
        source_size_bytes=10,
    )


def _normalized_rows(
    day: str,
    lane: str,
    definition: dict,
    *,
    queue_gap: bool,
    mbo_trade: bool,
):
    common = {
        "schema": "ng_normalized_event.v1",
        "dataset": definition["dataset"],
        "publisher_id": definition["publisher_id"],
        "instrument_id": definition["instrument_id"],
        "raw_symbol": definition["raw_symbol"],
        "definition_date": definition["definition_date"],
        "session_day": day,
        "source_id": f"fixture:{lane}:{day}",
    }
    if lane == "l1_trades":
        return [
            {
                **common,
                "event_type": "trade",
                "ts_event_s": _ts(day, 10),
                "source_sequence": 1,
                "ingest_sequence": 1,
                "price": 3.0,
                "size": 2.0,
                "side": "B",
            },
            {
                **common,
                "event_type": "trade",
                "ts_event_s": _ts(day, 20),
                "source_sequence": 2,
                "ingest_sequence": 2,
                "price": 3.01,
                "size": 1.0,
                "side": "A",
            },
        ]
    sequences = [1, 3, 4] if queue_gap else [1, 2, 3]
    rows = [
        {
            **common,
            "event_type": "mbo",
            "ts_event_s": _ts(day, 9),
            "source_sequence": sequences[0],
            "ingest_sequence": 1,
            "action": "A",
            "side": "B",
            "size": 5.0,
            "order_id": 10,
            "price": 3.0,
            "flags": 0,
        }
    ]
    if mbo_trade:
        rows.append(
            {
                **common,
                "event_type": "mbo",
                "ts_event_s": _ts(day, 15),
                "source_sequence": sequences[1],
                "ingest_sequence": 2,
                "action": "T",
                "side": "A",
                "size": 1.0,
                "order_id": 11,
                "price": 3.01,
                "flags": 0,
            }
        )
    rows.append(
        {
            **common,
            "event_type": "mbo",
            "ts_event_s": _ts(day, 21),
            "source_sequence": sequences[2],
            "ingest_sequence": 3 if mbo_trade else 2,
            "action": "C",
            "side": "B",
            "size": 0.0,
            "order_id": 10,
            "price": 3.0,
            "flags": 128,
        }
    )
    return rows


def _candidate(
    root: Path,
    day: str,
    lane: str,
    definition: dict,
    *,
    queue_gap: bool,
    mbo_trade: bool,
):
    path = root / f"{day}_{lane}.jsonl"
    rows = _normalized_rows(
        day,
        lane,
        definition,
        queue_gap=queue_gap,
        mbo_trade=mbo_trade,
    )
    _write_jsonl(path, rows)
    normalized_source_id = f"target-slice:{lane}:{day}:{definition['raw_symbol']}"
    candidate = {
        "candidate_id": mod._fp(
            {
                "day": day,
                "lane": lane,
                "definition_fingerprint": definition["definition_fingerprint"],
            }
        ),
        "object_id": f"object:{lane}:{day}",
        "source_location": f"s3://observed/cumulative/{lane}.dbn.zst",
        "quarantine_object_fingerprint": "q" * 64,
        "probe_object_fingerprint": "p" * 64,
        "probe_evidence_fingerprint": "e" * 64,
        "proposed_binding_fingerprint": "b" * 64,
        "corpus_id": (
            coverage.L1_CORPUS_ID
            if lane == "l1_trades"
            else coverage.MBO_CORPUS_ID
        ),
        "target": slicer._target_label(day),
        "day": day,
        "lane": lane,
        "definition": copy.deepcopy(definition),
        "definition_fingerprint": definition["definition_fingerprint"],
        "materialized_path": str(path),
        "record_count": len(rows),
        "event_start_s": rows[0]["ts_event_s"],
        "event_end_s": rows[-1]["ts_event_s"],
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "normalized_source_id": normalized_source_id,
        "input_record_count": len(rows),
        "skipped_nonmatching": 0,
        "skipped_nontarget": 0,
        "derived_from_cumulative_or_multiday_object": True,
        "source_bytes_unchanged": True,
        "identity_inferred_from_object_name": False,
        "session_day_inferred_from_object_name": False,
    }
    candidate["candidate_fingerprint"] = mod._fp(candidate)
    return candidate


def _inputs(
    root: Path, *, queue_gap: bool = False, mbo_trade: bool = True
):
    root.mkdir(parents=True, exist_ok=True)
    definitions = {
        "NGJ26": _definition("NGJ26", 1008),
        "NGK26": _definition("NGK26", 996),
    }
    candidates = []
    for day in slicer._target_days():
        expected = slicer._target_identity(day)
        definition = definitions[expected["raw_symbol"]]
        for lane in coverage.LANES:
            candidates.append(
                _candidate(
                    root,
                    day,
                    lane,
                    definition,
                    queue_gap=queue_gap and lane == "mbo",
                    mbo_trade=mbo_trade,
                )
            )
    selections = slicer._selection_rows(candidates)
    pairs = slicer._pair_rows(selections, candidates)
    status, groups = slicer._status(pairs)
    snapshot = {"observed_at": "2026-07-23T00:00:00Z"}
    plan = slicer._build_inspection_plan(
        selections=selections,
        candidates=candidates,
        output_root=root,
        snapshot=snapshot,
        bundle_fingerprint=None,
    )
    bundle = {
        "schema": slicer.SCHEMA,
        "status": status,
        "snapshot_fingerprint": "s" * 64,
        "quarantine_fingerprint": "q" * 64,
        "definition_catalog_fingerprint": "d" * 64,
        "definition_probe_gate_fingerprint": "g" * 64,
        "probe_fingerprint": "p" * 64,
        "proposed_binding_manifest_fingerprint": "b" * 64,
        "output_root": str(root),
        "target_days": list(slicer._target_days()),
        "candidate_count": len(candidates),
        "candidates": sorted(
            candidates,
            key=lambda row: (row["day"], row["lane"], row["candidate_id"]),
        ),
        "selections": selections,
        "pairs": pairs,
        "groups": groups,
        "skipped_objects": [],
        "selection_may_use_record_count_or_filename_alone": False,
        "conflicting_candidates_stand_down": True,
        "broad_corpus_completeness_asserted": False,
        "source_bytes_untouched": True,
        "random_shuffle_used": False,
        **slicer._authority(),
        "inspection_plan_fingerprint": plan["plan_fingerprint"],
        "inspection_plan": plan,
    }
    bundle["slice_bundle_fingerprint"] = mod._fp(bundle)
    _, _, receipt = inspection.build_catalog(plan)
    return bundle, receipt


def _refingerprint(value: dict, field: str) -> None:
    value.pop(field, None)
    value[field] = mod._fp(value)


class BasisInventoryRegenerationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.slice_bundle, self.receipt = _inputs(self.root)

    def tearDown(self):
        self.tempdir.cleanup()

    def build(self):
        return mod.build_basis_inventories(self.slice_bundle, self.receipt)

    def test_builds_ready_canonical_g15_and_g16_inventories(self):
        g15, g16, bundle = self.build()
        self.assertEqual(
            [row["date"] for row in g15], list(mod.g15_basis.CANONICAL_DATES)
        )
        self.assertEqual(
            [row["date"] for row in g16["rows"]],
            list(mod.g16_basis.CANONICAL_DATES),
        )
        self.assertEqual(
            bundle["status"], "G15_G16_BASIS_INVENTORIES_READY"
        )
        self.assertEqual(
            bundle["g15_basis_report"]["status"], "MATCHED_L1_MBO_READY"
        )
        self.assertEqual(
            bundle["g16_basis_report"]["status"], "MATCHED_L1_MBO_READY"
        )

    def test_daily_counts_come_from_exact_shards(self):
        g15, g16, bundle = self.build()
        for row in g15 + g16["rows"]:
            self.assertEqual(row["l1_n_trades"], 2)
            self.assertEqual(row["n_mbo"], 3)
            self.assertEqual(row["n_trades"], 1)
            self.assertTrue(row["daily_counts_derived_from_inspected_shards"])
            self.assertFalse(row["cumulative_source_counts_reused"])
        self.assertTrue(bundle["daily_counts_derived_from_inspected_shards"])
        self.assertFalse(bundle["cumulative_source_counts_reused"])

    def test_event_ranges_and_hashes_are_bound_to_daily_bytes(self):
        g15, _, _ = self.build()
        row = g15[0]
        self.assertEqual(row["l1_first_event_s"], _ts(row["date"], 10))
        self.assertEqual(row["mbo_last_event_s"], _ts(row["date"], 21))
        self.assertEqual(len(row["l1_sha256"]), 64)
        self.assertEqual(len(row["mbo_sha256"]), 64)

    def test_inputs_remain_immutable(self):
        before = copy.deepcopy((self.slice_bundle, self.receipt))
        self.build()
        self.assertEqual((self.slice_bundle, self.receipt), before)

    def test_queue_sequence_gaps_are_visible_stand_downs(self):
        self.slice_bundle, self.receipt = _inputs(
            self.root / "gap", queue_gap=True
        )
        g15, g16, bundle = self.build()
        self.assertEqual(
            bundle["status"],
            "G15_G16_BASIS_INVENTORIES_READY_WITH_QUEUE_STAND_DOWNS",
        )
        self.assertEqual(len(bundle["queue_stand_down_days"]), 24)
        self.assertTrue(
            all(row["queue_usable"] is False for row in g15 + g16["rows"])
        )
        self.assertTrue(
            all(row["flow_usable"] is True for row in g15 + g16["rows"])
        )

    def test_missing_mbo_trades_blocks_flow_without_inventing_evidence(self):
        self.slice_bundle, self.receipt = _inputs(
            self.root / "no_trade", mbo_trade=False
        )
        g15, g16, bundle = self.build()
        self.assertEqual(bundle["status"], "BLOCKED")
        self.assertEqual(len(bundle["flow_stand_down_days"]), 24)
        self.assertTrue(
            all(row["n_trades"] == 0 for row in g15 + g16["rows"])
        )
        self.assertEqual(bundle["g15_basis_report"]["status"], "BLOCKED")
        self.assertEqual(bundle["g16_basis_report"]["status"], "BLOCKED")

    def test_slice_bundle_fingerprint_tamper_is_rejected(self):
        self.slice_bundle["candidate_count"] += 1
        with self.assertRaisesRegex(
            mod.BasisInventoryRegenerationError, "fingerprint"
        ):
            self.build()

    def test_refingerprinted_selection_tamper_is_rejected(self):
        self.slice_bundle["selections"][0][
            "selected_candidate_id"
        ] = "invented"
        _refingerprint(self.slice_bundle, "slice_bundle_fingerprint")
        with self.assertRaisesRegex(
            mod.BasisInventoryRegenerationError, "selections"
        ):
            self.build()

    def test_receipt_must_belong_to_slice_plan(self):
        self.receipt["plan_fingerprint"] = "x" * 64
        _refingerprint(self.receipt, "receipt_fingerprint")
        with self.assertRaisesRegex(
            mod.BasisInventoryRegenerationError, "does not belong"
        ):
            self.build()

    def test_catalog_candidate_hash_disagreement_is_rejected(self):
        catalog = self.receipt["catalog"]
        entry = catalog["corpora"][0]["entries"][0]
        entry["sha256"] = "f" * 64
        _refingerprint(entry, "inspection_fingerprint")
        _refingerprint(catalog, "catalog_fingerprint")
        audit = coverage.build_audit(catalog)
        self.receipt["catalog_fingerprint"] = catalog["catalog_fingerprint"]
        self.receipt["audit"] = audit
        self.receipt["audit_fingerprint"] = audit["fingerprint"]
        self.receipt["source_inspection_fingerprints"][
            entry["source_id"]
        ] = entry["inspection_fingerprint"]
        _refingerprint(self.receipt, "receipt_fingerprint")
        with self.assertRaisesRegex(
            mod.BasisInventoryRegenerationError,
            "differs from selected shard",
        ):
            self.build()

    def test_changed_daily_file_is_rejected(self):
        path = Path(
            self.receipt["catalog"]["corpora"][0]["entries"][0][
                "materialized_path"
            ]
        )
        path.write_text(
            path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(
            mod.BasisInventoryRegenerationError, "bytes changed"
        ):
            self.build()

    def test_unexpected_extra_inspected_source_is_rejected(self):
        corpus = self.receipt["catalog"]["corpora"][0]
        extra = copy.deepcopy(corpus["entries"][0])
        extra["source_id"] = "extra-source"
        _refingerprint(extra, "inspection_fingerprint")
        corpus["entries"].append(extra)
        corpus["observed_object_count"] += 1
        _refingerprint(self.receipt["catalog"], "catalog_fingerprint")
        audit = coverage.build_audit(self.receipt["catalog"])
        self.receipt["catalog_fingerprint"] = self.receipt["catalog"][
            "catalog_fingerprint"
        ]
        self.receipt["audit"] = audit
        self.receipt["audit_fingerprint"] = audit["fingerprint"]
        self.receipt["source_statuses"][extra["source_id"]] = "PRESENT"
        self.receipt["source_inspection_fingerprints"][
            extra["source_id"]
        ] = extra["inspection_fingerprint"]
        self.receipt["present_count"] += 1
        _refingerprint(self.receipt, "receipt_fingerprint")
        with self.assertRaisesRegex(
            mod.BasisInventoryRegenerationError, "source set mismatch"
        ):
            self.build()

    def test_inventory_tamper_is_rejected_even_after_bundle_refingerprint(self):
        g15, g16, bundle = self.build()
        g15[0]["l1_n_trades"] += 1
        bundle["g15_inventory_fingerprint"] = mod._fp(g15)
        _refingerprint(bundle, "fingerprint")
        with self.assertRaises(Exception):
            mod.validate_regeneration_bundle(
                bundle,
                g15,
                g16,
                slice_bundle=self.slice_bundle,
                inspection_receipt=self.receipt,
            )

    def test_bundle_authority_cannot_be_escalated(self):
        g15, g16, bundle = self.build()
        bundle["may_update_ng_brain"] = True
        _refingerprint(bundle, "fingerprint")
        with self.assertRaisesRegex(
            mod.BasisInventoryRegenerationError, "may_update_ng_brain"
        ):
            mod.validate_regeneration_bundle(
                bundle, g15, g16, rebuild=False
            )

    def test_brokerage_and_options_contract_remain_locked(self):
        _, _, bundle = self.build()
        self.assertEqual(bundle["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertEqual(bundle["cme_event_contracts_mode"], "SHADOW")
        self.assertFalse(bundle["options_lane_started"])
        self.assertFalse(bundle["execution_authority"])

    def test_deterministic_rebuild(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
