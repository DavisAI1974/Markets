"""Explicit core package boundary for reusable ReFRAG primitives."""

from refrag_core.cache import ChunkEmbeddingCache
from refrag_core.chunking import Chunk, chunk_tokens
from refrag_core.decoder_runner import TinyDecoderModel, generate_with_model_prefill, generate_with_prefill
from refrag_core.encoder import SimpleChunkEncoder
from refrag_core.metrics import timer, tokens_per_second
from refrag_core.projector import MLPProjector
from refrag_core.prompt_builder import PromptBuildResult, build_mixed_prompt
from refrag_core.retrieval import FaissIndex, SearchHit, VectorIndex, cosine
from refrag_core.selector import SimilaritySelector

__all__ = [
    "Chunk",
    "ChunkEmbeddingCache",
    "FaissIndex",
    "MLPProjector",
    "PromptBuildResult",
    "SearchHit",
    "SimilaritySelector",
    "SimpleChunkEncoder",
    "TinyDecoderModel",
    "VectorIndex",
    "build_mixed_prompt",
    "chunk_tokens",
    "cosine",
    "generate_with_model_prefill",
    "generate_with_prefill",
    "timer",
    "tokens_per_second",
]
