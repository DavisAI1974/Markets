# Trade lifecycle evidence and first combined interpretation

All **30,739 recorded market trades** remain the primary population. No trade is dropped, no trade prices are averaged, no model predictions are voted or blended, and no nested source payload is replaced by a scalar summary. Families and dipoles supply supporting context. This checkpoint adds inspectable evidence and bounded interpretation; it does not claim a finished explanation of every trade.

## What the dipole overlay actually adds

Dipole retains directional flow, its persistence/opposition, full-book depth/order/level counts at stored stages, price coupling and orientation relative to the preceding candidate. These describe a flow episode around the trades. They do not independently establish a price turn, prebirth prediction, exhaustion, an execution, or survival of a particular order. Rolling flow and dipole readings share inputs; their agreement is not independent confirmation. SAME/FLIP orientation relative to another candidate is also distinct from the terminal REVERSAL phase and from a price reversal.

The first combined example is the original trade sequence **118–149** (zero-based source ordinals), including trades **122–143** overlapping `dip-19648-1697581775`. It is an exploratory example from this conversation, not a signal selected and validated out of sample. All original prints, the full nested dipole, compact second-set views, source references and surrounding lifecycle records are in [trade-dipole-overlay-example.json](trade-dipole-overlay-example.json).

| Added evidence | Observable finding | Gap it fills; remaining limit |
|---|---|---|
| Individual tape prints | The overlapping prints run from 3.061 to 3.067, reaching 3.068 in between. | The flow path accompanied a rise with a one-tick giveback; the phase label alone does not describe that price path. |
| Producer's rolling-flow definition and tape clocks | The three terminal stages at `1697582164000000000`, `1697582165000000000`, `1697582166000000000` each store signed flow −1. **No new trade was recorded during those three seconds.** The signed lots are a rolling 20-second window. | Repeated opposing windows are not three fresh selling bursts. They cannot establish acceleration of selling or three independent confirmations. |
| Stored stage price and full depth | Those same three stages all store price `3067000000`; bid depth is 1050, 1051, 1049 and ask depth 710 at each stage. | Flow opposition occurred without a stored price fall during those readings. Net depth changes do not identify execution, cancellation or absorption. Stored stage books may be carried from the latest source update. |
| Exact subsequent prints | Trade 143 is 3.067, size 1, event `1697582150669372401`, receive `1697582150669638037`, known-by `1697582150669677102`, input/close `5657/5660`. Trade 144 is 3.068, size 1, event `1697582182540204471`, receive `1697582182540971619`, known-by `1697582182540994234`, input/close `5711/5713`. | The next print is higher after the flow reversal. That contradicts an immediate bearish price-turn interpretation; it does not establish bullish continuation or exclude spread effects. Exact ROOT quotes at these two emissions are not in this local selected-context export. |
| Explicit replenishment action | At known-by `1697582171050270017`, cursor `5695`, original `A` adds one unit at bid `3066000000`, order ID `788699917772`, classified `NEW_ID_ADD`. | A displayed addition is directly supported. It is not inferred from snapshot differences, and does not establish iceberg refresh or the cause of the next higher print. |
| Replenishment outcome definitions | A nearby `RESTORED` episode reports arrival ratio 43 for one removed unit. The source explicitly credits arrivals to every pending episode in the price neighborhood. | This is arrival density relative to removed quantity, not proof that the original order returned or independent confirmations from shared attributions. |
| Full subsequent tail | Trades 144/145 print 3.068; trades 146/147 later print 3.066/3.065. The 60-second last-print endpoint is 43.459005766 seconds old. | Neither the first higher tail print nor a stale endpoint can settle the full lifecycle. The later pullback stays in the record. |
| Second-set values and states | All 19 compact numbers, source float64 hex, float32 values and state codes are attached for each trade at four original source views. | They provide far-book identity/priority/replenishment and step context where PRESENT. Far-book survival does not prove touch-order survival. MISSING placeholders are not measured zero. Definitions still govern interpretation. |

The path's candidate event second is `1697581775`, available second `1697581825` (50 seconds later). Its completed source row is known by `1697582167857645502`, cursor `5689`. Stage-zero book timing remains an open audit flag. These clocks describe sequencing and original measurement meaning; **all later evidence remains allowed** in current retrospective explanation.

## Other newly checked trade mechanics

Trades 32 and 33 share one native emission, cursor 1141: two units at 3.058 and one at 3.059. The original queue records show three filled ask orders (IDs `788699907318`, `788699907316`, `788699906908`). Their `C` cleanup messages must not be counted as three new maker cancellations. In another direct example at cursor 374919, one removed unit belongs to a FILLED order and six to a CANCELLED order. Treating all seven as makers pulling would change the explanation incorrectly. Original records are retained in [new-trade-order-evidence.json](new-trade-order-evidence.json).

Across the preserved removal records, 5,680 link to FILLED terminal orders, 2,213 to CANCELLED terminal orders, and 17 lack that exact same-emission terminal-order match. These are coverage/mechanics checks, not a pooled trade signal. All 7,910 original removals remain individually inspectable.

The saved absorption calculator also needs its source units: its reference adapter sums FILL and TRADE action quantities; `depth_at_open` is traded-plus-withdrawn action quantity, and `surviving_depth` is added action quantity. These are not automatically unique tape volume, full standing depth, or proven FIFO survival. MIXED-side response sign is not an unqualified market direction. [per-event-unit-reconciliation.jsonl.gz](per-event-unit-reconciliation.jsonl.gz) retains each original event and its individual prints. Reference code is saved under `producer-source/`; byte identity to every runtime producer remains a separate provenance limitation.

## Day-wide evidence retained

| Artifact | Scope |
|---|---|
| `every-trade-evidence-bundle.jsonl.gz` | All 30,739 original trades, unchanged original fields, exact integer clocks/cursors, chronological neighbors and nested-source references. |
| `original-native-trade-groups.jsonl.gz` | 29,797 native emission groups, each preserving its individual original prints. |
| `source-*.jsonl.gz` | All 388,640 nested records from the exact saved lifecycle SQLite member, including 308,611 lineage records. |
| `supporting-path-phase-annotations.jsonl.gz` | Separate reconstructed annotations for 862 stored dipole paths and 54,042 stages. Full originals remain in `source-episode.jsonl.gz`; 16,040 trades with no overlap are retained. |
| `original-root-native-measurement-rows.jsonl.gz` | 1,872,499 unchanged long-form measurement rows at trade emission/prior group ordinals in the existing selected-context export; references for every trade are in `every-trade-root-record-links.jsonl.gz`. |
| `second-set-source/` | Full original bytes of four compact source members (771,787 rows), preserved in gzip chunks below GitHub's per-file size limit. |
| `every-trade-original-second-set.jsonl.gz` | All trades matched exactly to input and emission clocks; full named 19-number compact views with states at trade input, previous input, prior completed group and emission close. |
| `all-99-source-role-coverage.csv`, `all-13-input-bindings.json`, `all-510-frankie-knowledge-claims.json` | Exact run roles/bindings and saved claims remain in scope. An inventory or claim is not proof its semantics have all been consumed or established. |
| `every-trade-observed-lifecycle-windows.csv.gz` | Supplementary per-trade navigation at 1/5/20/60/120/300/600 seconds, including endpoint ages and edge censoring. Never a replacement for the individual path or a strategy return. |

Original model forecasts stay at their original contexts in `../final-model-analysis-20261023/source/`. No prediction has been invented for an unmatched trade. Complementary model disagreements remain available without ranking, voting or averaging.

## What was missing, and what remains

The six-hour run already ingested and aligned substantial evidence by instrument, timestamp and cursor. This continuation is filling **local evidence availability and interpretation gaps**, not discovering that timestamps were absent or declaring that the completed run failed. Its 2,097 fits addressed family occurrence and signed/absolute quote changes at selected contexts. They were not finished trade-by-trade lifecycle explanations.

The targeted local phase took 55.831 seconds. A subsequent AWS-plugin presigned, fixed-range read retrieved only 44,748,800 compressed bytes of one named archive in 27.129 seconds, verifying the four newly transported member identities against the original receipt. No whole archive/database rehash, EC2 start, fit or new resource was needed. Timing describes these phases, not all review work. [source-provenance.json](source-provenance.json) and the separate receipts retain the distinction.

Still open:

- **Continuous evidence at every trade:** this local selected projection has exact-emission ROOT measurements for 1,543 trades and prior-group measurements for 2,070. Original continuous full-depth/FIFO/ROOT pins exist in the run list, but they are not all materialized here. Missing links retain the trade and mean neither zero nor no activity. A specific needed order/quote gap should lead to a bounded source read, not a broad rerun.
- **Full second-set richness:** the recovered 19-number compact subset is not the entire rich second-set payload. All raw trade-input rows lack PRESENT compact components; 28,402 emission-close views have at least one PRESENT component. Exact clocks match. Preserve states without inventing a reason absent from this compact source.
- **Exhaustion:** use the existing exhaustion work and its source definitions. Append its later results by instrument, exact clocks/cursors and order/path identity. Do not duplicate that workflow or hold all other trade analysis until it finishes. Distinguish weakened new aggressor flow, loss of price response, opposing flow, a real price flip, and an observation boundary.
- **Source geometry and units:** 12,528 ladder records say FULL_BOOK_TRANSITION and two say GROUP_LOCAL_DELTA, but older rounded ladder price geometry must not substitute for correctly scaled ROOT quotes. Scope alone does not certify units. New quantity/order reconciliations are explicit above.
- **Scientific gates:** semantic coverage remains **NOT_PASSED**. The unresolved MLP occurrence repeatability evidence remains: the 120-second fold-4 repeat differs by max 0.4313412606716156; log losses 1.5684192762348583 versus 2.915890359438005. Invalid negative magnitude predictions, poor interval calibration and one-day validation also remain. No new fit or selected success example resolves those limits.

The next combined analyses should keep trades as the entry point and ask which additional original layer distinguishes each plausible mechanism, including contrary, flat, stale and unresolved outcomes. Dipole is one supporting description, not the population selector or the answer.

## Reproduction of this checkpoint

The ordered helper scripts are in `tasks/family-research-20261022/`: `targeted_trade_lifecycle_pass.py`, `read_bounded_second_set.py`, `finalize_trade_evidence.py`, `attach_trade_root_and_order_evidence.py`, `audit_trade_dipole_overlay.py`. The bounded-read helper accepts a temporary URL through stdin and never saves it; **no network repeat is required to use this checkpoint**, because original compact chunks are already saved. The finalizer removes only redundant scalar intermediates made by this pass and keeps nested originals. `checkpoint-verification.json` records the final preservation checks.
