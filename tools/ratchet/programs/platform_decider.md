---
# The control file of the loop on the decider program (graph adoption plan, stage 3, with the platform's decider
# door). NOT RUN: dispatching a loop needs Greg's go, and every trial of it is an engine run on the stored tape.
# The loop is started with PLATFORM (a checkout of paper-trading-platform), MARKETS_DATA (the markets-data checkout)
# and TRIAL_KEEP (a folder for the records each trial keeps) set in its environment.
loop: platform-decider
repo: ../../..                    # this Markets checkout; the loop's worktree is a worktree of it
mutable:                          # the one file an agent changes: the decider program
  - "tools/decider/programs/loop_decider.py"
protected:                        # everything else of Markets. A glob `tools/**` would also match the one mutable file
  - "*"                           # (protected wins), so: each file directly in a folder, each folder by name, and in
  - ".claude/**"                  # tools/decider and its programs folder each file that exists today. A new file beside
  - ".claude-plugin/**"           # them is "outside mutable" and is refused too.
  - ".github/**"
  - "agent-pass/**"
  - "artifacts/**"
  - "crypto_ng/**"
  - "data/**"
  - "deploy/**"
  - "desk/**"
  - "odcore/**"
  - "plugins/**"
  - "research/**"
  - "root/**"
  - "scripts/**"
  - "tasks/**"
  - "tests/**"
  - "tools/*"
  - "tools/kgraph/**"
  - "tools/ratchet/**"
  - "tools/swarm/**"
  - "tools/token_test/**"
  - "tools/decider/*"
  - "tools/decider/programs/*.md"
  - "tools/decider/programs/skip_all.py"
  - "tools/decider/programs/decider_v1.py"
proposer:
  kind: file                      # a proposal is a whole new program file (tools/ratchet/file_proposer.py)
metric:
  name: trades_opened
  direction: null                 # Greg has not chosen the figure this loop keeps or reverts by, so every trial is
                                  # recorded (status "recorded") and none is kept or reverted. No result figure is
                                  # declared until he chooses one. trades_opened is a count of what was written, named
                                  # here only because a metric name is required; it is not a measure of anything good.
  unit: trades
figures:                          # the last line of the wrapper: the trial's figures() counts and four counts of
  - name: journal_rows            # decisions.jsonl, each its own line, none combined with another, none a result
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
  - name: decider_asked
    unit: questions
    parse: {kind: json, key: figures.decider_asked}
  - name: decider_take
    unit: answers
    parse: {kind: json, key: figures.decider_take}
  - name: decider_skip
    unit: answers
    parse: {kind: json, key: figures.decider_skip}
  - name: decider_skip_by_code
    unit: answers
    parse: {kind: json, key: figures.decider_skip_by_code}
run:
  command: "python3 -m tools.decider.trial_with_decider --program tools/decider/programs/loop_decider.py --platform \"$PLATFORM\" --data \"$MARKETS_DATA\" --trade-day 2023-10-02 --plan \"$PLATFORM/paper_platform/execution_plans/loop-trial.json\" --from-minute 30 --minutes 30 --budget 3000 --keep \"$TRIAL_KEEP\""
  cwd: "."                        # the last stdout line is one JSON object {"trial": {...}, "figures": {...}}
  timeout_s: 3600                 # the builder's value, Greg's to change
  env: {}
budget:                           # every value below is the session's plain small value, Greg's to change
  max_trials: 3
  max_wall_clock_s: 14400
  max_model_calls: 45
  max_sub_agents: 3
  max_tokens: 600000
  max_tool_calls: null
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
  - "a trial would change a file outside the one decider program file"
---

Greg, 2026-11-24: "We are supposed to be testing our new agents setup to see if they could be the decders"

Greg, 2026-11-24, to a decider that the agents write once as a program and that then answers at every opening signal with no model call: "Let's do it then."

What is not decided: the figure the loop keeps or reverts by. `direction` is null, so every trial is recorded and none is kept or
reverted. The eleven figures are counts of what the platform and the decider's door wrote; none is a result. The timeout and the budget
values are the builder's, not Greg's. Trial 0 is the program as it stands (it takes every signal: the platform as it runs today seen
through the gate); a trial after it runs the program an agent wrote.

NOT RUN. Every trial, trial 0 included, is an engine run on the stored tape, so it needs Greg's go. How it is started, with an agent
proposing a whole program each trial (NOT RUN):

    export PLATFORM=/path/to/paper-trading-platform MARKETS_DATA=/path/to/markets-data TRIAL_KEEP=<a free folder>
    python3 -m tools.ratchet.ready --program tools/ratchet/programs/platform_decider.md --data "$MARKETS_DATA"
    python3 -m tools.ratchet.loop --program tools/ratchet/programs/platform_decider.md \
        --mailbox <mailbox folder> --scratch <fresh scratch folder> --data "$MARKETS_DATA"

The first only reports. In the second, each trial waits in `<mailbox>/trial-<n>/` for proposed.py, answer.json and usage.json.
