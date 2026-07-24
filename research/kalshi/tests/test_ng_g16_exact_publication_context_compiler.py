from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class ExactPublicationContextCompilerTests(unittest.TestCase):
    def _root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def _write(self, path: Path, value: object) -> Path:
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def _spec(self, root: Path, mode: str, context: dict) -> Path:
        return self._write(
            root / "spec.json",
            {"schema": compiler.SPEC_SCHEMA, "mode": mode, "context": context},
        )

    def _lock_context(self, root: Path) -> dict:
        self._write(
            root / "exact_curve.json",
            {"actual_g16_outcomes_used": False, "fingerprint": "exact-curve"},
        )
        return {
            "exact_curve_authorization": {"$file": "exact_curve.json"},
            "exact_causal_authorization": {},
            "counterfactual_curve_authorization": {},
            "curve_kwargs": {},
            "legacy_lock_kwargs": {},
        }

    def test_lock_resolves_references_and_builds_exact_artifact(self) -> None:
        root = self._root()
        spec = self._spec(root, compiler.LOCK_MODE, self._lock_context(root))
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ) as build:
            context, artifact, receipt = compiler.compile_context(
                spec, mode=compiler.LOCK_MODE
            )
        self.assertEqual(
            context["exact_curve_authorization"]["fingerprint"], "exact-curve"
        )
        build.assert_called_once_with(**context)
        self.assertEqual(receipt["reference_count"], 1)
        self.assertFalse(receipt["actual_g16_outcomes_used"])
        self.assertEqual(receipt["artifact_fingerprint"], artifact["lock_fingerprint"])

    def test_completion_resolves_lock_after_fixed_outcome_boundary(self) -> None:
        root = self._root()
        self._write(root / "lock.json", {"lock_fingerprint": "locked"})
        spec = self._spec(
            root,
            compiler.COMPLETE_MODE,
            {
                "exact_curve_lock": {"$file": "lock.json"},
                "exact_lock_kwargs": {},
                "legacy_completion_kwargs": {},
            },
        )
        with mock.patch.object(
            compiler.gate, "build_completion", return_value=_completion_artifact()
        ):
            _, _, receipt = compiler.compile_context(
                spec, mode=compiler.COMPLETE_MODE
            )
        self.assertTrue(receipt["actual_g16_outcomes_used"])
        self.assertEqual(receipt["fixed_outcome_boundary"], "POST_LOCK_ONLY")

    def test_reference_sha256_mismatch_fails_closed(self) -> None:
        root = self._root()
        context = self._lock_context(root)
        context["exact_curve_authorization"]["$sha256"] = "wrong"
        spec = self._spec(root, compiler.LOCK_MODE, context)
        with self.assertRaises(compiler.G16ExactPublicationContextCompilerError):
            compiler.compile_context(spec, mode=compiler.LOCK_MODE)

    def test_missing_required_context_key_is_rejected(self) -> None:
        root = self._root()
        context = self._lock_context(root)
        context.pop("curve_kwargs")
        spec = self._spec(root, compiler.LOCK_MODE, context)
        with self.assertRaises(compiler.G16ExactPublicationContextCompilerError):
            compiler.compile_context(spec, mode=compiler.LOCK_MODE)

    def test_pre_outcome_lock_rejects_score_reference(self) -> None:
        root = self._root()
        self._write(root / "g16_score.json", {"blind_score": 1})
        context = self._lock_context(root)
        context["curve_kwargs"] = {"score": {"$file": "g16_score.json"}}
        spec = self._spec(root, compiler.LOCK_MODE, context)
        with self.assertRaises(compiler.G16ExactPublicationContextCompilerError):
            compiler.compile_context(spec, mode=compiler.LOCK_MODE)

    def test_pre_outcome_lock_allows_explicit_false_outcome_flags(self) -> None:
        root = self._root()
        context = self._lock_context(root)
        context["curve_kwargs"] = {"actual_g16_outcomes_used": False}
        spec = self._spec(root, compiler.LOCK_MODE, context)
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            compiler.compile_context(spec, mode=compiler.LOCK_MODE)

    def test_refingerprinted_options_escalation_is_rejected(self) -> None:
        root = self._root()
        spec = self._spec(root, compiler.LOCK_MODE, self._lock_context(root))
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            context, artifact, receipt = compiler.compile_context(
                spec, mode=compiler.LOCK_MODE
            )
        changed = copy.deepcopy(receipt)
        changed["options_lane_started"] = True
        changed.pop("fingerprint")
        changed["fingerprint"] = compiler._fp(changed)
        with self.assertRaises(compiler.G16ExactPublicationContextCompilerError):
            compiler.validate_receipt(
                changed,
                context=context,
                artifact=artifact,
                mode=compiler.LOCK_MODE,
            )

    def test_source_spec_and_context_are_not_mutated(self) -> None:
        root = self._root()
        context = self._lock_context(root)
        original = copy.deepcopy(context)
        spec = self._spec(root, compiler.LOCK_MODE, context)
        before = spec.read_bytes()
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            compiler.compile_context(spec, mode=compiler.LOCK_MODE)
        self.assertEqual(context, original)
        self.assertEqual(spec.read_bytes(), before)

    def test_compilation_is_deterministic(self) -> None:
        root = self._root()
        spec = self._spec(root, compiler.LOCK_MODE, self._lock_context(root))
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            first = compiler.compile_context(spec, mode=compiler.LOCK_MODE)
            second = compiler.compile_context(spec, mode=compiler.LOCK_MODE)
        self.assertEqual(first, second)

    def test_file_reference_rejects_unsupported_keys(self) -> None:
        root = self._root()
        context = self._lock_context(root)
        context["exact_curve_authorization"]["unexpected"] = True
        spec = self._spec(root, compiler.LOCK_MODE, context)
        with self.assertRaises(compiler.G16ExactPublicationContextCompilerError):
            compiler.compile_context(spec, mode=compiler.LOCK_MODE)

    def test_receipt_preserves_permanent_authority_wall(self) -> None:
        root = self._root()
        spec = self._spec(root, compiler.LOCK_MODE, self._lock_context(root))
        with mock.patch.object(
            compiler.gate, "build_curve_lock", return_value=_lock_artifact()
        ):
            _, _, receipt = compiler.compile_context(spec, mode=compiler.LOCK_MODE)
        self.assertFalse(receipt["paid_live_data_assumed"])
        self.assertFalse(receipt["random_shuffle_used"])
        self.assertTrue(receipt["one_signal_authority_preserved"])
        self.assertTrue(receipt["blind_forecasts_immutable"])
        self.assertFalse(receipt["may_update_ng_brain"])
        self.assertFalse(receipt["execution_authority"])
        self.assertEqual(receipt["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(receipt["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(receipt["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
