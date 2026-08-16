import copy
import importlib.util
import sys
import types
import unittest

HERE = __import__("pathlib").Path(__file__).resolve()
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research" / "kalshi"))

import frankie_s135_group_runner as runner


class FakeConfig:
    GROUPS = {
        "gx": {
            "days": ["20260109", "20260112"],
            "anchor_date": "20260108",
            "mask_after": "20260108",
        }
    }

    @staticmethod
    def owner_map(gid):
        return {"20260109": "E", "20260112": "B"}

    @staticmethod
    def leg_for(gid, day):
        return "ng_mbo_ngx26"


class FakeRuntime:
    class base:
        @staticmethod
        def _validate_day(output, gid, day, owner):
            if "curve" not in output:
                raise ValueError("missing curve")

    @staticmethod
    def install():
        return None

    @staticmethod
    def validate_owner_output(output, owner, task="day_forecast"):
        if task == "day_forecast" and output.get("owner") != owner:
            raise ValueError("wrong owner")
        if task == "weekend_bridge" and any(k in output for k in ("curve_nodes", "path_p50_curve")):
            raise ValueError("A may not own Monday")

    class s133:
        class s120:
            @staticmethod
            def assert_no_outcome_leak(text, gid, day):
                if "target_outcome" in text:
                    raise ValueError("outcome leak")

    @staticmethod
    def packet(template, gid, day, spec, namespace):
        return "prompt", {"template": template, "group": gid, "day": day, "specialist": spec}

    @staticmethod
    def packet_sequential(template, gid, day, spec, namespace, *, prior_session, provenance):
        if prior_session["date"] >= day:
            raise ValueError("future leak")
        return "prompt", {
            "template": template,
            "group": gid,
            "day": day,
            "specialist": spec,
            "completed_prior_session_context": {"session": dict(prior_session)},
        }


class S135RunnerTests(unittest.TestCase):
    def setUp(self):
        self.spec = runner.GroupRunSpec.from_group("GX", "blind", config_module=FakeConfig)
        self.gate = {
            "run_gate": "PASS",
            "mandatory_checks": {f"check_{i:02d}": True for i in range(1, 22)},
            "group_run_spec": self.spec.as_dict(),
            "state_check": {"state_health": "PASS"},
        }

    def forecast(self, owner, value=1):
        return {
            "owner": owner,
            "disposition": "ABSTAIN",
            "curve": [
                {"event": "open", "p25": value - 1, "p50": value, "p75": value + 1},
                {"event": "turn", "p25": value, "p50": value + 2, "p75": value + 3},
            ],
        }

    def test_group_spec_is_derived_from_existing_config(self):
        self.assertEqual(self.spec.group, "gx")
        self.assertEqual([(d.day, d.owner, d.leg) for d in self.spec.days], [
            ("20260109", "E", "ng_mbo_ngx26"),
            ("20260112", "B", "ng_mbo_ngx26"),
        ])
        self.assertEqual(self.spec.anchor_date, "20260108")

    def test_reveal_before_freeze_fails_closed(self):
        ledger = runner.SequentialReplayLedger(self.spec)
        with self.assertRaises(runner.RunContractError):
            ledger.reveal("20260109", {"date": "20260109"})

    def test_freeze_is_immutable_and_abstain_curve_is_not_flattened(self):
        ledger = runner.SequentialReplayLedger(self.spec)
        out = self.forecast("E", 10)
        expected_curve = copy.deepcopy(out["curve"])
        frozen = ledger.freeze("20260109", out)
        out["curve"][0]["p50"] = 999
        thawed = frozen.thaw_verified()
        self.assertEqual(thawed["curve"], expected_curve)
        self.assertNotEqual(thawed["curve"][0]["p50"], thawed["curve"][1]["p50"])

    def test_out_of_order_freeze_and_future_prior_context_fail(self):
        ledger = runner.SequentialReplayLedger(self.spec)
        with self.assertRaises(runner.RunContractError):
            ledger.freeze("20260112", self.forecast("B"))
        with self.assertRaises(runner.RunContractError):
            runner.SequentialReplayLedger(self.spec, initial_prior_session={"date": "20260109"})

    def test_completed_state_is_carry_only_after_freeze_then_reveal(self):
        ledger = runner.SequentialReplayLedger(self.spec)
        ledger.freeze("20260109", self.forecast("E"))
        with self.assertRaises(runner.RunContractError):
            ledger.carry_for("20260109")
        ledger.reveal("20260109", {"date": "20260109", "turn_kind": "turn_up"})
        ledger.advance("20260109")
        carry = ledger.carry_for("20260112")
        self.assertEqual(carry["date"], "20260109")
        self.assertEqual(carry["turn_kind"], "turn_up")

    def test_scoring_uses_verified_frozen_forecast_only(self):
        ledger = runner.SequentialReplayLedger(self.spec)
        live = self.forecast("E", 4)
        ledger.freeze("20260109", live)
        live["curve"][0]["p50"] = 999
        with self.assertRaises(runner.RunContractError):
            ledger.score_frozen("20260109", lambda *args: None)
        ledger.reveal("20260109", {"date": "20260109", "close": 3.1})
        seen = {}
        def score(plan, frozen, actual):
            seen["p50"] = frozen["curve"][0]["p50"]
            seen["date"] = actual["date"]
            return {"ok": True}
        self.assertEqual(ledger.score_frozen("20260109", score), {"ok": True})
        self.assertEqual(seen, {"p50": 4, "date": "20260109"})

    def test_weekend_bridge_rejects_target_outcome_and_does_not_own_monday(self):
        ledger = runner.SequentialReplayLedger(self.spec)
        ledger.freeze("20260109", self.forecast("E"))
        ledger.reveal("20260109", {"date": "20260109", "close": 3.0})
        ledger.advance("20260109")
        with self.assertRaises(runner.RunContractError):
            ledger.record_weekend_bridge("20260112", {"target_outcome": 3.5})
        bridge = ledger.record_weekend_bridge("20260112", {"weekend_state": "available-only"})
        self.assertEqual(bridge["weekend_state"], "available-only")
        self.assertEqual(ledger.events[-1]["via"], "A")
        self.assertEqual(ledger.events[-1]["forecast_owner"], "B")

    def test_run_group_orders_freeze_before_reveal_and_routes_e_a_b(self):
        calls = []
        def forecast(plan, prompt, packet):
            calls.append(("forecast", plan.day, plan.owner, "s135_weekend_bridge_context" in packet))
            return self.forecast(plan.owner, 7 if plan.owner == "E" else 8)
        def reveal(gid, day):
            calls.append(("reveal", day))
            return {"date": day, "close": 3.0, "turn_kind": "none"}
        def bridge(plan, prompt, packet):
            calls.append(("bridge", plan.day, packet["specialist"]))
            return {"weekend_state": "Friday exit carried; no invented archive"}
        def score(plan, frozen, actual):
            calls.append(("score", plan.day, frozen["owner"]))
            return {"scored": True}

        ledger = runner.run_group(
            self.spec,
            forecast_fn=forecast,
            preflight_result=self.gate,
            reveal_fn=reveal,
            score_fn=score,
            weekend_bridge_fn=bridge,
            initial_prior_session={"date": "20260108", "close": 2.9},
            runtime_module=FakeRuntime,
        )
        self.assertTrue(ledger.complete)
        self.assertEqual(calls[0][:3], ("forecast", "20260109", "E"))
        self.assertEqual(calls[1], ("reveal", "20260109"))
        self.assertEqual(calls[2][:2], ("score", "20260109"))
        self.assertEqual(calls[3], ("bridge", "20260112", "A"))
        self.assertEqual(calls[4], ("forecast", "20260112", "B", True))
        self.assertEqual(calls[5], ("reveal", "20260112"))
        self.assertEqual(ledger.frozen_record("20260112").thaw_verified()["owner"], "B")

    def test_runner_refuses_execution_without_21_of_21_state_preflight(self):
        with self.assertRaises(runner.RunContractError):
            runner.run_group(
                self.spec,
                forecast_fn=lambda plan, prompt, packet: self.forecast(plan.owner),
                reveal_fn=lambda gid, day: {"date": day},
                score_fn=lambda plan, frozen, actual: {},
                weekend_bridge_fn=lambda plan, prompt, packet: {"weekend_state": "ok"},
                runtime_module=FakeRuntime,
            )
        bad = dict(self.gate)
        bad["mandatory_checks"] = dict(self.gate["mandatory_checks"])
        bad["mandatory_checks"]["check_21"] = False
        with self.assertRaises(runner.RunContractError):
            runner.run_group(
                self.spec,
                forecast_fn=lambda plan, prompt, packet: self.forecast(plan.owner),
                preflight_result=bad,
                reveal_fn=lambda gid, day: {"date": day},
                score_fn=lambda plan, frozen, actual: {},
                weekend_bridge_fn=lambda plan, prompt, packet: {"weekend_state": "ok"},
                runtime_module=FakeRuntime,
            )

    def test_runner_refuses_to_synthesize_weekend_bridge(self):
        with self.assertRaises(runner.RunContractError):
            runner.run_group(
                self.spec,
                forecast_fn=lambda plan, prompt, packet: self.forecast(plan.owner),
                preflight_result=self.gate,
                reveal_fn=lambda gid, day: {"date": day},
                score_fn=lambda plan, frozen, actual: {},
                initial_prior_session={"date": "20260108"},
                runtime_module=FakeRuntime,
            )

    def test_nested_same_or_future_date_in_prior_context_fails(self):
        with self.assertRaises(runner.RunContractError):
            runner.SequentialReplayLedger(
                self.spec,
                initial_prior_session={"date": "20260108", "note": "future marker 2026-01-09"},
            )

    def test_real_g24_config_is_date_swappable_and_has_internal_e_a_b_weekend(self):
        spec = runner.GroupRunSpec.from_group("g24", "blind")
        self.assertEqual(len(spec.days), 10)
        self.assertEqual(spec.days[0].day, "20260720")
        routes = []
        for prev, cur in zip(spec.days, spec.days[1:]):
            if runner._is_friday_to_monday(prev.day, cur.day):
                routes.append((prev.owner, "A", cur.owner))
        self.assertEqual(routes, [("E", "A", "B")])

    def test_preflight_exposes_all_21_mandatory_checks(self):
        fake_s135 = types.ModuleType("frankie_s135_current_runtime")
        fake_s135.stack_manifest = lambda: {}
        old = sys.modules.get("frankie_s135_current_runtime")
        sys.modules["frankie_s135_current_runtime"] = fake_s135
        try:
            path = ROOT / "research" / "kalshi" / "frankie_s135_preflight.py"
            pspec = importlib.util.spec_from_file_location("s135_preflight_test", path)
            preflight = importlib.util.module_from_spec(pspec)
            pspec.loader.exec_module(preflight)
        finally:
            if old is None:
                sys.modules.pop("frankie_s135_current_runtime", None)
            else:
                sys.modules["frankie_s135_current_runtime"] = old

        stack = {
            "stack_version": "s135.current-frankie.2",
            "specialists": list("ABCDE"),
            "canonical_plays_total": 100,
            "full_plays_served": 100,
            "modules": {
                "s126_specialist_parity": {},
                "s132_event_driven_curve": {},
                "s133_reasoning_authority": {},
                "s135_specialist_authority": {},
            },
            "requirements": {
                "full_s3_substrate_before_state": True,
                "current_brain_later_learned_evidence": "allowed except target-window outcome wall in historical improvement tests",
                "fixed_curve_clock": False,
                "abstain_flat_curve": False,
                "owner_averaging": False,
                "hydration": "REJECTED_NOT_USED",
                "new_datapoint_family": False,
                "sequential_prior_completed_session": True,
            },
        }
        state = {"state_health": "PASS", "tape_reconcile": "PASS", "archive_gap_proof": None}
        checks = preflight._mandatory_checks(stack, runner.runner_contract_manifest(), self.spec, state)
        self.assertEqual(len(checks), 21)
        self.assertTrue(all(checks.values()), checks)

    def test_manifest_locks_standing_constraints(self):
        manifest = runner.runner_contract_manifest()
        self.assertTrue(manifest["freeze_before_reveal"])
        self.assertTrue(manifest["score_frozen_artifact_only"])
        self.assertTrue(manifest["friday_e_to_a_to_monday_b"])
        self.assertFalse(manifest["coordinator_averaging"])
        self.assertFalse(manifest["fixed_curve_clock"])
        self.assertFalse(manifest["abstain_flattening"])
        self.assertEqual(manifest["hydration"], "REJECTED_NOT_USED")
        self.assertFalse(manifest["new_datapoint_family"])
        self.assertFalse(manifest["architecture_varies_by_group"])


if __name__ == "__main__":
    unittest.main()
