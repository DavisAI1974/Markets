from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_g16_exact_context_compilation_gate as attestor
import ng_g16_exact_publication_context_compiler as compiler


def _lock_artifact() -> dict:
    value = {
        "schema": "ng_g16_exact_counterfactual_curve_lock.v1",
        "status": "EXACT_G16_CORPUS_COUNTERFACTUAL_CURVE_LOCKED",
    }
    value["lock_fingerprint"] = compiler._fp(value)
    return value


def _completion_artifact() -> dict:
    value = {
        "schema": "ng_g16_exact_counterfactual_publication_completion.v1",
        "status": "EXACT_G16_CORPUS_COUNTERFACTUAL_PUBLICATION_COMPLETE",
    }
    value["completion_fingerprint"] = compiler._fp(value)
    return value


class ExactContextCompilationGateTests(unittest.TestCase):
    def _root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def _write(self, path: Path, value: object) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def _compile_lock(self, root: Path) -> tuple[Path, Path, Path, Path]:
        self._write(
            root / "exact_curve.json",
            {"actual_g16_outcomes_used": False, "fingerprint": "exact-curve"},
        )
        spec = self._write(
            root / "lock_spec.json",
            {
                "schema": compiler.SPEC_SCHEMA,
                "mode": compiler.LOCK_MODE,
                "context": {
                    "exact_curve_authorization": {"$file": "exact_curve.json"},
                    "exact_causal_authorization": {},
                    "counterfactual_curve_authorization": {},
                    "curve_kwargs": {},
                    "legacy_lock_kwargs": {},
                },
            },
        )
        context, artifact, receipt = compiler.compile_context(
            spec, mode=compiler.LOCK_MODE
        )
        context_path = self._write(root / "lock_context.json", context)
        artifact_path = self._write(root / "lock.json", artifact)
        receipt_path = self._write(root / "lock_receipt.json", receipt)
        return spec, context_path, artifact_path, receipt_path

    def _compile_complete(
        self, root: Path, lock_artifact: dict
    ) -> tuple[Path, Path, Path, Path]:
        self._write(root / "lock_input.json", lock_artifact)
        spec = self._write(
            root / "publication_spec.json",
            {
                "schema": compiler.SPEC_SCHEMA,
                "mode": compiler.COMPLETE_MODE,
                "context": {
                    "exact_curve_lock": {"$file": "lock_input.json"},
                    "exact_lock_kwargs": {},
                    "legacy_completion_kwargs": {},
                },
            },
        )
        context, artifact, receipt = compiler.compile_context(
            spec, mode=compiler.COMPLETE_MODE
        )
        context_path = self._write(root / "publication_context.json", context)
        artifact_path = self._write(root / "publication.json", artifact)
        receipt_path = self._write(root / "publication_receipt.json", receipt)
        return spec, context_path, artifact_path, receipt_path

    def test_lock_attestation_reconstructs_compiler_and_references(self) -> None:
        root = self._root()
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            paths = self._compile_lock(root)
            value = attestor.build_attestation(
                mode=compiler.LOCK_MODE,
                spec_path=paths[0],
                context_path=paths[1],
                artifact_path=paths[2],
                receipt_path=paths[3],
            )
            attestor.validate_attestation(value)
        self.assertEqual(
            value["status"], "EXACT_G16_LOCK_CONTEXT_COMPILATION_ATTESTED"
        )
        self.assertEqual(value["reference_count"], 1)
        self.assertFalse(value["actual_g16_outcomes_used"])

    def test_publication_attestation_binds_pre_outcome_lock(self) -> None:
        root = self._root()
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ), mock.patch.object(
            compiler.gate, "build_completion", return_value=_completion_artifact()
        ):
            lock_paths = self._compile_lock(root)
            lock = attestor.build_attestation(
                mode=compiler.LOCK_MODE,
                spec_path=lock_paths[0],
                context_path=lock_paths[1],
                artifact_path=lock_paths[2],
                receipt_path=lock_paths[3],
            )
            lock_attestation_path = self._write(root / "lock_attestation.json", lock)
            lock_artifact = json.loads(lock_paths[2].read_text(encoding="utf-8"))
            publication_paths = self._compile_complete(root, lock_artifact)
            publication = attestor.build_attestation(
                mode=compiler.COMPLETE_MODE,
                spec_path=publication_paths[0],
                context_path=publication_paths[1],
                artifact_path=publication_paths[2],
                receipt_path=publication_paths[3],
                lock_attestation_path=lock_attestation_path,
            )
            attestor.validate_attestation(publication)
        self.assertTrue(publication["actual_g16_outcomes_used"])
        self.assertEqual(
            publication["lock_context_compilation_attestation_fingerprint"],
            lock["fingerprint"],
        )
        self.assertEqual(
            publication["source_lock_artifact_fingerprint"],
            lock["artifact_fingerprint"],
        )

    def test_publication_requires_lock_attestation(self) -> None:
        root = self._root()
        with mock.patch.object(
            compiler.gate, "build_completion", return_value=_completion_artifact()
        ):
            paths = self._compile_complete(root, _lock_artifact())
            with self.assertRaises(attestor.G16ExactContextCompilationGateError):
                attestor.build_attestation(
                    mode=compiler.COMPLETE_MODE,
                    spec_path=paths[0],
                    context_path=paths[1],
                    artifact_path=paths[2],
                    receipt_path=paths[3],
                )

    def test_external_reference_is_rejected(self) -> None:
        root = self._root()
        outside = root.parent / "outside_exact_curve.json"
        self._write(outside, {"fingerprint": "outside"})
        spec = self._write(
            root / "lock_spec.json",
            {
                "schema": compiler.SPEC_SCHEMA,
                "mode": compiler.LOCK_MODE,
                "context": {
                    "exact_curve_authorization": {"$file": str(outside)},
                    "exact_causal_authorization": {},
                    "counterfactual_curve_authorization": {},
                    "curve_kwargs": {},
                    "legacy_lock_kwargs": {},
                },
            },
        )
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            context, artifact, receipt = compiler.compile_context(
                spec, mode=compiler.LOCK_MODE
            )
            with self.assertRaises(attestor.G16ExactContextCompilationGateError):
                attestor.build_attestation(
                    mode=compiler.LOCK_MODE,
                    spec_path=spec,
                    context_path=self._write(root / "context.json", context),
                    artifact_path=self._write(root / "artifact.json", artifact),
                    receipt_path=self._write(root / "receipt.json", receipt),
                )

    def test_refingerprinted_reference_snapshot_tampering_fails(self) -> None:
        root = self._root()
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            paths = self._compile_lock(root)
            value = attestor.build_attestation(
                mode=compiler.LOCK_MODE,
                spec_path=paths[0],
                context_path=paths[1],
                artifact_path=paths[2],
                receipt_path=paths[3],
            )
            changed = copy.deepcopy(value)
            changed["source_bundle"]["reference_snapshots"][0]["raw_utf8"] = "{}\n"
            changed.pop("fingerprint")
            changed["fingerprint"] = attestor._fp(changed)
            with self.assertRaises(attestor.G16ExactContextCompilationGateError):
                attestor.validate_attestation(changed)

    def test_refingerprinted_saved_context_tampering_fails(self) -> None:
        root = self._root()
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            paths = self._compile_lock(root)
            value = attestor.build_attestation(
                mode=compiler.LOCK_MODE,
                spec_path=paths[0],
                context_path=paths[1],
                artifact_path=paths[2],
                receipt_path=paths[3],
            )
            changed = copy.deepcopy(value)
            context = json.loads(changed["source_bundle"]["context_raw_utf8"])
            context["curve_kwargs"]["unexpected"] = True
            changed["source_bundle"]["context_raw_utf8"] = json.dumps(context) + "\n"
            changed["context_sha256"] = attestor._sha256_text(
                changed["source_bundle"]["context_raw_utf8"]
            )
            changed["context_fingerprint"] = compiler._fp(context)
            changed.pop("fingerprint")
            changed["fingerprint"] = attestor._fp(changed)
            with self.assertRaises(attestor.G16ExactContextCompilationGateError):
                attestor.validate_attestation(changed)

    def test_refingerprinted_options_escalation_fails(self) -> None:
        root = self._root()
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            paths = self._compile_lock(root)
            value = attestor.build_attestation(
                mode=compiler.LOCK_MODE,
                spec_path=paths[0],
                context_path=paths[1],
                artifact_path=paths[2],
                receipt_path=paths[3],
            )
            changed = copy.deepcopy(value)
            changed["options_lane_started"] = True
            changed.pop("fingerprint")
            changed["fingerprint"] = attestor._fp(changed)
            with self.assertRaises(attestor.G16ExactContextCompilationGateError):
                attestor.validate_attestation(changed)

    def test_attestation_is_deterministic(self) -> None:
        root = self._root()
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            paths = self._compile_lock(root)
            kwargs = dict(
                mode=compiler.LOCK_MODE,
                spec_path=paths[0],
                context_path=paths[1],
                artifact_path=paths[2],
                receipt_path=paths[3],
            )
            self.assertEqual(
                attestor.build_attestation(**kwargs),
                attestor.build_attestation(**kwargs),
            )

    def test_permanent_authority_wall(self) -> None:
        root = self._root()
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            paths = self._compile_lock(root)
            value = attestor.build_attestation(
                mode=compiler.LOCK_MODE,
                spec_path=paths[0],
                context_path=paths[1],
                artifact_path=paths[2],
                receipt_path=paths[3],
            )
        self.assertFalse(value["paid_live_data_assumed"])
        self.assertFalse(value["random_shuffle_used"])
        self.assertTrue(value["one_signal_authority_preserved"])
        self.assertTrue(value["blind_forecasts_immutable"])
        self.assertFalse(value["may_update_ng_brain"])
        self.assertFalse(value["execution_authority"])
        self.assertEqual(value["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(value["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(value["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
