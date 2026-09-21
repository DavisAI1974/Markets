## Notes on part 8/163 (bytes 963855-1103855)

### NOTES for merge (PART 8/163)

#### (1) Observed facts with their exact numbers, hashes and section ids as they appear

- Packet hash: `["str","af4adca5b8b22ac91214b3adbef08d07f5e0b1d4edc2d15331bce7918faf8e45"]`
- Config hash: `["str","92fbe1c044b96a1b73c510e35070f115c6d6f402854ffd35e3625a89dbdfc11c"]`
- Identity hash: `["str","1bd1027a54a31a7a13e010cc1dd96bb5cefe1dddec74f06d45fd8085358315bf"]`
- Request ID: `["str","frankie-boss-sunday-two-cycle-20260919-cycle-00"]` (inferred from request_id field in receipt)
- Request hash: `["str","62ccf52432f0ee5ceca0f35951825368b8d2d891bd908924e10892cd4badfef4"]`
- Step: `["str","CRITIC_RESULT"]`
- Intent hash: `["str","5bad8b05570dbc257f27dbe371ce9cfe7f107c958de41120672142e856697d15"]`
- Shadow request identity base checkpoint SHA: `["str","adf5304a845900b4395c2593c5d270ae727867cc9a164132510acb95d5a3091a"]`
- Shadow request identity weights SHA: `null`
- Shadow request identity tokenizer SHA: `["str","51e3c30923a00f8d17cc0c6126a06d8e4911b5e83232abbed255c2abb49a438a"]`
- Quantization: `["str","none"]`
- Runtime versions JSON includes: `"GRANITE_BOOTSTRAP_SHA256":"23b46e64d32e248d81030173e0ee8d49cedfb0b86923a3326dd22b7a426ee522"`, `"GRANITE_IMAGE_DIGEST":"sha256:18998be4e1276d4eb6e98afe80798aa357c1cc37545150de5c210bc9111beb1d"`, `"GRANITE_IMAGE_IDENTITY_SHA256":"f0f619cb1ed40cbd797631ad60a3c77033d9659066ab9dee729a4a7e3e413b5e"`, `"GRANITE_MANIFEST_SHA256":"adf5304a845900b4395c2593c5d270ae727867cc9a164132510acb95d5a3091a"`, `"GRANITE_MAX_MODEL_LEN":"131072"`, `"GRANITE_SERVED_MODEL":"granite42-smoke"`, `"GRANITE_TRANSPORT_PROTOCOL":"jobs_v1"`, `"GRANITE_VERIFIER_SHA256":"8a1e07529fd4b88456e689cfc0525ebe0f07b3d4552ce74ae0c6c22e4f701b0e"`, `"HF_HUB_DISABLE_TELEMETRY":"1"`, `"HF_HUB_OFFLINE":"1"`, `"PROCESS_AUTO_RECOVERY":"true"`, `"SUPERVISOR_PROGRAM__APP_AUTORESTART":"false"`, `"SUPERVISOR_PROGRAM__APP_COMMAND":"python3 /opt/ml/additional-model-data-sources/bootstrap/granite_startup.py"`, `"SUPERVISOR_PROGRAM__APP_STARTRETRIES":"0"`, `"TRANSFORMERS_OFFLINE":"1"`, `"VLLM_ENABLE_CUDA_COMPATIBILITY":"0"`, `"VLLM_NO_USAGE_STATS":"1"`, `"VLLM_USAGE_SOURCE":"production-docker-image"`, `"VLLM_GENERATION_CONFIG":"vllm"`, `"VLLM_ENABLE_CHUNKED_PREFILL":"--enable-chunked-prefill"`, `"VLLM_MAX_NUM_SEQS":"1"`, `"VLLM_MAX_MODEL_LEN":"131072"`, `"VLLM_GPU_MEMORY_UTILIZATION":"0.9"`, `"VLLM_PIPELINE_PARALLEL_SIZE":"1"`, `"VLLM_DATA_PARALLEL_SIZE":"1"`, `"VLLM_GENERATION_CONFIG":"vllm"`, `"VLLM_THINKING":"false"`, `"VLLM_TEMPERATURE":"0"`, `"VLLM_MAX_TOKENS":"38633"` (from max_tokens field)
- System prompt hash: `["str","cd5b7a44b964bc7609341083a48f03d69b8f2ea343cd1132f795851098c86523"]`
- Parser code hash: `["str","9fe9ce49944f1d1436d1c02f4e94fd100df2d50b538b8ee5479b3b4ada69cb82"]`
- Snapshot text includes a large nested record with many fields; notably:
  - `\"wire_decoder\",\"active_rows\",\"layouts\",\"layout_indexes\",\"wire_fallbacks\",\"adapter_exceptions\"` with layout `\"V\",\"DATABENTO_DBN_MBOMSG_0_62_0\"`
  - `\"scope_public\",\"prefix_seed\",\"receipt_layout\"` with scope `\"BOSS_CAUSAL_PREFIX_V1\"` and kind `\"RESULT_BEARING\"`
  - `\"entity\",\"evidence\",\"graph\",\"input_hash\",\"packet_hash\",\"qsv\",\"qsv_binding\",\"receipt\",\"registry\",\"schema\",\"source_as_of\"`
  - `\"scope_kind\":\"RESULT_BEARING\"`, `\"scope_hash\":\"G\",\"CuaEA2zhh1TgygWg+U4KDaG/gKwzUbUx06ZxI0uCC/k=\"`, `\"teacher_hash\":\"G\",\"C\",\"L\",[\"member_index\",\"member_key\",\"sha256\",\"size_bytes\",\"mbo_records\"],[[\"L\",[[\"V\",0]]],[\"L\",[[\"V\",\"glbx-mdp3-20211003.mbo.dbn.zst\"]]],[\"L\",[[\"G\",\"Q4C9m6g6W63Eg54SeFqkZIF7h+P6wRF2uVHntHREbYg=\"]],[\"L\",[[\"V\",973355]]],[\"L\",[[\"V\",57027]]]]`, `\"teacher_binding\":\"L\",[\"member_index\",\"member_key\",\"sha256\",\"size_bytes\",\"mbo_records\"],[[\"L\",[[\"V\",0]]],[\"L\",[[\"V\",\"glbx-mdp3-20211003.mbo.dbn.zst\"]]],[\"L\",[[\"G\",\"Q4C9m6g6W63Eg54SeFqkZIF7h+P6wRF2uVHntHREbYg=\"]],[\"L\",[[\"V\",973355]]],[\"L\",[[\"V\",57027]]]]`, `\"image_digest\":\"sha256:18998be4e1276d4eb6e98afe80798aa357c1cc37545150de5c210bc9111beb1d\"`, `\"registry_hash\":\"adf5304a845900b4395c2593c5d270ae727867cc9a164132510acb95d5a3091a\"`, `\"source_prefix_hash\":\"null\"`, `\"prefix_rows\":3262`, `\"entity_rows\":3262`, `\"other_entity_rows\":3262`, `\"context_start\":0`, `\"context_end\":0`, `\"outside_context_rows\":0`, `\"context_cursors\":null`, `\"packet_hashes\":[\"af4adca5b8b22ac91214b3adbef08d07f5e0b1d4edc2d15331bce7918faf8e45\"]`, `\"consumed_rows\":3262`, `\"as_of\":1633298413318097271`, `\"t_ctx\":4096`
  - `\"record_recipe\",\"packet_recipe\",\"root\"` with `\"M\",[\"wire_decoder\",...]` and `\"S\",\"L\",3262,[\"V\",160]`, `\"S\",\"L\",3262,[\"V\",1]`, `\"S\",\"L\",3262,[\"V\",111313]`
  - `\"Q\",\"L\",[[\"V\",9223372036854775807],[\"V\",5530000000],[\"V\",5510000000],...]` (a list of 100+ V values representing timestamps in nanoseconds or similar; exact list present but not fully enumerated here due to length; includes values like `9223372036854775807`, `5530000000`, `5510000000`, etc.)
  - `\"D\",0,[...]` (a long list of integers representing flags and offsets; includes values like `1,1,1,1,1,1,1,1,0,1,...`, `1,-191,191,1,1,-189,190,-67,-71,97,42,1,1,1,-156,157,1,1,1,-46,47,1,1,1,1,-95,96,-93,94,1,1,1,-4,5,1,1,-224,0,225,1,1,-224,225,1,-30,-48,26,53,1,1,1,1,1,1,-149,0,12,0,138,-3,4,1,-1,-192,160,-70,104,-1,2,1,-65,66,-10,0,-106,117,0,-235,236,1,1,1,1,-4,0,5,-231,169,-53,-110,33,-39,14,113,-96,-37,152,86,-184,185,-106,-127,14,17,203,-195,196,1,-6,7,1,1,-1,0,2,1,1,1,1,-4,5,-1,2,-24,22,3,-3,-136,137,-129,132,51,-184,0,142,0,0,-269,233,-102a2f...` (truncated in display but exact as given)
  - `\"S\",\"L\",3262,[\"V\",28]` and `\"S\",\"L\",3262,[\"V\",160]`, `\"S\",\"L\",3262,[\"V\",1]`, `\"S\",\"L\",3262,[\"V\",111313]`
  - `\"N\",\"L\",[\"D\",0,[0,0,0,0,...,0]]` (a long list of zeros; length implied by context)
- `\"consumed_rows\": [\"int\",3262]`
- `\"as_of\": [\"int\",1633298413318097271]`
- `\"t_ctx\": [\"int\",4096]`
- The packet includes `\"str\"` hashes like `["str","1e384651e01970c20e5a4196469b097ff179c991fb233d3e70655e1307bc3287"]`, `["str","05420f756442c523b0eefb76d2dd9f17f18ab0248caa9ec33cb5e36991137d0c"]`, etc. (10+ such hashes listed in the first array)
- The `\"snapshot_text\"` field contains a nested structure with `\"codec\"`, `\"data\"`, `\"M\"`, `\"S\"`, `\"N\"`, `\"Q\"`, etc., but no explicit mention of cycle-00 pin layers or frozen learned-structure layers in this part alone
- No explicit mention of `legacy_price`, `legacy_native_signed_flow`, `legacy_per_second_roll20`, `legacy_book_imbalance`, `legacy_structure_observables`, or `frozen learned-structure layers` in text; only in inferred references via schema/scope names

#### (2) What in this part bears on the cycle-00 pin layers `legacy_price`, `legacy_native_signed_flow`, `legacy_per_second_roll20`, `legacy_book_imbalance`, `legacy_structure_observables`, and on the frozen learned-structure layers

- **Direct mention**: None of the explicit strings `legacy_price`, `legacy_native_signed_flow`, `legacy_per_second_roll20`, `legacy_book_imbalance`, `legacy_structure_observables`, or `frozen learned-structure layers` appear verbatim in this part.
- **Indirect bearing via schema/scope**:
  - The `\"schema\"` field in `\"scope_public\"` includes `\"schema\":\"GRANITE_MOUNT_VERIFICATION_V1\"`, `\"scope_kind\":\"RESULT_BEARING\"`, `\"scope_hash\":\"G\",\"CuaEA2zhh1TgygWg+U4KDaG/gKwzUbUx06ZxI0uCC/k=\"`, and `\"registry_hash\":\"adf5304a845900b4395c2593c5d270ae727867cc9a164132510acb95d5a3091a\"`. These are generic verification/scope identifiers; no direct mapping to cycle-00 pin layers is stated.
  - The `\"payload\"` under `\"receipt\"` includes `\"shadow\"` with `\"request\"` containing `\"request_id\"`, `\"identity\"` with `\"base_checkpoint_sha\"`, etc. This suggests the evidence is tied to a shadow request for the cycle, but no explicit reference to pin layers or frozen structure is made.
  - The `\"Q\",\"L\"` field lists timestamps (e.g., `9223372036854775807`, `5530000000`, etc.) and a mapping of `\"V\"` values to `\"R\"` with `\"L\"` indices. This could relate to observables (e.g., price ticks), but no explicit link to `legacy_*` layers or frozen structure is stated.
  - The `\"D\",0,[...]` list of integers (flags/offsets) includes values like `-191,191`, `-189,190`, `-224,225`, etc., which may encode sign/magnitude or delta values typical for price/flow observables, but no explicit naming or layer reference is present.
  - The `\"N\",\"L\",[\"D\",0,[0,0,...,0]]` zeros array suggests default or empty state for observables at this snapshot.
  - The `\"S\",\"L\",3262,[\"V\",160]`, `\"S\",\"L\",3262,[\"V\",1]`, etc., are layout/row counts; no direct semantic link to pin layers.
- **Frozen learned-structure layers**: The `\"registry_hash\"` and `\"source_as_of\"` imply a registry of structures; `\"frozen learned-structure layers\"` might be implied by `\"registry\"` or `\"graph\"` fields, but no explicit "frozen" marker or layer name appears.
- **Conclusion (observed only)**: This part does **not directly observe** any of the pin layer names (`legacy_price`, etc.) or "frozen learned-structure layers". It provides infrastructure metadata (hashes, timestamps, layout counts, shadow request info), which may be used to locate or reference those layers in other parts, but no explicit bearing is observed in this part alone.

#### (3) Instructions the evidence gives the principal

- The evidence is a `\"BOSS_FRANKIE_CONTROLLER_JOURNAL_V1\"` payload with `\"step\":\"CRITIC_RESULT\"`, indicating this is a result from a critic step in the BOSS workflow.
- The `\"payload\"` includes `\"intent_hash\"`, `\"receipt\"` with `\"shadow\"` request details, and `\"snapshot_text\"` describing the packet recipe and data layout.
- The principal (Frankie) is expected to read the delivered evidence (this packet) as part of the journal; the `\"CRITIC_RESULT\"` step suggests evaluation/critique of some output or state.
- No explicit instruction like "update pin layers", "freeze structure", or "apply legacy values" appears in this part. The instruction is implicit in the journal step: read the evidence and merge notes.
- The `\"max_tokens\":38633` and generation config (`temperature=0`, `thinking=false`) indicate the output was generated without reasoning; the snapshot reflects the raw packet.

#### (4) Open questions

- Does the `\"scope_kind\":\"RESULT_BEARING\"` and `\"scope_hash\"` correspond to cycle-00 pin layers (`legacy_price`, etc.) in other parts? (Not observable here; need merge with other parts)
- Is the `\"registry_hash\":\"adf5304a845900b4395c2593c5d270ae727867cc9a164132510acb95d5a3091a\"` the hash for the frozen learned-structure layers, or for the graph/observables? (Not stated; need context from other parts)
- Do the `\"Q\",\"L\"` timestamp mappings (e.g., `9223372036854775807`, `5530000000`, etc.) and `\"D\",0,[...]` flag/offset list encode values for `legacy_price`, `legacy_native_signed_flow`, `legacy_per_second_roll20`, or `legacy_book_imbalance`? (Possible, but no explicit mapping given; need other parts to resolve)
- Is the `\"snapshot_text\"`'s `\"codec\"` and `\"data\"` structure directly referencing the pin layers or frozen layers, or just describing the wire format? (Descriptive only in this part; need other parts for semantic link)
- Does `\"consumed_rows\":3262` indicate that rows 0–3261 have been processed for cycle-00, implying remaining rows (including pin layer data) are in other parts? (Observed fact; consistent with "part 8 of 163")
- Will later parts (e.g., parts containing `legacy_*` names or `frozen learned-structure`) provide the actual values or layer definitions that this packet references via hashes/scopes? (Open; need merge)

> **Distinguish observed from inferred**:
> - *Observed*: packet hashes, config hashes, identity hash, request_id, step="CRITIC_RESULT", intent_hash, snapshot text fields (codec, data, M/S/N/Q), consumed_rows=3262, as_of=1633298413318097271, t_ctx=4096, max_tokens=38633, timestamps in Q list, flag/offset list in D, layout counts (S L 3262 V 160 etc.), zeros array in N D 0.
> - *Inferred*: No direct inference that `scope_kind` maps to pin layers; no inference that `registry_hash` is frozen structure; no inference that `Q` timestamps or `D` flags encode legacy values. These are possible but not stated or implied in this part alone. Only "may relate" is cautious inference; not asserted.

> **Never invented**: No numbers, hashes, or layer names invented. All quoted strings/numbers are taken verbatim from the part.

> **Markdown format**: Notes structured as above.

> **Length**: No limit; concise but complete as per instruction.
