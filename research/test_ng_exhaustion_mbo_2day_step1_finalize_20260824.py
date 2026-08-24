from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_exhaustion_mbo_5y_step1_census_20260822 as base
import ng_exhaustion_mbo_2day_step1_finalize_20260824 as subject


PARENT_MANIFEST = Path(
    "research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json"
)


def _second(epoch_second: int) -> dict:
    row = base.SecondAggregator._row(epoch_second)
    row.update(
        {
            "legacy_rows": 1,
            "legacy_buy_qty": 2.0,
            "native_buy_qty": 2.0,
            "trade_count": 1,
            "last_trade_price": 6.0,
            "last_ts_recv_ns": epoch_second * 1_000_000_000,
            "last_raw_symbol": "NGX21",
            "last_instrument_id": 1,
        }
    )
    return row


def _write_synthetic_october_child(root: Path) -> tuple[Path, Path, subject.ExpectedOctoberIdentity]:
    manifest = base.load_manifest(PARENT_MANIFEST)
    seconds_path = root / "20211001_20211101.seconds.jsonl.gz"
    start = subject.WINDOW_START_EPOCH
    end = subject.WINDOW_END_EPOCH
    seconds_output = base.deterministic_gzip_jsonl(
        seconds_path,
        (
            _second(start - 1),
            _second(start),
            _second(start + 43_200),
            _second(end - 1),
            _second(end),
        ),
    )
    october_objects = base._segment_objects(manifest, subject.OCTOBER_SEGMENT, None)
    receipt = {
        "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_SEGMENT_RECEIPT_V1",
        "revision": base.REVISION,
        "segment": subject.OCTOBER_SEGMENT,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "source_scope": base._segment_source_scope(
            manifest, subject.OCTOBER_SEGMENT, None
        ),
        "engine_hashes": base.material_hashes(),
        "ruleset_sha256": base.ruleset_sha256(),
        "status": "SEGMENT_COMPLETE",
        "source_object_count": len(october_objects),
        "source_objects": [
            {key: row[key] for key in ("key", "bytes", "sha256", "native_segment_job_id")}
            for row in october_objects
        ],
        "replay_summary": {"synthetic_test_fixture": True},
        "seconds_output": seconds_output,
        "case_retention_policy": base.RULESET,
        "release_or_virgin_holdout_consumed": False,
        "predictive_or_trading_experiment_run": False,
        "completed_at_utc": "2026-08-24T00:00:00+00:00",
    }
    receipt["receipt_sha256"] = base.sha256_json(receipt)
    receipt_path = root / "20211001_20211101.receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    expected = subject.ExpectedOctoberIdentity(
        seconds_bytes=seconds_path.stat().st_size,
        seconds_sha256=base.sha256_file(seconds_path),
        receipt_file_sha256=base.sha256_file(receipt_path),
        receipt_sha256=receipt["receipt_sha256"],
    )
    return seconds_path, receipt_path, expected


def _fake_events(view: str) -> list[dict]:
    native = view == "V4_NATIVE_FULL"
    rows = []
    families = ("A", "B", "C", "A", "B", "C", "A")
    for index, family in enumerate(families):
        event_id = f"20211003-{90_000 + index * 90:06d}-{1 if index % 2 == 0 else -1:+d}"
        if native:
            event_id = "V4N1|" + event_id
        horizons = {
            str(horizon): {
                "censored": False,
                "signed_displacement_ticks": float((index + 1) ** 2 + horizon / 100),
                "mfe_ticks": float((index + 1) ** 3 + horizon / 50),
                "mae_ticks": -float((index + 1) * 0.5 + horizon / 200),
            }
            for horizon in base.frozen_detector.HORIZONS
        }
        previous_id = None if index == 0 else rows[-1]["event_id"]
        rows.append(
            {
                "event_id": event_id,
                "week_sunday": "20211003",
                "sequence_index": index,
                "t0_idx": 90_000 + index * 90,
                "polarity": 1 if index % 2 == 0 else -1,
                "family": family,
                "link": {
                    "previous_event_id": previous_id,
                    "next_event_id": None,
                    "next_same_polarity": None if index == 6 else int(index % 3 == 0),
                },
                "dynamic_endpoint": {
                    "causal_confirmation_idx": 90_003 + index * 90
                },
                "outcome": {
                    "post_endpoint_price": {
                        "endpoint_price": 6.0 + index / 100,
                        "horizons": horizons,
                    }
                },
                "source_boundary_censored": True,
                "source_provenance": {
                    "source_dbn_key": "exact.dbn.zst",
                    "source_dbn_sha256": "a" * 64,
                    "contract_resolution_status": "RESOLVED_FROM_DBN_METADATA",
                },
                "native_structure": (
                    {
                        "taxonomy": base.NATIVE_TAXONOMY,
                        "label": "synthetic-native",
                        "integrity_at_t0": {},
                    }
                    if native
                    else None
                ),
            }
        )
    for index, row in enumerate(rows[:-1]):
        row["link"]["next_event_id"] = rows[index + 1]["event_id"]
    return rows


class TwoDayStep1FinalizerTests(unittest.TestCase):
    def test_adapter_uses_exact_frozen_detector_feature_lineage_and_crosswalk_functions(self):
        self.assertIs(subject.FROZEN_DETECT_EVENTS, base.detect_events_for_week)
        self.assertIs(subject.FROZEN_COMPACT_LINEAGE, base.compact_lineage_input)
        self.assertIs(
            subject.FROZEN_BEHAVIOR_VECTOR, base.frozen_discovery.behavior_vector
        )
        self.assertIs(subject.FROZEN_BUILD_CROSSWALK, base.build_crosswalk)
        post = {
            "horizons": {
                str(horizon): {
                    "censored": False,
                    "signed_displacement_ticks": float(horizon),
                    "mfe_ticks": float(horizon + 1),
                    "mae_ticks": -float(horizon + 1),
                }
                for horizon in base.frozen_detector.HORIZONS
            }
        }
        sample = {"next_same": 1, "post": post}
        self.assertEqual(
            subject.FROZEN_BEHAVIOR_VECTOR(sample, "full")[:8],
            subject.FROZEN_BEHAVIOR_VECTOR(sample, "sparse"),
        )

    def test_validates_child_and_filters_exact_half_open_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            seconds_path, receipt_path, expected = _write_synthetic_october_child(
                Path(tmp)
            )
            validated = subject.validate_october_child(
                PARENT_MANIFEST,
                seconds_path,
                receipt_path,
                expected_identity=expected,
            )
            rows = list(subject.iter_two_day_seconds(seconds_path))

        self.assertEqual(validated["receipt_sha256"], expected.receipt_sha256)
        self.assertEqual(
            [row["epoch_second"] for row in rows],
            [
                subject.WINDOW_START_EPOCH,
                subject.WINDOW_START_EPOCH + 43_200,
                subject.WINDOW_END_EPOCH - 1,
            ],
        )

    def test_child_tamper_fails_closed_before_finalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seconds_path, receipt_path, expected = _write_synthetic_october_child(root)
            with gzip.open(seconds_path, "at") as handle:
                handle.write(json.dumps(_second(subject.WINDOW_START_EPOCH + 10)) + "\n")

            with self.assertRaisesRegex(base.CensusError, "seconds (byte|SHA-256) drift"):
                subject.finalize_two_day_step1(
                    PARENT_MANIFEST,
                    seconds_path,
                    receipt_path,
                    root / "out",
                    expected_identity=expected,
                )

            self.assertFalse((root / "out").exists())

    def test_finalizer_reuses_frozen_steps_and_emits_scored_d0_d5_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seconds_path, receipt_path, expected = _write_synthetic_october_child(root)
            out = root / "out"

            with mock.patch.object(
                subject,
                "FROZEN_DETECT_EVENTS",
                side_effect=lambda _rows, view, _pre, _a: _fake_events(view),
            ) as detector:
                receipt = subject.finalize_two_day_step1(
                    PARENT_MANIFEST,
                    seconds_path,
                    receipt_path,
                    out,
                    expected_identity=expected,
                )

            self.assertEqual(detector.call_count, 2)
            self.assertEqual(receipt["source_window"]["start"], subject.WINDOW_START_ISO)
            self.assertEqual(
                receipt["source_window"]["end_exclusive"], subject.WINDOW_END_ISO
            )
            self.assertEqual(receipt["selected_seconds"]["rows"], 3)
            self.assertEqual(receipt["event_counts"], {"legacy": 7, "native": 7})
            self.assertEqual(
                receipt["family_counts"]["legacy"], {"A": 3, "B": 2, "C": 2}
            )
            self.assertEqual(
                receipt["family_counts"]["native"], {"A": 3, "B": 2, "C": 2}
            )

            validation = receipt["diagnostic_validation"]
            self.assertEqual(
                validation["status"],
                "USER_AUTHORIZED_SELF_FIT_SELF_SCORE_DIAGNOSTIC_ACCEPTED",
            )
            self.assertEqual(validation["observed_week_count"], 1)
            self.assertTrue(validation["d0_d5_population_claimable"])
            self.assertTrue(validation["d1_d5_scores_accepted"])
            self.assertFalse(validation["out_of_time_validation_claimed"])
            self.assertEqual(
                validation["only_methodological_exception"],
                "REPLACE_52_WEEK_OUT_OF_TIME_SPLIT_WITH_TWO_DAY_SELF_FIT_SELF_SCORE",
            )
            self.assertFalse(receipt["comparison_to_54w_answers_performed"])

            for view in ("legacy", "native"):
                structural = receipt["structural_outputs"][view]
                self.assertEqual(structural["dimension"], 22)
                self.assertEqual(set(structural["depth"]), {"1", "2", "3", "4", "5"})
                for depth in structural["depth"].values():
                    self.assertEqual(
                        set(depth), {"ridge", "extra_trees", "knn"}
                    )
                self.assertEqual(structural["gain_output"]["rows"], 45)
                self.assertIn("path", structural["gain_output"])
                self.assertTrue(
                    (out / structural["gain_output"]["relative_path"]).is_file()
                )
                self.assertEqual(structural["sparse_sensitivity"]["dimension"], 8)
                self.assertEqual(
                    set(structural["sparse_sensitivity"]["depth"]),
                    {"1", "2", "3", "4", "5"},
                )
                self.assertEqual(
                    set(structural["aggregate"]), {"1", "2", "3", "4", "5"}
                )
                histogram = receipt[f"{view}_population_summary"]["depth_histogram"]
                self.assertEqual(sum(int(value) for value in histogram.values()), 7)
                self.assertTrue(set(int(key) for key in histogram).issubset(set(range(6))))

            self.assertFalse(receipt["child_output_reuse"]["raw_mbo_replayed"])
            self.assertFalse(receipt["provider_llm_called"])
            self.assertFalse(receipt["external_provider_model_called"])
            self.assertTrue(receipt["local_structural_models_fitted"])
            self.assertEqual(
                receipt["local_structural_model_families"],
                ["ridge", "extra_trees", "knn"],
            )
            self.assertFalse(receipt["frankie_launched"])
            self.assertEqual(len(receipt["diagnostic_adapter"]["sha256"]), 64)

            for view in ("legacy", "native"):
                population_path = out / receipt["population_outputs"][view]["relative_path"]
                with gzip.open(population_path, "rt") as handle:
                    rows = [json.loads(line) for line in handle]
                self.assertEqual(len(rows), 7)
                self.assertEqual(
                    [row["origin_sequence_index"] for row in rows], list(range(7))
                )
                self.assertTrue(
                    all(0 <= row["realized_structural_depth"] <= 5 for row in rows)
                )
                self.assertTrue(rows[-1]["unresolved"])
                self.assertIn(
                    "D1_NO_SCORED_DESCENDANT_IN_TWO_DAY_WINDOW",
                    rows[-1]["inherited_information_uncertainty"],
                )
                self.assertTrue(
                    all(
                        row["diagnostic_adapter"]["sha256"]
                        == receipt["diagnostic_adapter"]["sha256"]
                        for row in rows
                    )
                )
                self.assertFalse(
                    any(
                        "OOT" in reason
                        for row in rows
                        for reason in row["inherited_information_uncertainty"]
                    )
                )

            bypass = json.loads(
                (out / "TWO_DAY_VALIDATION_BYPASS_RECEIPT.json").read_text()
            )
            self.assertEqual(
                bypass["only_methodological_exception"],
                "REPLACE_52_WEEK_OUT_OF_TIME_SPLIT_WITH_TWO_DAY_SELF_FIT_SELF_SCORE",
            )
            self.assertFalse(bypass["comparison_to_54w_answers_performed"])
            self.assertIn("SELF_FIT", bypass["artifact_namespace_difference"])
            self.assertEqual(
                bypass["diagnostic_adapter"]["sha256"],
                receipt["diagnostic_adapter"]["sha256"],
            )


if __name__ == "__main__":
    unittest.main()
