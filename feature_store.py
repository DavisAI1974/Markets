from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


DEFAULT_ONCHAIN_STORE = Path("live_data/onchain_features.jsonl")
_ONCHAIN_MEMORY: dict[tuple[str, float], dict[str, Any]] = {}


def _feature_dict(features: Any) -> dict[str, Any]:
    if isinstance(features, dict):
        return dict(features)
    if hasattr(features, "to_dict"):
        return dict(features.to_dict())
    if is_dataclass(features):
        return asdict(features)
    raise TypeError(f"Unsupported feature payload {type(features)!r}")


def write_onchain_features(
    asset: str,
    features: Any,
    *,
    path: str | Path = DEFAULT_ONCHAIN_STORE,
    keep_memory: bool = True,
) -> dict[str, Any]:
    row = _feature_dict(features)
    row["asset"] = str(asset or row.get("asset") or "").upper()
    ts = float(row.get("ts_utc") or row.get("timestamp") or 0.0)
    row["ts_utc"] = ts
    if keep_memory:
        _ONCHAIN_MEMORY[(row["asset"], ts)] = row
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def latest_onchain_features(asset: str, *, path: str | Path = DEFAULT_ONCHAIN_STORE) -> dict[str, Any] | None:
    key_asset = str(asset or "").upper()
    candidates = [row for (a, _), row in _ONCHAIN_MEMORY.items() if a == key_asset]
    if candidates:
        return max(candidates, key=lambda r: float(r.get("ts_utc") or 0.0))
    in_path = Path(path)
    if not in_path.exists():
        return None
    latest: dict[str, Any] | None = None
    with in_path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get("asset") or "").upper() != key_asset:
                continue
            if latest is None or float(row.get("ts_utc") or 0.0) > float(latest.get("ts_utc") or 0.0):
                latest = row
    return latest
