from __future__ import annotations

import gzip
import json
from pathlib import Path
import unittest

from research.kalshi.frankie_causal_operational_context_20260824 import (
    ACCEPTED_MINIMUM_BLOCKS,
    ACCEPTED_MINIMUM_PATHS,
    CausalDecisionStateSnapshotAdapter,
    DecisionFieldStatus,
    OperationalContextError,
    RegistryCoverageOracle,
    build_canonical_s135_snapshot,
    flatten_decision_state,
    load_hourly_weather_observations,
)


class CausalDecisionStateSnapshotTest(unittest.TestCase):
    @staticmethod
    def _paths() -> tuple[str, ...]:
        return tuple(
            f"block_{block:02d}.field_{field:02d}"
            for block in range(44)
            for field in range(44)
        )

    def test_hourly_weather_advances_by_prefix_without_later_hours_or_daily_realized_proxy(self) -> None:
        import tempfile
        from datetime import datetime, timezone

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = root / "data/nws_hourly"
            store.mkdir(parents=True)
            rows = (
                {"station": "ORD", "valid": "2021-10-01 08:00", "received_at": "2021-10-01T08:10:00Z", "tmpf": "51.0"},
                {"station": "ORD", "valid": "2021-10-01 10:00", "received_at": "2021-10-01T10:10:00Z", "tmpf": "54.0"},
            )
            with gzip.open(store / "ORD_202110.jsonl.gz", "wt", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row) + "\n")
            nine = datetime(2021, 10, 1, 9, tzinfo=timezone.utc).timestamp()
            eleven = datetime(2021, 10, 1, 11, tzinfo=timezone.utc).timestamp()
            early = load_hourly_weather_observations(root, decision_day="20211001", evaluated_at=nine)
            late = load_hourly_weather_observations(root, decision_day="20211001", evaluated_at=eleven)
            self.assertEqual(early.observation_count, 1)
            self.assertEqual(late.observation_count, 2)
            self.assertFalse(any("10_00" in path for path in flatten_decision_state(early.state)))

            paths = self._paths() + ("weather.gw_hdd", "weather_forecast.gw_hdd")
            oracle = RegistryCoverageOracle.create(
                paths=paths, source_ids=("registry",), source_hashes=("a" * 64,)
            )
            canonical = {
                "weather": {"gw_hdd": 99.0},
                "weather_forecast": {"known_by": nine - 60.0, "gw_hdd": 12.0},
                **early.state,
            }
            snapshot = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
                run_id="weather", decision_day="20211001", evaluated_at=nine,
                canonical_state=canonical, canonical_source_id="S135",
                canonical_source_sha256="b" * 64, field_sources=early.field_sources,
            )
            by_path = {field.path: field for field in snapshot.fields}
            self.assertEqual(by_path["weather_forecast.gw_hdd"].status.value, "PRESENT")
            self.assertEqual(by_path["weather.gw_hdd"].status.value, "UNAVAILABLE")
            hourly = [field for field in snapshot.fields if field.block == "weather_observation_hourly"]
            self.assertTrue(hourly)
            self.assertTrue(all(field.known_by <= nine for field in hourly))
            self.assertTrue(any(field.value == "51.0" for field in hourly))
            self.assertFalse(any(field.value == "54.0" for field in hourly))
            self.assertTrue(all("nws_hourly" in field.source_id for field in hourly))

    def test_recursive_snapshot_retains_every_registry_path_and_explicit_null(self) -> None:
        paths = self._paths()
        self.assertGreaterEqual(len(paths), ACCEPTED_MINIMUM_PATHS)
        oracle = RegistryCoverageOracle.create(
            paths=paths,
            source_ids=("canonical-registry-fixture",),
            source_hashes=("1" * 64,),
            block_sources={"block_00": ("weather observation vintage", "hourly as-of")},
        )
        adapter = CausalDecisionStateSnapshotAdapter(oracle)
        state = {
            "block_00": {"field_00": 7.0, "field_01": None},
            "block_43": {"field_43": "retained"},
        }
        snapshot = adapter.snapshot(
            run_id="run-1",
            decision_day="20211001",
            evaluated_at=1633046401.0,
            canonical_state=state,
            canonical_source_id="S135_CURRENT_RUNTIME",
            canonical_source_sha256="2" * 64,
        )

        self.assertEqual(snapshot.path_count, len(paths))
        self.assertEqual(snapshot.schema_registered_count, len(paths))
        self.assertEqual(snapshot.emitted_leaf_count, 3)
        self.assertEqual(snapshot.emitted_registered_count, 3)
        self.assertEqual(snapshot.emitted_additive_count, 0)
        self.assertEqual(
            snapshot.present_count + snapshot.explicit_null_count + snapshot.unavailable_count,
            snapshot.schema_registered_count,
        )
        self.assertEqual(snapshot.source_snapshot_leaf_count, 3)
        self.assertEqual(len(snapshot.source_snapshot_leaf_hash), 64)
        self.assertGreaterEqual(snapshot.block_count, ACCEPTED_MINIMUM_BLOCKS)
        by_path = {field.path: field for field in snapshot.fields}
        self.assertEqual(by_path["block_00.field_00"].value, 7.0)
        self.assertEqual(by_path["block_00.field_00"].status, DecisionFieldStatus.PRESENT)
        self.assertIsNone(by_path["block_00.field_01"].value)
        self.assertEqual(by_path["block_00.field_01"].status, DecisionFieldStatus.EXPLICIT_NULL)
        self.assertEqual(by_path["block_01.field_00"].status, DecisionFieldStatus.UNAVAILABLE)
        self.assertEqual(snapshot.emitted_coverage_fraction, 3 / len(paths))
        self.assertEqual(snapshot.value_coverage_fraction, 2 / len(paths))
        payload = snapshot.provider_payload()
        self.assertEqual(payload["snapshot_hash"], snapshot.snapshot_hash)
        self.assertEqual(len(payload["fields"]), len(paths))
        self.assertEqual(
            snapshot.family_manifest["block_00"]["upstream_source"],
            "weather observation vintage",
        )
        self.assertEqual(snapshot.family_manifest["block_00"]["cadence"], "hourly as-of")

    def test_extra_canonical_paths_are_additive_and_no_registry_path_can_drop(self) -> None:
        paths = self._paths()
        oracle = RegistryCoverageOracle.create(
            paths=paths,
            source_ids=("registry",),
            source_hashes=("3" * 64,),
        )
        snapshot = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
            run_id="run-2",
            decision_day="20211002",
            evaluated_at=1633132801.0,
            canonical_state={"new_block": {"new_field": 1}},
            canonical_source_id="S135_CURRENT_RUNTIME",
            canonical_source_sha256="4" * 64,
        )
        self.assertIn("new_block.new_field", {field.path for field in snapshot.fields})
        self.assertEqual(snapshot.path_count, len(paths) + 1)

        with self.assertRaisesRegex(OperationalContextError, "1,914"):
            RegistryCoverageOracle.create(
                paths=("only.one",),
                source_ids=("stale",),
                source_hashes=("5" * 64,),
            )

    def test_flattening_matches_registry_list_convention_and_rejects_nonfinite_values(self) -> None:
        flattened = flatten_decision_state(
            {"family": {"rows": [{"x": 1}, {"x": 2}, {"x": 3}, {"x": 4}, {"x": 5}]}}
        )
        self.assertEqual(
            set(flattened),
            {"family.rows[0].x", "family.rows[1].x", "family.rows[2].x", "family.rows[3].x"},
        )
        with self.assertRaisesRegex(OperationalContextError, "non-finite"):
            flatten_decision_state({"family": {"bad": float("nan")}})

    def test_repo_oracle_uses_live_survey_not_stale_generated_store(self) -> None:
        repo = Path(__file__).resolve().parents[3]
        oracle = RegistryCoverageOracle.from_repo(repo)
        stale = json.loads((repo / "research/kalshi/store/data_points.json").read_text())
        self.assertGreaterEqual(oracle.path_count, ACCEPTED_MINIMUM_PATHS)
        self.assertGreaterEqual(oracle.block_count, ACCEPTED_MINIMUM_BLOCKS)
        self.assertGreater(oracle.path_count, int(stale["n_served"]))
        self.assertIn("upstream_source", oracle.block_sources["weather"])

    def test_missing_s135_substrate_is_explicit_not_synthesized_or_fatal(self) -> None:
        repo = Path(__file__).resolve().parents[3]
        snapshot = build_canonical_s135_snapshot(
            repo_root=repo,
            run_id="missing-substrate",
            decision_day="20211001",
            evaluated_at=1633046401.0,
            group="3",
        )
        self.assertEqual(snapshot.build_status, "EXPLICIT_MISSING_CANONICAL_SUBSTRATE")
        self.assertEqual(snapshot.path_count, snapshot.registry_path_count)
        self.assertTrue(snapshot.build_error_hash)
        self.assertTrue(all(field.status is DecisionFieldStatus.UNAVAILABLE for field in snapshot.fields))

    def test_live_registry_parity_keeps_real_present_null_and_missing_states_readable(self) -> None:
        repo = Path(__file__).resolve().parents[3]
        oracle = RegistryCoverageOracle.from_repo(repo)
        snapshot = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
            run_id="live-registry-fixture",
            decision_day="20211001",
            evaluated_at=1633046401.0,
            canonical_state={
                "cash_basis": {"vintage_asof": "20210929", "age_days": 2, "basis_chg_1d": None},
                "new_lawful_family": {
                    "known_by": 1633046400.0,
                    "fixture_additive_path": "retained",
                },
            },
            canonical_source_id="deterministic-canonical-adapter-fixture-no-real-dbn",
            canonical_source_sha256="9" * 64,
        )
        self.assertEqual(snapshot.path_count, oracle.path_count + 2)
        self.assertEqual(snapshot.registry_path_count, oracle.path_count)
        self.assertEqual(snapshot.block_count, oracle.block_count + 1)
        self.assertGreaterEqual(oracle.path_count, 1_914)
        self.assertGreaterEqual(oracle.block_count, 44)
        fields = {field.path: field for field in snapshot.fields}
        self.assertEqual(fields["cash_basis.age_days"].status, DecisionFieldStatus.PRESENT)
        self.assertEqual(fields["cash_basis.basis_chg_1d"].status, DecisionFieldStatus.EXPLICIT_NULL)
        self.assertEqual(fields["cash_basis.basis_chg_3d"].status, DecisionFieldStatus.UNAVAILABLE)
        self.assertEqual(fields["new_lawful_family.fixture_additive_path"].value, "retained")

    def test_same_day_realized_weather_is_quarantined_but_forecast_vintages_remain(self) -> None:
        paths = self._paths() + (
            "weather.gw_hdd",
            "weather.realized_as_proxy_for_forecastable_regime",
            "weather_forecast.gw_hdd",
            "weather_forecast_cycle.cycle",
        )
        oracle = RegistryCoverageOracle.create(
            paths=paths,
            source_ids=("registry",),
            source_hashes=("a" * 64,),
        )
        snapshot = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
            run_id="weather-quarantine",
            decision_day="20211001",
            evaluated_at=1633046401.0,
            canonical_state={
                "weather": {
                    "gw_hdd": 9.5,
                    "realized_as_proxy_for_forecastable_regime": True,
                },
                "weather_forecast": {"asof_utc": "2021-09-30T23:59:00Z", "gw_hdd": 12.0},
                "weather_forecast_cycle": {
                    "asof_utc": "2021-09-30T21:59:00Z", "cycle": "20210930T12Z"
                },
            },
            canonical_source_id="S135",
            canonical_source_sha256="b" * 64,
        )
        fields = {field.path: field for field in snapshot.fields}
        self.assertEqual(fields["weather.gw_hdd"].status, DecisionFieldStatus.UNAVAILABLE)
        self.assertEqual(
            fields["weather.gw_hdd"].missing_reason,
            "UNAVAILABLE_CAUSAL_QUARANTINE_SAME_DAY_REALIZED_WEATHER",
        )
        self.assertEqual(fields["weather_forecast.gw_hdd"].status, DecisionFieldStatus.PRESENT)
        self.assertEqual(fields["weather_forecast_cycle.cycle"].status, DecisionFieldStatus.PRESENT)
        payload = snapshot.provider_payload()
        weather = next(row for row in payload["fields"] if row["path"] == "weather.gw_hdd")
        self.assertIsNone(weather["value"])

    def test_explicit_block_availability_is_derived_and_future_metadata_is_quarantined(self) -> None:
        paths = self._paths() + (
            "weather_forecast.known_by", "weather_forecast.gw_hdd",
            "storage.available_at", "storage.vs_5yr",
        )
        oracle = RegistryCoverageOracle.create(
            paths=paths, source_ids=("registry",), source_hashes=("c" * 64,)
        )
        snapshot = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
            run_id="availability", decision_day="20211001", evaluated_at=100.0,
            canonical_state={
                "weather_forecast": {"known_by": 90.0, "gw_hdd": 11.0},
                "storage": {"available_at": 101.0, "vs_5yr": 20.0},
            },
            canonical_source_id="S135", canonical_source_sha256="d" * 64,
        )
        fields = {field.path: field for field in snapshot.fields}
        forecast = fields["weather_forecast.gw_hdd"]
        self.assertEqual(forecast.known_by, 90.0)
        self.assertEqual(forecast.available_at, 90.0)
        self.assertTrue(forecast.clock_basis.startswith("EXPLICIT_METADATA:"))
        storage = fields["storage.vs_5yr"]
        self.assertEqual(storage.status, DecisionFieldStatus.UNAVAILABLE)
        self.assertEqual(storage.missing_reason, "UNAVAILABLE_CAUSAL_QUARANTINE_FUTURE_AVAILABILITY")

    def test_source_cadence_matrix_enforces_report_period_static_and_unverified_classes(self) -> None:
        from datetime import datetime, timezone

        cutoff = datetime(2021, 10, 5, tzinfo=timezone.utc).timestamp()
        real_paths = (
            "storage.as_of", "storage.level", "grid_stack.period", "grid_stack.gas_mwh",
            "nuclear_outages.period", "nuclear_outages.capacity_out_mw",
            "cot.publication_ts", "cot.open_interest", "steo_vintage.knowable_from",
            "steo_vintage.value", "flow_calendar.is_eia_print_day", "solar.date",
            "solar.gw_day_length_h", "built_utc",
            "stor_surprise", "storage_consensus.next_print.print_datetime_utc",
            "storage_consensus.next_print.consensus_chg_bcf",
        )
        oracle = RegistryCoverageOracle.create(
            paths=self._paths() + real_paths,
            source_ids=("registry",), source_hashes=("d" * 64,),
        )
        snapshot = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
            run_id="cadence", decision_day="20211005", evaluated_at=cutoff,
            canonical_state={
                "storage": {
                    "as_of": "2021-10-01", "available_at": "2021-10-01T14:30:00Z",
                    "level": 3200,
                },
                "grid_stack": {"period": "2021-10-01", "gas_mwh": 7},
                "nuclear_outages": {"period": "2021-10-04", "capacity_out_mw": 10},
                "cot": {"publication_ts": "2021-10-04T15:30:00Z", "open_interest": 8},
                "steo_vintage": {"knowable_from": "2021-10-04", "value": 6},
                "flow_calendar": {"is_eia_print_day": False},
                "solar": {"date": "2021-10-05", "gw_day_length_h": 12.0},
                "built_utc": "2026-08-24T00:00:00Z",
                "stor_surprise": 3,
                "storage_consensus": {"next_print": {
                    "print_datetime_utc": "2021-10-07T14:30:00Z",
                    "consensus_chg_bcf": 4,
                }},
            },
            canonical_source_id="S135", canonical_source_sha256="e" * 64,
        )
        fields = {field.path: field for field in snapshot.fields}
        for path in (
            "storage.level", "grid_stack.gas_mwh",
            "cot.open_interest", "steo_vintage.value", "flow_calendar.is_eia_print_day",
        ):
            self.assertEqual(fields[path].status, DecisionFieldStatus.PRESENT, path)
        for path in (
            "built_utc", "stor_surprise", "nuclear_outages.capacity_out_mw",
            "solar.gw_day_length_h",
            "storage_consensus.next_print.consensus_chg_bcf",
        ):
            self.assertEqual(fields[path].status, DecisionFieldStatus.UNAVAILABLE, path)
        self.assertEqual(snapshot.availability_matrix["block_count"], snapshot.block_count)
        self.assertEqual(len(snapshot.availability_matrix["matrix_hash"]), 64)

        later = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
            run_id="cadence", decision_day="20211006",
            evaluated_at=datetime(2021, 10, 6, tzinfo=timezone.utc).timestamp(),
            canonical_state={
                "nuclear_outages": {"period": "2021-10-04", "capacity_out_mw": 10},
            },
            canonical_source_id="S135", canonical_source_sha256="e" * 64,
        )
        later_fields = {field.path: field for field in later.fields}
        self.assertEqual(
            later_fields["nuclear_outages.capacity_out_mw"].status,
            DecisionFieldStatus.PRESENT,
        )

    def test_storage_without_exact_release_clock_stays_quarantined_after_report_date(self) -> None:
        from datetime import datetime, timezone

        oracle = RegistryCoverageOracle.create(
            paths=self._paths() + ("storage.as_of", "storage.level"),
            source_ids=("registry",), source_hashes=("f" * 64,),
        )
        snapshot = CausalDecisionStateSnapshotAdapter(oracle).snapshot(
            run_id="storage-no-clock", decision_day="20211005",
            evaluated_at=datetime(2021, 10, 5, 12, tzinfo=timezone.utc).timestamp(),
            canonical_state={"storage": {"as_of": "2021-10-01", "level": 3200}},
            canonical_source_id="S135", canonical_source_sha256="1" * 64,
        )
        field = {item.path: item for item in snapshot.fields}["storage.level"]
        self.assertEqual(field.status, DecisionFieldStatus.UNAVAILABLE)
        self.assertEqual(
            field.missing_reason,
            "UNAVAILABLE_CAUSAL_QUARANTINE_UNVERIFIED_AVAILABILITY",
        )


if __name__ == "__main__":
    unittest.main()
