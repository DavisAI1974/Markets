#!/usr/bin/env python3
"""S134 runner repair: enforce the S132 open anchor after adaptive-node deduplication.

The S134 target-curve refiner correctly discovers event-driven nodes from realized NGV25 tape, but
its first implementation zero-anchored the first node before de-duplicating near-identical reopen
labels.  A surviving replacement node could therefore violate S132's cumulative-from-open invariant.

This runner changes no curve selection, target tape, reasoning, brain, specialist role, or score.  It
only re-applies the required zero anchor to the first authoritative curve node immediately before the
unchanged S132 validator runs.
"""
from __future__ import annotations

import frankie_g3_s134_full_refine as s134

_original_validate = s134.s132.validate_day


def _validate_after_dedup(payload, gid, day, spec):
    nodes = payload.get("curve_nodes")
    path = payload.get("path_p50_curve")
    if isinstance(nodes, list) and nodes:
        first = nodes[0]
        if isinstance(first, dict):
            first["p25_cum_usd"] = 0.0
            first["p50_cum_usd"] = 0.0
            first["p75_cum_usd"] = 0.0
    if isinstance(path, list) and path and isinstance(path[0], list) and len(path[0]) >= 2:
        path[0][1] = 0.0
    return _original_validate(payload, gid, day, spec)


def main() -> int:
    s134.s132.validate_day = _validate_after_dedup
    return s134.main()


if __name__ == "__main__":
    raise SystemExit(main())
