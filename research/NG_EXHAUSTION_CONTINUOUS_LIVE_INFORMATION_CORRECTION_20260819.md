# NG Exhaustion Recovery — Continuous Live Information Correction — 2026-08-19

Status: **ACTIVE AUTHORITATIVE INFORMATION RULE FOR THE D0-D5 RECOVERY PROGRAM.**

The recovery model is not restricted to frozen event labels. At every causal checkpoint it may observe the market information that would actually be visible by that second.

## Continuous observations

At every D0 ROOT_AGE checkpoint, every D1-D5 PRIOR checkpoint, and every D1-D5 post-birth H checkpoint, the active `FULL_CAUSAL` view includes the then-observable progression of:

- raw price direction (up/down) and cumulative displacement;
- short-horizon price velocity, range and path evolution;
- contemporaneous classified buy-versus-sell flow;
- rolling flow imbalance / dipole direction and change;
- book imbalance and its change through time;
- causal clock/session position;
- all predecessor/root event information whose own causal availability time has already passed.

These observations do not require the future target polarity, target family, final depth, or final chain type to be known.

## Label versus observation

A future target label is not the same thing as an observed directional market state.

The model must **not** receive a retrospective frozen target-polarity label before that label is causally available. But it **must** still see the actual price/flow/book direction that is unfolding live, and it may infer whatever direction or structure it can from those observations.

Unknown target polarity therefore never makes a PRIOR checkpoint fail or become ineligible.

## Primary prediction questions

The primary recovery questions remain:

1. does the chain stop or continue / is the next stage born;
2. what eventual depth does the chain reach;
3. what P/O/S/X structural state/family is the chain becoming.

Target polarity is not a fourth required prediction target. SAME/FLIP remains preserved secondary context/annotation for later behavior and strategy work.

## Causal implementation

Raw direction/flow/book features are formed only from records timestamped no later than the active checkpoint. The V3 implementation compresses the authoritative raw tape to causal one-second state, matching the detector and H-clock temporal resolution while preserving the needed direction, flow and book information.

No future interpolation, future threshold, future target label, or later lineage membership may enter an earlier checkpoint.

## Supersession

Any recovery result that depended on hiding live direction/flow/book until target confirmation, or that treated SAME/FLIP as part of the required primary type prediction, is comparison evidence only and is superseded for final synthesis by the V3 continuous-live-state pass.

No frozen detector, canonical evidence, Phase-1/Phase-2 artifact, runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or SSOS play is modified.

Policy: `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.
