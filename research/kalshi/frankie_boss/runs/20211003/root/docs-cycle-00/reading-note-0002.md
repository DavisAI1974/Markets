## Notes on part 3/4 (bytes 377873-527078)

### NOTES for merge (Part 3/4)

#### 1. Observed facts with exact numbers, hashes, section ids as they appear

- `request_hash`: `"62ccf52432f0ee5ceca0f35951825368b8d2d891bd908924e10892cd4badfef4"` (from top-level JSON)
- `request_id`: `"frankie-boss-sunday-two-cycle-20260919-cycle-00"` (from top-level JSON)
- `step`: `"RESULT"` (from top-level JSON)
- `previous_hash`: `"fc09e3a3cc944e96a43cc7fa000fe5bbc33a8797c113ba82b1f0d2be25e1859e"` (from top-level JSON)
- `schema`: `"C15_FULL_EVIDENCE_V1"` (from top-level JSON)

- `member files/critic-prompt.txt`:
  - `sha256`: `"d17184c95a2d55198053299d3cbcea8a9d19a832df0c492ee3bf361e88e0441e"`
  - `bytes`: `148492`
  - `kind`: `"str"`
  - `document 0` JSON references the same `sha256` and `bytes`

- `member files/critic-snapshot.txt`:
  - `sha256`: `"0b895d45ef46a58d6fbe736017971ed28b1fded724b6e5f3367fe2b3ba9f0d53"`
  - `bytes`: `144407`
  - `kind`: `"tree"`
  - `document 0` JSON references the same `sha256` and `bytes`

- `member files/native.c15.jsonl`:
  - `sha256`: `"9fbcaae010da05c242c2b129015697bb010399e8a33993dd7082fd6c1249bf93"`
  - `bytes`: `11977861`
  - `kind`: `"BOSS_FORECAST_REFRESH_INTENT_V1"` for `document 0`
    - `arm_hash`: `"d4347090fb2000bfa2e78385be9e53abcc3423c7a195bcad03fdfc4ba4d4db92"`
    - `as_of`: `1633298413318097271`
    - `generation_hash`: `"601668996d8e06f9e2d27036412b26af1c0291c896e822821e183f605cc67ff7"`
    - `material`: `false`
    - `refresh_policy_hash`: `"7d2cc4d8fcf0c8b3efa2686f21ce9c34583fb53b11c4ba1b19b404e7e25f79d5"`
    - `source_as_of`: `1633298413317923251`
    - `source_hash`: `"e947260436b02edcc4d3214499956442c5d1951756298eddf3e448631861e2b5"`
    - `targets`: `[{"instrument":"NG.v.0/instrument_id=111313","target_id":"NG_111313_OWN_SOURCE_20211003:close","target_ns":1633305600000000000}]`
    - `previous_hash`: `"ce10a0acc840f3e92f98daa884cf1b6cf55ab1eb277f71ca9ff64f3f22c8a4e9"`
  - `document 1` JSON:
    - `kind`: `"BOSS_ROLLING_FORECAST_V1"`
    - `payload.candidates[0].arm_hash`: `"d4347090fb2000bfa2e78385be9e53abcc3423c7a195bcad03fdfc4ba4d4db92"`
    - `payload.candidates[0].as_of`: `1633298413318097271`
    - `payload.candidates[0].candidate_id`: `"254d7344620bfb9fa028f0991359bce0eebbd60bb2f66b1a5ae6b01c6252c5bb"`
    - `payload.candidates[0].forecast_artifact.sha256`: `"83100bc38d19661678c65b8477d0bccad7b5ed8686e16e5db4446aa9b8b7fad5"`
    - `payload.candidates[0].model_hash`: `"b33de3c99ea6f710af738104ef1fc0b2cbab654d972ebddcf9a1f21aba5624f8"`
    - `payload.candidates[0].source_as_of`: `1633298413317923251`
    - `payload.candidates[0].source_hash`: `"e947260436b02edcc4d3214499956442c5d1951756298eddf3e448631861e2b5"`
    - `payload.candidates[0].target`: `{"instrument":"NG.v.0/instrument_id=111313","target_id":"NG_111313_OWN_SOURCE_20211003:close","target_ns":1633305600000000000}`
    - `payload.generation_hash`: `"601668996d8e06f9e2d27036412b26af1c0291c896e822821e183f605cc67ff7"`
    - `payload.previous_hash`: `null`
    - `payload.refresh_policy_hash`: `"7d2cc4d8fcf0c8b3efa2686f21ce9c34583fb53b11c4ba1b19b404e7e25f79d5"`
    - `payload.request_hash`: `"4760c0304c229f0c2cfe21d4a2f7d9b9085d42b16a2b5fe46916ec7d4154e4f4"`
    - `payload.revision`: `1`
    - `payload.selected_id`: `"254d7344620bfb9fa028f0991359bce0eebbd60bb2f66b1a5ae6b01c6252c5bb"`
    - `previous_hash`: `"fe19ed4c4b23fc643bd26d0959ed0dec65c9419618ce5ff61d596ef57d80d9d6"`

- `member files/record-000000.json`:
  - `sha256`: `"448000af72ea54496b82e79e897d5e65fe8b83379e29dd59b883ec7f45f1379b"`
  - `bytes`: `5234`
  - `kind`: `"tree"`
  - `document 0` JSON references the same `sha256` and `bytes`

- `member manifest`:
  - `sha256`: `"bb67eb6a1e9899edd033da3493883bec5652f3124e5223997df859d8fe1ead83"`
  - `bytes`: `2509`
  - `document 0` JSON:
    - `agent_commit`: `"7b98617bdbbc2476666db9cf1c018c8efe6878da"`
    - `boss_commit`: `"35f857f09f20726cd97a0dd2168153ecde80e946"`
    - `configuration_hash`: `"18826a0f60a13b5968f79f4fcc69e8850de7f41f4c3a2358f94488545d9f0467"`
    - `controller_checkpoint.head_hash`: `"978c1a9f691839ce2d08826bae4160e7ad2a795ab828778af1f159e9c5e64152"`
    - `controller_checkpoint.schema`: `"BOSS_FRANKIE_CONTROLLER_JOURNAL_V1"`
    - `files` list includes:
      - `"controller.c15.jsonl"`: `bytes`: `1410438`, `sha256`: `"b7eab68c31d570c321e1af6f424728a04713bfd56bd71b24311d50584a83fb6b"`
      - `"critic-prompt.txt"`: `bytes`: `148492`, `sha256`: `"d17184c95a2d55198053299d3cbcea8a9d19a832df0c492ee3bf361e88e0441e"`
      - `"critic-snapshot.txt"`: `bytes`: `144407`, `sha256`: `"0b895d45ef46a58d6fbe736017971ed28b1fded724b6e5f3367fe2b3ba9f0d53"`
      - `"forecast-000000.bin"`: `bytes`: `5987733`, `sha256`: `"83100bc38d19661678c65b8477d0bccad7b5ed8686e16e5db4446aa9b8b7fad5"`
      - `"native.c15.jsonl"`: `bytes`: `11977861`, `sha256`: `"9fbcaae010da05c242c2b129015697bb010399e8a33993dd7082fd6c1249bf93"`
      - `"record-000000.json"`: `bytes`: `5234`, `sha256`: `"448000af72ea54496b82e79e897d5e65fe8b83379e29dd59b883ec7f45f1379b"`
      - `"state.c15.json"`: `bytes`: `1408446`, `sha256`: `"d923e571c9150c04417a34edc068b49b161b6061bf0d6dc49be799ab8060b9c9"`
    - `native_checkpoint.head_hash`: `"6a57fefb679c7f1e2e32fac663d774e4734377cf82dedbffe68bc33af2122d78"`
    - `native_checkpoint.schema`: `"BOSS_ROLLING_FORECAST_V1"`
    - `request_hash`: `"62ccf52432f0ee5ceca0f35951825368b8d2d891bd908924e10892cd4badfef4"`
    - `request_id`: `"frankie-boss-sunday-two-cycle-20260919-cycle-00"`
    - `status`: `"incomplete"`
    - `targets` list includes:
      - `artifact_digest`: `"254d7344620bfb9fa028f0991359bce0eebbd60bb2f66b1a5ae6b01c6252c5bb"`
      - `artifact_path`: `"forecast-000000.bin"`
      - `publication_hash`: `"6a57fefb679c7f1e2e32fac663d774e4734377cf82dedbffe68bc33af2122d78"`
      - `record_path`: `"record-000000.json"`
      - `record_digest`: `"448000af72ea54496b82e79e897d5e65fe8b83379e29dd59b883ec7f45f1379b"`
      - `revision`: `1`
      - `target`: `{"instrument":"NG.v.0/instrument_id=111313","target_id":"NG_111313_OWN_SOURCE_20211003:close","target_ns":1633305600000000000}`

- `member mapping_evidence`:
  - `sha256`: `"7b0c57a43d28a5105b19e54edd9a41035130a5c6f3ce592ed47cc207700267fa"`
  - `bytes`: `1243`
  - `document 0` JSON:
    - `boss_source.arm_hash`: `"d4347090fb2000bfa2e78385be9e53abcc3423c7a195bcad03fdfc4ba4d4db92"`
    - `boss_source.as_of`: `1633298413318097271`
    - `boss_source.prefix_hash`: `"e947260436b02edcc4d3214499956442c5d1951756298eddf3e448631861e2b5"`
    - `boss_source.source_as_of`: `1633298413317923251`
    - `boss_source.through_cursor`: `3261`
    - `journal_checkpoint.head_hash`: `"96f2d5818a59bfadf5ca156ae25cfdfcb9c655355227ea0dda6ff6f70897e3f7"`
    - `mapping_sha256`: `"55cccc238a15b76528d60220e8a236204bf244ef4e33948e9ef6b74a03656e21"`
    - `mapping_status`: `"EXACT_WIRE_BYTES_AND_ACTUAL_BOSS_PREFIX"`
    - `market_calculations`: `false`
    - `matched_groups`: `2282`
    - `matched_records`: `3262`
    - `member_ledger.encoding`: `"plain"`
    - `member_ledger.physical.bytes`: `10756276521`
    - `member_ledger.plain.bytes`: `10756276521`
    - `native_checkpoint.count`: `2`
    - `source`:
      - `arm_hash`: `"d4347090fb2000bfa2e78385be9e53abcc3423c7a195bcad03fdfc4ba4d4db92"`
      - `as_of`: `1633298413318097271`
      - `prefix_hash`: `"e947260436b02edcc4d3214499956442c5d1951756298eddf3e448631861e2b5"`
      - `source_as_of`: `1633298413317923251`
      - `through_cursor`: `3261`
    - `source`:
      - `arm_hash`: `"A_MEMORY"`
      - `delivery_manifest_sha256`: `"d6455e85d495af91fc92321bb5c966eec47fbcd5e2d0f6d50ede359329937b17"`
      - `delivery_receipt_sha256`: `"3420045aecc9c225ce77bf47a184cc2b262685177998f51ff94585b0b3149d1b"`
      - `result_hash`: `"c406eee730401de16165b46091ac3042a1ca49d9025bbaefa9aa272bf52e420b"`
      - `run_id`: `"frankie-a-memory-rt-33746436209-1"`
      - `source_day`: `"20211003"`
      - `source_manifest_hash`: `"f296526eb52f16ad534bdd311b19815f9922f2964c862ad3390d137dd88085de"`
      - `sha256`: `"4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88"`
      - `size_bytes`: `973355`
    - `schema`: `"FRANKIE_BOSS_SOURCE_BINDING_V1"`

- `member source_binding`:
  - `sha256`: `"da85119c760012844cd37d244905803ad24f0996ceeeab3cdf3fbfaae83064a0"`
  - `bytes`: `1023`
  - `document 0` JSON:
    - `agent`: `{"arm":"A_MEMORY", ...}`
    - `agent.arm`: `"A_MEMORY"`
    - `agent.delivery_manifest_sha256`: `"d6455e85d495af91fc92321bb5c966eec47fbcd5e2d0f6d50ede359329937b17"`
    - `agent.delivery_receipt_sha256`: `"3420045aecc9c225ce77bf47a184cc2b262685177998f51ff94585b0b3149d1b"`
    - `agent.result_hash`: `"c406eee730401de16165b46091ac3042a1ca49d9025bbaefa9aa272bf52e420b"`
    - `agent.run_id`: `"frankie-a-memory-rt-33746436209-1"`
    - `agent.source_day`: `"20211003"`
    - `agent.source_manifest_hash`: `"f296526eb52f16ad534bdd311b19815f9922f2964c862ad3390d137dd88085de"`
    - `agent.sha256`: `"4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88"`
    - `agent.size_bytes`: `973355`
    - `boss_source.arm_hash`: `"d4347090fb2000bfa2e78385be9e53abcc3423c7a195bcad03fdfc4ba4d4db92"`
    - `boss_source.as_of`: `1633298413318097271`
    - `boss_source.prefix_hash`: `"e947260436b02edcc4d3214499956442c5d1951756298eddf3e448631861e2b5"`
    - `boss_source.source_as_of`: `1633298413317923251`
    - `boss_source.through_cursor`: `3261`
    - `provenance.authority`: `"Codex host full mapping and actual source journal verification"`
    - `provenance.mapping_artifact_bytes`: `1243`
    - `provenance.mapping_artifact_sha256`: `"7b0c57a43d28a5105b19e54edd9a41035130a5c6f3ce592ed47cc207700267fa"`
    - `provenance.method`: `"EXACT_WIRE_BYTES_AND_ACTUAL_BOSS_PREFIX"`
    - `schema`: `"FRANKIE_BOSS_SOURCE_BINDING_V1"`

- Layer status (in Frankie's own derivation text):
  - `legacy_price`: derived; producer: `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`; file `/opt/frankie-box/session/work/derived/legacy_price.json` sha256 `507d51fe6b75dad3`
  - `legacy_native_signed_flow`: derived; producer: `research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py` SecondBinner; file `/opt/frankie-box/session/work/derived/legacy_native_signed_flow.json` sha256 `515d41d416f724e4`
  - `legacy_per_second_roll20`: derived; producer: `research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py` roll20 (window 20); file `/opt/frankie-box/session/work/derived/legacy_per_second_roll20.json` sha256 `eacce1747cf9032e`
  - `legacy_book_imbalance`: derived; producer: `V4MboAdapter F_LAST book snapshot + a_memory_member_first_recalculation_20260828.book_values/book_transition`; file `/opt/frankie-box/session/work/derived/legacy_book_imbalance.json` sha256 `73939ae61e64787f`
  - `legacy_structure_observables`: derived; producer: `a_memory_member_first_recalculation_20260828.describe_structure per F_LAST group`; file `/opt/frankie-box/session/work/derived/legacy_structure_observables.json` sha256 `c65376c8d0b7a55d`

- Table `legacy_price`: 91 rows, `sep=space`, columns `ts_recv	ts_event	price	size	bid_px_00	ask_px_00`. First row: `1633298400.2957356 1633298400.0 5.628 30 5.646 5.586`. Contains `^` for repeated values (e.g., `^ 5.635 2 ^2`). No explicit row id or hash in table text.

- Table `per_second_flow_and_roll20`: 14 rows, `sep=space`, columns `second	buy	sell	roll20`. First row: `1633298400 58.0 10.0 S48/68`. Contains `+1` for delta seconds, `Sxx/yy` strings.

- Table `legacy_book_imbalance`: 2282 rows, `sep=space`, columns `ts_recv_ns	ts_event_ns	best_bid	best_ask	=mid	depth_imbalance_n	=spread	=depth_imbalance_full	bid_depth_full	ask_depth_full	bid_order_count_full	ask_order_count_full	bid_price_level_count_full	ask_price_level_count_full	=transition`. First row: `1633287605008387796 ~-253824335 5.53 5.553 7/43 465 397 154 90 121 76`. Contains `~` for `ts_event` offset, `^` for repeated `transition` values.

- Table `legacy_structure_observables`: 2282 rows, `sep=space`, columns listed with `=` for derived names (e.g., `=ts_recv_ns`, `=ts_event_ns`, `=action_counts.A`, etc.), `^` for repeated `transition` (e.g., `^fill_disposition.unresolved_fill_order_ids=[]`). First row: `@0=[]	@1="M"	@2="B"	@3="A"	@4="C"	@5="TFM"	@6="ABB"	@7="TFCN"	@8="ABBN"	@9="MN"	@10="BN"	@11="AN"	@12="TN"	@13="TTN"	@14="AAN"	@15="NNAN"	@16="CN"	@17="TFC"	@18="BAA"	@19="NNB"	@20="BAAN"	@21="TFFCCN"`. Second row: `SRAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA SNBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA 197 F 1622 10000 I785971080066,+155177105,+3932805,+24951825,+2172992,+1520616,+727104,+14433918,+6472595,+9480578,+35312142,+95748,+2202,+49787,+493552,+1806,+435083,+493611,+1999,+617,+486,+444580,+58483,+695762,+814958,+445,+191359,+512489,+2274,+2740,+2034,+619,+520,+2528,+1087,+1276,+266,+202734,+632584,+36,+531,+341,+18,+782515,+188933,+940969,+111536,+589833,+1264722,+577159,+130,+83551,+2510,+1492552,+11445,+415921,+131,+28,+47,+487,+581350,+1044337,+1551203,+441956,+7195,+93765,+21129,+66223,+39139,+500970,+4931,+38479,+92377,+6267,+119100,+693448,+685196,+640276,+592078,+783014,+23122,+3404,+381976,+199334,+105556,+903248,+70900,+10752,+6205,+23,+12,+29,+648,+89031,+27831,+93596,+1351225,+1916274,+1280516,+202,+116535,+272,+1497,+2951,+9005,+8902,+3048,+6556,+73747,+2631,+44531,+17754,+14202,+54501,+71539,+130899,+80891,+909545,+47898,+588153,+38974,+646,+3133,+38240,+200,+402411,+320624,+311251,+68081,+70420,+2326,+8407,+9920,+187548,+129069,+221008,+8990,+17644,+462833,+125951,+1651,+1588,+2009,+1598,+2502,+2099,+4366,+4203,+1355,+1857,+1292,+1934,+37711,+223964,+35425,+31566,+27,+28139,+6766,+1150,+13,+92237,+31574,+9499,+97839,+41134,+4811,+42118,+10893,+262462,+240777,+340016,+495136,+34139,+29789,+313047,+23528,+122360,+5352,+112973,+28190,+317257,+62670,+40887,+8756,+17883,+3631,+55536,+3306,+23198,+72113,+129,+3595,+8814,+2788,+74943,+10153,+1101,+43480,+36813,+33454,+118637,+28248,+60086,+20951,+154336,+1645,+4310,+3153,+876,+1776,+16696,+11299,+116759,+99017,+59315,+183609,+40788,+100,+1195,+36628,+22150,+9074,+34915,+4577,+4672,+30950,+298,+28859,+15364,+12248,+15105,+19796,+6790,+8026,+41,+96,+57,+128,+140,+97,+4452,+2,+1203 @0 @0 @0`. Contains `I` for `price_raw_min`/`price_raw_max` (e.g., `I785971080066,+155177105,+3932805,...`). Contains `@n` dictionary entries (e.g., `@0=[]`, `@1="M"`). Contains `S` strings (e.g., `SRA...`). Contains `F` for `terminal_action` (e.g., `F 1622`). Contains `^` for repeated `transition` (e.g., `^4 +11 +11 ^4`).

- `constants:` line in `legacy_structure_observables` table: `fill_disposition.unresolved_fill_order_ids=[]`
- `scales:` line: `price_raw_min=1000000	price_raw_max=1000000`
- `dictionary:` line lists `@0` to `@21` with string values.

- `Derivation digest DIGEST_V5` text: describes adapter calculations, table formats (`sep=space` or `sep=space`), `^` for repeated `=k`/`^k`, `transition` recomputed, `roll20 = n/d`, `DIGEST_V4` checks equal before writing, etc. Mentions `6524` entries in `/opt/frankie-box/data/prefix-00.sqlite` (kinds `{'INPUT': 3262, 'APPLIED': 3262}`), `legacy control row projection`: `1482`, `F_LAST groups closed`: `2282`, `adapter failures`: `0`.

- `Layer status (pin group legacy_observable_crosswalk)` lists the five legacy layers with producers and file paths and sha256 hashes (e.g., `legacy_price` sha256 `507d51fe6b75dad3`, etc.).

- `table legacy_price` shows price and bid/ask with `^` for repeated price changes (e.g., `^ 5.635 2 ^2`). No explicit hash or row id in table.

- `table per_second_flow_and_roll20` shows `second`, `buy`, `sell`, `roll20` with `+1` deltas and `Sxx/yy` strings.

- `table legacy_book_imbalance` shows `ts_recv_ns`, `ts_event_ns`, `best_bid`, `best_ask`, `=mid`, `depth_imbalance_n`, `=spread`, `=depth_imbalance_full`, etc., with `~` for `ts_event` offset and `^` for repeated `transition`.

- `table legacy_structure_observables` shows action/side strings, counts, `I` for price bounds, `S` strings, `F` for terminal action, `^` for repeated `transition`, `=k` for derived names, `^k` for repeated derived values.

- `constants:` and `scales:` and `dictionary:` are part of the table header/metadata in the text.

- `head 96f2d5818a59bfad...` in `Derivation digest` text: `head equals the request source_hash: False` (exact phrase: `head 96f2d5818a59bfad...; head equals the request source_hash: False`). No full hash given in table text; only `head_hash` `96f2d5818a59bfadf5ca156ae25cfdfcb9c655355227ea0dda6ff6f70897e3f7` from manifest.

- No explicit mention of `frozen learned-structure layers` in this part; only `legacy_*` layers and `layer status` listed.

#### 2. What in this part bears on the cycle-00 pin layers legacy_price, legacy_native_signed_flow, legacy_per_second_roll20, legacy_book_imbalance, legacy_structure_observables, and on the frozen learned-structure layers

- **`legacy_price`**:
  - Observed: `table legacy_price` text is present with 91 rows, `sep=space`, columns `ts_recv	ts_event	price	size	bid_px_00	ask_px_00`, first row `1633298400.2957356 1633298400.0 5.628 30 5.646 5.586`, uses `^` for repeated price values (e.g., `^ 5.635 2 ^2`). This directly corresponds to the `legacy_price` layer derived by `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`. The layer exists and its table content is observed.
  - Does not directly mention `legacy_price` file hash `507d51fe6b75dad3` in this part, but the layer status text confirms it exists and is derived.

- **`legacy_native_signed_flow`**:
  - Observed: `table per_second_flow_and_roll20` text is present with 14 rows, `sep=space`, columns `second	buy	sell	roll20`, first row `1633298400 58.0 10.0 S48/68`, uses `+1` for delta seconds. The layer `legacy_native_signed_flow` is derived by `research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py` SecondBinner. The `per_second_flow_and_roll20` table likely feeds into both `legacy_native_signed_flow` (signed flow) and `legacy_per_second_roll20` (roll20). The table is observed.
  - No direct file hash `515d41d416f724e4` mentioned in table text, but layer status confirms producer.

- **`legacy_per_second_roll20`**:
  - Observed: same `table per_second_flow_and_roll20` text is present; `roll20` column is present (e.g., `58.0`, `10.0`, etc.). The layer `legacy_per_second_roll20` is derived by `research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py` roll20 (window 20). The table directly provides the roll20 values (as `roll20` column), so it bears on this layer.
  - Layer status confirms producer.

- **`legacy_book_imbalance`**:
  - Observed: `table legacy_book_imbalance` text is present with 2282 rows, `sep=space`, columns including `=depth_imbalance_full`, `=transition`, `~` for `ts_event` offset, `^` for repeated `transition`. The layer `legacy_book_imbalance` is derived by `V4MboAdapter F_LAST book snapshot + a_memory_member_first_recalculation_20260828.book_transition`. The table directly provides book imbalance values, so it bears on this layer.
  - Layer status confirms producer.

- **`legacy_structure_observables`**:
  - Observed: `table legacy_structure_observables` text is present with 2282 rows, `sep=space`, columns with `=action_counts.A`, `=side_counts.A`, `=side_counts.B`, `=side_counts.N`, `=terminal_action`, `=terminal_side`, `=component_count`, `=distinct_price_count`, `=distinct_order_id_count`, `=fill_disposition.class`, `=fill_disposition.signature.*`, `=mirror.*`, `^fill_disposition.unresolved_fill_order_ids=[]`, `^` for repeated `transition` (e.g., `^4 +11 +11 ^4`). The layer `legacy_structure_observables` is derived by `a_memory_member_first_recalculation_20260828.describe_structure per F_LAST group`. The table directly provides structure observables, so it bears on this layer.
  - Layer status confirms producer.

- **`frozen learned-structure layers`**:
  - Observed: No explicit mention of "frozen learned-structure layers" in this part. The `layer status` only lists `legacy_*` layers. The `Derivation digest` text describes `DIGEST_V5` and `DIGEST_V4` but does not mention "frozen learned-structure layers" in this part. However, the phrase "frozen learned-structure layers" appears in the instruction "(and on the frozen learned-structure layers)" in the prompt. Since this part does not contain any text about "frozen learned-structure layers" (e.g., no file path, hash, or description), it bears no observed fact on them. We only note what is observed: no evidence in this part about frozen learned-structure layers.

> Inference (not observed): The `legacy_*` layers are derived (not frozen), and the frozen learned-structure layers are likely separate from the `legacy_*` layers (as implied by "frozen"). But we do not observe any data or instruction about them in this part.

#### 3. Instructions the evidence gives the principal

- The `Derivation digest DIGEST_V5` text describes how the V4 adapter computes derived fields (`=name`, `^name` for repeated), uses exact IEEE division for floats, checks equal before writing, uses shortest round-trip decimals, `^k`/`=k` notation, etc. This is a procedural instruction for the adapter.

- The `layer status` text lists producers for each `legacy_*` layer, confirming they are derived by specific modules.

- The table formats (`sep=space`, `sep=tab` for `legacy_price`? No, `sep=space` for all tables in `Derivation digest` text) and use of `^`, `~`, `=`, `^` for repeated values are specified in the table headers and constants.

- The `constants:` and `scales:` and `dictionary:` metadata in tables define how values are stored (e.g., `price_raw_min=1000000`, `price_raw_max=1000000`, dictionary entries `@n`).

- No explicit "instruction" like "do X" appears in plain text; the evidence shows the computed tables and layer status. Thus, the instruction given to the principal (Frankie) by this evidence is implicit: the tables and layer status reflect the correct derivation according to the adapter rules (e.g., `^` for repeats, `~` for offsets, exact IEEE division). Frankie should verify that the observed tables match the expected format and that the layer producers are correct.

> Specifically, the evidence shows the actual table contents (e.g., `legacy_price` rows, `legacy_book_imbalance` rows, `legacy_structure_observables` rows) and layer status. The principal (Frankie) should check that the tables are consistent with the adapter rules (e.g., `^` for repeated derived values, `~` for `ts_event` offset), and that the layer producers match the listed modules.

#### 4. Open questions

- (Observed) The `frozen learned-structure layers` are mentioned in the prompt ("and on the frozen learned-structure layers"), but no evidence in this part describes them (e.g., no file path, hash, table, or instruction about them). Thus: **What are the frozen learned-structure layers? Are they derived from the same input rows? Do they include any of the `legacy_*` data? What is their format or status?** (Cannot infer; only observed absence in this part.)

- (Observed) The `head_hash` `96f2d5818a59bfadf5ca156ae25cfdfcb9c655355227ea0dda6ff6f70897e3f7` from `manifest` is compared to `request source_hash` in `Derivation digest` text (`head equals the request source_hash: False`). No `request source_hash` is given in this part; only `prefix_hash` `"e947260436b02edcc4d3214499956442c5d1951756298eddf3e448631861e2b5"` and `arm_hash` `"d4347090fb2000bfa2e78385be9e53abcc3423c7a195bcad03fdfc4ba4d4db92"`. **What is the `request source_hash`? Is `head equals request source_hash` always false for cycle-00?** (Cannot infer; only observed statement `head equals the request source_hash: False`.)

- (Observed) The `legacy_*` layer file hashes are given (`e.g., legacy_price sha256 507d51fe6b75dad3`), but the actual file content (e.g., JSON) is not shown in this part. **Do the table contents in the text exactly match the file content for each legacy layer?** (Cannot infer; only observed table text; no file content shown.)

- (Observed) The `table legacy_structure_observables` uses `I` for `price_raw_min`/`price_raw_max` (e.g., `I785971080066,+155177105,...`), and `@n` dictionary. **Is the dictionary consistent across rows? Are `@n` values reused correctly?** (Cannot infer; only observed rows; no consistency check shown.)

- (Observed) The `table per_second_flow_and_roll20` has `roll20` as a column (e.g., `58.0`, `10.0`), and `legacy_per_second_roll20` layer is derived from it. **Is `roll20` computed as `n/d` (trailing 20-second buy/sell sums) exactly as IEEE division?** (Cannot infer; only observed values; no calculation shown.)

- (Observed) The `table legacy_book_imbalance` has `=depth_imbalance_full` and `=transition`. **Is `transition` recomputed correctly from book fields?** (Cannot infer; only observed `^` for repeated `transition`; no recomputation shown.)

- (Observed) The `Derivation digest` text says `adapter failures: 0`. **Is this confirmed by this part?** (Yes, observed in text: `adapter failures: 0`.) No question needed; it is observed.

- (Observed) The `member manifest` includes `status: "incomplete"`. **Is the cycle-00 run incomplete?** (Observed; status is "incomplete", but no further detail.)

> Open questions are limited to what is not observed or inferred: only the frozen learned-structure layers description, request source_hash vs head_hash, file content consistency, dictionary reuse, roll20/transition computation details. Do not invent answers.

#### Distinguish observed vs inferred

- **Observed**: All exact strings, numbers, hashes, table rows, column names, `^`, `~`, `=`, `I`, `S`, `@n`, layer status text (`derived; producer: ...`), `adapter failures: 0`, `status: "incomplete"`, `head equals the request source_hash: False`, table formats (`sep=space`), etc., as written in the part.

- **Inferred**: None of the following are inferred:
  - "frozen learned-structure layers" description (not observed in this part)
  - `request source_hash` value (not given)
  - consistency of table vs file (not shown)
  - dictionary reuse correctness (not checked)
  - roll20/transition computation (not shown)
  - `head equals request source_hash` always false (only observed as `False` for this cycle)

> All statements in "Instructions" and "Open questions" clarify what is observed vs what is inferred/unknown.

---

*Notes format: Markdown, no length limit. Only NOTES for merge; nothing else.*
