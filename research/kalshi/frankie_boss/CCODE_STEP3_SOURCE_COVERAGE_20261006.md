# CCode step #3: source-to-consumer map of the existing planes (2026-10-06)

Branch `ccr-e9f0f4af-lqxmss`, rebased onto Codex checkpoint `4eec55ec` (base tip `440f9149`). SOURCE-BUILT /
RUNTIME-UNVERIFIED: every statement below comes from reading producers, readers and callers in the checkout (and the
pinned producer commit `2ebb8ce8` for the two modules not in this checkout); no search, teacher, ROOT, E2E or AWS action
ran. The codebase-memory MCP (`index_repository`) timed out on this repository; the trace was done by direct reads and
caller greps; nothing is attributed to the graph.

Files CCode edits: `frankie_box_experiment_search.py` (changed), `frankie_box_experiment_surface.py` (unchanged: its
`external_fields` is now called; the rest is listed below), `frankie_box_experiment_data.py` (unchanged: the export
already carries every file the experiment path produces; its BEDROCK exclusion is Greg's 2026-09-29 decision).

Scope ruled by the drop-in: only the two verified wiring gaps are implemented (section 3). Everything else is reported
with its exact status and, where a connection is missing, the exact change and owner (section 4). "Bedrock-era" is not
used as a status anywhere: each layer is placed by what the experiment path actually produces and reads.

## Integration review by Codex — 2026-10-06

Integrated from CCode `e46228fbc46a7eee88e44a2be7d758d7e8f54175` onto the newer Codex tree at
`f143e775090296774f31adfda3cbc5f59fd687a0`. The map is useful source evidence, but its original claims of lossless
per-event coverage, value-based alias identity and complete consumption were incorrect. The implementation and this
map are corrected below. Existing candidate/scientific counts are not independently verified by reading this map.
Action-string family descriptors and teacher D-chain projections are related inputs, not proof that every registered
D-family geometric or exhaustion calculation has been run. #2 and #3 remain open; no real E2E has passed.

## 1. The producers on the experiment path and what each one emits

- **Ingest** (`frankie_box_ingest_block.sh`, the pinned V4 adapter and `c15_observer.observe_book`): the sealed journal.
  Per record an INPUT entry with every raw field. Per F_LAST group an APPLIED entry holding the V4 `event_frame`
  (`raw_actions` of the group; `book` = `book_snapshot(depth 10)`: best/spread/mid, bid/ask depth n and full, order and
  level counts, and per level `bid_levels[i]` / `ask_levels[i]` with `size, order_count, front_order_size,
  front_order_age_s, queue_age_median_s, queue_age_p90_s, largest_order_share`; `activity` = rolling windows 1/5/20/60/300 s
  with `event_count, action_count.*, action_qty.*, action_side_qty.*, trade_buy/sell_aggressor_qty,
  trade_aggressor_imbalance, add_cancel_churn, top_level_add/cancel_qty_derived, priority_lost_modify_count,
  missing_reference_count`; `integrity` counters) and the full-book observation (every resting order, every level's FIFO
  order ids).
- **ROOT legacy pass** (`frankie_box_boss_session.py` 737-836, run by `frankie_box_experiment_root.py` with
  `Session.derive(bedrock=False)`): `adapter.apply(record)` for every INPUT record; writes `.rows/prices.jsonl`
  (trades: ts, price, size, touch), `.rows/frames.jsonl` (per F_LAST: `best_bid, best_ask, mid, depth_imbalance_n` plus
  `book_transition(previous, book)['after']` = the eight `BOOK_FIELDS` `spread, depth_imbalance_full, bid/ask_depth_full,
  bid/ask_order_count_full, bid/ask_price_level_count_full`, plus `transition` = the sign signature),
  `.rows/structures.jsonl` (per F_LAST: `describe_structure(raw_actions)`: `action_string, side_string, action_counts,
  side_counts, terminal_action, terminal_side, component_count, distinct_price_count, distinct_order_id_count,
  fill_disposition_signature, candidate_family_id, matches_carried_native_family, carried_native_family,
  discovery_status, price_raw_min/max/span, order_ids, fill_disposition{class, *_order_ids, *_count, signature},
  mirror{side_string, mirror_side_string, mirror_pair_key, orientation}`), `.rows/failures.jsonl`, the five legacy layer
  JSONs (`legacy_native_signed_flow.json`, `legacy_per_second_roll20.json` and the three spools under their layer names).
  **The frames spool keeps 4 + 8 fields of the frame's `book` and nothing of its per-level lists, `activity` or
  `integrity`** (lines 816-822: the exact dropped carrier).
- **BOSS teacher** (`frankie_box_experiment_teacher.py` for every day in `_finish_day`; `c15_teacher_r3.JournalTeacherR3.attach`
  through `parallel_teacher.parallel_attach`): walks the journal whole (every level, FIFO ids, unknown trades carried),
  runs the far-side cohort geometry and the D chain (`c15_dstate.DChain`) and retains per context cursor one row of the
  19 columns (`c15_normalizer.COLUMNS`), each with `value, state (PRESENT/MISSING/INVALID/ABLATED), raw_reason`.
  `DState` itself (`anchor_dir, E, E_prev, armed, broken, pull_depth, n_ext, m_last, m_prev, p_last, p_prev, g_E, age,
  duration_last`) is not retained anywhere; it reaches the rows only as the six chain columns and their reasons
  (`CHAIN_BROKEN, NO_COMPLETED_STEP, DEGENERATE_STEP`).
- **Day file** (`frankie_box_day_external.sh`): the 13 historical points as 27 aliases plus every other column of every
  table, per entity, each at its publication stamp (`operations/frankie_day_external.AsOfReader`).
- **Bedrock traversal/projection** (ROOT processes 2 and 3, `frankie_box_bedrock.py`): OFF on the experiment path;
  `derive.json` records its layers `not_derived`; the export marks `work/bedrock/**`, `.projection-v2/**`,
  `bedrock_section_*` BEDROCK.

## 2. The receipt: every registry layer and every category the calculations find

`PLANE_COVERAGE` names all 49 registry layers plus found categories (59 rows). It is a static source mapping.
`plane_summary` writes `mapped` / `mapped_partial`, not a claim that a whole plane was consumed. Each source receipt
now lists actual `placed_series`, `placed_cells` and exclusions. A missing source is `listed_missing` or
`not_in_this_export`; an empty read is `read_without_channels`. The full day-file row is `not_requested` under
`SEARCH_EXTERNAL_FIELDS=aliases`. Failed numeric leakage gates are recorded as exclusions. `cells_not_counted` and
the exact `couplings.parts` establish which pair computations were produced; a placed channel alone does not.

Other statuses retain their literal meanings: `produced_not_carried`, `built_not_called`, `not_produced`, `clock`.
The row-state/reason category is `retained_not_searched`: its original `computed_not_retained` label was wrong.
DState itself remains unretained, as described separately. Static status counts are not runtime coverage totals.
The table below is a source map; "none" means no additional gap was identified for that mapped projection, not proof
of complete scientific coverage.

| plane | status | mapped through | remaining |
| --- | --- | --- | --- |
| Families (`derived_d_family_geometry`; every action-string family, carried seed or open-world candidate) | mapped_partial | `structures.*`: cells `action_string, candidate_family_id, carried_native_family, discovery_status, side_string, terminal_action, terminal_side`; series `matches_carried_native_family, action_counts.<a>, side_counts.<s>, component_count, distinct_*_count, price_raw_min/max/span` | the cross-group family lineage rows: not produced (bedrock projection) |
| Mirror identity | mapped | cells `structures.mirror.orientation, mirror_pair_key, mirror_side_string, side_string` | none |
| Fill disposition (`order_lifecycle_fills`) | mapped_partial | `structures.fill_disposition.fill_id_count, cancelled_fill_id_count, modified_fill_id_count, same_id_cancel_modify_count, unresolved_fill_id_count`; cells `class, signature`; `events.F_*`; teacher `far_absorption_share_64/1024` | per-order disposition across groups: not produced |
| D's / exhaustion (`derived_unresolved_age_chain_trajectory`, `prebirth_unresolved_chain_extension_state`) | mapped_partial | teacher `dipole.unresolved_age_groups_log, extension_count_log, step_ratio_log, pullback_ticks_last_log, step_duration_groups_log, pullback_ticks_prev_log` | `DState` computed, not retained; the rows' states counted in the manifest, reasons retained in source rows, neither used as cells; bedrock episode rows not produced |
| Depletion/replenishment, resilience/recovery | mapped_partial | teacher `far_replenish_log1p_64/1024, far_absorption_share_64/1024, far_identity_survival_64/1024, far_size_retention_64/1024` | the bedrock replenishment/absorption/recovery rows: not produced |
| FIFO queues, queue age and survival, queue concentration, orders and volume ahead | produced_not_carried / mapped_partial | teacher `far_front_age_log, far_queue_age_p90_log, far_size_hhi` (far-side top-three cohort) | per level, top 10 each side: `front_order_age_s, queue_age_median_s, queue_age_p90_s, largest_order_share, front_order_size, order_count, size` produced in every frame, not spooled; FIFO ids and order sizes in the APPLIED observation, not spooled; volume ahead is derivable, not a retained searched value |
| Mechanics by side and level, churn and turnover, aggressor flow | mapped_partial / produced_not_carried | `structures.action_counts.*, side_counts.*`, `events.<action>_<side>`, `signed_flow.buy/sell` | the frame's rolling activity windows (`action_qty, action_side_qty, add_cancel_churn, priority_lost_modify_count, trade_*_aggressor_qty, trade_aggressor_imbalance, top_level_*_qty_derived`) produced, not spooled |
| Missingness and integrity | mapped_partial | Dipole states counted per column (`states_per_component`), values used only where PRESENT | the frame's `integrity` counters produced, not spooled; `failures.jsonl` not read; `raw_reason` not cells |
| Order lifecycle adds/cancels/modifies/replaces/trades/clears | mapped_partial | `events.<action>_<side>` counts and sizes; `events.last.<field>` at the close; cells `events.last.action/side`; `prices.*`; `events.last.is_snapshot` | per-order linking, identity transitions, roll state, bootstrap receipts: not produced |
| Spread and depth imbalance, price and book path, legacy price/flow/roll20/book/structure | mapped | `frames.*`, `prices.*`, `signed_flow.*`, `roll20.value`, `structures.*` | none |
| Full depth, level and order counts | mapped_partial | `frames.bid/ask_depth_full, bid/ask_order_count_full, bid/ask_price_level_count_full` | per-level size and order_count produced, not spooled |
| Open-world predecessor state | mapped_partial | cell `structures.discovery_status` per group | across groups: not produced |
| Ancestry gaps, book-regime paths, v4 mechanics fifo features (`_window_extras`), feature-availability stamps, the 5 pre-birth layers, discovery/evaluation/lock clocks, identity transitions, roll state, bootstrap receipts | not_produced | nothing | bedrock traversal/projection only |
| `odcore.info_dipole` divergence/exhaustion | built_not_called | nothing | referenced only as the construction of historical claims H01/H02; computing it on the day's signed flow is a new derived series |
| Day file, legacy aliases and fields per entity | mapped_partial | `external.<alias>.value`; `external.<table>.<column>.entity=<id>.value` and nested leaves; text leaves as cells | identity/clock columns listed; as-of sampling can omit values superseded before a group close; actual exclusions recorded |
| Sealed journal INPUT / APPLIED | mapped_partial / produced_not_carried | INPUT: `events.*`, `events.last.*`; identities listed | APPLIED frame and observation: read whole by the teacher; `journal_axis` built, uncalled (axis change) |

Receive timestamps and publication stamps govern alignment; absolute event timestamps are listed. The registry's
derived feature-availability layer is not produced. A generic as-of rule or leakage gate is not that layer.

## 3. Integrated wiring and corrections, with actual calculation consumers

The F_LAST axis, transforms, cell-selection rule, lags, `couple` and circular-shift chance statistic are unchanged.
No native-ordinal draft is applied. These additions broaden inputs under that existing axis; they do not turn it into
a lossless all-event search.

**Closing INPUT quantities -> `events.last.<field>`:** only the closing INPUT of each F_LAST group is selected.
Its ordinal group position and receive stamp must match the ROOT frame. Direct placement at its own frame prevents a
later record with an equal receive timestamp from replacing the earlier group's closing record. A mismatch lists the
new projection as unavailable, preserving the original spool and existing search inputs. The source receipt counts
selected records and records not individually selected. Intermediate field values remain unsearched. Existing per-group
action/side counts and sizes remain unchanged. `ts_in_delta_ns` is an interval and now stays a quantity; identity,
metadata and absolute clocks remain listed. Text fields of the closing record supply the existing text-cell machinery.
This corrects the original statement that every event is placed at its first following close: `asof_values` selects
only the latest known value and cannot preserve every intermediate event on that axis.

**Day-file fields per entity:** the existing `external_fields(reader)` is now called. Every non-identity/non-clock
column goes through the existing `columns()` reader, including nested/list leaves, booleans, nulls and separate numeric
and text channels for mixed fields. Numeric leaves use the existing `leakage_gate` and `asof_values`; text leaves use
existing as-of cells. No field is skipped because its values happen to equal another series. Legacy aliases remain
alongside entity-specific fields, with source definitions listed. They are overlapping representations of evidence,
not additional independent observations. This also removes the hash-of-values failure for nested lists/dicts and the
original boolean-only misclassification. The table's actual `stamp_column` identifies its clock.

`SEARCH_EXTERNAL_FIELDS` accepts only `all` (default) or `aliases`. The mode and active surface helper hash are now
pinned in the search continuation identity. A resume cannot silently reuse the other mode's prepared arrays. Aliases-only
is reduced coverage, not an equivalent scientific run. No existing completed artifacts are rewritten.

Both channel routes reach `build_series` -> `search` -> `_step_job` -> the existing `jobs` / `_cell_job` ->
`couple(fx, transforms(pick(steps[ty][y])), lags)`. The full transform roster already existed; its docstring correction
is not a new cross-transform implementation. Data availability and actual completed calculations remain distinct.

## 4. Remaining gaps, each with its exact missing connection and owner (reported, not implemented)

1. **Per-level FIFO/queue-age/concentration, rolling activity, integrity at every F_LAST close** (produced_not_carried,
   including per-level portions of several registry mappings). The values exist at the same F_LAST closes the axis uses
   (the APPLIED frame of the sealed journal; the ROOT frame before spooling), so no axis, clock or grouping change is
   needed. Two routes: (a) ROOT spool: in `frankie_box_boss_session.py` 816-822 spool the frame's
   `book.bid_levels[i].*`, `book.ask_levels[i].*`, `book.bid_depth_n/ask_depth_n`, `activity.<w>.*` and `integrity.*`
   beside the 12 current fields (the search's `columns()` already flattens list positions and nested keys, so
   `frames.book.bid_levels[0].front_order_age_s` would be a series with no search change); owner: the ROOT session
   module (Codex/ROOT), and the retained ROOT identity (legacy-state resume) must be re-minted for the changed row shape.
   (b) Search-side: a reader of the journal's APPLIED entries that takes only `frame.book`/`activity`/`integrity` at
   each APPLIED `ts_recv_ns` (the F_LAST close) and feeds `asof`; `surface.journal_axis` is the existing reader but
   materializes every entry whole including the observation and changes the axis, so this route is new reader code in
   my file. Either is a wiring of available data with the same statistic; it is outside the two authorized gaps, so it
   is the next decision for Codex/Greg. Cost: 10 levels x 2 sides x 7 fields + 5 windows x ~14 fields adds ~200 series.
2. **The Dipole rows' `state` and `raw_reason` as cells** (retained_not_searched; the D chain's own categories
   `CHAIN_BROKEN` / `NO_COMPLETED_STEP` / `DEGENERATE_STEP` and every column's PRESENT/MISSING/INVALID/ABLATED). Exact
   change, my file: in the dipole block of `build_series`, beside `values[name]`, keep `reasons[name].append(c.get('raw_reason'))`
   and `states_text[name].append(state)` and place them with `asof_values` as cells `dipole.<column>.state` and
   `dipole.<column>.reason`. Not implemented in this integration; causal row binding and missing states must be preserved.
3. **`DState` retention** (the chain's armed/broken/extension/pullback state between the six columns): computed inside
   the pinned teacher (`c15_dstate`, `c15_teacher`), retained nowhere. Exposing it means the pinned teacher retaining more
   than its target rows: a pinned-code change, Greg's call.
4. **`odcore.info_dipole` on the day's signed flow** (built_not_called): `divergence(buy_vol, sell_vol, price_drift)` and
   `signed_flow_features` could run on `legacy_native_signed_flow` per second with the prices spool's drift; that is a new
   derived series (a calculation), listed as a mathematical decision.
5. **Bedrock-only layers** (not_produced layers and the cross-group halves of mapped_partial rows): produced only
   by ROOT processes 2 and 3 (`BEDROCK=on` in `frankie_box_experiment_root.sh` / the orchestrator's `root()` env, Codex)
   and admitted by lifting the BEDROCK disposition in `frankie_box_experiment_data.py` CATALOG (mine, two lines). Greg's
   2026-09-28 "give the teachers the bedrock tables" and 2026-09-29 "no bedrock in the experiment" conflict; the code
   implements the second; the cost is the Monday ROOT's multi-hour traversal per day in the day's lane. Not done.
6. **Structure identity lists** (`structures.order_ids[i]`, `fill_disposition.*_order_ids[i]`) are searched as numeric
   series by position. Treating them as identities (listed, like `EVENT_IDENTITY_FIELDS`) would remove series from the
   search; left as is and listed, so the series count is read correctly.
7. **Conditions on numeric states** (`state_masks`, built, uncalled) and **the native ordinal axis** (`journal_axis`,
   `ordinal_values`; the preserved patch's core, unapplied): design and mathematical decisions as before.
8. **`failures.jsonl`**: the records the legacy pass could not apply are listed in the ROOT receipt, not read by the
   search (not a series).

## 5. Checks, status

- CCode reported before integration: `py_compile` on `frankie_box_experiment_search.py`; module import; `PLANE_COVERAGE` checked against the 49 registry
  names (none missing, 59 distinct rows); `plane_summary` exercised as a pure function with read/missing sources (a
  consumed plane whose source is missing reports `listed_missing`); diff review. No tests, installs, dispatch, model
  call, E2E or AWS action.
- Integration source checks: Python compilation, diff review and `git diff --check`; no data execution or new tests.
- Cost note for the E2E: the per-event fields add a handful of series; the day-file columns can add hundreds of entity
  series and the pair count grows with the square of the series count; `SEARCH_EXTERNAL_FIELDS=aliases` reduces coverage and changes the pinned resume identity.
  Entity fields and their legacy aliases overlap; equal bytes do not justify suppressing a distinct entity.
- The drafts patch remains unapplied; no #5, Granite or Jev work. CCode's next assignment is
  `HANDOFF_20261006_CCODE_STEP4.md`; Codex retains search/source integration ownership.
