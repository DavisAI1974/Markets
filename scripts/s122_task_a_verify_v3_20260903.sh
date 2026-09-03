#!/usr/bin/env bash
set -euo pipefail
python3 -m pip install --quiet databento matplotlib scipy scikit-learn
bash scripts/s122_task_a_verify_v2_20260903.sh
