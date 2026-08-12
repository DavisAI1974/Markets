from __future__ import annotations

from dashboard.adapters import demo, paths, signals


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
    fanout_paths = signals._fanout_paths(state, "grid_stack.bas.US48.gas_mwh")
    assert fanout_paths == [
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


def test_dashboard_uses_canonical_markets_env_file(tmp_path, monkeypatch):
    """Regression for D1-11: M-10 must not strand the dashboard S3 read lane."""
    resolver = paths._canonical_creds()
    home_env = tmp_path / "markets.env"
    home_env.write_text(
        "AWS_ACCESS_KEY_ID=sentinel-access-id\n"
        "AWS_SECRET_ACCESS_KEY=sentinel-secret-value\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(resolver, "HOME_ENV", str(home_env))
    monkeypatch.setattr(resolver, "LEGACY", str(tmp_path / "absent-legacy.env"))
    monkeypatch.setattr(paths, "_looks_real", lambda key_id, secret: bool(key_id and secret))
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv("MARKETS_" + name, raising=False)

    resolved = paths.resolve_aws_creds()

    assert resolved == {
        "aws_access_key_id": "sentinel-access-id",
        "aws_secret_access_key": "sentinel-secret-value",
    }
    status = paths.aws_credential_status()
    assert status["resolved"] is True
    assert status["source"] == "research/kalshi/creds.py"


def test_dashboard_rejects_placeholder_credentials(monkeypatch):
    class PlaceholderResolver:
        @staticmethod
        def get(name, required=False):
            return "proxy-injected"

    monkeypatch.setattr(paths, "_canonical_creds", lambda: PlaceholderResolver())
    assert paths.resolve_aws_creds() is None
