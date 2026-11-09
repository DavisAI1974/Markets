"""What the recorded detector operands and the 20 s completed-group flow series say about the Native dipole births, per day.  Measurements only.
Reads each day's candidate inputs (recorded_operands) and dipole-completed-group-flow.csv.gz.  Writes crossday/x02_operands_per_day.csv and x02_hold_rules.csv.
The flow series is the companion observation lens, not the saved action-quote detector substrate (dipole-application-method.json), so it is read as an observation, not as the detector."""
import gzip, json, os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = f'{HERE}/..'; OUT = f'{HERE}/crossday'; os.makedirs(OUT, exist_ok=True)
def paths(d):
    if d == '20231018': return f'{ROOT}/october18-candidate-inputs.jsonl.gz', f'{ROOT}/research-atlas-v2/dipole-completed-group-flow.csv.gz'
    return f'{ROOT}/replay-comparison/{d}/candidate-inputs.jsonl.gz', f'{ROOT}/replay-comparison/{d}/research-atlas-v2/dipole-completed-group-flow.csv.gz'
res = []; hold = []
for d in ('20231002', '20231003', '20231017', '20231018'):
    cp, sp = paths(d); rows = [json.loads(l) for l in gzip.open(cp, 'rt')]
    ops = pd.DataFrame([dict(r['recorded_operands'], top_birth_second=r['birth_second'], top_available_second=r['available_second']) for r in rows if 'recorded_operands' in r and 'birth_second' in r])
    if 'event_second' not in ops.columns:   # Oct 18's operand block is the shorter one: the top-level birth and available seconds stand in
        ops['event_second'] = ops.top_birth_second; ops['available_second'] = ops.top_available_second; ops['detection_lag_seconds'] = ops.available_second - ops.event_second
    same_ids = int((ops.event_second == ops.top_birth_second).sum()) if 'top_birth_second' in ops else -1
    S = pd.read_csv(sp); r = S.ratio.to_numpy(float); sec = S.second.to_numpy(); ab = np.abs(r); idx = np.searchsorted(sec, ops.event_second.to_numpy())
    ev = np.sort(ops.event_second.to_numpy()); gaps = np.diff(ev); dl = ops.detection_lag_seconds.to_numpy(); lag = (ops.available_second - ops.event_second).to_numpy()
    res.append(dict(day=d, candidate_rows=len(rows), births=len(ops), event_second_equals_birth_second=same_ids, series_seconds=len(S), series_ratio_defined=int(np.isfinite(r).sum()), series_abs_ratio_eq_1=int((ab == 1).sum()),
        births_on_abs_ratio_1=int((ab[idx] == 1).sum()), polarity_equals_ratio_sign=int((np.sign(r[idx]) == ops.polarity.to_numpy()).sum()), magnitude_equals_abs_ratio=int(np.isclose(ops.magnitude, ab[idx]).sum()),
        prominence_equals_magnitude_minus_baseline=int(np.isclose(ops.prominence, ops.magnitude - ops.baseline).sum()), threshold_values=str(sorted(ops.threshold.unique().tolist())),
        detection_lag_eq_50=int((dl == 50).sum()), detection_lag_41_49=int(((dl >= 41) & (dl <= 49)).sum()), detection_lag_below_41=int((dl < 41).sum()), detection_lag_min=int(dl.min()),
        available_minus_event_eq_detection_lag=int((lag == dl).sum()), gap_min_s=int(gaps.min()), gap_median_s=float(np.median(gaps)), gaps_below_50=int((gaps < 50).sum()), gap_max_s=int(gaps.max()),
        obs_behind_threshold_min=int(ops.observations_behind_threshold.min()), obs_behind_threshold_max=int(ops.observations_behind_threshold.max()), baseline_min=float(ops.baseline.min()), baseline_max=float(ops.baseline.max())))
    for h in (1, 25, 30, 45, 50, 51, 60, 100):
        last = -10**9; got = []
        for k in np.where(ab == 1)[0]:
            if sec[k] - last >= h: got.append(sec[k]); last = sec[k]
        hold.append(dict(day=d, hold_s=h, rule_births=len(got), recorded_births=len(ev), exact_overlap=len(set(got) & set(ev)), recorded_not_produced=len(set(ev) - set(got)), produced_not_recorded=len(set(got) - set(ev))))
R = pd.DataFrame(res); H = pd.DataFrame(hold); R.to_csv(f'{OUT}/x02_operands_per_day.csv', index=False); H.to_csv(f'{OUT}/x02_hold_rules.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); print(R.T.to_string()); print(H.to_string(index=False))
