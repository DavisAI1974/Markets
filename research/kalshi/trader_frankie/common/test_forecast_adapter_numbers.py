"""Regression checks for numeric preservation in the read-only forecast adapter."""
from __future__ import annotations

from .forecast_adapter import ReadOnlyForecastAdapter, _number


def test_number_preserves_numeric_values() -> None:
    assert _number(0.75) == 0.75
    assert _number("1.25") == 1.25
    assert _number(2) == 2.0


def test_number_rejects_non_numeric_and_bool_values() -> None:
    assert _number(None) is None
    assert _number(True) is None
    assert _number("not-a-number") is None


def test_adapter_preserves_confidence_and_terminal_move() -> None:
    envelope = ReadOnlyForecastAdapter().adapt(
        {
            "forecast_id": "regression-numeric-adapter",
            "forecast": {
                "direction": "UP",
                "expected_terminal_move": 0.031,
                "confidence": 0.82,
            },
        }
    )
    assert envelope.forecast.expected_terminal_move == 0.031
    assert envelope.forecast.confidence == 0.82
