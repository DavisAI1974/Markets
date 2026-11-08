set -eu
cd "$HOME/ng-root-bounded-13eb0f6ab"
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
/usr/bin/time -v -o out/native-ready.time venv/bin/python bounded_native.py 20231018 "$PWD/out/native-ready" "$PWD/out/sharded" > out/native-ready.json