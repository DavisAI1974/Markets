"""Explicit, non-invasive interfaces. No AWS or Frankie side effects."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .core import Observation, LocalityEngine, LocalityError, _digest
from .ledger import DecisionLedger

@dataclass(frozen=True)
class EvidenceManifest:
    run_id:str
    day:str
    source_identity:str
    planes:tuple[str,...]
    def validate(self):
        if not self.run_id or not self.day or not self.source_identity:
            raise LocalityError("source-bound manifest required")
        if len(set(self.planes))!=len(self.planes) or not self.planes:
            raise LocalityError("unique named evidence planes required")

def shadow_batch(events:Iterable[Observation],engine:LocalityEngine,
                 ledger:DecisionLedger,manifest:EvidenceManifest)->dict:
    """Produce proposals only. Never remove or schedule scientific calculations."""
    manifest.validate()
    decisions=[]
    for obs in events:
        d=engine.propose(obs)
        ledger.append(d,"PROPOSE","shadow-adapter","non-destructive locality proposal")
        if d.status in ("NEW_CENTER","PROPOSE_ONLY"):
            engine.admit(obs,d)
        decisions.append({"event_id":obs.event_id,"status":d.status,
                          "center":d.proposed_center,"candidate_weights":d.candidates,
                          "event_identity":d.evidence_identity})
    return {"version":1,"mode":"SHADOW_ONLY","run":manifest.run_id,"day":manifest.day,
            "source_identity":manifest.source_identity,"planes":list(manifest.planes),
            "metric_identity":engine.metric.identity(),"decisions":decisions,
            "ledger_head":ledger.export()["head"],
            "scientific_jobs_eliminated":0,"workload_counts":"UNKNOWN",
            "identity":_digest(decisions)}

def buildmap_evidence(shadow_result:dict)->dict:
    """Read-only bounded artifact for BuildMap import; not a signed collector receipt."""
    if shadow_result.get("mode")!="SHADOW_ONLY":
        raise LocalityError("only shadow artifacts may be exported")
    return {"kind":"adaptive-locality-shadow","schema_version":1,
            "provenance":{"run":shadow_result["run"],"day":shadow_result["day"],
                          "source_identity":shadow_result["source_identity"],
                          "metric_identity":shadow_result["metric_identity"]},
            "decisions":shadow_result["decisions"],"ledger_head":shadow_result["ledger_head"],
            "scientific_jobs_eliminated":0,
            "trust":"UNSIGNED_RESEARCH_ARTIFACT_NOT_ACCEPTANCE_EVIDENCE"}
