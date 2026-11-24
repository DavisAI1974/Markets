---
# The control file of the loop on Greg's own paper platform (graph adoption plan, stages 3 and 7f, for the
# own platform). NOT RUN: dispatching a loop needs Greg's go. The platform does the runs; this loop only
# changes the one plan file, runs the platform's trial runner on a stretch of stored tape, and records every
# trial in the experiment record.
loop: platform-exit
repo: ../../../../paper-trading-platform      # a checkout of DavisAI1974/paper-trading-platform beside Markets, branch codex/strategy-trades-and-mbo-capture
mutable:                          # the plan a trial changes: its `exit` entry and each rule's placement. Nothing else.
  - "paper_platform/execution_plans/loop-trial.json"
protected:                        # everything else of the platform. A glob `paper_platform/**` would also match the
  - "paper_platform/*"            # one mutable file (protected wins), so: every file directly in paper_platform/,
  - "paper_platform/markets/**"   # each folder of it, and each plan, note and contract file of execution_plans/ that
  - "paper_platform/rules/**"     # exists today. A new file beside them is "outside mutable" and is refused too.
  - "paper_platform/static/**"
  - "paper_platform/execution_plans/ngx3-*.json"
  - "paper_platform/execution_plans/README.md"
  - "paper_platform/execution_plans/NG_OCT2023_CONTRACT.md"
  - "root/**"
  - "crypto_ng/**"
  - "tests/**"
  - ".github/**"
  - "docs/**"
  - ".gitignore"
  - "AGENTS.md"
  - "README.md"
metric:
  name: trades_opened
  direction: null                 # Greg has not chosen the figure this loop keeps or reverts by, so every trial is
                                  # recorded (status "recorded") and none is kept or reverted. No result figure is
                                  # declared until he chooses one. trades_opened is a count of what was written, named
                                  # here only because a metric name is required; it is not a measure of anything good.
  unit: trades
figures:                          # the figures() of paper_platform/trial.py: counts of what the trial wrote, each its own
  - name: journal_rows            # line, none combined with another, none a result
    unit: rows
    parse: {kind: json, key: figures.journal_rows}
  - name: signals_open
    unit: signals
    parse: {kind: json, key: figures.signals_open}
  - name: paper_orders
    unit: orders
    parse: {kind: json, key: figures.paper_orders}
  - name: fills
    unit: fills
    parse: {kind: json, key: figures.fills}
  - name: trades_opened
    unit: trades
    parse: {kind: json, key: figures.trades_opened}
  - name: trades_holding_no_contract_at_end
    unit: trades
    parse: {kind: json, key: figures.trades_holding_no_contract_at_end}
  - name: trades_closed_by_an_administrative_fill
    unit: trades
    parse: {kind: json, key: figures.trades_closed_by_an_administrative_fill}
run:
  command: "python3 -m paper_platform.trial --data \"$MARKETS_DATA\" --trade-day 2023-10-02 --plan paper_platform/execution_plans/loop-trial.json --from-minute 30 --minutes 30"
  cwd: "."                        # the loop is started with MARKETS_DATA set to the markets-data checkout (the run
                                  # directory is inside the loop's scratch worktree, where no ../markets-data exists)
                                  # the last stdout line is one JSON object {"figures": {...}, ...}
  timeout_s: 1800                 # the builder's value, Greg's to change
  env: {}
budget:                           # every value below is the builder's plain small value, Greg's to change
  max_trials: 3
  max_wall_clock_s: 7200
  max_model_calls: 45             # the session's plain small values for the proposer: one proposing agent a trial,
  max_sub_agents: 3               # 100,000 tokens a proposal by the harness's total. Greg's to change. The loop checks
  max_tokens: 300000              # them before each trial from what the main session reported, so the last trial can
  max_tool_calls: null            # pass a limit by its own use.
  max_concurrent_workers: 1
  max_retries: 0
  max_graph_writes: 20
crash:
  max_consecutive_crashes: 2
keep: strictly_better
stop:
  after_trials: null
  after_trials_without_a_keep: 3
escalate:
  - "the budget is exhausted"
  - "a trial would change a file outside the one plan file"
---

Greg, 2026-11-24, on the loop: "That's the entire reason why we built thsi thing!!! Doesn't matter how much work it is."

Greg, 2026-11-24, on the exit under test: "We should try a simple exit strategy. Sell when we give 20% from highest profit value back once we enter trade."

Greg, 2026-11-24: "Do the simple exit until we do more research and find better ones"

Greg, 2026-11-24: "that is our hold strategy. Hold until we give 20% back"

What is not decided: the figure the loop keeps or reverts by. `direction` is null, so every trial is recorded and none is kept or
reverted. The seven figures are counts of what the platform wrote; none is a result. The timeout and the budget values are the builder's,
not Greg's. The mutable file `paper_platform/execution_plans/loop-trial.json` does not exist in the platform checkout yet: the first
trial's plan is made from a committed plan before the loop is dispatched (Greg's go). The runs of 2026-11-24 are recorded with
`python3 -m tools.kgraph.ingest_platform` and are not scored (Greg: "Don't use score since we didn't use anything we wanted scored").

How it is started, with an agent proposing each change (NOT RUN; every trial, trial 0 included, is an engine run, so it needs Greg's go):

    MARKETS_DATA=/path/to/markets-data python3 -m tools.ratchet.ready --program tools/ratchet/programs/platform_exit.md --data "$MARKETS_DATA"
    MARKETS_DATA=/path/to/markets-data python3 -m tools.ratchet.loop --program tools/ratchet/programs/platform_exit.md \
        --mailbox <mailbox folder> --scratch <fresh scratch folder> --data "$MARKETS_DATA"

The first only reports. In the second, each trial waits for answer.json and usage.json in `<mailbox>/trial-<n>/`; see the manual,
"The loop with an agent proposing each change". This control file has never been run.
