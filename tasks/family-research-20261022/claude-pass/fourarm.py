"""Four-arm comparison on identical eligible rows and identical outcome windows.
Arms: baseline | baseline+flow | baseline+book | baseline+both.   Ridge on standardized features (NaN -> 0 plus a missing flag).
Evaluation: rows are in chronological order and cut into K contiguous blocks.  For test block k (k>=2) the model is fit on rows from blocks < k
whose outcome window ends before block k starts (purge).  Ridge alpha is picked on the last quarter of the (purged) training rows.
Metrics on the test rows: MSE, MAE (raw outcome ticks), and sign agreement among rows with nonzero outcome and nonzero prediction.
Benchmarks: predict zero, predict training mean.  Null: circular shift of the outcome vector against the features (>= min_shift rows), full pipeline.
No cost, fee or execution assumption.  Overlapping windows are handled by purge only; effective independent count is lower than n."""
import numpy as np, pandas as pd

def design(df, cols):
    X = []; names = []
    for c in cols:
        v = df[c].to_numpy(float); miss = np.isnan(v)
        X.append(np.where(miss, np.nan, v)); names.append(c)
        if miss.any(): X.append(miss.astype(float)); names.append(c + '__missing')
    return np.column_stack(X), names

def _fit(Xtr, ytr, alpha):
    mu = np.nanmean(Xtr, axis=0); mu = np.where(np.isnan(mu), 0, mu)
    sd = np.nanstd(Xtr, axis=0); sd = np.where((sd == 0) | np.isnan(sd), 1, sd)
    Z = (np.where(np.isnan(Xtr), mu, Xtr) - mu) / sd
    ym = ytr.mean(); A = Z.T @ Z + alpha * np.eye(Z.shape[1]); b = np.linalg.solve(A, Z.T @ (ytr - ym))
    return mu, sd, b, ym

def _pred(model, X):
    mu, sd, b, ym = model; Z = (np.where(np.isnan(X), mu, X) - mu) / sd; return Z @ b + ym

def run_arm(X, y, start_ns, end_ns, K=5, alphas=(1, 10, 100, 1000), clip=None):
    n = len(y); edges = np.linspace(0, n, K + 1).astype(int); out = []
    for k in range(1, K):
        te = np.arange(edges[k], edges[k + 1]); t_start = start_ns[te[0]]
        tr = np.arange(0, edges[k]); tr = tr[end_ns[tr] < t_start]
        ok_te = ~np.isnan(y[te]); te = te[ok_te]; tr = tr[~np.isnan(y[tr])]
        if len(tr) < 40 or len(te) < 10: continue
        ytr = np.clip(y[tr], -clip, clip) if clip else y[tr]
        cut = int(len(tr) * .75); best = None
        for a in alphas:
            m = _fit(X[tr[:cut]], ytr[:cut], a); e = np.mean((_pred(m, X[tr[cut:]]) - ytr[cut:]) ** 2)
            if best is None or e < best[0]: best = (e, a)
        m = _fit(X[tr], ytr, best[1]); p = _pred(m, X[te]); yt = y[te]
        out.append(dict(block=k + 1, n_train=len(tr), n_test=len(te), alpha=best[1], mse=np.mean((p - yt) ** 2), mae=np.mean(np.abs(p - yt)),
                        mse_zero=np.mean(yt ** 2), mae_zero=np.mean(np.abs(yt)), mse_mean=np.mean((ytr.mean() - yt) ** 2), mae_mean=np.mean(np.abs(ytr.mean() - yt)),
                        sign_n=int(((yt != 0) & (p != 0)).sum()), sign_agree=int(((np.sign(p) == np.sign(yt)) & (yt != 0) & (p != 0)).sum())))
    return pd.DataFrame(out)

def summarize(res):
    t = res.n_test.sum()
    return dict(n_test=int(t), mse=(res.mse * res.n_test).sum() / t, mae=(res.mae * res.n_test).sum() / t, mse_zero=(res.mse_zero * res.n_test).sum() / t,
                mae_zero=(res.mae_zero * res.n_test).sum() / t, mse_mean=(res.mse_mean * res.n_test).sum() / t, mae_mean=(res.mae_mean * res.n_test).sum() / t,
                sign_n=int(res.sign_n.sum()), sign_agree=int(res.sign_agree.sum()))

def four_arms(df, base, flow, book, ycol, K=5, clip=None, nnull=0, min_shift=25, seed=0, extra_both=()):
    df = df.sort_values('start_ns').reset_index(drop=True)
    y = df[ycol].to_numpy(float); s = df.start_ns.to_numpy(); e = df.end_ns.to_numpy()
    arms = {'1_baseline': base, '2_base+flow': base + flow, '3_base+book': base + book, '4_base+both': base + flow + book + list(extra_both)}
    res = {}; per_block = {}; Xs = {}
    for name, cols in arms.items():
        X, _ = design(df, cols); Xs[name] = X
        r = run_arm(X, y, s, e, K=K, clip=clip); per_block[name] = r; res[name] = summarize(r)
    out = pd.DataFrame(res).T
    out['mse_vs_zero'] = out.mse / out.mse_zero; out['mse_vs_mean'] = out.mse / out.mse_mean; out['mae_vs_zero'] = out.mae / out.mae_zero
    out['sign_share'] = out.sign_agree / out.sign_n
    nulls = None
    if nnull:
        rng = np.random.default_rng(seed); n = len(y); rows = []; rows2 = []
        for _ in range(nnull):
            sh = int(rng.integers(min_shift, n - min_shift)); ys = np.roll(y, sh); r = {}; r2 = {}
            for name in arms:
                rr = run_arm(Xs[name], ys, s, e, K=K, clip=clip); sm = summarize(rr); r[name] = sm['mse'] / sm['mse_zero']; r2[name] = sm['sign_agree'] / max(sm['sign_n'], 1)
            rows.append(r); rows2.append(r2)
        nulls = pd.DataFrame(rows); nulls.attrs['sign'] = pd.DataFrame(rows2)
    return out, per_block, nulls, len(df)
