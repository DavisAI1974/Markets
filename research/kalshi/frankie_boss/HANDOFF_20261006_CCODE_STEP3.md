# CCode assignment — Step #3 existing all-plane search coverage

Greg authorized a separate CCode task while Codex continues Step #2. Work in your own branch; do not push directly to
Codex's branch. Fetch `chatgpt/frankie-30day-aws-workflow-20261006` from `DavisAI1974/Markets`, verify the latest tip and
preserve newer work. Start with `HANDOFF_20261006_STEP1_RECOVERY.md`, follow its reading order, then read
`HANDOFF_20261006_STEP2_KNOWLEDGE.md`, including its latest source audit. Read applicable skills and repository instructions.

## Your task

Own Step #3's existing search/source coverage. **Inspect before building. Do not assume missing implementation.**
Trace the complete existing inventory of Frankie's normal ingest/calculation planes into the active scientific search:
full native journal, full book, FIFO/queue/order age, families/D structures, exhaustion, Dipole and the external day file.
Examples are not a whitelist. Distinguish source availability, fields actually consumed, calculations actually performed,
existing-but-uncalled implementation, genuinely missing connections, and runtime verification.

Read and reuse these existing components before editing:
- `deploy/aws/box/frankie_box_experiment_search.py`, `frankie_box_experiment_surface.py`,
  `frankie_box_experiment_transforms.py`, `frankie_box_experiment_data.py`, `frankie_box_experiment_root.py`.
- `deploy/aws/box/frankie_box_joined_teacher.py`, `frankie_box_host_config.py`,
  `frankie_box_scientific_dialogue.py`, `frankie_box_teacher_discussion.py`.
- `SPEC-scientific-teacher.md`, `SPEC-joined-teachers.md`, the R4 build workbook, and the current experiment spec.
- Read `drafts/SEARCH_SURFACE_AND_CONFIRMATION_NOT_APPLIED_20261006.patch` as evidence only. Do not apply it.

Known source facts to verify, not blindly reproduce: ROOT uses `bedrock=False`; export excludes certain bedrock paths;
search currently uses selected ROOT spools; the native full-evidence surface helper already exists. The older joined
teacher path exists but belongs to the former model-driven dialogue and is disabled by host configuration. A full-book
raw read does not by itself prove consumption of separately derived family/D planes. Do not turn every old switch on.

First produce a compact source-to-consumer map with exact functions/paths and exclusions. Then fix only verified Step #3
reader/wiring gaps for already available data, reusing existing scientific functions. Preserve math, native resolution,
source identities, causal timestamps, missing/invalid states, every occurrence and claim scope. List producer-activation
or mathematical design decisions that need coordination instead of silently rebuilding ROOT or changing statistics.
Do not activate cross-transform/conditional/frozen-lag draft behavior as a shortcut.

## File ownership

You may edit only verified Step #3 search/source-reader wiring in `frankie_box_experiment_search.py`,
`frankie_box_experiment_surface.py`, `frankie_box_experiment_data.py`, and your own report
`research/kalshi/frankie_boss/CCODE_STEP3_SOURCE_COVERAGE_20261006.md`.
Read other files freely. If a fix requires a different owner/file, document the exact required change for integration.
Codex owns Step #2 classroom code/external adapter/runner/learner reader, experiment teacher, accumulated knowledge,
queue/controller, directives and shared handoffs. Do not edit them in parallel. Your earlier `c547c01a` is integrated;
Codex's new SOCRATIC/VERIFY connection reuses it. Do not duplicate that work.

## Settled constraints

- Both teachers see all applicable ingest/calculation data, excluding Frankie's private trade-decision logic. Lawful
  finding/claim projections keep their author and scope; do not expose private notes, answer keys or Jev's blind claims.
- BOSS retains its original broader representation supervision, mathematical targets, masks, controls and training
  role. Scientific teacher owns mechanism/evidence testing/search. Shared discovery is additive to those roles.
- All 30 random-order days continuously share completed knowledge at applicable workflow boundaries. Trading-date
  chronology and former year-based holdout rules do not gate learning. Preserve causal time within each raw day.
- Scientifically checked single occurrences receive equal treatment. No rarity/minimum-days gate; repeated use of
  identical evidence is not independent scientific confirmation. Preserve nonlinear/multivariable discovery methods.
- AWS CPU ONLY, NO PODS. Exactly three held 16-CPU lanes, two main and one Linux; 15 workers plus coordinator each.
  Same owning box/lane from ROOT through completion. Giant evidence stays local; preserve existing save/resume.
- No AWS starts, installations, dispatch, scientific runs or model calls. No explicit AWS go has been given.
- No extra tests or validator framework. Source review and syntax checks only. No benchmark/canary/E2E.
- STOP AND DISCUSS BEFORE #5. Preserved draft stays unapplied. Granite report is another chat; Jev CPU is discussion pending.
- One real E2E only after wiring/discussions and explicit AWS go; 30 days require separate authorization.

Return the source map, precise changes (if any), source-only checks, unresolved decisions and commit SHA. Commit/push
your branch with `[skip ci]`; do not claim runtime verification or a passed E2E. Codex will review and integrate.
