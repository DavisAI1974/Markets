# CCode step #3: source-to-consumer map of the existing planes (2026-10-06)

Branch `ccr-e9f0f4af-lqxmss` on Codex checkpoint `b141b09f`. SOURCE-BUILT / RUNTIME-UNVERIFIED: every statement below
comes from reading producers, readers and callers in the checkout; no search, teacher, ROOT, E2E or AWS action ran.
The codebase-memory MCP was called (`index_repository`, fast mode) and timed out after 60 s on this repository, so the
trace was done by direct reads and caller greps; nothing is attributed to the graph.

Files CCode may edit: `frankie_box_experiment_search.py` (changed), `frankie_box_experiment_surface.py` (unchanged: its
functions are called now, nothing in it needed to change), `frankie_box_experiment_data.py` (unchanged: the export
already catalogues everything the experiment path produces; its BEDROCK exclusion is Greg's 2026-09-29 decision, below).

## 1. The inventory of planes and where each one lives

The pinned complete registry (`knowledge/CYCLE_CALCULATION_PINS.json`, group `complete_registry_as_of_20260828`) names
49 layers in seven groups. The sealed journal (`c15_builder.AppliedEvidence`) carries, per INPUT record, the raw MBO
record with every field, and per F_LAST group an APPLIED entry with the V4 frame (raw actions of the group, the book
snapshot, activity, integrity, census view, clocks) and the full-book observation (`c15_observer.observe_book`: every
resting order and every price level with its FIFO order ids).

| Plane | Producer in the experiment path | Where it is | Who reads it |
| --- | --- | --- | --- |
| Raw MBO records, every field | ingest (`frankie_box_ingest_block.sh`) | journal INPUT entries; ROOT spool `.rows/input-*.jsonl` (every record decoded) | BOSS teacher (pinned walk), ROOT legacy pass, search (per-group counts; per-event fields since this commit) |
| Full book, FIFO order ids per level, resting orders | ingest (V4 adapter + observer) | journal APPLIED observation | BOSS teacher (pinned walk, "all levels"); nothing in the search (`journal_axis` built, uncalled, see 3.4) |
| Book frames at F_LAST (best/mid/depth imbalance + the producer's full-depth transition fields) | ROOT legacy pass (`frankie_box_boss_session.py` legacy stage) | `.rows/frames.jsonl` = legacy_book_imbalance | search (axis + `frames.*`), classroom via the derivation digest on arm days |
| Group structure (actions by side) | ROOT legacy pass | `.rows/structures.jsonl` = legacy_structure_observables | search (`structures.*`) |
| Trades | ROOT legacy pass | `.rows/prices.jsonl` = legacy_price | search (`prices.*`) |
| Signed flow, roll20 (per second) | ROOT legacy pass | `legacy_native_signed_flow.json`, `legacy_per_second_roll20.json` | search (`signed_flow.*`, `roll20.value`) |
| Dipole, 19 columns (far-side age, HHI, replenishment, priority loss, absorption, identity survival, size retention, unresolved age chain) | the pinned C15 teacher walk, per day (`frankie_box_experiment_teacher.py`, run for every day by `_finish_day`) | `experiment-teacher-rows/<day>/host-dipole-classroom-source.c15.json` | classroom (TEACH/GUIDED), search (`dipole.*`), scientific teacher through the search, exchange |
| Frankie's 13 historical points (27 aliases incl. station temperatures) | day file beside the ingest (`frankie_box_day_external.sh`) | `ingest/day-external.json` | ROOT (`external-computation.json`), classroom external section, search (`external.<alias>.value`) |
| Day-file tables, every other column per entity | same file | same file | nothing until this commit (`external_fields` built, uncalled) |
| Order lifecycle (9), full-book FIFO queue (8), microstructure mechanics (7), derived geometry incl. D family geometry and dipole state (8), pre-birth (5), causal clocks (7) | the pinned bedrock producers (`frankie_box_bedrock.py`, ROOT processes 2 and 3) | NOT PRODUCED: `frankie_box_experiment_root.py` runs `Session.derive(bedrock=False)`; `derive.json` records them `not_derived`; the export marks `work/bedrock/**`, `.projection-v2/**`, `bedrock_section_*` as BEDROCK | nobody in the experiment |
| Exhaustion / D-chain state | the C15 D1-D6 geometry (`c15_dstate.py`) feeds the teacher's Dipole columns (consumed above); the bedrock `derived_d_family_geometry` and `derived_roll20_and_dipole_state` layers are the family/D planes | teacher rows (consumed); bedrock layers (not produced) | as above |

## 2. The consumers, traced

- **BOSS teacher**: `JournalTeacherR3.attach` through `parallel_teacher.parallel_attach` walks the sealed journal whole
  (every level, unknown trades carried) and produces the 19 Dipole columns. Representation supervision, targets, masks
  and controls are the R4 workbook's C14 to C18 and are untouched. Built, actively wired, runtime-unverified.
- **Scientific teacher**: the search (`frankie_box_experiment_search.py`) over the exported day data, then
  `frankie_box_scientific_teacher.py` testing Frankie's novel findings, Jev's claims and the historical catalog on the
  search's counts; since `b141b09f` also the accumulated native claims at the exchange boundary (Codex). Built, wired.
- **Frankie**: ROOT reads the journal (legacy pass: every INPUT record, spools, five legacy layers, bedrock off); the
  classroom reads the teacher rows, the day file and, on arm days, the derivation digest; TEACH and GUIDED answerable,
  SOCRATIC/VERIFY refuse (CCode handoff of the same date). Teachers never receive his private trade-decision logic:
  the export's FRANKIE_REASONING and GRADED exclusions and R09/R10 hold.
- **Joined teacher** (`frankie_box_joined_teacher.py`): the 2026-09-28 model-driven route over the Monday root's 43
  bedrock + 5 legacy layers. Built; dispatchable only through `frankie_box_run.yml` (`box-joined-*` group); no caller
  in the experiment. Its statistic (`_pair_block`) is what the search's `couple` reproduces exactly. Disabled by the
  bedrock-off decision; not re-enabled.
- **Scientific dialogue / teacher discussion / host config**: the full daily run's model-driven classroom dialogue and
  the cycle-0 host configuration. `teacher_discussion.run` is reused by `frankie_box_experiment_exchange.py` (roles);
  `scientific_dialogue` and `host_config` are not on the experiment path. Nothing enabled.
- **Surface helper** (`frankie_box_experiment_surface.py`): four functions, zero callers before this commit.
  `external_fields` is now called by the search. `journal_axis`, `ordinal_values`, `state_masks` remain uncalled (3.4,
  3.5).

## 3. Gaps found and their disposition

### 3.1 Fixed in this commit (available data, existing functions, same statistic)

- **Per-event INPUT fields** (listed "not searched" since the first slice). Every quantity field of every raw record
  (price, price_raw, size, flags, is_last, is_snapshot and any other numeric field the record carries) is now a series
  `events.last.<field>`, placed by the existing as-of rule at the record's own receive time so the group close reads
  the last event's value, through the same leakage gate as every source. `action` and `side` at the close become
  cells. Identity and clock fields (`EVENT_IDENTITY_FIELDS`: order ids, sequence, instrument/publisher/channel ids,
  timestamps) are listed, not searched; an order id has no steps.
- **Every day-file column per entity**: `frankie_box_experiment_surface.external_fields(reader)` now feeds the search:
  each table column, per native entity (station, model, contract, ...), at its own publication stamp. A column whose
  stamps and values equal one of the aliases is marked `covered_by_alias` and not searched twice; the stamp column and
  the entity identities are listed; text columns become cells; mixed or nested columns are listed. The manifest's
  `sources[external].all_fields` names every one of those groups. `SEARCH_EXTERNAL_FIELDS=aliases` (an environment
  variable the search reads; no shell change needed) keeps the thirteen aliases only, recorded in the manifest.
- **Truthful `not_searched` list and a `planes` receipt**. Two entries were stale: cross-transform pairs are already all
  T x T' (`y_transforms` returns every transform; its docstring said otherwise), and the teacher's Dipole rows now exist
  for every day because `_finish_day` runs the teacher step before the classroom. The new `planes` entry in the search
  MANIFEST says per plane whether this run consumed it, listed it missing, or whether no producer runs for it.

### 3.2 Decision for Greg: producer activation (the bedrock planes)

Families, D's, exhaustion as a family plane, order lifecycle, FIFO queue age/survival/concentration/volume ahead,
mechanics, pre-birth and the causal clocks are the 44 registry layers beyond the five legacy ones. They are produced
only by the pinned bedrock producers in ROOT processes 2 and 3, which the experiment ROOT switches off, and the export
excludes their paths. Two of Greg's own decisions conflict here: 2026-09-28 "give the teachers the bedrock tables" and
2026-09-29 "no bedrock in the experiment". The current code implements the second. Making these planes reach the
teachers means (a) `frankie_box_experiment_root.sh` run with `BEDROCK=on` for the experiment days, (b) lifting the
BEDROCK disposition in `frankie_box_experiment_data.py` CATALOG, (c) a cost: the bedrock traversal was the Monday ROOT's
multi-hour stage and would run per day in the day's held 16-CPU lane. (a) is Codex's shell and the orchestrator's
`root()` env; (b) is mine and is a two-line change once decided. Not done without the decision.

### 3.3 Decision for Greg or Codex: numeric-state conditions

`state_masks` builds a mask per (series, sign) at the decision row; wired naively it multiplies the job count by three
times the number of series (hundreds of cells, each coupling every series against every other). Which states are
conditions is a design choice. The text cells (session phase, continuity segment, source day, source role, the closing
action and side, the day-file text columns) are already cells.

### 3.4 Decision: the native journal ordinal axis (the preserved patch's core)

`journal_axis` reads every INPUT/APPLIED entry of the sealed journal with the verified full-evidence reader on the
native ordinal and would expose the APPLIED frame fields and the full-book observation. It was read, not applied:
it materializes every entry whole (the observation is the complete book, thousands of resting orders, per APPLIED
entry) and it changes the axis from F_LAST group closes to entries, which changes step counts, the meaning of a lag
and the chance check's exclusion window. That is a mathematical decision; the patch stays unapplied as instructed.

### 3.5 Not a gap

`ordinal_values` only serves the ordinal axis. The five legacy layer JSON files are the spools under other names
(`frankie_box_digest_render.py` maps them one to one), so they are covered. `targets`: a lagged series is already the y
side at lag k and fills are already the per-group `events.F_*` counts; new target definitions are mathematics.

## 4. Changes, checks, status

- `deploy/aws/box/frankie_box_experiment_search.py`: `EVENT_IDENTITY_FIELDS`, the rewritten `NOT_SEARCHED`, the
  per-event series and cells in `build_series`, the all-column external fields in `build_series`, `plane_summary` and
  the manifest's `planes`, header and `y_transforms` docstrings. `couple`, `transforms`, the leakage gate, the cells,
  the chance check and every count are untouched.
- Checks: `py_compile` on the three owned modules, module import, `plane_summary` exercised as a pure function, diff
  review. No tests, installs, dispatch, model call, E2E or AWS action.
- Cost note for the E2E: the per-event fields add a handful of series; the day-file columns can add hundreds of
  entity series, and the pair count grows with the square of the series count. If the first E2E's search runtime is
  unacceptable, `SEARCH_EXTERNAL_FIELDS=aliases` restores the previous surface without a code change.
- Unresolved for integration (Codex): nothing required for this commit to run. If Greg activates the bedrock planes,
  the ROOT shell/orchestrator env (`BEDROCK=on`) is Codex's and the export disposition is mine.
