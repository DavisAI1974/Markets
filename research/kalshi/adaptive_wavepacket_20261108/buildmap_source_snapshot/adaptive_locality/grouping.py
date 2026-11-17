"""Reversible, chronological grouping labels, not scientific calculations.

Each event remains individual; outliers remain distinct and must be reviewed.
No averaging, flattening, calculation elimination or causal-history rewrites.
"""
from __future__ import annotations
from dataclasses import dataclass
from .core import Observation, LocalityError, _digest
from .disk_index import DiskGridIndex


@dataclass(frozen=True)
class GroupProposal:
    event_id: str
    evidence_identity: str
    index_revision: int
    center_id: str
    status: str
    distance: float | None


class ShadowGrouper:
    def __init__(self, index: DiskGridIndex):
        self.index=index
        self._members: dict[str, dict] = {}
        self._head="GENESIS"
        self._entries: list[dict] = []
        self._view_aliases: dict[str, str] = {}
        self._last_order: tuple[int,str] | None = None

    def _log(self, kind: str, payload: dict):
        entry={"sequence":len(self._entries),"previous":self._head,
               "kind":kind,"payload":payload}
        entry["hash"]=_digest(entry)
        self._entries.append(entry)
        self._head=entry["hash"]

    def propose(self, obs: Observation) -> GroupProposal:
        key=(obs.event_clock,obs.event_id)
        if obs.event_id in self._members:
            previous=self._members[obs.event_id]
            if previous["evidence_identity"]!=obs.identity():
                raise LocalityError("conflicting original event evidence")
            return GroupProposal(obs.event_id,obs.identity(),self.index.revision,
                                 previous["center_id"],"DUPLICATE",None)
        if self._last_order is not None and key<=self._last_order:
            raise LocalityError("non-monotone or ambiguous causal ordering")
        if self.index.get(obs.event_id) is not None:
            raise LocalityError("preexisting untracked center evidence")
        # Causal compatibility and directional compatibility are exact filters.
        found=self.index.candidates(obs,max_neighbors=1,allow_cross_family=False,
                                    same_direction=True,historical_only=True)
        if found:
            return GroupProposal(obs.event_id,obs.identity(),self.index.revision,
                                 found[0].center_id,"ASSIGN_SHADOW_ONLY",found[0].distance)
        return GroupProposal(obs.event_id,obs.identity(),self.index.revision,
                             obs.event_id,"NEW_CENTER",None)

    def admit(self, obs: Observation, proposal: GroupProposal) -> None:
        if proposal.status not in ("ASSIGN_SHADOW_ONLY","NEW_CENTER"):
            raise LocalityError("proposal must be a new shadow decision")
        if proposal!=self.propose(obs):
            raise LocalityError("stale, contradictory, or incompatible proposal")
        if proposal.status=="NEW_CENTER":
            self.index.add(obs)
        self._members[obs.event_id]={"evidence_identity":obs.identity(),
                                     "center_id":proposal.center_id,
                                     "family":obs.family,"direction":obs.direction,
                                     "clock":obs.event_clock,"status":proposal.status}
        self._last_order=(obs.event_clock,obs.event_id)
        self._log("ADMIT_SHADOW_ONLY",{"event_id":obs.event_id,
                                      "evidence_identity":obs.identity(),
                                      "proposal":proposal.__dict__,
                                      "scientific_jobs_eliminated":0})

    def flag_outlier(self, obs: Observation, registry, reason: str):
        """Retain original evidence and a distinct shadow label before any grouping."""
        if obs.event_id in self._members:
            raise LocalityError("outlier review must occur before grouping admission")
        key=(obs.event_clock,obs.event_id)
        if self._last_order is not None and key<=self._last_order:
            raise LocalityError("outlier event violates causal input ordering")
        outcome=registry.flag(obs,reason)
        self._members[obs.event_id]={"evidence_identity":obs.identity(),
                                     "center_id":obs.event_id,
                                     "family":obs.family,"direction":obs.direction,
                                     "clock":obs.event_clock,
                                     "status":"OUTLIER_AWAITING_REVIEW"}
        self._last_order=key
        self._log("FLAG_OUTLIER",{"event_id":obs.event_id,
                                  "evidence_identity":obs.identity(),
                                  "reason":reason,"scientific_jobs_eliminated":0})
        return outcome

    def alias_view(self, old: str, new: str, reason: str) -> None:
        """Reversible display-only alias, never a mutation to original memberships."""
        if not reason or old==new or old not in self.index_ids() or new not in self.index_ids():
            raise LocalityError("invalid center alias proposal")
        old_member=self._members[old]
        new_member=self._members[new]
        if old_member["family"]!=new_member["family"] or old_member["direction"]!=new_member["direction"]:
            raise LocalityError("cross-family or direction alias prohibited")
        if old in self._view_aliases or old in self._view_aliases.values() or new in self._view_aliases or new in self._view_aliases.values():
            raise LocalityError("aliases cannot be chained or silently replaced")
        self._view_aliases[old]=new
        self._log("ALIAS_VIEW",{"old":old,"new":new,"reason":reason})

    def revert_alias(self, old: str, reason: str) -> None:
        if old not in self._view_aliases or not reason:
            raise LocalityError("unknown alias or missing reason")
        new=self._view_aliases.pop(old)
        self._log("REVERT_ALIAS",{"old":old,"new":new,"reason":reason})

    def index_ids(self):
        return {k for k,v in self._members.items() if v["center_id"]==k and
                v["status"]=="NEW_CENTER"}

    def snapshot(self):
        return {"schema":1,"metric_identity":self.index.metric.identity(),
                "source_identity":self.index.source_identity,
                "members":dict(sorted(self._members.items())),
                "view_aliases":dict(sorted(self._view_aliases.items())),
                "ledger_head":self._head,"ledger_count":len(self._entries),
                "scientific_jobs_eliminated":0,
                "outlier_count":sum(x["status"]=="OUTLIER_AWAITING_REVIEW"
                                    for x in self._members.values()),
                "averaged":0,"flattened":0,"discarded":0}

    def verify(self):
        previous="GENESIS"
        for seq,entry in enumerate(self._entries):
            if entry["sequence"]!=seq or entry["previous"]!=previous or entry["hash"]!=_digest(
                    {k:v for k,v in entry.items() if k!="hash"}):
                raise LocalityError("grouping ledger corrupted")
            previous=entry["hash"]
        if previous!=self._head:
            raise LocalityError("grouping ledger head mismatch")
        return True
