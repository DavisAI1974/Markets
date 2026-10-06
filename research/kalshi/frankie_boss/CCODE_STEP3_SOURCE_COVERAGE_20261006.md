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

The table is the code: `PLANE_COVERAGE` in `frankie_box_experiment_search.py` (59 rows: the 49 layers of the complete
registry, checked name by name against `knowledge/CYCLE_CALCULATION_PINS.md`, plus the found categories and the day
file). `plane_summary` writes it into every search MANIFEST as `planes`, downgrading any `consumed` row whose source the
run did not read to `listed_missing` / `not_in_this_export`, so the receipt states what that run read. Statuses:

| status | meaning |
| --- | --- |
| consumed | every retained form of the layer the path produces is a series or cell of the search |
| consumed_partial | a per-group or teacher form is searched; the cross-group or per-level form is not (named in `remaining`) |
| produced_not_carried | the pinned producer computes it at every F_LAST close (it is in the APPLIED frame) and the ROOT legacy pass does not spool it |
| computed_not_retained | the pinned teacher computes it and retains only a projection |
| built_not_called | an implementation exists and nothing on the experiment path calls it |
| not_produced | only the bedrock traversal/projection (off) produces it |
| clock | a timestamp or availability rule; it places series, it is not one |

Counts: consumed 13, consumed_partial 23, produced_not_carried 5, computed_not_retained 1, built_not_called 1,
not_produced 10, clock 6. The rows that answer the pushback directly:

| plane | status | consumed through | remaining |
| --- | --- | --- | --- |
| Families (`derived_d_family_geometry`; every action-string family, carried seed or open-world candidate) | consumed_partial | `structures.*`: cells `action_string, candidate_family_id, carried_native_family, discovery_status, side_string, terminal_action, terminal_side`; series `matches_carried_native_family, action_counts.<a>, side_counts.<s>, component_count, distinct_*_count, price_raw_min/max/span` | the cross-group family lineage rows: not produced (bedrock projection) |
| Mirror identity | consumed | cells `structures.mirror.orientation, mirror_pair_key, mirror_side_string, side_string` | none |
| Fill disposition (`order_lifecycle_fills`) | consumed_partial | `structures.fill_disposition.fill_id_count, cancelled_fill_id_count, modified_fill_id_count, same_id_cancel_modify_count, unresolved_fill_id_count`; cells `class, signature`; `events.F_*`; teacher `far_absorption_share_64/1024` | per-order disposition across groups: not produced |
| D's / exhaustion (`derived_unresolved_age_chain_trajectory`, `prebirth_unresolved_chain_extension_state`) | consumed_partial | teacher `dipole.unresolved_age_groups_log, extension_count_log, step_ratio_log, pullback_ticks_last_log, step_duration_groups_log, pullback_ticks_prev_log` | `DState` computed, not retained; the rows' `state`/`raw_reason` categories counted in the manifest, not cells; bedrock episode rows not produced |
| Depletion/replenishment, resilience/recovery | consumed_partial | teacher `far_replenish_log1p_64/1024, far_absorption_share_64/1024, far_identity_survival_64/1024, far_size_retention_64/1024` | the bedrock replenishment/absorption/recovery rows: not produced |
| FIFO queues, queue age and survival, queue concentration, orders and volume ahead | produced_not_carried / consumed_partial | teacher `far_front_age_log, far_queue_age_p90_log, far_size_hhi` (far-side top-three cohort) | per level, top 10 each side: `front_order_age_s, queue_age_median_s, queue_age_p90_s, largest_order_share, front_order_size, order_count, size` produced in every frame, not spooled; FIFO ids and volume ahead in the APPLIED observation, not spooled |
| Mechanics by side and level, churn and turnover, aggressor flow | consumed_partial / produced_not_carried | `structures.action_counts.*, side_counts.*`, `events.<action>_<side>`, `signed_flow.buy/sell` | the frame's rolling activity windows (`action_qty, action_side_qty, add_cancel_churn, priority_lost_modify_count, trade_*_aggressor_qty, trade_aggressor_imbalance, top_level_*_qty_derived`) produced, not spooled |
| Missingness and integrity | consumed_partial | Dipole states counted per column (`states_per_component`), values used only where PRESENT | the frame's `integrity` counters produced, not spooled; `failures.jsonl` not read; `raw_reason` not cells |
| Order lifecycle adds/cancels/modifies/replaces/trades/clears | consumed_partial | `events.<action>_<side>` counts and sizes; `events.last.<field>` at the close; cells `events.last.action/side`; `prices.*`; `events.last.is_snapshot` | per-order linking, identity transitions, roll state, bootstrap receipts: not produced |
| Spread and depth imbalance, price and book path, legacy price/flow/roll20/book/structure | consumed | `frames.*`, `prices.*`, `signed_flow.*`, `roll20.value`, `structures.*` | none |
| Full depth, level and order counts | consumed_partial | `frames.bid/ask_depth_full, bid/ask_order_count_full, bid/ask_price_level_count_full` | per-level size and order_count produced, not spooled |
| Open-world predecessor state | consumed_partial | cell `structures.discovery_status` per group | across groups: not produced |
| Ancestry gaps, book-regime paths, v4 mechanics fifo features (`_window_extras`), feature-availability stamps, the 5 pre-birth layers, discovery/evaluation/lock clocks, identity transitions, roll state, bootstrap receipts | not_produced | nothing | bedrock traversal/projection only |
| `odcore.info_dipole` divergence/exhaustion | built_not_called | nothing | referenced only as the construction of historical claims H01/H02; computing it on the day's signed flow is a new derived series |
| Day file, 27 aliases and every other column per entity | consumed | `external.<alias>.value`; `external.<table>.<column>.entity=<id>`; text columns as cells | none |
| Sealed journal INPUT / APPLIED | consumed / produced_not_carried | INPUT: `events.*`, `events.last.*`; identities listed | APPLIED frame and observation: read whole by the teacher; `journal_axis` built, uncalled (axis change) |

Clocks (6 rows): `ts_recv_ns` is the axis and every source's known-at stamp; `ts_event*` is read and popped; the as-of
rule and the leakage gate are `clock_event_known_by` / `clock_feature_availability` applied; the three host clocks are
not on the path.

## 3. The two wiring gaps fixed, with their active caller and calculation consumer

Both reuse the existing machinery only: `asof_values` (the as-of placement), `leakage_gate` (`odcore.leakage`), the
`columns()` flattening rule, the existing transforms, cells, lags, `couple` and the chance check. No clock, grouping, lag
unit, transform, cell rule or statistic changed; every event and every entity stays distinct; original values are
placed, never reduced.

**Per-event INPUT quantity fields -> `events.last.<field>`** (`build_series`, the INPUT loop): for every record every
numeric field (price, price_raw, size, flags, is_last, is_snapshot and any other the record carries; bools as 0/1) is
collected with the record's own `ts_recv` as the known-at stamp; `asof('events.last', event_known, event_fields)` runs
the leakage gate per field and places each as a series read at the first group close at or after the record; `action`
and `side` become cells `events.last.action` / `events.last.side` through `asof_values`. Identity and clock fields
(`EVENT_IDENTITY_FIELDS`) are listed in `sources[events].per_event_fields`, not searched.
Consumer chain: `build_series` -> `series['events.last.<f>']` -> `run()` builds `steps[t][name]` for every transform t
over `names = sorted(series)` (`_step_job`) -> `jobs` = every (cell, transform, x) over `names` -> `_cell_job` takes each
`x`, including `events.last.*`, and for every partner `(ty, y)` from `y_transforms(tx)` computes
`couple(fx, transforms(pick(steps[ty][y])), lags)`: the joined-teacher statistic with its circular-shift null, written as a
pair row with `beyond_chance`. The cells `events.last.action/side` enter `cell_index` and condition every job exactly as
the existing text cells do.

**Every day-file column per entity -> `external.<table>.<column>.entity=<id>`** (`build_series`, the external block):
`frankie_box_experiment_surface.external_fields(reader)` (built, previously uncalled) yields every table column per
native entity with its own publication stamps; a column whose stamps and values equal an alias is marked
`covered_by_alias` and not searched twice; the stamp column and entity identities are listed; numeric columns go through
`asof('external.' + key, stamps, {'value': values})` (leakage gate, as-of placement); text columns become cells; mixed or
nested columns are listed. `SEARCH_EXTERNAL_FIELDS=aliases` keeps the 27 aliases only, recorded in the manifest.
Consumer chain: identical to the above from `series[...]` onward: `_step_job` -> `jobs` -> `_cell_job` -> `couple`.

Also in this commit: `NOT_SEARCHED` rewritten per plane (11 entries, no "bedrock" lump: the per-level/activity/integrity
fields as produced-not-carried; the D chain's state and reasons; the structure identity lists; the bedrock-only layers;
the failures spool; conditions, targets, the ordinal axis, the teacher-not-run case, the claims), the `PLANE_COVERAGE`
receipt and `plane_summary`, the `y_transforms` docstring (every T x T' pair was already produced).

## 4. Remaining gaps, each with its exact missing connection and owner (reported, not implemented)

1. **Per-level FIFO/queue-age/concentration, rolling activity, integrity at every F_LAST close** (produced_not_carried,
   5 registry layers plus the per-level halves of 4 more). The values exist at the same F_LAST closes the axis uses
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
2. **The Dipole rows' `state` and `raw_reason` as cells** (computed_not_retained; the D chain's own categories
   `CHAIN_BROKEN` / `NO_COMPLETED_STEP` / `DEGENERATE_STEP` and every column's PRESENT/MISSING/INVALID/ABLATED). Exact
   change, my file: in the dipole block of `build_series`, beside `values[name]`, keep `reasons[name].append(c.get('raw_reason'))`
   and `states_text[name].append(state)` and place them with `asof_values` as cells `dipole.<column>.state` and
   `dipole.<column>.reason`. Three lines; not done because it adds cells (conditions) beyond the two gaps.
3. **`DState` retention** (the chain's armed/broken/extension/pullback state between the six columns): computed inside
   the pinned teacher (`c15_dstate`, `c15_teacher`), retained nowhere. Exposing it means the pinned teacher retaining more
   than its target rows: a pinned-code change, Greg's call.
4. **`odcore.info_dipole` on the day's signed flow** (built_not_called): `divergence(buy_vol, sell_vol, price_drift)` and
   `signed_flow_features` could run on `legacy_native_signed_flow` per second with the prices spool's drift; that is a new
   derived series (a calculation), listed as a mathematical decision.
5. **Bedrock-only layers** (not_produced, 10 rows and the cross-group halves of the consumed_partial rows): produced only
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

- `py_compile` on `frankie_box_experiment_search.py`; module import; `PLANE_COVERAGE` checked against the 49 registry
  names (none missing, 59 distinct rows); `plane_summary` exercised as a pure function with read/missing sources (a
  consumed plane whose source is missing reports `listed_missing`); diff review. No tests, installs, dispatch, model
  call, E2E or AWS action.
- Cost note for the E2E: the per-event fields add a handful of series; the day-file columns can add hundreds of entity
  series and the pair count grows with the square of the series count; `SEARCH_EXTERNAL_FIELDS=aliases` restores the
  previous surface without a code change.
- Nothing required for integration; the drafts patch is unapplied; no #5, Granite or Jev work.
