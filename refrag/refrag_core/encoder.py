class SimpleChunkEncoder:
    """Tiny deterministic encoder for sandbox demos/tests."""

    def __init__(self, d_enc: int = 16):
        self.d_enc = d_enc

    def encode(self, chunks: list[list[int]]) -> list[list[float]]:
        out: list[list[float]] = []
        for toks in chunks:
            if not toks:
                out.append([0.0] * self.d_enc)
                continue
            tmin = min(toks)
            tmax = max(toks)
            mean = sum(toks) / len(toks)
            var = sum((t - mean) ** 2 for t in toks) / len(toks)
            vec = [mean, var**0.5, float(tmin), float(tmax)]
            norm = (tmax + 1.0) if tmax >= 0 else 1.0
            resized = [(toks[i % len(toks)] / norm) for i in range(self.d_enc - 4)]
            out.append(vec + resized)
        return out
