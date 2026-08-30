"""The one mechanical mirror key. Contract 4.4 mandates exactly one, and there were three.

The mirror is the SIDE-SWAPPED SIDE STRING, not a price reflection and not a book
geometry: swap `A` for `B` through a member's side string, pair the string with its swap,
and let the lexicographically first of the pair be `CANONICAL` so both members of a pair
resolve to the same key from either end. That definition is not new here - it was built,
run, and emitted a `mirror-pair-index.json` with 966 mirror-ready keys as
`mirror_identity()` in `a_memory_member_first_recalculation_20260828.py:94-102`, which now
delegates to this module so the implementation is singular rather than merely agreed.

**`SAME` and `FLIP` are not mirror words and must not be used here.** They are TAKEN, with
published results behind them: *"`SAME` / `FLIP` refers to current exhaustion polarity
relative to the latest predecessor"*
(`CHAIN_PHASE2_MODULE_NOVELTY_FINDINGS_20260818.md:14`), frozen with committed counts of
1,546 FLIP / 1,883 SAME of 3,429 and gated in four separate files, and carried in this
package as `discovery_contract()["transition_orientation_seeds"]`. That relation is
TEMPORAL - a chain member against its predecessor. The mirror relation is CROSS-SECTIONAL -
a structure against its side-swapped counterpart. Naming both pairs the same thing is the
`_family_id` defect: it does not fail, it disagrees, and the disagreement surfaces only
after a run.
"""
from __future__ import annotations

CANONICAL = "CANONICAL"
MIRROR = "MIRROR"
VALID_ORIENTATIONS = frozenset({CANONICAL, MIRROR})

_SIDE_SWAP = str.maketrans({"A": "B", "B": "A"})


def mirror_identity(sides: str) -> dict[str, str]:
    """Resolve a side string to its mirror pair and this string's orientation within it.

    Deliberately total: a side string carrying `N` or any other character passes those
    characters through unswapped rather than raising, because an unsided or novel row is
    preserved and characterized here, never dropped (D60).
    """
    mirror = sides.translate(_SIDE_SWAP)
    pair = sorted((sides, mirror))
    return {
        "side_string": sides,
        "mirror_side_string": mirror,
        "mirror_pair_key": f"{pair[0]}|{pair[1]}",
        "orientation": CANONICAL if sides == pair[0] else MIRROR,
    }


def mirror_orientation(sides: str) -> str:
    """Just the orientation, for callers that stratify on it and need nothing else."""
    return mirror_identity(sides)["orientation"]
