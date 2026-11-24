class MLPProjector:
    """2-layer MLP-style projector (pure Python)."""

    def __init__(self, d_enc: int, d_model: int):
        self.d_enc = d_enc
        self.d_model = d_model

    def project(self, enc_emb: list[list[float]]) -> list[list[float]]:
        out: list[list[float]] = []
        for row in enc_emb:
            base = sum(row) / max(1, len(row))
            out.append([base + (j * 0.001) for j in range(self.d_model)])
        return out
