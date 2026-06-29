"""
_leg2_diagnosis.py — DIAGNOSTIC (not a gate re-run). Why did OD-BOOK leg 2
(turn-net-of-fee) fail while leg 1 (forecast skill) and leg 3 (stability) passed?

The pre-registered verdict is KILL and the sentinel is frozen. This does NOT touch
the gate or change the verdict. It dissects the *mechanism* of the leg-2 failure on
the same TEST block, to decide whether a DIFFERENT (maker-execution) experiment is
worth a fresh pre-registration.

Procedure (matches the committed run's tuned configs):
  - fit champion VAR(p=3, alpha=100) and challenger DMD(energy=0.9999) on TRAIN.
  - one expensive forecast pass over the TEST block → predicted forward log-return
    arrays at h in {1,5,10} for both models, plus realized step returns / mids /
    spreads. Everything after that is vectorized.

Analyses:
  A. magnitude: predicted-move and realized-move bps distributions vs the 22 bps
     taker floor. (Is the signal simply sub-fee?)
  B. direction: sign hit-rate of predicted vs realized next-step (is there real
     directional skill independent of magnitude?)
  C. deadband curve: gross / fees / net / flips / gross-per-flip across deadbands
     (shows the fee-churn structure the single tuned deadband hides).
  D. maker counterfactual: same positions, but (i) fee=0, (ii) maker rebate
     -1 bps/side, (iii) capture half-spread per flip. Does the directional skill
     go net-positive once the taker floor is removed? That isolates execution model
     vs no-signal as the cause.
  E. turn census: how many real >=22 bps swings exist in the test block + realized
     amplitude distribution (connects to S42's "trade only theta>~20 bps swings").
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import book_state          # noqa: E402
import champion            # noqa: E402
import challenger_od       # noqa: E402
import metrics             # noqa: E402
import splits              # noqa: E402

HORIZONS = [1, 5, 10]
FEE_BPS = 22.0
THETA_BPS = 22.0
DEADBANDS = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]


def predicted_fwd_array(model, X, horizon, mid_ret_idx):
    """Predicted cumulative forward log-return at each t over the test block."""
    n = X.shape[0]
    out = np.full(n, np.nan)
    for t in range(model.p - 1, n - horizon):
        hist = X[max(0, t - model.p + 1): t + 1]
        if hist.shape[0] < model.p:
            continue
        out[t] = metrics.predict_fwd_logret(model, hist, horizon, mid_ret_idx)
    return out


def realized_fwd_array(mid, horizon):
    n = len(mid)
    out = np.full(n, np.nan)
    out[: n - horizon] = np.log(mid[horizon:] / mid[:n - horizon])
    return out


def swing_from_pred(pred, deadband_bps):
    db = deadband_bps / 1e4
    pos = np.zeros_like(pred)
    ok = np.isfinite(pred)
    pos[ok & (pred > db)] = 1.0
    pos[ok & (pred < -db)] = -1.0
    return pos


def pnl_breakdown(pos, step_ret, spread_bps, fee_bps, half_spread_capture=False,
                  per_flip_credit_bps=0.0):
    """Vectorized swing PnL. step_ret aligned so pos[t] earns step_ret[t]
    (t -> t+1). Fee charged per flip (any change in position incl. to/from flat).
    Optional maker economics: per_flip_credit_bps (e.g. -? actually a rebate is a
    credit so positive credit) and half-spread capture per flip."""
    n = min(len(pos), len(step_ret))
    p = pos[:n]
    r = step_ret[:n]
    valid = np.isfinite(r)
    gross = float(np.nansum(p * np.where(valid, r, 0.0)) * 1e4)  # bps
    flips_mask = np.abs(np.diff(np.concatenate([[0.0], p]))) > 0
    n_flips = int(np.sum(flips_mask))
    fee = n_flips * fee_bps
    credit = n_flips * per_flip_credit_bps
    spread_credit = 0.0
    if half_spread_capture:
        # a maker that gets filled earns ~half the spread at each entry flip
        flip_idx = np.where(flips_mask)[0]
        flip_idx = flip_idx[flip_idx < len(spread_bps)]
        spread_credit = float(np.sum(0.5 * spread_bps[flip_idx]))
    net = gross - fee + credit + spread_credit
    return {"gross_bps": gross, "n_flips": n_flips, "fee_bps": fee,
            "credit_bps": credit, "spread_credit_bps": spread_credit,
            "net_bps": net, "gross_per_flip": gross / n_flips if n_flips else 0.0}


def pct(a, qs=(50, 75, 90, 95, 99)):
    a = a[np.isfinite(a)]
    return {f"p{q}": float(np.percentile(np.abs(a), q)) for q in qs} if len(a) else {}


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "/tmp/od_book.jsonl.gz"
    bs = book_state.build_state(data)
    print(f"[diag] {bs.n} states, span {(bs.ts[-1]-bs.ts[0])/3600:.2f} h")
    sp = splits.three_way(bs.n, 0.6, 0.2)
    Xtr, Xte = bs.X[sp.train], bs.X[sp.test]
    mid_te = bs.mid[sp.test]
    cols = bs.cols
    mri = cols.index("mid_ret")
    spread_idx = cols.index("spread")
    # spread in bps on the test block
    spread_bps_te = (Xte[:, spread_idx] / mid_te) * 1e4

    champ = champion.fit_var(Xtr, p=3, alpha=100.0)
    chal = challenger_od.fit_dmd(Xtr, rank=None, h=1, energy=0.9999)
    print("[diag] models fit (champ VAR3/a100, chal DMD e0.9999). Forecasting test...")

    step_ret = np.concatenate([np.diff(np.log(mid_te)), [np.nan]])  # r[t] = t->t+1

    report = {"data": os.path.basename(data), "n_test": int(len(mid_te)),
              "fee_bps": FEE_BPS, "models": {}}

    # E. turn census (model-independent)
    turns = metrics.label_turns(mid_te, THETA_BPS)
    amps = []
    for i in range(1, len(turns)):
        amps.append(abs(turns[i][2] / turns[i - 1][2] - 1.0) * 1e4)
    report["turn_census"] = {
        "n_turns_ge_22bps": len(turns),
        "test_len": int(len(mid_te)),
        "turns_per_hour": len(turns) / ((bs.ts[sp.test][-1] - bs.ts[sp.test][0]) / 3600)
        if len(sp.test) > 1 else float("nan"),
        "swing_amp_bps": pct(np.array(amps)) if amps else {},
        "step_ret_bps": pct(step_ret * 1e4),
        "spread_bps": pct(spread_bps_te),
    }

    for name, model in [("champion", champ), ("challenger", chal)]:
        mrep = {}
        for h in HORIZONS:
            pred = predicted_fwd_array(model, Xte, h, mri)
            real = realized_fwd_array(mid_te, h)
            ok = np.isfinite(pred) & np.isfinite(real)
            # B. direction
            hit = float(np.mean(np.sign(pred[ok]) == np.sign(real[ok]))) if ok.any() else float("nan")
            nz = ok & (np.abs(pred) > 0)
            hit_nz = float(np.mean(np.sign(pred[nz]) == np.sign(real[nz]))) if nz.any() else float("nan")
            # A. magnitude
            mag = {"pred_abs_bps": pct(pred * 1e4), "real_abs_bps": pct(real * 1e4)}
            # C. deadband curve (taker, fee=22)
            db_curve = {}
            for db in DEADBANDS:
                pos = swing_from_pred(pred, db)
                db_curve[db] = pnl_breakdown(pos, step_ret, spread_bps_te, FEE_BPS)
            # D. maker counterfactuals at deadband=0 (max signal use) and best-net db
            best_db = max(DEADBANDS, key=lambda d: db_curve[d]["net_bps"])
            pos0 = swing_from_pred(pred, 0.0)
            posb = swing_from_pred(pred, best_db)
            maker = {
                "taker_fee22_db0": db_curve[0.0],
                "taker_fee22_dbBest": {"deadband": best_db, **db_curve[best_db]},
                "maker_fee0_db0": pnl_breakdown(pos0, step_ret, spread_bps_te, 0.0),
                "maker_rebate1bps_db0": pnl_breakdown(pos0, step_ret, spread_bps_te, 0.0,
                                                      per_flip_credit_bps=1.0),
                "maker_halfspread_db0": pnl_breakdown(pos0, step_ret, spread_bps_te, 0.0,
                                                      half_spread_capture=True),
                "maker_fee0_dbBest": {"deadband": best_db,
                                      **pnl_breakdown(posb, step_ret, spread_bps_te, 0.0)},
            }
            mrep[h] = {"hit_rate_all": hit, "hit_rate_nonzero_pred": hit_nz,
                       "n_scored": int(ok.sum()), "magnitude": mag,
                       "deadband_curve_taker22": db_curve, "execution_models": maker}
        report["models"][name] = mrep

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_leg2_diagnosis.json")
    json.dump(json.loads(json.dumps(report, default=float)), open(out, "w"), indent=2)
    print(f"[diag] wrote {out}")

    # console summary
    for name in ("champion", "challenger"):
        print(f"\n=== {name} ===")
        for h in HORIZONS:
            m = report["models"][name][h]
            print(f" h={h:>2}  hit(all)={m['hit_rate_all']:.4f} "
                  f"hit(nz)={m['hit_rate_nonzero_pred']:.4f}  "
                  f"pred|p50|={m['magnitude']['pred_abs_bps'].get('p50',float('nan')):.3f}bps "
                  f"real|p50|={m['magnitude']['real_abs_bps'].get('p50',float('nan')):.3f}bps")
            em = m["execution_models"]
            t0 = em["taker_fee22_db0"]; mk0 = em["maker_fee0_db0"]
            mks = em["maker_halfspread_db0"]
            print(f"       taker22 db0:  gross={t0['gross_bps']:+.1f} flips={t0['n_flips']} "
                  f"net={t0['net_bps']:+.1f}  (gross/flip={t0['gross_per_flip']:+.4f}bps)")
            print(f"       maker  db0:  fee0 net={mk0['net_bps']:+.1f} | "
                  f"+halfspread net={mks['net_bps']:+.1f} "
                  f"(spread_credit={mks['spread_credit_bps']:+.0f})")
    tc = report["turn_census"]
    print(f"\n[turn census] {tc['n_turns_ge_22bps']} turns >=22bps over test "
          f"({tc.get('turns_per_hour',float('nan')):.1f}/h); "
          f"swing amp p50={tc['swing_amp_bps'].get('p50',float('nan')):.1f}bps; "
          f"step|ret| p50={tc['step_ret_bps'].get('p50',float('nan')):.3f}bps; "
          f"spread p50={tc['spread_bps'].get('p50',float('nan')):.2f}bps")


if __name__ == "__main__":
    main()
