#!/bin/sh
# ROOT part 2 on a pod: one trade day per pod (Greg, 2026-11-16: the step runs go on pods, all four trade days at
# the same time). The pod fetches the code, the raw tape and that trade day's stored rows from the two public
# repositories (no key is needed and none is on the pod), runs the named calculations with their checks, and then
# serves the output folder so the session can fetch it, compare every file with the fingerprint in its receipt,
# and store it on the trade day's root-rows branch. The pod itself writes nothing to git.
#
#   sh pod_run.sh <trade day YYYYMMDD> <Markets branch> <calculation> [<calculation> ...]
set -eu
DAY=$1; BRANCH=$2; shift 2
WORK=/root/work
GITHUB=https://github.com/DavisAI1974
mkdir -p "$WORK/out"
cd "$WORK"
pip install -q databento pyarrow numpy
[ -d code ] || { git clone -q --depth 1 --filter=blob:none --sparse --branch "$BRANCH" "$GITHUB/Markets" code
                 git -C code sparse-checkout set root; }
[ -d data ] || { git clone -q --depth 1 --filter=blob:none --sparse --branch ccr-349e2ffe-07p8od "$GITHUB/markets-data" data
                 git -C data sparse-checkout set data/nymex_mbo/ng_v0_oct2023; }
[ -d rows ] || git clone -q --depth 1 --single-branch --branch "root-rows-$DAY" "$GITHUB/markets-data" rows
git -C code rev-parse HEAD > "$WORK/out/CODE_COMMIT"
git -C rows rev-parse HEAD > "$WORK/out/ROWS_COMMIT"
cd "$WORK/code"
: > "$WORK/out/STATUS"
for CALC in "$@"; do
    if MARKETS_DATA="$WORK/data" python3 -m root.run calc "$CALC" "$DAY" --rows "$WORK/rows" --out "$WORK/out" \
            > "$WORK/out/$CALC.log" 2>&1; then
        echo "$CALC passed" >> "$WORK/out/STATUS"
    else
        echo "$CALC FAILED" >> "$WORK/out/STATUS"
    fi
done
echo finished >> "$WORK/out/STATUS"
cd "$WORK/out"
exec python3 -m http.server 8000 --bind 0.0.0.0
