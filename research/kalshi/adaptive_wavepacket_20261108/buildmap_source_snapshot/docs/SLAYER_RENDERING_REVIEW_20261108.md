# Slayer architectural review for Adaptive Locality — 2026-11-08

Source examined: https://github.com/janearc/slayer (public main branch, README.md, OPERATION.md, PACKAGES.md, doc/fast.md, burning-trousers/README.md, LICENSE.txt, render/smokecache/cache.go, render/frame/frame.go). Slayer is a Go ray tracer and photographic rendering toolkit, with an optional macOS Metal implementation. Its README labels it pre-release. The repository license file is Apache License 2.0. We did not copy or vendor its code.

## Decision

**Adopt the architectural patterns; do not embed the renderer in Frankie.**

| Observed Slayer design | Locality/Frankie implication | Implementation in isolated branch |
|---|---|---|
| Raw linear-light frame separate from color development | Separate verified scientific state from presentation, avoid recomputation for appearance changes | `adaptive_locality/visualization.py` emits content-addressed raw JSON and independently creates standalone HTML |
| Deterministic sampling and 64-pixel replay via Fermat | Select reproducible calculation/point probes from an immutable manifest | `replay_probes` uses frame identity and deterministic sample selection; not proof of bitwise source calculation equivalence |
| Cache key tied to executable, inputs, sampling and sensor | Cache grouping/reuse only under full source, input, metric, policy and direction identity | Pattern recorded; a real cache is NOT implemented, and no calculation is suppressed |
| Atomic publication of complete render artifacts | Do not expose torn checkpoint or report outputs | Existing local no-clobber checkpoints, read-only viewer output; broader transactional multi-output bundling remains open |
| Independent physics/regression/mutation harness | Validate both mathematical results and viewer against distinct fixtures | Standalone visualization test suite; independent scientific market acceptance remains open |
| Wavefront grouping of rays by task in future roadmap | Consider batch/queue grouping by work type without changing causal event identity | Shadow ready-group queue already exists, no production connection |
| CPU reference for macOS Metal | Keep CPU as scientific reference; GPU optional after reproducible equivalence and cost benefit | No GPU implementation planned in current phase |
| Procedural geometry and hexagonal sphere tiles | Potential inspiration for future visual spatial packing; not a direct fit to high-dimensional market-state metrics | No dependency adopted; dimension reduction and metric geometry still require separate scientific justification |

## What was actually built

- `adaptive_locality/visualization.py`: verifies every input event against its shadow decision and metric, prioritizes centers when selecting display-only samples, computes finite-window family diagnostics, creates an immutable raw frame digest, and develops an offline HTML report independently.
- `adaptive_locality/review_cli.py`: opt-in CLI that accepts the same JSON input format as the existing shadow CLI, produces an offline HTML report, and optionally writes deterministic replay-probe identities.
- `tests/test_adaptive_locality_visualization.py`: checks stable display identity, zero scientific job elimination, wrong/stale evidence rejection, HTML injection escaping, replay determinism, display-only sampling, no-clobber output, and CLI contract.
- No modifications to `public/app.js`, `src/server.js`, BuildMap scanner, Frankie source, AWS, production pipeline or source data.

## Deliberate limitations

This is a **BuildMap-adjacent proof-of-concept viewer**, not a feature wired into the existing BuildMap application. It is separate by design and intentionally uses only standard-library Python + self-contained HTML/JS.

The two-dimensional plot is a projection, **not** the full metric-space geometry or proof of an accurate grouping. The Cauchy window check is a finite diagnostic only. Stable hashes establish repeatable representation and input consistency, not correctness or scientific equivalence. Decision and cache identity is a necessary condition, never on its own authorization to eliminate calculations.

The renderer's color choices are for legibility, not market science. Do not label visually overlapping points as causally equivalent, collapse family identities, or silently drop dissimilar behavior.

## How to try it locally without connecting services

The command below requires a local checkout of the isolated branch and a user-created JSON input with fields `manifest`, `metric`, `config`, `events`. At least two distinct numeric features must be in `metric.features`. Run from the repository root:

```bash
python -m unittest discover -s tests -p 'test_adaptive_locality*.py' -v
python -m adaptive_locality.review_cli my-shadow-input.json \
  --x spread --y pressure \
  --output offline-locality.html \
  --probes offline-locality-probes.json
```

Open `offline-locality.html` locally. No network requests are made by the viewer, and the exporter refuses to overwrite an existing output. Inputs and output paths must differ. Generated HTML and probes are **local research artifacts**, not verified market or BuildMap receipts.

## Priorities for the next chat

1. Finish durable identity-aware execution/snapshot recovery and high-cardinality bounded metric index **in isolation**.
2. Add raw-frame cache keyed by all relevant code, data, metric, projection, axis and display policy contracts; require independent correctness/retention tests before using it.
3. Expand property-based, replay, differential, concurrency and scientific invariant checks.
4. If the user elects to integrate BuildMap later, use a strictly read-only, provenance-labeled import behind a feature flag. Do not merge this branch, modify BuildMap default experience, run Frankie, or deploy AWS without approval.

For Slayer details, see its own docs at https://github.com/janearc/slayer/blob/main/OPERATION.md and https://github.com/janearc/slayer/blob/main/PACKAGES.md. License: https://github.com/janearc/slayer/blob/main/LICENSE.txt.
