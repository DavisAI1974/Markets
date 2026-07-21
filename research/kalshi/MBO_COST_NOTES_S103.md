# MBO cost / size findings (S103 info-gathering; Databento GLBX.MDP3, free metadata estimate)

Question (Greg): can we pull MBO 1-yr historic + run a live MBO feed? Ran Databento's FREE metadata
cost/size estimate on the box (i-08cee7171c0a76a04; DB key in /etc/markets/coach.env). Window
2025-07-01 -> 2026-07-01. Numbers are LIST cost; our in-sub draw is typically far less (the L1/mbp-1
year pull runs $0.00 in-sub on the $179/mo Bento Live Standard).

| scope | schema | list $ | size GB |
|---|---|---|---|
| **NG front-continuous (c.0)** | **mbo** | **22.96** | **13.96** |
| NG c.0 | mbp-10 | 34.61 | 75.77 |
| NG c.0 | mbp-1 (current pull) | 0.75 | 8.14 |
| **CL front-continuous (c.0)** | **mbo** | **52.84** | **32.28** |
| CL c.0 | mbp-10 | 79.32 | 174.32 |
| CL c.0 | mbp-1 | 1.75 | 27.12 |
| NG ALL contracts (parent) | mbo | 320.95 | 195.73 |
| NG parent | mbp-10 | 536.73 | 1178.60 |
| CL ALL contracts (parent) | mbo | 734.86 | 451.73 |
| CL parent | mbp-10 | 1214.36 | 2687.27 |

## Takeaways
- **On the front-continuous (c.0 = what the forecaster uses), MBO is CHEAPER and ~5x SMALLER than the
  MBP-10 we already buy** (NG c.0: MBO $23/14GB vs MBP-10 $35/76GB). Reason: MBP-10 re-snapshots all 10
  levels on every event (verbose); MBO logs compact single-order events. **This REVERSES the S85 "MBO
  off for cost" decision for the continuous front.** And MBO is the exact order-level data (adds/pulls/
  cancels, queue position, far-side recruitment) that sharpens the turn/direction nowcast the S103
  problem memo flags as under-used.
- **NG + CL c.0 MBO, 1 year = ~$76 LIST / ~46 GB total** - trivial to stream per-day to S3 like the L1
  pull (won't fit the box's 200GB local; S3-stream). Likely much less than $76 actual (in-sub).
- The PARENT (all contracts / full cross-expiry book) is the expensive path: NG $321/196GB, CL
  $735/452GB. Not needed unless we specifically want every expiry.
- **Live MBO:** historic feasibility clear; live MBO on the sub still needs a TIER confirm, but L1 live
  is $0 in-sub and the sub is per-dataset (GLBX.MDP3), so MBO live is very likely covered too.

## How to pull (when Greg gives the go)
- Same untethered pattern as the L1 year pull (per-day build-in-memory -> ONE atomic S3 put, skip-if-
  exists = clean resume). Schema `mbo`, symbols `NG.c.0`/`CL.c.0`, stype_in `continuous`, dest
  s3://bento-568968024170-us-east-2-an/nymex/ng_mbo/ (and cl_mbo/).
- Cost/size check is FREE and re-runnable: databento Historical.metadata.get_cost / get_billable_size
  (no data pulled). Script used: base64->SSM->box; DB key from /etc/markets/coach.env.
- COORDINATE with ChatGPT's live-MBO effort (same DB key / box) before standing up a second feed - avoid
  double-write / double-cost.

## STATUS: INFO-GATHERING ONLY - nothing pulled, nothing started (Greg, S103).
