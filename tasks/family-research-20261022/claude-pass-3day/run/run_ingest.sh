#!/bin/bash
set -e
export OD_WORK=/home/claude/work/derived
cd /home/claude/markets/tasks/family-research-20261022/claude-pass-3day
for d in 20231018; do
  f=NG_v0_mbo_$d.dbn.zst; sha=$(python3 -I -c "import json;print(json.load(open('/home/claude/work/tapes/sha.json'))['$f'])")
  python3 -I c00_dbn_to_parquet.py /home/claude/work/tapes/$f $sha $OD_WORK/raw_$d.parquet $OD_WORK/receipt_$d.json > $OD_WORK/c00_$d.log 2>&1
  python3 -I c03_recon_mbo.py $OD_WORK/raw_$d.parquet $OD_WORK/recon_$d.parquet > $OD_WORK/c03_$d.log 2>&1
  python3 -I c01b_groups_from_recon.py $d > $OD_WORK/c01b_$d.log 2>&1
  echo done $d
done
