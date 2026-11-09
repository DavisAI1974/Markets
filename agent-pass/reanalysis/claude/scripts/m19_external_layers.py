"""M19: the 13 external points and 48 series (lifecycle packet external/): what value each had at each session's first and last known clock,
and the 99-layer registry: how many layers have a measured field link at all. These are context layers (daily/weekly cadence); constant within a
session, so they cannot move intraday outcomes on these four days; across four sessions they are four observations."""
import json, gzip, numpy as np, pandas as pd
from common import *
EXT = LIFECYCLE / "external"
with gzip.open(EXT / "original-external-series.json.gz", "rt") as fh: ser = json.load(fh)
contract = json.load(open(EXT / "external-context-contract.json")); bind = json.load(open(EXT / "all-13-input-bindings.json"))
series = ser["series"] if isinstance(ser, dict) and "series" in ser else ser
print(type(series).__name__, len(series)); s0 = series[0] if isinstance(series, list) else list(series.values())[0]; print("series record keys:", list(s0.keys())[:12])
def known_at(s, t_ns):
    pub = np.array(s.get("publication_ns") or s.get("known_ns") or [], dtype="int64"); vals = s.get("known") or s.get("values") or []
    i = np.searchsorted(pub, t_ns, side="right") - 1
    return (vals[i] if i >= 0 and i < len(vals) else None, int(pub[i]) if i >= 0 else None)
rows = []
sess = {"20231002": ("2023-10-01T21:00:00Z", "2023-10-02T21:00:00Z"), "20231003": ("2023-10-02T21:00:00Z", "2023-10-03T21:00:00Z"), "20231017": ("2023-10-16T21:00:00Z", "2023-10-17T21:00:00Z"), "20231018": ("2023-10-17T21:00:00Z", "2023-10-18T21:00:00Z")}
for s in (series if isinstance(series, list) else series.values()):
    name = s.get("series") or s.get("name")
    for day, (a, b) in sess.items():
        ta = int(pd.Timestamp(a).value); tb = int(pd.Timestamp(b).value)
        va, pa = known_at(s, ta); vb, pb = known_at(s, tb)
        rows.append(dict(series=name, day=day, value_at_session_start=json.dumps(va)[:80], published_ns_start=pa, value_at_session_end=json.dumps(vb)[:80], published_ns_end=pb, changed_within_session=(va != vb)))
df = pd.DataFrame(rows); df.to_csv(OUT / "m19_external_values_by_session.csv", index=False)
print("series:", df.series.nunique(), "| changed within a session (series,day) pairs:", int(df.changed_within_session.sum()), "of", len(df))
print(df[df.changed_within_session][["series", "day"]].drop_duplicates().to_string()[:2000])
pts = pd.DataFrame([dict(point_id=p["point_id"], name=p["name"], use=p["use"], series=[x["series"] for x in p["series"]], tables=[t["table"] for t in p["tables"]]) for p in bind["points"]]); pts.to_csv(OUT / "m19_13_points.csv", index=False); print(pts[["point_id", "name", "use"]].to_string())
reg = json.load(open(LIFECYCLE / "99-layer-attachments.json"))
disp = pd.Series([r["disposition"] for r in reg]).value_counts().to_dict(); linked = [(r["layer_id"], len(r["linked_fields"])) for r in reg if r["linked_fields"]]
print("99-layer dispositions:", disp); print("layers with linked fields:", len(linked), linked[:40])
json.dump(dict(dispositions=disp, layers_with_fields=linked, changed_within_session=int(df.changed_within_session.sum()), series=int(df.series.nunique())), open(OUT / "m19_external_summary.json", "w"), indent=1)
