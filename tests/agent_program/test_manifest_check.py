"""Checks of the manifest check (tools/kgraph/manifest_check.py), through its public command.

Real cases read the real history of a markets-data checkout (set MARKETS_DATA). Expected values are
literals read with `git show --stat`, `git diff --name-status`, `git ls-tree -l` and `sha256sum`,
not with the command's own git calls. The cases the real history does not hold are in ONE separated
section at the foot of this file.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from tests.agent_program.realrecords import PAPER
from tools.kgraph.manifest_check import main
from tools.kgraph.store import markets_data_root


def _root():
    try:
        root = markets_data_root()
    except FileNotFoundError as e:
        pytest.skip(f"no markets-data checkout: {e}")
    return root


def _needs(root, *commits):
    for c in commits:
        r = subprocess.run(["git", "-C", str(root), "cat-file", "-e", c + "^{commit}"], capture_output=True)
        if r.returncode:
            pytest.skip(f"this markets-data checkout does not hold commit {c}")


def _run(capsys, data, rng):
    code = main(["--data", str(data), "--range", rng])
    return code, capsys.readouterr().out.splitlines()


def _counts(lines):
    last = lines[-1]
    assert last.startswith("COUNTS ")
    return dict(kv.split("=") for kv in last.split()[1:])


# ---- real cases ----

def test_d70527a_five_run_plans_added_no_manifest_holds_them(capsys):
    # markets-data d70527a (`git show --stat`): added run-0157.json .. run-0161.json under PAPER/run-plans/;
    # `git diff --name-status d70527a^ d70527a` shows 5 A lines and nothing else; none of the 14 manifests at
    # d70527a names any of them (grep of each manifest at d70527a: 0 hits).
    root = _root()
    _needs(root, "d70527a")
    code, out = _run(capsys, root, "d70527a^..d70527a")
    assert code == 0
    c = _counts(out)
    assert (c["added"], c["with_entry"], c["no_entry"], c["gone_at_B"]) == ("5", "0", "5", "0")
    assert c["manifests_read"] == "13" and c["manifests_shape_not_read"] == "1"
    assert "manifest paper-rules/20261109/machine/PAPER_UNIVERSE_MANIFEST.json: its shape was not read" in out
    for n in range(157, 162):
        p = f"{PAPER}/run-plans/run-{n:04d}.json"
        rows = [ln for ln in out if ln.startswith(p + " |")]
        assert len(rows) == 1
        assert "exists at B" in rows[0] and "no manifest holds an entry for it" in rows[0]


def test_42614ca_first_load_experiments_files_have_entries(capsys):
    # markets-data 42614ca ("graph and experiments: the first load"), parent 624710b. `git diff --name-status`
    # shows A for experiments/MANIFEST.json, frankie_exp_dag.sqlite, trials.jsonl and graph/MANIFEST.json,
    # graph/edges/DERIVED_FROM.jsonl, graph/nodes/{AgentRun,Commit,Source}.jsonl = 8 added.
    # `git ls-tree -l`: trials.jsonl 52408 bytes, sha256 f924686d...; sqlite 77824 bytes, sha256 9074acf3...;
    # both equal their experiments/MANIFEST.json entries; DERIVED_FROM.jsonl 5171 bytes, sha256 711e9e0b..., equal
    # to its graph/MANIFEST.json entry. The two MANIFEST.json files are held by no manifest (not self-listed).
    root = _root()
    _needs(root, "42614ca", "624710b")
    code, out = _run(capsys, root, "624710b..42614ca")
    assert code == 0
    c = _counts(out)
    assert c["added"] == "8" and c["with_entry"] == "6" and c["no_entry"] == "2" and c["gone_at_B"] == "0"
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")]
    assert len(row) == 1
    assert "bytes at B 52408" in row[0]
    assert "experiments/MANIFEST.json: bytes equal, sha256 equal" in row[0]
    row = [ln for ln in out if ln.startswith("experiments/frankie_exp_dag.sqlite |")]
    assert "bytes at B 77824" in row[0] and "experiments/MANIFEST.json: bytes equal, sha256 equal" in row[0]
    row = [ln for ln in out if ln.startswith("graph/edges/DERIVED_FROM.jsonl |")]
    assert "bytes at B 5171" in row[0] and "graph/MANIFEST.json: bytes equal, sha256 equal" in row[0]
    for p in ("experiments/MANIFEST.json", "graph/MANIFEST.json"):
        row = [ln for ln in out if ln.startswith(p + " |")]
        assert len(row) == 1 and "no manifest holds an entry for it" in row[0]


def test_bad_range_exits_2_with_a_sentence(capsys):
    root = _root()
    code, out = _run(capsys, root, "0000000..1111111")
    assert code == 2
    assert len(out) == 1 and "cannot read the range" in out[0]


def test_bad_checkout_exits_2_with_a_sentence(capsys, tmp_path):
    code, out = _run(capsys, tmp_path, "a..b")
    assert code == 2
    assert len(out) == 1 and "cannot read the checkout" in out[0]


def test_output_gives_no_verdict_words(capsys):
    root = _root()
    _needs(root, "42614ca", "624710b")
    _, out = _run(capsys, root, "624710b..42614ca")
    text = " ".join(out).lower()
    assert "pass" not in text and "fail" not in text


# ---- CASES THE REAL HISTORY DOES NOT HOLD ----
# Each is a real file's text with exactly the named thing changed, committed into a scratch git repo
# (tmp_path, never markets-data). Real texts come from markets-data 42614ca.

def _git(repo, *a, text=True, inp=None):
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=text, input=inp, check=True)
    return r.stdout


def _scratch(tmp_path, root, manifest_text, extra_commit=None):
    """Commit 1: nothing but a README. Commit 2: real trials.jsonl and the (changed) manifest."""
    repo = tmp_path / "scratch"
    (repo / "experiments").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "x@example.invalid")
    _git(repo, "config", "user.name", "x")
    (repo / "README.md").write_text("scratch\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    trials = subprocess.run(["git", "-C", str(root), "show", "42614ca:experiments/trials.jsonl"],
                            capture_output=True, check=True).stdout
    (repo / "experiments" / "trials.jsonl").write_bytes(trials)
    (repo / "experiments" / "MANIFEST.json").write_text(manifest_text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add")
    if extra_commit:
        extra_commit(repo)
    return repo


def _real_manifest(root):
    _needs(root, "42614ca")
    return _git(root, "show", "42614ca:experiments/MANIFEST.json")


def test_changed_sha256_is_named_as_not_equal(capsys, tmp_path):
    # change: the sha256 of the experiments/trials.jsonl entry, first character f -> 0
    root = _root()
    text = _real_manifest(root)
    assert "f924686d" in text
    repo = _scratch(tmp_path, root, text.replace("f924686d", "0924686d", 1))
    code, out = _run(capsys, repo, "HEAD~1..HEAD")
    assert code == 0
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "experiments/MANIFEST.json: bytes equal, sha256 not equal" in row


def test_changed_bytes_is_named_as_not_equal(capsys, tmp_path):
    # change: the bytes of the experiments/trials.jsonl entry, 52408 -> 52409
    root = _root()
    text = _real_manifest(root)
    repo = _scratch(tmp_path, root, text.replace("52408", "52409", 1))
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "experiments/MANIFEST.json: bytes not equal, sha256 equal" in row


def test_manifest_of_unknown_shape_is_named_not_skipped(capsys, tmp_path):
    # change: the key "files" renamed "rows", so the manifest holds no list under "entries" or "files"
    root = _root()
    text = _real_manifest(root)
    assert '"files"' in text
    repo = _scratch(tmp_path, root, text.replace('"files"', '"rows"', 1))
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    assert "manifest experiments/MANIFEST.json: its shape was not read" in out
    c = _counts(out)
    assert c["manifests_shape_not_read"] == "1" and c["manifests_read"] == "0"
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "no manifest holds an entry for it" in row


def test_entry_without_bytes_or_sha_is_compared_only_where_it_carries_them(capsys, tmp_path):
    # change: the entry's "bytes" and "sha256" keys removed (the entry keeps path and source)
    root = _root()
    m = json.loads(_real_manifest(root))
    for k in ("bytes", "sha256"):
        del m["files"][0][k]
    repo = _scratch(tmp_path, root, json.dumps(m, indent=1))
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "experiments/MANIFEST.json: bytes not in entry, sha256 not in entry" in row


def test_file_removed_after_being_added_is_counted_gone_at_B(capsys, tmp_path):
    # change: a third commit deletes experiments/trials.jsonl; range covers both commits
    root = _root()
    text = _real_manifest(root)

    def rm(repo):
        _git(repo, "rm", "-q", "experiments/trials.jsonl")
        _git(repo, "commit", "-q", "-m", "remove")

    repo = _scratch(tmp_path, root, text, rm)
    _, out = _run(capsys, repo, "HEAD~2..HEAD")
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "gone at B" in row
    assert _counts(out)["gone_at_B"] == "1"
