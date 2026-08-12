#!/usr/bin/env python3
"""Lossless transmission compaction for the S120 Frankie canary.

This is intentionally narrower than Nova-Optimizer's generic NovaCompressor.
Frankie's canary packet contains canonical field names and 90 play bodies whose
keys must not be shortened, renamed, truncated, selected away, or semantically
rewritten.  The safest first reduction is therefore JSON lexical compaction:
remove representation-only whitespace while preserving the exact JSON object.

The Nova-Optimizer project remains the provenance for the token-reduction idea;
its MCP tool consolidation path is not applicable to this canary because the
Frankie S118/S120 backend is explicitly tool-less.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


class PacketCompactionError(RuntimeError):
    pass


def compact_packet_json(packet: Mapping[str, Any]) -> str:
    """Serialize a Frankie packet with no semantic transformation.

    Keys and values are untouched.  Only optional JSON whitespace is removed.
    sort_keys matches the legacy canary serializer's deterministic ordering.
    """
    text = json.dumps(dict(packet), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    decoded = json.loads(text)
    if decoded != dict(packet):
        raise PacketCompactionError("lossless packet round-trip check failed")
    return text


def pretty_packet_json(packet: Mapping[str, Any]) -> str:
    """Legacy S118/S120 transmission form, for before/after measurement only."""
    return json.dumps(dict(packet), indent=2, sort_keys=True, ensure_ascii=False)


def compaction_stats(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return measured character/byte savings without estimating model tokens."""
    before = pretty_packet_json(packet)
    after = compact_packet_json(packet)
    before_bytes = len(before.encode("utf-8"))
    after_bytes = len(after.encode("utf-8"))
    saved = before_bytes - after_bytes
    pct = (100.0 * saved / before_bytes) if before_bytes else 0.0
    return {
        "mode": "lossless_json_whitespace_only",
        "before_bytes": before_bytes,
        "after_bytes": after_bytes,
        "bytes_saved": saved,
        "savings_percent": round(pct, 3),
        "semantic_round_trip_equal": json.loads(after) == dict(packet),
    }


def assert_frankie_invariants(original: Mapping[str, Any], compact_text: str) -> dict[str, Any]:
    """Fail closed if compaction changes the canary's full-brain invariants."""
    decoded = json.loads(compact_text)
    if decoded != dict(original):
        raise PacketCompactionError("compacted packet is not structurally identical to original")

    brain = decoded.get("brain_view_served")
    if not isinstance(brain, dict):
        raise PacketCompactionError("brain_view_served missing after compaction")
    plays = brain.get("plays")
    if not isinstance(plays, dict):
        raise PacketCompactionError("full play map missing after compaction")
    serving = brain.get("_frankie_serving")
    if not isinstance(serving, dict):
        raise PacketCompactionError("serving telemetry missing after compaction")

    canonical = int(serving.get("canonical_plays_total", -1))
    served = int(serving.get("full_plays_served", -1))
    if canonical != 90 or served != 90 or len(plays) != 90:
        raise PacketCompactionError(
            f"full-brain invariant failed after compaction: canonical={canonical} served={served} bodies={len(plays)}"
        )
    if "play_index" not in brain:
        raise PacketCompactionError("play_index missing after compaction")
    if decoded.get("realized_outcome_in_packet") is not False:
        raise PacketCompactionError("realized_outcome_in_packet invariant failed")

    return {
        "canonical_plays_total": canonical,
        "full_play_bodies_served": served,
        "play_index_present": True,
        "realized_outcome_in_packet": False,
        "semantic_round_trip_equal": True,
    }
