# NG Exhaustion Recovery — Polarity Is Not a Primary Target — 2026-08-19

Status: **ACTIVE CORRECTION FOR THE D0-D5 FULL-CAUSAL RECOVERY PASS.**

## User-authorized clarification

The recovery program is not attempting to predict target polarity as one of its primary questions.

Therefore:

- unknown future target polarity must never make a PRIOR checkpoint ineligible;
- unknown future target polarity must never make a CONTINUATION or EVENTUAL_DEPTH PRIOR fail;
- the primary `CHAIN_TYPE_FAMILY` target is the frozen structural P/O/S/X state/family only;
- SAME/FLIP transition orientation is preserved as a secondary annotation and later context/strategy variable, not part of the primary chain-type prediction label;
- a model is not penalized in the primary recovery because SAME/FLIP cannot yet be known or predicted.

## Causal information rule remains unchanged

This correction does **not** prohibit polarity as information once polarity is genuinely known.

- predecessor/root polarity may be used at any checkpoint where it is already causal;
- after a newborn target is causally confirmed, its then-known polarity may enter FULL_CAUSAL as a feature for unresolved continuation/depth/state-family questions;
- before target confirmation, target polarity is not supplied as a feature;
- raw market price remains available causally and does not require target polarity to exist as information.

## Structural label split

The frozen pairing/grouping grammar remains preserved in full for provenance:

- structural state: P/O/S/X;
- transition orientation: SAME/FLIP.

For this recovery pass they are separated:

- **primary prediction target:** P/O/S/X state/family;
- **secondary annotation:** SAME/FLIP;
- **legacy combined token:** `state|transition` may remain in durable historical evidence but is not the authoritative primary target.

This does not delete or rewrite prior pairing/grouping findings. It only prevents a polarity-bearing combined label from redefining the present recovery question.

## PRIOR eligibility

PRIOR eligibility depends on the causal availability of the predecessor/root information needed to form the checkpoint and on the checkpoint remaining strictly before target `t0`.

It does not depend on knowing the target polarity, target state, target family, final depth, final duration, or any other future target fact.

Policy: `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.

No protected artifact or permanent Frankie brain is modified by this correction.
