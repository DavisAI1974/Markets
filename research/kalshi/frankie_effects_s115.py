"""Explicit S115 falsifier reports for A-68 retention and A-62 specialist priors.

These reports are deliberately event-level. They may declare a mechanism inert; they do not fit a
cutoff or pool heterogeneous cells to manufacture significance.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


class EffectStop(RuntimeError):
    pass


def _index(rows: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    out = {}
    for row in rows:
        event_id = str(row.get("event_id") or "")
        if not event_id:
            raise EffectStop(f"{label} row missing event_id")
        if event_id in out:
            raise EffectStop(f"{label} duplicate event_id: {event_id}")
        out[event_id] = row
    return out


def retention_falsifier(
    *, carrying: Sequence[Mapping[str, Any]], noncarrying: Sequence[Mapping[str, Any]], lens: str,
) -> dict[str, Any]:
    """A-68: same-lens event pairs; no pooled mean.

    Each row must carry `event_id`, `lens`, and `absolute_error`. An event counts as improved only if
    the journal-carrying version has strictly lower absolute error on that same event.
    """
    a = _index(carrying, "carrying")
    b = _index(noncarrying, "noncarrying")
    if set(a) != set(b):
        raise EffectStop("A-68 retention comparison requires identical event IDs")
    pairs = []
    any_improvement = False
    for event_id in sorted(a):
        ca, no = a[event_id], b[event_id]
        if ca.get("lens") != lens or no.get("lens") != lens:
            raise EffectStop(f"A-68 cross-lens comparison on {event_id}")
        ce = float(ca["absolute_error"])
        ne = float(no["absolute_error"])
        improved = ce < ne
        any_improvement = any_improvement or improved
        pairs.append(
            {
                "event_id": event_id,
                "lens": lens,
                "carrying_absolute_error": ce,
                "noncarrying_absolute_error": ne,
                "retention_improved_this_event": improved,
            }
        )
    return {
        "verdict": "RETENTION_EVIDENCE_PRESENT" if any_improvement else "RETENTION_INERT_ONE_SESSION",
        "pooled_scalar": None,
        "pairs": pairs,
        "report_statement": (
            "A-68 retention has event-level evidence on at least one same-lens event."
            if any_improvement
            else "A-68 retention showed no same-lens event improvement; keep object-state only for contract value."
        ),
    }


def specialist_prior_falsifier(
    *, before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]], lens: str,
) -> dict[str, Any]:
    """A-62: cut priors if neither named failure nor emission improves on any matched event.

    Each row requires `event_id`, `lens`, `named_failure_present`, and `emitted`. A named failure is
    improved only when present before and absent after. Emission improves only when a previously
    non-emitting event emits after. No aggregate threshold is fitted.
    """
    b = _index(before, "before")
    a = _index(after, "after")
    if set(a) != set(b):
        raise EffectStop("A-62 prior comparison requires identical event IDs")
    pairs = []
    failure_improved = False
    emission_improved = False
    for event_id in sorted(a):
        pre, post = b[event_id], a[event_id]
        if pre.get("lens") != lens or post.get("lens") != lens:
            raise EffectStop(f"A-62 cross-lens comparison on {event_id}")
        fi = bool(pre.get("named_failure_present")) and not bool(post.get("named_failure_present"))
        ei = (not bool(pre.get("emitted"))) and bool(post.get("emitted"))
        failure_improved = failure_improved or fi
        emission_improved = emission_improved or ei
        pairs.append(
            {
                "event_id": event_id,
                "lens": lens,
                "failure_improved_this_event": fi,
                "emission_improved_this_event": ei,
            }
        )
    inert = not failure_improved and not emission_improved
    return {
        "verdict": "INERT_CUT" if inert else "PRIOR_EFFECT_PRESENT",
        "pooled_scalar": None,
        "pairs": pairs,
        "report_statement": (
            "A-62 specialist priors changed neither the named failure nor emission on matched events; cut them."
            if inert
            else "A-62 specialist priors have event-level evidence in the named failure or emission path."
        ),
    }
