import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    chunk_index: int
    token_ids: list[int]
    text: str = ""


def make_chunk_id(doc_id: str, chunk_index: int, tokenizer_name: str, k: int) -> str:
    raw = f"{doc_id}|{chunk_index}|{tokenizer_name}|{k}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def chunk_tokens(doc_id: str, text: str, token_ids: list[int], tokenizer_name: str, k: int) -> list[Chunk]:
    if k <= 0:
        raise ValueError("k must be > 0")
    chunks: list[Chunk] = []
    for i in range(0, len(token_ids), k):
        idx = i // k
        chunks.append(
            Chunk(
                chunk_id=make_chunk_id(doc_id, idx, tokenizer_name, k),
                doc_id=doc_id,
                chunk_index=idx,
                token_ids=token_ids[i : i + k],
                text=text,
            )
        )
    return chunks
