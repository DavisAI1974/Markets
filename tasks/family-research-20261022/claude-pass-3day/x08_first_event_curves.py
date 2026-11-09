"""Sorted 'recognition minus first event' curves from x07, four days overlaid, for three event types, plus two-sample KS distances between curves (a distance between two empirical distributions; no threshold applied).
Writes crossday/es-first-event-curves.png, crossday/x08_first_event_curve_rows.csv (every plotted value), x08_quantiles.csv, x08_ks_between_curves.csv, x08_reconciliation.csv"""
import os, numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
H = os.path.dirname(os.path.abspath(__file__)); OUT = f'{H}/crossday'; DAYS = ['20231002', '20231003', '20231017', '20231018']; LAB = dict(zip(DAYS, ['Oct 2', 'Oct 3', 'Oct 17', 'Oct 18']))
COL = dict(zip(DAYS, ['#1f77b4', '#c05621', '#2a9d8f', '#b565a7'])); EV = [('k_aggressor_start', 'Aggressor start (first lots in the birth direction)'), ('k_touch_size_change', 'Touch-size change (either side)'), ('k_quote_relocation', 'Quote relocation (best bid or ask price)')]
X = {d: pd.read_csv(f'{H}/tables/dipole/{d}/x07_first_events.csv') for d in DAYS}
f, A = plt.subplots(1, 3, figsize=(15, 4.8)); rec = []; rowsout = []; Y = {}
for a, (c, ttl) in zip(A, EV):
    for d in DAYS:
        x = X[d]; ok = x[c] >= 0; y = np.sort((x.delay_s - x[c])[ok].to_numpy()); Y[(c, d)] = y
        a.plot(np.arange(len(y)), y, color=COL[d], lw=1.3, marker='.', ms=2, label=f'{LAB[d]}: {len(x)} rows / {len(y)} plotted / {int((~ok).sum())} no event')
        rec.append(dict(event=c, day=d, rows=len(x), points_plotted=len(y), no_event_within_horizon=int((~ok).sum()), rows_eq_plotted_plus_none=bool(len(x) == len(y) + int((~ok).sum()))))
        rowsout += [dict(event=c, day=d, order=i, y=float(v)) for i, v in enumerate(y)]
    a.axhline(0, color='#718096', lw=.7); a.set_title(ttl, loc='left', fontsize=9); a.set_xlabel('Ordered observation (each day sorted separately)'); a.grid(color='#e2e8f0', lw=.6); a.legend(fontsize=7, frameon=False, loc='lower right')
A[0].set_ylabel('Recognition minus first event (seconds)\n(first event searched from the birth-second start boundary)')
f.suptitle('My analog of the first-event curves: all covered candidates, four days overlaid. Original values and ranks, points joined without smoothing.', x=.01, ha='left', fontsize=10); f.tight_layout(rect=(0, 0, 1, .95)); f.savefig(f'{OUT}/es-first-event-curves.png', dpi=130); plt.close(f)
pd.DataFrame(rec).to_csv(f'{OUT}/x08_reconciliation.csv', index=False); pd.DataFrame(rowsout).to_csv(f'{OUT}/x08_first_event_curve_rows.csv', index=False)
def ks(a, b):
    g = np.sort(np.concatenate([a, b])); return float(np.max(np.abs(np.searchsorted(np.sort(a), g, side='right') / len(a) - np.searchsorted(np.sort(b), g, side='right') / len(b))))
Q = []; 
for (c, d), y in Y.items(): Q.append(dict(event=c, day=d, n=len(y), **{f'p{q}': float(np.percentile(y, q)) for q in (1, 5, 10, 25, 50, 75, 90, 95, 99)}, min=float(y.min()), max=float(y.max()), share_negative=float(np.mean(y < 0)), share_between_45_and_55=float(np.mean((y >= 45) & (y <= 55)))))
pd.DataFrame(Q).to_csv(f'{OUT}/x08_quantiles.csv', index=False)
K = []; names = [(c, d) for c, _ in EV for d in DAYS]
for i, (c1, d1) in enumerate(names):
    for (c2, d2) in names[i + 1:]: K.append(dict(curve_a=f'{c1[2:]} {LAB[d1]}', curve_b=f'{c2[2:]} {LAB[d2]}', ks_distance=ks(Y[(c1, d1)], Y[(c2, d2)]), same_event=c1 == c2, same_day=d1 == d2))
K = pd.DataFrame(K); K.to_csv(f'{OUT}/x08_ks_between_curves.csv', index=False)
pd.set_option('display.width', 250); print(pd.DataFrame(Q).round(1).to_string(index=False))
print(pd.DataFrame(rec).to_string(index=False))
# the user's question: is Oct 3 quote relocation closer to the aggressor curves than the other days' quote relocation curves are
q3 = 'quote_relocation Oct 3'
for dd in DAYS:
    print('quote', LAB[dd], 'vs aggressor of each day:', {LAB[e]: round(ks(Y[('k_quote_relocation', dd)], Y[('k_aggressor_start', e)]), 3) for e in DAYS})
print('quote vs quote:', K[(K.same_event) & K.curve_a.str.startswith('quote')].round(3).to_string(index=False))
print('aggressor vs aggressor:', K[(K.same_event) & K.curve_a.str.startswith('aggressor')].round(3).to_string(index=False))
