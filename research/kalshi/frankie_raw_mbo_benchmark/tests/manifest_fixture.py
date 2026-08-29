"""Shared source-manifest fixture for the A-arm test suites.

Both suites previously built a manifest by hand, so a schema change broke each of them
separately and in the same way. Building it in one place means the next schema change
touches one file.
"""
from __future__ import annotations

from typing import Any, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.raw_mbo_source_manifest import (
    CAUSAL_CLOCK,
    DEFAULT_SOURCE_URI_PREFIX,
    EXPECTED_ROSTER,
    SCHEMA,
    SOURCE_KIND,
    manifest_hash,
    source_identity_hash,
)


def manifest_fixture(record_counts: Sequence[int]) -> dict[str, Any]:
    """A valid manifest over the real roster with caller-supplied record counts."""
    if len(record_counts) != len(EXPECTED_ROSTER):
        raise ValueError("record_counts must cover the whole roster")
    sources = []
    for position, ((date, role), records) in enumerate(zip(EXPECTED_ROSTER, record_counts)):
        name = f"glbx-mdp3-{date}.mbo.dbn.zst"
        sources.append(
            {
                "name": name,
                "date": date,
                "role": role,
                "roster_position": position,
                "uri": f"{DEFAULT_SOURCE_URI_PREFIX}/{name}",
                "bytes": 1000 + position + 1,
                "sha256": str(position + 1) * 64,
                "mbo_records": records,
                "download_receipt": None,
                "staged_path": f"/staged/{name}",
                "staged_sha256": None,
            }
        )
    value: dict[str, Any] = {
        "schema": SCHEMA,
        "source_kind": SOURCE_KIND,
        "causal_clock": CAUSAL_CLOCK,
        "canonical_source_rewritten": False,
        "sources": sources,
        "total_mbo_records": sum(record_counts),
        "source_identity_hash": "",
        "manifest_hash": "",
    }
    value["source_identity_hash"] = source_identity_hash(value)
    value["manifest_hash"] = manifest_hash(value)
    return value
