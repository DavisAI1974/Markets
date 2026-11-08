# Claude Code October NG discovery notes

Independent Claude Code review, November 8, 2026. Written to its own file at the
user's request so the Desktop, Codex and Claude Code reviews can be merged later.
The shared [October discovery log](october-discovery-log.md) is source context and
is unchanged here. Interpretations below were formed from the pinned evidence
before reading the Codex notes; the agreement and disagreement section at the end
was written afterwards and says which is which.

Pinned inputs: evidence revision `d25fc3f7e59c2a1cb51ec943cd91ff34e176a72a`
(group export, lifecycle tables), reconstruction `b5f28bd57de5ed4ff889335edb9a33216b67eb6a`
(863 dipole candidate inputs), handoff `5724f4096248dd8080aa381a34855097c685dc1c`,
raw tape `1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202` (October 18 UTC member, cursor
offset 17,375), producer `2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134`. All four dates
remain discovery; October 2 and 17 are partial. Everything below is October 18
only and is one day of dependent observations. Ticks are 0.001 price units.

Code and compact tables live in [claude-code/](claude-code/):
[four-arm script](claude-code/four_arm_first_family_flow_book.py) ·
[four-arm summary](claude-code/first-family-four-arm-summary.json) ·
[per-event rows](claude-code/first-family-four-arm-events.jsonl.gz) ·
[dipole post-recognition script](claude-code/dipole_post_recognition_outcomes.py) ·
[dipole summary](claude-code/dipole-post-recognition-summary.json) ·
[dipole rows](claude-code/dipole-post-recognition-rows.jsonl.gz) ·
[size-one script](claude-code/size_one_four_arm.py) ·
[size-one summary](claude-code/size-one-four-arm-summary.json) ·
[375/391 tape trace](claude-code/trace_first_family_orders.py) ·
[trace summary](claude-code/trace-first-family-summary.json) ·
[375 messages](claude-code/trace-instance375-messages.jsonl.gz) ·
[391 messages](claude-code/trace-instance391-messages.jsonl.gz) ·
[cohort mechanics script](claude-code/sweep_cohort_trace.py) ·
[cohort mechanics rows](claude-code/sweep-cohort-events.jsonl.gz) ·
[market fundamentals research notes](claude-code/research-notes/) (six sourced note files: commodity futures and natural gas, price formation and microstructure, market psychology, quant research methods, unsolved puzzles, novel frameworks; the one-file synthesis is pending).

## 1. What the dipole tracked, and what happened after it became visible

**What it tracks.** The detector follows the 20-second rolling signed-lot ratio
(buy lots minus sell lots over classified lots). A birth is a peak of that ratio
above a trailing 85th-percentile bar; recognition is the later completed group
at which the peak is knowable (median 2.4 s after the nominal second, max 87 s).
The ratio can change without any new print, because old prints age out of the
window; 345 of 863 recognitions had no classified volume in the latest window.
So "persistence" and "reversal" of the dipole are statements about a rolling
trade-sign ratio, not about price and not about fresh order flow.

**Birth-to-recognition is realised history, not a forecast.** The existing table
(155/65/55, 56/127/34) measures the midpoint from before the birth second to the
recognition close. That interval is mostly before the candidate existed. Read
from the recognition close forward (the first moment anyone could act), the
picture is:

| Post-recognition, oriented to birth polarity | +1 s with / flat / against | +20 s | +60 s | +300 s |
| --- | --- | --- | --- | --- |
| All 863 | 98 / 671 / 94 | 260 / 357 / 245 | 339 / 188 / 335 | 393 / 73 / 392 |
| Rolling flow still same as birth (275) | 29 / 211 / 35 | 90 / 99 / 86 | 119 / 43 / 113 | 131 / 15 / 126 |
| Rolling flow opposite (217) | 28 / 164 / 25 | 69 / 71 / 76 | 89 / 35 / 92 | 93 / 17 / 106 |
| Balanced with volume (26) | 3 / 17 / 6 | 9 / 3 / 14 | 9 / 3 / 14 | 10 / 1 / 15 |
| Undefined, no volume (345) | 38 / 279 / 28 | 92 / 184 / 69 | 122 / 107 / 116 | 159 / 40 / 145 |

Flat dominates at one second (671 of 863). At every horizon the birth polarity
and the flow state at recognition are near coin flips. SAME versus FLIP
orientation to the predecessor is also indistinguishable (20 s: 138/192/142
versus 122/164/103). The one-lot births (332) behave like the multi-lot births.
On this day the dipole's direction carried no measurable post-recognition
information about the midpoint.

**What did carry information at recognition is the displayed touch, and it is
not a dipole property.** Comparing displayed bid size with ask size at the
recognition close:

| Touch size at recognition relative to birth polarity | +1 s with / flat / against | +20 s | +60 s |
| --- | --- | --- | --- |
| Aligned (393) | 59 / 299 / 35 | 146 / 160 / 86 | 171 / 87 / 134 |
| Opposed (371) | 28 / 292 / 51 | 85 / 152 / 134 | 133 / 71 / 167 |
| Equal (99) | 11 / 80 / 8 | 29 / 45 / 25 | 35 / 30 / 34 |

Rewritten as a plain queue-imbalance read (midpoint moves toward the heavier
touch side), recognitions give 280 with / 312 flat / 171 against at 20 s and
338 / 158 / 267 at 60 s. The same read at every active-session second's last
close (23,810 seconds, no dipole involved) gives 8,655 with / 5,508 flat / 7,531
against at 20 s (53.5 percent of non-flat) and 10,025 / 2,615 / 9,054 at 60 s.
At one second the day-wide rate is 1,859 / 18,838 / 997 (65 percent), and at
recognitions 110 / 591 / 63 (64 percent). So the touch read is a general feature
of this book (as Gould and Bonart found on large-tick equities), slightly
stronger at 20 s inside the recognition cohort (62 percent of non-flat) than
day-wide. The split holds within each polarity: buy births with aligned touch
66 / 69 / 40 at 20 s versus opposed 53 / 90 / 78; sell births 80 / 91 / 46
versus 32 / 62 / 56. Whether the extra strength at recognitions is real or
reflects which seconds recognitions land in (quieter; 41 percent flat at 20 s
versus 26 percent day-wide) needs activity matching.

**The prebirth-depth stack does not survive recognition.** The shared log's
"flow stacked with displayed depth" result (222 of 416 versus 124 of 343 by
recognition) becomes, after recognition, 129 / 172 / 114 (aligned) versus
99 / 137 / 107 (opposed) at 20 s and 167 / 97 / 151 versus 134 / 64 / 145 at
60 s. The contrast lived inside the birth-to-recognition interval.

**The realised move reverses more often than it continues.** Where the midpoint
had already moved with the birth polarity by recognition (382 cases), the next
20 s went 94 with / 160 flat / 128 against and the next 60 s 134 / 87 / 161.
Where it had moved against (278), the next 20 s went 106 / 96 / 75 and 60 s
133 / 36 / 108. Short-horizon midpoint mean reversion after a displacement is
the simplest reading (bid-ask bounce and queue refill), and it is the opposite
of what a persistence story would predict.

**Cases.**

- `dip-19648-1697636574`, buy birth of 51 classified lots, recognition G286246 /
  cursor 374629 with quote 3.124 x 2 / 3.125 x 5. Rolling flow had flipped to
  6 buy / 9 sell; the touch opposed the birth. The midpoint was flat at +1 s,
  then −1.0, −6.5 and −7.5 ticks at +5, +20 and +60 s. Flow reversal plus an
  opposed touch, and the price followed the touch.
- `dip-19648-1697638738`, buy birth, recognition G327505 / cursor 429221 with
  3.100 x 43 / 3.101 x 6 (a 43-lot bid under a 6-lot ask). Rolling flow was
  balanced (3 buy / 3 sell). Midpoint +0.5, +6.0, +6.0, +2.5 ticks. Aligned
  touch, moved with it.
- `dip-19648-1697660175`, sell birth at 20:16 UTC, flow still sell-heavy
  (7 buy / 29 sell), touch 3.045 x 4 / 3.046 x 5 aligned with the birth, and the
  midpoint rose 9.0, 18.5 and 17.0 ticks at +5, +20 and +60 s. The strongest
  counterexample on the day: persistent sell flow and an ask-heavy touch, and the
  market rallied into the close.
- `dip-19648-1697623317`, buy birth from a single unspecified-side lot,
  recognition G95819 / cursor 119626 at 3.079 x 5 / 3.081 x 2, aligned touch,
  and −8.5 ticks within one second. A one-lot "burst" is not a burst.
- `dip-19648-1697629784`, sell birth, touch opposed (3.100 x 5 / 3.102 x 4),
  recognition cursor 175623: flat to +5 s, +6.5 ticks at +20 s (against), then
  −6.5 at +60 s (with). The 20 s and 60 s endpoints carry opposite signs; an
  endpoint table hides the path.
- The two cases already in the shared log: `dip-19648-1697625921` is flat at
  every horizon through +60 s and `dip-19648-1697607905` moves +0.5 then −0.5
  ticks. Neither the explained rise before recognition nor the sell-dominant
  late flow predicted anything after recognition.

**Open.** Whether rejected peaks (never selected) behave the same; whether the
touch read at recognitions is stronger than at activity-matched seconds; and
whether a fresh-print definition of flow (not the rolling ratio) does better.
Trader intent and hidden quantity remain unobserved.

## 2. The 375/391 stack on all 749 first-family events

**The book condition of the saved screen is a constant.** Full displayed bid
depth exceeded full ask depth at all 749 family starts (ratio 1.03 to 2.43,
median 1.48). "Total displayed bid size larger" selects nothing on this day,
the inverse stack is empty by construction, and the screen is really a
flow-only screen (60 s buy-heavy, 5 s and 1 s sell-heavy). Any book layer has to
come from the touch or the near ladder, whose signs disagree with each other in
301 of 682 events where both are nonzero.

**Four arms on one eligible population.** Eligible = events whose 1 s and 5 s
aggressor windows have the same nonzero sign ("recent flow"): 377 of 749
(196 selling, 181 buying; the other 372 have no agreeing recent direction,
mostly empty 1 s windows). Outcomes are the midpoint from the last completed
group at or before the strict cutoff to the last group at or before cutoff +
horizon, oriented so positive = continued in the recent-flow direction.

| Arm | n (600 s clusters) | +1 s cont / flat / rev | +60 s | +600 s |
| --- | --- | --- | --- | --- |
| Baseline: recent flow only | 377 (37) | 211 / 59 / 107 | 202 / 31 / 144 | 200 / 12 / 160 |
| + flow: 60 s window opposes recent | 95 (24) | 47 / 17 / 31 | 57 / 7 / 31 | 56 / 4 / 35 |
| contrast: 60 s agrees | 278 (40) | 162 / 42 / 74 | 145 / 22 / 111 | 142 / 8 / 123 |
| + book: touch size agrees with recent | 192 | 120 / 27 / 45 | 115 / 16 / 61 | 98 / 9 / 83 |
| + book: touch size opposes recent | 156 | 81 / 24 / 51 | 78 / 14 / 64 | 85 / 2 / 66 |
| + book: near-10 imbalance agrees | 257 | 138 / 45 / 74 | 128 / 22 / 107 | 132 / 11 / 111 |
| + book: near-10 imbalance opposes | 120 | 73 / 14 / 33 | 74 / 9 / 37 | 68 / 1 / 49 |
| + both: 60 s opposes and touch opposes | 45 | 20 / 7 / 18 | 28 / 4 / 13 | 27 / 1 / 17 |
| + both: 60 s opposes and touch agrees | 42 | 24 / 8 / 10 | 26 / 3 / 13 | 26 / 2 / 14 |
| Saved 50-case screen (recent selling) | 50 (20) | 23 / 6 / 21 | 29 / 5 / 16 | 39 / 1 / 10 |
| Flow-only mirror (recent buying, 60 s sell-heavy) | 45 (20) | 24 / 11 / 10 | 28 / 2 / 15 | 17 / 3 / 25 |

What this says:

- **Recent flow continues at one second, and most of that is already in the
  price.** The baseline's 56 percent continuation versus 28 percent reversal at
  1 s is the strongest short-horizon regularity in the set, but 247 of the 377
  events had already moved with the recent flow in the second before the cutoff
  (97 flat, 33 against). The family anchor sits inside a move in progress, as
  the 375 review said; the "signal" is largely the displacement being measured
  twice.
- **The 60-second transition layer weakens short continuation rather than
  adding to it.** With the 60 s window opposing, 1 s continuation is 47 / 31;
  with it agreeing, 162 / 74. Flow that has just turned against the minute's
  flow is less persistent at one second than flow that agrees with it. The
  layer's apparent payoff is at 600 s, where it is the day drift (next point).
- **The 600-second "continuation" of the 50 is the day's downtrend.** Unoriented,
  426 of 744 events were lower 600 s later (median −1.5 ticks); in chronological
  quarter 3, where 371 of the 749 starts sit, 218 were lower and 144 higher. The
  midpoint went from 3.129 at 13:00 UTC to 3.046 at 19:00 UTC. The 50 selling
  cases "continued" 39 / 10 at 600 s; the 45 buying mirror cases "reversed"
  25 / 17, which is the same thing said the other way. Activity-matched
  controls (same 60 s aggressor tercile, outside the stack) were lower at 600 s
  in 44 of 110, 49 of 103 and 57 of 109 cases across terciles, so the 50's
  39 of 50 is above the control rate but with 20 overlapping clusters and a
  one-day trend it cannot be separated from drift.
- **The two book layers disagree in sign.** Touch size agreeing with recent flow
  (bid thinner than ask while selling) goes with more 1 s continuation
  (120 / 45 versus 81 / 51), on both sides: selling 62 / 24 versus 36 / 30,
  buying 58 / 21 versus 45 / 21. Near-10 depth opposing recent flow goes with
  more continuation (73 / 33 versus 138 / 74), also on both sides. The first is
  the queue-imbalance read (thin touch gives way). The second says a heavy near
  ladder on the side being hit did not protect it, which is consistent with the
  withdrawal mechanics in section 3 (deeper bids are pulled, not consumed). One
  "book behavior" variable does not exist; the rank at which you measure
  decides the sign.
- **Both layers together on 45 cases are a coin flip at one second** (20 / 18)
  and the 42 cases with the opposite touch alignment are 24 / 10. With samples
  this size and shared windows, neither cell separates from the baseline.

Pre-event snapshot staleness matters: 136 of 749 strict-pre books were more than
1 s old and 15 more than 10 s. Case 391's was 25.5 ms old and the family group
itself carried a three-level sweep (section 3), so its "−1.5 ticks at 1 s" is a
−3.5 sweep and a +2.5 rebound measured from a quote that no longer existed.

## 3. Why 375 and 391 diverged: the order messages

Both are first-family anchors during selling, with the same flow screen and a
bid-heavy full book. Replayed from the October 18 tape with fill-to-reduction
linkage by order and price (the audit script's Book), the as-of touch matched the
saved pre-event groups exactly.

**375 (G233425 / cursor 303645 as-of, family group cursors 303646–303656,
13:09:12.081 UTC).** As-of: 3.152 x 7 in 5 orders / 3.154 x 25 in 14 orders;
3.151 x 12, 3.150 x 13 below. In the milliseconds before the anchor (cursors
303634–303642) four one-lot bids at 3.152 had already been filled and cleaned
up; the 7 lots were the residue of a level being eaten. The family group is one
aggressive sell of 8 lots (order 788701294505) printing at 3.152, four passive
fills of 2 + 1 + 2 + 1 lots on orders 788701293125, 788701293255, 788701271942
and 788701294329 with their cleanup cancels, and a fifth bid (788701293148, 1
lot) cancelled with no fill in the group. The trade summary says 8, the linked
fills say 6, the unlinked cancel says 1; the three totals are kept apart (an
aggressor larger than the displayed level, a self-match-prevention cancel, or
a coincident pull are all consistent). The bid level is emptied; the best bid
becomes the already-displayed 3.151.

In the next 250 ms: 53 bid orders holding 156 lots at 3.151 and below were
cancelled without any linked fill (7 at 3.151, 7 at 3.150, 15 at 3.149, then
deeper), 127 new ask orders holding 188 lots were added at 3.150–3.153 (53 lots
at 3.151, i.e. inside the old spread), and 36 prints of mixed aggressor side
walked from 3.152 to 3.149. By +1 s the quote was 3.147 x 3 / 3.148 x 4. The
mechanism is withdrawal plus repricing: bids pulled from below, offers chasing
down into the vacated space, with the prints a small part of the volume. Nothing
rested against the move.

**391 (G244933 / cursor 319188 as-of, family group cursors 319189–319233,
13:14:00.879 UTC).** As-of: 3.139 x 4 in 4 orders / 3.140 x 3 in 3; 3.138 x 15,
3.137 x 7 below. The family group is one sell order, 788701345922, printing
4 lots at 3.139, 15 at 3.138 and 31 at 3.137 (50 lots across three levels, 40
lots of identified passive fills; one filled bid, 788701318037, displayed 1 lot
and filled 15, so part of the third level was hidden), and then the same order
ID adds 150 lots as a resting ask at 3.137. The group closes 3.136 x 13 / 3.137
x 150 (one order). The unexecuted remainder of a 200-lot sell became the new best
offer three ticks below the old one.

In the next 204 ms that 150-lot offer was filled completely by buyers: first fill
at +5.8 ms, 10 lots by +18.7 ms, 104 by +189.4 ms, the last 44 at +203.8 ms, 26
fills in all, with 217 lots printed in the next second. Bids also churned (154
lots cancelled unlinked deeper, 190 added deeper), but the quote at +1 s was
3.137 x 10 / 3.139 x 13: the swept levels were half rebuilt because something
large stood still and was lifted.

**Same screen, different path, and the difference was not in the screen.** Both
anchors were sells into a bid being eaten. In 375 the seller was small (8 lots),
the level emptied, and the rest of the book ran away. In 391 the seller was
large (200 lots), swept three levels, parked the remainder as displayed
liquidity, and the other side executed against it within a quarter second. The
pre-event features (60 s / 5 s / 1 s flow, full depth) do not see the aggressor's
size or whether it will rest; the family group itself does, 25 ms after the saved
pre quote. Whether that is "exhaustion" or simply a seller who finished is not
knowable from the tape.

**How often the pieces recur (694 events with October 18 tape coverage, 359 with
recent flow).** Measured on the family group and the 250 ms after its close, so
these describe mechanism inside the outcome window, not an entry condition:

| Mechanism in the family group or first 250 ms | n | +1 s cont / flat / rev | +600 s |
| --- | --- | --- | --- |
| Family group printed on the hit side | 243 | 177 / 40 / 26 | 129 / 11 / 100 |
| Family group did not | 116 | 27 / 16 / 73 | 61 / 1 / 52 |
| Sweep of 2 or more price levels | 128 | 106 / 12 / 10 | 63 / 7 / 56 |
| Single level printed | 115 | 71 / 28 / 16 | 66 / 4 / 44 |
| Aggressor remainder posted as resting order | 86 events (9 with 10+ lots) | | |
| No hit-side adds at or better than the old touch | 136 | 122 / 10 / 4 | 77 / 5 / 52 |
| Hit-side adds at or better than the old touch | 223 | 82 / 46 / 95 | 113 / 7 / 100 |
| Opposite side added orders better than its old touch (chasing) | 234 | 196 / 18 / 20 | 127 / 10 / 95 |
| No opposite-side chasing | 125 | 8 / 38 / 79 | 63 / 2 / 57 |
| Hit-side unlinked cancels deeper above median (58 lots) | 179 | 140 / 10 / 29 | 96 / 6 / 77 |
| At or below median | 180 | 64 / 46 / 70 | 94 / 6 / 75 |
| Opposite-side fills at or better than old touch (absorption) present | 249 | 168 / 34 / 47 | 141 / 10 / 96 |
| None | 110 | 36 / 22 / 52 | 49 / 2 / 56 |

The one-second outcome is almost fully described by two things visible in the
first quarter second: whether anyone re-posted at or above the old touch on the
side being hit (replenishment), and whether the other side chased into the
vacated prices. At 600 s every cell is near even. The four counterexamples to
"no replenishment, continued" are instances 103, 176, 321 and 590 (at
05:55:01, 10:18:35, 13:00:06 and 16:16:49 UTC); instance 321 is a 39-lot,
five-level buy sweep met by 258 lots of chasing asks and 134 lots of absorption
fills that still reversed 0.5 tick at 1 s and then rose 17.5 ticks by 600 s.
Remainders resting as displayed liquidity after a sweep (the 391 shape) appear
in 86 of 694 family groups, nine of them 10 lots or more (instances 139, 204,
260, 349, 365, 391 and three others); their outcomes are mixed and the cell is
too small to say more.

## 4. Size-one episodes: what was on the next shelf

The 1,012 episodes' as-of-onset features from the mechanism ledger, arranged as
four arms. Retreats among episodes still open at the assumed 1 ms entry are the
actionable subset; all-episode counts describe the mechanism.

| Arm | Cells with retreats after entry / still open |
| --- | --- |
| Baseline: side x onset type | Ask new best 43 / 93, ask standing 34 / 65, bid new best 49 / 116, bid standing 37 / 79 |
| + flow: fill-linked onset reduction (standing only) | Ask 8 / 14 fill-linked versus 26 / 50 unlinked; bid 8 / 14 versus 29 / 65 |
| + book: next displayed level below 10 lots | Ask new best 27 / 49 versus 16 / 44 at 10+; ask standing 13 / 19 versus 21 / 46; bid new best 30 / 64 versus 19 / 52; bid standing 17 / 33 versus 20 / 46 |
| + both (standing, fill-linked x next level) | Ask fill-linked and thin next 5 / 6, fill-linked and deep next 3 / 9; bid 5 / 6 and 3 / 8 |

The next level's displayed size at onset separates retreat from recovery in all
four side-by-onset cells, in the same direction, and the fill-linked onset adds
to it in the small standing cells. Graded by next-level size among still-open
episodes: ask 6 / 9 at 6 lots or fewer, 34 / 59 at 7–9, 18 / 53 at 10–12, 19 / 37
at 13 or more; bid 10 / 19, 37 / 78, 22 / 58, 17 / 40. Not monotone at the deep
end, so this is "thin next shelf retreats more", not a linear relation. The gap
to the next level is one tick in 1,010 of 1,012 episodes, so distance is not the
variable; size is. The touch's prior order count is 2 or fewer in 389 of the 409
standing onsets and carries nothing there. Recorded survivor refresh before onset
exists in only 9 episodes (7 retreated).

Why a thin next shelf should predict the touch disappearing is not obvious; the
touch retreats when its last lot is filled or pulled, which the next level does
not cause. Two readings: a thin next level marks a ladder already being
withdrawn (the move is in progress and the touch is next), or thin next levels
cluster in active minutes when everything moves. Matching on recent print rate
and time of day would separate them. Examples: bid 3.153 at G229693 / cursor
298558 (prior touch 2 lots, next 3.152 x 7, onset by an unlinked 1-lot cancel)
retreated to 3.152 after 1.592 ms; the same price and next size at G231373 /
cursor 300845 recovered to 2 lots after 8.047 ms; ask 3.155 at G230258 / cursor
299293 with a deep next (3.156 x 11) retreated after 10.153 ms. All three are
"still open at entry" cases.

## 5. The 99 planes and 13 data points

Of 14,463 declared external publications during the October 18 tape, 14,063 are
`curve.traded_shape` rows whose front leg is the NG trade itself (shared source,
not confirmation). The rest: 397 hourly station observations (`weather.obs_hourly`,
298 per station, on the hour plus specials), 22 hourly `eia930.us48` rows, 4 MOS
cycles (04:30, 10:30, 16:30, 22:30 UTC), 2 model-disagreement rows, 3 settled-curve
rows (18:30 and 19:00 UTC), 1 daily HDD (05:10) and 1 calendar row (18:00). Points
1, 3, 4 and 8 (CFTC), 11 and 12 (storage) had zero publications during the tape;
October 18, 2023 was a Wednesday, the storage report is Thursday 10:30 ET. Those
six points are day constants and cannot explain anything intraday here. Points
1, 3 and 4 are three columns of one `cot.023651` row; 5 and 7 are two columns of
one EIA-930 row; 2 and 9 are two reductions of the same MOS runs; 11 and 12
share `storage.weekly`. Counting them as 13 independent inputs overstates the
external information by about two to one.

The planes that answered questions in these notes are 29–36 and 46 (order
actions and fills, used in section 3), 38–40 and 43–44 (depth, order counts,
FIFO; section 4), 47 (signed flow; sections 1–2) and 54–58 (the legacy roll20
and book imbalance that the dipole is built from). Planes 66–70 and 78–88 are
later labels and sealed answers and were not used as predictors. The dipole
(58) and the flow substrate (47, 54, 55) are the same prints reduced three ways.

Cross-layer: the dipole's recognition delay (section 1) is a clock-plane fact
(73, 74) that changes a flow-plane claim; the touch and near-depth sign
disagreement (section 2) is why the "book" block in any model is unstable; and
the external-timing finding of the mechanism audit (traded-curve updates share
print clocks) is the same shared-source problem seen in the 13 points.

## 6. Explanations, with mechanics beside psychology

Observed mechanism (on this tape): a sweep empties a level; the quote moves to
the next displayed price; what happens next depends on whether orders are
re-posted at or above the old touch (section 3), whether the other side chases,
and whether a large resting order appears for the move to execute against (391).
Deeper orders on the hit side are pulled more than they are consumed (156 lots
cancelled unlinked versus 6 filled in 375's first 250 ms).

Associations: recent-flow continuation at 1 s; touch-size imbalance predicting
the next 20 s direction at 62–65 percent of non-flat outcomes; a thin next shelf
preceding a size-one retreat; the day's downtrend appearing as "continuation" of
selling at 600 s.

Behavioral hypotheses and what would separate them from mechanics:

| Hypothesis | Footprint seen here | Mechanical alternative | Discriminating evidence |
| --- | --- | --- | --- |
| Fear-driven withdrawal: resting bidders pull when a level breaks | 375: 53 bid orders, 156 lots cancelled unlinked below the touch within 250 ms | Market-making algorithms re-centre quotes around the new midpoint; cancels and re-adds are symmetric repricing, not flight | Track the cancelled order IDs: if the same IDs re-appear at lower prices within milliseconds it is repricing; if they vanish it is withdrawal. Compare the two by subsequent 1 s and 60 s moves |
| Relief or bargain buying after a flush | 391: 150 lots lifted in 204 ms | A resting buyer's own algorithm (for example a spread leg or an iceberg) executing against any offer below a limit | Whether the buyers' order IDs were new or had been resting; whether other maturities moved at the same clock (the curve leg); whether similar-sized resting offers elsewhere in the day were lifted as fast |
| Herding or copying into a visible move | Opposite side chasing (234 events) | Order-anticipation and momentum algorithms respond to the same public tape | Participant-level data; not in the tape |
| Anchoring to the old touch price | Replenishment at exactly the old touch (223 events) | Queue-position economics: re-posting at the old price regains a known queue | Compare re-posts by the same order IDs versus new IDs; the former is queue management |
| Loss-driven liquidation feeding the downtrend | Quarter 3 drift, 218 of 371 events lower at 600 s | A weather or storage expectation revision during the New York session; curve-wide repricing | The four MOS cycles do not fall inside quarter 3; the settled-curve rows do (18:30, 19:00 UTC). Check other maturities' moves at those clocks |

Private intent, account P&L, stop instructions and participant identity remain
unknown; nothing in the tape distinguishes an algorithm from a person.

## 7. Agreement and disagreement with the Codex notes

Written after reading [codex-flow-book-discovery-20261108.md](codex-flow-book-discovery-20261108.md).

Agree, independently reached: full book bid-heavy at all 749 starts; the 50-case
screen reproduces exactly and its 1 s / 5 s outcomes are 23 / 6 / 21 and
23 / 3 / 24; 671 of 863 recognitions flat at one second and birth-to-recognition
tables are not forecasts; the 391 sweep-and-rest mechanism (same order ID, 150
lots, fully filled within about 204 ms); the 40 versus 50 lot gap in 391's
family group; the 13 points' shared sources and intraday constancy; the
traded-curve clock sharing the print clock.

Differences in emphasis or result:

- Codex frames the stack question as a ridge-model error comparison (book worsens
  signed MAE at every horizon). These notes frame it as counts on one eligible
  population and find the book layer's sign depends on rank (touch versus near
  10). Both say the stack adds nothing reliable; the reasons given differ and
  both should be kept.
- Codex reports touch alignment on the 50 (12 / 6 / 3 versus 9 / 13 / 2) and says
  the inverse-flow cohort does not reproduce it. On the full 377-event eligible
  set the touch-aligned continuation is higher on both sides (62 / 24 versus
  36 / 30 selling; 58 / 21 versus 45 / 21 buying). The 50 and the 45 are too
  small to carry this; the full set is where the pattern lives.
- Codex did not test the touch read at recognition for the dipoles or the
  day-wide control; these notes find it is the only thing at recognition with a
  directional association and that it is mostly a general property of the book.
- Codex's 375 reading emphasises offer growth before the anchor and the 8 / 6 / 7
  lot totals; these notes add the 250 ms after: 156 lots of unlinked bid
  cancellation and 188 lots of new offers inside the old spread, which is the
  mechanism of the five-tick fall.
- Codex's activity controls are matched one-to-one within hour and spread; these
  notes use terciles and same-hour pools and reach the same conclusion that the
  600 s result is not separable from drift.
- Codex did not run the size-one four arms; the next-shelf finding (section 4)
  is new and unreviewed.

## 8. Four-date index

Codex captured interim table locations, coverage and job states at 18:03 UTC in
[flow-book-discovery-v1/date-tables/](flow-book-discovery-v1/date-tables/)
(October 2: root-native failed exit 1 at 17:54 UTC, standalone held; October 3
and 17: root-native running, standalone waiting). These notes reuse that index
rather than duplicating it. October 18 evidence is the pinned set above. The
heartbeat owns monitoring, recovery, save-and-publish and pod shutdown; nothing
here launched, monitored or stopped anything.

## 9. Next comparisons that would move an explanation

1. Re-run section 1's touch read on activity-matched seconds (same prints in the
   prior 20 s, same hour) to see whether recognitions add anything to the plain
   queue-imbalance read.
2. Follow cancelled order IDs in the 250 ms after a sweep: re-posted lower
   (repricing) versus gone (withdrawal), and whether that split predicts the 60 s
   path. This is the test that separates the "fear" row from the "re-centring"
   row in section 6.
3. For every family group that printed, record aggressor order size, levels
   swept and remainder posted, then test whether any of it was visible at the
   previous completed close (the real decision point). The expectation from 375
   and 391 is that none of it was.
4. Repeat sections 2–4 on October 3 when its standalone export lands, with the
   same definitions, before any threshold is kept.
5. Match size-one onsets on recent print rate and hour to see whether the thin
   next shelf survives.

## 10. Carried from earlier sessions: dipole applications and the NG look-ahead budget

Two different objects are called "the dipole" in this repository. The S92 direction nowcast
`dip_imb_level` (about 300 s of Lee-Ready flow overlapping a leg's trigger push; 7 percent versus 93
percent up by tercile, 34 of 34 out of sample on strong flow) and the S36 divergence and exhaustion
filter are the project's dipole applications. The October 18 candidate detector studied in sections 1
and 2 is a third thing: a peak of a 20-second rolling signed-lot ratio, recognized a median 2.407 s
after its nominal second. The null found here (no post-recognition direction) is about that detector
and does not touch the S92 nowcast; equally, the S92 result does not validate the detector. The S90
NG canary already found the static divergence read did not transfer to NG and the exhaustion read gave
only a faint pulse; the S92 pass ruled `dip_aligned_flow`, `dip_mi_flow` and `exhaustion` noise for
direction, sustain, turn and peak on 12 warm-season days.

The look-ahead budget measured so far (WTI sub-minute first reprice about 7 s and continuing about 20 s;
NG release move two-thirds complete within 60 s, sometimes within 1 s; Kalshi settles on the Pyth NGDQ6
5:00 pm EDT candle) is tabulated in [Appendix A of the primer](claude-code/market-fundamentals-primer.md#appendix-a-project-carry-over-the-dipole-applications-and-the-ng-look-ahead-time-budget).
Against that budget the detector's 2.4 s median recognition delay is 12 to 35 percent of the window and
its 87 s tail exceeds it. The size-one replay's 1 ms entry and the 0.366 ms median lead of the next print
are the same problem at a finer scale. Every candidate here should be scored on its recognition clock.

## 11. The whole day under the frozen exhaustion contract, with the three clocks kept apart

Re-analysis of the full October 18 session (21:00 UTC October 17 to 21:00 UTC October 18, both UTC
tape members, 30,739 prints exactly as archived) with the frozen NG exhaustion detector from the
canonical chain sources (`artifacts/sqlite-triage/20261022/families/full-context-audit/canonical-sources/research/`):
roll-20 classified flow, the 85th percentile of |roll20| for the day, a 5 s local maximum, a 45 s
refractory resolved by prominence, polarity = sign of roll20 at t0, endpoint = three consecutive
forward-filled oriented roll20 at or below zero, seed state P/O/S/X from the first zero within +60 and
the late pressure over t0+41..t0+60, aftermath in 2-tick classes at confirmation + 5..300 s. Script and
tables: [exhaustion_clock_reanalysis_oct18.py](claude-code/exhaustion_clock_reanalysis_oct18.py),
[summary](claude-code/exhaustion-clock-oct18-summary.json), [events](claude-code/exhaustion-clock-oct18-events.jsonl.gz);
flow-only runs on the October 2 and 17 per-second tables Codex captured from the boxes:
[script](claude-code/exhaustion_clock_flow_only.py), [October 2](claude-code/exhaustion-clock-20231002-flow-only.json),
[October 17](claude-code/exhaustion-clock-20231017-flow-only.json).

**The detector reproduces.** 813 of the 863 archived births are reproduced second for second; the other 50
are refractory tie-breaks among equal-magnitude candidates. The frozen canonical table would then drop 309
of the 890 detected events because the oriented roll20 is undefined 60 s before t0 (no classified volume
in that window); the archived Native adapter keeps them. Both are reported here, flagged.

**The threshold is saturated.** On all three days the 85th percentile of |roll20| is exactly 1.0 (27.7 and
27.8 percent of all flow-bearing seconds are fully one-sided on October 2 and 17). So the frozen detector
fires only on completely one-sided 20-second windows, which are mostly tiny: 351 of 766 October 2 events
and 350 of 766 October 17 events have one classified lot in the burst window. It therefore fires in quiet
periods and goes silent when the market is busy: October 18 had 11 events in the 13:00 UTC hour (the
hour of 375 and 391 and the day's heaviest trading) against 48 to 54 in the overnight hours. One event sits
in the 13:00 to 13:20 window (13:18:32 UTC, sell polarity, 972 lots of 300 s volume, runway 7 s, price
reversed 16 ticks by seed-known +300 s). Whatever "exhaustion" means on these days, this detector measures
the end of one- and two-lot bursts in thin tape, not the end of the pushes that moved the price.

**Three clocks, three days.** The clock structure is nearly identical across the three dates:

| Clock | October 18 (full, 890 events) | October 17 (partial, 766) | October 2 (partial, 766) |
| --- | --- | --- | --- |
| Information horizon, local maximum | t0+5 s | t0+5 s | t0+5 s |
| Information horizon, refractory-final | t0+50 s; archived actual recognition median 51 s, range 7 to 137 s | t0+50 s | t0+50 s |
| Exhaustion runway (structural onset minus t0), median and quartiles | 33 s (17 to 77) | 34 s (16 to 78) | 31 s (15 to 71) |
| State-confirmation offset (confirm minus t0) | 35 s (19 to 79), max 675 | 36 s (18 to 80), max 564 | 33 s (17 to 73), max 507 |
| Runway by seed state, median | P 121 s, O 24, S 20, X 20 | P 110, O 24, S 20, X 21 | P 110, O 22, S 20, X 20 |
| Exhaustion already confirmed before t0+5 | 49 (5.5 percent) | 57 (7.4 percent) | 56 (7.3 percent) |
| Already confirmed before t0+50 | 556 (62 percent) | 477 (62 percent) | 484 (63 percent) |
| Already confirmed before the seed state is knowable (t0+61) | 604 (68 percent) | 519 (68 percent) | 530 (69 percent) |
| Archived recognition arrived after confirmation | 449 of 813 | not available | not available |
| Inter-event gap, median; gaps under 60 s | 72 s; 323 | 72 s; 271 | 72 s; 249 |
| Next event starts before the current one confirms | 270 (30 percent) | not computed | not computed |

By the time an event is knowable under its own contract, it is over in about five of eight cases, and the
seed state that the chain grammar is built from is knowable only after seven of ten have ended. The
only family with runway left at the information horizon is P (persistent, no zero within 60 s): 265 of
the 334 events still running at t0+50 are P.

**Price over the three intervals (October 18 only, last-trade price, oriented to polarity).**

| Interval | With polarity / flat / against |
| --- | --- |
| t0 to confirmation (the runway) | 236 / 255 / 399 (midpoint: 318 / 202 / 370) |
| t0+50 to +30 s, events already over at t0+50 (556) | 159 / 215 / 181 |
| t0+50 to +30 s, events still running at t0+50 (334) | 56 / 210 / 68 |
| confirmation +5 s to +30 s (the SSOS and P-O-X entry window) | 226 / 441 / 223 |
| Aftermath from confirmation, 2-tick classes, +60 s | continuation 155 / chop 565 / reversal 169 |
| Aftermath from confirmation, +300 s | 310 / 309 / 266 |

During the runway the price more often gives back than continues (399 against versus 236 with): the
flow burst that defines t0 is already the tail of its own move. After the information horizon and after
confirmation there is nothing in either direction, in both the already-over and still-running subsets.

**The seed-state split is contemporaneous, not predictive.** From confirmation, O (collapsed, opposite
flow) shows reversal 84 against continuation 36 at +60 s and S (collapsed, same-flow reload) shows
continuation 71 against reversal 31. Measured instead from t0+61, the first second at which the seed
state exists, the same families give O 85 with / 104 against and S 81 / 79, P 65 / 68, X 47 / 46. The
late-pressure window that defines the seed (t0+41..60) overlaps the price path from confirmation
(median t0+35), so the apparent aftermath split is flow and price moving together inside the seed's own
window. Codex's "aging-only flips" result is the same mechanism seen from the other side.

**The dipole applications at these anchors.** The 300 s flow imbalance (the S92 direction nowcast's
operand) has no relation to the price over the runway (agree 299 / disagree 336; strong flow 172 / 198) or
to the 30 s after the information horizon (strong 136 / 114), and its sign agrees with the 20 s burst
polarity in only 510 of 856 defined cases on October 18 (428 of 733 on October 2, 414 of 743 on October
17). Among the 189 P-family events with strong 300 s flow, the next 60 s after the seed is knowable went
41 with the flow sign and 41 against. The resting-book contrarian read at t0 (10-level imbalance over
t0-19..t0) does not separate either: aligned 73 / 148, opposed 77 / 131, flat 86 / 120, all showing the
general runway give-back. This is not a test of the S92 nowcast, whose anchor is a price leg's birth;
it says the nowcast's operand carries nothing at flow-exhaustion anchors.

**The frozen chain plays on this day.** S,S,O,S occurred 14 times (confirmation+5 to +30: 4 with / 5 flat /
5 against) and P,O,X 11 times (4 / 4 / 3). Too few to say anything, consistent with the chain work's own
expectation of about 2.5 percent frequency, and recorded as such.

**Examples (October 18, seconds are the session index from 21:00 UTC October 17).**

- Longest runway: 01:48:50 UTC (s 17330), sell polarity, P, runway 673 s, confirmation 675 s, archived
  recognition at +53 s, 300 s flow +0.10 against the burst, price minus 1 tick over the runway and +1 tick
  by seed-known +300 s. An exhaustion that outlived its own recognition by ten minutes and went nowhere.
- Over before knowable: 00:22:19 UTC (s 12139), buy polarity, X, runway 1 s, confirmation 3 s, archived
  recognition at +104 s. The burst was a one-second event recognized a minute and three quarters later.
- O with reversal: 00:53:58 UTC (s 14038), buy polarity, runway 41 s, confirmation 43 s, recognition at
  +51 s, price minus 3 ticks over the runway and minus 2 by seed-known +300 s. The reversal was already
  in the price before the state was confirmed.
- S with continuation: 22:37:12 UTC (s 5832), buy polarity, 300 s flow +0.76, book minus 0.59 (ask heavy),
  price minus 3 ticks over the runway, then +2 by seed-known +60 s. Continuation after a give-back.
- Release window, 14:30 to 15:00 UTC: eight events, 300 s volumes 287 to 481 lots, runways 3 to 66 s, every
  recognition 32 to 53 s after t0; outcomes from seed-known +300 s range from minus 11 to +14 ticks with
  no relation to polarity. The storage-report hour is where the detector is least able to keep up.

**What this changes.** (1) The dipole-direction null in section 1 and the clock finding here are the same
fact: this detector recognizes an event about 50 s after a burst that typically ended 33 s after it began,
so nothing measured from recognition can carry the burst's direction. (2) The frozen contract's own
numbers put the information horizon (50 s) past the state-confirmation time (35 s) for most events; any
chain research built on it is research into what follows an already-ended burst, which is what the SSOS
and P-O-X plays correctly assume by entering at endpoint+5. (3) The saturated threshold means the
exhaustion population is a quiet-tape population; a detector meant for the moves that matter needs a
threshold that does not saturate (a volume floor on the window, or a quantile of a non-saturating
statistic). (4) None of this touches the S92 price-leg nowcast, which is anchored differently; it does say
that reusing its 300 s operand at exhaustion anchors is empty.

Open: the same pass with prices on October 2, 3 and 17 when their print exports land (the flow-only
clock structure is already in place for 2 and 17); a volume-floored variant of the detector; and whether
the P family's long runway carries direction once the pre-arc-undefined and defined halves are matched
on activity.
