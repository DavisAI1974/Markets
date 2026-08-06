"""Pluggable slow-path reasoning backends for Frankie.

Bedrock and OpenAI are independent lanes over the same immutable event package. Neither
backend receives a tool, shell, credential, order route, or write authority. Both must
return the same strict JSON contract; the deterministic core adjudicates disagreement.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping, Protocol

from frankie_core import BackendError, FrankieConfig, GateStop

MAX_MODEL_TEXT = 250_000


class ReasoningBackend(Protocol):
    name: str

    def generate(self, *, instructions: str, prompt: str) -> Mapping[str, Any]: ...


def redact_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    text = re.sub(r"AKIA[0-9A-Z]{12,}", "[REDACTED_AWS_KEY]", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[REDACTED_OPENAI_KEY]", text)
    return text[:2000]


def extract_json_object(text: str) -> Mapping[str, Any]:
    if len(text) > MAX_MODEL_TEXT:
        raise BackendError(f"model output too large: {len(text)} characters")
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise BackendError("model did not return a JSON object")
        try:
            value = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise BackendError(f"model returned invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise BackendError("model output JSON must be an object")
    return value


class BedrockBackend:
    name = "bedrock"

    def __init__(self, config: FrankieConfig):
        if not config.bedrock_model:
            raise GateStop("FRANKIE_BEDROCK_MODEL is required for the Bedrock backend")
        self.config = config

    def generate(self, *, instructions: str, prompt: str) -> Mapping[str, Any]:
        try:
            import creds

            client = creds.aws_client("bedrock-runtime", self.config.bedrock_region)
            response = client.converse(
                modelId=self.config.bedrock_model,
                system=[{"text": instructions}],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 4096, "temperature": 0.0, "topP": 0.9},
            )
            if response.get("stopReason") == "guardrail_intervened":
                raise BackendError("Bedrock guardrail intervened")
            blocks = response["output"]["message"]["content"]
            text = "\n".join(str(block.get("text") or "") for block in blocks if "text" in block)
            return extract_json_object(text)
        except (BackendError, GateStop):
            raise
        except Exception as exc:
            raise BackendError(f"Bedrock invocation failed: {redact_error(exc)}") from exc


class OpenAIBackend:
    name = "openai"

    def __init__(self, config: FrankieConfig):
        self.config = config

    def generate(self, *, instructions: str, prompt: str) -> Mapping[str, Any]:
        try:
            import creds
            from openai import OpenAI

            client = OpenAI(api_key=creds.get("OPENAI_API_KEY"))
            response = client.responses.create(
                model=self.config.openai_model,
                instructions=instructions,
                input=prompt,
                store=False,
            )
            return extract_json_object(response.output_text)
        except (BackendError, GateStop):
            raise
        except Exception as exc:
            raise BackendError(f"OpenAI invocation failed: {redact_error(exc)}") from exc


class ScriptedBackend:
    """Deterministic backend for tests and integration smoke runs."""

    def __init__(self, name: str, result: Mapping[str, Any]):
        self.name = name
        self.result = dict(result)

    def generate(self, *, instructions: str, prompt: str) -> Mapping[str, Any]:
        del instructions, prompt
        return dict(self.result)


def backend_from_name(name: str, config: FrankieConfig) -> ReasoningBackend:
    normalized = name.strip().lower()
    if normalized == "bedrock":
        return BedrockBackend(config)
    if normalized == "openai":
        return OpenAIBackend(config)
    raise GateStop(f"unknown Frankie backend: {name!r}")
