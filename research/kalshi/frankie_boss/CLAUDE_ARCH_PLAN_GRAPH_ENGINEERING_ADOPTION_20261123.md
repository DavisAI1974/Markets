# Graph engineering adoption for Frankie - architecture plan

Author: Claude (architect, chat). Date: 2026-11-23. For: Claude Code ("code"), Codex review.
Source: "Graph Engineering: The Karpathy Loop, Improved 1000x by Itself" (independent synthesis,
July 2026, 11 pages; Greg's upload). Owner direction, Greg 2026-11-23: adopt what we can for
Frankie; the conflicts with existing rules that Claude listed are overruled; token usage is a
real constraint, handled by routing work to Sonnet and Haiku. AWS is not available.

## Current direction (Greg, 2026-11-23, 14:34)

- NOW: run Stage 7 (paper trading on the tastytrade sandbox, rules kept in git) as a standalone
  build, and see what happens before anything in Frankie changes. Until stages 2 and 4 exist,
  the Stage 7 record lives as append-only JSONL in markets-data; it is loaded into the experiment
  DAG and the graph when those are built.
- ALSO NOW: stage 1 (the four agents and the CLAUDE.md roles section) is committed so Codex's
  read-only auditor and verifier tasks run with the new roster (Greg: where they touch each
  other, they run with the new changes). See `CODEX_PROMPT_AMENDMENTS_20261123.md`.
- FILED FOR LATER DECISIONS: stages 2 to 6 and stage 8. They are here so Code has them when Greg
  decides. Nothing in them is built or switched on until he says so. Frankie is unchanged.

## Scope of the overrule (what changes, what does not)

Overruled for this adoption, by Greg's word on 2026-11-23:
- The ratchet loop (keep the change if the metric improves, revert otherwise) is adopted.
- Confidence cutoffs in fan-out reducers are allowed.
- Model-based entity resolution (merging surface forms into canonical entries) is allowed.
- Token-budgeted, graph-built context is allowed for engineering sessions and for Frankie's
  packet. This reverses the 2026-09-14 ruling of no active-recall layer in the native path, and
  the no-caps ruling, for the context path only.
- Exit criteria, evaluation gates and per-run budgets from the paper are adopted.
- Swarms (parallel fan-out of sub-agents) are adopted.

Not touched by this plan (not among the listed conflicts; still in force unless Greg says so):
launch HOLD and step-by-step go; merge authority with Greg; Codex review; code in Markets and
data in markets-data with MANIFEST.json entries; the four trade days through `for_calculations()`;
gross only; zero synthetic data; leakage gate before backtests.

## Token plan (applies to every stage)

1. Model routing. Haiku: search, reading docs, extraction, per-event fan-out workers. Sonnet:
   building, tests, entity resolution, graph queries, reducers. Opus: plans touching core
   Frankie paths, repeated failures, final review, refute waves on high-stakes findings only.
2. Declared budget per run (paper section VIII.B), written in the run's plan JSON before it
   starts: max model calls, max sub-agents, max concurrent workers, max tool calls, max tokens,
   max wall clock, max retries, max graph writes. On exhaustion the run returns completed work,
   unresolved items and the reason it stopped.
3. Every agent run is recorded as an AgentRun entry in the graph with model, input tokens,
   output tokens, wall clock and outcome, so token use is measured per run, not estimated.
4. Graph-built context replaces handoff replay (stage 5). This is the largest expected saving.
   Speculative until measured: the saving is not known until stage 5 runs side by side with the
   current session start and the current Frankie packet (proven packet: 92,427 input tokens at
   3,262 rows, stacked_v1).

## Stage 1 - Role-split agents (ready)

Files: `.claude/agents/scout.md` (Haiku), `builder.md` (Sonnet), `reviewer.md` (Opus), plus the
CLAUDE.md roles section. Delivered 2026-11-23. Changes from the first draft, per the overrule:
- scout: may extract structured findings from documents for the graph (stage 4), each tagged
  with its source path and commit.
- reviewer: adds the grounding check (stage 4b).
- Retire `.claude/agents/aws-*.md` and the `aws-mcp` entry in `.mcp.json` (AWS not available).

## Stage 2 - Experiment DAG (AgentHub pattern)

Every experiment is a node: parent, agent run, hypothesis, diff (commit id), metric values,
runtime, environment, status (kept, reverted, crash), links to related experiments.
- Storage: one SQLite file in markets-data (`experiments/frankie_exp_dag.sqlite`) plus the git
  commits it points at. No server needed at our scale; AgentHub's own design is a bare git repo
  plus SQLite.
- Code: `tools/exp_dag.py` in Markets with the AgentHub verbs: `push`, `fetch <id>`, `log`,
  `children <id>`, `leaves`, `lineage <id>`, `diff <a> <b>`.
- First users: the Experiment Arms sheet of the build plan workbook (backfill its arms as nodes),
  the experiment orchestrator's series and survivors steps, the dipole teacher arms D0-D5.

## Stage 3 - Ratchet loop harness

A `program.md` per loop, holding: mutable files, protected files, the metric and its direction,
the budget, the run command, output parsing, crash handling, keep and revert rules, logging,
escalation to Greg, and when the loop stops. Each trial is pushed to the stage-2 DAG with its
status, including reverted and crashed trials.
- Candidate loops: Granite structured-output plan (BOSS_GRANITE_STRUCTURED_OUTPUT_PLAN_V1),
  packet shrinking (stage 5b), the extraction prompt itself (paper section VII.A).
- Open item for Greg: the metric for each loop is his call. The harness is built metric-agnostic
  so it does not wait on that.
- Runs on the GitHub 16-CPU runner or the RunPod Pod per the dual-compute design; dispatch is
  under HOLD.

## Stage 4 - Knowledge graph (findings memory)

4a. Schema. Node types from the paper (Entity, Claim, Source, Artifact, AgentRun, Evaluation,
Task, Commit, Metric), with Frankie entity subtypes: TradeDay, DipoleEvent (keyed by its
timestamp and run id, e.g. #147), Peak (pinned to timestamp), Family, Chain, CalcOutput, Render.
Edge types: MENTIONS, SUPPORTS, CONTRADICTS, DERIVED_FROM, PRODUCED, EVALUATES, REVISES,
SUPERSEDES, DEPENDS_ON, PARENT_OF, RESOLVED_TO, plus PINNED_AT and MEMBER_OF.
Write invariants (paper appendix): every claim has a source or is marked inference; every
artifact has an authoring run and version; every evaluation names its rubric; every superseded
object stays addressable.
Storage: versioned JSONL in markets-data (`graph/nodes/*.jsonl`, `graph/edges/*.jsonl`, with
MANIFEST.json entries), loaded into a NetworkX MultiDiGraph for queries. SQLite index if queries
get slow.

4a-bis. One register, not two. Codex's plan
`research/kalshi/FRANKIE_INDEPENDENT_SCIENTIFIC_VERIFIER_PLAN.md` (commit 79517f6) defines claim,
check, verdict and adverse-evidence contracts. If both go ahead, those contracts are the field
definitions for this graph's Claim and Evaluation nodes and their edges (a claim revision is a
REVISES edge, a refutation a CONTRADICTS edge, a superseded claim keeps SUPERSEDES and stays
addressable), and its claim lineage is the stage-2 DAG. The verifier is a consumer of this graph,
not a second ledger.

4b. Ingest, cheapest path first:
- Deterministic (no model): calc outputs, renders and MANIFEST.json entries in markets-data
  become CalcOutput, Render and Source nodes; events and peaks from the detector outputs become
  DipoleEvent and Peak nodes pinned to their timestamps.
- Haiku extraction: the 30-plus SESSION_HANDOFF, KICKOFF and HANDOFF files, the research notes
  and the build plan workbook become Claim nodes with SUPPORTS edges to their source file and
  commit. Schema-constrained structured output.
- Sonnet resolution: merges surface forms (component names, file renames, family names across
  runs) into canonical nodes. Every merge keeps aliases, evidence, confidence and the run that
  made it, and is reversible.

4c. Grounding check. The reviewer (and any evaluator) checks a claim against graph edges and
returns structured feedback when a supporting path is missing:
`{"decision": "revise", "claim": ..., "reason": ..., "required_evidence": [...]}`.
This is the same mechanism as the check register in Codex's verifier plan: one
implementation, run by the reviewer agent as the verifier's independent reviewer.
Open item for Greg: whether Granite's B2 shadow-critic role takes on this check for Frankie's
own claims (it fits "a logic helper for Frankie", but Granite's role was set by Greg on
2026-09-29 and is not among the overruled items).

## Stage 5 - Graph-built context

5a. Engineering sessions. A new session starts from a context builder, not from the handoff pile:
resolve the entities in the task, expand one or two hops over allowed edge types, include the
current artifact versions, recent verified claims and open conflicts, serialize within the
declared token budget, attach edge ids for citation.
5b. Frankie's packet. The same builder produces a subgraph-based packet as a new, opt-in input
path beside stacked_v1, run side by side against the current packet with the stage-3 harness.
This changes Frankie's input path, per the overrule; it is built additively and switched only on
Greg's go.

## Stage 6 - Swarm

First workload: one Haiku worker per dipole event on the four trade days. Each reads its event's
stacked, time-exact layers and writes Claim nodes for that event to the graph. Reducer defined
before fan-out (Sonnet), confidence cutoff on what goes to review, Opus or Sonnet refute wave on
what passes, synthesis with cited edges. Declared budget per run; concurrency set to what the
runner and the API rate allow.
Later workloads: auditing every file for one defect class; generating tests for independent
modules.

## Stage 7 - Paper trading on the tastytrade sandbox (Greg, 2026-11-23)

Target: tastytrade sandbox, `https://api.cert.tastyworks.com` (production is
`https://api.tastyworks.com`; credentials are per environment and do not cross over). Sandbox
orders never reach a real market.

7a. Rules in git. Each strategy is a rule file in Markets, `strategies/<name>.yaml`, validated
against `strategies/schema.json`: name, version, instrument and symbology, entry conditions,
exit conditions, sizing, order type, time-in-force, active hours, and the finding ids in the
graph that the rule rests on. Each edit is a commit; each version is a node in the stage-2 DAG.

7b. Runner. `strategies/runner.py`, run on GitHub Actions (no AWS). It loads the rule files at a
pinned commit, computes signals from the market feed, dry-runs each order, then submits to the
sandbox. Credentials live in GitHub secrets only. Dispatch is under HOLD: Greg's go to start it.
Market feed (Greg, 2026-11-23: "Tasty's for now"): tastytrade's production quote stream (API
quote token, DXLink WebSocket) on a production credential used for market data only, never for
orders. Orders go only to the sandbox credential. Not the sandbox's own quotes: sandbox REST
quote snapshots return HTTP 502 and its quotes are not claimed to match the market. Every
streamed event the runner uses is recorded to markets-data alongside the orders and fills.

7c. Record before the reset. The sandbox clears trades, transactions and positions every 24
hours. The runner writes every signal, dry-run, order, status change and fill to markets-data
as it happens (append-only JSONL with MANIFEST.json entries), plus an end-of-session pull of
orders, transactions and positions before the reset. Our record is the record of truth.

7d. Graph links. Each Order and Fill becomes a node: Fill -FILLS-> Order -PLACED_BY-> rule
version (Commit) -DERIVED_FROM-> Claim(s) -> DipoleEvent / Peak / Family. Each fill also stores
the market price from our own feed at the fill timestamp beside the sandbox fill price, since the
sandbox fills at its own rounded quote mid.

7e. First test, before any strategy work: confirm the sandbox lists and accepts orders for the
instruments the rules use (NG futures and futures options). The sandbox docs confirm futures in
general and name no NG or CL contracts. Record what it accepts and how it fills. In the same
test, record which event types and fields the production stream delivers for NG (quotes,
trades, any book depth) and at what timestamp resolution, since rules built on order-book
reads need to know what the feed carries.

7f. The ratchet loop (stage 3) and the reviewer's grounding check (stage 4c) run on rule
versions using the paper record. The official tastytrade MCP server (dry-run-first order flow,
clone and build from github.com/tastytrade/tastytrade-mcp) can be added for agent read access.

## Stage 8 - Token test: can Claude agents carry Granite's daily load (Greg, 2026-11-23)

Background: Granite (self-hosted on the RunPod Pod) carries the daily conversations because a
trading agent running that load through Claude or OpenAI used too many tokens per day. Greg is
fine replacing Granite if the token use works out. This stage measures it.

8a. Baseline. From the retained Granite receipts of a completed cycle, list every Granite call
of one trade day individually: who initiated it, purpose, input tokens, output tokens, wall
clock. Known reference point: the proven packet is 92,427 input tokens at 3,262 rows
(stacked_v1).

8b. Replay the same calls, same day, through each arm, every call recorded individually:
- A: Sonnet with the current packet.
- B: Haiku for extraction and reading calls, Sonnet for reasoning calls, current packet.
- C: arm B with graph-built context (stage 5) in place of the full packet.
- D: arm C with prompt caching on the shared prefix of each conversation.
- E: arm C or D sent as non-urgent batch requests, for calls that do not need an answer
  inside the trading session.
Per call: input, cached-input and output tokens, model, wall clock, cost, and the output itself
next to Granite's output for the same call.

8c. Output first: one table with every call by every arm, plus charts of tokens per call and
cumulative tokens through the trade day for each arm, with row counts reconciled to plotted
points. Every trial goes into the stage-2 experiment DAG. Greg reads the results and decides.

8d. Initiation. Whatever replaces Granite needs something to start each conversation. In the
replay the call schedule comes from the Granite receipts; for live use the trigger is Frankie's
own state (events, births, peaks, exhaustion), posting a task with its subgraph and budget.

## Order

Now: stage 7 (7e first, then 7a, 7b, 7c; 7d and 7f wait for stages 2 and 4).
When Greg decides to proceed with the rest: stage 1, then 2 and 4a together, then 4b, then 3,
then 5a, then 5b and 6. Stage 8 (the token test) can run whenever Greg wants the Granite
question measured. Each stage lands on its
own branch for Codex review; nothing is merged without Greg.

## Open items for Greg

1. Metric per ratchet loop (stage 3).
2. Granite as the grounding checker for Frankie's claims (stage 4c).
3. Where this sits relative to the fresh-run family step.
