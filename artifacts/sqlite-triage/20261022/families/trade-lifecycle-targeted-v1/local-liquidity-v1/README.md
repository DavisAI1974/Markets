# Local liquidity and quote changes: fixed prices, changing rank windows

The broader explanation supported by this continuation is that **liquidity at the touch, liquidity within a moving rank window, and the full resting book describe different things**. A thin touch can disappear while a large distant book remains. Nearby depth can then increase because different prices enter its measurement window. A fixed closing quote can also conceal substantial changes in displayed size. None of those observations alone identifies a fill, cancellation, surviving order or replenishment mechanism.

This work follows the [original full master list](../../completed-run-source-list.json), [completed-run findings](../completed-run-connections-v1/run-evidence-index.json), [broader flow/quote results](../day-wide-mechanisms-v1/README.md) and original Frankie knowledge. All **30,739 trades** remain unchanged and separately linked. All original market layers, external histories, model disagreements, knowledge claims and later evidence remain available. New files supplement the original nested records and full compressed ladders; they do not replace them.

## Broader explanations and their counterevidence

| Explanation supported by observed books | Checked evidence | Counterevidence and limit retained |
|---|---|---|
| Distant size can conceal a thin local level. | In **11,348** saved snapshots, full-book size skew opposes touch-size skew; in **16,261**, it opposes first-ten-level skew. | These are repeated states in one consecutive window, not independent trials or a directional model. Full depth remains relevant context; its sign does not describe every local price. |
| A quote can retreat to an already occupied next price after the old touch disappears. | Of **696 bid changes**, **341** land on the previous second bid level. Of **718 ask changes**, **357** land on the previous second ask level. | The complete-group geometry is observed. Execution, cancellation, modification and other intragroup paths remain unallocated without the corresponding action evidence. |
| A larger first-ten-level reading can accompany a worse executable quote because the rank window moves. | **340 bid retreats** and **351 ask increases** coincide with increased first-ten size. In **338 / 350**, respectively, net size change at the shared absolute prices is nonpositive. | The decomposition preserves all shared-price changes and all prices entering/leaving the window. Entry into the first ten is not a proven new order or new liquidity. Some transitions also have real shared-price size changes; they remain separate. |
| Stable closing quotes can conceal changing local liquidity. | **4,737 bid-side** and **4,590 ask-side** transitions change displayed touch size while that side's best price is unchanged. In constant-quote paths, **488 bid** and **445 ask** paths have both size increases and decreases. | Snapshot differences are net displayed changes. They do not separate gross adds, fills, cancels or order turnover. Front age/concentration fields remain retained, without declaring identity survival from them. |
| Equal endpoint sizes can conceal intermediate depletion and recovery. | **126 bid** and **141 ask** constant-quote paths return to their starting touch size after intermediate changes. | Every intermediate signed size change remains recorded. These counts do not establish replenishment by the same order or hidden liquidity. |
| Quote changes require more than reading the tape alone. | **863 quote-changing groups** in the continuous window contain no T from the original complete trade inventory. | This means no recorded T in those groups, not proof of no F, no execution elsewhere or maker cancellation. Original same-emission queue/replenishment refs remain attached where saved. |

All counts preserve individual observations. No average, fitted rule, model vote or favorable-outcome selection was made. A group may change both bid and ask; the side counts overlap. Several trades may share a group; their evidence is not independent.

## Exact rank-window example

Transition **50**, native groups **229250 → 229251**, shows:

| Measurement | Before | After |
|---|---:|---:|
| Best bid | 3.152 | 3.151 |
| Displayed size at old bid 3.152 | 1 | 0 |
| Displayed size at 3.151 | 10 | 10 |
| Full bid size | 2,128 | 2,127 |
| First-ten bid size | 178 | 199 |

The nine shared first-ten prices have **zero net size change**. Price **3.142**, with size **22**, enters the first-ten window; price **3.152**, with size **1**, leaves it. Thus the measured near-depth change is exactly **0 + 22 − 1 = +21**, although the best bid falls and full bid size decreases. This is evidence about moving measurement boundaries and local level disappearance. It is not evidence that 21 units were added, or that the disappeared unit was cancelled rather than filled.

The after-book is known by **1697634435800983734**, cursor **297950**. There is no recorded T in that completed group. All original first-ten rows and full source-row ranges remain linked. The ask side's first-ten size is unchanged in this transition.

This decomposition is saved for **both sides of every one of the 22,193 consecutive transitions**, including zero, negative, mixed and contrary cases. It does not rely on this example alone.

## Thinness is a condition, not a sufficient prediction

All outcomes after a recorded size-one touch are retained:

| Side | Next best unchanged | Next best lower | Next best higher |
|---|---:|---:|---:|
| Bid size 1 | 1,865 | 222 | 0 |
| Ask size 1 | 1,451 | 3 | 239 |

These are adjacent-book observations, often repeated within the same episode, not probabilities or independent opportunities. They preserve the obvious counterexample to treating every thin touch as imminent depletion. A level can remain, recover, change identity, or disappear; a snapshot alone does not settle those alternatives.

Likewise, groups **229201–229228** keep closing quotes **3.152/3.153**, with all trades **10856–10858** retained. The ask ends at its original size, but its full signed size path includes **−1 then +1**, with the intervening unchanged readings also saved. The bid's endpoint change is **−1** despite several increases and decreases. An endpoint-only comparison would miss those paths.

## What extends across the whole day

The existing selected ROOT evidence contributes **13,268 original measurements at 2,053 source ordinals**. It supplies full prior bid/ask sizes for **2,070 trades** across the retained day. In that selected population:

- **986 trades** have prior full-book size skew opposite to the source `depth_n` imbalance sign.
- **638 trades** have prior full-book size skew opposite to their observed prior/close midpoint change.

These are comparisons at original contexts, not tests of a universal book-imbalance trading rule. For trade **1**, the saved prior full bid/ask sizes are **905/572**, while source `depth_n` skew is negative; quotes move **3.061/3.062 → 3.060/3.062**. Late trade **30669** has full sizes **1,797/1,088**, source `depth_n` skew negative, and quotes **3.076/3.077 → 3.075/3.077**. The original clocks and source pointers remain on each trade. Opposing local/full signs also remain recorded as late as trade **30736**, whose close quote is unavailable in this projection; that trade is not removed or given an invented price response.

The independent continuous evidence covers **22,194 books** around the saved 375/391 window, including **1,288 trades** with a prior-to-close window transition. It is not a continuous full-day book export. The other trades remain explicitly linked to all original evidence, with missing observations preserved. The 2,070 selected-prior trades and 1,288 window-transition trades overlap and must not be added as distinct coverage.

Every one of the **10,267,320 saved level rows** was streamed once from the four existing byte parts of one gzip stream. Full-side size, level count, touch price and first-ten totals were checked at each book. Within this window, the producer's `depth_n` equals the sum of ranks 1–10 in all **44,388 side/book checks**. That does not certify every `depth_n` producer or runtime elsewhere. All **443,880 original first-ten rows** are separately saved, with original fields and full-source CSV row coordinates. The full far-book source remains unchanged in Git; no loose archive/database was restored or rehashed.

## How Frankie knowledge is being used

[The source-bound knowledge ledger](frankie-local-liquidity-use.json) retains the entire original `direction.book_contrarian` play, including its **PROVISIONAL** status, flat/ambiguous-flow trigger, weak tie-breaker scope, absent forward evidence and **UNCLEAR** audit. The present comparisons do not test that original trigger, leg population or forward claim. They keep resting-liquidity skew distinct from fresh aggression and avoid promoting an observed skew into a directional verdict.

The ledger also retains original classroom claims **0, 2 and 8**, whose step relationships can differ from their endpoint relationships. Those are saved hypotheses about their original far-book quantities, not established touch mechanisms. Here their methodological distinction is applied explicitly: every fixed-price size step is retained beside the endpoint, and far-book age/identity co-movement is not substituted for actual touch-order survival. All 510 original claims remain eligible, with no claim of complete semantic consumption. Later knowledge informs this retrospective study without being backdated into historical forecasts.

The completed run's actual deep-book use and horizon-dependent history results motivate these comparisons. They do not attribute a neural forecast to a particular queue or establish causation from training gain. The prior broader results remain attached: rolling flow can persist with no fresh trades, fresh flow can oppose its rolling sign, and multiple curve fields can share a source row. Those observations help separate background state, current pressure and actual local quote response.

The action-level anchors remain the checked trades **127**, **139–144** and **146–149**: thin-level depletion, fills of a standing offer, explicit bid depletion and the contrary later recovery. Their original T/F/C/M records take precedence over a snapshot cancellation story. No new snapshot classification overrides those records. Trade **119** and trade **134**'s ten unallocated T units remain unresolved; the absorption counter definition is not a missing-fill repair.

## Saved evidence and checks

- `all-22194-window-local-liquidity-books.jsonl.gz`: unchanged original quote books, exact clocks, both touch rows, first-ten refs, full source-row ranges, depth skews and all original tape members.
- `all-original-first-ten-level-rows.jsonl.gz`: all 443,880 original near-level rows, preserving raw price, size, order count, front size, ages, concentration and integer-clock text.
- `all-22193-consecutive-local-liquidity-transitions.jsonl.gz`: every fixed-price before/after size observation, quote step, prior second-level comparison, original tape members and available same-emission lifecycle refs. Causes remain unallocated.
- `all-22193-first-ten-membership-effects.jsonl.gz`: exact shared-price and entering/leaving-window decomposition, in the same line order as the transition file. Each trade's `window_transition_line` locates both records.
- `all-window-constant-quote-liquidity-paths.jsonl.gz`: all 1,374 paths, including singletons, every size step, endpoint differences and original trade members.
- `all-selected-day-depth-views.jsonl.gz` and `every-trade-local-liquidity-links.jsonl.gz`: original selected measurements and every one of the 30,739 unchanged trades, preserving unmatched contexts and linking the full prior flow/quote/external/model/knowledge evidence.
- [Analysis receipt](analysis-receipt.json) and [verification](verification.json): exact scope/counts, original-field checks, independent saved-checkpoint comparisons and unresolved gates.

Helpers are `tasks/family-research-20261022/analyze_local_liquidity.py`, `test_local_liquidity.py` and `verify_local_liquidity.py`. The `--paths-only` mode operates on the new saved projections; it does not stream the full original ladder again. Original archives, sources, storage and attempts remain intact.

**Semantic coverage stays NOT_PASSED. MLP reproducibility stays UNRESOLVED:** original 120-second fold-4 max difference **0.4313412606716156**, log losses **1.5684192762348583 / 2.915890359438005**. Whole-day causal completion, unseen intragroup order histories and validated exhaustion remain unfinished. No AWS call/start, refit, raw journal scan, new resource or C: artifact was used. All work is in the E: Git checkout.
