"""odcore/quiet_registry.py — per-cell QuietFloor coefficient store for production wiring (S44 prep).

The QuietFloor gate is validated and leakage-safe, but going live (NEXT #5) needs the per-cell fitted
coefficients (phi, c, sigma) + the operating point (K, k) in a durable place the hot path can read.
This is that store: a small JSON registry keyed by cell (asset_venue), plus a factory that hands the
live gate an `IncrementalQuietGate` for a cell. Flipping the gate on in production then becomes
config-only — no refit in the hot path.

Leakage note: the stored coefficients are fit OFFLINE on each cell's TRAIN quiet cells
(`odcore.quiet_floor.fit`); apply is causal. Re-fit and re-write per cell as more book accrues.

This module does NOT change any live behavior on its own — it is read by the emit path only once a
cell is explicitly enabled there (NEXT #5).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from .incremental import IncrementalQuietGate

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "quiet_floor_registry.json")


@dataclass
class CellGateParams:
    cell: str
    phi: float
    c: float
    sigma: float
    K: int                 # depth levels for the imbalance LEVEL (locked: 10, see _gate_param_sweep)
    k: float               # gate threshold in sigma (locked: 1.5)
    r2_quiet: float = 0.0
    n_quiet: int = 0
    hours: float = 0.0
    source: str = ""       # provenance (e.g. data branch / extract sha)


def _read(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save(params: CellGateParams, path: str = DEFAULT_PATH) -> None:
    """Upsert one cell's gate parameters into the registry."""
    reg = _read(path)
    reg[params.cell] = asdict(params)
    with open(path, "w") as f:
        json.dump(reg, f, indent=2, sort_keys=True)


def load(cell: str, path: str = DEFAULT_PATH) -> CellGateParams | None:
    rec = _read(path).get(cell)
    return CellGateParams(**rec) if rec else None


def all_cells(path: str = DEFAULT_PATH) -> list[str]:
    return sorted(_read(path).keys())


def get_gate(cell: str, k: float | None = None, path: str = DEFAULT_PATH) -> IncrementalQuietGate | None:
    """Build a live causal `IncrementalQuietGate` for a cell from the registry, or None if absent.

    Pass k to override the stored gate threshold (else the cell's stored k is used)."""
    p = load(cell, path)
    if p is None:
        return None
    return IncrementalQuietGate(phi=p.phi, c=p.c, sigma=p.sigma, k=k if k is not None else p.k)
