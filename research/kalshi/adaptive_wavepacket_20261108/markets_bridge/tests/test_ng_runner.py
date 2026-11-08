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
            self.assertEqual(summary["net_of_fee_computed"], False)
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


if __name__ == "__main__":
    unittest.main()
