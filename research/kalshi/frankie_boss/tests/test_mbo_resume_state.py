from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
RESEARCH_ROOT = REPO_ROOT / "research"
ADAPTER_PATH = RESEARCH_ROOT / "ng_exhaustion_mbo_v4_state_adapter_20260820.py"
RESUME_PATH = Path(__file__).resolve().parents[1] / "mbo_resume_state.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


adapter_module = load_module("v4_mbo_adapter_under_test", ADAPTER_PATH)
resume_module = load_module("v4_mbo_resume_under_test", RESUME_PATH)

V4MboAdapter = adapter_module.V4MboAdapter
F_LAST = adapter_module.F_LAST
PRICE_SCALE = adapter_module.PRICE_SCALE
ResumeStateError = resume_module.ResumeStateError
adapter_state_hash = resume_module.adapter_state_hash
export_adapter_state = resume_module.export_adapter_state
load_adapter_state = resume_module.load_adapter_state
restore_adapter_state = resume_module.restore_adapter_state
write_adapter_state_atomic = resume_module.write_adapter_state_atomic

SOURCE_SHA = "a" * 64


def row(
    *,
    action: str,
    side: str,
    order_id: int,
    price: int,
    size: int,
    sequence: int,
    ts_recv_ns: int,
    flags: int = F_LAST,
    instrument_id: int = 1,
):
    return {
        "instrument_id": instrument_id,
        "publisher_id": 1,
        "channel_id": 7,
        "order_id": order_id,
        "action": action,
        "side": side,
        "price": price,
        "size": size,
        "flags": flags,
        "sequence": sequence,
        "ts_event": ts_recv_ns - 10,
        "ts_recv": ts_recv_ns,
        "ts_in_delta": 10,
    }


def apply_rows(adapter, rows):
    emitted = []
    for record in rows:
        frame, legacy = adapter.apply(
            record,
            raw_symbol="NGX1",
            source_dbn_object="synthetic.mbo.dbn.zst",
            source_dbn_sha256=SOURCE_SHA,
        )
        if frame is not None:
            emitted.append((frame, legacy))
    return emitted


class MboResumeStateTests(unittest.TestCase):
    def prefix(self):
        p = PRICE_SCALE
        return [
            row(action="A", side="B", order_id=1, price=100 * p, size=10, sequence=1, ts_recv_ns=1_000_000_000),
            row(action="A", side="B", order_id=2, price=100 * p, size=5, sequence=2, ts_recv_ns=2_000_000_000),
            row(action="A", side="A", order_id=3, price=101 * p, size=8, sequence=3, ts_recv_ns=3_000_000_000),
            row(action="T", side="B", order_id=0, price=101 * p, size=3, sequence=4, ts_recv_ns=4_000_000_000),
            row(action="M", side="B", order_id=1, price=100 * p, size=7, sequence=5, ts_recv_ns=5_000_000_000),
            row(action="A", side="B", order_id=20, price=99 * p, size=4, sequence=1, ts_recv_ns=5_500_000_000, instrument_id=2),
        ]

    def suffix(self):
        p = PRICE_SCALE
        return [
            row(action="M", side="B", order_id=2, price=99 * p, size=6, sequence=6, ts_recv_ns=6_000_000_000),
            row(action="C", side="B", order_id=1, price=100 * p, size=7, sequence=7, ts_recv_ns=7_000_000_000),
            row(action="A", side="B", order_id=4, price=100 * p, size=4, sequence=8, ts_recv_ns=8_000_000_000),
            row(action="T", side="A", order_id=0, price=100 * p, size=2, sequence=9, ts_recv_ns=9_000_000_000),
            row(action="M", side="B", order_id=20, price=99 * p, size=3, sequence=2, ts_recv_ns=9_500_000_000, instrument_id=2),
        ]

    def test_export_restore_round_trip_is_exact(self):
        adapter = V4MboAdapter()
        apply_rows(adapter, self.prefix())
        state = export_adapter_state(adapter)
        self.assertEqual(state["state_hash"], adapter_state_hash(state))
        restored = restore_adapter_state(state)
        self.assertEqual(export_adapter_state(restored), state)

    def test_continuous_equals_checkpoint_restore_continue(self):
        continuous = V4MboAdapter()
        apply_rows(continuous, self.prefix())

        resumed_source = V4MboAdapter()
        apply_rows(resumed_source, self.prefix())
        restored = restore_adapter_state(export_adapter_state(resumed_source))

        continuous_emitted = apply_rows(continuous, self.suffix())
        restored_emitted = apply_rows(restored, self.suffix())

        self.assertEqual(continuous_emitted, restored_emitted)
        self.assertEqual(export_adapter_state(continuous), export_adapter_state(restored))

    def test_checkpoint_refuses_open_event_group(self):
        p = PRICE_SCALE
        adapter = V4MboAdapter()
        apply_rows(
            adapter,
            [row(action="A", side="B", order_id=1, price=100 * p, size=10, sequence=1, ts_recv_ns=1_000_000_000, flags=0)],
        )
        with self.assertRaisesRegex(ResumeStateError, "F_LAST"):
            export_adapter_state(adapter)

    def test_hash_detects_state_tampering(self):
        adapter = V4MboAdapter()
        apply_rows(adapter, self.prefix())
        state = export_adapter_state(adapter)
        poisoned = copy.deepcopy(state)
        poisoned["record_count"] += 1
        with self.assertRaisesRegex(ResumeStateError, "hash"):
            restore_adapter_state(poisoned)

    def test_restore_rejects_fifo_level_inconsistency_even_with_rehashed_payload(self):
        adapter = V4MboAdapter()
        apply_rows(adapter, self.prefix())
        state = export_adapter_state(adapter)
        poisoned = copy.deepcopy(state)
        level = poisoned["books"][0]["levels"]["B"][0]
        level["order_ids"].append(level["order_ids"][0])
        poisoned["state_hash"] = adapter_state_hash(poisoned)
        with self.assertRaisesRegex(ResumeStateError, "FIFO|duplicate|level"):
            restore_adapter_state(poisoned)

    def test_schema_is_closed(self):
        adapter = V4MboAdapter()
        apply_rows(adapter, self.prefix())
        state = export_adapter_state(adapter)
        poisoned = copy.deepcopy(state)
        poisoned["step1_answer"] = "forbidden"
        poisoned["state_hash"] = adapter_state_hash(poisoned)
        with self.assertRaisesRegex(ResumeStateError, "unknown"):
            restore_adapter_state(poisoned)

    def test_atomic_state_file_round_trip(self):
        adapter = V4MboAdapter()
        apply_rows(adapter, self.prefix())
        state = export_adapter_state(adapter)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adapter-state.json"
            write_adapter_state_atomic(path, state)
            self.assertEqual(load_adapter_state(path), state)
            self.assertFalse(any(p.name.endswith(".tmp") for p in path.parent.iterdir()))

            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["record_count"] += 1
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ResumeStateError, "hash"):
                load_adapter_state(path)


if __name__ == "__main__":
    unittest.main()
