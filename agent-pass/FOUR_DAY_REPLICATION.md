# Four-date replication status

**November 9 update:** the remaining family four-arm/prebirth/primer scope is now complete on October 2, 3 and 17, with October 18 reference reproduction. See [FAMILY_REPLICATION.md](FAMILY_REPLICATION.md) for immutable outputs, populations, checks and comparison limits. This supersedes the missing-family status from the earlier dipole-only run below.

## Four-date replication completion — 2026-11-08 Eastern

Latest user priority: finish October 2, 3 and 17 to the October 18 NG dipole analysis scope first. Assemble timestamped layers afterward, then add other researchers' work. Do not restart crypto-source exploration or paper infrastructure before finishing this replication.

The previously missing continuous precursor scan and primer diagnostics are now published in [markets-data](https://github.com/DavisAI1974/markets-data/tree/71240aa56a8b27f7d7f68acd154784579094e5c1/tasks/family-research-20261022/four-day-extensions/run-42563528655-1). [Hosted run 42563528655](https://github.com/DavisAI1974/markets-data/actions/runs/42563528655) succeeded. Source code: Markets `c4ca63f2816a50e051f70f6219f2378bd9530777`. Publication: markets-data `71240aa56a8b27f7d7f68acd154784579094e5c1`. There are 64 output files (34,935,051 measured bytes) plus the manifest.

Six unit tests passed. Before the other dates ran, October 18 reproduced all eight saved continuous-scan tables and all three primer tables, with numerical comparison tolerance rtol 1e-11 / atol 1e-12. Per-date checks passed for strict availability, all births, onset/operator reconciliation, contiguous observation clocks, outcome denominator conservation, and the two finalization-only births. The published summary/verification files were read back and the chart visually inspected.

| Analysis | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
|---|---|---|---|---|
| Native A–E, M1/M2 and shape forms | Existing complete | Existing complete | Existing complete | Existing complete |
| Original dipole application, 11-arm stack | Existing complete | Existing complete | Existing complete | Existing complete |
| Dipole prebirth controls, aggression-to-rest, delayed observations | Existing complete | Existing complete | Existing complete | Existing complete |
| Continuous completed-second precursor scan, all 10 predicates | Newly complete | Newly complete | Newly complete | Reproduced |
| Primer next-price-change and 1ms–20s response grid on aggression-to-rest cases | Newly complete | Newly complete | Newly complete | Reproduced |
| Primer dipole prebirth quote-age/control-reuse sensitivity | Newly complete | Newly complete | Newly complete | Reproduced |
| Family four-arm study, prebirth controls and family primer | Complete: 796 families | Complete: 849 families | Complete: 824 families | Original 749 reproduced |

| Date | Retained births | Observed seconds | Input-available seconds | Unique onset seconds |
|---|---:|---:|---:|---:|
| Oct 2 | 741 | 75,600 | 75,579 | 10,932 |
| Oct 3 | 833 | 82,800 | 82,758 | 11,928 |
| Oct 17 | 741 | 75,600 | 75,579 | 10,602 |
| Oct 18 | 863 | 82,800 | 82,758 | 10,383 |

October 2 and 17 retain the original partial spans. No prefix was substituted. The finalization-only birth on October 3 and on October 17 remains in retrospective links without an invented recognition.

Evidence status, before assembling other layers:

- **Agrees:** the same precursor categories occur on every date. Among births with a prior onset, median last lead is 12–13 seconds for step weakening, 19 seconds for fresh opposed weakening on all four dates, and 19–20 seconds for half-window weakening. These are descriptive onset-to-birth intervals, not simulated trade lead times or measurements of whole-path similarity.
- **Differs:** onset counts, unlinked onset counts, and control sensitivities differ. For example, October 2's one-second prebirth displayed-lot contrast is negative across all matched pairs but positive when both quotes are at most one second old. October 17's 20-second contrast changes from positive to negative under that same fixed diagnostic. The original summary statistics are reproduced as diagnostics; individual input values and time paths are not rescaled.
- **Unresolved:** the separate family four-arm/prebirth/primer inputs have since been recovered and completed (FAMILY_REPLICATION.md). Older targeted family/lifecycle overlaps and original Family A runway identities remain separate scopes; the dipole extension run does not certify those broader studies as replicated. Exact duration/exhaustion strategy and paper execution remain unconfigured. The optional parent tail audit was a proposed additional study, not a completed October 18 module to copy.

No desktop computation, producer rerun, timestamp-layer assembly, external researcher merge, simulator execution or live order occurred in this replication. All ten precursor hypotheses and all existing 11 stack arms remain retained.
