"""Read-only adapter for research/kalshi/SIGNALS_IN_USE.json.

The registry says which leaves are both served to a blind specialist and referenced by at
least one brain play. This adapter joins those definitions to one causal decision_state
without changing the signal core. Missing stays None; fan-out blocks are expanded from the
actual state rather than from a hard-coded BA or region list.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from . import paths

SIGNALS_PATH = os.path.join(paths.KALSHI_RESEARCH, "SIGNALS_IN_USE.json")
_TOKEN = re.compile(r"([^\[\]]+)|\[(\d+)\]")
_cache: dict[str, Any] = {}


def _load() -> dict:
    mtime = os.path.getmtime(SIGNALS_PATH)
    if _cache.get("mtime") != mtime:
        with open(SIGNALS_PATH, encoding="utf-8") as fh:
            _cache["data"] = json.load(fh)
        _cache["mtime"] = mtime
    return _cache["data"]


def _parts(path: str) -> list[str | int]:
    out: list[str | int] = []
    for raw in path.split("."):
        for name, idx in _TOKEN.findall(raw):
            out.append(int(idx) if idx else name)
    return out


def resolve(root: Any, path: str) -> Any:
    cur = root
    for part in _parts(path):
        if isinstance(part, int):
            if not isinstance(cur, list) or part >= len(cur):
                return None
            cur = cur[part]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
    return cur


def _fanout_paths(state: dict, example_path: str) -> list[str]:
    bits = example_path.split(".")
    for marker in ("bas", "regions"):
        if marker not in bits:
            continue
        idx = bits.index(marker)
        parent_path = ".".join(bits[: idx + 1])
        parent = resolve(state, parent_path)
        if not isinstance(parent, dict):
            return [example_path]
        suffix = ".".join(bits[idx + 2 :])
        prefix = ".".join(bits[: idx + 1])
        return [f"{prefix}.{key}.{suffix}" if suffix else f"{prefix}.{key}"
                for key in sorted(parent)]
    return [example_path]


def snapshot(day: str, decision_state: dict) -> dict:
    registry = _load()
    state = decision_state.get("state", {}) if isinstance(decision_state, dict) else {}
    blocks_out: dict[str, list] = {}
    flat: list[dict] = []
    resolved_definitions = 0
    resolved_instances = 0
    total_instances = 0

    for block, definitions in registry.get("blocks", {}).items():
        block_rows = []
        for item in definitions:
            example_path = item.get("example_path")
            if not example_path:
                continue
            paths_for_item = _fanout_paths(state, example_path)
            values = []
            for concrete_path in paths_for_item:
                value = resolve(state, concrete_path)
                values.append({"path": concrete_path, "value": value,
                               "available": value is not None})
                total_instances += 1
                if value is not None:
                    resolved_instances += 1
            n_resolved = sum(1 for row in values if row["available"])
            if n_resolved:
                resolved_definitions += 1
            status = "resolved" if n_resolved == len(values) else (
                "partial" if n_resolved else "awaiting")
            row = {
                "block": block,
                "field": item.get("field"),
                "example_path": example_path,
                "brain_mentions": item.get("brain_mentions", 0),
                "declared_repeats": item.get("repeats"),
                "status": status,
                "resolved_count": n_resolved,
                "instance_count": len(values),
                "values": values,
            }
            block_rows.append(row)
            flat.append(row)
        blocks_out[block] = block_rows

    flat.sort(key=lambda row: (-int(row.get("brain_mentions") or 0), row["example_path"]))
    return {
        "available": True,
        "day": day,
        "source": "research/kalshi/SIGNALS_IN_USE.json",
        "note": registry.get("note"),
        "fanout": registry.get("fanout", {}),
        "unique_signal_count": registry.get("unique_signal_count", len(flat)),
        "definition_count": len(flat),
        "resolved_definition_count": resolved_definitions,
        "instance_count": total_instances,
        "resolved_instance_count": resolved_instances,
        "blocks": blocks_out,
        "signals": flat,
        "provenance": "real registry definitions joined to the selected as-of decision_state",
    }
