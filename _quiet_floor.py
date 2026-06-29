"""_quiet_floor.py — S42: use Chat's QUIET relaxation operator as a FLOOR so the dipole stops
firing continuously while it's trend-following (Greg, S42).

Chat's OD run (research/od_book/chat_runs/OD_book_run_1.docx) found the book imbalance obeys a very
clean AR(1) RELAXATION operator that is QUIET AND STILL between trades:
    imb(t+1) = phi*imb(t) + c
    quiet (n_trades=0, ~80% of cells): phi=0.947, OOS R2=0.904   <- the still floor
    trade (n_trades>0):                phi=0.883, OOS R2=0.726   <- disturbed by a real shock

THE IDEA: between trades the imbalance just relaxes smoothly toward its mean. That smooth decay is
the FLOOR — not new information. The directional dipole (book-imbalance LEVEL, S42 PART B) keeps
FIRING through a whole trend because the level stays elevated as it slowly relaxes. So fire the dipole
on the INNOVATION instead:
    floor_hat(t) = phi_quiet*imb(t-1) + c_quiet      (what the quiet relaxation expects)
    innov(t)     = imb(t) - floor_hat(t)             (the part the floor did NOT explain)
innov ~ 0 between trades (smooth bumps absorbed), and spikes only when a real shock breaks the
relaxation. We test three things:
  (1) reproduce Chat's quiet/trade AR(1) split on our 11.67h;
  (2) SMOOTHING: innov is quiet between trades (variance vs raw d_imb), and firing concentrates on
      trade/shock cells rather than firing continuously through trends;
  (3) RETENTION: the floored signal keeps the directional next-move edge (S42 PART B), OOS.
"""
from __future__ import annotations
import argparse, json
import numpy as np
from _liquidity_dive import fwd_cum_return
from _birth_probe import load_book, to_grid


def ar1_fit(x_t, x_t1):
    """LS fit x_t1 = phi*x_t + c; return phi, c, OOS-style R2 on the SAME arrays (caller splits)."""
    if len(x_t) < 50 or x_t.std() < 1e-12:
        return 0.0, 0.0, 0.0
    A = np.vstack([x_t, np.ones_like(x_t)]).T
    (phi, c), *_ = np.linalg.lstsq(A, x_t1, rcond=None)
    pred = phi * x_t + c
    ss_res = np.sum((x_t1 - pred) ** 2); ss_tot = np.sum((x_t1 - x_t1.mean()) ** 2) + 1e-12
    return float(phi), float(c), float(1 - ss_res / ss_tot)


def run(path, K, thr_q, split):
    g = to_grid(load_book(path), 0.1)
    bd, ad = g["bidK"][K], g["askK"][K]
    imb = (bd - ad) / (bd + ad + 1e-12)
    vol = g["buy"] + g["sell"]
    quiet = vol <= 0.0                      # no taker volume in this cell = quiet (Chat: n_trades=0)
    n = len(imb)
    lm = np.log(np.where(g["mid"] > 0, g["mid"], np.nan))
    sret = np.nan_to_num(np.concatenate([[0.], np.diff(lm)]))
    cut = int(n * split)

    # ---- (1) reproduce Chat's quiet/trade AR(1) split ----
    t, t1 = np.arange(n - 1), np.arange(1, n)
    def split_fit(mask_next):
        m = mask_next[1:]                    # condition on the t+1 cell, like Chat
        tr = (t < cut) & m; te = (t >= cut) & m
        phi, c, _ = ar1_fit(imb[t][tr], imb[t1][tr])
        pred = phi * imb[t][te] + c
        ss = np.sum((imb[t1][te] - pred) ** 2); tot = np.sum((imb[t1][te] - imb[t1][te].mean()) ** 2) + 1e-12
        return phi, c, float(1 - ss / tot), int(te.sum())
    phi_all, c_all, r2_all, n_all = split_fit(np.ones(n, bool))
    phi_q, c_q, r2_q, n_q = split_fit(quiet)
    phi_tr, c_tr, r2_tr, n_tr = split_fit(~quiet)
    print(f"# book imbalance AR(1) relaxation operator (K={K}, {n:,} cells @100ms = {n*0.1/3600:.2f}h)")
    print(f"#   {'subset':14}{'phi':>8}{'OOS R2':>9}{'n_test':>10}")
    print(f"    {'all':14}{phi_all:8.4f}{r2_all:9.4f}{n_all:10,}")
    print(f"    {'QUIET (still)':14}{phi_q:8.4f}{r2_q:9.4f}{n_q:10,}   <- the FLOOR operator")
    print(f"    {'trade (loud)':14}{phi_tr:8.4f}{r2_tr:9.4f}{n_tr:10,}")

    # ---- the FLOOR + innovation ----
    floor_hat = np.zeros(n); floor_hat[1:] = phi_q * imb[:-1] + c_q
    innov = imb - floor_hat
    d_imb = np.concatenate([[0.], np.diff(imb)])

    # ---- (2) SMOOTHING: quiet vs trade, and firing during trends ----
    # standardize each firing signal so thresholds are comparable
    def z(x): return x / (x.std() + 1e-12)
    raw_z, innov_z = z(imb), z(innov)
    print(f"\n# SMOOTHING — does the floor go quiet between trades?")
    print(f"   std(raw imbalance)  quiet={imb[quiet].std():.4f}  trade={imb[~quiet].std():.4f}")
    print(f"   std(innovation)     quiet={innov[quiet].std():.4f}  trade={innov[~quiet].std():.4f}  "
          f"(ratio trade/quiet = {innov[~quiet].std()/(innov[quiet].std()+1e-12):.2f}x)")
    print(f"   -> the floor absorbs the smooth between-trade relaxation; innov energy concentrates on trades.")

    # FIRING: a 'firing' = the standardized signal crosses |.|>thr (would trigger an entry).
    # Count firings during TREND stretches (sign-persistent runs of the 1s return) for raw vs innov.
    r1 = np.convolve(sret, np.ones(10), "same")        # ~1s smoothed return -> trend sign
    trend = np.abs(np.convolve(sret, np.ones(50), "same")) > np.quantile(
        np.abs(np.convolve(sret, np.ones(50), "same")), 0.8)  # top-20% sustained-move cells
    def firings(sig_z):
        on = np.abs(sig_z) > thr_q
        # count rising edges (new firings), total on-fraction, and on-fraction during trends
        edges = int(np.sum(on[1:] & ~on[:-1]))
        return edges, float(on.mean()), float(on[trend].mean())
    e_raw, on_raw, ontr_raw = firings(raw_z)
    e_in, on_in, ontr_in = firings(innov_z)
    print(f"\n# FIRING (|standardized signal|>{thr_q}sigma = would trigger): does it stop firing in trends?")
    print(f"   {'signal':12}{'#firings':>10}{'on-frac':>9}{'on-frac@trend':>15}")
    print(f"   {'raw level':12}{e_raw:10,}{on_raw:9.3f}{ontr_raw:15.3f}")
    print(f"   {'innovation':12}{e_in:10,}{on_in:9.3f}{ontr_in:15.3f}")
    print(f"   -> raw level stays ON through trends (high on-frac@trend = keeps firing while riding);")
    print(f"      innovation fires discretely at shocks/turns (lower on-frac@trend).")

    # ---- (3) RETENTION: does the floored signal keep the directional next-move edge? ----
    print(f"\n# RETENTION — directional next-cell edge (OOS test split), raw level vs innovation:")
    print(f"   {'signal':12}{'OOS_r':>8}{'hit%':>7}")
    fwd = fwd_cum_return(sret, 1)
    res = {}
    for nm, sig in [("raw level", imb), ("innovation", innov), ("d_imb", d_imb)]:
        a = sig[cut:n - 1]; b = fwd[cut:n - 1]; m = ~np.isnan(b)
        a, b = a[m], b[m]
        r = float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-12 else 0.0
        nz = (a != 0) & (b != 0)
        hit = float((np.sign(a) == np.sign(b))[nz].mean()) if nz.any() else float("nan")
        res[nm] = dict(oos_r=round(r, 4), hit=round(hit, 4))
        print(f"   {nm:12}{r:+8.3f}{hit*100:7.1f}")
    print(f"\n   reading: direction lives in the LEVEL; the innovation alone dilutes it. So use the floor")
    print(f"   as a GATE (fire on shocks) and keep the LEVEL for direction (below).")

    # ---- (4) THE FLOOR AS A GATE: level for direction, innovation for WHEN to fire ----
    # gate opens only when imbalance breaks the quiet relaxation envelope (a real shock, ~a trade);
    # between trades the smooth relaxation keeps |innov| small -> gate closed -> dipole stays quiet.
    sig_all = innov.std() + 1e-12
    print(f"\n# FLOOR-AS-GATE — fire only when |innov| > k*sigma (a shock breaks the quiet floor):")
    print(f"   {'k*sigma':>8}{'open%':>8}{'open%|quiet':>12}{'open%|trade':>12}{'gated hit%':>11}{'raw hold%':>11}")
    gate_out = {}
    for k in (1.0, 1.5, 2.0):
        gate = np.abs(innov) > k * sig_all
        open_q = float(gate[quiet].mean()); open_t = float(gate[~quiet].mean())
        # directional hit when the gate is open, using the LEVEL's sign
        a = imb[cut:n - 1]; b = fwd_cum_return(sret, 1)[cut:n - 1]; gg = gate[cut:n - 1]
        m = (~np.isnan(b)) & gg & (a != 0) & (b != 0)
        hit_gate = float((np.sign(a[m]) == np.sign(b[m])).mean()) if m.any() else float("nan")
        # raw level "keeps firing" reference: fraction of cells the level itself would hold a position
        raw_hold = float((np.abs(raw_z) > thr_q).mean())
        gate_out[k] = dict(open=float(gate.mean()), open_quiet=open_q, open_trade=open_t,
                           gated_hit=round(hit_gate, 4))
        print(f"   {k:8.1f}{gate.mean():8.3f}{open_q:12.3f}{open_t:12.3f}{hit_gate*100:11.1f}{raw_hold*100:11.1f}")
    print(f"   -> gate opens far more on TRADE cells than QUIET cells (fires on shocks, silent between");
    print(f"      trades); gated hit% tracks the LEVEL's ~{res['raw level']['hit']*100:.0f}% — direction kept, churn cut.")

    out = dict(path=path, K=K, thr_q=thr_q, split=split, gate=gate_out,
               ar1=dict(all=[phi_all, r2_all], quiet=[phi_q, r2_q], trade=[phi_tr, r2_tr]),
               smoothing=dict(std_innov_quiet=float(innov[quiet].std()),
                              std_innov_trade=float(innov[~quiet].std()),
                              std_raw_quiet=float(imb[quiet].std()), std_raw_trade=float(imb[~quiet].std())),
               firing=dict(raw=[e_raw, on_raw, ontr_raw], innov=[e_in, on_in, ontr_in]),
               retention=res)
    json.dump(out, open("_quiet_floor_results.json", "w"), indent=2)
    print("\n[saved] _quiet_floor_results.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="/tmp/book.jsonl.gz")
    ap.add_argument("--K", type=int, default=10, help="depth levels (Chat used all 10)")
    ap.add_argument("--thr_q", type=float, default=1.5, help="firing threshold in sigma")
    ap.add_argument("--split", type=float, default=0.6)
    a = ap.parse_args()
    run(a.path, a.K, a.thr_q, a.split)
