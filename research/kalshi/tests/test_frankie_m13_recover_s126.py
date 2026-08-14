from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_m13_recover_s126 as m13  # noqa: E402


def _evidence(
    release="2026-07-23",
    observed="2026-07-23T14:06:50Z",
    printed="2026-07-23T14:30:00Z",
    value=29.0,
    run=30011332024,
    job=89219907311,
):
    return {
        "release_date": release,
        "print_datetime_utc": printed,
        "observed_at_utc": observed,
        "consensus_bcf": value,
        "previous_bcf": 41.0,
        "workflow_run_id": run,
        "workflow_job_id": job,
        "source": "ForexFactory/Fair Economy via consensus_poll.py",
        "evidence_url": f"https://github.com/DavisAI1974/Markets/actions/runs/{run}",
    }


def test_validate_evidence_requires_strictly_preprint_timestamp():
    ok = m13.validate_evidence_rows([_evidence()])
    assert ok[0]["consensus_bcf"] == 29.0

    with pytest.raises(m13.M13InvariantError, match="BLIND WALL"):
        m13.validate_evidence_rows(
            [_evidence(observed="2026-07-23T14:30:00Z")]
        )

    with pytest.raises(m13.M13InvariantError, match="BLIND WALL"):
        m13.validate_evidence_rows(
            [_evidence(observed="2026-07-23T14:30:01Z")]
        )


def test_merge_appends_new_report_with_normal_release_mechanics_and_exact_evidence():
    row = _evidence()
    merged, notes = m13.merge_storage_consensus(
        {"reports": []}, [row], {"2026-07-23": 31.0}
    )
    assert len(merged["reports"]) == 1
    rec = merged["reports"][0]
    assert rec["for_report_date"] == "2026-07-17"
    assert rec["print_date"] == "2026-07-23"
    assert rec["print_dow"] == "Thu"
    assert rec["print_time_et"] == "10:30"
    assert rec["consensus_chg_bcf"] == 29.0
    assert rec["consensus_pre_print_bcf"] == 29.0
    assert rec["actual_current_vintage_bcf"] == 31.0
    assert rec["actual_as_printed_bcf"] is None
    assert rec["estimates"][0]["pre_print"] is True
    assert rec["estimates"][0]["snapshot_utc"] == row["observed_at_utc"]
    assert rec["estimates"][0]["workflow_run_id"] == row["workflow_run_id"]
    assert "appended legal forward consensus" in notes[0]


def test_merge_preserves_conflicting_archived_headline_and_carries_forward_value_side_by_side():
    row = _evidence(value=29.0)
    baseline = {
        "reports": [
            {
                "print_date": "2026-07-23",
                "nominal_release_date": "2026-07-23",
                "consensus_chg_bcf": 28.0,
                "source": "archived-house",
                "consensus_pre_print_bcf": 28.0,
                "consensus_pre_print_snapshot_utc": "2026-07-22T18:00:00Z",
                "n_estimates": 1,
                "house_disagreement_bcf": None,
                "estimates": [
                    {
                        "source": "archived-house",
                        "value_bcf": 28.0,
                        "pre_print": True,
                        "snapshot_utc": "2026-07-22T18:00:00Z",
                    }
                ],
            }
        ]
    }
    merged, notes = m13.merge_storage_consensus(baseline, [row], {})
    rec = merged["reports"][0]
    assert rec["consensus_chg_bcf"] == 28.0
    assert rec["consensus_pre_print_bcf"] == 28.0
    assert sorted(e["value_bcf"] for e in rec["estimates"]) == [28.0, 29.0]
    assert rec["house_disagreement_bcf"] == 1.0
    assert any("preserved existing archived headline" in n for n in notes)


class _Body:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data


class _FakeS3:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def get_object(self, *, Bucket, Key):
        assert Bucket == m13.BUCKET
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": _Body(self.objects[Key])}


def test_d47_readback_requires_exact_remote_sha_and_manifest(tmp_path):
    src = tmp_path / "store"
    src.mkdir()
    (src / "a.json").write_bytes(b'{"a":1}\n')
    (src / "nested").mkdir()
    (src / "nested" / "b.json").write_bytes(b'{"b":2}\n')
    prefix = "test/"
    manifest = {
        "object_count": 2,
        "files": ["a.json", "nested/b.json"],
    }
    s3 = _FakeS3(
        {
            prefix + "a.json": (src / "a.json").read_bytes(),
            prefix + "nested/b.json": (src / "nested" / "b.json").read_bytes(),
            prefix + "manifest.json": json.dumps(manifest).encode(),
        }
    )
    result = m13.verify_s3_readback(prefix, src, s3)
    assert result["sha256_readback"] == "PASS"
    assert result["files"] == 2

    s3.objects[prefix + "a.json"] = b"corrupt"
    with pytest.raises(m13.M13InvariantError, match="SHA256 mismatch"):
        m13.verify_s3_readback(prefix, src, s3)


def test_run_refuses_s3_mutation_without_execute():
    with pytest.raises(m13.M13InvariantError, match="without --execute"):
        m13.run("g24", "2026-08-13", execute=False)
