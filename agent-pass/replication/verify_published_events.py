"""Read back immutable completed studies, verify clocks, and add explicit joins."""
import argparse,json,os,pathlib,tempfile
from event_common import Context,BASE
from finish_family_replication import get,jsonwrite,seal,READS
import verify_combined_events,event_integration

def main():
    p=argparse.ArgumentParser();p.add_argument("--day",required=True);p.add_argument("--output",required=True,type=pathlib.Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    path=BASE+f"/combined-events/run-{os.environ['ANALYSIS_RUN']}-1/events-{a.day}"
    manifest=json.loads(get("markets-data",os.environ["ANALYSIS_REV"],path+"/MANIFEST.json"))
    for e in manifest["files"]:
        target=a.output/e["path"];target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(get("markets-data",os.environ["ANALYSIS_REV"],path+"/"+e["path"],e["sha256"]))
    with tempfile.TemporaryDirectory() as tmp:
        ctx=Context(a.day,a.output,pathlib.Path(tmp))
        verify_combined_events.run(ctx)
        summary=json.loads((a.output/"analysis-summary.json").read_text())
        summary["joint_analysis"]=event_integration.run(ctx)
        jsonwrite(a.output/"analysis-summary.json",summary)
        jsonwrite(a.output/"verification-input-manifest.json",READS)
        seal(a.output)
        print(json.dumps(summary),flush=True)
if __name__=="__main__":main()
