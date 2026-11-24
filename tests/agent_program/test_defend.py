"""Tickets 02 and 03: registering a claim before its outcome is seen, and the independent challenge.

Real things only. The grounds are a real Claim of the markets-data graph (claim:70038adffed2), the real text of
rule CL01 of the paper-trading-platform at its real commit, and a real line of a real file of markets-data; the
artifact is the real file of rule CL01 at that commit; the proposer and the reviewers are real AgentRuns of the
graph (run:0002 builder; run:0003 and run:0005 reviewers). The claim file and the challenge file each check
writes are THIS TEST'S OWN TEXT about those real things: they are not market data and say nothing about the
market. Every write goes to a scratch copy of the graph, made once for the module; markets-data is only read.
"""

import hashlib
import json
import shutil
import subprocess

import pytest

from tools.kgraph import defend, grounding, schema
from tools.kgraph.extract import repo_dirs
from tools.kgraph.store import GraphStore

from .realrecords import PAPER, WORK, data_root

CLAIM_ID = "claim:70038adffed2"
PROPOSER, REVIEWER, REVIEWER2, SCOUT = "run:0002", "run:0003", "run:0005", "run:0001"
HANDOFF = f"{WORK}/NEXT_SESSION_HANDOFF_20261124X.md"
CITED_QUOTE = "This file replaces handoff W as the starting point"
RULE_QUOTE = "a run of the best offer UP takes its second step"
MECH = "MECHANISM-TEXT the proposer's own reasoning about why"
ALT = "ALTERNATIVE-TEXT the proposer's own other reading"
FALS = "FALSIFIER-TEXT an observation the proposer wrote beforehand"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = data_root()
    plat = root.parent / "paper-trading-platform"
    if not (plat / ".git").exists():
        pytest.skip("no paper-trading-platform checkout")
    commit = subprocess.run(["git", "-C", str(plat), "log", "-1", "--format=%H", "--", "paper_platform/rules/CL01.json"],
                            capture_output=True, text=True).stdout.strip()
    raw = subprocess.run(["git", "-C", str(plat), "show", f"{commit}:paper_platform/rules/CL01.json"],
                         capture_output=True).stdout
    g = tmp_path_factory.mktemp("g") / "graph"
    shutil.copytree(root / "graph", g)
    store = GraphStore(root, graph_dir=g)
    for need in (CLAIM_ID, PROPOSER, REVIEWER, REVIEWER2, SCOUT):
        if not store.node(need):
            pytest.skip(f"{need} is not in this graph")
    before = sorted(GraphStore(root, graph_dir=g, tolerant=True).check_all())
    return {"store": store, "root": root, "graph": g, "commit": commit, "sha": hashlib.sha256(raw).hexdigest(),
            "spec": json.loads(raw)["specification"], "before": before, "tmp": tmp_path_factory.mktemp("f")}


def _claim(world, key="test-claim-1", **over):
    d = {
        "claim_key": key, "hypothesis": "HYPOTHESIS-TEXT plain words", "exact_claim": "EXACT-CLAIM-TEXT about rule CL01",
        "scope": "SCOPE-TEXT one rule, one commit", "boundaries": "BOUNDARIES-TEXT none beyond the scope",
        "mechanism": MECH, "alternatives": [ALT],
        "falsifiers": [{"observation": FALS, "record": "the decider's stored decisions"}],
        "artifact_repo": "paper-trading-platform", "artifact_path": "paper_platform/rules/CL01.json",
        "code_commit": world["commit"], "artifact_sha256": world["sha"],
        "data_manifest_hashes": {"none": "no data bears on this claim yet"},
        "outcome_visibility": {"outcome_seen": False, "what": "OUTCOME-TEXT the proposer had seen no outcome"},
        "inference": False,
        "rests_on": [{"kind": "claim", "id": CLAIM_ID},
                     {"kind": "rule", "rule_id": "CL01", "commit": world["commit"], "quote": RULE_QUOTE},
                     {"kind": "cited", "repo": "markets-data", "path": HANDOFF, "line_start": 3, "line_end": 3,
                      "quote": CITED_QUOTE, "said_by": "Claude"}],
    }
    d.update(over)
    return d


def _w(world, d, name="f.json"):
    p = world["tmp"] / name
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def _reg(world, key="k", run=PROPOSER, name="f.json", **over):
    return defend.register(world["store"], _w(world, _claim(world, key, **over), name), run)


def _chal(**over):
    d = {"alternatives": ["the handoff was renamed, not replaced"], "falsifiers": [{"observation": "a later handoff that names W as current", "record": "the handoff files of markets-data"}],
         "distinguishing_observation": "the first line of the file names which handoff it follows",
         "what_was_checked": ["the cited lines"], "what_was_observed": ["the words stand in the file"],
         "what_remains_open": ["whether the next session used it"], "objections": ["none beyond what remains open"],
         "saw_proposer_reasoning": False, "what_i_opened": ["the brief only"]}
    d.update(over)
    return d


def _brief_file(world, cid):
    p = world["tmp"] / f"brief-{cid[-8:]}.md"
    p.write_text(defend.brief(world["store"], cid), encoding="utf-8")
    return p


def _challenge(world, cid, run=REVIEWER, name="c.json", **over):
    return defend.challenge(world["store"], cid, _w(world, _chal(**over), name), run, _brief_file(world, cid))


def test_a_complete_claim_registers_and_reads_back(world):
    s = world["store"]
    r = _reg(world, "t1")
    c = s.node(r["claim"])
    a, d = c["attrs"], _claim(world, "t1")
    assert c["rev"] == 1 and a["claim_file"] == d and a["proposer_run"] == PROPOSER and a["inference"] is False
    for k in ("hypothesis", "exact_claim", "scope", "boundaries", "mechanism", "alternatives", "falsifiers", "code_commit",
              "artifact_repo", "artifact_path", "artifact_sha256", "outcome_visibility"):
        assert a[k] == d[k], k
    assert a["data_manifest_hashes"] == [d["data_manifest_hashes"]]       # the explicit "none" is kept, as a one-entry list
    assert a["quote"] == RULE_QUOTE and a["source"].startswith("src:paper-trading-platform")
    cited = [g for g in a["rests_on"] if g["kind"] == "cited"][0]
    assert cited["said_by"] == "Claude" and cited["commit"] and len(cited["sha256"]) == 64
    edges = {(e["type"], e["src"], e["dst"]) for e in s.edges()}
    assert ("DERIVED_FROM", c["id"], CLAIM_ID) in edges
    assert ("SUPPORTS", cited["source"], c["id"]) in edges           # the SUPPORTS path of a cited line
    assert ("SUPPORTS", a["source"], c["id"]) in edges
    text = defend.show(s, c["id"])
    for k in (MECH, ALT, FALS, "OUTCOME-TEXT", "EXACT-CLAIM-TEXT", c["written_at"]):
        assert k in text


def test_grounding_finds_a_supporting_path_for_registered_claims(world):
    s = world["store"]
    dirs = repo_dirs(world["root"], None, None)
    c = _reg(world, "t1")["claim"]
    r = grounding.check_node(s, c, dirs)
    assert r["required_evidence"] == [] and r["supporting_paths"] and r["decision"] in (None, "unread")
    inf = _reg(world, "t-inf", inference=True, inference_reason="INFERENCE-TEXT a reading",
               rests_on=[{"kind": "claim", "id": CLAIM_ID}], name="inf.json")["claim"]
    r = grounding.check_node(s, inf, dirs)
    assert r["required_evidence"] == [] and r["supporting_paths"]


@pytest.mark.parametrize("field,over", [
    ("mechanism", {"mechanism": ""}), ("alternatives", {"alternatives": []}), ("falsifiers", {"falsifiers": []}),
    ("scope", {"scope": " "}), ("exact_claim", {"exact_claim": ""}), ("outcome_visibility", {"outcome_visibility": "none"}),
    ("outcome_visibility", {"outcome_visibility": {"outcome_seen": False, "what": ""}}),
    ("data_manifest_hashes", {"data_manifest_hashes": []}), ("falsifiers", {"falsifiers": [{"observation": "x", "record": ""}]}),
])
def test_a_claim_missing_a_field_is_refused_naming_it(world, field, over):
    with pytest.raises(schema.Refused, match=field):
        _reg(world, "refuse-" + field, **over)
    assert world["store"].node("claim:reg-" + defend.sha("refuse-" + field)) is None


def test_an_unknown_key_or_a_badly_typed_optional_is_refused_by_name(world):
    with pytest.raises(schema.Refused, match="surprise"):
        _reg(world, "unk", surprise="x")
    with pytest.raises(schema.Refused, match="source_event_ids"):
        _reg(world, "unk2", source_event_ids=[1, 2])


@pytest.mark.parametrize("ground", [
    {"kind": "claim", "id": "claim:does-not-exist"},
    {"kind": "claim", "id": PROPOSER},
    {"kind": "rule", "rule_id": "CL99", "commit": "COMMIT", "quote": RULE_QUOTE},
    {"kind": "rule", "rule_id": "CL01", "commit": "0" * 40, "quote": RULE_QUOTE},
    {"kind": "rule", "rule_id": "CL01", "commit": "COMMIT", "quote": "the"},
    {"kind": "cited", "repo": "markets-data", "path": HANDOFF, "line_start": 3, "line_end": 3, "quote": "the", "said_by": "x"},
    {"kind": "cited", "repo": "markets-data", "path": HANDOFF, "line_start": 3, "line_end": 3,
     "quote": "words that are not in the file at all", "said_by": "x"},
    {"kind": "cited", "repo": "markets-data", "path": HANDOFF, "line_start": 3, "line_end": 3, "quote": CITED_QUOTE},
    {"kind": "cited", "repo": "markets-data", "path": "no/such/file.md", "line_start": 1, "line_end": 1, "quote": "x", "said_by": "x"},
    {"kind": "greg", "repo": "markets-data", "path": HANDOFF},
])
def test_a_ground_that_is_not_real_is_refused(world, ground):
    ground = {k: (world["commit"] if v == "COMMIT" else v) for k, v in ground.items()}
    with pytest.raises(schema.Refused, match="rests_on"):
        _reg(world, "badground", rests_on=[ground])


def test_a_claim_that_is_not_an_inference_needs_a_source(world):
    with pytest.raises(schema.Refused, match="rests_on"):
        _reg(world, "nosource", rests_on=[{"kind": "claim", "id": CLAIM_ID}])


def test_a_run_that_is_not_an_agent_run_is_refused(world):
    for bad in (CLAIM_ID, "run:9999", ""):
        with pytest.raises(schema.Refused, match="AgentRun"):
            _reg(world, "badrun", run=bad)


def test_a_refused_registration_leaves_a_task_and_no_claim(world):
    s = world["store"]
    n0 = len(s.nodes("Task"))
    with pytest.raises(schema.Refused, match="mechanism"):
        _reg(world, "kept-after-refusal", mechanism="")
    tasks = [t for t in s.nodes("Task") if t["attrs"].get("claim_file", {}) and isinstance(t["attrs"]["claim_file"], dict)
             and t["attrs"]["claim_file"].get("claim_key") == "kept-after-refusal"]
    assert len(s.nodes("Task")) == n0 + 1 and len(tasks) == 1
    t = tasks[0]["attrs"]
    assert t["text"].startswith("not admissible for a check: ") and t["text"].endswith("; retained")
    assert "mechanism" in t["reason"] and t["run"] == PROPOSER and t["refused_at"] and t["claim_file"]["hypothesis"]
    assert s.node("claim:reg-" + defend.sha("kept-after-refusal")) is None


def test_the_artifact_is_checked_not_only_its_format(world):
    with pytest.raises(schema.Refused, match=r"a{64}.*" + world["sha"]):
        _reg(world, "art1", artifact_sha256="a" * 64)
    with pytest.raises(schema.Refused, match="code_commit"):
        _reg(world, "art2", code_commit="0" * 40)
    with pytest.raises(schema.Refused, match="artifact_path"):
        _reg(world, "art3", artifact_path="paper_platform/rules/NOPE.json")


def test_same_file_twice_writes_nothing_and_only_the_proposer_revises(world):
    s = world["store"]
    first = _reg(world, "twice", name="a.json")
    again = _reg(world, "twice", name="a.json")
    assert first["new"] >= 1 and again["new"] == 0 and again["revised"] == 0
    cid = first["claim"]
    with pytest.raises(schema.Refused, match="only run:0002 may revise"):
        _reg(world, "twice", run=REVIEWER, scope="SCOPE-TEXT changed by another run", name="b.json")
    nxt = _reg(world, "twice", scope="SCOPE-TEXT changed", name="c.json")
    assert nxt["revised"] == 1 and s.node(cid)["rev"] == 2 and len(s.history(cid)) == 2
    shown = defend.show(s, cid)
    assert shown.count("revision 1, written") == 1 and shown.count("revision 2, written") == 1


def test_a_revision_that_drops_a_ground_withdraws_its_link(world):
    s = world["store"]
    cid = _reg(world, "drops", name="d1.json")["claim"]
    live = lambda: {(e["type"], e["src"], e["dst"]) for e in s.edges()}
    assert ("DERIVED_FROM", cid, CLAIM_ID) in live()
    only_rule = [g for g in _claim(world)["rests_on"] if g["kind"] == "rule"]
    r = _reg(world, "drops", rests_on=only_rule, name="d2.json")
    assert r["withdrawn"] and ("DERIVED_FROM", cid, CLAIM_ID) not in live()
    cited_edges = [e for e in s.edges(withdrawn=True) if e["type"] == "SUPPORTS" and e["dst"] == cid and e["attrs"].get("withdrawn")]
    assert cited_edges and all(e["attrs"]["withdrawn_reason"] for e in cited_edges)
    assert s.history(r["withdrawn"][0])          # the earlier line is kept


def test_the_brief_holds_the_claim_and_grounds_and_not_the_proposers_reasoning(world):
    s = world["store"]
    cid = _reg(world, "briefed", reasoning_files=["notes/proposer-notes.md"], inference=False)["claim"]
    b = defend.brief(s, cid)
    for k in ("EXACT-CLAIM-TEXT", "SCOPE-TEXT", "BOUNDARIES-TEXT", "HYPOTHESIS-TEXT", world["spec"], world["commit"],
              s.node(CLAIM_ID)["attrs"]["text"], CITED_QUOTE, "said by Claude as the proposer states; code does not check who said it", world["sha"],
              "notes/proposer-notes.md", "defend show"):
        assert k in b, k
    assert "Greg's words" not in b
    assert json.loads(subprocess.run(["git", "-C", str(world["root"].parent / "paper-trading-platform"), "show",
                                      f"{world['commit']}:paper_platform/rules/CL01.json"], capture_output=True, text=True).stdout
                      )["specification"] in b                       # the artifact's own text at its commit
    for k in (MECH, ALT, FALS, "OUTCOME-TEXT", "the decider's stored decisions"):
        assert k not in b, k
    low = b.lower()
    assert "no verdict word" in low and "distinguishing_observation" in low and "saw_proposer_reasoning" in low
    out = world["tmp"] / "brief-cli.md"
    assert defend.main(["challenge-brief", "--claim", cid, "--out", str(out), "--data", str(world["root"]),
                        "--graph-dir", str(world["graph"])]) == 0
    assert out.read_text(encoding="utf-8") == b


CLAUDE_MD_QUOTE = "standing rules (Greg, 2026-09-16) -- MEMORY, read before touching Granite"


def _claude_md_ground(said_by):
    return {"kind": "cited", "repo": "Markets", "path": "CLAUDE.md", "line_start": 32, "line_end": 32,
            "quote": CLAUDE_MD_QUOTE, "said_by": said_by}


def test_who_said_a_cited_line_is_the_proposers_word_and_code_says_so(world):
    s = world["store"]
    rest = [g for g in _claim(world)["rests_on"] if g["kind"] != "cited"] + [_claude_md_ground("Greg"), _claim(world)["rests_on"][2]]
    cid = _reg(world, "greg-seen", rests_on=rest, name="gs.json",
               outcome_visibility={"outcome_seen": True, "what": "SEEN-TEXT the four trade days were studied first"})["claim"]
    by_path = {g["path"]: g for g in s.node(cid)["attrs"]["rests_on"] if g["kind"] == "cited"}
    assert by_path["CLAUDE.md"]["said_by_named_in_lines"] is True       # line 32 of CLAUDE.md reads "(Greg, 2026-09-16)"
    assert by_path[HANDOFF]["said_by_named_in_lines"] is False          # line 3 of the handoff does not hold "Claude"
    line = "registered after an outcome was seen: SEEN-TEXT the four trade days were studied first"
    g = by_path["CLAUDE.md"]
    for text in (defend.brief(s, cid), defend.show(s, cid)):
        assert "Greg's words" not in text and line in text
        for k in ("CLAUDE.md", g["commit"], g["sha256"], "said by Greg as the proposer states; code does not check who said it"):
            assert k in text, k
        assert "appears in the cited lines: true" in text and "appears in the cited lines: false" in text


def test_a_complete_challenge_is_an_evaluation_tied_to_the_claim(world):
    s = world["store"]
    cid = _reg(world, "challenged")["claim"]
    assert any(cid in l for l in defend.undefended(s))
    r = _challenge(world, cid)
    ev = s.node(r["evaluation"])
    a = ev["attrs"]
    assert ev["type"] == "Evaluation" and a["rubric"] == defend.RUBRIC and defend.RUBRIC.startswith("independent challenge v1: ")
    for k in ("what_was_checked", "what_was_observed", "what_remains_open", "reviewer", "alternatives", "falsifiers",
              "distinguishing_observation", "claim_revision", "input_hash", "expected_observation", "what_i_opened"):
        assert a[k]
    assert a["brief_sha256"] == hashlib.sha256(_brief_file(world, cid).read_bytes()).hexdigest()
    assert a["saw_proposer_reasoning"] is False and a["challenge_file"] == _chal() and a["reviewer"] == REVIEWER
    assert any(e["type"] == "EVALUATES" and e["src"] == ev["id"] and e["dst"] == cid for e in s.edges())
    assert not any(cid in l for l in defend.undefended(s))
    assert ev["id"] in defend.show(s, cid) and "whether the next session used it" in defend.show(s, cid)
    assert _challenge(world, cid)["new"] == 0                            # the same challenge twice writes nothing
    _reg(world, "challenged", scope="SCOPE-TEXT changed again", name="h.json")
    assert any(cid in l for l in defend.undefended(s))


@pytest.mark.parametrize("over,field", [
    ({"alternatives": []}, "alternatives"), ({"falsifiers": []}, "falsifiers"),
    ({"distinguishing_observation": ""}, "distinguishing_observation"), ({"what_remains_open": []}, "what_remains_open"),
    ({"saw_proposer_reasoning": "no"}, "saw_proposer_reasoning"), ({"extra_note": "x"}, "extra_note"),
])
def test_a_challenge_without_its_parts_is_refused(world, over, field):
    cid = _reg(world, "needs-three")["claim"]
    with pytest.raises(schema.Refused, match=field):
        _challenge(world, cid, **over)


def test_who_may_challenge(world):
    s = world["store"]
    cid = _reg(world, "who")["claim"]
    with pytest.raises(schema.Refused, match="sole verifier"):
        _challenge(world, cid, run=PROPOSER)
    with pytest.raises(schema.Refused, match="role"):
        _challenge(world, cid, run=SCOUT)
    with pytest.raises(schema.Refused, match="AgentRun"):
        _challenge(world, cid, run="run:9999")
    with pytest.raises(schema.Refused, match="--brief"):
        defend.challenge(s, cid, _w(world, _chal()), REVIEWER, None)
    other = _reg(world, "other-claim", name="o.json")["claim"]
    with pytest.raises(schema.Refused, match="not the brief"):
        defend.challenge(s, cid, _w(world, _chal()), REVIEWER, _brief_file(world, other))
    # a reviewer run that made a ground of the claim is refused
    ground = _reg(world, "ground-by-reviewer", run=REVIEWER, name="gr.json")["claim"]
    mine = _reg(world, "rests-on-reviewers", name="rr.json", rests_on=_claim(world)["rests_on"] + [{"kind": "claim", "id": ground}])["claim"]
    with pytest.raises(schema.Refused, match="made the ground claim"):
        _challenge(world, mine, run=REVIEWER)
    assert _challenge(world, mine, run=REVIEWER2, name="c2.json")["new"] >= 1


def test_verdict_labels_are_refused_and_ordinary_words_are_not(world):
    cid = _reg(world, "labels")["claim"]
    # the plan's six labels, anywhere in a sentence, in any letter case, with underscores or spaces
    for text in ("the claim is SUPPORTED_WITHIN_SCOPE", "REFUTED_WITH_EVIDENCE here", "it is inconclusive",
                 "supported within scope, said the note", "so it Needs More Evidence", "blocked_input_scope", "Superseded retained"):
        with pytest.raises(schema.Refused, match=r"what_remains_open.*carries the word"):
            _challenge(world, cid, what_remains_open=[text])
    # a field whose WHOLE value is one plain form
    for text in ("verdict", "passed", "FAILED", "pass", "fail", "pass/fail", "proven", "Disproven", "approved", "rejected"):
        with pytest.raises(schema.Refused, match=r"what_remains_open.*carries the word"):
            _challenge(world, cid, what_remains_open=[text])
    with pytest.raises(schema.Refused, match=r"mechanism.*carries the word"):
        _reg(world, "labels3", mechanism="rejected")
    # an ordinary sentence or a file name that holds one of the plain words is accepted
    honest = "the statement is true on the stored lines, it holds there, false elsewhere; ok"
    assert _challenge(world, cid, what_remains_open=[honest], name="honest.json")["new"] >= 1
    for i, text in enumerate(("orders rejected by the exchange appear", "after the settle window passed", "a verdict follows",
                              "the check passed", "it failed", "the runs that failed to start are logged")):
        assert _challenge(world, cid, what_remains_open=[text], name=f"ord{i}.json")["new"] >= 1
    assert _challenge(world, cid, what_i_opened=["out/verdict.json"], name="fn.json")["new"] >= 1
    assert _reg(world, "labels2", mechanism="the rule was rejected by the book")["new"] >= 1


def test_a_reviewer_who_made_a_ground_of_a_ground_is_refused(world):
    far = _reg(world, "far-ground", run=REVIEWER, name="fg.json")["claim"]
    mid = _reg(world, "mid-ground", name="mg.json", rests_on=_claim(world)["rests_on"] + [{"kind": "claim", "id": far}])["claim"]
    top = _reg(world, "top-claim", name="tp.json", rests_on=_claim(world)["rests_on"] + [{"kind": "claim", "id": mid}])["claim"]
    with pytest.raises(schema.Refused, match="made the ground claim"):
        _challenge(world, top, run=REVIEWER, name="far.json")
    assert _challenge(world, top, run=REVIEWER2, name="far2.json")["new"] >= 1


def test_the_role_must_be_exactly_reviewer(world):
    s = world["store"]
    near = [n["id"] for n in s.nodes("AgentRun") if n["attrs"].get("role", "").strip().lower() != "reviewer"
            and "reviewer" in n["attrs"].get("role", "").lower()]
    if not near:
        pytest.skip("no real run in this graph holds a role that only contains the word reviewer")
    cid = _reg(world, "exact-role")["claim"]
    with pytest.raises(schema.Refused, match="role"):
        _challenge(world, cid, run=near[0], name="near.json")


def test_the_brief_is_sealed_to_what_the_code_builds(world):
    s = world["store"]
    cid = _reg(world, "sealed", reasoning_files=["notes/proposer-notes.md"])["claim"]
    rev = s.node(cid)["rev"]
    forged = world["tmp"] / "forged-brief.md"
    forged.write_text(f"# Challenge brief for {cid} (revision {rev})\n\nmechanism: {MECH}\n", encoding="utf-8")
    with pytest.raises(schema.Refused, match="not the brief"):
        defend.challenge(s, cid, _w(world, _chal(), "sealed-c.json"), REVIEWER, forged)
    real = _brief_file(world, cid)
    padded = world["tmp"] / "padded-brief.md"
    padded.write_bytes(real.read_bytes() + b"\nmechanism: " + MECH.encode() + b"\n")
    with pytest.raises(schema.Refused, match="not the brief"):
        defend.challenge(s, cid, _w(world, _chal(), "sealed-c.json"), REVIEWER, padded)
    r = defend.challenge(s, cid, _w(world, _chal(), "sealed-c.json"), REVIEWER, real)
    assert s.node(r["evaluation"])["attrs"]["brief_sha256"] == hashlib.sha256(defend.brief(s, cid).encode("utf-8")).hexdigest()
    b = defend.brief(s, cid)
    assert "notes/proposer-notes.md" in b and "printed in full" in b and "thing claimed about" in b


def test_an_artifact_listed_among_the_reasoning_files_is_refused(world):
    with pytest.raises(schema.Refused, match="reasoning_files"):
        _reg(world, "art-is-reasoning", reasoning_files=["notes/x.md", "paper_platform/rules/CL01.json"])
    assert world["store"].node("claim:reg-" + defend.sha("art-is-reasoning")) is None


def test_a_revision_that_changes_the_falsifiers_says_so_everywhere(world):
    s = world["store"]
    cid = _reg(world, "fchange", name="fc1.json")["claim"]
    assert "falsifiers_changed_from_revision" not in s.node(cid)["attrs"]
    new_f = [{"observation": "FALS2-TEXT a different observation", "record": "the decider's stored decisions"}]
    r = _reg(world, "fchange", falsifiers=new_f, name="fc2.json")
    c = s.node(cid)
    assert r["revised"] == 1 and c["rev"] == 2 and c["attrs"]["falsifiers_changed_from_revision"] == 1
    words = "the falsifiers were changed in this revision from those of revision 1"
    assert words in defend.brief(s, cid) and words in defend.show(s, cid)
    assert "FALS2-TEXT" not in defend.brief(s, cid)                       # the text itself stays out of the brief
    assert any(cid in l and words in l for l in defend.undefended(s))
    again = _reg(world, "fchange", falsifiers=new_f, name="fc2.json")      # the same revised file, again: nothing new
    assert again["new"] == 0 and again["revised"] == 0 and s.node(cid)["rev"] == 2
    assert s.node(cid)["attrs"]["falsifiers_changed_from_revision"] == 1
    _reg(world, "fchange", falsifiers=new_f, scope="SCOPE-TEXT changed after", name="fc3.json")
    assert "falsifiers_changed_from_revision" not in s.node(cid)["attrs"]  # revision 3 did not change them


def test_a_revision_leaves_standing_a_link_another_run_wrote_into_the_claim(world):
    s = world["store"]
    cid = _reg(world, "others-link", name="ol1.json")["claim"]
    other_src = f"src:markets-data:{PAPER}/agent-runs.jsonl"      # a real Source of the graph that is not one of the claim's grounds
    assert s.node(other_src) and other_src not in [g.get("source") for g in s.node(cid)["attrs"]["rests_on"]]
    mine = defend.link("SUPPORTS", other_src, cid)
    s.write([], [mine], written_by=REVIEWER)
    only_rule = [g for g in _claim(world)["rests_on"] if g["kind"] == "rule"]
    r = _reg(world, "others-link", rests_on=only_rule, name="ol2.json")      # the proposer drops two of its own grounds
    live = {e["id"] for e in s.edges()}
    assert r["withdrawn"] and mine["id"] in live and mine["id"] not in r["withdrawn"]
    assert len(s.history(mine["id"])) == 1 and not s.history(mine["id"])[0]["attrs"].get("withdrawn")


def _item(world, **over):
    d = {"what": "the text of rule CL01", "sha256": world["sha"], "repo": "paper-trading-platform",
         "path": "paper_platform/rules/CL01.json", "commit": world["commit"]}
    d.update(over)
    return d


def test_a_data_manifest_item_is_checked_against_the_file_at_its_commit(world):
    s = world["store"]
    ok = _reg(world, "man-ok", data_manifest_hashes=[_item(world)], name="man1.json")["claim"]
    assert s.node(ok)["attrs"]["data_manifest_hashes"] == [_item(world)]
    with pytest.raises(schema.Refused, match=r"data_manifest_hashes.*" + "a" * 64 + r".*" + world["sha"]):
        _reg(world, "man-bad", data_manifest_hashes=[_item(world, sha256="a" * 64)], name="man2.json")
    with pytest.raises(schema.Refused, match="data_manifest_hashes.*commit"):
        _reg(world, "man-bad", data_manifest_hashes=[_item(world, commit="0" * 40)], name="man3.json")
    with pytest.raises(schema.Refused, match="data_manifest_hashes.*path"):
        _reg(world, "man-bad", data_manifest_hashes=[_item(world, path="paper_platform/rules/NOPE.json")], name="man4.json")
    with pytest.raises(schema.Refused, match="data_manifest_hashes.*repo"):
        _reg(world, "man-bad", data_manifest_hashes=[_item(world, repo="nowhere")], name="man5.json")
    with pytest.raises(schema.Refused, match="data_manifest_hashes"):
        _reg(world, "man-bad", data_manifest_hashes=[{"what": "x", "sha256": world["sha"]}], name="man6.json")
    assert world["store"].node("claim:reg-" + defend.sha("man-bad")) is None


def _cli(world, verb, *args):
    return defend.main([verb, *args, "--data", str(world["root"]), "--graph-dir", str(world["graph"])])


def _fresh_tasks(world):
    return GraphStore(world["root"], graph_dir=world["graph"]).nodes("Task")


def test_a_refused_challenge_leaves_a_task_and_no_evaluation(world, capsys):
    s = world["store"]
    cid = _reg(world, "chal-refused")["claim"]
    n0, e0 = len(s.nodes("Task")), len(s.nodes("Evaluation"))
    with pytest.raises(schema.Refused, match="sole verifier"):
        _challenge(world, cid, run=PROPOSER, name="cr.json")
    assert len(s.nodes("Task")) == n0 + 1 and len(s.nodes("Evaluation")) == e0
    t = [t for t in s.nodes("Task") if t["attrs"].get("claim") == cid and t["attrs"].get("verb") == "challenge"][0]["attrs"]
    assert "sole verifier" in t["reason"] and t["run"] == PROPOSER and t["challenge_file"]["alternatives"] and t["refused_at"]
    assert t["text"].startswith("not admissible for a check: ") and t["state"] == "blocked"
    # the same through the command line: exit code 2, and the refusal was retained
    n1 = len(_fresh_tasks(world))
    assert _cli(world, "challenge", "--claim", cid, "--file", str(_w(world, _chal(), "cr2.json")), "--run", PROPOSER,
                "--brief", str(_brief_file(world, cid))) == 2
    assert "sole verifier" in capsys.readouterr().err and len(_fresh_tasks(world)) == n1 + 1


def test_a_refused_challenge_brief_leaves_a_task(world, capsys):
    n0 = len(_fresh_tasks(world))
    out = world["tmp"] / "nobrief.md"
    assert _cli(world, "challenge-brief", "--claim", "claim:does-not-exist", "--out", str(out), "--run", REVIEWER) == 2
    fresh = _fresh_tasks(world)
    assert len(fresh) == n0 + 1 and not out.exists()
    t = [t for t in fresh if t["attrs"].get("verb") == "challenge-brief"][0]["attrs"]
    assert t["claim"] == "claim:does-not-exist" and "registered" in t["reason"] and t["run"] == REVIEWER


def test_a_refusal_that_cannot_be_written_says_both_reasons_and_exits_3(world, capsys, monkeypatch):
    f = _w(world, _claim(world, "unwritable", mechanism=""), "uw.json")
    n0 = len(_fresh_tasks(world))
    assert _cli(world, "register", "--claim-file", str(f), "--run", PROPOSER) == 2          # retained: exit code 2
    assert len(_fresh_tasks(world)) == n0 + 1
    capsys.readouterr()
    orig = GraphStore.write

    def failing(self, nodes, edges, **kw):
        if any(n["type"] == "Task" for n in nodes):
            raise schema.Refused("PENDING-FILE-LEFT-OVER the graph will not take this write")
        return orig(self, nodes, edges, **kw)
    monkeypatch.setattr(GraphStore, "write", failing)
    assert _cli(world, "register", "--claim-file", str(f), "--run", PROPOSER) == 3
    err = capsys.readouterr().err
    assert "mechanism" in err and "PENDING-FILE-LEFT-OVER" in err
    monkeypatch.undo()
    assert len(_fresh_tasks(world)) == n0 + 1          # nothing was written the second time


def test_registration_never_writes_a_new_revision_of_an_existing_source(world):
    s = world["store"]
    sid = "src:Markets:.claude/agents/scout.md"          # a real Source of the graph; the committed file has changed since
    before = s.history(sid)
    cited = {"kind": "cited", "repo": "Markets", "path": ".claude/agents/scout.md", "line_start": 8, "line_end": 8,
             "quote": "You are the scout for DavisAI Markets", "said_by": "Claude"}
    now_bytes = subprocess.run(["git", "-C", str(repo_dirs(world["root"], None, None)["Markets"]), "show",
                                "HEAD:.claude/agents/scout.md"], capture_output=True).stdout
    assert before and before[-1]["attrs"]["sha256"] != hashlib.sha256(now_bytes).hexdigest()       # the condition holds
    rule = [g for g in _claim(world)["rests_on"] if g["kind"] == "rule"]
    cid = _reg(world, "source-stays", rests_on=rule + [cited], name="ss.json")["claim"]
    assert s.history(sid) == before                      # the existing Source is left exactly as it was
    g = [g for g in s.node(cid)["attrs"]["rests_on"] if g["kind"] == "cited"][0]
    assert g["sha256"] == hashlib.sha256(now_bytes).hexdigest() and g["commit"] and g["source"] == sid
    e = [e for e in s.edges("SUPPORTS") if e["src"] == sid and e["dst"] == cid][0]
    assert e["attrs"]["commit"] == g["commit"] and e["attrs"]["sha256"] == g["sha256"]
    r = [g for g in s.node(cid)["attrs"]["rests_on"] if g["kind"] == "rule"][0]
    er = [e for e in s.edges("SUPPORTS") if e["src"] == r["source"] and e["dst"] == cid][0]
    assert er["attrs"]["commit"] == r["commit"] and er["attrs"]["sha256"] == r["sha256"]


def test_an_inference_that_names_nothing_it_rests_on_is_refused(world):
    with pytest.raises(schema.Refused, match=r"rests_on.*inference"):
        _reg(world, "inf-empty", inference=True, inference_reason="INFERENCE-TEXT a reading", rests_on=[])
    assert world["store"].node("claim:reg-" + defend.sha("inf-empty")) is None


def test_a_claim_carries_no_dead_unlinked_grounds_field(world):
    cid = _reg(world, "t1")["claim"]
    assert "unlinked_grounds" not in world["store"].node(cid)["attrs"]
    assert "NO LINK" not in defend.show(world["store"], cid)


def test_the_store_checks_no_worse_after_the_writes(world):
    after = sorted(GraphStore(world["root"], graph_dir=world["graph"], tolerant=True).check_all())
    assert [b for b in after if b not in world["before"]] == []
