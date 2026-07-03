"""odcore/platform.py — THE ONE VERSION (S55, Greg: "compile 1 version that is the best one —
the live, the paper, all sizes and whatever").

This module is the single decision layer of the trading platform. Paper trading, research
evaluation, and (when a venue is secured) live trading all run THROUGH this file — there is no
second version anywhere. The failure mode this kills: fixes validated in probe scripts that never
reach the code that trades (sized trades were flat in every S55 coarse probe; dive timing sat
unwired S53->S55), and probe verdicts rendered under different mechanics than the platform uses.

What it composes (zigzag machinery stays its own component — imported, never duplicated):
  odcore.flip_detector   WHEN — lean_series + detect_flips declare the turns (the zigzag)
  odcore.swing_maker     WHETHER/HOW — simulate_swing_maker (maker-at-the-turn, cover-grace S48,
                         dipole lean-collapse exit S55R8, entry gates, taker fill_mode S55R12)
                         + size_legs (two-factor conviction sizing S47, OOS S49)
  odcore.info_dipole     the divergence read (S36) — entry gate + per-trade descriptors (S55R1)

Entry points:
  DEPLOYED               the per-cell production config registry (fees, grace map, sizing params)
  run_cell(cfg, ...)     one deployed cell book -> sized, descriptor-carrying trade rows
  run_stream(...)        ANY flip stream (fine lean flips, coarse price zigzag, bigline-derived)
                         through the SAME executor/sizing/descriptors — research uses this, so
                         coarse verdicts are rendered by the platform's own mechanics
  append_ledger(...)     deduped JSONL ledger append (the forward record)

LIVE status: no real-money order code exists yet (deploy gated on the venue decision, S49/S50).
When it lands, it consumes run_cell decisions from THIS module — it does not reimplement them.

Standing rules enforced here: opt-in variants default OFF and bit-reproduce; variant runs route
to the sandbox ledger, never the baseline forward ledger; adoption is per cell via the forward
ledger + controls, never by flag drift.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np

from odcore.flip_detector import lean_series, detect_flips
from odcore.info_dipole import divergence
from odcore.swing_maker import simulate_swing_maker, size_legs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "paper_ledger.jsonl")
SANDBOX_LEDGER = os.path.join(ROOT, "paper_ledger_sandbox.jsonl")

# ---- deployed constants (S46-S49 lineage; grid = 0.1s book cells) ----
FLOW_W, WFLIP, REV, DIVW = 20, 600, 0.1, 600


@dataclass
class CellConfig:
    """Per-cell production config. Defaults = the deployed values; every knob's S-origin is in
    the field comment. Variants (dipole_entry/dipole_exit/fill_mode) default OFF/maker."""
    coin: str
    K: int = 1                      # book depth levels for channels (btc = 10)
    grace: int = 300                # S48 cover-grace cells (doge 600 — falling-knife tail)
    maker_fee: float = 0.0          # bps/leg; deploy requires <= 0 (S49)
    taker_fee: float = 5.0          # bps/leg
    alpha: float = 1.0              # sizing strength (S47 two-factor conviction)
    roll: int = 200                 # sizing causal rolling window (trades)
    dipole_entry: bool = False      # S55: gate flip actionability on the S36 divergence read
    dipole_exit: tuple | None = None  # S55 R8: (arm_hi, exit_lo) lean-collapse exit
    fill_mode: str = "maker"        # "maker" = deployed model; "taker" = research/bins mode
    book_path: str = ""             # default /tmp/<coin>_coinbase_book.jsonl.gz

    @property
    def cell(self):
        return f"{self.coin}_coinbase"

    @property
    def path(self):
        return self.book_path or f"/tmp/{self.coin}_coinbase_book.jsonl.gz"

    @property
    def is_variant(self):
        return bool(self.dipole_entry or self.dipole_exit or self.fill_mode != "maker")


# the production registry (S47 "bring them all in"; grace map S48; per-cell deploy rule)
DEPLOYED = [CellConfig("sol"), CellConfig("doge", grace=600), CellConfig("xrp"),
            CellConfig("eth"), CellConfig("btc", K=10)]


def _dipole_descriptors(legs, lean, piv, buy, sell, mid):
    """S55 R1 per-leg dipole read — record-only; the forward ledger accrues the per-cell OOS
    validation of each (scale, descriptor) pair. Same causal objects the sizing pass uses."""
    out = []
    for l in legs:
        ci = int(l.flip_idx); p = piv.get(ci, ci); plo = max(0, p - DIVW)
        dv = divergence(buy[plo:p + 1], sell[plo:p + 1], float(mid[p] - mid[plo])) \
            if p - plo >= 12 else None
        ce = min(int(l.close_idx), len(lean) - 1)
        out.append(dict(
            dive_depth=round(float(abs(lean[p])), 4),             # |lean@pivot| — S40/S47 size input
            lean_flip=round(float(lean[ci]) * -int(l.side), 4),   # with-OLD-leg lean at the confirm
            lean_close=round(float(lean[ce]) * int(l.side), 4),   # with-ride lean at exit (S55 R8)
            dipole_class=dv["expect"] if dv else "n/a",
            rev_conv=float(dv["reversal_conviction"]) if dv else None))
    return out


def _entry_gate(n, flips, buy, sell, mid):
    """S55: feed swing_maker's entry_gate socket with the S36 divergence read at each pivot."""
    egate = np.zeros(n, bool)
    for (c, p, _s) in flips:
        c, p = int(c), int(p); plo = max(0, p - DIVW)
        if p - plo < 12:
            continue
        dv = divergence(buy[plo:p + 1], sell[plo:p + 1], float(mid[p] - mid[plo]))
        egate[c] = bool(dv and dv["expect"] == "reversal")
    return egate


def run_stream(mid, buy, sell, flips, *, best_bid_sz=None, best_ask_sz=None,
               half_spread_bps=0.0, maker_fee=0.0, taker_fee=5.0, grace=0,
               dipole_entry=False, dipole_exit=None, fill_mode="maker",
               alpha=1.0, roll=200, quality=None, size_axis=None):
    """ANY flip stream through the platform's decision code — the single research entry point.

    flips: (confirm_idx, pivot_idx, side) tuples — fine detect_flips output OR a coarse price
    zigzag (same tuple shape). fill_mode="taker" for dump bins (no book depth; pass no sizes).
    quality/size_axis: per-leg causal arrays for size_legs; omit -> legs stay flat (size 1.0).
    Returns (SwingResult, descriptors list). Equivalence proof (S55 R12 canary): zz150 through
    this in taker mode reproduces the S54 leg tables bit-for-bit on all 5 coins.
    """
    mid = np.asarray(mid, float)
    buy = np.asarray(buy, float); sell = np.asarray(sell, float)
    z = np.zeros(len(mid))
    bb = z if best_bid_sz is None else np.asarray(best_bid_sz, float)
    ba = z if best_ask_sz is None else np.asarray(best_ask_sz, float)
    lean = lean_series(buy, sell, WFLIP)
    piv = {int(c): int(p) for (c, p, s) in flips}
    egate = _entry_gate(len(mid), flips, buy, sell, mid) if dipole_entry else None
    res = simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=half_spread_bps,
                               maker_fee_bps=maker_fee, taker_fee_bps=taker_fee,
                               cover_grace=grace, entry_gate=egate,
                               lean=lean if dipole_exit else None, lean_exit=dipole_exit,
                               fill_mode=fill_mode)
    if quality is not None and size_axis is not None and res.legs:
        size_legs(res.legs, quality, size_axis, alpha=alpha, roll=roll)
    desc = _dipole_descriptors(res.legs, lean, piv, buy, sell, mid)
    return res, desc


def run_cell(cfg: CellConfig):
    """One deployed cell book -> sized, descriptor-carrying trade rows (the ledger schema).
    This is the paper AND (future) live decision path — one implementation."""
    # local imports: the book loaders live at repo root (script-level modules)
    import sys
    for p in (ROOT, os.path.join(ROOT, "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from _liquidity_dive import build_channels, median_spread_bps
    from _birth_probe import load_book

    if not os.path.exists(cfg.path):
        return []
    raw = load_book(cfg.path)                    # parse the gzip ONCE; reuse for every consumer
    ch, g = build_channels(cfg.path, cfg.K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    sret = ch["signed_ret"]
    hs = median_spread_bps(cfg.path, raw=raw) / 2.0
    t0 = float(raw["ts"][0])                     # grid idx -> ts = t0 + idx*0.1
    vol = buy + sell; cvol = np.concatenate([[0.0], np.cumsum(vol)])
    vm = lambda t, w: (cvol[t + 1] - cvol[max(0, t + 1 - w)]) / (t + 1 - max(0, t + 1 - w))
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    piv = {int(c): int(p) for (c, p, s) in allf}
    egate = _entry_gate(len(mid), allf, buy, sell, mid) if cfg.dipole_entry else None
    res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                               maker_fee_bps=cfg.maker_fee, taker_fee_bps=cfg.taker_fee,
                               cover_grace=cfg.grace, entry_gate=egate,
                               lean=lean if cfg.dipole_exit else None, lean_exit=cfg.dipole_exit,
                               fill_mode=cfg.fill_mode)
    legs = res.legs
    # two-factor conviction SIZING (S47, OOS S49) — causal features at the flip (decision) cell
    clmx, size_score = [], []
    for l in legs:
        ci = int(l.flip_idx); p = piv.get(ci, ci); lo = max(0, ci - DIVW)
        cx = vm(ci, 60) / (vm(ci, 600) + 1e-12)
        v60 = vm(ci, 60); vlt = float(np.std(sret[max(0, ci - 120):ci + 1])) * 1e4
        rnp = abs(mid[ci] - mid[lo]) / mid[lo] * 1e4; dp = abs(lean[p])
        clmx.append(cx); size_score.append(v60 + vlt + rnp + dp)
    size_legs(legs, clmx, size_score, alpha=cfg.alpha, roll=cfg.roll)
    desc = _dipole_descriptors(legs, lean, piv, buy, sell, mid)
    mode = ("de" if cfg.dipole_entry else "") + ("dx" if cfg.dipole_exit else "")
    out = []
    for i, l in enumerate(legs):
        ts = t0 + int(l.open_idx) * 0.1
        out.append(dict(cell=cfg.cell, coin=cfg.coin, ts=round(ts, 3), side=int(l.side),
                        entry=round(float(l.open_px), 6), exit=round(float(l.close_px), 6),
                        net_bps=round(float(l.net_bps), 4), size_mult=round(l.size, 3),
                        sized_net=round(float(l.net_bps) * l.size, 4),
                        swing_bps=round(float(l.swing_bps), 3), maker_close=bool(l.close_maker),
                        grace=int(cfg.grace), lean_exit=bool(l.lean_exit), mode=mode,
                        **desc[i]))
    return out


def load_ledger(path=LEDGER):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(x) for x in f if x.strip()]


def append_ledger(rows, path=LEDGER, existing=None):
    """Deduped append by (cell, ts) — repeated runs over the rolling book window accumulate a
    genuine FORWARD record. Returns the newly-appended rows."""
    existing = load_ledger(path) if existing is None else existing
    seen = {(r["cell"], r["ts"]) for r in existing}
    new = [r for r in rows if (r["cell"], r["ts"]) not in seen]
    with open(path, "a") as f:
        for r in new:
            f.write(json.dumps(r) + "\n")
    return new
