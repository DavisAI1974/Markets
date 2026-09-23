# Read the existing work probe only. No job launch, process control or source write.
set -eu
: "${CODE_ROOT:?existing inactive staged checkout required}"
: "${DIRECTORY:?existing work-probe directory required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*/markets) ;; *) echo "inactive staged checkout required" >&2; exit 2;; esac
case "$DIRECTORY" in /opt/frankie-box/work/*) ;; *) echo "work probe must be under the box work root" >&2; exit 2;; esac
case "$CODE_ROOT/$DIRECTORY/" in *"/../"*|*"/./"*) echo "normalized paths required" >&2; exit 2;; esac
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_progress.py" --directory "$DIRECTORY"
