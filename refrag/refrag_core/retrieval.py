from dataclasses import dataclass
from math import sqrt
from pathlib import Path
import importlib.util
import json


@dataclass
class SearchHit:
    idx: int
    score: float


class _PythonIndex:
    """Pure-Python in-memory similarity index."""

    def __init__(self, dim: int):
        self.dim = dim
        self._vecs: list[list[float]] = []

    def add(self, vecs: list[list[float]]) -> None:
        for v in vecs:
            if len(v) != self.dim:
                raise ValueError(f"vector dim must be {self.dim}")
            self._vecs.append([float(x) for x in v])

    def search(self, q: list[float], top_k: int) -> list[SearchHit]:
        if len(q) != self.dim:
            raise ValueError(f"q dim must be {self.dim}")
        scored = [SearchHit(i, _dot(v, q)) for i, v in enumerate(self._vecs)]
        return sorted(scored, key=lambda x: x.score, reverse=True)[:top_k]

    def save(self, path: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"backend": "python", "dim": self.dim, "vectors": self._vecs}
        p.write_text(json.dumps(payload, indent=2))
        return str(p)

    @classmethod
    def load(cls, path: str) -> "_PythonIndex":
        payload = json.loads(Path(path).read_text())
        idx = cls(dim=int(payload["dim"]))
        idx.add(payload.get("vectors", []))
        return idx


class _FaissFlatIPIndex:
    """Optional FAISS-backed index wrapper."""

    def __init__(self, dim: int):
        import faiss  # type: ignore
        import numpy as np

        self.dim = dim
        self._faiss = faiss
        self._np = np
        self._index = faiss.IndexFlatIP(dim)

    def add(self, vecs: list[list[float]]) -> None:
        arr = self._np.asarray(vecs, dtype=self._np.float32)
        if arr.ndim != 2 or arr.shape[1] != self.dim:
            raise ValueError(f"vector dim must be {self.dim}")
        self._index.add(arr)

    def search(self, q: list[float], top_k: int) -> list[SearchHit]:
        arr = self._np.asarray([q], dtype=self._np.float32)
        if arr.shape[1] != self.dim:
            raise ValueError(f"q dim must be {self.dim}")
        scores, ids = self._index.search(arr, top_k)
        return [SearchHit(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if int(i) >= 0]

    def save(self, path: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._faiss.write_index(self._index, str(p))
        return str(p)

    @classmethod
    def load(cls, path: str) -> "_FaissFlatIPIndex":
        import faiss  # type: ignore

        index = faiss.read_index(str(path))
        obj = cls(dim=index.d)
        obj._index = index
        return obj


class VectorIndex:
    """Backend-selectable vector index with optional persistence.

    backends:
    - python: always available
    - faiss: used when installed
    - auto: faiss if available, otherwise python
    """

    def __init__(self, dim: int, backend: str = "auto"):
        self.dim = dim
        self.backend = self._resolve_backend(backend)
        self._impl = self._make_impl(self.backend, dim)

    def _resolve_backend(self, backend: str) -> str:
        if backend not in {"auto", "python", "faiss"}:
            raise ValueError("backend must be one of: auto, python, faiss")
        if backend == "auto":
            return "faiss" if importlib.util.find_spec("faiss") is not None else "python"
        if backend == "faiss" and importlib.util.find_spec("faiss") is None:
            raise RuntimeError("faiss backend requested but faiss is not installed")
        return backend

    def _make_impl(self, backend: str, dim: int):
        if backend == "faiss":
            return _FaissFlatIPIndex(dim)
        return _PythonIndex(dim)

    def add(self, vecs: list[list[float]]) -> None:
        self._impl.add(vecs)

    def search(self, q: list[float], top_k: int) -> list[SearchHit]:
        return self._impl.search(q, top_k)

    def save(self, path: str) -> str:
        return self._impl.save(path)

    @classmethod
    def load(cls, path: str, backend: str = "python") -> "VectorIndex":
        if backend == "faiss":
            impl = _FaissFlatIPIndex.load(path)
            obj = cls(dim=impl.dim, backend="faiss")
            obj._impl = impl
            return obj

        impl = _PythonIndex.load(path)
        obj = cls(dim=impl.dim, backend="python")
        obj._impl = impl
        return obj


class FaissIndex(VectorIndex):
    """Backward-compatible alias used throughout existing scripts/tests."""

    def __init__(self, dim: int, backend: str = "auto"):
        super().__init__(dim=dim, backend=backend)


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def cosine(a: list[float], b: list[float]) -> float:
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return _dot(a, b) / (na * nb)
