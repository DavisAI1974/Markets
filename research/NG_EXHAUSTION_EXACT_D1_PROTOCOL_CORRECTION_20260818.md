# NG Exhaustion Exact-D1 Chronology Correction — 2026-08-18

Status: **AUTHORITATIVE ADDENDUM TO THE EXACT-D1 CAMPAIGN; PHASE-1/PHASE-2 FREEZES UNCHANGED.**

## Why this correction is required

The exact-D1 definition is `all_model_consecutive_positive_depth == 1` from the frozen Phase-1 lineage. The Phase-1 structural engine is out-of-time by construction: base weeks 0–17 train the first fold, and the first lineage labels are emitted only for test weeks beginning at base week index 18.

Therefore the first 18 base weeks have **no honest exact-D1 label**. They must not be relabeled in-sample, treated as D1 negatives, or used to fit D1 duration families.

## Correct exact-D1 chronology

- Base weeks 0–17: **PRELINEAGE_UNLABELED**. Preserve as Phase-1 model-training provenance only; exclude from D1 fitting and D1 predictor negatives.
- Base weeks 18–35 (Phase-1 Eras1–3): **D1 DISCOVERY/FIT**. These are the first 18 genuinely OOT lineage-labeled weeks.
- Base weeks 36–47 (Eras4–5): **D1 VALIDATION 1**.
- Base weeks 48–53: **D1 UNTOUCHED HISTORICAL CONFIRMATION**.
- Held week `20260329`: **INSERT-ONLY HELD VALIDATION**.

For compatibility with the already-written D1 lane functions, some machine outputs may retain the internal field name `train` for the D1 DISCOVERY/FIT block. That internal field must never be confused with the original Phase-1 training weeks.

## What does not change

This correction does not rebuild, retune, or alter:

- the exhaustion detector;
- canonical event rows;
- Phase-1 structural gains or lineage scores;
- Phase-2 findings;
- the runway clock;
- permanent Frankie or Frankie 1;
- `research/kalshi/spawn.py`;
- the frozen SSOS paper play.

No new play is promoted. Any profitable historical D1 candidate still requires a fresh prospective/OOT promotion contract.
