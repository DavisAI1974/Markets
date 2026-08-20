#!/usr/bin/env python3
"""Isolated bridge from a causal discovery receipt to the frozen runway engine.

The frozen runway engine is allowed to retain canonical retrospective t0 as structural
metadata. This adapter prevents that t0 from becoming an availability clock: activation
and every V4 evaluation are forbidden before the receipt's event_known_by timestamp.
No frozen source is modified.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Any

from research.kalshi.ng_exhaustion_v4_causal_clock import CausalClockError,CausalDiscoveryReceipt,validate_availability_chain


@dataclass(frozen=True)
class AuthorizedV4Event:
    event_id:str
    session_id:str
    canonical_t0:float
    event_known_by:float
    activation_second:int
    discovery_receipt_hash:str
    frozen_runway_event:Any

    def assert_evaluation_time(self, *, feature_available_at:float, model_evaluated_at:float,
                               decision_available_at:float) -> None:
        if feature_available_at < self.event_known_by:
            raise CausalClockError("V4 feature evaluation attempted before event_known_by")
        if not self.event_known_by <= feature_available_at <= model_evaluated_at <= decision_available_at:
            raise CausalClockError("V4 evaluation clock order violated")


def activate_frozen_runway(*, receipt:CausalDiscoveryReceipt, runway_engine:Any) -> AuthorizedV4Event:
    """Activate the unchanged runway only after the event is lawfully discoverable.

    `runway_engine` must expose `.feed.last_seen_second` and `.mark_event(event_id,
    session_id,t0_second)` like LiveExhaustionRunwayEngine. The old engine still receives
    canonical t0 because its frozen geometry is defined around that structural anchor;
    the wrapper's activation/evaluation wall prevents t0 from granting earlier knowledge.
    """
    receipt.validate()
    activation_second=int(math.ceil(receipt.event_known_by))
    feed=getattr(runway_engine,"feed",None)
    last=getattr(feed,"last_seen_second",None)
    if last is None or int(last) < activation_second:
        raise CausalClockError(
            f"runway activation requires feed through event_known_by: last={last}, required={activation_second}"
        )
    canonical=receipt.canonical_t0
    if abs(canonical-round(canonical))>1e-9:
        raise CausalClockError("frozen runway canonical_t0 must resolve to an integer second")
    event=runway_engine.mark_event(
        event_id=receipt.event_id,
        session_id=receipt.session_id,
        t0_second=int(round(canonical)),
    )
    return AuthorizedV4Event(
        event_id=receipt.event_id,
        session_id=receipt.session_id,
        canonical_t0=receipt.canonical_t0,
        event_known_by=receipt.event_known_by,
        activation_second=activation_second,
        discovery_receipt_hash=receipt.receipt_hash,
        frozen_runway_event=event,
    )


def authorize_v4_evaluation(*, receipt:CausalDiscoveryReceipt, feature_available_at:float,
                            model_evaluated_at:float, decision_available_at:float) -> dict[str,float]:
    """Shared gate for any V4 path that does not instantiate the runway wrapper."""
    return validate_availability_chain(
        receipt,
        feature_available_at=feature_available_at,
        model_evaluated_at=model_evaluated_at,
        decision_available_at=decision_available_at,
    )
