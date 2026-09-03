"""Regression gate for the F-35 supersession stamps on frozen records."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RECORD_DIR = ROOT / "research/kalshi/frankie_raw_mbo_benchmark"
STAMP_MARKER = "<!-- BEGIN F-35 SUPERSESSION STAMP -->"
STAMP_DATE = "2026-09-03"

SUPERSEDED_ASSERTIONS = {
    "FRANKIE_FEED_RECORD_SUNDAY_33630348943_20260903.md": (
        "`raw_actions` is `ABSENT`",
        "`native_acmrtfn_messages`, `order_lifecycle_adds`, "
        "`order_lifecycle_cancels`, and `order_lifecycle_modifies` are "
        "`RECEIPTED_CARRIER_ABSENT`",
    ),
    "LAYER_CROSSWALK_SUNDAY_33630348943_RENDER_20260902.md": (
        "`raw_actions[]` is `NOT ON THE ROW`",
        "`native_acmrtfn_messages`, `order_lifecycle_adds`, "
        "`order_lifecycle_cancels`, and `order_lifecycle_modifies` are "
        "`PRODUCED_NOT_DELIVERED`",
    ),
    "LAYER_CROSSWALK_SUNDAY_33630348943_FED_RENDER_20260903.md": (
        "`raw_actions[]` is `NOT ON THE ROW`",
        "`native_acmrtfn_messages`, `order_lifecycle_adds`, "
        "`order_lifecycle_cancels`, and `order_lifecycle_modifies` are "
        "`RECEIPTED_CARRIER_ABSENT`",
    ),
    "LAYER_CROSSWALK_FIXTURE_RENDER_20260902.md": (
        "`raw_actions[]` is `NOT ON THE ROW`",
        "`native_acmrtfn_messages`, `order_lifecycle_adds`, "
        "`order_lifecycle_cancels`, and `order_lifecycle_modifies` are "
        "`RECEIPTED_CARRIER_ABSENT`",
    ),
}


def test_frozen_records_keep_one_immediate_supersession_stamp_and_registry_policy() -> None:
    paths = []
    for name, assertions in SUPERSEDED_ASSERTIONS.items():
        path = RECORD_DIR / name
        paths.append(path.relative_to(ROOT).as_posix())
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        assert lines[0].startswith("# ")
        assert lines[1] == ""
        assert lines[2] == STAMP_MARKER
        assert text.count(STAMP_MARKER) == 1
        normalized = " ".join(
            line.removeprefix("> ").strip() for line in text.splitlines()
        )
        assert STAMP_DATE in text
        assert "`e4d576f`" in text
        assert "`9f984bf`" in text
        assert assertions[0] in normalized
        assert assertions[1] in normalized
        assert (
            "This is a dated record of what an earlier run delivered and is "
            "deliberately not rewritten."
        ) in normalized

    registry = json.loads(
        (ROOT / "research/kalshi/store/documents.json").read_text(encoding="utf-8")
    )
    policy = registry["record_supersession_stamp"]
    assert policy["marker"] == STAMP_MARKER
    assert policy["placement"] == "immediately under the document title"
    assert policy["required_fields"] == [
        "date",
        "behaviour-changing commits",
        "document-specific superseded assertions",
        "dated-record non-rewrite sentence",
    ]
    assert sorted(policy["applies_to"]) == sorted(paths)
