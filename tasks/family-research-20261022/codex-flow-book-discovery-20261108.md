# Codex October NG flow and book discovery

Independent Codex research notes, November 8, 2026. The user requested separate
Markdown findings for the independent reviewers, to merge at the end. This file
therefore carries this review's findings and interim table index; the shared
October discovery log is unchanged. Claude should retain its own interpretation.

Source evidence is pinned to `b5f28bd57de5ed4ff889335edb9a33216b67eb6a`, including
the original 749 SQLite family starts, the original 50 matches, the October 18
group export and the 863 reconstructed dipoles. The updated research handoff is
`5724f4096248dd8080aa381a34855097c685dc1c`. Raw message extracts use
`1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202`. These are the common inputs available
to both reviewers. All four dates remain discovery; October 2 and 17 are partial.

## What the current comparison says

**NG-FLOW-BOOK-v1.** Recent signed flow, the local quote, and total displayed depth
describe different things. Total depth was bid-heavy at all 749 saved family
starts. It cannot distinguish these cases by sign, even though its magnitude
varies. Local touch depth can oppose that whole-book sign. The original 50-case
stack has both subsequent directions and flats. Its five-minute downward
majority largely disappears as a mean difference against the selected activity
controls. The four-arm model probe does not establish a general benefit from
stacking flow with this book representation.

**NG-DIPOLE-POST-RECOGNITION-v1.** The detector tracks the shape of rolling signed
trade imbalance, whose changes can reflect new prints or old prints aging out.
Persistence or reversal of that ratio is different from persistence or reversal
of price. Most one-second midpoint outcomes after actual recognition are flat.
Birth-to-recognition descriptions should not be presented as future forecasts.

**NG-391-SWEEP-AND-REST-v1.** The initial sell sweep and the subsequent large offer
in case 391 share an order ID. That offer then receives 150 lots of passive fills
and is removed before the quote recovers. The observed switch from aggressive
execution to resting liquidity, then opposite-side execution against it, links
two previously separate parts of this case. It does not identify trader intent,
establish a trade signal, or show how often this specific mechanism occurs in
the other 48 original cases.

## Cohort, controls and contrary observations

The opportunity is a first-observed structural family, not the birth of its
orders, the first onset of the pressure condition, or an unconditional market
opportunity. Predictors use the retained strict-pre family projection and the
last completed group satisfying both the receive cutoff and cursor cap. Outcomes
use the last observed valid midpoint at or before the declared horizon. Exact
source groups, cursors, nanosecond clocks, quote ages, raw changes, ticks and
percentage changes are retained. Halt/reset crossings and session-end censoring
stay explicit. An old but unchanged quote is retained with its age, not treated
as a fresh transaction.

| Original 50-case stack: horizon | Down | Flat | Up | Overlapping-window clusters |
| --- | ---: | ---: | ---: | ---: |
| 1 second | 23 | 6 | 21 | 48 |
| 5 seconds | 23 | 3 | 24 | 46 |
| 20 seconds | 23 | 10 | 17 | 43 |
| 60 seconds | 29 | 5 | 16 | 35 |
| 300 seconds | 33 | 1 | 16 | 23 |

The screen reproduces the exact 50 original instance IDs. Among all 749 starts,
437 have usable one-, five- and 60-second signed ratios; 312 lack at least one
ratio, commonly because the denominator has no classified volume. Missing flow
is not balanced flow. The complete input cohort for all four arms is 437.
There are 749 available outcomes at one and five seconds, 748 at 20 and 60,
and 742 at 300 seconds before common-input filtering.

**Unsupported inverse and a useful partial contrast.** Full-book imbalance
ranges from +0.014737 to +0.416769 across all 749 starts. There are zero exact
inverse-stack cases because the required ask-heavy full book never occurs.
There are 45 cases with inverse *flow* alone: sell-heavy 60 seconds followed by
buy-heavy five and one seconds. Preserve these as a separate comparison, not
as fabricated support for the full inverse stack.

Local touch direction changes the interpretation of the same aggregate stack.
Of the original 50, 21 have touch imbalance aligned with recent selling, 24
oppose it, and 5 have equal touch size. At one second, aligned cases have
12 moves with selling, 6 against and 3 flat; opposed cases have 9 with,
13 against and 2 flat. The inverse-flow cohort does not reproduce that contrast:
its 21 aligned cases have 12 moves with buying, 4 against and 5 flat, versus
11 with, 5 against and 5 flat among 21 opposed cases. These small, overlapping,
selected cohorts challenge a universal alignment rule.

For each original match, the descriptive control is another family start in the
same UTC hour and spread, nearest in log(1 + 60-second classified lots), then in
clock distance. This uses no later outcome. Matching uses replacement: 50 pairs
reuse 35 controls. The median absolute log-activity difference is 0.0653 and the
maximum is 0.7538; there is no caliper, so some matches are loose. Mean case-minus-
control midpoint changes are -0.00015 at one second, -0.00103 at 60 seconds, and
-0.00006 at 300 seconds. The original five-minute mean is -0.00059 versus
-0.00053 for its controls. Overlap and imperfect balance prevent a causal or
independent-significance interpretation.

[Opportunities](flow-book-discovery-v1/opportunities.csv.gz) ·
[All outcomes](flow-book-discovery-v1/outcomes.csv.gz) ·
[Cohort distributions](flow-book-discovery-v1/cohort-outcomes.csv) ·
[Setup cross-tabs, including inverse flow](flow-book-discovery-v1/setup-crosstabs.csv) ·
[Matched controls](flow-book-discovery-v1/activity-controls.csv) ·
[Paired outcomes](flow-book-discovery-v1/activity-control-outcomes.csv)

## Four comparable arms

The baseline includes spread, unsigned classified activity at one and 60 seconds,
and prior midpoint changes over one and five seconds. The flow arm adds the three
signed ratios. The book arm adds touch imbalance and size, changes in touch
imbalance, same-price display changes with explicit price-movement flags, and
near/full-depth imbalance. Both includes both blocks, additively. Display changes
are not relabeled as fills or cancellations. This is a limited representation of
book behavior; it does not encode every queue or order mechanism.

Ridge uses fixed alpha 10, training-only scaling and intercept, three expanding
chronological splits starting at 40%, 60% and 80%, outcome-end purge and a
600-second embargo. All arms use the same rows and outcomes. There are 263 test
predictions per arm at each horizon through 60 seconds, and 260 at 300 seconds.
These are within-day discovery probes, not external validation or admitted
scoring models. The arm names mean baseline **plus** the named block.

| Target / horizon | Baseline MAE | Flow MAE | Book MAE | Both MAE |
| --- | ---: | ---: | ---: | ---: |
| Signed / 1 s | 0.001509 | 0.001505 | 0.001770 | 0.001714 |
| Signed / 20 s | 0.002450 | 0.002513 | 0.002796 | 0.002829 |
| Signed / 60 s | 0.003009 | 0.002997 | 0.003245 | 0.003219 |
| Signed / 300 s | 0.006206 | 0.006198 | 0.006710 | 0.006709 |
| Absolute / 1 s | 0.001151 | 0.001153 | 0.001268 | 0.001266 |
| Absolute / 20 s | 0.001930 | 0.001897 | 0.001933 | 0.001912 |
| Absolute / 60 s | 0.002061 | 0.002060 | 0.002001 | 0.001998 |
| Absolute / 300 s | 0.004279 | 0.004275 | 0.004426 | 0.004430 |

Table values pool individual test-row absolute errors, rather than giving unequal
fold sizes equal weight. All five horizons and each fold remain in the artifacts.
Book and both worsen pooled signed error at every tested horizon. Absolute-move
results differ by horizon and fold: both improves 60-second absolute error in
folds 1 and 3 but slightly worsens it in fold 2; at 20 seconds it worsens fold 1
and improves folds 2 and 3. This is contrary evidence to a uniformly helpful stack.
Negative predictions for the absolute target remain recorded, without clipping.

The first exploratory pass purged only overlapping labels. Its metrics,
predictions and splits are preserved under `initial-no-embargo/`. The reported
pass adds the standing protocol's 600-second embargo. This was a protocol
correction, not selection of an embargo to improve results. Both outcomes remain
available. No hyperparameter search was performed.

[Exact method and feature lists](flow-book-discovery-v1/method.json) ·
[Fold metrics](flow-book-discovery-v1/arm-metrics.csv) ·
[Every prediction](flow-book-discovery-v1/arm-predictions.csv.gz) ·
[Train/test membership and clocks](flow-book-discovery-v1/chronological-splits.csv) ·
[Initial pass](flow-book-discovery-v1/initial-no-embargo/arm-metrics.csv) ·
[Reproducible comparison code](flow_book_discovery.py)

## What cases 375 and 391 add to the broad comparison

The original full-depth condition is shared, but the local touch differs.
Case 375's strict-pre G233425 / cursor 303645 has bid size 7 and ask size 25:
touch imbalance -0.5625, aligned with recent selling. Case 391's G244933 /
cursor 319188 has bid size 4 and ask size 3: +0.142857, opposing recent selling.
Both subsequently fall. Case 391 therefore remains a counterexample to treating
a bid-heavy touch as protection from the next decline. The following later
events explain parts of the path, but were not all available at those decisions.

| Case and source coordinates | Observed mechanism and availability |
| --- | --- |
| 375, cursors 303542–303552 | Before the family anchor, new offers of 5 and 4 lots join at 3.156. A one-lot trade at 3.155 is followed by a five-lot trade, passive fills and linked removals of bid orders 788701294308 and 788701294279. G233368 closes with the lower bid. Offer growth preceded this quote change by fractions of a millisecond; this does not establish executable advance warning. |
| 375, cursors 303646–303656 | The family group includes an eight-lot trade summary at 3.152, six lots of identified passive fills and seven lots of bid removals. Keep those distinct totals; do not force trade summaries and visible passive messages into one conserved quantity. Completed-group recognition is 1697634552081390598 ns, after the raw actions. |
| 391, cursors 319189–319233 | Order 788701345922 appears in trade summaries for 4 lots at 3.139, 15 at 3.138 and 31 at 3.137, then in an add of 150 offer lots at 3.137. The same order ID links the sweep to the resting offer, consistent with an unexecuted remainder becoming displayed liquidity. The group closes at 1697634840878613141 ns with bid 3.136 and ask 3.137. These are family-group outcomes relative to the frozen prior completed quote. |
| 391, that order's later fills through cursor 319627 | The displayed offer receives 150 lots of identified passive fills. Its modifies reduce displayed quantity, and the final 44-lot fill is followed by a 44-lot removal. Another one-lot offer also fills and is removed. G245219 / cursor 319629 closes at 1697634841082639442 ns with the next ask exposed. This is 204.026301 ms after the family close. |

The last sequence resolves a previously open distinction: that offer's final
disappearance is fill-linked, rather than an unexplained withdrawal. It also
shows why a large displayed ask can be both an immediate obstacle to recovery
and liquidity against which recovery demand executes. Subsequent bid improvement
and later renewed declines remain separate steps. Both 375 and 391 eventually
recovered their strict-pre midpoint; their different five-minute endpoints do
not describe uninterrupted continuation versus reversal.

The initial 391 trade summaries total 50 lots; the retained passive fills within
that initial group total 40. The later 150-lot resting-order sequence is a
separate directly linked observation. Native order identity does not identify
the beneficial owner, the trader's total position, urgency or loss aversion.
The raw extracts cover one second before through five seconds after each family
anchor: 1,612 messages for 375 and 1,207 for 391. Mechanism frequency across all
50 remains unmeasured; the complete cohort outcomes above provide the broader
context without inventing the missing order-level prevalence.

[Original messages with order IDs and UTC-member record indices](flow-book-discovery-v1/case-original-messages.csv.gz) ·
[Raw source and exact extraction spans](flow-book-discovery-v1/original-message-source.json) ·
[Both cases' retained measurements](flow-book-discovery-v1/case-375-391-measurements.csv) ·
[Earlier continuous quote and queue evidence](../../artifacts/sqlite-triage/20261022/families/trading-episode-375-391/availability-evidence-ledger.csv)

## Dipoles after actual recognition

Outcomes here start at the actual recognition close, not the nominal availability
second or the birth second. Orientation is relative to birth polarity, including
when the rolling flow has already reversed. These are 863 selected recognitions;
unrecognized opportunities are outside this cohort.

| Flow state at recognition | Cases | Same as birth at +1 s | Flat at +1 s | Opposite at +1 s |
| --- | ---: | ---: | ---: | ---: |
| Still same direction | 275 | 29 | 211 | 35 |
| Reversed direction | 217 | 28 | 164 | 25 |
| Balanced, classified volume present | 26 | 3 | 17 | 6 |
| Undefined, no classified volume | 345 | 38 | 279 | 28 |

Together, 671/863 are flat at one second. This differs from the earlier
birth-to-recognition table, which describes movement already realized when the
candidate appears. At 300 seconds, the still-same cohort has 131 with birth,
126 against and 15 flat among 272 available outcomes; three are censored.
The reversed cohort has 93 with birth, 106 against and 17 flat among 216
available outcomes. Both directions remain substantial.

The broad distinction appears in the same pinned concrete cases:

- `dip-19648-1697581215`, recognition G2363 / cursor 3411: empty recent flow,
  flat midpoint at +1, +5 and +20 seconds. The +20 endpoint is G2533 /
  cursor 3612, receive 1697581282196212863 ns.
- `dip-19648-1697583021`, recognition G6230 / cursor 7726: the intervening ask
  sweep had already happened and aged out of the rolling window. The midpoint
  is flat at +1 second, then down 0.0005 at +5, +20 and +60. A mechanism that
  explains the earlier rise does not guarantee continuation after recognition.
- `dip-19648-1697625921`, recognition G112817 / cursor 141147: late flow is
  14 buy versus 39 sell lots while the birth-to-recognition midpoint had risen.
  It is flat over all sampled endpoints through +60 seconds, then up 0.0030 at
  +300, endpoint G114709 / cursor 143584, receive 1697626236183886050 ns.
- `dip-19648-1697607905`, recognition G42542 / cursor 51260: late flow is
  4 buy versus 25 sell lots. Post-recognition midpoint first rises 0.0005 at
  +1 second, falls 0.0005 at +5 through +60, and rises 0.0025 at +300.
  Endpoint signs alone conceal the changing path.

All exact recognition and endpoint coordinates, quote ages, percentage changes,
flow numerator/denominator operands and censoring are retained. Holding quotes
through quiet intervals can produce flat endpoints without a fresh price test.

[All recognition-to-outcome rows](flow-book-discovery-v1/dipole-after-recognition.csv.gz) ·
[Every state/horizon summary](flow-book-discovery-v1/dipole-after-recognition-summary.csv)

## The 99 planes, 13 inputs and cross-layer questions

The [99-role table](flow-book-discovery-v1/all-99-relationship-roles.csv) preserves
every registry entry. Market mechanisms, derived transforms, source clocks,
controls, runtime records and later outcomes have different research roles;
the registry is not 99 independent numerical predictors. The retained numeric
screen covers 135 local feature definitions and 89 selected external field/series
combinations, 224 total. It keeps all 14,784 attempted rank comparisons across
the whole cohort, original 50 and four chronological quarters, including
constant and insufficient-support results. It provides hypotheses rather than
significance claims or new semantic admission.

**NG-RELATION-SCOPE-v1.** One-second flow imbalance has pooled Spearman +0.3069
with the next one-second signed move on 437 defined observations. Each quarter
is positive (+0.4543, +0.3110, +0.1986, +0.2904). Yet the four-arm flow increment
is small and does not uniformly improve errors. Correlation and incremental
forecast value answer different questions when the baseline already contains
activity and recent price response.

Full-book imbalance has pooled +0.2370 rank correlation with 20-second absolute
move on 748 observations, but quarter correlations are -0.0064, +0.1429,
-0.1231 and +0.0875. The pooled association is not a stable within-quarter
relationship. Similarly, far-size retention has pooled -0.1381 correlation with
the next one-second signed move on 617 observations, but +0.0414 among the
43 original-stack cases with that field. Queue identity survival shows a related
change. These are plausible context interactions and shared-measurement effects,
not evidence that a far queue universally predicts the opposite direction.

The [13-point coverage table](flow-book-discovery-v1/all-13-point-coverage.csv)
keeps the original bindings and source dependencies. Points 1, 3 and 4 reuse one
NYMEX positioning source; 5 and 7 reuse the power source; 2 and 9 share weather
inputs. Positioning, storage and the carried storage surprise have no changing
source row across these 749 starts, so they cannot identify an intraday revision
effect here. Weather and curve series vary, but variation alone does not identify
which mechanism caused a short quote move. Point 6 is present in only 90 saved
contexts under its declared availability; do not backfill its later timestamp.

**NG-CURVE-CLOCK-COMMON-DRIVER-v1.** Of 62 external series rows per case, 18 have
different retained source ordinals between 375 and 391: one traded-curve series
and 17 station-weather series. Most carried positioning, storage, forecast and
power context is identical. The curve update for 375 is stamped
1697634552081117158 ns, the exact receive clock of the family group's trade at
cursor 303646. For 391 it is stamped 1697634840877425246 ns, the initial sweep's
receive clock at cursor 319189. Both are before the family close but after the
frozen previous completed book. This is a concrete shared-source/timing
alternative to interpreting the curve as an independent warning.

External operands preserve a `published_after_prequote` flag. Their exploratory
correlations use the saved declared publication cutoff, which can include these
partial-group trades; they are not inputs to the four-arm model. A subsequent
test must align all sources to one declared decision boundary and separate the
front leg's reused trade from genuinely independent maturity information.
Station changes need their underlying values and availability examined before
they can explain the divergence; a changed row ID is not a demand surprise.

[All field relationships](flow-book-discovery-v1/all-field-relationships.csv.gz) ·
[Local coverage and missing reasons](flow-book-discovery-v1/measurement-coverage.csv) ·
[External series coverage](flow-book-discovery-v1/external-series-coverage.csv) ·
[Exact external operands and source rows](flow-book-discovery-v1/external-operands.csv.gz) ·
[Both cases' original external records](flow-book-discovery-v1/case-375-391-external.csv.gz) ·
[Relationship method](flow-book-discovery-v1/relationship-method.json) ·
[Extraction and relationship code](flow_book_relationships.py)

## Psychology and competing explanations to carry forward

| Hypothesis | Observable support, contrary evidence and discriminating test |
| --- | --- |
| Urgent selling followed by relief or aggressive bargain buying | Case 391's sweep, resting remainder and later opposite-side fills fit the observable sequence. Ordinary algorithmic slicing, hedging or inventory adjustment can produce the same sequence. Compare sweep-to-rest episodes with similarly sized sweeps without a resting remainder, matched on prior flow, spread and depth. Participant positions or execution instructions would distinguish motives. |
| Defensive withdrawal amplifies selling | Case 375 has lower bids removed and new lower offers during the decline. Some removals are fill-linked; treating every C message as voluntary withdrawal would be wrong. Compare order-linked fill reductions with unmatched removals at fixed prices before the decision. |
| Absorption or resilient liquidity predicts a rebound | Case 391's large ask is completely executed and bids recover, but earlier bid reappearances preceded another drop. The original 50 also include contrary and flat outcomes in every touch-alignment stratum. Distinguish execution against a surviving order, new displayed orders, and price improvement; test what was known before the intended decision. |
| Shared information rather than distinct signals | Flow, midpoint, dipoles and the front curve leg reuse trades; several external inputs reuse the same source. Compare independently timed other-maturity changes and genuine publication revisions after controlling for local activity. The existing evidence does not supply trader intent or an independent surprise for these two cases. |

These are retained hypotheses, not psychological diagnoses or selected simulator
rules. Position/P&L data, complete participant identity and private stop or margin
instructions remain unavailable. Candidate recognition, historical path labels,
scoring admission and simulator execution remain separate. No paper ticket,
order, fill, fee-adjusted return or new noise judgment is asserted.

## Four-date table index: observed November 8 at 18:03 UTC

These are interim locations and compact captures, not completion claims.
Runtime revision from the execution handoff is
`6f9178bbb97721c7a71e94bb602ac256db348c87`. The existing heartbeat owns monitoring
and recovery. It was updated at the user's request to save each completed day's
unique data/code to Git, confirm publication, then shut down its idle original
pod independently. Shared network volume `qu5lhaqqbx` must remain intact.

| Date | Coverage and currently retained outputs | Job/standalone status at capture |
| --- | --- | --- |
| October 2 | Partial. 75,597 per-second flow and roll20 observations, seconds 1696204800–1696280396. Price summary reports 37,670 prints. ROOT references report 600,291 frames/structures; bulk spools remain remote. | `failed root-native exit=1` at 17:54:21 UTC; standalone held. These derived tables do not establish Native completion. [Index and exact paths](flow-book-discovery-v1/date-tables/20231002/table-index.json) |
| October 3 | Full-session tape scope. No small derived tables in the targeted locations at capture. | `root-native`; standalone waiting. [Index and exact paths](flow-book-discovery-v1/date-tables/20231003/table-index.json) |
| October 17 | Partial. 75,579 per-second flow and roll20 observations, seconds 1697500816–1697576394. Price summary reports 33,451 prints. | `root-native`; standalone waiting. [Index and exact paths](flow-book-discovery-v1/date-tables/20231017/table-index.json) |
| October 18 | Full session. 583,688 retained groups, 30,739 prints, historical ROOT/Native and reconstructed candidate evidence at the pinned revisions above. | Existing retained evidence reused for this research. [Shared historical index](october-discovery-log.md) |

Each remote control folder is `/opt/frankie-box/replay-control/YYYYMMDD`.
Actual ROOT data is under
`/opt/frankie-box/work/experiment-roots/ng-replay-YYYYMMDD/work/derived/`;
standalone output location is `/opt/frankie-box/work/standalone-inputs/YYYYMMDD/`.
The captures preserve small derived JSONs losslessly as gzip, including full
per-second arrays and spool references. `legacy_price.json` is the producer's
first/last summary, not a complete print export. Bulk frames/structures have not
been copied or claimed safely archived by this review. In particular, the October
2 frame reference reports 520,064,232,895 bytes; its remote pointer alone is not
sufficient grounds to shut down the pod. Save/shutdown remains the heartbeat's
separate task after necessary outputs and unique data are safe.

[Targeted table capture code](capture_discovery_table_index.py)

## Validation and remaining work

The new focused tests cover strict nanosecond/cursor boundaries, missing versus
balanced flow, inverse-stack classification, and exclusion of overlapping
training labels. The study also checks exact original-50 membership and each
retained family prequote's group/cursor against the standalone table. No prior
producer, teacher, receipt audit, old Search or AWS job was rerun.

Remaining work is explicit: reconstruct order-level prevalence beyond these two
cases; distinguish conditions at family starts from unselected market
opportunities; compare the other dates when their actual tables arrive; test
queue and independent external additions with aligned clocks; and merge the
independent reviewer notes while preserving disagreements. None of those pending
steps is replaced by the descriptive correlations or this limited ridge probe.
