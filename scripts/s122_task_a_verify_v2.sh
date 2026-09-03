#!/usr/bin/env bash
set -euo pipefail
python3 -m pip install --quiet pytest
mkdir -p data
cp scripts/s122_task_a_verify.sh data/s122_task_a_runner.sh
python3 scripts/s122_patch_task_a_runner.py
bash data/s122_task_a_runner.sh
