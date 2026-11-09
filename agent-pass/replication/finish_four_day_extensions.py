"""Complete retained NG extensions on a hosted runner; no producers or orders."""
import argparse
import gc
import gzip
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = "tasks/family-research-20261022"
EVIDENCE = "2ab66b7ab865e5c433a0140e81d693dd54da4903"
ORIGINAL = "407a23379"
DATA = "968fa11324f66b70cd318140c51bf19e23f9ee4e"
OPERATOR = "b5f28bd57de5ed4ff889335edb9a33216b67eb6a"
OLD_CANDIDATES = ROOT + "/october18-candidate-inputs.jsonl.gz"
NS = 10**9
SOURCES = []
WORK = None

def fetch(repo, ref, path):
    url = f"https://raw.githubusercontent.com/DavisAI1974/{repo}/{ref}/{path}"
    with urllib.request.urlopen(url, timeout=180) as response:
        raw = response.read()
    SOURCES.append(dict(repository=repo, revision=ref, path=path, bytes=len(raw),
                        sha256=hashlib.sha256(raw).hexdigest(), url=url))
    return raw

def read_table(raw, name):
    return pd.read_csv(io.BytesIO(raw), compression="gzip" if name.endswith(".gz") else None)

def retained(name, day):
    prefix = ROOT + ("/research-atlas-v2" if day == "20231018" else f"/replay-comparison/{day}/research-atlas-v2")
    return fetch("Markets", EVIDENCE, prefix + "/" + name)

def birth_rows(candidates):
    # Finalization-only candidates retain their true historical birth, not a fake recognition.
    return [dict(candidate_id=c["candidate_id"],
                 birth_second=c["birth_second"] if "birth_second" in c else
                 c["original_episode"]["birth_recv_ns"] // NS) for c in candidates]

def unit_tests():
    sys.path.insert(0, str(WORK))
    for name in ("flow_book_discovery.py", "research_atlas.py"):
        (WORK/name).write_bytes(fetch("Markets", ORIGINAL, ROOT+"/"+name))
    for name in ("research_atlas_continuous.py", "research_atlas_primer.py", "test_extensions.py", "finish_four_day_extensions.py"):
        (WORK/name).write_bytes((Path(__file__).parent/name).read_bytes())
    subprocess.run([sys.executable, "-m", "pytest", "-q", str(WORK/"test_extensions.py")], check=True)

def check_tables(out, n):
    f = pd.read_csv(out/"observations.csv.gz")
    e = pd.read_csv(out/"onsets.csv.gz")
    links = pd.read_csv(out/"birth-links.csv.gz")
    metrics = pd.read_csv(out/"outcome-summary.csv")
    assert e.quote_known_by_ns.lt(e.decision_ns).all()
    assert e.input_available.all()
    assert not any("birth" in c or "future" in c for c in e.columns)
    assert links.groupby("hypothesis").candidate_id.nunique().eq(n).all()
    assert links.loc[links.signals_in_prior60.gt(0), "last_lead_s"].between(1,60).all()
    assert (metrics.up+metrics.down+metrics.flat == metrics.available).all()
    assert (metrics.available+metrics.unavailable == metrics.n).all()
    assert (metrics.flow_weaker+metrics.flow_stronger+metrics.flow_same == metrics.flow_comparable).all()
    np.testing.assert_allclose(e.loc[e.operator_defined,"ratio"], e.loc[e.operator_defined,"imb_level"])
    # The entire row timeline is exact and contains one row per observed second.
    assert f.second.diff().dropna().eq(1).all()
    assert ((f.second+1)*NS == f.decision_ns).all()
    return dict(observation_seconds=len(f), input_available_seconds=int(f.input_available.sum()),
                unique_onset_seconds=int(e.decision_ns.nunique()), onset_rows=len(e),
                retained_births=n, birth_link_rows=len(links),
                all_availability_and_denominator_checks="passed")

def regression(out, names, prefix, filters=None):
    checked=[]
    for name in names:
        expected=read_table(fetch("Markets", ORIGINAL, prefix+"/"+name),name)
        actual=pd.read_csv(out/name)
        if filters:
            actual,expected=filters(name,actual,expected)
        pd.testing.assert_frame_equal(actual.reset_index(drop=True),expected.reset_index(drop=True),
                                      check_dtype=False, rtol=1e-11,atol=1e-12)
        checked.append(name)
    return checked

def run_day(day, destination):
    import flow_book_discovery as fb
    import research_atlas as atlas
    import research_atlas_continuous as continuous
    import research_atlas_primer as primer
    start_sources=len(SOURCES)
    target=destination/day
    out=target/"research-atlas-v2"
    out.mkdir(parents=True)
    (out/"sources").mkdir()
    flowdir=target/"flow-book-discovery-v1"
    flowdir.mkdir()
    manifests=json.loads(fetch("markets-data", DATA, "MANIFEST.json"))
    entry=next(e for e in manifests["entries"] if e.get("session")==day and e["path"].endswith("/groups.jsonl.gz"))
    raw=fetch("markets-data",DATA,entry["markets_data_path"])
    assert hashlib.sha256(raw).hexdigest()==entry["sha256"]
    assert len(raw)==entry["bytes"]
    groups=[json.loads(line) for line in gzip.decompress(raw).splitlines()]
    del raw
    cand_path=OLD_CANDIDATES if day=="20231018" else ROOT+f"/replay-comparison/{day}/candidate-inputs.jsonl.gz"
    candidates=[json.loads(line) for line in gzip.decompress(fetch("Markets",EVIDENCE,cand_path)).splitlines()]
    births=birth_rows(candidates)
    expected={"20231002":741,"20231003":833,"20231017":741,"20231018":863}[day]
    assert len(births)==expected
    assert len({c["candidate_id"] for c in births})==expected
    midnight=int(datetime.strptime(day,"%Y%m%d").replace(tzinfo=timezone.utc).timestamp())
    atlas.OPEN=(midnight if day in ("20231002","20231017") else midnight-7200)*NS
    atlas.CLOSE=(midnight+21*3600)*NS
    group_path=entry["markets_data_path"]
    def rows(path):
        if path==group_path:
            return groups
        if path==OLD_CANDIDATES:
            return births
        raise ValueError("Unexpected fallback input "+path)
    atlas.OUT=out
    for module in (continuous,primer):
        module.rows=rows
        module.GROUPS=group_path
    continuous.ATLAS=out
    continuous.OUT=out/"continuous-prebirth-v1"
    primer.OUT=out
    primer.HERE=target
    names=["dipole-completed-group-flow.csv.gz","dipole-application-method.json",
           "aggression-to-rest-events.csv","prebirth-cases.csv.gz",
           "prebirth-matched-pairs.csv.gz","prebirth-dipole_birth-control-grid.csv.gz"]
    if day=="20231018":
        names.append("prebirth-family_start-control-grid.csv.gz")
    for name in names:
        (out/name).write_bytes(retained(name,day))
    operator=fetch("Markets",OPERATOR,"odcore/info_dipole.py")
    (out/"sources/info_dipole_pinned.py").write_bytes(operator)
    continuous.main(operator_bytes=operator)
    if day=="20231018":
        family=read_table(fetch("Markets",EVIDENCE,ROOT+"/flow-book-discovery-v1/opportunities.csv.gz"),"opportunities.csv.gz")
        primer.main(family=family)
    else:
        primer.main(family=pd.DataFrame(columns=["instance","anchor_ns","pre_group"]),
                    sensitivity_populations=[("dipole_birth","displayed_lots")])
    checks=check_tables(continuous.OUT,expected)
    if day=="20231018":
        checks["october18_continuous_reproduced"]=regression(continuous.OUT,
            ["observations.csv.gz","active-events.csv.gz","onsets.csv.gz","birth-links.csv.gz",
             "onset-birth-labels.csv.gz","outcomes.csv.gz","summary.csv","outcome-summary.csv"],
            ROOT+"/research-atlas-v2/continuous-prebirth-v1")
        checks["october18_primer_reproduced"]=regression(out,
            ["primer-spread-event-outcomes.csv.gz","primer-spread-event-summary.csv","primer-prebirth-sensitivity.csv"],
            ROOT+"/research-atlas-v2")
    checks.update(day=day,completed_groups=len(groups),
                  finalization_only=sum(c.get("recognition_group") is None for c in candidates),
                  scope="partial" if day in ("20231002","20231017") else "full archived session")
    method_path=continuous.OUT/"method.json"
    method=json.loads(method_path.read_text())
    method.update(session_date=day,source_revision=DATA,source_groups=group_path,evidence_revision=EVIDENCE,
                  birth_alignment="Post-hoc [birth-60s, birth); all recorded births retained, including finalization-only. Birth labels never enter predicates.")
    method["limits"]=[v for v in method["limits"] if "October 2/3/17 final" not in v]
    method["limits"].append("Original partial coverage preserved for October 2 and 17; no added prefix or producer rerun.")
    method_path.write_text(json.dumps(method,indent=2)+"\n")
    method_path=out/"primer-application-method.json"
    method=json.loads(method_path.read_text())
    method.update(session_date=day,scope=checks["scope"],source_groups=group_path,source_revision=DATA,
                  family_population="original October 18 749 starts" if day=="20231018" else
                  "unavailable: no comparable saved family-start index; not replaced by dipoles")
    method_path.write_text(json.dumps(method,indent=2)+"\n")
    (target/"verification.json").write_text(json.dumps(checks,indent=2)+"\n")
    (target/"input-manifest.json").write_text(json.dumps(SOURCES[start_sources:],indent=2)+"\n")
    # Inputs remain pinned by manifest; retain only newly produced outputs here.
    for name in names:
        (out/name).unlink()
    (out/"sources/info_dipole_pinned.py").unlink()
    print(json.dumps(checks),flush=True)
    return checks

def figures_and_report(destination,checks):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    allsummary=[]
    fig,axes=plt.subplots(2,2,figsize=(16,10),layout="constrained")
    for ax,check in zip(axes.flat,checks):
        day=check["day"]
        out=destination/day/"research-atlas-v2"
        s=pd.read_csv(out/"continuous-prebirth-v1/summary.csv")
        s.insert(0,"day",day)
        allsummary.append(s)
        ax.barh(s.hypothesis,s.onsets,color="#326da8")
        ax.set_title(f'{day} — {check["scope"]}\n{check["observation_seconds"]:,} seconds; {check["retained_births"]} births')
        ax.set_xlabel("Observed onsets (each predicate separately)")
        ax.tick_params(axis="y",labelsize=8)
    fig.suptitle("Same continuous precursor definitions, original four date scopes\nOnsets precede any retrospective birth matching; overlapping predicates are not independent")
    fig.savefig(destination/"continuous-onsets-four-days.png",dpi=150)
    plt.close(fig)
    pd.concat(allsummary).to_csv(destination/"four-day-continuous-summary.csv",index=False)
    header="# Remaining October 18 extensions: four-date replication\n\n"
    text=header+"Ran on a GitHub-hosted runner using pinned saved inputs. No producer, desktop computation, or simulator ran.\n\n"
    text+="The continuous precursor scan and primer next-price-change/quote-age/reused-control diagnostics now cover each available date span. October 18 reproduces all eight continuous tables and three primer tables before the other dates run.\n\n"
    text+="| Date | Scope | Groups | Births | Available seconds | Unique onset seconds |\n|---|---|---:|---:|---:|---:|\n"
    for c in checks:
        text+=f'| {c["day"]} | {c["scope"]} | {c["completed_groups"]} | {c["retained_births"]} | {c["input_available_seconds"]} | {c["unique_onset_seconds"]} |\n'
    text+="\n![Continuous onsets](continuous-onsets-four-days.png)\n\n"
    text+="Agreement, differences, and unresolved findings remain separate: the same algorithms and denominators are now available for comparison; equal procedures do not assert equal outcomes. All ten precursor hypotheses remain retained. Individual rows, causal clocks, unlinked onsets, flat/contrary outcomes and censored cases are preserved.\n\n"
    text+="The separate 749-family-start study is NOT complete on the other dates: no equivalent saved family-start index is supplied by the sealed dipole inputs. The primer family subset remains October 18 only. No dipole was relabeled as a family. This receipt completes the missing extensions applicable to the archived Native populations, not the older ROOT/SQLite/Julia family pipeline.\n\n"
    text+="Existing four-date modules remain at Markets commit "+EVIDENCE+": original dipole operator, 11-arm stacks, matched prebirth, same-order aggression-to-rest paths, delayed observations, plus the published native-dipole renders. Timestamp assembly, other researchers' layers, and paper configuration follow this replication task; no paper orders have been submitted.\n"
    (destination/"README.md").write_text(text)
    (destination/"verification.json").write_text(json.dumps(checks,indent=2)+"\n")

def main():
    global WORK
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    destination=args.output.resolve()
    destination.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="ng-extension-") as directory:
        WORK=Path(directory)
        unit_tests()
        results=[]
        for day in ("20231018","20231002","20231003","20231017"):
            results.append(run_day(day,destination))
            gc.collect()
        figures_and_report(destination,results)
    entries=[]
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            raw=path.read_bytes()
            entries.append(dict(path=str(path.relative_to(destination)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    manifest=dict(schema="ng.four_day_extensions.v1",code_commit=os.environ.get("CODE_REV"),
                  workflow_run=os.environ.get("GITHUB_RUN_ID"),files=entries,source_reads=SOURCES)
    (destination/"MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(f"COMPLETE {len(entries)} verified output files",flush=True)

if __name__=="__main__":
    main()
