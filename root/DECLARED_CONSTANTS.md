# ROOT: every number written into the code, and why (SPEC-root.md criterion 10)

The test `tests/root/test_outside.py::test_no_hidden_numbers` fails on any number in the ROOT code other than 0 and
1 that is not one of these: a constant listed below, a position inside a record (an index or slice), the rounding
width of a value (the original files' rounding, presentation only), or a calendar fact inside the functions named at
the end.

## `root/calendar.py`

| Constant | Value | Why |
|---|---|---|
| `EASTERN` | America/New_York | The exchange's clock. Daylight and standard time come from the zone. |
| `OPEN_EASTERN` | 6:00 pm | A trade day opens 6 pm Eastern the evening before (Greg's rule). |
| `HALT_EASTERN` | 5:00 pm | A trade day halts 5 pm Eastern on the named date. |
| `SETTLE_FROM_EASTERN`, `SETTLE_TO_EASTERN` | 2:28 pm, 2:30 pm | The NYMEX natural gas settlement window. |
| `NS_PER_SECOND` | 10^9 | Unit conversion. |
| `TRADE_DAY`, `STRETCH`, `STARTUP` | labels | The three labels a written row can carry (SPEC-root.md section B). |
| `SUNDAY` | 6 | Weekday number of Sunday (Monday = 0): the week's start-up day. |
| `FIRST_TRADE_WEEKDAY`, `LAST_TRADE_WEEKDAY` | 0, 4 | Trade days are Monday to Friday. |

## `root/outside.py` (SPEC-outside.md; "as in the original" means Markets 7f34afa)

| Constant | Value | Why |
|---|---|---|
| `TRADE_DAYS` | Oct 2, 3, 17, 18, 2023 | The four trade days in scope. |
| `NS_PER_MINUTE`, `NS_PER_HOUR`, `HOURS_PER_DAY`, `DAYS_PER_WEEK`, `MONTHS_PER_YEAR` | | Unit and calendar conversion. |
| `FRIDAY`, `SATURDAY`, `SUNDAY` | 4, 5, 6 | Weekday numbers (Monday = 0). |
| `GZIP_LEVEL` | 9 | Compression of the larger tables; the content is unchanged. |
| `POSITIONING_CODES` | 023651, 023391, 023392, 0233AG, 0233AH | The NYMEX gas contract and the four ICE gas contracts, as in the original. |
| `WINDOW_1Y_DAYS`, `MIN_REPORTS_1Y` | 365, 45 | The one-year standing (X01, X08) and the fewest reports it needs, as in the original. |
| `WINDOW_3Y_DAYS`, `MIN_REPORTS_3Y` | 1095, 140 | The three-year standing (X04), as in the original. |
| `WEEK_STEP_MIN_DAYS`, `WEEK_STEP_MAX_DAYS` | 5, 10 | The change on the week (X03) is taken only against a report 5 to 10 days earlier, as in the original. |
| `PERCENT`, `TIE_WEIGHT` | 100, 0.5 | The standing is a percentage; a tie in the window counts half, as in the original. |
| `FEDERAL_HOLIDAY_JUNETEENTH_FROM` | 2021 | Juneteenth is a federal holiday from 2021 (positioning release rule). |
| `POSITIONING_RELEASE_EASTERN` | 3:30 pm | Positioning reports come out Friday 3:30 pm Eastern after the report date (rule, as in the original). |
| `CITY_WEIGHTS` | 16 cities | The gas weights of the original, scaled to add up to 1 (`TOTAL_RAW_WEIGHT`, `CITY_SHARE`). |
| `UNWEIGHTED_CITIES` | AUS, SAT | Two cities whose hourly temperature the original showed beside a row, with no weight. |
| `DEGREE_DAY_BASE_F` | 65 F | Degree-day base, as in the original. |
| `HIGH_LOW_MIDPOINT` | 2 | The original forecast day temperature is the midpoint of the day's high and low. |
| `READING_LAG_NS` | 10 minutes | A station reading is taken as public 10 minutes after its time (assumed, as in the original). |
| `READINGS_LOOKBACK_NS` | 72 hours | Station readings are kept from 72 hours before each trade day opens, as in the original. |
| `GAS_DAY_START_EASTERN` | 10:00 am | Fix 3: the gas day runs 10 am Eastern to 10 am Eastern. |
| `CARRY_OVER_GAS_DAYS` | 2 | Fix 3: carry-over is the gas-weighted heating degree days of each of the two gas days before. |
| `GAS_DAYS_FROM` | Sep 20, 2023 | The first gas day made, early enough for every carry-over the four trade days need. |
| `TRACE_PRECIP_IN` | 0.001 inch | A reported trace of rain, as in the original. |
| `FORECAST_TZ` | America/Chicago | The original forecast describes the calendar date in Central time (kept simple for now). |
| `FORECAST_LAG_NS` | 4.5 hours | A forecast model run is taken as public 4.5 hours after it starts (assumed, as in the original). |
| `FORECAST_MIN_TEMPS` | GFS 5, NAM 5, MEX 2 | The fewest forecast temperatures inside a date for that date to be used, as in the original. |
| `FORECAST_ON_ROW` | GFS D, NAM D, GFS D+1, MEX D+3 | The four forecast figures the original showed beside a row. |
| `DISAGREEMENT_HORIZONS` | 8 | The disagreement between models is taken over the trade day's date and the 7 after, as in the original. |
| `GRID_LAG_NS` | 2 hours | An hour's grid figure is taken as public 2 hours after its stamp (assumed, as in the original). |
| `HEAT_RATE_BTU_PER_KWH`, `GAS_BURN_DIVISOR` | 7,900; 1.035e9 | The gas-burn estimate (X07): gas MWh in the hour x 24 x 7,900 / 1.035e9, as in the original. |
| `NG_LAST_TRADE_BUSINESS_DAYS` | 3 | Natural gas futures expire 3 business days before the delivery month. |
| `EXPIRY_SEARCH_MONTHS_AHEAD` | 2 | The last expired contract is found by looking from two delivery months ahead and stepping back, as in the original. |
| `MONTH_CODES`, `TWO_DIGIT_YEAR` | F to Z; 100 | Contract month letters and the two-digit year of a symbol such as NGV23. |
| `UNDEFINED_PRICE`, `PRICE_SCALE` | 2^63 - 1; 10^9 | The vendor's mark for no price, and its price unit. |
| `SETTLEMENT_STAT_TYPE` | 3 | The vendor's code for a settlement price. |
| `CURVE_MONTHS` | 12 | The curve shape is taken over the 12 nearest months that have a price, as in the original. |
| `SHAPE_NEEDS_MONTHS` | 2 | No shape without the front two months; the middle rank is the count halved, as in the original. |
| `STORAGE_RELEASE_EASTERN` | 10:30 am | The weekly storage report comes out Thursday 10:30 am Eastern (rule, as in the original). |
| `STORAGE_RELEASE_DAYS_AFTER_WEEK` | 6 | That Thursday is 6 days after the week ending Friday, as in the original. |
| `FIVE_YEAR_PRIOR_YEARS` | 5 | The five-year comparison uses the same ISO week in each of the five prior calendar years, and is empty unless all five exist, as in the original's fallback. |
| `STORAGE_TOTAL`, `STORAGE_WEEK`, `STORAGE_REGIONS`, `STORAGE_NOTE`, `STORAGE_HISTORY_SHEET`, `STORAGE_CHANGES_SHEET` | labels | The EIA workbooks' own column and sheet labels; columns are found by label, never by position. |

## `root/pin.py` (section G: the outside figures on every row)

No number is written into it. Its choices are labels: `NYMEX_GAS` and `ICE_HENRY_HUB` (the CFTC contract codes of the
original, 023651 and 023391), `FORECAST_FIGURES` (the four forecast figures of `FORECAST_ON_ROW`), and the column
lists `AS_OF` (latest value known at or before the row's received time) and `PER_TRADE_DAY` (on every row of the
trade day, empty on a row of no trade day). The times a value becomes known are the ones declared for
`root/outside.py`.

## `root/tape.py`

| Constant | Value | Why |
|---|---|---|
| `BUILT_TRADE_DAYS` | Oct 2, 3, 17, 18, 2023 | The only trade days whose ticks may enter a calculation (Greg: none of the hours outside the four trade days are used in calculations). |
| `CLEAR` | R | The tape's action code for a clear. |
| `TICK`, `VENDOR_SNAPSHOT` | labels | What a record is. |

## `root/store.py`

| Constant | Value | Why |
|---|---|---|
| `ROWS_PER_PART` | 2^18 | Rows per stored part file, so every file stays far below GitHub's 100 MB file limit. Storage only; no row is dropped or merged. |
| `PICTURE_ROWS_PER_PART` | 2^22 | Book-picture rows per stored part file. Storage only. |
| `ZSTD_LEVEL` | 9 | Compression of the stored files; the content is unchanged. |

## `root/checks.py`

| Constant | Value | Why |
|---|---|---|
| `HALVE` | 2 | The playback check cuts the tape inside an exchange event at the middle trade message that does not end its event. It only chooses where a check cuts; no row or figure depends on it. |

## `root/run.py`

| Constant | Value | Why |
|---|---|---|
| `BYTES_PER_MEGABYTE` | 2^20 | Unit conversion for the sizes printed after a build. |

## Functions whose numbers are calendar facts

- `us_federal_holidays`, `nth`, `observed`: the dates of the US federal holidays (months, days, which Monday or
  Thursday), used only by the positioning release rule.
- `to_ns`: seconds in a day, nanoseconds in a microsecond, and the 1970 epoch.
