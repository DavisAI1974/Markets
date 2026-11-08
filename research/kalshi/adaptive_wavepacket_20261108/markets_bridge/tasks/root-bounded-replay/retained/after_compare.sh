set -eu
src=/mnt/e/tmp/ng-root-bounded-13eb0f6ab
cd "$HOME/ng-root-bounded-13eb0f6ab"
cp -r "$src/producers" .
cp "$src/check_sqlite.py" "$src/bounded_native.py" .
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
for i in $(seq 1 300); do
  if [ -f out/resumed-save/spool-comparison.json ] && grep -q 'Exit status: 0' out/resumed-save.time; then
    break
  fi
  if [ -f out/single-ready.time ] && grep -q 'Command exited with non-zero status' out/single-ready.time; then
    break
  fi
  if [ -f out/resumed-save.time ] && grep -q 'Command exited with non-zero status' out/resumed-save.time; then
    break
  fi
  sleep 2
done
venv/bin/python check_sqlite.py 20231018 out/sharded out/checked-clock.sqlite > out/sqlite-check.json
cat out/sqlite-check.json
/usr/bin/time -v -o out/native.time venv/bin/python bounded_native.py 20231018 out/native out/sharded > out/native-run.json