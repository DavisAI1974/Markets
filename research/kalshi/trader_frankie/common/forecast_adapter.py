"""External, read-only adapter from existing Frankie output to ForecastEnvelope."""
from __future__ import annotations

import copy
import json
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .hashing import hash_payload
from .models import ChainState, Forecast, ForecastEnvelope, ForecastProvenance


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _tuple_strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(str(item) for item in value if item is not None)
    return ()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class ReadOnlyForecastAdapter:
    """Copies input before adapting and never imports or writes any Frankie 1 module or path."""

    forecaster_id = "FRANKIE_1"

    def adapt(self, raw: Mapping[str, Any]) -> ForecastEnvelope:
        if not isinstance(raw, Mapping):
            raise TypeError("Frankie output must be a mapping")
        # JSON round-trip guarantees this adapter holds no live reference to parent state.
        detached = json.loads(json.dumps(copy.deepcopy(dict(raw)), allow_nan=False))
        forecast = _mapping(detached.get("forecast"))
        prediction = _mapping(detached.get("prediction"))
        posterior = _mapping(detached.get("posterior"))
        metadata = _mapping(detached.get("metadata"))
        chain = _mapping(_first(detached.get("chain_state"), detached.get("chain")))
        provenance = _mapping(detached.get("provenance"))

        expected_path = _first(
            forecast.get("expected_path"), prediction.get("expected_path"), detached.get("expected_path")
        )
        if not isinstance(expected_path, list):
            expected_path = []
        source_hashes = _first(provenance.get("source_hashes"), detached.get("source_hashes"), [])
        return ForecastEnvelope(
            forecast_id=_first(
                detached.get("forecast_id"), detached.get("decision_id"), detached.get("event_id")
            ),
            forecaster=self.forecaster_id,
            forecaster_version=_first(
                detached.get("forecaster_version"), detached.get("agent_version"), metadata.get("version")
            ),
            generated_at=_first(
                detached.get("generated_at"), detached.get("generated_at_utc"), detached.get("observed_at")
            ),
            information_cutoff=_first(
                detached.get("information_cutoff"), detached.get("knowable_at"), metadata.get("cutoff")
            ),
            underlying=_first(
                detached.get("underlying"), forecast.get("underlying"), metadata.get("underlying")
            ),
            forecast=Forecast(
                direction=_first(
                    forecast.get("direction"), prediction.get("direction"), posterior.get("direction"),
                    detached.get("direction"),
                ),
                expected_path=tuple(_freeze_json(item) for item in expected_path),
                expected_terminal_move=_number(_first(
                    forecast.get("expected_terminal_move"), prediction.get("terminal_move"),
                    detached.get("expected_terminal_move"),
                )),
                confidence=_number(_first(
                    forecast.get("confidence"), prediction.get("confidence"), posterior.get("confidence"),
                    detached.get("confidence"),
                )),
                horizon=_first(forecast.get("horizon"), prediction.get("horizon"), detached.get("horizon")),
            ),
            chain_state=ChainState(
                mechanism=chain.get("mechanism"),
                depth=int(chain["depth"]) if isinstance(chain.get("depth"), int) else None,
                origin_id=chain.get("origin_id"),
                polarity=chain.get("polarity"),
                expected_lifespan=chain.get("expected_lifespan"),
                invalidation=_tuple_strings(chain.get("invalidation")),
            ),
            provenance=ForecastProvenance(
                forecast_hash=str(provenance.get("forecast_hash") or hash_payload(detached)),
                brain_version=_first(provenance.get("brain_version"), metadata.get("brain_version")),
                source_hashes=_tuple_strings(source_hashes),
            ),
        )
