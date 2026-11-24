"""Stage 4b, the part with no model: saved calculation outputs, renders, manifests, dipole events
and peaks become graph nodes. Every value is read from a saved record; no calculation is made on
any tick, nothing is averaged, ranked, labelled or dropped.

  python3 -m tools.kgraph.ingest_det --data <markets-data checkout> [--graph-dir <scratch>]
        [--only tradedays,manifests,rootrows,dipoles,peaks,renders]

Each part is one function that returns the store.write() result (parts that leave something out also
return what they left out, by name).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

from .sources import REPOS, code_stamp, commit_node, last_commit, link, source_id, source_node
from .store import GraphStore

WRITER = "tools.kgraph.ingest_det"
REPO = REPOS["markets-data"]
WORK = "tasks/family-research-20261022/research-union-current"
DAYS = ("2023-10-02", "2023-10-03", "2023-10-17", "2023-10-18")
NY = ZoneInfo("America/New_York")
RULE = "a trade day is 6 pm Eastern the evening before to 5 pm Eastern on the named date"

# (manifest path, key of its list of files or None when the file is itself the list)
MANIFESTS = (
    ("MANIFEST.json", "entries"),
    ("data/nymex_mbo/ng_v0_oct2023/MANIFEST.json", "files"),
    ("data/outside/ng_oct2023/MANIFEST.json", "files"),
    (f"{WORK}/desktop-old-family-chain-on-clock-20261117/MANIFEST.json", "files"),
    (f"{WORK}/desktop-peak-lives-on-clock-20261117/MANIFEST.json", "files"),
    (f"{WORK}/field-rebuild-20261113/STATIC_CONTENT_MANIFEST.json", None),
)
WORKBOOK = f"{WORK}/root-redesign-20261116/ROOT_dipoles_pinned.xlsx"


def _stamp() -> str:
    return code_stamp(WRITER)


def tradeday_id(d: str) -> str:
    return f"tradeday:{d}"


def _tradeday_nodes() -> list[dict]:
    out = []
    for d in DAYS:
        day = dt.date.fromisoformat(d)
        start = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(18, 0), tzinfo=NY)
        end = dt.datetime.combine(day, dt.time(17, 0), tzinfo=NY)
        ns = lambda x: int(x.astimezone(dt.timezone.utc).timestamp()) * 10**9
        out.append({"id": tradeday_id(d), "type": "TradeDay", "attrs": {
            "date": d, "weekday": day.strftime("%A"),
            "starts_et": f"{start:%Y-%m-%d %H:%M:%S} America/New_York",
            "ends_et": f"{end:%Y-%m-%d %H:%M:%S} America/New_York",
            "start_ns": ns(start), "end_ns": ns(end), "rule": RULE}})
    return out


def tradedays(store: GraphStore) -> dict:
    return store.write(_tradeday_nodes(), [], written_by=_stamp())


# ---- manifests ---------------------------------------------------------------------------------
PATH_FIELDS = ("path", "markets_data_path", "file", "stored")   # each manifest names its file in its own field


def _listed_path(root: Path, manifest_rel: str, e: dict) -> tuple[str | None, bool]:
    """The checkout path an entry names and whether a file is there. A manifest gives a path either
    from the top of the checkout or from its own folder; the one that is a real file is taken."""
    base = Path(manifest_rel).parent
    named = [e[f] for f in PATH_FIELDS if isinstance(e.get(f), str)]
    for n in named:
        for cand in (Path(n), base / n):
            if (root / cand).is_file():
                return str(cand), True
    return (named[0] if named else None), False


def manifests(store: GraphStore) -> dict:
    """One Source for each manifest and one for each FILE it lists; one MEMBER_OF link for each ENTRY.

    A file listed by two manifests is one node with two links. What a manifest says of the file (the
    whole entry, as stored) is on the link, so two manifests never overwrite each other. Where the
    file is in the checkout its node is the file's own Source (bytes and sha256 read from the file),
    and the link says whether the manifest's sha256 is the file's. A UTC clock day stays `utc_day`.
    """
    root = store.data_root
    nodes, edges, not_listed, per, files = {}, [], [], {}, {}
    for mrel, key in MANIFESTS:
        msrc = source_node("markets-data", root, mrel, kind="manifest")
        nodes[msrc["id"]] = msrc
        j = json.loads((root / mrel).read_text(encoding="utf-8"))
        entries = j if key is None else j.get(key)
        if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
            not_listed.append(mrel)
            continue
        per[mrel] = len(entries)
        for i, e in enumerate(entries):
            p, there = _listed_path(root, mrel, e)
            if p is None:
                p = f"{mrel}#entry{i}"
            nid = source_id("markets-data", p)
            on_link = {"manifest_index": i, "entry": e}
            if there:
                if nid not in nodes:
                    nodes[nid] = source_node("markets-data", root, p)
                listed = e.get("sha256") or e.get("stored_sha256")
                if listed:
                    on_link["manifest_sha256_is_the_files"] = listed == nodes[nid]["attrs"]["sha256"]
            elif nid not in nodes:
                attrs = {"kind": "listed_file_not_in_checkout", "repo": REPO, "path": p}
                for k in ("bytes", "sha256", "utc_day"):
                    if k in e:
                        attrs[k] = e[k]
                nodes[nid] = {"id": nid, "type": "Source", "attrs": attrs}
            if "utc_day" in e:
                nodes[nid]["attrs"].setdefault("utc_day", e["utc_day"])
            files.setdefault(nid, []).append(mrel)
            edges.append(link("MEMBER_OF", nid, msrc["id"], key=str(i), **on_link))
    res = store.write(list(nodes.values()), edges, written_by=_stamp())
    res.update(entries_per_manifest=per, not_listed=not_listed,
               files_listed_more_than_once={k: v for k, v in files.items() if len(v) > 1})
    return res


# ---- ROOT rows branches ------------------------------------------------------------------------
def _gitb(root, *args: str) -> bytes:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.decode().strip()}")
    return r.stdout


def branch_ref(d: str) -> str:
    return f"origin/root-rows-{d.replace('-', '')}"


def rootrows(store: GraphStore) -> dict:
    root = store.data_root
    nodes, edges, left_out = _tradeday_nodes(), [], []
    for d in DAYS:
        ds, ref = d.replace("-", ""), branch_ref(d)
        branch = f"root-rows-{ds}"
        cnode = commit_node("markets-data", root, ref)
        nodes.append(cnode)
        names = _gitb(root, "ls-tree", "-r", "--name-only", ref).decode().splitlines()
        wanted = ["RECEIPT.json"] + sorted(n for n in names if re.fullmatch(r"CALC-.+\.json", n))
        left_out += [f"{branch}:{n}" for n in names if n.startswith("CALC") and n not in wanted]
        srcs, calcs = {}, {}
        for n in wanted:
            raw = _gitb(root, "show", f"{ref}:{n}")
            sid = source_id("markets-data", n, branch)
            nodes.append({"id": sid, "type": "Source", "attrs": {
                "kind": "file", "repo": REPO, "path": n, "commit": cnode["attrs"]["sha"], "branch": branch,
                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}})
            srcs[n] = (sid, raw)
        for n in wanted[1:]:
            m = re.fullmatch(rf"CALC-(.+?)(-COUNT)?-{ds}\.json", n)
            if not m:
                left_out.append(f"{branch}:{n} (name does not fit CALC-<calc>-<day>.json)")
                continue
            calcs.setdefault(m.group(1), {})["count" if m.group(2) else "main"] = n
        for calc, parts in sorted(calcs.items()):
            if "main" not in parts:
                left_out.append(f"{branch}: {parts['count']} has no CALC-{calc}-{ds}.json to attach to")
                continue
            j = json.loads(srcs[parts["main"]][1])
            cid = f"calc:{calc}:{d}"
            cols = [c["column"] if isinstance(c, dict) else c for c in j.get("columns", [])]
            receipt = {k: v for k, v in j.items() if k != "columns"}
            nodes.append({"id": cid, "type": "CalcOutput", "attrs": {
                "calc": calc, "path": parts["main"], "branch": branch, "commit": cnode["attrs"]["sha"],
                "trade_day": d, "what": j.get("what"), "laid_out_and_approved": j.get("laid_out_and_approved"),
                "columns": cols,
                "parquet_parts": sorted(x for x in names if x.startswith(f"calc-{calc}-{ds}")),
                "receipt": receipt}})
            for n in parts.values():
                edges.append(link("DERIVED_FROM", cid, srcs[n][0]))
            edges.append(link("PINNED_AT", cid, tradeday_id(d)))
            edges.append(link("PRODUCED", cnode["id"], cid))
    res = store.write(nodes, edges, written_by=_stamp())
    res["not_made"] = left_out
    return res


# ---- the dipole workbook -----------------------------------------------------------------------
LEFT_OUT_SHEETS = "crypto and ng <trade day> (all four): the program's own trades, for observation only"


def _sheets(root, prefix: str):
    import openpyxl
    wb = openpyxl.load_workbook(root / WORKBOOK, read_only=True)
    for ws in wb.worksheets:
        m = re.fullmatch(rf"{prefix} (\d{{4}}-\d{{2}}-\d{{2}})", ws.title)
        if m:
            yield ws, m.group(1)


def _sheet_rows(ws):
    it = ws.iter_rows(values_only=True)
    header = next(it)
    for r, vals in enumerate(it, 2):
        yield r, dict(zip(header, vals))


def _from_workbook(store: GraphStore, prefix: str, make) -> dict:
    """One node for each row of each `<prefix> <trade day>` sheet, with every cell kept as stored
    under `pinned`. Where it came from is on the line itself (source, sheet, row); the one link is
    PINNED_AT its trade day. Two rows that would share an id are both kept."""
    root, total, dup = store.data_root, {"new": 0, "revised": 0, "unchanged": 0}, []
    wsrc = source_node("markets-data", root, WORKBOOK, kind="workbook")
    for ws, d in _sheets(root, prefix):
        nodes, edges, seen = [wsrc, *_tradeday_nodes()], [], set()
        for r, row in _sheet_rows(ws):
            nid, ntype, attrs = make(d, row)
            if nid in seen:
                nid = f"{nid}#row{r}"
                dup.append(nid)
            seen.add(nid)
            nodes.append({"id": nid, "type": ntype, "attrs": {
                **attrs, "trade_day": d, "source": wsrc["id"], "sheet": ws.title, "row": r, "pinned": row}})
            edges.append(link("PINNED_AT", nid, tradeday_id(d)))
        res = store.write(nodes, edges, written_by=_stamp())
        for k in ("new", "revised", "unchanged"):
            total[k] += res[k]
    total["duplicate_ids_renumbered"] = dup
    total["left_out_sheets"] = [LEFT_OUT_SHEETS]
    return total


def dipoles(store: GraphStore) -> dict:
    return _from_workbook(store, "dipoles", lambda d, row: (
        f"dipole:{row['dipole']}", "DipoleEvent",
        {"dipole": row["dipole"], "birth_ns": int(row["native_birth_ns"])}))


def peaks(store: GraphStore) -> dict:
    return _from_workbook(store, "peaks", lambda d, row: (
        f"peak:{d}:{int(row['peak_high_position'])}", "Peak",
        {"position_on_tape": int(row["peak_high_position"]), "high_eastern": str(row["high_eastern"])}))


# ---- renders -----------------------------------------------------------------------------------
def renders(store: GraphStore) -> dict:
    root = store.data_root
    paths = _gitb(root, "ls-files").decode().splitlines()
    nodes = []
    for p in paths:
        if not p.endswith((".png", ".html")):
            continue
        raw = (root / p).read_bytes()
        nodes.append({"id": f"render:{p}", "type": "Render", "attrs": {
            "path": p, "repo": REPO, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "commit": last_commit(root, p)}})
    return store.write(nodes, [], written_by=_stamp())


PARTS = {"tradedays": tradedays, "manifests": manifests, "rootrows": rootrows,
         "dipoles": dipoles, "peaks": peaks, "renders": renders}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None)
    ap.add_argument("--graph-dir", default=None)
    ap.add_argument("--only", default=",".join(PARTS))
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    for name in a.only.split(","):
        print(name, json.dumps(PARTS[name](store), ensure_ascii=False))
    print("counts", json.dumps(GraphStore(a.data, graph_dir=a.graph_dir).counts()))


if __name__ == "__main__":
    main()
