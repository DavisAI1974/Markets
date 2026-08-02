# G22 REFINE REASONING LEDGER — S110

**Why this file exists (Greg, S110):** *"are we logging the context of the refine's decisions? those are
probably the most useful."* Audit answer: the structured reasoning IS committed (390 KB across the ten
r1 posteriors and five r2 files — `evidence_used`, `evidence_rejected`, `stand_down_reasons`,
`magnitude_derivation`, `mbo_verdict`, `proposal_contribution`). What was NOT captured is the
specialists' PROSE SUMMARIES — the sharpest framing of the run — and the distilled cross-day
narrative. S109 built a ledger for the G22 BLIND because Greg asked in-session; nobody made it
standing procedure, so the refine had none. Now required by SOP v1.4.

Scope: the G22 refine, brain s103.7, per-day causal isolation.
Score: blind 4/10 · sum|err| 5,965 · drift −1,815 → **r1 10/10 · 500 · −80** → **r2 10/10 · 330 · +50**.

---

## PART 1 — DECISIONS THAT WERE RIGHT, AND THE REASONING THAT PRODUCED THEM

### 1.1 C separated a ROLL-DOWN from a REVISION (0624, blind −200 → +600, actual +800)
The blind read `run_delta_cdd −0.011` as "nothing new, therefore priced, therefore inert." C found
the +2.2 gw-CDD step was **not a forecast revision at all**: 0623's h1 view of 06-24 was 10.034 and
0624's D0 view is 10.022 — the mass **rolled down** into the near window while the skeptic model
capitulated upward (MET 8.402 → 9.115, spread 1.632 → 0.907). The blind applied the revision arm to
a roll-down event. **The brain already held the right instrument** — the s101.6 pricing-time rule
(moderate adds price at near-window ENTRY, D0..D+2), which supersedes the revision read by its own
text. Replicable rule: *before reading a delta as "priced," check whether the level moved by
revision or by the window advancing.*

### 1.2 C proved the flip was NOT tape-callable, and said so (0624)
C checked `giveback_exhaustion` limb by limb **with price visible** and it fails all three (chain age
2, cum −80, no D-1 absorption tell); the accumulation arm's silence was *correct*. Conclusion stated
plainly: **no tape instrument could have called this flip — the instrument was the weather slope.**
Why it matters: a refine that manufactures a tape story for a fundamentals day teaches the blind to
hallucinate one. The honest negative is the lesson.

### 1.3 D re-verified its own consensus reconstruction against the price curve (0625, err −10)
Blind used 67.0 (strictly pre-print) over the served 74.0 (post-print capture). The refine confirmed
it from the other side: **a −770 flush in 18 minutes pinned to 10:30** is the signature of a genuine
unpriced surprise, not an in-line print inside a 7 Bcf dispersion. Decision-time surprise **+9
bearish**, not the served +2. Adjacent trap found: top-level `stor_surprise` −5.0 on a print-day
slice is the *prior* print's seasonal surprise — mislabel-shaped, flagged.

### 1.4 E re-derived the roll confound independently and AGREED with the settlement (0626, err 0)
Seven measured quantities, including the control: 0625 was also a scheduled-flow day (opex + EIA) and
shows **none** of the fingerprints. Big-print cohort 210 @ 0.783 contributing ≥ ~+4,800 net buy while
session flow was only +871 → the organic residual **sold** ~3,900–8,600 lots; breadth unmoved
(0.509 → 0.504). Fires on the letter, void on the mechanism.

### 1.5 E's corrected flip test survived its own re-execution (0626 → 0629)
E re-classified its exit **MOMENTUM_CARRY → POSITIONING_SPENT_FADE** and re-specified the flip as
two limbs: flip UP only if (1) weekend cycles add gw_cdd **AND** (2) the burn confirms. Executed on
the realized weekend: limb 1 passes (+4.8 CDD), **limb 2 fails decisively** (burn 38.6 → 34.4, wind
+62%) → HOLD DOWN. **E's original blind sign survives its own corrected test** — the S109 ledger's
"perfect process, wrong outcome" resolved by adding the missing limb, not by reversing the process.

### 1.6 B answered the P3 question as a CONFIRMED NEGATIVE plus a positive (0622)
Gap **not ownable as a number** from any decision-legit channel — walked channel by channel (Friday
exit pointed down; CDD ladder had no forward levels; calendar mild; positioning could not sign it,
the same 2.83-pctile book sat under G21's 0614 seam that gapped −750). **But ownable in SIGN**:
`model_disagreement.stability` served +0.58/+0.42/+0.47/+1.01/+0.52 across h1–h5 — every reachable
horizon hotter, sum +3.0 — while every purpose-built weekend feed was HDD-only and read ~zero on the
wrong axis. 3/3 seams called (0614 −750, 0621 +1,210, 0628 +50); positioning 1/3. **The channel's own
label ("uncertainty conditioner") steered readers away** → the new audit kind, *served-but-mislabeled*.

### 1.7 B derived the 0629 sign at the reopen, BEFORE any session tape (err 110)
Re-executed E's two-limb test from its own slice, got HOLD DOWN pre-tape, then derived
DOWN-how-much from exactly three terms: fade-class crest remainder (−230), the block's own bleed
scale (−560/−730 realized), constraint floor (−150..−200). Stack ≈ −1,050 session / −1,000 day
against actual −1,110. The 14:52 capitulation tranche **explicitly not claimed**.

### 1.8 A stood on a repair clause it had authored and refuted itself (0703)
`thin_session_range_invariance` — sqrt(participation) survives its **second consecutive forward
pass** (net 410 vs 453 predicted). New nuance: thinness scaled magnitude, not direction; the
holiday-eve session carries a **risk-bound** participant (weekend squaring) that tilts sign without
preserving range — distinct from the volume-bound class.

---

## PART 2 — SELF-CATCHES AND CORRECTIONS

### 2.1 D audited its own timing claim and called it WRONG (0702)
Blind put ~12–13% of path mass pre-10:30 (positive); realized pre-print share was ~38% of leg travel,
all down. **The falsifier window was drawn too narrow** — it named 08:00–10:30, which netted just −50
and "never fired" while the decomposition failed anyway. Corrected rule: pre-print window =
**reopen → 10:30**. A right net (0) with a wrong window is a different lesson than a wrong net, and
only the decomposition separates them.

### 2.2 D re-derived its own point and named its r1 slack (0702, r2)
r2 kept the point at 0 but re-derived it as *reclaim-to-boundary*, and named two timing slacks
against the authoritative curve: the r1 seam front-ran the onset, and the r1 afternoon clock ran ~1h
early. Same number, better mechanism, stated as a correction rather than a confirmation.

### 2.3 C recorded the honest in-block NEGATIVE on its own new channel (0701)
Wind read this time — but recorded plainly: **wind does not sort day sign** (0630 printed +780 under
a rising-wind slice). It is a **damper, never a sorter**. That caveat went into the merged play text.

### 2.4 A found the two-sided derivation the r1 could only bound one way (0703, r2)
D's phase grammar (reclaim paid, extension denied) transferred one altitude up and became A's close
cap: two independent derivations — sqrt-participation (440–453) and the reclaim-cap ceiling (~500) —
triangulating the same center. **The handoff's value is that it hands the next owner the
interpretation, not the number.**

### 2.5 C found the HE24 boundary is a fourth phase sample (r2)
dir-vs-flow at the exit sorted the next session's class **5/5 in G22**: failing dip-buys →
continuation down; absorption → reversal up; still-delivering stall → give-back; unpaid late
extension → round-trip. Honest n stated by C itself: 5 boundaries in ONE block, two arms with
cross-group siblings. Owned-set error r1 340 → r2 170 (blind 2,620).

### 2.6 B found the seam TURN CLOCK, both edges (r2)
On a weekend seam the turn lands at a **model-posting-window edge**, and covering-license × burn-
constraint selects WHICH edge: licensed+confirmed → the LAST window (0622 high 04:07–04:09, verified);
unlicensed+vetoed → the FIRST window with the second hot cycle **ignored** (0629 died 22:55/23:32,
then straight down through the posting window). By ~04:30 ET the seam has classified the Monday.

---

## PART 3 — THE CROSS-CUTTING FINDING THREE SPECIALISTS CONVERGED ON

**"READ-AT-THE-WRONG-LEVEL" — gross where the tradeable object is the RESIDUAL.** Named by E,
co-signed by B and A, three instances in one block:

| instance | gross (what was read) | residual (what traded) |
|---|---|---|
| expiry Friday 0626 | aggressor flow +871 | ex-program residual: net SELLING |
| Monday 0629 | CDD add +4.8 realized | burn residual −4.2 Bcf/d (wind +62%) |
| Monday 0629 gate | D-1 tilt aggregate | program-decontaminated tilt |

Every one passes every reconciliation, because the value **is** correct — as the wrong object. Merged
into `agents/state_auditor.md` as known-kind #6, beside #7 *served-but-mislabeled* (§1.6).

---

## PART 4 — WHAT THE LEDGER ITSELF TEACHES

Three of the ten best reads came from **standing down** a play whose reading agreed with the
specialist's own number (C's accumulation arm on trajectory; E's refute-limb on the roll; D's
surviving selection limb). Two came from **refusing to force** a branch (B's gap ownership; D's
"already priced" limb). One came from **auditing its own falsifier** and reporting the failure
(D-0702). None came from finding a new signal.

The generalizable claim: **at this stage the refine's value is disciplined subtraction — removing
instruments that fire on the letter and void on the mechanism.** The blind's remaining error is not
mostly a missing signal; it is a handful of instruments reading the wrong object at the wrong level
in the wrong window.
## DECISION CLAIMS (machine-checked - do not hand-edit; regenerate with `python decision_trace.py claims <gid>`)

| date | owner | phase | number | decision_id |
|---|---|---|---|---|
| 20260622 | B | blind | -420 | `072d52a6f475` |
| 20260622 | B | refine_r1 | +650 | `af2a319ca0ed` |
| 20260622 | B | refine_r2 | +650 | `af2a319ca0ed` |
| 20260623 | C | blind | -430 | `9ba7dca4d555` |
| 20260623 | C | refine_r1 | -700 | `65147514c786` |
| 20260623 | C | refine_r2 | -700 | `65147514c786` |
| 20260624 | C | blind | -200 | `9d813b96b772` |
| 20260624 | C | refine_r1 | +600 | `8f037a42fe8d` |
| 20260624 | C | refine_r2 | +700 | `14cd8a972924` |
| 20260625 | D | blind | -110 | `d080ba58adf5` |
| 20260625 | D | refine_r1 | -70 | `6d64d73ec460` |
| 20260625 | D | refine_r2 | -70 | `6d64d73ec460` |
| 20260626 | E | blind | +250 | `dd476bf17075` |
| 20260626 | E | refine_r1 | +230 | `3eca232aaeb6` |
| 20260626 | E | refine_r2 | +230 | `3eca232aaeb6` |
| 20260629 | B | blind | +325 | `1af30be59d28` |
| 20260629 | B | refine_r1 | -1000 | `34a4f46fe057` |
| 20260629 | B | refine_r2 | -1000 | `34a4f46fe057` |
| 20260630 | C | blind | -420 | `7d54b97e89fb` |
| 20260630 | C | refine_r1 | +700 | `66e9c72e2d63` |
| 20260630 | C | refine_r2 | +750 | `27bd098eddb5` |
| 20260701 | C | blind | -380 | `848991d524fc` |
| 20260701 | C | refine_r1 | -470 | `b9985f6ed78e` |
| 20260701 | C | refine_r2 | -490 | `53ebac970ca4` |
| 20260702 | D | blind | +200 | `d4f8fd78755d` |
| 20260702 | D | refine_r1 | +0 | `a11d6e131e5d` |
| 20260702 | D | refine_r2 | +0 | `a11d6e131e5d` |
| 20260703 | A | blind | -160 | `db7ddf0b69e6` |
| 20260703 | A | refine_r1 | +450 | `b144708a9d82` |
| 20260703 | A | refine_r2 | +450 | `b144708a9d82` |

