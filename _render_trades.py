"""_render_trades.py — render the 10 dissected maker fills as price curves, in the style of Greg's
hand-drawn swing diagram (buy the valleys, sell-short the peaks; mark where we actually got filled).

Reproduces the EXACT fills the deploy map / _dissect_fills.py simulate for one cell, picks the same 10
across the gross distribution, and draws each: the mid curve in a context window, the POST (where we
quoted), the FILL (where opposing flow hit us), and the EXIT (+hold), with the swing label. The point
is visual: the losers are quotes posted mid-trend (filled on the way down for a bid = a falling knife);
the winners are quotes that sat at a real turn (the valley/peak Greg drew).

Run:  python _render_trades.py <coin> [K] [kgate]
"""
from __future__ import annotations

import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from _liquidity_dive import build_channels, median_spread_bps
from odcore import quiet_floor
from odcore.maker_book import _first_fill_index
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker
from odcore.info_dipole import divergence

DIVW = 600   # trailing order-flow window (cells) for the dipole exhaustion/divergence read at each flip


def exhaustion_gate(flips, buy, sell, mid, n):
    """Per-cell entry gate (default True) set FALSE at flips that the info-dipole does NOT confirm as a real
    reversal — i.e. the flow still CONFIRMS the move and the dipole is strengthening ('continue': the ~49%
    healthy-trend tail). Causal: uses only the trailing DIVW window of buy/sell + price drift up to the flip.
    Gating these out caps the flip's wrong-tail (shorting into continued buying / buying into continued
    selling)."""
    g = np.ones(n, dtype=bool)
    for (ci, _pv, _s) in flips:
        ci = int(ci)
        lo = max(0, ci - DIVW)
        d = divergence(buy[lo:ci + 1], sell[lo:ci + 1], float(mid[ci] - mid[lo]))
        if d is None:
            continue                      # too short / empty window -> leave True (don't over-filter)
        g[ci] = bool(d["opposing"] or d["exhausting"])   # real reversal needs flow opposition OR exhaustion
    return g

FLOW_W, TRAIN_FRAC, FILL_WINDOW, HOLD, KGATE = 20, 0.6, 10, 1, 1.5
# Maker-at-the-turn = "have the BEST bid/offer" (front of queue, price improvement): fill on the first REAL
# opposing trade, NO time window (Greg S46: time windows are irrelevant). The conviction quote rests the
# whole leg, re-quoted as price moves; taker is the last-option flatten. Caveat: assumes best-price priority
# (latency/colocation) and the model credits the full half-spread (price improvement gives up a little).
# flip-detector operating point = the VALIDATED S40 point (W=60,REV=0.10 on 1-sec bins) scaled to the 100ms
# book grid: 60s lean = 600 cells. NOT tuned on this one 11.7h window (the RULES line: never tune off one
# window) — fixed, principled; we report, we do not grid-search for net.
WFLIP, REV = 600, 0.10
QUEUE_FRAC = 1.0       # S45 baseline ONLY (the original floor/confirm/opposing maker model = join the queue).
                       # The maker-at-the-turn swing executor no longer uses it (front-of-queue, no window).
FEE_FLOOR_BPS = 20.0   # S36b: trade only swings >= ~20 bps (round-trip fee + 2x entry slippage); a GATE, not a knob
CTX = 60   # context cells each side (6s) so the valley/peak shape is visible

BLUE = "#1414dc"


def render_swing(coin, K, path, ctx=CTX):
    """Maker-at-the-turn re-evaluation (STRATEGY_maker_at_the_turn_S45.md): one-sided quoting gated on the
    CAUSAL flip detector, with the QuietFloor confirming the shock. Prints the per-cell verdict and renders
    the swing legs (short=peaks, long=valleys) so we can confirm the S45 losers invert."""
    ch, g = build_channels(path, K, FLOW_W)
    imb = ch["depth_imb"]; mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    n = len(mid); cut = int(n * TRAIN_FRAC)
    hs_bps = median_spread_bps(path) / 2.0

    # QuietFloor shock gate (fit on TRAIN; the kickoff's "floor confirms the shock"). gated_signal != 0 = open.
    quiet = (buy + sell) <= 0.0
    qf = quiet_floor.fit(imb, quiet, train_frac=TRAIN_FRAC)
    confirm = qf.gated_signal(imb, k=KGATE) != 0

    # CAUSAL flips on the trailing flow lean; restrict the executor to the held-out TEST slice
    lean = lean_series(buy, sell, WFLIP)
    flips_all, _ = detect_flips(lean, REV)
    flips = [(ci, pv, sd) for (ci, pv, sd) in flips_all if ci >= cut]

    # front-of-queue, NO time window (Greg S46): conviction quote rests the whole leg, fills on the first
    # opposing trade; taker is the last-option flatten when no opposing trade arrives before the next turn.
    egate = exhaustion_gate(flips, buy, sell, mid, n)   # dipole exhaustion/divergence wrong-tail gate
    def sim(eg, label):
        return simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=hs_bps,
                                    maker_fee_bps=0.0, taker_fee_bps=0.0, taker_fallback=True,
                                    confirm=confirm, confirm_lookback=WFLIP, entry_gate=eg, arm=label)
    res_exh = sim(egate, f"{coin}_swing_exh")      # + exhaustion gate (wrong-tail A/B)
    res = sim(None, f"{coin}_swing")               # PRIMARY = no exhaustion gate (better net/win on this window)
    dng = res.as_dict(); de = res_exh.as_dict()
    print(f"\n# {coin.upper()}_coinbase MAKER-AT-THE-TURN wrong-tail gate A/B (K={K}, Wflip={WFLIP}, REV={REV}):")
    print(f"#   NO gate (primary): legs={dng['n_legs']:>4}  net/leg={dng['net_per_leg_bps']:+.3f}  "
          f"win={100*dng['win_frac']:.0f}%  total={dng['total_net_bps']:+.1f}  taker={dng['n_taker_closes']}")
    print(f"#   + EXH gate       : legs={de['n_legs']:>4}  net/leg={de['net_per_leg_bps']:+.3f}  "
          f"win={100*de['win_frac']:.0f}%  total={de['total_net_bps']:+.1f}  taker={de['n_taker_closes']} "
          f"(marginal on this window — revisit as data accrues)")
    d = res.as_dict()
    # the S36b fee-floor GATE: report the subset of legs whose swing cleared ~20 bps (the tradeable scale)
    big = [l for l in res.legs if l.swing_bps >= FEE_FLOOR_BPS]
    big_net = float(np.mean([l.net_bps for l in big])) if big else float("nan")
    big_tot = float(np.sum([l.net_bps for l in big])) if big else 0.0
    print(f"\n# {coin.upper()}_coinbase MAKER-AT-THE-TURN (K={K}, Wflip={WFLIP}, REV={REV}, floor k={KGATE}, "
          f"half_sp={hs_bps:.4f} bps, test slice {cut:,}:{n:,})")
    print(f"#   flips(test)={len(flips)}  legs={d['n_legs']}  maker_fill_rate={100*d['fill_rate']:.0f}%  "
          f"taker_closes={d['n_taker_closes']}")
    print(f"#   ALL legs:   gross/leg={d['gross_per_leg_bps']:+.3f}  net/leg={d['net_per_leg_bps']:+.3f}  "
          f"total_net={d['total_net_bps']:+.1f} bps  win={100*d['win_frac']:.0f}%  "
          f"mean_swing={d['mean_swing_bps']:.2f} bps")
    print(f"#   swings>={FEE_FLOOR_BPS:.0f}bps (fee-floor gate): n={len(big)}  net/leg={big_net:+.3f}  "
          f"total_net={big_tot:+.1f} bps")

    legs = res.legs
    if not legs:
        print("#   no closed legs — nothing to render"); return d
    # render up to 10 legs sampled across net (worst losers .. best winners), each on its mid curve
    legs_sorted = sorted(legs, key=lambda l: l.net_bps)
    pick_ix = np.linspace(0, len(legs_sorted) - 1, min(10, len(legs_sorted))).round().astype(int)
    picks = [legs_sorted[i] for i in pick_ix]
    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    fig.suptitle(f"{coin.upper()}_coinbase MAKER-AT-THE-TURN — one-sided, flip-gated (K={K}). "
                 f"Short legs sit at PEAKS, long legs at VALLEYS. o=entry(turn) x=exit(next turn). "
                 f"Green=net+, Red=net-.", fontsize=12)
    for ax, l in zip(axes.flat, picks):
        oi, ei = l.open_idx, l.close_idx
        lo, hi = max(0, oi - ctx), min(n - 1, ei + ctx)
        xs = np.arange(lo, hi + 1) - oi
        ax.plot(xs, mid[lo:hi + 1], color=BLUE, lw=2.4, solid_capstyle="round")
        col = "#0a8f2a" if l.net_bps > 0 else "#cc1414"
        ax.scatter([0], [l.open_px], s=80, facecolors="none", edgecolors="k", lw=1.8, zorder=5)
        ax.scatter([ei - oi], [l.close_px], marker="x", s=95, color=col, lw=2.4, zorder=6)
        ax.axhline(l.open_px, color=col, ls=":", lw=1.2, alpha=0.8)
        label = "Short top" if l.side < 0 else "Long valley"
        ax.annotate(label, xy=(0, l.open_px), xytext=(-ctx * 0.9, l.open_px),
                    fontsize=12, color=BLUE, weight="bold", va="center")
        ax.set_title(f"{'ASK/short' if l.side < 0 else 'BID/long'}  hold={ei-oi}c  "
                     f"net={l.net_bps:+.2f} bps{'' if l.close_maker else ' (taker exit)'}",
                     fontsize=9, color=col)
        ax.set_xticks([]); ax.set_yticks([])
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = f"_render_trades_{coin}_swing.png"
    fig.savefig(out, dpi=110)
    print(f"# wrote {out}")
    return d


def swing_walk(coin, K, kgate, path, ctx=CTX):
    """Walk-through: the SAME 10 trades the original (floor) render samples, each annotated with what the
    new MAKER-AT-THE-TURN strategy does at that exact moment. The point (Greg): the S45 losers were BIDs
    posted at peaks (bought the falling knife); under maker-at-the-turn the same peak shows an OFFER ->
    short the top -> cover the valley. Prints a side-by-side table + a paired render."""
    ch, g = build_channels(path, K, FLOW_W)
    imb = ch["depth_imb"]; mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    n = len(mid); cut = int(n * TRAIN_FRAC); hs_bps = median_spread_bps(path) / 2.0
    quiet = (buy + sell) <= 0.0
    qf = quiet_floor.fit(imb, quiet, train_frac=TRAIN_FRAC)
    gated = qf.gated_signal(imb, k=kgate)

    # --- ORIGINAL floor-signal fills (identical to the S45 default render: join-the-queue, queue_frac=1.0) ---
    side = np.zeros(n); side[cut:] = gated[cut:]
    qa = np.where(side > 0, bb, ba) * 1.0
    filled_at = np.where(side > 0, _first_fill_index(qa, sell, FILL_WINDOW),
                         np.where(side < 0, _first_fill_index(qa, buy, FILL_WINDOW), -1))
    filled = (side != 0) & (filled_at >= 0) & ((filled_at + HOLD) <= (n - 1))
    idx = np.where(filled)[0]; fi = filled_at; ei = np.clip(fi + HOLD, 0, n - 1)
    hs_price = (hs_bps / 1e4) * mid
    o_entry = np.where(side > 0, mid - hs_price, mid + hs_price)
    o_gross = side[idx] * (mid[ei[idx]] - o_entry[idx]) / mid[idx] * 1e4
    order = np.argsort(o_gross)
    picks = order[np.linspace(0, len(idx) - 1, 10).round().astype(int)]

    # --- NEW maker-at-the-turn legs (flip-gated + floor-confirmed) ---
    confirm = gated != 0
    lean = lean_series(buy, sell, WFLIP)
    flips_all, _ = detect_flips(lean, REV)
    flips = [(ci, pv, sd) for (ci, pv, sd) in flips_all if ci >= cut]
    res = simulate_swing_maker(mid, bb, ba, buy, sell, flips, half_spread_bps=hs_bps,
                               maker_fee_bps=0.0, taker_fee_bps=0.0, taker_fallback=True,
                               confirm=confirm, confirm_lookback=WFLIP, arm=f"{coin}_swing")

    def leg_at(t):  # the swing leg governing cell t: from the flip that DECIDED the side (flip_idx, before
        for l in res.legs:           # the fill lag) through the cover, so the few-cell fill lag doesn't read as flat
            if l.flip_idx <= t <= l.close_idx:
                return l
        return None

    print(f"\n# {coin.upper()}_coinbase WALK-THROUGH — same 10 floor-signal trades, OLD vs MAKER-AT-THE-TURN")
    print(f"# (K={K}, gate k={kgate}, Wflip={WFLIP}, REV={REV}, half_sp={hs_bps:.3f} bps; test slice {cut:,}:{n:,})")
    print(f"#{'':2}{'cell':>8}{'OLD side':>10}{'OLD gross':>11}   ||  NEW maker-at-the-turn")
    sumold = sumnew = 0.0
    for r, k in enumerate(picks):
        t = int(idx[k]); osd = "BID/long" if side[idx][k] > 0 else "ASK/short"; og = float(o_gross[k])
        sumold += og
        l = leg_at(t)
        if l is None:
            newtxt = "flat (no confirmed turn here)"
        else:
            nsd = "SHORT(ask)" if l.side < 0 else "LONG(bid)"
            ex = "maker" if l.close_maker else "taker"
            newtxt = (f"{nsd}  entry {l.open_px:.5f} @c{l.open_idx} -> exit {l.close_px:.5f} @c{l.close_idx} "
                      f"({ex})  net {l.net_bps:+.2f} bps  swing {l.swing_bps:.1f}")
            sumnew += l.net_bps
        flag = "  <-- inverted" if (l is not None and (side[idx][k] > 0) == (l.side < 0)) else ""
        print(f"#{r:2}{t:>8}{osd:>10}{og:>+11.2f}   ||  {newtxt}{flag}")
    print(f"# {'':18}OLD sum {sumold:+.2f} bps  ||  NEW sum (legs covering these moments) {sumnew:+.2f} bps")

    # paired render: each panel = mid curve with the OLD marker (o post) and the NEW leg entry/exit
    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    fig.suptitle(f"{coin.upper()}_coinbase — same 10 trades: OLD floor fill (black o, dotted = old entry) "
                 f"vs NEW maker-at-the-turn (green/red entry o -> exit x). Old BIDs at peaks become SHORTs.",
                 fontsize=11)
    for ax, k in zip(axes.flat, picks):
        t = int(idx[k]); l = leg_at(t)
        lo = max(0, (l.open_idx if l else t) - ctx); hi = min(n - 1, (l.close_idx if l else int(ei[t])) + ctx)
        xs = np.arange(lo, hi + 1) - t
        ax.plot(xs, mid[lo:hi + 1], color=BLUE, lw=2.2, solid_capstyle="round")
        ax.scatter([0], [mid[t]], s=70, facecolors="none", edgecolors="k", lw=1.8, zorder=5)
        ax.axhline(o_entry[t], color="k", ls=":", lw=1.0, alpha=0.6)
        if l is not None:
            col = "#0a8f2a" if l.net_bps > 0 else "#cc1414"
            ax.scatter([l.open_idx - t], [l.open_px], s=80, color=col, zorder=6)
            ax.scatter([l.close_idx - t], [l.close_px], marker="x", s=95, color=col, lw=2.4, zorder=6)
            ax.set_title(f"OLD {'BID' if side[idx][k]>0 else 'ASK'} {o_gross[k]:+.1f} | NEW "
                         f"{'SHORT' if l.side<0 else 'LONG'} {l.net_bps:+.1f} bps", fontsize=9, color=col)
        else:
            ax.set_title(f"OLD {'BID' if side[idx][k]>0 else 'ASK'} {o_gross[k]:+.1f} | NEW flat",
                         fontsize=9, color="#888")
        ax.set_xticks([]); ax.set_yticks([]); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = f"_render_trades_{coin}_swingwalk.png"
    fig.savefig(out, dpi=110); print(f"# wrote {out}")


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "sol"
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    kgate = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
    mode = sys.argv[4] if len(sys.argv) > 4 else "floor"   # floor | confirm | opposing | both | swing | swingwalk
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"

    if mode == "swing":
        render_swing(coin, K, path)
        return
    if mode == "swingwalk":
        swing_walk(coin, K, kgate, path)
        return

    ch, g = build_channels(path, K, FLOW_W)
    imb = ch["depth_imb"]; mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    n = len(mid); cut = int(n * TRAIN_FRAC)
    hs_bps = median_spread_bps(path) / 2.0
    quiet = (buy + sell) <= 0.0
    qf = quiet_floor.fit(imb, quiet, train_frac=TRAIN_FRAC)
    gated = qf.gated_signal(imb, k=kgate)
    if mode in ("both", "opposing", "confirm"):
        # aligned = depth_imb * sign(trailing price drift); >0 book CONFIRMS the move, <0 OPPOSES it
        lm = np.log(np.where(mid > 0, mid, np.nan)); pdwin = 30
        pd = np.zeros(n); pd[pdwin:] = np.nan_to_num(lm[pdwin:] - lm[:-pdwin])
        aligned = np.sign(imb) * np.sign(pd)
        cond = (aligned > 0) if mode == "confirm" else (aligned < 0)   # confirm=continuation, else reversal
        gated = np.where((gated != 0) & cond, np.sign(imb), 0.0)
    side = np.zeros(n); side[cut:] = gated[cut:]

    qa = np.where(side > 0, bb, ba) * QUEUE_FRAC
    filled_at = np.where(side > 0, _first_fill_index(qa, sell, FILL_WINDOW),
                         np.where(side < 0, _first_fill_index(qa, buy, FILL_WINDOW), -1))
    filled = (side != 0) & (filled_at >= 0) & ((filled_at + HOLD) <= (n - 1))
    idx = np.where(filled)[0]
    fi = filled_at; ei = np.clip(fi + HOLD, 0, n - 1)
    hs_price = (hs_bps / 1e4) * mid
    entry = np.where(side > 0, mid - hs_price, mid + hs_price)
    sgn = side[idx]
    gross = sgn * (mid[ei[idx]] - entry[idx]) / mid[idx] * 1e4

    order = np.argsort(gross)
    picks = order[np.linspace(0, len(idx) - 1, 10).round().astype(int)]

    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    fig.suptitle(f"{coin.upper()}_coinbase maker fills — {mode.upper()} signal (K={K} top-of-book, gate "
                 f"k={kgate})  —  blue=mid; o post, • fill, x exit(+hold). Green=favorable, Red=adverse.",
                 fontsize=13)
    for ax, k in zip(axes.flat, picks):
        t = int(idx[k]); f = int(fi[t]); e = int(ei[t]); is_bid = sgn[k] > 0
        lo, hi = max(0, t - CTX), min(n - 1, e + CTX)
        xs = np.arange(lo, hi + 1) - t              # cells relative to post (x=0)
        ax.plot(xs, mid[lo:hi + 1], color=BLUE, lw=2.4, solid_capstyle="round")
        good = gross[k] > 0
        col = "#0a8f2a" if good else "#cc1414"
        # post / fill / exit markers
        ax.scatter([0], [mid[t]], s=70, facecolors="none", edgecolors="k", lw=1.8, zorder=5)
        ax.scatter([f - t], [mid[f]], s=85, color=col, zorder=6)
        ax.scatter([e - t], [mid[e]], marker="x", s=90, color=col, lw=2.4, zorder=6)
        ax.axhline(entry[t], color=col, ls=":", lw=1.2, alpha=0.8)
        label = "Buy long" if is_bid else "Sell short"
        ax.annotate(label, xy=(0, mid[t]), xytext=(-CTX * 0.9, mid[t]),
                    fontsize=13, color=BLUE, weight="bold",
                    va="center", rotation=12 if is_bid else -12)
        ax.set_title(f"{'BID' if is_bid else 'ASK'}  wait={f-t}c  "
                     f"gross={gross[k]:+.2f} bps", fontsize=10, color=col)
        ax.set_xlabel("cells from post (100ms)"); ax.set_xticks([])
        ax.set_yticks([])
        ax.spines[["top", "right"]].set_visible(False)
    # legend in words
    axes.flat[0].text(0.02, 0.02, "o post   • fill   x exit(+hold)",
                      transform=axes.flat[0].transAxes, fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = f"_render_trades_{coin}_{mode}.png"
    fig.savefig(out, dpi=110)
    print(f"wrote {out}  (mean gross over all {len(idx)} fills = {gross.mean():+.4f} bps)")


if __name__ == "__main__":
    main()
