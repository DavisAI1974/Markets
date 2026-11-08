set -eu
cd "$HOME/ng-root-bounded-13eb0f6ab"
src=/mnt/e/tmp/ng-root-bounded-13eb0f6ab
mkdir -p "$src/compression"
venv/bin/python "$src/measure_compression.py" out/02-healthy/work/derived/.rows/frames.jsonl   3519da997dbcb7bb18be95d3f5fb440b9e3a60cc6be147f93bdb19ea603f15ce   "$src/compression/frames-20231002.jsonl.zst" > "$src/compression/20231002.json"
cat "$src/compression/20231002.json"
venv/bin/python "$src/measure_compression.py" out/sharded/work/derived/.rows/frames.jsonl   2d0f6717080dcfea2b8f58262369d9faf9bc2c1ac90bcd2ac60f75dcaecc6162   "$src/compression/frames-20231018.jsonl.zst" > "$src/compression/20231018.json"
cat "$src/compression/20231018.json"