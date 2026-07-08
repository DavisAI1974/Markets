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

from odcore.flip_detector import lean_series, detect_flips, retime_flips
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
    book_path: str = ""             # default /tmp/<coin>_<venue>_book.jsonl.gz
    venue: str = "coinbase"         # S56: venue is a first-class cell dimension (per-cell deploy)
    sandbox: bool = False           # sandbox cells -> SANDBOX_LEDGER (S53 rule)
    # --- Kraken flow-lean STACK (S65; used by run_kraken_cell; defaults preserve the Coinbase run_cell) ---
    side: int = +1                  # +1 forward / -1 reversed (per-coin direction)
    rev: float = REV                # per-cell zigzag reversal threshold (S65 swing-floor; default 0.10)
    eps: float | None = None        # early-arm retime eps_bps (None = base detect_flips)
    bail: float | None = None       # deep-bail depth bp (None = no exit_spec price_stop)
    improve: float = 0.0            # enticing-close concession bps (close_improve_bps)

    @property
    def cell(self):
        return f"{self.coin}_{self.venue}"

    @property
    def path(self):
        return self.book_path or f"/tmp/{self.coin}_{self.venue}_book.jsonl.gz"

    @property
    def is_variant(self):
        return bool(self.dipole_entry or self.dipole_exit or self.fill_mode != "maker")


# the production registry (S47 "bring them all in"; grace map S48; per-cell deploy rule)
DEPLOYED = [CellConfig("sol"), CellConfig("doge", grace=600), CellConfig("xrp"),
            CellConfig("eth"), CellConfig("btc", K=10)]

# SANDBOX registry — EMPTY as of S57 (Greg: strike Bybit — all references, data, and code).
# The S56 Bybit sandbox cells were removed after eligibility verification: Bybit's own
# restricted-jurisdictions policy excludes the United States, applies at the UBO level for
# entities (Business-KYC FAQ), and no US-facing intermediary offers its books (post-Falcon-Labs
# CFTC enforcement). The venue is not lawfully tradeable for us at any fee tier, so no research
# cell may live here. Next sandbox cells must be on a US-lawful venue (per-cell rule, S33).
SANDBOX = []

# KRAKEN flow-lean registry (S65) — the per-coin STACK, the single source of truth the sim consumes.
# Fee frame kr_mk0 (0bp maker). All cells: FRONT-OF-LINE fill + enticing close (improve=0.5).
# PER-COIN REV (Greg's rule: cut churn ONLY where it's NEGATIVE, keep it where POSITIVE — S65 sweep
# `_kraken_revsweep.py`): eth/btc/sol keep REV 0.10 (their fine churn is net-POSITIVE — coarsening loses
# money); DOGE coarsened to 0.30 (+8.17 vs +6.05 — its churn is NEGATIVE) and XRP to 0.13 (+16.05 vs
# +14.02 — negative churn cut). eth/btc keep early-arm (helps on book); sol/doge/xrp base.
# ⚠ BOOK-PROVISIONAL (one 30h window): the direction re-adjudication (SOL fwd, XRP fwd, DOGE fwd) + the
# coarsened DOGE/XRP REV are the SIM's current book-best; the S63 30d-TAPE deploy map (SOL reversed, XRP
# aside, DOGE fade-8h) stands for LIVE CAPITAL until a 30d-tape/Tardis confirm.
KRAKEN = [
    CellConfig("eth", venue="kraken", side=+1, rev=0.10, eps=10.0, bail=100.0, grace=300, improve=0.5),
    CellConfig("btc", venue="kraken", side=+1, rev=0.10, eps=5.0,  bail=80.0,  grace=300, improve=0.5, K=10),
    CellConfig("sol", venue="kraken", side=+1, rev=0.10, eps=None, bail=None,  grace=300, improve=0.5),
    CellConfig("doge", venue="kraken", side=+1, rev=0.30, eps=None, bail=None, grace=600, improve=0.5),
    CellConfig("xrp", venue="kraken", side=+1, rev=0.13, eps=None, bail=None,  grace=300, improve=0.5),
]


# KRAKEN candidate cells (S67) — NEW majors beyond the deployed 5, graded per-cell on 14d Kraken tape
# by scripts/grade_coin_kraken.py (the S54 gate: forward-vs-reversed + shift-null floor + per-window
# sign consistency). These are CANDIDATES, NOT in DEPLOYED — seated in the capital model for backup
# capacity, promoted to live only after a longer-window confirm. Each carries its S67 grade verdict.
# Deep book != edge (Greg's "as much backup capacity as possible" is gated by the per-cell grade):
#   SUI  REJECT   (-2.30 $/hr, 43% windows — 2nd-deepest book, no mean-reversion edge on tape)
KRAKEN_CANDIDATES = [
    CellConfig("ltc", venue="kraken", side=-1, rev=0.30, grace=300, improve=0.5),   # SEAT: +3.33 $/hr, rev-side, 86% windows, clears floor
]
# MARGINAL: positive edge that beats reversed but does NOT robustly clear the null floor / sub-window
# consistency — usable as thin BACKUP capacity (low weight in the pool), not core. Off by default.
KRAKEN_CANDIDATES_MARGINAL = [
    CellConfig("avax", venue="kraken", side=+1, rev=0.13, grace=300, improve=0.5),   # +3.37 $/hr but 57% windows, barely over floor
    CellConfig("ada", venue="kraken", side=+1, rev=0.10, grace=300, improve=0.5),    # +1.88 $/hr, BELOW its own null floor (+2.41)
    CellConfig("sui", venue="kraken", side=-1, rev=0.30, grace=300, improve=0.5),    # REJECT (-2.30) — seated only so it's not dropped; greedy never funds negative edge
]


def kraken_flips(cfg, mid, buy, sell):
    """Compose a Kraken cell's flip stream from its config (live): early-arm (retime) if eps set else
    base detect_flips at cfg.rev; reverse for reversed cells."""
    if cfg.eps is not None:
        flips = retime_flips(mid, buy, sell, WFLIP, cfg.rev, cfg.eps)[0]
    else:
        flips = detect_flips(lean_series(buy, sell, WFLIP), cfg.rev)[0]
    if cfg.side < 0:
        flips = [(c, p, -s) for (c, p, s) in flips]
    return flips


def run_kraken_cell(cfg, mid, buy, sell, best_bid_sz, best_ask_sz, half_spread_bps,
                    balance_exit=None, bal_lean_w=None):
    """THE LIVE Kraken decision path (S65): compose the per-coin STACK (direction + early-arm + deep-bail
    + enticing + per-cell REV) and run it through run_stream FRONT-OF-LINE. The basket sim calls THIS —
    it does not reimplement the decision (the S65 sim=live-code rule). Book ARRAYS are passed in (Kraken
    venue data-loading is the caller's job until a live Kraken loader lands). Returns (SwingResult, desc).

    balance_exit (S75, opt-in — default None = the deployed exit, byte-identical): (arm_hi, exit_lo) for
    the balance exit (with-ride flow-lean armed then decaying to <= exit_lo). Coexists with the deep-bail
    (both walked, earliest cell wins). bal_lean_w = the balance-exit lean window in cells (None = WFLIP)."""
    flips = kraken_flips(cfg, mid, buy, sell)
    exit_spec = {"kind": "price_stop", "x_bp": float(cfg.bail), "action": "flat", "side": 0} \
        if cfg.bail is not None else None
    return run_stream(mid, buy, sell, flips, best_bid_sz=best_bid_sz, best_ask_sz=best_ask_sz,
                      half_spread_bps=half_spread_bps, maker_fee=cfg.maker_fee, taker_fee=cfg.taker_fee,
                      grace=cfg.grace, exit_spec=exit_spec, fill_model="front",
                      close_improve_bps=cfg.improve,
                      balance_exit=balance_exit, bal_lean_w=bal_lean_w)


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
               dipole_entry=False, dipole_exit=None, exit_spec=None, lean_w=None,
               balance_exit=None, bal_lean_w=None,
               fill_mode="maker", fill_model="front", queue_frac=1.0,
               close_improve_bps=0.0, alpha=1.0, roll=200, quality=None, size_axis=None):
    """ANY flip stream through the platform's decision code — the single research entry point.

    flips: (confirm_idx, pivot_idx, side) tuples — fine detect_flips output OR a coarse price
    zigzag (same tuple shape). fill_mode="taker" for dump bins (no book depth; pass no sizes).
    fill_model="queue" (S61 build (a), opt-in — default "front" = bit-identical) = the HONEST
    maker fill: queue-ahead at the posted level must trade through before any fill (see
    swing_maker); requires real best_bid_sz/best_ask_sz.
    exit_spec (S61, opt-in — default None = bit-identical) = the per-cell exit corrector socket
    (price_stop / armed_dive / casc_flip; see swing_maker). lean_w (CELLS) = the walker's lean
    window for exit_spec — callers define it WALL-CLOCK per venue (600s = 600 cells on 1s bins,
    6000 on 0.1s books; the S60 R4b confound fix). Descriptors stay on the platform WFLIP lean.
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
    wl = lean if lean_w is None else lean_series(buy, sell, int(lean_w))
    # the lean the executor's exit walkers see: balance_exit uses its own (opt-in) window (bal_lean_w
    # cells; default = the WFLIP flip-lean the executor already computes); price_stop ignores lean.
    if balance_exit is not None:
        lean_arg = lean if bal_lean_w is None else lean_series(buy, sell, int(bal_lean_w))
    elif dipole_exit:
        lean_arg = lean
    elif exit_spec is not None:
        lean_arg = wl
    else:
        lean_arg = None
    res = simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=half_spread_bps,
                               maker_fee_bps=maker_fee, taker_fee_bps=taker_fee,
                               cover_grace=grace, entry_gate=egate,
                               lean=lean_arg, lean_exit=dipole_exit, exit_spec=exit_spec,
                               balance_exit=balance_exit,
                               fill_mode=fill_mode, fill_model=fill_model,
                               queue_frac=queue_frac, close_improve_bps=close_improve_bps)
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


@dataclass
class PortfolioResult:
    """Result of a shared-pool portfolio replay (run_portfolio). POOL RETURN, not sum-@-$5k."""
    pool: float
    hours: float
    total_pnl_usd: float
    per_coin: dict                 # coin -> dict(realized_pnl_usd, n_legs, n_funded, mean_alloc_usd, ...)
    pool_pnl_bucketed: np.ndarray  # per-bucket $ PnL of the whole pool (for pool Sharpe)
    mean_util: float               # mean pool $ deployed / pool  (EVENT-sampled — do not use for time-in-market)
    max_util: float                # peak pool $ deployed / pool
    idle_frac: float               # fraction of live EVENTS with zero pool deployed (event-sampled)
    time_util: float = 0.0         # TIME-weighted deployed $ / pool over the whole window (the honest utilization)
    time_in_play_frac: float = 0.0 # fraction of the window (wall-clock) with ANY capital deployed

    @property
    def pool_return_per_hr(self):
        return self.total_pnl_usd / self.hours if self.hours else 0.0


def run_portfolio(cell_legs, *, pool=5000.0, desired=None, caps=None, weights=None,
                  clusters=None, cluster_caps=None, mode="greedy", n=None, bucket_cells=3600,
                  leg_caps=None, preempt=False, preempt_cut_bps=5.0, mtm_prices=None):
    """Replay a set of per-cell leg streams as ONE shared capital pool (S67 capital model).

    Sits ON TOP of the proven per-cell path: the legs are already the output of run_kraken_cell /
    run_stream (this function never re-decides a trade — architect §2.3, sim=live). It answers the
    question basket_sim's `aggregate (sum @ $5k each)` line cannot: what does ONE shared pool earn
    when it is spread across the coins, capacity-capped and correlation-aware?

    cell_legs:   {coin: [SwingLeg,...]} — legs on a COMMON time grid (caller clips to the overlap
                 window so open_idx/close_idx share one 0..n index space). This strategy holds at
                 most one open leg per coin at a time, so the allocation KEY is the coin.
    pool:        shared pool $ (the ONLY place a total-$ figure enters — never a per-cell slice).
    desired:     {coin: usd} each coin WANTS per open leg (v1 per-coin: the position cap). Default =
                 caps (a coin wants to fill up to its capacity).
    caps:        {coin: usd} hard per-coin capacity ceiling (the SWAPPABLE capacity — per-coin
                 scaffold now, per-leg later without changing this function). Default = pool (uncapped
                 vs the pool). NOTE: a low cap => small size, NEVER exclusion (allocator rule 1).
    weights:     {coin: return-on-capacity} funding priority; default equal.
    clusters/cluster_caps: correlation-cluster labels + per-cluster budgets (a correlated-flush cap).
    leg_caps:    {coin: [usd per leg]} — OPTIONAL per-LEG counterparty capacity (S71). When given, each
                 opening leg's demand AND cap = leg_caps[coin][k] (k = its index in cell_legs[coin]),
                 the $ its book depth can absorb at the moment it opens, INSTEAD of the per-coin scalar
                 cap. This is the concurrency lever: a best coin whose leg caps at < pool leaves headroom
                 that cascades to the next-best LIVE coin, so several coins hold at once on one $5k pool.
                 None (default) = the old per-coin behaviour, byte-for-byte. A leg cap is a SIZE ceiling,
                 never an inclusion gate (allocator rule 1): a thin cap => small notional, never dropped.
    preempt:     OPTIONAL reactive preemption (S71, opt-in; default False = byte-identical). When a
                 higher-edge coin FIRES and free pool < what it can absorb, CUT the lowest-edge HELD
                 position (weight < the opener's) to fund the opener. Reactive AT the fire, never
                 predictive (leakage-safe: the decision uses only weights known before the fire + the
                 already-realized book state). The cut leg is realized CONSERVATIVELY FLAT minus a
                 `preempt_cut_bps` taker cut cost on its allocation (we don't peek at its intra-leg mark),
                 biasing AGAINST preemption so any lift is real. Its later natural close then realizes on
                 0 held $ (no double count). This is "reserve-per-rest v1": the opener reserves only its
                 real capacity; freed capital is genuinely free. preempt_cut_bps: the early-cut taker cost.
    n:           grid length in cells (default = max close_idx + 1). bucket_cells: bucket size for the
                 pool-PnL series (3600 = hourly on a 1s grid).

    Returns PortfolioResult. Event-driven: closes free capital before opens at the same cell; a batch
    of coins opening at one cell competes for the REMAINING pool via allocator.allocate (weighted by
    return-on-capacity, capped per-coin and per-cluster). A held leg is NOT resized mid-hold and is
    never preempted by a later arrival (realistic: you don't yank a resting maker position — a v1
    simplification, documented). Leg PnL realizes on the notional it actually held: net_bps/1e4 * alloc.
    """
    from odcore.allocator import allocate

    coins = list(cell_legs)
    caps = dict(caps) if caps else {c: float(pool) for c in coins}
    desired = dict(desired) if desired else dict(caps)
    weights = weights or {}
    if n is None:
        n = 1 + max((int(l.close_idx) for legs in cell_legs.values() for l in legs), default=0)
    hours = n / float(bucket_cells)

    # event list: (cell_idx, order, coin, leg_key, leg). order: closes (0) before opens (1) at a tie.
    events = []
    for coin, legs in cell_legs.items():
        for k, l in enumerate(legs):
            o, c = int(l.open_idx), int(l.close_idx)
            if c < o:
                continue
            events.append((o, 1, coin, k, l))
            events.append((c, 0, coin, k, l))
    events.sort(key=lambda e: (e[0], e[1]))

    held = {}                         # coin -> allocated $ of its currently-open leg
    held_leg = {}                     # coin -> the open SwingLeg (for honest preemption mark-to-market)
    preempt_events = [0]              # count of reactive preemptions (S71, opt-in)
    cl_used = {}                      # cluster_id -> deployed $
    per_coin = {c: dict(realized_pnl_usd=0.0, n_legs=0, n_funded=0, alloc_sum=0.0,
                        desired_sum=0.0) for c in coins}
    nb = max(1, n // bucket_cells)
    pool_pnl = np.zeros(nb)
    util_samples = []                 # pool_used sampled after every event (for utilization stats)
    timeline = []                     # (cell_idx, deployed$) after each batch -> TIME-weighted utilization

    def pool_used():
        return sum(held.values())

    i = 0
    E = len(events)
    while i < E:
        idx = events[i][0]
        # 1) process all CLOSES at this cell first (free capital)
        j = i
        while j < E and events[j][0] == idx and events[j][1] == 0:
            _, _, coin, _, l = events[j]
            alloc = held.pop(coin, 0.0)
            held_leg.pop(coin, None)              # this leg is done (or was already preempted -> alloc 0)
            pnl = float(l.net_bps) / 1e4 * alloc
            per_coin[coin]["realized_pnl_usd"] += pnl
            b = min(int(l.close_idx) // bucket_cells, nb - 1)
            pool_pnl[b] += pnl
            if clusters and coin in clusters:
                cl_used[clusters[coin]] = cl_used.get(clusters[coin], 0.0) - alloc
            j += 1
        # 2) batch all OPENS at this cell; they compete for the REMAINING pool
        opens = []
        while j < E and events[j][0] == idx and events[j][1] == 1:
            opens.append(events[j])
            j += 1
        if opens:
            rem_pool = float(pool) - pool_used()
            oc = [e[2] for e in opens]
            # reactive PREEMPTION (opt-in): if the best-edge opener can't be fully funded from free pool,
            # cut the lowest-edge HELD position (weight < opener's) to fund it. Reactive at the fire only.
            if preempt and opens:
                def _w(c):
                    return float(weights.get(c, 0.0))
                best_op = max(oc, key=_w)
                # what the best opener can absorb this fire (its leg cap or per-coin cap)
                if leg_caps is not None and best_op in leg_caps:
                    k_op = next((e[3] for e in opens if e[2] == best_op), 0)
                    want = float(leg_caps[best_op][k_op]) if k_op < len(leg_caps[best_op]) \
                        else float(caps.get(best_op, pool))
                else:
                    want = float(caps.get(best_op, pool))
                # cut lower-edge holders (lowest weight first) until the opener's want is covered
                while rem_pool + 1e-9 < min(want, float(pool)):
                    cand = [c for c in held if _w(c) < _w(best_op) and held[c] > 1e-9]
                    if not cand:
                        break
                    victim = min(cand, key=_w)
                    freed = held.pop(victim)
                    vleg = held_leg.pop(victim, None)
                    # HONEST cut mark-to-market from the BOOK mid at the cut time (leakage-free: mid[idx]
                    # is known at idx). Realize the victim's actual intra-leg PnL, minus a taker cut cost.
                    gross = 0.0
                    if vleg is not None and mtm_prices is not None and victim in mtm_prices:
                        mp = mtm_prices[victim]; o_v = int(vleg.open_idx)
                        if 0 <= o_v < len(mp) and idx < len(mp) and mp[o_v] > 0:
                            gross = int(vleg.side) * (float(mp[idx]) / float(mp[o_v]) - 1.0) * 1e4
                    cut_pnl = (gross - float(preempt_cut_bps)) / 1e4 * freed
                    per_coin[victim]["realized_pnl_usd"] += cut_pnl
                    pool_pnl[min(idx // bucket_cells, nb - 1)] += cut_pnl
                    if clusters and victim in clusters:
                        cl_used[clusters[victim]] = cl_used.get(clusters[victim], 0.0) - freed
                    preempt_events[0] += 1
                    rem_pool = float(pool) - pool_used()
            if leg_caps is not None:
                # per-LEG counterparty capacity (S71): each opening leg's demand AND cap = the $ its
                # book depth absorbs at open. e[3] = k, the leg's index in cell_legs[coin]. A coin opens
                # at most one leg at a given cell, so oc has one entry per coin (keys stay unique).
                dem = {}; cp = {}
                for e in opens:
                    c, k = e[2], e[3]
                    lc = float(leg_caps[c][k]) if (c in leg_caps and k < len(leg_caps[c])) \
                        else float(caps.get(c, pool))
                    dem[c] = lc; cp[c] = lc
            else:
                dem = {c: float(desired.get(c, caps.get(c, pool))) for c in oc}
                cp = {c: float(caps.get(c, pool)) for c in oc}
            ccaps = None
            if cluster_caps and clusters:
                ccaps = {cid: float(cluster_caps[cid]) - cl_used.get(cid, 0.0)
                         for cid in set(clusters.get(c) for c in oc if c in clusters)}
            alloc = allocate(dem, caps=cp, pool=max(0.0, rem_pool), weights=weights,
                             clusters=clusters, cluster_caps=ccaps, mode=mode)
            for e in opens:
                coin, l = e[2], e[4]
                a = alloc.get(coin, 0.0)
                held[coin] = a
                if a > 1e-9:
                    held_leg[coin] = l            # track the open leg for honest preemption MTM
                per_coin[coin]["n_legs"] += 1
                per_coin[coin]["desired_sum"] += dem[coin]
                if a > 1e-9:
                    per_coin[coin]["n_funded"] += 1
                    per_coin[coin]["alloc_sum"] += a
                if clusters and coin in clusters:
                    cl_used[clusters[coin]] = cl_used.get(clusters[coin], 0.0) + a
        timeline.append((idx, pool_used()))       # deployed $ persists from idx until the next batch
        util_samples.append(timeline[-1][1])
        i = j

    # TIME-weighted deployment over [0, n): each batch's deployed $ holds until the next batch's cell.
    cap_seconds = 0.0; play_seconds = 0.0
    for k, (idx_k, dep_k) in enumerate(timeline):
        end = timeline[k + 1][0] if k + 1 < len(timeline) else n
        dur = max(0, end - idx_k)
        cap_seconds += dep_k * dur
        if dep_k > 1e-9:
            play_seconds += dur
    time_util = float(cap_seconds / (pool * n)) if (pool and n) else 0.0
    time_in_play = float(play_seconds / n) if n else 0.0

    total = float(sum(pc["realized_pnl_usd"] for pc in per_coin.values()))
    for c, pc in per_coin.items():
        pc["mean_alloc_usd"] = pc["alloc_sum"] / pc["n_funded"] if pc["n_funded"] else 0.0
        pc["fill_share"] = pc["n_funded"] / pc["n_legs"] if pc["n_legs"] else 0.0
    us = np.asarray(util_samples, float) if util_samples else np.zeros(1)
    pr = PortfolioResult(
        pool=float(pool), hours=hours, total_pnl_usd=total, per_coin=per_coin,
        pool_pnl_bucketed=pool_pnl,
        mean_util=float(us.mean() / pool) if pool else 0.0,
        max_util=float(us.max() / pool) if pool else 0.0,
        idle_frac=float(np.mean(us <= 1e-9)),
        time_util=time_util, time_in_play_frac=time_in_play)
    pr.preempt_events = preempt_events[0]     # S71 opt-in reactive preemption count (attr; additive)
    return pr


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
