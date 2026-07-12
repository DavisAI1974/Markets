# SESSION HANDOFF — S85 (work date 2026-07-12) — Databento LIVE + event_move_baseline first real result

Branch: worked on harness branch `claude/kalshi-s85-kickoff-p5i61k` (rebased onto the s79 trunk at start;
harness cut it from the stale S70 tip `3c70ff5` again). **All work pushed to the canonical trunk
`claude/kalshi-s79-kickoff-ij8t9o`** (default; collectors auto-push there; pull before push). Commits:
`8af3709` (event_move_baseline + databento defs mode) -> `5395b93` (volume roll) -> `05c7bc1` (retry) ->
`8b0aa1f` (tick_source aggregate) -> `d3c9bcf` (fast-60s metric) -> [docs commit]. Data on the new
**`data/nymex-ticks`** branch.

## 1. Databento is LIVE — key set, pipeline proven end-to-end

Greg set `DATABENTO_API_KEY` (a SECRET — never commit; pass inline as env var). `pip install databento`
-> 0.81.0 (the version the tool was written against). The whole chain now works against the real API:
cost gate -> pull -> definition schema -> baseline.

**Cost map (all free `metadata.get_cost`, zero data):**
| pull | NG | CL | NG+CL |
|------|----|----|-------|
| trades 1yr | $15.80 | $32.38 | ~$48 |
| trades 2yr | $31.61 | $64.32 | ~$96 |
| tbbo 1yr | $26.33 | $53.97 | ~$80 |
| **mbp-10 1yr** | **$38.98** | **$90.68** | **~$130** |
| definition | ~$0 | ~$0 | ~$0 |

$125 credit (6mo, one/team). **Schema decision (Greg): MBP-10** — "a few bucks over for a better view."
MBP-10 is a superset (trades + top-of-book + 10-level DEPTH, ns-stamped) = timestamps + fill size +
bid/offer size + resting-depth run-length read in one feed; ~$5 over the credit for a full year of both.
**MBO (L3) stays OFF** — 50-100GB/yr, disk/overkill, not money. Live subscription NOT bought (research =
pay-as-you-go historical; live is $179/mo + CME passthrough, a go-live-era cost).

## 2. event_move_baseline.py — BUILT and RUN on real ticks (`EVENT_MOVE_FINDINGS_S85.md`)

Per-event move MAGNITUDE + DURATION on the true-tick tape, per surprise-cell, ticks/$/bps, distributions
not means, leakage-gated. Tick size POINT-IN-TIME from the `definition` schema (NG/CL both confirmed
$10/tick vs reference). **12 NG + 12 CL EIA-release windows, leakage PASS 12/12 on `definition` ticks.**

**The headline is a HOLD-TIME map (the S85 fast-window metric):**
- **NG front-loaded**: 60s move 106bps p50 ($310, up to $550/contract), **captures 66% of the full peak
  in the first minute** (06-11 peaked in 1 SECOND). NG = the ~60s fast scalp.
- **CL slower**: 60s 23bps p50 ($190, p90 $509, max $700), captures 27% -> a LONGER hold gets the rest
  (06-17 CL: $290 in 60s but $2,640/341bps full move over 17min). NOT "CL fails" (Greg corrected the
  deflationary framing) — CL is KEPT on a longer hold; frequency isn't the gate, EV-net-of-fee is.
- Both kept, different hold windows. Matches EVENT_WEIGHT_STUDY (NG fast/heaviest z=5.2; crude diffuse).

CAVEATS: futures move = the CEILING, not Kalshi P&L (the lag join measures the real echo net-of-fee next);
surprise=unknown for all (historical consensus/actual not wired — the surprise split is where CL's big
days live); n=12, windows only, provisional.

## 3. Tooling hardened this session

- `databento_backfill.py`: added `defs` mode + definition-schema writer (`{ROOT}_definitions.jsonl`,
  point-in-time tick_size/value); default continuous roll = **VOLUME** (`.v.0`, the liquid front Kalshi
  reprices off; `--roll {v,n,c}`); `_retry()` exp-backoff on transient proxy resets (ConnectionResetError
  104 crashed a multi-window pull; now survives).
- `event_move_baseline.py`: fast-window (60s) metric (`--fast`); tick_source aggregated per-event
  (an event before the def window falls back to reference — was mislabeled as events[0]).
- Data PERSISTED: gzipped tape+defs+baselines on **`data/nymex-ticks`** (1.6MB); `kalshi-session-start`
  skill updated to restore it into `data/pyth_ticks/`. So next session RESTORES, does not re-pull/re-spend.

## OPEN / NEXT (S86) — this is a clean checkpoint before the heavy pull

1. **Extend the writer + baseline to consume MBP-10 DEPTH** (bid/offer size + 10 levels), then batch-pull
   the full-year MBP-10 for NG+CL (~$130) -> daily tape (KXNATGASD settles 5PM close EVERY day) + ~52
   releases/yr/contract for real per-cell N. Watch container DISK (multi-GB -> batch/compressed).
2. **Historical surprise join** (EIA actuals + street consensus) -> the surprise-cell split (beat/miss x
   big/small) — where CL's big-day fires show up; NG/CL both need it to move past surprise=unknown.
3. **The lag join** — Kalshi echo net-of-fee vs the futures move, per hold-time, per contract: turns the
   ceiling into realized-EV. (The S82 level-hit dataset was built to receive this `futures_move` context.)
4. Standing: fix bogus `NGDQ6` in `pyth_collector.py`; score Greg's weather forecaster per-day net-of-fee;
   Pyth live sub-second lag when a post-reopen tape lands.

## RULES (unchanged): NYMEX is the canary (fire on Kalshi); each trade individually / per-cell /
distributions not means; NEVER lead with the deflationary median or say "X failed" (S85: CL); exclude the
settle window; leakage gate before any backtest; zero synthetic; provisional-until-live; weather
forecaster = Greg's spec HANDS OFF; keep KALSHI_TRADING.md + CLAUDE.md lean; DATABENTO_API_KEY is a secret.
