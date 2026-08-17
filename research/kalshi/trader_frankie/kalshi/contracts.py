"""Explicit Kalshi contract registry and exact-identity resolver."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..common.hashing import hash_payload
from ..common.models import ForecastEnvelope, IdentityStatus
from .models import ContractMapping, ContractResolution, ObservedContract


class RegistryError(RuntimeError):
    pass


def _required(raw: Mapping[str, Any], name: str) -> Any:
    value = raw.get(name)
    if value is None or value == "":
        raise RegistryError(f"contract mapping missing {name}")
    return value


class KalshiContractRegistry:
    def __init__(self, mappings: tuple[ContractMapping, ...]) -> None:
        self._by_ticker: dict[str, ContractMapping] = {}
        for mapping in mappings:
            if mapping.ticker in self._by_ticker:
                raise RegistryError(f"duplicate approved ticker: {mapping.ticker}")
            self._by_ticker[mapping.ticker] = mapping

    @classmethod
    def from_file(cls, path: str | Path) -> "KalshiContractRegistry":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        items = raw.get("mappings") if isinstance(raw, dict) else None
        if not isinstance(items, list):
            raise RegistryError("Kalshi registry must contain a mappings list")
        mappings: list[ContractMapping] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise RegistryError("Kalshi mapping must be an object")
            mappings.append(ContractMapping(
                mapping_id=str(_required(item, "mapping_id")),
                ticker=str(_required(item, "ticker")),
                event_ticker=str(_required(item, "event_ticker")),
                series_ticker=str(_required(item, "series_ticker")),
                yes_meaning=str(_required(item, "yes_meaning")),
                no_meaning=str(_required(item, "no_meaning")),
                settlement_condition=str(_required(item, "settlement_condition")),
                settlement_source=str(_required(item, "settlement_source")),
                settlement_field=str(_required(item, "settlement_field")),
                settlement_time=str(_required(item, "settlement_time")),
                close_time=str(_required(item, "close_time")),
                expiration_time=str(_required(item, "expiration_time")),
                underlying=str(_required(item, "underlying")),
                compatible_horizons=tuple(str(v) for v in _required(item, "compatible_horizons")),
                enabled_routes=tuple(str(v) for v in _required(item, "enabled_routes")),
                version=str(_required(item, "version")),
            ))
        return cls(tuple(mappings))

    def get(self, ticker: str) -> ContractMapping | None:
        return self._by_ticker.get(ticker)

    def resolve(
        self,
        *,
        ticker: str,
        forecast: ForecastEnvelope,
        observed: ObservedContract,
    ) -> ContractResolution:
        mapping = self.get(ticker)
        if mapping is None:
            return ContractResolution(
                status=IdentityStatus.UNKNOWN,
                mapping=None,
                reasons=("TICKER_NOT_IN_APPROVED_REGISTRY",),
                identity_hash=hash_payload({"ticker": ticker, "status": "UNKNOWN"}),
            )
        expected = {
            "ticker": mapping.ticker,
            "event_ticker": mapping.event_ticker,
            "series_ticker": mapping.series_ticker,
            "yes_meaning": mapping.yes_meaning,
            "no_meaning": mapping.no_meaning,
            "settlement_condition": mapping.settlement_condition,
            "settlement_source": mapping.settlement_source,
            "settlement_field": mapping.settlement_field,
            "settlement_time": mapping.settlement_time,
            "close_time": mapping.close_time,
            "expiration_time": mapping.expiration_time,
        }
        actual = {
            key: getattr(observed, key) for key in expected
        }
        unknown = sorted(key for key, value in actual.items() if value is None or value == "")
        mismatches = sorted(key for key in expected if actual[key] is not None and actual[key] != expected[key])
        if forecast.underlying is None or forecast.forecast.horizon is None:
            unknown.extend(key for key, value in (
                ("forecast.underlying", forecast.underlying),
                ("forecast.horizon", forecast.forecast.horizon),
            ) if value is None)
        else:
            if forecast.underlying != mapping.underlying:
                mismatches.append("forecast.underlying")
            if forecast.forecast.horizon not in mapping.compatible_horizons:
                mismatches.append("forecast.horizon")
        identity_payload = {
            "mapping": mapping.as_dict(),
            "observed": actual,
            "observed_source_hash": observed.raw_source_hash,
            "forecast_underlying": forecast.underlying,
            "forecast_horizon": forecast.forecast.horizon,
        }
        if mismatches:
            status = IdentityStatus.MISMATCH
            reasons = tuple(f"MISMATCH:{key}" for key in sorted(set(mismatches)))
        elif unknown:
            status = IdentityStatus.UNKNOWN
            reasons = tuple(f"UNKNOWN:{key}" for key in sorted(set(unknown)))
        else:
            status = IdentityStatus.EXACT
            reasons = ("ALL_IDENTITY_FIELDS_EXACT",)
        return ContractResolution(
            status=status,
            mapping=mapping,
            reasons=reasons,
            identity_hash=hash_payload(identity_payload),
        )
