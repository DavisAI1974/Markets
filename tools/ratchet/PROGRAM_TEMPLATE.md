---
# PROGRAM_TEMPLATE.md - a filled-in control file for one ratchet loop (tools/ratchet/loop.py).
# Copy it, change every value, keep every field. A field that is missing or not on this list is refused,
# with its name (tools/ratchet/program.py). This example loops on a checkout of paper-trading-platform
# and goes by the number of its own checks that pass: an engineering count, not a trade figure.

loop: tasty-checks-count          # the loop's name; letters, digits, . _ - ; the branch is ratchet/<loop>
repo: /path/to/the/git/checkout   # the git repository the loop changes (a path; relative = beside this file).
                                  # The loop works in its own worktree, never in your working tree.

mutable:                          # globs a trial MAY change (paths from the repo root; ** crosses folders)
  - "tasty/**"
  - "tests/tasty_runner/**"
protected:                        # globs a trial may NEVER change. A trial that touches one is not run:
  - "tests/tasty_runner/test_paper_replay.py"   # it is recorded as crash, "touched <file>", undone, and
                                                # raised to Greg. A file matching neither list is "outside
                                                # mutable": also a crash, "touched <file>".

metric:                           # the figure the loop keeps or reverts by
  name: checks_passed             # must be the name of one of the figures below
  direction: higher               # higher | lower | null. null = Greg has not chosen the figure: every
                                  # trial is run and recorded (status "recorded"), none kept or reverted.
  unit: checks

figures:                          # EVERY figure listed is read after each run and written as its own line
  - name: checks_passed           # of the trial; none is averaged or combined with another
    unit: checks
    parse:                        # regex: the LAST match in the output; group = which group is the number
      kind: regex
      pattern: "(\\d+) passed"
      group: 1
  # - name: some_figure
  #   parse: {kind: json, key: result.count}   # json: dotted key into the JSON printed on the last stdout line

run:
  command: "python3 -m pytest tests/tasty_runner -q -p no:cacheprovider"   # run in the worktree. It must ONLY
                                  # READ AND PRINT: see "What the guard covers" below the front matter.
  cwd: "."                        # where to run it, relative to the repo root
  timeout_s: 120                  # longer than this is a crash
  env: {}                         # extra environment variables for the command; each trial records the
                                  # command and these variables' NAMES (not their values)

budget:                           # the plan's per-run budget. null = no limit set.
  max_trials: 5                   # proposed trials (the baseline, trial 0, is not counted). Harness-enforced.
  max_wall_clock_s: 900           # seconds for the whole loop. Harness-enforced.
  max_model_calls: null           # these four are taken from what the proposer reports it has used;
  max_sub_agents: null            # a figure it does not report is written "not reported", never 0.
  max_concurrent_workers: 1       # the harness runs one trial at a time (reported as 1)
  max_tool_calls: null
  max_tokens: null
  max_retries: 0                  # times a crashed run command is run again on the same commit (null = 0).
                                  # Harness-enforced; every attempt is in the trial's log and "attempts".
  max_graph_writes: 20            # lines the loop may add to the experiment record. Harness-enforced.

crash:
  max_consecutive_crashes: 2      # a non-zero exit, a timeout or a figure that cannot be read is a crash;
                                  # this many in a row stops the loop and escalates to Greg

keep: strictly_better             # strictly_better | better_or_equal, against the best KEPT trial so far.
                                  # Trial 0 (the baseline, a run of HEAD with no change) is the first best.

stop:
  after_trials: null              # stop after this many proposed trials (a plain stop, not an escalation)
  after_trials_without_a_keep: 3  # stop after this many trials in a row that were not kept

escalate:                         # plain-word conditions for Greg. The harness itself raises three: the
  - "the budget is exhausted"     # budget is exhausted, max_consecutive_crashes is reached, a protected
  - "a figure moves by a surprising amount"   # file is touched. Others here are listed in the result for
                                              # a person to judge; the harness does not evaluate them.
escalate_file: escalation.json    # optional: where escalations are written (relative = beside this file)

record:
  data_root: /path/to/markets-data   # optional: the markets-data checkout holding experiments/ (else found
                                     # as tools.exp_dag does)
---

Free notes below the front matter are kept with the file and not read by the harness: why this loop
exists, who chose the metric and when.

What the guard covers, and what it does not. The guard covers what a proposer changes inside the worktree:
every file git lists as changed or new, and every file git ignores that is new or changed since the proposer
was called (an ignored file is read by the run command like any other, so it counts as a change outside
`mutable` and the trial is recorded as crash, "touched <file>", and not run). The guard does not cover what
the run command itself does elsewhere: a command that writes outside the worktree (through an environment
variable, an absolute path, `gh workflow run`) is neither checked nor undone. A control file's command must
therefore only read and print.
