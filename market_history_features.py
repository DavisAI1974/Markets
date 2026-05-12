"""
market_history_features.py — external history loaders/alignment helpers.

These utilities bridge the live/backend JSONL histories into the offline
chunk-based feature pipeline so tier search and the Phase 1.5 multi-feature
scan can consume funding/OI context when historical backfill exists.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from bisect import bisect_right

import numpy as np


_VENUE_ALIASES = {
    "bb": "Bybit",
    "bybit": "Bybit",
    "binance": "Binance",
    "bn": "Binance",
}

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
_DATA_BRANCH_FILES = (
    "backend_funding_history.jsonl",
    "backend_oi_history.jsonl",
)
_SYNC_ATTEMPTED = False


def _norm_venue(venue: str | None) -> str:
    if not venue:
        return ""
    key = str(venue).strip().lower()
    return _VENUE_ALIASES.get(key, str(venue).strip())


def _chunk_start_ts(chunk) -> float:
    bars = getattr(chunk, "bars", None) or []
    if not bars:
        return 0.0
    try:
        return float(bars[0].ts)
    except Exception:
        return 0.0


def _align_series_to_chunks(chunks: list,
                            times: list[float],
                            values: list[float],
                            max_age_sec: float | None) -> np.ndarray:
    """Piecewise-constant alignment: latest observation at or before chunk ts."""
    out = np.full(len(chunks), np.nan, dtype=float)
    if not times or not values:
        return out
    for i, chunk in enumerate(chunks):
        ts = _chunk_start_ts(chunk)
        if ts <= 0:
            continue
        idx = bisect_right(times, ts) - 1
        if idx < 0:
            continue
        obs_ts = times[idx]
        if max_age_sec is not None and (ts - obs_ts) > max_age_sec:
            continue
        out[i] = float(values[idx])
    return out


def _read_jsonl(path: str) -> list[dict]:
    rows: list[dict] = []
    if not path or not os.path.exists(path):
        return rows
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except Exception:
        return []
    return rows


def _history_candidate_paths(path: str | None) -> list[str]:
    raw = str(path or "").strip()
    basename = os.path.basename(raw) if raw else ""
    candidates: list[str] = []
    if raw:
        candidates.append(raw if os.path.isabs(raw) else os.path.join(_REPO_ROOT, raw))
    if basename:
        candidates.append(os.path.join(_REPO_ROOT, basename))
        candidates.append(os.path.join(_REPO_ROOT, "data", "perp-history", basename))
    seen: set[str] = set()
    out: list[str] = []
    for cand in candidates:
        norm = os.path.normcase(os.path.abspath(cand))
        if norm in seen:
            continue
        seen.add(norm)
        out.append(cand)
    return out


def _read_jsonl_with_fallback(path: str | None) -> tuple[list[dict], str]:
    last_candidate = str(path or "")
    for cand in _history_candidate_paths(path):
        last_candidate = cand
        rows = _read_jsonl(cand)
        if rows:
            return rows, cand
    return [], last_candidate


def _line_count(path: str) -> int:
    if not path or not os.path.exists(path):
        return 0
    try:
        with open(path) as fh:
            return sum(1 for line in fh if line.strip())
    except Exception:
        return 0


def sync_history_from_data_branch(
    *,
    output_dir: str | None = None,
    fetch_remote: bool = False,
    remote: str = "origin",
) -> dict[str, dict]:
    if fetch_remote:
        try:
            subprocess.run(
                ["git", "-C", _REPO_ROOT, "fetch", remote, "data/perp-history"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    branch_refs = (
        f"{remote}/data/perp-history",
        "refs/remotes/origin/data/perp-history",
        "data/perp-history",
    )
    outdir = output_dir or _REPO_ROOT
    os.makedirs(outdir, exist_ok=True)
    synced: dict[str, dict] = {}
    for filename in _DATA_BRANCH_FILES:
        local_path = os.path.join(outdir, filename)
        local_lines = _line_count(local_path)
        best_blob: str | None = None
        best_ref = ""
        best_lines = local_lines
        for ref in branch_refs:
            try:
                proc = subprocess.run(
                    ["git", "-C", _REPO_ROOT, "show", f"{ref}:{filename}"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except Exception:
                continue
            if proc.returncode != 0 or not proc.stdout.strip():
                continue
            line_count = sum(1 for line in proc.stdout.splitlines() if line.strip())
            if line_count <= best_lines:
                continue
            best_blob = proc.stdout
            best_ref = ref
            best_lines = line_count
        if best_blob is None:
            continue
        with open(local_path, "w", newline="") as fh:
            fh.write(best_blob)
        synced[filename] = {
            "path": local_path,
            "source_ref": best_ref,
            "lines": best_lines,
            "replaced_lines": local_lines,
        }
    return synced


def ensure_local_history_depth(
    *,
    funding_history_path: str | None = "backend_funding_history.jsonl",
    oi_history_path: str | None = "backend_oi_history.jsonl",
) -> dict[str, dict]:
    global _SYNC_ATTEMPTED
    if _SYNC_ATTEMPTED:
        return {}
    _SYNC_ATTEMPTED = True

    funding_target = next(iter(_history_candidate_paths(funding_history_path)), "")
    oi_target = next(iter(_history_candidate_paths(oi_history_path)), "")
    funding_need = (
        os.path.basename(funding_target) in _DATA_BRANCH_FILES
        and _line_count(funding_target) < 8
    )
    oi_need = (
        os.path.basename(oi_target) in _DATA_BRANCH_FILES
        and _line_count(oi_target) < 16
    )
    if not (funding_need or oi_need):
        return {}
    return sync_history_from_data_branch(output_dir=_REPO_ROOT, fetch_remote=False)


def _funding_series(path: str,
                    asset: str,
                    venue: str) -> tuple[list[float], list[float], str]:
    rows, used_path = _read_jsonl_with_fallback(path)
    if not rows:
        return [], [], f"no historical funding backfill at {used_path or path}"
    venue = _norm_venue(venue)
    filtered = []
    for row in rows:
        if str(row.get("asset", "")).upper() != str(asset).upper():
            continue
        if _norm_venue(row.get("venue")) != venue:
            continue
        rate = row.get("rate")
        obs_ts = row.get("ts_utc")
        try:
            rate_f = float(rate)
            ts_f = float(obs_ts)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(rate_f) and math.isfinite(ts_f)):
            continue
        filtered.append((ts_f, rate_f))
    if len(filtered) < 8:
        return [], [], (f"funding history too thin for {asset}/{venue}: "
                        f"{len(filtered)} rows")
    filtered.sort(key=lambda x: x[0])
    rates = np.asarray([row[1] for row in filtered], dtype=float)
    mu = float(np.mean(rates))
    sd = float(np.std(rates))
    if sd < 1e-12:
        return [], [], f"funding history degenerate for {asset}/{venue}"
    times = [float(row[0]) for row in filtered]
    zvals = [float((row[1] - mu) / sd) for row in filtered]
    return times, zvals, ""


def _oi_series(path: str,
               asset: str,
               venue: str) -> tuple[list[float], list[float], str]:
    rows, used_path = _read_jsonl_with_fallback(path)
    if not rows:
        return [], [], f"no historical OI backfill at {used_path or path}"
    venue = _norm_venue(venue)
    filtered = []
    for row in rows:
        if str(row.get("asset", "")).upper() != str(asset).upper():
            continue
        if _norm_venue(row.get("venue")) != venue:
            continue
        oi = row.get("oi")
        obs_ts = row.get("ts_utc")
        try:
            oi_f = float(oi)
            ts_f = float(obs_ts)
        except (TypeError, ValueError):
            continue
        if oi_f <= 0 or not (math.isfinite(oi_f) and math.isfinite(ts_f)):
            continue
        filtered.append((ts_f, oi_f))
    if len(filtered) < 16:
        return [], [], f"OI history too thin for {asset}/{venue}: {len(filtered)} rows"
    filtered.sort(key=lambda x: x[0])

    times: list[float] = []
    deltas: list[float] = []
    for i in range(1, len(filtered)):
        prev_ts, prev_oi = filtered[i - 1]
        cur_ts, cur_oi = filtered[i]
        if prev_oi <= 0:
            continue
        delta = (cur_oi - prev_oi) / prev_oi
        if not math.isfinite(delta):
            continue
        times.append(float(cur_ts))
        deltas.append(float(delta))
    if len(deltas) < 12:
        return [], [], (f"OI delta history too thin for {asset}/{venue}: "
                        f"{len(deltas)} rows")
    arr = np.asarray(deltas, dtype=float)
    mu = float(np.mean(arr))
    sd = float(np.std(arr))
    if sd < 1e-12:
        return [], [], f"OI delta history degenerate for {asset}/{venue}"
    zvals = [float((delta - mu) / sd) for delta in deltas]
    return times, zvals, ""


def precompute_external_feature_values(
    chunks: list,
    asset: str,
    perp_history_venue: str | None,
    funding_history_path: str | None = "backend_funding_history.jsonl",
    oi_history_path: str | None = "backend_oi_history.jsonl",
) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Return ({feature -> aligned values}, {feature -> status})."""
    values: dict[str, np.ndarray] = {}
    status: dict[str, str] = {}

    ensure_local_history_depth(
        funding_history_path=funding_history_path,
        oi_history_path=oi_history_path,
    )

    if not perp_history_venue:
        status["funding_rate_z"] = "no perp history venue configured"
        status["oi_delta_z"] = "no perp history venue configured"
        return values, status

    fund_ts, fund_z, fund_status = _funding_series(
        funding_history_path or "", asset, perp_history_venue)
    if fund_status:
        status["funding_rate_z"] = fund_status
    else:
        aligned = _align_series_to_chunks(
            chunks, fund_ts, fund_z, max_age_sec=16 * 60 * 60)
        if np.any(np.isfinite(aligned)):
            values["funding_rate_z"] = aligned
            status["funding_rate_z"] = ""
        else:
            status["funding_rate_z"] = (
                f"funding history present for {asset}/{_norm_venue(perp_history_venue)} "
                "but no observations align to these chunk timestamps"
            )

    oi_ts, oi_z, oi_status = _oi_series(
        oi_history_path or "", asset, perp_history_venue)
    if oi_status:
        status["oi_delta_z"] = oi_status
    else:
        aligned = _align_series_to_chunks(
            chunks, oi_ts, oi_z, max_age_sec=6 * 60 * 60)
        if np.any(np.isfinite(aligned)):
            values["oi_delta_z"] = aligned
            status["oi_delta_z"] = ""
        else:
            status["oi_delta_z"] = (
                f"OI history present for {asset}/{_norm_venue(perp_history_venue)} "
                "but no observations align to these chunk timestamps"
            )

    return values, status
