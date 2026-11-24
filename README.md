# Markets operator-discovery source handoff

Isolated code-only handoff for branch `od-refrag/markets-handoff` in `DavisAI1974/Markets`.
Copies were made first; original files were not edited or moved. Every copied file is listed below with its absolute source path and SHA-256. The branch starts with a new root commit and contains no inherited repository history.

## Layout and source locations

- `refrag/`: the import closure of `E:\refrag\adapters\markets_refrag_adapter.py`, including local imports inside functions and package initializers.
- `markets/markets_adapter.py`: market-specific chunking primitives imported by the original scripts.
- `markets/vendored_build_kit/`: all seven `_markets_*.py` files beside the requested originals, plus that folder's original README.
- `refrag/registry/manifests/*.json` and `refrag/schema/*.json`: static operator definitions and type schemas required by the code's registry loader. These are source configuration, not learned knowledge or discovery records.

The requested adapter exists at `E:\refrag\adapters\markets_refrag_adapter.py`, rather than an extra nested `refrag/adapters` path. The named original market scripts now reside in `E:\Markets\vendored_build_kit`; its own README identifies these as verbatim durable copies of the original untracked root scripts. F: holds this one handoff folder because E: is full.

## Window to 128 operator coefficients

`load_closes / slice_closes / closes_to_log_returns` (markets bar loader) -> `run_pipeline_on_winner` (markets adapter) -> `OperatorOrchestrator.execute` -> spectral chunking -> 128-dimensional spectral encoding -> retrieval and falsification selection -> `refrag_discovery.runtime.operator_decoder.execute` -> `adapters.od_refrag_adapter.OperatorDecoder.prefill / refine` -> `result.operator_coefficients`.

The copied decoder explicitly describes itself as a deterministic stub: prefill averages selected embeddings and refinement repeatedly normalizes the vector. It does not import the separate physics engine in `E:\operator_discovery`. The vector length follows the embedding width (default 128); empty or degenerate inputs can return fewer coefficients. This handoff preserves the actual implementation, not a replacement decoder.

The adapter supports post-hoc trade windows and `--pre-entry-minutes`; the gate requests the 30-minute pre-entry window with window_size=192 and stride=16. Original absolute Windows paths are preserved. To use another location, configure or adjust paths in your own working copy; no originals were changed here.

## Known missing original dependency

`_markets_gate_v2.py` and `_markets_dipole_export_centroids_v2.py` import `_markets_combined_info_flow_kfold.py`. That original module was not found in the requested source trees, local operator-discovery folders, SENTINEL, or searched backups/drives. No substitute was invented. Those two modules need that file to import successfully; their original source is still included verbatim. The ReFRAG coefficient-generation dependency closure itself is present.

## Runtime dependencies and excluded inputs

Python 3.10+ and `jsonschema` are needed for the copied runtime/registry path. NumPy and scikit-learn are used by the chunker-stack analysis script; FAISS and umap are optional backends. Third-party libraries are not vendored. Put the copied `refrag`, `refrag/adapters`, `markets`, and `markets/vendored_build_kit` directories on PYTHONPATH for imports. The adapter and gate also preserve hardcoded paths from their source, so their direct CLIs are not portable without path configuration.

No market bars, trade lists, coefficients, centroids, gate calibration files, discovery outputs, evidence snapshots, registry state/indexes, trained checkpoints, SENTINEL knowledge files, credentials, caches, or old Git objects are included. Analysis and gate CLIs require their own local inputs; this is a source handoff, not an export of live data. SENTINEL was searched for relevant source only; nothing from it was copied.

## Verification

All copied files were checked byte-for-byte against their sources. Python syntax, JSON parsing, import-closure analysis, runtime smoke checks, and the final staged allowlist are checked before publishing. The copied adapter/orchestrator was run twice on an in-memory synthetic 384-sample return window. Each run returned 128 finite coefficients with unit norm; the two vectors matched exactly. All local imports resolved to handoff copies. During these runs, an audit hook blocked access to E: and confined writes to untracked Git metadata, so no original source or real market data was accessed. All 22 static registry definitions loaded successfully. The two market scripts with the missing helper were not represented as passing imports.

## File provenance (SHA-256)

| Handoff file | Original source path | SHA-256 |
|---|---|---|
| `markets/markets_adapter.py` | `E:\Markets\markets_adapter.py` | `a309585fe5e0e2852ac83bdfd599e08da0e0c6bb5c6c153b931a3c67cfffaa62` |
| `markets/vendored_build_kit/README.md` | `E:\Markets\vendored_build_kit\README.md` | `8af59348c2fb45684f63a2a3ca24f5cebde1140bd3620f170ca5ce5a745a72bb` |
| `markets/vendored_build_kit/_markets_algebraic_dipole.py` | `E:\Markets\vendored_build_kit\_markets_algebraic_dipole.py` | `39f267a2eaccddd4c4256e613e21ab8ecc6d1f2a31e71de1a04fa6661d7eb7f0` |
| `markets/vendored_build_kit/_markets_dipole_chunker_stack.py` | `E:\Markets\vendored_build_kit\_markets_dipole_chunker_stack.py` | `cac32a065cfeace86cbacd845083108d4e96b5134c892a10d5b41947570da773` |
| `markets/vendored_build_kit/_markets_dipole_export_centroids.py` | `E:\Markets\vendored_build_kit\_markets_dipole_export_centroids.py` | `844e1f2b9d6d75864c2db1c5f30e7bee2bdf3cca332a2c599dd0111af075eea3` |
| `markets/vendored_build_kit/_markets_dipole_export_centroids_v2.py` | `E:\Markets\vendored_build_kit\_markets_dipole_export_centroids_v2.py` | `b543eb6516bc4677efdceb5381632d6b572b14f6dea9b100cec6ddc797ea35c4` |
| `markets/vendored_build_kit/_markets_dipole_kfold.py` | `E:\Markets\vendored_build_kit\_markets_dipole_kfold.py` | `c4698a435d6964211866f34a0fc06f763ad02a8fd171d1ceacdc56f9d9cc159b` |
| `markets/vendored_build_kit/_markets_dipole_separation.py` | `E:\Markets\vendored_build_kit\_markets_dipole_separation.py` | `e64e2014d5207e07e8c8cd1b1659229957f62cc101ba3912b2b03686cf2a4ee0` |
| `markets/vendored_build_kit/_markets_gate_v2.py` | `E:\Markets\vendored_build_kit\_markets_gate_v2.py` | `1d10b97c42ae5d1ec97ae96016ad64189545bf28c647e01e0b46536569a6f304` |
| `refrag/adapters/markets_bar_loader.py` | `E:\refrag\adapters\markets_bar_loader.py` | `b093020cd29715e9dba43d5ba6c6e6b92e152a84edad331b18cbdd54d06ebb30` |
| `refrag/adapters/markets_refrag_adapter.py` | `E:\refrag\adapters\markets_refrag_adapter.py` | `ad1a471ba01e8f4717fdb37fd634d25c27b38745b470b8fa40022bfb93fbf33e` |
| `refrag/adapters/od_refrag_adapter.py` | `E:\refrag\adapters\od_refrag_adapter.py` | `0254c093d0d4d5a0e23210ecf82f7b64cf30d98cf177f4c18f5a07568b579769` |
| `refrag/refrag_core/__init__.py` | `E:\refrag\refrag_core\__init__.py` | `654cacdb6b7c55fa893416ad52d31cf880375da6c95e5e842f5cd6a6f393f60f` |
| `refrag/refrag_core/cache.py` | `E:\refrag\refrag_core\cache.py` | `8af792d5732601988f2ab413e26b67d76d88c3024ca184627732a63d4584cdef` |
| `refrag/refrag_core/chunking.py` | `E:\refrag\refrag_core\chunking.py` | `b35586bba742c990ad25426d9f5d13680b00025fd46c0bf493a50333a55d69ae` |
| `refrag/refrag_core/decoder_runner.py` | `E:\refrag\refrag_core\decoder_runner.py` | `2fad61cfa24238be0f0adf6d9f45e5ee71cf23ef86b9c3838c652478540358f1` |
| `refrag/refrag_core/encoder.py` | `E:\refrag\refrag_core\encoder.py` | `41bca8ce4739a8992dffcb7f57c6a4cc38cd30d7e663110bdd5fdc919a70c5c6` |
| `refrag/refrag_core/metrics.py` | `E:\refrag\refrag_core\metrics.py` | `7ab9a687a5b390037ca7e6fe976fa7b1f609ea92e00c2aa4229b8f06799ed1ea` |
| `refrag/refrag_core/projector.py` | `E:\refrag\refrag_core\projector.py` | `e761c9c8ed878edb8f4dd17baa9089f1843d1933792b642008e974e96861cb8c` |
| `refrag/refrag_core/prompt_builder.py` | `E:\refrag\refrag_core\prompt_builder.py` | `edee02ce84c39e982dfdac2a8697fd7bd281af88d9a55d4f451e199248ad5ba7` |
| `refrag/refrag_core/retrieval.py` | `E:\refrag\refrag_core\retrieval.py` | `d44a40b80dce9810c71805116f7daded9fb1edb662109edc43ec181e2e147b20` |
| `refrag/refrag_core/selector.py` | `E:\refrag\refrag_core\selector.py` | `b6555fc571442cad0c607e288310155097b8c0bd6e286cf5e7a3f55599a1abe4` |
| `refrag/refrag_discovery/__init__.py` | `E:\refrag\refrag_discovery\__init__.py` | `654c7d27e52b6dd96b867f3ad3a0b9352f994018f9a258ddb396b39cd1e9b81d` |
| `refrag/refrag_discovery/control_plane/__init__.py` | `E:\refrag\refrag_discovery\control_plane\__init__.py` | `cc2cb104bf0f0def13abbcc7179ae4e2fb9799c196cec518da9726615dcd1d17` |
| `refrag/refrag_discovery/control_plane/cross_domain_transfer_detector.py` | `E:\refrag\refrag_discovery\control_plane\cross_domain_transfer_detector.py` | `33d9f3d4ce0f067774aab9357dcc5c7c2b3be93d3e0d2ef96dac732bc2d2b183` |
| `refrag/refrag_discovery/control_plane/exploration_policy_controller.py` | `E:\refrag\refrag_discovery\control_plane\exploration_policy_controller.py` | `e3405f9af2f006eeb132239a105fed290e5f4bd19f3ce5cf33d9bc9d77f5a12d` |
| `refrag/refrag_discovery/control_plane/manifest_synthesizer.py` | `E:\refrag\refrag_discovery\control_plane\manifest_synthesizer.py` | `68bb1af1c19ffab64072cfdb4f724de558dde552102b45b4f89bd234cb665795` |
| `refrag/refrag_discovery/control_plane/operator_benchmark_suite.py` | `E:\refrag\refrag_discovery\control_plane\operator_benchmark_suite.py` | `b12db5079295d177f031634bd78a5821c18e87e1f2efcae292fa01696aab61d6` |
| `refrag/refrag_discovery/control_plane/operator_chain_builder.py` | `E:\refrag\refrag_discovery\control_plane\operator_chain_builder.py` | `0b45268b47ee8e12fa8de3c4d7e75bf4f9d5609215176a58c45bd39e4a7d5602` |
| `refrag/refrag_discovery/control_plane/operator_composability_scorer.py` | `E:\refrag\refrag_discovery\control_plane\operator_composability_scorer.py` | `cd6c6ffa8c5ea3fb00a862d3d3ed8b3ad56d6899608e3dde39f0d5563cad7aca` |
| `refrag/refrag_discovery/control_plane/operator_gap_finder.py` | `E:\refrag\refrag_discovery\control_plane\operator_gap_finder.py` | `fab1c4fdd5129a1c605d4219960f7de5bf21a4bdc5b7c99bedda681df163af5d` |
| `refrag/refrag_discovery/control_plane/operator_graph_rewriter.py` | `E:\refrag\refrag_discovery\control_plane\operator_graph_rewriter.py` | `bea4ee41371896170b4b9792e78b6fa5f188cb5d23c3aee091ed8829d0e31612` |
| `refrag/refrag_discovery/control_plane/operator_lifecycle_tracker.py` | `E:\refrag\refrag_discovery\control_plane\operator_lifecycle_tracker.py` | `8a47c093f955713cfc48b568baff6f0e52f43fa54970bdc98dddeb1383950771` |
| `refrag/refrag_discovery/control_plane/operator_lineage_tracker.py` | `E:\refrag\refrag_discovery\control_plane\operator_lineage_tracker.py` | `d3c7676d2e7f7bbd120184ca37bc02c1e69c6d8a552f9f075f5f8d197fd947be` |
| `refrag/refrag_discovery/control_plane/operator_promotion_recommender.py` | `E:\refrag\refrag_discovery\control_plane\operator_promotion_recommender.py` | `296757ab97e2b883d8835c300c8925444598e2291661e4b9330079f43c6b125c` |
| `refrag/refrag_discovery/control_plane/pipeline_performance_optimizer.py` | `E:\refrag\refrag_discovery\control_plane\pipeline_performance_optimizer.py` | `aa41833c182db051b220d2f3f85225f8ebbb23248fd7a61e8e3bf03bbb130b50` |
| `refrag/refrag_discovery/control_plane/production_readiness.py` | `E:\refrag\refrag_discovery\control_plane\production_readiness.py` | `5c87702250b989d3d3779473599fa83f22c3ac7c0d1b9e292ce537a57d9f94dd` |
| `refrag/refrag_discovery/control_plane/storage.py` | `E:\refrag\refrag_discovery\control_plane\storage.py` | `d12b7f03727519d11979785068665c2cf31c5b6e821d4ea2cae97cc6bc5a4242` |
| `refrag/refrag_discovery/control_plane/stubs.py` | `E:\refrag\refrag_discovery\control_plane\stubs.py` | `f0cb83413f5eed270a2f3bf1aba7772bd975f0d8bfeb65c9ebc243646d1c3f3e` |
| `refrag/refrag_discovery/control_plane/task_meta_learner.py` | `E:\refrag\refrag_discovery\control_plane\task_meta_learner.py` | `c76bb10149596c6c1b07587e1a0f1771370f2da80b2187f667863d26bc587f56` |
| `refrag/refrag_discovery/paths.py` | `E:\refrag\refrag_discovery\paths.py` | `a59819968644ec620f1c9457863444761d1eb667701eee0c85ad635f3ea986f1` |
| `refrag/refrag_discovery/registry/__init__.py` | `E:\refrag\refrag_discovery\registry\__init__.py` | `27033d1412476cdccd51d4c1ba8cdd019b7f51b08c34d70a85592b2a8309f28b` |
| `refrag/refrag_discovery/registry/bootstrap.py` | `E:\refrag\refrag_discovery\registry\bootstrap.py` | `b6e0e0ada47a9918ea8d9319ef55ecbea89598c8273d46e601dd4ceb6f52f712` |
| `refrag/refrag_discovery/registry/dependency_graph_store.py` | `E:\refrag\refrag_discovery\registry\dependency_graph_store.py` | `f991b31f3fa77a4617b2fe69fef5c21acfc1225dbe3e57928f6301a4fe925ed5` |
| `refrag/refrag_discovery/registry/discovery_index_writer.py` | `E:\refrag\refrag_discovery\registry\discovery_index_writer.py` | `ad489427b8360783e54980fa0ca5bdea9ab5e4657b4f5107467fa71a31959206` |
| `refrag/refrag_discovery/registry/manifest_validator.py` | `E:\refrag\refrag_discovery\registry\manifest_validator.py` | `dd6a1b0c30cc0d46dbf1c58344bac76fad832c595905321fef3796784c8b7d89` |
| `refrag/refrag_discovery/registry/models.py` | `E:\refrag\refrag_discovery\registry\models.py` | `1a35e43d2a60f77bbfb6e36506bb4e94a272e8623472f982c591c8604f77cfdb` |
| `refrag/refrag_discovery/registry/operator_query.py` | `E:\refrag\refrag_discovery\registry\operator_query.py` | `177195c49e2cdb5d86ad1875ef7d7f23a3bd0c4f1cbf89161cb9bd15b8c228cc` |
| `refrag/refrag_discovery/registry/registry_writer.py` | `E:\refrag\refrag_discovery\registry\registry_writer.py` | `573224b2583f018c2c7ef21268f6f97e8d03d8b2e39e936d050c011ccccff3ac` |
| `refrag/refrag_discovery/registry/trace_store.py` | `E:\refrag\refrag_discovery\registry\trace_store.py` | `87a9a356f00bd2cd1d549f2a75775faabb398379f6d026fa83d750f948b7bf66` |
| `refrag/refrag_discovery/runtime/__init__.py` | `E:\refrag\refrag_discovery\runtime\__init__.py` | `b38d05e998df2c747634cde8ed45215784222edb3fb4c0e1431d60f080ef2b92` |
| `refrag/refrag_discovery/runtime/evidence_graph_builder.py` | `E:\refrag\refrag_discovery\runtime\evidence_graph_builder.py` | `e33dbc9b165a29dd2900efe80ef406c98f46877974f6a0616107ce039eb1f6b2` |
| `refrag/refrag_discovery/runtime/falsification_prioritizer.py` | `E:\refrag\refrag_discovery\runtime\falsification_prioritizer.py` | `d43c55d74a8f94a838feaf8631f6f2609b3b41b90ee19095e404dcd9d2dfef12` |
| `refrag/refrag_discovery/runtime/od_spectral_retrieval_pipeline.py` | `E:\refrag\refrag_discovery\runtime\od_spectral_retrieval_pipeline.py` | `b93b00da0626a63b89dc7cd537ab3238af33791f265287a1ca6b1c238623b886` |
| `refrag/refrag_discovery/runtime/operator_decoder.py` | `E:\refrag\refrag_discovery\runtime\operator_decoder.py` | `e1ae2c6fb48c06d61d81e72370d69f05f5a4ffdecc1bd2f97026ca910487906d` |
| `refrag/refrag_discovery/runtime/operator_orchestrator.py` | `E:\refrag\refrag_discovery\runtime\operator_orchestrator.py` | `dfd7772eb0a00a13286316d187200147c8d9f3e6f69a6341a6b0422b48d18db5` |
| `refrag/refrag_discovery/runtime/retrieval_policy_learner.py` | `E:\refrag\refrag_discovery\runtime\retrieval_policy_learner.py` | `160456d5767e42aa9a7391796c05a4a53c796e4907c61ac9c738be6b1bcbca96` |
| `refrag/refrag_discovery/runtime/spectral_chunk_encode.py` | `E:\refrag\refrag_discovery\runtime\spectral_chunk_encode.py` | `d1b6da2934917edddd073fa4cb932cabbc013813bef71ac8e41709936455f43b` |
| `refrag/refrag_discovery/runtime/spectral_chunker.py` | `E:\refrag\refrag_discovery\runtime\spectral_chunker.py` | `b8bd50a59fe811ddcb5eccee08d81cbbfa194aa19302adbd5083b4b344dd0e51` |
| `refrag/refrag_discovery/runtime/types.py` | `E:\refrag\refrag_discovery\runtime\types.py` | `0a5af7f43535cdb15a35848c384e70b26b02b3b27ca7021ff520a958ae62198b` |
| `refrag/registry/manifests/cross_domain_transfer_detector.v2.json` | `E:\refrag\registry\manifests\cross_domain_transfer_detector.v2.json` | `05901bd15f6e1b2f703a1323ac4bec10bb2ebe3eac2cd62406d317f77435709a` |
| `refrag/registry/manifests/evidence_graph_builder.v2.json` | `E:\refrag\registry\manifests\evidence_graph_builder.v2.json` | `99ede2b99b34965fc9593c2791e9833f89af9739816edf1115d95055dd16d74a` |
| `refrag/registry/manifests/exploration_policy_controller.v2.json` | `E:\refrag\registry\manifests\exploration_policy_controller.v2.json` | `066b5c52481ef08b0114eba0fcecae2dfb9301901e25fb95093680dee27d1297` |
| `refrag/registry/manifests/falsification_prioritizer.v2.json` | `E:\refrag\registry\manifests\falsification_prioritizer.v2.json` | `90118553e127ec53c7782c754031824679fe27ce2090dc6cc518e5ff495cc1f8` |
| `refrag/registry/manifests/manifest_synthesizer.v2.json` | `E:\refrag\registry\manifests\manifest_synthesizer.v2.json` | `0c801c76e477a95012ab0344f563ccc52aade191c49064d2e188f50e611d971f` |
| `refrag/registry/manifests/od_spectral_retrieval_pipeline.v2.json` | `E:\refrag\registry\manifests\od_spectral_retrieval_pipeline.v2.json` | `ec72a32d3c2a6b5b25e4a37cddbba1a5c4b9b5d6d17d27843b90f74b308f21e9` |
| `refrag/registry/manifests/operator_benchmark_suite.v2.json` | `E:\refrag\registry\manifests\operator_benchmark_suite.v2.json` | `1702110c93d1ce2ed317c02917f04184b7d3f6b820bb5675d43c5c2cb6b38618` |
| `refrag/registry/manifests/operator_chain_builder.v2.json` | `E:\refrag\registry\manifests\operator_chain_builder.v2.json` | `70d3ec03f1798e257c8bef6eff5d64ceef76390cc77320c1fa46b13aa897744c` |
| `refrag/registry/manifests/operator_composability_scorer.v2.json` | `E:\refrag\registry\manifests\operator_composability_scorer.v2.json` | `9d4add6bbb84eef3a0386ec11ed8a6c28e13102f6424653189d5545eb73f28c7` |
| `refrag/registry/manifests/operator_decoder.v2.json` | `E:\refrag\registry\manifests\operator_decoder.v2.json` | `e031ef541c90d5ba95820365ff60b379202851e1e5db8ed7291c4c456ade3c8d` |
| `refrag/registry/manifests/operator_gap_finder.v2.json` | `E:\refrag\registry\manifests\operator_gap_finder.v2.json` | `81096ad1c3c35b239b7851e64ff155f08a4edcf08ef2d523826de4573b441aba` |
| `refrag/registry/manifests/operator_graph_rewriter.v2.json` | `E:\refrag\registry\manifests\operator_graph_rewriter.v2.json` | `f9929b749d621db5fb8aae6ffba2737b78205caeee9d510518a34f8a6c954b60` |
| `refrag/registry/manifests/operator_lifecycle_tracker.v2.json` | `E:\refrag\registry\manifests\operator_lifecycle_tracker.v2.json` | `ef527249a48030475212cd5b1de782bc78b8bef2f6df136780431ac12ea0504a` |
| `refrag/registry/manifests/operator_lineage_tracker.v2.json` | `E:\refrag\registry\manifests\operator_lineage_tracker.v2.json` | `0a650ead99ee19c67680f18c671bf293eafc5d280b212b494ca57801a1a08d80` |
| `refrag/registry/manifests/operator_orchestrator.v2.json` | `E:\refrag\registry\manifests\operator_orchestrator.v2.json` | `67fcd1632993583c04be3c3f0070923daaf18eccaeffbc421b513a875e588c46` |
| `refrag/registry/manifests/operator_promotion_recommender.v2.json` | `E:\refrag\registry\manifests\operator_promotion_recommender.v2.json` | `e25156b390a29c0c5625bda571a8db1d44f077616107437a2d39f33ecf96a2d6` |
| `refrag/registry/manifests/operator_query.v2.json` | `E:\refrag\registry\manifests\operator_query.v2.json` | `94fcdf7989ef8ce3321cfb550c8b8a728b3b1998d3aa889b39e581bcfcf317f2` |
| `refrag/registry/manifests/pipeline_performance_optimizer.v2.json` | `E:\refrag\registry\manifests\pipeline_performance_optimizer.v2.json` | `dc7282c24cb3b2e0a3f61b8daeff15bae7c95ddb183ad295965c3eaea60d7ff1` |
| `refrag/registry/manifests/retrieval_policy_learner.v2.json` | `E:\refrag\registry\manifests\retrieval_policy_learner.v2.json` | `e6f467b9d6c486481b286797615336c37aec89c6c9b7640adcda4c3b434c00b3` |
| `refrag/registry/manifests/spectral_chunk_encode.v2.json` | `E:\refrag\registry\manifests\spectral_chunk_encode.v2.json` | `38a634d3b20a2511ecae2787124e1f41493ceb0eee88bbafc212acf38627f282` |
| `refrag/registry/manifests/spectral_chunker.v2.json` | `E:\refrag\registry\manifests\spectral_chunker.v2.json` | `450e6ee317cc466c172bb2591885d4f41547cfed4db5d49a3679a178d53c73bb` |
| `refrag/registry/manifests/task_meta_learner.v2.json` | `E:\refrag\registry\manifests\task_meta_learner.v2.json` | `257790776ef1964bea1c66520aa22a707b837c8ba83c93a47a559541f621db9b` |
| `refrag/schema/evidence_graph.schema.json` | `E:\refrag\schema\evidence_graph.schema.json` | `76647cbe769ea26a041095e84136d2c9b8f517b22782e2af45fe8c20d29892f4` |
| `refrag/schema/operator_candidate.schema.json` | `E:\refrag\schema\operator_candidate.schema.json` | `56575261a42cd563bd9579a6fdb60dc17243739c72a64df4535f18b590a8e873` |
| `refrag/schema/operator_manifest.schema.json` | `E:\refrag\schema\operator_manifest.schema.json` | `479f3a8c051c29d6ecad426b9a42ee33eb62108da74876eace356dedfea8ff71` |
| `refrag/schema/spectral_chunk.schema.json` | `E:\refrag\schema\spectral_chunk.schema.json` | `37067632faf4f5e4fa7a83e33f94d161aadebbf8b5aac8397f6965dc8f610e36` |

The root README and .gitignore are newly written handoff notes/configuration, rather than copied originals. Git records their final content hashes; a README cannot contain its own final SHA-256.
