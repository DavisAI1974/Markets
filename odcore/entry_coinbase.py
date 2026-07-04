"""odcore/entry_coinbase.py — the COINBASE mid-band ENTRY machine (S59 promotion; entry piece
DONE, Greg's call — S58_ENTRY_NOTES.md definition-of-done executed here).

PLATFORM SEPARATION (Greg, S59): venue goes in the file title from here on. This module is the
Coinbase deploy shape of the S58 entry piece. Kraken gets its own module when Kraken books have
accrued and validated per cell (venue law: nothing flow-based ports without a per-venue pass;
price mechanics DO port, so `armed_midband_flips` itself is venue-neutral and a future
entry_kraken module may import it from here).

WHAT WAS PROMOTED (from scripts/_s58_piece1_reruns.py `machine()` — the round-6 reference
implementation, promoted verbatim; the S59 canary asserts bit-identical flips against it):
  - v2 arming (extremes anchored since the last flip; ARM=theta extension arms the turn watch)
  - c-scaled fine confirm (first c*theta reversal off the running extreme confirms — the S55 R5
    lag cut; c scales with the band, the S57 lesson)
  - MODE-0 FALLBACK FIX (S58 mistakes-ledger #2): the trailing-ARM fallback fires in mode 0
    too — a veto rejecting the first-ever confirm can never strand the machine again
  - BASELINE fallback = immediate flip at theta-adverse (bounded loss ~theta, the crown jewel;
    round-5 falsified the bounce fallback as a general fix — bnc25 survives ONLY as the BTC
    per-cell candidate, carried on the config)
  - per-cell confirm-predicate SOCKET (`pred`) — naive k0 = None. The bins member maps (sol
    fade+climax, btc opposing-mandatory, doge clmxexh, xrp death-combo veto) are RESEARCH-ONLY:
    flow reads do not port venues (S58 master finding); they activate per cell only after an
    accrued-Coinbase-books pass. The socket is deliberately data-blind (takes a closure) so no
    flow read can wire in without its own leakage gate.

REGISTRY (the S58 five-verdict board, Coinbase frame — every deploy shape is NAIVE k0):
  sol  th100 c0.5  ACTIVE   — the lead cell (books th100 k0 +6.11 net/leg, n=56 one-window)
  xrp  th80  c0.5  ACTIVE   — naive only (its stack lift was a pooled-window artifact);
                              death-combo veto = flagged research candidate, NOT active
  doge th100 c0.5  ACTIVE   — naive; clmxexh = the only flow map that held its books shape,
                              top per-venue-validation candidate as books accrue, NOT active
  btc  th80  c0.5  INACTIVE — pending Coinbase book accrual (collector repaired S58); the
                              th80 stack read stays bins/research-only
  eth  DROPPED — not in the registry (re-entry test: ~100 accrued book confirms in th100 k3
                 with top-2-excluded mean > +10bp/leg + k3^B3 shuffle-gate pass)

ONE-VERSION LAW: this module produces the FLIP STREAM only; execution, fees, sizing and
descriptors run through odcore.platform.run_stream (swing_maker executor) — paper, research
and (future) live all render through the same mechanics. Mid-band legs are FLAT size (the
sizing stack is fine-scale-validated only; mid-band sizing was NOT earned — S55 R11, parked
Piece 3). Sandbox rule: these cells write the SANDBOX ledger, never the baseline forward
ledger; the S59 canary asserts the baseline paper path is bit-identical with this module
present. Leakage: `assert_truncation_invariance` is the machine's own causality gate —
run it on every tape before trusting a new cell's rows.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def armed_midband_flips(mid, theta_bp, c=0.5, pred=None, reads=None, bounce_frac=0.0):
    """The promoted S58 armed mid-band machine -> flip stream [(confirm_idx, pivot_idx, side)].

    mid: 1d price array (any regular grid — bp thresholds are grid-independent).
    theta_bp: the band (ARM = theta extension; fallback bound ~theta).
    c: confirm fraction — first c*theta reversal off the running extreme confirms.
    pred: optional confirm predicate pred(reads, pivot_idx, new_side) -> bool. None = naive k0
          (every Coinbase deploy shape). A vetoed dip keeps riding; the fallback is NEVER vetoed.
    reads: opaque object handed to pred (e.g. a StackReads-like wrapper); unused when pred None.
    bounce_frac: 0.0 = BASELINE fallback (immediate flip at theta-adverse, bounded loss).
          >0 = bounce fallback (flip on first bounce_frac*theta recovery off the running adverse
          extreme) — round-5 falsified as a general fix; carried ONLY as the BTC candidate.

    Verbatim port of scripts/_s58_piece1_reruns.py::machine() (mode-0 fallback fix included);
    the S59 promotion canary asserts bit-identical flips on the round-6 tapes.
    """
    a, f = theta_bp / 1e4, (c * theta_bp) / 1e4
    fb = (bounce_frac * theta_bp) / 1e4
    ok = (lambda pi, d: True) if pred is None else (lambda pi, d: pred(reads, pi, d))
    n = len(mid)
    flips = []
    lo_i = hi_i = 0
    mode = 0
    pend = 0
    pext = 0
    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if pend == -1:
            if m < mid[pext]:
                pext = t
            if m >= mid[pext] * (1 + fb):
                flips.append((t, hi_i, -1)); mode = -1; pend = 0; lo_i = t
                continue
        elif pend == +1:
            if m > mid[pext]:
                pext = t
            if m <= mid[pext] * (1 - fb):
                flips.append((t, lo_i, +1)); mode = +1; pend = 0; hi_i = t
                continue
        if pend == 0 and mode >= 0:
            armed_dn = mid[hi_i] >= mid[lo_i] * (1 + a)
            if armed_dn and m <= mid[hi_i] * (1 - f) and ok(hi_i, -1):
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
            if armed_dn and m <= mid[hi_i] * (1 - a):       # fallback — fires in mode 0 too
                if fb <= 0:
                    flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                else:
                    pend = -1; pext = t
                continue
        if pend == 0 and mode <= 0:
            armed_up = mid[lo_i] <= mid[hi_i] * (1 - a)
            if armed_up and m >= mid[lo_i] * (1 + f) and ok(lo_i, +1):
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
                continue
            if armed_up and m >= mid[lo_i] * (1 + a):       # fallback — fires in mode 0 too
                if fb <= 0:
                    flips.append((t, lo_i, +1)); mode = +1; hi_i = t
                else:
                    pend = +1; pext = t
    return flips


def assert_truncation_invariance(mid, theta_bp, c=0.5, cuts=(3, 2)):
    """Causality gate: flips on a prefix tape must equal the full-tape flips below the cut.
    Raises AssertionError on any divergence. Run per tape before trusting new-cell rows."""
    mid = np.asarray(mid, float)
    full = armed_midband_flips(mid, theta_bp, c)
    n = len(mid)
    for den in cuts:
        cut = n // den
        pre = armed_midband_flips(mid[:cut], theta_bp, c)
        want = [x for x in full if x[0] < cut]
        assert pre[:len(want)] == want, \
            f"leakage: prefix flips diverge below cut {cut} (theta={theta_bp}, c={c})"
    return True


@dataclass
class MidbandCellConfig:
    """Per-cell Coinbase mid-band entry config (S58 five-verdict board)."""
    coin: str
    theta_bp: float                  # the band (sol/doge 100, xrp/btc 80)
    c: float = 0.5                   # confirm fraction (round-2/3 band)
    K: int = 1                       # book depth levels for channels (btc = 10)
    maker_fee: float = 8.0           # bps/leg — cb_real, the honest Coinbase spot column
    taker_fee: float = 16.0          # bps/leg — Coinbase taker at our tier
    bounce_frac: float = 0.0         # baseline fallback; 0.25 = the BTC-only candidate (research)
    active: bool = True              # False = gated (btc: pending book accrual)
    research_note: str = ""          # flagged flow-map candidate, NOT wired (venue law)
    venue: str = "coinbase"

    @property
    def cell(self):
        return f"{self.coin}_{self.venue}_mb{int(self.theta_bp)}"

    @property
    def path(self):
        return f"/tmp/{self.coin}_{self.venue}_book.jsonl.gz"


# The Coinbase mid-band registry — every ACTIVE deploy shape is NAIVE k0 (S58 master finding:
# price mechanics port, flow reads don't). research_note = the per-cell flow-map candidate that
# activates ONLY after an accrued-books per-venue pass. ETH is deliberately absent (DROPPED;
# re-entry test in S58_ENTRY_NOTES.md).
COINBASE_MIDBAND = [
    MidbandCellConfig("sol", 100.0),
    MidbandCellConfig("xrp", 80.0,
                      research_note="death-combo veto (opposing & climax & !exhausting) — "
                                    "harmless rider on bins; needs books pass"),
    MidbandCellConfig("doge", 100.0,
                      research_note="clmxexh (clmx60>=3.4 & exhausting) — only flow map that "
                                    "held its books shape (th100 +15.6 vs k0 +9.3, n~23); "
                                    "top per-venue-validation candidate"),
    MidbandCellConfig("btc", 80.0, K=10, active=False,
                      research_note="pending Coinbase book accrual (collector repaired S58); "
                                    "th80 opposing-mandatory stack + bnc25 fallback = bins "
                                    "research candidates"),
]


def run_midband_cell(cfg: MidbandCellConfig, fill_model: str = "front", queue_frac: float = 1.0):
    """One Coinbase mid-band cell book -> flat-size, descriptor-carrying trade rows through the
    platform executor (run_stream). SANDBOX rows (S53 rule) — caller routes the ledger.

    fill_model (S61 build (a), opt-in — default "front" = bit-identical): "queue" runs the HONEST
    maker fill (queue-ahead at the posted level must trade through; see swing_maker) so the real
    maker_close% / fill cost is measurable — a MEASUREMENT arm; the sandbox default is unchanged
    until the honest model earns its own gate record."""
    import sys
    for p in (ROOT, os.path.join(ROOT, "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from _liquidity_dive import build_channels, median_spread_bps
    from _birth_probe import load_book
    from odcore.platform import run_stream, FLOW_W

    if not cfg.active or not os.path.exists(cfg.path):
        return []
    raw = load_book(cfg.path)
    ch, g = build_channels(cfg.path, cfg.K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs = median_spread_bps(cfg.path, raw=raw) / 2.0
    t0 = float(raw["ts"][0])
    assert_truncation_invariance(mid, cfg.theta_bp, cfg.c)      # leakage gate, every tape
    flips = armed_midband_flips(mid, cfg.theta_bp, cfg.c, bounce_frac=cfg.bounce_frac)
    if len(flips) < 2:
        return []
    res, desc = run_stream(mid, buy, sell, flips, best_bid_sz=bb, best_ask_sz=ba,
                           half_spread_bps=hs, maker_fee=cfg.maker_fee,
                           taker_fee=cfg.taker_fee, fill_model=fill_model,
                           queue_frac=queue_frac)
    out = []
    for i, l in enumerate(res.legs):
        ts = t0 + int(l.open_idx) * 0.1
        out.append(dict(cell=cfg.cell, coin=cfg.coin, ts=round(ts, 3), side=int(l.side),
                        entry=round(float(l.open_px), 6), exit=round(float(l.close_px), 6),
                        net_bps=round(float(l.net_bps), 4), size_mult=1.0,
                        sized_net=round(float(l.net_bps), 4),
                        swing_bps=round(float(l.swing_bps), 3), maker_close=bool(l.close_maker),
                        grace=0, lean_exit=bool(l.lean_exit),
                        mode=f"mb{int(cfg.theta_bp)}c{cfg.c:g}", **desc[i]))
    return out
