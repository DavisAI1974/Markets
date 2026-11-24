"""Stage 4b, the model part: what a reader returned becomes claims only where its quote stands in the
file. Checked on the real read of handoff X kept in markets-data graph/reads/ and on the real file."""

import json
import re

import pytest

from tools.kgraph import extract, ingest_agent_runs, schema
from tools.kgraph.store import GraphStore

from .realrecords import WORK, data_root

READ = "graph/reads/run-0018-NEXT_SESSION_HANDOFF_20261124X.json"
HANDOFF = f"{WORK}/NEXT_SESSION_HANDOFF_20261124X.md"
RUN = "run:0018"


@pytest.fixture()
def loaded(tmp_path):
    root = data_root()
    if not (root / READ).exists():
        pytest.skip(f"{READ} is not in this markets-data checkout")
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)                       # the reader's own run must be in the graph
    dirs = extract.repo_dirs(root, None, None)
    result = json.loads((root / READ).read_text(encoding="utf-8"))
    return store, dirs, result


def _stands(claim, lines):
    """Counted here by a route of the check's own: the quote, spaces squeezed, inside its lines."""
    span = " ".join(" ".join(lines[claim["line_start"] - 1:claim["line_end"]]).split())
    return " ".join(claim["quote"].split()) in span


def test_every_returned_claim_is_written_or_kept_as_thrown_out(loaded):
    store, dirs, result = loaded
    lines = (store.data_root / HANDOFF).read_text(encoding="utf-8").splitlines()
    returned = [c for p in result["pieces"] for c in p["claims"]]
    standing = [c for c in returned if _stands(c, lines)]
    report = extract.load_result(store, dirs, result, RUN)
    claims = store.nodes("Claim")
    assert report["claims_written"] == len(claims) == len(standing)
    assert report["thrown_out"] == len(returned) - len(standing)
    assert len([t for t in store.nodes("Task") if t["attrs"]["state"] == "blocked"]) == report["thrown_out"]
    # each claim is tied to the handoff by a SUPPORTS link and to the run that read it
    sid = "src:markets-data:" + HANDOFF
    assert {e["dst"] for e in store.edges("SUPPORTS")} == {c["id"] for c in claims}
    assert all(e["src"] == sid for e in store.edges("SUPPORTS"))
    assert {e["dst"] for e in store.edges("PRODUCED") if e["src"] == RUN} >= {c["id"] for c in claims}
    for c in claims:
        a = c["attrs"]
        assert _stands(a, lines) and a["source"] == sid and a["extracted_by"] == RUN and len(a["source_commit"]) == 40
    # Greg's own words are kept as his
    greg = [c["attrs"] for c in claims if "finish building everything for the agents" in c["attrs"]["quote"]]
    assert len(greg) == 1 and greg[0]["said_by"] == "Greg" and greg[0]["statement_kind"] == "decision"
    assert store.check_all() == []
    again = extract.load_result(store, dirs, result, RUN)      # a second load adds nothing
    assert len(store.nodes("Claim")) == len(claims) and again["claims_written"] == len(claims)
    assert all(len(store.history(c["id"])) == 1 for c in claims)


def test_a_claim_whose_quote_is_not_in_the_file_is_not_believed(loaded):
    store, dirs, result = loaded
    real = result["pieces"][0]["claims"][0]
    wrong_words = {**real, "quote": real["quote"].replace("replaces", "follows")}       # one word changed
    wrong_lines = {**real, "line_start": 60, "line_end": 60}                           # real quote, wrong lines
    outside = {**real, "line_start": 500, "line_end": 501}                             # lines the piece does not have
    bad = {"pieces": [{"piece": result["pieces"][0]["piece"], "claims": [real, wrong_words, wrong_lines, outside]}]}
    report = extract.load_result(store, dirs, bad, RUN)
    assert report["claims_written"] == 1 and report["thrown_out"] == 3
    kept = [t["attrs"] for t in store.nodes("Task") if t["attrs"]["state"] == "blocked"]
    assert len(kept) == 3 and all(k["returned"] in (wrong_words, wrong_lines, outside) for k in kept)
    assert sorted(bool(re.search("word for word|outside the piece", k["reason"])) for k in kept) == [True] * 3


def test_a_read_needs_its_run_and_the_file_as_it_was_cut(loaded):
    store, dirs, result = loaded
    with pytest.raises(schema.Refused, match="not an AgentRun"):
        extract.load_result(store, dirs, result, "run:9999")
    stale = json.loads(json.dumps(result))
    stale["pieces"][0]["piece"] = re.sub(r"@[0-9a-f]{10}#", "@0000000000#", stale["pieces"][0]["piece"])
    with pytest.raises(schema.Refused, match="has changed since the brief"):
        extract.load_result(store, dirs, stale, RUN)
    assert store.nodes("Claim") == []


def test_coverage_says_which_documents_are_read_and_which_are_not(loaded):
    store, dirs, result = loaded
    extract.load_result(store, dirs, result, RUN)
    out = extract.coverage(store, dirs)
    docs = {(d["repo"], d["path"]): d for d in out["documents"]}
    assert docs[("markets-data", HANDOFF)]["state"] == "done"
    w = docs[("markets-data", f"{WORK}/NEXT_SESSION_HANDOFF_20261124W.md")]
    assert w["state"] == "not_extracted" and w["claims"] == 0
    tasks = {t["id"]: t["attrs"] for t in store.nodes("Task") if t["id"].startswith("task:extract:")}
    assert len(tasks) == len([d for d in out["documents"] if d["state"] in ("done", "open", "not_extracted")])
    assert out["read"] == 1 and out["not_read"] == len(tasks) - 1          # nothing is passed over in silence
    assert tasks[f"task:extract:markets-data:{HANDOFF}"]["claims"] == len(store.nodes("Claim"))


def test_the_brief_numbers_every_line_and_cuts_only_at_entries():
    root = data_root()
    store = GraphStore(root)
    dirs = extract.repo_dirs(root, None, None)
    brief, listing = extract.build_brief(store, dirs, [f"markets-data:{HANDOFF}"])
    lines = (root / HANDOFF).read_text(encoding="utf-8").splitlines()
    assert len(listing) == 1 and (listing[0]["first"], listing[0]["last"]) == (1, len(lines))
    assert all(f"{n}| {lines[n - 1]}" in brief for n in (1, 7, len(lines)))
    big = (root / WORK / "root-redesign-20261116/ROOT_GAMEPLAN_DECISIONS.md").read_text(encoding="utf-8").splitlines()
    cut = extract.pieces(big)
    assert cut[0][0] == 1 and cut[-1][1] == len(big)
    assert all(a2 == b1 + 1 for (_, b1), (a2, _) in zip(cut, cut[1:]))      # no line lost, none read twice
    assert all(big[a - 1].startswith(("#", "- ")) for a, _ in cut[1:])       # a cut never falls inside an entry
