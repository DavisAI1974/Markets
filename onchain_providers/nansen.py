from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests


class NansenProvider:
    """Nansen-backed OnchainProvider.

    Endpoint paths and raw keys are isolated here so the rest of the platform
    only sees the normalized on-chain schema from onchain_features.py.
    """

    BASE_URL = "https://api.nansen.ai"

    def __init__(self, api_key: str | None = None, timeout: float = 5.0):
        self.api_key = api_key or os.getenv("NANSEN_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError("NANSEN_API_KEY not set")

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _time_range_params(self, window: timedelta) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        start = now - window
        return {
            "start_time": start.isoformat().replace("+00:00", "Z"),
            "end_time": now.isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def _data(raw: dict[str, Any]) -> dict[str, Any]:
        data = raw.get("data") if isinstance(raw, dict) else {}
        return data if isinstance(data, dict) else {}

    def fetch_exchange_flows(self, asset: str, window: timedelta) -> dict[str, Any]:
        params = self._time_range_params(window)
        params["asset"] = asset
        raw = self._get("/v1/exchange-flows", params)
        d = self._data(raw)
        return {
            "inflow_total": d.get("inflow_total", 0.0),
            "outflow_total": d.get("outflow_total", 0.0),
            "inflow_zscore": d.get("inflow_zscore", 0.0),
            "outflow_zscore": d.get("outflow_zscore", 0.0),
            "netflow_zscore": d.get("netflow_zscore", 0.0),
            "inflow_whales_share": d.get("inflow_whales_share", 0.0),
            "outflow_whales_share": d.get("outflow_whales_share", 0.0),
        }

    def fetch_whales(self, asset: str, window: timedelta) -> dict[str, Any]:
        params = self._time_range_params(window)
        params["asset"] = asset
        raw = self._get("/v1/whales/accumulation", params)
        d = self._data(raw)
        return {
            "accumulation_volume": d.get("accumulation_volume", 0.0),
            "distribution_volume": d.get("distribution_volume", 0.0),
            "accumulation_zscore": d.get("accumulation_zscore", 0.0),
            "distribution_zscore": d.get("distribution_zscore", 0.0),
            "accumulation_trend_1d": d.get("accumulation_trend_1d", 0.0),
            "distribution_trend_1d": d.get("distribution_trend_1d", 0.0),
            "whale_to_exchange_flow_ratio": d.get("whale_to_exchange_flow_ratio", 0.0),
        }

    def fetch_smart_money(self, asset: str, window: timedelta) -> dict[str, Any]:
        params = self._time_range_params(window)
        params["asset"] = asset
        raw = self._get("/v1/smart-money/rotations", params)
        d = self._data(raw)
        return {
            "net_into_asset_usd": d.get("net_into_asset_usd", 0.0),
            "net_out_of_asset_usd": d.get("net_out_of_asset_usd", 0.0),
            "net_rotation_score": d.get("net_rotation_score", 0.0),
            "rotation_zscore": d.get("rotation_zscore", 0.0),
            "rotation_target": d.get("rotation_target", asset),
            "rotation_source": d.get("rotation_source", "unknown"),
        }

    def fetch_stablecoins(self, window: timedelta) -> dict[str, Any]:
        raw = self._get("/v1/stablecoins/exchange-flows", self._time_range_params(window))
        d = self._data(raw)
        return {
            "exchange_inflow_usd": d.get("inflow_usd", 0.0),
            "exchange_outflow_usd": d.get("outflow_usd", 0.0),
            "netflow_usd": d.get("netflow_usd", 0.0),
            "netflow_zscore": d.get("netflow_zscore", 0.0),
            "buying_power_score": d.get("buying_power_score", 0.0),
        }

    def fetch_network_stats(self, asset: str, window: timedelta) -> dict[str, Any]:
        params = self._time_range_params(window)
        params["asset"] = asset
        raw = self._get("/v1/network/stats", params)
        d = self._data(raw)
        return {
            "active_addresses": d.get("active_addresses", 0),
            "active_addresses_zscore": d.get("active_addresses_zscore", 0.0),
            "new_addresses": d.get("new_addresses", 0),
            "new_addresses_zscore": d.get("new_addresses_zscore", 0.0),
            "tx_count": d.get("tx_count", 0),
            "tx_count_zscore": d.get("tx_count_zscore", 0.0),
            "fee_rate": d.get("fee_rate", 0.0),
            "fee_rate_zscore": d.get("fee_rate_zscore", 0.0),
            "defi_tvl_usd": d.get("defi_tvl_usd"),
            "defi_tvl_zscore": d.get("defi_tvl_zscore"),
        }
