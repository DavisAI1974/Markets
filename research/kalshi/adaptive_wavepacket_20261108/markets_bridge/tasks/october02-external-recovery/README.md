# October 2 external evidence

This recovery uses the available October 2, 2023 NGX3 tape from 00:00 UTC through the 21:00 UTC halt, with the halt excluded. The prior evening market tape remains outside the available span. No original October 2 day attachment was found in the pinned catalog. The recovery file reports the source, units and as-of placement for each result. The four-date calculation gate remains open.

| Point | Disposition | October 2 result |
| --- | --- | --- |
| 1. NYMEX managed-money percentile, 1 year | Recomputed CFTC archive | 42.45 |
| 2. Gas-weighted HDD forecast | Reconstructed and held for release clock | 71 cycle/model/target rows for October 2–9. All 52 overlapping October 3 attachment aggregates matched independently calculated HDD, CDD, coverage and station count. |
| 3. NYMEX managed-money weekly change | Independently verified | −23,471 contracts. The September 26 and September 19 source reports independently match the underlying long and short counts. |
| 4. NYMEX managed-money percentile, 3 years | Recomputed CFTC archive | 18.15 |
| 5. US48 wind generation | Held for first-publication vintage | EIA-930 archive rows retained. The source declares a current revision and a nominal availability clock. |
| 6. Sessions since prompt expiry | Verified calendar control | Three sessions after NGV23 expired on September 27. The source-defined default reader placement is 2 p.m. ET on October 2. |
| 7. Estimated US48 gas burn | Held for first-publication vintage | EIA-930 archive rows retained. The derived burn estimate inherits the source vintage and clock. |
| 8. ICE LD1 managed-money percentile, 1 year | Recomputed CFTC archive | 59.43. All four ICE code histories remain separate. |
| 9. GFS/NAM HDD disagreement | Reconstructed and held for release clock | Six matched model cycles. The calculations use the common stations for each target and exclude unresolved station conflicts. |
| 10. Observed gas-weighted HDD | Held for publication clock | Archived daily and station values retained. The daily gas-day close and station times are distinct from the nominal ten-minute dissemination lag. |
| 11. Weekly storage | Independently verified as reported | 3,359 Bcf, up 90 Bcf for the week ending September 22, and 189 Bcf above the five-year average. The revised catalog calculation of 199 Bcf above average remains separate. |
| 12. Storage estimate vs. actual | Independently verified alternate survey | The Desk median was 90 Bcf, the actual was 90 Bcf and the difference was 0 Bcf. The separate Investing.com 88 Bcf estimate has a retained capture after the October 2 halt, so that variant remains held for earlier availability. |
| 13. Futures curve | NGX3 trades verified. Full strip held. | All 37,670 NGX3 trade occurrences matched receive time, event time, instrument, price, size and aggressor side against the pinned tape. Other contracts, statistics, definitions and shape dependencies remain subject to full-strip checks. |

The CFTC values use the September 26 futures-only report. The original publication date is September 29, 2023 and the pinned publication rule places it at 3:30 p.m. ET. The 1-year and 3-year percentile values reproduce the original midpoint rank over the 53 and 157 underlying weekly observations. The latest report and the prior NYMEX report were independently matched to the contemporaneous long-format publications. The first-print vintage of every older constituent in the percentile histories has yet to be checked individually. [CFTC September 26 report](https://www.cftc.gov/sites/default/files/files/dea/cotarchives/2023/futures/nat_gas_lf092623.htm) · [CFTC September 19 report](https://www.cftc.gov/sites/default/files/files/dea/cotarchives/2023/futures/nat_gas_lf091923.htm) · [Official historical dataset](https://publicreporting.cftc.gov/w/72hh-3qpy/default?cur=3Os6srWMit3)

The storage attachment conservatively places both September 28 EIA update values at the end of its dated release day in New York, before the available market span. Its survey scope differs from the Investing.com variant. Calendar calculations used the pinned expiry and business-day code with the CME termination rule. [EIA September 28 update](https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2023/09_28/) · [CME NYMEX Rulebook, Chapter 220](https://www.cmegroup.com/rulebook/NYMEX/2/220.pdf)

The compressed ledger contains 146,800 normalized candidates with original observation and scope, numeric and missing state, event and publication fields, and every matching source occurrence. It applies the halt cutoff to each row and uses the original 72-hour weather and eight-day power scopes as carry-in bounds. The October 3 attachment explicitly pins the October 2 parent curve input partition. No October 2 definitions were present in the selected catalog clocks. The combined October 2–3 exporter can overwrite earlier instrument definition metadata, so full-curve reconciliation needs the original parent definition, statistics and trade partitions. The verified NGX3 component does not establish those aliases or components. Reconstructed October 2 MOS values retain the modeled runtime-plus-4.5-hour stamp as an evidence field. A matching historical calculation does not establish dissemination timing.

The normalized catalog was recovered by reading the 57 Git archive chunks in manifest order, checking each length and SHA-256, matching the 3,788,033,203-byte aggregate, and streaming only the 8,941,207,552-byte scoped SQLite member to scratch. Its SHA-256 matched the repository component manifest. Temporary scratch and the original absolute paths do not serve as artifact dependencies.

- [Recovery receipt and selected values](october02-external-recovery.json)
- [Reconstructed forecast and disagreement candidates](october02-mos-reconstruction.json)
- [NGX3 curve component comparison receipt](october02-ngx3-curve-trades-crosscheck.json)
- [Source-row ledger](october02-normalized-evidence.jsonl.gz)
- [Independent CFTC historical extract](cftc-disaggregated-futures-only-through-2023-09-26.json)

Use the receipt's dispositions and times in any later reader. The held rows and alternate estimates remain in their own source roles. The recovered rows have not been joined to ROOT or used to calculate a discovery score.
