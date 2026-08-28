# A-clean REAL_TIME_FRANKIE Non-Averaged Extraction Opportunities

## Retrospective provenance and controlling rule

This positive opportunity memo was produced retrospectively from read-only inspection of the intact first A-clean native runtime at `/workspace/scratch/da00127ac123/a-clean-runtime-33161766927`, its canonical native ledger and manifest, its adapter checkpoints, the canonical V4 adapter/full-state replay machinery, and the positive carry-forward artifact. The current controlling mission composition was loaded in full with these exact bindings:

| Mission component | SHA-256 |
|---|---|
| Original scientific RT mission | `442cc84c524feb6306224a6ba7e6984a21605c7a515c651b52c77bc279e2b2ef` |
| Native positive-discovery addendum | `ae4209670d37c2f324c17c3fa39cce8f7b45d273773f5b9070a00831b2626f48` |
| Controlling mission composition | `1d936286839e8aede6540f4bc700695f47733b8af60cf77a37518a48eca93840` |

The first replay's per-source-day `first`/`last`/`min`/`max`/arithmetic-`mean` summaries for the eight book dimensions remain intact in their dedicated diagnostic channel.

Every new extraction below uses the mission's parallel-view rule. The exact member-level view and the averaged analytical view are coequal when each yields valuable information. Every result record should carry:

`view_type`, `population_selector`, `denominator_n`, `source_day`, `family_id`, `subfamily_id`, `side_sequence`, `session_id`, `causal_phase`, `event_clock_basis`, `receive_clock_basis`, `availability_clock_basis`, `member_group_refs`, `metric`, and `value`.

An exact-versus-average difference produced by population, family, side, session, phase, granularity, or clock is recorded as `COMPLEMENTARY_SCOPE_DIFFERENCE`. Each estimand keeps its own definition and evidence. Arithmetic companions stay within one exact family/subfamily, side stratum, session, causal phase, source day, and clock basis.

## Key answer

The first native run contains substantially more positive causal information than the already verified family inventory. The held-out ledger directly exposes 1,441 distinct action strings and 1,976 action-plus-side strings on October 4, followed by 1,509 and 2,094 on October 5. It contains reproducible larger fill/cancel cascades, mixed cancel/modify branches, add-interleaved trade groups, large multi-price burst groups, repeated family chains, homogeneous queue-mutation runs, session restart neighborhoods, and cross-group same-order depletion runways.

The 18 adapter states and their checkpoint chain also verify deterministic access to full resting orders, FIFO order-ID queues, priority receive clocks/sequences, last-update clocks, and causally ordered 300-second activity tails. Restoring these exact checkpoints and continuing through canonical DBNs can materialize full book/FIFO state before and after every selected F_LAST group, turning the ledger-resident structures into queue depletion, replenishment, absorption, pre-birth, recognition, dipole, and strategy-feasibility research objects.

## A. Directly extractable now from the intact ledger and snapshots

### A1. Open-world action and side taxonomy beyond the carried families

The complete action-string census already reveals scalable and mixed-disposition extensions:

| Additional exact family | 2021-10-04 groups | 2021-10-05 groups | Positive mechanical finding |
|---|---:|---:|---|
| `TFC` | 7,950 | 8,268 | Every trade size equals its fill size; every fill ID reappears in the terminal F_LAST cancel. Single-price groups: 7,948/7,950 and 8,261/8,268. |
| `TFFCC` | 829 | 912 | Terminal cancel carries F_LAST. Every one of 1,658 and 1,824 fill-action IDs reappears among the later cancels. |
| `TFFFCCCN` | 2,193 | 2,382 | Three-fill extension: all 6,579 and 7,146 fill-action IDs reappear among later cancels; every group has neutral F_LAST. |
| `TFFFFCCCCN` | 664 | 803 | Four-fill extension: all 2,656 and 3,212 fill-action IDs reappear among later cancels; every group has neutral F_LAST. |
| `TFFFFFCCCCCN` | 207 | 321 | Five-fill extension: all 1,035 and 1,605 fill-action IDs reappear among later cancels; every group has neutral F_LAST. |
| `TFFCM` | 404 | 421 | Across two fills per group, 404/421 fill-action IDs continue into `C` and 404/421 into `M`, preserving split post-fill disposition with F_LAST on `M`. |
| `TFFCMN` | 313 | 360 | The same split cancel/modify disposition receives a separate neutral close: 313/360 fill IDs continue into each terminal branch. |
| `TFTFCMN` | 183 | 189 | Two ordered `T→F` contacts split into one cancel-linked and one modify-linked fill, then neutral close. |
| `TFACN` | 448 | 471 | `A` is inserted before the cancel; all 448/471 fill IDs later cancel. Principal side structure is `BABAN`. |
| `TFCAN` | 409 | 416 | `A` follows the cancel; all 409/416 fill IDs later cancel. Principal side structure is `ABBAN`. |

Concrete exact members show why these are separate subfamilies:

- Group 1,162,754 is `T(A,3) → F(B,1) → F(B,1) → F(B,1) →` three same-ID `C(B,1) → N`, all at 5.744; event `2021-10-04T00:02:52.520421089Z`, first receive `00:02:52.520776644Z`, F_LAST `00:02:52.520801298Z`.
- Group 1,171,586 is a size-seven ask trade split across bid fills of 1/2/3/1, followed by four matching cancels and `N`, all at 5.724; F_LAST forms 26,040 ns after first receive.
- Group 1,162,421 is `T(B,2) → F(A,1,id=786260852423) → F(A,1,id=786260852588) → C(first id) → M(second id,F_LAST)` at 5.734.
- Group 1,164,841 is `T(B,1) → F(A,1) → A(B,1,5.760) → C(A,1,5.759) → N`, preserving replenishment and withdrawal order inside one group.

**Exact member-level calculation.** Emit every group under its full action string, full side string, group ID/hash, ordered actions, order IDs, prices, sizes, event clock, first receive, component receives, and F_LAST availability. Compute exact per-day counts and the full member roster for each content-derived family/subfamily.

**Averaged analytical companion.** Within one fixed `(source_day, exact action family, exact side sequence, session, causal phase, ts_recv clock)` population, calculate arithmetic means for trade size, component count, priced-action span, distinct price count, distinct order-ID count, fill/cancel/modify quantity, and first-receive-to-F_LAST formation time. Record `denominator_n` as the exact group count and retain every member reference beside the mean.

### A2. Large burst-cascade groups as exact high-multiplicity clusters

Two held-out members demonstrate a much deeper cascade surface:

| Group | Exact action composition | Exact side composition | Prices / nonzero order IDs | Event / first receive / F_LAST | Formation |
|---:|---|---|---:|---|---:|
| 1,754,546 | 42 `T`, 107 `F`, 101 `C`, 2 `A`, 1 `N` = 253 actions | A=44, B=208, N=1 | 32 / 115 | `14:00:43.393163909Z` / `14:00:43.398485027Z` / `14:00:43.404169835Z` | 5,684,808 ns |
| 3,829,652 | 53 `T`, 110 `F`, 95 `C`, 14 `A`, 1 `M`, 1 `N` = 274 actions | A=139, B=52, N=83 | 22 / 136 | `17:29:15.960857981Z` / `17:29:15.965512037Z` / `17:29:15.974473826Z` | 8,961,789 ns |

These are exact, multi-price, multi-order execution clusters whose internal ordering can reveal repeated contact, partial absorption, concurrent replenishment, and final withdrawal without compressing the group.

**Exact member-level calculation.** Preserve the full raw action path and derive ordered per-price and per-order subsequences: trade-to-fill matching, cumulative filled quantity, cumulative cancel/modify/add quantity, first/last contact per price, side flips, and F_LAST formation clocks. Each burst retains its own action string and group identity.

**Averaged analytical companion.** For repeated members of the same exact action-string and side-string subfamily within one source day/session/phase, compute arithmetic means of action count, trade/fill/cancel/add/modify quantity, distinct price count, distinct order count, formation time, and per-price contact count. A singleton exact subfamily has `denominator_n=1`; its arithmetic companion equals the member value and remains explicitly labeled as such.

### A3. Exact cross-group same-order depletion runways

Order `786260864394` supplies a directly observed three-group causal chain:

1. Group 1,166,147: `AN` adds ask size 3 at 5.758; event `2021-10-04T00:07:47.335768709Z`; first component receive `00:07:47.335984267Z`; F_LAST availability `00:07:47.336003229Z`.
2. Group 1,166,161: `TFMN` fills 2 and modifies the same order to residual size 1; event `00:07:51.633134933Z`; first receive `00:07:51.633461326Z`; F_LAST `00:07:51.633499294Z`.
3. Group 1,166,162: immediate `TFCN` fills and cancels the residual size 1; first receive `00:07:51.633519694Z`; F_LAST `00:07:51.633590258Z`.

The add group's lawful availability precedes first-fill event time by 4.297131704 s and first-fill receive time by 4.297458097 s. The second depletion group begins 20,400 ns after the first depletion group closes and completes the same order 90,964 ns after that first close. This is an exact pre-contact → partial depletion/resizing → residual completion runway.

**Exact member-level calculation.** Join actions by `(instrument_id, order_id)` in causal `ts_recv_ns` order. Retain every add, priority-changing modify, priority-retaining modify, fill detail, cancel, price/side/size state, group boundary, and lawful clock. Derive exact order birth, queue-entry age, first contact, residual sizes, inter-group gaps, and terminal disposition.

**Averaged analytical companion.** For one fixed content-derived lifecycle family such as `(AN → TFMN → TFCN, same order ID, same side, same price, same session/phase)`, compute arithmetic means of birth-to-first-contact lead, first-contact-to-recognition latency, inter-group gap, total lifecycle duration, filled fraction at each stage, and residual quantity. The denominator is the number of exact lifecycle members in that same stratum.

### A4. Family transitions, recurrence, and homogeneous runs

Immediate family-to-family edges already form non-averaged runway candidates. Exact same-side recurrence counts for October 4/5 include `TFCN/BAAN → TFCN/BAAN` 564/518, `TFCN/ABBN → TFCN/ABBN` 506/502, `TFM/BAA → TFM/BAA` 381/375, and `TFM/ABB → TFM/ABB` 371/497. Mirrored cascade contraction appears as `TFFCCN/BAAAAN → TFCN/BAAN` 77/73 and `TFFCCN/ABBBBN → TFCN/ABBN` 67/92.

Longest exact consecutive runs further expose distinct persistence:

| Family | October 4 exact longest run | October 5 exact longest run |
|---|---|---|
| `TFCN` | 4 groups, 1,660,925–1,660,928 | 4 groups, 3,650,191–3,650,194 |
| `TFFCCN` | 2 groups, 1,165,325–1,165,326 | 3 groups, 3,688,079–3,688,081 |
| `TFM` | 8 groups, 1,807,483–1,807,490 | 8 groups, 4,069,473–4,069,480 |
| `TFMN` | 7 groups, 1,403,834–1,403,840 | 3 groups, 2,979,689–2,979,691 |
| `TN` | 5 groups, 1,672,112–1,672,116 | 6 groups, 3,236,190–3,236,195 |
| `C` | 83 groups, 2,650,719–2,650,801 | 86 groups, 4,234,464–4,234,549 |

**Exact member-level calculation.** Build the complete directed adjacency ledger and maximal-run roster keyed by exact `(family, side sequence, source day, session, phase)`. Preserve group IDs, each member clock, inter-group receive gaps, price path, shared order IDs, and the exact edge/run start and completion.

**Averaged analytical companion.** Within one identical edge or maximal-run family/side/session/phase stratum, calculate arithmetic mean inter-group gap, run length, run duration, trade/fill/cancel quantity, price displacement, and F_LAST formation time. The denominator is the number of exact edge or run instances, with the full instance roster retained.

### A5. Session withdrawal-to-restart phase chains

The mass-withdrawal groups have exact causal neighborhoods:

- October 4: the five preceding families are `C/A`, `A/A`, `MN/AN`, `MN/AN`, `M/B`; group 2,654,677 then closes its 430-cancel withdrawal at `21:00:00.237256020Z`. The next closed group arrives at `21:45:06.591299273Z`, 2,706.354043253 s later; the first five restart groups are all atomic adds, sides B, B, A, A, A.
- October 5: the five preceding groups are all atomic bid cancels; group 4,237,483 closes its 581-cancel withdrawal at `21:00:00.228110022Z`. The next group arrives at `21:45:06.126881137Z`, 2,705.898771115 s later; the first five restart groups are all atomic adds, sides B, B, B, A, A.

This yields exact pre-boundary, withdrawal, quiet interval, and restart phases for each source-day session.

**Exact member-level calculation.** Preserve every group in each individual session phase and calculate exact boundary-to-restart duration, first post-boundary action/side/price/order ID, ordered restart chain, side-specific add/cancel quantities, and order survival across the withdrawal.

**Averaged analytical companion.** Within each individual source-day session and one fixed phase/side/family stratum, calculate arithmetic mean action size, inter-arrival time, order age, price distance from touch, and restored depth per restart member. The denominator is the number of exact members in that one session phase; October 4 and October 5 remain separately identified session populations.

### A6. Full FIFO snapshots and exact activity tails already resident at checkpoints

All 18 adapter-state hashes validate against their checkpoint receipts, and the full checkpoint chain validates. The scientific replay positions include F_LAST-closed states at records 1,561,401; 2,000,000; 2,500,000; 3,000,001; 3,500,000; 3,555,759; 4,000,000; 4,500,000; 5,000,000; 5,500,000; and 5,667,689. Each state stores:

- every resting order with side, price, size, `priority_recv_ns`, `priority_sequence`, and `last_update_recv_ns`;
- each full price level's FIFO-ordered order-ID list; and
- an exact, causally ordered activity tail covering up to 300 seconds, with action, side, price, size, size delta, priority-loss flag, missing-reference flag, top-touch flag, and receive clock.

For example, the start-of-October-4 state contains 805 resting orders; the end-of-October-4 state contains 666; the intermediate held-out checkpoints contain 1,033, 1,224, 1,137, and 1,037. October 5 intermediate states contain 1,085, 1,372, 1,301, and 1,339 resting orders before the 762-order terminal state.

**Exact member-level calculation.** At each checkpoint, enumerate each price level and FIFO member with exact volume ahead, priority age, last-update age, side, price, size, and survival into the next checkpoint. Enumerate every activity-tail member by exact action/family/side and clock.

**Averaged analytical companion.** Within one checkpoint, exact side, exact price level, exact activity family/side, and exact causal window, calculate arithmetic mean order size, priority age, update age, volume ahead, action size, and size delta. Identify checkpoint state hash, denominator, session/phase, and `ts_recv_ns` watermark; retain the member order/action roster.

## B. Deterministically reconstructable from native DBNs plus exact adapter checkpoints

The canonical full-state bridge exposes the live `InstrumentBook` after every F_LAST group; `orders` holds every resting order and `levels` holds every full FIFO queue. `checkpoint_state()` materializes full bid/ask depth and per-level `fifo_queue`; the exact resume contract restores orders, FIFO levels, activity, cached totals, and clocks and round-trips to the same state hash. These mechanics support targeted read-only reconstruction from the nearest verified checkpoint.

### B1. Every-group full-book before/after and queue impact

**Exact member-level calculation.** For each selected group, bind the previous F_LAST post-state as `book_before`, apply the ordered raw actions, and bind terminal F_LAST as `book_after`. Emit exact side/price-level depth deltas, order-count deltas, level births/deaths, best-price/spread changes, order-ID entries/exits, FIFO position changes, volume-ahead changes, priority resets, and member clocks.

**Averaged analytical companion.** Within one fixed `(day, exact family/subfamily, exact side sequence, session, phase, clock)` group population, compute arithmetic means for book depth delta, order-count delta, level-count delta, spread delta, touch depth consumed, levels crossed, volume-ahead change, and priority-age change. `denominator_n` is the exact number of reconstructed groups in that stratum.

### B2. Queue depletion, replenishment, and absorption runways

**Exact member-level calculation.** Trace each touched price queue member by member across a causal prefix. Depletion is the exact ordered removal/fill/size-reduction path; replenishment is the exact ordered add or priority-reset path back into that price; absorption is a content-derived runway retaining repeated trade/fill contacts, held or restored price, queue identities, quantities, and all F_LAST clocks. Preserve separate stopped, extended, recurring, reversed, and completed paths.

**Averaged analytical companion.** Within one exact runway family, side, price relation, day, session, and phase, calculate arithmetic mean quantity depleted, quantity replenished, restoration fraction, time to restoration, number of repeated contacts, queue members consumed, volume ahead, order survival time, and price displacement. The exact runway roster and stage clocks remain attached.

### B3. Pre-birth and earliest lawful recognition clocks

**Exact member-level calculation.** For each content-derived exhaustion onset, replay only lawful prefixes and identify the earliest group whose F_LAST state supports a precursor, the onset event/receive clocks, the first post-onset F_LAST that supports recognition, stage transitions, and completion. Record lead, detection latency, causal age, and duration separately on event, receive, availability, and decision clocks.

**Averaged analytical companion.** Within one fixed exhaustion family/subfamily, side, session, phase, and clock definition, calculate arithmetic means for pre-birth lead, onset-to-recognition latency, total duration, stage duration, recurrence gap, and remaining-duration error. Denominators are exact runway counts, with member timings preserved.

### B4. Exact side/dipole evolution

**Exact member-level calculation.** At every selected F_LAST, retain full-depth bid/ask imbalance, trade-aggressor quantity by side, add/cancel/modify quantity by side, top-touch quantity, and exact signed flow for the causal 1/5/20/60/300-second windows. Bind precursor, onset, transition, inflection, persistence, collapse, flip, and completion stages to their own group IDs and clocks.

**Averaged analytical companion.** Within one exact family/subfamily, mirrored-side stratum, day, session, phase, stage, window, and clock basis, calculate arithmetic mean signed trade imbalance, full-depth imbalance, opposing-side quantity, add/cancel churn, top-touch quantity, and price response. Opposite mirrored sides remain separate populations.

### B5. FIFO-aware causal strategy research

**Exact member-level calculation.** For each provisional trigger, preserve the triggering group/runway, decision F_LAST, displayed queue, proposed order price/side/size, FIFO volume ahead, later native queue mutations, first executable contact, hold/exit/invalidation group, fees/slippage inputs, and exact price path. The observed exhaustion classification remains bound to the native runway.

**Averaged analytical companion.** Within one identical trigger family/subfamily, side, session, phase, queue-position band, decision clock, and fixed horizon, calculate arithmetic mean time to executable contact, filled quantity, favorable excursion, adverse excursion, holding time, and fee/slippage-adjusted research outcome. The denominator is the exact trigger count and every member path remains visible.

## Highest-value corrected-rerun ordering

1. Promote the new `TFC`, three-/four-/five-fill cascades, mixed `TFFCM`/`TFFCMN`/`TFTFCMN`, and `TFACN`/`TFCAN` families into the open-world taxonomy with exact member ledgers and coequal within-stratum averaged companions.
2. Build same-order lifecycle joins and exact family adjacency/run rosters, beginning with the observed `AN → TFMN → TFCN` residual-depletion chain.
3. Restore the nearest hash-verified checkpoint around each candidate and reconstruct full before/after book and FIFO state at every member F_LAST.
4. Form queue-depletion, replenishment, absorption, recurrence, and session-phase runways from exact causal prefixes.
5. Bind earliest lawful precursor/onset/recognition clocks and exact side/dipole stages.
6. Calculate coequal arithmetic companions only inside fully identified day/family/subfamily/side/session/phase/clock strata, surface `COMPLEMENTARY_SCOPE_DIFFERENCE` whenever the two views answer different questions, and carry both views into bounded-lookahead and provisional strategy research.

This ordering converts the intact first run from a family census into a native causal research surface while preserving every distinct group, order, queue, side, session, phase, and clock.

## Read-only verification performed

The native ledger SHA-256 is `b7399305906936fb89c5028fe2f32e291aefc2f9be14e421e6afc14b27acd038`; its 4,256,603 decompressed envelopes were inspected, including 3,094,296 held-out groups. The canonical source identity embedded in `source_manifest.json` is `a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba`. The checkpoint receipt chain was verified in order, and every one of the 18 adapter-state files recomputed to its recorded state hash and passed the canonical adapter-state validator. All inspection and calculations were read-only; no replay or model process was launched.
