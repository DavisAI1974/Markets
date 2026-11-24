"""Stage 4b (no model): saved outputs, manifests, dipoles, peaks and renders in the graph, checked
against the real records they were read from. Writes go to a scratch graph, never to markets-data."""

import json
import re
import subprocess
from pathlib import Path

import openpyxl
import pytest

from tools.kgraph import ingest_det as det
from tools.kgraph.store import GraphStore

from .realrecords import data_root


@pytest.fixture()
def store(tmp_path):
    return GraphStore(data_root(), graph_dir=tmp_path / "graph")


def _git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout


def _need_refs(root):
    for d in det.DAYS:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "-q", det.branch_ref(d)], capture_output=True)
        if r.returncode:
            pytest.skip(f"{det.branch_ref(d)} is not fetched in this checkout")


def _again(fn, store):
    r = fn(store)
    assert r["new"] == 0 and r["revised"] == 0
    assert store.check_all() == []


def test_tradedays(store):
    det.tradedays(store)
    t = {n["attrs"]["date"]: n["attrs"] for n in store.nodes("TradeDay")}
    assert sorted(t) == list(det.DAYS)
    a = t["2023-10-02"]
    assert a["starts_et"] == "2023-10-01 18:00:00 America/New_York"
    assert a["ends_et"] == "2023-10-02 17:00:00 America/New_York"
    assert a["weekday"] == "Monday"
    assert a["start_ns"] == 1696197600 * 10**9 and a["end_ns"] - a["start_ns"] == 23 * 3600 * 10**9  # EDT, UTC-4
    _again(det.tradedays, store)


def test_manifests_one_link_per_entry_and_one_node_per_file(store):
    root = store.data_root
    res = det.manifests(store)
    expected, files, there = 0, set(), set()
    for rel, key in det.MANIFESTS:
        j = json.loads((root / rel).read_text(encoding="utf-8"))
        entries = j if key is None else j[key]
        assert res["entries_per_manifest"][rel] == len(entries)
        expected += len(entries)
        for e in entries:                       # counted here by another route than the code's
            names = [e[f] for f in ("path", "markets_data_path", "file", "stored") if isinstance(e.get(f), str)]
            real = [str(c) for n in names for c in (Path(n), Path(rel).parent / n) if (root / c).is_file()]
            files.add(real[0] if real else names[0])
            if real:
                there.add(real[0])
    members = store.edges("MEMBER_OF")
    assert len(members) == expected and not res["not_listed"]              # no entry dropped
    listed = {e["src"] for e in members}
    assert listed == {f"src:markets-data:{f}" for f in files}              # one node for one file
    kinds = {n["id"]: n["attrs"]["kind"] for n in store.nodes("Source")}
    assert {i for i in listed if kinds[i] != "listed_file_not_in_checkout"} == {f"src:markets-data:{f}" for f in there}
    # a file two manifests list is one node with a link from each
    twice = res["files_listed_more_than_once"]
    assert twice and all(len([e for e in members if e["src"] == nid]) == len(ms) for nid, ms in twice.items())
    # one real entry comes back whole on its link, and a UTC clock day stays a UTC clock day
    first = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))["entries"][0]
    edge = next(e for e in members if e["dst"] == "src:markets-data:MANIFEST.json" and e["attrs"]["manifest_index"] == 0)
    assert edge["attrs"]["entry"] == first
    node = store.node(edge["src"])["attrs"]
    assert node["utc_day"] == first["utc_day"] and "trade_day" not in node
    # where the manifest gives the file's sha256, the link says whether it is the file's (it is, for the tape)
    assert edge["attrs"]["manifest_sha256_is_the_files"] is True and node["sha256"] == first["sha256"]
    _again(det.manifests, store)


def test_rootrows_one_calc_output_per_calc_file(store):
    root = store.data_root
    _need_refs(root)
    res = det.rootrows(store)
    n_calc = n_json = 0
    for d in det.DAYS:
        ds, ref = d.replace("-", ""), det.branch_ref(d)
        names = _git(root, "ls-tree", "-r", "--name-only", ref).splitlines()
        main = [x for x in names if re.fullmatch(rf"CALC-.+-{ds}\.json", x) and "-COUNT-" not in x]
        alljson = [x for x in names if re.fullmatch(r"CALC-.+\.json", x)]
        n_calc += len(main)
        n_json += len(alljson)
        assert len([c for c in store.nodes("CalcOutput") if c["attrs"]["trade_day"] == d]) == len(main)
    assert len(store.nodes("CalcOutput")) == n_calc
    assert len(store.edges("PRODUCED")) == n_calc and len(store.nodes("Commit")) == 4
    # every CALC json (counts files too) and each RECEIPT.json is a Source on its branch
    on_branch = [s for s in store.nodes("Source") if s["attrs"].get("branch")]
    assert len(on_branch) == n_json + 4 and all(s["id"].startswith("src:markets-data@root-rows-") for s in on_branch)
    assert len(store.edges("DERIVED_FROM")) == n_json
    # spot check: the stored receipt comes back unchanged except for the column descriptions
    raw = json.loads(_git(root, "show", f"{det.branch_ref('2023-10-02')}:CALC-sweeps-20231002.json"))
    a = store.node("calc:sweeps:2023-10-02")["attrs"]
    assert a["receipt"] == {k: v for k, v in raw.items() if k != "columns"}
    assert a["columns"] == [c["column"] for c in raw["columns"]] and a["trade_day"] == "2023-10-02"
    assert any(e["dst"] == "tradeday:2023-10-02" for e in store.edges("PINNED_AT") if e["src"] == a_id(a))
    assert all(x.endswith(".log") or "no CALC" in x for x in (n.split(":", 1)[1].strip() for n in res["not_made"]))
    _again(det.rootrows, store)


def a_id(a):
    return f"calc:{a['calc']}:{a['trade_day']}"


def _sheet_counts(root, prefix):
    wb = openpyxl.load_workbook(root / det.WORKBOOK, read_only=True)
    out = {}
    for ws in wb.worksheets:
        m = re.fullmatch(rf"{prefix} (\d{{4}}-\d{{2}}-\d{{2}})", ws.title)
        if m:
            out[m.group(1)] = sum(1 for _ in ws.iter_rows(min_row=2, values_only=True))
    return out


def test_dipoles_one_node_per_sheet_row(store):
    root = store.data_root
    counts = _sheet_counts(root, "dipoles")
    assert sorted(counts) == list(det.DAYS)
    det.dipoles(store)
    nodes = store.nodes("DipoleEvent")
    assert len(nodes) == sum(counts.values())
    for d, n in counts.items():
        assert len([x for x in nodes if x["attrs"]["trade_day"] == d]) == n
    wb = openpyxl.load_workbook(root / det.WORKBOOK, read_only=True)
    ws = wb["dipoles 2023-10-02"]
    rows = list(ws.iter_rows(min_row=1, max_row=2, values_only=True))
    header, first = rows
    node = store.node(f"dipole:{first[1]}")["attrs"]
    assert node["pinned"] == dict(zip(header, first)) and node["row"] == 2 and node["sheet"] == "dipoles 2023-10-02"
    assert node["birth_ns"] == int(first[3])
    assert len(store.edges("PINNED_AT")) == len(nodes) and store.edges("DERIVED_FROM") == []
    assert store.node(node["source"])["attrs"]["path"] == det.WORKBOOK     # each line names the workbook it came from
    # every dipole's own birth time lies inside the trade day its sheet is named for
    days = {n["attrs"]["date"]: n["attrs"] for n in store.nodes("TradeDay")}
    outside = [x["id"] for x in nodes
               if not days[x["attrs"]["trade_day"]]["start_ns"] <= x["attrs"]["birth_ns"] < days[x["attrs"]["trade_day"]]["end_ns"]]
    assert outside == []
    _again(det.dipoles, store)


def test_peaks_one_node_per_sheet_row(store):
    root = store.data_root
    counts = _sheet_counts(root, "peaks")
    assert sorted(counts) == list(det.DAYS)
    res = det.peaks(store)
    nodes = store.nodes("Peak")
    assert len(nodes) == sum(counts.values())
    wb = openpyxl.load_workbook(root / det.WORKBOOK, read_only=True)
    header, first = list(wb["peaks 2023-10-03"].iter_rows(min_row=1, max_row=2, values_only=True))
    node = next(n for n in nodes if n["attrs"]["trade_day"] == "2023-10-03" and n["attrs"]["row"] == 2)["attrs"]
    assert node["pinned"] == dict(zip(header, first)) and node["position_on_tape"] == int(first[1])
    assert node["high_eastern"] == str(first[0])
    assert len(res["duplicate_ids_renumbered"]) == len({n["id"] for n in nodes if "#row" in n["id"]})
    assert len(store.edges("PINNED_AT")) == len(nodes) and store.edges("DERIVED_FROM") == []
    _again(det.peaks, store)


def test_renders_one_node_per_tracked_png_or_html(store):
    root = store.data_root
    det.renders(store)
    tracked = [p for p in _git(root, "ls-files").splitlines() if p.endswith((".png", ".html"))]
    nodes = store.nodes("Render")
    assert len(nodes) == len(tracked) and tracked
    n = store.node(f"render:{tracked[0]}")["attrs"]
    assert n["bytes"] == (root / tracked[0]).stat().st_size and len(n["sha256"]) == 64 and n["commit"]
    _again(det.renders, store)


def test_what_a_loader_could_not_place_is_kept_in_the_graph_as_an_open_task(store):
    """A manifest with no list of files, a CALC file whose name does not fit, a COUNT file with no main file.
    Real records only: where the real checkout holds no such case, that part is skipped with the reason."""
    root = store.data_root
    res = det.manifests(store)
    tasks = {t["id"]: t["attrs"] for t in store.nodes("Task") if t["id"].startswith("task:manifest-not-listed:")}
    assert len(tasks) == len(res["not_listed"])
    assert all(a["state"] == "open" and a["reason"] for a in tasks.values())
    for m in res["not_listed"]:
        assert any(m in a["text"] for a in tasks.values())
    _again(det.manifests, store)                                   # not twice
    _need_refs(root)
    r = det.rootrows(store)
    kept = [t["attrs"] for t in store.nodes("Task") if t["attrs"].get("left_out_by") == det.WRITER]
    assert len(kept) >= len(r["not_made"])
    assert all(any(n.split(" ")[0].split(":", 1)[1] in k["text"] for k in kept) for n in r["not_made"])
    if not tasks and not r["not_made"]:
        pytest.skip("the real checkout holds no manifest without a list and no CALC file left out: no case to read")


def test_one_source_is_not_flipped_between_two_kinds_by_two_writers(store):
    from tools.kgraph.sources import source_node
    det.dipoles(store)
    wb = source_node("markets-data", store.data_root, det.WORKBOOK)
    assert store.node(wb["id"])["attrs"]["kind"] == "workbook"
    assert store.write([wb], written_by="code:test@x")["unchanged"] == 1       # the other writer (resolve) says the same kind
    assert len(store.history(wb["id"])) == 1
