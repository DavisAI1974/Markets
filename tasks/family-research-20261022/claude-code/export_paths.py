"""Where each session's standalone export and touch-print decisions live on the branch, and its session origin."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR = ROOT / "tasks" / "family-research-20261022"
RETAINED = ROOT / "research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-bounded-replay/retained"

SESSIONS = {
    "oct02": dict(day="20231002", day0=1696194000, groups=FR / "replay-artifacts/20231002/standalone-inputs/groups.jsonl.gz",
                  decisions=FR / "replay-artifacts/20231002/standalone-decisions/decisions.jsonl.gz", export_scope="partial (no Sunday-evening prefix)"),
    "oct03": dict(day="20231003", day0=1696280400, groups=FR / "replay-artifacts/20231003/standalone-inputs/groups.jsonl.gz",
                  decisions=FR / "replay-artifacts/20231003/standalone-decisions/decisions.jsonl.gz", export_scope="full session"),
    "oct17": dict(day="20231017", day0=1697490000, groups=FR / "replay-artifacts/20231017/standalone-inputs/groups.jsonl.gz",
                  decisions=FR / "replay-artifacts/20231017/standalone-decisions/decisions.jsonl.gz", export_scope="partial (no evening prefix)"),
    "oct18": dict(day="20231018", day0=1697576400, groups=RETAINED / "october18-standalone-inputs/groups.jsonl.gz",
                  decisions=FR / "october18-touch-print-decisions.jsonl.gz", export_scope="full session"),
}

# The branch files above arrive with the next fetch; until then the same bytes (sha256-verified against the receipts)
# sit in the session scratchpad, downloaded from the branch head 2f12d6d4 via raw.githubusercontent.com.
SCRATCH = Path("/tmp/claude-0/-home-user-Markets/e6cffa19-4561-5119-b5f4-3474c12f9fe5/scratchpad/exports")
for _tag, _s in SESSIONS.items():
    for _k in ("groups", "decisions"):
        if not _s[_k].exists():
            _alt = SCRATCH / _s["day"] / ("standalone-inputs/groups.jsonl.gz" if _k == "groups" else "standalone-decisions/decisions.jsonl.gz")
            if _alt.exists():
                _s[_k] = _alt
