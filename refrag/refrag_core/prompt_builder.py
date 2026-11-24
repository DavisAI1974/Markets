from dataclasses import dataclass


@dataclass
class PromptBuildResult:
    prefill_embeds: list[list[float]]
    attention_mask: list[int]
    compressed_chunks: int
    expanded_chunks: int


def build_mixed_prompt(
    query_token_embeds: list[list[float]],
    chunk_embeds: list[list[float]],
    chunk_token_embeds: list[list[list[float]]],
    expand_indices: set[int],
) -> PromptBuildResult:
    seqs: list[list[float]] = list(query_token_embeds)
    compressed = 0
    expanded = 0
    for i, emb in enumerate(chunk_embeds):
        if i in expand_indices:
            seqs.extend(chunk_token_embeds[i])
            expanded += 1
        else:
            seqs.append(emb)
            compressed += 1
    mask = [1] * len(seqs)
    return PromptBuildResult(seqs, mask, compressed, expanded)
