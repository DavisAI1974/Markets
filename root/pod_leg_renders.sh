#!/bin/bash
# ROOT: the trade leg pictures of all four trade days on ONE pod, every trade day's program started together and
# pinned to its own CPUs (Greg, 2026-11-18: the runs go on pods, helpers pinned to CPUs, everything in one launch).
# The pod's own command starts the file server on /root/work/out and clones the code; this does the rest. No key is
# on the pod and it writes nothing to git: the session fetches every file and proves it (root/pod_fetch.py, with
# the address <pod>/d<trade day>).
#
#   bash root/pod_leg_renders.sh <code commit> [what root.leg_renders is asked for, e.g. --random 10]
set -u
COMMIT=$1; shift
WORK=/root/work; OUT=$WORK/out; CODE=$WORK/code; GITHUB=https://github.com/DavisAI1974
DAYS=(20231002 20231003 20231017 20231018)
say() { echo "$1" >> "$OUT/STATUS"; }

pip install -q pyarrow==26.0.1 numpy==2.5.5 matplotlib scipy >> "$OUT/setup.log" 2>&1 || { say 'FAILED in the set-up: the libraries'; exit 1; }
git -C "$CODE" fetch -q --depth 1 origin "$COMMIT" >> "$OUT/setup.log" 2>&1 && git -C "$CODE" checkout -q "$COMMIT" >> "$OUT/setup.log" 2>&1 \
  || { say "FAILED in the set-up: the code at $COMMIT"; exit 1; }
CPUS=($(python3 -c "import os; print(*sorted(os.sched_getaffinity(0)))"))
EACH=$(( ${#CPUS[@]} / ${#DAYS[@]} )); [ "$EACH" -lt 1 ] && EACH=1
say "set up; ${#CPUS[@]} CPUs, $EACH for each trade day"

for i in "${!DAYS[@]}"; do
  d=${DAYS[$i]}
  mine=$(IFS=,; echo "${CPUS[*]:$((i * EACH)):$EACH}")
  (
    mkdir -p "$OUT/d$d"
    {
      git clone -q --depth 1 --filter=blob:none --no-checkout --single-branch --branch "root-rows-$d" "$GITHUB/markets-data" "$WORK/rows/$d" &&
      git -C "$WORK/rows/$d" sparse-checkout set --no-cone "/calc-leg_peaks-facts-*" "/tick-renders/tick-dipole-*" \
        "/tick-renders/TICK-RENDERS-*" "/crypto-ng-tick/crypto-ng-tick-tape-trades-*" "/continuing/continuing-*" &&
      git -C "$WORK/rows/$d" checkout -q "root-rows-$d"
    } >> "$OUT/d$d/setup.log" 2>&1 || { echo "FAILED in the set-up: the stored files of trade day $d" >> "$OUT/d$d/STATUS"; exit 1; }
    git -C "$WORK/rows/$d" rev-parse HEAD > "$OUT/d$d/ROWS_COMMIT"
    echo "$COMMIT" > "$OUT/d$d/CODE_COMMIT"
    cd "$CODE"
    if OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 taskset -c "$mine" \
        python3 -m root.leg_renders "$d" --rows "$WORK/rows/$d" --out "$OUT/d$d" --keep-cpus "$@" > "$OUT/d$d/leg_renders.log" 2>&1
    then echo "leg_renders passed on CPUs $mine at $COMMIT" >> "$OUT/d$d/STATUS"
    else echo "leg_renders FAILED on CPUs $mine at $COMMIT" >> "$OUT/d$d/STATUS"
    fi
  ) &
done
wait
say "finished leg_renders at $COMMIT"
