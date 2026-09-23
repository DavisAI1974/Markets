# Dipole knowledge gap review — 2026-09-22

Status: reviewed research inventory plus an explicit principal signal-discovery instruction. No teacher seed, formula, runtime configuration, or deployed artifact changed. Source snapshot: `bb28b35eefd3cb2dc602031800ac9b7d3d2d5175`, branch `codex/trading-day-readiness-20260922`.

The survey found missing historical mathematics and missing qualifications on old claims. It found no newly validated trading mechanism that should automatically replace current teacher mathematics. Historical failed, superseded, and unresolved work remains useful learning material when its status and reasons travel with it.

## What already exists, and what “teacher” means

The current native route selects the governed C15R3 mathematical teacher. It computes nineteen queue/pressure/D-chain targets; it is not a conversational agent or a repository-reading knowledge base. The classroom wraps those targets with explanations, observation review, 171 pair comparisons, and deterministic grading. It does not currently provide an independent scientific-reasoning teacher that can endorse a new mechanism. See [sunday_native_runtime.py:66](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/kalshi/frankie_boss/sunday_native_runtime.py#L66), [dipole_classroom.py:1](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/kalshi/frankie_boss/dipole_classroom.py#L1), and [dipole_classroom_final_review.py:151](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/kalshi/frankie_boss/dipole_classroom_final_review.py#L151).

The classroom progression remains TEACH → GUIDED → SOCRATIC → VERIFY. The preceding repair retains completed exchanges and all learned records, including uncertainty, corrections and rejected findings. That repair is committed and CI-tested; production deployment and cycle 0 have not happened. Carrying completed learning forward does not turn that learning into an independent discovery on a historical replay.

The retained principal prompt declares **71 artifacts: four inline and 67 for retrieval**, including the full NG brain, Phase-1/2 research and four proposal layers. It also supplies 44 established Memory A findings. This is much broader than the nineteen classroom descriptions. Indexing a file is evidence that it was declared available, not proof that every teacher has read it. See [historical-prompt.md:28](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/kalshi/frankie_boss/sunday_20260915_package/FB/actual-feedback-run/execution/cycle-00/principal/historical-prompt.md#L28).

At this snapshot 63 of the 71 original paths exist. Eight original paths are absent; the 166,700-byte Memory A seed is retained under [FROZEN_MEMORY_A_20211003.json:1](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/kalshi/frankie_boss/sunday_20260915_package/FB/retained-principal/FROZEN_MEMORY_A_20211003.json#L1). This audit read that retained copy. It does not claim to have revalidated all remote runtime bundle bytes or restored the other original paths.

## Reviewed missing payloads

“Missing” below means not located in the inspected classroom/math definitions and accessible retained knowledge corpus, after checking equivalent concepts and transitive references. It is not a proof of absence from inaccessible conversations or unretained external archives.

### K01 — Keep the different Dipole constructions distinct

**Retain as historical definitions, with separate provenance.** The original supervised algebraic construction projects a per-trade vector onto winner/loser centroids:

`H_a = c·c_win / ||c_win||; H_b = c·c_lose / ||c_lose||; H_a² = a + b(H_a H_b) + c₂(H_a H_b)².`

These are projections, not cosine similarities; winner alignment is not buy/sell direction. The original 128-dimensional construction, later 15-dimensional coupling-vector port, entropy/MI flow construction, and current C15 pressure surface are different representations. A high fit to outcome-labeled centroids is not a causal price forecast or a profit result.

Sources: [dipole_predictor.py:4](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/odcore/dipole_predictor.py#L4), [dipole_trade.py:13](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/odcore/dipole_trade.py#L13), [_markets_algebraic_dipole.py:164](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/vendored_build_kit/_markets_algebraic_dipole.py#L164), [SESSION_HANDOFF_2026-06-21_S33.md:19](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/SESSION_HANDOFF_2026-06-21_S33.md#L19).

The teacher needs this missing semantic crosswalk, not an unreviewed replacement of C15. The failed buy/sell-Vasicek reconstruction must remain marked as a failed reconstruction.

### K02 — Preserve the centroid invalidation and subsequent research decision together

**Superseded predictive claims; structural research remains open.** Earlier results were affected by timestamp/horizon corruption, disjoint source/date pools, outcome-derived features, and episode anchors. The same-period/same-pipeline S34 check reported zero of twelve cells surviving its 500-permutation null and explicitly superseded the earlier `z=+9.6`/confounded classification headlines. S35 then set aside balanced-class centroid separation as the grading objective while preserving the distinctive-fingerprint/stack research direction. It did not declare every Dipole construction dead.

Sources: [SESSION_HANDOFF_2026-06-13_S30.md:15](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/SESSION_HANDOFF_2026-06-13_S30.md#L15), [SESSION_HANDOFF_2026-06-21_S34.md:15](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/SESSION_HANDOFF_2026-06-21_S34.md#L15), [SESSION_HANDOFF_2026-06-21_S35.md:14](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/SESSION_HANDOFF_2026-06-21_S35.md#L14), [SESSION_HANDOFF_2026-06-21_S35.md:27](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/SESSION_HANDOFF_2026-06-21_S35.md#L27).

Additional qualifications: entry-to-exit waveform features cannot establish pre-entry prediction; shuffled stratified folds are not temporally purged validation; the exporter’s 79.4% OOF result is not a justified live expectation. Sources: [_markets_dipole_chunker_stack.py:17](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/vendored_build_kit/_markets_dipole_chunker_stack.py#L17), [_markets_dipole_kfold.py:102](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/vendored_build_kit/_markets_dipole_kfold.py#L102), [_markets_dipole_export_centroids_v2.py:159](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/vendored_build_kit/_markets_dipole_export_centroids_v2.py#L159).

**Before any revival:** recover exact labels, episode identities, pre-decision features, train-only transformations and temporal splits. Recalculation is required for a new predictive claim, not for allowing the teacher to read the historical idea and its failure.

### K03 — Recover spectral/null-space mathematics with its controls

**Research-method material; simulated findings stay scoped.** The six-column entropy/operator basis, centered SVD, equal-entropy identities, MI axis, estimator/sample dependence and circular-shift controls are not the C15 curriculum. Opposition resembling `−(H_a−H_b)²≈0` can be an equal-marginal bookkeeping identity rather than evidence of dynamic coupling. Rank and eigenvalue magnitude have different dependence on the estimation procedure.

Sources: [CLAUDE_ARCHIVE_OD.md:438](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/CLAUDE_ARCHIVE_OD.md#L438), [CLAUDE_ARCHIVE_OD.md:477](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/CLAUDE_ARCHIVE_OD.md#L477), [CLAUDE_ARCHIVE_OD.md:779](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/CLAUDE_ARCHIVE_OD.md#L779), [operators.py:113](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/odcore/operators.py#L113), [null_extract.py:35](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/odcore/null_extract.py#L35), [coupling_scanner.py:55](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/odcore/coupling_scanner.py#L55).

Root code review confirms a concrete qualification: `CHEM_RESIDUAL` is not orthogonal to `EQ_QUAD` (their unnormalized dot product is 0.23). Its squared projection is an overlapping fixed-axis diagnostic, not an additional independent partition of residual energy. The code separately computes the orthogonal remainder; do not add the chemistry projection to that remainder. [null_extract.py:74](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/odcore/null_extract.py#L74).

The archive’s “markets on the coupling side” inference relies partly on old predictor results and inherits their later corrections. Cross-domain analogy is a research hypothesis, not established market physics. Original simulator claims were read, not independently rerun here. The separate synthetic Gram-matrix/conditioning cautions in [TEACHER_MATERIAL_RECONCILIATION_20260914.md:52](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/kalshi/frankie_boss/TEACHER_MATERIAL_RECONCILIATION_20260914.md#L52) are useful supporting references, not new proof of a defect in C15.

### K04 — Supply exact flow measurement semantics

**Explanatory addition; broad flow mechanisms already exist.** In the historical implementation, balance means signed imbalance zero (buy share 0.5); `mi_flow` is an imbalance-signed difference between half-window MI estimates, without division by elapsed time. Calling it a numerical time derivative would be inaccurate. The sign of `C_signed` is largely assigned by imbalance itself, so sign-only success does not independently validate entropy information. A heuristic conviction is not a calibrated probability.

Source: [info_dipole.py:58](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/odcore/info_dipole.py#L58). Preserve estimator, binning, window and units with every formula. The existing research-only `DEPLOY_VALIDATED=False` status remains unchanged.

### K05 — Qualify the advertised clock-isolation result

**Newly identified methodological correction; recalculation required for the causal claim.** The timing script claims to hold true turns constant, but independently recomputes ZigZag pivots after minute downsampling. It compares different turn populations. The archived medians do not isolate the clock effect or establish the advertised 8–10 bps round-trip advantage.

Sources: [_info_dipole_timing_test.py:67](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/_info_dipole_timing_test.py#L67), [_info_dipole_timing_test_results.json:8](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/_info_dipole_timing_test_results.json#L8), [S36_NETCOST_BACKTEST_FINDINGS.md:146](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/S36_NETCOST_BACKTEST_FINDINGS.md#L146).

A decisive recalculation would match original pivot identities, declare the observation/decision clocks, and account for execution. This correction does not refute the general possibility that faster observation helps.

### K06 — Correct the interpretation of the filter comparison

**Missing qualification.** The harness independently optimizes reversal thresholds and filters for in-sample net. It does not isolate filter quality under identical timing and matched false-positive rates, despite the advertised comparison. Higher precision can coincide with different selectivity or timing.

Sources: [_info_dipole_harness.py:114](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/_info_dipole_harness.py#L114), [_info_dipole_harness_results.json:92](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/_info_dipole_harness_results.json#L92). A new claim needs fixed/shared timing and a predeclared selectivity comparison. The general FILTER/TIMING idea is already in the NG brain and is not counted as new knowledge.

### K07 — Preserve what the old gate and “deploy map” actually do

**Missing operational and validation qualifications.** Removing calls does not flatten an open position: the historical simulator holds until the next surviving opposite call or stream end. The later map selects its winning configuration on reported OOS performance, leaving no further untouched holdout for that selection. Maker economics reuse the same fills with a lower fee; fill probability and adverse selection were not modeled.

Sources: [_info_dipole_regime_gate.py:55](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/_info_dipole_regime_gate.py#L55), [_info_dipole_harness.py:78](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/_info_dipole_harness.py#L78), [_info_dipole_harness.py:128](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/_info_dipole_harness.py#L128), [_info_dipole_gated_swing.py:81](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/_info_dipole_gated_swing.py#L81).

Keep positive cells and negative cells as historical evidence with these limitations. They do not justify restoring the strategy or treating a call filter as a risk-flattening controller.

### K08 — Label retrospective native geometry and runway eligibility correctly

**Specific provenance qualification; the general causality rules already exist.** The native-shape audit uses a full-day quantile, future-centered local maxima, globally ranked refractory selection, mirrored/rescaled trajectories, and cross-day neighbors that may come from later days. The runway audit conditions on retrospectively identified ZigZag legs and survival to the queried age. Those support descriptive research, not automatically a causal entry classifier.

Sources: [ng_dipole_native_shape_audit.py:97](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/ng_dipole_native_shape_audit.py#L97), [ng_dipole_native_shape_audit.py:201](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/ng_dipole_native_shape_audit.py#L201), [ng_dipole_native_shape_audit.py:335](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/ng_dipole_native_shape_audit.py#L335), [ng_dipole_runway_audit.py:157](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/ng_dipole_runway_audit.py#L157), [ng_dipole_runway_audit.py:227](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/ng_dipole_runway_audit.py#L227).

No matching retained output artifact for either named audit was found in this tree. A fresh empirical claim needs reconstructed inputs/results and lawful event eligibility. Historical mirroring is not permission to reintroduce it into the current preserved-evidence path.

### K09 — Bind result artifacts to the code that produced them

**Concrete missing provenance warning.** The retained trailing-backtest JSON contains `ride_stop_*` results, whereas current source emits `price_stop_*` and `dipole_exit_flip`. It cannot substantiate the current dipole-exit variant merely because its basename matches the script. Sources: [_info_dipole_trailing_backtest_results.json:12](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/_info_dipole_trailing_backtest_results.json#L12), [_info_dipole_trailing_backtest.py:238](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/_info_dipole_trailing_backtest.py#L238).

Require a matching source revision, input identity and result schema before quoting a result. No archived outcome was recalculated during this review.

### K10 — Retain adjacent older ideas as proposals, not discoveries

**Lower-priority research leads, with overlap removed.** Earlier handoffs propose lag-one persistence, non-DC spectral peaks, impact/volume proxies, trade-size modes, interarrival variation, cross-venue lags and coefficient trajectories across change boundaries. Generic persistence/absorption is already covered; the specific old feature recipes and their historical rationale are not the C15 fields.

Sources: [HANDOFF_PHASE1_5.md:38](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/HANDOFF_PHASE1_5.md#L38), [HANDOFF_PHASE1_5.md:115](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/HANDOFF_PHASE1_5.md#L115), [HANDOFF_DESKTOP.md:54](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/HANDOFF_DESKTOP.md#L54). Hand-set actor labels and thresholds do not prove participant identity. Keep these as searchable proposal cards pending a precise Dipole question and current-data recalculation. Do not import their old dimensional-reduction architecture by implication.

## Exclusions after deduplication

- General collapse-versus-crossing, FILTER/TIMING, the single-day NG +2.7 percentage-point observation and Simpson/trend warnings already exist in the NG brain. They are not additions.
- Family A’s persistent/fast-collapse runway split, provisional C, failed B-locality rule and scratch-curve warning are **already transitively indexed**: [NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_20260818.md:9](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_20260818.md#L9) points to [FRANKIE_NG_EXHAUSTION_BRAIN_LESSON_PROPOSAL_20260817.md:1](https://github.com/DavisAI1974/Markets/blob/bb28b35eefd3cb2dc602031800ac9b7d3d2d5175/research/FRANKIE_NG_EXHAUSTION_BRAIN_LESSON_PROPOSAL_20260817.md#L1). The parent contains the exact 61D/+60-second definition and reveal medians. A chat paraphrase calling B reliably local is older than the failed holdout result.
- Phase-1/2 D-depth, ancestry, recurrence, POX, causal-clock corrections and geometric contracts are in the existing declared package. Their presence in another handoff is not new knowledge.
- Memory A’s slice-specific no-direction, missing-input, censoring and untested-mirror findings already exist. Do not generalize them into universal market facts or add duplicate lesson cards.
- C15R3’s size-weighted identity survival, capped original-size retention, fill reconciliation and masks are implemented knowledge. Classroom prose could state the weighting more precisely, but this is presentation work, not a missing formula.

## Explicit signal-discovery priority

Greg clarified during this review that discovering a trading signal, including one derived from Dipole, must be an important continuing mission alongside the other work. The retained historical prompt already asks for possible signals, but the current shared run-analysis instruction did not state that priority explicitly. This change adds it to `RUN_ANALYSIS_INSTRUCTION`, which is used both in the newly rendered continuation prompt and the principal session request. It asks for candidate mechanisms, supporting/conflicting evidence, causal availability and the next discriminating calculation; it explicitly permits revisiting a failed idea when its math/data/test was inadequate. It separates scientific validation from predictive/economic performance and does not require a second occurrence as the only route to a scoped scientific conclusion.

The instruction is prospective: it does not claim that Frankie has received it in a production session. It preserves the required cycle sequence and the other research missions. The reviewed catalog is not automatically inserted into the frozen seed.

## Remaining integration work

The user’s requirement is complete shared research access, including superseded ideas and failed tests with their labels, and continued learning from every completed cycle. A useful next implementation is a versioned shared research catalog consumed by the classroom/scientific-review conversation, with source references, claim scope, mathematical definitions, known contradictions and supersession links. Indexed material should have observable retrieval/read receipts. Existing formulas remain versioned deterministic computations; a text seed alone cannot change or educate a mathematical function.

The new scientific-review conversation is still unimplemented. Current novelty review checks cited values and relationships and retains the premise as a hypothesis; it cannot validate a broader mechanism. The requested future reviewer should receive **all** prior observations, lessons, corrections and uncertainty, not only novel findings. It should evaluate scientific coherence and evidence directly. A second independent occurrence may strengthen empirical support, but must not be the only permitted validation route. Scientific acceptance of a scoped mechanism and empirical claims of forecasting/profitability are separate conclusions.

This review does not add a waiting requirement for access to information. Disputed and superseded material can be read immediately as such; acceptance as current mathematical or predictive truth requires an explicit, supported conclusion. The exact shared-teacher design and practical full-context admission remain subsequent work.

## Coverage and limits

All 751 tracked Markdown/text paths were retrieved and keyword-screened at the pinned snapshot, including all 167 handoff/kickoff narrative paths. The handoff selector also covered 20 other blobs, for 187 handoff/kickoff files total. Relevant passages and superseding sections were reviewed; unrelated operational prose was not exhaustively interpreted line by line.

The historical-code review inspected 23 scoped Dipole Python sources, nine raw-text result artifacts, and three spectral dependencies. The root inspected current teacher/classroom wiring, the retained prompt and Memory A, and all 63 currently available paths from the 71-artifact declared baseline. Identical non-handoff document blobs were deduplicated during screening.

Conversation coverage is recorded separately in the coverage artifact: 23 relevant conversations, all returned pages, 445 turns. The app exposes only eight pinned and fifty recent active conversations plus eight archived Codex tasks; the active listing has no older-page enumeration. Transcript reads were limited to relevant accessible material and may themselves be summaries/truncated. No exhaustive claim about all historical ChatGPT/Work/Codex conversations is made. No verified chat-only missing scientific result was established.

The full repository tree was inventoried, not every binary, data row, historical commit or external research archive. Absence judgments are bounded by that coverage. Keywords are discovery aids; source-specific semantic review and supersession checks support the selected entries.

No local filesystem/shell access, ingestion restart, deployment, market rerun, model call or production cycle was performed. This document records source review, not new experimental results.
