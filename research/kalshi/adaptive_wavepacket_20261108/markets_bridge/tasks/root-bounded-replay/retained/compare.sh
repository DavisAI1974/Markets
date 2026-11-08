set -eu
src=/mnt/e/tmp/ng-root-bounded-13eb0f6ab
cd "$HOME/ng-root-bounded-13eb0f6ab"
cp "$src/bounded_root.py" .
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
out="$PWD/out"
mkdir -p "$out"
run () {
  mode=$1
  name=$2
  shift 2
  FRANKIE_ROOT_LEGACY_FRAME_SHARDS="$mode" /usr/bin/time -v -o "$out/$name.time"     venv/bin/python bounded_root.py 20231018 "$out/$name" "$@"
}
run on sharded
run off single
run off resumed-save --save
run off resumed-save