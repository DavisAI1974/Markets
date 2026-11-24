"""Ticket 46, consolidation as a standing step of every read: the brief of candidate pairs for one read's
claims, the pairs applied one link each, the count of what has been through the step, the take-back of a
later-over-earlier link, and the date fault that must not return.

Every check works on a scratch copy of the REAL graph of the markets-data checkout (the nodes and links
only, copied to a scratch folder); nothing is written into markets-data and no claim is made up. The one
case the real graph does not hold (a refusal, a claim added after the last pass) sits apart at the foot of
the file."""

import json
import re
import shutil

import pytest

from tools.kgraph import consolidate, resolve, schema
from tools.kgraph.extract import repo_dirs
from tools.kgraph.store import GraphStore

from .realrecords import data_root

# THE DATE FAULT (ticket 46, second box). Both claims sit in a folder named family-research-20261022/
# and carry no said_on, so the date comes from the FILE's own name.
NEW_1124 = "claim:eeeda142ddb2"      # NEXT_SESSION_HANDOFF_20261124X.md line 4: file date 2026-11-24, folder date 2022-10-22
OLD_1123 = "claim:69e43c1bcaf7"      # NEXT_SESSION_HANDOFF_20261123U.md line 3: file date 2026-11-23, same folder
FOLDER_DATE, FILE_DATES = "20261022", ("20261124", "20261123")
READ = "run:0022"                   # a real read of the graph (256 claims); 9 of the 32 hand-made links of run 96 rest on it
SMALL_READ = "run:0023"             # a real read; 1 of the hand-made links rests on it
APPLIER = "run:0096"                # a real AgentRun of the graph
HAND_PAIRS = "graph/reads/run-0096-consolidate-pairs.json"


@pytest.fixture()
def scratch(tmp_path):
    root = data_root()
    g = tmp_path / "graph"
    shutil.copytree(root / "graph", g, ignore=shutil.ignore_patterns("reads", "reviews", "merges", "evaluations", "MANIFEST.json"))
    return root, g


def run_cmd(mod, root, g, *argv):
    return mod.main(["--data", str(root), "--graph-dir", str(g), *argv])


def hand_pairs(root, read):
    p = root / HAND_PAIRS
    if not p.exists():
        pytest.skip(f"{HAND_PAIRS} is not in this markets-data checkout")
    store = GraphStore(root)
    return [x for x in json.loads(p.read_text(encoding="utf-8"))["pairs"] if store.node(x["new"])["attrs"]["extracted_by"] == read]


def take_back_hand_links(root, g, pairs, capsys):
    """Take back, on the scratch copy, the real links of run 96 that rest on the chosen read, so the pass can be made again."""
    store = GraphStore(root, graph_dir=g)
    by = {(e["src"], e["dst"]): e["id"] for e in store.edges("SUPERSEDES")}
    for x in pairs:
        run_cmd(resolve, root, g, "undo", "--edge", by[(x["new"], x["old"])], "--reason", "the pass is made again on a scratch copy", "--run", APPLIER)
    capsys.readouterr()


def brief_pairs(text):
    """The pairs of a brief: (later id, later date, earlier id, earlier date, [shared entity ids], section)."""
    out, section = [], None
    for blk in re.split(r"\n(?=### pair )", text)[1:]:
        later = re.search(r"^(?:later|one): (claim:\w+) \| (\S+) \|", blk, re.M)
        earlier = re.search(r"^(?:earlier|other): (claim:\w+) \| (\S+) \|", blk, re.M)
        shared = re.findall(r" \[([^\[\]]+)\](?:; |$)", re.search(r"^shared: (.*)$", blk, re.M).group(1))
        out.append((later[1], later[2], earlier[1], earlier[2], shared))
    return out


def counts_line(out, read):
    m = re.search(rf"{read}: claims_added=(\d+) claims_with_a_candidate=(\d+) pairs=(\d+)", out)
    return tuple(int(x) for x in m.groups())


def status(root, g, capsys):
    assert run_cmd(consolidate, root, g, "status") == 0
    out = capsys.readouterr().out
    reads = {}
    for m in re.finditer(r"^(run:\w+) \| claims=(\d+) \| (through the step|not yet)", out, re.M):
        reads[m[1]] = (int(m[2]), m[3])
    c = dict(re.findall(r"(\w+)=(\d+)", out.strip().splitlines()[-1]))
    assert out.strip().splitlines()[-1].startswith("COUNTS ")
    return reads, {k: int(v) for k, v in c.items()}, out


def test_a_brief_names_only_the_reads_claims_and_every_pair_shares_an_entity_with_the_earlier_dated_earlier(scratch, capsys, tmp_path):
    root, g = scratch
    out_file = tmp_path / "brief.txt"
    assert run_cmd(consolidate, root, g, "brief", "--read", READ, "--out", str(out_file)) == 0
    printed = capsys.readouterr().out
    store = GraphStore(root, graph_dir=g)
    added = {n["id"] for n in store.nodes("Claim") if n["attrs"].get("extracted_by") == READ}
    pairs = brief_pairs(out_file.read_text(encoding="utf-8"))
    ment, canon = {}, {}
    for e in store.edges("MENTIONS"):
        if e["dst"] not in canon:
            canon[e["dst"]] = resolve.canonical(store, e["dst"])
        ment.setdefault(e["src"], set()).add(canon[e["dst"]])
    standing = {(e["src"], e["dst"]) for e in store.edges("SUPERSEDES")} | {(e["dst"], e["src"]) for e in store.edges("SUPERSEDES")}
    assert pairs
    seen = set()
    for later, ldate, earlier, edate, shared in pairs:
        assert later in added and earlier != later                          # the later side is the read's claim, only
        assert shared and set(shared) <= ment[later] & ment[earlier]       # they share a mentioned Entity
        assert (later, earlier) not in standing and (later, earlier) not in seen
        seen.add((later, earlier))
        if ldate != "undated" and edate != "undated":                      # the earlier is dated earlier
            assert edate <= ldate                                          # earlier date, or the same date (the reader orders those)
            assert resolve._when(store, store.node(earlier), None)[0] == edate and resolve._when(store, store.node(later), None)[0] == ldate
        else:                                                              # a claim with no date cannot be placed by one: it is listed, not cut
            assert "undated" in (ldate, edate)
    # every candidate is in the brief: the same rule worked out apart, claim by claim
    want = set()
    all_claims = store.nodes("Claim")
    days = {o["id"]: resolve._when(store, o, None)[0] for o in all_claims}
    for cid in added:
        a = days[cid]
        for o in all_claims:
            if o["id"] == cid or (cid, o["id"]) in standing or not (ment.get(cid, set()) & ment.get(o["id"], set())):
                continue
            b = days[o["id"]]
            if (a and b and b <= a) or not (a and b):
                want.add((cid, o["id"]))
    want = {(x, y) for (x, y) in want if not (y in added and (y, x) in want and y < x)}   # a pair of the same read both ways is listed once
    assert seen == want
    n_added, n_with, n_pairs = counts_line(printed, READ)
    assert n_added == len(added) == 256 and n_pairs == len(pairs) and n_with == len({p[0] for p in pairs})


def test_before_any_apply_every_claim_of_a_real_read_is_not_yet_and_after_apply_the_read_is_through_the_step(scratch, capsys, tmp_path):
    root, g = scratch
    reads, counts, _ = status(root, g, capsys)
    assert reads[READ] == (256, "not yet")
    assert all(v[1] == "not yet" for v in reads.values())                  # the hand pass of run 96 left no Task: not yet is what is so
    store = GraphStore(root, graph_dir=g)
    assert counts == {"claims": len(store.nodes("Claim")), "through_the_step": 0, "not_yet": len(store.nodes("Claim")),
                      "reads": len(reads), "reads_not_yet": len(reads)}
    # the pass is made again on the real pairs of run 96 that rest on this read
    pairs = hand_pairs(root, READ)
    assert len(pairs) == 9
    take_back_hand_links(root, g, pairs, capsys)
    run_cmd(consolidate, root, g, "brief", "--read", READ, "--out", str(tmp_path / "b.txt"))
    n_pairs = counts_line(capsys.readouterr().out, READ)[2]
    in_brief = {frozenset((p[0], p[2])) for p in brief_pairs((tmp_path / "b.txt").read_text(encoding="utf-8"))}   # a pair of the same read is listed once, either way round
    shares = [x for x in pairs if frozenset((x["new"], x["old"])) in in_brief]
    assert len(shares) == 3                                                 # the other 6 of the hand pass share no Entity with their earlier claim: the brief cannot reach them
    pf = tmp_path / "pairs.json"
    pf.write_text(json.dumps({"pairs": pairs}), encoding="utf-8")
    assert run_cmd(consolidate, root, g, "apply", "--read", READ, "--pairs", str(pf), "--run", APPLIER) == 0
    res = json.loads(capsys.readouterr().out)
    assert len(res["applied"]) == 9 and res["refused"] == [] and res["candidate_pairs"] == n_pairs
    store = GraphStore(root, graph_dir=g)
    for x in pairs:
        assert any(e["src"] == x["new"] and e["dst"] == x["old"] and e["attrs"]["why"] == x["why"] and e["attrs"]["made_by"] == APPLIER
                   for e in store.edges("SUPERSEDES"))
    task = store.node(res["task"])
    assert task["type"] == "Task" and task["attrs"]["state"] == "done"
    assert (task["attrs"]["read"], task["attrs"]["applied_by"], task["attrs"]["candidate_pairs"]) == (READ, APPLIER, n_pairs)
    assert (task["attrs"]["pairs_applied"], task["attrs"]["pairs_refused"]) == (9, 0)
    assert store.check_all() == []
    reads, counts, out = status(root, g, capsys)
    assert reads[READ] == (256, "through the step") and sum(1 for v in reads.values() if v[1] == "not yet") == len(reads) - 1
    assert counts["through_the_step"] == 256 and counts["not_yet"] == counts["claims"] - 256
    assert counts["reads_not_yet"] == counts["reads"] - 1


def test_an_empty_pairs_file_is_a_real_answer_and_the_read_is_through_the_step(scratch, capsys, tmp_path):
    root, g = scratch
    pf = tmp_path / "none.json"
    pf.write_text(json.dumps({"pairs": []}), encoding="utf-8")
    before = len(GraphStore(root, graph_dir=g).edges("SUPERSEDES"))
    assert run_cmd(consolidate, root, g, "apply", "--read", SMALL_READ, "--pairs", str(pf), "--run", APPLIER) == 0
    res = json.loads(capsys.readouterr().out)
    assert res["applied"] == [] and res["refused"] == []
    store = GraphStore(root, graph_dir=g)
    assert len(store.edges("SUPERSEDES")) == before
    reads, counts, _ = status(root, g, capsys)
    assert reads[SMALL_READ] == (150, "through the step") and counts["through_the_step"] == 150


def test_undo_takes_back_a_later_over_earlier_link_and_it_stays_on_record_as_withdrawn(scratch, capsys):
    root, g = scratch
    before = {e["id"] for e in GraphStore(root, graph_dir=g).edges("SUPERSEDES")}
    run_cmd(resolve, root, g, "supersede", "--new", NEW_1124, "--old", OLD_1123, "--why", "check of the take-back", "--run", "code:test")
    eid = capsys.readouterr().out.strip().splitlines()[-1]
    store = GraphStore(root, graph_dir=g)
    assert eid.startswith("e:") and eid not in before and eid in {e["id"] for e in store.edges("SUPERSEDES")}
    run_cmd(resolve, root, g, "undo", "--edge", eid, "--reason", "the check takes it back", "--run", "run:0096")
    store = GraphStore(root, graph_dir=g)
    assert eid not in {e["id"] for e in store.edges("SUPERSEDES")}
    on_record = {e["id"]: e for e in store.edges("SUPERSEDES", withdrawn=True)}[eid]
    assert on_record["attrs"]["withdrawn"] is True and "the check takes it back" in on_record["attrs"]["withdrawn_reason"]
    assert "run:0096" in on_record["attrs"]["withdrawn_reason"]
    assert on_record["attrs"]["why"] == "check of the take-back" and on_record["attrs"]["made_by"] == "code:test"
    assert len(store.history(eid)) == 2                                       # the first line stays
    # any other kind of link is still refused
    mention = store.edges("MENTIONS")[0]["id"]
    with pytest.raises(schema.Refused):
        resolve.undo(store, mention, "no", "run:0096")


def test_the_date_fault_cannot_return_supersede_reads_the_files_date_not_the_folders(scratch, capsys):
    root, g = scratch
    store = GraphStore(root, graph_dir=g)
    for cid, fdate in ((NEW_1124, FILE_DATES[0]), (OLD_1123, FILE_DATES[1])):
        a = store.node(cid)["attrs"]
        assert not a.get("said_on")
        folder, name = a["source"].rsplit("/", 1)
        assert FOLDER_DATE in folder and fdate in name and FOLDER_DATE not in name
    assert resolve._when(store, store.node(NEW_1124), None)[0] == "2026-11-24"
    assert resolve._when(store, store.node(OLD_1123), None)[0] == "2026-11-23"
    # the true pair (2026-11-24 over 2026-11-23) is taken; read by the folder it would have been refused (2026-10-22)
    assert run_cmd(resolve, root, g, "supersede", "--new", NEW_1124, "--old", OLD_1123, "--why", "date check", "--run", "code:test") == 0
    # and the wrong way round is refused for its dates, so the dates really are compared
    with pytest.raises(schema.Refused, match="2026-11-23 against 2026-11-24"):
        resolve.supersede(store, OLD_1123, NEW_1124, "date check", "code:test")


# ==== CASES THE REAL GRAPH DOES NOT HOLD (each a real node or line with exactly the named thing changed) ====

def test_a_pair_supersede_refuses_is_printed_and_counted_never_dropped_and_a_second_apply_is_refused(scratch, capsys, tmp_path):
    root, g = scratch
    real = hand_pairs(root, SMALL_READ)[0]
    take_back_hand_links(root, g, [real], capsys)
    # change: the real pair of run 96 with its two claims turned the other way round (the earlier set over the later)
    turned = {"new": real["old"], "old": real["new"], "why": "the earlier claim set over the later one"}
    pf = tmp_path / "pairs.json"
    pf.write_text(json.dumps({"pairs": [turned, real]}), encoding="utf-8")   # turned first: refused as not of the read, printed and counted
    assert run_cmd(consolidate, root, g, "apply", "--read", SMALL_READ, "--pairs", str(pf), "--run", APPLIER) == 0
    res = json.loads(capsys.readouterr().out)
    assert len(res["applied"]) == 1 and len(res["refused"]) == 1
    assert res["refused"][0]["new"] == turned["new"] and "is not one of the claims of" in res["refused"][0]["refusal"]   # the turned pair's later claim is of run:0032, not of the read: refused by point 2 of ticket 46; the date refusal itself is held by the check of OLD_1123 over NEW_1124 above
    task = GraphStore(root, graph_dir=g).node(res["task"])
    assert (task["attrs"]["pairs_applied"], task["attrs"]["pairs_refused"]) == (1, 1)
    with pytest.raises(schema.Refused, match="already been through the step"):
        consolidate.apply(GraphStore(root, graph_dir=g), SMALL_READ, [real], APPLIER)


def test_a_claim_added_after_the_last_pass_is_listed_as_not_yet(scratch, capsys, tmp_path):
    root, g = scratch
    pf = tmp_path / "none.json"
    pf.write_text(json.dumps({"pairs": []}), encoding="utf-8")
    run_cmd(consolidate, root, g, "apply", "--read", SMALL_READ, "--pairs", str(pf), "--run", APPLIER)
    capsys.readouterr()
    store = GraphStore(root, graph_dir=g)
    real = store.node("claim:eeeda142ddb2")
    # change: a copy of this real claim with a new id and `extracted_by` a read made after the pass ("run:0099")
    added = {"id": "claim:ffffffffffff", "type": "Claim", "attrs": dict(real["attrs"], extracted_by="run:0099")}
    supports = {"id": "e:ffffffffffff", "type": "SUPPORTS", "src": real["attrs"]["source"], "dst": added["id"], "attrs": {}}   # as its source's link to the real claim
    store.write([added], [supports], written_by="code:test")
    reads, counts, out = status(root, g, capsys)
    assert reads["run:0099"] == (1, "not yet") and reads[SMALL_READ] == (150, "through the step")
    assert counts["through_the_step"] == 150 and counts["not_yet"] == counts["claims"] - 150
    assert counts["reads_not_yet"] == counts["reads"] - 1


# ==== TICKET 46, THE REVIEWER'S READ (run 202), POINT 1: A PAIR AND ITS REVERSE ARE NEVER BOTH APPLIED ====
SAME_FILE_LATER, SAME_FILE_EARLIER = "claim:01bf69899b10", "claim:a33d8b40772c"   # ROOT_GAMEPLAN_DECISIONS.md:6143 and :6048, same date, same commit, both of run:0022


def test_a_pair_and_its_reverse_are_never_both_applied(scratch, capsys, tmp_path):
    root, g = scratch
    dirs = repo_dirs(root, None, None)
    first = resolve.supersede(GraphStore(root, graph_dir=g), SAME_FILE_LATER, SAME_FILE_EARLIER, "line 6143 settles line 6048", "code:test", dirs)
    with pytest.raises(schema.Refused, match=re.escape(first)):
        resolve.supersede(GraphStore(root, graph_dir=g), SAME_FILE_EARLIER, SAME_FILE_LATER, "the turned pair", "code:test", dirs)
    # and through apply: the reverse is printed with the refusal and counted
    pf = tmp_path / "pairs.json"
    pf.write_text(json.dumps({"pairs": [{"new": SAME_FILE_EARLIER, "old": SAME_FILE_LATER, "why": "the turned pair"}]}), encoding="utf-8")
    assert run_cmd(consolidate, root, g, "apply", "--read", READ, "--pairs", str(pf), "--run", APPLIER) == 0
    res = json.loads(capsys.readouterr().out)
    assert res["applied"] == [] and len(res["refused"]) == 1 and first in res["refused"][0]["refusal"]
    standing = {(e["src"], e["dst"]) for e in GraphStore(root, graph_dir=g).edges("SUPERSEDES")}
    assert (SAME_FILE_LATER, SAME_FILE_EARLIER) in standing and (SAME_FILE_EARLIER, SAME_FILE_LATER) not in standing


def test_the_brief_lists_a_pair_of_the_same_read_once_not_both_ways(scratch, capsys, tmp_path):
    root, g = scratch
    out_file = tmp_path / "brief.txt"
    run_cmd(consolidate, root, g, "brief", "--read", READ, "--out", str(out_file))
    text = out_file.read_text(encoding="utf-8")
    pairs = brief_pairs(text)
    ids = [(p[0], p[2]) for p in pairs]
    assert len(set(ids)) == len(ids) and not any((e, l) in set(ids) for l, e in ids)
    assert "order not settled by date: the reader says which is later, from the words" in text
    assert any(re.search(r"^one: " + re.escape(l), text, re.M) for l, e in ids)


# ==== POINT 2: apply TAKES ONLY PAIRS WHOSE LATER CLAIM IS ONE OF THE READ'S OWN ====
OTHER_READ_CLAIM = "claim:6c0b6129f869"   # a real claim of run:0092 (ROOT_GAMEPLAN_DECISIONS.md), offered below with --read run:0022


def test_apply_refuses_a_pair_whose_later_claim_is_not_of_the_read(scratch, capsys, tmp_path):
    root, g = scratch
    store = GraphStore(root, graph_dir=g)
    assert store.node(OTHER_READ_CLAIM)["attrs"]["extracted_by"] == "run:0092" and store.node(SAME_FILE_EARLIER)["attrs"]["extracted_by"] == READ
    pf = tmp_path / "pairs.json"
    pf.write_text(json.dumps({"pairs": [{"new": OTHER_READ_CLAIM, "old": SAME_FILE_EARLIER, "why": "a pair of run:0092 offered with the read run:0022"}]}), encoding="utf-8")
    assert run_cmd(consolidate, root, g, "apply", "--read", READ, "--pairs", str(pf), "--run", APPLIER) == 0
    res = json.loads(capsys.readouterr().out)
    assert res["applied"] == [] and len(res["refused"]) == 1
    assert "run:0092" in res["refused"][0]["refusal"] and READ in res["refused"][0]["refusal"]
    assert not [e for e in GraphStore(root, graph_dir=g).edges("SUPERSEDES") if e["src"] == OTHER_READ_CLAIM]
    task = GraphStore(root, graph_dir=g).node(res["task"])
    assert (task["attrs"]["pairs_applied"], task["attrs"]["pairs_refused"]) == (0, 1)
