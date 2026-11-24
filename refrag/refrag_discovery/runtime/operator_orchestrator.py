from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter
from uuid import uuid4


def _utc_now_iso_compact() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

from refrag_core.prompt_builder import build_mixed_prompt
from refrag_core.retrieval import VectorIndex
from refrag_discovery.control_plane import call_control_plane_operator
from refrag_discovery.paths import ARTIFACTS_DIR, DISCOVERIES_DIR
from refrag_discovery.registry import build_default_operator_query, trace_store
from refrag_discovery.runtime import evidence_graph_builder, falsification_prioritizer, operator_decoder
from refrag_discovery.runtime import retrieval_policy_learner, spectral_chunk_encode, spectral_chunker
from refrag_discovery.runtime.types import PipelineArtifacts, RetrievedChunk, StageTrace


# Arch doc §4 mandates the discoveries/ tree at PROJECT_ROOT (not under
# artifacts/) for production runs. When the orchestrator is invoked with an
# explicit ``artifacts_dir`` (per-scenario benchmark sandboxes) we keep the
# legacy ``<artifacts_dir>/discoveries/`` and ``<artifacts_dir>/evidence_graphs/``
# layout so scenario isolation is preserved.
UNKNOWN_DOMAIN = "unknown"


def _scalar_to_embedding(value: float, dim: int) -> list[float]:
    return [float(value)] + [0.0] * (dim - 1)


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm <= 0:
        return [0.0 for _ in vector]
    return [float(value) / norm for value in vector]


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _count_edges(graph: dict, relation: str) -> int:
    return sum(1 for edge in graph.get("edges", []) if edge.get("relation") == relation)


def _reward_trend(values: list[float], window: int = 3) -> float:
    if len(values) < 2:
        return 0.0
    if len(values) <= window:
        return values[-1] - values[0]
    baseline = _average(values[:-window])
    recent = _average(values[-window:])
    return recent - baseline


def _summarize_policy_records(records: list[dict]) -> dict[str, float | int | dict[str, float]]:
    rewards = [float(record.get("reward", 0.0) or 0.0) for record in records]
    probability_valid = [float(record.get("probability_valid", 0.0) or 0.0) for record in records]
    latency = [float(record.get("pipeline_latency_s", 0.0) or 0.0) for record in records]
    policy_confidence = [float(record.get("policy_confidence", 0.0) or 0.0) for record in records]
    confidence_alignment = [float(record.get("confidence_alignment", 0.0) or 0.0) for record in records]
    evidence_density = [float(record.get("evidence_density", 0.0) or 0.0) for record in records]
    support_ratio = [float(record.get("support_ratio", 0.0) or 0.0) for record in records]
    graph_coverage = [float(record.get("graph_coverage", 0.0) or 0.0) for record in records]

    component_names: set[str] = set()
    for record in records:
        component_names.update(dict(record.get("reward_components", {})).keys())
    avg_component_scores = {
        name: round(
            _average(
                [
                    float(dict(record.get("reward_components", {})).get(name, 0.0) or 0.0)
                    for record in records
                ]
            ),
            6,
        )
        for name in sorted(component_names)
    }

    avg_reward = _average(rewards)
    avg_recent_reward = _average(rewards[-3:])
    return {
        "selection_count": len(records),
        "avg_reward": round(avg_reward, 6),
        "avg_recent_reward": round(avg_recent_reward, 6),
        "reward_trend": round(_reward_trend(rewards), 6),
        "best_reward": round(max(rewards) if rewards else 0.0, 6),
        "avg_probability_valid": round(_average(probability_valid), 6),
        "avg_pipeline_latency_s": round(_average(latency), 6),
        "avg_policy_confidence": round(_average(policy_confidence), 6),
        "avg_confidence_alignment": round(_average(confidence_alignment), 6),
        "avg_evidence_density": round(_average(evidence_density), 6),
        "avg_support_ratio": round(_average(support_ratio), 6),
        "avg_graph_coverage": round(_average(graph_coverage), 6),
        "avg_component_scores": avg_component_scores,
    }


class StageExecutionError(RuntimeError):
    def __init__(self, trace: StageTrace) -> None:
        super().__init__(trace.error or f"Stage execution failed: {trace.stage}")
        self.trace = trace


class OperatorOrchestrator:
    def __init__(self, operator_query=None, artifacts_dir: Path | None = None) -> None:
        self.operator_query = operator_query or build_default_operator_query()
        # ``artifacts_dir`` controls the sandboxing of per-scenario state. The
        # explicit-override case keeps EVERY artefact (discoveries, evidence
        # graphs, traces, policy history) under that directory so test runs
        # don't pollute the global discoveries/ store. When no override is
        # passed we use the arch-doc layout: scratch state under ARTIFACTS_DIR
        # but durable discoveries under DISCOVERIES_DIR per §4.
        self.artifacts_dir = artifacts_dir or ARTIFACTS_DIR
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._uses_default_artifacts = artifacts_dir is None

    def _discoveries_root(self) -> Path:
        """Per arch §4: discoveries/ lives at PROJECT_ROOT for production. For
        sandboxed scenarios it lives under the supplied artifacts_dir so the
        scenario stays self-contained."""
        return DISCOVERIES_DIR if self._uses_default_artifacts else (self.artifacts_dir / "discoveries")

    def execute(
        self,
        *,
        pipeline_id: str,
        data_sources: dict[str, list[float]],
        query: dict,
        task_config: dict | None = None,
        termination_config: dict | None = None,
        trace_level: str = "standard",
        domain: str = UNKNOWN_DOMAIN,
    ) -> dict:
        pipeline_started = perf_counter()
        task_config = task_config or {}
        termination_config = termination_config or {"max_iterations": 1}
        run_id = str(uuid4())
        domain_tag = str(domain or UNKNOWN_DOMAIN).strip() or UNKNOWN_DOMAIN
        artifacts = PipelineArtifacts(run_id=run_id)
        execution_waves = self.operator_query.resolve_pipeline_dag(pipeline_id)
        stage_ids = [stage_id for wave in execution_waves for stage_id in wave]
        # Fix B-2 / arch §2 ("Execute stages in order, respecting data
        # dependencies"): runtime_guarantees synthesis was an invented-knob
        # block (parallel_wave_execution_enabled, parallelism_cap_configured,
        # max_wave_width, evidence_graph_integrity_checks_enabled,
        # accumulated_graph_quarantine_enabled) that the arch doc never
        # sanctioned. Removed along with the underlying parallel-wave
        # execution machinery; stages now run sequentially within each
        # topological wave.

        resolved_versions = {
            stage_id: self.operator_query.get_manifest(stage_id).get("lineage", {}).get("version", "unknown")
            for stage_id in stage_ids
        }

        context: dict = {
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "domain": domain_tag,
            "data_sources": data_sources,
            "query": query,
            "task_config": task_config,
            "termination_config": termination_config,
            "resolved_versions": resolved_versions,
            "trace_level": trace_level,
        }

        # Arch §2 / §8 Phase 2: closed-loop falsification.
        # Step 1: initial full pass through every wave so all stage outputs
        #         (chunks, encoded chunks, query vectors, retrieval policy,
        #          falsification ranks, decoder coefficients, evidence graph)
        #         exist in `context`.
        for wave in execution_waves:
            try:
                wave_results = self._execute_wave(wave, context)
            except StageExecutionError as exc:
                artifacts.traces.append(exc.trace)
                raise
            for stage_id, stage_output, trace in wave_results:
                context[stage_id] = stage_output
                artifacts.traces.append(trace)

        # Step 2: refinement loop. Re-run the Falsification Loop stages
        # (falsification_prioritizer -> operator_decoder -> evidence_graph_builder)
        # using the prior iteration's outputs from `context`. Termination
        # signal per Greg's 2026-05-25 call: "stop when no new coefficients
        # are produced" — i.e. max |coef[N] - coef[N-1]| < delta_threshold.
        # max_iterations is only a runaway safety cap, NOT the primary
        # stopping criterion. The decoder's posterior_width stub returns a
        # constant per pipeline run (arch §8 acknowledges it as a stub
        # until 100+ training pairs), so coefficient-delta is what actually
        # tracks convergence here.
        max_iterations = max(1, int(termination_config.get("max_iterations", 100_000)))
        delta_threshold = float(
            termination_config.get("delta_threshold", 1e-6)
        )
        loop_stage_ids = (
            "falsification_prioritizer",
            "operator_decoder",
            "evidence_graph_builder",
        )
        loop_waves = [
            wave for wave in execution_waves
            if any(stage_id in wave for stage_id in loop_stage_ids)
        ]

        closed_loop_iterations = 1
        termination_condition = "single_pass_bootstrap"
        prev_coefficients = list(
            (context.get("operator_decoder") or {}).get("operator_coefficients") or []
        )
        last_delta = float("inf")
        while closed_loop_iterations < max_iterations:
            for wave in loop_waves:
                try:
                    wave_results = self._execute_wave(wave, context)
                except StageExecutionError as exc:
                    artifacts.traces.append(exc.trace)
                    raise
                for stage_id, stage_output, trace in wave_results:
                    context[stage_id] = stage_output
                    artifacts.traces.append(trace)

            closed_loop_iterations += 1

            new_coefficients = list(
                (context.get("operator_decoder") or {}).get("operator_coefficients") or []
            )
            if prev_coefficients and len(new_coefficients) == len(prev_coefficients):
                last_delta = max(
                    abs(a - b) for a, b in zip(new_coefficients, prev_coefficients)
                )
            prev_coefficients = new_coefficients

            if last_delta < delta_threshold:
                termination_condition = (
                    f"coefficients_converged "
                    f"(max_delta={last_delta:.2e} < {delta_threshold:.2e}, "
                    f"iter={closed_loop_iterations})"
                )
                break

        if (
            closed_loop_iterations >= max_iterations
            and termination_condition == "single_pass_bootstrap"
        ):
            termination_condition = (
                f"max_iterations_safety_cap "
                f"({closed_loop_iterations}/{max_iterations}, "
                f"last_delta={last_delta:.2e})"
            )

        decoder_output = context["operator_decoder"]
        graph_output = context["evidence_graph_builder"]
        total_latency_s = round(perf_counter() - pipeline_started, 4)
        # ``domain_tag`` already computed at the top of execute() so the
        # evidence-graph loader/saver can use it during stage execution.
        result = {
            "operator_coefficients": decoder_output["operator_coefficients"],
            "coefficient_posterior": decoder_output["coefficient_posterior"],
            "retrieval_policy": context["retrieval_policy_learner"],
            "evidence_graph": graph_output["graph"],
            "operator_validity_posterior": graph_output["operator_validity_posterior"],
            "evidence_graph_metadata": graph_output["metadata"],
            "discovery_recorded": True,
            "pipeline_latency_s": total_latency_s,
        }

        execution_trace = {
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "domain": domain_tag,
            "execution_waves": execution_waves,
            "stages": [
                {
                    "stage": index + 1,
                    "operator_id": trace.stage,
                    "version": resolved_versions.get(trace.stage, "unknown"),
                    "wall_time_ms": trace.wall_time_ms,
                    "input_size": trace.input_size,
                    "output_size": trace.output_size,
                    "status": trace.status,
                    "error": trace.error,
                }
                for index, trace in enumerate(artifacts.traces)
            ],
            "closed_loop_iterations": closed_loop_iterations,
            "termination_condition": termination_condition,
            "total_wall_time_ms": round(total_latency_s * 1000, 3),
            "discovery_recorded": True,
        }
        discovery_payload = {
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "domain": domain_tag,
            "result": result,
            "execution_trace": execution_trace,
        }
        # Arch §4: production runs write to
        # ``discoveries/operator_discoveries/<domain>/<run_id>.json``.
        # Sandboxed scenarios (callers that supply ``artifacts_dir=``) keep the
        # flat ``<artifacts_dir>/discoveries/`` layout — Windows benchmark
        # tmpdirs already push close to MAX_PATH=260 and the extra
        # ``operator_discoveries/<domain>/`` nesting tips them over. Domain
        # partitioning isn't useful for one-off scenario sandboxes anyway; it
        # exists to keep the durable cross-domain store comparable.
        if self._uses_default_artifacts:
            discovery_path = self._discoveries_root() / "operator_discoveries" / domain_tag
        else:
            discovery_path = self._discoveries_root()
        discovery_path.mkdir(parents=True, exist_ok=True)
        (discovery_path / f"{run_id}.json").write_text(
            json.dumps(discovery_payload, indent=2),
            encoding="utf-8",
        )
        # Fix D / arch §4: every persisted discovery updates the master
        # index.json so cross_domain_transfer_detector / evidence graph
        # consumers have a queryable map. Atomic rename for crash-safety;
        # concurrent adapter processes risk last-writer-wins on this file
        # (acceptable since each writer is appending its own run_id; the
        # worst case is dropping one parallel run's entry — caller can
        # rebuild via directory scan).
        self._update_discoveries_index(
            self._discoveries_root(),
            run_id=run_id,
            domain=domain_tag,
            relative_path=str(
                (discovery_path / f"{run_id}.json").relative_to(self._discoveries_root())
            ).replace("\\", "/"),
        )
        self._save_accumulated_evidence_graph(pipeline_id, domain_tag, graph_output["graph"])
        policy_outcome = self._record_retrieval_policy_outcome(
            pipeline_id=pipeline_id,
            query_mode=str(context["query"].get("query_mode", "from_spectral_target")),
            retrieval_policy=context["retrieval_policy_learner"],
            result=result,
        )
        if policy_outcome:
            result["retrieval_policy"].setdefault("metadata", {})
            result["retrieval_policy"]["metadata"]["last_observed_reward"] = float(policy_outcome["reward"])
            result["retrieval_policy"]["metadata"]["last_reward_components"] = dict(
                policy_outcome.get("reward_components", {})
            )
            result["retrieval_policy"]["metadata"]["last_reward_signal"] = str(
                policy_outcome.get("reward_signal", "composite")
            )
        policy_benchmark_state = self._load_retrieval_policy_benchmark()
        policy_feedback = self._build_policy_control_plane_feedback(
            pipeline_id=pipeline_id,
            query_mode=str(context["query"].get("query_mode", "from_spectral_target")),
            retrieval_policy=result["retrieval_policy"],
            policy_outcome=policy_outcome,
            policy_benchmark=policy_benchmark_state,
        )
        # Arch §3.1 mandates lineage state live under ``registry/lineage/``,
        # which ``operator_state_path("lineage", ..., artifacts_dir=None)``
        # routes to. Passing ``self.artifacts_dir`` (defaults to ARTIFACTS_DIR)
        # would short-circuit that and write to ``artifacts/control_plane/lineage/``.
        # Production mode (no explicit artifacts_dir) → pass None so registry
        # routing applies. Sandboxed scenarios → pass through self.artifacts_dir
        # so per-scenario state stays isolated.
        lineage_artifacts_dir = None if self._uses_default_artifacts else self.artifacts_dir

        # Phase 1 (arch §8 milestone "Operator state tracking active"):
        # bootstrap per-operator lifecycle state for every runtime stage
        # plus the pipeline itself. lifecycle_tracker is zero-dep (arch §6
        # Depth 0) — called without transition_to it just reads/initialises
        # the operator's state file at artifacts/control_plane/lifecycle/<op>.json.
        # Without this loop only retrieval_policy_learner was getting tracked
        # because benchmark_suite was hardcoded to it; now all 8 runtime
        # operators + pipeline get coverage.
        _runtime_operator_ids = [
            "spectral_chunker",
            "spectral_chunk_encode",
            "operator_query",
            "retrieval_policy_learner",
            "falsification_prioritizer",
            "operator_decoder",
            "evidence_graph_builder",
            "operator_orchestrator",
        ]
        lifecycle_states = {}
        for _op_id in _runtime_operator_ids + [pipeline_id]:
            lifecycle_states[_op_id] = call_control_plane_operator(
                "operator_lifecycle_tracker",
                {
                    "operator_id": _op_id,
                    "artifacts_dir": lineage_artifacts_dir,
                },
            )

        # ────────────────────────────────────────────────────────────────────
        # Fix A (deferred-bug item A, 2026-05-25): PLANE SEPARATION (Rule 1).
        #
        # Per arch §1.2 the control plane runs "between discovery runs, on
        # periodic schedules, or in the background … not latency-sensitive".
        # The runtime plane is latency-sensitive. Before this fix the
        # orchestrator was synchronously invoking SIX control-plane operators
        # inside every per-trade execute() call:
        #   - operator_benchmark_suite           [C]
        #   - pipeline_performance_optimizer     [C]
        #   - exploration_policy_controller      [C]
        #   - _persist_retrieval_policy_control_loop (synthesised from above)
        # That's a hard arch-doc violation. The adapter
        # (E:\refrag\adapters\markets_refrag_adapter.py) now fires these
        # post-bucket as the Phase 5 capstone instead, with bucket-aggregated
        # inputs.
        #
        # What stays inside execute() — bookkeeping + online learning:
        #   - operator_lifecycle_tracker (zero-dep, per arch §6 Depth 0; light)
        #   - operator_lineage_tracker   (zero-dep, per arch §6 Depth 0; light)
        #   - task_meta_learner.update_from_outcome (cross-layer; arch §1
        #     classifies it as 'X', and the update step IS an online learning
        #     signal per-outcome — moving it post-bucket would lose the
        #     per-trial credit assignment)
        #
        # ``telemetry_routed`` therefore shrinks from 6 keys to 3. Anything
        # reading the removed keys from OUTSIDE execute() must handle missing
        # keys gracefully (the adapter now provides them itself from its
        # post-bucket sweep). ``policy_feedback`` and ``policy_benchmark_state``
        # are still computed here because (a) they're cheap, and (b) the
        # retrieval-policy metadata published to ``result`` reflects per-trial
        # state — that's part of the runtime contract, not control plane.
        # ────────────────────────────────────────────────────────────────────
        telemetry_routed = {
            "operator_lifecycle_tracker": lifecycle_states,
            "operator_lineage_tracker": call_control_plane_operator(
                "operator_lineage_tracker",
                {
                    "operator_id": pipeline_id,
                    "version": str(
                        self.operator_query.get_manifest(pipeline_id).get("lineage", {}).get("version", "unknown")
                    ),
                    "schema_snapshot": self.operator_query.get_manifest(pipeline_id),
                    "performance_benchmark": {
                        "summary": {
                            "overall_score": max(0.0, 1.0 - min(1.0, total_latency_s)),
                            "health_score": max(0.0, 1.0 - min(1.0, total_latency_s / 2.0)),
                            "pipeline_latency_s": total_latency_s,
                        },
                        "execution_trace": execution_trace,
                    },
                    "artifacts_dir": lineage_artifacts_dir,
                },
            ),
            "task_meta_learner": call_control_plane_operator(
                "task_meta_learner",
                {
                    "task_description": f"{pipeline_id}:{context['query']['query_mode']}",
                    "task_features": {
                        "domain": "operator-discovery",
                        "data_type": "spectral",
                        "size": sum(len(values) for values in data_sources.values()),
                        "noise": round(
                            sum(abs(value) for values in data_sources.values() for value in values[:8])
                            / max(1, sum(min(8, len(values)) for values in data_sources.values())),
                            6,
                        ),
                    },
                    "query_mode": "update_from_outcome",
                    "task_outcome": {
                        "health_score": max(0.0, 1.0 - min(1.0, total_latency_s / 2.0)),
                        "selected_mode": result["retrieval_policy"]["selected_mode"],
                        "policy_reward": float(policy_outcome.get("reward", 0.0) if policy_outcome else 0.0),
                        "probability_valid": float(result["operator_validity_posterior"]["probability_valid"]),
                    },
                    "artifacts_dir": self.artifacts_dir,
                },
            ),
        }
        # Fix A: surface the per-trade policy_feedback so the post-bucket
        # adapter sweep can aggregate per-operator metrics across the bucket
        # without re-deriving them. ``policy_benchmark_state`` is the
        # cumulative retrieval_policy_benchmark.json snapshot AFTER this
        # trade's outcome was recorded; the adapter's bucket-end benchmark
        # call will see the same shape.
        result["retrieval_policy"].setdefault("metadata", {})
        result["retrieval_policy"]["metadata"]["policy_feedback"] = policy_feedback
        # No control_loop_state_path set in-call. The adapter post-bucket
        # writes ``retrieval_policy_control_loop.json``; subsequent BUCKET
        # runs will pick it up via _load_control_loop_state(). Within a
        # single bucket the control loop is intentionally not refreshed
        # per-trade — that was the latency cost the arch doc forbids.

        # Fix C: arch §3.2 prescribes SQLite (append-only) for execution traces.
        # trace_store handles concurrent writers (transaction-serialized) and
        # crash safety (atomic commit), replacing the prior 4-KB-bounded JSONL
        # os.write workaround. Trace shape is unchanged — payload_json column
        # preserves the trace dict verbatim.
        trace_store.append_trace(execution_trace)

        return {
            "run_id": run_id,
            "result": result,
            "execution_trace": execution_trace,
            "telemetry_routed": telemetry_routed,
            "discovery_recorded": True,
        }

    def _run_stage(self, stage_id: str, context: dict) -> dict:
        if stage_id == "spectral_chunker":
            chunks = []
            change_points: dict[str, list[int]] = {}
            for source_id, data in context["data_sources"].items():
                output = spectral_chunker.execute(
                    source_id=source_id,
                    data=data,
                    **context["task_config"].get(stage_id, {}),
                )
                chunks.extend(output["chunks"])
                change_points[source_id] = output["change_points"]
            return {
                "chunks": chunks,
                "change_points": change_points,
            }

        if stage_id == "spectral_chunk_encode":
            return spectral_chunk_encode.execute(
                chunks=context["spectral_chunker"]["chunks"],
                **context["task_config"].get(stage_id, {}),
            )

        if stage_id == "operator_query":
            query = context["query"]
            return self.operator_query.build_query_vectors(
                mode=query["query_mode"],
                candidate=query.get("candidate"),
                target_frequencies=query.get("target_frequencies"),
                target_energy=float(query.get("target_energy", 1.0)),
                evidence_state=query.get("evidence_state"),
                n_queries=int(query.get("n_queries", 1)),
                d_enc=int(context["spectral_chunk_encode"]["metadata"]["d_enc"]),
                sample_rate=float(query.get("sample_rate", 1.0)),
            )

        if stage_id == "retrieval_policy_learner":
            uncertainties = context["spectral_chunk_encode"]["embedding_uncertainty"]
            avg_uncertainty = sum(uncertainties) / max(1, len(uncertainties))
            return retrieval_policy_learner.execute(
                task_features={
                    "query_mode": context["query"]["query_mode"],
                    "chunk_count": len(context["spectral_chunker"]["chunks"]),
                    "avg_uncertainty": avg_uncertainty,
                    "artifacts_dir": self.artifacts_dir,
                },
                available_modes=["candidate_similarity", "spectral_target", "hybrid"],
                **context["task_config"].get(stage_id, {}),
            )

        if stage_id == "falsification_prioritizer":
            retrieved = self._retrieve_ranked_chunks(context)
            candidate = context["query"].get("candidate") or {
                "operator_id": "query_target",
                "spectral_signature": context["operator_query"]["query_vectors"][0],
                "coefficients": {},
            }
            # Arch §5 Falsification Loop / §6 dep table:
            # operator_decoder feeds falsification_prioritizer. On
            # iteration N+1 we pass the decoder's coefficient_posterior
            # from iteration N so falsification can BALD-prioritise
            # chunks that reduce remaining operator uncertainty per its
            # v2 manifest (acquisition_function='bald'). On the first
            # iteration this key is absent → falsification falls back
            # to divergence ranking (arch §8 Phase 2: 'Divergence
            # ranking first').
            decoder_state = context.get("operator_decoder") or {}
            operator_posterior = decoder_state.get("coefficient_posterior")
            return falsification_prioritizer.execute(
                candidate_operator=candidate,
                dataset_chunks=retrieved,
                top_k=int(context["query"].get("top_k", 8)),
                operator_posterior=operator_posterior,
                **context["task_config"].get(stage_id, {}),
            )

        if stage_id == "operator_decoder":
            mixed_prompt = self._build_prefill(context)
            return operator_decoder.execute(
                prefill_embeds=mixed_prompt.prefill_embeds,
                prefill_mask=mixed_prompt.attention_mask,
                **context["task_config"].get(stage_id, {}),
            )

        if stage_id == "evidence_graph_builder":
            evidence_items = list(context.get("falsification_prioritizer", {}).get("ranked_chunks", []))
            evidence_items.append(context["operator_decoder"])
            stage_config = dict(context["task_config"].get(stage_id, {}))
            existing_graph_state = self._load_accumulated_evidence_graph_state(
                context["pipeline_id"], context.get("domain", UNKNOWN_DOMAIN)
            )
            stage_config.setdefault(
                "existing_graph",
                existing_graph_state["graph"],
            )
            output = evidence_graph_builder.execute(
                evidence_items=evidence_items,
                graph_id=context.get("run_id", str(uuid4())),
                **stage_config,
            )
            output.setdefault("metadata", {})
            output["metadata"]["existing_graph_status"] = str(existing_graph_state["status"])
            if existing_graph_state.get("quarantined_path"):
                output["metadata"]["quarantined_existing_graph_path"] = str(
                    existing_graph_state["quarantined_path"]
                )
            return output

        raise NotImplementedError(f"Stage not implemented: {stage_id}")

    def _execute_wave(self, wave: list[str], context: dict) -> list[tuple[str, dict, StageTrace]]:
        # Fix B-2 / arch §2: "Execute stages in order, respecting data
        # dependencies." Sequential execution within each topological wave.
        # The prior ThreadPoolExecutor + parallel_safe manifest constraint
        # were invented knobs the arch doc never sanctioned; if wave-level
        # parallelism becomes a real concern later, pipeline_performance_optimizer
        # is the operator that should propose it post-bucket (Rule 10).
        return [self._execute_stage(stage_id, context) for stage_id in wave]

    def _execute_stage(self, stage_id: str, context: dict) -> tuple[str, dict, StageTrace]:
        started = perf_counter()
        input_size = self._estimate_input_size(context, stage_id)
        try:
            stage_output = self._run_stage(stage_id, context)
            trace = StageTrace(
                stage=stage_id,
                wall_time_ms=round((perf_counter() - started) * 1000, 3),
                input_size=input_size,
                output_size=self._estimate_output_size(stage_output),
                status="success",
            )
            return stage_id, stage_output, trace
        except Exception as exc:
            trace = StageTrace(
                stage=stage_id,
                wall_time_ms=round((perf_counter() - started) * 1000, 3),
                input_size=input_size,
                output_size=0,
                status="error",
                error=str(exc),
            )
            raise StageExecutionError(trace) from exc

    # Fix B-2 / arch §2: _wave_can_run_parallel, _parallelism_cap, and
    # _runtime_guarantees were removed. They synthesized knobs the spec
    # doesn't define (parallel_wave_execution_enabled, max_parallel_stages,
    # parallel_safe, etc.). Stages execute sequentially per arch §2; if a
    # post-bucket optimization wants to propose batching, that belongs in
    # pipeline_performance_optimizer (Rule 10).

    def _accumulated_evidence_graph_path(self, pipeline_id: str, domain: str) -> Path:
        """Arch §4: production accumulated evidence graphs are organised
        per-domain (``quantum_evidence.json``, ``seismic_evidence.json``, ...)
        so cross-domain transfer detection can compare like-with-like without
        mashing pipelines' outputs together. Sandboxed scenarios keep the
        per-``pipeline_id`` layout — only one scenario runs at a time, and the
        path-length budget under deep pytest tmpdirs is tight (MAX_PATH=260).

        Mapping pipelines back to their evidence file is documented in
        ``discoveries/README.md``.
        """
        if self._uses_default_artifacts:
            domain_tag = str(domain or UNKNOWN_DOMAIN).strip() or UNKNOWN_DOMAIN
            return self._discoveries_root() / "evidence_graphs" / f"{domain_tag}_evidence.json"
        return self.artifacts_dir / "evidence_graphs" / f"{pipeline_id}.json"

    def _quarantine_accumulated_evidence_graph(self, path: Path) -> Path:
        invalid_path = path.with_suffix(".invalid.json")
        if invalid_path.exists():
            invalid_path.unlink()
        path.replace(invalid_path)
        return invalid_path

    def _load_accumulated_evidence_graph_state(
        self, pipeline_id: str, domain: str = UNKNOWN_DOMAIN
    ) -> dict[str, object]:
        path = self._accumulated_evidence_graph_path(pipeline_id, domain)
        state: dict[str, object] = {
            "path": str(path),
            "status": "missing",
            "graph": None,
        }
        if not path.exists():
            return state
        try:
            graph = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            invalid_path = self._quarantine_accumulated_evidence_graph(path)
            state["status"] = "corrupt_json"
            state["quarantined_path"] = str(invalid_path)
            return state

        errors = evidence_graph_builder.validate_runtime_graph(graph, require_claim=False)
        if errors:
            invalid_path = self._quarantine_accumulated_evidence_graph(path)
            state["status"] = "invalid_structure"
            state["quarantined_path"] = str(invalid_path)
            state["errors"] = list(errors)
            return state

        state["status"] = "loaded"
        state["graph"] = graph
        return state

    def _save_accumulated_evidence_graph(
        self, pipeline_id: str, domain: str, graph: dict
    ) -> None:
        errors = evidence_graph_builder.validate_runtime_graph(graph)
        if errors:
            raise ValueError(f"Refusing to persist invalid accumulated evidence graph: {'; '.join(errors)}")
        path = self._accumulated_evidence_graph_path(pipeline_id, domain)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="graph-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(graph, indent=2))
            os.replace(temp_name, path)
        except Exception:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
            raise

    def _update_discoveries_index(
        self,
        discoveries_root: Path,
        *,
        run_id: str,
        domain: str,
        relative_path: str,
    ) -> None:
        """Append a discovery to ``discoveries/index.json`` per arch §4.

        Atomic rename via tempfile + os.replace (Windows-safe). Concurrent
        adapter processes can race on the read-modify-write; we accept
        last-writer-wins because each writer is appending an independent
        run_id (the index can be rebuilt via directory scan if needed).
        """
        index_path = discoveries_root / "index.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index: dict = {}
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
                if not isinstance(index, dict):
                    index = {}
            except json.JSONDecodeError:
                # Corrupt index — quarantine and start fresh. Same pattern
                # as the evidence graph quarantine; the directory contents
                # remain truth, the index is a derived cache.
                invalid = index_path.with_suffix(".invalid.json")
                if invalid.exists():
                    invalid.unlink()
                index_path.replace(invalid)
                index = {}
        # Preserve any existing legacy keys (e.g. ``by_domain``) and add the
        # arch §4 ``by_run_id`` map. Single source of truth = file system,
        # so adding new keys is safe.
        by_run_id = dict(index.get("by_run_id", {}))
        by_run_id[run_id] = {
            "domain": domain,
            "path": relative_path,
            "timestamp": _utc_now_iso_compact(),
        }
        index["by_run_id"] = by_run_id
        # Maintain by_domain legacy list too (the codebase already wrote it).
        by_domain = dict(index.get("by_domain", {}))
        domain_list = list(by_domain.get(domain, []))
        if run_id not in domain_list:
            domain_list.append(run_id)
        by_domain[domain] = domain_list
        index["by_domain"] = by_domain

        fd, temp_name = tempfile.mkstemp(prefix="index-", suffix=".tmp", dir=index_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(index, indent=2, sort_keys=True))
            os.replace(temp_name, index_path)
        except Exception:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
            raise

    def _load_retrieval_policy_benchmark(self) -> dict:
        path = self.artifacts_dir / "retrieval_policy_benchmark.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    # Fix A (2026-05-25): _persist_retrieval_policy_control_loop MOVED to
    # ``refrag_discovery/control_plane/pipeline_performance_optimizer.py``
    # as ``synthesize_retrieval_policy_control_loop`` per Rule 1 (Plane
    # Separation) + Rule 10 (Orchestrator Executes, Does Not Plan).
    # The adapter invokes it post-bucket — see markets_refrag_adapter.py
    # Phase 5 capstone block.

    def _build_policy_control_plane_feedback(
        self,
        *,
        pipeline_id: str,
        query_mode: str,
        retrieval_policy: dict,
        policy_outcome: dict | None,
        policy_benchmark: dict,
    ) -> dict:
        selected_mode = str(retrieval_policy.get("selected_mode", ""))
        benchmark_summary = dict(policy_benchmark.get("summary", {}))
        mode_metrics = {
            str(mode): dict(metrics)
            for mode, metrics in dict(policy_benchmark.get("mode_metrics", {})).items()
        }
        query_mode_metrics = {
            str(mode): dict(metrics)
            for mode, metrics in dict(policy_benchmark.get("query_mode_metrics", {})).items()
        }
        selected_mode_metrics = dict(mode_metrics.get(selected_mode, {}))
        selected_query_mode_metrics = dict(query_mode_metrics.get(query_mode, {}))
        component_scores = dict(benchmark_summary.get("avg_component_scores", {}))
        overall_score = float(benchmark_summary.get("avg_reward", 0.0) or 0.0)
        robustness_score = float(selected_mode_metrics.get("avg_probability_valid", overall_score) or overall_score)
        efficiency_score = float(component_scores.get("efficiency", 0.0) or 0.0)
        query_mode_best_modes = {
            mode: str(metrics.get("best_mode", ""))
            for mode, metrics in query_mode_metrics.items()
        }

        pending_tasks: list[dict[str, float | str]] = []
        gaps: list[dict[str, float | str]] = []
        for mode, metrics in mode_metrics.items():
            selection_count = int(metrics.get("selection_count", 0) or 0)
            reward_trend = float(metrics.get("reward_trend", 0.0) or 0.0)
            if selection_count < 2:
                pending_tasks.append({"task": f"benchmark_mode:{mode}", "priority": 0.82})
                gaps.append({"target": mode, "severity": 0.8})
            elif reward_trend < 0.0:
                pending_tasks.append(
                    {"task": f"stabilize_mode:{mode}", "priority": round(min(1.0, 0.74 + abs(reward_trend)), 4)}
                )

        for observed_query_mode, metrics in query_mode_metrics.items():
            history_length = int(metrics.get("history_length", 0) or 0)
            if history_length < 2:
                pending_tasks.append({"task": f"expand_query_mode:{observed_query_mode}", "priority": 0.79})
                gaps.append({"target": observed_query_mode, "severity": 0.76})

        if overall_score < 0.65:
            pending_tasks.insert(0, {"task": "tune_reward_model:retrieval_policy", "priority": 0.88})

        operator_metrics = {
            "overall_score": round(overall_score, 6),
            "robustness_score": round(robustness_score, 6),
            "efficiency_score": round(efficiency_score, 6),
            "selected_mode": selected_mode,
            "reward_signal": str(
                retrieval_policy.get("metadata", {}).get(
                    "last_reward_signal",
                    retrieval_policy.get("metadata", {}).get("reward_signal", "composite"),
                )
            ),
            "selection_count": int(selected_mode_metrics.get("selection_count", 0) or 0),
            "reward_trend": round(float(selected_mode_metrics.get("reward_trend", 0.0) or 0.0), 6),
            "query_mode_best_modes": query_mode_best_modes,
            "mode_metrics": mode_metrics,
        }
        if policy_outcome:
            operator_metrics["latest_outcome"] = {
                "query_mode": query_mode,
                "reward": round(float(policy_outcome.get("reward", 0.0) or 0.0), 6),
                "reward_components": dict(policy_outcome.get("reward_components", {})),
            }

        exploration_state = {
            "pending_tasks": pending_tasks,
            "gap_report": {"gaps": gaps},
            "resources": {
                "pipeline_id": pipeline_id,
                "query_mode": query_mode,
                "selected_mode": selected_mode,
                "history_length": int(policy_benchmark.get("history_length", 0) or 0),
            },
            "policy_benchmark": policy_benchmark,
            "query_mode_context": {
                "current_query_mode": query_mode,
                "best_mode": str(selected_query_mode_metrics.get("best_mode", "")),
            },
        }
        return {
            "operator_metrics": operator_metrics,
            "exploration_state": exploration_state,
        }

    def _record_retrieval_policy_outcome(
        self,
        *,
        pipeline_id: str,
        query_mode: str,
        retrieval_policy: dict,
        result: dict,
    ) -> dict | None:
        selected_mode = str(retrieval_policy.get("selected_mode", ""))
        if not selected_mode:
            return None
        probability_valid = float(result["operator_validity_posterior"]["probability_valid"])
        evidence_graph = result["evidence_graph"]
        node_count = len(evidence_graph.get("nodes", []))
        edge_count = len(evidence_graph.get("edges", []))
        support_edges = _count_edges(evidence_graph, "supports")
        contradiction_edges = _count_edges(evidence_graph, "contradicts")
        evidence_density = edge_count / max(1.0, node_count * 2.0)
        support_ratio = support_edges / max(1.0, support_edges + contradiction_edges)
        graph_coverage = min(1.0, node_count / 12.0)
        latency_score = max(0.0, 1.0 - min(1.0, float(result["pipeline_latency_s"])))
        policy_confidence = float(retrieval_policy.get("policy_confidence", 0.0) or 0.0)
        confidence_alignment = max(0.0, 1.0 - abs(policy_confidence - probability_valid))
        reward_signal = str(retrieval_policy.get("metadata", {}).get("reward_signal", "composite"))
        reward_weights = retrieval_policy_learner.reward_component_weights(reward_signal)
        reward_components = {
            "quality": round(probability_valid, 6),
            "evidence": round(min(1.0, evidence_density), 6),
            "consistency": round(support_ratio, 6),
            "coverage": round(graph_coverage, 6),
            "efficiency": round(latency_score, 6),
            "calibration": round(confidence_alignment, 6),
        }
        reward = round(
            sum(reward_components[name] * float(weight) for name, weight in reward_weights.items()),
            6,
        )

        history_path = self.artifacts_dir / "policy_history.jsonl"
        history_entry = {
            "pipeline_id": pipeline_id,
            "query_mode": query_mode,
            "selected_mode": selected_mode,
            "policy_confidence": policy_confidence,
            "reward_signal": reward_signal,
            "reward": reward,
            "reward_components": reward_components,
            "reward_weights": reward_weights,
            "probability_valid": probability_valid,
            "pipeline_latency_s": float(result["pipeline_latency_s"]),
            "graph_nodes": node_count,
            "graph_edges": edge_count,
            "support_edges": support_edges,
            "contradiction_edges": contradiction_edges,
            "evidence_density": round(evidence_density, 6),
            "support_ratio": round(support_ratio, 6),
            "graph_coverage": round(graph_coverage, 6),
            "confidence_alignment": round(confidence_alignment, 6),
        }
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(history_entry) + "\n")

        records = [
            json.loads(line)
            for line in history_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        mode_metrics: dict[str, dict[str, float | int | dict[str, float]]] = {}
        for mode in sorted({str(record.get("selected_mode", "")) for record in records if record.get("selected_mode")}):
            mode_records = [record for record in records if str(record.get("selected_mode", "")) == mode]
            mode_metrics[mode] = _summarize_policy_records(mode_records)

        query_mode_metrics: dict[str, dict[str, object]] = {}
        for record_query_mode in sorted(
            {str(record.get("query_mode", "")) for record in records if record.get("query_mode")}
        ):
            query_records = [
                record for record in records if str(record.get("query_mode", "")) == record_query_mode
            ]
            query_mode_mode_metrics: dict[str, dict[str, float | int | dict[str, float]]] = {}
            for mode in sorted(
                {
                    str(record.get("selected_mode", ""))
                    for record in query_records
                    if record.get("selected_mode")
                }
            ):
                query_mode_mode_metrics[mode] = _summarize_policy_records(
                    [record for record in query_records if str(record.get("selected_mode", "")) == mode]
                )
            best_mode = ""
            if query_mode_mode_metrics:
                best_mode = max(
                    query_mode_mode_metrics.items(),
                    key=lambda item: float(dict(item[1]).get("avg_reward", 0.0) or 0.0),
                )[0]
            query_mode_metrics[record_query_mode] = {
                "history_length": len(query_records),
                "best_mode": best_mode,
                "mode_metrics": query_mode_mode_metrics,
            }

        benchmark_summary = {
            "pipeline_id": pipeline_id,
            "history_length": len(records),
            "reward_model": {
                "version": "v2",
                "latest_signal": reward_signal,
                "component_weights": reward_weights,
                "components": list(reward_weights.keys()),
            },
            "summary": _summarize_policy_records(records),
            "mode_metrics": {
                mode: dict(metrics)
                for mode, metrics in mode_metrics.items()
            },
            "query_mode_metrics": query_mode_metrics,
        }
        benchmark_path = self.artifacts_dir / "retrieval_policy_benchmark.json"
        benchmark_path.write_text(json.dumps(benchmark_summary, indent=2), encoding="utf-8")
        return history_entry

    def _retrieve_ranked_chunks(self, context: dict) -> list[RetrievedChunk]:
        encoded_chunks = context["spectral_chunk_encode"]["encoded_chunks"]
        embeddings = [_normalize_vector(item.embedding) for item in encoded_chunks]
        if not embeddings:
            return []
        index = VectorIndex(dim=len(embeddings[0]), backend="python")
        index.add(embeddings)
        retrieved_scores: dict[int, float] = {}
        top_k = int(context["query"].get("top_k", 8))
        selected_mode = context.get("retrieval_policy_learner", {}).get("selected_mode", "hybrid")
        query_vectors = context["operator_query"]["query_vectors"]
        if selected_mode != "hybrid" and query_vectors:
            query_vectors = [query_vectors[0]]

        for query_vector in query_vectors:
            normalized_query = _normalize_vector(query_vector)
            for hit in index.search(normalized_query, top_k=min(top_k, len(embeddings))):
                weighted_score = hit.score
                uncertainty = encoded_chunks[hit.idx].uncertainty
                if selected_mode == "candidate_similarity":
                    weighted_score = hit.score * (1.0 - uncertainty / 2.0)
                elif selected_mode == "spectral_target":
                    weighted_score = hit.score * (1.0 + uncertainty / 4.0)
                weighted_score = max(0.0, min(1.0, weighted_score))
                current = retrieved_scores.get(hit.idx)
                if current is None or weighted_score > current:
                    retrieved_scores[hit.idx] = round(weighted_score, 6)

        ranked_indices = sorted(retrieved_scores.items(), key=lambda item: item[1], reverse=True)
        return [
            RetrievedChunk(
                chunk=encoded_chunks[index].chunk,
                embedding=encoded_chunks[index].embedding,
                score=score,
                rank=rank,
            )
            for rank, (index, score) in enumerate(ranked_indices)
        ]

    def _build_prefill(self, context: dict):
        prioritized = context["falsification_prioritizer"]["ranked_chunks"]
        d_enc = int(context["spectral_chunk_encode"]["metadata"]["d_enc"])
        expand_budget = int(context["query"].get("expand_budget", 4))
        expand_indices = set(range(min(expand_budget, len(prioritized))))
        return build_mixed_prompt(
            query_token_embeds=context["operator_query"]["query_vectors"],
            chunk_embeds=[item.embedding for item in prioritized],
            chunk_token_embeds=[
                [_scalar_to_embedding(value, d_enc) for value in item.chunk.values[: min(16, len(item.chunk.values))]]
                for item in prioritized
            ],
            expand_indices=expand_indices,
        )

    def _estimate_input_size(self, context: dict, stage_id: str) -> int:
        if stage_id == "spectral_chunker":
            return sum(len(values) for values in context["data_sources"].values())
        if stage_id == "spectral_chunk_encode":
            return len(context["spectral_chunker"]["chunks"])
        if stage_id == "operator_query":
            return len(context["query"])
        if stage_id == "retrieval_policy_learner":
            return len(context["spectral_chunk_encode"]["encoded_chunks"])
        if stage_id == "falsification_prioritizer":
            return len(context["spectral_chunk_encode"]["encoded_chunks"])
        if stage_id == "operator_decoder":
            return len(context["falsification_prioritizer"]["ranked_chunks"])
        if stage_id == "evidence_graph_builder":
            return len(context["falsification_prioritizer"]["ranked_chunks"]) + 1
        return 0

    def _estimate_output_size(self, output: dict) -> int:
        if "chunks" in output:
            return len(output["chunks"])
        if "encoded_chunks" in output:
            return len(output["encoded_chunks"])
        if "query_vectors" in output:
            return len(output["query_vectors"])
        if "ranked_chunks" in output:
            return len(output["ranked_chunks"])
        if "operator_coefficients" in output:
            return len(output["operator_coefficients"])
        if "graph" in output:
            return len(output["graph"]["nodes"])
        return len(output)
