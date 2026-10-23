# Family research handoff for individual instance analysis

Prepared October 22, 2026 Eastern. **First work in the new chat: compare instances 375 and 391 in detail.** Most subsequent work should remain analysis of this completed run, one instance/market episode at a time.

## Latest user direction: use the run list and start with every trade

The user withdrew an accidental strategy-position answer. The primary population is the timestamped trade record, all 30,739 recorded trades in `price-curve-timestamps.csv`, not the 749 family records. Start with trades and build supporting evidence around them. Use the exact completed-run source list in `completed-run-source-list.json`, including original 99-plane entries, the 13 historical point bindings, confirmed second-set numbers, Bedrock/native/lifecycle tables, ROOT/full depth/FIFO/MBO, families/dipoles, external inputs and Frankie knowledge. Do not replace that run list with a narrower invented checklist.

The user explicitly directed unrestricted retrospective interpretation: include everything available, even information learned later that day or on later days. Do not hide or discard contrary/unfavorable evidence. Keep exact clocks to describe sequence and lifecycle; do not exclude later knowledge from current reasoning. Earlier strict-as-of restrictions remain descriptions of original forecasts and supplementary timing diagnostics, not a prohibition on considering later knowledge. Distinguish retrospective explanation from any historical-forecast claim when making one. Explore prebirth, direction, momentum, duration, flips, exhaustion, end/tail and other behavior supported by the record.

The 375/391 quote/queue projections in `trading-episode-375-391/` are supporting work, not the full trade-first or whole-day review. Complete run-source interpretation for every trade remains pending. Keep semantic coverage NOT_PASSED and unresolved MLP reproducibility explicit. All operating restrictions and saved/stopped state remain in force.

## October 22 continuation correction: analyze trading episodes first

The user clarified that recorded trades and market behavior before, during and after a move are the primary analysis unit. Family events are explanatory annotations, alongside queues, aggressor flow, external context and frozen model perspectives. Instances 375 and 391 locate two related portions of a connected episode; their family appearances must not define the causal beginning, an entry, an execution, or independent confirmations. Distinguish market executions, quote changes and any actually recorded strategy fills. Price endpoints alone are not trades.

C: cleanup was performed first. This same linked Markets checkout was relocated to `E:/Markets-family-research-handoff`; its prior C: source and the adjacent October 22 family research files now contain no remaining files on C:. All recovered documents are committed or have byte-identical existing Git copies. Existing bulk transport archives are preserved off C: inside the checkout and remain outside Git; see `artifacts/recovered-c-drive/20261022/relocation-receipt.json`. No AWS action was performed. E:/Markets has pre-existing changes in two granite files; they were left untouched.

## The user objective

Latest user request: “dig into 375 and 391 and show what was different in the queues, replenishment and price action before the moves. could we have seen the difference in real time? create handoff and print drop in for new chat. have those 2 instances be the first thing we do but we will be spending most our time doing analysis of this run.”

The user has explicitly corrected the framing:

- Averages are informative context and checks. They are not a trade signal.
- Inspect individual instances, contemporaneous market conditions, and the sequence of changes before and after a possible decision.
- The different models supply complementary perspectives. Do not turn the work into an architecture leaderboard, a winner/loser exercise, or an unvalidated average/vote of their outputs.
- The earlier fitted baselines omitted substantial market depth. Do not use those older partial-depth runs to judge the completed expanded candidate. The ridge fit inside the completed candidate was also refitted on its expanded input.
- Distinguish a first-observed structural family event from an individual execution, a filled strategy trade, or the causal beginning of a move.

The broader project keeps families, the confirmed second set, all 13 historical external concepts, 99 source roles/dispositions, FIFO/dipole/lifecycle evidence and timestamped prices linked. These are not automatically 99 live numerical inputs or completely certified semantics. Use available external and knowledge context where its actual publication/known-by time permits it; retain later knowledge only as a hypothesis source. The full source/semantic background is in `family-full-context-analysis-handoff.txt` and the canonical producer definitions, but its old running/incomplete execution statements are historical and superseded by the completed-run receipts.

**This handoff deliberately leaves the deeper 375/391 comparison as the first analysis in the new chat.** The preliminary observations and readable individual records are saved; queue replenishment mechanisms, continuous order identity and an actionable real-time distinction have not yet been established. Do not present that pending work as complete.

## Workspace and operating constraints

Use only this existing clean checkout:

```text
E:/Markets-family-research-handoff
```

Set every shell command's working directory explicitly to that checkout. **Never dirty E:/Markets.** Local branch `codex/family-research-handoff-20261022`; remote `https://github.com/DavisAI1974/Markets.git`, destination branch `claude/kalshi-s79-kickoff-ij8t9o`. The completed individual-record/replay checkpoint is **817064e7**; this handoff is an additional saved checkpoint. No fresh clone or setup reconstruction is needed.

Windows PowerShell. `C:/Python313/python.exe` has pandas, numpy, matplotlib and Pillow. Use ordinary plotting tools for scientific figures. Preserve exact integer nanosecond clocks and cursor caps; do not let a nullable pandas column coerce them through float. There are no subagents/new chats/cross-chat messages/automations/live orders authorized by this handoff. The user will paste the drop-in into a new chat.

All four research instances are complete, durably saved and **stopped**. Do not restart them, rerun fits/finalizers, terminate instances, delete storage, provision resources, broaden IAM, or alter the old Search workflow. Keep all EBS, all attempts, C/D swap and snapshot `snap-0d3e867c1240b6528`. No repeated hashing of frozen inputs or databases. No broad raw scans/input restores as a setup step. Analysis should begin with the already saved local projections below.

If a specific missing source later requires a bounded S3 read, use the AWS plugin `run_script` / `get_presigned_url`; **never AWS CLI**. Prefer exact archived members/offsets and existing manifests. Do not print temporary presigned URLs. No AWS call or EC2 start was needed for the saved instance review. Reauthorization of new spending/compute work is not implied by this analysis handoff.

## Read these saved artifacts first

All paths below are relative to `artifacts/sqlite-triage/20261022/families/` unless stated otherwise.

1. `instance-market-review-20261023/instance-375-review.md` — preliminary exact episode replay, model forecasts and the preliminary 391 comparison.
2. `instance-market-review-20261023/instance-review-receipt.json` and `verification-receipt.json` — exact clock, label and ladder checks.
3. `instance-market-review-20261023/cases/0375.md` and `cases/0391.md` — their separate pre-event context and every main/quantile horizon forecast.
4. `family-save-stop-COMPLETE-20261023.txt` and `tasks/family-research-20261022/verified-save-stop-completion-20261023.json` (the latter path is repository-relative) — authoritative saved/stopped state and full archive/volume receipts. Older handoffs contain obsolete running/incomplete status. Do not resume those old operational procedures.
5. `final-model-analysis-20261023/full-model-perspectives.md` — aggregate context, supporting tables and known limitations. Its averages support instance analysis rather than substitute for it.

## Exact case identities and decision boundaries

Both are instrument **150611**, chronological quarter/test fold **3**. Times below are UTC for the historical market data, not the current session date.

| Field | Instance 375 | Instance 391 |
|---|---|---|
| Family | `ow-a76c2c9727ecf53400a6` | `ow-01b606e004de7b1d9a51` |
| Sample | `375:before_start` | `391:before_start` |
| First observed receive time UTC | 2023-10-18 13:09:12.081390598 | 2023-10-18 13:14:00.878613141 |
| First observed receive ns | `1697634552081390598` | `1697634840878613141` |
| First observed exchange event ns | `1697634552076735159` | `1697634840876731125` |
| Strict pre-event cutoff receive ns | `1697634552081390597` | `1697634840878613140` |
| Strict pre-event input cursor cap | `303655` | `319232` |
| Family group source ordinal / cursor | `233426` / `303656` | `244934` / `319233` |
| Last eligible pre-group ordinal / cursor | `233425` / `303645` | `244933` / `319188` |
| Pre-group known-by receive ns | `1697634552081085486` | `1697634840853117209` |
| Pre-group age at cutoff | 0.305111 ms | 25.495931 ms |
| Pre-event bid / ask / mid | 3.152 / 3.154 / 3.1530 | 3.139 / 3.140 / 3.1395 |
| Pre-event full bid / ask size | 2,081 / 1,223 | 1,993 / 1,348 |
| Pre-event 60 s buy / sell aggressor quantity | 126 / 58 | 116 / 88 |
| Pre-event 5 s buy / sell quantity | 13 / 31 | 16 / 27 |
| Pre-event 1 s buy / sell quantity | 0 / 24 | 6 / 26 |

At 375, first-ten-level sizes were 155 bid / 160 ask despite the larger full bid book. The pre-event ask at 3.154 had size 25 across 14 orders and front-order age about 0.003852 s; bid at 3.152 had size 7 across 5 orders. These are snapshot queue summaries, not a checked reconstruction of individual order survival or executed volume at each price.

## What is already checked about the price sequences

375: the final burst's first lower-midpoint update was about **60.133 ms before** its family appeared. The midpoint was already down from 3.1555 to the strict pre-event 3.1530. The family is therefore not evidence that the move started at time zero. The pre-event book is only 0.305111 ms old, but that does not establish the candidate could have been detected before the earlier price change.

| Horizon from each case's own first appearance | 375 signed midquote change from its strict pre-event mid | 391 signed change |
|---|---:|---:|
| 1 s | −0.0055 | −0.0015 |
| 5 s | −0.0075 | −0.0005 |
| 20 s | −0.0035 | −0.0010 |
| 60 s | −0.0075 | −0.0010 |
| 120 s | −0.0045 | +0.0060 |
| 300 s | −0.0125 | +0.0070 |
| 600 s | −0.0035 | −0.0085 |

All seven 375 horizons through 600 s match the saved observed book endpoints within 1e-12. All six 391 horizons through 300 s also match the same saved quote window within 1e-12. Longer endpoints are retained in the model output but are outside the continuous window for that case. They must not be turned into a fabricated intrahorizon path.

391 is approximately **288.797223 seconds after 375**, inside the same wider price episode. There are **32 different first-family events** in the saved −120/+600-second window around 375. They are not independent trades or 32 independent confirmations. Similar recent selling in 391 accompanied less immediate downward displacement, then a two-to-five-minute rebound, then a later decline. The reason is still open; do not label it absorption/exhaustion until the queue and execution evidence supports that interpretation.

The case-finding description formed while inspecting 375 was: 60 s buy quantity > sell, 5 s sell > buy, 1 s sell > buy, full bid size > full ask. It finds **50 contexts**, including 375; 391 is the next chronological match after it. This was post-hoc case-finding, not preregistered signal validation, a success rate, or an entry rule. No future price outcome was used to filter those matches. Keep counterexamples and inconclusive cases.

## First analysis in the new chat

Begin with **375 versus 391**, before expanding to other instances:

1. Recenter the same saved quote sequence on each event. Separate pre-move, pre-family, family group, immediate reaction and later rebound/continuation. Retain actual observation ages and gaps. Pick a shared pre-event window (for example −120 s) and examine the final seconds/milliseconds where the source supports it. Do not use post-event evidence in a supposed pre-event decision.
2. Extract matched absolute-price ladders for 391 and any additional necessary 375 checkpoints from the already local split compressed level export. Existing 375 checkpoint ladders do **not** yet include a dedicated set centered on 391. A bounded sequential pass of the saved projection to select required ordinals is acceptable; no raw/database rehash or cloud setup is needed.
3. Compare touch and nearby depth, distance from touch, spread, order counts, front size, queue-age distributions, concentration, and how those change around price steps. Match **side plus absolute price**; changing rank is not a surviving queue/order identity. The full bid total cannot substitute for local liquidity.
4. Investigate replenishment explicitly. At a fixed price, document depletion and reappearance/refresh of displayed size, queue age/priority resets, and available recorded executions/adds/cancels. Snapshot differences alone cannot separate cancellation from execution or establish FIFO survival. Retrieve only the exact additional saved source needed if existing projection fields cannot answer this. Report that limitation rather than manufacture an order history.
5. Compare aggressor pressure with price response and queue recovery. Ask whether selling continues to produce lower quotes or meets a recovering/stable bid, and whether offers step down or cease doing so. These are questions to test, not findings already established. Short rolling windows overlap; source-state counter changes across anchors are not automatically interval flow.
6. Build an **availability timeline** for each potential distinguishing observation: exact known-by/cursor, first observed qualifying state, price already traversed at that instant, remaining lead time, and whether the evidence was truly pre-move or only confirmation afterward. Distinguish source-observable from consumed by the fitted model and from operationally executable. We have not simulated processing latency, queue fills, fees or slippage.
7. Attach the original frozen forecasts for each instance, horizon, target and model. Use disagreements to frame specific questions. Do not infer which feature drove a neural prediction from a broad gain table; inspect saved tree paths/states only if needed and actually available. No new fit, test-based model selection or automatic voting/averaging is authorized here.
8. Produce a visual side-by-side case study plus an evidence ledger: observable fact, exact time/source, competing interpretation, counterevidence, and what would falsify the candidate. State what could have been seen in real time, what is only hindsight, and what remains unresolved. Preserve any unfavorable/flat result.

After these two cases, continue analysis of this run primarily at the individual instance/episode level. Use the 749 readable records, chronological neighbors and the 50-case inventory to choose further comparisons transparently. Averages remain useful for context, calibration and checking whether individual patterns repeat; they are not trade triggers. Do not narrow the whole research project permanently to this one 50-case screen.

## Local source map and extraction notes

### Consecutive observed books and ladders

`timestamped-mbo-window-v1/consecutive_quote_books.csv.gz` — **22,194 rows**, actual completed-group books. Columns include family/instrument, source ordinal, input cursor, exchange event/receive/known-by ns, relative receive ns, best bid/ask/mid/spread, `bid_depth_n`/`ask_depth_n`, full depth totals, number of levels, original source offsets/lengths/hashes.

The window is centered on 375, but each row's `family_id` is the **export's anchor label**, not the structural family emitted at that row. To identify actual per-group families, join source ordinals against `descriptive-v1/retained_group_sequence.csv.gz`. When recentering on 391, calculate relative time from integer `known_by_ns - 1697634840878613141`; do not reuse the original 375-relative column unchanged.

Actual first/last known-by times are `1697634432293731473` and `1697635152020583540`. Relative to 391, coverage is approximately **−408.584882 to +311.141970 s**. It covers a shared −120/+300-second comparison for both cases. It does **not** cover 391 through +600 s or the raw predecessor exactly at 375's −120 s boundary. Leave missing boundary states explicit or use an already pinned eligible context; do not interpolate.

`timestamped-mbo-window-v1/consecutive_bid_ask_levels.csv.gz.part001` through `.part004` are **byte parts of one gzip stream**, not four independent gzip files. Total compressed bytes 243,624,107; **10,267,320 rows**. Fields include exact clocks/cursor/ordinal, side/rank, scaled and raw absolute price, size, order count, front-order size/age, median/p90 queue age and largest-order share. They contain level summaries, not full order-ID execution traces. The `Parts` reader in the saved helper streams all four without making an extra full local copy.

`timestamped-mbo-window-v1/window_receipt.json` pins original scope/provenance. **Do not rehash these frozen sources as a setup ritual.** The review helper already checked touches, level-size conservation and matching labels. At all 18 checked ladders `depth_n` equals the sum of ranks 1–10; retain the producer name elsewhere unless independently checked.

### Individual instance records and forecast data

`instance-market-review-20261023/` contains:

- `instance-by-instance.md` and `cases/0001.md` through `cases/0749.md` — readable separate case records with chronological navigation, pre-event context, each model/horizon and later outcomes. These are records, not 749 completed causal reviews.
- `chronological-instance-index.csv` — all 749 cases, exact clocks, current quote/depth, rolling flow and saved-forecast availability. **662** cases have saved held-out forecasts. Do not replace missing forecasts with in-sample or synthetic predictions.
- `individual-instance-records.jsonl.gz` — all 749 exact-integer clock records, raw missing/disposition measurements and main/quantile forecasts.
- `pre-event-clock-receipts.csv`, `pre-event-measurements.csv.gz` — **749 checked eligibility joins**, **101,115 saved measurement rows**. These human-readable projections are bounded, not a claim that all 1.15 million expanded columns are interpreted here.
- `all-pre-event-forecasts.csv.gz` — **426,845** original pre-event forecast/refit rows, including source/history removal refits. The per-instance JSON includes **109,674** main/quantile rows. Preserve labels, folds and model identities.
- `instance-375-all-model-forecasts.csv`, `instance-391-all-model-forecasts.csv` — direct case subsets.
- `instance-375-checkpoints.csv`, `instance-375-checkpoint-ladders.csv.gz` — 18 actual ladders / 8,320 level rows already extracted; no new 391 extraction yet.
- `instance-375-pre-event-flow.csv`, `instance-375-pre-event-measurements.csv`, `instance-375-external-asof.csv` — recorded local/native/second-set measurements, 62 external rows with publication provenance.
- `instance-375-family-occurrences.csv` — its four same-family occurrences across the retained day; separate from `instance-375-neighboring-first-events.csv`.
- `candidate-flow-transition-instances.csv`, `candidate-flow-transition-audit.csv` — all 50 matches and full three-state screening inventory, without future-outcome filtering.
- `instance-375-market-replay.png`, `instance-375-review.md`, `instance-review-receipt.json`, `verification-receipt.json`.

Reproducible helpers (repository-relative):

```text
tasks/family-research-20261022/review_individual_instances.py
tasks/family-research-20261022/render_instance_cards.py
tasks/family-research-20261022/build_model_perspectives.py
```

Read these for schema/joins. **Do not rerun them just to recreate already saved records.** Extend targeted analysis instead. The review helper's selected quote/layer clocks remain integer. Avoid pandas `groupby(...).observed` attribute collision: use `groupby(...)["observed"]`. Avoid `iterrows`/nullable-float conversion for nanosecond identities.

`descriptive-v1/retained_group_sequence.csv.gz`, `group_context_receipts.csv.gz`, `features.csv.gz`, `group_measurements.csv.gz`, `complete_context_measurements.csv.gz`, and `enriched-v2/native_measurements.csv.gz`, `quote_windows.csv.gz` are available locally. Use exact sample IDs, lag cutoffs, source refs and clock semantics. A current measurement and a past-window difference are not interchangeable. Raw component meanings need their producer definition before giving them economic names.

`final-model-analysis-20261023/source/` retains the final raw metric/prediction tables and transport manifest locally. Bulk 235 MB core predictions and 172 MB registry are intentionally Git-ignored, but remain in S3; the smaller case subsets above are committed and are the efficient starting point. Do not redownload the full final archive for a case whose needed data already exists locally.

## Scientific and operational status to preserve

All **2,097 mandatory fits** are complete: 1,908 core and 189 neural; final PCA/clustering and original postprocessors ran once on A. Predicted row counts: 1,181,946 core and 118,203 neural. The data are one October 17–18, 2023 market day, 749 structural families and 3,745 selected phase samples. Three test folds are chronological parts of that same day. Maintain family/horizon purge, 600 s embargo, training-only preprocessing, fixed original seeds/25 neural epochs, strict as-of clocks and no future backfill. Missing/undefined is not zero and does not delete an instance.

**V3 is frozen; semantic coverage stays `NOT_PASSED`.** Complete knowledge/99-plane consumption and unit mappings remain unresolved. Later teacher/brain/terminal episode evidence cannot be backdated into a 2023 decision. Avoid declaring a causal effect, a profitable signal, stable economic regime labels or calibrated uncertainty from these case descriptions.

Residual-MLP occurrence 120 s/fold 4 has unresolved repeatability evidence: max prediction difference **0.4313412606716156**, original logloss **1.5684192762348583** versus repeat **2.915890359438005**. Original completed attempt remains canonical and both attempts remain saved. Some magnitude predictions are invalid negatives; quantile intervals have poor coverage. Preserve these contrary results rather than silently clipping, selecting or suppressing them.

All four scoped us-east-1 instances remain stopped:

```text
A i-035994afa8bdf66a5
B i-087f8d3247ae847a9
C i-031eeb577ad72b064
D i-0d17573dbce871520
```

Verified completion is in `tasks/family-research-20261022/verified-save-stop-completion-20261023.json`. The save-stop heartbeat was deleted after confirmed completion; do not recreate it. Compute is stopped; retained EBS/snapshots/S3 continue charging. Nine attached volumes total 13,920 GiB; the frozen snapshot is encrypted, and result archives use AES256 server-side encryption with all four bucket public-access blocks enabled. One legacy volume is unencrypted and retained unchanged; do not claim every legacy disk is encrypted or alter it.

Canonical bucket `frankie-granite42-568968024170-us-east-1`, epoch `cce6f548f09f50f00caaca396a213e9f2d42d5a7ff85c0644be311eb83e708f4`:

```text
host-deliveries/family-research-20261022/save-stop/<EPOCH>/A-final-1792717045761634343.tar.gz
20696923225 bytes
SHA256 fa195668b0d9ca489639efb60b0c07596c55865dab82d449ba04663a027b6d5d

host-deliveries/family-research-20261022/dual-box/<EPOCH>/B-results.tar.gz
host-deliveries/family-research-20261022/dual-box/<EPOCH>/C-results.tar.gz
host-deliveries/family-research-20261022/dual-box/<EPOCH>/D-results.tar.gz
```

Full archive SHA256/length and durable stop-proof read-back were checked before shutdown. The local aggregate read streamed only the scientific prefix of A's archive; it did not download/reverify the whole 20.7 GB archive. Recovery must preserve the collection manifest's shard-linked layout, attempts and storage. Existing exact receipts supersede assumptions from filenames or old progress notes.

## Expected first deliverable

A 375/391 side-by-side reconstruction with actual price/queue/replenishment evidence and a timestamped answer to **“Could we have distinguished these states before the relevant move, in real time?”** Clearly label observable preconditions, later confirmations, competing explanations, missing action/identity evidence and unresolved cases. Then continue studying individual events and connected episodes from this completed run, using the model perspectives together and aggregates as supporting context.
