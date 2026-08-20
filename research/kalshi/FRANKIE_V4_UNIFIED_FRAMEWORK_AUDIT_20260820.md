# Frankie V4 unified framework audit — 2026-08-20

Status: **DESIGN/AUDIT ONLY. V4 IS UNAUTHORIZED AND UNLAUNCHED.**

Exact checkpoint audited: `71a71e94c08c27615b05f10165cbc88e38f2aa56`.

Read-only provisional source inspected at
`C:\Users\A\Documents\Codex\2026-08-19\i\work\Markets`. None of its V4 files
were copied, staged, launched, or treated as authoritative.

## Decision

One unified V4 is technically feasible and is the only safe design. The
provisional package is only partly unified: POX and D0–D5 share a useful core
model/lock/update loop, but their runners still independently own population,
split, reveal, feature, schema, run-identity, and output contracts. D4/D5 bypass
the walk-forward engine through a separate case-study path. That is still more
than one V4 implementation.

Preserve the documented run characteristics unless a demonstrated defect below
requires correction: every causal second, full curve-to-date state,
discovery-only lock choice, frozen/adaptive twins, learning only after
conservative reveal, immutable active-instance snapshots, D4/D5 case-study
status, the fixed POX branch population, no voting, and no promotion.

## Duplication and demonstrated conflicts

1. `ng_exhaustion_v4_core_20260820.py` provides a shared loop, while the POX
   and D0–D5 drivers separately implement cases, splits, reveal semantics,
   features, audit fields, schemas, and identities.
2. D4/D5 use `full_curve_case_study`, a second execution path rather than an
   adapter mode of the shared engine.
3. The reconciler hard-codes D lanes and POX targets separately; both workflow
   files repeat that registry again.
4. D cases may extend to `stage_censor_time - 1` after truth is revealable.
   Every primary case must satisfy `start_timestamp <= end_timestamp <
   reveal_timestamp`.
5. The durable 3,429-case POX split is not reveal-time isolated. On 2025-07-17,
   the last fit outcome becomes known 28 seconds after the first tune case
   begins. Identity chronology alone is insufficient; a reveal-time embargo is
   required.
6. POX `MEMBERSHIP` uses the full roster while `BRANCH` uses the fixed 3,429
   ledger, but both are labeled `FIXED_3429_DO_NOT_REOPEN`. They need distinct
   population identities.
7. The fixed branch is future-origin/oracle conditioned before origin birth.
   Preserve it only as a non-promotable posthoc benchmark. A genuinely causal
   activation bridge would be a separate proposal.
8. The canonical normalized-LF POX ledger SHA-256 is
   `328d66e61b14d4a04905ea95776cb7cca153a52726bf6cd41d18bc6aa2a645dc`.
   The provisional workflow checks counts, not this semantic hash.
9. POX schema discovery probes one to three cases instead of preflighting the
   whole population and binding ordered names/types/semantics.
10. Mutable cases receive `_v4_start_timestamp` in place; split disjointness,
    unique identities, and block isolation are not engine invariants.
11. The claimed shared graph encoder is actually deterministic signed-hash
    ordered-message features plus separate online logistic heads. It may remain
    a baseline, but must not be called a shared learned graph encoder, TGN,
    TGAT, spectral filtering, ReLIC, or graphon invariance.
12. POX does not literally retain every V3 field; unsafe fields are removed or
    renamed and a safe subset is selected. The exact safe mapping must be
    enumerated.
13. A candidate “adapter” is a copied, updated SGD model, not a reversible
    serialized delta. Current rollback identity is a label, not byte evidence.
14. Retention reuses same-head discovery/tune rows instead of the documented
    protected D0–D3/class/POX/no-lock/wrong-lock/latency/D4/D5 matrix and fresh
    chronological evidence.
15. Several causal facts are asserted booleans rather than recomputed, including
    earlier-call immutability, no post-reveal revision, and no future target use.
16. A terminal accepted update can enter lineage even though it applies to no
    later instance.
17. Lock selection has no invalid/no-reliable-lock outcome.
18. Snapshot identity binds width, not ordered feature semantics. Run identity
    omits material input, split, adapter, configuration, code, and ruleset
    hashes; S3 versions/content digests are not fully pinned.
19. Full-curve runtime and artifact volume have not passed the six-hour
    workflow preflight.
20. Reconciliation does not recompute movies, first locks, summaries, update
    lineage, rollback, split isolation, fixed-ledger semantics, or many claimed
    booleans. POX equivalence/count/source/reveal checks are incomplete.
21. Updated recovery rules bind the source run/workflow/dispatch SHA, but must
    separately record `runner_commit`, `adjudicator_commit`, and an exact
    `reconciliation_ruleset_id` plus content hash.

## Required unified design

Use one immutable `V4LaneSpec` registry, one orchestrator, one engine, and one
registry-driven reconciler. An adapter may own only target/model-specific
population, labels, reveal logic, causal start/end policy, feature provider,
coordinate formatting, and declared case-study restrictions. The shared engine
owns chronology, immutable snapshots, every-second replay, movies, locks,
reveal-before-update enforcement, candidate evaluation, rollback lineage, and
normalized outputs.

Required modes:

| Adapter | Population | Mode | Restriction |
|---|---|---|---|
| D0–D3 target adapters | frozen D populations | `WALK_FORWARD` | target-specific label/reveal/coordinate only |
| D4/D5 adapters | preserved 8 and 1 cases | `CASE_STUDY_NO_ADAPTATION` | same movie/engine contract; no general update |
| POX membership adapter | full positives plus controls | `WALK_FORWARD` | explicit membership/control population |
| POX fixed branch adapter | exact 3,429 ledger | `WALK_FORWARD_POSTHOC_ORACLE_CONDITIONED` | canonical hash; permanently non-promotable label |

The reconciler must consume the same registry and normalized artifact schema.
Adding a lane must require one adapter plus conformance tests, not independent
edits to drivers, workflows, and reconciler lists.

## Minimum normalized artifact identity

Each execution artifact must bind runner/engine/adapter code hashes; exact input
object version and content hashes; canonicalization; population/split/case
manifests; ordered feature schema; model/config/lock/update/retention policies;
immutable per-instance snapshots; movie rows and recomputable movie hash; first
lock; recomputable summaries; no-reliable-lock/no-lock/wrong-lock/late/censored
partitions; update ancestry; and byte-verifiable rollback artifacts.

Adjudicated output additionally binds the exact adjudicator commit and
reconciliation ruleset hash. None of these identities grants promotion.

## Required pre-launch gates

1. Clean descendant of `71a71e9` with the overlapping-predecessor causal fix.
2. Single registry and adapter-conformance gate; no alternate D4/D5 engine.
3. Causal-window, snapshot-freeze, learn-after-reveal, and no-mid-instance-update tests.
4. Identity/group-disjoint and reveal-embargo splits, including a regression
   test that rejects the observed 2025-07-17 POX overlap.
5. Distinct membership/branch population identities and exact 3,429/1,546/1,883
   counts plus canonical LF ledger hash.
6. Whole-population ordered semantic-schema preflight and causal mutation tests.
7. Discovery-only lock selection with explicit invalid/no-reliable-lock status
   and independent first-lock recomputation.
8. Fresh chronological update evidence, complete protected retention matrix,
   no accepted-but-unusable terminal update, and real rollback artifacts.
9. Reconciler tamper tests for movies, probabilities, timestamps, snapshots,
   summaries, sources, ledgers, ancestry, and asserted booleans.
10. Dual runner/adjudicator SHA and ruleset binding.
11. Full-curve time/memory/row/artifact-byte preflight without weakening the
    primary full-curve policy.
12. Full Frankie suite, selftest, unified-V4 adversarial tests, and reconciliation
    tests green on one exact candidate commit.

The provisional dirty-tree V4 tests passed 26/26 read-only, but they do not
cover the defects above and do not authorize a run.

## Authorization sequence

There is no V4 launch commit. First implement and test the unified design on a
clean descendant; then report the exact 40-character candidate SHA plus
engine/adapter/ruleset identities and remaining blockers. A separate explicit
user authorization must name that exact commit, workflow scope, and ruleset
before dispatch. No V4 run occurred during this work.
