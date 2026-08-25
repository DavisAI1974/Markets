# ReFRAG v2.1 source bundle in Markets

This directory persists the supplied ReFRAG/Operator Discovery artifacts inside Markets. ReFRAG owns
operator registry and governance; Frankie imports the named QSV registry here and does not create a
second registry.

- Original source bundle: `provenance/davisai_refrag_v21_manifests.zip`
  (`bc2df161ee55c3fe3e65e2071ef2ba87d005d46b1a16fe550c341630d121a26a`).
- Exact manifests: `registry/manifests/`.
- Architecture source: `docs/architecture_spec_v21.docx`.
- Market-shaped executable adapter: repository-root `markets_adapter.py`, byte-identical to stable
  Markets ref `7f492b2bcb3934ff3e280f4ef0b44fc3d38b486e` before this registry addition.
- Supplied generic OD integration adapter: `od_refrag_adapter.py`.

`qsv_registry.py` derives `QSV_FEATURE_REGISTRY` from the executable `MarketChunkEncoder` output
contract: its 14 actually emitted named market features followed by normalized FFT-magnitude slots
derived from that encoder's configured `d_enc`. Un-emitted `MarketFeatures` attributes and the
separate 128-D operator-coefficient object are not silently folded into QSV. Downstream code must use
`len(QSV_FEATURE_REGISTRY)` and may not restate a width.
