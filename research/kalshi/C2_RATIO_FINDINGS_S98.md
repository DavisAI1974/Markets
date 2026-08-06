# C2 RATIO FINDINGS - S98 (DATA_GATE Tier 1: the flip-confirm C2 arm, measured on comparable data)

The S97/S100.2 refine flagged C2's ratio reformulation as a BUILD GAP: the apparent separation
(true confirms 0.00-0.42 vs false 0107 = 1.23) came from a zigzag proxy whose absolute level was NOT
comparable to the committed fingerprints, so the numbers were flagged, never adopted. Greg's rule:
derive properly, do not adopt. This is the derivation. PER-EVENT throughout; nothing pooled.

## Provenance (comparability closed)

- G11 (20260118-20260130, 12 sessions) run through `month_characterize.characterize_day` - the SAME
  tool and leg definitions as every pre-G11 day in `renders/ng_refine_s95/fingerprints.json` - via
  `run_g11_fingerprints_s98.py`, on the walked NG.n.0 basis (instrument 1021, no intra-block roll),
  each row tagged `series_basis: NG.n.0`. Runtime 29s, 12/12 days clean.
- COMPARABILITY VERIFIED BY EXACT REPRODUCTION: every recorded pre-G11 instance count reproduces to
  the digit from the merged file - 1208 up 3/33 big 2/6; 1008 up 0/15; 1020 dn 1/10 big 0/2;
  1223 dn 3/38 big 2/6; 0107 dn 10/36 big 6/7. Definitions are aligned; the G11 rows are on the
  same scale.

## The measurement

RATIO = (old-chain-side continuation share) / (new-side continuation share), the flagged
reformulation. Old side = the chain's polarity before the candidate flip.

| day | verdict | old cont | old % | new % | RATIO | old big legs alive |
|---|---|---|---|---|---|---|
| 20251008 | TRUE confirm (G4 top) | 0/15 | 0.0 | 46.2 | 0.000 | 0/0 |
| 20251020 | TRUE confirm (G5 bottom) | 1/10 | 10.0 | 45.5 | 0.220 | 0/2 |
| 20251208 | TRUE confirm (G9 crest) | 3/33 | 9.1 | 38.5 | 0.236 | 2/6 |
| 20251223 | TRUE termination (G9 year-end) | 3/38 | 7.9 | 51.7 | 0.153 | 2/6 |
| 20260107 | FALSE (G10 - correctly declined) | 10/36 | 27.8 | 38.7 | 0.718 | 6/7 |
| 20260120 | TRUE confirm (G11 - the C1 fire) | 8/28 | 28.6 | 40.0 | 0.714 | 3/3 |

## THE RESULT: THE RATIO REFORMULATION IS REFUTED

0120 (true) and 0107 (false) - the exact pair the reformulation existed to separate - are
NEAR-IDENTICAL on every C2 arm:
- ratio 0.714 vs 0.718;
- absolute old-side share 28.6% vs 27.8% (both fail the <=15% bar identically);
- old-side big legs FULLY/majority alive on both (3/3 vs 6/7) - the rejection arm says "no flip"
  on both, i.e. it is a constant on this pair and carries zero information.

The proxy's 0.00-0.42-vs-1.23 separation was an artifact of the non-comparable base - which is
precisely why it was flagged rather than adopted, and the flag did its job.

## Mechanism, revised per-instance (and an S100.2 correction)

- On the G11-class tape, BOTH sides retaining a live share is the NORM: across all nine G11 weekday
  sessions, per-side continuation runs 18-47% (e.g. 0121 up 41%/dn 22%; 0126 up 20%/dn 30%;
  0130 up 45%/dn 18%). A collapse-to-<=10% signature simply does not occur at this tape character.
- CORRECTION TO THE S100.2 MECHANISM: the "scale artifact" story (absolute bar mechanically
  unreachable at 160-550 legs) does not survive the comparable measurement. Real-tool leg counts:
  G11 days carry 63-149 legs (the 160-550 was proxy inflation), 0107 carries 67 - inside the same
  range as 0120's 63 - and, decisively, 1208 COLLAPSED TO 9.1% ON AN 85-LEG TAPE. Total leg count
  is not the discriminating condition. What is observable per-instance: the four 2025 true confirms
  all collapsed <=10%; the two January-2026 instances both read ~28% with OPPOSITE ground truths.
  Whether the condition is trade-count regime (15-25k vs 75-125k trades), season, or tape character
  cannot be settled on n=2 in that class - both candidate framings are recorded, no boundary is
  fitted.

## What carries the flip confirm (per-instance, from the same record)

The two January instances ARE separated - by the other conditions:
- C1 (band-break, scale-invariant by construction - a ratio to the condition-class band):
  0120 +1930 = 3.9x its band top; 0107 +1510 = IN-band. Five fires, one correct decline, zero
  false positives across the walk (S100.2, unchanged).
- C4 (driver arbiter): 0120 had the first-appearance cold add (0119 feed) and subsequently the
  winter's first surplus narrowing; 0107 sat under a re-widening surplus with no driver.
- C3 (printed-never-front-run) applies unchanged.

## Resolution proposed for the brain (s100.3 proposal - NOT merged; renders-printed-first protocol)

C2 is KEPT and SCOPED per-instance, never deleted (doctrine): it DISCRIMINATES on the class of its
four 2025 instances (collapse-to-<=10% fired on all four true confirms; its big-leg arm also
rejects 0107) and is NON-DISCRIMINATING on the 0107/0120 class (n=1 true, n=1 false; every arm
constant across the pair). On that class the confirm COMPLETES as C1 + C3 + C4. This resolves the
gate blocker: the four-condition confirm can complete on modern tapes, because the condition that
cannot be evaluated there no longer blocks it - it abstains, recorded as out-of-scope, and the
load-bearing conditions carry.

## Honest limits

- The critical pair is n=1 vs n=1. The 0.714/0.718 near-equality is one pair, not a law. Every
  future flip instance gets ALL arms scored per-instance regardless of scope - the data stays in
  place and the scoping is falsifiable by the next instance that lands.
- C1's zero-false-positive record spans five fires and one decline - strong for a tape rule, still
  small-n. C3/C4 are forward-confirmed twice each (S100.2).
- G11's own holdout caveat stands (the orchestrator had seen the block's path; the blind agent had
  not). The fingerprint rows are mechanical extraction and unaffected.
