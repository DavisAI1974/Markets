# Free public-data gap plan for NG

## Collecting now

- EIA weekly Lower-48 working gas and weekly change.
- EIA-930 hourly demand, forecast demand, net generation and interchange for major gas-consuming balancing authorities.
- EIA-930 hourly generation by fuel, including natural gas, wind, solar, coal and nuclear.
- NOAA/NWS hourly forecasts for 16 gas-demand metros.
- NOAA/NWS active weather alerts for major gas-demand and Gulf supply states.

Collector: `research/kalshi/free_ng_data_collector.py`

AWS timer: `markets-free-ng.timer` every 30 minutes.

Local snapshot: `/var/lib/markets/free_ng/latest.json`

S3 snapshot: `s3://bento-568968024170-us-east-2-an/drivers/free_ng/latest.json`

## Free sources to add next

- ECMWF IFS/AIFS open forecast snapshots: temperature, wind and ensemble spread.
- NOAA GEFS/GFS model-run deltas and ensemble spread.
- NOAA storm and tropical products affecting Gulf production and LNG terminals.
- EIA nuclear outages and generator availability.
- Public pipeline electronic bulletin-board notices and maintenance postings.
- LNG terminal and Coast Guard public status notices.

## Gaps unlikely to be fully solved by free data

- Timely terminal-level LNG feedgas nominations.
- Nationwide dry-gas production estimates with trading-day latency.
- Clean, normalized interstate pipeline nominations across all systems.
- Institutional storage consensus history and revisions.
- CME ECNG/ECH market depth and trade history until venue data access is selected.

All free-source data enters as `research-input`; it cannot grant execution authority by itself.
