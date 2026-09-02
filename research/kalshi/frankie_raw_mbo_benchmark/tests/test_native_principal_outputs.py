"""The principal's OUTPUT ledgers: the required set is DERIVED, the chain is append-only.

Greg, S120 (DROP_IN_S121 item zero, ruling 4): *"don't take any historical number like that
as a valid number that we should follow"*; *"not 10 as the floor. if it's supposed to have
30, the floor is 28. 10 is how 20 get silently dropped."* So no test here asserts a literal
count. Each derives the expected count independently of the module and compares.

Every refusal below is PRODUCED, not asserted: a guard whose firing branch never executed was
never tested (S113, NC-3).
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
import re
import unittest
from pathlib import Path

from research.kalshi.frankie_raw_mbo_benchmark import native_principal_outputs as outputs
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    REGISTRY_PATH,
    load_registry,
)

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "agents"
    / "frankie_native_raw_mbo_calculation_contract_20260828.md"
)


def registry_today() -> dict:
    return load_registry(REGISTRY_PATH)


def contract_today() -> str:
    return CONTRACT_PATH.read_text(encoding="utf-8")


def independent_output_ids(registry: dict) -> list[str]:
    """Read the registry the long way round, so the test does not trust the module's reader."""
    for group in registry["groups"]:
        if group["group_id"] == "append_only_outputs":
            return [entry["layer_id"] for entry in group["entries"]]
    raise AssertionError("no append_only_outputs group in the registry")


def independent_section_ids(contract_text: str) -> list[str]:
    """Line scan, not the module's regex: every `### 4.` heading, first token after `### `."""
    ids = []
    for line in contract_text.splitlines():
        if line.startswith("### 4."):
            ids.append(line.split()[1])
    return ids


class RequiredSetIsDerivedTest(unittest.TestCase):
    def test_output_layer_ids_are_read_from_the_loaded_registry(self):
        registry = registry_today()
        self.assertEqual(
            list(outputs.registry_output_layer_ids(registry)), independent_output_ids(registry)
        )

    def test_contract_section_ids_include_4_0_and_4_0b_in_document_order(self):
        ids = outputs.contract_section_ids(contract_today())
        self.assertEqual(list(ids), independent_section_ids(contract_today()))
        self.assertIn("4.0", ids)
        self.assertIn("4.0b", ids)
        self.assertLess(ids.index("4.0"), ids.index("4.0b"))
        self.assertLess(ids.index("4.0b"), ids.index("4.1"))

    def test_required_count_on_todays_files_is_outputs_plus_sections_plus_two(self):
        registry, contract = registry_today(), contract_today()
        required = outputs.required_ledger_ids(registry, contract)
        expected = len(independent_output_ids(registry)) + len(independent_section_ids(contract)) + 2
        self.assertEqual(len(required), expected)
        self.assertEqual(len(set(required)), len(required), "no ledger id repeats")
        for section in independent_section_ids(contract):
            self.assertIn(f"contract_section_{section}", required)
        self.assertIn("raw_mbo_classification", required)
        self.assertIn("knowledge_verification", required)

    def test_adding_a_contract_heading_grows_the_set_by_exactly_one(self):
        registry, contract = registry_today(), contract_today()
        before = outputs.required_ledger_ids(registry, contract)
        after = outputs.required_ledger_ids(registry, contract + "\n### 4.17 A new focus\n\nText.\n")
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(set(after) - set(before), {"contract_section_4.17"})

    def test_removing_an_output_layer_from_a_registry_copy_shrinks_the_set_by_one(self):
        registry, contract = registry_today(), contract_today()
        before = outputs.required_ledger_ids(registry, contract)
        smaller = copy.deepcopy(registry)
        group = next(g for g in smaller["groups"] if g["group_id"] == "append_only_outputs")
        removed = group["entries"].pop()["layer_id"]
        after = outputs.required_ledger_ids(smaller, contract)
        self.assertEqual(len(after), len(before) - 1)
        self.assertEqual(set(before) - set(after), {removed})

    def test_a_contract_with_no_section_headings_is_refused(self):
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.contract_section_ids("# Not a calculation contract\n\n## 4. Matrix\n")

    def test_a_registry_without_the_output_group_is_refused(self):
        registry = copy.deepcopy(registry_today())
        registry["groups"] = [g for g in registry["groups"] if g["group_id"] != "append_only_outputs"]
        with self.assertRaises(outputs.PrincipalOutputError):
            outputs.registry_output_layer_ids(registry)

    def test_no_module_level_constant_names_a_count(self):
        # Ruling 4. A count typed into the module is the number that becomes the floor.
        tree = ast.parse(inspect.getsource(outputs))
        offenders = []
        for node in tree.body:
            targets = []
            value = None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            if value is None:
                continue
            if isinstance(value, ast.UnaryOp):
                value = value.operand
            if isinstance(value, ast.Constant) and isinstance(value.value, int) and not isinstance(value.value, bool):
                offenders.append(ast.unparse(targets[0]))
        self.assertEqual(offenders, [], f"module-level integer constants: {offenders}")


if __name__ == "__main__":
    unittest.main()
