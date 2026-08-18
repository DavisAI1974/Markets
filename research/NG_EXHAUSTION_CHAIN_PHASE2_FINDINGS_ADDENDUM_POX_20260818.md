# NG Exhaustion Chain Phase 2 — P-O-X Disposition Correction and Forensic Addendum — 2026-08-18

## Status correction

The earlier Phase-2 findings used the phrase **"P,O,X candidate killed"** after the insert-only held week printed a negative fixed-horizon mean. That disposition is superseded.

**P-O-X is not killed. It is ACTIVE_CONDITIONAL_MECHANISM_UNDER_REVIEW.**

The observed held-week result remains unchanged. What changes is how that result is interpreted and what process follows from it.

From this point forward, a failed fold triggers **FLAG_AND_DECOMPOSE**, not automatic deletion. Candidate retirement requires demonstrated leakage/structural invalidity, repeated independent out-of-time failure after mechanism decomposition, or a predeclared falsifier showing the mechanism is indistinguishable from null across relevant blocks.

## Why the automatic kill was too aggressive

The D3 `P,O,X -> continuation to +60s` candidate was strong before the held week:

- Eras 1-3: n=209, gross mean `+0.431t`, one-sided week-delta p=`0.0165`.
- Eras 4-5: n=140, gross mean `+0.200t`, p=`0.0566`.
- Untouched confirmation: n=78, gross mean `+0.449t`, positive week-delta rate `1.0`, p=`0.00568`.
- Full 54-week descriptive population: n=666, gross mean `+0.297t`; 38 positive-mean weeks, 14 negative-mean weeks, 2 zero-mean weeks.

The held week had 13 eligible instances and a gross mean of `-0.231t`. But that held result is not unusually extreme relative to the candidate's own historical week distribution:

- 9 of 54 historical weeks had a P-O-X weekly mean at or below the held value (`16.7%`).
- Exact held-week same-week circular-shift lower-tail p=`0.3901`.
- Exact two-sided p=`0.7802`.

Therefore the held reversal is a forensic flag, not evidence sufficient to retire the mechanism.

## It is not one bad print

The 13 held cases contain 5 negatives, 5 zeroes, and 3 positives. Removing any one case does not restore a positive held mean. The reversal is distributed across several instances.

However, it is highly structured.

## The held reversal splits by how the latest X state resolves

Condition on a field that is causal and known at current `t0`: whether the current exhaustion polarity matches the immediately preceding X-state exhaustion polarity.

### Current polarity opposite the latest predecessor

- Held: n=6, mean `+0.500t`.
- Held losing cases: **0**.
- 54-week base: n=339, mean `+0.316t`.

### Current polarity same as the latest predecessor

- Held: n=7, mean `-0.857t`.
- Held losing cases: 5.
- 54-week base: n=327, mean `+0.278t`.
- Only about `7.4%` of historical same-branch weekly means were at or below the held same-branch mean.

So the held week did not reject P-O-X uniformly. It exposed a branch distinction inside the mechanism.

## The path diverges progressively after entry

Using the fixed entry at structural endpoint `+5s`, held mean oriented returns evolve as follows:

| Branch | +10s | +20s | +30s | +60s |
|---|---:|---:|---:|---:|
| X -> same-polarity current | 0.000t | -0.286t | -0.714t | -0.857t |
| X -> opposite-polarity current | 0.000t | +0.167t | +0.333t | +0.500t |

The branches are not identical until the last sample and then randomly different. They separate progressively after roughly +10 seconds.

## Re-origin during the fixed +60 hold is part of the mechanism

Eleven of the 13 held P-O-X cases had a new exhaustion begin before the planned +60 exit. All five held losses are inside that set.

But **successor-before-exit is not by itself an invalidation**. On the held week:

- X -> same-polarity current with successor before exit: n=6, mean `-1.167t`.
- X -> opposite-polarity current with successor before exit: n=5, mean `+0.600t`.

The 54-week base also shows that subsequent polarity matters strongly. For the same-current-vs-latest branch:

- if the later successor is same polarity, mean is about `+0.74t` to `+0.76t` depending on whether it arrives before the fixed exit;
- if the later successor flips polarity, mean is approximately flat/slightly negative (`-0.05t` to `-0.08t`).

This successor information is **future at original entry** and may not be leaked into entry selection. But once a new exhaustion actually occurs, its observed onset/polarity can legitimately be used as a dynamic state transition or exit decision.

That points to a different interpretation:

> **P-O-X appears to be a branching transition precursor inside a rolling/re-origin state machine, not necessarily a single blind hold-to-60s trade state.**

## What is now open

P-O-X remains active. The next work is to determine:

1. whether `X -> opposite-polarity current` is the stable executable branch or merely the held-week survivor;
2. what causally available predecessor/timing geometry distinguishes the same-polarity branch when it works from when it decays;
3. whether a new exhaustion should terminate, reverse, or re-origin the trade state instead of allowing a fixed +60s hold to run through it;
4. whether the correct P-O-X play is a state-transition contract with dynamic exits rather than a fixed-horizon continuation rule;
5. how those branches behave across every OOT era without selecting a rule from the held week and retroactively promoting it.

The SSOS paper play remains frozen and unchanged. This addendum does not alter Phase-1 evidence, the detector, the 54-week base, held rows, runway clock, permanent Frankie, Frankie 1, or `research/kalshi/spawn.py`.

Machine-readable forensic record: `research/NG_EXHAUSTION_CHAIN_PHASE2_POX_FORENSICS_20260818.json`.
