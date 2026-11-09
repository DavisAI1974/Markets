"""NG runner: runs end to end on a REAL cached NG day, otherwise skips (zero synthetic trading data).

Cache a day first (when S3 access is available) with the repo's own loader:
    PYTHONPATH=research/kalshi python3 -c "import event_move_baseline as e; e._s3_fetch_cont_gz('NG','20260617')"
then:
    NG_PROBE_DAY=20260617 PYTHONPATH=.:research/kalshi:research/kalshi/adaptive_wavepacket_20261108/working_tree \
      python3 -m unittest research.kalshi.adaptive_wavepacket_20261108.markets_bridge.tests.test_ng_runner
"""
import glob
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
CACHE = ROOT / "data" / "nymex_cont"


def _cached_day():
    day = os.environ.get("NG_PROBE_DAY")
    if day and (CACHE / f"NG_{day}.jsonl.gz").exists() or day and (CACHE / f"NG_{day}.jsonl").exists():
        return day
    found = sorted(glob.glob(str(CACHE / "NG_*.jsonl*")))
    return Path(found[-1]).name[3:11] if found else None


class NgRunnerCliTests(unittest.TestCase):
    def test_cli_help_and_defaults(self):
        from research.kalshi.adaptive_wavepacket_20261108.markets_bridge import ng_runner
        self.assertEqual(ng_runner.NG_SETTLE_UTC, (21, 0))
        self.assertEqual(ng_runner.NG_SETTLE_GUARD_S, 1800)
        with self.assertRaises(SystemExit) as stop:
            ng_runner.main(["--help"])
        self.assertEqual(stop.exception.code, 0)
        # Settle exclusion window arithmetic (UTC): 21:00 +/- 1800 s.
        self.assertTrue(ng_runner.in_window(21 * 3600 + 10 * 60, (21, 0), 1800))
        self.assertFalse(ng_runner.in_window(20 * 3600, (21, 0), 1800))


@unittest.skipUnless(_cached_day(), "no cached NG day under data/nymex_cont (AWS not accessible)")
class NgRunnerRealDayTests(unittest.TestCase):
    def test_real_day_runs_end_to_end_and_registries_verify(self):
        from research.kalshi.adaptive_wavepacket_20261108.markets_bridge import ng_runner
        day = _cached_day()
        grid, channels, provenance = ng_runner.load_ng_day(day, "local")
        self.assertIn("ng_buy", channels)
        self.assertIn("ng_sell", channels)
        self.assertEqual(len(grid), len(channels["ng_buy"]))
        # Bounded slice: 2 hours of seconds -> ~360 frames at window 60 / stride 20.
        lo = 0
        hi = min(len(grid), 7200)
        grid = grid[lo:hi]
        channels = {k: v[lo:hi] for k, v in channels.items()}
        with tempfile.TemporaryDirectory() as folder:
            summary = ng_runner.run_probe(grid, channels, source_identity=f"NG_{day}",
                                          provenance=provenance, out_dir=folder, shift_null=10)
            self.assertEqual(summary["no_trade_signal_computed"], True)
            self.assertEqual(summary["trade_cost_in_any_calculation"], False)
            self.assertEqual(summary["frames_dropped"], 0)
            self.assertEqual(set(summary["estimators"]), {"frozen-bin", "vasicek-ksg"})
            for name, block in summary["estimators"].items():
                self.assertTrue(block["registry_verified"], name)
                self.assertTrue(block["five_step"]["report_present"], name)
                self.assertEqual(len(block["five_step"]["directions"]), 2)
                for d in block["five_step"]["directions"]:
                    self.assertIn(d["status"], ("CANDIDATE_ASSOCIATION_REVIEW_ONLY",
                                                "NO_SUPPORTED_ASSOCIATION",
                                                "ABSTAIN_UNIDENTIFIABLE_DIPOLE_RATIO",
                                                "ABSTAIN_RANK_OR_NUMERIC_ARTIFACT",
                                                "ABSTAIN_SELF_MODEL_ALREADY_EXPLAINS_HOLDOUT",
                                                "ABSTAIN_INSUFFICIENT_CHRONOLOGICAL_SUPPORT"))
                self.assertEqual(len(block["geometry"]), 2)
            self.assertTrue((Path(folder) / "summary.json").exists())
            print(ng_runner.one_screen(summary))


class ReplicationTableTests(unittest.TestCase):
    """The table reads engine OUTPUT schemas (status strings); it contains no market data."""

    @staticmethod
    def _summary(day, status, frac, b, se, pred):
        d = {"target": "ng_buy", "donor": "ng_sell", "status": status, "improvement": 0.3,
             "dipole_balance": b, "balance_standard_error": se, "reason": ""}
        block = {"five_step": {"directions": [d]},
                 "circular_shift_null": [{"target": "ng_buy", "donor": "ng_sell",
                                          "fraction_of_shifts_at_or_above_actual": frac}],
                 "geometry": [{"target": "ng_buy", "donor": "ng_sell", "predictive": {"status": pred}}]}
        return {"source_identity": day, "estimators": {"frozen-bin": block, "vasicek-ksg": block}}

    def test_days_are_counted_not_pooled(self):
        from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.ng_runner import replication_table
        good = self._summary("NG_1", "CANDIDATE_ASSOCIATION_REVIEW_ONLY", 0.0, 2.0, 0.5,
                             "CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY")
        weak_b = self._summary("NG_2", "CANDIDATE_ASSOCIATION_REVIEW_ONLY", 0.0, 1.0, 0.9,
                               "CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY")
        no = self._summary("NG_3", "NO_SUPPORTED_ASSOCIATION", 0.4, None, None,
                           "NO_STABLE_ADDITIONAL_GEOMETRIC_PREDICTION")
        table = replication_table([good, weak_b, no])
        row = table["directions"]["ng_buy<-ng_sell"]
        self.assertEqual(row["days_run"], 3)
        self.assertEqual(row["days_meeting_criteria"], 1)
        self.assertEqual(row["meets_criteria_by_day"], {"NG_1": True, "NG_2": False, "NG_3": False})
        self.assertFalse(table["pooled"])
        self.assertEqual(table["criteria"]["days_required_for_replication"], 3)
        self.assertEqual(row["days"]["NG_3"]["frozen-bin"]["b_over_se"], None)

    def test_single_estimator_day_cannot_meet_criteria(self):
        from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.ng_runner import replication_table
        one = self._summary("NG_1", "CANDIDATE_ASSOCIATION_REVIEW_ONLY", 0.0, 2.0, 0.5,
                            "CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY")
        del one["estimators"]["vasicek-ksg"]
        self.assertEqual(replication_table([one])["directions"]["ng_buy<-ng_sell"]["days_meeting_criteria"], 0)


if __name__ == "__main__":
    unittest.main()
