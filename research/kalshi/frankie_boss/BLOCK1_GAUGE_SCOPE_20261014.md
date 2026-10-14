# Current timing scope: Claude's block-1 gauge, updated efficiency code

Greg clarified October 14 at 01:21–01:29 ET: use Claude's existing five-minute
test procedure with our updated code. Ingest/ROOT continuation can wait until
the one-day run is underway. Thirty-day code changes remain deferred.

The current published runtime source is `805a494`, including the efficiency
work from `bd8f4f1`, subsequent review corrections, and the native open-group
saves. Fetch and preserve any newer work before staging the selected commit.
The stopped box's older deployed checkout must be updated before measurement.
The earlier Codex review is recorded in SESSION13; runtime verification is the
purpose of this small run, not something already established by source review.

## Exact existing test

- Day `20231018`, sealed block `1`, 1,588 rows: the first five minutes of data.
- Run the full existing classroom and external section, one block only.
- Use the existing teacher rows and attached day file; preserve the same all-99
  and second-set bindings, original row keys, clocks and evidence.
- Use the current `frankie_box_block_gauge.py`, with evidence encoding `shadow`.
- Write into a fresh commit/timestamp gauge directory using the existing runner.
- Report total wall time, session time, per-step times, classroom/external status
  and encoding comparisons. Shadow overhead stays visible in the measured time.

Five minutes describes the source block, not a five-minute CPU/runtime cutoff.
The former combined 35-minute ingest/ROOT leg and its partial-save/reopen
experiment are deferred; they are not prerequisites for this gauge.

## Existing invocation, after explicit AWS authorization

Follow SESSION13 section 7: stage the selected current commit, restore recorded
disk run settings, enable the retained swapfile, use the held CPU booking, and
launch through SSM/systemd so an SSM command ending cannot kill the gauge.
With `CR` bound to that staged checkout, Claude's command is:

```bash
systemd-run --unit=frankie-gauge-$(date +%s) --collect -p WorkingDirectory=$CR sh -c "/opt/frankie-box/venv/bin/python -B \
  deploy/aws/box/frankie_box_block_gauge.py --rows-dir /opt/frankie-box/work/experiment-teacher-rows/20231018 \
  --ingest-dir /opt/frankie-box/work/ingest-20231018-gh-36571235912-1 --day 20231018 --block 1 \
  --evidence-encoding shadow --out /opt/frankie-box/work/gauge-block1 \
  > /opt/frankie-box/work/gauge-block1/run-\$(date +%H%M%S).log 2>&1"
```

Keep the run attended and stop the box promptly when it completes or fails.
Preserve any unfinished output and actual saved continuation state without
claiming an interrupted measurement completed. The existing recovery limits
remain explicit in SESSION13; this scope creates no new recovery capability.
Starting AWS and resuming saved `a2` still require Greg's separate explicit word.

## Preserved unfinished source

These local draft branches are outside the timing checkout:

| Draft | Local commit | Continuation note |
| --- | --- | --- |
| `codex/deferred-ingest-root-20261014` | `22d32ab` | `DEFERRED_INGEST_ROOT_20261014.md` on that branch |
| `codex/deferred-gauge-checkpoint-20261014` | `5f34cf7` | `DEFERRED_GAUGE_CHECKPOINT_20261014.md` on that branch |

Both drafts are incomplete and unreviewed. Automatic approval review rejected
pushing the new ingest/ROOT branch because explicit authorization to publish
substantial unreviewed deferred source was absent. Neither draft was deployed or
run, and neither contains generated scientific outputs. They remain locally
preserved; publishing them requires explicit authorization.
