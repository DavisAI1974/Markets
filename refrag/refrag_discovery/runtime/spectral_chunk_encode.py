from __future__ import annotations

from adapters.od_refrag_adapter import SpectralChunkEncoder
from refrag_discovery.runtime.types import EncodedChunk


def execute(
    *,
    chunks: list,
    d_enc: int = 128,
    encoder_mode: str = "deterministic",
    contrastive_checkpoint: str | None = None,
) -> dict:
    encoder = SpectralChunkEncoder(d_enc=d_enc)
    embeddings = encoder.encode(chunks)
    uncertainties: list[float] = []
    encoded_chunks: list[EncodedChunk] = []
    for chunk, embedding in zip(chunks, embeddings):
        chunk_energy = sum(abs(value) for value in chunk.values) / max(1, len(chunk.values))
        uncertainty = round(1.0 / (1.0 + chunk_energy), 4)
        uncertainties.append(uncertainty)
        encoded_chunks.append(
            EncodedChunk(chunk=chunk, embedding=embedding, uncertainty=uncertainty)
        )
    return {
        "embeddings": embeddings,
        "embedding_uncertainty": uncertainties,
        "encoded_chunks": encoded_chunks,
        "metadata": {
            "encoder_mode": encoder_mode,
            "contrastive_checkpoint": contrastive_checkpoint,
            "d_enc": d_enc,
        },
    }
