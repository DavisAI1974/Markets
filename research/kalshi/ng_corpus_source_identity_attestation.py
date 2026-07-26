#!/usr/bin/env python3
"""Public entrypoint for source-native corpus identity attestation.

The implementation remains ordinary reviewable Python in
``ng_corpus_source_identity_attestation_impl.py``. This entrypoint installs one
Databento enum compatibility rule before re-exporting that implementation:
prefer an enum's symbolic ``name`` over its numeric ``value``. Databento schema
enums expose numeric wire values, while corpus validation must compare semantic
names such as ``TRADES`` and ``MBO``.
"""
from __future__ import annotations

from typing import Any

import ng_corpus_source_identity_attestation_impl as _impl


def _enum_text(value: Any) -> str:
    """Normalize enum-like values without mistaking numeric wire values for names."""
    name = getattr(value, "name", None)
    if name not in (None, ""):
        value = name
    else:
        candidate = getattr(value, "value", None)
        if candidate not in (None, ""):
            value = candidate
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="replace")
    return str(value or "").strip().lower().replace("_", "-")


# The implementation's metadata and symbology checks resolve this global at call
# time, so patching it here applies the compatibility rule throughout the module.
_impl._enum_text = _enum_text

for _name in dir(_impl):
    if _name.startswith("__") or _name == "_enum_text":
        continue
    globals()[_name] = getattr(_impl, _name)

globals()["_enum_text"] = _enum_text


if __name__ == "__main__":
    raise SystemExit(main())
