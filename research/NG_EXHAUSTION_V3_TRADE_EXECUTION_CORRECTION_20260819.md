# NG Exhaustion V3 Trade Execution Correction — 2026-08-19

Status: **AUTHORITATIVE TRADE-RESEARCH CORRECTION FOR THE ACTIVE V3 RECOVERY LINE. PROPOSAL/HISTORICAL RESEARCH ONLY.**

## Why this correction exists

The earlier D0 trade prototype capped an open trade at the next canonical exhaustion `t0`. That next event is known only retrospectively at the signal timestamp and therefore cannot define a live-executable exit.

The active V3 trade program supersedes that execution convention without deleting the historical prototype or its outputs.

## Signal contract

Each Logistic / ExtraTrees / KNN lane must independently reproduce its own validated V3 continuation/terminality signal. There is no model vote, median probability, ensemble gate, or cross-model probability aggregation.

- D0: reproduce the earliest independently validated `D0_TERMINALITY` root signal.
- D1-D3: reproduce the earliest independently validated `CONTINUATION` signal, PRIOR first and H+1..H+5 only if that model fails PRIOR.
- A model with no independently validated signal has no trade lane.

## Direction contract

The trade direction is not the future target polarity and cannot use the realized target polarity.

Discovery may compare only directions available at the causal signal timestamp:

- with / against the last confirmed predecessor polarity;
- with / against observed live five-second price direction;
- with / against observed live twenty-second signed aggressor-flow direction.

These are ordinary causal market observations. A missing/flat direction produces no trade for that candidate/row; it does not fail the underlying prediction.

## Execution contract

- Entry = first authoritative raw trade at or after the causal signal, with a maximum five-second entry delay.
- Exit = first authoritative raw trade at or after a **fixed predeclared hold horizon**, with a maximum ten-second exit delay.
- Candidate horizons = 5, 10, 20, 30, 60, 120, 300 seconds.
- No next-exhaustion, next-chain-event, realized endpoint, future target birth, or other future structural event may cap or choose the exit.
- Costs are reported at 0.5, 1.0 and 2.0 ticks.
- MFE, MAE, path range, path efficiency and positive-week stability are preserved.

## Candidate selection and OOT

Discovery tune may select among predeclared probability-quantile thresholds, directions and fixed horizons. The selected candidate is then frozen before validation, untouched confirmation and held evaluation.

The trade result is model-specific. Failed candidates, mixed validation, low support and held contradictions remain evidence and are not deleted.

## PRIOR versus H

A validated PRIOR signal is directly researchable as a causal live-entry timestamp because it is defined from information already available before target birth.

A post-birth H signal remains historical timing/economics research until the exact upstream causal **event-mark/discovery timestamp** is proven. Frozen `t0` is not automatically assumed to be the timestamp at which a live system knew the event existed.

Raw price direction, flow/dipole and book state remain continuously observable regardless of whether the event-specific label has been marked.

## Preservation

This correction does not mutate the frozen detector, canonical rows, Phase 1, Phase 2, runway clock, permanent Frankie, Frankie 1, `spawn.py`, or the SSOS play.

Standing policy: `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.
