"""Dipole cohort, step 1: turn the 863 archived Native candidates into as-of decision cutoffs on my reconstructed books.
The candidate file supplies only WHERE to cut (a strict prebirth cutoff and the recognition clock).  Ids, birth seconds, cursors and clocks are provenance.
Codex's member runs from 2023-10-17 22:00 UTC to 2023-10-18 21:00 UTC; my tapes are UTC days, so a candidate is served by the tape that holds its whole window:
  pre  = birth_second start minus 1 ns (strictly before the birth second)
  rec  = recognition receive time (the clock at which the candidate became visible)
A candidate is covered by a tape when pre >= tape start + 600 s (the grid warm-up) and rec + 60 s <= the tape's last group close.
Output: /home/claude/work/derived/cohort_cuts_<tape>_<pre|rec>.npy and tables/dipole/t6_cohort_coverage.csv"""
import sys; sys.path.insert(0, '.')
from odcfg import *
import gzip, json, numpy as np, pandas as pd, os
S = 10**9
rows = [json.loads(l) for l in gzip.open(f'{HERE}/../october18-candidate-inputs.jsonl.gz', 'rt')]
tapes = {}
for d in ('20231017', '20231018'):
    z = np.load(groups(d)); tapes[d] = (int(z['recv_ns'][0]), int(z['recv_ns'][-1]))
out = []
for k, r in enumerate(rows):
    pre = r['birth_second'] * S - 1; rec = int(r['recognition_receive_ns']); tape = None
    for d, (a, b) in tapes.items():
        if pre >= a + 600 * S and rec + 60 * S <= b: tape = d
    out.append(dict(row=k, tape=tape if tape else 'none', pre_ns=pre, rec_ns=rec))
cov = pd.DataFrame(out); cov['uncovered_reason'] = np.where(cov.tape == 'none', 'seam_or_warmup', '')
os.makedirs(f'{HERE}/tables/dipole', exist_ok=True)
for d in tapes:
    s = cov[cov.tape == d]
    np.save(f'{WORK}/cohort_cuts_{d}_pre.npy', s.pre_ns.to_numpy()); np.save(f'{WORK}/cohort_cuts_{d}_rec.npy', s.rec_ns.to_numpy())
cov.to_csv(f'{HERE}/tables/dipole/t6_cohort_coverage.csv', index=False)
print(cov.tape.value_counts().to_dict(), 'total', len(cov))
