#!/bin/bash
# usage: run_session.sh <session>
set -e
export OD_WORK=/home/claude/work/derived OD_SESS=$1
cd /home/claude/markets/tasks/family-research-20261022/claude-pass-3day
python3 -I c24a_cohort_cuts.py
CW=$OD_WORK/$1
for d in $(python3 -I -c "
import sys; sys.path.insert(0,'.')
from odcfg import *
print(' '.join(TAPES))"); do
  for k in pre rec; do
    [ -f $CW/cohort_cuts_${d}_$k.npy ] || continue
    n=$(python3 -I -c "import numpy as np;print(len(np.load('$CW/cohort_cuts_${d}_$k.npy')))")
    [ "$n" -gt 0 ] || continue
    OD_CUTS=$CW/cohort_cuts_${d}_$k.npy OD_OUT=$CW/cohort_grid_${d}_$k.parquet python3 -I c12_tier2_build.py $d | tail -1
  done
done
python3 -I c24b_dipole_cohort.py > $CW/c24b.log 2>&1
python3 -I c24c_dipole_cases.py > $CW/c24c.log 2>&1
python3 -I c24d_dipole_charts.py > $CW/c24d.log 2>&1
echo session $1 complete
