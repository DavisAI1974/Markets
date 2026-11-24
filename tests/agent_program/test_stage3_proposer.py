"""Stage 3, the proposer: checks on real records only (see test_stage3_ratchet.py). Nothing here runs the
engine: no paper run, no trial of the platform."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.kgraph import ingest_agent_runs as iar
from tools.kgraph.store import GraphStore

from .realrecords import PAPER, data_root


@pytest.fixture(scope="module")
def root():
    return data_root()


def scratch_store(root, tmp_path):
    g = tmp_path / "graph"
    if (root / "graph").exists():
        shutil.copytree(root / "graph", g)
    return GraphStore(root, graph_dir=g), g


def test_run_47_two_lines_load_as_two_revisions(root, tmp_path):
    lines = [json.loads(l) for l in (root / iar.RUNS_FILE).read_text().splitlines() if l.strip()]
    twice = [l for l in lines if l["run"] == 47]
    if len(twice) < 2 or not any("corrects" in l for l in twice):
        pytest.skip("this checkout has no corrected run 47")
    store, g = scratch_store(root, tmp_path)
    iar.agent_runs(store)
    hist = GraphStore(root, graph_dir=g).history("run:0047")
    assert [h["rev"] for h in hist] == [1, 2]
    assert "corrects" not in hist[0]["attrs"] and "corrects" in hist[1]["attrs"]
    assert hist[1]["attrs"]["line_start"] > hist[0]["attrs"]["line_start"]


def test_same_run_number_without_corrects_or_across_sessions_is_still_refused(root, tmp_path):
    src = tmp_path / "data"
    f = src / iar.RUNS_FILE
    f.parent.mkdir(parents=True)
    shutil.copy(root / "MANIFEST.json", src / "MANIFEST.json")   # makes it a checkout the store accepts
    real = [json.loads(l) for l in (root / iar.RUNS_FILE).read_text().splitlines() if l.strip()]
    base = next(l for l in real if l["run"] == 46)       # a real line, only edited to be repeated
    def write(second):
        f.write_text(json.dumps(base) + "\n" + json.dumps(second) + "\n")
        for a in (["init", "-q"], ["add", "-A"],
                  ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"]):
            subprocess.run(["git", "-C", str(src), *a], check=True, capture_output=True)
    store = GraphStore(src, graph_dir=tmp_path / "g1")
    write(dict(base))                                           # no corrects
    with pytest.raises(ValueError, match="both say run 46"):
        iar.agent_runs(store)
    store = GraphStore(src, graph_dir=tmp_path / "g2")
    write(dict(base, corrects="x", session="another"))          # corrects, other session
    with pytest.raises(ValueError, match="both say run 46"):
        iar.agent_runs(store)
