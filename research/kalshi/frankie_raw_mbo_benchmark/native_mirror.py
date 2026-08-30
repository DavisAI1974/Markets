"""Section 4.4's one mechanically defined mirror key.

Contract 4.4: *"Preserve each member and its mechanically defined mirror key."*
Singular. This module is that key, so the definition has one implementation rather
than several that agree today.

The mirror is the SIDE-SWAPPED SIDE STRING, not a price reflection and not book
geometry: swap `A` for `B` through a member's side string, pair the string with its
swap, and let the lexicographically first of the pair be `CANONICAL`, so both members
of a pair resolve to the same key from either end. The definition is not new here - it
was built, ran, and emitted a `mirror-pair-index.json` with 966 mirror-ready keys as
`mirror_identity()` in `a_memory_member_first_recalculation_20260828.py`, which now
delegates here.

**This is NOT section 4.12's orientation, and the two must not be merged.** Contract
4.12 stratifies on `SAME` / `FLIP` (*"`SAME` and `FLIP` orientations never pool"*) and
that vocabulary is also the frozen chain-transition polarity carried here as
`discovery_contract()["transition_orientation_seeds"]`. `CANONICAL` / `MIRROR` is the
4.4 pair key: which half of a mirrored pair a member is. Different axis, different
section, both required.
"""
from __future__ import annotations

CANONICAL = "CANONICAL"
MIRROR = "MIRROR"
VALID_ORIENTATIONS = frozenset({CANONICAL, MIRROR})

_SIDE_SWAP = str.maketrans({"A": "B", "B": "A"})


def mirror_identity(sides: str) -> dict[str, str]:
    """Resolve a side string to its mirror pair and this string's half of it.

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
    """Just the pair half, for callers that stratify on it and need nothing else."""
    return mirror_identity(sides)["orientation"]
