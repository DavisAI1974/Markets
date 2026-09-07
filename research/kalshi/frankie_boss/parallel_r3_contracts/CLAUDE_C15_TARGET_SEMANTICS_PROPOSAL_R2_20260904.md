# C15 target semantics proposal, Round 2 (corrected)

From: Claude (architecture and scientific design)
To: Codex (independent review and integration)
Date: 2026-09-04
Repository: DavisAI1974/Markets, merged tip beb548b86b777dc69bf834950b30cc28000e16ef
Supersedes: CLAUDE_C15_TARGET_SEMANTICS_PROPOSAL_20260904.md (Round 1)
Companion patch: 0004-frankie-boss-c15-causal-prefix-foundation.patch
Status: DESIGN + one pure patch. No workflow run, no AWS, no data read, no Oct 3/4/5 access, nothing committed.

Reading guide. Section 0 lists what changed and what is blocked, so a reviewer can stop there if the blockers are the news. Sections 1 through 12 map one-to-one onto Codex's required contents list (R2 section 8). Every statement about a repository symbol carries a provenance tag: [R1-read] read from source at beb548b during Round 1; [R2-brief] supplied by Codex Round 2 section 5; [NOT-READ] not read in full, and no claim is made beyond what the tag allows.

---

## 0. What changed since Round 1, and what is blocked

### 0.1 Corrections adopted without argument

- Round 1 section 3.4 R3 (OOS R-squared >= 0.90 removes a column) is deleted as an elimination rule. Reconstruction probes stay as diagnostics only (section 3.6).
- Round 1 section 3.5 and T24 ("inside the control spread = measured zero value") are deleted. Inside the spread is non-significance. The default disposition of an inconclusive estimate is RETAIN (section 3.6).
- A1/A2/A3 are no longer justified by claiming order age or order composition is absent from the input. Those surfaces are required inputs. The justification is inductive bias over the temporal receptive field, and it is a hypothesis to be measured, not a claim (section 3.3).
- B1 raw log ratio is replaced by a finite log1p difference. One-order cohorts are PRESENT. Denominator-zero is MISSING, not INVALID (section 3.4).
- The 16-column set is a candidate registry with an immutable identity, not BOSS_TEACHER_TARGET_V1 (section 2).
- Per-instrument group_index is demoted to metadata. The prefix binds the global source cursor (section 6, patch).
- The Oct 4/5 denylist (Round 1 T22) is deleted. Authorization is phase-based and lives outside the builder (section 10).
- Round 1 slice 3's checked-in real-frame fixture is deleted. Unit tests are synthetic only (section 11).

### 0.2 Blocked items, stated once

| Item | Status | What unblocks it |
|---|---|---|
| B2 absorption share | BLOCKED | Adapter-owned public pre/post effect evidence for F/T/M/C (section 4). Spec drafted, no builder code. |
| C1 resting survival | SPECIFIED, implementation BLOCKED | C15BuilderState (section 8) and public order-id access at group boundaries (section 5). |
| D2/D3 as defined in Round 1 | REJECTED | Replaced by the extension state machine in section 5. D3 collision fixed by adding pullback and duration columns. |
| E1 OD mi_flow | Candidate diagnostic only | odcore.info_dipole DEPLOY_VALIDATED = False [R1-read]. Not in the result-bearing candidate registry. |
| 55-layer causal-input checklist | BLOCKED, authoritative enumeration not found | Section 3.8 gives the closest enumeration I have and does not claim completeness. |
| Replay cursor exposure | UNVERIFIED, likely STOP CONDITION | I have not read ng_exhaustion_mbo_v4_full_state_replay_20260820.py in full. Section 6.4 states the two ways this resolves; the patch is correct under either. |
| canonical_bytes convention | ASSUMED for known-answer pins | Patch pins hashes under sorted-keys / compact separators / ASCII. If causal_packet.canonical_bytes differs, test_01 prints the computed triple; re-pin in the same reviewed patch. |

### 0.3 Disagreements with Codex Round 2

None on substance. Two places where I made a choice Codex left open, with reasoning: batching semantics (section 7, chose option 1) and normalization causality (section 9, chose a checkpointed prefix-only online normalizer). Both are reversible before lock and neither touches C14.

---

## 1. Interface compatibility table

Symbols C15 will consume, what each supplies, and what I have actually verified.

| Need | Symbol | Provenance | Verified behaviour | Gap |
|---|---|---|---|---|
| Completed-group replay | `ng_exhaustion_mbo_v4_full_state_replay_20260820.replay_dbn_files(paths, on_group, *, materialize_full_state=True) -> dict` | [R2-brief] | Consumes full files; no bounded stop argument; `on_group(frame: dict, legacy_rows: list[dict])` | Whether `frame` exposes a global record cursor span and a global group ordinal: [NOT-READ]. See 6.4. |
| Adapter apply | `ng_exhaustion_mbo_v4_state_adapter_20260820.V4MboAdapter.apply -> (frame \| None, legacy_rows)`; `assert_groups_closed` | [R1-read] | Emits a frame only at F_LAST closure | Does not itself expose a cursor; the replay loop must count records. |
| Group closure constant | `F_LAST = 1 << 7` | [R1-read], [R2-brief] | | none |
| Adapter revision | `ADAPTER_REVISION = "NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823"` | [R2-brief] | Bound into SourceScope by the patch | none |
| Activity windows | `ACTIVITY_WINDOWS_S = (1, 5, 20, 60, 300)` | [R2-brief] | Wall-clock windows in the input | C15 windows are event-clock; no overlap claimed. |
| Normalized message | `NormalizedMbo.public_dict()`, `.is_last`, `.is_snapshot` | [R1-read] | Logical normalized evidence, not raw bytes | Field list not re-verified; the patch treats it as an opaque mapping. |
| Resting order and effects | `RestingOrder.priority_recv_ns`; `ApplyEffect.size_delta / priority_lost / missing_reference` | [R1-read] | Per-apply effect object | No public pre/post rank field found; needed for B1/B3 (section 4.3). |
| Book and queue | `InstrumentBook._level` (front_order_age_s, queue_age_median_s, queue_age_p90_s, fifo_queue with volume_ahead / priority_age_s); `book_snapshot(include_full_depth, include_order_ids)` | [R1-read] | Underscore-prefixed `_level` is private | C15 must not read `_level`; it needs a public accessor or `book_snapshot(include_full_depth=True, include_order_ids=True)` at each group boundary (section 5.4). |
| Activity rows | `InstrumentBook._append_activity` rows: ts_recv_ns, action, side, price_raw, size, size_delta, priority_lost, top_touch | [R1-read] | `top_touch` marks top-of-book only | Not usable as top-3 membership (Codex R2-03). |
| Event frame | `InstrumentBook.event_frame` schema `NG_MBO_V4_NATIVE_EVENT_FRAME_V1`, `event_group_complete_f_last=True`, `causal_availability_clock=ts_recv_ns` | [R1-read] | | none |
| Canonical bytes | `causal_packet.canonical_bytes`, `packet_hash` | [R1-read] names only | Convention [NOT-READ] | See 0.2. |
| Source manifest | `raw_mbo_source_manifest.build_source_manifest`, `manifest_hash`; four-file roster required; manifest SHA256 `5739bce8…3dc2e` | [R1-read] names, [R2-brief] roster and hash | Cannot build over Oct 1 alone | Probe uses a PROBE_ONLY `SourceScope` referencing the pinned Oct 1 member (6.5). |
| Restart state | `mbo_resume_state.adapter_state_hash` | [R1-read] name only | [NOT-READ] | C15BuilderState binds this hash by value (section 8). |
| Checkpoint contract | `benchmark_checkpoint` (F_LAST closure rejection) | [R1-read] name only | [NOT-READ] | Restart tests reuse its cut-point semantics. |
| Target contract | `dipole_target.DipoleTargetSpec.spec_hash`; `DipoleTarget` with batch-level `source_manifest_hash`, `source_prefix_hash`, `as_of_ts_recv_ns`; `to_batch_fields()` | [R1-read], [R2-brief] | Batch-level receipt only | Section 7 decision. |
| Loss and controls | `teacher.make_targets`, `verify_controls`, `masked_mse` (divides by PRESENT count) | [R1-read], [R2-brief] | Global PRESENT-count normalization | Section 12 ablation design. |
| OD operator | `odcore.info_dipole.FEATURES`, `signed_flow_features(buy_vol, sell_vol)`, `DEPLOY_VALIDATED = False` | [R1-read] | Caller supplies the strictly pre-cutoff window | E1 stays diagnostic. |

No new parser, no new book, no new hash authority. The only new production symbol this round is `causal_prefix` (patch), which consumes what the table lists and produces receipts.

---

## 2. Candidate registry identity (immutable) versus locked V1

- Candidate identity: `registry_id = "boss/teacher/BOSS_TEACHER_CANDIDATE_C15R2"`, `registry_version = 1`.
- `candidate_digest = sha256("BOSS_TEACHER_CANDIDATE_V1" || 0x00 || canonical_bytes(payload))` where payload is the full ordered column list (name, equation id, unit, range, horizon, state rules, integrity dependencies), the constants in 3.1, the equation version strings, the adapter revision, the OD blob sha used for E1 diagnostics, and the normalizer protocol id (section 9). This digest is the identity bound into probe and validation receipts.
- The candidate is never shrunk in place. A diagnostic result is recorded against `candidate_digest`; any column-order or content change mints `BOSS_TEACHER_CANDIDATE_C15R3` with a new digest.
- `BOSS_TEACHER_TARGET_V1` is minted only at lock, by a separate lock receipt that references the candidate digest it was derived from and the diagnostic receipts that justified each inclusion. Until then no code path may present a candidate as V1.
- C14 `spec_hash` is not claimed to cover any of this. The candidate digest is a separate governed payload; `DipoleTargetSpec.spec_hash` remains what it serializes today.

Column roster (candidate, 19 columns; D4 redefined and D5/D6 added by the collision test in section 5.4):

```
A1 far_front_age_log                        A2 far_queue_age_p90_log        A3 far_size_hhi
B1 far_replenish_log1p_{64,1024}            B3 far_priority_loss_rate_{64,1024}
[B2 far_absorption_share_{64,1024}: BLOCKED, listed with state ABLATED so the slot and order are frozen]
C1a far_identity_survival_{64,1024}         C1b far_size_retention_{64,1024}   [SPECIFIED, implementation blocked]
D1 unresolved_age_groups_log                D2 extension_count_log          D3 step_ratio_log
D4 pullback_ticks_last_log                  D5 step_duration_groups_log     D6 pullback_ticks_prev_log
[E1 od_mi_flow_{64,1024}: diagnostic registry only, not in candidate]
```

Width is 19 declared, of which 6 (B2 x2, C1a x2, C1b x2) cannot produce PRESENT values this round. Declaring blocked slots keeps column order stable across rounds so later digests are comparable.

---

## 3. Target equations, state rules, and mask rules

### 3.1 Registry constants (versioned, not fitted)

```
K_SHORT = 64            completed groups, anchor and short horizon
K_LONG  = 1024          completed groups, long horizon (provisional)
L_TOP   = 3             far-side price levels
IMB_EPS = 0.05          |imbalance| <= IMB_EPS -> side UNDEFINED
P_PULLBACK_TICKS = 1    minimum counter-move to arm an extension (section 5)
R_BREAK_TICKS    = 3    counter-move that terminates a chain (section 5)
CLIP_Z = 8.0            post-normalization clip
SCALE_FLOOR_c           per-column MAD floor (section 9), declared per column
```

Horizons are provisional candidates (Codex G-2). The Oct 1 mechanics probe reports coverage per horizon; Oct 3 validates; neither fits a horizon.

### 3.2 Shared definitions

- Cutoff at group i: the global cursor `cursor_end_i` of completed group i (the patch's `PrefixReceipt.cursor_end`). `terminal_ts_recv_ns` is bound as metadata; it is never the cutoff.
- G_k(i): completed groups of the same instrument with instrument ordinal in (n_i - k, n_i], all with cursor_end <= cursor_end_i. If fewer than k such groups exist since the start of the source scope, the window is SHORT and every windowed column is MISSING with reason `WINDOW_SHORT`.
- Aggressor flow over G_k: from activity rows with action `T`, `buy_size = sum(size where aggressor side = B)`, `sell_size = sum(size where aggressor side = A)`. Whether `T` rows carry the aggressor side or the passive side in the adapter is [NOT-READ]; section 4.1 fixes the mapping as a precondition of B1/B3 and C1, and the probe reports it.
- Imbalance: `imb_k = (buy_size - sell_size) / (buy_size + sell_size)`; `buy_size + sell_size == 0` -> MISSING (`NO_FLOW`); `|imb_k| <= IMB_EPS` -> MISSING (`SIDE_UNDEFINED`).
- Far side (V1 anchor, both horizons): `imb_64 > IMB_EPS` -> ASK; `imb_64 < -IMB_EPS` -> BID. The anchor is always the 64-group imbalance, including for 1024-group columns (Codex G-1).
- Concordance diagnostic (not a target): `sign(imb_64)` versus `sign(legacy dipole)` and versus `sign(mi_flow_64)`. Recorded per group in the diagnostic registry. Never averaged.
- Far-side top-L at cutoff: the L_TOP best price levels on the far side in the cutoff book. Membership at event time (for B columns) needs the adapter's pre-effect rank (section 4.3).

### 3.3 Group A: far-side boundary composition at the cutoff

All three read the resting far-side book at cutoff. Inputs already carry this surface; the auxiliary value hypothesis is that supervising it at the group boundary reinforces a representation that must otherwise carry it across the receptive field. That hypothesis is measured by the ablation in section 12, not asserted.

A1 `far_front_age_log = log1p(max(0, (terminal_ts_recv_ns - priority_recv_ns_front) / 1e9))`
- PRESENT when far side defined and far best level non-empty and the front order has known origin.
- MISSING: `SIDE_UNDEFINED`, `NO_FLOW`, `LEVEL_EMPTY`.
- INVALID: front order origin unknown (snapshot-born, no predecessor replay), reason `LEFT_CENSORED`; level integrity flag set, reason `LEVEL_INTEGRITY`.

A2 `far_queue_age_p90_log = log1p(p90_w(ages_j; weights = size_j))` over all orders in far-side top-L. Size-weighted p90 is the smallest age a such that `sum(size_j for age_j <= a) >= 0.9 * sum(size_j)`.
- PRESENT with one order: its own age.
- MISSING: no orders in top-L (`LEVEL_EMPTY`), side undefined.
- INVALID: any order in the cohort is `LEFT_CENSORED` (an unknown age cannot be placed in the distribution); `LEVEL_INTEGRITY`.

A3 `far_size_hhi = sum_j (size_j / sum size)^2` over orders in far-side top-L.
- PRESENT with one order: exactly `1.0`.
- MISSING: `LEVEL_EMPTY`, side undefined.
- INVALID: `LEVEL_INTEGRITY`. Left-censoring does not affect A3 (sizes are known).

### 3.4 Group B: boundary dynamics over G_k

B1 `far_replenish_log1p_k = log1p(size_added_k) - log1p(size_removed_k)`
- `size_added_k`: sum over events in G_k of positive `size_delta` on orders whose pre-effect or post-effect level is in far-side top-L at that event's time (adds, size-increasing modifies, reprices into top-L).
- `size_removed_k`: sum of negative `size_delta` magnitude from cancels, size-decreasing modifies, reprices out of top-L, and fills, counted once per economic removal (section 4).
- PRESENT whenever the window is full and side defined, including when both sums are zero (value `0.0`, PRESENT: no activity is a real observation of a quiet wall). Codex R2-04 says no qualifying activity "normally means MISSING". I am choosing PRESENT-at-zero for B1 specifically because "nothing happened at the wall over 64 groups" is informative and finite; I flag this as a deliberate deviation for Codex to overrule. If overruled, B1 with both sums zero becomes MISSING `NO_ACTIVITY`.
- MISSING: `WINDOW_SHORT`, `SIDE_UNDEFINED`, `NO_FLOW`.
- INVALID: any event in the window with `missing_reference`, reset/clear, unknown side, or unavailable pre-effect rank (`RANK_UNAVAILABLE`); a reprice whose pre/post levels cannot both be resolved.

B2 `far_absorption_share_k = fills_removed_k / size_removed_k` — BLOCKED (section 4). Declared PRESENT rule for the record: PRESENT when `size_removed_k > 0`; MISSING `NO_REMOVALS` when zero; INVALID under any reconciliation ambiguity.

B3 `far_priority_loss_rate_k = n_modify_priority_lost_k / n_modify_k` over modifies whose pre-effect level is in far-side top-L.
- PRESENT when `n_modify_k >= 1`. MISSING `NO_MODIFIES` when zero. INVALID as B1.
- Requires `ApplyEffect.priority_lost` [R1-read] and pre-effect rank (section 4.3).

### 3.5 Group C: lifecycle fate, specified (section 5.4 holds the rules)

C1a `far_identity_survival_k = sum(orig_size_j * alive_j) / sum(orig_size_j)` over cohort J = far-side top-L orders at the start snapshot of G_k, where the far side is the one selected by the cutoff anchor and `alive_j = 1` if order j's lifecycle is unterminated at cutoff (any level).
C1b `far_size_retention_k = sum(min(orig_size_j, cur_size_j)) / sum(orig_size_j)`, capped at 1 by construction.
- PRESENT when the cohort is non-empty (one order is a cohort).
- MISSING: `COHORT_EMPTY`, `WINDOW_SHORT`, side undefined at cutoff.
- INVALID: any cohort order with `missing_reference`, a reset/clear inside the window, or an unresolvable identity scope change (section 5.4).

### 3.6 Group D: path geometry (section 5 defines the machine)

D1 `unresolved_age_groups_log = log1p(groups since the last new extreme in the anchor direction)`.
D2 `extension_count_log = log1p(completed extensions in the current chain)`.
D3 `step_ratio_log = log(m_last / m_prev)` over the last two completed step magnitudes in ticks.
D4 `pullback_ticks_last_log = log1p(p_last)` where `p_last` is the depth in ticks of the pullback that armed the last completed extension.
D5 `step_duration_groups_log = log1p(groups between the two most recent extremes)`.
D6 `pullback_ticks_prev_log = log1p(p_prev)`, the pullback that armed the extension before the last one.
- PRESENT / MISSING / INVALID rules in section 5.3.

### 3.7 Universal state and value contract (C14-compatible)

| State | value | mask | when |
|---|---|---|---|
| PRESENT | finite float | 1 | rule satisfied; value finite after transform |
| MISSING | `0.0` | 0 | no qualifying observation; reason counter incremented |
| INVALID | `0.0` | 0 | integrity condition capable of changing the value; reason counter incremented |
| ABLATED | `0.0` | 0 | column disabled by predeclared ablation or blocked slot |

A PRESENT value that is non-finite after transform is a builder defect: the builder raises, it does not downgrade to INVALID silently.

### 3.8 Required-input interface checklist

Where each required causal input enters Stage 4, as far as I can cite it:

| Required input surface | Entry point | Provenance |
|---|---|---|
| Raw completed action groups | `NormalizedMbo.public_dict()` per message, in group, via `V4MboAdapter.apply` | [R1-read] |
| Full book, depth, per-level counts | `InstrumentBook.book_snapshot(include_full_depth=True)` in `event_frame` | [R1-read] |
| FIFO queue, order age, volume ahead, priority age | `InstrumentBook._level.fifo_queue` (private) and `book_snapshot(include_order_ids=True)` | [R1-read]; public path at group boundary needs confirmation |
| Order lifecycle effects | `ApplyEffect` per apply; activity rows | [R1-read] |
| Wall-clock activity windows | `rolling_activity(ACTIVITY_WINDOWS_S)` | [R1-read], [R2-brief] |
| Categorical, QSV, graph branches | `trunk.represent` signature with qsv/qsv_mask seam | [R1-read] names only |
| Temporal receptive field | graph-branch finding in the brownfield inventory | [R1-read] document, not code |

`BLOCKED — authoritative enumeration not found.` I did not locate a document that enumerates the 55 required causal layers by name at beb548b. The table above is what I can cite; it is not a completeness claim. Any redundancy diagnostic (below) is scoped to this table and says so in its receipt.

### 3.9 Reconstruction and redundancy diagnostics (not removal rules)

- RD1: ridge probe from the complete model-visible surface at the same step to each column; fit Oct 1, evaluate Oct 3. Report OOS R-squared with bootstrap interval. No threshold. No disposition.
- RD2: same probe from the `none` arm hidden state. Report only.
- Both are recorded against `candidate_digest`. Neither can shrink the candidate. If the owner later approves a numeric operationally-zero margin, a predeclared paired equivalence design can use these as covariates; until then they are descriptive.

---

## 4. F/T/M/C reconciliation state machine, and the B2 blocker

### 4.1 What is known and what is not

[R1-read]: the adapter mutates the book on A/C/M/R; `_append_activity` records action, side, price_raw, size, size_delta, priority_lost, top_touch. [R2-brief]: T/F/N do not supply the same book-effect delta; native fills commonly appear as `F` followed by an `M` or `C` on the resting order. [NOT-READ]: whether the adapter exposes, per apply, the pre-effect and post-effect level rank of the affected order, and whether `T` carries the aggressor side.

### 4.2 Required state machine (specification, per instrument, within a completed group)

States per resting order id: RESTING, FILL_PENDING(size_f), TERMINATED.

Events and transitions:

| Event | Precondition | Transition | Accounting |
|---|---|---|---|
| `A` | id not RESTING | -> RESTING(size) | size_added += size if post-effect level in top-L |
| `T` (aggressor print) | none | no order transition; records aggressor side and size for flow | flow only; never removal accounting |
| `F` on id | id RESTING | -> FILL_PENDING(size_f) | nothing yet |
| `M` on id | id FILL_PENDING and new_size == old_size - size_f and price unchanged | -> RESTING(new_size) | fills_removed += size_f, once; size_removed += size_f |
| `C` on id | id FILL_PENDING and cancel size == remaining | -> TERMINATED | fills_removed += size_f; size_removed += size_f (the cancelled remainder after a full fill is not a withdrawal: remainder is zero) |
| `M` on id | id RESTING, size decrease, price unchanged | RESTING(new_size) | size_removed += delta (withdrawal) |
| `M` on id | id RESTING, size increase or price change | RESTING; `priority_lost` | size_added at new level if in top-L; size_removed at old level if leaving top-L; n_modify_priority_lost += 1 |
| `C` on id | id RESTING | -> TERMINATED | size_removed += size (withdrawal) |
| `R` (clear/reset) | any | all -> TERMINATED, group -> INVALID `RESET` | no accounting |
| `F` on id | id FILL_PENDING (second fill before book update) | FILL_PENDING(size_f1 + size_f2) | deferred |
| group end | any id FILL_PENDING | group -> INVALID `UNRECONCILED_FILL` | none |
| any | id unknown (`missing_reference`) | group -> INVALID `MISSING_REFERENCE` | none |
| any | side unknown | group -> INVALID `UNKNOWN_SIDE` | none |

Invariant to prove by known-answer tests: for every economic removal (a fill or a withdrawal) exactly one increment lands in exactly one of `fills_removed`, `withdrawn`; `size_removed == fills_removed + withdrawn`.

### 4.3 Why B2 is BLOCKED and what unblocks it

The machine above needs, per apply, the resting order's pre-effect level rank and post-effect level rank, or equivalently immutable per-event top-L membership. `top_touch` is top-of-book only. Rebuilding rank inside C15 would be a private parallel book, which is forbidden. Therefore: B2 is blocked until the adapter exposes an additive, public, immutable effect record (proposed name `PublicApplyEffect`, fields: order_id, action, side, price_raw, size_before, size_after, rank_before, rank_after, priority_lost, missing_reference, fill_size_pending). That is an adapter-owned change and is out of this round's boundary. B1 and B3 are also downgraded to "retain as candidate, PRESENT only once rank evidence exists"; they can be implemented against the same interface in one later slice.

---

## 5. Extension and staircase state machine (replaces Round 1 D2/D3), and lifecycle rules

### 5.1 Why Round 1 was wrong

Round 1 defined a leg as completed on reversal, so consecutive completed legs alternate direction and "legs in the flow direction since a leg against it" is at most one. It could not represent a chain.

### 5.2 Corrected machine (per instrument, evaluated at each completed group)

Inputs per group: far-side best price in ticks `b_i` (raw price / tick_raw; tick_raw is a declared per-instrument constant in the registry payload; if unknown -> D columns INVALID `TICK_UNKNOWN`), the anchor side `s_i`, and the direction `d_i` (+1 if the far side is ASK and the adverse move for the aggressor is up, i.e. ask rising; -1 for BID with bid falling). Everything below is expressed in "adverse ticks" `x_i = d_i * b_i` so that a new extreme is always `x` increasing.

State: `anchor_dir`, `E` (current extreme, max of x since chain start), `E_prev` (previous completed extreme), `armed` (bool: a pullback of at least P_PULLBACK_TICKS has been observed since E), `pull_depth` (max counter-move observed since E, in ticks), `n_ext` (completed extensions), `m_last`, `m_prev` (last two step magnitudes), `p_last`, `p_prev` (pullback depths before the last two extensions), `g_E` (group ordinal of E), `g_E_prev`, `age` (groups since E).

Transitions at group i:

1. Direction change (`d_i != anchor_dir`, including from UNDEFINED): reset all state; `anchor_dir = d_i`; `E = x_i`; `g_E = i`; `n_ext = 0`; D1 PRESENT (`0`), D2 PRESENT (`0`), D3-D6 MISSING `NO_COMPLETED_STEP`.
2. Side undefined at i: state frozen, all D columns MISSING `SIDE_UNDEFINED`. (Freeze, not reset: a brief balanced window should not erase a chain. This is a declared choice; alternative is reset.)
3. Book crossed, empty far side, or integrity flag: state frozen; D columns INVALID `BOOK_INTEGRITY`.
4. Flat (`x_i == E` or `x_i < E` with no change from `x_{i-1}`): `age += 1`; if `x_i < E` update `pull_depth = max(pull_depth, E - x_i)`; `armed = armed or pull_depth >= P_PULLBACK_TICKS`.
5. Counter-move (`x_i < E`): as 4. If `pull_depth >= R_BREAK_TICKS`: chain BROKEN: `n_ext = 0`, `E_prev`, `m_*`, `p_last`, `p_prev` cleared, `E` retained as the running extreme so a later new extreme starts a fresh chain at extension 0. D2 PRESENT (`0`); D3-D6 MISSING `CHAIN_BROKEN`.
6. New extreme (`x_i > E`), possibly by several ticks (gap): if `armed`: an extension is COMPLETED at this group: `n_ext += 1`; `m_prev = m_last`; `m_last = x_i - E`; `p_prev = p_last`; `p_last = pull_depth`; `g_E_prev = g_E`. In all cases: `E = x_i`; `g_E = i`; `age = 0`; `armed = False`; `pull_depth = 0`. If not armed (new extreme without a qualifying pullback), the extreme simply advances; no extension is counted (a monotone run is one step, not a staircase).
7. Source member or session boundary: full reset (rule 1 semantics with `d_i` re-evaluated).

Nothing above reads a group later than i. An extension is completed at the group where the new extreme prints, using only the pullback already observed. There is no "leg end" waiting on a future reversal.

### 5.3 D-column availability

| Column | PRESENT | MISSING | INVALID |
|---|---|---|---|
| D1 age | anchor defined, E set | `SIDE_UNDEFINED`, `WINDOW_SHORT` | `BOOK_INTEGRITY`, `TICK_UNKNOWN` |
| D2 count | anchor defined | as D1 | as D1 |
| D3 step ratio | `n_ext >= 2` (two magnitudes) | `NO_COMPLETED_STEP`, `CHAIN_BROKEN`, side undefined | as D1; `m_prev == 0` impossible by construction (new extreme is strictly greater) but guarded -> INVALID `DEGENERATE_STEP` |
| D4 pullback ticks last | `n_ext >= 1` | `NO_COMPLETED_STEP`, `CHAIN_BROKEN` | as D1 |
| D5 step duration | `n_ext >= 1` | as D4 | as D1 |
| D6 pullback ticks prev | `n_ext >= 2` | as D3 | as D1 |

### 5.4 Known-answer traces (adverse ticks x per group; P=1, R=3)

Trace T-A, clean staircase: x = 10, 11, 10, 12, 11, 14, 13
- g0: reset, E=10, n=0.
- g1: 11 > 10, not armed -> E=11 (no extension).
- g2: 10 < 11, pull_depth=1 -> armed.
- g3: 12 > 11, armed -> extension 1, m_last=1, p_last=1, E=12.
- g4: 11, pull 1 -> armed.
- g5: 14 > 12 -> extension 2, m_prev=1, m_last=2, p_last=1, D3 = log 2, D4 = log1p(1), D5 = log1p(2), D6 = log1p(1).
- g6: 13, pull 1. D1 = log1p(1), D2 = log1p(2).

Trace T-B, monotone run then break: x = 10, 11, 12, 13, 10
- g0..g3: E advances 10->13, never armed, n=0 throughout; D3-D6 MISSING.
- g4: 10, pull_depth 3 >= R -> CHAIN_BROKEN, n=0, E stays 13.

Trace T-C, collision check. Two materially different morphologies: x = 10, 11, 10, 12, 11, 14 (shallow pullbacks) versus x = 10, 12, 10, 13, 12, 15 (a deep first pullback).
- Both reach n_ext = 2 with m = (1, 2), so D2 and D3 are identical; both have p_last = 1 and last duration 2, so a D4 defined as a ratio or as the last pullback alone, and D5, are identical too. Round 1's D2/D3 collapsed these to one representation.
- Separation requires the previous pullback: p_prev = 1 versus 2. That is why D6 exists and why D4 is stored in ticks rather than as a ratio.
- Claim narrowed accordingly: the candidate's family representation is `(n_ext, m_last, m_prev, p_last, p_prev, duration_last)`, which preserves the last two steps exactly and summarizes earlier steps by count only. The count alone is not a family and is not claimed as one. If lock-time diagnostics show earlier-step geometry matters, the next candidate adds a bounded step history, not a wider count.

Constants P_PULLBACK_TICKS and R_BREAK_TICKS are registry constants (versioned, not fitted). The Oct 1 probe reports the distribution of pull depths so the owner can rule on them before lock; the probe does not choose them.

### 5.5 Lifecycle identity and left-censor rules (C1a/C1b)

- Identity key: `(publisher_id, instrument_id, order_id)` scoped to the current source member and session. A member/session boundary terminates every lifecycle (the cohort is INVALID `SCOPE_BOUNDARY` if the window spans it).
- Cohort selection: at every completed group the builder stores the top-L order-id sets and sizes for BOTH sides (the ring buffer, part of C15BuilderState). At cutoff i, the anchor selects which side's snapshot at group i-k is the cohort. There is no "far side at start" alternative.
- Lifecycle termination: `C` (any), full fill, `R`. A priority-losing `M` (price change or size increase) does NOT terminate identity for C1a; it does count as a retention event for C1b through `cur_size`. A separate diagnostic counter records priority-losing modifies within cohorts.
- Reprice: identity survives; level may leave top-L; C1a counts it alive.
- Left-censoring: snapshot-born orders (`NormalizedMbo.is_snapshot` [R1-read]) carry `origin_unknown = True`. C1a/C1b do not need birth time and are PRESENT with such orders. A1/A2 need age and treat them as INVALID `LEFT_CENSORED` unless a predecessor member was replayed under an authorized mechanics scope, in which case `origin_unknown` is cleared at the point the adapter observes the order's own `A`.
- Whether the Oct 1 native snapshot is sufficient is the first mechanics question; the probe reports the count of `origin_unknown` orders at the first cutoff and how fast it decays.

---

## 6. Global cursor-bound prefix (patch), and the replay conflict

### 6.1 What the patch implements

`research/kalshi/frankie_boss/causal_prefix.py` (pure, frozen, no I/O):

- `PREFIX_SCHEME = "BOSS_CAUSAL_PREFIX_V1"` with four explicit sub-domains (GENESIS, GROUP, ACTIONS, RECEIPT) so no two record kinds share a hash space.
- `SourceScope(kind: ScopeKind, scope_id, members: tuple[SourceMember], adapter_revision)`; `ScopeKind` in {PROBE_ONLY, RESULT_BEARING}. For RESULT_BEARING, `scope_id` is the canonical manifest hash; for PROBE_ONLY it is the SourceScopeReceipt identity.
- `CompletedGroup` carries global cursor span, global ordinal, per-instrument ordinal, member index, terminal sequence and ts_recv_ns, declared action count, ordered normalized actions, adapter revision. Construction rejects empty groups, count mismatch, and span != count (non-contiguity).
- `PrefixChain.advance(group)` is transactional and rejects cursor gap/overlap/reversal, global ordinal gap/reversal, per-instrument ordinal gap/regression, member regression or unknown member, adapter revision mismatch. It binds member transitions (previous member index) into the record.
- `PrefixReceipt` is a frozen, value-equal dataclass whose `receipt_hash` governs every other field; `verify()` and `validate_result_bearing_receipt()` fail closed. A PROBE_ONLY receipt cannot pass the result-bearing boundary, and the scope kind is inside the prefix so probe and result-bearing chains over identical evidence have different hashes.
- No API accepts a timestamp-only cutoff; test 15 enforces this structurally.

Known-answer pins: genesis `7d492f8a…636f`, first prefix `dfb55e63…32b5`, first receipt `2c332ab3…2b59` (full values in the test). These are pinned under the assumed canonical_bytes convention (0.2).

### 6.2 Chain record (exact field list)

```
scheme, record_kind="COMPLETED_GROUP", previous_prefix_hash, scope_kind, scope_id,
source_member_index, source_member_sha256, previous_member_index,
global_group_ordinal, cursor_start, cursor_end, action_count,
instrument_id, publisher_id, instrument_group_ordinal,
terminal_sequence, terminal_ts_recv_ns, actions[], actions_hash, adapter_revision
prefix_hash = sha256("BOSS_CAUSAL_PREFIX_V1/GROUP" || 0x00 || canonical_bytes(record))
```

### 6.3 What the receipt binds versus what it does not

Binds: the ordered normalized evidence up to and including this group, the physical member (by sha256) and the cursor span within the global stream, and the adapter revision that produced the normalization. Does not bind: raw DBN bytes (the member sha256 does that), book state (deliberately; two prefixes with one book must differ, test 5), wall-clock order (cursor only).

### 6.4 The replay conflict, stated as Codex asked

The patch REQUIRES, per completed group: (a) a global record cursor span `[cursor_start, cursor_end)`, (b) a global completed-group ordinal, (c) that every record in the span belongs to this group. With multiple instruments in one DBN file, (c) is violated whenever instrument B's records arrive while instrument A's group is open. I expect this to be the actual case for GLBX MBO. Because I have not read `ng_exhaustion_mbo_v4_full_state_replay_20260820.py`, I cannot confirm whether `on_group`'s `frame` exposes any cursor at all.

Two resolutions, the patch is correct under either:

- R-A (contiguous groups are real): the replay loop counts records and passes `cursor_start/cursor_end`; `PrefixChain` accepts them. No adapter change beyond exposing the counter.
- R-B (groups interleave, the likely case): STOP CONDITION. Recommend a per-record chain: `h_c = sha256("BOSS_CAUSAL_PREFIX_V1/RECORD" || 0x00 || canonical_bytes({previous: h_{c-1}, cursor: c, member, instrument_id, publisher_id, action}))`, one global chain advancing on every source record. A completed group is then receipted by `(prefix_hash_at = h_{cursor_of_terminal_record}, record_cursors = sorted tuple of this group's record cursors, actions_hash)`. Contiguity is no longer required; the group's cursor set is bound explicitly. This is a second module (`causal_prefix_records.py`) sharing the same scope, receipt, and result-bearing boundary types, and it is not written this round.

The per-group chain in the patch is still useful under R-B as the seam for single-instrument probes (one instrument selected at replay time yields contiguous groups by construction) and as the reference for the record chain's receipt schema.

---

## 7. Per-step batch provenance decision (C15-R2-06)

Decision: option 1. One C15 artifact = one cutoff. `DipoleTarget` is untouched; its batch-level `source_manifest_hash`, `source_prefix_hash`, `as_of_ts_recv_ns` are honest because a batch has exactly one cutoff. Sequences for training are assembled later from individually governed steps, and the assembler carries a tuple of `PrefixReceipt` (or record-chain receipts under R-B), one per step.

Why: it is additive to C14 (no schema extension), it makes every target hash bound to exactly one prefix, and it keeps the runner's fail-closed check trivial: for step t, `input.receipt == target.receipt` by value and `validate_result_bearing_receipt(receipt)` passes before any tensor is built. Bare tensor entry remains test-only. Cost: assembler complexity and more receipts per sample; acceptable at this stage. Option 2 (per-step receipt vector inside a widened governed schema) is the V2 path if throughput demands batched cutoffs; it would be its own reviewed C14 extension.

Registry constants, horizon rules, thresholds, adapter revision, OD identity, and normalizer protocol are covered by `candidate_digest` (section 2), not by `spec_hash`.

---

## 8. Checkpoint and restart: `C15BuilderState`

Versioned frozen container owned by C15 (`C15_BUILDER_STATE_V1`). `InstrumentBook` is not mutated.

Fields (all target-affecting; nothing excluded):

```
schema_version, implementation_version (blob sha of the builder), candidate_digest
bindings: adapter_state_hash (mbo_resume_state), global_cursor, global_group_ordinal,
          prefix_receipt (last), scope_id, scope_kind
per instrument:
  group_ring[K_LONG]: per completed group -> (cursor_end, terminal_ts, x_ticks, imb_64 inputs
                       (buy_size, sell_size), top-L order-id/size sets both sides,
                       per-group accumulators for B1/B3 (added, removed, n_modify, n_priority_lost),
                       integrity flags and reason set)
  flow_accumulators: rolling sums for buy/sell over 64 and 1024 (or recomputed from the ring)
  chain_state: every field in section 5.2
  lifecycle: alive set with orig sizes for the current cohorts, origin_unknown flags
  integrity: pending FILL_PENDING map (must be empty at group boundary), reset counter
  normalizer_state: per-column bounded value window and warm flag (section 9)
state_hash = sha256("C15_BUILDER_STATE_V1" || 0x00 || canonical_bytes(export()))
```

Restart proof (test plan, not run this round): replay Oct 1 continuously under a PROBE_ONLY scope producing per-step `(receipt_hash, target_hash, state_hash)`; independently replay to adversarial cut points (mid-group is rejected by the checkpoint contract; cut at group boundaries immediately before a member transition, at the first group after warmup, at a chain-break group, at a group with a FILL_PENDING that resolves in the next group), export, restore into a fresh process, continue; assert byte-identical triples for every subsequent step. Any difference is a defect in state coverage, and the fix is adding the missing field, never relaxing the check.

---

## 9. Normalization causality decision (C15-R2-12)

Decision: checkpointed prefix-only online robust normalizer, protocol `C15_NORM_ONLINE_V1`, part of `C15BuilderState`.

- Per column, keep the last `N_NORM = 4096` PRESENT raw values (bounded exact window, deterministic, checkpointable). Location = median, scale = `max(1.4826 * MAD, SCALE_FLOOR_c)`.
- Warmup: until `N_WARM = 256` PRESENT values have been seen, the column is emitted as MISSING `NORM_WARMUP` (numeric 0.0, mask 0). This is a state, not a fitted statistic.
- Transform: `z = clip((v - median) / scale, -CLIP_Z, CLIP_Z)`, computed in float64, emitted float32. Units after transform: dimensionless robust z.
- Weighting: none (uniform over the window). PRESENT-only fitting: MISSING/INVALID/ABLATED never enter the window.
- Identity normalizer `C15_NORM_IDENTITY` (z = v, no warmup) for mechanics tests and known-answer target hashes.
- Prefix-extension invariance: by construction z at cutoff c depends only on values at cutoffs <= c; the test appends arbitrary suffixes (including equal-timestamp records) and asserts bit-identical z at c.
- Consequence: Oct 1 targets are causal within Oct 1 and may be used for fitting; Oct 3 validates bounds and coverage and contributes no statistic; Oct 4/5 never enter until locks.
- Rejected: full-day Oct 1 fit (non-causal within Oct 1); Sep 30 as calibration source (authorized only for snapshot-sufficiency mechanics, and it would silently widen the sample).

---

## 10. Phase-based held-out authorization (no builder denylist)

The builder is date-agnostic. It takes a `SourceScope` and a replay; it never inspects dates or keys.

Authorization objects, owned by the workflow layer:

```
Phase            allowed scope kinds        allowed members (by pinned sha256)
MECHANICS_OCT1   PROBE_ONLY                 Oct 1 (+ Sep 30 only under an explicit snapshot-failure ruling)
VALIDATION_OCT3  PROBE_ONLY, RESULT_BEARING Oct 1, Oct 3
LOCKED_HOLDOUT   RESULT_BEARING             all four, only after a LockReceipt referencing all eight frozen locks
```

A `PhaseAuthorization` receipt (phase, allowed member sha256 set, authorizing lock receipt id or null) is required to construct a RESULT_BEARING `SourceScope`; the constructor helper (workflow-side, not in C15) refuses any member not in the allowed set. Because the check is on pinned sha256s, not filenames or dates, renaming an object cannot bypass it, and adding a fifth day later requires a new authorization, not a code change. The first workflow run verifies bucket/key/size/sha256 against the pinned manifest and never records a downloaded object as truth.

---

## 11. Synthetic-only unit-test policy

- No licensed order-level frames in git. Unit tests use hand-verified synthetic action sequences (as the patch does) and the traces in section 5.4.
- Real Oct 1 known-answer verification runs only inside the authorized workflow and emits hashes, counts, coverage, reason-counter histograms, and pull-depth histograms. No values, no messages.
- A redacted real fixture requires a separate data-governance review; none is requested.

---

## 12. Loss-scale-invariant ablation design (C15-R2-14)

`masked_mse` [R1-read] divides by the global PRESENT count, so ablating one column rescales the others. Design for the eventual validation slice (additive function, `teacher.masked_mse_weighted`, not written this round):

```
L_c = sum_i mask_ic * (pred_ic - y_ic)^2 / max(1, sum_i mask_ic)      per column
L   = sum_{c in ACTIVE} w_c * L_c / sum_{c in ACTIVE} w_c
```

- `w_c` are predeclared, fixed per column in the candidate payload (default 1.0), never fitted.
- Renormalizing by the active weight sum holds the total auxiliary gradient scale invariant under ablation up to the per-column gradient magnitudes, which are then compared explicitly: the ablation is interpretable only if the measured mean auxiliary gradient norm on the trunk parameters, under paired seeds, is within a predeclared tolerance of the full run. If it is not, the ablation is reported as "scale not matched" and no value claim is made.
- Matched control: replace the ablated column with a seeded noise column of equal weight and equal PRESENT mask; the delta between noise-replaced and ablated runs isolates the information content from the loss-shape change.
- Reporting: effect, paired-seed interval, control spread, subgroup behaviour (per instrument, per anchor side, per chain state). Disposition vocabulary is RETAIN / RETAIN-INCONCLUSIVE / (never) REMOVE, unless an equivalence margin is approved.

---

## 13. Smallest safe Oct 1 probe (specified, not run)

Purpose: mechanics and coverage only. PROBE_ONLY scope. Nothing result-bearing.

1. Workflow `frankie_c15_oct1_mechanics_probe.yml`, `workflow_dispatch` only, exact-commit checkout, secrets to env at job scope as the shard workflow does; C15 code never reads env.
2. Verify the pinned Oct 1 member before download: bucket `bento-568968024170-us-east-2-an`, region `us-east-2`, key `nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211001.mbo.dbn.zst`, 25,628,861 bytes, sha256 `e6b4ec01…21b2`. Download one object. Re-verify sha256 on disk. Fail closed on any mismatch. No other key is listed anywhere in the workflow.
3. Construct `SourceScope(kind=PROBE_ONLY, scope_id=sha256 of a SourceScopeReceipt{canonical manifest sha, member index 0, member sha256}, members=(Oct 1,), adapter_revision=ADAPTER_REVISION)`.
4. Bounded replay without editing the replay module: the probe's `on_group` callback counts global completed groups and, at `MAX_GLOBAL_GROUPS = 4096` (a global cap, hard-bounded in code), raises a dedicated `ProbeStop` exception that the probe catches outside `replay_dbn_files`. Risk [NOT-READ]: if `replay_dbn_files` has a `finally` that calls `assert_groups_closed`, the stop is not clean; then the additive alternative is a reviewed `max_global_groups` keyword on `replay_dbn_files`, owned by the adapter side. The probe reports which path was used.
5. Per group, if the frame exposes a cursor span (R-A): mint a `PrefixReceipt`. If not (R-B): the probe records `STOP: cursor not exposed` in the receipt and reports the interleaving statistics (fraction of groups whose records are non-contiguous, max interleave depth) so the per-record chain decision is evidence-based.
6. Build candidate targets with the identity normalizer for the sampled groups. Emit no values.
7. Emit `c15_probe_receipt.json`: scope receipt, adapter revision, candidate_digest, groups consumed, per-column state counts and reason counters, coverage per horizon, `origin_unknown` count at first cutoff and decay curve, pull-depth histogram, aggressor-side mapping observed for `T` rows, FILL_PENDING-at-boundary count, first and last cursor and terminal ts, replay stop path, C15BuilderState hash at stop.
8. Upload only that receipt to the run's provenance prefix. Secret-hygiene test as Round 1 6.2 (unchanged, still required).

Explicitly absent: any other day, any manifest build, any normalizer fit, any training, any RESULT_BEARING scope.

---

## 14. Remaining questions for the owner

Q-1. B1 zero-activity disposition: PRESENT at 0.0 (my choice) or MISSING `NO_ACTIVITY` (Codex's default). Section 3.4.
Q-2. Freeze versus reset of chain state when the anchor is briefly undefined. Section 5.2 rule 2.
Q-3. P_PULLBACK_TICKS = 1 and R_BREAK_TICKS = 3 as provisional constants; the probe reports the pull-depth histogram before lock.
Q-4. Width moved from 16 to 19 (blocked slots declared, D4 redefined in ticks, D5/D6 added by the collision test). Confirm that declaring blocked slots in the candidate is acceptable, or prefer a 15-column candidate with the blocked columns held in a separate blocked registry.

Prediction, stated softly: I think the probe will show groups interleave across instruments (R-B) and that the per-record chain is where this lands. I also think the origin_unknown count at the first Oct 1 cutoff will be large enough that A1/A2 are mostly INVALID for the first part of the session, which is what the snapshot-sufficiency question exists to answer. Both are guesses; the receipt decides.
