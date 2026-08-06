from __future__ import annotations

from dashboard.adapters import demo, signals


def test_resolve_supports_dicts_and_arrays():
    state = {"a": {"b": [{"c": 7}]}}
    assert signals.resolve(state, "a.b[0].c") == 7
    assert signals.resolve(state, "a.b[1].c") is None
    assert signals.resolve(state, "a.missing") is None


def test_fanout_uses_actual_state_keys():
    state = {
        "grid_stack": {
            "bas": {
                "ERCO": {"gas_mwh": 10},
                "US48": {"gas_mwh": 20},
            }
        }
    }
    paths = signals._fanout_paths(state, "grid_stack.bas.US48.gas_mwh")
    assert paths == [
        "grid_stack.bas.ERCO.gas_mwh",
        "grid_stack.bas.US48.gas_mwh",
    ]


def test_demo_feed_has_no_execution_authority(monkeypatch):
    monkeypatch.delenv("KALSHI_DEMO_API_KEY_ID", raising=False)
    monkeypatch.delenv("KALSHI_DEMO_PRIVATE_KEY_PATH", raising=False)
    signal_snapshot = {
        "signals": [
            {
                "example_path": "weather_forecast.forecast_run_delta_cdd",
                "values": [
                    {
                        "path": "weather_forecast.forecast_run_delta_cdd",
                        "value": 1.25,
                        "available": True,
                    }
                ],
            }
        ]
    }
    feed = demo.snapshot("20260805", {"state": {}}, signal_snapshot)
    assert feed["execution_enabled"] is False
    assert feed["credential_status"]["write_enabled"] is False
    assert feed["opportunities"]
    assert all(row["execution_authority"] == "NONE" for row in feed["opportunities"])
    assert feed["opportunities"][0]["signal_value"] == 1.25
