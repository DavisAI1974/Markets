"""Two sections computing one estimand cannot both be right. The gate that says so.

**Why this exists.** Section 4.9 and section 4.12 both compute `(bid - ask)/(bid + ask)` on
the same day and the same instrument. On run 33605852433, 4.9 returned exactly +/-1.0 on
**152 of its 154** readings while 4.12 returned `[0.0116, 0.1109]` on **3,454** and never once
reached a bound. One of them was reading a one-sided, top-of-book view rather than the
reconstructed full book the run already stores at 10.13 GB. **All eight section-6 gates
passed.**

They passed because every existing gate checks a section against ITSELF - are the
denominators declared, is the population reconciled, do the exact members sit beneath the
summary - and a one-sided book satisfies all of that perfectly. It is present, typed, in
range, self-consistent, and wrong. The only thing that separates it from a correct book is
another computation of the same quantity, which was sitting in the same artifact, and nothing
compared them.

**So this gate is horizontal, and it is the only horizontal one.** It reads the declared
register of estimands that more than one section computes, aggregates each section's own
averaged companions, and fails the calculation when they disagree beyond a stated tolerance.

**Why the test is distributional rather than a range check.** A range check would not have
caught this: 4.9's `[-1, 1]` CONTAINS 4.12's `[0.0116, 0.1109]`. What separates them is
shape - one is pinned to its bounds and the other never approaches them. So agreement is
tested on two statistics that survive re-stratification, since two sections legitimately
stratify differently and their strata need not correspond:

- the **population-weighted mean**, invariant to how the same members are grouped;
- the **population-weighted second moment**, `sum(sum_of_squares) / sum(n)`, which measures
  how far from zero the members sit REGARDLESS OF SIGN;
- the **extreme share**, the fraction of members sitting at the estimand's declared bounds.

**The second moment is the one that cannot be dodged, and it is why the first version of
this gate was not enough.** Mean and extreme share both cancel under sign symmetry: a
section pinned half at +1 and half at -1 has a mean of 0.0, and if a stratum straddles both
bounds its extreme share is 0.0 too, because a summary cannot be resolved into members. So a
100%-degenerate section passed simply by being stratified differently - the real run only
fired because 4.9's strata happened to be sign-pure. `E[x^2]` is about 1.0 for that section
and about 0.004 for a section living in [0.0116, 0.1109], on every stratification of either.
`sum_of_squares` is already emitted on every distribution row and was going unread.

**The extreme share is counted conservatively.** From per-stratum summaries a mixed stratum -
minimum at one bound, maximum at the other - cannot be resolved into members, so it
contributes nothing. That undercounts and never overcounts, so a firing gate is always
reporting at least the divergence it names. It is retained as a diagnostic because when it
does fire it names the defect precisely; it is no longer relied on alone.

**A declared member that goes missing while its counterpart speaks is also a failure.** A
section that should compute an estimand and emitted nothing has not agreed with anyone, and
silence is the one reading this gate must never accept as consensus - that is the 4.2 shape,
where the section summarising the full book produced nothing and its absence read as assent.
But when EVERY member is silent the estimand was simply never exercised, which is a coverage
question the coverage and denominator gates already own; failing it here would reject every
short slice for a defect it does not have.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

# THE REGISTER. Each entry names an estimand that more than one section computes, the members
# that compute it, and what counts as disagreement. Entries are added when a shared estimand
# is identified, never when a disagreement is found - a register that grows only in response
# to known defects tests only the defects already known.
SHARED_ESTIMANDS: tuple[dict[str, Any], ...] = (
    {
        "estimand": "relative_book_imbalance",
        "formula": "(bid - ask) / (bid + ask)",
        "members": (("4.9", "relative_imbalance"), ("4.12", "normalized_imbalance")),
        "bounds": (-1.0, 1.0),
        # A bounded estimand on one instrument and one day. Two correct computations of it
        # can differ by re-stratification and by population, but not by this much in the mean.
        "max_mean_divergence": 0.05,
        # E[x^2]. A section pinned at the bounds sits near 1.0; one living inside
        # [0.0116, 0.1109] sits near 0.004. Neither cancels, and neither moves when the
        # same members are re-stratified.
        "max_second_moment_divergence": 0.10,
        # The one that actually fires here. 4.9 sat at 98.7% pinned, 4.12 at 0.0%.
        "max_extreme_share_divergence": 0.25,
        # Above this many observations in one member, a declared counterpart emitting
        # NOTHING is a defect rather than a coverage accident. Below it a short slice
        # legitimately fails to exercise one of the two - 4.12 needs candidate episodes
        # that a three-group fixture never produces. The threshold is DECLARED per
        # entry rather than global, because how much traffic an estimand needs before
        # silence becomes suspicious is a property of the estimand, not of the gate.
        "silence_is_a_defect_above_n": 1000,
        # Below this many observations a member is REPORTED and not compared. A book
        # with a genuinely empty ask yields exactly +1.0, and four such readings are a
        # true fact about a short slice, not grounds to reject a fourteen-hour run.
        "compare_above_n": 30,
        "basis": (
            "both sections declare the same formula over the same book on the same "
            "instrument and day; a difference in shape is a difference in substrate"
        ),
    },
)

EXTREME_TOLERANCE = 0.01  # within 1% of a bound counts as sitting at it


class AgreementError(ValueError):
    """A register entry is malformed. Distinct from the sections disagreeing."""


def _observation_count(value: Mapping[str, Any]) -> int:
    """How many observations a companion row stands for, whatever measure produced it.

    Mirrors the runner's own function. Reading `value["n"]` alone values a RATIO_PAIR or a
    SURVIVAL row at zero - so a register entry naming one of those measures would report
    "absent on every stratum" forever, and the gate would be permanently, silently blind to
    exactly the pairing it was added to watch.
    """
    if "n" in value:
        return int(value.get("n") or 0)
    if "total_observations" in value:
        return int(value.get("total_observations") or 0)
    nested = value.get("member_ratio_distribution")
    if isinstance(nested, Mapping):
        return int(nested.get("n") or 0)
    return 0


def _numeric(value: Any) -> float | None:
    """A real number, or None. `True` is not a number here and neither is a string."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _aggregate(rows: Iterable[Mapping[str, Any]], bounds: tuple[float, float]) -> dict[str, Any]:
    """Population-weighted aggregate of one section's own averaged companions.

    Uses `sum` and `n` rather than averaging the per-stratum means, because a mean of means
    weights a stratum of one member the same as a stratum of a thousand - which is the shape
    of error this whole programme keeps finding.

    REFUSES rather than skips a populated row whose `sum` is missing or non-numeric. Skipping
    it added the row's population to the denominator with nothing in the numerator, so a
    section with no sums at all reported a mean of exactly 0.0 - present, typed, in range,
    and measuring nothing, which is the failure class this module exists to catch.
    """
    low, high = bounds
    span = high - low
    total_n = 0
    total_sum = 0.0
    total_squares = 0.0
    squares_known = True
    minimum: float | None = None
    maximum: float | None = None
    extreme_n = 0
    strata = 0
    for row in rows:
        value = row.get("value") or {}
        if not isinstance(value, Mapping):
            raise AgreementError(f"{row.get('section')}:{row.get('measure')} has no value object")
        n = _observation_count(value)
        if n < 0:
            raise AgreementError(
                f"{row.get('section')}:{row.get('measure')} declares a negative population"
            )
        if n == 0:
            continue
        total = _numeric(value.get("sum"))
        if total is None:
            raise AgreementError(
                f"{row.get('section')}:{row.get('measure')} carries {n} observations with no "
                "numeric sum; a population with no numerator would read as a mean of zero"
            )
        strata += 1
        total_n += n
        total_sum += total
        squares = _numeric(value.get("sum_of_squares"))
        if squares is None:
            squares_known = False
        else:
            total_squares += squares
        lo, hi = _numeric(value.get("minimum")), _numeric(value.get("maximum"))
        if lo is not None:
            minimum = lo if minimum is None else min(minimum, lo)
        if hi is not None:
            maximum = hi if maximum is None else max(maximum, hi)
        # CONSERVATIVE: only a stratum wholly at one bound contributes. A mixed stratum
        # cannot be resolved into members from a summary, so it contributes nothing rather
        # than an estimate. This is why it cannot be the only test - see the module docstring.
        if lo is not None and hi is not None:
            at_low = abs(lo - low) <= EXTREME_TOLERANCE * span and \
                abs(hi - low) <= EXTREME_TOLERANCE * span
            at_high = abs(lo - high) <= EXTREME_TOLERANCE * span and \
                abs(hi - high) <= EXTREME_TOLERANCE * span
            if at_low or at_high:
                extreme_n += n
    return {
        "n": total_n,
        "strata": strata,
        "mean": (total_sum / total_n) if total_n else None,
        # None, never zero, when a measure does not emit sum_of_squares - an unknown
        # dispersion must not be comparable to a known one.
        "second_moment": (total_squares / total_n) if (total_n and squares_known) else None,
        "minimum": minimum,
        "maximum": maximum,
        "extreme_share": (extreme_n / total_n) if total_n else None,
        "extreme_n": extreme_n,
    }


def compare(
    averaged_rows: Sequence[Mapping[str, Any]],
    register: Sequence[Mapping[str, Any]] = SHARED_ESTIMANDS,
) -> list[dict[str, Any]]:
    """One verdict per register entry. Returns rows; raises only on a malformed register."""
    verdicts: list[dict[str, Any]] = []
    for entry in register:
        for field in ("estimand", "members", "bounds", "max_mean_divergence",
                      "max_second_moment_divergence", "max_extreme_share_divergence"):
            if field not in entry:
                raise AgreementError(f"register entry missing {field!r}")
        if len(entry["members"]) < 2:
            raise AgreementError(
                f"{entry['estimand']}: a shared estimand needs at least two computations; "
                "one section agreeing with itself is what the existing gates already check"
            )
        bounds = tuple(entry["bounds"])
        # Reversed or malformed bounds make `span` negative, and every "within tolerance of a
        # bound" test then returns false - silently disabling the extreme-share check for the
        # whole entry while the gate reports a clean pass.
        if len(bounds) != 2 or any(_numeric(b) is None for b in bounds) or bounds[0] >= bounds[1]:
            raise AgreementError(
                f"{entry['estimand']}: bounds must be (low, high) with low < high, got {bounds!r}"
            )
        observed: dict[str, dict[str, Any]] = {}
        absent: list[str] = []
        for section, measure in entry["members"]:
            rows = [
                r for r in averaged_rows
                if str(r.get("section")) == section and str(r.get("measure")) == measure
            ]
            agg = _aggregate(rows, bounds)
            observed[f"{section}:{measure}"] = agg
            if not agg["n"]:
                absent.append(f"{section}:{measure}")

        problems: list[str] = []
        notes: list[str] = []
        populated = {k: v for k, v in observed.items() if v["n"]}
        loudest = max((v["n"] for v in populated.values()), default=0)
        floor = entry.get("compare_above_n", 0)
        # A member too small to compare is REPORTED, not compared and not dropped. A book
        # with a genuinely empty ask yields exactly +1.0, and a handful of such readings on a
        # short slice is a true measurement, not grounds to reject the run.
        comparable = {k: v for k, v in populated.items() if v["n"] >= floor}
        for name, agg in sorted(populated.items()):
            if name not in comparable:
                notes.append(
                    f"{name} carries only {agg['n']} observations, below the declared "
                    f"comparison floor of {floor}, so it is recorded and not compared"
                )
            lo, hi = agg["minimum"], agg["maximum"]
            # Free, and a defect on its face: a value outside the estimand's own declared
            # bounds cannot be the estimand, whatever it agrees with.
            if (lo is not None and lo < bounds[0]) or (hi is not None and hi > bounds[1]):
                problems.append(
                    f"{name} observed [{lo}, {hi}] outside its declared bounds "
                    f"{bounds}; the values are not the estimand they are labelled as"
                )
        if absent and populated:
            # SILENCE IS NOT AGREEMENT - but only where there was something to agree WITH.
            # One section computing the estimand while its declared counterpart emits
            # nothing is exactly the shape of the 4.2 defect: the companion did not concur,
            # it went missing, and a single unopposed reading then stands as consensus.
            said = (
                f"{', '.join(absent)} produced no populated stratum while "
                f"{', '.join(sorted(populated))} did (n={loudest}), for an estimand all of "
                "them are declared to compute"
            )
            if loudest > entry.get("silence_is_a_defect_above_n", float("inf")):
                problems.append(said)
            else:
                # D60: RECORDED, never silently tolerated. Below the declared threshold this
                # is reported and does not reject, because it is indistinguishable here from
                # a slice too short to exercise the section.
                notes.append(
                    said + " - below the declared threshold of "
                    f"{entry.get('silence_is_a_defect_above_n')}, so recorded rather than "
                    "rejected; a slice this short may simply not exercise it"
                )
        # Every member silent means the estimand was not exercised at all in this traversal -
        # a short slice, or a day with none of the relevant events. That is a COVERAGE
        # question, already owned by the coverage and denominator gates, and answering it
        # here would reject every small run for a defect it does not have.
        if len(comparable) >= 2:
            populated = comparable
            moments = {k: v["second_moment"] for k, v in populated.items()
                       if v["second_moment"] is not None}
            if len(moments) >= 2:
                moment_spread = max(moments.values()) - min(moments.values())
                if moment_spread > entry["max_second_moment_divergence"]:
                    problems.append(
                        f"population-weighted second moments differ by {moment_spread:.4f} "
                        f"(> {entry['max_second_moment_divergence']}): "
                        + ", ".join(f"{k}={v:.4f}" for k, v in moments.items())
                        + " - E[x^2] does not cancel under sign symmetry and does not move "
                          "under re-stratification, so this is a substrate difference"
                    )
            elif moments:
                notes.append(
                    f"{entry['estimand']}: only {len(moments)} of {len(populated)} members "
                    "emit sum_of_squares, so the second moment could not be compared"
                )
            means = {k: v["mean"] for k, v in populated.items()}
            spread = max(means.values()) - min(means.values())
            if spread > entry["max_mean_divergence"]:
                problems.append(
                    f"population-weighted means differ by {spread:.4f} "
                    f"(> {entry['max_mean_divergence']}): "
                    + ", ".join(f"{k}={v:.4f}" for k, v in means.items())
                )
            shares = {k: v["extreme_share"] for k, v in populated.items()}
            share_spread = max(shares.values()) - min(shares.values())
            if share_spread > entry["max_extreme_share_divergence"]:
                problems.append(
                    f"share of members sitting at the bounds differs by {share_spread:.3f} "
                    f"(> {entry['max_extreme_share_divergence']}): "
                    + ", ".join(f"{k}={v:.3f}" for k, v in shares.items())
                    + " - a bounded estimand pinned to its bounds in one section and never "
                      "reaching them in another is a substrate difference, not a stratum one"
                )
        verdicts.append({
            "estimand": entry["estimand"],
            "formula": entry.get("formula"),
            "basis": entry.get("basis"),
            "agreed": not problems,
            "problems": problems,
            "notes": notes,
            "observed": observed,
        })
    return verdicts


def gate_detail(verdicts: Sequence[Mapping[str, Any]]) -> tuple[bool, str]:
    """Collapse the verdicts into the (passed, detail) a section-6 gate reports."""
    failed = [v for v in verdicts if not v["agreed"]]
    if not verdicts:
        return True, "no shared estimands are registered"
    noted = [n for v in verdicts for n in v.get("notes", ())]
    if not failed:
        detail = f"{len(verdicts)} shared estimand(s) agree across the sections that compute them"
        # A pass carrying a note is still a pass, but the note is never dropped - that is the
        # difference between tolerating an absence and hiding one.
        return True, detail + (" | NOTED: " + "; ".join(noted) if noted else "")
    parts = [f"{v['estimand']}: " + "; ".join(v["problems"]) for v in failed]
    return False, " | ".join(parts) + (" | NOTED: " + "; ".join(noted) if noted else "")
