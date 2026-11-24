"""Greg, 2026-11-24: "Make sure any nee claims aren't tied to tasty platdorm issues". What the tastytrade
sandbox does and what its thin feed lacks are parked, so nothing new may rest on a claim about them.
Checked on the real reads of handoff X and the running list."""

import json
import re
import subprocess

import pytest

from tools.kgraph import context, extract, grounding, ingest_agent_runs, ingest_paper, platform_scope, schema
from tools.kgraph.sources import link, source_node
from tools.kgraph.store import GraphStore

from .realrecords import data_root

READS = {"run:0018": "graph/reads/run-0018-NEXT_SESSION_HANDOFF_20261124X.json",
         "run:0021": "graph/reads/run-0021-NEXT_SESSION_HANDOFF_20261124W.json",
         "run:0023": "graph/reads/run-0023-RUNNING_LIST.json"}
READ_V = ("run:0032", "graph/reads/run-0032-NEXT_SESSION_HANDOFF_20261124V.json")
ANSWER = "graph/evaluations/run-0036-tastytrade-platform.json"
LIST = "tasty/RUNNING_LIST.md"


@pytest.fixture()
def graph(tmp_path):
    root = data_root()
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)
    dirs = extract.repo_dirs(root, None, None)
    if "paper-trading-platform" not in dirs:
        pytest.skip("no paper-trading-platform checkout beside Markets")
    for run, rel in READS.items():
        if not (root / rel).exists():
            pytest.skip(f"{rel} is not in this markets-data checkout")
        extract.load_result(store, dirs, json.loads((root / rel).read_text(encoding="utf-8")), run)
    return store, dirs


def _claim(store, words):
    return next(c for c in store.nodes("Claim") if words in c["attrs"]["quote"])


def test_a_claim_read_from_a_document_is_marked_as_it_is_loaded(graph):
    store, dirs = graph
    tied = platform_scope.ties(store)
    assert tied                                             # the loader marks: no separate step to forget
    # the feed's own fault (running list, section B): "A THIRD OF THE PRINTS HAVE NO SIDE (9 of 107, then 141 of 440)"
    assert tied[_claim(store, "141 of 440")["id"]]["rule"] == "the running list"
    # the sandbox account left short (handoff X line 96): marked by its words, provisionally
    assert tied[_claim(store, "5WY79188 is short 13 lots")["id"]]["rule"] == "its own words"
    # a rule that has nothing to do with the platform
    assert _claim(store, "A trade day is 6 pm Eastern")["id"] not in tied
    # Greg's own words are never marked, whatever their kind; both kinds of claim really occur here
    claims = {c["id"]: c["attrs"] for c in store.nodes("Claim")}
    names_it = lambda a: bool(platform_scope.WORDS.search(a["text"] + " " + a["quote"]))
    gregs = [i for i, a in claims.items() if a.get("said_by") == "Greg" and names_it(a)]
    rules = [i for i, a in claims.items() if a["statement_kind"] == "rule" and names_it(a)]
    assert gregs and rules and not set(gregs) & set(tied)
    # a standing rule is never marked for its words; only a line the running list itself parks is
    assert [r for r in rules if r not in tied] and all(tied[r]["rule"] == "the running list" for r in rules if r in tied)
    assert _claim(store, "sandbox-only issues are parked")["id"] in gregs
    for t in tied.values():
        assert t["why"] and t["rule"] in ("the running list", "its own words")
    assert platform_scope.mark(store, dirs)["new"] == 0       # marking twice marks nothing twice
    assert platform_scope.pending(store, dirs) == []


def test_a_claim_written_by_another_path_shows_up_as_not_marked(graph):
    """Whatever writes a claim must mark; one that does not is listed by `python3 -m tools.kgraph check`.
    A real claim of handoff V's read is written here straight through the store, as another path would."""
    store, dirs = graph
    run, rel = READ_V
    if not (store.data_root / rel).exists():
        pytest.skip(f"{rel} is not in this markets-data checkout")
    piece = json.loads((store.data_root / rel).read_text(encoding="utf-8"))["pieces"][0]
    sid = piece["piece"].split("@")[0]
    c = next(c for c in piece["claims"] if c.get("said_by") != "Greg" and c["statement_kind"] != "rule"
             and platform_scope.WORDS.search(c["text"] + " " + c["quote"]))
    src = source_node("markets-data", store.data_root, sid.split(":", 2)[2])
    node = {"id": extract.claim_id(sid, c["quote"]), "type": "Claim", "attrs": {
        "text": c["text"], "statement_kind": c["statement_kind"], "inference": c["inference"], "said_by": c.get("said_by"),
        "source": sid, "line_start": c["line_start"], "line_end": c["line_end"], "quote": c["quote"]}}
    store.write([src, node], [link("SUPPORTS", sid, node["id"])], written_by="code:test")
    waiting = platform_scope.pending(store, dirs)
    assert len(waiting) == 1 and node["id"] in waiting[0] and "is not marked" in waiting[0]
    assert platform_scope.mark(store, dirs)["new"] == 1 and platform_scope.pending(store, dirs) == []


def test_the_parked_lines_are_read_from_the_running_list_itself(graph):
    store, dirs = graph
    # the list as it stood at the commit the read was made from (the list is added to; a claim's line
    # numbers are that wording's)
    read_at = next(c["attrs"]["source_commit"] for c in store.nodes("Claim") if c["attrs"]["source"].endswith(LIST))
    text = subprocess.run(["git", "-C", str(dirs["paper-trading-platform"]), "show", f"{read_at}:{LIST}"],
                          capture_output=True, text=True, check=True).stdout
    # the list's own words (C22): "... dropped when the sandbox is left behind: C5 (...), C8 ..., C20 ..."
    assert platform_scope.parked_items(text) == {"C5", "C8", "C9", "C19", "C10", "C18", "C11", "C13", "C14", "C15", "C20"}
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines, 1) if l.startswith("14. ") and "STUCK SHORT 13 LOTS" in l)
    end = next(i for i, l in enumerate(lines, 1) if i > start and re.match(r"\d+\. ", l)) - 1
    tied = platform_scope.members(store)
    in_c14 = [c for c in store.nodes("Claim") if c["attrs"]["source"].endswith(LIST) and start <= c["attrs"]["line_start"] <= end]
    assert in_c14 and all(c["id"] in tied for c in in_c14)
    # a line that is "still ours, whatever the feed or the broker" (C2) is not tied by the list
    c2 = [c for c in store.nodes("Claim") if "worked out again from all the trades at every print" in c["attrs"]["quote"]]
    assert c2 and not any(e["attrs"]["rule"] == "the running list" for e in store.edges("MEMBER_OF")
                          if e["src"] == c2[0]["id"] and e["dst"] == platform_scope.SCOPE_ID)


def test_nothing_new_may_rest_on_what_is_marked(graph):
    """The links tried here are relations the record itself states, not invented ones: CL16 was written
    for the print with no side (decisions file, 2026-11-24); the list's reading "if many are unmarked
    buys ..." rests on its count of prints with no side; handoff X and the list's line C14 state the same
    fact about the account; and the list's line C19 is a statement about the 13 fills."""
    store, dirs = graph
    no_side = _claim(store, "141 of 440")
    ingest_paper.paper(store, str(dirs["paper-trading-platform"]))
    cl16 = next(n for n in store.nodes("Entity") if n["attrs"].get("entity_kind") == "rule version" and n["attrs"]["strategy"] == "CL16")
    with pytest.raises(schema.Refused, match="tastytrade platform"):       # a rule version may not rest on it
        store.write([], [link("DERIVED_FROM", cl16["id"], no_side["id"])], written_by="code:test")
    reading = next(c for c in store.nodes("Claim") if c["attrs"]["inference"] and c["attrs"]["source"].endswith(LIST)
                   and 56 <= c["attrs"]["line_start"] <= 61)
    with pytest.raises(schema.Refused, match="tastytrade platform"):       # nor may a reading
        store.write([], [link("DERIVED_FROM", reading["id"], no_side["id"])], written_by="code:test")
    # nor may a claim be written as a later wording of a marked one
    x_short, list_short = _claim(store, "5WY79188 is short 13 lots"), _claim(store, "STUCK SHORT 13 LOTS")
    with pytest.raises(schema.Refused, match="tastytrade platform"):
        store.write([], [link("REVISES", x_short["id"], list_short["id"])], written_by="code:test")
    # the runs' own orders and fills are marked as they are loaded, and a claim may not rest on one
    tied = platform_scope.ties(store)
    records = store.nodes("Order") + store.nodes("Fill")
    assert records and all(tied[r["id"]]["rule"] == "a record of a sandbox run" for r in records)
    fill = store.nodes("Fill")[0]
    about_fills = next(c for c in store.nodes("Claim") if c["attrs"]["source"].endswith(LIST) and "13 fills" in c["attrs"]["quote"])
    with pytest.raises(schema.Refused, match="tastytrade platform"):
        store.write([], [link("DERIVED_FROM", about_fills["id"], fill["id"])], written_by="code:test")
    # the records' own links to one another are records, not something new resting on the platform
    assert store.edges("FILLS") and store.edges("PLACED_BY") and store.check_all() == []
    assert not [e for e in store.edges() if e["type"] in ("DERIVED_FROM", "REVISES") and e["dst"] in (no_side["id"], list_short["id"])]
    # a mark is lifted only on Greg's own words (none are made up here, so only the refusal is checked)
    with pytest.raises(schema.Refused, match="Greg"):
        platform_scope.untie(store, no_side["id"], greg_words="", by="code:test")
    assert no_side["id"] in platform_scope.members(store)


def test_the_evaluators_real_answer_confirms_marks_and_lifts_provisional_ones(tmp_path):
    """On the evaluator's own answer as it came back, kept in markets-data. Skipped until one exists."""
    root = data_root()
    if not (root / ANSWER).exists():
        pytest.skip(f"{ANSWER} is not in this markets-data checkout: no evaluator has read the claims yet")
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)
    dirs = extract.repo_dirs(root, None, None)
    for f in sorted((root / "graph/reads").glob("run-*.json")):
        extract.load_result(store, dirs, json.loads(f.read_text(encoding="utf-8")), "run:" + f.name.split("-")[1])
    before = platform_scope.ties(store)
    answer = json.loads((root / ANSWER).read_text(encoding="utf-8"))
    out = platform_scope.apply(store, answer, "run:0036")
    after = platform_scope.ties(store)
    assert out["marked"] + out["confirmed"] + out["lifted"] + len(out["not_applied"]) == len(answer["tied"]) + len(answer["not_tied"])
    firm = {c for c, t in before.items() if t["rule"] != "its own words"}
    assert firm <= set(after) and all(after[c]["rule"] == before[c]["rule"] for c in firm)       # a firm mark is never lifted here
    claims = {c["id"]: c["attrs"] for c in store.nodes("Claim")}
    assert not [c for c in after if c in claims and (claims[c].get("said_by") == "Greg" or claims[c]["statement_kind"] == "rule")]
    lifted = [i["claim"] for i in answer["not_tied"] if i["claim"] in before and before[i["claim"]]["rule"] == "its own words"]
    assert out["lifted"] == len(lifted) and not set(lifted) & set(after)
    assert platform_scope.mark(store, dirs)["new"] == 0                    # a lifted mark is not made again
    for c in lifted[:5]:
        hist = store.history(platform_scope.edge_id("MEMBER_OF", c, platform_scope.SCOPE_ID, ""))
        assert hist[-1]["attrs"]["withdrawn"] and "the evaluator" in hist[-1]["attrs"]["withdrawn_reason"]
    with pytest.raises(schema.Refused):
        platform_scope.apply(store, answer, "run:9999")


def test_the_grounding_check_does_not_take_a_tied_claim_as_evidence(graph):
    store, dirs = graph
    r = grounding.check_text(store, "141 of 440 prints have no side.", dirs)
    assert r["decision"] == "revise" and "tastytrade platform" in r["reason"]
    assert any("does not come from the tastytrade" in e for e in r["required_evidence"])
    assert r["supporting_candidates"] and all(c["platform_issue"] for c in r["supporting_candidates"])   # shown, and said to be tied
    one = grounding.check_claim(store, _claim(store, "141 of 440")["id"], dirs)
    assert any("tastytrade platform" in o for o in one["what_was_observed"])
    # a sentence the list carries that is not about the platform is still found (list A2)
    ok = grounding.check_text(store, "CL14, CL17, CL05, CL06 and CL16 made 235 of the 327 trades.", dirs)
    assert ok["decision"] is None and any(not c["platform_issue"] for c in ok["supporting_candidates"])


def test_the_session_context_drops_nothing_it_marks_tied_claims_and_calls_the_parked_ones_last(graph):
    """Greg, 2026-11-24: nothing gets replaced; what does not work is scored so it is not called."""
    store, dirs = graph
    ties = platform_scope.ties(store)
    claim_ids = {c["id"] for c in store.nodes("Claim")}
    by_list = {c for c, t in ties.items() if t["rule"] != "its own words" and c in claim_ids}     # firmly marked
    by_words = {c for c in ties if c in claim_ids} - by_list
    assert by_list and by_words
    out = context.build(store, None, budget_tokens=400000, dirs=dirs)
    allc = {c["id"] for c in store.nodes("Claim")}
    assert set().union(out["included"], out["folded"], out["cut"], out["not_reached"]) == allc and out["cut"] == []
    assert by_list <= set(out["called_last"])
    text = out["text"].splitlines()
    for cid in list(by_list & set(out["included"]))[:10]:
        line = next(l for l in text if f"c:{cid.split(':', 1)[1]}" in l)
        assert "(parked: a tastytrade platform issue)" in line
    for cid in list(by_words & set(out["included"]))[:10]:
        line = next(l for l in text if f"c:{cid.split(':', 1)[1]}" in l)
        assert "(names the tastytrade platform: nothing new may rest on it)" in line
    assert "Sandbox-only issues are parked" in out["text"]                    # Greg's own decision is shown, unmarked
    # under a real budget the parked lines are the first to fall: none is shown while an unmarked claim of its kind is cut
    small = context.build(store, None, budget_tokens=6000, dirs=dirs)
    kind = lambda c: store.node(c)["attrs"]["statement_kind"]
    cut_plain = {kind(c) for c in small["cut"] if c not in small["called_last"]}
    assert not [c for c in small["included"] if c in by_list and kind(c) in cut_plain]
    assert f"{len(small['called_last'])} claims have something against them" in small["text"]
