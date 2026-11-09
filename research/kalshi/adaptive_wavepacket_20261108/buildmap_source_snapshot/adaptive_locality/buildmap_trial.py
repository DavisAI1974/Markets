"""Optional BuildMap *inspection* trial, not a runtime or scientific dependency.

Only emits a conservative, draft manifest for an explicitly disposable
scratch checkout. The core Adaptive Locality modules never import BuildMap.
There are no evidence receipts or verified/live claims. BuildMap's native
static scanner may be run against a scratch source copy to reveal unmapped
dependencies and planned scientific review gaps; it cannot certify math,
replace outlier investigation, or suppress any calculations.
"""
from __future__ import annotations

import json
from .core import _digest
from .research_gates import UNVERIFIED_GATES

_COMPONENTS = (
    ("raw-observables", "Source-bound observables",
     ("adaptive_locality/information.py",), (),
     "Full RawFrame lineage, fixed bins, H/MI and explicitly Fisher-like proxy."),
    ("directional-coupling", "Five-step directional association",
     ("adaptive_locality/coupling.py",), ("raw-observables",),
     "Held-out direction tests, self baseline and historical donor null; not causality."),
    ("static-geometry", "Static algebraic geometry diagnostics",
     ("adaptive_locality/geometry_probe.py",), ("raw-observables","directional-coupling"),
     "Separate exact algebraic identities, rank, frozen support and residual."),
    ("predictive-controls", "Chronological geometry controls",
     ("adaptive_locality/geometry_validation.py",), ("raw-observables","directional-coupling"),
     "Future target rate, independent self baseline, past-only donor null and regime splits."),
    ("level2-links", "Unsmoothed pair-balance interactions",
     ("adaptive_locality/level2_coupling.py",), ("directional-coupling",),
     "Every directional window and link remains separate with research holds."),
    ("raw-research-holds", "Durable original-evidence research registry",
     ("adaptive_locality/research_holds.py",),
     ("raw-observables","static-geometry","predictive-controls","level2-links"),
     "Immutable source-bound RawFrame+InfoFrame archives and reversible review cases."),
)


def inspection_manifest() -> dict:
    """Declare inspection tasks with no evidence claims or runtime connections."""
    components=[{"id":component_id,"name":name,
                 "group":"Standalone mathematical review",
                 "files":list(files),"dependsOn":list(dependencies),
                 "purpose":purpose,"contributes":"Make outstanding scientific acceptance gaps explicit.",
                 "visual":{"kind":"proof","label":"Research review"}}
                for component_id,name,files,dependencies,purpose in _COMPONENTS]
    for gate in UNVERIFIED_GATES:
        components.append({
            "id":"unverified-"+gate.gate_id,
            "name":"Unverified: "+gate.gate_id.replace("-"," "),
            "group":"Retained for further scientific inspection",
            "files":["adaptive_locality/unverified_review/"+gate.gate_id+".py"],
            "dependsOn":["raw-research-holds"],
            "purpose":gate.reason+" Required evidence: "+gate.required_evidence,
            "contributes":"Unresolved science gate remains visible and incomplete.",
            "visual":{"kind":"proof","label":"Research hold"},
        })
    return {
        "name":"Adaptive Locality — isolated review trial",
        "mode":"brownfield",
        "mission":("Inspect isolated mathematical source and outstanding evidence gaps "
                   "without changing calculations or promoting unsupported claims."),
        "components":components,
        "finishedProduct":{
            "experience":"Offline, read-only inspector of sources and missing scientific checks.",
            "behavior":"Review only; not a mathematical result or production acceptance."},
    }


def inspection_comparison_contract() -> dict:
    """Predeclared test criterion; no self-reported performance improvement."""
    manifest=inspection_manifest()
    return {"kind":"ADAPTIVE_LOCALITY_OPTIONAL_BUILDMAP_TRIAL",
            "schema":1,"mode":"STATIC_SOURCE_INSPECTION_ONLY",
            "manifest_identity":_digest(manifest),
            "component_count":len(manifest["components"]),
            "known_scientific_gates":tuple("unverified-"+g.gate_id
                                            for g in UNVERIFIED_GATES),
            "keep_only_if":(
                "native BuildMap scanner finds actual source connections",
                "missing independent-science gates remain visibly incomplete",
                "no component is falsely verified or made live",
                "scientific calculations and source evidence remain unchanged",
            ),
            "scientific_jobs_eliminated":0,
            "scientific_predictive_improvement_claimed":False,
            "limits":"This comparison measures source-inspection coverage, not prediction, causation or speed."}


if __name__=="__main__":
    print(json.dumps({"manifest":inspection_manifest(),
                      "comparison_contract":inspection_comparison_contract()},
                     sort_keys=True,separators=(",",":")))
