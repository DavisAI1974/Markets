from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "ng_corpus_executor_plan_compiler_v23.py",
    "ng_corpus_executor_pipeline_arm_v23.py",
    "ng_historical_refinement_preflight_v24.py",
)


def test_v28_execution_modules_are_reviewable_plain_python() -> None:
    for filename in MODULES:
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "_v28_execution_patch.txz" not in source
        assert "exec(compile(" not in source
        assert "tarfile" not in source


def test_archived_v28_source_bundle_is_removed() -> None:
    assert not (ROOT / "_v28_execution_patch.txz").exists()
