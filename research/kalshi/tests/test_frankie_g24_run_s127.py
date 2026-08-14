from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_g24_run_s127 as s127  # noqa: E402


def full_brain():
    plays = {f"p{i}": {"body": f"play {i}"} for i in range(90)}
    return {
        "plays": plays,
        "play_index": {},
        "_frankie_serving": {
            "canonical_plays_total": 90,
            "full_plays_served": 90,
        },
    }


class S127G24RunnerTests(unittest.TestCase):
    def test_launcher_has_no_model_or_reveal_phase(self):
        self.assertEqual(s127.GID, "g24")
        self.assertEqual(s127.PHASES, ("preflight", "export"))
        for forbidden in ("forecast", "score", "refine", "openai", "claude", "bedrock"):
            self.assertNotIn(forbidden, s127.PHASES)

    def test_g24_packet_corrects_only_operational_metadata(self):
        original = {
            "walked_validation_only": True,
            "realized_outcome_in_packet": False,
            "causal_slice": {"sentinel": 1},
            "brain_view_served": full_brain(),
        }
        with patch.object(s127.s126, "packet", return_value=("prompt", original)):
            prompt, packet = s127._g24_packet("BLD-1", "g24", "20260720", "B", "ns")
        self.assertEqual(prompt, "prompt")
        self.assertIsNot(packet, original)
        self.assertTrue(original["walked_validation_only"])
        self.assertFalse(packet["walked_validation_only"])
        self.assertEqual(packet["causal_slice"], original["causal_slice"])
        self.assertEqual(packet["brain_view_served"], original["brain_view_served"])
        self.assertFalse(packet["realized_outcome_in_packet"])
        self.assertIn("ChatGPT", packet["operator_transport"])

    def test_g24_packet_rejects_other_groups(self):
        with self.assertRaisesRegex(s127.S127Stop, "g24-only"):
            s127._g24_packet("BLD-1", "g18", "20260427", "B", "ns")

    @patch.object(s127.s126, "attach_specialist_access", side_effect=lambda payload, **_: payload)
    @patch.object(s127.s120, "assert_no_outcome_leak")
    @patch.object(s127.s120, "full_brain", side_effect=lambda view: view)
    @patch.object(s127.base, "_read_json")
    @patch.object(s127.base, "_slice_path")
    @patch.object(s127.base, "_build_role_view")
    @patch.object(s127.base, "_emit_prompt", return_value="bridge prompt")
    def test_bridge_uses_friday_brain_and_friday_causal_slice(
        self, emit, build_view, slice_path, read_json, full, leak, attach
    ):
        build_view.return_value = Path("brain-friday.json")
        slice_path.return_value = Path("slice-friday.json")
        read_json.side_effect = [full_brain(), {"20260724": {"state": "friday-only"}}]
        _, packet = s127._g24_bridge_packet("20260727", "20260724", "ns")
        build_view.assert_called_once_with("g24", "20260724", "ns")
        slice_path.assert_called_once_with("g24", "20260724")
        self.assertEqual(packet["decision_day"], "20260724")
        self.assertEqual(packet["day"], "20260727")
        self.assertEqual(packet["causal_slice"], {"20260724": {"state": "friday-only"}})
        leak.assert_called_once()

    @patch.object(s127, "install")
    @patch.object(s127, "verify_sanctioned_state")
    @patch.object(s127, "verify_original_spawn")
    @patch.object(s127.base, "preflight_group")
    def test_preflight_stays_structural_and_unrevealed(
        self, preflight_group, verify_spawn, verify_state, install
    ):
        verify_spawn.return_value = {"verified": True}
        verify_state.return_value = {"verdict": "SANCTIONED_G24_STATE"}
        preflight_group.return_value = {
            "group": "g24",
            "days": [
                {"day": day, "owner": "B", "packet_bytes": 1, "served_plays": 90}
                for day in s127.gc.GROUPS["g24"]["days"]
            ],
            "actuals_read": False,
            "verdict": "PACKETS_CAUSAL",
        }
        out = s127.preflight("ns")
        install.assert_called_once_with()
        preflight_group.assert_called_once_with("g24", "ns")
        self.assertFalse(out["model_backend_invoked"])
        self.assertFalse(out["actuals_read"])

    @patch.object(s127, "install")
    @patch.object(s127, "preflight")
    @patch.object(s127, "_g24_bridge_packet")
    @patch.object(s127, "_g24_packet")
    def test_export_is_lossless_packet_only(self, day_packet, bridge_packet, preflight, install):
        preflight.return_value = {"actuals_read": False}
        base_packet = {
            "realized_outcome_in_packet": False,
            "brain_view_served": full_brain(),
            "causal_slice": {"x": 1},
        }
        day_packet.return_value = ("prompt", base_packet)
        bridge_packet.return_value = ("bridge", base_packet)
        with tempfile.TemporaryDirectory() as td:
            out = s127.export_packets("ns", Path(td))
            self.assertEqual(out["packet_count"], 11)  # 10 days + one in-block Fri->Mon bridge
            self.assertFalse(out["model_api_invoked"])
            self.assertFalse(out["actuals_read"])
            manifest = json.loads((Path(td) / "manifest.json").read_text())
            self.assertEqual(manifest["packet_count"], 11)
            for row in manifest["packets"]:
                p = Path(td) / row["path"]
                decoded = json.loads(p.read_text())
                self.assertEqual(decoded, base_packet)
                self.assertEqual(row["invariants"]["full_play_bodies_served"], 90)


if __name__ == "__main__":
    unittest.main()
