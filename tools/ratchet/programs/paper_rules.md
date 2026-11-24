---
# The control file of the loop on the paper runner's rules (plan stage 7f: "the ratchet loop runs on rule
# versions using the paper record"). NOT RUN: dispatching a loop needs Greg's go, and so does any paper run.
loop: paper-rules
repo: ../../../../paper-trading-platform      # a checkout of DavisAI1974/paper-trading-platform beside Markets, branch claude/tasty-runner
mutable:                          # a trial may change the rules, and nothing else
  - "tasty/paper/rules_cl.py"
  - "tasty/paper/rules_cx.py"
protected:                        # the engine, the order path, the feed, the checks; and every file that is
  - "tasty/paper/broker_tasty.py" # Codex's or shared (his platform, the line code, ROOT): never touched
  - "tasty/paper/runner.py"
  - "tasty/paper/replay.py"
  - "tasty/paper/ledger.py"
  - "tasty/paper/lines.py"
  - "tasty/paper/events.py"
  - "tasty/paper/clock.py"
  - "tasty/paper/close_out.py"
  - "tasty/paper/feed_tasty.py"
  - "tasty/paper/stream_tasty.py"
  - "tasty/paper/quotes_live.py"
  - "tasty/paper/rule_base.py"
  - "tests/**"
  - "paper_platform/**"
  - "crypto_ng/**"
  - "root/**"
  - ".github/**"
  - ".gitignore"
  - "AGENTS.md"
  - "README.md"
metric:
  name: checks_passed
  direction: null                 # Greg has not chosen the figure this loop goes by, and nothing from the
                                  # sandbox feed is scored: every trial is recorded, none is kept or reverted
  unit: checks
figures:
  - name: checks_passed           # an engineering count: how many of the runner's own checks pass on the
    unit: checks                  # saved recordings with the changed rules. It is not a trade figure.
    parse: {kind: regex, pattern: "(\\d+) passed", group: 1}
run:
  command: "python3 -m pytest tests/tasty_runner -q -p no:cacheprovider"
  cwd: "."
  timeout_s: 300
  env: {}
budget:
  max_trials: 5
  max_wall_clock_s: 1800
  max_model_calls: null
  max_sub_agents: null
  max_concurrent_workers: 1
  max_tool_calls: null
  max_tokens: null
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
  - "a trial would change a file that is Codex's or shared"
---

Why this loop exists: Greg, 2026-11-24: "We're going to ha e to rewrite rules a little later. We have that agent
program that will help highlight things." Each edit of a rule is one trial with its commit, recorded in the
experiment record whatever its outcome.

What is not decided: the figure it goes by. The count of passing checks only says that a rule edit did not break
the runner; it says nothing about whether a rule is any good, and nothing from the sandbox feed is scored. Until
Greg chooses a figure (it needs the richer feed he said is coming), `direction` is null and the loop only records.

The grounding check (`python3 -m tools.kgraph.rule_versions check`) is run on the rule versions beside it: a rule
version that rests on no claim of the graph is reported with the evidence it needs.
