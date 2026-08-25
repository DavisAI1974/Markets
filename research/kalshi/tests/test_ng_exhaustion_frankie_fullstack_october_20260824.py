from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

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

    def test_staged_roster_is_byte_and_sha_verified_without_key_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payloads = {"predecessor.dbn.zst": b"predecessor", "target.dbn.zst": b"target"}
            roster = []
            for name, data in payloads.items():
                (root / name).write_bytes(data)
                roster.append(
                    fullstack.SourceObject(
                        date="20210930" if name.startswith("pre") else "20211001",
                        segment="segment",
                        key=f"canonical/path/{name}",
                        sha256=hashlib.sha256(data).hexdigest(),
                        bytes=len(data),
                        bucket="bucket",
                        purpose="PREDECESSOR_BOOTSTRAP" if name.startswith("pre") else "OCTOBER_CAUSAL_STREAM",
                    )
                )

            verified = fullstack.verify_staged_source_roster(tuple(roster), root)
            self.assertEqual(verified, (root / "predecessor.dbn.zst", root / "target.dbn.zst"))

            (root / "target.dbn.zst").write_bytes(b"drift")
            with self.assertRaises(fullstack.FullStackOctoberError):
                fullstack.verify_staged_source_roster(tuple(roster), root)

    def test_launch_event_sink_emits_workflow_gate_names_for_both_lanes(self) -> None:
        sink = fullstack.LaunchJsonEventSink()
        stream = io.StringIO()
        with redirect_stdout(stream):
            sink.emit_launch(
                "PAIRED_PREFIX_ACCEPTED",
                control_provider_response_ids=[f"ctrl-{index}" for index in range(5)],
                combined_provider_response_ids=[f"combined-{index}" for index in range(5)],
                identical_prefix_proof_hash="a" * 64,
            )
        row = json.loads(stream.getvalue())
        self.assertEqual(row["event"], "PAIRED_PREFIX_ACCEPTED")
        self.assertEqual(len(row["control_provider_response_ids"]), 5)
        self.assertEqual(len(row["combined_provider_response_ids"]), 5)
        self.assertEqual(len(set(row["control_provider_response_ids"] + row["combined_provider_response_ids"])), 10)


if __name__ == "__main__":
    unittest.main()
