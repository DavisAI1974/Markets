DROP-IN FOR NEXT CHAT — FRANKIE 30-DAY AWS WORKFLOW

Repo: DavisAI1974/Markets
Branch: chatgpt/frankie-30day-aws-workflow-20261006
Tip: 1f63f76cf70c6e405e3eaebe958647a66526f74b

Read first:
1. research/kalshi/frankie_boss/HANDOFF_20261006_AWS_WORKFLOW.md
2. research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md
3. .claude/skills/experiment-orchestrator/SKILL.md

Mission: finish the actual AWS workflow, not a test framework. Reuse the existing 16-core/15-worker CPU ledger, held
day slots, FIFO queues, claims and receipts. A day stays on the SAME box/16-core lane from ROOT to completion. Frankie
gets new legal knowledge immediately after every knowledge-producing stage.

Granite decision is FINAL for this experiment: active bounded post-class coordinator/facilitator. See
knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md and CLASSROOM_RULES_V3.json. No critic/self-assessment role in this
30-day experiment; no standing GPU. Prefer local/free standard GitHub CPU for quantized Granite if adequate, then small
AWS CPU, paid GPU only fallback.

Important correction: the old four-at-once ROOT run was GitHub-CONTROLLED, not GitHub-computed. Run 36656174396
dispatched four A100 RunPods. Free public GitHub runners are 4-vCPU CPU-only. Paid GitHub T4 GPU runners are $3.12/h and
larger runners are always billed. Current stopped AWS fleet supplies 3 full 16-core lanes: main r7i.8xlarge = 2; Linux
worker r7i.4xlarge = 1. Fourth lane economics remain to solve.

Continue next:
A. inventory/patch the remote Linux worker from ROOT-only to the common ROOT-to-finish day runner;
B. solve minimal cross-box small-state synchronization;
C. finish the missing full search surface, survivor/freeze and confirmation wiring;
D. wire the small Granite facilitator loop;
E. choose the fourth lane;
F. one real ROOT-to-finish E2E only after wiring; fix actual failures; then launch 30 days.

No AWS launch without Greg's explicit go. Read-only AWS/GitHub investigation is fine.
