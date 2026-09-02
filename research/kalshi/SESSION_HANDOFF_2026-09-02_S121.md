# SESSION HANDOFF 2026-09-02 S121 - BUILT, NOT WIRED: THE SEARCH, THE RULINGS, THE PERSONAS

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Started at `ac4c373` (1,483 tests). Tip at the
time of writing `cd0d7a5`; the final tip, the wiring merges and the close-out shas are in section 9,
which is completed when the three wiring personas land. Read `DROP_IN_S122.md` for the next chat.

## 0. READ THIS FIRST: GREG'S RULINGS OF THE DAY, VERBATIM, AND WHAT EACH CHANGED

Six rulings landed in one session, each recorded in `store/decisions.json` and rendered to
`DECISIONS.md` the hour it was said (D30: a finding with no home does not exist).

- **D82** (measured S120, rule stated S121): a layer's evidence binds to the FILE that carries it,
  never to a document that describes it. 91 of 99 registry layers bound to one markdown; 2 of 75
  applicable inputs reached him. `BOUND_TO_INVENTORY_DOCUMENT` is now a named defect status.
- **D83**: *"hardcoded windows we do not want these! Again i say it! All times are derived by their
  actual events, prebirth findings, h times if we don't find them in prebirth, etc all by using
  the clocks we made just for this reason. There should be zero hard coded time intervals for
  anything."* and *"The clocks need to be wired into Frankie."* ITEM ONE went from a discussion to
  a build the moment this was said, twice.
- **D84**: *"we need to salvage what we can from the agents before they end"* and *"we need to
  have push spots when agents are doing long builds."* Every persona pushes its own branch after
  every commit; the coordinator merges green slices as they land and pushes after each merge.
- **D85, superseded within the hour by D86**: *"We aren't going to worry about a memory
  anymore"* read as retiring the memory arm; corrected by *"Wait. We are only going to do memory
  and not clean but still just one arm"* and *"In rt, Frankie isn't going to be flying blind so
  I'm retiring clean because of time."* ONE ARM AND IT IS A_MEMORY. Memory is his own day-over-day
  carry of his frozen outputs. Then: *"Just give him the canary stuff from the past runs to start
  it and it will build from there"*, *"And the other stuff too. I'm not picky about this."* Day one
  is SEEDED with every committed output of the past runs, provenance-labelled, every lesson
  UNVERIFIED until he verifies it against the stream. The wrong-data run 32851909748-1 is in the
  seed AS the wrong-data run, labelled, not filtered (D76).
- **The premise that reorganised the session**: *"i feel like this stuff has been built but just
  not wired and fed. we need a search for the stuff that you think we should be building, all of
  it and have the Engineer agent persona agents do the wiring and feeding of what has been
  built."* Then *"Look in step1 files for your clocks, windows section"*, *"Have them immediately
  start wiring as they land"*, and *"when they get done wiring have them search more if we still
  need to do that."* The search record is section 4; it confirmed the premise in every area.

## 1. THE FIRST ROUND: FOUR PERSONAS, THE RATE LIMIT, THE SALVAGE

Four test-engineer personas ran in isolated worktrees cut from `ac4c373` (the worktree base-ref
setting was unset, so a default worktree would have branched from the repo default branch, not the
drop-in tip; the worktrees were cut by hand): knowledge delivery (items 3-5, 12), the 99-layer
crosswalk (items 6, 9), the output ledgers (item 8), and the windows-and-clocks packet (ITEM ONE,
redirected mid-run from options to a build spec when D83 landed). The session rate limit killed
all four together mid-slice. Everything committed survived in the worktrees; two uncommitted
tests-first files (19 and 449 lines) were committed by the coordinator as labelled RED salvage on
the persona branches, never merged; all four branches were pushed (the first application of D84).
Greg's interrupt then cancelled the personas for good; their green tips were merged:

| persona | tip merged | what landed | tests at tip |
|---|---|---|---|
| outputs | `833cbd6` (via `6e19421`, `1581c67`) | `native_principal_outputs.py`: the required ledger set DERIVED from registry + contract headings + 9a + knowledge verification (no count anywhere), chain-hashed append-only ledgers, ten per-ledger validators, the timing rule (a named clock and observed ns, never a ladder label), whole-bundle and directory validation, CLI | 1,596 |
| windows | `490f8c2` (via `b3f31eb`) | `FRANKIE_WINDOWS_AND_CLOCKS_D60_PACKET_S121.md`: the measured record of every fixed interval and the seven clocks, and the build spec under D83; its salvaged clock tests are on `persona/s121-windows` at `21c4622` | 1,483 (doc only) |
| knowledge | `00c03db` (via `c1df5ac`, `8b47df6`) | inventory classification by rule (KEEP / CODE / SUPERSEDED / SEALED / OBSOLETE), the dated addendum `NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824_ADDENDUM_20260902.md`, the 14 knowledge layers REBOUND to their real KEEP files by script with `registry_sha256` recomputed, the two `_V3_V4_` proposal addenda allow-listed under the lineage ruling | 1,527 |
| crosswalk | `e5a6c85` (via `fc1b316`, `9f38038`) | `native_layer_crosswalk.py`: `LAYER_PRODUCERS` for all 99 layers verified by execution, `crosswalk()` with COMPUTED status, `gate_applicable_inputs` (the item-7 gate function), the policy-versus-computed comparison, the fixture render | 1,546 |

Merged tree: **1,703 tests green**, store check, docs gate and the D34 grep clean at `1581c67`.
Two document-registry entries were added for the renders (`6d56216`, `bfb4e43`).

## 2. THE SUNDAY CROSSWALK, ON THE REAL RESULT

The delivery manifest of run 33666109982 presigns Sunday's `calculation_result.json` directly, so
it was fetched into the gitignored `data/` (D34: the S3 key and sha256 are its identity, never a
local path) and the crosswalk computed on it: **75 of 75 applicable inputs not DELIVERED** - 60
PRODUCED_NOT_DELIVERED, 14 reading BOUND_TO_INVENTORY_DOCUMENT off a static producer flag that
predates the rebind (itself a wiring finding), 1 NO_PRODUCER_FOUND (clock_lock_time, correctly:
his own output), 9 sealed UNPROVEN, 10 outputs PENDING. Registered as a dated record,
`LAYER_CROSSWALK_SUNDAY_33630348943_RENDER_20260902.md`. That run (result_hash `d2ab3feb...`,
57,027 records, 43,569 groups, 19 cutoffs) predates the field census and sections 4.0 and 4.0b,
so the emitter refuses it, which is right. Canary 33659412614 completed green on `69c7fc3`, also
pre-clocks. The Sunday re-run belongs to the next chat, through the A-memory launch workflow.

## 3. WHAT THE SCRATCHPAD CORRECTION WAS

The Sunday objects were first fetched into the session scratchpad. Greg: *"we don't use scratchpad
anymore. that's a rule in your md file."* D34: git for code and records, S3 for data, `data/` as
the only disposable local place, and no artifact may name a scratchpad path. Moved, the scratchpad
copies deleted, every persona reminded, and every merged diff grepped for scratchpad and /tmp
paths before commit.

## 4. THE SEARCH RECORD (Greg's premise, verified)

`FRANKIE_BUILT_NOT_WIRED_SEARCH_S121.md`, from three read-only search agents at `bfb4e43`. In one
sentence: every validator, receipt, renderer and gate needed for the spawn path exists and is
tested; almost none has a production caller; the one function that exists nowhere is the
sealed-absence proof producer. Highlights, each verified by reading the cited code:

- The knowledge pipeline exists end to end, including the per-artifact INSPECTED / UNINSPECTED read
  gate (`bind_principal_knowledge_use`); nothing on the spawn path imports it; the manifest's 12
  artifacts overlap the 63 KEEP paths in zero places; Python source is not an allowed kind.
- `load_principal_artifact`, `attach_principal_findings`, `validate_output_bundle_dir`,
  `render_crosswalk_table`, `gate_applicable_inputs` have no production caller; `emit()` is called
  by no workflow; `native_staging.py` is the only sibling without a CLI.
- Three of the seven clocks are FULL in `member_clock_row` and need a naming wrapper by registry
  id; two are same-frame field copies; one is a key on the cutoff dict; the seventh is his own
  first-lock entry. The Step-1 2-day module carries the most developed clock design on the same
  hash-locked adapter, including `event_known_by_ts_recv_ns` as the next confirming record's
  receive time and a post-lock `outcome_availability` clock.
- All ten native sections are wired and event-anchored; what does not exist is an `activity_since`
  recomposition on anchors and two small accumulators (last book reset, last same-side F_LAST).
- 4.16's event-driven half is WIRED and OFF by default, which is why Sunday produced zero change
  points; 4.11 has no ladder at all, its real gap is an uncalled `precursor_for`, so PRIOR is
  unreachable.
- The RT-to-Forecaster one-way handoff, first lock and context manifest exist with V2 workmode
  schemas and produced the prior reduced run's files; they are re-fed, never rebuilt.

## 5. THE SECOND ROUND: THREE WIRING PERSONAS (in flight at the time of writing)

Spawned as each search landed, in worktrees cut from `bfb4e43`, under D84 push spots, arm A_MEMORY:

- `persona/s121-wire-outputs-staging`: `load_principal_artifact` calls `validate_output_bundle_dir`;
  a read-back driver and CLI chain load and attach; the report at the choke point carries the
  crosswalk table; the handoff machinery re-fed from the bundle by reuse.
- `persona/s121-wire-knowledge-gates`: the 63 KEEP files and the seed memory registered in the
  EXISTING manifest (one kind added for Python source), the a_memory_overlay layers rebound from
  the wrong-data package to `A_MEMORY_SEED_20260902.json`, the knowledge receipt produced FROM the
  existing pipeline, the read gate wired through `bind_principal_knowledge_use`, the sealed-absence
  proof (the one new producer, modelled on `brain_view.context_leak`), the spawn gate in `emit()`
  with HONEST fixtures, the crosswalk's stale bound flag read off the registry.
- `persona/s121-wire-clocks-windows`: the seven clocks by registry id on rows and GroupDelivery by
  reuse, F-20's `emitted_at_recv_ns` at retention (folded in: a lifecycle row without its own
  availability instant is a row missing its feature-availability clock), `activity_since` on event
  anchors with the fixed-seconds blocks removed, 4.16 response-matured with the ladder retired,
  `precursor_for` wired, `RecognitionLabel` given its caller.

## 6. WHAT IS MINE AT MERGE (cross-persona call sites)

Staging calls the knowledge read gate; `REQUIRED_CUTOFF_KEYS` gains the model-evaluation clock; the
registry's seven clock layers repoint to the producing code through the rebind script; the
crosswalk's producer records follow any moved symbol. Then F-22 onward, the enforcement lines of
D82-D86 restated with shas, this section 9, the drop-in, the push.

## 7. STANDING RULES THAT BIT THIS SESSION

- A worktree cut without a base-ref setting branches from the repo default branch. Cut them by hand
  from the drop-in tip.
- A rate limit kills every background persona at once. D84: push after every commit. The first
  application recovered all twelve committed slices and salvaged two uncommitted ones.
- Search before building (S116, again). The clocks existed in four places; the knowledge pipeline
  existed end to end; the read gate existed. Every "build" item of the drop-in was a wiring item.
- A static flag that mirrors a registry fact rots the moment the registry changes; compute it.
- `plant_status.py` still expects branch `claude/kalshi-agents-coordinator-guard-sg0n15` (the walk's S114 drop-in) and reads FAIL on every Frankie-branch session since S115, beside the briefings-audit backlog (23 of 27). Both pre-existing, both left as they are: an andon expectation is not changed silently, and the walk and the Frankie line share one board. A decision on a per-branch expectation belongs to Greg.

## 8. NOT DONE THIS SESSION

The Sunday re-run on the new code (needs Greg and the box; the A-memory workflow); the spawn; the
reveal; Monday. The removal of the retired A-clean overlay, profiles and workflow (D60 discussion).
Key rotation stays deferred until the walk ends.

## 9. THE CLOSE (completed when the wiring lands)

Pending: merge shas of the three wiring branches, the cross-persona call-site commits, the final
test count, the final tip.
