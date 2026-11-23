# Amendments to Codex's prompt "Frankie - Performance Auditor and Scientific Verifier"

From: Claude (architect, chat), 2026-11-23. For: Greg to relay with the prompt.
Trunk tip checked: 79517f6 (auditor agent at b0e5546, verifier plan at 79517f6).

## Timing (Greg, 2026-11-23)

Current work is the tastytrade sandbox paper trading (Stage 7 of
`CLAUDE_ARCH_PLAN_GRAPH_ENGINEERING_ADOPTION_20261123.md`). Frankie does not change yet. Both tasks
in this prompt are read-only audit and planning, so they can run whenever Greg chooses; their
output is filed for the Frankie decisions, alongside the adoption plan.

## Integration rule (Greg, 2026-11-23)

Where these two tasks and the adoption plan touch each other, they run as one system, not two:

1. Order. Commit the stage-1 files first (`.claude/agents/scout.md`, `builder.md`,
   `reviewer.md`, the updated `frankie-performance-auditor.md`, and `CLAUDE.md.patch`), then run
   these tasks, so they run with the new roster.
2. Agents. The main session sends locating and inventory work (file:line, SHAs, receipts, PR
   contents, markets-data manifests) to the scout (Haiku) and passes its pointers on; the audit
   goes to the auditor (Sonnet); independent review goes to the reviewer (Opus). Subagents
   cannot call each other, so the main session does the routing. The verifier's Phase 3
   "independent reviewer" is `reviewer.md`, not a new agent; any deterministic checks it later
   needs are built by the builder. Four agents in total; no more.
3. Records. The verifier's claim, check, verdict and adverse-evidence contracts are the field
   definitions of the graph's Claim and Evaluation nodes (plan stage 4, section 4a-bis); claim
   lineage is the experiment DAG (stage 2). Auditor findings are source-tagged claims, and
   measured spend and tokens are AgentRun and Metric entries. Until stages 2 and 4 are built,
   both write append-only JSONL to markets-data with MANIFEST.json entries, in that shape, so
   they load straight in later.
4. Grounding. The reviewer's grounding check (plan stage 4c) and the verifier's check register
   are the same mechanism: one implementation.
5. Tokens. The plan's model routing and declared per-run budgets apply to both tasks.
6. Reuse/gap matrix. The adoption plan is Greg's adopted direction (2026-11-23). Count it as
   existing architecture in the matrix, not as a new framework that has to justify itself, and
   mark each item's real state (delivered, committed, planned).

## Add to "Read before beginning"

- `CLAUDE_ARCH_PLAN_GRAPH_ENGINEERING_ADOPTION_20261123.md` and `README_HANDOFF_20261123.md`
  (the graph-engineering adoption plan, stages 1 to 8, and today's direction).

## Task 1 - Performance auditor

1. Use the updated `.claude/agents/frankie-performance-auditor.md` from this handoff (Greg,
   2026-11-23): `model: sonnet`, and no AWS anywhere in it. Commit it over b0e5546's version.
2. Replace item 5's "avoidable AWS expense" with "avoidable RunPod Pod, GitHub runner and model
   API token spend". AWS is not available (Greg, 2026-11-23).
3. Add to item 7: list any check that the planned experiment DAG (stage 2) or knowledge graph
   (stage 4) would make redundant, so it is recorded once there instead of rerun.
4. Add a section: Granite call load. From existing Granite receipts, list every Granite call for
   one completed trade day (purpose, input tokens, output tokens, wall clock). This is the
   baseline Stage 8 of the adoption plan needs (the token test for replacing Granite). Read-only,
   from saved receipts only.

## Task 2 - Scientific verifier

1. Add to the comparison list: the adoption plan's stage 2 (experiment DAG), stage 4 (knowledge
   graph: Claim, Evaluation and Source nodes, provenance on every edge, four write invariants)
   and the reviewer agent's grounding check (`.claude/agents/reviewer.md`, delivered 2026-11-23,
   not yet committed).
2. The plan's "one canonical claim/evidence register" should be the stage-4 graph, with the
   verifier's claim/check/verdict/adverse_evidence contracts as its field definitions and the
   stage-2 DAG as claim lineage. Assess that mapping rather than a separate register.
3. Add one link to assess: sandbox strategy rules (Stage 7a) name the claim ids they rest on, so
   every paper order traces to registered claims and their checks.
4. Status vocabulary: Greg does not want verdict or pass/fail framing unless he asks for it.
   Flag where `SUPPORTED_WITHIN_SCOPE` / `REFUTED_WITH_EVIDENCE` style labels appear and propose
   descriptive status fields (what was checked, what was observed, what remains open) for his
   decision.

## Both tasks

- Replace "raw tick tape belongs in S3" with: the S3 bucket is undecided (Greg, 2026-11-23);
  leave the bucket, its data and S3 code paths as they are, and do not plan new S3 use.
- Unchanged: read-only, no code changes, no commits, launch HOLD, four trade days, gross only,
  no synthetic data, leakage gate, Markets code only, results to markets-data.
