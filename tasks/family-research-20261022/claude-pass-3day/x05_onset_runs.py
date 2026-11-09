"""One-sided runs in the 20 s completed-group flow ratio and where the recorded Native dipole births sit inside them.  Measurements only.
A run = consecutive series seconds with |ratio| == 1 and the same sign.  Onset = first second of a run.  Writes crossday/x05_onsets_per_day.csv, x05_birth_position_in_run.csv, x05_onset_hold_rules.csv."""
import gzip, json, os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = f'{HERE}/..'; OUT = f'{HERE}/crossday'
def paths(d):
    if d == '20231018': return f'{ROOT}/october18-candidate-inputs.jsonl.gz', f'{ROOT}/research-atlas-v2/dipole-completed-group-flow.csv.gz'
    return f'{ROOT}/replay-comparison/{d}/candidate-inputs.jsonl.gz', f'{ROOT}/replay-comparison/{d}/research-atlas-v2/dipole-completed-group-flow.csv.gz'
res, pos, hold = [], [], []
for d in ('20231002', '20231003', '20231017', '20231018'):
    cp, sp = paths(d); rows = [json.loads(l) for l in gzip.open(cp, 'rt')]
    ev = np.array(sorted(r['birth_second'] for r in rows if 'birth_second' in r and 'recorded_operands' in r))
    S = pd.read_csv(sp); r = S.ratio.to_numpy(float); sec = S.second.to_numpy(); ab = np.abs(r); one = ab == 1; sg = np.sign(r)
    contiguous = np.r_[False, np.diff(sec) == 1]; same = np.r_[False, one[1:] & one[:-1] & (sg[1:] == sg[:-1])] & contiguous
    onset = one & ~same; run_id = np.cumsum(onset) * one; idx_run_start = np.where(onset)[0]
    # position of each second inside its run (0 = onset)
    posn = np.zeros(len(S), int); 
    for k in range(1, len(S)):
        posn[k] = posn[k - 1] + 1 if same[k] else 0
    idx = np.searchsorted(sec, ev); ok = (idx < len(sec)) & (sec[np.minimum(idx, len(sec) - 1)] == ev); assert ok.all()
    on_birth = onset[idx]; p = posn[idx]
    res.append(dict(day=d, births=len(ev), series_seconds=len(S), seconds_abs_ratio_1=int(one.sum()), runs=int(onset.sum()), births_on_onset=int(on_birth.sum()), births_not_on_onset=int((~on_birth).sum()),
                    onsets_that_are_births=int(np.isin(sec[onset], ev).sum()), onsets_not_births=int((~np.isin(sec[onset], ev)).sum()), runs_containing_a_birth=int(len(np.unique(run_id[idx]))), runs_containing_more_than_one_birth=int((np.bincount(run_id[idx])[1:] > 1).sum())))
    vc = pd.Series(p).value_counts().sort_index()
    for k, c in vc.items(): pos.append(dict(day=d, seconds_since_run_onset=int(k), births=int(c)))
    # onset-based hold rules
    ons = sec[onset]
    for h in (1, 20, 30, 40, 45, 50, 60, 100):
        last = -10**9; got = []
        for s_ in ons:
            if s_ - last >= h: got.append(s_); last = s_
        hold.append(dict(day=d, hold_s=h, rule_births=len(got), recorded_births=len(ev), exact_overlap=len(set(got) & set(ev)), recorded_not_produced=len(set(ev) - set(got)), produced_not_recorded=len(set(got) - set(ev))))
R = pd.DataFrame(res); R.to_csv(f'{OUT}/x05_onsets_per_day.csv', index=False); pd.DataFrame(pos).to_csv(f'{OUT}/x05_birth_position_in_run.csv', index=False); H = pd.DataFrame(hold); H.to_csv(f'{OUT}/x05_onset_hold_rules.csv', index=False)
pd.set_option('display.width', 250); print(R.T.to_string()); print(H.to_string(index=False)); P = pd.DataFrame(pos); print(P.pivot(index='seconds_since_run_onset', columns='day', values='births').fillna(0).astype(int).head(30).to_string())
