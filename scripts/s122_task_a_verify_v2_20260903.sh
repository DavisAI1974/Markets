#!/usr/bin/env bash
set -euo pipefail
mkdir -p data
cp scripts/s122_task_a_verify_and_candidate_20260903.sh data/s122_task_a_runner.sh
python3 scripts/s122_task_a_patch_status_expectations_20260903.py
bash data/s122_task_a_runner.sh
