# FRANKIE WINDOWS AND CLOCKS: THE D60 PACKET AND THE BUILD SPEC (S121, 2026-09-02)

**What this document is.** Item one of `DROP_IN_S121.md`: every hardcoded window, ladder and
horizon still in the raw-MBO path, measured with file:line and consumers (section 1); the seven
causal clocks the registry requires, each with its producer today or `NO_PRODUCER_FOUND`, verified
by execution (section 2); the build specification that replaces the fixed intervals with values
derived from actual events on named clocks (section 3); the implementation choices with the default
taken for each and why (section 4); and every command run, so a reader can reproduce each number
(section 5). Worktree `persona/s121-windows`, cut from `ac4c373`; baseline suite 1,483 passed,
859 subtests, before any change.

**Why it is a spec and not an options packet.** The item was opened as a D60 discussion. Greg
ruled on it during this session, as relayed by the coordinator, verbatim:

> "hardcoded windows we do not want these! Again i say it! All times are derived by their actual
> events, prebirth findings, h times if we don't find them in prebirth, etc all by using the
> clocks we made just for this reason. There should be zero hard coded time intervals for
> anything."

and then: *"The clocks need to be wired into Frankie."* That closes the D60 discussion for the
fixed-interval DERIVED blocks: the removal of the fixed-seconds `activity` / `activity_full`
blocks from the published member row is ordered by Greg, which is what D60 requires before
anything is dropped. Nothing raw is removed: every record, field and book level still passes
through (D60, D61, D81). Only blocks whose definition is a fixed number of seconds go, and each is
named in the removal table in section 3.

The ruling reached this packet relayed, not first-hand. It is quoted as relayed and the packet is
built on it; if the relay is wrong, section 3 is the part to strike and sections 1, 2 and 5 stand
on their own as the measured record.

Section 2 of the calculation contract (`agents/frankie_native_raw_mbo_calculation_contract_20260828.md`)
already says what the clocks must be: *"event time, first-component receive time, F_LAST
availability time, and decision/as-of time as separate clocks"*, *"The first lawful knowledge
time for a completed group is its F_LAST receive time"*, *"The first lawful later recognition is
continuous H+N, where N is the observed elapsed time on the named clock."* Feed inventory section
12 closes with *"No fixed hourly windows or answer-derived PRIOR/T0/H."* The code below is
measured against those sentences.

---

## 1. What is hardcoded, exactly

Every fixed interval in the path, found by `grep` (section 5, commands A3 to A5) and read in
context. Paths are repo-relative. "Bytes per member row" is measured on the smallest fixture the
tests use (`tests/test_native_full_capture_adapter.py::rec`, one record, one group) and on a
three-record, two-group fixture; the production share on the delivered Sunday ledger was NOT
measured here because that ledger is not in this worktree - `book_full` is 93.47% of its bytes
(D76), so the real share of the activity blocks is far smaller than the fixture share. The command
that measures it on a delivered ledger is A8 in section 5.

### 1.1 The table

| # | Name and values | Defined at | Consumers (file:line) | Feeds | Class | Bytes per member row (fixture) |
|---|---|---|---|---|---|---|
| 1 | `ACTIVITY_WINDOWS_S = (1, 5, 20, 60, 300)` seconds | `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py:51` (HASH-LOCKED, D61) | adapter `:281` (one `_RollingActivityWindow` per window in `InstrumentBook.__init__`), `:544` (`_append_activity` keeps rows back to `now - max(...)` = 300 s), `:690` (rebuild on receive-clock regression), `:696-700` (`rolling_activity` snapshot per window), `:726` (`event_frame["activity"]`), `:739` (`checkpoint_state["activity"]`); `frankie_raw_mbo_benchmark/native_full_capture_adapter.py:53` (import), `:187-189` (`frame["activity_full"]` per window), `:200-208` (`_window_extras`); `mbo_resume_state.py:19` (import), `:300-307` (rebuilds `_activity_windows`, expires each at `activity_last_now_ns - seconds`); `research/ng_exhaustion_step1_october_shards_20260824.py:34` (import), `:48`, `:166-175` (`_book_state` dumps each window's internals), `:350` | member row `activity` (5 blocks x 12 fields) and `activity_full` (5 x 3); registry group `microstructure_mechanics`, feed inventory section 7 ("adds/cancels/modifies/replaces/trades/fills by side", "churn and queue turnover"); contract 4.3/4.7/4.8 read the group's own actions, not these blocks | FIXED_SECONDS_LADDER. **Replaced by this build, slice (b).** | fixture 1: `activity` 1,650 B + `activity_full` 490 B of a 4,911 B frame (43.6%); fixture 2 group 1: 1,766 + 582 of 6,131 B (38.3%) |
| 2 | `WARMUP_SECONDS = max(ACTIVITY_WINDOWS_S)` = 300 | `research/ng_exhaustion_step1_october_shards_20260824.py:48` | `:143` (plan body), `:224` (default argument), `:350` (boundary equality threshold), `:382`, `:436` (acceptance check); `BOUNDARY_METHOD` `:50` names it ("...AFTER_300S_WARMUP") | the October shard boundary PROOF: continued-vs-fresh adapter state equality once the longest window has filled. Not on any row | DERIVED FROM #1. Not in this build: the proof is about the locked adapter's own windows, which the locked file keeps | none |
| 3 | `REORDER_TOLERANCE_SECONDS = 60` | same file `:49` | `:144` | shard plan | operational tolerance of the shard planner, not a measurement window. Not in this build | none |
| 4 | `HORIZON_SETS`: `"a-arm-h1": (1 s, 10 s, 60 s)` FROZEN (run 33605852433); `"a-arm-h2": (1 ms, 10 ms, 100 ms, 1 s, 10 s, 60 s)` | `frankie_raw_mbo_benchmark/native_response.py:146-166` | `native_response.py:190-198` (`horizons_for_version`), `:432-438` (a registered version refuses other horizons), `:583` (`open_track`: one `HorizonObservation` per horizon, `due_recv_ns = first_lawful + horizon`), `:586-588` (`advance` matures at `recv_ns >= due`); `native_calculation_runner.py:283-284` (parameters), `:349-352`; `native_a_arm_launch.py:455-456` (`horizons_for_version("a-arm-h2")`, `"a-arm-h2"` - a file this build may not edit); `native_replay_driver.py:643-649` (`response.advance(second * NS)` on every completed second, occasion `HORIZON_MATURED`) | lifecycle ledger `response` rows (`horizon_ns`, `due_recv_ns`, `read_recv_ns`, `read_lateness_ns`, `reading_resolution`), `response_at_risk_table` (`horizon_ns`, `horizon_version`), 4.16 stratum subfamily `horizon=<ns>|horizon_version=<v>`, summary `horizons_ns`; contract 4.16 "versioned fixed H+N reporting horizons" | FIXED_SECONDS_LADDER. **Replaced by this build, slice (c).** | none on the member row; six `HorizonObservation` records per 4.16 track under a-arm-h2 |
| 5 | 4.11 `HORIZON = "H+N"` | `native_recognition.py:35` | `:84-97` (`record_call` classifies PRIOR / T0 / H+N by comparing the observed instant with `birth_recv_ns` and stores it), `:154-159` (`horizon_delay_ns` = recognition - birth), `native_candidate_adapter.py:251-252, 302-311` (the call is made at `available_second * NS`) | 4.11 recognition records in the `episode` lifecycle rows | **NOT A LADDER.** `H+N` is a label; N is already the observed elapsed time. The handoff's "4.11's H ladder" conflates 4.11 with the two `HORIZON_MATURED` occasions in the driver, which belong to 4.16 (`:648`) and 4.7 (`:1061`). What 4.11 does carry: N at SECOND granularity on the candidate lane's `available_second`, not on an F_LAST receive; and PRIOR is unreachable because no `precursor_for` callback is wired anywhere (A9). **Slice (d) stamps the clocks and the F_LAST cutoff of emission; it removes nothing.** | none |
| 6 | `DEFAULT_REPLACEMENT_HORIZON_NS = 60 s` | `native_absorption.py:49` | `:220` (`AbsorptionCalculator.__init__` default), used by `note_same_side_add` | 4.8 replacement attribution (lifecycle `absorption` rows); its docstring ties it to #7 | FIXED_SECONDS_HORIZON. Not in this build's ordered list; the derived replacement is named in section 3.5 | none |
| 7 | 4.7 replenishment `horizon_ns` = 60 s | `native_a_arm_launch.py:447` (`replenishment_horizon_ns=60_000_000_000`); required by `native_calculation_runner.py:280, 340` | `native_replenishment.py:311-317`, `:328` (`causal_cutoff = episode open + horizon`), `:520-524` (`advance` emits RESTORED / NEVER_RESTORED at `open + horizon`); driver `:1058-1062` (`replenishment.advance(recv_ns)`, occasion `HORIZON_MATURED`) | 4.7 rows (`horizon_ns`, outcome at the horizon; `CENSORED_*` at boundaries) | FIXED_SECONDS_HORIZON. Not in this build's ordered list. Note that restoration itself is already event-observed (`first_restoration_recv_ns`); the fixed horizon only decides NEVER_RESTORED and when to emit | none |
| 8 | `DEFAULT_MIRROR_DISTANCE_BOUND_NS = 60 s` | `native_calculation_runner.py:88` | `:281` (parameter), `:330-336` (`MirrorMatcher(distance_bound=...)`); the runner's own comment: "PROVISIONAL AND DECLARED AS SUCH" | 4.4 mirrored pairings | FIXED_SECONDS_BOUND. Not in this build's ordered list | none |
| 9 | Candidate detector constants: `ROLL_WINDOW = 20`, `PEAK_QUANTILE = 0.85`, `LOCAL_RADIUS = 5` s, `REFRACTORY = 45` s, `BASELINE_LAG = 9`, `BASELINE_START = 30`, `BASELINE_POINTS = 21`, `DAY_SECONDS = 86400` (a COUNT of observations, `:221`), `warmup_seconds = 900` (`:222`), `min_threshold_observations = 600` (`:223`, a COUNT) | `native_candidate.py:70-76, 98, 221-223`; driver defaults `native_replay_driver.py:333-334` | `native_candidate.CausalPeakDetector` throughout; `native_replay_driver.py:568-574` (`_new_detector`) | the D66 candidate unit: `available_second = event_second + LOCAL_RADIUS` is the detection lag every 4.11 recognition carries; the refractory and the trailing bar decide which seconds become candidates | FROZEN-DETECTOR PORT ("Ported verbatim from ng_exhaustion_chain_canonical_table_20260817", `:69`): legacy observables by definition, the same class as #11. Changing them changes what a candidate IS and breaks reconciliation with the frozen census. Not in this build; named so the gap is declared | none |
| 10 | `PERSIST_SECONDS = 3` | `native_candidate_adapter.py:61`, default `:216`, stored `:225` | `:409` (`reversing = opposite_run >= persist_seconds`) | 4.10 REVERSAL entry; 4.12 stage filing | FROZEN-DETECTOR PORT ("The frozen PERSIST"). Not in this build | none |
| 11 | `native_roll20.DEFAULT_WINDOW = 20` and its consumers | `native_roll20.py:40` | `:186`, `:226`, `:261` (crosswalk hash), `native_flow_substrate.py:256, 520, 596` (`window_seconds`), `native_replay_driver.py:800` (`_flow_at`) | registry layer `legacy_per_second_roll20` (group `legacy_observable_crosswalk`, CAUSAL_STREAM_REQUIRED), 4.0 substrate, 4.12 signed flow, 4.16 flow channel | **LEGACY OBSERVABLE BY DEFINITION.** roll20 IS the 20-second rolling signed flow of the frozen census; the 20 is its name, not a tuning. Kept | none (feeds lifecycle `flow_substrate` rows) |
| 12 | `MAX_DENSE_SPAN = 40 * 86400` | `native_roll20.py:42` | dense-series guard | refuses a series wider than forty days as a unit error | a guard, not a window. Excluded | none |
| 13 | `DEFAULT_EVERY_RECORDS = 250_000`, `DEFAULT_EVERY_SECONDS = 600.0`; `KEY_SAMPLE_EVERY = 97` | `periodic_checkpointer.py:40-41`; `native_row_sink.py:36` | checkpoint cadence; per-key byte sampling rate | operational cadence and a sampling stride; neither measures the market | operational, not measurement. Excluded | none |
| 14 | Exchange instants: reopen 17:00 CT, close 16:00 CT, settlement 14:28-14:30 ET | `native_session.py:87` and the functions below it | `SessionRule` (`native_replay_driver.py:117-134`) | session phase and continuity segment | INSTANTS from the CME calendar (exchange facts), not intervals. Excluded, and one of them - the reopen - is an ANCHOR the new windows use (section 3.2) | none |

### 1.2 What the table says

1. Two fixed ladders reach the artifact Frankie receives: #1 on every member row and #4 on every
   4.16 track. Everything else is either derived from #1 (#2), a fixed horizon that gates ONE
   section's emission (#6, #7, #8), a frozen-detector constant whose value defines the candidate
   unit (#9, #10), or a legacy observable whose number is its definition (#11).
2. The one interval the handoff attributed to 4.11 does not exist in code. 4.11 already measures
   N as observed elapsed time. Its remaining distance from the contract is granularity (a second
   boundary rather than the F_LAST receive at which the traversal actually emitted the call) and
   the absence of any prebirth precursor.
3. `ACTIVITY_WINDOWS_S` cannot be edited: D61 pins the adapter's bytes and other pipelines'
   provenance rests on the hash (`test_checked_in_finalizer_lock_pins_every_executable_byte`).
   Its windows keep being computed inside the locked file on every record. The build removes them
   from the PUBLISHED row and adds event-anchored windows in the wrapper; `mbo_resume_state` keeps
   rebuilding the locked file's windows for its exact round-trip, because that state belongs to
   the locked adapter and the round-trip check (`restored != dict(state)`) is exact.

---

## 2. The seven clocks, one by one

The registry group `causal_clocks` (`agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json`,
policy `CAUSAL_STREAM_REQUIRED`, activation `EACH_F_LAST_CUTOFF`, carrier MEMBER per
`native_causal_stream.LAYER_CARRIERS`) holds exactly seven entries, each with a one-line
description and the feed inventory as its only source path (A6). Feed inventory section 12 lists
eight items: the seven below plus "Onset time, withheld until allowed", which is the sealed answer
clock and is not a producer question.

Verified by execution (A7): a driver-built member row carries a `clocks` object with FIVE fields,

```
row['clocks'] = {"decision_ts_recv_ns": 1633352400000150000, "f_last_ts_recv_ns": 1633352400000150000,
                 "first_component_ts_event_ns": 1633352400000000000, "first_component_ts_recv_ns": 1633352400000150000,
                 "first_lawful_availability_ns": 1633352400000150000}
row['decision_basis'] = REPLAY_EARLIEST_LAWFUL_AVAILABILITY
```

and a `GroupDelivery` receipt carries FOUR, validated by `GROUP_CLOCK_KEYS`
(`native_ingestion_layer_registry.py:144-146`, exact-key check at `:444-450`):

```
GroupDelivery.first_lawful_availability_ns = 1633352400000150000
GroupDelivery.receipt['clocks'] = {"availability_time_ns": 1633352400000150000, "decision_time_ns": 1633352400000150000,
                                   "event_time_ns": 1633352400000000000, "receive_time_ns": 1633352400000150000}
delivered_layers for causal_clocks group: ['clock_event_time', 'clock_receive_time', 'clock_event_known_by',
   'clock_feature_availability', 'clock_prospective_discovery_confirmation', 'clock_model_evaluation', 'clock_lock_time']
```

The receipt names all seven layer ids as delivered, with the sha256 of the member line as each
one's evidence (`native_causal_stream.py:484-489`). No field on the row is keyed by any of the
seven ids (`git grep known_by` finds the registry, the execution gate's surface list and nothing
in `native_*`, A9). Delivered-by-hash and findable-by-name are different facts; the crosswalk
needs the second.

| Layer id | Feed inventory 12 / contract meaning | Produced today? Producer and carrier | How it is produced in real time (verified against the code) |
|---|---|---|---|
| `clock_event_time` | Event time: when the exchange says the record happened (contract 2 "event time"; 4.5 "event-to-receive latency per component") | YES, unnamed. Per component `raw_actions[].ts_event_ns` (adapter `public_dict`); group `ts_event_ns` = the F_LAST component's (`event_frame`, adapter `:713`); `clocks.first_component_ts_event_ns` (`native_clocks.py:200`); receipt `event_time_ns` | `ts_event` on every DBN record, as received; nothing to compute. The group carries first and F_LAST component event times |
| `clock_receive_time` | Receive time: when the feed handler stamped the record (contract 2 "receive time"; the package's causal clock, `CAUSAL_CLOCK = "ts_recv_ns"` in nine modules, A9) | YES, unnamed. Per component `raw_actions[].ts_recv_ns`; group `ts_recv_ns` (F_LAST's); `clocks.first_component_ts_recv_ns`, `clocks.f_last_ts_recv_ns`; receipt `receive_time_ns` | `ts_recv` on every record. The stream is ordered on it (`native_causal_stream.py:467-471` refuses a backwards move) |
| `clock_event_known_by` | The instant a completed group is first lawfully knowable: its F_LAST receive (contract 2, sentence one of the second paragraph) | YES, under another name. `clocks.f_last_ts_recv_ns` = `clocks.first_lawful_availability_ns` (`native_clocks.py:170-176, 201-202`); receipt `availability_time_ns`; `GroupDelivery.first_lawful_availability_ns` (the cutoff every sidecar row is gated on, `native_causal_stream.py:464, 473-474`) | The receive time of the record carrying `F_LAST`, taken when it arrives. A group is visible to the principal at that instant and never before (D81) |
| `clock_feature_availability` | 4.5: "the first lawful availability of every derived feature"; feed inventory 9 "Feature-availability timestamps" | PARTIAL. One stamp per member row (`first_lawful_availability_ns`): every derived block on the row (`structure`, `book_full`, `book_regime`, ...) is computed at group close on the causal prefix ending at that F_LAST. Lifecycle rows have NO uniform stamp; `native_causal_stream.lifecycle_availability` (`:170-190`) resolves each by a declared rule (`SECOND_COMPLETE`, `CANDIDATE_AVAILABLE_SECOND`, `OWN_CLOCK`, `NO_OWN_CLOCK`); the mirror rows name no clock and are withheld and counted (F-20). No field is named by this id | In RT, the wall-clock instant at which the derived feature finished computing on the prefix, which is at or after the F_LAST receive. In replay there is no such instant to observe, so the earliest lawful one (F_LAST receive) is adopted and the BASIS travels on the record, exactly as `decision_basis` does for the decision clock (`native_clocks.py:113-131`) |
| `clock_prospective_discovery_confirmation` | The cutoff at which 4.11 first emits PRIOR / T0 / H+N for a candidate; feed inventory 11 "An instance created only after D discovery is a recognition instance, not a prior-prediction instance" | PARTIAL, lifecycle only. `CandidateRecognition.recognized_recv_ns` (`native_recognition.py:84-97`) set by `record_call` inside `CandidateEpisodeTracker.open` (`native_candidate_adapter.py:302-311`) at `available_second * NS`; reaches the `episode` lifecycle rows (`recognition_outcome` at open, `recognition` sub-object at close). Nothing on the member row; nothing keyed by this id | TWO instants, and the code records only the first: (i) the knowable instant, `available_second` (the spike at t is a local maximum only once t + LOCAL_RADIUS has arrived); (ii) the F_LAST cutoff at which the traversal actually emitted the call - `_advance_candidates` runs inside `_on_group` for the group that closed (`native_replay_driver.py:1019`), so the emission cutoff is that group's receive time. The build carries both, named. In RT they are the same event seen from the candidate lane and from the group stream |
| `clock_model_evaluation` | The cutoff at which the principal is invoked (feed inventory 12 "Model evaluation time"; contract 2 "decision/as-of time") | PARTIAL, by convention. `clocks.decision_ts_recv_ns` with `decision_basis = REPLAY_EARLIEST_LAWFUL_AVAILABILITY` (`native_clocks.py:113-131`): a replay has no decision to observe, so F_LAST is adopted and the basis says so. The REAL evaluation cutoff exists only in the driver's `cutoff` dict when `cadence.should_invoke` fires (`native_replay_driver.py:1063-1088`: `group_index`, `recv_ns`, `first_lawful_availability_ns`, ...) and in the spawn request `native_staging.stage_spawn_request` writes from it (`native_staging.py:61-112`, `REQUIRED_CUTOFF_KEYS` `:41-48`). On the fixture no cutoff fired (`invocation_cutoffs: []`, A7). Not on any row; not keyed by this id | The receive-clock instant of the group at whose cutoff the principal is (staged to be) invoked. In RT it is the moment the spawn is requested; the staged request is the record of it. The build stamps it on the member row of the cutoff group and adds it to the cutoff dict; `native_staging` is owned by the coordinator, so section 3.4 carries the exact wiring note |
| `clock_lock_time` | The cutoff at which the principal writes FIRST_LOCK (feed inventory 11 "Later outcome reveal after predictions and locks freeze") | **NO_PRODUCER_FOUND.** `RT_FIRST_LOCK.json` (`a_clean_rt_replay_20260828.py:430-454`) carries hashes, record counts and flags (`first_lock_frozen`, `amendment_allowed`, `forecaster_started`) and NO time field; `corrected_a_arm_execution_gate.validate_first_lock_and_freeze` (`:495-517`) checks hash and run identity, never a clock. The registry's output layer `output_first_locks_and_no_locks` is one of the ten outputs the S120 spawn produced none of | The receive-clock cutoff of the group at which the principal writes his FIRST_LOCK entry, stamped by HIM in his own ledger (the output-ledgers persona owns that ledger; section 3.4 carries the note). The traversal cannot produce this clock: it is the principal's act, not the tape's |

Two structural facts fall out of the table. First, five of the seven clocks belong to the stream
and can be produced on every member row and every `GroupDelivery` from what the traversal already
knows; the other two are acts of the spawn and of the principal and must be stamped where those
acts happen. Second, the registry's delivery receipt is validated against an exact four-key clock
object (`GROUP_CLOCK_KEYS`) in a module this build may not edit, so the seven named fields must
ride on the row and on `GroupDelivery` as a separate object, not inside `receipt["clocks"]`.

---

## 3. The build spec

Written in slice 2 of this packet (see the commit log).

## 4. Implementation choices

Written in slice 2 of this packet (see the commit log).

---

## 5. Verification appendix

Every command below was run from the worktree root (`git rev-parse --show-toplevel`), on
`persona/s121-windows` at `ac4c373` unless a later slice says otherwise. Outputs are quoted as
printed, trimmed only where marked `[...]`. Temporary files come from `tempfile` and are never
named (D34).

### A1. Branch, tip, clean tree, baseline suite

```
$ git rev-parse --abbrev-ref HEAD && git log --oneline -1 && git status --short | wc -l
persona/s121-windows
ac4c373 Regenerate the document inventory after the salvaged draft was added
0
$ python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests -q -x --no-header -p no:cacheprovider 2>&1 | tail -1
1483 passed, 859 subtests passed in 59.94s
```

### A2. The activity blocks on the test fixtures (section 1, row 1)

```
$ python3 - <<'PY'
import json, sys
sys.path.insert(0, ".")
from research.kalshi.frankie_raw_mbo_benchmark.native_full_capture_adapter import FullCaptureAdapter
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import F_LAST, V4MboAdapter, ACTIVITY_WINDOWS_S
def rec(*, seq, order_id, action="A", side="B", size=5, price=3_500_000_000, last=True, flags=None, ts=1_000_000_000):
    return {"instrument_id": 42, "publisher_id": 1, "channel_id": 0, "order_id": order_id, "action": action,
            "side": side, "price": price, "size": size, "flags": (F_LAST if last else 0) if flags is None else flags,
            "sequence": seq, "ts_event": ts, "ts_recv": ts + 150_000, "ts_in_delta": 0,
            "source_dbn_object": "20211004.dbn", "source_dbn_sha256": "0" * 64}
def drive(adapter, records):
    frames = []
    for r in records:
        frame, _legacy = adapter.apply(r, raw_symbol="NGX1", source_dbn_object=r["source_dbn_object"], source_dbn_sha256=r["source_dbn_sha256"])
        if frame is not None: frames.append(frame)
    return frames
def jb(obj): return len(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())
print("ACTIVITY_WINDOWS_S =", ACTIVITY_WINDOWS_S)
records = [rec(seq=1, order_id=11, ts=1_000)]
kept = drive(FullCaptureAdapter(), records)[0]; base = drive(V4MboAdapter(), records)[0]
print("frame top-level key count (wrapper):", len(kept), " (base):", len(base))
print("activity keys:", list(kept["activity"].keys()))
print("activity['1'] keys:", list(kept["activity"]["1"].keys()))
print("activity_full['1'] keys:", list(kept["activity_full"]["1"].keys()))
print("bytes activity:", jb(kept["activity"]), "activity_full:", jb(kept["activity_full"]), "frame:", jb(kept), "book_full:", jb(kept["book_full"]))
recs2 = [rec(seq=1, order_id=11, ts=1_000, last=False), rec(seq=2, order_id=12, side="A", price=3_510_000_000, ts=1_500),
         rec(seq=3, order_id=0, action="T", side="B", size=2, price=3_510_000_000, ts=2_000_000_000)]
for i, f in enumerate(drive(FullCaptureAdapter(), recs2)):
    print(f"group {i}: bytes activity {jb(f['activity'])}, activity_full {jb(f['activity_full'])}, frame {jb(f)}")
PY
ACTIVITY_WINDOWS_S = (1, 5, 20, 60, 300)
frame top-level key count (wrapper): 24  (base): 20
activity keys: ['1', '5', '20', '60', '300']
activity['1'] keys: ['event_count', 'action_count', 'action_qty', 'action_side_qty', 'trade_buy_aggressor_qty', 'trade_sell_aggressor_qty', 'trade_aggressor_imbalance', 'add_cancel_churn', 'top_level_add_qty_derived', 'top_level_cancel_qty_derived', 'priority_lost_modify_count', 'missing_reference_count']
activity_full['1'] keys: ['action_side_count', 'top_level_qty_by_action', 'receive_order_clean']
bytes activity: 1650 activity_full: 490 frame: 4911 book_full: 1007
group 0: bytes activity 1700, activity_full 535, frame 6537
group 1: bytes activity 1766, activity_full 582, frame 6131
```

### A3. Every fixed interval, by grep

```
$ grep -rn "HORIZON\|LADDER\|_S = \|_S=\|WINDOW\|1, 5, 20, 60, 300\|WARMUP" --include=*.py research/kalshi/frankie_raw_mbo_benchmark/*.py research/ng_exhaustion_mbo_v4_state_adapter_20260820.py research/ng_exhaustion_step1_october_shards_20260824.py | grep -v tests/
[... 80 lines; the hits that are intervals are the rows of table 1.1; the rest are string labels
     (`HORIZON = "H+N"`, `WINDOW_LONG`, `LADDER_SCOPE`, `CENSORED_HORIZON`, `WINDOW_INCOMPLETE`) ...]
$ grep -n "_NS = \|_NS=\|\* NS_PER_S\|\* 1_000_000_000\|1_000_000_000 \*\|_SECONDS = \|_MS = " research/kalshi/frankie_raw_mbo_benchmark/*.py | grep -v tests/
research/kalshi/frankie_raw_mbo_benchmark/mbo_resume_state.py:307:                window.expire_before(int(book._activity_last_now_ns) - seconds * 1_000_000_000)
research/kalshi/frankie_raw_mbo_benchmark/native_absorption.py:49:DEFAULT_REPLACEMENT_HORIZON_NS = 60 * 1_000_000_000
research/kalshi/frankie_raw_mbo_benchmark/native_calculation_runner.py:88:DEFAULT_MIRROR_DISTANCE_BOUND_NS = 60 * 1_000_000_000
research/kalshi/frankie_raw_mbo_benchmark/native_candidate.py:98:DAY_SECONDS = 86400
research/kalshi/frankie_raw_mbo_benchmark/native_candidate_adapter.py:61:PERSIST_SECONDS = 3
research/kalshi/frankie_raw_mbo_benchmark/native_response.py:143:NS_PER_MS = 1_000_000
research/kalshi/frankie_raw_mbo_benchmark/native_response.py:150:    "a-arm-h1": (1 * NS_PER_S, 10 * NS_PER_S, 60 * NS_PER_S),
research/kalshi/frankie_raw_mbo_benchmark/native_response.py:162:        1 * NS_PER_S,
research/kalshi/frankie_raw_mbo_benchmark/native_response.py:163:        10 * NS_PER_S,
research/kalshi/frankie_raw_mbo_benchmark/native_response.py:164:        60 * NS_PER_S,
research/kalshi/frankie_raw_mbo_benchmark/periodic_checkpointer.py:41:DEFAULT_EVERY_SECONDS = 600.0
[... conversions (`* NS_PER_SECOND` on a variable) omitted: they are unit changes, not intervals ...]
```

### A4. Exact line numbers for the table

```
$ grep -n "^ACTIVITY_WINDOWS_S" research/ng_exhaustion_mbo_v4_state_adapter_20260820.py
51:ACTIVITY_WINDOWS_S = (1, 5, 20, 60, 300)
$ grep -n "ACTIVITY_WINDOWS_S\|rolling_activity\|\"activity\"" research/ng_exhaustion_mbo_v4_state_adapter_20260820.py
51:ACTIVITY_WINDOWS_S = (1, 5, 20, 60, 300)
281:        self._activity_windows = {seconds: _RollingActivityWindow() for seconds in ACTIVITY_WINDOWS_S}
544:        cutoff = msg.ts_recv_ns - max(ACTIVITY_WINDOWS_S) * 1_000_000_000
684:    def rolling_activity(self, now_ns: int) -> dict[str, Any]:
690:            self._activity_windows = {seconds: _RollingActivityWindow() for seconds in ACTIVITY_WINDOWS_S}
696:        for seconds in ACTIVITY_WINDOWS_S:
726:            "activity": self.rolling_activity(now_ns),
739:            "activity": self.rolling_activity(now_ns),
$ grep -n "^WARMUP_SECONDS\|^REORDER_TOLERANCE_SECONDS\|^BOUNDARY_METHOD" research/ng_exhaustion_step1_october_shards_20260824.py
48:WARMUP_SECONDS = max(ACTIVITY_WINDOWS_S)
49:REORDER_TOLERANCE_SECONDS = 60
50:BOUNDARY_METHOD = "CONTINUED_VERSUS_FRESH_COMPLETE_V4_STATE_AFTER_300S_WARMUP"
$ grep -n "^HORIZON_SETS\|\"a-arm-h1\"\|\"a-arm-h2\"\|^def horizons_for_version" research/kalshi/frankie_raw_mbo_benchmark/native_response.py
146:HORIZON_SETS: dict[str, tuple[int, ...]] = {
150:    "a-arm-h1": (1 * NS_PER_S, 10 * NS_PER_S, 60 * NS_PER_S),
158:    "a-arm-h2": (
190:def horizons_for_version(horizon_version: str) -> tuple[int, ...]:
$ grep -n "replenishment_horizon_ns=\|response_horizons_ns=\|response_horizon_version=" research/kalshi/frankie_raw_mbo_benchmark/native_a_arm_launch.py
447:        replenishment_horizon_ns=60_000_000_000,
455:        response_horizons_ns=horizons_for_version("a-arm-h2"),
456:        response_horizon_version="a-arm-h2",
$ grep -n "^ROLL_WINDOW\|^PEAK_QUANTILE\|^LOCAL_RADIUS\|^REFRACTORY\|^BASELINE_LAG\|^BASELINE_START\|^BASELINE_POINTS\|^DAY_SECONDS\|warmup_seconds: int = \|min_threshold_observations: int = \|threshold_observations: int = " research/kalshi/frankie_raw_mbo_benchmark/native_candidate.py
70:ROLL_WINDOW = 20
71:PEAK_QUANTILE = 0.85
72:LOCAL_RADIUS = 5
73:REFRACTORY = 45
74:BASELINE_LAG = 9
75:BASELINE_START = 30
76:BASELINE_POINTS = BASELINE_START - BASELINE_LAG
98:DAY_SECONDS = 86400
221:        threshold_observations: int = DAY_SECONDS,
222:        warmup_seconds: int = 900,
223:        min_threshold_observations: int = 600,
$ grep -n "^PERSIST_SECONDS\|persist_seconds: int = " research/kalshi/frankie_raw_mbo_benchmark/native_candidate_adapter.py
61:PERSIST_SECONDS = 3
216:        persist_seconds: int = PERSIST_SECONDS,
$ grep -n "candidate_warmup_seconds: int = \|candidate_min_observations: int = \|window = native_roll20.DEFAULT_WINDOW\|HORIZON_MATURED" research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py
333:        candidate_warmup_seconds: int = 900,
334:        candidate_min_observations: int = 600,
648:                occasion="HORIZON_MATURED",
800:        window = native_roll20.DEFAULT_WINDOW
1061:            occasion="HORIZON_MATURED",
$ grep -n "^DEFAULT_WINDOW\|^MAX_DENSE_SPAN" research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py
40:DEFAULT_WINDOW = 20
42:MAX_DENSE_SPAN = 40 * 86400
$ grep -n "^DEFAULT_EVERY_RECORDS\|^DEFAULT_EVERY_SECONDS" research/kalshi/frankie_raw_mbo_benchmark/periodic_checkpointer.py
40:DEFAULT_EVERY_RECORDS = 250_000
41:DEFAULT_EVERY_SECONDS = 600.0
$ grep -n "^DEFAULT_REPLACEMENT_HORIZON_NS" research/kalshi/frankie_raw_mbo_benchmark/native_absorption.py
49:DEFAULT_REPLACEMENT_HORIZON_NS = 60 * 1_000_000_000
$ grep -n "^DEFAULT_MIRROR_DISTANCE_BOUND_NS" research/kalshi/frankie_raw_mbo_benchmark/native_calculation_runner.py
88:DEFAULT_MIRROR_DISTANCE_BOUND_NS = 60 * 1_000_000_000
```

### A5. The consumers of the locked adapter's windows outside the locked file

```
$ grep -rn "ACTIVITY_WINDOWS_S\|_activity_windows" research/kalshi/frankie_raw_mbo_benchmark/*.py research/ng_exhaustion_step1_october_shards_20260824.py
research/kalshi/frankie_raw_mbo_benchmark/mbo_resume_state.py:19:    ACTIVITY_WINDOWS_S,
research/kalshi/frankie_raw_mbo_benchmark/mbo_resume_state.py:300:        book._activity_windows = {seconds: _RollingActivityWindow() for seconds in ACTIVITY_WINDOWS_S}
research/kalshi/frankie_raw_mbo_benchmark/native_full_capture_adapter.py:53:    ACTIVITY_WINDOWS_S,
research/kalshi/frankie_raw_mbo_benchmark/native_full_capture_adapter.py:188:            str(seconds): self._window_extras(book, seconds) for seconds in ACTIVITY_WINDOWS_S
research/ng_exhaustion_step1_october_shards_20260824.py:34:    ACTIVITY_WINDOWS_S,
research/ng_exhaustion_step1_october_shards_20260824.py:48:WARMUP_SECONDS = max(ACTIVITY_WINDOWS_S)
research/ng_exhaustion_step1_october_shards_20260824.py:166:    for seconds in ACTIVITY_WINDOWS_S:
$ grep -rn "checkpoint_state(" --include=*.py research/ | grep -v "def checkpoint_state"
research/test_ng_exhaustion_mbo_v4_state_adapter_20260820.py:140: [...]
research/test_ng_exhaustion_mbo_v4_state_adapter_20260820.py:152: [...]
research/test_ng_exhaustion_mbo_v4_state_adapter_20260820.py:162: [...]
research/test_ng_exhaustion_mbo_v4_state_adapter_20260820.py:238: [...]
research/kalshi/frankie_raw_mbo_benchmark/chat_packet_seam.py:192:    full_state = books[instrument_id].checkpoint_state(
```

### A6. The registry's causal_clocks group

```
$ python3 - <<'PY'
import json
d = json.load(open("research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json"))
g = next(x for x in d["groups"] if x["group_id"] == "causal_clocks")
print({k: v for k, v in g.items() if k != "entries"})
for e in g["entries"]: print(e["layer_id"], "|", e["description"], "|", e["source_paths"])
PY
{'group_id': 'causal_clocks', 'policy': 'CAUSAL_STREAM_REQUIRED', 'activation_stage': 'EACH_F_LAST_CUTOFF', 'authority': 'BINDING_CURRENT', 'arms': ['A_CLEAN', 'A_MEMORY'], 'principal_route': 'CAUSAL_GROUP_STREAM', 'proof_mode': 'SOURCE_READY_AND_PER_GROUP_RECEIPT'}
clock_event_time | Event-time clock | ['research/kalshi/NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md']
clock_receive_time | Receive-time clock | [same]
clock_event_known_by | Event-known-by clock | [same]
clock_feature_availability | Feature-availability clock | [same]
clock_prospective_discovery_confirmation | Prospective discovery and confirmation clock | [same]
clock_model_evaluation | Model-evaluation clock | [same]
clock_lock_time | Lock-time clock | [same]
```

### A7. A driver-built member row's clocks and a GroupDelivery's clocks (section 2)

```
$ python3 - <<'PY'
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, ".")
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_replay_driver import make_driver, record, at, NS_PER_SECOND
from research.kalshi.frankie_raw_mbo_benchmark.native_causal_stream import CausalGroupStream
from research.kalshi.frankie_raw_mbo_benchmark.native_row_sink import RowSink
driver = make_driver(total_mbo_records=3)
base = at("2021-10-04T13:00:00")
driver.consume(record(seq=i, event_ns=base + i * NS_PER_SECOND, order_id=700 + i) for i in range(3))
result = driver.finalize()
row = driver.counters.member_rows[0]
print("top-level key count:", len(row))
print("row['clocks'] =", json.dumps(row["clocks"], sort_keys=True))
print("row['decision_basis'] =", row["decision_basis"])
print("invocation_cutoffs:", result["traversal"]["invocation_cutoffs"])
with tempfile.TemporaryDirectory() as tmp:
    sink = RowSink(Path(tmp) / "exact_member_rows.jsonl", ledger="member")
    for r in driver.counters.member_rows: sink.write(r)
    sink.close()
    d = CausalGroupStream(Path(tmp) / "exact_member_rows.jsonl", run_id="demo", arm="A_CLEAN").next_group()
    print("GroupDelivery.first_lawful_availability_ns =", d.first_lawful_availability_ns)
    print("GroupDelivery.receipt['clocks'] =", json.dumps(d.receipt["clocks"], sort_keys=True))
    print("GroupDelivery fields =", list(d.__dataclass_fields__))
    print("delivered clock layers:", [l["layer_id"] for l in d.receipt["delivered_layers"] if l["layer_id"].startswith("clock_")])
PY
top-level key count: 48
row['clocks'] = {"decision_ts_recv_ns": 1633352400000150000, "f_last_ts_recv_ns": 1633352400000150000, "first_component_ts_event_ns": 1633352400000000000, "first_component_ts_recv_ns": 1633352400000150000, "first_lawful_availability_ns": 1633352400000150000}
row['decision_basis'] = REPLAY_EARLIEST_LAWFUL_AVAILABILITY
invocation_cutoffs: []
GroupDelivery.first_lawful_availability_ns = 1633352400000150000
GroupDelivery.receipt['clocks'] = {"availability_time_ns": 1633352400000150000, "decision_time_ns": 1633352400000150000, "event_time_ns": 1633352400000000000, "receive_time_ns": 1633352400000150000}
GroupDelivery fields = ['group_index', 'first_lawful_availability_ns', 'group', 'group_line', 'lifecycle_rows', 'legacy_rows', 'bytes_delivered', 'group_sha256', 'receipt', 'gate']
delivered clock layers: ['clock_event_time', 'clock_receive_time', 'clock_event_known_by', 'clock_feature_availability', 'clock_prospective_discovery_confirmation', 'clock_model_evaluation', 'clock_lock_time']
```

The 48 top-level keys of the fixture row are the 48 fields S120 counted on the Sunday ledger
(`SESSION_HANDOFF_2026-09-02_S120.md`, "STATE, VERIFIED BY EXECUTION" in `DROP_IN_S121.md`).

### A8. Production byte share of the activity blocks (NOT run here; the ledger is not in this worktree)

```
$ python3 -m research.kalshi.frankie_raw_mbo_benchmark.report_ledger_size --result <calculation_result.json>
```
The per-key byte estimate `RowSink` samples every 97th row (`native_row_sink.py:36, 99-123`) lives
in the run's sink receipt, keyed `activity` and `activity_full`, and that command renders it. The
`--help` of the module was run here to confirm the flag (exit 0); the Sunday result file itself is
on S3 and was not fetched into this worktree.

### A9. Producer searches for the seven clocks

```
$ grep -rn "CAUSAL_CLOCK = " research/kalshi/frankie_raw_mbo_benchmark/*.py | wc -l
9
$ grep -rn "known_by" research/kalshi/frankie_raw_mbo_benchmark/*.py research/kalshi/agents/*.json
research/kalshi/frankie_raw_mbo_benchmark/corrected_a_arm_execution_gate_20260828.py:31:        "clock_event_known_by",
research/kalshi/frankie_raw_mbo_benchmark/corrected_a_arm_execution_gate_20260828.py:143:        "clock_event_known_by",
research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json:237:        {"layer_id": "clock_event_known_by", [...]
$ grep -rn "first_lawful_availability" research/kalshi/frankie_raw_mbo_benchmark/*.py | cut -d: -f1 | sort | uniq -c
      2 research/kalshi/frankie_raw_mbo_benchmark/emit_frankie_spawn.py
      5 research/kalshi/frankie_raw_mbo_benchmark/native_causal_stream.py
      2 research/kalshi/frankie_raw_mbo_benchmark/native_clocks.py
      2 research/kalshi/frankie_raw_mbo_benchmark/native_principal_outputs_draft_20260902.py
      1 research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py
      1 research/kalshi/frankie_raw_mbo_benchmark/native_staging.py
$ grep -rn "precursor_for" research/kalshi/frankie_raw_mbo_benchmark/*.py
research/kalshi/frankie_raw_mbo_benchmark/native_candidate_adapter.py:217:        precursor_for: Callable[[Candidate], int | None] | None = None,
research/kalshi/frankie_raw_mbo_benchmark/native_candidate_adapter.py:227:        self.precursor_for = precursor_for
research/kalshi/frankie_raw_mbo_benchmark/native_candidate_adapter.py:302:        precursor_ns = self.precursor_for(candidate) if self.precursor_for else None
research/kalshi/frankie_raw_mbo_benchmark/native_candidate_adapter.py:580:            "prior_reachable": self.precursor_for is not None,
$ sed -n '430,454p' research/kalshi/frankie_raw_mbo_benchmark/a_clean_rt_replay_20260828.py | grep -c "_ns\|time"
0
```
The last command is the `clock_lock_time` finding: the first-lock record has no time field.

### A10. The decisions this packet binds to

```
$ python3 - <<'PY'
import json
d = json.load(open("research/kalshi/store/decisions.json"))
for e in d["entries"]:
    if e["id"] in {"D60", "D61", "D76", "D77", "D80", "D81"}: print(e["id"], "|", e["session"], "|", e["status"])
PY
D60 | S115 (Greg, STANDING RULE) | OPEN (rule standing; instance 1 fixed, instance 2 fixed)
D61 | S115 (Claude, under D60) | CLOSED
D76 | S119 (Greg, on the D68 question) | STANDING
D77 | S119 (measured, after a subagent swept the shared tree) | STANDING
D80 | S120 (measured, wiring 4.16) | STANDING
D81 | S121 (Greg, 2026-09-02) | BUILT AND WIRED; NOT YET RUN AGAINST THE SUNDAY LEDGERS
```
