# Frankie boss / Sol replacement — next-chat handoff

Date: 2026-08-24

Repository: `DavisAI1974/Markets`

Branch: `codex/frankie-boss-sol-replacement-20260824`

## Governing status

Continue the from-scratch Frankie boss / Sol-replacement build around Frankie's existing seam.
The causal-clock correction, real BLD-1 contract, named QSV registry, exact QSV ablation, and explicit
four-field BLD-1 projection are complete and must not be reopened without a failing test or a new
deliberate contract decision.

This checkpoint does **not** claim that the complete Sol replacement has been trained, evaluated,
promoted, or launched. The next chat must select the next bounded implementation tranche from the
actual remaining architecture after reading the sources below.

## Mandatory first actions

1. Invoke the release 0.6.7 agent-skills lifecycle. At minimum use context engineering, planning/task
   breakdown, Git workflow, API/interface design, incremental implementation, test-driven development,
   documentation/ADRs, and a bounded code-quality review. Use debugging only for an observed failure.
2. Verify the remote branch HEAD and inspect the worktree before modifying anything.
3. Read this handoff, `tasks/plan.md`, `tasks/todo.md`,
   `research/kalshi/frankie_boss/README.md`, `research/refrag/README.md`, and the supplied provenance
   README.
4. Read all governing handoffs and architecture sources listed below.
5. Write the next bounded plan before code. Keep the change additive and test-first.

## Non-negotiable boundaries

- Frankie's existing core and provider seam do not change.
- All 1,940 capability paths and 46 blocks remain wired and addressable in both lanes and all five
  roles. Unwanted capabilities may be dormant; never delete or hand-curate them away.
- ReFRAG supplies operator registry/governance. Do not duplicate that machinery in Frankie.
- QSV stays optional, masked, dormant by default, and exactly ablatable.
- `qsv_dim` is always `len(QSV_FEATURE_REGISTRY)`; do not hardcode the observed default width.
- There is exactly one shared temporal graph branch, not three graph models.
- Only deliberately mapped quantities cross the BLD-1 boundary. New heads remain internal until their
  destination, units, chronology, and semantics are explicitly specified and tested.
- Nova remains a separate project/service. Do not merge its identity or source tree into Frankie.
- Brain-guided, gated-delta, linear-attention, and paper-derived mechanisms are research candidates,
  not assumed requirements. Adopt only through controlled experiments and license-compatible code.
- Persist supplied artifacts byte-for-byte. Do not normalize, rename, delete, or curate the raw
  checkpoint/provenance bundle.

## Completed causal-clock seam

The Databento fields have these fixed meanings:

| Source field | Internal field | Meaning |
|---|---|---|
| `ts_recv_ns` | `ingest_time` | Causal availability time |
| `ts_event_ns` | `event_time` | Exchange event time |
| `ts_in_delta_ns` | provenance only | Transport/latency evidence, never the causal clock |

Do not reinterpret event time as availability time. Restatements with an old event time and future
receive time remain invisible until receive time.

## Completed QSV registry seam

Authority flows in one direction:

`markets_adapter.py::MARKET_FEATURE_SPEC` and
`MarketChunkEncoder.feature_registry` ->
`research.refrag.qsv_registry.QSV_FEATURE_REGISTRY` ->
`research.kalshi.frankie_boss.trunk.TrunkConfig.qsv_dim`.

The exact named prefix is:

`ret_mean`, `ret_std`, `ret_skew`, `ret_kurt`, `autocorr_lag1`, `mean_dipole`,
`mean_ofi`, `volume_zscore`, `realized_vol`, `range_atr`, `spectral_energy`,
`spectral_entropy`, `peak_frequency`, `spectral_centroid`.

The remaining registry entries are generated `fft_magnitude_{i}` slots for the encoder's configured
remaining positions. The current default derives 64 total entries, but that number is not a trunk
contract. The separate 128-D operator coefficients and un-emitted Phase 1.5 `MarketFeatures` fields
are not this vector.

Masking rules:

- Absent/masked QSV contributes exactly zero, including the projection bias.
- Masked NaN/Inf is exactly equivalent to absence.
- Present NaN/Inf fails closed.
- `FieldEncoder.ablate_qsv()` makes the whole stream exactly inert and does not require a payload.

## Completed internal-head to BLD-1 seam

Frankie's authoritative S121-compatible output remains the real 12-field BLD-1 contract. Only these
learned values are projected:

| Internal head | BLD-1 field | Public semantics |
|---|---|---|
| `session_net_usd` | `guessed_net_usd` | Prior-close-to-close session move, including gap |
| `overnight_gap_usd` | `overnight_gap_usd` | Prior close to session-open move |
| `session_path_p50_curve` | `path_p50_curve` | Endogenous `[et_time, cumulative_from_open_usd]` P50 points |
| `confidence_label` | `confidence` | Existing BLD label: `low`, `med`, or `high` |

The curve is chronological, has the authoritative endpoints, and its terminal cumulative-from-open
value equals net less gap. Exact-linear A86-style curves are rejected.

`calibrated_call_probability`, `p_up`, `size`, regime logits, contradiction, sigma, evidence
scores, and all other learned values remain immutable internal diagnostics. No numeric confidence
threshold was invented.

CALL/ABSTAIN disposition is independent of the valid market forecast. A forecast-backed ABSTAIN
preserves net, gap, curve, and confidence. Malformed or unavailable forecast heads produce the
complete zero safety abstention.

## Capability and seam preservation evidence

Both lanes and all five roles were verified against the same 1,940-path/46-block registry surface.
The following frozen files were unchanged by the QSV/BLD continuation:

| Frozen file | SHA-256 |
|---|---|
| `research/kalshi/frankie_full_stack_runtime_adapter_20260824.py` | `1b0d3d1036d201cb9e8977303124fd31b8d28f08e7f9fdfb0695540b14bb857c` |
| `research/kalshi/agent_frankie.py` | `a748ed2c0861f1bf8da1affbe0d8b9b0d92de9705b0d468c78e55468c06e4ea3` |
| `research/kalshi/spawn.py` | `f2ae5287b24b2772a75e1c1674f0f7df590b93d2cbb773662ef30210bce78a54` |

Do not change those files merely to connect the boss package. Build additively around their existing
interfaces.

## Persisted artifacts

- Executable package: `research/kalshi/frankie_boss/`.
- Raw supplied checkpoint: `research/kalshi/frankie_boss/provenance/supplied_checkpoint/`.
- ReFRAG source/governance: `research/refrag/`.
- ReFRAG archive SHA-256:
  `bc2df161ee55c3fe3e65e2071ef2ba87d005d46b1a16fe550c341630d121a26a`.
- The raw checkpoint contains the supplied code/test variants and 28 chronological screenshots.
- The ReFRAG bundle contains 22 valid manifests, the original ZIP, architecture DOCX/PDF sources,
  and Nucleus source markdown.

## Verification record

- Untouched supplied checkpoint: `101 passed`.
- Focused final seam suite: `74 passed`.
- Bounded implementation/preservation suite: `160 passed in 4.37s`.
- Registry runtime check: current derived length 64; first entries `ret_mean`, `ret_std`,
  `ret_skew`; final entries `fft_magnitude_47`, `fft_magnitude_48`, `fft_magnitude_49`.
- Exactly one `TemporalGraphBranch` instance.
- Both capability-preservation tests passed at 1,940 paths and 46 blocks.
- `compileall` passed.
- All 22 manifests parsed and the ReFRAG ZIP passed `testzip`.
- Source secret scan passed.
- Fresh-context adversarial review reported no Critical or Required blocker.

The documentation-closeout shell did not retain the earlier Python test environment: bare `pytest`
and the active Python lacked pytest/torch. That is an environment-path fact, not a failed regression.
No executable code changed in the closeout commit. Recreate or select an environment with pytest and
torch before rerunning the bounded suite.

## Publication record

- Local implementation commit: `a31307729c00aa6f2996b711ab2fcf65c2ef2e3f`.
- GitHub implementation commit: `fd7d9a00ac2728660de674a06b6ce55e569311f0`.
- Final implementation tree: `c101ae305c4cdfe59a484cc1c349595ce0ca7e7a`.
- Implementation comparison from `a7dd99e77216768fec6132eed0eaaaeae20b0355`: 31 commits ahead,
  zero behind. The documentation commit containing this handoff is its direct successor, so the
  published branch is 32 commits ahead after closeout.

Direct HTTPS Git authentication was unavailable in the work environment. The selected GitHub
connector recreated the 31 local-only commits in order, verified every created tree against the local
tree SHA, and then created the branch. Commit SHAs differ because connector-generated commit metadata
differ; file blobs, trees, order, and messages were preserved. For later publications, do not squash
or force-update this history silently.

## Required source reading

### Markets causal clock

- `CHATGPT_HANDOFF_NG_EXHAUSTION_CLOCK_COMPLETE_20260817.md`
- `CHATGPT_HANDOFF_NG_EXHAUSTION_V3_MONITOR_V4_NEXT_20260820.md`
- `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py`
- `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`

### Frankie BLD-1

- `CHATGPT_HANDOFF_S117_AGENT_FRANKIE.md`
- `CHATGPT_KICKOFF_S118_TAKEOVER.md`
- `CHATGPT_KICKOFF_S119_MCP_FRANKIE.md`
- `CHATGPT_KICKOFF_S120_GPT56_CANARY_TAKEOVER.md`
- `research/kalshi/frankie_s118_redo.py`
- `research/kalshi/frankie_s121_curve_restore.py`
- `research/kalshi/forecasts/c2c018_s120_compact_canary/grp18_B_20260427.json`

### ReFRAG and OD in Markets

- `HANDOFF_DESKTOP.md`
- `BUILD_PLAN.md`
- `CLEANUP_RUNBOOK.md`
- `CLAUDE_ARCHIVE_OD.md`
- `HANDOFF_PHASE1_5.md`
- `OPTION_E_PRODUCT_SPEC.md`
- `markets_adapter.py`
- `vendored_build_kit/_markets_algebraic_dipole.py`
- `vendored_build_kit/_markets_dipole_chunker_stack.py`
- `vendored_build_kit/_markets_dipole_separation.py`
- `vendored_build_kit/_markets_dipole_kfold.py`
- `vendored_build_kit/_markets_dipole_export_centroids.py`
- `_run_onset_coeffs.py`

### Agent-skills lifecycle

Use addyosmani/agent-skills release `0.6.7` specifically. Read its `README.md`,
`docs/adoption-guide.md`, `docs/codex-setup.md`, `AGENTS.md`, `skills/`, `commands/`, and
`references/`. Do not substitute current main or a newer release silently.

### External research boundaries

- `DavisAI1974/evolution` main is the Nova project. Read its governing docs and implementation, but
  keep it separate from Frankie.
- `DavisAI1974/Basic_equations` main is the earlier equation/dipole research source. It does not
  define an authoritative fixed-width QSV vector.
- `DavisAI1974/Quantum-Signal-Validator` master is a signal-validation application, not the QSV
  registry authority.
- Read `pkuxmq/Brain-guided_LLM`, its linked paper, `NVlabs/GatedDeltaNet-2`,
  `fla-org/flash-linear-attention`, and arXiv `2506.10943` only as controlled research inputs.
  Verify licenses before copying implementation; prefer a clean-room or compatible primitive.
- `DavisAI1974/operator_hilbert_seq` previously returned 404. Do not depend on it until access is
  restored.

## Next bounded work

The next chat should not guess that the boss is production-ready. After the mandatory reading, inspect
the current package, architecture artifacts, and tests to identify the next missing executable seam.
Record that choice in `tasks/plan.md` before implementation.

Likely categories to evaluate include the actual training/data path, governed experiment execution,
calibration/version promotion, and additive runtime integration, but none is automatically authorized
as the next slice merely because it appears in this list. Keep experimental teacher mechanisms behind
their required control arms and retain negative/KILL results.

For every next slice:

1. Define the typed boundary and authority.
2. Add failing behavior tests.
3. Implement the smallest additive path.
4. Run focused tests plus the capability/seam preservation checks.
5. Perform a fresh-context adversarial review and bounded five-axis review.
6. Update this handoff and lifecycle docs.
7. Commit atomically and verify the remote branch through GitHub.

No production launch, model promotion, or destructive cleanup is authorized by this handoff alone.
