# CCODE HANDOFF — MARKETS SCIENCE + BUILDMAP MIGRATION (IN PROGRESS)

> **MIGRATION STATUS UPDATE:** The [latest audited inventory](MIGRATION_STATUS_20261108.md) confirms **131 of 133 original source files copied with exact matching Git blob SHAs**. The only two remaining source files are the original DOCX and PDF binary reports, still linked and recorded by source SHA. **Transfer is not declared complete; Claude Code may begin read-only review but should defer any final completeness verdict.** The earlier 63-file figure below records the count when this handoff was first published.
Date: 2026-11-08
**STATUS: EARLY REVIEW COPY; FILE TRANSFER STILL IN PROGRESS — NOT A COMPLETED MIGRATION OR RELEASE ACCEPTANCE**

## Ownership and repository

- **Canonical destination:** `DavisAI1974/Markets`
- **Working migration branch:** `research/markets-adaptive-wavepacket-migration-20261108`
- **Source snapshot:** `DavisAI1974/BuildMap` branch `feat/adaptive-locality-engine-20261108`, pinned to exact commit `8b4295dcb4044a6e4df4b7dbad897a81348fe6e2`.
- **Source draft PR:** https://github.com/DavisAI1974/BuildMap/pull/4 — historical provenance, not the eventual Markets merge target.
- **Destination snapshot directory:** `research/kalshi/adaptive_wavepacket_20261108/buildmap_source_snapshot/`.
- **At creation of this handoff:** 63 of 131 UTF-8 source files had been committed into the snapshot; two binary BuildMap reports (.pdf/.docx) also require separate transfer or explicitly recorded source links. The count and branch HEAD WILL CHANGE as transfer continues. **Do not assume an absent file is intentionally omitted.**
- Markets's default branch (`claude/kalshi-s79-kickoff-ij8t9o` when inspected) is untouched. Existing Markets/Frankie files are not overwritten. The migration branch was created at Markets HEAD `c93895e22a2388112404f0122e37eee4947c5c45`.

## Immediate instructions to Claude Code

**You may begin READ-ONLY review of existing Markets code and already transferred source now.** Source files, tests, and reports are STILL BEING COPIED. Do not judge missing artifacts as abandoned; do not produce a final completeness verdict or edit a partially copied source tree. Wait for an explicit `MIGRATION_COMPLETE` inventory/verification report before making final acceptance conclusions. Recheck HEAD when that report arrives. Do not merge or deploy. Do not start AWS, Frankie, Search, native calculations, active data ingestion, or any production jobs.

**EVERY SCIENTIFIC OBSERVATION OR IDEA IS RETAINED.** Unverified, underidentified, rank-deficient, contradictory, short-lived, anomalous, negative, partially implemented, or scientifically invalid *claims* are annotated as **FOR FURTHER INSPECTION / RESEARCH**; underlying original observations, failed theories, counterexamples, source lineage and research history are not discarded. No smoothing, averaging, flattening, surrogate replacing, implicit directional collapse or elimination of calculations. Preserve event/order/member IDs, actual orders, family, AB/BA direction, clocks and full provenance.

## Correction to previous repository/design language — IMPORTANT

The work was placed in BuildMap primarily as a convenient isolated source repository. **The project is for Markets** and must be organized and owned in the Markets repository. The earlier stand-alone documents often call BuildMap an "optional experimental inspection trial" or say it should be "dropped if no benefit." **That classification is superseded as a project decision:** BuildMap is an **included, planned component** of the Markets scientific workflow and review architecture. We are migrating its actual scanner, visualizer, import/export, workflow views and tests alongside the science, not just its note file. There are still required tests and acceptance gates before trustworthy runtime integration: retain those as **UNVERIFIED / TESTS PENDING**. Do not claim the old static-scanner proof established live integration, and do not deploy or couple it to active trading or production while the migration is incomplete.

The original standalone scientific implementation remains useful as a bounded, self-contained package within Markets until contracts and validation justify connecting consumers. **Isolated does not mean unrelated to Markets; it means it cannot accidentally affect live science or orders.**

## Motivation and scientific history to preserve

The original user-shared post in an earlier session:

> I'm working on some functions that mimic Cauchy behavior (sequence terms that become arbitrarily close), but are bounded by computability over a dynamic domain.
>
> We can achieve this by implementing a wave packet function that localizes both a merge by distance condition and sphere packing (use difference in distance between position neighbors to enable Neumann BCs).
>
> Soft launching hard boundaries #complexity #quantumphysics #mathart #

That post is the basis for the research architecture. Preserve all *separable* questions and their status:
1. Finite computability of Cauchy-like sequences in **dynamic domains**: changing metrics and embeddings require new mathematical contracts; finite-window diagnostics do not prove infinite convergence.
2. Real Gaussian **localized packet/kernel** as a CPU reference; "quantum wave packet" is an inspiration, **not** established Schrödinger/physical state.
3. **Distance-based merge** and **sphere packing/covering** as reversible candidate organization; proximity cannot prove scientific equivalence or justify suppressing native calculations.
4. **Soft-launching hard boundaries**, packet support and uncertainty; preserve the possibility of gradual decisions without silently enforcing permanent hard group deletions.
5. **Neumann boundary inspiration from neighbor-distance differences**: physical Neumann flux needs a defined domain, field, normals, operator and boundary. Current graph Laplacian/weighted-flux experiments are not a continuum Neumann proof; the inspiration remains for further research.

Further scientific discussions:
- **Five-step information-theoretic/operator coupling**, researched from `DavisAI1974/Basic_equations` (`level2_four_sciences.py`, `static_dipole_test.py`, `three_discoveries.py`): derived `H`/`MI`/FI-like proxy; build operator library `Ha, Hb, Ha², Hb², HaHb, MI` and cross terms; fit `dH/dt`; analyze distinct sciences/domains independently; compare surviving operators.
- **Level 2 directional dipoles**, `B_ij(t)=|c_(Hi²)| / |c_(Hi Hj)|` if denominator identified. Distinct pair series, source windows and AB/BA must never be averaged into `B_net`. Historical hardcoded six-node chain is a research precedent, **not** a discovered network.
- **Algebraic geometry correction:** `-Ha²-Hb²+2HaHb = -(Ha-Hb)²` is universally true, including unconnected equal-entropy data with near-zero empirical mutual information. Likewise when donor `Hb=c!=0`, the static `Ha²=(HaHb)²/c²` fit is an identity, not predictive coupling. Retain the hypotheses and corrected counterexamples together.
- **Independent predictive investigation:** static-fit residual vs frozen-support novelty, conditioning/rank, chronological future target-rate prediction, historical donor-lag null, nested linear vs quadratic interaction, nonstationary regimes and random seeds. Positive synthetic results are **hypothesis-generating**, not causal/physical acceptance. Keep weak/negative/held results.
- Original inspiration from **Slayer** (`janearc/slayer`): raw scientific frame separated from display development, deterministic replay probes, content-verified cache keys, atomic output and CPU-first tests. Adopt architecture, not rendering code. The native BuildMap source is still part of this Markets move.
- Related scientific leads remain open: KBK, AI Poincaré, SINDy/PySR, geometry of operator coefficient surfaces, dynamic metric transport, boundary alternatives and independent physics/biology/chemistry/geology comparisons. Do not claim these are implemented without verifying source.

## Markets / Frankie application context (historical requirements, not current run-status claims)

This effort was discussed in connection with **Frankie** and broader Markets research:
- Study native order-book/event observations and market-state neighborhoods instead of allowing opaque **ID/name-driven group count explosion**; IDs are retained as provenance and actual orders, not automatically treated as continuous market-condition axes.
- Keep complete original order/member relationships, FIFO/resting age, queue position, replenishment/withdrawal/absorption/modification, causality, session clocks, family patterns P/O/X/F and historically specified **99 union evidence planes**. Do not assume every venue/workflow uses identical categories or schemas; inspect real source.
- Proposed asynchronous assembly-line workflow: a ready-prepped group can proceed to subsequent calculation without waiting for a whole day; shared reusable tables and exact source identities protect work already done. **Search work and 30-day native ingestion must not be touched by this migration.**
- Preserve AB/BA direction where scientifically meaningful; no duplicate computation eliminated without an independent source/precision/side-effect equivalence proof. Reuse tables and checkpoint receipts only under validated contracts. Investigate conflicting saved results rather than rejecting them irreversibly.
- Original one-day test label `20231018`/`e2e-20231018-a2`, then staggered days/30-day plan, CPU-first; these are **historical research context**, not evidence of currently running jobs or a deployment instruction.
- Prior independent roles included Boss Teacher / ReFRAG, Dipole Teacher, Granite facilitation, and 99-layer native evidence. Trace available Markets source and current branch independently before proposing downstream integration.

## Existing code already in Markets to audit *without overwriting*

Markets root contains `_info_dipole_*` studies, `news_coupling_research.py`, `news_dipole_replay.py`, `markets_adapter.py` and extensive `research/kalshi/frankie_boss/` and associated market pipeline modules. Review those and their current identities, but do not assume the isolated BuildMap source is intended to replace them. We are transferring the work into a **separate subtree** precisely to preserve both code histories without name collisions. Later reconciliation is a separate task.

## Migrated snapshot / what the final source set MUST include

From the pinned BuildMap commit, preserve **all source paths and content**, including:
- `adaptive_locality/` full Python package, all documentation, `research_holds.py`, `research_gates.py`, `standalone_review.py`, coupling, geometry, raw archive, queue, index, cache, visualization, source contracts and related tools.
- All `tests/test_adaptive_locality*.py` and the `tests/adaptive-locality-buildmap-trial.test.js` test.
- Native BuildMap source: `src/` scanner, Python analyzer/observer, workflows, source map/import/export/evidence, `public/` viewer and Guide, `.buildmap/` fixtures/settings, `tests/*.test.js` native tests, package manifests and locked dependencies.
- Architecture/build plans, implementation status, source scientific-context register, Slayer inspiration, independent validation report, acceptance matrix and previous/Claude Code handoffs.
- Original binary PDFs/DOCXs and other non-UTF8 files via a separately verifiable byte-copy path; if that route is unavailable, report each exact missing file and source permalink, never silently pretend the copy was complete.
- Preserve the *original* source snapshot unmodified. Use **this handoff and new Markets-specific README as authoritative migration guidance**; historical documents are evidence, even where their earlier "optional/experimental" language has been superseded.

## What Claude Code should examine now

1. Inventory actual Markets HEAD/branches, Frankie/source paths, market science and prior research handoffs **read-only**.
2. Read snapshot modules and scientific-context docs **as they arrive**; re-read once `MIGRATION_COMPLETE` is verified.
3. Audit overlaps/conflicts between Markets native dipole, Frankie native research and copied standalone `adaptive_locality`. Record candidate interfaces, full input source/clock/calc identity requirements, and tests that must precede wiring.
4. Prepare an architecture review with line-linked defects, independent mathematical derivations, no-loss guarantees, inferred workflows and **a clear list of tests remaining**, especially raw-data provenance, full conservation, family/direction/causal preservation, real-domain/seed/multiplicity controls, exact-condition spectra, Neumann physical eligibility, and BuildMap scanner/collector/UX against real source.
5. Treat **BuildMap as an included product component pending tests**, not a discarded experiment. Its previous scratch scanner measured 7 static source edges and surfaced 8 research gates with no false verified claims; **that is not a verified live integration**.
6. Produce a *proposed* Markets-native module layout and phased interface plan, with an explicit preservation/replay/rollback acceptance matrix; **do not implement live integration during transfer**.

## Acceptance gates and "nothing dropped"

Eight explicitly retained `UNVERIFIED` categories from the prior research registry: independent replication; causal controls; algebraic novelty; rank/conditioning; true parameter Fisher information; physical Neumann boundary; raw external validation; scientific equivalence. **They are not an exhaustive list**. Pending BuildMap integration/real-source tests are additional required gates. For every failure: mark `RESEARCH_HOLD`, `UNVERIFIED`, `CONFLICTING`, `NOT_IMPLEMENTED` or `TEST_PENDING`, preserve the source as available and specify the next independent test.

**This handoff is for an early read-only review while files are STILL TRANSFERRING; it does not certify transfer completion, scientific correctness, or production readiness.**
