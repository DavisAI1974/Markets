"""Dipole cohort, control pool anchored at group closes.  A recognition is always a completed-group close (snapshot age 0), and a 3 s grid cut is an arbitrary time
(snapshot age > 0); activity clusters in time, so the next-second behaviour after a group close differs from the next-second behaviour after an arbitrary time.
Forward controls therefore use random group closes of the same tape: 40,000 per tape, same feature/outcome code (c12 with explicit cutoffs).
Usage: python3 -I c24a2_groupclose_controls.py   -> /home/claude/work/derived/gc_cuts_<d>.npy ; then run c12 with OD_CUTS to make gc_grid_<d>.parquet"""
import sys; sys.path.insert(0, '.')
from odcfg import *
import numpy as np
S = 10**9; N = 40000
for d in ('20231017', '20231018'):
    z = np.load(groups(d)); r = z['recv_ns']; ok = np.where((r >= r[0] + 600 * S) & (r <= r[-1] - 660 * S))[0]
    rng = np.random.default_rng(3); pick = np.sort(rng.choice(ok, size=N, replace=False)); np.save(f'{WORK}/gc_cuts_{d}.npy', r[pick]); print(d, len(ok), 'sampled', N)
