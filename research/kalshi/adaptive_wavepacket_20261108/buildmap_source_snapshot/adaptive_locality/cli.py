"""Offline shadow-mode command; no production integration."""
import argparse
import json
from pathlib import Path
from .core import Observation,MetricContract,LocalityConfig,LocalityEngine
from .ledger import DecisionLedger
from .adapters import EvidenceManifest,shadow_batch,buildmap_evidence

def main():
    p=argparse.ArgumentParser()
    p.add_argument("input",help="local JSON containing manifest, metric, config, events")
    p.add_argument("--output",required=True,help="new JSON output path (must not exist)")
    args=p.parse_args()
    src=Path(args.input)
    dst=Path(args.output)
    if src.resolve()==dst.resolve(): p.error("input and output must differ")
    raw=json.loads(src.read_text(encoding="utf-8"))
    metric=MetricContract(**{**raw["metric"],"features":tuple(raw["metric"]["features"]),
                             "scales":tuple(raw["metric"]["scales"]),"weights":tuple(raw["metric"]["weights"])})
    engine=LocalityEngine(metric,LocalityConfig(**raw["config"]))
    manifest=EvidenceManifest(**{**raw["manifest"],"planes":tuple(raw["manifest"]["planes"])})
    events=(Observation(**x) for x in raw["events"])
    ledger=DecisionLedger()
    result=buildmap_evidence(shadow_batch(events,engine,ledger,manifest))
    with dst.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,allow_nan=False)
        f.write("\n")
if __name__=="__main__": main()
