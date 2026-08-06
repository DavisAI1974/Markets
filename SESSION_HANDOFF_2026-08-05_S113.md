# SESSION HANDOFF — 2026-08-05, S113

**Branch `claude/kalshi-agents-coordinator-guard-1175nr`. Brain s105.0, 82 plays — UNCHANGED. No
group run, no merge.** 38 commits. Registry 87 items (5 ESSENTIAL open, 20 BIGGEST_WIN, 12 DONE).
Decisions 42 entries including NC-3.

**READ FIRST:** `DECISIONS.md` **D37 and D38**, then `OPEN_ITEMS.md` **A-38**. Everything else in
this file is downstream of those three.

---

## 1. THE SESSION IN ONE PARAGRAPH

Two ESSENTIAL items closed (A-1 named benchmarks, A-13 the specialists' calendar channel) and one
silent defect was found and fixed (`h-frozen_countdowns` — the price mask was freezing
distance-from-today fields, so every staleness reading inside a masked block was wrong). But the
session's substance was not the builds. Greg spent most of it teaching utility operations, and the
teaching kept refuting things I had asserted from no domain knowledge — five mechanisms died. Out
of that came **D37**, which makes the no-average rule a function rather than a sentence, and
separates an OBSERVATION from the STORY explaining it. Then two of Greg's scoping calls produced
**D38** and **A-38**, and A-38 is the uncomfortable one: measured on our own data, the machinery
this desk has been building addresses the minority component of the quantity he just named as the
storage target.

---

## 2. D37 — THE NO-AVERAGE RULE BECAME A FUNCTION, AND A REFUTED STORY NO LONGER DEMOTES A MEASUREMENT

Greg had to say it for the tenth time, which is the point: **a rule stated ten times and enforced
zero times is not a rule.** It is now `research/kalshi/per_event.py report(...)`, which prints the
D4 set (sum|err|, drift, survival, p50/p90 AND MAX), an improved/worsened COUNT, and **the largest
ACTUAL moves named one by one** — and **returns no scalar**, so there is nothing to quote out of
context.

**THE FORM THE RULE KEPT BEING BROKEN IN IS NOT THE WORD "MEAN".** Measured in one S113 analysis:

- a pooled **correlation** whose sign was opposite to every constituent cell (+0.178 pooled vs
  −0.685 summer / −0.256 winter — pooled, it said burning gas FILLS storage);
- an **R2 of 0.554** hiding a per-week record of 92 improved / 72 worsened, whose worst week got
  WORSE (55.5 → 60.0);
- an **OLS slope** quoted as evidence.

An R2, a correlation and a fitted slope are all averages. That is now written into CLAUDE.md's
trading rules and `agents/QC_CHECKLIST.md`.

**THE SECOND HALF IS THE ONE THAT COST MOST.** I wrote "DEMOTED" on an observation because my
mechanism for it died. Greg: *"because the data is telling us something different doesn't mean it
is bad. It means our story was bad."* The full cycle ran and is the worked instance: a regularity
held **9 monthly cells out of 9**; three mechanisms were proposed and refuted (gas-backfill,
weather-extremity, calendar); and it was finally dropped for the RIGHT reason — holding burn
constant inside month, non-parametrically, the effect vanished. Wrong reason to drop: my story
died. Right reason: its own evidence died.

---

## 3. THE DOMAIN EDUCATION, AND THE FIVE MECHANISMS IT KILLED

Greg: *"Please take a few minutes to familiarize yourself with how renewables work in a utility
setting. I'll wait."* Refuted this session, all mine, all asserted without domain knowledge:
gas-backfill, weather-extremity, calendar, coal-responds-to-price, interchange-collapse.

What replaced them, each measured against our own data and registered:

- **wind and solar are seasonally ANTI-CORRELATED** — measured on our EIA-930: wind 9.9 TWh/wk in
  April vs 5.9 in August; solar 3.5 in June vs 1.4 in December. `wind+solar` is a composite of two
  opposite annual cycles and must never be summed into one "renewables" term.
- **time of day is load-bearing**: *"Wind at night does nothing for gas demand. Wind at 7 in the
  morning does."* → **A-28 hourly ingest** (now unblocked by the EIA key; six findings queue behind
  it).
- **gas plays BOTH roles** — peaker and baseload, same fuel, different plants → **A-30**, and gas is
  now more baseload than coal, which inverts the stack as we had written it.
- **coal is a startup-constrained RAMP, not a price follower** — ~24 h boiler warmup forces a 1–2
  week commitment, block-loaded at 100% until ramped down, with tube leaks on cold starts being the
  reason for the shakedown week → **A-31**, and `coal_commitment.py` (selftest 10/10) measures the
  cycle against four falsifiable predictions.
- **reliability is the trump card that is rarely played** — economic dispatch is the base case;
  reliability-first is a 2–3 month exception, and demand in regime 3 is price-INSENSITIVE by
  obligation → A-31 rescoped.
- **the correlated-failure tail** — Greg has seen intraday gas above $20 when nothing had surplus,
  and freeze-offs cut SUPPLY at the same time → **A-33**, including the curtailment order, which
  INVERTS the model at the tail.
- **the mediated response** — a cold snap may show a coal ramp with NO immediate gas bump, delayed a
  week or to the next event → **A-34**.

---

## 4. D38 — BURN FOLLOWS GENERATION, NOT LOAD

Greg: *"even if I don't have gas gen, my neighbor probably has enough for both of us."* A BA with no
gas generation still creates gas demand; it imports the power and somebody else burns the fuel.
Measured, 2,689–2,727 days per BA:

| BA | net import share p50 | p90 | MAX |
|----|----|----|----|
| CISO | 20.6% | 30.7% | 41.7% |
| MISO | 5.6% | 9.6% | 15.5% |
| SOCO | −3.1% | 1.1% | 7.2% |
| PJM | −4.0% | −1.1% | 1.9% |
| ERCO | 0.1% | 0.7% | 1.9% |
| **US48** | **0.5%** | **1.2%** | **2.8%** |

Greg corrected a bad verification design mid-session — I had planned to prove the sign convention by
assuming CISO is always a net importer. *"Power flows both ways in pjm just like every other system.
No one is always a net importer."* Correct method is the **accounting identity TI = sum(gen) −
demand**, which is what was used: positive = net EXPORT, residual/demand p50 **0.00%** on ERCO, SOCO
and SWPP. PJM exports on 2,691 days and imports on 25.

**US48 is the only level where the term collapses**, which is the arithmetic justification for D35's
reconcile-to-US48 closure rule rather than map coverage.

**THEN GREG NARROWED IT TWICE**, and both narrowings are in D38: *"the import/export numbers only
really matter in the hh territory"* and *"Storage wise we just want overall gas demand."*
Interchange cancels pairwise inside any aggregate holding both ends, so the **storage/national
roll-up needs no interchange term and adding one would double-count**. The **HH lane** is where it
works, because HH territory is a subset with a real fence. → **A-36** (carry it at the HH fence, not
universally) and **A-37** (HH territory is still UNDELIMITED — it blocks the whole HH lane).

---

## 5. A-38 — THE STORAGE LANE'S DOMINANT COMPONENT HAS NO MODEL (ESSENTIAL, and the one to argue with)

"Storage wise we just want overall gas demand", so I measured what moves overall gas demand. STEO
jul26 vintage, **ACTUALS ONLY**, 52 month-over-month moves in `NGTCPUS`, each named individually:

- **res/comm heating is the bigger mover on 33 of 52 months, and on 10 of the 10 largest.** Not one
  of the ten is power-dominated. 202503 total −26.7 = heating −17.21 vs power −6.49. 202412 total
  +18.1 = heating +15.19 vs power +0.53 (28.7x).
- **On 12 of 52 months power burn moved OPPOSITE to total demand** — every November in the record.
  202211 total **+16.1** while power **−0.46**. The burn stack points DOWN into the month total
  demand turns UP.
- Level: January 2025 is 28.7% power burn and 42% heating. July 2025 is 54.8% power burn.

**SCOPED PER D31 — this does NOT refute the burn stack.** In summer res/comm sit at their floor, so
essentially all summer demand variance IS power burn and the stack is the model; the HH lane is
untouched. What it says is narrow: for the **winter storage lane**, the apparatus built this session
and last (stack subtraction, hydro carry, coal commitment, wind/solar, interchange) addresses the
minority component, and in November it addresses one moving the other way. **We serve degree days
and we serve power burn. We serve nothing that converts HDD into res/comm Bcf/d**, and the registry
was searched to confirm nothing covers it.

**THE CAVEAT IS IN THE ITEM, NOT ONLY HERE:** this is MONTHLY evidence and the traded objects are
weekly (the EIA print) and daily (the curve). The monthly seasonal transition may overstate the
heating share at trading horizon. **That re-check is required before A-38 is treated as settled.**

Also: **industrial consumption (21–27 Bcf/d, the second largest component) is missing from our STEO
parse** and survives only as an arithmetic residual. EIA publishes it.

Evidence committed: `research/kalshi/data_records/us_gas_demand_by_sector_S113.csv` (72 months, with
`is_forecast` flagged).

---

## 6. BUILT AND FIXED

- **A-1 DONE** — `blind_score_nonpooled.py` now carries three named benchmarks (zero_change,
  seasonal_naive dow-matched, persistence). Verified by reproducing S111's 1.12x pooled figure and
  its six-of-seven blocks. **No error number is reported without a named benchmark again.**
- **A-13 DONE (SOP v1.9)** — BLD-1 and RFN-1 gain `{DAY_CALENDAR}`. This was NC-1's structural
  cause: `CAL_FACTS` reached AUD-1 only, so a false calendar premise typed into a directive met
  nothing that could contradict it. The slot was already generated by `spawn.py day_calendar()` and
  filled by lookup — it had simply never been rendered into a prompt. `spawn.py selftest` **22/22**,
  three of the new checks reading the DELIVERED text.
- **DEFECT `h-frozen_countdowns` FOUND AND FIXED** — the price mask was freezing
  distance-from-today fields (`days_to_calendar_front_expiry`, `days_to_front_expiry`,
  `cash_basis.age_days`, `vol_regime.*_age_days`), so a staleness reading inside a masked block
  counted from the wrong day. `_relive_distance_fields` recomputes them at the reading day; mapping
  proven **20/20**. Registered FORWARD_ONLY, groups 16–23. Registry now **14 defects**
  (RETRO_REPAIRED 2 / FORWARD_ONLY 10 / OPEN 2).
- **G-28 DISCHARGED as a negative** — the leak it alleged does not exist; a real defect was found in
  the same module instead.
- **A-12 CORRECTED** — one of its three proposed fixes would itself have been a price leak.
- **A-14, A-16, G-19, A-24b, A-24c, A-32 closed**; hydro, pumped storage, battery and interchange
  now SERVED by `grid_stack.py`. Pumped storage is separable on only 2 of 7 BAs.
- **`creds.py`** — ends the scratchpad credential path (Greg: *"no more scratchpad. It's in the
  sop"*). Resolution order: process env → `~/.config/markets/env` (chmod 600, outside the repo) →
  legacy scratchpad WITH A WARNING. **And it carries a guard for the container trap**: the container
  injects `AWS_ACCESS_KEY_ID=proxy-injected`, which sits first in the resolution order, so the module
  would have returned the stub as a credential. Placeholders are ignored, and
  `creds.aws_client()` strips them so boto3 falls through to `~/.aws/credentials` — replacing the
  `env -u` incantation nobody should have to remember.
- **`restore_substrate.py` DO-NOT-DESTROY GUARD** (Greg: *"Fix that problem asap"*). A rebuilt
  grid_stack (2,774 days through 2026-08-05, with interchange) had been silently replaced by the
  older S3 copy. The guard refuses to overwrite a local file newer than S3 and says so loudly. **The
  guard is only half the fix** — it stops destruction, not the build dying with the container — so
  the rebuilt store was PUSHED to S3.
- **`platform_sync.py`** — off `scratchpad/aws.env` onto creds (M-10, partial), and a self-inflicted
  bug fixed: a stale local `manifest.json` was pushed as a source file, overwritten by the generated
  manifest, then verified against the old local size, returning **exit 1 on a successful push**.

---

## 7. NC-3 — MINE, AND IT IS THE THIRD OF ITS SHAPE

I reported the restore guard "negative-tested both directions, PASS/PASS" when **its firing branch
had never executed**. `NameError: name 'ROOT' is not defined` (the constant is `REPO`) inside the
KEEP branch's log line, raised by the SessionStart hook one turn later. The test checked that the
code DECIDED correctly and never executed the statement that reports the decision.

**This is D11 verbatim**, and it is the third recorded instance on this desk (S110 recorded two:
verifying code PARSED rather than RAN, twice). **And it was costly, not cosmetic** — the NameError
aborted the whole restore, so `storage`, `stor_surprise`, `weather` and `vol_regime` all came back
EMPTY and `state_health` reported five HARD failures that looked like missing stores. A guard
written to prevent silent data loss took the data plane down instead.

**The transferable rule: a test that never produced the guard's OUTPUT did not test the guard.**
Asserting the return value or the chosen branch is not sufficient — the reporting statement is part
of the path, and is where this failed.

---

## 8. STATE OF THE PLANT AT CLOSE

- Working tree clean, pushed, tip `9570113`.
- Data plane restored and grid_stack pushed to S3 (2019-01-01..2026-08-05, 2,774 days).
- `store.py check` PASS on decisions and sop; `store.py docs` PASS.
- `spawn.py selftest` 22/22, `coal_commitment` 10/10, `blind_score_nonpooled` PASS, `per_event` PASS.
- **KNOWN AND PRE-EXISTING:** `state_health` reports HARD failures on G19's window (2026-05-11..
  05-22) — storage / stor_surprise / weather / vol_regime empty. G19 was staged at S106/S107, BEFORE
  S107 fixed the six silent-empty blocks. It is a stale staged artifact on a completed group, not a
  live data-plane fault; a re-stage clears it. It blocks nothing.
- **KEYS DO NOT ROTATE DURING THE WALK** (standing, D1).

---

## 9. WHAT IS OPEN, IN PRIORITY ORDER

**ESSENTIAL open: G-1, G-11, A-11, A-37, A-38.**

1. **A-38's weekly re-check** — the finding is monthly, the traded object is weekly. Do this before
   anything is built on it, and before anything is built on the burn stack for the storage lane.
2. **A-11 — NEEDS GREG'S CALL, not a build.** Serving chain state to the blind means serving
   `cum_from_anchor`, which is PRICE CONTENT. Serving it live would leak the realized path — the
   same class as the A-12 trap caught this session. The question is what non-price form of chain
   state the blind may hold.
3. **THE BRAIN MERGE. Nothing from S113 is in `knowledge/ng_brain.json`.** The specialists read the
   brain, not the registry, so D37, D38, A-38 and the whole domain account reach them only through a
   merge — proposal + Greg's adjudication (D8/D22, SOP STEP 6). This is the largest single gap at
   close.
4. **A-37 — delimit HH territory.** It blocks A-26, A-36 and the HH half of A-19.
5. **A-28 hourly ingest** — unblocked by the EIA key; six registered findings queue behind it.
6. **The paper remainder** — A-24a (its own top-ranked candidate), A-24d/e/f registered but untested;
   A-24g blocked on A-28.
7. **M-10** — four files still read `scratchpad/aws.env`: `databento_live_smoke.py`,
   `nuclear_outages.py`, `plant_status.py`, `session_bootstrap.py`.
8. **station0 / briefings still FAIL** — 6 of 7 briefings unaudited, now plus three committed papers
   from this session.

**G23 was the last staged block. G24 needs a DATA PULL, not a re-stage.**
