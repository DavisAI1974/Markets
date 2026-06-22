# Crypto Trading Platform — Mission

## What this platform is

A crypto trading platform whose signal core is built on Operator Discovery (OD) — a
domain-agnostic method that extracts the governing structure of a system directly from raw
data, with no model assumed in advance. Applied to crypto markets (treated as the "5th
science" alongside physics, biology, chemistry, and geology in the OD research line), OD
turns each trade's raw order-flow and price history into a distinctive 128-dimensional
operator-coefficient signature. The platform's job is to use those signatures to predict
winning trades.

The platform shell already exists and is mature: exchange collectors with durable data
pipelines, a FastAPI backend, a frontend, a paper executor with risk gates, a chunker, a
backtester, and an operator registry. The mission is the signal core that sits inside it.

## The core thesis: predict winners by their distinctive fingerprint

We predict winning trades by their distinctive fingerprint — not by any single indicator,
and not by statistically separating a "win" class from a "lose" class. Every trade leaves a
distinctive fingerprint when the full OD toolkit is run over it, and winning trades have
recognizably different fingerprints from losing ones. The platform's edge is the ability to
extract that fingerprint, as early and as accurately as possible, and act on it.

Extracting these distinctive OD traits from raw market data is a capability no one else in
the world has. That is the moat.

## The fingerprint is the whole toolkit, stacked

The fingerprint is assembled by stacking every tool, each contributing an orthogonal view of
the trade. The tools are complementary, never competing:

- The dipole — the per-bucket 128-dimensional OD operator-coefficient signature.
- The six microstructure features — mean_dipole, dipole_acl1, volume_zscore,
  trade_present_score, trade_recent_2chunk_bps, trade_from_onset_bps.
- refrag — the OD discovery pipeline itself.
- Any other OD tool in the toolkit (lead-lag timing, strength meters, functional families,
  and others as they are validated).

A tool that is weak on its own can still sharpen the combined fingerprint, so we never pit
tools head-to-head; we stack them. The strength of any single tool — for example, how
strongly the dipole alone separates winners from losers — is not the metric. The
distinctiveness of the combined fingerprint is.

## Buckets: every cell is its own world (asset x venue x side)

Markets are not uniform, so we never pool them. Every trade is bucketed by cell, defined as
asset x venue x side, because:

- The same coin behaves differently across venues (Coinbase vs Kraken vs Bybit).
- Different coins behave differently (BTC vs ETH).
- Buy and sell are different regimes.

Within a cell, winners and losers differ in head versus tail pressure — the order-flow and
price pressure at a trade's onset (head) versus its most recent window (tail). That
difference is precisely what makes winners fingerprintable. Each cell gets its own distinctive
coefficients; we validate and deploy per cell. Partial coverage — a signal that works on some
cells and not others — is a success on the cells where it works, not a failure.

## Early and accurate

The fingerprint must be computed as early as possible — ideally pre-entry, from minimal data —
and as accurately as possible, so a winner can be recognized in time to act on it. The heavy
part of the fingerprint (the 128-dimensional OD coefficient) is computed live and memoized,
and the platform is built to run on scalable cloud compute, so accuracy is never traded away
for speed. A small added latency at entry is acceptable; a degraded fingerprint is not.

## Discipline: how we keep a real edge instead of fooling ourselves

- Distinctiveness, not separation. We do not balance classes, average coefficients into
  win/lose centroids, or grade by separation AUC. Those operations blur the very
  distinctiveness that is the signal.
- Zero synthetic trading data. Signals, backtests, and any claimed edge are computed only from
  real exchange data.
- Honest validation. No system delivers "100% winners," and max-bank sizing destroys a real
  edge on the first losing streak. We prove an edge with walk-forward validation and a
  tautology-killing null, then size from measured OD confidence with circuit breakers.
- OD-native sizing, not textbook Kelly.

## How it runs (architecture in brief)

Real-time exchange collectors feed a live encoder that computes each candidate trade's
fingerprint (OD coefficients plus the microstructure features). A per-cell predictor scores
that fingerprint against the cell's distinctive winning profile. An adaptive selector deploys
the winning approach per source. OD-native sizing with risk gates and circuit breakers governs
position size, and the paper/live executor places the trade. The shell is mature; the work is
the OD signal core and the live fingerprint encoder.

## Where we are

- The OD signal core is built into the platform, including a validated live OD-coefficient
  computation that runs the discovery pipeline per candidate trade and is memoized for speed.
- Per-cell distinctive coefficients have been discovered for all twelve cells (roughly 1,900
  distinctive signatures), with every cell carrying both winning and losing examples.
- The live fingerprint encoder is being assembled — recovering and porting the feature
  computations into the live path — so the platform can fingerprint candidate trades and
  predict winners per cell, in real time.

## Scope

This is the crypto trading platform only. The separate quote / market-making service is out of
scope. The canonical implementation plan is BUILD_PLAN.md; the operating context and session
history are in CLAUDE.md and the SESSION_HANDOFF files.
