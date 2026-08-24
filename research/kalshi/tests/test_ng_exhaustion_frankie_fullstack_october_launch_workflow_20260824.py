from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import textwrap
import unittest
from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/ng_exhaustion_frankie_fullstack_october_20260824.yml"
)
MANIFEST = Path(
    "research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json"
)
MARKER = Path(
    "research/kalshi/NG_EXHAUSTION_FRANKIE_FULLSTACK_OCTOBER_LAUNCH_20260824.json"
)
TARGET_BRANCH = "chatgpt/ng-exhaustion-october-sharded-20260824"
WORKFLOW_TEST = Path(
    "research/kalshi/tests/test_ng_exhaustion_frankie_fullstack_october_launch_workflow_20260824.py"
)
RETIRED_WORKFLOWS = (
    Path(".github/workflows/ng_exhaustion_october_frankie_blind_canary_20260824.yml"),
    Path(".github/workflows/ng_exhaustion_october_frankie_blind_canary_probe_20260824.yml"),
)
FOCUSED_LAUNCH_TESTS = (
    "test_frankie_authority_knowledge_plane_20260824.py",
    "test_frankie_lane_aware_context_router_20260824.py",
    "test_frankie_full_stack_paired_lane_orchestrator_20260824.py",
    "test_frankie_full_stack_provisional_combined_pipeline_20260824.py",
    "test_frankie_provider_knowledge_tools_20260824.py",
    "test_frankie_full_stack_runtime_adapter_20260824.py",
    "test_frankie_causal_operational_context_20260824.py",
    "test_frankie_causal_runtime_tools_20260824.py",
    "test_frankie_v4_authority_runtime_validation_20260824.py",
    "test_frankie_source_inventory_cross_reference_20260824.py",
    "test_ng_exhaustion_frankie_fullstack_october_20260824.py",
    "test_ng_exhaustion_frankie_fullstack_october_launch_workflow_20260824.py",
)


class FullStackOctoberLaunchWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_trigger_is_explicit_new_marker_or_confirmed_dispatch_on_target_branch(self):
        self.assertIn("workflow_dispatch:", self.source)
        self.assertIn("confirm_full_october:", self.source)
        self.assertIn("type: boolean", self.source)
        self.assertIn(f"- {TARGET_BRANCH}", self.source)
        self.assertIn(str(MARKER), self.source)
        self.assertIn(f"refs/heads/{TARGET_BRANCH}", self.source)
        marker = json.loads(MARKER.read_text(encoding="utf-8"))
        self.assertIs(marker.get("launch_authorized"), True)
        self.assertEqual(marker.get("launch_branch"), TARGET_BRANCH)
        self.assertEqual(
            marker.get("authorized_scope"),
            "FULL_OCTOBER_2021_IDENTICAL_PREFIX_S135_CONTROL_VS_ALL_PROVISIONAL_COMBINED",
        )

    def test_obsolete_canary_workflows_are_forensic_only_and_cannot_run_jobs(self):
        for path in RETIRED_WORKFLOWS:
            source = path.read_text(encoding="utf-8")
            self.assertIn("workflow_dispatch:", source)
            self.assertNotRegex(source, re.compile(r"(?m)^\s*push:\s*$"))
            self.assertIn("if: ${{ false }}", source)
            self.assertIn("RETIRED_FORENSIC_ONLY", source)

    def test_staging_is_manifest_driven_for_predecessor_plus_all_26_october_objects(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = manifest["canonical_dbn_objects"]
        predecessor = [
            row
            for row in rows
            if row["segment"] == "20210901_20211001"
            and row["key"].endswith("glbx-mdp3-20210930.mbo.dbn.zst")
        ]
        october = [row for row in rows if row["segment"] == "20211001_20211101"]
        self.assertEqual(len(predecessor), 1)
        self.assertEqual(len(october), 26)
        self.assertEqual(len(predecessor) + len(october), 27)

        for token in (
            'manifest["canonical_dbn_objects"]',
            'row.get("segment") == predecessor_segment',
            'row.get("segment") == october_segment',
            "len(targets) != 26",
            "len(roster) != 27",
            "for index, row in enumerate(roster)",
            'row["bytes"]',
            'row["sha256"]',
            "sha256_file(destination)",
        ):
            self.assertIn(token, self.source)
        self.assertNotIn("target_key =", self.source)

    def test_packages_exact_sha_and_invokes_only_the_full_month_runner(self):
        self.assertIn('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"', self.source)
        self.assertIn('git archive --format=tar "$GITHUB_SHA"', self.source)
        self.assertIn(
            "python research/kalshi/ng_exhaustion_frankie_fullstack_october_20260824.py",
            self.source,
        )
        self.assertIn('research/kalshi/restore_substrate.py', self.source)
        self.assertIn("frankie_s135_substrate_descriptor_20260824.py", self.source)
        self.assertIn("S135_SUBSTRATE_DESCRIPTOR.json", self.source)
        for flag in ("--manifest", "--source-root", "--output-root", "--run-id"):
            self.assertIn(flag, self.source)
        self.assertNotIn("ng_exhaustion_october_frankie_v4_bridge_20260824.py", self.source)
        self.assertNotIn("frankie_bounded_3mo_parallel.py", self.source)
        self.assertNotIn("canary", self.source.lower())

    def test_identity_is_unique_and_keyed_by_sha_run_and_attempt(self):
        for token in (
            "ng-exhaustion-frankie-fullstack-october-",
            "/mnt/markets/ng_exhaustion_frankie_fullstack_october_20260824/",
            "${GITHUB_SHA}",
            "${GITHUB_RUN_ID}",
            "${GITHUB_RUN_ATTEMPT}",
            "frankie/fullstack-october-2021/launches/",
            "systemd-run --collect --unit",
            '--property=Restart=no',
        ):
            self.assertIn(token, self.source)

    def test_permanent_services_are_observed_but_never_mutated_or_required_inactive(self):
        for service in (
            "markets-frankie.service",
            "markets-frankie-reflect.service",
            "markets-frankie-reflect.timer",
            "markets-frankie-bounded-3mo.service",
        ):
            self.assertIn(service, self.source)
        self.assertIn('systemctl show "$service"', self.source)
        self.assertNotRegex(
            self.source,
            re.compile(
                r"systemctl\s+(?:start|stop|restart|try-restart|reload|enable|disable|mask|unmask|reset-failed)"
                r"[^\n]*(?:markets-frankie|permanent)",
                re.IGNORECASE,
            ),
        )
        self.assertNotIn("require inactive", self.source.lower())
        self.assertNotIn("is-active --quiet markets-frankie", self.source)

    def test_rollback_sync_dependencies_and_focused_tests_are_explicit(self):
        self.assertIn('FULLSTACK_STOP_COMMAND=systemctl stop $unit', self.source)
        self.assertIn('aws s3 sync "$output"', self.source)
        self.assertIn('aws s3 cp "$run_log"', self.source)
        self.assertIn("deploy/aws/requirements-frankie-fullstack-20260824.lock", self.source)
        requirements = Path(
            "deploy/aws/requirements-frankie-fullstack-20260824.txt"
        ).read_text(encoding="utf-8")
        self.assertIn("databento==0.81.0", requirements)
        self.assertNotIn(">=", requirements)
        self.assertIn("requirements-frankie-fullstack-ci-20260824.lock", self.source)
        self.assertIn('"$ci_venv/bin/python" -m pytest --quiet', self.source)
        for test_name in FOCUSED_LAUNCH_TESTS:
            self.assertEqual(
                self.source.count(f"research/kalshi/tests/{test_name}"),
                1,
                f"focused launch gate must run {test_name} exactly once",
            )

    def test_runtime_supply_chain_is_hash_locked_unprivileged_and_credential_scoped(self):
        build = self.source.index("Build hash-locked offline runtime package without credentials")
        publish = self.source.index("Publish exact GITHUB_SHA package")
        self.assertLess(build, publish)
        build_job = self.source[: self.source.index("  launch-fullstack-october:")]
        self.assertNotIn("AWS_ACCESS_KEY_ID: ${{ secrets.", build_job)
        for token in (
            "--require-hashes",
            "--no-index",
            "--only-binary=:all:",
            "deploy/wheelhouse",
            "requirements-frankie-fullstack-20260824.lock",
            "requirements-frankie-fullstack-ci-20260824.lock",
            "Cross the no-secret artifact boundary",
            "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
            "needs.build-and-verify.outputs.package_sha256",
            "needs.build-and-verify.outputs.wheelhouse_sha256",
            'test "$observed_package_sha" = "$expected_package_sha"',
            'test "$observed_wheelhouse_sha" = "$expected_wheelhouse_sha"',
            'useradd --system --no-create-home --shell /usr/sbin/nologin "$provider_user"',
            'runuser -u "$provider_user"',
            '--uid "$provider_user"',
            '--property=NoNewPrivileges=yes',
            '--property=ProtectSystem=strict',
            '--property=IPAddressDeny=169.254.169.254/32',
            '--property=IPAddressDeny=fd00:ec2::254/128',
            '--property="InaccessiblePaths=$aws_credential_file',
            'openai_credential_file=__OPENAI_CREDENTIAL_FILE__',
            'unset OPENAI_API_KEY MARKETS_OPENAI_API_KEY',
            '-u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN',
        ):
            self.assertIn(token, self.source)
        lock = Path("deploy/aws/requirements-frankie-fullstack-20260824.lock").read_text(
            encoding="utf-8"
        )
        rows = [line for line in lock.splitlines() if line and not line.startswith(("#", " "))]
        self.assertGreaterEqual(len(rows), 45)
        self.assertTrue(all(re.fullmatch(r"[a-z0-9-]+==[^ ]+ \\", line) for line in rows))
        self.assertGreaterEqual(lock.count("--hash=sha256:"), len(rows))
        self.assertNotIn("python - \"$wheelhouse\" \"$lock\"", self.source)
        self.assertNotIn("pip install --quiet --upgrade pip", self.source)
        self.assertNotIn("requirements-frankie.txt", self.source)
        self.assertNotIn("actions/checkout@v4", self.source)
        self.assertNotIn("actions/download-artifact@v4", self.source)
        output_syncs = re.findall(r'aws s3 sync \"\$output\"[^;\n]+', self.source)
        self.assertEqual(len(output_syncs), 2)
        self.assertTrue(all("--no-follow-symlinks" in command for command in output_syncs))
        self.assertNotRegex(self.source, re.compile(r'pip install[^\n]*(?:>=|matplotlib(?:\s|$))'))

    def test_launch_waits_for_every_evidence_gate_and_fails_closed(self):
        for event in (
            "KNOWLEDGE_MANIFEST_READY",
            "ANSWER_WALL_PREFREEZE_VERIFIED",
            "FORBIDDEN_V3_DENIED",
            "PAIRED_PREFIX_ACCEPTED",
        ):
            self.assertIn(event, self.source)
        for token in (
            '"S135_CONTROL"',
            '"FULL_PROVISIONAL_COMBINED"',
            '"gpt-5.6-sol"',
            "control_provider_response_ids",
            "combined_provider_response_ids",
            "identical_prefix_proof_hash",
            "schema_registered_count",
            "registered_block_count",
            "present_count",
            "explicit_null_count",
            "unavailable_count",
            "causal_quarantine_count",
            "same_day_realized_weather_quarantine_count",
            "same_day_realized_weather_present_count",
            "source_snapshot_leaf_count",
            "source_snapshot_leaf_hash",
            "availability_matrix_hash",
            "availability_matrix_block_count",
            "availability_matrix",
            "availability_audit",
            "audit_hash",
            "control_snapshot_hash",
            "combined_snapshot_hash",
            "provider_tool_evidence",
            "v4_governing_runtime",
            "direct_operational_execution_count",
            "superseded_equivalence_count",
            "value_state_read_invocation_count",
            "value_state_read_count",
            "value_state_read_receipt_hashes",
            "per_invocation",
            "tool_receipt_hashes",
            "evidence_journal_head_hash",
            "control_final_ledger_hash",
            "combined_final_ledger_hash",
            "helper_evidence",
            "frankie_reasoning",
            "probability_movie",
            '"S135_PRIMARY"',
            '"SHADOW_ONLY"',
            "knowledge_manifest_hash",
            "receipt_hash",
            "Traceback",
            "MODEL_DRIFT",
            "RUN_FAILED",
            "FULLSTACK_LAUNCH_GATES=PASS",
        ):
            self.assertIn(token, self.source)
        self.assertIn('ActiveState --value "$unit"', self.source)
        self.assertIn('test "$status" = Success', self.source)
        for proof in (
            'decision_state["schema_registered_count"] < 1940',
            'decision_state.get("registered_block_count") != 46',
            'decision_state.get("coverage_status") != "CANONICAL_S135_ACCEPTED"',
            'sum(status_counts) != decision_state["schema_registered_count"]',
            'present_count <= 0',
            'not expected_registered_blocks.issubset(availability_matrix)',
            'matrix_hash != expected_matrix_hash',
            'audit_hash != expected_audit_hash',
            'registered_audit.get("total") != decision_state["schema_registered_count"]',
            'all_field_audit.get("total") != decision_state.get("provider_path_count")',
            'weather_present_count != 0',
            'evidence.get("value_state_read_invocation_count") != 5',
            'value_count < 1',
            'evidence.get("value_state_read_count") != observed_value_read_count',
            'governing.get("module_count") != 15',
            'governing.get("direct_operational_execution_count") != 11',
            'governing.get("superseded_equivalence_count") != 4',
            'set(governing_modules) != expected_governing_modules',
            'control_snapshot != combined_snapshot',
            'call_count < 5',
            'len(receipt_hashes) != call_count',
            'journal_heads[0] == journal_heads[1]',
        ):
            self.assertIn(proof, self.source)

    def test_paired_prefix_gate_requires_seven_active_components_and_defers_only_meta_loop(self):
        active = (
            "S137_COGNITIVE_RUNTIME",
            "HIPPORAG_RETRIEVAL",
            "TEMPORAL_GRAPH",
            "LATS_BOUNDED_SEARCH",
            "WORKING_MEMORY",
            "PROGRESS_COMPRESSION",
            "PROVISIONAL_V4_ENGINEERING_CANDIDATE",
        )
        for component in active:
            self.assertIn(component, self.source)
        for token in (
            '"META_LOOP"',
            '"DEFERRED_NOT_YET_LAWFUL"',
            '"POST_EVIDENCE_DIAGNOSTIC"',
            '"PRE_REVEAL_PREFIX"',
            "active_provisional_component_receipt_hashes",
            "len(control_ids) < 5",
            "len(combined_ids) < 5",
            "set(control_ids) & set(combined_ids)",
            'control_ledger.get("path") == combined_ledger.get("path")',
            'wall.get("step1_sealed") is not True',
        ):
            self.assertIn(token, self.source)

    def test_launch_gate_is_initial_paired_evidence_not_full_month_global_freeze(self):
        self.assertIn('required = {', self.source)
        required_match = re.search(r"required = \{(.*?)\n          \}", self.source, re.DOTALL)
        self.assertIsNotNone(required_match)
        required = required_match.group(1)
        self.assertIn("PAIRED_PREFIX_ACCEPTED", required)
        self.assertNotIn("GLOBAL_EXPERIMENT_FROZEN", required)
        self.assertIn('test "$(systemctl show --property=ActiveState --value "$unit")" = active', self.source)

    def test_embedded_python_generator_and_remote_python_scripts_compile(self):
        match = re.search(
            r"          python - <<'PY'\n(.*?)\n          PY", self.source, re.DOTALL
        )
        self.assertIsNotNone(match)
        generator = textwrap.dedent(match.group(1))
        tree = ast.parse(generator, filename=str(WORKFLOW))
        scripts = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "credential_scope_script",
                    "stage_script",
                    "gate_script",
                    "runner_script",
                }:
                    scripts[target.id] = node.value.value
        self.assertEqual(
            set(scripts),
            {"credential_scope_script", "stage_script", "gate_script", "runner_script"},
        )
        for name in ("credential_scope_script", "stage_script", "gate_script"):
            source = scripts[name]
            compile(textwrap.dedent(source), f"<{name}>", "exec")
        subprocess.run(
            ["bash", "-n"],
            input=textwrap.dedent(scripts["runner_script"]),
            text=True,
            capture_output=True,
            check=True,
        )



if __name__ == "__main__":
    unittest.main()
