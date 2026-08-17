"""Explicit tastytrade instrument registry, initially optimized for the NG futures path."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..common.hashing import hash_payload
from ..common.models import ForecastEnvelope, IdentityStatus
from .models import InstrumentMapping, InstrumentResolution, InstrumentType, ObservedInstrument


class InstrumentRegistryError(RuntimeError):
    pass


def _required(raw: Mapping[str, Any], name: str) -> Any:
    value = raw.get(name)
    if value is None or value == "":
        raise InstrumentRegistryError(f"instrument mapping missing {name}")
    return value


class TastyInstrumentRegistry:
    def __init__(self, mappings: tuple[InstrumentMapping, ...]) -> None:
        self._by_id: dict[str, InstrumentMapping] = {}
        for mapping in mappings:
            if mapping.instrument_id in self._by_id:
                raise InstrumentRegistryError(f"duplicate instrument_id: {mapping.instrument_id}")
            self._by_id[mapping.instrument_id] = mapping

    @classmethod
    def from_file(cls, path: str | Path) -> "TastyInstrumentRegistry":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        items = raw.get("instruments") if isinstance(raw, dict) else None
        if not isinstance(items, list):
            raise InstrumentRegistryError("Tasty registry must contain an instruments list")
        mappings: list[InstrumentMapping] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise InstrumentRegistryError("Tasty instrument mapping must be an object")
            mappings.append(InstrumentMapping(
                instrument_id=str(_required(item, "instrument_id")),
                symbol=str(_required(item, "symbol")),
                instrument_type=InstrumentType(str(_required(item, "instrument_type"))),
                root_symbol=str(_required(item, "root_symbol")),
                product_code=str(_required(item, "product_code")),
                exchange=str(_required(item, "exchange")),
                underlying=str(_required(item, "underlying")),
                contract_multiplier=float(_required(item, "contract_multiplier")),
                tick_size=float(_required(item, "tick_size")),
                expiration_time=str(_required(item, "expiration_time")),
                compatible_horizons=tuple(str(v) for v in _required(item, "compatible_horizons")),
                enabled_routes=tuple(str(v) for v in _required(item, "enabled_routes")),
                version=str(_required(item, "version")),
            ))
        return cls(tuple(mappings))

    def get(self, instrument_id: str) -> InstrumentMapping | None:
        return self._by_id.get(instrument_id)

    def resolve(
        self,
        *,
        instrument_id: str,
        forecast: ForecastEnvelope,
        observed: ObservedInstrument,
    ) -> InstrumentResolution:
        mapping = self.get(instrument_id)
        if mapping is None:
            return InstrumentResolution(
                status=IdentityStatus.UNKNOWN,
                mapping=None,
                reasons=("INSTRUMENT_NOT_IN_APPROVED_REGISTRY",),
                identity_hash=hash_payload({"instrument_id": instrument_id, "status": "UNKNOWN"}),
            )
        expected = {
            "symbol": mapping.symbol,
            "instrument_type": mapping.instrument_type.value,
            "root_symbol": mapping.root_symbol,
            "product_code": mapping.product_code,
            "exchange": mapping.exchange,
            "contract_multiplier": mapping.contract_multiplier,
            "tick_size": mapping.tick_size,
            "expiration_time": mapping.expiration_time,
        }
        actual = {key: getattr(observed, key) for key in expected}
        unknown = [key for key, value in actual.items() if value is None or value == ""]
        mismatches = [key for key in expected if actual[key] is not None and actual[key] != expected[key]]
        if observed.active is not True:
            (unknown if observed.active is None else mismatches).append("active")
        if observed.tradeable is not True:
            (unknown if observed.tradeable is None else mismatches).append("tradeable")
        if forecast.underlying is None or forecast.forecast.horizon is None:
            if forecast.underlying is None:
                unknown.append("forecast.underlying")
            if forecast.forecast.horizon is None:
                unknown.append("forecast.horizon")
        else:
            if forecast.underlying != mapping.underlying:
                mismatches.append("forecast.underlying")
            if forecast.forecast.horizon not in mapping.compatible_horizons:
                mismatches.append("forecast.horizon")
        payload = {
            "mapping": mapping.as_dict(),
            "observed": actual,
            "active": observed.active,
            "tradeable": observed.tradeable,
            "raw_source_hash": observed.raw_source_hash,
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
            reasons = ("ALL_INSTRUMENT_FIELDS_EXACT",)
        return InstrumentResolution(
            status=status, mapping=mapping, reasons=reasons, identity_hash=hash_payload(payload)
        )
