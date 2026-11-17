"""Bounded in-memory ready-group queue with explicit replay and no external execution."""
from dataclasses import dataclass
from .core import LocalityError,_digest

@dataclass(frozen=True)
class ReadyGroup:
    group_id:str
    source_identity:str
    feature_identity:str
    evidence_ids:tuple[str,...]
    family:str
    direction:str
    def __post_init__(self):
        if not all((self.group_id,self.source_identity,self.feature_identity,self.family,self.direction)):
            raise LocalityError("missing group contract")
        if not self.evidence_ids or len(set(self.evidence_ids))!=len(self.evidence_ids):
            raise LocalityError("missing or repeated evidence")
    def identity(self):
        return _digest(self.__dict__)

class ShadowQueue:
    """No background workers, scientific calculations, network, or AWS calls."""
    def __init__(self,capacity:int=1024):
        if capacity<1: raise LocalityError("capacity must be positive")
        self.capacity=capacity
        self.pending:dict[str,ReadyGroup]={}
        self.completed:dict[str,str]={}
    def submit(self,group:ReadyGroup)->str:
        digest=group.identity()
        if group.group_id in self.completed:
            if self.completed[group.group_id]!=digest: raise LocalityError("completed ID conflict")
            return "ALREADY_COMPLETED"
        if group.group_id in self.pending:
            if self.pending[group.group_id].identity()!=digest: raise LocalityError("pending ID conflict")
            return "ALREADY_PENDING"
        if len(self.pending)>=self.capacity: return "BACKPRESSURE"
        self.pending[group.group_id]=group
        return "QUEUED"
    def preview(self)->tuple[ReadyGroup,...]:
        return tuple(self.pending[k] for k in sorted(self.pending))
    def mark_completed(self,group_id:str,verified_identity:str)->None:
        if group_id not in self.pending: raise LocalityError("unknown pending group")
        group=self.pending[group_id]
        if verified_identity!=group.identity(): raise LocalityError("identity mismatch")
        self.completed[group_id]=verified_identity
        del self.pending[group_id]
    def snapshot(self)->dict:
        return {"capacity":self.capacity,"pending":[g.__dict__ for g in self.preview()],
                "completed":dict(sorted(self.completed.items()))}
    @classmethod
    def recover(cls,snapshot:dict)->"ShadowQueue":
        queue=cls(snapshot["capacity"])
        for raw in snapshot["pending"]:
            group=ReadyGroup(**{**raw,"evidence_ids":tuple(raw["evidence_ids"])})
            if queue.submit(group)!="QUEUED": raise LocalityError("duplicate pending entry")
        for key,digest in snapshot["completed"].items():
            if key in queue.pending or not isinstance(digest,str) or len(digest)!=64:
                raise LocalityError("invalid completed record")
            queue.completed[key]=digest
        return queue
