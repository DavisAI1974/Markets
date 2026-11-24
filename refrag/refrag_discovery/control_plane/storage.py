from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from refrag_discovery.paths import ARTIFACTS_DIR, LINEAGE_DIR


# Arch doc §3.1 routes lineage state to ``registry/lineage/`` because the
# lineage graph is part of the registry the rest of the system queries via
# ``operator_query``. All other control-plane state kinds (benchmarks,
# lifecycle, optimizations, exploration, meta_learner) remain under
# ``artifacts/control_plane/<kind>/`` since the arch doc does not name them
# under registry/. A caller supplying ``artifacts_dir=`` (e.g. per-scenario
# benchmark runs) still gets a sandboxed copy at
# ``<artifacts_dir>/control_plane/<kind>/<operator_id>.json`` regardless of
# kind, preserving test isolation.
REGISTRY_KINDS: frozenset[str] = frozenset({"lineage"})


def control_plane_dir(artifacts_dir: Path | None = None) -> Path:
    path = (artifacts_dir or ARTIFACTS_DIR) / "control_plane"
    path.mkdir(parents=True, exist_ok=True)
    return path


def operator_state_path(kind: str, operator_id: str, artifacts_dir: Path | None = None) -> Path:
    if artifacts_dir is None and kind in REGISTRY_KINDS:
        path = LINEAGE_DIR if kind == "lineage" else None
        if path is None:  # defensive: future kinds added to REGISTRY_KINDS need a branch
            raise NotImplementedError(f"REGISTRY_KINDS contains {kind!r} but no path is wired")
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{operator_id}.json"
    path = control_plane_dir(artifacts_dir) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{operator_id}.json"


def suite_state_path(kind: str, suite_id: str, artifacts_dir: Path | None = None) -> Path:
    path = control_plane_dir(artifacts_dir) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{suite_id}.json"


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return dict(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        invalid_path = path.with_suffix(path.suffix + ".invalid")
        if invalid_path.exists():
            invalid_path.unlink()
        path.replace(invalid_path)
        return dict(default)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    # Fix E: atomic write via tempfile + os.replace. Mirrors the orchestrator's
    # _save_accumulated_evidence_graph pattern. os.replace is atomic on
    # Windows, so a kill mid-write leaves the original file intact rather
    # than corrupting it and triggering the load_json quarantine that
    # silently destroys state.
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    # Short prefix avoids MAX_PATH=260 on Windows for deeply nested paths.
    fd, temp_name = tempfile.mkstemp(prefix=".tmp_", suffix="", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)
        # Windows: os.replace raises PermissionError (WinError 5) when the target
        # is transiently locked by a CONCURRENT writer. Parallel discovery workers
        # share control-plane files (lifecycle/benchmark), so retry briefly with
        # backoff instead of crashing the whole pipeline run before discoveries
        # are written. os.replace stays atomic; last-writer-wins on shared state.
        for _attempt in range(40):
            try:
                os.replace(temp_name, path)
                break
            except PermissionError:
                time.sleep(0.05)
        else:
            os.replace(temp_name, path)  # exhausted retries: do it once more, let it raise
    except Exception:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
