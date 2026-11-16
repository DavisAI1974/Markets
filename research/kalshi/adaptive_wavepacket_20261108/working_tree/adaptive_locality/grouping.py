"""Reversible, chronological grouping labels, not scientific calculations.

Each event remains individual; outliers remain distinct and must be reviewed.
No averaging, flattening, calculation elimination or causal-history rewrites.
"""
from __future__ import annotations
from dataclasses import dataclass
from .core import Observation, LocalityError, _digest
from .disk_index import DiskGridIndex


# Ledger kinds that would mean science was reduced; none is ever emitted by this
# module, and the snapshot counters are DERIVED from the ledger so that stays checkable.
REDUCTION_KINDS={"discarded":"DISCARD","averaged":"AVERAGE","flattened":"FLATTEN"}


@dataclass(frozen=True)
class GroupProposal:
    event_id: str
    evidence_identity: str
    index_revision: int
    center_id: str
    status: str
    distance: float | None
    # E-4: the candidates beyond the nearest, plus the index's truncation disclosure (E-6).
    alternatives: tuple[tuple[str, float], ...] = ()
    total_in_radius: int = 0
    truncated: bool = False


class ShadowGrouper:
    def __init__(self, index: DiskGridIndex, *, alternatives: int = 8):
        if type(alternatives) is not int or alternatives < 0:
            raise LocalityError("alternatives must be a non-negative integer")
        self.index=index
        self.alternatives=alternatives
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

    def _refuse(self, event_id: str, reason: str, **extra):
        """E-4: every refusal is a recoverable ledger entry BEFORE the error is raised."""
        self._log("REFUSED",{"event_id":event_id,"reason":reason,
                             "scientific_jobs_eliminated":0,**extra})
        raise LocalityError(reason)

    def propose(self, obs: Observation) -> GroupProposal:
        key=(obs.event_clock,obs.event_id)
        if obs.event_id in self._members:
            previous=self._members[obs.event_id]
            if previous["evidence_identity"]!=obs.identity():
                self._refuse(obs.event_id,"conflicting original event evidence",
                             evidence_identity=obs.identity(),
                             member_evidence_identity=previous["evidence_identity"])
            return GroupProposal(obs.event_id,obs.identity(),self.index.revision,
                                 previous["center_id"],"DUPLICATE",None)
        if self._last_order is not None and key<=self._last_order:
            self._refuse(obs.event_id,"non-monotone or ambiguous causal ordering",
                         evidence_identity=obs.identity(),clock=obs.event_clock,
                         last_order=list(self._last_order))
        if self.index.get(obs.event_id) is not None:
            self._refuse(obs.event_id,"preexisting untracked center evidence",
                         evidence_identity=obs.identity())
        # Causal compatibility and directional compatibility are exact filters.
        report=self.index.candidate_report(obs,max_neighbors=1+self.alternatives,
                                           allow_cross_family=False,
                                           same_direction=True,historical_only=True)
        found=report["hits"]
        if found:
            return GroupProposal(obs.event_id,obs.identity(),report["revision"],
                                 found[0].center_id,"ASSIGN_SHADOW_ONLY",found[0].distance,
                                 tuple((h.center_id,h.distance) for h in found[1:]),
                                 report["total_in_radius"],report["truncated"])
        return GroupProposal(obs.event_id,obs.identity(),report["revision"],
                             obs.event_id,"NEW_CENTER",None,(),0,False)

    def admit(self, obs: Observation, proposal: GroupProposal) -> None:
        if proposal.status not in ("ASSIGN_SHADOW_ONLY","NEW_CENTER"):
            self._refuse(obs.event_id,"proposal must be a new shadow decision",
                         evidence_identity=obs.identity(),proposal_status=proposal.status)
        if proposal!=self.propose(obs):
            self._refuse(obs.event_id,"stale, contradictory, or incompatible proposal",
                         evidence_identity=obs.identity(),proposal=proposal.__dict__)
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
            self._refuse(obs.event_id,"outlier review must occur before grouping admission",
                         evidence_identity=obs.identity(),outlier_reason=reason)
        key=(obs.event_clock,obs.event_id)
        if self._last_order is not None and key<=self._last_order:
            self._refuse(obs.event_id,"outlier event violates causal input ordering",
                         evidence_identity=obs.identity(),outlier_reason=reason,
                         clock=obs.event_clock,last_order=list(self._last_order))
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
            self._refuse(old,"invalid center alias proposal",new=new,alias_reason=reason)
        old_member=self._members[old]
        new_member=self._members[new]
        if old_member["family"]!=new_member["family"] or old_member["direction"]!=new_member["direction"]:
            self._refuse(old,"cross-family or direction alias prohibited",new=new,alias_reason=reason)
        if old in self._view_aliases or old in self._view_aliases.values() or new in self._view_aliases or new in self._view_aliases.values():
            self._refuse(old,"aliases cannot be chained or silently replaced",new=new,alias_reason=reason)
        self._view_aliases[old]=new
        self._log("ALIAS_VIEW",{"old":old,"new":new,"reason":reason})

    def revert_alias(self, old: str, reason: str) -> None:
        if old not in self._view_aliases or not reason:
            self._refuse(old,"unknown alias or missing reason",alias_reason=reason)
        new=self._view_aliases.pop(old)
        self._log("REVERT_ALIAS",{"old":old,"new":new,"reason":reason})

    def index_ids(self):
        return {k for k,v in self._members.items() if v["center_id"]==k and
                v["status"]=="NEW_CENTER"}

    def ledger_kind_counts(self) -> dict[str,int]:
        counts: dict[str,int] = {}
        for entry in self._entries:
            counts[entry["kind"]]=counts.get(entry["kind"],0)+1
        return dict(sorted(counts.items()))

    def snapshot(self):
        kinds=self.ledger_kind_counts()
        return {"schema":1,"metric_identity":self.index.metric.identity(),
                "source_identity":self.index.source_identity,
                "alternatives":self.alternatives,
                "members":dict(sorted(self._members.items())),
                "view_aliases":dict(sorted(self._view_aliases.items())),
                "ledger_head":self._head,"ledger_count":len(self._entries),
                "entries":[dict(e) for e in self._entries],
                "last_order":list(self._last_order) if self._last_order is not None else None,
                "scientific_jobs_eliminated":0,
                "outlier_count":sum(x["status"]=="OUTLIER_AWAITING_REVIEW"
                                    for x in self._members.values()),
                # E-16: derived from ledger kinds, not declared constants.
                "counter_derivation":"derived from ledger kinds",
                "ledger_kind_counts":kinds,
                "refused":kinds.get("REFUSED",0),
                **{name:kinds.get(kind,0) for name,kind in REDUCTION_KINDS.items()}}

    @classmethod
    def recover(cls, index: DiskGridIndex, snapshot: dict) -> "ShadowGrouper":
        """E-4: rebuild from snapshot(); the ledger chain is verified before use."""
        if not isinstance(snapshot,dict) or snapshot.get("schema")!=1:
            raise LocalityError("unsupported grouping snapshot")
        if (snapshot.get("metric_identity")!=index.metric.identity()
                or snapshot.get("source_identity")!=index.source_identity):
            raise LocalityError("grouping snapshot index identity mismatch")
        grouper=cls(index,alternatives=snapshot.get("alternatives",8))
        entries=snapshot.get("entries")
        members=snapshot.get("members")
        aliases=snapshot.get("view_aliases")
        if not isinstance(entries,list) or not isinstance(members,dict) or not isinstance(aliases,dict):
            raise LocalityError("incomplete grouping snapshot")
        grouper._entries=[dict(e) for e in entries]
        grouper._head=snapshot.get("ledger_head")
        if snapshot.get("ledger_count")!=len(grouper._entries):
            raise LocalityError("grouping ledger count mismatch")
        grouper.verify()
        grouper._members={k:dict(v) for k,v in members.items()}
        grouper._view_aliases=dict(aliases)
        last=snapshot.get("last_order")
        grouper._last_order=None if last is None else (int(last[0]),str(last[1]))
        return grouper

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
