"""The one small interface to a model, and its two real callers.

    call(model, system, user, max_tokens, effort, schema=None)
        -> {"text", "usage": {"input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
            "output_tokens"}, "model", "stop_reason", "wall_clock_s"}

- `AnthropicCaller`: the official `anthropic` SDK (never raw HTTP), as the Claude API reference files show.
- `FileCaller`: writes each brief to a folder and waits for a result file that an agent of the session
  puts there; a small wave can be run through the session's own agents this way.

There is NO caller that makes up an answer, not even for a check. Nothing in this module runs on its own.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

WORKER_MODEL = "claude-haiku-5-5"
REDUCER_MODEL = "claude-sonnet-5-5"
REFUTE_MODEL = "claude-sonnet-5-5"          # or "claude-opus-5-5" for a high-stakes wave
MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")   # exact ids, no date suffix
EFFORTS = ("low", "medium", "high", "xhigh", "max")
FALLBACK_BETA = "server-side-fallback-2026-07-01"
USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


class ModelCallFailed(RuntimeError):
    """A call that returned nothing usable. `kind` says which of the typed errors it was."""

    def __init__(self, kind: str, message: str, retryable: bool = False):
        super().__init__(f"{kind}: {message}")
        self.kind, self.retryable = kind, retryable


def request_kwargs(model: str, system: str, user: str, max_tokens: int, effort: str, schema: dict | None = None) -> dict:
    """What is sent, as a pure function (so a check can look at it without a call). No temperature,
    no top_p, no prefill, no forced tool_choice; thinking is adaptive (left out); effort is set."""
    if model not in MODELS:
        raise ValueError(f"model {model!r} is not one of {MODELS}")
    if effort not in EFFORTS:
        raise ValueError(f"effort {effort!r} is not one of {EFFORTS}")
    out_cfg = {"effort": effort}
    if schema is not None:
        out_cfg["format"] = {"type": "json_schema", "schema": schema}
    kw = {"model": model, "max_tokens": int(max_tokens), "system": system,
          "messages": [{"role": "user", "content": user}], "output_config": out_cfg}
    if model != "claude-haiku-5-5":
        kw["betas"] = [FALLBACK_BETA]
        kw["fallbacks"] = "default"
    return kw


class AnthropicCaller:
    """Calls the API through the `anthropic` SDK. The key is the SDK's own (ANTHROPIC_API_KEY in the
    environment); this code never reads, prints or stores one. Retries are the SDK's own (`max_retries`)."""

    def __init__(self, max_retries: int = 2, timeout: float = 600.0):
        self.max_retries, self.timeout, self._client = max_retries, timeout, None

    def _c(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(max_retries=self.max_retries, timeout=self.timeout)
        return self._client

    def call(self, model, system, user, max_tokens, effort, schema=None) -> dict:
        import anthropic
        kw = request_kwargs(model, system, user, max_tokens, effort, schema)
        t0 = time.monotonic()
        try:
            if model == "claude-haiku-5-5":
                r = self._c().messages.create(**kw)
            else:
                r = self._c().beta.messages.create(**kw)
        # most specific first (the order was checked with issubclass on the installed SDK)
        except anthropic.RateLimitError as e:
            raise ModelCallFailed("rate limit (429; a spend cap is a RateLimitError too)", str(e), retryable=False) from e
        except anthropic.AuthenticationError as e:
            raise ModelCallFailed("authentication (401)", str(e)) from e
        except anthropic.PermissionDeniedError as e:
            raise ModelCallFailed("permission denied (403)", str(e)) from e
        except anthropic.NotFoundError as e:
            raise ModelCallFailed("not found (404; a wrong or unavailable model id)", str(e)) from e
        except anthropic.BadRequestError as e:
            raise ModelCallFailed("bad request (400)", str(e)) from e
        except anthropic.APITimeoutError as e:
            raise ModelCallFailed("timeout", str(e), retryable=True) from e
        except anthropic.APIConnectionError as e:
            raise ModelCallFailed("connection", str(e), retryable=True) from e
        except anthropic.InternalServerError as e:     # 500 and 529 (overloaded) after the SDK's own retries
            raise ModelCallFailed("server error (>=500)", str(e), retryable=True) from e
        except anthropic.APIStatusError as e:
            raise ModelCallFailed(f"api status {e.status_code}", str(e)) from e
        wall = time.monotonic() - t0
        # stop reasons first: a refusal or a cut-off answer is returned as such, never read as an answer
        text = ""
        if r.stop_reason not in ("refusal",):
            text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        u = r.usage
        return {"text": text, "usage": {k: int(getattr(u, k, 0) or 0) for k in USAGE_KEYS},
                "model": r.model, "stop_reason": r.stop_reason, "wall_clock_s": wall}


class FileCaller:
    """Writes the brief to `<folder>/<id>.brief.txt` and waits for `<folder>/<id>.result.json`, put there
    by an agent of the session. `<id>` is a hash of the model and the brief, so the same brief is the same
    file. The result file is either the answer's JSON itself or {"text": "...", "usage": {...},
    "model": "...", "stop_reason": "..."}. Tokens are not reported by a session agent: usage is null."""

    def __init__(self, folder, poll_s: float = 2.0, timeout_s: float = 3600.0):
        self.folder, self.poll_s, self.timeout_s = Path(folder), poll_s, timeout_s

    @staticmethod
    def call_id(model: str, system: str, user: str) -> str:
        return hashlib.sha256(json.dumps([model, system, user], ensure_ascii=False).encode()).hexdigest()[:16]

    def call(self, model, system, user, max_tokens, effort, schema=None) -> dict:
        cid = self.call_id(model, system, user)
        self.folder.mkdir(parents=True, exist_ok=True)
        brief, result = self.folder / f"{cid}.brief.txt", self.folder / f"{cid}.result.json"
        if not brief.exists():
            brief.write_text(f"MODEL ROLE: {model}  EFFORT: {effort}  MAX OUTPUT TOKENS: {max_tokens}\n\n"
                             f"{system}\n\n{user}\n", encoding="utf-8")
        t0 = time.monotonic()
        while not result.exists():
            if time.monotonic() - t0 > self.timeout_s:
                raise ModelCallFailed("no result file", f"{result} did not appear in {self.timeout_s} s", retryable=False)
            time.sleep(self.poll_s)
        raw = result.read_text(encoding="utf-8")
        try:
            j = json.loads(raw)
        except json.JSONDecodeError:
            j = None
        if isinstance(j, dict) and "text" in j and isinstance(j["text"], str):
            usage = j.get("usage") or {k: None for k in USAGE_KEYS}
            return {"text": j["text"], "usage": {k: usage.get(k) for k in USAGE_KEYS},
                    "model": j.get("model") or model, "stop_reason": j.get("stop_reason") or "end_turn",
                    "wall_clock_s": time.monotonic() - t0}
        return {"text": raw, "usage": {k: None for k in USAGE_KEYS}, "model": model, "stop_reason": "end_turn",
                "wall_clock_s": time.monotonic() - t0}
