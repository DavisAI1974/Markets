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

**How this relates to section 4.12's `SAME`/`FLIP` is an OPEN RULING, not settled here.**
An earlier version of this docstring asserted they were "different axes, both required".
The contract does not say that. Section 3 lists the stratifier as "side or mirror
orientation" (:65) and forbids averaging across "mirror orientations" (:71) - one axis
named two ways - while 4.12 stratifies on `SAME`/`FLIP` and speaks of "paired mirror
differences" in the same clause. So "4.12's orientation IS the mirror orientation" reads at
least as well as the split.

Nothing is pinned either way, and nothing needs to be yet: `DipoleStage.orientation` has no
producer anywhere in the tree and `mirror_signed_flow` is never looked up, so 4.12's
orientation is unfed and the question is not live. It becomes live the moment something
feeds it. Until then this module claims only 4.4's member-level pair key and makes no claim
about 4.12.
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
