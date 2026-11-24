"""Where the checks of the agent program find real records.

No made-up data: every check reads records saved in a markets-data checkout (set MARKETS_DATA or keep
the checkout beside Markets). Without one the checks are skipped with the reason, never faked.
Writes made by a check go to a scratch folder, never into markets-data.
"""

from __future__ import annotations

import pytest

from tools.kgraph.store import markets_data_root

WORK = "tasks/family-research-20261022/research-union-current"
PAPER = f"{WORK}/paper-trading-20261123"


def data_root():
    try:
        root = markets_data_root()
    except FileNotFoundError as e:
        pytest.skip(f"no markets-data checkout: {e}")
    if not (root / PAPER / "agent-runs.jsonl").exists():
        pytest.skip("this markets-data checkout has no paper-trading-20261123/agent-runs.jsonl (wrong branch)")
    return root
