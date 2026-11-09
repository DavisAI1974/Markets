# Four-date combined event studies — completed and verified

Completed 2026-11-09 on GitHub-hosted CPU runners for October 2, 3, 17 and 18. No boxes were needed. These are the current verified combined-study outputs.

[Browse the four result folders](https://github.com/DavisAI1974/markets-data/tree/87dc338f2e74646eb731b3cd6f8968a5a0a653e2/tasks/family-research-20261022/combined-events/run-42571551209-1). Each events-YYYYMMDD folder contains analysis-summary.json, verification.json, source/input manifests and a SHA256/byte-size MANIFEST.json.
[Successful final verification and publication](https://github.com/DavisAI1974/markets-data/actions/runs/42571551209).

## Reproducible inputs and execution

- Exact action clocks and book reconstruction: markets-data commit 2fd55ea1276d00530f8cdbd1caf5918910494f19, combined-events/run-42569937357-1. Original DBN action timestamps were recovered; every retained action reconciled to the compact cache and every completed group's best prices, sizes and order counts to the saved export.
- Full studies: run 42570958744, code 782e1e11ffb4c3eb0fbfe6fd84fc75a3a3fdc516.
- Independent read-back, clock/reference verification and joint links: run 42571551209, code 43e4d2bdfa5a10f4df9ab1b12da1dd713615bbd4.
- Authoritative data publication: 87dc338f2e74646eb731b3cd6f8968a5a0a653e2, tasks/family-research-20261022/combined-events/run-42571551209-1.
- October 2 and 17 have partial retained session coverage. Counts refer to each saved span, not equal full-session coverage.

## Completed scope

1. Chronology, duration and overlap: all retained prints, equal-price stretches, directional print legs, first family observations and all occurrences, neighboring starts, shifted family windows, prior price changes and actual archived dipole recognition links.
2. Pressure and response: size-one onsets, early falling-size signals and retreat-to-previous-second signals; strict-prior print cadence, fresh/rolling wire flow, quote-ending mechanisms, next-group print arrival and delayed hypothetical quote observations.
3. Large moves and recovery: midpoint jumps of at least two ticks, prior signals, 1/5/20-second response, first half/full return after the first-five-second displacement, selected original actions/book states, and fixed-price versus moving-rank depth changes.
4. Explicit cross-study joins: cross-study-event-links.parquet retains one row per pressure signal with its structural family, already-recognized dipole, previous trade and observable flow/book/cadence context. cross-study-condition-outcomes.parquet describes joint conditions without collapsing source events. Retrospective leg IDs are navigation only, not signal inputs.

| Date | Trades | Price stretches | Print legs | First families | Pressure signals | Large moves | Joint outcome rows |
|---|---:|---:|---:|---:|---:|---:|---:|
| Oct 2 | 37,670 | 9,569 | 5,996 | 796 | 109,307 | 46 | 327,921 |
| Oct 3 | 41,410 | 10,573 | 6,907 | 849 | 116,187 | 58 | 348,561 |
| Oct 17 | 33,451 | 9,762 | 5,592 | 824 | 114,994 | 57 | 344,982 |
| Oct 18 | 30,739 | 9,109 | 5,120 | 764 | 109,754 | 64 | 329,262 |

The original October 18 selected 749-family study remains correctly reproduced in FAMILY_REPLICATION.md. This expanded chronology includes all 764 observed structural families. The 15 additional families are a scope difference.

## Verification and comparison

**Agrees:** original October 18 chronology counts, bounded signal counts (1,012 size-one, 2,850 early-falling, 698 retreat), next-group arrival cells, 64 large moves, all twelve original rule/side-by-horizon outcome cells and thin-quote ending/by-entry counts reproduce. Every date passes individual signal clocks, strictly prior print order, episode endings, delayed quote clocks and integer-nanosecond schema checks. Joint outcome denominators conserve every signal and its three horizons.

**Differs:** date populations and observed outcomes vary. Under the defined 600-second recovery observation, full returns occur in 35/46, 48/58, 42/57 and 49/64 large moves respectively. A failure to observe return is not proof of permanent movement. Structural starts, Native births and CCode's independent candidates are distinct populations; a family first observation is not automatically a market birth.

**Unresolved:** CCode's independently generated 839/857/830/890 candidates still require explicit identity/scope matching to Native 741/833/741/863; our study uses actual archived recognition, not t0+50. See CCODE_FAMILY_AND_RECOGNITION_INPUTS.md. Desktop's shape layers and the old 2,000-winner curves are not yet reconciled by these joins. Recognizable shape, remaining duration and useful decision timing still need interpretation against these individual records.

## Clocks, limits and next use

Event, receive, completed-group known-by and actual recognition clocks remain separate integer nanoseconds with source cursors/groups. No smoothing, normalization, value adjustment or forced equal populations. Finalization-only candidates retain missing live recognition; nominal lifetime endpoints do not establish full-path availability.

The historical 1ms entry and 1/5/30-second exits are hypothetical quote observations with observed spread, not actual fills. First recovery is not event death. Overlapping cases and joint counts are descriptive, not independent trials. This completes the specified combined studies, not every historical 99-field lifecycle or hand-curated case audit.

Next use these tables to pin the existing individual renders and other researchers' records to raw source clocks. The 99 layers and 13 external points stay deferred. Paper configuration/readiness still needs checking; no paper orders have been started by this work.

Known mistakes are corrected in the active results and summaries. The corrected version is authoritative; erroneous substitutes are not competing findings. Original observations, including unfavorable cases and genuine missing data, remain intact.
