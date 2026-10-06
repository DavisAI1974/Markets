# CCode parallel assignment — step 2 reused-teacher delivery

Run using-agent-skills, memory MCP and local context-engineering.
Repo: `DavisAI1974/Markets`.
Base: `chatgpt/frankie-30day-aws-workflow-20261006`; initial checkpoint `d303f84f87e67fff26ed6f6e011cbaf364d6a9cb`.
Fetch latest and preserve newer work. Create a separate branch from the latest base; do not push to the shared base.
Codex will integrate the resulting narrow commit.

Greg's final clarification: ALL 30 days run as continuous learning in random order. Do not gate learned knowledge by
market date OR the old discovery/confirmation label; October 2024 findings may teach a later-running October 2022 day.
All assigned years now use the existing learning route. Keep per-day raw-source timing and host-answer/Jev walls. Checked findings may teach
subsequent same-day work immediately; no remainder-of-day embargo and no double-counted independent check.

Read `HANDOFF_20261006_STEP1_RECOVERY.md` first and follow its reading order. Then read
`HANDOFF_20261006_STEP2_KNOWLEDGE.md` for Codex's concurrent learner/carry changes.

Own `deploy/aws/box/frankie_box_experiment.py`: `Run.teacher()`, `Run.teacher_knowledge()` and directly necessary
teacher reuse/publication call sites only. Existing code already attempts publication for reused rows; inspect before
changing anything. Trace fresh and reused rows through real knowledge publication, including source/day binding,
complete legal measured findings, recovery/idempotent publication and publication before the next dependent boundary.
A retained file or stage receipt alone does not prove delivery. Read the learner/lane-state interfaces for compatibility.

Do not edit classroom_code, experiment_classroom_v2, lane_state, brain, previous-class selection/carry or Run.record;
Codex owns those. Report required interface changes. Preserve teacher math, observations, source evidence, host-answer
walls and Frankie's private decision process. Do not modify pinned producers or apply the saved search/confirmation patch.

No tests, validator framework, installations, AWS starts or compute dispatch. Source/syntax/diff checks only. Exactly
three held 16-CPU lanes, two main and one Linux, 15 workers plus coordinator. Same box/lane ROOT through completion,
giant artifacts local, AWS CPU only, no Pods. Checked single occurrences receive equal treatment.

Stop before #5; Granite and Jev CPU decisions require discussion. One real E2E requires completed wiring/discussions and
Greg's explicit AWS go. Thirty days requires separate authorization.

Push a narrow commit to your separate branch with `[skip ci]`; return branch, SHA, changed functions, exact source
checks and unresolved integration needs. Report SOURCE-BUILT / RUNTIME-UNVERIFIED. If no correction is needed, provide
the concrete trace and findings rather than manufacturing a patch.
