# Completed-run findings connected to the whole-day trade evidence

The screenshots identify the completed expanded family-model run in `DavisAI1974/Markets`, branch `claude/kalshi-s79-kickoff-ij8t9o`, at checkpoint **682b69b3**. Its **2,097 fits**, learned conditional relationships, individual forecasts and contrary results are now explicitly indexed alongside the original deep-market inventory and Frankie knowledge. The newly pushed inventory at **5470b27b** has been incorporated. The controlling [original master list](../../completed-run-source-list.json) is unchanged; these are links among its evidence, not another source selection.

The screenshots do **not** establish a separate Janus + HippoRAG execution. The master records a disabled shadow disposition in one older reader; that is not proof about every later component. Attribution to a separate combined run remains unverified. Historical text in the pictured chat and old handoff supplies provenance, not instructions to restart boxes, recreate setup or write on C:.

## What prior knowledge has actually been used

The previous trade work retained all **510 Frankie claims**, used source definitions to distinguish tape quantities from action counters and fill cleanup from fresh cancellation, and pointed to the original forecasts. Earlier case work also inspected separate forecasts for 375/391. It had **not** established a systematic connection between every completed-run finding, every knowledge claim and every trade. File retention alone must not be described as scientific consumption.

[The evidence index](run-evidence-index.json) makes that distinction explicit. It links the [deep-market inventory](../../deep-market-data-inventory-20261023.md), [completed-run findings](../../final-model-analysis-20261023/full-model-perspectives.md), their [verification](../../final-model-analysis-20261023/verification-receipt.json), [original individual records](../../instance-market-review-20261023/individual-instance-records.jsonl.gz), and [working semantic review](../../knowledge-semantic-review-working-notes.md). All later knowledge remains available for retrospective explanation, with its actual provenance. Nothing is backdated into a historical forecast.

## SQLite findings across the saved day

The exact saved **464,343,040-byte** `episode-path-audit-v1/lifecycle_asof.sqlite` member was loaded directly from its Git-preserved compressed parts into memory with `query_only=ON`. No database or archive was restored to disk. The query retained access to all **388,640 original records**, including **308,611 lineage records**. No raw journal scan, AWS operation, fit or resource start occurred.

| Whole-source question | Result | Implication |
|---|---|---|
| Are the remaining quantity differences necessarily isolated missing-fill problems? | Of 6,265 original absorption records, 832 share an emission with original tape prints. **819 of those 832** have source `traded_quantity` different from the sum of the individual tape sizes. | The existing adapter's F-plus-T measurement definition is a broad issue. Do not interpret its action counter as unique tape volume. Neither equality nor difference proves missing executions. |
| Can all later saved lineage records repair the identity gaps? | Among 7,939 distinct instrument/order identities from all saved removals plus the 32 bounded T IDs, only **four** match a lineage node or parent. These four are censored roots emitted at cursor 490. | This saved lineage projection provides very little overlap with those identities. It cannot be treated as a complete full-day order genealogy. All unmatched identities remain indexed. |
| Does that search settle trades 119 and 134? | Neither original T ID has a matching node or parent in the saved lineage source. | Trade 119's one-unit liquidity origin and trade 134's ten unallocated T units remain unresolved. Absorption counters and the lineage search do not supply the missing fills. |
| Can original forecasts simply be assigned to every trade? | **59 trades** share a completed group with an original model pre-context. All 749 original family contexts and their **109,674 nested main/quantile forecast rows** are linked. | A shared group is not a per-trade prediction or feature attribution. The other trades remain in the population with access to the entire earlier/later context timeline. |

These counts describe coverage and measurement relationships, not averaged economic evidence. Every underlying absorption record, matching print, absent match and original forecast remains individually addressable. The 832-group result is a SQLite check of the existing per-event unit reconciliation; it is not a newly discovered missing-data population.

## Broader explanations to pursue with the completed-run findings

The results direct attention to several connected mechanisms rather than spending a separate investigation on every counter discrepancy:

1. **Separate tape motion, quote motion and the actions that changed a queue.** The existing day-wide quote comparison has 149 print changes with unchanged quotes and 13 print/midpoint changes in opposite directions. The bounded episode shows standing-offer fills and explicit bid depletion. Those are different observations; an absorption label or a higher print cannot settle them. Reconcile T, F and C roles before interpreting quantity counters.
2. **Follow local liquidity and its history at fixed side and absolute price.** The completed trees used beyond-level-10 fields in 125 of 126 fits, reaching rank 265, but fitted use does not establish independent importance or the cause of a trade. Saved history-removal results vary by horizon and retain flat and contrary effects. Use those findings to inspect queue age, concentration, depletion and explicit additions together; full-book totals and rank changes cannot substitute for order survival.
3. **Keep flow and price response separate through the entire path.** Buying can consume a standing offer without advancing it; later selling can clear a thin bid. The dipole's repeated rolling readings can contain no new trade and can arrive after the quote retreat. These source definitions provide broader alternatives to treating every print leg as momentum or every terminal dipole label as an early exhaustion call.
4. **Use external and model disagreements as competing context.** The saved weather/curve histories, all original forecast horizons and unfavorable outcomes stay separate. Slow external data can proxy time within this one day. The original 43 support-qualified interaction contrasts have no exact pair/outcome/horizon replicated across folds. They guide questions, not causal explanations or model votes.

These are research directions constrained by existing checked findings. This pass does not certify those mechanisms for the remaining trades, claim all Frankie plays apply, or replace the original evidence with a narrative. Existing exhaustion work can be joined later.

## Saved navigation and verification

| Artifact | Preserved scope |
|---|---|
| `every-trade-completed-run-and-lineage-links.jsonl.gz` | All **30,739 unchanged original trade records**, exact integer clocks/cursors, complete earlier/later original model-context ranges, nearest-context navigation, same-group removal refs and order-lineage refs. Neighbors are navigation, not causal matches. |
| `all-749-original-model-context-links.jsonl.gz` | Every original case's exact decision/start/pre-group clocks and cursors, original nested-case/card pointers, original forecast disposition and row count. All model values remain in the unchanged original cases and forecast CSVs. |
| `all-observed-removal-and-bounded-T-order-lineage-links.jsonl.gz` | Every one of the 7,939 queried identities, including empty results; every matched source record hash, node/parent role, actual emission clock, cursor, source side/status and entered/exited clocks. Graph associations are not execution allocation. |
| `all-6265-absorption-to-original-tape-links.jsonl.gz` | Every original absorption record hash with all individual matching tape ordinals and its original metric/disposition. No tape match is explicit, not a zero-execution conclusion. |
| `sqlite-query-receipt.json` | Exact database scope, counts, no AWS/refit/raw-read operations, unresolved attribution and scientific gates. |
| `verification.json` | Unchanged all-trade fields/clocks, original context and lineage identities, source pointer and document checks. |

The original nested sources remain unchanged. These supplementary navigation indexes do not flatten or replace them. A group can contain several trades and several removals: sharing a group does not allocate every removal to each trade. The available T-ID check is bounded to trades 118–149; a missing T-ID pointer elsewhere is a projection limitation.

Reproducible helpers: `tasks/family-research-20261022/query_saved_run_connections.py`, `test_saved_run_connections.py` and `verify_saved_run_connections.py`. Their outputs are already saved; no setup repeat is required.

**Semantic coverage remains NOT_PASSED. MLP reproducibility remains UNRESOLVED:** 120-second fold 4 max difference 0.4313412606716156; log losses 1.5684192762348583 and 2.915890359438005. Original negative magnitude predictions, poor interval coverage, sparse interactions and contrary evidence remain available. All four AWS boxes remain stopped; this pass made no AWS call.
