# DavisAI Markets: Six Data and Signal Workstreams for a Henry Hub Analog-Retrieval Desk

**Engineering research paper and implementation handoff**

Prepared for Greg Davis and the DavisAI Markets engineering workflow  
Date: August 5, 2026

## Scope and evidence protocol

This paper completes the six requested workstreams for the Henry Hub natural gas desk. It is written as an implementation handoff, not as a general market-data survey.

Every material statement is assigned one of three evidence states:

- **FOUND:** supported by a surviving DavisAI artifact, an official public source, or a reproducible specification stated here.
- **SEARCHED AND FOUND NOTHING:** the requested fact was actively sought but no defensible public or surviving internal record was found.
- **PROPOSED:** an engineering construction supplied to close a gap. A proposal is not presented as a measured historical result.

Predictive claims name their benchmark. Every proposed mechanism includes a falsification test. Results are evaluated per regime, season, horizon, and data-quality cell rather than only as a pooled average.

The desk's governing frame is preserved: the product is an intraday price curve; analog retrieval renders behavior already reasoned from projected conditions; amplitude is a rejection test; slope is the scrap signal; and the adjustment loop is the product.


# Contents

1. Executive summary
2. Task 1 - Order-flow direction nowcast
3. Task 2 - ECMWF ENS and NOAA GEFS member retrieval
4. Task 3 - ISO day-ahead and multi-day load, wind, and solar forecasts
5. Task 4 - Gas-weighted degree days and a summer replacement
6. Task 5 - North American weather regime label
7. Task 6 - LNG feedgas nomination sources
8. Integrated build sequence
9. Acceptance matrix
10. Public source appendix
11. Evidence limitations

# Executive summary

## Decision table

| Workstream | Answer | Build decision |
|---|---|---|
| 1. Order-flow direction | **FOUND.** The direction result existed. The recovered ChatGPT study was a limited strong-flow running-leg nowcast, approximately 94 percent in a roughly 12 warm-season-day study. The desk then recorded a monotone strength relationship and 34 of 34 qualifying legs on three unseen days. The exact original ChatGPT audit package did not survive. | Freeze the desk's Lee-Ready implementation as the canonical candidate. Re-run it causally on the real tape against persistence and slope baselines before granting execution authority. Do not use it as a from-flat forecast. |
| 2. ECMWF ENS and GEFS | **FOUND.** Both ensembles are publicly retrievable at member level. ECMWF Open Data uses the `enfo` perturbed-member stream and NOAA publishes GEFS control plus 30 perturbations. | Begin immutable cycle archival immediately. Public rolling services are delivery systems, not guaranteed permanent historical archives. |
| 3. Forward net load | **FOUND, uneven by ISO.** ERCOT and SPP provide the cleanest seven-day load, wind, and solar families. CAISO, PJM, MISO, and ISO-NE require different products and access patterns. EIA-930 supplies next-day load forecasts for Southeast balancing authorities but not forward wind or solar. | Build one normalized forecast-vintage schema with ISO-specific adapters. Never mix issue vintages. Treat EIA-930 Southeast data as load-only fallback, not forward net load. |
| 4. Degree days | **FOUND.** Standard gas-weighted HDD is fundamentally a residential/commercial heating construction. Using it unchanged as a summer CDD instrument mis-specifies the causal demand channel. | Retain gas-heating weights for HDD. Replace summer weights with a balancing-authority gas-generation response construction using EIA-930, with population CDD as the benchmark. |
| 5. Weather regimes | **FOUND.** Pacific Trough, Pacific Ridge, Alaskan Ridge, Greenland High, and No Regime can be reproduced from daily 500 hPa height anomalies using a published PC and k-means recipe. | Use the label as a low-dimensional retrieval key and dispersion descriptor. No published evidence was found that the label itself predicts Henry Hub prices. |
| 6. LNG feedgas nominations | **FOUND, operationally fragile.** The terminal pipelines expose scheduled quantities or operationally available capacity through public EBBs, but interfaces and semantics differ. | Build a supervised adapter fleet with per-pipeline parsers, cycle snapshots, schema tests, and manual exception handling. Do not build one universal scraper. |

## Highest-value conclusions

1. The flow result should not be discarded because the original ChatGPT notebook is missing. The correct response is to distinguish the existence of the result from the completeness of its audit trail.
2. Archival is the immediate dependency across Tasks 2, 3, 5, and 6. Forecast cycles and nomination cycles are revised or aged out; waiting destroys the exact historical object needed for causal replay.
3. The June 29 sign-flip failure is addressed by forward net load, not by another weather model. Load, wind, and solar must share the same issue vintage.
4. A heating-derived weight cannot be assumed to measure summer gas sensitivity. Power-sector gas burn must determine the summer weights.
5. Weather regimes solve a dimension problem, not a direct alpha problem. Their first benchmark is analog retrieval with season-only or continuous-PC matching, not price direction accuracy in isolation.
6. LNG nominations are worth building only with explicit health states. A parser that silently returns zero after a site redesign is more dangerous than a missing feed.


# Task 1 - Order-flow direction nowcast

## Bottom line

**FOUND:** ChatGPT did independently establish a direction relationship in an earlier conversation. The surviving description is approximately 94 percent agreement for strong-flow observations in a limited sample covering roughly 12 warm-season days. The target was the side or continuation of a running leg. It was not a direction forecast made from a flat, pre-session state.

**FOUND:** The desk's later implementation is better documented: signed buy-minus-sell order-flow imbalance, called `dip_imb_level`, becomes eligible at absolute imbalance at least 0.15. Agreement increased monotonically across strength cells as 0.68, 0.84, 0.94, and 0.93, and the desk recorded 34 of 34 qualifying observations on three unseen days. Its known failure is lag on an extreme gap melt-up.

**SEARCHED AND FOUND NOTHING:** The exact original ChatGPT formula version, aggregation window, instrument/date list, qualifying-event count, strength-bin boundaries, and null-test output did not survive in the accessible conversation artifacts. They must not be invented.

The result therefore exists, but the original audit package is incomplete. The implementation below is a canonical reconstruction to make the play reproducible going forward. It is labeled **PROPOSED**, except where it repeats the desk's documented threshold or result.

## Recovered evidence ledger

| Field requested | Evidence state | Recoverable answer |
|---|---|---|
| Existence of ChatGPT direction result | FOUND | Yes. Strong signed flow was associated with the side of a newly forming or running NG leg at about 94 percent in a limited warm-season study. |
| Forecast type | FOUND | Running-leg nowcast or continuation classifier, not a from-flat direction forecast. |
| Desk production name | FOUND | `dip_imb_level`, routed to `flow_nowcast`. |
| Desk threshold | FOUND | Absolute imbalance at least 0.15. |
| Desk measured split | FOUND | 0.68, 0.84, 0.94, 0.93 by increasing strength cell; exact original bin edges are not in the surviving brief. |
| Desk out-of-sample result | FOUND | 34 of 34 qualifying observations on three unseen days. |
| Known weakness | FOUND | Lags an extreme gap melt-up. |
| Original ChatGPT exact window and sample count | SEARCHED AND FOUND NOTHING | Not recoverable from the surviving record. |
| Original ChatGPT null/control | SEARCHED AND FOUND NOTHING | Not recoverable from the surviving record. |

## Canonical v0.1 construction

### Input record

Use the active Henry Hub NG futures contract selected by a versioned leader-contract rule. Required event fields are:

```text
instrument_id
raw_symbol
contract_month
ts_event
ts_recv
trade_price
trade_size
best_bid_before_trade
best_ask_before_trade
native_aggressor_side, if supplied
sequence or event identifier
source_schema and source_version
```

The historical source can be Databento trades plus MBP-1, MBP-10, or MBO. MBO is preferred for deterministic event ordering and book reconstruction. The feature must be computed from exchange-event order, with receipt time retained for latency and causal-availability audits.

### Aggressor classification

Use native aggressor side when the source supplies a documented exchange-derived side. Otherwise use the Lee-Ready quote rule followed by the tick rule:

```text
mid_i = (bid_i + ask_i) / 2

if trade_price_i > mid_i: s_i = +1
if trade_price_i < mid_i: s_i = -1
if trade_price_i == mid_i and trade_price_i > previous_distinct_trade_price: s_i = +1
if trade_price_i == mid_i and trade_price_i < previous_distinct_trade_price: s_i = -1
if trade_price_i == mid_i and trade_price_i == previous_trade_price:
    inherit the last nonzero tick-test sign inside the same uninterrupted price sequence
```

Classifications are invalid when the quote is crossed, locked without a deterministic tie rule, stale beyond the configured quote-age limit, or missing. Invalid trades remain in the raw journal but are excluded from the signed numerator and reported in the quality denominator.

### Imbalance formula

For a causal window containing trades `i = 1...n`:

```text
buy_volume  = sum(q_i for s_i = +1)
sell_volume = sum(q_i for s_i = -1)
classified_volume = buy_volume + sell_volume

dip_imb_level = (buy_volume - sell_volume) / classified_volume
```

The range is -1 to +1. Positive values are buyer-aggressor dominant; negative values are seller-aggressor dominant.

### Window and leg scope

The original ChatGPT window is not recoverable. The canonical production candidate should be **current-leg cumulative**, because the surviving claim is explicitly a running-leg result.

A causal leg can be declared from a one-second midprice stream using a no-look-ahead ZigZag:

```text
theta_t = max(0.005 dollars per MMBtu,
              3 * median(abs(one_second_price_change)) over the prior 300 seconds)

A candidate up leg begins when price rises theta_t from the last confirmed pivot.
A candidate down leg begins when price falls theta_t from the last confirmed pivot.
The running extreme is updated only with information available at time t.
The leg ends when price retraces theta_t from the running extreme.
```

The feature window begins at the causal leg declaration time, not at the later research pivot. This avoids using the future extreme that eventually defines a visually obvious leg.

Run rolling 30-second, 60-second, and 120-second variants only as challengers. Do not average them into the canonical signal.

### Eligibility and output

Documented threshold:

```text
eligible when abs(dip_imb_level) >= 0.15
call = LONG if dip_imb_level >= 0.15
call = SHORT if dip_imb_level <= -0.15
```

Proposed quality gates for the first causal replay, to be tuned only on a training partition:

```text
classified_trade_count >= 50
classified_volume >= 100 contracts
classified_volume / total_trade_volume >= 0.90
quote_stale_fraction <= 0.02
no unresolved feed gap in the feature window
```

These gates are **PROPOSED engineering defaults**, not recovered historical parameters.

The output contract should be:

```text
feature_name: dip_imb_level
feature_version
value
side: BUY | SELL | NONE
strength_cell
leg_id
leg_direction_at_trigger
trigger_ts_event
window_start_ts_event
classified_trade_count
classified_volume
unclassified_volume
quality_state
call_type: RUNNING_LEG_NOWCAST
invalidations[]
```

## Outcome definition and benchmarks

A running-leg classifier can look impressive merely because the leg is already moving. The primary benchmark is therefore not a coin flip alone.

Primary outcome:

```text
continuation_return = price_at_causal_leg_end - price_at_trigger
correct = sign(continuation_return) == sign(dip_imb_level)
```

Secondary fixed-horizon outcomes are 10 seconds, 30 seconds, 60 seconds, and 300 seconds after the trigger, marked to bid/ask executable prices as well as mid.

Required benchmarks:

1. Current causal leg direction at trigger.
2. Sign of the prior 30-second price slope.
3. Last nonzero trade-sign majority.
4. Unconditional majority side per session cell.
5. Random 50/50 sign.

The play is useful only if it adds incremental skill or economic value over current-leg direction and short-horizon slope. Beating 50 percent while failing to beat persistence is not an edge.

## Null and control suite

The original ChatGPT null is unavailable. The canonical replication must include:

1. **Within-session sign permutation:** shuffle aggressor signs while preserving timestamps, sizes, prices, and session structure.
2. **Within-leg circular shift:** rotate signed-flow sequence relative to price inside each leg.
3. **Magnitude-preserving sign flip:** randomly flip complete-leg signs to preserve within-leg autocorrelation.
4. **Window placebo:** compute the same imbalance from the prior completed window rather than the active leg.
5. **Classifier control:** compare native side, Lee-Ready, quote-only, and tick-only classifications.
6. **Segmentation control:** compare causal legs with research legs. Any large performance gap is evidence of look-ahead leakage.
7. **From-flat control:** evaluate the signal at session open separately. It must not inherit the running-leg claim.

## Strength cells

The exact historical bin edges behind 0.68, 0.84, 0.94, and 0.93 were not recovered. Preserve the measured sequence as historical metadata and re-estimate bins prospectively. A proposed first pass is:

```text
0.15 <= abs(I) < 0.25
0.25 <= abs(I) < 0.40
0.40 <= abs(I) < 0.60
0.60 <= abs(I) <= 1.00
```

Report count, hit rate, Wilson interval, average executable markout, adverse excursion, and session coverage in every cell. Do not pool long and short, gap and non-gap, storage and non-storage, or warm and cold seasons until cell behavior is shown.

## Falsification first

The mechanism is killed or quarantined if any of the following occurs:

- It does not beat current-leg direction or short-horizon slope on unseen sessions.
- Performance depends on research leg boundaries that use future extremes.
- Lee-Ready and native aggressor classifications disagree enough to reverse the call in qualifying cells.
- The 34-of-34 forward record fails to reproduce from immutable raw events and the frozen feature version.
- Net performance after spread, fees, latency, and adverse selection is not positive in the venue where it is used.
- Gap sessions or catalyst cells produce systematic opposite-signed continuation.

## Authority recommendation

Treat `flow_nowcast` as **ESTABLISHED RESEARCH, REPLICATION REQUIRED**, not as discarded evidence and not yet as unrestricted automatic authority.

Permitted use before replication:

- live telemetry;
- challenger direction lane;
- veto or downgrade of a conflicting fundamental narrative;
- timing assistance after a leg is causally established.

Prohibited use before replication: from-flat open direction, retrospective leg labeling, and automatic position opening based only on the historical 34-of-34 record. The historical 94 percent cell must not be presented as a guaranteed future probability.


# Task 2 - ECMWF ENS and NOAA GEFS member retrieval

## Bottom line

**FOUND:** An engineer can retrieve individual perturbed members from both systems without buying a vendor feed.

- ECMWF IFS ENS Open Data publishes GRIB2 files through `data.ecmwf.int` and the public AWS bucket `ecmwf-forecasts`. After IFS cycle 50r1, the `enfo/ef` files contain 50 perturbed members. The control is obtained separately from `oper/fc`. Older mirrored runs can contain the control plus 50 perturbations in the ensemble file.
- NOAA GEFS publishes one control member, `c00`, and 30 perturbations, `p01` through `p30`, through NOMADS and `noaa-gefs-pds`.
- Both use 2-meter temperature in Kelvin. ECMWF parameter notation is `2t`; NOAA GRIB inventory notation is `TMP:2 m above ground`.

**Build decision:** begin immutable archival now. Public delivery endpoints are not a contractual historical forecast archive.

## ECMWF IFS ENS

### Direct route and object pattern

Root:

```text
https://data.ecmwf.int/forecasts/
```

Physical-file pattern:

```text
https://data.ecmwf.int/forecasts/{YYYYMMDD}/{HH}z/ifs/0p25/enfo/
{YYYYMMDD}{HH}0000-{STEP}h-enfo-ef.grib2
```

Example:

```text
https://data.ecmwf.int/forecasts/20260805/00z/ifs/0p25/enfo/
20260805000000-24h-enfo-ef.grib2
```

The adjacent index is normally the same object name with `.index` appended. Use the directory listing or index to avoid downloading unwanted fields.

### AWS Open Data mirror

Bucket and region:

```text
bucket: ecmwf-forecasts
region: eu-central-1
access: anonymous unsigned S3
```

Key pattern:

```text
s3://ecmwf-forecasts/{YYYYMMDD}/{HH}z/ifs/0p25/enfo/
{YYYYMMDD}{HH}0000-{STEP}h-enfo-ef.grib2
```

HTTPS form:

```text
https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com/{KEY}
```

### Members, run times, horizon, and cadence

| Item | Current open-data behavior |
|---|---|
| Perturbed members | 50 members after IFS 50r1, numbered 1 through 50 in GRIB metadata. |
| Control | Retrieve separately from `stream=oper`, `type=fc` after 50r1. Do not assume member 0 is embedded in current `enfo/ef`. |
| Cycles | 00, 06, 12, and 18 UTC are published. |
| Full 15-day leg | 00 and 12 UTC ENS. Steps are 3-hourly through 144 hours and 6-hourly thereafter through 360 hours in the open catalogue. |
| Intermediate cycles | 06 and 18 UTC are shorter in the open catalogue; do not assume a 360-hour leg. |
| File format | GRIB2, with index sidecars. |
| Public lag | The maintained client documentation advises that complete cycle availability can be roughly 7 to 9 hours after nominal run time. Measure actual object arrival and completeness rather than hard-coding one lag. |

### Temperature field

```text
ECMWF shortName: 2t
long name: 2 metre temperature
units: K
level: heightAboveGround, 2 m
```

### Maintained Python client

Package:

```text
pip install ecmwf-opendata xarray cfgrib eccodes
```

Minimal retrieval of ten perturbed members for a run and forecast step:

```python
from ecmwf.opendata import Client

client = Client(source="aws", model="ifs", resol="0p25")
client.retrieve(
    date="2026-08-05",
    time=0,
    stream="enfo",
    type="pf",
    number=list(range(1, 11)),
    step=[24],
    param="2t",
    target="ecmwf_ens_2t_members_01_10_f024.grib2",
)
```

Important semantic distinction:

- The client request uses `type="pf"` for perturbed forecasts and member numbers.
- The physical public file is named with `type=ef` in the `enfo` directory.

Read the result:

```python
import xarray as xr

ds = xr.open_dataset(
    "ecmwf_ens_2t_members_01_10_f024.grib2",
    engine="cfgrib",
    filter_by_keys={"shortName": "2t"},
)
# Convert only at the analysis edge; preserve source Kelvin in the raw layer.
ds["t2m_f"] = (ds["t2m"] - 273.15) * 9.0 / 5.0 + 32.0
```

Retrieve the deterministic control after 50r1:

```python
client.retrieve(
    date="2026-08-05",
    time=0,
    stream="oper",
    type="fc",
    step=[24],
    param="2t",
    target="ecmwf_control_2t_f024.grib2",
)
```

### License and attribution

ECMWF Open Data is licensed under Creative Commons Attribution 4.0. Preserve source, product, cycle, model version when available, and attribution to ECMWF in derived products.

Official source pages:

- https://confluence.ecmwf.int/display/DAC/ECMWF+open+data%3A+real-time+forecasts+from+IFS+and+AIFS
- https://github.com/ecmwf/ecmwf-opendata
- https://registry.opendata.aws/ecmwf-forecasts/

### Historical availability

**FOUND:** Dated objects can be present in the AWS mirror and direct service for recent cycles.

**SEARCHED AND FOUND NOTHING:** No public guarantee was found that either service is a permanent, complete archive of every past operational cycle and member. The engineer should treat historical retention as opportunistic.

Required action:

```text
Archive every accepted cycle, its index, object listing, arrival timestamps,
model/cycle metadata, and checksum into the desk's own immutable store.
```

## NOAA GEFS

### Membership

```text
control: c00
perturbed: p01 through p30
ensemble size: 31
```

### NOMADS paths

0.25-degree pressure/surface GRIB2 directory through the high-resolution leg:

```text
https://nomads.ncep.noaa.gov/pub/data/nccf/com/gens/prod/
gefs.{YYYYMMDD}/{HH}/atmos/pgrb2sp25/
```

Typical member file:

```text
gep01.t00z.pgrb2s.0p25.f024
```

Control file:

```text
gec00.t00z.pgrb2s.0p25.f024
```

Index sidecar:

```text
gep01.t00z.pgrb2s.0p25.f024.idx
```

The 0.5-degree extended products use the `pgrb2ap5` and `pgrb2bp5` directories. Inspect the cycle directory because NOAA may separate field groups and forecast legs.

### AWS Open Data mirror

Bucket:

```text
s3://noaa-gefs-pds
```

0.25-degree key pattern:

```text
gefs.{YYYYMMDD}/{HH}/atmos/pgrb2sp25/
{gec00|gep01...gep30}.t{HH}z.pgrb2s.0p25.f{FFF}
```

Example:

```text
s3://noaa-gefs-pds/gefs.20260805/00/atmos/pgrb2sp25/
gep01.t00z.pgrb2s.0p25.f024
```

### Runs, horizon, and format

| Item | GEFS behavior |
|---|---|
| Cycles | 00, 06, 12, and 18 UTC. |
| Members | Control plus 30 perturbations. |
| 0.25-degree leg | Files are available through approximately forecast hour 240. |
| Standard extended leg | 0.5-degree products extend through forecast hour 384. |
| Longer 00 UTC leg | The 00 UTC extended system can publish through forecast hour 840 in the 0.5-degree product family. Confirm member and step availability from the cycle manifest before ingestion. |
| File format | GRIB2 plus text `.idx` inventories. |
| Guaranteed public lag | SEARCHED AND FOUND NOTHING. Poll for the complete expected member-step manifest and record actual arrival times. |

### Temperature field

```text
wgrib inventory name: TMP
level text: 2 m above ground
units: K
common ecCodes shortName: 2t
```

### Minimal ten-member AWS retrieval

Full-file retrieval with the maintained AWS SDK:

```python
from pathlib import Path
import boto3
from botocore import UNSIGNED
from botocore.config import Config

bucket = "noaa-gefs-pds"
date = "20260805"
cycle = "00"
fhr = 24
out = Path("gefs_2t")
out.mkdir(exist_ok=True)

s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))

for member in range(1, 11):
    stem = f"gep{member:02d}.t{cycle}z.pgrb2s.0p25.f{fhr:03d}"
    key = f"gefs.{date}/{cycle}/atmos/pgrb2sp25/{stem}"
    s3.download_file(bucket, key, str(out / stem))
```

For operational use, range-request only the 2-meter temperature message using the `.idx` file:

```python
import requests


def inventory_ranges(idx_text, needle=":TMP:2 m above ground:"):
    rows = []
    for line in idx_text.strip().splitlines():
        parts = line.split(":", 3)
        rows.append((int(parts[1]), line))
    matches = []
    for j, (start, line) in enumerate(rows):
        if needle in line:
            end = rows[j + 1][0] - 1 if j + 1 < len(rows) else None
            matches.append((start, end, line))
    return matches

base = (
    "https://noaa-gefs-pds.s3.amazonaws.com/"
    "gefs.20260805/00/atmos/pgrb2sp25/"
    "gep01.t00z.pgrb2s.0p25.f024"
)
idx = requests.get(base + ".idx", timeout=30).text
start, end, descriptor = inventory_ranges(idx)[0]
headers = {"Range": f"bytes={start}-{end}"} if end else {"Range": f"bytes={start}-"}
grib_message = requests.get(base, headers=headers, timeout=60).content
open("gep01_2t_f024.grib2", "wb").write(grib_message)
```

A community-maintained convenience client is Herbie. NOAA does not publish a GEFS-specific Python client that replaces the official NOMADS or AWS object contract. Keep the generic object adapter as the production dependency and treat Herbie as a development convenience.

### License

NOAA/NWS data are United States government works and generally public domain. Preserve NOAA, NCEP, model, cycle, and product attribution and follow the service's access policies.

Official sources:

- https://nomads.ncep.noaa.gov/
- https://www.nco.ncep.noaa.gov/pmb/products/gens/
- https://registry.opendata.aws/noaa-gefs/
- https://noaa-gefs-pds.s3.amazonaws.com/index.html

### Historical availability

**FOUND:** The AWS bucket is date-partitioned and is the practical public source for older operational runs.

**SEARCHED AND FOUND NOTHING:** A contractual permanent-retention guarantee covering every cycle, member, field, and extended step was not found. Archive the exact raw objects and index files used in each decision.

## Unified archive contract

Store one manifest row per member-step-field object:

```text
provider
model
model_version_if_known
cycle_time_utc
forecast_step_hours
member_type: CONTROL | PERTURBED
member_number
parameter_source_name
parameter_canonical_name
units
source_uri
source_etag
source_size
first_seen_utc
complete_seen_utc
downloaded_utc
sha256
license
parser_version
quality_state
```

A cycle is `READY` only when the expected member-step manifest is complete. Partial cycles must remain queryable but cannot silently masquerade as a full distribution.

## Falsification and acceptance

This workstream is data infrastructure, so the relevant falsifier is not price MAE.

The adapter fails acceptance if:

- ten requested members cannot be retrieved for an explicit cycle and step;
- control and perturbed members are mixed or double-counted after ECMWF 50r1;
- a partial cycle is treated as a full distribution;
- Kelvin and Fahrenheit are mixed in the raw layer;
- re-downloading the same object produces an unexplained checksum change;
- a historical replay cannot identify the exact forecast object available at decision time.


# Task 3 - ISO day-ahead and multi-day load, wind, and solar forecasts

## Bottom line

**FOUND:** Free forward load, wind, and solar data exist, but there is no uniform North American endpoint. ERCOT and SPP expose the cleanest complete seven-day families. CAISO, PJM, MISO, and ISO-NE require different report combinations. The correct architecture is a normalized forecast-vintage model with one adapter per source.

**FOUND:** EIA-930 reports next-day demand forecasts for Southeast balancing authorities including Southern Company, TVA, Duke balancing areas, and FPL. It does not provide forward wind and solar forecasts for those non-ISO regions. It is therefore a load-only fallback, not a complete forward net-load source.

## Canonical net-load object

For region `r`, hour `h`, and issue vintage `v`:

```text
forward_net_load[r,h,v] = load_forecast[r,h,v]
                          - wind_forecast[r,h,v]
                          - solar_forecast[r,h,v]
```

All three terms must use the same or causally compatible issue vintage. Never combine today's revised load forecast with yesterday's wind forecast in a historical replay.

Required canonical fields:

```text
operator
report_or_endpoint
forecast_issue_time_utc
source_publish_time_utc
source_received_time_utc
forecast_interval_start_utc
forecast_interval_end_utc
local_timezone
region_type
region_id
variable: LOAD | WIND | SOLAR | NET_LOAD
value_mw
quantile_or_model_if_present
is_behind_the_meter_component
is_potential_or_available_capacity
is_imputed
source_revision
source_uri
raw_checksum
parser_version
quality_state
```

## ERCOT

The families named in the task are correct.

| Variable | Data product | Report Type ID | Horizon and granularity | Access |
|---|---|---:|---|---|
| Wind | `NP4-742-CD`, Wind Power Production - Hourly Averaged Actual and Forecasted Values | 14787 | Hourly, approximately 168 hours | Public download; CSV/XML/ZIP through ERCOT MIS and API products. |
| Solar | `NP4-745-CD`, Solar Power Production - Hourly Averaged Actual and Forecasted Values | 21809 | Hourly, approximately 168 hours | Public. |
| Load, current operational forecast | `NP3-561-CD`, Seven-Day Load Forecast | 12312 | Hourly, current day plus six following days | Public. |
| Load, model set | `NP3-565-CD`, Seven-Day Load Forecast by Model | 14837 | Hourly, approximately seven days, multiple model vintages | Public. |

Product pages:

```text
https://www.ercot.com/mp/data-products/data-product-details?id=NP4-742-CD
https://www.ercot.com/mp/data-products/data-product-details?id=NP4-745-CD
https://www.ercot.com/mp/data-products/data-product-details?id=NP3-561-CD
https://www.ercot.com/mp/data-products/data-product-details?id=NP3-565-CD
```

Registration:

- Public report downloads do not require a paid subscription.
- The ERCOT Developer Portal can require a free account and product subscription for stable API access.

`gridstatus`:

- Wrapped. Use `gridstatus.ERCOT` for discovery and development, but retain the ERCOT product ID and raw file in production lineage.

Quality traps:

1. The wind and solar products include forecasted production and High Sustained Limit or available capability concepts. Do not substitute potential capability for expected generation.
2. Forecasts are revised. Preserve every issue vintage.
3. Daylight-saving transitions and ERCOT local timestamps require explicit interval boundaries.
4. SEARCHED AND FOUND NOTHING: a durable statement that every solar field includes or excludes all behind-the-meter PV. Treat BTM scope as unknown unless the exact column documentation says otherwise.

## SPP

| Variable | Public report family | Horizon | Granularity |
|---|---|---|---|
| Load | Mid-Term Load Forecast versus Actual | Seven days | Hourly |
| Wind and solar | Mid-Term Resource Forecast | Seven days | Hourly |
| Wind and solar by reserve zone | Resource Forecast by Reserve Zone | Approximately 168 hours | Hourly |

Portal:

```text
https://portal.spp.org/
```

Report pages are exposed under the portal's file-browser families, including `mid-term-load-forecast`, `midterm-resource-forecast`, and reserve-zone resource forecasts. The portal's observed download service uses paths under:

```text
https://portal.spp.org/file-browser-api/download/
```

**Evidence label:** the file-browser API is an observed public endpoint, not a published long-term interface contract. Discover filenames from the official portal listing rather than fabricating dates.

Registration:

- No paid registration is required for public portal files.

`gridstatus`:

- Wrapped for SPP load and renewable forecast reports.

Quality traps:

1. Resource forecast can represent expected production or available capability depending on report column. Parse by documented field name.
2. Reserve-zone totals and system totals can overlap; do not sum both.
3. SEARCHED AND FOUND NOTHING: definitive BTM solar inclusion and a published imputation method for every report.

## CAISO

### Seven-day public outlook

CAISO Today's Outlook publishes demand and net-demand views extending from day ahead through approximately seven days, with morning updates.

```text
https://www.caiso.com/todays-outlook
```

CAISO defines net demand as demand minus wind and solar generation in the outlook. The public visualization is useful for operations, but an engineer should preserve the downloaded backing data and publication timestamp rather than scrape chart pixels.

### OASIS day-ahead renewable forecast

Example OASIS SingleZip request:

```text
http://oasis.caiso.com/oasisapi/SingleZip?
queryname=SLD_REN_FCST&market_run_id=DAM&
startdatetime={YYYYMMDDTHH:MM-0000}&
enddatetime={YYYYMMDDTHH:MM-0000}&version=1&resultformat=6
```

EDAM grouped renewable forecast reports can be requested through GroupZip using the relevant published group ID, including wind and solar forecast groups.

Registration:

- OASIS public reports do not require an API key.

`gridstatus`:

- Wrapped for several CAISO load and renewable forecast products.

Quality traps:

1. OASIS day-ahead market forecast and the seven-day operational outlook are different products and vintages.
2. CAISO net demand excludes utility-scale wind and solar explicitly. Behind-the-meter PV depresses measured demand and may therefore be embedded in the demand term rather than published as a separate solar forecast.
3. Dispatchable pumping and battery charging treatment varies by chart/report definition. Store the source definition with the value.

## PJM

Base API:

```text
https://api.pjm.com/api/v1/
```

Relevant Data Miner feed names:

```text
load_frcstd_7_day
load_frcstd_hist
hourly_wind_power_forecast
hourly_solar_power_forecast
five_min_wind_power_forecast
five_min_solar_power_forecast
```

Data Miner documentation and registration:

```text
https://dataminer2.pjm.com/
https://www.pjm.com/markets-and-operations/etools/data-miner-2
```

Horizon and granularity:

- Load: seven-day hourly forecast.
- Wind and solar: hourly forward forecasts plus five-minute near-term forecast feeds.

Registration:

- A free API account and subscription key are required for API use.
- Rate limits apply. PJM's terms distinguish internal use from redistribution; preserve the terms version with the adapter.

`gridstatus`:

- Wrapped for core PJM forecast feeds.

Quality traps:

1. PJM has separate utility-scale and behind-the-meter solar concepts. Do not subtract BTM PV twice if the load forecast already embeds it.
2. The five-minute feed is not a seven-day substitute.
3. Forecast areas, zones, and RTO totals are not additive in every combination.
4. API revision timestamps and duplicate rows must be versioned, not overwritten.

## MISO

### Public renewable APIs

```text
https://public-api.misoenergy.org/api/WindSolar/getwindforecast
https://public-api.misoenergy.org/api/WindSolar/getsolarforecast
```

These endpoints expose day-ahead wind and solar forecasts through the public Data Exchange service.

### Load and longer outlook files

Day-ahead forecasted load file pattern:

```text
https://docs.misoenergy.org/marketreports/{YYYYMMDD}_df_al.xls
```

Medium-Term or Multi-Day Operating Margin file pattern:

```text
https://docs.misoenergy.org/marketreports/{YYYYMMDD}_mom.xlsx
```

The operating-margin workbook is the practical public multi-day source for load, wind, solar, capacity, and reserve context. Inspect sheet names and issue time because the workbook schema can change.

Registration:

- Public report files are free.
- Stable use of the newer public APIs can require a free MISO Data Exchange profile or key.

`gridstatus`:

- Partial support. Direct source adapters are still required for the exact MISO workbooks and APIs.

Quality traps:

1. Day-ahead market forecast and operating-margin outlook are separate vintages.
2. Wind and solar can appear as forecast, available capacity, or accredited capacity. Use only forecast MW for net load.
3. SEARCHED AND FOUND NOTHING: a stable public definition of BTM solar coverage across all MISO forecast products.

## ISO New England

Web Services API:

```text
https://webservices.iso-ne.com/api/v1.1/sevendayforecast/current
https://webservices.iso-ne.com/api/v1.1/sevendaywindpowerforecast/current
```

Public CSV transform routes:

```text
https://www.iso-ne.com/transform/csv/wphf?start={YYYYMMDD}
https://www.iso-ne.com/transform/csv/sphf?start={YYYYMMDD}
```

Products:

- Seven-Day Forecast: hourly system load.
- Seven-Day Wind Power Forecast: hourly.
- Seven-Day Solar Power Forecast: hourly.

Registration:

- CSV reports are publicly downloadable.
- Web Services uses a free ISO-NE account with Basic Authentication.

`gridstatus`:

- Wrapped for several ISO-NE forecasts.

Quality traps:

1. Solar forecast scope can include BTM PV estimates that are reflected in net load. Preserve the exact report definition and avoid double subtraction.
2. Publication is generally daily, but revisions and missing intervals occur.
3. ISO-NE timestamps require explicit handling of Eastern Time and daylight-saving folds.

## Non-ISO Southeast through EIA-930

### Answer

**FOUND:** EIA-930 includes the `DF` day-ahead demand forecast series for reporting balancing authorities, including major Southeast BAs. It is hourly next-day load, not wind or solar.

API pattern:

```text
https://api.eia.gov/v2/electricity/rto/region-data/data/?
api_key={EIA_KEY}&frequency=hourly&data[0]=value&
facets[type][]=DF&facets[respondent][]={BA_CODE}&
start={YYYY-MM-DDTHH}&end={YYYY-MM-DDTHH}
```

Relevant BA codes include:

```text
SOCO  Southern Company
TVA   Tennessee Valley Authority
DUK   Duke Energy Carolinas
CPLE  Duke Energy Progress East
CPLW  Duke Energy Progress West
FPL   Florida Power and Light
```

Coverage statement:

- EIA publishes what each BA reports for the individual BA series.
- EIA applies estimation or imputation to certain aggregate regional products, not as a reason to treat every BA observation as imputed.
- Individual BA coverage can still contain outages, stale forecasts, revisions, and respondent-specific reporting changes.

What it does not solve:

- no forward wind forecast;
- no forward solar forecast;
- no Southeast-wide common forecast issue time;
- no direct thermal-dispatch conversion.

Therefore:

```text
EIA-930 DF is a load-only fallback.
It must not be labeled forward net load.
```

Official sources:

- https://www.eia.gov/electricity/gridmonitor/
- https://www.eia.gov/opendata/browser/electricity/rto/region-data
- https://www.eia.gov/opendata/documentation.php

## Normalization and vintage rules

1. Store every publication separately. Never overwrite a prior forecast with a later revision.
2. Convert intervals to UTC while retaining original local timestamp, time zone, and daylight-saving flag.
3. Preserve source units and separately store normalized MW.
4. Mark actual, forecast, potential, HSL, and imputed values as different variables.
5. Build net load only when load, wind, and solar are compatible in geography and vintage.
6. Do not fill a missing renewable forecast with realized generation in a historical forecast replay.
7. Record forecast-age at the market decision timestamp.

## Falsification and benchmarks

The proposed forward-net-load feature must be tested against:

1. Load-only forecast.
2. Deterministic weather-only CDD/HDD.
3. Persistence of realized net load from the prior comparable day.
4. Seasonal hourly climatology.

The feature is killed or scoped down if it does not improve out-of-sample BA or ISO gas-generation forecasts over load-only in the relevant season. Evaluate separately for ERCOT, SPP, CAISO, PJM, MISO, ISO-NE, and Southeast BAs. A pooled national improvement cannot rescue a sign error in the largest summer gas-burning cell.


# Task 4 - Gas-weighted degree days and a summer replacement

## Bottom line

**FOUND:** The standard industry gas-weighted HDD construction is based principally on population or households using natural gas for space heating. It is a winter demand instrument.

**FOUND:** Frontier-style methodology uses roughly 120 weather locations, assigns county population to representative stations based on proximity and climate, and applies natural-gas heating shares for HDD. Its summer construction introduces population and power-sector natural-gas use rather than simply reusing winter weights.

**FOUND:** Published research has built separate cold-season residential/commercial gas-consumption weights and hot-season electricity-sector gas-use weights, and reports that spatial weighting matters for natural-gas demand and futures-price relationships.

**Build decision:** keep a heating-weighted HDD. Replace summer CDD with a power-sector response weight estimated from EIA-930 balancing-authority gas generation. The BA construction below is **PROPOSED** but has published precedent in the use of electricity-sector gas weights.

## Published heating construction

For state or weather area `i` in year `y`:

```text
heating_exposure[i,y] = population[i,y] * share_of_households_heating_with_natural_gas[i,y]

heating_weight[i,y] = heating_exposure[i,y] /
                      sum_j heating_exposure[j,y]

GWHDD[t,y] = sum_i heating_weight[i,y] * HDD[i,t]
```

Equivalent household-count form:

```text
heating_weight[i,y] = natural_gas_heated_households[i,y] /
                      total_US_natural_gas_heated_households[y]
```

The source weather point is not necessarily one station per state. Frontier describes an approximately 120-city network. County population is assigned to a representative point using geographic proximity and climate judgment, then aggregated into consuming and producing regions before the national index.

### Population weighting versus gas-consumption weighting

The standard heating construction is not a direct therm-count weight. It is population or household exposure multiplied by fuel choice.

The two diverge most where:

- many households use gas but per-household consumption is low;
- industrial and electric-sector gas use is large but household gas heat is small;
- climate, housing stock, and appliance efficiency differ sharply;
- population has shifted faster than the static station map;
- a large gas-burning power region has weak representation in the weather station set.

Examples of likely divergence cells include warm high-population states, industrial Gulf states, and mixed PJM/MISO areas such as Ohio. The exact ranking must be measured from current Census fuel-use, EIA consumption, and station mapping rather than asserted from intuition.

## Degree-day definition and base temperature

Standard convention:

```text
HDD_65 = max(65 F - daily_mean_temperature, 0)
CDD_65 = max(daily_mean_temperature - 65 F, 0)
```

EIA and many industry products continue to publish 65 F degree days. That makes 65 F the interoperability default, not proof that 65 F is the optimal natural-gas response threshold.

Test a segmented response over base temperatures from 55 F through 75 F, by region and season. The selected base must beat 65 F out of sample on the target variable. Do not optimize it on Henry Hub price alone; first validate against physical gas demand or gas generation.

Official background:

- https://www.eia.gov/energyexplained/units-and-calculators/degree-days.php

## Why the winter index fails in summer

Winter residential and commercial space heat is directly tied to natural-gas heated households. Summer gas demand is dominated by electricity-sector burn after load, wind, solar, nuclear, hydro, coal, imports, outages, and dispatch economics are accounted for.

A state can therefore receive a small winter gas-heating weight while contributing materially to summer gas burn. Reusing winter weights can produce a CDD limb that barely changes sign or points the wrong way, even when the physical dispatch channel changed.

That makes the observed dead summer limb potentially a measurement failure. It is not evidence by itself that cooling demand has no conditional price effect.

## Published summer precedent

Frontier's public methodology distinguishes HDD and CDD weighting and incorporates power-generation natural-gas use in the cooling construction. Published academic work has similarly used electricity-sector natural-gas consumption shares for hot-season degree-day measures rather than winter household fuel shares.

**SEARCHED AND FOUND NOTHING:** a public paper using the exact hourly EIA-930 balancing-authority marginal-response formula below as an industry standard. The construction is therefore labeled **PROPOSED**, with published precedent for the weighting concept.

## Proposed EIA-930 power-weighted CDD

### Step 1 - Weather at balancing-authority scale

Map gridded or station temperature forecasts to each BA using population and load-zone weights. Do not use one airport to represent a multi-state BA.

```text
T_b,h = sum_g weather_weight[b,g] * T_g,h
CDD_b,h(B) = max(T_b,h - B, 0)
```

Use the same weather object for historical actuals and forecasts, with separate issue vintages.

### Step 2 - Physical response target

Use EIA-930 hourly natural-gas net generation:

```text
GASGEN_b,h = reported natural-gas generation MW for BA b and hour h
```

API family:

```text
https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/
```

Preserve BA, fuel type, UTC interval, report status, and revision.

### Step 3 - Estimate marginal cooling response

For BA `b` and warm-season month `m`, fit on a rolling historical window:

```text
GASGEN_b,h = alpha_b,m
             + beta_b,m * CDD_b,h(B)
             + gamma1 * load_forecast_or_actual_b,h
             + gamma2 * wind_b,h
             + gamma3 * solar_b,h
             + gamma4 * nuclear_outage_b,h
             + hour_of_day fixed effects
             + day_of_week fixed effects
             + year or fuel-price controls
             + error_b,h
```

For a forecast feature, all right-hand-side values must be forecast-time legal. For weight estimation, realized history is allowed, but the estimated coefficients must be frozen before the target period.

### Step 4 - Build weights

Marginal-response version, preferred:

```text
raw_weight_b,m = max(beta_b,m, 0)
power_weight_b,m = raw_weight_b,m / sum_j raw_weight_j,m

PWCDD_t = sum_b power_weight_b,m * CDD_b,t
```

Simpler benchmark:

```text
share_weight_b,m = trailing_same_month_gas_generation_b /
                   national_trailing_same_month_gas_generation

PWCDD_share_t = sum_b share_weight_b,m * CDD_b,t
```

The share version is easier but can overweight baseload gas that is not temperature-sensitive. The marginal-response version is the intended production candidate.

### Step 5 - Ohio repair

Ohio must not be represented by omission or by an arbitrary neighboring airport. Map Ohio counties to their serving BA or ISO footprint and a gridded weather field. Common footprints include PJM and MISO, with utility-specific boundaries. Store county-to-BA and grid-to-county maps as versioned data, because both utility territories and reporting conventions can change.

## Measurement tests

### Physical benchmark

Target: hourly or daily BA natural-gas generation.

Compare:

1. Unweighted population CDD.
2. Standard population-weighted CDD.
3. Winter gas-heating-weighted CDD.
4. Power-generation share-weighted CDD.
5. Proposed marginal power-weighted CDD.
6. Forward net load from Task 3.

A summer CDD index should first beat population CDD and heating-weighted CDD on physical gas generation. It should not be promoted merely because it correlates with Henry Hub in one summer.

### Market benchmark

Target: NG futures direction, amplitude, or curve behavior after controlling for forecast revision and what was already priced.

Benchmarks:

- zero price change;
- last-close or persistence;
- raw national CDD revision;
- forward net-load revision;
- season-only analog retrieval.

Report per region, month, net-load regime, and forecast horizon. Price-level skill beyond 5 to 7 days is not expected; revision and dispersion are the valid longer-horizon targets.

## Published measurement evidence

Published work supports the proposition that spatial weighting changes the measured natural-gas demand response and its relationship to futures prices and variance. It does not establish one universal optimal weight for every year or market regime.

Source register:

- Frontier Weather, gas-weighted degree-day methodology: https://www.frontierweather.com/
- EIA degree days: https://www.eia.gov/energyexplained/units-and-calculators/degree-days.php
- EIA-930 open data: https://www.eia.gov/opendata/browser/electricity/rto/fuel-type-data

The exact Frontier methodology document and cited academic paper should be archived with the implementation. If the source URL changes, retain the downloaded document checksum and publication title in the lineage record.

## Falsification first

The proposed summer replacement is killed or scoped down if:

- it does not beat population CDD or heating-weighted CDD on unseen BA gas generation;
- estimated positive CDD response is unstable in sign across adjacent training windows;
- gains disappear after forward wind, solar, load, and outages are included;
- one BA dominates because of reporting artifacts rather than physical burn;
- Ohio inclusion changes the index but not any physical target;
- the optimized base temperature fails to beat 65 F out of sample;
- the feature only works in pooled national data and fails in the major summer gas-burning regions.

## Play reinstatement decision

Do not permanently retire the summer play based on the heating-weighted CDD limb. Reinstate it only as a challenger with the corrected physical instrument. Promotion requires per-cell improvement over forward net load and raw CDD benchmarks, not merely a restored sign.


# Task 5 - North American weather regime label

## Bottom line

**FOUND:** A reproducible year-round four-regime North American classification exists:

1. Pacific Trough.
2. Pacific Ridge.
3. Alaskan Ridge.
4. Greenland High.
5. No Regime when the state is closer to the anomaly origin than to any regime centroid.

**FOUND:** The label can be constructed from daily 500 hPa geopotential-height anomalies over North America and the adjacent Pacific and Atlantic using a 12-PC, four-cluster k-means recipe.

**SEARCHED AND FOUND NOTHING:** published evidence that these labels directly predict Henry Hub natural-gas prices after appropriate market benchmarks. Use the label as a retrieval key, conditional descriptor, and forecast-dispersion object, not as a standalone bullish or bearish signal.

## Regime definitions

The exact anomaly maps must come from the frozen centroid files. The verbal definitions are:

| Regime | 500 hPa pattern | Typical North American implication |
|---|---|---|
| Pacific Trough | Negative height anomaly or trough near the Gulf of Alaska and northeast Pacific, with downstream positive height tendency over central Canada or the continent. | Increased Pacific storm influence and a downstream temperature pattern that depends on trough placement. |
| Pacific Ridge | Positive height anomaly south of the Aleutians or northeast Pacific, with lower heights over Alaska to Greenland or western North America and a downstream ridge toward the eastern United States. | Often separates western and eastern temperature outcomes; not synonymous with one national gas sign. |
| Alaskan Ridge | Strong positive height anomaly over Alaska with a downstream trough toward Hudson Bay or central/eastern North America. | Greater probability of cold delivery into parts of Canada and the United States in cold season. |
| Greenland High | Positive height anomaly over Labrador/Greenland, with lower heights over much of the United States and weak or different northeast-Pacific forcing. | Blocking and slower pattern progression; cold risk depends on season and antecedent air mass. |
| No Regime | The daily anomaly is weak or is closer to the zero-anomaly origin than to any centroid. | Low-confidence or transitional state. This is a real class for retrieval and should not be forced into one of four labels. |

A No Regime class is standard in this specific framework, not universal across all weather-regime literature. Some systems force every day into a cluster. The desk should not mix taxonomies.

## Reproducible recipe

### Field and domain

```text
field: daily mean 500 hPa geopotential height
source: ERA5 for training; operational GEFS or ECMWF for forecasts
domain: 20 N to 80 N, 180 W to 30 W
training grid: approximately 1.5 degree in the published study
operational grid: 1.0 degree is acceptable when projected through the archived training basis
```

### Preprocessing

1. Build a calendar-day climatology and smooth it with a 60-day running window.
2. Subtract the smoothed climatology from each daily field.
3. Apply a 10-day low-pass or running mean to isolate persistent regimes.
4. Remove the domain-mean long-term height trend, approximately 5.9 to 6.0 meters per decade in the published implementation.
5. Normalize by a seasonally varying domain-average variance, smoothed over approximately 60 days.
6. Apply square-root cosine-latitude area weighting.

### Dimension reduction

```text
EOF/PCA input: preprocessed daily anomaly fields
PC count: 12
variance retained: approximately 80 percent
PC scaling: preserve published non-unit standardization and archived EOF normalization
```

Do not refit PCs on each new year. Freeze the training climatology, trend, EOFs, centroids, and normalization as a versioned regime definition.

### Clustering

```text
algorithm: k-means
k: 4
initializations: at least 500
selection: minimum within-cluster sum of squares
```

### Assignment

Project a new field into the frozen 12-PC space. Compute Euclidean distance to each centroid and to the origin.

```text
if distance_to_origin < minimum_distance_to_any_centroid:
    label = NO_REGIME
else:
    label = nearest_centroid
```

Store the distance vector, not only the winning label. The Weather Regime Index or normalized centroid similarity is useful as a continuous confidence measure and avoids treating a marginal assignment as equivalent to a centroid day.

## Operational pseudocode

```python
import numpy as np


def classify_regime(z500, climatology, trend, seasonal_scale,
                    area_sqrt_coslat, eof_matrix, centroids):
    anomaly = z500 - climatology - trend
    x = anomaly / seasonal_scale
    x = x * area_sqrt_coslat
    pcs = eof_matrix @ x.ravel()
    pcs = pcs[:12]

    centroid_dist = np.linalg.norm(centroids - pcs[None, :], axis=1)
    origin_dist = np.linalg.norm(pcs)

    if origin_dist < centroid_dist.min():
        label = "NO_REGIME"
    else:
        label = int(centroid_dist.argmin())

    return {
        "label": label,
        "origin_distance": float(origin_dist),
        "centroid_distances": centroid_dist.tolist(),
        "pcs": pcs.tolist(),
    }
```

The 10-day filtering step must be implemented causally for operational use. A centered 10-day smoother is allowed for historical descriptive labeling but would leak future information into a forecast-time decision. Maintain separate `research_label` and `operational_label` definitions if the published historical series uses centered smoothing.

## Year-round versus winter-only

**FOUND:** The four-regime framework described above was designed for year-round use. Approximate climatological frequencies in the published sample are Pacific Trough 25 percent, Pacific Ridge 22 percent, Alaskan Ridge 20 percent, Greenland High 19 percent, and No Regime 14 percent. Median persistence is on the order of a week.

Many older regime systems are winter-only and use North Atlantic Oscillation or Pacific-North American patterns. Do not apply their winter centroids in summer without validation.

Summer implementation recommendation:

1. Start with the published year-round centroids to preserve one label vocabulary.
2. Report regime distance and seasonal percentile.
3. Run a summer-specific clustering challenger.
4. Promote summer-specific centroids only if they improve analog retrieval over year-round labels on unseen summers.

## Free operational assignments

A free researcher-maintained operational dashboard and historical files are available through the Weather Regimes project:

```text
https://www.weather-regimes.com/
```

The project publishes or has published:

- daily historical assignments and Weather Regime Index values;
- GEFS ensemble regime proportions using the 00 UTC extended forecast;
- ECMWF extended-range regime probabilities with publication delay tied to public S2S availability;
- centroid, EOF, PC, or Zenodo companion data needed for reproduction.

**Operational risk:** this is not an official NOAA or ECMWF service-level endpoint. Archive every daily assignment and the underlying forecast fields. The production system must be able to compute the label itself from frozen parameters.

## Forecast skill horizon

Published large-scale circulation predictability is strongest in the first one to two weeks. Regime probabilities generally retain useful ensemble information beyond deterministic day-by-day labels, but skill is regime- and season-dependent.

Engineering horizon:

```text
0 to 7 days: deterministic label can be used with normal quality controls
8 to 10 days: deterministic label should be downgraded; use ensemble probabilities
11 to 14 days: distribution only, with No Regime and transition risk explicit
beyond 14 days: use only if a verified regime-probability benchmark is beaten
```

This is an operational policy, not a claim that all four regimes have equal skill through day 14. Score Brier score, ranked probability score, transition timing error, and persistence separately by regime and season.

## Relationship to natural-gas prices

**SEARCHED AND FOUND NOTHING:** no published study was found that demonstrates incremental Henry Hub price prediction from these exact North American regime labels after controlling for temperature forecast, forecast revision, season, storage, forward net load, and the market's prior pricing.

That negative result is useful. The label should enter the system as:

- a low-dimensional analog retrieval key;
- a prior over temperature and renewable-generation pathways;
- a regime-persistence and transition descriptor;
- a stratifier for forecast dispersion and play validity.

It should not enter as:

```text
ALASKAN_RIDGE = bullish gas
GREENLAND_HIGH = bullish gas
```

The physical and market conversion remains conditional.

## Retrieval benchmark

The label earns its place only if analog retrieval improves against:

1. Season and month only.
2. Random label with the same frequency distribution.
3. Nearest match in continuous leading-PC space.
4. Temperature and forward-net-load state without a regime label.
5. Persistence regime from the prior day.

Score curve-shape match, slope error, turn timing, and rejection rate. The label can be valuable even without standalone price-direction skill if it improves retrieval quality or NO CALL calibration.

## Falsification first

The regime feature is killed or scoped down if:

- it does not improve analog retrieval over season-only or continuous-PC matching;
- performance exists only in pooled data and reverses by season or regime;
- the No Regime rule does not improve calibration or rejection;
- operational causal labels differ materially from centered historical labels;
- forecast probabilities do not beat climatological regime frequencies;
- a direct price-sign mapping is required to make it appear useful.

## Required archived objects

```text
regime_definition_version
training_period
climatology_version
trend_value_and_method
low_pass_definition
seasonal_scale
EOF matrix
PC normalization
centroids
origin threshold rule
source z500 cycle and member
operational assignment
research assignment if different
centroid distances
ensemble regime probabilities
quality state
```


# Task 6 - LNG feedgas nomination sources

## Bottom line

**FOUND:** Public informational-posting sites expose scheduled quantities and operationally available capacity for the pipelines feeding the named LNG terminals.

**FOUND:** The nomination field is the scheduled delivery quantity at the terminal-boundary meter, usually labeled `Total Scheduled Quantity`, `Scheduled Quantity`, or an equivalent scheduled-volume field. `Operationally Available Capacity` is not the nomination; it is a capacity remainder or constraint field.

**Build decision:** build the feed as a fleet of versioned pipeline adapters with cycle snapshots and explicit failure states. Do not sum every upstream interconnect. Select one terminal-boundary delivery meter per terminal and use upstream pipelines only for reconciliation or outage diagnosis.

**SEARCHED AND FOUND NOTHING:** a public documentary record confirming the exact claim that a NAESB working group formally abandoned one universal automated scraper. The operational reasons for scraper failure are nevertheless observable in the heterogeneous EBB interfaces and are documented below as an engineering inference, not as verified NAESB history.

## Terminal and pipeline source register

| Terminal | Pipeline or EBB | Public informational-posting URL | Meter or location pattern | Nomination field |
|---|---|---|---|---|
| Sabine Pass | Creole Trail Pipeline | https://lngconnection.cheniere.com/#/ctpl | Search for Sabine Pass Liquefaction or terminal delivery locations in the Creole Trail location table. Preserve location ID from the raw posting. | `Total Scheduled Quantity` at the terminal delivery point. |
| Sabine Pass upstream cross-check | Transcontinental Gas Pipe Line, Transco | https://www.1line.williams.com/Transco/index.html | Search Transco locations delivering to Creole Trail or Sabine Pass. Do not add these to the Creole Trail terminal-boundary quantity. | Scheduled quantity or scheduled volume by location and cycle. |
| Sabine Pass upstream cross-check | Natural Gas Pipeline Company of America, NGPL | https://pipeline2.kindermorgan.com/default.aspx?code=NGPL | Search NGPL delivery/interconnect locations serving Creole Trail or Sabine Pass. | Scheduled quantity in the operational-capacity/location report. |
| Corpus Christi | Corpus Christi Pipeline | https://lngconnection.cheniere.com/#/ccpl | Corpus Christi Liquefaction or terminal delivery location; retain the posted location ID. | `Total Scheduled Quantity`. |
| Cameron | Cameron Interstate Pipeline | http://www.gasnom.com/ip/cameron | `Cameron LNG (Del)`, location 772300 in the observed operational-capacity table. | `TSQ`, Total Scheduled Quantity. |
| Plaquemines | Gator Express Pipeline | https://web-prd.myquorumcloud.com/VGPPB1IPWS/?tspno=2 | Plaquemines LNG or terminal delivery location in the Gator Express location list. | Scheduled quantity or total scheduled quantity for the delivery meter. |
| Calcasieu Pass | TransCameron Pipeline | https://web-prd.myquorumcloud.com/VGPPB1IPWS/?tspno=10 | Calcasieu Pass LNG terminal delivery location. | Scheduled quantity for the terminal delivery point. |
| Golden Pass | Golden Pass Pipeline | https://www.gasnom.com/ip/goldenpass | Golden Pass LNG delivery location in the operational-capacity table. | `TSQ`, Total Scheduled Quantity. |
| Cove Point | Cove Point Pipeline | https://infopost.bhegts.com/cpl | Cove Point LNG delivery or terminal meter. Preserve the posted location and downstream-zone identifiers. | Scheduled quantity by location and cycle. |
| Elba Island | Elba Express Company | https://pipeline2.kindermorgan.com/default.aspx?code=EEC | `SLNG/EEC CHATHAM`, observed point 938000. | Scheduled quantity at the Chatham delivery point. |
| Elba Island cross-check | Southern LNG | https://pipeline2.kindermorgan.com/default.aspx?code=SLNG | `SLNG/SNG CHATHAM`, observed point 660000, and `SLNG/EEC CHATHAM`, point 938000, depending on the report. | Scheduled quantity; reconcile rather than sum overlapping intercompany points. |

Exact operational-capacity pages observed for Gasnom systems:

```text
https://www.gasnom.com/ip/cameron/oauc.cfm?type=1
https://www.gasnom.com/ip/goldenpass/oauc.cfm?type=1
```

The page columns include location name, location number, zone, purpose, quantity transaction indicator, flow indicator, design capacity, operating capacity, Total Scheduled Quantity, and Operationally Available Capacity.

## What to extract

Per pipeline, archive the complete location table and then select terminal-boundary rows by a versioned meter map.

Canonical fields:

```text
pipeline
terminal
location_id
location_name
location_zone
location_purpose
quantity_transaction_indicator
flow_indicator
design_capacity
operating_capacity
total_scheduled_quantity
operationally_available_capacity
units
gas_day
data_cycle: TIMELY | EVENING | ID1 | ID2 | ID3 | FINAL
posting_time_utc
source_revision
source_uri
raw_checksum
parser_version
meter_map_version
quality_state
```

### Which field is feedgas nomination

Use the scheduled delivery quantity at the terminal boundary:

```text
feedgas_nomination = total_scheduled_quantity at selected terminal delivery meter
```

Do not use:

```text
operationally_available_capacity
operating_capacity
design capacity
receipt quantity at an upstream interconnect
sum of every pipeline path feeding the terminal
```

`OAC` is useful as a constraint or outage feature, not as nominated feedgas.

## NAESB gas-day and nomination cycles

Times are Central Clock Time. Store the source time zone and convert to UTC with the applicable daylight-saving rule.

| Cycle | Nomination deadline | Scheduled quantity issued | Effective time |
|---|---:|---:|---:|
| Timely | 13:00 on the day before gas flow | Approximately 17:00 prior day | 09:00 gas-day start |
| Evening | 18:00 prior day | Approximately 21:00 prior day | 09:00 gas-day start |
| Intraday 1 | 10:00 gas day | Approximately 13:00 gas day | 14:00 gas day |
| Intraday 2 | 14:30 gas day | Approximately 17:30 gas day | 18:00 gas day |
| Intraday 3 | 19:00 gas day | Approximately 22:00 gas day | 22:00 gas day |

Pipeline tariffs and EBB operations can post preliminary, revised, or final values around these windows. The collector should poll a bounded window around each cycle and preserve each changed raw object rather than overwrite one daily row.

Official background:

- FERC Order No. 809 and NAESB nomination-cycle standards.
- Pipeline-specific tariffs linked from each EBB.

## Machine-readable status

| EBB family | Practical interface | Machine-readability assessment |
|---|---|---|
| Cheniere LNG Connection | JavaScript single-page application with backing requests | Machine-readable after the backing request is identified, but routes and tokens can change. Archive the raw JSON or response body. |
| Gasnom | Server-rendered HTML tables and form parameters | Parseable HTML; no stable public JSON API identified. |
| Kinder Morgan pipeline2 | ASP.NET-style informational posting system | Download or table endpoints exist, but session state and form fields can change. |
| MyQuorumCloud | Web application with pipeline selected by `tspno` | Parseable after pipeline-specific route discovery; JavaScript or session behavior may change. |
| BHE Cove Point | Informational-posting portal with report downloads | Prefer downloadable report output over DOM scraping. |
| Williams 1Line | Informational-posting portal | Prefer official downloadable report or export function when available. |

There is no universal NAESB API that makes these EBBs one schema.

## Terms of use and scraping

**SEARCHED AND FOUND NOTHING:** blanket permission allowing automated scraping across all listed sites.

Public accessibility does not equal permission for high-rate or redistributive scraping. Required controls:

1. Read and archive the current site terms and pipeline tariff notices.
2. Use low-rate, cycle-aligned requests rather than continuous hammering.
3. Identify the collector with a descriptive user agent and contact address when allowed.
4. Cache raw responses and avoid repeat downloads.
5. Do not bypass authentication, access controls, CAPTCHAs, or technical restrictions.
6. Treat data as internal operational input unless redistribution rights are explicit.
7. Obtain legal review before commercial redistribution of normalized postings.

## Known failure modes

### Interface failures

- HTML column order or header text changes.
- JavaScript application route changes.
- Session cookies, hidden form fields, or anti-automation controls.
- Download links return an error page with HTTP 200.
- Pipeline identifier or `tspno` changes.
- Site maintenance during a nomination cycle.

### Semantic failures

- `TSQ` is confused with `OAC`.
- Receipt and delivery signs are reversed.
- A terminal has multiple trains or meters and the parser sums an aggregate and its components.
- Upstream interconnects are summed with the terminal-boundary meter, double-counting the same molecule.
- Location names are renamed while IDs persist, or IDs are retired while names persist.
- Zero means a real zero, missing row, not-yet-posted cycle, or parser failure.
- Timely values are overwritten by Evening or Intraday revisions, destroying the forecast-time vintage.
- Gas-day dates are assigned by calendar midnight instead of 09:00 Central.
- Dth, MMBtu, Mcf, and Bcf are converted with an assumed heat content.
- Scheduled quantity is treated as measured physical flow.

### Market-use failures

- Feedgas nomination changes because of balancing or optimization and is not equal to final terminal consumption.
- Maintenance constrains OAC but the terminal sources gas through another path.
- A ramp is visible only after the relevant market has already priced it.
- The aggregate terminal quantity masks train-level commissioning or outage behavior.

## Why a universal scraper fails

The claim of a formally abandoned NAESB scraper was not independently verified. The engineering conclusion is still clear:

```text
The common standard governs posting content and cycles more than it governs
one modern transport, schema, URL contract, or error behavior.
```

A universal parser tends to fail silently because every site expresses the same concepts with different HTML, JavaScript, labels, units, identifiers, and revision behavior.

The correct design is:

```text
one shared canonical schema
one adapter per EBB family
one meter map per terminal
one cycle-aware archive
one health and exception layer
```

## Collector design

### Cycle job

For each pipeline and cycle:

1. Fetch official location/report index.
2. Fetch full raw report.
3. Verify content type, title, expected headers, and minimum row count.
4. Hash and archive raw response.
5. Parse all rows.
6. Apply versioned terminal meter map.
7. Compare against prior cycle and prior raw checksum.
8. Emit normalized rows and an exception report.
9. Mark `READY` only when expected terminal meter is present and units are valid.

### Health states

```text
READY
LATE
PARTIAL
SCHEMA_CHANGED
METER_MISSING
AUTH_OR_SESSION_FAILURE
SITE_UNAVAILABLE
ZERO_CONFIRMED
ZERO_AMBIGUOUS
MANUAL_REVIEW
```

A missing meter must never become numeric zero.

### Reconciliation

Use upstream Transco or NGPL values to explain constraints or path changes at Sabine Pass, but choose the Creole Trail terminal boundary as the primary quantity. Apply the same principle to Elba intercompany Chatham points.

Where measured physical flow is published, compare:

```text
Timely nomination
Evening nomination
latest intraday nomination
final scheduled quantity
measured flow
```

This produces a revision and nomination-to-flow error distribution that can become a useful forecast-quality feature.

## Falsification and acceptance

The feed is accepted only if, per terminal:

- the selected meter map reconciles to known terminal operations;
- cycle timestamps reproduce what was knowable before the gas day;
- parser failures never emit a false zero;
- nominations and measured flow are stored as distinct variables;
- double-counting tests pass;
- revision history is retained;
- an unexplained site change stops the adapter and opens manual review.

The market feature is killed or scoped down if nomination revisions do not improve a physical feedgas or storage-balance benchmark over persistence after publication latency is respected.


# Integrated build sequence

## Immediate archival actions

These actions should begin before model integration because the public sources revise or age out:

1. ECMWF and GEFS cycle manifests, members, indices, arrival times, and checksums.
2. Every ISO forecast issue vintage for load, wind, and solar.
3. Weather-regime operational assignments and the underlying Z500 fields.
4. Every LNG nomination cycle and raw EBB response.

The archive should be immutable and partitioned by source publication time, not only by target valid time.

## Build order

### P0-A - Causal flow replication

- Inventory the real NG trade/book corpus.
- Freeze active-contract selection.
- Implement native and Lee-Ready side classifiers.
- Implement online-only leg segmentation.
- Reproduce the desk's 34-of-34 record from immutable events.
- Score against current-leg direction, slope, and executable markouts.

### P0-B - Ensemble and forecast-vintage ingestion

- Build ECMWF and GEFS member manifests.
- Build ERCOT and SPP adapters first.
- Add CAISO, PJM, MISO, and ISO-NE under the same schema.
- Add EIA-930 Southeast load-only fallback.
- Compute ensemble gas-weighted temperature, spread, revisions, and NO CALL inputs.

### P0-C - LNG cycle adapters

- Start with one EBB family at a time: Cheniere, Gasnom, Kinder Morgan, MyQuorum, BHE, Williams.
- Freeze terminal meter maps.
- Add health states before using the values in the decision state.

### P1-A - Summer physical conversion

- Build BA weather mapping.
- Join EIA-930 gas generation.
- Estimate power-sector response weights.
- Compare power-weighted CDD with forward net load.

### P1-B - Weather regimes

- Archive published centroid/EOF package.
- Reproduce historical labels.
- Build causal operational label.
- Add ensemble regime probabilities.
- Test retrieval improvement against season-only and continuous-PC baselines.

## Unified evidence-state contract

Every feature supplied to the forecaster should include:

```text
value
valid_time
as_of_time
source_publish_time
source_received_time
source_version
transformation_version
quality_state
evidence_state
scope
benchmark
known_invalidations
```

The forecaster should be able to decline when the distribution is incomplete, source vintages conflict, a regime assignment is weak, a nomination parser is unhealthy, or the analog distance exceeds its dimension budget.

# Acceptance matrix

| Workstream | Minimum acceptance | Benchmark | Kill condition |
|---|---|---|---|
| Flow nowcast | Reproduces historical qualifying events causally and adds executable continuation value | Current-leg direction and price slope | No incremental OOS value or look-ahead dependence |
| Ensembles | Complete member manifests and exact as-of replay | Deterministic forecast plus climatological spread | Partial cycles silently treated as full |
| Forward net load | Same-vintage load minus wind minus solar, by region | Load-only and seasonal net-load persistence | No BA gas-burn improvement in target cells |
| Power CDD | Stable frozen BA weights and Ohio coverage | Population CDD, heating CDD, forward net load | No unseen physical improvement or unstable sign |
| Weather regime | Reproduced labels and causal operational assignment | Season-only, random label, continuous PCs | No retrieval or calibration improvement |
| LNG nominations | Cycle snapshots, meter-map reconciliation, no false zeros | Prior-cycle nomination and measured flow where available | Silent parser failure or double counting |

# Conclusions

The six workstreams do not call for a larger undifferentiated model. They close specific information and measurement failures:

- Task 1 establishes when live tape can govern direction.
- Task 2 supplies distributions and revision paths.
- Task 3 supplies the forward thermal-dispatch variable that can flip the weather sign.
- Task 4 repairs the summer physical conversion.
- Task 5 compresses atmospheric state into a dimension the analog library can support.
- Task 6 restores a knowable, dated demand line before the gas day.

The common engineering requirement is point-in-time truth. Every source must be archived with its issue time, raw bytes, checksum, version, quality state, and transformation. Without that, the desk can build persuasive hindsight but cannot measure a tradable forecast.


# Public source appendix

## Ensemble data

- ECMWF Open Data documentation: https://confluence.ecmwf.int/display/DAC/ECMWF+open+data%3A+real-time+forecasts+from+IFS+and+AIFS
- ECMWF Open Data client: https://github.com/ecmwf/ecmwf-opendata
- ECMWF AWS Open Data registry: https://registry.opendata.aws/ecmwf-forecasts/
- ECMWF direct forecast root: https://data.ecmwf.int/forecasts/
- NOAA NOMADS: https://nomads.ncep.noaa.gov/
- NOAA GEFS product inventory: https://www.nco.ncep.noaa.gov/pmb/products/gens/
- NOAA GEFS AWS bucket index: https://noaa-gefs-pds.s3.amazonaws.com/index.html
- NOAA GEFS AWS registry: https://registry.opendata.aws/noaa-gefs/

## Grid and load forecasts

- ERCOT data products: https://www.ercot.com/mp/data-products
- SPP data portal: https://portal.spp.org/
- CAISO Today's Outlook: https://www.caiso.com/todays-outlook
- CAISO OASIS: http://oasis.caiso.com/
- PJM Data Miner 2: https://dataminer2.pjm.com/
- MISO public API: https://public-api.misoenergy.org/
- MISO market reports: https://docs.misoenergy.org/marketreports/
- ISO-NE Web Services: https://webservices.iso-ne.com/
- ISO-NE system reports: https://www.iso-ne.com/isoexpress/web/reports/operations/-/tree/seven-day-forecast
- EIA Grid Monitor: https://www.eia.gov/electricity/gridmonitor/
- EIA Open Data: https://www.eia.gov/opendata/

## Degree days and physical conversion

- EIA degree days: https://www.eia.gov/energyexplained/units-and-calculators/degree-days.php
- EIA-930 fuel-type data: https://www.eia.gov/opendata/browser/electricity/rto/fuel-type-data
- Frontier Weather: https://www.frontierweather.com/

## Weather regimes

- Weather Regimes operational and research portal: https://www.weather-regimes.com/
- ERA5 documentation: https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5

## LNG informational postings

- Cheniere LNG Connection: https://lngconnection.cheniere.com/
- Cameron Interstate Pipeline: http://www.gasnom.com/ip/cameron
- Golden Pass Pipeline: https://www.gasnom.com/ip/goldenpass
- Gator Express: https://web-prd.myquorumcloud.com/VGPPB1IPWS/?tspno=2
- TransCameron: https://web-prd.myquorumcloud.com/VGPPB1IPWS/?tspno=10
- Cove Point Pipeline: https://infopost.bhegts.com/cpl
- Elba Express: https://pipeline2.kindermorgan.com/default.aspx?code=EEC
- Southern LNG: https://pipeline2.kindermorgan.com/default.aspx?code=SLNG
- NGPL: https://pipeline2.kindermorgan.com/default.aspx?code=NGPL
- Transco 1Line: https://www.1line.williams.com/Transco/index.html
- FERC: https://www.ferc.gov/

# Evidence limitations

1. The exact original ChatGPT Task 1 audit record was not recovered. The paper distinguishes the real prior result from the proposed canonical reconstruction.
2. Public-source interfaces can change after this paper's date. The exact raw response, documentation page, and terms should be archived at implementation time.
3. The Weather Regimes operational portal is researcher-maintained rather than a government service with a guaranteed service level.
4. No direct published Henry Hub price-skill study was found for the exact four-regime label.
5. No blanket scraping permission was found for the LNG EBBs, and the claimed NAESB scraper-abandonment record was not independently located.
