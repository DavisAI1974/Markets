#!/bin/bash
# S66 overnight durable collection (Greg away): pull deep Kraken tape for the FULL
# rebate-eligible USD alt universe (352 pairs, maker<0), gzip + commit to an orphan
# data branch every few batches so committed progress survives a container recycle.
# Resumable: skips any pair already committed. Also absorbs the running majors.
set -u
REPO=/home/user/Markets
WT=/tmp/data_wt
RAW=/tmp/ktape_sc
DAYS=120
PAR=4
LIST=/tmp/eligible_pairs.txt
mkdir -p "$RAW" "$WT/bins"
cd "$REPO"
mapfile -t PAIRS < "$LIST"

commit_push() {
  cd "$WT" || return
  git add -A bins 2>/dev/null
  if ! git diff --cached --quiet 2>/dev/null; then
    n=$(ls bins/*.json.gz 2>/dev/null | wc -l)
    git commit -q -m "kraken eligible-alt tape: ${n} pairs @ ${DAYS}d [S66 overnight collect]" 2>/dev/null
    for a in 1 2 3 4; do
      if git push -u origin data/kraken-smallcap-tape >/dev/null 2>&1; then break; fi
      sleep $((a * 4))
    done
    echo "[collect] committed+pushed ${n} pairs @ $(date -u +%H:%M:%S)"
  fi
  cd "$REPO" || return
}

pull_one() {
  local p="$1"
  [ -f "$WT/bins/${p}.json.gz" ] && return 0        # already durable -> skip (resume)
  python backfill_kraken_trades.py --pair "$p" --days "$DAYS" \
      --bins-path "$RAW/${p}.json" > "$RAW/${p}.log" 2>&1
  if [ -f "$RAW/${p}.json" ]; then
    gzip -c "$RAW/${p}.json" > "$WT/bins/${p}.json.gz"
    rm -f "$RAW/${p}.json"
  fi
}
export REPO WT RAW DAYS
export -f pull_one

echo "[collect] START $(date -u) — ${#PAIRS[@]} eligible pairs @ ${DAYS}d, par=${PAR}"
i=0; batch=0
while [ $i -lt ${#PAIRS[@]} ]; do
  for j in $(seq 0 $((PAR - 1))); do
    idx=$((i + j)); [ $idx -ge ${#PAIRS[@]} ] && break
    pull_one "${PAIRS[$idx]}" &
  done
  wait
  i=$((i + PAR)); batch=$((batch + 1))
  [ $((batch % 5)) -eq 0 ] && commit_push
done
wait

# absorb the running majors (SOL/XRP/DOGE 30d) into the durable branch too
for m in SOLUSD XRPUSD XDGUSD; do
  if [ -f /tmp/ktape/${m}_30d_bins.json ] && [ ! -f "$WT/bins/${m}_30d.json.gz" ]; then
    gzip -c /tmp/ktape/${m}_30d_bins.json > "$WT/bins/${m}_30d.json.gz"
  fi
done
commit_push
echo "[collect] DONE $(date -u): $(ls $WT/bins/*.json.gz 2>/dev/null | wc -l) pairs durable"
