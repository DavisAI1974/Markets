# CODEX TASK - S122 ITEM 4

Repository `DavisAI1974/Markets`, branch **`chatgpt/frankie-raw-mbo-benchmark-20260828`**, base commit
`8e578f5`. Baseline suite: **1,885 passed, 5,509 subtests**.

There are **four tasks**. They are small, bounded and verified. Everything else you may notice is out
of scope and section 6 names it explicitly.

Every claim below was checked by EXECUTING the code at `8e578f5`, not by reading it. If something is
not where this file says, **stop and report it** - do not go looking. Three of the defects listed
here exist because someone patched a symptom instead of reporting a cause.

---

## 0. RULES

1. **Tests first.** Write the failing test, RUN it, watch it fail for the reason you intend, then
   implement. A test that never failed has tested nothing.
2. **A refusal is produced by a test**, never asserted in prose.
3. **Never edit `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`** (hash-locked, D61).
   `git diff --quiet` on it exits 0 at every commit.
4. **Never write to a scratchpad or `/tmp`** (D87). Transient files go under the gitignored `data/`
   and are deleted. Tests use `tempfile` inside the test. No committed file may name such a path (D34).
5. **Commit and push after every task** (D84):
   `git push -u origin chatgpt/frankie-raw-mbo-benchmark-20260828`. One task per commit. Never force-push.
6. **No historical number is a spec** (D60). Derive counts at run time. Never type `99`, `75`, `63`,
   `14`, `10` as an expected count.
7. **Nothing is dropped** (D60/D76). If a change would remove a field or a row, keep it and say so.
8. **One arm: `A_MEMORY`** (D86/D88). `A_CLEAN` stays a valid enum value as an inert record.
9. **No emojis.** Commit messages end with exactly:
   `Co-Authored-By: Codex <noreply@openai.com>`

### Gates before every commit

```bash
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests -q -p no:cacheprovider \
  > data/suite.log 2>&1; echo "EXIT $?"; tail -2 data/suite.log
python3 research/kalshi/store.py check     # 4 PASS lines
python3 research/kalshi/store.py docs      # PASS docs
git diff | grep -nE 'E:[/\\]|scratchpad|/tmp'    # finds nothing
git diff --quiet research/ng_exhaustion_mbo_v4_state_adapter_20260820.py && echo LOCKED_OK
```

**Redirect pytest to a file and read `EXIT`.** Piping to `tail` hides failures from `set -e`; that
exact mistake pushed a red commit in this session.

### Do not touch

`chat_packet_seam.py`, `A_MEMORY_SEED_*.json`, `register_a_memory_knowledge.py`,
`rebind_registry_knowledge_layers.py`, the registry's `a_memory_overlay` group,
`.github/workflows/frankie_a_memory_rt_native_launch_20260828.yml`, `native_staging.py`,
`prior_memory/**`, `principal_runs/**`, any `*_RENDER_*.md` or `FRANKIE_FEED_RECORD_*.md`.
**The A_MEMORY seed is being built in parallel and you will collide.**

---

## 1. TASK A - carry per-record `raw_actions` on the member row (F-30)

**Why.** D81, Greg: the principal receives *"every record of every field"*. The delivered member
ledger does not carry the per-record raw actions, so ten order-lifecycle layers compute
`RECEIPTED_CARRIER_ABSENT` on the real Sunday result. Greg's resolution is fixed: **carry them.**

**The defect, proven by execution.** `native_replay_driver.py:1083` builds the row with
`member_clock_row({"raw_actions": list(actions)}, ...)`. That function (`native_clocks.py:235`) uses
the list to derive clocks and **returns a fresh dict without it**. Calling it directly returns:

```
row keys: ['causal_clocks', 'channel_count', 'channels', 'clocks', 'component_count', ...]
raw_actions on the row: False
```

Then `native_replay_driver.py:1105-1107` carries every other frame key onto the row **except** this
one, under a comment that is FALSE and is why the drop survived review:

```python
# `raw_actions` is excluded only because the member row already holds it.
for carried, value in frame.items():
    if carried == "raw_actions" or carried in row:
```

**Do exactly this.**

1. RED test in `tests/test_native_replay_driver.py`: every member row the driver writes carries
   `raw_actions`, a list, one entry per component, in receive order, **equal to the frame's own
   list compared whole** (not a count, not a hash). Second test: `len(row["raw_actions"]) ==
   row["component_count"]` on every row of a multi-group fixture. Third: the row has exactly one
   `raw_actions` key (no duplicate copy).
2. Stop excluding it in that loop. Delete the false comment; replace it with one line stating that
   `member_clock_row` does not return it and that this was measured.
3. Remove the now-false `raw_actions` entries from `structurally_absent` tuples in
   `native_layer_crosswalk.py`. Find them with:
   `grep -n 'structurally_absent=("raw_actions' research/kalshi/frankie_raw_mbo_benchmark/native_layer_crosswalk.py`
   (12 occurrences at `8e578f5`). **Remove only the `raw_actions` and `raw_actions[]` entries.**
   Entries naming a field the tape genuinely lacks - `raw_actions[].source_dbn_sha256`,
   `raw_actions[].source_dbn_object`, `raw_actions[].is_snapshot`, `raw_actions[].book_effect` -
   STAY unless you can see that field on a real row. Decide each by looking at a row.
   Where a tuple becomes empty, remove the argument.
4. Ledger bytes change, so `tests/test_native_row_sink_differential.py` re-baselines. Fix it
   honestly and say in the commit body that ledger bytes and hashes changed.
5. **Measure and state in the commit body**: member-ledger bytes on the fixture before and after,
   and the per-row cost. This is a D60 size decision and it is recorded now, not discovered on a
   10 GB ledger.

**Done when** a fixture run's field census sees the per-record raw action fields, each of the 12
pins is removed or justified, and the differential is green with its re-baseline explained.

---

## 2. TASK B - change points ON by default

**Why.** D88: the canonical launcher carries everything as its DEFAULTS; a flag exists only to turn
a default OFF for a declared comparison. `observe_change_point` was wired at S120 and left gated
off, which is why one canonical run reported section 4.16 as not fed. The real Sunday box run
produced **88,071 fed change points**, so the mechanism works and only the default is wrong.

**The state, verified.**

| symbol | file:line | today |
|---|---|---|
| `emit_change_points` | `native_replay_driver.py:407, 426` | defaults `False` |
| `_observe_change_points` | `native_replay_driver.py:812-826` | returns early when off |
| `emit_change_points` | `native_a_arm_launch.py:387, 532` | defaults `False` |
| CLI flag | `native_a_arm_launch.py:~616` | `--emit-change-points`, opt-IN |

**Do exactly this.**

1. Default `emit_change_points=True` in `NativeReplayDriver` and in `native_a_arm_launch.launch`.
2. Turn the CLI flag into an opt-OUT: `--no-change-points`, `action="store_false"`,
   `dest="emit_change_points"`, default `True`. The help text says change points are on by default
   under D83/D88 and that turning them off is a declared comparison.
3. Tests: with no flag, a fixture run emits change points; with the flag, it emits none and the
   section declares itself off rather than empty.

**That is the whole task.** See section 6 on the horizon ladder, which is NOT part of it.

---

## 3. TASK C - give `RecognitionLabel` its caller

**Why.** `native_clocks.RecognitionLabel` (`native_clocks.py:158`) is the validated carrier of
section 2's PRIOR / T0 / H+N with its lead and the clock it was measured on. It has no production
caller, so recognitions travel as ad-hoc dicts and its four invariants - the label is known, the
clock is `ts_recv_ns`, PRIOR precedes its reference, T0 coincides, H+N follows - are enforced
nowhere.

**Do exactly this.**

1. Find the production sites that emit a recognition label today:
   `grep -rn 'recognized_recv_ns\|RECOGNIZED_BASIS\|"label"' --include=*.py research/kalshi/frankie_raw_mbo_benchmark | grep -v tests/`
   The candidate adapter's `record_call` path (`native_candidate_adapter.py:306-309, 362`) is the
   one that matters.
2. Construct a `RecognitionLabel` there and let its validation run, so an impossible recognition
   raises instead of being written. Keep whatever the row and output carry today; add the validated
   object's values beside them (D60: nothing is dropped, nothing is renamed).
3. Tests: a T0 recognition whose observed time does not equal its reference is REFUSED; an H+N
   whose observed time precedes its reference is REFUSED; the lead sign matches the convention
   documented at `native_principal_outputs.py:891` (`lead = reference - observed`, positive before
   birth).

**`precursor_for` is NOT part of this task.** See section 6.

---

## 4. TASK D - the crosswalk: five defects measured on the real Sunday ledgers

Measured on run `33630348943` (57,027 records, 43,569 groups, the whole 10.6 GB member ledger
streamed causally). The record is committed at
`research/kalshi/frankie_raw_mbo_benchmark/FRANKIE_FEED_RECORD_SUNDAY_33630348943_20260903.md`.

**Start from the tests-first file that already exists.** On branch
`persona/s121-wire-knowledge-gates` at `dd874f3`, `tests/test_native_layer_crosswalk_s122.py` is RED
for exactly one reason: it imports `group_carriers_from_producers` from `native_layer_crosswalk`,
which does not exist. Fetch that branch and read the test - it encodes the intended shape of D-2.

### D-1 (HIGH) - "carrier absent" and "census absent" are the same status

`observed_carriers` (`native_layer_crosswalk.py:960-965`) checks member carriers **only** against
`layers.exact_member_ledger.field_census`, and with `--ledger-dir` the crosswalk opens only the
legacy file (`:994-1004`), never the delivered member ledger. On the Sunday result **36 of the 45**
`RECEIPTED_CARRIER_ABSENT` rows read "(the result carries no field census)" while the fields were on
every delivered row.

Fix: when `--ledger-dir` is given, read the delivered member ledger's field names (a bounded scan;
state the bound in code and in the status detail) and add a distinct `CENSUS_ABSENT` status. Missing
evidence and an absent carrier must never share a status.

### D-2 - two authorities disagree about which ledger carries a layer

`native_causal_stream.LAYER_CARRIERS` (per group) and `native_layer_crosswalk.LAYER_PRODUCERS[*].ledgers`
(per layer) disagree for **10 layers**; two are DELIVERED and lifecycle-only
(`resilience_and_recovery`, `clock_prospective_discovery_confirmation`) while their group is claimed
on `member`. Add `group_carriers_from_producers` deriving one from the other, and a test that fails
when either moves.

### D-3 - the arm is never read off the result

Neither the crosswalk nor the stream reads `layers.identity_receipt.arm`. `--arm A_MEMORY` against
an A_CLEAN-identity run is silent. Read the arm off the result when one is given; a disagreement
with `--arm` is stated loudly, not absorbed.

### D-4 - two statuses that must be computed, not stamped

- **F-27:** `_static_status` (`:1103-1130`) reads `bound_to_inventory_document` from a constant in
  `LAYER_PRODUCERS` (`:145`). The registry was rebound on 2026-09-02 and that constant lied the same
  day. Compute it with
  `native_knowledge_delivery.layers_bound_only_to(registry, FEED_DOC, policies=KNOWLEDGE_INPUT_POLICIES)`.
  Test: on the rebound registry with no knowledge receipt those layers read `PRODUCED_NOT_DELIVERED`.
- **F-29:** `clock_lock_time` is an input layer with no producer because the lock instant is
  Frankie's own output (`output_first_locks_and_no_locks`). Greg's resolution is fixed: a computed
  status **`PRINCIPAL_STAMPED`** for that one layer, accepted by `gate_applicable_inputs`, with the
  pre-call stamp still reading as a disagreement. **Do not move the layer in the registry.**

### D-5 - the CLI default

`native_layer_crosswalk.py:1533`: `--arm default="A_CLEAN"` becomes `A_MEMORY`, `A_CLEAN` still a
valid choice, default pinned by test. Same for any `A_CLEAN` usage example in that module's docstring.

**Done when** each of the five has a test that fails without its fix, and recomputing the crosswalk
on the committed Sunday result changes the statuses you predicted and no others.

---

## 5. ORDER

**A, then D, then B, then C.** A is the ruling itself. D is the largest. B and C are small.

If you run out of budget: **commit what is green as a labelled save point, commit RED tests-first
files with RED in the subject line, push, and stop.** Never leave work uncommitted in a container.

---

## 6. EXPLICITLY OUT OF SCOPE - do not start these

Each of these looks like an obvious next step and is not. They were investigated at `8e578f5` and
ruled out with reasons.

1. **Retiring the 4.16 horizon ladder.** `HORIZON_SETS` (`native_response.py:146`) is not a knob:
   the response table is BUILT on fixed horizons, each with its own at-risk denominator, each
   written once and refusing a second write, with lateness recorded per reading. It is read live by
   `native_a_arm_launch.py:456-457` into `native_calculation_runner.py:284-285, 351-352`. Replacing
   it with realized-response maturation is a redesign of section 4.16, not a wiring change. It is
   Greg's call. **Change the default (Task B) and stop there.**
2. **Wiring `precursor_for` to make PRIOR reachable.** The module says so itself
   (`native_candidate_adapter.py:14-24`): *"PRIOR is structurally unreachable for a candidate defined
   by its own detection... Prebirth prediction needs a DIFFERENT signal that precedes the spike - a
   precursor - and this module takes one as an optional callback rather than inventing it. Until
   such a signal exists, every candidate is honestly `H+N`."* There is no precursor detector in the
   repository. Wiring the callback means INVENTING one. `prior_reachable: false` is a true statement
   about the current evidence surface, not a defect. Leave it.
3. **The spawn gate in `emit_frankie_spawn.emit`.** It depends on the knowledge receipt (on branch
   `persona/s121-wire-knowledge-gates` at `d5e7f34`) and on the A_MEMORY seed, which is being built
   in parallel. Attempting it now collides.
4. **Making `emit_frankie_spawn` succeed on the Sunday result.** It correctly refuses: the run's
   bound mission and contract hashes no longer match the files on disk, and the run predates the
   field census. **Never weaken a refusal to make a run pass.** Fix the feeding, never the gate.
5. **The A_MEMORY seed, the packet seam, the launch workflow.** Being built in parallel.

---

## 7. YOUR REPORT

Per task: DONE / IN_PROGRESS / NOT_STARTED; every commit sha with confirmation it was pushed; the
test count at your tip; **anything in this file that turned out to be wrong**; every decision that
belongs to Greg (state it and keep going - D60 means nothing is dropped while it waits); and
confirmation that nothing was written to a scratchpad or `/tmp` and that the hash-locked adapter is
byte-identical.
