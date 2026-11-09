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

## 12. The frozen runway-clock duration math, tested on the whole October 18 session

Greg's pointer to the frozen NG exhaustion clock came with its original duration math: the V0 runway clock
(commit 637778d6, `ng_exhaustion_runway_clock.py`, documented by Codex in
`research-atlas-v2/sources/ng-frozen-runway-clock.md`). That clock assigns a revealed Family A event to one of
two post-states by a frozen 61-sample classifier on the oriented roll-20 curve at t0..+60 (normalized by the
t0 value, nearest of two centroids; `FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json`, SHA
698b956f, read from the pinned commit and hash-checked), and states reveal totals in seconds from t0 for how
long the exhaustion lasts at four tick scales:

| state | 3t | 5t | 8t | 13t |
|---|---|---|---|---|
| A-fast-collapse (frozen) | 358 | 993 | 1802 | 4386 |
| A-persistent (frozen) | 700 | 1802 | 3455 | 6836 |

with remaining = max(0, total minus elapsed), and a replay proof that required persistent > fast-collapse at
every scale on each held-out day. This is a fourth clock, distinct from the three in section 11: the
information horizon (t0+50), the state-confirmation time (median 35 s) and the exhaustion runway (onset,
median 33 s) are all about the burst itself; the duration math is about the post-state, how long the price
takes to travel k ticks after the burst. I kept it separate and tested it as written on all 890 events the
frozen detector finds on the full October 18 session (scripts `runway_duration_test_oct18.py`,
`frozen_a_classifier_oct18.py`, `a_state_direction_knowable_oct18.py`; outputs beside them). Durations are
the first second after t0 at which the forward-filled last-trade price (and separately the midpoint) is k
ticks from its t0 value, in either direction and in the burst-polarity direction; session-end censoring is
handled with Kaplan-Meier medians. Nothing refit. No trade cost anywhere.

**Caveat stated first.** The frozen pipeline applies the A classifier only to events the pre-family A/B/C
classifier (78 features on t-60..t0, RobustScaler, separate frozen artifact) puts in Family A. That artifact
exists at 637778d6 (`FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json`) but I have not
applied it yet, so here the A classifier labels every detected event. The frozen reveal population was 831
fast and 785 persistent on four other days. If the pre-family gate matters, the numbers below move; the
ordering test is the part most likely to survive it.

**The classifier splits the day in half and agrees with the seed proxy one way.** 442 A-fast-collapse, 448
A-persistent. Every event whose oriented curve reaches zero within +60 and is labeled fast is also a
collapsed seed (O, S or X): 442 of 442. The persistent label is wider than seed P: 265 P plus 183 collapsed
seeds. So "P" is a sufficient but not necessary mark of the persistent state under the frozen classifier.

**The ordering holds at every scale, with both labelings and all four series.** Persistent > fast-collapse
(and seed-proxy persistent > collapsed) for price-with, price-either, mid-with and mid-either at 3, 5, 8 and
13 ticks, 16 of 16 comparisons. That is the frozen proof's own criterion and October 18 passes it.

**The absolute totals: persistent close, fast long.** Kaplan-Meier medians, with-polarity price, seconds from
t0:

| state | 3t | 5t | 8t | 13t |
|---|---|---|---|---|
| A-fast-collapse realised | 450 | 1128 | 2798 | 6388 |
| A-fast-collapse frozen | 358 | 993 | 1802 | 4386 |
| A-persistent realised | 579 | 1341 | 3536 | 6956 |
| A-persistent frozen | 700 | 1802 | 3455 | 6836 |

The persistent totals are within 3 to 26 percent of the frozen values at all four scales. The fast-collapse
totals run 14 to 55 percent longer than frozen, and the gap widens with scale. Either-direction medians are
far shorter (fast 85 / 240 / 598 / 1415, persistent 201 / 545 / 1282 / 3425), which says the frozen totals
were polarity-oriented durations, and that the first k-tick excursion after a burst is often not in the
burst's direction. Censoring is material only for with-polarity at 8 and 13 ticks (70 and 95 fast events
never reach the level before 21:00 UTC).

**The countdown at +60, the first moment the state exists.** Remaining time under the frozen rule
(total minus 60) against the realised Kaplan-Meier median remaining among events not yet at the level:

| state | 3t | 5t | 8t | 13t |
|---|---|---|---|---|
| fast, frozen remaining | 298 | 933 | 1742 | 4326 |
| fast, realised remaining | 620 | 1229 | 2903 | 6328 |
| persistent, frozen remaining | 640 | 1742 | 3395 | 6776 |
| persistent, realised remaining | 759 | 1470 | 3519 | 6896 |

Persistent is a usable countdown on this day (within 4 to 16 percent). Fast-collapse undercounts by about
2x at 3 ticks and 1.5x at 8 and 13. Only 62 fast and 54 persistent events (14 and 12 percent) had already
moved 3 ticks by +60; at 8 ticks it is 3 and 3, at 13 ticks none. So the clock is almost never already over
when it starts, which is the opposite of the burst clocks in section 11.

**Direction: contemporaneous at t0, null once knowable.** Measured from t0, the first k-tick excursion is in
the burst direction 39 to 44 percent of the time for fast-collapse and 52 to 59 percent for persistent; by
seed, O is 33 percent (two-thirds reversal), P 53, S 49, X 50. That looks like a direction read. It is not
one that can be used: the state is defined on t0..+60, and a large part of those first excursions happen
inside or just after that window. Re-anchored at +60 (and at max(+60, archived recognition)), measured
from the price at the anchor, every group is at 44 to 56 percent with-polarity for the first 3/5/8-tick
excursion, and the oriented tick change at anchor+60/+300/+600 has median 0 for both A states and all four
seeds (fast at +300: 198 with / 45 flat / 196 against; persistent: 183 / 77 / 186; O at +300: 107 / 32 / 110).
The A state and the seed state tell you how long the price will take to travel, not which way. Same
conclusion as sections 1 and 11, reached a third way.

**What this means for the program.** (1) The frozen duration math is a time-to-distance clock and on October
18 it is well calibrated for the persistent state and slow for the fast state; as a countdown it is honest
about the former and optimistic about the latter. (2) It is the one clock in this reanalysis that is NOT
over before it is knowable, because it measures the post-state, so it is the one with a possible operating
use on the Kalshi lag: a time-to-k-ticks forecast at +60 with the direction supplied elsewhere (the S92
price-leg nowcast, or nothing). (3) The missing pre-family gate is the next check; if Family A is a minority
of these 890, the fast-collapse gap may be a Family B/C contamination rather than a day effect. (4) Repeat
on October 2, 3 and 17 when prices land; the either-direction medians are a day-activity measure and should
be read against the day's print count before any cross-day comparison.

### Coverage: the missing evening prefix, and whether the other two have it

Greg asked whether the missing data could be filled and whether Desktop and Codex are missing it too.
Filled: the October 18 session begins 21:00 UTC October 17, and the print export's 30,739 prints cover it,
but the Databento member file named for October 18 starts at 00:00 UTC, so a replay from that member alone
starts three hours into the session with no state, drops the 21:00 to 24:00 prefix, and (if the clip at
21:00 UTC October 18 is missed) picks up 327 prints of the next session. My exhaustion pass now replays the
October 17 member (cursor offset minus 841,601) ahead of the October 18 member, clips at 21:00 UTC, and
matches 30,739 prints and 813 of the 863 archived births. Coverage of the other two passes as read from
their files on the branch:

- Desktop (`october-discovery-log-claude.md`, `claude-pass/`): states one UTC member, so its replay is missing
  the evening prefix and any statistic it computes over "the day" from the tape omits 21:00 to 24:00 UTC
  October 17 and begins with an empty book at 00:00. Its group-export work is unaffected because the export
  is already session-complete.
- Codex (`codex-flow-book-discovery-20261108.md`, `flow-book-discovery-v1/`): the raw-record inventory and the
  extracts are built from the October 18 member only, so the same prefix is missing there; the group-export
  tables (583,688 groups) are full-session. Its per-second legacy signed-flow files for October 2 and 17 are
  from the group export and are full-session.

So the answer is yes on both counts for the tape-replay side and no for the group-export side. Any merge of
the three passes should note which side each number came from before comparing counts.

## 13. What the frozen state says besides direction, what the pre-birth window says, and the stack

Greg's two prompts after section 12 were that the state might say something other than direction, and
to look before birth as well. Both were tested on all 890 October 18 events from the knowable anchor
t0+60, and every claim below was then re-run on the October 17 session as the out-of-sample check (the
October 17 numbers in this section are from the pass without the evening prefix, archived in
`claude-code/no-prefix-oct17/`; section 14 carries the full-session pass). Scripts:
`beyond_direction_prebirth_oct18.py`, `other_things_oct18.py`, `stack_direction_sources_oct18.py`,
`next_burst_forecast_oct18.py`, `cell_flip_diagnosis.py`; outputs beside them. All scripts take `NG_DAY`.
No trade cost anywhere; nothing refit.

### 13.1 The state is an activity and persistence readout

Known at +60, the persistent state marks a quieter aftermath. Medians over the next 600 s, October 18,
fast-collapse first then persistent: range 9 vs 6 ticks, largest excursion 8 vs 5, path length 44 vs 20,
volume 325 vs 88 lots, time to the first 1-tick move 14 vs 31 s, share of seconds within a tick of the
anchor price 0.11 vs 0.18. Rank AUCs (probability a persistent value exceeds a fast one):

| measure, 600 s from +60 | Oct 18 | Oct 17 |
|---|---|---|
| volume | 0.27 | 0.30 |
| path length | 0.28 | 0.30 |
| range | 0.33 | 0.36 |
| dispersion of 1 s changes | 0.30 | n/a |
| time to first tick | 0.65 | 0.64 |
| hold share | 0.61 | 0.56 |

That is the "something other than direction": the state forecasts how much the tape will move and how
long the price will sit, in the next ten minutes, and it does so on both days.

**Most of it is pre-birth activity carried forward.** Fast-collapse events come from busy tape: the
pre-event 300 s volume separates the states at AUC 0.28 (Oct 18) and 0.30 (Oct 17), hour of day at 0.38,
and forward 300 s volume correlates 0.84 and 0.83 with pre-event volume. Inside the low and mid activity
terciles the state's forward AUCs collapse toward 0.5 (Oct 18 low tercile: volume 0.48, range 0.47; mid:
0.39, 0.44); a residual survives in the high tercile (volume 0.32, dispersion 0.32) and on October 17 in
the mid and high terciles (volume 0.38 and 0.39). So: the activity read is the larger part, the state
adds a smaller part among busy events.

**Pre-birth predicts the clocks, not the direction.** Spearman correlations with the post-state clocks,
both days within a few hundredths of each other (Oct 18 / Oct 17):

| pre-birth feature | time to 3 ticks either way | 600 s range from +60 | oriented 300 s change |
|---|---|---|---|
| 300 s volume | -0.52 / -0.52 | +0.60 / +0.58 | 0.00 / -0.01 |
| 300 s path length | -0.54 / -0.54 | +0.63 / +0.61 | 0.00 / -0.01 |
| 60 s volume | -0.48 / n/a | +0.51 / n/a | 0.00 |
| prominence | +0.26 | -0.28 | 0.00 |

Prominence is a relative measure (burst against a quiet background), so a high value is a quiet-tape
mark and belongs with the activity family. The oriented roll-20 pre-arc itself (base, slope, minimum)
separates the states at 0.49 to 0.57 on both days, i.e. the shape before t0 is nearly uninformative about
the shape after t0; what the frozen A classifier reads at t0..+60 is not readable before t0 from the arc,
but the activity level that accompanies it is.

**Frozen pre-family.** The frozen pre-family classifier (SHA 583f6a12, loaded through the frozen live
clock's own integrity-checked loader) puts 832 of 890 October 18 events in Family A (39 B, 19 C) and 711
of 765 on October 17 (26 B, 28 C). The section 12 caveat is therefore minor: the Family-A-only duration
test is unchanged on October 18 (ordering 4 of 4; persistent 579 / 1291 / 3605 / 7001 s vs frozen 700 /
1802 / 3455 / 6836; fast 479 / 1130 / 2963 / 6446 vs 358 / 993 / 1802 / 4386).

### 13.2 The book, the spread, and the next event

Persistent events happen on thinner books and wider spreads (toward-side 10-level depth AUC 0.33 and
0.37, away-side 0.34 and 0.38, spread at t0 0.59 on both days): the quiet-tape signature again. After the
anchor the state says nothing about recruitment or consumption: the 300 s and 600 s depth-change AUCs are
0.47 to 0.57 on both sides, both days.

**The state forecasts the polarity of the next burst.** Share of next frozen-detector events that flip
polarity, base rate 0.45 (Oct 18) and 0.47 (Oct 17):

| after | Oct 18 | Oct 17 |
|---|---|---|
| A-persistent | 0.33 | 0.38 |
| A-fast-collapse | 0.56 | 0.56 |
| seed P | 0.28 | 0.35 |
| seed O | 0.64 | 0.69 |
| seed S | 0.36 | 0.27 |
| seed X | 0.54 | 0.57 |

This survives the activity terciles (AUC 0.35 to 0.40 in each on Oct 18) and replicates in sign and
roughly in size. The median gap to the next event is 72 to 73 s from t0 on both days, and 37 percent of
next events have already begun by +60. A flow that has not exhausted (persistent, P) continues as the same
side's next burst; one that collapsed or met late opposite pressure (fast-collapse, O) is followed by the
other side. That is a statement about the sequence of flow bursts, knowable at +60.

### 13.3 Does any direction source stack with it

Nine direction sources available at the anchor were crossed with the activity read: the burst's own
polarity; the state's forecast of the next burst's side (two forms); the 300 s flow imbalance (the S92
nowcast operand) and a strong-flow variant (this day's top tercile of |imbalance|, not the S92 cut); the
10-level resting-book imbalance; the touch imbalance; the S92 recruitment read (toward-side minus away-side
depth change over t0..+60, times polarity); and 300 s price momentum. Targets: the signed change from the
anchor at +300 and +600 and the side of the first 3-tick excursion. Cells: A state, activity tercile,
state x tercile, hour class, and every two-source agreement.

**Pooled over the day, nothing.** Every source sits at 0.46 to 0.52 non-flat hit share on both horizons
on both days (book 0.54 on the first 3-tick side, Oct 18 only).

**Per cell, October 18 showed structure.** Book imbalance in persistent cells 0.56 to 0.57 (n about
400) and inverted in busy fast-collapse cells (0.36 at +600, median 3 ticks against, n 194); strong flow
in the mid-activity band 0.65 to 0.69 and 0.77 in fast-collapse x mid (n 31 to 83); momentum with the move
in busy tape (0.55) and against it in quiet tape (0.41). Across the 371 cells with 30 or more decided
outcomes, 46 were beyond 0.42 / 0.58 where 23 would be by chance: twice chance, so the day had structure.

**None of it survived October 17.** The same cells: book in persistent 0.48 / 0.46, book in busy
fast-collapse 0.57 (sign reversed), strong flow in the mid band 0.39 / 0.56, momentum in busy tape 0.46 /
0.49. Across the 360 cells common to both days, the sign of (hit minus 0.5) agrees 52 percent of the time
and the rank correlation of hit rates across days is minus 0.08. October 17 also had 46 cells beyond the
band against 24 expected, so each day has structure of its own and they do not share it.

**The difference between the days is the drift.** `cell_flip_diagnosis.py` splits every cell's hit rate
by the sign of the call. October 18 opened the session at 3059 and closed at 3072 (plus 13 ticks) with
every overnight hour from 23:00 to 12:00 UTC rising except two; October 17 opened at 3120 and closed at
3061 (minus 59), with minus 66 in the 13:00 hour. Book imbalance in persistent cells on October 18: buy
calls hit 0.63 (n 180), sell calls 0.51 (n 261); on October 17 buy calls 0.44 (n 210), sell calls 0.53
(n 157). Book in persistent x low activity: buy calls 0.77 on the 18th (n 40), 0.40 on the 17th (n 108).
Momentum in quiet tape: the 18th's "mean reversion" was sell calls failing at 0.30 on a rising overnight;
the 17th's was buy calls failing at 0.34 on a falling day. Burst polarity in the persistent state on the
17th (0.37, the day's largest cell): buy bursts at 0.33, on a day that fell. In each case the lift lives
on the side that the day drifted toward, and the calls are not balanced within the cell (book buy-call
share ranges 0.19 to 0.68 across cells and days), so the cell hit rate is a drift detector. Activity level
is not the difference: the tercile cuts are 38 / 163 lots on the 18th and 34 / 153 on the 17th, and
recutting each day at the other's cuts changes nothing. Centering each cell on its median move does not
remove it either, because the median is 0 at this tick resolution and the asymmetry is in the sign split.
This is the Simpson's-on-a-trending-window artifact the dipole discipline already records for the crypto
era, reproduced on NG at one-day scale.

**What is left.** Nine cells sit beyond 0.06 on the same side both days, where about eleven would by
chance; two of them share a cell and point the same way: fast-collapse x mid activity, book imbalance at
+300 (0.57 and 0.57, n about 90 each) and the next-seed forecast (0.60 and 0.60, n about 50). That is a
watch-list entry for October 2 and 3, not a finding.

### 13.4 Does the next-burst forecast convert into price

Section 11 found that a burst's price move is contemporaneous with the burst. A correct forecast of the
next burst's side, held from +60, should then capture the next burst's own move if the later burst moves
price the way the first did. It does not. Restricting to next events that begin after the anchor (558 on
Oct 18), the forecast is right 54 percent of the time (57 after persistent, 51 after fast-collapse), and
the price change over the next burst's own window, oriented by the forecast, is 187 with / 150 flat / 221
against. Conditioning on the forecast being right makes it worse: 82 / 76 / 143, the price moves against
the correctly forecast burst 64 percent of the time; when the forecast is wrong the price goes with it
(105 / 74 / 78). The later same-side burst is absorbed. Longer horizons from the anchor (+1800, +3600) are
at 0.51. The sequence of flow is forecastable; the sequence of price is not, from these anchors.

### 13.5 The broad reading

Put together: this family of frozen objects reads the tape's activity and the persistence of a flow. It
says when the price will travel k ticks (the duration math, calibrated for the persistent state), how far
and how hard the tape will move in the next ten minutes, how long the price will sit, and which side the
next burst will come from. It says nothing about which way the price goes, and the per-cell direction reads
that appeared on one day were the day's drift. The direction half of any stack has to come from a source
that is not a function of the same tape at the same anchor. On the Kalshi lag that source already exists:
NYMEX itself. The move happens on NYMEX first and Kalshi follows seconds to a minute later, so the direction
does not need to be forecast, it is observed; what the lag trade lacks is advance notice of when a move is
coming and how big it will be, which is exactly what the activity read and the clocks supply. The test is
the activity read as the arm-and-size layer and the observed NYMEX move as the trigger, scored on Kalshi
fills for the same dates. That needs Kalshi-side data for October 2023, which is not in the repository, and
is the next comparison I would run.

## 14. The October 17 session, full tape, as the out-of-sample day

### 14.1 Coverage and the re-pull

The tape commit (1d15dc6f) held only the October 2, 3, 17 and 18 UTC-day members, each starting at 00:00
UTC with Databento's range-start snapshot, so the October 17 session (22:00 UTC October 16 to 21:00 UTC
October 17) had no tape for its first three hours, and the October 2 session (Sunday evening October 1)
likewise. At Greg's request the two missing UTC days were pulled on 2026-11-08 with the tape commit's own
recipe (GLBX.MDP3, NG.v.0 continuous, mbo, one UTC day per file): 2023-10-16 is 925,662 records, 2023-10-01
is 12,532 records (the Sunday evening), USD 0.09 in total, committed as data commit 603c4def with the
manifest extended and a README addendum. The replay now pins each member to its commit. The October 17
pass without the prefix is kept in `claude-code/no-prefix-oct17/` for comparison; everything below is the
full-session pass. Databento's range-start `R` record clears the book before the snapshot re-adds it, so
chaining members does not double count (checked on the Book class).

**What the prefix changed.** 33,703 prints instead of 33,451; 830 frozen-detector events instead of 765
(65 in the evening hours); the first trade at 22:00 UTC October 16 instead of 00:00 UTC. One result
changed sign: the frozen duration ordering at 3 ticks, which the no-prefix pass failed (694 vs 707 s) and
the full session passes (823 vs 739). Everything else moved by hundredths. So the missing prefix was worth
filling and it did not drive any conclusion.

### 14.2 The clocks and the detector

Same contract, same constants, archived births not available for this date (no standalone export yet).
Threshold saturates at 1.0 again. 830 events, 424 sell / 406 buy polarity; seeds P 268, O 223, S 182,
X 157. Runway median 36 s (q25 18, q75 84, max 985), confirmation median 38 s, 492 of 830 confirmed before
the archived adapter's t0+50 horizon, 59 before t0+5; remaining runway at t0+50 negative for 481 (58
percent). The October 18 figures were 33 / 35 s, 62 percent over before knowable. The three clocks have
the same shape on both days.

### 14.3 The frozen duration math

A classifier: 400 fast-collapse, 430 persistent; every seed-P event is persistent, every fast event is a
collapsed seed, as on the 18th. Kaplan-Meier medians, with-polarity price, seconds from t0:

| state | 3t | 5t | 8t | 13t |
|---|---|---|---|---|
| fast-collapse realised (Oct 17) | 739 | 1651 | 2931 | 9371 |
| fast-collapse realised (Oct 18) | 450 | 1128 | 2798 | 6388 |
| fast-collapse frozen | 358 | 993 | 1802 | 4386 |
| persistent realised (Oct 17) | 823 | 2057 | 4622 | 11587 |
| persistent realised (Oct 18) | 579 | 1341 | 3536 | 6956 |
| persistent frozen | 700 | 1802 | 3455 | 6836 |

Ordering persistent > fast-collapse holds 4 of 4 with polarity and 4 of 4 either way, and on the
Family-A-only subset (774 of 830 are Family A; 28 B, 28 C). October 17 is a slower price-travel day
than the 18th (either-direction medians 111 / 315 / 871 / 2506 s for fast against 85 / 240 / 598 / 1415)
despite more volume (74,222 lots against 64,462), so the absolute totals run long on both states: fast
about 2x frozen at every scale, persistent 1.2x at 3 and 5 ticks and 1.3x to 1.7x at 8 and 13. The +60
countdown is correspondingly optimistic on this day for both states (persistent frozen remaining 640 /
1742 / 3395 / 6776 against realised 966 / 2297 / 4566 / 11527). Two-day reading of the duration math: the
two-state ordering is robust; the persistent totals are calibrated on a day like the 18th and slow on a
day like the 17th; the fast totals are short on both. A day-level speed scale (price travel per lot, or
the either-direction 3-tick median of the first hours) is the obvious correction to test before any use.

### 14.4 Replication table for section 13

| claim | Oct 18 | Oct 17 full | holds |
|---|---|---|---|
| state carries no price direction at +60 (first 3t with share) | 0.49 / 0.48 | 0.45 / 0.46 | yes |
| persistent state = quieter 600 s (volume AUC) | 0.27 | 0.30 | yes |
| range / path / dispersion AUC | 0.33 / 0.28 / 0.30 | 0.36 / 0.30 / 0.32 | yes |
| time to first tick / hold share AUC | 0.65 / 0.61 | 0.65 / 0.57 | yes |
| low-activity tercile: state AUCs collapse | 0.48 / 0.47 | 0.50 / 0.51 | yes |
| pre-300 s volume separates the states (AUC) | 0.28 | 0.29 | yes |
| pre-arc shape separates the states (arc_min AUC) | 0.57 | 0.56 | yes, weakly |
| pre-300 s volume vs time to 3t (rho) | -0.52 | -0.55 | yes |
| pre-300 s path vs 600 s range (rho) | +0.63 | +0.62 | yes |
| pre-birth vs oriented 300 s change (rho) | 0.00 | -0.01 | yes (null) |
| pre-family A share | 0.93 | 0.93 | yes |
| next burst flips after persistent / fast | 0.33 / 0.56 | 0.37 / 0.56 | yes |
| next burst flips after P / O / S / X | 0.28 / 0.64 / 0.36 / 0.54 | 0.34 / 0.69 / 0.28 / 0.55 | yes |
| next-state forecast realised | 0.61 | 0.59 | yes |
| thinner book, wider spread at persistent events (toward depth / spread AUC) | 0.33 / 0.59 | 0.36 / 0.57 | yes |
| post-anchor depth change by state | 0.47 to 0.57 | 0.51 | yes (null) |
| median abs move by cell, fast high / persistent low, 600 s | 6 / 2 | 5 / 2 | yes |
| book imbalance direction in persistent cells (+300) | 0.56 | 0.50 | no |
| book imbalance inverted in busy fast-collapse cells (+600) | 0.36 | 0.56 | no, reversed |
| strong flow in mid-activity band (+300) | 0.69 | 0.41 | no, reversed |
| momentum in busy tape (+300) | 0.55 | 0.46 | no |
| fast-collapse x mid: book (+300) / next-seed (+300) | 0.57 / 0.60 | 0.59 / 0.61 | yes, n 96 / 38, watch list |
| next-burst forecast right: price against that burst | 0.64 | 0.69 | yes |
| next-burst forecast wrong: price with that burst | 0.57 | 0.65 | yes |

Two October 17 readings are not explained by section 13.3's drift account and are recorded as such. First,
pooled over the whole day, the burst polarity reverses at +300 (286 with / 128 flat / 412 against, 0.41),
where the 18th was 0.50; in the persistent state it is 0.36 and both call sides are below 0.5 (buy bursts
0.33, sell bursts 0.41), so this is not only the day's fall. Second, strong flow in the mid band points the
wrong way on both call sides. One day each; neither is a finding, both are the kind of day-level
difference (a falling day with reversing bursts) that a third and fourth day will sort.

### 14.5 The one two-day regularity that is new

Section 13.4's result sharpened on the 17th: when the state's forecast of the next burst's side is right,
the price during that next burst moves against it (Oct 18: 82 / 76 / 143; Oct 17: 59 / 80 / 130), and when
the forecast is wrong the price moves with the burst that came (105 / 74 / 78 and 125 / 74 / 66). In
plain terms, a second burst from the expected side is absorbed and a burst from the unexpected side
moves price. The outcome is contemporaneous with the burst (its side is known at its own t0+5 to +50, by
section 11, and its move is mostly done by confirmation), so this is not an entry read from the anchor;
it is a statement about which bursts move price, consistent on two days, and the first candidate I would
hand to the frozen chain plays (SSOS, P-O-X enter at endpoint+5 of a sequence) as a filter to test, with the
caveat that it was found on the same two days it is reported on.

### 14.6 Index of this session's October 17 artifacts

Full-session pass, all under `claude-code/`: `exhaustion-clock-oct17-*`, `runway-duration-oct17-*`,
`frozen-a-classifier-oct17-*`, `a-state-direction-knowable-oct17-*`, `beyond-direction-prebirth-oct17-*`,
`other-things-oct17-*`, `stack-direction-sources-oct17-*`, `next-burst-forecast-oct17-*`; the no-prefix
pass in `no-prefix-oct17/`; the cross-day diagnosis in `cell-flip-diagnosis.json` (built on the no-prefix
stack table; the full-session table differs by the 65 prefix events). The group export and archived births
for October 17 have not landed; when they do, the four-arm, dipole post-recognition, size-one and sweep
cohort passes run unchanged, and the exhaustion pass gains its archived-recognition comparison. October 2
and 3 are ready to run from the tape now (`NG_DAY=20231002`, `20231003`), October 2 with its Sunday prefix.

## 15. Four sessions through the tape chain: what holds on all four, what held on one

October 2 (with its Sunday-evening prefix from the 2023-10-01 member) and October 3 ran through the same
chain as 17 and 18 (`NG_DAY=20231002`, `20231003`; outputs `*-oct02-*`, `*-oct03-*`). No standalone export
exists for 2, 3 or 17, so the archived-recognition match and the export-side passes (four arms, dipole
post-recognition, size-one, sweep cohort) remain October 18 only. The cross-day cell diagnosis was rebuilt
on all four days (`cell-flip-diagnosis-4day.json`, from the full-session tables).

**The four sessions.** October 2 opened 2957 and closed 2841 (minus 116 ticks, 85,654 lots); October 3
opened 2841 and closed 2943 (plus 102, 92,979 lots); October 17 minus 63 (74,624 lots); October 18 plus 13
(64,462 lots). Two falling days, one rising, one flat, each with a 110 to 145 tick range. Prints 38,127 /
41,410 / 33,703 / 30,739. Frozen-detector events 839 / 857 / 830 / 890; the threshold saturates at 1.0 on
all four; runway medians 32 / 31 / 36 / 33 s; confirmation 34 / 33 / 38 / 35 s; 62 / 63 / 58 / 62 percent
of events over before the archived adapter's t0+50 horizon. The three clocks of section 11 look the same
on every day.

### 15.1 Holds on all four days

| claim | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
|---|---|---|---|---|
| A classifier splits the day near half (fast / persistent) | 415 / 424 | 458 / 399 | 400 / 430 | 442 / 448 |
| every seed-P event is persistent, every fast event a collapsed seed | yes (1 exception) | yes | yes | yes |
| duration ordering persistent > fast, 4 scales, with polarity and either | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 |
| no price direction at +60 (first 3t with-polarity share, fast / persistent) | 0.54 / 0.47 | 0.52 / 0.52 | 0.45 / 0.46 | 0.49 / 0.48 |
| persistent = quieter 600 s (volume AUC) | 0.30 | 0.27 | 0.30 | 0.27 |
| persistent = slower first tick / longer hold (AUC) | 0.63 / 0.58 | 0.66 / 0.62 | 0.65 / 0.57 | 0.65 / 0.61 |
| pre-300 s volume separates the states (AUC) | 0.30 | 0.25 | 0.29 | 0.28 |
| pre-arc shape barely does (arc minimum AUC) | 0.56 | 0.57 | 0.56 | 0.57 |
| pre-300 s volume vs time to 3 ticks (rho) | -0.49 | -0.56 | -0.55 | -0.52 |
| pre-300 s path vs 600 s range (rho) | +0.54 | +0.60 | +0.62 | +0.63 |
| pre-birth vs oriented 300 s change (rho) | -0.04 | +0.03 | -0.01 | 0.00 |
| forward volume vs pre-volume (rho) | 0.81 | 0.82 | 0.82 | 0.84 |
| pre-family A share | 0.96 | 0.94 | 0.93 | 0.93 |
| next burst flips after persistent / fast | 0.40 / 0.57 | 0.34 / 0.57 | 0.37 / 0.56 | 0.33 / 0.56 |
| next burst flips after P / O | 0.39 / 0.62 | 0.28 / 0.68 | 0.34 / 0.69 | 0.28 / 0.64 |
| next-state forecast realised | 0.59 | 0.62 | 0.59 | 0.61 |
| thinner toward-side depth / wider spread at persistent events (AUC) | 0.33 / 0.60 | 0.30 / 0.54 | 0.36 / 0.57 | 0.33 / 0.59 |
| post-anchor depth change by state (AUC) | 0.52 | 0.54 | 0.51 | 0.57 |
| median abs 600 s move, fast x high / persistent x low (ticks) | 6 / 2 | 4 / 1 | 5 / 2 | 6 / 2 |
| next burst forecast right: price against it | 0.67 | 0.70 | 0.69 | 0.64 |
| next burst forecast wrong: price with it | 0.68 | 0.73 | 0.65 | 0.57 |

Every row of section 13.1, 13.2 and 14.5 holds on four sessions spanning two falling days, a rising day
and a flat one. The state is an activity and persistence readout; the pre-birth activity predicts the
clocks and nothing about direction; the flow sequence is forecastable one burst ahead; the expected burst
is absorbed and the unexpected one moves price.

### 15.2 The duration math across four days

With-polarity Kaplan-Meier medians, seconds from t0 (frozen totals in the last row of each block):

| fast-collapse | 3t | 5t | 8t | 13t |
|---|---|---|---|---|
| Oct 2 | 635 | 1265 | 3108 | 7408 |
| Oct 3 | 781 | 1744 | 4035 | 10959 |
| Oct 17 | 739 | 1651 | 2931 | 9371 |
| Oct 18 | 450 | 1128 | 2798 | 6388 |
| frozen | 358 | 993 | 1802 | 4386 |

| persistent | 3t | 5t | 8t | 13t |
|---|---|---|---|---|
| Oct 2 | 844 | 2600 | 5231 | 10857 |
| Oct 3 | 1047 | 3184 | 6250 | 11513 |
| Oct 17 | 823 | 2057 | 4622 | 11587 |
| Oct 18 | 579 | 1341 | 3536 | 6956 |
| frozen | 700 | 1802 | 3455 | 6836 |

The ordering is robust, 16 of 16 across the four days. The absolute totals are not: October 18 is the only
session on which the persistent totals match the frozen values; the other three run 1.2x to 1.8x long,
and the fast-collapse totals run 1.3x to 2.5x long on every day. The frozen reveal population was four
other days; as a countdown the clock is honest about which state is slower and optimistic about how
soon, by a factor that varies by day. The day-level correction to test is a speed scale measured in the
session's first hours (either-direction 3-tick median: 106 / 142 / 111 / 85 s for the fast state on the
four days, which orders the days the same way the totals do).

### 15.3 Direction cells across four days

Within each day there is structure: cells with 30 or more decided outcomes beyond 0.42 / 0.58 number 33 /
59 / 63 / 46 against 21 to 24 expected by chance. Across days there is none: pairwise same-sign shares of
(hit minus 0.5) over the 355 common cells are 0.41 to 0.53 and rank correlations minus 0.20 to plus 0.05;
cells on the same side on all four days number 45 where 44 are expected under independence. The section
13.3 watch-list cell (fast-collapse x mid activity, book and next-seed) is 0.47 / 0.40 on October 2 and
0.54 / 0.46 on October 3: dead. The book-imbalance read in persistent cells is 0.51 / 0.49 / 0.50 / 0.56;
the burst-polarity reversal of October 17's persistent state (0.36) is 0.49 / 0.48 / 0.50 elsewhere, so it
was a property of that falling day. Within-day structure that does not cross days is the drift of section
13.3 generalized: each session's direction cells inherit that session's path.

Three cells are on the same side beyond 0.04 on all four days, and they are one thing: 300 s price
momentum in quiet tape is followed by the opposite 300 s move more often than not (low activity tercile
0.45 / 0.45 / 0.42 / 0.41; fast-collapse x low 0.40 / 0.42 / 0.46 / 0.40; persistent x mid at +600 0.43 /
0.45 / 0.41 / 0.44), on both call sides on three of the days. It is weak (54 to 60 percent of decided
outcomes, with a fifth of outcomes flat and the median called move 0), it is the size of bid-ask bounce in a
thin overnight book, and three cells out of 355 beyond 0.04 on one side is what chance gives. Logged as a
candidate for a microstructure explanation (quiet-tape mean reversion at one to two ticks), not a signal.

### 15.4 Where this leaves the program after four sessions

- The frozen exhaustion family, applied as frozen, is a four-day-consistent reader of tape activity,
  flow persistence and flow sequence. It does not read price direction, on any day, from any anchor at
  which its state is known.
- The direction half of any stack must come from a different source than the same tape at the same
  anchor. On the lag it is the observed NYMEX move itself; that test needs the Kalshi side for these
  dates.
- The one object the frozen chain plays could use now is the absorption regularity (section 14.5): a burst
  from the forecast side does not move price, a burst from the other side does, four of four days. It is
  contemporaneous with the burst and is a filter candidate, found on the days it is reported on.
- Open on the export side: the standalone group exports for 2, 3 and 17, which unlock the archived
  recognition match and the four-arm, dipole post-recognition, size-one and sweep-cohort passes per date.

## 16. The clock: frozen totals with a session-time-matched day scale and a band

Greg asked for the clock while the exports are pending. `claude-code/ng_runway_clock_v2.py` builds it,
scores six versions on the four sessions at the +60 anchor, and ends with `RunwayClock`, the live form.
Outputs: `runway-clock-v2-summary.json`, `runway-clock-v2-{oct02,oct03,oct17,oct18}-events.jsonl.gz`.
The frozen two-state totals are never changed; everything added is one multiplier at a time, and every
multiplier that is estimated is estimated on the other three days.

**The construction.** remaining_k = max(0, T[state][k] x s(t) x f[state] minus elapsed), with T the frozen
totals, s(t) the day scale and f the state factor. The day scale is the session's running price-travel
speed (Kaplan-Meier median of the either-direction 3-tick time over events born before now, censored at
now) divided by a reference day's running speed at the same session second. The first build divided by a
single full-day reference number and was wrong by 4 to 7x in the early hours on every day, the reference
day included: the overnight tape travels that much slower than the US day, so an unmatched running ratio
measures the hour, not the day. Matching by session second removes that and makes the reference day's
scale 1.0 by construction. Warm-up of 30 events (about two hours), scale 1 before that.

**What each version does, 32 cells (4 days x 2 states x 4 scales), realised Kaplan-Meier remaining over
predicted median remaining:**

| version | median ratio | range | cells within 20 pct | share reaching level within prediction (0.50 ideal) |
|---|---|---|---|---|
| v1 frozen, unscaled | 1.70 | 0.84 to 2.97 | 4 | 0.38 |
| v2a day scale, reference October 18 | 1.39 | 0.84 to 2.09 | 12 | 0.42 |
| v2b day scale, reference = median of other three days | 1.77 | 0.94 to 3.02 | 7 | 0.39 |
| v2c trailing-60-event speed, reference October 18 | 1.47 | 0.84 to 2.56 | 10 | 0.43 |
| v3 v2a x event-activity multiplier (other days) | 1.61 | 0.71 to 4.44 | 6 | 0.42 |
| v4 v2a x state factor (other days) | 0.99 | 0.70 to 1.66 | 22 | 0.48 |

Readings. (1) The day scale is real and the matched form is the right one: v2a halves the miss. (2) The
reference matters: October 18 is the day the frozen persistent totals already fit, and using it as the
clock's reference carries that fit to the other days (v2a); the no-privileged-day reference (v2b) does
not, because the frozen totals are not calibrated to the average of these four days. The choice of
October 18 is made after seeing it, and is stated. (3) A trailing window does not beat the cumulative
speed. (4) Event-level activity multipliers (v3) widen the misses: within a day the busy events travel
faster, but the frozen totals already encode that through the state and the hour, and a second activity
term over-corrects. (5) The remaining bias is state-level: the frozen fast-collapse totals are short by
about 1.45x and the persistent totals by 1.1 to 1.2x on every day that did not supply them. A leave-one-
day-out state factor (v4) brings the median ratio to 0.99 with 22 of 32 cells within 20 percent and a
reach-within-prediction share of 0.48. That is the clock. Its one systematic miss is October 2's
persistent state (ratios 1.5 to 1.7), a session whose speed rose from 0.34x to 1.27x of the reference
across the day, faster than a cumulative estimate follows.

**The band.** The per-event scatter around any of these medians is a factor of about 3.5 either way
(median absolute log ratio 1.2 to 1.3 for every version), because time-to-k-ticks is heavy-tailed. The
delivered clock therefore emits q25 and q75 multipliers of realised over predicted, per state, from the
other three days: about 0.21 to 0.26 on the low side and 2.4 to 4.0 on the high side. Leave-one-day-out
coverage of that band on the held-out day's observed events: October 2 0.45 / 0.34 (fast / persistent),
October 3 0.56 / 0.63, October 17 0.51 / 0.51, October 18 0.48 / 0.52, against a nominal 0.50. The band is
honest and it is wide: the clock tells you the median wait and that half the waits fall between a fifth
and three times it.

**The live form.** `RunwayClock(reference_curve, state_factor, band)` takes the reference day's
(session second, running median) curve and the two leave-one-day-out tables; `birth(t0)` and
`resolved_either3(t0, seconds)` feed it as events are born and first travel 3 ticks either way;
`remaining(state, t0, now)` returns the day scale and, per level, q25 / median / q75 seconds remaining.
Nothing in it reads past `now`. Smoke-tested against the batch v4 on October 18: identical medians.

**What this clock is and is not.** It is a countdown for how long the price will take to travel k ticks
in the burst's direction after an exhaustion whose A state is known, calibrated to a median on four
sessions with leave-one-day-out factors, with a stated reference day and a wide band. It says nothing
about direction (sections 11 to 15). Its inputs are the frozen detector, the frozen A classifier, and the
tape's print stream. Before any use: a fifth and sixth day to test the state factors and the band as
fixed numbers rather than leave-one-day-out estimates; a faster-adapting day scale for sessions like
October 2; and the Kalshi side, where the clock's job would be to say when the NYMEX move that Kalshi
follows is due.

## 17. The export side on four sessions: what the standalone exports changed, and what they did not

The standalone writer finished overnight. Exports for October 2, 3 and 17 are on the branch under
`tasks/family-research-20261022/replay-artifacts/<date>/standalone-inputs/groups.jsonl.gz` with their
receipts, and the sealed touch-print decisions beside them (`standalone-decisions/decisions.jsonl.gz`).
Receipts: October 2 is PARTIAL_TRADE_DATE from the October 2 UTC member (600,291 groups, 37,670 prints, no
Sunday-evening prefix); October 17 is PARTIAL_TRADE_DATE from the October 17 member (635,170 groups,
33,451 prints, no evening prefix); October 3 is the full session with the October 2 member replayed as
warm-up (653,912 groups, 41,410 prints); October 18 unchanged (583,688 groups, 30,739 prints). All four
pin the original tape commit 1d15dc6f and adapter af36937d; none used the prefix members from data commit
603c4def. Each file's sha256 matches its receipt. Script: `export_paths.py` (the per-session export locations the
later passes read through).

**What the exports changed on my side: nothing in sections 11 to 16, which never read them.** They add
two things: an independent outcome source (the group-close midpoints under the known-by clock) and a
population defined by the same frozen touch-print rules on every day.

### 17.1 Export against tape

Print counts agree exactly where the export is session-complete (October 3: 41,410 both; October 18:
30,739 both) and differ by the prefix hours where it is not (October 17: 33,451 export vs 33,703 tape;
October 2: 37,670 vs 38,127). The exports' cursor 0 is the first record at or after the session open inside
the prior UTC member (section 18), and the Book's touch at every size-one onset matches the export's on all
four sessions with zero mismatches, so the two reconstructions of the book agree.

### 17.2 Outcomes after recognition and the four arms on four sessions

These two passes were first run on substitutes (a t0+50 recognition rule and the frozen touch-print candidate
population) while the actual per-date inputs did not exist. Those versions were removed from the branch once
the actual archived Native recognitions and the actual first-observed family starts arrived; the real-input
results are section 22. Nothing from the substitute runs is cited anywhere in this file.

## 18. The size-one onsets on four sessions

Section 4 studied 1,012 October 18 size-one onset episodes from the SQLite triage ledger. Greg asked for
the same on four days. Three scripts do it: `size_one_from_groups.py` derives every size-one onset from a
session's standalone group export (a touch side showing exactly one lot where the previous group close did
not: NEW_BEST when the price changed, STANDING_BEST_SHRANK when it did not), with the first end (RETREATED,
SIZE_RECOVERED_AT_SAME_PRICE, IMPROVED), the prior touch, and the 1 ms paper-entry timing;
`size_one_tape_pass.py` replays the raw tape with the audit Book and records, at each onset's close, the next
displayed level and the onset group's reductions at the standing price, fill-linked or not;
`size_one_four_arm_days.py` mirrors section 4's arms. Outputs `size-one-episodes-<tag>*`,
`size-one-tape-<tag>*`, `size-one-four-arm-<tag>-*`.

**Validation.** The derivation finds all 1,012 ledger episodes and agrees with the ledger on onset type,
outcome, end group and entry timing 1,012 of 1,012; the tape pass agrees on the next displayed level and
the fill-linkage class 1,012 of 1,012; the Book's touch at every onset matches the export's (price, 1 lot,
1 order) on all four sessions, 101,000 onsets, zero mismatches. The ledger turned out to be every size-one
onset inside a 12-minute window, 13:07:15 to 13:19:08 UTC on October 18 (the per-minute counts match
exactly); the full October 18 session has 27,560. Cursor mapping: the exports' cursor 0 is the first record
at or after the session open inside the prior UTC member (October 18: October 17 member at minus 841,601
then plus 17,375; October 3: October 2 member at minus 808,453 then plus 4,889), which is also why October
3's export is session-complete while October 2's and 17's are not. Populations: 27,560 / 27,111 / 24,352 /
22,041 onsets on October 18 / 17 / 3 / 2; the 13:00 hour alone 5,048 / 4,152 / 3,205 / 2,687.

**The mechanism, four days, whole session.** Retreat share of all onsets in the cell (October 18 / 17 / 3 / 2):

| cell | n (Oct 18) | retreat share | retreat share, still open at 1 ms entry |
|---|---|---|---|
| NEW_BEST, no reduction | 16,095 | 0.37 / 0.38 / 0.42 / 0.38 | 0.45 / 0.46 / 0.48 / 0.46 |
| STANDING shrank, fill-linked reduction | 3,509 | 0.73 / 0.72 / 0.74 / 0.74 | 0.58 / 0.57 / 0.59 / 0.56 |
| STANDING shrank, unlinked reduction | 7,820 | 0.52 / 0.53 / 0.53 / 0.56 | 0.46 / 0.46 / 0.49 / 0.49 |
| STANDING shrank, prior touch had more than 2 orders | 663 | 0.76 / 0.79 / 0.79 / 0.81 | 0.58 / 0.65 / 0.65 / 0.61 |
| STANDING shrank, prior touch had 2 or fewer | 10,776 | 0.58 / 0.58 / 0.61 / 0.62 | 0.49 / 0.48 / 0.51 / 0.51 |
| NEW_BEST, next level under 10 lots | 9,691 | 0.39 / 0.42 / 0.46 / 0.42 | 0.46 / 0.49 / 0.50 / 0.47 |
| NEW_BEST, next level 10 or more | 6,430 | 0.34 / 0.33 / 0.40 / 0.36 | 0.44 / 0.43 / 0.47 / 0.45 |
| fill-linked x next under 10 (both arms) | 1,728 | 0.75 / 0.74 / 0.79 / 0.76 | 0.60 / 0.58 / 0.62 / 0.60 |

The 13:00 hour gives the same ordering on every day with the same numbers to within a few points, and the
October 18 ledger window reproduces section 4 exactly (fill-linked standing 0.78 of 133, new best with no
reduction 0.32 of 601).

**Reading.** (1) How a one-lot best arose is a four-day-stable predictor of what it does next: a standing
level eaten down to one lot by fills retreats 72 to 74 percent of the time on every session, a fresh
one-lot best price holds 58 to 64 percent. The sides agree, the days agree, the hour agrees with the
session. (2) The arms stack as section 4 said: fill linkage is the flow arm and carries most of it; a
crowded prior touch (more than two orders) sharpens the standing-shrank retreat to 76 to 81 percent; a thin
next level adds 3 to 6 points to the new-best retreat and 2 to 5 to the fill-linked one. (3) The time scale
is the problem it was on October 18: the median first end is 0.8 to 2.8 ms after the onset, 60 to 65
percent of episodes are already resolved by the assumed 1 ms entry, and among those still open the retreat
shares compress to 0.44 to 0.62. The information is real, mechanical (queue depletion at the touch), and
largely consumed before anything a millisecond away can act on it. (4) No psychology is needed to read it:
a fill-eaten one-lot remainder is the tail of a queue that was being consumed, and its owner cancels or is
taken; a fresh one-lot new best is a probe that the next arrivals join or do not. The observable that would
separate a behavioural story (probing, spoof-like placement) from the mechanical one is the identity and
history of the order ids behind the new-best onsets across days, which the tape carries and this pass
does not yet aggregate.

With this, every October 18 export-side pass has its four-session form except the two order traces, whose
instances are October 18's own; the first-family population and the archived recognitions are in section 22.

## 19. The orders behind the one-lot bests, and the frozen SSOS play on four sessions

### 19.1 Mechanical or behavioural: what the order ids say

Section 18 asked whether a one-lot new best is a mechanical remainder or a behaviour. The MBO tape names
every order, so `size_one_order_identity.py` records, for each of the 101,000 onsets, the one order at the
touch at the onset close: how it got there in the onset group (a fresh add at that price, a reprice of an
older order from another price, an older resting order left alone, or the survivor cutting its own size),
its age, how many earlier onsets the same order id created, and its fate after the onset (the next message
on that id and the delay). Outputs `size-one-orders-<tag>*`. Four sessions, October 18 / 17 / 3 / 2:

**New-best onsets (16,121 / 16,119 / 14,892 / 13,059).**

| origin of the one-lot order | share | retreat | filled first | cancelled within 5 ms | median fate delay |
|---|---|---|---|---|---|
| fresh add in the onset group (age 0.02 ms) | 0.93 to 0.94 | 0.36 / 0.37 / 0.42 / 0.37 | 0.54 / 0.56 / 0.65 / 0.62 | 0.19 / 0.19 / 0.16 / 0.16 | 9 to 11 ms |
| older order repriced to the new best (median age 7 s) | 0.05 to 0.06 | 0.52 / 0.59 / 0.56 / 0.57 | 0.82 / 0.84 / 0.88 / 0.86 | 0.004 or less | 4 to 6 ms |
| older resting order left as the new best | 0.01 | 0.27 / 0.33 / 0.29 / 0.40 | 0.44 / 0.42 / 0.45 / 0.29 | 0.15 to 0.31 | 8 to 30 ms |

Order ids that create two or more new-best onsets in a session are 1.7 to 2.9 percent of new-best onsets
(the busiest id made 20 on October 18, 9 or fewer elsewhere). A fresh one-lot new best is therefore a new
order that is hit more often than it is pulled; one in six is pulled inside 5 ms, which is the ceiling on
any probing story for this population. The repriced-in minority behaves differently and consistently: an
older order stepping to a new best with one lot is filled 82 to 88 percent of the time within a few
milliseconds and almost never cancelled; it is a price improver that gets taken, and its touch retreats
more often than the fresh add's (because it was filled, not because it fled).

**Standing-best-shrank onsets (11,439 / 10,992 / 9,461 / 8,983).**

| origin | share | retreat | filled first | cancelled within 5 ms | median fate delay |
|---|---|---|---|---|---|
| older resting survivor (level eaten or cancelled around it) | 0.88 to 0.92 | 0.58 / 0.59 / 0.61 / 0.62 | 0.57 / 0.58 / 0.64 / 0.63 | 0.23 to 0.24 | 3 to 5 ms |
| survivor cut its own size to one lot | 0.07 to 0.12 | 0.72 / 0.70 / 0.76 / 0.71 | 0.89 / 0.85 / 0.84 / 0.81 | 0.06 to 0.15 | 0.6 to 0.75 ms |

| prior onsets by the same order id | share of standing onsets | retreat | filled first |
|---|---|---|---|
| 0 | 0.68 to 0.78 | 0.67 / 0.67 / 0.69 / 0.69 | 0.60 / 0.61 / 0.66 / 0.65 |
| 1 | 0.17 to 0.21 | 0.49 / 0.46 / 0.47 / 0.50 | 0.53 / 0.55 / 0.61 / 0.62 |
| 2 | 0.03 to 0.04 | 0.38 / 0.39 / 0.32 / 0.37 | 0.57 / 0.64 / 0.70 / 0.70 |
| 3 or more | 0.02 to 0.06 | 0.11 / 0.20 / 0.17 / 0.17 | 0.75 / 0.79 / 0.79 / 0.82 |

Here identity carries information on every day: 17 to 25 percent of standing-shrank onsets come from
order ids that have been the one-lot survivor before (the busiest ids 20 to 57 times in a session), and
the more often an order has already been eaten to one lot and come back, the less its remnant retreats
(0.67 to 0.69 on a first appearance, 0.11 to 0.20 on a fourth or later) and the more it is filled rather
than pulled. These are refreshing liquidity providers: a resting order that keeps re-growing at the same
price after being consumed. The section 18 mechanism (fill-eaten standing levels retreat 73 percent) is
the first-appearance case; the repeat-survivor case is its behavioural complement, and it is the one place
in this work where who the order is, not only what happened to the level, predicts what the level does.

### 19.2 The frozen SSOS play and the absorption filter at its horizon

`chain_play_filter.py` reproduces NG_CHAIN_D4_SSOS_CONTINUATION_V1 as frozen: four predecessors' seed
states S,S,O,S oldest to newest, each knowable before the current t0; endpoint confirmed by onset+5 or no
entry; stand down if a successor starts before confirmation; enter with the current polarity at onset+5,
exit at onset+30; gross return in ticks. P,O,X was killed on its held week and is not run. Eligible targets
399 / 355 / 415 / 404 (the two gates each remove about a third of events: the immediate predecessor's seed
is usually not yet known at t0 because the median gap is 72 s, and a successor often starts before
confirmation).

| session | play instances | frequency of eligible | gross return mean (ticks) | with / flat / against |
|---|---|---|---|---|
| Oct 18 | 10 | 0.025 | minus 0.30 | 2 / 3 / 5 |
| Oct 17 | 10 | 0.028 | minus 0.30 | 5 / 2 / 3 |
| Oct 3 | 3 | 0.007 | plus 0.67 | 1 / 1 / 1 |
| Oct 2 | 7 | 0.017 | minus 0.43 | 1 / 2 / 4 |

The frequency matches the frozen base (2.49 percent) on two sessions and is lower on the others; the
return does not: the frozen base averaged plus 0.26 ticks and the held week plus 0.82, and these four
sessions give 30 instances at minus 0.21 on average, 9 with, 8 flat, 13 against. Thirty instances is not a
verdict, and whether October 2023 lies inside or outside the play's 54-week base is not recorded here; it
is one more block in which the play did not pay, logged as such. The eligible universe itself is flat
(0.51 to 0.57 with-share, means minus 0.02 to plus 0.17 ticks).

**The absorption regularity does not transfer to the play's window.** Splitting every eligible entry by
whether the current burst came from the side the previous event's state forecast: October 18 shows it
(expected side 0.42 with-share and minus 0.27 ticks, unexpected side 0.62 and plus 0.25), October 17 does
not (0.57 vs 0.54), October 3 weakly (0.49 vs 0.53), October 2 reverses (0.61 vs 0.53). Section 14.5's
regularity was measured over the next burst's own window, t0 to confirmation, and it held on four days
there; over onset+5 to onset+30 it is one day's. The absorption is in the burst, not after it, which is
consistent with section 11: by confirmation the burst's move is done.

### 19.3 Where this leaves the open questions

- Mechanical versus behavioural, answered for the one-lot bests: fresh new bests are new orders that get
  hit (mechanical, with a one-in-six fast-cancel minority); repriced-in new bests are price improvers that
  get taken; repeat-survivor standing remnants are refreshing providers whose history predicts holding.
  The last is the behavioural layer and it is readable from order ids alone.
- The frozen SSOS play is negative on three of four sessions; the absorption read is not a filter for it.
- Still open, as before: the Kalshi side for the lag stack, a fifth and sixth session for the clock's
  factors, and the 749 first-family population's cross-day form, whose definition is October 18's own.

## 20. Splitting the data out of the code repository

Greg's call after today's fetch stalls: the data goes to its own repository, `DavisAI1974/markets-data`,
and the project's own rule (git is code, S3 is all data) is restored as far as the account allows. What
exists on this branch now, all in `claude-code/`:

- `build_data_manifest.py` writes `data-manifest.json`: 29 entries. Tape tier: the six Databento NG MBO
  UTC-day members (83 MB, hashes from the Databento pull manifests, pinned at commits 1d15dc6f and
  603c4def). Export tier: the four standalone group exports, three sealed decision files, their receipts,
  and the October 18 candidate inputs, size-one ledger, touch-print decisions and large-quote moves (102 MB,
  hashes from the receipts or computed from the committed blobs). Archive tier: the three ROOT frame
  spools (1.67 TB uncompressed, 211 to 243 parts each, spool and part hashes from the published
  `source.json` and `SHA256SUMS`), listed with S3 targets and not moved by git. Every markets-data path is
  today's relative path, except the October 18 export, which moves under `replay-artifacts/20231018/` so
  the four sessions share one layout.
- `data_locator.py` resolves a manifest entry to bytes or a local path: a `MARKETS_DATA_DIR` checkout
  first, then the session mirror, then the pinned Markets commit; sha256 verified on every read. All 25
  hashed entries verify. My tape and export loaders now read through it; the October 18 recognition pass
  re-run through the locator is byte-identical to the committed summary.
- `stage_markets_data_repo.py <checkout>` fills a markets-data checkout from the pinned bytes, verifies
  each copy, writes `MANIFEST.json` and a README, and prints the archive entries with their S3 targets.

What stays as it is: the Markets history. No data commit is rewritten; every pin in the three reviews keeps
resolving. What changes for the other two passes: no further data commits to Markets; read inputs through
the manifest (path plus sha256), with `MARKETS_DATA_DIR` once the repository exists; record the
markets-data commit in the date-table indexes instead of a Markets path; ROOT frame publication resumes to
S3, not to git.

## 21. October 2, 3 and 17 done the way October 18 was done

Greg asked for the October 18 treatment on the three new sessions. The four pieces of that treatment and
where each now stands: outcomes after the archived adapter's recognition (section 1) and the four arms on the
first-observed family starts (section 2) are in section 22 on the actual per-date inputs; the size-one four
arms (section 4) are in 18 and the orders behind them in 19; and the concrete traces (section 3, cases 375
and 391) are here. Script
`trace_divergent_pairs.py`, outputs `divergent-pairs-{oct17,oct03,oct02}.json`. For each session it picks,
inside the 13:00 UTC hour, two matched pairs with the same start and a different end: a standing best eaten
to one lot by fills on the order's first appearance, and a fresh one-lot new best, each pair matched on
prior touch size, next-level bucket and far-side touch, both episodes still open at the 1 ms entry, one
RETREATED and one SIZE_RECOVERED, closest onsets in time. Every message at the touch price on both sides
from 250 ms before the onset to 50 ms after the end is dumped with cursor, clock, order id and fill linkage.

### 21.1 The three sessions

| | October 2 | October 3 | October 17 |
|---|---|---|---|
| session path | 2957 to 2841, minus 116 ticks, range 121 | 2841 to 2943, plus 102, range 145 | 3124 to 3061, minus 63, range 110 |
| volume (lots) | 85,654 | 92,979 | 74,624 |
| biggest hours (net ticks, lots) | 14:00 minus 41 on 18,185; 22:00 (Sunday open) minus 39 on 724; 17:00 minus 34 | 15:00 plus 40 on 14,548; 12:00 plus 33 on 10,476; 07:00 minus 27 | 13:00 minus 66 on 10,896; 16:00 plus 26; 15:00 minus 23 |
| frozen-detector events | 839 | 857 | 830 |
| size-one onsets (13:00 hour) | 22,042 (2,687) | 24,353 (3,205) | 27,111 (4,152) |
| first-observed family starts | 796 | 849 | 824 |
| export scope | partial, no Sunday-evening prefix | full session | partial, no evening prefix |

October 2 is the Monday after a Sunday-evening gap down (39 ticks in the opening hour on 724 lots) that
kept falling through the US day; October 3 is a rising day whose two big hours are the US morning and
15:00; October 17 is a falling day whose whole decline is one hour, 13:00 UTC, minus 66 ticks on 10,896
lots, after which it chopped. On all three the overnight is quiet and the exhaustion detector, the size-one
onsets and the family starts concentrate in the 12:00 to 18:00 hours, as on the 18th.

### 21.2 What each day says, per the four-day passes

Every row of sections 13 to 19 is already per day; the per-day reading in one place, October 2 / 3 / 17:

- Recognition carries no direction (archived recognitions, baseline with-share at 300 s 0.49 / 0.49 / 0.46);
  the touch-size read at recognition is right 65 / 76 / 73 percent at 1 s and 52 / 50 / 48 at 300 s, the same
  as the day's all-seconds control. Same on all three (section 22.2).
- First-family starts: recent flow continues at 5 s (0.57 / 0.55 / 0.54); the 375/391 stack adds nothing on
  the 3rd (0.34 at 60 s), holds on the 17th (0.59) and splits on the 2nd (0.61 at 60 s, 0.42 at 300 s); the full
  displayed book is bid-heavy at 90 to 100 percent of starts on each (section 22.1).
- Size-one: fill-eaten standing remnants retreat 0.74 / 0.74 / 0.72, fresh one-lot new bests 0.38 / 0.42 /
  0.38, crowded prior touch 0.81 / 0.79 / 0.79; repeat-survivor orders retreat 0.17 / 0.17 / 0.20 after
  three prior appearances.
- Clocks: persistent > fast-collapse at every scale; the frozen persistent totals run 1.2 to 1.6x long on
  the 2nd, 1.5 to 1.8x on the 3rd, 1.2 to 1.7x on the 17th; the delivered clock (section 16) brings all
  three inside 20 percent on 17 to 22 of their 24 cells except October 2's persistent state.
- Next-burst polarity forecast right 0.59 / 0.62 / 0.59; absorption (forecast right, price against that
  burst) 0.67 / 0.70 / 0.69.

Nothing in the three days contradicts the 18th; the one thing the 18th had that the others do not is its
per-cell direction lifts, which section 13.3 showed to be its own drift.

### 21.3 The traced pairs: what differs between a retreat and a recovery

Six pairs, twelve episodes, all with exact clocks and order ids in the json. The finding is the same on
every day, and it is sharper than section 3's: at matched onset conditions, the retreat and the recovery
are the same process observed at two moments, and the difference between them is a race decided in under
five milliseconds that the onset book does not contain.

**October 17, bid 3070, 13:00 hour (groups 279739 and 279746, seven milliseconds apart).** The level is
being nibbled by one-lot sells (`T A 3070 x1`) and refilled by one-lot bids. At the first onset the
resting order 788697670940 (6.5 s old) is the last lot after a one-lot sell takes 788697670661. 2.1 ms
later a fresh one-lot bid 788697671119 joins: SIZE_RECOVERED. 0.2 ms after that a one-lot sell takes
788697670940, and 788697671119, 0.4 ms old, is now the single lot of the second onset, the same level,
the same order that produced the recovery. For 2.47 s nothing arrives; then one-lot sell 788697671183
takes it and the bid steps to 3069 x 19: RETREATED. Within 0.4 ms the far side posts one-lot asks AT 3070
(the spread collapses onto the vacated price), and within 4 ms new one-lot bids rebuild 3070 (788697671201
first, twenty lots and twelve orders by +17 ms, an 8-lot 788697671267 among them), then a 5-lot buy sweep
takes 3071 at +22 ms. The retreat lasted 4 ms. Recovery and retreat were one refill apart.

**October 2, ask 2906, 13:00 hour (groups 222337 and 222341, two milliseconds apart).** Same structure on
the other side: one-lot buys (`T B 2906 x1`) consume one-lot asks that re-arrive every 1 to 3 ms. The
recovered episode's refill (788650870862, posted at +2.064 ms) is the survivor of the retreated episode
two groups later; it is taken at +2.877 ms with no refill in time, the ask steps to 2907 x 8, and 1.2 ms
later 788650870888 re-posts one lot at 2906 and is itself taken 1.7 ms after that. The level flickers
between one lot and none at a 2 to 3 ms cadence; which state a group close catches decides the label.

**October 3, ask 2895 and 2894 (groups 266919 and 267317).** The retreat: the last ask lot 788654032680
(8.5 s old) is taken at +2.207 ms by a one-lot buy, and the taker's own residual then posts a one-lot BID at
2895 (788654033868, +2.492 ms): the price did not just retreat, the aggressor crossed and sat on the level
it emptied, with three more one-lot bids joining within 8 ms and the ask side reassembling at 2896 x 14.
The recovery: a 3.4 ms old remnant 788654035110 at 2894 is joined by 788654035139 at +4.66 ms and holds
14.7 s before it is filled. The next level was 13 to 15 lots in both; the far side 17 to 20 lots in both.

**The fresh one-lot new bests (three pairs).** On October 17 (ask 3097) and October 3 (ask 2896) the
retreated probe is not taken; it cancels itself at +1.46 and +1.37 ms, and in both cases the message
immediately before its cancel is a cancel on the far side's touch (bid 3096 x1 at +1.303 ms; the far side's
fills and cancels in the 4 ms before). Its twin, posted 0.5 to 2 ms later at the same price by the next
order id, is joined within 1.6 to 6.6 ms and holds (on the 17th, filled 2.7 s later). On October 2 (bid
2893) the retreated probe is taken by a one-lot sell at +1.386 ms; its twin 788650632114 is joined at
+5.5 ms, grows to four lots and two orders, and then cancels itself at +8.57 ms once a 2-lot order has
joined it. New-best probes come in trains: three to five one-lot adds at the same price within 10 ms from
consecutive order ids, each withdrawn or taken within a few milliseconds.

**Reading, mechanics first.** (1) Both sides of the touch are being worked in one-lot increments on all
three days: one-lot takers and one-lot refills at a cadence of 1 to 3 ms. A standing level eaten to one lot
is the trough of that cycle; whether the next event is a refill (recovery) or a take (retreat) is the
phase of the cycle at the group close, and matched onset books cannot tell the two apart. That is why
sections 4 and 18 found the retreat shares stable across days yet the book arms worth only a few points.
(2) The retreat is a flicker, not a move: in five of six standing and fresh-add retreats the level is
re-posted at the same price within 1 to 5 ms, and in the sixth the far side crosses onto it. The frozen
first-end label is correct and the price did not go anywhere. (3) Order identity threads the episodes:
the refill that ends one episode is the survivor that begins the next, on every day. (4) The one
behaviour-shaped regularity is the probe's self-cancel: a fresh one-lot new best pulls itself within 1.5 ms
of the far-side touch thinning, on two of three days, which is a reactive quoting rule. It is behavioural
in the sense that a rule is being run, and mechanical in the sense that the rule is visible: watch the far
touch, pull if it cancels. Nothing in these twelve episodes needs a story about intent beyond that rule and
the one-lot cadence, and the observable that would separate a human from a machine here is the cadence
itself, which is sub-5 ms on all three days.

**Against October 18's 375 and 391.** Section 3 found that 375 and 391 diverged on whether a resting 200-lot
order was consumed in 204 ms or withdrawn. These pairs sit two orders of magnitude below that in size and
time and show the same shape: the divergence is decided by which of two already-running processes (the
taker stream or the refill stream) lands next, not by anything readable at the decision boundary. The
larger episodes of section 3 and the one-lot episodes here differ in scale and agree in kind.

## 22. Actual family starts and actual archived recognitions on all four sessions

Codex's handoff (`agent-pass/CCODE_FAMILY_AND_RECOGNITION_INPUTS.md`, Markets c22ecc13) supplied the two
inputs sections 17 and 21 had to stand in for: the first-observed structural family starts for October 2,
3 and 17 with their strict-pre ROOT operands (markets-data 7b50d634, family replication run 42566535537;
796 / 849 / 824 families, and the 749 October 18 reference), and the archived Native dipole candidates with
live recognition clocks (Markets 1a8ba347, `replay-comparison/<date>/candidate-inputs.jsonl.gz`; 741 /
833 / 741). Both are now manifest entries (36 in `data-manifest.json`, all 32 hashed entries verified) and
the original October 18 scripts run on them unchanged in method: `four_arm_first_family_days.py` and
`dipole_post_recognition_days.py` are date-parametric copies of the section 2 and section 1 scripts, and
each reproduces the committed October 18 summary byte for byte on the new inputs before touching another
date (the October 18 family index yields the same 749, 377 eligible, 50-case screen and every arm cell; the
October 18 candidate file yields the same 863 rows and every arm). The substitute runs that preceded these inputs
were removed from the branch; only the actual-input results are kept.

**Joins, reported as asked.** Family starts: every row's saved pre-event cursor agrees with the as-of
group chosen from the export (823 / 848 / 795 of 823 / 848 / 795; one family per date has no earlier
source group and is excluded by the index itself). Archived recognitions: on October 17 all 740 live
recognitions match a group by clock and cursor; on October 3, 830 match by both and 2 match by cursor with
a tied receive clock (known-by ties are ordered by close cursor); on October 2, 739 and 2. The two
finalization-only candidates (`dip-19633-1696366763`, `dip-19647-1697576378`) have no live recognition
and are excluded with their ids recorded; nothing was given a t0+50 clock. Against my own detector, the
archived births match a detector t0 on 813 / 691 / 800 / 704 of 863 / 740 / 832 / 741 (October 18 / 17 /
3 / 2); the unmatched archived births are the adapter's 85th-percentile trailing threshold admitting
events the day-native threshold does not, as section 11 found, and the detector's extra events
(890 / 830 / 857 / 839) are the reverse plus the prefix hours the partial exports do not cover. The
archived recognition offset from birth is median 51 / 52 / 52 / 52 s on the four days, maximum 137 to
157 s, and 449 / 393 / 466 / 407 recognitions arrive after the burst's own confirmation: the three clocks
of section 11 hold on the actual recognitions of every session.

### 22.1 Section 2 on actual family starts, four sessions

| | Oct 18 | Oct 17 | Oct 3 | Oct 2 |
|---|---|---|---|---|
| first-observed families | 749 | 823 | 848 | 795 |
| eligible (1 s and 5 s flow agree) | 377 | 430 | 433 | 428 |
| original screen (375/391 stack, selling side) | 50 | 46 | 57 | 40 |
| inverse stack (buying side) | 0 | 3 | 0 | 2 |
| full displayed depth bid-heavy at start | 1.000 | 0.916 | 0.999 | 0.903 |
| full depth ratio, median | 1.48 | 1.21 | 1.42 | 1.18 |
| baseline continuation, 5 s | 0.61 | 0.54 | 0.55 | 0.57 |
| baseline continuation, 60 s | 0.58 | 0.56 | 0.49 | 0.54 |
| baseline continuation, 300 s | 0.51 | 0.48 | 0.52 | 0.56 |
| + 60 s flow opposes, 60 s | 0.65 | 0.60 | 0.42 | 0.58 |
| + full depth opposes, 60 s | 0.60 | 0.51 | 0.49 | 0.59 |
| + both (the stack), 60 s | 0.64 | 0.59 | 0.34 | 0.61 |
| + both, 300 s | 0.67 | 0.53 | 0.54 | 0.42 |
| both agree (inverse), 60 s | 0.54 | 0.59 | 0.52 | 0.49 |
| all families unoriented, up share at 600 s | 0.41 | 0.44 | 0.57 | 0.45 |

Reading. (1) The population behaves the same way on every session: half the family starts have a defined
recent flow, and that flow continues at 5 s on all four days (54 to 61 percent) and is gone by 300 s. (2)
The stack is October 18's and October 17's: 0.64 and 0.59 at 60 s on the two falling days, 0.34 on the
rising October 3 (the stack's selling side reverses there), 0.61 at 60 s but 0.42 at 300 s on the mixed
October 2. The inverse stack exists on 3 and 2 events, which is section 2's finding (the buy-side mirror
barely occurs) on all four days. The unoriented day reference says why: all families drift down at 600 s
on the three days the stack held and up on the day it failed. This is the drift account of 13.3 on the
actual population. (3) The full displayed book is bid-heavy at family starts on all four sessions,
90 to 100 percent, median ratio 1.18 to 1.48. Section 2 called it a day constant for October 18; it is a
constant of this population on every day, and it is a FULL-depth property: the 10-level depth at the
exhaustion anchors (section 13.2) is not bid-heavy in the same way. The far ladder of NG was bid-heavy throughout these four October
sessions, and the "book opposes" arm therefore means "recent flow is buying" more than it means anything
about the book.

### 22.2 Section 1 on actual archived recognitions, four sessions

Outcomes from the recognition group's midpoint, oriented to birth polarity, with-share of non-flat (October
18 / 17 / 3 / 2), and the day's control (the same touch-size read at every active second's last close,
no dipole involved):

| | 1 s | 5 s | 20 s | 60 s | 300 s |
|---|---|---|---|---|---|
| baseline (all recognitions) | 0.51 / 0.56 / 0.52 / 0.46 | 0.48 / 0.53 / 0.48 / 0.47 | 0.52 / 0.51 / 0.49 / 0.49 | 0.50 / 0.49 / 0.46 / 0.52 | 0.50 / 0.46 / 0.49 / 0.49 |
| recognition touch aligned to birth | 0.63 / 0.73 / 0.76 / 0.65 | 0.59 / 0.67 / 0.69 / 0.62 | 0.63 / 0.59 / 0.60 / 0.58 | 0.56 / 0.55 / 0.51 / 0.57 | 0.51 / 0.48 / 0.50 / 0.52 |
| recognition touch opposed to birth | 0.35 / 0.40 / 0.28 / 0.25 | 0.34 / 0.38 / 0.30 / 0.29 | 0.39 / 0.42 / 0.38 / 0.36 | 0.44 / 0.42 / 0.40 / 0.45 | 0.49 / 0.44 / 0.48 / 0.47 |
| control: heavier touch side wins, all active seconds | 0.65 / 0.65 / 0.67 / 0.67 | 0.58 / 0.58 / 0.60 / 0.59 | 0.54 / 0.54 / 0.55 / 0.55 | 0.53 / 0.53 / 0.53 / 0.52 | 0.52 / 0.53 / 0.52 / 0.51 |

The actual recognitions say, on every session: the birth polarity
carries nothing after recognition at any horizon; the touch-size relation at recognition carries the next
few ticks and decays to the control by 300 s; and the control, which has no dipole in it, is the same
number at every horizon on every day. The 300 s flow state at emission (same or opposite the birth) has no
consistent sign across the four days (same-direction 1 s: 0.45 / 0.59 / 0.53 / 0.36). Buy births and sell
births differ only as each day drifted.

### 22.3 What the actual inputs changed

Nothing in direction, two things in precision. The first-family four arms now stand on the actual
population on four sessions and their reading is the drift reading, with the inverse stack confirmed rare
everywhere; and the full-depth bid skew is promoted from an October 18 observation to a four-session
property of NG's displayed book at family starts. The archived
recognition clocks confirm the information horizon on four sessions rather than one. The population
distinction the handoff draws (all first-observed structural ids per date, not a copied 749 whitelist)
is preserved in the tables above and in `first-family-four-arm-<tag>-summary.json`.

## 23. Separation and clocks: a statement for the merge

Greg asked whether events, instances and lifecycles have been kept separate, and that anything without a
clock be given one. The answer, checked against every row file on the branch:

**Separation.** Every pass writes one row per event beside its summary, and no row is ever merged with
another: the 890 / 830 / 857 / 839 frozen-detector events, the 863 / 740 / 832 / 741 archived recognitions,
the 749 / 823 / 848 / 795 family starts, the 27,560 / 27,111 / 24,352 / 22,041 size-one episodes with their
individual first ends, and the one order behind each of them all keep their own rows with their own
identities (candidate id, family id, onset group and side, order id). Summaries are per session; no table
pools the four days as its final word. The three places where numbers from more than one day enter one
calculation are stated as such where they appear: the leave-one-day-out factors and bands of the clock
(section 16, estimated on the other three days and applied to the fourth), the cross-day sign-agreement
counts of the direction cells (section 15.3, a comparison of per-day tables, not a pooled table), and the
thirty SSOS play instances reported pooled beside their per-day rows (section 19.2). Lifecycles are kept
whole: a size-one episode's onset, first end and the survivor order's later fate are three clocks on one
row, never collapsed into one outcome, and the episode that follows on the same level is its own row (the
October 17 and October 2 pairs in 21.3 are two rows each, threaded by the order id).

**Clocks.** The exhaustion, family, recognition and size-one row files always carried absolute clocks
(t0_utc; start_recv_ns and cutoff_ns; recognition_receive_ns; onset_ns and end_ns with cursors). Eleven
derived row files carried only the session-relative second or the onset group id. `attach_clocks.py`
stamped every row of those files with the absolute epoch second and UTC string for each session-second
field (t0, onset, confirm, next t0, seed-known, information horizons, archived recognition) and the session
tag and origin, and joined onset_ns, onset_utc, end_ns and the cursors onto the size-one tape and order rows
from their episode file. Nothing existing was changed or removed; the pass is idempotent. After it, no
row file on the branch is without an absolute clock, which was checked by reading the first row of every
one of them. The clocks remain distinct where the frozen contract distinguishes them: t0 (the local
maximum), t0+5 (knowable), the archived recognition receive clock, the structural onset and confirmation,
and the +60 state anchor each have their own field.

## 24. The 99-layer pin ledger of my rows

Every per-event row of this work is now pinned to the canonical 99-layer registry
(`artifacts/sqlite-triage/20261022/families/full-context-audit/canonical-99-registry.json`, 18 groups,
99 layers) by timestamp, with nothing removed or merged. `pin_rows_to_99.py` reads each row file of a
session and writes one record per row: the original row verbatim, its natural ids (t0, candidate id, family
id, onset group and side, order id), every absolute clock the row carries, its sources (the tape members
with their commits and hashes, the exports with their hashes), and `pins`: one entry per measured field
that corresponds to registry layers, naming the layer indices and ids, the field's value, the clock kind
and the absolute clock the measurement was taken at. The clock kinds are kept distinct: receive-second bin
(the replay's per-second bins), receive nanoseconds, known-by receive clock (archived recognitions, group
closes), known-by cutoff, availability at t0+50, the +60 anchor, and the outcome window. Aggregates are never
pinned; a median or an AUC has no clock and is not in the ledger. The field-to-layer map and the registry
hash are in `ninety-nine-pin-map.json`; counts per layer and per file in `ninety-nine-pins-summary.json`.

The four ledgers (25 to 32 MB each, 1.2 million rows in all, touching 29 layers from raw-source identity
through the order lifecycle, the FIFO book, signed flow, the derived dipole state and predecessor seeds, the
clocks, and the sealed later-outcome layer) are data, so they live in markets-data under
`tasks/family-research-20261022/claude-code-pins/`, commit 158ae78, with manifest entries. No summary or
render was pinned; those are views over these rows.

Second pass of the ledger (after section 25). An audit of every row file against the ledger found row
sources of mine outside the sixteen per-session files, so the builder now also pins: the flow-only detector
runs on the Codex-captured per-second tables for October 2 and 17 (766 rows each; their clock is the row's
own epoch second and their source is the per-second table, not the tape, which the record says); the
October 18 sweep cohort (749 rows, one per first-family instance, clock = the family start receive clock);
the order-level traces of instances 375 and 391 (1,650 and 1,212 raw tape messages, clock = receive
nanoseconds); the traced divergent pairs of October 2, 3 and 17 (one row per pair and one per message, the
message clock derived from the episode onset plus the message's millisecond offset, named as such); and the
five-view case rows of section 25 (the per-second context series, the per-second tape counts, the touch
snapshots with their receive clock and cursor, and the prints). The two untagged October 18 files
(`dipole-post-recognition-rows`, `first-family-four-arm-events`) were checked row for row against their
tagged copies and are identical, so they are recorded as predecessor copies rather than pinned twice. The
family starts and touch-print decisions that the case context cites are Codex's rows and are left to their
owner; the detector events and size-one onsets it cites were already pinned from their own files. The
sixteen original files pin exactly as before (row and pin counts unchanged). The ledgers now hold 486,180
rows touching 31 layers (order identity transitions and legacy price were added by the tape messages and
the case series), markets-data commit 5c94c64, manifest re-pinned.

## 25. Ten cases through five coordinated views

The per-event renders of section 24's rows. Ten individual events were chosen by stated rules across all
four sessions, including failed and flat moves, and each is drawn through the same five views with the
same ids and clocks: (1) the whole lifecycle, last price in ticks from the t0 price with the oriented roll-20
lean, t0 minus 300 s to plus 600 s, with the knowable horizon (t0+5), structural onset, confirmation,
archived recognition and seed-known clocks marked, and the neighbouring detector event; (2) fresh flow
entering the 20 s window against flow expiring from it, per second; (3) the liquidity response, net adds
minus cancels by side, executions by aggressor, ten-level depth and the best quotes; (4) the event sequence
along the same lifecycle: other detector events, family starts, size-one onsets, touch-print decisions,
prints by lot size; (5) continuation and exhaustion after confirmation: oriented price from the confirm
price, pauses of 30 s or more, the first 3-tick excursion with and against, and sign changes. Under each
case sits the table of pinned rows: the event row, the archived candidate with its recognition receive
clock and cursor, the onset and confirmation clocks, the other detector events, the family starts, the
touch-print candidates, the size-one onsets and the prints in the window, each with its id, its absolute
clock and the row file it came from. Only id-and-timestamp rows are drawn; nothing on a sorted curve.

`select_cases.py` picks the cases and writes `cases-10.json`; `case_tape_windows.py` replays the raw tape
for each window (adds, cancels, modifies and fills by side per second, prints with receive nanoseconds and
cursor, touch and depth snapshots); `case_context.py` joins the detector clocks, archived recognitions,
family starts, size-one onsets and touch-print decisions in the window; `render_case_views.py` draws the
page. The case rows are data and live in markets-data under `tasks/family-research-20261022/
claude-code-cases/` (commit ea137b6, manifest entries with hashes; the renderer reads them back through
`data_locator`). The page is `claude-code/renders/ng-case-views.html` with a PDF beside it; the composite
and per-view PNGs are in the same markets-data folder under `renders/`.

The ten cases (session second of t0, the detector's local maximum, and the UTC clock):

| case | session | t0 | UTC | rule | state, seed | runway | recognised |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Oct 18 | 70369 | 16:32:49 | largest oriented move by seed-known +300 s, US day | fast-collapse, S | 1 s | +8 s |
| 2 | Oct 18 | 57586 | 12:59:46 | most negative oriented move by +300 s, US day | fast-collapse, X | 63 s | +51 s |
| 3 | Oct 18 | 43914 | 09:11:54 | the S,S,O,S play entry with the most negative gross return | fast-collapse, O | 8 s | +25 s |
| 4 | Oct 18 | 17330 | 01:48:50 | recognised before confirmation, longest runway | persistent, P | 673 s | +53 s |
| 5 | Oct 17 | 59992 | 13:39:52 | largest oriented +300 s move in the 13:00 hour | persistent, O | 56 s | +51 s |
| 6 | Oct 17 | 61497 | 14:04:57 | absorbed pair: next burst from the forecast side, price against it | persistent, P | 110 s | +51 s |
| 7 | Oct 3 | 67166 | 15:39:26 | largest oriented +300 s move in the 15:00 hour | fast-collapse, S | 2 s | +51 s |
| 8 | Oct 3 | 14033 | 00:53:53 | persistent, overnight, zero move at +60 and +300, lowest volume | persistent, P | 143 s | +51 s |
| 9 | Oct 2 | 64190 | 14:49:50 | largest absolute oriented +300 s move in the 14:00 hour | fast-collapse, S | 3 s | +51 s |
| 10 | Oct 2 | 61148 | 13:59:08 | moved with polarity by confirmation, then the other way by +300 | fast-collapse, S | 33 s | +51 s |

Case 1 and case 10 are the same shape at confirmation (a fast-collapse S seed confirmed within seconds of
t0) and go opposite ways by +300 s, which is the section 13 point drawn: the state names the activity and
its persistence, not the direction. Cases 4, 6 and 8 show the persistent state's long runway with the
archived recognition landing at +51 to +53 s, well before confirmation, which is the information horizon of
section 16. Case 5 sits inside the October 17 13:00 UTC collapse hour where the October 18 cell lifts did
not hold. These are descriptions of individual events, not a comparison with the other two passes.

## 26. The Oct 18 suites carried onto the other three sessions (the three-day handoff's section 3B), and the index rows

Done 2026-11-09 in the session after the handoff, on Desktop's branch `claude/three-day-dipole-20261108` under `claude-pass-3day/`, because that is
where the three-day repeat of the Oct 18 suite lives; the discovery record of it belongs here with my other sections. Nothing merged; no comparison with
the Codex or Desktop findings was made (deferred by Greg); no AWS, pod or producer action.

**Tier 2 side by side (`FINDINGS_TIER2_CROSSDAY_20261109.md`, `crossday/t2x_*.csv`, `crossday/t2x-*.png`).** The c14, c15, c16, c17 and c18 tables of the
four UTC members had been run with the same code but never put beside each other. `x14_tier2_crossday.py` writes one row per condition/outcome pair
(2,669 on all four days), per pair coupling (every (x1, x2, y) of the family, 5,166 on all four days, from `x17_pair_couplings_full.py` rather than each day's
top 400), per lead-lag pair (49), per state cell (42) and per selection step, with the four days' values and counts of days sharing a sign; `x16` saves the
c14 shifted-Y draws so the agreement counts have the day-by-day reference the regime comparison had. Measured: 1,330 of 2,669 pairs share a sign on all
four days against 372 to 633 under the shifted draws; 99 pairs are beyond every day's own line against 0 in every draw, 93 of them book-response pairs
(touch activity over the past 5 to 60 s against touch activity over the next 5 s), 5 the spread and touch counts against the next spread change, 1 the
300 s quote-change count against the next 20 s absolute move; no signed-move or flow-persistence pair is beyond the line on more than one day; the touch
imbalances against the signed move repeat in sign on all four days at +0.11 to +0.14. State cells: every bid-heavy cell positive and every ask-heavy cell
negative on all four days at both horizons; the mid-imbalance cells do not agree. Lead-lag: 12 of 21 distinct pairs beyond the band on all four days
with the peak at lag 0; touch imbalance leads flow by one second on all four days. Pair couplings beyond every day's line: 9 rows, all with y = dspr_5
(tch_imb x tchn_imb +0.126 to +0.145 and the touch sizes and counts against the 5 s quote-change count, negative). Oct 17 stands apart on bid-side
book pairs (0.29 to 0.32 against 0.15 to 0.23). The grids were rebuilt from the manifest-pinned tapes and reproduce every committed Tier 2 table to
1e-16. The Oct 18 original Tier 2 tables in `claude-pass/tables/` (2,635 pairs, 44 cells) were a legacy-mode run (export groups, no closed-market
exclusion, `age_s` and `qage_s` out); the reason is now recorded in the findings file.

**Tier 1 on the actual family starts (`FINDINGS_TIER1_CROSSDAY_20261109.md`, `tables/<session>/t1_*.csv`, `crossday/t1x_*.csv`).** The handoff's open
question (which population to use for Tier 1 on the other days) is answered by section 22: the actual first-observed family starts exist for all four
sessions. `x18_tier1_days.py` runs c02, c06, c07, c08, c10 and c11 unchanged in method on them (795 / 848 / 823 / 749, the one-per-date family with no
earlier group left out with its id recorded; session groups from the tape members, prior member from 21:00 UTC to the 21:00 UTC close; order-level
windows from the date member, 781 / 796 / 809 / 694 families inside it). On Oct 18 the chain reproduces every committed Tier 1 table value for value,
including the 4 and 5 censored outcomes at 300 and 600 s. Measured on the four sessions: the full displayed book bid-heavy at 718 / 847 / 754 / 749 of
the starts with the near ten levels split evenly; the refill read at the side being hit, which had been Oct 18 only, with the same sign on all four
days (sell-hit bid adds per lot filled against the next midpoint, Spearman +0.21 / +0.15 / +0.10 / +0.26 at 1 s; the mirror on the ask -0.14 / -0.13 /
-0.29 / -0.27), holding inside fill-size halves at 1 s and gone by 300 s; the original 60+/5-/1- stack lower at 60 s on Oct 17 and 18 (0.57, 0.58 down
share against 0.42, 0.47 for all families), flat on Oct 2 and reversed on Oct 3, as section 22 found by its own orientation; no ridge arm below the
predict-zero error on more than two days at any horizon; the one-second flow cells sorting the next 5 s on every day and fading by 60 s.

**Pins and clocks.** The family masters are per-event rows (one per family start) and are pinned to the canonical 99-layer registry like every other row
of mine: `claude-code/pin_tier1_rows_to_99.py` (the pin_rows_to_99 field map and clock rules, extended for the ROOT operands, reference-group
fields, prior displacement, order-level windows and the horizon outcomes; two clock kinds added, the reference group's known-by receive clock and
the outcome window from the start by horizon) writes `claude-code-pins/ninety-nine-pins-tier1-<tag>.jsonl.gz` (795 / 848 / 823 / 749 records,
133k to 145k pins, 19 to 20 layers, every field mapped), published to markets-data main at 67b7a6a with manifest entries (the push went through once the
repository was attached to the session; `data-manifest.json` carries the commit). Every record carries the start, cutoff and reference-group clocks
as nanoseconds and UTC strings. The cross-day tables are aggregates and are not pinned.

**Index.** The October 2 and 3 rows of "Where to find the four dates" in `october-discovery-log.md` now carry coverage, session members and cursors,
the sealed export and decision locations with their markets-data commits, the archived candidate files and counts, the family indexes, my per-event
row files, pin ledgers and case rows, and the three-day tables (commit 5d9c269). October 17 keeps its placeholder; it is indexed in 14.6.

Not done, by Greg's direction: the agreement and disagreement pass against the Codex and Desktop passes; the 99 and 13 crosswalk and the merge of the
three reviewer files (merge time); the detector reverse-engineering (3C, not needed for discovery); the two Oct 18-only coupling variants c13 and
c14_deseason (superseded by c14 and c19, which run on all four days).
