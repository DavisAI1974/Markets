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

- the **population-weighted mean**, which is invariant to how the same members are grouped;
- the **extreme share**, the fraction of members sitting at the estimand's declared bounds.

**The extreme share is counted conservatively.** From per-stratum summaries a mixed stratum -
minimum at one bound, maximum at the other - cannot be resolved into members, so it
contributes nothing. That undercounts and never overcounts, so a firing gate is always
reporting at least the divergence it names.

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
        # The one that actually fires here. 4.9 sat at 98.7% pinned, 4.12 at 0.0%.
        "max_extreme_share_divergence": 0.25,
        # Above this many observations in one member, a declared counterpart emitting
        # NOTHING is a defect rather than a coverage accident. Below it a short slice
        # legitimately fails to exercise one of the two - 4.12 needs candidate episodes
        # that a three-group fixture never produces. The threshold is DECLARED per
        # entry rather than global, because how much traffic an estimand needs before
        # silence becomes suspicious is a property of the estimand, not of the gate.
        "silence_is_a_defect_above_n": 1000,
        "basis": (
            "both sections declare the same formula over the same book on the same "
            "instrument and day; a difference in shape is a difference in substrate"
        ),
    },
)

EXTREME_TOLERANCE = 0.01  # within 1% of a bound counts as sitting at it


class AgreementError(ValueError):
    """A register entry is malformed. Distinct from the sections disagreeing."""


def _aggregate(rows: Iterable[Mapping[str, Any]], bounds: tuple[float, float]) -> dict[str, Any]:
    """Population-weighted aggregate of one section's own averaged companions.

    Uses `sum` and `n` rather than averaging the per-stratum means, because a mean of means
    weights a stratum of one member the same as a stratum of a thousand - which is the shape
    of error this whole programme keeps finding.
    """
    low, high = bounds
    span = high - low
    total_n = 0
    total_sum = 0.0
    minimum: float | None = None
    maximum: float | None = None
    extreme_n = 0
    strata = 0
    for row in rows:
        value = row.get("value") or {}
        n = value.get("n") or 0
        if not isinstance(n, int) or n <= 0:
            continue
        strata += 1
        total_n += n
        if isinstance(value.get("sum"), (int, float)):
            total_sum += float(value["sum"])
        lo, hi = value.get("minimum"), value.get("maximum")
        if isinstance(lo, (int, float)):
            minimum = float(lo) if minimum is None else min(minimum, float(lo))
        if isinstance(hi, (int, float)):
            maximum = float(hi) if maximum is None else max(maximum, float(hi))
        # CONSERVATIVE: only a stratum wholly at one bound contributes. A mixed stratum
        # cannot be resolved into members from a summary, so it contributes nothing rather
        # than an estimate.
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
            at_low = abs(float(lo) - low) <= EXTREME_TOLERANCE * span and \
                abs(float(hi) - low) <= EXTREME_TOLERANCE * span
            at_high = abs(float(lo) - high) <= EXTREME_TOLERANCE * span and \
                abs(float(hi) - high) <= EXTREME_TOLERANCE * span
            if at_low or at_high:
                extreme_n += n
    return {
        "n": total_n,
        "strata": strata,
        "mean": (total_sum / total_n) if total_n else None,
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
                      "max_extreme_share_divergence"):
            if field not in entry:
                raise AgreementError(f"register entry missing {field!r}")
        if len(entry["members"]) < 2:
            raise AgreementError(
                f"{entry['estimand']}: a shared estimand needs at least two computations; "
                "one section agreeing with itself is what the existing gates already check"
            )
        bounds = tuple(entry["bounds"])
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
        if len(populated) >= 2:
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
