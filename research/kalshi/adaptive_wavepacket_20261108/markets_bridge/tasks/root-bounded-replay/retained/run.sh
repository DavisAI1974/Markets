set -eu
src=/mnt/e/tmp/ng-root-bounded-13eb0f6ab
dir=$HOME/ng-root-bounded-13eb0f6ab
cp -r "$src/deploy" "$src/research" "$src/producers" "$dir"
cp "$src/markets_adapter.py" "$src/bounded_root.py" "$src"/*-input.jsonl "$src"/*-input-receipt.json "$dir"
cd "$dir"
mkdir -p root-producers/research/kalshi
ln -sfn "$dir/producers/research/kalshi/frankie_raw_mbo_benchmark" root-producers/research/kalshi/frankie_raw_mbo_benchmark
ln -sfn "$dir/producers/research/kalshi/agents" root-producers/research/kalshi/agents
cp research/ng_exhaustion_mbo_v4_state_adapter_20260820.py root-producers/research
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
if [ ! -f 20231018.sqlite ]; then venv/bin/python bounded_root.py 20231018 unused --prepare; fi
FRANKIE_ROOT_LEGACY_FRAME_SHARDS=on /usr/bin/time -v -o on.time venv/bin/python bounded_root.py 20231018 "$src/out/on"