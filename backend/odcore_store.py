"""
odcore_store.py — backend cache of the Operator-Discovery coupling layer.

Computes, from the REAL collector bins (realbins/, materialized from the data/* branches),
the OD quantities the S21 frontend surfaces:

  - coupling matrix     : pairwise lag-0 |cross-correlation| + structured-coupling verdict
                          across every source (cross-venue / cross-asset / orderflow).
  - lead-lag            : per asset, who-moves-first across venues (raw cross-cov over lag,
                          z vs a time-slide null) — the S19 right tool.
  - dipole signals      : per source, the algebraic chem-dipole fit (a,b,c,R2) on the
                          orderflow operator matrix + the current H_a>H_b direction.
  - strength over time  : rolling OD strength meters (biology MI-slope, chemistry residual
                          fraction) for one (asset, venue) — the coupling STRENGTH readout.
  - decoupling events   : rolling lag-0 coupling on the strongest cross-venue pair per asset,
                          with collapses flagged (the tradeable dislocation signal).

Heavy compute (windowed entropy / KSG MI) is done once on a refresh cadence and cached;
the API endpoints read the cache. Nothing here is synthetic — if a bins file is missing the
source is simply skipped (Result Discipline: report what the data supports, no fabrication).
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field, asdict

import numpy as np

from odcore.io import load_bins, align, BinSeries
from odcore.channels import materialize
from odcore.operators import windowed_operator_matrix, COL
from odcore.null_extract import analyze_coupling, coupling_strength
from odcore.dipole_predictor import fit_algebraic_dipole
from odcore.leadlag import detect_leadlag, cross_correlation
from odcore.coupling_scanner import rolling_coupling, detect_decoupling

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REALBINS = os.path.join(REPO_ROOT, "realbins")

# (asset, venue, source-stem under realbins/). Mirrors the collector outputs.
OD_SOURCES = [
    ("BTC", "Coinbase", "btc_coinbase"),
    ("BTC", "Kraken", "btc_kraken"),
    ("BTC", "Bybit-perp", "btc_bybit_perp"),
    ("ETH", "Coinbase", "eth_coinbase"),
    ("ETH", "Kraken", "eth_kraken"),
    ("ETH", "Bybit-perp", "eth_bybit_perp"),
]

# Compute knobs (kept conservative so a refresh stays well under the poll interval).
RESAMPLE_S = 60          # minute bars
WINDOW = 40
STRIDE = 10
MAX_LAG = 15             # bars (= 15 min at 60s) for the lead-lag search
ROLL_WIN = 240           # rolling-coupling window in bars (= 4h)
ROLL_STEP = 30           # rolling-coupling step in bars (= 30 min)
REFRESH_INTERVAL_S = 600  # recompute the OD layer at most this often


def _stem(asset: str, venue: str) -> str:
    return next((s for a, v, s in OD_SOURCES if a == asset and v == venue), "")


@dataclass
class CouplingCell:
    a: str                 # "BTC/Coinbase"
    b: str
    pair_kind: str         # cross_venue | cross_asset
    cc0: float             # lag-0 |cross-correlation| of log returns
    structured: bool       # OD structured-coupling verdict on the pair operator matrix
    mi_frac: float
    chem_frac: float
    n_windows: int


@dataclass
class LeadLagCell:
    a: str
    b: str
    lag_bars: int          # >0 => a leads b
    lag_seconds: int
    cc: float
    z: float               # vs time-slide null
    leader: str            # "BTC/Coinbase" | "BTC/Kraken" | "synchronous"


@dataclass
class DipoleSignal:
    asset: str
    venue: str
    a: float               # algebraic dipole H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2
    b: float
    c: float               # quadratic content = chem-dipole signature
    r2: float
    direction: int         # +1 (H_a>H_b, buy-side informative) | -1 | 0
    n_windows: int


@dataclass
class StrengthPoint:
    ts: float
    mi_slope: float
    mi_slope_r2: float
    chem_frac: float


@dataclass
class DecouplingEventOut:
    pair: str
    ts: float
    cc: float
    baseline: float
    severity: str


@dataclass
class ODSnapshot:
    coupling_matrix: list[dict] = field(default_factory=list)
    leadlag: dict[str, list[dict]] = field(default_factory=dict)   # asset -> cells
    dipole_signals: list[dict] = field(default_factory=list)
    strength: dict[str, list[dict]] = field(default_factory=dict)  # "ASSET/VENUE" -> points
    decoupling: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    computed_utc: float = 0.0
    resample_s: int = RESAMPLE_S


class CouplingStore:
    """Loads the real bins, computes the OD coupling layer, caches the snapshot."""

    def __init__(self, sources=OD_SOURCES, realbins_dir=REALBINS):
        self._sources = sources
        self._realbins = realbins_dir
        self._series: dict[tuple[str, str], BinSeries] = {}
        self.snapshot = ODSnapshot()
        self._last_refresh = 0.0
        self._lock = threading.Lock()   # prevents overlapping refreshes (compute is ~80s)

    # -- data ------------------------------------------------------------
    def _load_series(self):
        """Load + resample each available source once (cached for the process)."""
        if self._series:
            return
        for asset, venue, stem in self._sources:
            path = os.path.join(self._realbins, f"{stem}_bins.json")
            if not os.path.exists(path):
                continue
            try:
                self._series[(asset, venue)] = load_bins(path).resample(RESAMPLE_S)
            except Exception as e:
                print(f"[CouplingStore] load failed {stem}: {e}", flush=True)

    def _key(self, asset, venue) -> str:
        return f"{asset}/{venue}"

    # -- compute ---------------------------------------------------------
    def refresh(self, force: bool = False):
        now = time.time()
        if not force and (now - self._last_refresh) < REFRESH_INTERVAL_S and self.snapshot.computed_utc:
            return
        # Skip if another refresh is already running (compute is ~80s; the poll loop
        # would otherwise stack duplicate recomputes). Non-blocking.
        if not self._lock.acquire(blocking=False):
            return
        try:
            self._refresh_locked()
        finally:
            self._lock.release()

    def _refresh_locked(self):
        now = time.time()
        self._load_series()
        if not self._series:
            print("[CouplingStore] no real bins available; OD layer empty", flush=True)
            self._last_refresh = now
            return
        t0 = time.time()
        snap = ODSnapshot(resample_s=RESAMPLE_S)
        snap.sources = [{"asset": a, "venue": v, "bars": len(self._series[(a, v)])}
                        for (a, v) in self._series]
        snap.coupling_matrix = [asdict(c) for c in self._coupling_matrix()]
        snap.leadlag = {asset: [asdict(c) for c in cells]
                        for asset, cells in self._leadlag_all().items()}
        snap.dipole_signals = [asdict(d) for d in self._dipole_signals()]
        snap.strength = {k: [asdict(p) for p in pts] for k, pts in self._strength_all().items()}
        snap.decoupling = [asdict(e) for e in self._decoupling()]
        snap.computed_utc = time.time()
        self.snapshot = snap
        self._last_refresh = now
        print(f"[CouplingStore] OD layer refreshed in {time.time()-t0:.1f}s "
              f"({len(snap.coupling_matrix)} pairs, {len(snap.dipole_signals)} sources)",
              flush=True)

    def _base(self, asset: str) -> str:
        return asset

    def _coupling_matrix(self) -> list[CouplingCell]:
        keys = list(self._series)
        cells: list[CouplingCell] = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                (a_asset, a_ven), (b_asset, b_ven) = keys[i], keys[j]
                sa, sb = self._series[keys[i]], self._series[keys[j]]
                try:
                    sa, sb = align(sa, sb)
                except Exception:
                    continue
                ra, rb = sa.log_return(), sb.log_return()
                if ra.size < WINDOW * 3:
                    continue
                _, cc = cross_correlation(ra, rb, max_lag=0)
                cc0 = abs(float(cc[0]))
                # structured-coupling verdict on the cross-source return operator matrix
                M = windowed_operator_matrix(ra, rb, window=WINDOW, stride=STRIDE)
                if M.shape[0] >= 30:
                    v = analyze_coupling(M)
                    structured, mi_frac, chem_frac = v.structured, v.mi_frac, v.chem_residual_frac
                    nwin = int(M.shape[0])
                else:
                    structured, mi_frac, chem_frac, nwin = False, 0.0, 0.0, int(M.shape[0])
                kind = "cross_venue" if a_asset == b_asset else "cross_asset"
                cells.append(CouplingCell(
                    a=self._key(a_asset, a_ven), b=self._key(b_asset, b_ven),
                    pair_kind=kind, cc0=cc0, structured=structured,
                    mi_frac=mi_frac, chem_frac=chem_frac, n_windows=nwin))
        cells.sort(key=lambda c: c.cc0, reverse=True)
        return cells

    def _leadlag_all(self) -> dict[str, list[LeadLagCell]]:
        out: dict[str, list[LeadLagCell]] = {}
        by_asset: dict[str, list[tuple[str, str]]] = {}
        for (asset, venue) in self._series:
            by_asset.setdefault(asset, []).append((asset, venue))
        for asset, venues in by_asset.items():
            cells: list[LeadLagCell] = []
            for i in range(len(venues)):
                for j in range(i + 1, len(venues)):
                    sa, sb = self._series[venues[i]], self._series[venues[j]]
                    try:
                        sa, sb = align(sa, sb)
                    except Exception:
                        continue
                    ll = detect_leadlag(sa.log_return(), sb.log_return(),
                                        max_lag=MAX_LAG, n_null=200, seed=7)
                    ka, kb = self._key(*venues[i]), self._key(*venues[j])
                    leader = ka if ll.leader == "a" else (kb if ll.leader == "b" else "synchronous")
                    cells.append(LeadLagCell(
                        a=ka, b=kb, lag_bars=ll.lag, lag_seconds=ll.lag * RESAMPLE_S,
                        cc=float(ll.cc), z=float(ll.z), leader=leader))
            if cells:
                cells.sort(key=lambda c: c.z, reverse=True)
                out[asset] = cells
        return out

    def _dipole_signals(self) -> list[DipoleSignal]:
        out: list[DipoleSignal] = []
        for (asset, venue), s in self._series.items():
            a = materialize(_stem(asset, venue), "taker_buy", s)
            b = materialize(_stem(asset, venue), "taker_sell", s)
            M = windowed_operator_matrix(a, b, window=WINDOW, stride=STRIDE)
            if M.shape[0] < 30:
                continue
            fit = fit_algebraic_dipole(M)
            # current OD direction: +1 when buy-side entropy H_a exceeds sell-side H_b
            cur = 1 if M[-1, COL["H_a"]] > M[-1, COL["H_b"]] else -1
            out.append(DipoleSignal(
                asset=asset, venue=venue, a=fit.a, b=fit.b, c=fit.c, r2=fit.r2,
                direction=cur, n_windows=int(M.shape[0])))
        out.sort(key=lambda d: abs(d.c), reverse=True)
        return out

    def _strength_all(self) -> dict[str, list[StrengthPoint]]:
        """Rolling OD strength meters on each source's orderflow channel pair."""
        out: dict[str, list[StrengthPoint]] = {}
        for (asset, venue), s in self._series.items():
            a = materialize(_stem(asset, venue), "taker_buy", s)
            b = materialize(_stem(asset, venue), "taker_sell", s)
            pts: list[StrengthPoint] = []
            n = min(a.size, b.size)
            for start in range(0, n - ROLL_WIN + 1, ROLL_STEP):
                aw, bw = a[start:start + ROLL_WIN], b[start:start + ROLL_WIN]
                M = windowed_operator_matrix(aw, bw, window=WINDOW, stride=STRIDE)
                if M.shape[0] < 10:
                    continue
                st = coupling_strength(M)
                ts = float(s.ts[min(start + ROLL_WIN - 1, len(s) - 1)])
                pts.append(StrengthPoint(ts=ts, mi_slope=st.mi_slope,
                                         mi_slope_r2=st.mi_slope_r2,
                                         chem_frac=st.chem_residual_frac))
            if pts:
                out[self._key(asset, venue)] = pts
        return out

    def _decoupling(self) -> list[DecouplingEventOut]:
        """Rolling lag-0 coupling on the strongest cross-venue pair per asset; flag collapses."""
        events: list[DecouplingEventOut] = []
        by_asset: dict[str, list[tuple[str, str]]] = {}
        for (asset, venue) in self._series:
            by_asset.setdefault(asset, []).append((asset, venue))
        for asset, venues in by_asset.items():
            best = None  # (cc0, keyA, keyB, series)
            for i in range(len(venues)):
                for j in range(i + 1, len(venues)):
                    sa, sb = self._series[venues[i]], self._series[venues[j]]
                    try:
                        sa, sb = align(sa, sb)
                    except Exception:
                        continue
                    ra, rb = sa.log_return(), sb.log_return()
                    _, cc = cross_correlation(ra, rb, max_lag=0)
                    cc0 = abs(float(cc[0]))
                    if best is None or cc0 > best[0]:
                        best = (cc0, venues[i], venues[j], (ra, rb))
            if best is None:
                continue
            _, ka, kb, (ra, rb) = best
            cc_series = rolling_coupling(ra, rb, win=ROLL_WIN, step=ROLL_STEP)
            evs = detect_decoupling(cc_series, lookback=20, drop_k=2.5)
            pair = f"{self._key(*ka)} <> {self._key(*kb)}"
            sa = self._series[ka]
            for e in evs:
                bar_idx = min(e.index * ROLL_STEP + ROLL_WIN - 1, len(sa) - 1)
                events.append(DecouplingEventOut(
                    pair=pair, ts=float(sa.ts[bar_idx]), cc=e.cc,
                    baseline=e.baseline, severity=e.severity))
        events.sort(key=lambda e: e.ts, reverse=True)
        return events


# Module-level singleton used by the API server.
coupling_store = CouplingStore()
