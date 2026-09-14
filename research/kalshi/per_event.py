"""per_event.py - the reporting contract for any measurement on this desk.

WHY THIS EXISTS. The rule has been written in the docs since S80 and re-derived by hand in S108
(D4), S111 and again in S113: "EACH TRADE INDIVIDUALLY, never average... every aggregate blurs away
the per-trade fingerprint that IS the predictive content. Characterize the DISTRIBUTION and the
per-trade fingerprint; never lead with the mean." Writing it down has not been enough. In one S113
session a single analysis reported (1) a POOLED correlation whose sign was the opposite of every
constituent seasonal cell, (2) an R2 that flattered a 56%-of-weeks record, and (3) an OLS slope -
itself an averaged coefficient - as if it were evidence. Greg caught all three.

So this is the rule as a FUNCTION rather than a sentence. The point is not that averages are
forbidden arithmetic; it is that an average may never be the VERDICT, and the per-event record must
be printed beside it every time, without the analyst having to remember.

THE SECOND RULE IT ENFORCES, learned the same session: an observation and the story explaining it
are INDEPENDENT. A refuted mechanism does not demote the observation it was invented to explain -
our thoughts are guesses, the data is the finding. So `explanation` is recorded separately from the
evidence and is never allowed to change the numbers above it.

Usage:
    from per_event import report
    report("breadth vs storage", weeks, actual, baseline, candidate,
           labels=[...], explanation="hypothesis, may be refuted without touching the evidence")
"""
from __future__ import annotations


def _q(vals, p):
    s = sorted(vals)
    return s[int(p * (len(s) - 1))] if s else 0.0


def report(title, keys, actual, baseline_pred, candidate_pred=None, *,
           explanation=None, top_n=8, units=""):
    """Print the per-event record. `keys` name each event (a date, a trade id, a week).

    Never returns a single summary number, deliberately - there is no scalar to quote out of
    context. sum|err| is included because D4 names it explicitly, alongside drift, and it does not
    cancel; the mean is not printed at all.
    """
    n = len(keys)
    eb = [a - b for a, b in zip(actual, baseline_pred)]
    ec = [a - c for a, c in zip(actual, candidate_pred)] if candidate_pred else None
    print(f"=== {title}   n={n}")
    print(f"  D4 SET (never one of these alone):")
    for lab, e in (("baseline", eb), ("candidate", ec)):
        if e is None:
            continue
        print(f"    {lab:<10} sum|err| {sum(map(abs, e)):>10.1f}{units}   drift {sum(e):>+10.1f}{units}"
              f"   survives {(100*abs(sum(e))/sum(map(abs,e)) if sum(map(abs,e)) else 0):>5.0f}%"
              f"   |err| p50 {_q(list(map(abs,e)),.5):>8.1f}  p90 {_q(list(map(abs,e)),.9):>8.1f}"
              f"  MAX {max(map(abs,e)):>8.1f}")
    if ec:
        imp = sum(1 for x, y in zip(eb, ec) if abs(y) < abs(x))
        print(f"    events improved {imp}/{n}   worsened {n-imp}/{n}"
              f"   -- a count, not a rate; read the events below before believing it")
    order = sorted(range(n), key=lambda i: -abs(actual[i]))
    print(f"  THE {min(top_n,n)} LARGEST ACTUAL MOVES - where being wrong costs, named individually:")
    for i in order[:top_n]:
        line = f"    {str(keys[i]):<12} actual {actual[i]:>+9.1f}{units}  baseline err {eb[i]:>+9.1f}"
        if ec:
            line += f"  candidate err {ec[i]:>+9.1f}  {'better' if abs(ec[i])<abs(eb[i]) else 'WORSE'}"
        print(line)
    if ec:
        big = sorted(range(n), key=lambda i: -abs(ec[i]))[:min(4, n)]
        print(f"  WORST REMAINING EVENTS after the candidate:")
        for i in big:
            print(f"    {str(keys[i]):<12} actual {actual[i]:>+9.1f}{units}  err {ec[i]:>+9.1f}")
    print("  A CANDIDATE THAT ORDERS THE QUIET MIDDLE AND MISSES THE LARGEST MOVES HAS NOT HELPED.")
    if explanation:
        print(f"  EXPLANATION (a GUESS, recorded separately - refuting it does NOT demote the")
        print(f"  evidence above, which stands or falls on its own): {explanation}")
