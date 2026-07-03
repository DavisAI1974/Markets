"""_s57_sizing_round.py — S57: LEAN INTO SIZING / double down on big runs.

GREG'S SIZING SPEC (S57): $5k = the MID price of the size range; stay MUCH LOWER on
unsure/bad trades until confident; lean HARD AND FAST into the good trades when confident;
hard limit $10k. In size-multiplier terms (x$5k): lo 0.2 (=$1k floor), mid 1.0, hi 2.0
(=$10k cap). The deployed S47 mechanics (rank-conviction, causal rolling normalization,
S49 leakage-PASS construction) are kept; only the envelope and the lean (alpha) move.

One defined round, sol/eth bybit legs at TRUE fees (-0.4bp G1 MM3, grace 300):
  A. GREG ENVELOPE alpha sweep — clip(1 + alpha*z(conviction), 0.2, 2.0), alpha
     0.5/1.0/2.0/3.0/5.0: high alpha saturates the clips = bimodal low/high = "hard and
     fast". Reference rows: deployed envelope (0.25, 4.0) at alpha 1.0 for continuity.
  B. JOIN-VELOCITY tilt — the S57 veto-diagnosis finding (strong joins +5.6bp/leg vs +4.3
     population; corr(fade,net) -0.31 sol@10s): size' = clip(size * (1 + beta*z(join)),
     0.2, 2.0), join = side x trailing mid move (>0 = riding the run). beta 0.25/0.5/1.0,
     windows 10s/30s, applied on the envelope base.

SCORING (S47 discipline): MATCHED-CAPITAL lift (sizes rescaled to mean 1) so no variant
wins by deploying more capital, PLUS the raw $ totals (Greg's envelope is a capital design —
raw is what it earns as specced). Controls per variant: SHUFFLED size assignment (20 seeds)
and REVERSED tilt. All features causal (trailing windows, rolling stats over prior legs).

$/hr figures are FULL-FILL reference basis @size x $5k (rebate floor included) — variant
deltas are the read; the deploy number stays the queue-honest capacity bracket.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                                    # noqa: E402
from _liquidity_dive import build_channels, median_spread_bps         # noqa: E402
from odcore.flip_detector import lean_series, detect_flips            # noqa: E402
from odcore.platform import FLOW_W, WFLIP, REV, DIVW                  # noqa: E402
from odcore.swing_maker import simulate_swing_maker, size_legs        # noqa: E402

MID = 5000.0                 # $ at size 1.0 (Greg: the mid price of the range)
LO, HI = 0.2, 2.0            # $1k floor / $10k cap (Greg's envelope)
MAKER, TAKER, GRACE = -0.4, 5.5, 300
ALPHAS = (0.5, 1.0, 2.0, 3.0, 5.0)
BETAS = (0.25, 0.5, 1.0)
JWINS = (100, 300)           # 10s / 30s
ROLL, WARM = 200, 20


def mc(net, size):
    s = np.asarray(size, float)
    return float(np.sum(net * s) / (s.mean() + 1e-12))


def raw_usd(net, size, hrs):
    """$ per hour as specced: each leg trades size x $5k."""
    return float(np.sum(net * size)) * MID / 1e4 / hrs


def rolling_z(x, roll=ROLL, warm=WARM):
    x = np.asarray(x, float)
    z = np.zeros(len(x))
    for i in range(len(x)):
        lo = max(0, i - roll)
        if i - lo >= warm:
            pr = x[lo:i]
            z[i] = (x[i] - pr.mean()) / (pr.std() + 1e-9)
    return z


def build(coin):
    path = f"/tmp/{coin}_bybit_book.jsonl.gz"
    raw = load_book(path)
    ch, g = build_channels(path, 1, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    sret = ch["signed_ret"]
    hs = median_spread_bps(path, raw=raw) / 2.0
    hrs = (float(raw["ts"][-1]) - float(raw["ts"][0])) / 3600.0
    cvol = np.concatenate([[0.0], np.cumsum(buy + sell)])
    vm = lambda t, w: (cvol[t + 1] - cvol[max(0, t + 1 - w)]) / (t + 1 - max(0, t + 1 - w))
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    piv = {int(c): int(p) for (c, p, s) in allf}
    res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                               maker_fee_bps=MAKER, taker_fee_bps=TAKER, cover_grace=GRACE)
    legs = res.legs
    net = np.asarray([float(l.net_bps) for l in legs])
    clmx, ss = [], []
    joins = {w: [] for w in JWINS}
    for l in legs:
        ci = int(l.flip_idx); p = piv.get(ci, ci); lo = max(0, ci - DIVW)
        clmx.append(vm(ci, 60) / (vm(ci, 600) + 1e-12))
        v60 = vm(ci, 60); vlt = float(np.std(sret[max(0, ci - 120):ci + 1])) * 1e4
        rnp = abs(mid[ci] - mid[lo]) / mid[lo] * 1e4; dp = abs(lean[p])
        ss.append(v60 + vlt + rnp + dp)
        for w in JWINS:
            wlo = max(0, ci - w)
            joins[w].append(int(l.side) * (mid[ci] - mid[wlo]) / mid[wlo] * 1e4)
    return legs, net, clmx, ss, joins, hrs


def sized(legs, clmx, ss, alpha, lo_clip, hi_clip):
    size_legs(legs, clmx, ss, alpha=alpha, roll=ROLL, lo_clip=lo_clip, hi_clip=hi_clip)
    return np.asarray([float(l.size) for l in legs])


def dist(sz):
    return (f"avg ${sz.mean() * MID:,.0f}/leg, {100 * np.mean(sz <= LO + 1e-9):.0f}% at floor, "
            f"{100 * np.mean(sz >= HI - 1e-9):.0f}% at cap")


def main():
    rng = np.random.default_rng(57)
    for coin in ("sol", "eth"):
        legs, net, clmx, ss, joins, hrs = build(coin)
        n = len(net)
        flat_usd = float(net.sum()) * MID / 1e4 / hrs
        print(f"\n[{coin}_bybit] {n} legs {hrs:.2f}h @TRUE -0.4/5.5 — flat@$5k "
              f"${flat_usd:+.2f}/hr")
        print(f"  A: Greg envelope ($1k floor / $5k mid / $10k cap) — alpha sweep")
        print(f"  {'alpha':>6} {'env':>10} | {'raw $/hr':>9} | {'mc lift%':>9} | "
              f"{'shuf mc$ (20s)':>15} | {'rev mc$':>8} | size dist")
        base_sizes = None
        rows = [(a, LO, HI) for a in ALPHAS] + [(1.0, 0.25, 4.0)]
        for a, loc, hic in rows:
            sz = sized(legs, clmx, ss, a, loc, hic)
            if a == 1.0 and hic == HI:
                base_sizes = sz.copy()
            t_mc = mc(net, sz)
            flat = float(net.sum())
            lift = 100 * (t_mc - flat) / abs(flat)
            shf = [mc(net, rng.permutation(sz)) for _ in range(20)]
            rev = mc(net, sized(legs, clmx, ss, -a, loc, hic))
            d = MID / 1e4 / hrs
            env = f"[{loc:.2f},{hic:.1f}]"
            print(f"  {a:>6.2f} {env:>10} | {raw_usd(net, sz, hrs):>+9.2f} | {lift:>+8.1f}% | "
                  f"{np.mean(shf) * d:>+8.2f}±{np.std(shf) * d:>4.2f} | {rev * d:>+8.2f} | {dist(sz)}")
        # B: join tilt on the envelope base (alpha 1.0), final clip = the $10k hard cap
        sized_mc = mc(net, base_sizes)
        d = MID / 1e4 / hrs
        print(f"  B: join tilt size' = clip(size x (1+beta*z(join)), {LO}, {HI}) on envelope "
              f"base (mc ${sized_mc * d:+.2f}/hr)")
        print(f"  {'win':>5} {'beta':>5} | {'raw $/hr':>9} | {'mc $/hr':>8} {'vs base':>8} | "
              f"{'shuf (20s)':>12} | {'rev $/hr':>8}")
        for w in JWINS:
            jz = rolling_z(joins[w])
            for b in BETAS:
                sz = np.clip(base_sizes * (1.0 + b * jz), LO, HI)
                t_mc = mc(net, sz)
                shf = []
                for _ in range(20):
                    perm = rng.permutation(len(jz))
                    sz_s = np.clip(base_sizes * (1.0 + b * jz[perm]), LO, HI)
                    shf.append(mc(net, sz_s))
                sz_r = np.clip(base_sizes * (1.0 - b * jz), LO, HI)
                print(f"  {w // 10:>4}s {b:>5.2f} | {raw_usd(net, sz, hrs):>+9.2f} | "
                      f"{t_mc * d:>+8.2f} {(t_mc - sized_mc) * d:>+8.2f} | "
                      f"{np.mean(shf) * d:>+8.2f}±{np.std(shf) * d:>4.2f} | {mc(net, sz_r) * d:>+8.2f}")


if __name__ == "__main__":
    main()
