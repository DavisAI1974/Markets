#!/usr/bin/env bash
set -euo pipefail
TARGET='chatgpt/frankie-raw-mbo-benchmark-20260828'
CANDIDATE='chatgpt/s122-item4-task-d-candidate-20260903'
BASE='e4d576f25bee8850a0bafa48d573927b938adda4'
TEST='research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk_s122_item4_d.py'
PATCH='scripts/s122_patch_task_d_20260903.py'
STALE_PATCH='scripts/s122_patch_task_d_stale_tests_20260903.py'

cp "$TEST" /home/runner/task_d_test.py
cp "$PATCH" /home/runner/task_d_patch.py
cp "$STALE_PATCH" /home/runner/task_d_stale_patch.py
python3 -m pip install --quiet pytest databento matplotlib scipy scikit-learn

git fetch origin "$TARGET" "$CANDIDATE"
test "$(git rev-parse origin/$TARGET)" = "$BASE" || { echo 'STOP: target branch moved'; exit 41; }
test "$(git rev-parse origin/$CANDIDATE)" = "$BASE" || { echo 'STOP: candidate branch moved'; exit 42; }
git switch -C s122-task-d "origin/$TARGET"
cp /home/runner/task_d_test.py "$TEST"
cp /home/runner/task_d_patch.py data_s122_task_d_patch.py
cp /home/runner/task_d_stale_patch.py data_s122_task_d_stale_patch.py
python3 data_s122_task_d_patch.py
python3 data_s122_task_d_stale_patch.py
rm data_s122_task_d_patch.py data_s122_task_d_stale_patch.py

python3 -m py_compile \
  research/kalshi/frankie_raw_mbo_benchmark/native_layer_crosswalk.py \
  research/kalshi/frankie_raw_mbo_benchmark/native_causal_stream.py

set +e
python3 -m pytest \
  "$TEST" \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk.py \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_causal_stream.py \
  -q -p no:cacheprovider > data_s122_d_focused.log 2>&1
FOCUSED=$?
set -e
echo "FOCUSED_EXIT $FOCUSED"
tail -120 data_s122_d_focused.log
test "$FOCUSED" -eq 0

set +e
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests -q -p no:cacheprovider > data_s122_d_suite.log 2>&1
SUITE=$?
set -e
echo "SUITE_EXIT $SUITE"
tail -120 data_s122_d_suite.log
test "$SUITE" -eq 0

python3 research/kalshi/store.py check
python3 research/kalshi/store.py docs
# Inspect only newly added lines. Existing tests deliberately contain '/tmp/' and 'scratchpad'
# as forbidden-string assertions; unchanged/context lines are not a newly introduced path.
if git diff --unified=0 | grep '^+' | grep -v '^+++' | grep -nE 'E:[/\\]|scratchpad|/tmp'; then
  echo 'forbidden path text found in added diff lines' >&2
  exit 43
fi
git diff --quiet research/ng_exhaustion_mbo_v4_state_adapter_20260820.py
echo LOCKED_OK
if git diff --name-only | grep -E '(^|/)[^/]*_RENDER_[^/]*\.md$|(^|/)FRANKIE_FEED_RECORD_[^/]*\.md$'; then
  echo 'forbidden historical render/feed record changed' >&2
  exit 44
fi

# The task is bounded to these source/test files.
git status --short
git diff --check
git add \
  research/kalshi/frankie_raw_mbo_benchmark/native_layer_crosswalk.py \
  research/kalshi/frankie_raw_mbo_benchmark/native_causal_stream.py \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk.py \
  "$TEST"
git diff --cached --check
git diff --cached --stat

git config user.name 'OpenAI Codex'
git config user.email 'noreply@openai.com'
git commit -m 'fix: compute crosswalk evidence from delivered carriers' \
  -m 'S122 Item 4 Task D separates missing member-census evidence from measured carrier absence, derives causal group carriers from the per-layer producer records, verifies the requested arm against the run identity, computes knowledge binding from the rebound registry, accounts lock time as PRINCIPAL_STAMPED, and makes A_MEMORY the no-result CLI default. Historical render/feed-record files remain untouched.' \
  -m 'Co-Authored-By: Codex <noreply@openai.com>'
git push origin "HEAD:$CANDIDATE"
