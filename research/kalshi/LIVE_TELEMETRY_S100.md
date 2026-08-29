# LIVE TELEMETRY - S100 (the live loop's first breath, 2026-07-20)

The first live-feed telemetry datum of the program, per the S100 kickoff (Bento Standard
subscribed S99; smoke test = S100 opener). Recorded per-event; the numbers below are the
distribution of one 60s window, not a pooled conclusion.

## The datum

- When: 2026-07-20 18:37 UTC (14:37 ET, Monday, RTH mid-session).
- Where: EC2 `i-08cee7171c0a76a04` (t3.xlarge, us-east-2) - NOT the eventual live box; the
  **CORRECTED 2026-08-29 BY LIVE PROBE:** the instance is an **r6i.2xlarge** (8 vCPU / 61.8 GiB usable, 32.0 GiB swap, 128.2 GiB free disk, us-east-2b, running). The `t3.xlarge` above was true when written and became false when the box was resized; it is left in place as the record. Measured by `.github/workflows/frankie_box_sizing_probe_20260829.yml`, run 33242769879.
  smoke ran here because the Claude cloud container cannot reach the live gateway at all
  (raw-TCP port 13000 blocked by the container's HTTPS-only proxy - a structural fact for all
  future sessions: live-feed work happens on AWS boxes, never in the container).
- What: GLBX.MDP3, schema `trades`, parent symbology NG.FUT (all NG futures + spreads).
- Result: n=29 TradeMsg in 60s (quiet summer Monday tape across the family).
  Latency (exchange ts_event -> our process): **min 6.6 / median 7.7 / p90 13.0 /
  max 23.4 ms.**
- Read: ~1000x inside the established 7-20 SECOND futures->Kalshi lag edge. The us-east-2
  transit profile (~7ms) is consistent with a Chicago-area GLBX gateway (CME Aurora);
  us-east-2 sits closer to it than us-east-1 does. The AWS_PLATFORM_S98 us-east-1 live-box
  plan is unaffected in its conclusion (any US region beats the edge's clock by orders of
  magnitude) but the region choice can be revisited with measurements when M5 builds.

## Events on the way to the datum (each cost time; named so they never repeat)

1. AWS key: the container's placeholder env vars overrode the real pair - see CLAUDE.md
   "AWS KEY" section (the fix is `bash -lc` / explicit creds). The key itself was never wrong.
2. Container cannot run the live smoke (raw TCP blocked) - ran via SSM on the box instead.
3. First subscribe returned "A live data license is required to access GLBX.MDP3" - the
   Standard plan alone is not the license; Greg attached the GLBX.MDP3 live license /
   corrected a latency-category setting in the portal, after which the feed flowed.
4. THE MAPPING-RECORD TRAP: on subscribe the gateway emits SymbolMappingMsg for EVERY child
   of the parent (dozens; ts_event set, price/size None). The v1 smoke filter
   (`hasattr(rec,"ts_event")`) counted 40 of those, printed "LIVE PLAN WORKING", and exited
   without seeing one trade. Fixed: only `isinstance(rec, db.TradeMsg)` counts
   (databento_live_smoke.py now enforces this and prints the latency distribution).

## Standing consequences

- Live-loop telemetry per fire (the decay watch) is cheap and instant at this latency; the
  hot path budget is dominated by our own logic, not transit.
- The Databento key in use = `db-3ba8...` (the pre-rotation key; still fully alive - portal
  deactivation was never done). Full key lives outside the repo (scratchpad/aws.env pattern).
- Box stopped after the smoke (leave-as-found); restart-on-demand is ~3 minutes via
  start_instances + SSM.
