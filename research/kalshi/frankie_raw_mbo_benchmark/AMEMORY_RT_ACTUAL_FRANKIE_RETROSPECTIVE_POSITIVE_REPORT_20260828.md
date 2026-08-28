# A-memory REAL_TIME_FRANKIE Retrospective Positive Report

## Retrospective provenance and scientific standing

This is the A-memory counterpart to the A-clean retrospective interim report. It
is a `RETROSPECTIVE_ROLE_ANALYSIS` produced after completion of the A-memory
diagnostic native-MBO replay. It did not make a principal Frankie model call and
does not claim a principal-execution lock or freeze. That execution-provenance
fact does not reduce the scientific standing of the positively supported
findings below: each retained finding is mechanically bound to intact native
MBO, exact causal clocks, and the verified A-memory prior package.

Evidence access was read-only and arm-local:

- A-memory runtime:
  `/workspace/scratch/da00127ac123/a-memory-runtime-c7da7d2/`;
- verified prior memory:
  `research/kalshi/frankie_raw_mbo_benchmark/prior_memory/workmode-32851909748-1/`;
- packet proof:
  `/workspace/scratch/da00127ac123/a-memory-packet-c7da7d2/memory/`.

No A-clean report, first-replay Forecaster report, Step-1, answer/reveal,
scoring, BOSS, B0/B1/B2, Granite, reconciliation, or other-arm output was used
to derive this report. The controlling native RT mission and its authorized
shared positive-discovery addendum supplied the research questions. Every
retained native structure was independently reproduced from the A-memory
event-group ledger.

The scientific unit is one distinct F_LAST-closed event group. Its first lawful
availability is the group's closing `ts_recv_ns`. Event time, first-component
receive time, group-close receive time, and decision/as-of time remain separate.

## Hash-bound evidence receipt

| Item | SHA-256 / identity |
|---|---|
| A-memory run | `frankie-a-memory-rt-c7da7d257fda-1` |
| A-memory packet | `amemory-rtpkt-4eed0d33d524b7388db5` |
| Native event-group ledger file | `bc0788b51a719d39f5024f10007f4c74e96ff3361a21b66d662d9fadf1a67d8f` |
| `rt_observations.json` file | `764d1e6f006ef6fe35cad22c3a6c202d3596303356d434c7ecd8065564966051` |
| Observation object | `dce8b9c3808cf0c5321e53879e0b4d504c267d037c9e0a276875bde6d4ff12ef` |
| `evidence_bundle.json` file | `50b2fce744ecdd0b18ba4c7c83603e058c202a55b6769546de470df17392183b` |
| Evidence-bundle object | `94a32deafdcb580868ba24df829b616edf36a80f84f80b7cd828efea24a13b36` |
| `progress.json` file | `b523cea8172c96e156f9c6eba2c4249afee498d1bf216579f2842867ea2fc94c` |
| Final diagnostic checkpoint | `07a407f5616a5a65f8345f8f44728506f1ea5c243c3114204ab1f471df92637b` |
| Source-manifest file | `24a47eb1631a17ab391eb61ad73051f694b4c564dddec4050518e730efe40767` |
| Canonical source manifest | `a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba` |
| Prior learned package | `0a5cddbcd971a3e6c2cad88a8e5559b0ab0529a31174c882355a61fe9c680b87` |
| Prior package proof | `e7d8cbc54f354a4902ab72792e379033a25f5f28102fcf9d4bb82dda1d7e8435` |
| Repository verification | `9c5847e33f4014eac12e8da67c2f97e55280545f67ea0d7899fa1c914d39683b` |
| Prior `RT_OUTPUT.json` file | `72a22b5ec0ee5f6ebdcf14d0ff566dd178f31ce2bd6d3f3f85cf9b49a2ac9158` |

The independent pass sequentially decompressed and parsed all 4,256,603 JSONL
event-group envelopes and all 5,667,689 native records. Every group carried
`V4_NATIVE_FULL`, stored raw actions exactly once, used no seconds collapse,
closed on F_LAST, and had group `ts_recv_ns` equal to the final action receive
time.

| Source day | Role | Native records | Closed groups | Distinct action strings | Distinct action-plus-side strings |
|---|---|---:|---:|---:|---:|
| 2021-10-01 | warmup/development | 1,504,374 | 1,118,738 | 1,219 | 1,701 |
| 2021-10-03 | warmup/development | 57,027 | 43,569 | 135 | 186 |
| 2021-10-04 | held out | 1,994,358 | 1,506,255 | 1,441 | 1,976 |
| 2021-10-05 | held out | 2,111,930 | 1,588,041 | 1,509 | 2,094 |

The diversity counts positively establish why exact members remain coequal with
daily summaries: a daily statistic cannot encode thousands of distinct native
action/side paths, order identities, or causal timings.

## Coequal averaged source-day view

Arithmetic means below use one post-F_LAST full-book snapshot per closed group.
October 4 and October 5 remain separate populations; no cross-day average is
reported.

| Metric | 2021-10-04 (`n=1,506,255`) | 2021-10-05 (`n=1,588,041`) | Positive scientific content |
|---|---:|---:|---|
| Mean spread | 0.002263499 | 0.002218553 | Similar narrow whole-day spread scale |
| Mean full-depth imbalance | 0.121055981 | 0.221155480 | October 5 is the more bid-heavy full-book regime |
| Mean bid depth | 1,485.381 | 1,809.887 | October 5 is +21.847% |
| Mean ask depth | 1,162.397 | 1,156.146 | October 5 is -0.538% |
| Mean bid orders | 621.512 | 723.815 | October 5 is +16.460% |
| Mean ask orders | 489.025 | 510.784 | October 5 is +4.449% |
| Mean bid levels | 358.664 | 390.580 | October 5 is +8.899% |
| Mean ask levels | 270.886 | 257.847 | October 5 is -4.813% |

The exact endpoints explain the averaged regime without replacing it. October
4 moves from imbalance 0.058007 to 0.210909 while bid depth changes 1,067 to 999
and ask depth changes 950 to 651: its closing bid-heaviness is primarily
ask-withdrawal-led. October 5 moves from imbalance 0.210909 to 0.315686 while
bid depth changes 999 to 1,342 and ask depth changes 651 to 698: its additional
bid-heaviness is primarily bid-accumulation-led. The regime and mechanism views
are a `COMPLEMENTARY_SCOPE_DIFFERENCE` and are equally scientific.

## Independently reproduced exact family surface

### Post-fill lifecycle and cascade families

| Exact action family | 2021-10-04 | 2021-10-05 | Mechanically verified content |
|---|---:|---:|---|
| `TFCN` | 38,510 | 39,766 | Every fill ID continues into a same-ID cancel |
| `TFM` | 6,173 | 6,605 | Every fill ID continues into a same-ID modify |
| `TFMN` | 1,910 | 1,833 | Same-ID modify followed by a distinct neutral close |
| `TFFCCN` | 7,037 | 7,522 | All 14,074/15,044 fill IDs continue into later cancels |
| `TFTFCCN` | 819 | 832 | All 1,638/1,664 fill IDs continue into later cancels |
| `TN` | 1,901 | 2,204 | Trade followed by a distinct neutral F_LAST close |

The principal mirrored side counts also reproduce exactly: `TFCN` has
`ABBN` 17,750/18,344 and `BAAN` 17,197/18,233; `TFM` has `ABB`
2,567/3,310 and `BAA` 2,878/2,707; `TFFCCN` has `ABBBBN`
3,022/3,403 and `BAAAAN` 3,030/3,226; and `TFTFCCN` has
`ABABBBN` 352/349 and `BABAAAN` 358/340 by October 4/5.

### Open-world extensions and elementary queue vocabulary

| Family | 2021-10-04 | 2021-10-05 | Positive structure |
|---|---:|---:|---|
| `TFC` / `TFFCC` | 7,950 / 829 | 8,268 / 912 | Unclosed one-/two-fill disposition |
| `TFFFCCCN` | 2,193 | 2,382 | Three-fill cascade |
| `TFFFFCCCCN` | 664 | 803 | Four-fill cascade |
| `TFFFFFCCCCCN` | 207 | 321 | Five-fill cascade |
| `TFFCM` / `TFFCMN` | 404 / 313 | 421 / 360 | Split cancel/modify disposition |
| `TFTFCMN` | 183 | 189 | Repeated contact with split disposition |
| `TFACN` / `TFCAN` | 448 / 409 | 471 / 416 | Add-interleaved replenishment timing |
| `A` / `AN` | 590,918 / 97,879 | 615,022 / 105,958 | Resting-order birth vocabulary |
| `C` / `CN` | 516,259 / 66,469 | 534,916 / 71,149 | Withdrawal vocabulary |
| `M` / `MN` | 145,701 / 12,315 | 166,389 / 13,980 | Residual-order resizing vocabulary |

This independent A-memory reproduction confirms the exact native family surface
while preserving rare, split, add-interleaved, and higher-multiplicity members.
It does not turn the taxonomy into a closed label set.

## New positive finding: mirrored formation-latency asymmetry

For each row below, the arithmetic mean is calculated only within one source
day, exact action family, and exact side sequence. Latency is final F_LAST
`ts_recv_ns` minus the first component's `ts_recv_ns`. No family, side, day,
session, phase, or cluster is pooled.

| Day | Exact family | Bid-resting mirror: n / mean us | Ask-resting mirror: n / mean us | Ask minus bid mean |
|---|---|---:|---:|---:|
| Oct 4 | `TFCN` | `ABBN`: 17,750 / 101.016 | `BAAN`: 17,197 / 112.715 | +11.698 us (+11.581%) |
| Oct 5 | `TFCN` | `ABBN`: 18,344 / 107.577 | `BAAN`: 18,233 / 117.320 | +9.743 us (+9.057%) |
| Oct 4 | `TFM` | `ABB`: 2,567 / 62.227 | `BAA`: 2,878 / 70.462 | +8.235 us (+13.235%) |
| Oct 5 | `TFM` | `ABB`: 3,310 / 61.593 | `BAA`: 2,707 / 72.877 | +11.284 us (+18.320%) |
| Oct 4 | `TFMN` | `ABBN`: 669 / 97.415 | `BAAN`: 908 / 102.248 | +4.834 us (+4.962%) |
| Oct 5 | `TFMN` | `ABBN`: 803 / 100.267 | `BAAN`: 763 / 111.861 | +11.594 us (+11.563%) |
| Oct 4 | `TFFCCN` | `ABBBBN`: 3,022 / 105.848 | `BAAAAN`: 3,030 / 119.735 | +13.887 us (+13.120%) |
| Oct 5 | `TFFCCN` | `ABBBBN`: 3,403 / 109.738 | `BAAAAN`: 3,226 / 122.371 | +12.633 us (+11.512%) |
| Oct 4 | `TFTFCCN` | `ABABBBN`: 352 / 110.418 | `BABAAAN`: 358 / 123.223 | +12.805 us (+11.597%) |
| Oct 5 | `TFTFCCN` | `ABABBBN`: 349 / 112.208 | `BABAAAN`: 340 / 130.703 | +18.495 us (+16.483%) |

All ten independently stratified comparisons have the same sign: the
ask-resting orientation takes longer on average to reach lawful F_LAST than its
bid-resting mirror. This is a new positive native timing correlation. It is not
yet attributed to economic behavior rather than venue/feed sequencing.

**Scientific hypothesis M1.** Mirrored post-fill and cascade families carry a
stable side-oriented formation-latency state relevant to earliest lawful
recognition. The corrected rerun should test exact members within fixed channel,
session, price, size, multiplicity, and activity phase. Falsifiers are a sign
reversal after those controls, confinement to a boundary/reset interval, or a
demonstrated deterministic feed-serialization cause with no market-state
content.

## New native confirmation and tightening of authorized prior memory

The prior-memory package retained a final October 5 window with 41 trades,
full-window signed quantity imbalance -0.111111, ordered-half transition
-0.36 to +0.20, and price drift 6.333 to 6.329 (-0.004). The A-memory native
ledger independently reproduces every one of those quantities from exact `T`
actions in the half-open event-time window
`[1633477500000000000,1633478400000000000)`:

| Exact native view | Population and stratum | B size / A size | Signed B-minus-A size imbalance | First / last price | Drift |
|---|---|---:|---:|---:|---:|
| Full 15-minute window | 41 `T` actions; 17 B, 17 A, 7 N | 20 / 25 | -0.111111 | 6.333 / 6.329 | -0.004 |
| Ordered first 20 trades | Exact first member half | 8 / 17 | -0.360000 | 6.333 / 6.325 | -0.008 |
| Ordered last 21 trades | Exact second member half | 12 / 8 | +0.200000 | 6.327 / 6.329 | +0.002 |
| Clock first 7.5 minutes | 24 trades | 9 / 17 | -0.307692 | 6.333 / 6.327 | -0.006 |
| Clock last 7.5 minutes | 17 trades | 11 / 8 | +0.157895 | 6.329 / 6.329 | 0.000 |

The ordered-member split and equal-clock split answer different questions and
therefore form a `COMPLEMENTARY_SCOPE_DIFFERENCE`, not a contradiction. Both
show negative early flow giving way to positive late flow; the ordered-member
tail has a +0.002 price response, while the equal-clock tail is flat from its
first to last print.

The first exact trade event occurs at `1633477559288543675` and becomes lawful
at group close `1633477559289024271`. The final trade event occurs at
`1633478340871744473` and becomes lawful at group close
`1633478340872057922`. Thus the native ledger adds exact member identity and
availability clocks to the previously retained motif.

The final retained 298.143984377-second native activity window contains 310
exact actions: 106 `A`, 128 `C`, 27 `M`, 8 `T`, 10 `F`, and 31 `N`. Its eight
trade prices are `6.327, 6.325, 6.329, 6.330, 6.329, 6.329, 6.330, 6.329`.
The final price is +0.002 from the first trade and +0.004 from the first
side-resolved trade while the final book remains 1,342 bid depth versus 698 ask
depth.

**Scientific finding M2.** The prior balance-cross motif is no longer supported
only by a reduced-surface summary: its trade count, signed quantities, ordered
halves, price path, and late positive response are independently present in
native A-memory MBO with lawful group-close clocks.

**Scientific hypothesis M3.** A sell-flow weakening candidate strengthens when
an exact negative full window contains a positive late-flow segment, a
non-negative late price response, and persistent bid-heavy depth. It remains a
conditional stabilization/absorption hypothesis, not a guaranteed direction.
Falsifiers are renewed negative exact flow/price coupling, bid-side withdrawal
that removes the relative-depth advantage, or failure to recur under a
prospectively fixed same-session definition.

## Exact lifecycle, recurrence, and session anchors

Order `786260864394` supplies a complete three-group lifecycle:

1. group 1,166,147: `AN` births an ask order of size 3 at 5.758;
2. group 1,166,161: `TFMN` fills size 2 and modifies the same order to size 1;
3. group 1,166,162: `TFCN` fills and cancels the residual size 1.

The birth group closes at `1633306067336003229`; the partial-fill group first
arrives 4.297458097 seconds later. The residual-completion group first arrives
20,400 ns after the partial-fill group closes. This exact `AN -> TFMN -> TFCN`
chain positively connects order birth, partial depletion/resizing, and residual
completion without averaging away identity.

Immediate exact-family recurrence also exists in both held-out days. Maximum
consecutive runs are `TFCN` 4/4, `TFM` 8/8, `TFMN` 7/3, `TFFCCN` 2/3, and
`TFTFCCN` 2/1 for October 4/5. Exact immediately adjacent edges include
`TFMN -> TFCN` 398/393, `TFM -> TFM` 940/1,046, and
`TFFCCN -> TFCN` 227/257. These counts remain day- and edge-specific.

The deterministic session withdrawal anchors reproduce exactly:

| Group | Event time ns | First receive ns | F_LAST availability ns | Cancels | Bid / ask cancels | Cancel size |
|---:|---:|---:|---:|---:|---:|---:|
| 2,654,677 | 1633381200078569755 | 1633381200235943540 | 1633381200237256020 | 430 | 219 / 211 | 796 |
| 4,237,483 | 1633467600078400519 | 1633467600226788647 | 1633467600228110022 | 581 | 371 / 210 | 1,179 |

These groups are separate session phases, not intraday burst members or inputs
to a pooled daily family average.

## Positive exhaustion-research program for the corrected rerun

1. **Post-fill disposition:** retain exact `TFCN`, `TFM`, and `TFMN` members to
   distinguish withdrawal from residual-order resizing.
2. **Cascade multiplicity:** search exact transitions among one-, two-, three-,
   four-, five-fill, repeated-contact, and split-disposition families.
3. **Mirrored timing asymmetry:** prospectively test M1 with fixed family, side,
   session, channel, size, price, multiplicity, and causal phase.
4. **Memory-guided balance cross:** prospectively test M2/M3 with exact native
   trade members, full FIFO durability, lawful flow/price clocks, and no
   backdating.
5. **Order-lifecycle chains:** enumerate content-derived same-order chains such
   as `AN -> TFMN -> TFCN`, preserving every member and inter-group gap.
6. **Recurrence and phase:** retain exact same-family runs, directed family
   edges, and 21:00 withdrawal/restart phases separately.
7. **Coequal views:** report exact members alongside arithmetic companions only
   within identical day/family/subfamily/side/session/phase/clock strata.

## Positive knowledge capsule candidates

1. **Native confirmation of authorized memory:** Exact A-memory MBO reproduces
   the prior 41-trade final-window motif: signed B-minus-A size imbalance
   -0.111111, ordered halves -0.36 to +0.20, and price drift -0.004, now with
   exact action identities and lawful group-close clocks.
2. **Late response refinement:** The ordered late half delivers +0.002 price
   response and the final 298.144-second exact tail delivers +0.002 from its
   first trade (+0.004 from its first side-resolved trade) while final depth
   remains bid-heavy at 1,342/698.
3. **New mirrored timing correlation:** Across five principal mirrored families
   on both held-out days, ask-resting members take 4.834-18.495 microseconds
   longer on average to reach F_LAST than bid-resting mirrors, with separate
   populations and denominators retained.
4. **Mechanism-separated regime:** October 4's closing bid-heaviness is
   ask-withdrawal-led; October 5's additional bid-heaviness is
   bid-accumulation-led. Daily regime and exact mechanism are coequal scientific
   findings.
5. **Exact lifecycle:** Order `786260864394` follows
   `AN -> TFMN -> TFCN`, connecting birth, partial fill/resizing, and residual
   completion with exact member and clock identity.
6. **Open-world cascade surface:** Three-, four-, and five-fill cascades,
   split cancel/modify branches, repeated-contact split branches, and
   add-interleaved variants recur on both held-out days and remain distinct.
7. **Session segmentation:** The exact 21:00 UTC 430-cancel and 581-cancel
   groups are deterministic withdrawal anchors and must remain separate causal
   phases.

## Classification

`RETROSPECTIVE_ROLE_ANALYSIS`; A-memory only; positive scientific findings;
read-only native-ledger analysis; verified prior memory used; no principal
Frankie invocation; no principal-execution lock/freeze; no corrected full rerun;
no Forecaster run.
