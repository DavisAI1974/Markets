---
# The control file of the packet loop (plan stage 3, candidate loop "packet shrinking"; stage 5b).
# NOT RUN: dispatching a loop needs Greg's go, and the figure it goes by is his to choose.
loop: packet-graph-v1
repo: ../../..                    # the Markets checkout this file is in
mutable:
  - "tools/kgraph/packet.py"
protected:                        # the rule that nothing of the future is in a packet, and its checks
  - "tests/agent_program/test_stage5b_packet.py"
  - "tools/kgraph/store.py"
  - "tools/kgraph/schema.py"
  - "root/**"
  - "research/kalshi/frankie_boss/**"
metric:
  name: tokens_estimated
  direction: null                 # Greg has not chosen the figure this loop goes by: every trial is
                                  # recorded and none is kept or reverted until he does
  unit: tokens (estimated at 4 characters a token)
figures:
  - name: tokens_estimated
    unit: tokens (estimated)
    parse: {kind: json, key: tokens_estimated}
  - name: rows
    unit: dipole events
    parse: {kind: json, key: rows}
  - name: leakage_breaches
    unit: breaches
    parse: {kind: json, key: leakage_breaches}
run:
  command: "python3 -m tools.kgraph.packet --event dipole:dip-19632-1696206142 --budget 4000 --json"
  cwd: "."
  timeout_s: 120
  env: {}
budget:
  max_trials: 5
  max_wall_clock_s: 900
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
  - "a trial shows a leakage breach (the command exits 1: it is recorded as a crash)"
---

Why this loop exists: the proven packet is 92,427 input tokens at 3,262 rows, and shrinking the packet is
one of the most important jobs (CLAUDE.md). This loop would try changes to the graph-built packet
(`tools/kgraph/packet.py`) one at a time and record each.

What is not decided: the figure it goes by (fewer tokens alone is not the goal: a packet can be made small
by leaving out what Frankie needs). Until Greg chooses, `direction` is null and the loop only records.

The checks of the rule (nothing known after the event's moment is in its packet) are protected: a trial
that changes them is not run.
