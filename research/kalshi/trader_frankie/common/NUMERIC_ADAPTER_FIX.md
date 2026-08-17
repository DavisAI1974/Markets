# Trader Frankie numeric adapter regression fix

The read-only forecast adapter previously returned `None` for ordinary numeric inputs because `_number()` exited before its float conversion and the conversion block was unreachable inside `_freeze_json()`.

Fixed behavior:

- `None` and booleans remain rejected as numeric forecast values.
- integers, floats, and numeric strings convert to `float`.
- invalid numeric strings return `None`.
- `Forecast.expected_terminal_move` and `Forecast.confidence` now preserve valid numeric values from the detached Frankie 1 forecast payload.

Regression coverage is in `test_forecast_adapter_numbers.py`.

This change is confined to the Trader Frankie descendant package and does not modify Frankie 1 or any frozen parent file.
