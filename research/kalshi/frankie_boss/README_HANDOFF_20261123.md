# Handoff index - Graph engineering adoption and tastytrade sandbox (2026-11-23)

From: Claude (architect, chat). To: Claude Code ("code"). Owner and merge authority: Greg.

## Current direction (Greg, 2026-11-23)

1. Build and run the tastytrade sandbox paper trading now: strategy rules kept in git, a runner
   on GitHub Actions, every signal, order and fill recorded to markets-data before the sandbox's
   24-hour reset. First step is checking that the sandbox accepts NG futures and futures
   options. This is Stage 7 of the plan. Starting the runner needs Greg's go. Market feed for
   signals: tastytrade's production quote stream for now (Greg), on a data-only credential;
   orders go only to the sandbox.
2. Frankie does not change yet. Everything else in the plan is filed for when Greg decides.
3. AWS is not available. Nothing new uses S3, EC2, SSM, Bedrock, SageMaker or boto3.

## Files

| File | Goes to | Status |
|---|---|---|
| `CLAUDE_ARCH_PLAN_GRAPH_ENGINEERING_ADOPTION_20261123.md` | Markets, `research/kalshi/frankie_boss/` | Full plan, stages 1 to 8. Stage 7 is current work; the rest is filed |
| `.claude/agents/scout.md` | Markets, `.claude/agents/` | Stage 1, ready, filed |
| `.claude/agents/builder.md` | Markets, `.claude/agents/` | Stage 1, ready, filed |
| `.claude/agents/reviewer.md` | Markets, `.claude/agents/` | Stage 1, ready, filed |
| `CLAUDE.md.patch` | Markets, applied to `CLAUDE.md` | Stage 1 roles section; applies cleanly to trunk tip 012586b |

## The plan, stage by stage

- Stage 1: three agents. Scout on Haiku (finds things, extracts findings for the graph), Builder
  on Sonnet (implements a settled plan, diff first), Reviewer on Opus (plans touching core
  Frankie paths, repeated failures, final diffs, grounding check). Retire the aws-* agents and
  the aws-mcp entry.
- Stage 2: experiment history in the AgentHub style. SQLite in markets-data plus git commits,
  with children, leaves, lineage and diff commands. Every trial kept with its status.
- Stage 3: keep-if-better loop harness with a control file per loop. The metric for each loop is
  Greg's call.
- Stage 4: knowledge graph of findings in markets-data (versioned JSONL, NetworkX). Calc outputs,
  renders, events and peaks added by code; handoffs extracted by Haiku; merges by Sonnet, each
  reversible. Reviewer checks claims against graph edges.
- Stage 5: context built from the graph, for engineering sessions first, then as an opt-in input
  path for Frankie's packet beside stacked_v1.
- Stage 6: swarm, one Haiku worker per dipole event writing findings to the graph.
- Stage 7: tastytrade sandbox paper trading (current work, see above).
- Stage 8: token test. Replay one trade day of Granite's calls through Sonnet, Haiku plus Sonnet,
  graph-built context, prompt caching and batch requests; every call recorded individually with
  tokens, cost and output next to Granite's. Settles whether Claude agents can carry Granite's
  daily load. Greg is fine replacing Granite if the token use works out.

## Open items for Greg

1. Metric for each keep-if-better loop (stage 3).
2. Granite as the grounding checker, or replaced outright after the stage 8 test.
3. When the filed stages proceed, relative to the fresh-run family step.
4. The S3 bucket (raw tick tape, the 5-year NG MBO pull): Greg has not decided yet. Until he
   does, leave the bucket, its data and the existing S3 code paths exactly as they are. No
   deleting, moving or rewriting.

## Still in force

Launch HOLD and Greg's step-by-step go; Greg's merge authority; Codex review; code in Markets,
data in markets-data with MANIFEST.json entries; the four trade days through
`for_calculations()`; gross only; zero synthetic data; leakage gate before backtests.
Overruled for this adoption only (Greg, 2026-11-23): the rule conflicts listed in the plan's
"Scope of the overrule" section.
