# Whole-day observed trade chronology

Every one of the **30,739 original trades** has an individual row in `every-trade-chronological-lifecycle.jsonl.gz`. Every original field is preserved, with exact integer event, receive, group-availability and cursor values. This is the next day-wide descriptive lifecycle layer, with the remaining causal work explicitly unfinished.

The observed tape contains **9,109 maximal equal-price stretches** and **5,120 maximal same-sign print-step legs**. There are 5,119 changes of print-step direction. A stretch is only an index over its individual prints. A leg points into the full individual tape; adjacent legs overlap at the complete turning stretch. No prices, clocks, sizes, forecasts or source payloads are averaged or replaced. Equal-time prints and multi-print emission groups remain distinct.

Each trade retains:

- The complete earlier and later trade ranges, its containing stretch and every overlapping leg, with exact clocks at both observed boundaries. Later evidence remains eligible even when unavailable to an original forecast.
- The original strict prior group and same-emission lifecycle references, all compact second-set views, selected ROOT measurement pointers, all external-series links and the full bounded native/ROOT/rich-second-set links where available.
- Individual same-emission removal references and all recorded terminal-order classifications. These links exist for **1,487 trades**; shared-emission links are shared evidence, not independent confirmations or new unique executions.
- Supporting dipole paths when present. The **16,040 trades without a saved overlapping dipole** remain in the same primary population.
- Explicit unfinished states for causal precursors, quote/order interpretation outside checked contexts, exhaustion and full semantic coverage.

`all-price-stretches.jsonl.gz` records each exact price, the complete inclusive trade-ordinal interval, the incoming/outgoing print steps and the first next differing print. `all-overlapping-print-legs.jsonl.gz` records the complete same-sign path intervals and overlapping endpoints. First-to-last receive durations are observed tape durations, not a claim that a directional force or order continuously persisted between prints. The final boundary is an observation boundary, not a proven market episode death.

The next prints after the checked sequence show why a terminal narrative must remain open: trades **149–151** each print 3.067; trade **152** prints 3.068; **153** prints 3.067; **154** prints 3.068; **155** prints 3.067. Every later trade through ordinal 30,738 remains linked. This alternation cannot by itself establish repeated quote reversals, fresh aggressor flips or renewed exhaustion. Exact quote/order mechanisms for this continuation remain to be established from their original layers. Earlier prints 0–117 also remain unfinished; chronological navigation does not silently skip them.

The checked quote/order role contexts still cover **32 trades, 118–149**. Read [the role reconciliation](../quote-order-gapfill-v1/role-reconciliation-v1/README.md) before extending those mechanisms. It resolves resting ask identities for N-side fills without inventing their unspecified aggressors, retains differing execution/resting prices for same-ID T/F records, and preserves the unallocated quantity in trades 119 and 134.

`scope-and-interpretation-policy.json` points to the exact full run-source list, all 99 roles, the 13 original bindings, the complete external histories, all 510 Frankie knowledge claims and the original forecast contexts. The applied Frankie method preserves separate clocks, open-world membership, first availability and negative/unresolved evidence. These pointers preserve the entire source scope; they do **not** assert that all its semantics or all knowledge claims have been consumed or proven for every trade. No new forecast is assigned to an unmatched trade.

`verification.json` independently checks every original trade field, all 30,739 exact clock sets, every stretch member, all leg directions and shared turning boundaries. The focused unit tests exercise duplicate sequences, flat tape, overlapping turns and the actual 32-trade side/price cases. No frozen input database/archive was rehashed for analysis, no raw source scan or retrieval occurred, and no AWS operation, fit, resource or order was created.

**Semantic coverage remains NOT_PASSED.** This means meaning and mechanisms are still incomplete, despite passed preservation/alignment checks and complete observed-tape navigation. It does not invalidate the individually checked facts. **MLP reproducibility remains unresolved:** original 120-second fold-4 max difference 0.4313412606716156; log losses 1.5684192762348583 versus 2.915890359438005. Invalid negative magnitude predictions, interval calibration and one-day validation limits remain. Existing exhaustion work can be joined later by instrument, exact clocks/cursors and order/path identity.

Reproduce from the saved materialized evidence with `python -B tasks/family-research-20261022/continue_trade_chronology.py`, then `python -B tasks/family-research-20261022/verify_trade_chronology.py`. No setup, archive restoration, network source read or model run is required.
