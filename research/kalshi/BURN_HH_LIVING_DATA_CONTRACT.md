# Burn / Henry Hub Living Data Contract

Status: S125 baseline locked.

## Scope

Maintain a continuously refreshed event-level dataset for U.S. gas-fired power generation and Henry Hub observations.

The active comparison window is the most recent complete 365 calendar days available at the chosen cutoff. Older rows may be retained separately for provenance and later historical testing, but they are not mixed into the active recent-year window.

## Method constraints

Each dated observation remains individually recoverable. The canonical dataset does not replace event rows with pooled R-squared, correlation, regression, annual averages, seasonal averages, or fitted coefficients.

Season and month are labels for retrieval and comparison, not replacements for the underlying dated rows. Spring and fall remain in the dataset.

## Required fields

Retain when available:

- event date
- prior comparable Henry Hub date
- source availability / as-of timestamp
- Henry Hub level and change
- US48 gas-fired generation level and change
- wind level and change
- solar level and change
- hydro level and change
- nuclear level and change
- coal level and change
- calendar gap and intervening-day count
- same-direction, opposite-direction, or zero-involved relationship label
- season and month
- source and revision identifier

Raw MWh remains the canonical physical unit. Any later unit conversion is derived and must preserve the underlying raw values.

## Causal reconstruction

For any historical as-of view, expose only rows and revisions available before that cutoff. Later rows and later revisions are excluded from that reconstruction.

If a source revises historical values, retain enough provenance or version information to distinguish the newer revision from the earlier as-of state.

## S125 baseline

Generator: `research/kalshi/burn_hh_12m_event_ledger.py`

Baseline README: `research/kalshi/s125_burn_hh_12m/README.md`

Completion record: `S125_GAS_AUDIT_STATUS.md`

Successful baseline build commit: `a7d6d04b27f6bdf79b3d96f1bcaaa124c056a05f`.

The S112/S113 June 29 statement is not treated as a verified baseline row under this data definition because it did not reproduce as a simple day-over-day result in the raw EIA US48 generation series.
