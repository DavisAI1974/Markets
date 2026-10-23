# Deep market data inventory for the completed family research run

Saved October 23, 2026. This is the consolidated **list of market-data sources, field lists, input construction and retained locations** behind the completed expanded candidate. It inventories existing data; it does not create another raw-data backup or certify unresolved semantics.

- [Exact source files and saved archive locations](deep-market-data-source-files-20261023.csv): **44 entries**, with original/member paths, recorded SHA256 and byte lengths where available, offset indexes, roles, evidence paths and exact S3 URIs.
- [Original external tables and column lists](deep-market-data-external-tables-20261023.csv): **20 tables**, their original aligned row counts, and actual field names.
- [Instance-by-instance records](instance-market-review-20261023/instance-by-instance.md): 749 individual family events, including their pre-event context and saved model forecasts.
- [Analysis handoff](family-instance-analysis-handoff-20261022.md): begin with the queues, replenishment and real-time observability of 375 versus 391.

The receipts and builder were read from repository checkpoint `86854f8664f4fdf736c76a46b5908fd681b929f9`. Source hashes below were copied from existing receipts, not recomputed by scanning raw ledgers. Historical extraction receipts describe their own stage; their old “no model fit yet” statements do not supersede the final completed-run receipts.

## 1 Deep native order book and FIFO data

The original indexed sources include full native member rows, ROOT frames, structures, prices and lifecycle rows. Their five exact file paths, SHA256 values, sizes and offset-index paths are in the source-files CSV and the original [source registry](descriptive-v1/source_registry.csv). These are original host paths on retained storage, not files newly copied into Git or currently running services.

The recovered selected-context book data includes:

- Actual bid/ask prices and raw price encodings; spread and midpoint.
- Every observed native book rank at the selected contexts, reaching **bid rank 281 and ask rank 247**. These are observed maxima, not a fixed depth or evidence that every context has that many levels.
- Per-level displayed size, order count and front-order size.
- Queue/order position and priority-age measurements; front, median and p90 age summaries where defined.
- FIFO size concentration, largest-order share, size-weighted priority age and volume-ahead measurements where defined.
- Full-side sizes/order counts/level counts, depth imbalance, price span and nearer-depth summaries.
- Ingress/within-group timing and receive-gap measurements, with raw absolute clocks and order identifiers retained as provenance.
- Source missingness and state for nonexistent levels, undefined quantities and invalid/unavailable ages.

Exact field lists already saved in Git:

| List | What it contains |
|---|---|
| [Native and confirmed second-set field registry](joint-inputs-v4/native_second_full_feature_registry.csv) | 47,792 numeric identities and 19,119 categorical fields in the extraction; 20,572 recorded categorical levels in its vocabulary. |
| [Native category vocabulary](joint-inputs-v4/native_second_category_vocabulary.json) | The observed labels retained separately from numerical measurements. |
| [ROOT full field registry](joint-inputs-v4/root_full_feature_registry.csv) | 5,034 numeric fields and 5,252 categorical fields in the ROOT extraction. |
| [ROOT category vocabulary](joint-inputs-v4/root_full_category_vocabulary.json) | ROOT categorical labels used by the expanded builder. |
| [Native extraction receipt](joint-inputs-v4/native_second_full_extraction_receipt.json) | Selected payload size/hash, counts and extraction checks. |
| [ROOT extraction receipt](joint-inputs-v4/root_full_extraction_receipt.json) | Snapshot identity/alias, clocks, fill-signature checks and payload size/hash. |

These component extractions cover **6,265 unique source records mapped to 10,486 selected contexts**. They preserve complete selected snapshots, not an invented continuous order history. A changed rank does not establish that the same order or absolute-price queue survived.

The selected native/second-set values are `joint-inputs-v4/native_second_full_context_values.jsonl.gz` (229,953,002 bytes, recorded SHA256 `d058d04fbdb90b93f15c06f2b8649733a9a7bb450b27d0196251a81cde85aafd`). ROOT values are `joint-inputs-v4/root_full_context_values.jsonl.gz` (116,893,886 bytes, SHA256 `a6f0edfd04ec532b9407b549c668d2cf09452c280a13e3b374e409ad4288a3ba`). The source-files CSV gives each containing archive and member path.

## 2 Flow, timing, families and the confirmed second set

The aligned reconstruction retains **749 first-observed structural families**, **583,688 completed groups**, **771,787 confirmed second-set rows** and **30,739 timestamped trades** for the one retained October 17–18, 2023 market day.

The measurements include:

- Buy/sell-aggressor quantities and imbalance in recorded rolling windows.
- Event/action counts and quantities, add/cancel churn, top-level add/cancel quantities and modify/priority-loss measurements where emitted.
- Measured elapsed durations since book reset, same-side group completion, touch change, trade and session-open anchors where available.
- Family/group/trade linkage, exact input cursors, event/receive/known-by clocks and observation ages.
- The original 19 second-set components, their values, states, reasons and source references.
- Recurrence, mirror, ladder, absorption, flow-substrate, replenishment, queue, candidate, episode and response carriers where available in the saved lifecycle evidence.

Useful existing lists and projections:

- [Selected-context full field inventory receipt](full-context-audit/field_inventory_receipt.json) and [field inventory](full-context-audit/complete_field_inventory.csv).
- [Second-set component dispositions](descriptive-v1/all_second_set_component_dispositions.csv).
- [Family master](descriptive-v1/family_master.csv), [selected samples](descriptive-v1/samples.csv), [indexed source context receipts](descriptive-v1/group_context_receipts.csv.gz), and [actual retained group sequence](descriptive-v1/retained_group_sequence.csv.gz).
- [Saved native timing measurements](enriched-v2/native_measurements.csv.gz) and [selected pre-event measurement ledger](instance-market-review-20261023/pre-event-measurements.csv.gz).

“First observed family” is not proven original order birth or an executed strategy trade. Lifecycle terminal/segment-close/complete-episode evidence is retained separately; its earlier event times do not make it available before emission. Full consumption of every supplemental lifecycle field is not certified.

## 3 The 13 historical external concepts

These conceptual points are backed by the 20 original aligned tables listed in the external-tables CSV. Retain underlying series, instruments, stations, forecast models, target dates, vintage/revision and publication provenance separately.

1. NYMEX managed-money net one-year percentile — `cot.023651`.
2. Forecast gas-weighted HDD — `mos.gw_by_cycle`, with model/horizon distinctions.
3. NYMEX managed-money net week-on-week change — `cot.023651`.
4. NYMEX managed-money net three-year percentile — `cot.023651`.
5. US48 wind — `eia930.us48`, with hourly source detail retained.
6. Sessions since prompt expiry — `calendar.sessions_since_prompt_expiry`.
7. Estimated gas burn — `eia930.us48`.
8. ICE LD1 managed-money net one-year percentile — `cot.023391`.
9. Forecast-model disagreement — `mos.disagreement_by_cycle`.
10. Observed gas-weighted HDD/weather — `weather.gw_daily` and `weather.obs_hourly`.
11. Weekly storage — `storage.weekly`.
12. Storage estimate/actual/surprise — `storage.estimate` and `storage.weekly`.
13. Futures curve shape — `curve.settled_shape`, `curve.traded_shape`, with underlying curve trades, statistics and definitions.

The original aligned table counts sum to **329,658 rows**. The [external point provenance](descriptive-v1/external_point_provenance.csv) preserves columns, conceptual-point mapping and timestamp notes. Other retained COT/curve/MOS/hourly tables are not silently discarded because they are not one of the 13 labels.

The later recovery includes **17 manifested external source files**, plus separately retained source variants, including the additional October 17 prior-day source. The normalized catalog records **19 source collections and 7,679,916 source records**; as-of resolution records **5,275,928 observations**; the scoped feature timeline contains **187,766 rows** across **38,677 scopes**. These are different pipeline counts, not interchangeable sample sizes or additional independently aligned MBO days.

Evidence: [source recovery](full-context-audit/external_history_recovery.json), [scoped normalization](external-history-v4/scoped_history_receipt.json), [as-of resolution](external-asof-v4/observation_resolution_receipt.json), [scoped timeline](external-scope-history-v4/scope_history_receipt.json).

Publication/known-by clocks, nominal or derived availability, contradictory variants, source M/null, absent and real zero remain distinct. Current missing values are not replaced by later observations or the separately labelled last-present value.

## 4 What the completed matrix builder actually read

The [expanded candidate builder](scripts/build_expanded_candidate.jl) explicitly reads:

1. `joint-inputs-v3/model_matrix.jls` — **28,100 inherited columns**, with values and missingness asserted unchanged.
2. The native/second-set and ROOT selected values and their registries/vocabularies — **80,839 expanded current columns**, plus changes over 120/300/600 seconds.
3. `external-scope-history-v4/scope_feature_timeline.jsonl.gz` — **200,868 selected dynamic-history/current-age columns**, plus changes over 120/300/600 seconds.
4. Original sample/outcome/metadata files and exact source-context cutoffs/cursor caps.

The resulting matrix is **3,745 samples × 1,154,928 columns**:

```text
28,100 + 4 × 80,839 + 4 × 200,868 = 1,154,928
```

The multiplier four means current measurements plus three lag-change blocks. It is not four independent samples. Constant history dimensions remain in provenance even when not materialized into the dynamic input. Per-model/cohort training preprocessing and feature eligibility still determine fitted columns; existence in a registry is not proof every model used every field.

The [final input receipt](final-model-analysis-20261023/source/model_input_receipt.json) binds these counts and the unchanged target-file SHA256 `6a0613a357675ba60c7d4e946592b2aa69ea0e09dd488cd0ecfa4d54ba445608`.

The complete encoded column-name file is `joint-inputs-v4-candidate-20261022/model_feature_registry.csv`, emitted alongside `model_matrix.jls`. The large final registry is intentionally not duplicated into this small inventory. The source-files CSV records its original location; the Git-committed extraction registries above supply detailed native/ROOT field lists. The inventory does not invent a matrix/registry hash where the inspected receipt did not provide one.

## 5 Exact market replay for individual analysis

[Timestamped book export](timestamped-mbo-window-v1/window_receipt.json):

- 22,194 consecutive completed-group books.
- 10,267,320 bid/ask level rows, including absolute/raw price, rank/side, size, order count and queue-age summaries.
- Anchor instance 375, selected chronologically before outcomes; −120/+600 seconds around its first appearance.
- [Quote books](timestamped-mbo-window-v1/consecutive_quote_books.csv.gz).
- Level data split into `consecutive_bid_ask_levels.csv.gz.part001` through `.part004`, totaling 243,624,107 compressed bytes. They are byte parts of **one** gzip stream.
- Original source offsets and hashes retained; no synthetic fills or intragroup states.

The same window partially covers instance 391. [The individual case review](instance-market-review-20261023/instance-375-review.md) records those boundaries and what remains unproven about replenishment and real-time detection.

## 6 Retained evidence and recovery locations

The 99 plane identities include raw/calculation/clocks, knowledge/control/arms, sealed answers/targets, disabled shadows and append-only outputs. They are **not 99 automatically valid numerical predictors**. [The registry](descriptive-v1/plane_registry.csv), producer definitions, teacher/brain material and complete episode/dipole evidence remain linked research evidence. Later knowledge and terminal outcomes cannot be backdated as predictors.

Exact locations, sizes and recorded hashes are in [the source-files CSV](deep-market-data-source-files-20261023.csv). In particular:

- Input/component checkpoint archives: `s3://bento-568968024170-us-east-2-an/frankie/family-prebirth/20261022/`.
- Additional prior-day external source: exact URI and distinct source SHA256 in the CSV.
- Final fitted-result/shard archives: `s3://frankie-granite42-568968024170-us-east-1/host-deliveries/family-research-20261022/`, epoch `cce6f548f09f50f00caaca396a213e9f2d42d5a7ff85c0644be311eb83e708f4`.
- Frozen-input snapshot: `snap-0d3e867c1240b6528`; original EBS is retained.
- [Full save/stop verification and recovery layout](../../../../tasks/family-research-20261022/verified-save-stop-completion-20261023.json).

The final result archives are not a claim that all original raw input files are inside the A results tar. Preserve the separately pinned input/component archives, original retained storage and frozen snapshot. Paths/verification status in this inventory are receipt-based; no new S3 or EC2 verification was performed.

**Semantic coverage remains NOT_PASSED.** Native/ROOT extraction and actual matrix consumption are established at the levels stated above; complete knowledge/99-plane semantic consumer coverage and some units remain unresolved. Missingness and contrary evidence are retained. All 2,097 fits and final processing are complete, and the four scoped boxes remain stopped. This commit adds inventory files only.
