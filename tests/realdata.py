"""Real-data test helper. Tests run on the materialized data/* branch bins (realbins/).

ZERO synthetic data: ground truth for the lead-lag test comes from injecting a KNOWN lag
into a REAL market return series (real data, known shift to recover), not fabricated noise.
If realbins/ is absent (fresh checkout without the data branch), the tests skip with a
clear message rather than fall back to synthetic.
"""

from __future__ import annotations

import os

REALBINS = os.path.join(os.path.dirname(__file__), "..", "realbins")


def have(source: str) -> bool:
    return os.path.exists(os.path.join(REALBINS, f"{source}_bins.json"))


def path(source: str) -> str:
    return os.path.join(REALBINS, f"{source}_bins.json")
