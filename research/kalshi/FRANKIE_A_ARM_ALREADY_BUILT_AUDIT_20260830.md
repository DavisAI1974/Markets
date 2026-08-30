# Auditing the "missing" list against what is already built

**Why this document exists.** Greg, twice in one session: *"Don't we already have an
exhaustion calc?"*, then *"We have actually done step 1 work for the less than mbo data for
these 2 days"*, then *"go through this list and look for things already built because I'm
sure we have a clock too."* He was right all three times. This is the systematic pass,
claim by claim, with the disproof attempt recorded next to each.

**The one number that summarises it: the benchmark imports ONE module out of the roughly
forty-module built exhaustion stack.** Every `from research.` line in
`frankie_raw_mbo_benchmark/` resolves to `ng_exhaustion_mbo_v4_state_adapter_20260820`
(`V4MboAdapter`, `F_LAST`, `F_TOB`) and nothing else. Not the runway clock, not the live
clock, not the causal discovery clock, not the dipole shape audit. That is the answer to
*"why aren't we using what is already there"* - not a decision anyone made, just a package
that grew without importing.

---

## The claims, tested

Each claim is quoted from `FRANKIE_A_ARM_PRIOR_WORK_RECOVERY_20260829.md` or
`DROP_IN_FRANKIE_A_ARM_NEXT.md`. Both are mine from prior sessions.

| # | Claim | Verdict |
|---|---|---|
| C1 | *"no code in `frankie_raw_mbo_benchmark/` computes roll20 or any dipole from the MBO stream"* | **Literally true, materially misleading** |
| C2 | *"THE EVENT CLOCK DOES NOT EXIST IN THE BUILT WORK"* | **REFUTED** |
| C3 | *"The only raw material for a real event clock in the repo is `native_clocks.sequence_span`"* | **REFUTED** |
| C4 | *"MISSED is genuinely new"* | **HOLDS** |
| C5 | *"the built prebirth measurement has a large negative class, 135,823 positive / 20,562 negative"* | **UNVERIFIED - the two numbers are different quantities** |

---

### C1 - roll20. Literally true, materially misleading.

Already corrected in `FRANKIE_A_ARM_ROLL20_SUBSTRATE_SCOPE_20260830.md` section 5, and worse
than recorded there. Three independent implementations exist:

1. **Batch, per-second** - `ng_exhaustion_mbo_5y_step1_census_20260822.py:244-334` emits
   `legacy_buy_qty`/`legacy_sell_qty` (mid comparison, the frozen recipe) and
   `native_buy_qty`/`native_sell_qty` (the tape's side field). For October 2021 this is a
   112,852,940-byte hash-pinned artifact.
2. **The detector** - `ng_dipole_native_shape_audit.flow_series` / `detect_dipole_peaks`,
   frozen, runs today, measured at 1.521s for the whole A-arm roster.
3. **LIVE AND STREAMING** - `ng_exhaustion_live_clock.AggressorRoll20Feed`, which this pass
   found and which nothing previously mentioned. Its docstring: *"reconstructs the exact
   20-second rolling aggressor-volume imbalance used by the frozen exhaustion research
   (trade sign = price vs concurrent top-of-book mid)"*. It has an incremental
   `ingest_trade(second, price, size, bid_px, ask_px)`, a pre-binned `ingest_volume(second,
   buy_volume, sell_volume)`, a retain window, `raw_value_at`, `raw_series` and `snapshot`.

So roll20 exists in batch form, in frozen-detector form, AND as a live incremental feed with
exactly the two entry points the A-arm would need. The sentence in the drop-in box was true
about the *benchmark package* and got read as true about the *project*.

### C2 - the clock. Refuted, and the refuting module is in `research/kalshi/`.

The recovery document reached its conclusion by grepping the literal string `event_clock`,
finding only a boolean availability flag, and stopping. That is the same error as C1:
searching for the NAME rather than the THING.

**Four clock modules and five clock artifacts exist:**

* **`research/kalshi/ng_exhaustion_v4_causal_clock.py`** - *"Isolated V4 causal
  discovery-clock contract... It exists to make the V4 event-known boundary explicit and
  **fail closed when retrospective t0 is substituted for a causal mark**."* Carries
  `CausalDiscoveryReceipt` with a `validate()`, `make_receipt(event_id, session_id,
  detector_revision, ...)`, `validate_availability_chain(receipt, feature_available_at,
  ...)`, and `first_receive_ordered_mark(rows, qualifying_field="qualifies")`. **This is an
  event clock.** It is the discovery-time contract, it is schema-versioned
  (`NG_EXHAUSTION_V4_CAUSAL_DISCOVERY_V1`), and it sits in the same directory as the
  benchmark.
* **`research/ng_exhaustion_runway_clock.py`** - deterministic V0, frozen reveal duration
  baselines with *"do not retune to held-out medians"*, classifier SHA `698b956f...`
  enforced, `validate_committed_replay_metrics`.
* **`research/ng_exhaustion_live_clock.py`** - the live adapter, carrying
  `AggressorRoll20Feed` and `LiveExhaustionRunwayEngine` with `mark_event(event_id,
  session_id, t0_second)` and `update(event_id, now_second, ...)`, pre-family classifier SHA
  `583f6a12...` enforced.
* **`research/ng_exhaustion_live_clock_batch_proof.py`**, with
  `NG_EXHAUSTION_LIVE_CLOCK_V0_FINAL_PROOF_20260817.json`.

**And the boundary document is the one that matters most for design.**
`NG_EXHAUSTION_EVENT_MARK_CLOCK_OPEN_BOUNDARY_20260819.md` names **three timestamps that
must not be conflated**:

1. frozen retrospective exhaustion onset / birth `t0`;
2. the upstream causal detector's actual **live event-mark / discovery timestamp**;
3. the later structural endpoint, `dynamic_endpoint.causal_confirmation_idx`.

with the explicit warning that (3) *"is not automatically the event discovery timestamp and
must not be used as a generic label-availability gate merely because it is the only
confirmation field in the canonical row"*, and that (1) *"is also not automatically assumed
to be a live notification timestamp."*

**This has a direct consequence for what I built earlier today.** The landmark ladder I put
into `native_exhaustion` carries `T0` and `ENDPOINT_ONSET` / `ENDPOINT_CONFIRMATION` - that
is (1) and (3). **It cannot express (2)**, the live mark. The ladder is not wrong, but it is
incomplete in precisely the way this document warns about, and an RT arm needs (2). The
boundary doc was dated 2026-08-19 and `ng_exhaustion_v4_causal_clock.py` is dated
2026-08-20, so the open boundary appears to have been closed the next day by that receipt
contract - which should be confirmed before anything is built on the assumption.

### C3 - "only raw material is `sequence_span`". Refuted by C2.

### C4 - MISSED. The claim holds.

The only occurrence of `MISSED` as a detection-outcome anywhere in the repo is
`frankie_raw_mbo_benchmark/native_recognition.py` itself. The built corpus has three forms
of CENSORED and no concept separating *"a birth occurred and the detector said nothing"*
from *"no birth occurred"*. **One negative claim out of five survives**, which is roughly the
rate that should have been expected and was not.

### C5 - the 4.11 negative class. Not verified; the numbers do not obviously mean what I said.

The recovery document asserted *"At D0 the split is 135,823 positive / 20,562 negative."*
What is actually findable:

* `ng_exhaustion_d0_model_specific_trade_20260819.py:159` asserts **135,823** rows with
  `continuation == 1`.
* `NG_EXHAUSTION_CHAIN_PHASE2_FINDINGS_20260817.md:28` reports **156,422** OOT origin
  instances, of which **20,562** survive to **D1+** (13.15%).

So 20,562 is a *D1+ survival count from a 156,422 population*, not the negative complement
of 135,823 within D0. The two numbers come from different documents and different
populations, and 135,823 + 20,562 = 156,385, which is near 156,422 but not equal to it.
**A negative class does exist somewhere in the built prebirth work - that part is not in
doubt - but the specific split I quoted should not be reused until it is re-derived from one
source.** Flagging rather than silently repairing, per D60.

---

## What this changes

1. **Nothing here needs building.** roll20, the runway clock, the live streaming feed, the
   family classifiers and the causal discovery receipt all exist, are frozen, and several are
   hash-enforced. The gap is imports.
2. **The landmark ladder needs a third landmark** - the live event-mark - or an explicit
   statement that 4.10 does not model discovery time. Either is fine; silence is not.
3. **The remaining genuinely-new item is MISSED**, and it is small.
4. **The unit question is smaller than it looked.** `AggressorRoll20Feed` already accepts
   both a raw-trade entry point and a pre-binned entry point, so a nanosecond arm and a
   per-second arm can feed the same frozen object without either one being reinterpreted.

## Method note, because the failure repeated

Both C1 and C2 were reached the same way: grep the NAME, find nothing, conclude absence.
Both were wrong for the same reason. The corpus names things by their role
(`AggressorRoll20Feed`, `CausalDiscoveryReceipt`, `legacy_buy_qty`), not by the vocabulary a
later contract invented. **Absence of a string is not absence of a capability**, and the
check that would have caught it every time is to search for the INPUTS and OUTPUTS a
capability must have rather than its name.

Cross-model review was not available: neither `gemini` nor `codex` is on PATH in this
container. Recorded rather than skipped silently.
