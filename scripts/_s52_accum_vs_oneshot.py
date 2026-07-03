"""_s52_accum_vs_oneshot.py — S52 head-to-head: Greg's accumulate-at-the-turn vs the deployed one-shot.

Scores odcore/swing_accum (two-phase: starter -> confirm -> all-in remainder; fee-aware unload; quick
dump on failures) against the validated one-shot (simulate_swing_maker + eligibility-corrected capacity)
per cell x fee tier x deploy size, on the Coinbase books AND the NEW Bybit venue books (one 5.83h
window — PROVISIONAL, per-cell rule; hypotheses to confirm as the cron accrues).

TURN SELECTION (Greg: "eliminate the noise — not hit lift hit lift over tiny movements; this is where
the dipole comes in") is implemented on two axes, both causal:
  - DETECTOR SCALE: detect_flips at REV in {0.1 (deployed), 0.25, 0.5} — a coarser zigzag IS the
    swing-size filter (fewer, bigger swings by construction; the smoke test showed a gate on the fine
    196/hr stream correctly rejects ~every turn: 2bps swings cannot pay an accumulate cycle).
  - DIPOLE GATE at the PIVOT: odcore.info_dipole.divergence on the pre-pivot window — flow OPPOSING the
    drift into the pivot + EXHAUSTING (the S36 64%-reversal two-factor read). Entries only; exits never
    gated. CONTROL: the same gate shuffled across flips (same pass-rate, no information).
  - REVERSED-SIDE CONTROL: sides inverted under the dipole gate — if reversed wins, the model class is
    broken (the S51 disqualifier); report, don't deploy.

FILL-OPTIMISM TIERS: the one-shot baseline's per-leg bps are front-of-queue (its production assumption),
so the primary accum rows run queue_frac=0 (same tier — apples to apples) with price-eligibility ON for
both sides (the S52 correction). A queue_frac=1 row at the middle size gives the pessimistic bracket.

Metrics per arm: $/hr, legs/hr, win%, confirmed/dumped fractions, med winner vs loser NOTIONAL (the
loser-truncation claim — Greg's design goal), VW add-height above the turn (the S40 crescendo headwind),
maker $/hr (Bybit MM maker-share qualification input).
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker
from odcore.swing_accum import simulate_swing_accum
from odcore.info_dipole import divergence
from _capacity_model import _leg_caps, _dollars, FLOW_W, WFLIP, DIVW

CELLS = [
    ("sol_coinbase", "/tmp/sol_coinbase_book.jsonl.gz", 1, 300,
     [("mk0", 0.0, 5.0), ("mk-1", -1.0, 5.0)]),
    ("doge_coinbase", "/tmp/doge_coinbase_book.jsonl.gz", 1, 600,
     [("mk0", 0.0, 5.0), ("mk-1", -1.0, 5.0)]),
    ("xrp_coinbase", "/tmp/xrp_coinbase_book.jsonl.gz", 1, 300,
     [("mk0", 0.0, 5.0), ("mk-1", -1.0, 5.0)]),
    ("eth_coinbase", "/tmp/eth_coinbase_book.jsonl.gz", 1, 300,
     [("mk0", 0.0, 5.0), ("mk-1", -1.0, 5.0)]),
    ("btc_coinbase", "/tmp/btc_coinbase_book.jsonl.gz", 10, 300,
     [("mk0", 0.0, 5.0), ("mk-1", -1.0, 5.0)]),
    ("sol_bybit", "/tmp/sol_bybit_book.jsonl.gz", 1, 300,
     [("mk+2", 2.0, 5.5), ("mk0", 0.0, 5.5), ("mk-0.5", -0.5, 5.5), ("mk-1.25", -1.25, 5.5)]),
    ("eth_bybit", "/tmp/eth_bybit_book.jsonl.gz", 1, 300,
     [("mk+2", 2.0, 5.5), ("mk0", 0.0, 5.5), ("mk-0.5", -0.5, 5.5), ("mk-1.25", -1.25, 5.5)]),
]
SIZES = [1_000.0, 5_000.0]   # Greg: drop $25k for now
REVS = [("fine", 0.1), ("mid", 0.25), ("coarse", 0.5)]
ZIG_K = 4.0   # theta = ZIG_K x (half_spread + taker) bps — the S36b minimum-tradeable-swing arithmetic


def _price_zigzag(mid, theta_bps):
    """Causal price zigzag: a turn is CONFIRMED when price reverses theta off the running extreme.
    Returns [(confirm_idx, pivot_idx, side)] with side +1 = valley (go long), matching detect_flips."""
    th = theta_bps / 1e4
    flips = []
    n = len(mid)
    lo_i = hi_i = 0
    mode = 0   # 0 = undetermined, +1 tracking high (last turn was valley), -1 tracking low
    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if mode >= 0 and m <= mid[hi_i] * (1 - th):     # reversal down off the high -> PEAK confirmed
            flips.append((t, hi_i, -1)); mode = -1; lo_i = t
        elif mode <= 0 and m >= mid[lo_i] * (1 + th):   # reversal up off the low -> VALLEY confirmed
            flips.append((t, lo_i, +1)); mode = +1; hi_i = t
    return flips


def _dipole_gate(flips, mid, buy, sell):
    """Causal per-flip gate at the PIVOT: flow opposing the drift into the pivot + exhausting (S36)."""
    g = np.zeros(len(flips), bool)
    for k, (ci, p, _s) in enumerate(flips):
        p = int(p)
        lo = max(0, p - DIVW)
        if p - lo < 12:
            continue
        drift = float(mid[p] - mid[lo])
        d = divergence(buy[lo:p + 1], sell[lo:p + 1], drift)
        if d is not None and d.get("opposing") and d.get("exhausting"):
            g[k] = True
    return g


def run_cell(label, path, K, grace, tiers):
    if not os.path.exists(path):
        return None
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    tape_hr = float(np.sum((buy + sell) * mid)) / hrs
    lean = lean_series(buy, sell, WFLIP)
    out = dict(cell=label, hrs=hrs, spread_bps=2 * hs, tape_hr=tape_hr, scales={})

    theta = ZIG_K * (hs + tiers[0][2])
    scale_streams = [(sname, rev, detect_flips(lean, rev)[0]) for sname, rev in REVS]
    scale_streams.append((f"zigzag{theta:.0f}bp", None, _price_zigzag(mid, theta)))
    for sname, rev, allf in scale_streams:
        if len(allf) < 10:
            continue
        sw = [abs(mid[int(b[0])] - mid[int(a[0])]) / mid[int(a[0])] * 1e4
              for a, b in zip(allf[:-1], allf[1:])]
        gdip = _dipole_gate(allf, mid, buy, sell)
        rng = np.random.default_rng(7)
        gshuf = rng.permutation(gdip)
        srow = dict(rev=rev, n_flips=len(allf), turns_hr=len(allf) / hrs,
                    med_swing=float(np.median(sw)), dip_pass=float(gdip.mean()), tiers={})

        for (tl, mk, tk) in tiers:
            tier = {}
            # one-shot baseline at THIS scale (deployed detector = fine)
            res1 = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                                        maker_fee_bps=mk, taker_fee_bps=tk, cover_grace=grace)
            nets1 = np.asarray([float(l.net_bps) for l in res1.legs])
            if len(nets1):
                ones = np.ones_like(nets1)
                caps_r, _ = _leg_caps(res1.legs, mid, buy, sell, bb, ba, window=None)
                tier["oneshot"] = {int(S): _dollars(nets1, ones, caps_r, hrs, S) for S in SIZES}
            else:
                tier["oneshot"] = {}
            arms = {}
            for gname, gmask in (("ungated", None), ("dipole", gdip), ("shuffle", gshuf)):
                for S in SIZES:
                    r = simulate_swing_accum(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                                             maker_fee_bps=mk, taker_fee_bps=tk, S_max=S,
                                             unload_grace=grace, queue_frac=0.0,
                                             entry_ok=gmask, arm=f"{gname}/S{int(S)}")
                    arms[f"{gname}/S{int(S)}"] = dict(
                        dphr=r.net_usd / hrs, legs_hr=r.n_legs / hrs, win=r.win_frac,
                        conf=r.n_confirmed / max(1, r.n_legs), dump=r.n_dumped / max(1, r.n_legs),
                        med_win_not=r.med_win_notional, med_loss_not=r.med_loss_notional,
                        maker_hr=r.maker_usd / hrs,
                        add_h=float(np.mean([l.add_height_bps for l in r.legs])) if r.legs else 0.0)
            # honest-queue bracket + reversed control, middle size, dipole gate
            rq = simulate_swing_accum(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                                      maker_fee_bps=mk, taker_fee_bps=tk, S_max=SIZES[1],
                                      unload_grace=grace, queue_frac=1.0, entry_ok=gdip, arm="q1")
            arms["Q1/dipole/S5000"] = dict(dphr=rq.net_usd / hrs, legs_hr=rq.n_legs / hrs, win=rq.win_frac)
            rf = [(c, p, -s) for (c, p, s) in allf]
            rr = simulate_swing_accum(mid, bb, ba, buy, sell, rf, half_spread_bps=hs,
                                      maker_fee_bps=mk, taker_fee_bps=tk, S_max=SIZES[1],
                                      unload_grace=grace, queue_frac=0.0, entry_ok=gdip, arm="rev")
            arms["REV/dipole/S5000"] = dict(dphr=rr.net_usd / hrs, legs_hr=rr.n_legs / hrs, win=rr.win_frac)
            tier["accum"] = arms
            srow["tiers"][tl] = tier
        out["scales"][sname] = srow
    return out


def main():
    print("=== S52 head-to-head: ACCUMULATE (Greg) vs ONE-SHOT (deployed), corrected fills ===")
    print("    queue tier: primary rows front-of-queue (== one-shot optimism), Q1 = honest bracket\n")
    results = []
    for spec in CELLS:
        r = run_cell(*spec)
        if r is None:
            print(f"[{spec[0]}] no book\n"); continue
        results.append(r)
        print(f"[{r['cell']}]  {r['hrs']:.1f}h  spread {r['spread_bps']:.2f}bps  tape ${r['tape_hr']/1e6:.1f}M/hr")
        for sname, srow in r["scales"].items():
            print(f"  scale {sname} (REV={srow['rev']}): {srow['turns_hr']:.0f} turns/hr, "
                  f"med swing {srow['med_swing']:.1f}bps, dipole passes {srow['dip_pass']*100:.0f}%")
            for tl, tier in srow["tiers"].items():
                osr = "  ".join(f"S{k}: {v:+.1f}" for k, v in tier["oneshot"].items())
                print(f"    [{tl}] one-shot(rest) $/hr:  {osr}")
                for gname in ("ungated", "dipole", "shuffle"):
                    row = "  ".join(f"S{int(S)}: {tier['accum'][f'{gname}/S{int(S)}']['dphr']:+.1f}"
                                    for S in SIZES)
                    a = tier["accum"][f"{gname}/S5000"]
                    print(f"       accum {gname:7s} $/hr: {row}   (legs/hr {a['legs_hr']:.1f}, "
                          f"win {a['win']*100:.0f}%, conf {a['conf']*100:.0f}%, dump {a['dump']*100:.0f}%, "
                          f"W/L not {a['med_win_not']:.0f}/{a['med_loss_not']:.0f}, addH {a['add_h']:.1f})")
                q1 = tier["accum"]["Q1/dipole/S5000"]; rv = tier["accum"]["REV/dipole/S5000"]
                print(f"       Q1(honest queue) dipole/S5k: {q1['dphr']:+.1f} $/hr   |   "
                      f"CONTROL reversed dipole/S5k: {rv['dphr']:+.1f} $/hr (win {rv['win']*100:.0f}%)")
        print()
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "_s52_accum_vs_oneshot_results.json"), "w") as f:
        json.dump(results, f, indent=2, default=float)


if __name__ == "__main__":
    main()
