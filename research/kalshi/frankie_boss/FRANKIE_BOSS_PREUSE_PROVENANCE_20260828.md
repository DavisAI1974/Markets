# Frankie BOSS pre-use provenance baseline

Date: 2026-08-28

Repository: `DavisAI1974/Markets`

Branch: `codex/frankie-boss-sol-replacement-20260824`

## Purpose

Freeze a factual, additive provenance baseline for the Frankie BOSS before its first reasoning-loop continuation or any first-use experiment. This document records what already exists, what is historically verified, what remains unproven, and which boundaries must remain intact.

This is provenance and context documentation only. It does not authorize or perform a BOSS code change, training run, provider-model call, Frankie launch, production launch, or causal packet-to-tensor/data-seam change.

## Agent-skills lifecycle classification

The BOSS continuation is treated as **brownfield, verification-first** under `addyosmani/agent-skills` release `0.6.7`.

Reason: the BOSS is not a blank project. An executable checkpoint, tests, contracts, provenance artifacts, frozen seams, task records, and architecture decisions already exist. The fact that the BOSS has not yet been used does not make those existing contracts greenfield.

The active meta-skill is `using-agent-skills`. For the present phase, the governing path begins with `context-engineering` and read-only verification before new specification, planning, tests, or implementation. `documentation-and-adrs` is used to preserve decisions and provenance. New BOSS capabilities may later use the full spec -> plan -> build -> review lifecycle, but only after the existing architecture is understood and protected.

Pinned Agent Skills release:

- Release/tag: `0.6.7`
- Annotated tag object: `656688c9117e2a5c371703ef0c005e409df6f16b`
- Tagged commit: `df1edb2e05487d0aa6d93c747141e0aed1187f25`

Do not silently substitute `main` or a later agent-skills release for this BOSS lifecycle.

## Exact pre-document repository state

The authoritative BOSS branch state immediately before this provenance document was created:

- Branch: `codex/frankie-boss-sol-replacement-20260824`
- Remote HEAD: `69c59d6e8527776ff3ed17c813efbbe3cab405d3`
- Direct implementation parent: `fd7d9a00ac2728660de674a06b6ce55e569311f0`
- Governing handoff: `research/kalshi/FRANKIE_BOSS_SOL_REPLACEMENT_HANDOFF_20260824.md`

The handoff commit records the completed QSV registry and BLD-1 mapping checkpoint and explicitly does not claim that the complete Sol replacement has been trained, evaluated, promoted, or launched.

## Existing BOSS authority and artifact locations

- Executable BOSS package: `research/kalshi/frankie_boss/`
- BOSS package checkpoint README: `research/kalshi/frankie_boss/README.md`
- Raw supplied checkpoint: `research/kalshi/frankie_boss/provenance/supplied_checkpoint/`
- Raw supplied checkpoint provenance: `research/kalshi/frankie_boss/provenance/README.md`
- ReFRAG source/governance: `research/refrag/`
- ReFRAG provenance archive: `research/refrag/provenance/davisai_refrag_v21_manifests.zip`
- Lifecycle plan: `tasks/plan.md`
- Lifecycle task record: `tasks/todo.md`

The raw supplied checkpoint remains byte-for-byte comparison authority. Future executable changes belong outside `supplied_checkpoint/`.

## Supplied executable-source baseline

The persisted provenance records these supplied SHA-256 identities:

| Executable file | Supplied source | Supplied SHA-256 |
|---|---|---|
| `causal_packet.py` | `causal_packet.py` | `ea7b7acf43ea2eb03e279acef19b0385dda4a9cd6b3a9e5d53bdab99945e1fc8` |
| `databento_adapter.py` | `databento_adapter.py` | `79ba86199135575aff9fcb686356df07cad242140462449ec7f4a539be7032b9` |
| `decision_contract.py` | `decision_contract(2).py` | `f2c8eb7ba494d490fb42248eeb962f6656c7cd00d5cc30422e9c79fddee2cdfe` |
| `frankie_contract.py` | `frankie_contract.py` | `236eff0c51dc9ef5ca110b2e6febc5f8b1d130360ce6ad5711949d13bdab7bc3` |
| `teacher.py` | `teacher.py` | `d78dc3a839bb09e849e8e3387a3240531f918243071bf38c84f42620dc6e0b43` |
| `trunk.py` | `trunk(2).py` | `2d769713a44ca681991ef2969b0672940dacbaa900730d40dc242a3ce9d665c8` |

ReFRAG archive SHA-256:

`bc2df161ee55c3fe3e65e2071ef2ba87d005d46b1a16fe550c341630d121a26a`

## Frozen/completed boundaries carried forward

The following are existing authority and are not reopened merely because reasoning-loop work begins:

1. Frankie's existing core/provider seam remains unchanged.
2. All 1,940 capability paths and 46 blocks remain wired and addressable in both lanes and all five roles.
3. ReFRAG owns operator registry/governance; BOSS does not duplicate it.
4. QSV remains optional, masked, dormant by default, derived from `QSV_FEATURE_REGISTRY`, and exactly ablatable.
5. `qsv_dim` is derived from `len(QSV_FEATURE_REGISTRY)` rather than a hardcoded observed width.
6. The BOSS trunk contains exactly one shared temporal graph branch.
7. Only the deliberately mapped four learned quantities cross the BLD-1 boundary: `session_net_usd`, `overnight_gap_usd`, `session_path_p50_curve`, and `confidence_label` to their existing public BLD-1 destinations.
8. Other learned heads remain internal diagnostics/training state unless a later explicit typed mapping is separately specified and tested.
9. The causal availability clock remains receive time; exchange event time is not reinterpreted as availability time.
10. Raw supplied checkpoint/provenance artifacts are not normalized, renamed, deleted, or hand-curated.
11. Nova remains a separate project/service.
12. Brain-guided, gated-delta, linear-attention, and other paper-derived mechanisms remain controlled research candidates rather than assumed requirements.

## Historical verification record -- not rerun by this document

The governing handoff and package README record the following prior verification:

- Untouched supplied checkpoint: `101 passed`.
- Bounded implementation/preservation suite: `160 passed`.
- Focused final seam suite: `74 passed`.
- Capability preservation: 1,940 paths / 46 blocks in both lanes and all five roles.
- Exactly one `TemporalGraphBranch` instance.
- QSV masking/absence/ablation behavior verified.
- All 22 ReFRAG manifests parsed and the archive passed integrity checking.
- Fresh-context adversarial review reported no unresolved Critical or Required blocker.

These are historical receipts. They are not represented as tests rerun on 2026-08-28 unless a later provenance entry records a new execution receipt.

## Current scientific/operational status

At this baseline:

- The BOSS executable checkpoint exists.
- The BOSS has **not** been established by this branch as trained, evaluated, promoted, production-ready, or launched.
- No BOSS reasoning-loop continuation has been implemented after the governing handoff.
- No provider model or Frankie run is authorized by this provenance document.
- Current scope is BOSS reasoning loops only.
- The causal packet-to-tensor/data seam is explicitly out of scope for the present tranche.

## Separation from the active two-day Step-1 recovery

A separate branch, `chatgpt/frankie-october-aws-readonly-20260824`, is carrying the two-day/full-MBO Step-1 recovery work. At the time this baseline was prepared, its observed remote HEAD was `e720d645156feaebc207a84df73c125bdceaa1df`, with commit message `ops: launch Step-1 V6 on 64G host [APPROVED_FULL_MBO_STEP1_V6_64G_CONTINUE_20260828]`.

Nothing from that recovery branch is incorporated into the BOSS branch by this document. Cross-branch work must be deliberately compared and provenance-bound before any future incorporation.

## Provenance rules for every subsequent BOSS tranche

Every future BOSS reasoning-loop tranche should append or create durable provenance that records, at minimum:

1. Pre-change branch and exact commit SHA.
2. Governing handoff/spec/ADR and exact external-source versions.
3. Files read as architectural authority and any conflicts found between docs, tests, and code.
4. Exact files changed and why each change is in scope.
5. Test-first receipt: failing behavior/characterization test before implementation where applicable.
6. Post-change focused and preservation test receipts, including environment identity when material.
7. Exact recurrence/depth, stopping/halting, masking, residual/state-update, temporal-graph, training/inference, and ablation/control contracts affected by the tranche.
8. Experiment configuration, seeds, data identity/hash, code SHA, model/checkpoint identity, and control/ablation identity for any result-bearing experiment.
9. Positive, negative, null, contradictory, and KILL results. Do not delete or relabel inconvenient findings as failures merely because they do not support a hypothesis.
10. External research source, version/commit, license, and whether implementation is copied, adapted, or clean-room.
11. Fresh-context adversarial review findings and bounded code-quality review findings.
12. Final commit SHA and remote verification.

Historical provenance documents are append-only in meaning: correct later mistakes by a new dated record or explicit supersession reference rather than silently rewriting the scientific history.

## Immediate next context-engineering step

Before writing a reasoning-loop spec or code, perform a read-only BOSS architecture inventory that identifies the existing authority for:

- loop state,
- recurrence/depth,
- stopping/halting,
- masking,
- residual/state updates,
- interaction with the one shared temporal graph branch,
- training versus inference behavior,
- exact ablation/control behavior.

The purpose of that inventory is to distinguish already-implemented contract from missing contract. Do not invent a generic recurrent loop to fill gaps.

Only after that read-only inventory should a bounded reasoning-loop specification and test-first plan be proposed.
