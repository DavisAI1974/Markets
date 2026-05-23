from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


ONCHAIN_ACCUMULATION = "onchain_accumulation"
ONCHAIN_DISTRIBUTION = "onchain_distribution"
ONCHAIN_NEUTRAL = "onchain_neutral"
ONCHAIN_STRESS = "onchain_stress"
ONCHAIN_ROTATION = "onchain_rotation"


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class OnchainFeatures:
    asset: str
    ts_utc: float
    window_minutes: int = 60
    exchange_flows: dict[str, Any] = field(default_factory=dict)
    whales: dict[str, Any] = field(default_factory=dict)
    smart_money: dict[str, Any] = field(default_factory=dict)
    stablecoins: dict[str, Any] = field(default_factory=dict)
    network: dict[str, Any] = field(default_factory=dict)
    dex_cex_flows: dict[str, Any] = field(default_factory=dict)
    perp_protocol: dict[str, Any] = field(default_factory=dict)
    stables_health: dict[str, Any] = field(default_factory=dict)
    labels: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        regime = classify_onchain_regime(out)
        out["timestamp"] = datetime.fromtimestamp(float(self.ts_utc), timezone.utc).isoformat()
        out["regime"] = regime
        out["labels"] = {
            **self.labels,
            "onchain_regime": regime,
        }
        return out


class OnchainProvider(Protocol):
    """Provider boundary for Nansen, Amberdata, or self-indexed data."""

    def fetch_exchange_flows(self, asset: str, window: timedelta) -> dict[str, Any]:
        ...

    def fetch_whales(self, asset: str, window: timedelta) -> dict[str, Any]:
        ...

    def fetch_smart_money(self, asset: str, window: timedelta) -> dict[str, Any]:
        ...

    def fetch_stablecoins(self, window: timedelta) -> dict[str, Any]:
        ...

    def fetch_network_stats(self, asset: str, window: timedelta) -> dict[str, Any]:
        ...


DEFAULT_WINDOW_MINUTES = 60


def empty_onchain_features(asset: str, ts_utc: float, window_minutes: int = 60) -> dict[str, Any]:
    return OnchainFeatures(
        asset=asset,
        ts_utc=ts_utc,
        window_minutes=window_minutes,
        exchange_flows={
            "window_minutes": window_minutes,
            "inflow_total": 0.0,
            "outflow_total": 0.0,
            "inflow_zscore": 0.0,
            "outflow_zscore": 0.0,
            "netflow": 0.0,
            "netflow_zscore": 0.0,
            "inflow_whales_share": 0.0,
            "outflow_whales_share": 0.0,
        },
        whales={
            "window_minutes": 180,
            "accumulation_volume": 0.0,
            "distribution_volume": 0.0,
            "accumulation_zscore": 0.0,
            "distribution_zscore": 0.0,
            "accumulation_trend_1d": 0.0,
            "distribution_trend_1d": 0.0,
            "whale_to_exchange_flow_ratio": 0.0,
        },
        smart_money={
            "window_minutes": 240,
            "net_into_asset_usd": 0.0,
            "net_out_of_asset_usd": 0.0,
            "net_rotation_score": 0.0,
            "rotation_zscore": 0.0,
            "rotation_target": asset,
            "rotation_source": "unknown",
        },
        stablecoins={
            "window_minutes": window_minutes,
            "exchange_inflow_usd": 0.0,
            "exchange_outflow_usd": 0.0,
            "netflow_usd": 0.0,
            "netflow_zscore": 0.0,
            "buying_power_score": 0.0,
        },
        network={
            "window_minutes": 1440,
            "active_addresses": 0,
            "active_addresses_zscore": 0.0,
            "new_addresses": 0,
            "new_addresses_zscore": 0.0,
            "tx_count": 0,
            "tx_count_zscore": 0.0,
            "fee_rate_sat_per_vb": 0.0,
            "fee_rate_zscore": 0.0,
            "defi_tvl_usd": 0.0,
            "defi_tvl_zscore": 0.0,
        },
        dex_cex_flows={
            "window_minutes": window_minutes,
            "dex_volume_usd": 0.0,
            "cex_volume_usd": 0.0,
            "dex_cex_volume_ratio": 0.0,
            "dex_cex_ratio_zscore": 0.0,
        },
        perp_protocol={
            "window_minutes": window_minutes,
            "liquidations_long_usd": 0.0,
            "liquidations_short_usd": 0.0,
            "liquidations_zscore": 0.0,
            "open_interest_change_usd": 0.0,
        },
        stables_health={
            "usdt_premium_bps": 0.0,
            "usdc_premium_bps": 0.0,
            "depeg_risk_score": 0.0,
        },
    ).to_dict()


def build_onchain_features(
    provider: OnchainProvider,
    asset: str,
    now: datetime | None = None,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
) -> OnchainFeatures:
    """Build the canonical on-chain block from any provider implementation."""
    now = now or datetime.now(timezone.utc)
    window = timedelta(minutes=window_minutes)
    network_window = timedelta(days=1)
    return OnchainFeatures(
        asset=asset,
        ts_utc=now.astimezone(timezone.utc).timestamp(),
        window_minutes=window_minutes,
        exchange_flows=_build_exchange_flows(provider, asset, window),
        whales=_build_whales(provider, asset, window),
        smart_money=_build_smart_money(provider, asset, window),
        stablecoins=_build_stablecoins(provider, window),
        network=_build_network(provider, asset, network_window),
    )


def _build_exchange_flows(provider: OnchainProvider, asset: str, window: timedelta) -> dict[str, Any]:
    raw = provider.fetch_exchange_flows(asset, window) or {}
    inflow = _float(raw.get("inflow_total"))
    outflow = _float(raw.get("outflow_total"))
    return {
        "window_minutes": int(window.total_seconds() / 60),
        "inflow_total": inflow,
        "outflow_total": outflow,
        "inflow_zscore": _float(raw.get("inflow_zscore")),
        "outflow_zscore": _float(raw.get("outflow_zscore")),
        "netflow": _float(raw.get("netflow"), inflow - outflow),
        "netflow_zscore": _float(raw.get("netflow_zscore")),
        "inflow_whales_share": _float(raw.get("inflow_whales_share")),
        "outflow_whales_share": _float(raw.get("outflow_whales_share")),
    }


def _build_whales(provider: OnchainProvider, asset: str, window: timedelta) -> dict[str, Any]:
    raw = provider.fetch_whales(asset, window) or {}
    return {
        "window_minutes": int(window.total_seconds() / 60),
        "accumulation_volume": _float(raw.get("accumulation_volume")),
        "distribution_volume": _float(raw.get("distribution_volume")),
        "accumulation_zscore": _float(raw.get("accumulation_zscore")),
        "distribution_zscore": _float(raw.get("distribution_zscore")),
        "accumulation_trend_1d": _float(raw.get("accumulation_trend_1d")),
        "distribution_trend_1d": _float(raw.get("distribution_trend_1d")),
        "whale_to_exchange_flow_ratio": _float(raw.get("whale_to_exchange_flow_ratio")),
    }


def _build_smart_money(provider: OnchainProvider, asset: str, window: timedelta) -> dict[str, Any]:
    raw = provider.fetch_smart_money(asset, window) or {}
    return {
        "window_minutes": int(window.total_seconds() / 60),
        "net_into_asset_usd": _float(raw.get("net_into_asset_usd")),
        "net_out_of_asset_usd": _float(raw.get("net_out_of_asset_usd")),
        "net_rotation_score": _float(raw.get("net_rotation_score")),
        "rotation_zscore": _float(raw.get("rotation_zscore")),
        "rotation_target": raw.get("rotation_target") or asset,
        "rotation_source": raw.get("rotation_source") or "unknown",
    }


def _build_stablecoins(provider: OnchainProvider, window: timedelta) -> dict[str, Any]:
    raw = provider.fetch_stablecoins(window) or {}
    return {
        "window_minutes": int(window.total_seconds() / 60),
        "exchange_inflow_usd": _float(raw.get("exchange_inflow_usd")),
        "exchange_outflow_usd": _float(raw.get("exchange_outflow_usd")),
        "netflow_usd": _float(raw.get("netflow_usd")),
        "netflow_zscore": _float(raw.get("netflow_zscore")),
        "buying_power_score": _float(raw.get("buying_power_score")),
    }


def _build_network(provider: OnchainProvider, asset: str, window: timedelta) -> dict[str, Any]:
    raw = provider.fetch_network_stats(asset, window) or {}
    return {
        "window_minutes": int(window.total_seconds() / 60),
        "active_addresses": int(_float(raw.get("active_addresses"))),
        "active_addresses_zscore": _float(raw.get("active_addresses_zscore")),
        "new_addresses": int(_float(raw.get("new_addresses"))),
        "new_addresses_zscore": _float(raw.get("new_addresses_zscore")),
        "tx_count": int(_float(raw.get("tx_count"))),
        "tx_count_zscore": _float(raw.get("tx_count_zscore")),
        "fee_rate": _float(raw.get("fee_rate"), _float(raw.get("fee_rate_sat_per_vb"))),
        "fee_rate_sat_per_vb": _float(raw.get("fee_rate_sat_per_vb"), _float(raw.get("fee_rate"))),
        "fee_rate_zscore": _float(raw.get("fee_rate_zscore")),
        "defi_tvl_usd": raw.get("defi_tvl_usd"),
        "defi_tvl_zscore": raw.get("defi_tvl_zscore"),
    }


def classify_onchain_regime(
    onchain: dict[str, Any] | None = None,
    *,
    exchange_flows: dict[str, Any] | None = None,
    whales: dict[str, Any] | None = None,
    smart_money: dict[str, Any] | None = None,
    stablecoins: dict[str, Any] | None = None,
    network: dict[str, Any] | None = None,
) -> str:
    onchain = onchain or {}
    flows = exchange_flows if exchange_flows is not None else onchain.get("exchange_flows") or {}
    whales = whales if whales is not None else onchain.get("whales") or {}
    smart = smart_money if smart_money is not None else onchain.get("smart_money") or {}
    stables = stablecoins if stablecoins is not None else onchain.get("stablecoins") or {}
    network = network if network is not None else onchain.get("network") or {}

    netflow_z = _float(flows.get("netflow_zscore"))
    inflow_z = _float(flows.get("inflow_zscore"))
    accumulation_z = _float(whales.get("accumulation_zscore"))
    distribution_z = _float(whales.get("distribution_zscore"))
    stable_netflow_z = _float(stables.get("netflow_zscore"))
    rotation_z = abs(_float(smart.get("rotation_zscore")))
    net_out = _float(smart.get("net_out_of_asset_usd"))
    fee_z = _float(network.get("fee_rate_zscore"))

    if netflow_z <= -2.0 and accumulation_z >= 1.5 and stable_netflow_z >= 1.5:
        return ONCHAIN_ACCUMULATION
    if netflow_z >= 2.0 and distribution_z >= 1.5:
        return ONCHAIN_DISTRIBUTION
    if stable_netflow_z >= 2.0 and rotation_z >= 2.0:
        return ONCHAIN_ROTATION
    if inflow_z >= 3.0 and (net_out > 0.0 or fee_z >= 2.5):
        return ONCHAIN_STRESS
    return ONCHAIN_NEUTRAL


def classify_onchain_regime_blocks(
    *,
    exchange_flows: dict[str, Any],
    whales: dict[str, Any],
    smart_money: dict[str, Any],
    stablecoins: dict[str, Any],
    network: dict[str, Any],
) -> str:
    return classify_onchain_regime(
        exchange_flows=exchange_flows,
        whales=whales,
        smart_money=smart_money,
        stablecoins=stablecoins,
        network=network,
    )


def onchain_allows_side(onchain_regime: str, side: str) -> tuple[bool, str]:
    side_norm = str(side or "").lower()
    if side_norm in {"buy", "long"} and onchain_regime == ONCHAIN_DISTRIBUTION:
        return False, "On-chain distribution conflicts with long exposure"
    if side_norm in {"sell", "short"} and onchain_regime == ONCHAIN_ACCUMULATION:
        return False, "On-chain accumulation conflicts with short exposure"
    return True, ""
