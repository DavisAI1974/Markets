#!/usr/bin/env bash
set -euo pipefail

TARGET='chatgpt/frankie-raw-mbo-benchmark-20260828'
CANDIDATE='chatgpt/s122-item4-task-a-candidate-20260903'
EXPECTED_BASE='3e0eec9535c9b814fc88c42e0beb0edbc94df302'

python3 -m pip install --quiet pytest
mkdir -p data

git fetch origin "$TARGET" "$CANDIDATE"
ACTUAL_BASE="$(git rev-parse "origin/$TARGET")"
test "$ACTUAL_BASE" = "$EXPECTED_BASE" || {
  echo "STOP: target moved from $EXPECTED_BASE to $ACTUAL_BASE" >&2
  exit 41
}
test "$(git rev-parse "origin/$CANDIDATE")" = "$EXPECTED_BASE" || {
  echo "STOP: candidate branch is no longer at the clean base" >&2
  exit 42
}
git switch -C s122-task-a "$EXPECTED_BASE"

python3 - <<'PY'
import json
from pathlib import Path
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_row_sink_differential import run_slice
root = Path('data/s122_task_a_before')
result = run_slice(root, stream=True)
receipt = result['layers']['exact_member_ledger']['rows_receipt']
path = Path(receipt['path'])
measure = {'bytes': path.stat().st_size, 'rows': receipt['row_count'], 'sha256': receipt['sha256']}
Path('data/task_a_before.json').write_text(json.dumps(measure, sort_keys=True), encoding='utf-8')
print('BEFORE', measure)
PY

# RED: add only the Task-A behavior tests before touching production code.
python3 - <<'PY'
from pathlib import Path

p = Path('research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_replay_driver.py')
text = p.read_text(encoding='utf-8')
marker = '\n\nclass LegacyRowRetentionTest(unittest.TestCase):\n'
assert marker in text
assert 'class RawActionsMemberRowS122Test' not in text
block = r'''

class RawActionsMemberRowS122Test(unittest.TestCase):
    """F-30: every member row carries the frame's per-record raw actions whole."""

    def _run(self):
        driver = make_driver(total_mbo_records=3)
        captured_frames = []
        original_on_group = driver._on_group

        def capture_frame(envelope, source_object):
            captured_frames.append(list(envelope["compact_event_frame"]["raw_actions"]))
            return original_on_group(envelope, source_object)

        driver._on_group = capture_frame
        base = at("2021-10-04T13:00:00")
        driver.consume([
            record(seq=0, event_ns=base, order_id=801, last=False),
            record(seq=1, event_ns=base + 1, order_id=802, last=True),
            record(seq=2, event_ns=base + NS_PER_SECOND, order_id=803, last=True),
        ])
        driver.finalize()
        return driver.counters.member_rows, captured_frames

    def test_every_member_row_carries_the_frame_raw_actions_whole(self):
        rows, frames = self._run()
        self.assertEqual(len(rows), len(frames))
        for row, frame_actions in zip(rows, frames):
            with self.subTest(group=row["group_index"]):
                self.assertIsInstance(row["raw_actions"], list)
                self.assertEqual(row["raw_actions"], frame_actions)

    def test_raw_actions_length_matches_component_count_for_every_group(self):
        rows, _ = self._run()
        self.assertGreater(len(rows), 1, "fixture must contain multiple groups")
        for row in rows:
            self.assertEqual(len(row["raw_actions"]), row["component_count"])

    def test_raw_actions_has_exactly_one_top_level_key(self):
        rows, _ = self._run()
        for row in rows:
            self.assertEqual(list(row).count("raw_actions"), 1)
'''
p.write_text(text.replace(marker, block + marker, 1), encoding='utf-8')

p = Path('research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_row_sink_differential.py')
text = p.read_text(encoding='utf-8')
marker = '    def test_all_three_ledgers_stream_and_reconcile_against_their_counters(self):\n'
assert marker in text
assert 'test_raw_actions_rebaseline_is_identical_on_both_retention_paths' not in text
block = r'''    def test_raw_actions_rebaseline_is_identical_on_both_retention_paths(self):
        """F-30 changes ledger bytes, never the row retained by each path."""
        receipt = self.streamed["layers"]["exact_member_ledger"]["rows_receipt"]
        streamed_rows = [
            json.loads(line)
            for line in Path(receipt["path"]).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        inline_rows = self.inline["layers"]["exact_member_ledger"]["rows"]
        self.assertEqual(len(streamed_rows), len(inline_rows))
        self.assertGreater(len(streamed_rows), 0)
        for streamed_row, inline_row in zip(streamed_rows, inline_rows):
            self.assertEqual(streamed_row["raw_actions"], inline_row["raw_actions"])
            self.assertEqual(len(streamed_row["raw_actions"]), streamed_row["component_count"])

'''
p.write_text(text.replace(marker, block + marker, 1), encoding='utf-8')
PY

set +e
python3 -m pytest \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_replay_driver.py \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_row_sink_differential.py \
  -q -p no:cacheprovider > data/red.log 2>&1
RED_EXIT=$?
set -e
echo "RED_EXIT $RED_EXIT"
tail -80 data/red.log
test "$RED_EXIT" -ne 0
grep -q "raw_actions" data/red.log

# GREEN implementation: carry the frame list, then make the crosswalk tell the measured truth.
python3 - <<'PY'
from pathlib import Path
p = Path('research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py')
text = p.read_text(encoding='utf-8')
old = '''        # `raw_actions` is excluded only because the member row already holds it.\n        for carried, value in frame.items():\n            if carried == "raw_actions" or carried in row:\n'''
new = '''        # Measured: member_clock_row consumes raw_actions for clocks but does not return it.\n        for carried, value in frame.items():\n            if carried in row:\n'''
assert text.count(old) == 1
p.write_text(text.replace(old, new, 1), encoding='utf-8')
PY

python3 - <<'PY'
import re
from pathlib import Path

p = Path('research/kalshi/frankie_raw_mbo_benchmark/native_layer_crosswalk.py')
text = p.read_text(encoding='utf-8')

# Replace the now-false module account of the measured row.
pattern = re.compile(r'\*\*The measurement this table records, and it is the one Greg\'s ruling 2 turns on\.\*\*.*?\n\n\*\*The seven clocks', re.S)
replacement = '''**The measurement this table records, and it is the one Greg's ruling 2 turns on.** The exact
member row now carries the frame's `raw_actions` list whole. `native_clocks.member_clock_row`
consumes that list to derive clocks but returns a fresh dict without it, so
`native_replay_driver._on_group` carries the frame field onto the row explicitly. The field census
therefore names the per-record A/C/M/R/T/F/N messages and their order ids, prices, sizes, flags,
sequences, clocks, provenance, snapshot flag and `book_effect`. The producer records below declare
those paths as member carriers; no raw-action field remains pinned as structurally absent.

**The seven clocks'''
text, count = pattern.subn(replacement, text, count=1)
assert count == 1

# Replace the now-false reusable note, keeping its references surgical.
pattern = re.compile(r'RAW_ACTIONS_DROP = \(.*?\n\)\nINVENTORY_BOUND =', re.S)
replacement = '''RAW_ACTIONS_CARRIED = (
    "CARRIED: `NormalizedMbo.public_dict` builds every per-record field and "
    "`FullCaptureAdapter.apply` attaches the per-record `book_effect`; "
    "`native_replay_driver._on_group` carries the frame's `raw_actions` list whole onto the "
    "exact member row because `member_clock_row` consumes it for clocks but does not return it. "
    "The row field census is the delivery proof."
)
INVENTORY_BOUND ='''
text, count = pattern.subn(replacement, text, count=1)
assert count == 1
text = text.replace('RAW_ACTIONS_DROP', 'RAW_ACTIONS_CARRIED')

# For each raw-action structural-absence pin, move the exact same path(s) into member_paths.
block_re = re.compile(r'(?ms)^    "(?P<layer>[^"]+)": _row\(\n(?P<body>.*?^    \),\n)')
changed_layers = []

def update_block(match):
    layer = match.group('layer')
    body = match.group('body')
    absent = re.search(r'(?m)^        structurally_absent=\((?P<items>[^\n]*)\),\n', body)
    if absent is None or 'raw_actions' not in absent.group('items'):
        return match.group(0)
    tokens = re.findall(r'"([^"]+)"', absent.group('items'))
    assert tokens and all(token.startswith('raw_actions') for token in tokens), (layer, tokens)
    member = re.search(r'(?s)        member_paths=\((?P<items>.*?)\),\n', body)
    if member is None:
        merged = tokens
        member_line = '        member_paths=(' + ', '.join(f'"{x}"' for x in merged)
        if len(merged) == 1:
            member_line += ','
        member_line += '),\n'
        body = body[:absent.start()] + member_line + body[absent.end():]
    else:
        existing = re.findall(r'"([^"]+)"', member.group('items'))
        merged = existing + [x for x in tokens if x not in existing]
        member_line = '        member_paths=(' + ', '.join(f'"{x}"' for x in merged)
        if len(merged) == 1:
            member_line += ','
        member_line += '),\n'
        body = body[:member.start()] + member_line + body[member.end():]
        body = re.sub(r'(?m)^        structurally_absent=\([^\n]*\),\n', '', body, count=1)
    changed_layers.append(layer)
    return f'    "{layer}": _row(\n' + body

text = block_re.sub(update_block, text)
assert len(changed_layers) == 12, changed_layers
assert 'structurally_absent=("raw_actions' not in text

# Remove only statements that are now false because the measured row carries the list.
for old, new in (
    (' - NOT ON THE ROW', ''),
    (' is NOT ON THE ROW', ' is carried on the member row'),
    ('are dropped with raw_actions', 'are carried with raw_actions'),
    ('is dropped with raw_actions', 'is carried with raw_actions'),
    ('dropped with raw_actions', 'carried with raw_actions'),
    ('is dropped with it', 'is carried with it'),
    ('are dropped with it', 'are carried with it'),
):
    text = text.replace(old, new)

p.write_text(text, encoding='utf-8')
print('CROSSWALK_RAW_ACTION_CARRIER_LAYERS', changed_layers)
PY

# Update the existing execution proof: remaining pins stay absent; raw actions must now be present.
python3 - <<'PY'
from pathlib import Path
p = Path('research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk.py')
text = p.read_text(encoding='utf-8')
old = '''    def test_structurally_absent_carriers_are_in_fact_absent_from_the_row(self):\n        """The measurement behind the RECEIPTED_CARRIER_ABSENT status, pinned. The driver\n        drops the frame's `raw_actions` at group close saying the row already holds them; the\n        row does not. When that is fixed this test fails and the records get updated - the\n        crosswalk cannot silently keep reporting a defect that is gone."""\n        pinned = 0\n        for layer_id, record in LAYER_PRODUCERS.items():\n            for pattern in record.get("structurally_absent", ()):\n                pinned += 1\n                with self.subTest(layer_id=layer_id, path=pattern):\n                    self.assertFalse(\n                        path_present(pattern, self.member_paths),\n                        f"{layer_id}: {pattern} is now on the row; update the producer record",\n                    )\n        self.assertGreater(pinned, 0)\n        self.assertNotIn("raw_actions", self.member_rows[0])\n'''
new = '''    def test_structurally_absent_carriers_are_in_fact_absent_from_the_row(self):\n        """Remaining absence declarations are measured; F-30 raw actions are now carriers."""\n        raw_action_pins = []\n        for layer_id, record in LAYER_PRODUCERS.items():\n            for pattern in record.get("structurally_absent", ()):\n                if pattern.startswith("raw_actions"):\n                    raw_action_pins.append((layer_id, pattern))\n                with self.subTest(layer_id=layer_id, path=pattern):\n                    self.assertFalse(\n                        path_present(pattern, self.member_paths),\n                        f"{layer_id}: {pattern} is now on the row; update the producer record",\n                    )\n        self.assertEqual(raw_action_pins, [])\n        self.assertIn("raw_actions", self.member_rows[0])\n        for path in ("raw_actions[]", "raw_actions[].action", "raw_actions[].order_id",\n                     "raw_actions[].source_dbn_sha256", "raw_actions[].source_dbn_object",\n                     "raw_actions[].is_snapshot", "raw_actions[].book_effect"):\n            self.assertTrue(path_present(path, self.member_paths), path)\n'''
assert text.count(old) == 1
p.write_text(text.replace(old, new, 1), encoding='utf-8')
PY

python3 -m py_compile research/kalshi/frankie_raw_mbo_benchmark/native_layer_crosswalk.py

set +e
python3 -m pytest \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_replay_driver.py \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_row_sink_differential.py \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk.py \
  -q -p no:cacheprovider > data/green-focused.log 2>&1
FOCUSED_EXIT=$?
set -e
echo "FOCUSED_EXIT $FOCUSED_EXIT"
tail -100 data/green-focused.log
test "$FOCUSED_EXIT" -eq 0

python3 - <<'PY'
import json
from pathlib import Path
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_row_sink_differential import run_slice
root = Path('data/s122_task_a_after')
result = run_slice(root, stream=True)
receipt = result['layers']['exact_member_ledger']['rows_receipt']
path = Path(receipt['path'])
measure = {'bytes': path.stat().st_size, 'rows': receipt['row_count'], 'sha256': receipt['sha256']}
Path('data/task_a_after.json').write_text(json.dumps(measure, sort_keys=True), encoding='utf-8')
print('AFTER', measure)
PY

set +e
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests -q -p no:cacheprovider \
  > data/suite.log 2>&1
SUITE_EXIT=$?
set -e
echo "EXIT $SUITE_EXIT"
tail -120 data/suite.log
test "$SUITE_EXIT" -eq 0

python3 research/kalshi/store.py check
python3 research/kalshi/store.py docs
if git diff | grep -nE 'E:[/\\]|scratchpad|/tmp'; then
  echo 'forbidden path text found in diff' >&2
  exit 43
fi
git diff --quiet research/ng_exhaustion_mbo_v4_state_adapter_20260820.py
echo LOCKED_OK

python3 - <<'PY'
import json
from pathlib import Path
before = json.loads(Path('data/task_a_before.json').read_text(encoding='utf-8'))
after = json.loads(Path('data/task_a_after.json').read_text(encoding='utf-8'))
assert before['rows'] == after['rows']
assert before['bytes'] != after['bytes']
assert before['sha256'] != after['sha256']
delta = after['bytes'] - before['bytes']
per_row = delta / after['rows']
body = f'''fix: carry per-record raw actions on member rows

S122 Item 4 Task A / F-30 carries each compact frame's raw_actions list whole onto the exact member row instead of dropping it after member_clock_row consumes it for clock derivation. The crosswalk now declares the measured raw-action paths as member carriers, removes the twelve now-false structural-absence pins, and the execution proof requires those fields in the census.

Member-ledger fixture measurement: before {before['bytes']} bytes ({before['sha256']}), after {after['bytes']} bytes ({after['sha256']}), delta {delta} bytes across {after['rows']} rows = {per_row:.2f} bytes per row. Ledger bytes and hashes changed by design because the per-record actions are now retained on every member row.

Co-Authored-By: Codex <noreply@openai.com>
'''
Path('data/task_a_commit_message.txt').write_text(body, encoding='utf-8')
print(body)
PY

git status --short
git diff --stat
git add \
  research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py \
  research/kalshi/frankie_raw_mbo_benchmark/native_layer_crosswalk.py \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_replay_driver.py \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_row_sink_differential.py \
  research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk.py
git diff --cached --check
git diff --cached --stat
git config user.name 'OpenAI Codex'
git config user.email 'noreply@openai.com'
git commit -F data/task_a_commit_message.txt
git push origin "HEAD:$CANDIDATE"
