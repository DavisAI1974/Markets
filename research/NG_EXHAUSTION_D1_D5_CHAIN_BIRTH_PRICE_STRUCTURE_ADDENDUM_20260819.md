# NG Exhaustion D1-D5 Chain-Birth Price-Structure Addendum — 2026-08-19

Status: **AUTHORITATIVE ADDENDUM TO THE D1-D5 CHAIN-BIRTH PREDICTABILITY PROTOCOL. PRIOR REMAINS PRIMARY.**

## Purpose

The chain-birth timing study must use the causal price structure that accumulates as each individual exhaustion occurrence ages through the active H clock.

Price structure is not a yes/no gate and must not be collapsed across multiple occurrences in a chain.

## Per-occurrence rule

Every predecessor exhaustion occurrence required by a D-stage birth rule carries its own distinct causal price path.

Examples:

- D1 birth candidate: one predecessor occurrence -> one price path;
- D2 birth candidate: two predecessor occurrences -> two separate price paths;
- D3 birth candidate: three separate price paths;
- D4 birth candidate: four separate price paths;
- D5 birth candidate: five separate price paths.

The paths remain ordered by chain occurrence. They may be concatenated for modeling, but they may not be pooled, averaged, or reduced to a single generic `price_structure_available` flag.

## One-second causal path

For an occurrence with frozen detector confirmation `c`, define the causal baseline price as the last authoritative NG trade known at or before `c`.

For every integer second `s = 1..H`, the price at second `s` is the last authoritative NG trade known at or before `c+s`.

The occurrence's active H input is therefore the ordered path:

`PRICE_PATH(H) = [P(c+1), P(c+2), ..., P(c+H)]`

represented relative to the occurrence's causal baseline and aligned to its polarity.

No future interpolation is allowed. If no new trade occurs during a second, the last already-known trade price is carried forward. No price after `c+H` may enter the H snapshot.

The implementation stores one signed cumulative price value per elapsed second. Adjacent differences recover the one-second changes, so duplicating both cumulative and delta paths is unnecessary.

## Dense H semantics

The active H grid remains:

`1,2,3,4,5,10,15,20,25,30,35,...,3600`

At each H, the model sees **all one-second price structure accumulated from second 1 through H** for every required predecessor occurrence.

Thus:

- H=1 sees second 1 only;
- H=2 sees seconds 1 and 2;
- H=5 sees seconds 1 through 5;
- H=15 sees seconds 1 through 15;
- H=25 sees seconds 1 through 25;
- and so on.

A later H is an extension of the earlier causal path, never a replacement summary.

## PRIOR remains primary

This addendum does not change the search hierarchy.

For every D1-D5 stage/rule/subfamily:

1. exhaust PRIOR H values in ascending order using the per-occurrence causal price paths available by that H;
2. preserve the earliest validated PRIOR birth signal;
3. only if PRIOR fails, use the target detector-relative fallback ladder `+0,+1,+2,+3,+4,+5,+10,+15,+20,+25,...`.

A cleaner later price path may not overwrite an earlier validated PRIOR call.

## Price availability is infrastructure, not a model feature

The authoritative raw NG tape is required infrastructure for this study.

If a required raw session is missing or cannot supply a causal baseline for an occurrence, the run must fail closed as a **data-integrity failure**. It may not silently drop that row.

Once raw-tape integrity passes:

- `price_structure_available` is assumed true for all model-eligible occurrences;
- availability/missingness may not be passed into the classifier;
- availability may not separate births from stops;
- no positive/negative row may receive preferential price coverage.

In short: **price structure is input data; price-structure availability is not predictive information.**

## Sparse D4/D5 preservation

D4 and D5 remain low-support case studies, but each individual predecessor occurrence still receives its own causal one-second price path.

For durable storage, one full path through the maximum PRIOR-eligible H may be stored per predecessor occurrence; every earlier H is an exact prefix of that path. This preserves the complete dense-clock price structure without duplicating the same prefix hundreds of times.

Low support prevents a universal timing law; it does not permit deleting price structure from the preserved cases.

## Strategy handoff

Once a PRIOR chain-birth signal validates, strategy research begins from the exact signal timestamp and may use:

- the individual predecessor price structures that produced the signal;
- the predicted next-stage birth probability;
- the separately validated direction/behavior characterization;
- raw price economics from the signal forward;
- remaining runway, MFE/MAE, chop/directionality, costs, and candidate exits.

Fallback strategy research starts only at the earliest validated fallback point for cases where no PRIOR birth signal validates.

## Protected boundaries

This addendum does not modify the frozen detector, canonical rows, Phase-1 lineage/scores, Phase-2 findings, runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or the frozen SSOS play. No play promotion or permanent brain merge is authorized.
