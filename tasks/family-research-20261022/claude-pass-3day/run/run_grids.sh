#!/bin/bash
export OD_WORK=/home/claude/work/derived
cd /home/claude/markets/tasks/family-research-20261022/claude-pass-3day
echo "$(date +%T) grids start"
printf "%s\n" 20231001 20231002 20231003 20231016 20231017 | xargs -P2 -I{} sh -c 'python3 -I c12_tier2_build.py {} > $OD_WORK/c12_{}.log 2>&1; echo "$(date +%T) grid {} done: $(tail -1 $OD_WORK/c12_{}.log)"'
for s in 20231002 20231003 20231017; do OD_SESS=$s python3 -I c24a2_groupclose_controls.py; done
for d in 20231001 20231002 20231003 20231016 20231017; do
  OD_CUTS=$OD_WORK/gc_cuts_$d.npy OD_OUT=$OD_WORK/gc_grid_$d.parquet python3 -I c12_tier2_build.py $d > $OD_WORK/c12gc_$d.log 2>&1 & 
  [ $(jobs -r | wc -l) -ge 2 ] && wait -n
done; wait
echo "$(date +%T) gc grids done"
