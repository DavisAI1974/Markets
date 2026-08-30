# The wiring list

**Greg:** *"i believe the drop in box mentions wiring stuff in and not building."* It does,
and I had been framing this session as a build question anyway. The box says it twice:

> **Section 8:** *"Verify by EXECUTION, not by the presence of a file. Four adapters were
> built and called by nothing; the checkpointer sits on a driver no workflow dispatches; ten
> of thirteen sections receive zero data today. **Components existing is not wiring
> existing.**"*
>
> **Section 9:** *"Adapters wired: **0**. Execution gate referenced by any non-test file:
> **0**. Workflows that dispatch the driver: **0**."*

So this document is a wiring list. **Nothing on it is a build.** Every row is an existing
producer connected to an existing consumer.

---

## Measured first: what the driver writes today

`native_replay_driver.py`, every write call, by execution rather than by reading the box:

| line | call | section fed |
|---|---|---|
| 325 | `self.run.coverage.observe_group(...)` | coverage |
| 360 | `self.run.clocks.observe(row)` | 4.x clocks |
| 370 | `self.run.replenishment.advance(recv_ns)` | one clock advance only |
| 253 / 361 / 362 | `note_lifecycle_row` / `note_member_row` / `note_session_assignment` | bookkeeping |

Everything else the runner touches is a READ - `summary()`, `population_report()`,
`at_risk_table()`, `depth_distribution()`. Eleven calculators are constructed at
`native_calculation_runner.py:253-264`; three receive data. **The box's count reproduces
exactly.**

---

## Tier 1 - four adapters, four consumers, four call sites

These are complete on both ends. The adapter builds the domain object; the calculator has
the method that takes it; nothing calls either. Each row is one line in the driver, beside
the existing `clocks.observe(row)` at line 360.

| Producer (built, called by nothing) | What it returns | Consumer (built, never fed) |
|---|---|---|
| `native_group_adapters.occurrences(actions, ctx)` | one `Occurrence` per action in tape order, node label `action\|side` | `native_recurrence.observe_sequence` / `add_edge` |
| `native_group_adapters.ladder_transitions(...)` | one transition per side - depth CONSUMED before, depth LEFT after, group-local delta | `native_ladder.observe` (`:291`) |
| `native_group_adapters.runway_pressure_fields(...)` | exact per-group quantities for a `RunwayPressure`, traded and withdrawn depletion kept separate | `native_absorption` `RunwayPressure` |
| `native_group_adapters.lineage_additions(...)` | `LineageGraph.add` keyword sets for order ids this group touched FIRST | `native_lineage.observe_node` (`:234`) |

Confirmed by execution: the only non-test references to `native_group_adapters` anywhere are
one constant import (`PRICE_SENTINEL_ABS` in `native_rt_book`) and two docstring mentions.
**Adapters wired: 0**, as the box says.

`native_queue` (`observe_level`, `note_level_fill`, `observe`) is a fifth unfed consumer with
**no** adapter on the producer side. That one is a genuine gap, and it is the only Tier-1-shaped
gap that is not just a missing call.

## Tier 2 - three sections wire to the BUILT stack, not to new code

4.10, 4.11 and 4.12 are the sections the last two drop-in boxes said needed a substrate
built. Per `FRANKIE_A_ARM_ALREADY_BUILT_AUDIT_20260830.md`, they do not.

| Need | Existing thing to wire to |
|---|---|
| per-second roll20, live/incremental | `ng_exhaustion_live_clock.AggressorRoll20Feed.ingest_trade(second, price, size, bid_px, ask_px)` - reconstructs *"the exact 20-second rolling aggressor-volume imbalance used by the frozen exhaustion research"* |
| per-second roll20, pre-binned | same class, `ingest_volume(second, buy_volume, sell_volume)`, fed from the benchmark's OWN per-second binning of the native F_LAST stream. **NOT from the Step-1 seconds artifact** - the mission forbids Step-1-derived input and the inventory seals it as `SEALED_TARGET_ANSWER` |
| candidate detection | `ng_dipole_native_shape_audit.flow_series` + `detect_dipole_peaks`, frozen, measured at 1.521s for the whole A-arm roster |
| A/B/C family | `ng_exhaustion_live_clock.FrozenPreFamilyClassifier`, SHA `583f6a12...` enforced |
| duration / remaining runway | `ng_exhaustion_runway_clock.ExhaustionRunwayClock`, classifier SHA `698b956f...` enforced, frozen baselines, *"do not retune"* |
| discovery time | `research/kalshi/ng_exhaustion_v4_causal_clock` - `make_receipt`, `validate_availability_chain`, `first_receive_ordered_mark` |

**The benchmark currently imports exactly one built module** -
`ng_exhaustion_mbo_v4_state_adapter_20260820` - and none of the above.

## Tier 3 - the two the box counted that are not adapters

* **Execution gate referenced by non-test files: 0.** `corrected_a_arm_execution_gate_20260828`
  exists and is exercised only by its tests.
* **Workflows dispatching the driver: 0.** The periodic checkpointer sits on a driver nothing
  dispatches.

---

## One thing that must be settled before Tier 2, and it is not a build either

`NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md` names three timestamps that must
not be conflated - retrospective `t0`, the live discovery mark, and the endpoint's causal
confirmation - and warns explicitly against using the third as a label-availability gate.

The landmark ladder committed earlier today (`c0b6216`) carries the first and third. **It
cannot express the second.** Before 4.10 or 4.11 is fed, either a third landmark is added or
the module states that it does not model discovery time. `ng_exhaustion_v4_causal_clock`
appears to be the closure of that open boundary - it is dated the day after - and that should
be confirmed rather than assumed.

## Order

1. **Tier 1**, because both ends already exist and each row is one call. Four sections stop
   being empty for four lines.
2. **The event-mark ruling**, because Tier 2 inherits it.
3. **Tier 2**, as imports of frozen modules.
4. **Tier 3**, the gate reference and a workflow that dispatches the driver.

**Withdrawn:** an earlier version of this list ended with a retrieval question about where the
October Step-1 seconds artifact lives. That question is void - the mission forbids Step-1-derived
input and the feed inventory seals that artifact as the answer. The benchmark computes its own
per-second surface from the native stream and crosswalks it, per inventory section 8.
