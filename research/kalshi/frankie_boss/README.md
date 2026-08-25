# Frankie boss / Sol replacement seam

This package is an additive from-scratch boss-model layer around Frankie's existing BLD-1 boundary.
It does not replace or edit `spawn.py`, S135, the provider adapter, the 1,940-path/46-block capability
surface, or ReFRAG governance.

## Checkpoint status

The QSV-registry and internal-head-to-BLD-1 continuation is complete. The executable checkpoint,
supplied source artifacts, ReFRAG governance bundle, tests, and provenance are committed on
`codex/frankie-boss-sol-replacement-20260824`. This is a completed seam checkpoint, not a claim that
the entire Sol replacement has been trained, evaluated, promoted, or launched.

The implementation commit is `a31307729c00aa6f2996b711ab2fcf65c2ef2e3f` in the local history and
`fd7d9a00ac2728660de674a06b6ce55e569311f0` in the connector-published GitHub history. The trees and
messages are identical; the commit identities differ because the GitHub connector recreated the
previously local-only commit chain with new commit metadata.

## QSV / Operator Discovery input

ReFRAG owns `research.refrag.qsv_registry.QSV_FEATURE_REGISTRY`. Its order is generated from the
existing market-shaped `MarketChunkEncoder` output contract: the 14 emitted return,
microstructure/flow, volatility/range and spectral summary features, followed by that encoder's
configured normalized FFT-magnitude slots. The separate 128-D operator coefficients and currently
un-emitted Phase 1.5 attributes are not this vector. The trunk derives `qsv_dim` from the registry and
rejects drift.

QSV is dormant by default through `use_qsv=False`. Enabling it creates the separate projection path;
`qsv_mask` controls per-step availability, including non-finite unavailable payloads, and
`FieldEncoder.ablate_qsv()` makes that projection exactly inert.

The trunk contains one shared `TemporalGraphBranch`. There are not three graph models.

## Internal heads to BLD-1

Only these learned quantities have deliberately specified public semantics:

| Internal quantity | BLD-1 destination | Semantics |
|---|---|---|
| `session_net_usd` | `guessed_net_usd` | Prior-close-to-close session move, including the overnight gap |
| `overnight_gap_usd` | `overnight_gap_usd` | Prior close to session-open move |
| `session_path_p50_curve` | `path_p50_curve` | Endogenous `[et_time, cumulative_from_open_usd]` P50 points; terminal value equals net less gap |
| `confidence_label` | `confidence` | Already-governed BLD-1 label: `low`, `med`, or `high` |

`calibrated_call_probability`, `p_up`, `size`, `regime_logits`, `contradiction`, `sigma`,
`evidence_scores`, and any future learned quantity remain internal. In particular, no numeric
confidence-to-label thresholds are invented here. `InternalBLD1Heads.internal_only` retains these
values for diagnostics and training; the typed projector never considers them when building BLD-1.

## Verification checkpoint

- The untouched supplied source set reproduced `101 passed`.
- The bounded implementation and preservation suite produced `160 passed`.
- Both lanes and all five roles retained the same 1,940 addressable paths and 46 blocks.
- QSV is dormant by default; masked non-finite payloads are exactly absent, while present non-finite
  payloads fail closed.
- Forecast-backed ABSTAIN preserves the valid net, gap, and curve; malformed or unavailable forecasts
  use the complete zero safety abstention.
- A fresh-context adversarial review and the agent-skills five-axis review found no remaining
  Critical or Required issue.

The next-chat authority is
`research/kalshi/FRANKIE_BOSS_SOL_REPLACEMENT_HANDOFF_20260824.md`.
