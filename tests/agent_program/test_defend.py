"""Tickets 02 and 03: registering a claim before its outcome is seen, and the independent challenge.

Real things only. The grounds are a real Claim of the markets-data graph (claim:70038adffed2), the real text
of rule CL01 of the paper-trading-platform at its real commit, and a real line of a real file of markets-data;
the proposer and the reviewer are two real AgentRuns of the graph (run:0002 and run:0001). The claim file and
the challenge file each check writes are THIS TEST'S OWN TEXT about those real things: they are not market
data and make no statement about the market. Every write goes to a scratch copy of the graph, made once for
the module; markets-data is only read.
"""

import copy
import json
import shutil
import subprocess

import pytest

from tools.kgraph import defend, schema
from tools.kgraph.store import GraphStore

from .realrecords import WORK, data_root

CLAIM_ID = "claim:70038adffed2"
PROPOSER, REVIEWER = "run:0002", "run:0001"
HANDOFF = f"{WORK}/NEXT_SESSION_HANDOFF_20261124X.md"
MECH = "MECHANISM-TEXT-the proposer's own reasoning about why"
ALT = "ALTERNATIVE-TEXT-the proposer's own other reading"
FALS = "FALSIFIER-TEXT-an observation the proposer wrote beforehand"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = data_root()
    plat = root.parent / "paper-trading-platform"
    if not (plat / ".git").exists():
        pytest.skip("no paper-trading-platform checkout")
    commit = subprocess.run(["git", "-C", str(plat), "log", "-1", "--format=%H", "--", "paper_platform/rules/CL01.json"],
                            capture_output=True, text=True).stdout.strip()
    g = tmp_path_factory.mktemp("g") / "graph"
    shutil.copytree(root / "graph", g)
    store = GraphStore(root, graph_dir=g)
    for need in (CLAIM_ID, PROPOSER, REVIEWER):
        if not store.node(need):
            pytest.skip(f"{need} is not in this graph")
    spec = json.loads((plat / "paper_platform/rules/CL01.json").read_text())["specification"]
    return {"store": store, "root": root, "graph": g, "commit": commit, "spec": spec}


def _claim(world, key="test-claim-1", **over):
    d = {
        "claim_key": key, "hypothesis": "HYPOTHESIS-TEXT plain words", "exact_claim": "EXACT-CLAIM-TEXT about rule CL01",
        "scope": "SCOPE-TEXT one rule, one commit", "boundaries": "BOUNDARIES-TEXT none beyond the scope",
        "mechanism": MECH, "alternatives": [ALT],
        "falsifiers": [{"observation": FALS, "record": "the decider's stored decisions"}],
        "code_commit": world["commit"], "artifact_path": "paper_platform/rules/CL01.json", "artifact_sha256": "a" * 64,
        "outcome_visibility": "OUTCOME-TEXT the proposer had seen no outcome",
        "inference": True, "inference_reason": "INFERENCE-TEXT it is the proposer's reading",
        "rests_on": [{"kind": "claim", "id": CLAIM_ID},
                     {"kind": "rule", "rule_id": "CL01", "commit": world["commit"]},
                     {"kind": "greg", "repo": "markets-data", "path": HANDOFF, "line_start": 3, "line_end": 3,
                      "quote": "This file replaces handoff W as the starting point"}],
    }
    d.update(over)
    return d


def _w(tmp_path, d, name="f.json"):
    p = tmp_path / name
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def _chal(**over):
    d = {"alternatives": ["the handoff was renamed, not replaced"], "falsifiers": ["a later handoff that names W as current"],
         "distinguishing_observation": "the first line of the file names which handoff it follows",
         "what_was_checked": ["the cited lines"], "what_was_observed": ["the words stand in the file"],
         "what_remains_open": ["whether the next session used it"], "objections": ["none beyond what remains open"]}
    d.update(over)
    return d


def test_a_complete_claim_registers_and_reads_back(world, tmp_path):
    s = world["store"]
    r = defend.register(s, _w(tmp_path, _claim(world)), PROPOSER)
    assert r["new"] >= 1 and s.node(r["claim"])["rev"] == 1
    c = s.node(r["claim"])
    a = c["attrs"]
    d = _claim(world)
    for k in ("hypothesis", "exact_claim", "scope", "boundaries", "mechanism", "alternatives", "falsifiers", "code_commit",
              "artifact_path", "artifact_sha256", "outcome_visibility", "inference", "inference_reason"):
        assert a[k] == d[k], k
    assert a["proposer_run"] == PROPOSER and len(a["rests_on"]) == 3
    kinds = {(e["type"], e["dst"]) for e in s.edges() if e["src"] == c["id"]}
    assert ("DEPENDS_ON", CLAIM_ID) in kinds
    text = defend.show(s, c["id"])
    for k in (MECH, ALT, FALS, "OUTCOME-TEXT", "EXACT-CLAIM-TEXT"):
        assert k in text


@pytest.mark.parametrize("field,over", [
    ("mechanism", {"mechanism": ""}), ("alternatives", {"alternatives": []}), ("falsifiers", {"falsifiers": []}),
    ("scope", {"scope": " "}), ("exact_claim", {"exact_claim": ""}), ("outcome_visibility", {"outcome_visibility": ""}),
])
def test_a_claim_missing_a_field_is_refused_naming_it(world, tmp_path, field, over):
    with pytest.raises(schema.Refused, match=field):
        defend.register(world["store"], _w(tmp_path, _claim(world, key="refuse-" + field, **over)), PROPOSER)
    assert world["store"].node("claim:reg-" + defend.sha("refuse-" + field)) is None


def test_a_falsifier_must_name_its_record(world, tmp_path):
    with pytest.raises(schema.Refused, match="falsifiers"):
        defend.register(world["store"], _w(tmp_path, _claim(world, falsifiers=[{"observation": "x", "record": ""}])), PROPOSER)


@pytest.mark.parametrize("ground", [
    {"kind": "claim", "id": "claim:does-not-exist"},
    {"kind": "claim", "id": PROPOSER},
    {"kind": "rule", "rule_id": "CL01", "commit": "0" * 40},
    {"kind": "rule", "rule_id": "CL99", "commit": "HEAD"},
    {"kind": "greg", "repo": "markets-data", "path": HANDOFF, "line_start": 3, "line_end": 3, "quote": "words that are not in the file"},
    {"kind": "greg", "repo": "markets-data", "path": "no/such/file.md", "line_start": 1, "line_end": 1, "quote": "x"},
])
def test_a_ground_that_is_not_real_is_refused(world, tmp_path, ground):
    with pytest.raises(schema.Refused, match="rests_on"):
        defend.register(world["store"], _w(tmp_path, _claim(world, key="badground", rests_on=[ground])), PROPOSER)


def test_a_run_that_is_not_an_agent_run_is_refused(world, tmp_path):
    for bad in (CLAIM_ID, "run:9999", ""):
        with pytest.raises(schema.Refused, match="AgentRun"):
            defend.register(world["store"], _w(tmp_path, _claim(world, key="badrun")), bad)


def test_the_same_file_twice_writes_nothing_and_a_changed_file_is_the_next_revision(world, tmp_path):
    s = world["store"]
    p = _w(tmp_path, _claim(world, key="twice"))
    first = defend.register(s, p, PROPOSER)
    again = defend.register(s, p, PROPOSER)
    assert first["new"] >= 1 and again["new"] == 0 and again["revised"] == 0 and again["unchanged"] >= 1
    cid = first["claim"]
    nxt = defend.register(s, _w(tmp_path, _claim(world, key="twice", scope="SCOPE-TEXT changed"), "g.json"), PROPOSER)
    assert nxt["claim"] == cid and nxt["revised"] == 1 and s.node(cid)["rev"] == 2 and len(s.history(cid)) == 2


def test_the_brief_holds_the_grounds_in_full_and_not_the_proposers_reasoning(world, tmp_path):
    s = world["store"]
    cid = defend.register(s, _w(tmp_path, _claim(world, key="briefed")), PROPOSER)["claim"]
    b = defend.brief(s, cid)
    assert "EXACT-CLAIM-TEXT" in b and "SCOPE-TEXT" in b and "BOUNDARIES-TEXT" in b
    assert world["spec"] in b and world["commit"] in b
    assert s.node(CLAIM_ID)["attrs"]["text"] in b and "This file replaces handoff W as the starting point" in b
    assert "a" * 64 in b
    for k in (MECH, ALT, FALS, "HYPOTHESIS-TEXT", "INFERENCE-TEXT", "OUTCOME-TEXT", "the decider's stored decisions"):
        assert k not in b, k
    low = b.lower()
    assert "no verdict word" in low and "alternatives" in low and "distinguishing_observation" in low
    out = tmp_path / "brief.md"
    assert defend.main(["challenge-brief", "--claim", cid, "--out", str(out), "--data", str(world["root"]),
                        "--graph-dir", str(world["graph"])]) == 0
    assert out.read_text(encoding="utf-8") == b


def test_a_challenge_is_an_evaluation_tied_to_the_claim_and_undefended_follows_it(world, tmp_path):
    s = world["store"]
    cid = defend.register(s, _w(tmp_path, _claim(world, key="challenged")), PROPOSER)["claim"]
    assert any(cid in l for l in defend.undefended(s))
    cf = _w(tmp_path, _chal(), "c.json")
    r = defend.challenge(s, cid, cf, REVIEWER)
    ev = s.node(r["evaluation"])
    assert ev["type"] == "Evaluation" and ev["attrs"]["rubric"] == defend.RUBRIC
    assert defend.RUBRIC.startswith("independent challenge v1: ")
    for k in ("what_was_checked", "what_was_observed", "what_remains_open", "reviewer", "alternatives", "falsifiers",
              "distinguishing_observation", "claim_revision", "input_hash", "expected_observation"):
        assert ev["attrs"][k]
    assert ev["attrs"]["reviewer"] == REVIEWER
    assert any(e["type"] == "EVALUATES" and e["src"] == ev["id"] and e["dst"] == cid for e in s.edges())
    assert not any(cid in l for l in defend.undefended(s))
    shown = defend.show(s, cid)
    assert ev["id"] in shown and "whether the next session used it" in shown
    assert defend.challenge(s, cid, cf, REVIEWER)["new"] == 0     # the same challenge twice writes nothing
    # the changed claim is undefended again until it is challenged at its new revision
    defend.register(s, _w(tmp_path, _claim(world, key="challenged", scope="SCOPE-TEXT changed again"), "h.json"), PROPOSER)
    assert any(cid in l for l in defend.undefended(s))


@pytest.mark.parametrize("over,field", [
    ({"alternatives": []}, "alternatives"), ({"falsifiers": []}, "falsifiers"),
    ({"distinguishing_observation": ""}, "distinguishing_observation"),
])
def test_a_challenge_without_its_three_parts_is_refused(world, tmp_path, over, field):
    s = world["store"]
    cid = defend.register(s, _w(tmp_path, _claim(world, key="needs-three")), PROPOSER)["claim"]
    with pytest.raises(schema.Refused, match=field):
        defend.challenge(s, cid, _w(tmp_path, _chal(**over), "c.json"), REVIEWER)


def test_the_proposer_may_not_challenge_its_own_claim(world, tmp_path):
    s = world["store"]
    cid = defend.register(s, _w(tmp_path, _claim(world, key="own")), PROPOSER)["claim"]
    with pytest.raises(schema.Refused, match="sole verifier"):
        defend.challenge(s, cid, _w(tmp_path, _chal(), "c.json"), PROPOSER)
    with pytest.raises(schema.Refused, match="AgentRun"):
        defend.challenge(s, cid, _w(tmp_path, _chal(), "c.json"), "run:9999")


def test_a_verdict_word_in_a_status_field_is_refused(world, tmp_path):
    s = world["store"]
    cid = defend.register(s, _w(tmp_path, _claim(world, key="verdict")), PROPOSER)["claim"]
    for over in ({"status": "SUPPORTED_WITHIN_SCOPE"}, {"verdict": "pass"}, {"status": "refuted with evidence"}):
        with pytest.raises(schema.Refused, match="verdict word"):
            defend.challenge(s, cid, _w(tmp_path, _chal(**over), "c.json"), REVIEWER)


def test_the_store_checks_clean_after_the_writes(world, capsys):
    from tools.kgraph.__main__ import main
    before = len(world["store"].check_all())
    fresh = GraphStore(world["root"], graph_dir=world["graph"], tolerant=True)
    breaches = fresh.check_all()
    assert not [b for b in breaches if "claim:reg-" in b or "eval:" in b and "independent challenge" in b], breaches
    assert main(["check", "--data", str(world["root"]), "--graph-dir", str(world["graph"])]) in (0, 1)
    out = capsys.readouterr().out
    assert "claim:reg-" not in out
    assert before == len(breaches)
