# Frankie boss / Sol replacement seam

This package is an additive from-scratch boss-model layer around Frankie's existing BLD-1 boundary.
It does not replace or edit `spawn.py`, S135, the provider adapter, the 1,940-path/46-block capability
surface, or ReFRAG governance.

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
