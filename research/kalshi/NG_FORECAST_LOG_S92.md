# NG blind-forecast log (S92) — the forecaster's reasoning, values, and the data he was missing

The Phase-2 blind build: an agent forecast 12 unseen NG days from **decision-time state only** (weekday +
EIA storage surprise + curve regime; it never saw the actual curves). It did well for how little relevant
info it had. This logs exactly how it reasoned, how it assigned magnitudes, what it got right, and — the
point — **what data it was missing and how to get it.** (Overlay render: `renders/ng_learn_s92/ng_blind_overlay_12days.png`;
forecasts: `renders/ng_learn_s92/ng_blind_forecasts.json`.)

## What it got right (blind)
- **Magnitude / trend-vs-range axis worked.** The big-|surprise| weeks it flagged (08-12, 08-13, 08-07,
  08-21) WERE the genuinely big-move days; small-|surprise| days stayed comparatively rangey.
- **Clean hits (magnitude + direction):** **08-13 Wed** (trend-up-grind; actual ground up) and **08-21 Thu**
  (quiet-then-pop-up; actual ground up +5.5c). Right call for the right reason.
- Friday range calls (07-18, 09-05) roughly held.

## Its reasoning framework (the rules it applied, in priority order)
1. **Storage-surprise |MAGNITUDE| → trend-vs-range.** |surprise| >= ~20 Bcf -> "trendy week" (big day);
   small |surprise| -> range/chop. (Magnitude, NOT sign.)
2. **Weekday archetype.** Tue = strongest-trend weekday; Wed = up-lean with a US-session catalyst; Thu =
   storage catalyst AT the 10:30 ET print (the decisive move is at the print); **Fri = range, and it
   OVERRIDES surprise** (its key structural bet, e.g. 08-08).
3. **Grind-vs-spike shape law.** A trend day = a slow US-session grind that holds (not a spike).
4. **Direction = a weak lean only.** below-consensus = bullish / above = bearish — explicitly flagged
   LOW-confidence (Pass 2: surprise sign does not sort direction).
5. **US-session timing (08-16 ET)** = where the day's real move happens; overnight ~flat.

## How it put VALUES to it (magnitude scaling)
- Mapped the |surprise| bucket to a $/contract magnitude prior: **big (>=20) -> ~$900** peak (trend);
  **moderate (~10) -> ~$250**; **small (<=8) -> ~$55-70** (range). Then shaped the archetype curve to that
  peak and set the close = a retention fraction of the peak (grind holds most, spike-fade gives most back).

## What it MISSED — DIRECTION (the honest gap)
- **08-12 Tue** is the lesson: identical logic (big surprise + below=bullish -> up) called UP; NG fell **-19c**.
  The two hits (08-13, 08-21) got direction right because the below=bullish lean happened to land; 08-12
  shows that lean is a coin-flip. **Magnitude/trendiness it can call; direction it cannot** — with the data
  it had.

## THE DATA GAPS — the relevant info it lacked, and how to get each
| missing signal | what it would unlock | how to get it |
|---|---|---|
| **News / headlines** | direction + the many unexplained legs (geopolitics, LNG, outages) | forward RSS collection (`news_ingest_rss.py`) — start now; NO history exists |
| **Real desk CONSENSUS** (vs our seasonal-proxy surprise) | surprise SIGN -> direction (the proxy sign is unreliable) | `consensus_poll.py` -> `consensus.jsonl` (ForexFactory, forward-only) |
| **Day-ahead vs spot / pipeline nominations** (Greg's idea) | intraday demand pressure -> leg size + direction | Platts / NGI cash indices / pipeline EBB noms — NEW paid source |
| **Backwardation regime** | test the prompt/curve-spread signal (the day-ahead/spot proxy) | needs a WINTER stretch in-sample — comes with the full-year tape (contango-flat all 12 warm-season days) |
| **Overnight / pre-session lean** | a direction anchor knowable at the open | derivable from the tape pre-08:00 ET — a cheap add we have the data for |

## Direction we may take from here (Greg S92: fine with divergence)
- **Direction is the open problem.** The magnitude/day-type read is decent; the value is in solving up-vs-down,
  and the table above is the data plan for it.
- The overnight-lean add is free (we have the ticks) and is the first cheap shot at a direction anchor.
- The signal-hunt agent (running) is testing every signal against direction + the turning points, per-event.
