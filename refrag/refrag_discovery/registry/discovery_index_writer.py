"""Atomic incremental writer for ``discoveries/index.json`` (arch §4 + Rule 8).

The arch doc §4 names ``discoveries/index.json`` the "master query point" — a
single queryable record mapping ``discovery_id -> file path`` that the
contrastive encoder, evidence graph, and cross-domain transfer detector all
consult to find relevant training data. Rule 8 demands that "every validated
operator recovery is persisted immediately"; the per-domain JSON files are the
ground truth, the index is a derived cache, and the cache must keep up.

This module exposes a single function:

    append_discovery(discoveries_root, *, run_id, domain, relative_path,
                     pipeline_id="", recorded_at=None)

…that atomically read-modify-writes ``index.json`` with the new entry. It
respects the existing on-disk schema (``discoveries`` dict, ``by_domain`` list,
``by_run_id`` dict, ``summary`` aggregate) so callers swapping in this writer
do not regress the structure that ``scripts/build_discoveries_index.py``
already produces in batch mode.

Design notes
------------
* Atomic on Windows + POSIX via ``tempfile.mkstemp`` + ``os.replace`` in the
  same directory as the target — same pattern as the storage helper and the
  orchestrator's evidence-graph saver.
* Idempotent on the same ``(run_id, domain, relative_path)`` triple — a second
  call with the same values is a no-op on the on-disk bytes (modulo
  ``recorded_at`` resolution, which is monotonic).
* Concurrent writers race on the read-modify-write window. We accept
  last-writer-wins because every writer is appending an independent
  ``run_id``; the worst case is dropping one parallel run's entry, which the
  ``build_discoveries_index.py`` directory-scan can always reconstruct.
* If the existing index is malformed, the file is moved to ``index.invalid.json``
  and a fresh index is built — mirroring the orchestrator's
  ``_update_discoveries_index`` quarantine pattern.

Schema written
--------------
Keys preserved/written (top-level)::

    {
      "discoveries": { "<run_id>": {"domain","path","pipeline_id","recorded_at"}, ... },
      "by_domain":   { "<domain>": ["<run_id>", ...] },
      "by_run_id":   { "<run_id>": {"domain","path","timestamp"} },
      "duplicates":  [ ... legacy field preserved if present ],
      "summary":     { "total_discoveries": N, "by_domain": {...}, "updated_at": "..." }
    }
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _quarantine_invalid_index(index_path: Path) -> None:
    invalid = index_path.with_suffix(".invalid.json")
    if invalid.exists():
        invalid.unlink()
    index_path.replace(invalid)


def _load_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _quarantine_invalid_index(index_path)
        return {}
    if not isinstance(data, dict):
        _quarantine_invalid_index(index_path)
        return {}
    return data


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)
        os.replace(temp_name, path)
    except Exception:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def append_discovery(
    discoveries_root: Path | str,
    *,
    run_id: str,
    domain: str,
    relative_path: str,
    pipeline_id: str = "",
    recorded_at: str | None = None,
) -> Path:
    """Append one discovery to ``discoveries_root/index.json``.

    Returns the path to ``index.json``. Idempotent for the same
    ``(run_id, domain, relative_path)``. Atomic via tempfile + ``os.replace``.

    Parameters
    ----------
    discoveries_root:
        Path of the ``discoveries/`` directory (typically
        ``refrag_discovery.paths.DISCOVERIES_DIR``).
    run_id:
        The discovery_id. Becomes the key in ``discoveries`` and ``by_run_id``.
    domain:
        Domain tag for the discovery (e.g. ``markets_btc_bybit_buy``).
    relative_path:
        Path of the per-domain JSON file relative to ``discoveries_root``,
        using POSIX-style separators (``operator_discoveries/<domain>/<run_id>.json``).
    pipeline_id:
        Pipeline that produced the discovery; defaults to empty string when the
        caller doesn't have it handy (the directory-scan rebuilder fills it
        from the on-disk payload).
    recorded_at:
        ISO-8601 UTC timestamp. Defaults to the current time.
    """
    root = Path(discoveries_root)
    index_path = root / "index.json"
    ts = recorded_at or _utc_now_iso()

    index = _load_index(index_path)

    # discoveries: <run_id> -> {domain, path, pipeline_id, recorded_at}
    discoveries = dict(index.get("discoveries", {}))
    discoveries[run_id] = {
        "domain": domain,
        "path": relative_path,
        "pipeline_id": pipeline_id,
        "recorded_at": ts,
    }

    # by_domain: <domain> -> sorted unique list of run_ids
    by_domain_raw = dict(index.get("by_domain", {}))
    domain_runs = list(by_domain_raw.get(domain, []))
    if run_id not in domain_runs:
        domain_runs.append(run_id)
    by_domain_raw[domain] = sorted(set(domain_runs))

    # by_run_id: <run_id> -> {domain, path, timestamp}
    by_run_id = dict(index.get("by_run_id", {}))
    by_run_id[run_id] = {
        "domain": domain,
        "path": relative_path,
        "timestamp": ts,
    }

    # summary: aggregate (totals + per-domain count + updated_at)
    summary = {
        "total_discoveries": len(discoveries),
        "by_domain": {d: len(ids) for d, ids in sorted(by_domain_raw.items())},
        "updated_at": ts,
    }

    # Preserve legacy "duplicates" list if the rebuilder wrote one — single
    # source of truth is the directory scan, but we don't want this writer
    # silently nuking diagnostics the batch rebuild produced.
    duplicates = list(index.get("duplicates", []))

    payload: dict[str, Any] = {
        "discoveries": dict(sorted(discoveries.items())),
        "by_domain": {d: sorted(ids) for d, ids in sorted(by_domain_raw.items())},
        "by_run_id": dict(sorted(by_run_id.items())),
        "duplicates": duplicates,
        "summary": summary,
    }

    _atomic_write_json(index_path, payload)
    return index_path


__all__ = ["append_discovery"]
