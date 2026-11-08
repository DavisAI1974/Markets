"""Forward-selection stack on the Tier 2 grid (market conditions only).
Candidates: as-of conditions with >=90% coverage.  Transform: percentile rank inside activity quintiles (market condition).  Model: ridge on selected features.
Score: pooled out-of-fold Pearson correlation between prediction and outcome, chronological expanding folds (6 contiguous blocks; fit on earlier blocks, rows purged if their 60 s outcome window crosses the test start).
At each step add the candidate with the best score gain.  Outcome kept in its units (ticks / lots), clipped to +-clip for fitting only.
ts/rec coordinates stay out of the math."""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import rankdata
df = pd.read_parquet('tables/t2_grid.parquet').sort_values('cut_ns').reset_index(drop=True); N = len(df)
df['F_supdiff_5'] = df.F_sup_b_5 - df.F_sup_a_5
OUT = ('dm_', 'am_', 'dbid_', 'dask_', 'dspr_', 'F_'); SKIP = {'cut_ns', 'rec_idx', 'block', 'utc_hour', 'settle_tag', 'mid'}
cand = [c for c in df.columns if c not in SKIP and not c.startswith(OUT) and df[c].notna().mean() >= .9]
act = df.ntr_60.rank(pct=True) + df.qchg_60.rank(pct=True) + df.ntr_20.rank(pct=True); q = pd.qcut(act.rank(method='first'), 5, labels=False).to_numpy()
def sp(a):
    out = np.zeros(N)
    for k in range(5):
        m = q == k; v = a[m]; v = np.where(np.isnan(v), np.nanmedian(v), v); out[m] = (rankdata(v) - .5) / m.sum() - .5
    return out
P = {c: sp(df[c].to_numpy(float)) for c in cand}
K = 6; edges = np.linspace(0, N, K + 1).astype(int); cutns = df.cut_ns.to_numpy()
def oof_score(cols, y, clip):
    X = np.column_stack([np.ones(N)] + [P[c] for c in cols]); preds = np.full(N, np.nan)
    for k in range(1, K):
        te = np.arange(edges[k], edges[k + 1]); tr = np.arange(0, edges[k]); tr = tr[cutns[tr] + 60 * 10**9 < cutns[te[0]]]
        ok = ~np.isnan(y[tr]); tr = tr[ok]; yt = np.clip(y[tr], -clip, clip)
        A = X[tr].T @ X[tr] + 30 * np.eye(X.shape[1]); A[0, 0] -= 30; b = np.linalg.solve(A, X[tr].T @ yt); preds[te] = X[te] @ b
    m = ~np.isnan(preds) & ~np.isnan(y); return np.corrcoef(preds[m], y[m])[0, 1]
rows = []
for yc, clip in (('dm_5', 5), ('dm_20', 8), ('dm_60', 15), ('dspr_5', 5), ('F_supdiff_5', 200), ('am_20', 8), ('F_net_5', 100)):
    y = df[yc].to_numpy(float); chosen = []; best = 0.0
    for step in range(1, 7):
        scores = {c: oof_score(chosen + [c], y, clip) for c in cand if c not in chosen}
        c, s = max(scores.items(), key=lambda kv: kv[1])
        if s - best < 0.002 and step > 1: break
        chosen.append(c); rows.append(dict(outcome=yc, step=step, added=c, oof_corr=s, gain=s - best)); best = s
R = pd.DataFrame(rows); R.to_csv('tables/t2_forward_stack.csv', index=False); pd.set_option('display.width', 160); print(R.round(4).to_string(index=False))
