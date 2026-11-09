#!/bin/bash
export OD_WORK=/home/claude/work/derived
cd /home/claude/markets/tasks/family-research-20261022/claude-pass-3day
rm -rf /home/claude/work/renders; mkdir -p /home/claude/work/renders
for pair in "20231002 20231003" "20231017 20231018"; do
  for d in $pair; do (OD_SESS=$d python3 -I x12_instance_renders.py /home/claude/work/renders/$d > /home/claude/work/renders/log_$d.txt 2>&1; echo "$(date +%T) $d done rc=$?") & done; wait
done
echo "$(date +%T) ALL RENDERS DONE"
