# Whole-day flow, quotes and external context: broader explanations

This continuation uses the [original master list](../../completed-run-source-list.json), the [completed-run findings and knowledge index](../completed-run-connections-v1/run-evidence-index.json), and existing saved market data. All **30,739 original trades** remain separate with unchanged fields and exact integer clocks/cursors. Original nested sources, all 48 external series, the complete 211,055-row external history, Frankie knowledge and original model forecasts remain available, including later evidence. No source was removed because it was flat, contradictory, missing or not useful to this particular comparison.

The completed run taught us to separate transaction paths from quote endpoints, inspect local book conditions with their history, and preserve directional/model disagreement. This pass applies those distinctions to the day. It does not fit a new model, infer missing aggressor sides, average predictions or certify a universal explanation.

## What the broader evidence establishes

| Competing interpretation | Checked observations | Consequence for lifecycle explanation |
|---|---|---|
| Repeated directional flow means repeated new aggression. | **2,605 of 8,088 saved completed-second flow records** have nonzero rolling signed flow with no new tape trade in that second. Fresh-trade counts agree with the original tape in **all 8,088** records. | A rolling state can persist after its contributing trades. Repeated readings do not supply additional executed volume or independent confirmations. |
| The rolling sign describes the newest pressure. | **112 saved seconds** have fresh midpoint-classified net flow opposite to the rolling signed-flow sign. **20** have fresh trades with zero rolling signed flow. | New opposing pressure, persistence of older pressure and a balanced rolling total must be distinguished. None alone is a validated price flip or exhaustion signal. |
| Every changed print indicates movement of the quoted market. | The expanded source union supplies **2,715 exact prior/close quote pairs**. **343 print changes across 340 emission groups** occur with unchanged paired quotes; **22 across 20 groups** oppose the paired midpoint change. | Print direction is not automatically quote direction or aggressor direction. The prior print and the current group comparison also cover different intervals; these flags alone do not prove bid/ask bounce or allocate a quote change to a particular print. |
| A string of up/down prints proves repeated quote reversals. | **Eight runs of consecutive groups** have unchanged closing bid/ask while their individual prints move both up and down. | Some apparent print turns can coexist with stable completed-group quotes. Intragroup excursions, trade side, order survival and execution mechanisms still require their own evidence. |
| Many external field updates mean many independent news events. | During the tape span, the existing history has **96,515 series observations at 14,463 distinct declared publication clocks**. Of those observations, **91,338** are traded-curve fields at **14,063** clocks. Shared table/source-ordinal/clock coordinates are retained explicitly. | Multiple fields from one market source row cannot be counted as independent macroeconomic confirmation. Curve observations remain useful market context; they are not automatically independent external releases. |

These are counts of individually retained observations and coverage, not pooled trading signals. The source selections are fixed saved projections, not representative sampling of every second or every action. There are no nonzero rolling-flow records without any tape print anywhere in their declared rolling window, and no source fresh-count discrepancy in this saved set. Those favorable checks remain beside all disagreements; they do not establish complete market/channel semantics.

## Exact examples at different points in the day

The original source ordinal of a trade is its zero-based trade identifier throughout this work.

- **Early opposing fresh flow:** source-flow line **3240**, second **1697580007**, contains original trades **19–21**. Fresh source net flow is **−2**, while rolling signed flow is **+4**. The record is known by **1697580008128483235**, cursor **1026**. It describes fresh selling inside a still-positive rolling balance, without proving that price must reverse.
- **Early persistence without a fresh trade:** source-flow line **3242**, second **1697580013**, has no tape trade, fresh net zero and rolling signed flow **+4**. Its actual emission is **1697580016093159688**, cursor **1056**. The source-second label is not its knowledge clock.
- **A balanced roll with a fresh sale:** source-flow line **3482**, second **1697580984**, contains trade **113**, source SELL net **−1**, rolling signed flow **0**. Known by **1697580985286343126**, cursor **2808**. A zero rolling balance is not absence of execution.
- **The same flow distinction late in the day:** source-flow line **8027**, second **1697661672**, contains trade **30515**. Fresh source net is **−2**, rolling signed flow **+6**; known by **1697661673962170457**, cursor **765267**. This keeps the early finding from being framed as unique to trades 119/134.
- **A late opposed print/quote change:** trade **27732** prints **3.056**, down **0.001** from the previous print. Its strict prior group is bid/ask **3.056/3.057**; its emission group is **3.056/3.058**. The midpoint rises while the print falls. Event **1697653801325636239**, receive **1697653801325999623**, known-by **1697653801326285090**; trade/close cursors **697480/697501**. Group membership does not make this one print the cause of the ask change.
- **A late changed print with unchanged group quotes:** trade **30690** prints **3.080**, up **0.001**, with prior and close quotes both **3.079/3.080**. Known by **1697662598264204946**, cursors **770245/770255**. This supports distinguishing transaction motion from quote progress near the day's end as well.

All matching and contrary observations remain in the complete JSONL files. Examples above are chronological illustrations; they are not favorable-outcome selections or a new trade rule.

## Continuous observations and the important coverage limit

The eight unchanged-quote runs with both rising and falling prints are all within the already saved consecutive window around instances 375/391. **They are not eight separate full-day replications.** Every intervening completed-group ordinal must be present; a missing, conflicting or invalid group breaks a run. Matching sparse endpoints never fill the gap.

For example, groups **233610–233715** retain bid/ask **3.150/3.151** across **106** consecutive group closes, containing all trades **11107–11120**. The first/last known-by clocks are **1697634552159143911 / 1697634552237928439**. Every print stays separate. Another run, groups **245009–245218**, retains **3.136/3.137** across **210** closes and all trades **11749–11772**, clocks **1697634840909745564 / 1697634841082436113**. These observations distinguish closing-quote stability from the individual transaction path. They do not certify stable quotes between group closes or identify the standing queue that supplied each trade.

The quote union preserves **64,584 placed source views at 35,147 coordinates**, plus **173 unplaced/out-of-bounds endpoints**. It combines the saved original quote-endpoint receipts, the consecutive window, selected ROOT scalar views and the already checked 32-trade books. Every overlapping view agrees on the exact scalar bid/ask under this comparison; no conflicting view was selected away. This is still only **2,715** paired trade contexts. The other **28,024 trades** remain explicitly retained without a matched pair in this union. No continuous full-day quote path is invented.

Saved own-second flow is linked to **845 trades**. That coverage is distinct from all-day tape coverage and must not be extrapolated to the other 29,894 trades. Same-second flow generally becomes available later; the exact original known-by clocks/cursors remain on every reference.

## External background, new observations and shared provenance

All 48 original series behind all 13 bindings remain available with their complete histories. During the tape span, declared observations come from traded/settled curve, hourly/daily weather, MOS, EIA930 and calendar sources. COT and storage remain background context with their saved original values and provenance; no new publication of those series appears inside this tape interval. A lack of a fresh publication is not evidence those conditions had no market influence.

**11,463 intertrade intervals** contain at least one declared publication; **381** contain a publication from a table other than `curve.traded_shape`. Every field and shared coordinate is retained, including invalid/null states, different forecast target dates and model disagreements. Intervals are `(previous trade receive, current trade receive]`, with no invented left boundary for trade zero. This is temporal navigation only. Declared publication clocks may be derived or nominal; they are not proof of live delivery, a news surprise, or the cause of the next print. Long intertrade gaps can contain several observations. No value is forward-filled over an invalid row or replaced with a later favorable observation.

The retained full history also supplies all observations outside these intervals and learned later. The daily publication index does not narrow retrospective evidence eligibility. It prevents counting shared measurements as independent news while keeping their potential economic meaning available.

## Relation to deeper liquidity and completed-run knowledge

The completed models actually used fields beyond level 10 in **125 of 126** shallow/deeper tree fits, reaching rank **265**; the saved history-removal effects also vary by horizon and include flat and contrary results. These results motivate checking local liquidity and its history rather than equating full-book size, directional flow and price response.

The checked trade 127 thin-ask depletion, trades 139–142/144 standing-offer fills, and trades 143/146/147 explicit bid depletion remain the action-level anchors for those competing mechanisms. This continuation does **not** relabel all 343 stable-quote print changes as absorption, all 112 opposing fresh-flow seconds as exhaustion, or the eight quote runs as proof of replenishment. A stable quote can coexist with changing depth or identities; only original adds/fills/modifies/cancels and queue records settle those distinctions. No new feature attribution is inferred from broad fitted gain tables, and no missing per-trade model forecast is invented.

The saved absorption counter comparison remains **819 of 832** tape-linked records with different source counter versus tape quantity. T, F and C roles and their units still govern that interpretation. Trade **119** and the unallocated ten T units of trade **134** remain unresolved. All original contradictory T/F/side records, sequence flags, MLP attempts, invalid magnitude forecasts and poor interval calibration remain intact.

## Artifacts and verification

- `all-8088-original-flow-seconds-with-tape.jsonl.gz`: every original nested flow wrapper, every matching fresh print, rolling-window tape ranges, exact emission delays and all interpretation flags.
- `all-saved-quote-source-views.jsonl.gz` and `all-unplaced-quote-endpoints.jsonl.gz`: every separate saved quote view and original payload/pointer, exact coordinate/clock checks and conversion status. These supplement the immutable originals.
- `every-trade-flow-and-expanded-quote-comparison.jsonl.gz`: every original trade and exact clocks, quote comparisons, all own-second flow refs, publication ranges, and links to all original external/second-set/model/knowledge context.
- `all-consecutive-unchanged-group-quote-runs.jsonl.gz`: every run, including singletons, with all individual trade members and explicit observation boundaries.
- `all-declared-external-publications-during-tape.jsonl.gz`: every in-span declared observation pointer, original state/reason/value, shared source coordinates and full unchanged-history reference.
- [Analysis receipt](analysis-receipt.json) and [verification](verification.json): counts, every flagged original row/trade identifier, preservation checks and scope limits.

Helpers are `tasks/family-research-20261022/analyze_day_flow_and_quotes.py`, `test_day_flow_and_quotes.py` and `verify_day_flow_and_quotes.py`. Recovered producer references distinguish fresh midpoint-classified volume, rolling signed lots and normalized roll20; they do not certify byte identity to runtime `db96f24f` or turn midpoint classification into the tape's native side.

**Semantic coverage remains NOT_PASSED; MLP reproducibility remains UNRESOLVED.** The original 120-second fold-4 max difference is **0.4313412606716156**, with log losses **1.5684192762348583 / 2.915890359438005**. Whole-day causal lifecycle explanations are unfinished. No AWS call/start, raw market-journal scan, fit, new resource or C: artifact was needed. All work is confined to the Git checkout on E:.
