#!/usr/bin/env python3
"""Temporary Claude Code operator for the existing Frankie blind/refine framework.

This is intentionally NOT a permanent Frankie backend. It leaves the provider registry,
spawn.py, brain, schemas, serving policy, masks, thresholds, and decision settings unchanged.
Claude Code receives the already-prepared Frankie packet, reasons over it, and returns the
existing structured output. Remove this file/use-path to remove the temporary substitution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_group_forecast_s118 as base  # noqa: E402
import frankie_s118_redo as s120  # noqa: E402
import frankie_s121_curve_restore as s121  # noqa: E402
from frankie_backends import extract_json_object  # noqa: E402
from frankie_core import verify_original_spawn  # noqa: E402
from frankie_packet_compact_s120 import (  # noqa: E402
    assert_frankie_invariants,
    compact_packet_json,
)

TEMP_BACKEND_NAME = "claude-code-subscription-temp"
DEFAULT_DISALLOWED_TOOLS = (
    "Bash,Read,Write,Edit,MultiEdit,Glob,Grep,WebFetch,WebSearch,NotebookEdit"
)

OPERATOR_GUARD = r"""
TEMPORARY CLAUDE OPERATOR CONTRACT FOR FRANKIE

You are temporarily operating the EXISTING Frankie forecasting framework. You are not
designing, configuring, optimizing, or editing Frankie.

NON-NEGOTIABLE:
- DO NOT change, prune, rank-gate, hide, truncate, summarize-away, reconfigure, rewrite,
  override, or reinterpret the data surface or settings Frankie is allowed to see.
- DO NOT change the brain, schema, masks, thresholds, timing rules, ownership rules,
  decision settings, field inventory, output contract, or specialist assignments.
- The complete packet supplied to you is the authority. All supplied fields and all
  supplied play bodies remain available to Frankie. You decide relevance in your reasoning;
  you do not alter availability.
- Respect the causal cutoff. In the blind phase, future/actual target-price information is
  unavailable by design and must remain unavailable. Never infer or reconstruct a masked
  future target curve from later information.
- A-82 isolation remains binding. Never weaken it.
- Never modify spawn.py or any repository file. You have no repository-write task here.
- Do not use tools. Do not browse, read files, execute shell commands, or obtain outside data.
- Do not fabricate missing fields, prices, timestamps, thresholds, coefficients, or evidence.
- Return ONLY the JSON object required by the canonical Frankie prompt/schema.
- Never enable execution authority.

For BLIND packets: make the forecast from the full causal packet, brain, schema and role
material exactly as supplied. The blind artifact is immutable after it is written.

For REFINE packets: the blind artifact is historical evidence and MUST NOT be edited. Use the
explicitly revealed actual only for posterior diagnosis/refinement under the canonical RFN-1
contract. Do not retroactively alter the blind call.
""".strip()

_PROVIDER_ENV_KEYS = {
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_BASE_URL",
    "ANTHROPIC_VERTEX_PROJECT_ID",
    "CLOUD_ML_REGION",
}


class ClaudeOperatorStop(base.ForecastStop):
    pass


def _subscription_env() -> dict[str, str]:
    """Force Claude Code toward its stored Claude-app subscription auth, not API/cloud routing."""
    env = dict(os.environ)
    for key in _PROVIDER_ENV_KEYS:
        env.pop(key, None)
    return env


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _full_brain_guard(packet: Mapping[str, Any], *, blind: bool) -> dict[str, Any]:
    brain = packet.get("brain_view_served")
    if not isinstance(brain, Mapping):
        raise ClaudeOperatorStop("brain_view_served missing from Claude packet")
    plays = brain.get("plays")
    serving = brain.get("_frankie_serving")
    if not isinstance(plays, Mapping) or not isinstance(serving, Mapping):
        raise ClaudeOperatorStop("full Frankie brain/serving telemetry missing from Claude packet")
    canonical = int(serving.get("canonical_plays_total", -1))
    served = int(serving.get("full_plays_served", -1))
    if canonical != 90 or served != 90 or len(plays) != 90:
        raise ClaudeOperatorStop(
            f"temporary Claude seam refuses reduced brain: canonical={canonical} "
            f"served={served} bodies={len(plays)}"
        )
    if blind and packet.get("realized_outcome_in_packet") is not False:
        raise ClaudeOperatorStop("blind Claude packet attempted to carry realized outcome")
    return {"canonical_plays": canonical, "served_plays": served, "blind": blind}


def _claude_command(system_prompt: str) -> list[str]:
    exe = os.environ.get("FRANKIE_CLAUDE_CLI", "claude")
    cmd = [
        exe,
        "-p",
        "Return the required Frankie JSON using the complete packet supplied on stdin.",
        "--output-format",
        "json",
        "--max-turns",
        "1",
        "--permission-mode",
        "plan",
        "--disallowedTools",
        os.environ.get("FRANKIE_CLAUDE_DISALLOWED_TOOLS", DEFAULT_DISALLOWED_TOOLS),
        "--system-prompt",
        system_prompt,
    ]
    model = os.environ.get("FRANKIE_CLAUDE_MODEL", "").strip()
    if model:
        cmd.extend(["--model", model])
    return cmd


def claude_generate(packet: Mapping[str, Any], *, phase: str) -> Mapping[str, Any]:
    """Send one immutable prepared packet to Claude Code and parse only the model JSON result."""
    phase_norm = phase.strip().lower()
    if phase_norm not in {"blind", "refine"}:
        raise ClaudeOperatorStop(f"unknown Claude operator phase: {phase!r}")
    blind = phase_norm == "blind"
    _full_brain_guard(packet, blind=blind)

    if blind:
        compact = compact_packet_json(packet)
        assert_frankie_invariants(packet, compact)
    else:
        compact = json.dumps(dict(packet), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if json.loads(compact) != dict(packet):
            raise ClaudeOperatorStop("refine packet lossless round-trip failed")

    before_hash = _sha256_text(compact)
    system_prompt = (
        base.MODEL_INSTRUCTIONS.rstrip()
        + "\n\n"
        + OPERATOR_GUARD
        + f"\n\nCURRENT PHASE: {phase_norm.upper()}"
    )
    timeout = int(os.environ.get("FRANKIE_CLAUDE_TIMEOUT_SECONDS", "900"))

    try:
        with tempfile.TemporaryDirectory(prefix="frankie-claude-readonly-") as tmp:
            done = subprocess.run(
                _claude_command(system_prompt),
                input=compact,
                cwd=tmp,
                env=_subscription_env(),
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
    except FileNotFoundError as exc:
        raise ClaudeOperatorStop(
            "Claude Code CLI not found. Install/login to Claude Code with the Claude app "
            "subscription, or set FRANKIE_CLAUDE_CLI."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ClaudeOperatorStop("Claude Code temporary Frankie invocation timed out") from exc

    after = (
        compact_packet_json(packet)
        if blind
        else json.dumps(dict(packet), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    if _sha256_text(after) != before_hash:
        raise ClaudeOperatorStop("Frankie packet changed across Claude invocation")

    if done.returncode != 0:
        err = (done.stderr or done.stdout or "").strip()[-3000:]
        raise ClaudeOperatorStop(f"Claude Code exited {done.returncode}: {err}")

    try:
        envelope = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise ClaudeOperatorStop(f"Claude Code did not return its JSON envelope: {exc}") from exc
    if not isinstance(envelope, dict) or envelope.get("is_error") is True:
        raise ClaudeOperatorStop("Claude Code returned an error result envelope")
    result_text = envelope.get("result")
    if not isinstance(result_text, str) or not result_text.strip():
        raise ClaudeOperatorStop("Claude Code JSON envelope is missing result text")
    result = extract_json_object(result_text)
    if result.get("execution_enabled") is True or result.get("execution_authority") is True:
        raise ClaudeOperatorStop("Claude output attempted to enable execution")
    return result


def _blind_invoke(packet: dict[str, Any], backend_name: str) -> Mapping[str, Any]:
    if backend_name != TEMP_BACKEND_NAME:
        raise ClaudeOperatorStop(f"unexpected backend at temporary Claude seam: {backend_name!r}")
    return claude_generate(packet, phase="blind")


def install() -> None:
    """Install only current Frankie guards plus the temporary inference substitution."""
    s121.install()
    base._invoke = _blind_invoke


def forecast_groups(groups: list[str], namespace: str, *, resume: bool) -> list[dict[str, Any]]:
    """Blind phase only. This function never calls score_group/_actual_by_day."""
    install()
    return [
        base.run_group(gid, namespace, TEMP_BACKEND_NAME, resume=resume)
        for gid in groups
    ]


def score_groups(groups: list[str], namespace: str) -> list[dict[str, Any]]:
    """Reveal/score only after blind artifacts have been frozen."""
    s121.install()
    return [base.score_group(gid, namespace) for gid in groups]


def _blind_path(namespace: str, gid: str, spec: str, day: str) -> Path:
    return base.FORECASTS / namespace / f"grp{gid[1:]}_{spec}_{day}.json"


def refine_group(gid: str, namespace: str, *, resume: bool = True) -> dict[str, Any]:
    """Canonical RFN-1 posterior pass. It cannot run until every blind day is already frozen."""
    install()
    days = list(base.gc.GROUPS[gid]["days"])
    owners = base.gc.owner_map(gid)

    blind_paths = [_blind_path(namespace, gid, owners[day], day) for day in days]
    missing = [str(p.relative_to(HERE)) for p in blind_paths if not p.is_file()]
    if missing:
        raise ClaudeOperatorStop(
            "refine refused before full blind group is frozen; missing: " + ", ".join(missing)
        )

    # OUTCOME ACCESS STARTS ONLY AFTER the full blind-file precheck above.
    actual = base._actual_by_day(gid)
    written: list[str] = []
    for day in days:
        spec = owners[day]
        out = base.FORECASTS / namespace / "refine" / f"grp{gid[1:]}_{spec}_{day}_refine.json"
        if resume and out.is_file():
            written.append(str(out.relative_to(HERE)))
            continue

        prompt = base._emit_prompt(
            "RFN-1",
            gid,
            day=day,
            spec=spec,
            namespace=namespace,
            allow_bridge_deviation=True,
        )
        view_path = base._build_role_view(gid, day, namespace)
        view = s120.full_brain(base._read_json(view_path))
        blind_payload = base._read_json(_blind_path(namespace, gid, spec, day))
        actual_row = actual.get(day)
        if not isinstance(actual_row, Mapping):
            raise ClaudeOperatorStop(f"{gid} {day}: actual missing for refine")

        packet = {
            "packet_version": "claude-temp-refine.1",
            "phase": "REFINE",
            "group": gid,
            "day": day,
            "specialist": spec,
            "template": "RFN-1",
            "canonical_prompt": prompt,
            "canonical_role_files": {
                "shared": base.ROLE_SHARED.read_text(encoding="utf-8"),
                "specialist": base.ROLE_SPEC[spec].read_text(encoding="utf-8"),
            },
            "causal_slice": base._read_json(base._slice_path(gid, day)),
            "brain_view_served": view,
            "blind_forecast_immutable": blind_payload,
            "realized_outcome_in_packet": True,
            "realized_outcome_revealed_after_blind": dict(actual_row),
            "operator_policy": {
                "provider": TEMP_BACKEND_NAME,
                "frankie_settings_mutable": False,
                "blind_artifact_mutable": False,
                "full_brain_available": True,
                "coordinator_filtering_allowed": False,
            },
        }
        payload = dict(claude_generate(packet, phase="refine"))
        if payload.get("execution_enabled") is True or payload.get("execution_authority") is True:
            raise ClaudeOperatorStop(f"{gid} {day}: refine attempted to enable execution")
        base._atomic_json(out, payload)
        written.append(str(out.relative_to(HERE)))

    return {"group": gid, "namespace": namespace, "refinements": written}


def preflight(groups: list[str], namespace: str) -> list[dict[str, Any]]:
    install()
    return [base.preflight_group(gid, namespace) for gid in groups]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=("preflight", "forecast", "score", "refine"),
        help="keep blind forecast, reveal/score, and posterior refine as separate phases",
    )
    parser.add_argument("groups", nargs="*", default=list(base.ALLOWED_GROUPS))
    parser.add_argument("--namespace", default="frankie_claude_temp")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    try:
        verify_original_spawn()
        if args.phase == "preflight":
            result = preflight(args.groups, args.namespace)
        elif args.phase == "forecast":
            result = forecast_groups(args.groups, args.namespace, resume=not args.no_resume)
        elif args.phase == "score":
            result = score_groups(args.groups, args.namespace)
        else:
            result = [
                refine_group(gid, args.namespace, resume=not args.no_resume)
                for gid in args.groups
            ]
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
