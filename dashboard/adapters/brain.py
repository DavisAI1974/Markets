"""Brain adapter - read-only view of research/kalshi/knowledge/ng_brain.json.

Doctrine carried into every response (TWO_COACH_SPEC / DASHBOARD_HANDOFF rule 4):
- every confidence keeps its provenance (status, forward_evidence, requires, scope);
- one voice per target: plays are grouped by target, but the dashboard NEVER elects an
  owning play - that election is the signal core's emit, which does not exist as a feed
  yet. Until it does, per-target groups are labeled inventory, not calls.
"""
from __future__ import annotations

import json
import os

from . import paths


def _mtime() -> float:
    return os.path.getmtime(paths.BRAIN_PATH)


_cache: dict = {}


def load() -> dict:
    if _cache.get("mtime") != _mtime():
        _cache["data"] = json.load(open(paths.BRAIN_PATH))
        _cache["mtime"] = _mtime()
    return _cache["data"]


def summary() -> dict:
    b = load()
    meta = b.get("meta", {})
    plays = b.get("plays", [])
    by_target: dict[str, list] = {}
    for p in plays:
        by_target.setdefault(p.get("target", "unspecified"), []).append({
            "id": p.get("id"),
            "confidence": p.get("confidence"),
            "status": p.get("status"),
            "trigger": p.get("trigger"),
            "read": p.get("read"),
            "requires": p.get("requires"),
            "scope": p.get("scope"),
            "forward_evidence": p.get("forward_evidence"),
        })
    doctrine = b.get("doctrine_tier3", {})
    return {
        "version": meta.get("version"),
        "meta": meta,
        "n_plays": len(plays),
        "targets": sorted(by_target),
        "plays_by_target": by_target,
        "doctrine_keys": sorted(doctrine) if isinstance(doctrine, dict) else None,
        "doctrine_tier3": doctrine,
        "open_frontier": b.get("open_frontier"),
        "provenance_note": ("plays listed as INVENTORY grouped by target; the owning-play "
                            "election is the signal core's emit (TWO_COACH_SPEC sec 1) and "
                            "is not produced by this dashboard"),
    }
