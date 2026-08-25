from __future__ import annotations

import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frankie_full_stack_paired_lane_orchestrator_20260824 import (  # noqa: E402
    ComponentStatus,
)
from frankie_full_stack_provisional_combined_pipeline_20260824 import (  # noqa: E402
    ACTIVE_COMPONENT_IDS,
    ProvisionalAbilityApis,
    execute_combined_provisional_pipeline,
)
from frankie_full_stack_runtime_contracts_20260824 import CausalPrefixBinding  # noqa: E402


def binding() -> CausalPrefixBinding:
    return CausalPrefixBinding(
        run_id="combined-pipeline-test",
        causal_cutoff=1633046400.0,
        event_known_by=1633046400.0,
        causal_prefix_hash="1" * 64,
        state_prefix_hash="2" * 64,
        knowledge_manifest_hash="3" * 64,
    ).validate()


class ProvisionalCombinedPipelineTests(unittest.TestCase):
    def test_production_adapters_execute_every_checked_in_public_api(self):
        receipts = execute_combined_provisional_pipeline(
            binding=binding(),
            causal_state={
                "signal": "prefix-only",
                "source_second": 1633046400,
                "protected_prefix_hash": "1" * 64,
            },
            source_contexts={
                component_id: [
                    {
                        "path": f"research/kalshi/{component_id.lower()}.py",
                        "source_sha256": "a" * 64,
                        "content_excerpt": f"{component_id} checked-in source",
                    }
                ]
                for component_id in ACTIVE_COMPONENT_IDS
            },
        )

        active = [json.loads(item.context_json) for item in receipts[:-1]]
        self.assertEqual([item["component_id"] for item in active], list(ACTIVE_COMPONENT_IDS))
        self.assertTrue(all(item["executed"] for item in active))
        self.assertTrue(all(item["derived_output"]["status"] == "COMPLETED" for item in active))
        self.assertEqual(len({item["all_together_input_hash"] for item in active}), 1)

    def test_all_seven_abilities_execute_on_one_identity_and_outputs_enter_receipts(self):
        calls: list[tuple[str, str, str]] = []

        def ability(component_id):
            def execute(request):
                calls.append(
                    (
                        component_id,
                        request.binding.causal_prefix_hash,
                        request.all_together_input_hash,
                    )
                )
                return {
                    "status": "COMPLETED",
                    "component_id": component_id,
                    "derived": request.causal_state["signal"],
                }

            return execute

        apis = ProvisionalAbilityApis(
            s137_cognitive_runtime=ability("S137_COGNITIVE_RUNTIME"),
            hipporag_retrieval=ability("HIPPORAG_RETRIEVAL"),
            temporal_graph=ability("TEMPORAL_GRAPH"),
            lats_bounded_search=ability("LATS_BOUNDED_SEARCH"),
            working_memory=ability("WORKING_MEMORY"),
            progress_compression=ability("PROGRESS_COMPRESSION"),
            provisional_v4_candidate=ability("PROVISIONAL_V4_ENGINEERING_CANDIDATE"),
        )

        receipts = execute_combined_provisional_pipeline(
            binding=binding(),
            causal_state={"signal": "prefix-only"},
            source_contexts={
                component_id: [{"path": f"shadow/{component_id}.py", "source_sha256": "a" * 64}]
                for component_id in ACTIVE_COMPONENT_IDS
            },
            apis=apis,
        )

        self.assertEqual([row[0] for row in calls], list(ACTIVE_COMPONENT_IDS))
        self.assertEqual({row[1] for row in calls}, {"1" * 64})
        self.assertEqual(len({row[2] for row in calls}), 1)
        active = [item for item in receipts if item.component_id != "META_LOOP"]
        self.assertEqual([item.component_id for item in active], list(ACTIVE_COMPONENT_IDS))
        for item in active:
            context = json.loads(item.context_json)
            self.assertTrue(context["executed"])
            self.assertEqual(context["binding"]["causal_prefix_hash"], "1" * 64)
            self.assertEqual(context["derived_output"]["derived"], "prefix-only")
            self.assertEqual(context["component_id"], item.component_id)
            self.assertEqual(item.status, ComponentStatus.ACTIVE)

        deferred = receipts[-1]
        self.assertEqual(deferred.component_id, "META_LOOP")
        self.assertEqual(deferred.status, ComponentStatus.DEFERRED_NOT_YET_LAWFUL)
        self.assertFalse(json.loads(deferred.context_json)["executed"])

    def test_rejected_ability_fails_before_any_provider_can_receive_partial_context(self):
        calls: list[str] = []

        def complete(request):
            calls.append(request.component_id)
            return {"status": "COMPLETED"}

        def rejected(request):
            calls.append(request.component_id)
            return {"status": "REJECTED", "reason": "contract failure"}

        apis = ProvisionalAbilityApis(
            s137_cognitive_runtime=complete,
            hipporag_retrieval=rejected,
            temporal_graph=complete,
            lats_bounded_search=complete,
            working_memory=complete,
            progress_compression=complete,
            provisional_v4_candidate=complete,
        )
        with self.assertRaisesRegex(ValueError, "HIPPORAG_RETRIEVAL.*REJECTED"):
            execute_combined_provisional_pipeline(
                binding=binding(),
                causal_state={"signal": "prefix-only"},
                source_contexts={component_id: [{}] for component_id in ACTIVE_COMPONENT_IDS},
                apis=apis,
            )
        self.assertEqual(calls, ["S137_COGNITIVE_RUNTIME", "HIPPORAG_RETRIEVAL"])


if __name__ == "__main__":
    unittest.main()
