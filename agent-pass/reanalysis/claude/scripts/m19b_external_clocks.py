"""M19b: do intraday events cluster around external publication clocks? For each session, the distinct publication times of the 48 series inside
the session (weather model runs, hourly EIA930 and temperatures, settle and traded curve) are compared with the rate of Native births, large moves,
thin-touch episodes and prints in the 5 minutes after vs the 5 minutes before each publication, and vs the session-wide per-5-minute rate."""
import pandas as pd, numpy as np, json, pyarrow.parquet as pq
from common import *
ext = pd.read_csv(OUT / "m19_external_values_by_session.csv")
import gzip
with gzip.open(LIFECYCLE / "external/original-external-series.json.gz", "rt") as fh: ser = json.load(fh)
series = ser["series"] if isinstance(ser, dict) and "series" in ser else ser
sess = {"20231002": ("2023-10-01T21:00:00Z", "2023-10-02T21:00:00Z"), "20231003": ("2023-10-02T21:00:00Z", "2023-10-03T21:00:00Z"), "20231017": ("2023-10-16T21:00:00Z", "2023-10-17T21:00:00Z"), "20231018": ("2023-10-17T21:00:00Z", "2023-10-18T21:00:00Z")}
out = {}
for day, (a, b) in sess.items():
    ta, tb = int(pd.Timestamp(a).value), int(pd.Timestamp(b).value)
    pubs = {}
    for s in series:
        for k in s["known"]:
            p = k.get("published_ns")
            if p is not None and ta < p <= tb: pubs.setdefault(p, set()).add(s["table"])
    dc = pq.read_table(EVENTS / f"events-{day}/a-dipole-clocks.parquet", columns=["birth_label_ns"]).to_pandas().birth_label_ns.values
    lm = pd.read_csv(OUT / f"m2_large_moves_{day}.csv").move_known_by_ns.values
    tr = pq.read_table(EVENTS / f"events-{day}/a-trades.parquet", columns=["receive_ns"]).to_pandas().receive_ns.values
    ep = pq.read_table(EVENTS / f"events-{day}/b-quote-episodes.parquet", columns=["onset_clocks"]).to_pandas().onset_clocks.apply(lambda c: c["known_by_ns"]).values
    W = 300 * 10**9; span_5min = (tb - ta) / W
    def rate(arr): return len(arr) / span_5min
    rows = []
    for p, tabs in sorted(pubs.items()):
        r = dict(published_utc=pd.Timestamp(p, unit="ns").strftime("%H:%M:%S"), tables="|".join(sorted(tabs)))
        for name, arr in [("births", dc), ("large_moves", lm), ("thin_episodes", ep), ("prints", tr)]:
            r[f"{name}_before5"] = int(((arr >= p - W) & (arr < p)).sum()); r[f"{name}_after5"] = int(((arr > p) & (arr <= p + W)).sum()); r[f"{name}_session_rate5"] = round(rate(arr), 2)
        rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(OUT / f"m19b_external_clocks_{day}.csv", index=False)
    agg = {}
    for name in ["births", "large_moves", "thin_episodes", "prints"]:
        agg[name] = dict(before5_total=int(df[f"{name}_before5"].sum()) if len(df) else 0, after5_total=int(df[f"{name}_after5"].sum()) if len(df) else 0, expected_per_window=round(rate(eval({"births": "dc", "large_moves": "lm", "thin_episodes": "ep", "prints": "tr"}[name])), 2), n_publications=len(df))
    out[day] = dict(publications_in_session=len(pubs), tables=sorted({t for v in pubs.values() for t in v}), aggregate=agg,
                    by_table={t: dict(n=int((df.tables.str.contains(t)).sum()), births_after5=int(df[df.tables.str.contains(t)].births_after5.sum()), births_before5=int(df[df.tables.str.contains(t)].births_before5.sum()), moves_after5=int(df[df.tables.str.contains(t)].large_moves_after5.sum()), moves_before5=int(df[df.tables.str.contains(t)].large_moves_before5.sum()), prints_after5=int(df[df.tables.str.contains(t)].prints_after5.sum()), prints_before5=int(df[df.tables.str.contains(t)].prints_before5.sum())) for t in sorted({t for v in pubs.values() for t in v})} if len(df) else {})
    print(day, "publications:", len(pubs), out[day]["tables"]); print("   aggregate:", agg); print("   by table:", out[day]["by_table"])
json.dump(out, open(OUT / "m19b_external_clocks.json", "w"), indent=1)
