# S125 independent 12-month gas-generation vs Henry Hub ledger

Window: 2025-08-01 through 2026-07-31 (365 calendar days).

This artifact intentionally computes no R-squared, correlation, regression, fitted coefficient, seasonal mean, or annual mean.

`physical_daily_365d.csv` preserves every calendar day of US48 EIA Grid Monitor generation by fuel. `hh_trading_day_event_ledger.csv` preserves each Henry Hub trading-day move and compares it with the change in US48 natural-gas generation over the same trading-date endpoints. Weekend and holiday physical paths remain visible via the calendar gap and interval NG min/max columns.

Natural-gas generation is retained in raw MWh. No heat-rate conversion is applied here, so a Bcf/d conversion cannot create or reverse the sign relationship. Wind and solar are retained on every date because the requested study is intentionally limited to one recent renewable regime.

The source workbook's `UTC time` is treated as interval end. We subtract one hour to obtain interval start, convert to America/New_York, then sum by local calendar date. The `source_hour_count` field preserves the 23/24/25-hour DST audit trail.

Physical calendar rows: 365
Henry Hub event rows: 246
First Henry Hub event row: 2025-08-04
Last Henry Hub event row: 2026-07-31

Sources:
- EIA US48 Grid Monitor full-history workbook: https://www.eia.gov/electricity/gridmonitor/knownissues/xls/Region_US48.xlsx
- EIA Henry Hub daily history: https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDd.xls
