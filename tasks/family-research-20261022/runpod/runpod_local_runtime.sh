#!/usr/bin/env bash
set -euo pipefail
day=$1
base=/opt/frankie-box
ctl=$base/replay-control
target=/opt/replay-runtime/venv
export PYTHONDONTWRITEBYTECODE=1
cd "$base/replay-code/markets"
python3 -m venv "$target"
py=$target/bin/python
"$py" -m pip install --no-compile --disable-pip-version-check --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu -r deploy/aws/box/frankie_box_venv_requirements.txt
"$py" -m pip check
export PYTHONPATH="$PWD:$base/producers"
"$py" -m research.kalshi.frankie_boss.operations.ingest_block_sources --help >/dev/null
"$py" deploy/aws/box/frankie_box_experiment_root.py --help >/dev/null
"$py" deploy/aws/box/frankie_box_experiment_teacher.py --help >/dev/null
touch "$ctl/$day/runtime-local-ready"