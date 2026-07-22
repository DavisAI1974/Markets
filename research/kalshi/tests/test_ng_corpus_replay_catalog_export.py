from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ng_corpus_coverage_audit as coverage
import ng_corpus_replay_catalog_export as mod
import ng_g15_replay_manifest_bridge as g15
import ng_g16_historical_replay as g16


def _refingerprint(value: dict, field: str) -> None:
    value.pop(field, None)
    value[field] = coverage._fp(value)


def _inputs(root: Path):
    g15_inventory = g15._fixture_inventory()
    g16_inventory, g16_definition = g16._fixture_inventory(root)
    entries = {lane: [] for lane in mod.LANES}

    g15_rows = g15._inventory_rows(g15_inventory)
    for day in coverage.G15_DATES:
        basis = g15_rows[day]
        target = coverage.G15_CONTRACT_MAP[day]
        for lane in mod.LANES:
            start, end = g15._inventory_event_range(basis, lane)
            row = mod._fixture_row(
                day,
                lane,
                target,
                start,
                end,
                g15._expected_inventory_count(basis, lane),
            )
            entries[lane].append(row)

    g16_rows = g16._inventory_rows(g16_inventory)
    for day in coverage.G16_DATES:
        basis = g16_rows[day]
        target = coverage.G16_CONTRACT_MAP[day]
        for lane in mod.LANES:
            start, end = g16._inventory_range(basis, lane)
            row = mod._fixture_row(
                day,
                lane,
                target,
                start,
                end,
                g16._expected_count(basis, lane),
            )
            row.update(
                definition_date=g16_definition["definition_date"],
                definition_start_s=g16_definition["definition_start_s"],
                definition_end_s=g16_definition["definition_end_s"],
            )
            entries[lane].append(row)

    catalog = coverage.expected_catalog_template(publisher_id=1)
    target_days = list(coverage.G15_DATES + coverage.G16_DATES)
    for corpus in catalog["corpora"]:
        corpus["entries"] = entries[corpus["lane"]]
        corpus["expected_days"] = target_days
        corpus["expected_object_count"] = len(corpus["entries"])
        corpus["observed_object_count"] = len(corpus["entries"])
        corpus["remote_inventory_verified"] = True
        corpus["inventory_complete"] = True
        corpus["inventory_observed_at"] = "2026-07-22T20:00:00Z"
    _refingerprint(catalog, "catalog_fingerprint")
    audit = coverage.build_audit(catalog)
    return catalog, audit, g15_inventory, g16_inventory


class ReplayCatalogExportTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.catalog, self.audit, self.g15_inventory, self.g16_inventory = _inputs(self.root)

    def tearDown(self):
        self.tempdir.cleanup()

    def build(self):
        return mod.build_export_bundle(
            self.catalog,
            self.audit,
            self.g15_inventory,
            self.g16_inventory,
        )

    def rebuild_audit(self):
        _refingerprint(self.catalog, "catalog_fingerprint")
        self.audit = coverage.build_audit(self.catalog)

    def test_exports_canonical_24_and_22_lane_catalogs(self):
        bundle = self.build()
        self.assertEqual(len(bundle["g15_catalog"]["sources"]), 24)
        self.assertEqual(len(bundle["g16_catalog"]["sources"]), 22)
        self.assertEqual(bundle["selected_day_pair_count"], 23)
        self.assertEqual(bundle["selected_source_lane_count"], 46)
        self.assertEqual(len(bundle["g15_bridge_fingerprint"]), 64)
        self.assertEqual(len(bundle["g16_manifest_fingerprint"]), 64)
        mod.validate_export_bundle(bundle)

    def test_downstream_manifest_builders_accept_exported_catalogs(self):
        bundle = self.build()
        bridge = g15.build_replay_manifest(self.g15_inventory, bundle["g15_catalog"])
        manifest = g16.build_manifest(self.g16_inventory, bundle["g16_catalog"])
        self.assertEqual(bridge["manifest_report"]["status"], "READY")
        self.assertEqual(len(bridge["manifest"]["entries"]), 24)
        self.assertEqual(manifest["status"], "READY")
        self.assertEqual(len(manifest["entries"]), 22)

    def test_inputs_remain_immutable(self):
        before = copy.deepcopy(
            (self.catalog, self.audit, self.g15_inventory, self.g16_inventory)
        )
        self.build()
        self.assertEqual(
            (self.catalog, self.audit, self.g15_inventory, self.g16_inventory),
            before,
        )

    def test_refingerprinted_audit_selection_tamper_is_rejected(self):
        report = self.audit["exact_intersections"]["g15"]["day_reports"][0]
        report["selected_pair"]["l1_source_id"] = "invented-source"
        _refingerprint(self.audit, "fingerprint")
        with self.assertRaisesRegex(mod.ReplayCatalogExportError, "deterministic rebuild"):
            self.build()

    def test_unknown_source_is_not_promoted(self):
        self.catalog["corpora"][0]["entries"][0]["status"] = "UNKNOWN"
        self.rebuild_audit()
        with self.assertRaisesRegex(mod.ReplayCatalogExportError, "not replay-ready"):
            self.build()

    def test_wrong_basis_is_not_relabelled(self):
        row = self.catalog["corpora"][0]["entries"][0]
        row["raw_symbol"] = "NGK26"
        row["instrument_id"] = 996
        self.rebuild_audit()
        with self.assertRaisesRegex(mod.ReplayCatalogExportError, "not replay-ready"):
            self.build()

    def test_nonoverlapping_event_ranges_block_export(self):
        day = coverage.G15_DATES[0]
        l1 = next(
            row
            for corpus in self.catalog["corpora"]
            for row in corpus["entries"]
            if row["day"] == day and row["lane"] == "l1_trades"
        )
        mbo = next(
            row
            for corpus in self.catalog["corpora"]
            for row in corpus["entries"]
            if row["day"] == day and row["lane"] == "mbo"
        )
        mbo["event_start_s"] = l1["event_end_s"] + 1.0
        mbo["event_end_s"] = l1["event_end_s"] + 2.0
        self.rebuild_audit()
        with self.assertRaisesRegex(mod.ReplayCatalogExportError, "not replay-ready"):
            self.build()

    def test_cross_day_definition_disagreement_blocks_export(self):
        day = coverage.G15_DATES[1]
        for corpus in self.catalog["corpora"]:
            for row in corpus["entries"]:
                if row["day"] == day:
                    row["definition_date"] = "2026-03-02"
        self.rebuild_audit()
        with self.assertRaisesRegex(mod.ReplayCatalogExportError, "disagrees across days"):
            self.build()

    def test_selected_source_missing_required_metadata_blocks_export(self):
        self.catalog["corpora"][0]["entries"][0]["location"] = None
        self.rebuild_audit()
        with self.assertRaisesRegex(mod.ReplayCatalogExportError, "missing location"):
            self.build()

    def test_basis_inventory_count_mismatch_is_rejected_downstream(self):
        row = next(
            item for item in self.g15_inventory
            if str(item.get("date") or "").replace("-", "") == coverage.G15_DATES[0]
        )
        row["l1_n_trades"] += 1
        with self.assertRaises(Exception):
            self.build()

    def test_deterministic_lexical_tie_break_is_preserved(self):
        day = coverage.G15_DATES[0]
        for corpus in self.catalog["corpora"]:
            original = next(row for row in corpus["entries"] if row["day"] == day)
            duplicate = copy.deepcopy(original)
            duplicate["source_id"] = f"000-{corpus['lane']}"
            duplicate["location"] = f"s3://observed/000-{corpus['lane']}"
            corpus["entries"].append(duplicate)
            corpus["expected_object_count"] += 1
            corpus["observed_object_count"] += 1
        self.rebuild_audit()
        bundle = self.build()
        selected = {
            row["coverage_source_id"]
            for row in bundle["g15_catalog"]["sources"]
            if row["day"] == day
        }
        self.assertEqual(selected, {"000-l1_trades", "000-mbo"})

    def test_basis_and_coverage_provenance_are_both_retained(self):
        row = self.build()["g15_catalog"]["sources"][0]
        self.assertEqual(len(row["basis_row_fingerprint"]), 64)
        self.assertEqual(len(row["coverage_entry_fingerprint"]), 64)
        self.assertEqual(len(row["coverage_pair_fingerprint"]), 64)
        self.assertTrue(row["coverage_source_id"])

    def test_bundle_count_tamper_is_rejected_even_after_refingerprint(self):
        bundle = self.build()
        bundle["selected_source_lane_count"] = 45
        _refingerprint(bundle, "fingerprint")
        with self.assertRaisesRegex(mod.ReplayCatalogExportError, "source-lane count"):
            mod.validate_export_bundle(bundle)

    def test_nested_catalog_tamper_is_rejected_even_after_refingerprint(self):
        bundle = self.build()
        bundle["g16_catalog"]["sources"].pop()
        _refingerprint(bundle["g16_catalog"], "fingerprint")
        _refingerprint(bundle, "fingerprint")
        with self.assertRaisesRegex(mod.ReplayCatalogExportError, "source-lane count"):
            mod.validate_export_bundle(bundle)

    def test_authority_and_brokerage_contract_remain_fail_closed(self):
        bundle = self.build()
        self.assertFalse(bundle["unknown_promoted_to_present"])
        self.assertFalse(bundle["actual_outcomes_used"])
        self.assertFalse(bundle["paid_live_data_assumed"])
        self.assertFalse(bundle["may_update_ng_brain"])
        self.assertFalse(bundle["execution_authority"])
        self.assertFalse(bundle["options_lane_started"])
        self.assertTrue(bundle["one_signal_authority_preserved"])
        self.assertTrue(bundle["blind_forecasts_immutable"])
        self.assertEqual(bundle["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(bundle["brokerage_contract"], "tastytrade_not_ibkr")


if __name__ == "__main__":
    unittest.main()
