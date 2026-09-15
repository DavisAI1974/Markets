# Source and journal audit — updated disposition

## Standing instruction for additional days

**Reuse this pipeline. For additional days, change the dates and run. Rebuild only when functionality is explicitly added or changed.** Date-specific inputs, state and receipts belong in configuration/manifests; unchanged reducers, readers, CPU controls, checkpoints, probes and publishing must be reused. The current Sunday-specific counts/cutoffs still need one-time configuration parameterization before arbitrary dates are accepted.

## Authority and preservation

Read [NEW_CHAT_HANDOFF.md](NEW_CHAT_HANDOFF.md) first. Repository: DavisAI1974/Markets. Publication branch: codex/journal-reduction-stack-20260915. Runtime checkout remains frozen at 9a8f3f46abaa3d840b07b685010108e0c551b174; the publisher advances the remote branch independently. Do not pull/reset the runtime during execution. Original documents and frozen evidence on E/C are retained as history; this Git continuation supersedes their old live-status claims.

## Verified outcomes

- Original source/schedule/lineage workers completed. Source57027 records, logical journal114054 entries.
- Old parallel verification34958705448 was cancelled with owner authorization. Do not restart.
- Actual combined journal run34962256086 succeeded and archived every result file in Git under outputs/frankie-boss/20260915/reduction-stack/runs/34962256086.
- Independent snapshot physicalSHAc54dbe5776c2d5990e18772aadea2123d1e35eb8e6b404a885de14b83495066b differs legitimately from original main journalSHA181467d12a3ea289e67141be2f73e2c5ec068661c5c66c75c51eb30a2787dd6a because the backup includes committed WAL content.
- Compact journalSHA19603159548b1e443a3565f8c999543981c43c23c80fd511c11e760f633b260f;569667584bytes;7129 physical blocks. Logical head d8de0394367b66ea034d2553c3dd45fb7b1ae2b3c92724f8817627118f173500.
- CheckpointSHA750dbb3c63ab672614323dca0dd7f363847ea78aa8a489d0f0b84afe8f00bcf7; state d46ec93352cfa63fab20e260bb608b0b76e71e5ca10cacd952de6b912bea2d64.
- Existing Git archive was restored once to E runtime staging. All17 file hashes and authenticated archive identity passed. No second conversion or source conformance run.

## Launch authority

The independent remote receipt retains gate_authority=false. It was never copied into original completion markers. Original completion, ingestion, schedule and lineage provide the launch source authority; compact prefixes are additionally matched to original journal cutoff digests.

The old handoff helper failed when sorted JSON map order differed from the original schedule packing order. verified_sunday_schedule.py restores the known schema order and checks original logical digestf6922f7a4b93b44394c6683e3d7c45782f27e250c81987bd54414fb124c60e42 without changing values. Focused regression run34964666064 passed once. Original failure evidence remains.

The current builder copies compressed blocks, physically ends each prefix at its authored cutoff, verifies full INPUT/APPLIED records, and records original context selection seeds. No conformance-only projection is used for Frankie.

## Still pending

The complete nineteen-prefix manifest, final data/delta audit, actual model execution and nineteen learning cycles remain pending. Running prefix progress or successful source verification is not model execution. Inspect the primary handoff for exact process IDs and final-gate steps. Historical source audit remains at E:/Codex/Frankie-BOSS-20260915/github-parallel/PARALLEL_SOURCE_AUDIT.md.
