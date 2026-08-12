import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_claude_code_temp as mod


def packet90():
    plays = {f"play-{i:02d}": {"id": f"play-{i:02d}", "body": f"body-{i:02d}"} for i in range(90)}
    return {
        "packet_version": "test",
        "realized_outcome_in_packet": False,
        "canonical_prompt": "test canonical prompt",
        "canonical_role_files": {"shared": "shared", "specialist": "specialist"},
        "causal_slice": {"sentinel_field": 123, "another_field": "kept"},
        "brain_view_served": {
            "plays": plays,
            "play_index": {"play-00": {"status": "ARMED"}},
            "_frankie_serving": {
                "canonical_plays_total": 90,
                "full_plays_served": 90,
            },
        },
    }


class ClaudeCodeTempTests(unittest.TestCase):
    def test_guard_explicitly_forbids_changing_frankie_view(self):
        text = mod.OPERATOR_GUARD
        self.assertIn("DO NOT change, prune, rank-gate, hide, truncate", text)
        self.assertIn("data surface or settings Frankie is allowed to see", text)
        self.assertIn("all supplied play bodies remain available", text.lower())
        self.assertIn("blind artifact is immutable", text)
        self.assertIn("A-82 isolation remains binding", text)

    def test_subscription_env_strips_api_and_cloud_provider_routing(self):
        with mock.patch.dict(
            mod.os.environ,
            {
                "ANTHROPIC_API_KEY": "api-key",
                "ANTHROPIC_AUTH_TOKEN": "auth-token",
                "ANTHROPIC_BASE_URL": "https://gateway.invalid",
                "CLAUDE_CODE_USE_BEDROCK": "1",
                "CLAUDE_CODE_USE_VERTEX": "1",
                "KEEP_ME": "yes",
            },
            clear=False,
        ):
            env = mod._subscription_env()
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)
        self.assertNotIn("ANTHROPIC_BASE_URL", env)
        self.assertNotIn("CLAUDE_CODE_USE_BEDROCK", env)
        self.assertNotIn("CLAUDE_CODE_USE_VERTEX", env)
        self.assertEqual(env["KEEP_ME"], "yes")

    def test_blind_invocation_is_tool_disabled_lossless_and_outside_repo(self):
        packet = packet90()
        before = json.loads(json.dumps(packet))
        model_result = {
            "specialist": "B",
            "group": "G24",
            "date": "20260720",
            "guessed_net_usd": 100,
        }
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = list(cmd)
            captured["input"] = kwargs["input"]
            captured["cwd"] = pathlib.Path(kwargs["cwd"])
            captured["env"] = dict(kwargs["env"])
            self.assertTrue(captured["cwd"].is_dir())
            self.assertNotEqual(captured["cwd"].resolve(), HERE.resolve())
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps(
                    {
                        "type": "result",
                        "subtype": "success",
                        "is_error": False,
                        "result": json.dumps(model_result),
                        "session_id": "test",
                    }
                ),
                stderr="",
            )

        with mock.patch.object(mod.subprocess, "run", side_effect=fake_run):
            got = mod.claude_generate(packet, phase="blind")

        self.assertEqual(got, model_result)
        self.assertEqual(packet, before)
        decoded = json.loads(captured["input"])
        self.assertEqual(decoded, packet)
        self.assertEqual(len(decoded["brain_view_served"]["plays"]), 90)
        self.assertEqual(decoded["causal_slice"]["sentinel_field"], 123)

        cmd = captured["cmd"]
        self.assertIn("-p", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("--max-turns", cmd)
        self.assertIn("--disallowedTools", cmd)
        self.assertIn("--system-prompt", cmd)
        self.assertEqual(cmd[cmd.index("--max-turns") + 1], "1")
        disallowed = cmd[cmd.index("--disallowedTools") + 1]
        for tool in ("Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch"):
            self.assertIn(tool, disallowed)
        system_prompt = cmd[cmd.index("--system-prompt") + 1]
        self.assertIn("CURRENT PHASE: BLIND", system_prompt)
        self.assertIn("DO NOT change, prune, rank-gate", system_prompt)
        self.assertNotIn("ANTHROPIC_API_KEY", captured["env"])
        self.assertNotIn("CLAUDE_CODE_USE_BEDROCK", captured["env"])

    def test_reduced_brain_is_refused_before_claude(self):
        packet = packet90()
        packet["brain_view_served"]["plays"].pop("play-89")
        with self.assertRaises(mod.ClaudeOperatorStop):
            mod.claude_generate(packet, phase="blind")

    def test_refine_packet_must_be_separate_phase_and_keeps_full_brain(self):
        packet = packet90()
        packet["realized_outcome_in_packet"] = True
        packet["blind_forecast_immutable"] = {"guessed_net_usd": 100}
        packet["realized_outcome_revealed_after_blind"] = {"day_move_usd": 80}
        model_result = {"posterior": "diagnosis", "execution_enabled": False}

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps(
                    {
                        "type": "result",
                        "subtype": "success",
                        "is_error": False,
                        "result": json.dumps(model_result),
                    }
                ),
                stderr="",
            )

        with mock.patch.object(mod.subprocess, "run", side_effect=fake_run):
            got = mod.claude_generate(packet, phase="refine")
        self.assertEqual(got, model_result)
        self.assertEqual(len(packet["brain_view_served"]["plays"]), 90)

    def test_blind_phase_rejects_realized_outcome(self):
        packet = packet90()
        packet["realized_outcome_in_packet"] = True
        with self.assertRaises(mod.ClaudeOperatorStop):
            mod.claude_generate(packet, phase="blind")


if __name__ == "__main__":
    unittest.main()
