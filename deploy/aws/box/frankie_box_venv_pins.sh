#!/usr/bin/env bash
# Hold the box venv to the codec's exact DBN pin. granite_context_stacked._wire reconstructs DBN wire bytes with
# databento-dbn 0.62.0 and refuses any other version; the stage script asked for that pin beside an UNPINNED databento
# client, and the client (0.86.0) dragged the SDK to 0.69.0 (measured 2026-09-21, box run 35596609957), which is why
# the reading render's L7 (derivable packet-hash vectors) never fired. databento 0.81.0 is the client release whose
# requirement is databento-dbn>=0.62.0,<0.63.0 (PyPI metadata). Idempotent: prints the versions, repairs only when the
# SDK differs from the pin, prints them again. Touches the venv only; nothing under session/ or data/.
set -u
ROOT=/opt/frankie-box; PY="$ROOT/venv/bin/python"
[ -x "$PY" ] || { echo "venv not staged"; exit 2; }
before=$("$PY" -c "from importlib.metadata import version; print(version('databento-dbn'))" 2>/dev/null || echo absent)
echo "databento-dbn before: $before"; "$ROOT/venv/bin/pip" freeze 2>/dev/null | grep -i '^databento' | sed 's/^/  /'
if [ "$before" != "0.62.0" ]; then
  "$ROOT/venv/bin/pip" install -q "databento==0.81.0" "databento-dbn==0.62.0" cffi >"$ROOT/logs/pip-pins.log" 2>&1 || { echo "pin install failed"; tail -5 "$ROOT/logs/pip-pins.log"; exit 3; }
fi
after=$("$PY" -c "from importlib.metadata import version; print(version('databento-dbn'))" 2>/dev/null || echo absent)
echo "databento-dbn after: $after"; "$ROOT/venv/bin/pip" freeze 2>/dev/null | grep -i '^databento' | sed 's/^/  /'
"$PY" -c "import databento_dbn as d; m = d.MBOMsg; print('MBOMsg constructor', 'ok' if callable(m) else 'missing')"
[ "$after" = "0.62.0" ] || { echo "VENV_PINS_RECEIPT {\"schema\":\"FRANKIE_BOX_VENV_PINS_V1\",\"databento_dbn\":\"$after\",\"pin\":\"0.62.0\",\"held\":false}"; exit 4; }
echo "VENV_PINS_RECEIPT {\"schema\":\"FRANKIE_BOX_VENV_PINS_V1\",\"databento_dbn\":\"$after\",\"pin\":\"0.62.0\",\"held\":true,\"before\":\"$before\"}"
