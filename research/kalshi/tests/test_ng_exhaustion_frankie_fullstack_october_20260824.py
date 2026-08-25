from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from research.kalshi import ng_exhaustion_frankie_fullstack_october_20260824 as fullstack


MANIFEST = Path(
    "research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json"
)


class FullStackOctoberContractTest(unittest.TestCase):
    def test_selects_exact_predecessor_and_all_october_objects(self) -> None:
        manifest = json.loads(MANIFEST.read_text())

        roster = fullstack.select_october_source_roster(manifest)

        self.assertEqual(len(roster), 27)
        self.assertTrue(roster[0].key.endswith("glbx-mdp3-20210930.mbo.dbn.zst"))
        self.assertEqual(roster[0].purpose, "PREDECESSOR_BOOTSTRAP")
        self.assertEqual({item.segment for item in roster[1:]}, {"20211001_20211101"})
        self.assertEqual(len({item.key for item in roster}), len(roster))
        self.assertTrue(all(item.purpose == "OCTOBER_CAUSAL_STREAM" for item in roster[1:]))

    def test_config_is_full_month_sol_only_and_requires_fresh_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "out"
            config = fullstack.FullStackOctoberConfig(
                run_id="october-fullstack-test",
                manifest_path=MANIFEST,
                source_root=Path(temporary),
                output_root=root,
            ).validate()

            self.assertEqual(config.model, "gpt-5.6-sol")
            self.assertEqual(
                config.target_start,
                int(datetime(2021, 10, 1, tzinfo=timezone.utc).timestamp()),
            )
            self.assertEqual(
                config.target_end,
                int(datetime(2021, 11, 1, tzinfo=timezone.utc).timestamp()),
            )
            self.assertEqual(config.answer_wall_mode, "SEALED_UNTIL_PRIMARY_FREEZE")

            root.mkdir()
            (root / "existing").write_text("immutable")
            with self.assertRaises(fullstack.FullStackOctoberError):
                config.validate()

    def test_rejects_manifest_identity_drift(self) -> None:
        manifest = json.loads(MANIFEST.read_text())
        manifest["manifest_sha256"] = "0" * 64

        with self.assertRaises(fullstack.FullStackOctoberError):
            fullstack.select_october_source_roster(manifest)


if __name__ == "__main__":
    unittest.main()
