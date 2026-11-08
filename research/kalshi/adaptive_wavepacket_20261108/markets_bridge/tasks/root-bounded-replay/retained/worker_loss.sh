set -eu
src=/mnt/e/Markets-family-research-handoff/research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-bounded-replay
cd "$HOME/ng-root-bounded-13eb0f6ab"
cp "$src/bounded_root.py" "$src/check_sqlite.py" .
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 FRANKIE_ROOT_LEGACY_FRAME_SHARDS=on
scratch=$(mktemp -d /dev/shm/ng-root-02.XXXXXX)
journal="$scratch/source.sqlite"
venv/bin/python bounded_root.py 20231002 unused --prepare --journal "$journal"
cp "$journal" 20231002.sqlite
rm -- "$journal"
rmdir -- "$scratch"
venv/bin/python bounded_root.py 20231002 out/02-healthy
venv/bin/python bounded_root.py 20231002 out/02-worker-loss --drop-shard-at 200
cmp out/02-healthy/spool-comparison.json out/02-worker-loss/spool-comparison.json
venv/bin/python check_sqlite.py 20231002 out/02-healthy out/02-checked-clock.sqlite > out/02-sqlite-check.json
cat out/02-sqlite-check.json