import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import ng_exhaustion_mbo_5y_step1_census_20260822 as census


RECOVERY = ROOT / ".github/workflows/ng_exhaustion_mbo_5y_step1_recover_20260823.yml"
STATUS = ROOT / ".github/workflows/ng_exhaustion_mbo_5y_step1_status_20260823.yml"
LOCK = ROOT / "research/kalshi/NG_EXHAUSTION_MBO_5Y_STEP1_FINALIZER_LOCK_20260823.json"
SCRIPT = ROOT / "research/kalshi/ng_exhaustion_step1_recovery.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_recovery_workflow_is_manual_exact_candidate_and_never_cancels_live_work():
    source = RECOVERY.read_text(encoding="utf-8")
    assert "workflow_dispatch" in source
    assert "0d318335825b4a0e19a5a2881522f3da0374788e" in source
    assert "classify_recovery_state" in source
    assert "HEALTHY_RUNNING" in source
    assert "FINALIZE_FROM_CHILDREN" in source
    assert "RESUME_CONTROLLER" in source
    assert "cancel-command" not in source
    assert "stop " not in source
    assert "kill -TERM" not in source
    assert "kill -KILL" not in source


def test_finalizer_reuses_exact_children_and_retains_one_day_authorization():
    source = RECOVERY.read_text(encoding="utf-8")
    assert "--child-recovery-contract" in source
    assert "--accepted-one-day-launch-receipt" in source
    assert "FULL_65_CHILDREN_REUSED_NO_RAW_MBO_REPLAY" in source
    assert "ng_exhaustion_step1_recovery.py prepare-contract" in source
    assert "STEP1_DUAL_CENSUS_RECEIPT.json" in source
    assert "CONTROLLER_HEARTBEAT.json" in source
    assert "list-objects" not in source
    assert "aws s3 ls" not in source
    assert "authorize_dispatch" not in source
    assert "agent_frankie" not in source


def test_status_reads_exact_full_heartbeat_and_unit_without_prefix_listing():
    source = STATUS.read_text(encoding="utf-8")
    assert "if: github.event_name == 'workflow_dispatch'" in source
    assert "0d318335825b4a0e19a5a2881522f3da0374788e" in source
    assert "full/progress/CONTROLLER_HEARTBEAT.json" in source
    assert "full/CONTROLLER_HEARTBEAT.json" in source
    assert "systemctl show" in source
    assert "list-objects" not in source
    assert "aws s3 ls" not in source


def test_checked_in_finalizer_lock_pins_every_executable_byte():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    claimed = lock.pop("finalizer_lock_sha256")
    actual = hashlib.sha256(
        json.dumps(lock, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    assert claimed == actual
    assert lock["finalizer_engine_hashes"] == census.material_hashes()
    assert lock["recovery_script_sha256"] == digest(SCRIPT)
    assert lock["recovery_workflow_sha256"] == digest(RECOVERY)
