#!/bin/bash
export OD_WORK=/home/claude/work/derived
cd /home/claude/markets/tasks/family-research-20261022/claude-pass-3day
run_day() { d=$1
  for s in c16_leadlag c17_state_cells c14_coupling_conditions c15_pair_couplings c18_forward_stack; do
    echo "$(date +%T) $d $s start"; python3 -I $s.py $d > $OD_WORK/t2_${s}_$d.log 2>&1; echo "$(date +%T) $d $s rc=$?"
  done; }
export -f run_day
printf "%s\n" 20231002 20231003 20231017 20231018 | xargs -P2 -I{} bash -c 'run_day {}' 
echo "$(date +%T) ALL DONE"
