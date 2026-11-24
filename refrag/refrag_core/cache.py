import sqlite3
import struct


class ChunkEmbeddingCache:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS chunk_cache (chunk_id TEXT PRIMARY KEY, dim INTEGER, data BLOB)"
        )
        self.conn.commit()

    def put(self, chunk_id: str, emb: list[float]) -> None:
        data = struct.pack(f"<{len(emb)}f", *emb)
        self.conn.execute(
            "INSERT OR REPLACE INTO chunk_cache (chunk_id, dim, data) VALUES (?, ?, ?)",
            (chunk_id, len(emb), data),
        )
        self.conn.commit()

    def get(self, chunk_id: str) -> list[float] | None:
        cur = self.conn.execute("SELECT dim, data FROM chunk_cache WHERE chunk_id = ?", (chunk_id,))
        row = cur.fetchone()
        if row is None:
            return None
        dim, data = row
        return list(struct.unpack(f"<{dim}f", data))
