from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests


class AmberdataProvider:
    """Amberdata-backed OnchainProvider with normalized return fields."""

    BASE_URL = "https://web3api.io/api/v2"

    def __init__(self, api_key: str | None = None, timeout: float = 5.0):
        self.api_key = api_key or os.getenv("AMBERDATA_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError("AMBERDATA_API_KEY not set")

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.BASE_URL}{path}"
        headers = {
            "x-api-key": self.api_key,
            "accept": "application/json",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _time_range_params(self, window: timedelta) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        start = now - window
        return {
            "startDate": start.isoformat().replace("+00:00", "Z"),
            "endDate": now.isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def _payload(raw: dict[str, Any]) -> dict[str, Any]:
        payload = raw.get("payload") if isinstance(raw, dict) else {}
        return payload if isinstance(payload, dict) else {}

    def fetch_exchange_flows(self, asset: str, window: timedelta) -> dict[str, Any]:
        params = self._time_range_params(window)
        params["symbol"] = asset
        raw = self._get("/market/exchange-flows", params)
        d = self._payload(raw)
        return {
            "inflow_total": d.get("inflowAmount", 0.0),
            "outflow_total": d.get("outflowAmount", 0.0),
            "inflow_zscore": d.get("inflowZScore", 0.0),
            "outflow_zscore": d.get("outflowZScore", 0.0),
            "netflow_zscore": d.get("netflowZScore", 0.0),
            "inflow_whales_share": d.get("inflowWhalesShare", 0.0),
            "outflow_whales_share": d.get("outflowWhalesShare", 0.0),
        }

    def fetch_whales(self, asset: str, window: timedelta) -> dict[str, Any]:
        params = self._time_range_params(window)
        params["symbol"] = asset
        params["minBalanceUsd"] = 1_000_000
        raw = self._get("/addresses/top-holders", params)
        d = self._payload(raw)
        return {
            "accumulation_volume": d.get("accumulationAmount", 0.0),
            "distribution_volume": d.get("distributionAmount", 0.0),
            "accumulation_zscore": d.get("accumulationZScore", 0.0),
            "distribution_zscore": d.get("distributionZScore", 0.0),
            "accumulation_trend_1d": d.get("accumulationTrend1d", 0.0),
            "distribution_trend_1d": d.get("distributionTrend1d", 0.0),
            "whale_to_exchange_flow_ratio": d.get("whaleToExchangeFlowRatio", 0.0),
        }

    def fetch_smart_money(self, asset: str, window: timedelta) -> dict[str, Any]:
        params = self._time_range_params(window)
        params["symbol"] = asset
        params["cohort"] = "smartMoney"
        raw = self._get("/cohorts/flows", params)
        d = self._payload(raw)
        return {
            "net_into_asset_usd": d.get("netIntoAssetUsd", 0.0),
            "net_out_of_asset_usd": d.get("netOutOfAssetUsd", 0.0),
            "net_rotation_score": d.get("netRotationScore", 0.0),
            "rotation_zscore": d.get("rotationZScore", 0.0),
            "rotation_target": d.get("rotationTarget", asset),
            "rotation_source": d.get("rotationSource", "unknown"),
        }

    def fetch_stablecoins(self, window: timedelta) -> dict[str, Any]:
        raw = self._get("/stablecoins/exchange-flows", self._time_range_params(window))
        d = self._payload(raw)
        return {
            "exchange_inflow_usd": d.get("inflowUsd", 0.0),
            "exchange_outflow_usd": d.get("outflowUsd", 0.0),
            "netflow_usd": d.get("netflowUsd", 0.0),
            "netflow_zscore": d.get("netflowZScore", 0.0),
            "buying_power_score": d.get("buyingPowerScore", 0.0),
        }

    def fetch_network_stats(self, asset: str, window: timedelta) -> dict[str, Any]:
        params = self._time_range_params(window)
        params["symbol"] = asset
        raw = self._get("/metrics/network-activity", params)
        d = self._payload(raw)
        return {
            "active_addresses": d.get("activeAddresses", 0),
            "active_addresses_zscore": d.get("activeAddressesZScore", 0.0),
            "new_addresses": d.get("newAddresses", 0),
            "new_addresses_zscore": d.get("newAddressesZScore", 0.0),
            "tx_count": d.get("transactionCount", 0),
            "tx_count_zscore": d.get("transactionCountZScore", 0.0),
            "fee_rate": d.get("avgFeeRate", 0.0),
            "fee_rate_zscore": d.get("avgFeeRateZScore", 0.0),
            "defi_tvl_usd": d.get("defiTvlUsd"),
            "defi_tvl_zscore": d.get("defiTvlZScore"),
        }
