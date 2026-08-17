"""Review-only learning proposals; no result automatically changes either trader or Frankie 1."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

from .hashing import new_id, to_primitive, utc_now
from .ledger import ImmutableTradingLedger


class LessonType(str, enum.Enum):
    FORECAST = "FORECAST_LESSON"
    TRADING = "TRADING_LESSON"
    EXECUTION = "EXECUTION_LESSON"
    RISK = "RISK_LESSON"


@dataclass(frozen=True)
class LearningProposal:
    proposal_id: str
    venue: str
    lesson_type: LessonType
    evidence_ids: tuple[str, ...]
    claim: str
    created_at: str
    reviewed: bool = False
    automatic_application: bool = False

    def as_dict(self) -> dict[str, Any]:
        return to_primitive(self)


def propose_lesson(
    *,
    ledger: ImmutableTradingLedger,
    venue: str,
    lesson_type: LessonType,
    evidence_ids: tuple[str, ...],
    claim: str,
    correlation_id: str,
) -> LearningProposal:
    proposal = LearningProposal(
        proposal_id=new_id("learning-proposal"),
        venue=venue,
        lesson_type=lesson_type,
        evidence_ids=evidence_ids,
        claim=claim,
        created_at=utc_now().isoformat().replace("+00:00", "Z"),
    )
    ledger.append(
        "learning_proposals", proposal.as_dict(), correlation_id=correlation_id,
        source_id=proposal.proposal_id, venue=venue,
    )
    return proposal
