# S125 gas audit status

The independent recent-year gas-generation vs Henry Hub event audit is complete.

Window: 2025-08-01 through 2026-07-31.
Physical coverage: 365 calendar days.
Henry Hub event rows: 246.
Method: event-level only; no pooled R-squared, correlation, regression, seasonal average, or annual average is used as the verdict.

Reproducer: `research/kalshi/burn_hh_12m_event_ledger.py`
Workflow: `.github/workflows/burn_hh_12m_s125.yml`
Successful build commit: `a7d6d04b27f6bdf79b3d96f1bcaaa124c056a05f`
Successful workflow run: `31755161335`
Artifact: `s125-burn-hh-12m-independent-ledger` (ID 9202452919)

Key interpretation: burn is conditional state/context evidence, not a fixed directional coefficient. Shoulder-season flat response, renewable substitution, winter sign inversion, and summer decoupling all occur on specific dated events. The older June 29 example did not reproduce under the raw EIA US48 generation definition and remains unverified pending recovery of its exact burn definition/window.
