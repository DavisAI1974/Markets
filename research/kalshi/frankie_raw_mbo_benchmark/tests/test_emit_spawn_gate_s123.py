"""S123 Task A: the computed layer gate is on the spawn-emission path."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.kalshi.frankie_raw_mbo_benchmark import emit_frankie_spawn as emitter
from research.kalshi.frankie_raw_mbo_benchmark import native_layer_crosswalk as xw
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import canonical_hash
from research.kalshi.frankie_raw_mbo_benchmark.tests.test_emit_frankie_spawn import (
    _delivery_receipt,
    _repo_with_docs,
    _result,
)


def _write_json(root: Path, name: str, body: dict) -> Path:
    path = root / name
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _registry() -> dict:
    """Two real input identities, small enough that every status has one cause."""
    entries = [
        {
            "layer_id": layer_id,
            "description": layer_id,
            "source_paths": [xw.LAYER_PRODUCERS[layer_id]["carrier_paths"][0]],
            "v3_derived": False,
        }
        for layer_id in ("controlling_rt_mission", "native_calculation_contract")
    ]
    return {
        "registry_sha256": "a" * 64,
        "groups": [{
            "group_id": "binding_common_controls",
            "policy": "STATIC_REQUIRED_INPUT",
            "activation_stage": "PRE_CALL",
            "authority": "BINDING_CURRENT",
            "arms": ["A_MEMORY"],
            "principal_route": "DIRECT",
            "proof_mode": "CONTENT_SHA256",
            "entries": entries,
        }],
    }


class EmitSpawnGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.root, mission_sha, contract_sha = _repo_with_docs(self.root)
        self.result_body = _result(mission_sha, contract_sha)
        identity = self.result_body["layers"]["identity_receipt"]
        identity.update(arm="A_MEMORY", run_id="frankie-a-memory-fixture")
        self.result = _write_json(self.root, "calculation_result.json", self.result_body)
        self.delivery = _delivery_receipt(self.root)
        self.stream_body = {
            "schema": xw.STREAM_RECEIPT_SCHEMA,
            "layer_carriers": {},
            "complete": True,
            "receipt_sha256": "",
        }
        self.stream_body["receipt_sha256"] = canonical_hash(
            self.stream_body, omit="receipt_sha256"
        )
        self.stream = _write_json(self.root, "stream_receipt.json", self.stream_body)
        self.outputs_body = {
            "schema": xw.OUTPUTS_RECEIPT_SCHEMA,
            "ledgers": {},
            "receipt_sha256": "c" * 64,
        }
        self.outputs = _write_json(self.root, "outputs_receipt.json", self.outputs_body)
        self.sealed_body = {
            "schema": xw.SEALED_PROOF_SCHEMA,
            "all_absent": True,
            "tokens_checked": [],
            "receipt_sha256": "d" * 64,
        }
        self.sealed = _write_json(self.root, "sealed_proof.json", self.sealed_body)
        self.registry = _registry()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _knowledge(self, delivered: bool) -> tuple[Path, dict]:
        layers = []
        if delivered:
            layers = [
                {
                    "layer_id": entry["layer_id"],
                    "status": "DELIVERED",
                    "files": [{
                        "path": entry["source_paths"][0],
                        "sha256": "b" * 64,
                        "bytes": 1,
                    }],
                }
                for entry in self.registry["groups"][0]["entries"]
            ]
        body = {
            "schema": xw.KNOWLEDGE_RECEIPT_SCHEMA,
            "layers": layers,
            "receipt_sha256": "b" * 64,
        }
        return _write_json(self.root, "knowledge_receipt.json", body), body

    def _emit(self, knowledge: Path, captured: dict) -> str:
        def compute(*args, **kwargs):
            captured["registry_arg"] = args[0]
            captured.update(kwargs)
            return xw.crosswalk(*args, **kwargs)

        with (
            patch.object(xw, "load_registry", return_value=self.registry),
            patch.object(emitter, "crosswalk", side_effect=compute),
        ):
            return emitter.emit(
                self.result,
                repo_root=self.root,
                delivery_receipt=self.delivery,
                stream_receipt=self.stream,
                knowledge_receipt=knowledge,
                outputs_receipt=self.outputs,
                sealed_proof=self.sealed,
                ledger_dir=self.root / "delivered",
            )

    def test_accounted_inputs_emit_and_every_receipt_reaches_the_computed_crosswalk(self) -> None:
        knowledge, knowledge_body = self._knowledge(delivered=True)
        captured: dict = {}

        text = self._emit(knowledge, captured)

        self.assertIsNone(captured["registry_arg"])
        self.assertEqual(captured["arm"], "A_MEMORY")
        self.assertEqual(captured["result"], self.result_body)
        self.assertEqual(captured["stream_receipt"], self.stream_body)
        self.assertEqual(captured["knowledge_receipt"], knowledge_body)
        self.assertEqual(captured["outputs_receipt"], self.outputs_body)
        self.assertEqual(captured["sealed_proof"], self.sealed_body)
        self.assertEqual(captured["ledger_dir"], self.root / "delivered")

        body = xw.crosswalk(
            self.registry,
            arm="A_MEMORY",
            result=self.result_body,
            delivery_receipt=captured["delivery_receipt"],
            stream_receipt=self.stream_body,
            knowledge_receipt=knowledge_body,
            outputs_receipt=self.outputs_body,
            sealed_proof=self.sealed_body,
            ledger_dir=self.root / "delivered",
        )
        totals = body["totals"]
        self.assertIn(body["crosswalk_sha256"], text)
        self.assertIn(str(totals["inputs_accounted"]), text)
        self.assertIn(str(totals["inputs_applicable"]), text)

    def test_refusal_preserves_every_computed_offender_and_status(self) -> None:
        knowledge, knowledge_body = self._knowledge(delivered=False)
        delivery_body = json.loads(self.delivery.read_text(encoding="utf-8"))
        body = xw.crosswalk(
            self.registry,
            arm="A_MEMORY",
            result=self.result_body,
            delivery_receipt=delivery_body,
            stream_receipt=self.stream_body,
            knowledge_receipt=knowledge_body,
            outputs_receipt=self.outputs_body,
            sealed_proof=self.sealed_body,
            ledger_dir=self.root / "delivered",
        )
        offenders = [
            f"{row['layer_id']}={row['status']}"
            for row in body["layers"]
            if row["arm_applicable"]
            and row["policy"] in xw.INPUT_POLICIES
            and row["status"] not in xw.ACCOUNTED_INPUT_STATUSES
        ]
        self.assertGreater(len(offenders), 1)

        with self.assertRaises(emitter.EmitError) as caught:
            self._emit(knowledge, {})

        for offender in offenders:
            self.assertIn(offender, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
