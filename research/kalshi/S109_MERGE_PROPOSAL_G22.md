# S109 MERGE PROPOSAL — from the G22 blind

**PROPOSAL ONLY. No brain edit has been made.** Per standing doctrine: brain merges are proposal files
plus adjudication, incumbents byte-identical, never a direct edit. Nothing here is merged until Greg
says so. Evidence and reasoning: `G22_REASONING_LEDGER_S109.md`.

G22 blind: 4/10 direction, sum|err| **5,965**, drift **−1,815**, survives 30%. Second-best blind of the
walk on sum|err| (G17 4,510 · **G22 5,965** · G21 6,320 · G20 7,880 · G19 9,390) and the worst on
direction.

---

## P1 — THE SUMMER ARTIFACT LEAN (highest value; systematic, not judgement)

**Claim.** In a summer/CDD block the HDD-keyed play family is *unevaluable*, and every member degrades
**in the same direction — bearish or void**. Four independent artifacts push down at once; none is a
signal.

**The four, measured on G22** (realized gw_cdd ran 9.0 → 18.7; `forecast_gw_hdd` sat at 0.034–0.301):

| # | play / field | HDD bar | in July | degrades to |
|---|---|---|---|---|
| 1 | `selector.divergence_resolution` catalyst override | HDD ≥ 16.4 | unreachable | never fires → selector defaults to the S3-bearish angle |
| 2 | `magnitude.shoulder_weather_band_void` | HDD ≤ ~13.5 | trivially satisfied | **voids the weather band** on every summer day |
| 3 | `forecast_run_delta_cdd` across a seam | — | structurally blind (§P2) | reads ~0 against a +4.7 add |
| 4 | `weather_forecast_cycle.sunday_reopen` | HDD-only | +0.096 for 0629 | reads ~0 against the same +4.7 add |

**Forward evidence.** Specialist B named this mechanism in its 0629 posterior **before the block was
scored**. The scoreboard then showed: four days forecast down that printed up (0622, 0624, 0630, 0703),
contributing **−3,840** of signed error against a block drift of −1,815. Blind cum −1,345 vs actual
+470; blind ends 3.063 vs 3.245.

**This is the same shape as the S108 b_share defect**: a one-directional structural lean in which every
individual field is present, numeric, in range, and self-consistent.

**Proposed (additive, no incumbent rewritten):**

- **`weather.absolute_hdd_bar_unevaluable_in_cdd_regime`** — an absolute HDD bar that is unreachable in
  the block's regime returns **UNKNOWN**, never a satisfied/refuted boolean, and must not default a
  selector or void a band. `requires`: the block's realized or forecast CDD regime. `scope`: any play
  stating an absolute HDD threshold. **Falsifier**: a winter block where the same bars evaluate normally
  and the plays behave as measured — i.e. this play must be inert outside CDD regimes.
- **Re-point 1 and 2 to the now-served CDD ladder** (`forecast_gw_cdd`, `d_gw_cdd`, `fwd7_gw_cdd_span`).
  The summer-side thresholds are **NOT proposed here** — there is no measured summer authority threshold
  anywhere in the brain (16.4 is a winter instrument), and D named that gap independently as the main
  driver of its own low sign confidence. Inventing a summer bar now would be fitting. **Proposed as a
  build item, not a play.**

**Attribution discipline:** the CDD ladder is a DATA fix (§P4). Do not bank any G23 improvement as
evidence for a play when the input changed underneath it.

---

## P2 — SEAM DELTAS ARE STRUCTURALLY BLIND (general, high confidence)

**Claim.** A model *run* delta baselines run-over-run, not session-over-session. Across a weekend or
holiday seam spanning 4–8 cycles the accumulation appears in no single delta.

**Measured.** `forecast_run_delta_cdd` = −0.219 on 0629 against a **+4.7 level move**; the block's whole
run-delta series sits in a +1.05/−0.50 noise band while the level ran 10.08 → 14.82. Mechanism verified
rather than asserted: on 0624 the level moved +2.205 while the field read −0.011. Second independent
instance on a different field: `sunday_reopen` d_gw_hdd +0.096 for the same seam.

**Consequence.** E read the field correctly and got the sign backwards. Friday→Monday is the walk's
declared focus, so this touches the highest-value day class.

**Proposed:** **`weekend.seam_delta_requires_level_difference`** — across any weekend or holiday
boundary, difference the **LEVELS**; run deltas are intra-week instruments only. `forward_evidence`:
G22 0629, two independent fields. **Falsifier**: an intra-week day where the run delta and the level
difference agree (they should — the claim is scoped to seams).

*Data side already landed: `seam_delta_warning` is served in-band.*

---

## P3 — THE WEEKEND-GAP INSTRUMENT IS REFUTED IN SUMMER (n=1, strongest single result)

**Claim.** `magnitude.weekend_gap_delivery`'s fresh arm (+1500..+2500) is **winter-measured with no
summer instance**, and G22 supplies an n=1 **refutation**, not a calibration miss.

**The test, and why it is clean.** The bridge pre-committed to a mechanism, and the driver **arrived
exactly as forecast**:

| | forecast | realized |
|---|---|---|
| 0629 gw_cdd | 14.815 | **14.8** |
| 0630 gw_cdd | 16.194 | 15.7 |

| 0629 | forecast | actual |
|---|---|---|
| gap | **+480** | **+50** |
| session | −155 | **−1,160** |
| net | +325 | **−1,110** |

A large, correctly-forecast, correctly-**realized** weekend CDD add produced **five ticks of gap** and a
hard down session. A had already rescaled the winter band to +350..+800 on regime grounds and was still
~10× high on the gap.

**Both Mondays fail the gap in opposite directions:**

| Monday | forecast gap | actual gap | forecast session | actual session |
|---|---|---|---|---|
| 0622 | +20 | **+1,210** | −440 | −560 (**err 120**) |
| 0629 | +480 | **+50** | −155 | −1,160 |

B derived 0622's gap from reopen participation — *"a weekend that traded nothing repriced nothing"* —
and the 252-lot reopen preceded a +1,210 gap. So **reopen participation does not predict gap size
either**.

**Proposed (deliberately conservative):**

- **RETRACT the summer applicability** of `weekend_gap_delivery`'s fresh arm — scope it to winter
  explicitly, where its exemplars live. Do **not** propose a summer band; n=1 refutation licenses a
  scope restriction, not a new number.
- **`boundary.weekend_gap_is_not_forecastable_from_current_instruments`** (PROPOSED, n=2) — on this
  evidence the blind's weekend-gap read is uninformative in both directions, while its **session** read
  is sound (0622 session err 120). Suggests carrying weekend gaps as an explicit **wide band** rather
  than a point estimate, and scoring gap and session separately. **Falsifier**: a block where a
  pre-committed gap call lands inside ±300 on both Mondays.

**Do NOT merge as "the panel was too bullish."** That is the net-not-mechanism error this walk has
already paid for once.

---

## P4 — DATA BUILDS LANDED THIS SESSION (not brain changes; listed for attribution hygiene)

1. **CDD forward ladder served** — `forecast_gw_cdd`, `d_gw_cdd`, `fwd7_gw_cdd_span` on `horizons` /
   `run_delta`. The feed always computed them; assembly dropped them, exactly as S107 dropped
   `big_print_b_share`. Additive: fitted HDD bars read exactly what they read before.
2. **`sunday_reopen` carries CDD** — `gw_cdd_d0` and `d_gw_cdd`.
3. **`seam_delta_warning`** and **`ladder_basis_note`** served in-band.
4. **`forward_stamps()` wired into `build_causal_slices.build()`** — it existed but was never called, so
   C's catch (a `consensus_pre_print_snapshot_utc` stamped 2026-07-02 under the 0629, 0630 and 0701
   blocks) would have stayed invisible. Reported, never fatal.
5. **Anchor block** carries `direction_caveat` / `close_in_range` / `net_ticks` and the reconstruction
   basis (auditor f14).

**Standing attribution rule:** these changed the INPUTS. Any G23 improvement must not be banked as
evidence for a play.

---

## STILL OPEN — NOT PROPOSED, NEEDS A DECISION OR A BUILD

| item | why it is not a proposal |
|---|---|
| `storage_consensus` post-print look-ahead (auditor f2) | a DATA fix needing the source feed; on 0625 it destroys ~78% of decision-time surprise. Specialists are currently working around it correctly, which is not a substitute for fixing it. |
| No measured **summer** authority threshold | genuine build gap; naming a number now would be fitting. D and B both hit it independently. |
| `flow.resting_program_inverts_aggressor_tilt` never fires on `is_expiry_day` | proposed by the clean bridge with a price-free discriminator; wants a second instance before merge. |
| `options_surface` 10× strike scale (auditor f6) | data fix; 0 of 67 plays read it, so it costs specialist budget, not signal. |
| Session **close time in ET** absent on shortened sessions | A had to assume ~13:00 on 0703. `cme_early_close: false` on a `partial_session` should be a hard `state_health` failure. |
| Phase boundaries carry no clock mapping | binds hardest on EIA days — D cannot anchor a mechanism to the 10:30 print, which is why its timing claims are testable only in post-mortem. |
