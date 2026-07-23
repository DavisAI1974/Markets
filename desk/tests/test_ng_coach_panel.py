import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from desk import ng_coach_panel as panel  # noqa: E402
from desk.app import app, index  # noqa: E402


def message(sequence=1, event_s=100.0, event_type="INITIAL_UPDATE", text="Exact source update"):
    prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
    posterior = {"up": 0.65, "flat": 0.15, "down": 0.2}
    row = {
        "schema": panel.MESSAGE_SCHEMA,
        "authority": panel.MESSAGE_AUTHORITY,
        "market": "NG",
        "group": 15,
        "session_day": "20260318",
        "sequence": sequence,
        "as_of_event_s": event_s,
        "event_type": event_type,
        "priority": "normal",
        "material_change": True,
        "triggers": ["BLIND_TO_POSTERIOR_L1=0.500000"],
        "posterior_status": "STAND_DOWN" if event_type == "STAND_DOWN" else "UPDATED",
        "blind_prior": prior,
        "posterior": prior if event_type == "STAND_DOWN" else posterior,
        "top_direction": "up",
        "top_probability": 0.4 if event_type == "STAND_DOWN" else 0.65,
        "stand_down_reasons": ["mbo_gap"] if event_type == "STAND_DOWN" else [],
        "strongest_attribution": {
            "name": "signed_flow",
            "contribution": 0.5,
            "value": {"imb_level": 0.5},
        },
        "lag": {
            "status": "MEASURED_WINDOW",
            "timing_claim_allowed": True,
            "text": "Exact-product first reprice median 110 ms.",
            "lookup_fingerprint": "lag-fp",
            "key_fingerprint": "key-fp",
            "eligible_pre_cutoff_observations": 6,
            "first_reprice_p50_ms": 110.0,
            "first_reprice_p90_ms": 150.0,
            "reasons": [],
        },
        "invalidates_message_fingerprint": None,
        "display_text": text,
        "speech_text": text,
        "dedupe_key": f"dedupe-{sequence}",
        "source": {
            "posterior_output_fingerprint": f"posterior-{sequence}",
            "posterior_stream_fingerprint": "posterior-stream",
            "lag_lookup_fingerprint": "lag-fp",
        },
        "voxa_payload": {
            "schema": panel.VOXA_SCHEMA,
            "intent": "markets.ng.coach_update",
            "speech_text": text,
            "display_text": text,
            "priority": "normal",
            "dedupe_key": f"dedupe-{sequence}",
            "metadata": {
                "market": "NG",
                "group": 15,
                "session_day": "20260318",
                "sequence": sequence,
                "event_type": event_type,
                "top_direction": "up",
                "top_probability": 0.65,
                "posterior_output_fingerprint": f"posterior-{sequence}",
            },
            "transport_status": "ADAPTER_ONLY_NOT_SENT",
        },
        "transport_status": "ADAPTER_ONLY_NOT_SENT",
        "execution_authority": False,
        "may_update_ng_brain": False,
        "may_change_posterior": False,
        "may_change_blind_prior": False,
        "delivery_authority": False,
    }
    row["message_fingerprint"] = panel._fp(row)
    return row


def stream(messages=None, audit=None):
    messages = list(messages or [])
    audit = list(
        audit
        if audit is not None
        else [
            {
                "posterior_output_fingerprint": f"posterior-{row['sequence']}",
                "session_day": row["session_day"],
                "as_of_event_s": row["as_of_event_s"],
                "emitted": True,
                "message_fingerprint": row["message_fingerprint"],
            }
            for row in messages
        ]
    )
    value = {
        "schema": panel.STREAM_SCHEMA,
        "authority": panel.STREAM_AUTHORITY,
        "market": "NG",
        "group": 15,
        "source_posterior_stream_schema": "ng_rt_refine_stream.v1",
        "source_posterior_stream_fingerprint": "posterior-stream",
        "previous_coach_stream_fingerprint": None,
        "config": {
            "posterior_l1_threshold": 0.12,
            "top_probability_threshold": 0.52,
            "invalidation_drop_threshold": 0.12,
        },
        "material_change_only": True,
        "one_signal_authority_preserved": True,
        "n_posterior_outputs": len(audit),
        "n_messages": len(messages),
        "n_suppressed": sum(not bool(row.get("emitted")) for row in audit),
        "messages": messages,
        "audit": audit,
        "terminal_state_by_day": {},
        "transport_status": "ADAPTER_ONLY_NOT_SENT",
        "execution_authority": False,
        "may_update_ng_brain": False,
        "may_change_posterior": False,
        "may_change_blind_prior": False,
        "delivery_authority": False,
        "source_gate_schema": panel.SOURCE_GATE_SCHEMA,
        "source_gate_fingerprint": "source-gate-fp",
        "source_authorization_status": panel.SOURCE_STATUS,
        "source_authorization_schema": "ng_g15_pipeline.v1",
        "source_authorization_fingerprint": "source-auth-fp",
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "blind_forecast_immutable": True,
        "may_change_blind_forecast": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "READ_ONLY_DASHBOARD_OR_VOXA_PRESENTATION",
    }
    value["stream_fingerprint"] = panel._fp(value)
    return value


def write_payload(directory, payload):
    path = Path(directory) / "coach.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class CoachPanelTests(unittest.TestCase):
    def test_missing_file_is_offline_and_non_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(Path(directory) / "missing.json", now_s=100.0)
        self.assertEqual(result["panel_status"], "OFFLINE")
        self.assertFalse(result["execution_authority"])

    def test_invalid_json_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coach.json"
            path.write_text("not json", encoding="utf-8")
            result = panel.read_coach_stream(path, now_s=100.0)
        self.assertEqual(result["panel_status"], "INVALID")

    def test_fresh_exact_source_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(
                write_payload(directory, stream([message()])), now_s=105.0
            )
        self.assertEqual(result["panel_status"], "FRESH_SHADOW")
        self.assertTrue(result["one_signal_authority_preserved"])
        self.assertTrue(result["blind_forecast_immutable"])
        self.assertFalse(result["delivery_authority"])
        self.assertFalse(result["execution_authority"])

    def test_old_exact_source_stream_is_historical_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(
                write_payload(directory, stream([message()])), now_s=500.0
            )
        self.assertEqual(result["panel_status"], "HISTORICAL_REPLAY")

    def test_latest_stand_down_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(
                write_payload(directory, stream([message(event_type="STAND_DOWN")])),
                now_s=105.0,
            )
        self.assertEqual(result["panel_status"], "STAND_DOWN")
        self.assertEqual(result["latest_message"]["stand_down_reasons"], ["mbo_gap"])

    def test_no_material_change_is_explicit(self):
        audit = [
            {
                "posterior_output_fingerprint": "posterior-1",
                "session_day": "20260318",
                "as_of_event_s": 100.0,
                "emitted": False,
                "suppression_reasons": ["NO_MATERIAL_CHANGE"],
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(
                write_payload(directory, stream([], audit=audit)), now_s=105.0
            )
        self.assertEqual(result["panel_status"], "NO_MATERIAL_CHANGE")
        self.assertEqual(result["n_suppressed"], 1)

    def test_stream_fingerprint_tampering_is_invalid(self):
        value = stream([message()])
        value["n_suppressed"] = 999
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(write_payload(directory, value), now_s=105.0)
        self.assertEqual(result["panel_status"], "INVALID")

    def test_refingerprinted_execution_escalation_is_invalid(self):
        value = stream([message()])
        value["execution_authority"] = True
        value["stream_fingerprint"] = panel._fp({k: v for k, v in value.items() if k != "stream_fingerprint"})
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(write_payload(directory, value), now_s=105.0)
        self.assertEqual(result["panel_status"], "INVALID")

    def test_missing_source_gate_is_invalid(self):
        value = stream([message()])
        value["source_gate_schema"] = None
        value["stream_fingerprint"] = panel._fp({k: v for k, v in value.items() if k != "stream_fingerprint"})
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(write_payload(directory, value), now_s=105.0)
        self.assertEqual(result["panel_status"], "INVALID")

    def test_message_fingerprint_tampering_is_invalid(self):
        value = stream([message()])
        value["messages"][0]["display_text"] = "changed"
        value["stream_fingerprint"] = panel._fp({k: v for k, v in value.items() if k != "stream_fingerprint"})
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(write_payload(directory, value), now_s=105.0)
        self.assertEqual(result["panel_status"], "INVALID")

    def test_claimed_voxa_delivery_is_invalid_even_when_refingerprinted(self):
        row = message()
        row["voxa_payload"]["transport_status"] = "SENT"
        row["message_fingerprint"] = panel._fp({k: v for k, v in row.items() if k != "message_fingerprint"})
        value = stream([row])
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(write_payload(directory, value), now_s=105.0)
        self.assertEqual(result["panel_status"], "INVALID")

    def test_backward_message_chronology_is_invalid(self):
        value = stream([message(1, 200.0), message(2, 100.0)])
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(write_payload(directory, value), now_s=205.0)
        self.assertEqual(result["panel_status"], "INVALID")

    def test_duplicate_dedupe_key_is_invalid(self):
        first = message(1, 100.0)
        second = message(2, 200.0)
        second["dedupe_key"] = first["dedupe_key"]
        second["message_fingerprint"] = panel._fp({k: v for k, v in second.items() if k != "message_fingerprint"})
        value = stream([first, second])
        with tempfile.TemporaryDirectory() as directory:
            result = panel.read_coach_stream(write_payload(directory, value), now_s=205.0)
        self.assertEqual(result["panel_status"], "INVALID")

    def test_render_escapes_message_text(self):
        row = message(text="<script>alert(1)</script>")
        result = {
            "panel_status": "FRESH_SHADOW",
            "latest_message": row,
            "group": 15,
            "n_messages": 1,
            "n_suppressed": 0,
        }
        rendered = panel.render_coach_panel(result)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_render_states_adapter_only_and_execution_unavailable(self):
        result = {
            "panel_status": "FRESH_SHADOW",
            "latest_message": message(),
            "group": 15,
            "n_messages": 1,
            "n_suppressed": 0,
        }
        rendered = panel.render_coach_panel(result)
        self.assertIn("VOXA ADAPTER ONLY", rendered)
        self.assertIn("transport not sent", rendered)
        self.assertIn("Execution unavailable", rendered)

    def test_desk_routes_and_htmx_wiring_exist(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/api/ng/coach", paths)
        self.assertIn("/partials/ng-coach", paths)
        page = index()
        self.assertIn('hx-get="/partials/ng-coach"', page)
        self.assertIn("coach 5s", page)
        self.assertIn("execution gated", page)


if __name__ == "__main__":
    unittest.main()
