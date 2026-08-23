import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/frankie_v4_follow_on_agents_20260821.yml"
BASELINE = ROOT / "research/kalshi/NG_EXHAUSTION_V4_PROTECTED_BASELINE_20260821.json"


def test_follow_on_workflow_uses_existing_hash_baseline_not_missing_git_object():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "bd3d729780a025c1fbffd4f219854a609fa5ac6a" not in source
    assert "NG_EXHAUSTION_V4_PROTECTED_BASELINE_20260821.json" in source
    assert "follow-on-agent:\n    if: github.event_name == 'workflow_dispatch'" in source


def test_protected_baseline_matches_current_files():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    for relative, expected in baseline["files_sha256"].items():
        raw = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
        actual = hashlib.sha256(raw).hexdigest()
        assert actual == expected, relative
