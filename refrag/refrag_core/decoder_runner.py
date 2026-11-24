import time
from dataclasses import dataclass
from typing import Any


@dataclass
class DecodeResult:
    token_ids: list[int]
    ttft_s: float


class TinyDecoderModel:
    """Simple deterministic model for sandbox testing."""

    def prefill(self, prefill_embeds: list[list[float]], prefill_mask: list[int]) -> int:
        if not prefill_embeds:
            return 0
        score = sum(prefill_embeds[-1]) + sum(prefill_mask)
        return int(abs(score) * 1000) % 100

    def next_token(self, prev_token: int, step: int) -> int:
        return (prev_token + step + 3) % 100


def generate_with_prefill(model: TinyDecoderModel, prefill_embeds: list[list[float]], prefill_mask: list[int], max_new_tokens: int = 16) -> DecodeResult:
    t0 = time.perf_counter()
    first = model.prefill(prefill_embeds, prefill_mask)
    ttft = time.perf_counter() - t0
    generated = [first]
    for step in range(max_new_tokens - 1):
        generated.append(model.next_token(generated[-1], step))
    return DecodeResult(token_ids=generated, ttft_s=ttft)


def _argmax(values: list[float]) -> int:
    if not values:
        return 0
    best_i = 0
    best_v = values[0]
    for i, v in enumerate(values[1:], start=1):
        if v > best_v:
            best_i = i
            best_v = v
    return best_i


def generate_with_model_prefill(
    model: Any,
    prefill_embeds: list[list[float]],
    prefill_mask: list[int],
    max_new_tokens: int = 16,
    eos_token_id: int | None = None,
) -> DecodeResult:
    """Model-backed prefill/generate path compatible with HF-style call signatures.

    Expected model behavior:
    - `model(inputs_embeds=..., attention_mask=..., use_cache=True)` for prefill
    - returns object with `.logits` and `.past_key_values`
    - `model(input_ids=[token], past_key_values=..., use_cache=True)` for decode
    """
    t0 = time.perf_counter()
    prefill_out = model(inputs_embeds=prefill_embeds, attention_mask=prefill_mask, use_cache=True)
    ttft = time.perf_counter() - t0

    logits = getattr(prefill_out, "logits")
    past = getattr(prefill_out, "past_key_values", None)
    next_token = _argmax(logits[-1])

    generated = [next_token]
    for _ in range(max_new_tokens - 1):
        step_out = model(input_ids=[next_token], past_key_values=past, use_cache=True)
        past = getattr(step_out, "past_key_values", past)
        logits = getattr(step_out, "logits")
        next_token = _argmax(logits[-1])
        generated.append(next_token)
        if eos_token_id is not None and next_token == eos_token_id:
            break

    return DecodeResult(token_ids=generated, ttft_s=ttft)
