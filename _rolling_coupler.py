"""_rolling_coupler.py — S41: the FULL 5-step coupler (all steps, in order), rolling over the
book, to hunt the lead/lag REGIME and test the quiet/loud condition.

Greg's rules honored:
  - use our 5-step agnostic coupler, and run ALL 5 STEPS IN ORDER (we call the whole
    `odcore.dipole_trade.trade_coupling_vector`, not a single step).
  - the lead/lag between the operator (book liquidity) and price is NOT random -- find the
    condition that flips it. Prime candidate (Greg + Chat): QUIET vs LOUD (the imbalance
    relaxes cleanly between trades; a trade breaks it).

Per rolling window (5 min = 3000 cells, step 30s = 300 cells), on the BOOK file:
  step1-5 coupler on (a = signed depth-imbalance [the operator], b = signed return [price]):
     -> 15-dim c_i incl. leadlag (step 4): +lag => liquidity LEADS price, -lag => price leads.
  regime conditions measured on the same window:
     quiet_frac   = fraction of snapshots with no trade  (high => quiet/relaxing)
     realized_vol = std of returns
     relax_r2     = OOS-ish AR(1) fit quality of imbalance (high => clean relaxation = quiet)
  TEST: does leadlag (operator leads vs lags price) track quiet/loud?
        hypothesis: operator LEADS when quiet (liquidity withdraws into the calm), LAGS when loud.
"""
from __future__ import annotations
import argparse, json
import numpy as np
from _birth_probe import load_book, to_grid
from odcore.dipole_trade import trade_coupling_vector, FEATURE_NAMES


def ar1_r2(x):
    """In-sample AR(1) fit quality of x (proxy for 'clean relaxation')."""
    if len(x) < 20: return 0.0
    a, b = x[:-1], x[1:]
    if a.std() < 1e-9: return 0.0
    phi = np.cov(a, b)[0, 1] / (a.var() + 1e-12)
    pred = phi * a
    ss_res = np.sum((b - pred) ** 2); ss_tot = np.sum((b - b.mean()) ** 2) + 1e-12
    return max(0.0, 1 - ss_res / ss_tot)


def run(path, win, step, K, render):
    g = to_grid(load_book(path), 0.1)
    n = g["n"]
    depth_imb = (g["bidK"][K] - g["askK"][K]) / (g["bidK"][K] + g["askK"][K] + 1e-12)  # operator (signed)
    ret = np.concatenate([[0.], np.diff(np.log(np.where(g["mid"] > 0, g["mid"], np.nan)))])
    ret = np.nan_to_num(ret)
    ntr = (g["buy"] + g["sell"]) > 0  # snapshot had a trade

    li = FEATURE_NAMES.index("leadlag"); lz = FEATURE_NAMES.index("leadlag_z")
    rows = []
    for s in range(0, n - win, step):
        a = depth_imb[s:s + win]; b = ret[s:s + win]
        c = trade_coupling_vector(a, b, window=40, stride=10, max_lag=15, leadlag_nnull=30)
        if c is None: continue
        rows.append(dict(t=s + win,
                         leadlag=float(c[li]), leadlag_z=float(c[lz]),
                         eq_entropy=float(c[FEATURE_NAMES.index("eq_entropy_frac")]),
                         dipole_r2=float(c[FEATURE_NAMES.index("dipole_r2")]),
                         quiet_frac=float((~ntr[s:s + win]).mean()),
                         vol=float(b.std()),
                         relax_r2=ar1_r2(depth_imb[s:s + win])))
    R = {k: np.array([r[k] for r in rows]) for k in rows[0]}
    nW = len(rows)
    print(f"# rolling 5-step coupler: {nW} windows (win={win} cells={win*0.1/60:.0f}min, step={step*0.1:.0f}s)")
    print(f"# operator = signed depth-imbalance(K={K})  vs  price return.  +leadlag => OPERATOR LEADS price.\n")

    lead = R["leadlag"]
    print(f"lead/lag distribution:  operator LEADS (lag>0): {(lead>0).mean():.1%}   "
          f"LAGS (lag<0): {(lead<0).mean():.1%}   coincident: {(lead==0).mean():.1%}")
    print(f"  mean leadlag = {lead.mean():+.2f} cells ({lead.mean()*0.1:+.2f}s)   "
          f"median = {np.median(lead):+.1f}\n")

    def corr(x, y):
        if x.std() < 1e-9 or y.std() < 1e-9: return 0.0
        return float(np.corrcoef(x, y)[0, 1])
    print("DOES THE LEAD/LAG TRACK THE CONDITION? (corr of leadlag with each regime var)")
    for cond in ("quiet_frac", "vol", "relax_r2"):
        c_all = corr(R[cond], lead)
        # split: operator-leads vs operator-lags windows, mean of the condition
        m_lead = R[cond][lead > 0].mean() if (lead > 0).any() else np.nan
        m_lag = R[cond][lead < 0].mean() if (lead < 0).any() else np.nan
        flag = ""
        if cond in ("quiet_frac", "relax_r2") and m_lead > m_lag: flag = "  <-- LEADS when quieter (hypothesis holds)"
        if cond == "vol" and m_lead < m_lag: flag = "  <-- LEADS when calmer (hypothesis holds)"
        print(f"  {cond:11s}: corr={c_all:+.3f}   mean@lead={m_lead:+.4f}  mean@lag={m_lag:+.4f}{flag}")

    out = dict(path=path, win=win, step=step, K=K, n_windows=nW,
               frac_lead=float((lead > 0).mean()), frac_lag=float((lead < 0).mean()),
               mean_leadlag_s=float(lead.mean() * 0.1),
               corr_leadlag=dict(quiet_frac=corr(R["quiet_frac"], lead),
                                 vol=corr(R["vol"], lead), relax_r2=corr(R["relax_r2"], lead)))
    json.dump(out, open("_rolling_coupler_results.json", "w"), indent=2)
    print("\n[saved] _rolling_coupler_results.json")
    if render: _render(R)


def _render(R):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    t = R["t"] * 0.1 / 60
    fig, ax = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    ax[0].plot(t, R["leadlag"], color="#722ed1", lw=1); ax[0].axhline(0, color="k", lw=0.6)
    ax[0].fill_between(t, 0, R["leadlag"], where=R["leadlag"] > 0, color="#237804", alpha=0.3, label="operator LEADS")
    ax[0].fill_between(t, 0, R["leadlag"], where=R["leadlag"] < 0, color="#cf1322", alpha=0.3, label="price leads")
    ax[0].set_ylabel("leadlag (cells)"); ax[0].legend(fontsize=8, loc="upper left")
    ax[0].set_title("5-step coupler rolling: operator(book liquidity) vs price lead/lag, and the regime")
    ax[1].plot(t, R["quiet_frac"], color="#0050b3", lw=1, label="quiet_frac")
    ax[1].plot(t, R["relax_r2"], color="#08979c", lw=1, label="relax R2")
    ax[1].set_ylabel("quiet / relax"); ax[1].legend(fontsize=8, loc="upper left")
    ax[2].plot(t, R["vol"], color="#d46b08", lw=1, label="realized vol")
    ax[2].set_ylabel("vol"); ax[2].set_xlabel("minutes"); ax[2].legend(fontsize=8, loc="upper left")
    fig.tight_layout(); fig.savefig("_rolling_coupler.png", dpi=110); plt.close(fig)
    print("[render] _rolling_coupler.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="/tmp/book.jsonl.gz")
    ap.add_argument("--win", type=int, default=3000, help="rolling window in cells (3000=5min)")
    ap.add_argument("--step", type=int, default=300, help="step in cells (300=30s)")
    ap.add_argument("--K", type=int, default=5)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    run(a.path, a.win, a.step, a.K, not a.no_render)
