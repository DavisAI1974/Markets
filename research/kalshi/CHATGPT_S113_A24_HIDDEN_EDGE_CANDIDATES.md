# S113 A-24 DISCOVERY NOTE

# Hidden Edge Candidates Inside DATA_POINTS.md

Date: 2026-08-05
Source reviewed: DATA_POINTS.md
Scope: Candidate discovery from the field registry. This is not a correlation result because the registry contains field names, coverage, readership and defects, not the underlying daily values.

## Executive conclusion

The registry suggests that the largest unexploited value is not another standalone input. It is the interaction between:

1. how large a state change is;
2. whether independent sources confirm it;
3. when the information became available;
4. whether the physical system had room to absorb it; and
5. whether the market-data measurement itself was trustworthy.

Three candidate mechanisms stand out as possible new edge families:

1. Weather information acceptance: revision size x model convergence x release timing.
2. Storage headline versus revision polarity: surprise x vintage revision x regional location.
3. Physical absorption capacity: regional gas-marginality breadth x South Central salt-storage composition.

Two additional candidates look more like high-value filters than new direction signals:

4. Freshness-weighted source precedence.
5. Order-flow signal integrity from denominator and session-quality agreement.

Two lower-confidence but genuinely non-obvious curve-shape candidates are also worth testing:

6. Cross-basin freeze geometry x storage buffer.
7. Sunset compression x regional gas marginality.

The known obvious gaps were deliberately excluded: forward wind and solar, LNG feedgas, weather ensembles, forward nuclear outages, hydro serving, Southeast BA coverage, weather-station redesign, basic COT changes, and chain state. Those are already explicit work items.

## Evidence limitation

DATA_POINTS.md proves that the fields exist, how long they are populated, whether the blind can see them and whether anything reads them. It cannot prove that two fields are correlated.

Therefore every item below is labelled CANDIDATE, not FINDING.

A candidate should be promoted only after:

- a named benchmark is beaten;
- the mechanism works in the specific cells where it is supposed to work;
- the relationship survives an untouched forward period;
- the result is not created by a block defect or timestamp leak; and
- the rule has a computable no-call state.

## Rank 1 - Weather information acceptance

### Core idea

The desk currently has the size of the weather revision, but does not read the two variables that determine whether the revision should already be priced and whether it is credible:

- inter-model disagreement;
- exact information availability relative to the market reopen or session.

The same GWDD revision is not the same event in three states:

1. It completed before Globex reopened and was already available for the opening gap.
2. It completed after the reopen and is new intraday information.
3. It is large but independent models are moving apart rather than converging.

The hidden variable is not weather. It is market acceptance of the weather revision.

### Exact fields

Revision magnitude already available:

```text
weather_forecast.run_delta[*].d_gw_hdd
weather_forecast.run_delta[*].d_gw_cdd
weather_forecast.run_delta[*].coverage
weather_forecast.run_delta[*].partial
```

Unread agreement fields:

```text
model_disagreement.summary.max_abs_spread_gw_hdd
model_disagreement.summary.max_abs_spread_horizon
model_disagreement.summary.mean_abs_spread_over_overlap
model_disagreement.summary.n_overlap_horizons
model_disagreement.disagreement[*].spread_gw_hdd
model_disagreement.disagreement[*].spread_gw_cdd
model_disagreement.stability.GFS[*].d_gw_hdd
model_disagreement.stability.MEX[*].d_gw_hdd
model_disagreement.stability.NAM[*].d_gw_hdd
```

Unread information-clock fields:

```text
weather_forecast_cycle.sunday_reopen.asof_utc
weather_forecast_cycle.sunday_reopen.max_cycle_runtime_utc
weather_forecast_cycle.sunday_reopen.availability_rule
weather_forecast_cycle.weekday_open.asof_utc
weather_forecast_cycle.weekday_open.max_cycle_runtime_utc
model_disagreement.asof_utc
globex_reopen_et
session_close_et
settle_window_et
```

### Pre-registered directional implications

- Revision completed before reopen: more of the effect should appear in the gap, with less remaining intraday continuation.
- Revision completed after reopen and model disagreement falls: higher probability of a continuing intraday leg.
- Revision completed after reopen and model disagreement rises: higher probability of whipsaw, giveback or no call.
- Partial coverage or a low overlap count should reduce authority regardless of revision size.

These are mechanism signs, not fitted thresholds.

### Outcome

Separate the price curve into:

```text
weekend or session gap
first-hour move
remaining-session slope
maximum favorable excursion
giveback from first reaction
settlement move
```

### Benchmark to beat

Weather revision magnitude alone.

### Kill test

Kill the interaction if release timing and disagreement add no out-of-sample discrimination to gap-versus-intraday delivery after controlling for revision size and horizon.

### Why it could be large

This directly prevents the system from treating an already-priced weekend revision as fresh intraday information. It also turns model disagreement into an observed no-call gate rather than a prose confidence statement.

## Rank 2 - Storage headline versus revision polarity

### Core idea

The system has three simultaneous descriptions of the same storage event:

1. the headline surprise versus consensus;
2. the difference between the as-printed and current vintage;
3. the regional location of the revision, including South Central salt and nonsalt.

None of the revision fields is read.

A bullish headline accompanied by an offsetting bearish revision is not the same event as a bullish headline confirmed by revisions. That difference should affect curve shape even when the first price reaction has the same sign.

### Exact fields

```text
storage_consensus.last_print.surprise_as_printed_vs_consensus_bcf
storage_consensus.last_print.vintage_diff_bcf
storage_vintage.vintage_delta_chg
storage_vintage.vintage_delta_level
storage_vintage.regions.*.chg_delta
storage_vintage.regions.*.level_delta
storage_vintage.regions.south_central_salt.chg_delta
storage_vintage.regions.south_central_nonsalt.chg_delta
storage_vintage.regions.south_central_salt.level_delta
storage_vintage.regions.south_central_nonsalt.level_delta
storage_vintage.as_printed_recovered
```

### Pre-registered states

```text
headline and revision aligned
headline and revision opposed
national revision small but South Central revision material
salt and nonsalt revisions aligned
salt and nonsalt revisions opposed
```

No magnitude threshold is proposed. Alignment is defined by sign.

### Expected curve implication

- Aligned headline and revision: greater continuation probability.
- Opposed headline and revision: greater spike-and-fade or turn probability.
- Revision concentrated in South Central salt: potentially different Henry Hub response from the same national revision located elsewhere.
- Salt and nonsalt opposition: possible signal that the national total is hiding different short-cycle and seasonal inventory conditions.

### Benchmark to beat

Headline storage surprise alone.

### Kill test

Kill the mechanism if alignment and regional revision topology do not change continuation, giveback or end-of-day direction within the same headline-surprise cells.

### Why it could be large

The desk forecasts a curve, not just the first reaction. Revision polarity is naturally a continuation-versus-fade variable.

## Rank 3 - Physical absorption capacity

### Core idea

The registry holds the two sides of a physical elasticity calculation but does not combine them:

- how broadly gas is becoming marginal across power regions;
- the composition of the South Central storage buffer near the Henry Hub system.

US48 gas burn can be identical in two sessions while one is concentrated in a single BA and the other is a synchronized increase across several large regions. The second state is more likely to create correlated physical demand.

Likewise, the same total South Central inventory can have a different salt-versus-nonsalt composition.

The candidate edge is the interaction, not either level alone.

### Exact fields

Unread BA gas-share fields:

```text
grid_stack.bas.CISO.gas_share
grid_stack.bas.ERCO.gas_share
grid_stack.bas.MISO.gas_share
grid_stack.bas.PJM.gas_share
grid_stack.bas.SOCO.gas_share
grid_stack.bas.SWPP.gas_share
grid_stack.bas.US48.gas_share
```

Existing BA gas fields:

```text
grid_stack.bas.*.gas_mwh
grid_stack.bas.*.gas_chg_7d_mwh
grid_stack.bas.US48.est_gas_burn_bcfd
```

Unread storage-composition fields:

```text
storage_regional.salt_share
storage_regional.regions.south_central_salt.vs_year_ago
storage_regional.regions.south_central_nonsalt.vs_year_ago
```

Existing regional controls:

```text
storage_regional.regions.south_central_salt.vs_5yr
storage_regional.regions.south_central_nonsalt.vs_5yr
storage_regional.regions.south_central_salt.weekly_chg
storage_regional.regions.south_central_nonsalt.weekly_chg
```

### Derived variables to test without fitted weights

```text
gas_marginality_breadth:
number of served BAs whose gas share increased from the prior observation

gas_marginality_dispersion:
cross-BA dispersion of gas-share changes

salt_composition_change:
change in storage_regional.salt_share

salt_nonsalt_divergence:
difference in the signs of salt and nonsalt weekly changes or benchmark gaps
```

The BA count is an equal-count diagnostic, not a claim that each BA has equal Henry Hub transmission.

### Expected implication

Conditional on the same US48 gas burn or gas-burn change:

- broader regional gas marginality plus a less supportive salt-storage state should produce a larger Henry Hub response;
- concentrated gas burn with an offsetting storage composition should produce less price elasticity;
- weather revisions should have more price impact in the broad-and-thin state.

### Benchmark to beat

```text
US48 gas burn alone
South Central total storage alone
weather revision alone
```

### Kill test

Kill the interaction if gas-marginality breadth and storage composition add no out-of-sample value after controlling for total gas burn, season and storage level.

### Why it could be large

This is a candidate conversion edge: it estimates when the same weather or load shock becomes a large Henry Hub shock.

## Rank 4 - Freshness-weighted source precedence

### Core idea

The registry contains ages and availability timestamps throughout the state, but many are unread:

```text
ngwu_balance.issue_age_days
ngwu_balance.knowable_from
cot.age_days_combined
steo_vintage.knowable_from
weather_forecast.asof_utc
weather_forecast_cycle.*.asof_utc
model_disagreement.asof_utc
storage_consensus.*.snapshot_utc
tape_conditions.asof_prior_session
```

The system has previously failed when an old fundamental narrative overruled fresh order flow. The hidden variable may be the age difference between the conflicting sources.

### Candidate rule class

Authority should depend on:

```text
source freshness
source cadence
whether a newer source directly contradicts it
whether the slow source has updated since the market regime changed
```

This does not mean fresh always wins. It means stale and fresh observations should not vote as if they were simultaneous.

### Test

On days where tape and fundamentals disagree:

1. record the age of every contributing block;
2. identify the freshest directional family;
3. compare outcomes when the fresh family was followed versus overruled;
4. keep results per conflict type and season.

### Benchmark to beat

The current fixed precedence or narrative synthesis.

### Kill test

Kill freshness as an authority variable if source-age spread does not discriminate which side wins on conflict days.

### Why it could be large

It can improve direction without adding another predictor. It changes who is allowed to speak.

## Rank 5 - Order-flow signal integrity

### Core idea

The desk's best direction result uses order-flow imbalance, but the registry holds unread fields that test whether the imbalance was measured cleanly:

```text
tape_conditions.session_b_share
tape_conditions.session_b_share_two_sided
tape_conditions.phase_b_share_two_sided[*]
tape_conditions.unsided_volume_frac
tape_conditions.prior_session_is_reopen_stub
tape_conditions.session_b_share_basis
tape_conditions.source_store
tape_conditions.phase_n_trades[*]
tape_conditions.l1_book.quote_bid_share_p25_p75[*]
```

The unread fields also carry a known `h-tape_offinstrument` defect marker. The candidate edge is not a new direction signal. It is a quality gate on the existing signal.

### Pre-registered confirmation conditions

A strong order-flow call has higher authority when:

- all-trade and two-sided b-share agree in direction;
- phase-level signed flow agrees rather than cancelling;
- the observation is not a reopen stub;
- unsided volume does not dominate the result;
- trade and phase counts show that the reading is supported by actual observations;
- quote-side distribution confirms the same pressure.

No numeric cutoff is proposed.

### Benchmark to beat

The existing strong-flow call without an integrity gate.

### Kill test

Kill the gate if existing signal failures are not concentrated in denominator disagreement, reopen stubs, unsided-volume problems or low-information phases.

### Data limitation

Several quality fields have only 29 observations or fewer. Use the existing sample only for diagnosis and accrue forward evidence before granting production authority.

## Rank 6 - Cross-basin freeze geometry

### Core idea

The forecast has per-basin freeze detail, but almost every numeric field in the block is unread:

```text
freeze_risk.*.basins.MAF.thresholds_f.*.first_below
freeze_risk.*.basins.MAF.thresholds_f.*.last_below
freeze_risk.*.basins.MAF.thresholds_f.*.max_consecutive
freeze_risk.*.basins.OKC.*
freeze_risk.*.basins.PIT.*
freeze_risk.*.basins.SHV.*
freeze_risk.*.basins.*.tmin_by_horizon[*]
```

National GWDD collapses the order, overlap and duration of basin-level cold. Those three properties may distinguish a local cold event from a correlated production-system shock.

### Candidate interactions

```text
number of basins simultaneously below a fixed published threshold
time spread between first-below dates
overlap duration
sequence of first-below dates
maximum consecutive duration
interaction with South Central salt storage state
```

The temperature thresholds already exist in the data. Do not retune them against price.

### Benchmark to beat

GWDD revision and the coldest single basin alone.

### Kill test

Kill the geometry if basin overlap and sequence do not add value within equal-GWDD cells.

## Rank 7 - Sunset compression and the deterministic gas ramp

### Core idea

The registry contains a complete deterministic solar clock that nothing reads:

```text
solar.gw_day_length_chg_7d
solar.gw_day_length_h
solar.metros.*.sunset_et
solar.sunset_et_earliest
solar.sunset_et_latest
```

It also has unread regional solar share and gas share:

```text
grid_stack.bas.*.solar_share
grid_stack.bas.*.solar_chg_7d_mwh
grid_stack.bas.*.gas_share
```

The non-obvious variable is not total solar generation. It is the width and location of the sunset window across gas-marginal BAs.

### Candidate mechanism

When several high-solar, high-gas-share BAs lose solar within a narrow Eastern-time window, the thermal ramp is synchronized. That may generate a repeatable late-session price-curve leg even when daily temperature is unchanged.

Nuclear outage changes can be tested as a separate level condition:

```text
nuclear_outages.chg_1d_mw
nuclear_outages.pct_of_fleet_out
```

### Benchmark to beat

Daily solar MWh, day length and load alone.

### Kill test

Kill the mechanism if sunset-window width and regional solar/gas shares do not explain late-session slope after controlling for load, weather and realized solar generation.

### Confidence

Lower than the first five. The mechanism is clean and dated, but the current served grid block is daily. The strongest test may require the hourly EIA-930 series already upstream rather than the daily roll-up.

## What was deliberately excluded

These are important, but they are already visible and are not hidden discoveries:

```text
forward wind and solar forecast
ECMWF and GEFS ensemble members
LNG feedgas
forward nuclear outage schedule
hydro serving and reservoir state
coal additions and retirements
Southeast BA serving
weather-station redesign
basic COT change
chain state
NO CALL
```

Price-derived blocks were also excluded from blind-edge claims:

```text
options_surface
contract_structure
cash_basis
vol_regime
squeeze_watch
```

The registry states that the blind sees these frozen at the anchor vintage. They may be useful for other lanes or research, but unread fields inside them are not hidden live predictors.

## Recommended test order

### First pass

1. Weather information acceptance.
2. Storage headline versus revision polarity.
3. Physical absorption capacity.

These have 118 to 131 populated observations across most components and directly target curve direction, continuation and magnitude.

### Second pass

4. Freshness-weighted source precedence.
5. Order-flow signal integrity.

These may improve the system faster than adding new predictors.

### Third pass

6. Cross-basin freeze geometry.
7. Sunset compression.

These are narrower seasonal or intraday mechanisms.

## Minimal output contract for every test

```text
candidate_id
session
information_available_at
eligible_cell
input_fields
predicted_behavior
actual_curve_behavior
benchmark_behavior
incremental_result
falsified
reason
```

## Final assessment

There are hidden gems in the registry, but the best ones are not simple pairwise correlations.

The most promising unknown structure is:

```text
shock x confirmation x novelty x absorption capacity
```

The desk already owns most of those dimensions. The failure is that the state serves them as separate fields and the reasoning layer does not join them.

The strongest single candidate is the weather information-acceptance mechanism. The strongest physical candidate is gas-marginality breadth interacted with South Central salt-storage composition. The strongest curve-shape candidate is storage headline-versus-revision polarity.
