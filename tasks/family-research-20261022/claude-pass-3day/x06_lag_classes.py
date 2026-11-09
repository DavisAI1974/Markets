"""Candidates grouped by how the recorded detection lag relates to the seconds since the one-sided run onset in the 20 s flow series.  Measurements only.
Classes (mutually exclusive, in this order): onset_lag50 (birth on run onset, lag 50), inside_lag50 (birth inside a run, lag 50), inside_lag_eq_50_minus_pos (birth inside a run, lag + seconds-since-onset = 50),
onset_lag_lt50 (birth on run onset, lag < 50), inside_other.  Per class: n, recognition delay percentiles, birth-axis oriented-change shares and first-move share at the birth second.
Writes crossday/x06_lag_classes.csv and x06_lag_class_paths.csv (every candidate: day, row, class, pos, lag, delay)."""
import gzip, json, os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = f'{HERE}/..'; OUT = f'{HERE}/crossday'; W = '/home/claude/work/derived'
def paths(d):
    if d == '20231018': return f'{ROOT}/october18-candidate-inputs.jsonl.gz', f'{ROOT}/research-atlas-v2/dipole-completed-group-flow.csv.gz'
    return f'{ROOT}/replay-comparison/{d}/candidate-inputs.jsonl.gz', f'{ROOT}/replay-comparison/{d}/research-atlas-v2/dipole-completed-group-flow.csv.gz'
allr, summ = [], []
for d in ('20231002', '20231003', '20231017', '20231018'):
    cp, sp = paths(d); rows = [json.loads(l) for l in gzip.open(cp, 'rt')]
    S = pd.read_csv(sp); r = S.ratio.to_numpy(float); sec = S.second.to_numpy(); one = np.abs(r) == 1; sg = np.sign(r)
    same = np.r_[False, one[1:] & one[:-1] & (sg[1:] == sg[:-1])] & np.r_[False, np.diff(sec) == 1]; onset = one & ~same
    posn = np.zeros(len(S), int)
    for k in range(1, len(S)): posn[k] = posn[k - 1] + 1 if same[k] else 0
    z = np.load(f'{W}/{d}/x03_cohort_birth.npz'); ks = z['ks']; mo = z['mid_o']; rw = z['row']
    bs = np.array([rows[k]['birth_second'] for k in rw]); lag = np.array([rows[k]['available_second'] - rows[k]['birth_second'] for k in rw]); delay = np.array([(rows[k]['recognition_receive_ns'] - rows[k]['birth_second'] * 10**9) / 1e9 for k in rw])
    idx = np.searchsorted(sec, bs); ok = sec[np.minimum(idx, len(sec) - 1)] == bs
    pos = np.where(ok, posn[np.minimum(idx, len(sec) - 1)], -1); ons = np.where(ok, onset[np.minimum(idx, len(sec) - 1)], False)
    cl = np.where(ons & (lag == 50), 'onset_lag50', np.where(~ons & (lag == 50), 'inside_lag50', np.where(~ons & (lag + pos == 50), 'inside_lag_eq_50_minus_pos', np.where(ons & (lag < 50), 'onset_lag_lt50', 'inside_other'))))
    df = pd.DataFrame(dict(day=d, row=rw, cls=cl, pos=pos, lag=lag, delay_s=delay)); allr.append(df)
    for c in ['onset_lag50', 'inside_lag50', 'inside_lag_eq_50_minus_pos', 'onset_lag_lt50', 'inside_other']:
        m = cl == c; n = int(m.sum())
        if n == 0: continue
        o = dict(day=d, cls=c, n=n, share_of_day=n / len(cl), delay_p5=np.percentile(delay[m], 5), delay_p25=np.percentile(delay[m], 25), delay_p50=np.percentile(delay[m], 50), delay_p75=np.percentile(delay[m], 75), delay_p95=np.percentile(delay[m], 95), lag_min=int(lag[m].min()), lag_max=int(lag[m].max()), pos_min=int(pos[m].min()), pos_max=int(pos[m].max()))
        for k in (-20, -10, 1, 5, 20, 60, 160):
            v = mo[m, list(ks).index(k)]; o[f'pos_k{k}'] = float(np.nanmean(v > 0)); o[f'neg_k{k}'] = float(np.nanmean(v < 0))
        first = np.where((mo[m][:, list(ks).index(0) + 1:] != 0).any(1), (mo[m][:, list(ks).index(0) + 1:] != 0).argmax(1), -1); o['first_move_at_birth_second'] = float(np.mean(first == 0)); o['no_move_within_160s'] = float(np.mean(first < 0))
        summ.append(o)
A = pd.concat(allr, ignore_index=True); A.to_csv(f'{OUT}/x06_lag_class_paths.csv', index=False); S_ = pd.DataFrame(summ); S_.to_csv(f'{OUT}/x06_lag_classes.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
print(pd.crosstab(A.cls, A.day, margins=True).to_string()); print(S_[['day', 'cls', 'n', 'delay_p5', 'delay_p50', 'delay_p95', 'pos_k1', 'neg_k1', 'pos_k60', 'neg_k60', 'pos_k-10', 'neg_k-10', 'first_move_at_birth_second']].round(3).to_string(index=False))
