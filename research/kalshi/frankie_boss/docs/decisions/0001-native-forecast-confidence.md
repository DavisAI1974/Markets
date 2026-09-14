# ADR-0001: Add a native path-first forecast and governed confidence bundle

## Status

Proposed, 2026-09-14. Design only; not implementation or production approval.

## Context

The current generic TypedHeads do not produce Frankie's four required BLD-1
forecast quantities. S121 requires endogenous timestamps and a real full-session
path, and makes trade disposition independent of that forecast. B0/B1 controls
and complete raw-evidence preservation must remain intact.

## Decision

Add an opt-in gap, time-selector and time-query path bundle after the same native
B1 representation. Derive daily net from gap plus the path terminal. Keep the
existing projector and twelve public fields unchanged.

Use pointwise conditional medians for gap/path, without incorrectly claiming
that their preopen sum is a marginal median net. Fit timing before path values;
use native-generated times and independent audit queries to avoid future-extremum
label leakage and easy-knot-only evaluation.

Define confidence as the calibrated probability of a joint, explicitly bounded
gap/net/path-error event. Proposed public bands are 0.60/0.80; unknown calibration
has an explicit low/null sentinel. Bind the policy, model and calibration artifacts
to the exact forward/retry identity.

The owner's research notes add mandatory timestamp-resolvability evidence before
timing labels, internal ordered quantiles with per-horizon coverage curves,
count-reconciled bins, a paired forecast-only baseline for confidence's incremental
information, explicit experimental grids/seeds and support exit/re-entry logs.
Correlation is a diagnostic, not an independence certificate; timestamp
interarrival is not itself jitter. No prior research result is claimed reproduced.

## Alternatives considered

- Relabel p_up, size or sigma: rejected; their semantics do not match BLD-1.
- Predict daily net then interpolate a path: rejected by S121.
- Output a fixed clock grid: rejected by S121.
- Independently predict three medians and force reconciliation: rejected because
  median additivity is not generally valid.
- Confidence as profitable-trade probability: rejected; disposition/risk are
  separate capabilities and no execution model is established here.
- Let Granite fill missing native forecasts: rejected; shadow must stay shadow.
- Invent production error/support thresholds now: rejected; units and empirical
  validation must be bound before a production policy can become eligible.

## Consequences

The missing output meanings and candidate architecture are specified, but no
weights or calibration evidence are created. The staged training protocol costs
data and must demonstrate adequate endogenous-time coverage. USD tolerances and
support/drift acceptance limits remain required production configuration.

See ../../SPEC-native-forecast-confidence.md for contract, tests and boundaries.
