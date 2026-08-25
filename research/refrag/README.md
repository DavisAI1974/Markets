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

The named prefix, in exact encoder order, is:

1. `ret_mean`
2. `ret_std`
3. `ret_skew`
4. `ret_kurt`
5. `autocorr_lag1`
6. `mean_dipole`
7. `mean_ofi`
8. `volume_zscore`
9. `realized_vol`
10. `range_atr`
11. `spectral_energy`
12. `spectral_entropy`
13. `peak_frequency`
14. `spectral_centroid`

The remaining names are generated as `fft_magnitude_{i}` for the encoder's configured remaining
positions. With the existing default encoder configuration the derived registry currently contains
64 entries, but 64 is an observed default, not a downstream width contract.

The generic `od_refrag_adapter.py` exports `OD_FEATURE_REGISTRY`; it does not define a competing
QSV registry. Registry ordering and vector emission share `MARKET_FEATURE_SPEC` in
`markets_adapter.py`, so a name/order change cannot be made in only one of those paths.
