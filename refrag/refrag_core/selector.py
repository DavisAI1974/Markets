from refrag_core.retrieval import cosine


class SimilaritySelector:
    """Select top chunks by query/chunk cosine similarity."""

    def select(self, query_embed: list[float], chunk_embeds: list[list[float]], budget: int) -> list[int]:
        if budget <= 0 or len(chunk_embeds) == 0:
            return []
        scores = [(i, cosine(query_embed, e)) for i, e in enumerate(chunk_embeds)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return [i for i, _ in scores[:budget]]
