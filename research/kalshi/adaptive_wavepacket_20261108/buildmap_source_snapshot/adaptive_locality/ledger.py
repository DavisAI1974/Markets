"""Scientific equivalence gate and append-only decision ledger."""
from __future__ import annotations
from dataclasses import dataclass
from .core import Decision, LocalityError, _digest

@dataclass(frozen=True)
class JobReceipt:
    job_id:str
    source_identity:str
    input_identity:str
    metric_identity:str
    family:str
    direction:str
    output_identity:str
    side_effect_free:bool
    complete:bool
    def __post_init__(self):
        if not all((self.job_id,self.source_identity,self.input_identity,self.metric_identity,
                    self.family,self.direction,self.output_identity)):
            raise LocalityError("complete receipt identity fields required")

class ScientificGate:
    """Fail closed. Identical hashes do not prove arbitrary side effects absent."""
    @staticmethod
    def equivalent(a:JobReceipt,b:JobReceipt)->tuple[bool,str]:
        if not a.complete or not b.complete: return False,"incomplete"
        if not a.side_effect_free or not b.side_effect_free: return False,"side effects not excluded"
        keys=("source_identity","input_identity","metric_identity","family","direction","output_identity")
        if any(getattr(a,k)!=getattr(b,k) for k in keys): return False,"scientific identities differ"
        return True,"same declared exact identity and outputs; review still required"

class DecisionLedger:
    def __init__(self):
        self._entries:list[dict]=[]
        self._head="GENESIS"
    def append(self,decision:Decision,action:str,reviewer:str,reason:str)->dict:
        if action not in ("PROPOSE","REJECT","ABSTAIN","APPROVE_ASSIGNMENT","ROLLBACK"):
            raise LocalityError("unsupported ledger action")
        if action=="APPROVE_ASSIGNMENT" and decision.status not in ("PROPOSE_ONLY","NEW_CENTER"):
            raise LocalityError("cannot approve ineligible decision")
        if not reviewer or not reason: raise LocalityError("reviewer and reason required")
        entry={"sequence":len(self._entries),"previous":self._head,"action":action,
               "reviewer":reviewer,"reason":reason,"decision":decision.__dict__}
        entry["hash"]=_digest(entry)
        self._entries.append(entry)
        self._head=entry["hash"]
        return dict(entry)
    def verify(self)->bool:
        previous="GENESIS"
        for i,entry in enumerate(self._entries):
            payload={k:v for k,v in entry.items() if k!="hash"}
            if entry["sequence"]!=i or entry["previous"]!=previous or _digest(payload)!=entry["hash"]:
                return False
            previous=entry["hash"]
        return True
    def export(self)->dict:
        return {"head":self._head,"entries":[dict(x) for x in self._entries]}
