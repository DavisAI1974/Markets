# Claude to Codex — Frankie BOSS contract addendum for parallel lanes

Date: 2026-09-07
Identifier: `BOSS_CONTRACT_ADDENDUM_R3_20260907` (rev 1, 2026-09-07: section 1.3 and A2 parameter-count invariant corrected per Codex)
Base: `beb548b86b777dc69bf834950b30cc28000e16ef` (read-only clone; `trunk.py`, `teacher.py`, `dipole_target.py`, the V4 adapter, replay, manifest, and resume state were read at this commit)
Supersedes nothing. Extends: R2 target-semantics proposal (`CLAUDE_C15_TARGET_SEMANTICS_PROPOSAL_R2_20260904.md`), Codex R2 rulings, Round 3 findings memo and patch 0005.

## 0. Boundary and fixed ground

Nothing in this addendum authorizes a change to any existing Frankie input, calculation, plane, adapter, replay, Memory A artifact, or last-run behavior. Every contract below describes additive BOSS code that lives beside Frankie and is off by default. Where a contract needs something from the adapter, it consumes the adapter's existing outputs; it never asks the adapter to change.

Fixed and not reopened: B2_GATED; native B1 authoritative; Granite 4.2 8B bounded shadow critic; ReFRAG/QSV governed; dipole training-only; 19-column candidate `BOSS_TEACHER_CANDIDATE_C15R2`; B1 quiet wall PRESENT `0.0`; undefined anchor freezes the chain; one cutoff per C15 artifact; patch 0005 as the prefix foundation pending Codex verification.

Lane map for this addendum:

| Lane | Contract | Depends on | Blocked by |
|---|---|---|---|
| L-B1 | C19 recurrence, C20 halting | `trunk.py` at base, `causal_packet` | nothing; pure model code |
| L-NORM | C15 normalizer completion | R2 section 9, phase authorization | nothing; pure code |
| L-D | C15 section 5.2 / 5.5 state machine | adapter `ApplyEffect`, `RestingOrder`, receipts from `RecordPrefixChain` | patch 0005 commit |
| L-INT | observer hook, builder, checkpoint | all of the above | later authorization; not in this addendum |

Each lane binds its own code SHA and config hash into the receipt it emits. Cross-lane compatibility is guaranteed by the identities in section 5, not by lanes reading each other's code.

---

## 1. C19 — B1 recurrence: `BOSS_B1_RECURRENCE_V1`

### 1.1 What is reused and what is new

The B0 trunk is not modified. `Trunk.represent()` stays the one-pass fixed-depth representation and remains the B0 control. B1 is a new module `B1Reasoner` that wraps a `Trunk` instance and adds one shared-weight reasoning cell. The B0 control and B1 are separately trained instances of separately declared architectures; B1 code must be able to reproduce B0 exactly at zero reasoning steps (acceptance A1).

### 1.2 State

- `h0`: `(B, T, d_model)`, the output of `trunk.represent(...)` for this packet. Computed once per forward. Never recomputed inside the loop.
- `z_k`: `(B, T, d_model)`, the whole-representation reasoning state after `k` steps. `z_0 = h0` (identity initialization; no learned init, no noise).
- `k`: integer step counter, `0 <= k <= K_MAX`.
- There is no other carried state. The cell's internal `GatedDeltaCell` state `S` is local to a single step (section 1.5).

### 1.3 Transition (one shared cell, applied `k` times)

```
u      = LN_in( z_k + W_in @ h0 + e_step[k] )        # input re-injection + step embedding
u      = SWA_R(u)                                    # sliding-window attention, same window as trunk
u      = GDC_R(u)                                    # GatedDeltaCell, S initialised to zeros this step
u      = u + FF_R(u)                                 # LN -> Linear -> GELU -> Linear
z_{k+1} = LN_out(u)
```

- `W_in`, `SWA_R`, `GDC_R`, `FF_R`, `LN_in`, `LN_out` form the recurrent core: ONE parameter set reused at every step. The recurrent core's parameter count is independent of `K_MAX`.
- `e_step` is a learned table of exactly `K_MAX x d_model` parameters and is the only parameter group whose size depends on configured depth. It is reported separately from the core count in the receipt and the model registry (`n_params_core`, `n_params_step_embedding`). Step `k` uses row `k`; no row is ever shared across steps.
- `e_step` is a learned embedding table of size `K_MAX x d_model`; step `k` uses row `k`. It lets a shared cell know where it is without unsharing weights.
- `W_in @ h0` is re-injected every step so the state cannot drift away from the evidence. This is the only place `h0` enters after step 0.
- No trunk layer runs inside the loop. The shared-weight boundary is exactly `B1Reasoner`'s cell. Trunk weights train jointly but are applied once.

### 1.4 Graph processing does not repeat

`TemporalGraphBranch` is applied exactly once, inside `trunk.represent()`, before the loop, matching the executable authority recorded in the architecture inventory (one module, one application). The reasoning cell does not receive `parent`, `venue_id`, or `instrument_id`. Rationale: ancestry is static within a packet; re-applying it re-injects the same embeddings and would make the loop a second graph model. The docstring wording "per layer" is not authority.

### 1.5 Temporal memory reset and carry

- `GDC_R` initialises `S` to zeros at the start of every reasoning step and sweeps sequence time within that step. `S` is never carried from step `k` to `k+1`; information that must persist across steps lives in `z_k`.
- No state of any kind carries across packets or forwards. Two forwards on the same packet produce identical outputs regardless of what ran before (acceptance A6). This is required by the packet hash audit.

### 1.6 Heads and teacher attachment

- `B1Reasoner.represent()` returns `z_K` where `K` is the depth used (section 2). `TypedHeads` and the BLD-1 projector read `z_K` only.
- Teacher supervision (`TeacherHead`, D0-D5 arms) attaches to `B1Reasoner.represent()` output, the same surface it uses for B0. Nothing in `teacher.py` changes.
- `B1Reasoner.represent_b0()` exposes `h0` for diagnostics. It is not a training surface.

### 1.7 Training unroll and detachment

- Full backpropagation through every executed step. No `.detach()`, no `.no_grad()` prefix, no truncation inside the loop in V1. Gradients reach the trunk through `h0` and through every re-injection.
- Depth during training is governed by section 2; under the FIXED policy every example unrolls `K_FIXED` steps.
- Deferred to promotion: truncated backprop with a no-grad prefix (the memory-saving variant), curriculum on depth, and recurrence regularisers. None may be added without a new schema id.

### 1.8 Config and receipt

```
B1Config: k_max: int = 8, k_fixed: int = 8, halt_policy: "FIXED" | "CONVERGENCE",
          conv_tau: float = 1e-3, inject_input: bool = True, step_embedding: bool = True
```
`inject_input` and `step_embedding` exist so ablations are declarable; V1 sets both true.

Every forward emits `RecurrenceReceipt`: `schema="BOSS_B1_RECURRENCE_V1"`, `b1_code_sha`, `config_hash`, `k_max`, per-example `depth_used` and `stop_reason` (section 2), `packet_hash`. The receipt is part of the decision provenance; it carries no market values.

### 1.9 Acceptance criteria (L-B1)

- A1 Identity at zero depth: with `K=0`, `B1Reasoner(trunk).forward(packet)` equals `trunk.forward(packet)` bit-for-bit under the same weights.
- A2 Shared weights: `n_params_core` (every `B1Reasoner` parameter except `e_step`) is identical for `k_max` in {1, 4, 8}; `n_params_step_embedding` equals exactly `k_max * d_model`; the receipt reports both.
- A3 Eval determinism: two eval forwards on the same packet at the same depth produce identical logits and identical `z_K`.
- A4 Gradient reach: after one backward at `K_FIXED=4`, `e_step[0]`, `W_in`, and at least one trunk encoder parameter have non-zero gradient.
- A5 Graph once: a spy counter on `TemporalGraphBranch.forward` reads exactly 1 per forward for every `K`.
- A6 No cross-forward state: forward(packet_A) then forward(packet_B) yields the same output for B as forward(packet_B) alone.
- A7 Step-local memory: instrumenting `GDC_R` shows `S` equals zeros at the start of every step.
- A8 Config binding: changing `k_max` or `conv_tau` changes `config_hash`; the receipt carries `b1_code_sha` equal to the blob SHA of the module file, plus `n_params_core` and `n_params_step_embedding`.

---

## 2. C20 — Halting: `BOSS_B1_HALT_V1`

### 2.1 Distinction from abstention

Compute halting decides how many reasoning steps run. BLD-1 abstention decides what Frankie is told. They are independent: halting never sets or reads `disposition`, `confidence`, or any head output; the decision-contract validator never reads `depth_used` or `stop_reason`. A `MAX_DEPTH` stop is a normal outcome, not a defect and not an abstain trigger. This is enforced structurally (acceptance H6).

### 2.2 Initial policy: FIXED

V1 default is FIXED depth: every example runs exactly `K_FIXED` steps (`K_FIXED = K_MAX = 8` provisional). FIXED is the control arm against which any adaptive policy must earn its place. `stop_reason = FIXED_DEPTH`.

### 2.3 Adaptive candidate: CONVERGENCE (deterministic, outcome-independent)

Selected as the first adaptive candidate because it needs no halting target, no learned halt head, and cannot see outcomes.

- Per example `b`, after computing `z_{k+1}`: `r_b = ||z_{k+1,b} - z_{k,b}||_2 / max(||z_{k,b}||_2, 1e-6)`, norms taken over `(T, d_model)` with the packet's valid-token mask applied.
- Halt example `b` at the first `k+1 >= K_MIN` with `r_b < conv_tau`; `stop_reason = CONVERGED`, `depth_used = k+1`.
- If no halt by `K_MAX`: `stop_reason = MAX_DEPTH`, `depth_used = K_MAX`.
- `K_MIN = 1`, `K_MAX = 8`, `conv_tau = 1e-3`, all registry constants of the halt schema, not tuning knobs during blind days.

### 2.4 Per-example masking

- `active_b` is a per-example boolean, all true at `k=0`. Once false it never becomes true again in that forward.
- Frozen examples keep their state: `z_{k+1,b} = z_{k,b}` where `active_b` is false, applied as a mask after the cell computes on the whole batch. The cell may run on halted rows; their result is discarded by the mask. Loss and heads read `z_{depth_used_b, b}`, which is exactly the frozen state.
- Batch composition must not change any example's depth or output (acceptance H2). The trunk's attention is per sequence and the reasoning cell has no cross-batch operation, so this holds by construction; the test proves it.
- The loop terminates as soon as no example is active, but output is identical whether it terminates early or runs to `K_MAX` with all rows frozen.

### 2.5 Training treatment

- FIXED: unroll `K_FIXED`; standard loss on `z_{K_FIXED}`.
- CONVERGENCE: the same rule runs in training and eval with the same constants. Gradients flow through the steps an example executed; the freeze mask is a hard mask (no straight-through, no ponder cost). Loss is on the frozen final state. There is no halting loss in V1 because nothing is learned about halting.
- Deferred to promotion: ACT/PonderNet-style learned halting with a ponder penalty, halting on head-confidence, and any halting target. Each requires a new halt schema id and a control against CONVERGENCE.

### 2.6 Receipt

`HaltReceipt` fields are carried inside `RecurrenceReceipt` (section 1.8): `halt_schema="BOSS_B1_HALT_V1"`, `policy`, `k_min`, `k_max`, `conv_tau`, per-example `depth_used`, `stop_reason` in {FIXED_DEPTH, CONVERGED, MAX_DEPTH}, and per-example `r_trace` (the `r_b` sequence, diagnostic). Every stop is receipted; there is no silent stop.

### 2.7 Acceptance criteria (L-B1)

- H1 FIXED equals plain B1: under FIXED with `K_FIXED=k`, output equals `B1Reasoner` run for `k` steps with no halting code path.
- H2 Batch independence: for CONVERGENCE, `depth_used` and output of example `b` are identical in a batch of 1 and in a batch of 32 with different neighbours.
- H3 Cap: no example reports `depth_used > K_MAX`; an example with `conv_tau = 0` reports `MAX_DEPTH`.
- H4 Monotone freeze: for every example, `z_{k,b}` is constant for all `k >= depth_used_b`.
- H5 Determinism: two eval forwards produce identical `depth_used`, `stop_reason`, and logits.
- H6 Structural separation: the halting function's signature accepts only `(z_prev, z_next, valid_mask, k, constants)`; a test asserts no parameter name matches target, label, outcome, confidence, or disposition; the decision-contract validator has no parameter or field named depth or stop_reason.
- H7 Receipt completeness: every example in every forward has exactly one `stop_reason`.

---

## 3. C15 normalizer completion: `C15_NORM_ONLINE_V1`

R2 section 9 stands (bounded exact window `N_NORM=4096`, median/MAD, `CLIP_Z=8.0`, PRESENT-only fitting, identity normalizer for mechanics tests, prefix-extension invariance). This section finishes it.

### 3.1 Scope of a normalizer state

One state per `(instrument_id, column)` for instruments in the declared target universe (the same registry payload that declares `tick_raw` per instrument). Columns are the 19 candidate slots; ABLATED slots hold no state.

### 3.2 Order of operations at cutoff `c` (exclusive window)

1. Compute the column's raw value `v_c` and state (PRESENT/MISSING/INVALID/ABLATED) from the builder.
2. Compute `z_c` from the window as it stands BEFORE `v_c` is inserted: the window contains PRESENT raw values from cutoffs strictly less than `c`.
3. If `v_c` is PRESENT and the phase is UPDATING, insert `v_c` into the window (evicting the oldest beyond `N_NORM`).

The current observation therefore enters after normalization, never before. Rationale: `z_c` is then a pure function of the prefix strictly before `c`, so "transform" and "update" are two separately checkpointable steps, and a value can never shrink its own z by widening the scale it is measured against. This tightens R2's "cutoffs <= c" to "cutoffs < c"; it is a clarification, not a reversal.

### 3.3 Warmup boundary (exact)

Let `n_c` be the number of PRESENT raw values at cutoffs `< c` for this `(instrument, column)`. The column is emitted MISSING `NORM_WARMUP` while `n_c < N_WARM` (`N_WARM = 256`). The first PRESENT-emitted z is at the first cutoff whose window already holds 256 PRESENT values. MISSING and INVALID observations never count toward `n_c` and never enter the window. Warmup is per `(instrument, column)`; a column can be warm on one instrument and not another.

### 3.4 Scale floors (provisional registry constants, declared per column in the column's own post-transform units)

| Columns | Unit | `SCALE_FLOOR_c` |
|---|---|---|
| A1, A2 (log1p seconds) | nats | 0.05 |
| A3 (HHI share) | share | 0.02 |
| B1 (log1p size difference) | nats | 0.05 |
| B3 (rate) | share | 0.02 |
| B2, C1a, C1b (blocked; declared for the record) | share | 0.02 |
| D1, D2, D5 (log1p group counts) | nats | 0.10 |
| D3 (log step ratio) | nats | 0.05 |
| D4, D6 (log1p ticks) | nats | 0.10 |

`scale = max(1.4826 * MAD, SCALE_FLOOR_c)`. Floors exist so a column that is PRESENT but nearly constant during a quiet stretch does not amplify noise to the clip; the Oct 1 mechanics probe reports the fraction of cutoffs where the floor binds per column, and the owner rules on the numbers before lock. Floors are never fitted.

### 3.5 Phase behaviour

| Phase | Scope kind | Normalizer mode | State at phase start | State hash bound where |
|---|---|---|---|---|
| MECHANICS_OCT1 | PROBE_ONLY | UPDATING | empty (all columns in warmup) | per-batch in `C15BuilderState.state_hash` |
| VALIDATION_OCT3 | PROBE_ONLY or RESULT_BEARING | FROZEN | restored from the end-of-Oct-1 export | `DipoleTargetSpec.normalizer_id` |
| LOCKED_HOLDOUT (Oct 4/5) | RESULT_BEARING | FROZEN | the lock-time state, which is the same end-of-Oct-1 export | `DipoleTargetSpec.normalizer_id` and the LockReceipt |

- FROZEN means transform only; step 3 of section 3.2 is skipped. A column still in warmup at freeze time stays MISSING `NORM_WARMUP` for the whole frozen phase; it does not warm up on validation or held-out data.
- There is no automatic reset. A source-member boundary does not reset normalizer state (unlike the D-machine, section 4). Reset happens only by constructing a new builder under a new phase authorization, which is a new `normalizer_id`.
- `normalizer_id` format: `C15_NORM_ONLINE_V1:UPDATING` during MECHANICS_OCT1; `C15_NORM_ONLINE_V1:FROZEN:<state_hash>` in frozen phases; `C15_NORM_IDENTITY` for mechanics known-answer tests. A frozen phase whose `normalizer_id` does not carry the state hash is a defect.
- Oct 3 contributes no statistic (R2 decision); Oct 1 is the only source of normalizer statistics for this candidate.

### 3.6 Export/restore

Per `(instrument, column)`: `values` (the exact window, insertion order, up to `N_NORM` float64), `n_present` (count since phase start, for warmup), `mode`. `state_hash = sha256("C15_NORM_ONLINE_V1" || 0x00 || canonical_bytes(export))`. Restore verifies the hash and refuses a state whose `mode`, `N_NORM`, `N_WARM`, floors, or clip differ from the constructing config. Median/MAD are recomputed from `values`, never stored.

### 3.7 Acceptance criteria (L-NORM)

- N1 Exclusive window: at the 257th PRESENT observation the emitted z uses exactly the previous 256 values; inserting the 257th value first changes z (a test that constructs both orders and asserts they differ, then asserts the implementation matches the exclusive one).
- N2 Warmup boundary: cutoffs with `n_c` in `[0, 255]` are MISSING `NORM_WARMUP`; `n_c = 256` is PRESENT; a MISSING observation at any point does not advance `n_c`.
- N3 Floor binds: a column fed 300 identical PRESENT values emits z exactly `0.0` (not NaN, not clipped) and reports `floor_bound = True`.
- N4 Frozen phase: after restore in FROZEN mode, 1,000 further PRESENT values leave `state_hash` unchanged and every z is computed against the restored window.
- N5 Prefix invariance: for any cutoff `c`, appending arbitrary suffix values (including duplicates and equal timestamps) leaves `z_c` bit-identical (float64 compute, float32 emit).
- N6 Export/restore identity: continuous run versus export-at-every-cutoff-and-restore yields identical z sequences and identical final `state_hash`.
- N7 Bounded: memory is exactly `N_NORM` values per `(instrument, column)`; no history beyond the window.
- N8 Ablated slots hold no state and never emit PRESENT.

---

## 4. C15 state machine: two explicit reconciliations

### 4.1 Section 5.2 chain-break transition (explicit)

Add the boolean `broken` to the state. Replace R2 rules 4, 5, and 6 with the following. All other rules are unchanged; `E` is retained on a break as R2 states.

Rule 4/5 merged (not a new extreme, `x_i <= E`):
```
age += 1
if x_i < E:
    pull_depth = max(pull_depth, E - x_i)
    if not broken:
        armed = armed or pull_depth >= P_PULLBACK_TICKS
        if pull_depth >= R_BREAK_TICKS:
            broken = True; armed = False
            n_ext = 0; E_prev = None; m_last = m_prev = None
            p_last = p_prev = None; g_E_prev = None
# while broken: pull_depth keeps tracking (diagnostic), no re-break, no arming
```
Rule 6 (new extreme, `x_i > E`):
```
if broken:
    # fresh chain restarts at extension 0 on this extreme
    broken = False; n_ext = 0
    (m_*, p_*, E_prev, g_E_prev already cleared at the break)
elif armed:
    n_ext += 1; m_prev = m_last; m_last = x_i - E
    p_prev = p_last; p_last = pull_depth; g_E_prev = g_E
E = x_i; g_E = i; age = 0; armed = False; pull_depth = 0
```

Column availability while `broken`: D1 PRESENT (`log1p(age)`, age counted from the retained `E`), D2 PRESENT (`0.0`), D3-D6 MISSING `CHAIN_BROKEN`. At the restarting extreme: D1 `0.0`, D2 `0.0`, D3-D6 MISSING `NO_COMPLETED_STEP`. The pullback that caused the break is NOT credited as the first pullback of the new chain; a new chain needs a new pullback of at least `P_PULLBACK_TICKS` after its first extreme before an extension can complete. This is the literal reading of R2's "starts a fresh chain at extension 0".

Known-answer trace T-D (P=1, R=3): `x = 10, 11, 10, 12, 9, 13, 12, 14`
- g0 reset E=10. g1 E=11 (not armed). g2 pull 1, armed. g3 extension 1, E=12, m_last=1, p_last=1.
- g4 x=9: pull_depth=3 >= R: broken, n_ext=0, m/p cleared, E stays 12, age=1. D2 = 0, D3-D6 MISSING CHAIN_BROKEN.
- g5 x=13 > 12 while broken: restart, broken=False, n_ext=0, E=13, age=0, armed=False. D3-D6 MISSING NO_COMPLETED_STEP.
- g6 x=12: pull 1, armed. g7 x=14: extension 1 of the new chain, m_last=1, p_last=1. D4 = log1p(1), D5 = log1p(2), D3/D6 MISSING (n_ext < 2).

Acceptance (L-D): D1 the machine reproduces R2 traces T-A, T-B, T-C and this T-D exactly; D2 no transition reads a group later than `i` (a test feeds the sequence one group at a time and asserts the state after each step is independent of what follows); D3 `broken` never re-fires while already broken; D4 a break with `pull_depth >= R` on the same group that would have armed produces broken, not armed.

### 4.2 Section 5.5 lifecycle termination reconciled to the adapter

The adapter is the book authority, and its `_cancel` reduces `size` and removes the order only when the remaining size is zero. Fills arrive as `F`/`T` records with no book effect; the resting order's size change appears through subsequent `C` or `M`. R2's "C (any) terminates" is therefore replaced by:

- Termination event: an order in the cohort is terminated at the first event after which its `order_id` is absent from `book.orders`. In adapter terms that is `ApplyEffect.removed == True` (a `C` that reaches zero, an `R` clear, an `A` with `F_TOB` clearing the side), plus `modify_side_change` (the adapter removes and re-adds under the same id; identity does not survive a side change).
- Partial cancel (`C` with remaining size > 0): identity survives; `alive_j` stays 1 for C1a; `cur_size_j` decreases for C1b. Recorded as a retention event.
- Priority-losing `M` (price change or size increase): identity survives for C1a (unchanged from R2); `cur_size` updates for C1b; diagnostic counter increments.
- `F` records: not a termination by themselves. They are counted in the fill diagnostic per cohort order by `order_id`; the economic removal is credited when the matching `C`/`M` brings the size down, which is how B1 `size_removed` already counts (once per economic removal, section 4 of R2).
- Integrity: `cancel_missing_order`, `modify_missing_treated_as_add`, or a reset inside the window on any cohort order marks the cohort INVALID `MISSING_REFERENCE` / `RESET_IN_WINDOW`, unchanged from R2.
- The cohort snapshot at group `i-k` stores `orig_size_j = RestingOrder.size` at that snapshot and the `order_id`; `cur_size_j` at cutoff is `book.orders[order_id].size` if present, else 0.

Acceptance (L-D): D5 a cohort order partially cancelled 3 times then fully cancelled has `alive = 1` through the third partial and `0` after the full; C1b tracks `min(orig, cur)` at each step. D6 a fill (`F`) followed by a `C` to zero terminates at the `C`, not the `F`. D7 `modify_side_change` terminates. D8 a priority-losing `M` does not terminate and increments the diagnostic counter. D9 all lifecycle decisions are derived only from `ApplyEffect` fields and `book.orders` membership; the test injects a fake adapter effect stream and never constructs a book by hand.

---

## 5. Cross-lane identities (what every lane must bind)

| Identity | Producer | Consumers | Format |
|---|---|---|---|
| `packet_hash` | `causal_packet` | B1, halting receipt, decision contract | existing |
| `terminal_prefix_hash`, `receipt_hash` | `RecordPrefixChain` (patch 0005) | C15 builder, `C15BuilderState` | 64-hex |
| `normalizer_id`, normalizer `state_hash` | L-NORM | `DipoleTargetSpec`, `C15BuilderState` | section 3.5 |
| `candidate_digest` | registry (`BOSS_TEACHER_CANDIDATE_C15R2`) | builder, teacher spec `registry_id` | existing |
| `b1_code_sha`, `config_hash` | L-B1 | `RecurrenceReceipt`, model registry | blob SHA, sha256 of canonical config |
| `builder_code_sha` | L-D / L-INT | `DipoleTargetSpec` | existing field |

Hash convention everywhere: `sha256(DOMAIN || 0x00 || canonical_bytes(payload))` with `causal_packet.canonical_bytes` as the only serializer. No lane introduces a second serializer.

---

## 6. Workbook reconciliation (no duplicate implementation)

At `beb548b` the repository already contains `dipole_target.py` (DIPOLE_TEACHER_SCHEMA_V1 with PRESENT/MISSING/INVALID/ABLATED states, spec hash, masked MSE) and the repaired `teacher.py` controls (fixed random input projection for plain_aux, Sattolo derangement for shuffled, CPU-generator random). The workbook rows to reconcile rather than rebuild:

- C14 Dipole target schema: "Specified - not built" is stale; the schema is Built. The gap is the builder that populates it (C15), not the schema.
- C17 plain_aux and C18 shuffled/random: "Built - repair required" is stale for the code; move to "Built - preservation proof pending" and point G12/G14 at the existing tests rather than at new work.
- C13 qsv_mask: verify against `teacher.make_targets(dipole_mask=...)` and the trunk `qsv_mask` pass-through before changing status; do not re-implement.
- C15: stays Partial; add this addendum and patch 0005 as source evidence.

---

## 7. Deferred (named so no lane invents it)

- Truncated/no-grad-prefix recurrence training; depth curricula; recurrence regularisers (C19).
- Learned halting (ACT/Ponder), halting on confidence, any halting target, ponder cost (C20).
- Cross-packet state of any kind (C19, C20).
- Learned or weighted normalizer statistics; any Oct 3 contribution to statistics (C15).
- Registry constant changes (`P_PULLBACK_TICKS`, `R_BREAK_TICKS`, horizons, floors, `conv_tau`, `K_MAX`): only via a new candidate/schema id after the Oct 1 probe report.
- B2 absorption, C1 implementation, E1 promotion: blocked as in Codex R2 rulings.
- Observer hook, C15 builder, checkpoint slice: specified in the Round 3 memo, awaiting authorization after patch 0005 commits.
