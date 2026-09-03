#!/usr/bin/env bash
set -euo pipefail
mkdir -p data
cp scripts/s122_task_a_verify.sh data/s122_task_a_runner.sh
python - <<'PY'
from pathlib import Path
p = Path('data/s122_task_a_runner.sh')
text = p.read_text(encoding='utf-8')
old = 'test "$RED_EXIT" -ne 0\ngrep -q "raw_actions" data/red.log\ntail -20 data/red.log\n'
new = 'test "$RED_EXIT" -ne 0\necho "--- RED LOG ---"\ntail -80 data/red.log\necho "--- END RED LOG ---"\ngrep -q "raw_actions" data/red.log\n'
assert text.count(old) == 1
p.write_text(text.replace(old, new, 1), encoding='utf-8')
PY
bash data/s122_task_a_runner.sh
