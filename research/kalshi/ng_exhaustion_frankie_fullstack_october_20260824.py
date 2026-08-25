#!/usr/bin/env python3
"""Fresh full-stack October Frankie runner.

This module is the additive integration owner for the corrected October construction.  It does not
import or reveal Step-1 outputs.  The initial slice freezes the exact canonical raw-object roster and
full-month operating boundary; knowledge, causal-plane, helper-runtime, and launch wiring are added
through the focused contracts tested beside this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Mapping


SCHEMA = "NG_EXHAUSTION_FRANKIE_FULLSTACK_OCTOBER_V1_20260824"
EXPECTED_MODEL = "gpt-5.6-sol"
EXPECTED_MANIFEST_SHA256 = "5739bce85d9bfbbe6c59d000bc411b424d7752b98a309725161d44e6d1d3dc2e"
PREDECESSOR_SEGMENT = "20210901_20211001"
OCTOBER_SEGMENT = "20211001_20211101"
PREDECESSOR_NAME = "glbx-mdp3-20210930.mbo.dbn.zst"
TARGET_START = int(datetime(2021, 10, 1, tzinfo=timezone.utc).timestamp())
TARGET_END = int(datetime(2021, 11, 1, tzinfo=timezone.utc).timestamp())
ANSWER_WALL_MODE = "SEALED_UNTIL_PRIMARY_FREEZE"
_OBJECT_DATE = re.compile(r"glbx-mdp3-(20\d{6})\.mbo\.dbn\.zst$")


class FullStackOctoberError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceObject:
    date: str
    segment: str
    key: str
    sha256: str
    bytes: int
    bucket: str
    purpose: str


def _source_object(row: Mapping[str, Any], *, purpose: str) -> SourceObject:
    key = str(row.get("key") or "")
    match = _OBJECT_DATE.search(key)
    if match is None:
        raise FullStackOctoberError(f"canonical DBN key has no source date: {key!r}")
    sha = str(row.get("sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise FullStackOctoberError(f"canonical DBN object has invalid SHA-256: {key}")
    size = row.get("bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise FullStackOctoberError(f"canonical DBN object has invalid byte length: {key}")
    return SourceObject(
        date=match.group(1),
        segment=str(row.get("segment") or ""),
        key=key,
        sha256=sha,
        bytes=size,
        bucket=str(row.get("bucket") or ""),
        purpose=purpose,
    )


def select_october_source_roster(manifest: Mapping[str, Any]) -> tuple[SourceObject, ...]:
    """Return one lawful predecessor object followed by all 26 canonical October objects."""
    if manifest.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256:
        raise FullStackOctoberError("canonical raw-object manifest identity mismatch")
    rows = manifest.get("canonical_dbn_objects")
    if not isinstance(rows, list):
        raise FullStackOctoberError("canonical_dbn_objects must be a list")

    predecessor_rows = [
        row for row in rows
        if isinstance(row, Mapping)
        and row.get("segment") == PREDECESSOR_SEGMENT
        and str(row.get("key") or "").endswith(PREDECESSOR_NAME)
    ]
    if len(predecessor_rows) != 1:
        raise FullStackOctoberError("exact canonical predecessor bootstrap object is required")
    target_rows = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("segment") == OCTOBER_SEGMENT
    ]
    targets = sorted(
        (_source_object(row, purpose="OCTOBER_CAUSAL_STREAM") for row in target_rows),
        key=lambda item: (item.date, item.key),
    )
    if len(targets) != 26 or len({item.key for item in targets}) != 26:
        raise FullStackOctoberError("October canonical roster must contain exactly 26 unique objects")
    if targets[0].date != "20211001" or targets[-1].date != "20211031":
        raise FullStackOctoberError("October canonical roster date coverage drift")
    predecessor = _source_object(predecessor_rows[0], purpose="PREDECESSOR_BOOTSTRAP")
    return (predecessor, *targets)


@dataclass(frozen=True)
class FullStackOctoberConfig:
    run_id: str
    manifest_path: Path
    source_root: Path
    output_root: Path
    model: str = EXPECTED_MODEL
    target_start: int = TARGET_START
    target_end: int = TARGET_END
    answer_wall_mode: str = ANSWER_WALL_MODE

    def validate(self) -> "FullStackOctoberConfig":
        if not str(self.run_id or "").strip():
            raise FullStackOctoberError("run_id is required")
        if self.model != EXPECTED_MODEL:
            raise FullStackOctoberError(f"model must be exactly {EXPECTED_MODEL}")
        if (self.target_start, self.target_end) != (TARGET_START, TARGET_END):
            raise FullStackOctoberError("runner must cover the exact full October half-open interval")
        if self.answer_wall_mode != ANSWER_WALL_MODE:
            raise FullStackOctoberError("October Step-1 answer wall must remain sealed until primary freeze")
        if self.output_root.exists() and any(self.output_root.iterdir()):
            raise FullStackOctoberError("output_root must be new or empty")
        return self
