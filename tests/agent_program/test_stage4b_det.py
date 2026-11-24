"""Stage 4b (no model): saved outputs, manifests, dipoles, peaks and renders in the graph, checked
against the real records they were read from. Writes go to a scratch graph, never to markets-data."""

import json
import re
import subprocess

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


def test_manifests_one_node_per_entry(store):
    root = store.data_root
    res = det.manifests(store)
    listed = [n for n in store.nodes("Source") if n["attrs"]["kind"] == "listed_file"]
    expected = 0
    for rel, key in det.MANIFESTS:
        j = json.loads((root / rel).read_text(encoding="utf-8"))
        n = len(j if key is None else j[key])
        assert res["entries_per_manifest"][rel] == n
        expected += n
    assert len(listed) == expected and not res["not_listed"]
    ids = {n["id"] for n in listed}
    assert all(d in ids for d in res["duplicate_ids_renumbered"])
    members = store.edges("MEMBER_OF")
    assert len(members) == expected
    # one real entry comes back whole, as stored, and a UTC clock day stays a UTC clock day
    first = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))["entries"][0]
    node = next(n for n in listed if n["attrs"]["manifest_index"] == 0 and n["attrs"]["manifest"].startswith("src:markets-data:MANIFEST.json@"))
    assert node["attrs"]["entry"] == first
    assert node["attrs"]["utc_day"] == first["utc_day"] and "trade_day" not in node["attrs"]
    # where a listed file is in the checkout, the node's path is that file (counted here by another route)
    for rel, key in det.MANIFESTS:
        j = json.loads((root / rel).read_text(encoding="utf-8"))
        entries = j if key is None else j[key]
        there = 0
        for e in entries:
            names = [e[f] for f in ("path", "markets_data_path", "file", "stored") if isinstance(e.get(f), str)]
            there += any((root / n).is_file() or (root / rel).parent.joinpath(n).is_file() for n in names)
        mine = [n for n in listed if n["attrs"]["manifest"].startswith(f"src:markets-data:{rel}@")]
        assert sum(n["attrs"]["present_in_checkout"] for n in mine) == there
        assert all((root / n["attrs"]["path"]).is_file() for n in mine if n["attrs"]["present_in_checkout"])
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
    assert len([s for s in store.nodes("Source") if s["attrs"].get("branch")]) == n_json + 4
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
