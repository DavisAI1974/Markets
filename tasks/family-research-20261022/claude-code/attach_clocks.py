"""Attach absolute clocks to every per-event row file that carried only session-relative seconds or group ids.

Session seconds count from the trading-day origin DAY0 (21:00 UTC the prior calendar day). For each row the
pass adds, for every field named t0 / onset / confirm / next_t0 / seed_known_s / recognition that holds a
session second, a sibling <name>_epoch_s and <name>_utc; a `session` tag and `day0_epoch_s`; and, for the
size-one tape and order rows (keyed by onset group and side), the episode's onset_ns, onset_utc, end_ns and
cursors joined from size-one-episodes-<tag>.jsonl.gz. Existing fields are never changed or removed; each
file is rewritten in place with the same row order. Idempotent.
"""

import datetime as dt
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY0 = {"oct02": 1696194000, "oct03": 1696280400, "oct17": 1697490000, "oct18": 1697576400}
SESSION_SECOND_FIELDS = ("t0", "onset", "confirm", "next_t0", "seed_known_s", "info_horizon_local_s", "info_horizon_refractory_s", "archived_recognition_s")
FILES = ["a-state-direction-knowable-{t}-events.jsonl.gz", "chain-play-filter-{t}-rows.jsonl.gz", "frozen-a-classifier-{t}-events.jsonl.gz",
         "next-burst-forecast-{t}-events.jsonl.gz", "other-things-{t}-events.jsonl.gz", "runway-clock-v2-{t}-events.jsonl.gz",
         "runway-duration-{t}-events.jsonl.gz", "stack-direction-sources-{t}-events.jsonl.gz", "beyond-direction-prebirth-{t}-events.jsonl.gz",
         "exhaustion-clock-{t}-events.jsonl.gz"]
JOINED = ["size-one-tape-{t}.jsonl.gz", "size-one-orders-{t}.jsonl.gz"]


def utc(epoch_s):
    return dt.datetime.fromtimestamp(epoch_s, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp(row, tag):
    row.setdefault("session", tag)
    row.setdefault("day0_epoch_s", DAY0[tag])
    for f in SESSION_SECOND_FIELDS:
        v = row.get(f)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and f"{f}_epoch_s" not in row:
            e = DAY0[tag] + int(v)
            row[f"{f}_epoch_s"] = e
            row[f"{f}_utc"] = utc(e)
    return row


def rewrite(path, fn):
    rows = [fn(json.loads(l)) for l in gzip.open(path, "rt")]
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    return len(rows)


def main():
    report = {}
    for tag in DAY0:
        for pat in FILES:
            p = HERE / pat.format(t=tag)
            if p.exists():
                report[p.name] = rewrite(p, lambda r, tag=tag: stamp(r, tag))
        ep = HERE / f"size-one-episodes-{tag}.jsonl.gz"
        if ep.exists():
            key = {}
            for l in gzip.open(ep, "rt"):
                e = json.loads(l)
                key[(e["onset_group"], e["side"])] = dict(onset_ns=e["onset_ns"], onset_utc=utc(e["onset_ns"] // 10**9)[:-1] + f".{e['onset_ns'] % 10**9:09d}Z",
                                                         onset_cursor=e["onset_cursor"], end_ns=e["end_ns"], end_cursor=e["end_cursor"], session=tag)
            for pat in JOINED:
                p = HERE / pat.format(t=tag)
                if p.exists():
                    def fn(r, key=key):
                        k = (r.get("onset_group"), r.get("side"))
                        if k in key:
                            for kk, vv in key[k].items():
                                r.setdefault(kk, vv)
                        return r
                    report[p.name] = rewrite(p, fn)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
